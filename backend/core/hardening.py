"""
Production hardening primitives.

This module bundles cross-cutting middleware/utilities so server.py stays
slim. All knobs are env-tunable so the same image runs in Emergent's
managed runtime, in Docker locally, or in AWS/GCP prod with stricter
posture.

Covered concerns:
  - Security headers (HSTS / CSP / X-Frame / X-Content-Type / Referrer / Permissions)
  - Body size cap (defends against memory-bomb requests)
  - GZip response compression
  - Slow request logging (separate from the regular request log)
  - Prometheus-style /metrics counters (in-memory; pluggable)
  - PII redaction helper for log lines
  - Idempotency-Key dedupe (mutation endpoints)
  - Lightweight circuit breaker + retry-with-jitter for outbound HTTP
  - Audit log helper (append-only collection)

Nothing here imports route modules — safe to import from server.py before
router wiring.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Awaitable, Callable, Dict, Iterable, Optional

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("hardening")

# ---------------------------------------------------------------------------
# Env knobs
# ---------------------------------------------------------------------------
ENV = os.environ.get("DEZIDER_ENV", "dev").lower()         # dev | stage | prod
ENABLE_SEC_HEADERS = os.environ.get("SECURITY_HEADERS_ENABLED", "true").lower() != "false"
ENABLE_HSTS = os.environ.get("HSTS_ENABLED", "true").lower() != "false"
HSTS_MAX_AGE = int(os.environ.get("HSTS_MAX_AGE", "63072000"))   # 2 years
MAX_BODY_BYTES = int(os.environ.get("MAX_BODY_BYTES", str(10 * 1024 * 1024)))  # 10 MB
CSP_POLICY = os.environ.get(
    "CSP_POLICY",
    "default-src 'self'; "
    "img-src 'self' data: blob: https:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline'; "
    "connect-src 'self' https: wss:; "
    "frame-ancestors *; "
    "base-uri 'self'; "
    "object-src 'none';",
)
GZIP_MIN_SIZE = int(os.environ.get("GZIP_MIN_SIZE", "1024"))
SLOW_REQUEST_MS = int(os.environ.get("SLOW_REQUEST_MS", "800"))
IDEMPOTENCY_TTL_SECONDS = int(os.environ.get("IDEMPOTENCY_TTL_SECONDS", "86400"))  # 24h
METRICS_ENABLED = os.environ.get("METRICS_ENABLED", "true").lower() != "false"
METRICS_TOKEN = os.environ.get("METRICS_TOKEN", "")


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply industry-standard security headers to every response.

    `frame-ancestors *` is intentional in CSP because /api/embed/{slug} pages
    are designed to be iframed on third-party org/govt websites.
    Routes that DON'T want to be embedded should set X-Frame-Options=DENY
    on their own response.
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if not ENABLE_SEC_HEADERS:
            return response
        # Only override if the route hasn't set its own.
        defaults = {
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "X-DNS-Prefetch-Control": "off",
            "Permissions-Policy": "camera=(self), microphone=(self), geolocation=(self), "
                                  "interest-cohort=(), payment=(self), accelerometer=(), "
                                  "gyroscope=()",
            "Cross-Origin-Opener-Policy": "same-origin-allow-popups",
            "Cross-Origin-Resource-Policy": "cross-origin",
            "X-Frame-Options": response.headers.get("X-Frame-Options", "SAMEORIGIN"),
            "Content-Security-Policy": response.headers.get("Content-Security-Policy", CSP_POLICY),
        }
        if ENABLE_HSTS and (request.url.scheme == "https" or ENV == "prod"):
            defaults["Strict-Transport-Security"] = (
                f"max-age={HSTS_MAX_AGE}; includeSubDomains; preload"
            )
        for k, v in defaults.items():
            response.headers.setdefault(k, v)
        return response


# ---------------------------------------------------------------------------
# Body size cap middleware
# ---------------------------------------------------------------------------
class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests with Content-Length > MAX_BODY_BYTES."""

    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > MAX_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={
                    "detail": "Payload too large",
                    "max_bytes": MAX_BODY_BYTES,
                    "received_bytes": int(cl),
                },
            )
        return await call_next(request)


# ---------------------------------------------------------------------------
# Slow-request log
# ---------------------------------------------------------------------------
class SlowRequestLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - t0) * 1000
        if elapsed >= SLOW_REQUEST_MS:
            try:
                rid = response.headers.get("X-Request-ID", "-")
                logger.warning(
                    "slow_request rid=%s %s %s status=%s elapsed_ms=%.0f",
                    rid, request.method, request.url.path, response.status_code, elapsed,
                )
            except Exception:
                pass
        return response


