"""OBSOLETE one-shot extractor (2026-07-09).

Bump implementation now lives at ``logic/bump_optimizer.py``.
Public entry: ``logic.coverage_optimizer`` (suggest_bump_chain, etc.).
Do not re-create ``logic/scheduling_bump.py``.
"""

from __future__ import annotations

import sys


def main() -> int:
    print("obsolete: bump code is logic/bump_optimizer.py (public: logic.coverage_optimizer). No action taken.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
