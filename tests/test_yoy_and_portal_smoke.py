"""
Smoke test — Public Pulse Phase 3 (YoY analytics) + Sub-Portal embed endpoints.

This test does NOT require seeded org data; it verifies endpoints respond with
proper status codes and shapes. Real-data assertions (k-anonymity unblock,
branded HTML output) require seeded org records.
"""
import os
import sys
import time
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8001")
API = f"{BASE_URL}/api"


class Results:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors: list = []

    def check(self, condition, label, detail=""):
        if condition:
            self.passed += 1
            print(f"  OK  {label}")
        else:
            self.failed += 1
            self.errors.append(f"{label}: {detail}")
            print(f"  FAIL {label}{(' - ' + detail) if detail else ''}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*70}\nYoY+Portal smoke - {self.passed}/{total} passed\n{'='*70}")
        if self.errors:
            print("\nFailures:")
            for e in self.errors:
                print(f"  - {e}")
        return self.failed == 0


def main():
    r = Results()
    print("\n" + "="*70 + "\n YoY + Portal Smoke Test\n" + "="*70)

    # ----- YoY -----
    print("\n[YoY] Overall")
    res = requests.get(f"{API}/public-pulse/analytics/yoy/overall", timeout=10)
    r.check(res.status_code == 200, "yoy/overall returns 200", f"status={res.status_code}")
    data = res.json()
    r.check(data.get("dashboard") == "yoy_overall", "yoy/overall reports correct dashboard key")
    r.check("k_threshold" in data, "yoy/overall has k_threshold")
    if not data.get("blocked"):
        r.check("series" in data and isinstance(data["series"], list),
                "yoy/overall has series list")
        r.check("current_year_total" in data, "yoy/overall has current_year_total")

    print("\n[YoY] Feedback")
    res = requests.get(f"{API}/public-pulse/analytics/yoy/feedback", timeout=10)
    r.check(res.status_code == 200, "yoy/feedback returns 200")
    fb_data = res.json()
    r.check(fb_data.get("dashboard") == "yoy_feedback", "yoy/feedback reports correct dashboard key")

    print("\n[YoY] Tool — known slug")
    res = requests.get(f"{API}/public-pulse/analytics/yoy/tool/life_direction", timeout=10)
    r.check(res.status_code == 200, "yoy/tool/life_direction returns 200",
            f"status={res.status_code}")
    tool_data = res.json()
    r.check(tool_data.get("dashboard") == "yoy_tool_life_direction",
            "yoy/tool reports correct dashboard key")

    print("\n[YoY] Tool — unknown slug")
    res = requests.get(f"{API}/public-pulse/analytics/yoy/tool/does_not_exist", timeout=10)
    r.check(res.status_code == 404, "yoy/tool unknown slug returns 404",
            f"status={res.status_code}")

    # ----- Portal endpoints -----
    print("\n[Portal] /p/{slug} unknown")
    res = requests.get(f"{API}/p/this-slug-cannot-exist-{int(time.time())}", timeout=10)
    r.check(res.status_code == 404, "GET /p/{slug} unknown returns 404")

    print("\n[Portal] /embed/{slug} unknown")
    res = requests.get(f"{API}/embed/this-slug-cannot-exist-{int(time.time())}", timeout=10)
    r.check(res.status_code == 404, "GET /embed/{slug} unknown returns 404")

    print("\n[Portal] /embed/{slug}/widget.js unknown")
    res = requests.get(f"{API}/embed/this-slug-cannot-exist-{int(time.time())}/widget.js", timeout=10)
    r.check(res.status_code == 404, "GET /embed/{slug}/widget.js unknown returns 404")

    print("\n[Portal] /p/{slug}/feedback unknown POST")
    res = requests.post(
        f"{API}/p/this-slug-cannot-exist-{int(time.time())}/feedback",
        json={"feedback_type": "suggestion", "title": "x", "description": "y"},
        timeout=10,
    )
    r.check(res.status_code == 404, "POST /p/{slug}/feedback unknown returns 404",
            f"status={res.status_code}")

    # Try with an approved org if any exists in the DB. Best-effort discovery.
    print("\n[Portal] Find any approved org (best-effort)")
    # Register a user, look at org listings — but the public listing endpoint may not exist.
    # Instead just probe for a likely admin endpoint to fetch one slug:
    try:
        # Use admin probe via mongo-style query indirectly: admin orgs list
        # (this requires admin auth so it's expected to 401/403)
        admin_probe = requests.get(f"{API}/public-pulse/admin/orgs?status=approved&limit=1", timeout=5)
        r.check(admin_probe.status_code in (401, 403, 404, 200),
                "admin orgs probe responds (auth-gated or not-implemented)",
                f"status={admin_probe.status_code}")
    except Exception:
        pass

    return r.summary()


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
