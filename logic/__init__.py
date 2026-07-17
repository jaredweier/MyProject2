"""
Dodgeville Police Department Scheduler — Core Business Logic (package).
"""

from logic.analytics import *
from logic.banked_time import *
from logic.bidding import *
from logic.bump_off_duty import (
    ALL_CRITERIA as ALL_CRITERIA,
)
from logic.bump_off_duty import (
    CRITERION_LABELS as CRITERION_LABELS,
)
from logic.bump_off_duty import (
    advance_call_list_cursor as advance_call_list_cursor,
)
from logic.bump_off_duty import (
    extract_text_from_upload as extract_text_from_upload,
)
from logic.bump_off_duty import (
    get_bump_call_list as get_bump_call_list,
)
from logic.bump_off_duty import (
    get_next_call_list_officer as get_next_call_list_officer,
)
from logic.bump_off_duty import (
    get_off_duty_bump_settings_for_ui as get_off_duty_bump_settings_for_ui,
)
from logic.bump_off_duty import (
    import_bump_call_list_file as import_bump_call_list_file,
)
from logic.bump_off_duty import (
    import_bump_call_list_text as import_bump_call_list_text,
)
from logic.bump_off_duty import (
    load_off_duty_bump_policy as load_off_duty_bump_policy,
)
from logic.bump_off_duty import (
    reset_call_list_cursor as reset_call_list_cursor,
)
from logic.bump_off_duty import (
    save_bump_call_list as save_bump_call_list,
)
from logic.bump_off_duty import (
    save_off_duty_bump_policy as save_off_duty_bump_policy,
)
from logic.cad_rms_bridge import (
    cad_bidirectional_roundtrip_smoke as cad_bidirectional_roundtrip_smoke,
)
from logic.cad_rms_bridge import (
    cad_bridge_status as cad_bridge_status,
)
from logic.cad_rms_bridge import (
    import_cad_duty_bidirectional as import_cad_duty_bidirectional,
)
from logic.cad_rms_bridge import (
    pull_cad_from_url as pull_cad_from_url,
)
from logic.cad_rms_bridge import (
    receive_cad_inbound as receive_cad_inbound,
)
from logic.cad_rms_export import (
    export_duty_roster_for_cad as export_duty_roster_for_cad,
)
from logic.cad_rms_export import (
    post_cad_webhook as post_cad_webhook,
)
from logic.callbacks import *
from logic.callout_desk import (
    build_callout_ladder as build_callout_ladder,
)
from logic.callout_desk import (
    execute_callout_order as execute_callout_order,
)
from logic.callout_desk import (
    get_ot_equity_sort_enabled as get_ot_equity_sort_enabled,
)
from logic.callout_desk import (
    list_today_vacancies as list_today_vacancies,
)
from logic.callout_desk import (
    set_ot_equity_sort_enabled as set_ot_equity_sort_enabled,
)
from logic.certifications import *
from logic.court_calendar import (
    court_calendar_summary as court_calendar_summary,
)
from logic.court_calendar import (
    create_court_or_training as create_court_or_training,
)
from logic.court_calendar import (
    list_court_training_events as list_court_training_events,
)
from logic.coverage_timeline import (
    CoverageWindow as CoverageWindow,
)
from logic.coverage_timeline import (
    evaluate_day_coverage as evaluate_day_coverage,
)
from logic.coverage_timeline import (
    occupancy_at as occupancy_at,
)
from logic.coverage_windows_store import (
    add_coverage_window as add_coverage_window,
)
from logic.coverage_windows_store import (
    delete_coverage_window as delete_coverage_window,
)
from logic.coverage_windows_store import (
    get_active_coverage_windows as get_active_coverage_windows,
)
from logic.coverage_windows_store import (
    get_coverage_247_minimum as get_coverage_247_minimum,
)
from logic.coverage_windows_store import (
    list_coverage_windows as list_coverage_windows,
)
from logic.coverage_windows_store import (
    save_coverage_windows as save_coverage_windows,
)
from logic.coverage_windows_store import (
    set_coverage_247_minimum as set_coverage_247_minimum,
)
from logic.dashboard import *
from logic.dual_workforce import (
    compute_officer_ot_split as compute_officer_ot_split,
)
from logic.dual_workforce import (
    export_dual_ot_ledger_csv as export_dual_ot_ledger_csv,
)
from logic.dual_workforce import (
    flsa_profile_for_officer as flsa_profile_for_officer,
)
from logic.dual_workforce import (
    get_dual_workforce_settings as get_dual_workforce_settings,
)
from logic.dual_workforce import (
    run_dual_period_ot_ledger as run_dual_period_ot_ledger,
)
from logic.dual_workforce import (
    save_dual_workforce_settings as save_dual_workforce_settings,
)
from logic.exports import *
from logic.extra_duty import *
from logic.fatigue_gates import (
    check_rest_hard_stop as check_rest_hard_stop,
)
from logic.fatigue_gates import (
    fatigue_watchlist as fatigue_watchlist,
)
from logic.fatigue_gates import (
    rest_fatigue_hard_stops_enabled as rest_fatigue_hard_stops_enabled,
)
from logic.geofence_clock import (
    apply_geofence_punches_to_timecard as apply_geofence_punches_to_timecard,
)
from logic.geofence_clock import (
    clock_status as clock_status,
)
from logic.geofence_clock import (
    get_geofence_config as get_geofence_config,
)
from logic.geofence_clock import (
    list_geofence_punches as list_geofence_punches,
)
from logic.geofence_clock import (
    record_geofence_punch as record_geofence_punch,
)
from logic.geofence_clock import (
    save_geofence_config as save_geofence_config,
)
from logic.hosting import (
    deployment_checklist as deployment_checklist,
)
from logic.hosting import (
    get_hosting_config as get_hosting_config,
)
from logic.labor_compliance import *
from logic.ldap_auth import (
    ldap_field_trial_checklist as ldap_field_trial_checklist,
)
from logic.ldap_auth import (
    ldap_health_check as ldap_health_check,
)
from logic.ldap_auth import (
    save_ldap_field_trial_settings as save_ldap_field_trial_settings,
)
from logic.leave_accruals import (
    deduct_leave_accrual as deduct_leave_accrual,
)
from logic.leave_accruals import (
    get_accrual_deduct_on_approve as get_accrual_deduct_on_approve,
)
from logic.leave_accruals import (
    get_officer_accrual_balances as get_officer_accrual_balances,
)
from logic.leave_accruals import (
    list_roster_accrual_balances as list_roster_accrual_balances,
)
from logic.leave_accruals import (
    set_accrual_deduct_on_approve as set_accrual_deduct_on_approve,
)
from logic.leave_donation import *
from logic.notify_channels import (
    dispatch_channel_hooks as dispatch_channel_hooks,
)
from logic.notify_channels import (
    dispatch_template as dispatch_template,
)
from logic.notify_channels import (
    get_notify_channel_config as get_notify_channel_config,
)
from logic.notify_channels import (
    test_notify_channels as test_notify_channels,
)
from logic.notify_queue import (
    list_notify_outbox as list_notify_outbox,
)
from logic.notify_queue import (
    notify_outbox_stats as notify_outbox_stats,
)
from logic.notify_queue import (
    process_notify_outbox as process_notify_outbox,
)
from logic.notify_queue import (
    prove_notify_paths as prove_notify_paths,
)
from logic.notify_queue import (
    save_notify_settings as save_notify_settings,
)
from logic.officers import *
from logic.offline_api import (
    build_offline_snapshot as build_offline_snapshot,
)
from logic.operations import *
from logic.ops_desk import (
    diagnose_manual_review as diagnose_manual_review,
)
from logic.ops_desk import (
    get_ops_desk_board as get_ops_desk_board,
)
from logic.ops_desk import (
    list_manual_review_queue as list_manual_review_queue,
)
from logic.ops_desk import (
    resolve_manual_review as resolve_manual_review,
)
from logic.optimized_schedule_apply import (
    apply_schedule_builder_defaults_to_department as apply_schedule_builder_defaults_to_department,
)
from logic.optimized_schedule_apply import (
    format_optimized_plan_view as format_optimized_plan_view,
)
from logic.optimized_schedule_apply import (
    get_last_optimized_plan as get_last_optimized_plan,
)
from logic.optimized_schedule_apply import (
    get_schedule_builder_defaults as get_schedule_builder_defaults,
)
from logic.optimized_schedule_apply import (
    implement_optimized_plan as implement_optimized_plan,
)
from logic.optimized_schedule_apply import (
    preview_implement_plan as preview_implement_plan,
)
from logic.optimized_schedule_apply import (
    recommend_implement_dates as recommend_implement_dates,
)
from logic.optimized_schedule_apply import (
    save_last_optimized_plan as save_last_optimized_plan,
)
from logic.optimized_schedule_apply import (
    set_schedule_builder_defaults as set_schedule_builder_defaults,
)
from logic.ot_equity_ledger import (
    export_ot_equity_dual_csv as export_ot_equity_dual_csv,
)
from logic.ot_equity_ledger import (
    get_ot_equity_summary as get_ot_equity_summary,
)
from logic.ot_equity_ledger import (
    record_ot_offer as record_ot_offer,
)
from logic.ot_equity_ledger import (
    record_ot_worked as record_ot_worked,
)
from logic.ot_fill import (
    FILL_MODE_LABELS as FILL_MODE_LABELS,
)
from logic.ot_fill import (
    FILL_MODES as FILL_MODES,
)
from logic.ot_fill import (
    apply_ot_fill_selection as apply_ot_fill_selection,
)
from logic.ot_fill import (
    get_officer_ot_fill_year_stats as get_officer_ot_fill_year_stats,
)
from logic.ot_fill import (
    get_ot_fill_mode as get_ot_fill_mode,
)
from logic.ot_fill import (
    get_ot_fill_modes_for_ui as get_ot_fill_modes_for_ui,
)
from logic.ot_fill import (
    get_ot_fill_year_leaderboard as get_ot_fill_year_leaderboard,
)
from logic.ot_fill import (
    list_ot_fill_candidates as list_ot_fill_candidates,
)
from logic.ot_fill import (
    move_officer_to_end_of_call_list as move_officer_to_end_of_call_list,
)
from logic.ot_fill import (
    record_ordered_in as record_ordered_in,
)
from logic.ot_fill import (
    record_turned_down as record_turned_down,
)
from logic.ot_fill import (
    set_ot_fill_mode as set_ot_fill_mode,
)
from logic.payroll import *
from logic.payroll_exceptions import (
    export_pay_pack as export_pay_pack,
)
from logic.payroll_exceptions import (
    flsa_period_banners as flsa_period_banners,
)
from logic.payroll_exceptions import (
    list_payroll_exceptions as list_payroll_exceptions,
)
from logic.payroll_exceptions import (
    schedule_to_timecard_defaults as schedule_to_timecard_defaults,
)
from logic.policy_pack import (
    collect_policy_pack as collect_policy_pack,
)
from logic.policy_pack import (
    export_policy_pack as export_policy_pack,
)
from logic.policy_pack import (
    get_last_exported_policy_pack as get_last_exported_policy_pack,
)
from logic.policy_pack import (
    import_policy_pack as import_policy_pack,
)
from logic.product_impl_kit import (
    export_implementation_kit as export_implementation_kit,
)
from logic.product_impl_kit import (
    get_implementation_kit as get_implementation_kit,
)
from logic.publish_gates import (
    get_publish_block_on_manual_review as get_publish_block_on_manual_review,
)
from logic.publish_gates import (
    live_coverage_severity_for_window as live_coverage_severity_for_window,
)
from logic.publish_gates import (
    preflight_publish_base_schedule as preflight_publish_base_schedule,
)
from logic.publish_gates import (
    publish_base_schedule_gated as publish_base_schedule_gated,
)
from logic.publish_gates import (
    set_publish_block_on_manual_review as set_publish_block_on_manual_review,
)
from logic.requests import *
from logic.roster_titles import *
from logic.roster_titles import (
    get_title_callin_limits as get_title_callin_limits,
)
from logic.roster_titles import (
    resolve_officer_callin_limits as resolve_officer_callin_limits,
)
from logic.roster_titles import (
    save_title_callin_limits as save_title_callin_limits,
)
from logic.roster_titles import (
    set_title_callin_limit as set_title_callin_limit,
)
from logic.rotation_config import *
from logic.rotation_patterns import (
    build_pattern as build_pattern,
)
from logic.rotation_patterns import (
    parse_variation_set as parse_variation_set,
)
from logic.rotation_patterns import (
    projected_annual_hours as projected_annual_hours,
)
from logic.rotation_presets_catalog import (
    apply_rotation_preset_metadata as apply_rotation_preset_metadata,
)
from logic.rotation_presets_catalog import (
    list_rotation_presets as list_rotation_presets,
)
from logic.rotation_preview import *
from logic.scheduling import *

