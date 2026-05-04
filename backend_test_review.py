"""
Supplementary backend review tests — covers review-request items not
already fully asserted by the existing /app/tests/test_*.py suites.

Focus:
  - YoY analytics for marriage_readiness and govt_benefit_finder (+ 404 unknown)
  - White-label portal positive path against a REAL approved org from pp_orgs
  - Portal negative paths (invalid feedback_type, empty title, unknown slug)
  - Auth /me without auth → 401
"""
import os
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8001")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ.get("DB_NAME", "test_database")


class R:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.fails = []

    def ok(self, cond, label, detail=""):
        if cond:
            self.passed += 1
            print(f"  OK  {label}")
        else:
            self.failed += 1
            self.fails.append(f"{label}: {detail}")
            print(f"  FAIL {label} -- {detail}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'=' * 70}\nReview Supplementary: {self.passed}/{total} passed\n{'=' * 70}")
        for e in self.fails:
            print(f"  - {e}")
        return self.failed == 0


def get_approved_slug():
    c = MongoClient(MONGO_URL)
    db = c[DB_NAME]
    row = db.pp_orgs.find_one({"status": "approved"}, {"_id": 0, "slug": 1, "display_name": 1})
    c.close()
    return row


def test_auth_me_unauth(r):
    print("\n[Auth] GET /auth/me without auth")
    resp = requests.get(f"{API}/auth/me")
    r.ok(resp.status_code == 401, "GET /auth/me no-auth returns 401", f"got {resp.status_code}")


def test_yoy_all_tools(r):
    print("\n[YoY] All required tool slugs + unknown")
    for slug in ["marriage_readiness", "govt_benefit_finder"]:
        resp = requests.get(f"{API}/public-pulse/analytics/yoy/tool/{slug}")
        r.ok(resp.status_code == 200, f"yoy/tool/{slug} returns 200",
             f"got {resp.status_code} body={resp.text[:200]}")
        if resp.status_code == 200:
            body = resp.json()
            r.ok(body.get("dashboard") == f"yoy_tool_{slug}",
                 f"yoy/tool/{slug} dashboard key correct",
                 f"dashboard={body.get('dashboard')}")
    # unknown
    resp = requests.get(f"{API}/public-pulse/analytics/yoy/tool/does_not_exist")
    r.ok(resp.status_code == 404, "yoy/tool/does_not_exist returns 404",
         f"got {resp.status_code}")


def test_portal_404s(r):
    print("\n[Portal] 404 paths")
    resp = requests.get(f"{API}/p/does-not-exist")
    r.ok(resp.status_code == 404, "/p/does-not-exist returns 404")
    resp = requests.get(f"{API}/embed/does-not-exist")
    r.ok(resp.status_code == 404, "/embed/does-not-exist returns 404")
    resp = requests.get(f"{API}/embed/does-not-exist/widget.js")
    r.ok(resp.status_code == 404, "/embed/does-not-exist/widget.js returns 404")

    # POST feedback unknown slug, valid body
    body = {"feedback_type": "suggestion", "title": "hi", "description": "hello"}
    resp = requests.post(f"{API}/p/does-not-exist/feedback", json=body)
    r.ok(resp.status_code == 404, "POST /p/does-not-exist/feedback (valid body) returns 404",
         f"got {resp.status_code}")

    # unknown slug + invalid feedback_type → 404 (slug check first)
    body = {"feedback_type": "bogus", "title": "hi", "description": "hello"}
    resp = requests.post(f"{API}/p/does-not-exist/feedback", json=body)
    r.ok(resp.status_code == 404,
         "POST /p/does-not-exist/feedback (bogus type) returns 404 (slug check first)",
         f"got {resp.status_code}")


