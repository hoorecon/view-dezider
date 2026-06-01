"""Decisions routes — PRR CRUD, templates, cloning, Test123, Mode Assessment, Journal, Stats, Folders, Step Sharing, MPPS"""

import uuid
import os
import io
import csv
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from core.database import db
from core.auth import (
    get_current_user, require_admin, require_root_super_admin,
    get_user_role, get_role_level, ADMIN_ROLES, ROOT_SUPER_ADMIN_EMAIL,
)
from core.helpers import create_notification
from models.decisions_models import (
    # PRR Decisions
    Factor, OptionAssessment, MPPSActionItem, MPPSImprovement,
    DecisionOption, PRRDecision, PRRDecisionCreate, PRRDecisionUpdate,
    CloneDecisionRequest,
    # Templates
    SaveTemplateRequest, UseTemplateRequest,
    # Admin
    PromoteUserRequest, DemoteUserRequest,
    # Test123
    Test123Session, Test123Create, Test123Update,
    # Assessment
    ModeAssessmentCreate, ModeAssessmentResult,
    # Journal
    JournalEntry, JournalEntryCreate, JournalEntryUpdate,
    VALID_LINKED_MODULES, VALID_ENTRY_TYPES,
    # Step Sharing
    ShareStepRequest, ContributeStepRequest, MergeStepRequest,
    NotificationCreate,
    # Static reference
    DECISION_FOLDERS, ASSESSMENT_QUESTIONS,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Decisions"])


# ========================
# PRR DECISION CRUD
# ========================

@router.post("/decisions", response_model=dict)
async def create_decision(decision: PRRDecisionCreate, user: dict = Depends(get_current_user)):
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
    result = await db.decisions.delete_one({"id": decision_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Decision not found")
    return {"message": "Decision deleted successfully"}

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
            cloned["factors"].append({"id": str(uuid.uuid4()), "name": f["name"], "order": f.get("order", 0), "category": "primary", "rating": 0})
    if clone_level in ("classification", "prioritization", "options", "assessment"):
        for i, f in enumerate(original.get("factors", [])):
            if i < len(cloned["factors"]):
                cloned["factors"][i]["category"] = f.get("category", "primary")
    if clone_level in ("prioritization", "options", "assessment"):
        for i, f in enumerate(original.get("factors", [])):
            if i < len(cloned["factors"]):
                cloned["factors"][i]["rating"] = f.get("rating", 0)
    if clone_level in ("options", "assessment"):
        factor_id_map = {}
        for i, orig_f in enumerate(original.get("factors", [])):
            if i < len(cloned["factors"]):
                factor_id_map[orig_f["id"]] = cloned["factors"][i]["id"]
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
    return {"id": new_id, "message": f"Decision cloned successfully (level: {clone_level})"}


# ========================
# TEMPLATE ROUTES
# ========================

@router.post("/decisions/{decision_id}/save-as-template")
async def save_as_template(decision_id: str, data: SaveTemplateRequest, user: dict = Depends(get_current_user)):
    original = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not original:
        raise HTTPException(status_code=404, detail="Decision not found")
    template_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # 5 cumulative depth levels, identical semantics to /clone:
    #   factors < classification < prioritization < options < assessment
    level = data.template_type
    if level not in ("factors", "classification", "prioritization", "options", "assessment"):
        level = "options"  # backward-compatible default

    orig_factors = original.get("factors", [])
    factors = []
    for f in orig_factors:
        factors.append({"id": str(uuid.uuid4()), "name": f["name"], "order": f.get("order", 0),
                        "category": "primary", "rating": 0})
    if level in ("classification", "prioritization", "options", "assessment"):
        for i, f in enumerate(orig_factors):
            if i < len(factors):
                factors[i]["category"] = f.get("category", "primary")
    if level in ("prioritization", "options", "assessment"):
        for i, f in enumerate(orig_factors):
            if i < len(factors):
                factors[i]["rating"] = f.get("rating", 0)

    options = []
    if level in ("options", "assessment"):
        factor_id_map = {}
        for i, of in enumerate(orig_factors):
            if i < len(factors):
                factor_id_map[of["id"]] = factors[i]["id"]
        for opt in original.get("options", []):
            new_opt = {"id": str(uuid.uuid4()), "name": opt["name"], "assessments": [], "worth_percentage": 0.0}
            if level == "assessment":
                for asmt in opt.get("assessments", []):
                    new_fid = factor_id_map.get(asmt["factor_id"], asmt["factor_id"])
                    new_opt["assessments"].append({"factor_id": new_fid, "percentage": asmt.get("percentage"),
                                                   "unit_value": asmt.get("unit_value"), "assessment_mode": asmt.get("assessment_mode")})
                new_opt["worth_percentage"] = opt.get("worth_percentage", 0.0)
            options.append(new_opt)

    template = {
        "id": template_id, "name": data.name, "template_type": level,
        "visibility": data.visibility,
        "shared_with": [e.strip().lower() for e in data.shared_with if e.strip()],
        "created_by": user["user_id"], "created_by_name": user.get("name", "Unknown"),
        "created_by_email": user.get("email", ""),
        "source_decision_title": original.get("title", ""),
        "context": original.get("context", ""), "factors": factors,
        "options": options, "created_at": now,
    }
    await db.templates.insert_one(template)
    return {"id": template_id, "message": "Template saved successfully"}

@router.get("/templates")
async def get_templates(user: dict = Depends(get_current_user)):
    user_email = user.get("email", "").lower()
    user_id = user["user_id"]
    all_templates = await db.templates.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    my_templates, shared_templates, public_templates, authorized_templates = [], [], [], []
    for t in all_templates:
        visibility = t.get("visibility", "private")
        created_by = t.get("created_by", "")
        shared_with = [e.lower() for e in t.get("shared_with", [])]
        is_authorized = t.get("authorized", False)
        if is_authorized and visibility == "public":
            authorized_templates.append(t)
        if created_by == user_id:
            my_templates.append(t)
        elif visibility == "shared" and user_email in shared_with:
            shared_templates.append(t)
        elif visibility == "public" and created_by != user_id and not is_authorized:
            public_templates.append(t)
    return {"my_templates": my_templates, "shared_templates": shared_templates,
            "public_templates": public_templates, "authorized_templates": authorized_templates}

@router.post("/templates/{template_id}/use")
async def use_template(template_id: str, data: UseTemplateRequest, user: dict = Depends(get_current_user)):
    template = await db.templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    new_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    factor_id_map = {}
    new_factors = []
    for f in template.get("factors", []):
        new_factor_id = str(uuid.uuid4())
        factor_id_map[f["id"]] = new_factor_id
        new_factors.append({"id": new_factor_id, "name": f["name"], "category": f.get("category", "primary"),
                            "rating": f.get("rating", 0), "order": f.get("order", 0)})
    new_options = []
    for opt in template.get("options", []):
        new_opt = {"id": str(uuid.uuid4()), "name": opt["name"], "assessments": [], "worth_percentage": 0.0}
        if template.get("template_type") == "assessment":
            for asmt in opt.get("assessments", []):
                new_factor_id = factor_id_map.get(asmt["factor_id"], asmt["factor_id"])
                new_opt["assessments"].append({"factor_id": new_factor_id, "percentage": asmt.get("percentage"),
                                               "unit_value": asmt.get("unit_value"), "assessment_mode": asmt.get("assessment_mode")})
            new_opt["worth_percentage"] = opt.get("worth_percentage", 0.0)
        new_options.append(new_opt)
    decision = {
        "id": new_id, "user_id": user["user_id"], "title": data.title,
        "context": template.get("context", ""), "factors": new_factors, "options": new_options,
        "chosen_option_id": None, "decision_case": None, "notes": "", "status": "draft",
        "created_at": now, "updated_at": now,
    }
    await db.decisions.insert_one(decision)
    return {"id": new_id, "message": "Decision created from template"}

@router.delete("/templates/{template_id}")
async def delete_template(template_id: str, user: dict = Depends(get_current_user)):
    result = await db.templates.delete_one({"id": template_id, "created_by": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found or not authorized")
    return {"message": "Template deleted successfully"}

@router.post("/templates/{template_id}/import")
async def import_template(template_id: str, user: dict = Depends(get_current_user)):
    template = await db.templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    user_email = user.get("email", "").lower()
    visibility = template.get("visibility", "private")
    shared_with = [e.lower() for e in template.get("shared_with", [])]
    if template["created_by"] == user["user_id"]:
        raise HTTPException(status_code=400, detail="This is already your template")
    if visibility == "private":
        raise HTTPException(status_code=403, detail="This template is private")
    if visibility == "shared" and user_email not in shared_with:
        raise HTTPException(status_code=403, detail="This template is not shared with you")
    new_template_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    imported = {
        "id": new_template_id, "name": f"{template['name']} (imported)",
        "template_type": template.get("template_type", "options"), "visibility": "private",
        "shared_with": [], "created_by": user["user_id"],
        "created_by_name": user.get("name", "Unknown"), "created_by_email": user.get("email", ""),
        "source_decision_title": template.get("source_decision_title", ""),
        "imported_from": template.get("created_by_name", "Unknown"),
        "context": template.get("context", ""), "factors": template.get("factors", []),
        "options": template.get("options", []), "created_at": now,
    }
    await db.templates.insert_one(imported)
    return {"id": new_template_id, "message": "Template imported to your collection"}

@router.put("/templates/{template_id}")
async def update_template(template_id: str, data: SaveTemplateRequest, user: dict = Depends(get_current_user)):
    template = await db.templates.find_one({"id": template_id, "created_by": user["user_id"]}, {"_id": 0})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found or not authorized")
    update_fields = {"name": data.name, "visibility": data.visibility,
                     "shared_with": [e.strip().lower() for e in data.shared_with if e.strip()]}
    await db.templates.update_one({"id": template_id}, {"$set": update_fields})
    return {"message": "Template updated successfully"}


# ========================
# ADMIN ROUTES
# ========================

@router.post("/admin/setup")
async def admin_setup(user: dict = Depends(get_current_user)):
    # SECURITY: Only the designated root super-admin email may ever claim
    # super_admin via setup. This blocks self-elevation by any other user.
    email = (user.get("email") or "").strip().lower()
    if email != ROOT_SUPER_ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Only the root super-admin may perform setup")
    existing_super = await db.users.find_one({"role": "super_admin"}, {"_id": 0})
    if existing_super and (existing_super.get("email") or "").strip().lower() != ROOT_SUPER_ADMIN_EMAIL:
        raise HTTPException(status_code=400, detail="Super Admin already exists")
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"role": "super_admin"}})
    return {"message": "You are now Super Admin", "role": "super_admin"}

@router.post("/admin/promote")
async def promote_user(data: PromoteUserRequest, user: dict = Depends(require_root_super_admin)):
    promoter_role = get_user_role(user)
    promoter_level = get_role_level(promoter_role)
    target_role = data.role
    target_level = get_role_level(target_role)
    if target_role not in ("admin", "co_admin"):
        raise HTTPException(status_code=400, detail="Can only promote to 'admin' or 'co_admin'")
    if target_role == "co_admin" and promoter_role != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can create Co-Admins")
    if target_role == "admin" and promoter_level < 2:
        raise HTTPException(status_code=403, detail="Only Co-Admin or above can promote to Admin")
    target_user = await db.users.find_one({"email": data.email.lower()}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found with this email")
    current_target_level = get_role_level(get_user_role(target_user))
    if current_target_level >= target_level:
        raise HTTPException(status_code=400, detail=f"User already has role '{get_user_role(target_user)}'")
    await db.users.update_one({"email": data.email.lower()}, {"$set": {"role": target_role}})
    return {"message": f"User {data.email} promoted to {target_role}"}

@router.post("/admin/demote")
async def demote_user(data: DemoteUserRequest, user: dict = Depends(require_root_super_admin)):
    demoter_role = get_user_role(user)
    demoter_level = get_role_level(demoter_role)
    target_user = await db.users.find_one({"email": data.email.lower()}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found with this email")
    target_role = get_user_role(target_user)
    # The root super-admin can never be demoted via API (checked first).
    if (target_user.get("email") or "").strip().lower() == ROOT_SUPER_ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Root super-admin cannot be demoted")
    if target_user["user_id"] == user["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot demote yourself")
    if target_role == "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin cannot be demoted")
    if target_role == "co_admin" and demoter_role != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can demote Co-Admins")
    if target_role == "admin" and demoter_level < 2:
        raise HTTPException(status_code=403, detail="Only Co-Admin or above can demote Admins")
    await db.users.update_one({"email": data.email.lower()}, {"$set": {"role": "user"}})
    return {"message": f"User {data.email} demoted to regular user"}

@router.get("/admin/users")
async def get_admin_users(user: dict = Depends(require_admin)):
    admin_users = await db.users.find({"role": {"$in": ["super_admin", "co_admin", "admin"]}}, {"_id": 0, "password_hash": 0}).to_list(100)
    return admin_users

@router.post("/admin/templates/{template_id}/approve")
async def approve_admin_template(template_id: str, user: dict = Depends(require_admin)):
    template = await db.templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.get("visibility") != "public":
        raise HTTPException(status_code=400, detail="Only public templates can be authorized")
    await db.templates.update_one({"id": template_id}, {"$set": {
        "authorized": True, "authorized_by": user["user_id"],
        "authorized_by_name": user.get("name", "Unknown"), "authorized_at": datetime.now(timezone.utc),
    }})
    return {"message": "Template authorized successfully"}

@router.post("/admin/templates/{template_id}/revoke")
async def revoke_admin_template(template_id: str, user: dict = Depends(require_admin)):
    template = await db.templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.templates.update_one({"id": template_id}, {"$set": {
        "authorized": False, "authorized_by": None, "authorized_by_name": None, "authorized_at": None,
    }})
    return {"message": "Template authorization revoked"}


# ========================
# TEST123 ROUTES
# ========================

@router.post("/test123", response_model=dict)
async def create_test123(test_data: Test123Create, user: dict = Depends(get_current_user)):
    session = Test123Session(user_id=user["user_id"], situation=test_data.situation)
    await db.test123_sessions.insert_one(session.dict())
    return {"id": session.id, "message": "Test123 session created"}

@router.get("/test123", response_model=List[dict])
async def get_test123_sessions(user: dict = Depends(get_current_user)):
    sessions = await db.test123_sessions.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return sessions

@router.get("/test123/{session_id}")
async def get_test123_session(session_id: str, user: dict = Depends(get_current_user)):
    session = await db.test123_sessions.find_one({"id": session_id, "user_id": user["user_id"]}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.put("/test123/{session_id}")
async def update_test123_session(session_id: str, update_data: Test123Update, user: dict = Depends(get_current_user)):
    existing = await db.test123_sessions.find_one({"id": session_id, "user_id": user["user_id"]}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Session not found")
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    update_dict["updated_at"] = datetime.now(timezone.utc)
    await db.test123_sessions.update_one({"id": session_id}, {"$set": update_dict})
    return {"message": "Session updated successfully"}


@router.delete("/test123/{session_id}")
async def delete_test123_session(session_id: str, user: dict = Depends(get_current_user)):
    """Delete a Test123 quick-decision session owned by the caller."""
    res = await db.test123_sessions.delete_one(
        {"id": session_id, "user_id": user["user_id"]}
    )
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True, "session_id": session_id, "message": "Session deleted."}


# ========================
# MODE ASSESSMENT ROUTES
# ========================

@router.get("/assessment/questions")
async def get_assessment_questions():
    return {"questions": ASSESSMENT_QUESTIONS}

@router.post("/assessment", response_model=dict)
async def submit_assessment(assessment: ModeAssessmentCreate, user: dict = Depends(get_current_user)):
    answers = assessment.answers
    mode_scores = {"emotional": 0.0, "logical": 0.0, "intuitive": 0.0, "awareness": 0.0}
    mode_counts = {"emotional": 0, "logical": 0, "intuitive": 0, "awareness": 0}
    for question in ASSESSMENT_QUESTIONS:
        if question["id"] in answers:
            mode = question["mode"]
            mode_scores[mode] += answers[question["id"]]
            mode_counts[mode] += 1
    for mode in mode_scores:
        if mode_counts[mode] > 0:
            mode_scores[mode] = round(mode_scores[mode] / mode_counts[mode], 2)
    dominant_mode = max(mode_scores, key=mode_scores.get)
    result = ModeAssessmentResult(user_id=user["user_id"], answers=answers, dominant_mode=dominant_mode, mode_scores=mode_scores)
    await db.assessments.insert_one(result.dict())
    return {"id": result.id, "dominant_mode": dominant_mode, "mode_scores": mode_scores}

@router.get("/assessment/history")
async def get_assessment_history(user: dict = Depends(get_current_user)):
    assessments = await db.assessments.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(10)
    return assessments


# ========================
# JOURNAL ROUTES
# ========================

@router.post("/journal", response_model=dict)
async def create_journal_entry(entry: JournalEntryCreate, user: dict = Depends(get_current_user)):
    if entry.linked_module and entry.linked_module not in VALID_LINKED_MODULES:
        raise HTTPException(status_code=400, detail=f"Invalid linked_module. Must be one of: {VALID_LINKED_MODULES}")
    if entry.entry_type and entry.entry_type not in VALID_ENTRY_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid entry_type. Must be one of: {VALID_ENTRY_TYPES}")
    linked_title = entry.linked_title
    if entry.linked_module and entry.linked_id and not linked_title:
        collection_map = {
            "decision": ("decisions", "title"), "solution_finder": ("solution_finders", "title"),
            "solution_matrix": ("solution_matrices", "smart_goal"), "gem": ("gem_goals", "title"),
            "ctt": ("ctt_tasks", "task"), "lifestyle": ("lifestyle_routines", "name"),
        }
        if entry.linked_module in collection_map:
            coll, field = collection_map[entry.linked_module]
            doc = await db[coll].find_one({"id": entry.linked_id}, {field: 1})
            linked_title = doc.get(field) if doc else None
    journal_entry = JournalEntry(
        user_id=user["user_id"], decision_title=entry.decision_title,
        decision_description=entry.decision_description, linked_module=entry.linked_module,
        linked_id=entry.linked_id, linked_title=linked_title or entry.linked_title,
        entry_type=entry.entry_type, decision_date=entry.decision_date or datetime.now(timezone.utc)
    )
    await db.journal.insert_one(journal_entry.dict())
    return {"id": journal_entry.id, "message": "Journal entry created"}

@router.get("/journal", response_model=List[dict])
async def get_journal_entries(user: dict = Depends(get_current_user),
                              linked_module: Optional[str] = None, linked_id: Optional[str] = None,
                              entry_type: Optional[str] = None):
    query = {"user_id": user["user_id"]}
    if linked_module:
        query["linked_module"] = linked_module
    if linked_id:
        query["linked_id"] = linked_id
    if entry_type:
        query["entry_type"] = entry_type
    entries = await db.journal.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return entries

@router.get("/journal/reminders", response_model=List[dict])
async def get_journal_reminders(user: dict = Depends(get_current_user)):
    now = datetime.now(timezone.utc)
    decisions = await db.decisions.find({
        "user_id": user["user_id"],
        "implementation_review_date": {"$lte": now, "$ne": None},
        "decision_type": {"$in": ["problem", "need"]},
    }, {"_id": 0}).sort("implementation_review_date", 1).to_list(50)
    reminders = []
    for dec in decisions:
        existing_journal = await db.journal.find_one({"user_id": user["user_id"], "linked_module": "decision", "linked_id": dec["id"]})
        if not existing_journal:
            priority_label = "P0" if dec.get("decision_type") == "problem" else "P1"
            reminders.append({
                "decision_id": dec["id"], "title": dec.get("title", ""),
                "decision_type": dec.get("decision_type", ""), "life_area": dec.get("life_area", ""),
                "priority_label": priority_label,
                "implementation_review_date": dec.get("implementation_review_date"),
                "status": dec.get("status", ""), "created_at": dec.get("created_at"),
            })
    return reminders

@router.get("/journal/linkable-items", response_model=dict)
async def get_linkable_items(user: dict = Depends(get_current_user)):
    user_id = user["user_id"]
    decisions = await db.decisions.find({"user_id": user_id}, {"_id": 0, "id": 1, "title": 1, "decision_type": 1, "life_area": 1, "status": 1}).sort("created_at", -1).to_list(50)
    solution_finders = await db.solution_finders.find({"user_id": user_id}, {"_id": 0, "id": 1, "title": 1}).sort("created_at", -1).to_list(50)
    solution_matrices = await db.solution_matrices.find({"user_id": user_id}, {"_id": 0, "id": 1, "smart_goal": 1, "area_of_life": 1}).sort("created_at", -1).to_list(50)
    gem_goals = await db.gem_goals.find({"user_id": user_id}, {"_id": 0, "id": 1, "title": 1, "goal_type": 1, "life_area": 1}).sort("created_at", -1).to_list(50)
    ctt_tasks = await db.ctt_tasks.find({"user_id": user_id}, {"_id": 0, "id": 1, "task": 1, "life_area": 1, "status": 1}).sort("created_at", -1).to_list(50)
    lifestyle_routines = await db.lifestyle_routines.find({"user_id": user_id}, {"_id": 0, "id": 1, "name": 1, "life_area": 1, "frequency": 1}).sort("created_at", -1).to_list(50)
    return {
        "decision": [{"id": d["id"], "title": d.get("title", ""), "extra": d.get("decision_type", "")} for d in decisions],
        "solution_finder": [{"id": d["id"], "title": d.get("title", ""), "extra": ""} for d in solution_finders],
        "solution_matrix": [{"id": d["id"], "title": d.get("smart_goal", ""), "extra": d.get("area_of_life", "")} for d in solution_matrices],
        "gem": [{"id": d["id"], "title": d.get("title", ""), "extra": d.get("goal_type", "")} for d in gem_goals],
        "ctt": [{"id": d["id"], "title": d.get("task", ""), "extra": d.get("status", "")} for d in ctt_tasks],
        "lifestyle": [{"id": d["id"], "title": d.get("name", ""), "extra": d.get("frequency", "")} for d in lifestyle_routines],
    }

@router.get("/journal/{entry_id}")
async def get_journal_entry(entry_id: str, user: dict = Depends(get_current_user)):
    entry = await db.journal.find_one({"id": entry_id, "user_id": user["user_id"]}, {"_id": 0})
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry

@router.put("/journal/{entry_id}")
async def update_journal_entry(entry_id: str, update_data: JournalEntryUpdate, user: dict = Depends(get_current_user)):
    existing = await db.journal.find_one({"id": entry_id, "user_id": user["user_id"]}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Entry not found")
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
    update_dict["updated_at"] = datetime.now(timezone.utc)
    await db.journal.update_one({"id": entry_id}, {"$set": update_dict})
    return {"message": "Entry updated successfully"}

@router.delete("/journal/{entry_id}")
async def delete_journal_entry(entry_id: str, user: dict = Depends(get_current_user)):
    result = await db.journal.delete_one({"id": entry_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"message": "Entry deleted successfully"}


# ========================
# DASHBOARD STATS
# ========================

@router.get("/stats")
async def get_user_stats(user: dict = Depends(get_current_user)):
    user_id = user["user_id"]
    total_decisions = await db.decisions.count_documents({"user_id": user_id})
    completed_decisions = await db.decisions.count_documents({"user_id": user_id, "status": "completed"})
    total_test123 = await db.test123_sessions.count_documents({"user_id": user_id})
    total_journal = await db.journal.count_documents({"user_id": user_id})
    completed_journal = await db.journal.count_documents({"user_id": user_id, "status": "completed"})
    latest_assessment = await db.assessments.find_one({"user_id": user_id}, {"_id": 0}, sort=[("created_at", -1)])
    return {
        "decisions": {"total": total_decisions, "completed": completed_decisions},
        "test123": {"total": total_test123},
        "journal": {"total": total_journal, "completed": completed_journal},
        "latest_assessment": latest_assessment,
    }


# ========================
# FOLDERS
# ========================

@router.get("/folders")
async def get_folders():
    return DECISION_FOLDERS


# ========================
# STEP SHARING
# ========================

@router.post("/decisions/{decision_id}/share-step")
async def share_step(decision_id: str, data: ShareStepRequest, user: dict = Depends(get_current_user)):
    decision = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    recipients = []
    for email in data.recipient_emails:
        recipient_user = await db.users.find_one({"email": email}, {"_id": 0})
        if recipient_user:
            recipients.append({"user_id": recipient_user["user_id"], "email": email,
                               "name": recipient_user.get("name", email), "status": "pending", "contribution": None})
    if not recipients:
        raise HTTPException(status_code=400, detail="No valid recipients found")
    share_doc = {
        "id": str(uuid.uuid4()), "decision_id": decision_id, "owner_id": user["user_id"],
        "owner_name": user.get("name", user["email"]), "step_number": data.step_number,
        "merge_mode": data.merge_mode, "custom_weights": data.custom_weights or {},
        "message": data.message, "recipients": recipients,
        "decision_title": decision.get("title", ""), "decision_context": decision.get("context", ""),
        "step_data": {"factors": decision.get("factors", []),
                      "options": [{"id": o["id"], "name": o["name"]} for o in decision.get("options", [])]},
        "status": "active", "created_at": datetime.now(timezone.utc), "merged_at": None,
    }
    await db.shared_steps.insert_one(share_doc)
    STEP_NAMES = {1: 'Context & Options', 2: 'List Factors', 3: 'Classify Factors', 4: 'Prioritize Factors',
                  5: 'Calculate Ratings', 6: 'Define Options', 7: 'Assess & Calculate', 8: 'Case-1 Results',
                  9: 'MPPS Analysis', 10: 'Final Decision'}
    step_name = STEP_NAMES.get(data.step_number, f'Step {data.step_number}')
    sender_name = user.get("name", user["email"])
    sender_email = user.get("email", "")
    decision_title = decision.get("title", "a decision")
    for r in recipients:
        await create_notification(r["user_id"], "share_invite", f"Step {data.step_number}: {step_name}",
            f'{sender_name} ({sender_email}) shared Step {data.step_number} "{step_name}" of "{decision_title}" with you',
            {"share_id": share_doc["id"], "decision_id": decision_id, "step_number": data.step_number,
             "step_name": step_name, "sender_name": sender_name, "sender_email": sender_email, "decision_title": decision_title})
    return {"id": share_doc["id"], "message": f"Step {data.step_number} shared with {len(recipients)} users"}

@router.get("/shared-steps/received")
async def get_received_shared_steps(user: dict = Depends(get_current_user)):
    shares = await db.shared_steps.find({"recipients.user_id": user["user_id"], "status": "active"}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return shares

@router.get("/shared-steps/sent")
async def get_sent_shared_steps(user: dict = Depends(get_current_user)):
    shares = await db.shared_steps.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return shares

@router.get("/shared-steps/{share_id}")
async def get_shared_step(share_id: str, user: dict = Depends(get_current_user)):
    share = await db.shared_steps.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Shared step not found")
    is_owner = share["owner_id"] == user["user_id"]
    is_recipient = any(r["user_id"] == user["user_id"] for r in share.get("recipients", []))
    if not is_owner and not is_recipient:
        raise HTTPException(status_code=403, detail="Access denied")
    return share

@router.post("/shared-steps/{share_id}/contribute")
async def contribute_to_shared_step(share_id: str, data: ContributeStepRequest, user: dict = Depends(get_current_user)):
    share = await db.shared_steps.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Shared step not found")
    is_recipient = any(r["user_id"] == user["user_id"] for r in share.get("recipients", []))
    if not is_recipient:
        raise HTTPException(status_code=403, detail="You are not a recipient of this share")
    contribution = {"factors": data.factors, "options": data.options, "assessments": data.assessments,
                    "note": data.note, "submitted_at": datetime.now(timezone.utc).isoformat()}
    await db.shared_steps.update_one({"id": share_id, "recipients.user_id": user["user_id"]},
        {"$set": {"recipients.$.status": "contributed", "recipients.$.contribution": contribution}})
    contributor_name = user.get("name", user.get("email", "Someone"))
    await create_notification(share["owner_id"], "share_contributed", "New Contribution",
        f'{contributor_name} contributed to Step {share.get("step_number", "?")} of "{share.get("decision_title", "your decision")}"',
        {"share_id": share_id, "decision_id": share.get("decision_id")})
    return {"message": "Contribution submitted successfully"}

@router.post("/shared-steps/{share_id}/merge")
async def merge_shared_step(share_id: str, data: MergeStepRequest, user: dict = Depends(get_current_user)):
    share = await db.shared_steps.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Shared step not found")
    if share["owner_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Only the owner can merge contributions")
    decision = await db.decisions.find_one({"id": share["decision_id"], "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    contributions = []
    for r in share.get("recipients", []):
        if r.get("contribution"):
            contributions.append({"user_id": r["user_id"], "data": r["contribution"]})
    if not contributions:
        raise HTTPException(status_code=400, detail="No contributions to merge")
    merge_mode = data.merge_mode or share.get("merge_mode", "equal")
    total_participants = len(contributions) + 1
    weights = {}
    if merge_mode == "equal":
        w = 1.0 / total_participants
        weights[user["user_id"]] = w
        for c in contributions:
            weights[c["user_id"]] = w
    elif merge_mode == "self_weighted":
        weights[user["user_id"]] = 0.5
        other_weight = 0.5 / len(contributions) if contributions else 0
        for c in contributions:
            weights[c["user_id"]] = other_weight
    elif merge_mode == "custom" and data.custom_weights:
        weights = data.custom_weights
        if user["user_id"] not in weights:
            weights[user["user_id"]] = 0.5
    step_number = share.get("step_number", 7)
    if step_number == 7 and decision.get("options"):
        merged_options = []
        for option in decision["options"]:
            merged_assessments = []
            for factor in decision.get("factors", []):
                owner_assessment = next((a for a in option.get("assessments", []) if a.get("factor_id") == factor["id"]), None)
                owner_pct = owner_assessment.get("percentage", 50) if owner_assessment else 50
                weighted_sum = owner_pct * weights.get(user["user_id"], 0.5)
                for c in contributions:
                    c_assessments = c["data"].get("assessments", {})
                    c_key = f"{option['id']}_{factor['id']}"
                    c_pct = c_assessments.get(c_key, 50)
                    weighted_sum += c_pct * weights.get(c["user_id"], 0)
                merged_assessments.append({"factor_id": factor["id"], "percentage": min(100, max(0, round(weighted_sum))),
                                           "assessment_mode": "custom", "unit_value": ""})
            merged_options.append({**option, "assessments": merged_assessments})
        now = datetime.now(timezone.utc)
        await db.decisions.update_one({"id": share["decision_id"]}, {"$set": {"options": merged_options, "updated_at": now}})
    await db.shared_steps.update_one({"id": share_id}, {"$set": {"status": "merged", "merged_at": datetime.now(timezone.utc)}})
    for r in share.get("recipients", []):
        if r.get("contribution"):
            await create_notification(r["user_id"], "share_merged", "Contributions Merged",
                f'{user.get("name", "Someone")} merged your input for "{share.get("decision_title", "a decision")}"',
                {"share_id": share_id, "decision_id": share["decision_id"]})
    return {"message": "Contributions merged successfully", "weights": weights}


# ========================
# MPPS ACTION PLAN DOWNLOADS
# ========================

@router.get("/decisions/{decision_id}/mpps-action-plan")
async def download_mpps_action_plan(decision_id: str, user: dict = Depends(get_current_user)):
    """Download MPPS action plan as CSV"""
    decision = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    improvements = decision.get("mpps_improvements", [])
    factors = decision.get("factors", [])
    options = decision.get("options", [])
    mpps_option_id = decision.get("mpps_option_id")
    mpps_timeframe = decision.get("mpps_timeframe", "Not specified")
    target_option = next((o for o in options if o.get("id") == mpps_option_id), options[0] if options else None)
    option_name = target_option.get("name", "Unknown") if target_option else "Unknown"
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["MPPS Action Plan"])
    writer.writerow(["Decision", decision.get("title", "")])
    writer.writerow(["Context", decision.get("context", "")])
    writer.writerow(["Option", option_name])
    writer.writerow(["Timeframe", mpps_timeframe])
    writer.writerow(["Projected Worth", f"{decision.get('mpps_projected_worth', 0)}%"])
    writer.writerow([])
    writer.writerow(["Factor", "Category", "Rating", "Current %", "Projected %", "Delta %",
                     "Target Value", "Target Unit", "Improvement Plan", "TEPFI Elements", "Solution Layer",
                     "Assignee Name", "Assignee Email", "Assignee Mobile", "Task", "Deadline"])
    for imp in improvements:
        factor = next((f for f in factors if f.get("id") == imp.get("factor_id")), {})
        tepfi = ", ".join(imp.get("tepfi_elements", []))
        layer = imp.get("tepfi_layer", "")
        action_items = imp.get("action_items", [])
        base_row = [
            factor.get("name", ""), factor.get("category", ""), factor.get("rating", ""),
            imp.get("original_percentage", ""), imp.get("projected_percentage", ""), imp.get("delta_percentage", ""),
            imp.get("expected_value", ""), imp.get("expected_unit", ""), imp.get("improvement_plan", ""), tepfi, layer,
        ]
        if action_items:
            for ai in action_items:
                writer.writerow(base_row + [ai.get("assignee_name", ""), ai.get("assignee_email", ""),
                                            ai.get("assignee_mobile", ""), ai.get("task", ""), ai.get("deadline", "")])
        else:
            writer.writerow(base_row + ["", "", "", "", ""])
    csv_content = output.getvalue()
    return StreamingResponse(io.BytesIO(csv_content.encode()), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="MPPS_Action_Plan_{decision_id[:8]}.csv"'})

@router.get("/decisions/{decision_id}/mpps-action-plan-pdf")
async def download_mpps_action_plan_pdf(decision_id: str, user: dict = Depends(get_current_user)):
    """Download MPPS action plan as PDF"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.units import mm
    decision = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    improvements = decision.get("mpps_improvements", [])
    factors = decision.get("factors", [])
    options = decision.get("options", [])
    mpps_option_id = decision.get("mpps_option_id")
    mpps_timeframe = decision.get("mpps_timeframe", "Not specified")
    target_option = next((o for o in options if o.get("id") == mpps_option_id), options[0] if options else None)
    option_name = target_option.get("name", "Unknown") if target_option else "Unknown"
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm, leftMargin=12*mm, rightMargin=12*mm)
    styles = getSampleStyleSheet()
    story = []
    title_style = ParagraphStyle('Title2', parent=styles['Title'], fontSize=16, spaceAfter=6)
    story.append(Paragraph("MPPS Action Plan", title_style))
    story.append(Spacer(1, 4*mm))
    summary_data = [
        ["Decision", decision.get("title", "")], ["Context", decision.get("context", "")],
        ["Option", option_name], ["Timeframe", mpps_timeframe],
        ["Projected Worth", f"{decision.get('mpps_projected_worth', 0)}%"],
    ]
    summary_table = Table(summary_data, colWidths=[35*mm, 140*mm])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 6*mm))
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=7, leading=9)
    header_style = ParagraphStyle('Header', parent=styles['Normal'], fontSize=7, leading=9, fontName='Helvetica-Bold', textColor=colors.white)
    for imp in improvements:
        factor = next((f for f in factors if f.get("id") == imp.get("factor_id")), {})
        tepfi = ", ".join(imp.get("tepfi_elements", []))
        layer = imp.get("tepfi_layer", "")
        action_items = imp.get("action_items", [])
        factor_title = ParagraphStyle('FTitle', parent=styles['Heading3'], fontSize=11, spaceAfter=2, spaceBefore=4)
        orig = imp.get("original_percentage", "--")
        proj = imp.get("projected_percentage", "--")
        delta = imp.get("delta_percentage", "--")
        story.append(Paragraph(f"{factor.get('name', '')} — {factor.get('category', '')} (Rating: {factor.get('rating', '')})", factor_title))
        info_data = [
            [Paragraph("<b>Current %</b>", cell_style), Paragraph(f"{orig}%", cell_style),
             Paragraph("<b>Projected %</b>", cell_style), Paragraph(f"{proj}%", cell_style),
             Paragraph("<b>Delta</b>", cell_style), Paragraph(f"+{delta}%" if delta and str(delta) != '--' else str(delta), cell_style)],
            [Paragraph("<b>Target Value</b>", cell_style), Paragraph(str(imp.get("expected_value", "")), cell_style),
             Paragraph("<b>Unit</b>", cell_style), Paragraph(str(imp.get("expected_unit", "")), cell_style),
             Paragraph("<b>TEPFI</b>", cell_style), Paragraph(tepfi, cell_style)],
            [Paragraph("<b>Layer</b>", cell_style), Paragraph(layer, cell_style),
             Paragraph("<b>Plan</b>", cell_style), Paragraph(str(imp.get("improvement_plan", "")), cell_style), "", ""],
        ]
        info_table = Table(info_data, colWidths=[22*mm, 28*mm, 22*mm, 28*mm, 22*mm, 53*mm])
        info_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('FONTSIZE', (0, 0), (-1, -1), 7), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3), ('TOPPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(info_table)
        if action_items:
            story.append(Spacer(1, 2*mm))
            ai_header = [Paragraph("Who", header_style), Paragraph("Email", header_style),
                         Paragraph("Mobile", header_style), Paragraph("Task", header_style), Paragraph("By When", header_style)]
            ai_data = [ai_header]
            for ai in action_items:
                ai_data.append([
                    Paragraph(ai.get("assignee_name", ""), cell_style), Paragraph(ai.get("assignee_email", ""), cell_style),
                    Paragraph(ai.get("assignee_mobile", ""), cell_style), Paragraph(ai.get("task", ""), cell_style),
                    Paragraph(ai.get("deadline", ""), cell_style),
                ])
            ai_table = Table(ai_data, colWidths=[30*mm, 38*mm, 28*mm, 50*mm, 29*mm])
            ai_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6366F1')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey), ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('BOTTOMPADDING', (0, 0), (-1, -1), 3), ('TOPPADDING', (0, 0), (-1, -1), 3),
            ]))
            story.append(ai_table)
        story.append(Spacer(1, 4*mm))
    doc.build(story)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="MPPS_Action_Plan_{decision_id[:8]}.pdf"'})
