"""Rate limiting — slowapi-backed, with tighter caps for AI endpoints.

Strategy:
- IP-based default keying for unauthenticated routes.
- Per-user (Bearer token) keying for authenticated routes — prevents one
  abusive user from starving others sharing the same IP (corp NAT / VPN).
- AI endpoints get tighter limits because each call costs LLM credits.

Usage in routes:
    from core.rate_limiting import limiter, AI_LIMIT, AUTH_LIMIT, DEFAULT_LIMIT

    @router.post("/ai/something")
    @limiter.limit(AI_LIMIT)
    async def my_ai_route(request: Request, ...):
        ...

The `request: Request` parameter is REQUIRED for slowapi to work.
"""

import os
from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def _user_or_ip_key(request: Request) -> str:
    """Use the bearer token (or session cookie) as the rate-limit key when present.

    This way one abusive user behind a shared NAT/VPN can't spend the IP-wide
    quota of every co-worker. Falls back to remote IP for unauthenticated traffic.
    """
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return f"user:{auth[7:]}"
    cookie_token = request.cookies.get("session_token")
    if cookie_token:
        return f"user:{cookie_token}"
    return f"ip:{get_remote_address(request)}"


# Limit profiles — tweak via env without code changes.
DEFAULT_LIMIT = os.environ.get("RATE_LIMIT_DEFAULT", "120/minute")    # generic CRUD / lists
AUTH_LIMIT = os.environ.get("RATE_LIMIT_AUTH", "10/minute")           # login / register / password reset
AI_LIMIT = os.environ.get("RATE_LIMIT_AI", "10/minute")               # LLM-backed endpoints
EXPENSIVE_LIMIT = os.environ.get("RATE_LIMIT_EXPENSIVE", "20/minute") # PDF / heavy aggregations
PUBLIC_LIMIT = os.environ.get("RATE_LIMIT_PUBLIC", "60/minute")       # unauthenticated/public

# Disable globally with RATE_LIMIT_ENABLED=false (e.g., during testing)
ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() != "false"

limiter = Limiter(
    key_func=_user_or_ip_key,
    default_limits=[DEFAULT_LIMIT] if ENABLED else [],
    enabled=ENABLED,
    headers_enabled=True,  # X-RateLimit-* response headers — useful for debugging
)


__all__ = [
    "limiter",
    "RateLimitExceeded",
    "DEFAULT_LIMIT",
    "AUTH_LIMIT",
    "AI_LIMIT",
    "EXPENSIVE_LIMIT",
    "PUBLIC_LIMIT",
]
