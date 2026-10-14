"""Video Call Sessions routes (Expert Consultation)"""

import uuid
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user, ADMIN_ROLES
from core.helpers import create_notification

DEFAULT_CALL_DURATION = 30
MIN_CALL_DURATION = 5
MAX_CALL_DURATION = 120

router = APIRouter(tags=["Video Calls"])


@router.get("/call-config")
async def get_call_config():
    """Get admin-configured call settings"""
    config = await db.app_config.find_one({"key": "call_settings"}, {"_id": 0})
    if not config:
        return {
            "min_duration": MIN_CALL_DURATION, "max_duration": MAX_CALL_DURATION,
            "default_duration": DEFAULT_CALL_DURATION, "provider": "jitsi",
            "jitsi_domain": "meet.jit.si",
        }
    return config.get("value", {})


@router.put("/call-config")
async def update_call_config(request: Request, user: dict = Depends(get_current_user)):
    """Update call configuration (admin only)"""
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Admin access required")
    body = await request.json()
    config_value = {
        "min_duration": max(5, min(body.get("min_duration", MIN_CALL_DURATION), 60)),
        "max_duration": max(15, min(body.get("max_duration", MAX_CALL_DURATION), 180)),
        "default_duration": body.get("default_duration", DEFAULT_CALL_DURATION),
        "provider": body.get("provider", "jitsi"),
        "jitsi_domain": body.get("jitsi_domain", "meet.jit.si"),
    }
    await db.app_config.update_one(
        {"key": "call_settings"},
        {"$set": {"key": "call_settings", "value": config_value}},
        upsert=True
    )
    return {"message": "Call config updated", "config": config_value}


import logging
import re
from core.notify import send_email, send_whatsapp, PUBLIC_APP_URL
from core.expert_contacts import _account_phone, choose_notify_phone, verified_whatsapp_for_email

logger = logging.getLogger("video_calls")


def _format_meeting_time(dt: datetime) -> tuple[str, str]:
    """Returns (ist_str, utc_str)"""
    utc_str = dt.strftime("%d %b %Y, %I:%M %p UTC")
    ist_dt = dt + timedelta(hours=5, minutes=30)
    ist_str = ist_dt.strftime("%d %b %Y, %I:%M %p IST")
    return ist_str, utc_str


def _google_calendar_template(title: str, start: datetime, end: datetime, details: str, location: str) -> str:
    """A Google Calendar link that works even when nobody has connected OAuth."""
    def stamp(dt: datetime) -> str:
        aware = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        return aware.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    return (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={quote(title)}"
        f"&dates={stamp(start)}/{stamp(end)}"
        f"&details={quote(details)}"
        f"&location={quote(location)}"
    )


async def _calendar_owner_ids(booker_id: str, expert_email: Optional[str]) -> list:
    ids = []
    if booker_id:
        ids.append(booker_id)
    if expert_email:
        expert_user = await db.users.find_one(
            {"email": {"$regex": f"^{re.escape(expert_email)}$", "$options": "i"}},
            {"_id": 0, "user_id": 1},
        )
        uid = (expert_user or {}).get("user_id")
        if uid and uid not in ids:
            ids.append(uid)
    return ids


async def _sync_appointment_calendar(session_like: dict, action: str) -> dict:
    """Write the appointment onto the connected Google Calendar. Empty dict if nobody is connected."""
    from routes.google_calendar import write_appointment_event

    when = _as_aware(session_like.get("scheduled_at"))
    if not when:
        return {}
    duration = int(session_like.get("duration_minutes") or DEFAULT_CALL_DURATION)
    title = (
        (session_like.get("share_context") or {}).get("decision_title")
        or session_like.get("decision_title")
        or "Expert consultation"
    )
    room = session_like.get("room_url") or ""
    summary = f"JELCOS consultation — {title}"
    description = (
        f"Consultation with {session_like.get('expert_name') or 'Expert'}.\n"
        f"Requested by {session_like.get('creator_name') or 'User'}.\n"
        f"Join: {room}\n"
        f"Reschedule or cancel: {PUBLIC_APP_URL}/expert-appointments"
    )
    owners = await _calendar_owner_ids(session_like.get("created_by") or "", session_like.get("expert_email"))
    attendees = [email for email in [session_like.get("expert_email"), session_like.get("creator_email")] if email]
    try:
        return await write_appointment_event(
            owners,
            event_id=session_like.get("google_calendar_event_id"),
            calendar_owner_id=session_like.get("google_calendar_user_id"),
            action=action,
            summary=summary,
            description=description,
            start=when,
            end=when + timedelta(minutes=duration),
            location=room,
            attendee_emails=attendees,
        )
    except Exception as exc:
        logger.warning("Google Calendar sync failed: %s", exc)
        return {}


