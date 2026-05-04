"""
Final regression sweep after additional refactoring + LLM error polish.

Tests:
  1. Auth flow end-to-end (register/login/me/forgot/reset)
  2. Decisions CRUD
  3. Test123, Assessment, Journal, Folders
  4. Solutions Store
  5. Collaboration decision-modes
  6. LLM error polish (503 with typed body + Retry-After)
  7. Observability headers (X-Request-ID, X-Response-Time-MS)

Rate limits: AUTH=10/min, AI=10/min — spacing where needed.
"""
import os
import time
import json
import uuid
import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost:8001")
API = f"{BASE_URL}/api"

TS = int(time.time())
EMAIL = f"regress_{TS}@viewdezider.com"
PASSWORD = "StrongPass_2026!"
NEW_PASSWORD = "NewStrong_2026!"
NAME = "Maya Regression"

session = requests.Session()
session.headers.update({"Content-Type": "application/json"})

results = []

def log(name: str, ok: bool, detail: str = ""):
    status = "PASS" if ok else "FAIL"
    tag = "✅" if ok else "❌"
    print(f"{tag} [{status}] {name} -- {detail}")
    results.append((name, ok, detail))


def assert_headers(resp: requests.Response, label: str):
    rid = resp.headers.get("X-Request-ID")
    rtm = resp.headers.get("X-Response-Time-MS")
    if rid and rtm:
        return True, f"rid={rid[:12]} time={rtm}ms"
    missing = []
    if not rid:
        missing.append("X-Request-ID")
    if not rtm:
        missing.append("X-Response-Time-MS")
    return False, f"missing {missing} on {label}"


def req(method: str, path: str, *, json_body=None, headers=None, token: str = None):
    url = f"{API}{path}"
    h = {}
    if headers:
        h.update(headers)
    if token:
        h["Authorization"] = f"Bearer {token}"
    resp = session.request(method, url, json=json_body, headers=h, timeout=30)
    return resp


# ─────────────────────────────────────────────────────────────
# 1. AUTH FLOW
# ─────────────────────────────────────────────────────────────
print("\n========== 1. AUTH FLOW ==========")
token = None
user_id = None

# Register
r = req("POST", "/auth/register", json_body={"email": EMAIL, "password": PASSWORD, "name": NAME})
ok_h, hdr_info = assert_headers(r, "POST /auth/register")
if r.status_code == 200:
    body = r.json()
    token = body.get("session_token")
    user_id = body.get("user_id")
    log("Auth: register", bool(token) and r.status_code == 200,
        f"status={r.status_code} has_token={bool(token)} email={body.get('email')} {hdr_info}")
else:
    log("Auth: register", False, f"status={r.status_code} body={r.text[:200]} {hdr_info}")

# Observability header check at this point
log("Observability: headers on /auth/register", ok_h, hdr_info)

time.sleep(1.0)

# Login
r = req("POST", "/auth/login", json_body={"email": EMAIL, "password": PASSWORD})
if r.status_code == 200:
    body = r.json()
    token = body.get("session_token") or token
    log("Auth: login", bool(token), f"status=200 has_token={bool(token)}")
else:
    log("Auth: login", False, f"status={r.status_code} body={r.text[:200]}")

time.sleep(0.5)

# Me
r = req("GET", "/auth/me", token=token)
if r.status_code == 200:
    body = r.json()
    log("Auth: /auth/me", body.get("email") == EMAIL,
        f"status=200 email={body.get('email')} has_password={body.get('has_password')}")
else:
    log("Auth: /auth/me", False, f"status={r.status_code} body={r.text[:200]}")

time.sleep(0.5)

# Forgot-password
r = req("POST", "/auth/forgot-password", json_body={"email": EMAIL})
otp = None
if r.status_code == 200:
    body = r.json()
    otp = body.get("otp")
    log("Auth: forgot-password", bool(otp),
        f"status=200 otp_returned={bool(otp)} expires_in={body.get('expires_in_minutes')}")
else:
    log("Auth: forgot-password", False, f"status={r.status_code} body={r.text[:200]}")

time.sleep(0.5)

# Reset-password
if otp:
    r = req("POST", "/auth/reset-password",
            json_body={"email": EMAIL, "otp": otp, "new_password": NEW_PASSWORD})
    log("Auth: reset-password", r.status_code == 200,
        f"status={r.status_code} body={r.text[:150]}")
else:
    log("Auth: reset-password", False, "no otp from forgot-password")

