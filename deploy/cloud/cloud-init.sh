#!/usr/bin/env bash
# First-boot helper for Ubuntu cloud VMs — installs Docker + starts Chronos.
# Usage (as root or with sudo), from repo root:
#   bash deploy/cloud/cloud-init.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
fi

if [[ ! -f .env ]]; then
  if [[ -f deploy/cloud/env.example ]]; then
    cp deploy/cloud/env.example .env
    SECRET="$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | xxd -p -c 64)"
    # shellcheck disable=SC2016
    sed -i "s/change-me-to-64-hex-chars/${SECRET}/" .env || true
    echo "Wrote .env with random SCHEDULER_STORAGE_SECRET — edit SCHEDULER_PUBLIC_URL / CHRONOS_DOMAIN"
  fi
fi

export SCHEDULER_SKIP_STARTUP_GATES=1
# shellcheck disable=SC1091
set -a
[[ -f .env ]] && source .env
set +a

echo "Building and starting Chronos..."
docker compose up -d --build

echo
echo "Chronos should be on http://$(curl -s ifconfig.me 2>/dev/null || echo YOUR_PUBLIC_IP):${SCHEDULER_PORT:-8080}"
echo "For HTTPS: set CHRONOS_DOMAIN DNS A record, then:"
echo "  docker compose -f deploy/cloud/docker-compose.caddy.yml up -d --build"
echo "Logins: admin/admin · supervisor/supervisor · officer/officer"
echo "UAT doc: docs/VIRTUAL_UAT.md · Cloud: docs/deploy/CLOUD_VM.md"
