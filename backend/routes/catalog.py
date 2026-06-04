"""
Central Catalog Management (CCM) — REST routes.

Public:
  GET  /catalog/tree                        full tree (or filtered by life_area_id)
  GET  /catalog/nodes                       flat list w/ filters
  GET  /catalog/nodes/{node_id}             single node + ancestors (breadcrumb)

Admin:
  POST   /catalog/seed?force=true|false     idempotent seed of backbone + L2/L3
  POST   /catalog/nodes                     create a Level-2 or Level-3 node
  PUT    /catalog/nodes/{node_id}           update name/slug/icon/sort_order/active
  DELETE /catalog/nodes/{node_id}           soft-delete (only if no children + no solutions mapped)
  POST   /catalog/solutions/{solution_id}/map  map a solution to a node
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.auth import get_current_user, require_admin
from core.database import db
from data.catalog_seed import CCM_LEVEL2_BY_SUBAREA
from data.hos_seed_data import LIFE_AREAS, SUB_AREAS
from models.catalog_models import (
    CATALOG_MAX_DEPTH,
    CatalogMapping,
    CatalogNodeCreate,
    CatalogNodeUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalog", tags=["Central Catalog Management"])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
LA_SLUG_SHORT = {
    "la_health": "hlt",
    "la_knowledge": "kno",
    "la_relationships": "rel",
    "la_finance": "fin",
    "la_career": "car",
    "la_assets": "ast",
    "la_self": "self",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:60] or "node"


def _level0_node_id(life_area_id: str) -> str:
    return f"cn_l0_{life_area_id}"


def _level1_node_id(sub_area_id: str) -> str:
    return f"cn_l1_{sub_area_id}"


def _strip(doc: dict) -> dict:
    """Drop Mongo's _id from a returned doc."""
    if doc and "_id" in doc:
        doc.pop("_id", None)
    return doc


async def _ensure_unique_slug_under_parent(parent_id: str, slug: str, exclude_node_id: Optional[str] = None) -> None:
    q: Dict[str, Any] = {"parent_id": parent_id, "slug": slug}
    if exclude_node_id:
        q["node_id"] = {"$ne": exclude_node_id}
    existing = await db.catalog_nodes.find_one(q, {"_id": 1})
    if existing:
        raise HTTPException(409, f"slug '{slug}' already exists under parent {parent_id}")


# ---------------------------------------------------------------------------
# seed (idempotent)
# ---------------------------------------------------------------------------
async def _ensure_backbone_seeded() -> Dict[str, int]:
    """Insert / refresh Level-0 and Level-1 nodes (backbone) from HOS data."""
    inserted = 0
    updated = 0

    for la in LIFE_AREAS:
        la_id = la["id"]
        node_id = _level0_node_id(la_id)
        doc = {
            "node_id": node_id,
            "name": la["name"],
            "slug": la["slug"],
            "level": 0,
            "parent_id": None,
            "life_area_id": la_id,
            "sub_area_id": None,
            "icon": la.get("icon"),
            "color": la.get("color"),
            "sort_order": la.get("order", 0),
            "is_active": True,
            "is_immutable": True,
            "updated_at": _now(),
        }
        existing = await db.catalog_nodes.find_one({"node_id": node_id}, {"_id": 1, "name_custom": 1})
        if existing:
            if existing.get("name_custom"):
                doc.pop("name", None)
                doc.pop("icon", None)
            await db.catalog_nodes.update_one({"node_id": node_id}, {"$set": doc})
            updated += 1
        else:
            doc["created_at"] = _now()
            await db.catalog_nodes.insert_one(doc)
            inserted += 1

    for sa in SUB_AREAS:
        sa_id = sa["id"]
        la_id = sa["life_area_id"]
        node_id = _level1_node_id(sa_id)
        doc = {
            "node_id": node_id,
            "name": sa["name"],
            "slug": sa["slug"],
            "level": 1,
            "parent_id": _level0_node_id(la_id),
            "life_area_id": la_id,
            "sub_area_id": sa_id,
            "sort_order": sa.get("order", 0),
            "is_active": True,
            "is_immutable": True,
            "updated_at": _now(),
        }
        existing = await db.catalog_nodes.find_one({"node_id": node_id}, {"_id": 1, "name_custom": 1})
        if existing:
            if existing.get("name_custom"):
                doc.pop("name", None)
                doc.pop("icon", None)
            await db.catalog_nodes.update_one({"node_id": node_id}, {"$set": doc})
            updated += 1
        else:
            doc["created_at"] = _now()
            await db.catalog_nodes.insert_one(doc)
            inserted += 1

    return {"backbone_inserted": inserted, "backbone_updated": updated}


def _l2_node_id(la_short: str, slug: str) -> str:
    return f"cn_{la_short}_{slug}"


