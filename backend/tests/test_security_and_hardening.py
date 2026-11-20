"""Security, RBAC confidentiality, rate limiting, and regression tests for LOOMOS hardening."""

from __future__ import annotations

from datetime import date
from fastapi.testclient import TestClient


def _create_supervisor_headers(client: TestClient, owner_headers: dict[str, str], username: str = "sup_sec") -> dict[str, str]:
    res = client.post(
        "/api/v1/auth/users",
        headers=owner_headers,
        json={"full_name": "Supervisor Sec", "username": username, "password": "supPassword1", "role": "SUPERVISOR"},
    )
    assert res.status_code == 201, res.text
    tok = client.post("/api/v1/auth/login", json={"username": username, "password": "supPassword1"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def test_security_headers_and_signed_inspection_images(client: TestClient, initialized_owner) -> None:
    owner_headers, _ = initialized_owner
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.headers.get("x-content-type-options") == "nosniff"
    assert health.headers.get("x-frame-options") == "DENY"

    card = client.get("/api/v1/inspections/model-card", headers=owner_headers).json()
    sample_id = card["samples"][0]["id"]
    insp = client.post("/api/v1/inspections/analyze", headers=owner_headers, data={"sample_id": sample_id}).json()

    # Unsigned anonymous access MUST be rejected (401)
    unsigned_url = insp["raw_image_url"].split("?")[0]
    assert client.get(unsigned_url).status_code == 401
    assert client.get(f"{unsigned_url}?sig=forgedsig123").status_code == 401

    # Signed URL returned to authenticated user works for <img> tags
    assert "?sig=" in insp["raw_image_url"]
    assert client.get(insp["raw_image_url"]).status_code == 200
    # Direct Bearer JWT without sig also works
    assert client.get(unsigned_url, headers=owner_headers).status_code == 200


def test_supervisor_financial_isolation_alerts_and_wages(client: TestClient, initialized_owner) -> None:
    owner_headers, _ = initialized_owner
    sup_headers = _create_supervisor_headers(client, owner_headers, "sup_iso")

    # Create weaver with private wage rule
    w = client.post(
        "/api/v1/weavers",
        headers=owner_headers,
        json={"full_name": "Murugan", "wage_mode": "PER_LOOM_SHIFT", "rate_paise": 7500},
    ).json()
    assert len(w["wage_rules"]) == 1

    # Owner sees wage_rules; Supervisor MUST see empty wage_rules
    owner_weavers = client.get("/api/v1/weavers", headers=owner_headers).json()
    sup_weavers = client.get("/api/v1/weavers", headers=sup_headers).json()
    assert len(owner_weavers[0]["wage_rules"]) == 1
    assert sup_weavers[0]["wage_rules"] == []

    # Trigger a confidential RATE_UNDERPAYMENT alert
    trader = client.post("/api/v1/traders", headers=owner_headers, json={"company_name": "Secret Trader"}).json()
    sort_obj = client.post(
        "/api/v1/fabric-sorts",
        headers=owner_headers,
        json={"sort_name": "SecSort", "reed": 60, "pick": 60, "width_in": "50.00", "agreed_rate_paise": 700},
    ).json()
    d = client.post(
        "/api/v1/deliveries",
        headers=owner_headers,
        json={
            "trader_id": trader["id"],
            "challan_no": "CH-SEC-1",
            "delivery_date": date.today().isoformat(),
            "items": [{"sort_id": sort_obj["id"], "pieces": 10, "metres": "1000.00", "applied_rate_paise": 600}],
        },
    )
    assert d.status_code == 201

    owner_alerts = client.get("/api/v1/alerts?status=OPEN", headers=owner_headers).json()
    rate_alerts = [a for a in owner_alerts if a["alert_type"] == "RATE_UNDERPAYMENT"]
    assert len(rate_alerts) >= 1

    # Supervisor MUST NOT see RATE_UNDERPAYMENT in /alerts or /dashboard/floor
    sup_alerts = client.get("/api/v1/alerts?status=OPEN", headers=sup_headers).json()
    assert all(a["alert_type"] != "RATE_UNDERPAYMENT" for a in sup_alerts)

    sup_floor = client.get("/api/v1/dashboard/floor", headers=sup_headers).json()
    assert all(a["alert_type"] != "RATE_UNDERPAYMENT" for a in sup_floor["open_alerts"])

    # Supervisor MUST NOT be allowed to dismiss Owner's financial alert
    dismiss = client.patch(
        f"/api/v1/alerts/{rate_alerts[0]['id']}",
        headers=sup_headers,
        json={"status": "DISMISSED"},
    )
    assert dismiss.status_code == 403


def test_duplicate_payslip_blocked_and_csv_formula_sanitized(client: TestClient, initialized_owner) -> None:
    owner_headers, _ = initialized_owner
    w = client.post(
        "/api/v1/weavers",
        headers=owner_headers,
        json={"full_name": "Selvam", "wage_mode": "FIXED_WEEKLY", "rate_paise": 350000},
    ).json()
    today = date.today().isoformat()
    payload = {
        "period_start": today,
        "period_end": today,
        "items": [
            {
                "weaver_id": w["id"],
                "wage_mode_snapshot": "FIXED_WEEKLY",
                "units_worked": "0.14",
                "rate_paise_snapshot": 350000,
                "gross_paise": 50000,
                "advance_deducted_paise": 0,
                "defect_deduction_paise": 0,
            }
        ],
    }
    first = client.post("/api/v1/payslips/finalize", headers=owner_headers, json=payload)
    assert first.status_code == 201
    dup = client.post("/api/v1/payslips/finalize", headers=owner_headers, json=payload)
    assert dup.status_code == 409

    # CSV formula injection prevention on expense note
    client.post(
        "/api/v1/expenses",
        headers=owner_headers,
        json={"expense_date": today, "category": "Spares", "amount_paise": 5000, "note": "=CMD|' /C calc'!A0"},
    )
    csv_res = client.get("/api/v1/exports/csv/expenses", headers=owner_headers)
    assert csv_res.status_code == 200
    text = csv_res.content.decode("utf-8-sig")
    assert "'=CMD|' /C calc'!A0" in text

    # Malformed CSV import returns 422 cleanly (not 500)
    bad_csv = client.post(
        "/api/v1/imports/eb-bills-csv",
        headers=owner_headers,
        files={"file": ("bad.csv", b"period_start,period_end,units_consumed,net_bill_rs\nnot-a-date,2026-01-01,100,abc\n", "text/csv")},
    )
    assert bad_csv.status_code == 422

    # Negative units_kwh on EB calculator rejected cleanly (422)
    assert client.get("/api/v1/analytics/eb-calculate?units_kwh=-50", headers=owner_headers).status_code == 422


def test_login_rate_limiting(client: TestClient, initialized_owner) -> None:
    for _ in range(15):
        r = client.post("/api/v1/auth/login", json={"username": "bruteforce_user", "password": "wrongpassword"})
        assert r.status_code == 401
    blocked = client.post("/api/v1/auth/login", json={"username": "bruteforce_user", "password": "wrongpassword"})
    assert blocked.status_code == 429
    assert "retry-after" in {k.lower() for k in blocked.headers.keys()}
