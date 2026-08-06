"""
Moderation for user-published public content — Decision Templates and
Decider Apps.

Every doc in `templates` or `decider_store_templates` carries a
`moderation_status` field with one of:
  • `unverified`   — default for user-published items. Shown in Decider
                     Store with a small "Unverified" badge if the admin
                     config allows it (default: ON).
  • `jai_verified` — Editorial approval by an admin. Green badge.
  • `disapproved`  — Blocked by admin with a remark. HIDDEN from
                     `/decider-store`. Publisher sees a red "Disapproved"
                     badge with the admin's remark on their Mine tab and
                     can resubmit with an author remark.

Also fixes the "user-published public templates are not shown in
/decider-store" bug: the storefront query previously required
`is_approved=True` which was only set by seed / authorize flows. We now
show ANY public template whose `moderation_status != 'disapproved'`,
gated by the admin config `show_unverified_in_store` (default True).

Endpoints (all admin-only unless marked):
  GET   /admin/moderation/store            — pending queue with filters
  POST  /admin/moderation/{item_id}/approve
  POST  /admin/moderation/{item_id}/disapprove   {reason: str}
  POST  /admin/moderation/{item_id}/reset        (back to unverified)
  GET   /admin/moderation/config
  PATCH /admin/moderation/config           {show_unverified_in_store: bool}
  POST  /templates/{template_id}/resubmit  {publisher_remark: str}  (owner)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.database import db
from core.auth import get_current_user, require_super_admin

router = APIRouter(tags=["moderation"])

CFG_DOC_ID = "decider_moderation"
DEFAULT_CFG = {
    "id": CFG_DOC_ID,
    "show_unverified_in_store": True,
    "show_jai_verified_in_store": True,
    # Disapproved items are ALWAYS hidden — no config toggle.
}


class DisapproveBody(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)


class ResubmitBody(BaseModel):
    publisher_remark: str = Field(..., min_length=1, max_length=1000)


class ConfigPatch(BaseModel):
    show_unverified_in_store: Optional[bool] = None
    show_jai_verified_in_store: Optional[bool] = None


async def get_moderation_config() -> Dict[str, Any]:
    """Read admin config; upserts the defaults on first call."""
    doc = await db.decider_config.find_one({"id": CFG_DOC_ID}, {"_id": 0})
    if not doc:
        await db.decider_config.insert_one(dict(DEFAULT_CFG))
        return dict(DEFAULT_CFG)
    return doc


async def _apply_moderation(item_id: str, status: str, *, admin: Dict[str, Any],
                            reason: Optional[str] = None) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    patch: Dict[str, Any] = {
        "moderation_status": status,
        "moderation_updated_at": now,
        "moderation_updated_by": admin.get("user_id"),
        "moderation_updated_by_name": admin.get("name") or admin.get("email"),
    }
    if reason is not None:
        patch["moderation_remark"] = reason
    # Update both the source-of-truth `templates` row and the Decider Store
    # mirror `decider_store_templates` (id is the same across both).
    r1 = await db.templates.update_one({"id": item_id}, {"$set": patch})
    r2 = await db.decider_store_templates.update_one(
        {"template_id": item_id}, {"$set": patch}
    )
    if r1.matched_count == 0 and r2.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"item_id": item_id, "status": status, "remark": reason}


@router.get("/admin/moderation/store")
async def moderation_queue(
    status: Optional[str] = None,
    kind: Optional[str] = None,
    _: dict = Depends(require_super_admin),
) -> Dict[str, Any]:
    """Return items in the moderation queue.

    Filter by `status` (unverified | jai_verified | disapproved) and/or
    `kind` (template | app). Defaults to everything published publicly.
    """
    q: Dict[str, Any] = {}
    if status:
        q["moderation_status"] = status
    if kind:
        q["kind"] = kind
    # Only public items ever need moderation.
    q["$or"] = [{"is_public": True}, {"visibility": "public"}, {"pricing_type": {"$exists": True}}]
    items = await db.decider_store_templates.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    counts = {
        "unverified": await db.decider_store_templates.count_documents({"moderation_status": "unverified"}),
        "jai_verified": await db.decider_store_templates.count_documents({"moderation_status": "jai_verified"}),
        "disapproved": await db.decider_store_templates.count_documents({"moderation_status": "disapproved"}),
        "unset": await db.decider_store_templates.count_documents({"moderation_status": {"$exists": False}}),
    }
    return {"items": items, "counts": counts}


@router.post("/admin/moderation/{item_id}/approve")
async def moderation_approve(item_id: str, admin: dict = Depends(require_super_admin)):
    return await _apply_moderation(item_id, "jai_verified", admin=admin, reason="")


@router.post("/admin/moderation/{item_id}/disapprove")
async def moderation_disapprove(item_id: str, body: DisapproveBody, admin: dict = Depends(require_super_admin)):
    return await _apply_moderation(item_id, "disapproved", admin=admin, reason=body.reason.strip())


@router.post("/admin/moderation/{item_id}/reset")
async def moderation_reset(item_id: str, admin: dict = Depends(require_super_admin)):
    return await _apply_moderation(item_id, "unverified", admin=admin, reason="")


@router.get("/admin/moderation/config")
async def get_config(_: dict = Depends(require_super_admin)) -> Dict[str, Any]:
    return await get_moderation_config()


@router.patch("/admin/moderation/config")
async def patch_config(body: ConfigPatch, _: dict = Depends(require_super_admin)) -> Dict[str, Any]:
    patch = {k: v for k, v in body.dict().items() if v is not None}
    if not patch:
        return await get_moderation_config()
    await db.decider_config.update_one(
        {"id": CFG_DOC_ID}, {"$set": patch}, upsert=True,
    )
    return await get_moderation_config()


@router.post("/templates/{template_id}/resubmit")
async def resubmit_template(template_id: str, body: ResubmitBody, user: dict = Depends(get_current_user)):
    """Publisher's own resubmission — flips status back to `unverified` and
    stashes the publisher's justification remark for the admin to review.
    """
    t = await db.templates.find_one({"id": template_id, "created_by": user["user_id"]}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Template not found or not yours")
    if t.get("moderation_status") != "disapproved":
        raise HTTPException(status_code=400, detail="Only disapproved items can be resubmitted")
    now = datetime.now(timezone.utc)
    patch = {
        "moderation_status": "unverified",
        "moderation_publisher_remark": body.publisher_remark.strip(),
        "moderation_publisher_remark_at": now,
    }
    await db.templates.update_one({"id": template_id}, {"$set": patch})
    await db.decider_store_templates.update_one({"template_id": template_id}, {"$set": patch})
    return {"template_id": template_id, "status": "unverified"}


async def backfill_default_moderation_status() -> Dict[str, int]:
    """One-shot migration: ensure every existing template + store doc has a
    `moderation_status`. Called from `main` at startup so we don't need a
    separate CLI step in dev. Also mirrors PUBLIC templates that were saved
    before the mirror-on-save code path existed — the exact root cause of
    "user-published public templates are missing from /decider-store".
    """
    fixed_t = fixed_s = fixed_mirror = 0
    now = datetime.now(timezone.utc)

    # First — mirror any PUBLIC template that has no `decider_store_templates`
    # row yet. Uses the same helper the save endpoint calls so schema stays
    # in lock-step. Also RE-mirrors existing rows whose factor_count / factors[]
    # is out of sync with the source template (this covers the "0 factors /
    # 0 options showing even though the template has 19" bug on legacy rows
    # that were upserted before the content-embed fix landed).
    try:
        from routes.decisions.templates import _mirror_template_to_store
        async for t in db.templates.find({"visibility": "public"}, {"_id": 0}):
            src_factors = t.get("factors") or []
            src_options = t.get("options") or []
            exists = await db.decider_store_templates.find_one(
                {"template_id": t["id"]},
                {"_id": 0, "factor_count": 1, "option_count": 1, "factors": 1, "options": 1},
            )
            needs_refresh = (
                not exists
                or int(exists.get("factor_count") or 0) != len(src_factors)
                or int(exists.get("option_count") or 0) != len(src_options)
                or len(exists.get("factors") or []) != len(src_factors)
                or len(exists.get("options") or []) != len(src_options)
            )
            if not needs_refresh:
                continue
            try:
                await _mirror_template_to_store(t)
                fixed_mirror += 1
            except Exception:
                pass
    except Exception:
        pass

    # Templates: admin/system-owned or is_official → jai_verified;
    # otherwise unverified (only if visibility=public — private/shared
    # templates have no store presence and don't need a status).
    async for t in db.templates.find({"moderation_status": {"$exists": False}}, {"_id": 0, "id": 1, "created_by": 1, "is_official": 1, "authorized": 1, "visibility": 1}):
        if t.get("visibility") != "public":
            continue
        status = "jai_verified" if (
            t.get("is_official") or t.get("authorized") or t.get("created_by") in (None, "", "system")
        ) else "unverified"
        await db.templates.update_one({"id": t["id"]}, {"$set": {"moderation_status": status, "moderation_updated_at": now}})
        fixed_t += 1

    async for s in db.decider_store_templates.find({"moderation_status": {"$exists": False}}, {"_id": 0, "template_id": 1, "is_official": 1, "is_approved": 1, "publisher_type": 1}):
        status = "jai_verified" if (s.get("is_official") or s.get("is_approved")) else "unverified"
        await db.decider_store_templates.update_one(
            {"template_id": s["template_id"]},
            {"$set": {"moderation_status": status, "moderation_updated_at": now}},
        )
        fixed_s += 1
    return {"templates_updated": fixed_t, "store_updated": fixed_s, "mirrored_missing": fixed_mirror}


async def backfill_default_policies() -> Dict[str, int]:
    """Ensure every existing public template + Decider Store item has a
    `policies` block. Uses standard defaults where missing."""
    default_privacy = (
        "By publishing this template publicly you agree that any lead-generation "
        "contact details you provide (name, email, WhatsApp) may be shown to "
        "interested viewers so they can reach out to you. JELCOS AI does not sell "
        "or share this data with third parties and stores it only for the purpose "
        "of connecting viewers with you."
    )
    default_terms = (
        "This template is offered as a starting point for decision-making. The "
        "publisher is not liable for outcomes of any decision made using this "
        "template. Viewers may clone and modify the template for personal use; "
        "commercial re-distribution requires written permission from the publisher."
    )
    now = datetime.now(timezone.utc).isoformat()
    default = {"privacy_policy": default_privacy, "terms_of_use": default_terms, "agreed_at": now}
    r1 = await db.templates.update_many(
        {"visibility": "public", "$or": [{"policies": {"$exists": False}}, {"policies": None}, {"policies": {}}]},
        {"$set": {"policies": default}},
    )
    r2 = await db.decider_store_templates.update_many(
        {"$or": [{"policies": {"$exists": False}}, {"policies": None}, {"policies": {}}]},
        {"$set": {"policies": default}},
    )
    return {"templates_updated": r1.modified_count, "store_updated": r2.modified_count}
