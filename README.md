# LOOMOS — Smart Powerloom Shed Production, Analytics & AI Cloth Inspection

**LOOMOS** is a mobile-first, free & open-source production management, electricity analytics, payroll, and smartphone cloth-defect inspection web app built for decentralized shuttle powerloom job-work units in Tamil Nadu.

## Key Features
- **Daily Shed Operations:** Mobile-friendly Daily Shift production grid (`Direct Metres` & `Start → End Counter`, mid-shift beam swaps), Warp Beam lifecycle & weft wastage tracking, and real-time Dashboard (`Time Run %`, `Weaving Speed %`, `Combined Efficiency %`, conditional Full OEE).
- **Money & Bills (Owner RBAC):** 4-mode weaver/helper/pirn-winder payroll with dated wage rules, *Uthaav* advances, live Damage Cut, and trilingual (`EN / தமிழ் / हिन्दी`) printable payslips; Delivery Challans with automatic **Trader Rate-Cut Checker**, Receivables Ledger, Expenses, and **7-Sheet Excel (`.xlsx`)** + Print-PDF statements.
- **TNPDCL Power & Forecasting:** Live database-driven `LA3A2` powerloom tariff calculator (`Total Units`, `EB Meter Prev → Curr`, and `By Fabric Metres`), **EB Bill vs. Metres Produced** efficiency tracking with automatic meter under-reading detection, Beam Finish ETA (`shed_calendar` + `P50/P25–P75`), 5-week walk-forward weekly production forecast (`CN-MA` + `Holt` vs `Naive`), and a `20 / 30 / 50 / 100` Shuttle Loom Expansion Simulator.
- **Offline CPU Vision AI (`/inspect`):** Two-Output ONNX `MobileNetV3-Large (Multi-Dataset RGB)` defect detection trained across `24,064` real fabric images (`16.8 MB` ONNX, `~30–45 ms` CPU) with 5-crop multi-scale tiling, seamless feathered Grad-CAM overlays, Camera + Gallery/Files mobile upload, 6 diverse held-out reference samples, mandatory human verification, and an `RQ3` few-shot fine-tuning script.
- **Clean 3-Section Bilingual UX (`EN | தமிழ்`):** Organized into **Daily Shed**, **Money & Bills**, and **Smart Tools** with full English & Tamil translations, collapsible `+ Add` forms, page guides, and 1-click **Technical Details** toggles.

## Quick Local Start (Windows)
- **Isolated Demo Sandbox (5 looms, safe to experiment):** Double-click `Start_LOOMOS_DEMO.bat`  
  Demo logins: Owner `welcome123` / `welcome123` · Supervisor `welcome@123` / `welcome@123`
- **Real Shed Mode (clean `loomos.db`):** Double-click `Start_LOOMOS.bat` and complete the 3-step `/setup` wizard.

## One-Click 24/7 Cloud Hosting (Docker)
This repository ships with a single-container `Dockerfile` (FastAPI serving both the API, ONNX Vision AI, and built React SPA on one port), plus `railway.toml` and `render.yaml`:
- **Railway (24/7 + Persistent Storage):** Create a new Railway project from this GitHub repo, attach a Persistent Volume at `/data`, and set:
  - `LOOMOS_DB_PATH=/data/loomos.db`
  - `LOOMOS_UPLOAD_DIR=/data/uploads`
  - `LOOMOS_BACKUP_DIR=/data/backups`
  - *(For a pre-populated demo deployment instead, also set `LOOMOS_DEMO_MODE=true` and `LOOMOS_AUTO_SEED_DEMO=true`.)*
- **Render (Free Live Demo or Paid Persistent Disk):** Connect this GitHub repo as a **Web Service** or **Blueprint** (`render.yaml`).

## Tech Stack
- **Frontend:** React 18, TypeScript, Vite 6, Tailwind CSS v4, Lucide Icons
- **Backend:** FastAPI, SQLAlchemy 2, Alembic, SQLite (WAL mode, integer paise), `openpyxl`
- **Vision AI:** PyTorch → Two-Output ONNX (`onnxruntime` CPU), OpenCV CLAHE + Grad-CAM
