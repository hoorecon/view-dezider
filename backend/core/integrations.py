"""
core/integrations.py
Runtime resolver for 3rd-party integration credentials.

Credentials can be configured two ways:
  1. Admin UI  → stored in the `integrations` Mongo collection
                 ({provider, config:{...}, enabled:bool}).
  2. Environment variables (.env) → deployment-level fallback.

Provider clients should call these helpers at REQUEST time (not import time)
so Admin edits take effect immediately without a container restart.

Resolution order for any credential:  Admin-UI value (when the integration is
`enabled`)  →  environment variable fallback.
"""
from __future__ import annotations

import os
import logging
from typing import Any, Dict, Tuple

from core.database import db

logger = logging.getLogger(__name__)

try:
    import razorpay as _razorpay  # type: ignore
except Exception:  # pragma: no cover
    _razorpay = None


async def get_integration(provider: str, require_enabled: bool = True) -> Dict[str, Any]:
    """Return the saved config dict for a provider, or {} if none / disabled."""
    doc = await db.integrations.find_one({"provider": provider}, {"_id": 0}) or {}
    if require_enabled and not doc.get("enabled", False):
        return {}
    return doc.get("config") or {}


async def resolve_razorpay_creds() -> Tuple[str, str, str]:
    """Return (key_id, key_secret, webhook_secret).

    Admin-UI (enabled) values take precedence; falls back to env vars
    RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET / RAZORPAY_WEBHOOK_SECRET.
    """
    cfg = await get_integration("razorpay")
    key_id = cfg.get("key_id") or os.getenv("RAZORPAY_KEY_ID", "")
    key_secret = cfg.get("key_secret") or os.getenv("RAZORPAY_KEY_SECRET", "")
    webhook_secret = cfg.get("webhook_secret") or os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    return key_id, key_secret, webhook_secret


async def get_razorpay_client():
    """Build a Razorpay client at request time.

    Returns (client, key_id, key_secret). `client` is None when the SDK is
    unavailable or credentials are not configured.
    """
    key_id, key_secret, _ = await resolve_razorpay_creds()
    client = None
    if _razorpay and key_id and key_secret:
        try:
            client = _razorpay.Client(auth=(key_id, key_secret))
        except Exception as e:  # pragma: no cover
            logger.warning("Razorpay client init failed: %s", e)
    return client, key_id, key_secret
