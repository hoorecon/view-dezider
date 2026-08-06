"""Decision template routes — save-as-template, list, use, import, update, delete."""

import uuid
import logging
from typing import Any, Dict
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from core.auth import get_current_user
from models.decisions_models import SaveTemplateRequest, UseTemplateRequest, TemplateContentUpdate
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
        # Carry the source decision's editorial metadata so downstream store
        # cards (life_area, category, decision_type) render correctly.
        "life_area": original.get("life_area") or original.get("folder") or "",
        "category": original.get("category") or "",
        "decision_type": original.get("decision_type") or "",
        # Public-only publisher metadata & policy consent.
        "lead_gen": (data.lead_gen.dict() if data.lead_gen else None),
        "policies": (data.policies.dict() if data.policies else None),
    }
    await db.templates.insert_one(template)
    # Mirror PUBLIC templates into the Decider Store so they show under the
    # "Decision Templates" section of /decider-store (which reads from
    # `decider_store_templates`, not `templates`).
    if (data.visibility or "private") == "public":
        try:
            await _mirror_template_to_store(template)
        except Exception as e:
            logger.warning("mirror to decider_store_templates failed: %s", str(e)[:160])
    return {"id": template_id, "message": "Template saved successfully"}


async def _mirror_template_to_store(template: dict) -> None:
    """Upsert a public template into `decider_store_templates` so it appears
    under Decider Store → Decision Templates. Publisher type is auto-derived
    from the author's subscription-plan tier."""
    tpl_id = template["id"]
    factors = template.get("factors", []) or []
    options = template.get("options", []) or []
    now = datetime.now(timezone.utc)

    # Publisher type from author's current subscription tier
    publisher_type = "individual"
    try:
        w = await db.credit_wallets.find_one({"user_id": template.get("created_by")},
                                             {"_id": 0, "current_plan": 1})
        p = ((w or {}).get("current_plan") or "").lower()
        if "premium" in p:   publisher_type = "organization"
        elif "pro" in p:     publisher_type = "expert"
    except Exception:
        pass

    await db.decider_store_templates.update_one(
        {"template_id": tpl_id},
        {"$set": {
            "template_id": tpl_id,
            "id": tpl_id,
            "kind": "template",
            "title": template.get("name") or "Decision template",
            "subtitle": template.get("source_decision_title") or "",
            "description": template.get("context") or "",
            "category": template.get("category") or "General",
            "life_area": template.get("life_area") or template.get("category") or "General",
            "applicable_org_types": template.get("applicable_org_types") or [],
            "decision_type": template.get("decision_type") or "General",
            "factor_count": len(factors),
            "option_count": len(options),
            # Embed the actual content arrays so the detail page can render
            # factors + options without an extra fetch, AND so store-side
            # filters that read from `factors[]` (e.g. min_factors range)
            # keep working for user-published templates too.
            "factors": factors,
            "options": options,
            "is_public": True,
            "is_free": True,
            "pricing_type": "free",
            "is_active": True,
            "status": "authorized",
            "publisher_type": publisher_type,
            "creator_name": template.get("created_by_name") or "",
            "created_by": template.get("created_by"),
            "created_by_name": template.get("created_by_name", ""),
            "created_at": template.get("created_at", now),
            "updated_at": now,
            # Attach publisher lead-gen + agreed policies so store viewers can
            # see who to contact + what they're agreeing to when using it.
            "lead_gen": template.get("lead_gen") or {},
            "policies": template.get("policies") or {},
        },
         # New user-published templates default to `unverified` and MUST be
         # moderated before showing a "jAI Verified" badge. Preserve existing
         # status on re-mirror so admin approvals aren't lost.
         "$setOnInsert": {"install_count": 0, "moderation_status": "unverified"}},
        upsert=True,
    )


async def _unmirror_template_from_store(template_id: str) -> None:
    """Remove the Decider Store mirror row when a template is deleted or its
    visibility is downgraded from public."""
    await db.decider_store_templates.delete_one({"template_id": template_id, "kind": "template"})


