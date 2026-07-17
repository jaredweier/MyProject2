# Virtual UAT — Chronos Command

**Goal:** Department (or remote) testers can exercise Chronos in a browser within **12 hours** of prep, with clear pass/fail and known residuals.

**Auto pack:** `python dev.py virtual-lab` · status: `logs/virtual_lab_status.json`

---

## Outside sources used (ideas, not copy)

| Source theme | Applied here |
|--------------|--------------|
| UAT entry/exit (TestRail, Inflectra, AltexSoft) | Gates before humans; residual list; role scenarios |
| Playwright 2026 (stable locators, isolation) | `data-testid` on login; one server; lab DB |
| LE scheduling products (PowerTime, Vector, Snap, eSchedule) | Critical paths: leave, swap, open shift, OT/coverage, audit, min staffing |

---

## 0. Entry criteria (must be green)

```bat
python dev.py virtual-lab
REM ship claim for handoff:
python dev.py virtual-lab --ship
```

| Gate | Command | Honest? |
|------|---------|---------|
| Doctor | `python dev.py doctor` | env OK |
| Readiness | `python dev.py readiness-check` | login + seed security |
| LE scenarios | `python scripts/virtual_uat_scenarios.py` | leave/swap/OT/ops/auth |
| Residual | `python scripts/residual_proof_smoke.py` | 32+ product residuals |
| Ship | `python dev.py verify --tier check` | `honest_gate: true` |

**Do not start human UAT** if `logs/virtual_lab_status.json` → `ready: false`.

---

## 1. Start virtual lab (browser)

### Isolated lab DB (recommended)

```powershell
New-Item -ItemType Directory -Force -Path lab_data | Out-Null
$env:SCHEDULER_SKIP_GATES = "1"
$env:SCHEDULER_DB_PATH = "$PWD\lab_data\virtual_uat.db"
python main.py --browser --host 0.0.0.0 --port 8080
```

Or double-click **`Start Virtual Lab.bat`**.

### LAN testers (same building)

- Server machine: `scripts\host_online.bat` or `Start Virtual Lab.bat`
- Clients: `http://<server-ip>:8080`
- Firewall: allow inbound TCP **8080**
- **One Chronos only** on that port

### Remote testers (different location) — full product

| Method | When | How |
|--------|------|-----|
| **Tunnel (fast)** | Same-day UAT from your PC | Double-click **`Start Remote UAT Tunnel.bat`** → send them the `https://…` URL |
| **Cloud VM** | Stable multi-day pilot | `docs/deploy/CLOUD_VM.md` + Docker/Caddy HTTPS |
| VPN | Dept already has VPN | Host on LAN; tester VPN then `http://internal-ip:8080` |

Tunnel needs **cloudflared** once: `winget install Cloudflare.cloudflared`

### Always-on (PC on → remote UAT up; tracks your code)

| Action | File |
|--------|------|
| **Install** (logon + start now) | **`Install Always-On UAT.bat`** |
| Show current URL | **`Show Remote UAT URL.bat`** |
| Uninstall / stop | **`Uninstall Always-On UAT.bat`** |
| URL text | `logs/remote_uat_url.txt` |
| Supervisor log | `logs/always_on_uat.log` |

Behavior:

- Starts **Chronos UAT lab + Cloudflare tunnel** when you sign into Windows
- **Restarts Chronos if it crashes** or if **you save code** under `gui/`, `logic/`, etc.
- Tunnel usually **stays up** across code restarts (quick-tunnel URL only changes if tunnel process dies)
- Testers: after you ship UI changes, they should **Ctrl+F5**

Power tip: set **Sleep = Never** while remotes are testing (Settings → System → Power).

**Stable hostname (recommended if you own a domain on Cloudflare):**

1. Double-click **`Setup Domain Tunnel.bat`**
2. Enter domain (e.g. `mypd.com`) and subdomain (default `chronos`)
3. Complete the one-time Cloudflare browser login
4. Share the fixed URL: `https://chronos.mypd.com` (never changes)

Files written: `lab_data/domain_tunnel.json` · `lab_data/cloudflared-chronos.yml`
Always-on reads those automatically (no fragile env-only setup).

CLI equivalent:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_domain_tunnel.ps1 -Domain mypd.com -Subdomain chronos
```

Otherwise each **quick tunnel** restart gets a new `*.trycloudflare.com` URL — always share the current value from `Show Remote UAT URL.bat`.

**What the remote tester does (full ability):**

1. Open the **one** `https://….trycloudflare.com` link (no install, no VPN).
2. Click **Enter full product (Administration)** — full left nav (roster, leave, ops, payroll, deploy, security, …).
3. Open **UAT Lab** in the nav (`/uat`) for a clickable map of **every** page.
4. Optional: sign out and try `supervisor` / `officer` to see limited roles.

