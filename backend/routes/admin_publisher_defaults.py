"""
Admin-configurable defaults for Publisher Contact info attached to
Admin-authored (jAI Verified) templates and Decider Apps.

Publishers can override these on a per-item basis via the standard
`lead_gen` block, but any admin item that publishes without an explicit
`lead_gen` will inherit these defaults automatically.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.database import db
from core.auth import require_super_admin

router = APIRouter(tags=["admin-publisher-defaults"])

CFG_DOC_ID = "admin_publisher_defaults"

_DEFAULT: Dict[str, Any] = {
    "id": CFG_DOC_ID,
    "contact_name": "JELCOS AI Editorial",
    "organization": "JELCOS AI",
    "designation": "Editorial Team",
    "email": "hello@jelcos.ai",
    "whatsapp": "",
    "mobile": "",
    "redirect_url": "https://jelcos.ai",
}


class PublisherDefaults(BaseModel):
    contact_name: Optional[str] = None
    organization: Optional[str] = None
    designation: Optional[str] = None
    email: Optional[str] = None
    whatsapp: Optional[str] = None
    mobile: Optional[str] = None
    redirect_url: Optional[str] = None


@router.get("/admin/publisher-defaults")
async def get_defaults(_: dict = Depends(require_super_admin)) -> Dict[str, Any]:
    doc = await db.decider_config.find_one({"id": CFG_DOC_ID}, {"_id": 0})
    if not doc:
        await db.decider_config.insert_one(dict(_DEFAULT))
        return dict(_DEFAULT)
    return doc


@router.patch("/admin/publisher-defaults")
async def patch_defaults(body: PublisherDefaults, _: dict = Depends(require_super_admin)) -> Dict[str, Any]:
    patch = {k: v for k, v in body.dict().items() if v is not None}
    if patch:
        await db.decider_config.update_one({"id": CFG_DOC_ID}, {"$set": patch}, upsert=True)
    return await get_defaults(_=_)


async def apply_defaults_to_admin_items() -> Dict[str, int]:
    """Backfill lead_gen on every admin-authored public template/app that
    has no `lead_gen` yet, using the current defaults. Idempotent — items
    already carrying a `lead_gen.contact_name` are left untouched.
    """
    cfg = await db.decider_config.find_one({"id": CFG_DOC_ID}, {"_id": 0}) or dict(_DEFAULT)
    defaults = {k: v for k, v in cfg.items() if k in _DEFAULT and k != "id" and v}
    if not defaults:
        return {"templates_updated": 0, "store_updated": 0}
    q = {
        "$and": [
            {"$or": [{"is_official": True}, {"is_approved": True}, {"created_by": {"$in": [None, "", "system"]}}]},
            {"$or": [{"lead_gen": {"$exists": False}}, {"lead_gen": None}, {"lead_gen": {}}, {"lead_gen.contact_name": {"$in": ["", None]}}]},
        ]
    }
    r1 = await db.templates.update_many(q, {"$set": {"lead_gen": defaults}})
    r2 = await db.decider_store_templates.update_many(q, {"$set": {"lead_gen": defaults}})
    return {"templates_updated": r1.modified_count, "store_updated": r2.modified_count}