@router.get("/templates")
async def get_templates(user: dict = Depends(get_current_user)):
    user_email = user.get("email", "").lower()
    user_id = user["user_id"]
    all_templates = await db.templates.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    my_templates, shared_templates, public_templates, authorized_templates = [], [], [], []
    for t in all_templates:
        visibility = t.get("visibility", "private")
        created_by = t.get("created_by", "")
        shared_with = [e.lower() for e in t.get("shared_with", [])]
        is_authorized = t.get("authorized", False) or t.get("is_official", False)

        # Authorized bucket — editorial / admin-published templates.
        if is_authorized and visibility == "public":
            authorized_templates.append(t)

        # Mine — anything I created (regardless of visibility).
        if created_by == user_id:
            my_templates.append(t)

        # Shared — visibility=shared and I'm on the share list.
        if visibility == "shared" and user_email in shared_with:
            shared_templates.append(t)

        # Public — ANY template with visibility=public. This includes:
        #   • my own public templates (so I can verify what others see)
        #   • other users' public templates
        #   • admin / system authorized public templates (10 founder pack etc.)
        # Fixes the "my public template shows under Mine but not under Public"
        # + "10 admin templates in /decider-store missing from Templates→Public"
        # bugs. Deduping happens client-side by template id.
        if visibility == "public":
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
        # Copy the rich Step-2 metadata a template can carry (variable_id,
        # expected_value, unit, operator, factor_type, gap_multiplier). The
        # legacy min-schema is preserved for old templates that don't have
        # these fields.
        new_factors.append({
            "id": new_factor_id,
            "name": f["name"],
            "category": f.get("category", "primary"),
            "rating": f.get("rating", 0),
            "order": f.get("order", 0),
            "variable_id": f.get("variable_id"),
            "expected_value": f.get("expected_value"),
            "unit": f.get("unit"),
            "operator": f.get("operator"),
            "factor_type": f.get("factor_type"),
            "gap_multiplier": f.get("gap_multiplier", 1.0),
        })
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
        # Carry over dependency formulas + equal_weightage from the template.
        "formulas": template.get("formulas", []),
        "equal_weightage": bool(template.get("equal_weightage", False)),
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
    # Also remove the Decider Store mirror if it existed
    try:
        await _unmirror_template_from_store(template_id)
    except Exception as e:
        logger.warning("unmirror failed on delete %s: %s", template_id, str(e)[:160])
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
    # Sync mirror row based on new visibility
    try:
        fresh = await db.templates.find_one({"id": template_id}, {"_id": 0})
        if fresh and data.visibility == "public":
            await _mirror_template_to_store(fresh)
        else:
            await _unmirror_template_from_store(template_id)
    except Exception as e:
        logger.warning("mirror sync on update failed: %s", str(e)[:160])
    return {"message": "Template updated successfully"}


# ────────────────────────────────────────────────────────────────────
# PATCH — edit template content (Steps 1..7) OR just flip visibility.
# Handles issues #6 (Private ↔ Public ↔ Shared toggle) and #7 (edit the
# actual factor / option / classification / prioritization content of a
# saved template) with a single endpoint.
# ────────────────────────────────────────────────────────────────────
@router.patch("/templates/{template_id}")
async def patch_template(template_id: str, data: TemplateContentUpdate, user: dict = Depends(get_current_user)):
    template = await db.templates.find_one({"id": template_id, "created_by": user["user_id"]}, {"_id": 0})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found or not authorized")

    # Downgrading TO public requires the same guard as save-as-template.
    payload = data.dict(exclude_unset=True)
    new_visibility = payload.get("visibility", template.get("visibility", "private"))
    if new_visibility == "public" and template.get("visibility") != "public":
        # Only require lead-gen block if not already present.
        lg = payload.get("lead_gen") or template.get("lead_gen") or {}
        if not (lg.get("contact_name") and lg.get("email") and lg.get("whatsapp")):
            raise HTTPException(
                status_code=400,
                detail="Public templates need contact name, email and WhatsApp in lead_gen block.",
            )

    update_fields: Dict[str, Any] = {}
    for key in ("name", "visibility", "context", "factors", "options", "formulas",
                "equal_weightage", "life_area", "category", "decision_type"):
        if key in payload and payload[key] is not None:
            update_fields[key] = payload[key]
    if "shared_with" in payload and payload["shared_with"] is not None:
        update_fields["shared_with"] = [e.strip().lower() for e in payload["shared_with"] if e.strip()]
    if "lead_gen" in payload and payload["lead_gen"] is not None:
        update_fields["lead_gen"] = payload["lead_gen"]
    if "policies" in payload and payload["policies"] is not None:
        update_fields["policies"] = payload["policies"]
    update_fields["updated_at"] = datetime.now(timezone.utc)

    await db.templates.update_one({"id": template_id}, {"$set": update_fields})

    # Sync the Decider Store mirror row: (a) upsert if now public,
    # (b) drop if no longer public.
    try:
        fresh = await db.templates.find_one({"id": template_id}, {"_id": 0})
        if fresh and fresh.get("visibility") == "public":
            await _mirror_template_to_store(fresh)
        else:
            await _unmirror_template_from_store(template_id)
    except Exception as e:
        logger.warning("mirror sync on patch failed: %s", str(e)[:160])
    return {"message": "Template updated", "updated_fields": list(update_fields.keys())}
