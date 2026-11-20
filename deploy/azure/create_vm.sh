#!/usr/bin/env bash
# Fast 1-command Azure VM creator + LOOMOS auto-deployer (run in Azure Cloud Shell Bash!)
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Kavinprakash132/LOOMOS/main/deploy/azure/create_vm.sh | bash
# Optional args: [demo|real] [easy-dns-name]
#   curl -fsSL https://raw.githubusercontent.com/Kavinprakash132/LOOMOS/main/deploy/azure/create_vm.sh | bash -s -- demo loomos

set -euo pipefail

MODE="${1:-demo}"
CUSTOM_DNS="${2:-}"
RG="loomos-rg"
VM="loomos-vm"
ADMIN_USER="loomosadmin"
ADMIN_PASS="Loomos@$(openssl rand -hex 4)9!"

echo "================================================================"
echo "  LOOMOS Fast Azure VM Provisioner (Mode: ${MODE})"
echo "================================================================"

SUB_NAME="$(az account show --query name -o tsv 2>/dev/null || true)"
if [ -z "${SUB_NAME}" ]; then
  echo "ERROR: Not logged into Azure CLI. Open Azure Cloud Shell (Bash) or run 'az login' first."
  exit 1
fi
echo "==> Subscription: ${SUB_NAME}"

echo "==> [1/4] Finding best allowed region & budget-friendly VM size..."
CHOICE="$(python3 - <<'PY'
import json, subprocess, sys

def run_az(args):
    p = subprocess.run(["az"] + args + ["-o", "json"], capture_output=True, text=True)
    if p.returncode != 0 or not p.stdout.strip():
        return None
    try:
        return json.loads(p.stdout)
    except Exception:
        return None

# 1. Discover allowed locations from Azure for Students policy (if any)
policies = run_az(["policy", "assignment", "list"]) or []
allowed = set()
for pol in policies:
    params = pol.get("parameters") or {}
    for k, v in params.items():
        if "location" in k.lower() and isinstance(v, dict):
            val = v.get("value")
            if isinstance(val, list):
                for loc in val:
                    if isinstance(loc, str):
                        allowed.add(loc.lower().replace(" ", ""))

preferred_regions = [
    "centralindia", "southindia", "westindia",
    "southeastasia", "malaysiawest", "indonesiacentral", "eastasia",
    "uaenorth", "qatarcentral", "japaneast", "koreacentral",
    "westeurope", "northeurope", "uksouth", "francecentral", "swedencentral",
    "eastus2", "eastus", "westus2", "centralus", "westus3", "canadacentral",
]

if allowed:
    regions = [r for r in preferred_regions if r in allowed] + sorted(allowed - set(preferred_regions))
else:
    regions = preferred_regions

# Modest, smooth, low-cost / 12-month-free B-series first
preferred_skus = [
    "Standard_B2ats_v2",  # 2 vCPU, 1 GiB (FREE 750 hrs/mo + 2 GB swap)
    "Standard_B1ms",      # 1 vCPU, 2 GiB (~$15/mo from $100 student credit)
    "Standard_B1s",       # 1 vCPU, 1 GiB (FREE 750 hrs/mo + 2 GB swap)
    "Standard_B2ts_v2",   # 2 vCPU, 1 GiB (budget burstable)
    "Standard_B2ls_v2",   # 2 vCPU, 4 GiB (budget AMD burstable)
    "Standard_B2s",       # 2 vCPU, 4 GiB (classic burstable)
    "Standard_D2as_v5",   # fallback if B-series restricted
    "Standard_D2s_v3",    # fallback
]

def sku_vcpus(sku_obj):
    for cap in sku_obj.get("capabilities") or []:
        if cap.get("name") == "vCPUs":
            try:
                return int(cap.get("value", 1))
            except Exception:
                return 1
    return 1

def sku_family(sku_obj):
    return (sku_obj.get("family") or "").lower()

for region in regions[:8]:
    skus = run_az(["vm", "list-skus", "-l", region, "--resource-type", "virtualMachines"]) or []
    if not skus:
        continue
    usages = run_az(["vm", "list-usage", "-l", region]) or []
    avail_cores = {}
    total_free = 999
    for u in usages:
        name = ((u.get("name") or {}).get("value") or "").lower()
        free = int(u.get("limit", 0)) - int(u.get("currentValue", 0))
        if name == "cores":
            total_free = free
        avail_cores[name] = free

    if total_free < 1:
        continue

    sku_map = {}
    for s in skus:
        name = s.get("name")
        if name not in preferred_skus:
            continue
        # Reject if whole-location restricted
        restricted = False
        for r in s.get("restrictions") or []:
            if r.get("type") == "Location" and r.get("reasonCode") == "NotAvailableForSubscription":
                restricted = True
                break
        if restricted:
            continue
        need = sku_vcpus(s)
        fam = sku_family(s)
        if need > total_free:
            continue
        if fam in avail_cores and need > avail_cores[fam]:
            continue
        sku_map[name] = s

    for target in preferred_skus:
        if target in sku_map:
            print(f"{region} {target}")
            sys.exit(0)

# Fallback: first allowed region + Standard_B1ms
print(f"{regions[0]} Standard_B1ms")
PY
)"

REGION="$(echo "${CHOICE}" | awk '{print $1}')"
VM_SIZE="$(echo "${CHOICE}" | awk '{print $2}')"

