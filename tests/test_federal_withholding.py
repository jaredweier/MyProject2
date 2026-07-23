"""Oracle tests for logic/payroll/withholding.py against IRS Pub 15-T (2026)
Percentage Method Tables for Manual Payroll Systems With Forms W-4 From 2020
or Later. Expected values are computed by hand directly from the published
bracket tables (base_tax + (adjusted_wage - exceeds) * rate), not from the
implementation, so a bug in bracket lookup or Worksheet 4 arithmetic fails
these tests."""

import unittest

from logic.payroll.withholding import (
    calculate_federal_withholding,
    normalize_filing_status,
    normalize_pay_frequency,
    pay_periods_per_year,
)


class TestFederalWithholding(unittest.TestCase):
    def test_weekly_single_standard_mid_bracket(self):
        # Weekly, Single/MFS, standard: $548-$1,279 bracket, base $23.80, 12%, exceeds $548.
        result = calculate_federal_withholding(1000, "weekly", "single", tax_year=2026)
        self.assertAlmostEqual(result, 23.80 + (1000 - 548) * 0.12, places=2)

    def test_biweekly_mfj_standard_mid_bracket(self):
        # Biweekly, MFJ, standard: $2,192-$5,115 bracket, base $95.40, 12%, exceeds $2,192.
        result = calculate_federal_withholding(3000, "biweekly", "married_filing_jointly", tax_year=2026)
        self.assertAlmostEqual(result, 95.40 + (3000 - 2192) * 0.12, places=2)

    def test_weekly_step2_checkbox_uses_different_table(self):
        # Weekly, Single/MFS, Step 2 checked: $639-$1,171 bracket, base $55.70, 22%, exceeds $639.
        result = calculate_federal_withholding(700, "weekly", "single", step2_checkbox=True, tax_year=2026)
        self.assertAlmostEqual(result, 55.70 + (700 - 639) * 0.22, places=2)

    def test_zero_bracket_below_threshold(self):
        # Weekly, MFJ, standard: wages below $619 -> $0 withholding.
        result = calculate_federal_withholding(500, "weekly", "married_filing_jointly", tax_year=2026)
        self.assertEqual(result, 0.0)

    def test_monthly_head_of_household_with_dependents_credit(self):
        # Monthly, HoH, standard: $3,488-$7,633 bracket, base $147.50, 12%, exceeds $3,488.
        tentative = 147.50 + (5000 - 3488) * 0.12
        expected = round(tentative - (2000.0 / 12), 2)
        result = calculate_federal_withholding(
            5000,
            "monthly",
            "head_of_household",
            step3_dependents_credit_annual=2000.0,
            tax_year=2026,
        )
        self.assertAlmostEqual(result, expected, places=2)

    def test_step4a_other_income_increases_adjusted_wage(self):
        # Weekly, Single/MFS, standard, +$100/wk other income -> adjusted wage $1,100.
        result = calculate_federal_withholding(
            1000, "weekly", "single", step4a_other_income_annual=5200.0, tax_year=2026
        )
        self.assertAlmostEqual(result, 23.80 + (1100 - 548) * 0.12, places=2)

    def test_step4b_deductions_decreases_adjusted_wage(self):
        # Weekly, Single/MFS, standard, -$100/wk deductions -> adjusted wage $900.
        result = calculate_federal_withholding(1000, "weekly", "single", step4b_deductions_annual=5200.0, tax_year=2026)
        self.assertAlmostEqual(result, 23.80 + (900 - 548) * 0.12, places=2)

    def test_step4c_extra_withholding_adds_flat_amount(self):
        base = calculate_federal_withholding(1000, "weekly", "single", tax_year=2026)
        with_extra = calculate_federal_withholding(
            1000, "weekly", "single", step4c_extra_withholding=25.0, tax_year=2026
        )
        self.assertAlmostEqual(with_extra, base + 25.0, places=2)

    def test_credit_cannot_drive_withholding_negative(self):
        result = calculate_federal_withholding(
            500,
            "weekly",
            "married_filing_jointly",
            step3_dependents_credit_annual=1_000_000.0,
            tax_year=2026,
        )
        self.assertEqual(result, 0.0)

    def test_top_bracket_is_open_ended(self):
        # Weekly, Single/MFS, standard: above $12,629 -> base $3,711.14, 37%, exceeds $12,629.
        result = calculate_federal_withholding(20000, "weekly", "single", tax_year=2026)
        self.assertAlmostEqual(result, 3711.14 + (20000 - 12629) * 0.37, places=2)

    def test_unknown_tax_year_raises(self):
        with self.assertRaises(ValueError):
            calculate_federal_withholding(1000, "weekly", "single", tax_year=1999)

    def test_unknown_filing_status_raises(self):
        with self.assertRaises(ValueError):
            calculate_federal_withholding(1000, "weekly", "not_a_status", tax_year=2026)

    def test_normalize_filing_status_aliases(self):
        self.assertEqual(normalize_filing_status("Single"), "single_or_mfs")
        self.assertEqual(normalize_filing_status("MFJ"), "married_filing_jointly")
        self.assertEqual(normalize_filing_status("head of household"), "head_of_household")

    def test_pay_periods_per_year(self):
        self.assertEqual(pay_periods_per_year("weekly"), 52)
        self.assertEqual(pay_periods_per_year("biweekly"), 26)
        self.assertEqual(pay_periods_per_year("semimonthly"), 24)
        self.assertEqual(pay_periods_per_year("monthly"), 12)

    def test_unknown_pay_frequency_raises(self):
        with self.assertRaises(ValueError):
            normalize_pay_frequency("daily")


if __name__ == "__main__":
    unittest.main()