def _l3_node_id(la_short: str, l2_slug: str, l3_slug: str) -> str:
    return f"cn_{la_short}_{l2_slug}_{l3_slug}"


async def _seed_levels_2_and_3() -> Dict[str, int]:
    inserted = 0
    skipped = 0
    sub_area_lookup = {sa["id"]: sa for sa in SUB_AREAS}

    for sub_area_id, l2_list in CCM_LEVEL2_BY_SUBAREA.items():
        sa = sub_area_lookup.get(sub_area_id)
        if not sa:
            logger.warning("CCM seed: unknown sub_area_id %s — skipped", sub_area_id)
            continue
        la_id = sa["life_area_id"]
        la_short = LA_SLUG_SHORT.get(la_id, la_id.replace("la_", ""))
        parent_l1 = _level1_node_id(sub_area_id)

        for idx, l2 in enumerate(l2_list, start=1):
            l2_slug = _slugify(l2["slug"])
            l2_node_id = _l2_node_id(la_short, l2_slug)
            doc_l2 = {
                "node_id": l2_node_id,
                "name": l2["name"],
                "slug": l2_slug,
                "level": 2,
                "parent_id": parent_l1,
                "life_area_id": la_id,
                "sub_area_id": sub_area_id,
                "icon": l2.get("icon"),
                "color": l2.get("color"),
                "sort_order": idx,
                "is_active": True,
                "is_immutable": False,
                "updated_at": _now(),
            }
            existing = await db.catalog_nodes.find_one({"node_id": l2_node_id}, {"_id": 1})
            if existing:
                skipped += 1
            else:
                doc_l2["created_at"] = _now()
                await db.catalog_nodes.insert_one(doc_l2)
                inserted += 1

            for jdx, l3 in enumerate(l2.get("children", []), start=1):
                l3_slug = _slugify(l3["slug"])
                l3_node_id = _l3_node_id(la_short, l2_slug, l3_slug)
                doc_l3 = {
                    "node_id": l3_node_id,
                    "name": l3["name"],
                    "slug": l3_slug,
                    "level": 3,
                    "parent_id": l2_node_id,
                    "life_area_id": la_id,
                    "sub_area_id": sub_area_id,
                    "sort_order": jdx,
                    "is_active": True,
                    "is_immutable": False,
                    "updated_at": _now(),
                }
                exists_l3 = await db.catalog_nodes.find_one({"node_id": l3_node_id}, {"_id": 1})
                if exists_l3:
                    skipped += 1
                else:
                    doc_l3["created_at"] = _now()
                    await db.catalog_nodes.insert_one(doc_l3)
                    inserted += 1

    return {"l2_l3_inserted": inserted, "l2_l3_skipped_existing": skipped}


@router.post("/seed")
async def seed_catalog(
    force: bool = Query(False),
    user: dict = Depends(require_admin),
):
    """Idempotent seed. `force=true` wipes existing non-immutable (L2/L3) nodes
    and re-seeds them cleanly. Backbone (L0/L1) is always preserved."""
    if force:
        # Drop only L2/L3 (non-immutable) so backbone stays intact
        wipe = await db.catalog_nodes.delete_many({"is_immutable": {"$ne": True}})
        # Also clear catalog_node_id from solutions that pointed to wiped nodes
        await db.solutions_store.update_many(
            {"catalog_node_id": {"$exists": True}, "catalog_level": {"$gte": 2}},
            {"$unset": {"catalog_node_id": "", "catalog_level": "", "catalog_life_area_id": "", "catalog_sub_area_id": ""}},
        )
        wiped_count = wipe.deleted_count
    else:
        wiped_count = 0

    backbone = await _ensure_backbone_seeded()
    levels = await _seed_levels_2_and_3()

    # quick indexes
    await db.catalog_nodes.create_index("node_id", unique=True)
    await db.catalog_nodes.create_index("parent_id")
    await db.catalog_nodes.create_index("level")
    await db.catalog_nodes.create_index("life_area_id")
    await db.catalog_nodes.create_index([("parent_id", 1), ("slug", 1)])
    await db.solutions_store.create_index("catalog_node_id")

    total = await db.catalog_nodes.count_documents({})
    return {
        "ok": True,
        "force": force,
        "wiped_l2_l3_nodes": wiped_count,
        **backbone,
        **levels,
        "total_nodes": total,
    }


