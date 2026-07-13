# First-responder WFM — agent learnings log

Append via `python dev.py fr-domain learn ...`. Summarize public sources only.

## 2026-07-09T08:52:26.477055+00:00 — deep-improve
Court/leave: explainable approve path; cert band gates UI; vacancy notify + alerts inbox; blackout conflicts

## 2026-07-09T08:59:34.509776+00:00 — commercial-2026
2026 police scheduling rankings emphasize Aladtec (TCP): shift scheduling, OT requests, cert tracking, communication, time-off, fatigue/coverage-gap alerts, department custom rules, reporting. inTime themes: court scheduling, OT management, fatigue tracking, shift bidding, analytics. Chronos should keep court/subpoena path, bid cycle, fatigue/hours watch, and gap alerts as first-class UI.
_source: tcpsoftware.com/articles/police-scheduling-software https://tcpsoftware.com/articles/police-scheduling-software/_

## 2026-07-09T08:59:34.919722+00:00 — flsa-7k
FLSA 7(k): work periods 7-28 consecutive days. LE OT after hours proportional to 171/28 (14-day LE = 86h; 7-day = 43h). Fire proportional to 212/28 (14-day fire = 106h). Not legal advice — product must show configurable threshold meters and work-period settings. Comp time public safety often capped at 480h banked; cash vs comp election is CBA-driven.
_source: DOL WHD Fact Sheet #8 https://www.dol.gov/agencies/whd/fact-sheets/8-flsa-police-firefighters_

## 2026-07-09T08:59:35.300953+00:00 — shift-bidding-cba
Police shift bidding: officers rank preferred shifts; awards by seniority almost always; annual/semi-annual bid seasons common (e.g. Oct bid for Jan assignments). Products need draft→publish→rank→preview awards→finalize. Participation reports defend fairness. Vacation bidding is separate seniority auction.
_source: inTime + Cedar City + Tacoma PD CBA patterns https://intime.com/industries/police/police-shift-bidding/_

## 2026-07-09T08:59:35.670520+00:00 — callback-odl
Call-back for vacancies often administered on rotating list regardless of length of callback (ODL). Court time often has minimums (2-3h) when off-duty appearance. Shift incentive differentials (e.g. 3-5% for evenings/nights) appear in CBAs. Chronos: callback rotation UI + pay-code uses_callback_minimum + night differential already exist — expose CBA knobs in pay-code UI.
_source: municipal CBA patterns (call back rotation) _

## 2026-07-09T08:59:36.048595+00:00 — aladtec-extra-hours
Aladtec Extra Hours: officers record unplanned shifts, holdovers, variances, unscheduled OT. Chronos analog: payroll entries + timecard add entry + open shifts; add holdover reason codes and supervisor Extra Hours queue if missing.
_source: EMS1 Aladtec Extra Hours https://www.ems1.com/ems-today/articles/aladtec-launches-extra-hours-function-for-cloud-based-scheduling-software-TToyJ1IZn0BE05b3/_

## 2026-07-09T08:59:36.473603+00:00 — ems-fire-software-2026
EMS/fire WFM 2026: complex 24/7 rotations (Kelly/Pitman/24-on), multi-station boards, credential gates, OT cost visibility, labor rules. First Due style drag-drop boards and today strip remain UI targets. Chronos police-first but FR domain should keep fire presets in idea backlog and cert gates.
_source: recruiterslineup EMS software 2026 https://www.recruiterslineup.com/best-ems-scheduling-software/_

## 2026-07-09T08:59:36.849025+00:00 — comp-cash-election
Public-sector officers often elect cash OT vs comp bank per entry or per CBA default. Product needs election toggle on OT lines and clear bank caps. Chronos has Comp Earned vs Overtime Earned codes — UI should make election explicit (not buried in code names).
_source: public sector OT practices _

## 2026-07-09T08:59:37.231615+00:00 — products-catalog-expand
Catalog beyond Aladtec/Snap/inTime: First Arriving (situational awareness displays with Aladtec staffing), Vector Solutions / Softworks / Hero Schedule, WhenToWork, Deputy (non-LE but roster patterns), PowerDMS policy for bid SOPs. Dig tool should append vendor functions when agents learn.
_source: web research 2026 _

## 2026-07-09T09:01:44.998118+00:00 — implemented-2026-07-09
From dig+research: shipped pay-code CBA UI (callback min, holiday mult), bid participation report + apply preview awards, timecard scope ledger (Extra Hours pattern), roster title rates + period hours + delete, holiday delete + unavail check, cash/comp election copy on timecard. Remaining thin: user CRUD mutators, PDF exports, simulator save/export, bid-from-sim.
_source: session dig implement _

