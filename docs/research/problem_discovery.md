# Problem Discovery and Prioritisation

**Last updated:** 2026-11-17

Using industry analysis, local unit data (`Powerloom_Business_Plan.docx`), and 2025 Somanur–Palladam sector reporting, six software-solvable problems were evaluated. Per the project brief, problems are ranked by **severity, frequency, business impact, willingness to adopt, technical feasibility, research potential, and validation availability**—not programming ease.

---

## 1. Detailed Problem Profiles

### P1. Undetected / Unattributed Fabric Defects & Subjective Quality Inspection
- **Who experiences it:** Loom owners, supervisors, weavers, and job-work traders.
- **Cause:** Grey cloth (*Gada*) is inspected manually under variable shed lighting without systematic defect logging per loom or weaver; subtle oil stains, broken picks, and holes slip through to the trader or cause disputes without root-cause traceability.
- **Frequency:** Daily across shifts (requires field verification for exact % incidence in the target unit).
- **Current solution:** Visual eye-check during folding or at trader godown.
- **Why insufficient:** Fatiguing, subjective, creates no historical defect log linking defect types back to specific looms (e.g., a loom leaking oil or dropping warp ends) or weavers, and provides no visual proof.
- **Operational/financial impact:** Piece rejections, rate deductions, damaged trader trust.
- **Can software improve it?** Yes—smartphone-photo deep learning classification with Grad-CAM visual heatmaps linked directly to `loom_id`, `beam_id`, and `weaver_id`.
- **Measurable metrics:** Model Macro-F1 & per-class recall on benchmark and local `LOOMOS-Shed` photos; zero-shot vs fine-tuned cross-domain accuracy gap (RQ3); defect count tracked by loom/weaver.

### P2. Unverified Job-Work Rate Cuts & Unreconciled Trader Delivery Balances
- **Who experiences it:** Job-work loom owners.
- **Cause:** Deliveries and payments are tracked informally in paper diaries/WhatsApp; traders sometimes pay 25–50 paise/m below agreed rates or leave pending balances unclear across multiple beams.
- **Frequency:** Weekly (every fabric delivery cycle and settlement).
- **Current solution:** Paper notebooks and manual calculator checks.
- **Why insufficient:** At ~₹2.03/m net profit, an unnoticed ₹0.50/m shortfall wipes out ~25% of margin. Manual cross-checking across 40+ weekly deliveries and multiple sorts is error-prone.
- **Operational/financial impact:** Direct margin leakage (up to thousands of rupees per month even in a 20-loom shed).
- **Can software improve it?** Yes—deterministic agreed-rate × delivered-metres ledger paired with an automatic **Trader Rate & Payment Checker** flagging every paise discrepancy immediately.
- **Measurable metrics:** Owner reconciliation time (minutes, before vs after); count of unflagged rate/balance mismatches caught during pilot.

### P3. Error-Prone Shift Production Logging, Weaver Wage & Advance Accounting
- **Who experiences it:** Supervisors and loom owners; weavers (indirectly through pay trust).
- **Cause:** Shift-wise loom metres, stoppages, mixed wage rules (per loom-shift, per shift, or per metre), and weekly advances (*uthaav*) are written in paper registers and summed manually every weekend.
- **Frequency:** Twice daily (data entry) + weekly (payroll settlement).
- **Current solution:** Paper tally books or generic spreadsheet/calculator.
- **Why insufficient:** Manual summation errors, lost advance slips, and inability to spot sudden loom underperformance or impossible entries (e.g., typing 95 m instead of 35 m in a shift).
- **Operational/financial impact:** Overpaid/underpaid wages causing worker friction, hours spent weekly on manual arithmetic, undetected bad entries.
- **Can software improve it?** Yes—mobile-first <2-minute shift grid, deterministic multi-mode wage engine, shareable payslips, plus anomaly/outlier flagging (`z-score`/IQR vs Isolation Forest).
- **Measurable metrics:** Shift entry time, weekly payroll calculation time (before vs after), error/discrepancy rate, outlier detection precision/recall (RQ1, RQ5).

