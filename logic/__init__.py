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
from logic.callbacks import *
from logic.certifications import *
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
from logic.exports import *
from logic.extra_duty import *
from logic.labor_compliance import *
from logic.leave_donation import *
from logic.officers import *
from logic.operations import *
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
    recommend_implement_dates as recommend_implement_dates,
)
from logic.optimized_schedule_apply import (
    save_last_optimized_plan as save_last_optimized_plan,
)
from logic.optimized_schedule_apply import (
    set_schedule_builder_defaults as set_schedule_builder_defaults,
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
from logic.rotation_preview import *
from logic.scheduling import *
from logic.shift_assignment import *
from logic.simulator_store import *
from logic.snapshots import *
from logic.snapshots import _insert_override_record as _insert_override_record
from logic.staffing_config import *
from logic.users import *
