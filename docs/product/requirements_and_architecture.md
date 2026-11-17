# LOOMOS Product Requirements & Phased Scope (v3)

**Last updated:** 2026-11-17

---

## 1. User Personas
- **Owner (`OWNER` role):** Uses Laptop/PC and Android phone; manages masters, payroll, deliveries, trader rate checks, EB bills, forecasts, audit logs, and backups.
- **Supervisor (`SUPERVISOR` role):** Uses Android phone on the shed floor; enters shift production + stop reasons (`Power Cut`, etc.) and reviews cloth photos in `/inspect`.

---

## 2. Prioritised Functional Scope (v3 — Locked Down for 10 Weeks)

### Build Steps 1 & 2 — Core Product (Finished First with Full `pytest` Suite)
- **FR-00 Secure 3-Step Setup (`/setup`):** Owner Account + Unit Identity -> Dynamic `N`-loom generator -> Import Historical CSVs / Blank Templates / Optional Sample Seed / Start Clean.
- **FR-01 Auth & RBAC:** JWT login (`OWNER` vs `SUPERVISOR`).
- **FR-02 Configurable Masters (No Hardcoding):** Looms, Weavers/Helpers (4 dated wage modes: `PER_METRE`, `PER_LOOM_SHIFT`, `PER_SHIFT_ATTENDANCE`, `FIXED_WEEKLY`), Traders, Fabric Sorts (rate + expected weft kg/100m + wastage %), Stop Reasons (explicit `Power Cut` stop type), Editable EB Tariff Plans & Slabs.
- **FR-03 Beams & Weft Yarn Wastage Tracking:** Receive warp beam, log weft yarn receipts (`kg`), mount/unload beams (supporting mid-shift changeovers), compare **weft kg used vs metres produced** against expected sort allowance to flag excess yarn wastage/shortage.
- **FR-04 Fast Shift Grid (<90 sec):** Auto-filled editable date (`Today` / `Yesterday` / calendar), auto-shift, last-shift Weaver & Beam carry-forward, Direct or Counter metres, `Power Cut` & stoppage duration logging (`downtime_mins`), atomic save.
- **FR-05 Multi-Mode Payroll & Advances:** Deterministic calculation across all 4 wage modes + advances (*uthaav*) + defect deductions + immutable finalized snapshots.
- **FR-06 Deliveries, Payments & Trader Rate Checker:** Log dispatches & payments; flag `applied_rate < agreed_rate` immediately.
- **FR-07 Full Audit Log & Soft Deletes:** Every create, update, soft delete, and finalize on wages, advances, deliveries, payments, rates, EB bills, and expenses logs `(who, when, old_values, new_values)` in `audit_logs`; zero hard deletes on financial records.
- **FR-08 Bilingual UI & Payslips (`EN | தமிழ்`):** Live English/Tamil switch for UI labels and printable/shareable weaver payslips.
- **FR-09 Step 2 Exports & History Importer:** Downloadable **CSV exports** on all history tables, **full SQLite/JSON backup download**, and historical delivery/EB CSV importer with blank templates.

### Build Step 3 — Intelligence & Defect Vision (Kept Lean & Honest)
- **FR-10 Photo Defect Inspection + Grad-CAM (`/inspect`):** Upload/capture photo (or test built-in samples strictly labelled **`"AITEX Reference Sample (demo only)"`**) -> ONNX prediction + uncertainty threshold + Grad-CAM overlay -> **saves EVERY reviewed photo with its ground-truth label (`Defect` or `Clean`)** into the `LOOMOS-Shed` evaluation/fine-tuning store. Model cards show **held-out test precision, recall, F1, confusion matrix, and failure cases** (never training confidence).
- **FR-11 EB Bill Predictor (DB-Driven + Power-Cut Adjusted):** Projects bi-monthly kWh and ₹ bill from effective running loom-hours (`shift_hours - power_cut_hours`) and woven metres; displays **lost metres & lost ₹ revenue due to power cuts** and warns before crossing higher tariff slabs.
- **FR-12 Beam Finish ETA:** Remaining metres ÷ trailing daily loom output (with uncertainty range).
- **FR-13 One Weekly Production Forecast + Naive Baseline:** **Holt's Exponential Smoothing** compared against a **Naive (Last-Week / Mean) baseline** (MAE/MAPE back-tested on real delivery history).
- **FR-14 Simple Statistical Anomaly Alerts:** Transparent **`z-score` / IQR rules** flagging typos (e.g., `95 m` in one shuttle shift) and multi-shift drops. *(Dismissible to prevent alert fatigue.)*

### Build Step 4 — Polish, E2E & Optional Add-On
- **FR-15 Multi-Format Polish Exports:** **Excel (`.xlsx`)** workbooks and formatted **PDF** payslips, delivery statements, and monthly P&L (English & Tamil).
- **FR-16 *(Build Last Only If Time Remains)* Basic What-If Simulator:** Simple single-screen comparison of `N` shuttle vs shuttle+rapier mix.

### Explicitly Removed in v3
- **Loom Health Score** (removed).
- **Isolation Forest** (removed).
- GST invoicing / e-way bills, IoT sensors, continuous live video, online payments.
