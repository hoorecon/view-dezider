"""
HOS Decision Intake Layer - Backend Routes
Implements the foundational Decision Engine catalog:
  Level 1: Life Areas (10)
  Level 2: Ask Types (Problem/Need/Aspiration)
  Level 3: Sub-Areas (3-7 per Life Area)
  Level 4: Decision Categories (5-10 per Sub-Area)
  Level 5: Decision Scenarios / Templates (with prefilled factors)
  Level 6: Optional CLD/intelligence layer (placeholder for future)
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid
import re

# Import shared dependencies
from core.database import db
from core.auth import get_current_user

router = APIRouter(prefix="/hos", tags=["HOS Decision Intake"])

# ========================
# ENUMS / CONSTANTS
# ========================

ACTING_AS_CONTEXTS = ["INDIVIDUAL", "ORGANIZATION", "GOVERNMENT"]
ASK_TYPES = ["PROBLEM", "NEED", "ASPIRATION"]
TEMPLATE_TYPES = ["AUTHORIZED_STANDARD", "DYNAMIC_CLD_STARTER", "CUSTOM_BLANK"]
ORG_TYPES = ["BUSINESS", "NONPROFIT", "GOVERNMENT"]

# ========================
# PYDANTIC MODELS
# ========================

class DecisionCreateFromTemplate(BaseModel):
    acting_as_context: str  # INDIVIDUAL / ORGANIZATION / GOVERNMENT
    life_area_id: str
    ask_type_id: str
    sub_area_id: Optional[str] = None
    category_id: Optional[str] = None
    template_id: Optional[str] = None  # if null, custom blank
    title: str
    raw_user_input: Optional[str] = ""
    source_type: str = "CUSTOM_BLANK"  # AUTHORIZED_STANDARD / DYNAMIC_CLD_STARTER / CUSTOM_BLANK

# ========================
# MASTER DATA ENDPOINTS
# ========================

@router.get("/life-areas")
async def list_life_areas():
    """List all 10 life areas (Level 1)"""
    areas = await db.hos_life_areas.find({}, {"_id": 0}).sort("order", 1).to_list(20)
    return areas

@router.get("/ask-types")
async def list_ask_types():
    """List all ask types: Problem, Need, Aspiration (Level 2)"""
    types = await db.hos_ask_types.find({}, {"_id": 0}).sort("order", 1).to_list(10)
    return types

@router.get("/sub-areas")
async def list_sub_areas(life_area_id: str = Query(...)):
    """List sub-areas for a life area (Level 3)"""
    items = await db.hos_sub_areas.find(
        {"life_area_id": life_area_id}, {"_id": 0}
    ).sort("order", 1).to_list(20)
    return items

@router.get("/categories")
async def list_categories(sub_area_id: str = Query(...)):
    """List decision categories for a sub-area (Level 4)"""
    items = await db.hos_decision_categories.find(
        {"sub_area_id": sub_area_id}, {"_id": 0}
    ).sort("order", 1).to_list(20)
    return items

# ========================
# TEMPLATE / SCENARIO ENDPOINTS (Level 5)
# ========================

@router.get("/templates")
async def list_templates(
    acting_as: Optional[str] = None,
    life_area_id: Optional[str] = None,
    ask_type_id: Optional[str] = None,
    sub_area_id: Optional[str] = None,
    category_id: Optional[str] = None,
    template_type: Optional[str] = None,
    limit: int = 50,
):
    """List templates/scenarios with optional filters"""
    query: Dict[str, Any] = {"status": "active"}
    if acting_as:
        query["acting_as_contexts"] = acting_as.upper()
    if life_area_id:
        query["life_area_id"] = life_area_id
    if ask_type_id:
        query["ask_type_id"] = ask_type_id
    if sub_area_id:
        query["sub_area_id"] = sub_area_id
    if category_id:
        query["category_id"] = category_id
    if template_type:
        query["template_type"] = template_type.upper()

    items = await db.hos_decision_templates.find(
        query, {"_id": 0}
    ).sort([("popularity", -1), ("order", 1)]).to_list(limit)
    return items

@router.get("/templates/suggest")
async def autosuggest_templates(
    acting_as: str = Query(...),
    life_area_id: str = Query(...),
    ask_type_id: str = Query(...),
    q: Optional[str] = None,
    sub_area_id: Optional[str] = None,
    category_id: Optional[str] = None,
    limit: int = 20,
):
    """
    Autosuggest matching scenarios/templates (Level 5).
    Uses required context filters + optional search text for ranking.
    """
    # Build base query from required filters
    query: Dict[str, Any] = {
        "status": "active",
        "acting_as_contexts": acting_as.upper(),
        "life_area_id": life_area_id,
        "ask_type_id": ask_type_id,
    }
    if sub_area_id:
        query["sub_area_id"] = sub_area_id
    if category_id:
        query["category_id"] = category_id

    # If search text, use regex for partial matching
    if q and q.strip():
        search_pattern = re.escape(q.strip())
        query["$or"] = [
            {"title": {"$regex": search_pattern, "$options": "i"}},
            {"description": {"$regex": search_pattern, "$options": "i"}},
            {"tags": {"$regex": search_pattern, "$options": "i"}},
        ]

    items = await db.hos_decision_templates.find(
        query, {"_id": 0}
    ).sort([("popularity", -1), ("order", 1)]).to_list(limit)

    # If no exact matches with search text, relax to just context filters
    if q and q.strip() and len(items) == 0:
        fallback_query: Dict[str, Any] = {
            "status": "active",
            "acting_as_contexts": acting_as.upper(),
            "life_area_id": life_area_id,
            "ask_type_id": ask_type_id,
        }
        items = await db.hos_decision_templates.find(
            fallback_query, {"_id": 0}
        ).sort([("popularity", -1), ("order", 1)]).to_list(limit)

    return items

@router.get("/templates/{template_id}")
async def get_template_detail(template_id: str):
    """Get full template detail including starter config and factor defaults"""
    template = await db.hos_decision_templates.find_one(
        {"id": template_id}, {"_id": 0}
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Also fetch template defaults if they exist
    defaults = await db.hos_template_defaults.find_one(
        {"template_id": template_id}, {"_id": 0}
    )
    if defaults:
        template["defaults"] = defaults

    return template

# ========================
# DECISION CREATION
# ========================

@router.post("/decisions")
async def create_decision_from_intake(
    payload: DecisionCreateFromTemplate,
    user: dict = Depends(get_current_user),
):
    """Create a new decision from the HOS intake flow"""
    # Validate acting_as_context
    if payload.acting_as_context.upper() not in ACTING_AS_CONTEXTS:
        raise HTTPException(status_code=400, detail=f"Invalid acting_as_context. Must be one of: {ACTING_AS_CONTEXTS}")
    if payload.source_type.upper() not in TEMPLATE_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid source_type. Must be one of: {TEMPLATE_TYPES}")

    # Load template starter config if a template is selected
    starter_config = None
    factors_to_load = []
    if payload.template_id:
        template = await db.hos_decision_templates.find_one({"id": payload.template_id})
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        defaults = await db.hos_template_defaults.find_one({"template_id": payload.template_id})
        if defaults:
            starter_config = {
                "default_factors": defaults.get("default_factors_json", []),
                "suggested_questions": defaults.get("suggested_questions_json", []),
                "starter_notes": defaults.get("starter_notes", ""),
                "cld_placeholder": defaults.get("future_cld_placeholder_json", {}),
            }
            factors_to_load = defaults.get("default_factors_json", [])

    # Resolve life area name for the PRR decision
    life_area_doc = await db.hos_life_areas.find_one({"id": payload.life_area_id})
    life_area_slug = life_area_doc.get("slug", "") if life_area_doc else ""

    # Resolve ask type for decision_type
    ask_type_doc = await db.hos_ask_types.find_one({"id": payload.ask_type_id})
    decision_type_val = ask_type_doc.get("slug", "") if ask_type_doc else ""

    now = datetime.now(timezone.utc)
    decision_id = str(uuid.uuid4())

    # Build PRR decision document directly (avoids circular import with server.py)
    doc_dict = {
        "id": decision_id,
        "user_id": user["user_id"],
        "title": payload.title,
        "context": payload.raw_user_input or payload.title,
        "folder": life_area_slug,
        "life_area": life_area_slug,
        "decision_type": decision_type_val,
        "decision_case": None,
        "factors": factors_to_load if factors_to_load else [],
        "options": [],
        "chosen_option_id": None,
        "notes": "",
        "reflection": "",
        "final_notes": "",
        "rating_gap_multiplier": 1.0,
        "mpps_option_id": None,
        "mpps_improvements": [],
        "mpps_projected_worth": None,
        "mpps_timeframe": None,
        "implementation_review_date": None,
        "status": "draft",
        "created_at": now,
        "updated_at": now,
        "hos_metadata": {
            "acting_as_context": payload.acting_as_context.upper(),
            "life_area_id": payload.life_area_id,
            "ask_type_id": payload.ask_type_id,
            "sub_area_id": payload.sub_area_id,
            "category_id": payload.category_id,
            "template_id": payload.template_id,
            "source_type": payload.source_type.upper(),
            "starter_config_json": starter_config,
        },
    }

    await db.decisions.insert_one(doc_dict)

    return {
        "id": doc_dict["id"],
        "title": doc_dict["title"],
        "source_type": payload.source_type.upper(),
        "factors_loaded": len(factors_to_load),
        "message": "Decision created from HOS intake",
    }

# ========================
# SEED DATA
# ========================

@router.post("/seed")
async def seed_master_data(force: bool = False):
    """Seed all HOS master data. Pass ?force=true to drop and re-seed."""
    from data.hos_seed_data import (
        LIFE_AREAS, ASK_TYPES, SUB_AREAS, CATEGORIES,
        TEMPLATES, TEMPLATE_DEFAULTS,
    )

    # Check if already seeded (skip if force)
    existing = await db.hos_life_areas.count_documents({})
    if existing > 0 and not force:
        counts = {
            "life_areas": await db.hos_life_areas.count_documents({}),
            "ask_types": await db.hos_ask_types.count_documents({}),
            "sub_areas": await db.hos_sub_areas.count_documents({}),
            "categories": await db.hos_decision_categories.count_documents({}),
            "templates": await db.hos_decision_templates.count_documents({}),
            "template_defaults": await db.hos_template_defaults.count_documents({}),
        }
        return {"message": "Master data already seeded", "counts": counts}

    # Drop existing collections if force
    if force:
        for coll_name in [
            "hos_life_areas", "hos_ask_types", "hos_sub_areas",
            "hos_decision_categories", "hos_decision_templates", "hos_template_defaults",
        ]:
            await db[coll_name].drop()

    # Insert all data
    await db.hos_life_areas.insert_many(LIFE_AREAS)
    await db.hos_ask_types.insert_many(ASK_TYPES)
    await db.hos_sub_areas.insert_many(SUB_AREAS)
    await db.hos_decision_categories.insert_many(CATEGORIES)
    await db.hos_decision_templates.insert_many(TEMPLATES)

    # Add IDs to template defaults
    import uuid as _uuid
    defaults_with_ids = []
    for d in TEMPLATE_DEFAULTS:
        doc = dict(d)
        doc["id"] = str(_uuid.uuid4())
        defaults_with_ids.append(doc)
    await db.hos_template_defaults.insert_many(defaults_with_ids)

    # Create indexes
    await db.hos_decision_templates.create_index([("title", "text"), ("description", "text"), ("tags", "text")])
    await db.hos_decision_templates.create_index("life_area_id")
    await db.hos_decision_templates.create_index("ask_type_id")
    await db.hos_decision_templates.create_index("acting_as_contexts")
    await db.hos_sub_areas.create_index("life_area_id")
    await db.hos_decision_categories.create_index("sub_area_id")

    return {
        "message": "HOS master data seeded successfully" + (" (force re-seeded)" if force else ""),
        "counts": {
            "life_areas": len(LIFE_AREAS),
            "ask_types": len(ASK_TYPES),
            "sub_areas": len(SUB_AREAS),
            "categories": len(CATEGORIES),
            "templates": len(TEMPLATES),
            "template_defaults": len(defaults_with_ids),
        }
    }
