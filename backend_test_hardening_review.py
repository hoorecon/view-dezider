"""
Hardening review verification tests.
Covers items (2)-(12) from the review request that go beyond the existing
4 test suites.
"""
import io
import json
import time
import uuid
import requests

BASE = "http://localhost:8001/api"

PASS = 0
FAIL = 0
FAILS = []


def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  OK  {label}")
    else:
        FAIL += 1
        FAILS.append(f"{label} :: {detail}")
        print(f"  FAIL {label} :: {detail}")


def section(name):
    print(f"\n=== {name} ===")


# ---------------------------------------------------------------------------
# 0. Setup: register fresh user
# ---------------------------------------------------------------------------
section("Setup: register fresh user")
ts = int(time.time())
email = f"reviewer.priya.{ts}@dezider-test.in"
payload = {"email": email, "password": "ReviewPass!2026", "name": "Priya Sharma"}
r = requests.post(f"{BASE}/auth/register", json=payload, timeout=10)
check("register fresh user", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
TOKEN = r.json().get("session_token") if r.status_code == 200 else None
H = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}


# ---------------------------------------------------------------------------
# (2) Security headers — sample of routes
# ---------------------------------------------------------------------------
section("(2) Security headers")
r = requests.get(f"{BASE}/health")
hdrs = {k.lower(): v for k, v in r.headers.items()}
check("/health X-Content-Type-Options=nosniff",
      hdrs.get("x-content-type-options", "").lower() == "nosniff",
      f"got={hdrs.get('x-content-type-options')}")
check("/health Referrer-Policy present", "referrer-policy" in hdrs, "")
check("/health Permissions-Policy present", "permissions-policy" in hdrs, "")
check("/health Content-Security-Policy present",
      "content-security-policy" in hdrs, "")
check("/health X-Frame-Options=SAMEORIGIN",
      hdrs.get("x-frame-options", "").upper() == "SAMEORIGIN",
      f"got={hdrs.get('x-frame-options')}")

# embed override
r2 = requests.get(f"{BASE}/embed/coimbatore-skills-foundation-5b9c19")
hdrs2 = {k.lower(): v for k, v in r2.headers.items()}
xf = hdrs2.get("x-frame-options", "").upper()
check("embed status 200", r2.status_code == 200, f"status={r2.status_code}")
check("embed X-Frame-Options=ALLOWALL (override)",
      xf == "ALLOWALL", f"got={xf}")

# HSTS not set when scheme=http and DEZIDER_ENV=dev
check("HSTS not set on dev/http", "strict-transport-security" not in hdrs,
      f"got={hdrs.get('strict-transport-security')}")


# ---------------------------------------------------------------------------
# (3) Body cap — 11 MB body should 413, normal body fine
# ---------------------------------------------------------------------------
section("(3) Body cap")
big = b"X" * (11 * 1024 * 1024)
try:
    r = requests.post(f"{BASE}/auth/login", data=big,
                      headers={"Content-Type": "application/json",
                               "Content-Length": str(len(big))}, timeout=15)
    check("11 MB body returns 413", r.status_code == 413,
          f"status={r.status_code}")
except requests.exceptions.RequestException as e:
    check("11 MB body returns 413", False, f"exception={e}")

# normal body works (login fail with 401 is acceptable proof normal body passes)
r = requests.post(f"{BASE}/auth/login",
                  json={"email": email, "password": "ReviewPass!2026"})
check("normal-sized POST goes through", r.status_code in (200, 401),
      f"status={r.status_code}")


# ---------------------------------------------------------------------------
# (4) DPDP roundtrip
# ---------------------------------------------------------------------------
section("(4) DPDP / GDPR roundtrip")
r = requests.get(f"{BASE}/dpdp/status", headers=H)
check("dpdp/status default=none", r.status_code == 200 and
      r.json().get("deletion_status") == "none",
      f"status={r.status_code} body={r.text[:200]}")

r = requests.get(f"{BASE}/dpdp/export", headers=H)
ok_export = r.status_code == 200
body = r.json() if ok_export else {}
check("dpdp/export returns 200", ok_export, f"status={r.status_code}")
check("dpdp/export contains user_id+email",
      body.get("user_id") and body.get("email") == email,
      f"keys={list(body.keys())[:5]}")

