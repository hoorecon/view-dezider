"""
core/integrations.py
Runtime resolver for 3rd-party integration credentials.

Credentials can be configured two ways:
  1. Admin UI  → stored in the `integrations` Mongo collection
                 ({provider, config:{...}, enabled:bool}).
  2. Environment variables (.env) → deployment-level fallback.

Resolution for Razorpay (option-3 behaviour):
  Sources are tried in priority order  →  1) Admin UI (enabled)  2) .env.
  Each candidate's keys are auth-checked against Razorpay (result cached for
  10 min). The FIRST source that passes is used. A source is skipped only on a
  definitive authentication failure; a transient network error never discards
  otherwise-configured keys (so a Razorpay outage can't block checkout).

Provider clients call these helpers at REQUEST time so Admin edits take effect
without a container restart.
"""
from __future__ import annotations

import os
import time
import asyncio
import logging
from typing import Any, Dict, Optional, Tuple

from core.database import db

logger = logging.getLogger(__name__)

try:
    import razorpay as _razorpay  # type: ignore
except Exception:  # pragma: no cover
    _razorpay = None

try:
    import requests as _requests  # razorpay's transport; used to detect network errors
except Exception:  # pragma: no cover
    _requests = None


# ── Cached auth-validation ────────────────────────────────────────────────────
_VALIDATION_TTL = 600  # seconds
# (key_id, key_secret) -> (is_valid: bool, checked_at_epoch: float)
_validation_cache: Dict[Tuple[str, str], Tuple[bool, float]] = {}


def _mask(key_id: str) -> str:
    return (key_id[:12] + "…") if key_id and len(key_id) > 12 else (key_id or "")


async def validate_razorpay_keys(key_id: str, key_secret: str) -> Optional[bool]:
    """Auth-check a Razorpay key pair (cached).

    Returns:
      True  → keys are valid
      False → definitive authentication failure (bad keys)
      None  → could not determine (SDK missing / network error) — caller should
              treat the keys as usable rather than discard them.
    """
    if not (_razorpay and key_id and key_secret):
        return False

    cached = _validation_cache.get((key_id, key_secret))
    if cached and (time.time() - cached[1] < _VALIDATION_TTL):
        return cached[0]

    def _check() -> Optional[bool]:
        try:
            client = _razorpay.Client(auth=(key_id, key_secret))
            client.order.all({"count": 1})  # read-only, no charge
            return True
        except Exception as e:  # noqa: BLE001
            # Network / connectivity problems → "unknown", do not discard keys.
            if _requests is not None and isinstance(e, _requests.exceptions.RequestException):
                logger.warning(
                    "Razorpay key validation network error (assuming usable) key_id=%s: %s",
                    _mask(key_id), str(e)[:120],
                )
                return None
            # Anything else (401/400 auth issues) → invalid keys.
            logger.warning(
                "Razorpay key validation FAILED (auth) key_id=%s: %s",
                _mask(key_id), str(e)[:140],
            )
            return False

    result = await asyncio.to_thread(_check)
    if result is not None:  # cache only definitive results
        _validation_cache[(key_id, key_secret)] = (result, time.time())
    return result


# ── Generic integration config ───────────────────────────────────────────────
async def get_integration(provider: str, require_enabled: bool = True) -> Dict[str, Any]:
    """Return the saved config dict for a provider, or {} if none / disabled."""
    doc = await db.integrations.find_one({"provider": provider}, {"_id": 0}) or {}
    if require_enabled and not doc.get("enabled", False):
        return {}
    return doc.get("config") or {}


