# Verified Source Register & Search Log

**Last updated:** 2026-11-17

---

## 1. Academic Sources (Verified via Crossref & OpenAlex APIs)

| ID | Citation | Year | DOI / URL | Verification Method |
|---|---|---|---|---|
| S01 | Silvestre-Blanes, J., Albero-Albero, T., Miralles, I., Pérez-Lloréns, R., & Moreno, J. *A Public Fabric Database for Defect Detection Methods and Results.* AUTEX Research Journal, 19(4), 363–374. | 2019 | `10.2478/aut-2019-0035` | Crossref + OpenAlex + GitHub AITEX dataset files inspected on disk |
| S02 | Hanbay, K., Talu, M. F., & Özgüven, Ö. F. *Fabric defect detection systems and methods—A systematic literature review.* Optik. | 2016 | `10.1016/j.ijleo.2016.09.110` | Crossref + OpenAlex |
| S03 | Nasim, M. Q., Mumtaz, R., Ahmad, M., & Ali, A. *Fabric Defect Detection in Real World Manufacturing Using Deep Learning.* Information, 15(8), 476. | 2024 | `10.3390/info15080476` | OpenAlex API (title, authors, abstract verified) |
| S04 | Mao, M., & Hong, M. *YOLO Object Detection for Real-Time Fabric Defect Inspection in the Textile Industry: A Review of YOLOv1 to YOLOv11.* Sensors, 25(7), 2270. | 2025 | `10.3390/s25072270` | OpenAlex API (title, authors, abstract verified) |
| S05 | Islam, F., Sumaya, Monir, M. F., & Islam, A. *FabricSpotDefect: An annotated dataset for identifying spot defects in different fabric types.* Data in Brief. | 2024 | `10.1016/j.dib.2024.111165` | OpenAlex API (title, authors, abstract verified) |
| S06 | Dhali, S. K., Shome, A., & Alam, K. M. *FabriXNet: An Explainable AI Framework for Automated Fabric Defect Detection and Quality Inspection.* IEEE ICCIT 2025. | 2025 | `10.1109/iccit68739.2025.11491382` | OpenAlex API (title, authors, abstract verified) |
| S07 | Swapno, S. M. M. R. et al. *Explainable transformer framework for fast cotton leaf diagnostics and fabric defect detection.* iScience. | 2025 | `10.1016/j.isci.2025.114411` | OpenAlex API (title, authors, abstract verified) |
| S08 | Howard, A. et al. *Searching for MobileNetV3.* IEEE/CVF ICCV 2019. | 2019 | `10.1109/ICCV.2019.00140` | Crossref API |
| S09 | He, K., Zhang, X., Ren, S., & Sun, J. *Deep Residual Learning for Image Recognition.* IEEE CVPR 2016. | 2016 | `10.1109/CVPR.2016.90` | Crossref API |
| S10 | Selvaraju, R. R. et al. *Grad-CAM: Visual Explanations from Deep Networks via Gradient-Based Localization.* International Journal of Computer Vision. | 2019 | `10.1007/s11263-019-01228-7` | OpenAlex API |
| S11 | Pandey, V., Kumar, A., & Gupta, S. *Assessing the need for the adoption of digitalization in Indian small and medium enterprises.* Open Engineering. | 2024 | `10.1515/eng-2024-0072` | OpenAlex API (title, authors, abstract verified) |
| S12 | Rodríguez-Espíndola, O. et al. *Analysis of the adoption of emergent technologies for risk management in the era of digital manufacturing.* Technological Forecasting and Social Change. | 2022 | `10.1016/j.techfore.2022.121562` | OpenAlex API (title, authors, abstract verified) |
| S13 | Alayón, C., Säfsten, K., & Johansson, G. *Barriers and Enablers for the Adoption of Sustainable Manufacturing by Manufacturing SMEs.* Sustainability, 14(4), 2364. | 2022 | `10.3390/su14042364` | OpenAlex API |
| S14 | Kamble, A. P., Munshi, M. M., & Salati, A. Y. *A Study on Human Resource Planning in Powerloom Units in Ichalkaranji.* African Journal of Biomedical Research. | 2024 | `10.53555/ajbr.v27i5s.7146` | OpenAlex API |
| S15 | Hyndman, R. J., Koehler, A. B., Ord, K., & Snyder, R. D. *Forecasting with Exponential Smoothing.* Springer. | 2008 | `10.1007/978-3-540-71918-2` | OpenAlex API |
| S16 | Liu, F. T., Ting, K. M., & Zhou, Z.-H. *Isolation Forest.* IEEE ICDM 2008. | 2008 | `10.1109/ICDM.2008.17` | Crossref API |
| S17 | Hevner, A. R., March, S. T., Park, J., & Ram, S. *Design Science in Information Systems Research.* MIS Quarterly. | 2004 | `10.2307/25148625` | Crossref + OpenAlex |
| S18 | Peffers, K., Tuunanen, T., Rothenberger, M. A., & Chatterjee, S. *A Design Science Research Methodology for Information Systems Research.* JMIS. | 2007 | `10.2753/MIS0742-1222240302` | Crossref + OpenAlex |
| S19 | Bangor, A., Kortum, P., & Miller, J. *An Empirical Evaluation of the System Usability Scale.* IJHCI. | 2008 | `10.1080/10447310802205776` | Crossref + OpenAlex |
| S20 | Matzka, S. *Explainable AI for Predictive Maintenance Applications.* IEEE AI4I 2020. *(Explicitly excluded synthetic dataset reference)* | 2020 | `10.1109/AI4I49448.2020.00023` | Crossref + local CSV inspection |

---

## 2. Dataset, Industry & Competitor Sources

| ID | Source | Accessed Date | Notes & Limitations |
|---|---|---|---|
| D01 | AITEX Fabric Image Database (GitHub mirror `jraad/fabric_defect_detection`, `data/aitex/`) + `aitex.es` code reference | 2026-11-17 | Inspected directly on disk: 106 defect strips, 109 masks, 141 clean strips, 185 OD crops |
| D02 | TILDA Textile Texture Database (`lmb.informatik.uni-freiburg.de/resources/datasets/tilda.en.html` + GitHub mirror `the-h-b/TILDA_400`) | 2026-11-17 | Freiburg `tilda_CD1+CD2.zip` direct path returned HTTP 404; GitHub mirror inspected (`hole`, `objects`, `oil spot`, `thread error` = 2,430 patches; `good` class requires Kaggle download) |
| D03 | `Powerloom_Business_Plan.docx` (owner's 20-loom unit records) | 2026-11-17 | Primary operational records: 5 TANGEDCO LA3A2 bills + 41 weekly deliveries (2,51,455 m) |
| I01 | Ministry of Textiles / IBEF Powerloom Sector Statistics | 2026-11-17 | Secondary synthesis via web search (~24.86L looms national, ~5.63–5.68L TN); primary Annual Report PDF check pending in Week 2 |
| I02 | Somanur/Palladam 33-day job-work strike reporting (The Hindu, Times of India, New Indian Express, Apr 2025) | 2026-11-17 | Search synthesis documenting April 2025 MoU & 25–50 paise rate-cut disputes |
| C01–C06 | `loomiro.com`, `texfo.in`, `pinakexa.com`, `emanage.in`, `vastraapp.com`, `trackweaving.com` | 2026-11-17 | Homepages fetched directly via HTTP 200; custom-quote products lack public price sheets |
