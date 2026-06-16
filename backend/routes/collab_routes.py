"""Step-Share Invites & A/V Appointments — generic multi-user collaboration.

Spans 5 modules: conflict-breaker, pros-cons, swot, solution-finder, goal-setter.
(my-dezider already has its own share path.)

KEY DESIGN PRINCIPLES (frozen after Slice D/E confirmation in v3.23 planning)
----------------------------------------------------------------------------
- In-app only (no magic email links). New invitees do an "instant sign-up"
  flow with mandatory WhatsApp number verification before they can submit.
- Each invite has a hard `expires_at`. After expiry, the invitee can still
  view the step in read-only mode and even submit a "late note" — but the
  submission is flagged `late=True` and NOT auto-merged.
- Owner merge action preserves originality:
    - The original invitee response stays IMMUTABLE in `submission`.
    - Owner adds optional `override_notes` (free-form text) when merging.
- Multi-party (CB only): each invite is tied to a `party_id`. Other modules
  use "co-fill" mode: invitees additively contribute rows/items but cannot
  edit owner or other contributors' rows (only their own).
- All notifications go via `core.notify` (Resend email + UltraMsg WhatsApp).

A/V APPOINTMENTS
- Always uses Jitsi room `jitsi-room.tsx`.
- Reminder schedule defaults to [60min, 15min] before; owner-configurable.
- Stored in UTC; UI renders in viewer's local TZ.
- The reminder dispatcher runs from the existing APScheduler tick (see
  `_av_appointment_tick`).
"""
import logging
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Literal, Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, EmailStr

from core.database import db
from core.notify import send_email, send_whatsapp, basic_email
from routes.auth_routes import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/collab", tags=["Collaboration"])


# ============================================================
# Constants
# ============================================================
MODULES = {
    "conflict-breaker": "Conflict Breaker",
    "pros-cons": "Pros & Cons",
    "swot": "SWOT Analysis",
    "solution-finder": "Solution Finder",
    "goal-setter": "Goal Setter",
    "my-dezider": "MyDezider",
}

INVITE_STATUSES = ("pending", "accepted", "submitted", "expired", "cancelled")
APPT_STATUSES = ("scheduled", "completed", "cancelled", "missed")
DEFAULT_INVITE_TTL_HOURS = 72
DEFAULT_REMINDER_OFFSETS_MIN = [60, 15]


# ============================================================
# Pydantic models
# ============================================================
class InviteCreatePayload(BaseModel):
    module: str
    decision_id: str
    step_id: str
    step_label: str
    party_id: Optional[str] = None
    party_label: Optional[str] = None
    invitee_phone: str = Field(..., min_length=8)
    invitee_email: Optional[EmailStr] = None
    invitee_display_name: Optional[str] = None
    expires_at: Optional[datetime] = None
    message: Optional[str] = None  # personal note from owner
    fields: List[str] = Field(default_factory=list)  # which fields the invitee should fill


class InviteSubmitPayload(BaseModel):
    submission: Dict[str, Any]


class InviteMergePayload(BaseModel):
    override_notes: Optional[str] = None


class AppointmentCreatePayload(BaseModel):
    module: str
    decision_id: str
    step_id: Optional[str] = None
    title: str
    scheduled_at: datetime  # accepts ISO-8601, UTC stored
    duration_minutes: int = Field(default=30, ge=5, le=240)
    participants: List[Dict[str, Any]] = Field(default_factory=list)
    reminder_offsets_minutes: List[int] = Field(default_factory=lambda: list(DEFAULT_REMINDER_OFFSETS_MIN))
    notes: Optional[str] = None


# ============================================================
# Helpers
# ============================================================
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_module(module: str) -> None:
    if module not in MODULES:
        raise HTTPException(400, f"Unknown module '{module}'")