### P4. Lack of Visibility into Beam Completion Dates & Short-Term Output/Electricity Costs
- **Who experiences it:** Loom owners managing trader schedules and cash flow.
- **Cause:** Without cumulative metre subtraction per beam and rolling daily efficiency per loom, owners guess beam fall dates and cannot anticipate when bi-monthly TANGEDCO LA3A2 consumption crosses the ₹5.30/unit slab.
- **Frequency:** Weekly / bi-monthly billing cycle.
- **Current solution:** Mental estimation ("around next Thursday") and reacting when the EB bill arrives.
- **Why insufficient:** Missed delivery commitments hurt trader relationships; unexpected ₹32k–₹44k summer/peak EB bills strain cash flow; delivery timing lags obscure true cost per metre.
- **Operational/financial impact:** Poor scheduling between beams (idle loom downtime waiting for the next beam) and cash-flow surprises.
- **Can software improve it?** Yes—beam completion estimator + calibrated weekly output forecast + TANGEDCO slab EB predictor back-tested on the unit's 41 real deliveries and 5 EB bills.
- **Measurable metrics:** Back-test MAE and MAPE against a naive baseline (RQ4).

### P5. Unprioritised Loom Maintenance Without Hardware Sensors
- **Who experiences it:** Loom owners and fitters/mechanics.
- **Cause:** Shuttle looms lack electronic counters or IoT sensors; gradual drops in shift efficiency, rising stoppages, or repeat defects on a specific loom go unnoticed across dozens of paper pages.
- **Frequency:** Ongoing / weekly.
- **Current solution:** Reactive repair only after a breakdown or major fabric spoil.
- **Why insufficient:** Commercial IoT loom monitors (e.g., TrackWeaving) require hardware retrofitting unsuitable for older shuttle looms.
- **Operational/financial impact:** Lost production hours (~10.2% baseline efficiency gap below theoretical 60 m/day = ~6.15 m/loom/day potential upside).
- **Can software improve it?** Yes—an explainable **Loom Health Score (0–100)** derived purely from logged efficiency trends, stop reasons, and defect incidence.
- **Measurable metrics:** Number of recurring underperforming looms surfaced during pilot and validated by the owner.

### P6. Weft Yarn Consumption vs. Fabric Delivered Reconciliation Gaps
- **Who experiences it:** Job-work loom owners and traders.
- **Cause:** Verifying whether weft yarn supplied (kg) aligns with theoretical fabric weight (count, pick, width, waste allowance) is rarely calculated per beam in small units.
- **Frequency:** Per completed beam (every few weeks).
- **Current solution:** Accepted on trader trust unless major discrepancy is obvious.
- **Why insufficient:** Leaves owners vulnerable to unfair shortage claims or unnoticed yarn pilferage/excess waste.
- **Operational/financial impact:** Unverified deductions at order closure.
- **Can software improve it?** Yes—deterministic standard textile yarn-consumption calculator (Should-have scope).

---

## 2. Prioritisation Matrix (1–5 Scale per Criterion; Higher = Stronger Case)

| Problem | Severity | Freq. | Impact | Adoption Readiness | Tech Feasibility | Research Potential | Validation Access | Total (/35) | Priority |
|---|---|---|---|---|---|---|---|---|---|
| **P1. Fabric Defect Inspection (Phone + XAI)** | 4 | 4 | 4 | 4 | 4 | **5** | 4 | **29** | **Rank 1 (Primary ML Research)** |
| **P3. Shift Production, Wages & Outlier Checks** | **5** | **5** | **5** | **5** | **5** | 4 | **5** | **34** | **Rank 1 (Primary Ops Core)** |
| **P2. Trader Rate & Payment Checker** | **5** | 4 | **5** | **5** | **5** | 3 | **5** | **32** | **Rank 2 (Must-Have Diff.)** |
| **P4. Beam, Output & EB Slab Forecasting** | 4 | 4 | 4 | 4 | **5** | **4** | **5** | **30** | **Rank 3 (Must-Have Analytics)** |
| **P5. Sensor-Free Loom Health Score** | 3 | 4 | 4 | 4 | **5** | 3 | 4 | **27** | **Rank 4 (Should-Have)** |
| **P6. Yarn Reconciliation** | 3 | 3 | 3 | 3 | **5** | 2 | 3 | **22** | **Rank 5 (Should-Have)** |

**Synthesis:** Combining **P3 + P2 + P4** (Operations + Forecasting Core) with **P1** (Smartphone Fabric Defect Detection + Grad-CAM) creates a cohesive product where the daily operational workflow feeds quality traceability, financial protection, and rigorous academic research—without turning into a bloated multi-industry ERP.
