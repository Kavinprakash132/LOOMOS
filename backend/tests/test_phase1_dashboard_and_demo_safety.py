"""Tests for Phase 1 Dashboard, Partial/Full OEE, Demo DB isolation safety & DEMO banner status."""

from __future__ import annotations

import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from fastapi.testclient import TestClient

from scripts.seed_demo_cli import REAL_DB_PATH, populate_demo_shed


def test_dashboard_partial_utilization_then_full_oee_and_owner_pnl(
    client: TestClient, initialized_owner
) -> None:
    headers, _ = initialized_owner
    looms = client.get("/api/v1/looms", headers=headers).json()
    loom1 = looms[0]  # S-01, 160 RPM

    trader = client.post("/api/v1/traders", headers=headers, json={"company_name": "Murugan Mills"}).json()
    sort_obj = client.post(
        "/api/v1/fabric-sorts",
        headers=headers,
        json={"sort_name": "40s Grey", "reed": 84, "pick": 76, "width_in": "48.00", "agreed_rate_paise": 600},
    ).json()
    weaver = client.post(
        "/api/v1/weavers",
        headers=headers,
        json={"full_name": "Weaver 1", "wage_mode": "PER_LOOM_SHIFT", "rate_paise": 6000},
    ).json()
    beam = client.post(
        "/api/v1/beams",
        headers=headers,
        json={
            "beam_no": "B-OEE",
            "trader_id": trader["id"],
            "sort_id": sort_obj["id"],
            "received_date": date.today().isoformat(),
            "warp_length_m": "500.00",
        },
    ).json()
    client.post(f"/api/v1/beams/{beam['id']}/load", headers=headers, json={"loom_id": loom1["id"]})

    # Shift with 600 planned_mins, 30 power_cut_mins, 30 downtime_mins -> Operating = 540 mins (90.00% Availability)
    # Ideal metres = 160 * 0.0254 / 76 * 540 = 28.8758 m -> Net 26.00 m -> Performance = 90.04%
    today = date.today().isoformat()
    client.post(
        "/api/v1/shifts/batch",
        headers=headers,
        json={
            "entry_date": today,
            "shift_no": 1,
            "rows": [
                {
                    "client_uuid": "oee-test-1",
                    "loom_id": loom1["id"],
                    "weaver_id": weaver["id"],
                    "beam_id": beam["id"],
                    "entry_mode": "DIRECT",
                    "net_metres": "26.00",
                    "planned_mins": 600,
                    "power_cut_mins": 30,
                    "downtime_mins": 30,
                    "defective_metres": "0.00",
                }
            ],
        },
    )

    # Delivery & expense for Owner P&L
    client.post(
        "/api/v1/deliveries",
        headers=headers,
        json={
            "trader_id": trader["id"],
            "challan_no": "CH-OEE",
            "delivery_date": today,
            "items": [{"sort_id": sort_obj["id"], "pieces": 1, "metres": "100.00", "applied_rate_paise": 550}],
        },
    )
    client.post(
        "/api/v1/expenses",
        headers=headers,
        json={"expense_date": today, "category": "Oil", "amount_paise": 5000},
    )

    summary = client.get(f"/api/v1/dashboard/summary?from_date={today}&to_date={today}", headers=headers)
    assert summary.status_code == 200, summary.text
    s = summary.json()
    assert s["availability_pct"] == 90.0
    assert s["quality_recorded"] is False
    assert s["quality_pct"] is None
    assert s["full_oee_pct"] is None
    assert s["utilization_ap_pct"] is not None
    # P&L: revenue 100 * 550 = 55000 - expenses 5000 = 50000 paise
    assert s["financials"]["billed_revenue_paise"] == 55000
    assert s["financials"]["expenses_paise"] == 5000
    assert s["financials"]["net_operating_paise"] == 50000
    assert s["financials"]["total_rate_underpayment_paise"] == 5000  # 100m * 50 paise cut

    # Supervisor RBAC check: floor allowed, financial summary forbidden (403)
    client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"full_name": "Sup", "username": "sup_oee", "password": "supPassword1", "role": "SUPERVISOR"},
    )
    sup_tok = client.post("/api/v1/auth/login", json={"username": "sup_oee", "password": "supPassword1"}).json()["access_token"]
    sup_h = {"Authorization": f"Bearer {sup_tok}"}
    assert client.get(f"/api/v1/dashboard/floor?from_date={today}&to_date={today}", headers=sup_h).status_code == 200
    assert client.get(f"/api/v1/dashboard/summary?from_date={today}&to_date={today}", headers=sup_h).status_code == 403

    # Log confirmed defective metres on Shift 2 (1.30m defect out of 26.00m -> total 52.00m net, 1.30m defect -> 97.50% Quality!)
    client.post(
        "/api/v1/shifts/batch",
        headers=headers,
        json={
            "entry_date": today,
            "shift_no": 2,
            "rows": [
                {
                    "client_uuid": "oee-test-2",
                    "loom_id": loom1["id"],
                    "weaver_id": weaver["id"],
                    "beam_id": beam["id"],
                    "entry_mode": "DIRECT",
                    "net_metres": "26.00",
                    "planned_mins": 600,
                    "power_cut_mins": 30,
                    "downtime_mins": 30,
                    "defective_metres": "1.30",
                }
            ],
        },
    )
    s2 = client.get(f"/api/v1/dashboard/summary?from_date={today}&to_date={today}", headers=headers).json()
    assert s2["quality_recorded"] is True
    assert s2["quality_pct"] == 97.5
    assert s2["full_oee_pct"] is not None


