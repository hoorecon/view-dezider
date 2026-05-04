"""Shared helper for converting LLM provider exceptions into clean HTTP responses.

Why:
- Raw `emergentintegrations.ChatError` -> HTTPException(500, ...) leaks vendor
  internals into the API response.
- Budget caps and provider rate-limits are *transient* — clients should retry,
  so we return 503 (Service Unavailable) with `Retry-After`, not 500.
- A single helper means consistent error UX across AI Assistant, CLD,
  Conflict Breaker, Admin Docs refresh, etc.
"""
import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def llm_error_to_http(exc: Exception, *, request_id: str | None = None) -> HTTPException:
    """Map an LLM call exception to an appropriate HTTPException.

    503 → transient (budget exceeded, rate limit, provider 5xx). Client should retry.
    502 → upstream auth/config issue (bad key).
    500 → genuinely unknown.
    """
    err = str(exc)
    err_lower = err.lower()

    if "budget" in err_lower and "exceed" in err_lower:
        logger.warning(f"LLM budget exhausted (request_id={request_id})")
        raise HTTPException(
            status_code=503,
            detail={
                "code": "llm_budget_exceeded",
                "message": "AI service is temporarily unavailable due to quota limits. Please try again shortly.",
                "request_id": request_id,
            },
            headers={"Retry-After": "60"},
        )
    if any(token in err_lower for token in ("rate limit", "ratelimit", "too many requests", "429")):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "llm_rate_limited",
                "message": "AI service rate-limited. Please try again in a few seconds.",
                "request_id": request_id,
            },
            headers={"Retry-After": "10"},
        )
    if any(token in err_lower for token in ("invalid api key", "authentication", "unauthorized", "401", "403")):
        logger.error(f"LLM auth failure (request_id={request_id}): {err[:200]}")
        raise HTTPException(
            status_code=502,
            detail={
                "code": "llm_upstream_auth",
                "message": "AI service configuration issue. Contact support.",
                "request_id": request_id,
            },
        )
    if any(token in err_lower for token in ("timeout", "timed out", "504", "502", "503")):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "llm_upstream_unavailable",
                "message": "AI service temporarily unavailable. Please retry.",
                "request_id": request_id,
            },
            headers={"Retry-After": "15"},
        )

    # Unknown failure — log full exception for ops, return generic 500
    logger.error(f"Unhandled LLM error (request_id={request_id}): {err[:300]}")
    raise HTTPException(
        status_code=500,
        detail={
            "code": "llm_unknown_error",
            "message": "AI generation failed. Please try again.",
            "request_id": request_id,
        },
    )
