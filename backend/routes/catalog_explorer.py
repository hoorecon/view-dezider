"""
Central Catalog Manager — Explorer (lazy, Windows-Explorer style).

Unifies the full backbone into one lazily-expanded tree:

  LifeArea (L0)
    └─ SubArea / catalog node (L1, L2, L3 …)         [catalog_nodes]
         └─ OrgType (7)                               [fixed taxonomy]
              └─ PNRAG (5: Problem/Need/Risk/Aspiration/General)
                   └─ Scenario                        [cce_scenarios]
                        ├─ Decision Templates         [cce_decision_templates]
                        ├─ Solution Templates (ASM, upcoming)  [cce_solution_templates]
                        └─ Solution Store items ★ ReviewNet     [solutions_store + review_net]

OrgType folders attach under ANY catalog level ≥ 1 (sub-area and deeper).
Scenarios are keyed by (catalog_node_id, org_type, pnrag) — the same key the
DEO website mapping uses. The three leaf collections are peers under a Scenario.

Full inline CRUD is provided for Scenarios, Decision Templates, ASM Solution
Templates and Solution Store items. ReviewNet factor ratings are shown read-only
with a deep-link to the ReviewNet editor.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.database import db
from core.auth import get_current_user

logger = logging.getLogger("catalog_explorer")
router = APIRouter(prefix="/catalog-explorer", tags=["Catalog Explorer"])

# ── Fixed taxonomies ─────────────────────────────────────────────────────────
ORG_TYPES: List[Dict[str, str]] = [
    {"key": "individual",  "label": "Individual",  "icon": "person",         "color": "#6366F1"},
    {"key": "business",    "label": "Business",     "icon": "business",       "color": "#0EA5E9"},
    {"key": "academy",     "label": "Academy",      "icon": "school",         "color": "#F59E0B"},
    {"key": "ngo",         "label": "NGO",          "icon": "heart",          "color": "#10B981"},
    {"key": "association",  "label": "Association",  "icon": "people-circle",  "color": "#F43F5E"},
    {"key": "govt",        "label": "Govt",         "icon": "globe",          "color": "#8B5CF6"},
    {"key": "nature",      "label": "Nature",       "icon": "leaf",           "color": "#16A34A"},
]
ORG_TYPE_KEYS = {o["key"] for o in ORG_TYPES}

PNRAG: List[Dict[str, str]] = [
    {"key": "problem",    "label": "Problem",    "icon": "warning",                       "color": "#EF4444"},
    {"key": "need",       "label": "Need",       "icon": "flag",                          "color": "#F59E0B"},
    {"key": "risk",       "label": "Risk",       "icon": "alert-circle",                  "color": "#DC2626"},
    {"key": "aspiration", "label": "Aspiration", "icon": "rocket",                        "color": "#10B981"},
    {"key": "general",    "label": "General",    "icon": "ellipsis-horizontal-circle",    "color": "#64748B"},
]
PNRAG_KEYS = {p["key"] for p in PNRAG}

LEAF_GROUPS = [
    {"key": "decision_templates", "label": "Decision Templates",          "icon": "git-branch",  "color": "#7C3AED"},
    {"key": "solution_templates", "label": "Solution Templates (ASM)",    "icon": "construct",   "color": "#0891B2"},
    {"key": "solution_items",     "label": "Solution Store Items",        "icon": "pricetags",   "color": "#059669"},
]
SOLUTION_TYPES = ["PRODUCT", "SERVICE", "EVENT", "PROJECT", "PERSON_CONTACT"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _role(user: dict) -> str:
    return (user.get("role") or "user").lower()


def _caps(user: dict) -> Dict[str, Any]:
    """Capability matrix that drives both the API guards and the UI affordances.

    - Super Admin  → full CRUD on the catalog structure (catalog nodes,
                     scenarios, decision templates, ASM solution templates).
    - Admin/Co-Admin → read-only on the structure, BUT may create/edit/delete
                     Solution Store items & ReviewNet entries (auto-approved).
    """
    role = _role(user)
    is_admin = role in ("admin", "co_admin", "super_admin")
    is_super = role == "super_admin"
    return {
        "role": role,
        "is_admin": is_admin,
        "is_super_admin": is_super,
        "can_full_crud": is_super,     # structure: nodes, scenarios, templates
        "can_store_crud": is_admin,    # solution store items + reviewnet (auto-approved)
    }


def _require_admin(user: dict) -> dict:
    """Read access to the Explorer — any platform admin role."""
    if _role(user) not in ("admin", "super_admin", "co_admin"):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


def _require_full(user: dict) -> dict:
    """Structural changes (scenarios / templates / nodes) — Super Admin only."""
    if _role(user) != "super_admin":
        raise HTTPException(
            status_code=403,
            detail="Super Admin access required to change catalog structure.",
        )
    return user


def _require_store(user: dict) -> dict:
    """Solution Store / ReviewNet entries — any admin (auto-approved)."""
    if _role(user) not in ("admin", "super_admin", "co_admin"):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


async def _solution_rating(solution_id: str) -> Dict[str, Any]:
    """Aggregate ReviewNet overall rating for a solution (approved reviews)."""
    cur = db.review_net.find(
        {"solution_id": solution_id, "status": {"$in": ["approved", "auto_approved"]}},
        {"_id": 0, "overall_rating": 1},
    )
    ratings = [r.get("overall_rating") for r in await cur.to_list(500) if r.get("overall_rating") is not None]
    if not ratings:
        return {"avg": None, "count": 0}
    return {"avg": round(sum(ratings) / len(ratings), 2), "count": len(ratings)}


def _node(node_type: str, key: str, label: str, **kw) -> Dict[str, Any]:
    base = {
        "id": key, "node_type": node_type, "label": label,
        "sublabel": kw.get("sublabel"), "icon": kw.get("icon"), "color": kw.get("color"),
        "expandable": kw.get("expandable", True),
        "editable": kw.get("editable", False),
        "deletable": kw.get("deletable", False),
        "badge": kw.get("badge"),
        # context carried for child queries / CRUD
        "ctx": kw.get("ctx", {}),
        "meta": kw.get("meta", {}),
    }
    return base


# ──────────────────────────────────────────────────────────────────────────────
# Lazy children
# ──────────────────────────────────────────────────────────────────────────────
@router.get("/children")
async def get_children(
    node_type: str = Query("catalog_node"),
    node_id: Optional[str] = Query(None),
    life_area_id: Optional[str] = Query(None),
    org_type: Optional[str] = Query(None),
    pnrag: Optional[str] = Query(None),
    scenario_id: Optional[str] = Query(None),
    group: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    _require_admin(user)
    caps = _caps(user)
    out: List[Dict[str, Any]] = []

    # ── catalog nodes (life areas + sub areas + deeper) ──
    if node_type == "catalog_node":
        if node_id is None:
            q = {"level": 0}
        else:
            q = {"parent_id": node_id}
        cur = db.catalog_nodes.find(q, {"_id": 0}).sort([("sort_order", 1), ("name", 1)])
        nodes = await cur.to_list(500)
        for n in nodes:
            lvl = n.get("level", 0)
            child_count = await db.catalog_nodes.count_documents({"parent_id": n["node_id"]})
            out.append(_node(
                "catalog_node", n["node_id"], n.get("name", "—"),
                sublabel=f"L{lvl}" + (f" · {child_count} sub" if child_count else ""),
                icon=n.get("icon") or ("folder" if lvl < 2 else "folder-open"),
                color=n.get("color") or "#475569",
                editable=(caps["can_full_crud"] and lvl >= 2 and not n.get("is_immutable")),
                deletable=(caps["can_full_crud"] and lvl >= 2 and not n.get("is_immutable")),
                ctx={"node_id": n["node_id"], "life_area_id": n.get("life_area_id"),
                     "level": lvl, "parent_id": n.get("parent_id")},
                meta={"is_immutable": bool(n.get("is_immutable")), "level": lvl, "slug": n.get("slug")},
            ))
        # OrgType folders under any node at level >= 1
        if node_id is not None:
            this = await db.catalog_nodes.find_one({"node_id": node_id}, {"_id": 0, "level": 1, "life_area_id": 1})
            if this and this.get("level", 0) >= 1:
                for o in ORG_TYPES:
                    sc = await db.cce_scenarios.count_documents({"catalog_node_id": node_id, "org_type": o["key"]})
                    out.append(_node(
                        "org_type", f"{node_id}::{o['key']}", o["label"],
                        sublabel="Organisation type", icon=o["icon"], color=o["color"],
                        badge=(str(sc) if sc else None),
                        ctx={"node_id": node_id, "org_type": o["key"],
                             "life_area_id": this.get("life_area_id")},
                    ))
        return {"children": out}

    # ── OrgType -> PNRAG ──
    if node_type == "org_type":
        for p in PNRAG:
            sc = await db.cce_scenarios.count_documents(
                {"catalog_node_id": node_id, "org_type": org_type, "pnrag": p["key"]})
            out.append(_node(
                "pnrag", f"{node_id}::{org_type}::{p['key']}", p["label"],
                sublabel="PNRAG", icon=p["icon"], color=p["color"],
                badge=(str(sc) if sc else None),
                ctx={"node_id": node_id, "org_type": org_type, "pnrag": p["key"],
                     "life_area_id": life_area_id},
            ))
        return {"children": out}

    # ── PNRAG -> Scenarios ──
    if node_type == "pnrag":
        cur = db.cce_scenarios.find(
            {"catalog_node_id": node_id, "org_type": org_type, "pnrag": pnrag},
            {"_id": 0}).sort([("sort_order", 1), ("created_at", 1)])
        for s in await cur.to_list(500):
            out.append(_node(
                "scenario", s["scenario_id"], s.get("title", "—"),
                sublabel=s.get("description") or "Scenario", icon="bookmark", color="#9333EA",
                editable=caps["can_full_crud"], deletable=caps["can_full_crud"],
                ctx={"scenario_id": s["scenario_id"], "node_id": node_id,
                     "org_type": org_type, "pnrag": pnrag, "life_area_id": life_area_id},
                meta={"title": s.get("title"), "description": s.get("description")},
            ))
        return {"children": out}

    # ── Scenario -> 3 leaf groups ──
    if node_type == "scenario":
        dt = await db.cce_decision_templates.count_documents({"scenario_id": scenario_id})
        st = await db.cce_solution_templates.count_documents({"scenario_id": scenario_id})
        si = await db.solutions_store.count_documents({"scenario_ids": scenario_id})
        counts = {"decision_templates": dt, "solution_templates": st, "solution_items": si}
        for g in LEAF_GROUPS:
            out.append(_node(
                "group", f"{scenario_id}::{g['key']}", g["label"],
                sublabel=("Peer items under scenario"), icon=g["icon"], color=g["color"],
                badge=str(counts[g["key"]]),
                ctx={"scenario_id": scenario_id, "group": g["key"]},
                meta={"group": g["key"]},
            ))
        return {"children": out}

    # ── Group -> items ──
    if node_type == "group":
        if group == "decision_templates":
            cur = db.cce_decision_templates.find({"scenario_id": scenario_id}, {"_id": 0}).sort("created_at", 1)
            for t in await cur.to_list(500):
                out.append(_node(
                    "decision_template", t["template_id"], t.get("title", "—"),
                    sublabel=t.get("decision_type") or "Decision template",
                    icon="git-branch", color="#7C3AED", expandable=False,
                    editable=caps["can_full_crud"], deletable=caps["can_full_crud"],
                    ctx={"template_id": t["template_id"], "scenario_id": scenario_id},
                    meta=t,
                ))
        elif group == "solution_templates":
            cur = db.cce_solution_templates.find({"scenario_id": scenario_id}, {"_id": 0}).sort("created_at", 1)
            for t in await cur.to_list(500):
                out.append(_node(
                    "solution_template", t["template_id"], t.get("title", "—"),
                    sublabel=t.get("asm_stage") or "ASM solution template",
                    icon="construct", color="#0891B2", expandable=False,
                    editable=caps["can_full_crud"], deletable=caps["can_full_crud"],
                    ctx={"template_id": t["template_id"], "scenario_id": scenario_id},
                    meta=t,
                ))
        elif group == "solution_items":
            cur = db.solutions_store.find({"scenario_ids": scenario_id}, {"_id": 0}).sort("created_at", -1)
            for s in await cur.to_list(500):
                rating = await _solution_rating(s["solution_id"])
                badge = (f"★ {rating['avg']} ({rating['count']})" if rating["avg"] is not None else "no ratings")
                out.append(_node(
                    "solution_item", s["solution_id"], s.get("name", "—"),
                    sublabel=f"{s.get('type', '')} · {', '.join(s.get('org_types') or []) or 'any org'}",
                    icon="pricetag", color="#059669", expandable=False,
                    editable=caps["can_store_crud"], deletable=caps["can_store_crud"], badge=badge,
                    ctx={"solution_id": s["solution_id"], "scenario_id": scenario_id},
                    meta={"type": s.get("type"), "url": s.get("url"), "provider": s.get("provider"),
                          "description": s.get("description"), "org_types": s.get("org_types") or [],
                          "rating": rating},
                ))
        return {"children": out}

    raise HTTPException(status_code=400, detail=f"Unknown node_type '{node_type}'")


@router.get("/meta")
async def explorer_meta(user: dict = Depends(get_current_user)):
    _require_admin(user)
    return {"org_types": ORG_TYPES, "pnrag": PNRAG, "leaf_groups": LEAF_GROUPS,
            "solution_types": SOLUTION_TYPES, "capabilities": _caps(user)}


# ──────────────────────────────────────────────────────────────────────────────
# Scenario CRUD
# ──────────────────────────────────────────────────────────────────────────────
class ScenarioCreate(BaseModel):
    catalog_node_id: str
    org_type: str
    pnrag: str
    title: str = Field(..., min_length=1, max_length=160)
    description: Optional[str] = Field(default=None, max_length=600)
    sort_order: int = 0


class ScenarioUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=160)
    description: Optional[str] = Field(default=None, max_length=600)
    sort_order: Optional[int] = None


@router.post("/scenarios")
async def create_scenario(body: ScenarioCreate, user: dict = Depends(get_current_user)):
    _require_full(user)
    if body.org_type not in ORG_TYPE_KEYS:
        raise HTTPException(400, "Invalid org_type.")
    if body.pnrag not in PNRAG_KEYS:
        raise HTTPException(400, "Invalid pnrag.")
    node = await db.catalog_nodes.find_one({"node_id": body.catalog_node_id}, {"_id": 0, "life_area_id": 1})
    if not node:
        raise HTTPException(404, "Catalog node not found.")
    doc = {
        "scenario_id": f"scn_{uuid.uuid4().hex[:14]}",
        "catalog_node_id": body.catalog_node_id,
        "life_area_id": node.get("life_area_id"),
        "org_type": body.org_type,
        "pnrag": body.pnrag,
        "title": body.title.strip(),
        "description": (body.description or "").strip() or None,
        "sort_order": body.sort_order,
        "created_at": _now(), "updated_at": _now(),
    }
    await db.cce_scenarios.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/scenarios/{scenario_id}")
async def update_scenario(scenario_id: str, body: ScenarioUpdate, user: dict = Depends(get_current_user)):
    _require_full(user)
    updates = {k: v for k, v in body.dict().items() if v is not None}
    if not updates:
        raise HTTPException(400, "Nothing to update.")
    updates["updated_at"] = _now()
    r = await db.cce_scenarios.update_one({"scenario_id": scenario_id}, {"$set": updates})
    if r.matched_count == 0:
        raise HTTPException(404, "Scenario not found.")
    return {"success": True}


@router.delete("/scenarios/{scenario_id}")
async def delete_scenario(
    scenario_id: str,
    cascade: bool = Query(False),
    user: dict = Depends(get_current_user),
):
    _require_full(user)
    dt = await db.cce_decision_templates.count_documents({"scenario_id": scenario_id})
    st = await db.cce_solution_templates.count_documents({"scenario_id": scenario_id})
    si = await db.solutions_store.count_documents({"scenario_ids": scenario_id})
    if (dt + st + si) and not cascade:
        raise HTTPException(
            status_code=409,
            detail=(
                f"This scenario still has {dt} decision template(s), {st} solution "
                f"template(s) and {si} store item(s). Remove them first, or confirm "
                f"a cascade delete."
            ),
        )
    await db.cce_scenarios.delete_one({"scenario_id": scenario_id})
    await db.cce_decision_templates.delete_many({"scenario_id": scenario_id})
    await db.cce_solution_templates.delete_many({"scenario_id": scenario_id})
    # Store items are real catalogued records — unlink the scenario, never hard-delete.
    await db.solutions_store.update_many(
        {"scenario_ids": scenario_id}, {"$pull": {"scenario_ids": scenario_id}}
    )
    return {
        "success": True,
        "deleted_decision_templates": dt,
        "deleted_solution_templates": st,
        "unlinked_store_items": si,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Decision Template CRUD (scenario-linked)
# ──────────────────────────────────────────────────────────────────────────────
class DecisionTemplateBody(BaseModel):
    scenario_id: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=200)
    decision_type: Optional[str] = Field(default=None, max_length=60)
    description: Optional[str] = Field(default=None, max_length=1000)


@router.post("/decision-templates")
async def create_decision_template(body: DecisionTemplateBody, user: dict = Depends(get_current_user)):
    _require_full(user)
    if not body.scenario_id:
        raise HTTPException(400, "scenario_id is required.")
    doc = {
        "template_id": f"cdt_{uuid.uuid4().hex[:14]}",
        "scenario_id": body.scenario_id,
        "title": body.title.strip(),
        "decision_type": (body.decision_type or "").strip() or None,
        "description": (body.description or "").strip() or None,
        "created_at": _now(), "updated_at": _now(),
    }
    await db.cce_decision_templates.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/decision-templates/{template_id}")
async def update_decision_template(template_id: str, body: DecisionTemplateBody, user: dict = Depends(get_current_user)):
    _require_full(user)
    updates = {"title": body.title.strip(), "updated_at": _now()}
    if body.decision_type is not None:
        updates["decision_type"] = body.decision_type.strip() or None
    if body.description is not None:
        updates["description"] = body.description.strip() or None
    r = await db.cce_decision_templates.update_one({"template_id": template_id}, {"$set": updates})
    if r.matched_count == 0:
        raise HTTPException(404, "Template not found.")
    return {"success": True}


@router.delete("/decision-templates/{template_id}")
async def delete_decision_template(template_id: str, user: dict = Depends(get_current_user)):
    _require_full(user)
    await db.cce_decision_templates.delete_one({"template_id": template_id})
    return {"success": True}


# ──────────────────────────────────────────────────────────────────────────────
# ASM Solution Template CRUD (scenario-linked, upcoming)
# ──────────────────────────────────────────────────────────────────────────────
class SolutionTemplateBody(BaseModel):
    scenario_id: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=200)
    asm_stage: Optional[str] = Field(default=None, max_length=60)
    description: Optional[str] = Field(default=None, max_length=1000)


@router.post("/solution-templates")
async def create_solution_template(body: SolutionTemplateBody, user: dict = Depends(get_current_user)):
    _require_full(user)
    if not body.scenario_id:
        raise HTTPException(400, "scenario_id is required.")
    doc = {
        "template_id": f"cst_{uuid.uuid4().hex[:14]}",
        "scenario_id": body.scenario_id,
        "title": body.title.strip(),
        "asm_stage": (body.asm_stage or "").strip() or None,
        "description": (body.description or "").strip() or None,
        "created_at": _now(), "updated_at": _now(),
    }
    await db.cce_solution_templates.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/solution-templates/{template_id}")
async def update_solution_template(template_id: str, body: SolutionTemplateBody, user: dict = Depends(get_current_user)):
    _require_full(user)
    updates = {"title": body.title.strip(), "updated_at": _now()}
    if body.asm_stage is not None:
        updates["asm_stage"] = body.asm_stage.strip() or None
    if body.description is not None:
        updates["description"] = body.description.strip() or None
    r = await db.cce_solution_templates.update_one({"template_id": template_id}, {"$set": updates})
    if r.matched_count == 0:
        raise HTTPException(404, "Template not found.")
    return {"success": True}


@router.delete("/solution-templates/{template_id}")
async def delete_solution_template(template_id: str, user: dict = Depends(get_current_user)):
    _require_full(user)
    await db.cce_solution_templates.delete_one({"template_id": template_id})
    return {"success": True}


# ──────────────────────────────────────────────────────────────────────────────
# Solution Store item CRUD (real solutions_store, scenario-mapped)
# ──────────────────────────────────────────────────────────────────────────────
class SolutionItemBody(BaseModel):
    scenario_id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=200)
    type: str = "PRODUCT"
    description: Optional[str] = Field(default=None, max_length=1000)
    url: Optional[str] = None
    provider: Optional[str] = None


@router.post("/solution-items")
async def create_solution_item(body: SolutionItemBody, user: dict = Depends(get_current_user)):
    _require_store(user)
    if not body.scenario_id:
        raise HTTPException(400, "scenario_id is required.")
    if body.type.upper() not in SOLUTION_TYPES:
        raise HTTPException(400, f"Invalid type. One of {SOLUTION_TYPES}")
    scn = await db.cce_scenarios.find_one({"scenario_id": body.scenario_id}, {"_id": 0})
    if not scn:
        raise HTTPException(404, "Scenario not found.")
    node = await db.catalog_nodes.find_one({"node_id": scn["catalog_node_id"]}, {"_id": 0})
    sol = {
        "solution_id": str(uuid.uuid4()),
        "type": body.type.upper(),
        "name": body.name.strip(),
        "description": (body.description or "").strip(),
        "life_area_id": scn.get("life_area_id"),
        "sub_area_id": (node or {}).get("sub_area_id"),
        "catalog_node_id": scn["catalog_node_id"],
        "org_types": [scn["org_type"]],
        "decision_types": [],
        "scenario_ids": [body.scenario_id],
        "visibility": "PUBLIC",
        "approval_status": "approved",
        "is_authorized": True,
        "created_by": user["user_id"],
        "created_by_name": user.get("name", ""),
        "url": (body.url or "").strip(),
        "provider": (body.provider or "").strip(),
        "tags": [], "type_specific": {}, "quantitative_factors": [],
        "country": "IN", "language": "en", "currency": "INR",
        "status": "active",
        "created_at": _now(), "updated_at": _now(),
    }
    await db.solutions_store.insert_one(sol)
    sol.pop("_id", None)
    return sol


@router.put("/solution-items/{solution_id}")
async def update_solution_item(solution_id: str, body: SolutionItemBody, user: dict = Depends(get_current_user)):
    _require_store(user)
    updates = {"name": body.name.strip(), "updated_at": _now()}
    if body.type:
        updates["type"] = body.type.upper()
    if body.description is not None:
        updates["description"] = body.description.strip()
    if body.url is not None:
        updates["url"] = body.url.strip()
    if body.provider is not None:
        updates["provider"] = body.provider.strip()
    r = await db.solutions_store.update_one({"solution_id": solution_id}, {"$set": updates})
    if r.matched_count == 0:
        raise HTTPException(404, "Solution not found.")
    return {"success": True}


@router.delete("/solution-items/{solution_id}")
async def delete_solution_item(solution_id: str, user: dict = Depends(get_current_user)):
    _require_store(user)
    await db.solutions_store.delete_one({"solution_id": solution_id})
    return {"success": True}


@router.get("/solution-items/{solution_id}/ratings")
async def solution_ratings(solution_id: str, user: dict = Depends(get_current_user)):
    """ReviewNet qualitative-factor breakdown for a solution (read-only)."""
    _require_admin(user)
    cur = db.review_net.find(
        {"solution_id": solution_id, "status": {"$in": ["approved", "auto_approved"]}},
        {"_id": 0, "factor_ratings": 1, "overall_rating": 1})
    reviews = await cur.to_list(500)
    factor_acc: Dict[str, List[float]] = {}
    overall: List[float] = []
    for rv in reviews:
        if rv.get("overall_rating") is not None:
            overall.append(rv["overall_rating"])
        for fk, fv in (rv.get("factor_ratings") or {}).items():
            if isinstance(fv, (int, float)):
                factor_acc.setdefault(fk, []).append(fv)
    factors = [{"factor": k, "avg": round(sum(v) / len(v), 2), "count": len(v)} for k, v in factor_acc.items()]
    return {
        "overall": (round(sum(overall) / len(overall), 2) if overall else None),
        "review_count": len(reviews),
        "factors": sorted(factors, key=lambda x: x["factor"]),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Seed / migrate scenarios from existing decision templates (Super Admin)
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/seed-scenarios-from-templates")
async def seed_scenarios_from_templates(
    force: bool = Query(False),
    user: dict = Depends(get_current_user),
):
    """Best-effort migration: turn existing `decision_templates` rows into
    Explorer `cce_scenarios` so the tree is populated out of the box.

    Each template is placed under its life-area's FIRST sub-area node with
    org_type='individual' and pnrag='general'. Idempotent by (title, node).
    Super Admin only.
    """
    _require_full(user)

    # Build life_area_id -> first sub_area (L1) catalog node
    first_sub_by_la: Dict[str, dict] = {}
    cur = db.catalog_nodes.find({"level": 1}, {"_id": 0}).sort([("sort_order", 1), ("name", 1)])
    async for n in cur:
        la = n.get("life_area_id")
        if la and la not in first_sub_by_la:
            first_sub_by_la[la] = n

    created = 0
    skipped = 0
    unmatched = 0

    async for t in db.decision_templates.find({}, {"_id": 0}):
        la = t.get("life_area")
        node = first_sub_by_la.get(la)
        if not node:
            unmatched += 1
            continue
        title = (t.get("name") or "").strip()
        if not title:
            unmatched += 1
            continue
        existing = await db.cce_scenarios.find_one(
            {"catalog_node_id": node["node_id"], "org_type": "individual",
             "pnrag": "general", "title": title},
            {"_id": 1},
        )
        if existing:
            if force:
                await db.cce_scenarios.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {
                        "description": (t.get("description") or "").strip() or None,
                        "updated_at": _now(),
                    }},
                )
            skipped += 1
            continue
        doc = {
            "scenario_id": f"scn_{uuid.uuid4().hex[:14]}",
            "catalog_node_id": node["node_id"],
            "life_area_id": node.get("life_area_id"),
            "org_type": "individual",
            "pnrag": "general",
            "title": title,
            "description": (t.get("description") or "").strip() or None,
            "sort_order": 0,
            "source": "decision_template_migration",
            "source_template_id": t.get("id"),
            "created_at": _now(), "updated_at": _now(),
        }
        await db.cce_scenarios.insert_one(doc)
        created += 1

    # ensure helpful indexes
    await db.cce_scenarios.create_index([("catalog_node_id", 1), ("org_type", 1), ("pnrag", 1)])
    await db.cce_scenarios.create_index("scenario_id", unique=True)
    await db.cce_decision_templates.create_index("scenario_id")
    await db.cce_solution_templates.create_index("scenario_id")

    return {
        "ok": True,
        "scenarios_created": created,
        "skipped_existing": skipped,
        "templates_unmatched": unmatched,
    }
