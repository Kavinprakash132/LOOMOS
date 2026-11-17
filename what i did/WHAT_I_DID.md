# LOOMOS — Complete Project Guide, Progress Log & AI Handoff ("What I Did")

**Last Updated:** 2026-11-17 (After Delivery Phase 1 — Isolated Demo DB, Dashboard, Partial OEE & One-Click LAN Launchers)  
**Project Root:** `d:\project in antigravity\loomos\`  
**Rule:** Every time changes are made to LOOMOS, this single file is updated with what was built, verified, left unfinished, and planned next—so you can use it to explain every single detail to anyone (your college guide, viva examiners, friends, or any AI).

---

## 0. Quick 30-Second Summary (How to Explain LOOMOS)

> **LOOMOS** is a mobile-first production management and analytics web app with smartphone-based fabric defect detection, built for small decentralized powerloom job-work units in Tamil Nadu.  
> Instead of paper notebooks, a supervisor or owner opens LOOMOS in Chrome over local shed Wi-Fi on an Android phone or laptop (`Choice 1`), logs daily shift metres in `<90 sec`, manages warp beams & weft wastage, calculates 4-mode weaver/helper wages with trilingual (`EN / தமிழ் / हिन्दी`) printable payslips, catches trader per-metre rate cuts, and checks cloth defects from photos (Step 3).  
> Everything uses **₹0 free & open-source tools** (React + TypeScript + Tailwind + FastAPI + SQLite + PyTorch/ONNX), stores money in integer paise, never hardcodes business rules, and records every financial edit/soft-delete in an immutable audit log.

---

## 1. Current Status Overview

| Milestone | Status | Verified Proof |
|---|---|---|
| **Baseline Research & Vision Gate (`docs/`, AITEX Gate 1)** | **DONE** | 18 research/architecture docs, 20 DOIs, zero-leakage strip split check |
| **Baseline App Core (Step 1 + Gate 1.5 + Step 2 Core)** | **DONE** | Migration `e16c9a3c63cb (head)`, auth/RBAC, masters, beams, shifts, 4-mode payroll, deliveries, exports |
| **Delivery Phase 1: Isolated Demo DB, Launchers, Dashboard, Partial/Full OEE & Void Controls** | **DONE & LIVE** | `Start_LOOMOS.bat` + `Start_LOOMOS_DEMO.bat`, 5 shuttle looms (`<30m` demo), `ConfirmVoidModal`, `Pirn Winder` role, `DD/MM/YYYY` dates, `HH.MM` hours display, CSS caret fix, plain-language note, inline RPM & unused loom delete; **`npm run build` passed (`4.28s`)**, **`pytest` 18/18 passed (`21.28s`)** |
| **Delivery Phase 2: Reconciled Vision (`ResNet-18` vs `MobileNetV3-Small`) & `/inspect`** | **NEXT** | Single leak-free held-out split; 1:1 winning model metrics + Grad-CAM + Two-Output ONNX; save all reviewed shed photos |
| **Delivery Phase 3: Shed Analytics, Beam ETA, Component EB Predictor & Weekly Forecast** | **PLANNED** | Real-shed EB predictor + outage loss, Beam ETA (`P75`/`P25` + `due_date`), `MAD/IQR` alerts, `CN-MA` + `Holt` vs `Naive` |
| **Delivery Phase 4: `.xlsx` / Print-PDF Reports & 3–4 Playwright E2E Flows** | **PLANNED** | `openpyxl` books + Print-PDF statements + 3–4 Desktop/Mobile Playwright flows |
| **Delivery Phase 5 *(Optional)*: Multi-Group Expansion Simulator & `RQ3` Few-Shot Script** | **OPTIONAL** | `20/30/50/100` + mixed Shuttle/Rapier/Airjet P&L, Incremental Payback, EMI & 2D Matrix (no Monte Carlo) |

---

## 2. What We Have & What Has Been Done So Far

### A. Real Business Baseline Data (`d:\project in antigravity\Powerloom_Business_Plan.docx`)
Used strictly for calibration and optional historical import—**never hardcoded** into LOOMOS:
- **Unit profile:** 20 conventional shuttle looms on job-work (`₹6/m`, 2 shifts, ~25 working days/month), expanding toward 50 looms / rapier options.
- **Historical totals in doc:** `41` weekly delivery totals summarized across 5 EB periods (`2,51,455 m`, calibrated `53.85 m/loom/day` = `89.8%` efficiency), `5` real bi-monthly TANGEDCO `LA3A2` bills (`P1` 8,360 kWh / `P2` 6,407 kWh / `P3` 2,796 kWh / `P4` 4,346 kWh / `P5` 6,361 kWh), worker wages (`₹60/loom/shift` + `₹2,500/week` women helper), profit `~₹2.03/m`.
- **Verified TANGEDCO LA3A2 tariff slab formula:** `0–1,000` free, `1,001–1,500` @ `₹4.15`, `>1,500` @ `₹5.30`. Checked against all 5 real energy bills (`P1`–`P5`): `round(calc_paise / 100) == doc_rupees` across all 5 periods.

### B. Industry, Competitor & Academic Research (`loomos/docs/`)
- **18 structured docs created** across `docs/academic/`, `docs/architecture/`, `docs/business/`, `docs/product/`, `docs/project_management/`, `docs/research/`, `docs/research_methodology/`.
- **Industry & market context:** IBEF/Ministry of Textiles figures cited in web search (~24.86 lakh powerlooms nationally across >3.85 lakh units; ~5.63–5.68 lakh in TN); Mar–Apr 2025 Somanur/Palladam 33-day strike & April 20, 2025 MoU + reported 25–50 paise/m rate cuts (justifying the Trader Rate Checker).
- **Live competitor checks (`competitor_analysis.md`):** Inspected `loomiro.com` (Surat waterjet/airjet, Hinglish/Gujarati/English, from ₹999/mo billed yearly), `texfo.in` (quote-based mobile weaving ERP), `pinakexa.com` (multi-industry ERP), `emanage.in` (enterprise mill ERP), `vastraapp.com` (apparel/trader ERP), `trackweaving.com` (IoT sensor monitoring).
- **20 Crossref/OpenAlex-verified academic references (`literature_review.md` & `source_register.md`):** Silvestre-Blanes et al. (2019 AITEX `10.2478/aut-2019-0035`), Hanbay et al. (2016), Nasim et al. (2024), Mao & Hong (2025), Islam et al. (2024 FabricSpotDefect), Dhali et al. (2025 FabriXNet), Swapno et al. (2025), Howard et al. (2019 MobileNetV3), He et al. (2016 ResNet), Selvaraju et al. (2019 Grad-CAM), Pandey et al. (2024), Rodríguez-Espíndola et al. (2022), Alayón et al. (2022), Kamble et al. (2024), Hyndman et al. (2008), Hevner et al. (2004), Peffers et al. (2007), Bangor et al. (2008 SUS), plus excluded negative reference Matzka (2020 AI4I synthetic milling dataset).

### C. Week 1 Vision Dataset Gate (`loomos/docs/research/vision_gate_report.md`)
- **Why UCI AI4I 2020 was dropped:** Verified via Matzka (2020) that AI4I is a *synthetic milling-machine* dataset (96.6% non-failure; missed ~37% failures), not looms.
- **Public textile datasets verified on disk:**
  - **AITEX** (`jraad/fabric_defect_detection`): `106` defect strips + `109` masks (`104` valid non-empty defect strips after dropping missing-mask `0100_025_08.png` and empty-mask `0106_010_03.png`) + `141` clean strips across 7 fabric weaves + `185` COCO crops.
  - **TILDA_400** (`the-h-b/TILDA_400`): `2,430` `64×64` RGB defect patches (`hole`: 337, `objects`: 837, `oil spot`: 636, `thread error`: 620; CC BY-NC-SA 4.0).
- **Zero-leakage strip split:** `72` train / `16` val / `16` held-out test defect strips (`0` overlap). Test split = `604` (`27` defect / `577` clean) or `620` (`28` defect / `592` clean) non-overlapping `256×256` patches (`95.5%` clean majority!).
- **Measured held-out test results (leading with Defect Recall & Defect F1):**
  - **`ResNet-18 + CLAHE + centered train crops`:** **Defect Recall `0.481`**, **Defect F1 `0.565`**, Precision `0.684`, Macro-F1 `0.774`, ROC-AUC `0.950`, CPU `37.24 ms/img`, Confusion Matrix `[[571, 6], [14, 13]]` *(overall accuracy `96.69%` is inflated because 95.5% of patches are clean, and the test set has only 27 defect patches)*.
  - **`MobileNetV3-Small` (raw):** Defect Recall `0.607`, Defect F1 `0.436`, Precision `0.340`, Macro-F1 `0.699`, ROC-AUC `0.895`, CPU `19.64 ms/img` (`6.51 ms/img` cached).
  - **`SmallCNN` (scratch):** Defect Recall `0.607`, Defect F1 `0.215`, Precision `0.131`, Macro-F1 `0.550`, ROC-AUC `0.755`.
- **Grad-CAM visual check (`MobileNetV3-Small`, confirmed on held-out test strips `0005_002_01`, `0058_019_06`, `0015_006_02`, `0079_025_03`):** Highlighted `Broken End` (`1.00`), `Fuzzyball` (`0.94`, ignoring bright selvedge edge), and `Broken Yarn` (`1.00`), while missing a ~5×5 px `Warp Ball` speck (`0.49` FN failure case).

### D. Build Step 1 Implemented Files & Passing Checks
1. **Backend (`d:\project in antigravity\loomos\backend\`, Python `3.13.5` `.venv`):**
   - `app/core/config.py`, `database.py` (SQLite WAL + `foreign_keys=ON`), `security.py` (bcrypt + JWT + `require_owner`), `audit.py` (`record_audit` + `soft_delete_record`), `i18n.py` (`en` & `ta` bundles).
   - `app/models/core.py` + Alembic migration `alembic/versions/b37e5a1361f8_initial_schema_v3.py`: Full v3 normalized schema (`unit_settings`, `eb_tariff_plans`, `eb_tariff_slabs`, `users`, `audit_logs`, `looms`, `weavers`, `wage_rules`, `traders`, `fabric_sorts`, `beams`, `weft_receipts`, `beam_loadings`, `stop_reasons`, `shift_entries` with **unique `client_uuid`** & `(loom_id, entry_date, shift_no, beam_id)`, `advances`, `payslips`, `deliveries`, `delivery_items`, `trader_payments`, `inspections`, `defect_predictions`, `eb_readings`, `eb_bills`, `expenses`, `alerts`). Integer paise for money; soft-delete fields on all financial tables.
   - `app/routers/setup.py`: `GET /api/v1/setup/status`, CSV templates `/templates/{eb_bills|deliveries}`, `POST /api/v1/setup/initialize` (Step 1 Owner & Unit -> Step 2 Dynamic `N` looms -> Step 3 Clean / CSV Import / `[DEMO]` seed, locked `409` once done).
   - `app/routers/auth.py`: Login, `/me`, `/me/language`, Owner-only `/users`.
   - `app/routers/settings.py`: Unit settings, editable `eb-tariffs` (TANGEDCO LA3A2 preset + custom plans + soft delete), configurable `stop-reasons` (`POWER_CUT` flagged `is_power_cut=True`).
   - `app/routers/masters.py`: `looms` (single + `/bulk`), `weavers` + dated `wage-rules` (`PER_METRE`, `PER_LOOM_SHIFT`, `PER_SHIFT_ATTENDANCE`, `FIXED_WEEKLY`, plus soft delete), `traders`, `fabric-sorts` (with rate, expected weft kg/100m, wastage %), and `audit-logs`.
   - `app/services/eb_calculator.py` & `seed_defaults.py`.
   - **Verified `pytest -v` (`tests/`):** **9/9 Passed** in `10.26s`.
2. **Frontend (`d:\project in antigravity\loomos\frontend\`, React 18 + TS + Vite 6 + Tailwind v4):**
   - LAN-safe relative `/api` proxy in `vite.config.ts` (`http://127.0.0.1:8000`); no hardcoded `localhost` in browser fetches (`src/api/client.ts`).
   - Bilingual `EN | தமிழ்` switcher (`src/i18n/translations.ts`, `src/context/AuthContext.tsx`).
   - Responsive Desktop Sidebar + Mobile Bottom Nav (`AppShell.tsx`).
   - Working pages: `SetupPage.tsx`, `LoginPage.tsx`, `SettingsMastersPage.tsx` (`LoomsTab.tsx`, `WeaversTab.tsx`, `TradersSortsTab.tsx`, `EbAndStopsTab.tsx`, `TeamUnitTab.tsx`), `AuditLogPage.tsx`, `PlaceholderStepPage.tsx`.
   - **Verified `npm run build` (`tsc -b && vite build`):** **Passed** in `7.15s`.

