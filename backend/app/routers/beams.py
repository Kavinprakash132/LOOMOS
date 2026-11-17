"""Warp beam inventory, loom loading/unloading, and weft yarn wastage tracking."""

from __future__ import annotations

from datetime import datetime, timezone
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
    Trader,
    User,
    WeftReceipt,
)
from app.schemas.step1 import SoftDeleteRequest
from app.schemas.step2 import (
    BeamCreate,
    BeamLoadRequest,
    BeamResponse,
    BeamUnloadRequest,
    BeamUpdate,
    WeftReceiptCreate,
    WeftReceiptResponse,
)
from app.services.beam_service import compute_beams_response_list, sync_weft_wastage_alert

router = APIRouter(prefix="/api/v1", tags=["beams"])


def _get_beam_or_404(db: Session, beam_id: int) -> Beam:
    beam = db.get(Beam, beam_id)
    if not beam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beam not found")
    return beam


@router.get("/beams", response_model=list[BeamResponse])
def list_beams(
    status_filter: str | None = Query(default=None, alias="status"),
    _user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> list[BeamResponse]:
    """List warp beams with live woven metres, remaining metres, active loom, and weft wastage."""
    rows = compute_beams_response_list(db)
    if status_filter:
        rows = [r for r in rows if r["status"] == status_filter]
    return [BeamResponse.model_validate(r) for r in rows]


@router.post("/beams", response_model=BeamResponse, status_code=status.HTTP_201_CREATED)
def create_beam(
    payload: BeamCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BeamResponse:
    """Receive a new warp beam from a trader (optionally with pre-existing opening woven metres)."""
    beam_no = payload.beam_no.strip()
    if db.scalar(select(Beam.id).where(Beam.beam_no == beam_no)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Beam {beam_no} already exists")
    if not db.get(Trader, payload.trader_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trader not found")
    if not db.get(FabricSort, payload.sort_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fabric sort not found")

    beam = Beam(
        beam_no=beam_no,
        trader_id=payload.trader_id,
        sort_id=payload.sort_id,
        received_date=payload.received_date,
        warp_length_m=payload.warp_length_m,
        opening_woven_m=payload.opening_woven_m,
        expected_tail_waste_m=payload.expected_tail_waste_m,
        due_date=payload.due_date,
        expected_pieces=payload.expected_pieces,
        status="IN_STOCK",
        created_by=user.id,
    )
    db.add(beam)
    db.flush()
    record_audit(
        db,
        entity_type="beam",
        entity_id=beam.id,
        action="CREATE",
        changed_by=user.id,
        new_values=snapshot_fields(
            beam, ["beam_no", "trader_id", "sort_id", "warp_length_m", "opening_woven_m", "due_date"]
        ),
    )
    db.commit()
    return BeamResponse.model_validate(compute_beams_response_list(db, beam_ids=[beam.id])[0])


@router.patch("/beams/{beam_id}", response_model=BeamResponse)
def update_beam(
    beam_id: int,
    payload: BeamUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BeamResponse:
    beam = _get_beam_or_404(db, beam_id)
    fields = [
        "opening_woven_m",
        "expected_tail_waste_m",
        "returned_weft_kg",
        "actual_waste_m",
        "due_date",
        "expected_pieces",
    ]
    old_snap = snapshot_fields(beam, fields)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(beam, k, v)
    record_audit(
        db,
        entity_type="beam",
        entity_id=beam.id,
        action="UPDATE",
        changed_by=user.id,
        old_values=old_snap,
        new_values=snapshot_fields(beam, fields),
    )
    sync_weft_wastage_alert(db, beam.id)
    db.commit()
    return BeamResponse.model_validate(compute_beams_response_list(db, beam_ids=[beam.id])[0])


@router.post("/beams/{beam_id}/load", response_model=BeamResponse)
def load_beam_onto_loom(
    beam_id: int,
    payload: BeamLoadRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BeamResponse:
    """Mount an IN_STOCK beam onto an operational loom."""
    beam = _get_beam_or_404(db, beam_id)
    if beam.status == "COMPLETED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Completed beam cannot be reloaded")
    loom = db.get(Loom, payload.loom_id)
    if not loom or not loom.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loom not found or inactive")

    existing_loom_beam = db.scalar(
        select(BeamLoading).where(BeamLoading.loom_id == payload.loom_id, BeamLoading.unloaded_at.is_(None))
    )
    if existing_loom_beam:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Loom {loom.loom_number} already has an active beam loaded. Unload it first.",
        )

    existing_this_beam = db.scalar(
        select(BeamLoading).where(BeamLoading.beam_id == beam_id, BeamLoading.unloaded_at.is_(None))
    )
    if existing_this_beam:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This beam is already mounted on a loom")

    ts = payload.loaded_at or datetime.now(timezone.utc)
    loading = BeamLoading(loom_id=payload.loom_id, beam_id=beam_id, loaded_at=ts, created_by=user.id)
    beam.status = "RUNNING"
    db.add(loading)
    db.flush()
    record_audit(
        db,
        entity_type="beam_loading",
        entity_id=loading.id,
        action="CREATE",
        changed_by=user.id,
        new_values={"beam_id": beam_id, "loom_id": payload.loom_id, "loaded_at": ts.isoformat()},
    )
    db.commit()
    return BeamResponse.model_validate(compute_beams_response_list(db, beam_ids=[beam_id])[0])


@router.post("/beams/{beam_id}/unload", response_model=BeamResponse)
def unload_beam(
    beam_id: int,
    payload: BeamUnloadRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BeamResponse:
    """Unmount a beam from its loom, record returned leftover weft kg, and recheck wastage."""
    beam = _get_beam_or_404(db, beam_id)
    loading = db.scalar(
        select(BeamLoading).where(BeamLoading.beam_id == beam_id, BeamLoading.unloaded_at.is_(None))
    )
    if not loading:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Beam is not currently loaded on any loom")

    ts = payload.unloaded_at or datetime.now(timezone.utc)
    loading.unloaded_at = ts
    loading.unload_reason = payload.unload_reason

    old_snap = snapshot_fields(beam, ["status", "returned_weft_kg", "actual_waste_m"])
    if payload.returned_weft_kg is not None:
        beam.returned_weft_kg = payload.returned_weft_kg
    if payload.actual_waste_m is not None:
        beam.actual_waste_m = payload.actual_waste_m
    beam.status = "COMPLETED" if payload.unload_reason == "COMPLETED" else "IN_STOCK"

    record_audit(
        db,
        entity_type="beam",
        entity_id=beam.id,
        action="UPDATE",
        changed_by=user.id,
        old_values=old_snap,
        new_values={
            **snapshot_fields(beam, ["status", "returned_weft_kg", "actual_waste_m"]),
            "unload_reason": payload.unload_reason,
        },
        reason=f"Beam unloaded ({payload.unload_reason})",
    )
    sync_weft_wastage_alert(db, beam.id)
    db.commit()
    return BeamResponse.model_validate(compute_beams_response_list(db, beam_ids=[beam.id])[0])


# ---------------------------------------------------------------------------
# Weft Receipts
# ---------------------------------------------------------------------------
@router.get("/weft-receipts", response_model=list[WeftReceiptResponse])
def list_weft_receipts(
    beam_id: int | None = None,
    _user: Annotated[User, Depends(get_current_user)] = None,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = None,  # type: ignore[assignment]
) -> list[WeftReceiptResponse]:
    stmt = select(WeftReceipt).where(WeftReceipt.is_deleted.is_(False)).order_by(WeftReceipt.received_date.desc(), WeftReceipt.id.desc())
    if beam_id is not None:
        stmt = stmt.where(WeftReceipt.beam_id == beam_id)
    return [WeftReceiptResponse.model_validate(r) for r in db.scalars(stmt).all()]


@router.post("/weft-receipts", response_model=WeftReceiptResponse, status_code=status.HTTP_201_CREATED)
def create_weft_receipt(
    payload: WeftReceiptCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WeftReceiptResponse:
    if payload.beam_id is not None:
        beam = _get_beam_or_404(db, payload.beam_id)
        trader_id = payload.trader_id or beam.trader_id
        sort_id = payload.sort_id or beam.sort_id
    else:
        trader_id = payload.trader_id
        sort_id = payload.sort_id
        if trader_id and not db.get(Trader, trader_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trader not found")

    wr = WeftReceipt(
        beam_id=payload.beam_id,
        trader_id=trader_id,
        sort_id=sort_id,
        received_date=payload.received_date,
        bags=payload.bags,
        net_weight_kg=payload.net_weight_kg,
        note=payload.note,
        created_by=user.id,
    )
    db.add(wr)
    db.flush()
    record_audit(
        db,
        entity_type="weft_receipt",
        entity_id=wr.id,
        action="CREATE",
        changed_by=user.id,
        new_values=snapshot_fields(wr, ["beam_id", "trader_id", "bags", "net_weight_kg"]),
    )
    if wr.beam_id is not None:
        sync_weft_wastage_alert(db, wr.beam_id)
    db.commit()
    db.refresh(wr)
    return WeftReceiptResponse.model_validate(wr)


@router.delete("/weft-receipts/{receipt_id}", response_model=WeftReceiptResponse)
def soft_delete_weft_receipt(
    receipt_id: int,
    payload: SoftDeleteRequest,
    owner: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_db)],
) -> WeftReceiptResponse:
    wr = db.get(WeftReceipt, receipt_id)
    if not wr or wr.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Weft receipt not found")
    soft_delete_record(
        db,
        obj=wr,
        entity_type="weft_receipt",
        entity_id=wr.id,
        user_id=owner.id,
        reason=payload.reason.strip(),
        audit_fields=["beam_id", "bags", "net_weight_kg"],
    )
    db.commit()
    db.refresh(wr)
    return WeftReceiptResponse.model_validate(wr)
