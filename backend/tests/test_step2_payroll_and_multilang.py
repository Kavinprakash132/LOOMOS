"""Tests for 4-mode payroll, dated rate history, mid-shift beam dedup, attendance & EN/TA/HI slips."""

from __future__ import annotations

from decimal import Decimal
from fastapi.testclient import TestClient


def _create_supervisor(client: TestClient, owner_headers: dict) -> dict:
    client.post(
        "/api/v1/auth/users",
        headers=owner_headers,
        json={
            "full_name": "Siva",
            "username": "sup_siva",
            "password": "supPassword1",
            "role": "SUPERVISOR",
            "preferred_lang": "en",
        },
    )
    tok = client.post("/api/v1/auth/login", json={"username": "sup_siva", "password": "supPassword1"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_four_mode_payroll_dated_rates_and_trilingual_slips(client: TestClient, initialized_owner) -> None:
    headers, _ = initialized_owner
    looms = client.get("/api/v1/looms", headers=headers).json()
    trader = client.post("/api/v1/traders", headers=headers, json={"company_name": "Kaveri"}).json()
    sort_obj = client.post(
        "/api/v1/fabric-sorts",
        headers=headers,
        json={"sort_name": "30s Grey", "reed": 68, "pick": 64, "width_in": "44.00", "agreed_rate_paise": 600},
    ).json()
    beam1 = client.post(
        "/api/v1/beams",
        headers=headers,
        json={"beam_no": "B1", "trader_id": trader["id"], "sort_id": sort_obj["id"], "received_date": "2026-10-25", "warp_length_m": "800.00"},
    ).json()
    beam2 = client.post(
        "/api/v1/beams",
        headers=headers,
        json={"beam_no": "B2", "trader_id": trader["id"], "sort_id": sort_obj["id"], "received_date": "2026-10-25", "warp_length_m": "800.00"},
    ).json()

    # 1. PER_LOOM_SHIFT weaver with mid-week rate revision (Nov 1-3: ₹60, Nov 4+: ₹75)
    w_loom = client.post(
        "/api/v1/weavers",
        headers=headers,
        json={
            "full_name": "Arumugam",
            "full_name_ta": "ஆறுமுகம்",
            "preferred_slip_lang": "ta",
            "role_type": "WEAVER",
            "wage_mode": "PER_LOOM_SHIFT",
            "rate_paise": 6000,
            "effective_from": "2026-11-01",
        },
    ).json()
    client.post(
        f"/api/v1/weavers/{w_loom['id']}/wage-rules",
        headers=headers,
        json={"wage_mode": "PER_LOOM_SHIFT", "rate_paise": 7500, "effective_from": "2026-11-04"},
    )

    # 2. PER_METRE weaver (₹4.00/m)
    w_metre = client.post(
        "/api/v1/weavers",
        headers=headers,
        json={
            "full_name": "Ramesh Kumar",
            "full_name_hi": "रमेश कुमार",
            "preferred_slip_lang": "hi",
            "role_type": "WEAVER",
            "wage_mode": "PER_METRE",
            "rate_paise": 400,
            "effective_from": "2026-11-01",
        },
    ).json()

    # 3. PER_SHIFT_ATTENDANCE fitter (₹500/shift) with explicit HALF & PRESENT attendance
    w_fitter = client.post(
        "/api/v1/weavers",
        headers=headers,
        json={
            "full_name": "Bala Fitter",
            "preferred_slip_lang": "en",
            "role_type": "FITTER",
            "wage_mode": "PER_SHIFT_ATTENDANCE",
            "rate_paise": 50000,
            "effective_from": "2026-11-01",
        },
    ).json()

    # 4. FIXED_WEEKLY helper (₹2500/week)
    w_helper = client.post(
        "/api/v1/weavers",
        headers=headers,
        json={
            "full_name": "Lakshmi",
            "full_name_ta": "லட்சுமி",
            "preferred_slip_lang": "ta",
            "role_type": "HELPER",
            "wage_mode": "FIXED_WEEKLY",
            "rate_paise": 250000,
            "effective_from": "2026-11-01",
        },
    ).json()

    # Log shifts:
    # Nov 2 Shift 1: Arumugam swaps beams mid-shift on looms[0] (B1: 12m + B2: 15m) -> MUST count as 1 loom-shift @ ₹60 (NOT ₹120!)
    client.post(
        "/api/v1/shifts/batch",
        headers=headers,
        json={
            "entry_date": "2026-11-02",
            "shift_no": 1,
            "rows": [
                {"client_uuid": "pay-s1", "loom_id": looms[0]["id"], "weaver_id": w_loom["id"], "beam_id": beam1["id"], "entry_mode": "DIRECT", "net_metres": "12.00"},
                {"client_uuid": "pay-s2", "loom_id": looms[0]["id"], "weaver_id": w_loom["id"], "beam_id": beam2["id"], "entry_mode": "DIRECT", "net_metres": "15.00"},
                {"client_uuid": "pay-s3", "loom_id": looms[1]["id"], "weaver_id": w_metre["id"], "beam_id": beam1["id"], "entry_mode": "DIRECT", "net_metres": "32.50"},
            ],
        },
    )
    # Nov 5 Shift 1: Arumugam runs 2 looms -> 2 loom-shifts @ ₹75 = ₹150. Total Arumugam = ₹60 + ₹150 = ₹210 (21000 paise)
    client.post(
        "/api/v1/shifts/batch",
        headers=headers,
        json={
            "entry_date": "2026-11-05",
            "shift_no": 1,
            "rows": [
                {"client_uuid": "pay-s4", "loom_id": looms[0]["id"], "weaver_id": w_loom["id"], "beam_id": beam2["id"], "entry_mode": "DIRECT", "net_metres": "28.00"},
                {"client_uuid": "pay-s5", "loom_id": looms[2]["id"], "weaver_id": w_loom["id"], "beam_id": beam1["id"], "entry_mode": "DIRECT", "net_metres": "26.00"},
            ],
        },
    )

    # Attendance for Fitter: Nov 2 PRESENT (1.0), Nov 3 HALF (0.5) -> 1.5 shifts * ₹500 = ₹750 (75000 paise)
    client.post(
        "/api/v1/attendance/batch",
        headers=headers,
        json={"attendance_date": "2026-11-02", "shift_no": 1, "items": [{"weaver_id": w_fitter["id"], "status": "PRESENT"}]},
    )
    client.post(
        "/api/v1/attendance/batch",
        headers=headers,
        json={"attendance_date": "2026-11-03", "shift_no": 1, "items": [{"weaver_id": w_fitter["id"], "status": "HALF"}]},
    )

    # Advance (uthaav) of ₹50 (5000 paise) for Arumugam
    client.post(
        "/api/v1/advances",
        headers=headers,
        json={"weaver_id": w_loom["id"], "advance_date": "2026-11-03", "amount_paise": 5000, "note": "Festival advance"},
    )

    # Preview 7-day period Nov 1..7
    prev = client.post(
        "/api/v1/payslips/preview",
        headers=headers,
        json={"period_start": "2026-11-01", "period_end": "2026-11-07", "deduct_period_advances": True},
    )
    assert prev.status_code == 200, prev.text
    by_id = {x["weaver_id"]: x for x in prev.json()}

    assert Decimal(by_id[w_loom["id"]]["units_worked"]) == Decimal("3.00")
    assert by_id[w_loom["id"]]["gross_paise"] == 21000
    assert by_id[w_loom["id"]]["advance_deducted_paise"] == 5000
    assert by_id[w_loom["id"]]["net_payable_paise"] == 16000

    # Ramesh: 32.50m * 400 paise = 13000 paise
    assert by_id[w_metre["id"]]["gross_paise"] == 13000
    # Bala Fitter: 1.50 shifts * 50000 = 75000 paise
    assert by_id[w_fitter["id"]]["gross_paise"] == 75000
    # Lakshmi Helper: 7 days fixed weekly = 250000 paise
    assert by_id[w_helper["id"]]["gross_paise"] == 250000

    # Finalize and test trilingual printable endpoints (ta / hi / en)
    fin = client.post(
        "/api/v1/payslips/finalize",
        headers=headers,
        json={
            "period_start": "2026-11-01",
            "period_end": "2026-11-07",
            "items": [
                {
                    "weaver_id": r["weaver_id"],
                    "wage_mode_snapshot": r["wage_mode"],
                    "units_worked": r["units_worked"],
                    "rate_paise_snapshot": r["rate_paise"],
                    "gross_paise": r["gross_paise"],
                    "advance_deducted_paise": r["advance_deducted_paise"],
                    "defect_deduction_paise": r["defect_deduction_paise"],
                }
                for r in prev.json()
            ],
        },
    )
    assert fin.status_code == 201
    slips_by_w = {s["weaver_id"]: s for s in fin.json()}

    # Hindi printable slip for Ramesh
    hi_slip = client.get(f"/api/v1/payslips/{slips_by_w[w_metre['id']]['id']}/printable", headers=headers).json()
    assert hi_slip["lang"] == "hi"
    assert "रमेश" in hi_slip["localized_weaver_name"]
    assert "बुनकर" in hi_slip["labels"]["payslip_title"]

    # Tamil printable slip for Arumugam
    ta_slip = client.get(f"/api/v1/payslips/{slips_by_w[w_loom['id']]['id']}/printable", headers=headers).json()
    assert ta_slip["lang"] == "ta"
    assert "ஆறுமுகம்" in ta_slip["localized_weaver_name"]
    assert "கூலி சீட்டு" in ta_slip["labels"]["payslip_title"]

    # Soft-delete voiding preserves slip history & audit trail
    void_slip = client.request(
        "DELETE",
        f"/api/v1/payslips/{slips_by_w[w_helper['id']]['id']}",
        headers=headers,
        json={"reason": "Recalculate with bonus"},
    )
    assert void_slip.status_code == 200 and void_slip.json()["is_deleted"] is True

    # RBAC check: Supervisor blocked from payroll & advances
    sup_headers = _create_supervisor(client, headers)
    assert client.get("/api/v1/advances", headers=sup_headers).status_code == 403
    assert client.get("/api/v1/payslips", headers=sup_headers).status_code == 403
