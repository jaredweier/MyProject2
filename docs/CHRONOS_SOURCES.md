# Chronos Command — External Sources (OPEN — not an allowlist)

**Purpose:** Optional starter docs for NiceGUI/Chronos.
**NOT exclusive.** Use any source that yields a better product.

**Tool:** `python dev.py ui-domain explore|brainstorm|research-queries|learn`
**Last researched:** 2026-07-09

### Agent rule (find → implement → deposit)
1. Search widely — any public web/GitHub/design/product source.
2. Implement the best patterns in-repo.
3. Deposit URLs via this file or `ui-domain learn`.
4. Report: searched → used → implemented → deposited.

---

## 1. NiceGUI (primary UI stack — `gui/`)

| Resource | URL | Use for Chronos |
|----------|-----|-----------------|
| **Docs home** | https://nicegui.io/documentation | API index; always prefer over guesswork |
| **Upload** | https://nicegui.io/documentation/upload | Media logo/photo: modern `e.file` / async read (not old `e.content`) |
| **Static files** | https://nicegui.io/documentation/section_pages_routing#add_a_directory_of_static_files | `app.add_static_files` for `gui/static/` — keep CSS/images out of WebSocket |
| **Storage / sessions** | https://nicegui.io/documentation/storage | Multi-user: `app.storage.user` / browser; requires `storage_secret` |
| **Config & deployment** | https://nicegui.io/documentation/section_configuration_deployment | Host/port, reload, **native mode**, `storage_secret`, Docker notes |
| **Security** | https://nicegui.io/documentation/section_security | Auth middleware patterns, what not to expose via static |
| **Testing** | https://nicegui.io/documentation/section_testing | UI automation without inventing a framework |
| **Examples hub** | https://nicegui.io/examples | Small runnable demos |
| **GitHub repo** | https://github.com/zauberzeug/nicegui | Source of truth for version-specific APIs (we track NiceGUI 3.x) |
| **Auth example** | https://github.com/zauberzeug/nicegui/tree/main/examples/authentication | Login gate + middleware; map to our `gui/session.py` + `logic` users |
| **Modularization** | https://github.com/zauberzeug/nicegui/blob/main/examples/modularization/main.py | Multi-page layout without duplicating chrome |
| **APIRouter example** | https://github.com/zauberzeug/nicegui/blob/main/examples/modularization/api_router_example.py | Prefix routers / larger apps |
| **Upload discussion (API drift)** | https://github.com/zauberzeug/nicegui/discussions/5320 | Confirms new upload field names (`e.file.name`, etc.) |
| **Shared layout / sub_pages** | https://github.com/zauberzeug/nicegui/discussions/5083 | Shell + content area pitfalls; avoid broken nested layouts |
| **Native + frozen packaging** | https://github.com/zauberzeug/nicegui/discussions/1714 | PyInstaller/shiv + `native=True` traps |
| **Auth/session gotchas** | https://github.com/zauberzeug/nicegui/discussions/4119 | Wrong user/event binding after login |
| **Auth + FastAPI patterns** | https://medium.com/towardsdev/user-authentication-and-authorization-in-nicegui-fastapi-35bfa8f73a14 | Middleware, storage choices (adapt; keep our password policy) |
| **Starter structure** | https://github.com/bitdoze/nicegui-starter | Optional layout reference only |
| **Talk Python #525 (NiceGUI 3.0)** | https://talkpython.fm/episodes/show/525/nicegui-goes-3.0 | Native mode, sticky sessions, packaging tradeoffs |

**In-repo application:** `gui/app.py`, `gui/shell.py`, `gui/static/chronos.css`, `gui/pages/*`. Prefer static CSS over huge inline HTML.

---

## 2. Underlying UI (Quasar / Vue — what NiceGUI wraps)