def _build_expert_call_email_html(
    expert_name: str,
    creator_name: str,
    creator_email: str,
    decision_title: str,
    step_number: int,
    step_name: str,
    room_url: str,
    duration_minutes: int,
    ist_time: str,
    utc_time: str,
    is_scheduled: bool = False,
    manage_url: str = "",
    calendar_url: str = "",
    calendar_synced: bool = False,
) -> str:
    meeting_title = "Scheduled Expert Consultation" if is_scheduled else "Live Expert Consultation Request"
    badge_bg = "#EDE9FE" if is_scheduled else "#DCFCE7"
    badge_color = "#6D28D9" if is_scheduled else "#15803D"
    badge_text = "Scheduled Meeting" if is_scheduled else "LIVE Consultation"
    manage_block = ""
    if is_scheduled and manage_url:
        manage_block = f"""
              <p style="text-align:center;margin:0 0 8px 0;">
                <a href="{manage_url}" style="display:inline-block;background:#5E35B1;color:#FFFFFF;text-decoration:none;font-size:14px;font-weight:700;padding:10px 18px;border-radius:10px;margin-right:8px;">Reschedule</a>
                <a href="{manage_url}" style="display:inline-block;background:#FFFFFF;color:#DC2626;text-decoration:none;font-size:14px;font-weight:700;padding:10px 18px;border-radius:10px;border:1px solid #FECACA;">Cancel</a>
              </p>
              <p style="text-align:center;font-size:12px;color:#64748B;margin:0 0 20px 0;">Sign in with this expert email address to reschedule or cancel.</p>
"""
    calendar_block = ""
    if calendar_url:
        calendar_label = "Open in Google Calendar" if calendar_synced else "Add to Google Calendar"
        calendar_block = f"""
              <p style="text-align:center;margin:0 0 20px 0;">
                <a href="{calendar_url}" style="display:inline-block;background:#FFFFFF;color:#1A73E8;text-decoration:none;font-size:14px;font-weight:700;padding:10px 18px;border-radius:10px;border:1px solid #BFDBFE;">{calendar_label}</a>
              </p>
"""

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{meeting_title}</title>
</head>
<body style="margin:0;padding:0;background-color:#F8FAFC;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1E293B;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#F8FAFC;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width:580px;background-color:#FFFFFF;border-radius:16px;overflow:hidden;box-shadow:0 4px 6px -1px rgba(0,0,0,0.07);border:1px solid #E2E8F0;" cellspacing="0" cellpadding="0">
          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg, #5E35B1 0%, #7C3AED 100%);padding:28px 24px;text-align:center;">
              <h1 style="margin:0;color:#FFFFFF;font-size:24px;font-weight:800;letter-spacing:0.5px;">JELCOS AI</h1>
              <p style="margin:6px 0 0 0;color:#DDD6FE;font-size:12px;font-weight:500;">Joyful Executive's Life Choices Operating System — Powered by AI</p>
            </td>
          </tr>
          
          <!-- Body Content -->
          <tr>
            <td style="padding:28px 24px;">
              <div style="display:inline-block;background-color:{badge_bg};color:{badge_color};padding:4px 12px;border-radius:999px;font-size:12px;font-weight:700;margin-bottom:16px;">
                {badge_text}
              </div>
              
              <h2 style="margin:0 0 8px 0;font-size:20px;font-weight:700;color:#0F172A;">Hello {expert_name},</h2>
              <p style="margin:0 0 20px 0;font-size:14px;line-height:22px;color:#475569;">
                <strong>{creator_name}</strong> has invited you to an expert consultation session to evaluate and guide a critical decision.
              </p>

              <!-- Meeting Details Card -->
              <table role="presentation" width="100%" style="background-color:#F8FAFC;border-radius:12px;border:1px solid #E2E8F0;margin-bottom:24px;" cellspacing="0" cellpadding="0">
                <tr>
                  <td style="padding:16px 18px;">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                      <tr>
                        <td style="padding:6px 0;font-size:13px;color:#64748B;width:120px;vertical-align:top;"><strong>Topic / Decision:</strong></td>
                        <td style="padding:6px 0;font-size:14px;color:#0F172A;font-weight:600;vertical-align:top;">{decision_title}</td>
                      </tr>
                      <tr>
                        <td style="padding:6px 0;font-size:13px;color:#64748B;vertical-align:top;"><strong>Stage & Step:</strong></td>
                        <td style="padding:6px 0;font-size:13px;color:#0F172A;vertical-align:top;">Step {step_number}: {step_name}</td>
                      </tr>
                      <tr>
                        <td style="padding:6px 0;font-size:13px;color:#64748B;vertical-align:top;"><strong>Requester:</strong></td>
                        <td style="padding:6px 0;font-size:13px;color:#0F172A;vertical-align:top;">{creator_name} {f'({creator_email})' if creator_email else ''}</td>
                      </tr>
                      <tr>
                        <td style="padding:6px 0;font-size:13px;color:#64748B;vertical-align:top;"><strong>Date & Time:</strong></td>
                        <td style="padding:6px 0;font-size:13px;color:#0F172A;font-weight:600;vertical-align:top;">
                          {ist_time}<br><span style="font-size:12px;color:#64748B;font-weight:400;">{utc_time}</span>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:6px 0;font-size:13px;color:#64748B;vertical-align:top;"><strong>Call Duration:</strong></td>
                        <td style="padding:6px 0;font-size:13px;color:#0F172A;font-weight:600;vertical-align:top;">{duration_minutes} Minutes</td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- Action Button -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-bottom:24px;">
                <tr>
                  <td align="center">
                    <a href="{room_url}" target="_blank" style="display:inline-block;background-color:#16A34A;color:#FFFFFF;text-decoration:none;font-size:15px;font-weight:700;padding:14px 32px;border-radius:12px;box-shadow:0 2px 4px rgba(22,163,74,0.25);">
                      🎥 Join Video Call Now
                    </a>
                  </td>
                </tr>
                <tr>
                  <td align="center" style="padding-top:10px;">
                    <p style="margin:0;font-size:12px;color:#64748B;">
                      Direct Link: <a href="{room_url}" target="_blank" style="color:#5E35B1;text-decoration:underline;word-break:break-all;">{room_url}</a>
                    </p>
                  </td>
                </tr>
              </table>

              {manage_block}
              {calendar_block}

              <!-- Joining Instructions -->
              <div style="background-color:#F5F3FF;border-left:4px solid #7C3AED;border-radius:6px;padding:14px 16px;margin-bottom:20px;">
                <h3 style="margin:0 0 8px 0;font-size:13px;font-weight:700;color:#5E35B1;text-transform:uppercase;letter-spacing:0.5px;">Joining Instructions</h3>
                <ol style="margin:0;padding-left:18px;font-size:13px;line-height:20px;color:#334155;">
                  <li style="margin-bottom:4px;">Click the <strong>Join Video Call Now</strong> button or open the link above in Chrome, Safari, Firefox, or Edge.</li>
                  <li style="margin-bottom:4px;">Allow browser camera and microphone permissions when prompted.</li>
                  <li style="margin-bottom:4px;">No app download or account login required — the call opens directly in your browser.</li>
                  <li>Two-way video, audio, and screen sharing are enabled so you can review factors and options in real time.</li>
                </ol>
              </div>

              <p style="margin:0;font-size:12px;color:#94A3B8;line-height:18px;text-align:center;">
                This consultation request was initiated by {creator_name} through JELCOS AI.
              </p>
            </td>
          </tr>
          
          <!-- Footer -->
          <tr>
            <td style="background-color:#F1F5F9;padding:16px 24px;text-align:center;border-top:1px solid #E2E8F0;">
              <p style="margin:0;font-size:11px;color:#64748B;">
                © {datetime.now().year} JELCOS AI · Powered by HOORECON IT-Sys Pvt Ltd
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _build_expert_call_whatsapp_text(
    expert_name: str,
    creator_name: str,
    creator_email: str,
    decision_title: str,
    step_number: int,
    step_name: str,
    room_url: str,
    duration_minutes: int,
    ist_time: str,
    utc_time: str,
    is_scheduled: bool = False,
    manage_url: str = "",
    calendar_url: str = "",
) -> str:
    status_header = "📅 *SCHEDULED CONSULTATION MEETING*" if is_scheduled else "🔴 *LIVE CONSULTATION MEETING REQUEST*"
    manage_block = ""
    if is_scheduled and manage_url:
        manage_block = (
            f"📅 *RESCHEDULE*\n{manage_url}\n\n"
            f"❌ *CANCEL*\n{manage_url}\n\n"
            f"_Sign in with this expert email, then choose the meeting._\n\n"
        )
    calendar_block = f"📅 *GOOGLE CALENDAR:*\n{calendar_url}\n\n" if calendar_url else ""
    return (
        f"🔔 *JELCOS AI — Expert Consultation Request*\n\n"
        f"Hello *{expert_name}*,\n\n"
        f"*{creator_name}* has requested an expert consultation session with you on JELCOS AI.\n\n"
        f"{status_header}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 *Decision Topic:* {decision_title}\n"
        f"🔍 *Stage:* Step {step_number}: {step_name}\n"
        f"👤 *Client:* {creator_name}{f' ({creator_email})' if creator_email else ''}\n"
        f"⏰ *Date & Time:* {ist_time}\n"
        f"     _({utc_time})_\n"
        f"⏳ *Duration:* {duration_minutes} Minutes\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔗 *JOIN VIDEO CALL LINK:*\n"
        f"{room_url}\n\n"
        f"{manage_block}"
        f"{calendar_block}"
        f"📌 *Joining Instructions:*\n"
        f"1. Tap the link above to open the video call directly in your phone or desktop browser.\n"
        f"2. Allow microphone and camera access when prompted.\n"
        f"3. No app installation or login is required.\n"
        f"4. Audio, video, and screen sharing are enabled.\n\n"
        f"_Sent via JELCOS AI Expert Network._"
    )


