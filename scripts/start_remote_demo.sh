#!/usr/bin/env bash
# ==============================================================================
# LOOMOS DEMO LAUNCHER (Linux / Google Antigravity Remote Agents)
# Uses isolated backend/data/loomos_demo.db (Real loomos.db is never touched)
# ==============================================================================
# Usage:
#   bash scripts/start_remote_demo.sh               # Start Backend (8000) + Vite Dev (5173)
#   bash scripts/start_remote_demo.sh clean         # Reset loomos_demo.db to empty /setup wizard
#   bash scripts/start_remote_demo.sh --single-port # Serve API + built React SPA on port 8000
# ==============================================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"
VENV_PY="${BACKEND_DIR}/.venv/bin/python"
VENV_ALEMBIC="${BACKEND_DIR}/.venv/bin/alembic"
VENV_UVICORN="${BACKEND_DIR}/.venv/bin/uvicorn"

export LOOMOS_DB_PATH="${BACKEND_DIR}/data/loomos_demo.db"
export LOOMOS_DEMO_MODE="true"

if [ ! -x "${VENV_PY}" ]; then
  echo "Backend virtualenv not found. Running scripts/remote_setup.sh first..."
  bash "${ROOT_DIR}/scripts/remote_setup.sh"
fi

cd "${BACKEND_DIR}"
if [ "${1:-}" = "clean" ]; then
  echo "Resetting ONLY loomos_demo.db to empty Setup Wizard state..."
  "${VENV_PY}" scripts/seed_demo_cli.py --clean
else
  if [ ! -f "${LOOMOS_DB_PATH}" ]; then
    echo "Seeding isolated demo database loomos_demo.db..."
    "${VENV_PY}" scripts/seed_demo_cli.py --demo
  else
    "${VENV_ALEMBIC}" upgrade head
  fi
fi

if [ "${1:-}" = "--single-port" ]; then
  if [ ! -f "${FRONTEND_DIR}/dist/index.html" ]; then
    echo "Building frontend/dist for single-port serving..."
    (cd "${FRONTEND_DIR}" && npm run build)
  fi
  echo "Starting LOOMOS (DEMO Single-Port API + SPA) on http://0.0.0.0:8000 ..."
  exec "${VENV_UVICORN}" app.main:app --host 0.0.0.0 --port 8000
fi

cleanup() {
  echo "Stopping LOOMOS Demo servers..."
  kill "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting LOOMOS Backend (DEMO DB) on http://0.0.0.0:8000 ..."
"${VENV_UVICORN}" app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "Starting LOOMOS Frontend (DEMO MODE) on http://0.0.0.0:5173 ..."
cd "${FRONTEND_DIR}"
npm run dev -- --host 0.0.0.0 --port 5173 &
FRONTEND_PID=$!

echo ""
echo "  DEMO MODE ACTIVE (loomos_demo.db)"
echo "  Frontend Dev URL : http://127.0.0.1:5173"
echo "  Backend API URL  : http://127.0.0.1:8000"
echo "  Demo Owner       : welcome123 / welcome123"
echo "  Demo Supervisor  : sup_siva  / supPassword1"
echo ""

wait -n "${BACKEND_PID}" "${FRONTEND_PID}"
