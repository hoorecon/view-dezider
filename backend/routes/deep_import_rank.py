"""Deep-Import auto-assess & rank — Wave 2 #8b (June 2026).

After a Deep-Import job finalises and the user has set their Step-5 factor
weightages, this module:

  1. Estimates how many AI credits would be needed to fully assess the first
     `budget_count` options (= every option × factor cell that's still empty).
  2. Runs the assessment loop sequentially — same per-cell engine the rest of
     the app uses (`core.ai_assess.ai_assess_factor`) — so it shares quota
     handling, AI metering, blank-default fill, and provenance.
  3. Scores each assessed option using `services.apply_assessment_rows`'
     identical worth math (rating × percentage / total-rating), then writes
     the sorted top-N option-ids onto the decision so Step 8 can preselect
     them.

The endpoints expose only the new behaviour; nothing in the legacy import or
manual assessment paths changes.

Routes (all under /api):
  GET  /decisions/{id}/deep-import/budget-estimate?budget_count=N
  POST /decisions/{id}/deep-import/auto-assess-rank
        body: {"budget_count": N, "blank_default_pct": optional override}
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.auth import get_current_user
from core.database import db
from core import ai_wallet
from core.blank_default import (
    get_user_blank_default,
    resolve_decision_blank_pct,
)
from core.ai_assess import ai_assess_factor

router = APIRouter(tags=["DeepImportRank"])


# ─────────────────────── helpers ───────────────────────
def _has(v: Any) -> bool:
    return v is not None and str(v).strip() != ""


def _cell_pct(opt: Dict[str, Any], fid: str) -> Optional[int]:
    for a in opt.get("assessments") or []:
        if a.get("factor_id") == fid:
            return a.get("percentage")
    return None


def _empty_cells(decision: Dict[str, Any], option_ids: List[str]) -> List[Dict[str, str]]:
    """Return [{option_id, factor_id}] for cells with no percentage yet,
    limited to top-level factors (sub-factor rollup is handled by Step 9
    already)."""
    top_level = [f for f in decision.get("factors", []) if not f.get("parent_id")]
    options_by_id = {o["id"]: o for o in decision.get("options", []) if o["id"] in option_ids}
    out: List[Dict[str, str]] = []
    for oid in option_ids:
        opt = options_by_id.get(oid)
        if not opt:
            continue
        for f in top_level:
            if _cell_pct(opt, f["id"]) is None:
                out.append({"option_id": oid, "factor_id": f["id"]})
    return out


def _compute_worth(option: Dict[str, Any], factors: List[Dict[str, Any]]) -> float:
    """Worth = sum(rating × pct) / sum(rating × 100) × 100 — matches
    services.py:apply_assessment_rows so Step 8/9 see consistent numbers."""
    by_fid = {a.get("factor_id"): a for a in option.get("assessments") or []}
    num = 0.0
    den = 0.0
    for f in factors:
        if f.get("parent_id"):
            continue
        r = int(f.get("rating") or 0)
        if r <= 0:
            continue
        a = by_fid.get(f["id"]) or {}
        pct = a.get("percentage")
        if pct is None:
            continue
        num += r * int(pct)
        den += r * 100.0
    if den <= 0:
        return 0.0
    return round(num / den * 100.0, 2)


async def _per_cell_estimate(user_id: str) -> float:
    """Avg per-cell AI cost in CREDITS (post-markup). Falls back to a
    historical average per-cell from `ai_wallet_ledger`. Conservative default
    when no history (~1.5 cr/cell ≈ small Claude/Gemini call)."""
    # Pull recent ai-assess debit rows from the wallet ledger.
    rows = await (
        db.ai_wallet_ledger.find({
            "user_id": user_id,
            "kind": "debit",
            "feature": {"$in": ["ai_assess_factor", "ai_assess_batch", "ai_assess_all_batched"]},
        }, {"_id": 0, "credits": 1, "meta": 1})
        .sort("ts", -1).limit(60).to_list(60)
    )
    if rows:
        # Each batch/factor row already represents 1..N cells; we approximate
        # cell count from meta.cells when present, else 1.
        total_cr = sum(float(r.get("credits") or 0) for r in rows)
        total_cells = sum(int((r.get("meta") or {}).get("cells") or 1) for r in rows)
        if total_cells:
            return max(0.5, total_cr / total_cells)
    return 1.5


# ─────────────────────── routes ───────────────────────
@router.get("/decisions/{decision_id}/deep-import/budget-estimate")
async def budget_estimate(decision_id: str, budget_count: int = 0,
                          user: dict = Depends(get_current_user)):
    """Cost preview for the Deep-Import "process N options" budget picker.

    `budget_count = 0` → return the discovered total (so the UI can render
    the slider min/max). Otherwise compute the credits required to fully
    assess the first `budget_count` options' empty cells.
    """
    decision = await db.decisions.find_one(
        {"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    cfg = await ai_wallet.get_config()
    max_options = int(cfg.get("deep_import_max_options") or 10)
    top_n = int(cfg.get("deep_import_top_n") or 5)

    options = decision.get("options") or []
    total_options = len(options)
    # The "budget" is bounded by the admin cap AND the count of discovered options.
    upper = max(2, min(total_options, max_options))
    lower = min(2, upper)
    requested = budget_count if budget_count > 0 else upper
    requested = max(lower, min(upper, requested))

    # Estimate empty cells the auto-assess loop will need to fill.
    target_ids = [o["id"] for o in options[:requested]]
    empty = _empty_cells(decision, target_ids)
    per_cell = await _per_cell_estimate(user["user_id"])
    estimate = round(len(empty) * per_cell, 1)

    bal = await ai_wallet.get_balance(user["user_id"])
    balance = float(bal.get("balance") or 0)
    return {
        "total_options": total_options,
        "max_options": max_options,
        "top_n": top_n,
        "lower": lower,
        "upper": upper,
        "requested": requested,
        "empty_cells": len(empty),
        "per_cell_credits": round(per_cell, 2),
        "estimate_credits": estimate,
        "balance": round(balance, 1),
        "sufficient": balance >= estimate,
        "shortfall": round(max(0.0, estimate - balance), 1),
    }


@router.post("/decisions/{decision_id}/deep-import/auto-assess-rank")
async def auto_assess_rank(decision_id: str, body: Dict[str, Any],
                           user: dict = Depends(get_current_user)):
    """Sequentially AI-assess every empty cell of the first `budget_count`
    options, compute final worth %, write the top-N option ids onto the
    decision, and clear the pending-rank flag.

    Returns the ranked option list and the top-N ids that Step 8 picks up.
    """
    user_id = user["user_id"]
    decision = await db.decisions.find_one({"id": decision_id, "user_id": user_id}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    cfg = await ai_wallet.get_config()
    max_options = int(cfg.get("deep_import_max_options") or 10)
    top_n = int(cfg.get("deep_import_top_n") or 5)
    try:
        budget = int(body.get("budget_count") or 0)
    except (TypeError, ValueError):
        budget = 0
    options = decision.get("options") or []
    if not options:
        raise HTTPException(status_code=400, detail="No options on this decision yet.")
    upper = max(2, min(len(options), max_options))
    lower = min(2, upper)
    if budget < lower or budget > upper:
        raise HTTPException(
            status_code=400,
            detail=f"budget_count must be between {lower} and {upper}",
        )

    # Resolve effective blank-default (decision override > user pref > 5).
    user_blank = await get_user_blank_default(user_id)
    blank_pct = resolve_decision_blank_pct(decision, user_blank)
    body_blank = body.get("blank_default_pct")
    if body_blank is not None:
        try:
            n = int(body_blank)
            if 0 <= n <= 100:
                blank_pct = n
        except (TypeError, ValueError):
            pass

    factors = [f for f in decision.get("factors", []) if not f.get("parent_id")]
    target_options = options[:budget]
    target_ids = [o["id"] for o in target_options]
    factors_by_id = {f["id"]: f for f in decision.get("factors", [])}
    options_by_id = {o["id"]: o for o in decision.get("options", [])}

    results: List[Dict[str, Any]] = []
    cells_processed = 0
    cells_succeeded = 0
    out_of_credits = False
    ai_unavailable = False
    for oid in target_ids:
        opt = options_by_id[oid]
        for f in factors:
            fid = f["id"]
            existing_pct = _cell_pct(opt, fid)
            if existing_pct is not None:
                continue  # already scored — skip
            cells_processed += 1
            # Pull current actual_value (deep import pre-fills this for the
            # discovered options). When missing on quantitative factors we
            # let ai_assess force_fill the actual itself.
            existing = next((a for a in opt.get("assessments") or [] if a.get("factor_id") == fid), None)
            provided_actual = (existing or {}).get("unit_value")

            is_qual = f.get("data_type") == "text" or f.get("factor_type") in ("subjective", "qualitative")
            incomplete = (not _has(f.get("expected_value"))) or (
                (not is_qual) and (not _has(f.get("operator")) or not _has(provided_actual))
            )
            try:
                result = await ai_assess_factor(
                    factor=f, option=opt,
                    decision_title=decision.get("title") or "",
                    decision_context=decision.get("context") or "",
                    user_id=user_id, provided_actual=provided_actual,
                    force_fill=incomplete,  # let AI infer Actual when needed
                )
            except HTTPException as he:
                if he.status_code == 402:
                    out_of_credits = True
                    break
                if he.status_code == 502:
                    ai_unavailable = True
                    break
                # Cell-level error → fall through to blank-default fill below.
                results.append({"option_id": oid, "factor_id": fid, "status": "error"})
                continue

            # Apply the result (same math as the per-cell endpoint).
            from routes.decisions.assessment import _apply_assessment  # local import dodges circular load
            pct, final_actual = _apply_assessment(f, opt, result)
            cells_succeeded += 1
            results.append({
                "option_id": oid, "factor_id": fid, "status": "done",
                "percentage": pct, "actual_value": final_actual,
            })
        if out_of_credits or ai_unavailable:
            break

    # Default-fill blanks (status=error) so worth math doesn't choke on a few
    # AI-misses. Mirrors what the regular batch endpoint already does.
    from routes.decisions.assessment import _apply_blank_default  # local import
    blanks_applied = _apply_blank_default(decision, results, blank_pct)

    # Recompute worth_percentage for ALL assessed options so Step 8 has
    # accurate numbers.
    ranked: List[Dict[str, Any]] = []
    for oid in target_ids:
        opt = options_by_id[oid]
        opt["worth_percentage"] = _compute_worth(opt, factors)
        ranked.append({
            "option_id": oid,
            "name": opt.get("name"),
            "worth_percentage": opt["worth_percentage"],
        })
    ranked.sort(key=lambda r: r["worth_percentage"], reverse=True)
    top_n_ids = [r["option_id"] for r in ranked[:top_n]]

    # Persist option assessments + worth + ranking + clear pending flag.
    await db.decisions.update_one(
        {"id": decision_id, "user_id": user_id},
        {"$set": {
            "options": decision["options"],
            "factors": decision["factors"],
            "deep_import_pending_rank": False,
            "deep_import_top_n_ids": top_n_ids,
            "updated_at": datetime.now(timezone.utc),
        }},
    )

    return {
        "ranked": ranked,
        "top_n_option_ids": top_n_ids,
        "top_n": top_n,
        "cells_processed": cells_processed,
        "cells_succeeded": cells_succeeded,
        "blanks_applied": blanks_applied,
        "blank_default_pct": blank_pct,
        "out_of_credits": out_of_credits,
        "ai_unavailable": ai_unavailable,
    }


@router.post("/decisions/{decision_id}/deep-import/dismiss-rank-prompt")
async def dismiss_rank_prompt(decision_id: str, user: dict = Depends(get_current_user)):
    """User chose to skip the auto-rank prompt — clear the pending flag so
    the modal doesn't keep nagging."""
    r = await db.decisions.update_one(
        {"id": decision_id, "user_id": user["user_id"]},
        {"$set": {"deep_import_pending_rank": False,
                  "updated_at": datetime.now(timezone.utc)}},
    )
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Decision not found")
    return {"ok": True}
