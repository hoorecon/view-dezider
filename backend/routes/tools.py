"""Solution Finder and Solution Matrix tool endpoints."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user
from models.solution_matrix_models import (
    empty_layer_set,
    normalise_layer_set,
    MATRIX_PARENT_LAYERS,
)

router = APIRouter()


# ========================
# SIMPLE SOLUTION FINDER
# ========================

@router.post("/solution-finders")
async def create_solution_finder(request: Request, user: dict = Depends(get_current_user)):
    """Create a new Simple Solution Finder entry"""
    body = await request.json()
    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "entry_id": entry_id,
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "area_of_life": body.get("area_of_life", ""),
        "smart_goal": body.get("smart_goal", ""),
        "milestones": body.get("milestones", []),
        "q1_all_concerns": body.get("q1_all_concerns", ""),
        "q2_primary_concerns": body.get("q2_primary_concerns", ""),
        "q3_capabilities": body.get("q3_capabilities", ""),
        "q3_resources": body.get("q3_resources", ""),
        "q3_solutions": body.get("q3_solutions", ""),
        "external_help_aspect": body.get("external_help_aspect", ""),
        "external_help_level": body.get("external_help_level", ""),
        "external_help_from": body.get("external_help_from", ""),
        "q4_negative_consequences": body.get("q4_negative_consequences", ""),
        "q4_mitigation_plans": body.get("q4_mitigation_plans", ""),
        "q4_contingency_plans": body.get("q4_contingency_plans", ""),
        "action_items": body.get("action_items", []),
        "status": body.get("status", "in_progress"),
        "created_at": now,
        "updated_at": now,
    }

    await db.solution_finders.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/solution-finders")
async def list_solution_finders(user: dict = Depends(get_current_user)):
    query = {"user_id": user["user_id"]}
    entries = await db.solution_finders.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return entries


@router.get("/solution-finders/{entry_id}")
async def get_solution_finder(entry_id: str, user: dict = Depends(get_current_user)):
    entry = await db.solution_finders.find_one(
        {"entry_id": entry_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.put("/solution-finders/{entry_id}")
async def update_solution_finder(entry_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    entry = await db.solution_finders.find_one({"entry_id": entry_id, "user_id": user["user_id"]})
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    update_fields = {}
    allowed = [
        "area_of_life", "smart_goal", "milestones",
        "q1_all_concerns", "q2_primary_concerns",
        "q3_capabilities", "q3_resources", "q3_solutions",
        "external_help_aspect", "external_help_level", "external_help_from",
        "q4_negative_consequences", "q4_mitigation_plans", "q4_contingency_plans",
        "action_items", "status",
    ]
    for field in allowed:
        if field in body:
            update_fields[field] = body[field]
    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.solution_finders.update_one(
        {"entry_id": entry_id, "user_id": user["user_id"]}, {"$set": update_fields}
    )
    updated = await db.solution_finders.find_one({"entry_id": entry_id}, {"_id": 0})
    return updated


@router.delete("/solution-finders/{entry_id}")
async def delete_solution_finder(entry_id: str, user: dict = Depends(get_current_user)):
    result = await db.solution_finders.delete_one({"entry_id": entry_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"message": "Entry deleted"}


# ========================
# ADVANCED SOLUTION MATRIX
# ========================

@router.post("/solution-matrices")
async def create_solution_matrix(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "entry_id": entry_id,
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "area_of_life": body.get("area_of_life", ""),
        "smart_goal": body.get("smart_goal", ""),
        "milestones": body.get("milestones", []),
        "q1_all_concerns": body.get("q1_all_concerns", ""),
        "q2_priority_concerns": body.get("q2_priority_concerns", ""),
        "simpler_solutions": body.get("simpler_solutions", ""),
        "simpler_capabilities": body.get("simpler_capabilities", ""),
        "simpler_resources": body.get("simpler_resources", ""),
        "simpler_help_aspect": body.get("simpler_help_aspect", ""),
        "simpler_help_level": body.get("simpler_help_level", ""),
        "simpler_help_from": body.get("simpler_help_from", ""),
        "matrix_self": normalise_layer_set(body.get("matrix_self")),
        "matrix_micro": normalise_layer_set(body.get("matrix_micro")),
        "matrix_macro": normalise_layer_set(body.get("matrix_macro")),
        "solution_category": body.get("solution_category", {
            "completely_solvable": False, "partially_solvable": False,
            "not_solvable": False, "patience_period": False,
            "accept_let_go": False, "surrender_trust": False,
            "surrender_ignore": False, "surrender_involve": False,
        }),
        "solution_sources": body.get("solution_sources", {
            "from_self": "", "from_wellwisher": "",
            "from_experienced": "", "from_expert": "", "from_coach": "",
        }),
        "q4_negative_consequences": body.get("q4_negative_consequences", ""),
        "q4_mitigation_plans": body.get("q4_mitigation_plans", ""),
        "q4_contingency_plans": body.get("q4_contingency_plans", ""),
        "action_items": body.get("action_items", []),
        "status": body.get("status", "in_progress"),
        "created_at": now,
        "updated_at": now,
    }

    await db.solution_matrices.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/solution-matrices")
async def list_solution_matrices(user: dict = Depends(get_current_user)):
    query = {"user_id": user["user_id"]}
    entries = await db.solution_matrices.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return entries


@router.get("/solution-matrices/{entry_id}")
async def get_solution_matrix(entry_id: str, user: dict = Depends(get_current_user)):
    entry = await db.solution_matrices.find_one(
        {"entry_id": entry_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.put("/solution-matrices/{entry_id}")
async def update_solution_matrix(entry_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    entry = await db.solution_matrices.find_one({"entry_id": entry_id, "user_id": user["user_id"]})
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    update_fields = {}
    allowed = [
        "area_of_life", "smart_goal", "milestones",
        "q1_all_concerns", "q2_priority_concerns",
        "simpler_solutions", "simpler_capabilities", "simpler_resources",
        "simpler_help_aspect", "simpler_help_level", "simpler_help_from",
        "matrix_self", "matrix_micro", "matrix_macro",
        "solution_category", "solution_sources",
        "q4_negative_consequences", "q4_mitigation_plans", "q4_contingency_plans",
        "action_items", "status",
    ]
    for field in allowed:
        if field in body:
            if field in MATRIX_PARENT_LAYERS:
                # Normalise nested OrgType layout (accepts flat legacy too)
                update_fields[field] = normalise_layer_set(body[field])
            else:
                update_fields[field] = body[field]
    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.solution_matrices.update_one(
        {"entry_id": entry_id, "user_id": user["user_id"]}, {"$set": update_fields}
    )
    updated = await db.solution_matrices.find_one({"entry_id": entry_id}, {"_id": 0})
    return updated


@router.delete("/solution-matrices/{entry_id}")
async def delete_solution_matrix(entry_id: str, user: dict = Depends(get_current_user)):
    result = await db.solution_matrices.delete_one({"entry_id": entry_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"message": "Entry deleted"}
