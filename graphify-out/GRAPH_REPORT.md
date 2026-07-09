# Graph Report - .  (2026-07-09)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 3110 nodes · 9067 edges · 155 communities (135 shown, 20 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 566 edges (avg confidence: 0.67)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `dd0cea35`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- dev.py
- cli.py
- fr_domain.py
- working_date_for_squad
- test_database
- timecard.py
- database.py
- Card
- bidding.py
- format_date
- get_connection
- coverage_optimizer.py
- config.py
- verify.py
- PrimaryButton
- math_scenarios.py
- entries.py
- get_any_officer
- labor_compliance.py
- get_officer_by_id
- staffing_config.py
- app.py
- snapshots.py
- dashboard.py
- simulator.py
- lib.rs
- run_ui_aesthetics_review
- validators.py
- test_validators.py
- scheduling.py
- rust_bridge.py
- app.py
- helpers.py
- route_task
- font
- log_audit_action
- ui_exhaustive_test.py
- aggrid_from_dicts
- widgets.py
- suggest_bump_chain_py
- display.py
- clock.py
- session.py
- banked_time.py
- photos.py
- RotationSchedule
- ui_test_helpers.py
- media.py
- layout
- batch_process.py
- schedules.py
- TimecardScheduleTests
- TestRotationLogic
- helpers.py
- assets.py
- DodgevilleSchedulerApp
- run_token_audit
- get_active_rotation_cycle_length
- startup_gates.py
- normalize_officer_job_title
- refactor_check.py
- context_window.py
- parse_date
- leave.py
- SessionMixin
- certs.py
- outline_file
- run_slice_check
- test_position_pay.py
- validators_config.py
- get_current_cycle_window
- VerifyUnifiedTests
- rotation.rs
- agent_gates.py
- run_usage_brief
- registry.py
- check_read
- run_agent_kit
- dump_json
- structure_lint.py
- ui_domain.py
- run_ui_visual_diff
- ui_workflow_probe.py
- Tier2FeatureTests
- extra_duty.py
- icons.py
- get_position_pay_rates
- simulate_schedule_py
- run_lint
- roster_titles.py
- source_eval.py
- opencode.json
- LaborComplianceTests
- minimum_rest_gap_hours_with_times
- test_database_backup.py
- test_ui_readiness.py
- build_agent_pack
- run_ui_exhaustive
- compute_shift_coverage_counts
- split_finance_payroll.py
- ContextWindowTests
- applies_night_minimum
- rust_fallback.py
- export_project_code.py
- StartupGatesTests
- build_frozen_eval.py
- extract_logic_modules.py
- extract_ui_mixins.py
- split_ui_monoliths.py
- AgentGatesTests
- .scroll_body
- image
- rebuild_ui_mixins.py
- run_ui_observe
- TokenAuditTests
- TokenScanTests
- command
- run_build_rust
- run_chronos_e2e
- run_read_budget
- authenticate_role
- run_ui_handler_coverage
- ui_mixin_import_check.py
- agent-pack
- check
- context-window
- fix-hint
- lint
- route-task
- token-audit
- ui-observe
- usage-brief
- detect_truncated_functions.py
- extract_logic_core_trim.py
- extract_logic_requests.py
- rebuild_logic_monolith.py
- split_scheduling_sim.py
- split_validators_config.py
- validate_minimum_rest_gap
- _mdy_datetime
- analytics.py
- __init__.py
- __init__.py
- __init__.py
- is_command_staff_weekday
- dodgeville-scheduler
- period.py

## God Nodes (most connected - your core abstractions)
1. `test_database()` - 256 edges
2. `get_connection()` - 191 edges
3. `format_date()` - 144 edges
4. `get_any_officer()` - 136 edges
5. `parse_date()` - 113 edges
6. `working_date_for_squad()` - 84 edges
7. `main()` - 79 edges
8. `get_officer_by_id()` - 71 edges
9. `main()` - 70 edges
10. `get_officers_by_seniority()` - 66 edges

## Surprising Connections (you probably didn't know these)
- `cmd_audit()` --calls--> `run_audit()`  [INFERRED]
  dev.py → audit.py
- `cmd_logic_imports()` --calls--> `run_audit()`  [INFERRED]
  dev.py → audit.py
- `list_pending_requests()` --calls--> `get_pending_day_off_requests()`  [INFERRED]
  cli.py → logic/requests.py
- `list_requests()` --calls--> `get_day_off_requests()`  [INFERRED]
  cli.py → logic/requests.py
- `approve_request()` --calls--> `process_day_off_request()`  [INFERRED]
  cli.py → logic/requests.py

## Import Cycles
- None detected.

## Communities (155 total, 20 thin omitted)

### Community 0 - "dev.py"
Cohesion: 0.05
Nodes (73): cmd_agent_gates(), cmd_agent_kit(), cmd_agent_pack(), cmd_batch_process(), cmd_build_portable(), cmd_build_rust(), cmd_cheap_check(), cmd_check() (+65 more)

### Community 1 - "cli.py"
Cohesion: 0.05
Nodes (75): add_availability_cmd(), add_holiday_cmd(), approve_request(), approve_swap(), assign_override_cmd(), assignments_shift_bid_cmd(), availability_conflicts_cmd(), backup_create() (+67 more)

### Community 2 - "fr_domain.py"
Cohesion: 0.06
Nodes (71): cmd_next(), cmd_patterns(), cmd_recipe(), cmd_scaffold(), cmd_show(), cmd_thin(), cmd_wire(), Enterprise software acceleration kit for Chronos.  Surfaces patterns, scaffolds (+63 more)