# ---------------------------------------------------------------------------
# In-memory metrics (Prometheus-style)
# ---------------------------------------------------------------------------
class _Metrics:
    """Tiny in-process metrics store. Acceptable for single-pod deployments;
    swap to prometheus_client for multi-pod fleets.
    """
    def __init__(self):
        self.counters: Dict[str, int] = {}
        self.histograms: Dict[str, list] = {}
        self.up_since = datetime.now(timezone.utc)

    def inc(self, name: str, value: int = 1, **labels):
        key = self._key(name, labels)
        self.counters[key] = self.counters.get(key, 0) + value

    def observe(self, name: str, value_ms: float, **labels):
        key = self._key(name, labels)
        bucket = self.histograms.setdefault(key, [])
        bucket.append(value_ms)
        # Keep only last 1000 to bound memory
        if len(bucket) > 1000:
            del bucket[: len(bucket) - 1000]

    @staticmethod
    def _key(name: str, labels: Dict[str, Any]) -> str:
        if not labels:
            return name
        parts = [f'{k}="{v}"' for k, v in sorted(labels.items())]
        return f"{name}{{{','.join(parts)}}}"

    def render_prometheus(self) -> str:
        out = [
            f"# HELP dezider_uptime_seconds Time since process boot.",
            f"# TYPE dezider_uptime_seconds gauge",
            f"dezider_uptime_seconds {(datetime.now(timezone.utc) - self.up_since).total_seconds():.0f}",
        ]
        for k, v in sorted(self.counters.items()):
            out.append(f"# TYPE {k.split('{')[0]} counter")
            out.append(f"{k} {v}")
        for k, samples in sorted(self.histograms.items()):
            if not samples:
                continue
            samples_sorted = sorted(samples)
            n = len(samples_sorted)
            p50 = samples_sorted[int(n * 0.5)]
            p95 = samples_sorted[min(n - 1, int(n * 0.95))]
            p99 = samples_sorted[min(n - 1, int(n * 0.99))]
            base = k.split("{")[0]
            out.append(f"# TYPE {base} summary")
            out.append(f"{k}_count {n}")
            out.append(f"{k}_p50 {p50:.2f}")
            out.append(f"{k}_p95 {p95:.2f}")
            out.append(f"{k}_p99 {p99:.2f}")
        return "\n".join(out) + "\n"

    def render_json(self) -> Dict[str, Any]:
        hist: Dict[str, Any] = {}
        for k, samples in self.histograms.items():
            if not samples:
                continue
            ss = sorted(samples)
            n = len(ss)
            hist[k] = {
                "count": n,
                "p50": ss[int(n * 0.5)],
                "p95": ss[min(n - 1, int(n * 0.95))],
                "p99": ss[min(n - 1, int(n * 0.99))],
            }
        return {
            "uptime_seconds": int((datetime.now(timezone.utc) - self.up_since).total_seconds()),
            "counters": dict(self.counters),
            "histograms": hist,
        }


metrics = _Metrics()


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not METRICS_ENABLED:
            return await call_next(request)
        t0 = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - t0) * 1000
        # Group by route template, not raw path, to avoid cardinality explosion
        route_path = request.scope.get("route")
        path_label = getattr(route_path, "path", request.url.path)
        method = request.method
        status_class = f"{response.status_code // 100}xx"
        metrics.inc("http_requests_total", method=method, path=path_label, status=status_class)
        metrics.observe("http_request_duration_ms", elapsed, method=method, path=path_label)
        if response.status_code >= 500:
            metrics.inc("http_5xx_total", path=path_label)
        return response


# ---------------------------------------------------------------------------
# PII redaction
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_RE = re.compile(r"\b(\+?\d[\d\-\s]{8,15}\d)\b")
_AADHAAR_RE = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
_PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")


def redact_pii(text: str) -> str:
    if not isinstance(text, str):
        return text
    text = _EMAIL_RE.sub("[email-redacted]", text)
    text = _PHONE_RE.sub("[phone-redacted]", text)
    text = _AADHAAR_RE.sub("[aadhaar-redacted]", text)
    text = _PAN_RE.sub("[pan-redacted]", text)
    return text


class _PiiRedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = redact_pii(record.msg)
        except Exception:
            pass
        return True


def install_log_pii_filter():
    """Attach the redactor to the root logger so ALL log lines are scrubbed."""
    logging.getLogger().addFilter(_PiiRedactingFilter())


# ---------------------------------------------------------------------------
# Idempotency-Key support
# ---------------------------------------------------------------------------
async def get_idempotent_response(db, key: str) -> Optional[Dict[str, Any]]:
    if not key:
        return None
    doc = await db.idempotency_keys.find_one({"_id": key})
    if not doc:
        return None
    expires_at = doc.get("expires_at")
    if isinstance(expires_at, datetime) and expires_at < datetime.now(timezone.utc):
        await db.idempotency_keys.delete_one({"_id": key})
        return None
    return doc