## 2026-07-09T09:03:17.765034+00:00 — aladtec-mobile-2026
Aladtec mobile (TCP App Store): trades/giveaways/swaps, extra-duty requests, OT signup; admins: coverage alerts, min staffing, skills/certs, OT spend, agency comms. Chronos should keep open-shift claim + trades + cert gates + OT alerts as core; strengthen coverage-alert strip and Extra Hours path.
_source:  https://apps.apple.com/us/app/aladtec-by-tcp/id6736937495_

## 2026-07-09T09:03:18.191769+00:00 — powertime-cba
PowerDMS PowerTime LE: automated rest rules (no back-to-back), CBA rules engine for seniority bidding + fair OT, FLSA/comp tracking autopilot, off-duty special detail management, permanent audit trail, min staffing open shifts, email/mobile notifications, payroll exports from schedule. Mobile officers: view schedule, open shifts, time off, swaps. Pitman/8/10/12h templates. Chronos gaps to close: stronger fatigue strip, special-detail/extra-duty, payroll PDF export UI, audit visibility.
_source:  https://www.powerdms.com/industry/law-enforcement/powertime_

## 2026-07-09T09:03:18.594655+00:00 — intime-top5
InTime top police scheduling features: (1) mobile app access (2) visual dashboard: OT causes, equitable OT, sick leave, fatigue, leave forecasts, agency spend (3) scheduling intelligence with agency rules / double-book prevent / training non-compliance (4) automated time tracking schedule→timesheet→payroll (5) product demos. Modules: court+subpoena, vacation bidding, wellness, event/extra duty, training mgmt. Chronos: deepen dashboard KPIs, prefill timesheet, court leave types, fatigue visibility.
_source:  https://intime.com/industries/police/top-5-police-scheduling-software-features/_

## 2026-07-09T09:03:19.003170+00:00 — firstdue-shiftboard
First Due Scheduling: drag-drop shiftboard, multi-day/rotation views, roster count strip, employee center (banks/announcements/call shifts), certifications hub, call-shift rules (sorting, rankings, reset periods, deadlines), vacancy bidding from board, SMS/email/app vacancy notify, FLSA cycle reports, accrual banks. Chronos: today roster-count strip on dashboard + open-shift digests already partial.
_source:  https://www.firstdue.com/products/schedulingpersonnel_

## 2026-07-09T09:03:19.405149+00:00 — vector-callback
Vector Scheduling LE: mass callback SMS/push, rules-based automation, FLSA OT + accrual, time-off approval routing, open post fill. Pattern: expedite callbacks with multi-channel notify. Chronos: in-app + open-shift-digest; no SMS vendor yet but digests/create_notification path.
_source:  https://www.vectorsolutions.com/solutions/vector-scheduling/law-enforcement/_

## 2026-07-09T09:03:19.798649+00:00 — hero-schedule
Hero Schedule police: OT management, leave, trades, open shifts, FLSA compliance, pay period management, shift bidding. Logic-driven admin for OT/leave/open shifts; officers request TO/OT and see open shifts.
_source:  https://heroschedule.com/scheduling/police-departments/_

## 2026-07-09T09:03:20.196150+00:00 — flsa-comp-480
DOL/FLSA: public safety employees may accrue up to 480 hours comp time (not less than 1.5h banked per OT hour). At cap, additional OT must be cash. Employee must be permitted to use comp time unless unduly disruptive. Termination: pay out remaining comp. Agencies may set lower policy caps. Chronos must show 480h (or dept) cap on bank UI and force cash path near cap — not legal advice.
_source:  https://www.dol.gov/agencies/whd/fact-sheets/8-flsa-police-firefighters_

## 2026-07-09T09:03:20.594824+00:00 — snap-callout
Snap Schedule police: rotating shifts, OT management, seniority open-shift fill, automated callouts invite via SMS/in-app/voice, time-off + OT workflows, FLSA/shift premium policies, union compliance warnings.
_source:  https://www.snapschedule.com/industry/police-law-enforcement-scheduling/_

## 2026-07-09T09:03:20.996477+00:00 — tracwire-shift
Tracwire/SHIFT-class: work-period OT (7/14/28), rest period warnings, OT typed (internal/court/grant/special event), message blast available officers, claim from phone, export to payroll. Chronos should type OT notes/reasons and export payroll pack.
_source:  https://www.tracwire.com/law-enforcement-scheduling-software_

## 2026-07-09T09:03:21.393965+00:00 — industry-consensus-2026
2026 consensus across Aladtec/inTime/PowerTime/First Due/Vector/Snap/Hero: mobile officer self-service, min staffing + open shifts, seniority/CBA bid + fair OT, rest/fatigue rules, cert gates, court/extra-duty, schedule→timesheet→payroll export, multi-channel vacancy notify, visual command dashboard. Chronos already strong on rotation/bump/leave math; product excellence = expose those + fill export/fatigue/today-strip/comp-cap/user admin/PDF.
_source:  multi-vendor research 2026-07_