### E. Gate 1.5 Audit Fixes & Build Step 2 Implemented Files & Passing Checks
1. **Gate 1.5 Pre-Step 2 Migration (`alembic/versions/e16c9a3c63cb_gate15_audit_fixes_for_step2_and_step3.py`):**
   - Added `UnitSettings.planned_shift_mins` (`600`), `shed_calendar` working/holiday table, `Weaver.full_name_hi` & `Weaver.preferred_slip_lang` (`en|ta|hi`), and `weaver_attendance` (`PRESENT | HALF | ABSENT`) for helpers/fitters/attendance shifts.
   - Added itemized `EbTariffPlan` (`fixed_charge_per_kw_month_paise`, `electricity_tax_bps`, `fppca_paise_per_unit`, `tax_on_gross`) & `EbBill` component columns (`fixed_paise`, `tax_paise`, `fppca_paise`, `subsidy_paise`, `other_charges_paise`) + `calculate_bill_breakdown_paise(...)` in `app/services/eb_calculator.py`.
   - Added `Beam.opening_woven_m`, `expected_tail_waste_m`, `returned_weft_kg`, `actual_waste_m`, `due_date`; `BeamLoading.unload_reason`; nullable `WeftReceipt.beam_id`; `ShiftEntry.planned_mins`, `power_cut_mins`, `defective_metres` + `SoftDeleteMixin` + partial unique indexes; `DeliveryItem` production dates; and `Inspection.defective_metres`, `session_burst_id`, `split_tag`, `second_reviewer_label`, `DefectPrediction.threshold_used`.