def test_portal_positive(r, org):
    slug = org["slug"]
    display_name = org["display_name"]
    print(f"\n[Portal] Positive path for real approved slug={slug}")

    # GET /api/p/{slug}
    resp = requests.get(f"{API}/p/{slug}")
    r.ok(resp.status_code == 200, f"GET /p/{slug} returns 200",
         f"got {resp.status_code} body={resp.text[:200]}")
    if resp.status_code == 200:
        body = resp.json()
        # Flexible structure check — branding fields present somewhere in payload
        flat = str(body)
        r.ok(slug in flat, "GET /p/{slug} payload contains slug")
        r.ok("primary_color" in flat or "primaryColor" in flat,
             "GET /p/{slug} payload contains primary_color")
        r.ok(display_name in flat, "GET /p/{slug} payload contains display_name")
        r.ok("config" in body or "portal_config" in body or
             any("config" in str(k).lower() for k in (body.keys() if isinstance(body, dict) else [])),
             "GET /p/{slug} payload has config object",
             f"keys={list(body.keys()) if isinstance(body, dict) else type(body)}")

    # GET /api/embed/{slug}
    resp = requests.get(f"{API}/embed/{slug}")
    r.ok(resp.status_code == 200, f"GET /embed/{slug} returns 200",
         f"got {resp.status_code}")
    if resp.status_code == 200:
        ctype = resp.headers.get("content-type", "")
        r.ok("text/html" in ctype, "embed content-type is text/html", f"got {ctype}")
        xfo = resp.headers.get("x-frame-options", "") or resp.headers.get("X-Frame-Options", "")
        r.ok(xfo.upper() == "ALLOWALL", "X-Frame-Options: ALLOWALL", f"got {xfo!r}")
        body = resp.text
        r.ok(display_name in body, "embed HTML contains display_name")
        r.ok(slug in body, "embed HTML contains slug")

    # GET /api/embed/{slug}/widget.js
    resp = requests.get(f"{API}/embed/{slug}/widget.js")
    r.ok(resp.status_code == 200, f"widget.js returns 200", f"got {resp.status_code}")
    if resp.status_code == 200:
        ctype = resp.headers.get("content-type", "")
        r.ok("javascript" in ctype.lower(), "widget.js content-type is application/javascript",
             f"got {ctype}")
        r.ok(f"/embed/{slug}" in resp.text or slug in resp.text,
             "widget.js body contains embed URL / slug")

    # POST feedback - valid, no auth
    body = {"feedback_type": "suggestion", "title": "Love this portal", "description": "Great work!"}
    resp = requests.post(f"{API}/p/{slug}/feedback", json=body)
    r.ok(resp.status_code == 200,
         f"POST /p/{slug}/feedback valid no-auth returns 200",
         f"got {resp.status_code} body={resp.text[:200]}")
    if resp.status_code == 200:
        j = resp.json()
        r.ok(j.get("ok") is True, "response ok=true")
        r.ok("feedback_id" in j, "feedback_id returned")

    # POST feedback - bogus type → 400
    body = {"feedback_type": "bogus", "title": "hi", "description": "hi"}
    resp = requests.post(f"{API}/p/{slug}/feedback", json=body)
    r.ok(resp.status_code == 400,
         f"POST /p/{slug}/feedback bogus type returns 400",
         f"got {resp.status_code}")

    # POST feedback - empty title → 400
    body = {"feedback_type": "suggestion", "title": "", "description": "some text"}
    resp = requests.post(f"{API}/p/{slug}/feedback", json=body)
    r.ok(resp.status_code == 400,
         f"POST /p/{slug}/feedback empty title returns 400",
         f"got {resp.status_code}")

    # GET /api/p/{slug}/feedback/public
    resp = requests.get(f"{API}/p/{slug}/feedback/public")
    r.ok(resp.status_code == 200,
         f"GET /p/{slug}/feedback/public returns 200",
         f"got {resp.status_code}")
    if resp.status_code == 200:
        j = resp.json()
        # Accept either list or dict with items
        items = j if isinstance(j, list) else j.get("items", j.get("feedback", []))
        r.ok(isinstance(items, list), "feedback/public returns items list",
             f"type={type(j).__name__}")


def main():
    r = R()
    test_auth_me_unauth(r)
    test_yoy_all_tools(r)
    test_portal_404s(r)

    org = get_approved_slug()
    if org:
        test_portal_positive(r, org)
    else:
        print("\n[Portal] No approved org in pp_orgs — skipping positive path")

    ok = r.summary()
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
