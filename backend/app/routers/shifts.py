"""Daily shift production grid, smart prefill, worker attendance, and shed calendar."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit, snapshot_fields, soft_delete_record
from app.core.database import get_db
from app.core.security import get_current_user, require_owner
from app.models.core import (
    Beam,
    BeamLoading,
    FabricSort,
    Loom,
    ShedCalendar,
    ShiftEntry,
    UnitSettings,
    User,
    Weaver,
    WeaverAttendance,
)
from app.schemas.step1 import SoftDeleteRequest
from app.schemas.step2 import (
    AttendanceBatchRequest,
    AttendanceResponse,
    CalendarDayResponse,
    CalendarDayUpsert,
    ShiftBatchSaveRequest,
    ShiftEntryResponse,
    ShiftEntryUpdate,
    ShiftPrefillResponse,
)
from app.services.beam_service import compute_beams_response_list, sync_weft_wastage_alert

router = APIRouter(prefix="/api/v1", tags=["shifts"])


def _compute_net_metres(
    entry_mode: str,
    start_meter: Decimal | None,
    end_meter: Decimal | None,
    net_metres: Decimal | None,
    meter_reset: bool = False,
) -> Decimal:
    if entry_mode == "COUNTER":
        if start_meter is None or end_meter is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="COUNTER mode requires start_meter and end_meter",
            )
        if end_meter < start_meter:
            if not meter_reset:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="end_meter cannot be less than start_meter unless meter_reset is flagged",
                )
            if net_metres is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Provide explicit net_metres when meter_reset is true",
                )
            return net_metres
        return (end_meter - start_meter).quantize(Decimal("0.01"))

    if net_metres is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="DIRECT mode requires net_metres",
        )
    return net_metres.quantize(Decimal("0.01"))


def _hydrate_shift_rows(db: Session, entries: list[ShiftEntry]) -> list[ShiftEntryResponse]:
    looms = {l.id: l.loom_number for l in db.scalars(select(Loom)).all()}
    weavers = {w.id: w.full_name for w in db.scalars(select(Weaver)).all()}
    beams = {b.id: b.beam_no for b in db.scalars(select(Beam)).all()}
    out: list[ShiftEntryResponse] = []
    for e in entries:
        data = ShiftEntryResponse.model_validate(e)
        data.loom_number = looms.get(e.loom_id)
        data.weaver_name = weavers.get(e.weaver_id)
        data.beam_no = beams.get(e.beam_id) if e.beam_id else None
        out.append(data)
    return out


# ---------------------------------------------------------------------------
# Shed Calendar (Working Days & Holiday Overrides)
# ---------------------------------------------------------------------------
@router.get("/calendar", response_model=list[CalendarDayResponse])
def list_calendar_days(
    from_date: date | None = None,
    to_date: date | None = None,
    _user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> list[CalendarDayResponse]:
    stmt = select(ShedCalendar).order_by(ShedCalendar.calendar_date.desc())
    if from_date:
        stmt = stmt.where(ShedCalendar.calendar_date >= from_date)
    if to_date:
        stmt = stmt.where(ShedCalendar.calendar_date <= to_date)
    return [CalendarDayResponse.model_validate(c) for c in db.scalars(stmt).all()]


@router.put("/calendar/{calendar_date}", response_model=CalendarDayResponse)
def upsert_calendar_day(
    calendar_date: date,
    payload: CalendarDayUpsert,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CalendarDayResponse:
    row = db.scalar(select(ShedCalendar).where(ShedCalendar.calendar_date == calendar_date))
    if row:
        old = snapshot_fields(row, ["is_working_day", "planned_shifts", "note"])
        row.is_working_day = payload.is_working_day
        row.planned_shifts = payload.planned_shifts
        row.note = payload.note
        record_audit(
            db,
            entity_type="shed_calendar",
            entity_id=row.id,
            action="UPDATE",
            changed_by=user.id,
            old_values=old,
            new_values=snapshot_fields(row, ["is_working_day", "planned_shifts", "note"]),
        )
    else:
        row = ShedCalendar(
            calendar_date=calendar_date,
            is_working_day=payload.is_working_day,
            planned_shifts=payload.planned_shifts,
            note=payload.note,
            created_by=user.id,
        )
        db.add(row)
        db.flush()
        record_audit(
            db,
            entity_type="shed_calendar",
            entity_id=row.id,
            action="CREATE",
            changed_by=user.id,
            new_values=snapshot_fields(row, ["calendar_date", "is_working_day", "planned_shifts"]),
        )
    db.commit()
    db.refresh(row)
    return CalendarDayResponse.model_validate(row)


# ---------------------------------------------------------------------------
# Smart Shift Prefill & Shift Entry Grid
# ---------------------------------------------------------------------------
@router.get("/shifts/prefill", response_model=ShiftPrefillResponse)
def get_shift_prefill(
    entry_date: date | None = None,
    shift_no: int | None = Query(default=None, ge=1, le=3),
    _user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> ShiftPrefillResponse:
    """Return smart defaults per operational loom (active beam, carried-forward weaver & counter)."""
    settings = db.scalar(select(UnitSettings).limit(1))
    now_local = datetime.now()
    suggested_date = date.today()
    cutoff = settings.shift_cutoff_hour if settings else 18
    max_shifts = settings.shifts_per_day if settings else 2
    suggested_shift = 1 if now_local.hour < cutoff else min(2, max_shifts)

    target_date = entry_date or suggested_date
    target_shift = shift_no or suggested_shift
    if shift_no is None and target_shift == 2:
        has_shift2 = db.scalar(
            select(ShiftEntry.id)
            .where(
                ShiftEntry.entry_date == target_date,
                ShiftEntry.shift_no == 2,
                ShiftEntry.is_deleted.is_(False),
            )
            .limit(1)
        )
        has_shift1 = db.scalar(
            select(ShiftEntry.id)
            .where(
                ShiftEntry.entry_date == target_date,
                ShiftEntry.shift_no == 1,
                ShiftEntry.is_deleted.is_(False),
            )
            .limit(1)
        )
        if not has_shift2 and has_shift1:
            target_shift = 1

    looms = db.scalars(select(Loom).where(Loom.is_active.is_(True)).order_by(Loom.loom_number)).all()
    beam_infos = {b["id"]: b for b in compute_beams_response_list(db)}
    active_loadings = {
        bl.loom_id: bl.beam_id
        for bl in db.scalars(select(BeamLoading).where(BeamLoading.unloaded_at.is_(None))).all()
    }

    existing_rows = db.scalars(
        select(ShiftEntry).where(
            ShiftEntry.entry_date == target_date,
            ShiftEntry.shift_no == target_shift,
            ShiftEntry.is_deleted.is_(False),
        )
    ).all()
    hydrated_existing = _hydrate_shift_rows(db, existing_rows)
    existing_by_loom: dict[int, list[ShiftEntryResponse]] = {}
    for item in hydrated_existing:
        existing_by_loom.setdefault(item.loom_id, []).append(item)

    # Latest non-deleted shift per loom before or up to target_date for carry-forward
    recent_shifts = db.scalars(
        select(ShiftEntry)
        .where(ShiftEntry.is_deleted.is_(False))
        .order_by(ShiftEntry.entry_date.desc(), ShiftEntry.shift_no.desc(), ShiftEntry.id.desc())
    ).all()
    latest_by_loom: dict[int, ShiftEntry] = {}
    for sh in recent_shifts:
        if sh.loom_id not in latest_by_loom:
            latest_by_loom[sh.loom_id] = sh

    prefill_rows = []
    for l in looms:
        active_beam_id = active_loadings.get(l.id)
        b_info = beam_infos.get(active_beam_id) if active_beam_id else None
        last_sh = latest_by_loom.get(l.id)
        prefill_rows.append(
            {
                "loom_id": l.id,
                "loom_number": l.loom_number,
                "loom_type": l.loom_type,
                "rated_rpm": l.rated_rpm,
                "default_weaver_id": last_sh.weaver_id if last_sh else None,
                "active_beam_id": active_beam_id,
                "active_beam_no": b_info["beam_no"] if b_info else None,
                "active_sort_name": b_info["sort_name"] if b_info else None,
                "remaining_beam_m": b_info["remaining_m"] if b_info else None,
                "last_end_meter": last_sh.end_meter if last_sh else None,
                "existing_entries": existing_by_loom.get(l.id, []),
            }
        )

    return ShiftPrefillResponse(
        suggested_date=suggested_date,
        suggested_shift=suggested_shift,
        entry_date=target_date,
        shift_no=target_shift,
        shifts_per_day=max_shifts,
        planned_shift_mins=settings.planned_shift_mins if settings else 600,
        default_entry_mode=settings.default_entry_mode if settings else "DIRECT",  # type: ignore[arg-type]
        looms=prefill_rows,
    )


@router.get("/shifts", response_model=list[ShiftEntryResponse])
def list_shifts(
    from_date: date | None = None,
    to_date: date | None = None,
    loom_id: int | None = None,
    weaver_id: int | None = None,
    include_deleted: bool = False,
    limit: int = Query(default=200, ge=1, le=2000),
    _user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> list[ShiftEntryResponse]:
    stmt = select(ShiftEntry).order_by(ShiftEntry.entry_date.desc(), ShiftEntry.shift_no.desc(), ShiftEntry.loom_id)
    if not include_deleted:
        stmt = stmt.where(ShiftEntry.is_deleted.is_(False))
    if from_date:
        stmt = stmt.where(ShiftEntry.entry_date >= from_date)
    if to_date:
        stmt = stmt.where(ShiftEntry.entry_date <= to_date)
    if loom_id:
        stmt = stmt.where(ShiftEntry.loom_id == loom_id)
    if weaver_id:
        stmt = stmt.where(ShiftEntry.weaver_id == weaver_id)
    entries = db.scalars(stmt.limit(limit)).all()
    return _hydrate_shift_rows(db, entries)


@router.post("/shifts/batch", response_model=list[ShiftEntryResponse], status_code=status.HTTP_201_CREATED)
def save_shift_batch(
    payload: ShiftBatchSaveRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ShiftEntryResponse]:
    """Save or upsert an entire shift grid atomically with client_uuid idempotency and audit trail."""
    settings = db.scalar(select(UnitSettings).limit(1))
    default_planned = settings.planned_shift_mins if settings else 600

    saved_entries: list[ShiftEntry] = []
    touched_beams: set[int] = set()

    for r in payload.rows:
        net_m = _compute_net_metres(r.entry_mode, r.start_meter, r.end_meter, r.net_metres, r.meter_reset)
        planned = r.planned_mins if r.planned_mins is not None else default_planned

        # 1. Exact idempotent replay check on client_uuid
        by_uuid = db.scalar(select(ShiftEntry).where(ShiftEntry.client_uuid == r.client_uuid))
        if by_uuid and not by_uuid.is_deleted:
            old = snapshot_fields(
                by_uuid,
                ["weaver_id", "beam_id", "net_metres", "power_cut_mins", "downtime_mins", "defective_metres", "stop_reason_id"],
            )
            by_uuid.weaver_id = r.weaver_id
            by_uuid.beam_id = r.beam_id
            by_uuid.entry_mode = r.entry_mode
            by_uuid.start_meter = r.start_meter
            by_uuid.end_meter = r.end_meter
            by_uuid.net_metres = net_m
            by_uuid.planned_mins = planned
            by_uuid.power_cut_mins = r.power_cut_mins
            by_uuid.downtime_mins = r.downtime_mins
            by_uuid.defective_metres = r.defective_metres
            by_uuid.stop_reason_id = r.stop_reason_id
            by_uuid.notes = r.notes
            new_snap = snapshot_fields(
                by_uuid,
                ["weaver_id", "beam_id", "net_metres", "power_cut_mins", "downtime_mins", "defective_metres", "stop_reason_id"],
            )
            if old != new_snap:
                record_audit(
                    db,
                    entity_type="shift_entry",
                    entity_id=by_uuid.id,
                    action="UPDATE",
                    changed_by=user.id,
                    old_values=old,
                    new_values=new_snap,
                )
            saved_entries.append(by_uuid)
            if by_uuid.beam_id:
                touched_beams.add(by_uuid.beam_id)
            continue

        # 2. Check existing active slot for (loom, date, shift, beam) so grid re-saves update cleanly
        slot_stmt = select(ShiftEntry).where(
            ShiftEntry.loom_id == r.loom_id,
            ShiftEntry.entry_date == payload.entry_date,
            ShiftEntry.shift_no == payload.shift_no,
            ShiftEntry.is_deleted.is_(False),
        )
        slot_stmt = slot_stmt.where(ShiftEntry.beam_id == r.beam_id if r.beam_id is not None else ShiftEntry.beam_id.is_(None))
        existing_slot = db.scalar(slot_stmt)
        if existing_slot:
            old = snapshot_fields(
                existing_slot,
                ["weaver_id", "net_metres", "power_cut_mins", "downtime_mins", "defective_metres", "stop_reason_id"],
            )
            existing_slot.weaver_id = r.weaver_id
            existing_slot.entry_mode = r.entry_mode
            existing_slot.start_meter = r.start_meter
            existing_slot.end_meter = r.end_meter
            existing_slot.net_metres = net_m
            existing_slot.planned_mins = planned
            existing_slot.power_cut_mins = r.power_cut_mins
            existing_slot.downtime_mins = r.downtime_mins
            existing_slot.defective_metres = r.defective_metres
            existing_slot.stop_reason_id = r.stop_reason_id
            existing_slot.notes = r.notes
            new_snap = snapshot_fields(
                existing_slot,
                ["weaver_id", "net_metres", "power_cut_mins", "downtime_mins", "defective_metres", "stop_reason_id"],
            )
            if old != new_snap:
                record_audit(
                    db,
                    entity_type="shift_entry",
                    entity_id=existing_slot.id,
                    action="UPDATE",
                    changed_by=user.id,
                    old_values=old,
                    new_values=new_snap,
                )
            saved_entries.append(existing_slot)
            if existing_slot.beam_id:
                touched_beams.add(existing_slot.beam_id)
            continue

        entry = ShiftEntry(
            client_uuid=r.client_uuid,
            loom_id=r.loom_id,
            weaver_id=r.weaver_id,
            beam_id=r.beam_id,
            entry_date=payload.entry_date,
            shift_no=payload.shift_no,
            entry_mode=r.entry_mode,
            start_meter=r.start_meter,
            end_meter=r.end_meter,
            net_metres=net_m,
            planned_mins=planned,
            power_cut_mins=r.power_cut_mins,
            downtime_mins=r.downtime_mins,
            defective_metres=r.defective_metres,
            stop_reason_id=r.stop_reason_id,
            notes=r.notes,
            created_by=user.id,
        )
        db.add(entry)
        db.flush()
        record_audit(
            db,
            entity_type="shift_entry",
            entity_id=entry.id,
            action="CREATE",
            changed_by=user.id,
            new_values=snapshot_fields(entry, ["loom_id", "weaver_id", "beam_id", "entry_date", "shift_no", "net_metres"]),
        )
        saved_entries.append(entry)
        if entry.beam_id:
            touched_beams.add(entry.beam_id)

    for bid in touched_beams:
        sync_weft_wastage_alert(db, bid)

    db.commit()
    return _hydrate_shift_rows(db, saved_entries)


@router.patch("/shifts/{shift_id}", response_model=ShiftEntryResponse)
def update_shift_entry(
    shift_id: int,
    payload: ShiftEntryUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ShiftEntryResponse:
    entry = db.get(ShiftEntry, shift_id)
    if not entry or entry.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift entry not found")
    fields = [
        "weaver_id",
        "beam_id",
        "entry_mode",
        "start_meter",
        "end_meter",
        "net_metres",
        "planned_mins",
        "power_cut_mins",
        "downtime_mins",
        "defective_metres",
        "stop_reason_id",
        "notes",
    ]
    old = snapshot_fields(entry, fields)
    updates = payload.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(entry, k, v)
    if entry.entry_mode == "COUNTER" and entry.start_meter is not None and entry.end_meter is not None and entry.end_meter >= entry.start_meter:
        entry.net_metres = (entry.end_meter - entry.start_meter).quantize(Decimal("0.01"))
    record_audit(
        db,
        entity_type="shift_entry",
        entity_id=entry.id,
        action="UPDATE",
        changed_by=user.id,
        old_values=old,
        new_values=snapshot_fields(entry, fields),
    )
    if entry.beam_id:
        sync_weft_wastage_alert(db, entry.beam_id)
    db.commit()
    db.refresh(entry)
    return _hydrate_shift_rows(db, [entry])[0]


@router.delete("/shifts/{shift_id}", response_model=ShiftEntryResponse)
def soft_delete_shift_entry(
    shift_id: int,
    payload: SoftDeleteRequest,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> ShiftEntryResponse:
    entry = db.get(ShiftEntry, shift_id)
    if not entry or entry.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift entry not found")
    soft_delete_record(
        db,
        obj=entry,
        entity_type="shift_entry",
        entity_id=entry.id,
        user_id=owner.id,
        reason=payload.reason.strip(),
        audit_fields=["loom_id", "weaver_id", "entry_date", "shift_no", "net_metres"],
    )
    db.commit()
    db.refresh(entry)
    return _hydrate_shift_rows(db, [entry])[0]


# ---------------------------------------------------------------------------
# Worker Attendance (Helpers, Fitters, and Zero-Loom Shifts)
# ---------------------------------------------------------------------------
@router.get("/attendance", response_model=list[AttendanceResponse])
def list_attendance(
    from_date: date | None = None,
    to_date: date | None = None,
    _user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> list[AttendanceResponse]:
    stmt = select(WeaverAttendance).where(WeaverAttendance.is_deleted.is_(False)).order_by(WeaverAttendance.attendance_date.desc(), WeaverAttendance.shift_no.desc())
    if from_date:
        stmt = stmt.where(WeaverAttendance.attendance_date >= from_date)
    if to_date:
        stmt = stmt.where(WeaverAttendance.attendance_date <= to_date)
    rows = db.scalars(stmt).all()
    weavers = {w.id: w.full_name for w in db.scalars(select(Weaver)).all()}
    out = []
    for r in rows:
        item = AttendanceResponse.model_validate(r)
        item.weaver_name = weavers.get(r.weaver_id)
        out.append(item)
    return out


@router.post("/attendance/batch", response_model=list[AttendanceResponse], status_code=status.HTTP_201_CREATED)
def save_attendance_batch(
    payload: AttendanceBatchRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AttendanceResponse]:
    saved: list[WeaverAttendance] = []
    for item in payload.items:
        existing = db.scalar(
            select(WeaverAttendance).where(
                WeaverAttendance.weaver_id == item.weaver_id,
                WeaverAttendance.attendance_date == payload.attendance_date,
                WeaverAttendance.shift_no == payload.shift_no,
                WeaverAttendance.is_deleted.is_(False),
            )
        )
        if existing:
            old = snapshot_fields(existing, ["status", "note"])
            existing.status = item.status
            existing.note = item.note
            new_snap = snapshot_fields(existing, ["status", "note"])
            if old != new_snap:
                record_audit(
                    db,
                    entity_type="weaver_attendance",
                    entity_id=existing.id,
                    action="UPDATE",
                    changed_by=user.id,
                    old_values=old,
                    new_values=new_snap,
                )
            saved.append(existing)
        else:
            row = WeaverAttendance(
                weaver_id=item.weaver_id,
                attendance_date=payload.attendance_date,
                shift_no=payload.shift_no,
                status=item.status,
                note=item.note,
                created_by=user.id,
            )
            db.add(row)
            db.flush()
            record_audit(
                db,
                entity_type="weaver_attendance",
                entity_id=row.id,
                action="CREATE",
                changed_by=user.id,
                new_values=snapshot_fields(row, ["weaver_id", "attendance_date", "shift_no", "status"]),
            )
            saved.append(row)
    db.commit()
    weavers = {w.id: w.full_name for w in db.scalars(select(Weaver)).all()}
    out = []
    for r in saved:
        res = AttendanceResponse.model_validate(r)
        res.weaver_name = weavers.get(r.weaver_id)
        out.append(res)
    return out


@router.delete("/attendance/{attendance_id}", response_model=AttendanceResponse)
def soft_delete_attendance(
    attendance_id: int,
    payload: SoftDeleteRequest,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> AttendanceResponse:
    row = db.get(WeaverAttendance, attendance_id)
    if not row or row.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found")
    soft_delete_record(
        db,
        obj=row,
        entity_type="weaver_attendance",
        entity_id=row.id,
        user_id=owner.id,
        reason=payload.reason.strip(),
        audit_fields=["weaver_id", "attendance_date", "shift_no", "status"],
    )
    db.commit()
    db.refresh(row)
    return AttendanceResponse.model_validate(row)
