# Research Methodology, Interview Guide & Evaluation Plan (v3)

**Last updated:** 2026-11-17

---

## 1. Research Design: Design Science Research (DSR) + Case Study

LOOMOS follows **Design Science Research (DSR)** (Hevner et al., 2004; Peffers et al., 2007) paired with a **single-unit case study** and **quantitative ML/forecasting experiments**.

---

## 2. Measurable Evaluation Plan (RQ1 – RQ5)

| RQ | Metric | Baseline / Comparator | Honest Reporting Standard |
|---|---|---|---|
| **RQ1** (Ops Efficiency) | Shift entry time (sec), weekly payroll time (min), arithmetic discrepancy count | Pre-deployment notebook timings (Week 1–2) vs LOOMOS pilot (Week 9) | Descriptive before/after comparison; single-unit limitation stated |
| **RQ2** (Public Vision Benchmark) | **Held-out test split** Precision, Recall, F1, Confusion Matrix, CPU ms/image, Model MB + explicit **failure case gallery** | `Custom CNN` vs `MobileNetV3-Small` vs `ResNet-18` vs `EfficientNet-B0` | Strict **strip-level zero-leakage split**; training accuracy/confidence **never** presented as accuracy proof |
| **RQ3** (Domain Shift & Fine-Tuning) | Zero-shot vs fine-tuned Macro-F1 on real reviewed shed photos (`LOOMOS-Shed`, saving both `Defect` and `Clean` samples) + Grad-CAM visual check | Public-trained model tested directly on shed phone photos vs fine-tuned (`10/25/50` photos/class) | Honest reporting of domain-shift drops and misclassifications |
| **RQ4** (Forecasting & Outliers) | Weekly output & power-cut-adjusted EB kWh **MAE / MAPE**; `z-score`/IQR anomaly flag precision | **Naive baseline (last-week / mean)** vs **Holt's Exponential Smoothing** (and EB slab regression) | Rolling back-test on historical deliveries & real EB bills |
| **RQ5** (Usability) | System Usability Scale (**SUS**, 0–100) + post-task feedback | Bangor et al. (2008) thresholds (~68 avg, ≥70 good) | 5–8 participants with informed consent & anonymization |
