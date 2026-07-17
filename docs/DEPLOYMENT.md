# Deployment Guide — Dodgeville PD Scheduler

Deploy the scheduler to **up to 8 department PCs** with **one shared schedule** for all users.

**Model:** One copy of the app on a **network file share**; every PC runs the same `.exe` and uses the same database, photos, and exports.

---

## Prerequisites

| Item | Requirement |
|------|-------------|
| Build PC | Windows, Python 3.x, project source |
| File server | Windows share, stable **wired** LAN |
| Client PCs | Windows 10/11, 64-bit (up to 8) |
| Users | Individual logins (Administration / Supervisor / Officer) |

---

## 1. Build the release package

On your development machine:

```bat
build_test.bat
```

This runs `python dev.py check`, then builds:

`dist\Dodgeville_PD_Scheduler\`

Zip that **entire folder** for IT (not the `.exe` alone).

---

## 2. Install on the file server

Copy the folder to a central share, for example:

```
\\PD-SERVER\PDApps\ChronosScheduler\
├── Dodgeville_PD_Scheduler.exe   (package name may still say Dodgeville)
├── _internal\
├── roster_seed.json
├── Start Dodgeville Scheduler.bat   ← copy from project docs/deploy/
└── (after first run)
    ├── dodgeville_scheduler.db
    ├── photos\                   ← brand + officer uploads live here
    │   ├── chronos_logo.png      ← optional product mark (upload in UI)
    │   ├── dept_logo.png         ← optional agency seal
    │   └── dept_photo.jpg        ← optional login hero photo
    ├── backups\
    ├── logs\
    └── exports\
