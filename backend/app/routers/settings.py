"""Unit settings, editable DB-driven EB tariff plans/slabs, and stop reasons."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.audit import record_audit, snapshot_fields, soft_delete_record
from app.core.database import get_db
from app.core.security import get_current_user, require_owner
from app.models.core import EbTariffPlan, EbTariffSlab, StopReason, UnitSettings, User
from app.schemas.step1 import (
    EbTariffPlanCreate,
    EbTariffPlanResponse,
    SoftDeleteRequest,
    StopReasonCreate,
    StopReasonResponse,
    StopReasonUpdate,
    UnitSettingsResponse,
    UnitSettingsUpdateRequest,
)

router = APIRouter(prefix="/api/v1", tags=["settings"])


@router.get("/settings", response_model=UnitSettingsResponse)
def get_unit_settings(
    _user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UnitSettingsResponse:
    """Return active shed configuration."""
    row = db.scalar(select(UnitSettings).limit(1))
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setup not initialized")
    return UnitSettingsResponse.model_validate(row)


@router.patch("/settings", response_model=UnitSettingsResponse)
def update_unit_settings(
    payload: UnitSettingsUpdateRequest,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> UnitSettingsResponse:
    """Update shed settings with full audit logging."""
    row = db.scalar(select(UnitSettings).limit(1))
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setup not initialized")

    fields = [
        "unit_name",
        "location",
        "default_language",
        "shifts_per_day",
        "planned_shift_mins",
        "shift_cutoff_hour",
        "default_entry_mode",
        "sanctioned_kw",
        "active_tariff_plan_id",
    ]
    old_snap = snapshot_fields(row, fields)
    updates = payload.model_dump(exclude_unset=True)
    if "active_tariff_plan_id" in updates and updates["active_tariff_plan_id"] is not None:
        plan = db.get(EbTariffPlan, updates["active_tariff_plan_id"])
        if not plan or plan.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tariff plan not found")
    for key, val in updates.items():
        setattr(row, key, val.strip() if isinstance(val, str) else val)

    record_audit(
        db,
        entity_type="unit_settings",
        entity_id=row.id,
        action="UPDATE",
        changed_by=owner.id,
        old_values=old_snap,
        new_values=snapshot_fields(row, fields),
    )
    db.commit()
    db.refresh(row)
    return UnitSettingsResponse.model_validate(row)


@router.get("/eb-tariffs", response_model=list[EbTariffPlanResponse])
def list_eb_tariffs(
    include_deleted: bool = False,
    _owner: Annotated[User, Depends(require_owner)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> list[EbTariffPlanResponse]:
    """List database-driven electricity tariff plans and slabs."""
    stmt = select(EbTariffPlan).options(selectinload(EbTariffPlan.slabs)).order_by(EbTariffPlan.id.desc())
    if not include_deleted:
        stmt = stmt.where(EbTariffPlan.is_deleted.is_(False))
    plans = db.scalars(stmt).all()
    return [EbTariffPlanResponse.model_validate(p) for p in plans]


@router.post("/eb-tariffs", response_model=EbTariffPlanResponse, status_code=status.HTTP_201_CREATED)
def create_eb_tariff(
    payload: EbTariffPlanCreate,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> EbTariffPlanResponse:
    """Create a new custom or revised electricity tariff plan with unit slabs."""
    plan = EbTariffPlan(
        name=payload.name.strip(),
        billing_cycle_days=payload.billing_cycle_days,
        overhead_per_kw_paise=payload.overhead_per_kw_paise,
        fixed_charge_per_kw_month_paise=payload.fixed_charge_per_kw_month_paise,
        electricity_tax_bps=payload.electricity_tax_bps,
        fppca_paise_per_unit=payload.fppca_paise_per_unit,
        tax_on_gross=payload.tax_on_gross,
        effective_from=payload.effective_from,
        notes=payload.notes,
        created_by=owner.id,
    )
    plan.slabs = [
        EbTariffSlab(
            min_unit=s.min_unit,
            max_unit=s.max_unit,
            rate_paise_per_unit=s.rate_paise_per_unit,
        )
        for s in payload.slabs
    ]
    db.add(plan)
    db.flush()
    record_audit(
        db,
        entity_type="eb_tariff_plan",
        entity_id=plan.id,
        action="CREATE",
        changed_by=owner.id,
        new_values={
            **snapshot_fields(plan, ["name", "billing_cycle_days", "overhead_per_kw_paise", "effective_from"]),
            "slabs": [s.model_dump() for s in payload.slabs],
        },
    )
    db.commit()
    db.refresh(plan)
    return EbTariffPlanResponse.model_validate(plan)


@router.delete("/eb-tariffs/{plan_id}", response_model=EbTariffPlanResponse)
def soft_delete_eb_tariff(
    plan_id: int,
    payload: SoftDeleteRequest,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> EbTariffPlanResponse:
    """Soft-delete an unused EB tariff plan with audit logging."""
    plan = db.scalar(select(EbTariffPlan).options(selectinload(EbTariffPlan.slabs)).where(EbTariffPlan.id == plan_id))
    if not plan or plan.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tariff plan not found")

    unit = db.scalar(select(UnitSettings).limit(1))
    if unit and unit.active_tariff_plan_id == plan.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Switch the active tariff plan in Settings before archiving this plan",
        )

    soft_delete_record(
        db,
        obj=plan,
        entity_type="eb_tariff_plan",
        entity_id=plan.id,
        user_id=owner.id,
        reason=payload.reason.strip(),
        audit_fields=["name", "billing_cycle_days", "overhead_per_kw_paise"],
    )
    db.commit()
    db.refresh(plan)
    return EbTariffPlanResponse.model_validate(plan)


@router.get("/stop-reasons", response_model=list[StopReasonResponse])
def list_stop_reasons(
    active_only: bool = True,
    _user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> list[StopReasonResponse]:
    """List configurable stop reasons (including Power Cut flag)."""
    stmt = select(StopReason).order_by(StopReason.id)
    if active_only:
        stmt = stmt.where(StopReason.is_active.is_(True))
    rows = db.scalars(stmt).all()
    return [StopReasonResponse.model_validate(r) for r in rows]


@router.post("/stop-reasons", response_model=StopReasonResponse, status_code=status.HTTP_201_CREATED)
def create_stop_reason(
    payload: StopReasonCreate,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> StopReasonResponse:
    """Add a configurable stop reason."""
    if db.scalar(select(StopReason.id).where(StopReason.code == payload.code)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stop reason code already exists")
    sr = StopReason(**payload.model_dump(), created_by=owner.id)
    db.add(sr)
    db.flush()
    record_audit(
        db,
        entity_type="stop_reason",
        entity_id=sr.id,
        action="CREATE",
        changed_by=owner.id,
        new_values=snapshot_fields(sr, ["code", "label_en", "label_ta", "is_power_cut"]),
    )
    db.commit()
    db.refresh(sr)
    return StopReasonResponse.model_validate(sr)


@router.patch("/stop-reasons/{reason_id}", response_model=StopReasonResponse)
def update_stop_reason(
    reason_id: int,
    payload: StopReasonUpdate,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> StopReasonResponse:
    """Edit or soft-archive a stop reason."""
    sr = db.get(StopReason, reason_id)
    if not sr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stop reason not found")
    fields = ["label_en", "label_ta", "is_power_cut", "is_active"]
    old_snap = snapshot_fields(sr, fields)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(sr, k, v.strip() if isinstance(v, str) else v)
    record_audit(
        db,
        entity_type="stop_reason",
        entity_id=sr.id,
        action="UPDATE",
        changed_by=owner.id,
        old_values=old_snap,
        new_values=snapshot_fields(sr, fields),
    )
    db.commit()
    db.refresh(sr)
    return StopReasonResponse.model_validate(sr)
