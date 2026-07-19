"""Option Bank — admin ingestion & management for the 10M-scale Finder.

One bank per Decider-Store template (`decider_option_bank`). Options flow in
from THREE sources (all normalized once at ingest — FRAME stage S0):

  1. INTERNAL  — the template's own embedded options, and Solution Store +
                 ReviewNet items already bridged to the template
                 (`decider_template_id`, quantitative_factors keyed by
                 sub-factor id, ReviewNet baseline_profile).
  2. PARTNER   — any external JSON API: admin supplies the URL, an items path
                 and a {sub_factor_id: json_key} value map.
  3. DEEP IMPORT / BULK — raw option rows (name + values keyed by sub-factor
                 id) posted by Deep-Import finalize flows, scripts, or CSVs.

Routes (under /api, admin-only):
  GET    /decider-store/{tid}/bank                    stats (count, by source)
  POST   /decider-store/{tid}/bank/sync-template      ingest embedded options
  POST   /decider-store/{tid}/bank/ingest/solutions   ingest bridged Store+ReviewNet
  POST   /decider-store/{tid}/bank/ingest/partner     ingest external API
  POST   /decider-store/{tid}/bank/ingest/bulk        ingest raw rows
  DELETE /decider-store/{tid}/bank                    clear (optionally by source)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from core.auth import require_admin
from core.database import db
from core.finder_bank import BANK, bank_upsert

router = APIRouter(prefix="/decider-store", tags=["Option Bank"])

VALID_SOURCES = ("template", "store_bridge", "partner_api", "deep_import", "bulk", "synthetic")


async def _template(tid: str) -> Dict[str, Any]:
    t = await db.decider_store_templates.find_one({"template_id": tid}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Template not found")
    return t


@router.get("/{template_id}/bank")
async def bank_stats(template_id: str, user: dict = Depends(require_admin)):
    await _template(template_id)
    rows = await db[BANK].aggregate([
        {"$match": {"template_id": template_id}},
        {"$group": {"_id": "$source", "n": {"$sum": 1}}},
    ]).to_list(20)
    by_source = {r["_id"] or "unknown": r["n"] for r in rows}
    return {"template_id": template_id, "total": sum(by_source.values()),
            "by_source": by_source}


@router.post("/{template_id}/bank/sync-template")
async def bank_sync_template(template_id: str, user: dict = Depends(require_admin)):
    """Copy the template's embedded options into the bank (values are already
    keyed by sub-factor id in the authoring schema)."""
    t = await _template(template_id)
    items = [{"name": o.get("name"), "description": o.get("description") or o.get("remarks"),
              "source_ref": o.get("id"), "values": o.get("values") or {}}
             for o in (t.get("options") or [])]
    counts = await bank_upsert(t, items, "template")
    return {"source": "template", "received": len(items), **counts}


@router.post("/{template_id}/bank/ingest/solutions")
async def bank_ingest_solutions(template_id: str, user: dict = Depends(require_admin)):
    """Pull every Solution-Store item bridged to this template (quantitative
    factors keyed by sub-factor id) merged with its ReviewNet baseline
    (qualitative baseline_profile) — the internal-data rail."""
    t = await _template(template_id)
    sols = await db.solutions_store.find(
        {"decider_template_id": template_id},
        {"_id": 0, "solution_id": 1, "name": 1, "description": 1,
         "quantitative_factors": 1}).to_list(100000)
    items: List[Dict[str, Any]] = []
    for s in sols:
        values: Dict[str, Any] = {}
        for qf in s.get("quantitative_factors") or []:
            values[qf.get("factor_id")] = {"raw": qf.get("value"), "num": qf.get("num")}
        baseline = await db.review_net.find_one(
            {"review_id": f"rv_baseline_{s['solution_id']}"},
            {"_id": 0, "baseline_profile": 1})
        for sid, bp in ((baseline or {}).get("baseline_profile") or {}).items():
            values.setdefault(sid, {"raw": bp.get("value"), "num": bp.get("num")})
        items.append({"name": s.get("name"), "description": s.get("description"),
                      "source_ref": s.get("solution_id"), "values": values})
    counts = await bank_upsert(t, items, "store_bridge")
    return {"source": "store_bridge", "received": len(items), **counts}


def _dig(obj: Any, path: str) -> Any:
    for part in [p for p in (path or "").split(".") if p]:
        if isinstance(obj, dict):
            obj = obj.get(part)
        else:
            return None
    return obj


@router.post("/{template_id}/bank/ingest/partner")
async def bank_ingest_partner(template_id: str, request: Request,
                              user: dict = Depends(require_admin)):
    """External partner-API rail. Body:
      {api_url, items_path?: "data.results", name_key: "title",
       value_map: {<sub_factor_id>: "<json_key>"}, headers?: {}, limit?: 10000}
    """
    t = await _template(template_id)
    body = await request.json()
    api_url = str(body.get("api_url") or "").strip()
    if not api_url.startswith(("http://", "https://")):
        raise HTTPException(400, "api_url must be an http(s) URL")
    name_key = str(body.get("name_key") or "name")
    value_map: Dict[str, str] = body.get("value_map") or {}
    if not isinstance(value_map, dict) or not value_map:
        raise HTTPException(400, "value_map {sub_factor_id: json_key} is required")
    limit = min(100000, max(1, int(body.get("limit") or 10000)))
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
            resp = await client.get(api_url, headers=body.get("headers") or {})
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:
        raise HTTPException(400, f"Partner API fetch failed: {str(e)[:150]}")
    rows = _dig(payload, body.get("items_path") or "") or payload
    if isinstance(rows, dict):
        rows = rows.get("items") or rows.get("results") or rows.get("data") or []
    if not isinstance(rows, list):
        raise HTTPException(400, "Could not locate an items array — set items_path")
    items = []
    for r in rows[:limit]:
        if not isinstance(r, dict):
            continue
        items.append({"name": _dig(r, name_key),
                      "source_ref": str(r.get("id") or r.get("uid") or "")[:80] or None,
                      "values": {sid: _dig(r, key) for sid, key in value_map.items()}})
    counts = await bank_upsert(t, items, "partner_api")
    return {"source": "partner_api", "received": len(items), **counts}


@router.post("/{template_id}/bank/ingest/bulk")
async def bank_ingest_bulk(template_id: str, request: Request,
                           user: dict = Depends(require_admin)):
    """Raw rows rail (Deep-Import finalize, scripts, CSV loaders). Body:
      {items: [{name, description?, source_ref?, values: {sub_id: raw|{raw,num}}}],
       source?: "deep_import"|"bulk"|"synthetic"}"""
    t = await _template(template_id)
    body = await request.json()
    items = body.get("items") or []
    if not isinstance(items, list) or not items:
        raise HTTPException(400, "items[] is required")
    if len(items) > 50000:
        raise HTTPException(400, "Max 50,000 items per bulk call — batch your loads")
    source = body.get("source") if body.get("source") in VALID_SOURCES else "bulk"
    counts = await bank_upsert(t, items, source)
    return {"source": source, "received": len(items), **counts}


@router.delete("/{template_id}/bank")
async def bank_clear(template_id: str, source: Optional[str] = None,
                     user: dict = Depends(require_admin)):
    await _template(template_id)
    q: Dict[str, Any] = {"template_id": template_id}
    if source:
        q["source"] = source
    res = await db[BANK].delete_many(q)
    return {"deleted": res.deleted_count}