```

**Branding:** No logo/team photo is shipped. After install, an admin opens Chronos → **Branding & Media** and uploads:
1. **Chronos Command logo** (product mark on login + sidebar)
2. **Department logo** (agency seal)
3. **Department photo** (login hero)

**Permissions:** Every scheduler user needs **Modify** on this folder (read/write/create files).

**IT notes:**

- Prefer a **wired** server and gigabit LAN.
- Consider excluding this folder from aggressive real-time antivirus scanning on the server (coordinate with IT policy).
- Plan **nightly backups** of `dodgeville_scheduler.db` and `photos\`.

---

## 3. Prepare roster and accounts (first launch only)

**Before** rolling out to all 8 PCs:

1. Edit `roster_seed.json` on the share with real officer names, squads, shifts, and titles—or leave officers empty and import CSV later from the Officers tab.
2. Remove or replace `demo_users` in `roster_seed.json` for production, **or** use `Start Dodgeville Scheduler.bat` which sets `SKIP_DEMO_USERS=1`.
3. From **one** PC, run `Start Dodgeville Scheduler.bat` (or the `.exe` once).
4. Sign in as the first admin account (create via CLI on build machine if demo users are skipped—see below).
5. Complete the **first-time department setup** wizard.
6. Open **User Accounts** → create logins for each person; link officers to roster entries.
7. Run **Backup Database** from the sidebar; store the backup off the share.

### First admin without demo users

If demo users are skipped and no accounts exist yet, on a machine with **Python source** installed:

```bat
python cli.py users create --username pdadmin --password "TempPass1!" --role Administration
```

Then sign in through the GUI and change the password.

---

## 4. Deploy to client PCs

On each of the 8 computers:

1. Create a desktop shortcut to:
   ```
   \\PD-SERVER\PDApps\DodgevilleScheduler\Start Dodgeville Scheduler.bat
   ```
   (Adjust `PD-SERVER` and path to match your environment.)

2. Optional: rename shortcut to **Dodgeville PD Scheduler**.

3. Train users:
   - Sign in with **personal** account (not shared Windows login for app identity).
   - **Sign out** when leaving a shared workstation.
   - Report “database is locked” or slowness to IT/supervisor.

**Do not** install separate local copies with separate databases unless you intend separate schedules.

---

## 5. Pilot test (required)

Before full rollout, have **2–3 people** use different PCs **at the same time** for 2–3 days:

| Test | Pass criteria |
|------|----------------|
| Officer submits time off on PC A | Visible on PC B after refresh |
| Supervisor approves on PC B | Schedule updates on PC A |
| Roster edit + photo upload | Visible on another PC |
| Two users editing different areas | No repeated “database locked” errors |
| Backup while app is open | Backup completes; restore tested once |

If locking is frequent during normal use, see **Plan B** in [Remote and multi-site access](#remote-and-multi-site-access) below.

---

## 6. Updates (new version)

1. **Backup** `dodgeville_scheduler.db` and `photos\` from the share.
2. Replace app files on the share with the new `dist\Dodgeville_PD_Scheduler\` build **except**:
   - `dodgeville_scheduler.db`
   - `photos\`
   - `backups\`
   - `logs\`
   - `exports\`
3. Keep `Start Dodgeville Scheduler.bat` and customized `roster_seed.json` if edited.
4. Have one user launch and smoke-test; then notify department.

---

## 7. Backup and restore

**Daily (automated or manual):**

- Copy `\\PD-SERVER\PDApps\DodgevilleScheduler\dodgeville_scheduler.db`
- Copy `\\PD-SERVER\PDApps\DodgevilleScheduler\photos\`
- Or use in-app **Backup Database** (stores under `backups\` on the share)

**Restore:**

1. Close the app on all PCs (or after hours).
2. Replace `dodgeville_scheduler.db` from backup.
3. Restore `photos\` if needed.
4. Relaunch from one PC and verify.

---

## Launcher script

Copy [`docs/deploy/Start Dodgeville Scheduler.bat`](deploy/Start%20Dodgeville%20Scheduler.bat) to the share next to the `.exe`.

Edit the `cd /d` line at the top if your share path differs.

Environment set by the launcher:

| Variable | Value | Purpose |
|----------|--------|---------|
| `SKIP_DEMO_USERS` | `1` | No demo admin/supervisor/officer accounts on empty DB |
| `SCHEDULER_AUTO_LOGIN` | `0` | Login screen always shown |
| `SCHEDULER_DB_PATH` | (optional) | Uncomment to put DB on a different path than the exe folder |

---

## SQLite on a network share

This app uses **SQLite** (single file). It works for many small departments on a LAN but is **not** a full client/server database.

| Suitable | Risky |
|----------|--------|
| Mostly viewing schedules | Many simultaneous writes |
| Bursty approvals and edits | Unstable Wi‑Fi to the share |
| ≤8 PCs, not all busy at once | VPN + high-latency link to SQLite on SMB |

Operational guidance: supervisors batch heavy roster/payroll work when possible; officers submit requests; take backups before bulk operations.

---

## Remote and multi-site access

The shipped app is a **Windows desktop GUI**, not a web application. Users **outside** the building cannot run it like a website without extra infrastructure.

### Option A — VPN (recommended first step)

**What:** Officers/supervisors connect to the department VPN, then use the **same network shortcut** as on-site.

**Steps:**

1. IT deploys VPN (Windows VPN, Fortinet, Cisco, etc.).
2. VPN users receive the same `Start Dodgeville Scheduler.bat` pointing at the internal UNC path.
3. VPN must reach the file server; test concurrent VPN + LAN users in pilot.
4. Same SQLite-on-SMB caveats apply over VPN—latency can increase lock errors.

**Effort:** Low (IT standard). **Fits current app:** Yes.

### Option B — Remote Desktop (RDS or single PC)

**What:** Publish a Windows session that already has the shortcut (or full desktop).

**Steps:**

1. Dedicated PC or RDS session on the LAN with shortcut to the share.
2. Users RDP from home via VPN or RD Gateway.
3. Only the RDP session talks to SQLite; remote users share one or few sessions.

**Effort:** Low–medium. **Fits current app:** Yes. **Downside:** Not one-session-per-user unless RDS licensing and multiple sessions are configured.

### Option C — Cloud VM + VPN/RDP

**What:** Host the file share (or entire app) on an Azure/AWS VM; users VPN or RDP in.

**Steps:**

1. Migrate share to cloud VM on private network.
2. Department VPN into cloud VNet.
3. Same shortcut model.

**Effort:** Medium. **Fits current app:** Yes with migration planning.

### Option D — Web or mobile app (new development)

**What:** Browser-based UI backed by PostgreSQL/SQL Server and an API.

**Steps (high level):**

1. Extract business logic from `logic.py` behind a REST/API layer.
2. Replace CustomTkinter UI with web frontend (or keep desktop for in-station, web for remote).
3. Migrate SQLite schema to a server database.
4. Authentication: HTTPS, sessions, optional LDAP/OAuth.
5. Hosting: on-prem or cloud with TLS and backups.

**Effort:** High (major project). **Fits current app:** Requires rebuild of presentation and data tier—not a config change.

### Option E — Port forwarding / expose SMB (do not use)

Exposing the file share or SQLite over the public internet is **unsafe** and unreliable. Do not do this.

---

## Summary

| Scenario | Approach |
|----------|----------|
| 8 PCs, same building | Shared folder on `\\PD-SERVER\...` + launcher shortcut |
| Home / off-duty access | VPN + same shortcut, or RDP to departmental PC/RDS |
| Public web link | Not available today; requires Option D |
| Long-term scale | Server database + API + web UI |

---

## Related docs

- [`PROJECT_README.md`](PROJECT_README.md) — project status and agent workflow
- [`HANDOFF.md`](HANDOFF.md) — development handoff
- [`EVALUATE.txt`](../EVALUATE.txt) — evaluation smoke-test checklist
- Build scripts: `build_test.bat`, `build_quick.bat`
