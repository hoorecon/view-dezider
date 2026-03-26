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
async def seed_master_data():
    """Seed all HOS master data: life areas, ask types, sub-areas, categories, and templates"""

    # Check if already seeded
    existing = await db.hos_life_areas.count_documents({})
    if existing > 0:
        # Return counts of existing data
        life_areas_count = await db.hos_life_areas.count_documents({})
        ask_types_count = await db.hos_ask_types.count_documents({})
        sub_areas_count = await db.hos_sub_areas.count_documents({})
        categories_count = await db.hos_decision_categories.count_documents({})
        templates_count = await db.hos_decision_templates.count_documents({})
        template_defaults_count = await db.hos_template_defaults.count_documents({})
        
        return {
            "message": "Master data already seeded",
            "counts": {
                "life_areas": life_areas_count,
                "ask_types": ask_types_count,
                "sub_areas": sub_areas_count,
                "categories": categories_count,
                "templates": templates_count,
                "template_defaults": template_defaults_count,
            }
        }

    # ---- LEVEL 1: Life Areas ----
    life_areas = [
        {"id": "la_health", "name": "Physical, Mental & Emotional Health", "slug": "holistic_health", "icon": "fitness", "color": "#10B981", "order": 1},
        {"id": "la_knowledge", "name": "Knowledge & Skills", "slug": "knowledge_skills", "icon": "book", "color": "#3B82F6", "order": 2},
        {"id": "la_relationships", "name": "Relationships", "slug": "relationships", "icon": "heart", "color": "#EC4899", "order": 3},
        {"id": "la_finance", "name": "Finance", "slug": "finance", "icon": "cash", "color": "#F59E0B", "order": 4},
        {"id": "la_career", "name": "Career", "slug": "career", "icon": "briefcase", "color": "#6366F1", "order": 5},
        {"id": "la_assets", "name": "Assets (Movable & Immovable)", "slug": "assets", "icon": "home", "color": "#8B5CF6", "order": 6},
        {"id": "la_hobbies", "name": "Hobbies & Entertainment", "slug": "hobbies_entertainment", "icon": "game-controller", "color": "#14B8A6", "order": 7},
        {"id": "la_social_image", "name": "Social Image & Influence", "slug": "social_image", "icon": "star", "color": "#F97316", "order": 8},
        {"id": "la_contribution", "name": "Social Contribution", "slug": "social_contributions", "icon": "people", "color": "#06B6D4", "order": 9},
        {"id": "la_spirituality", "name": "Spirituality", "slug": "spirituality_religion", "icon": "leaf", "color": "#A855F7", "order": 10},
    ]
    await db.hos_life_areas.insert_many(life_areas)

    # ---- LEVEL 2: Ask Types ----
    ask_types = [
        {"id": "at_problem", "name": "Problem", "slug": "problem", "icon": "warning", "color": "#EF4444", "description": "Solving a challenge or crisis", "priority_label": "P0", "order": 1},
        {"id": "at_need", "name": "Need", "slug": "need", "icon": "flag", "color": "#F59E0B", "description": "Fulfilling a requirement", "priority_label": "P1", "order": 2},
        {"id": "at_aspiration", "name": "Aspiration", "slug": "aspiration", "icon": "rocket", "color": "#10B981", "description": "Pursuing a goal or dream", "priority_label": "P2", "order": 3},
    ]
    await db.hos_ask_types.insert_many(ask_types)

    # ---- LEVEL 3: Sub-Areas ----
    sub_areas = [
        # Finance
        {"id": "sa_fin_income", "life_area_id": "la_finance", "name": "Income", "slug": "income", "order": 1},
        {"id": "sa_fin_expenses", "life_area_id": "la_finance", "name": "Expenses", "slug": "expenses", "order": 2},
        {"id": "sa_fin_savings", "life_area_id": "la_finance", "name": "Savings", "slug": "savings", "order": 3},
        {"id": "sa_fin_investments", "life_area_id": "la_finance", "name": "Investments", "slug": "investments", "order": 4},
        {"id": "sa_fin_debt", "life_area_id": "la_finance", "name": "Debt", "slug": "debt", "order": 5},
        {"id": "sa_fin_risk", "life_area_id": "la_finance", "name": "Risk Management", "slug": "risk_management", "order": 6},
        # Career
        {"id": "sa_car_job", "life_area_id": "la_career", "name": "Job & Employment", "slug": "job_employment", "order": 1},
        {"id": "sa_car_business", "life_area_id": "la_career", "name": "Business & Startup", "slug": "business_startup", "order": 2},
        {"id": "sa_car_growth", "life_area_id": "la_career", "name": "Professional Growth", "slug": "professional_growth", "order": 3},
        {"id": "sa_car_leadership", "life_area_id": "la_career", "name": "Leadership & Management", "slug": "leadership_management", "order": 4},
        {"id": "sa_car_transition", "life_area_id": "la_career", "name": "Career Transition", "slug": "career_transition", "order": 5},
        # Relationships
        {"id": "sa_rel_marriage", "life_area_id": "la_relationships", "name": "Marriage & Partnership", "slug": "marriage_partnership", "order": 1},
        {"id": "sa_rel_family", "life_area_id": "la_relationships", "name": "Family", "slug": "family", "order": 2},
        {"id": "sa_rel_friends", "life_area_id": "la_relationships", "name": "Friendships & Social", "slug": "friendships_social", "order": 3},
        {"id": "sa_rel_professional", "life_area_id": "la_relationships", "name": "Professional Relationships", "slug": "professional_relationships", "order": 4},
        {"id": "sa_rel_conflict", "life_area_id": "la_relationships", "name": "Conflict Resolution", "slug": "conflict_resolution", "order": 5},
        # Health
        {"id": "sa_hlt_physical", "life_area_id": "la_health", "name": "Physical Health", "slug": "physical_health", "order": 1},
        {"id": "sa_hlt_mental", "life_area_id": "la_health", "name": "Mental Health", "slug": "mental_health", "order": 2},
        {"id": "sa_hlt_emotional", "life_area_id": "la_health", "name": "Emotional Wellbeing", "slug": "emotional_wellbeing", "order": 3},
        {"id": "sa_hlt_fitness", "life_area_id": "la_health", "name": "Fitness & Nutrition", "slug": "fitness_nutrition", "order": 4},
        # Knowledge
        {"id": "sa_kno_education", "life_area_id": "la_knowledge", "name": "Formal Education", "slug": "formal_education", "order": 1},
        {"id": "sa_kno_skills", "life_area_id": "la_knowledge", "name": "Skill Development", "slug": "skill_development", "order": 2},
        {"id": "sa_kno_certifications", "life_area_id": "la_knowledge", "name": "Certifications & Training", "slug": "certifications_training", "order": 3},
        # Assets
        {"id": "sa_ast_real_estate", "life_area_id": "la_assets", "name": "Real Estate", "slug": "real_estate", "order": 1},
        {"id": "sa_ast_vehicles", "life_area_id": "la_assets", "name": "Vehicles & Equipment", "slug": "vehicles_equipment", "order": 2},
        {"id": "sa_ast_digital", "life_area_id": "la_assets", "name": "Digital Assets", "slug": "digital_assets", "order": 3},
        # Hobbies
        {"id": "sa_hob_sports", "life_area_id": "la_hobbies", "name": "Sports & Activities", "slug": "sports_activities", "order": 1},
        {"id": "sa_hob_creative", "life_area_id": "la_hobbies", "name": "Creative Arts", "slug": "creative_arts", "order": 2},
        {"id": "sa_hob_travel", "life_area_id": "la_hobbies", "name": "Travel & Experiences", "slug": "travel_experiences", "order": 3},
        # Social Image
        {"id": "sa_soc_brand", "life_area_id": "la_social_image", "name": "Personal Brand", "slug": "personal_brand", "order": 1},
        {"id": "sa_soc_network", "life_area_id": "la_social_image", "name": "Networking", "slug": "networking", "order": 2},
        {"id": "sa_soc_reputation", "life_area_id": "la_social_image", "name": "Reputation", "slug": "reputation", "order": 3},
        # Contribution
        {"id": "sa_con_volunteering", "life_area_id": "la_contribution", "name": "Volunteering", "slug": "volunteering", "order": 1},
        {"id": "sa_con_philanthropy", "life_area_id": "la_contribution", "name": "Philanthropy", "slug": "philanthropy", "order": 2},
        {"id": "sa_con_community", "life_area_id": "la_contribution", "name": "Community Building", "slug": "community_building", "order": 3},
        # Spirituality
        {"id": "sa_spi_practice", "life_area_id": "la_spirituality", "name": "Spiritual Practice", "slug": "spiritual_practice", "order": 1},
        {"id": "sa_spi_purpose", "life_area_id": "la_spirituality", "name": "Purpose & Meaning", "slug": "purpose_meaning", "order": 2},
        {"id": "sa_spi_mindfulness", "life_area_id": "la_spirituality", "name": "Mindfulness & Meditation", "slug": "mindfulness_meditation", "order": 3},
    ]
    await db.hos_sub_areas.insert_many(sub_areas)

    # ---- LEVEL 4: Decision Categories ----
    categories = [
        # Finance > Income
        {"id": "cat_fin_salary", "sub_area_id": "sa_fin_income", "life_area_id": "la_finance", "name": "Salary Growth", "order": 1},
        {"id": "cat_fin_revenue", "sub_area_id": "sa_fin_income", "life_area_id": "la_finance", "name": "Business Revenue", "order": 2},
        {"id": "cat_fin_side", "sub_area_id": "sa_fin_income", "life_area_id": "la_finance", "name": "Side Income", "order": 3},
        {"id": "cat_fin_pricing", "sub_area_id": "sa_fin_income", "life_area_id": "la_finance", "name": "Pricing Strategy", "order": 4},
        {"id": "cat_fin_cashflow", "sub_area_id": "sa_fin_income", "life_area_id": "la_finance", "name": "Cash Flow Stability", "order": 5},
        # Finance > Investments
        {"id": "cat_fin_stocks", "sub_area_id": "sa_fin_investments", "life_area_id": "la_finance", "name": "Stock Market", "order": 1},
        {"id": "cat_fin_realestate_inv", "sub_area_id": "sa_fin_investments", "life_area_id": "la_finance", "name": "Real Estate Investment", "order": 2},
        {"id": "cat_fin_mutual", "sub_area_id": "sa_fin_investments", "life_area_id": "la_finance", "name": "Mutual Funds & SIP", "order": 3},
        {"id": "cat_fin_crypto", "sub_area_id": "sa_fin_investments", "life_area_id": "la_finance", "name": "Crypto & Alternative", "order": 4},
        # Finance > Debt
        {"id": "cat_fin_loan", "sub_area_id": "sa_fin_debt", "life_area_id": "la_finance", "name": "Loans & EMI", "order": 1},
        {"id": "cat_fin_credit", "sub_area_id": "sa_fin_debt", "life_area_id": "la_finance", "name": "Credit Management", "order": 2},
        # Career > Job
        {"id": "cat_car_switch", "sub_area_id": "sa_car_job", "life_area_id": "la_career", "name": "Job Switch", "order": 1},
        {"id": "cat_car_negotiate", "sub_area_id": "sa_car_job", "life_area_id": "la_career", "name": "Salary Negotiation", "order": 2},
        {"id": "cat_car_resign", "sub_area_id": "sa_car_job", "life_area_id": "la_career", "name": "Resignation Decision", "order": 3},
        # Career > Business
        {"id": "cat_car_startup", "sub_area_id": "sa_car_business", "life_area_id": "la_career", "name": "Starting a Business", "order": 1},
        {"id": "cat_car_funding", "sub_area_id": "sa_car_business", "life_area_id": "la_career", "name": "Funding & Investment", "order": 2},
        {"id": "cat_car_hiring", "sub_area_id": "sa_car_business", "life_area_id": "la_career", "name": "Hiring & Team Building", "order": 3},
        {"id": "cat_car_expansion", "sub_area_id": "sa_car_business", "life_area_id": "la_career", "name": "Business Expansion", "order": 4},
        # Career > Leadership
        {"id": "cat_car_lead_style", "sub_area_id": "sa_car_leadership", "life_area_id": "la_career", "name": "Leadership Style", "order": 1},
        {"id": "cat_car_burnout", "sub_area_id": "sa_car_leadership", "life_area_id": "la_career", "name": "Burnout Management", "order": 2},
        # Relationships > Marriage
        {"id": "cat_rel_choose", "sub_area_id": "sa_rel_marriage", "life_area_id": "la_relationships", "name": "Choosing a Partner", "order": 1},
        {"id": "cat_rel_marital", "sub_area_id": "sa_rel_marriage", "life_area_id": "la_relationships", "name": "Marital Decisions", "order": 2},
        {"id": "cat_rel_separation", "sub_area_id": "sa_rel_marriage", "life_area_id": "la_relationships", "name": "Separation & Divorce", "order": 3},
        # Relationships > Family
        {"id": "cat_rel_parenting", "sub_area_id": "sa_rel_family", "life_area_id": "la_relationships", "name": "Parenting", "order": 1},
        {"id": "cat_rel_eldercare", "sub_area_id": "sa_rel_family", "life_area_id": "la_relationships", "name": "Elder Care", "order": 2},
    ]
    await db.hos_decision_categories.insert_many(categories)

    # ---- LEVEL 5: Decision Templates / Scenarios ----
    def make_factor(name, category, rating, order, unit=None, expected_value=None):
        return {
            "id": str(uuid.uuid4()),
            "name": name,
            "category": category,
            "rating": rating,
            "order": order,
            "unit": unit,
            "expected_value": expected_value,
            "data_type": "numeric" if isinstance(expected_value, (int, float)) else "text" if expected_value else None,
            "operator": ">=" if isinstance(expected_value, (int, float)) else None,
            "gap_multiplier": 1.0,
            "parent_id": None,
            "weight": None,
        }

    templates = [
        # ===== FINANCE TEMPLATES =====
        {
            "id": "tpl_fin_quit_job", "life_area_id": "la_finance", "ask_type_id": "at_problem",
            "sub_area_id": "sa_fin_income", "category_id": "cat_fin_cashflow",
            "acting_as_contexts": ["INDIVIDUAL"],
            "template_type": "AUTHORIZED_STANDARD",
            "title": "Should I quit my job?",
            "description": "Evaluate whether to leave your current job considering financial stability, career growth, and personal satisfaction.",
            "tags": ["quit", "resign", "job", "leave", "career change"],
            "popularity": 95, "order": 1, "status": "active",
        },
        {
            "id": "tpl_fin_loan", "life_area_id": "la_finance", "ask_type_id": "at_need",
            "sub_area_id": "sa_fin_debt", "category_id": "cat_fin_loan",
            "acting_as_contexts": ["INDIVIDUAL", "ORGANIZATION"],
            "template_type": "AUTHORIZED_STANDARD",
            "title": "Should I take a business loan?",
            "description": "Assess the viability and risks of taking a business loan for expansion or working capital.",
            "tags": ["loan", "debt", "business", "funding", "capital"],
            "popularity": 88, "order": 2, "status": "active",
        },
        {
            "id": "tpl_fin_invest", "life_area_id": "la_finance", "ask_type_id": "at_aspiration",
            "sub_area_id": "sa_fin_investments", "category_id": "cat_fin_stocks",
            "acting_as_contexts": ["INDIVIDUAL"],
            "template_type": "AUTHORIZED_STANDARD",
            "title": "Where should I invest my savings?",
            "description": "Compare investment options: stocks, mutual funds, real estate, or fixed deposits.",
            "tags": ["invest", "savings", "stocks", "mutual funds", "returns"],
            "popularity": 85, "order": 3, "status": "active",
        },
        {
            "id": "tpl_fin_cashflow_starter", "life_area_id": "la_finance", "ask_type_id": "at_problem",
            "sub_area_id": "sa_fin_income", "category_id": "cat_fin_cashflow",
            "acting_as_contexts": ["INDIVIDUAL", "ORGANIZATION"],
            "template_type": "DYNAMIC_CLD_STARTER",
            "title": "Cash flow instability starter map",
            "description": "A starter framework for analyzing cash flow instability loops — income vs expenses dynamics.",
            "tags": ["cash flow", "instability", "loop", "burn rate", "runway"],
            "popularity": 72, "order": 4, "status": "active",
        },
        {
            "id": "tpl_fin_raise_funding", "life_area_id": "la_finance", "ask_type_id": "at_need",
            "sub_area_id": "sa_fin_investments", "category_id": "cat_fin_realestate_inv",
            "acting_as_contexts": ["ORGANIZATION"],
            "template_type": "AUTHORIZED_STANDARD",
            "title": "Should I raise funding or bootstrap?",
            "description": "Compare the trade-offs of raising external capital vs bootstrapping your company.",
            "tags": ["funding", "bootstrap", "venture", "startup", "capital"],
            "popularity": 90, "order": 5, "status": "active",
        },

        # ===== CAREER TEMPLATES =====
        {
            "id": "tpl_car_expand", "life_area_id": "la_career", "ask_type_id": "at_aspiration",
            "sub_area_id": "sa_car_business", "category_id": "cat_car_expansion",
            "acting_as_contexts": ["ORGANIZATION"],
            "template_type": "AUTHORIZED_STANDARD",
            "title": "Should I expand my startup?",
            "description": "Evaluate market readiness, team capacity, and financial runway before expanding.",
            "tags": ["expand", "startup", "growth", "scale", "market"],
            "popularity": 92, "order": 1, "status": "active",
        },
        {
            "id": "tpl_car_cofounder", "life_area_id": "la_career", "ask_type_id": "at_need",
            "sub_area_id": "sa_car_business", "category_id": "cat_car_hiring",
            "acting_as_contexts": ["INDIVIDUAL", "ORGANIZATION"],
            "template_type": "AUTHORIZED_STANDARD",
            "title": "Should I hire a cofounder?",
            "description": "Assess whether bringing on a cofounder will strengthen or complicate your venture.",
            "tags": ["cofounder", "partner", "hire", "startup", "team"],
            "popularity": 87, "order": 2, "status": "active",
        },
        {
            "id": "tpl_car_leadership_improve", "life_area_id": "la_career", "ask_type_id": "at_aspiration",
            "sub_area_id": "sa_car_leadership", "category_id": "cat_car_lead_style",
            "acting_as_contexts": ["INDIVIDUAL", "ORGANIZATION"],
            "template_type": "AUTHORIZED_STANDARD",
            "title": "How to improve my leadership skills?",
            "description": "Evaluate areas for leadership development: communication, delegation, strategic thinking.",
            "tags": ["leadership", "improve", "skills", "management", "growth"],
            "popularity": 80, "order": 3, "status": "active",
        },
        {
            "id": "tpl_car_burnout_starter", "life_area_id": "la_career", "ask_type_id": "at_problem",
            "sub_area_id": "sa_car_leadership", "category_id": "cat_car_burnout",
            "acting_as_contexts": ["INDIVIDUAL"],
            "template_type": "DYNAMIC_CLD_STARTER",
            "title": "Leadership burnout starter model",
            "description": "A starter CLD framework for understanding the burnout cycle — workload, recovery, performance loops.",
            "tags": ["burnout", "stress", "leadership", "workload", "loop"],
            "popularity": 70, "order": 4, "status": "active",
        },
        {
            "id": "tpl_car_runway_starter", "life_area_id": "la_career", "ask_type_id": "at_problem",
            "sub_area_id": "sa_car_business", "category_id": "cat_car_funding",
            "acting_as_contexts": ["ORGANIZATION"],
            "template_type": "DYNAMIC_CLD_STARTER",
            "title": "Founder runway stress loop",
            "description": "Starter model for the founder stress-runway cycle — how burn rate affects decisions and team morale.",
            "tags": ["runway", "founder", "stress", "burn rate", "startup"],
            "popularity": 75, "order": 5, "status": "active",
        },
        {
            "id": "tpl_car_switch", "life_area_id": "la_career", "ask_type_id": "at_need",
            "sub_area_id": "sa_car_job", "category_id": "cat_car_switch",
            "acting_as_contexts": ["INDIVIDUAL"],
            "template_type": "AUTHORIZED_STANDARD",
            "title": "Should I switch to a different industry?",
            "description": "Evaluate the pros and cons of making a career switch to a new industry or domain.",
            "tags": ["switch", "industry", "career change", "transition"],
            "popularity": 82, "order": 6, "status": "active",
        },

        # ===== RELATIONSHIP TEMPLATES =====
        {
            "id": "tpl_rel_marry", "life_area_id": "la_relationships", "ask_type_id": "at_need",
            "sub_area_id": "sa_rel_marriage", "category_id": "cat_rel_choose",
            "acting_as_contexts": ["INDIVIDUAL"],
            "template_type": "AUTHORIZED_STANDARD",
            "title": "Should I marry this person?",
            "description": "A structured evaluation of compatibility, values, lifestyle, and long-term partnership potential.",
            "tags": ["marry", "marriage", "partner", "compatibility", "relationship"],
            "popularity": 93, "order": 1, "status": "active",
        },
        {
            "id": "tpl_rel_conflict_starter", "life_area_id": "la_relationships", "ask_type_id": "at_problem",
            "sub_area_id": "sa_rel_conflict", "category_id": None,
            "acting_as_contexts": ["INDIVIDUAL"],
            "template_type": "DYNAMIC_CLD_STARTER",
            "title": "Marriage conflict starter structure",
            "description": "A starter model for mapping recurring conflict patterns in a relationship — triggers, reactions, resolution loops.",
            "tags": ["conflict", "marriage", "argument", "resolution", "loop"],
            "popularity": 68, "order": 2, "status": "active",
        },
        {
            "id": "tpl_rel_relocate", "life_area_id": "la_relationships", "ask_type_id": "at_problem",
            "sub_area_id": "sa_rel_family", "category_id": "cat_rel_parenting",
            "acting_as_contexts": ["INDIVIDUAL"],
            "template_type": "AUTHORIZED_STANDARD",
            "title": "Should I relocate for family?",
            "description": "Weigh career opportunities against family needs when considering relocation.",
            "tags": ["relocate", "family", "move", "city", "opportunity"],
            "popularity": 78, "order": 3, "status": "active",
        },

        # ===== GOVERNMENT CONTEXT TEMPLATES =====
        {
            "id": "tpl_gov_policy", "life_area_id": "la_contribution", "ask_type_id": "at_need",
            "sub_area_id": "sa_con_community", "category_id": None,
            "acting_as_contexts": ["GOVERNMENT"],
            "template_type": "AUTHORIZED_STANDARD",
            "title": "Should we implement this public policy?",
            "description": "Evaluate the impact, cost, and public sentiment of a proposed policy change.",
            "tags": ["policy", "government", "public", "impact", "regulation"],
            "popularity": 65, "order": 1, "status": "active",
        },
        {
            "id": "tpl_gov_budget", "life_area_id": "la_finance", "ask_type_id": "at_problem",
            "sub_area_id": "sa_fin_expenses", "category_id": None,
            "acting_as_contexts": ["GOVERNMENT"],
            "template_type": "AUTHORIZED_STANDARD",
            "title": "Budget allocation for public infrastructure",
            "description": "Prioritize budget allocation across competing public infrastructure needs.",
            "tags": ["budget", "infrastructure", "allocation", "public spending"],
            "popularity": 60, "order": 2, "status": "active",
        },
    ]
    await db.hos_decision_templates.insert_many(templates)

    # ---- LEVEL 5+: Template Defaults (factors, questions, notes, CLD placeholders) ----
    template_defaults = [
        {
            "id": str(uuid.uuid4()), "template_id": "tpl_fin_quit_job",
            "default_factors_json": [
                make_factor("Current Salary & Benefits", "primary", 85, 1, "USD", 80000),
                make_factor("Job Satisfaction", "primary", 90, 2),
                make_factor("Market Demand for Skills", "primary", 80, 3),
                make_factor("Financial Runway (months)", "primary", 75, 4, "months", 6),
                make_factor("Career Growth Potential", "secondary", 70, 5),
                make_factor("Work-Life Balance", "secondary", 65, 6),
                make_factor("Health Impact", "secondary", 60, 7),
                make_factor("Family Support", "secondary", 55, 8),
            ],
            "suggested_questions_json": [
                "How many months of expenses can you cover without income?",
                "What is the job market like for your skills right now?",
                "Have you explored internal transfer or role change first?",
                "What are your non-negotiable requirements in a new role?",
            ],
            "starter_notes": "Consider both financial and emotional readiness. Map your current situation against at least 2-3 alternatives.",
            "future_cld_placeholder_json": {
                "starter_variables": ["salary", "job_satisfaction", "skill_market_value", "financial_runway", "stress_level"],
                "potential_loops": ["income-stress-performance", "satisfaction-productivity-growth"],
            },
        },
        {
            "id": str(uuid.uuid4()), "template_id": "tpl_fin_loan",
            "default_factors_json": [
                make_factor("Interest Rate", "primary", 90, 1, "%", 12),
                make_factor("Revenue to EMI Ratio", "primary", 85, 2, "ratio", 3),
                make_factor("Business Growth Rate", "primary", 80, 3, "%", 20),
                make_factor("Collateral Available", "primary", 75, 4),
                make_factor("Market Conditions", "secondary", 65, 5),
                make_factor("Alternative Funding Options", "secondary", 60, 6),
            ],
            "suggested_questions_json": [
                "Can your current revenue comfortably cover the EMI?",
                "What is the loan's purpose — growth or survival?",
                "Have you compared at least 3 different lenders?",
            ],
            "starter_notes": "Focus on debt serviceability, not just approval eligibility.",
            "future_cld_placeholder_json": {
                "starter_variables": ["interest_rate", "revenue", "emi", "growth_rate"],
                "potential_loops": ["debt-growth-revenue"],
            },
        },
        {
            "id": str(uuid.uuid4()), "template_id": "tpl_car_expand",
            "default_factors_json": [
                make_factor("Market Readiness", "primary", 90, 1),
                make_factor("Financial Runway", "primary", 85, 2, "months", 12),
                make_factor("Team Capacity", "primary", 80, 3),
                make_factor("Competitive Landscape", "primary", 75, 4),
                make_factor("Operational Scalability", "secondary", 70, 5),
                make_factor("Customer Demand", "secondary", 65, 6),
                make_factor("Regulatory Compliance", "secondary", 55, 7),
            ],
            "suggested_questions_json": [
                "Is your product-market fit validated?",
                "Do you have enough runway for 12+ months post-expansion?",
                "Can your team handle 2x the current workload?",
            ],
            "starter_notes": "Expansion is irreversible. Evaluate both best-case and worst-case scenarios.",
            "future_cld_placeholder_json": {
                "starter_variables": ["market_size", "team_size", "burn_rate", "revenue", "competition"],
                "potential_loops": ["growth-hiring-burn_rate", "market_demand-revenue-capacity"],
            },
        },
        {
            "id": str(uuid.uuid4()), "template_id": "tpl_car_cofounder",
            "default_factors_json": [
                make_factor("Complementary Skills", "primary", 90, 1),
                make_factor("Shared Vision & Values", "primary", 88, 2),
                make_factor("Financial Contribution", "primary", 75, 3),
                make_factor("Work Ethic Compatibility", "primary", 80, 4),
                make_factor("Equity Split Fairness", "secondary", 70, 5),
                make_factor("Conflict Resolution Style", "secondary", 65, 6),
            ],
            "suggested_questions_json": [
                "What skills gap does this cofounder fill?",
                "Have you worked together under stress before?",
                "Is the equity and role split clearly defined?",
            ],
            "starter_notes": "Cofounder conflicts are the #1 startup killer. Test compatibility before commitment.",
            "future_cld_placeholder_json": {
                "starter_variables": ["skill_overlap", "trust_level", "equity_satisfaction", "decision_speed"],
                "potential_loops": ["trust-communication-productivity"],
            },
        },
        {
            "id": str(uuid.uuid4()), "template_id": "tpl_rel_marry",
            "default_factors_json": [
                make_factor("Value Alignment", "primary", 95, 1),
                make_factor("Communication Quality", "primary", 90, 2),
                make_factor("Financial Compatibility", "primary", 80, 3),
                make_factor("Family Compatibility", "primary", 75, 4),
                make_factor("Lifestyle Compatibility", "secondary", 70, 5),
                make_factor("Emotional Maturity", "secondary", 85, 6),
                make_factor("Conflict Resolution Ability", "secondary", 65, 7),
                make_factor("Long-term Vision Alignment", "secondary", 60, 8),
            ],
            "suggested_questions_json": [
                "Do you share the same core values (religion, money, children)?",
                "How do you handle disagreements together?",
                "Have you discussed financial goals and responsibilities?",
                "Do your families support the relationship?",
            ],
            "starter_notes": "Marriage is a partnership. Evaluate compatibility across all life dimensions, not just romantic feelings.",
            "future_cld_placeholder_json": {
                "starter_variables": ["communication_quality", "trust", "shared_values", "external_pressure"],
                "potential_loops": ["trust-communication-intimacy", "conflict-resolution-growth"],
            },
        },
        {
            "id": str(uuid.uuid4()), "template_id": "tpl_fin_cashflow_starter",
            "default_factors_json": [
                make_factor("Monthly Revenue", "primary", 90, 1, "USD"),
                make_factor("Monthly Expenses", "primary", 85, 2, "USD"),
                make_factor("Burn Rate", "primary", 80, 3, "%"),
                make_factor("Payment Collection Cycle", "primary", 75, 4, "days", 30),
                make_factor("Emergency Fund Coverage", "secondary", 70, 5, "months", 3),
            ],
            "suggested_questions_json": [
                "What is your actual monthly burn rate vs projected?",
                "How long is your average payment collection cycle?",
            ],
            "starter_notes": "CLD Starter: Map the cash flow feedback loops between revenue, expenses, and runway.",
            "future_cld_placeholder_json": {
                "starter_variables": ["revenue", "expenses", "burn_rate", "runway", "collection_cycle"],
                "potential_loops": ["revenue-investment-growth", "expenses-runway-stress-decisions"],
                "node_hints": [
                    {"variable": "revenue", "type": "stock"},
                    {"variable": "expenses", "type": "stock"},
                    {"variable": "burn_rate", "type": "flow"},
                ],
            },
        },
        {
            "id": str(uuid.uuid4()), "template_id": "tpl_car_burnout_starter",
            "default_factors_json": [
                make_factor("Weekly Work Hours", "primary", 85, 1, "hours", 50),
                make_factor("Recovery Time", "primary", 80, 2, "hours", 10),
                make_factor("Team Support Level", "primary", 75, 3),
                make_factor("Delegation Effectiveness", "secondary", 70, 4),
                make_factor("Personal Boundary Setting", "secondary", 65, 5),
            ],
            "suggested_questions_json": [
                "How many hours per week are you actually working?",
                "When did you last take more than 2 days completely off?",
            ],
            "starter_notes": "CLD Starter: Map the burnout cycle — overwork → reduced performance → more work → deeper burnout.",
            "future_cld_placeholder_json": {
                "starter_variables": ["workload", "stress", "performance", "recovery", "delegation"],
                "potential_loops": ["workload-stress-performance-more_work (reinforcing)", "recovery-performance-confidence (balancing)"],
            },
        },
        {
            "id": str(uuid.uuid4()), "template_id": "tpl_fin_raise_funding",
            "default_factors_json": [
                make_factor("Current Runway", "primary", 90, 1, "months", 18),
                make_factor("Revenue Growth Rate", "primary", 85, 2, "%", 15),
                make_factor("Equity Dilution Impact", "primary", 80, 3, "%"),
                make_factor("Investor Value-Add", "primary", 75, 4),
                make_factor("Founder Control Retention", "secondary", 70, 5),
                make_factor("Market Timing", "secondary", 65, 6),
            ],
            "suggested_questions_json": [
                "Can you reach profitability without external funding?",
                "What percentage of equity are you willing to give up?",
                "Do potential investors bring strategic value beyond money?",
            ],
            "starter_notes": "Bootstrap preserves control, funding accelerates growth. Neither is universally better.",
            "future_cld_placeholder_json": {
                "starter_variables": ["runway", "growth_rate", "dilution", "control", "speed_to_market"],
                "potential_loops": ["funding-growth-valuation", "dilution-control-decision_speed"],
            },
        },
    ]
    await db.hos_template_defaults.insert_many(template_defaults)

    # Create indexes for search performance
    await db.hos_decision_templates.create_index([("title", "text"), ("description", "text"), ("tags", "text")])
    await db.hos_decision_templates.create_index("life_area_id")
    await db.hos_decision_templates.create_index("ask_type_id")
    await db.hos_decision_templates.create_index("acting_as_contexts")
    await db.hos_sub_areas.create_index("life_area_id")
    await db.hos_decision_categories.create_index("sub_area_id")

    return {
        "message": "HOS master data seeded successfully",
        "counts": {
            "life_areas": len(life_areas),
            "ask_types": len(ask_types),
            "sub_areas": len(sub_areas),
            "categories": len(categories),
            "templates": len(templates),
            "template_defaults": len(template_defaults),
        }
    }