2. **Step 2 Backend Services & Routers:**
   - `app/services/beam_service.py` & `app/routers/beams.py`: Warp beam receiving, mounting/unloading with returned weft reconciliation, weft receipts, and `WEFT_WASTAGE` alerts.
   - `app/routers/shifts.py`: `/shifts/prefill` (local IST date/shift suggestion, carried-forward weaver & beam, last end-meter), idempotent `client_uuid` `/shifts/batch` (Direct/Counter, `power_cut_mins`, `planned_mins`, beam swaps, soft delete + audit), `/attendance/batch`, and `/calendar/{date}`.
   - `app/services/payroll_service.py`, `app/core/i18n.py` (`PAYSLIP_TRANSLATIONS`), & `app/routers/payroll.py`: Owner-only 4-mode payroll (`PER_METRE`, `PER_LOOM_SHIFT` with beam-swap deduplication, `PER_SHIFT_ATTENDANCE`, `FIXED_WEEKLY`) honoring dated wage-rule revisions, advances (*uthaav*), finalized snapshots, soft-delete voiding, and trilingual (`en | ta | hi`) printable payslips (`/payslips/{id}/printable`).
   - `app/routers/finance.py` & `app/routers/data_ops.py`: Deliveries + `RATE_UNDERPAYMENT` Rate Checker, Trader Payments & Receivables, Expenses, EB Readings/Bills, dismissible Alerts, Excel-safe UTF-8 BOM (`utf-8-sig`) CSV exports, post-setup CSV importers, and WAL-safe `sqlite3.Connection.backup()` `.db` download.
   - **Verified `pytest -v` (`tests/`):** **14/14 Passed** in `27.00s`.
