"""PostHog server-side analytics (EU cloud).

Captures authoritative business events (signup, payment_success,
ai_credits_consumed, otp_sent, eg_session_completed) keyed by the same
non-PII `user_id` the frontend identifies with, so frontend + backend
events merge into one user timeline in PostHog.

No-op when POSTHOG_API_KEY is absent (dev/preview without analytics).
NEVER raises — analytics must not break business flows.
"""
import logging
import os
from typing import Any, Dict, Optional

log = logging.getLogger("posthog_client")

_client = None
_init_done = False


def _get_client():
    global _client, _init_done
    if _init_done:
        return _client
    _init_done = True
    api_key = os.environ.get("POSTHOG_API_KEY")
    if not api_key:
        log.info("POSTHOG_API_KEY not set — server-side analytics disabled (no-op)")
        return None
    try:
        from posthog import Posthog
        _client = Posthog(
            api_key,
            host=os.environ.get("POSTHOG_HOST", "https://eu.i.posthog.com"),
        )
        log.info("PostHog server-side analytics enabled")
    except Exception as e:
        log.warning(f"PostHog init failed — analytics disabled: {e}")
        _client = None
    return _client


def track(user_id: str, event: str, properties: Optional[Dict[str, Any]] = None) -> None:
    """Capture a server-side event for `user_id` (non-PII distinct id)."""
    client = _get_client()
    if client is None or not user_id:
        return
    try:
        client.capture(event, distinct_id=user_id,
                       properties={"source": "backend", **(properties or {})})
    except Exception as e:
        log.debug(f"posthog capture failed (non-fatal): {e}")