r = requests.post(f"{BASE}/dpdp/delete-request", headers=H)
ok = r.status_code == 200 and r.json().get("deletion_status") == "pending"
check("dpdp/delete-request returns pending", ok, f"body={r.text[:200]}")
grace = r.json().get("grace_until") if ok else None
check("dpdp/delete-request grace_until present", bool(grace),
      f"grace={grace}")

r = requests.get(f"{BASE}/dpdp/status", headers=H)
check("dpdp/status reflects pending",
      r.status_code == 200 and r.json().get("deletion_status") == "pending",
      f"body={r.text[:200]}")

r = requests.post(f"{BASE}/dpdp/cancel-delete", headers=H)
check("dpdp/cancel-delete returns cancelled",
      r.status_code == 200 and r.json().get("deletion_status") == "cancelled",
      f"body={r.text[:200]}")

r = requests.get(f"{BASE}/dpdp/status", headers=H)
check("dpdp/status returns to none",
      r.status_code == 200 and r.json().get("deletion_status") == "none",
      f"body={r.text[:200]}")

r = requests.post(f"{BASE}/dpdp/cancel-delete", headers=H)
check("dpdp/cancel-delete with no pending returns 400",
      r.status_code == 400, f"status={r.status_code}")

r = requests.get(f"{BASE}/dpdp/admin/audit-log", headers=H)
check("dpdp admin audit-log denied for non-admin (401/403)",
      r.status_code in (401, 403), f"status={r.status_code}")

r = requests.post(f"{BASE}/dpdp/admin/purge-pending", headers=H)
check("dpdp admin purge-pending denied for non-admin (401/403)",
      r.status_code in (401, 403), f"status={r.status_code}")


# ---------------------------------------------------------------------------
# (5) Metrics + health endpoints
# ---------------------------------------------------------------------------
section("(5) Metrics + Health")
r = requests.get(f"{BASE}/metrics")
check("/metrics returns 200", r.status_code == 200, f"status={r.status_code}")
check("/metrics body contains http_requests_total",
      "http_requests_total" in r.text,
      f"body[:200]={r.text[:200]}")

r = requests.get(f"{BASE}/metrics/json", headers=H)
check("/metrics/json denied for non-admin",
      r.status_code in (401, 403), f"status={r.status_code}")

r = requests.get(f"{BASE}/health/live")
ok = r.status_code == 200
body = r.json() if ok else {}
check("/health/live 200", ok, f"status={r.status_code}")
check("/health/live body status=alive", body.get("status") == "alive",
      f"body={body}")

r = requests.get(f"{BASE}/health/version")
ok = r.status_code == 200
body = r.json() if ok else {}
check("/health/version 200", ok, f"status={r.status_code}")
check("/health/version returns version+commit+env",
      "version" in body and "commit" in body and "env" in body,
      f"keys={list(body.keys())}")


# ---------------------------------------------------------------------------
# (6) Admin docs API
# ---------------------------------------------------------------------------
section("(6) Admin docs")
r = requests.get(f"{BASE}/admin-docs", headers=H)
check("/admin-docs denied for non-admin",
      r.status_code in (401, 403), f"status={r.status_code} body={r.text[:200]}")
r = requests.get(f"{BASE}/admin-docs/PRD", headers=H)
check("/admin-docs/PRD denied for non-admin",
      r.status_code in (401, 403), f"status={r.status_code}")


# ---------------------------------------------------------------------------
# (7) Audit log on DPDP actions (indirect — confirm rows exist by using
#     no-admin token gate then checking DB via collection peek if possible)
#  We've already triggered dpdp.delete_request and dpdp.delete_cancel above.
#  Without admin, we can't view, but we can verify gates are correct (done).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# (8) PII redaction in logs
# ---------------------------------------------------------------------------
section("(8) PII redaction in supervisor logs")
import subprocess
# Tail logs and look for plain test email vs redaction
log = subprocess.run(["tail", "-n", "500", "/var/log/supervisor/backend.err.log"],
                     capture_output=True, text=True)
