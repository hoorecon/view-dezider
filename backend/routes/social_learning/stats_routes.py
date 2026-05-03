"""
Social Learning Engine — Stats Routes
Statistics and filter options.
"""

from fastapi import APIRouter, Depends
from core.database import db
from routes.auth_routes import get_current_user

from .constants import CATEGORIES, LIFE_AREAS, ORG_TYPES, SUPPORTED_LANGUAGES, TEMPLATE_STATUSES

router = APIRouter()


@router.get("/stats")
async def get_social_learning_stats(user: dict = Depends(get_current_user)):
    """Get overall social learning statistics."""
    total_t1 = await db.social_learning_templates.count_documents({"tier": 1})
    total_t2 = await db.social_learning_templates.count_documents({"tier": 2, "status": "authorized"})
    total_t3 = await db.social_solution_templates.count_documents({"tier": 3})
    pending = await db.social_learning_templates.count_documents({"status": "submitted"})
    my_count = await db.social_learning_templates.count_documents({"created_by": user["user_id"]})

    pipeline = [
        {"$match": {"status": "authorized"}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
    ]
    cat_breakdown = await db.social_learning_templates.aggregate(pipeline).to_list(10)

    pipeline_la = [
        {"$match": {"status": "authorized"}},
        {"$unwind": "$life_areas"},
        {"$group": {"_id": "$life_areas", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    la_breakdown = await db.social_learning_templates.aggregate(pipeline_la).to_list(20)

    return {
        "tier_1_user_templates": total_t1,
        "tier_2_authorized": total_t2,
        "tier_3_solutions": total_t3,
        "pending_review": pending,
        "my_templates": my_count,
        "category_breakdown": [{**c, "category": c["_id"]} for c in cat_breakdown],
        "life_area_breakdown": [{**la, "life_area": la["_id"]} for la in la_breakdown],
    }


@router.get("/filter-options")
async def get_filter_options(user: dict = Depends(get_current_user)):
    """Get available filter options for browsing templates."""
    return {
        "categories": CATEGORIES,
        "life_areas": LIFE_AREAS,
        "org_types": ORG_TYPES,
        "languages": SUPPORTED_LANGUAGES,
        "template_statuses": TEMPLATE_STATUSES,
    }