# Optimizer APIs live on brain modules — not re-exported here:
#   coverage_optimizer / bump_optimizer / scheduling_sim / staffing_optimizer
from logic.shift_assignment import *
from logic.sim_product_pack import (
    apply_sim_winner_to_draft_month as apply_sim_winner_to_draft_month,
)
from logic.sim_product_pack import (
    fairness_report_full as fairness_report_full,
)
from logic.sim_product_pack import (
    import_live_department_constraints as import_live_department_constraints,
)
from logic.sim_product_pack import (
    plain_english_staffing_explain as plain_english_staffing_explain,
)
from logic.sim_product_pack import (
    sensitivity_headcount as sensitivity_headcount,
)
from logic.sim_product_pack import (
    sensitivity_relax_night_min as sensitivity_relax_night_min,
)
from logic.sim_product_pack import (
    try_cpsat_when_small as try_cpsat_when_small,
)
from logic.simulator_store import *
from logic.snapshots import *
from logic.snapshots import _insert_override_record as _insert_override_record
from logic.staffing_config import *
from logic.stations import (
    assign_unassigned_to_station as assign_unassigned_to_station,
)
from logic.stations import (
    bulk_set_station as bulk_set_station,
)
from logic.stations import (
    ensure_default_hq_station as ensure_default_hq_station,
)
from logic.stations import (
    get_station_min_staffing_matrix as get_station_min_staffing_matrix,
)
from logic.stations import (
    list_station_posts as list_station_posts,
)
from logic.stations import (
    officers_by_station as officers_by_station,
)
from logic.stations import (
    station_staffing_board as station_staffing_board,
)
from logic.stations import (
    upsert_station_post as upsert_station_post,
)
from logic.tenant import (
    create_tenant as create_tenant,
)
from logic.tenant import (
    get_tenant_info as get_tenant_info,
)
from logic.tenant import (
    list_local_tenants as list_local_tenants,
)
from logic.time_punch import (
    approve_punch_edit as approve_punch_edit,
)
from logic.time_punch import (
    get_punch_policy as get_punch_policy,
)
from logic.time_punch import (
    is_punch_required as is_punch_required,
)
from logic.time_punch import (
    list_punch_edit_requests as list_punch_edit_requests,
)
from logic.time_punch import (
    officer_clock as officer_clock,
)
from logic.time_punch import (
    reject_punch_edit as reject_punch_edit,
)
from logic.time_punch import (
    request_punch_edit as request_punch_edit,
)
from logic.time_punch import (
    set_punch_required as set_punch_required,
)
from logic.users import *