def _build_user_call_email_html(
    expert_name: str,
    creator_name: str,
    decision_title: str,
    step_number: int,
    step_name: str,
    room_url: str,
    duration_minutes: int,
    ist_time: str,
    utc_time: str,
    is_scheduled: bool = False,
    calendar_url: str = "",
) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1E293B;padding:20px;background:#F8FAFC;">
  <div style="max-width:540px;margin:0 auto;background:#FFF;padding:24px;border-radius:14px;border:1px solid #E2E8F0;">
    <h2 style="color:#5E35B1;margin-top:0;">JELCOS AI Consultation Confirmation</h2>
    <p>Hello {creator_name},</p>
    <p>{"Your appointment with <strong>" + expert_name + "</strong> is booked. The meeting link and time are below." if is_scheduled else "Your expert consultation meeting with <strong>" + expert_name + "</strong> has been initiated and meeting invites have been dispatched."}</p>
    <div style="background:#F8FAFC;padding:14px;border-radius:10px;margin:16px 0;border:1px solid #E2E8F0;">
      <p style="margin:4px 0;"><strong>Expert:</strong> {expert_name}</p>
      <p style="margin:4px 0;"><strong>Decision:</strong> {decision_title} (Step {step_number})</p>
      <p style="margin:4px 0;"><strong>Date & Time:</strong> {ist_time} ({utc_time})</p>
      <p style="margin:4px 0;"><strong>Duration:</strong> {duration_minutes} Minutes</p>
    </div>
    <p><a href="{room_url}" style="display:inline-block;background:#16A34A;color:#FFF;padding:12px 24px;border-radius:10px;text-decoration:none;font-weight:700;">Open Video Meeting Room</a></p>
    {f'<p><a href="{calendar_url}" style="color:#1A73E8;font-weight:700;">Google Calendar</a></p>' if calendar_url else ''}
    <p style="font-size:12px;color:#64748B;margin-top:16px;">Meeting Link: {room_url}</p>
  </div>
