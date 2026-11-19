"""Operational Utilization / Conditional OEE and Owner Financial Dashboard service."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import (
    Alert,
    Beam,
    BeamLoading,
    Delivery,
    DeliveryItem,
    EbBill,
    Expense,
    FabricSort,
    Inspection,
    Loom,
    Payslip,
    ShiftEntry,
    TraderPayment,
)


def _pct(num: Decimal | float, den: Decimal | float) -> float | None:
    d = float(den)
    if d <= 0:
        return None
    return round(float(num) * 100.0 / d, 2)


def compute_floor_dashboard(db: Session, *, period_start: date, period_end: date) -> dict:
    """Compute Availability, Performance (RPM+Pick), A*P Utilization, and conditional OEE."""
    today = date.today()
    looms = db.scalars(select(Loom).where(Loom.is_active.is_(True)).order_by(Loom.loom_number)).all()
    sorts = {s.id: s for s in db.scalars(select(FabricSort)).all()}
    beams = {b.id: b for b in db.scalars(select(Beam)).all()}
    active_loadings = {
        bl.loom_id: beams.get(bl.beam_id)
        for bl in db.scalars(select(BeamLoading).where(BeamLoading.unloaded_at.is_(None))).all()
    }

    shifts = db.scalars(
        select(ShiftEntry).where(
            ShiftEntry.entry_date >= period_start,
            ShiftEntry.entry_date <= period_end,
            ShiftEntry.is_deleted.is_(False),
        )
    ).all()

    today_shifts = db.scalars(
        select(ShiftEntry).where(ShiftEntry.entry_date == today, ShiftEntry.is_deleted.is_(False))
    ).all()
    today_metres = sum((s.net_metres for s in today_shifts), Decimal("0.00")).quantize(Decimal("0.01"))

    # Confirmed inspection defective metres in period that are NOT already linked into a ShiftEntry (avoid double-counting)
    conf_insp = db.scalars(
        select(Inspection).where(
            Inspection.review_status == "CONFIRMED_DEFECT",
            Inspection.defective_metres > 0,
            Inspection.shift_entry_id.is_(None),
        )
    ).all()
    insp_defect_by_loom: dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for ins in conf_insp:
        d_local = ins.inspected_at.date()
        if period_start <= d_local <= period_end and ins.loom_id is not None:
            insp_defect_by_loom[ins.loom_id] += ins.defective_metres

    by_loom_shifts: dict[int, list[ShiftEntry]] = defaultdict(list)
    for s in shifts:
        by_loom_shifts[s.loom_id].append(s)

    total_planned = 0
    total_operating = 0
    total_power_cut = 0
    total_downtime = 0
    total_metres = Decimal("0.00")
    total_metres_with_ideal = Decimal("0.00")
    total_ideal_metres = Decimal("0.00")
    total_defective = Decimal("0.00")

    loom_rows: list[dict] = []
    active_looms_in_period: set[int] = set()

    for l in looms:
        l_shifts = by_loom_shifts[l.id]
        if l_shifts:
            active_looms_in_period.add(l.id)

        l_planned = sum(s.planned_mins for s in l_shifts)
        l_pc = sum(s.power_cut_mins for s in l_shifts)
        l_dt = sum(s.downtime_mins for s in l_shifts)
        l_op = sum(max(0, s.planned_mins - s.power_cut_mins - s.downtime_mins) for s in l_shifts)
        l_metres = sum((s.net_metres for s in l_shifts), Decimal("0.00")).quantize(Decimal("0.01"))
        l_defect = (sum((s.defective_metres for s in l_shifts), Decimal("0.00")) + insp_defect_by_loom[l.id]).quantize(
            Decimal("0.01")
        )

        l_ideal = Decimal("0.00")
        l_metres_with_ideal = Decimal("0.00")
        last_sort_name: str | None = None
        mounted = active_loadings.get(l.id)
        if mounted and mounted.sort_id in sorts:
            last_sort_name = sorts[mounted.sort_id].sort_name

        for s in l_shifts:
            b = beams.get(s.beam_id) if s.beam_id else mounted
            srt = sorts.get(b.sort_id) if b and b.sort_id in sorts else None
            if srt:
                last_sort_name = srt.sort_name
            op_m = max(0, s.planned_mins - s.power_cut_mins - s.downtime_mins)
            if srt and srt.pick > 0 and op_m > 0:
                # Theoretical m/min = (RPM * 0.0254 m/in) / pick_per_inch
                ideal_m = (
                    Decimal(l.rated_rpm) * Decimal("0.0254") / Decimal(srt.pick) * Decimal(op_m)
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                l_ideal += ideal_m
                l_metres_with_ideal += s.net_metres

        avail = _pct(l_op, l_planned)
        perf = _pct(l_metres_with_ideal, l_ideal) if l_ideal > 0 else None
        util = round(avail * perf / 100.0, 2) if (avail is not None and perf is not None) else None

        qual: float | None = None
        oee: float | None = None
        if l_defect > 0 and l_metres > 0:
            good_m = max(Decimal("0.00"), l_metres - l_defect)
            qual = _pct(good_m, l_metres)
            if util is not None and qual is not None:
                oee = round(util * qual / 100.0, 2)

        total_planned += l_planned
        total_operating += l_op
        total_power_cut += l_pc
        total_downtime += l_dt
        total_metres += l_metres
        total_metres_with_ideal += l_metres_with_ideal
        total_ideal_metres += l_ideal
        total_defective += l_defect

        loom_rows.append(
            {
                "loom_id": l.id,
                "loom_number": l.loom_number,
                "loom_type": l.loom_type,
                "rated_rpm": l.rated_rpm,
                "sort_name": last_sort_name,
                "shifts_logged": len(l_shifts),
                "net_metres": l_metres,
                "ideal_metres": l_ideal if l_ideal > 0 else None,
                "planned_mins": l_planned,
                "operating_mins": l_op,
                "power_cut_mins": l_pc,
                "downtime_mins": l_dt,
                "confirmed_defective_metres": l_defect,
                "availability_pct": avail,
                "performance_pct": perf,
                "utilization_ap_pct": util,
                "quality_pct": qual,
                "full_oee_pct": oee,
            }
        )

    shed_avail = _pct(total_operating, total_planned)
    shed_perf = _pct(total_metres_with_ideal, total_ideal_metres) if total_ideal_metres > 0 else None
    shed_util = round(shed_avail * shed_perf / 100.0, 2) if (shed_avail is not None and shed_perf is not None) else None

    quality_recorded = total_defective > Decimal("0.00") and total_metres > Decimal("0.00")
    shed_qual: float | None = None
    shed_oee: float | None = None
    if quality_recorded:
        shed_qual = _pct(max(Decimal("0.00"), total_metres - total_defective), total_metres)
        if shed_util is not None and shed_qual is not None:
            shed_oee = round(shed_util * shed_qual / 100.0, 2)
        oee_note = "Shows combined loom running time, weaving speed, and cloth quality from logged defective metres."
    else:
        oee_note = (
            "Shows how long looms ran and how fast they wove compared to loom RPM. "
            "Cloth Quality % appears once damaged metres are logged in Daily Shift."
        )

    open_alerts = db.scalars(
        select(Alert).where(Alert.status == "OPEN").order_by(Alert.created_at.desc(), Alert.id.desc()).limit(25)
    ).all()
    running_beams_count = len([b for b in beams.values() if b.status == "RUNNING"])
    wastage_alerts_count = len([a for a in open_alerts if a.alert_type == "WEFT_WASTAGE"])

    return {
        "period_start": period_start,
        "period_end": period_end,
        "today_date": today,
        "today_metres": today_metres,
        "period_metres": total_metres.quantize(Decimal("0.01")),
        "active_looms_count": len(active_looms_in_period),
        "operational_looms_count": len([l for l in looms if l.status == "OPERATIONAL"]),
        "running_beams_count": running_beams_count,
        "weft_wastage_alerts_count": wastage_alerts_count,
        "total_planned_mins": total_planned,
        "total_operating_mins": total_operating,
        "total_power_cut_mins": total_power_cut,
        "total_downtime_mins": total_downtime,
        "total_ideal_metres": total_ideal_metres.quantize(Decimal("0.01")),
        "confirmed_defective_metres": total_defective.quantize(Decimal("0.01")),
        "availability_pct": shed_avail,
        "performance_pct": shed_perf,
        "utilization_ap_pct": shed_util,
        "quality_recorded": quality_recorded,
        "quality_pct": shed_qual,
        "full_oee_pct": shed_oee,
        "oee_note": oee_note,
        "open_alerts": open_alerts,
        "loom_breakdown": loom_rows,
    }


def compute_owner_financials(db: Session, *, period_start: date, period_end: date) -> dict[str, int]:
    """Compute Owner P&L over the chosen period plus overall Trader Receivables & Rate-Cut shortfall."""
    sorts = {s.id: s for s in db.scalars(select(FabricSort)).all()}
    deliveries = db.scalars(select(Delivery).where(Delivery.is_deleted.is_(False))).all()
    del_map = {d.id: d for d in deliveries}
    items = db.scalars(select(DeliveryItem).where(DeliveryItem.is_deleted.is_(False))).all()

    billed_period_paise = 0
    total_billed_all_paise = 0
    total_underpayment_all_paise = 0

    for it in items:
        d = del_map.get(it.delivery_id)
        if not d:
            continue
        amt = int((it.metres * Decimal(it.applied_rate_paise)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        total_billed_all_paise += amt
        if period_start <= d.delivery_date <= period_end:
            billed_period_paise += amt
        srt = sorts.get(it.sort_id) if it.sort_id else None
        if srt and it.applied_rate_paise < srt.agreed_rate_paise:
            total_underpayment_all_paise += int(
                (it.metres * Decimal(srt.agreed_rate_paise - it.applied_rate_paise)).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
            )

    payments = db.scalars(select(TraderPayment).where(TraderPayment.is_deleted.is_(False))).all()
    total_received_all_paise = sum(p.amount_paise + p.shortage_deduction_paise for p in payments)

    slips_period = db.scalars(
        select(Payslip).where(
            Payslip.is_deleted.is_(False),
            Payslip.period_end >= period_start,
            Payslip.period_start <= period_end,
        )
    ).all()
    wages_paise = sum(s.gross_paise for s in slips_period)

    eb_period = db.scalars(
        select(EbBill).where(
            EbBill.is_deleted.is_(False),
            EbBill.period_end >= period_start,
            EbBill.period_end <= period_end,
        )
    ).all()
    eb_paise = sum(b.net_bill_paise for b in eb_period)

    exp_period = db.scalars(
        select(Expense).where(
            Expense.is_deleted.is_(False),
            Expense.expense_date >= period_start,
            Expense.expense_date <= period_end,
        )
    ).all()
    expenses_paise = sum(e.amount_paise for e in exp_period)

    net_op = billed_period_paise - wages_paise - eb_paise - expenses_paise

    return {
        "billed_revenue_paise": billed_period_paise,
        "finalized_wages_paise": wages_paise,
        "eb_bills_paise": eb_paise,
        "expenses_paise": expenses_paise,
        "net_operating_paise": net_op,
        "total_receivable_paise": total_billed_all_paise - total_received_all_paise,
        "total_rate_underpayment_paise": total_underpayment_all_paise,
    }
