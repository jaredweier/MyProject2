---
description: Run full Dodgeville PD verification suite
agent: build
---

Run project verification in order:

1. `python dev.py preflight`
2. `python dev.py check`
3. If UI files changed in this session, also `python dev.py ui-smoke`

Report pass/fail for each step and summarize any failures with file paths.
