# Project Proposal (For B.Sc. Computer Technology Approval)

**Project Title:**  
**LOOMOS: A Mobile-First Production Management and Analytics Platform with Explainable Smartphone-Based Fabric Defect Detection for Small Powerloom Job-Work Units**

**Degree:** B.Sc. Computer Technology (Final Year Project, 2026–2027)  
**Methodology:** Design Science Research (DSR) + Single-Unit Case Study + Experimental ML Benchmarking  
**Tech Stack:** React (TypeScript, Vite, Tailwind CSS, PWA), FastAPI (Python), SQLite / PostgreSQL, PyTorch + ONNX Runtime + Grad-CAM, Scikit-Learn / Statsmodels (100% Free & Open-Source)

---

## 1. Background & Problem Statement
Small decentralized powerloom units (typically 12–50 looms) form the backbone of Tamil Nadu's weaving clusters (Somanur, Palladam, Coimbatore, Erode). Most operate on thin-margin **job-work contracts** (~₹6/m revenue, ~₹2/m net profit), yet still manage shift production, weaver wages, advances, trader deliveries, and fabric quality using paper notebooks. This causes:
1. Time-consuming and error-prone weekly wage/advance settlements (supporting per-metre, per-shift, and per-loom-shift pay).
2. Unnoticed unilateral trader rate cuts (25–50 paise/m) and unclear beam completion schedules.
3. Unpredictable bi-monthly electricity (TANGEDCO LA3A2) slab jumps above 1,500 units.
4. Subjective manual cloth quality inspection with no visual proof or loom/weaver traceability.

Meanwhile, existing textile ERPs charge recurring SaaS fees or target large mills, IoT loom monitors require costly sensors unsuitable for legacy shuttle looms, and academic deep learning defect detectors are rarely tested on consumer smartphone images inside real small weaving sheds.

---

## 2. Aim & Research Questions
**Aim:** Design, build, and empirically evaluate a zero-cost, mobile-first production management and analytics system integrating smartphone-based explainable deep learning fabric defect detection for small job-work powerloom units.

- **RQ1 (Operations):** Can a mobile-first system reduce record-keeping time and calculation discrepancies compared to paper notebooks in a 20-loom unit?
- **RQ2 (Model Benchmark):** Which lightweight CNN (`Custom CNN`, `MobileNetV3-Small`, `ResNet-18`, `EfficientNet-B0`) provides the best accuracy-to-latency trade-off on public textile defect benchmarks (AITEX, TILDA)?
- **RQ3 (Domain Shift & XAI):** How effectively do models trained on public industrial benchmarks generalize to real smartphone grey-fabric photos (`LOOMOS-Shed`), how much does small-sample fine-tuning (`10/25/50` images/class) improve performance, and does **Grad-CAM** localize defects visually?
- **RQ4 (Forecasting & Anomalies):** Do simple, explainable forecasting models outperform naive baselines on real historical delivery and TANGEDCO electricity records?
- **RQ5 (Usability):** Do shed owners and supervisors rate the system usable on the System Usability Scale (SUS)?

---

## 3. System Modules
1. **Job-Work Operations Core:** Dynamic `N`-loom onboarding, bilingual UI & payslips (`EN | தமிழ்`), weavers/helpers (4 dated wage modes), warp beams & weft kg wastage check, <90-sec shift grid with `Power Cut` duration logging, delivery challans, **Trader Rate-Cut Checker**, immutable `audit_logs`, and soft deletes on all financial records.
2. **Analytics & Forecasting Engine:** Beam completion ETA, **Holt's Exponential Smoothing vs Naive baseline** weekly output forecast, DB-driven **TANGEDCO EB Bill Predictor** adjusted for logged power cuts, and transparent **`z-score`/IQR anomaly alerts**.
3. **Explainable Vision Module:** Photo-based defect classification + **Grad-CAM heatmap overlay** exported via ONNX Runtime, built-in labelled `"AITEX Reference Sample (demo only)"` examples, held-out test metrics, and full ground-truth saving of every reviewed photo (`Defect` or `Clean`).

---

## 4. Datasets & Evaluation Plan
- **Public Benchmarks:** **AITEX Fabric Image Database** (`doi:10.2478/aut-2019-0035`) and **TILDA Textile Texture Database** (Uni Freiburg).
- **Local Datasets:** Real operational history from an active 20-loom unit (41 weekly deliveries totaling 2,51,455 m + 5 TANGEDCO bills) and **LOOMOS-Shed** (planned 500+ smartphone photos of grey cloth from local weaving sheds, anonymized).
- **Validation:** Pre/post task timing, 3–4 week shed pilot, strip-level zero-leakage ML cross-validation, historical forecasting back-tests (MAE/MAPE), automated `pytest` + Playwright tests, and SUS usability testing (`n = 5–8` industry participants).
