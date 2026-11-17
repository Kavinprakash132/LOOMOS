# REST API Design Specification (v3)

**Base Path:** `/api/v1` | **Framework:** FastAPI + Pydantic v2 + JWT Bearer Auth

---

## 1. Auth, Setup & Settings
- `GET /api/v1/setup/status` — Whether initial Owner + shed setup is completed (locks `/setup` once complete).
- `POST /api/v1/setup/initialize` — Atomically creates Step 1 Owner account, unit settings, Step 2 `N` looms, and optional Step 3 CSV/demo seed.
- `POST /api/v1/auth/login` & `GET /api/v1/auth/me` — JWT auth (`OWNER` / `SUPERVISOR`, `preferred_lang`).
- `GET/PATCH /api/v1/settings` — Unit name, default language (`en`/`ta`), shift count, entry mode, sanctioned kW.
- `GET/POST/PATCH /api/v1/eb-tariffs` — Editable tariff plans & slabs (seeded with TANGEDCO LA3A2).

## 2. Masters & Audit Logs (`OWNER` write; soft-archive / soft-delete only)
- `GET/POST/PATCH /api/v1/looms` & `POST /api/v1/looms/bulk` — Add/edit/archive looms (`is_active`).
- `GET/POST/PATCH /api/v1/weavers` & `POST /api/v1/weavers/{id}/wage-rules` — 4 dated wage modes (`PER_METRE`, `PER_LOOM_SHIFT`, `PER_SHIFT_ATTENDANCE`, `FIXED_WEEKLY`); soft-delete logged to `audit_logs`.
- `GET/POST/PATCH /api/v1/traders`, `/fabric-sorts` (incl. `agreed_rate_paise`, `expected_weft_kg_per_100m`, `wastage_pct`), `/stop-reasons` (incl. `is_power_cut`).
- `GET /api/v1/audit-logs` — Filterable immutable history (`entity_type`, `action`, `changed_by`, date range).

## 3. Beams, Weft Wastage & Shift Floor Entry
- `GET/POST /api/v1/beams` — Receive warp beam, compute `woven_metres`, `remaining_metres`, `weft_kg_received`, `expected_weft_kg`, **weft wastage % flag**, and **Beam Finish ETA**.
- `POST /api/v1/beams/{beam_id}/weft-receipts` & `DELETE /api/v1/weft-receipts/{id}` *(soft delete + audit)*.
- `POST /api/v1/looms/{loom_id}/load-beam` & `/unload-beam`.
- `GET /api/v1/shifts?date=YYYY-MM-DD&shift_no=1|2` — Auto-carries forward previous shift Weaver & Active Beam for all `N` active looms.
- `POST /api/v1/shifts/bulk` — Atomic save (supports mid-shift beam split & `client_uuid` idempotency); computes `power_cut_mins` and runs `z-score`/IQR outlier checks.

## 4. Wages, Advances, Deliveries & Rate Checker (`OWNER` only; soft-delete + audit)
- `GET/POST /api/v1/advances` & `DELETE /api/v1/advances/{id}` *(soft delete + reason + audit)*.
- `POST /api/v1/payslips/preview` & `/finalize` & `DELETE /api/v1/payslips/{id}` *(soft-delete void + audit)*; `GET /api/v1/payslips/{id}/export?format=csv|xlsx|pdf&lang=en|ta`.
- `GET/POST /api/v1/deliveries` & `DELETE /api/v1/deliveries/{id}` *(soft delete + audit)* — Runs **Trader Rate Checker** (`applied_rate_paise < sort.agreed_rate_paise`).
- `GET/POST /api/v1/trader-payments` & `DELETE /api/v1/trader-payments/{id}` *(soft delete + audit)*.

## 5. Quality Inspection (`/inspect`)
- `GET /api/v1/inspections/reference-samples` — Lists built-in samples explicitly flagged **`is_reference_sample: true` ("AITEX Reference Sample (demo only)")**.
- `GET /api/v1/inspections/model-card` — Held-out test split Precision, Recall, F1, Confusion Matrix, and failure cases.
- `POST /api/v1/inspections` — Runs ONNX + Grad-CAM overlay on uploaded photo (or reference sample); returns prediction, confidence, uncertainty flag, and heatmap URL.
- `PATCH /api/v1/inspections/{id}/review` — Saves **every** reviewed photo (`CONFIRMED_DEFECT` or `CONFIRMED_CLEAN` + `reviewed_label`) into `LOOMOS-Shed` storage.

## 6. Analytics, EB Predictor, Imports & Exports (`OWNER` only)
- `GET /api/v1/dashboard/summary` — Live DB totals, power-cut impact, active anomalies, open rate/wastage alerts.
- `GET /api/v1/analytics/weekly-forecast` — **Holt's Exponential Smoothing** vs **Naive baseline** (back-test MAE/MAPE).
- `GET/POST /api/v1/eb/readings`, `/eb/bills`, `GET /api/v1/eb/prediction` — DB-driven slab forecast adjusted for logged `Power Cut` duration + estimated metres/₹ lost to power cuts.
- `POST /api/v1/import/history` & `GET /api/v1/import/templates/{type}` — Historical CSV upload & blank templates.
- `GET /api/v1/exports/{entity}?format=csv|xlsx|pdf` & `GET /api/v1/backup/download` — Step 2 CSV + full DB backup; Step 4 Excel/PDF polish.
- `POST /api/v1/analytics/what-if` *(Step 4 optional, only if time remains)*.
