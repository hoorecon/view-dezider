"""
Social Learning Engine — Helpers
Utility functions used across the Social Learning module.
"""

import json
from datetime import datetime, timezone
from fastapi import HTTPException, Request
from core.database import db


def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return ""


async def require_admin(user: dict):
    """Verify user has admin role. Raises 403 if not."""
    u = await db.users.find_one({"user_id": user["user_id"]})
    if not u or u.get("role") not in ["admin", "org_admin", "super_admin"]:
        raise HTTPException(403, "Admin access required")
    return u


def build_template_doc(
    template_id: str, classification: dict, content: str,
    user: dict, source_url: str = None, source_name: str = None,
    title: str = None, input_mode: str = "text",
) -> dict:
    """Build a template document from enhanced AI classification."""
    now = datetime.now(timezone.utc).isoformat()

    # Extract the new structured data
    la_mapping = classification.get("life_area_mapping", {})
    region = classification.get("region_hierarchy", {})
    scenario = classification.get("scenario_mapping", {})
    mydezider = classification.get("learnings_for_mydezider", {})
    solution_finder = classification.get("learnings_for_solution_finder", {})

    # Backward-compatible life_areas list
    life_areas = [la_mapping.get("primary_life_area_id", "")]
    life_areas += classification.get("secondary_life_areas", [])
    life_areas = [la for la in life_areas if la]

    # Factors: enrich with approval status
    factors = mydezider.get("factors", [])
    for f in factors:
        f["approved"] = False  # User must review and approve
        f["modified_by_user"] = False

    # Risks: enrich with approval status
    risks = solution_finder.get("risks", [])
    for r in risks:
        r["approved"] = False
        r["modified_by_user"] = False
        # Ensure risk_index is computed
        if "risk_index" not in r:
            r["risk_index"] = (r.get("probability", 5)) * (r.get("impact", 5))

    return {
        "id": template_id,
        "tier": 1,
        "status": "draft",
        "created_by": user["user_id"],
        "created_at": now,
        "updated_at": now,
        "input_mode": input_mode,

        # Source
        "original_content": content[:5000],
        "source_url": source_url,
        "source_name": source_name,
        "user_title": title,

        # AI Classification
        "detected_language": classification.get("detected_language", "english"),
        "english_summary": classification.get("english_summary", ""),
        "title": classification.get("original_title", title or "Untitled"),
        "category": classification.get("category", "problem"),
        "category_reasoning": classification.get("category_reasoning", ""),

        # Region Hierarchy
        "region_hierarchy": region,
        "geo_level": region.get("level", "global"),

        # Life Area Mapping (enhanced)
        "life_area_mapping": la_mapping,
        "life_areas": life_areas,
        "primary_life_area": la_mapping.get("primary_life_area_id", ""),
        "life_area_sub_area": la_mapping.get("sub_area_1", ""),
        "life_area_sub_area_2": la_mapping.get("sub_area_2"),
        "secondary_life_areas": classification.get("secondary_life_areas", []),

        # Org Types
        "org_types": classification.get("org_types", []),

        # Scenario Mapping
        "scenario_mapping": scenario,

        "severity_score": classification.get("severity_score", 5),

        # Learnings for My Dezider (Factors)
        "learnings_mydezider": {
            "factors": factors,
            "summary": mydezider.get("summary", ""),
        },
        # Backward compat
        "factors": factors,

        # Learnings for Solution Finder (Risks)
        "learnings_solution_finder": {
            "risks": risks,
            "summary": solution_finder.get("summary", ""),
        },
        # Backward compat
        "concerns": [
            {
                "concern": r.get("risk_name", ""),
                "severity": "high" if r.get("risk_index", 0) >= 50 else "medium" if r.get("risk_index", 0) >= 25 else "low",
                "mitigation": r.get("mitigation_plan", ""),
            }
            for r in risks
        ],

        "root_causes": classification.get("root_causes", []),
        "lessons_learned": classification.get("lessons_learned", []),
        "what_could_prevent": classification.get("what_could_prevent", ""),

        "tags": classification.get("tags", []),

        # Admin fields
        "admin_notes": "",
        "authorized_at": None,
        "authorized_by": None,
    }