# Pick the cleanest available DNS name in this region
SUB_ID="$(az account show --query id -o tsv | tr -d '\r')"
DNS_LABEL="$(python3 - "${SUB_ID}" "${REGION}" "${CUSTOM_DNS}" <<'PY'
import json, random, subprocess, sys

sub_id, region, custom = sys.argv[1], sys.argv[2], sys.argv[3].strip().lower()
candidates = []
if custom:
    candidates.append(custom)
candidates += ["loomos", "loomos-app", "loomos-in", "loomos-kavin", "loomos-shed", f"loomos-{random.randint(10,99)}"]

for name in candidates:
    url = f"https://management.azure.com/subscriptions/{sub_id}/providers/Microsoft.Network/locations/{region}/CheckDnsNameAvailability?domainNameLabel={name}&api-version=2023-09-01"
    p = subprocess.run(["az", "rest", "--method", "get", "--url", url, "-o", "json"], capture_output=True, text=True)
    if p.returncode == 0 and p.stdout.strip():
        try:
            if json.loads(p.stdout).get("available") is True:
                print(name)
                sys.exit(0)
        except Exception:
            pass
print(f"loomos-{random.randint(100,999)}")
PY
)"

FQDN="${DNS_LABEL}.${REGION}.cloudapp.azure.com"

echo "==> Selected Region: ${REGION}"
echo "==> Selected Size:   ${VM_SIZE}"
echo "==> Target HTTPS:    https://${FQDN}"

echo "==> [2/4] Creating Resource Group '${RG}' & Ubuntu 24.04 VM '${VM}' (with auto-install on boot)..."
az group create -n "${RG}" -l "${REGION}" -o none

CLOUD_INIT="/tmp/loomos-cloud-init.sh"
cat > "${CLOUD_INIT}" <<EOF
#!/usr/bin/env bash
exec > /var/log/loomos-install.log 2>&1
set -x
curl -fsSL https://raw.githubusercontent.com/Kavinprakash132/LOOMOS/main/deploy/azure/setup_azure_vm.sh | bash -s -- "${FQDN}" "${MODE}"
EOF

if ! az vm create \
  -g "${RG}" \
  -n "${VM}" \
  -l "${REGION}" \
  --image Ubuntu2404 \
  --size "${VM_SIZE}" \
  --security-type Standard \
  --storage-sku Standard_LRS \
  --os-disk-size-gb 30 \
  --admin-username "${ADMIN_USER}" \
  --admin-password "${ADMIN_PASS}" \
  --public-ip-sku Standard \
  --public-ip-address-dns-name "${DNS_LABEL}" \
  --custom-data "${CLOUD_INIT}" \
  -o none; then
  echo "Retrying with Ubuntu2204 image..."
  az vm create \
    -g "${RG}" \
    -n "${VM}" \
    -l "${REGION}" \
    --image Ubuntu2204 \
    --size "${VM_SIZE}" \
    --security-type Standard \
    --storage-sku Standard_LRS \
    --os-disk-size-gb 30 \
    --admin-username "${ADMIN_USER}" \
    --admin-password "${ADMIN_PASS}" \
    --public-ip-sku Standard \
    --public-ip-address-dns-name "${DNS_LABEL}" \
    --custom-data "${CLOUD_INIT}" \
    -o none
fi

echo "==> [3/4] Opening HTTP (80) & HTTPS (443) firewall ports..."
az vm open-port -g "${RG}" -n "${VM}" --port 80 --priority 1010 -o none
az vm open-port -g "${RG}" -n "${VM}" --port 443 --priority 1020 -o none

PUB_IP="$(az vm show -d -g "${RG}" -n "${VM}" --query publicIps -o tsv | tr -d '\r')"

echo ""
echo "================================================================"
echo "  VM CREATED! SAVE THESE DETAILS:"
echo "  Live HTTPS URL : https://${FQDN}"
echo "  Public IP      : ${PUB_IP}"
echo "  Region / Size  : ${REGION} / ${VM_SIZE}"
echo "  SSH Login      : ssh ${ADMIN_USER}@${PUB_IP}"
echo "  SSH Password   : ${ADMIN_PASS}"
echo "  LOOMOS Mode    : ${MODE}"
if [ "${MODE}" = "demo" ]; then
  echo "  Demo Owner     : welcome123 / welcome123"
  echo "  Demo Supervisor: welcome@123 / welcome@123"
fi
echo "================================================================"
echo ""
echo "==> [4/4] Waiting for Docker build + Let's Encrypt HTTPS on VM (~2-4 mins)..."

READY=0
for i in $(seq 1 36); do
  if curl -fsS --max-time 6 "https://${FQDN}/api/v1/health" >/dev/null 2>&1; then
    READY=1
    break
  fi
  printf "."
  sleep 10
done
echo ""

if [ "${READY}" -eq 1 ]; then
  echo "SUCCESS! LOOMOS IS LIVE 24/7 AT: https://${FQDN}"
  curl -fsS "https://${FQDN}/api/v1/setup/status" || true
  echo ""
else
  echo "Still building Docker image on the VM (almost done!)."
  echo "Open https://${FQDN} in 1-2 minutes, or check logs via:"
  echo "  ssh ${ADMIN_USER}@${PUB_IP} 'sudo tail -f /var/log/loomos-install.log'"
fi
