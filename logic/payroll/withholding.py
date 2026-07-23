"""Federal income tax withholding — IRS Pub 15-T Percentage Method (Forms W-4 from 2020+).

Implements Worksheet 4 ("Employer's Withholding Worksheet for Percentage
Method Tables for Manual Payroll Systems With Forms W-4 From 2020 or Later")
from IRS Publication 15-T. Tables are versioned per tax year — add a new
entry to ``_WITHHOLDING_TABLES`` and ``_PAY_PERIODS_PER_YEAR`` stays fixed
when a new year's publication is released. Only the 2026 tables are present
today; earlier/later years are not supported until added.

This computes federal withholding only — state/local withholding, FICA, and
other deductions are handled elsewhere in logic/payroll/.
"""

from __future__ import annotations

from typing import Dict, List, NamedTuple, Optional

FilingStatus = str  # "single_or_mfs" | "married_filing_jointly" | "head_of_household"
PayFrequency = str  # "weekly" | "biweekly" | "semimonthly" | "monthly"

_FILING_STATUS_ALIASES: Dict[str, FilingStatus] = {
    "single": "single_or_mfs",
    "single_or_mfs": "single_or_mfs",
    "married_filing_separately": "single_or_mfs",
    "mfs": "single_or_mfs",
    "married_filing_jointly": "married_filing_jointly",
    "mfj": "married_filing_jointly",
    "married": "married_filing_jointly",
    "head_of_household": "head_of_household",
    "hoh": "head_of_household",
}

_PAY_PERIODS_PER_YEAR: Dict[PayFrequency, int] = {
    "weekly": 52,
    "biweekly": 26,
    "semimonthly": 24,
    "monthly": 12,
}


class _Bracket(NamedTuple):
    at_least: float
    less_than: Optional[float]  # None = top, open-ended bracket
    base_tax: float
    rate_pct: float  # e.g. 12.0 for 12%
    exceeds: float


