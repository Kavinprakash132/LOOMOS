"""Tests for Phase 2 Reconciled Vision (Two-Output ONNX + Grad-CAM) & /inspect APIs + Supervisor /beams RBAC."""

from __future__ import annotations

import io
from datetime import date
from fastapi.testclient import TestClient
from PIL import Image


def test_model_card_and_supervisor_beams_and_inspect_access(client: TestClient, initialized_owner) -> None:
    owner_headers, _ = initialized_owner

    mc = client.get("/api/v1/inspections/model-card", headers=owner_headers)
    assert mc.status_code == 200, mc.text
    card = mc.json()
    assert card["winning_model_name"] in {"ResNet-18 + CLAHE", "MobileNetV3-Small + CLAHE"}
    assert len(card["comparison"]) == 2
    assert len(card["samples"]) == 6
    assert card["held_out_split_summary"]["test_total_patches"] > 500

    # Create supervisor and verify /beams reads (traders + fabric-sorts) and /inspect sample access succeed
    sup_res = client.post(
        "/api/v1/auth/users",
        headers=owner_headers,
        json={"full_name": "Sup Vision", "username": "sup_vis", "password": "supPassword1", "role": "SUPERVISOR"},
    )
    assert sup_res.status_code == 201
    sup_tok = client.post("/api/v1/auth/login", json={"username": "sup_vis", "password": "supPassword1"}).json()[
        "access_token"
    ]
    sup_headers = {"Authorization": f"Bearer {sup_tok}"}

    assert client.get("/api/v1/traders", headers=sup_headers).status_code == 200
    assert client.get("/api/v1/fabric-sorts", headers=sup_headers).status_code == 200

    # Sample image loads cleanly
    first_sample = card["samples"][0]
    img_res = client.get(first_sample["image_url"])
    assert img_res.status_code == 200
    assert img_res.headers["content-type"].startswith("image/")


def test_analyze_sample_and_upload_then_review_unlocks_full_oee(client: TestClient, initialized_owner) -> None:
    owner_headers, _ = initialized_owner
    looms = client.get("/api/v1/looms", headers=owner_headers).json()
    loom1 = looms[0]

    trader = client.post("/api/v1/traders", headers=owner_headers, json={"company_name": "Tiruppur Mills"}).json()
    sort_obj = client.post(
        "/api/v1/fabric-sorts",
        headers=owner_headers,
        json={"sort_name": "40s Gada", "reed": 84, "pick": 76, "width_in": "48.00", "agreed_rate_paise": 600},
    ).json()
    weaver = client.post(
        "/api/v1/weavers",
        headers=owner_headers,
        json={"full_name": "Arumugam", "wage_mode": "PER_LOOM_SHIFT", "rate_paise": 6000},
    ).json()
    beam = client.post(
        "/api/v1/beams",
        headers=owner_headers,
        json={
            "beam_no": "BM-V1",
            "trader_id": trader["id"],
            "sort_id": sort_obj["id"],
            "received_date": date.today().isoformat(),
            "warp_length_m": "500.00",
        },
    ).json()

    today = date.today().isoformat()
    client.post(
        "/api/v1/shifts/batch",
        headers=owner_headers,
        json={
            "entry_date": today,
            "shift_no": 1,
            "rows": [
                {
                    "client_uuid": "vis-oee-shift-1",
                    "loom_id": loom1["id"],
                    "weaver_id": weaver["id"],
                    "beam_id": beam["id"],
                    "entry_mode": "DIRECT",
                    "net_metres": "28.00",
                    "planned_mins": 600,
                    "defective_metres": "0.00",
                }
            ],
        },
    )

    # 1) Analyze reference AITEX sample via ONNX + Grad-CAM
    card = client.get("/api/v1/inspections/model-card", headers=owner_headers).json()
    defect_sample = next(s for s in card["samples"] if s["is_defect"])
    an1 = client.post(
        "/api/v1/inspections/analyze",
        headers=owner_headers,
        data={"sample_id": defect_sample["id"], "loom_id": str(loom1["id"]), "beam_id": str(beam["id"])},
    )
    assert an1.status_code == 201, an1.text
    insp1 = an1.json()
    assert insp1["prediction"]["model_version"] == card["model_version"]
    assert insp1["heatmap_image_url"] is not None

    # Raw & heatmap PNGs serve 200 OK
    assert client.get(insp1["raw_image_url"]).status_code == 200
    assert client.get(insp1["heatmap_image_url"]).status_code == 200

    # Confirm defect + push damaged metres into latest shift -> unlocks Full OEE
    rev1 = client.post(
        f"/api/v1/inspections/{insp1['id']}/review",
        headers=owner_headers,
        json={
            "review_status": "CONFIRMED_DEFECT",
            "reviewed_label": "Broken End (Warp)",
            "defective_metres": "1.40",
            "add_to_today_shift": True,
        },
    )
    assert rev1.status_code == 200, rev1.text
    assert rev1.json()["review_status"] == "CONFIRMED_DEFECT"
    assert rev1.json()["shift_entry_id"] is not None

    dash = client.get(f"/api/v1/dashboard/floor?from_date={today}&to_date={today}", headers=owner_headers).json()
    assert dash["quality_recorded"] is True
    assert dash["quality_pct"] == 95.0

    # 2) Analyze uploaded camera bytes and save as CONFIRMED_CLEAN (saves all reviewed photos)
    buf = io.BytesIO()
    Image.new("RGB", (320, 240), color=(215, 215, 215)).save(buf, format="JPEG")
    buf.seek(0)
    an2 = client.post(
        "/api/v1/inspections/analyze",
        headers=owner_headers,
        files={"file": ("shed_photo.jpg", buf.getvalue(), "image/jpeg")},
        data={"loom_id": str(loom1["id"])},
    )
    assert an2.status_code == 201, an2.text
    insp2 = an2.json()
    rev2 = client.post(
        f"/api/v1/inspections/{insp2['id']}/review",
        headers=owner_headers,
        json={"review_status": "CONFIRMED_CLEAN", "reviewed_label": "Clean Cloth", "defective_metres": "0.00"},
    )
    assert rev2.status_code == 200
    assert rev2.json()["review_status"] == "CONFIRMED_CLEAN"

    listed = client.get("/api/v1/inspections", headers=owner_headers).json()
    assert len(listed) >= 2


