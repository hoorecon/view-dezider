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

ACTING_AS_CONTEXTS = [
    "INDIVIDUAL",
    "BUSINESS_ORG",
    "ACADEMIC_ORG",
    "NONPROFIT_ORG",
    "ASSOCIATION",
    "GOVERNMENT",
]
# Legacy contexts kept for backward compatibility with old templates
LEGACY_ACTING_AS_CONTEXTS = ["INDIVIDUAL", "ORGANIZATION", "GOVERNMENT"]
ASK_TYPES = ["PROBLEM", "NEED", "ASPIRATION"]
TEMPLATE_TYPES = ["AUTHORIZED_STANDARD", "DYNAMIC_CLD_STARTER", "CUSTOM_BLANK"]
ORG_TYPES = ["BUSINESS_ORG", "ACADEMIC_ORG", "NONPROFIT_ORG", "ASSOCIATION", "GOVERNMENT"]
APPLIES_TO_MODULES = ["dezider", "swot"]
DECISION_TYPES_VALID = ["problem", "need", "aspiration"]

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
    # Timing fields — added on Initial-Info Step 4 so that downstream PRR steps
    # (and Action Center / CTT / Lifestyle handoffs) inherit a consistent
    # deadline + impact horizon from the very start.
    deadline_date: Optional[str] = None       # ISO date string YYYY-MM-DD
    impact_horizon_value: Optional[int] = None
    impact_horizon_unit: Optional[str] = None # days | weeks | months | years

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
    module: str = Query("dezider"),   # 'dezider' | 'swot'
    limit: int = 20,
):
    """
    Autosuggest matching scenarios/templates (Level 5).

    Filters by:
      - module      → templates whose `applies_to_modules` includes the requested module
      - acting_as   → 6-value OrgType.  Empty `org_types` array on a doc means
                      "applies to ALL OrgTypes". Legacy docs that still only have
                      `acting_as_contexts` are also matched via that field.
      - ask_type_id → existing single-value filter; the new `decision_types`
                      multi-array is also honored if present.
      - life_area_id required
      - sub_area_id, category_id optional
      - q free-text search across title/description/tags
    """
    # Decision type derived from ask_type_id slug (at_problem → 'problem', etc.)
    decision_type = ""
    if ask_type_id:
        decision_type = ask_type_id.replace("at_", "").lower()

    module_lc = (module or "dezider").strip().lower()
    if module_lc not in APPLIES_TO_MODULES:
        module_lc = "dezider"

    # Base required filters (life area + module)
    query: Dict[str, Any] = {
        "status": "active",
        "life_area_id": life_area_id,
        # applies_to_modules: array on doc. Empty/missing array = legacy "dezider-only".
        # We match if the array contains the requested module OR (for legacy docs)
        # if the field is missing AND the requested module is 'dezider'.
        "$and": [],
    }

    # Module filter
    if module_lc == "dezider":
        query["$and"].append({
            "$or": [
                {"applies_to_modules": "dezider"},
                {"applies_to_modules": {"$exists": False}},  # legacy docs
            ]
        })
    else:  # swot
        query["$and"].append({"applies_to_modules": "swot"})

    # Org-type filter (legacy + new). Empty org_types = wildcard.
    acting_as_upper = (acting_as or "").upper()
    org_filter_clauses = [{"org_types": {"$size": 0}}]  # wildcard rule
    if acting_as_upper:
        org_filter_clauses.append({"org_types": acting_as_upper})
        # Also tolerate legacy `acting_as_contexts` array
        if acting_as_upper in ("BUSINESS_ORG", "ACADEMIC_ORG", "NONPROFIT_ORG", "ASSOCIATION"):
            org_filter_clauses.append({"acting_as_contexts": "ORGANIZATION"})
        else:
            org_filter_clauses.append({"acting_as_contexts": acting_as_upper})
    query["$and"].append({"$or": org_filter_clauses})

    # Decision-type filter (legacy ask_type_id + new decision_types). Empty decision_types = wildcard.
    dt_clauses = [{"decision_types": {"$size": 0}}]
    if decision_type:
        dt_clauses.append({"decision_types": decision_type})
    if ask_type_id:
        dt_clauses.append({"ask_type_id": ask_type_id})
    query["$and"].append({"$or": dt_clauses})

    if sub_area_id:
        query["sub_area_id"] = sub_area_id
    if category_id:
        query["category_id"] = category_id

    # If search text, use regex for partial matching
    if q and q.strip():
        search_pattern = re.escape(q.strip())
        query["$and"].append({"$or": [
            {"title": {"$regex": search_pattern, "$options": "i"}},
            {"description": {"$regex": search_pattern, "$options": "i"}},
            {"tags": {"$regex": search_pattern, "$options": "i"}},
        ]})

    items = await db.hos_decision_templates.find(
        query, {"_id": 0}
    ).sort([("popularity", -1), ("order", 1)]).to_list(limit)

    # Relax fallback — drop sub_area/category/q if no exact matches
    if (sub_area_id or category_id or (q and q.strip())) and len(items) == 0:
        relaxed = {
            "status": "active",
            "life_area_id": life_area_id,
            "$and": query["$and"][:3],   # keep module + org + decision-type filters
        }
        items = await db.hos_decision_templates.find(
            relaxed, {"_id": 0}
        ).sort([("popularity", -1), ("order", 1)]).to_list(limit)

    return items