### Community 3 - "working_date_for_squad"
Cohesion: 0.05
Nodes (21): AuditFinding, Regression audit for known scheduling bugs. Run: python dev.py audit, run_audit(), Run SCHEDULING_RULES.md regression scenarios S-01 through S-11., _run_all(), ScenarioResult, Fast integration smoke tests — core scheduling flows without the GUI., _result() (+13 more)

### Community 4 - "test_database"
Cohesion: 0.05
Nodes (7): Provide an isolated SQLite DB path; resets env and modules cleanly., test_database(), AnalyticsTests, AuthTests, PayCodeRulesTests, RosterImportTests, UserSecurityTests

### Community 5 - "timecard.py"
Cohesion: 0.15
Nodes (31): is_pay_period_locked(), approve_timecard_period(), _approved_day_off_request_type(), auto_prefill_timecard_from_live_schedule(), copy_timecard_from_previous_period(), delete_timecard_entry(), get_officer_live_schedule_day(), get_pay_period_hours_summary() (+23 more)

### Community 6 - "database.py"
Cohesion: 0.06
Nodes (47): hash_password(), Password hashing utilities — PBKDF2 with legacy plaintext fallback., verify_password(), _backfill_payroll_pay_period_start(), connection(), _drop_legacy_shift_bid_tables(), _ensure_department_setting_defaults(), _ensure_indexes() (+39 more)

### Community 7 - "Card"
Cohesion: 0.11
Nodes (25): BasePage, Base page — every screen is a full-grid CTkFrame with optional scroll body., Consistent layout: fill parent grid, optional header + scroll body., Override to reload data when page is shown., BankedTimePage, PayrollPage, Timecard, banked time, payroll — essential finance surfaces., TimecardPage (+17 more)

### Community 8 - "bidding.py"
Cohesion: 0.08
Nodes (52): post_shift_bid_event_cmd(), show_shift_bid_cmd(), _apply_event_award_schedule(), auto_close_expired_shift_bid_events(), build_shift_bid_payload_from_simulation(), _create_event_options(), create_shift_bid_event(), create_shift_bid_from_simulation() (+44 more)

### Community 9 - "format_date"
Cohesion: 0.12
Nodes (50): export_coverage(), _build_doc(), generate_coverage_pdf(), generate_pay_stub_pdf(), generate_payroll_pdf(), generate_requests_pdf(), generate_schedule_pdf(), generate_shift_swaps_pdf() (+42 more)

### Community 10 - "get_connection"
Cohesion: 0.08
Nodes (52): get_connection(), _content(), cancel_shift_bid_event(), get_callback_events(), get_callback_ledger(), get_callback_rotation(), get_next_callback_candidate(), date (+44 more)

### Community 11 - "coverage_optimizer.py"
Cohesion: 0.10
Nodes (44): CoveragePolicy, list_scored_replacements(), load_coverage_policy(), optimize_day_off_coverage(), parse_min_staffing_by_band(), _plan_score(), Configurable coverage optimizer for day-off bumps and staffing scenarios.  Works, All eligible replacements with multi-objective scores (best first). (+36 more)

### Community 12 - "config.py"
Cohesion: 0.08
Nodes (37): Dodgeville Police Department Scheduler Centralized configuration, constants, an, page_bidding(), page_timecards(), _event_list(), _officer_bid_form(), Shift bidding — annual/cycle bid events (Snap/Aladtec pattern).  Logic lives in, Submit preference ranks for open bid events (Aladtec/Snap officer participation), render_bidding() (+29 more)

### Community 13 - "verify.py"
Cohesion: 0.06
Nodes (38): print_report(), cmd_verify_features(), Full-stack verification — unified release tier (no duplicate subprocess gates)., Ultra-fast gate — delegates to unified verify tier 'fast'., run_cheap_check(), Suggest free next steps after a failed gate — no LLM required., run_fix_hint(), _slice_for_path() (+30 more)

### Community 14 - "PrimaryButton"
Cohesion: 0.11
Nodes (19): Refresh live schedule, timeline, dashboard, and timecard after schedule changes., User-facing date placeholder (M/D/YY e.g. 7/9/26)., refresh_after_schedule_change(), today_placeholder(), AccessPage, Access control — user list + basic create., Time off + shift exchange — coverage-first leave workflows., RequestsPage (+11 more)

### Community 15 - "math_scenarios.py"
Cohesion: 0.10
Nodes (35): demo_week_instance(), format_solution_report(), ortools_available(), Optional Google OR-Tools CP-SAT bridge for multi-day staffing feasibility.  Does, Compact multi-day multi-band staffing problem (scenario math only)., Synthetic week for free math demos (no DB)., OR-Tools-style human report of feasibility + named soft penalties., CP-SAT: assign each officer 0..1 band per day such that each (day, band)     mee (+27 more)

### Community 16 - "entries.py"
Cohesion: 0.10
Nodes (40): _preview_bank_deltas(), Compute bank deltas for reporting without balance-cap enforcement., callback_payable_hours(), Minimum paid hours for call-back / call-in (FLSA hours worked)., _ensure_officer_time_banks(), _months_between(), date, Officer time-bank accrual bootstrap and bulk rate tools. (+32 more)

### Community 17 - "get_any_officer"
Cohesion: 0.08
Nodes (4): get_any_officer(), BankedTimeTests, TestNotificationsSwapsExports, TestPayroll

