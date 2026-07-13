---
name: ui-development
description: >
  Chronos NiceGUI (gui/*) UI specialist — maximum capability. Use ANY public
  source for look and function. Tool: python dev.py ui-domain.
---

# UI Development — maximum capability

## Goal

Build the **best** Chronos UI possible. Research is unrestricted.

## Tools

```bash
python dev.py ui-domain explore|brainstorm|research-queries|suggest --all|learn
python dev.py ui-review · ui-diff --quick · chronos-e2e
```

web_search / GitHub / competitor UX / design systems / demos — **all allowed**.

## Surfaces

- Primary: `gui/app.py`, `gui/shell.py`, `gui/pages/*`, `gui/static/chronos.css`, `gui/tables.py`
- Legacy `ui/*` only when useful as reference

## Implementation

- Prefer strong complete UX over half-wired features
- Call `logic.*` for domain ops when practical; restructure layers if a better architecture wins
- Deposit finds: `ui-domain learn --url … --as-idea`

## Design skill XOR (mandatory)

Before visual UI work, pick **exactly one**:

| Pick | Skill | Prefer when |
|------|--------|-------------|
| A | `frontend-design` | Greenfield identity, distinctive new pages |
| B | taste pack (`design-taste-frontend`, `redesign-existing-projects`, …) | Chronos polish, anti-slop, redesign existing UI |

- **Do not load both** in one task unless the user explicitly requests both.
- User names a skill → that skill only.
- Unspecified → Chronos/`gui` polish = **B** (`redesign-existing-projects`); greenfield brand = **A**.
- Always keep `ui-modern.md` tokens; this skill still owns wiring/`logic` calls.

## Related

`first-responder-wfm` · `scheduling-logic` · `docs/knowledge/ui_sources.json` · `AGENTS.md` § UI design skills
