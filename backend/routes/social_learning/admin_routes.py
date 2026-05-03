"""
Social Learning Engine — Admin Routes
Admin approval, Tier 2/3 management, and browsing.
"""

import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from routes.auth_routes import get_current_user
from routes.audit_trail import log_audit_event

from .models import AdminApprovalRequest, SynthesizeRequest
from .helpers import get_client_ip, require_admin
from .ai_engine import synthesize_templates

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/admin/pending")
async def get_pending_templates(
    category: Optional[str] = None,
    life_area: Optional[str] = None,
    limit: int = 30,
    skip: int = 0,
    user: dict = Depends(get_current_user),
):
    """List submitted templates pending admin approval."""
    await require_admin(user)
    query: dict = {"status": "submitted"}
    if category:
        query["category"] = category
    if life_area:
        query["life_areas"] = life_area

    total = await db.social_learning_templates.count_documents(query)
    templates = await db.social_learning_templates.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    return {"total": total, "templates": templates}


@router.post("/admin/approve/{template_id}")
async def approve_template(template_id: str, data: AdminApprovalRequest, request: Request, user: dict = Depends(get_current_user)):
    """Approve or reject a submitted template. Approved = Tier 2."""
    await require_admin(user)

    template = await db.social_learning_templates.find_one({"id": template_id})
    if not template:
        raise HTTPException(404, "Template not found")
    if template["status"] != "submitted":
        raise HTTPException(400, f"Template status is '{template['status']}', expected 'submitted'")

    if data.status not in ["authorized", "rejected"]:
        raise HTTPException(400, "Status must be 'authorized' or 'rejected'")

    now = datetime.now(timezone.utc).isoformat()
    update = {
        "status": data.status,
        "admin_notes": data.admin_notes or "",
        "updated_at": now,
    }
    if data.status == "authorized":
        update["tier"] = 2
        update["authorized_at"] = now
        update["authorized_by"] = user["user_id"]

    await db.social_learning_templates.update_one({"id": template_id}, {"$set": update})

    await log_audit_event(
        action=f"social_learning_{data.status}", entity_type="social_learning",
        entity_id=template_id, user_id=user["user_id"],
        details=f"Template {data.status}: {template.get('title', '')[:60]}. Notes: {data.admin_notes or 'N/A'}",
        ip_address=get_client_ip(request),
    )

    return {"id": template_id, "status": data.status, "tier": 2 if data.status == "authorized" else 1}


@router.get("/authorized")
async def get_authorized_templates(
    category: Optional[str] = None,
    life_area: Optional[str] = None,
    org_type: Optional[str] = None,
    region: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 30,
    skip: int = 0,
    user: dict = Depends(get_current_user),
):
    """Browse Authorized Social Learning Templates (Tier 2). Available to all users."""
    query: dict = {"status": "authorized", "tier": 2}
    if category:
        query["category"] = category
    if life_area:
        query["life_areas"] = life_area
    if org_type:
        query["org_types"] = org_type
    if region:
        query["geo_regions"] = region
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"english_summary": {"$regex": search, "$options": "i"}},
            {"tags": {"$regex": search, "$options": "i"}},
        ]

    total = await db.social_learning_templates.count_documents(query)
    templates = await db.social_learning_templates.find(
        query, {"_id": 0, "original_content": 0}
    ).sort("severity_score", -1).skip(skip).limit(limit).to_list(limit)

    return {"total": total, "templates": templates}


# ========================
# TIER 3: Social Solution Templates (AI Synthesis)
# ========================

@router.post("/admin/synthesize")
async def synthesize_social_solution(data: SynthesizeRequest, request: Request, user: dict = Depends(get_current_user)):
    """Synthesize multiple Authorized templates into a Social Solution Template (Tier 3). Admin-only."""
    await require_admin(user)

    if len(data.template_ids) < 2:
        raise HTTPException(400, "At least 2 Authorized templates required for synthesis")

    templates = await db.social_learning_templates.find(
        {"id": {"$in": data.template_ids}, "status": "authorized", "tier": 2}, {"_id": 0}
    ).to_list(100)

    if len(templates) < 2:
        raise HTTPException(400, f"Only {len(templates)} authorized templates found. Need at least 2.")

    try:
        synthesis = await synthesize_templates(templates, {
            "target_region": data.target_region,
            "target_org_type": data.target_org_type,
            "target_life_area": data.target_life_area,
        })
    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        raise HTTPException(500, f"AI synthesis failed: {str(e)}")

    now = datetime.now(timezone.utc).isoformat()
    solution_id = f"SST-{uuid.uuid4().hex[:10].upper()}"

    solution = {
        "id": solution_id,
        "tier": 3,
        "status": "active",
        "created_by": user["user_id"],
        "created_at": now,

        "source_template_ids": data.template_ids,
        "source_count": len(templates),
        "target_region": data.target_region,
        "target_org_type": data.target_org_type,
        "target_life_area": data.target_life_area,

        "title": synthesis.get("title", "Synthesized Template"),
        "description": synthesis.get("description", ""),
        "category": synthesis.get("category", "problem"),
        "life_areas": synthesis.get("life_areas", []),
        "primary_life_area": synthesis.get("primary_life_area", ""),
        "life_area_sub_area": synthesis.get("life_area_sub_area", ""),
        "org_types": synthesis.get("org_types", []),
        "geo_relevance": synthesis.get("geo_relevance", ""),
        "pattern_identified": synthesis.get("pattern_identified", ""),

        "synthesized_factors": synthesis.get("synthesized_factors", []),
        "synthesized_concerns": synthesis.get("synthesized_concerns", []),
        "combined_lessons": synthesis.get("combined_lessons", []),
        "combined_root_causes": synthesis.get("combined_root_causes", []),
        "accuracy_notes": synthesis.get("accuracy_notes", ""),

        "premium_life_scenario": synthesis.get("premium_life_scenario", {}),

        "tags": synthesis.get("tags", []),
        "access_tier": "premium",
    }

    await db.social_solution_templates.insert_one(solution)

    await log_audit_event(
        action="social_solution_synthesized", entity_type="social_solution",
        entity_id=solution_id, user_id=user["user_id"],
        details=f"Social Solution Template synthesized from {len(templates)} sources: {solution['title'][:60]}",
        ip_address=get_client_ip(request),
    )

    solution.pop("_id", None)
    return solution


@router.get("/solutions")
async def get_social_solutions(
    category: Optional[str] = None,
    life_area: Optional[str] = None,
    org_type: Optional[str] = None,
    region: Optional[str] = None,
    access_tier: Optional[str] = None,
    limit: int = 30,
    skip: int = 0,
    user: dict = Depends(get_current_user),
):
    """Browse Social Solution Templates (Tier 3)."""
    query: dict = {"status": "active", "tier": 3}
    if category:
        query["category"] = category
    if life_area:
        query["life_areas"] = life_area
    if org_type:
        query["org_types"] = org_type
    if region:
        query["geo_relevance"] = {"$regex": region, "$options": "i"}
    if access_tier:
        query["access_tier"] = access_tier

    total = await db.social_solution_templates.count_documents(query)
    solutions = await db.social_solution_templates.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    return {"total": total, "solutions": solutions}


@router.get("/solution/{solution_id}")
async def get_social_solution(solution_id: str, user: dict = Depends(get_current_user)):
    """Get a specific Social Solution Template."""
    solution = await db.social_solution_templates.find_one({"id": solution_id}, {"_id": 0})
    if not solution:
        raise HTTPException(404, "Social Solution Template not found")
    return solution
