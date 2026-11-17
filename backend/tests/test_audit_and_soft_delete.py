"""Tests verifying immutable audit_logs and soft deletes across financial/config records."""

from __future__ import annotations

import json
from fastapi.testclient import TestClient


def test_sort_rate_edit_writes_old_and_new_values_to_audit_log(
    client: TestClient, initialized_owner
) -> None:
    owner_headers, _ = initialized_owner
    sort_res = client.post(
        "/api/v1/fabric-sorts",
        headers=owner_headers,
        json={
            "sort_name": "40s Poplin",
            "warp_count": "40s",
            "weft_count": "40s",
            "reed": 92,
            "pick": 80,
            "width_in": "48.00",
            "agreed_rate_paise": 600,
            "expected_weft_kg_per_100m": "6.500",
            "wastage_pct": "2.50",
        },
    )
    assert sort_res.status_code == 201
    sort_id = sort_res.json()["id"]

    # Update agreed_rate_paise from 600 to 650
    upd = client.patch(
        f"/api/v1/fabric-sorts/{sort_id}",
        headers=owner_headers,
        json={"agreed_rate_paise": 650},
    )
    assert upd.status_code == 200
    assert upd.json()["agreed_rate_paise"] == 650

    logs = client.get("/api/v1/audit-logs?entity_type=fabric_sort&action=UPDATE", headers=owner_headers).json()
    assert len(logs) == 1
    old_vals = json.loads(logs[0]["old_values_json"])
    new_vals = json.loads(logs[0]["new_values_json"])
    assert old_vals["agreed_rate_paise"] == 600
    assert new_vals["agreed_rate_paise"] == 650


def test_soft_delete_on_wage_rule_and_eb_tariff_preserves_history(
    client: TestClient, initialized_owner
) -> None:
    owner_headers, _ = initialized_owner

    # 1. Create weaver with wage rule, then soft-delete the wage rule
    weaver = client.post(
        "/api/v1/weavers",
        headers=owner_headers,
        json={"full_name": "Arun", "wage_mode": "PER_METRE", "rate_paise": 350},
    ).json()
    rule_id = weaver["wage_rules"][0]["id"]

    del_rule = client.request(
        "DELETE",
        f"/api/v1/wage-rules/{rule_id}",
        headers=owner_headers,
        json={"reason": "Entered wrong initial rate"},
    )
    assert del_rule.status_code == 200
    assert del_rule.json()["is_deleted"] is True

    # 2. Create custom EB tariff plan and soft-delete it (cannot delete active one)
    new_plan = client.post(
        "/api/v1/eb-tariffs",
        headers=owner_headers,
        json={
            "name": "Custom Test Tariff",
            "billing_cycle_days": 30,
            "overhead_per_kw_paise": 10000,
            "effective_from": "2026-11-01",
            "slabs": [
                {"min_unit": 0, "max_unit": 500, "rate_paise_per_unit": 0},
                {"min_unit": 501, "max_unit": None, "rate_paise_per_unit": 600},
            ],
        },
    ).json()

    del_plan = client.request(
        "DELETE",
        f"/api/v1/eb-tariffs/{new_plan['id']}",
        headers=owner_headers,
        json={"reason": "Draft tariff not used"},
    )
    assert del_plan.status_code == 200
    assert del_plan.json()["is_deleted"] is True

    # Default list hides soft-deleted plan; include_deleted=true still preserves it
    active_plans = client.get("/api/v1/eb-tariffs", headers=owner_headers).json()
    all_plans = client.get("/api/v1/eb-tariffs?include_deleted=true", headers=owner_headers).json()
    assert len(active_plans) == 1
    assert len(all_plans) == 2

    # Soft-delete entries appear in immutable audit logs
    del_logs = client.get("/api/v1/audit-logs?action=SOFT_DELETE", headers=owner_headers).json()
    assert len(del_logs) == 2
    assert {x["entity_type"] for x in del_logs} == {"wage_rule", "eb_tariff_plan"}
