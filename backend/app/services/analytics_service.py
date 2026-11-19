"""Phase 3–5 Backend Analytics, Beam ETA, EB Predictor, Anomaly Detection, Forecasts, XLSX & Expansion Simulator."""

from __future__ import annotations

import io
import math
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from statistics import median
from typing import Any

import openpyxl
from openpyxl.styles import Font, PatternFill
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.core import (
    Beam,
    BeamLoading,
    Delivery,
    DeliveryItem,
    EbBill,
    EbReading,
    EbTariffPlan,
    Expense,
    FabricSort,
    Loom,
    Payslip,
    ShedCalendar,
    ShiftEntry,
    Trader,
    TraderPayment,
    UnitSettings,
    Weaver,
)
from app.services.beam_service import compute_beams_response_list
from app.services.dashboard_service import compute_floor_dashboard, compute_owner_financials
from app.services.eb_calculator import calculate_bill_breakdown_paise, calculate_slab_breakdown_rows


def _quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    pos = (len(sorted_vals) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_vals[lo])
    frac = pos - lo
    return float(sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac)


def _advance_working_days(start: date, work_days: int, off_dates: set[date]) -> date:
    """Step forward `work_days` non-holiday calendar days from start."""
    cur = start
    remaining = max(1, work_days)
    safety = 0
    while remaining > 0 and safety < 730:
        cur = cur + timedelta(days=1)
        safety += 1
        if cur not in off_dates:
            remaining -= 1
    return cur


def _hours_str(total_mins: int) -> str:
    safe = max(0, int(total_mins))
    return f"{safe // 60}.{safe % 60:02d}"


def compute_beam_etas(db: Session) -> list[dict[str, Any]]:
    """Compute remaining warp finish ETA (P50 median, P75 optimistic, P25 conservative) skipping holidays."""
    beams = [b for b in compute_beams_response_list(db) if b["status"] == "RUNNING"]
    if not beams:
        return []

    today = date.today()
    since = today - timedelta(days=14)
    rows = db.execute(
        select(ShiftEntry.loom_id, ShiftEntry.entry_date, ShiftEntry.net_metres).where(
            ShiftEntry.is_deleted.is_(False),
            ShiftEntry.entry_date >= since,
            ShiftEntry.entry_date <= today,
            ShiftEntry.net_metres > 0,
        )
    ).all()

    daily_by_loom: dict[int, dict[date, float]] = defaultdict(lambda: defaultdict(float))
    for loom_id, e_date, net_m in rows:
        daily_by_loom[loom_id][e_date] += float(net_m)

    off_dates = {
        c.calendar_date
        for c in db.scalars(
            select(ShedCalendar).where(ShedCalendar.calendar_date >= today, ShedCalendar.is_working_day.is_(False))
        ).all()
    }

    out: list[dict[str, Any]] = []
    for b in beams:
        rem_m = float(b["remaining_m"])
        l_id = b["active_loom_id"]
        daily_vals = sorted(daily_by_loom.get(l_id, {}).values()) if l_id else []
        if len(daily_vals) >= 2:
            p50 = round(float(median(daily_vals)), 2)
            p75 = round(_quantile(daily_vals, 0.75), 2)
            p25 = round(max(10.0, _quantile(daily_vals, 0.25)), 2)
        elif len(daily_vals) == 1:
            p50 = round(max(10.0, daily_vals[0]), 2)
            p75 = round(p50 * 1.15, 2)
            p25 = round(max(10.0, p50 * 0.85), 2)
        else:
            p50, p75, p25 = 50.0, 56.0, 42.0

        days_p50 = max(1, math.ceil(rem_m / max(1.0, p50)))
        days_p75 = max(1, math.ceil(rem_m / max(1.0, p75)))
        days_p25 = max(1, math.ceil(rem_m / max(1.0, p25)))

        eta_p50 = _advance_working_days(today, days_p50, off_dates)
        eta_p75 = _advance_working_days(today, days_p75, off_dates)
        eta_p25 = _advance_working_days(today, days_p25, off_dates)

        due = b["due_date"]
        days_var = (due - eta_p50).days if due else None
        on_track = (eta_p50 <= due) if due else True

        out.append(
            {
                "beam_id": b["id"],
                "beam_no": b["beam_no"],
                "sort_name": b["sort_name"],
                "loom_number": b["active_loom_number"] or "-",
                "remaining_m": round(rem_m, 2),
                "p50_daily_m": p50,
                "p75_daily_m": p75,
                "p25_daily_m": p25,
                "working_days_left_p50": days_p50,
                "eta_date_p50": eta_p50.isoformat(),
                "eta_date_p75": eta_p75.isoformat(),
                "eta_date_p25": eta_p25.isoformat(),
                "due_date": due.isoformat() if due else None,
                "days_variance": days_var,
                "on_track": on_track,
            }
        )
    return out