### Community 18 - "labor_compliance.py"
Cohesion: 0.11
Nodes (41): _flsa_panel(), §7(k) work-period knobs — industry LE payroll pattern., get_labor_compliance_report(), compute_fatigue_score(), count_consecutive_work_days_ending(), describe_consecutive_work_violation(), flsa_threshold_for_period_days(), get_fatigue_score_threshold() (+33 more)

### Community 19 - "get_officer_by_id"
Cohesion: 0.08
Nodes (39): delete_officer(), describe_day_off_request(), get_officer_by_id(), get_pay_period_hours_by_officer(), get_request_reviewer_officer_ids(), get_suggested_seniority_rank(), get_supervisors(), date (+31 more)

### Community 20 - "staffing_config.py"
Cohesion: 0.13
Nodes (31): staffing_settings_cmd(), render_simulator(), allowed_bump_sources_for_shift(), build_shift_times(), can_officer_cover_shift(), _format_minutes(), get_active_annual_hours_target(), get_active_bump_rules() (+23 more)

### Community 21 - "app.py"
Cohesion: 0.09
Nodes (29): configure_logging(), Configure file/console logging once (call from app entry, not on import)., CTk, Logger, gui_gate_warning_if_failed(), Show non-blocking warning if last startup gate failed., _install_tk_error_handler(), Dodgeville PD Scheduler — rebuilt UI (grid shell + modular pages). (+21 more)

### Community 22 - "snapshots.py"
Cohesion: 0.10
Nodes (31): Dodgeville Police Department Scheduler — Core Business Logic (package)., _notify_schedule_published(), build_schedule_matrix(), _load_override_maps_for_range(), _officer_day_status(), Return bumped/covering/swapped maps and per-day bumped schedule statuses., _schedule_status_for_override_reason(), distribute_shift_bands() (+23 more)

### Community 23 - "dashboard.py"
Cohesion: 0.09
Nodes (36): get_dashboard_insights(), get_equitable_ot_ledger(), get_hours_watch(), get_labor_budget_status(), get_labor_cost_forecast(), get_overtime_alerts(), get_payroll_ytd(), Fairness ledger: OT/comp hours by officer vs squad average for the pay period. (+28 more)

### Community 24 - "simulator.py"
Cohesion: 0.11
Nodes (28): optimize_staffing_scenarios(), Sweep simulator configs and rank by coverage quality.      Optimizes for: fewest, get_simulator_defaults_from_roster(), Schedule simulation and coverage-plan preview helpers.  Extracted from ``logic, Find best rotation/officer-count/min-staffing combination via scenario sweep., run_schedule_simulation(), run_staffing_optimizer(), _assign_officers() (+20 more)

### Community 25 - "lib.rs"
Cohesion: 0.19
Nodes (35): PyAny, PyList, PyModule, batch_day_status(), build_schedule_matrix(), compute_coverage_counts(), consecutive_work_days(), covering_shifts_from_py() (+27 more)

### Community 26 - "run_ui_aesthetics_review"
Cohesion: 0.12
Nodes (29): build_rows(), _exists(), FeatureRow, _gui_mentions(), _logic_has(), Law-enforcement scheduling feature benchmark — free local checklist.  Compares C, run_le_benchmark(), _check_aesthetics_source() (+21 more)

### Community 27 - "validators.py"
Cohesion: 0.19
Nodes (29): validate_staffing_settings(), Centralized validation for Dodgeville PD Scheduler. All request/schedule checks, FLSA public-sector compensatory time accrual cap (default 480h)., Department fatigue rule — max consecutive scheduled work days., _time_to_minutes(), validate_annual_hours_target(), validate_app_user_role(), validate_availability_entry() (+21 more)

### Community 28 - "test_validators.py"
Cohesion: 0.10
Nodes (16): create_day_off_request(), create_app_user(), TestValidators, is_night_shift(), is_officer_active(), _night_shift_starts(), normalize_optional_text(), validate_cycle_date() (+8 more)

### Community 29 - "scheduling.py"
Cohesion: 0.14
Nodes (32): is_high_risk_night(), _bump_capacity_exhausted(), compute_minimum_rest_gap(), count_officers_on_shift_on_date(), describe_minimum_rest_violation(), get_cycle_day(), _get_monthly_rotation_base_only(), get_monthly_rotation_summary() (+24 more)

### Community 30 - "rust_bridge.py"
Cohesion: 0.12
Nodes (29): available(), backend_name(), batch_day_status(), build_schedule_matrix(), compute_coverage_counts(), consecutive_work_days(), get_cycle_day(), get_squad_on_duty() (+21 more)

### Community 31 - "app.py"
Cohesion: 0.08
Nodes (25): _ensure_static_css(), page_access(), page_availability(), page_callbacks(), page_home(), page_notifications(), page_open_shifts(), page_operations() (+17 more)

### Community 32 - "helpers.py"
Cohesion: 0.07
Nodes (11): date, Shared test fixtures for Dodgeville PD Scheduler., Stable calendar anchor — use in test assertions instead of date.today()., reference_today(), Tests for analytics, holidays, availability, and exports., Auth and user account tests., BatchCoverageTests, HelperTests (+3 more)

### Community 33 - "route_task"
Cohesion: 0.11
Nodes (23): _complexity(), _cost_tier(), _cursor_mode(), _do_not(), format_recommendation(), _match_domain(), _model_tier(), _oss_hints() (+15 more)

### Community 34 - "font"
Cohesion: 0.13
Nodes (7): CTkFont, CTkLabel, get_unread_notification_count(), DashboardPage, font(), ActionTile, AlertBanner

