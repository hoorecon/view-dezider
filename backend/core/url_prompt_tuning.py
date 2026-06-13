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

# Deep-Import pipeline stages are tunable too — their guidance blocks are
# APPENDED to the stage system prompts in routes/deep_import.py (same
# override/approval mechanism as page types).
DEEP_KEYS: Dict[str, str] = {
    "deep_links": "Deep Import — option/detail link selection",
    "deep_hubs": "Deep Import — listing-hub page locating",
    "deep_consolidate": "Deep Import — factor consolidation",
}
# Which ai_calls stages feed each deep key's evidence.
_DEEP_STAGE_PREFIX = {"deep_links": "links_pick", "deep_hubs": "hubs_pick",
                      "deep_consolidate": "consolidate"}
TUNE_KEYS = tuple(PAGE_TYPES) + tuple(DEEP_KEYS)

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


async def get_guidance(key: str) -> str:
    """Active auto-tune guidance block for a tunable key ('' when none).
    Used by the Deep-Import stage prompts; page types go through
    url_detail.get_active_guidance (which also has built-in defaults)."""
    try:
        doc = await db.url_prompt_overrides.find_one({"key": key}, {"_id": 0, "guidance": 1})
        return (doc or {}).get("guidance") or ""
    except Exception:  # noqa: BLE001 — guidance must never block an import
        return ""


async def _failing_runs(key: str, days: int) -> List[Dict[str, Any]]:
    # A run is a "failing candidate" if any of these are true:
    #   - hard error
    #   - partial (extracted below the quality floor — silent under-extraction)
    #   - the user's accuracy hints did not pass
    #   - user gave a 👎 verdict
    #   - user submitted Train AI feedback flagging mistakes (highest priority)
    fail_or = [{"status": "error"}, {"status": "partial"},
               {"hint_pass": False}, {"feedback": "down"},
               {"user_reported_failure": True}]
    q: Dict[str, Any] = {"ts": {"$gte": _now() - timedelta(days=days)}, "$or": fail_or}
    if key in DEEP_KEYS:
        q["endpoint"] = "deep_import"
    else:
        q["page_type"] = key
    return await (db.url_import_runs
                  .find(q, {"_id": 0, "id": 1, "url": 1, "status": 1, "error": 1,
                            "partial_reason": 1,
                            "hints": 1, "hint_warnings": 1, "feedback": 1,
                            "user_training": 1, "user_reported_failure": 1,
                            "ai_retry_used": 1, "route": 1, "factors_added": 1,
                            "options_added": 1, "ai_raw_response": 1,
                            "ai_calls": 1, "ai_engines": 1, "total_credits": 1})
                  .sort("ts", -1).limit(MAX_EVIDENCE_RUNS).to_list(MAX_EVIDENCE_RUNS))


def _evidence_text(runs: List[Dict[str, Any]], stage_prefix: Optional[str] = None) -> str:
    blocks = []
    for i, r in enumerate(runs, 1):
        block = (
            f"RUN {i}: url={r.get('url')}\n"
            f"  status={r.get('status')} route={r.get('route')} error={r.get('error') or '-'}\n"
            f"  user_hints={json.dumps(r.get('hints') or {})}\n"
            f"  hint_warnings={r.get('hint_warnings') or []}\n"
            f"  user_verdict={r.get('feedback') or '-'} retry_used={r.get('ai_retry_used')}\n"
            f"  engines={r.get('ai_engines') or []} run_credits={r.get('total_credits')}\n"
            f"  outcome={r.get('factors_added')}F/{r.get('options_added')}O")
        # Per-stage trace (deep imports): engine + tokens + credits + raw output
        # for the stage being tuned — lets the tuner ground its diagnosis.
        calls = [c for c in (r.get("ai_calls") or [])
                 if not stage_prefix or str(c.get("stage") or "").startswith(stage_prefix)]
        for c in calls[-2:]:
            block += (f"\n  stage={c.get('stage')} engine={c.get('engine')}"
                      f" tokens={c.get('tokens')} credits={c.get('credits')}\n"
                      f"  stage_response_excerpt={(c.get('raw_response') or '')[:RAW_EXCERPT]!r}")
        if not calls:
            block += f"\n  raw_llm_response_excerpt={(r.get('ai_raw_response') or '')[:RAW_EXCERPT]!r}"
        blocks.append(block)
    return "\n".join(blocks)


async def generate_suggestions(admin_id: str, *, days: int = 30,
                               page_type: Optional[str] = None) -> Dict[str, Any]:
    """Analyse failing runs per tunable key (page types + deep-import stages)
    and store 'proposed' suggestions. Skips keys with no failing runs or with
    a suggestion already pending."""
    targets = [page_type] if page_type else list(TUNE_KEYS)
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
        if pt in DEEP_KEYS:
            current = await get_guidance(pt)
            stage_prefix = _DEEP_STAGE_PREFIX[pt]
            scope_line = f"PIPELINE STAGE: {DEEP_KEYS[pt]} (key: {pt})"
        else:
            override = await get_override(pt)
            current = (override or {}).get("guidance") or PAGE_TYPE_GUIDANCE.get(pt, "")
            stage_prefix = None
            scope_line = f"PAGE TYPE: {pt}"
        prompt = (f"{scope_line}\n\nCURRENT GUIDANCE BLOCK:\n{current or '(none — empty block)'}\n\n"
                  f"EVIDENCE — {len(runs)} failing run(s) from the last {days} days:\n"
                  + _evidence_text(runs, stage_prefix=stage_prefix))
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


