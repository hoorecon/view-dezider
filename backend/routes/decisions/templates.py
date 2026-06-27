"""Decision template routes — save-as-template, list, use, import, update, delete."""

import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from core.auth import get_current_user
from models.decisions_models import SaveTemplateRequest, UseTemplateRequest
from .services import consume_entitlement

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Decisions"])


@router.post("/decisions/{decision_id}/save-as-template")
async def save_as_template(decision_id: str, data: SaveTemplateRequest, user: dict = Depends(get_current_user)):
    original = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not original:
        raise HTTPException(status_code=404, detail="Decision not found")

    # Phase-2 gating: PUBLIC templates can only be created from a Completed (100%)
    # flow. Private / Shared remain allowed at any step. Uses the SAME unified
    # status model as the Solution Box (/solution-box) so UI and API agree.
    if (data.visibility or "private") == "public":
        from routes.solution_box import _progress_decider
        if _progress_decider(original).get("status") != "completed":
            raise HTTPException(
                status_code=400,
                detail="Public templates can only be created from a Completed (100%) flow. Save it as Private or Shared instead, or finish the assessment first.",
            )

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
        # Base = "factors only" depth: no classification (category) and no
        # prioritization (rating) so a Copy-Factors template carries Step-2 data
        # only and lands the user back on Step 2.
        factors.append({"id": str(uuid.uuid4()), "name": f["name"], "order": f.get("order", 0),
                        "category": "", "rating": 0})
    if level in ("classification", "prioritization", "options", "assessment"):
        for i, f in enumerate(orig_factors):
            if i < len(factors):
                factors[i]["category"] = f.get("category", "primary")
    if level in ("prioritization", "options", "assessment"):
        for i, f in enumerate(orig_factors):
            if i < len(factors):
                factors[i]["rating"] = f.get("rating", 0)
                if f.get("gap_multiplier") is not None:
                    factors[i]["gap_multiplier"] = f.get("gap_multiplier")

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
    await consume_entitlement(user["user_id"], new_id, context="template-use")
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
