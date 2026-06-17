"""7×7 Organization Matrix — Masters CRUD + Per-Org Assessment.

Backend for:
  - Admin Masters CRUD over 7 Divisions / 7 Drivers / Scoring Scale
  - Per-Org sub-team CRUD on top of standard seed
  - Per-cell scoring (division × driver) with fortnightly cadence
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field

from core.database import db
from core.auth import get_current_user, ADMIN_ROLES, get_user_role
from data.seven_seven_seed import SEVEN_DIVISIONS, SEVEN_DRIVERS, SCORING_SCALE

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/seven-seven", tags=["7x7 Matrix"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _ensure_seeded():
    """Idempotent seed of master tables."""
    for d in SEVEN_DIVISIONS:
        await db.ss_divisions.update_one(
            {"code": d["code"]},
            {"$setOnInsert": {**d, "id": str(uuid.uuid4()), "platform_default": True, "active": True, "created_at": _now()}},
            upsert=True,
        )
    for dr in SEVEN_DRIVERS:
        await db.ss_drivers.update_one(
            {"code": dr["code"]},
            {"$setOnInsert": {**dr, "id": str(uuid.uuid4()), "platform_default": True, "active": True, "created_at": _now()}},
            upsert=True,
        )
    for sc in SCORING_SCALE:
        await db.ss_scale.update_one(
            {"code": sc["code"]},
            {"$setOnInsert": {**sc, "id": str(uuid.uuid4()), "platform_default": True, "active": True, "created_at": _now()}},
            upsert=True,
        )


# ─── Masters ────────────────────────────────────────────────────────
@router.get("/divisions")
async def list_divisions(user: dict = Depends(get_current_user)):
    await _ensure_seeded()
    rows = await db.ss_divisions.find({"active": True}, {"_id": 0}).sort("order", 1).to_list(100)
    return {"divisions": rows}


@router.get("/drivers")
async def list_drivers(user: dict = Depends(get_current_user)):
    await _ensure_seeded()
    rows = await db.ss_drivers.find({"active": True}, {"_id": 0}).sort("order", 1).to_list(100)
    return {"drivers": rows}


@router.get("/scale")
async def list_scale(user: dict = Depends(get_current_user)):
    await _ensure_seeded()
    rows = await db.ss_scale.find({"active": True}, {"_id": 0}).sort("order", -1).to_list(20)
    return {"scale": rows}


class DivisionIn(BaseModel):
    code: str
    name: str
    department: Optional[str] = ""
    icon: Optional[str] = "folder"
    color: Optional[str] = "#64748B"
    order: int = 100
    sub_teams: List[Dict[str, Any]] = Field(default_factory=list)
    active: bool = True


class DriverIn(BaseModel):
    code: str
    name: str
    category: str  # team|systems|strategy
    hint: Optional[str] = ""
    order: int = 100
    active: bool = True


@router.post("/divisions")
async def upsert_division(p: DivisionIn, user: dict = Depends(get_current_user)):
    if get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Admin only")
    doc = p.model_dump()
    existing = await db.ss_divisions.find_one({"code": p.code})
    if existing:
        await db.ss_divisions.update_one({"code": p.code}, {"$set": doc})
    else:
        doc.update({"id": str(uuid.uuid4()), "platform_default": False, "created_at": _now()})
        await db.ss_divisions.insert_one(doc)
    return {"ok": True}


@router.post("/drivers")
async def upsert_driver(p: DriverIn, user: dict = Depends(get_current_user)):
    if get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Admin only")
    doc = p.model_dump()
    existing = await db.ss_drivers.find_one({"code": p.code})
    if existing:
        await db.ss_drivers.update_one({"code": p.code}, {"$set": doc})
    else:
        doc.update({"id": str(uuid.uuid4()), "platform_default": False, "created_at": _now()})
        await db.ss_drivers.insert_one(doc)
    return {"ok": True}


@router.delete("/divisions/{code}")
async def delete_division(code: str, user: dict = Depends(get_current_user)):
    if get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Admin only")
    existing = await db.ss_divisions.find_one({"code": code})
    if not existing:
        raise HTTPException(404, "Not found")
    if existing.get("platform_default"):
        raise HTTPException(400, "Cannot delete a platform-default division — disable it instead")
    await db.ss_divisions.delete_one({"code": code})
    return {"ok": True}


@router.delete("/drivers/{code}")
async def delete_driver(code: str, user: dict = Depends(get_current_user)):
    if get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Admin only")
    existing = await db.ss_drivers.find_one({"code": code})
    if not existing:
        raise HTTPException(404, "Not found")
    if existing.get("platform_default"):
        raise HTTPException(400, "Cannot delete a platform-default driver — disable it instead")
    await db.ss_drivers.delete_one({"code": code})
    return {"ok": True}


# ─── Per-Org Assessment ─────────────────────────────────────────────
class CellScoreIn(BaseModel):
    user_org_id: str  # custom org id from user_orgs collection
    division_code: str
    driver_code: str
    scale_code: str  # up_to_mark|moderate|inadequate
    remarks: Optional[str] = ""
    sub_team_code: Optional[str] = None  # if scoring a sub-team rather than whole division


@router.post("/assess")
async def submit_cell_score(p: CellScoreIn, user: dict = Depends(get_current_user)):
    # Ensure user owns the org or is admin
    org = await db.user_orgs.find_one({"id": p.user_org_id})
    if not org:
        raise HTTPException(404, "User-Org not found")
    if org.get("owner_user_id") != user["user_id"] and get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Not your org")

    doc = {
        "id": str(uuid.uuid4()),
        "user_org_id": p.user_org_id,
        "user_id": user["user_id"],
        "division_code": p.division_code,
        "sub_team_code": p.sub_team_code,
        "driver_code": p.driver_code,
        "scale_code": p.scale_code,
        "remarks": p.remarks or "",
        "created_at": _now(),
    }
    await db.ss_assessments.insert_one(doc)
    doc.pop("_id", None)
    return {"assessment": doc}


@router.get("/assess/{user_org_id}")
async def get_latest_assessment_matrix(user_org_id: str, user: dict = Depends(get_current_user)):
    """Return latest score per (division, driver) cell for the org."""
    org = await db.user_orgs.find_one({"id": user_org_id})
    if not org:
        raise HTTPException(404, "User-Org not found")
    # pipeline — get latest record per (division, driver) for this org
    rows = await db.ss_assessments.find(
        {"user_org_id": user_org_id, "sub_team_code": None}, {"_id": 0}
    ).sort("created_at", -1).to_list(2000)
    latest: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        key = f"{r['division_code']}|{r['driver_code']}"
        if key not in latest:
            latest[key] = r
    return {"matrix": list(latest.values()), "total_assessments": len(rows)}


@router.get("/assess/{user_org_id}/history")
async def get_assessment_history(user_org_id: str, user: dict = Depends(get_current_user)):
    rows = await db.ss_assessments.find({"user_org_id": user_org_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"history": rows}


@router.get("/assess/{user_org_id}/due")
async def assessment_due_status(user_org_id: str, user: dict = Depends(get_current_user)):
    """Fortnightly cadence: returns due_now=True if last assessment > 14 days ago."""
    latest = await db.ss_assessments.find_one({"user_org_id": user_org_id}, sort=[("created_at", -1)])
    if not latest:
        return {"due_now": True, "last_assessed_at": None, "cadence_days": 14}
    last = latest["created_at"]
    if isinstance(last, str):
        last = datetime.fromisoformat(last.replace("Z", "+00:00"))
    # MongoDB returns offset-naive datetimes; make tz-aware (UTC) for safe subtraction.
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    delta = (_now() - last).days
    return {"due_now": delta >= 14, "days_since_last": delta, "cadence_days": 14, "last_assessed_at": last.isoformat()}


# ─── User Custom Orgs CRUD (Interim layer: Life Area → Org → GEM) ─────
class UserOrgIn(BaseModel):
    name: str
    org_type: str = "BUSINESS"  # references catalog org types
    life_area: str  # the parent life area (e.g. "finance", "business", etc.)
    sub_area: Optional[str] = ""
    description: Optional[str] = ""
    icon: Optional[str] = "business"
    color: Optional[str] = "#4338CA"


@router.post("/orgs")
async def create_user_org(p: UserOrgIn, user: dict = Depends(get_current_user)):
    doc = {
        "id": str(uuid.uuid4()),
        "owner_user_id": user["user_id"],
        "org_id": user.get("org_id"),  # parent SaaS org if any
        **p.model_dump(),
        "created_at": _now(),
        "active": True,
    }
    await db.user_orgs.insert_one(doc)
    doc.pop("_id", None)
    return {"user_org": doc}


@router.get("/orgs")
async def list_user_orgs(life_area: Optional[str] = None, user: dict = Depends(get_current_user)):
    q: Dict[str, Any] = {"owner_user_id": user["user_id"], "active": True}
    if life_area:
        q["life_area"] = life_area
    rows = await db.user_orgs.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"orgs": rows}


@router.get("/orgs/{org_id}")
async def get_user_org(org_id: str, user: dict = Depends(get_current_user)):
    doc = await db.user_orgs.find_one({"id": org_id, "owner_user_id": user["user_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    return doc


@router.put("/orgs/{org_id}")
async def update_user_org(org_id: str, p: UserOrgIn, user: dict = Depends(get_current_user)):
    existing = await db.user_orgs.find_one({"id": org_id, "owner_user_id": user["user_id"]})
    if not existing:
        raise HTTPException(404, "Not found")
    await db.user_orgs.update_one({"id": org_id}, {"$set": p.model_dump()})
    return {"ok": True}


@router.delete("/orgs/{org_id}")
async def delete_user_org(org_id: str, user: dict = Depends(get_current_user)):
    res = await db.user_orgs.update_one(
        {"id": org_id, "owner_user_id": user["user_id"]},
        {"$set": {"active": False}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"ok": True}