def test_phase3_analytics_phase4_reports_and_phase5_simulator(client: TestClient, initialized_owner) -> None:
    import subprocess
    import sys
    from pathlib import Path

    owner_headers, _ = initialized_owner
    ov = client.get("/api/v1/analytics/overview", headers=owner_headers)
    assert ov.status_code == 200, ov.text
    ov_json = ov.json()
    assert "beam_etas" in ov_json and "eb_prediction" in ov_json and "weekly_forecast" in ov_json
    assert len(ov_json["weekly_forecast"]["history"]) == 5

    stmt = client.get("/api/v1/analytics/reports/statement", headers=owner_headers)
    assert stmt.status_code == 200
    assert "financials" in stmt.json()

    xlsx = client.get("/api/v1/exports/xlsx/workbook", headers=owner_headers)
    assert xlsx.status_code == 200
    assert xlsx.content[:2] == b"PK"  # valid ZIP/XLSX container

    sim = client.post(
        "/api/v1/analytics/expansion-simulate",
        headers=owner_headers,
        json={"loom_count": 50, "rpm": 165, "efficiency_pct": 85},
    )
    assert sim.status_code == 200, sim.text
    sim_json = sim.json()
    assert sim_json["primary"]["loom_count"] == 50
    assert [p["loom_count"] for p in sim_json["presets"]] == [20, 30, 50, 100]
    assert len(sim_json["sensitivity_matrix"]) == 5

    backend_dir = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "scripts/run_rq3_fewshot.py", "--dry-run", "--db", str(backend_dir / "data" / "loomos.db")],
        cwd=str(backend_dir),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_eb_vs_metres_efficiency_and_meter_fault_detection(client: TestClient, initialized_owner) -> None:
    """Verify EB Bill vs. Metres Produced comparison, meter under-reading alert, and metre-based EB estimator."""
    headers, _ = initialized_owner
    trader = client.post("/api/v1/traders", headers=headers, json={"company_name": "S.M.T Mills"}).json()
    sort_obj = client.post(
        "/api/v1/fabric-sorts",
        headers=headers,
        json={"sort_name": "62x62 50in Grey", "reed": 62, "pick": 62, "width_in": "50.00", "agreed_rate_paise": 600},
    ).json()

    # Seed 4 historical bi-monthly cycles matching real godown pattern: 3 normal (~0.13 kWh/m) + 1 faulty meter (~0.06 kWh/m)
    cycles = [
        ("2025-06-28", "2025-08-30", "2025-08-15", "8360", 4414600, "60350.00", "CH-P1"),
        ("2025-08-30", "2025-10-29", "2025-10-15", "6407", 3255400, "55500.00", "CH-P2"),
        ("2025-10-29", "2025-12-28", "2025-12-15", "2796", 1111600, "46135.00", "CH-P3"),  # Under-reading fault!
        ("2026-02-28", "2026-04-26", "2026-04-15", "6361", 3228200, "49550.00", "CH-P5"),
    ]
    for p_start, p_end, del_dt, kwh, net_p, metres, ch_no in cycles:
        r_eb = client.post(
            "/api/v1/eb-bills",
            headers=headers,
            json={
                "period_start": p_start,
                "period_end": p_end,
                "units_consumed": kwh,
                "net_bill_paise": net_p,
                "total_power_cut_mins": 0,
            },
        )
        assert r_eb.status_code == 201, r_eb.text
        r_del = client.post(
            "/api/v1/deliveries",
            headers=headers,
            json={
                "trader_id": trader["id"],
                "challan_no": ch_no,
                "delivery_date": del_dt,
                "items": [{"sort_id": sort_obj["id"], "pieces": 50, "metres": metres, "applied_rate_paise": 600}],
            },
        )
        assert r_del.status_code == 201, r_del.text

    ov = client.get("/api/v1/analytics/overview", headers=headers)
    assert ov.status_code == 200, ov.text
    eff = ov.json()["eb_efficiency"]
    assert len(eff["periods"]) == 4

    by_end = {p["period_end"]: p for p in eff["periods"]}
    assert by_end["2025-12-28"]["status_flag"] == "METER_UNDER_READING"
    assert by_end["2025-12-28"]["metres_produced"] == 46135.0
    assert by_end["2026-04-26"]["status_flag"] == "NORMAL"
    assert eff["avg_kwh_per_metre"] is not None and 0.11 <= eff["avg_kwh_per_metre"] <= 0.15

    # Live metre-based EB estimator endpoint
    est = client.get("/api/v1/analytics/eb-estimate?metres=50000", headers=headers)
    assert est.status_code == 200, est.text
    ej = est.json()
    assert ej["target_metres"] == 50000.0
    assert 5000.0 <= ej["estimated_kwh"] <= 7500.0
    assert ej["estimated_bill_paise"] > 2500000

    # Workbook must include the new "EB vs Metres" 7th sheet
    import io
    import openpyxl

    wb_res = client.get("/api/v1/exports/xlsx/workbook", headers=headers)
    assert wb_res.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(wb_res.content))
    assert "EB vs Metres" in wb.sheetnames
    assert wb["EB vs Metres"].max_row == 5  # Header + 4 cycles

    # Interactive EB Bill Calculator endpoint: exact match to real TNPDCL P5 (6361 kWh) and Free Quota (79 kWh)
    calc_p5 = client.get(
        "/api/v1/analytics/eb-calculate?units_kwh=6361&sanctioned_kw=10&billing_days=60&recorded_demand_kw=6.06",
        headers=headers,
    )
    assert calc_p5.status_code == 200, calc_p5.text
    cj = calc_p5.json()
    assert cj["energy_paise"] == 2968965
    assert cj["fixed_paise"] == 107000
    assert cj["rounded_payable_rupees"] == 32282
    assert len(cj["slabs"]) == 3

    calc_free = client.get("/api/v1/analytics/eb-calculate?units_kwh=79&sanctioned_kw=10&billing_days=60", headers=headers)
    assert calc_free.status_code == 200
    assert calc_free.json()["rounded_payable_rupees"] == 0
    assert calc_free.json()["free_quota_applied"] is True
