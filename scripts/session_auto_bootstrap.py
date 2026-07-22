#!/usr/bin/env python3
"""Auto-run at every new agent session (Grok/Cursor hook or launcher).

Refreshes lean kit/pack + SESSION_CONTRACT.md. No graphify tax.
Safe to call from any cwd; only acts when workspace is this MyProject tree
(or SCHEDULER_FORCE_BOOTSTRAP=1).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "logs" / "SESSION_CONTRACT.md"
KIT = ROOT / "logs" / "agent_kit" / "latest.md"
PACK = ROOT / "logs" / "agent_pack" / "latest.md"

CONTRACT_BODY = """# Session contract (auto - do not ask user to paste)

You are already bound by `AGENTS.md` + `.grok/rules/*`. Follow now.

## Trust (human rebuke - binding)
- Full rules + mistakes: **`docs/AGENT_TRUST_AND_MISTAKES.md`** (read when doing product/sim/optimizer/UI).
- **Never claim fixed/done** without proving the **user exact scenario** (or honest residual).
- Unit green != Chronos works. **No half-jobs. No appeasement hacks.**
- User numbers first (e.g. **8h** shifts: 6-2,5-3 annual ~ **2008h**). Do not invent 11h/12h.
- Prove first, claim second. Ship language only: `verify --tier check` + `honest_gate: true`.

## Reply
Caveman: short bullets. No preamble/recap. Prose only if user asks explain/docs.

## Work
1. `python dev.py route-task "<task>"` **once** - obey cost_tier
2. Load **at most one** skill body if route prints it
3. `usage-brief` then `outline`/`symbol` then edit `touch_together` only
4. After edits: `python dev.py verify --tier fast`
5. Ship claim: `verify --tier check` + `logs/last_verify.json` -> `honest_gate: true`

## Hard bans
- No explore/plan subagents; no subagents for gates/verify
- Never open `docs/archived_skills/` unless user names that skill
- No graphify / vision / OSS research unless user asks
- No whole-repo reads; stop when confident
- No fixed/implemented without scenario proof or explicit residual

## Primary product
Chronos UI = `gui/`. Domain = `logic/*` + `validators`. No SQL in `gui/`.
**Brand:** config `Chronos Command` | display **CHRONOS COMMAND** (CSS uppercase only) | Weierworks Technologies, LLC | logo: Branding & Media.
Do **not** set `APP_NAME` to all-caps in Python — auth/logic stay Title Case string; paint via `gui/theme.py` brand classes.

**Simulator / staffing (still binding):**
- UI: `gui/pages/simulator/page.py` | engine `simulator.py` | `staffing_optimizer` for multi-block
- No invent constraints; OFF days OFF unless opt-in; user numbers **8h / ~2008h / 6-2,5-3**
- Sensitivity **cheap by default** (`logic/sim_product_pack.py`); deep only if asked

**Also hot (2026-07-17 — always-on remote UAT · live SMS deferred):**
- **Always-on remote UAT:** Task `ChronosAlwaysOnUAT` · `Install Always-On UAT.bat` · supervisor `scripts/always_on_uat.ps1`
- Public URL: `logs/remote_uat_url.txt` · card `logs/remote_uat_live.txt` · lab DB `lab_data/virtual_uat.db`
- UAT full product: `SCHEDULER_UAT_LAB=1` · login one-click admin · `/uat` hub · `logic/uat_lab.py`
- Code saves under gui/logic auto-restart Chronos (tunnel stays when healthy) · testers Ctrl+F5
- **One Chronos only** on :8080 — do not start a second server over always-on
- Brand: config `Chronos Command` · display CHRONOS COMMAND CSS only
- Station/fatigue/ops depth landed · notify **file sink** (live carrier deferred)
- E2E: `chronos-e2e --quick` against existing :8080 · Doc: `docs/VIRTUAL_UAT.md` · Cloud: `docs/deploy/CLOUD_VM.md`
- Open residual: **live SMS/email** · LDAP AD IT · optional named CF tunnel for fixed URL
- Last ship: `verify --tier check` + `honest_gate: true` — re-run after product edits

## Session brief (auto-read)
**Must obey** `logs/NEXT_SESSION_BRIEF.md` - last landings, open residuals, proof commands.
Handoff head: `docs/HANDOFF.md` section NEXT SESSION. Start pack: `docs/NEXT_AGENT_PROMPT.md`.