### Community 35 - "log_audit_action"
Cohesion: 0.12
Nodes (25): ldap_auth_enabled(), _ldap_settings(), Optional LDAP / Active Directory authentication scaffold.  Enable with environme, Attempt LDAP bind for the user. Returns success dict with ldap_username on pass., try_ldap_authenticate(), get_simulator_scenario(), list_simulator_scenarios(), load_simulator_scenario_for_bid() (+17 more)

### Community 36 - "ui_exhaustive_test.py"
Cohesion: 0.14
Nodes (26): _close_toplevels(), _confirm_yesno(), _destroy_app(), _entries_in(), _invoke_button(), _login_admin(), _login_role(), _open_dialog_without_wait() (+18 more)

### Community 37 - "aggrid_from_dicts"
Cohesion: 0.12
Nodes (25): aggrid, page_roster(), Patrol roster management., render_roster(), Base vs live row diffs (enterprise schedule compare)., _render_schedule_diff_panel(), aggrid_from_dicts(), _clean_rows() (+17 more)

### Community 38 - "widgets.py"
Cohesion: 0.10
Nodes (11): CTkImage, render_icon(), CoverageBadge, ExpandableSection, _hover_accent(), MetricRow, NavButton, UI component library — single design system for the rebuilt app. (+3 more)

### Community 39 - "suggest_bump_chain_py"
Cohesion: 0.23
Nodes (26): assignment_exhausted(), can_cover_shift(), dict_result(), find_replacement(), is_night_shift(), night_minimum_uncovered(), normalize_shift_band(), officer_full_to_status() (+18 more)

### Community 40 - "display.py"
Cohesion: 0.14
Nodes (26): apply_login_window_layout(), center_window(), center_window_win32(), configure_ctk_scaling(), _env_ui_scale(), _geometry_scale(), _monitor_work_area(), Display scaling and window placement (DPI, centering, login vs main layout). (+18 more)

