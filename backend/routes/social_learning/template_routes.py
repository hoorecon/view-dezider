"""
Social Learning Engine — Template Routes
Template CRUD, submission, factor/risk approval, and re-analysis.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from routes.auth_routes import get_current_user
from routes.audit_trail import log_audit_event

from .models import FactorApprovalRequest, RiskApprovalRequest, ReAnalyzeRequest
from .helpers import get_client_ip
from .ai_engine import classify_news, EMERGENT_LLM_KEY

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/my-templates")
async def get_my_templates(
    status: Optional[str] = None,
    category: Optional[str] = None,
    life_area: Optional[str] = None,
    limit: int = 30,
    skip: int = 0,
    user: dict = Depends(get_current_user),
):
    """Get current user's Social Learning Templates."""
    query: dict = {"created_by": user["user_id"]}
    if status:
        query["status"] = status
    if category:
        query["category"] = category
    if life_area:
        query["life_areas"] = life_area

    total = await db.social_learning_templates.count_documents(query)
    templates = await db.social_learning_templates.find(
        query, {"_id": 0, "original_content": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    return {"total": total, "templates": templates}


@router.get("/template/{template_id}")
async def get_template(template_id: str, user: dict = Depends(get_current_user)):
    """Get a specific Social Learning Template with full details."""
    template = await db.social_learning_templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(404, "Template not found")

    if template["status"] == "draft" and template["created_by"] != user["user_id"]:
        u = await db.users.find_one({"user_id": user["user_id"]})
        if not u or u.get("role") not in ["admin", "org_admin", "super_admin"]:
            raise HTTPException(403, "Access denied")

    return template


@router.post("/template/{template_id}/submit")
async def submit_template(template_id: str, user: dict = Depends(get_current_user)):
    """Submit a draft template for admin review."""
    template = await db.social_learning_templates.find_one({"id": template_id})
    if not template:
        raise HTTPException(404, "Template not found")
    if template["created_by"] != user["user_id"]:
        raise HTTPException(403, "Only the creator can submit")
    if template["status"] != "draft":
        raise HTTPException(400, f"Template is already '{template['status']}', cannot submit")

    now = datetime.now(timezone.utc).isoformat()
    await db.social_learning_templates.update_one(
        {"id": template_id},
        {"$set": {"status": "submitted", "updated_at": now}}
    )

    return {"id": template_id, "status": "submitted", "message": "Template submitted for admin review"}


@router.delete("/template/{template_id}")
async def delete_template(template_id: str, user: dict = Depends(get_current_user)):
    """Delete a user's own draft template."""
    template = await db.social_learning_templates.find_one({"id": template_id})
    if not template:
        raise HTTPException(404, "Template not found")
    if template["created_by"] != user["user_id"]:
        u = await db.users.find_one({"user_id": user["user_id"]})
        if not u or u.get("role") not in ["admin", "org_admin", "super_admin"]:
            raise HTTPException(403, "Only the creator or admin can delete")
    if template["status"] == "authorized":
        raise HTTPException(400, "Cannot delete authorized templates")

    await db.social_learning_templates.delete_one({"id": template_id})
    return {"message": "Template deleted", "id": template_id}


# ========================
# FACTOR/RISK REVIEW & APPROVAL
# ========================

@router.post("/template/{template_id}/approve-factors")
async def approve_factors(template_id: str, data: FactorApprovalRequest, user: dict = Depends(get_current_user)):
    """User reviews and approves specific factors (with or without modifications)."""
    template = await db.social_learning_templates.find_one({"id": template_id})
    if not template:
        raise HTTPException(404, "Template not found")
    if template["created_by"] != user["user_id"]:
        raise HTTPException(403, "Only the creator can approve factors")

    factors = template.get("factors", [])
    learnings = template.get("learnings_mydezider", {})
    lm_factors = learnings.get("factors", factors)

    # Mark approved indices
    for i, f in enumerate(lm_factors):
        f["approved"] = i in data.approved_factor_indices

    # Apply user modifications
    if data.modified_factors:
        for mf in data.modified_factors:
            idx = mf.get("index")
            if idx is not None and 0 <= idx < len(lm_factors):
                for key in ["name", "expected_value", "expected_value_pct", "classification", "practical_priority", "practical_priority_num"]:
                    if key in mf:
                        lm_factors[idx][key] = mf[key]
                lm_factors[idx]["modified_by_user"] = True
                lm_factors[idx]["approved"] = True

    now = datetime.now(timezone.utc).isoformat()
    await db.social_learning_templates.update_one(
        {"id": template_id},
        {"$set": {
            "learnings_mydezider.factors": lm_factors,
            "factors": lm_factors,
            "updated_at": now,
        }}
    )
    return {"id": template_id, "approved_count": sum(1 for f in lm_factors if f.get("approved")), "total": len(lm_factors)}


@router.post("/template/{template_id}/approve-risks")
async def approve_risks(template_id: str, data: RiskApprovalRequest, user: dict = Depends(get_current_user)):
    """User reviews and approves specific risks (with or without modifications)."""
    template = await db.social_learning_templates.find_one({"id": template_id})
    if not template:
        raise HTTPException(404, "Template not found")
    if template["created_by"] != user["user_id"]:
        raise HTTPException(403, "Only the creator can approve risks")

    learnings = template.get("learnings_solution_finder", {})
    risks = learnings.get("risks", [])

    for i, r in enumerate(risks):
        r["approved"] = i in data.approved_risk_indices

    if data.modified_risks:
        for mr in data.modified_risks:
            idx = mr.get("index")
            if idx is not None and 0 <= idx < len(risks):
                for key in ["risk_name", "probability", "impact", "mitigation_plan", "contingency_plan"]:
                    if key in mr:
                        risks[idx][key] = mr[key]
                if "probability" in mr or "impact" in mr:
                    risks[idx]["risk_index"] = risks[idx].get("probability", 5) * risks[idx].get("impact", 5)
                risks[idx]["modified_by_user"] = True
                risks[idx]["approved"] = True

    now = datetime.now(timezone.utc).isoformat()
    await db.social_learning_templates.update_one(
        {"id": template_id},
        {"$set": {
            "learnings_solution_finder.risks": risks,
            "updated_at": now,
        }}
    )
    return {"id": template_id, "approved_count": sum(1 for r in risks if r.get("approved")), "total": len(risks)}


@router.post("/template/{template_id}/re-analyze")
async def re_analyze_template(template_id: str, data: ReAnalyzeRequest, request: Request, user: dict = Depends(get_current_user)):
    """Re-analyze a template with additional user context."""
    template = await db.social_learning_templates.find_one({"id": template_id})
    if not template:
        raise HTTPException(404, "Template not found")
    if template["created_by"] != user["user_id"]:
        raise HTTPException(403, "Only the creator can re-analyze")

    original_content = template.get("original_content", "")
    if not original_content:
        raise HTTPException(400, "No original content available for re-analysis")

    # Re-classify with additional context
    enhanced_content = f"""{original_content}

--- ADDITIONAL USER CONTEXT ---
{data.additional_context}
{f"Focus on: {data.focus_area}" if data.focus_area else ""}"""

    try:
        classification = await classify_news(enhanced_content)
    except Exception as e:
        logger.error(f"Re-analysis failed: {e}")
        raise HTTPException(500, f"Re-analysis failed: {str(e)}")

    # Build updated fields
    la_mapping = classification.get("life_area_mapping", {})
    region = classification.get("region_hierarchy", {})
    scenario = classification.get("scenario_mapping", {})
    mydezider = classification.get("learnings_for_mydezider", {})
    solution_finder = classification.get("learnings_for_solution_finder", {})

    factors = mydezider.get("factors", [])
    for f in factors:
        f["approved"] = False
        f["modified_by_user"] = False

    risks = solution_finder.get("risks", [])
    for r in risks:
        r["approved"] = False
        r["modified_by_user"] = False
        if "risk_index" not in r:
            r["risk_index"] = r.get("probability", 5) * r.get("impact", 5)

    life_areas = [la_mapping.get("primary_life_area_id", "")]
    life_areas += classification.get("secondary_life_areas", [])
    life_areas = [la for la in life_areas if la]

    now = datetime.now(timezone.utc).isoformat()
    update = {
        "english_summary": classification.get("english_summary", template.get("english_summary", "")),
        "title": classification.get("original_title", template.get("title", "")),
        "category": classification.get("category", template.get("category", "")),
        "region_hierarchy": region,
        "geo_level": region.get("level", "global"),
        "life_area_mapping": la_mapping,
        "life_areas": life_areas,
        "primary_life_area": la_mapping.get("primary_life_area_id", ""),
        "life_area_sub_area": la_mapping.get("sub_area_1", ""),
        "life_area_sub_area_2": la_mapping.get("sub_area_2"),
        "scenario_mapping": scenario,
        "learnings_mydezider": {"factors": factors, "summary": mydezider.get("summary", "")},
        "factors": factors,
        "learnings_solution_finder": {"risks": risks, "summary": solution_finder.get("summary", "")},
        "root_causes": classification.get("root_causes", []),
        "lessons_learned": classification.get("lessons_learned", []),
        "severity_score": classification.get("severity_score", 5),
        "tags": classification.get("tags", []),
        "updated_at": now,
        "re_analysis_context": data.additional_context,
        "re_analysis_count": template.get("re_analysis_count", 0) + 1,
    }

    await db.social_learning_templates.update_one({"id": template_id}, {"$set": update})

    updated = await db.social_learning_templates.find_one({"id": template_id}, {"_id": 0, "original_content": 0})
    return updated
