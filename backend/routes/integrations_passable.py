"""
Inter-module Passable Values (per JELCOS "Inter-module Integrations" matrix)
============================================================================
One generic hand-off engine: outcomes of MyDezider (Step 10) and Pros & Cons
(Step 8) — Option Names, Case-1 Worth %, MPPS Worth % — plus Solution Finder
SMART Goals (Step 1, as a one-liner with a navigable link) are exposed as
"passable values" that any target step can insert via the frontend
PassableValuePicker.

Each value carries `life_area` and `updated_at` so the enlarged "Inter
Modules Connector" modal can filter by Module, Area of Life and Date Range
in addition to free-text search.
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from core.database import db
from core.auth import get_current_user

router = APIRouter(prefix="/integrations", tags=["Inter-module Integrations"])


def _iso(x):
    """Best-effort ISO 8601 string for a datetime/str/None."""
    if not x:
        return ""
    try:
        return x.isoformat() if hasattr(x, "isoformat") else str(x)
    except Exception:
        return ""


@router.get("/passable-values")
async def passable_values(user: dict = Depends(get_current_user)):
    """All live passable values for the current user.
    Each item: {kind, category, value, source, module, link, ref_id,
                life_area, updated_at, decision_title}."""
    uid = user.get("user_id")
    out: List[Dict[str, Any]] = []

    # ── MyDezider decisions ──
    decs = await db.decisions.find(
        {"user_id": uid},
        {"_id": 0, "id": 1, "title": 1, "life_area": 1, "updated_at": 1,
         "options.id": 1, "options.name": 1, "options.worth_percentage": 1,
         "mpps_option_id": 1, "mpps_projected_worth": 1, "chosen_option_id": 1},
    ).sort("updated_at", -1).to_list(80)
    for d in decs:
        title = d.get("title") or "Decision"
        life_area = d.get("life_area") or ""
        updated = _iso(d.get("updated_at"))
        # Fixed link: /prr/{id} is the actual Expo Router path (was /decision/{id}).
        link_options = f"/prr/{d['id']}?step=2"   # Option names live on Step 2
        link_worth = f"/prr/{d['id']}?step=10"    # Worth %/MPPS on Step 10
        for o in (d.get("options") or []):
            name = (o.get("name") or "").strip()
            if not name:
                continue
            chosen = o.get("id") == d.get("chosen_option_id")
            out.append({
                "kind": "text", "category": "Option Name", "value": name,
                "source": f"MyDezider · {title}" + (" · ✓ chosen" if chosen else ""),
                "module": "MYDEZIDER", "link": link_options, "ref_id": d["id"],
                "life_area": life_area, "updated_at": updated,
                "decision_title": title,
            })
            wp = float(o.get("worth_percentage") or 0)
            if wp > 0:
                out.append({
                    "kind": "percent", "category": "Case-1 Worth %",
                    "value": str(round(wp)),
                    "source": f"{name} · {title}",
                    "module": "MYDEZIDER", "link": link_worth, "ref_id": d["id"],
                    "life_area": life_area, "updated_at": updated,
                    "decision_title": title,
                })
            if o.get("id") == d.get("mpps_option_id") and d.get("mpps_projected_worth"):
                out.append({
                    "kind": "percent", "category": "MPPS Worth %",
                    "value": str(round(float(d["mpps_projected_worth"]))),
                    "source": f"{name} · {title}",
                    "module": "MYDEZIDER", "link": link_worth, "ref_id": d["id"],
                    "life_area": life_area, "updated_at": updated,
                    "decision_title": title,
                })

    # ── Pros & Cons analyses ──
    pcs = await db.pros_cons.find(
        {"user_id": uid},
        {"_id": 0, "id": 1, "title": 1, "life_area": 1, "updated_at": 1,
         "options": 1, "assessments": 1, "config": 1},
    ).sort("updated_at", -1).to_list(80)
    for p in pcs:
        title = p.get("title") or "Pros & Cons"
        life_area = p.get("life_area") or ""
        updated = _iso(p.get("updated_at"))
        link = f"/tools/pros-cons-wizard?id={p['id']}"
        final_id = (p.get("config") or {}).get("final_choice_option_id")
        for o in (p.get("options") or []):
            name = (o.get("name") or "").strip()
            if not name:
                continue
            out.append({
                "kind": "text", "category": "Option Name", "value": name,
                "source": f"Pros & Cons · {title}" + (" · ✓ chosen" if o.get("id") == final_id else ""),
                "module": "PROS_CONS", "link": link, "ref_id": p["id"],
                "life_area": life_area, "updated_at": updated,
                "decision_title": title,
            })
            cells = (p.get("assessments") or {}).get(o.get("id"), {}) or {}
            pcts = [float(c.get("assessment_pct") or 0) for c in cells.values() if isinstance(c, dict)]
            pcts = [x for x in pcts if x > 0]
            if pcts:
                out.append({
                    "kind": "percent", "category": "P&C Score %",
                    "value": str(round(sum(pcts) / len(pcts))),
                    "source": f"{name} · {title}",
                    "module": "PROS_CONS", "link": link, "ref_id": p["id"],
                    "life_area": life_area, "updated_at": updated,
                    "decision_title": title,
                })

    # ── Solution Finder SMART Goals (Step 1) — one-liner + navigable link ──
    sfs = await db.solution_finders.find(
        {"user_id": uid, "smart_goal": {"$nin": [None, ""]}},
        {"_id": 0, "entry_id": 1, "smart_goal": 1, "life_area": 1, "updated_at": 1, "title": 1},
    ).sort("updated_at", -1).to_list(80)
    for e in sfs:
        goal = (e.get("smart_goal") or "").strip()
        if not goal:
            continue
        out.append({
            "kind": "text", "category": "SMART Goal", "value": goal[:140],
            "source": "Solution Finder — open for Q5 action-plan details",
            "module": "SOLUTION_FINDER",
            "link": f"/tools/solution-finder?id={e['entry_id']}",
            "ref_id": e["entry_id"],
            "life_area": e.get("life_area") or "",
            "updated_at": _iso(e.get("updated_at")),
            "decision_title": e.get("title") or "Solution Finder",
        })

    # Distinct life areas (for the filter chip row in the picker)
    life_areas = sorted({(v.get("life_area") or "").strip() for v in out if v.get("life_area")})
    return {"values": out, "count": len(out), "life_areas": life_areas}
