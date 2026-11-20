#!/usr/bin/env bash
# ==============================================================================
# LOOMOS — Google Antigravity Remote Agents / Linux Cloud Bootstrapper
# ==============================================================================
# Usage:
#   bash scripts/remote_setup.sh                 # Standard full-stack setup + test
#   bash scripts/remote_setup.sh --with-vision   # Also install Phase 2-4 ML/Excel packages
#   bash scripts/remote_setup.sh --reseed-demo   # Force fresh re-seed of loomos_demo.db
# ==============================================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"

WITH_VISION=false
RESEED_DEMO=false

for arg in "$@"; do
  case "$arg" in
    --with-vision) WITH_VISION=true ;;
    --reseed-demo) RESEED_DEMO=true ;;
  esac
done

echo "============================================================"
echo "  LOOMOS Remote Cloud Environment Setup"
echo "  Workspace: ${ROOT_DIR}"
echo "============================================================"

# 1. Python Virtual Environment & Backend Dependencies
cd "${BACKEND_DIR}"
if [ ! -d ".venv" ]; then
  echo "[1/5] Creating Python virtual environment in backend/.venv ..."
  python3 -m venv .venv
fi

VENV_PY="${BACKEND_DIR}/.venv/bin/python"
VENV_PIP="${BACKEND_DIR}/.venv/bin/pip"
VENV_ALEMBIC="${BACKEND_DIR}/.venv/bin/alembic"
VENV_PYTEST="${BACKEND_DIR}/.venv/bin/pytest"

echo "[2/5] Installing Python dependencies ..."
"${VENV_PIP}" install --upgrade pip -q
if [ "${WITH_VISION}" = true ]; then
  "${VENV_PIP}" install -r requirements-phase2-4.txt
else
  "${VENV_PIP}" install -r requirements.txt
fi

# 2. Initialize Databases (Reproducible without laptop SQLite files)
echo "[3/5] Initializing SQLite databases via Alembic & Demo Seeder ..."
mkdir -p "${BACKEND_DIR}/data/backups" "${BACKEND_DIR}/data/uploads"

# Upgrade production schema (creates empty loomos.db if missing; never overwrites data)
LOOMOS_DB_PATH="${BACKEND_DIR}/data/loomos.db" "${VENV_ALEMBIC}" upgrade head

# Seed isolated demo database (loomos_demo.db)
if [ ! -f "${BACKEND_DIR}/data/loomos_demo.db" ] || [ "${RESEED_DEMO}" = true ]; then
  "${VENV_PY}" scripts/seed_demo_cli.py --demo
else
  LOOMOS_DB_PATH="${BACKEND_DIR}/data/loomos_demo.db" "${VENV_ALEMBIC}" upgrade head
fi

# 3. Frontend Dependencies & Production Build
echo "[4/5] Installing Frontend dependencies and verifying build ..."
cd "${FRONTEND_DIR}"
if [ -f "package-lock.json" ]; then
  npm ci --no-audit --no-fund
else
  npm install --no-audit --no-fund
fi
npm run build

# 4. Run Backend Test Gate
echo "[5/5] Running pytest verification suite ..."
cd "${BACKEND_DIR}"
"${VENV_PYTEST}" -v

echo "============================================================"
echo "  LOOMOS Remote Setup Complete!"
echo "  - Start Demo Stack : bash scripts/start_remote_demo.sh"
echo "  - Start Real Stack : bash scripts/start_remote.sh"
echo "  - Demo Owner Login : welcome123 / welcome123"
echo "  - Demo Supervisor  : welcome@123 / welcome@123"
echo "============================================================"
