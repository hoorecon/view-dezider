"""
Backend regression test for View Dezider API after P0/P1 hardening + refactor.

Covers:
  - P0 New Hardening: /api/health, /api/health/ready, response headers,
    rate-limit headers
  - P0 Auth flow regression (signature changes added `request: Request`)
  - P0 PRR Decisions CRUD sanity
  - P1 Admin Docs surface (auth gate)
  - P1 Critical AI endpoint structure (auth gates only — no LLM calls)
  - P0 ACM auth gate
"""
import os
import sys
import time
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001") + "/api"
TIMEOUT = 30

results = []


def log(name, passed, detail=""):
    icon = "PASS" if passed else "FAIL"
    msg = f"[{icon}] {name}"
    if detail:
        msg += f" -- {detail}"
    print(msg)
    results.append({"name": name, "passed": passed, "detail": detail})


def req(method, path, **kwargs):
    kwargs.setdefault("timeout", TIMEOUT)
    return requests.request(method, BASE_URL + path, **kwargs)


# =================================================================
# P0 — NEW HARDENING INFRASTRUCTURE
# =================================================================
def test_health():
    print("\n--- P0: Health & Readiness ---")
    r = req("GET", "/health")
    body = r.json() if r.ok else {}
    ok = (
        r.status_code == 200
        and body.get("status") == "ok"
        and body.get("service") == "View Dezider API"
    )
    log("GET /api/health returns ok+service", ok, f"status={r.status_code} body={body}")

    r = req("GET", "/health/ready")
    body = r.json() if r.ok else {}
    checks = body.get("checks", {}) if isinstance(body, dict) else {}
    ok = (
        r.status_code == 200
        and body.get("status") == "ok"
        and "mongodb" in checks
        and checks["mongodb"] == "ok"
    )
    log("GET /api/health/ready probes mongodb", ok, f"status={r.status_code} body={body}")


def test_response_headers():
    print("\n--- P0: Observability + Rate-Limit Headers ---")
    r = req("GET", "/health")
    h = r.headers

    rid = h.get("X-Request-ID") or h.get("x-request-id") or ""
    rid_ok = len(rid) == 12 and all(c in "0123456789abcdef" for c in rid.lower())
    log("X-Request-ID present (12-hex)", rid_ok, f"value={rid!r}")

    rtime = h.get("X-Response-Time-MS") or h.get("x-response-time-ms") or ""
    try:
        float(rtime)
        rtime_ok = True
    except Exception:
        rtime_ok = False
    log("X-Response-Time-MS present + numeric", rtime_ok, f"value={rtime!r}")

    rl_limit = h.get("X-RateLimit-Limit")
    rl_remain = h.get("X-RateLimit-Remaining")
    rl_reset = h.get("X-RateLimit-Reset")
    log(
        "X-RateLimit headers (Limit/Remaining/Reset)",
        all([rl_limit, rl_remain, rl_reset]),
        f"limit={rl_limit} remain={rl_remain} reset={rl_reset}",
    )


def test_rate_limit_decrement():
    print("\n--- P0: Rate-Limit Counter Decrements ---")
    remains = []
    for _ in range(4):
        r = req("GET", "/health")
        try:
            remains.append(int(r.headers.get("X-RateLimit-Remaining", "0")))
        except ValueError:
            remains.append(-1)
        time.sleep(0.05)
    decreasing = remains[0] > remains[-1]
    log("X-RateLimit-Remaining decrements", decreasing, f"sequence={remains}")


# =================================================================
# P0 — AUTH FLOW REGRESSION
# =================================================================
auth_state = {}


def test_auth_register():
    print("\n--- P0: Auth Flow Regression ---")
    suffix = int(time.time())
    email = f"sarah.cardoso.{suffix}@viewdezider-test.com"
    pwd = "InitialPass#2026"
    payload = {"email": email, "password": pwd, "name": "Sarah Cardoso"}
    r = req("POST", "/auth/register", json=payload)
    body = r.json() if r.ok else r.text
    ok = (
        r.status_code == 200
        and isinstance(body, dict)
        and body.get("session_token")
        and body.get("email") == email
        and body.get("user_id")
        and body.get("name") == "Sarah Cardoso"
    )
    log("POST /api/auth/register", ok, f"status={r.status_code}")
    if ok:
        auth_state["email"] = email
        auth_state["password"] = pwd
        auth_state["token"] = body["session_token"]
        auth_state["user_id"] = body["user_id"]
    else:
        print(f"   body={body}")


