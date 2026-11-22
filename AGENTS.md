# LOOMOS — Engineering, Domain & AI Agent Brain (`AGENTS.md`)

> Read this file completely before modifying code in this repository. It encodes the full architecture, Tamil Nadu powerloom domain logic, UI/UX taste rules, security invariants, and verification workflow for **LOOMOS** (Mobile-First Powerloom Job-Work Production, Analytics, AI Copilot & Cloth Defect Inspection System).

---

## 1. System Architecture & Production Environment

- **Production Domain:** `https://loomos.tech` (`www.loomos.tech` and legacy domain permanently redirect to `https://loomos.tech` with automatic Let's Encrypt HTTPS + HTTP/3 via Caddy 2).
- **Backend:** FastAPI + SQLAlchemy 2 (`Mapped` / `mapped_column`) + Alembic + SQLite (WAL mode) + ONNX Runtime CPU + Google GenAI (`google-genai`), located in `backend/`.
- **Frontend:** React 18 + TypeScript (strict) + Vite 6 + Tailwind CSS v4 + Lucide React icons, located in `frontend/`.
- **Packaging & Cloud Budget:** Single multi-stage `Dockerfile` builds the React SPA into `backend/static/` and serves everything via Uvicorn behind Caddy (`deploy/azure/`). Target server is a **1 GiB RAM Azure VM** — keep runtime dependencies lean (never add PyTorch, TensorFlow, or heavy bloat).
- **Auto-Migration on Boot:** `backend/scripts/cloud_start.py` runs `alembic upgrade head` automatically on every container start before launching Uvicorn. Every schema change MUST ship with an idempotent Alembic migration.
- **CI/CD:** `.github/workflows/ci-deploy.yml` runs `npm ci && npm run build` and `pytest -v` on every PR and push to `main`, then auto-deploys verified `main` commits to Azure VM.

---

## 2. Repository Map

| Path | Responsibility |
|---|---|
| `backend/app/main.py` | FastAPI app factory, security/CSP/cache headers, SPA static serving, optional API docs lock (`LOOMOS_ENABLE_API_DOCS`). |
| `backend/app/core/config.py` | Typed `Settings` (`LOOMOS_*` env vars), IST helpers (`today_ist()`, `now_ist()`), private AI allowlist helpers. |
| `backend/app/core/security.py` | Bcrypt password hashing, HS256 JWT tokens, `get_current_user`, `require_owner`. |
| `backend/app/core/audit.py` | Immutable `AuditLog` writer (`record_audit`, `snapshot_fields`, `soft_delete_record`). |
| `backend/app/models/core.py` | 3NF SQLAlchemy 2 ORM tables: `User`, `UnitSettings`, `Loom` (with `reed_space_in`, `cloth_width_in`, `default_pick`), `Weaver`, `WageRule`, `Trader`, `FabricSort`, `Beam`, `BeamMount`, `WeftReceipt`, `ShiftEntry`, `Attendance`, `ShedCalendar`, `Advance`, `Payslip`, `Delivery`, `DeliveryItem`, `TraderPayment`, `Expense`, `EbTariffPlan`, `EbTariffSlab`, `EbReading`, `EbBill`, `Inspection`, `DefectPrediction`, `Alert`, `AuditLog`, `AiChatThread`, `AiChatMessage`. |
| `backend/alembic/versions/` | Sequential, idempotent SQLite-safe migrations (always verify single head via `alembic heads`). |
| `backend/app/routers/auth.py` | Login with anti-XFF-spoof multi-tier rate limiting, `/me`, bilingual preference, Owner user management with private-account hiding & demo credential lock. |
| `backend/app/routers/masters.py` | Dynamic N-loom CRUD/bulk creation (`reed_space_in`, `cloth_width_in`, `default_pick`), weavers + dated wage rules, traders, fabric sorts, redacted audit log view. |
| `backend/app/routers/beams.py` | Warp beam lifecycle (`IN_STOCK` → `RUNNING` → `COMPLETED`), loading/unloading, weft receipts, automatic weft wastage alerts. |
| `backend/app/routers/shifts.py` | Smart O(N_looms) shift prefill (`ROW_NUMBER()`), atomic idempotent batch save (`client_uuid`), mid-shift 2nd beam split (`segment_no`), attendance, shed calendar. |
| `backend/app/routers/payroll.py` | Advances (`uthaav`), 4-mode payroll preview/finalize (duplicate 409 guard), trilingual printable payslips (`en`/`ta`/`hi`). |
| `backend/app/routers/finance.py` | Grey cloth deliveries with automated trader rate-cut checker (`RATE_UNDERPAYMENT`), trader payments/ledger, expenses, EB readings/bills, RBAC-filtered alerts. |
| `backend/app/routers/inspections.py` | Cloth defect inspection upload (15 MB / 40M px caps), HMAC-signed image URLs (`?sig=...`), MobileNetV3-Large ONNX inference + feathered Grad-CAM overlay. |
| `backend/app/routers/analytics.py` | Beam P50/P75/P25 ETAs, TNPDCL LA3A2 EB slab calculator & kWh/m efficiency anomaly detector, MAD/IQR production anomalies, 5-week walk-forward forecast, 7-sheet XLSX export, 20–100 loom expansion simulator. |
| `backend/app/routers/assistant.py` & `backend/app/services/assistant_service.py` | Private multimodal bilingual Gemini AI Copilot strictly gated to `LOOMOS_AI_ALLOWED_USERNAMES`, 10 live read tools, 12 HMAC-signed single-use Confirm/Cancel write proposals, model fallback chain, and private server-synced chat history (text-only, 30d / 40-thread auto-pruning, zero tokens stored). |
| `backend/app/routers/data_ops.py` | UTF-8 BOM CSV exports (formula-injection escaped), CSV imports, hot SQLite backup (scrubs private AI users, `ai_chat_*` tables, audit references, then runs `VACUUM` for non-allowlisted callers). |
| `backend/data/vision/` | Tracked production ONNX cloth defect model (`winning_model.onnx`, `model_card.json`, 6 held-out sample PNGs). |
| `frontend/src/context/ToastContext.tsx` | Global floating toast notifications (`useToast().success / error / info`). Every mutation across the app MUST trigger clear toast feedback. |
| `frontend/src/hooks/useLiveRefresh.ts` | Live data-refresh hook listening to `loomos:data-updated`. Every data page subscribes so confirming an AI Copilot action refreshes the screen without a page reload. |
| `frontend/src/components/AppShell.tsx` | Clean flat sidebar (no nested collapsible accordions) + mobile 3-section bottom nav + lazy-loaded private `AiCopilotDrawer`. |
| `frontend/src/components/AiCopilotDrawer.tsx` | Private slide-over Copilot UI (only rendered when `user.ai_enabled === true`) with inline synced History panel, New Chat, Copy on every bubble, Camera/Gallery scan, Confirm/Cancel cards. |
| `frontend/src/i18n/translations.ts` | Bilingual English (`en`) and Tamil (`ta`) UI dictionary; pages also use `tr(en, ta)` from `useAuth()`. |

---

## 3. Powerloom Domain Math & Invariants (Never Break!)

1. **Integer Paise for ALL Money:** Store and compute currency strictly in integer paise (`100 paise = ₹1.00`) using `Decimal` + `ROUND_HALF_UP`. Never store floats for money.
2. **Dynamic Loom Specs:** Never hardcode loom counts or machine types. Looms carry `loom_type` (`SHUTTLE|RAPIER|AIRJET|WATERJET|PROJECTILE`), `rated_rpm`, `reed_space_in`, `cloth_width_in` (optional), and `default_pick` (PPI, optional).
3. **Weaving Physics & OEE:**
   - Ideal shift metres from RPM & Pick (PPI): $\text{Ideal Metres} = \frac{\text{RPM} \times \text{Operating Mins}}{\text{Pick (PPI)} \times 39.3701}$.
   - OEE: Availability = Operating Mins / Planned Mins; Performance = Net Metres / Ideal Metres; Quality = (Net − Defective) / Net. Never fake Quality = 100% when no defects have been recorded (`quality_recorded = False`).
4. **TNPDCL LA3A2 Bi-Monthly Powerloom Electricity Tariff:**
   - Tariffs & unit slabs live in DB (`eb_tariff_plans`, `eb_tariff_slabs`) — zero hardcoded rates.
   - Free quota waiver: when bi-monthly consumption $\le 1{,}000\text{ kWh}$ under TNPDCL LA3A2, energy charge, fixed charge, and electricity tax are waived (`₹0`).
   - Above 1,000 kWh, progressive slabs apply plus fixed demand charge, FPPCA, and electricity tax — verified against real 2024–2026 TNPDCL bills in `backend/tests/test_masters_and_tariffs.py`.
5. **4-Mode Effective-Dated Payroll:** `PER_METRE`, `PER_LOOM_SHIFT`, `PER_SHIFT_ATTENDANCE`, `FIXED_WEEKLY`. Creating a newer dated wage rule auto-closes the previous rule (`effective_to = new_from - 1 day`). Payslips are immutable snapshots with duplicate-period `409` protection.
6. **Trader Rate-Cut & Weft Wastage Alerts:**
   - Deliveries compare `applied_rate_paise` vs `FabricSort.agreed_rate_paise` and auto-raise `RATE_UNDERPAYMENT` alerts on shortfalls.
   - Beam unload / weft receipts compare net weft consumed vs expected `expected_weft_kg_per_100m * woven_m / 100` against `wastage_pct` tolerance.
7. **Soft Delete + Immutable Audit Trail:** Never hard-delete financial records (shifts, advances, payslips, deliveries, payments, expenses, EB bills/tariffs, wage rules). Always use `soft_delete_record()` and `record_audit()`.
8. **India Standard Time (IST):** Always use `today_ist()` and `now_ist()` from `app.core.config` (never bare `date.today()` for shed business dates, since Docker runs in UTC). Display dates in Indian `DD/MM/YYYY` format (`formatDateDMY`).

---

## 4. UI / UX Design System Rules (Strictly Enforced)

The owner prioritizes **calm, clean, professional SaaS design — NEVER cluttered or "option inside options"**:

1. **No Option-Inside-Options:**
   - Do not stack collapsible menus inside sidebars, duplicate switches on every card, or bury common workflows in deep nested drawers.
   - Prefer one global mode switch at the top of a page (e.g., `Direct Metres | Meter Counter` on `TodayShiftPage`) instead of repeating it on every loom card.
2. **Data First, Collapsible Creation Forms:**
   - Pages and Settings tabs open directly onto clean lists/tables of actual shed data, with a single crisp **`+ Add ...`** toggle button that reveals the creation form on demand and auto-closes upon save.
3. **Calm Underline Tabs:** Use consistent underline tabs (`border-b-2 -mb-px`) across multi-tab pages (`TodayShiftPage`, `SettingsMastersPage`, `PayrollPage`, `DeliveriesPage`, `AnalyticsReportsPage`).
4. **Collapsed Optional Complexity:**
   - `PageGuideBanner` stays collapsed by default (toggled via `? Guide`).
   - Rare shift options (beam override, defective metres, mid-shift 2nd beam split) stay tucked inside a single collapsed `More options` toggle per loom card, and a 2nd beam renders cleanly nested inside the *same* loom card (`Part 2 — New Beam`).
5. **Immediate Feedback Everywhere:**
   - Every save, update, mount, unload, finalize, or delete action MUST call `toast.success(...)` or `toast.error(...)` via `useToast()`. Never use `window.alert` or `window.confirm`.
6. **Auto Live Refresh:** Every data page MUST call `useLiveRefresh(loadFn)` so AI Copilot confirmations refresh the visible screen automatically with zero full-page reload.
7. **Bilingual `EN | தமிழ்` Parity:** Every new user-facing string, label, placeholder, and toast MUST support both English and Tamil via `t(...)` or `tr(en, ta)`.
8. **Mobile-First Ergonomics:** Keep routes lazy-loaded (`React.lazy`), touch targets clean, and camera inputs dual-mode (Camera with `capture="environment"` + Gallery without `capture`).

---

## 5. Non-Negotiable Security & Privacy Invariants

1. **NEVER Commit Secrets or Production Data:** Never commit `.env`, API keys, passwords, private SSH keys, card numbers, `.db` files, `backups/`, `data_imports/`, or private production usernames.
2. **Strict Role Isolation (`OWNER` vs `SUPERVISOR`):**
   - Supervisors may NEVER view or edit financial P&L, `wage_rules`, payroll, deliveries, EB bills, or financial alerts (`RATE_UNDERPAYMENT`, `EB_OVERCHARGE`, `EB_BILL`).
3. **Strict Private AI Copilot Isolation:**
   - Every `/api/v1/assistant/*` endpoint (chat, execute, threads CRUD) MUST stay gated behind `require_ai_owner` AND filter thread/message queries by `user_id == owner.id`.
   - Private AI-allowlisted accounts MUST stay hidden from non-allowlisted Owners in `GET /api/v1/auth/users`, unmodifiable (`404`) via `PATCH /api/v1/auth/users/{id}`, and redacted from audit logs/exports.
   - Non-AI SQLite backups (`GET /api/v1/backup/sqlite`) MUST scrub private AI users, wipe `ai_chat_messages` & `ai_chat_threads`, redact AI audit markers, and run `VACUUM` so zero deleted bytes remain in free pages.
   - AI chat history MUST remain text-only (never store base64/binary photos in SQLite), never store reusable `action_token` values, and auto-prune threads > 30 days or > 40 per user.
   - All AI DB mutations MUST use two-step HMAC-signed single-use Confirm/Cancel tokens — never execute writes directly from model output.
4. **Input & Export Hardening:** Preserve CSV formula-injection escaping (`_sanitize_csv_cell`), upload size/pixel caps, HMAC-signed inspection image URLs, anti-XFF-spoof multi-tier login rate limiting, CSP/HSTS headers, and demo credential vandalism locks.

---

## 6. Required Verification Before Every Commit / PR

Run ALL three checks and confirm **zero errors** before committing or opening a PR:

```bash
# 1. Frontend TypeScript strict check + Vite production build
cd frontend
npm ci
npm run build

# 2. Alembic single-head & upgrade verification (when schema changes)
cd ../backend
alembic heads

# 3. Full Backend Pytest Suite (must pass 100%)
pytest -v
```

For any new feature or bug fix, add focused tests in `backend/tests/` covering happy paths, edge cases, and RBAC/security invariants.