</body>
</html>"""


REMINDER_OFFSETS_MIN = (60, 15)
MIN_LEAD_MINUTES = 15


def _parse_future_meeting(raw, now: datetime) -> datetime:
    """Parse an appointment time. It must be at least 15 minutes ahead."""
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(status_code=400, detail="Choose a valid appointment date and time")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    if parsed <= now + timedelta(minutes=MIN_LEAD_MINUTES):
        raise HTTPException(status_code=400, detail="Appointment time must be at least 15 minutes from now")
    return parsed


def _as_aware(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def _build_reschedule_email_html(expert_name, creator_name, decision_title, room_url, old_time, new_time, duration_minutes) -> str:
    return f"""<!DOCTYPE html>
<html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1E293B;padding:20px;background:#F8FAFC;">
  <div style="max-width:540px;margin:0 auto;background:#FFF;padding:24px;border-radius:14px;border:1px solid #E2E8F0;">
    <h2 style="color:#5E35B1;margin-top:0;">Appointment rescheduled</h2>
    <p>The consultation between <strong>{creator_name}</strong> and <strong>{expert_name}</strong> has a new time.</p>
    <p style="margin:4px 0;"><strong>Decision:</strong> {decision_title}</p>
    <p style="margin:4px 0;"><strong>Previous time:</strong> {old_time}</p>
    <p style="margin:4px 0;"><strong>New time:</strong> {new_time}</p>
    <p style="margin:4px 0;"><strong>Duration:</strong> {duration_minutes} minutes</p>
    <p><a href="{room_url}" style="display:inline-block;background:#16A34A;color:#FFF;padding:12px 24px;border-radius:10px;text-decoration:none;font-weight:700;">Open the same meeting link</a></p>
    <p style="font-size:12px;color:#64748B;">The join link has not changed: {room_url}</p>
  </div>
