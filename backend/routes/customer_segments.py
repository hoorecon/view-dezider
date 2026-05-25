"""
customer_segments.py — Admin CRUD on Customer Segment / Target-Group master.

Endpoints:
  GET    /api/admin/customer-segments              — list all
  POST   /api/admin/customer-segments              — create
  GET    /api/admin/customer-segments/{sid}        — read one
  PUT    /api/admin/customer-segments/{sid}        — update
  DELETE /api/admin/customer-segments/{sid}        — delete
  POST   /api/admin/customer-segments/{sid}/factor — add custom factor
  DELETE /api/admin/customer-segments/{sid}/factor/{key}
  POST   /api/admin/customer-segments/{sid}/ai-research — AI fill one factor
  PUT    /api/admin/customer-segments/{sid}/pricing       — upsert tier pricing
  GET    /api/customer-segments/factors            — predefined factor catalog
  GET    /api/customer-segments                    — public list (for pricing)
  GET    /api/pricing                              — combined: tiers + segments + matrix
"""
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from core.database import db
from core.auth import get_current_user, require_admin
from models.customer_segment_models import (
    PREDEFINED_FACTORS,
    FACTOR_CATEGORIES,
    CustomerSegmentCreate,
    CustomerSegmentUpdate,
    FactorAddRequest,
    AIResearchRequest,
    TierPricingUpsert,
)
from models.tier_models import CHAKRA_TIERS, TIER_KEYS

router = APIRouter(tags=["Customer Segments — Target Group Master"])

# In-process TTL cache for the public /pricing payload (hot path).
# Invalidated on any admin write (segment / pricing / factor / matrix).
_PRICING_CACHE: Dict[str, Any] = {"data": None, "expires_at": 0.0}
_PRICING_TTL_SECONDS = 60.0


def _invalidate_pricing_cache() -> None:
    _PRICING_CACHE["data"] = None
    _PRICING_CACHE["expires_at"] = 0.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _segment_to_dict(d: dict) -> dict:
    d = {k: v for k, v in d.items() if k != "_id"}
    return d


# ----------------------------------------------------------------------
# Public reads
# ----------------------------------------------------------------------
@router.get("/customer-segments/factors")
async def list_factor_catalog():
    """Return predefined factor catalog (used by Admin UI dropdowns)."""
    return {
        "factors": PREDEFINED_FACTORS,
        "categories": FACTOR_CATEGORIES,
    }


@router.get("/customer-segments")
async def list_customer_segments_public():
    """Public read — used by /pricing page to render segment cards."""
    docs = []
    async for d in db.customer_segments.find({}, {"_id": 0}).sort("created_at", -1):
        docs.append(d)
    return {"segments": docs, "tiers": CHAKRA_TIERS}


@router.get("/pricing")
async def public_pricing_payload():
    """One-shot pricing payload for the public /pricing page.

    Returns: tiers[], segments[], matrix_rows[] (modules x tiers feature gating).
    Cached in-process for 60s; invalidated on any admin write.
    """
    now = time.time()
    if _PRICING_CACHE["data"] is not None and _PRICING_CACHE["expires_at"] > now:
        return _PRICING_CACHE["data"]

    segments = []
    async for d in db.customer_segments.find({}, {"_id": 0}).sort("created_at", -1):
        segments.append(d)

    # Pull matrix rows the same way tier_matrix.get_public_matrix does (cheap)
    modules = await db.acm_modules.find({}, {"_id": 0}).sort("order", 1).to_list(50)
    cells: List[Dict[str, Any]] = []
    async for c in db.tier_matrix.find({"feature_id": None}, {"_id": 0}):
        cells.append(c)
    by_key = {(c["module_id"], c["tier_key"]): c for c in cells}
    rows = []
    for mod in modules:
        mid = mod.get("module_id")
        if not mid:
            continue
        rows.append({
            "module_id": mid,
            "module_name": mod.get("module_name"),
            "module_icon": mod.get("module_icon"),
            "tiers": {t["key"]: bool(by_key.get((mid, t["key"]), {}).get("allowed", False)) for t in CHAKRA_TIERS},
        })

    payload = {
        "tiers": CHAKRA_TIERS,
        "segments": segments,
        "matrix_rows": rows,
    }
    _PRICING_CACHE["data"] = payload
    _PRICING_CACHE["expires_at"] = now + _PRICING_TTL_SECONDS
    return payload


# ----------------------------------------------------------------------
# Admin CRUD
# ----------------------------------------------------------------------
@router.get("/admin/customer-segments")
async def admin_list(user: dict = Depends(require_admin)):
    docs = []
    async for d in db.customer_segments.find({}, {"_id": 0}).sort("created_at", -1):
        docs.append(d)
    return {"segments": docs, "tiers": CHAKRA_TIERS, "factors": PREDEFINED_FACTORS}