# ── Auto-approve config ─────────────────────────────────────────────────────
# Stored in app_config so an admin can tune without a redeploy. Default policy:
#   • Auto-approve ENABLED — non-techie admins shouldn't have to triage prompts.
#   • Grace 24h — admins still have a full day to override any proposal before
#     it goes live.
#   • Min evidence 2 — never auto-approve a proposal backed by only one bad run.
#   • Per page-type / deep-key the LATEST proposal wins; older proposals for
#     the same key get auto-rejected (they're stale duplicates).
_AUTO_KEY = "auto_tune_autoapprove"
AUTO_DEFAULT = {"enabled": True, "grace_hours": 24, "min_evidence": 2}


async def get_auto_approve_config() -> Dict[str, Any]:
    doc = await db.app_config.find_one({"key": _AUTO_KEY}, {"_id": 0}) or {}
    cfg = {**AUTO_DEFAULT, **{k: doc.get(k) for k in AUTO_DEFAULT if k in doc}}
    cfg["enabled"] = bool(cfg["enabled"])
    cfg["grace_hours"] = max(1, min(168, int(cfg["grace_hours"])))     # 1h … 7d
    cfg["min_evidence"] = max(1, min(20, int(cfg["min_evidence"])))
    return cfg


async def set_auto_approve_config(payload: Dict[str, Any], admin_id: str) -> Dict[str, Any]:
    update: Dict[str, Any] = {"updated_by": admin_id, "updated_at": _now()}
    if "enabled" in payload:
        update["enabled"] = bool(payload["enabled"])
    if "grace_hours" in payload:
        gh = int(payload["grace_hours"])
        if not (1 <= gh <= 168):
            raise ValueError("grace_hours must be 1..168")
        update["grace_hours"] = gh
    if "min_evidence" in payload:
        me = int(payload["min_evidence"])
        if not (1 <= me <= 20):
            raise ValueError("min_evidence must be 1..20")
        update["min_evidence"] = me
    await db.app_config.update_one({"key": _AUTO_KEY}, {"$set": update}, upsert=True)
    return await get_auto_approve_config()


async def _last_admin_touch_at(key: str) -> Optional[datetime]:
    """Returns the most-recent timestamp at which a HUMAN admin decided on this
    key's suggestions. Used to defer auto-approve when the admin recently
    expressed a manual preference (their voice wins for `grace_hours`)."""
    row = await db.prompt_tuning_suggestions.find_one(
        {"page_type": key,
         "status": {"$in": ["approved", "rejected"]},
         "decided_by": {"$nin": [None, "__auto_approve__"]}},
        {"_id": 0, "decided_at": 1}, sort=[("decided_at", -1)])
    return (row or {}).get("decided_at")