# ---------------------------------------------------------------------------
# read APIs
# ---------------------------------------------------------------------------
@router.get("/nodes")
async def list_nodes(
    life_area_id: Optional[str] = Query(None),
    sub_area_id: Optional[str] = Query(None),
    level: Optional[int] = Query(None, ge=0, le=CATALOG_MAX_DEPTH),
    parent_id: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    user: dict = Depends(get_current_user),
):
    q: Dict[str, Any] = {}
    if life_area_id:
        q["life_area_id"] = life_area_id
    if sub_area_id:
        q["sub_area_id"] = sub_area_id
    if level is not None:
        q["level"] = level
    if parent_id:
        q["parent_id"] = parent_id
    if is_active is not None:
        q["is_active"] = is_active

    cursor = db.catalog_nodes.find(q, {"_id": 0}).sort([("level", 1), ("sort_order", 1), ("name", 1)])
    nodes = [_strip(d) for d in await cursor.to_list(2000)]
    return {"items": nodes, "total": len(nodes)}


@router.get("/nodes/{node_id}")
async def get_node(node_id: str, user: dict = Depends(get_current_user)):
    node = await db.catalog_nodes.find_one({"node_id": node_id}, {"_id": 0})
    if not node:
        raise HTTPException(404, "node not found")

    # walk up to build ancestors
    ancestors: List[dict] = []
    parent_id = node.get("parent_id")
    while parent_id:
        anc = await db.catalog_nodes.find_one({"node_id": parent_id}, {"_id": 0})
        if not anc:
            break
        ancestors.append(anc)
        parent_id = anc.get("parent_id")
    ancestors.reverse()

    children_count = await db.catalog_nodes.count_documents({"parent_id": node_id})
    solutions_count = await db.solutions_store.count_documents({"catalog_node_id": node_id})

    return {
        "node": node,
        "ancestors": ancestors,
        "breadcrumb": [a["name"] for a in ancestors] + [node["name"]],
        "children_count": children_count,
        "solutions_count": solutions_count,
    }