def compute_eb_prediction_and_outage_loss(db: Session) -> dict[str, Any]:
    """Predict current bi-monthly EB bill components and quantify 30-day stoppage/outage losses."""
    settings = db.scalar(select(UnitSettings).limit(1))
    sanctioned_kw = float(settings.sanctioned_kw) if settings else 10.0

    plan: EbTariffPlan | None = None
    if settings and settings.active_tariff_plan_id:
        plan = db.scalar(
            select(EbTariffPlan)
            .options(selectinload(EbTariffPlan.slabs))
            .where(EbTariffPlan.id == settings.active_tariff_plan_id, EbTariffPlan.is_deleted.is_(False))
        )
    if not plan:
        plan = db.scalar(
            select(EbTariffPlan)
            .options(selectinload(EbTariffPlan.slabs))
            .where(EbTariffPlan.is_deleted.is_(False))
            .order_by(EbTariffPlan.id.desc())
            .limit(1)
        )

    cycle_days = plan.billing_cycle_days if plan else 60
    bills = db.scalars(
        select(EbBill).where(EbBill.is_deleted.is_(False)).order_by(EbBill.period_end.desc()).limit(3)
    ).all()

    if bills:
        per_bill_rates = []
        for b in bills:
            bd = max(1, (b.period_end - b.period_start).days + 1)
            per_bill_rates.append(float(b.units_consumed) / bd)
        avg_daily_kwh = sum(per_bill_rates) / len(per_bill_rates)
        projected_kwh = round(avg_daily_kwh * cycle_days, 1)
        basis_note = f"Based on last {len(bills)} EB bill cycle(s) (~{avg_daily_kwh:.1f} kWh/day × {cycle_days} days)"
    else:
        readings = db.scalars(
            select(EbReading).where(EbReading.is_deleted.is_(False)).order_by(EbReading.reading_date.desc()).limit(2)
        ).all()
        if len(readings) == 2 and (readings[0].reading_date - readings[1].reading_date).days > 0:
            days_diff = (readings[0].reading_date - readings[1].reading_date).days
            daily_kwh = max(0.0, float(readings[0].kwh_total - readings[1].kwh_total) / days_diff)
            projected_kwh = round(daily_kwh * cycle_days, 1)
            basis_note = f"Based on last 2 meter snapshots ({daily_kwh:.1f} kWh/day)"
        else:
            op_looms = len(db.scalars(select(Loom).where(Loom.is_active.is_(True), Loom.status == "OPERATIONAL")).all()) or 5
            projected_kwh = round(op_looms * 6.5 * cycle_days, 1)
            basis_note = f"Estimated for {op_looms} operational shuttle looms (~6.5 kWh/loom/day)"

    if plan:
        bd_paise = calculate_bill_breakdown_paise(
            projected_kwh, plan, sanctioned_kw=sanctioned_kw, billing_days=cycle_days
        )
        tariff_name = plan.name
    else:
        bd_paise = {
            "energy_paise": 0,
            "fixed_paise": 0,
            "tax_paise": 0,
            "fppca_paise": 0,
            "overhead_paise": 0,
            "net_bill_paise": 0,
        }
        tariff_name = "No active EB plan"

    # Quantify 30-day stoppage / outage loss
    today = date.today()
    since30 = today - timedelta(days=29)
    shifts = db.scalars(
        select(ShiftEntry).where(
            ShiftEntry.is_deleted.is_(False),
            ShiftEntry.entry_date >= since30,
            ShiftEntry.entry_date <= today,
        )
    ).all()

    stopped_mins = sum((s.power_cut_mins + s.downtime_mins) for s in shifts)
    total_metres = sum(float(s.net_metres) for s in shifts)
    operating_mins = sum(max(0, s.planned_mins - s.power_cut_mins - s.downtime_mins) for s in shifts)
    metres_per_min = (total_metres / operating_mins) if operating_mins > 0 else 0.045
    lost_metres = round(stopped_mins * metres_per_min, 2)

    sorts = db.scalars(select(FabricSort).where(FabricSort.is_active.is_(True))).all()
    avg_rate_paise = int(round(sum(s.agreed_rate_paise for s in sorts) / len(sorts))) if sorts else 600
    lost_rev_paise = int(round(lost_metres * avg_rate_paise))

    return {
        "tariff_name": tariff_name,
        "sanctioned_kw": sanctioned_kw,
        "billing_cycle_days": cycle_days,
        "projected_units_kwh": projected_kwh,
        "energy_paise": bd_paise["energy_paise"],
        "fixed_paise": bd_paise["fixed_paise"],
        "tax_paise": bd_paise["tax_paise"],
        "fppca_paise": bd_paise["fppca_paise"],
        "projected_net_bill_paise": bd_paise["net_bill_paise"],
        "slab_note": basis_note,
        "outage_30d_stopped_mins": stopped_mins,
        "outage_30d_stopped_hrs": _hours_str(stopped_mins),
        "outage_30d_lost_metres": lost_metres,
        "outage_30d_lost_revenue_paise": lost_rev_paise,
    }


def _get_active_tariff_and_kw(db: Session) -> tuple[EbTariffPlan | None, float]:
    settings = db.scalar(select(UnitSettings).limit(1))
    sanctioned_kw = float(settings.sanctioned_kw) if (settings and settings.sanctioned_kw) else 10.0
    plan = None
    if settings and settings.active_tariff_plan_id:
        plan = db.scalar(
            select(EbTariffPlan)
            .options(selectinload(EbTariffPlan.slabs))
            .where(EbTariffPlan.id == settings.active_tariff_plan_id, EbTariffPlan.is_deleted.is_(False))
        )
    if not plan:
        plan = db.scalar(
            select(EbTariffPlan)
            .options(selectinload(EbTariffPlan.slabs))
            .where(EbTariffPlan.is_deleted.is_(False))
            .order_by(EbTariffPlan.id.desc())
            .limit(1)
        )
    return plan, sanctioned_kw


