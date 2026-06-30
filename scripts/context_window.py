"""Context window management — summarize at 6k tokens, prune ephemeral tool results."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from scripts.token_estimate import estimate_tokens, file_stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CTX_DIR = os.path.join(ROOT, "logs", "context_window")
STATE_PATH = os.path.join(CTX_DIR, "state.json")
SUMMARY_PATH = os.path.join(CTX_DIR, "latest_summary.md")

SUMMARY_THRESHOLD = 6000
EPHEMERAL_TTL_TURNS = 2

DEFAULT_STATE: Dict[str, Any] = {
    "turn": 0,
    "tokens_since_summary": 0,
    "summary_threshold": SUMMARY_THRESHOLD,
    "ephemeral_ttl_turns": EPHEMERAL_TTL_TURNS,
    "current_task": "",
    "decisions": [],
    "tool_results": [],
    "archived_tools": [],
    "summaries": [],
    "updated": "",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state() -> Dict[str, Any]:
    if not os.path.isfile(STATE_PATH):
        return dict(DEFAULT_STATE)
    try:
        with open(STATE_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_STATE)
    merged = dict(DEFAULT_STATE)
    merged.update(data)
    return merged


def save_state(state: Dict[str, Any]) -> None:
    state["updated"] = _utc_now()
    os.makedirs(CTX_DIR, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)


def set_task(task: str) -> None:
    state = load_state()
    text = (task or "").strip()
    if text:
        state["current_task"] = text[:500]
        save_state(state)


def add_decision(text: str, *, turn: Optional[int] = None) -> None:
    text = (text or "").strip()
    if not text:
        return
    state = load_state()
    state.setdefault("decisions", []).append(
        {
            "turn": turn if turn is not None else state.get("turn", 0),
            "text": text[:400],
        }
    )
    save_state(state)


def register_tool(
    tool_id: str,
    *,
    tokens: int = 0,
    ephemeral: bool = True,
    keep: bool = False,
    summary: str = "",
    source: str = "",
) -> Dict[str, Any]:
    state = load_state()
    entry = {
        "id": tool_id[:120],
        "turn": state.get("turn", 0),
        "tokens": max(0, int(tokens)),
        "ephemeral": ephemeral and not keep,
        "keep": keep,
        "referenced": keep,
        "summary": (summary or tool_id)[:300],
        "source": source[:80],
    }
    tools: List[dict] = state.setdefault("tool_results", [])
    tools = [t for t in tools if t.get("id") != entry["id"]]
    tools.append(entry)
    state["tool_results"] = tools[-40:]
    state["tokens_since_summary"] = int(state.get("tokens_since_summary", 0)) + entry["tokens"]
    save_state(state)
    maybe_summarize(state)
    return entry


def register_tool_from_read(rel_path: str, *, root: str = ROOT) -> None:
    rel = rel_path.replace("\\", "/").lstrip("./")
    stats = file_stats(rel)
    tokens = stats.get("tokens", 0) if stats.get("exists") else estimate_tokens(rel)
    register_tool(
        f"read:{rel}",
        tokens=tokens,
        ephemeral=True,
        summary=f"read {rel}",
        source="read_guard",
    )


def mark_referenced(tool_id: str) -> bool:
    state = load_state()
    found = False
    for tool in state.get("tool_results", []):
        if tool.get("id") == tool_id:
            tool["referenced"] = True
            tool["keep"] = True
            tool["ephemeral"] = False
            found = True
    if found:
        save_state(state)
    return found


def mark_keep(tool_id: str) -> bool:
    return mark_referenced(tool_id)


def _one_line_tool(tool: dict) -> str:
    return f"{tool.get('id', '?')}: {tool.get('summary', '')} (~{tool.get('tokens', 0)}t)"


def prune_ephemeral(state: Optional[Dict[str, Any]] = None) -> int:
    state = state or load_state()
    turn = int(state.get("turn", 0))
    ttl = int(state.get("ephemeral_ttl_turns", EPHEMERAL_TTL_TURNS))
    kept: List[dict] = []
    archived: List[dict] = list(state.get("archived_tools", []))
    pruned = 0

    for tool in state.get("tool_results", []):
        age = turn - int(tool.get("turn", turn))
        drop = tool.get("ephemeral") and not tool.get("keep") and not tool.get("referenced") and age >= ttl
        if drop:
            archived.append(
                {
                    "id": tool.get("id"),
                    "summary": tool.get("summary") or _one_line_tool(tool),
                    "turn": tool.get("turn"),
                    "pruned_turn": turn,
                }
            )
            pruned += 1
        else:
            kept.append(tool)

    state["tool_results"] = kept
    state["archived_tools"] = archived[-80:]
    save_state(state)
    return pruned


def build_summary(state: Dict[str, Any]) -> str:
    lines = [
        "# Context checkpoint (replaces pruned history)",
        f"Generated: {_utc_now()}",
        f"Turn: {state.get('turn', 0)} · tokens summarized: {state.get('tokens_since_summary', 0)}",
        "",
        "## Keep",
        f"**Task:** {state.get('current_task') or '(unset)'}",
        "**Policy:** docs/AGENT_STABLE.md · **Resume:** logs/agent_pack/latest.md",
        "",
        "## Decisions",
    ]
    decisions = state.get("decisions", [])
    if decisions:
        for d in decisions[-12:]:
            lines.append(f"- [t{d.get('turn', '?')}] {d.get('text', '')}")
    else:
        lines.append('- (none recorded — use `python dev.py context-window decision "…"`)')

    recent = state.get("tool_results", [])
    if recent:
        lines.extend(["", "## Recent tool results (still active)"])
        for tool in recent[-6:]:
            flag = "keep" if tool.get("keep") or tool.get("referenced") else "ephemeral"
            lines.append(f"- [{flag}] {_one_line_tool(tool)}")

    archived = state.get("archived_tools", [])
    if archived:
        lines.extend(["", "## Pruned tool results (one-line)"])
        for tool in archived[-15:]:
            lines.append(f"- {tool.get('summary', tool.get('id', '?'))}")

    prior = state.get("summaries", [])
    if prior:
        lines.extend(["", "## Prior checkpoints"])
        for item in prior[-3:]:
            lines.append(f"- turn {item.get('turn', '?')}: {item.get('text', '')[:160]}")

    lines.extend(
        [
            "",
            "## Agent rule",
            "Ephemeral tool output drops after 2 turns unless `keep` or `referenced`.",
            f"Next summary at {state.get('summary_threshold', SUMMARY_THRESHOLD)} tokens since last checkpoint.",
        ]
    )
    return "\n".join(lines)


def apply_summary(state: Dict[str, Any]) -> str:
    text = build_summary(state)
    os.makedirs(CTX_DIR, exist_ok=True)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as fh:
        fh.write(text)

    checkpoint = {
        "turn": state.get("turn", 0),
        "tokens": state.get("tokens_since_summary", 0),
        "text": f"Checkpoint at turn {state.get('turn')}: {state.get('current_task', '')[:120]}",
        "created": _utc_now(),
    }
    state.setdefault("summaries", []).append(checkpoint)
    state["summaries"] = state["summaries"][-20:]
    state["tokens_since_summary"] = 0

    # Drop stale ephemeral tools; keep decisions, task, kept/referenced tools
    active = []
    for tool in state.get("tool_results", []):
        if tool.get("keep") or tool.get("referenced") or not tool.get("ephemeral"):
            active.append(tool)
        else:
            state.setdefault("archived_tools", []).append(
                {
                    "id": tool.get("id"),
                    "summary": tool.get("summary") or _one_line_tool(tool),
                    "turn": tool.get("turn"),
                    "pruned_turn": state.get("turn", 0),
                    "reason": "summary_checkpoint",
                }
            )
    state["tool_results"] = active[-20:]
    state["archived_tools"] = state.get("archived_tools", [])[-80:]
    save_state(state)
    return text


def maybe_summarize(state: Optional[Dict[str, Any]] = None) -> bool:
    state = state or load_state()
    threshold = int(state.get("summary_threshold", SUMMARY_THRESHOLD))
    if int(state.get("tokens_since_summary", 0)) < threshold:
        return False
    apply_summary(state)
    return True


def advance_turn(*, tokens: int = 0) -> Dict[str, Any]:
    state = load_state()
    state["turn"] = int(state.get("turn", 0)) + 1
    if tokens > 0:
        state["tokens_since_summary"] = int(state.get("tokens_since_summary", 0)) + tokens
    save_state(state)
    pruned = prune_ephemeral(state)
    summarized = maybe_summarize(load_state())
    return {
        "turn": state["turn"],
        "pruned": pruned,
        "summarized": summarized,
        "tokens_since_summary": load_state().get("tokens_since_summary", 0),
    }


def status_json() -> dict:
    state = load_state()
    summary = SUMMARY_PATH if os.path.isfile(SUMMARY_PATH) else ""
    from scripts.structured_output import shape_context_status

    return shape_context_status(state, summary_path=summary)


def status_text() -> str:
    state = load_state()
    threshold = int(state.get("summary_threshold", SUMMARY_THRESHOLD))
    tokens = int(state.get("tokens_since_summary", 0))
    tools = state.get("tool_results", [])
    ephemeral = sum(1 for t in tools if t.get("ephemeral") and not t.get("keep"))
    lines = [
        "Context window status",
        f"  turn: {state.get('turn', 0)}",
        f"  task: {state.get('current_task') or '(unset)'}",
        f"  tokens since summary: {tokens}/{threshold}",
        f"  active tools: {len(tools)} ({ephemeral} ephemeral)",
        f"  decisions: {len(state.get('decisions', []))}",
        f"  summary: {SUMMARY_PATH if os.path.isfile(SUMMARY_PATH) else '(none yet)'}",
    ]
    if tokens >= threshold * 0.8:
        lines.append("  ⚠ nearing summary threshold — surface decisions explicitly")
    return "\n".join(lines)


def agent_hint() -> str:
    state = load_state()
    tokens = int(state.get("tokens_since_summary", 0))
    threshold = int(state.get("summary_threshold", SUMMARY_THRESHOLD))
    parts = [f"context {tokens}/{threshold}t"]
    if os.path.isfile(SUMMARY_PATH):
        parts.append("@logs/context_window/latest_summary.md")
    return " · ".join(parts)


def run_context_window(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Context window: summarize @6k, prune ephemeral tools")
    sub = parser.add_subparsers(dest="action")

    status_p = sub.add_parser("status", help="Show turn, tokens, pruning state")
    status_p.add_argument("--json", action="store_true", help="Structured JSON only")
    sub.add_parser("prune", help="Prune ephemeral tools past TTL")
    sub.add_parser("summarize", help="Force checkpoint summary now")

    turn_p = sub.add_parser("turn", help="Advance turn (Cursor stop hook)")
    turn_p.add_argument("--tokens", type=int, default=0)

    task_p = sub.add_parser("task", help="Set current task (always kept)")
    task_p.add_argument("text", nargs="+")

    dec_p = sub.add_parser("decision", help="Record explicit conclusion (always kept)")
    dec_p.add_argument("text", nargs="+")

    tool_p = sub.add_parser("tool", help="Register tool result")
    tool_p.add_argument("tool_id")
    tool_p.add_argument("--tokens", type=int, default=0)
    tool_p.add_argument("--summary", default="")
    tool_p.add_argument("--keep", action="store_true", help="Not ephemeral — keep in context")
    tool_p.add_argument("--ephemeral", action="store_true", default=True)

    keep_p = sub.add_parser("keep", help="Mark tool result as referenced/kept")
    keep_p.add_argument("tool_id")

    record_p = sub.add_parser("record", help="Register tool output text; ephemeral by default")
    record_p.add_argument("--id", required=True)
    record_p.add_argument("--text", default="")
    record_p.add_argument("--keep", action="store_true")

    args = parser.parse_args(argv)
    action = args.action or "status"

    if action == "status":
        if getattr(args, "json", False):
            from scripts.structured_output import dump_json

            print(dump_json(status_json()))
        else:
            print(status_text())
        return 0
    if action == "prune":
        n = prune_ephemeral()
        print(f"context-window: pruned {n} ephemeral tool result(s)")
        return 0
    if action == "summarize":
        text = apply_summary(load_state())
        print(text)
        print("=" * 60)
        print(f"context-window: wrote {SUMMARY_PATH}")
        return 0
    if action == "turn":
        info = advance_turn(tokens=max(0, args.tokens))
        print(
            f"context-window: turn={info['turn']} pruned={info['pruned']} "
            f"summarized={info['summarized']} tokens={info['tokens_since_summary']}"
        )
        return 0
    if action == "task":
        set_task(" ".join(args.text))
        print(f"context-window: task set ({' '.join(args.text)[:80]})")
        return 0
    if action == "decision":
        add_decision(" ".join(args.text))
        print("context-window: decision recorded")
        return 0
    if action == "tool":
        ephemeral = not args.keep
        register_tool(
            args.tool_id,
            tokens=args.tokens,
            ephemeral=ephemeral,
            keep=args.keep,
            summary=args.summary or args.tool_id,
            source="cli",
        )
        print(f"context-window: registered {args.tool_id} ({'keep' if args.keep else 'ephemeral'})")
        return 0
    if action == "keep":
        ok = mark_keep(args.tool_id)
        print(f"context-window: {'kept' if ok else 'not found'} {args.tool_id}")
        return 0 if ok else 1
    if action == "record":
        tokens = estimate_tokens(args.text)
        register_tool(
            args.id,
            tokens=tokens,
            ephemeral=not args.keep,
            keep=args.keep,
            summary=args.text[:200] or args.id,
            source="record",
        )
        print(f"context-window: recorded ~{tokens} tokens ({'keep' if args.keep else 'ephemeral'})")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    import sys

    raise SystemExit(run_context_window(sys.argv[1:]))
