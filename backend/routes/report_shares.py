"""
Report Sharing — Phase 6.

Lets a facilitator share a decision report with others by **email (Resend)** or
**WhatsApp (UltraMsg)**. Recipients receive a secure link that drives them to
log in / sign up; the shared report then appears in their in-app
"Shared with me" section, from where they can view/download it (free).
No PDF is attached to the email/WhatsApp — link only (lead-magnet onboarding).
"""
import os
import re
import uuid
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from core.database import db
from core.auth import get_current_user
from routes.decision_reports import (
    _load_decision,
    _build_pdf,
    _user_timezone,
    _format_local,
    _pdf_payload_for_dezider,
    _pdf_payload_for_pros_cons,
    _pdf_payload_for_swot,
    _pdf_payload_for_solution_finder,
    _pdf_payload_for_assessment,
)

load_dotenv()
logger = logging.getLogger("report_shares")

router = APIRouter(prefix="/shares", tags=["report-shares"])

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM = os.getenv("RESEND_FROM_EMAIL") or "JELCOS AI <reports@updates.veales.in>"
PUBLIC_APP_URL = (os.getenv("PUBLIC_APP_URL") or "https://jelcos.ai").rstrip("/")
ULTRAMSG_INSTANCE = os.getenv("ULTRAMSG_INSTANCE_ID")
ULTRAMSG_TOKEN = os.getenv("ULTRAMSG_API_TOKEN")

MODULE_LABELS = {
    "dezider": "My Dezider",
    "pros_cons": "Pros & Cons",
    "swot": "SWOT",
    "solution_finder": "Solution Finder",
    "assessment": "Decision-Making Style",
}
_BUILDERS = {
    "dezider": _pdf_payload_for_dezider,
    "pros_cons": _pdf_payload_for_pros_cons,
    "swot": _pdf_payload_for_swot,
    "solution_finder": _pdf_payload_for_solution_finder,
    "assessment": _pdf_payload_for_assessment,
}


# ──────────────────────────── helpers ────────────────────────────
def _norm_email(e: Optional[str]) -> Optional[str]:
    e = (e or "").strip().lower()
    return e or None


def _norm_phone(p: Optional[str]) -> Optional[str]:
    digits = re.sub(r"\D", "", p or "")
    return digits or None


async def _user_phone(user_id: str) -> Optional[str]:
    try:
        c = await db.contacts.find_one({"user_id": user_id, "is_self": True}, {"_id": 0})
    except Exception:
        c = None
    for k in ("mobile", "phone", "whatsapp", "mobile_number", "contact_number"):
        if c and c.get(k):
            return _norm_phone(c.get(k))
    return None


async def _send_email(to: str, subject: str, html: str) -> None:
    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY not configured")
    last_err = None
    async with httpx.AsyncClient(timeout=20) as client:
        for attempt in range(3):  # absorb Resend's 2 req/s rate limit
            r = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}",
                         "Content-Type": "application/json"},
                json={"from": RESEND_FROM, "to": [to], "subject": subject, "html": html},
            )
            if r.status_code < 300:
                return
            last_err = f"Resend error {r.status_code}: {r.text[:300]}"
            if r.status_code == 429 and attempt < 2:
                import asyncio
                await asyncio.sleep(0.7 * (attempt + 1))
                continue
            break
    raise RuntimeError(last_err or "Resend error")


async def _send_whatsapp(to: str, body: str) -> None:
    if not (ULTRAMSG_INSTANCE and ULTRAMSG_TOKEN):
        raise RuntimeError("UltraMsg not configured")
    url = f"https://api.ultramsg.com/{ULTRAMSG_INSTANCE}/messages/chat"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, data={"token": ULTRAMSG_TOKEN, "to": to, "body": body})
    if r.status_code >= 300:
        raise RuntimeError(f"UltraMsg error {r.status_code}: {r.text[:300]}")
    try:
        data = r.json()
    except ValueError:
        data = None
    if isinstance(data, dict):
        if data.get("error"):
            raise RuntimeError(f"UltraMsg error: {data.get('error')}")
        # UltraMsg returns {"sent":"false", ...} (no "error" key) when the number
        # isn't on WhatsApp or the instance session is disconnected — that used to
        # be reported as success. Treat it as a real failure so the UI is honest.
        if str(data.get("sent", "true")).lower() in ("false", "0", "none", ""):
            raise RuntimeError(
                f"UltraMsg did not deliver (sent={data.get('sent')}). "
                "Check the recipient number is on WhatsApp and the UltraMsg instance is connected."
            )