## 2026-07-09T09:05:16.404512+00:00 — deep-research-implement-2026-07-09
Deep dig across Aladtec/PowerTime/inTime/First Due/Vector/Hero/Snap/DOL: deposited 10+ learnings; KB 10 commercial products. Implemented: today roster-count strip + fatigue KPI on dashboard; FLSA 480h comp cap meter on banks; payroll PDF export; pending leave PDF; simulator save/CSV/bid-from-sim; access user role+password reset+dept setup. Thin queue ~0. Continue: court module depth, SMS vacancy (no vendor), PWA, special-detail billing.

## 2026-07-09T09:07:59.061791+00:00 — oss-timefold-constraints
Timefold/Opta employee scheduling: hard vs soft constraints — no overlap, min rest between shifts, max days/week, unavailable; soft: desired/undesired days, load-balance nights (fairness), optional shifts. Chronos already has rest/night min/bump scores; soft preference alignment maps to availability preferences + OT equity. Python quickstarts exist; OR-Tools/CP-SAT already optional in Chronos.
_source:  https://timefold.ai/videos/employee-shift-scheduling-ai-in-python_

## 2026-07-09T09:07:59.481306+00:00 — oss-staffjoy
Staffjoy open-source suite (Suite/Chomp/Mobius): algorithm-based publish shifts, cost-aware assignment, mobile companion. Pattern: separate decomposition (chomp) vs assignment (mobius). Chronos uses rust_bridge + coverage_optimizer beam search — similar split of generation vs pick.
_source:  https://www.staffjoy.com/_

## 2026-07-09T09:07:59.936530+00:00 — oss-auto-shift-planner
Auto Shift Planner (Java OSS): rule-based roster with heuristic/metaheuristic, portable no-install UX. Validates product demand for rule-first scheduling without cloud lock-in — Chronos on-prem SQLite path is aligned.
_source:  https://betaiotazeta.github.io/AutoShiftPlanner/_

## 2026-07-09T09:08:01.525916+00:00 — github-shift-mip
GitHub shift-scheduling MIP (Excel in → CSV out) and nurse rostering CP projects: classic data flow roster constraints → solver → export. Chronos already schedule→timecard→CSV/PDF; keep export-first supervisor workflows.
_source:  https://github.com/lbiedma/shift-scheduling_

## 2026-07-09T09:08:01.948345+00:00 — cad-rms-boundary
CAD/RMS literature (BJA LEITSC, Mark43, Tyler, CivicEye): CAD owns call-for-service real-time; RMS owns case records; WFM owns duty roster. Chronos stays WFM — integrate via exports/webhooks later, not full CAD. UI lesson: real-time duty strip and incident-adjacent open OT.
_source:  https://bja.ojp.gov/sites/g/files/xyckuh186/files/media/document/leitsc_law_enforcement_cad_systems.pdf_

## 2026-07-09T09:08:02.841957+00:00 — dwave-employee-scheduling
D-Wave employee-scheduling example: availability, forecasted demand, manager/trainee pairing. Maps to Chronos cert/FTO pairing idea backlog + min staffing by band.
_source:  https://github.com/dwave-examples/employee-scheduling_

## 2026-07-09T09:10:26.185306+00:00 — staffjoy-suite-code-arch
Read Staffjoy suite README architecture: Flask+MySQL+Redis; Chomp microservice creates shifts from forecast; Mobius assigns workers under constraints; cron every 60s on internal API; Twilio SMS; workers claim shifts. Config via env SECRET_KEY. Lesson for Chronos: keep rotation generation separate from bump assignment; digests as jobs not request-path; never put secrets in repo.
_source:  https://github.com/Staffjoy/suite_

## 2026-07-09T09:11:58.109128+00:00 — ukg-telestaff-deep
UKG TeleStaff Cloud (ex-Kronos): rules-based automation for fire/EMS/police/sheriff/dispatch/corrections. Modules: centralized static+rotation+daily roster; min-staffing roster alarms; vacancy fill using fatigue hours+certs+policy; notify text/email/voice; skills/certs matching; shift bidding for locations/shifts/days off; EXTRA DUTY EVENTS plan-staff-track-invoice; self-service trades/TO with auto-approve when rules pass; CAD/RMS/payroll integrations; BIRT reporting. Chronos: strengthen vacancy notify multi-channel, extra-duty invoicing, roster alarms UX.
_source:  https://www.ukg.com/products/ukg-telestaff_

