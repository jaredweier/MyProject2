# Chronos Command — Online hosting

**Product:** Chronos Command
**Vendor:** Weierworks Technologies, LLC

Agencies can purchase **on-prem software** (desktop/portable) or an **online** deployment of the same product.

## Modes

| Mode | How to run | Data |
|------|------------|------|
| Desktop / on-prem | `python main.py` or portable build | Local `data/` folder |
| Local browser | `python main.py --browser` | Local `data/` |
| **Online host** | `python main.py --web` or Docker | Server `data/` volume |

## Quick online start

```bash
# Windows
set SCHEDULER_STORAGE_SECRET=replace-with-long-random-hex
set SCHEDULER_PUBLIC_URL=https://chronos.yourcity.gov
python main.py --web --host 0.0.0.0 --port 8080
```

```bash
# Docker (HTTP)
copy deploy\cloud\env.example .env   # set SCHEDULER_STORAGE_SECRET
docker compose up -d --build
```

```bash
# Cloud VM + HTTPS (Caddy)
# see docs/deploy/CLOUD_VM.md
cp deploy/cloud/env.example .env
# set SCHEDULER_STORAGE_SECRET + CHRONOS_DOMAIN
docker compose -f deploy/cloud/docker-compose.caddy.yml up -d --build
```

**Remote tester (no VM):** `Start Remote UAT Tunnel.bat` (cloudflared/ngrok).

## Production checklist

1. **TLS** — terminate HTTPS at nginx, Caddy, IIS, or cloud load balancer (app listens HTTP internally).
2. **`SCHEDULER_STORAGE_SECRET`** — required for multi-user sessions (do not use default).
3. **`SCHEDULER_PUBLIC_URL`** — public base URL for links in email/SMS.
4. **Upload Chronos logo** — Branding & Media before go-live (product mark in sidebar + login).
5. **Notify channels** — `/channels`: enable email/SMS; set SMTP and/or Twilio when ready (outbox queues without creds).
6. **Backup** — volume `chronos_data` / `data/` folder; use in-app backup regularly.
7. **LDAP/SSO (optional)** — `SCHEDULER_LDAP_ENABLED=1` + server/base DN (`logic/ldap_auth.py`).

## Environment reference

| Variable | Purpose |
|----------|---------|
| `SCHEDULER_UI_MODE=web` | Force online mode |
| `SCHEDULER_HOST` / `SCHEDULER_PORT` | Bind address |
| `SCHEDULER_STORAGE_SECRET` | Session crypto secret |
| `SCHEDULER_PUBLIC_URL` | Public URL |
| `SCHEDULER_TENANT_ID` / `NAME` | Multi-agency label (single DB per deploy) |
| `TWILIO_*` | Live SMS (optional; outbox works without) |
| `SCHEDULER_CAD_WEBHOOK_URL` | Optional duty-roster webhook |
| `SCHEDULER_LDAP_*` | Optional AD bind |

## Multi-tenant (isolated agencies)

Chronos uses **one SQLite + media tree per agency** (not shared-schema multi-tenant).

```bash
# Agency A
set SCHEDULER_TENANT_ID=agency-a
set SCHEDULER_TENANT_NAME=Agency A PD
set SCHEDULER_STORAGE_SECRET=secret-a
python main.py --web --port 8081

# Agency B (separate process/port or container)
set SCHEDULER_TENANT_ID=agency-b
set SCHEDULER_TENANT_NAME=Agency B PD
set SCHEDULER_STORAGE_SECRET=secret-b
python main.py --web --port 8082
```

Data lands in `tenants/agency-a/` and `tenants/agency-b/` (DB, photos, exports, logs).
Create folders from **Deploy & Implement → Agency tenants**, or `logic.tenant.create_tenant`.
Or set `SCHEDULER_DB_PATH` explicitly per process.

Also document dual OT engine + geofence clock on Deploy page.


## Branding before deploy

1. Sign in as admin → **Branding & Media**
2. Upload **Chronos Command** product logo
3. Optional: department seal + hero photo
4. Confirm login + sidebar show the mark

## Implementation kit

In-app: **Deploy & Implement** (`/deploy`) exports checklist JSON/MD for sales and onboarding.
