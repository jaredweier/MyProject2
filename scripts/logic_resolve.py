"""Resolve public domain symbols across package + three-brain modules.

Slice/feature tooling must not require optimizer APIs to live on ``import logic``.
Prefer brain homes:

  generator — logic.scheduling / logic.scheduling_matrix
  optimizer — logic.coverage_optimizer / logic.bump_optimizer / logic.scheduling_sim
  payroll   — logic.payroll
"""

from __future__ import annotations

import importlib
from typing import Any, Iterable, Optional

# Modules that own public APIs (order: package first for speed, then brains).
_BRAIN_MODULES: tuple[str, ...] = (
    "logic",
    "logic.scheduling",
    "logic.scheduling_matrix",
    "logic.coverage_optimizer",
    "logic.bump_optimizer",
    "logic.scheduling_sim",
    "logic.staffing_optimizer",
    "logic.optimized_schedule_apply",
    "logic.ot_fill",
    "logic.payroll",
    "logic.requests",
    "logic.officers",
    "logic.operations",
    "logic.snapshots",
    "logic.bidding",
    "logic.analytics",
    "logic.exports",
    "logic.labor_compliance",
    "logic.banked_time",
    "logic.dashboard",
    "logic.users",
    "logic.staffing_config",
    "logic.rotation_config",
    "logic.rotation_patterns",
    "logic.rotation_preview",
    "logic.shift_assignment",
    "logic.simulator_store",
    "logic.extra_duty",
    "logic.callbacks",
    "logic.certifications",
    "logic.coverage_timeline",
    "logic.coverage_windows_store",
    "logic.bump_off_duty",
    "logic.plan_explain",
    "logic.leave_donation",
    "logic.roster_titles",
)


def _module_attr(mod: Any, name: str) -> bool:
    return hasattr(mod, name) and not name.startswith("_")


def logic_has(name: str) -> bool:
    """True if ``name`` is a public attribute on the package or a brain module."""
    if not name or name == "simulator module via ui":
        return True
    if "." in name:
        mod_name, _, attr = name.partition(".")
        if mod_name == "database":
            import database

            return hasattr(database, attr)
        try:
            mod = importlib.import_module(mod_name if mod_name.startswith("logic") else f"logic.{mod_name}")
        except ImportError:
            return False
        return hasattr(mod, attr)

    for mod_name in _BRAIN_MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        if _module_attr(mod, name):
            return True
    return False


def resolve_logic(name: str) -> Optional[Any]:
    """Return the attribute object, or None if not found."""
    if not name or "." in name:
        return None
    for mod_name in _BRAIN_MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        if _module_attr(mod, name):
            return getattr(mod, name)
    return None


def all_public_logic_names() -> set[str]:
    """Union of public names across package + brain modules (for import audits)."""
    names: set[str] = set()
    for mod_name in _BRAIN_MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        for n in dir(mod):
            if not n.startswith("_"):
                names.add(n)
    return names


def missing_logic_symbols(names: Iterable[str]) -> list[str]:
    return [n for n in names if not logic_has(n)]
