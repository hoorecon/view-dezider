"""User-app Quick Links config (admin-editable). Max 3 tiles surface on the
guest/logged-in home 'Quick Links' section of jelcos.ai. Independent from
the admin dashboard pins added in v3.148.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from core.auth import require_super_admin
from core.database import db

router = APIRouter(tags=["user-home-quicklinks"])

_DOC_ID = "user_home_shared_v1"

# Menu of tiles an admin can pick from. `key` matches the frontend tile
# taxonomy so the home screen can look up icon/color if desired.
AVAILABLE_TILES: List[Dict[str, Any]] = [
    {"key": "decision_style", "label": "Know Your Decision Style",
     "subtitle": "Discover your innate style", "icon": "sparkles", "color": "#7C3AED",
     "href": "/quiz"},
    {"key": "decider_store", "label": "The Decider Store",
     "subtitle": "Templates & apps", "icon": "storefront", "color": "#EC4899",
     "href": "/decider-store"},
    {"key": "eft_tapping", "label": "EFT Tapping",
     "subtitle": "Stress relief", "icon": "hand-right", "color": "#F97316",
     "href": "/tools/eft"},
    {"key": "todays_plan", "label": "Today's Plan",
     "subtitle": "Actions + routines", "icon": "calendar", "color": "#0EA5E9",
     "href": "/(tabs)/index"},
    {"key": "mydezider", "label": "MyDezider",
     "subtitle": "10-step canonical", "icon": "compass", "color": "#8B5CF6",
     "href": "/prr/new"},
    {"key": "pros_cons", "label": "Pros & Cons",
     "subtitle": "Two-column starter", "icon": "swap-horizontal", "color": "#16A34A",
     "href": "/tools/pros-cons"},
    {"key": "instant_dezider", "label": "Instant Dezider",
     "subtitle": "Instant decision", "icon": "flash", "color": "#DC2626",
     "href": "/tools/instant"},
    {"key": "solution_finder", "label": "Solution Finder",
     "subtitle": "AI-scored ranking", "icon": "search", "color": "#0891B2",
     "href": "/tools/solution-finder"},
    {"key": "gem_pm", "label": "Emotional Gatekeeper",
     "subtitle": "Break loops & traps", "icon": "heart", "color": "#F59E0B",
     "href": "/tools/gem-pm"},
    {"key": "cld", "label": "CLD Viewer",
     "subtitle": "Causal loop diagrams", "icon": "git-network", "color": "#4F46E5",
     "href": "/tools/cld"},
    {"key": "goal_setter", "label": "Goal Setter",
     "subtitle": "Set outcomes", "icon": "trophy", "color": "#059669",
     "href": "/tools/goal-setter"},
    {"key": "lifestyle", "label": "Lifestyle Routines",
     "subtitle": "Daily rituals", "icon": "sunny", "color": "#B45309",
     "href": "/tools/lifestyle"},
]

_DEFAULT_KEYS: List[str] = ["decision_style", "decider_store", "eft_tapping"]
MAX_TILES = 3


def _tiles_by_keys(keys: List[str]) -> List[Dict[str, Any]]:
    lut = {t["key"]: t for t in AVAILABLE_TILES}
    return [lut[k] for k in keys if k in lut]


async def _read_keys() -> List[str]:
    doc = await db.user_home_quicklinks.find_one({"_id": _DOC_ID}, {"_id": 0, "pinned_keys": 1})
    if not doc:
        await db.user_home_quicklinks.update_one(
            {"_id": _DOC_ID},
            {"$set": {"pinned_keys": _DEFAULT_KEYS}},
            upsert=True,
        )
        return list(_DEFAULT_KEYS)
    return list(doc.get("pinned_keys") or _DEFAULT_KEYS)


@router.get("/home/quicklinks")
async def public_get_quicklinks() -> Dict[str, Any]:
    keys = await _read_keys()
    return {"tiles": _tiles_by_keys(keys)}


@router.get("/admin/user-quicklinks")
async def admin_get_quicklinks(user: dict = Depends(require_super_admin)) -> Dict[str, Any]:
    keys = await _read_keys()
    return {
        "pinned_keys": keys,
        "pinned_tiles": _tiles_by_keys(keys),
        "available": AVAILABLE_TILES,
        "max": MAX_TILES,
    }


@router.put("/admin/user-quicklinks")
async def admin_put_quicklinks(body: Dict[str, Any],
                               user: dict = Depends(require_super_admin)) -> Dict[str, Any]:
    incoming = body.get("pinned_keys") or []
    if not isinstance(incoming, list):
        return {"error": "pinned_keys must be a list"}
    valid_keys = {t["key"] for t in AVAILABLE_TILES}
    seen: set = set()
    clean: List[str] = []
    for k in incoming:
        if isinstance(k, str) and k in valid_keys and k not in seen:
            seen.add(k)
            clean.append(k)
            if len(clean) >= MAX_TILES:
                break
    await db.user_home_quicklinks.update_one(
        {"_id": _DOC_ID},
        {"$set": {"pinned_keys": clean}},
        upsert=True,
    )
    return {"pinned_keys": clean, "pinned_tiles": _tiles_by_keys(clean)}
