# Industry Analysis: Small Decentralized Powerloom Job-Work Units (India & Tamil Nadu)

**Last updated:** 2026-11-17  
**Scope:** Small and medium-sized decentralized powerloom weaving units in India, with primary focus on Western Tamil Nadu (Coimbatore–Tiruppur–Somanur–Palladam–Erode belt).

---

## 1. National and State Sector Footprint

| Metric | Value | Source & Verification Status |
|---|---|---|
| Total powerlooms in India | ~24.86 lakh (~2.49 million) | **Verified via secondary synthesis:** IBEF citing Ministry of Textiles / Office of the Textile Commissioner (requires primary PDF check in Week 2). |
| Powerloom units in India | >3.85 lakh units | IBEF citing Ministry of Textiles. |
| Workforce employed | ~44.18 lakh workers | IBEF citing Ministry of Textiles. |
| Share of Indian fabric production | ~60% | IBEF / Tamil Nadu Textile Policy references. |
| Powerlooms in Tamil Nadu | ~5.63–5.68 lakh (~23% nationally; 2nd largest after Maharashtra at ~9.48 lakh) | IBEF / Ministry of Textiles references. |
| Major Tamil Nadu clusters | Erode (Mega Cluster), Coimbatore, Tiruppur (Somanur/Palladam/Avinashi), Salem, Karur | Ministry of Textiles / state cluster records. |

---

## 2. How Small Job-Work Powerloom Units Operate

Unlike composite textile mills (spinning + sizing + weaving + processing + garmenting), the majority of small units in Western Tamil Nadu operate on a **decentralized job-work (conversion) model** (reported as ~90% of conventional powerlooms in the Somanur–Palladam–Avinashi belt):

1. **Parties & Ownership:**
   - **Trader / Master Weaver (Customer):** Owns the raw material (sized warp beams and weft yarn cones) and owns the finished grey cloth (*Gada*). Pays the loom owner strictly a conversion rate per metre woven.
   - **Loom Owner (Primary User/Buyer):** Owns the shed, looms (typically 12–50 shuttle looms, or 4–24 shuttleless rapier looms), pays electricity (EB), loom maintenance/spares, and weaver wages.
   - **Weavers / Operators (*Karigars*):** Run 2 shifts/day (morning & night), operating multiple looms per weaver. Paid per loom-shift, per shift, or per metre depending on local shed terms.
   - **Secondary Helpers:** Women winders/pirn winders/helpers (e.g., weekly wages in shuttle units).
2. **Physical Workflow:**
   - Trader sends a **warp beam** (specific length, fabric sort: yarn count, reed, pick, width) + **weft yarn bags/cones** to the shed.
   - Loom fitter/owner mounts the beam on one or more looms (`beam loading`).
   - Weavers run Day & Night shifts (~25 working days/month, ~5 days holiday/maintenance).
   - Finished grey fabric rolls/pieces (*taakas*) are folded, inspected visually, and delivered weekly to the trader with a delivery slip.
   - Trader pays job-work charges (`delivered_metres × rate_per_metre`) minus any shortage/defect deductions; owner settles weekly weaver wages and advances (*uthaav*), and pays bi-monthly EB bills.

---

## 3. Baseline Empirical Evidence from a Real 20-Loom Unit

From `Powerloom_Business_Plan.docx` (real records from a 20-shuttle-loom job-work unit in Kaduvettipalayam, Coimbatore/Tiruppur belt, 2025–2026):

- **Machinery:** 20 conventional shuttle powerlooms, 2 shifts/day, ~25 working days/month.
- **Revenue model:** Job-work at **₹6.00/metre** (41 real weekly deliveries = **2,51,455 m** across the tracked periods; calibrated normal output = **53.85 m/loom/day** vs 60 m theoretical max = **89.8% efficiency**).
- **Electricity (TANGEDCO LA3A2 / LT-IIIA2 powerloom tariff, 10 kW sanctioned load):**
  - 5 real bi-monthly bills: **8,360 kWh (₹44,146)** in P1 summer peak; **6,407 kWh (₹32,554)** and **6,361 kWh (₹32,282)** in normal periods P2/P5; **2,796 kWh (₹11,116)** during Diwali/Karthigai shutdown (P3); **4,346 kWh (₹20,328)** in P4.
  - Tariff slabs: **0–1,000 units FREE** (subsidy), **1,001–1,500 units @ ₹4.15/unit**, **>1,500 units @ ₹5.30/unit** + fixed/tax overhead (~₹446/kW bi-monthly in normal operation).
