---
description: Free agent bootstrap — token-first session pack (no LLM)
---

Run in shell (no vision, no full-repo read):

```bash
python dev.py agent-kit --slice day-off-requests --task "$ARGUMENTS"
```

Then work from `@logs/agent_kit/latest.md` only.
Budget files with `python dev.py read-budget <path>` before full reads.
Ship with `python dev.py verify --tier check`.