def test_auth_login():
    if "email" not in auth_state:
        log("POST /api/auth/login", False, "register failed; skip")
        return
    r = req(
        "POST",
        "/auth/login",
        json={"email": auth_state["email"], "password": auth_state["password"]},
    )
    body = r.json() if r.ok else r.text
    ok = r.status_code == 200 and isinstance(body, dict) and body.get("session_token")
    log("POST /api/auth/login", ok, f"status={r.status_code}")
    if ok:
        auth_state["token"] = body["session_token"]


def test_auth_me():
    if "token" not in auth_state:
        log("GET /api/auth/me", False, "no token; skip")
        return
    r = req(
        "GET",
        "/auth/me",
        headers={"Authorization": f"Bearer {auth_state['token']}"},
    )
    body = r.json() if r.ok else r.text
    ok = (
        r.status_code == 200
        and isinstance(body, dict)
        and "has_password" in body
        and body.get("email") == auth_state["email"]
    )
    log("GET /api/auth/me has has_password", ok, f"status={r.status_code}")


def test_forgot_reset_password():
    if "email" not in auth_state:
        log("POST /api/auth/forgot-password", False, "no user; skip")
        return
    r = req("POST", "/auth/forgot-password", json={"email": auth_state["email"]})
    body = r.json() if r.ok else r.text
    otp = body.get("otp") if isinstance(body, dict) else None
    ok = r.status_code == 200 and otp
    log("POST /api/auth/forgot-password returns OTP", ok, f"status={r.status_code}")
    if not ok:
        print(f"   body={body}")
        return

    new_pwd = "ResetPass#2026"
    r2 = req(
        "POST",
        "/auth/reset-password",
        json={"email": auth_state["email"], "otp": otp, "new_password": new_pwd},
    )
    log("POST /api/auth/reset-password", r2.status_code == 200, f"status={r2.status_code}")
    if r2.status_code == 200:
        auth_state["password"] = new_pwd

    r3 = req(
        "POST",
        "/auth/login",
        json={"email": auth_state["email"], "password": auth_state["password"]},
    )
    body3 = r3.json() if r3.ok else r3.text
    ok3 = r3.status_code == 200 and isinstance(body3, dict) and body3.get("session_token")
    log("Login w/ new password after reset", ok3, f"status={r3.status_code}")
    if ok3:
        auth_state["token"] = body3["session_token"]


# =================================================================
# P0 — PRR DECISIONS CRUD
# =================================================================
def test_decisions_crud():
    print("\n--- P0: PRR Decisions CRUD ---")
    if "token" not in auth_state:
        log("Decisions CRUD", False, "no token")
        return
    h = {"Authorization": f"Bearer {auth_state['token']}"}

    payload = {
        "title": "Should I move to Bangalore for the new role?",
        "folder": "career",
        "context": "Weighing the Bangalore offer vs staying in Mumbai. Family, finances, and career growth all in scope.",
    }
    r = req("POST", "/decisions", json=payload, headers=h)
    try:
        body = r.json()
    except Exception:
        body = r.text
    decision_id = body.get("id") if isinstance(body, dict) else None
    log("POST /api/decisions", bool(decision_id) and r.status_code == 200, f"status={r.status_code}")
    if not decision_id:
        print(f"   body={body}")
        return

    r = req("GET", "/decisions", headers=h)
    items = r.json() if r.ok else []
    found = any(d.get("id") == decision_id for d in items) if isinstance(items, list) else False
    log(
        "GET /api/decisions includes new",
        r.status_code == 200 and found,
        f"status={r.status_code} count={len(items) if isinstance(items, list) else 'N/A'}",
    )

    new_title = "Updated: Bangalore relocation analysis"
    r = req("PUT", f"/decisions/{decision_id}", json={"title": new_title}, headers=h)
    log("PUT /api/decisions/{id}", r.status_code == 200, f"status={r.status_code}")

    r = req("GET", f"/decisions/{decision_id}", headers=h)
    body = r.json() if r.ok else {}
    log(
        "Update persisted",
        r.status_code == 200 and body.get("title") == new_title,
        f"title={body.get('title')!r}",
    )

    r = req("DELETE", f"/decisions/{decision_id}", headers=h)
    log("DELETE /api/decisions/{id}", r.status_code == 200, f"status={r.status_code}")


