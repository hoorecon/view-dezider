"""Tiny reusable email sender (Resend) + the public app URL.

Centralises the Resend call so any module (step-sharing, report-sharing, …)
can send transactional email without duplicating the HTTP/retry logic.
"""
import os
import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM = os.getenv("RESEND_FROM_EMAIL") or "JELCOS AI <reports@updates.veales.in>"
PUBLIC_APP_URL = (os.getenv("PUBLIC_APP_URL") or "https://jelcos.ai").rstrip("/")


async def send_email(to: str, subject: str, html: str) -> bool:
    """Send one email via Resend. Returns True on success, False on any failure
    (callers treat email as best-effort and never block the request on it)."""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured — skipping email to %s", to)
        return False
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            for attempt in range(3):  # absorb Resend's 2 req/s rate limit
                r = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {RESEND_API_KEY}",
                             "Content-Type": "application/json"},
                    json={"from": RESEND_FROM, "to": [to], "subject": subject, "html": html},
                )
                if r.status_code < 300:
                    return True
                if r.status_code == 429 and attempt < 2:
                    await asyncio.sleep(0.7 * (attempt + 1))
                    continue
                logger.warning("Resend error %s sending to %s: %s", r.status_code, to, r.text[:200])
                break
    except Exception as e:  # noqa: BLE001
        logger.warning("Email send to %s failed: %s", to, e)
    return False
