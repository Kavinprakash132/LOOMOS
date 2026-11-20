"""Owner-only advances (uthaav), 4-mode payroll calculation, immutable payslips & trilingual print data."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit, snapshot_fields, soft_delete_record
from app.core.config import today_ist
from app.core.database import get_db
from app.core.i18n import get_payslip_translations
from app.core.security import require_owner
from app.models.core import Advance, Payslip, UnitSettings, User, Weaver
from app.schemas.step1 import SlipLangCode, SoftDeleteRequest
from app.schemas.step2 import (
    AdvanceCreate,
    AdvanceResponse,
    PayslipCalculateRequest,
    PayslipFinalizeRequest,
    PayslipLinePreview,
    PayslipResponse,
    PrintablePayslipResponse,
)
from app.services.payroll_service import calculate_payroll_preview

router = APIRouter(prefix="/api/v1", tags=["payroll"])


def _hydrate_payslip(slip: Payslip, weaver: Weaver | None) -> PayslipResponse:
    res = PayslipResponse.model_validate(slip)
    res.weaver_name = weaver.full_name if weaver else f"Worker #{slip.weaver_id}"
    res.preferred_slip_lang = (weaver.preferred_slip_lang if weaver else "en")  # type: ignore[assignment]
    return res


# ---------------------------------------------------------------------------
# Advances (Uthaav)
# ---------------------------------------------------------------------------
@router.get("/advances", response_model=list[AdvanceResponse])
def list_advances(
    weaver_id: int | None = None,
    include_deleted: bool = False,
    _owner: Annotated[User, Depends(require_owner)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> list[AdvanceResponse]:
    stmt = select(Advance).order_by(Advance.advance_date.desc(), Advance.id.desc())
    if not include_deleted:
        stmt = stmt.where(Advance.is_deleted.is_(False))
    if weaver_id is not None:
        stmt = stmt.where(Advance.weaver_id == weaver_id)
    rows = db.scalars(stmt).all()
    weavers = {w.id: w.full_name for w in db.scalars(select(Weaver)).all()}
    out = []
    for r in rows:
        item = AdvanceResponse.model_validate(r)
        item.weaver_name = weavers.get(r.weaver_id)
        out.append(item)
    return out


@router.post("/advances", response_model=AdvanceResponse, status_code=status.HTTP_201_CREATED)
def create_advance(
    payload: AdvanceCreate,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> AdvanceResponse:
    weaver = db.get(Weaver, payload.weaver_id)
    if not weaver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weaver/worker not found")
    adv = Advance(
        weaver_id=payload.weaver_id,
        advance_date=payload.advance_date,
        amount_paise=payload.amount_paise,
        note=payload.note,
        created_by=owner.id,
    )
    db.add(adv)
    db.flush()
    record_audit(
        db,
        entity_type="advance",
        entity_id=adv.id,
        action="CREATE",
        changed_by=owner.id,
        new_values=snapshot_fields(adv, ["weaver_id", "advance_date", "amount_paise"]),
    )
    db.commit()
    db.refresh(adv)
    res = AdvanceResponse.model_validate(adv)
    res.weaver_name = weaver.full_name
    return res


@router.delete("/advances/{advance_id}", response_model=AdvanceResponse)
def soft_delete_advance(
    advance_id: int,
    payload: SoftDeleteRequest,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> AdvanceResponse:
    adv = db.get(Advance, advance_id)
    if not adv or adv.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Advance not found")
    soft_delete_record(
        db,
        obj=adv,
        entity_type="advance",
        entity_id=adv.id,
        user_id=owner.id,
        reason=payload.reason.strip(),
        audit_fields=["weaver_id", "advance_date", "amount_paise"],
    )
    db.commit()
    db.refresh(adv)
    return AdvanceResponse.model_validate(adv)


# ---------------------------------------------------------------------------
# 4-Mode Payroll Preview, Finalization, Void & Trilingual Printable Slip
# ---------------------------------------------------------------------------
@router.post("/payslips/preview", response_model=list[PayslipLinePreview])
def preview_payroll(
    payload: PayslipCalculateRequest,
    _owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> list[PayslipLinePreview]:
    rows = calculate_payroll_preview(
        db,
        period_start=payload.period_start,
        period_end=payload.period_end,
        weaver_ids=payload.weaver_ids,
        deduct_period_advances=payload.deduct_period_advances,
        defect_deductions_paise=payload.defect_deductions_paise,
    )
    return [PayslipLinePreview.model_validate(r) for r in rows]


@router.post("/payslips/finalize", response_model=list[PayslipResponse], status_code=status.HTTP_201_CREATED)
def finalize_payslips(
    payload: PayslipFinalizeRequest,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> list[PayslipResponse]:
    if payload.period_end < payload.period_start:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid period range")

    weavers = {w.id: w for w in db.scalars(select(Weaver)).all()}
    created: list[Payslip] = []
    seen_req_weavers: set[int] = set()
    for item in payload.items:
        if item.weaver_id not in weavers:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Weaver {item.weaver_id} not found")
        if item.weaver_id in seen_req_weavers:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Duplicate payslip row for {weavers[item.weaver_id].full_name} in request",
            )
        seen_req_weavers.add(item.weaver_id)
        existing_slip = db.scalar(
            select(Payslip.id).where(
                Payslip.weaver_id == item.weaver_id,
                Payslip.period_start == payload.period_start,
                Payslip.period_end == payload.period_end,
                Payslip.is_deleted.is_(False),
            )
        )
        if existing_slip:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Payslip already finalized for {weavers[item.weaver_id].full_name} "
                    f"({payload.period_start} to {payload.period_end}). Void it first to regenerate."
                ),
            )
        net_p = max(0, item.gross_paise - item.advance_deducted_paise - item.defect_deduction_paise)
        slip = Payslip(
            weaver_id=item.weaver_id,
            period_start=payload.period_start,
            period_end=payload.period_end,
            wage_mode_snapshot=item.wage_mode_snapshot,
            units_worked=item.units_worked,
            rate_paise_snapshot=item.rate_paise_snapshot,
            gross_paise=item.gross_paise,
            advance_deducted_paise=item.advance_deducted_paise,
            defect_deduction_paise=item.defect_deduction_paise,
            net_payable_paise=net_p,
            status="FINALIZED",
            created_by=owner.id,
        )
        db.add(slip)
        db.flush()
        record_audit(
            db,
            entity_type="payslip",
            entity_id=slip.id,
            action="FINALIZE",
            changed_by=owner.id,
            new_values=snapshot_fields(
                slip,
                ["weaver_id", "period_start", "period_end", "wage_mode_snapshot", "gross_paise", "net_payable_paise"],
            ),
        )
        created.append(slip)
    db.commit()
    return [_hydrate_payslip(s, weavers.get(s.weaver_id)) for s in created]


@router.get("/payslips", response_model=list[PayslipResponse])
def list_payslips(
    include_deleted: bool = False,
    _owner: Annotated[User, Depends(require_owner)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> list[PayslipResponse]:
    stmt = select(Payslip).order_by(Payslip.period_end.desc(), Payslip.id.desc())
    if not include_deleted:
        stmt = stmt.where(Payslip.is_deleted.is_(False))
    slips = db.scalars(stmt).all()
    weavers = {w.id: w for w in db.scalars(select(Weaver)).all()}
    return [_hydrate_payslip(s, weavers.get(s.weaver_id)) for s in slips]


@router.delete("/payslips/{payslip_id}", response_model=PayslipResponse)
def soft_delete_payslip(
    payslip_id: int,
    payload: SoftDeleteRequest,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> PayslipResponse:
    """Void a finalized payslip via soft-delete + immutable audit log (never hard deleted)."""
    slip = db.get(Payslip, payslip_id)
    if not slip or slip.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payslip not found")
    soft_delete_record(
        db,
        obj=slip,
        entity_type="payslip",
        entity_id=slip.id,
        user_id=owner.id,
        reason=payload.reason.strip(),
        audit_fields=["weaver_id", "period_start", "period_end", "gross_paise", "net_payable_paise"],
    )
    db.commit()
    db.refresh(slip)
    return _hydrate_payslip(slip, db.get(Weaver, slip.weaver_id))


@router.get("/payslips/{payslip_id}/printable", response_model=PrintablePayslipResponse)
def get_printable_payslip(
    payslip_id: int,
    lang: SlipLangCode | None = Query(default=None),
    _owner: Annotated[User, Depends(require_owner)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> PrintablePayslipResponse:
    """Return localized payslip data in English, Tamil, or Hindi for browser print-to-PDF."""
    slip = db.get(Payslip, payslip_id)
    if not slip or slip.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payslip not found")
    weaver = db.get(Weaver, slip.weaver_id)
    unit = db.scalar(select(UnitSettings).limit(1))

    resolved_lang: SlipLangCode = lang or (weaver.preferred_slip_lang if weaver else "en")  # type: ignore[assignment]
    if resolved_lang == "ta" and weaver and weaver.full_name_ta:
        loc_name = f"{weaver.full_name_ta} ({weaver.full_name})"
    elif resolved_lang == "hi" and weaver and weaver.full_name_hi:
        loc_name = f"{weaver.full_name_hi} ({weaver.full_name})"
    else:
        loc_name = weaver.full_name if weaver else f"Worker #{slip.weaver_id}"

    return PrintablePayslipResponse(
        payslip=_hydrate_payslip(slip, weaver),
        unit_name=unit.unit_name if unit else "LOOMOS Weaving Unit",
        unit_location=unit.location if unit else "",
        lang=resolved_lang,
        localized_weaver_name=loc_name,
        role_type=(weaver.role_type if weaver else "WEAVER"),  # type: ignore[arg-type]
        labels=get_payslip_translations(resolved_lang),
        printed_on=today_ist(),
    )