@router.post("/admin/customer-segments")
async def admin_create(body: CustomerSegmentCreate, user: dict = Depends(require_admin)):
    sid = f"cs_{uuid.uuid4().hex[:12]}"
    # Seed factors with predefined skeleton if none provided
    factors = [f.model_dump() for f in body.factors]
    if not factors:
        factors = [{**f, "value": "", "is_custom": False} for f in PREDEFINED_FACTORS]

    # Default tier pricings — INR rows for all 7 tiers if none provided
    pricings = [p.model_dump() for p in body.tier_pricings]
    if not pricings:
        pricings = [
            {"tier_key": t["key"], "country_code": "IN", "currency": "INR",
             "monthly_price": float(t.get("monthly_price_inr", 0)),
             "annual_price": float(t.get("monthly_price_inr", 0)) * 10,
             "enabled": True}
            for t in CHAKRA_TIERS
        ]

    doc = {
        "segment_id": sid,
        "name": body.name,
        "description": body.description or "",
        "chakra_tier_link": body.chakra_tier_link,
        "factors": factors,
        "market_research_module_ids": body.market_research_module_ids or [],
        "tier_pricings": pricings,
        "created_at": _now(),
        "updated_at": _now(),
        "created_by": user.get("user_id"),
    }
    await db.customer_segments.insert_one(doc)
    _invalidate_pricing_cache()
    return {"ok": True, "segment": _segment_to_dict(doc)}


@router.get("/admin/customer-segments/{sid}")
async def admin_read(sid: str, user: dict = Depends(require_admin)):
    d = await db.customer_segments.find_one({"segment_id": sid}, {"_id": 0})
    if not d:
        raise HTTPException(404, "segment not found")
    return d


@router.put("/admin/customer-segments/{sid}")
async def admin_update(sid: str, body: CustomerSegmentUpdate, user: dict = Depends(require_admin)):
    upd: Dict[str, Any] = {"updated_at": _now()}
    if body.name is not None: upd["name"] = body.name
    if body.description is not None: upd["description"] = body.description
    if body.chakra_tier_link is not None: upd["chakra_tier_link"] = body.chakra_tier_link
    if body.factors is not None: upd["factors"] = [f.model_dump() for f in body.factors]
    if body.market_research_module_ids is not None: upd["market_research_module_ids"] = body.market_research_module_ids
    if body.tier_pricings is not None: upd["tier_pricings"] = [p.model_dump() for p in body.tier_pricings]
    res = await db.customer_segments.update_one({"segment_id": sid}, {"$set": upd})
    if res.matched_count == 0:
        raise HTTPException(404, "segment not found")
    d = await db.customer_segments.find_one({"segment_id": sid}, {"_id": 0})
    _invalidate_pricing_cache()
    return {"ok": True, "segment": d}


@router.delete("/admin/customer-segments/{sid}")
async def admin_delete(sid: str, user: dict = Depends(require_admin)):
    res = await db.customer_segments.delete_one({"segment_id": sid})
    if res.deleted_count == 0:
        raise HTTPException(404, "segment not found")
    _invalidate_pricing_cache()
    return {"ok": True}


# ----------------------------------------------------------------------
# Custom factor add/remove
# ----------------------------------------------------------------------
@router.post("/admin/customer-segments/{sid}/factor")
async def admin_add_factor(sid: str, body: FactorAddRequest, user: dict = Depends(require_admin)):
    d = await db.customer_segments.find_one({"segment_id": sid})
    if not d:
        raise HTTPException(404, "segment not found")
    factors = d.get("factors", [])
    if any(f.get("key") == body.key for f in factors):
        raise HTTPException(400, f"factor '{body.key}' already exists")
    factor = {
        "key": body.key,
        "label": body.label or body.key.replace("_", " ").title(),
        "category": body.category or "custom",
        "value": body.value or "",
        "ai_researchable": True,
        "is_custom": True,
    }
    factors.append(factor)
    await db.customer_segments.update_one(
        {"segment_id": sid}, {"$set": {"factors": factors, "updated_at": _now()}}
    )
    _invalidate_pricing_cache()
    return {"ok": True, "factor": factor}


@router.delete("/admin/customer-segments/{sid}/factor/{key}")
async def admin_remove_factor(sid: str, key: str, user: dict = Depends(require_admin)):
    d = await db.customer_segments.find_one({"segment_id": sid})
    if not d:
        raise HTTPException(404, "segment not found")
    factors = [f for f in d.get("factors", []) if f.get("key") != key]
    await db.customer_segments.update_one(
        {"segment_id": sid}, {"$set": {"factors": factors, "updated_at": _now()}}
    )
    _invalidate_pricing_cache()
    return {"ok": True}