3. **Step 2 Frontend Pages (English UI + Trilingual HTML `@media print` Slips):**
   - `src/pages/BeamsPage.tsx`, `TodayShiftPage.tsx`, `PayrollPage.tsx`, `DeliveriesPage.tsx` + updated `WeaversTab.tsx`, `EbAndStopsTab.tsx`, `TeamUnitTab.tsx`, `AppShell.tsx`, `App.tsx`, `index.css`, and `api/client.ts`.
   - **Verified `npm run build` (`tsc -b && vite build`):** **Passed** in `6.84s`.

### F. Delivery Phase 1 Implemented Files & Isolated Demo Sandbox
1. **Isolated Demo Database & Safety Guards:**
   - `backend/scripts/seed_demo_cli.py`: Targets **`data/loomos_demo.db` ONLY** (`--demo` seeds realistic 20-loom shed, `--clean` resets ONLY `loomos_demo.db` to empty setup state). Refuses (`exit code 2`) if pointed at production `data/loomos.db`. Explicit `--reset-production-db` requires typing `"RESET_REAL_LOOMOS_DB"` and creates an automatic timestamped backup first.
   - `app/core/config.py`, `app/schemas/step1.py`, `app/routers/setup.py`: Added `LOOMOS_DEMO_MODE` + `is_demo_mode` / `active_db_name` on `/setup/status`.
   - `frontend/src/components/DemoBanner.tsx`: Persistent amber `DEMO DATA ACTIVE (loomos_demo.db)` banner mounted in `AppShell.tsx`, `LoginPage.tsx`, and `SetupPage.tsx`.
2. **One-Click LAN Launchers:**
   - `loomos/Start_LOOMOS.bat` (uses real `data/loomos.db`, `LOOMOS_DEMO_MODE=false`) & `loomos/Start_LOOMOS_DEMO.bat` (uses isolated `data/loomos_demo.db`, `LOOMOS_DEMO_MODE=true`; run `Start_LOOMOS_DEMO.bat clean` to test fresh `/setup` safely).
3. **Owner Operational Dashboard & Partial/Conditional OEE:**
   - `backend/app/schemas/dashboard.py`, `app/services/dashboard_service.py`, `app/routers/dashboard.py`, `frontend/src/pages/DashboardPage.tsx`: `/dashboard/floor` (`OWNER` + `SUPERVISOR` operational metrics) & `/dashboard/summary` (`OWNER`-only financials). Displays **Availability %**, **Performance %**, **Utilization (`A×P %`)**, and unlocks **Quality % & Full OEE** automatically when confirmed `defective_metres > 0`.
4. **UI Void Controls (Soft-Delete Polish):**
   - Added `Void` buttons (w/ mandatory Audit Log reason) across `DeliveriesPage.tsx` (Challans, Payments, Expenses, EB Bills) and saved shift cards in `TodayShiftPage.tsx` (Owner-only).
   - **Verified `pytest -v` (`tests/`):** **17/17 Passed** in `28.88s` (`test_phase1_dashboard_and_demo_safety.py` + prior 14 tests).
   - **Verified `npm run build` (`tsc -b && vite build`):** **Passed** in `4.55s`.

---

## 3. What We Have NOT Built or Collected Yet (Honest Status)

### Software Not Built Yet (Locked Delivery Phases 2–5)
- **Phase 2 (Vision AI & `/inspect`):** Single leak-free held-out AITEX comparison of **only `ResNet-18 + CLAHE` vs `MobileNetV3-Small + CLAHE`**, Two-Output ONNX export (`logits + conv_maps`) of the **single winning model**, `/inspect` page (`/inspect` is currently `PlaceholderStepPage`) with phone camera upload + `"AITEX Reference Sample (demo only)"`, aligned Model Card + Grad-CAM overlay, saving **every** reviewed photo (`CONFIRMED_DEFECT` / `CONFIRMED_CLEAN` + optional `defective_metres`). *(No 5-fold CV, no LOFO, no Focal Loss, no sliding-window tests unless requested later.)*
- **Phase 3 (Analytics & Forecasting):** Component EB Bill Predictor + Power-Cut Lost Metres/₹, Beam Finish ETA (`shed_calendar` + `P75`/`P25` + `due_date` badge), Live `MAD/IQR` + Physical Cap Anomaly Alerts, Weekly Forecast (`Capacity-Normalized MA` + `Holt` vs `Naive`). *(No Isolation Forest, no Loom Health Score, no EDD, no Monte Carlo.)*
- **Phase 4 (Reports & 3–4 Focused Playwright Flows):** `openpyxl` multi-sheet `.xlsx` workbooks + HTML `@media print` Monthly P&L & Trader Statements + Playwright E2E covering **3–4 key flows** on Desktop & Mobile.
- **Phase 5 *(Optional)*:** Deterministic Multi-Group Expansion Simulator (`20/30/50/100` + `Shuttle/Rapier`, Incremental Payback, EMI, 2D Sensitivity Matrix) & `RQ3` few-shot script once field photos accumulate.
- **Deferred (Post-Degree):** Full Steps 2–4 Tamil app UI (UI stays clean English now; payslips already work in `EN`/`TA`/`HI`) & HTTPS Offline Sync Queue (`client_uuid` ready).

### Fieldwork & Research Experiments Not Done Yet
1. Inspecting one real TNPDCL consumer bill to finalize exact fixed/tax/subsidy line-item preset.
2. Digitizing the raw 41 weekly delivery rows (`Powerloom_Business_Plan.docx` has period sums only).
3. Entering real shed data & capturing `150–250` real `LOOMOS-Shed` smartphone cloth photos once Phase 2 `/inspect` goes live, plus `RQ1/RQ5` baseline timings & SUS survey.

