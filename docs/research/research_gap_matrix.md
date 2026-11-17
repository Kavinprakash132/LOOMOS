# Research Gap Matrix & Formal Research Framing

**Last updated:** 2026-11-17

---

## 1. Research Gap Matrix

| Existing Research / Commercial Solution | What It Addresses | Documented Limitations | Research Opportunity for LOOMOS |
|---|---|---|---|
| **Academic Fabric Defect DL** (Silvestre-Blanes et al., 2019; Nasim et al., 2024; Mao & Hong, 2025; Dhali et al., 2025) | High classification/detection accuracy on controlled industrial camera datasets (AITEX, TILDA) + Grad-CAM interpretability | Models assume controlled lighting/line-scan optics; cross-domain transfer to **handheld smartphone photos in small decentralized shuttle sheds** is under-evaluated, and models sit isolated from factory ERP/wage records | **RQ2 & RQ3:** Measure domain shift from public benchmarks (AITEX/TILDA) to smartphone grey-fabric photos (`LOOMOS-Shed`) + fine-tuning curve (`10/25/50` local shots) + link Grad-CAM results directly to `loom_id` & `weaver_id` |
| **Indian Textile ERPs** (Loomiro, TexFo, Pinakexa, eManage, VastraApp) | Beam loading, production logging, piece-rate wages, GST billing, taka inventory | Recurring SaaS fees (₹999+/mo or custom enterprise pricing); often aimed at Surat waterjet/airjet taka sales or larger mills; **no smartphone CNN defect detection**; no TANGEDCO LA3A2 slab predictor | Free, self-hosted, local-first PWA tailored around **TN job-work economics**: trader rate-cut audit, TANGEDCO slab EB forecasting, multi-mode weaver wages, and integrated vision inspection |
| **IoT Loom Monitoring** (TrackWeaving, iFactory AI) | Real-time automated RPM, stop reasons, and machine efficiency alerts | Requires hardware sensors on every loom—economically/mechanically unsuitable for 20-year-old mechanical shuttle looms | Software-only **statistical anomaly alerts (`z-score`/IQR) & power-cut impact tracking** derived purely from shift entries, at zero hardware cost |
| **Mobile Loom Ledger Apps** (e.g., Digital Diary Powerloom) | Replaces paper pocketbook for daily shift metres, advances, and payslip PDFs | Purely retrospective bookkeeping; **no production/EB forecasting, no trader rate-cut audit, no quality inspection** | Combine <2-min shift entry with explainable **back-tested short-horizon forecasting (RQ4)** calibrated on real delivery & EB history |
| **SME Digital Adoption Studies** (Pandey et al., 2024; Alayón et al., 2022; Kamble et al., 2024) | Identifies high digital barriers (cost, complexity, skill mismatch) in Indian manufacturing & powerloom SMEs | Mostly survey-based descriptive studies; few build and evaluate a live open-source DSR artefact inside an operating Tamil Nadu job-work unit | **RQ1 & RQ5:** Empirical Design Science Research case study measuring task time, accounting errors, and SUS inside an operating 20-loom unit |

---

## 2. Formal Research Framing

- **Research Problem:** Small decentralized powerloom job-work units in Tamil Nadu operate on narrow margins (~₹2/m) while relying on paper registers that cause calculation errors, miss unilateral trader rate cuts (25–50 paise/m), provide no short-term output or TANGEDCO electricity slab visibility, and lack traceable fabric quality inspection. Meanwhile, academic deep learning defect-detection models trained on lab/line-scan images lack empirical validation on smartphone photography in small sheds and remain disconnected from operational ERP workflows.
- **Research Aim:** To design, develop, and empirically evaluate **LOOMOS**, a zero-cost, mobile-first production management and analytics platform integrating explainable smartphone fabric defect detection for small job-work powerloom units.
- **Research Objectives:**
  1. Investigate workflows, adoption barriers, and competitive software gaps in Tamil Nadu job-work powerloom units.
  2. Design and implement a lightweight, modular mobile-first PWA and FastAPI system supporting job-work beams, flexible multi-mode weaver payroll (`per metre / per shift / per loom-shift`), trader rate-cut checking, and TANGEDCO LA3A2 EB slab modeling.
  3. Evaluate four lightweight CNN architectures on public textile defect benchmarks (`RQ2`) and quantify cross-domain transfer and few-shot fine-tuning gains on real shed smartphone photos (`LOOMOS-Shed`) with Grad-CAM (`RQ3`).
  4. Back-test explainable forecasting (weekly production & EB units) and anomaly-detection methods on historical shed records against naive baselines (`RQ4`).
  5. Evaluate operational efficiency (task time, error reduction) and usability (SUS) in a real 20-loom case-study pilot (`RQ1`, `RQ5`).
- **Expected Academic & Practical Contribution:**
  1. Verified open-source DSR software artefact ready for local use by small weaving units.
  2. Quantitative domain-shift & few-shot fine-tuning benchmark bridging industrial textile datasets (AITEX/TILDA) and smartphone shed photography (`LOOMOS-Shed`).
  3. Real-world empirical case study evaluating forecasting, anomaly detection, and usability in an active Tamil Nadu powerloom shed.
- **Scope & Limitations:** Single-unit descriptive case study (not statistically generalizable across all textile clusters); photo-based defect checking rather than continuous real-time machine vision; no automated IoT loom counters or GST tax filing.
