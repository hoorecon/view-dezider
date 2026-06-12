"""AI Auto-Tune for Import-URL prompts — the closing of the learning loop.

The AI reads FAILING runs per page type (errors, hint-pass failures, 👎
verdicts) from `url_import_runs`, diagnoses the pattern and proposes a revised
PAGE-TYPE GUIDANCE prompt block. A super-admin reviews and approves/rejects;
approval ACTIVATES the override (db.url_prompt_overrides), which
`url_detail.get_active_guidance()` injects into every subsequent extraction —
no deploy needed. Revert restores the built-in default at any time.

Collections:
  prompt_tuning_suggestions — {id, ts, page_type, status proposed|approved|rejected,
      rationale, expected_impact, current_guidance, proposed_guidance,
      evidence {run_ids, failing_runs, window_days}, created_by, decided_by, decided_at}
  url_prompt_overrides — {key: <page_type>, guidance, suggestion_id, updated_by, updated_at}
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from core.database import db
from core.ai_metering import metered_chat
from core.url_detail import PAGE_TYPE_GUIDANCE
from core.url_pagetype import PAGE_TYPES

logger = logging.getLogger(__name__)

MAX_EVIDENCE_RUNS = 6
RAW_EXCERPT = 1000

TUNER_SYSTEM = """You are a senior prompt engineer for a web-page → decision-matrix extraction pipeline.
You receive: (a) the CURRENT page-type guidance block appended to the extraction system prompt for ONE page type, and (b) EVIDENCE — recent runs of that page type that FAILED (pipeline errors, mismatches against user-verified page facts, or explicit user 👎 verdicts).
Diagnose the failure pattern and propose a CONCRETE revision of the guidance block.

Constraints for the proposed block:
- Keep the exact opening convention: it MUST start with "\\n\\nPAGE-TYPE GUIDANCE —".
- Keep it under 1200 characters; bullet style with "- " lines, same voice as the current block.
- Only change what the evidence justifies; preserve rules that are not implicated.
- Never contradict the core extraction schema (groups/factors/items, "<group>::<factor>" mapping, page_type values "detail"/"comparison").

