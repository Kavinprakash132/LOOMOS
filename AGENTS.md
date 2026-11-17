# Google Antigravity Remote Agents — Workspace Instructions (`LOOMOS`)

You are working on **LOOMOS**, a mobile-first Powerloom Job-Work Production, Analytics & Fabric Defect Inspection system.

Before making any code changes, read [`what i did/WHAT_I_DID.md`](what%20i%20did/WHAT_I_DID.md) for the complete project context, verified formulas, hand-calculation checks, and phased roadmap.

---

## 1. Non-Negotiable Engineering & Domain Rules

1. **Integer Paise Only for Money:** All monetary columns and calculations (`rate_paise`, `gross_paise`, `net_payable_paise`, `energy_paise`, `net_bill_paise`, `amount_paise`) MUST use integer paise (`₹1.00 = 100 paise`). Never use floating-point numbers for money.
2. **Immutable Audit Trail & Soft Deletes:** Every create/update/void on financial or master tables MUST call `record_audit(...)` or `soft_delete_record(...)` (`app/core/audit.py`) in the same database transaction. Financial records (`shift_entries`, `payslips`, `advances`, `deliveries`, `delivery_items`, `trader_payments`, `expenses`, `eb_bills`, `eb_readings`, `wage_rules`, `eb_tariff_plans`) are soft-deleted (`is_deleted = True`) and NEVER hard-deleted.
3. **Zero Hardcoded Business Rates:** Electricity tariff slabs (`TANGEDCO LA3A2`), wage rules, loom RPMs, and fabric sort specifications must always be read from the database.
4. **Strict Demo vs. Production DB Isolation:**
   - Automated demos, UI testing, and seeding MUST target `backend/data/loomos_demo.db` (`LOOMOS_DEMO_MODE=true`).
   - Never overwrite or wipe `backend/data/loomos.db`.
5. **No Secrets or `.db` Files in Git:** Never commit `.env`, `.jwt_secret`, `*.db`, `*.db-wal`, `*.db-shm`, `.venv/`, or `node_modules/`.
6. **Mandatory Progress Log Update:** Whenever you complete a feature, bug fix, or milestone, update [`what i did/WHAT_I_DID.md`](what%20i%20did/WHAT_I_DID.md) with what was built, verified, and changed.

---

## 2. Cloud / Linux Sandbox Commands

- **Bootstrap fresh cloud environment (venv + npm + migrations + demo seed + build + pytest):**
  ```bash
  bash scripts/remote_setup.sh
  ```
- **Run backend test gate:**
  ```bash
  cd backend && .venv/bin/pytest -v
  ```
- **Run frontend TypeScript & Vite production build check:**
  ```bash
  cd frontend && npm run build
  ```
- **Start Demo stack (`loomos_demo.db`, Owner `welcome123`/`welcome123`, Supervisor `sup_siva`/`supPassword1`):**
  ```bash
  bash scripts/start_remote_demo.sh
  ```
- **Fetch AITEX / TILDA_400 vision datasets on demand (for Phase 2 `/inspect`):**
  ```bash
  cd backend && .venv/bin/python scripts/fetch_vision_datasets.py
  ```
