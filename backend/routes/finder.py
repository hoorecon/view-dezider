"""DeciderApp / Finder — run the auto-filter + auto-assess + Top-N over a cloned
decision (see core.finder_engine). Deterministic by default; an optional 'llm'
engine fills any missing actual values via the shared per-cell AI assessor first.

Routes (under /api):
  GET  /decisions/{id}/finder/config          -> resolved defaults for the UI
  POST /decisions/{id}/finder/run             -> ranked Top-N (persists results)
        body: {min_options?, max_options?, top_n?, match_rule?, engine?}
  POST /decisions/{id}/finder/jobs            -> async Option-Bank run (10M scale)
  GET  /finder/jobs/{job_id}                  -> poll {status, progress, result}
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from core import ad_auction, ai_wallet, finder_bank, finder_engine
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
    bank_options = 0
    if decision.get("source_template_id"):
        bank_options = await db[finder_bank.BANK].count_documents(
            {"template_id": decision["source_template_id"]})
    return {"config": cfg, "total_options": len(decision.get("options") or []),
            "bank_options": bank_options,
            "is_app": decision.get("decider_kind") == "app"}


# ═══════════════ Option-Bank async jobs (10M-option scale) ═══════════════
@router.post("/decisions/{decision_id}/finder/jobs")
async def finder_job_start(decision_id: str, body: Dict[str, Any] = None,
                           user: dict = Depends(get_current_user)):
    body = body or {}
    decision = await db.decisions.find_one(
        {"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    tid = decision.get("source_template_id")
    if not tid:
        raise HTTPException(400, "This decision has no linked Decider App.")
    template = await db.decider_store_templates.find_one({"template_id": tid}, {"_id": 0})
    if not template:
        raise HTTPException(404, "Source Decider App not found")
    if await db[finder_bank.BANK].count_documents({"template_id": tid}) == 0:
        raise HTTPException(400, "No Option Bank for this app — use the standard run.")

    cfg = await _resolve_cfg(decision, body)
    region = str(body.get("region") or user.get("country") or "global").strip().lower() or "global"
    specs = finder_bank.build_leaf_specs(decision, template)
    shash = finder_bank.spec_hash(specs, cfg)

    # Expectations-hash cache: identical spec finished recently → instant.
    cached = await db.finder_jobs.find_one(
        {"decision_id": decision_id, "spec_hash": shash, "status": "done"},
        {"_id": 0}, sort=[("created_at", -1)])
    if cached and not body.get("force"):
        age = (datetime.now(timezone.utc)
               - datetime.fromisoformat(cached["created_at"])).total_seconds()
        if age < 600:
            return {"job_id": cached["id"], "cached": True}

    job = {"id": str(uuid.uuid4()), "decision_id": decision_id,
           "user_id": user["user_id"], "template_id": tid, "spec_hash": shash,
           "status": "running", "progress": {"pct": 1, "label": "Queued…"},
           "result": None, "error": None,
           "created_at": datetime.now(timezone.utc).isoformat(),
           "updated_at": datetime.now(timezone.utc).isoformat()}
    await db.finder_jobs.insert_one({**job})
    asyncio.create_task(finder_bank.run_bank_job(job["id"], decision, template,
                                                 cfg, user, region))
    return {"job_id": job["id"], "cached": False}


@router.get("/finder/jobs/{job_id}")
async def finder_job_status(job_id: str, user: dict = Depends(get_current_user)):
    job = await db.finder_jobs.find_one(
        {"id": job_id, "user_id": user["user_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(404, "Job not found")
    return job


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

    # ── Sponsored Solutions (AdMaker auction) — rendered BELOW organic ──
    # Quality gate (Min-Cutoff %) + slot count resolve hierarchically:
    # template finder_settings → CCM node chain → global admin defaults.
    template = None
    if decision.get("source_template_id"):
        template = await db.decider_store_templates.find_one(
            {"template_id": decision["source_template_id"]},
            {"_id": 0, "template_id": 1, "finder_settings": 1, "catalog_node_id": 1})
    ad_cfg = await ad_auction.resolve_ad_config(template)
    region = str(body.get("region") or user.get("country") or "global").strip().lower() or "global"
    sponsored: List[Dict[str, Any]] = []
    if template:
        sponsored = await ad_auction.run_auction(
            template_id=template["template_id"], ranked=result["ranked"],
            region=region, sponsored_n=ad_cfg["sponsored_n"],
            min_cutoff_pct=ad_cfg["min_cutoff_pct"])

    # Persist worth on options + the winning ids for later display.
    worth_by_id = {r["option_id"]: r["worth_percentage"] for r in result["ranked"]}
    for o in decision["options"]:
        if o["id"] in worth_by_id:
            o["worth_percentage"] = worth_by_id[o["id"]]
    await db.decisions.update_one(
        {"id": decision_id, "user_id": user["user_id"]},
        {"$set": {"options": decision["options"],
                  "finder_result_ids": result["top_ids"],
                  "finder_sponsored_ids": [w["option_id"] for w in sponsored],
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
    # User-safe Sponsored cards — bid amounts / CPC prices are NEVER exposed.
    result["sponsored"] = [{
        "option_id": w["option_id"], "name": w["name"],
        "worth_percentage": w["worth_percentage"], "slot": w["slot"],
        "advertiser_name": w["advertiser_name"], "bid_id": w["bid_id"],
        "ai_rationale": (opt_by_id.get(w["option_id"]) or {}).get("ai_rationale") or "",
    } for w in sponsored]
    result["ad_config"] = {
        "min_cutoff_pct": ad_cfg["min_cutoff_pct"],
        "sponsored_n": ad_cfg["sponsored_n"], "region": region,
        "eligible_above_cutoff": sum(
            1 for r in result["ranked"]
            if r["worth_percentage"] >= ad_cfg["min_cutoff_pct"]),
    }
    if sponsored:
        await ad_auction.record_impressions(
            sponsored, template["template_id"], decision_id, region, user["user_id"])
    if llm_info:
        result["llm"] = llm_info
    return result