---

## 4. What We Are Going To Do Next (Approved Phase Sequence)

1. **Phase 2 (Next):** Compare `ResNet-18 + CLAHE` vs `MobileNetV3-Small + CLAHE` cleanly on 1 leak-free held-out AITEX split -> export winning **Two-Output ONNX** -> build `/inspect` so you can capture & label real cloth photos while logging shed data.
2. **Phase 3:** Build `/analytics` & Beam ETA (`EB Predictor`, `Beam Finish ETA + due_date badge`, `MAD/IQR` alerts, `CN-MA + Holt vs Naive` weekly forecast) using real data accumulated during earlier phases.
3. **Phase 4:** Add `openpyxl` `.xlsx` + HTML Print-PDF statements and **3–4 key Playwright E2E flows** (Desktop + Mobile).
4. **Phase 5 *(Optional)*:** Build Multi-Group Expansion Simulator & `RQ3` few-shot adaptation script.

---

## 5. Phase 1 Live Browser Testing Guide, Hand Checks & Acceptance Checklist

### A. Launch & URLs (Isolated Demo DB Active)
- **Production DB Safety:** `backend\data\loomos.db` has **`0` `unit_settings` rows** (completely untouched). Demo runs against `backend\data\loomos_demo.db` (**`5` shuttle looms (`S-01`..`S-05`, `160–170 RPM`)**, 35 days of `< 30 m/shift` production (`22–28 m/shift`), 4 workers including `Pirn Winder`, `BM-100..105`, Weekly & Monthly deliveries, and `P5` EB bill).
- **One-Command Demo Batch File:** `Start_LOOMOS_DEMO.bat` *(or `Start_LOOMOS.bat` when ready to set up your real shed!)*
- **Laptop Browser URL:** `http://127.0.0.1:5173`
- **Android Phone URL (Same Wi-Fi):** `http://10.45.222.244:5173` *(if blocked on first connect, allow Python/Node on Private Networks in Windows Firewall)*.
- **Demo Logins:**
  - **Owner:** `welcome123` / `welcome123`
  - **Supervisor:** `sup_siva` / `supPassword1`

### B. Click-by-Click "How to Test Phase 1" (Login to End)
1. **Verify Demo Isolation Banner & Login/Setup:** Open `http://127.0.0.1:5173` on laptop (and `http://10.45.222.244:5173` on Android Chrome). Confirm the bright yellow **`DEMO DATA ACTIVE (loomos_demo.db)`** banner stays visible across `/login` and every page, password eye toggle reveals text cleanly, compulsory fields highlight red when invalid, and switching `EN | தமிழ்` translates Login & Setup labels.
2. **Owner Dashboard & Plain-English Efficiency (`/dashboard`):** Log in as `welcome123` / `welcome123`. Click **`Weekly (7d)`**, **`Monthly (30d)`**, and **`From .. To`** (`DD/MM/YYYY`) controls — confirm active range button highlights cleanly. Check Today's output (**`125.00 m`**), Weekly output (**`1,603.00 m`**) vs Monthly (**`7,353.00 m`**), **`Active Warp Beams`** (`4` running: `BM-101..104`), and Owner Financial Summary showing non-zero EB (`₹7,560.00`). Confirm efficiency breakdown displays **`Time Run %`** (`98.46%`), **`Weaving Speed %`** (`72.16%`), **`Combined Efficiency %`** (`71.05%`), and **`Defect-Free Cloth %`** (`Pending Defect Data`), plus per-loom Shuttle RPM table.
3. **Verify RBAC (`SUPERVISOR` vs `OWNER`):** Open Incognito / Phone browser and log in as `sup_siva` / `supPassword1`. Confirm Supervisor lands on `/today`, can visit **`Dashboard`** (`/dashboard`) to check looms & efficiency metrics **without** seeing the Owner Financial Summary card or Payroll/Deliveries/Settings/Audit tabs.
4. **Daily Shift Grid, Running/Stopped Toggle & 3-Column Counter (`/today`):** Verify only Shift 1 & Shift 2 appear (`shifts_per_day = 2`, no Shift 3), today's date (`DD/MM/YYYY`), `Saved` badge on recorded cards, **`[ ● Running | ■ Stopped ]`** toggle (no stoppage minute boxes), **`[ Metres | Counter ]`** toggle showing 3-column Counter (`Start Meter | End Meter | Net Metres` without editable text cursor inside `Net Metres`; `S-01` `last_end_meter = 2932.00`), **`+ Swap Beam`** adding a **`2nd Beam (Mid-Shift)`** slot with **`× Remove`** without duplicating looms, and **Void** opening the in-app `<ConfirmVoidModal>` (prefilled `"Entry mistake"`). Enter `1.30` in **`Confirmed Defect (m)`** on one row and tap **Save Shift**, then check `/dashboard` to see **`Defect-Free Cloth %`** unlock.
5. **Beams & Weft Reconciliation (`/beams`):** Open `/beams`, verify `DD/MM/YYYY` dates and the Warp Beam vs Weft cones subtitle. View `BM-100` (`COMPLETED`) showing `Weft Waste 21.53%`, `BM-101..104` running on `S-01..S-04`, and `BM-105` (`IN_STOCK`) ready to load onto free loom `S-05`.
6. **4-Mode Payroll & `EN / தமிழ் / हिन्दी` Print Payslips (`/payroll`):** Switch to **1. Calculate Weekly Payroll**, accept default 7-day range, click **Calculate Wages Preview**. Verify all 4 workers appear across roles (`Arumugam K`, `Ramesh Kumar`, `Meena Pirn Winder`, `Lakshmi Helper`), labelled **`Advance Cut (Uthaav)`** & **`Damage Cut (optional ₹)`** columns, `<ConfirmVoidModal>` on Void, and **Print / PDF** switching **`English | தமிழ் | हिन्दी`**.
7. **Deliveries Rate Checker, Shuttle Looms Tab, Workers & Audit Log (`/deliveries`, `/settings`, `/audit-log`):** On `/deliveries`, confirm auto-suggested Challan No (`CH-203`), red rate-cut badge on `CH-202` (`Shortfall ₹500.00`), labelled inputs across tabs, and **Void** working cleanly on Expenses & EB Meter Readings. On `/settings`, verify Shuttle-only Looms tab (`5` looms) with inline `RPM` + `Save`, `Delete` / `Archive` + `Show Archived` toggle, and single `Worker Name` input with **`Weaver | Pirn Winder | Helper`** roles. On `/audit-log`, verify IST `DD/MM/YYYY` timestamps and human-readable `Before` / `After` chips.
8. *(Optional Fresh Setup Test on Demo DB)*: Run `Start_LOOMOS_DEMO.bat clean` in a terminal to reset **only** `loomos_demo.db` to 0 rows, verify the 3-step `/setup` wizard (Shuttle-only, 1 or 2 shifts/day, `S-` default) runs end-to-end, and confirm real `loomos.db` remains untouched.

