"""Tests for dynamic masters, 4 wage modes, DB-driven EB tariffs, and TANGEDCO slab math."""

from __future__ import annotations

from decimal import Decimal
from fastapi.testclient import TestClient

from app.models.core import EbTariffPlan, EbTariffSlab, ShiftEntry
from app.services.eb_calculator import calculate_energy_charge_paise


def test_db_driven_tangedco_slab_math_matches_real_bills(client: TestClient, initialized_owner) -> None:
    owner_headers, _ = initialized_owner
    plans = client.get("/api/v1/eb-tariffs", headers=owner_headers).json()
    assert len(plans) == 1
    p = plans[0]

    # Reconstruct ORM plan from DB fields and verify all 5 real TANGEDCO bills (0 paise diff)
    orm_plan = EbTariffPlan(
        name=p["name"],
        billing_cycle_days=p["billing_cycle_days"],
        overhead_per_kw_paise=p["overhead_per_kw_paise"],
        effective_from=p["effective_from"],
        slabs=[EbTariffSlab(**{k: s[k] for k in ("min_unit", "max_unit", "rate_paise_per_unit")}) for s in p["slabs"]],
    )
    expected_bills = [
        # (units, exact_energy_paise, rounded_rupees_in_business_plan)
        (8360, 3843300, 38433),
        (6407, 2808210, 28082),
        (2796, 894380, 8944),
        (4346, 1715880, 17159),
        (6361, 2783830, 27838),
    ]
    for units, exact_paise, doc_rupees in expected_bills:
        calc_paise = calculate_energy_charge_paise(Decimal(units), orm_plan)
        assert calc_paise == exact_paise
        assert round(calc_paise / 100) == doc_rupees


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