@router.get("/scenarios")
async def list_scenarios(
    life_area_id: Optional[str] = None,
    sub_area_id: Optional[str] = None,
    module: str = Query("dezider"),
    limit: int = 50,
):
    """
    Return distinct scenarios for the given life-area/sub-area, derived from
    `hos_decision_templates.scenario_mapping`. Each scenario carries enough
    info for the Step-4 dropdown:
        {id, title, sub_area_id, life_area_id, template_id (representative)}
    Used by the new structured Step-4 UI.
    """
    module_lc = (module or "dezider").strip().lower()
    if module_lc not in APPLIES_TO_MODULES:
        module_lc = "dezider"

    query: Dict[str, Any] = {"status": "active"}
    if life_area_id:
        query["life_area_id"] = life_area_id
    if sub_area_id:
        query["sub_area_id"] = sub_area_id

    if module_lc == "dezider":
        query["$or"] = [
            {"applies_to_modules": "dezider"},
            {"applies_to_modules": {"$exists": False}},
        ]
    else:
        query["applies_to_modules"] = "swot"

    cursor = db.hos_decision_templates.find(
        query,
        {"_id": 0, "id": 1, "title": 1, "scenario_mapping": 1,
         "sub_area_id": 1, "life_area_id": 1, "popularity": 1},
    ).sort([("popularity", -1), ("order", 1)]).limit(limit)

    # Collapse multiple templates that share the same scenario title under one entry.
    seen: Dict[str, Dict[str, Any]] = {}
    async for doc in cursor:
        sm = doc.get("scenario_mapping") or {}
        title = (
            (sm.get("suggested_new_scenario") or {}).get("title")
            or sm.get("predefined_scenario_title")
            or doc.get("title")
            or ""
        )
        if not title:
            continue
        key = title.strip().lower()
        if key in seen:
            seen[key]["template_count"] = seen[key].get("template_count", 1) + 1
            continue
        seen[key] = {
            # Deterministic synthetic id so the frontend dropdown can use it
            # as a select value without hitting another endpoint.
            "id": sm.get("predefined_scenario_id")
                  or f"scn_{doc.get('life_area_id','')}_{doc.get('sub_area_id','')}_{key.replace(' ','_')[:60]}",
            "title": title,
            "sub_area_id": doc.get("sub_area_id"),
            "life_area_id": doc.get("life_area_id"),
            "representative_template_id": doc.get("id"),
            "template_count": 1,
        }

    return list(seen.values())

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


