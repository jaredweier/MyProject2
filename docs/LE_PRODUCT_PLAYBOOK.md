# LE / first-responder product playbook

**Purpose:** Ideas taken from **working public-safety scheduling & payroll products** (feature marketing, DOL FLSA rules, industry write-ups) — **reimplemented** in Chronos with our `logic/*` rules.
**Not** reverse-engineered proprietary source or UIs.

Sources researched (public pages / industry): Aladtec (TCP), Snap Schedule, inTime, Vector Solutions, First Due, Softworks, PowerTime, DOL FLSA §7(k).

---

## Patterns we stole → what we built

| Commercial pattern | Where it shows up in Chronos |
|--------------------|------------------------------|
| Open-shift / vacancy marketplace | `/open-shifts` · dashboard board · claim/assign |
| Annual / cycle **shift bidding** | `/bidding` · create draft · publish · preview · finalize |
| Coverage **gap board** (ops floor) | Dashboard + Ops Reports |
| **Hours / FLSA watch** (period thresholds) | Dashboard + Ops (`get_hours_watch`) |
| **Equitable OT ledger** | Ops Reports AG Grid (`get_equitable_ot_ledger`) |
| **My Week** officer self-service | Dashboard when officer-linked |
| Bulk approve “auto-OK” leave | Time Off → Bulk approve auto-OK |
| Roster CSV import | Roster → Import expansion |
| Dense payroll grid | Payroll ledger AG Grid |
| FLSA §7(k) work-period config | Payroll → FLSA panel (`get/save_flsa_settings`) |
| Pay period lock (close books) | Payroll → Lock current period |
| Timecard pay codes (OT/comp/night/court) | Timecards → Add Entry tab |
| OT alerts near threshold | Payroll page panel |
| Domain knowledge tool (learns) | `python dev.py fr-domain` |
| Cascading coverage / rest / night min | Already in logic (our differentiator vs retail tools) |

---

## Still valuable (not fully built)

| Pattern | Why agencies pay for it | Next step |
|---------|-------------------------|-----------|
| SMS / callback paging | Fill last-minute vacancies | Notify provider + open-shift hooks |
| Mobile app | Officers off-station | PWA / responsive Chronos |
| Court / subpoena module | inTime specialty | Request type + calendar flags (partial types exist) |
| Certification-gated fill | Only qualified on OT | Wire `logic/certifications.py` into open-shift claim |
| Seniority OT call-down list | Union fairness | Callback rotation UI on `logic/callbacks.py` |
| Comp time vs cash OT election | FLSA public sector | Timecard entry UX |
| 7(k) work-period config UX | 14-day 86h LE threshold | Surface `labor_compliance` settings in Chronos admin |

---

## Legal / product notes (FLSA ideas, not legal advice)

- LE often uses **§7(k)** work periods (e.g. 14 days / ~86h) instead of 40h weeks — see DOL Fact Sheet #8.
- Our hours watch + labor modules approximate this; configure thresholds in department settings.
- Equitable OT is a **grievance-prevention** feature, not optional chrome.

---

## Agent rule

When adding LE features: implement in `gui/` + existing `logic` first; do not invent parallel engines. Deposit new product ideas here.
