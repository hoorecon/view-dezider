"""SWOT Analysis Module — 8-step decision framework (mirrors Pros & Cons).

Legacy quadrants (strengths/weaknesses/opportunities/threats) and convert-to-decision
are preserved.  8-step flow uses the same shape as Pros & Cons (options with
pros & cons per option), letting both modules share the same wizard UI.
"""

import uuid
import os
import json as json_module
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from core.trash import move_to_trash
from core.auth import get_current_user

from models.decision_framework_models import (
    DecisionOption,
    FrameworkFactor,
    FrameworkConfig,
    AssessmentCell,
    FINAL_DECISION_GUIDELINES,
    compute_cell_value,
    compute_realistic_rating,
    compute_satisfaction_value,
    compute_option_rollups,
)
from data.hos_seed_data import LIFE_AREAS as _HOS_LIFE_AREAS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/swot", tags=["SWOT Analysis"])

# Lookup: bare slug ("career") OR human label ("Career") → canonical id ("la_career").
# Used by save-as-template to ensure the new template is discoverable by
# /api/hos/templates/suggest, which keys off the canonical `life_area_id`.
_LIFE_AREA_SLUG_TO_ID: Dict[str, str] = {}
for _la in _HOS_LIFE_AREAS:
    _LIFE_AREA_SLUG_TO_ID[_la["slug"]] = _la["id"]
    _LIFE_AREA_SLUG_TO_ID[_la["id"]] = _la["id"]
    _LIFE_AREA_SLUG_TO_ID[_la["name"].lower()] = _la["id"]


def _normalize_life_area_id(value: Optional[str]) -> str:
    """Map a SWOT's stored life_area (slug, id, or label) → canonical la_* id.

    Returns "" if the value cannot be resolved — callers should treat that as
    "no life area set".
    """
    if not value:
        return ""
    v = str(value).strip()
    if not v:
        return ""
    # Already canonical (e.g. "la_career") — keep as-is.
    if v.startswith("la_"):
        return v
    return _LIFE_AREA_SLUG_TO_ID.get(v, _LIFE_AREA_SLUG_TO_ID.get(v.lower(), ""))


def _now():
    return datetime.now(timezone.utc)


