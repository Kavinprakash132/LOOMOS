"""Tests for trader rate-cut checker, ledger balances, EB breakdown, CSV BOM exports & SQLite backup."""

from __future__ import annotations

import sqlite3
import tempfile
from decimal import Decimal
from pathlib import Path
from fastapi.testclient import TestClient

from app.models.core import EbTariffPlan, EbTariffSlab
from app.services.eb_calculator import calculate_bill_breakdown_paise


def test_eb_component_breakdown_and_cycle_proration() -> None:
    plan = EbTariffPlan(
        name="Test Composed Plan",
        billing_cycle_days=60,
        overhead_per_kw_paise=0,
        fixed_charge_per_kw_month_paise=11000,  # ₹110/kW/month
        electricity_tax_bps=500,  # 5%
        fppca_paise_per_unit=0,
        slabs=[
            EbTariffSlab(min_unit=0, max_unit=1000, rate_paise_per_unit=0),
            EbTariffSlab(min_unit=1001, max_unit=1500, rate_paise_per_unit=415),
            EbTariffSlab(min_unit=1501, max_unit=None, rate_paise_per_unit=530),
        ],
    )
    bd = calculate_bill_breakdown_paise(Decimal("6407"), plan, sanctioned_kw=Decimal("10.00"), billing_days=60)
    assert bd["energy_paise"] == 2808210
    assert bd["fixed_paise"] == 220000  # 10 kW * 11000 * 60/30
    assert bd["tax_paise"] == 140411  # round(2808210 * 0.05)
    assert bd["net_bill_paise"] == bd["energy_paise"] + bd["fixed_paise"] + bd["tax_paise"]


def test_deliveries_rate_checker_ledger_csv_bom_and_sqlite_backup(client: TestClient, initialized_owner) -> None:
    headers, _ = initialized_owner
    trader = client.post("/api/v1/traders", headers=headers, json={"company_name": "Somanur Looms"}).json()
    sort_obj = client.post(
        "/api/v1/fabric-sorts",
        headers=headers,
        json={"sort_name": "40s Grey Gada", "reed": 84, "pick": 76, "width_in": "48.00", "agreed_rate_paise": 600},
    ).json()

    # Delivery with 50 paise rate cut (550 paise applied vs 600 paise agreed) over 1000m -> ₹500 shortfall!
    d_res = client.post(
        "/api/v1/deliveries",
        headers=headers,
        json={
            "trader_id": trader["id"],
            "challan_no": "CH-501",
            "delivery_date": "2026-11-16",
            "items": [
                {
                    "sort_id": sort_obj["id"],
                    "pieces": 10,
                    "metres": "1000.00",
                    "applied_rate_paise": 550,
                    "production_start_date": "2026-11-09",
                    "production_end_date": "2026-11-15",
                }
            ],
        },
    )
    assert d_res.status_code == 201, d_res.text
    d_body = d_res.json()
    assert d_body["total_amount_paise"] == 550000
    assert d_body["total_underpayment_paise"] == 50000
    assert d_body["has_rate_cut"] is True

    alerts = client.get("/api/v1/alerts?status=OPEN", headers=headers).json()
    assert any(a["alert_type"] == "RATE_UNDERPAYMENT" and "CH-501" in a["message"] for a in alerts)

    # Record payment of ₹4000 (400000 paise) + ₹200 shortage deduction -> Receivable balance = ₹5500 - ₹4000 - ₹200 = ₹1300 (130000)
    pay = client.post(
        "/api/v1/payments",
        headers=headers,
        json={
            "trader_id": trader["id"],
            "payment_date": "2026-11-17",
            "amount_paise": 400000,
            "shortage_deduction_paise": 20000,
            "reference": "NEFT-8841",
        },
    )
    assert pay.status_code == 201
    ledger = client.get("/api/v1/traders/ledger", headers=headers).json()
    assert ledger[0]["balance_paise"] == 130000
    assert ledger[0]["underpayment_paise"] == 50000

    # EB reading + EB bill creation & post-setup CSV import
    assert client.post(
        "/api/v1/eb-readings",
        headers=headers,
        json={"reading_date": "2026-11-10", "kwh_total": "14200.50"},
    ).status_code == 201
    eb_res = client.post(
        "/api/v1/eb-bills",
        headers=headers,
        json={
            "period_start": "2026-08-30",
            "period_end": "2026-10-29",
            "units_consumed": "6407",
            "net_bill_paise": 3255400,
            "total_power_cut_mins": 90,
        },
    )
    assert eb_res.status_code == 201
    assert eb_res.json()["energy_paise"] == 2994955  # 2024-2026 live TNPDCL LA3A2: 500*445 + 4907*565

    # UTF-8 BOM CSV export check
    csv_res = client.get("/api/v1/exports/csv/deliveries", headers=headers)
    assert csv_res.status_code == 200
    assert csv_res.content.startswith(b"\xef\xbb\xbf")
    assert "CH-501" in csv_res.content.decode("utf-8-sig")

    # SQLite hot backup download returns a valid SQLite database
    bak = client.get("/api/v1/backup/sqlite", headers=headers)
    assert bak.status_code == 200
    assert bak.content.startswith(b"SQLite format 3\x00")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        tf.write(bak.content)
        tf_path = Path(tf.name)
    try:
        conn = sqlite3.connect(str(tf_path))
        cnt = conn.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0]
        conn.close()
        assert cnt == 1
    finally:
        tf_path.unlink(missing_ok=True)


