"""Video Call Sessions routes (Expert Consultation)"""

import uuid
from datetime import datetime, timezone, timedelta
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

logger = logging.getLogger("video_calls")


def _format_meeting_time(dt: datetime) -> tuple[str, str]:
    """Returns (ist_str, utc_str)"""
    utc_str = dt.strftime("%d %b %Y, %I:%M %p UTC")
    ist_dt = dt + timedelta(hours=5, minutes=30)
    ist_str = ist_dt.strftime("%d %b %Y, %I:%M %p IST")
    return ist_str, utc_str


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
) -> str:
    meeting_title = "Scheduled Expert Consultation" if is_scheduled else "Live Expert Consultation Request"
    badge_bg = "#EDE9FE" if is_scheduled else "#DCFCE7"
    badge_color = "#6D28D9" if is_scheduled else "#15803D"
    badge_text = "Scheduled Meeting" if is_scheduled else "LIVE Consultation"

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
) -> str:
    status_header = "📅 *SCHEDULED CONSULTATION MEETING*" if is_scheduled else "🔴 *LIVE CONSULTATION MEETING REQUEST*"
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
) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1E293B;padding:20px;background:#F8FAFC;">
  <div style="max-width:540px;margin:0 auto;background:#FFF;padding:24px;border-radius:14px;border:1px solid #E2E8F0;">
    <h2 style="color:#5E35B1;margin-top:0;">JELCOS AI Consultation Confirmation</h2>
    <p>Hello {creator_name},</p>
    <p>Your expert consultation meeting with <strong>{expert_name}</strong> has been initiated and meeting invites have been dispatched.</p>
    <div style="background:#F8FAFC;padding:14px;border-radius:10px;margin:16px 0;border:1px solid #E2E8F0;">
      <p style="margin:4px 0;"><strong>Expert:</strong> {expert_name}</p>
      <p style="margin:4px 0;"><strong>Decision:</strong> {decision_title} (Step {step_number})</p>
      <p style="margin:4px 0;"><strong>Date & Time:</strong> {ist_time} ({utc_time})</p>
      <p style="margin:4px 0;"><strong>Duration:</strong> {duration_minutes} Minutes</p>
    </div>
    <p><a href="{room_url}" style="display:inline-block;background:#16A34A;color:#FFF;padding:12px 24px;border-radius:10px;text-decoration:none;font-weight:700;">Open Video Meeting Room</a></p>
    <p style="font-size:12px;color:#64748B;margin-top:16px;">Meeting Link: {room_url}</p>
  </div>
</body>
</html>"""


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
    
    expert_phone = (
        body.get("expert_phone")
        or body.get("expert_whatsapp")
        or (expert.get("whatsapp") if expert else None)
        or (expert.get("phone") if expert else None)
        or (expert.get("mobile") if expert else None)
    )

    if not expert_phone and expert and expert.get("organizations"):
        for org in expert.get("organizations", []):
            if org.get("whatsapp"):
                expert_phone = org.get("whatsapp")
                break
            if org.get("mobile"):
                expert_phone = org.get("mobile")
                break

    if not expert_phone and expert_email:
        u_match = await db.users.find_one({"email": {"$regex": f"^{re.escape(expert_email)}$", "$options": "i"}}, {"_id": 0})
        if u_match:
            expert_phone = u_match.get("whatsapp") or u_match.get("phone") or u_match.get("mobile") or u_match.get("whatsapp_number")
        if not expert_phone:
            c_match = await db.contacts.find_one({"email": {"$regex": f"^{re.escape(expert_email)}$", "$options": "i"}}, {"_id": 0})
            if c_match:
                expert_phone = c_match.get("whatsapp") or c_match.get("mobile") or c_match.get("phone")

    # If client passed phone, save to expert profile for future reuse
    if expert_id and expert_phone:
        await db.experts.update_one(
            {"$or": [{"id": expert_id}, {"expert_id": expert_id}]},
            {"$set": {"whatsapp": expert_phone, "phone": expert_phone}}
        )

    # Determine timing
    now = datetime.now(timezone.utc)
    is_scheduled = False
    meeting_dt = now
    if scheduled_at_raw:
        try:
            parsed_dt = datetime.fromisoformat(str(scheduled_at_raw).replace('Z', '+00:00'))
            if parsed_dt.tzinfo is None:
                parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
            if parsed_dt > now:
                meeting_dt = parsed_dt
                is_scheduled = True
        except Exception:
            pass

    expires_at = meeting_dt + timedelta(minutes=duration_minutes)
    ist_time_str, utc_time_str = _format_meeting_time(meeting_dt)

    room_id = f"prr-{uuid.uuid4().hex[:12]}"
    room_url = f"https://{jitsi_domain}/{room_id}"

    user_doc = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password_hash": 0})
    creator_name = user_doc.get("name", "User") if user_doc else "User"
    creator_email = user_doc.get("email", "") if user_doc else ""
    creator_phone = (user_doc.get("whatsapp") or user_doc.get("phone") or user_doc.get("mobile") or user_doc.get("whatsapp_number")) if user_doc else None

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
        )
        try:
            sent_expert_wa = await send_whatsapp(expert_phone, wa_text)
            logger.info("Expert WhatsApp dispatch to %s: %s", expert_phone, sent_expert_wa)
        except Exception as e:
            logger.warning("Failed to send expert WhatsApp: %s", e)

    # Dispatch User Confirmation Email
    if creator_email and creator_email != expert_email:
        user_email_subj = f"Consultation Meeting Started with {expert_name} — {decision_title}"
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
        )
        try:
            await send_email(creator_email, user_email_subj, user_email_html)
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


@router.get("/call-sessions")
async def list_call_sessions(user: dict = Depends(get_current_user), decision_id: str = None):
    """List call sessions for the current user"""
    query = {"created_by": user["user_id"]}
    if decision_id:
        query["decision_id"] = decision_id
    sessions = await db.call_sessions.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
    return sessions