# ----------------------------------------------------------------------
# AI Research — fetch values for a single factor using LLM
# ----------------------------------------------------------------------
async def _llm_research(segment_name: str, segment_desc: str, factor_label: str, extra: str) -> str:
    """Use Emergent LLM key to research one factor. Falls back to a static
    suggestion when budget is capped or library unavailable."""
    fallback_map = {
        "Age Range": "25–44",
        "Gender": "All",
        "Income Range": "₹6L–₹25L per annum",
        "Education Level": "Graduate / Post-graduate",
        "Occupation": "Knowledge worker / founder",
        "Location / Geo": "Tier-1 & Tier-2 Indian cities",
        "Family Status": "Single / married, 0–2 dependants",
        "Urban / Rural": "Predominantly urban",
        "Core Values": "Growth, autonomy, ambition, balance",
        "Interests / Hobbies": "Tech, productivity, fitness, travel",
        "Lifestyle": "Fast-paced, digital-first, mobile-first",
        "Personality Traits": "Driven, analytical, optimistic",
        "Attitudes / Beliefs": "Open to AI, evidence-driven",
        "Motivations": "Financial freedom, impact, mastery",
        "Pain Points": "Time scarcity, decision overload, burnout",
        "Buying Behaviour": "Researches online, peer-driven, subscription-friendly",
        "Brand Loyalty": "Moderate — switches if value drops",
        "Decision Drivers": "ROI, ease-of-use, social proof",
        "Tech Savviness": "High",
        "Company Size": "1–50 employees",
        "Industry": "SaaS / Services / Consulting",
        "Role / Title": "Founder / Consultant / Manager",
        "Annual Revenue": "₹10L–₹10Cr",
    }
    fallback = fallback_map.get(factor_label, "—")

    try:
        from core.llm_compat import LlmChat, UserMessage  # provider-agnostic shim (Emergent | direct via litellm)
        api_key = os.environ.get("EMERGENT_LLM_KEY")
        if not api_key:
            return fallback
        chat = LlmChat(
            api_key=api_key,
            session_id=f"cs_research_{uuid.uuid4().hex[:8]}",
            system_message=(
                "You are a market-research analyst. Given a customer segment and "
                "a single demographic/psychographic factor, return ONLY a concise "
                "one-line answer (max 20 words) that best describes the typical "
                "value for that factor. No preamble, no list, no markdown."
            ),
        ).with_model("openai", "gpt-4o-mini")
        prompt = (
            f"Segment: {segment_name}\n"
            f"Description: {segment_desc or '(none)'}\n"
            f"Factor: {factor_label}\n"
            f"Extra context: {extra or '(none)'}\n\n"
            f"Answer:"
        )
        out = await chat.send_message(UserMessage(text=prompt))
        text = (out or "").strip()
        return text or fallback
    except Exception:
        return fallback


@router.post("/admin/customer-segments/{sid}/ai-research")
async def admin_ai_research(sid: str, body: AIResearchRequest, user: dict = Depends(require_admin)):
    d = await db.customer_segments.find_one({"segment_id": sid})
    if not d:
        raise HTTPException(404, "segment not found")
    factor = next((f for f in d.get("factors", []) if f.get("key") == body.factor_key), None)
    if not factor:
        raise HTTPException(404, f"factor '{body.factor_key}' not on segment")
    label = factor.get("label") or body.factor_key
    val = await _llm_research(d.get("name", ""), d.get("description", ""), label, body.extra_context or "")
    # Persist
    factors = d.get("factors", [])
    for f in factors:
        if f.get("key") == body.factor_key:
            f["value"] = val
            f["last_researched_at"] = _now().isoformat()
            break
    await db.customer_segments.update_one(
        {"segment_id": sid}, {"$set": {"factors": factors, "updated_at": _now()}}
    )
    return {"ok": True, "factor_key": body.factor_key, "value": val}


# ----------------------------------------------------------------------
# Tier pricing upsert (multi-currency / multi-country)
# ----------------------------------------------------------------------
@router.put("/admin/customer-segments/{sid}/pricing")
async def admin_upsert_pricing(sid: str, body: TierPricingUpsert, user: dict = Depends(require_admin)):
    for p in body.tier_pricings:
        if p.tier_key not in TIER_KEYS:
            raise HTTPException(400, f"unknown tier_key '{p.tier_key}'")
    res = await db.customer_segments.update_one(
        {"segment_id": sid},
        {"$set": {"tier_pricings": [p.model_dump() for p in body.tier_pricings],
                  "updated_at": _now()}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "segment not found")
    _invalidate_pricing_cache()
    return {"ok": True, "count": len(body.tier_pricings)}
