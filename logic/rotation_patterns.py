"""Multi-block rotation patterns: fixed vs rotating, variations, phase.

Used by simulator, schedule builder duty checks, and future per-officer roster fields.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

MAX_COMPOSITE_CYCLE_LENGTH = 112
MIN_BLOCK_ON = 1
MAX_BLOCK_ON = 28
MIN_BLOCK_OFF = 0
MAX_BLOCK_OFF = 28

ROTATION_STYLE_FIXED = "fixed"
ROTATION_STYLE_ROTATING = "rotating"


@dataclass(frozen=True)
class OnOffBlock:
    days_on: int
    days_off: int

    @property
    def length(self) -> int:
        return self.days_on + self.days_off


@dataclass
class RotationPattern:
    """One rotation variation (duty vector over a cycle)."""

    style: str  # fixed | rotating
    blocks: List[OnOffBlock] = field(default_factory=list)
    label: str = ""
    phase: int = 0  # cycle offset days

    @property
    def cycle_length(self) -> int:
        return sum(b.length for b in self.blocks)

    def duty_vector(self) -> List[bool]:
        vec: List[bool] = []
        for block in self.blocks:
            vec.extend([True] * block.days_on)
            vec.extend([False] * block.days_off)
        return vec

    def is_working(self, cycle_day: int) -> bool:
        """cycle_day is 1-based within the cycle."""
        vec = self.duty_vector()
        if not vec:
            return False
        n = len(vec)
        idx = (cycle_day - 1 + self.phase) % n
        return vec[idx]

    def work_days_per_cycle(self) -> int:
        return sum(1 for d in self.duty_vector() if d)

    def to_text(self) -> str:
        return ",".join(f"{b.days_on}-{b.days_off}" for b in self.blocks)

    def with_phase(self, phase: int) -> "RotationPattern":
        return RotationPattern(
            style=self.style,
            blocks=list(self.blocks),
            label=self.label,
            phase=int(phase) % max(self.cycle_length, 1),
        )


def parse_on_off_blocks(text: str) -> List[OnOffBlock]:
    """Parse '5-2' or '5-3,6-2' or '4-4,4-4,4-4,5-3,5-3' into blocks."""
    raw = (text or "").strip()
    if not raw:
        return []
    blocks: List[OnOffBlock] = []
    # Allow spaces around commas
    parts = re.split(r"[,;]+", raw)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(\d+)\s*[-/]\s*(\d+)$", part)
        if not m:
            raise ValueError(f"Invalid rotation block: {part!r} (use on-off like 5-2)")
        on_d, off_d = int(m.group(1)), int(m.group(2))
        if on_d < MIN_BLOCK_ON or on_d > MAX_BLOCK_ON:
            raise ValueError(f"days_on must be {MIN_BLOCK_ON}–{MAX_BLOCK_ON}, got {on_d}")
        if off_d < MIN_BLOCK_OFF or off_d > MAX_BLOCK_OFF:
            raise ValueError(f"days_off must be {MIN_BLOCK_OFF}–{MAX_BLOCK_OFF}, got {off_d}")
        blocks.append(OnOffBlock(on_d, off_d))
    return blocks


def build_pattern(
    text: str,
    *,
    style: Optional[str] = None,
    phase: int = 0,
    label: str = "",
) -> RotationPattern:
    blocks = parse_on_off_blocks(text)
    if not blocks:
        raise ValueError("Rotation pattern is empty")
    cycle = sum(b.length for b in blocks)
    if cycle > MAX_COMPOSITE_CYCLE_LENGTH:
        raise ValueError(f"Cycle length {cycle} exceeds max {MAX_COMPOSITE_CYCLE_LENGTH}")
    if style is None:
        style = ROTATION_STYLE_FIXED if len(blocks) == 1 else ROTATION_STYLE_ROTATING
    style = style.lower().strip()
    if style not in (ROTATION_STYLE_FIXED, ROTATION_STYLE_ROTATING):
        raise ValueError("style must be 'fixed' or 'rotating'")
    if style == ROTATION_STYLE_FIXED and len(blocks) != 1:
        raise ValueError("Fixed rotation must be a single on-off block (e.g. 5-2)")
    if style == ROTATION_STYLE_ROTATING and len(blocks) < 2:
        raise ValueError("Rotating rotation needs multiple blocks (e.g. 5-3,6-2)")
    return RotationPattern(
        style=style,
        blocks=blocks,
        label=label or text.strip(),
        phase=phase % cycle if cycle else 0,
    )


def validate_variation_set(patterns: Sequence[RotationPattern]) -> Tuple[bool, str]:
    """All variations must share the same cycle length."""
    if not patterns:
        return False, "At least one rotation variation is required"
    lengths = {p.cycle_length for p in patterns}
    if len(lengths) != 1:
        detail = ", ".join(f"{p.label or p.to_text()}={p.cycle_length}" for p in patterns)
        return False, f"All variations must share the same cycle length ({detail})"
    return True, f"OK ({next(iter(lengths))}-day cycle, {len(patterns)} variation(s))"


def parse_variation_set(
    texts: Sequence[str],
    *,
    style: Optional[str] = None,
) -> List[RotationPattern]:
    patterns = [build_pattern(t, style=style) for t in texts if (t or "").strip()]
    ok, msg = validate_variation_set(patterns)
    if not ok:
        raise ValueError(msg)
    return patterns


def expand_block_permutations(
    patterns: Sequence[RotationPattern],
) -> List[RotationPattern]:
    """Given a variation set, add all unique block-order permutations.

    For a 2-block pattern like 6-2,5-3 this produces 6-2,5-3 / 5-3,6-2 /
    6-3,5-2 / 5-2,6-3 — four distinct duty vectors from the same on/off
    block pool.  Single-block patterns pass through unchanged.
    """
    from itertools import permutations as _perms

    seen: set = set()
    result: List[RotationPattern] = []
    for p in patterns:
        dv = tuple(p.duty_vector())
        if dv not in seen:
            seen.add(dv)
            result.append(p)
        if len(p.blocks) < 2:
            continue
        for perm in _perms(p.blocks):
            blocks = list(perm)
            candidate = RotationPattern(
                style=p.style, blocks=blocks, label=",".join(f"{b.days_on}-{b.days_off}" for b in blocks)
            )
            cdv = tuple(candidate.duty_vector())
            if cdv not in seen:
                seen.add(cdv)
                result.append(candidate)
        swapped = [
            OnOffBlock(days_on=b.days_on, days_off=other.days_off)
            for b, other in zip(p.blocks, list(p.blocks)[1:] + [p.blocks[0]])
        ]
        for perm in _perms(swapped):
            blocks = list(perm)
            cl = sum(b.length for b in blocks)
            if cl != p.cycle_length:
                continue
            candidate = RotationPattern(
                style=p.style, blocks=blocks, label=",".join(f"{b.days_on}-{b.days_off}" for b in blocks)
            )
            cdv = tuple(candidate.duty_vector())
            if cdv not in seen:
                seen.add(cdv)
                result.append(candidate)
    return result


def projected_annual_hours(
    pattern: RotationPattern,
    shift_length_hours: float,
    *,
    days_per_year: float = 365.25,
) -> float:
    """
    Year-average annual hours from work fraction × shift length.

    Uses 365.25 (mean Gregorian year) so leap years are averaged in.
    Cycle length rarely divides 365/366 evenly — real calendar years will
    differ slightly by officer phase; compare officers for fairness, not
    exact equality to a single target hour.
    """
    cl = pattern.cycle_length
    if cl <= 0:
        return 0.0
    work_frac = pattern.work_days_per_cycle() / cl
    return round(work_frac * days_per_year * shift_length_hours, 1)


def annual_hours_within_band(
    projected: float,
    target: float,
    *,
    variance_hours: float = 0.0,
    variance_percent: float = 0.0,
) -> Tuple[bool, float, float, float]:
    """Return (ok, low, high, distance_outside). distance_outside=0 if inside band."""
    band = float(variance_hours or 0.0)
    if variance_percent:
        band = max(band, abs(target) * float(variance_percent) / 100.0)
    low = target - band
    high = target + band
    if projected < low:
        return False, low, high, low - projected
    if projected > high:
        return False, low, high, projected - high
    return True, low, high, 0.0


def pattern_summary(pattern: RotationPattern) -> Dict:
    return {
        "style": pattern.style,
        "label": pattern.label,
        "text": pattern.to_text(),
        "cycle_length": pattern.cycle_length,
        "phase": pattern.phase,
        "work_days_per_cycle": pattern.work_days_per_cycle(),
        "duty_vector": pattern.duty_vector(),
    }
