"""Tiny reusable email sender (Resend) + the public app URL.

Centralises the Resend call so any module (step-sharing, report-sharing, …)
can send transactional email without duplicating the HTTP/retry logic.
"""
import os
import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)

def _get_api_key() -> str:
    return (os.getenv("RESEND_API_KEY") or "").strip()


def _get_from_email() -> str:
    from_val = os.getenv("RESEND_FROM_EMAIL") or "JELCOS AI <reports@updates.veales.in>"
    return from_val.strip("\"'")


PUBLIC_APP_URL = (os.getenv("PUBLIC_APP_URL") or "https://jelcos.ai").rstrip("/")


async def send_email(to: str, subject: str, html: str) -> bool:
    """Send one email via Resend. Returns True on success, False on any failure
    (callers treat email as best-effort and never block the request on it)."""
    api_key = _get_api_key()
    from_email = _get_from_email()
    if not api_key:
        logger.warning("RESEND_API_KEY not configured — skipping email to %s", to)
        return False
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            for attempt in range(3):  # absorb Resend's 2 req/s rate limit
                r = await client.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {api_key}",
                             "Content-Type": "application/json"},
                    json={"from": from_email, "to": [to], "subject": subject, "html": html},
                )
                if r.status_code < 300:
                    logger.info("Email sent successfully to %s: %s", to, r.text[:100])
                    return True
                if r.status_code == 429 and attempt < 2:
                    await asyncio.sleep(0.7 * (attempt + 1))
                    continue
                logger.warning("Resend error %s sending to %s: %s", r.status_code, to, r.text[:200])
                break
    except Exception as e:  # noqa: BLE001
        logger.warning("Email send to %s failed: %s", to, e)
    return False