| Resource | URL | Use for Chronos |
|----------|-----|-----------------|
| **Quasar dark mode** | https://quasar.dev/style/dark-mode/ | `body--dark`, page background overrides |
| **Quasar colors / Sass vars** | https://quasar.dev/style/sass-scss-variables/ | Primary/secondary/accent; don’t fight Quasar defaults blindly |
| **Quasar layout / drawers** | https://quasar.dev/layout/drawer | Left nav rail patterns for command shell |
| **Quasar theme builder** | https://quasar.dev/style/theme-builder | Color experiments → export into `chronos.css` |

**In-repo application:** `gui/theme.py` + `gui/static/chronos.css` — navy/amber command theme; dark slate not pure black (`docs/UI_RESEARCH_BRIEF.md`).

---

## 3. Native window / downloadable client

| Resource | URL | Use for Chronos |
|----------|-----|-----------------|
| **pywebview** | https://pywebview.flowrl.com/ | Backend for NiceGUI `native=True` |
| **pywebview API** | https://pywebview.flowrl.com/api | Window args NiceGUI may forward |
| **PyInstaller** | https://www.pyinstaller.org/ | Windows downloadable builds (see in-repo build skill) |
| **NiceGUI native docs** | https://nicegui.io/documentation/section_configuration_deployment#native_mode | Official entry; Windows needs Edge/WebView2 stack |

**In-repo application:** launch modes in `gui/app.py`; build skill `.grok/skills/build-deploy/`.

---

## 4. Scheduling / calendar / roster (patterns only)

| Resource | URL | Use for Chronos |
|----------|-----|-----------------|
| **Schedule-X (JS calendar)** | https://github.com/schedule-x/schedule-x | Gantt/calendar UX patterns; optional future embed — **do not** replace `logic` rotation |
| **FullCalendar** (compare) | https://fullcalendar.io/docs | Industry schedule grid behaviors (read, don’t mandate) |
| **OR-Tools employee scheduling** | https://developers.google.com/optimization/scheduling/employee_scheduling | Official CP-SAT nurse/shift patterns |
| **OR-Tools shift_scheduling_sat.py** | https://github.com/google/or-tools/blob/main/examples/python/shift_scheduling_sat.py | Full constraint example |
| **OR-Tools CP-SAT primer** | https://github.com/d-krupke/cpsat-primer | Staff/shift assignment math learning |
| **In-repo CP-SAT bridge** | `logic/cp_sat_bridge.py` + `python dev.py math-scenarios --with-cpsat` | Optional what-if feasibility (not bump policy) |
| **SolverForge** (Timefold fork) | https://github.com/SolverForge/solverforge-legacy | Watch only — heavy; not wired |
| **Playwright Python intro** | https://playwright.dev/python/docs/intro | Chronos E2E: `python dev.py chronos-e2e` |
| **icalendar (PyPI)** | https://pypi.org/project/icalendar/ | RFC 5545; align with existing iCal export |
| **icalendar docs** | https://icalendar.readthedocs.io/ | DTSTART/TZID correctness for officer exports |
| **SmartBeats (LE patrol OSS)** | https://github.com/ASUCICREPO/smart-beats | Domain inspiration only (patrol areas ≠ our bump rules) |
| **Aladtec / public-safety WFM** (commercial ref) | Product sites / reviews | 24/7 coverage, OT, certs — UX expectations for PD schedulers |

**In-repo application:** `logic/scheduling.py`, `logic/snapshots.py`, `exports.py`, schedule pages under `gui/pages/schedules.py`. Domain facts: `docs/AGENT_STABLE.md`, `SCHEDULING_RULES.md`.

---

## 5. Timezones & date display (M/D/YY)

| Resource | URL | Use for Chronos |
|----------|-----|-----------------|
| **zoneinfo (stdlib)** | https://docs.python.org/3/library/zoneinfo.html | `America/Chicago` for Dodgeville; `SCHEDULER_TZ` override |
| **IANA tzdb** | https://www.iana.org/time-zones | Canonical zone names |
| **strftime reference** | https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes | zero-pads — **use** `validators.format_date` for unpadded `7/9/26` (July 9) |
| **ISO 8601 storage** | https://www.iso.org/iso-8601-date-and-time-format.html | Keep SQLite as `YYYY-MM-DD`; never “fix” storage to display format |