</body></html>"""


def _build_reschedule_whatsapp_text(expert_name, creator_name, decision_title, room_url, old_time, new_time, duration_minutes) -> str:
    return (
        f"📅 *JELCOS AI — Appointment rescheduled*\n\n"
        f"The consultation between *{creator_name}* and *{expert_name}* has moved.\n\n"
        f"📋 *Decision:* {decision_title}\n"
        f"↩️ *Previous time:* {old_time}\n"
        f"✅ *New time:* {new_time}\n"
        f"⏳ *Duration:* {duration_minutes} minutes\n\n"
        f"🔗 *Same join link:*\n{room_url}\n\n"
        f"📅 *RESCHEDULE*\n{PUBLIC_APP_URL}/expert-appointments\n\n"
        f"❌ *CANCEL*\n{PUBLIC_APP_URL}/expert-appointments\n\n"
        f"_Sign in with the expert email, then choose the meeting._\n\n"
        f"_Sent via JELCOS AI Expert Network._"
    )


def _build_cancel_whatsapp_text(expert_name, creator_name, decision_title, when_text) -> str:
    return (
        f"❌ *JELCOS AI — Appointment cancelled*\n\n"
        f"The consultation between *{creator_name}* and *{expert_name}* on *{decision_title}* "
        f"scheduled for {when_text} has been cancelled.\n\n"
        f"_Sent via JELCOS AI Expert Network._"
    )


format_meeting_time = _format_meeting_time
build_expert_call_email_html = _build_expert_call_email_html
build_expert_call_whatsapp_text = _build_expert_call_whatsapp_text
build_user_call_email_html = _build_user_call_email_html


@router.post("/call-sessions")
async def create_call_session(request: Request, user: dict = Depends(get_current_user)):
    """Create a new video call session with an expert and automatically notify via Email and WhatsApp."""
    body = await request.json()
    expert_id = body.get("expert_id")
    decision_id = body.get("decision_id")
    step_number = body.get("step_number", 0)
    step_name = body.get("step_name", f"Step {step_number}")
    decision_title = body.get("decision_title", "")
    duration_minutes = body.get("duration_minutes", DEFAULT_CALL_DURATION)
    scheduled_at_raw = body.get("scheduled_at")

    config = await db.app_config.find_one({"key": "call_settings"}, {"_id": 0})
    config_val = config.get("value", {}) if config else {}
    max_dur = config_val.get("max_duration", MAX_CALL_DURATION)
    min_dur = config_val.get("min_duration", MIN_CALL_DURATION)
    provider = config_val.get("provider", "jitsi")
    jitsi_domain = config_val.get("jitsi_domain", "meet.jit.si")

    duration_minutes = max(min_dur, min(duration_minutes, max_dur))

    expert = None
    if expert_id:
        expert = await db.experts.find_one(
            {"$or": [{"id": expert_id}, {"expert_id": expert_id}], "is_active": True},
            {"_id": 0}
        )
        if not expert:
            expert = await db.platform_experts.find_one(
                {"$or": [{"id": expert_id}, {"expert_id": expert_id}], "is_active": True},
                {"_id": 0}
            )
        if not expert:
            raise HTTPException(status_code=404, detail="Expert not found or inactive")

    # Resolve expert contact details
    expert_name = (expert.get("name") if expert else None) or body.get("expert_name") or "Expert"
    expert_email = body.get("expert_email") or (expert.get("email") if expert else None)
    
    stored_phone = None
    if expert:
        stored_phone = expert.get("whatsapp") or expert.get("phone") or expert.get("mobile")
        if not stored_phone:
            for org in expert.get("organizations") or []:
                stored_phone = org.get("whatsapp") or org.get("mobile")
                if stored_phone:
                    break

    submitted_phone = body.get("expert_phone") or body.get("expert_whatsapp")
    verified_phone = await verified_whatsapp_for_email(expert_email)
    expert_phone = choose_notify_phone(submitted_phone, stored_phone, verified_phone)

    if not expert_phone and expert_email:
        u_match = await db.users.find_one({"email": {"$regex": f"^{re.escape(expert_email)}$", "$options": "i"}}, {"_id": 0})
        if u_match:
            expert_phone = u_match.get("whatsapp_number") or u_match.get("whatsapp") or u_match.get("phone") or u_match.get("mobile")
        if not expert_phone:
            c_match = await db.contacts.find_one({"email": {"$regex": f"^{re.escape(expert_email)}$", "$options": "i"}}, {"_id": 0})
            if c_match:
                expert_phone = c_match.get("whatsapp") or c_match.get("mobile") or c_match.get("phone")

    # Determine timing
    now = datetime.now(timezone.utc)
    is_scheduled = False
    meeting_dt = now
    if scheduled_at_raw:
        meeting_dt = _parse_future_meeting(scheduled_at_raw, now)
        is_scheduled = True

    expires_at = meeting_dt + timedelta(minutes=duration_minutes)
    ist_time_str, utc_time_str = _format_meeting_time(meeting_dt)

    room_id = f"prr-{uuid.uuid4().hex[:12]}"
    room_url = f"https://{jitsi_domain}/{room_id}"

    user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password_hash": 0})
    creator_name = user_doc.get("name", "User") if user_doc else "User"
    creator_email = user_doc.get("email", "") if user_doc else ""
    creator_phone = _account_phone(user_doc)

    calendar_link = ""
    calendar_synced = False
    calendar_event_id = ""
    calendar_owner_id = ""
    if is_scheduled:
        calendar_draft = {
            "scheduled_at": meeting_dt.isoformat(),
            "duration_minutes": duration_minutes,
            "decision_title": decision_title,
            "room_url": room_url,
            "expert_name": expert_name,
            "expert_email": expert_email,
            "creator_name": creator_name,
            "creator_email": creator_email,
            "created_by": user["user_id"],
        }
        calendar_result = await _sync_appointment_calendar(calendar_draft, "create")
        calendar_event_id = calendar_result.get("event_id") or ""
        calendar_owner_id = calendar_result.get("owner_user_id") or ""
        calendar_synced = bool(calendar_event_id)
        calendar_link = calendar_result.get("html_link") or _google_calendar_template(
            f"JELCOS consultation — {decision_title or 'Expert consultation'}",
            meeting_dt,
            meeting_dt + timedelta(minutes=duration_minutes),
            f"Join: {room_url}\nReschedule or cancel: {PUBLIC_APP_URL}/expert-appointments",
            room_url,
        )

    # Dispatch Email to Expert
    sent_expert_email = False
    if expert_email:
        email_subj = f"{'Scheduled' if is_scheduled else 'Live'} Consultation with {creator_name} — {decision_title}"
        email_html = _build_expert_call_email_html(
            expert_name=expert_name,
            creator_name=creator_name,
            creator_email=creator_email,
            decision_title=decision_title,
            step_number=step_number,
            step_name=step_name,
            room_url=room_url,
            duration_minutes=duration_minutes,
            ist_time=ist_time_str,
            utc_time=utc_time_str,
            is_scheduled=is_scheduled,
            manage_url=f"{PUBLIC_APP_URL}/expert-appointments" if is_scheduled else "",
            calendar_url=calendar_link,
            calendar_synced=calendar_synced,
        )
        try:
            sent_expert_email = await send_email(expert_email, email_subj, email_html)
            logger.info("Expert email dispatch to %s: %s", expert_email, sent_expert_email)
        except Exception as e:
            logger.warning("Failed to send expert email: %s", e)

    # Dispatch WhatsApp to Expert
    sent_expert_wa = False
    if expert_phone:
        wa_text = _build_expert_call_whatsapp_text(
            expert_name=expert_name,
            creator_name=creator_name,
            creator_email=creator_email,
            decision_title=decision_title,
            step_number=step_number,
            step_name=step_name,
            room_url=room_url,
            duration_minutes=duration_minutes,
            ist_time=ist_time_str,
            utc_time=utc_time_str,
            is_scheduled=is_scheduled,
            manage_url=f"{PUBLIC_APP_URL}/expert-appointments" if is_scheduled else "",
            calendar_url=calendar_link,
        )
        try:
            sent_expert_wa = await send_whatsapp(expert_phone, wa_text)
            logger.info("Expert WhatsApp dispatch to %s: %s", expert_phone, sent_expert_wa)
        except Exception as e:
            logger.warning("Failed to send expert WhatsApp: %s", e)

    # Dispatch User Confirmation Email
    if creator_email and creator_email != expert_email:
        user_email_subj = (
            f"Appointment booked with {expert_name} — {decision_title}"
            if is_scheduled else
            f"Consultation Meeting Started with {expert_name} — {decision_title}"
        )
        user_email_html = _build_user_call_email_html(
            expert_name=expert_name,
            creator_name=creator_name,
            decision_title=decision_title,
            step_number=step_number,
            step_name=step_name,
            room_url=room_url,
            duration_minutes=duration_minutes,
            ist_time=ist_time_str,
            utc_time=utc_time_str,
            is_scheduled=is_scheduled,
            calendar_url=calendar_link,
        )
        try:
            await send_email(creator_email, user_email_subj, user_email_html)
        except Exception:
            pass

    if is_scheduled and creator_phone and creator_phone != expert_phone:
        caller_wa = _build_expert_call_whatsapp_text(
            expert_name=expert_name,
            creator_name=creator_name,
            creator_email=creator_email,
            decision_title=decision_title,
            step_number=step_number,
            step_name=step_name,
            room_url=room_url,
            duration_minutes=duration_minutes,
            ist_time=ist_time_str,
            utc_time=utc_time_str,
            is_scheduled=True,
        )
        if calendar_link:
            caller_wa += f"\n\n📅 Google Calendar:\n{calendar_link}"
        try:
            await send_whatsapp(creator_phone, caller_wa)
        except Exception:
            pass

    session_doc = {
        "id": str(uuid.uuid4()), "room_id": room_id, "room_url": room_url,
        "provider": provider, "created_by": user["user_id"],
        "creator_name": creator_name,
        "creator_email": creator_email,
        "expert_id": expert_id,
        "expert_name": expert_name,
        "expert_email": expert_email,
        "expert_phone": expert_phone,
        "decision_id": decision_id,
        "step_number": step_number,
        "step_name": step_name,
        "duration_minutes": duration_minutes,
        "status": "scheduled" if is_scheduled else "active",
        "is_scheduled": is_scheduled,
        "scheduled_at": meeting_dt.isoformat(),
        "created_at": now, "expires_at": expires_at, "ended_at": None,
        "notified_email": sent_expert_email,
        "notified_whatsapp": sent_expert_wa,
        "creator_phone": creator_phone,
        "reminders_sent": [],
        "reschedule_history": [],
        "google_calendar_event_id": calendar_event_id,
        "google_calendar_link": calendar_link,
        "google_calendar_user_id": calendar_owner_id,
        "google_calendar_synced": calendar_synced,
        "share_context": {
            "decision_title": decision_title,
            "step_data": body.get("step_data"),
        },
    }

    await db.call_sessions.insert_one(session_doc)

    # In-app notification
    if expert_email:
        notif = {
            "id": str(uuid.uuid4()),
            "user_email": expert_email,
            "type": "call_invitation",
            "title": f"Call Request from {creator_name}",
            "body": f"Step {step_number}: {step_name} - {decision_title}",
            "data": {
                "room_url": room_url, "session_id": session_doc["id"],
                "duration_minutes": duration_minutes, "expires_at": expires_at.isoformat(),
            },
            "read": False, "created_at": now,
        }
        await db.notifications.insert_one(notif)

    return {
        "session_id": session_doc["id"],
        "room_id": room_id,
        "room_url": room_url,
        "provider": provider,
        "duration_minutes": duration_minutes,
        "expires_at": expires_at.isoformat(),
        "notified_email": sent_expert_email,
        "notified_whatsapp": sent_expert_wa,
        "expert_name": expert_name,
        "expert_email": expert_email,
        "expert_phone": expert_phone,
        "is_scheduled": is_scheduled,
        "scheduled_at": meeting_dt.isoformat(),
        "status": "scheduled" if is_scheduled else "active",
        "google_calendar_link": calendar_link,
        "google_calendar_synced": calendar_synced,
    }


@router.post("/call-sessions/{session_id}/resend-invite")
async def resend_call_invitation(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Resend meeting invitation email and WhatsApp to the expert."""
    session = await db.call_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Call session not found")

    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    expert_email = body.get("expert_email") or session.get("expert_email")
    expert_phone = body.get("expert_phone") or session.get("expert_phone")
    expert_name = session.get("expert_name") or "Expert"
    creator_name = session.get("creator_name") or "User"
    creator_email = session.get("creator_email") or ""
    decision_title = session.get("share_context", {}).get("decision_title") or "Decision Consultation"
    step_number = session.get("step_number", 0)
    step_name = session.get("step_name", "")
    room_url = session.get("room_url", "")
    duration_minutes = session.get("duration_minutes", 30)

    now = datetime.now(timezone.utc)
    ist_time_str, utc_time_str = _format_meeting_time(now)

    sent_email = False
    if expert_email:
        email_subj = f"Consultation Meeting Link from {creator_name} — {decision_title}"
        email_html = _build_expert_call_email_html(
            expert_name=expert_name,
            creator_name=creator_name,
            creator_email=creator_email,
            decision_title=decision_title,
            step_number=step_number,
            step_name=step_name,
            room_url=room_url,
            duration_minutes=duration_minutes,
            ist_time=ist_time_str,
            utc_time=utc_time_str,
            is_scheduled=session.get("is_scheduled", False),
        )
        sent_email = await send_email(expert_email, email_subj, email_html)

    sent_wa = False
    if expert_phone:
        wa_text = _build_expert_call_whatsapp_text(
            expert_name=expert_name,
            creator_name=creator_name,
            creator_email=creator_email,
            decision_title=decision_title,
            step_number=step_number,
            step_name=step_name,
            room_url=room_url,
            duration_minutes=duration_minutes,
            ist_time=ist_time_str,
            utc_time=utc_time_str,
            is_scheduled=session.get("is_scheduled", False),
            manage_url=f"{PUBLIC_APP_URL}/expert-appointments" if session.get("is_scheduled") else "",
            calendar_url=session.get("google_calendar_link") or "",
        )
        sent_wa = await send_whatsapp(expert_phone, wa_text)

    await db.call_sessions.update_one(
        {"id": session_id},
        {"$set": {
            "expert_email": expert_email,
            "expert_phone": expert_phone,
            "notified_email": sent_email or session.get("notified_email", False),
            "notified_whatsapp": sent_wa or session.get("notified_whatsapp", False),
        }}
    )

    return {
        "message": "Invitation resent",
        "sent_email": sent_email,
        "sent_whatsapp": sent_wa,
        "expert_email": expert_email,
        "expert_phone": expert_phone,
    }


