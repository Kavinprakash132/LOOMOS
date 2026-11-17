# Academic Literature Review (Verified Sources)

**Last updated:** 2026-11-17  
**Databases Queried:** OpenAlex API, Crossref REST API, University of Freiburg LMB Repository  
**Verification Policy:** Every citation, DOI, author list, venue, year, and finding below was verified directly against Crossref/OpenAlex metadata and abstracts in this session. Papers without accessible abstracts beyond bibliographic metadata are noted explicitly.

---

## 1. Automated Fabric Defect Detection, Lightweight CNNs & Explainable AI (XAI)

### 1.1 Silvestre-Blanes et al. (2019) — *A Public Fabric Database for Defect Detection Methods and Results*
- **Journal:** *AUTEX Research Journal*, Vol. 19, No. 4, pp. 363–374 (2019) | **DOI:** `10.2478/aut-2019-0035`
- **Research problem:** Prior fabric defect detection algorithms were evaluated on small, private datasets, preventing fair comparative evaluation.
- **Methodology:** Compiled and publicly released the **AITEX Fabric Image Database (AFID)**: 245 images (`4096×256` pixels across 7 fabric weaves: 140 defect-free, 105 defective covering 12 defect classes with pixel-level binary masks) and evaluated benchmark detection/classification methods.
- **Limitations:** Images were captured under controlled industrial line-scan illumination (`4096×256` grayscale strips), not handheld consumer smartphone photography, and defect classes are heavily imbalanced (several classes have fewer than 10 strips).
- **Relevance to LOOMOS:** Primary open benchmark dataset for LOOMOS (RQ2) and source-domain benchmark for testing cross-domain generalization to smartphone shed photos (RQ3).

### 1.2 Hanbay, Talu & Özgüven (2016) — *Fabric defect detection systems and methods—A systematic literature review*
- **Journal:** *Optik* (2016) | **DOI:** `10.1016/j.ijleo.2016.09.110`
- **Relevance & summary:** Foundational systematic review categorizing structural, statistical, spectral, and early learning-based textile inspection methods. Establishes the transition from manual human visual inspection (fatiguing and inconsistent) to automated image-processing pipelines prior to modern lightweight deep learning. *(Note: full PDF not accessed; bibliographic metadata verified via Crossref & OpenAlex.)*

### 1.3 Nasim, Mumtaz, Ahmad & Ali (2024) — *Fabric Defect Detection in Real World Manufacturing Using Deep Learning*
- **Journal:** *Information* (MDPI), 15(8), 476 (2024) | **DOI:** `10.3390/info15080476`
- **Research problem:** Real-world textile manufacturing lacks high-quality, precisely positioned images and simultaneously weaves diverse plain and printed fabrics requiring low-cost, accurate deep learning models.
- **Important findings:** Demonstrates that deep learning models trained on indigenous production-floor fabric datasets achieve higher practical robustness than models limited to uniform lab textures, motivating lower computational cost for production deployment.
- **Limitations:** Still oriented toward factory inspection setups rather than decentralized 20-loom job-work sheds without dedicated inspection hardware.
- **Relevance to LOOMOS:** Directly motivates **RQ3**—combining public benchmarks with real local shed photography (`LOOMOS-Shed`) rather than assuming public models transfer unchanged.

### 1.4 Mao & Hong (2025) — *YOLO Object Detection for Real-Time Fabric Defect Inspection in the Textile Industry: A Review of YOLOv1 to YOLOv11*
- **Journal:** *Sensors* (MDPI), 25(7), 2270 (2025) | **DOI:** `10.3390/s25072270`
- **Research problem:** Systematic review of single-stage object detectors (YOLOv1–YOLOv11) for high-speed textile defect detection.
- **Important findings & limitations highlighted:** Identifies **dataset limitations, domain generalization across fabric weaves/lighting, and computational efficiency** on constrained factory hardware as open unsolved challenges.
- **Relevance to LOOMOS:** Confirms that domain generalization (RQ3) and low-compute deployment on CPU/mobile hardware remain active research problems in 2025.

### 1.5 Islam, Sumaya, Monir & Islam (2024) — *FabricSpotDefect: An annotated dataset for identifying spot defects in different fabric types*
- **Journal:** *Data in Brief* (Elsevier), 111165 (2024) | **DOI:** `10.1016/j.dib.2024.111165`
- **Methodology & findings:** Curates 1,014 raw fabric images with 3,288 manually annotated spot defects (expanded via augmentation to 2,300 images in YOLOv8/COCO formats) across diverse fabric types.
- **Relevance to LOOMOS:** Confirms spot defects (e.g., oil stains) are major industrial problems and provides a candidate secondary dataset for spot/stain validation in Week 1–2.

### 1.6 Dhali, Shome & Alam (2025) — *FabriXNet: An Explainable AI Framework for Automated Fabric Defect Detection and Quality Inspection*
- **Conference:** *IEEE ICCIT 2025* | **DOI:** `10.1109/iccit68739.2025.11491382`
- **Methodology & findings:** Combines multi-stage deep learning across multi-source datasets (TILDA, Tianchi, Roboflow; 44,047 images) with **Grad-CAM** visual explanations to improve human trust in defect localization.
- **Limitations:** Heavy multi-dataset YOLOv8 pipeline designed for automated detection, disconnected from job-work ERP tracking (weaver wages, beam traceability, rate protection).
- **Relevance to LOOMOS:** Validates integrating **Grad-CAM** into fabric defect inspection so shed owners can visually verify *why* a cloth photo was flagged.