def compute_eb_vs_metres_efficiency(db: Session) -> dict[str, Any]:
    """Compare each EB billing cycle against cloth metres produced (ShiftEntry or Delivery fallback).

    Computes kWh/metre, metres/kWh, EB cost/metre, detects meter under-reading or power-spike
    anomalies against the shed's own median baseline, and fits a metre-based EB predictor.
    """
    plan, sanctioned_kw = _get_active_tariff_and_kw(db)
    cycle_days = plan.billing_cycle_days if plan else 60
    bills = db.scalars(
        select(EbBill).where(EbBill.is_deleted.is_(False)).order_by(EbBill.period_end.desc())
    ).all()

    all_shifts = db.scalars(select(ShiftEntry).where(ShiftEntry.is_deleted.is_(False))).all()
    all_deliveries = db.scalars(select(Delivery).where(Delivery.is_deleted.is_(False))).all()

    raw_rows: list[dict[str, Any]] = []
    for b in bills:
        days = max(1, (b.period_end - b.period_start).days)
        units = float(b.units_consumed)
        shift_m = sum(
            float(s.net_metres)
            for s in all_shifts
            if b.period_start < s.entry_date <= b.period_end
        )
        del_m = sum(
            float(d.total_metres)
            for d in all_deliveries
            if b.period_start < d.delivery_date <= b.period_end
        )
        # Prefer logged daily shifts when substantial; fall back to deliveries for imported historical periods
        if shift_m > 0 and (del_m == 0 or shift_m >= 0.4 * del_m):
            metres = round(shift_m, 2)
            source = "SHIFTS"
        elif del_m > 0:
            metres = round(del_m, 2)
            source = "DELIVERIES"
        else:
            metres = 0.0
            source = "NONE"

        kwh_per_m = round(units / metres, 4) if metres > 0 and units > 0 else None
        m_per_kwh = round(metres / units, 2) if metres > 0 and units > 0 else None
        eb_paise_per_m = int(round(b.net_bill_paise / metres)) if metres > 0 else None

        raw_rows.append(
            {
                "bill_id": b.id,
                "period_start": b.period_start.isoformat(),
                "period_end": b.period_end.isoformat(),
                "days": days,
                "units_kwh": round(units, 2),
                "net_bill_paise": b.net_bill_paise,
                "metres_produced": metres,
                "metres_source": source,
                "kwh_per_metre": kwh_per_m,
                "metres_per_kwh": m_per_kwh,
                "eb_paise_per_metre": eb_paise_per_m,
                "status_flag": "NO_METRES",
                "status_note": "No shift or delivery metres logged in this EB cycle.",
            }
        )

    valid_ratios = [r["kwh_per_metre"] for r in raw_rows if r["kwh_per_metre"] is not None]
    # Use shed's own median when >= 3 cycles exist; otherwise reference calibrated shuttle benchmark (0.131 kWh/m)
    baseline_kwh_per_m = float(median(valid_ratios)) if len(valid_ratios) >= 3 else (valid_ratios[0] if valid_ratios else 0.131)

    normal_points: list[tuple[float, float]] = []
    for r in raw_rows:
        km = r["kwh_per_metre"]
        if km is None:
            continue
        if len(valid_ratios) >= 2 and km < 0.65 * baseline_kwh_per_m:
            r["status_flag"] = "METER_UNDER_READING"
            r["status_note"] = (
                f"{km:.3f} kWh/m is >35% below normal ({baseline_kwh_per_m:.3f} kWh/m) — check EB meter / phase loss."
            )
        elif len(valid_ratios) >= 2 and km > 1.30 * baseline_kwh_per_m:
            r["status_flag"] = "HIGH_POWER_USAGE"
            r["status_note"] = (
                f"{km:.3f} kWh/m is >30% above normal ({baseline_kwh_per_m:.3f} kWh/m) — check idle motors, PF, or unlogged cloth."
            )
        else:
            r["status_flag"] = "NORMAL"
            r["status_note"] = "Power consumption matches cloth woven."
            normal_points.append((r["metres_produced"], r["units_kwh"]))

    # Fit metre-based EB predictor (OLS when >=3 distinct normal cycles, else ratio)
    model_kind = "CALIBRATED_SHUTTLE_DEFAULT"
    base_kwh = 0.0
    slope_kwh_per_m = 0.131
    if len(normal_points) >= 3:
        xs = [p[0] for p in normal_points]
        ys = [p[1] for p in normal_points]
        mx = sum(xs) / len(xs)
        my = sum(ys) / len(ys)
        denom = sum((x - mx) ** 2 for x in xs)
        if denom > 1.0:
            slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
            intercept = my - slope * mx
            if slope > 0.01 and intercept >= 0:
                model_kind = "SHED_OLS_REGRESSION"
                base_kwh = round(intercept, 1)
                slope_kwh_per_m = round(slope, 5)
            else:
                model_kind = "SHED_MEDIAN_RATIO"
                base_kwh = 0.0
                slope_kwh_per_m = round(float(median([y / x for x, y in normal_points if x > 0])), 4)
    elif normal_points:
        model_kind = "SHED_OBSERVED_RATIO"
        base_kwh = 0.0
        slope_kwh_per_m = round(sum(y for _, y in normal_points) / sum(x for x, _ in normal_points), 4)

    normal_rows = [r for r in raw_rows if r["status_flag"] == "NORMAL"]
    avg_kwh_per_m = round(sum(r["kwh_per_metre"] for r in normal_rows) / len(normal_rows), 4) if normal_rows else None
    avg_m_per_kwh = round(sum(r["metres_per_kwh"] for r in normal_rows) / len(normal_rows), 2) if normal_rows else None
    avg_eb_paise_per_m = (
        int(round(sum(r["eb_paise_per_metre"] for r in normal_rows) / len(normal_rows))) if normal_rows else None
    )

    # Build quick lookup estimates scaled to shed size
    ref_metres = round(normal_rows[0]["metres_produced"], -2) if normal_rows else 10000.0
    presets_m = sorted({max(1000.0, round(ref_metres * f, -2)) for f in (0.75, 1.0, 1.25)})
    sample_estimates = []
    for m_val in presets_m:
        est_kwh = round(base_kwh + slope_kwh_per_m * m_val, 1)
        bd = (
            calculate_bill_breakdown_paise(est_kwh, plan, sanctioned_kw=sanctioned_kw, billing_days=cycle_days)
            if plan
            else {"energy_paise": 0, "fixed_paise": 0, "tax_paise": 0, "fppca_paise": 0, "net_bill_paise": 0}
        )
        sample_estimates.append(
            {
                "metres": m_val,
                "estimated_kwh": est_kwh,
                "estimated_bill_paise": bd["net_bill_paise"],
                "eb_paise_per_metre": int(round(bd["net_bill_paise"] / m_val)) if m_val > 0 else 0,
            }
        )

    return {
        "periods": raw_rows,
        "avg_kwh_per_metre": avg_kwh_per_m,
        "avg_metres_per_kwh": avg_m_per_kwh,
        "avg_eb_paise_per_metre": avg_eb_paise_per_m,
        "baseline_kwh_per_metre": round(baseline_kwh_per_m, 4),
        "model_kind": model_kind,
        "base_kwh": base_kwh,
        "slope_kwh_per_metre": slope_kwh_per_m,
        "sample_estimates": sample_estimates,
    }