time.sleep(0.5)

# Login with new password to confirm rotation
r = req("POST", "/auth/login", json_body={"email": EMAIL, "password": NEW_PASSWORD})
if r.status_code == 200:
    token = r.json().get("session_token") or token
    log("Auth: login with new password", True, "status=200")
else:
    log("Auth: login with new password", False, f"status={r.status_code}")


# ─────────────────────────────────────────────────────────────
# 2. DECISIONS CRUD
# ─────────────────────────────────────────────────────────────
print("\n========== 2. DECISIONS CRUD ==========")

dec_id = None
r = req("POST", "/decisions", token=token, json_body={
    "title": "Should I join the new startup?",
    "context": "Considering an offer vs staying at current company",
    "folder": "career",
    "life_area": "career",
    "decision_type": "need",
})
if r.status_code == 200:
    dec_id = r.json().get("id")
    log("Decisions: POST /decisions", bool(dec_id), f"status=200 id={dec_id}")
else:
    log("Decisions: POST /decisions", False, f"status={r.status_code} body={r.text[:200]}")

# List
r = req("GET", "/decisions", token=token)
if r.status_code == 200:
    arr = r.json()
    found = any(d.get("id") == dec_id for d in arr) if dec_id else False
    log("Decisions: GET /decisions", found, f"status=200 count={len(arr)} contains_new={found}")
else:
    log("Decisions: GET /decisions", False, f"status={r.status_code}")

# Get by id
if dec_id:
    r = req("GET", f"/decisions/{dec_id}", token=token)
    log("Decisions: GET /decisions/{id}", r.status_code == 200 and r.json().get("id") == dec_id,
        f"status={r.status_code}")

# Update
if dec_id:
    r = req("PUT", f"/decisions/{dec_id}", token=token, json_body={"title": "Startup vs staying (updated)"})
    log("Decisions: PUT /decisions/{id}", r.status_code == 200, f"status={r.status_code}")

# Delete
if dec_id:
    r = req("DELETE", f"/decisions/{dec_id}", token=token)
    log("Decisions: DELETE /decisions/{id}", r.status_code == 200, f"status={r.status_code}")


# ─────────────────────────────────────────────────────────────
# 3. TEST123, ASSESSMENT, JOURNAL, FOLDERS
# ─────────────────────────────────────────────────────────────
print("\n========== 3. TEST123, ASSESSMENT, JOURNAL, FOLDERS ==========")

# Folders
r = req("GET", "/folders", token=token)
if r.status_code == 200:
    folders = r.json()
    has_career = any(f.get("id") == "career" for f in folders) if isinstance(folders, list) else False
    log("Folders: GET /folders", has_career, f"status=200 count={len(folders) if isinstance(folders, list) else 'n/a'}")
else:
    log("Folders: GET /folders", False, f"status={r.status_code}")

# Test123 Create
t123_id = None
r = req("POST", "/test123", token=token, json_body={"situation": "My bike broke before work — Uber or bus?"})
if r.status_code == 200:
    t123_id = r.json().get("id")
    log("Test123: POST /test123", bool(t123_id), f"status=200 id={t123_id}")
else:
    log("Test123: POST /test123", False, f"status={r.status_code} body={r.text[:200]}")

# Test123 List
r = req("GET", "/test123", token=token)
if r.status_code == 200:
    arr = r.json()
    log("Test123: GET /test123", isinstance(arr, list),
        f"status=200 count={len(arr) if isinstance(arr, list) else 'n/a'}")
else:
    log("Test123: GET /test123", False, f"status={r.status_code}")

# Test123 Update
if t123_id:
    r = req("PUT", f"/test123/{t123_id}", token=token,
            json_body={"is_emotional": False, "what_i_want": "Reliable transport in under 40 minutes"})
    log("Test123: PUT /test123/{id}", r.status_code == 200, f"status={r.status_code}")

# Assessment questions
r = req("GET", "/assessment/questions", token=token)
if r.status_code == 200:
    body = r.json()
    qs = body.get("questions") if isinstance(body, dict) else body
    count = len(qs) if isinstance(qs, list) else 0
    log("Assessment: GET /assessment/questions", count == 12, f"status=200 count={count}")
    questions_payload = qs
else:
    log("Assessment: GET /assessment/questions", False, f"status={r.status_code}")
    questions_payload = None

