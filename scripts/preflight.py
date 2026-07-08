"""Pre-commit gate — delegates to unified verify tier 'preflight'."""

from __future__ import annotations

from scripts.verify import run_preflight as verify_preflight


def run_preflight(with_refactor: bool = False) -> int:
    return verify_preflight(source="preflight", with_refactor=with_refactor)


if __name__ == "__main__":
    import sys

    with_refactor = "--with-refactor" in sys.argv
    raise SystemExit(run_preflight(with_refactor=with_refactor))