# =================================================================
# P1 — ADMIN DOCS AUTH GATE
# =================================================================
def test_admin_docs_auth_gate():
    print("\n--- P1: Admin Docs Auth Gate ---")
    r = req("GET", "/admin/docs/api-catalog")
    log(
        "GET /api/admin/docs/api-catalog (no auth) -> 401",
        r.status_code == 401,
        f"status={r.status_code}",
    )

    if "token" in auth_state:
        h = {"Authorization": f"Bearer {auth_state['token']}"}
        r = req("GET", "/admin/docs/api-catalog", headers=h)
        log(
            "GET /api/admin/docs/api-catalog (non-admin) -> 403",
            r.status_code == 403,
            f"status={r.status_code}",
        )

    r = req("POST", "/admin/docs/refresh/prd")
    log(
        "POST /api/admin/docs/refresh/prd (no auth) -> 401",
        r.status_code == 401,
        f"status={r.status_code}",
    )

    r = req("POST", "/admin/docs/refresh-all")
    log(
        "POST /api/admin/docs/refresh-all (no auth) -> 401",
        r.status_code == 401,
        f"status={r.status_code}",
    )


# =================================================================
# P1 — AI ENDPOINT AUTH GATES
# =================================================================
def test_ai_endpoint_auth_gates():
    print("\n--- P1: AI Endpoint Auth Gates ---")
    cases = [
        ("POST", "/ai-assistant/quick-ask", {"question": "test"}),
        ("POST", "/cld/module/master/generate", {"context": "test"}),
        ("POST", "/conflict-breaker/sessions/test_session_id/ai-generate/crucial_check", {}),
        ("POST", "/tepfi-auto-map", {"factors": []}),
        ("POST", "/factors/fetch-data", {}),
    ]
    for method, path, payload in cases:
        r = req(method, path, json=payload)
        log(
            f"{method} {path} (no auth) -> 401",
            r.status_code == 401,
            f"status={r.status_code}",
        )


def test_cld_invalid_module_type():
    print("\n--- P1: CLD invalid module type ---")
    if "token" not in auth_state:
        log("CLD invalid module type", False, "no token")
        return
    h = {"Authorization": f"Bearer {auth_state['token']}"}
    r = req(
        "POST",
        "/cld/module/invalid_type/generate",
        json={"context": "test"},
        headers=h,
    )
    try:
        body = r.json()
    except Exception:
        body = {}
    detail = body.get("detail", "") if isinstance(body, dict) else str(body)
    detail_str = str(detail).lower()
    has_module_list = "master" in detail_str or "valid" in detail_str or "invalid" in detail_str
    log(
        "POST /cld/module/invalid_type/generate (auth) -> 400",
        r.status_code == 400,
        f"status={r.status_code} detail={str(detail)[:140]!r}",
    )
    log(
        "  ...with valid-module hint in detail",
        has_module_list,
        f"detail={str(detail)[:140]!r}",
    )


# =================================================================
# P0 — ACM AUTH GATE
# =================================================================
def test_acm_auth_gate():
    print("\n--- P0: ACM Auth Gate ---")
    r = req("GET", "/acm/matrix")
    log(
        "GET /api/acm/matrix (no auth) -> 401",
        r.status_code == 401,
        f"status={r.status_code}",
    )
    if "token" in auth_state:
        h = {"Authorization": f"Bearer {auth_state['token']}"}
        r = req("GET", "/acm/matrix", headers=h)
        log(
            "GET /api/acm/matrix (non-admin) -> 403/200",
            r.status_code in (200, 403),
            f"status={r.status_code}",
        )


# =================================================================
# RUN
# =================================================================
if __name__ == "__main__":
    print(f"Testing backend at {BASE_URL}")
    print("=" * 60)
    test_health()
    test_response_headers()
    test_rate_limit_decrement()
    test_auth_register()
    test_auth_login()
    test_auth_me()
    test_forgot_reset_password()
    test_decisions_crud()
    test_admin_docs_auth_gate()
    test_ai_endpoint_auth_gates()
    test_cld_invalid_module_type()
    test_acm_auth_gate()

    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"RESULTS: {passed}/{total} passed")
    failed = [r for r in results if not r["passed"]]
    if failed:
        print("\nFAILURES:")
        for r in failed:
            print(f"  FAIL {r['name']} -- {r['detail']}")
        sys.exit(1)
    sys.exit(0)
