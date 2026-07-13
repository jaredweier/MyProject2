"""Structured JSON output — fixed fields only, no prose."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence

# Batch result fields per task (flattened into each output element)
BATCH_FIELDS: Dict[str, Sequence[str]] = {
    "classification": ("complexity", "slice_id", "skill"),
    "extraction": ("valid_dates", "paths", "slice_ids", "tokens"),
    "summarization": ("preview", "tokens", "lines"),
    "scoring": ("score", "complexity", "tokens"),
    "validation": ("valid", "checks"),
}

ROUTE_FIELDS = (
    "tier",
    "cost",
    "slice",
    "skill",
    "cursor",
    "agent",
    "model",
    "ui_lane",
    "verify",
    "agents",
    "external",
    "oss_searches",
    "oss_actions",
)

CTX_FIELDS = ("turn", "task", "tokens", "threshold", "ephemeral", "decisions", "summary")


def dump_json(data: Any, *, compact: bool = True) -> str:
    if compact:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(data, indent=2, ensure_ascii=False)


def _pick(src: dict, fields: Sequence[str]) -> dict:
    return {k: src[k] for k in fields if k in src}


def shape_batch_row(task: str, row: dict, *, full: bool = False) -> dict:
    """One index-aligned batch element with schema fields only."""
    base: Dict[str, Any] = {"index": row.get("index", 0), "ok": row.get("ok", False)}
    if not row.get("ok"):
        base["error"] = row.get("error", "failed")
        return base
    if full:
        base["result"] = row.get("result", {})
        return base

    result = row.get("result") or {}
    fields = BATCH_FIELDS.get(task, ())
    if task == "validation":
        if "checks" in result:
            base["valid"] = all(c.get("ok") for c in result["checks"])
            base["checks"] = [{"field": c.get("field"), "ok": c.get("ok")} for c in result.get("checks", [])]
        else:
            base["valid"] = result.get("valid", True)
            if result.get("message"):
                base["message"] = result["message"]
        return base

    base.update(_pick(result, fields))
    return base


def shape_batch_results(task: str, rows: List[dict], *, full: bool = False) -> List[dict]:
    return [shape_batch_row(task, row, full=full) for row in rows]


def shape_route(rec: Any) -> dict:
    verify = rec.verify[0] if getattr(rec, "verify", None) else "python dev.py verify --tier fast"
    skill = rec.skill.split("/")[-2] if "/" in rec.skill else rec.skill
    return {
        "tier": getattr(rec, "complexity", ""),
        "cost": getattr(rec, "cost_tier", ""),
        "slice": getattr(rec, "slice_id", ""),
        "skill": skill,
        "cursor": getattr(rec, "cursor_mode", ""),
        "agent": getattr(rec, "primary_agent", "") or getattr(rec, "opencode_agent", ""),
        "model": getattr(rec, "preferred_model", getattr(rec, "model_tier", "")),
        "ui_lane": getattr(rec, "ui_lane", "none"),
        "verify": verify,
        "agents": list(getattr(rec, "agents", []) or [])[:8],
        "external": list(getattr(rec, "external_agents", []) or [])[:6],
        "oss_searches": list(getattr(rec, "oss_searches", []) or [])[:6],
        "oss_actions": list(getattr(rec, "oss_actions", []) or [])[:6],
    }


def shape_context_status(state: dict, *, summary_path: str = "") -> dict:
    tools = state.get("tool_results", [])
    ephemeral = sum(1 for t in tools if t.get("ephemeral") and not t.get("keep"))
    out = {
        "turn": state.get("turn", 0),
        "task": state.get("current_task") or "",
        "tokens": int(state.get("tokens_since_summary", 0)),
        "threshold": int(state.get("summary_threshold", 6000)),
        "ephemeral": ephemeral,
        "decisions": len(state.get("decisions", [])),
    }
    if summary_path:
        out["summary"] = summary_path
    return out