def _email_html(owner: str, title: str, module_label: str, link: str) -> str:
    return f"""
<div style="font-family:Helvetica,Arial,sans-serif;max-width:560px;margin:0 auto;color:#1f2937">
  <h2 style="color:#1E40AF;margin-bottom:4px">JELCOS AI</h2>
  <p style="color:#64748b;margin-top:0;font-style:italic">Joyful Executive's Life Choices Operating System — Powered by AI</p>
  <p><b>{owner}</b> has shared a <b>{module_label}</b> decision report with you:</p>
  <p style="font-size:18px;font-weight:700;margin:8px 0">{title}</p>
  <p>Open it in your JELCOS AI account — log in or create a free account, and it will
     appear in your <b>“Shared with me”</b> section to view and download.</p>
  <p style="margin:24px 0">
    <a href="{link}" style="background:#1E40AF;color:#fff;text-decoration:none;
       padding:12px 22px;border-radius:8px;font-weight:700">Open Shared Report</a>
  </p>
  <p style="color:#94a3b8;font-size:12px">If the button doesn't work, paste this link: {link}</p>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0"/>
  <p style="color:#475569;font-size:13px">Best Wishes from
     <a href="https://jelcos.ai" style="color:#1E40AF">JELCOS AI</a></p>
</div>
""".strip()


def _wa_text(owner: str, title: str, module_label: str, link: str) -> str:
    return (
        f"*JELCOS AI*\n_Joyful Executive's Life Choices Operating System — Powered by AI_\n\n"
        f"{owner} has shared a *{module_label}* decision report with you:\n"
        f"*{title}*\n\n"
        f"Open it in your JELCOS AI account (log in or sign up free) — it will appear in "
        f"your *Shared with me* section to view & download:\n{link}\n\n"
        f"Best wishes from JELCOS AI 🙏"
    )


def _share_meta(module: str, raw: dict) -> Dict[str, Any]:
    """Extract life_area + decision_type from a source doc so the recipient's
    'Shared with me' list can offer the same filters as Solution Box."""
    if module == "solution_finder":
        la = raw.get("area_of_life")
    else:
        la = raw.get("life_area") or raw.get("folder")
    return {"life_area": la, "decision_type": raw.get("decision_type")}


def _user_can_access(user: dict, share: dict, phone: Optional[str]) -> bool:
    if share.get("accepted_by_user_id") == user["user_id"]:
        return True
    email = _norm_email(user.get("email"))
    if email and share.get("recipient_email") == email:
        return True
    if phone and share.get("recipient_phone") == phone:
        return True
    return False


# ──────────────────────────── models ────────────────────────────
class ShareCreate(BaseModel):
    module: str
    decision_id: str
    channel: str  # 'email' | 'whatsapp'
    recipient_email: Optional[str] = None
    recipient_phone: Optional[str] = None
    recipient_name: Optional[str] = None


# ──────────────────────────── endpoints ────────────────────────────
@router.post("")
async def create_share(payload: ShareCreate, user: dict = Depends(get_current_user)):
    module = payload.module.lower()
    if module not in MODULE_LABELS:
        raise HTTPException(status_code=400, detail=f"Unknown module: {module}")
    if payload.channel not in ("email", "whatsapp"):
        raise HTTPException(status_code=400, detail="channel must be 'email' or 'whatsapp'")

    # Ownership check — raises 404 if the user does not own this decision.
    info = await _load_decision(module, payload.decision_id, user["user_id"])
    title = info.get("title") or MODULE_LABELS[module]
    meta = _share_meta(module, info.get("raw") or {})

    rec_email = _norm_email(payload.recipient_email)
    rec_phone = _norm_phone(payload.recipient_phone)
    if payload.channel == "email" and not rec_email:
        raise HTTPException(status_code=400, detail="recipient_email required for email")
    if payload.channel == "whatsapp" and not rec_phone:
        raise HTTPException(status_code=400, detail="recipient_phone required for whatsapp")

    token = secrets.token_urlsafe(24)
    owner_name = user.get("name") or "A JELCOS AI user"
    share = {
        "id": str(uuid.uuid4()),
        "token": token,
        "owner_id": user["user_id"],
        "owner_name": owner_name,
        "module": module,
        "module_label": MODULE_LABELS[module],
        "decision_id": payload.decision_id,
        "title": title,
        "channel": payload.channel,
        "recipient_email": rec_email,
        "recipient_phone": rec_phone,
        "recipient_name": payload.recipient_name,
        "life_area": meta.get("life_area"),
        "decision_type": meta.get("decision_type"),
        "status": "pending",
        "accepted_by_user_id": None,
        "sent": False,
        "send_error": None,
        "created_at": datetime.now(timezone.utc),
        "accepted_at": None,
    }
    await db.report_shares.insert_one(share)

    link = f"{PUBLIC_APP_URL}/shared/{token}"
    sent, err = False, None
    try:
        if payload.channel == "email":
            await _send_email(
                rec_email,
                f"{owner_name} shared a {MODULE_LABELS[module]} decision report with you",
                _email_html(owner_name, title, MODULE_LABELS[module], link),
            )
        else:
            await _send_whatsapp(rec_phone, _wa_text(owner_name, title, MODULE_LABELS[module], link))
        sent = True
    except Exception as e:  # don't lose the share if delivery fails
        err = str(e)
        logger.exception("share delivery failed: %s", err)

    await db.report_shares.update_one(
        {"id": share["id"]}, {"$set": {"sent": sent, "send_error": err}}
    )
    return {"ok": True, "sent": sent, "token": token, "link": link, "error": err}


