# LOOMOS — Engineering & AI Agent Guide (`AGENTS.md`)

> Read this file completely before modifying code in this repository. It captures the architecture, domain invariants, security rules, and verification commands for **LOOMOS** (Mobile-First Powerloom Job-Work Production, Analytics & Cloth Defect Inspection System).

---

## 1. Architecture Overview

- **Backend:** FastAPI + SQLAlchemy 2 + Alembic + SQLite (WAL mode) + ONNX Runtime + Google GenAI (`google-genai`), located in `backend/`.
- **Frontend:** React 18 + TypeScript + Vite 6 + Tailwind CSS v4 + Lucide Icons, located in `frontend/`.
- **Deployment:** Single multi-stage `Dockerfile` (builds React SPA → served by FastAPI/Uvicorn behind Caddy 2 reverse proxy with automatic HTTPS in `deploy/azure/`).
- **CI/CD:** `.github/workflows/ci-deploy.yml` runs `npm ci && npm run build` and `pytest -v` on every PR and push to `main`, and automatically deploys verified `main` commits to Azure VM.

---

## 2. Repository Map

| Path | Responsibility |
|---|---|
| `backend/app/main.py` | FastAPI app factory, security/CSP/cache headers, SPA static serving, optional API docs lock (`LOOMOS_ENABLE_API_DOCS`). |
| `backend/app/core/config.py` | Typed `Settings` (`LOOMOS_*` env vars), IST helpers (`today_ist()`, `now_ist()`), private AI allowlist helpers. |
| `backend/app/core/security.py` | Bcrypt password hashing, HS256 JWT tokens, `get_current_user`, `require_owner`. |
| `backend/app/core/audit.py` | Immutable `AuditLog` writer (`record_audit`, `snapshot_fields`, `soft_delete_record`). |
| `backend/app/models/core.py` | All 3NF SQLAlchemy 2 ORM tables (looms, weavers, wage rules, traders, fabric sorts, beams, shifts, advances, payslips, deliveries, EB tariffs/bills, inspections, alerts, audit logs). |
| `backend/app/routers/auth.py` | Login with anti-XFF-spoof multi-tier rate limiting, `/me`, bilingual preference, Owner user management with private-account hiding & demo credential lock. |
| `backend/app/routers/masters.py` | Dynamic N-loom CRUD/bulk creation, weavers + dated wage rules, traders, fabric sorts, redacted audit log view. |
| `backend/app/routers/beams.py` | Warp beam lifecycle (`IN_STOCK` → `RUNNING` → `COMPLETED`), loading/unloading, weft receipts, automatic weft wastage alerts. |
| `backend/app/routers/shifts.py` | Smart O(N_looms) shift prefill (`ROW_NUMBER()`), atomic idempotent batch save (`client_uuid`), attendance, shed calendar. |
| `backend/app/routers/payroll.py` | Advances (`uthaav`), 4-mode payroll preview/finalize (duplicate 409 guard), trilingual printable payslips (`en`/`ta`/`hi`). |
| `backend/app/routers/finance.py` | Grey cloth deliveries with automated trader rate-cut checker (`RATE_UNDERPAYMENT`), trader payments/ledger, expenses, EB readings/bills, RBAC-filtered alerts. |
| `backend/app/routers/inspections.py` | Cloth defect inspection upload (15 MB / 40M px caps), HMAC-signed image URLs (`?sig=...`), MobileNetV3-Large ONNX inference + feathered Grad-CAM overlay. |
| `backend/app/routers/analytics.py` | Beam P50/P75/P25 ETAs, TNPDCL EB slab calculator & kWh/m efficiency anomaly detector, MAD/IQR production anomalies, 5-week walk-forward forecast, XLSX workbook export, expansion simulator. |
| `backend/app/routers/assistant.py` & `backend/app/services/assistant_service.py` | Private multimodal bilingual Gemini AI Copilot strictly gated to `LOOMOS_AI_ALLOWED_USERNAMES`, 10 live read tools, 12 HMAC-signed single-use Confirm/Cancel write proposals, automatic model fallback. |
| `backend/app/routers/data_ops.py` | UTF-8 BOM CSV exports (with formula-injection escaping), CSV imports, SQLite hot backup (scrubbed & `VACUUM`ed for non-allowlisted callers). |
| `backend/data/vision/` | Tracked production ONNX cloth defect model (`winning_model.onnx`, `model_card.json`, 6 held-out sample PNGs). |
| `frontend/src/components/AppShell.tsx` | Responsive desktop sidebar + mobile 3-section bottom nav + lazy-loaded private `AiCopilotDrawer`. |
| `frontend/src/components/AiCopilotDrawer.tsx` | Private slide-over Copilot UI (only rendered when `user.ai_enabled === true`). |
| `frontend/src/i18n/translations.ts` | Bilingual English (`en`) and Tamil (`ta`) UI dictionary; pages also use `tr(en, ta)` from `useAuth()`. |

