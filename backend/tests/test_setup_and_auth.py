"""Tests for 3-step onboarding, setup lock, JWT auth, RBAC, and EN/Tamil switching."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_setup_flow_creates_owner_and_dynamic_looms_and_locks(client: TestClient) -> None:
    status_before = client.get("/api/v1/setup/status").json()
    assert status_before["is_initialized"] is False
    assert status_before["loom_count"] == 0

    init_payload = {
        "owner_full_name": "Ramasamy",
        "owner_username": "ram_owner",
        "owner_password": "password123",
        "unit_name": "Sri Textiles",
        "location": "Palladam",
        "default_language": "ta",
        "loom_groups": [
            {"count": 35, "prefix": "L-", "start_number": 1, "loom_type": "SHUTTLE", "rated_rpm": 160}
        ],
        "shifts_per_day": 2,
        "default_entry_mode": "DIRECT",
        "seed_mode": "CLEAN",
    }
    res = client.post("/api/v1/setup/initialize", json=init_payload)
    assert res.status_code == 201
    token = res.json()["access_token"]
    assert res.json()["user"]["role"] == "OWNER"
    assert res.json()["user"]["preferred_lang"] == "ta"

    status_after = client.get("/api/v1/setup/status").json()
    assert status_after["is_initialized"] is True
    assert status_after["loom_count"] == 35

    # Must lock permanently after initial setup
    second = client.post("/api/v1/setup/initialize", json=init_payload)
    assert second.status_code == 409

    looms = client.get("/api/v1/looms", headers={"Authorization": f"Bearer {token}"}).json()
    assert len(looms) == 35
    assert looms[0]["loom_number"] == "L-01"
    assert looms[-1]["loom_number"] == "L-35"


def test_setup_csv_history_seed_and_templates(client: TestClient) -> None:
    tpl = client.get("/api/v1/setup/templates/eb_bills")
    assert tpl.status_code == 200
    assert "units_consumed" in tpl.text

    res = client.post(
        "/api/v1/setup/initialize",
        json={
            "owner_full_name": "Owner",
            "owner_username": "owner1",
            "owner_password": "password123",
            "unit_name": "Test Unit",
            "loom_groups": [{"count": 5, "prefix": "L-", "start_number": 1}],
            "seed_mode": "CSV_IMPORT",
            "historical_eb_bills": [
                {
                    "period_start": "2026-02-28",
                    "period_end": "2026-04-26",
                    "units_consumed": "6361",
                    "net_bill_paise": 3228200,
                    "total_power_cut_mins": 120,
                }
            ],
            "historical_deliveries": [
                {
                    "trader_name": "Kaveri Fabrics",
                    "challan_no": "CH-100",
                    "delivery_date": "2026-04-22",
                    "metres": "6200.00",
                    "applied_rate_paise": 600,
                    "sort_name": "40s Grey",
                }
            ],
        },
    )
    assert res.status_code == 201
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    traders = client.get("/api/v1/traders", headers=headers).json()
    sorts = client.get("/api/v1/fabric-sorts", headers=headers).json()
    assert len(traders) == 1 and traders[0]["company_name"] == "Kaveri Fabrics"
    assert len(sorts) == 1 and sorts[0]["agreed_rate_paise"] == 600


def test_rbac_supervisor_cannot_access_financial_or_admin_endpoints(
    client: TestClient, initialized_owner
) -> None:
    owner_headers, _ = initialized_owner

    # Owner creates a Supervisor account
    sup_res = client.post(
        "/api/v1/auth/users",
        headers=owner_headers,
        json={
            "full_name": "Murugan",
            "username": "sup_murugan",
            "password": "supPassword1",
            "role": "SUPERVISOR",
            "preferred_lang": "ta",
        },
    )
    assert sup_res.status_code == 201

    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "sup_murugan", "password": "supPassword1"},
    )
    assert login_res.status_code == 200
    sup_headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    # Supervisor can read looms, stop reasons, settings, and switch language
    assert client.get("/api/v1/looms", headers=sup_headers).status_code == 200
    assert client.get("/api/v1/stop-reasons", headers=sup_headers).status_code == 200
    lang_res = client.patch("/api/v1/auth/me/language", headers=sup_headers, json={"preferred_lang": "en"})
    assert lang_res.status_code == 200
    assert lang_res.json()["preferred_lang"] == "en"

    # Supervisor can read traders & fabric sorts for Beams screen
    assert client.get("/api/v1/traders", headers=sup_headers).status_code == 200
    assert client.get("/api/v1/fabric-sorts", headers=sup_headers).status_code == 200

    # Supervisor is blocked from financial/admin routes
    assert client.get("/api/v1/traders/ledger", headers=sup_headers).status_code == 403
    assert client.post("/api/v1/traders", headers=sup_headers, json={"company_name": "Blocked Traders"}).status_code == 403
    assert (
        client.post(
            "/api/v1/fabric-sorts",
            headers=sup_headers,
            json={"sort_name": "Blocked", "reed": 64, "pick": 60, "width_in": "44", "agreed_rate_paise": 500},
        ).status_code
        == 403
    )
    assert client.get("/api/v1/eb-tariffs", headers=sup_headers).status_code == 403
    assert client.get("/api/v1/audit-logs", headers=sup_headers).status_code == 403
    assert (
        client.post(
            "/api/v1/looms",
            headers=sup_headers,
            json={"loom_number": "X-99"},
        ).status_code
        == 403
    )


def test_bilingual_i18n_bundle(client: TestClient) -> None:
    en = client.get("/api/v1/i18n/en").json()
    ta = client.get("/api/v1/i18n/ta").json()
    assert en["payslip_title"] == "Weekly Weaver Wage Slip"
    assert "கூலி" in ta["payslip_title"]
