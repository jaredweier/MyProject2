# Graph Report - .  (2026-07-09)

## Corpus Check
- 434 files · ~400,572 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3131 nodes · 9106 edges · 155 communities (141 shown, 14 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 568 edges (avg confidence: 0.67)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Format Date()
- Dev
- Test Database()
- Fr Domain
- Parse Date()
- Get Connection()
- Bidding
- Timecard
- Coverage Optimizer
- Period
- Get Any Officer()
- Officer Uses Command Staff Schedule()
- Requests
- Labor Compliance
- Rust Bridge
- Database
- Operations
- Simulator
- App
- Staffing Config
- Route Task()
- Scheduling
- Roster
- Validators
- Config
- Lib
- Verify
- Ui Exhaustive Test
- Layout()
- App (2)
- Assets
- Run Ui Aesthetics Review()
- Helpers
- Math Scenarios
- Snapshots
- Card
- Leave
- PrimaryButton
- Working Date For Squad()
- Test Validators
- Session
- Suggest Bump Chain Py()
- Display
- Font()
- RotationSchedule
- TimecardScheduleTests
- Banked Time
- Officers
- Batch Process
- Session (2)
- Clock
- Dashboard
- Helpers (2)
- Run Token Audit()
- Startup Gates
- Certs
- Widgets
- Context Window
- Ui Test Helpers
- Aggrid From Dicts()
- Refactor Check
- Get Officer By Id()
- Outline File()
- Run Graphify Gate()
- Run Slice Check()
- Test Position Pay
- Validators Config
- VerifyUnifiedTests
- Roster Cmds
- BasePage
- .configure()
- Get Active Rotation Cycle Length()
- Resource Path()
- Rotation
- Run Usage Brief()
- Registry
- Check Read()
- Run Session Start()
- Structure Lint
- Ui Domain
- Run Ui Visual Diff()
- Ui Workflow Probe
- Tier2FeatureTests
- Icons
- Simulate Schedule Py()
- Agent Gates
- Run Lint()
- LaborComplianceTests
- Source Eval
- Extra Duty
- Opencode
- Build Agent Pack()
- Minimum Rest Gap Hours With Times()
- Test Database Backup
- Roster (2)
- Run Ui Exhaustive()
- Get Officers By Seniority()
- Compute Shift Coverage Counts()
- Validate Minimum Rest Gap()
- Local Dispatch
- Split Finance Payroll
- ContextWindowTests
- Explain Coverage Plans()
- Rust Fallback
- Export Project Code
- Get Pending Day Off Requests()
- StartupGatesTests
- Build Frozen Eval
- Extract Logic Modules
- Extract Ui Mixins
- Split Ui Monoliths
- AgentGatesTests
- Image
- Rebuild Ui Mixins
- TokenAuditTests
- TokenScanTests
- List Backup Files()
- Command
- Run Build Rust()
- Run Chronos E2e()
- Run Fix Hint()
- Run Read Budget()
- Structured Output
- Run Ui Handler Coverage()
- Ui Mixin Import Check
- Date
- List Notifications()
- Agent Pack
- Check
- Context Window (2)
- Fix Hint
- Lint
- Route Task
- Token Audit
- Ui Observe
- Usage Brief
- Detect Truncated Functions
- Extract Logic Core Trim
- Extract Logic Requests
- Rebuild Logic Monolith
- Split Scheduling Sim
- Split Validators Config
- Mdy Datetime()
- Init
- Init (2)
- Init (3)
- Dodgeville Scheduler

## God Nodes (most connected - your core abstractions)
1. `test_database()` - 256 edges
2. `get_connection()` - 191 edges
3. `format_date()` - 144 edges
4. `get_any_officer()` - 136 edges
5. `parse_date()` - 113 edges
6. `working_date_for_squad()` - 84 edges
7. `main()` - 79 edges
8. `main()` - 71 edges
9. `get_officer_by_id()` - 71 edges
10. `get_officers_by_seniority()` - 66 edges

## Surprising Connections (you probably didn't know these)
- `cmd_audit()` --calls--> `run_audit()`  [INFERRED]
  dev.py → audit.py
- `cmd_logic_imports()` --calls--> `run_audit()`  [INFERRED]
  dev.py → audit.py
- `list_requests()` --calls--> `get_day_off_requests()`  [INFERRED]
  cli.py → logic/requests.py
- `submit_request_cmd()` --calls--> `create_day_off_request()`  [INFERRED]
  cli.py → logic/requests.py
- `fill_open_shift_cmd()` --calls--> `fill_open_shift()`  [INFERRED]
  cli.py → logic/operations.py

## Import Cycles
- None detected.

## Communities (155 total, 14 thin omitted)

### Community 0 - "Format Date()"
Cohesion: 0.06
Nodes (86): Backward-compat shim — implementation lives in logic/analytics.py., _build_doc(), generate_coverage_pdf(), generate_pay_stub_pdf(), generate_payroll_pdf(), generate_requests_pdf(), generate_schedule_pdf(), generate_shift_swaps_pdf() (+78 more)

### Community 1 - "Dev"
Cohesion: 0.05
Nodes (75): cmd_agent_gates(), cmd_agent_kit(), cmd_agent_pack(), cmd_audit(), cmd_batch_process(), cmd_build_portable(), cmd_build_rust(), cmd_cheap_check() (+67 more)

### Community 2 - "Test Database()"
Cohesion: 0.05
Nodes (9): Provide an isolated SQLite DB path; resets env and modules cleanly., test_database(), AnalyticsTests, AuthTests, Auth and user account tests., OfficerCrudTests, PayCodeRulesTests, RosterImportTests (+1 more)

### Community 3 - "Fr Domain"
Cohesion: 0.06
Nodes (71): cmd_next(), cmd_patterns(), cmd_recipe(), cmd_scaffold(), cmd_show(), cmd_thin(), cmd_wire(), Enterprise software acceleration kit for Chronos.  Surfaces patterns, scaffolds (+63 more)

### Community 4 - "Parse Date()"
Cohesion: 0.07
Nodes (61): add_availability_cmd(), add_holiday_cmd(), assign_override_cmd(), availability_conflicts_cmd(), backup_create(), backup_restore_cmd(), create_user_cmd(), delete_availability_cmd() (+53 more)

### Community 5 - "Get Connection()"
Cohesion: 0.08
Nodes (47): hash_password(), Password hashing utilities — PBKDF2 with legacy plaintext fallback., verify_password(), get_connection(), cancel_shift_bid_event(), create_shift_bid_event(), create_shift_bid_from_simulation(), Create a draft shift bid (optionally publish) from simulator results. (+39 more)

### Community 6 - "Bidding"
Cohesion: 0.07
Nodes (55): assignments_shift_bid_cmd(), list_shift_bids_cmd(), participation_shift_bid_cmd(), preview_shift_bid_cmd(), reassign_shift_bid_cmd(), show_shift_bid_cmd(), submit_shift_bid_cmd(), _apply_event_award_schedule() (+47 more)

### Community 7 - "Timecard"
Cohesion: 0.10
Nodes (48): get_pay_stub_preview(), callback_payable_hours(), Minimum paid hours for call-back / call-in (FLSA hours worked)., _ensure_officer_time_banks(), _months_between(), date, Officer time-bank accrual bootstrap and bulk rate tools., create_payroll_entry() (+40 more)

### Community 8 - "Coverage Optimizer"
Cohesion: 0.10
Nodes (47): CoveragePolicy, list_scored_replacements(), load_coverage_policy(), optimize_day_off_coverage(), parse_min_staffing_by_band(), _plan_score(), Configurable coverage optimizer for day-off bumps and staffing scenarios.  Works, All eligible replacements with multi-objective scores (best first). (+39 more)

### Community 9 - "Period"
Cohesion: 0.09
Nodes (49): import_timecard_to_payroll(), annual_salary_to_per_pay_period(), count_pay_periods_in_year(), format_pay_period_label(), get_adjacent_cycle_window(), get_adjacent_pay_period(), get_pay_period(), get_pay_period_history() (+41 more)

### Community 10 - "Get Any Officer()"
Cohesion: 0.07
Nodes (5): get_any_officer(), BankedTimeTests, TestPayroll, Seniority rank applies only to Vacation requests — senior officers first in gran, TestRegressions

### Community 11 - "Officer Uses Command Staff Schedule()"
Cohesion: 0.05
Nodes (6): CoverageOptimizerTests, Rotation and bump tests — isolated in-memory DB per test (avoids Windows file lo, TestRotationLogic, Rust bridge and scheduling math parity (Python fallback always; Rust when built), RustBridgeTests, officer_uses_command_staff_schedule()

### Community 12 - "Requests"
Cohesion: 0.08
Nodes (43): approve_request(), approve_swap(), create_swap_cmd(), read_notification(), reject_request(), reject_swap(), _handle_swap(), describe_day_off_request() (+35 more)

### Community 13 - "Labor Compliance"
Cohesion: 0.10
Nodes (45): _flsa_panel(), §7(k) work-period knobs — industry LE payroll pattern., get_hours_watch(), FLSA-oriented hours watch: weekly and pay-period threshold warnings., compute_fatigue_score(), count_consecutive_work_days_ending(), describe_consecutive_work_violation(), flsa_threshold_for_period_days() (+37 more)

### Community 14 - "Rust Bridge"
Cohesion: 0.08
Nodes (32): Validate and persist rotation settings; returns active config snapshot., save_rotation_settings(), available(), backend_name(), batch_day_status(), build_schedule_matrix(), compute_coverage_counts(), consecutive_work_days() (+24 more)

### Community 15 - "Database"
Cohesion: 0.08
Nodes (38): _backfill_payroll_pay_period_start(), connection(), _drop_legacy_shift_bid_tables(), _ensure_department_setting_defaults(), _ensure_indexes(), _ensure_schema_migrations(), _ensure_tier2_tables(), init_database() (+30 more)

### Community 16 - "Operations"
Cohesion: 0.09
Nodes (40): backup_database(), Replace the live database from a backup file.     Creates a pre-restore safety, restore_database(), add_holiday(), apply_position_pay_rates_to_roster(), delete_holiday(), delete_officer_availability(), fill_open_shift() (+32 more)

### Community 17 - "Simulator"
Cohesion: 0.10
Nodes (29): optimize_staffing_scenarios(), Sweep simulator configs and rank by coverage quality.      Optimizes for: fewest, get_simulator_defaults_from_roster(), Schedule simulation and coverage-plan preview helpers.  Extracted from ``logic, Find best rotation/officer-count/min-staffing combination via scenario sweep., run_schedule_simulation(), run_staffing_optimizer(), _assign_officers() (+21 more)

### Community 18 - "App"
Cohesion: 0.09
Nodes (16): gui_gate_warning_if_failed(), Show non-blocking warning if last startup gate failed., DodgevilleSchedulerApp, _install_tk_error_handler(), Dodgeville PD Scheduler — rebuilt UI (grid shell + modular pages)., Single app object: session + pure-grid shell + page controllers., run(), handle_export_result() (+8 more)

### Community 19 - "Staffing Config"
Cohesion: 0.13
Nodes (31): staffing_settings_cmd(), get_shift_number(), allowed_bump_sources_for_shift(), build_shift_times(), can_officer_cover_shift(), _format_minutes(), get_active_annual_hours_target(), get_active_bump_rules() (+23 more)

### Community 20 - "Route Task()"
Cohesion: 0.09
Nodes (30): cmd_route_task(), _complexity(), _cost_tier(), _cursor_mode(), _do_not(), format_recommendation(), _match_domain(), _model_tier() (+22 more)

### Community 21 - "Scheduling"
Cohesion: 0.11
Nodes (38): is_high_risk_night(), _show_plans(), get_coverage_gap_board(), get_coverage_report(), Near-term staffing gaps for the on-duty squad (today through hours_ahead)., _shift_starts(), _bump_capacity_exhausted(), compute_minimum_rest_gap() (+30 more)

### Community 22 - "Roster"
Cohesion: 0.09
Nodes (35): page_login(), page_media(), page_roster(), brand_dir(), data_uri(), logo_display(), _mime(), photo_display() (+27 more)

### Community 23 - "Validators"
Cohesion: 0.19
Nodes (33): validate_staffing_settings(), Centralized validation for Dodgeville PD Scheduler. All request/schedule checks, FLSA public-sector compensatory time accrual cap (default 480h)., Department fatigue rule — max consecutive scheduled work days., _time_to_minutes(), validate_annual_hours_target(), validate_app_user_role(), validate_availability_entry() (+25 more)

### Community 24 - "Config"
Cohesion: 0.11
Nodes (29): Dodgeville Police Department Scheduler Centralized configuration, constants, an, _event_list(), _officer_bid_form(), Shift bidding — annual/cycle bid events (Snap/Aladtec pattern).  Logic lives in, Submit preference ranks for open bid events (Aladtec/Snap officer participation), _banks(), Finance NiceGUI pages — split from monolith for maintainability., _resolve_bank_officer_id() (+21 more)

### Community 25 - "Lib"
Cohesion: 0.19
Nodes (35): PyAny, PyList, PyModule, batch_day_status(), build_schedule_matrix(), compute_coverage_counts(), consecutive_work_days(), covering_shifts_from_py() (+27 more)

### Community 26 - "Verify"
Cohesion: 0.08
Nodes (30): Ultra-fast gate — delegates to unified verify tier 'fast'., run_cheap_check(), Pre-commit gate — delegates to unified verify tier 'preflight'., run_preflight(), Fast readiness gate — catches failures that imports/audit miss (UI probe + core, _run_login_probe(), run_readiness_check(), _run_readiness_unittests() (+22 more)

### Community 27 - "Ui Exhaustive Test"
Cohesion: 0.11
Nodes (33): _close_toplevels(), _confirm_yesno(), _destroy_app(), _entries_in(), _invoke_button(), _login_admin(), _login_role(), _open_dialog_without_wait() (+25 more)

### Community 28 - "Layout()"
Cohesion: 0.13
Nodes (26): format_local_date(), M/D/YY — e.g. 7/9/26 for July 9, 2026., Access control — logins and roles (enterprise user admin)., render_access(), Callback / OT desired list rotation — inTime/Snap fairness pattern., render_callbacks(), Duty board — SHIFTVOID / PULSE mockup layout., render_dashboard() (+18 more)

### Community 29 - "App (2)"
Cohesion: 0.08
Nodes (28): configure_logging(), Configure file/console logging once (call from app entry, not on import)., _ensure_static_css(), page_access(), page_availability(), page_bidding(), page_callbacks(), page_home() (+20 more)

### Community 30 - "Assets"
Cohesion: 0.11
Nodes (27): Image, main(), Regression tests for supervisor-ready UI gates (catch false-positive smoke)., Login must paint brand images and complete headless shell login., ui-smoke must finish (no hang) and return 0 — catches login handler storms., TestUiReadiness, _apply_rounded_border(), _cover_crop() (+19 more)

### Community 31 - "Run Ui Aesthetics Review()"
Cohesion: 0.12
Nodes (29): build_rows(), _exists(), FeatureRow, _gui_mentions(), _logic_has(), Law-enforcement scheduling feature benchmark — free local checklist.  Compares C, run_le_benchmark(), _check_aesthetics_source() (+21 more)

### Community 32 - "Helpers"
Cohesion: 0.08
Nodes (21): AuditFinding, print_report(), Regression audit for known scheduling bugs. Run: python dev.py audit, run_audit(), Run SCHEDULING_RULES.md regression scenarios S-01 through S-11., _run_all(), ScenarioResult, Fast integration smoke tests — core scheduling flows without the GUI. (+13 more)

### Community 33 - "Math Scenarios"
Cohesion: 0.14
Nodes (28): demo_week_instance(), format_solution_report(), ortools_available(), Optional Google OR-Tools CP-SAT bridge for multi-day staffing feasibility.  Does, Compact multi-day multi-band staffing problem (scenario math only)., Synthetic week for free math demos (no DB)., OR-Tools-style human report of feasibility + named soft penalties., CP-SAT: assign each officer 0..1 band per day such that each (day, band)     mee (+20 more)

### Community 34 - "Snapshots"
Cohesion: 0.12
Nodes (29): _notify_schedule_published(), batch_officer_day_status(), build_schedule_matrix(), _load_override_maps_for_range(), _officer_day_status(), Resolve schedule status for many (officer_id, date) pairs with one override load, Return bumped/covering/swapped maps and per-day bumped schedule statuses., _schedule_status_for_override_reason() (+21 more)

### Community 35 - "Card"
Cohesion: 0.16
Nodes (15): AccessPage, Access control — user list + basic create., Base page — every screen is a full-grid CTkFrame with optional scroll body., BankedTimePage, PayrollPage, Timecard, banked time, payroll — essential finance surfaces., TimecardPage, Modular page controllers for the rebuilt UI. (+7 more)

### Community 36 - "Leave"
Cohesion: 0.10
Nodes (29): page_live(), page_monthly(), page_my_schedule(), page_time_off(), date, today_local(), _active_officers(), _approve() (+21 more)

### Community 37 - "PrimaryButton"
Cohesion: 0.15
Nodes (14): Refresh live schedule, timeline, dashboard, and timecard after schedule changes., User-facing date placeholder (M/D/YY e.g. 7/9/26)., refresh_after_schedule_change(), today_placeholder(), Time off + shift exchange — coverage-first leave workflows., RequestsPage, SwapsPage, Staffing simulator — single run + best-combination sweep. (+6 more)

### Community 38 - "Working Date For Squad()"
Cohesion: 0.11
Nodes (5): Rotation day when the squad is on duty (stable date near TEST_REFERENCE_DATE)., working_date_for_squad(), BumpSameShiftTests, Bump/coverage with duplicate shift bands and custom staffing settings., TestNotificationsSwapsExports

### Community 39 - "Test Validators"
Cohesion: 0.11
Nodes (10): create_day_off_request(), TestValidators, is_night_shift(), is_officer_active(), _night_shift_starts(), validate_cycle_date(), validate_day_off_request(), validate_manual_override() (+2 more)

### Community 40 - "Session"
Cohesion: 0.12
Nodes (13): can(), current_user(), display_name(), initials(), is_officer(), linked_officer_id(), Any, Browser/session state for multi-user web + desktop clients. (+5 more)

### Community 41 - "Suggest Bump Chain Py()"
Cohesion: 0.23
Nodes (26): assignment_exhausted(), can_cover_shift(), dict_result(), find_replacement(), is_night_shift(), night_minimum_uncovered(), normalize_shift_band(), officer_full_to_status() (+18 more)

### Community 42 - "Display"
Cohesion: 0.14
Nodes (26): apply_login_window_layout(), center_window(), center_window_win32(), configure_ctk_scaling(), _env_ui_scale(), _geometry_scale(), _monitor_work_area(), Display scaling and window placement (DPI, centering, login vs main layout). (+18 more)

### Community 43 - "Font()"
Cohesion: 0.13
Nodes (4): CTkFont, font(), MetricRow, SegmentBar

### Community 44 - "RotationSchedule"
Cohesion: 0.18
Nodes (22): consecutive_work_days_ending(), consecutive_work_message(), exceeds_consecutive_work_limit(), is_working_status(), Officer, String, RotationSchedule, is_command_staff_title() (+14 more)

### Community 45 - "TimecardScheduleTests"
Cohesion: 0.10
Nodes (3): seed_users_if_empty(), Tests for analytics, holidays, availability, and exports., TimecardScheduleTests

### Community 46 - "Banked Time"
Cohesion: 0.16
Nodes (24): _collect_payroll_bank_events(), _collect_timecard_bank_events(), _date_clause(), _deltas_from_payroll_row(), get_bank_transactions(), get_banked_time_summary(), get_timecard_entries_for_scope(), _merge_bank_events() (+16 more)

### Community 47 - "Officers"
Cohesion: 0.14
Nodes (24): add_officer(), delete_officer(), get_pay_period_hours_by_officer(), get_suggested_seniority_rank(), get_supervisors(), import_roster_from_csv(), date, Officer roster CRUD, lookup, photos, and pay-period hour totals. (+16 more)

### Community 48 - "Batch Process"
Cohesion: 0.20
Nodes (16): _classify_item(), _err(), _extract_item(), load_payload(), _ok(), process_batch(), Any, Batch independent items — output JSON array aligned by input index. (+8 more)

### Community 49 - "Session (2)"
Cohesion: 0.13
Nodes (10): CTk, apply_main_window_layout(), clear_login_window_layout(), Stop login-only centering handlers before maximizing the main shell., Maximize once at startup. Re-entrant handlers must not call this repeatedly., Session lifecycle — login, permissions, shell teardown., SessionMixin, Main window placement — maximize and focus after login. (+2 more)

### Community 50 - "Clock"
Cohesion: 0.17
Nodes (19): department_tz(), format_clock(), format_local_datetime(), now_local(), datetime, Department-local real time for Chronos Command UI.  User-facing dates: M/D/YY (e, M/D/YY HH:MM in department local time — e.g. 7/9/26 14:30., timezone_label() (+11 more)

### Community 51 - "Dashboard"
Cohesion: 0.15
Nodes (12): get_unread_notification_count(), get_department_branding(), Department name, mission, and tagline for UI surfaces., Return display strings for department branding., active_officers(), LoginFrame, Login — split brand panel + secure access form., DashboardPage (+4 more)

### Community 52 - "Helpers (2)"
Cohesion: 0.11
Nodes (19): CTkToplevel, ask_save_csv(), cancel_pending_after(), export_date_status_filters(), handle_logic_result(), label_has_image(), logic_message(), logic_success() (+11 more)

### Community 53 - "Run Token Audit()"
Cohesion: 0.18
Nodes (19): cmd_token_minimize(), Check, _cursorignore_blocks_large_dump(), _exists(), _opencode_minimal(), Verify token-minimization artifacts and settings — no LLM required., _read(), run_token_audit() (+11 more)

### Community 54 - "Startup Gates"
Cohesion: 0.16
Nodes (19): install(), install_git_refresh_hooks(), Install local token-minimization hooks (git + verify Cursor hooks)., verify_cursor_hooks(), _write_executable(), install(), _install_simple_hook(), Install git pre-commit hooks — full framework when available, simple fallback ot (+11 more)

### Community 55 - "Certs"
Cohesion: 0.19
Nodes (18): page_certs(), Certifications — LE/fire quals gate (PowerTime / Snap pattern)., render_certs(), _board(), LE self-service surfaces (open shift vacancy board).  Patterns from public-safet, _cert_is_valid(), get_officer_certifications(), get_shift_cert_requirements() (+10 more)

### Community 56 - "Widgets"
Cohesion: 0.22
Nodes (12): is_future_cycle_window(), LiveSchedulePage, OriginalSchedulePage, Schedule views — monthly base/live + duty timeline., _ScheduleBase, TimelinePage, CompactButton, CoverageBadge (+4 more)

### Community 57 - "Context Window"
Cohesion: 0.31
Nodes (20): add_decision(), advance_turn(), apply_summary(), build_summary(), load_state(), mark_keep(), mark_referenced(), maybe_summarize() (+12 more)

### Community 58 - "Ui Test Helpers"
Cohesion: 0.17
Nodes (19): main(), Run one UI smoke role in an isolated process (fresh Tk root)., assert_login_handlers_cleared(), assert_nav_contains(), assert_nav_excludes(), create_headless_app(), destroy_app(), enable_ui_test_mode() (+11 more)

### Community 59 - "Aggrid From Dicts()"
Cohesion: 0.16
Nodes (19): aggrid, Day-level working headcount from published base snapshot., Base vs live row diffs (enterprise schedule compare)., _render_monthly_headcount(), _render_schedule_diff_panel(), aggrid_from_dicts(), _clean_rows(), Any (+11 more)

### Community 60 - "Refactor Check"
Cohesion: 0.19
Nodes (18): audit_logic_imports(), _collect_from_ast(), _collect_from_regex(), collect_imported_symbols(), _iter_py_files(), _logic_exports(), Verify all `logic` imports resolve against logic.py exports., run_audit() (+10 more)

### Community 61 - "Get Officer By Id()"
Cohesion: 0.17
Nodes (18): _content(), get_callback_events(), get_callback_ledger(), get_callback_rotation(), get_next_callback_candidate(), date, Call-back rotation list and event tracking., Summary for Ops Reports — rotation order + recent events. (+10 more)

### Community 62 - "Outline File()"
Cohesion: 0.15
Nodes (11): outline_file(), AST outline of a Python file — minimal tokens vs full read., _resolve(), run_outline(), _definitions_in_file(), _iter_py_files(), lookup_symbol(), Find where a symbol is defined — avoid full-repo reads. (+3 more)

### Community 63 - "Run Graphify Gate()"
Cohesion: 0.18
Nodes (18): _find_graphify(), graph_stale(), _iter_watched_files(), main(), _newest_watched(), _node_count(), Path, Ensure graphify knowledge graph exists and stays current (code-only AST, free). (+10 more)

### Community 64 - "Run Slice Check()"
Cohesion: 0.15
Nodes (12): _step_slice_check(), _find_slice(), _logic_has(), _page_keys(), Vertical slice map and integrity checks., Run verify commands registered for a single vertical slice., run_slice_check(), run_slice_map() (+4 more)

### Community 65 - "Test Position Pay"
Cohesion: 0.12
Nodes (4): PositionPayTests, RosterTitleTests, is_yearly_salary_title(), monthly_pay_to_hourly()

### Community 66 - "Validators Config"
Cohesion: 0.15
Nodes (16): is_officer_unavailable_on_date(), parse_squad_a_days_text(), Parse comma/space-separated or JSON list of cycle days (1..cycle_length)., can_officer_work_day_band(), parse_bids_due_datetime(), date, datetime, Department settings, bidding eligibility, and certification validators. (+8 more)

### Community 67 - "VerifyUnifiedTests"
Cohesion: 0.16
Nodes (5): is_subset(), True when every child step appears in parent tier in the same relative order., tier_steps(), Unified verification — tiers must be strict supersets, no duplicate/conflicting, VerifyUnifiedTests

### Community 68 - "Roster Cmds"
Cohesion: 0.20
Nodes (15): add_officer(), add_officer_title_cmd(), delete_officer_cmd(), dispatch_officers(), import_officers_cmd(), list_officer_titles_cmd(), list_officers(), Officer roster CLI commands. (+7 more)

### Community 69 - "BasePage"
Cohesion: 0.12
Nodes (8): CTkFrame, CTkLabel, CTkScrollableFrame, BasePage, Consistent layout: fill parent grid, optional header + scroll body., Override to reload data when page is shown., Full-page scroll host — use for stacked cards/lists., Two-column layout filling the page (form | list).

### Community 70 - ".configure()"
Cohesion: 0.16
Nodes (5): CTkImage, render_icon(), ExpandableSection, NavButton, StatCard

### Community 71 - "Get Active Rotation Cycle Length()"
Cohesion: 0.30
Nodes (13): get_active_rotation_base_date(), get_active_rotation_cycle_length(), get_active_rotation_preset_name(), get_active_squad_a_days(), get_rotation_config(), get_rust_rotation_schedule(), _get_setting(), get_squad_on_duty() (+5 more)

### Community 72 - "Resource Path()"
Cohesion: 0.17
Nodes (12): _bootstrap_runtime(), Entry point for Dodgeville PD Scheduler — Duty Console (web + desktop)., Frozen .exe: cwd + crash log next to the executable., app_dir(), is_frozen(), Application paths — works in development and PyInstaller bundles., Resolve bundled assets (logo, team photo) in dev and frozen builds., resource_path() (+4 more)

### Community 73 - "Rotation"
Cohesion: 0.16
Nodes (13): dodgeville_squad_days(), is_high_risk_night_ordinal(), is_high_risk_night_weekday(), ordinal_to_weekday(), RotationMode, HashSet, PyDict, String (+5 more)

### Community 74 - "Run Usage Brief()"
Cohesion: 0.20
Nodes (10): register_tool_from_read(), estimate_tokens(), file_stats(), format_stats_row(), Rough token estimates for files and text (chars / 4 heuristic)., _head(), Print minimal agent context — slice-scoped files and verify commands., run_usage_brief() (+2 more)

### Community 75 - "Registry"
Cohesion: 0.17
Nodes (13): Print UI ↔ logic ↔ CLI feature coverage map.  UI ✓ requires at least one exist, True only when every listed ui_file exists, and at least one is listed., run_feature_map(), _ui_files_exist(), Vertical slice registry — feature-oriented project map., features_for_map(), get_slice(), Any (+5 more)

### Community 76 - "Check Read()"
Cohesion: 0.21
Nodes (8): check_read(), known_large_ui_files(), _norm(), Shared read-guard rules for Cursor hooks and token tooling., Large indexable product modules — prefer outline/symbol (ui/, gui/, logic/)., ReadGuardResult, Tests for read_guard., ReadGuardTests

### Community 77 - "Run Session Start()"
Cohesion: 0.20
Nodes (12): cmd_session_start(), _head(), One free command: minimal agent bootstrap for any session (token-first)., _run(), run_agent_kit(), _check(), Environment and project health checks for Dodgeville PD Scheduler., run_doctor() (+4 more)

### Community 78 - "Structure Lint"
Cohesion: 0.21
Nodes (14): check_analytics_shim(), check_cli_thin(), check_mixin_inheritance(), check_monolith_sizes(), check_ui_import_logic_package(), check_ui_no_sql(), _py_files(), Path (+6 more)

### Community 79 - "Ui Domain"
Cohesion: 0.35
Nodes (14): cmd_brainstorm(), cmd_chronos_map(), cmd_explore(), cmd_learn(), cmd_research_queries(), cmd_show(), cmd_suggest(), load_ideas() (+6 more)

### Community 80 - "Run Ui Visual Diff()"
Cohesion: 0.25
Nodes (10): _compare_images(), _filter_quick(), _is_quick_shot(), _latest_live_dir(), _list_pngs(), Compare ui-live screenshots against baselines (Pillow — already a project depend, Nav + login screenshots only (01–15): fast layout smoke., run_ui_visual_diff() (+2 more)

### Community 81 - "Ui Workflow Probe"
Cohesion: 0.30
Nodes (14): _check_day_off_approval_chain(), _check_demo_password_policy(), _check_headless_ui_shell(), _check_password_change_login_path(), _check_pay_period_lock(), _check_rust_backend(), _check_window_layout_guard(), _fail() (+6 more)

### Community 83 - "Icons"
Cohesion: 0.26
Nodes (12): ImageDraw, clear_icon_cache(), _icon_calendar(), _icon_dashboard(), _icon_leave(), _icon_officers(), _icon_operations(), _icon_payroll() (+4 more)

### Community 84 - "Simulate Schedule Py()"
Cohesion: 0.20
Nodes (13): format_minutes(), is_night_shift_start(), parse_minutes(), Bound, HashSet, PyDict, PyObject, PyResult (+5 more)

### Community 85 - "Agent Gates"
Cohesion: 0.25
Nodes (13): agent_context_hint(), auto_after_route_task(), auto_before_dev_command(), auto_before_session(), detect_slice_id(), _git_changed_files(), Automatic agent token-minimization gates.  Refreshes logs/agent_pack/latest.md a, One-line hint for agents (paste into logs or print). (+5 more)

### Community 86 - "Run Lint()"
Cohesion: 0.18
Nodes (7): Dependency vulnerability scan via pip-audit (PyPI advisory DB)., run_deps_audit(), Ruff lint and format gate — free OSS alternative to agent code review., _ruff_cmd(), run_lint(), OssToolsTests, Tests for OSS dev tooling wrappers.

### Community 88 - "Source Eval"
Cohesion: 0.24
Nodes (12): cmd_source_eval(), Evaluate all catalogued FR programs vs Chronos → implement queue., cmd_implement(), cmd_show(), evaluate_products(), _load_kb(), _probe_chronos(), Any (+4 more)

### Community 89 - "Extra Duty"
Cohesion: 0.22
Nodes (12): create_extra_duty_event(), _decode_notes(), _encode_notes(), export_extra_duty_invoice_csv(), list_extra_duty_events(), Extra duty / special detail — TeleStaff / Netchex / PowerTime pattern.  Uses ope, TeleStaff-style cost-recovery export: event, location, billing code, hours windo, List shifts tagged EXTRA_DUTY (TeleStaff-style special detail). (+4 more)

### Community 90 - "Opencode"
Cohesion: 0.15
Nodes (12): compaction, auto, prune, reserved, instructions, permission, bash, edit (+4 more)

### Community 91 - "Build Agent Pack()"
Cohesion: 0.26
Nodes (12): build_agent_pack(), build_agent_pack_json(), _git_touch_status(), _head(), _last_gate(), Build a minimal pasteable agent context pack — one file instead of repo dump., Ultra-compact machine-readable pack for tooling., run_agent_pack() (+4 more)

### Community 92 - "Minimum Rest Gap Hours With Times()"
Cohesion: 0.52
Nodes (11): effective_band_start(), meets_minimum_rest(), minimum_rest_gap_hours(), minimum_rest_gap_hours_with_times(), minimum_rest_message(), parse_minutes(), CoveringShiftStarts, Officer (+3 more)

### Community 93 - "Test Database Backup"
Cohesion: 0.21
Nodes (5): DatabaseBackupTests, file_test_database(), Database backup slice — manual, auto, restore, and status., Isolated on-disk DB for restore tests (in-memory URIs cannot be restored)., _sqlite_backup()

### Community 94 - "Roster (2)"
Cohesion: 0.32
Nodes (6): Patrol roster — clean list + detail form., RosterPage, SearchBar, StatusBadge, format_officer_shift_display(), parse_officer_shift_ui()

### Community 95 - "Run Ui Exhaustive()"
Cohesion: 0.25
Nodes (10): _acquire_exhaustive_lock(), _lock_holder_alive(), Prevent concurrent exhaustive runs (they deadlock headless Tk login)., _release_exhaustive_lock(), run_ui_exhaustive(), main(), _pid_alive(), Live on-screen UI test — visible window, auto-login, screenshots per step.  Uses (+2 more)

### Community 96 - "Get Officers By Seniority()"
Cohesion: 0.22
Nodes (10): _add_entry(), Quick timecard line — Regular / OT cash / Comp / Night diff (FR pay-code set)., get_equitable_ot_ledger(), Fairness ledger: OT/comp hours by officer vs squad average for the pay period., get_officers_by_seniority(), Roster list sorted by seniority rank (ascending) for UI display and vacation gra, rank_open_shift_candidates(), TeleStaff-style vacancy ranking: certs + rest + fatigue/OT equity + junior-first (+2 more)

### Community 97 - "Compute Shift Coverage Counts()"
Cohesion: 0.27
Nodes (9): compute_shift_coverage_counts(), normalize_shift_band(), parse_minutes(), HashMap, Officer, Option, PyResult, String (+1 more)

### Community 98 - "Validate Minimum Rest Gap()"
Cohesion: 0.31
Nodes (8): _hypothesis_available(), _hypothesis_battery(), _pure_fuzz(), Property-style fuzz for scheduling invariants — free local CPU.  Uses Hypothesis, Optional Hypothesis-powered properties., run_fuzz_scheduling(), True if gap_hours is None (no adjacent shift) or meets minimum rest., validate_minimum_rest_gap()

### Community 99 - "Local Dispatch"
Cohesion: 0.31
Nodes (7): list_catalog(), LocalPlan, main(), plan_local(), Route trivial/low tasks to the **physical machine** (free local tools) — $0 LLM, run_local_dispatch(), LocalDispatchTests

### Community 100 - "Split Finance Payroll"
Cohesion: 0.38
Nodes (9): _func_ranges(), _lines(), main(), Path, One-shot architecture split: finance UI + logic/payroll packages.  Preserves pub, 1-indexed inclusive line slice., _slice(), split_finance() (+1 more)

### Community 102 - "Explain Coverage Plans()"
Cohesion: 0.33
Nodes (8): explain_coverage_plans(), explain_replacement_components(), explain_score_weights(), Any, Explainable coverage plans — math-domain / supervisor trust.  Formats multi-plan, Document soft-score formula (mirrors coverage_optimizer.list_scored_replacements, OR-Tools-style component print for one candidate., Turn preview_best_coverage_plans result into multi-line supervisor text.

### Community 103 - "Rust Fallback"
Cohesion: 0.28
Nodes (8): date, python_batch_day_status(), python_build_schedule_matrix(), python_compute_coverage_counts(), Emergency Python implementations for scheduling math.  Used only when scheduler_, Build roster matrix without Rust., Resolve statuses without Rust — mirrors scheduler_core batch_day_status., Shift headcount batch without Rust.

### Community 104 - "Export Project Code"
Cohesion: 0.47
Nodes (8): collect_files(), encode_binary(), main(), Path, Concatenate project source into a single text file for offline reference., read_as_text(), should_include(), write_file_section()

### Community 105 - "Get Pending Day Off Requests()"
Cohesion: 0.25
Nodes (8): list_pending_requests(), list_requests(), _print_requests_table(), bulk_reject_pending_requests(), get_pending_day_off_requests(), Vacation grants use seniority (lower rank = more senior); other types sort by da, Reject standard Pending requests; skips Pending Manual Review., _sort_for_vacation_granting()

### Community 107 - "Build Frozen Eval"
Cohesion: 0.48
Nodes (6): _copy_snapshot(), main(), Path, _run(), _write_frozen_marker(), _write_readme()

### Community 108 - "Extract Logic Modules"
Cohesion: 0.57
Nodes (6): _extract_module(), _function_ranges(), _inject_core_reexports(), _inject_lazy_imports(), _inject_officers_lazy(), main()

### Community 109 - "Extract Ui Mixins"
Cohesion: 0.57
Nodes (6): _build_imports(), _collect_extra_methods(), _extract_chunk(), _find_line(), main(), _parse_app_imports()

### Community 110 - "Split Ui Monoliths"
Cohesion: 0.48
Nodes (6): main(), Path, Split ui/feature_pages.py and ui/schedule_pages.py into slice modules., split_feature_pages(), split_schedule_pages(), _write()

### Community 112 - "Image"
Cohesion: 0.33
Nodes (6): attachment, image, auto_resize, max_base64_bytes, max_height, max_width

### Community 113 - "Rebuild Ui Mixins"
Cohesion: 0.60
Nodes (5): _body_only(), main(), _read(), _slice_by_marker(), _write_mixin()

### Community 116 - "List Backup Files()"
Cohesion: 0.40
Nodes (5): backup_list_cmd(), list_backup_files(), Return backup .db paths under backups/, newest first., get_backup_status(), Latest backup age for dashboard reminders and admin UI.

### Community 117 - "Command"
Cohesion: 0.40
Nodes (5): description, subtask, template, command, cheap-check

### Community 118 - "Run Build Rust()"
Cohesion: 0.60
Nodes (4): _has_virtualenv(), Build the scheduler_core Rust extension via maturin., run_build_rust(), _verify_import()

### Community 119 - "Run Chronos E2e()"
Cohesion: 0.60
Nodes (4): main(), playwright_available(), Optional Chronos NiceGUI E2E smoke via Playwright (local machine, cheap).  Insta, run_chronos_e2e()

### Community 120 - "Run Fix Hint()"
Cohesion: 0.60
Nodes (4): Suggest free next steps after a failed gate — no LLM required., run_fix_hint(), _slice_for_path(), read_verify_state()

### Community 121 - "Run Read Budget()"
Cohesion: 0.60
Nodes (4): estimate_path(), main(), Estimate tokens before reading files — free gate to avoid whole-file waste., run_read_budget()

### Community 122 - "Structured Output"
Cohesion: 0.50
Nodes (4): _pick(), Structured JSON output — fixed fields only, no prose., One index-aligned batch element with schema fields only., shape_batch_row()

### Community 123 - "Run Ui Handler Coverage()"
Cohesion: 0.60
Nodes (4): _collect_test_steps(), _collect_ui_commands(), Report UI handler coverage — maps command= handlers in ui/ to exhaustive test st, run_ui_handler_coverage()

### Community 124 - "Ui Mixin Import Check"
Cohesion: 0.70
Nodes (4): check_file(), _collect_defs_and_imports(), main(), AST

### Community 125 - "Date"
Cohesion: 0.40
Nodes (5): is_command_staff_weekday(), _mdy_short(), date, Command staff work Monday–Friday (weekday 0–4)., UI date: M/D/YY with no leading zeros — e.g. 7/9/26 (July 9, 2026).

### Community 126 - "List Notifications()"
Cohesion: 0.50
Nodes (4): list_notifications(), get_notifications(), Map a notification to a UI navigation target, or None if not navigable., resolve_notification_navigation()

### Community 127 - "Agent Pack"
Cohesion: 0.50
Nodes (4): description, subtask, template, agent-pack

### Community 128 - "Check"
Cohesion: 0.50
Nodes (4): description, subtask, template, check

### Community 129 - "Context Window (2)"
Cohesion: 0.50
Nodes (4): context-window, description, subtask, template

### Community 130 - "Fix Hint"
Cohesion: 0.50
Nodes (4): fix-hint, description, subtask, template

### Community 131 - "Lint"
Cohesion: 0.50
Nodes (4): lint, description, subtask, template

### Community 132 - "Route Task"
Cohesion: 0.50
Nodes (4): route-task, description, subtask, template

### Community 133 - "Token Audit"
Cohesion: 0.50
Nodes (4): token-audit, description, subtask, template

### Community 134 - "Ui Observe"
Cohesion: 0.50
Nodes (4): ui-observe, description, subtask, template

### Community 135 - "Usage Brief"
Cohesion: 0.50
Nodes (4): usage-brief, description, subtask, template

### Community 136 - "Detect Truncated Functions"
Cohesion: 0.67
Nodes (3): detect_truncated(), main(), Detect logic.py functions that may be truncated (fall through to next def).

### Community 137 - "Extract Logic Core Trim"
Cohesion: 0.83
Nodes (3): _extract_functions(), _function_ranges(), main()

### Community 138 - "Extract Logic Requests"
Cohesion: 0.83
Nodes (3): _function_ranges(), _inject_lazy_imports(), main()

### Community 142 - "Mdy Datetime()"
Cohesion: 0.67
Nodes (3): _mdy_datetime(), datetime, UI datetime: M/D/YY HH:MM — e.g. 7/9/26 14:30.

## Knowledge Gaps
- **45 isolated node(s):** `Officer`, `$schema`, `instructions`, `small_model`, `auto` (+40 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_connection()` connect `Get Connection()` to `Format Date()`, `Test Database()`, `Parse Date()`, `Bidding`, `Timecard`, `Coverage Optimizer`, `Period`, `Get Any Officer()`, `Requests`, `Labor Compliance`, `Database`, `Operations`, `Scheduling`, `Validators`, `Helpers`, `Snapshots`, `Working Date For Squad()`, `Test Validators`, `TimecardScheduleTests`, `Banked Time`, `Officers`, `Dashboard`, `Certs`, `Get Officer By Id()`, `Validators Config`, `Ui Workflow Probe`, `LaborComplianceTests`, `Extra Duty`, `Get Officers By Seniority()`, `Get Pending Day Off Requests()`, `List Notifications()`?**
  _High betweenness centrality (0.114) - this node is a cross-community bridge._
- **Why does `test_database()` connect `Test Database()` to `Get Connection()`, `Coverage Optimizer`, `Get Any Officer()`, `Officer Uses Command Staff Schedule()`, `Rust Bridge`, `Database`, `Simulator`, `Staffing Config`, `Ui Exhaustive Test`, `Helpers`, `Math Scenarios`, `Working Date For Squad()`, `Test Validators`, `TimecardScheduleTests`, `Test Position Pay`, `Get Active Rotation Cycle Length()`, `Ui Workflow Probe`, `Tier2FeatureTests`, `LaborComplianceTests`, `Test Database Backup`?**
  _High betweenness centrality (0.099) - this node is a cross-community bridge._
- **Why does `format_date()` connect `Format Date()` to `Dev`, `Parse Date()`, `Bidding`, `Timecard`, `Period`, `Requests`, `Labor Compliance`, `Rust Bridge`, `Simulator`, `App`, `Scheduling`, `Validators`, `Config`, `Layout()`, `App (2)`, `Snapshots`, `Card`, `Leave`, `PrimaryButton`, `Test Validators`, `Font()`, `TimecardScheduleTests`, `Banked Time`, `Clock`, `Dashboard`, `Helpers (2)`, `Certs`, `Widgets`, `Aggrid From Dicts()`, `Get Officer By Id()`, `Validators Config`, `Roster Cmds`, `Get Active Rotation Cycle Length()`, `Extra Duty`, `Validate Minimum Rest Gap()`, `Get Pending Day Off Requests()`, `Date`?**
  _High betweenness centrality (0.097) - this node is a cross-community bridge._
- **What connects `Backward-compat shim — implementation lives in logic/analytics.py.`, `Regression audit for known scheduling bugs. Run: python dev.py audit`, `Password hashing utilities — PBKDF2 with legacy plaintext fallback.` to the rest of the system?**
  _583 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Format Date()` be split into smaller, more focused modules?**
  _Cohesion score 0.0565088080530771 - nodes in this community are weakly interconnected._
- **Should `Dev` be split into smaller, more focused modules?**
  _Cohesion score 0.048618048618048616 - nodes in this community are weakly interconnected._
- **Should `Test Database()` be split into smaller, more focused modules?**
  _Cohesion score 0.046620046620046623 - nodes in this community are weakly interconnected._