### C. Hand-Calculation Verification Checks (Compare Against 5-Loom Demo Data)
1. **Hand Check 1 — Loom `S-01` & `S-05` Utilization (`Weekly 7-Day Window`):**
   - `S-01` (`SHUTTLE`, `160 RPM`, `40s x 40s Grey Gada`): `13` shifts logged × `600` mins = **`7,800` planned mins**, `0` downtime -> `7,800` operating mins $\rightarrow$ **`Time Run %` = `100.0%`**.
   - Actual woven = **`364.00 m`** vs Ideal (`RPM/Pick` over `7,800` operating mins) = **`417.04 m`** $\rightarrow$ **`Weaving Speed %` = $\frac{364.00}{417.04} \times 100 = \mathbf{87.28\%}$**; **`Combined Efficiency %` = `87.28%`**.
   - `S-05` (`SHUTTLE`, `170 RPM`, no running beam): `13` shifts logged, `7,800` planned mins, `600` downtime mins $\rightarrow$ `7,200` operating mins $\rightarrow$ **`Time Run %` = $\frac{7,200}{7,800} \times 100 = \mathbf{92.31\%}$** (`Weaving Speed %` withheld when no beam sort PPI is attached).
2. **Hand Check 2 — Owner Weekly (`7d`) & Monthly (`30d`) Financials (`/dashboard`):**
   - **Weekly (`7d`):** Billed Revenue **`₹14,500.00`** − (Finalized Wages **`₹2,500.00`** + EB Bill **`₹7,560.00`** + Expenses **`₹2,000.00`** = `₹12,060.00`) = **Net Operating Balance `₹2,440.00`**.
   - **Monthly (`30d`):** Billed Revenue **`₹47,450.00`** − (Finalized Wages **`₹2,500.00`** + EB Bill **`₹7,560.00`** + Expenses **`₹3,400.00`** = `₹13,460.00`) = **Net Operating Balance `₹33,990.00`**.
   - **Trader Receivable Balance (All-Time):** **`₹6,300.00`**. **Rate-Cut Shortfall (`CH-202`):** **`₹500.00`**.
3. **Hand Check 3 — 7-Day Payroll Preview (`/payroll`):**
   - `Arumugam K` (`WEAVER`, `PER_LOOM_SHIFT`): `39.00` units $\rightarrow$ Gross `₹2,340.00` − Advance `₹500.00` = **`₹1,840.00` net**.
   - `Ramesh Kumar` (`WEAVER`, `PER_METRE`): `663.00 m` $\rightarrow$ Gross **`₹2,652.00` net**.
   - `Meena Pirn Winder` (`PIRN_WINDER`, `PER_SHIFT_ATTENDANCE`): `6.00` shifts $\rightarrow$ Gross **`₹2,100.00` net**.
   - `Lakshmi Helper` (`HELPER`, `FIXED_WEEKLY`): `1.00` week $\rightarrow$ Gross **`₹2,500.00` net**.

