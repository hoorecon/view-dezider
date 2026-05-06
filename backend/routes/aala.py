"""
AALA routes — Accrued Assets & Liabilities Analysis.

  GET    /api/aala/me                                  — the 5×3 cell grid (auto-seeds empty)
  PUT    /api/aala/me/cell/{factor}/{level}            — update one cell (summaries / score / lists)
  POST   /api/aala/me/cell/{factor}/{level}/asset      — add an asset item
  POST   /api/aala/me/cell/{factor}/{level}/liability  — add a liability item
  DELETE /api/aala/me/cell/{factor}/{level}/asset/{item_id}
  DELETE /api/aala/me/cell/{factor}/{level}/liability/{item_id}
  GET    /api/aala/me/deltas                           — last N delta-journal entries
  GET    /api/aala/me/feasibility/{factor}/{level}     — Time Dezider hook (0..1 score)

Delta journal is append-only (db.aala_deltas). Every cell mutation logs one.
"""
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.database import db
from core.auth import get_current_user
from models.aala_models import TEPFI, LEVELS, seed_empty_cells

router = APIRouter(prefix="/aala", tags=["AALA — Resource Ledger"])


class CellUpdateBody(BaseModel):
    assets_summary: Optional[str] = None
    liabilities_summary: Optional[str] = None
    balance_score: Optional[float] = None     # -10..+10


class AssetAddBody(BaseModel):
    label: str
    value: float = 0.0
    units: Optional[str] = None
    notes: Optional[str] = None


class LiabilityAddBody(BaseModel):
    label: str
    value: float = 0.0
    units: Optional[str] = None
    due: Optional[datetime] = None
    notes: Optional[str] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_factor_level(factor: str, level: str):
    if factor not in TEPFI:
        raise HTTPException(400, f"factor must be one of {TEPFI}")
    if level not in LEVELS:
        raise HTTPException(400, f"level must be one of {LEVELS}")


