"""
Social Learning Engine — Integration Routes
3-Tier integration endpoints for My Dezider (Decision Flow) and Solution Finder.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends
from core.database import db
from routes.auth_routes import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/templates-for-decision")
async def get_templates_for_decision(
    life_area: Optional[str] = None,
    sub_area: Optional[str] = None,
    category: Optional[str] = None,
    org_type: Optional[str] = None,
    region: Optional[str] = None,
    include_personal: bool = False,
    limit: int = 20,
    user: dict = Depends(get_current_user),
):
    """Get factor suggestions for My Dezider decision flow.
    Returns 3-tier structure: Personal (Tier 1), Admin-Authorized (Tier 2), AI-Derived (Tier 3).
    Filters by OrgType, Region, LifeArea, SubArea, Scenario.
    """
    tier_1 = []
    tier_2 = []
    tier_3 = []

    # Helper to build factor suggestion from template
    def extract_factors(t, source_tier, source_label):
        factors = t.get("factors", [])
        learnings = t.get("learnings_mydezider", {})
        if learnings.get("factors"):
            factors = learnings["factors"]

        scenario = t.get("scenario_mapping", {})
        return {
            "id": t.get("id", ""),
            "tier": source_tier,
            "source": source_label,
            "title": t.get("title", ""),
            "category": t.get("category", ""),
            "life_areas": t.get("life_areas", []),
            "primary_life_area": t.get("primary_life_area", ""),
            "sub_area": t.get("life_area_sub_area", ""),
            "sub_area_2": t.get("life_area_sub_area_2"),
            "region_hierarchy": t.get("region_hierarchy", {}),
            "org_types": t.get("org_types", []),
            "scenario_title": scenario.get("suggested_new_scenario", {}).get("title", "") or scenario.get("predefined_scenario_title", ""),
            "severity_score": t.get("severity_score", 5),
            "factors": [
                {
                    "name": f.get("name", ""),
                    "description": f.get("description", ""),
                    "practical_priority": f.get("practical_priority", "P5"),
                    "practical_priority_num": f.get("practical_priority_num", 5),
                    "classification": f.get("classification", "optional"),
                    "expected_value": f.get("expected_value", ""),
                    "expected_value_pct": f.get("expected_value_pct", 50),
                    "factor_type": f.get("factor_type", "qualitative"),
                    "unit": f.get("unit"),
                    "approved": f.get("approved", False),
                }
                for f in factors
            ],
            "factor_summary": learnings.get("summary", ""),
        }

    # Build base query filters
    base_filter: dict = {}
    if life_area:
        base_filter["$or"] = [{"life_areas": life_area}, {"primary_life_area": life_area}]
    if sub_area:
        base_filter["life_area_sub_area"] = {"$regex": sub_area, "$options": "i"}
    if category:
        base_filter["category"] = category
    if org_type:
        base_filter["org_types"] = org_type
    if region:
        base_filter["$or"] = base_filter.get("$or", []) + [
            {"region_hierarchy.country": {"$regex": region, "$options": "i"}},
            {"region_hierarchy.state": {"$regex": region, "$options": "i"}},
        ]

    # Tier 1: User's own templates (personal)
    if include_personal:
        t1_query = {**base_filter, "created_by": user["user_id"]}
        t1_query.setdefault("status", {"$in": ["draft", "submitted", "authorized"]})
        t1_templates = await db.social_learning_templates.find(
            t1_query, {"_id": 0, "original_content": 0}
        ).sort("severity_score", -1).limit(limit).to_list(limit)
        for t in t1_templates:
            tier_1.append(extract_factors(t, 1, "personal"))

    # Tier 2: Admin-authorized templates
    t2_query = {**base_filter, "status": "authorized", "tier": 2}
    t2_templates = await db.social_learning_templates.find(
        t2_query, {"_id": 0, "original_content": 0}
    ).sort("severity_score", -1).limit(limit).to_list(limit)
    for t in t2_templates:
        tier_2.append(extract_factors(t, 2, "authorized"))

    # Tier 3: AI-derived Social Solution Templates
    t3_query: dict = {"status": "active", "tier": 3}
    if life_area:
        t3_query["$or"] = [{"life_areas": life_area}, {"primary_life_area": life_area}]
    t3_solutions = await db.social_solution_templates.find(
        t3_query, {"_id": 0}
    ).sort("created_at", -1).limit(limit // 2).to_list(limit // 2)
    for s in t3_solutions:
        synth_factors = s.get("synthesized_factors", [])
        tier_3.append({
            "id": s["id"],
            "tier": 3,
            "source": "ai_derived",
            "title": s.get("title", ""),
            "category": s.get("category", ""),
            "life_areas": s.get("life_areas", []),
            "primary_life_area": s.get("primary_life_area", ""),
            "sub_area": s.get("life_area_sub_area", ""),
            "severity_score": 8,
            "scenario_title": s.get("pattern_identified", ""),
            "source_count": s.get("source_count", 0),
            "factors": [
                {
                    "name": f.get("name", ""),
                    "description": "",
                    "practical_priority_num": f.get("priority", 5),
                    "practical_priority": f"P{f.get('priority', 5)}",
                    "classification": "mandatory" if f.get("priority", 5) >= 7 else "optional",
                    "expected_value_pct": f.get("expected_value_pct", 50),
                    "factor_type": "qualitative",
                    "confidence": f.get("confidence", "medium"),
                    "supporting_template_count": f.get("supporting_template_count", 1),
                }
                for f in synth_factors
            ],
            "factor_summary": s.get("accuracy_notes", ""),
        })

    return {
        "tier_1_personal": tier_1,
        "tier_2_authorized": tier_2,
        "tier_3_ai_derived": tier_3,
        "total": len(tier_1) + len(tier_2) + len(tier_3),
    }


@router.get("/templates-for-solution-finder")
async def get_templates_for_solution_finder(
    life_area: Optional[str] = None,
    sub_area: Optional[str] = None,
    category: Optional[str] = None,
    org_type: Optional[str] = None,
    region: Optional[str] = None,
    include_personal: bool = False,
    limit: int = 20,
    user: dict = Depends(get_current_user),
):
    """Get risk suggestions for Solution Finder Q4.
    Returns 3-tier structure: Personal (Tier 1), Admin-Authorized (Tier 2), AI-Derived (Tier 3).
    """
    tier_1 = []
    tier_2 = []
    tier_3 = []

    def extract_risks(t, source_tier, source_label):
        learnings = t.get("learnings_solution_finder", {})
        risks = learnings.get("risks", [])
        scenario = t.get("scenario_mapping", {})
        return {
            "id": t.get("id", ""),
            "tier": source_tier,
            "source": source_label,
            "title": t.get("title", ""),
            "category": t.get("category", ""),
            "life_areas": t.get("life_areas", []),
            "primary_life_area": t.get("primary_life_area", ""),
            "sub_area": t.get("life_area_sub_area", ""),
            "region_hierarchy": t.get("region_hierarchy", {}),
            "org_types": t.get("org_types", []),
            "scenario_title": scenario.get("suggested_new_scenario", {}).get("title", "") or scenario.get("predefined_scenario_title", ""),
            "severity_score": t.get("severity_score", 5),
            "risks": [
                {
                    "risk_name": r.get("risk_name", ""),
                    "description": r.get("description", ""),
                    "probability": r.get("probability", 5),
                    "impact": r.get("impact", 5),
                    "risk_index": r.get("risk_index", 25),
                    "mitigation_plan": r.get("mitigation_plan", ""),
                    "contingency_plan": r.get("contingency_plan", ""),
                    "personalization_note": r.get("personalization_note", ""),
                    "approved": r.get("approved", False),
                }
                for r in risks
            ],
            "risk_summary": learnings.get("summary", ""),
        }

    base_filter: dict = {}
    if life_area:
        base_filter["$or"] = [{"life_areas": life_area}, {"primary_life_area": life_area}]
    if sub_area:
        base_filter["life_area_sub_area"] = {"$regex": sub_area, "$options": "i"}
    if category:
        base_filter["category"] = category
    if org_type:
        base_filter["org_types"] = org_type

    # Tier 1: Personal
    if include_personal:
        t1_query = {**base_filter, "created_by": user["user_id"]}
        t1_query.setdefault("status", {"$in": ["draft", "submitted", "authorized"]})
        t1_templates = await db.social_learning_templates.find(
            t1_query, {"_id": 0, "original_content": 0}
        ).sort("severity_score", -1).limit(limit).to_list(limit)
        for t in t1_templates:
            tier_1.append(extract_risks(t, 1, "personal"))

    # Tier 2: Authorized
    t2_query = {**base_filter, "status": "authorized", "tier": 2}
    t2_templates = await db.social_learning_templates.find(
        t2_query, {"_id": 0, "original_content": 0}
    ).sort("severity_score", -1).limit(limit).to_list(limit)
    for t in t2_templates:
        tier_2.append(extract_risks(t, 2, "authorized"))

    # Tier 3: AI-derived
    t3_query: dict = {"status": "active", "tier": 3}
    if life_area:
        t3_query["$or"] = [{"life_areas": life_area}, {"primary_life_area": life_area}]
    t3_solutions = await db.social_solution_templates.find(
        t3_query, {"_id": 0}
    ).sort("created_at", -1).limit(limit // 2).to_list(limit // 2)
    for s in t3_solutions:
        synth_concerns = s.get("synthesized_concerns", [])
        tier_3.append({
            "id": s["id"],
            "tier": 3,
            "source": "ai_derived",
            "title": s.get("title", ""),
            "category": s.get("category", ""),
            "life_areas": s.get("life_areas", []),
            "primary_life_area": s.get("primary_life_area", ""),
            "severity_score": 8,
            "source_count": s.get("source_count", 0),
            "risks": [
                {
                    "risk_name": c.get("concern", ""),
                    "description": "",
                    "probability": 6,
                    "impact": 7 if c.get("severity") == "high" else 5 if c.get("severity") == "medium" else 3,
                    "risk_index": 6 * (7 if c.get("severity") == "high" else 5 if c.get("severity") == "medium" else 3),
                    "mitigation_plan": c.get("mitigation_consensus", ""),
                    "contingency_plan": "",
                    "frequency": c.get("frequency", ""),
                }
                for c in synth_concerns
            ],
            "risk_summary": s.get("accuracy_notes", ""),
        })

    return {
        "tier_1_personal": tier_1,
        "tier_2_authorized": tier_2,
        "tier_3_ai_derived": tier_3,
        "total": len(tier_1) + len(tier_2) + len(tier_3),
    }
