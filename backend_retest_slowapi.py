"""
Focused re-test after slowapi headers_enabled=False fix.

Targets:
 1. POST /api/auth/forgot-password (previously 500 due to header injection)
 2. POST /api/auth/reset-password  (same previous failure)
 3. POST /api/auth/login with new password
 4. Spot-check: /api/health, /api/health/ready, X-Request-ID + X-Response-Time-MS headers
 5. Latent-bug sanity on /api/ai-assistant/quick-ask (should not 500 from slowapi)
"""

import os
import sys
import time
import uuid
import requests

BASE = "http://localhost:8001"
API = f"{BASE}/api"

results = []
def log(name, ok, detail=""):
    tag = "✅" if ok else "❌"
    print(f"{tag} {name} :: {detail}")
    results.append((name, ok, detail))

def spot_check_health():
    r = requests.get(f"{API}/health", timeout=10)
    ok = r.status_code == 200 and r.json().get("status") == "ok"
    xrid = r.headers.get("x-request-id")
    xrtm = r.headers.get("x-response-time-ms")
    log("GET /api/health", ok, f"code={r.status_code} x-request-id={xrid} x-response-time-ms={xrtm}")

    r2 = requests.get(f"{API}/health/ready", timeout=10)
    ok2 = r2.status_code == 200 and r2.json().get("checks", {}).get("mongodb") == "ok"
    log("GET /api/health/ready", ok2, f"code={r2.status_code} body={r2.json()}")

    has_obs = bool(xrid) and bool(xrtm)
    log("Observability headers (X-Request-ID + X-Response-Time-MS)", has_obs,
        f"x-request-id={xrid}, x-response-time-ms={xrtm}")

    # Confirm X-RateLimit-* intentionally NOT present (per new design)
    has_rl = any(h.lower().startswith("x-ratelimit") for h in r.headers.keys())
    log("X-RateLimit-* headers intentionally absent (by design)", not has_rl,
        f"present_keys={[h for h in r.headers.keys() if h.lower().startswith('x-ratelimit')]}")

def auth_flow():
    # 1. Register a real-looking user
    email = f"alex.rivera.{int(time.time())}@viewdezider.io"
    pwd_old = "FirstPass123!"
    pwd_new = "BrandNewPass456!"
    name = "Alex Rivera"

    r = requests.post(f"{API}/auth/register", json={
        "email": email, "password": pwd_old, "name": name
    }, timeout=15)
    if r.status_code != 200:
        log("Register seed user", False, f"code={r.status_code} body={r.text[:300]}")
        return None, None, None
    session_token = r.json().get("session_token")
    log("Register seed user", True, f"email={email}")

    # 2. forgot-password (should be 200, not 500)
    r = requests.post(f"{API}/auth/forgot-password", json={"email": email}, timeout=15)
    if r.status_code != 200:
        log("POST /api/auth/forgot-password (valid email)", False,
            f"code={r.status_code} body={r.text[:300]}")
        return email, pwd_old, None
    body = r.json()
    otp = body.get("otp")
    ok = otp is not None and len(str(otp)) >= 4
    log("POST /api/auth/forgot-password (valid email)", ok,
        f"code=200 otp_present={ok} keys={list(body.keys())}")

    # 3. reset-password
    r = requests.post(f"{API}/auth/reset-password", json={
        "email": email, "otp": otp, "new_password": pwd_new
    }, timeout=15)
    ok = r.status_code == 200
    log("POST /api/auth/reset-password", ok, f"code={r.status_code} body={r.text[:200]}")

    # 4. login with new password
    r = requests.post(f"{API}/auth/login", json={
        "email": email, "password": pwd_new
    }, timeout=15)
    ok = r.status_code == 200 and bool(r.json().get("session_token"))
    new_tok = r.json().get("session_token") if ok else None
    log("POST /api/auth/login (with new password)", ok,
        f"code={r.status_code} session_token={'***' if new_tok else None}")

    # Extra: login with OLD password should now fail
    r = requests.post(f"{API}/auth/login", json={
        "email": email, "password": pwd_old
    }, timeout=15)
    ok = r.status_code in (400, 401)
    log("Login with old password rejected", ok, f"code={r.status_code}")

    return email, pwd_new, new_tok

def quick_ask(session_token):
    if not session_token:
        log("POST /api/ai-assistant/quick-ask (latent slowapi check)", False,
            "no session_token available — skipped")
        return
    r = requests.post(f"{API}/ai-assistant/quick-ask",
                      headers={"Authorization": f"Bearer {session_token}"},
                      json={"question": "hi", "language": "en"}, timeout=30)
    # We're only verifying slowapi no longer crashes the handler. Any 2xx or
    # clean 4xx/5xx JSON body is acceptable. A crash from slowapi shows up as
    # an Internal Server Error with no JSON body or raises an exception.
    try:
        body = r.json()
        is_json = True
    except Exception:
        body = r.text[:400]
        is_json = False

    # Pass criteria: status is 200 OR (status is 4xx/5xx AND body is valid JSON)
    crashed_slowapi = (r.status_code == 500 and not is_json)
    ok = not crashed_slowapi
    log("POST /api/ai-assistant/quick-ask (latent slowapi check)", ok,
        f"code={r.status_code} is_json={is_json} note="
        + ("200 OK" if r.status_code == 200
           else f"non-200 but clean JSON (acceptable — may be LLM budget): {body if isinstance(body, dict) else body[:200]}"))

def main():
    print(f"--- Retest start :: BASE={BASE} ---")
    spot_check_health()
    print()
    email, pwd, tok = auth_flow()
    print()
    quick_ask(tok)
    print()
    # Summary
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    print(f"--- Summary: {passed} passed, {failed} failed ---")
    for name, ok, detail in results:
        if not ok:
            print(f"   ❌ {name} — {detail}")
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