### Community 41 - "clock.py"
Cohesion: 0.16
Nodes (23): department_tz(), format_clock(), format_local_date(), format_local_datetime(), now_local(), datetime, Department-local real time for Chronos Command UI.  User-facing dates: M/D/YY (e, M/D/YY HH:MM in department local time — e.g. 7/9/26 14:30. (+15 more)

### Community 42 - "session.py"
Cohesion: 0.13
Nodes (13): can(), current_user(), display_name(), initials(), is_officer(), linked_officer_id(), Any, Browser/session state for multi-user web + desktop clients. (+5 more)

### Community 43 - "banked_time.py"
Cohesion: 0.20
Nodes (20): _collect_payroll_bank_events(), _collect_timecard_bank_events(), _date_clause(), _deltas_from_payroll_row(), get_bank_transactions(), get_banked_time_summary(), get_timecard_entries_for_scope(), _merge_bank_events() (+12 more)

### Community 44 - "photos.py"
Cohesion: 0.12
Nodes (20): _bootstrap_runtime(), Entry point for Dodgeville PD Scheduler — Duty Console (web + desktop)., Frozen .exe: cwd + crash log next to the executable., app_dir(), is_frozen(), Application paths — works in development and PyInstaller bundles., Resolve bundled assets (logo, team photo) in dev and frozen builds., resource_path() (+12 more)

### Community 45 - "RotationSchedule"
Cohesion: 0.18
Nodes (22): consecutive_work_days_ending(), consecutive_work_message(), exceeds_consecutive_work_limit(), is_working_status(), Officer, String, RotationSchedule, is_command_staff_title() (+14 more)

### Community 46 - "ui_test_helpers.py"
Cohesion: 0.14
Nodes (24): main(), Run one UI smoke role in an isolated process (fresh Tk root)., assert_brand_assets(), assert_login_handlers_cleared(), assert_nav_contains(), assert_nav_excludes(), create_headless_app(), destroy_app() (+16 more)

### Community 47 - "media.py"
Cohesion: 0.14
Nodes (21): page_login(), page_media(), brand_dir(), data_uri(), logo_display(), _mime(), photo_display(), Path (+13 more)

### Community 48 - "layout"
Cohesion: 0.15
Nodes (18): Access control — logins and roles (enterprise user admin)., render_access(), Availability / blackout + holidays — LE self-service + admin calendar., render_availability(), Ops reports + holidays., render_operations(), apply_theme(), _install_command_palette() (+10 more)

### Community 49 - "batch_process.py"
Cohesion: 0.20
Nodes (16): _classify_item(), _err(), _extract_item(), load_payload(), _ok(), process_batch(), Any, Batch independent items — output JSON array aligned by input index. (+8 more)

### Community 50 - "schedules.py"
Cohesion: 0.12
Nodes (22): page_live(), page_monthly(), page_my_schedule(), date, today_local(), matrix_html(), Scheduling pages — My Schedule, Monthly, Live (SOC heat board)., Personal / unit timeline (My Schedule). (+14 more)

### Community 53 - "helpers.py"
Cohesion: 0.11
Nodes (20): CTkToplevel, ask_save_csv(), cancel_pending_after(), export_date_status_filters(), handle_export_result(), handle_logic_result(), label_has_image(), logic_message() (+12 more)

### Community 54 - "assets.py"
Cohesion: 0.19
Nodes (21): Image, main(), _apply_rounded_border(), _cover_crop(), _fit_contain(), load_brand_image(), load_logo(), load_logo_safe() (+13 more)

### Community 55 - "DodgevilleSchedulerApp"
Cohesion: 0.15
Nodes (3): DodgevilleSchedulerApp, Single app object: session + pure-grid shell + page controllers., SubNavBar

### Community 56 - "run_token_audit"
Cohesion: 0.18
Nodes (19): cmd_token_minimize(), Check, _cursorignore_blocks_large_dump(), _exists(), _opencode_minimal(), Verify token-minimization artifacts and settings — no LLM required., _read(), run_token_audit() (+11 more)

### Community 57 - "get_active_rotation_cycle_length"
Cohesion: 0.20
Nodes (19): get_active_rotation_base_date(), get_active_rotation_cycle_length(), get_active_rotation_preset_name(), get_active_squad_a_days(), get_rotation_config(), get_rust_rotation_schedule(), _get_setting(), get_squad_on_duty() (+11 more)

### Community 58 - "startup_gates.py"
Cohesion: 0.16
Nodes (19): install(), install_git_refresh_hooks(), Install local token-minimization hooks (git + verify Cursor hooks)., verify_cursor_hooks(), _write_executable(), install(), _install_simple_hook(), Install git pre-commit hooks — full framework when available, simple fallback ot (+11 more)

### Community 59 - "normalize_officer_job_title"
Cohesion: 0.18
Nodes (19): add_officer(), add_officer_title_cmd(), delete_officer_cmd(), dispatch_officers(), import_officers_cmd(), list_officers(), Officer roster CLI commands., update_officer_cmd() (+11 more)

### Community 60 - "refactor_check.py"
Cohesion: 0.18
Nodes (19): cmd_audit(), audit_logic_imports(), _collect_from_ast(), _collect_from_regex(), collect_imported_symbols(), _iter_py_files(), _logic_exports(), Verify all `logic` imports resolve against logic.py exports. (+11 more)

### Community 61 - "context_window.py"
Cohesion: 0.31
Nodes (20): add_decision(), advance_turn(), apply_summary(), build_summary(), load_state(), mark_keep(), mark_referenced(), maybe_summarize() (+12 more)

### Community 62 - "parse_date"
Cohesion: 0.13
Nodes (18): list_backup_files(), Return backup .db paths under backups/, newest first., get_backup_status(), Latest backup age for dashboard reminders and admin UI., bulk_approve_auto_ok_requests(), bulk_reject_pending_requests(), process_day_off_request(), Approve pending requests where bump chain resolves automatically. (+10 more)

### Community 63 - "leave.py"
Cohesion: 0.17
Nodes (18): _active_officers(), _approve(), _handle_swap(), Time off + shift exchange., _reject(), _request_queue(), _requests_panel(), _show_plans() (+10 more)

### Community 65 - "certs.py"
Cohesion: 0.22
Nodes (17): page_certs(), Certifications — LE/fire quals gate (PowerTime / Snap pattern)., render_certs(), assign_officer_certification(), _cert_is_valid(), get_officer_certifications(), get_shift_cert_requirements(), list_certification_types() (+9 more)

### Community 66 - "outline_file"
Cohesion: 0.15
Nodes (11): outline_file(), AST outline of a Python file — minimal tokens vs full read., _resolve(), run_outline(), _definitions_in_file(), _iter_py_files(), lookup_symbol(), Find where a symbol is defined — avoid full-repo reads. (+3 more)

### Community 67 - "run_slice_check"
Cohesion: 0.15
Nodes (12): _step_slice_check(), _find_slice(), _logic_has(), _page_keys(), Vertical slice map and integrity checks., Run verify commands registered for a single vertical slice., run_slice_check(), run_slice_map() (+4 more)

### Community 68 - "test_position_pay.py"
Cohesion: 0.12
Nodes (4): PositionPayTests, RosterTitleTests, is_yearly_salary_title(), monthly_pay_to_hourly()

### Community 69 - "validators_config.py"
Cohesion: 0.15
Nodes (16): is_officer_unavailable_on_date(), parse_squad_a_days_text(), Parse comma/space-separated or JSON list of cycle days (1..cycle_length)., can_officer_work_day_band(), parse_bids_due_datetime(), date, datetime, Department settings, bidding eligibility, and certification validators. (+8 more)

### Community 70 - "get_current_cycle_window"
Cohesion: 0.13
Nodes (9): export_ical_cmd(), export_schedule(), rotation_settings_cmd(), export_officer_schedule_ical(), Validate and persist rotation settings; returns active config snapshot., save_rotation_settings(), get_current_cycle_window(), Return start/end dates for the active rotation cycle containing reference (defau (+1 more)

### Community 71 - "VerifyUnifiedTests"
Cohesion: 0.18
Nodes (5): is_subset(), True when every child step appears in parent tier in the same relative order., tier_steps(), Unified verification — tiers must be strict supersets, no duplicate/conflicting, VerifyUnifiedTests

### Community 72 - "rotation.rs"
Cohesion: 0.16
Nodes (13): dodgeville_squad_days(), is_high_risk_night_ordinal(), is_high_risk_night_weekday(), ordinal_to_weekday(), RotationMode, HashSet, PyDict, String (+5 more)

### Community 73 - "agent_gates.py"
Cohesion: 0.22
Nodes (15): agent_context_hint(), auto_after_route_task(), auto_before_dev_command(), auto_before_session(), detect_slice_id(), _git_changed_files(), Automatic agent token-minimization gates.  Refreshes logs/agent_pack/latest.md a, One-line hint for agents (paste into logs or print). (+7 more)

### Community 74 - "run_usage_brief"
Cohesion: 0.20
Nodes (10): register_tool_from_read(), estimate_tokens(), file_stats(), format_stats_row(), Rough token estimates for files and text (chars / 4 heuristic)., _head(), Print minimal agent context — slice-scoped files and verify commands., run_usage_brief() (+2 more)

### Community 75 - "registry.py"
Cohesion: 0.17
Nodes (13): Print UI ↔ logic ↔ CLI feature coverage map.  UI ✓ requires at least one existin, True only when every listed ui_file exists, and at least one is listed., run_feature_map(), _ui_files_exist(), Vertical slice registry — feature-oriented project map., features_for_map(), get_slice(), Any (+5 more)

### Community 76 - "check_read"
Cohesion: 0.21
Nodes (8): check_read(), known_large_ui_files(), _norm(), Shared read-guard rules for Cursor hooks and token tooling., Large indexable product modules — prefer outline/symbol (ui/, gui/, logic/)., ReadGuardResult, Tests for read_guard., ReadGuardTests

### Community 77 - "run_agent_kit"
Cohesion: 0.20
Nodes (12): cmd_session_start(), _head(), One free command: minimal agent bootstrap for any session (token-first)., _run(), run_agent_kit(), _check(), Environment and project health checks for Dodgeville PD Scheduler., run_doctor() (+4 more)

### Community 78 - "dump_json"
Cohesion: 0.21
Nodes (10): run_agent_route(), dump_json(), _pick(), Any, Structured JSON output — fixed fields only, no prose., One index-aligned batch element with schema fields only., shape_batch_row(), shape_route() (+2 more)

### Community 79 - "structure_lint.py"
Cohesion: 0.21
Nodes (14): check_analytics_shim(), check_cli_thin(), check_mixin_inheritance(), check_monolith_sizes(), check_ui_import_logic_package(), check_ui_no_sql(), _py_files(), Path (+6 more)

### Community 80 - "ui_domain.py"
Cohesion: 0.35
Nodes (14): cmd_brainstorm(), cmd_chronos_map(), cmd_explore(), cmd_learn(), cmd_research_queries(), cmd_show(), cmd_suggest(), load_ideas() (+6 more)

### Community 81 - "run_ui_visual_diff"
Cohesion: 0.25
Nodes (10): _compare_images(), _filter_quick(), _is_quick_shot(), _latest_live_dir(), _list_pngs(), Compare ui-live screenshots against baselines (Pillow — already a project depend, Nav + login screenshots only (01–15): fast layout smoke., run_ui_visual_diff() (+2 more)

### Community 82 - "ui_workflow_probe.py"
Cohesion: 0.30
Nodes (14): _check_day_off_approval_chain(), _check_demo_password_policy(), _check_headless_ui_shell(), _check_password_change_login_path(), _check_pay_period_lock(), _check_rust_backend(), _check_window_layout_guard(), _fail() (+6 more)

### Community 84 - "extra_duty.py"
Cohesion: 0.19
Nodes (13): list_open_shifts(), _board(), get_coverage_gap_board(), create_extra_duty_event(), _decode_notes(), _encode_notes(), export_extra_duty_invoice_csv(), list_extra_duty_events() (+5 more)

### Community 85 - "icons.py"
Cohesion: 0.26
Nodes (12): ImageDraw, clear_icon_cache(), _icon_calendar(), _icon_dashboard(), _icon_leave(), _icon_officers(), _icon_operations(), _icon_payroll() (+4 more)

### Community 86 - "get_position_pay_rates"
Cohesion: 0.24
Nodes (14): get_position_pay_rates(), Persist position compensation (amount, basis, salary flag per title)., Return compensation config keyed by roster title., save_position_pay_rates(), monthly_pay_to_per_pay_period(), Monthly salary × 12, dispersed evenly across pay periods in the year., Hourly base rate from title compensation config (monthly × 12 ÷ 2008)., suggested_hourly_rate_for_title() (+6 more)

### Community 87 - "simulate_schedule_py"
Cohesion: 0.20
Nodes (13): format_minutes(), is_night_shift_start(), parse_minutes(), Bound, HashSet, PyDict, PyObject, PyResult (+5 more)

### Community 88 - "run_lint"
Cohesion: 0.18
Nodes (7): Dependency vulnerability scan via pip-audit (PyPI advisory DB)., run_deps_audit(), Ruff lint and format gate — free OSS alternative to agent code review., _ruff_cmd(), run_lint(), OssToolsTests, Tests for OSS dev tooling wrappers.

### Community 89 - "roster_titles.py"
Cohesion: 0.28
Nodes (12): list_officer_titles_cmd(), add_custom_officer_title(), _canonical_title(), get_builtin_officer_titles(), get_custom_officer_titles(), get_officer_title_options(), get_titles_in_use_on_roster(), is_assignable_officer_title() (+4 more)

### Community 90 - "source_eval.py"
Cohesion: 0.24
Nodes (12): cmd_source_eval(), Evaluate all catalogued FR programs vs Chronos → implement queue., cmd_implement(), cmd_show(), evaluate_products(), _load_kb(), _probe_chronos(), Any (+4 more)

### Community 91 - "opencode.json"
Cohesion: 0.15
Nodes (12): compaction, auto, prune, reserved, instructions, permission, bash, edit (+4 more)

### Community 93 - "minimum_rest_gap_hours_with_times"
Cohesion: 0.52
Nodes (11): effective_band_start(), meets_minimum_rest(), minimum_rest_gap_hours(), minimum_rest_gap_hours_with_times(), minimum_rest_message(), parse_minutes(), CoveringShiftStarts, Officer (+3 more)

### Community 94 - "test_database_backup.py"
Cohesion: 0.21
Nodes (5): DatabaseBackupTests, file_test_database(), Database backup slice — manual, auto, restore, and status., Isolated on-disk DB for restore tests (in-memory URIs cannot be restored)., _sqlite_backup()

### Community 95 - "test_ui_readiness.py"
Cohesion: 0.18
Nodes (6): Regression tests for supervisor-ready UI gates (catch false-positive smoke)., Login must paint brand images and complete headless shell login., ui-smoke must finish (no hang) and return 0 — catches login handler storms., TestUiReadiness, Capitalize the first letter of each word for headers, tabs, and labels., title_case_ui()

### Community 96 - "build_agent_pack"
Cohesion: 0.31
Nodes (10): build_agent_pack(), _git_touch_status(), _head(), _last_gate(), Build a minimal pasteable agent context pack — one file instead of repo dump., run_agent_pack(), _slice_touch(), format_recommendation_compact() (+2 more)

### Community 97 - "run_ui_exhaustive"
Cohesion: 0.25
Nodes (10): _acquire_exhaustive_lock(), _lock_holder_alive(), Prevent concurrent exhaustive runs (they deadlock headless Tk login)., _release_exhaustive_lock(), run_ui_exhaustive(), main(), _pid_alive(), Live on-screen UI test — visible window, auto-login, screenshots per step.  Uses (+2 more)

### Community 98 - "compute_shift_coverage_counts"
Cohesion: 0.27
Nodes (9): compute_shift_coverage_counts(), normalize_shift_band(), parse_minutes(), HashMap, Officer, Option, PyResult, String (+1 more)

### Community 99 - "split_finance_payroll.py"
Cohesion: 0.38
Nodes (9): _func_ranges(), _lines(), main(), Path, One-shot architecture split: finance UI + logic/payroll packages.  Preserves pub, 1-indexed inclusive line slice., _slice(), split_finance() (+1 more)

### Community 101 - "applies_night_minimum"
Cohesion: 0.25
Nodes (9): get_coverage_gap_board(), get_coverage_report(), Near-term staffing gaps for the on-duty squad (today through hours_ahead)., _shift_starts(), applies_night_minimum(), _mdy_short(), date, Night staffing rules apply only to night shifts on Fri/Sat. (+1 more)

### Community 102 - "rust_fallback.py"
Cohesion: 0.28
Nodes (8): date, python_batch_day_status(), python_build_schedule_matrix(), python_compute_coverage_counts(), Emergency Python implementations for scheduling math.  Used only when scheduler_, Build roster matrix without Rust., Resolve statuses without Rust — mirrors scheduler_core batch_day_status., Shift headcount batch without Rust.

### Community 103 - "export_project_code.py"
Cohesion: 0.47
Nodes (8): collect_files(), encode_binary(), main(), Path, Concatenate project source into a single text file for offline reference., read_as_text(), should_include(), write_file_section()

### Community 105 - "build_frozen_eval.py"
Cohesion: 0.48
Nodes (6): _copy_snapshot(), main(), Path, _run(), _write_frozen_marker(), _write_readme()

### Community 106 - "extract_logic_modules.py"
Cohesion: 0.57
Nodes (6): _extract_module(), _function_ranges(), _inject_core_reexports(), _inject_lazy_imports(), _inject_officers_lazy(), main()

### Community 107 - "extract_ui_mixins.py"
Cohesion: 0.57
Nodes (6): _build_imports(), _collect_extra_methods(), _extract_chunk(), _find_line(), main(), _parse_app_imports()

### Community 108 - "split_ui_monoliths.py"
Cohesion: 0.48
Nodes (6): main(), Path, Split ui/feature_pages.py and ui/schedule_pages.py into slice modules., split_feature_pages(), split_schedule_pages(), _write()

### Community 110 - ".scroll_body"
Cohesion: 0.27
Nodes (4): CTkFrame, CTkScrollableFrame, Full-page scroll host — use for stacked cards/lists., Two-column layout filling the page (form | list).

### Community 111 - "image"
Cohesion: 0.33
Nodes (6): attachment, image, auto_resize, max_base64_bytes, max_height, max_width

### Community 112 - "rebuild_ui_mixins.py"
Cohesion: 0.60
Nodes (5): _body_only(), main(), _read(), _slice_by_marker(), _write_mixin()

### Community 113 - "run_ui_observe"
Cohesion: 0.53
Nodes (5): _latest_dir(), _list_pngs(), Unified UI observation — capture runtime + static review for agent vision workfl, _read_review_summary(), run_ui_observe()

### Community 116 - "command"
Cohesion: 0.40
Nodes (5): description, subtask, template, command, cheap-check

### Community 117 - "run_build_rust"
Cohesion: 0.60
Nodes (4): _has_virtualenv(), Build the scheduler_core Rust extension via maturin., run_build_rust(), _verify_import()

### Community 118 - "run_chronos_e2e"
Cohesion: 0.60
Nodes (4): main(), playwright_available(), Optional Chronos NiceGUI E2E smoke via Playwright (local machine, cheap).  Insta, run_chronos_e2e()

### Community 119 - "run_read_budget"
Cohesion: 0.60
Nodes (4): estimate_path(), main(), Estimate tokens before reading files — free gate to avoid whole-file waste., run_read_budget()

### Community 120 - "authenticate_role"
Cohesion: 0.50
Nodes (3): _login_admin(), Exercise UI handlers against an isolated test database (headless CTk)., authenticate_role()

### Community 121 - "run_ui_handler_coverage"
Cohesion: 0.60
Nodes (4): _collect_test_steps(), _collect_ui_commands(), Report UI handler coverage — maps command= handlers in ui/ to exhaustive test st, run_ui_handler_coverage()

### Community 122 - "ui_mixin_import_check.py"
Cohesion: 0.70
Nodes (4): check_file(), _collect_defs_and_imports(), main(), AST

### Community 123 - "agent-pack"
Cohesion: 0.50
Nodes (4): description, subtask, template, agent-pack

### Community 124 - "check"
Cohesion: 0.50
Nodes (4): description, subtask, template, check

### Community 125 - "context-window"
Cohesion: 0.50
Nodes (4): context-window, description, subtask, template

### Community 126 - "fix-hint"
Cohesion: 0.50
Nodes (4): fix-hint, description, subtask, template

### Community 127 - "lint"
Cohesion: 0.50
Nodes (4): lint, description, subtask, template

### Community 128 - "route-task"
Cohesion: 0.50
Nodes (4): route-task, description, subtask, template

### Community 129 - "token-audit"
Cohesion: 0.50
Nodes (4): token-audit, description, subtask, template

### Community 130 - "ui-observe"
Cohesion: 0.50
Nodes (4): ui-observe, description, subtask, template

### Community 131 - "usage-brief"
Cohesion: 0.50
Nodes (4): usage-brief, description, subtask, template

### Community 132 - "detect_truncated_functions.py"
Cohesion: 0.67
Nodes (3): detect_truncated(), main(), Detect logic.py functions that may be truncated (fall through to next def).

### Community 133 - "extract_logic_core_trim.py"
Cohesion: 0.83
Nodes (3): _extract_functions(), _function_ranges(), main()

### Community 134 - "extract_logic_requests.py"
Cohesion: 0.83
Nodes (3): _function_ranges(), _inject_lazy_imports(), main()

### Community 139 - "_mdy_datetime"
Cohesion: 0.67
Nodes (3): _mdy_datetime(), datetime, UI datetime: M/D/YY HH:MM — e.g. 7/9/26 14:30.

### Community 154 - "period.py"
Cohesion: 0.12
Nodes (32): Move reference date backward/forward within a scope., shift_scope_reference(), annual_salary_to_per_pay_period(), count_pay_periods_in_year(), format_pay_period_label(), get_adjacent_cycle_window(), get_adjacent_pay_period(), get_pay_period() (+24 more)

## Knowledge Gaps
- **45 isolated node(s):** `Officer`, `$schema`, `instructions`, `small_model`, `auto` (+40 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `test_database()` connect `test_database` to `working_date_for_squad`, `database.py`, `coverage_optimizer.py`, `math_scenarios.py`, `get_any_officer`, `staffing_config.py`, `snapshots.py`, `simulator.py`, `test_validators.py`, `helpers.py`, `ui_exhaustive_test.py`, `TimecardScheduleTests`, `TestRotationLogic`, `test_position_pay.py`, `get_current_cycle_window`, `ui_workflow_probe.py`, `Tier2FeatureTests`, `LaborComplianceTests`, `test_database_backup.py`?**
  _High betweenness centrality (0.112) - this node is a cross-community bridge._
- **Why does `get_connection()` connect `get_connection` to `cli.py`, `working_date_for_squad`, `test_database`, `timecard.py`, `database.py`, `bidding.py`, `format_date`, `coverage_optimizer.py`, `entries.py`, `get_any_officer`, `labor_compliance.py`, `get_officer_by_id`, `snapshots.py`, `dashboard.py`, `period.py`, `validators.py`, `test_validators.py`, `scheduling.py`, `helpers.py`, `font`, `log_audit_action`, `banked_time.py`, `TimecardScheduleTests`, `get_active_rotation_cycle_length`, `normalize_officer_job_title`, `parse_date`, `certs.py`, `validators_config.py`, `ui_workflow_probe.py`, `extra_duty.py`, `roster_titles.py`, `LaborComplianceTests`?**
  _High betweenness centrality (0.098) - this node is a cross-community bridge._
- **Why does `format_date()` connect `format_date` to `dev.py`, `cli.py`, `timecard.py`, `Card`, `bidding.py`, `get_connection`, `config.py`, `PrimaryButton`, `entries.py`, `labor_compliance.py`, `get_officer_by_id`, `app.py`, `snapshots.py`, `dashboard.py`, `simulator.py`, `period.py`, `validators.py`, `test_validators.py`, `rust_bridge.py`, `app.py`, `font`, `clock.py`, `banked_time.py`, `layout`, `schedules.py`, `TimecardScheduleTests`, `helpers.py`, `get_active_rotation_cycle_length`, `normalize_officer_job_title`, `parse_date`, `leave.py`, `certs.py`, `validators_config.py`, `get_current_cycle_window`, `extra_duty.py`, `applies_night_minimum`?**
  _High betweenness centrality (0.093) - this node is a cross-community bridge._
- **What connects `Backward-compat shim — implementation lives in logic/analytics.py.`, `Regression audit for known scheduling bugs. Run: python dev.py audit`, `Password hashing utilities — PBKDF2 with legacy plaintext fallback.` to the rest of the system?**
  _576 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `dev.py` be split into smaller, more focused modules?**
  _Cohesion score 0.04887218045112782 - nodes in this community are weakly interconnected._
- **Should `cli.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05052631578947368 - nodes in this community are weakly interconnected._
- **Should `fr_domain.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05754385964912281 - nodes in this community are weakly interconnected._
