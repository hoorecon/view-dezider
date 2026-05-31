"""Solution Finder and Solution Matrix tool endpoints."""
import uuid
from typing import Dict
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
    """Create a new Simple Solution Finder entry.

    Schema v2 (June 2026 overhaul) — structured 4-level tree:
      concerns: [{concern_id, text, is_primary, order}]            ← Q1 (a)+(b) via ⭐
      root_causes: [{rca_id, concern_id, text, order}]              ← Q2 (NEW)
      solutions: [{sol_id, rca_id, text, capabilities, resources}]  ← Q3
      risks: [{risk_id, sol_id, name, impact_pct, probability_pct,  ← Q4a
              risk_index_pct, order}]
      mitigations: [{mit_id, risk_id, text, order}]                 ← Q4b (1..many)
      contingencies: [{cont_id, risk_id, text, order}]              ← Q4c (1..many)
      action_plan_items: [{ap_id, source_type, source_id, text,     ← Q5
              who, by_when, status, pushed_to_action_center,
              action_id, pushed_to_ctt, pushed_to_lifestyle}]
    Legacy v1 free-text fields are still accepted on the body but new entries
    should use the v2 arrays. Use POST /solution-finders/{id}/push-action-plan
    to fan out Q5 items into the universal Action Center.
    """
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
        # --- v2 structured tree ---
        "concerns": body.get("concerns", []),
        "root_causes": body.get("root_causes", []),
        "solutions": body.get("solutions", []),
        "risks": body.get("risks", []),
        "mitigations": body.get("mitigations", []),
        "contingencies": body.get("contingencies", []),
        "action_plan_items": body.get("action_plan_items", []),
        "schema_version": body.get("schema_version", 2),
        # --- legacy v1 (kept for backward read compat) ---
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
        # legacy v1
        "q1_all_concerns", "q2_primary_concerns",
        "q3_capabilities", "q3_resources", "q3_solutions",
        "external_help_aspect", "external_help_level", "external_help_from",
        "q4_negative_consequences", "q4_mitigation_plans", "q4_contingency_plans",
        "action_items", "status",
        # v2 structured tree (June 2026 overhaul)
        "concerns", "root_causes", "solutions", "risks",
        "mitigations", "contingencies", "action_plan_items",
        "schema_version",
        # timing + linking (Enhancements #4 & #5 — still supported)
        "deadline_date", "impact_horizon_value", "impact_horizon_unit",
        "linked_from_decision_id", "linked_from_module",
        "linked_from_option_label", "linked_from_score_pct",
        "allow_single_option",
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


