"""Admin dashboard pins — lets super-admin mark any admin tile as "Quick Link"
so it appears in a Quick Links group pinned to the top of /admin/index.

Storage: single shared doc `admin_dashboard_pins` (all super-admins see the same
pins). Seeded once with `decider-store` on first read.
"""
from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from core.auth import require_super_admin
from core.database import db

router = APIRouter(tags=["admin-dashboard-pins"])

_DOC_ID = "shared_pins_v1"
_DEFAULT_PINS: List[str] = ["decider-store"]


async def _read_pins() -> List[str]:
    doc = await db.admin_dashboard_pins.find_one({"_id": _DOC_ID}, {"_id": 0, "pinned": 1})
    if not doc:
        await db.admin_dashboard_pins.update_one(
            {"_id": _DOC_ID},
            {"$set": {"pinned": _DEFAULT_PINS}},
            upsert=True,
        )
        return list(_DEFAULT_PINS)
    return list(doc.get("pinned") or [])


@router.get("/admin/dashboard-pins")
async def get_pins(user: dict = Depends(require_super_admin)) -> Dict[str, Any]:
    return {"pinned": await _read_pins()}


@router.put("/admin/dashboard-pins")
async def put_pins(body: Dict[str, Any], user: dict = Depends(require_super_admin)) -> Dict[str, Any]:
    incoming = body.get("pinned") or []
    if not isinstance(incoming, list):
        return {"error": "pinned must be a list of tile keys"}
    # Dedup preserving order, cap at 40
    seen: set = set()
    clean: List[str] = []
    for k in incoming:
        if isinstance(k, str) and k and k not in seen:
            seen.add(k)
            clean.append(k)
            if len(clean) >= 40:
                break
    await db.admin_dashboard_pins.update_one(
        {"_id": _DOC_ID},
        {"$set": {"pinned": clean}},
        upsert=True,
    )
    return {"pinned": clean}
