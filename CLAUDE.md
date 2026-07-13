# Dodgeville PD â€” Claude / multi-agent notes

## Graphify = central knowledge base (always first)

**Use the knowledge graph for any project knowledge** â€” not only â€œwhere is this function?â€:

- Product behavior, feature location, architecture, process, doc/rule orientation
- Coupling between modules, â€œwhat touches day-off / payroll / UI?â€
- Orientation before opening large sources

```bash
# Ensure graph (free, local AST). Also run by: python dev.py graphify-gate
# Wired into: verify --tier preflight | check | full | release
graphify extract . --code-only
# or:
python dev.py graphify-gate

graphify query "<any project question>"
graphify path "A" "B"
graphify explain "Concept"
```

Read first:

- `graphify-out/KNOWLEDGE_HUB.md` â€” entry hubs (graph + docs + rules)
- `graphify-out/GRAPH_REPORT.md` â€” god nodes / communities
- `graphify-out/graph.json` via CLI query/path/explain (not full dump)

**Do not** re-read the whole repo when the graph can scope the answer.
Ship gate remains `python dev.py verify --tier check`.

Skill: `.claude/skills/graphify/SKILL.md` Â· PreToolUse hooks nudge search/read toward the graph.

## Use project tools whenever helpful

| Tool | Use when |
|------|----------|
| graphify | **Always first** for project knowledge |
| gstack | `/review` `/investigate` `/office-hours` `/qa` `/browse` `/ship` |
| stop-slop | Copy / docs / UI strings |
| frontend-design **or** taste | Visual UI (XOR) |
| Dodgeville skills | Domain `.grok/skills/*` |

## gstack (recommended install)

```bash
git clone --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack
cd ~/.claude/skills/gstack && ./setup --team
```

## stop-slop

`.claude/skills/stop-slop/SKILL.md` â€” strip AI writing patterns from prose.

## UI design skills (XOR â€” pick one)

Exactly one of **frontend-design** or a **taste-skill** pack member unless the user asks for both.

- Unspecified Chronos polish â†’ taste (`redesign-existing-projects`)
- Greenfield brand look â†’ frontend-design
Keep `.grok/rules/ui-modern.md` tokens.

## Session start (automatic bootstrap)

**Windows:** double-click `Start Agent Session.bat` or `Start Grok.bat`
(or `scripts\agent_session_bootstrap.bat` / `python dev.py session-start`).

That refreshes agent-kit, soft-refreshes the knowledge graph, and prints paste paths.
Cursor hooks also inject the same policy on sessionStart / workspaceOpen.

## Dodgeville free chain

`session-start` â†’ **graphify** â†’ usage-brief â†’ outline â†’ edit â†’ `graphify-gate` â†’ `verify --tier fast` â†’ ship `check`.

## GBrain Configuration (configured by /setup-gbrain)
- Mode: local-stdio
- Engine: pglite
- Config file: ~/.gbrain/config.json (mode 0600)
- Setup date: 2026-07-09
- MCP registered: no (Claude Code CLI not on this host; use `gbrain` CLI)
- Artifacts sync: off
- Current repo policy: unset (no origin remote)
- Embeddings: deferred (`--no-embedding`); set `OPENAI_API_KEY` or `VOYAGE_API_KEY`, then `gbrain config set embedding_model <provider:model>` and `gbrain embed --stale` for vector search
- Worktree pin: `.gbrain-source` -> gstack-code-myproject-3fd8ab37
- Code index: 282 pages / 3638 chunks (code strategy, --no-embed)
- Call graph: live (`code-callers`/`code-callees` ready after dream)

## GBrain Search Guidance (configured by /sync-gbrain)
<!-- gstack-gbrain-search-guidance:start -->

GBrain is set up and synced on this machine. The agent should prefer gbrain
over Grep when the question is semantic or when you don't know the exact
identifier yet.

**This worktree is pinned to a worktree-scoped code source** via the
`.gbrain-source` file in the repo root (kubectl-style context).
`gbrain code-def`, `code-refs`, `code-callers`, `code-callees`, `search`, and
`query` from anywhere under this worktree route to that source by default —
no `--source` flag needed (gbrain >= 0.41.38.0; on older gbrain the call-graph
commands need `--source "gstack-code-myproject-3fd8ab37"`). Conductor sibling worktrees
of the same repo each have their own pin and their own indexed pages, so
semantic results match the code on disk here.

Call-graph queries (`code-callers`/`code-callees`) also need the graph to be
built first — run `/sync-gbrain --dream` (or `--full`) if they return
`count: 0`. This only works if this source's gbrain schema pack extracts code
symbols; on a non-code-aware pack `--dream` completes but the graph stays empty
and reports a WARN. `code-def`/`code-refs` need the same extraction.

Two indexed corpora available via the `gbrain` CLI:
- This worktree's code (auto-pinned via `.gbrain-source`).
- `~/.gstack/` curated memory (registered as `gstack-brain-<user>` source via
  the existing federation pipeline).

Prefer gbrain when:
- "Where is X handled?" / semantic intent, no exact string yet:
    `gbrain search "<terms>"` or `gbrain query "<question>"`
- "Where is symbol Y defined?" / symbol-based code questions:
    `gbrain code-def <symbol>` or `gbrain code-refs <symbol>`
- "What calls Y?" / "What does Y depend on?":
    `gbrain code-callers <symbol>` / `gbrain code-callees <symbol>`
- "What did we decide last time?" / past plans, retros, learnings:
    `gbrain search "<terms>" --source gstack-brain-<user>`

Grep is still right for known exact strings, regex, multiline patterns, and
file globs. Run `/sync-gbrain` after meaningful code changes; for ongoing
auto-sync across all worktrees, run `gbrain autopilot --install` once per
machine — gbrain's daemon handles incremental refresh on a schedule.

Safety: don't run `/sync-gbrain` while `gbrain autopilot` is active — the
orchestrator refuses destructive source ops when it detects a running autopilot
to avoid racing it (#1734). Prefer registering user repos with `gbrain sources
add --path <dir>` (no `--url`): URL-managed sources can auto-reclone, and the
sync code walk for them requires an explicit `--allow-reclone` opt-in.

<!-- gstack-gbrain-search-guidance:end -->

## Design System

Always read `DESIGN.md` before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match `DESIGN.md`.