async def _resolve_user_to_invite(phone: str) -> Optional[dict]:
    """Find an existing user by phone (normalised) or return None for new sign-up."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    if not digits:
        return None
    # Try a few common phone fields.
    user = await db.users.find_one(
        {"$or": [{"phone": {"$regex": digits + "$"}},
                 {"mobile": {"$regex": digits + "$"}},
                 {"whatsapp": {"$regex": digits + "$"}}]},
        {"_id": 0, "user_id": 1, "email": 1, "name": 1},
    )
    return user


def _public_link(invite_id: str) -> str:
    import os
    base = (os.getenv("PUBLIC_APP_URL") or "https://jelcos.ai").rstrip("/")
    return f"{base}/share/invite/{invite_id}"


# ============================================================
# Step-Share Invite endpoints
# ============================================================
@router.post("/invite")
async def create_invite(payload: InviteCreatePayload, user: dict = Depends(get_current_user)):
    """Owner creates a share invite. Sends WhatsApp + email (if available)."""
    _ensure_module(payload.module)
    invite_id = str(uuid.uuid4())
    expires_at = payload.expires_at or (_now() + timedelta(hours=DEFAULT_INVITE_TTL_HOURS))
    existing_user = await _resolve_user_to_invite(payload.invitee_phone)

    doc = {
        "_id": invite_id,
        "invite_id": invite_id,
        "module": payload.module,
        "module_label": MODULES.get(payload.module, payload.module),
        "decision_id": payload.decision_id,
        "step_id": payload.step_id,
        "step_label": payload.step_label,
        "party_id": payload.party_id,
        "party_label": payload.party_label,
        "fields": payload.fields,
        "invitee_phone": payload.invitee_phone,
        "invitee_email": payload.invitee_email,
        "invitee_display_name": payload.invitee_display_name,
        "invitee_user_id": existing_user["user_id"] if existing_user else None,
        "owner_user_id": user["user_id"],
        "owner_name": user.get("name") or user.get("display_name") or "Someone",
        "message": payload.message,
        "expires_at": expires_at,
        "status": "pending",
        "submission": None,
        "submitted_at": None,
        "submitted_by_user_id": None,
        "merged_at": None,
        "override_notes": None,
        "created_at": _now(),
    }
    await db.collab_invites.insert_one(doc)

    # Best-effort outbound notifications. The link routes to the in-app
    # /share/invite/[id] page which handles login or instant signup.
    link = _public_link(invite_id)
    wa_body = (
        f"{doc['owner_name']} invites you to contribute to '{payload.step_label}' "
        f"in {doc['module_label']} on JELCOS AI.\nOpen: {link}\n"
        f"Expires: {expires_at.strftime('%d %b %Y %H:%M UTC')}"
    )
    notify_results = {"whatsapp": False, "email": False}
    try:
        notify_results["whatsapp"] = await send_whatsapp(payload.invitee_phone, wa_body)
    except Exception as e:
        logger.warning("invite wa send failed: %s", e)
    if payload.invitee_email:
        try:
            html = basic_email(
                f"Invitation: contribute to {payload.step_label}",
                [
                    f"<b>{doc['owner_name']}</b> has invited you to add your input to "
                    f"<i>{payload.step_label}</i> in <b>{doc['module_label']}</b>.",
                    f"This invite expires on <b>{expires_at.strftime('%d %b %Y %H:%M UTC')}</b>.",
                    (payload.message or ""),
                ],
                cta_text="Open invite",
                cta_url=link,
            )
            notify_results["email"] = await send_email(
                payload.invitee_email, f"Invitation: {payload.step_label}", html,
            )
        except Exception as e:
            logger.warning("invite email send failed: %s", e)

    doc.pop("_id", None)
    return {"invite": doc, "notify": notify_results, "link": link}


@router.get("/invite/{invite_id}")
async def get_invite(invite_id: str, user: dict = Depends(get_current_user)):
    """Invitee opens the share link. Either user is the invitee or the owner."""
    inv = await db.collab_invites.find_one({"invite_id": invite_id}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invite not found")
    # Permission: owner OR matching phone OR already-linked invitee_user_id
    is_owner = inv["owner_user_id"] == user["user_id"]
    is_invitee_linked = inv.get("invitee_user_id") == user["user_id"]
    if not (is_owner or is_invitee_linked):
        # Auto-link if the current user's phone matches.
        u_phone = user.get("phone") or user.get("mobile") or ""
        digits = "".join(ch for ch in (u_phone or "") if ch.isdigit())
        inv_digits = "".join(ch for ch in (inv.get("invitee_phone") or "") if ch.isdigit())
        if digits and inv_digits and (digits in inv_digits or inv_digits in digits):
            await db.collab_invites.update_one(
                {"invite_id": invite_id},
                {"$set": {"invitee_user_id": user["user_id"], "status": "accepted"}},
            )
            inv["invitee_user_id"] = user["user_id"]
            inv["status"] = "accepted"
            is_invitee_linked = True
        else:
            raise HTTPException(403, "Not authorized to view this invite")
    # Expiry refresh
    if inv["status"] == "pending" and _now() > inv["expires_at"]:
        await db.collab_invites.update_one({"invite_id": invite_id}, {"$set": {"status": "expired"}})
        inv["status"] = "expired"
    return {"invite": inv, "is_owner": is_owner, "is_invitee": is_invitee_linked}


@router.post("/invite/{invite_id}/submit")
async def submit_invite(invite_id: str, payload: InviteSubmitPayload, user: dict = Depends(get_current_user)):
    inv = await db.collab_invites.find_one({"invite_id": invite_id}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invite not found")
    if inv.get("invitee_user_id") not in (user["user_id"], None):
        raise HTTPException(403, "This invite is bound to another user")
    if inv["status"] in ("cancelled",):
        raise HTTPException(409, f"Invite is {inv['status']}")
    late = _now() > inv["expires_at"]
    await db.collab_invites.update_one(
        {"invite_id": invite_id},
        {"$set": {
            "submission": payload.submission,
            "submitted_at": _now(),
            "submitted_by_user_id": user["user_id"],
            "invitee_user_id": user["user_id"],
            "status": "submitted",
            "late": late,
        }},
    )
    # Notify owner
    try:
        owner = await db.users.find_one({"user_id": inv["owner_user_id"]}, {"_id": 0, "email": 1, "phone": 1, "mobile": 1, "name": 1})
        if owner:
            label = inv.get("party_label") or inv.get("invitee_display_name") or "Contributor"
            wa = f"{label} submitted '{inv['step_label']}' in {inv['module_label']}. Review on JELCOS AI."
            await send_whatsapp(owner.get("phone") or owner.get("mobile") or "", wa)
            if owner.get("email"):
                html = basic_email(
                    f"{label} submitted — {inv['step_label']}",
                    [f"{label} has submitted their contribution to <i>{inv['step_label']}</i>.",
                     "Review & merge from your dashboard."],
                    cta_text="Review submission",
                    cta_url=_public_link(invite_id),
                )
                await send_email(owner["email"], f"{label} submitted: {inv['step_label']}", html)
    except Exception as e:
        logger.warning("owner notify failed: %s", e)
    return {"ok": True, "late": late, "status": "submitted"}


@router.post("/invite/{invite_id}/merge")
async def merge_invite(invite_id: str, payload: InviteMergePayload, user: dict = Depends(get_current_user)):
    """Owner accepts the submission (original preserved + override notes optional)."""
    inv = await db.collab_invites.find_one({"invite_id": invite_id}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invite not found")
    if inv["owner_user_id"] != user["user_id"]:
        raise HTTPException(403, "Only the owner can merge")
    await db.collab_invites.update_one(
        {"invite_id": invite_id},
        {"$set": {
            "status": "merged",
            "merged_at": _now(),
            "override_notes": payload.override_notes,
        }},
    )
    return {"ok": True}


@router.post("/invite/{invite_id}/cancel")
async def cancel_invite(invite_id: str, user: dict = Depends(get_current_user)):
    inv = await db.collab_invites.find_one({"invite_id": invite_id}, {"_id": 0})
    if not inv:
        raise HTTPException(404, "Invite not found")
    if inv["owner_user_id"] != user["user_id"]:
        raise HTTPException(403, "Only the owner can cancel")
    await db.collab_invites.update_one({"invite_id": invite_id}, {"$set": {"status": "cancelled"}})
    return {"ok": True}


@router.get("/invites/owner/{module}/{decision_id}")
async def list_owner_invites(module: str, decision_id: str, user: dict = Depends(get_current_user)):
    _ensure_module(module)
    rows = await db.collab_invites.find(
        {"owner_user_id": user["user_id"], "module": module, "decision_id": decision_id},
        {"_id": 0},
    ).sort("created_at", -1).to_list(200)
    return {"invites": rows}


@router.get("/invites/incoming")
async def list_incoming_invites(user: dict = Depends(get_current_user)):
    rows = await db.collab_invites.find(
        {"invitee_user_id": user["user_id"], "status": {"$in": ["pending", "accepted", "submitted"]}},
        {"_id": 0},
    ).sort("created_at", -1).to_list(100)
    return {"invites": rows}


# ============================================================
# A/V Appointment endpoints
# ============================================================
@router.post("/appointment")
async def create_appointment(payload: AppointmentCreatePayload, user: dict = Depends(get_current_user)):
    _ensure_module(payload.module)
    appt_id = str(uuid.uuid4())
    jitsi_room = f"jelcos-{payload.module}-{secrets.token_urlsafe(6)}"
    doc = {
        "_id": appt_id,
        "appointment_id": appt_id,
        "module": payload.module,
        "module_label": MODULES.get(payload.module, payload.module),
        "decision_id": payload.decision_id,
        "step_id": payload.step_id,
        "title": payload.title,
        "scheduled_at": payload.scheduled_at,
        "duration_minutes": payload.duration_minutes,
        "owner_user_id": user["user_id"],
        "owner_name": user.get("name") or user.get("display_name") or "Owner",
        "participants": payload.participants,
        "jitsi_room": jitsi_room,
        "reminder_offsets_minutes": payload.reminder_offsets_minutes,
        "reminders_sent": [],
        "notes": payload.notes,
        "status": "scheduled",
        "created_at": _now(),
    }
    await db.av_appointments.insert_one(doc)
    # Immediate "appointment scheduled" notification.
    try:
        for p in payload.participants:
            ph = p.get("phone")
            em = p.get("email")
            local_time = payload.scheduled_at.strftime("%d %b %Y %H:%M UTC")
            body = (
                f"{doc['owner_name']} scheduled an A/V call: '{payload.title}' on "
                f"{local_time} ({payload.duration_minutes}min). JELCOS AI."
            )
            if ph:
                await send_whatsapp(ph, body)
            if em:
                html = basic_email(
                    f"Call scheduled: {payload.title}",
                    [f"Scheduled at <b>{local_time}</b> ({payload.duration_minutes} min).",
                     f"Hosted by {doc['owner_name']} in {doc['module_label']}."],
                    cta_text="Join when ready", cta_url=_public_link(appt_id),
                )
                await send_email(em, f"A/V Call scheduled: {payload.title}", html)
    except Exception as e:
        logger.warning("appt notify failed: %s", e)
    doc.pop("_id", None)
    return {"appointment": doc}


@router.get("/appointments/{module}/{decision_id}")
async def list_appointments(module: str, decision_id: str, user: dict = Depends(get_current_user)):
    _ensure_module(module)
    rows = await db.av_appointments.find(
        {"module": module, "decision_id": decision_id,
         "$or": [{"owner_user_id": user["user_id"]},
                 {"participants.user_id": user["user_id"]}]},
        {"_id": 0},
    ).sort("scheduled_at", -1).to_list(50)
    return {"appointments": rows}


@router.post("/appointment/{appt_id}/cancel")
async def cancel_appointment(appt_id: str, user: dict = Depends(get_current_user)):
    a = await db.av_appointments.find_one({"appointment_id": appt_id}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Appointment not found")
    if a["owner_user_id"] != user["user_id"]:
        raise HTTPException(403, "Only owner can cancel")
    await db.av_appointments.update_one({"appointment_id": appt_id}, {"$set": {"status": "cancelled"}})
    return {"ok": True}


# ============================================================
# APScheduler tick — process due reminders
# ============================================================
async def _av_appointment_tick():
    """Called every minute by the existing APScheduler. Sends due reminders."""
    try:
        now = _now()
        scheduled = db.av_appointments.find({"status": "scheduled"}, {"_id": 0})
        async for a in scheduled:
            scheduled_at: datetime = a.get("scheduled_at")
            if not scheduled_at:
                continue
            if scheduled_at.tzinfo is None:
                scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
            offsets = a.get("reminder_offsets_minutes") or list(DEFAULT_REMINDER_OFFSETS_MIN)
            sent = set(a.get("reminders_sent") or [])
            for offset in offsets:
                if offset in sent:
                    continue
                fire_at = scheduled_at - timedelta(minutes=offset)
                if now < fire_at:
                    continue
                # Send reminders to all participants
                for p in (a.get("participants") or []):
                    body = f"Reminder: '{a['title']}' starts in {offset} min."
                    ph = p.get("phone")
                    em = p.get("email")
                    try:
                        if ph:
                            await send_whatsapp(ph, body)
                        if em:
                            html = basic_email(
                                f"Reminder: {a['title']} in {offset} min",
                                [f"Your A/V call starts at <b>{scheduled_at.strftime('%H:%M UTC')}</b>."],
                                cta_text="Join now", cta_url=_public_link(a["appointment_id"]),
                            )
                            await send_email(em, f"Call in {offset} min", html)
                    except Exception as e:
                        logger.warning("reminder send failed: %s", e)
                sent.add(offset)
            await db.av_appointments.update_one(
                {"appointment_id": a["appointment_id"]},
                {"$set": {"reminders_sent": sorted(sent)}},
            )
            # Mark completed/missed once well past end time
            end_at = scheduled_at + timedelta(minutes=a.get("duration_minutes") or 30)
            if now > end_at + timedelta(minutes=30):
                await db.av_appointments.update_one(
                    {"appointment_id": a["appointment_id"]},
                    {"$set": {"status": "completed"}},
                )
    except Exception as e:
        logger.warning("av_appointment_tick: %s", e)
