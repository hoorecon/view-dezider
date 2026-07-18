"""DeciderApp / Finder — run the auto-filter + auto-assess + Top-N over a cloned
decision (see core.finder_engine). Deterministic by default; an optional 'llm'
engine fills any missing actual values via the shared per-cell AI assessor first.

Routes (under /api):
  GET  /decisions/{id}/finder/config          -> resolved defaults for the UI
  POST /decisions/{id}/finder/run             -> ranked Top-N (persists results)
        body: {min_options?, max_options?, top_n?, match_rule?, engine?}
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from core import ai_wallet, finder_engine
from core.auth import get_current_user
from core.database import db

router = APIRouter(tags=["Finder"])


async def _resolve_cfg(decision: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
    admin = await ai_wallet.get_config()
    cfg: Dict[str, Any] = {
        "min_options": admin.get("finder_min_options", 3),
        "max_options": admin.get("finder_max_options", 15),
        "top_n": admin.get("finder_top_n", 5),
        "match_rule": admin.get("finder_match_rule", "all"),
        "engine": admin.get("finder_engine", "deterministic"),
    }
    for src in (decision.get("finder_config") or {}, body or {}):
        for k in ("min_options", "max_options", "top_n", "match_rule", "engine"):
            if src.get(k) not in (None, ""):
                cfg[k] = src[k]
    try:
        cfg["min_options"] = max(1, int(float(cfg["min_options"])))
        cfg["max_options"] = max(cfg["min_options"], int(float(cfg["max_options"])))
        cfg["top_n"] = max(1, int(float(cfg["top_n"])))
    except (TypeError, ValueError):
        cfg["min_options"], cfg["max_options"], cfg["top_n"] = 3, 15, 5
    if cfg["match_rule"] not in ("all", "any"):
        cfg["match_rule"] = "all"
    if cfg["engine"] not in ("deterministic", "llm"):
        cfg["engine"] = "deterministic"
    return cfg


@router.get("/decisions/{decision_id}/finder/config")
async def finder_config(decision_id: str, user: dict = Depends(get_current_user)):
    decision = await db.decisions.find_one(
        {"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    cfg = await _resolve_cfg(decision, {})
    return {"config": cfg, "total_options": len(decision.get("options") or []),
            "is_app": decision.get("decider_kind") == "app"}


async def _llm_enrich(decision: Dict[str, Any], survivors: List[Dict[str, Any]],
                      user_id: str) -> Dict[str, Any]:
    """Best-effort: fill missing leaf actuals for the survivor set so the
    deterministic scorer has values to work with. Bounded by the survivor set."""
    from core.ai_assess import ai_assess_factor
    factors = decision.get("factors") or []
    leaves = [f for f in factors if not any(x.get("parent_id") == f["id"] for x in factors)]
    processed = succeeded = 0
    out_of_credits = ai_unavailable = False
    for opt in survivors:
        for f in leaves:
            exp = f.get("expected_value")
            if exp is None or str(exp).strip() == "":
                continue
            a = next((x for x in opt.get("assessments") or [] if x.get("factor_id") == f["id"]), None)
            has_actual = a and (str(a.get("unit_value") or "").strip() or a.get("actual_value") is not None)
            if has_actual:
                continue
            processed += 1
            try:
                result = await ai_assess_factor(
                    factor=f, option=opt, decision_title=decision.get("title") or "",
                    decision_context=decision.get("context") or "", user_id=user_id,
                    provided_actual=None, force_fill=True)
            except HTTPException as he:
                if he.status_code == 402:
                    out_of_credits = True
                elif he.status_code == 502:
                    ai_unavailable = True
                else:
                    continue
                break
            except Exception:
                continue
            actual = result.get("actual_value") if isinstance(result, dict) else None
            if actual is not None:
                if a:
                    a["unit_value"] = str(actual)
                else:
                    opt.setdefault("assessments", []).append(
                        {"factor_id": f["id"], "unit_value": str(actual), "percentage": None})
                succeeded += 1
        if out_of_credits or ai_unavailable:
            break
    return {"cells_processed": processed, "cells_succeeded": succeeded,
            "out_of_credits": out_of_credits, "ai_unavailable": ai_unavailable}


@router.post("/decisions/{decision_id}/finder/run")
async def finder_run(decision_id: str, body: Dict[str, Any] = None,
                     user: dict = Depends(get_current_user)):
    body = body or {}
    decision = await db.decisions.find_one(
        {"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    if not (decision.get("options") or []):
        raise HTTPException(status_code=400, detail="This decision has no options to search.")

    cfg = await _resolve_cfg(decision, body)

    llm_info: Dict[str, Any] = {}
    if cfg["engine"] == "llm":
        # Determine survivors deterministically first, then enrich just those.
        pre = finder_engine.run_finder(decision, cfg)
        surv_ids = {r["option_id"] for r in pre["ranked"]}
        survivors = [o for o in decision["options"] if o["id"] in surv_ids]
        llm_info = await _llm_enrich(decision, survivors, user["user_id"])

    result = finder_engine.run_finder(decision, cfg)

    # Persist worth on options + the winning ids for later display.
    worth_by_id = {r["option_id"]: r["worth_percentage"] for r in result["ranked"]}
    for o in decision["options"]:
        if o["id"] in worth_by_id:
            o["worth_percentage"] = worth_by_id[o["id"]]
    await db.decisions.update_one(
        {"id": decision_id, "user_id": user["user_id"]},
        {"$set": {"options": decision["options"],
                  "finder_result_ids": result["top_ids"],
                  "finder_last_run": datetime.now(timezone.utc).isoformat(),
                  "finder_config_used": cfg,
                  "updated_at": datetime.now(timezone.utc)}})

    # Attach rich per-option cards (name + worth + rationale) for the top set.
    opt_by_id = {o["id"]: o for o in decision["options"]}
    top_cards = []
    for r in result["top"]:
        o = opt_by_id.get(r["option_id"]) or {}
        top_cards.append({**r, "ai_rationale": o.get("ai_rationale") or "",
                          "source": o.get("source")})
    result["top"] = top_cards
    result["engine"] = cfg["engine"]
    if llm_info:
        result["llm"] = llm_info
    return result