def estimate_eb_for_metres(db: Session, target_metres: float) -> dict[str, Any]:
    """Estimate bi-monthly EB units and itemized bill for any target cloth metres woven."""
    eff = compute_eb_vs_metres_efficiency(db)
    plan, sanctioned_kw = _get_active_tariff_and_kw(db)
    cycle_days = plan.billing_cycle_days if plan else 60
    m_val = max(0.0, float(target_metres))
    est_kwh = round(eff["base_kwh"] + eff["slope_kwh_per_metre"] * m_val, 1) if m_val > 0 else 0.0
    bd = (
        calculate_bill_breakdown_paise(est_kwh, plan, sanctioned_kw=sanctioned_kw, billing_days=cycle_days)
        if plan
        else {"energy_paise": 0, "fixed_paise": 0, "tax_paise": 0, "fppca_paise": 0, "net_bill_paise": 0}
    )
    return {
        "target_metres": m_val,
        "estimated_kwh": est_kwh,
        "energy_paise": bd["energy_paise"],
        "fixed_paise": bd["fixed_paise"],
        "tax_paise": bd["tax_paise"],
        "fppca_paise": bd["fppca_paise"],
        "estimated_bill_paise": bd["net_bill_paise"],
        "eb_paise_per_metre": int(round(bd["net_bill_paise"] / m_val)) if m_val > 0 else 0,
        "model_kind": eff["model_kind"],
        "tariff_name": plan.name if plan else "No active EB plan",
    }


def calculate_custom_eb_bill(
    db: Session,
    *,
    units_kwh: float,
    sanctioned_kw: float | None = None,
    billing_days: int | None = None,
    recorded_demand_kw: float | None = None,
) -> dict[str, Any]:
    """Compute TNPDCL-style itemized EB bill working sheet using the active DB tariff plan."""
    plan, default_kw = _get_active_tariff_and_kw(db)
    kw = float(sanctioned_kw) if (sanctioned_kw is not None and sanctioned_kw > 0) else default_kw
    days = int(billing_days) if (billing_days is not None and billing_days > 0) else (plan.billing_cycle_days if plan else 60)
    units = max(0.0, float(units_kwh))
    rec_kw = float(recorded_demand_kw) if (recorded_demand_kw is not None and recorded_demand_kw > 0) else None

    if not plan:
        return {
            "tariff_name": "No active EB plan",
            "units_kwh": units,
            "sanctioned_kw": kw,
            "recorded_demand_kw": rec_kw,
            "billing_days": days,
            "free_quota_applied": False,
            "slabs": [],
            "energy_paise": 0,
            "fixed_paise": 0,
            "fppca_paise": 0,
            "tax_paise": 0,
            "net_bill_paise": 0,
            "rounded_payable_rupees": 0,
            "avg_paise_per_kwh": 0,
        }

    slabs = calculate_slab_breakdown_rows(units, plan)
    bd = calculate_bill_breakdown_paise(
        units,
        plan,
        sanctioned_kw=kw,
        billing_days=days,
        recorded_demand_kw=rec_kw,
    )
    free_quota_applied = bd["net_bill_paise"] == 0 and units > 0
    rounded_rs = int(round(bd["net_bill_paise"] / 100.0))
    avg_paise = int(round(bd["net_bill_paise"] / units)) if units > 0 else 0

    return {
        "tariff_name": plan.name,
        "units_kwh": round(units, 2),
        "sanctioned_kw": kw,
        "recorded_demand_kw": rec_kw,
        "billing_days": days,
        "free_quota_applied": free_quota_applied,
        "slabs": slabs,
        "energy_paise": bd["energy_paise"],
        "fixed_paise": bd["fixed_paise"],
        "fppca_paise": bd["fppca_paise"],
        "tax_paise": bd["tax_paise"],
        "net_bill_paise": bd["net_bill_paise"],
        "rounded_payable_rupees": rounded_rs,
        "avg_paise_per_kwh": avg_paise,
    }


def compute_production_anomalies(db: Session) -> list[dict[str, Any]]:
    """Detect Physical Cap breaches and robust MAD/IQR low-output outliers in recent shifts."""
    today = date.today()
    since30 = today - timedelta(days=29)
    shifts = db.scalars(
        select(ShiftEntry)
        .where(ShiftEntry.is_deleted.is_(False), ShiftEntry.entry_date >= since30)
        .order_by(ShiftEntry.entry_date.desc(), ShiftEntry.shift_no.desc())
    ).all()
    looms = {l.id: l for l in db.scalars(select(Loom)).all()}
    beams = {b.id: b for b in db.scalars(select(Beam)).all()}
    sorts = {s.id: s for s in db.scalars(select(FabricSort)).all()}

    vals_by_loom: dict[int, list[float]] = defaultdict(list)
    for sh in shifts:
        vals_by_loom[sh.loom_id].append(float(sh.net_metres))

    stats_by_loom: dict[int, tuple[float, float, float, float]] = {}
    for l_id, vals in vals_by_loom.items():
        if len(vals) < 4:
            continue
        sv = sorted(vals)
        med = float(median(sv))
        mad = float(median([abs(v - med) for v in sv]))
        q25 = _quantile(sv, 0.25)
        q75 = _quantile(sv, 0.75)
        stats_by_loom[l_id] = (med, mad, q25, q75)

    anomalies: list[dict[str, Any]] = []
    for sh in shifts:
        loom = looms.get(sh.loom_id)
        l_num = loom.loom_number if loom else f"Loom #{sh.loom_id}"
        val = float(sh.net_metres)

        beam = beams.get(sh.beam_id) if sh.beam_id else None
        srt = sorts.get(beam.sort_id) if beam else None
        if loom and srt and srt.pick > 0 and sh.planned_mins > 0:
            ideal_m = (loom.rated_rpm * 0.0254 / srt.pick) * sh.planned_mins
            if val > 1.05 * ideal_m:
                anomalies.append(
                    {
                        "shift_id": sh.id,
                        "entry_date": sh.entry_date.isoformat(),
                        "shift_no": sh.shift_no,
                        "loom_number": l_num,
                        "net_metres": round(val, 2),
                        "expected_median_m": round(ideal_m, 2),
                        "kind": "PHYSICAL_CAP",
                        "severity": "WARN",
                        "reason": f"{val:.2f} m exceeds physical loom speed limit ({ideal_m:.2f} m at {loom.rated_rpm} RPM)",
                    }
                )
                continue

        if sh.loom_id in stats_by_loom:
            med, mad, q25, q75 = stats_by_loom[sh.loom_id]
            iqr = q75 - q25
            low_fence = q25 - 1.5 * iqr
            z_mad = abs(val - med) / max(1.0, 1.4826 * mad)
            if (val < low_fence and val < med * 0.85) or z_mad > 3.0:
                note = "Stopped shift" if val == 0 else "Unusually low output" if val < med else "Unusually high spike"
                anomalies.append(
                    {
                        "shift_id": sh.id,
                        "entry_date": sh.entry_date.isoformat(),
                        "shift_no": sh.shift_no,
                        "loom_number": l_num,
                        "net_metres": round(val, 2),
                        "expected_median_m": round(med, 2),
                        "kind": "MAD_IQR_OUTLIER",
                        "severity": "CRITICAL" if val == 0 else "WARN",
                        "reason": f"{val:.2f} m woven ({note} vs {med:.2f} m typical shift)",
                    }
                )

    return anomalies[:20]


