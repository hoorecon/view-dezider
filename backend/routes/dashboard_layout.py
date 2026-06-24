"""
Dashboard Layout config — admin-editable section names, order, and tile→section
assignments for the Home dashboard.

- GET  /api/dashboard-layout        → effective layout (any authenticated user)
- PUT  /api/admin/dashboard-layout  → save layout (admin only)
- POST /api/admin/dashboard-layout/reset → restore defaults (admin only)

Visibility is still governed by the ACM (`dash_<id>` / `dash_section_<id>`); this
config only controls structure (order, display name, which tiles sit in which
section). Stored in app_config under key 'dashboard_layout'.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user, get_user_role, ADMIN_ROLES

router = APIRouter(tags=["Dashboard Layout"])

_CFG_KEY = "dashboard_layout"

# Canonical default — must stay in sync with frontend DEFAULT_LAYOUT.
DEFAULT_SECTIONS = [
    {"id": "self_discovery", "emoji": "🌌", "name": "Self Discovery",
     "tiles": ["pna", "gem"]},
    {"id": "decision_kickstarters", "emoji": "🔮", "name": "Decision Kickstarters",
     "tiles": ["instant_dezider", "my_dezider", "pros_cons", "emotional_gatekeeper"]},
    {"id": "problem_solvers", "emoji": "❤️", "name": "Problem Solvers",
     "tiles": ["solution_finder", "conflict_breaker"]},
    {"id": "goals_manifestation", "emoji": "🎯", "name": "Goals & Manifestation",
     "tiles": ["goal_setter", "goal_manifestation"]},
    {"id": "execute_track", "emoji": "✅", "name": "Execute & Track",
     "tiles": ["orgs", "values", "action_tracker", "atex", "ctt", "lifestyle_dezider"]},
    {"id": "reflection_awareness", "emoji": "🪞", "name": "Reflection & Awareness",
     "tiles": ["public_pulse", "outlet_analyzer", "aim_manager", "capabilities_index",
               "lifestyle_designer", "lifestyle_analyzer", "consciousness_diary",
               "unconditional_happiness"]},
    {"id": "collaboration_mgmt", "emoji": "👥", "name": "Collaboration & Management",
     "tiles": ["collaboration_hub", "aala", "time_dezider", "gem_flight"]},
    {"id": "solution_space", "emoji": "🧩", "name": "Solution Space",
     "tiles": ["solution_store", "review_net", "deo", "time_store"]},
    {"id": "more_tools", "emoji": "🧰", "name": "More Tools",
     "tiles": ["inbox", "notifications", "analytics", "contacts", "calendar",
               "ai_assistant", "social_learning", "cld_engine", "subscription"]},
]

# All tile ids known to the dashboard registry (for validation/merge).
KNOWN_TILES = {t for s in DEFAULT_SECTIONS for t in s["tiles"]}


async def _load_layout() -> dict:
    doc = await db.app_config.find_one({"key": _CFG_KEY}, {"_id": 0})
    sections = (doc or {}).get("sections") or DEFAULT_SECTIONS
    tile_titles = (doc or {}).get("tile_titles") or {}
    return {"sections": sections, "tile_titles": tile_titles}


async def _seed_tile_feature_names() -> dict:
    """feature_id → original seed feature_name for the dashboard_tiles module,
    so cleared/blank custom titles can be reverted to their seed defaults."""
    try:
        from data.acm_seed_data import ACM_MODULES
        for m in ACM_MODULES:
            if m.get("module_id") == "dashboard_tiles":
                return {f["feature_id"]: f["feature_name"] for f in (m.get("features") or [])}
    except Exception:
        pass
    return {}


async def _sync_tile_titles_to_acm(tile_titles: dict) -> None:
    """Mirror custom dashboard tile names into the ACM matrix so the
    `dashboard_tiles` module's feature labels stay in sync with what the
    admin renamed in the Dashboard Sections editor. Tiles WITHOUT a custom
    title are reverted to their original seed label (two-way sync)."""
    mod = await db.acm_modules.find_one({"module_id": "dashboard_tiles"}, {"_id": 0, "features": 1})
    if not mod:
        return
    seed_names = await _seed_tile_feature_names()
    changed = False
    features = mod.get("features") or []
    for f in features:
        fid = f.get("feature_id") or ""
        if not fid.startswith("dash_"):
            continue
        tile_id = fid[len("dash_"):]
        custom = (tile_titles.get(tile_id) or "").strip()
        if custom:
            desired = f"Dashboard tile · {custom}"
        else:
            desired = seed_names.get(fid)  # revert to seed label (None → leave as-is)
        if desired and f.get("feature_name") != desired:
            f["feature_name"] = desired
            changed = True
    if changed:
        await db.acm_modules.update_one(
            {"module_id": "dashboard_tiles"}, {"$set": {"features": features}}
        )
        try:
            from core.acm_engine import bump_acm_cache_stamp, refresh_acm_cache
            await bump_acm_cache_stamp()
            await refresh_acm_cache()
        except Exception:
            pass


@router.get("/dashboard-layout")
async def get_dashboard_layout(user: dict = Depends(get_current_user)):
    """Effective dashboard layout (sections in order, with tiles, custom titles)."""
    return await _load_layout()


@router.put("/admin/dashboard-layout")
async def save_dashboard_layout(request: Request, user: dict = Depends(get_current_user)):
    if get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")
    body = await request.json()
    sections = body.get("sections")
    if not isinstance(sections, list) or not sections:
        raise HTTPException(400, "sections (non-empty list) required")

    cleaned = []
    seen_ids = set()
    for s in sections:
        sid = (s or {}).get("id")
        if not sid or sid in seen_ids:
            continue
        seen_ids.add(sid)
        tiles = [t for t in (s.get("tiles") or []) if isinstance(t, str)]
        cleaned.append({
            "id": sid,
            "emoji": (s.get("emoji") or "").strip(),
            "name": (s.get("name") or sid).strip(),
            "tiles": tiles,
        })

    # Custom per-tile display names (tileId → title). Empty/blank values are
    # dropped so the tile falls back to its registry default.
    raw_titles = body.get("tile_titles") or {}
    tile_titles = {}
    if isinstance(raw_titles, dict):
        for k, v in raw_titles.items():
            if isinstance(k, str) and isinstance(v, str) and v.strip():
                tile_titles[k] = v.strip()

    await db.app_config.update_one(
        {"key": _CFG_KEY},
        {"$set": {"key": _CFG_KEY, "sections": cleaned, "tile_titles": tile_titles,
                  "updated_at": datetime.now(timezone.utc).isoformat(),
                  "updated_by": user.get("email") or user.get("id")}},
        upsert=True,
    )
    await _sync_tile_titles_to_acm(tile_titles)
    return {"ok": True, "sections": cleaned, "tile_titles": tile_titles}


@router.post("/admin/dashboard-layout/reset")
async def reset_dashboard_layout(user: dict = Depends(get_current_user)):
    if get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")
    await db.app_config.delete_one({"key": _CFG_KEY})
    await _sync_tile_titles_to_acm({})  # revert any ACM label overrides to seed defaults
    return {"ok": True, "sections": DEFAULT_SECTIONS, "tile_titles": {}}
