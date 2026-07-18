"""The Decider Store — a public storefront (like App Store / Play Store) for
Admin-Authorized Decision Templates.

• Templates are browsable WITHOUT login (public GET routes).
• Cloning ("Use this template") requires an authenticated user; the clone
  builds a fresh MyDezider decision prefilled at the chosen depth:
    - mode="full"        -> factors + classification (mandatory/optional) +
                            prioritization + options + option-values
    - mode="values_only" -> factors + options + option-values only; the user
                            classifies mandatory/optional and prioritizes.
• Admins author templates by importing an Excel file or a shared Google-Sheet
  (see core.decider_import) and can then fine-tune + Authorize them.

Collection: db.decider_store_templates
"""
from __future__ import annotations

import base64
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
import io

from core.auth import get_current_user
from core.database import db
from core.decider_import import (
    parse_import, gsheet_to_csv_url, build_import_template_xlsx, parse_value_cell,
)

router = APIRouter(prefix="/decider-store", tags=["The Decider Store"])

CLONE_MODES = {"full", "values_only"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_admin(user: dict) -> bool:
    return user.get("role") in ("admin", "super_admin")


def _card(t: Dict[str, Any]) -> Dict[str, Any]:
    """Lightweight card for storefront lists."""
    return {
        "template_id": t.get("template_id"),
        "title": t.get("title"),
        "subtitle": t.get("subtitle"),
        "description": t.get("description"),
        "category": t.get("category"),
        "decision_type": t.get("decision_type"),
        "cover_icon": t.get("cover_icon") or "grid",
        "cover_color": t.get("cover_color") or "#4F46E5",
        "pricing_type": t.get("pricing_type") or "free",
        "price_paise": t.get("price_paise") or 0,
        "currency": t.get("currency") or "INR",
        "allowed_clone_modes": t.get("allowed_clone_modes") or ["full", "values_only"],
        "factor_count": len(t.get("factors") or []),
        "option_count": len(t.get("options") or []),
        "install_count": t.get("install_count") or 0,
        "creator_name": t.get("creator_name") or "Earth Dezider",
        "status": t.get("status"),
    }


# ══════════════════════════════════════════════════════════════════════════
# PUBLIC (no login) — browse the store
# ══════════════════════════════════════════════════════════════════════════
@router.get("")
async def list_store(category: Optional[str] = None, decision_type: Optional[str] = None,
                     q: Optional[str] = None):
    query: Dict[str, Any] = {"status": "authorized", "is_public": True}
    if category:
        query["category"] = category
    if decision_type:
        query["decision_type"] = decision_type
    if q:
        query["title"] = {"$regex": q, "$options": "i"}
    docs = await db.decider_store_templates.find(query).sort("install_count", -1).to_list(200)
    return {"templates": [_card(d) for d in docs]}


@router.get("/meta")
async def store_meta():
    docs = await db.decider_store_templates.find(
        {"status": "authorized", "is_public": True}, {"category": 1, "_id": 0}
    ).to_list(500)
    cats: Dict[str, int] = {}
    for d in docs:
        c = d.get("category") or "General"
        cats[c] = cats.get(c, 0) + 1
    return {"categories": [{"key": k, "count": v} for k, v in sorted(cats.items())],
            "total": len(docs)}


@router.get("/import-template.xlsx")
async def download_import_template(sample: bool = True):
    """Downloadable XLSX authoring template (public so it's easy to grab)."""
    data = build_import_template_xlsx(sample=sample)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="decider_store_import_template.xlsx"'},
    )


# ══════════════════════════════════════════════════════════════════════════
# ADMIN — author / import / authorize
# ══════════════════════════════════════════════════════════════════════════
@router.get("/admin/all")
async def admin_list_all(user: dict = Depends(get_current_user)):
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    docs = await db.decider_store_templates.find({}).sort("created_at", -1).to_list(500)
    for d in docs:
        d.pop("_id", None)
    return {"templates": docs}