def compute_weekly_forecast(db: Session) -> dict[str, Any]:
    """5-week walk-forward weekly production forecast comparing CN-MA, Holt Linear, and Naive."""
    today = date.today()
    # Build 5 consecutive 7-day buckets ending today
    buckets: list[dict[str, Any]] = []
    for w_idx in range(4, -1, -1):
        w_end = today - timedelta(days=w_idx * 7)
        w_start = w_end - timedelta(days=6)
        rows = db.scalars(
            select(ShiftEntry).where(
                ShiftEntry.is_deleted.is_(False),
                ShiftEntry.entry_date >= w_start,
                ShiftEntry.entry_date <= w_end,
            )
        ).all()
        actual_m = round(sum(float(r.net_metres) for r in rows), 2)
        loom_shifts = max(1, len(rows))
        buckets.append(
            {
                "label": f"W{5 - w_idx}",
                "week_start": w_start.isoformat(),
                "week_end": w_end.isoformat(),
                "actual_metres": actual_m,
                "loom_shifts": len(rows),
                "metres_per_shift": round(actual_m / loom_shifts, 2),
            }
        )

    actuals = [b["actual_metres"] for b in buckets]
    shifts_counts = [b["loom_shifts"] for b in buckets]

    naive_errs: list[float] = []
    cnma_errs: list[float] = []
    holt_errs: list[float] = []

    level = actuals[0] if actuals else 0.0
    trend = (actuals[1] - actuals[0]) if len(actuals) > 1 else 0.0
    alpha, beta = 0.5, 0.2

    for i in range(1, len(buckets)):
        y_true = actuals[i]
        # Naive
        y_naive = actuals[i - 1]
        naive_errs.append(abs(y_true - y_naive))

        # CN-MA over up to prior 3 weeks
        prior_idx = list(range(max(0, i - 3), i))
        prior_m = sum(actuals[j] for j in prior_idx)
        prior_s = sum(shifts_counts[j] for j in prior_idx)
        avg_m_per_shift = (prior_m / prior_s) if prior_s > 0 else 25.0
        y_cnma = avg_m_per_shift * max(1, shifts_counts[i])
        cnma_errs.append(abs(y_true - y_cnma))

        # Holt 1-step ahead
        y_holt = max(0.0, level + trend)
        holt_errs.append(abs(y_true - y_holt))
        prev_level = level
        level = alpha * y_true + (1 - alpha) * (level + trend)
        trend = beta * (level - prev_level) + (1 - beta) * trend

    def _err_summary(errs: list[float], ys: list[float]) -> tuple[float, float]:
        if not errs:
            return 0.0, 0.0
        mae = sum(errs) / len(errs)
        mapes = [e / y * 100.0 for e, y in zip(errs, ys) if y > 0]
        mape = (sum(mapes) / len(mapes)) if mapes else 0.0
        return round(mae, 1), round(mape, 1)

    naive_mae, naive_mape = _err_summary(naive_errs, actuals[1:])
    cnma_mae, cnma_mape = _err_summary(cnma_errs, actuals[1:])
    holt_mae, holt_mape = _err_summary(holt_errs, actuals[1:])

    # Forecast next 7 days
    settings = db.scalar(select(UnitSettings).limit(1))
    default_shifts_day = settings.shifts_per_day if settings else 2
    op_looms = len(db.scalars(select(Loom).where(Loom.is_active.is_(True), Loom.status == "OPERATIONAL")).all()) or 5
    next_start = today + timedelta(days=1)
    next_end = today + timedelta(days=7)

    cal_rows = {
        c.calendar_date: c
        for c in db.scalars(
            select(ShedCalendar).where(ShedCalendar.calendar_date >= next_start, ShedCalendar.calendar_date <= next_end)
        ).all()
    }
    planned_work_days = 0
    planned_loom_shifts = 0
    for d_off in range(7):
        d = next_start + timedelta(days=d_off)
        cal = cal_rows.get(d)
        if cal:
            if cal.is_working_day:
                planned_work_days += 1
                planned_loom_shifts += cal.planned_shifts * op_looms
        else:
            planned_work_days += 1
            planned_loom_shifts += default_shifts_day * op_looms

    recent_m = sum(actuals[-3:])
    recent_s = sum(shifts_counts[-3:])
    recent_rate = (recent_m / recent_s) if recent_s > 0 else 25.0

    cnma_next = round(recent_rate * planned_loom_shifts, 1)
    holt_next = round(max(0.0, level + trend), 1)
    naive_next = round(actuals[-1], 1) if actuals else 0.0

    candidates = [
        ("CN-MA", cnma_mae, cnma_mape, cnma_next),
        ("Holt Linear", holt_mae, holt_mape, holt_next),
        ("Naive", naive_mae, naive_mape, naive_next),
    ]
    winner = min(candidates, key=lambda x: x[1])

    return {
        "history": buckets,
        "models": [
            {"model": name, "mae_m": mae, "mape_pct": mape, "next_week_forecast_m": fc, "is_winner": name == winner[0]}
            for name, mae, mape, fc in candidates
        ],
        "winner_model": winner[0],
        "recommended_forecast_m": winner[3],
        "next_week_start": next_start.isoformat(),
        "next_week_end": next_end.isoformat(),
        "planned_working_days": planned_work_days,
        "planned_loom_shifts": planned_loom_shifts,
    }