## 2026-07-09T09:11:58.524292+00:00 — neogov-ta-payroll-deep
NEOGOV Time & Attendance/Payroll public sector: work rules engine for OT, meals, differentials; FLSA 7(k); leave donations; timesheet button convert OT→comp; blended rate; lookback OT in payroll module when FLSA cycle ≠ pay period; geofenced clock; hours auto-flow to payroll; pay codes drive tax/FLSA/GL. Chronos has 7k settings, banks, cash/comp codes, prefill, period lock — missing leave donation and dual lookback UI.
_source:  https://www.neogov.com/products/time-and-attendance-software_

## 2026-07-09T09:11:58.928156+00:00 — netchex-dual-workforce
Netchex LE/sheriff payroll pattern: dual OT in one run (sworn 7k + civilian 40h); comp 480h public safety / 240h other; specialty assignment pay into regular rate; shift differentials blended for FLSA; off-duty detail tracking. Chronos single FLSA profile — dual workforce is frontier.
_source:  https://netchex.com/blog/payroll-software-sheriffs-offices-law-enforcement/_

## 2026-07-09T09:11:59.352513+00:00 — eso-fire-ems-scheduling
ESO Scheduling: fire/EMS roster inside records ecosystem; call-outs, swaps, PTO; cert+immunization readiness; live unit/station/shift dashboard; open shift bid; sync to Fire RMS/ePCR. Chronos cert gates exist; station multi-post and immunizations frontier.
_source:  https://www.eso.com/fire/_

## 2026-07-09T09:11:59.855315+00:00 — crewsense-vector-ot
TargetSolutions Scheduling / CrewSense / Vector: fire-EMS-police scheduling + OT management + training adjacency; OT equalization; compliance analytics. Complements Vector Scheduling LE callback SMS/push.
_source:  https://www.targetsolutions.com/_

## 2026-07-09T09:12:00.357437+00:00 — eschedule-police-time
eSchedule police software: schedule + automatic timekeeping for regular/OT/PTO; payroll/audit reports. Reinforces schedule→timesheet→payroll single path Chronos is building.
_source:  https://goeschedule.com/police-scheduling-software/_

## 2026-07-09T09:12:00.905453+00:00 — imagetrend-slate
ImageTrend Slate: EMS/fire crew scheduling for critical services — availability, assignments, coverage. EMS-first constraint set differs from patrol squad bands.
_source:  https://www.imagetrend.com/platform/scheduling-software/_

## 2026-07-09T09:12:01.346152+00:00 — frontier-registry-2026
Expanded KB to 18 commercial products + research_frontiers list (TeleStaff extra duty, NEOGOV leave donation, Netchex dual OT, ESO station posts, ImageTrend EMS, CrewSense OT equity, PeopleSoft 7k, ADP export maps, IAFF FLSA manual, municipal RFPs). fr-domain dig now surfaces frontiers.
_source:  session deep dive_

## 2026-07-09T09:15:53.401399+00:00 — source-eval-implement-2026-07-09
Built source-eval over 18 products. Implemented from evaluation: TeleStaff extra_duty (open_shift tagged EXTRA_DUTY) ops panel; NEOGOV convert_overtime_to_comp + UI; Netchex dual FLSA settings (dual flag, civilian weekly thr, sworn/civilian comp caps); OR-Tools-style score_components on coverage plans. Still MISS: leave donation, station posts, immunizations, geofence, blended rate, voice SMS.

## 2026-07-09T09:18:29.120533+00:00 — frontiers-closed-2026-07-09
Closed frontiers: leave donation (table+API+UI), blended OT rate, station/workforce_class on roster, IMM_* immunization types+status UI, extra-duty invoice CSV, ADP payroll pack. Remaining: voice SMS, geofence, full dual OT engine, multi-station mins, court calendar depth, PeopleSoft/IAFF/RFP research.

## 2026-07-09T09:20:53.246104+00:00 — eval-research-2026-07-09-no-impl
Industry eval themes (do not implement yet): schedule-to-payroll reconciliation is top failure mode; fatigue/rest blocks; dual workforce 7k vs 40h; TeleStaff launch pain is rules config not features; Vector/CrewSense emphasizes callback + min staffing + consecutive hours; Netchex warns LE scheduling rarely integrates to generic payroll without explicit 7k docs. Chronos audit goal: prove our gates still pass after feature flood.
_source:  https://netchex.com/blog/payroll-software-sheriffs-offices-law-enforcement/_

## 2026-07-09T09:20:53.752949+00:00 — telestaff-rfp-themes
TeleStaff LE materials: unlimited schedules, multi-shift rotation, future-deployed + extra-duty, skill/cert/availability matching, union/HR/fatigue rules, bidding, notifications. Implementation services exist because rules engines are hard — Chronos risk is similar: many knobs, regression risk. Evaluation priority over new features.
_source:  https://www.ukg.com/products/ukg-telestaff_
