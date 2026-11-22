---
applyTo: "backend/**"
---
# LOOMOS Backend Coding Guidelines (FastAPI + SQLAlchemy 2 + Alembic + SQLite)

## Database & ORM Patterns
- Use SQLAlchemy 2 typed syntax (`Mapped[...]`, `mapped_column(...)`, `select(...)`, `db.scalar(...)`, `db.scalars(...)`). Avoid legacy `db.query(...)`.
- Store all money values in `BigInteger` / `Integer` paise (`*_paise`), and physical quantities (metres, kg, kWh, cloth width inches) in `Numeric` / `Decimal`.
- Never use bare `date.today()` for shed operational dates — import `today_ist` and `now_ist` from `app.core.config`.
- Whenever adding columns or tables in `app/models/core.py`:
  1. Create a new migration in `backend/alembic/versions/` chaining cleanly off the current single head (`alembic heads`).
  2. Make `upgrade()` and `downgrade()` **idempotent** by checking `sa.inspect(op.get_bind()).get_table_names()` or `get_columns(...)` before creating/adding/dropping (critical for SQLite).
  3. Update Pydantic schemas in `app/schemas/`, router handlers, `assistant_service.py` tools (if relevant), and `AuditLogPage.tsx` `FIELD_LABELS`.

## Audit Trail & Soft Deletes
- Never hard-delete financial entities (`ShiftEntry`, `Advance`, `Payslip`, `Delivery`, `TraderPayment`, `Expense`, `EbReading`, `EbBill`, `EbTariffPlan`, `WageRule`, `WeftReceipt`).
- Always use `soft_delete_record(...)` and `record_audit(...)` from `app.core.audit`, and filter reads with `.where(Model.is_deleted.is_(False))`.

## Domain Math Guardrails
- Preserve exact TNPDCL LA3A2 slab math in `app/services/eb_calculator.py` (including the <= 1,000 kWh free-quota waiver). Never hardcode unit rates; always read `EbTariffPlan` + `EbTariffSlab`.
- Preserve `Decimal` + `ROUND_HALF_UP` rounding for payroll, delivery totals, rate-cut shortfalls, and weft wastage checks.
- Keep `backend/requirements.txt` compatible with a 1 GiB RAM Linux container (CPU `onnxruntime` only; no PyTorch).

## Testing Standards
- Run `pytest -v` in `backend/` after every change.
- For every new endpoint or field, add tests in `backend/tests/` verifying:
  - Create, read, update (and audit log entry), and invalid input handling (`422`/`409`).
  - Role enforcement (`SUPERVISOR` -> `403` on Owner endpoints; non-AI Owner -> `403` on `/api/v1/assistant/*`).
  - No regression in backup scrubbing (`test_assistant.py`) or TNPDCL bill accuracy (`test_masters_and_tariffs.py`).
