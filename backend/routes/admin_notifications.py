"""Admin routes — Notification Engine (Super-Admin).

Generic CRUD over notification *triggers*: each trigger binds a registered
trigger-event key (core/notification_engine.EVENT_REGISTRY) to a schedule
(or an in-code event) + Email/WhatsApp channels with per-channel toggles.
Powers the /admin/notification-engine dashboard.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.auth import require_super_admin
from core import notification_engine as ne

router = APIRouter(prefix="/admin/notification-engine", tags=["admin-notification-engine"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ScheduleIn(BaseModel):
    frequency: str = "weekly"                  # daily | weekly | monthly
    day_of_week: str = "mon"                   # weekly only
    day_of_month: int = Field(1, ge=1, le=28)  # monthly only
    hour: int = Field(9, ge=0, le=23)
    minute: int = Field(0, ge=0, le=59)
    timezone: str = "Asia/Kolkata"


class EmailChannelIn(BaseModel):
    enabled: bool = False
    recipients: List[str] = []


class WhatsAppChannelIn(BaseModel):
    enabled: bool = False
    numbers: List[str] = []


class ChannelsIn(BaseModel):
    email: EmailChannelIn = EmailChannelIn()
    whatsapp: WhatsAppChannelIn = WhatsAppChannelIn()


class TriggerCreate(BaseModel):
    event_key: str
    name: str = Field(..., min_length=2, max_length=120)
    description: Optional[str] = Field(None, max_length=500)
    enabled: bool = True
    schedule: Optional[ScheduleIn] = None
    channels: ChannelsIn = ChannelsIn()
    throttle_minutes: Optional[int] = Field(None, ge=1, le=10080)


class TriggerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    description: Optional[str] = Field(None, max_length=500)
    enabled: Optional[bool] = None
    schedule: Optional[ScheduleIn] = None
    channels: Optional[ChannelsIn] = None
    throttle_minutes: Optional[int] = Field(None, ge=1, le=10080)


def _validate_schedule(s: ScheduleIn) -> Dict[str, Any]:
    if s.frequency not in ne.FREQUENCIES:
        raise HTTPException(400, f"frequency must be one of {ne.FREQUENCIES}")
    if s.day_of_week not in ne.DAYS:
        raise HTTPException(400, f"day_of_week must be one of {ne.DAYS}")
    try:
        ZoneInfo(s.timezone)
    except Exception:
        raise HTTPException(400, f"Unknown timezone '{s.timezone}'")
    return s.model_dump()


def _validate_channels(c: ChannelsIn) -> Dict[str, Any]:
    recipients = []
    for r in c.email.recipients:
        r = (r or "").strip().lower()
        if not r:
            continue
        if not EMAIL_RE.match(r):
            raise HTTPException(400, f"Invalid email address: '{r}'")
        if r not in recipients:
            recipients.append(r)
    numbers = []
    for n in c.whatsapp.numbers:
        digits = re.sub(r"\D", "", n or "")
        if not digits:
            continue
        if len(digits) < 10 or len(digits) > 15:
            raise HTTPException(400, f"Invalid WhatsApp number: '{n}' (expect 10–15 digits incl. country code)")
        if digits not in numbers:
            numbers.append(digits)
    return {"email": {"enabled": c.email.enabled, "recipients": recipients},
            "whatsapp": {"enabled": c.whatsapp.enabled, "numbers": numbers}}


def _present(t: Dict[str, Any]) -> Dict[str, Any]:
    t.pop("_id", None)
    t["schedule_label"] = ne.schedule_label(t.get("schedule"))
    return t


@router.get("/registry")
async def list_registry(admin: dict = Depends(require_super_admin)):
    """Catalogue of available trigger-event keys (pick-list for trigger creation)."""
    return {"events": ne.registry_public()}


@router.get("/triggers")
async def list_triggers(admin: dict = Depends(require_super_admin)):
    rows = await ne.db.notification_triggers.find({}, {"_id": 0}).sort("created_at", 1).to_list(100)
    return {"triggers": [_present(t) for t in rows]}


@router.post("/triggers")
async def create_trigger(body: TriggerCreate, admin: dict = Depends(require_super_admin)):
    entry = ne.EVENT_REGISTRY.get(body.event_key)
    if not entry:
        raise HTTPException(400, f"event_key must be one of {list(ne.EVENT_REGISTRY)}")
    kind = entry["kind"]
    schedule = None
    next_run_at = None
    if kind == "scheduled":
        schedule = _validate_schedule(body.schedule or ScheduleIn(**entry["default_schedule"]))
        next_run_at = ne.compute_next_run(schedule)
    now = datetime.now(timezone.utc)
    doc = {
        "id": uuid.uuid4().hex,
        "event_key": body.event_key,
        "name": body.name.strip(),
        "description": (body.description or entry["description"]).strip(),
        "kind": kind,
        "enabled": body.enabled,
        "schedule": schedule,
        "channels": _validate_channels(body.channels),
        "throttle_minutes": (body.throttle_minutes or 60) if kind == "event" else None,
        "created_at": now, "updated_at": now, "created_by": admin["user_id"],
        "last_run_at": None, "last_status": None, "next_run_at": next_run_at,
    }
    await ne.db.notification_triggers.insert_one(dict(doc))
    return _present(doc)


@router.put("/triggers/{trigger_id}")
async def update_trigger(trigger_id: str, body: TriggerUpdate,
                         admin: dict = Depends(require_super_admin)):
    trig = await ne.db.notification_triggers.find_one({"id": trigger_id}, {"_id": 0})
    if not trig:
        raise HTTPException(404, "Trigger not found")
    updates: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
    if body.name is not None:
        updates["name"] = body.name.strip()
    if body.description is not None:
        updates["description"] = body.description.strip()
    if body.enabled is not None:
        updates["enabled"] = body.enabled
    if body.channels is not None:
        updates["channels"] = _validate_channels(body.channels)
    if body.throttle_minutes is not None and trig["kind"] == "event":
        updates["throttle_minutes"] = body.throttle_minutes
    if body.schedule is not None:
        if trig["kind"] != "scheduled":
            raise HTTPException(400, "Cannot set a schedule on an event-kind trigger")
        updates["schedule"] = _validate_schedule(body.schedule)
        updates["next_run_at"] = ne.compute_next_run(updates["schedule"])
    elif body.enabled and trig["kind"] == "scheduled" and trig.get("schedule") and not trig.get("next_run_at"):
        updates["next_run_at"] = ne.compute_next_run(trig["schedule"])
    await ne.db.notification_triggers.update_one({"id": trigger_id}, {"$set": updates})
    fresh = await ne.db.notification_triggers.find_one({"id": trigger_id}, {"_id": 0})
    return _present(fresh)


@router.delete("/triggers/{trigger_id}")
async def delete_trigger(trigger_id: str, admin: dict = Depends(require_super_admin)):
    r = await ne.db.notification_triggers.delete_one({"id": trigger_id})
    if not r.deleted_count:
        raise HTTPException(404, "Trigger not found")
    return {"deleted": True, "id": trigger_id}


@router.post("/triggers/{trigger_id}/test")
async def test_trigger(trigger_id: str, admin: dict = Depends(require_super_admin)):
    """Send this trigger NOW to its configured recipients (uses sample payload
    for event-kind triggers). Does not affect schedule/throttle state."""
    trig = await ne.db.notification_triggers.find_one({"id": trigger_id}, {"_id": 0})
    if not trig:
        raise HTTPException(404, "Trigger not found")
    run = await ne.run_trigger(trig, run_kind="test")
    return run


@router.get("/runs")
async def list_runs(trigger_id: Optional[str] = None, limit: int = 50,
                    admin: dict = Depends(require_super_admin)):
    q: Dict[str, Any] = {}
    if trigger_id:
        q["trigger_id"] = trigger_id
    rows = await (ne.db.notification_runs.find(q, {"_id": 0})
                  .sort("ts", -1).limit(min(max(limit, 1), ne.RUN_HISTORY_LIMIT)).to_list(ne.RUN_HISTORY_LIMIT))
    return {"runs": rows}
