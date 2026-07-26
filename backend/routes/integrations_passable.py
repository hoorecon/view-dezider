"""
Inter-module Passable Values (per JELCOS "Inter-module Integrations" matrix)
============================================================================
One generic hand-off engine: outcomes of MyDezider (Step 10) and Pros & Cons
(Step 8) — Option Names, Case-1 Worth %, MPPS Worth % — plus Solution Finder
SMART Goals (Step 1, as a one-liner with a navigable link) are exposed as
"passable values" that any target step can insert via the frontend
PassableValuePicker.
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from core.database import db
from core.auth import get_current_user

router = APIRouter(prefix="/integrations", tags=["Inter-module Integrations"])


@router.get("/passable-values")
async def passable_values(user: dict = Depends(get_current_user)):
    """All live passable values for the current user, grouped by kind:
      - kind='text'    → Option Names (MyDezider / Pros & Cons), SF SMART Goals
      - kind='percent' → Case-1 Worth %, MPPS Worth %, P&C option score %
    Each item: {kind, category, value, source, module, link, ref_id}."""
    uid = user.get("user_id")
    out: List[Dict[str, Any]] = []

    # ── MyDezider decisions ──
    decs = await db.decisions.find(
        {"user_id": uid},
        {"_id": 0, "id": 1, "title": 1, "options.id": 1, "options.name": 1,
         "options.worth_percentage": 1, "mpps_option_id": 1,
         "mpps_projected_worth": 1, "chosen_option_id": 1},
    ).sort("updated_at", -1).to_list(40)
    for d in decs:
        title = d.get("title") or "Decision"
        link = f"/decision/{d['id']}"
        for o in (d.get("options") or []):
            name = (o.get("name") or "").strip()
            if not name:
                continue
            chosen = o.get("id") == d.get("chosen_option_id")
            out.append({
                "kind": "text", "category": "Option Name", "value": name,
                "source": f"MyDezider · {title}" + (" · ✓ chosen" if chosen else ""),
                "module": "MYDEZIDER", "link": link, "ref_id": d["id"],
            })
            wp = float(o.get("worth_percentage") or 0)
            if wp > 0:
                out.append({
                    "kind": "percent", "category": "Case-1 Worth %",
                    "value": str(round(wp)),
                    "source": f"{name} · {title}",
                    "module": "MYDEZIDER", "link": link, "ref_id": d["id"],
                })
            if o.get("id") == d.get("mpps_option_id") and d.get("mpps_projected_worth"):
                out.append({
                    "kind": "percent", "category": "MPPS Worth %",
                    "value": str(round(float(d["mpps_projected_worth"]))),
                    "source": f"{name} · {title}",
                    "module": "MYDEZIDER", "link": link, "ref_id": d["id"],
                })

    # ── Pros & Cons analyses ──
    pcs = await db.pros_cons.find(
        {"user_id": uid},
        {"_id": 0, "id": 1, "title": 1, "options": 1, "assessments": 1, "config": 1},
    ).sort("updated_at", -1).to_list(40)
    for p in pcs:
        title = p.get("title") or "Pros & Cons"
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
                })

    # ── Solution Finder SMART Goals (Step 1) — one-liner + navigable link ──
    sfs = await db.solution_finders.find(
        {"user_id": uid, "smart_goal": {"$nin": [None, ""]}},
        {"_id": 0, "entry_id": 1, "smart_goal": 1},
    ).sort("updated_at", -1).to_list(40)
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
        })

    return {"values": out, "count": len(out)}
