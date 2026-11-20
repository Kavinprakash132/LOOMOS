"""Master data CRUD (Looms, Weavers + Wage Rules, Traders, Fabric Sorts) and Audit Log."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.audit import record_audit, snapshot_fields, soft_delete_record
from app.core.config import today_ist
from app.core.database import get_db
from app.core.security import get_current_user, require_owner
from app.models.core import AuditLog, BeamLoading, FabricSort, Inspection, Loom, ShiftEntry, Trader, User, WageRule, Weaver
from app.schemas.step1 import (
    AuditLogResponse,
    FabricSortCreate,
    FabricSortResponse,
    FabricSortUpdate,
    LoomCreate,
    LoomGroupInput,
    LoomResponse,
    LoomUpdate,
    SoftDeleteRequest,
    TraderCreate,
    TraderResponse,
    TraderUpdate,
    WageRuleCreate,
    WageRuleResponse,
    WeaverCreate,
    WeaverResponse,
    WeaverUpdate,
)

router = APIRouter(prefix="/api/v1", tags=["masters"])


def _apply_audited_update(
    db: Session,
    *,
    obj: object,
    entity_type: str,
    entity_id: int,
    user_id: int,
    updates: dict,
    fields: list[str],
) -> None:
    """Shared update helper that persists changes and records old/new audit snapshots."""
    old_snap = snapshot_fields(obj, fields)
    for key, val in updates.items():
        setattr(obj, key, val.strip() if isinstance(val, str) else val)
    record_audit(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        action="UPDATE",
        changed_by=user_id,
        old_values=old_snap,
        new_values=snapshot_fields(obj, fields),
    )


# ---------------------------------------------------------------------------
# Looms (Dynamic N-loom management)
# ---------------------------------------------------------------------------
@router.get("/looms", response_model=list[LoomResponse])
def list_looms(
    active_only: bool = True,
    _user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> list[LoomResponse]:
    stmt = select(Loom).order_by(Loom.loom_number)
    if active_only:
        stmt = stmt.where(Loom.is_active.is_(True))
    return [LoomResponse.model_validate(x) for x in db.scalars(stmt).all()]


@router.post("/looms", response_model=LoomResponse, status_code=status.HTTP_201_CREATED)
def create_loom(
    payload: LoomCreate,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> LoomResponse:
    number = payload.loom_number.strip()
    if db.scalar(select(Loom.id).where(Loom.loom_number == number)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Loom {number} already exists")
    loom = Loom(**{**payload.model_dump(), "loom_number": number}, created_by=owner.id)
    db.add(loom)
    db.flush()
    record_audit(
        db,
        entity_type="loom",
        entity_id=loom.id,
        action="CREATE",
        changed_by=owner.id,
        new_values=snapshot_fields(loom, ["loom_number", "loom_type", "rated_rpm", "status"]),
    )
    db.commit()
    db.refresh(loom)
    return LoomResponse.model_validate(loom)


@router.post("/looms/bulk", response_model=list[LoomResponse], status_code=status.HTTP_201_CREATED)
def bulk_create_looms(
    group: LoomGroupInput,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> list[LoomResponse]:
    """Generate multiple looms at once (e.g., when expanding a shed)."""
    created: list[Loom] = []
    for offset in range(group.count):
        num = f"{group.prefix}{group.start_number + offset:02d}"
        if db.scalar(select(Loom.id).where(Loom.loom_number == num)):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Loom {num} already exists")
        loom = Loom(
            loom_number=num,
            loom_type=group.loom_type,
            make_model=group.make_model.strip(),
            rated_rpm=group.rated_rpm,
            reed_space_in=group.reed_space_in,
            status="OPERATIONAL",
            created_by=owner.id,
        )
        db.add(loom)
        created.append(loom)
    db.flush()
    for loom in created:
        record_audit(
            db,
            entity_type="loom",
            entity_id=loom.id,
            action="CREATE",
            changed_by=owner.id,
            new_values=snapshot_fields(loom, ["loom_number", "loom_type", "rated_rpm"]),
            reason="Bulk loom generation",
        )
    db.commit()
    for loom in created:
        db.refresh(loom)
    return [LoomResponse.model_validate(x) for x in created]


@router.patch("/looms/{loom_id}", response_model=LoomResponse)
def update_loom(
    loom_id: int,
    payload: LoomUpdate,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> LoomResponse:
    loom = db.get(Loom, loom_id)
    if not loom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loom not found")
    updates = payload.model_dump(exclude_unset=True)
    if "loom_number" in updates:
        existing = db.scalar(select(Loom.id).where(Loom.loom_number == updates["loom_number"].strip(), Loom.id != loom_id))
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Loom number already taken")
    _apply_audited_update(
        db,
        obj=loom,
        entity_type="loom",
        entity_id=loom.id,
        user_id=owner.id,
        updates=updates,
        fields=["loom_number", "loom_type", "make_model", "rated_rpm", "reed_space_in", "status", "is_active"],
    )
    db.commit()
    db.refresh(loom)
    return LoomResponse.model_validate(loom)


@router.delete("/looms/{loom_id}")
def delete_or_archive_loom(
    loom_id: int,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str | int]:
    """Delete an unused loom outright, or archive a loom that has historical logs."""
    loom = db.get(Loom, loom_id)
    if not loom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loom not found")

    has_shifts = db.scalar(select(ShiftEntry.id).where(ShiftEntry.loom_id == loom_id).limit(1)) is not None
    has_beams = db.scalar(select(BeamLoading.id).where(BeamLoading.loom_id == loom_id).limit(1)) is not None
    has_inspections = db.scalar(select(Inspection.id).where(Inspection.loom_id == loom_id).limit(1)) is not None

    if has_shifts or has_beams or has_inspections:
        old = snapshot_fields(loom, ["loom_number", "status", "is_active"])
        loom.is_active = False
        loom.status = "IDLE"
        record_audit(
            db,
            entity_type="loom",
            entity_id=loom.id,
            action="ARCHIVE",
            changed_by=owner.id,
            old_values=old,
            new_values=snapshot_fields(loom, ["loom_number", "status", "is_active"]),
            reason="Loom has historical records and was archived cleanly",
        )
        db.commit()
        return {
            "status": "archived",
            "id": loom_id,
            "message": f"{loom.loom_number} has production history so it was archived (hidden from active looms).",
        }

    old_snap = snapshot_fields(loom, ["loom_number", "loom_type", "rated_rpm", "status"])
    loom_num = loom.loom_number
    db.delete(loom)
    record_audit(
        db,
        entity_type="loom",
        entity_id=loom_id,
        action="DELETE",
        changed_by=owner.id,
        old_values=old_snap,
        reason="Unused loom deleted by Owner",
    )
    db.commit()
    return {"status": "deleted", "id": loom_id, "message": f"Loom {loom_num} deleted permanently."}


# ---------------------------------------------------------------------------
# Weavers, Helpers & Dated Wage Rules
# ---------------------------------------------------------------------------
@router.get("/weavers", response_model=list[WeaverResponse])
def list_weavers(
    active_only: bool = True,
    user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> list[WeaverResponse]:
    stmt = select(Weaver).options(selectinload(Weaver.wage_rules)).order_by(Weaver.full_name)
    if active_only:
        stmt = stmt.where(Weaver.is_active.is_(True))
    weavers = db.scalars(stmt).all()
    is_owner = user.role == "OWNER"
    out: list[WeaverResponse] = []
    for w in weavers:
        resp = WeaverResponse.model_validate(w)
        if is_owner:
            active_rules = [r for r in w.wage_rules if not r.is_deleted]
            resp.wage_rules = [WageRuleResponse.model_validate(r) for r in active_rules]
        else:
            # Supervisors only need worker names/roles for shift entry; never expose private salaries
            resp.wage_rules = []
        out.append(resp)
    return out


@router.post("/weavers", response_model=WeaverResponse, status_code=status.HTTP_201_CREATED)
def create_weaver(
    payload: WeaverCreate,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> WeaverResponse:
    weaver = Weaver(
        full_name=payload.full_name.strip(),
        full_name_ta=payload.full_name_ta.strip() if payload.full_name_ta else None,
        full_name_hi=payload.full_name_hi.strip() if payload.full_name_hi else None,
        preferred_slip_lang=payload.preferred_slip_lang,
        role_type=payload.role_type,
        phone=payload.phone.strip(),
        created_by=owner.id,
    )
    db.add(weaver)
    db.flush()
    eff_from = payload.effective_from or today_ist()
    rule = WageRule(
        weaver_id=weaver.id,
        wage_mode=payload.wage_mode,
        rate_paise=payload.rate_paise,
        effective_from=eff_from,
        created_by=owner.id,
    )
    db.add(rule)
    db.flush()
    record_audit(
        db,
        entity_type="weaver",
        entity_id=weaver.id,
        action="CREATE",
        changed_by=owner.id,
        new_values={
            **snapshot_fields(weaver, ["full_name", "role_type"]),
            "wage_mode": rule.wage_mode,
            "rate_paise": rule.rate_paise,
        },
    )
    db.commit()
    db.refresh(weaver)
    return WeaverResponse.model_validate(weaver)


@router.patch("/weavers/{weaver_id}", response_model=WeaverResponse)
def update_weaver(
    weaver_id: int,
    payload: WeaverUpdate,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> WeaverResponse:
    weaver = db.scalar(select(Weaver).options(selectinload(Weaver.wage_rules)).where(Weaver.id == weaver_id))
    if not weaver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weaver not found")
    _apply_audited_update(
        db,
        obj=weaver,
        entity_type="weaver",
        entity_id=weaver.id,
        user_id=owner.id,
        updates=payload.model_dump(exclude_unset=True),
        fields=["full_name", "full_name_ta", "full_name_hi", "preferred_slip_lang", "role_type", "phone", "is_active"],
    )
    db.commit()
    db.refresh(weaver)
    resp = WeaverResponse.model_validate(weaver)
    resp.wage_rules = [WageRuleResponse.model_validate(r) for r in weaver.wage_rules if not r.is_deleted]
    return resp


@router.post("/weavers/{weaver_id}/wage-rules", response_model=WageRuleResponse, status_code=status.HTTP_201_CREATED)
def add_wage_rule(
    weaver_id: int,
    payload: WageRuleCreate,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> WageRuleResponse:
    """Create a new effective-dated wage rule and close prior open rule without altering history."""
    weaver = db.get(Weaver, weaver_id)
    if not weaver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weaver not found")

    open_rules = db.scalars(
        select(WageRule).where(
            WageRule.weaver_id == weaver_id,
            WageRule.is_deleted.is_(False),
            WageRule.effective_to.is_(None),
        )
    ).all()
    for prev in open_rules:
        if payload.effective_from <= prev.effective_from:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"New effective_from must be after existing rule start ({prev.effective_from})",
            )
        old_prev = snapshot_fields(prev, ["wage_mode", "rate_paise", "effective_from", "effective_to"])
        prev.effective_to = payload.effective_from - timedelta(days=1)
        record_audit(
            db,
            entity_type="wage_rule",
            entity_id=prev.id,
            action="UPDATE",
            changed_by=owner.id,
            old_values=old_prev,
            new_values=snapshot_fields(prev, ["wage_mode", "rate_paise", "effective_from", "effective_to"]),
            reason="Superseded by newer wage rule",
        )

    rule = WageRule(
        weaver_id=weaver_id,
        wage_mode=payload.wage_mode,
        rate_paise=payload.rate_paise,
        effective_from=payload.effective_from,
        created_by=owner.id,
    )
    db.add(rule)
    db.flush()
    record_audit(
        db,
        entity_type="wage_rule",
        entity_id=rule.id,
        action="CREATE",
        changed_by=owner.id,
        new_values=snapshot_fields(rule, ["weaver_id", "wage_mode", "rate_paise", "effective_from"]),
    )
    db.commit()
    db.refresh(rule)
    return WageRuleResponse.model_validate(rule)


@router.delete("/wage-rules/{rule_id}", response_model=WageRuleResponse)
def soft_delete_wage_rule(
    rule_id: int,
    payload: SoftDeleteRequest,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> WageRuleResponse:
    """Soft-delete a wage rule with mandatory reason and immutable audit entry."""
    rule = db.get(WageRule, rule_id)
    if not rule or rule.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wage rule not found")
    soft_delete_record(
        db,
        obj=rule,
        entity_type="wage_rule",
        entity_id=rule.id,
        user_id=owner.id,
        reason=payload.reason.strip(),
        audit_fields=["weaver_id", "wage_mode", "rate_paise", "effective_from", "effective_to"],
    )
    db.commit()
    db.refresh(rule)
    return WageRuleResponse.model_validate(rule)


# ---------------------------------------------------------------------------
# Traders (Read by Owner/Supervisor for Beam form; Owner-only for writes)
# ---------------------------------------------------------------------------
@router.get("/traders", response_model=list[TraderResponse])
def list_traders(
    active_only: bool = True,
    _user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> list[TraderResponse]:
    stmt = select(Trader).order_by(Trader.company_name)
    if active_only:
        stmt = stmt.where(Trader.is_active.is_(True))
    return [TraderResponse.model_validate(x) for x in db.scalars(stmt).all()]


@router.post("/traders", response_model=TraderResponse, status_code=status.HTTP_201_CREATED)
def create_trader(
    payload: TraderCreate,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> TraderResponse:
    trader = Trader(
        company_name=payload.company_name.strip(),
        contact_name=payload.contact_name.strip(),
        phone=payload.phone.strip(),
        created_by=owner.id,
    )
    db.add(trader)
    db.flush()
    record_audit(
        db,
        entity_type="trader",
        entity_id=trader.id,
        action="CREATE",
        changed_by=owner.id,
        new_values=snapshot_fields(trader, ["company_name", "contact_name", "phone"]),
    )
    db.commit()
    db.refresh(trader)
    return TraderResponse.model_validate(trader)


@router.patch("/traders/{trader_id}", response_model=TraderResponse)
def update_trader(
    trader_id: int,
    payload: TraderUpdate,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> TraderResponse:
    trader = db.get(Trader, trader_id)
    if not trader:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trader not found")
    _apply_audited_update(
        db,
        obj=trader,
        entity_type="trader",
        entity_id=trader.id,
        user_id=owner.id,
        updates=payload.model_dump(exclude_unset=True),
        fields=["company_name", "contact_name", "phone", "is_active"],
    )
    db.commit()
    db.refresh(trader)
    return TraderResponse.model_validate(trader)


# ---------------------------------------------------------------------------
# Fabric Sorts (Job-work rate & expected weft kg/100m audited on every edit)
# ---------------------------------------------------------------------------
@router.get("/fabric-sorts", response_model=list[FabricSortResponse])
def list_fabric_sorts(
    active_only: bool = True,
    _user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> list[FabricSortResponse]:
    stmt = select(FabricSort).order_by(FabricSort.sort_name)
    if active_only:
        stmt = stmt.where(FabricSort.is_active.is_(True))
    return [FabricSortResponse.model_validate(x) for x in db.scalars(stmt).all()]


@router.post("/fabric-sorts", response_model=FabricSortResponse, status_code=status.HTTP_201_CREATED)
def create_fabric_sort(
    payload: FabricSortCreate,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> FabricSortResponse:
    name = payload.sort_name.strip()
    if db.scalar(select(FabricSort.id).where(FabricSort.sort_name == name)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Fabric sort name already exists")
    sort_obj = FabricSort(
        **{
            **payload.model_dump(),
            "sort_name": name,
            "warp_count": payload.warp_count.strip(),
            "weft_count": payload.weft_count.strip(),
        },
        created_by=owner.id,
    )
    db.add(sort_obj)
    db.flush()
    record_audit(
        db,
        entity_type="fabric_sort",
        entity_id=sort_obj.id,
        action="CREATE",
        changed_by=owner.id,
        new_values=snapshot_fields(
            sort_obj, ["sort_name", "agreed_rate_paise", "expected_weft_kg_per_100m", "wastage_pct"]
        ),
    )
    db.commit()
    db.refresh(sort_obj)
    return FabricSortResponse.model_validate(sort_obj)


@router.patch("/fabric-sorts/{sort_id}", response_model=FabricSortResponse)
def update_fabric_sort(
    sort_id: int,
    payload: FabricSortUpdate,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> FabricSortResponse:
    sort_obj = db.get(FabricSort, sort_id)
    if not sort_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fabric sort not found")
    updates = payload.model_dump(exclude_unset=True)
    if "sort_name" in updates and updates["sort_name"] is not None:
        dup = db.scalar(
            select(FabricSort.id).where(FabricSort.sort_name == updates["sort_name"].strip(), FabricSort.id != sort_id)
        )
        if dup:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Fabric sort name already exists")
    _apply_audited_update(
        db,
        obj=sort_obj,
        entity_type="fabric_sort",
        entity_id=sort_obj.id,
        user_id=owner.id,
        updates=updates,
        fields=[
            "sort_name",
            "warp_count",
            "weft_count",
            "reed",
            "pick",
            "width_in",
            "agreed_rate_paise",
            "expected_weft_kg_per_100m",
            "wastage_pct",
            "is_active",
        ],
    )
    db.commit()
    db.refresh(sort_obj)
    return FabricSortResponse.model_validate(sort_obj)


# ---------------------------------------------------------------------------
# Immutable Audit Trail (Owner Only)
# ---------------------------------------------------------------------------
@router.get("/audit-logs", response_model=list[AuditLogResponse])
def list_audit_logs(
    entity_type: str | None = None,
    action: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    _owner: Annotated[User, Depends(require_owner)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> list[AuditLogResponse]:
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    return [AuditLogResponse.model_validate(x) for x in db.scalars(stmt).all()]