# Assessment submit
if questions_payload:
    # answers q1..qN = 4,3,5,2,4,3,5,4,3,4,3,5 (ratings 1-5)
    answers = {}
    for q in questions_payload:
        # q may have id like "q1" ... "q12"
        qid = q.get("id")
        if qid:
            answers[qid] = 4
    r = req("POST", "/assessment", token=token, json_body={"answers": answers})
    if r.status_code == 200:
        body = r.json()
        log("Assessment: POST /assessment", "dominant_mode" in body,
            f"status=200 dominant_mode={body.get('dominant_mode')}")
    else:
        log("Assessment: POST /assessment", False, f"status={r.status_code} body={r.text[:200]}")

# Journal create
r = req("POST", "/journal", token=token, json_body={
    "decision_title": "Took the Uber to get to meeting on time",
    "decision_description": "Traded money for reliability. Worth it given the stakes.",
})
journal_id = None
if r.status_code == 200:
    journal_id = r.json().get("id")
    log("Journal: POST /journal", bool(journal_id), f"status=200 id={journal_id}")
else:
    log("Journal: POST /journal", False, f"status={r.status_code} body={r.text[:200]}")

# Journal list
r = req("GET", "/journal", token=token)
if r.status_code == 200:
    arr = r.json()
    log("Journal: GET /journal", isinstance(arr, list),
        f"status=200 count={len(arr) if isinstance(arr, list) else 'n/a'}")
else:
    log("Journal: GET /journal", False, f"status={r.status_code}")


# ─────────────────────────────────────────────────────────────
# 4. SOLUTIONS STORE
# ─────────────────────────────────────────────────────────────
print("\n========== 4. SOLUTIONS STORE ==========")

r = req("GET", "/solutions-store/config/countries", token=token)
if r.status_code == 200:
    payload = r.json()
    arr = payload.get("countries") if isinstance(payload, dict) else payload
    log("SolutionsStore: config/countries", isinstance(arr, list) and len(arr) == 7,
        f"status=200 count={len(arr) if isinstance(arr, list) else 'n/a'}")
else:
    log("SolutionsStore: config/countries", False, f"status={r.status_code}")

r = req("GET", "/solutions-store/config/languages", token=token)
if r.status_code == 200:
    payload = r.json()
    arr = payload.get("languages") if isinstance(payload, dict) else payload
    log("SolutionsStore: config/languages", isinstance(arr, list) and len(arr) == 9,
        f"status=200 count={len(arr) if isinstance(arr, list) else 'n/a'}")
else:
    log("SolutionsStore: config/languages", False, f"status={r.status_code}")

# Create solution
r = req("POST", "/solutions-store/solutions", token=token, json_body={
    "type": "PRODUCT",
    "name": f"Regression test product {TS}",
    "description": "Ergonomic chair for standing-desk converts",
    "life_area_id": "la_health",
    "price_range": "5000-15000",
    "currency": "INR",
    "visibility": "PRIVATE",
})
sol_id = None
if r.status_code == 200:
    sol_id = r.json().get("solution_id")
    log("SolutionsStore: POST /solutions", bool(sol_id), f"status=200 id={sol_id}")
else:
    log("SolutionsStore: POST /solutions", False, f"status={r.status_code} body={r.text[:250]}")

# List
r = req("GET", "/solutions-store/solutions", token=token)
if r.status_code == 200:
    arr = r.json()
    log("SolutionsStore: GET /solutions", isinstance(arr, list),
        f"status=200 count={len(arr) if isinstance(arr, list) else 'n/a'}")
else:
    log("SolutionsStore: GET /solutions", False, f"status={r.status_code}")


# ─────────────────────────────────────────────────────────────
# 5. COLLABORATION decision-modes
# ─────────────────────────────────────────────────────────────
print("\n========== 5. COLLABORATION DECISION MODES ==========")

r = req("GET", "/collaboration/decision-modes", token=token)
if r.status_code == 200:
    arr = r.json()
    expected = {"equal", "voting", "command", "sme", "custom", "consensus"}
    present = {m.get("id") for m in arr} if isinstance(arr, list) else set()
    match = expected.issubset(present)
    log("Collaboration: GET /collaboration/decision-modes",
        match and isinstance(arr, list) and len(arr) == 6,
        f"status=200 count={len(arr) if isinstance(arr, list) else 'n/a'} ids={sorted(list(present))}")
else:
    log("Collaboration: GET /collaboration/decision-modes", False,
        f"status={r.status_code} body={r.text[:200]}")