combined = log.stdout + log.stderr
plain_count = combined.count(email)
redacted_count = combined.count("[email-redacted]")
check("test email NOT plain in backend logs (PII redaction)",
      plain_count == 0,
      f"plain occurrences={plain_count} (sample log lines containing it: see file)")
print(f"     ℹ️  redaction marker count in last 500 lines: {redacted_count}")


# ---------------------------------------------------------------------------
# (10) Solution Matrix end-to-end regression
# ---------------------------------------------------------------------------
section("(10) Solution Matrix end-to-end")

# matrix_mode standard with aggregate slot data
matrix_payload = {
    "title": "Standard Mode Aggregate Test",
    "matrix_mode": "standard",
    "matrix_self": {
        "aggregate": {"summary": "Health goals", "knowledge_skills": "RxKB",
                      "capacity": "5h/wk", "time": "6mo", "people": "Coach",
                      "finance": 5000, "infrastructure": "Gym"}
    },
}
r = requests.post(f"{BASE}/solution-matrices", headers=H, json=matrix_payload)
ok = r.status_code in (200, 201)
mid = r.json().get("entry_id") if ok else None
check("Create standard-mode + aggregate matrix", ok and bool(mid),
      f"status={r.status_code} body={r.text[:200]}")

if mid:
    r = requests.get(f"{BASE}/solution-matrices/{mid}", headers=H)
    body = r.json() if r.status_code == 200 else {}
    check("GET back persisted matrix_mode=standard",
          body.get("matrix_mode") == "standard",
          f"got={body.get('matrix_mode')}")
    agg = (body.get("matrix_self") or {}).get("aggregate") or {}
    check("standard aggregate slot has data",
          agg.get("summary") == "Health goals",
          f"agg={agg}")
    requests.delete(f"{BASE}/solution-matrices/{mid}", headers=H)

# matrix_mode accurate with 4 OrgType slots
matrix_payload2 = {
    "title": "Accurate Mode 4-Slot Test",
    "matrix_mode": "accurate",
    "matrix_self": {
        "individual": {"summary": "I-row", "knowledge_skills": "k1",
                       "capacity": "c1", "time": "t1", "people": "p1",
                       "finance": 100, "infrastructure": "i1"},
        "org": {"summary": "Org-row", "knowledge_skills": "k2",
                "capacity": "c2", "time": "t2", "people": "p2",
                "finance": 200, "infrastructure": "i2"},
        "govt": {"summary": "Govt-row", "knowledge_skills": "k3",
                 "capacity": "c3", "time": "t3", "people": "p3",
                 "finance": 300, "infrastructure": "i3"},
        "nature": {"summary": "Nature-row", "knowledge_skills": "k4",
                   "capacity": "c4", "time": "t4", "people": "p4",
                   "finance": 400, "infrastructure": "i4"},
    },
}
r = requests.post(f"{BASE}/solution-matrices", headers=H, json=matrix_payload2)
ok = r.status_code in (200, 201)
mid2 = r.json().get("entry_id") if ok else None
check("Create accurate-mode 4-OrgType matrix", ok and bool(mid2),
      f"status={r.status_code} body={r.text[:300]}")
if mid2:
    r = requests.get(f"{BASE}/solution-matrices/{mid2}", headers=H)
    body = r.json() if r.status_code == 200 else {}
    check("GET back matrix_mode=accurate", body.get("matrix_mode") == "accurate",
          f"got={body.get('matrix_mode')}")
    self_layer = body.get("matrix_self") or {}
    keys = set(self_layer.keys())
    check("All 4 OrgType slots present in matrix_self",
          {"individual", "org", "govt", "nature"} <= keys,
          f"keys={keys}")

# Templates endpoint returns 4+ entries
r = requests.get(f"{BASE}/solution-matrices/templates", headers=H)
ok = r.status_code == 200
body = r.json() if ok else {}
items = body.get("templates") or body.get("items") or body if isinstance(body, list) else body
if isinstance(body, dict):
    # try several shapes
    candidates = body.get("templates") or body.get("items") or []
else:
    candidates = body