def _compute_scenario(
    *,
    loom_count: int,
    rpm: float,
    pick_ppi: float,
    efficiency_pct: float,
    shifts_per_day: int,
    shift_hours: float,
    working_days_month: int,
    rate_per_metre_rs: float,
    weaver_wage_per_loom_shift_rs: float,
    helper_monthly_rs: float,
    capex_per_loom_rs: float,
    loan_pct: float,
    annual_interest_pct: float,
    loan_tenure_months: int,
    fixed_overhead_monthly_rs: float,
    kw_per_loom: float,
    tariff: EbTariffPlan | None,
) -> dict[str, Any]:
    shift_mins = shift_hours * 60.0
    total_loom_shifts = loom_count * shifts_per_day * working_days_month
    theoretical_m_per_min = (rpm * 0.0254) / max(1.0, pick_ppi)
    monthly_metres = round(theoretical_m_per_min * shift_mins * (efficiency_pct / 100.0) * total_loom_shifts, 1)

    gross_rev_paise = int(round(monthly_metres * rate_per_metre_rs * 100))
    weaver_wages_paise = int(round(total_loom_shifts * weaver_wage_per_loom_shift_rs * 100))
    helper_wages_paise = int(round(helper_monthly_rs * max(1.0, loom_count / 10.0) * 100))
    overhead_paise = int(round(fixed_overhead_monthly_rs * 100))

    total_kw = max(5.0, loom_count * kw_per_loom)
    est_monthly_kwh = loom_count * 6.5 * working_days_month
    if tariff:
        # Bi-monthly cycle -> prorate 30-day monthly EB cost (half of 60-day slab cycle * 2 -> simulate 60d/2)
        cycle_days = max(30, tariff.billing_cycle_days)
        eb_cycle = calculate_bill_breakdown_paise(
            est_monthly_kwh * (cycle_days / 30.0), tariff, sanctioned_kw=total_kw, billing_days=cycle_days
        )
        eb_monthly_paise = int(round(eb_cycle["net_bill_paise"] * (30.0 / cycle_days)))
    else:
        eb_monthly_paise = int(round(est_monthly_kwh * 5.0 * 100))

    ebitda_paise = gross_rev_paise - weaver_wages_paise - helper_wages_paise - eb_monthly_paise - overhead_paise
    total_capex_paise = int(round(loom_count * capex_per_loom_rs * 100))
    principal_paise = int(round(total_capex_paise * (loan_pct / 100.0)))

    r_monthly = (annual_interest_pct / 100.0) / 12.0
    n_months = max(1, loan_tenure_months)
    if principal_paise > 0 and r_monthly > 0:
        factor = (1.0 + r_monthly) ** n_months
        emi_paise = int(round(principal_paise * r_monthly * factor / (factor - 1.0)))
    elif principal_paise > 0:
        emi_paise = int(round(principal_paise / n_months))
    else:
        emi_paise = 0

    net_after_emi_paise = ebitda_paise - emi_paise
    payback_months = round(total_capex_paise / ebitda_paise, 1) if ebitda_paise > 0 else None

    return {
        "loom_count": loom_count,
        "monthly_metres": monthly_metres,
        "gross_revenue_paise": gross_rev_paise,
        "weaver_wages_paise": weaver_wages_paise,
        "helper_wages_paise": helper_wages_paise,
        "eb_monthly_paise": eb_monthly_paise,
        "overhead_paise": overhead_paise,
        "ebitda_paise": ebitda_paise,
        "total_capex_paise": total_capex_paise,
        "emi_paise": emi_paise,
        "net_after_emi_paise": net_after_emi_paise,
        "payback_months": payback_months,
    }


def simulate_expansion(db: Session, params: dict[str, Any]) -> dict[str, Any]:
    """Deterministic multi-size expansion P&L, EMI, payback, and 2D Rate × Efficiency sensitivity matrix."""
    settings = db.scalar(select(UnitSettings).limit(1))
    tariff = None
    if settings and settings.active_tariff_plan_id:
        tariff = db.scalar(
            select(EbTariffPlan).options(selectinload(EbTariffPlan.slabs)).where(EbTariffPlan.id == settings.active_tariff_plan_id)
        )
    if not tariff:
        tariff = db.scalar(
            select(EbTariffPlan).options(selectinload(EbTariffPlan.slabs)).where(EbTariffPlan.is_deleted.is_(False)).limit(1)
        )

    base_args = {
        "rpm": float(params.get("rpm", 160)),
        "pick_ppi": float(params.get("pick_ppi", 76)),
        "efficiency_pct": float(params.get("efficiency_pct", 85)),
        "shifts_per_day": int(params.get("shifts_per_day", 2)),
        "shift_hours": float(params.get("shift_hours", 10.0)),
        "working_days_month": int(params.get("working_days_month", 25)),
        "rate_per_metre_rs": float(params.get("rate_per_metre_rs", 6.0)),
        "weaver_wage_per_loom_shift_rs": float(params.get("weaver_wage_per_loom_shift_rs", 60.0)),
        "helper_monthly_rs": float(params.get("helper_monthly_rs", 10000.0)),
        "capex_per_loom_rs": float(params.get("capex_per_loom_rs", 95000.0)),
        "loan_pct": float(params.get("loan_pct", 70.0)),
        "annual_interest_pct": float(params.get("annual_interest_pct", 11.5)),
        "loan_tenure_months": int(params.get("loan_tenure_months", 60)),
        "fixed_overhead_monthly_rs": float(params.get("fixed_overhead_monthly_rs", 18000.0)),
        "kw_per_loom": float(params.get("kw_per_loom", 0.75)),
        "tariff": tariff,
    }
    loom_count = int(params.get("loom_count", 20))
    primary = _compute_scenario(loom_count=loom_count, **base_args)

    presets = [_compute_scenario(loom_count=n, **base_args) for n in (20, 30, 50, 100)]

    rate_deltas = [-0.50, -0.25, 0.0, 0.25, 0.50]
    eff_levels = [75.0, 80.0, 85.0, 90.0, 95.0]
    matrix: list[dict[str, Any]] = []
    for rd in rate_deltas:
        row_rate = round(base_args["rate_per_metre_rs"] + rd, 2)
        cells = []
        for eff in eff_levels:
            args_cell = {**base_args, "rate_per_metre_rs": max(1.0, row_rate), "efficiency_pct": eff}
            res_cell = _compute_scenario(loom_count=loom_count, **args_cell)
            cells.append({"efficiency_pct": eff, "ebitda_paise": res_cell["ebitda_paise"]})
        matrix.append({"rate_rs": row_rate, "cells": cells})

    return {
        "inputs": {k: v for k, v in base_args.items() if k != "tariff"} | {"loom_count": loom_count},
        "primary": primary,
        "presets": presets,
        "sensitivity_efficiencies": eff_levels,
        "sensitivity_matrix": matrix,
    }