def test_post_setup_csv_imports_calendar_expenses_and_supervisor_rbac(client: TestClient, initialized_owner) -> None:
    headers, _ = initialized_owner

    # 1. Shed calendar holiday override
    cal = client.put(
        "/api/v1/calendar/2026-11-18",
        headers=headers,
        json={"is_working_day": False, "planned_shifts": 0, "note": "Local temple festival"},
    )
    assert cal.status_code == 200 and cal.json()["is_working_day"] is False

    # 2. Expenses create & soft delete
    exp = client.post(
        "/api/v1/expenses",
        headers=headers,
        json={"expense_date": "2026-11-17", "category": "Pirn Windings & Oil", "amount_paise": 125000, "note": "2L spindle oil"},
    )
    assert exp.status_code == 201
    del_exp = client.request("DELETE", f"/api/v1/expenses/{exp.json()['id']}", headers=headers, json={"reason": "Duplicate bill"})
    assert del_exp.status_code == 200 and del_exp.json()["is_deleted"] is True

    # 3. Post-setup historical EB bills & deliveries CSV upload
    eb_csv = "period_start,period_end,units_consumed,net_bill_rs,power_cut_mins,notes\n2025-08-30,2025-10-29,6407,32554.00,60,P2\n"
    imp_eb = client.post("/api/v1/imports/eb-bills-csv", headers=headers, files={"file": ("eb.csv", eb_csv.encode("utf-8"), "text/csv")})
    assert imp_eb.status_code == 200 and imp_eb.json()["imported_eb_bills"] == 1

    del_csv = "delivery_date,trader_name,challan_no,sort_name,metres,rate_rs_per_m\n2025-10-18,Sri Textiles,CH-09,40s Grey,6150.00,6.00\n"
    imp_del = client.post("/api/v1/imports/deliveries-csv", headers=headers, files={"file": ("del.csv", del_csv.encode("utf-8"), "text/csv")})
    assert imp_del.status_code == 200 and imp_del.json()["imported_deliveries"] == 1

    # 4. Supervisor RBAC check on finance, exports, and backup
    client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"full_name": "Floor Sup", "username": "sup2", "password": "supPassword1", "role": "SUPERVISOR", "preferred_lang": "en"},
    )
    sup_tok = client.post("/api/v1/auth/login", json={"username": "sup2", "password": "supPassword1"}).json()["access_token"]
    sup_h = {"Authorization": f"Bearer {sup_tok}"}
    assert client.get("/api/v1/deliveries", headers=sup_h).status_code == 403
    assert client.get("/api/v1/expenses", headers=sup_h).status_code == 403
    assert client.get("/api/v1/exports/csv/shifts", headers=sup_h).status_code == 403
    assert client.get("/api/v1/backup/sqlite", headers=sup_h).status_code == 403
    # Supervisor CAN read shifts, beams & prefill
    assert client.get("/api/v1/beams", headers=sup_h).status_code == 200
    assert client.get("/api/v1/shifts/prefill", headers=sup_h).status_code == 200