async def _get_or_seed(user_id: str) -> Dict[str, Any]:
    doc = await db.aala.find_one({"user_id": user_id}, {"_id": 0})
    if doc:
        return doc
    seed = {
        "user_id": user_id,
        "cells": seed_empty_cells(),
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.aala.insert_one(seed.copy())
    seed.pop("_id", None)
    return seed


async def _log_delta(user_id: str, factor: str, level: str, kind: str, delta_value: float = 0.0,
                    description: Optional[str] = None, source: str = "manual") -> None:
    await db.aala_deltas.insert_one({
        "delta_id": f"d_{uuid.uuid4().hex[:12]}",
        "user_id": user_id, "factor": factor, "level": level,
        "kind": kind, "delta_value": float(delta_value),
        "description": description, "source": source,
        "occurred_at": _now(),
    })


def _find_cell_idx(doc: Dict[str, Any], factor: str, level: str) -> int:
    for i, c in enumerate(doc.get("cells", [])):
        if c["factor"] == factor and c["level"] == level:
            return i
    return -1


@router.get("/me")
async def get_my_aala(user: dict = Depends(get_current_user)):
    doc = await _get_or_seed(user["user_id"])
    return {"ok": True, "aala": doc, "tepfi": TEPFI, "levels": LEVELS}


@router.put("/me/cell/{factor}/{level}")
async def update_cell(factor: str, level: str, body: CellUpdateBody, user: dict = Depends(get_current_user)):
    _validate_factor_level(factor, level)
    doc = await _get_or_seed(user["user_id"])
    idx = _find_cell_idx(doc, factor, level)
    if idx < 0:
        raise HTTPException(500, "cell missing — reseed")
    cell = doc["cells"][idx]
    if body.assets_summary is not None:
        cell["assets_summary"] = body.assets_summary[:500]
        await _log_delta(user["user_id"], factor, level, "summary_edit", description="assets_summary updated")
    if body.liabilities_summary is not None:
        cell["liabilities_summary"] = body.liabilities_summary[:500]
        await _log_delta(user["user_id"], factor, level, "summary_edit", description="liabilities_summary updated")
    if body.balance_score is not None:
        new_score = max(-10.0, min(10.0, float(body.balance_score)))
        old = cell.get("balance_score", 0.0)
        cell["balance_score"] = new_score
        await _log_delta(user["user_id"], factor, level, "balance_set", delta_value=new_score - old)
    cell["last_updated"] = _now()
    doc["cells"][idx] = cell
    doc["updated_at"] = _now()
    await db.aala.update_one({"user_id": user["user_id"]}, {"$set": {"cells": doc["cells"], "updated_at": doc["updated_at"]}})
    return {"ok": True, "cell": cell}


@router.post("/me/cell/{factor}/{level}/asset")
async def add_asset(factor: str, level: str, body: AssetAddBody, user: dict = Depends(get_current_user)):
    _validate_factor_level(factor, level)
    if not body.label.strip():
        raise HTTPException(400, "label is required")
    doc = await _get_or_seed(user["user_id"])
    idx = _find_cell_idx(doc, factor, level)
    item = {
        "item_id": f"a_{uuid.uuid4().hex[:10]}",
        "label": body.label.strip()[:200],
        "value": float(body.value),
        "units": body.units,
        "notes": body.notes,
        "since": _now(),
    }
    doc["cells"][idx].setdefault("assets", []).append(item)
    doc["cells"][idx]["last_updated"] = _now()
    await db.aala.update_one({"user_id": user["user_id"]}, {"$set": {"cells": doc["cells"]}})
    await _log_delta(user["user_id"], factor, level, "asset_add", body.value, body.label)
    return {"ok": True, "asset": item}


@router.post("/me/cell/{factor}/{level}/liability")
async def add_liability(factor: str, level: str, body: LiabilityAddBody, user: dict = Depends(get_current_user)):
    _validate_factor_level(factor, level)
    if not body.label.strip():
        raise HTTPException(400, "label is required")
    doc = await _get_or_seed(user["user_id"])
    idx = _find_cell_idx(doc, factor, level)
    item = {
        "item_id": f"l_{uuid.uuid4().hex[:10]}",
        "label": body.label.strip()[:200],
        "value": float(body.value),
        "units": body.units,
        "due": body.due,
        "notes": body.notes,
    }
    doc["cells"][idx].setdefault("liabilities", []).append(item)
    doc["cells"][idx]["last_updated"] = _now()
    await db.aala.update_one({"user_id": user["user_id"]}, {"$set": {"cells": doc["cells"]}})
    await _log_delta(user["user_id"], factor, level, "liability_add", body.value, body.label)
    return {"ok": True, "liability": item}


@router.delete("/me/cell/{factor}/{level}/asset/{item_id}")
async def remove_asset(factor: str, level: str, item_id: str, user: dict = Depends(get_current_user)):
    _validate_factor_level(factor, level)
    doc = await _get_or_seed(user["user_id"])
    idx = _find_cell_idx(doc, factor, level)
    cell = doc["cells"][idx]
    before = len(cell.get("assets", []))
    cell["assets"] = [a for a in cell.get("assets", []) if a.get("item_id") != item_id]
    if len(cell["assets"]) == before:
        raise HTTPException(404, "asset not found")
    cell["last_updated"] = _now()
    await db.aala.update_one({"user_id": user["user_id"]}, {"$set": {"cells": doc["cells"]}})
    await _log_delta(user["user_id"], factor, level, "asset_remove", description=item_id)
    return {"ok": True}


@router.delete("/me/cell/{factor}/{level}/liability/{item_id}")
async def remove_liability(factor: str, level: str, item_id: str, user: dict = Depends(get_current_user)):
    _validate_factor_level(factor, level)
    doc = await _get_or_seed(user["user_id"])
    idx = _find_cell_idx(doc, factor, level)
    cell = doc["cells"][idx]
    before = len(cell.get("liabilities", []))
    cell["liabilities"] = [l for l in cell.get("liabilities", []) if l.get("item_id") != item_id]
    if len(cell["liabilities"]) == before:
        raise HTTPException(404, "liability not found")
    cell["last_updated"] = _now()
    await db.aala.update_one({"user_id": user["user_id"]}, {"$set": {"cells": doc["cells"]}})
    await _log_delta(user["user_id"], factor, level, "liability_remove", description=item_id)
    return {"ok": True}


@router.get("/me/deltas")
async def list_my_deltas(user: dict = Depends(get_current_user), limit: int = 100):
    items = []
    async for d in db.aala_deltas.find({"user_id": user["user_id"]}, {"_id": 0}).sort("occurred_at", -1).limit(min(max(limit, 1), 500)):
        items.append(d)
    return {"items": items, "count": len(items)}


@router.get("/me/feasibility/{factor}/{level}")
async def feasibility(factor: str, level: str, user: dict = Depends(get_current_user)):
    """Used by Time Dezider — 0..1 score where 1 = lots of spare resource, 0 = depleted."""
    _validate_factor_level(factor, level)
    doc = await _get_or_seed(user["user_id"])
    idx = _find_cell_idx(doc, factor, level)
    cell = doc["cells"][idx]
    score = float(cell.get("balance_score", 0.0))                  # -10..+10
    feasibility_score = max(0.0, min(1.0, (score + 10.0) / 20.0))   # normalise to 0..1
    return {
        "factor": factor, "level": level,
        "feasibility": round(feasibility_score, 3),
        "balance_score": score,
        "asset_count": len(cell.get("assets", [])),
        "liability_count": len(cell.get("liabilities", [])),
    }
