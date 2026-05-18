"""
decision_linking.py — unified endpoint listing FINALIZED decisions across
PRR, Solution Finder, Conflict Breaker and Solution Matrix.
"""
from fastapi import APIRouter, Depends
from core.database import db
from core.auth import get_current_user

router = APIRouter(tags=["Decision Linking"])


def _iso(v):
    if v is None: return None
    if hasattr(v, "isoformat"): return v.isoformat()
    return str(v)


@router.get("/decision-links/sources")
async def list_linkable_decisions(user: dict = Depends(get_current_user)):
    user_id = user["user_id"]
    items: list[dict] = []

    # PRR
    cur = db.prr_decisions.find(
        {"user_id": user_id, "status": {"$in": ["finalized", "archived", "completed"]}},
        {"_id": 0, "id": 1, "title": 1, "chosen_option_id": 1, "options": 1, "updated_at": 1},
    ).sort("updated_at", -1).limit(50)
    async for d in cur:
        chosen_label = None
        chosen_score = None
        for opt in (d.get("options") or []):
            if opt.get("id") == d.get("chosen_option_id"):
                chosen_label = opt.get("name") or opt.get("label")
                chosen_score = opt.get("score_pct") or opt.get("composite_score")
                break
        items.append({
            "decision_id": d.get("id"),
            "module": "prr",
            "title": d.get("title", ""),
            "selected_option_label": chosen_label,
            "score_pct": chosen_score,
            "finalized_at": _iso(d.get("updated_at")),
        })

    # Solution Finder
    cur = db.solution_finders.find(
        {"user_id": user_id, "status": {"$in": ["completed", "finalized"]}},
        {"_id": 0, "entry_id": 1, "smart_goal": 1, "area_of_life": 1, "action_items": 1, "updated_at": 1},
    ).sort("updated_at", -1).limit(50)
    async for d in cur:
        chosen_label = None
        for a in (d.get("action_items") or []):
            if a.get("chosen") or a.get("selected"):
                chosen_label = a.get("title") or a.get("description")
                break
        items.append({
            "decision_id": d.get("entry_id"),
            "module": "solution_finder",
            "title": d.get("smart_goal") or d.get("area_of_life") or "Solution Finder",
            "selected_option_label": chosen_label,
            "score_pct": None,
            "finalized_at": _iso(d.get("updated_at")),
        })

    # Conflict Breaker
    cur = db.conflict_breaker_sessions.find(
        {"user_id": user_id, "status": {"$in": ["completed", "closed"]}},
        {"_id": 0, "session_id": 1, "title": 1, "updated_at": 1, "closure": 1},
    ).sort("updated_at", -1).limit(50)
    async for d in cur:
        items.append({
            "decision_id": d.get("session_id"),
            "module": "conflict_breaker",
            "title": d.get("title", "Conflict Breaker session"),
            "selected_option_label": (d.get("closure") or {}).get("resolution"),
            "score_pct": None,
            "finalized_at": _iso(d.get("updated_at")),
        })

    # Solution Matrix
    cur = db.solution_matrices.find(
        {"user_id": user_id, "status": {"$in": ["completed", "finalized"]}},
        {"_id": 0, "entry_id": 1, "problem_statement": 1, "updated_at": 1},
    ).sort("updated_at", -1).limit(50)
    async for d in cur:
        items.append({
            "decision_id": d.get("entry_id"),
            "module": "solution_matrix",
            "title": d.get("problem_statement", "Solution Matrix"),
            "selected_option_label": None,
            "score_pct": None,
            "finalized_at": _iso(d.get("updated_at")),
        })

    return {"items": items, "count": len(items)}
