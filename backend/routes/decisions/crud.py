"""PRR Decision CRUD + clone routes."""

import uuid
import logging
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from core.trash import move_to_trash
from core.auth import get_current_user
from models.decisions_models import (
    PRRDecision, PRRDecisionCreate, PRRDecisionUpdate, CloneDecisionRequest,
)
from .services import consume_entitlement

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Decisions"])


@router.post("/decisions", response_model=dict)
async def create_decision(decision: PRRDecisionCreate, user: dict = Depends(get_current_user)):
    # Enforce free-use quota (WOWO Access Control add-on).
    from routes.module_limits import check_and_reserve_usage
    await check_and_reserve_usage(user, "my_dezider")

    user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    org_id = user_doc.get("org_id") if user_doc else None
    decision_doc = PRRDecision(
        user_id=user["user_id"], title=decision.title, context=decision.context,
        folder=decision.folder, life_area=decision.life_area,
        decision_type=decision.decision_type,
        implementation_review_date=decision.implementation_review_date
    )
    doc_dict = decision_doc.dict()
    doc_dict["org_id"] = org_id
    await db.decisions.insert_one(doc_dict)
    # Consume one entitlement for this new decision (prefers L2 bundle → L1) and
    # pre-unlock its report so the PDF stays free.
    await consume_entitlement(user["user_id"], decision_doc.id, context="create")
    return {"id": decision_doc.id, "message": "Decision created successfully"}


@router.get("/decisions", response_model=List[dict])
async def get_decisions(user: dict = Depends(get_current_user), folder: str = None):
    query = {"user_id": user["user_id"]}
    if folder:
        query["folder"] = folder
    decisions = await db.decisions.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return decisions


@router.get("/decisions/{decision_id}")
async def get_decision(decision_id: str, user: dict = Depends(get_current_user)):
    decision = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    return decision


@router.put("/decisions/{decision_id}")
async def update_decision(decision_id: str, update_data: PRRDecisionUpdate, user: dict = Depends(get_current_user)):
    existing = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Decision not found")
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    update_dict["updated_at"] = datetime.now(timezone.utc)
    if "options" in update_dict and "factors" in update_dict:
        factors = update_dict["factors"]
        options = update_dict["options"]
        total_rating = sum(f["rating"] for f in factors)
        for option in options:
            if total_rating > 0:
                worth = 0.0
                for assessment in option.get("assessments", []):
                    factor = next((f for f in factors if f["id"] == assessment["factor_id"]), None)
                    if factor:
                        pct = assessment.get("percentage") or 0
                        clamped_pct = max(0, min(100, pct))
                        assessment["percentage"] = clamped_pct
                        worth += (factor["rating"] / total_rating) * clamped_pct
                option["worth_percentage"] = round(min(100.0, max(0.0, worth)), 2)
            else:
                option["worth_percentage"] = 0.0
    await db.decisions.update_one({"id": decision_id}, {"$set": update_dict})
    return {"message": "Decision updated successfully"}


@router.delete("/decisions/{decision_id}")
async def delete_decision(decision_id: str, user: dict = Depends(get_current_user)):
    moved = await move_to_trash("decision", decision_id, user["user_id"])
    if not moved:
        raise HTTPException(status_code=404, detail="Decision not found")
    return {"message": "Decision moved to Trash"}


@router.post("/decisions/{decision_id}/clone")
async def clone_decision(decision_id: str, data: CloneDecisionRequest, user: dict = Depends(get_current_user)):
    original = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not original:
        raise HTTPException(status_code=404, detail="Decision not found")
    new_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    cloned = {
        "id": new_id, "user_id": user["user_id"], "title": data.title,
        "context": original.get("context", ""), "factors": [], "options": [],
        "chosen_option_id": None, "decision_case": None, "notes": "", "reflection": "",
        "final_notes": "", "folder": original.get("folder", ""), "status": "draft",
        "created_at": now, "updated_at": now,
    }
    clone_level = data.clone_level
    if clone_level in ("factors", "classification", "prioritization", "options", "assessment"):
        for f in original.get("factors", []):
            cloned["factors"].append({"id": str(uuid.uuid4()), "name": f["name"], "order": f.get("order", 0), "category": "", "rating": 0})
    if clone_level in ("classification", "prioritization", "options", "assessment"):
        for i, f in enumerate(original.get("factors", [])):
            if i < len(cloned["factors"]):
                cloned["factors"][i]["category"] = f.get("category", "primary")
    if clone_level in ("prioritization", "options", "assessment"):
        for i, f in enumerate(original.get("factors", [])):
            if i < len(cloned["factors"]):
                cloned["factors"][i]["rating"] = f.get("rating", 0)
    if clone_level in ("options", "assessment"):
        for opt in original.get("options", []):
            cloned["options"].append({"id": str(uuid.uuid4()), "name": opt["name"], "assessments": [], "worth_percentage": 0.0})
    if clone_level == "assessment":
        factor_id_map = {}
        for i, orig_f in enumerate(original.get("factors", [])):
            if i < len(cloned["factors"]):
                factor_id_map[orig_f["id"]] = cloned["factors"][i]["id"]
        for i, opt in enumerate(original.get("options", [])):
            if i < len(cloned["options"]):
                new_assessments = []
                for asmt in opt.get("assessments", []):
                    new_factor_id = factor_id_map.get(asmt["factor_id"], asmt["factor_id"])
                    new_assessments.append({"factor_id": new_factor_id, "percentage": asmt.get("percentage"),
                                            "unit_value": asmt.get("unit_value"), "assessment_mode": asmt.get("assessment_mode")})
                cloned["options"][i]["assessments"] = new_assessments
                cloned["options"][i]["worth_percentage"] = opt.get("worth_percentage", 0.0)
    await db.decisions.insert_one(cloned)
    await consume_entitlement(user["user_id"], new_id, context="clone")
    return {"id": new_id, "message": f"Decision cloned successfully (level: {clone_level})"}
