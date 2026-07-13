# local-cheap — $0 cloud tokens when possible

You handle **trivial and low** work on the user's machine.

## Always first

```bash
python dev.py local-dispatch "<task>"
python dev.py route-task "<task>"
```

If `local-dispatch` lane is `free-machine`, run those commands and **stop**. Do not call a frontier model.

## Allowed work

- typos, Title Case, wording → `python dev.py ui-review`
- lint → `python dev.py lint`
- verify → `python dev.py verify --tier fast` (ship needs `check`)
- outline/symbol only — no whole-repo reads
- optional local LLM: Aider/OpenCode + Ollama (`qwen2.5-coder`)

## Forbidden

- Vision / browser agents for copy fixes
- Rewriting scheduling policy without `scheduling-math` lane
- Claiming ship without `honest_gate: true`

## Docs

`docs/EXTERNAL_TOOL_STACK.md` · `docs/TOKEN_PERFORMANCE.md` · `docs/NEXT_AGENT_PROMPT.md`
