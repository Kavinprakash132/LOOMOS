"""4-mode integer-paise payroll calculator with dated wage rule lookup and advance tracking."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.core import Advance, Payslip, ShiftEntry, WageRule, Weaver, WeaverAttendance


ATTENDANCE_WEIGHTS = {
    "PRESENT": Decimal("1.0"),
    "HALF": Decimal("0.5"),
    "ABSENT": Decimal("0.0"),
}


def resolve_wage_rule_for_date(rules: list[WageRule], target_date: date) -> WageRule | None:
    """Pick the active non-deleted wage rule on target_date (falling back cleanly to earliest rule)."""
    active = [r for r in rules if not r.is_deleted]
    if not active:
        return None
    ordered_desc = sorted(active, key=lambda r: (r.effective_from, r.id), reverse=True)
    for r in ordered_desc:
        if r.effective_from <= target_date and (r.effective_to is None or r.effective_to >= target_date):
            return r
    # Fallback to earliest active rule if shifts were logged slightly prior to initial effective_from
    return sorted(active, key=lambda r: (r.effective_from, r.id))[0]


def calculate_payroll_preview(
    db: Session,
    *,
    period_start: date,
    period_end: date,
    weaver_ids: list[int] | None = None,
    deduct_period_advances: bool = True,
    defect_deductions_paise: dict[int, int] | None = None,
) -> list[dict]:
    """Calculate exact integer-paise payroll preview across all 4 wage modes."""
    deductions_map = defect_deductions_paise or {}

    weaver_stmt = select(Weaver).options(selectinload(Weaver.wage_rules)).where(Weaver.is_active.is_(True)).order_by(Weaver.full_name)
    if weaver_ids:
        weaver_stmt = weaver_stmt.where(Weaver.id.in_(weaver_ids))
    weavers = db.scalars(weaver_stmt).all()
    if not weavers:
        return []

    target_weaver_ids = [w.id for w in weavers]

    shifts = db.scalars(
        select(ShiftEntry).where(
            ShiftEntry.weaver_id.in_(target_weaver_ids),
            ShiftEntry.entry_date >= period_start,
            ShiftEntry.entry_date <= period_end,
            ShiftEntry.is_deleted.is_(False),
        )
    ).all()
    shifts_by_weaver: dict[int, list[ShiftEntry]] = defaultdict(list)
    for s in shifts:
        shifts_by_weaver[s.weaver_id].append(s)

    att_rows = db.scalars(
        select(WeaverAttendance).where(
            WeaverAttendance.weaver_id.in_(target_weaver_ids),
            WeaverAttendance.attendance_date >= period_start,
            WeaverAttendance.attendance_date <= period_end,
            WeaverAttendance.is_deleted.is_(False),
        )
    ).all()
    att_by_weaver: dict[int, dict[tuple[date, int], Decimal]] = defaultdict(dict)
    for a in att_rows:
        att_by_weaver[a.weaver_id][(a.attendance_date, a.shift_no)] = ATTENDANCE_WEIGHTS.get(a.status, Decimal("0.0"))

    # Compute un-deducted advance balance per worker up to period_end
    open_adv_by_weaver: dict[int, int] = defaultdict(int)
    if deduct_period_advances:
        adv_rows = db.scalars(
            select(Advance).where(
                Advance.weaver_id.in_(target_weaver_ids),
                Advance.advance_date <= period_end,
                Advance.is_deleted.is_(False),
            )
        ).all()
        paid_adv_sum: dict[int, int] = defaultdict(int)
        for adv in adv_rows:
            paid_adv_sum[adv.weaver_id] += adv.amount_paise

        prev_slips = db.scalars(
            select(Payslip).where(
                Payslip.weaver_id.in_(target_weaver_ids),
                Payslip.is_deleted.is_(False),
            )
        ).all()
        deducted_sum: dict[int, int] = defaultdict(int)
        for sl in prev_slips:
            deducted_sum[sl.weaver_id] += sl.advance_deducted_paise

        for wid in target_weaver_ids:
            open_adv_by_weaver[wid] = max(0, paid_adv_sum[wid] - deducted_sum[wid])

    period_days = (period_end - period_start).days + 1
    out: list[dict] = []

    for w in weavers:
        end_rule = resolve_wage_rule_for_date(w.wage_rules, period_end)
        if not end_rule:
            continue

        w_shifts = shifts_by_weaver[w.id]
        w_att = att_by_weaver[w.id]
        mode = end_rule.wage_mode
        units_worked = Decimal("0.00")
        gross_paise = 0
        rule_breakdown: dict[tuple[str, int], dict] = {}

        def _add_bucket(r_mode: str, r_paise: int, units: Decimal, sub_gross: int) -> None:
            key = (r_mode, r_paise)
            if key not in rule_breakdown:
                rule_breakdown[key] = {"wage_mode": r_mode, "rate_paise": r_paise, "units": Decimal("0.00"), "gross_paise": 0}
            rule_breakdown[key]["units"] += units
            rule_breakdown[key]["gross_paise"] += sub_gross

        if mode == "PER_METRE":
            for s in w_shifts:
                r = resolve_wage_rule_for_date(w.wage_rules, s.entry_date) or end_rule
                amt = int((s.net_metres * Decimal(r.rate_paise)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                units_worked += s.net_metres
                gross_paise += amt
                _add_bucket(r.wage_mode, r.rate_paise, s.net_metres, amt)

        elif mode == "PER_LOOM_SHIFT":
            # Deduplicate mid-shift beam swaps on the same (date, shift_no, loom_id)
            seen_loom_shifts: set[tuple[date, int, int]] = set()
            for s in w_shifts:
                ls_key = (s.entry_date, s.shift_no, s.loom_id)
                if ls_key in seen_loom_shifts:
                    continue
                seen_loom_shifts.add(ls_key)
                r = resolve_wage_rule_for_date(w.wage_rules, s.entry_date) or end_rule
                unit = Decimal("1.00")
                units_worked += unit
                gross_paise += r.rate_paise
                _add_bucket(r.wage_mode, r.rate_paise, unit, r.rate_paise)

        elif mode == "PER_SHIFT_ATTENDANCE":
            # Start from unique (date, shift) loom entries = 1.0, then override with explicit attendance rows
            shift_credits: dict[tuple[date, int], Decimal] = {}
            for s in w_shifts:
                shift_credits[(s.entry_date, s.shift_no)] = Decimal("1.0")
            for k, val in w_att.items():
                shift_credits[k] = val

            for (d, _sno), weight in sorted(shift_credits.items()):
                if weight <= 0:
                    continue
                r = resolve_wage_rule_for_date(w.wage_rules, d) or end_rule
                amt = int((weight * Decimal(r.rate_paise)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                units_worked += weight
                gross_paise += amt
                _add_bucket(r.wage_mode, r.rate_paise, weight, amt)

        elif mode == "FIXED_WEEKLY":
            # Check absent deductions only if explicit ABSENT attendance isn't relevant; pay weekly prorated cleanly
            units_worked = (Decimal(period_days) / Decimal(7)).quantize(Decimal("0.01"))
            cur = period_start
            raw_sum = Decimal("0")
            while cur <= period_end:
                r = resolve_wage_rule_for_date(w.wage_rules, cur) or end_rule
                day_share = Decimal(r.rate_paise) / Decimal(7)
                raw_sum += day_share
                _add_bucket(r.wage_mode, r.rate_paise, Decimal("0.14"), 0)
                cur += timedelta(days=1)
            gross_paise = int(raw_sum.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            for b in rule_breakdown.values():
                b["units"] = units_worked
                b["gross_paise"] = gross_paise

        adv_ded = min(gross_paise, open_adv_by_weaver[w.id]) if deduct_period_advances else 0
        def_ded = max(0, deductions_map.get(w.id, 0))
        net_paise = max(0, gross_paise - adv_ded - def_ded)

        out.append(
            {
                "weaver_id": w.id,
                "weaver_name": w.full_name,
                "full_name_ta": w.full_name_ta,
                "full_name_hi": w.full_name_hi,
                "preferred_slip_lang": w.preferred_slip_lang,
                "role_type": w.role_type,
                "wage_mode": mode,
                "units_worked": units_worked.quantize(Decimal("0.01")),
                "rate_paise": end_rule.rate_paise,
                "gross_paise": gross_paise,
                "advance_deducted_paise": adv_ded,
                "defect_deduction_paise": def_ded,
                "net_payable_paise": net_paise,
                "rule_breakdown": [
                    {
                        "wage_mode": k["wage_mode"],
                        "rate_paise": k["rate_paise"],
                        "units": str(k["units"].quantize(Decimal("0.01"))),
                        "gross_paise": k["gross_paise"],
                    }
                    for k in rule_breakdown.values()
                ],
            }
        )
    return out
