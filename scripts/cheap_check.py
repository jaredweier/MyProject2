"""Ultra-fast gate — delegates to unified verify tier 'fast'."""

from __future__ import annotations

from scripts.verify import run_fast


def run_cheap_check() -> int:
    return run_fast(source="cheap-check")


if __name__ == "__main__":
    raise SystemExit(run_cheap_check())