@router.get("/shared-with-me")
async def shared_with_me(user: dict = Depends(get_current_user)):
    email = _norm_email(user.get("email"))
    phone = await _user_phone(user["user_id"])
    ors: List[Dict[str, Any]] = [{"accepted_by_user_id": user["user_id"]}]
    if email:
        ors.append({"recipient_email": email})
    if phone:
        ors.append({"recipient_phone": phone})

    items = []
    async for s in db.report_shares.find({"$or": ors}, {"_id": 0}).sort("created_at", -1):
        if s.get("owner_id") == user["user_id"]:
            continue  # don't show the user's own shares back to them
        created = s.get("created_at")
        la = s.get("life_area")
        dt = s.get("decision_type")
        if la is None and dt is None:  # enrich legacy shares (pre-meta)
            try:
                info = await _load_decision(s["module"], s["decision_id"], s["owner_id"])
                m = _share_meta(s["module"], info.get("raw") or {})
                la, dt = m["life_area"], m["decision_type"]
            except Exception:
                pass
        items.append({
            "token": s.get("token"),
            "module": s.get("module"),
            "module_label": s.get("module_label") or MODULE_LABELS.get(s.get("module"), ""),
            "decision_id": s.get("decision_id"),
            "title": s.get("title"),
            "owner_name": s.get("owner_name"),
            "channel": s.get("channel"),
            "status": s.get("status"),
            "life_area": la,
            "decision_type": dt,
            "created_at": created.isoformat() if isinstance(created, datetime) else created,
        })
    return {"items": items}


@router.get("/{token}")
async def resolve_share(token: str, user: dict = Depends(get_current_user)):
    s = await db.report_shares.find_one({"token": token}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Shared report not found")
    phone = await _user_phone(user["user_id"])
    return {
        "token": token,
        "module": s.get("module"),
        "module_label": s.get("module_label"),
        "title": s.get("title"),
        "owner_name": s.get("owner_name"),
        "can_access": _user_can_access(user, s, phone),
    }


@router.post("/{token}/accept")
async def accept_share(token: str, user: dict = Depends(get_current_user)):
    s = await db.report_shares.find_one({"token": token}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Shared report not found")
    await db.report_shares.update_one(
        {"token": token},
        {"$set": {
            "accepted_by_user_id": user["user_id"],
            "status": "accepted",
            "accepted_at": datetime.now(timezone.utc),
        }},
    )
    return {
        "ok": True,
        "module": s.get("module"),
        "decision_id": s.get("decision_id"),
        "title": s.get("title"),
        "owner_name": s.get("owner_name"),
    }


@router.get("/{token}/report.pdf")
async def shared_report_pdf(token: str, user: dict = Depends(get_current_user)):
    s = await db.report_shares.find_one({"token": token}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Shared report not found")
    phone = await _user_phone(user["user_id"])
    if not _user_can_access(user, s, phone):
        raise HTTPException(status_code=403, detail="This report was not shared with your account")

    # auto-accept on first access so it shows under Shared with me
    if s.get("accepted_by_user_id") != user["user_id"]:
        await db.report_shares.update_one(
            {"token": token},
            {"$set": {"accepted_by_user_id": user["user_id"], "status": "accepted",
                      "accepted_at": datetime.now(timezone.utc)}},
        )

    module = s["module"]
    info = await _load_decision(module, s["decision_id"], s["owner_id"])
    payload = _BUILDERS[module](info["raw"])
    tzname = await _user_timezone(user["user_id"])
    payload["generated_at"] = _format_local(datetime.now(timezone.utc), tzname)
    from routes.app_appearance import get_app_logo
    logo = await get_app_logo()
    pdf = _build_pdf(payload, logo_data_url=logo)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="jelcos_{module}_{s["decision_id"][:8]}.pdf"'},
    )
