# Chronos Command — Cloud VM (remote testers)

**Product:** Chronos Command · **Vendor:** Weierworks Technologies, LLC

Use this when testers are **not on your LAN** and you want a stable public URL (not a laptop tunnel).

For a **same-day** link from your PC instead, use **`Start Remote UAT Tunnel.bat`** (cloudflared/ngrok).

---

## Architecture

```
Tester browser  →  HTTPS :443  →  Caddy/nginx (TLS)  →  Chronos :8080
                                              ↑
                                    Docker or python on VM
```

| Piece | Role |
|-------|------|
| Cloud VM | Public IP (Azure/AWS/GCP/DigitalOcean) |
| Docker Compose | Runs Chronos + optional Caddy |
| Volume | Persists DB / photos / logs |
| Security group | Allow **443** (and 80 for certs); **do not** expose 8080 publicly if proxy is up |

---

## Fast path (Ubuntu 22.04+ VM)

### 1. Create VM

| Provider | Suggested size | Notes |
|----------|----------------|--------|
| **Azure** | B2s / B2ats_v2 | Open inbound **80, 443** (NSG) |
| **AWS EC2** | t3.small | Security group: 80, 443 from `0.0.0.0/0` (or tester IPs) |
| **DigitalOcean** | $12 droplet | Firewall: 80, 443 |

Point a DNS A record (optional but best):

`chronos-uat.yourdomain.gov` → VM public IP

Without DNS, Caddy can still use a tunnel, or use HTTP-only for short lab (not ideal).

### 2. Install Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# log out/in
docker --version
```

### 3. Copy project to VM

From your PC (PowerShell), with SSH key:

```powershell
scp -r C:\Users\Windows\MyProject user@YOUR_VM_IP:~/chronos
```

Or git clone if the repo is on GitHub.

### 4. Configure secrets

```bash
cd ~/chronos
cp deploy/cloud/env.example .env
nano .env   # set SCHEDULER_STORAGE_SECRET + SCHEDULER_PUBLIC_URL
```

Generate a secret:

```bash
openssl rand -hex 32
```

Example `.env`:

```env
SCHEDULER_STORAGE_SECRET=paste-64-hex-here
SCHEDULER_PUBLIC_URL=https://chronos-uat.yourdomain.gov
SCHEDULER_PORT=8080
SCHEDULER_SKIP_STARTUP_GATES=1
```

### 5. Start (HTTP only — quick lab)

```bash
docker compose up -d --build
curl -sI http://127.0.0.1:8080 | head -5
```

Testers: `http://YOUR_VM_PUBLIC_IP:8080`
**Only if** security group opens **8080**. Prefer TLS (next).

### 6. Start with HTTPS (Caddy — recommended)

```bash
# DNS A record must already point to this VM
# .env must set SCHEDULER_STORAGE_SECRET and CHRONOS_DOMAIN
docker compose -f deploy/cloud/docker-compose.caddy.yml up -d --build
```

Testers open: `https://chronos-uat.yourdomain.gov`

Logins (seed/demo): `admin` / `admin` · `supervisor` / `supervisor` · `officer` / `officer`

### 7. Smoke

```bash
docker compose logs -f chronos
# From your laptop:
# open https://YOUR_DOMAIN  → Sign In
```

Human checklist: `docs/VIRTUAL_UAT.md`

---

## Azure checklist (portal)

1. Create **Resource group** → **Ubuntu 22.04 VM**
2. **Networking** → inbound: HTTP (80), HTTPS (443); SSH (22) from your IP only
3. Note public IP
4. SSH in → follow **Fast path** above
5. Optional: Azure DNS zone A record → public IP

## AWS checklist

1. EC2 Ubuntu AMI · t3.small · new key pair
2. Security group: 22 (your IP), 80, 443 (0.0.0.0/0 or tester CIDR)
3. Elastic IP optional (stable address)
4. SSH → **Fast path**

---

## Without Docker (Python on VM)

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv
cd ~/chronos
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export SCHEDULER_UI_MODE=web
export SCHEDULER_HOST=0.0.0.0
export SCHEDULER_PORT=8080
export SCHEDULER_SKIP_STARTUP_GATES=1
export SCHEDULER_STORAGE_SECRET=$(openssl rand -hex 32)
export SCHEDULER_PUBLIC_URL=https://chronos-uat.yourdomain.gov
# optional isolated lab DB:
# export SCHEDULER_DB_PATH=$PWD/lab_data/virtual_uat.db
python main.py --web --host 0.0.0.0 --port 8080
```

Put **Caddy** or **nginx** in front (configs under `deploy/cloud/`).

systemd unit example: `deploy/cloud/chronos.service`

---

## Security (UAT vs production)

| Practice | UAT lab | Production |
|----------|---------|------------|
| Demo passwords | OK short-term | Change / disable |
| Open 8080 to world | Avoid | Never |
| HTTPS | Strongly prefer | Required |
| Storage secret | Random | Random + secret store |
| Backups | `docker volume` snapshot | Nightly DB + photos |
| Live SMS | Deferred OK | Configure when ready |

Stop UAT when done:

```bash
docker compose down
# keep volume for data: omit -v
# wipe data: docker compose down -v
```

---

## Files in this pack

| Path | Purpose |
|------|---------|
| `docs/deploy/CLOUD_VM.md` | This guide |
| `deploy/cloud/env.example` | Env template |
| `deploy/cloud/Caddyfile` | TLS reverse proxy |
| `deploy/cloud/nginx.conf` | nginx alternative |
| `deploy/cloud/docker-compose.caddy.yml` | Compose overlay |
| `deploy/cloud/chronos.service` | systemd (no Docker) |
| `deploy/cloud/cloud-init.sh` | First-boot install helper |
| `docker-compose.yml` | Chronos service |
| `Start Remote UAT Tunnel.bat` | Laptop tunnel (no VM) |

Also: `docs/deploy/ONLINE_HOSTING.md` · `docs/VIRTUAL_UAT.md`
