# Business Validation & Business Model

**Last updated:** 2026-11-17

---

## 1. Customer Discovery & Stakeholder Map

| Role | Who in a Small Job-Work Unit | Relationship to LOOMOS |
|---|---|---|
| **Primary Customer & Decision-Maker** | Shed Owner (e.g., family's 20-loom unit, expanding to 50 looms) | Decides adoption, uses financial/forecasting/rate-checker views, owns data |
| **Daily Floor User** | Shift Supervisor (or Owner acting as supervisor) | Enters daily shift metres, stop reasons, and cloth defect photos on Android |
| **Secondary Stakeholders** | Weavers (*Karigars*), Job-Work Traders, Loom Fitter/Mechanic | Weavers receive transparent weekly payslips; traders receive accurate delivery challans; fitter sees low-health looms |
| **Early Adopters** | Target family unit (20 looms) + peer units in the local cluster (e.g., friend's 100-loom unit) | Immediate real-world pilot without sales friction |

*(Note: No primary user interviews have been conducted yet; operational pain points beyond `Powerloom_Business_Plan.docx` and 2025 news reports are treated as hypotheses until Week 1–2 interviews are logged.)*

---

## 2. Business Model Canvas (Commercial Path Evaluation)

| Block | LOOMOS Evaluation |
|---|---|
| **Value Proposition** | Zero-subscription, phone-first job-work production ledger that protects thin ₹2/m margins by flagging trader rate cuts, automating mixed-mode weaver wages, forecasting beam completion & TANGEDCO EB slabs, and documenting cloth defects via phone camera + Grad-CAM. |
| **Customer Segments** | Small decentralized job-work powerloom and shuttleless rapier units (10–100 looms) in Tamil Nadu (Somanur, Palladam, Avinashi, Erode, Salem, Karur). |
| **Channels** | Open-source local install (Academic/Pilot); word-of-mouth through local powerloom associations, loom mechanics/fitters, and neighbouring shed owners. |
| **Customer Relationships** | Self-serve local PWA with optional one-time setup/training support. |
| **Revenue Streams *(Hypotheses until validated)*** | **Academic & Internal Business Release:** Free (₹0, MIT/open-source core). **Optional Post-Graduation Commercial Path:** (a) One-time local installation + custom migration fee (₹3,000–₹5,000), or (b) Low-cost cloud backup & support retainer (₹299–₹499/month, far below Loomiro's ₹999/mo). |
| **Key Resources** | Open-source stack (React, FastAPI, SQLite/PostgreSQL, ONNX Runtime), shed laptop/PC + Android smartphone, `LOOMOS-Shed` defect dataset. |
| **Key Activities** | Software maintenance, model fine-tuning per fabric weave type, local backup verification. |
| **Cost Structure** | Development cost: **₹0** (student built, OSS stack). Local shed hosting: **₹0**. Optional cloud VPS later: ~₹400–₹800/month if multi-shed SaaS is ever pursued. |

---

## 3. Bottom-Up Market Opportunity (Transparent Assumptions)

| Tier | Estimate | Basis & Verification Status |
|---|---|---|
| **TAM (India Decentralized Powerloom Units)** | **>3.85 lakh units** (~24.86 lakh looms) | **Secondary industry figure** (IBEF citing Ministry of Textiles; primary PDF check pending). |
| **SAM (Tamil Nadu Powerloom Units)** | **~75,000 – 95,000 units** *(Assumed estimate)* | **Verified state loom count:** ~5.63–5.68 lakh looms in TN. **Assumed average unit size:** 6–8 looms per micro/small shed (requiring field validation; larger 20–50 loom sheds represent an estimated ~10–15% upper subset, or ~7,500–14,000 units). |
| **SOM (Realistic Pilot + Year-1 Local Cluster)** | **1 unit (pilot) → 10–25 units (Year 1 post-degree if commercialized)** | Directly reachable through personal/peer network in Coimbatore–Tiruppur belt. |

*(We deliberately avoid inflated multi-crore TAM valuations. Every assumption above is tagged for validation.)*

---

## 4. Business Feasibility Verdict

- **For the student's family business:** **Highly viable.** Direct cost is ₹0, eliminates arithmetic wage errors, audits ₹6/m trader settlements against 25–50 paise/m cuts (saving ₹13,000+/month on a 50-loom scale if even a ₹0.20/m discrepancy is caught across 67,000 m/month), and runs privately on a local laptop + Android phone.
- **Commercial viability as a standalone SaaS startup:** **Moderate/Cautious.** Loomiro (₹999/mo), TexFo, and Pinakexa already compete heavily, and small shuttle-loom owners in Tamil Nadu resist recurring SaaS fees during downturns. A realistic commercial path post-graduation is **open-core free local software with paid local setup/customization or low-cost regional support**, not venture-scale SaaS.
- **Academic & practical conclusion:** LOOMOS is strongest as a **dual-purpose B.Sc. CT research artefact AND real internal operations platform** for the family's 20→50 loom business.