@router.get("/call-sessions/{session_id}")
async def get_call_session(session_id: str, user: dict = Depends(get_current_user)):
    """Get call session details"""
    session = await db.call_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("expires_at"):
        expires_at = session["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        elif expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            if session["status"] == "active":
                await db.call_sessions.update_one({"id": session_id}, {"$set": {"status": "expired"}})
                session["status"] = "expired"
    return session


@router.put("/call-sessions/{session_id}/end")
async def end_call_session(session_id: str, user: dict = Depends(get_current_user)):
    """End a call session"""
    result = await db.call_sessions.update_one(
        {"id": session_id},
        {"$set": {"status": "ended", "ended_at": datetime.now(timezone.utc)}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Call session ended"}


def _session_when(session) -> Optional[datetime]:
    return _as_aware(session.get("scheduled_at")) or _as_aware(session.get("created_at"))


async def _profile_phone(user_id: Optional[str] = None, email: Optional[str] = None) -> Optional[str]:
    """Verified profile WhatsApp, then any number saved on the account."""
    fields = {"_id": 0, "whatsapp_number": 1, "whatsapp_verified": 1, "whatsapp": 1, "phone": 1, "mobile": 1}
    user = None
    if user_id:
        user = await db.users.find_one({"user_id": user_id}, fields)
    if not _account_phone(user) and email:
        user = await db.users.find_one(
            {"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}},
            fields,
        )
    return _account_phone(user)


async def _party_phone(stored: Optional[str], user_id: Optional[str] = None, email: Optional[str] = None) -> Optional[str]:
    """Use the number saved on the appointment, or the person's current profile number."""
    if stored:
        return stored
    return await _profile_phone(user_id, email)


async def _session_phones(session: dict) -> tuple[Optional[str], Optional[str]]:
    """Expert phone, then the booker's phone. Fills a missing number from the profile."""
    expert_phone = await _party_phone(session.get("expert_phone"), None, session.get("expert_email"))
    creator_phone = await _party_phone(session.get("creator_phone"), session.get("created_by"), session.get("creator_email"))
    updates = {}
    if creator_phone and not session.get("creator_phone"):
        updates["creator_phone"] = creator_phone
    if expert_phone and not session.get("expert_phone"):
        updates["expert_phone"] = expert_phone
    if updates and session.get("id"):
        await db.call_sessions.update_one({"id": session["id"]}, {"$set": updates})
        session.update(updates)
    return expert_phone, creator_phone


async def _notify_party(email: Optional[str], phone: Optional[str], subject: str, html: str, wa_text: str) -> None:
    if email:
        try:
            await send_email(email, subject, html)
        except Exception as exc:
            logger.warning("Appointment email failed: %s", exc)
    if phone:
        try:
            sent = await send_whatsapp(phone, wa_text)
            if not sent:
                logger.warning("Appointment WhatsApp was not accepted for %s", phone[-4:])
        except Exception as exc:
            logger.warning("Appointment WhatsApp failed: %s", exc)
    else:
        logger.warning("Appointment WhatsApp skipped: no phone for %s", email or "unknown")


def _can_manage_session(session: dict, user: dict) -> bool:
    if session.get("created_by") == user.get("user_id"):
        return True
    expert_email = (session.get("expert_email") or "").strip().lower()
    user_email = (user.get("email") or "").strip().lower()
    return bool(expert_email and user_email and expert_email == user_email)


@router.post("/call-sessions/{session_id}/cancel")
async def cancel_call_session(session_id: str, user: dict = Depends(get_current_user)):
    """Cancel a future appointment and tell the expert."""
    session = await db.call_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not _can_manage_session(session, user):
        raise HTTPException(status_code=403, detail="Only the person who booked this appointment, or the expert, can cancel it")
    when = _session_when(session)
    now = datetime.now(timezone.utc)
    if when and when <= now:
        raise HTTPException(status_code=400, detail="This appointment has already started")

    await _sync_appointment_calendar(session, "delete")
    await db.call_sessions.update_one(
        {"id": session_id},
        {"$set": {"status": "cancelled", "cancelled_at": now, "reminders_sent": ["cancelled"], "google_calendar_event_id": ""}},
    )
    ist_time, _utc_time = _format_meeting_time(when or now)
    title = (session.get("share_context") or {}).get("decision_title") or "Decision Consultation"
    expert_name = session.get("expert_name") or "Expert"
    creator_name = session.get("creator_name") or "User"
    html = f"""<div style="font-family:Helvetica,Arial,sans-serif;color:#1E293B">
      <h2 style="color:#5E35B1">Appointment cancelled</h2>
      <p>The consultation between <strong>{creator_name}</strong> and <strong>{expert_name}</strong>
      on <strong>{title}</strong> scheduled for {ist_time} has been cancelled.</p>
    </div>"""
    wa = _build_cancel_whatsapp_text(expert_name, creator_name, title, ist_time)
    expert_phone, creator_phone = await _session_phones(session)
    await _notify_party(session.get("expert_email"), expert_phone, f"Appointment cancelled — {title}", html, wa)
    await _notify_party(session.get("creator_email"), creator_phone, f"Appointment cancelled — {title}", html, wa)
    return {"message": "Appointment cancelled", "session_id": session_id}


@router.post("/call-sessions/{session_id}/reschedule")
async def reschedule_call_session(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Move a future appointment. The join link stays the same."""
    session = await db.call_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not _can_manage_session(session, user):
        raise HTTPException(status_code=403, detail="Only the person who booked this appointment, or the expert, can reschedule it")

    body = await request.json()
    now = datetime.now(timezone.utc)
    current = _session_when(session)
    if current and current <= now:
        raise HTTPException(status_code=400, detail="This appointment has already started")

    new_dt = _parse_future_meeting(body.get("scheduled_at"), now)
    config = await db.app_config.find_one({"key": "call_settings"}, {"_id": 0})
    config_val = config.get("value", {}) if config else {}
    max_dur = config_val.get("max_duration", MAX_CALL_DURATION)
    min_dur = config_val.get("min_duration", MIN_CALL_DURATION)
    duration_minutes = body.get("duration_minutes") or session.get("duration_minutes") or DEFAULT_CALL_DURATION
    duration_minutes = max(min_dur, min(int(duration_minutes), max_dur))

    old_ist, _old_utc = _format_meeting_time(current or now)
    new_ist, new_utc = _format_meeting_time(new_dt)
    title = (session.get("share_context") or {}).get("decision_title") or "Decision Consultation"
    expert_name = session.get("expert_name") or "Expert"
    creator_name = session.get("creator_name") or "User"
    room_url = session.get("room_url") or ""
    html = _build_reschedule_email_html(expert_name, creator_name, title, room_url, old_ist, new_ist, duration_minutes)
    wa = _build_reschedule_whatsapp_text(expert_name, creator_name, title, room_url, old_ist, new_ist, duration_minutes)
    subject = f"Appointment rescheduled — {title}"
    expert_phone, creator_phone = await _session_phones(session)
    await _notify_party(session.get("expert_email"), expert_phone, subject, html, wa)
    await _notify_party(session.get("creator_email"), creator_phone, subject, html, wa)

    history = {
        "from": (current or now).isoformat(),
        "to": new_dt.isoformat(),
        "by": user["user_id"],
        "at": now.isoformat(),
    }
    updated_session = {
        **session,
        "scheduled_at": new_dt.isoformat(),
        "duration_minutes": duration_minutes,
        "decision_title": title,
    }
    calendar_result = await _sync_appointment_calendar(
        updated_session,
        "update" if session.get("google_calendar_event_id") else "create",
    )
    calendar_fields = {}
    if calendar_result.get("event_id"):
        calendar_fields = {
            "google_calendar_event_id": calendar_result["event_id"],
            "google_calendar_link": calendar_result.get("html_link") or session.get("google_calendar_link") or "",
            "google_calendar_user_id": calendar_result.get("owner_user_id") or session.get("google_calendar_user_id") or "",
            "google_calendar_synced": True,
        }
    await db.call_sessions.update_one(
        {"id": session_id},
        {
            "$set": {
                "scheduled_at": new_dt.isoformat(),
                "expires_at": new_dt + timedelta(minutes=duration_minutes),
                "duration_minutes": duration_minutes,
                "reminders_sent": [],
                "updated_at": now,
                **calendar_fields,
            },
            "$push": {"reschedule_history": history},
        },
    )
    return {
        "message": "Appointment rescheduled",
        "session_id": session_id,
        "scheduled_at": new_dt.isoformat(),
        "scheduled_at_label": f"{new_ist} ({new_utc})",
        "duration_minutes": duration_minutes,
        "room_url": room_url,
        "google_calendar_link": calendar_fields.get("google_calendar_link") or session.get("google_calendar_link") or "",
    }


async def tick_call_session_reminders() -> int:
    """Send the 60-minute and 15-minute reminders for scheduled expert calls."""
    now = datetime.now(timezone.utc)
    sent_count = 0
    cursor = db.call_sessions.find({"status": "scheduled", "is_scheduled": True}, {"_id": 0})
    async for session in cursor:
        when = _session_when(session)
        if not when or when <= now:
            continue
        already = set(str(item) for item in (session.get("reminders_sent") or []))
        due = []
        for offset in REMINDER_OFFSETS_MIN:
            if str(offset) in already:
                continue
            if now >= when - timedelta(minutes=offset):
                due.append(offset)
        if not due:
            continue
        ist_time, utc_time = _format_meeting_time(when)
        title = (session.get("share_context") or {}).get("decision_title") or "Decision Consultation"
        expert_name = session.get("expert_name") or "Expert"
        creator_name = session.get("creator_name") or "User"
        room_url = session.get("room_url") or ""
        soonest = min(due)
        subject = f"Reminder: consultation in {soonest} minutes — {title}"
        html = _build_user_call_email_html(
            expert_name=expert_name,
            creator_name=creator_name,
            decision_title=title,
            step_number=session.get("step_number") or 0,
            step_name=session.get("step_name") or "",
            room_url=room_url,
            duration_minutes=session.get("duration_minutes") or 30,
            ist_time=ist_time,
            utc_time=utc_time,
            is_scheduled=True,
        )
        wa = (
            f"⏰ *JELCOS AI reminder*\n\n"
            f"Your consultation on *{title}* with *{expert_name}* starts in *{soonest} minutes*.\n"
            f"⏰ {ist_time}\n\n"
            f"🔗 Join:\n{room_url}"
        )
        expert_phone, creator_phone = await _session_phones(session)
        await _notify_party(session.get("expert_email"), expert_phone, subject, html, wa)
        await _notify_party(session.get("creator_email"), creator_phone, subject, html, wa)
        await db.call_sessions.update_one(
            {"id": session["id"]},
            {"$set": {"reminders_sent": list(already.union(str(offset) for offset in due))}},
        )
        sent_count += 1
    return sent_count


@router.get("/call-sessions")
async def list_call_sessions(user: dict = Depends(get_current_user), decision_id: str = None, role: str = None):
    """List call sessions for the booker, or for the signed-in expert."""
    if role == "expert":
        email = (user.get("email") or "").strip()
        query = {
            "status": "scheduled",
            "is_scheduled": True,
            "expert_email": {"$regex": f"^{re.escape(email)}$", "$options": "i"},
        }
    else:
        query = {"created_by": user["user_id"]}
        if decision_id:
            query["decision_id"] = decision_id
    sessions = await db.call_sessions.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
    return sessions
