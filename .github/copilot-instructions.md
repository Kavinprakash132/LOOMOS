# GitHub Copilot Repository Instructions — LOOMOS

You are engineering **LOOMOS**, a production, mobile-first web application for Tamil Nadu powerloom job-work sheds (daily shift production, warp beams & weft wastage, 4-mode payroll, trader rate-cut checker, TNPDCL electricity bill analytics, ONNX cloth defect inspection, and a private Gemini AI Copilot).

Read [AGENTS.md](../AGENTS.md) for the complete repository map and domain specification. Follow every rule below strictly on all tasks, code reviews, and pull requests.

## Tech Stack & Constraints
- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2 (`Mapped`/`mapped_column`), Alembic, SQLite (WAL mode), `onnxruntime` CPU, `google-genai`.
- **Frontend:** React 18, TypeScript (strict), Vite 6, Tailwind CSS v4, Lucide icons.
- **Cloud Target:** Single 1 GiB RAM Azure VM (`https://loomos.tech`, Docker + Caddy 2). Keep dependencies light — never add PyTorch, heavy UI frameworks, or unnecessary npm packages.
- **Auto-Deploy:** Every push to `main` passes CI (`npm run build` + `pytest -v`) and auto-deploys to Azure where `backend/scripts/cloud_start.py` runs `alembic upgrade head` automatically.

## Core Engineering & Domain Rules
1. **Money = Integer Paise Only:** Store and calculate currency in integer paise (`100 paise = ₹1.00`) with `Decimal` and `ROUND_HALF_UP`. Never use floating-point numbers for money.
2. **Dynamic Masters, Zero Hardcoding:** Never hardcode loom counts, wage rates, fabric sorts, or TNPDCL slab tariffs. Always read from the database.
3. **India Standard Time (IST):** Use `today_ist()` and `now_ist()` from `app.core.config` for shed dates (Docker runs UTC). Render dates as `DD/MM/YYYY` via `formatDateDMY`.
4. **Soft Delete & Immutable Audit:** Financial and config records are never hard-deleted. Use `soft_delete_record()` and `record_audit()` from `app.core.audit`.
5. **Idempotent Migrations:** Every model/column/table addition in `backend/app/models/core.py` MUST include an idempotent Alembic migration in `backend/alembic/versions/` that checks existing tables/columns before altering and preserves a single Alembic head.
6. **Bilingual `EN | தமிழ்`:** Every user-facing label, placeholder, button, and toast in `frontend/src/` must provide both English and Tamil via `t(...)` or `tr(en, ta)`.

## UI / UX Taste Rules (Calm, Clean SaaS)
- **Zero "option inside options":** Avoid nested collapsible sidebars, redundant per-card toggles, and walls of always-open empty forms.
- **Data First:** Open screens and Settings tabs directly onto data tables/cards with a single collapsible **`+ Add ...`** toggle that auto-closes on save.
- **Consistent Navigation:** Use calm underline tabs (`border-b-2 -mb-px`). Keep `PageGuideBanner` collapsed by default.
- **Always Confirm User Actions:** Call `useToast()` (`toast.success` / `toast.error`) on every save, edit, mount/unload, finalize, or delete action. Never use `window.alert` or `window.confirm`.
- **Live Screen Updates:** Wire `useLiveRefresh(loadFn)` on every data page so confirmed AI Copilot mutations refresh the page behind the drawer without reloading.

## Non-Negotiable Security Rules
- **Zero Secrets in Code/Docs:** Never commit `.env`, API keys, passwords, SSH keys, private production usernames, or `.db` files.
- **Role Isolation:** Supervisors must never access financial P&L, `wage_rules`, payroll, deliveries, EB bills, or financial alerts.
- **Private AI Isolation:** All `/api/v1/assistant/*` routes must use `require_ai_owner` and scope threads/messages by `user_id == owner.id`. Private AI users and `ai_chat_*` tables must remain scrubbed + `VACUUM`ed from non-AI SQLite backups (`backend/app/routers/data_ops.py`) and hidden from non-AI `/auth/users` and audit logs.
- **Confirmed Writes Only:** AI Copilot write tools must only propose HMAC-signed single-use Confirm/Cancel action cards — never mutate the DB directly during model tool calls, and never persist raw `action_token` strings in `ai_chat_messages`.
- **Lean Storage:** Never store raw uploaded images inside SQLite `ai_chat_messages`; preserve 30-day / 40-thread retention pruning.

## Verification Checklist (Mandatory Before Finishing)
1. `cd frontend && npm run build` — must exit `0` with zero TypeScript or Vite errors.
2. `cd backend && alembic heads` — must print exactly one head revision.
3. `cd backend && pytest -v` — 100% of tests must pass, plus add new pytest coverage for any changed behavior or security rule.