---

## 3. Non-Negotiable Domain & Engineering Invariants

1. **Integer Paise for ALL Money:** Store and compute currency strictly in integer paise (`100 paise = ₹1.00`) using `Decimal` + `ROUND_HALF_UP`. Never store floats for money.
2. **Zero Hardcoded Rates or Fixed Loom Counts:** Looms are dynamically N-sized (Shuttle/Rapier/Airjet/Waterjet/Projectile). EB tariffs & slabs live in `eb_tariff_plans` / `eb_tariff_slabs`. Wage rules are effective-dated (`effective_from` / `effective_to`).
3. **Soft Delete + Immutable Audit Trail:** Never hard-delete financial records (shifts, advances, payslips, deliveries, payments, expenses, EB bills/tariffs). Always use `soft_delete_record()` and `record_audit()`.
4. **India Standard Time (IST):** Always use `today_ist()` and `now_ist()` from `app.core.config` (never bare `date.today()` for shed calendar dates, because Docker runs in UTC). Display dates in Indian `DD/MM/YYYY` format (`formatDateDMY`).
5. **Bilingual `EN | தமிழ்` Support:** Every new frontend UI label, button, error, or banner must support both English and Tamil via `t(...)` or `tr(en, ta)`.
6. **Mobile-First UX:** Keep controls touch-friendly, keep routes lazy-loaded (`React.lazy`), avoid heavy npm dependencies, and keep camera inputs dual-mode (Camera with `capture="environment"` + Gallery without `capture`).
7. **1 GiB RAM Cloud Budget:** Keep backend dependencies lightweight (no PyTorch or heavy ML runtimes in `backend/requirements.txt`; inference runs strictly via `onnxruntime` CPU).

---

## 4. Non-Negotiable Security Rules

1. **NEVER Commit Secrets or User Data:** Never commit `.env`, API keys, passwords, private SSH keys, `.db` files, `backups/`, or `data_imports/`.
2. **Strict Role Isolation (`OWNER` vs `SUPERVISOR`):**
   - Supervisors may NEVER see financial P&L, `wage_rules`, payroll, deliveries, EB bills, or financial alerts (`RATE_UNDERPAYMENT`, `EB_OVERCHARGE`, `EB_BILL`), nor dismiss financial alerts.
3. **Strict Private AI Copilot Isolation:**
   - `/api/v1/assistant/*` endpoints MUST remain locked behind `require_ai_owner` (`LOOMOS_AI_ALLOWED_USERNAMES`).
   - Private AI-allowlisted accounts MUST remain hidden from non-allowlisted Owners in `GET /api/v1/auth/users`, unmodifiable via `PATCH /api/v1/auth/users/{id}` (`404`), scrubbed & `VACUUM`ed from SQLite backups, and redacted from audit logs/exports.
   - All AI write actions MUST remain two-step HMAC-signed single-use Confirm/Cancel cards — never execute unconfirmed DB mutations from model output.
4. **Input & Export Safety:**
   - Keep CSV formula-injection escaping (`_sanitize_csv_cell`), upload size/pixel caps, HMAC-signed inspection image URLs, anti-XFF-spoof rate limiting, and demo credential vandalism locks intact.

---

## 5. Required Verification Before Every Commit / PR

Run both checks and confirm **zero errors** before committing or opening a PR:

```bash
# 1. Frontend TypeScript check + production bundle build
cd frontend
npm ci
npm run build

# 2. Full Backend Pytest Suite (must pass 100%)
cd ../backend
pytest -v
```

For any new feature or bug fix, add focused tests in `backend/tests/` covering both happy paths and RBAC/security edge cases.