`SCHEDULER_UAT_LAB=1` resets demo passwords, clears force-password-change, seeds sample leave/open shift, and enables the one-click button.

### Accounts

| Role | User | Password |
|------|------|----------|
| Administration | `admin` | `admin` |
| Supervisor | `supervisor` | `supervisor` |
| Officer | `officer` | `officer` |

Hard-refresh (Ctrl+F5) after CSS/theme pulls. Restart process after Python edits.

---

## 2. Role scenarios (human checklist)

Score each: **Pass / Fail / Blocked** + notes. Map to industry LE flows.

### A. Officer (self-service)

| # | Scenario | Steps | Pass if |
|---|----------|-------|---------|
| O1 | Sign in | Login form → shell | Duty Board / nav visible |
| O2 | My week | Open My Week | Own shifts readable |
| O3 | Request time off | Time Off → submit on a **working** day | Pending request appears |
| O4 | Open shift | Open Shifts list | Vacancy visible or empty state clear |
| O5 | Shift exchange | Start swap with peer | Request pending (or clear validation) |
| O6 | Notifications | Notifications tab | List or empty state (no crash) |

### B. Supervisor (coverage)

| # | Scenario | Steps | Pass if |
|---|----------|-------|---------|
| S1 | Ops Desk | Open Ops Desk | KPIs: leave, gaps, station, fatigue |
| S2 | Approve leave | Pick pending → plan → confirm | Approved **or** Manual Review (not silent fail) |
| S3 | Reject leave | Reject with notes | Status Rejected + notes stored |
| S4 | Approve swap | Swaps queue | Schedule reflects exchange or clear block reason |
| S5 | Callout / order-in | Callout ladder if available | Eligible list or honest empty |
| S6 | Manual cover | Assign cover for gap | Success **or** fatigue hard-stop message |

### C. Administration

| # | Scenario | Steps | Pass if |
|---|----------|-------|---------|
| A1 | Roster | Search / edit officer | Save + list refresh |
| A2 | Station bulk | Bulk set station if shown | Station board understaff updates |
| A3 | Payroll | Timecard entry | Hours on ledger |
| A4 | Pay period | Lock awareness | Lock or clear “not ready” |
| A5 | Deploy / publish | Preflight | Ready or listed blockers |
| A6 | Audit | Audit trail | Login + mutations listed |
| A7 | Security | LDAP IT export | Packet exports; `production_ready=false` until real AD |

### D. Cross-cutting (virtual)

| # | Scenario | Pass if |
|---|----------|---------|
| X1 | Brand | Product shows Chronos Command (CSS may paint CHRONOS COMMAND) |
| X2 | Offline multi-page | Cached pages offline still load where designed |
| X3 | Mobile width | Narrow window: bottom nav / My Week usable |
| X4 | Two roles | Admin approve after officer submit (same lab DB) |

---

## 3. Exit criteria

**UAT exit (virtual lab go):**

- All **O1–O3, S1–S2, A1, A6, X1** Pass
- No open **P0** (data loss, wrong coverage, auth bypass)
- Known residuals accepted in writing (below)

**Not required for this virtual lab:**

- Live Twilio/SMTP delivery
- LDAP `production_ready=true`
- Frozen `.exe` on every client (source/`main.py --browser` is enough for virtual)

---

## 4. Known residuals (do not file as bugs)

| Item | Policy |
|------|--------|
| Live SMS/email | **Deferred** — file/in-app sink only |
| LDAP production | Needs reachable AD + IT sign-off |
| Offline leave approve | **Intentional** supervisor safety block |
| Feature-map “partial” | Honest dual-rate: logic strong, Chronos depth still browser-proving |

---

## 5. Automated proof (no human)

```bat
python dev.py virtual-lab
python dev.py chronos-e2e --quick
python scripts/leave_flow_smoke.py
python scripts/payroll_flow_smoke.py
python scripts/deeper_ui_click_paths.py
```

Artifacts:

- `logs/virtual_lab_status.json`
- `logs/virtual_uat_scenarios.json`
- `logs/last_verify.json` (`honest_gate`)

---

## 6. Reset / safety

```bat
REM isolated lab only:
del lab_data\virtual_uat.db
REM main project DB (careful):
python dev.py reset-db
```

Do **not** point `SCHEDULER_DB_PATH` at production share during throwaway UAT.

---

## 7. 12-hour countdown (suggested)

| Hour | Work |
|------|------|
| 0–1 | `virtual-lab --ship`; fix any red gate |
| 1–2 | Start lab host; `chronos-e2e --quick` |
| 2–4 | Human O1–O3, S1–S2 (critical path) |
| 4–8 | Full role matrix; log fails in issue list |
| 8–10 | Fix P0 only; re-run residual + e2e quick |
| 10–12 | Exit review; update HANDOFF residuals; ship note |

**Vendor:** Weierworks Technologies, LLC · product **Chronos Command**