# Publication 15-T (2026), section "4. Percentage Method Tables for Manual
# Payroll Systems With Forms W-4 From 2020 or Later" — Standard Withholding
# Rate Schedules (Step 2 box NOT checked) and Step 2 Checkbox Withholding
# Rate Schedules, transcribed verbatim from the published tables.
_WITHHOLDING_TABLES: Dict[int, Dict[PayFrequency, Dict[bool, Dict[FilingStatus, List[_Bracket]]]]] = {
    2026: {
        "weekly": {
            False: {
                "married_filing_jointly": [
                    _Bracket(0, 619, 0.00, 0, 0),
                    _Bracket(619, 1096, 0.00, 10, 619),
                    _Bracket(1096, 2558, 47.70, 12, 1096),
                    _Bracket(2558, 4685, 223.14, 22, 2558),
                    _Bracket(4685, 8380, 691.08, 24, 4685),
                    _Bracket(8380, 10474, 1577.88, 32, 8380),
                    _Bracket(10474, 15402, 2247.96, 35, 10474),
                    _Bracket(15402, None, 3972.76, 37, 15402),
                ],
                "single_or_mfs": [
                    _Bracket(0, 310, 0.00, 0, 0),
                    _Bracket(310, 548, 0.00, 10, 310),
                    _Bracket(548, 1279, 23.80, 12, 548),
                    _Bracket(1279, 2342, 111.52, 22, 1279),
                    _Bracket(2342, 4190, 345.38, 24, 2342),
                    _Bracket(4190, 5237, 788.90, 32, 4190),
                    _Bracket(5237, 12629, 1123.94, 35, 5237),
                    _Bracket(12629, None, 3711.14, 37, 12629),
                ],
                "head_of_household": [
                    _Bracket(0, 464, 0.00, 0, 0),
                    _Bracket(464, 805, 0.00, 10, 464),
                    _Bracket(805, 1762, 34.10, 12, 805),
                    _Bracket(1762, 2497, 148.94, 22, 1762),
                    _Bracket(2497, 4344, 310.64, 24, 2497),
                    _Bracket(4344, 5391, 753.92, 32, 4344),
                    _Bracket(5391, 12784, 1088.96, 35, 5391),
                    _Bracket(12784, None, 3676.51, 37, 12784),
                ],
            },
            True: {
                "married_filing_jointly": [
                    _Bracket(0, 310, 0.00, 0, 0),
                    _Bracket(310, 548, 0.00, 10, 310),
                    _Bracket(548, 1279, 23.80, 12, 548),
                    _Bracket(1279, 2342, 111.52, 22, 1279),
                    _Bracket(2342, 4190, 345.38, 24, 2342),
                    _Bracket(4190, 5237, 788.90, 32, 4190),
                    _Bracket(5237, 7701, 1123.94, 35, 5237),
                    _Bracket(7701, None, 1986.34, 37, 7701),
                ],
                "single_or_mfs": [
                    _Bracket(0, 155, 0.00, 0, 0),
                    _Bracket(155, 274, 0.00, 10, 155),
                    _Bracket(274, 639, 11.90, 12, 274),
                    _Bracket(639, 1171, 55.70, 22, 639),
                    _Bracket(1171, 2095, 172.74, 24, 1171),
                    _Bracket(2095, 2619, 394.50, 32, 2095),
                    _Bracket(2619, 6314, 562.18, 35, 2619),
                    _Bracket(6314, None, 1855.43, 37, 6314),
                ],
                "head_of_household": [
                    _Bracket(0, 232, 0.00, 0, 0),
                    _Bracket(232, 402, 0.00, 10, 232),
                    _Bracket(402, 881, 17.00, 12, 402),
                    _Bracket(881, 1249, 74.48, 22, 881),
                    _Bracket(1249, 2172, 155.44, 24, 1249),
                    _Bracket(2172, 2696, 376.96, 32, 2172),
                    _Bracket(2696, 6392, 544.64, 35, 2696),
                    _Bracket(6392, None, 1838.24, 37, 6392),
                ],
            },
        },
        "biweekly": {
            False: {
                "married_filing_jointly": [
                    _Bracket(0, 1238, 0.00, 0, 0),
                    _Bracket(1238, 2192, 0.00, 10, 1238),
                    _Bracket(2192, 5115, 95.40, 12, 2192),
                    _Bracket(5115, 9369, 446.16, 22, 5115),
                    _Bracket(9369, 16760, 1382.04, 24, 9369),
                    _Bracket(16760, 20948, 3155.88, 32, 16760),
                    _Bracket(20948, 30804, 4496.04, 35, 20948),
                    _Bracket(30804, None, 7945.64, 37, 30804),
                ],
                "single_or_mfs": [
                    _Bracket(0, 619, 0.00, 0, 0),
                    _Bracket(619, 1096, 0.00, 10, 619),
                    _Bracket(1096, 2558, 47.70, 12, 1096),
                    _Bracket(2558, 4685, 223.14, 22, 2558),
                    _Bracket(4685, 8380, 691.08, 24, 4685),
                    _Bracket(8380, 10474, 1577.88, 32, 8380),
                    _Bracket(10474, 25258, 2247.96, 35, 10474),
                    _Bracket(25258, None, 7422.36, 37, 25258),
                ],
                "head_of_household": [
                    _Bracket(0, 929, 0.00, 0, 0),
                    _Bracket(929, 1610, 0.00, 10, 929),
                    _Bracket(1610, 3523, 68.10, 12, 1610),
                    _Bracket(3523, 4994, 297.66, 22, 3523),
                    _Bracket(4994, 8688, 621.28, 24, 4994),
                    _Bracket(8688, 10783, 1507.84, 32, 8688),
                    _Bracket(10783, 25567, 2178.24, 35, 10783),
                    _Bracket(25567, None, 7352.64, 37, 25567),
                ],
            },
            True: {
                "married_filing_jointly": [
                    _Bracket(0, 619, 0.00, 0, 0),
                    _Bracket(619, 1096, 0.00, 10, 619),
                    _Bracket(1096, 2558, 47.70, 12, 1096),
                    _Bracket(2558, 4685, 223.14, 22, 2558),
                    _Bracket(4685, 8380, 691.08, 24, 4685),
                    _Bracket(8380, 10474, 1577.88, 32, 8380),
                    _Bracket(10474, 15402, 2247.96, 35, 10474),
                    _Bracket(15402, None, 3972.76, 37, 15402),
                ],
                "single_or_mfs": [
                    _Bracket(0, 310, 0.00, 0, 0),
                    _Bracket(310, 548, 0.00, 10, 310),
                    _Bracket(548, 1279, 23.80, 12, 548),
                    _Bracket(1279, 2342, 111.52, 22, 1279),
                    _Bracket(2342, 4190, 345.38, 24, 2342),
                    _Bracket(4190, 5237, 788.90, 32, 4190),
                    _Bracket(5237, 12629, 1123.94, 35, 5237),
                    _Bracket(12629, None, 3711.14, 37, 12629),
                ],
                "head_of_household": [
                    _Bracket(0, 464, 0.00, 0, 0),
                    _Bracket(464, 805, 0.00, 10, 464),
                    _Bracket(805, 1762, 34.10, 12, 805),
                    _Bracket(1762, 2497, 148.94, 22, 1762),
                    _Bracket(2497, 4344, 310.64, 24, 2497),
                    _Bracket(4344, 5391, 753.92, 32, 4344),
                    _Bracket(5391, 12784, 1088.96, 35, 5391),
                    _Bracket(12784, None, 3676.51, 37, 12784),
                ],
            },
        },
        "semimonthly": {
            False: {
                "married_filing_jointly": [
                    _Bracket(0, 1342, 0.00, 0, 0),
                    _Bracket(1342, 2375, 0.00, 10, 1342),
                    _Bracket(2375, 5542, 103.30, 12, 2375),
                    _Bracket(5542, 10150, 483.34, 22, 5542),
                    _Bracket(10150, 18156, 1497.10, 24, 10150),
                    _Bracket(18156, 22694, 3418.54, 32, 18156),
                    _Bracket(22694, 33371, 4870.70, 35, 22694),
                    _Bracket(33371, None, 8607.65, 37, 33371),
                ],
                "single_or_mfs": [
                    _Bracket(0, 671, 0.00, 0, 0),
                    _Bracket(671, 1188, 0.00, 10, 671),
                    _Bracket(1188, 2771, 51.70, 12, 1188),
                    _Bracket(2771, 5075, 241.66, 22, 2771),
                    _Bracket(5075, 9078, 748.54, 24, 5075),
                    _Bracket(9078, 11347, 1709.26, 32, 9078),
                    _Bracket(11347, 27363, 2435.34, 35, 11347),
                    _Bracket(27363, None, 8040.94, 37, 27363),
                ],
                "head_of_household": [
                    _Bracket(0, 1006, 0.00, 0, 0),
                    _Bracket(1006, 1744, 0.00, 10, 1006),
                    _Bracket(1744, 3817, 73.80, 12, 1744),
                    _Bracket(3817, 5410, 322.56, 22, 3817),
                    _Bracket(5410, 9413, 673.02, 24, 5410),
                    _Bracket(9413, 11681, 1633.74, 32, 9413),
                    _Bracket(11681, 27698, 2359.50, 35, 11681),
                    _Bracket(27698, None, 7965.45, 37, 27698),
                ],
            },
            True: {
                "married_filing_jointly": [
                    _Bracket(0, 671, 0.00, 0, 0),
                    _Bracket(671, 1188, 0.00, 10, 671),
                    _Bracket(1188, 2771, 51.70, 12, 1188),
                    _Bracket(2771, 5075, 241.66, 22, 2771),
                    _Bracket(5075, 9078, 748.54, 24, 5075),
                    _Bracket(9078, 11347, 1709.26, 32, 9078),
                    _Bracket(11347, 16685, 2435.34, 35, 11347),
                    _Bracket(16685, None, 4303.64, 37, 16685),
                ],
                "single_or_mfs": [
                    _Bracket(0, 335, 0.00, 0, 0),
                    _Bracket(335, 594, 0.00, 10, 335),
                    _Bracket(594, 1385, 25.90, 12, 594),
                    _Bracket(1385, 2538, 120.82, 22, 1385),
                    _Bracket(2538, 4539, 374.48, 24, 2538),
                    _Bracket(4539, 5673, 854.72, 32, 4539),
                    _Bracket(5673, 13681, 1217.60, 35, 5673),
                    _Bracket(13681, None, 4020.40, 37, 13681),
                ],
                "head_of_household": [
                    _Bracket(0, 503, 0.00, 0, 0),
                    _Bracket(503, 872, 0.00, 10, 503),
                    _Bracket(872, 1908, 36.90, 12, 872),
                    _Bracket(1908, 2705, 161.22, 22, 1908),
                    _Bracket(2705, 4706, 336.56, 24, 2705),
                    _Bracket(4706, 5841, 816.80, 32, 4706),
                    _Bracket(5841, 13849, 1180.00, 35, 5841),
                    _Bracket(13849, None, 3982.80, 37, 13849),
                ],
            },
        },
        "monthly": {
            False: {
                "married_filing_jointly": [
                    _Bracket(0, 2683, 0.00, 0, 0),
                    _Bracket(2683, 4750, 0.00, 10, 2683),
                    _Bracket(4750, 11083, 206.70, 12, 4750),
                    _Bracket(11083, 20300, 966.66, 22, 11083),
                    _Bracket(20300, 36313, 2994.40, 24, 20300),
                    _Bracket(36313, 45388, 6837.52, 32, 36313),
                    _Bracket(45388, 66742, 9741.52, 35, 45388),
                    _Bracket(66742, None, 17215.42, 37, 66742),
                ],
                "single_or_mfs": [
                    _Bracket(0, 1342, 0.00, 0, 0),
                    _Bracket(1342, 2375, 0.00, 10, 1342),
                    _Bracket(2375, 5542, 103.30, 12, 2375),
                    _Bracket(5542, 10150, 483.34, 22, 5542),
                    _Bracket(10150, 18156, 1497.10, 24, 10150),
                    _Bracket(18156, 22694, 3418.54, 32, 18156),
                    _Bracket(22694, 54725, 4870.70, 35, 22694),
                    _Bracket(54725, None, 16081.55, 37, 54725),
                ],
                "head_of_household": [
                    _Bracket(0, 2013, 0.00, 0, 0),
                    _Bracket(2013, 3488, 0.00, 10, 2013),
                    _Bracket(3488, 7633, 147.50, 12, 3488),
                    _Bracket(7633, 10821, 644.90, 22, 7633),
                    _Bracket(10821, 18825, 1346.26, 24, 10821),
                    _Bracket(18825, 23363, 3267.22, 32, 18825),
                    _Bracket(23363, 55396, 4719.38, 35, 23363),
                    _Bracket(55396, None, 15930.93, 37, 55396),
                ],
            },
            True: {
                "married_filing_jointly": [
                    _Bracket(0, 1342, 0.00, 0, 0),
                    _Bracket(1342, 2375, 0.00, 10, 1342),
                    _Bracket(2375, 5542, 103.30, 12, 2375),
                    _Bracket(5542, 10150, 483.34, 22, 5542),
                    _Bracket(10150, 18156, 1497.10, 24, 10150),
                    _Bracket(18156, 22694, 3418.54, 32, 18156),
                    _Bracket(22694, 33371, 4870.70, 35, 22694),
                    _Bracket(33371, None, 8607.65, 37, 33371),
                ],
                "single_or_mfs": [
                    _Bracket(0, 671, 0.00, 0, 0),
                    _Bracket(671, 1188, 0.00, 10, 671),
                    _Bracket(1188, 2771, 51.70, 12, 1188),
                    _Bracket(2771, 5075, 241.66, 22, 2771),
                    _Bracket(5075, 9078, 748.54, 24, 5075),
                    _Bracket(9078, 11347, 1709.26, 32, 9078),
                    _Bracket(11347, 27363, 2435.34, 35, 11347),
                    _Bracket(27363, None, 8040.94, 37, 27363),
                ],
                "head_of_household": [
                    _Bracket(0, 1006, 0.00, 0, 0),
                    _Bracket(1006, 1744, 0.00, 10, 1006),
                    _Bracket(1744, 3817, 73.80, 12, 1744),
                    _Bracket(3817, 5410, 322.56, 22, 3817),
                    _Bracket(5410, 9413, 673.02, 24, 5410),
                    _Bracket(9413, 11681, 1633.74, 32, 9413),
                    _Bracket(11681, 27698, 2359.50, 35, 11681),
                    _Bracket(27698, None, 7965.45, 37, 27698),
                ],
            },
        },
    },
}


