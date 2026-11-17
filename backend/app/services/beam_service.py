"""Beam remaining length, loom loading state, and weft wastage reconciliation."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit, snapshot_fields
from app.models.core import (
    Alert,
    Beam,
    BeamLoading,
    FabricSort,
    Loom,
    ShiftEntry,
    Trader,
    WeftReceipt,
)


def compute_beams_response_list(db: Session, beam_ids: list[int] | None = None) -> list[dict]:
    """Compute live woven metres, remaining metres, active loom, and weft wastage per beam."""
    stmt = select(Beam).order_by(Beam.id.desc())
    if beam_ids is not None:
        if not beam_ids:
            return []
        stmt = stmt.where(Beam.id.in_(beam_ids))
    beams = db.scalars(stmt).all()
    if not beams:
        return []

    target_ids = [b.id for b in beams]
    traders = {t.id: t.company_name for t in db.scalars(select(Trader)).all()}
    sorts = {s.id: s for s in db.scalars(select(FabricSort)).all()}
    looms = {l.id: l.loom_number for l in db.scalars(select(Loom)).all()}

    active_loadings = db.scalars(
        select(BeamLoading).where(BeamLoading.beam_id.in_(target_ids), BeamLoading.unloaded_at.is_(None))
    ).all()
    loading_by_beam = {bl.beam_id: bl for bl in active_loadings}

    shift_totals: dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for row in db.execute(
        select(ShiftEntry.beam_id, ShiftEntry.net_metres).where(
            ShiftEntry.beam_id.in_(target_ids), ShiftEntry.is_deleted.is_(False)
        )
    ):
        if row[0] is not None:
            shift_totals[row[0]] += row[1]

    weft_totals: dict[int, Decimal] = defaultdict(lambda: Decimal("0.000"))
    for row in db.execute(
        select(WeftReceipt.beam_id, WeftReceipt.net_weight_kg).where(
            WeftReceipt.beam_id.in_(target_ids), WeftReceipt.is_deleted.is_(False)
        )
    ):
        if row[0] is not None:
            weft_totals[row[0]] += row[1]

    out: list[dict] = []
    for beam in beams:
        sort_obj: FabricSort | None = sorts.get(beam.sort_id)
        new_woven = shift_totals[beam.id]
        woven_m = (beam.opening_woven_m + new_woven).quantize(Decimal("0.01"))
        usable_total = max(Decimal("0.00"), (beam.warp_length_m - beam.expected_tail_waste_m).quantize(Decimal("0.01")))
        remaining_m = max(Decimal("0.00"), (usable_total - woven_m).quantize(Decimal("0.01")))
        progress_pct = float(min(Decimal("100"), (woven_m * Decimal(100) / usable_total))) if usable_total > 0 else 0.0

        weft_received = weft_totals[beam.id].quantize(Decimal("0.001"))
        weft_consumed = max(Decimal("0.000"), (weft_received - beam.returned_weft_kg).quantize(Decimal("0.001")))
        expected_per_100 = sort_obj.expected_weft_kg_per_100m if sort_obj else Decimal("0.000")
        allowed_pct = float(sort_obj.wastage_pct) if sort_obj else 2.5

        # Only evaluate wastage against metres tracked on LOOMOS when beam had pre-existing opening weave
        metres_for_weft = new_woven if beam.opening_woven_m > 0 else woven_m
        expected_weft = (metres_for_weft * expected_per_100 / Decimal(100)).quantize(Decimal("0.001"))

        actual_wastage_pct: float | None = None
        wastage_flagged = False
        if expected_weft > Decimal("0.000") and (beam.status == "COMPLETED" or beam.returned_weft_kg > 0):
            diff_kg = weft_consumed - expected_weft
            actual_wastage_pct = round(float(diff_kg / expected_weft * Decimal(100)), 2)
            wastage_flagged = actual_wastage_pct > allowed_pct
        elif expected_per_100 > Decimal("0.000") and usable_total > Decimal("0.00"):
            # Mid-beam overflow check: flag only if consumed already exceeds entire remaining usable beam allowance
            full_expected = ((usable_total - beam.opening_woven_m) * expected_per_100 / Decimal(100))
            if full_expected > Decimal("0.000"):
                limit_kg = full_expected * (Decimal(1) + Decimal(str(allowed_pct)) / Decimal(100))
                if weft_consumed > limit_kg:
                    wastage_flagged = True
                    actual_wastage_pct = round(float((weft_consumed - full_expected) / full_expected * Decimal(100)), 2)

        bl = loading_by_beam.get(beam.id)
        out.append(
            {
                "id": beam.id,
                "beam_no": beam.beam_no,
                "trader_id": beam.trader_id,
                "trader_name": traders.get(beam.trader_id, f"Trader #{beam.trader_id}"),
                "sort_id": beam.sort_id,
                "sort_name": sort_obj.sort_name if sort_obj else f"Sort #{beam.sort_id}",
                "received_date": beam.received_date,
                "warp_length_m": beam.warp_length_m,
                "opening_woven_m": beam.opening_woven_m,
                "expected_tail_waste_m": beam.expected_tail_waste_m,
                "returned_weft_kg": beam.returned_weft_kg,
                "actual_waste_m": beam.actual_waste_m,
                "due_date": beam.due_date,
                "expected_pieces": beam.expected_pieces,
                "status": beam.status,
                "active_loom_id": bl.loom_id if bl else None,
                "active_loom_number": looms.get(bl.loom_id) if bl else None,
                "woven_m": woven_m,
                "usable_total_m": usable_total,
                "remaining_m": remaining_m,
                "progress_pct": round(progress_pct, 1),
                "weft_received_kg": weft_received,
                "weft_consumed_kg": weft_consumed,
                "expected_weft_kg": expected_weft,
                "actual_wastage_pct": actual_wastage_pct,
                "allowed_wastage_pct": allowed_pct,
                "wastage_flagged": wastage_flagged,
            }
        )
    return out


def sync_weft_wastage_alert(db: Session, beam_id: int) -> None:
    """Create or clear an open WEFT_WASTAGE alert whenever wastage crosses allowed_pct."""
    rows = compute_beams_response_list(db, beam_ids=[beam_id])
    if not rows:
        return
    info = rows[0]
    if not info["wastage_flagged"]:
        return

    tag = f"Beam {info['beam_no']}:"
    existing = db.scalar(
        select(Alert).where(
            Alert.alert_type == "WEFT_WASTAGE",
            Alert.status == "OPEN",
            Alert.message.like(f"{tag}%"),
        )
    )
    msg = (
        f"{tag} weft wastage {info['actual_wastage_pct']}% exceeds sort limit {info['allowed_wastage_pct']}% "
        f"(consumed {info['weft_consumed_kg']} kg vs expected {info['expected_weft_kg']} kg)."
    )[:255]
    if existing:
        existing.message = msg
        existing.loom_id = info["active_loom_id"]
    else:
        db.add(
            Alert(
                alert_type="WEFT_WASTAGE",
                loom_id=info["active_loom_id"],
                severity="WARN",
                message=msg,
                status="OPEN",
            )
        )
    db.flush()
