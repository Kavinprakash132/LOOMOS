"""Database-driven electricity tariff slab calculator (no hardcoded rates)."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from app.models.core import EbTariffPlan


def calculate_energy_charge_paise(units_kwh: Decimal | float | int, plan: EbTariffPlan) -> int:
    """Compute energy charges in integer paise by summing slab intervals in the tariff plan."""
    remaining = Decimal(str(units_kwh))
    if remaining <= 0:
        return 0

    total_paise = Decimal("0")
    ordered_slabs = sorted(plan.slabs, key=lambda s: s.min_unit)
    for slab in ordered_slabs:
        slab_start = Decimal(slab.min_unit)
        # Convert 1-based inclusive slab start (e.g. min_unit=1001, max_unit=1500 -> 500 units)
        lower_edge = slab_start - Decimal(1) if slab.min_unit > 0 else Decimal(0)
        if remaining <= lower_edge:
            continue
        upper_edge = Decimal(slab.max_unit) if slab.max_unit is not None else remaining
        units_in_slab = min(remaining, upper_edge) - lower_edge
        if units_in_slab > 0:
            total_paise += units_in_slab * Decimal(slab.rate_paise_per_unit)

    return int(total_paise.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate_slab_breakdown_rows(units_kwh: Decimal | float | int, plan: EbTariffPlan) -> list[dict[str, object]]:
    """Return TNPDCL-style slab-by-slab working sheet rows for any consumption figure."""
    remaining = max(Decimal("0"), Decimal(str(units_kwh)))
    rows: list[dict[str, object]] = []
    ordered_slabs = sorted(plan.slabs, key=lambda s: s.min_unit)
    for idx, slab in enumerate(ordered_slabs, 1):
        slab_start = Decimal(slab.min_unit)
        lower_edge = slab_start - Decimal(1) if slab.min_unit > 0 else Decimal(0)
        if remaining <= lower_edge:
            units_in_slab = Decimal("0")
        else:
            upper_edge = Decimal(slab.max_unit) if slab.max_unit is not None else remaining
            units_in_slab = max(Decimal("0"), min(remaining, upper_edge) - lower_edge)
        amt_paise = int((units_in_slab * Decimal(slab.rate_paise_per_unit)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        rows.append(
            {
                "slab_no": idx,
                "from_unit": slab.min_unit,
                "to_unit": slab.max_unit,
                "units_in_slab": float(units_in_slab),
                "rate_paise_per_unit": slab.rate_paise_per_unit,
                "amount_paise": amt_paise,
            }
        )
    return rows


def calculate_bill_breakdown_paise(
    units_kwh: Decimal | float | int,
    plan: EbTariffPlan,
    *,
    sanctioned_kw: Decimal | float | int = Decimal("10.00"),
    billing_days: int | None = None,
    recorded_demand_kw: Decimal | float | int | None = None,
) -> dict[str, int]:
    """Compute itemized EB bill prediction (energy, fixed, FPPCA, tax, net) in integer paise.

    Honors TNPDCL LT-III A(2) free-quota rule: if total units fall completely inside a zero-rate
    subsidized slab (e.g. <= 1,000 kWh), fixed charge and electricity tax are also waived (net = 0).
    """
    units_dec = max(Decimal("0"), Decimal(str(units_kwh)))
    kw_dec = max(Decimal("0"), Decimal(str(sanctioned_kw)))
    days = billing_days if billing_days is not None and billing_days > 0 else plan.billing_cycle_days

    energy_paise = calculate_energy_charge_paise(units_dec, plan)

    # Check TNPDCL powerloom free-quota waiver (e.g. 0-1,000 units @ Rs 0 -> Fixed & E-Tax = Rs 0)
    ordered_slabs = sorted(plan.slabs, key=lambda s: s.min_unit)
    if (
        energy_paise == 0
        and ordered_slabs
        and ordered_slabs[0].rate_paise_per_unit == 0
        and (ordered_slabs[0].max_unit is None or units_dec <= Decimal(ordered_slabs[0].max_unit))
    ):
        return {
            "energy_paise": 0,
            "fixed_paise": 0,
            "tax_paise": 0,
            "fppca_paise": 0,
            "overhead_paise": 0,
            "net_bill_paise": 0,
        }

    fixed_rate = getattr(plan, "fixed_charge_per_kw_month_paise", 0) or 0
    tax_bps = getattr(plan, "electricity_tax_bps", 0) or 0
    fppca_rate = getattr(plan, "fppca_paise_per_unit", 0) or 0
    tax_on_gross = bool(getattr(plan, "tax_on_gross", False))
    legacy_overhead = getattr(plan, "overhead_per_kw_paise", 0) or 0

    if fixed_rate > 0:
        # Pro-rate monthly fixed rate per kW across actual billing days (30-day nominal month)
        fixed_dec = kw_dec * Decimal(fixed_rate) * Decimal(days) / Decimal(30)
        fixed_paise = int(fixed_dec.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    else:
        fixed_paise = 0

    fppca_paise = int((units_dec * Decimal(fppca_rate)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    tax_base = energy_paise + fppca_paise
    if tax_on_gross and fixed_rate > 0:
        # TNPDCL E-Tax = 5% of (CC + RDFC), where RDFC uses ceil(recorded_demand_kw) if given, else sanctioned_kw
        if recorded_demand_kw is not None and Decimal(str(recorded_demand_kw)) > 0:
            rdfc_kw = Decimal(int(Decimal(str(recorded_demand_kw)).to_integral_value(rounding="ROUND_CEILING")))
            rdfc_paise = int((rdfc_kw * Decimal(fixed_rate) * Decimal(days) / Decimal(30)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        else:
            rdfc_paise = fixed_paise
        tax_base += rdfc_paise

    tax_paise = (
        int((Decimal(tax_base) * Decimal(tax_bps) / Decimal(10000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        if tax_bps > 0
        else 0
    )

    overhead_paise = fixed_paise + tax_paise + fppca_paise
    if fixed_rate == 0 and tax_bps == 0 and fppca_rate == 0 and legacy_overhead > 0:
        cycle_scale = Decimal(days) / Decimal(max(1, plan.billing_cycle_days))
        overhead_paise = int((kw_dec * Decimal(legacy_overhead) * cycle_scale).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    net_bill_paise = energy_paise + overhead_paise
    return {
        "energy_paise": energy_paise,
        "fixed_paise": fixed_paise,
        "tax_paise": tax_paise,
        "fppca_paise": fppca_paise,
        "overhead_paise": overhead_paise,
        "net_bill_paise": net_bill_paise,
    }
