"""Tests for dynamic masters, 4 wage modes, DB-driven EB tariffs, and TANGEDCO slab math."""

from __future__ import annotations

from decimal import Decimal
from fastapi.testclient import TestClient

from app.models.core import EbTariffPlan, EbTariffSlab, ShiftEntry
from app.services.eb_calculator import calculate_bill_breakdown_paise, calculate_energy_charge_paise


def test_db_driven_tangedco_slab_math_matches_real_bills(client: TestClient, initialized_owner) -> None:
    owner_headers, _ = initialized_owner
    plans = client.get("/api/v1/eb-tariffs", headers=owner_headers).json()
    assert len(plans) == 1
    p = plans[0]

    # Reconstruct ORM plan from DB fields and verify all live 2024-2026 TNPDCL LA3A2 bills (0 paise diff on CC!)
    orm_plan = EbTariffPlan(
        name=p["name"],
        billing_cycle_days=p["billing_cycle_days"],
        overhead_per_kw_paise=p["overhead_per_kw_paise"],
        fixed_charge_per_kw_month_paise=p["fixed_charge_per_kw_month_paise"],
        electricity_tax_bps=p["electricity_tax_bps"],
        fppca_paise_per_unit=p["fppca_paise_per_unit"],
        tax_on_gross=p["tax_on_gross"],
        effective_from=p["effective_from"],
        slabs=[EbTariffSlab(**{k: s[k] for k in ("min_unit", "max_unit", "rate_paise_per_unit")}) for s in p["slabs"]],
    )
    expected_live_bills = [
        # (units, recorded_demand_kw, exact_cc_paise, exact_tnpdcl_total_rs)
        (79, 1.37, 0, 0),            # Free quota <= 1,000 units: CC, Fixed & E-Tax all waived!
        (1828, 6.23, 407820, 5390),  # Jun 2026 live TNPDCL bill
        (6361, 6.06, 2968965, 32282),  # Apr 2026 (P5)
        (4346, 6.97, 1830490, 20328),  # Feb 2026 (P4)
        (2796, 3.43, 954740, 11116),   # Dec 2025 (P3)
        (6407, 6.64, 2994955, 32554),  # Oct 2025 (P2)
        (8360, 7.62, 4098400, 44146),  # Aug 2025 (P1)
    ]
    for units, rec_kw, exact_cc_paise, live_total_rs in expected_live_bills:
        calc_cc = calculate_energy_charge_paise(Decimal(units), orm_plan)
        assert calc_cc == exact_cc_paise
        bd = calculate_bill_breakdown_paise(
            Decimal(units), orm_plan, sanctioned_kw=Decimal("10.00"), billing_days=60, recorded_demand_kw=Decimal(str(rec_kw))
        )
        assert abs(round(bd["net_bill_paise"] / 100) - live_total_rs) <= 1


def test_all_four_wage_modes_and_dated_rate_history(client: TestClient, initialized_owner) -> None:
    owner_headers, _ = initialized_owner

    modes = [
        ("Weaver Metre", "WEAVER", "PER_METRE", 400),
        ("Weaver LoomShift", "WEAVER", "PER_LOOM_SHIFT", 6000),
        ("Weaver Shift", "WEAVER", "PER_SHIFT_ATTENDANCE", 45000),
        ("Lakshmi Winder", "HELPER", "FIXED_WEEKLY", 250000),
    ]
    created_ids = []
    for name, role_type, mode, rate in modes:
        r = client.post(
            "/api/v1/weavers",
            headers=owner_headers,
            json={
                "full_name": name,
                "full_name_ta": f"{name} தமிழ்",
                "role_type": role_type,
                "wage_mode": mode,
                "rate_paise": rate,
                "effective_from": "2026-10-01",
            },
        )
        assert r.status_code == 201, r.text
        created_ids.append(r.json()["id"])

    # Add a newer wage rule for Weaver LoomShift -> old rule must auto-close cleanly
    upd = client.post(
        f"/api/v1/weavers/{created_ids[1]}/wage-rules",
        headers=owner_headers,
        json={"wage_mode": "PER_LOOM_SHIFT", "rate_paise": 7000, "effective_from": "2026-11-01"},
    )
    assert upd.status_code == 201

    weavers = client.get("/api/v1/weavers", headers=owner_headers).json()
    w2 = next(w for w in weavers if w["id"] == created_ids[1])
    assert len(w2["wage_rules"]) == 2
    newest, older = w2["wage_rules"][0], w2["wage_rules"][1]
    assert newest["rate_paise"] == 7000 and newest["effective_to"] is None
    assert older["rate_paise"] == 6000 and older["effective_to"] == "2026-10-31"


def test_stop_reasons_include_power_cut_and_shift_client_uuid_uniqueness(
    client: TestClient, initialized_owner, db_session_factory
) -> None:
    owner_headers, _ = initialized_owner
    reasons = client.get("/api/v1/stop-reasons", headers=owner_headers).json()
    power_cuts = [r for r in reasons if r["is_power_cut"]]
    assert len(power_cuts) == 1 and power_cuts[0]["code"] == "POWER_CUT"

    # Verify ShiftEntry enforces unique client_uuid at DB constraint level
    TestingSession, _ = db_session_factory
    from datetime import date

    looms = client.get("/api/v1/looms", headers=owner_headers).json()
    w_res = client.post(
        "/api/v1/weavers",
        headers=owner_headers,
        json={"full_name": "Tester", "wage_mode": "PER_LOOM_SHIFT", "rate_paise": 6000},
    ).json()

    db = TestingSession()
    try:
        db.add(
            ShiftEntry(
                client_uuid="uuid-1234",
                loom_id=looms[0]["id"],
                weaver_id=w_res["id"],
                entry_date=date(2026, 11, 17),
                shift_no=1,
                net_metres=Decimal("28.50"),
            )
        )
        db.commit()
        db.add(
            ShiftEntry(
                client_uuid="uuid-1234",
                loom_id=looms[1]["id"],
                weaver_id=w_res["id"],
                entry_date=date(2026, 11, 17),
                shift_no=1,
                net_metres=Decimal("29.00"),
            )
        )
        import sqlalchemy.exc

        try:
            db.commit()
            assert False, "Expected IntegrityError on duplicate client_uuid"
        except sqlalchemy.exc.IntegrityError:
            db.rollback()
    finally:
        db.close()
