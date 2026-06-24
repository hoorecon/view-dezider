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


async def _load_layout() -> list:
    doc = await db.app_config.find_one({"key": _CFG_KEY}, {"_id": 0})
    if not doc or not doc.get("sections"):
        return DEFAULT_SECTIONS
    return doc["sections"]


@router.get("/dashboard-layout")
async def get_dashboard_layout(user: dict = Depends(get_current_user)):
    """Effective dashboard layout (sections in order, with tiles)."""
    return {"sections": await _load_layout()}


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

    await db.app_config.update_one(
        {"key": _CFG_KEY},
        {"$set": {"key": _CFG_KEY, "sections": cleaned,
                  "updated_at": datetime.now(timezone.utc).isoformat(),
                  "updated_by": user.get("email") or user.get("id")}},
        upsert=True,
    )
    return {"ok": True, "sections": cleaned}


@router.post("/admin/dashboard-layout/reset")
async def reset_dashboard_layout(user: dict = Depends(get_current_user)):
    if get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")
    await db.app_config.delete_one({"key": _CFG_KEY})
    return {"ok": True, "sections": DEFAULT_SECTIONS}