### D. Phase 1 Pass/Fail Acceptance Checklist
- [ ] **1. Real DB Untouched:** Confirm real `backend/data/loomos.db` stayed clean (`0` `unit_settings` rows) while `loomos_demo.db` powered all demo tests.
- [ ] **2. `DEMO DATA` Banner Visible:** Amber `DEMO DATA ACTIVE (loomos_demo.db)` bar shows on `/login`, `/dashboard`, and mobile viewports.
- [ ] **3. Laptop + Android Phone LAN Access:** Both `http://127.0.0.1:5173` and `http://10.45.222.244:5173` load without broken `/api` calls.
- [ ] **4. RBAC Enforced:** Supervisor cannot open `/dashboard/summary` financials, `/payroll`, `/deliveries`, or `/audit-log`.
- [ ] **5. Plain-English Efficiency & Full OEE Transition:** Dashboard matches Hand Check #1 (`S-01: 100.0% Time Run, 87.28% Speed; S-05: 92.31% Time Run`), withholds Defect-Free Cloth % when `defective_metres = 0`, and unlocks `FULL OEE` when confirmed defective metres > `0`.
- [ ] **6. Owner Weekly & Monthly Financials Match Hand Check #2:** Weekly (`₹14,500` Rev, `₹7,560` EB, `₹2,440` Net), Monthly (`₹47,450` Rev, `₹7,560` EB, `₹33,990` Net), Receivable `₹6,300`, Rate-Cut Shortfall `₹500`.
- [ ] **7. 4-Mode Payroll + `Pirn Winder` + EN/TA/HI Print Slips:** Matches Hand Check #3 and renders Tamil & Hindi cleanly in print preview.
- [ ] **8. `<ConfirmVoidModal>`, Human Audit Log, Unused Loom Delete & Exports:** Voiding shifts/slips/deliveries/expenses/EB readings removes items and writes readable `Before`/`After` entries in `/audit-log`; unused looms delete cleanly; CSV/DB exports download intact.

---

## 6. Change Log (Updated After Every Milestone)

