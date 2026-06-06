"""Reusable best-effort notifications (Resend email + UltraMsg WhatsApp).

Used for subscription dunning / lifecycle alerts. All functions are best-effort:
failures are logged, never raised, so they don't break the calling flow.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional

import httpx
from dotenv import load_dotenv

from core.database import db

load_dotenv()
log = logging.getLogger("notify")

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM = os.getenv("RESEND_FROM_EMAIL") or "JELCOS AI <reports@updates.veales.in>"
ULTRAMSG_INSTANCE = os.getenv("ULTRAMSG_INSTANCE_ID")
ULTRAMSG_TOKEN = os.getenv("ULTRAMSG_API_TOKEN")
PUBLIC_APP_URL = (os.getenv("PUBLIC_APP_URL") or "https://jelcos.ai").rstrip("/")


def _norm_phone(p: Optional[str]) -> Optional[str]:
    digits = re.sub(r"\D", "", p or "")
    return digits or None


async def send_email(to: str, subject: str, html: str) -> bool:
    if not (RESEND_API_KEY and to):
        return False
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            for attempt in range(3):
                r = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
                    json={"from": RESEND_FROM, "to": [to], "subject": subject, "html": html},
                )
                if r.status_code < 300:
                    return True
                if r.status_code == 429 and attempt < 2:
                    import asyncio
                    await asyncio.sleep(0.7 * (attempt + 1))
                    continue
                log.warning(f"Resend error {r.status_code}: {r.text[:200]}")
                break
    except Exception as e:
        log.warning(f"send_email failed: {str(e)[:160]}")
    return False


async def send_whatsapp(phone: str, body: str) -> bool:
    phone = _norm_phone(phone)
    if not (ULTRAMSG_INSTANCE and ULTRAMSG_TOKEN and phone):
        return False
    try:
        url = f"https://api.ultramsg.com/{ULTRAMSG_INSTANCE}/messages/chat"
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(url, data={"token": ULTRAMSG_TOKEN, "to": phone, "body": body})
        return r.status_code < 300
    except Exception as e:
        log.warning(f"send_whatsapp failed: {str(e)[:160]}")
    return False


async def _lookup_contact(user_id: str) -> tuple[Optional[str], Optional[str], str]:
    """Return (email, phone, name) for a user from users + contacts collections."""
    email = phone = None
    name = ""
    try:
        u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "email": 1, "name": 1, "phone": 1, "mobile": 1})
        if u:
            email = u.get("email")
            name = u.get("name") or ""
            phone = u.get("phone") or u.get("mobile")
    except Exception:
        pass
    if not phone:
        try:
            c = await db.contacts.find_one({"user_id": user_id, "is_self": True}, {"_id": 0})
            for k in ("mobile", "phone", "whatsapp", "mobile_number", "contact_number"):
                if c and c.get(k):
                    phone = c.get(k)
                    break
            if c and not name:
                name = c.get("name") or ""
        except Exception:
            pass
    return email, phone, name


def basic_email(title: str, lines: list, cta_text: str = "Open JELCOS AI", cta_url: str = "") -> str:
    cta_url = cta_url or PUBLIC_APP_URL
    body = "".join(f'<p style="margin:8px 0;color:#374151">{ln}</p>' for ln in lines)
    return f"""
<div style="font-family:Helvetica,Arial,sans-serif;max-width:560px;margin:0 auto;color:#1f2937">
  <h2 style="color:#5E35B1;margin-bottom:2px">JELCOS AI</h2>
  <p style="color:#64748b;margin-top:0;font-style:italic">Leaders' Operating System — Powered by AI</p>
  <h3 style="margin:16px 0 6px">{title}</h3>
  {body}
  <a href="{cta_url}" style="display:inline-block;margin-top:14px;background:#5E35B1;color:#fff;
     text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:700">{cta_text}</a>
  <p style="color:#94a3b8;font-size:12px;margin-top:18px">This is an automated message from JELCOS AI.</p>
</div>"""


async def notify_user(user_id: str, subject: str, email_lines: list, wa_body: str,
                      cta_text: str = "Manage subscription", cta_url: str = "") -> dict:
    """Send both email + WhatsApp to a user, best-effort. Returns delivery status."""
    email, phone, name = await _lookup_contact(user_id)
    html = basic_email(subject, email_lines, cta_text, cta_url)
    sent_email = await send_email(email, subject, html) if email else False
    sent_wa = await send_whatsapp(phone, wa_body) if phone else False
    return {"email": sent_email, "whatsapp": sent_wa, "to_email": email, "to_phone": bool(phone)}