Reply ONLY compact JSON (no prose, no markdown fences):
{"rationale":"<what is failing and why, grounded in the evidence>",
 "expected_impact":"<which metrics should improve: hint-pass / 👎 rate / error rate>",
 "proposed_guidance":"<the full revised block>"}"""


def _now():
    return datetime.now(timezone.utc)


def _normalize_guidance(text: str) -> str:
    """Exactly ONE '\\n\\nPAGE-TYPE GUIDANCE — ' header, regardless of how the
    LLM formatted its proposal (it often repeats or omits the header)."""
    body = re.sub(r"^[\s\-—:]*?(PAGE-TYPE GUIDANCE\s*[—\-:]*\s*)+", "", text.strip(),
                  flags=re.IGNORECASE)
    return "\n\nPAGE-TYPE GUIDANCE — " + body.strip()


async def get_override(page_type: str) -> Optional[Dict[str, Any]]:
    return await db.url_prompt_overrides.find_one({"key": page_type}, {"_id": 0})


async def list_overrides() -> List[Dict[str, Any]]:
    return await db.url_prompt_overrides.find({}, {"_id": 0}).to_list(20)


async def _failing_runs(page_type: str, days: int) -> List[Dict[str, Any]]:
    q = {
        "page_type": page_type,
        "ts": {"$gte": _now() - timedelta(days=days)},
        "$or": [{"status": "error"}, {"hint_pass": False}, {"feedback": "down"}],
    }
    return await (db.url_import_runs
                  .find(q, {"_id": 0, "id": 1, "url": 1, "status": 1, "error": 1,
                            "hints": 1, "hint_warnings": 1, "feedback": 1,
                            "ai_retry_used": 1, "route": 1, "factors_added": 1,
                            "options_added": 1, "ai_raw_response": 1})
                  .sort("ts", -1).limit(MAX_EVIDENCE_RUNS).to_list(MAX_EVIDENCE_RUNS))


def _evidence_text(runs: List[Dict[str, Any]]) -> str:
    blocks = []
    for i, r in enumerate(runs, 1):
        blocks.append(
            f"RUN {i}: url={r.get('url')}\n"
            f"  status={r.get('status')} route={r.get('route')} error={r.get('error') or '-'}\n"
            f"  user_hints={json.dumps(r.get('hints') or {})}\n"
            f"  hint_warnings={r.get('hint_warnings') or []}\n"
            f"  user_verdict={r.get('feedback') or '-'} retry_used={r.get('ai_retry_used')}\n"
            f"  outcome={r.get('factors_added')}F/{r.get('options_added')}O\n"
            f"  raw_llm_response_excerpt={(r.get('ai_raw_response') or '')[:RAW_EXCERPT]!r}")
    return "\n".join(blocks)


async def generate_suggestions(admin_id: str, *, days: int = 30,
                               page_type: Optional[str] = None) -> Dict[str, Any]:
    """Analyse failing runs per page type and store 'proposed' suggestions.
    Skips page types with no failing runs or with a suggestion already pending."""
    targets = [page_type] if page_type else list(PAGE_TYPES)
    created, skipped = [], []
    for pt in targets:
        pending = await db.prompt_tuning_suggestions.find_one(
            {"page_type": pt, "status": "proposed"}, {"_id": 0, "id": 1})
        if pending:
            skipped.append({"page_type": pt, "reason": "suggestion already pending review"})
            continue
        runs = await _failing_runs(pt, days)
        if not runs:
            skipped.append({"page_type": pt, "reason": "no failing runs in window"})
            continue
        override = await get_override(pt)
        current = (override or {}).get("guidance") or PAGE_TYPE_GUIDANCE.get(pt, "")
        prompt = (f"PAGE TYPE: {pt}\n\nCURRENT GUIDANCE BLOCK:\n{current or '(none — empty block)'}\n\n"
                  f"EVIDENCE — {len(runs)} failing run(s) from the last {days} days:\n"
                  + _evidence_text(runs))
        try:
            out = await metered_chat(admin_id, system_message=TUNER_SYSTEM, prompt=prompt,
                                     feature="url_prompt_tuning", session_prefix="urltune",
                                     tier="precise")
            m = re.search(r"\{.*\}", out or "", re.S)
            data = json.loads(m.group(0)) if m else {}
            proposed = str(data.get("proposed_guidance") or "").strip()
            if not proposed:
                raise ValueError("empty proposed_guidance")
            proposed = _normalize_guidance(proposed)
            sug = {
                "id": uuid.uuid4().hex, "ts": _now(), "page_type": pt, "status": "proposed",
                "rationale": str(data.get("rationale") or "")[:2000],
                "expected_impact": str(data.get("expected_impact") or "")[:600],
                "current_guidance": current, "proposed_guidance": proposed[:4000],
                "evidence": {"run_ids": [r["id"] for r in runs],
                             "failing_runs": len(runs), "window_days": days},
                "created_by": admin_id, "decided_by": None, "decided_at": None,
            }
            await db.prompt_tuning_suggestions.insert_one(sug)
            sug.pop("_id", None)
            created.append(sug)
        except Exception as e:  # noqa: BLE001 — continue with other page types
            logger.warning("auto-tune generation failed for %s: %s: %s",
                           pt, type(e).__name__, str(e)[:150])
            skipped.append({"page_type": pt, "reason": f"AI generation failed: {str(e)[:120]}"})
    return {"created": created, "skipped": skipped}


async def list_suggestions(limit: int = 30) -> List[Dict[str, Any]]:
    return await (db.prompt_tuning_suggestions.find({}, {"_id": 0})
                  .sort("ts", -1).limit(min(limit, 100)).to_list(100))


async def decide(suggestion_id: str, admin_id: str, *, approve: bool) -> Dict[str, Any]:
    """Approve → ACTIVATE the override for that page type. Reject → archive."""
    sug = await db.prompt_tuning_suggestions.find_one({"id": suggestion_id}, {"_id": 0})
    if not sug:
        raise KeyError("Suggestion not found")
    if sug["status"] != "proposed":
        raise ValueError(f"Suggestion already {sug['status']}")
    status = "approved" if approve else "rejected"
    await db.prompt_tuning_suggestions.update_one(
        {"id": suggestion_id},
        {"$set": {"status": status, "decided_by": admin_id, "decided_at": _now()}})
    if approve:
        await db.url_prompt_overrides.update_one(
            {"key": sug["page_type"]},
            {"$set": {"key": sug["page_type"], "guidance": sug["proposed_guidance"],
                      "suggestion_id": suggestion_id,
                      "updated_by": admin_id, "updated_at": _now()}},
            upsert=True)
    sug.update({"status": status, "decided_by": admin_id})
    return sug


async def revert_override(page_type: str, admin_id: str) -> bool:
    """Remove an active override — extraction falls back to the built-in block."""
    r = await db.url_prompt_overrides.delete_one({"key": page_type})
    if r.deleted_count:
        logger.info("prompt override for %s reverted to default by %s", page_type, admin_id)
    return bool(r.deleted_count)