def normalize_filing_status(value: str) -> FilingStatus:
    key = (value or "").strip().lower().replace(" ", "_").replace("-", "_")
    status = _FILING_STATUS_ALIASES.get(key)
    if not status:
        raise ValueError(f"Unknown filing status: {value!r}")
    return status


def normalize_pay_frequency(value: str) -> PayFrequency:
    key = (value or "").strip().lower()
    if key not in _PAY_PERIODS_PER_YEAR:
        raise ValueError(f"Unknown pay frequency: {value!r}")
    return key


def pay_periods_per_year(pay_frequency: str) -> int:
    return _PAY_PERIODS_PER_YEAR[normalize_pay_frequency(pay_frequency)]


def _find_bracket(brackets: List[_Bracket], adjusted_wage: float) -> _Bracket:
    for bracket in brackets:
        if adjusted_wage >= bracket.at_least and (bracket.less_than is None or adjusted_wage < bracket.less_than):
            return bracket
    # Adjusted wage is negative (shouldn't happen — callers floor at 0).
    return brackets[0]


def calculate_federal_withholding(
    gross_wages: float,
    pay_frequency: str,
    filing_status: str,
    *,
    step2_checkbox: bool = False,
    step3_dependents_credit_annual: float = 0.0,
    step4a_other_income_annual: float = 0.0,
    step4b_deductions_annual: float = 0.0,
    step4c_extra_withholding: float = 0.0,
    tax_year: int = 2026,
) -> float:
    """Federal income tax to withhold this pay period.

    Implements IRS Pub 15-T Worksheet 4 exactly (Steps 1-4), for tax years
    with tables loaded in ``_WITHHOLDING_TABLES``. Inputs mirror the
    employee's Form W-4 (2020+ revision): ``step2_checkbox`` is the Step 2
    multiple-jobs box, ``step3_dependents_credit_annual`` is the Step 3
    dependents/other-credits total, ``step4a_other_income_annual`` and
    ``step4b_deductions_annual`` are Step 4(a)/4(b), and
    ``step4c_extra_withholding`` is the Step 4(c) flat per-period add-on.
    """
    if tax_year not in _WITHHOLDING_TABLES:
        raise ValueError(f"No federal withholding tables loaded for tax year {tax_year}")
    frequency = normalize_pay_frequency(pay_frequency)
    status = normalize_filing_status(filing_status)
    periods = _PAY_PERIODS_PER_YEAR[frequency]

    # Step 1: adjust the wage amount.
    line_1a = max(0.0, float(gross_wages))
    line_1d = float(step4a_other_income_annual) / periods
    line_1e = line_1a + line_1d
    line_1g = float(step4b_deductions_annual) / periods
    line_1h = max(0.0, line_1e - line_1g)

    # Step 2: tentative withholding from the percentage-method table.
    brackets = _WITHHOLDING_TABLES[tax_year][frequency][bool(step2_checkbox)][status]
    bracket = _find_bracket(brackets, line_1h)
    line_2f = bracket.base_tax + (line_1h - bracket.exceeds) * (bracket.rate_pct / 100.0)

    # Step 3: dependents/other credits.
    line_3b = float(step3_dependents_credit_annual) / periods
    line_3c = max(0.0, line_2f - line_3b)

    # Step 4: additional flat withholding.
    line_4b = line_3c + float(step4c_extra_withholding)

    return round(line_4b, 2)
