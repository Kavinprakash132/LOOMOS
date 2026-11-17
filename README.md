# LOOMOS — Powerloom Job-Work Production, Analytics & Defect Inspection System

**LOOMOS** is a mobile-first production management, wage calculation, electricity bill forecasting, and smartphone fabric defect inspection web application built for small decentralized powerloom job-work sheds in Tamil Nadu.

It is fully compatible with **Google Antigravity Remote Agents** (cloud Linux sandboxes accessible from a smartphone such as the **Samsung S24 Ultra** at `antigravity.google.com` even when your laptop is powered off) as well as local Windows LAN execution.

---

## 1. Architecture & Stack

- **Backend (`backend/`):** Python 3.11–3.13, FastAPI, SQLAlchemy 2.0, Alembic, SQLite (WAL mode + `foreign_keys=ON`), PyJWT (`HS256`), `bcrypt`, `pytest`.
- **Frontend (`frontend/`):** React 18, TypeScript, Vite 6, Tailwind CSS v4, Lucide Icons, bilingual UI (`EN | தமிழ்`) and trilingual printable weaver payslips (`EN / தமிழ் / हिन्दी`).
- **Database Isolation (`backend/data/`):**
  - `loomos.db`: Real production database (initialized empty via `alembic upgrade head`; never touched by demo scripts).
  - `loomos_demo.db`: Isolated 5-loom Shuttle demo database seeded deterministically via `python scripts/seed_demo_cli.py --demo`.
- **Complete Project Log & Hand-Calculation Guide:** See [`what i did/WHAT_I_DID.md`](what%20i%20did/WHAT_I_DID.md).

---

## 2. Quick Start in Google Antigravity Remote Agents (Cloud Linux VM)

When working in a fresh cloud sandbox (or any Linux/macOS terminal), run the one-command bootstrapper from the repository root:

```bash
bash scripts/remote_setup.sh
```

What `scripts/remote_setup.sh` does automatically:
1. Creates `backend/.venv` and installs `backend/requirements.txt` (pass `--with-vision` to also install `backend/requirements-phase2-4.txt` for ONNX/OpenCV/Excel/Playwright).
2. Runs `alembic upgrade head` to initialize the empty `backend/data/loomos.db` schema.
3. Seeds the isolated 5-loom Shuttle demo database (`backend/data/loomos_demo.db`) via `python scripts/seed_demo_cli.py --demo`.
4. Installs `frontend/` npm packages (`npm ci`) and builds `frontend/dist` (`npm run build`).
5. Runs the full backend `pytest -v` verification suite.

### Starting the Servers in a Remote Agent / Cloud VM

- **Demo Mode (Recommended for testing & development — uses `loomos_demo.db`):**
  ```bash
  # Dual-server dev mode (FastAPI on :8000 + Vite HMR on :5173):
  bash scripts/start_remote_demo.sh

  # Or single-port mode (FastAPI serves both /api/v1/* and built React SPA on :8000):
  bash scripts/start_remote_demo.sh --single-port

  # Reset ONLY loomos_demo.db to empty 3-step /setup wizard state:
  bash scripts/start_remote_demo.sh clean
  ```

- **Production Mode (Uses `loomos.db`):**
  ```bash
  bash scripts/start_remote.sh
  ```

### Demo Credentials (`loomos_demo.db`)
- **Owner Login:** `welcome123` / `welcome123`
- **Supervisor Login:** `sup_siva` / `supPassword1`

---

## 3. Quick Start on Windows Laptop (Local Shed Wi-Fi / LAN)

- **Demo Mode (`loomos_demo.db`):** Double-click `Start_LOOMOS_DEMO.bat` (or run `Start_LOOMOS_DEMO.bat clean` to test the `/setup` wizard).
- **Production Mode (`loomos.db`):** Double-click `Start_LOOMOS.bat`.

---

## 4. Environment Variables & Secrets Configuration

Copy [`backend/.env.example`](backend/.env.example) to `backend/.env` for local overrides, or configure environment variables directly in **Google Antigravity Remote Agents** settings. **Never commit `.env`, `.jwt_secret`, or `.db` files to Git.**

| Variable | Default | Description |
|---|---|---|
| `LOOMOS_APP_NAME` | `LOOMOS` | Application title |
| `LOOMOS_DB_PATH` | `./data/loomos.db` | SQLite database path (relative paths resolve inside `backend/`) |
| `LOOMOS_DATABASE_URL` | *(empty)* | Optional full SQLAlchemy URL override |
| `LOOMOS_DEMO_MODE` | `false` | Forces amber `DEMO DATA ACTIVE` banner when `true` |
| `LOOMOS_SECRET_KEY` | *(auto-generated)* | JWT HS256 signing secret (auto-saved to `backend/data/.jwt_secret` if unset) |
| `LOOMOS_ACCESS_TOKEN_EXPIRE_MINUTES` | `720` | JWT session lifetime in minutes |
| `LOOMOS_CORS_ORIGINS` | `["*"]` | Allowed CORS origins JSON list |
| `LOOMOS_SERVE_STATIC` | `true` | Serves built `frontend/dist` SPA from FastAPI when present |
| `GEMINI_API_KEY` | *(empty)* | Optional Gemini API key injected via cloud environment variables |
| `LOOMOS_GEMINI_MODEL` | `gemini-2.5-flash` | Default Gemini model identifier when Gemini integration is used |
| `VITE_API_PROXY_TARGET` | `http://127.0.0.1:8000` | Backend target for Vite `/api` proxy in `frontend/vite.config.ts` |

---

## 5. Standard Commands for Development, Testing & Building

### Backend (from `backend/`)
```bash
# Activate virtualenv (Linux/macOS)
source .venv/bin/activate

# Run database migrations
alembic upgrade head

# Seed or reset isolated demo database (refuses to touch loomos.db)
python scripts/seed_demo_cli.py --demo
python scripts/seed_demo_cli.py --clean

# Fetch public AITEX / TILDA_400 datasets on demand (for Phase 2 Vision AI)
python scripts/fetch_vision_datasets.py

# Run full pytest suite
pytest -v
```

### Frontend (from `frontend/`)
```bash
# Install dependencies
npm ci

# Type-check and build production bundle (frontend/dist)
npm run build

# Start Vite dev server on 0.0.0.0:5173
npm run dev
```
