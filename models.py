from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple


@dataclass
class Officer:
    id: int
    name: str
    seniority_rank: int
    squad: str
    shift_start: str
    shift_end: str
    pay_rate: float = 30.0
    night_differential_rate: float = 1.0
    photo_path: Optional[str] = None
    active: bool = True
    start_date: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


@dataclass
class ProcessRequestResult:
    success: bool
    status: str = ""
    message: str = ""
    override_created: bool = False
    requires_manual: bool = False


@dataclass
class ProcessSwapResult:
    success: bool
    status: str = ""
    message: str = ""
    overrides_created: bool = False
    requires_manual: bool = False


@dataclass
class BumpChainStep:
    step_number: int
    original_officer_id: int
    original_officer_name: str
    original_shift: str
    replacement_officer_id: int
    replacement_officer_name: str
    replacement_shift: str
    replacement_on_duty: bool


@dataclass
class BumpChainSuggestion:
    success: bool
    chain: List[Tuple[int, int]] = field(default_factory=list)
    steps: List[BumpChainStep] = field(default_factory=list)
    primary_replacement_name: Optional[str] = None
    message: str = ""
    requires_manual: bool = False
    failure_reason: Optional[str] = None
    blocked_officer_name: Optional[str] = None
    blocked_shift: Optional[str] = None
    # Coverage optimizer metadata (optional; ignored by older call sites)
    plan_score: Optional[float] = None
    alternatives_considered: Optional[int] = None
    # Named soft components (OR-Tools / Timefold explainability)
    score_components: Optional[List[Dict]] = None


@dataclass
class BumpSimulationResult:
    success: bool
    replacement_name: Optional[str] = None
    message: str = ""
    requires_manual: bool = False
    reason: Optional[str] = None
    suggestion: Optional[BumpChainSuggestion] = None


@dataclass
class SwapValidationResult:
    success: bool
    officer1_id: int
    officer2_id: int
    swap_date: date
    message: str = ""
    requires_manual: bool = False
    reason: Optional[str] = None
    can_proceed: bool = False


@dataclass
class PayCalculationResult:
    entry_type: str
    regular_hours: float = 0.0
    overtime_hours: float = 0.0
    night_differential_hours: float = 0.0
    base_pay: float = 0.0
    overtime_pay: float = 0.0
    night_differential_pay: float = 0.0
    total_pay: float = 0.0
    comp_bank_delta: float = 0.0
    sick_bank_delta: float = 0.0
    float_holiday_bank_delta: float = 0.0
    holiday_bank_delta: float = 0.0
    message: str = ""
