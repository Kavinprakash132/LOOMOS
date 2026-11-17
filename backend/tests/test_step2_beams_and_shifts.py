"""Tests for beams, loom loading, opening weave/tail waste, weft reconciliation & shift grid."""

from __future__ import annotations

from decimal import Decimal
from fastapi.testclient import TestClient


def test_beam_lifecycle_wastage_alert_and_counter_shift_grid(client: TestClient, initialized_owner) -> None:
    headers, _ = initialized_owner
    looms = client.get("/api/v1/looms", headers=headers).json()
    loom1, loom2 = looms[0], looms[1]

    # Masters: trader, sort (agreed rate 600 paise, weft 10kg/100m, max wastage 5%), weaver
    trader = client.post(
        "/api/v1/traders", headers=headers, json={"company_name": "Murugan Mills"}
    ).json()
    sort_obj = client.post(
        "/api/v1/fabric-sorts",
        headers=headers,
        json={
            "sort_name": "40s Poplin",
            "reed": 84,
            "pick": 76,
            "width_in": "48.00",
            "agreed_rate_paise": 600,
            "expected_weft_kg_per_100m": "10.000",
            "wastage_pct": "5.00",
        },
    ).json()
    weaver = client.post(
        "/api/v1/weavers",
        headers=headers,
        json={"full_name": "Karthik S", "wage_mode": "PER_METRE", "rate_paise": 300},
    ).json()

    # Receive beam A (1000m total, 100m opening woven, 20m tail waste -> 880m usable, 780m remaining)
    beam_a = client.post(
        "/api/v1/beams",
        headers=headers,
        json={
            "beam_no": "B-101",
            "trader_id": trader["id"],
            "sort_id": sort_obj["id"],
            "received_date": "2026-11-10",
            "warp_length_m": "1000.00",
            "opening_woven_m": "100.00",
            "expected_tail_waste_m": "20.00",
            "due_date": "2026-11-25",
        },
    )
    assert beam_a.status_code == 201, beam_a.text
    b_data = beam_a.json()
    assert Decimal(b_data["usable_total_m"]) == Decimal("980.00")
    assert Decimal(b_data["remaining_m"]) == Decimal("880.00")

    # Receive beam B
    beam_b = client.post(
        "/api/v1/beams",
        headers=headers,
        json={
            "beam_no": "B-102",
            "trader_id": trader["id"],
            "sort_id": sort_obj["id"],
            "received_date": "2026-11-10",
            "warp_length_m": "500.00",
        },
    ).json()

    # Load beam A onto loom1; attempting to load beam B onto occupied loom1 must 409
    assert client.post(f"/api/v1/beams/{b_data['id']}/load", headers=headers, json={"loom_id": loom1["id"]}).status_code == 200
    assert client.post(f"/api/v1/beams/{beam_b['id']}/load", headers=headers, json={"loom_id": loom1["id"]}).status_code == 409

    # Issue 15.000 kg weft yarn for beam A
    wr = client.post(
        "/api/v1/weft-receipts",
        headers=headers,
        json={"beam_id": b_data["id"], "received_date": "2026-11-11", "bags": 1, "net_weight_kg": "15.000"},
    )
    assert wr.status_code == 201

    # Save shift batch on COUNTER mode: start=100, end=150 -> net 50.00m + power_cut 45m + defective 1.50m
    stops = client.get("/api/v1/stop-reasons", headers=headers).json()
    power_cut_stop = next(s for s in stops if s["is_power_cut"])

    batch = client.post(
        "/api/v1/shifts/batch",
        headers=headers,
        json={
            "entry_date": "2026-11-12",
            "shift_no": 1,
            "rows": [
                {
                    "client_uuid": "shift-uuid-001",
                    "loom_id": loom1["id"],
                    "weaver_id": weaver["id"],
                    "beam_id": b_data["id"],
                    "entry_mode": "COUNTER",
                    "start_meter": "100.00",
                    "end_meter": "150.00",
                    "power_cut_mins": 45,
                    "downtime_mins": 15,
                    "defective_metres": "1.50",
                    "stop_reason_id": power_cut_stop["id"],
                }
            ],
        },
    )
    assert batch.status_code == 201, batch.text
    assert Decimal(batch.json()[0]["net_metres"]) == Decimal("50.00")

    # Idempotent replay with same client_uuid must NOT duplicate row
    replay = client.post(
        "/api/v1/shifts/batch",
        headers=headers,
        json={
            "entry_date": "2026-11-12",
            "shift_no": 1,
            "rows": [
                {
                    "client_uuid": "shift-uuid-001",
                    "loom_id": loom1["id"],
                    "weaver_id": weaver["id"],
                    "beam_id": b_data["id"],
                    "entry_mode": "COUNTER",
                    "start_meter": "100.00",
                    "end_meter": "150.00",
                }
            ],
        },
    )
    assert replay.status_code == 201
    assert len(client.get("/api/v1/shifts", headers=headers).json()) == 1

    # Prefill for shift 2 carries forward weaver, beam A, and last_end_meter = 150.00
    prefill = client.get("/api/v1/shifts/prefill?entry_date=2026-11-12&shift_no=2", headers=headers).json()
    l1_prefill = next(r for r in prefill["looms"] if r["loom_id"] == loom1["id"])
    assert l1_prefill["default_weaver_id"] == weaver["id"]
    assert l1_prefill["active_beam_id"] == b_data["id"]
    assert Decimal(l1_prefill["last_end_meter"]) == Decimal("150.00")
    assert Decimal(l1_prefill["remaining_beam_m"]) == Decimal("830.00")

    # Test returned_weft_kg reconciliation on unload:
    # 50m woven -> expected 5.000 kg. With 15 kg received and 9.000 kg returned -> 6.000 kg consumed (20% waste > 5%) -> triggers WEFT_WASTAGE Alert!
    unload = client.post(
        f"/api/v1/beams/{b_data['id']}/unload",
        headers=headers,
        json={"unload_reason": "COMPLETED", "returned_weft_kg": "9.000"},
    )
    assert unload.status_code == 200
    u_data = unload.json()
    assert u_data["status"] == "COMPLETED"
    assert Decimal(u_data["weft_consumed_kg"]) == Decimal("6.000")
    assert u_data["wastage_flagged"] is True

    alerts = client.get("/api/v1/alerts?status=OPEN", headers=headers).json()
    assert any(a["alert_type"] == "WEFT_WASTAGE" and "B-101" in a["message"] for a in alerts)

    # Mid-shift beam swap + soft delete audit trail on shifts
    assert client.post(f"/api/v1/beams/{beam_b['id']}/load", headers=headers, json={"loom_id": loom2["id"]}).status_code == 200
    swap = client.post(
        "/api/v1/shifts/batch",
        headers=headers,
        json={
            "entry_date": "2026-11-12",
            "shift_no": 2,
            "rows": [
                {"client_uuid": "s2-swap-a", "loom_id": loom1["id"], "weaver_id": weaver["id"], "beam_id": b_data["id"], "entry_mode": "DIRECT", "net_metres": "10.00"},
                {"client_uuid": "s2-swap-b", "loom_id": loom1["id"], "weaver_id": weaver["id"], "beam_id": beam_b["id"], "entry_mode": "DIRECT", "net_metres": "12.00"},
            ],
        },
    )
    assert swap.status_code == 201
    shift_to_void = swap.json()[0]["id"]
    void_res = client.request("DELETE", f"/api/v1/shifts/{shift_to_void}", headers=headers, json={"reason": "Entered on wrong date"})
    assert void_res.status_code == 200 and void_res.json()["is_deleted"] is True