Generated: {ts}
Kit: `logs/agent_kit/latest.md` | Pack: `logs/agent_pack/latest.md` | Trust: `docs/AGENT_TRUST_AND_MISTAKES.md`
"""


def _is_myproject_workspace() -> bool:
    if os.environ.get("SCHEDULER_FORCE_BOOTSTRAP", "").strip() in ("1", "true", "yes"):
        return True
    markers = (
        os.environ.get("GROK_WORKSPACE_ROOT", ""),
        os.environ.get("CLAUDE_PROJECT_DIR", ""),
        os.getcwd(),
    )
    root_s = str(ROOT).lower().replace("/", "\\")
    for m in markers:
        if not m:
            continue
        p = str(Path(m).resolve()).lower().replace("/", "\\")
        if p == root_s or p.startswith(root_s + "\\"):
            return True
        if "myproject" in p and "myproject" in root_s:
            # same leaf name under users path
            if Path(m).resolve().name.lower() == "myproject":
                return True
    return False


def run_bootstrap(*, quiet: bool = True) -> int:
    if not _is_myproject_workspace():
        if not quiet:
            print("session_auto_bootstrap: skip (not MyProject workspace)")
        return 0

    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    slice_id = os.environ.get("SCHEDULER_SLICE", "").strip() or "general"
    task = os.environ.get("SCHEDULER_AGENT_TASK", "").strip() or "Session auto-bootstrap — Chronos token-min"

    # Soft gates (never fail session open)
    try:
        from scripts.agent_gates import run_agent_gates

        run_agent_gates(
            source="session-auto",
            command="SessionStart",
            quiet=True,
            force=True,
            debounce_sec=0,
        )
    except Exception:
        pass

    try:
        from scripts.agent_kit import run_agent_kit

        run_agent_kit(slice_id=slice_id, task=task, quiet=True)
    except Exception as exc:
        if not quiet:
            print(f"agent-kit failed: {exc}")

    try:
        from scripts.agent_pack import run_agent_pack

        run_agent_pack(task=task, slice_id=slice_id, quiet=True)
    except Exception:
        pass

    try:
        from scripts.context_window import set_task

        set_task(task)
    except Exception:
        pass

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    CONTRACT.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT.write_text(CONTRACT_BODY.format(ts=ts), encoding="utf-8")

    if not quiet:
        print(f"session_auto_bootstrap: kit={KIT} contract={CONTRACT}")
    return 0


def cursor_session_start_json() -> dict:
    """Cursor-compatible SessionStart stdout payload (if host honors it)."""
    pack_est = 0
    if PACK.is_file():
        pack_est = max(1, len(PACK.read_text(encoding="utf-8", errors="replace")) // 4)
    context = (
        f"SESSION CONTRACT ACTIVE (auto).\n"
        f"Obey @AGENTS.md | @logs/SESSION_CONTRACT.md | @logs/agent_pack/latest.md (~{pack_est}t).\n"
        f"TRUST/MISTAKES (binding): @docs/AGENT_TRUST_AND_MISTAKES.md\n"
        f"LAST LANDINGS + RESIDUALS (binding): @logs/NEXT_SESSION_BRIEF.md | @docs/HANDOFF.md NEXT SESSION\n"
        "Never claim fixed without proving user scenario. Unit green != UI works. No half-jobs.\n"
        "Caveman. route-task once. Max 1 skill. No archive skills. No subagents for gates.\n"
        "Sufficiency: stop when confident; no whole-repo reads.\n"
        "No graphify/OSS/vision unless user asks. Ship only with check + honest_gate.\n"
        "Brand: config Chronos Command | display CHRONOS COMMAND (CSS only) | Weierworks | logo via Branding & Media.\n"
        "Never uppercase APP_NAME in Python; brand classes in gui/theme.py. Hard-refresh after CSS.\n"
        "Simulator: last-saved constraints only; multi-block in optimizer; 8h/2008h first; sensitivity cheap default.\n"
        "Landed: ops depth residuals (station board · fatigue rank · bulk station · LDAP IT export · e2e --quick) + brand + product complete; check-green.\n"
        "Open residual: live SMS/email *delivery* only (user deferred) — needs real Twilio/SMTP. LDAP production_ready needs AD+IT.\n"
        "Do not claim live carrier notify or LDAP production without dept proof.\n"
        "Live e2e: one Chronos only · prefer chronos-e2e --quick. Restart Chronos after pulls. Ship: check + honest_gate.\n"
        "Proof cmds: residual_proof_smoke · deeper_ui_click_paths · chronos_e2e --quick · tests.test_product_hosting_p0."
    )
    return {
        "continue": True,
        "additional_context": context,
        "agent_message": context,
    }


def main() -> int:
    # Consume stdin (hook payload) if present
    if not sys.stdin.isatty():
        try:
            json.load(sys.stdin)
        except Exception:
            pass

    code = run_bootstrap(quiet=True)

    # Cursor / some hosts read additional_context from SessionStart stdout
    event = (os.environ.get("GROK_HOOK_EVENT") or "").lower()
    if event in ("", "session_start", "sessionstart") or os.environ.get("CURSOR_TRACE_ID"):
        print(json.dumps(cursor_session_start_json()))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