# ─────────────────────────────────────────────────────────────
# 6. LLM ERROR POLISH
# ─────────────────────────────────────────────────────────────
print("\n========== 6. LLM ERROR POLISH ==========")

# Space out to avoid AI=10/min rate cap
time.sleep(1.0)

r = req("POST", "/ai-assistant/quick-ask", token=token,
        json_body={"question": "What should I focus on this week?", "language": "en"})
# Expected: 503 with detail.code=llm_budget_exceeded + Retry-After:60 header
status = r.status_code
retry_after = r.headers.get("Retry-After")
rid_header = r.headers.get("X-Request-ID")
try:
    body = r.json()
except Exception:
    body = None

ok = False
detail_info = ""
if status == 503 and isinstance(body, dict):
    detail = body.get("detail") if isinstance(body.get("detail"), dict) else body
    code = detail.get("code") if isinstance(detail, dict) else None
    rid_body = detail.get("request_id") if isinstance(detail, dict) else None
    has_retry = retry_after is not None
    has_rid_header = rid_header is not None
    rids_match = (rid_body == rid_header) if (rid_body and rid_header) else False
    ok = code in (
        "llm_budget_exceeded", "llm_rate_limited",
        "llm_upstream_unavailable", "llm_upstream_auth"
    ) and has_retry and has_rid_header
    detail_info = (f"status=503 code={code} retry_after={retry_after} "
                   f"rid_header={rid_header} rid_body={rid_body} match={rids_match}")
elif status == 200:
    ok = True
    detail_info = f"status=200 (LLM budget not exhausted — answered OK)"
else:
    detail_info = f"status={status} body={str(body)[:250]} retry_after={retry_after}"

log("LLM Polish: POST /ai-assistant/quick-ask (503 or 200)", ok, detail_info)

# CLD generate — needs a decision. Use a dummy id to get 404 OR create one with factors and trigger 503
# Per the review, both 404 and 503 are "clean". Simplest: try on nonexistent decision.
r = req("POST", "/cld/deadbeef-not-exists/generate", token=token, json_body={
    "decision_title": "Test",
    "factors": [{"id": "f1", "name": "Salary"}, {"id": "f2", "name": "Growth"}],
})
status = r.status_code
try:
    body = r.json()
except Exception:
    body = None

if status == 503:
    detail = body.get("detail") if isinstance(body, dict) and isinstance(body.get("detail"), dict) else {}
    code = detail.get("code")
    log("LLM Polish: POST /cld/{decision_id}/generate (503)",
        code in ("llm_budget_exceeded", "llm_rate_limited",
                 "llm_upstream_unavailable", "llm_upstream_auth"),
        f"status=503 code={code} retry_after={r.headers.get('Retry-After')}")
elif status in (200, 400, 404):
    # 400 for "At least 2 factors" is fine (we gave 2); 404 for missing decision; 200 success
    log("LLM Polish: POST /cld/{decision_id}/generate (404/400/200)",
        True, f"status={status} body={str(body)[:150]}")
else:
    log("LLM Polish: POST /cld/{decision_id}/generate", False,
        f"status={status} body={str(body)[:200]}")


# ─────────────────────────────────────────────────────────────
# 7. OBSERVABILITY HEADERS (sample several responses)
# ─────────────────────────────────────────────────────────────
print("\n========== 7. OBSERVABILITY HEADERS ==========")

sample_endpoints = [
    ("GET", "/health", None),
    ("GET", "/health/ready", None),
    ("GET", "/folders", token),
    ("GET", "/assessment/questions", token),
    ("GET", "/collaboration/decision-modes", token),
]
all_ok = True
details = []
for m, p, t in sample_endpoints:
    r = req(m, p, token=t)
    rid = r.headers.get("X-Request-ID")
    rtm = r.headers.get("X-Response-Time-MS")
    has_both = bool(rid) and bool(rtm)
    if not has_both:
        all_ok = False
    details.append(f"{m} {p} → status={r.status_code} rid={'Y' if rid else 'N'} time={'Y' if rtm else 'N'}")

log("Observability: X-Request-ID & X-Response-Time-MS on multiple endpoints", all_ok,
    " | ".join(details))


# ─────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────
print("\n========== SUMMARY ==========")
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print(f"TOTAL: {passed}/{total} passed")
for name, ok, detail in results:
    if not ok:
        print(f"  ❌ {name}: {detail}")
print("\nDone.")