@router.get("/tree")
async def get_tree(
    life_area_id: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    """Return the full tree as a nested structure."""
    q: Dict[str, Any] = {}
    if life_area_id:
        q["life_area_id"] = life_area_id

    cursor = db.catalog_nodes.find(q, {"_id": 0}).sort([("level", 1), ("sort_order", 1), ("name", 1)])
    flat = [_strip(d) for d in await cursor.to_list(5000)]

    # build a node_id -> children list
    by_parent: Dict[Optional[str], List[dict]] = {}
    for n in flat:
        by_parent.setdefault(n.get("parent_id"), []).append({**n, "children": []})

    # attach children recursively
    def attach(node: dict) -> None:
        kids = by_parent.get(node["node_id"], [])
        kids.sort(key=lambda x: (x.get("sort_order", 0), x.get("name", "")))
        node["children"] = kids
        for k in kids:
            attach(k)

    roots = by_parent.get(None, [])
    roots.sort(key=lambda x: (x.get("sort_order", 0), x.get("name", "")))
    for r in roots:
        attach(r)

    return {"roots": roots, "total_nodes": len(flat)}


# ---------------------------------------------------------------------------
# admin-only mutators
# ---------------------------------------------------------------------------
@router.post("/nodes")
async def create_node(body: CatalogNodeCreate, user: dict = Depends(require_admin)):
    parent = await db.catalog_nodes.find_one({"node_id": body.parent_id}, {"_id": 0})
    if not parent:
        raise HTTPException(404, "parent_id not found")
    if parent["level"] >= CATALOG_MAX_DEPTH:
        raise HTTPException(400, f"parent is already at max depth {CATALOG_MAX_DEPTH}")

    new_level = parent["level"] + 1
    if new_level not in (2, 3):
        raise HTTPException(400, "only Level 2 and Level 3 nodes can be created via this endpoint")

    slug = _slugify(body.slug or body.name)
    await _ensure_unique_slug_under_parent(parent["node_id"], slug)

    la_short = LA_SLUG_SHORT.get(parent["life_area_id"], parent["life_area_id"].replace("la_", ""))

    if new_level == 2:
        node_id = _l2_node_id(la_short, slug)
    else:  # level 3
        # find parent L2 slug
        node_id = f"{parent['node_id']}_{slug}"

    # collision guard
    if await db.catalog_nodes.find_one({"node_id": node_id}, {"_id": 1}):
        # auto-suffix to keep idempotent in face of name reuse across siblings
        node_id = f"{node_id}_{int(_now().timestamp())}"

    doc = {
        "node_id": node_id,
        "name": body.name,
        "slug": slug,
        "level": new_level,
        "parent_id": parent["node_id"],
        "life_area_id": parent["life_area_id"],
        "sub_area_id": parent["sub_area_id"],
        "description": body.description,
        "icon": body.icon,
        "color": body.color,
        "sort_order": body.sort_order,
        "is_active": True,
        "is_immutable": False,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.catalog_nodes.insert_one(doc)
    return _strip(doc)


@router.put("/nodes/{node_id}")
async def update_node(node_id: str, body: CatalogNodeUpdate, user: dict = Depends(require_admin)):
    existing = await db.catalog_nodes.find_one({"node_id": node_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "node not found")
    if existing.get("is_immutable") and body.name is not None:
        raise HTTPException(403, "cannot rename a backbone (Level 0/1) node")

    set_doc: Dict[str, Any] = {"updated_at": _now()}
    if body.name is not None:
        set_doc["name"] = body.name
    if body.description is not None:
        set_doc["description"] = body.description
    if body.icon is not None:
        set_doc["icon"] = body.icon
    if body.color is not None:
        set_doc["color"] = body.color
    if body.sort_order is not None:
        set_doc["sort_order"] = body.sort_order
    if body.is_active is not None:
        if existing.get("is_immutable") and body.is_active is False:
            raise HTTPException(403, "cannot deactivate a backbone node")
        set_doc["is_active"] = body.is_active
    if body.slug is not None and not existing.get("is_immutable"):
        new_slug = _slugify(body.slug)
        await _ensure_unique_slug_under_parent(existing["parent_id"], new_slug, exclude_node_id=node_id)
        set_doc["slug"] = new_slug

    await db.catalog_nodes.update_one({"node_id": node_id}, {"$set": set_doc})
    updated = await db.catalog_nodes.find_one({"node_id": node_id}, {"_id": 0})
    return _strip(updated)


@router.delete("/nodes/{node_id}")
async def delete_node(node_id: str, user: dict = Depends(require_admin)):
    existing = await db.catalog_nodes.find_one({"node_id": node_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "node not found")
    if existing.get("is_immutable"):
        raise HTTPException(403, "backbone (Level 0/1) nodes cannot be deleted")

    children = await db.catalog_nodes.count_documents({"parent_id": node_id})
    if children:
        raise HTTPException(409, f"cannot delete: {children} child node(s) exist. Delete or reparent children first.")

    mapped = await db.solutions_store.count_documents({"catalog_node_id": node_id})
    if mapped:
        raise HTTPException(409, f"cannot delete: {mapped} solution(s) mapped to this node. Re-map them first.")

    await db.catalog_nodes.delete_one({"node_id": node_id})
    return {"ok": True, "deleted_node_id": node_id}


# ---------------------------------------------------------------------------
# solution mapping
# ---------------------------------------------------------------------------
@router.post("/solutions/{solution_id}/map")
async def map_solution(
    solution_id: str,
    body: CatalogMapping,
    user: dict = Depends(require_admin),
):
    sol = await db.solutions_store.find_one({"solution_id": solution_id}, {"_id": 0})
    if not sol:
        raise HTTPException(404, "solution not found")
    node = await db.catalog_nodes.find_one({"node_id": body.catalog_node_id}, {"_id": 0})
    if not node:
        raise HTTPException(404, "catalog_node_id not found")
    await db.solutions_store.update_one(
        {"solution_id": solution_id},
        {"$set": {
            "catalog_node_id": node["node_id"],
            "catalog_life_area_id": node["life_area_id"],
            "catalog_sub_area_id": node.get("sub_area_id"),
            "catalog_level": node["level"],
            "updated_at": _now().isoformat(),
        }},
    )
    return {
        "ok": True,
        "solution_id": solution_id,
        "catalog_node_id": node["node_id"],
        "level": node["level"],
        "name": node["name"],
    }


# ---------------------------------------------------------------------------
# bulk auto-map (best-effort migration of pre-CCM solutions)
# ---------------------------------------------------------------------------
class AutoMapResult(BaseModel):
    updated: int
    unmapped: int


@router.post("/auto-map-existing")
async def auto_map_existing(user: dict = Depends(require_admin)) -> AutoMapResult:
    """For every solution missing `catalog_node_id`, fall back to its Level-1
    sub_area node (so it at least has a backbone mapping). Admins can refine
    individual solutions later via /solutions/{id}/map.
    """
    updated = 0
    unmapped = 0
    cursor = db.solutions_store.find(
        {"catalog_node_id": {"$exists": False}},
        {"_id": 0, "solution_id": 1, "sub_area_id": 1, "life_area_id": 1, "name": 1},
    )
    async for sol in cursor:
        sa = sol.get("sub_area_id")
        if sa:
            node_id = _level1_node_id(sa)
            node = await db.catalog_nodes.find_one({"node_id": node_id}, {"_id": 0})
            if node:
                await db.solutions_store.update_one(
                    {"solution_id": sol["solution_id"]},
                    {"$set": {
                        "catalog_node_id": node_id,
                        "catalog_life_area_id": node["life_area_id"],
                        "catalog_sub_area_id": node["sub_area_id"],
                        "catalog_level": node["level"],
                    }},
                )
                updated += 1
                continue
        unmapped += 1
    return AutoMapResult(updated=updated, unmapped=unmapped)