- **2026-11-17 (Google Antigravity Remote Agents Cloud Compatibility):** Prepared standalone Git-ready copy in `git project/` (leaving original `loomos/` completely untouched): added POSIX cloud bootstrapper (`scripts/remote_setup.sh`), Linux launchers (`scripts/start_remote_demo.sh` & `scripts/start_remote.sh`), on-demand AITEX/TILDA dataset fetcher (`backend/scripts/fetch_vision_datasets.py`), relative-to-`BACKEND_ROOT` path resolution + optional `GEMINI_API_KEY` / `LOOMOS_DATABASE_URL` settings in `backend/app/core/config.py`, single-port static SPA fallback in `backend/app/main.py`, Vite 6 cloud host allowance (`allowedHosts: true` + `VITE_API_PROXY_TARGET`) in `frontend/vite.config.ts`, relaxed `bcrypt`/`pytest` upper bounds in `backend/requirements.txt` + `backend/requirements-phase2-4.txt`, hardened `.gitignore` + `.gitattributes`, and added root `README.md`, `AGENTS.md`, and `backend/tests/test_remote_compatibility.py`.
- **2026-11-17 (Phase 1 UX & 5-Loom Shuttle Feedback Pass):** Addressed all 29+3 browser-test findings across backend and frontend: added migration [f42b7c9d1a02_add_pirn_winder_worker_role.py](file:///d:/project%20in%20antigravity/loomos/backend/alembic/versions/f42b7c9d1a02_add_pirn_winder_worker_role.py) (`PIRN_WINDER` role) and `shifts_per_day` in [shifts.py](file:///d:/project%20in%20antigravity/loomos/backend/app/routers/shifts.py), added unused loom hard-delete (`DELETE /api/v1/looms/{loom_id}`) in [masters.py](file:///d:/project%20in%20antigravity/loomos/backend/app/routers/masters.py), auto-dismissed open `RATE_UNDERPAYMENT` alerts on challan void in [finance.py](file:///d:/project%20in%20antigravity/loomos/backend/app/routers/finance.py), reworked [seed_demo_cli.py](file:///d:/project%20in%20antigravity/loomos/backend/scripts/seed_demo_cli.py) to **5 shuttle looms (`S-01`..`S-05`, `< 30 m/shift`)** with relative Weekly/Monthly data & closed `P5` EB bill (`₹7,560.00`), removed formula wording from [dashboard_service.py](file:///d:/project%20in%20antigravity/loomos/backend/app/services/dashboard_service.py) & [DashboardPage.tsx](file:///d:/project%20in%20antigravity/loomos/frontend/src/pages/DashboardPage.tsx), unified UI dates to `DD/MM/YYYY` (`formatDateDMY` / `formatDateTimeIST`) and shift durations to `HH.MM` hours (`formatHoursFromMins`, e.g. `23.20 out of 24.00 shift hrs ran` in [client.ts](file:///d:/project%20in%20antigravity/loomos/frontend/src/api/client.ts)), hid non-input carets via `caret-color: transparent` in [index.css](file:///d:/project%20in%20antigravity/loomos/frontend/src/index.css) + `select-none` nav in [AppShell.tsx](file:///d:/project%20in%20antigravity/loomos/frontend/src/components/AppShell.tsx), built [ConfirmVoidModal.tsx](file:///d:/project%20in%20antigravity/loomos/frontend/src/components/ConfirmVoidModal.tsx) replacing `window.prompt()` across pages, switched `/today` to `[ ● Running | ■ Stopped ]` + 3-column Counter + mid-shift `2nd Beam (Mid-Shift)` swap in [TodayShiftPage.tsx](file:///d:/project%20in%20antigravity/loomos/frontend/src/pages/TodayShiftPage.tsx), restricted Setup/Looms to Shuttle Powerlooms with inline RPM edit & labelled fields, simplified Workers to single name + `Weaver | Pirn Winder | Helper`, added readable JSON formatting in [AuditLogPage.tsx](file:///d:/project%20in%20antigravity/loomos/frontend/src/pages/AuditLogPage.tsx), and updated `appSubtitle` in [translations.ts](file:///d:/project%20in%20antigravity/loomos/frontend/src/i18n/translations.ts). Re-seeded `loomos_demo.db`; verified **`npm run build` passed (`4.28s`)**, **`pytest -v` 18/18 passed (`21.28s`)**, and live LAN probe `http://10.45.222.244:5173/` (`200`).
- **2026-11-17 (Demo Credential Update & Backend-Restart Guard):** Changed demo Owner login to `welcome123` / `welcome123` across [seed_demo_cli.py](file:///d:/project%20in%20antigravity/loomos/backend/scripts/seed_demo_cli.py), [Start_LOOMOS_DEMO.bat](file:///d:/project%20in%20antigravity/loomos/Start_LOOMOS_DEMO.bat), [test_phase1_dashboard_and_demo_safety.py](file:///d:/project%20in%20antigravity/loomos/backend/tests/test_phase1_dashboard_and_demo_safety.py), and `WHAT_I_DID.md`; also fixed [AuthContext.tsx](file:///d:/project%20in%20antigravity/loomos/frontend/src/context/AuthContext.tsx) & [App.tsx](file:///d:/project%20in%20antigravity/loomos/frontend/src/App.tsx) so an unreachable/restarting backend shows a `Retry Connection` screen instead of falsely redirecting to `/setup`. Re-seeded `loomos_demo.db`; verified **`pytest` 17/17 passed (`30.19s`)** and live `welcome123` login.
- **2026-11-17 (Phase 1 Validation & Tamil Login/Setup Polish):** Added app-wide red highlight styling (`form.was-validated :invalid` & `.field-invalid` in [index.css](file:///d:/project%20in%20antigravity/loomos/frontend/src/index.css) + capture listeners in [App.tsx](file:///d:/project%20in%20antigravity/loomos/frontend/src/App.tsx)), explicit inline red field errors on [LoginPage.tsx](file:///d:/project%20in%20antigravity/loomos/frontend/src/pages/LoginPage.tsx), [SetupPage.tsx](file:///d:/project%20in%20antigravity/loomos/frontend/src/pages/SetupPage.tsx), and [TodayShiftPage.tsx](file:///d:/project%20in%20antigravity/loomos/frontend/src/pages/TodayShiftPage.tsx), positive `min`/`required` guards on [BeamsPage.tsx](file:///d:/project%20in%20antigravity/loomos/frontend/src/pages/BeamsPage.tsx), [DeliveriesPage.tsx](file:///d:/project%20in%20antigravity/loomos/frontend/src/pages/DeliveriesPage.tsx), and [PayrollPage.tsx](file:///d:/project%20in%20antigravity/loomos/frontend/src/pages/PayrollPage.tsx), plus full English/Tamil (`கடவுச்சொல்`) labels & validation hints in [translations.ts](file:///d:/project%20in%20antigravity/loomos/frontend/src/i18n/translations.ts) and [PasswordInput.tsx](file:///d:/project%20in%20antigravity/loomos/frontend/src/components/PasswordInput.tsx). Verified **`npm run build` (`tsc -b && vite build`) passed (`3.40s`)**.
- **2026-11-17 (Phase 1 UI Polish):** Renamed seeded demo shed `unit_name` from `Sri Lakshmi Weaving Works (DEMO)` to `LOOMOS` ([seed_demo_cli.py](file:///d:/project%20in%20antigravity/loomos/backend/scripts/seed_demo_cli.py)), avoided duplicate sidebar subtitle in [AppShell.tsx](file:///d:/project%20in%20antigravity/loomos/frontend/src/components/AppShell.tsx), updated `/setup` shed placeholder, and added a reusable show/hide password eye toggle ([PasswordInput.tsx](file:///d:/project%20in%20antigravity/loomos/frontend/src/components/PasswordInput.tsx)) across `LoginPage.tsx`, `SetupPage.tsx`, and `TeamUnitTab.tsx`. Re-seeded `loomos_demo.db`; verified **`pytest` 17/17 passed (`28.37s`)** and **`npm run build` passed (`2.81s`)**.
- **2026-11-17 (Delivery Phase 1 Complete):** Added isolated `loomos_demo.db` CLI seeder ([seed_demo_cli.py](file:///d:/project%20in%20antigravity/loomos/backend/scripts/seed_demo_cli.py)) with production safety guard, `Start_LOOMOS.bat` + `Start_LOOMOS_DEMO.bat` LAN launchers, `DEMO DATA` banner (`DemoBanner.tsx`), Owner/Supervisor `/dashboard` with Availability/Performance/`A×P` Utilization/conditional OEE & financial P&L (`dashboard_service.py`, `DashboardPage.tsx`), and UI soft-delete void buttons on `DeliveriesPage.tsx` & `TodayShiftPage.tsx`. Realigned roadmap to approved 5-phase browser-first order (`Phase 2: Vision AI & /inspect` next). Verified **`pytest` 17/17 passed (`28.88s`)**, **`npm run build` passed (`4.55s`)**, and live proxy/API serving on `0.0.0.0:8000` & `0.0.0.0:5173`.
- **2026-11-17 (Phase 1 + Vision Gate + Build Step 1):** Completed 18 research/architecture docs in `loomos/docs/`, verified 20 academic DOIs and 6 competitors, passed Week 1 AITEX Vision Gate (`ResNet-18 + CLAHE` `0.481` Recall / `0.565` Defect-F1 / `0.950` AUC), locked v3 scope + Choice 1 LAN + `client_uuid`, built Step 1 backend (`pytest` 9/9 passed) & frontend (`npm run build` passed), and consolidated project documentation into this single file.