def test_seed_demo_cli_safety_never_touches_production_db(tmp_path: Path) -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    script_path = backend_dir / "scripts" / "seed_demo_cli.py"

    # Attempting --demo or --clean against production loomos.db MUST abort with exit code 2
    for flag in ("--demo", "--clean"):
        proc = subprocess.run(
            [sys.executable, str(script_path), flag, "--db", str(REAL_DB_PATH)],
            cwd=str(backend_dir),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 2
        assert "REFUSING" in proc.stderr

    # Isolated temp demo DB populates 5 shuttle looms, unit_name='LOOMOS', and Pirn Winder cleanly
    import sqlite3

    demo_db = tmp_path / "loomos_demo.db"
    res = populate_demo_shed(demo_db)
    assert res["looms"] == 5 and res["owner_username"] == "welcome123" and demo_db.exists()
    with sqlite3.connect(demo_db) as conn:
        assert conn.execute("SELECT unit_name FROM unit_settings LIMIT 1").fetchone()[0] == "LOOMOS"


def test_delete_unused_loom_and_pirn_winder_role(client: TestClient, initialized_owner) -> None:
    headers, _ = initialized_owner
    # Create an extra unused loom and verify DELETE removes it permanently
    created = client.post(
        "/api/v1/looms",
        headers=headers,
        json={"loom_number": "S-99", "loom_type": "SHUTTLE", "rated_rpm": 165},
    )
    assert created.status_code == 201
    loom_id = created.json()["id"]
    del_res = client.delete(f"/api/v1/looms/{loom_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"
    looms_after = client.get("/api/v1/looms?active_only=false", headers=headers).json()
    assert all(l["id"] != loom_id for l in looms_after)

    # Create a Pirn Winder worker cleanly
    pw = client.post(
        "/api/v1/weavers",
        headers=headers,
        json={
            "full_name": "Kala Pirn Winder",
            "role_type": "PIRN_WINDER",
            "wage_mode": "PER_SHIFT_ATTENDANCE",
            "rate_paise": 35000,
        },
    )
    assert pw.status_code == 201, pw.text
    assert pw.json()["role_type"] == "PIRN_WINDER"


def test_setup_status_reports_demo_mode_flag(client: TestClient, monkeypatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("LOOMOS_DEMO_MODE", "true")
    get_settings.cache_clear()
    try:
        st = client.get("/api/v1/setup/status").json()
        assert st["is_demo_mode"] is True
    finally:
        monkeypatch.delenv("LOOMOS_DEMO_MODE", raising=False)
        get_settings.cache_clear()
