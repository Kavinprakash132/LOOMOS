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
