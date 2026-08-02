"""Short URLs & share links.

Public: GET /api/short/{slug} → returns {target_url, title, share_message}.
Admin CRUD + auto-seed from decision_templates & decider store apps.

Each row: {slug, target_href, title, share_message, kind: 'template'|'app'|'custom', target_id?, active}
"""
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from core.auth import require_super_admin
from core.database import db

router = APIRouter(tags=["short-urls"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(text: str, max_len: int = 32) -> str:
    """URL-safe slug: lowercase, alphanumerics + dashes."""
    text = (text or "").strip()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)[:max_len].strip("-")
    return text or "item"


async def _uniquify(base: str) -> str:
    """Return a slug that doesn't collide with existing short_urls rows."""
    candidate = base
    i = 2
    while await db.short_urls.find_one({"slug": candidate}, {"_id": 1}):
        candidate = f"{base}-{i}"
        i += 1
        if i > 999:
            candidate = f"{base}-{_now_iso()[-6:]}"
            break
    return candidate


# ─────────────────── Public ───────────────────

@router.get("/short/{slug}")
async def resolve_short_url(slug: str) -> Dict[str, Any]:
    row = await db.short_urls.find_one({"slug": slug, "active": True}, {"_id": 0})
    if not row:
        raise HTTPException(404, "Short URL not found or inactive.")
    return row


# ─────────────────── Admin ───────────────────

@router.get("/admin/short-urls")
async def list_short_urls(user: dict = Depends(require_super_admin)) -> Dict[str, Any]:
    rows = await db.short_urls.find({}, {"_id": 0}).sort("updated_at", -1).to_list(500)
    return {"count": len(rows), "items": rows}


@router.post("/admin/short-urls")
async def create_short_url(body: Dict[str, Any], user: dict = Depends(require_super_admin)) -> Dict[str, Any]:
    slug = _slugify(body.get("slug") or body.get("title") or "")
    if not slug:
        raise HTTPException(400, "slug or title required")
    if await db.short_urls.find_one({"slug": slug}, {"_id": 1}):
        raise HTTPException(409, f"Slug '{slug}' already exists.")
    row = {
        "slug": slug,
        "title": (body.get("title") or slug).strip(),
        "target_href": (body.get("target_href") or "").strip(),
        "share_message": (body.get("share_message") or "").strip(),
        "kind": body.get("kind") or "custom",
        "target_id": body.get("target_id") or None,
        "active": bool(body.get("active", True)),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    if not row["target_href"]:
        raise HTTPException(400, "target_href required")
    await db.short_urls.insert_one(dict(row))
    return row


@router.put("/admin/short-urls/{slug}")
async def update_short_url(slug: str, body: Dict[str, Any],
                           user: dict = Depends(require_super_admin)) -> Dict[str, Any]:
    row = await db.short_urls.find_one({"slug": slug}, {"_id": 0})
    if not row:
        raise HTTPException(404, "not found")
    updates: Dict[str, Any] = {}
    for k in ("title", "target_href", "share_message", "kind"):
        if k in body:
            updates[k] = (body[k] or "").strip() if isinstance(body[k], str) else body[k]
    if "active" in body:
        updates["active"] = bool(body["active"])
    updates["updated_at"] = _now_iso()
    await db.short_urls.update_one({"slug": slug}, {"$set": updates})
    return await db.short_urls.find_one({"slug": slug}, {"_id": 0})


@router.delete("/admin/short-urls/{slug}")
async def delete_short_url(slug: str, user: dict = Depends(require_super_admin)) -> Dict[str, Any]:
    r = await db.short_urls.delete_one({"slug": slug})
    return {"deleted": r.deleted_count}


@router.post("/admin/short-urls/seed")
async def seed_short_urls(body: Optional[Dict[str, Any]] = None,
                          user: dict = Depends(require_super_admin)) -> Dict[str, Any]:
    """Auto-generate short URLs for every decision template + store app that
    doesn't already have one. Idempotent — re-runs safely.
    """
    inserted_tpl = 0
    inserted_app = 0
    existing_by_target = {}
    async for r in db.short_urls.find({"kind": {"$in": ["template", "app"]}},
                                       {"_id": 0, "kind": 1, "target_id": 1, "slug": 1}):
        existing_by_target[(r["kind"], r.get("target_id"))] = r["slug"]

    async for t in db.decision_templates.find({}, {"_id": 0, "id": 1, "name": 1}):
        tid = t.get("id") or ""
        if not tid or ("template", tid) in existing_by_target:
            continue
        slug = await _uniquify(_slugify(t.get("name") or f"template-{tid[:6]}"))
        await db.short_urls.insert_one({
            "slug": slug,
            "title": t.get("name") or "Decision template",
            # Templates live at /decider-store/{template_id} — that's the public
            # detail-and-clone screen (frontend/app/decider-store/[id].tsx).
            "target_href": f"/decider-store/{tid}",
            "share_message": f"Try this decision template on JELCOS AI: {t.get('name','')}",
            "kind": "template",
            "target_id": tid,
            "active": True,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        })
        inserted_tpl += 1

    async for a in db.decider_store_templates.find({}, {"_id": 0, "id": 1, "name": 1, "slug": 1}):
        aid = a.get("id") or ""
        if not aid or ("app", aid) in existing_by_target:
            continue
        base = a.get("slug") or a.get("name") or f"app-{aid[:6]}"
        slug = await _uniquify(_slugify(base))
        await db.short_urls.insert_one({
            "slug": slug,
            "title": a.get("name") or "The Decider Store app",
            "target_href": f"/decider-store/{a.get('slug') or aid}",
            "share_message": f"Check out this app on The Decider Store: {a.get('name','')}",
            "kind": "app",
            "target_id": aid,
            "active": True,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        })
        inserted_app += 1

    return {"inserted_templates": inserted_tpl, "inserted_apps": inserted_app}


@router.post("/admin/short-urls/repair")
async def repair_short_urls(body: Optional[Dict[str, Any]] = None,
                            user: dict = Depends(require_super_admin)) -> Dict[str, Any]:
    """Rewrite bad `target_href` values that previous seed runs saved with the
    wrong URL prefix. Historically templates were seeded to
    `/decision-templates/{id}` (route that doesn't exist) — this migrates them
    to `/decider-store/{id}` (the real detail screen). Idempotent.
    """
    fixed_tpl = 0
    fixed_app = 0
    async for r in db.short_urls.find(
        {"kind": "template", "target_href": {"$regex": "^/decision-templates/"}},
        {"_id": 0, "slug": 1, "target_id": 1},
    ):
        new_href = f"/decider-store/{r.get('target_id') or ''}"
        await db.short_urls.update_one(
            {"slug": r["slug"]},
            {"$set": {"target_href": new_href, "updated_at": _now_iso()}},
        )
        fixed_tpl += 1

    # Also normalise store apps to /decider-store/{target_id}
    async for r in db.short_urls.find(
        {"kind": "app", "target_href": {"$not": {"$regex": "^/decider-store/"}}},
        {"_id": 0, "slug": 1, "target_id": 1},
    ):
        new_href = f"/decider-store/{r.get('target_id') or ''}"
        await db.short_urls.update_one(
            {"slug": r["slug"]},
            {"$set": {"target_href": new_href, "updated_at": _now_iso()}},
        )
        fixed_app += 1

    return {"fixed_templates": fixed_tpl, "fixed_apps": fixed_app}


async def repair_short_urls_on_boot() -> Dict[str, int]:
    """Called on backend startup — rewrites any lingering broken short-URL
    targets so users never land on 'Unmatched Route'. Silent, idempotent."""
    try:
        fixed_tpl = fixed_app = 0
        async for r in db.short_urls.find(
            {"kind": "template", "target_href": {"$regex": "^/decision-templates/"}},
            {"_id": 0, "slug": 1, "target_id": 1},
        ):
            await db.short_urls.update_one(
                {"slug": r["slug"]},
                {"$set": {"target_href": f"/decider-store/{r.get('target_id') or ''}",
                          "updated_at": _now_iso()}},
            )
            fixed_tpl += 1
        async for r in db.short_urls.find(
            {"kind": "app", "target_href": {"$not": {"$regex": "^/decider-store/"}}},
            {"_id": 0, "slug": 1, "target_id": 1},
        ):
            await db.short_urls.update_one(
                {"slug": r["slug"]},
                {"$set": {"target_href": f"/decider-store/{r.get('target_id') or ''}",
                          "updated_at": _now_iso()}},
            )
            fixed_app += 1
        return {"fixed_templates": fixed_tpl, "fixed_apps": fixed_app}
    except Exception:
        return {"fixed_templates": 0, "fixed_apps": 0}