@router.post("/solution-finders/{entry_id}/push-action-plan")
async def push_action_plan_to_action_center(
    entry_id: str, request: Request, user: dict = Depends(get_current_user)
):
    """Q5 → Action Center fan-out (per-item granularity).

    Accepts either of two body shapes:
      A)  { "items": [{"ap_id": "...", "push_ctt": bool, "push_lifestyle": bool}, ...] }
          → preferred. Per-item CTT / Lifestyle decisions.
      B)  { "ap_ids": ["..."], "push_to_ctt": bool, "push_to_lifestyle": bool }
          → legacy global-flag shape (kept for backward compat).

    Pushes any action_plan_item that's not yet pushed to the universal
    `action_items` collection (source_module='solution_finder'), and only
    fans the item into CTT / Lifestyle when its own per-item flag is true.
    Idempotent: items with pushed_to_action_center=true are skipped.
    """
    body = await request.json()
    items_arr = body.get("items")
    if items_arr:
        item_flags = {it["ap_id"]: (bool(it.get("push_ctt")), bool(it.get("push_lifestyle")))
                      for it in items_arr if it.get("ap_id")}
        requested_ids = set(item_flags.keys())
        legacy_ctt = False
        legacy_life = False
    else:
        requested_ids = set(body.get("ap_ids") or [])
        legacy_ctt = bool(body.get("push_to_ctt", False))
        legacy_life = bool(body.get("push_to_lifestyle", False))
        item_flags = {ap_id: (legacy_ctt, legacy_life) for ap_id in requested_ids}

    entry = await db.solution_finders.find_one(
        {"entry_id": entry_id, "user_id": user["user_id"]}
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    plan = list(entry.get("action_plan_items") or [])
    now = datetime.now(timezone.utc).isoformat()
    pushed = 0
    ctt_count = 0
    life_count = 0

    for it in plan:
        ap_id = it.get("ap_id")
        if requested_ids and ap_id not in requested_ids:
            continue
        if it.get("pushed_to_action_center"):
            continue
        want_ctt, want_life = item_flags.get(ap_id, (False, False))
        action_id = str(uuid.uuid4())
        await db.action_items.insert_one({
            "action_id": action_id,
            "user_id": user["user_id"],
            "title": it.get("text") or "Solution Finder action",
            "description": it.get("description", ""),
            "who": it.get("who", ""),
            "by_when": it.get("by_when"),
            "status": it.get("status") or "pending",
            "source_module": "solution_finder",
            "source_id": entry_id,
            "source_label": entry.get("smart_goal") or "Simple Solution Finder",
            "source_sub_type": it.get("source_type"),  # solution|mitigation|contingency
            "source_sub_id": it.get("source_id"),
            "recurrence_type": "one_time",
            "created_at": now,
            "updated_at": now,
        })
        it["pushed_to_action_center"] = True
        it["action_id"] = action_id
        pushed += 1

        if want_ctt and not it.get("pushed_to_ctt"):
            await db.ctt_tasks.insert_one({
                "task_id": str(uuid.uuid4()),
                "user_id": user["user_id"],
                "task": it.get("text") or "Solution Finder action",
                "deadline": it.get("by_when"),
                "status": "pending",
                "source_module": "solution_finder",
                "source_id": entry_id,
                "linked_action_id": action_id,
                "created_at": now, "updated_at": now,
            })
            it["pushed_to_ctt"] = True
            ctt_count += 1

        if want_life and not it.get("pushed_to_lifestyle"):
            await db.lifestyle_routines.insert_one({
                "routine_id": str(uuid.uuid4()),
                "user_id": user["user_id"],
                "name": it.get("text") or "Solution Finder routine",
                "description": f"From Simple Solution Finder: {entry.get('smart_goal','')}",
                "source_module": "solution_finder",
                "source_id": entry_id,
                "linked_action_id": action_id,
                "created_at": now, "updated_at": now,
            })
            it["pushed_to_lifestyle"] = True
            life_count += 1

    await db.solution_finders.update_one(
        {"entry_id": entry_id, "user_id": user["user_id"]},
        {"$set": {"action_plan_items": plan, "updated_at": now}},
    )
    return {
        "pushed_to_action_center": pushed,
        "pushed_to_ctt": ctt_count,
        "pushed_to_lifestyle": life_count,
        "action_plan_items": plan,
    }


@router.post("/solution-matrices/{entry_id}/push-action-plan")
async def push_matrix_action_plan(
    entry_id: str, request: Request, user: dict = Depends(get_current_user)
):
    """ASM Action Plan → Action Center / CTT / Lifestyle fan-out.

    The ASM Action Plan is the aggregate of every non-empty matrix cell entry
    (15 or 60 cells). The frontend sends the selected aggregated items:

      { "items": [ { "text": "<Layer·OrgType·Field: detail>",
                     "push_ctt": bool, "push_lifestyle": bool }, ... ] }

    Each selected item is written to the universal action_items collection
    (source_module='solution_matrix'), and optionally fanned into CTT and/or
    Lifestyle when its per-item flag is set.
    """
    body = await request.json()
    items_arr = body.get("items") or []
    entry = await db.solution_matrices.find_one(
        {"entry_id": entry_id, "user_id": user["user_id"]}
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    now = datetime.now(timezone.utc).isoformat()
    label = entry.get("smart_goal") or "Advanced Solution Matrix"
    pushed = ctt_count = life_count = 0

    for it in items_arr:
        text = (it.get("text") or "").strip()
        if not text:
            continue
        want_ctt = bool(it.get("push_ctt"))
        want_life = bool(it.get("push_lifestyle"))
        action_id = str(uuid.uuid4())
        await db.action_items.insert_one({
            "action_id": action_id,
            "user_id": user["user_id"],
            "title": text,
            "description": it.get("description", ""),
            "who": it.get("who", ""),
            "by_when": it.get("by_when"),
            "status": it.get("status") or "pending",
            "source_module": "solution_matrix",
            "source_id": entry_id,
            "source_label": label,
            "recurrence_type": "one_time",
            "created_at": now,
            "updated_at": now,
        })
        pushed += 1

        if want_ctt:
            await db.ctt_tasks.insert_one({
                "task_id": str(uuid.uuid4()),
                "user_id": user["user_id"],
                "task": text,
                "deadline": it.get("by_when"),
                "status": "pending",
                "source_module": "solution_matrix",
                "source_id": entry_id,
                "linked_action_id": action_id,
                "created_at": now, "updated_at": now,
            })
            ctt_count += 1

        if want_life:
            await db.lifestyle_routines.insert_one({
                "routine_id": str(uuid.uuid4()),
                "user_id": user["user_id"],
                "name": text,
                "description": f"From Advanced Solution Matrix: {label}",
                "source_module": "solution_matrix",
                "source_id": entry_id,
                "linked_action_id": action_id,
                "created_at": now, "updated_at": now,
            })
            life_count += 1

    return {
        "pushed_to_action_center": pushed,
        "pushed_to_ctt": ctt_count,
        "pushed_to_lifestyle": life_count,
    }


@router.post("/solution-finders/_admin/wipe-legacy")
async def wipe_legacy_solution_finders(user: dict = Depends(get_current_user)):
    """One-time admin op to delete all existing solution_finder entries for
    this user before the v2 schema rolls out. Per user direction during the
    SSF schema overhaul ('Just delete existing items as nothing serious is
    there now')."""
    r = await db.solution_finders.delete_many({"user_id": user["user_id"]})
    return {"deleted": r.deleted_count}


@router.get("/solution-finders/{entry_id}/asm-links")
async def get_asm_deep_dive_counts(
    entry_id: str, user: dict = Depends(get_current_user)
):
    """Reverse hook for the SSF UI.

    Returns the count of Advanced Solution Matrix entries that were spawned
    from each Q3/Q4b/Q4c row of this Simple Solution Finder, so the SSF UI
    can render a small "📊 N ASM deep-dive(s)" badge next to each row.
    Response shape: { "<source_id>": <count>, ... }
    """
    entry = await db.solution_finders.find_one(
        {"entry_id": entry_id, "user_id": user["user_id"]}, {"_id": 0, "entry_id": 1},
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    cursor = db.solution_matrices.find(
        {"user_id": user["user_id"], "linked_from_sf_entry_id": entry_id},
        {"_id": 0, "linked_from_sf_source_id": 1},
    )
    counts: Dict[str, int] = {}
    async for d in cursor:
        sid = d.get("linked_from_sf_source_id")
        if sid:
            counts[sid] = counts.get(sid, 0) + 1
    return counts


@router.get("/solution-finders/{entry_id}/asm-entries")
async def list_linked_asm_entries(
    entry_id: str, user: dict = Depends(get_current_user)
):
    """Phase-2 "From ASM" picker source.

    Returns the Advanced Solution Matrix analyses linked to this Solution
    Finder, each with a Category & Source-wise summary plus its entry_id so the
    UI can deep-link back to the ASM Solution Matrix tab (/tools/solution-matrix?id=<entry_id>).
    The SF UI filters this list by (source, source_id) for the level/row tapped.
    Response: [{ entry_id, title, source, source_id, categories: [...], sources: [...], updated_at }]
    """
    entry = await db.solution_finders.find_one(
        {"entry_id": entry_id, "user_id": user["user_id"]}, {"_id": 0, "entry_id": 1},
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    cursor = db.solution_matrices.find(
        {"user_id": user["user_id"], "linked_from_sf_entry_id": entry_id},
        {"_id": 0},
    )
    out = []
    async for d in cursor:
        cats = [k for k, v in (d.get("solution_category") or {}).items() if v]
        srcs = [k for k, v in (d.get("solution_sources") or {}).items() if (v or "").strip()]
        out.append({
            "entry_id": d.get("entry_id"),
            "title": d.get("smart_goal") or "Untitled ASM",
            "source": d.get("linked_from_sf_source"),
            "source_id": d.get("linked_from_sf_source_id"),
            "categories": cats,
            "sources": srcs,
            "updated_at": d.get("updated_at"),
        })
    out.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return out


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
        # SSF deep-link linkage — set when ASM was launched from a "Send to ASM"
        # pill in Simple Solution Finder (Q3/Q4b/Q4c). Lets ASM render a back
        # banner and lets future views reverse-link from SF → ASM.
        "linked_from_sf_entry_id": body.get("linked_from_sf_entry_id"),
        "linked_from_sf_source": body.get("linked_from_sf_source"),
        "linked_from_sf_source_id": body.get("linked_from_sf_source_id"),
        "linked_from_sf_label": body.get("linked_from_sf_label"),
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
        # SSF deep-link linkage (set when ASM opened from SF "Send to ASM" pill)
        "linked_from_sf_entry_id", "linked_from_sf_source",
        "linked_from_sf_source_id", "linked_from_sf_label",
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