check("/solution-matrices/templates returns 4+ entries",
      isinstance(candidates, list) and len(candidates) >= 4,
      f"status={r.status_code} count={len(candidates) if isinstance(candidates, list) else 'N/A'} body={str(body)[:200]}")

# PDF for created entry
if mid2:
    r = requests.get(f"{BASE}/solution-matrices/{mid2}/pdf", headers=H)
    ct = r.headers.get("content-type", "")
    check("Solution matrix PDF returns 200", r.status_code == 200,
          f"status={r.status_code}")
    check("PDF content-type is application/pdf", ct.startswith("application/pdf"),
          f"got={ct}")
    check("PDF body starts with %PDF", r.content.startswith(b"%PDF"),
          f"first8={r.content[:8]}")
    requests.delete(f"{BASE}/solution-matrices/{mid2}", headers=H)


# ---------------------------------------------------------------------------
# (11) Public Pulse YoY
# ---------------------------------------------------------------------------
section("(11) Public Pulse YoY")
r = requests.get(f"{BASE}/public-pulse/analytics/yoy/overall", headers=H)
check("yoy/overall 200", r.status_code == 200,
      f"status={r.status_code} body={r.text[:200]}")
if r.status_code == 200:
    check("yoy/overall dashboard=yoy_overall",
          r.json().get("dashboard") == "yoy_overall",
          f"got={r.json().get('dashboard')}")

r = requests.get(f"{BASE}/public-pulse/analytics/yoy/feedback", headers=H)
check("yoy/feedback 200", r.status_code == 200, f"status={r.status_code}")
if r.status_code == 200:
    check("yoy/feedback dashboard=yoy_feedback",
          r.json().get("dashboard") == "yoy_feedback",
          f"got={r.json().get('dashboard')}")

r = requests.get(f"{BASE}/public-pulse/analytics/yoy/tool/life_direction",
                 headers=H)
check("yoy/tool/life_direction 200", r.status_code == 200,
      f"status={r.status_code}")

r = requests.get(f"{BASE}/public-pulse/analytics/yoy/tool/does_not_exist",
                 headers=H)
check("yoy/tool/does_not_exist returns 404", r.status_code == 404,
      f"status={r.status_code}")


# ---------------------------------------------------------------------------
# (12) Public sub-portal (no auth needed for portal/embed/widget; auth optional
#      for feedback)
# ---------------------------------------------------------------------------
section("(12) Public sub-portal")
slug = "coimbatore-skills-foundation-5b9c19"

r = requests.get(f"{BASE}/p/{slug}")
ok = r.status_code == 200
body = r.json() if ok else {}
check("/p/{slug} 200 with branding payload", ok and "display_name" in body,
      f"status={r.status_code} body={str(body)[:200]}")

r = requests.get(f"{BASE}/embed/{slug}")
check("/embed/{slug} 200 HTML", r.status_code == 200 and
      "text/html" in r.headers.get("content-type", ""),
      f"status={r.status_code} ct={r.headers.get('content-type')}")

r = requests.get(f"{BASE}/embed/{slug}/widget.js")
check("/embed/{slug}/widget.js 200 application/javascript",
      r.status_code == 200 and
      "javascript" in r.headers.get("content-type", ""),
      f"status={r.status_code} ct={r.headers.get('content-type')}")

# POST feedback no auth
r = requests.post(
    f"{BASE}/p/{slug}/feedback",
    json={"feedback_type": "suggestion", "title": "Reviewer note",
          "description": "Verifying anonymous portal feedback works"},
)
check("POST feedback to /p/{slug} without auth returns 200",
      r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")

# POST feedback bad type
r = requests.post(
    f"{BASE}/p/{slug}/feedback",
    json={"feedback_type": "bogus_type", "title": "x", "description": "y"},
)
check("POST feedback with bad type returns 400", r.status_code == 400,
      f"status={r.status_code} body={r.text[:200]}")


# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print(f"REVIEW VERIFICATION  —  {PASS} passed, {FAIL} failed")
print("=" * 70)
if FAILS:
    print("\nFAIL DETAILS:")
    for f in FAILS:
        print(f"  ✗ {f}")