# ── Razorpay resolution (validated, with fallback) ───────────────────────────
async def resolve_razorpay_validated() -> Dict[str, Any]:
    """Pick the first usable Razorpay credential source.

    Returns dict: {key_id, key_secret, webhook_secret, source, valid}.
      source ∈ {"admin_ui", "env", "none"}
    """
    admin = await get_integration("razorpay")  # {} when disabled
    env_kid = os.getenv("RAZORPAY_KEY_ID", "")
    env_ks = os.getenv("RAZORPAY_KEY_SECRET", "")
    env_wh = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

    candidates = []
    if admin.get("key_id") and admin.get("key_secret"):
        candidates.append(
            ("admin_ui", admin["key_id"], admin["key_secret"], admin.get("webhook_secret") or env_wh)
        )
    if env_kid and env_ks:
        candidates.append(("env", env_kid, env_ks, env_wh))

    has_admin = any(c[0] == "admin_ui" for c in candidates)

    for source, kid, ks, wh in candidates:
        verdict = await validate_razorpay_keys(kid, ks)
        if verdict is False:
            logger.warning(
                "Razorpay '%s' credentials are INVALID — falling back to the next source.", source
            )
            continue
        # True (valid) or None (network-unknown) → accept this source.
        if source != "admin_ui" and has_admin:
            logger.warning(
                "Razorpay: Admin-UI keys were invalid; USING '%s' (.env) account instead.", source
            )
        return {
            "key_id": kid, "key_secret": ks, "webhook_secret": wh,
            "source": source, "valid": bool(verdict),
        }

    # Nothing usable — return best-effort so error messages stay meaningful.
    if candidates:
        source, kid, ks, wh = candidates[0]
        logger.error("Razorpay: no source passed validation; checkout will be unavailable.")
        return {"key_id": kid, "key_secret": ks, "webhook_secret": wh, "source": source, "valid": False}
    return {"key_id": "", "key_secret": "", "webhook_secret": env_wh, "source": "none", "valid": False}


async def resolve_razorpay_creds() -> Tuple[str, str, str]:
    """Return (key_id, key_secret, webhook_secret) from the chosen source."""
    r = await resolve_razorpay_validated()
    return r["key_id"], r["key_secret"], r["webhook_secret"]


async def get_razorpay_client():
    """Build a Razorpay client at request time from the chosen, validated source.

    Returns (client, key_id, key_secret). `client` is None when no usable
    credentials are available.
    """
    r = await resolve_razorpay_validated()
    client = None
    if _razorpay and r["key_id"] and r["key_secret"]:
        try:
            client = _razorpay.Client(auth=(r["key_id"], r["key_secret"]))
        except Exception as e:  # pragma: no cover
            logger.warning("Razorpay client init failed: %s", e)
    return client, r["key_id"], r["key_secret"]


# ── UltraMsg (WhatsApp) resolution ───────────────────────────────────────────
async def resolve_ultramsg_creds() -> Tuple[str, str, str]:
    """Return (instance_id, token, source) for UltraMsg WhatsApp.

    Priority: Admin UI (db.integrations, enabled) → .env fallback.
    source ∈ {"admin_ui", "env", "none"}.
    """
    admin = await get_integration("ultramsg")  # {} when disabled/missing
    if admin.get("instance_id") and admin.get("token"):
        return admin["instance_id"], admin["token"], "admin_ui"

    env_instance = os.getenv("ULTRAMSG_INSTANCE_ID", "")
    env_token = os.getenv("ULTRAMSG_API_TOKEN", "")
    if env_instance and env_token:
        return env_instance, env_token, "env"
    return "", "", "none"


# ── ScraperAPI (JS-rendering crawl proxy) resolution ─────────────────────────
async def resolve_scraperapi() -> Dict[str, str]:
    """Return {api_key, country_code, source} for ScraperAPI.

    Priority: Admin UI (db.integrations, enabled) → .env fallback. Optional —
    when no key is configured, callers fall back to a direct httpx fetch.
    source ∈ {"admin_ui", "env", "none"}.
    """
    admin = await get_integration("scraperapi")  # {} when disabled/missing
    if admin.get("api_key"):
        return {"api_key": admin["api_key"],
                "country_code": admin.get("country_code") or "in",
                "source": "admin_ui"}
    env_key = os.getenv("SCRAPERAPI_KEY", "")
    if env_key:
        return {"api_key": env_key,
                "country_code": os.getenv("SCRAPERAPI_COUNTRY", "") or "in",
                "source": "env"}
    return {"api_key": "", "country_code": "", "source": "none"}