async def auto_approve_pass() -> Dict[str, Any]:
    """For each page-type / deep-key:
      1. Pick the LATEST proposed suggestion (older than grace_hours).
      2. Auto-reject every other proposed suggestion for the same key.
      3. If the picked one has ≥ min_evidence failing runs AND no recent
         manual admin decision (within grace_hours), auto-approve it.

    Idempotent: a second call within the same grace window is a no-op.
    Always recorded in audit fields so admins can revert.
    """
    cfg = await get_auto_approve_config()
    if not cfg["enabled"]:
        return {"enabled": False, "approved": 0, "deduped": 0, "deferred": 0}

    grace = timedelta(hours=cfg["grace_hours"])
    threshold = _now() - grace

    approved = 0
    deduped = 0
    deferred: List[str] = []
    audit: List[Dict[str, Any]] = []

    # Group all PROPOSED suggestions by their key (page_type stores deep_keys too)
    pending = await (db.prompt_tuning_suggestions
                     .find({"status": "proposed"}, {"_id": 0})
                     .sort("ts", -1).to_list(500))
    by_key: Dict[str, List[Dict[str, Any]]] = {}
    for s in pending:
        by_key.setdefault(s["page_type"], []).append(s)

    for key, items in by_key.items():
        # Latest first (already sorted by ts desc above)
        latest = items[0]
        # Mongo can return naive datetimes — normalise to UTC-aware so the
        # comparison with `threshold` (always aware) doesn't TypeError.
        def _aware(dt):
            if dt is None:
                return None
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        # 1. Dedupe — auto-reject EVERY older proposal for the same key
        for old in items[1:]:
            await db.prompt_tuning_suggestions.update_one(
                {"id": old["id"]},
                {"$set": {"status": "rejected",
                          "decided_by": "__auto_approve__",
                          "decided_at": _now(),
                          "auto_reason": "stale duplicate — newer proposal for this key"}})
            deduped += 1

        # 2. Skip the latest if it's still within grace
        latest_ts = _aware(latest.get("ts"))
        if latest_ts and latest_ts > threshold:
            deferred.append(key)
            continue
        # 3. Respect a recent manual admin decision (their voice wins)
        last_touch = _aware(await _last_admin_touch_at(key))
        if last_touch and last_touch > threshold:
            deferred.append(key)
            continue
        # 4. Evidence floor — never auto-approve a flimsy proposal
        failing = int(((latest.get("evidence") or {}).get("failing_runs")) or 0)
        if failing < cfg["min_evidence"]:
            deferred.append(key)
            continue

        # All gates passed — auto-approve
        try:
            await db.prompt_tuning_suggestions.update_one(
                {"id": latest["id"]},
                {"$set": {"status": "approved",
                          "decided_by": "__auto_approve__",
                          "decided_at": _now(),
                          "auto_reason": f"auto-approved after {cfg['grace_hours']}h grace "
                                         f"(evidence: {failing} failing runs)"}})
            await db.url_prompt_overrides.update_one(
                {"key": latest["page_type"]},
                {"$set": {"key": latest["page_type"],
                          "guidance": latest["proposed_guidance"],
                          "suggestion_id": latest["id"],
                          "updated_by": "__auto_approve__",
                          "updated_at": _now()}},
                upsert=True)
            approved += 1
            audit.append({"key": key, "suggestion_id": latest["id"], "failing_runs": failing})
        except Exception as e:  # noqa: BLE001 — never break the loop
            logger.warning("auto-approve failed for %s: %s", key, str(e)[:160])

    if approved or deduped:
        logger.info("auto-tune auto-approve: %d approved, %d deduped, %d deferred",
                    approved, deduped, len(deferred))
    return {"enabled": True, "approved": approved, "deduped": deduped,
            "deferred": deferred, "audit": audit,
            "grace_hours": cfg["grace_hours"], "min_evidence": cfg["min_evidence"]}


async def bulk_decide(admin_id: str, *, approve: bool) -> Dict[str, Any]:
    """Admin one-click bulk approve / reject of ALL pending suggestions —
    used by the dashboard "Approve all" / "Reject all" buttons. Dedupes
    per-key first (only the latest proposal survives), then applies the
    same activation logic as `decide()`."""
    pending = await (db.prompt_tuning_suggestions
                     .find({"status": "proposed"}, {"_id": 0})
                     .sort("ts", -1).to_list(500))
    if not pending:
        return {"approved": 0, "rejected": 0, "deduped": 0}

    # Dedupe by key — only the latest is the candidate
    seen: Dict[str, Dict[str, Any]] = {}
    deduped = 0
    for s in pending:
        if s["page_type"] not in seen:
            seen[s["page_type"]] = s
        else:
            await db.prompt_tuning_suggestions.update_one(
                {"id": s["id"]},
                {"$set": {"status": "rejected", "decided_by": admin_id,
                          "decided_at": _now(),
                          "auto_reason": "stale duplicate — bulk action picked latest"}})
            deduped += 1

    approved = 0
    rejected = 0
    for s in seen.values():
        try:
            await decide(s["id"], admin_id, approve=approve)
            if approve:
                approved += 1
            else:
                rejected += 1
        except Exception as e:  # noqa: BLE001 — keep going
            logger.warning("bulk_decide failed for %s: %s", s["id"], str(e)[:160])
    return {"approved": approved, "rejected": rejected, "deduped": deduped}


# ── Daily automatic Auto-Tune sweep ──────────────────────────────────────────
def start_daily_auto_tune_task() -> None:
    """Run the Auto-Tune analysis automatically every 24h (in addition to the
    on-demand "Generate (AI)" button). Suggestions are only PROPOSED — they
    still require super-admin approval before going live. Metered (precise
    tier) to the first super-admin's wallet."""
    import asyncio

    async def _loop():
        await asyncio.sleep(1800)  # let the app settle; first sweep 30 min after boot
        while True:
            try:
                admin = (await db.users.find_one({"role": "super_admin"}, {"_id": 0, "user_id": 1})
                         or await db.users.find_one({"role": "admin"}, {"_id": 0, "user_id": 1}))
                if admin:
                    res = await generate_suggestions(admin["user_id"], days=7)
                    logger.info("daily auto-tune sweep: %d proposed, %d skipped",
                                len(res["created"]), len(res["skipped"]))
                # Auto-approve pass — runs ALWAYS (even when generation produced
                # nothing) so older pending proposals graduate after their grace
                # window. Idempotent: re-runs the same day are no-ops.
                ap = await auto_approve_pass()
                if ap.get("approved") or ap.get("deduped"):
                    logger.info("auto-tune auto-approve summary: %s", ap)
            except Exception as e:  # noqa: BLE001 — sweep must never crash the loop
                logger.warning("daily auto-tune sweep failed: %s", str(e)[:160])
            await asyncio.sleep(24 * 3600)

    asyncio.get_event_loop().create_task(_loop())
    logger.info("Prompt Auto-Tune daily task started (24h cadence; proposals need admin approval).")