- **Cost & Margin Breakdown (20 looms):**
  - Monthly Revenue: **₹1,66,500**
  - Monthly Labour: **₹82,833** (~49.7% of revenue: ₹60/loom/shift × 2 shifts + ₹2,500/week helper)
  - Monthly Electricity: **₹16,209** (~9.7% of revenue)
  - Maintenance & Misc: **₹11,000** (~6.6% of revenue)
  - Monthly Net Profit: **₹56,458** (**33.9% margin**, or **~₹2.03/metre**).

### Current Industry Pressure (Verified 2025 News)
- In March–April 2025, Somanur/Palladam job-work powerloom weavers staged a **33-day indefinite strike** over stalled per-metre job-work wage revisions (settled on 20 April 2025 with a 15% hike for Somanur variety and 10% for other varieties over 2022 benchmarks).
- Post-settlement reporting noted traders still attempting **25–50 paise/metre** unilateral cuts due to market pressure.
- **Implication for LOOMOS:** On a ~₹2.00/metre profit margin, a **₹0.50/metre unflagged rate cut wipes out 25% of net profit**, and a 2% unrecorded production/yarn leakage erodes margins further.

---

## 4. Digital Adoption Barriers & Operating Constraints

| Constraint | Reality in Small Tamil Nadu Sheds | Design Implication for LOOMOS |
|---|---|---|
| **Hardware & Budget** | No desktop server or IoT loom sensors; owner/supervisor use mid-range Android smartphones + possibly one home/office laptop | Mobile-first PWA accessible over local Wi-Fi/hotspot; zero sensor requirement |
| **Time Pressure on Floor** | Supervisor manages 20–50 noisy looms across shifts | Daily shift entry grid must finish in **<2 minutes per shift** |
| **Software Price Sensitivity** | ₹1,000–₹3,000/month SaaS subscriptions feel heavy relative to micro margins or during festival shutdowns | Free, open-source, self-hosted ₹0 architecture |
| **Language & Literacy** | Existing Surat/North Indian tools target Hinglish/Gujarati; local Tamil Nadu sheds prefer clean English numerals or Tamil labels | Clean English mobile interface (Phase 1), extensible i18n keys for Tamil later |
| **Dispersed/Intermittent Power & Network** | Sheds in semi-rural clusters (e.g., Kaduvettipalayam, Nallagoundampalayam) can have weak mobile data inside metal sheds | Runs locally on shed laptop/Wi-Fi with SQLite WAL + nightly backup |

---

## 5. Facts vs. Unverified Assumptions Requiring Field Verification

- **Established facts:** 20-loom unit's 5 EB bills, 41 weekly delivery totals, LA3A2 tariff slabs, ₹6/m conversion rate, ₹60/loom/shift rate in this unit, Apr 2025 Somanur/Palladam strike context, sector footprint estimates.
- **Assumptions requiring Week 1–2 field interviews (not yet verified):**
  1. Exact defect inspection workflow today (who checks grey *taakas*, before vs after folding, frequency of trader defect penalties/rejections).
  2. Which 4–6 defect types actually dominate in 30s/40s cotton grey shuttle weaving (expected: broken pick, broken end, oil stain, float, hole, thick/thin place).
  3. Whether the supervisor has reliable smartphone access during shift handovers or prefers owner batch entry from a tally sheet.
  4. Whether weekly yarn wastage reconciliation is done by beam or only by aggregate trader account.
  5. Exact notebook time and error rates (baseline timing study in Week 1–2 before deployment).