def _is_admin_user(user: dict) -> bool:
    role = (user or {}).get("role", "")
    org_role = (user or {}).get("org_role", "")
    return role in ("super_admin", "co_admin", "admin") or org_role in (
        "org_super_admin", "org_co_admin"
    )


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    user: dict = Depends(get_current_user),
):
    """Delete a decision template.

    Authorisation:
      • Admins (super_admin / co_admin) can delete any template.
      • Regular users can only delete templates THEY authored
        (created_by_user_id == own user_id) AND which are still
        in CUSTOM_BLANK / unapproved status (you cannot remove a
        template that has been approved by an admin).

    Deletion is HARD (removes the row entirely) plus a side-purge
    of any orphan `hos_template_defaults` row keyed by the same
    template_id, so the SWOT-saved templates can be cleaned up
    without leaving stale data.
    """
    tpl = await db.hos_decision_templates.find_one({"id": template_id}, {"_id": 0})
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")

    is_admin = _is_admin_user(user)
    is_author = (tpl.get("created_by_user_id") == user.get("user_id"))
    approved = tpl.get("approval_status") == "approved"
    authorized = tpl.get("source_type") == "AUTHORIZED_STANDARD"

    if not is_admin:
        if not is_author:
            raise HTTPException(
                status_code=403,
                detail="Only the template author or an admin may delete this template.",
            )
        if approved or authorized:
            raise HTTPException(
                status_code=403,
                detail="Approved/authorized templates can only be removed by an admin.",
            )

    res = await db.hos_decision_templates.delete_one({"id": template_id})
    await db.hos_template_defaults.delete_many({"template_id": template_id})

    # Audit trail (best-effort)
    try:
        await db.hos_template_deletion_log.insert_one({
            "id": str(uuid.uuid4()),
            "template_id": template_id,
            "title": tpl.get("title", ""),
            "deleted_by": user.get("user_id"),
            "deleted_by_name": user.get("name", ""),
            "deleted_by_role": "admin" if is_admin else "author",
            "source_type": tpl.get("source_type"),
            "approval_status": tpl.get("approval_status"),
            "at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass

    return {
        "deleted": bool(res.deleted_count),
        "template_id": template_id,
        "message": "Template deleted.",
    }


@router.post("/admin/templates/bulk-delete")
async def admin_bulk_delete_templates(
    body: Dict[str, Any],
    user: dict = Depends(get_current_user),
):
    """Admin-only convenience: hard-delete multiple templates by id list.

    Useful for cleaning up TEST_* leftovers from prior testing-agent runs.
    Body: { "ids": ["t1", "t2", ...] } or { "title_prefix": "TEST_" }.
    """
    if not _is_admin_user(user):
        raise HTTPException(status_code=403, detail="Admin role required")

    ids = list(body.get("ids") or [])
    prefix = body.get("title_prefix")
    query: Dict[str, Any] = {}
    if ids:
        query["id"] = {"$in": ids}
    elif prefix:
        query["title"] = {"$regex": f"^{re.escape(str(prefix))}"}
    else:
        raise HTTPException(status_code=400, detail="Provide `ids` or `title_prefix`")

    # Capture for audit
    matching = await db.hos_decision_templates.find(
        query, {"_id": 0, "id": 1, "title": 1}
    ).to_list(500)
    if not matching:
        return {"deleted_count": 0, "matched": []}

    matched_ids = [m["id"] for m in matching]
    res = await db.hos_decision_templates.delete_many({"id": {"$in": matched_ids}})
    await db.hos_template_defaults.delete_many({"template_id": {"$in": matched_ids}})

    try:
        await db.hos_template_deletion_log.insert_many([
            {
                "id": str(uuid.uuid4()),
                "template_id": m["id"],
                "title": m.get("title", ""),
                "deleted_by": user.get("user_id"),
                "deleted_by_name": user.get("name", ""),
                "deleted_by_role": "admin_bulk",
                "at": datetime.now(timezone.utc).isoformat(),
            }
            for m in matching
        ])
    except Exception:
        pass

    return {
        "deleted_count": res.deleted_count,
        "matched": [{"id": m["id"], "title": m.get("title")} for m in matching],
    }

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
        # Timing — captured on Initial-Info Step 4 (Decision Title screen).
        "deadline_date": payload.deadline_date,
        "impact_horizon_value": payload.impact_horizon_value,
        "impact_horizon_unit": payload.impact_horizon_unit,
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
