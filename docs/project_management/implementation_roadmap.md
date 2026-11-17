# 10-Week Implementation & Research Roadmap (v3)

**Window:** 18 Nov 2026 – 26 Jan 2027 (+ Feb 2027 buffer)

| Week | Dates | Engineering Deliverables | Research & ML Deliverables | Academic Docs |
|---|---|---|---|---|
| **1** | 18–24 Nov | Agree Phone-to-Laptop Architecture + v3 scope | Vision Gate **DONE** (`ResNet-18 + CLAHE` `0.950` AUC); shed interviews & **baseline notebook timings**; start `LOOMOS-Shed` photo collection | Submit 1-page Proposal |
| **2** | 25 Nov–1 Dec | **Build Step 1:** SQLite WAL schema, migrations, DB tariff slabs, `audit_logs` + soft deletes, Auth/RBAC, 3-step `/setup` wizard, bilingual i18n (`EN/TA`), Masters + `pytest` | Primary Ministry of Textiles check, **import 41 deliveries & 5 EB bills** | Chapters 1–2 |
| **3** | 2–8 Dec | **Build Step 2 (Part A):** Beams, Weft kg wastage check, Shift Grid (auto-date, carry-forward, direct/counter, `Power Cut` stop reason) | Train 4 CNNs on AITEX/TILDA (**RQ2**, held-out test metrics + failure cases) | SRS |
| **4** | 9–15 Dec | **Build Step 2 (Part B):** 4-mode Payroll + bilingual payslips, Deliveries + Rate Checker, Audit Log viewer, CSV Exports + Full DB Backup + `pytest` financial tests | Collect 500+ shed photos (`LOOMOS-Shed`) | System Design & ER/UML |
| **5** | 16–22 Dec | **Build Step 3 (Part A):** `/inspect` ONNX + Grad-CAM + labelled `"AITEX Reference Sample (demo only)"` + save every reviewed photo (`Defect` or `Clean`) | Label `LOOMOS-Shed` photos; run **RQ3 cross-domain & fine-tuning experiments** | — |
| **6** | 23–29 Dec | **Build Step 3 (Part B):** **EB Predictor** (with power-cut impact), **Beam ETA**, **Holt's Weekly Forecast vs Naive Baseline**, **`z-score`/IQR Anomaly Alerts**, Dashboard | Finalize RQ2/RQ3/RQ4 tables & failure cases | ML & Forecasting Chapter |
| **7** | 30 Dec–5 Jan | **Start shed pilot** + bug fixes | Log real floor defects & anomalies | Implementation Chapter |
| **8** | 6–12 Jan | **Build Step 4:** **Excel (`.xlsx`) & PDF exports** (EN/TA payslips & statements), Playwright mobile+desktop E2E suite, `Start_LOOMOS.bat`, *(basic What-If Simulator ONLY if ahead of schedule)* | Verify alert & rate-audit precision with owner | Testing Chapter |
| **9** | 13–19 Jan | Pilot continued *(around Pongal shutdown)* | **Post-pilot timings, SUS (`n=5–8`)** | Results & Discussion |
| **10** | 20–26 Jan | Freeze v1.0, user manual | Compile full thesis, slides, demo video | Final Report |
| **Buffer** | 27 Jan–Feb | Fixes / optional What-If polish | Optional IEEE-style student paper | Viva Prep |