def build_printable_statement(
    db: Session, *, from_date: date, to_date: date, trader_id: int | None = None
) -> dict[str, Any]:
    """Generate structured Monthly P&L & Trader Account Statement payload."""
    settings = db.scalar(select(UnitSettings).limit(1))
    dash = compute_floor_dashboard(db, period_start=from_date, period_end=to_date)
    fin = compute_owner_financials(db, period_start=from_date, period_end=to_date)

    traders = {t.id: t.company_name for t in db.scalars(select(Trader)).all()}
    d_stmt = (
        select(Delivery)
        .where(
            Delivery.is_deleted.is_(False),
            Delivery.delivery_date >= from_date,
            Delivery.delivery_date <= to_date,
        )
        .order_by(Delivery.delivery_date.asc(), Delivery.id.asc())
    )
    if trader_id:
        d_stmt = d_stmt.where(Delivery.trader_id == trader_id)
    deliveries = db.scalars(d_stmt).all()

    p_stmt = (
        select(TraderPayment)
        .where(
            TraderPayment.is_deleted.is_(False),
            TraderPayment.payment_date >= from_date,
            TraderPayment.payment_date <= to_date,
        )
        .order_by(TraderPayment.payment_date.asc())
    )
    if trader_id:
        p_stmt = p_stmt.where(TraderPayment.trader_id == trader_id)
    payments = db.scalars(p_stmt).all()

    items_by_del: dict[int, list[DeliveryItem]] = defaultdict(list)
    if deliveries:
        for it in db.scalars(
            select(DeliveryItem).where(
                DeliveryItem.is_deleted.is_(False),
                DeliveryItem.delivery_id.in_([d.id for d in deliveries]),
            )
        ).all():
            items_by_del[it.delivery_id].append(it)

    del_rows = []
    for d in deliveries:
        amt = sum(
            int((it.metres * Decimal(it.applied_rate_paise)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            for it in items_by_del[d.id]
        )
        del_rows.append(
            {
                "challan_no": d.challan_no,
                "delivery_date": d.delivery_date.isoformat(),
                "trader_name": traders.get(d.trader_id, f"Trader #{d.trader_id}"),
                "total_metres": str(d.total_metres),
                "amount_paise": amt,
            }
        )

    pay_rows = [
        {
            "payment_date": p.payment_date.isoformat(),
            "trader_name": traders.get(p.trader_id, f"Trader #{p.trader_id}"),
            "reference": p.reference or "-",
            "amount_paise": p.amount_paise,
            "shortage_deduction_paise": p.shortage_deduction_paise,
        }
        for p in payments
    ]

    return {
        "unit_name": settings.unit_name if settings else "LOOMOS",
        "location": settings.location if settings else "",
        "period_start": from_date.isoformat(),
        "period_end": to_date.isoformat(),
        "period_metres": str(dash["period_metres"]),
        "availability_pct": dash["availability_pct"],
        "performance_pct": dash["performance_pct"],
        "utilization_ap_pct": dash["utilization_ap_pct"],
        "quality_pct": dash["quality_pct"],
        "financials": fin,
        "deliveries": del_rows,
        "payments": pay_rows,
    }


def build_full_xlsx_workbook(db: Session) -> bytes:
    """Create formatted 6-sheet Excel (.xlsx) workbook using openpyxl."""
    wb = openpyxl.Workbook()
    header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")

    def _style_headers(ws, titles: list[str]) -> None:
        ws.append(titles)
        for col_idx in range(1, len(titles) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font

    today = date.today()
    month_start = today - timedelta(days=29)
    fin = compute_owner_financials(db, period_start=month_start, period_end=today)
    dash = compute_floor_dashboard(db, period_start=month_start, period_end=today)

    # Sheet 1: P&L Summary
    ws_pl = wb.active
    ws_pl.title = "P&L Summary"
    _style_headers(ws_pl, ["Metric (30-Day Window)", "Value"])
    for label, val in [
        ("Period Start", month_start.isoformat()),
        ("Period End", today.isoformat()),
        ("Total Cloth Woven (m)", float(dash["period_metres"])),
        ("Time Run % (Availability)", dash["availability_pct"] or "-"),
        ("Weaving Speed % (Performance)", dash["performance_pct"] or "-"),
        ("Billed Revenue (₹)", round(fin["billed_revenue_paise"] / 100.0, 2)),
        ("Finalized Wages (₹)", round(fin["finalized_wages_paise"] / 100.0, 2)),
        ("EB Bills (₹)", round(fin["eb_bills_paise"] / 100.0, 2)),
        ("Expenses (₹)", round(fin["expenses_paise"] / 100.0, 2)),
        ("Net Operating Balance (₹)", round(fin["net_operating_paise"] / 100.0, 2)),
        ("Pending Trader Receivables (₹)", round(fin["total_receivable_paise"] / 100.0, 2)),
        ("Trader Rate-Cut Shortfall (₹)", round(fin["total_rate_underpayment_paise"] / 100.0, 2)),
    ]:
        ws_pl.append([label, val])

    # Sheet 2: Shift Production
    ws_sh = wb.create_sheet("Shift Production")
    _style_headers(ws_sh, ["Date", "Shift #", "Loom", "Weaver", "Net Metres", "Defective (m)", "Planned Mins", "Downtime Mins"])
    looms_map = {l.id: l.loom_number for l in db.scalars(select(Loom)).all()}
    weavers_map = {w.id: w.full_name for w in db.scalars(select(Weaver)).all()}
    for sh in db.scalars(
        select(ShiftEntry).where(ShiftEntry.is_deleted.is_(False)).order_by(ShiftEntry.entry_date.desc()).limit(500)
    ).all():
        ws_sh.append([
            sh.entry_date.isoformat(),
            sh.shift_no,
            looms_map.get(sh.loom_id, sh.loom_id),
            weavers_map.get(sh.weaver_id, sh.weaver_id),
            float(sh.net_metres),
            float(sh.defective_metres),
            sh.planned_mins,
            sh.downtime_mins,
        ])

    # Sheet 3: Beams & Wastage
    ws_bm = wb.create_sheet("Beams & Wastage")
    _style_headers(ws_bm, ["Beam No", "Trader", "Sort", "Status", "Loom", "Usable (m)", "Woven (m)", "Remaining (m)", "Weft Used (kg)", "Wastage %"])
    for b in compute_beams_response_list(db):
        ws_bm.append([
            b["beam_no"],
            b["trader_name"],
            b["sort_name"],
            b["status"],
            b["active_loom_number"] or "-",
            float(b["usable_total_m"]),
            float(b["woven_m"]),
            float(b["remaining_m"]),
            float(b["weft_consumed_kg"]),
            b["actual_wastage_pct"] if b["actual_wastage_pct"] is not None else "-",
        ])

    # Sheet 4: Payroll Slips
    ws_pay = wb.create_sheet("Payroll Slips")
    _style_headers(ws_pay, ["Period Start", "Period End", "Worker", "Mode", "Units", "Gross (₹)", "Advance Cut (₹)", "Damage Cut (₹)", "Net Paid (₹)"])
    for s in db.scalars(select(Payslip).where(Payslip.is_deleted.is_(False)).order_by(Payslip.id.desc())).all():
        ws_pay.append([
            s.period_start.isoformat(),
            s.period_end.isoformat(),
            weavers_map.get(s.weaver_id, s.weaver_id),
            s.wage_mode_snapshot,
            float(s.units_worked),
            round(s.gross_paise / 100.0, 2),
            round(s.advance_deducted_paise / 100.0, 2),
            round(s.defect_deduction_paise / 100.0, 2),
            round(s.net_payable_paise / 100.0, 2),
        ])

    # Sheet 5: Deliveries & Rate Cuts
    ws_del = wb.create_sheet("Deliveries & Rate Cuts")
    _style_headers(ws_del, ["Challan No", "Date", "Trader", "Total Metres", "Billed (₹)"])
    traders_map = {t.id: t.company_name for t in db.scalars(select(Trader)).all()}
    items_all = defaultdict(int)
    for it in db.scalars(select(DeliveryItem).where(DeliveryItem.is_deleted.is_(False))).all():
        items_all[it.delivery_id] += int(round(float(it.metres) * it.applied_rate_paise))
    for d in db.scalars(select(Delivery).where(Delivery.is_deleted.is_(False)).order_by(Delivery.delivery_date.desc())).all():
        ws_del.append([
            d.challan_no,
            d.delivery_date.isoformat(),
            traders_map.get(d.trader_id, d.trader_id),
            float(d.total_metres),
            round(items_all[d.id] / 100.0, 2),
        ])

    # Sheet 6: EB Bills & Expenses
    ws_eb = wb.create_sheet("EB Bills & Expenses")
    _style_headers(ws_eb, ["Kind", "Start / Date", "End", "Category / Units", "Amount (₹)", "Notes"])
    for b in db.scalars(select(EbBill).where(EbBill.is_deleted.is_(False)).order_by(EbBill.period_end.desc())).all():
        ws_eb.append(["EB Bill", b.period_start.isoformat(), b.period_end.isoformat(), f"{b.units_consumed} kWh", round(b.net_bill_paise / 100.0, 2), b.notes or ""])
    for e in db.scalars(select(Expense).where(Expense.is_deleted.is_(False)).order_by(Expense.expense_date.desc())).all():
        ws_eb.append(["Expense", e.expense_date.isoformat(), "", e.category, round(e.amount_paise / 100.0, 2), e.note or ""])

    # Sheet 7: EB vs Metres Efficiency
    ws_eff = wb.create_sheet("EB vs Metres")
    _style_headers(
        ws_eff,
        ["Period Start", "Period End", "Days", "Metres Woven", "Source", "EB Units (kWh)", "EB Bill (₹)", "kWh / Metre", "Metres / kWh", "EB Cost (₹/m)", "Meter Status"],
    )
    eff_data = compute_eb_vs_metres_efficiency(db)
    for row in eff_data["periods"]:
        ws_eff.append([
            row["period_start"],
            row["period_end"],
            row["days"],
            row["metres_produced"],
            row["metres_source"],
            row["units_kwh"],
            round(row["net_bill_paise"] / 100.0, 2),
            row["kwh_per_metre"] if row["kwh_per_metre"] is not None else "-",
            row["metres_per_kwh"] if row["metres_per_kwh"] is not None else "-",
            round(row["eb_paise_per_metre"] / 100.0, 2) if row["eb_paise_per_metre"] is not None else "-",
            row["status_flag"],
        ])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
