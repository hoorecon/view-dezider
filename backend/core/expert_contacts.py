"""Resolve the WhatsApp number and email used for expert meeting notices.

The number saved on an expert record can lag the account profile. When the
expert email matches a user who verified WhatsApp on their profile, that
verified number is the one shown in Call an Expert and used for the notice.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, Optional

from core.database import db


def phone_key(value: Optional[str]) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 10:
        return "91" + digits
    return digits


def _account_phone(user: Optional[dict]) -> Optional[str]:
    if not user:
        return None
    if user.get("whatsapp_verified") and user.get("whatsapp_number"):
        return user["whatsapp_number"]
    return (
        user.get("whatsapp_number")
        or user.get("whatsapp")
        or user.get("phone")
        or user.get("mobile")
    )


async def users_by_email(emails: Iterable[str]) -> Dict[str, dict]:
    wanted = {(e or "").strip().lower() for e in emails if e and "@" in e}
    if not wanted:
        return {}
    rows = await db.users.find(
        {"email": {"$in": list(wanted)}},
        {
            "_id": 0,
            "email": 1,
            "whatsapp_number": 1,
            "whatsapp_verified": 1,
            "whatsapp": 1,
            "phone": 1,
            "mobile": 1,
        },
    ).to_list(len(wanted) + 10)
    return {(row.get("email") or "").strip().lower(): row for row in rows}


async def verified_whatsapp_for_email(email: Optional[str]) -> Optional[str]:
    """Profile WhatsApp only when the account has verified it."""
    key = (email or "").strip().lower()
    if "@" not in key:
        return None
    user = (await users_by_email([key])).get(key)
    if user and user.get("whatsapp_verified") and user.get("whatsapp_number"):
        return user["whatsapp_number"]
    return None


async def apply_account_contacts(items: list[dict]) -> list[dict]:
    """Fill each expert's phone/whatsapp from the matching verified profile.

    A verified profile number replaces a stale number stored on the expert.
    Experts with no account match keep their own phone, then an organisation
    WhatsApp/mobile if the expert record itself has none.
    """
    emails = []
    for item in items:
        emails.append(item.get("email") or "")
        for org in item.get("organizations") or []:
            emails.append(org.get("contact_email") or "")
    accounts = await users_by_email(emails)

    for item in items:
        email = (item.get("email") or "").strip().lower()
        account = accounts.get(email)
        verified = None
        if account and account.get("whatsapp_verified") and account.get("whatsapp_number"):
            verified = account["whatsapp_number"]
        if verified:
            item["whatsapp"] = verified
            item["phone"] = verified
            continue
        if item.get("whatsapp") or item.get("phone") or item.get("mobile"):
            continue
        fallback = _account_phone(account)
        if not fallback:
            for org in item.get("organizations") or []:
                fallback = org.get("whatsapp") or org.get("mobile")
                if fallback:
                    break
                fallback = _account_phone(accounts.get((org.get("contact_email") or "").strip().lower()))
                if fallback:
                    if not item.get("email"):
                        item["email"] = org.get("contact_email")
                    break
        if fallback:
            item["whatsapp"] = fallback
            item["phone"] = fallback
    return items


def choose_notify_phone(
    submitted: Optional[str],
    stored: Optional[str],
    verified: Optional[str],
) -> Optional[str]:
    """Prefer the verified profile number over a stale expert number.

    A number the caller typed that is different from both the stored expert
    number and the verified profile number is kept.
    """
    if verified:
        submitted_key = phone_key(submitted)
        stored_key = phone_key(stored)
        verified_key = phone_key(verified)
        if not submitted_key or submitted_key in (stored_key, verified_key):
            return verified
    return submitted or stored or verified