async def _load_swot(analysis_id: str, user_id: str) -> Dict[str, Any]:
    doc = await db.swot_analyses.find_one({"id": analysis_id, "user_id": user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="SWOT analysis not found")
    doc.setdefault("options", [])
    doc.setdefault("factors", [])
    doc.setdefault("assessments", {})
    doc.setdefault("config", FrameworkConfig().dict())
    doc.setdefault("current_step", 1)
    return doc


async def _persist_swot(analysis_id: str, user_id: str, patch: Dict[str, Any]):
    patch["updated_at"] = _now()
    await db.swot_analyses.update_one({"id": analysis_id, "user_id": user_id}, {"$set": patch})


# ========================
# MODELS
# ========================

class SwotItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    description: str = ""
    impact: int = 5  # 1-10


class SwotCreate(BaseModel):
    title: str
    context: str = ""
    life_area: Optional[str] = None
    decision_type: Optional[str] = None


class SwotUpdate(BaseModel):
    title: Optional[str] = None
    context: Optional[str] = None
    strengths: Optional[List[SwotItem]] = None
    weaknesses: Optional[List[SwotItem]] = None
    opportunities: Optional[List[SwotItem]] = None
    threats: Optional[List[SwotItem]] = None
    life_area: Optional[str] = None
    decision_type: Optional[str] = None


# ========================
# CRUD ROUTES
# ========================

@router.post("")
async def create_swot(data: SwotCreate, user: dict = Depends(get_current_user)):
    """Create a new SWOT analysis (also seeds the 8-step framework containers)."""
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "title": data.title,
        "context": data.context,
        "life_area": data.life_area,
        "decision_type": data.decision_type,
        # Legacy quadrants
        "strengths": [],
        "weaknesses": [],
        "opportunities": [],
        "threats": [],
        # 8-step framework containers (same shape as Pros & Cons)
        "options": [],
        "factors": [],
        "assessments": {},
        "config": FrameworkConfig().dict(),
        "current_step": 1,
        "rollups": [],
        "converted_decision_id": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.swot_analyses.insert_one(doc)
    return {"id": doc["id"], "message": "SWOT analysis created"}


@router.get("")
async def list_swot(user: dict = Depends(get_current_user)):
    """List all SWOT analyses for the user"""
    docs = await db.swot_analyses.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return docs


@router.get("/{analysis_id}")
async def get_swot(analysis_id: str, user: dict = Depends(get_current_user)):
    """Get a specific SWOT analysis"""
    doc = await db.swot_analyses.find_one(
        {"id": analysis_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="SWOT analysis not found")
    return doc


@router.put("/{analysis_id}")
async def update_swot(analysis_id: str, data: SwotUpdate, user: dict = Depends(get_current_user)):
    """Update a SWOT analysis"""
    existing = await db.swot_analyses.find_one(
        {"id": analysis_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="SWOT analysis not found")
    update_dict = {k: v for k, v in data.dict().items() if v is not None}
    for key in ["strengths", "weaknesses", "opportunities", "threats"]:
        if key in update_dict:
            update_dict[key] = [item if isinstance(item, dict) else item.dict() for item in update_dict[key]]
    update_dict["updated_at"] = datetime.now(timezone.utc)
    await db.swot_analyses.update_one({"id": analysis_id}, {"$set": update_dict})
    return {"message": "SWOT analysis updated"}


@router.delete("/{analysis_id}")
async def delete_swot(analysis_id: str, user: dict = Depends(get_current_user)):
    """Delete a SWOT analysis (moves to Trash)"""
    moved = await move_to_trash("swot", analysis_id, user["user_id"])
    if not moved:
        raise HTTPException(status_code=404, detail="SWOT analysis not found")
    return {"message": "SWOT analysis moved to Trash"}


# ========================
# SAVE AS TEMPLATE (Phase 2)
# ========================

class SwotSaveAsTemplateRequest(BaseModel):
    """Payload for POST /swot/{analysis_id}/save-as-template.

    `name` is required and becomes the template title. `description` is optional
    and shows in the template-picker. `is_public=True` makes the template
    discoverable by all users (subject to admin moderation); otherwise the
    template stays private to the creator.
    """
    name: str
    description: str = ""
    is_public: bool = False


@router.post("/{analysis_id}/save-as-template")
async def save_swot_as_template(
    analysis_id: str,
    data: SwotSaveAsTemplateRequest,
    user: dict = Depends(get_current_user),
):
    """Promote a SWOT analysis into a reusable v2 template.

    The new doc lives in `hos_decision_templates` so it can be surfaced by the
    standard `/hos/templates/suggest?module=swot` endpoint used by the new
    intake flow.

    Factor shape preserves the SWOT-flag per item:
        factors: [{
            id, name, swot_flag: 'S'|'W'|'O'|'T',
            polarity: 'positive' | 'negative',
            internal_external: 'internal' | 'external',
            description, weightage
        }, ...]

    Wildcards (`org_types=[]`, `decision_types=[]`) keep the template eligible
    for any caller until an admin curates it.
    """
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="Template name is required")

    swot = await db.swot_analyses.find_one(
        {"id": analysis_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not swot:
        raise HTTPException(status_code=404, detail="SWOT analysis not found")

    # Aggregate the 4 quadrants into a single factor list, preserving flag.
    QUADRANT_META = [
        ("strengths",     "S", "positive", "internal"),
        ("weaknesses",    "W", "negative", "internal"),
        ("opportunities", "O", "positive", "external"),
        ("threats",       "T", "negative", "external"),
    ]
    factors: List[Dict[str, Any]] = []
    for key, flag, polarity, ie in QUADRANT_META:
        for item in (swot.get(key) or []):
            factors.append({
                "id": item.get("id") or str(uuid.uuid4()),
                "name": item.get("text", ""),
                "description": item.get("description", ""),
                "swot_flag": flag,
                "polarity": polarity,
                "internal_external": ie,
                "weightage": item.get("impact", 5),
            })

    if not factors:
        raise HTTPException(
            status_code=400,
            detail="Add at least one S/W/O/T item before saving as template",
        )

    # Map decision_type → derived decision_types[] (legacy + v2 compat).
    dt = (swot.get("decision_type") or "").lower()
    decision_types = [dt] if dt in ("problem", "need", "aspiration") else []

    template_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    template_doc = {
        "id": template_id,
        "title": data.name.strip(),
        "description": data.description.strip()
            or f"Saved from SWOT analysis: {swot.get('title', '')}",
        "template_type": "AUTHORIZED_STANDARD" if user.get("role") in (
            "super_admin", "co_admin", "admin"
        ) else "CUSTOM_BLANK",
        "status": "active",
        "popularity": 0,
        "order": 0,
        # Taxonomy v2 fields
        "applies_to_modules": ["swot"],
        "org_types": [],          # wildcard — admin can narrow later
        "decision_types": decision_types,
        # Legacy compatibility — derive single-value fields so the existing
        # /hos/templates filter (without the v2 query) still finds this doc.
        "acting_as_contexts": ["INDIVIDUAL"],
        "ask_type_id": f"at_{dt}" if dt else "at_problem",
        "life_area_id": _normalize_life_area_id(swot.get("life_area")),
        "sub_area_id": None,
        "category_id": None,
        # Authorship + audit
        "factors": factors,
        "is_public": bool(data.is_public),
        "visibility": "PUBLIC" if data.is_public else "PRIVATE",
        "approval_status": "approved" if user.get("role") in (
            "super_admin", "co_admin", "admin"
        ) else "pending",
        "created_by": user["user_id"],
        "created_by_name": user.get("name", "Unknown"),
        "source_swot_analysis_id": analysis_id,
        "created_at": now,
        "updated_at": now,
    }

    await db.hos_decision_templates.insert_one(template_doc)
    logger.info(
        "SWOT %s saved as template %s by user %s (%d factors, public=%s)",
        analysis_id, template_id, user["user_id"], len(factors), data.is_public,
    )
    return {
        "id": template_id,
        "template_id": template_id,
        "factor_count": len(factors),
        "message": "Template saved successfully",
    }


# ========================
# CONVERT TO PRR DECISION
# ========================

@router.post("/{analysis_id}/convert-to-decision")
async def convert_to_decision(analysis_id: str, user: dict = Depends(get_current_user)):
    """Convert SWOT analysis into a PRR Decision with AI-generated expected values.
    
    - Strengths (internal positive) → factors as-is
    - Opportunities (external positive) → factors as-is
    - Weaknesses (internal negative) → prefixed with 'NOT '
    - Threats (external negative) → prefixed with 'NOT '
    - AI generates expected values for all factors
    """
    doc = await db.swot_analyses.find_one(
        {"id": analysis_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="SWOT analysis not found")

    strengths = doc.get("strengths", [])
    weaknesses = doc.get("weaknesses", [])
    opportunities = doc.get("opportunities", [])
    threats = doc.get("threats", [])

    total = len(strengths) + len(weaknesses) + len(opportunities) + len(threats)
    if total == 0:
        raise HTTPException(status_code=400, detail="Add at least one item in any SWOT quadrant before converting")

    # Build factor list with source metadata
    raw_factors = []
    order = 0

    for s in strengths:
        raw_factors.append({
            "name": s["text"],
            "source": "strength",
            "nature": "internal",
            "polarity": "positive",
            "description": s.get("description", ""),
            "importance": s.get("impact", 5),
            "order": order,
        })
        order += 1

    for o in opportunities:
        raw_factors.append({
            "name": o["text"],
            "source": "opportunity",
            "nature": "external",
            "polarity": "positive",
            "description": o.get("description", ""),
            "importance": o.get("impact", 5),
            "order": order,
        })
        order += 1

    for w in weaknesses:
        raw_factors.append({
            "name": f"SHOULD NOT - {w['text']}",
            "source": "weakness",
            "nature": "internal",
            "polarity": "negative",
            "description": w.get("description", ""),
            "importance": w.get("impact", 5),
            "order": order,
        })
        order += 1

    for t in threats:
        raw_factors.append({
            "name": f"SHOULD NOT - {t['text']}",
            "source": "threat",
            "nature": "external",
            "polarity": "negative",
            "description": t.get("description", ""),
            "importance": t.get("impact", 5),
            "order": order,
        })
        order += 1

    # AI-generate expected values
    factors_with_values = await _ai_generate_expected_values(
        doc["title"], doc.get("context", ""), raw_factors, user["user_id"]
    )

    # Create PRR Decision
    decision_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    prr_factors = []
    for idx, f in enumerate(factors_with_values):
        prr_factors.append({
            "id": str(uuid.uuid4()),
            "name": f["name"],
            "category": "primary" if f.get("polarity") == "positive" else "secondary",
            "rating": f["importance"],
            "order": idx,
            "unit": f.get("unit"),
            "expected_value": f.get("expected_value"),
            "data_type": f.get("data_type"),
            "operator": None,
            "gap_multiplier": 1.0,
            "parent_id": None,
            "weight": None,
        })

    s_count = len(strengths)
    w_count = len(weaknesses)
    o_count = len(opportunities)
    t_count = len(threats)

    # SWOT-converted Decisions operate in SINGLE-OPTION mode: there's just
    # one implicit option representing the user's current state. We seed it
    # here so Steps 6/7/9/10 don't render an empty options list.
    # Format (local-readable, sortable):  "Current Scenario - YYYY-MM-DD HH:MM"
    current_scenario_option = {
        "id": str(uuid.uuid4()),
        "name": f"Current Scenario - {now.strftime('%Y-%m-%d %H:%M')}",
        "description": "Auto-created from SWOT conversion. Rename if you'd like.",
        "order": 0,
        "is_default_scenario": True,  # flag used by frontend to lock the option list
        # CRITICAL: must be present — `calculateDynamicWorth` reads
        # `option.assessments.find(...)`. Missing array → blank-page crash.
        "assessments": [],
    }

    decision_doc = {
        "id": decision_id,
        "user_id": user["user_id"],
        "title": doc["title"],
        "context": doc.get("context", ""),
        "factors": prr_factors,
        "options": [current_scenario_option],
        "chosen_option_id": None,
        "decision_case": None,
        "notes": f"Converted from SWOT Analysis. S:{s_count} W:{w_count} O:{o_count} T:{t_count}.",
        "reflection": "",
        "final_notes": "",
        "folder": "",
        "life_area": doc.get("life_area"),
        "decision_type": doc.get("decision_type"),
        "rating_gap_multiplier": 1.0,
        "mpps_option_id": current_scenario_option["id"],  # MPPS always targets the lone option
        "mpps_improvements": [],
        "mpps_projected_worth": None,
        "mpps_timeframe": None,
        "implementation_review_date": None,
        "status": "in_progress",
        "source_module": "swot",
        "source_id": analysis_id,
        # SWOT-converted decisions intentionally have ONLY the lone "Current
        # Scenario" option. Pre-set the single-option flag so Step 7 doesn't
        # prompt the user with the "only one option — proceed?" confirmation.
        "allow_single_option": True,
        # Force /prr/[id] to open on Step 2 (Define Factors), regardless of how
        # much pre-fill we've done. User can step forward through the
        # AI-suggested classifications, priorities, ratings and override at
        # any point.
        "current_step": 2,
        "created_at": now,
        "updated_at": now,
    }

    await db.decisions.insert_one(decision_doc)
    await db.swot_analyses.update_one(
        {"id": analysis_id},
        {"$set": {"converted_decision_id": decision_id, "updated_at": now}}
    )
    try:
        from routes.sku_store import ensure_decision_entitlement
        await ensure_decision_entitlement(user["user_id"], module="dezider", decision_id=decision_id)
    except Exception as _e:
        logger.warning("entitlement consume on swot convert failed: %s", _e)

    return {
        "decision_id": decision_id,
        "factors_count": len(prr_factors),
        "message": f"Created PRR Decision with {len(prr_factors)} factors from SWOT (S:{s_count} W:{w_count} O:{o_count} T:{t_count})",
    }


async def _ai_generate_expected_values(title: str, context: str, raw_factors: list, user_id: str) -> list:
    """Use AI to generate expected values for each factor."""
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        return raw_factors

    try:
        from core.llm_compat import LlmChat, UserMessage  # provider-agnostic shim (Emergent | direct via litellm)

        factor_lines = []
        for f in raw_factors:
            source_label = f.get("source", "")
            nature = f.get("nature", "")
            factor_lines.append(
                f"- {f['name']} (source: {source_label}/{nature}, impact: {f['importance']}/10, desc: {f.get('description', '')})"
            )

        prompt = f"""You are a decision analysis expert. For the following decision, generate realistic expected values for each factor derived from a SWOT analysis.

Decision: {title}
Context: {context}

Factors (derived from SWOT — strengths/opportunities become positive factors, weaknesses/threats are prefixed with NOT to represent desired absence):
{chr(10).join(factor_lines)}

For EACH factor, provide:
1. expected_value: A realistic target/benchmark value (string). For "NOT X" factors, the expected value should represent the ideal state (e.g., "NOT High Employee Turnover" → expected_value: "< 5% annual turnover")
2. unit: The measurement unit (e.g., "INR", "hours", "rating/10", "percentage", "count", "yes/no")
3. data_type: "quantitative" or "qualitative"

Return ONLY a valid JSON array, one object per factor, in the SAME ORDER:
[{{{{
  "name": "factor name",
  "expected_value": "value",
  "unit": "unit",
  "data_type": "quantitative|qualitative"
}}}}]

Return ONLY valid JSON, no markdown fences."""

        chat = LlmChat(
            api_key=api_key,
            session_id=f"swot_{user_id}_{uuid.uuid4().hex[:8]}",
            system_message="You are a decision analysis expert. Return only valid JSON arrays."
        ).with_model("openai", "gpt-4.1-mini")

        response = await chat.send_message(UserMessage(text=prompt))
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        ai_values = json_module.loads(response_text)

        for i, f in enumerate(raw_factors):
            if i < len(ai_values):
                ai = ai_values[i]
                f["expected_value"] = ai.get("expected_value", "")
                f["unit"] = ai.get("unit", "")
                f["data_type"] = ai.get("data_type", "qualitative")

        return raw_factors

    except Exception as e:
        logger.error(f"AI expected value generation failed for SWOT: {e}")
        return raw_factors


# ════════════════════════════════════════════════════════════════════
#         8-STEP FRAMEWORK ENDPOINTS  (mirrors pros_cons.py)
# ════════════════════════════════════════════════════════════════════

@router.post("/{analysis_id}/factors")
async def swot_add_factor(analysis_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    doc = await _load_swot(analysis_id, user["user_id"])
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Factor name is required")
    factor = FrameworkFactor(name=name, expected_value=body.get("expected_value"),
                             unit=body.get("unit"), parent_id=body.get("parent_id"),
                             source="direct").dict()
    factor["priority_rank"] = len(doc["factors"]) + 1
    doc["factors"].append(factor)
    await _persist_swot(analysis_id, user["user_id"], {"factors": doc["factors"]})
    return {"id": factor["id"], "factor": factor}


@router.put("/{analysis_id}/factors/{factor_id}")
async def swot_update_factor(analysis_id: str, factor_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    doc = await _load_swot(analysis_id, user["user_id"])
    factors = doc["factors"]
    idx = next((i for i, f in enumerate(factors) if f["id"] == factor_id), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Factor not found")
    allowed = {"name", "expected_value", "unit", "parent_id", "notation", "priority_rank",
               "std_rating", "factor_type", "improvable", "my_expectation",
               "others_expectations", "market_standard", "realistic_gap_pct",
               "realistic_gap_value", "notes",
               "is_duplicate",   # Step 4 — soft de-dup flag (audit history)
               "display_name",   # Step 5+ rename override; original `name` preserved
               "priority_gap_pct"}  # Step 7 — per-pair gap above the next lower factor
    for k, v in body.items():
        if k in allowed:
            factors[idx][k] = v
    factors[idx]["realistic_rating"] = compute_realistic_rating(
        int(factors[idx].get("std_rating") or 0),
        float(factors[idx].get("realistic_gap_pct") or 0.0),
    )
    await _persist_swot(analysis_id, user["user_id"], {"factors": factors})
    return {"factor": factors[idx]}


@router.delete("/{analysis_id}/factors/{factor_id}")
async def swot_delete_factor(analysis_id: str, factor_id: str, user: dict = Depends(get_current_user)):
    doc = await _load_swot(analysis_id, user["user_id"])
    factors = [f for f in doc["factors"] if f["id"] != factor_id and f.get("parent_id") != factor_id]
    assessments = doc.get("assessments", {}) or {}
    for cells in assessments.values():
        cells.pop(factor_id, None)
    await _persist_swot(analysis_id, user["user_id"], {"factors": factors, "assessments": assessments})
    return {"deleted": True}


@router.post("/{analysis_id}/factors/reorder")
async def swot_reorder_factors(analysis_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    """Same auto-ladder std_rating behaviour as pros_cons (kept in parity).

    See /app/backend/routes/pros_cons.py reorder_factors() for the rationale.
    """
    doc = await _load_swot(analysis_id, user["user_id"])
    ordered = body.get("ordered_ids") or []
    rank_map = {fid: i + 1 for i, fid in enumerate(ordered)}
    for f in doc["factors"]:
        if f["id"] in rank_map:
            f["priority_rank"] = rank_map[f["id"]]
    doc["factors"].sort(key=lambda f: f.get("priority_rank", 999))

    # Auto-ladder std_rating using PER-PAIR priority_gap_pct (see pros_cons
    # reorder_factors() for the full rationale).
    cfg = doc.get("config") or {}
    base_gap = int(cfg.get("std_gap") or 10)
    mains = [f for f in doc["factors"] if not f.get("parent_id") and not f.get("is_duplicate")]
    if mains:
        bottom_to_top = list(reversed(mains))
        bottom_to_top[0]["std_rating"] = base_gap
        running = float(base_gap)
        for i in range(1, len(bottom_to_top)):
            gap_pct = float(bottom_to_top[i].get("priority_gap_pct") or 100.0)
            running += (gap_pct / 100.0) * base_gap
            bottom_to_top[i]["std_rating"] = int(round(running))
    for f in doc["factors"]:
        if f.get("parent_id") or f.get("is_duplicate"):
            f["std_rating"] = 0
    for f in doc["factors"]:
        f["realistic_rating"] = compute_realistic_rating(
            int(f.get("std_rating") or 0),
            float(f.get("realistic_gap_pct") or 0.0),
        )

    await _persist_swot(analysis_id, user["user_id"], {"factors": doc["factors"]})
    return {"factors": doc["factors"]}


@router.post("/{analysis_id}/factors/recalc-ladder")
async def swot_recalc_ladder(analysis_id: str, user: dict = Depends(get_current_user)):
    """SWOT parity of the per-pair ladder recalculation. See pros_cons.recalc_ladder."""
    doc = await _load_swot(analysis_id, user["user_id"])
    cfg = doc.get("config") or {}
    base_gap = int(cfg.get("std_gap") or 10)
    mains = sorted(
        [f for f in doc["factors"] if not f.get("parent_id") and not f.get("is_duplicate")],
        key=lambda f: f.get("priority_rank", 999),
    )
    if mains:
        bottom_to_top = list(reversed(mains))
        bottom_to_top[0]["std_rating"] = base_gap
        running = float(base_gap)
        for i in range(1, len(bottom_to_top)):
            gap_pct = float(bottom_to_top[i].get("priority_gap_pct") or 100.0)
            running += (gap_pct / 100.0) * base_gap
            bottom_to_top[i]["std_rating"] = int(round(running))
    for f in doc["factors"]:
        if f.get("parent_id") or f.get("is_duplicate"):
            f["std_rating"] = 0
        f["realistic_rating"] = compute_realistic_rating(
            int(f.get("std_rating") or 0),
            float(f.get("realistic_gap_pct") or 0.0),
        )
    await _persist_swot(analysis_id, user["user_id"], {"factors": doc["factors"]})
    return {"factors": doc["factors"]}


@router.post("/{analysis_id}/options")
async def swot_add_option(analysis_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    doc = await _load_swot(analysis_id, user["user_id"])
    opt = DecisionOption(
        name=(body.get("name") or "").strip() or f"Option {len(doc['options']) + 1}",
        description=body.get("description") or "",
        order=len(doc["options"]),
    ).dict()
    doc["options"].append(opt)
    await _persist_swot(analysis_id, user["user_id"], {"options": doc["options"]})
    return {"id": opt["id"], "option": opt}


@router.delete("/{analysis_id}/options/{option_id}")
async def swot_delete_option(analysis_id: str, option_id: str, user: dict = Depends(get_current_user)):
    doc = await _load_swot(analysis_id, user["user_id"])
    opts = [o for o in doc["options"] if o["id"] != option_id]
    assessments = doc.get("assessments", {}) or {}
    assessments.pop(option_id, None)
    await _persist_swot(analysis_id, user["user_id"], {"options": opts, "assessments": assessments})
    return {"deleted": True}


def _swot_add_pc_helper(doc, option_id, body, kind):
    opts = doc["options"]
    idx = next((i for i, o in enumerate(opts) if o["id"] == option_id), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Option not found")
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail=f"{kind} text required")
    item = {"id": str(uuid.uuid4()), "text": text, "description": body.get("description", ""),
            "importance": int(body.get("importance", 5)), "promoted_factor_id": None}
    opts[idx].setdefault(kind, []).append(item)
    return item


@router.post("/{analysis_id}/options/{option_id}/pros")
async def swot_add_pro(analysis_id: str, option_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    doc = await _load_swot(analysis_id, user["user_id"])
    item = _swot_add_pc_helper(doc, option_id, body, "pros")
    await _persist_swot(analysis_id, user["user_id"], {"options": doc["options"]})
    return item


@router.post("/{analysis_id}/options/{option_id}/cons")
async def swot_add_con(analysis_id: str, option_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    doc = await _load_swot(analysis_id, user["user_id"])
    item = _swot_add_pc_helper(doc, option_id, body, "cons")
    await _persist_swot(analysis_id, user["user_id"], {"options": doc["options"]})
    return item


@router.delete("/{analysis_id}/options/{option_id}/pros/{item_id}")
async def swot_del_pro(analysis_id: str, option_id: str, item_id: str, user: dict = Depends(get_current_user)):
    doc = await _load_swot(analysis_id, user["user_id"])
    for o in doc["options"]:
        if o["id"] == option_id:
            o["pros"] = [p for p in o.get("pros", []) if p["id"] != item_id]
    await _persist_swot(analysis_id, user["user_id"], {"options": doc["options"]})
    return {"deleted": True}


@router.delete("/{analysis_id}/options/{option_id}/cons/{item_id}")
async def swot_del_con(analysis_id: str, option_id: str, item_id: str, user: dict = Depends(get_current_user)):
    doc = await _load_swot(analysis_id, user["user_id"])
    for o in doc["options"]:
        if o["id"] == option_id:
            o["cons"] = [c for c in o.get("cons", []) if c["id"] != item_id]
    await _persist_swot(analysis_id, user["user_id"], {"options": doc["options"]})
    return {"deleted": True}


# ── Step #2 — Edit existing Pro / Con text (inline rename) — SWOT parity ──
@router.put("/{analysis_id}/options/{option_id}/pros/{item_id}")
async def swot_update_pro(analysis_id: str, option_id: str, item_id: str,
                          body: Dict[str, Any], user: dict = Depends(get_current_user)):
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Pro text cannot be empty")
    doc = await _load_swot(analysis_id, user["user_id"])
    found = False
    for o in doc["options"]:
        if o["id"] == option_id:
            for p in o.get("pros", []):
                if p["id"] == item_id:
                    p["text"] = text
                    found = True
                    break
    if not found:
        raise HTTPException(status_code=404, detail="Pro not found")
    await _persist_swot(analysis_id, user["user_id"], {"options": doc["options"]})
    return {"updated": True}


@router.put("/{analysis_id}/options/{option_id}/cons/{item_id}")
async def swot_update_con(analysis_id: str, option_id: str, item_id: str,
                          body: Dict[str, Any], user: dict = Depends(get_current_user)):
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Con text cannot be empty")
    doc = await _load_swot(analysis_id, user["user_id"])
    found = False
    for o in doc["options"]:
        if o["id"] == option_id:
            for c in o.get("cons", []):
                if c["id"] == item_id:
                    c["text"] = text
                    found = True
                    break
    if not found:
        raise HTTPException(status_code=404, detail="Con not found")
    await _persist_swot(analysis_id, user["user_id"], {"options": doc["options"]})
    return {"updated": True}


@router.put("/{analysis_id}/options/{option_id}")
async def swot_update_option(analysis_id: str, option_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    doc = await _load_swot(analysis_id, user["user_id"])
    opts = doc["options"]
    idx = next((i for i, o in enumerate(opts) if o["id"] == option_id), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Option not found")
    for k in ("name", "description"):
        if k in body:
            opts[idx][k] = body[k]
    await _persist_swot(analysis_id, user["user_id"], {"options": opts})
    return {"option": opts[idx]}


@router.post("/{analysis_id}/promote-pros-cons")
async def swot_promote(analysis_id: str, user: dict = Depends(get_current_user)):
    doc = await _load_swot(analysis_id, user["user_id"])
    factors = doc["factors"]
    promoted = 0
    next_rank = (max((f.get("priority_rank") or 0) for f in factors) + 1) if factors else 1
    for opt in doc["options"]:
        for p in opt.get("pros", []):
            if p.get("promoted_factor_id"):
                continue
            fid = str(uuid.uuid4())
            factors.append(FrameworkFactor(
                id=fid, name=p["text"], source="pro", source_option_id=opt["id"],
                source_item_id=p["id"], std_rating=int((p.get("importance") or 5) * 10),
                priority_rank=next_rank).dict())
            p["promoted_factor_id"] = fid
            next_rank += 1
            promoted += 1
        for c in opt.get("cons", []):
            if c.get("promoted_factor_id"):
                continue
            fid = str(uuid.uuid4())
            factors.append(FrameworkFactor(
                id=fid, name=f"SHOULD NOT - {c['text']}", source="con",
                source_option_id=opt["id"], source_item_id=c["id"],
                std_rating=int((c.get("importance") or 5) * 10),
                priority_rank=next_rank).dict())
            c["promoted_factor_id"] = fid
            next_rank += 1
            promoted += 1
    await _persist_swot(analysis_id, user["user_id"], {"factors": factors, "options": doc["options"]})
    return {"promoted_count": promoted, "total_factors": len(factors)}


@router.put("/{analysis_id}/config")
async def swot_update_config(analysis_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    doc = await _load_swot(analysis_id, user["user_id"])
    cfg = doc.get("config") or FrameworkConfig().dict()
    for k in ("mandatory_threshold_pct", "max_improvement_period_months", "std_gap"):
        if k in body:
            cfg[k] = body[k]
    # Top-level analysis-scoped flags (kept outside config blob).
    extra: Dict[str, Any] = {}
    for k in ("step7_alpha_seeded",):
        if k in body:
            extra[k] = bool(body[k])
    await _persist_swot(analysis_id, user["user_id"], {"config": cfg, **extra})
    return {"config": cfg, **extra}


@router.put("/{analysis_id}/assessments/{option_id}/{factor_id}")
async def swot_upsert_assessment(analysis_id: str, option_id: str, factor_id: str,
                                  body: Dict[str, Any], user: dict = Depends(get_current_user)):
    """Field-level $set so concurrent partial updates (e.g. actual_value &
    assessment_pct flushed in parallel by DebouncedInput on Step 7→8
    transitions) don't clobber each other. See pros_cons.upsert_assessment
    for the full rationale."""
    doc = await _load_swot(analysis_id, user["user_id"])
    factor = next((f for f in doc["factors"] if f["id"] == factor_id), None)
    if not factor:
        raise HTTPException(status_code=404, detail="Factor not found")
    if not any(o["id"] == option_id for o in doc["options"]):
        raise HTTPException(status_code=404, detail="Option not found")

    allowed_keys = {"assessment_pct", "actual_value", "satisfaction_pct", "improvement_pct", "notes"}
    field_updates: Dict[str, Any] = {}
    for k in allowed_keys:
        if k in body:
            field_updates[f"assessments.{option_id}.{factor_id}.{k}"] = body[k]

    assessments = doc.get("assessments") or {}
    existing_cell = (assessments.get(option_id) or {}).get(factor_id)
    if not existing_cell:
        defaults = AssessmentCell().dict()
        for k, v in defaults.items():
            path = f"assessments.{option_id}.{factor_id}.{k}"
            if path not in field_updates:
                field_updates[path] = v

    if field_updates:
        await db.swot.update_one(
            {"id": analysis_id, "user_id": user["user_id"]},
            {"$set": field_updates},
        )

    reread = await db.swot.find_one(
        {"id": analysis_id, "user_id": user["user_id"]},
        {f"assessments.{option_id}.{factor_id}": 1},
    )
    cell = ((reread or {}).get("assessments", {}).get(option_id) or {}).get(factor_id) or AssessmentCell().dict()
    derived_cell_value = compute_cell_value(int(cell.get("assessment_pct", 0) or 0),
                                             int(factor.get("std_rating", 0) or 0))
    derived_sat_value = compute_satisfaction_value(
        factor.get("realistic_rating") or factor.get("std_rating"),
        float(cell.get("satisfaction_pct", 0.0) or 0.0))
    cell["cell_value"] = derived_cell_value
    cell["satisfaction_value"] = derived_sat_value
    await db.swot.update_one(
        {"id": analysis_id, "user_id": user["user_id"]},
        {"$set": {
            f"assessments.{option_id}.{factor_id}.cell_value": derived_cell_value,
            f"assessments.{option_id}.{factor_id}.satisfaction_value": derived_sat_value,
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    return {"cell": cell}


@router.get("/{analysis_id}/aggregate")
async def swot_aggregate(analysis_id: str, user: dict = Depends(get_current_user)):
    doc = await _load_swot(analysis_id, user["user_id"])
    rollups = compute_option_rollups(doc["factors"], doc.get("assessments", {}) or {},
                                      doc["options"], doc.get("config"))
    await _persist_swot(analysis_id, user["user_id"], {"rollups": rollups})
    return {"rollups": rollups, "factors": doc["factors"], "options": doc["options"],
            "config": doc.get("config", FrameworkConfig().dict()),
            "final_decision_guidelines": FINAL_DECISION_GUIDELINES}


@router.post("/{analysis_id}/step")
async def swot_set_step(analysis_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    step = max(1, min(8, int(body.get("step") or 1)))
    await _persist_swot(analysis_id, user["user_id"], {"current_step": step})
    return {"current_step": step}