@router.post("/import/excel")
async def import_excel(request: Request, user: dict = Depends(get_current_user)):
    """Parse an uploaded XLSX (base64) -> preview {factors, options}. Not saved."""
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    body = await request.json()
    b64 = body.get("file_b64") or ""
    if "," in b64 and b64.strip().startswith("data:"):
        b64 = b64.split(",", 1)[1]
    try:
        data = base64.b64decode(b64)
        parsed = parse_import(data=data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"Could not read the Excel file: {str(e)[:150]}")
    return parsed


@router.post("/import/gsheet")
async def import_gsheet(request: Request, user: dict = Depends(get_current_user)):
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    body = await request.json()
    csv_url = gsheet_to_csv_url(body.get("sheet_url") or "")
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=25) as client:
            resp = await client.get(csv_url)
        if resp.status_code != 200 or "html" in resp.headers.get("content-type", "").lower():
            raise HTTPException(400, "Could not read the sheet as CSV. Make it link-shareable "
                                     "(Anyone with the link) or 'Publish to web'.")
        parsed = parse_import(csv_text=resp.text)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"Failed to fetch/parse the sheet: {str(e)[:150]}")
    return parsed


@router.post("")
async def create_template(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    is_admin = _is_admin(user)
    modes = [m for m in (body.get("allowed_clone_modes") or ["full", "values_only"]) if m in CLONE_MODES]
    pricing = (body.get("pricing_type") or "free").lower()
    if pricing not in ("free", "paid"):
        pricing = "free"
    doc = {
        "template_id": str(uuid.uuid4()),
        "title": (body.get("title") or "Untitled Template").strip(),
        "subtitle": body.get("subtitle") or "",
        "description": body.get("description") or "",
        "category": body.get("category") or "General",
        "decision_type": body.get("decision_type") or "aspiration",
        "cover_icon": body.get("cover_icon") or "grid",
        "cover_color": body.get("cover_color") or "#4F46E5",
        "pricing_type": pricing,
        "price_paise": int(body.get("price_paise") or 0),
        "currency": body.get("currency") or "INR",
        "creator_split_pct": int(body.get("creator_split_pct") or 70),
        "allowed_clone_modes": modes or ["full", "values_only"],
        "auto_push_on_authorize": bool(body.get("auto_push_on_authorize", False)),
        "factors": body.get("factors") or [],
        "options": body.get("options") or [],
        "created_by": user["user_id"],
        "creator_name": user.get("name") or "",
        "source": "admin" if is_admin else "user",
        # Admin-created -> authorized+public immediately; user-created -> pending.
        "status": "authorized" if is_admin else "pending",
        "is_public": bool(is_admin),
        "install_count": 0,
        "created_at": _now(),
        "updated_at": _now(),
        "authorized_at": _now() if is_admin else None,
        "authorized_by": user["user_id"] if is_admin else None,
    }
    await db.decider_store_templates.insert_one(doc)
    return {"template_id": doc["template_id"], "status": doc["status"],
            "is_public": doc["is_public"]}


@router.put("/{template_id}")
async def update_template(template_id: str, request: Request, user: dict = Depends(get_current_user)):
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    body = await request.json()
    allowed = ["title", "subtitle", "description", "category", "decision_type",
               "cover_icon", "cover_color", "pricing_type", "price_paise", "currency",
               "creator_split_pct", "allowed_clone_modes", "factors", "options", "is_public",
               "auto_push_on_authorize"]
    update = {k: body[k] for k in allowed if k in body}
    if "allowed_clone_modes" in update:
        update["allowed_clone_modes"] = [m for m in update["allowed_clone_modes"] if m in CLONE_MODES] or ["full"]
    update["updated_at"] = _now()
    res = await db.decider_store_templates.update_one({"template_id": template_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Template not found")
    return {"message": "updated"}


@router.post("/{template_id}/authorize")
async def authorize_template(template_id: str, user: dict = Depends(get_current_user)):
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    t = await db.decider_store_templates.find_one({"template_id": template_id})
    if not t:
        raise HTTPException(404, "Template not found")
    await db.decider_store_templates.update_one(
        {"template_id": template_id},
        {"$set": {"status": "authorized", "is_public": True,
                  "authorized_at": _now(), "authorized_by": user["user_id"], "updated_at": _now()}},
    )
    pushed = None
    if t.get("auto_push_on_authorize"):
        t["status"] = "authorized"
        pushed = await _push_template_to_stores(t, user)
    return {"message": "authorized", "auto_pushed": pushed}


@router.post("/{template_id}/unpublish")
async def unpublish_template(template_id: str, user: dict = Depends(get_current_user)):
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    await db.decider_store_templates.update_one(
        {"template_id": template_id}, {"$set": {"is_public": False, "updated_at": _now()}})
    return {"message": "unpublished"}


@router.delete("/{template_id}")
async def delete_template(template_id: str, user: dict = Depends(get_current_user)):
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    res = await db.decider_store_templates.delete_one({"template_id": template_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Template not found")
    return {"message": "deleted"}


# ══════════════════════════════════════════════════════════════════════════
# PUBLIC detail (kept AFTER admin routes so /admin, /meta, /import* win)
# ══════════════════════════════════════════════════════════════════════════
@router.get("/{template_id}")
async def get_template(template_id: str):
    t = await db.decider_store_templates.find_one({"template_id": template_id}, {"_id": 0})
    if not t or not (t.get("status") == "authorized" and t.get("is_public")):
        raise HTTPException(404, "Template not found")
    t.pop("created_by", None)
    return t


# ══════════════════════════════════════════════════════════════════════════
# CLONE (login required) -> new MyDezider decision, prefilled
# ══════════════════════════════════════════════════════════════════════════
def _fmt_value_text(vals: List[Dict[str, Any]]) -> str:
    parts = []
    for v in vals:
        pct = v.get("pct")
        parts.append(f"{v.get('value')} ({int(pct)}%)" if pct not in (None, 100, 100.0)
                     else str(v.get("value")))
    return ", ".join(parts)


def _build_decision_from_template(t: Dict[str, Any], mode: str, user: dict) -> Dict[str, Any]:
    full = (mode == "full")
    factors_out: List[Dict[str, Any]] = []
    id_map: Dict[str, str] = {}
    for order, f in enumerate(t.get("factors") or []):
        new_id = str(uuid.uuid4())
        id_map[f.get("id")] = new_id
        factors_out.append({
            "id": new_id,
            "name": f.get("name") or "Factor",
            "order": order,
            # classification + prioritization only carried in FULL mode
            "category": (f.get("category") or "primary") if full else "",
            "rating": (int(f.get("priority") or 0)) if full else 0,
            "data_type": f.get("data_type") or "Text",
            "factor_type": f.get("factor_type") or "qualitative",
            "gap_multiplier": 1.0,
            # store-template metadata (informational; harmless extra fields)
            "possible_values": f.get("possible_values") or [],
            "select_type": f.get("select_type"),
            "ui_object": f.get("ui_object"),
            "has_sub_pct": f.get("has_sub_pct", False),
        })

    options_out: List[Dict[str, Any]] = []
    for opt in t.get("options") or []:
        assessments = []
        for old_fid, vals in (opt.get("values") or {}).items():
            new_fid = id_map.get(old_fid)
            if not new_fid:
                continue
            # option "value" is prefilled as unit_value text; the suitability %
            # is retained as structured metadata (NOT the scoring assessment %,
            # which the user fills during their own assessment step).
            assessments.append({
                "factor_id": new_fid,
                "percentage": None,
                "unit_value": _fmt_value_text(vals),
                "suitability_values": vals,
            })
        options_out.append({
            "id": str(uuid.uuid4()),
            "name": opt.get("name") or "Option",
            "assessments": assessments,
            "worth_percentage": 0.0,
            "source": "store",
            "ai_rationale": opt.get("description") or opt.get("remarks") or "",
        })

    return {
        "id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "title": t.get("title") or "Decision",
        "context": t.get("description") or "",
        "factors": factors_out,
        "options": options_out,
        "chosen_option_id": None,
        "decision_case": None,
        "notes": "",
        "reflection": "",
        "final_notes": "",
        "folder": "",
        "life_area": t.get("category"),
        "decision_type": t.get("decision_type"),
        "rating_gap_multiplier": 1.0,
        "status": "draft",
        "source_template_id": t.get("template_id"),
        "source": "decider_store",
        "clone_mode": mode,
        "created_at": _now(),
        "updated_at": _now(),
    }


@router.post("/{template_id}/clone")
async def clone_template(template_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    mode = (body.get("mode") or "full").lower()
    if mode not in CLONE_MODES:
        mode = "full"
    t = await db.decider_store_templates.find_one({"template_id": template_id}, {"_id": 0})
    if not t or not (t.get("status") == "authorized" and t.get("is_public")):
        raise HTTPException(404, "Template not found")
    if mode not in (t.get("allowed_clone_modes") or ["full", "values_only"]):
        raise HTTPException(400, f"This template does not allow '{mode}' cloning.")

    # Paid templates require entitlement (fulfillment wired in Phase 2).
    if (t.get("pricing_type") == "paid") and (int(t.get("price_paise") or 0) > 0):
        raise HTTPException(
            status_code=402,
            detail={"message": "This is a paid template.",
                    "price_paise": t.get("price_paise"), "currency": t.get("currency") or "INR",
                    "creator_split_pct": t.get("creator_split_pct", 70)},
        )

    decision = _build_decision_from_template(t, mode, user)
    await db.decisions.insert_one(decision)
    await db.decider_store_templates.update_one(
        {"template_id": template_id}, {"$inc": {"install_count": 1}})
    return {"decision_id": decision["id"], "mode": mode,
            "factors": len(decision["factors"]), "options": len(decision["options"])}


# ══════════════════════════════════════════════════════════════════════════
# STORE ⇄ REVIEWNET BRIDGE
# Each unique Option ↔ one Solution-Store solution (its QUANTITATIVE factor
# values) ↔ its ReviewNet baseline (its QUALITATIVE factor values). Linked by
# solution_id stored on the option (non-duplication). Qualitative values are
# stored BOTH as a categorical baseline_profile AND as a 1–5★ admin baseline.
# ══════════════════════════════════════════════════════════════════════════
def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").strip().lower()).strip("_") or "factor"


def _star_from_pct(pct) -> int:
    try:
        return max(1, min(5, round(float(pct) / 20.0)))
    except (TypeError, ValueError):
        return 5


def _best_pct(vals) -> float:
    ps = [v.get("pct", 100) for v in (vals or []) if v.get("pct") is not None]
    return max(ps) if ps else 100.0


async def _push_template_to_stores(t: dict, user: dict) -> dict:
    """Push each option → Solution Store (quant) + ReviewNet baseline (qual)."""
    factors = t.get("factors") or []
    fmap = {f.get("id"): f for f in factors}
    qual_factors = {f.get("id"): f for f in factors if (f.get("factor_type") or "qualitative") != "quantitative"}

    # Ensure a ReviewNet catalog factor exists for every qualitative factor.
    rf_id_for: dict = {}
    for fid, f in qual_factors.items():
        rf_id = f"qf_decider_{_slug(f.get('name'))}"
        rf_id_for[fid] = rf_id
        await db.review_factors.update_one(
            {"factor_id": rf_id},
            {"$set": {"factor_id": rf_id, "name": f.get("name"), "slug": _slug(f.get("name")),
                      "scope_type": "global", "scope_id": None, "is_active": True,
                      "source": "decider_store", "updated_at": _now()},
             "$setOnInsert": {"created_at": _now()}},
            upsert=True,
        )

    options = t.get("options") or []
    solutions_out, reviews_out = 0, 0
    updated_options = []
    for opt in options:
        quant_factors_payload = []
        qual_profile: dict = {}
        factor_ratings: dict = {}
        for fid, vals in (opt.get("values") or {}).items():
            f = fmap.get(fid)
            if not f:
                continue
            text = _fmt_value_text(vals)
            if (f.get("factor_type") or "qualitative") == "quantitative":
                quant_factors_payload.append({
                    "factor_id": fid, "name": f.get("name"), "value": text,
                    "unit": "", "values": vals, "data_type": f.get("data_type") or "Text",
                })
            else:
                qual_profile[f.get("name")] = vals
                factor_ratings[rf_id_for.get(fid, f"qf_decider_{_slug(f.get('name'))}")] = _star_from_pct(_best_pct(vals))

        sol_id = opt.get("linked_solution_id") or str(uuid.uuid4())
        sol_doc = {
            "solution_id": sol_id,
            "type": "STRATEGY",
            "name": opt.get("name") or "Option",
            "description": opt.get("description") or opt.get("remarks") or "",
            "visibility": "PUBLIC",
            "approval_status": "approved",
            "is_authorized": True,
            "status": "active",
            "provider": opt.get("exemplary_companies") or "",
            "tags": [t.get("category")] if t.get("category") else [],
            "quantitative_factors": quant_factors_payload,
            "type_specific": {"affected_components": opt.get("affected_components") or "",
                              "strategy_type": t.get("title") or ""},
            "org_types": [], "decision_types": [t.get("decision_type")] if t.get("decision_type") else [],
            "currency": t.get("currency") or "INR",
            # cross-links (non-duplication + "Open in Decider Store")
            "source": "decider_store",
            "decider_template_id": t.get("template_id"),
            "decider_option_id": opt.get("id"),
            "created_by": user["user_id"],
            "created_by_name": user.get("name") or "",
            "org_id": user.get("org_id"),
            "updated_at": _now(),
        }
        existing = await db.solutions_store.find_one({"solution_id": sol_id}, {"created_at": 1})
        sol_doc["created_at"] = (existing or {}).get("created_at", _now())
        await db.solutions_store.replace_one({"solution_id": sol_id}, sol_doc, upsert=True)
        solutions_out += 1

        opt["linked_solution_id"] = sol_id
        updated_options.append(opt)

        if factor_ratings or qual_profile:
            rv_id = f"rv_baseline_{sol_id}"
            avg = round(sum(factor_ratings.values()) / len(factor_ratings), 2) if factor_ratings else 5.0
            await db.review_net.update_one(
                {"review_id": rv_id},
                {"$set": {
                    "review_id": rv_id, "solution_id": sol_id, "solution_name": opt.get("name"),
                    "reviewer_id": "decider_baseline", "reviewer_name": "Decider Baseline",
                    "reviewer_segment": "authoritative", "reviewer_subsegment": None,
                    "factor_ratings": factor_ratings, "overall_rating": avg,
                    "baseline_profile": qual_profile, "is_baseline": True,
                    "status": "approved", "moderation_action": "AUTO_APPROVE",
                    "source": "decider_store", "source_template_id": t.get("template_id"),
                    "source_option_id": opt.get("id"), "updated_at": _now(),
                }, "$setOnInsert": {"created_at": _now()}},
                upsert=True,
            )
            reviews_out += 1

    await db.decider_store_templates.update_one(
        {"template_id": t.get("template_id")},
        {"$set": {"options": updated_options, "pushed_to_stores_at": _now(), "updated_at": _now()}})
    return {"solutions": solutions_out, "reviews": reviews_out}


@router.post("/{template_id}/push-to-stores")
async def push_to_stores(template_id: str, user: dict = Depends(get_current_user)):
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    t = await db.decider_store_templates.find_one({"template_id": template_id})
    if not t:
        raise HTTPException(404, "Template not found")
    res = await _push_template_to_stores(t, user)
    return {"message": "pushed", **res}


@router.post("/{template_id}/sync-from-stores")
async def sync_from_stores(template_id: str, user: dict = Depends(get_current_user)):
    """Pull latest quant (Solution Store) + qual baseline (ReviewNet) back into
    the template options (reverse of push)."""
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    t = await db.decider_store_templates.find_one({"template_id": template_id}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Template not found")
    factors = t.get("factors") or []
    fid_by_name = {f.get("name"): f.get("id") for f in factors}
    synced = 0
    options = t.get("options") or []
    for opt in options:
        sol_id = opt.get("linked_solution_id")
        if not sol_id:
            continue
        sol = await db.solutions_store.find_one({"solution_id": sol_id}, {"_id": 0})
        if not sol:
            continue
        vals = dict(opt.get("values") or {})
        # quantitative back from solution
        for qf in sol.get("quantitative_factors") or []:
            fid = qf.get("factor_id") or fid_by_name.get(qf.get("name"))
            if not fid:
                continue
            vals[fid] = qf.get("values") or parse_value_cell(qf.get("value"))
        # qualitative back from ReviewNet baseline
        baseline = await db.review_net.find_one(
            {"review_id": f"rv_baseline_{sol_id}"}, {"_id": 0, "baseline_profile": 1})
        for fname, fvals in ((baseline or {}).get("baseline_profile") or {}).items():
            fid = fid_by_name.get(fname)
            if fid:
                vals[fid] = fvals
        opt["values"] = vals
        synced += 1
    await db.decider_store_templates.update_one(
        {"template_id": template_id},
        {"$set": {"options": options, "synced_from_stores_at": _now(), "updated_at": _now()}})
    return {"message": "synced", "options": synced}


@router.post("/from-solutions")
async def create_template_from_solutions(request: Request, user: dict = Depends(get_current_user)):
    """Build a NEW Decider template from a set of Solution-Store solutions
    (their quantitative_factors) + their ReviewNet baselines (qualitative)."""
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    body = await request.json()
    solution_ids = body.get("solution_ids") or []
    if not solution_ids:
        raise HTTPException(400, "solution_ids required")
    sols = await db.solutions_store.find({"solution_id": {"$in": solution_ids}}, {"_id": 0}).to_list(500)
    if not sols:
        raise HTTPException(404, "No matching solutions")

    # Build the factor set: quantitative from solutions, qualitative from baselines.
    factors: list = []
    factor_id_by_name: dict = {}

    def _ensure_factor(name: str, ftype: str) -> str:
        if name in factor_id_by_name:
            return factor_id_by_name[name]
        fid = str(uuid.uuid4())
        factor_id_by_name[name] = fid
        factors.append({"id": fid, "name": name, "order": len(factors),
                        "factor_type": ftype, "data_type": "Number" if ftype == "quantitative" else "Text",
                        "category": "", "priority": 0, "possible_values": [], "has_sub_pct": True})
        return fid

    baselines: dict = {}
    for sol in sols:
        b = await db.review_net.find_one({"review_id": f"rv_baseline_{sol['solution_id']}"}, {"_id": 0})
        if b:
            baselines[sol["solution_id"]] = b
        for qf in sol.get("quantitative_factors") or []:
            if qf.get("name"):
                _ensure_factor(qf["name"], "quantitative")
        for fname in ((b or {}).get("baseline_profile") or {}).keys():
            _ensure_factor(fname, "qualitative")

    options: list = []
    for sol in sols:
        vals: dict = {}
        for qf in sol.get("quantitative_factors") or []:
            if qf.get("name") in factor_id_by_name:
                vals[factor_id_by_name[qf["name"]]] = qf.get("values") or parse_value_cell(qf.get("value"))
        for fname, fvals in (baselines.get(sol["solution_id"], {}).get("baseline_profile") or {}).items():
            if fname in factor_id_by_name:
                vals[factor_id_by_name[fname]] = fvals
        options.append({
            "id": str(uuid.uuid4()), "name": sol.get("name") or "Option",
            "description": sol.get("description") or "",
            "exemplary_companies": sol.get("provider") or "",
            "affected_components": (sol.get("type_specific") or {}).get("affected_components") or "",
            "remarks": "", "product_model": "",
            "values": vals, "linked_solution_id": sol["solution_id"],
        })

    doc = {
        "template_id": str(uuid.uuid4()),
        "title": (body.get("title") or "Template from Solution Store").strip(),
        "subtitle": body.get("subtitle") or "",
        "description": body.get("description") or "",
        "category": body.get("category") or "General",
        "decision_type": body.get("decision_type") or "aspiration",
        "cover_icon": body.get("cover_icon") or "git-compare",
        "cover_color": body.get("cover_color") or "#0369A1",
        "pricing_type": "free", "price_paise": 0, "currency": "INR", "creator_split_pct": 70,
        "allowed_clone_modes": ["full", "values_only"], "auto_push_on_authorize": False,
        "factors": factors, "options": options,
        "created_by": user["user_id"], "creator_name": user.get("name") or "",
        "source": "solution_store", "status": "authorized", "is_public": True,
        "install_count": 0, "created_at": _now(), "updated_at": _now(),
        "authorized_at": _now(), "authorized_by": user["user_id"],
    }
    await db.decider_store_templates.insert_one(doc)
    return {"template_id": doc["template_id"], "factors": len(factors), "options": len(options)}
