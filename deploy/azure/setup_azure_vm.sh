#!/usr/bin/env bash
# One-command 24/7 Azure Ubuntu VM installer for LOOMOS (Docker + Persistent DB + Free HTTPS via Caddy)
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Kavinprakash132/LOOMOS/main/deploy/azure/setup_azure_vm.sh | sudo bash -s -- <YOUR_AZURE_DNS_OR_EMPTY> [demo|real]
# Example (Real Shed with Free Azure HTTPS):
#   curl -fsSL https://raw.githubusercontent.com/Kavinprakash132/LOOMOS/main/deploy/azure/setup_azure_vm.sh | sudo bash -s -- loomos-shed.centralindia.cloudapp.azure.com real
# Example (Demo Sandbox over HTTP/HTTPS):
#   curl -fsSL https://raw.githubusercontent.com/Kavinprakash132/LOOMOS/main/deploy/azure/setup_azure_vm.sh | sudo bash -s -- loomos-shed.centralindia.cloudapp.azure.com demo

set -euo pipefail

DOMAIN="${1:-:80}"
MODE="${2:-demo}"
REPO_URL="https://github.com/Kavinprakash132/LOOMOS.git"
APP_DIR="/opt/loomos"
DATA_DIR="/var/lib/loomos-data"

echo "==> [1/5] Ensuring 2 GB swapfile (protects free 1 GB B1s VMs during Docker build & ONNX)..."
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> [2/5] Installing Docker & Compose..."
export DEBIAN_FRONTEND=noninteractive
if ! command -v docker >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg git
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
fi

echo "==> [3/5] Preparing persistent storage at ${DATA_DIR}..."
mkdir -p "${DATA_DIR}/uploads" "${DATA_DIR}/backups"

echo "==> [4/5] Cloning / updating LOOMOS into ${APP_DIR}..."
if [ -d "${APP_DIR}/.git" ]; then
  git -C "${APP_DIR}" fetch origin
  git -C "${APP_DIR}" reset --hard origin/main
else
  git clone "${REPO_URL}" "${APP_DIR}"
fi

cd "${APP_DIR}/deploy/azure"
if [ "${MODE}" = "demo" ]; then
  cat > .env <<EOF
LOOMOS_DOMAIN=${DOMAIN}
LOOMOS_DEMO_MODE=true
LOOMOS_AUTO_SEED_DEMO=true
EOF
else
  cat > .env <<EOF
LOOMOS_DOMAIN=${DOMAIN}
LOOMOS_DEMO_MODE=false
LOOMOS_AUTO_SEED_DEMO=false
EOF
fi

echo "==> [5/5] Building & starting LOOMOS 24/7 (Docker + Caddy HTTPS)..."
docker compose up -d --build

echo ""
echo "================================================================"
echo "  LOOMOS IS NOW LIVE 24/7!"
if [ "${DOMAIN}" = ":80" ]; then
  PUB_IP=$(curl -fsSL https://api.ipify.org || echo "<YOUR_VM_PUBLIC_IP>")
  echo "  URL:  http://${PUB_IP}"
else
  echo "  URL:  https://${DOMAIN}"
fi
echo "  MODE: ${MODE}  |  Persistent DB: ${DATA_DIR}/loomos.db"
if [ "${MODE}" = "demo" ]; then
  echo "  Demo Owner Login:      welcome123 / welcome123"
  echo "  Demo Supervisor Login: sup_siva / supPassword1"
else
  echo "  First-time real shed setup: open URL to run 3-step /setup wizard!"
fi
echo "================================================================"
