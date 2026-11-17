# UX Design, Responsive Layouts & Page Inventory (v3)

**Last updated:** 2026-11-17  
**Languages:** Instant **`EN | தமிழ்`** toggle (header bar + user preference + bilingual weaver payslips).

---

## 1. Onboarding Flow (`/setup`)
1. **Step 1 — Claim Your Shed:** Owner Name, Username, Password + Unit Name & Location. *(Security & `created_by` integrity first.)*
2. **Step 2 — Size Your Shed:** Ask **"How many looms do you run?"** (`N`) + Loom Type/RPM mix (`Shuttle` / `Rapier` / `Airjet`). Auto-creates `L-01`..`L-N`.
3. **Step 3 — Data Choice:** Upload Historical Deliveries/EB CSVs, download blank Excel-ready CSV templates, opt into clearly labelled demo data, or Start Clean.

---

## 2. Page Inventory & Role Scope

| Route | Screen | Owner | Supervisor | Key v3 Capabilities |
|---|---|---|---|---|
| `/setup` | 3-Step Setup Wizard | First-boot | — | Locks after Owner created |
| `/login` | Sign In | Yes | Yes | Language toggle (`EN \| தமிழ்`) on login screen |
| `/today` | **Daily Shift Grid** | Yes | **Landing** | Auto-fills `Today` + active `Shift` + last shift's `Weaver/Beam`; `Yesterday` 1-tap + editable date; Direct or Counter mode; logs `Power Cut` mins |
| `/inspect` | **Cloth Quality Audit (ML)** | Yes | Yes | Capture guide + upload OR `"AITEX Reference Sample (demo only)"` -> ONNX + Grad-CAM + held-out Model Card + saves **every** reviewed photo (`Defect` or `Clean`) |
| `/dashboard` | **Owner Intelligence Hub** | **Landing** | No | Today/week metres, Beam ETAs, EB slab & power-cut loss card, Weekly Forecast vs Naive, dismissible `z-score`/IQR & wastage alerts |
| `/beams` | Beams & Weft Wastage | Yes | Read-only | Remaining metres + **Weft kg used vs metres produced** wastage flags |
| `/payroll` | Wages & Advances | Yes | No | 4 wage modes (`Per Metre`, `Per Loom-Shift`, `Per Shift`, `Fixed Weekly`), soft-deleted voiding, **EN/Tamil payslips** (CSV in Step 2; XLSX/PDF in Step 4) |
| `/deliveries` | Deliveries & Rate Checker | Yes | No | Auto-filled date, challans, soft deletes, `applied < agreed` rate alerts, CSV (Step 2) + XLSX/PDF (Step 4) |
| `/audit-log` | **Audit Trail & Voided Records** | Yes | No | Read-only log (`who, when, old value, new value`) for all financial edits & soft deletes |
| `/analytics` | Forecasts & EB Analysis | Yes | No | Holt's Weekly Forecast vs Naive, DB-driven TANGEDCO EB Predictor + power-cut lost-output view *(optional basic What-If in Step 4)* |
| `/settings` | Shed Masters, EB Slabs & Backups | Yes | No | Manage looms, weavers, sorts, stop reasons, editable EB slabs, Supervisors, CSV import, **Full DB Backup** |