**Product rule:** display **month/day** short (`7/9/26` or `7-9-2026`); `/` or `-`; year 2 or 4 digits. Storage ISO. Inventory all display paths before claiming fixed.

**In-repo application:** `config.DATE_*`, `validators.format_date` / `parse_date`, `gui/clock.py`.

---

## 6. LE / command-center / product UX (look & language)

| Resource | URL | Use for Chronos |
|----------|-----|-----------------|
| **In-repo UI research** | `docs/UI_RESEARCH_BRIEF.md` | Mark43/Spillman/Aladtec/Deputy/Gusto/Linear patterns already mapped |
| **COPS / SEARCH LE dashboards** | Search: COPS LE dashboard design, SEARCH.gov tech | Severity-first KPIs |
| **USWDS** | https://designsystem.digital.gov/ | Federal plain language + form patterns (optional) |
| **18F / plain language** | https://plainlanguage.gov/ | Copy: Title Case labels, no “Good morning” fluff |

Steal **severity colors, density, status chips** — not product logos or CAD maps.

---

## 7. Security / multi-user / ops

| Resource | URL | Use for Chronos |
|----------|-----|-----------------|
| **NiceGUI security section** | https://nicegui.io/documentation/section_security | Don’t expose secrets via static routes |
| **OWASP ASVS / cheat sheets** | https://cheatsheetseries.owasp.org/ | Session, password, CSRF mindset |
| **NIST SP 800-63B** (auth) | https://pages.nist.gov/800-63-3/sp800-63b.html | Password policy alignment (we already harden demos) |
| **CJIS Security Policy** | FBI CJIS docs (search current PDF) | **Posture language only** unless dept certifies — UI green indicators ≠ certified |
| **FIPS 140** overview | NIST FIPS 140-3 | Same: honest posture vs marketing chrome |

**In-repo application:** `permissions.py`, `auth_password.py`, `gui/pages/security.py`, `logic/users.py`. Never claim CJIS/FIPS compliance from a green pill alone.

---

## 8. Agent / engineering tooling (free gates)

| Resource | URL / path | Use for Chronos |
|----------|------------|-----------------|
| **OpenCode** | https://github.com/anomalyco/opencode | Alternate agent; project already has `.opencode/` |
| **pre-commit** | https://pre-commit.com/ | `preflight` on commit |
| **Ruff** | https://docs.astral.sh/ruff/ | Lint via `dev.py lint` |
| **pip-audit** | https://github.com/pypa/pip-audit | `dev.py deps-audit` |
| **In-repo OSS tooling doc** | `docs/OPEN_SOURCE_TOOLING.md` | Full local wiring |

---

## 9. How agents should use this list

```text
1. Match task → section (e.g. upload bug → §1 Upload + discussion 5320)
2. Open 1–2 primary links (docs or official example) — not ten blogs
3. Compare with our code via outline/symbol (not whole-repo)
4. Implement in gui/ or validators only as appropriate
5. verify --tier fast; check before claiming done
6. If a new source proved essential, add one row to this file
```

### Search recipes (when list is stale)

```text
site:nicegui.io upload
site:github.com/zauberzeug/nicegui examples authentication
site:github.com/zauberzeug/nicegui discussions native pyinstaller
"NiceGUI" storage_secret multi-user
Quasar dark mode CSS variables body--dark
python zoneinfo America/Chicago
icalendar RFC 5545 python export
```

---

## 10. Explicit non-goals

- Do **not** replace `logic/*` with OR-Tools/Schedule-X unless product asks.
- Do **not** pull LLM frameworks into runtime UI.
- Do **not** copy commercial PD product trademarks into brand assets.
- Do **not** treat blog posts as higher authority than NiceGUI official docs + our tests.