async def store_idempotent_response(db, key: str, status_code: int, body: Any):
    if not key:
        return
    await db.idempotency_keys.update_one(
        {"_id": key},
        {"$set": {
            "status_code": status_code,
            "body": body,
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=IDEMPOTENCY_TTL_SECONDS),
        }},
        upsert=True,
    )


# ---------------------------------------------------------------------------
# Outbound HTTP — circuit breaker + retry-with-jitter
# ---------------------------------------------------------------------------
class CircuitBreakerOpen(Exception):
    pass


class CircuitBreaker:
    """Per-host circuit breaker. Trip after `fail_threshold` consecutive
    failures, hold open for `cooldown_seconds`, then half-open one probe.
    """
    def __init__(self, fail_threshold: int = 5, cooldown_seconds: int = 30):
        self.fail_threshold = fail_threshold
        self.cooldown_seconds = cooldown_seconds
        self._state: Dict[str, Dict[str, Any]] = {}

    def _key_state(self, key: str) -> Dict[str, Any]:
        return self._state.setdefault(key, {
            "consecutive_failures": 0,
            "opened_at": None,
        })

    def is_open(self, key: str) -> bool:
        s = self._key_state(key)
        if s["opened_at"] is None:
            return False
        if (datetime.now(timezone.utc) - s["opened_at"]).total_seconds() > self.cooldown_seconds:
            # half-open — allow next probe
            return False
        return True

    def record_success(self, key: str):
        s = self._key_state(key)
        s["consecutive_failures"] = 0
        s["opened_at"] = None

    def record_failure(self, key: str):
        s = self._key_state(key)
        s["consecutive_failures"] += 1
        if s["consecutive_failures"] >= self.fail_threshold:
            s["opened_at"] = datetime.now(timezone.utc)


breaker = CircuitBreaker()


async def with_retry(
    func: Callable[[], Awaitable[Any]],
    *,
    retries: int = 2,
    base_delay: float = 0.25,
    max_delay: float = 2.0,
    breaker_key: Optional[str] = None,
) -> Any:
    """Run `func` with exponential backoff + full jitter and an optional
    circuit-breaker check.
    """
    if breaker_key and breaker.is_open(breaker_key):
        raise CircuitBreakerOpen(f"circuit open for {breaker_key}")
    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            result = await func()
            if breaker_key:
                breaker.record_success(breaker_key)
            return result
        except Exception as e:
            last_exc = e
            if breaker_key:
                breaker.record_failure(breaker_key)
            if attempt == retries:
                break
            delay = min(max_delay, base_delay * (2 ** attempt))
            await asyncio.sleep(delay * (0.5 + random.random() * 0.5))
    raise last_exc  # type: ignore


# ---------------------------------------------------------------------------
# Audit log helper
# ---------------------------------------------------------------------------
async def write_audit(
    db,
    *,
    action: str,
    actor_id: Optional[str],
    actor_email: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
    success: bool = True,
) -> None:
    """Append an audit-trail row. Best-effort — never raises."""
    try:
        ip_hash = None
        if request is not None and request.client:
            ip = request.headers.get("x-forwarded-for", request.client.host)
            ip = (ip or "").split(",")[0].strip()
            if ip:
                ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        await db.audit_log.insert_one({
            "action": action,
            "actor_id": actor_id,
            "actor_email": redact_pii(actor_email or "") or None,
            "target_type": target_type,
            "target_id": target_id,
            "metadata": metadata or {},
            "success": success,
            "ip_hash": ip_hash,
            "request_id": getattr(getattr(request, "state", None), "request_id", None) if request else None,
            "ts": datetime.now(timezone.utc),
        })
    except Exception:
        # Audit log MUST NOT break the request flow.
        logger.warning("audit_log_write_failed action=%s actor=%s", action, actor_id)


# ---------------------------------------------------------------------------
# Public bootstrap
# ---------------------------------------------------------------------------
def install_hardening(app):
    """Mount every middleware in the right order. Call ONCE from server.py.

    Order matters — outermost first:
      1. body-size cap (cheap, blocks huge requests immediately)
      2. gzip (so security-headers middleware sees the post-compression length)
      3. metrics + slow-request logger
      4. security headers (last so user routes can override)
    """
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=GZIP_MIN_SIZE)
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(SlowRequestLoggerMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    install_log_pii_filter()
    logger.info(
        "hardening installed env=%s sec_headers=%s hsts=%s gzip=%s metrics=%s body_cap=%dMB",
        ENV, ENABLE_SEC_HEADERS, ENABLE_HSTS, True, METRICS_ENABLED,
        MAX_BODY_BYTES // (1024 * 1024),
    )


__all__ = [
    "install_hardening", "metrics", "redact_pii", "with_retry",
    "breaker", "CircuitBreakerOpen", "write_audit",
    "get_idempotent_response", "store_idempotent_response",
    "METRICS_ENABLED", "METRICS_TOKEN",
]
