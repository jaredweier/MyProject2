"""Tests for P1.2 pool diversity check (master plan §4 stage 4).

Proves the outcome-metric + assignment-overlap dedup actually rejects
near-duplicate candidates that the old (variant,phase,start)-aggregate-only
dedup in staffing_cpsat.py would have kept, and keeps genuinely different
candidates.
"""

import unittest

from logic.staffing_optimizer import (
    _assignment_overlap_frac,
    _is_near_duplicate_candidate,
    _outcome_vector,
)


def _metrics(**kw):
    base = {
        "coverage_247_failures": 0,
        "extra_window_failures": 0,
        "gap_events": 0,
        "flsa_violations": 0,
        "annual_band_outside": 0,
        "avg_annual_hours": 2080,
        "annual_hours_spread": 0,
        "rest_failures": 0,
        "consecutive_work_failures": 0,
    }
    base.update(kw)
    return base


class OutcomeVectorTests(unittest.TestCase):
    def test_identical_metrics_same_vector(self):
        m = _metrics()
        v1 = _outcome_vector(m, annual=2080, annual_variance=40)
        v2 = _outcome_vector(m, annual=2080, annual_variance=40)
        self.assertEqual(v1, v2)

    def test_different_metrics_different_vector(self):
        v1 = _outcome_vector(_metrics(), annual=2080, annual_variance=40)
        v2 = _outcome_vector(_metrics(flsa_violations=3, gap_events=2), annual=2080, annual_variance=40)
        self.assertNotEqual(v1, v2)


class AssignmentOverlapTests(unittest.TestCase):
    def test_identical_rosters_full_overlap(self):
        a = [["0700", "0700", ""], ["1500", "1500", "1500"]]
        b = [["0700", "0700", ""], ["1500", "1500", "1500"]]
        self.assertEqual(_assignment_overlap_frac(a, b), 1.0)

    def test_disjoint_rosters_zero_overlap(self):
        a = [["0700", "0700"], ["1500", "1500"]]
        b = [["1500", "1500"], ["0700", "0700"]]
        self.assertEqual(_assignment_overlap_frac(a, b), 0.0)

    def test_empty_inputs_zero_overlap(self):
        self.assertEqual(_assignment_overlap_frac(None, [["0700"]]), 0.0)
        self.assertEqual(_assignment_overlap_frac([], []), 0.0)


class NearDuplicateTests(unittest.TestCase):
    """The scenario the audit flagged: two candidates that the old
    (variant,phase,start)-profile-count dedup would treat as 'new' (e.g.
    because officer roles/order differ) but which are actually the same
    outcome with >90% overlapping assignments — must be rejected."""

    def test_rejects_true_near_duplicate(self):
        cycle_a = [["0700"] * 5, ["1500"] * 5, ["2300"] * 5, ["0700"] * 5, ["1500"] * 5]
        cycle_b = [["0700"] * 5, ["1500"] * 5, ["2300"] * 5, ["0700"] * 5, ["1500"] * 4 + ["2300"]]
        vec_a = _outcome_vector(_metrics(), annual=2080, annual_variance=40)
        vec_b = _outcome_vector(_metrics(), annual=2080, annual_variance=40)
        self.assertTrue(_is_near_duplicate_candidate(vec_a, vec_b, cycle_a, cycle_b))

    def test_keeps_candidate_with_different_outcome_even_if_same_roster(self):
        cycle = [["0700"] * 5, ["1500"] * 5]
        vec_a = _outcome_vector(_metrics(), annual=2080, annual_variance=40)
        vec_b = _outcome_vector(_metrics(flsa_violations=5, gap_events=4), annual=2080, annual_variance=40)
        self.assertFalse(_is_near_duplicate_candidate(vec_a, vec_b, cycle, cycle))

    def test_keeps_candidate_with_different_roster_even_if_same_outcome(self):
        cycle_a = [["0700"] * 5, ["1500"] * 5]
        cycle_b = [["1500"] * 5, ["2300"] * 5]
        vec = _outcome_vector(_metrics(), annual=2080, annual_variance=40)
        self.assertFalse(_is_near_duplicate_candidate(vec, vec, cycle_a, cycle_b))

    def test_old_profile_only_dedup_would_have_kept_this_but_new_check_rejects(self):
        # Simulates two pool solutions with different (variant,phase,start)
        # aggregate profiles (so the old count_vars-based exclusion cut would
        # not fire again) but whose actual assignments/outcomes are ~95%
        # identical — a real near-duplicate the audit says slips through.
        cycle_a = [["0700"] * 20]
        cycle_b = [["0700"] * 19 + ["1500"]]
        vec = _outcome_vector(_metrics(), annual=2080, annual_variance=40)
        self.assertGreater(_assignment_overlap_frac(cycle_a, cycle_b), 0.9)
        self.assertTrue(_is_near_duplicate_candidate(vec, vec, cycle_a, cycle_b))


if __name__ == "__main__":
    unittest.main()
