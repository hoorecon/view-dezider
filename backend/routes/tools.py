"""Solution Finder and Solution Matrix tool endpoints."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import Response
from core.database import db
from core.auth import get_current_user
from models.solution_matrix_models import (
    empty_layer_set,
    normalise_layer_set,
    normalise_matrix_mode,
    MATRIX_PARENT_LAYERS,
    MATRIX_MODES,
    ORG_TYPES,
)
from data.solution_matrix_templates import list_templates, get_template
from utils.solution_matrix_pdf import render_matrix_pdf

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
    # Apply timing + linking + single-option defaults (Enhancements #4 & #5)
    await db.solution_finders.update_one(
        {"entry_id": entry_id},
        {"$set": {
            "deadline_date": body.get("deadline_date"),
            "impact_horizon_value": body.get("impact_horizon_value", 7),
            "impact_horizon_unit": body.get("impact_horizon_unit", "days"),
            "linked_from_decision_id": body.get("linked_from_decision_id"),
            "linked_from_module": body.get("linked_from_module"),
            "linked_from_option_label": body.get("linked_from_option_label"),
            "linked_from_score_pct": body.get("linked_from_score_pct"),
            "allow_single_option": body.get("allow_single_option", False),
        }},
    )
    doc.update({
        "deadline_date": body.get("deadline_date"),
        "impact_horizon_value": body.get("impact_horizon_value", 7),
        "impact_horizon_unit": body.get("impact_horizon_unit", "days"),
        "linked_from_decision_id": body.get("linked_from_decision_id"),
        "linked_from_module": body.get("linked_from_module"),
        "linked_from_option_label": body.get("linked_from_option_label"),
        "linked_from_score_pct": body.get("linked_from_score_pct"),
        "allow_single_option": body.get("allow_single_option", False),
    })
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

# ---------- Templates ----------
# NOTE: These routes must be declared BEFORE `/solution-matrices/{entry_id}` so
# the literal path segments (`templates`) aren't captured by the entry_id route.
@router.get("/solution-matrices/templates")
async def list_solution_matrix_templates(user: dict = Depends(get_current_user)):
    """Return the lightweight list of starter templates for the picker UI."""
    return {"templates": list_templates()}


@router.get("/solution-matrices/templates/{template_id}")
async def get_solution_matrix_template(template_id: str, user: dict = Depends(get_current_user)):
    """Return a single template (metadata + payload) for preview / apply."""
    tpl = get_template(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl


# ---------- CRUD ----------
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
        # NEW: user-selectable matrix mode
        "matrix_mode": normalise_matrix_mode(body.get("matrix_mode")),
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
    # Back-fill defaults so older records render cleanly in the new UI
    entry.setdefault("matrix_mode", "accurate")
    for layer in MATRIX_PARENT_LAYERS:
        entry[layer] = normalise_layer_set(entry.get(layer))
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
        "matrix_mode",
        "matrix_self", "matrix_micro", "matrix_macro",
        "solution_category", "solution_sources",
        "q4_negative_consequences", "q4_mitigation_plans", "q4_contingency_plans",
        "action_items", "status",
    ]
    for field in allowed:
        if field in body:
            if field in MATRIX_PARENT_LAYERS:
                update_fields[field] = normalise_layer_set(body[field])
            elif field == "matrix_mode":
                update_fields[field] = normalise_matrix_mode(body[field])
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


# ---------- PDF Export ----------
@router.get("/solution-matrices/{entry_id}/pdf")
async def export_solution_matrix_pdf(entry_id: str, user: dict = Depends(get_current_user)):
    """Render a Solution Matrix entry as a landscape A4 PDF."""
    entry = await db.solution_matrices.find_one(
        {"entry_id": entry_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    # Normalise for renderer
    entry.setdefault("matrix_mode", "accurate")
    for layer in MATRIX_PARENT_LAYERS:
        entry[layer] = normalise_layer_set(entry.get(layer))
    try:
        pdf_bytes = render_matrix_pdf(entry)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"PDF render failed: {exc}")
    filename = f"solution_matrix_{entry_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
