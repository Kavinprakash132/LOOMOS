# Decision Log, Risk Register, Assumptions & Final Feasibility Scorecard

**Last updated:** 2026-11-17

---

## 1. Auditable Decision Log

| ID | Decision | Options Considered | Rationale & Trade-Off |
|---|---|---|---|
| D-01 | **Replace synthetic predictive maintenance with Fabric Defect Vision + Data-Driven Shed Analytics** | (a) Tabular maintenance on UCI AI4I 2020; (b) Photo defect detection + historical forecasting & anomaly detection | UCI AI4I 2020 is synthetic milling data (Matzka, 2020) and showed 0.63 recall; shuttle looms lack vibration/torque sensors. Photo defect inspection + Grad-CAM + shed analytics match real hardware & data availability. |
| D-02 | **Photo-upload/capture defect inspection (no live video)** | (a) Continuous camera stream; (b) Photo-on-demand during inspection | Avoids fixed shed camera mounts, lighting wiring, and high CPU load while remaining directly testable in a 20-loom shed and repeatable in the viva. |
| D-03 | **Flexible per-weaver wage rules** | (a) Per-metre only; (b) Per metre / per shift / per loom-shift | `Powerloom_Business_Plan.docx` shows ₹60/loom/shift while local clusters also use per-metre and helper weekly rates; supporting all three makes LOOMOS usable in real sheds. |
| D-04 | **Modular monolith (FastAPI + React PWA + SQLite WAL)** | (a) Microservices + cloud Postgres; (b) Local FastAPI + SQLite + React PWA | ₹0 hosting, private local shed data, simple backup, PostgreSQL-compatible schema for later scaling, zero Play Store overhead on Android. |
| D-05 | **Strict separation of ML from financial truth** | (a) Inline ML adjustments; (b) Deterministic ledger + advisory ML | Prevents a model misclassification or noisy forecast from corrupting weaver pay or trader balances. |

---

## 2. Assumptions Log (To Validate in Week 1–2)

| ID | Assumption | Status | Validation Plan |
|---|---|---|---|
| A-01 | Pilot runs on current 20-loom unit (50-loom shed is future expansion) | Pending user confirmation | Confirm with owner before schema seeding |
| A-02 | Supervisor has Android phone and ≤2 min shift entry time is acceptable | Unverified | Week 1 shed floor interview + timing trial |
| A-03 | 500+ grey cloth photos (clean + defective) can be captured in Weeks 1–4 | Unverified | Start photo protocol Week 1; friend's 100-loom shed as secondary source; binary defect fallback if rare classes lack samples |
| A-04 | Historical 41 weekly deliveries exist in a table/list usable for backfill | Partially verified (`Powerloom_Business_Plan.docx` summarizes totals by EB period) | Obtain raw 41-row list/notebook from owner in Week 1–2 |
| A-05 | Shed has laptop/PC + Wi-Fi or phone hotspot for local PWA serving | Pending confirmation | Confirm in Week 1; free cloud tier (Render + Vercel) as fallback |

---

## 3. Section 14 — Final Decision Framework (Evidence-Based Scorecard, 1–10)

| Criterion | Score (/10) | Evidence-Backed Justification |
|---|---|---|
| **1. Problem Importance** | **8.5** | Real 20-loom profit is ~₹2.03/m (`Powerloom_Business_Plan.docx`); 2025 Somanur/Palladam 33-day strike & reported 25–50 paise rate cuts prove tiny unflagged discrepancies directly threaten survival. |
| **2. Research Gap Strength** | **8.0** | Commercial apps (Loomiro, TexFo, Pinakexa) handle bookkeeping, so gap is not "no ERP exists." Genuine gap lies in (a) smartphone domain-shift defect inspection (`RQ3`), (b) short-series forecasting/TANGEDCO slab prediction (`RQ4`), and (c) empirical DSR evaluation inside a TN job-work shed (`RQ1`, `RQ5`). |
| **3. Market Relevance** | **8.0** | Tamil Nadu hosts ~5.63–5.68 lakh powerlooms (~23% of India's ~24.86 lakh looms), heavily decentralized in job-work belts around Coimbatore, Tiruppur, and Erode. |
| **4. Customer Demand Evidence** | **6.5** | Strong operational evidence from the owner's own business plan and willingness to deploy internally; broader external demand across *other* sheds is hypothesized until Week 1–2 peer owner interviews are completed (score intentionally conservative). |
| **5. Differentiation** | **7.5** | Free self-hosted ownership + TN job-work rate-cut audit + TANGEDCO slab predictor + camera Grad-CAM defect traceability differentiate LOOMOS from Surat-focused ₹999/mo SaaS (Loomiro) and hardware-bound IoT (TrackWeaving). |
| **6. Technical Feasibility** | **8.5** | FastAPI, React, SQLite, PyTorch/ONNX, and statsmodels are mature OSS tools; hardware on hand (10-thread CPU laptop, Python 3.13/3.14, Node 24) already verified. |
| **7. Academic Contribution** | **8.5** | DSR methodology + cross-domain CNN benchmark (`RQ2`/`RQ3`) + Grad-CAM XAI + real-history forecasting back-test (`RQ4`) + SUS case evaluation (`RQ5`) meets B.Sc. CT & IEEE/conference rigor. |
| **8. Evaluation Feasibility** | **8.0** | Immediate access to an operating 20-loom shed, 41 deliveries, and 5 real TANGEDCO bills enables real pre/post timings and back-testing, though sample size (`n=1` shed) limits statistical generalization. |
| **9. Cost Feasibility** | **9.5** | ₹0 software licenses, ₹0 cloud bills (local Wi-Fi deployment), zero hardware sensors. |
| **10. Implementation Complexity** | **6.5** | Riskiest dimension: 10-week schedule for a full-stack PWA + 4-model ML benchmark + shed pilot is ambitious for one undergraduate, requiring strict MoSCoW discipline. |

**Overall Weighted Verdict:** **Proceed with LOOMOS** (avg ~7.9/10), conditional on passing the Week 1 Vision Gate and enforcing strict MoSCoW prioritization.

---

## 4. Three Biggest Reasons LOOMOS Could Fail & Reversal Criteria

1. **Scope Overload in a 10-Week Window:** Trying to build every ERP bell-and-whistle alongside ML experiments causes half-finished software before January 2027. *Mitigation:* Freeze Must-Have MVP strictly; drop Could/Should items immediately if Week 4 slips.
2. **Insufficient Local Defect Photos (`LOOMOS-Shed`) / Severe Lighting Failure:** If the shed produces too few defective pieces during December or phone glare ruins texture detail, multi-class classification collapses. *Mitigation:* Start collection in Week 1, include friend's 100-loom unit, enforce binary (`Defect / Clean`) fallback, and report honest failure analysis.
3. **Floor Adoption Friction (Supervisor Reverts to Notebooks):** If daily entry takes >3 minutes or phone/Wi-Fi connectivity drops inside the metal shed, the pilot produces empty data. *Mitigation:* Co-design the 2-minute grid with the supervisor in Week 1 and allow owner evening batch entry as backup.

**What Evidence Would Change Our Recommendation:**
- If **Week 1 Vision Gate** yields low discriminative performance on AITEX/TILDA **and** owner interviews show defect photos are impractical to collect before delivery, **drop vision inspection** and make **production anomaly detection + forecasting on backfilled shift/delivery records** the primary ML core.
- If **Week 1 interviews** show the shed lacks a laptop/smartphone workflow at all, shift from live shed deployment to a **retrospective historical-data prototype + lab usability evaluation**.
