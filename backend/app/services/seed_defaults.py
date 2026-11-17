"""Default preset seeders and Step 3 historical CSV / optional demo data helpers."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.audit import record_audit, snapshot_fields
from app.models.core import (
    Delivery,
    DeliveryItem,
    EbBill,
    EbTariffPlan,
    EbTariffSlab,
    FabricSort,
    StopReason,
    Trader,
    WageRule,
    Weaver,
)
from app.schemas.step1 import HistoricalDeliverySeedRow, HistoricalEbSeedRow
from app.services.eb_calculator import calculate_energy_charge_paise

DEFAULT_STOP_REASONS = [
    ("WARP_BREAK", "Warp Break", "பாவு அறுந்து", False),
    ("WEFT_BREAK", "Weft Break", "ஊடு நூல் அறுந்து", False),
    ("MECHANICAL", "Mechanical Fault", "இயந்திர பழுது", False),
    ("POWER_CUT", "Power Cut", "மின்வெட்டு", True),
    ("BEAM_CHANGE", "Beam Change", "பீம் மாற்றம்", False),
    ("NO_WEAVER", "No Weaver / Absent", "நெசவாளர் விடுப்பு", False),
    ("OTHER", "Other Stoppage", "மற்ற காரணம்", False),
]


def seed_default_tariff_and_stops(db: Session, owner_id: int) -> EbTariffPlan:
    """Create the editable TANGEDCO LA3A2 preset and standard stop reasons."""
    plan = EbTariffPlan(
        name="TANGEDCO LA3A2 (Powerloom LT-IIIA2 Preset)",
        billing_cycle_days=60,
        overhead_per_kw_paise=0,
        fixed_charge_per_kw_month_paise=0,
        electricity_tax_bps=500,
        fppca_paise_per_unit=0,
        tax_on_gross=False,
        effective_from=date(2025, 1, 1),
        notes="Editable preset: 0-1000 free, 1001-1500 @ Rs 4.15, >1500 @ Rs 5.30, 5% E-Tax (edit Fixed/FPPCA from bill).",
        created_by=owner_id,
    )
    plan.slabs = [
        EbTariffSlab(min_unit=0, max_unit=1000, rate_paise_per_unit=0),
        EbTariffSlab(min_unit=1001, max_unit=1500, rate_paise_per_unit=415),
        EbTariffSlab(min_unit=1501, max_unit=None, rate_paise_per_unit=530),
    ]
    db.add(plan)
    db.flush()

    record_audit(
        db,
        entity_type="eb_tariff_plan",
        entity_id=plan.id,
        action="CREATE",
        changed_by=owner_id,
        new_values=snapshot_fields(plan, ["name", "billing_cycle_days", "overhead_per_kw_paise"]),
        reason="Initial default preset during setup",
    )

    for code, label_en, label_ta, is_power_cut in DEFAULT_STOP_REASONS:
        db.add(
            StopReason(
                code=code,
                label_en=label_en,
                label_ta=label_ta,
                is_power_cut=is_power_cut,
                created_by=owner_id,
            )
        )
    return plan


def import_historical_seed(
    db: Session,
    *,
    owner_id: int,
    tariff_plan: EbTariffPlan,
    eb_bills: list[HistoricalEbSeedRow],
    deliveries: list[HistoricalDeliverySeedRow],
) -> None:
    """Import user-supplied historical EB bills and delivery records during onboarding."""
    for bill_row in eb_bills:
        energy_paise = calculate_energy_charge_paise(bill_row.units_consumed, tariff_plan)
        overhead_paise = max(0, bill_row.net_bill_paise - energy_paise)
        bill = EbBill(
            tariff_plan_id=tariff_plan.id,
            period_start=bill_row.period_start,
            period_end=bill_row.period_end,
            units_consumed=bill_row.units_consumed,
            energy_paise=energy_paise,
            overhead_paise=overhead_paise,
            net_bill_paise=bill_row.net_bill_paise,
            total_power_cut_mins=bill_row.total_power_cut_mins,
            notes=bill_row.notes,
            created_by=owner_id,
        )
        db.add(bill)
        db.flush()
        record_audit(
            db,
            entity_type="eb_bill",
            entity_id=bill.id,
            action="CREATE",
            changed_by=owner_id,
            new_values=snapshot_fields(bill, ["units_consumed", "net_bill_paise"]),
            reason="Historical onboarding CSV import",
        )

    trader_cache: dict[str, Trader] = {}
    sort_cache: dict[str, FabricSort] = {}

    for del_row in deliveries:
        t_key = del_row.trader_name.strip().lower()
        trader = trader_cache.get(t_key)
        if not trader:
            trader = Trader(company_name=del_row.trader_name.strip(), created_by=owner_id)
            db.add(trader)
            db.flush()
            trader_cache[t_key] = trader

        sort_id = None
        if del_row.sort_name:
            s_key = del_row.sort_name.strip().lower()
            sort_obj = sort_cache.get(s_key)
            if not sort_obj:
                sort_obj = FabricSort(
                    sort_name=del_row.sort_name.strip(),
                    reed=80,
                    pick=72,
                    width_in=Decimal("44.00"),
                    agreed_rate_paise=del_row.applied_rate_paise,
                    created_by=owner_id,
                )
                db.add(sort_obj)
                db.flush()
                sort_cache[s_key] = sort_obj
            sort_id = sort_obj.id

        delivery = Delivery(
            trader_id=trader.id,
            challan_no=del_row.challan_no,
            delivery_date=del_row.delivery_date,
            total_metres=del_row.metres,
            source="CSV_IMPORT",
            created_by=owner_id,
        )
        db.add(delivery)
        db.flush()
        item = DeliveryItem(
            delivery_id=delivery.id,
            sort_id=sort_id,
            pieces=1,
            metres=del_row.metres,
            applied_rate_paise=del_row.applied_rate_paise,
            created_by=owner_id,
        )
        db.add(item)
        db.flush()
        record_audit(
            db,
            entity_type="delivery",
            entity_id=delivery.id,
            action="CREATE",
            changed_by=owner_id,
            new_values=snapshot_fields(delivery, ["challan_no", "delivery_date", "total_metres"]),
            reason="Historical onboarding CSV import",
        )


def seed_optional_sample_data(db: Session, *, owner_id: int, tariff_plan: EbTariffPlan) -> None:
    """Seed clearly labelled synthetic demo masters/history only when requested by the user."""
    today = date.today()
    trader = Trader(company_name="[DEMO] Sri Murugan Textiles", contact_name="Kumar", phone="9876543210", created_by=owner_id)
    db.add(trader)
    sort_obj = FabricSort(
        sort_name="[DEMO] 40s x 40s Grey Gada",
        warp_count="40s Cotton",
        weft_count="40s Cotton",
        reed=84,
        pick=76,
        width_in=Decimal("48.00"),
        agreed_rate_paise=600,
        expected_weft_kg_per_100m=Decimal("6.800"),
        wastage_pct=Decimal("2.50"),
        created_by=owner_id,
    )
    db.add(sort_obj)

    weaver1 = Weaver(
        full_name="[DEMO] Selvam R",
        full_name_ta="[DEMO] செல்வம்",
        role_type="WEAVER",
        phone="9876500001",
        created_by=owner_id,
    )
    helper1 = Weaver(
        full_name="[DEMO] Lakshmi K (Winder)",
        full_name_ta="[DEMO] லட்சுமி (உதவியாளர்)",
        role_type="HELPER",
        phone="9876500002",
        created_by=owner_id,
    )
    db.add_all([weaver1, helper1])
    db.flush()

    db.add_all([
        WageRule(
            weaver_id=weaver1.id,
            wage_mode="PER_LOOM_SHIFT",
            rate_paise=6000,
            effective_from=today - timedelta(days=90),
            created_by=owner_id,
        ),
        WageRule(
            weaver_id=helper1.id,
            wage_mode="FIXED_WEEKLY",
            rate_paise=250000,
            effective_from=today - timedelta(days=90),
            created_by=owner_id,
        ),
    ])

    sample_units = Decimal("6407.00")
    energy_p = calculate_energy_charge_paise(sample_units, tariff_plan)
    db.add(
        EbBill(
            tariff_plan_id=tariff_plan.id,
            period_start=today - timedelta(days=60),
            period_end=today - timedelta(days=1),
            units_consumed=sample_units,
            energy_paise=energy_p,
            overhead_paise=447200,
            net_bill_paise=energy_p + 447200,
            total_power_cut_mins=180,
            notes="[DEMO] Sample bi-monthly EB record",
            created_by=owner_id,
        )
    )