### 1.7 Swapno et al. (2025) — *Explainable transformer framework for fast cotton leaf diagnostics and fabric defect detection*
- **Journal:** *iScience* (Cell Press), 114411 (2025) | **DOI:** `10.1016/j.isci.2025.114411`
- **Findings & relevance:** Pairs lightweight CNN feature extraction with compact attention + XAI for fabric defect classification (tested on CottonFabricImageBD and FabricSpotDefect). Reinforces lightweight + explainable architectures over opaque heavy models.

### 1.8 Foundational Computer Vision & XAI Methods
- **Howard et al. (2019)** — *Searching for MobileNetV3*, *IEEE/CVF ICCV 2019* (`10.1109/ICCV.2019.00140`): Lightweight depthwise-separable CNN designed for mobile/CPU inference latency constraints.
- **He et al. (2016)** — *Deep Residual Learning for Image Recognition*, *IEEE CVPR 2016* (`10.1109/CVPR.2016.90`): Residual connections (`ResNet-18`) serving as standard transfer-learning comparator.
- **Selvaraju et al. (2019)** — *Grad-CAM: Visual Explanations from Deep Networks via Gradient-Based Localization*, *IJCV* (`10.1007/s11263-019-01228-7`): Gradient-weighted activation heatmaps highlighting defective fabric regions for human verification without pixel segmentation overhead.

---

## 2. Digital Transformation & Information Systems in Manufacturing SMEs

### 2.1 Pandey, Kumar & Gupta (2024) — *Assessing the need for the adoption of digitalization in Indian small and medium enterprises*
- **Journal:** *Open Engineering* (2024) | **DOI:** `10.1515/eng-2024-0072`
- **Findings:** Indian SMEs contribute ~31% of GDP and ~43% of exports (2021–2022) yet lag significantly in adopting Industry 4.0/digitalization due to cost, employee skill gaps, and complex technology mismatch.
- **Relevance to LOOMOS:** Explains why zero-cost, <2-minute phone workflows succeed where complex desktop ERPs fail in 20-loom Indian units.

### 2.2 Rodríguez-Espíndola et al. (2022) — *Analysis of the adoption of emergent technologies for risk management in the era of digital manufacturing*
- **Journal:** *Technological Forecasting and Social Change*, 121562 (2022) | **DOI:** `10.1016/j.techfore.2022.121562`
- **Findings:** Integrates TAM, Resource-Based View, and Institutional Theory to model SME adoption of digital technologies for operational risk management.
- **Relevance to LOOMOS:** Supports framing LOOMOS around **operational risk reduction** (rate cuts, wage disputes, defects, EB spikes) rather than "ERP modernization" alone.

### 2.3 Alayón, Säfsten & Johansson (2022) — *Barriers and Enablers for the Adoption of Sustainable Manufacturing by Manufacturing SMEs*
- **Journal:** *Sustainability*, 14(4), 2364 (2022) | **DOI:** `10.3390/su14042364`
- **Findings:** Systematic review identifying financial constraints, lack of in-house IT expertise, and resource limits as core SME barriers; modular, low-overhead tools with immediate visible ROI act as primary enablers.

### 2.4 Kamble, Munshi & Salati (2024) — *A Study on Human Resource Planning in Powerloom Units in Ichalkaranji*
- **Journal:** *African Journal of Biomedical Research* (2024) | **DOI:** `10.53555/ajbr.v27i5s.7146`
- **Relevance:** Recent empirical study specifically studying labour and HR planning challenges in an Indian decentralized powerloom cluster (Ichalkaranji), reinforcing that weaver workforce management and productivity tracking remain critical pain points in Indian weaving clusters. *(Full text not accessed beyond abstract.)*

---

## 3. Forecasting, Anomaly Detection, DSR & Usability Foundations

- **Hyndman, Koehler, Ord & Snyder (2008)** — *Forecasting with Exponential Smoothing: The State Space Approach*, Springer (`10.1007/978-3-540-71918-2`): Methodological basis for Holt/exponential smoothing baselines on short weekly production time series (RQ4).
- **Liu, Ting & Zhou (2008)** — *Isolation Forest*, *IEEE ICDM 2008* (`10.1109/ICDM.2008.17`): Tree-based unsupervised anomaly detection baseline compared against transparent `z-score`/IQR rules for shift-entry outlier alerts.
- **Hevner, March, Park & Ram (2004)** — *Design Science in Information Systems Research*, *MIS Quarterly* (`10.2307/25148625`) & **Peffers et al. (2007)** — *A Design Science Research Methodology for Information Systems Research*, *JMIS* (`10.2753/MIS0742-1222240302`): Foundational DSR framework and 6-step process model structuring LOOMOS.
- **Bangor, Kortum & Miller (2008)** — *An Empirical Evaluation of the System Usability Scale*, *IJHCI* (`10.1080/10447310802205776`): Empirical SUS benchmark thresholds for evaluating usability (RQ5).

*(Also noted as excluded/negative reference: **Matzka (2020)**, `10.1109/AI4I49448.2020.00023` — synthetic milling machine dataset; explicitly excluded from LOOMOS modeling so no milling data is misrepresented as powerloom data.)*
