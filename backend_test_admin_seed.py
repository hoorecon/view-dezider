"""
Admin Data Seed verification — end-to-end tests against http://localhost:8001/api

Verifies:
  1. GET /admin/seed/status (admin) → seeded marker
  2. POST /admin/seed/run (admin) — idempotent (run twice)
  3. POST /admin/seed/run (user) → 403
  4. GET /admin/seed/status (user) → 403
  5. GET /experts?include_inactive=true — seeded experts present
  6. GET /decision-templates/all — seeded templates present
  7. GET /admin/customer-segments — seeded segments + tier_pricings
  8. GET /collaboration/decision-modes — 6 default modes
  9. GET /solutions-store/pending-approval — ≥ 6 pending entries
  10. GET /social-learning/admin/pending — ≥ 6 submitted templates
  11. GET /incidents — ≥ 4 seeded entries
  12. GET /audit-trail — ≥ 25 seeded entries
  13. Regression: /health, /branding/current, /customer-segments, /pricing
"""
import json
import sys
import requests

BASE = "http://localhost:8001/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"
USER_EMAIL = "harden_1777921741@example.com"
USER_PASS = "HardenPass2026!"

results = []
admin_token = None
user_token = None


def log(name, ok, info=""):
    status = "PASS" if ok else "FAIL"
    results.append((status, name, info))
    short = info if len(info) < 200 else info[:200] + "…"
    print(f"[{status}] {name} — {short}")


def login(email, pwd):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pwd}, timeout=15)
    r.raise_for_status()
    return r.json()["session_token"]


def H(token):
    return {"Authorization": f"Bearer {token}"}


# ── AUTH ─────────────────────────────────────────────────────────────
try:
    admin_token = login(ADMIN_EMAIL, ADMIN_PASS)
    log("0a Admin login", True, f"token={admin_token[:20]}…")
except Exception as e:
    log("0a Admin login", False, repr(e))
    print("P0 — cannot get admin token, aborting.")
    sys.exit(1)

try:
    user_token = login(USER_EMAIL, USER_PASS)
    log("0b User login", True, f"token={user_token[:20]}…")
except Exception as e:
    log("0b User login", False, repr(e))
    sys.exit(1)


# ── 1. GET /admin/seed/status (admin) ────────────────────────────────
try:
    r = requests.get(f"{BASE}/admin/seed/status", headers=H(admin_token), timeout=15)
    body = r.json()
    ok = (r.status_code == 200 and body.get("seeded") is True
          and body.get("seed_version") == "2026-06-01-01" and "summary" in body)
    log("1 GET /admin/seed/status (admin)", ok,
        f"status={r.status_code}, seeded={body.get('seeded')}, version={body.get('seed_version')}, summary_keys={list(body.get('summary', {}).keys())}")
except Exception as e:
    log("1 GET /admin/seed/status (admin)", False, repr(e))


# ── 2. POST /admin/seed/run (admin) — run twice for idempotency ──────
EXPECTED_KEYS = {
    "experts", "decision_templates", "customer_segments", "decision_modes",
    "pending_solutions", "social_learning_templates", "incidents",
    "audit_trail_events", "review_net_factors",
}
summary_run1 = summary_run2 = None
for run_idx in (1, 2):
    try:
        r = requests.post(f"{BASE}/admin/seed/run", headers=H(admin_token), timeout=60)
        body = r.json()
        s = body.get("summary", {})
        missing = EXPECTED_KEYS - set(s.keys())
        ok = (r.status_code == 200 and body.get("ok") is True and not missing)
        log(f"2.{run_idx} POST /admin/seed/run (admin)", ok,
            f"status={r.status_code}, ok={body.get('ok')}, summary={s}, missing={missing}")
        if run_idx == 1:
            summary_run1 = s
        else:
            summary_run2 = s
    except Exception as e:
        log(f"2.{run_idx} POST /admin/seed/run", False, repr(e))

# idempotency proof — second run summary should be all zeros (no new inserts) for upserted collections
# decision_modes uses $set so it'll always re-touch; that's fine. We assert no errors and same keys.
if summary_run2 is not None:
    # All upsert-on-insert counts should be 0 on the 2nd run
    setOnInsert_keys = ["experts", "decision_templates", "customer_segments",
                        "pending_solutions", "social_learning_templates",
                        "incidents", "audit_trail_events", "review_net_factors"]
    zero_second = all(summary_run2.get(k, -1) == 0 for k in setOnInsert_keys)
    log("2.3 Idempotency — 2nd run produced 0 new inserts", zero_second,
        f"second_run_summary={summary_run2}")


# ── 3. POST /admin/seed/run as USER → 403 ────────────────────────────
try:
    r = requests.post(f"{BASE}/admin/seed/run", headers=H(user_token), timeout=15)
    log("3 POST /admin/seed/run (user) → 403", r.status_code == 403, f"status={r.status_code}, body={r.text[:120]}")
except Exception as e:
    log("3 POST /admin/seed/run (user)", False, repr(e))


# ── 4. GET /admin/seed/status as USER → 403 ──────────────────────────
try:
    r = requests.get(f"{BASE}/admin/seed/status", headers=H(user_token), timeout=15)
    log("4 GET /admin/seed/status (user) → 403", r.status_code == 403, f"status={r.status_code}, body={r.text[:120]}")
except Exception as e:
    log("4 GET /admin/seed/status (user)", False, repr(e))


# ── 5. GET /experts?include_inactive=true ────────────────────────────
try:
    r = requests.get(f"{BASE}/experts?include_inactive=true", timeout=15)
    experts = r.json() if r.status_code == 200 else []
    names = [e.get("name") for e in experts]
    must_have = ["Dr. Anjali Mehra", "Rohan Iyer, CFP", "Dr. Priya Raghav, MBBS, MD"]
    missing = [n for n in must_have if n not in names]
    # Validate seeded records
    seeded = [e for e in experts if e.get("id", "").startswith("exp_seed_")]
    bad_spec = [e["name"] for e in seeded if not e.get("specialization")]
    bad_active = [e["name"] for e in seeded if not e.get("is_active")]
    ok = (r.status_code == 200 and len(experts) >= 7 and not missing
          and not bad_spec and not bad_active)
    log("5 GET /experts?include_inactive=true", ok,
        f"status={r.status_code}, count={len(experts)}, seeded_count={len(seeded)}, missing_names={missing}, bad_spec={bad_spec}, bad_active={bad_active}")
except Exception as e:
    log("5 GET /experts?include_inactive=true", False, repr(e))


# ── 6. GET /decision-templates/all (admin) ───────────────────────────
try:
    r = requests.get(f"{BASE}/decision-templates/all", headers=H(admin_token), timeout=15)
    tmpls = r.json() if r.status_code == 200 else []
    if isinstance(tmpls, dict):
        tmpls = tmpls.get("templates", [])
    names = [t.get("name") for t in tmpls]
    must_have = ["Job Offer Evaluation", "Buy vs. Rent a Home", "Marriage / Long-term Partner"]
    missing = [n for n in must_have if n not in names]
    seeded = [t for t in tmpls if t.get("id", "").startswith("tpl_seed_")]
    bad = []
    for t in seeded:
        if len(t.get("factors", [])) < 5:
            bad.append(f"{t.get('name')} factors={len(t.get('factors', []))}")
        if not t.get("is_approved"):
            bad.append(f"{t.get('name')} not_approved")
        if not t.get("is_official"):
            bad.append(f"{t.get('name')} not_official")
    ok = (r.status_code == 200 and len(tmpls) >= 12 and not missing and not bad)
    log("6 GET /decision-templates/all (admin)", ok,
        f"status={r.status_code}, count={len(tmpls)}, seeded_count={len(seeded)}, missing={missing}, bad={bad[:5]}")
except Exception as e:
    log("6 GET /decision-templates/all (admin)", False, repr(e))


# ── 7. GET /admin/customer-segments (admin) ──────────────────────────
try:
    r = requests.get(f"{BASE}/admin/customer-segments", headers=H(admin_token), timeout=15)
    body = r.json() if r.status_code == 200 else {}
    segs = body.get("segments", [])
    tiers = body.get("tiers", [])
    names = [s.get("name") for s in segs]
    must_have = [
        "Tech Startup Founder", "Working Parent (Mid-Career)",
        "Solopreneur / Freelance Consultant", "Student / Career Aspirant (18–24)",
        "Pre-Retiree / Retiree (50+)", "Corporate Decision-Maker (Director+)",
    ]
    missing = [n for n in must_have if n not in names]
    seeded = [s for s in segs if s.get("segment_id", "").startswith("cs_seed_")]
    bad = []
    chakra_links = 0
    for s in seeded:
        factors = s.get("factors", [])
        tp = s.get("tier_pricings", [])
        if len(factors) < 20:
            bad.append(f"{s.get('name')}: factors={len(factors)}")
        if len(tp) != 7:
            bad.append(f"{s.get('name')}: tier_pricings={len(tp)}")
        for row in tp:
            if row.get("country_code") != "IN" or row.get("currency") != "INR":
                bad.append(f"{s.get('name')}: tier_pricing currency/country wrong")
                break
        if s.get("chakra_tier_link"):
            chakra_links += 1
    ok = (r.status_code == 200 and len(segs) >= 6 and not missing
          and not bad and chakra_links >= 5)
    log("7 GET /admin/customer-segments (admin)", ok,
        f"status={r.status_code}, segments={len(segs)}, tiers={len(tiers)}, seeded_count={len(seeded)}, missing={missing}, chakra_links={chakra_links}, bad={bad[:5]}")
except Exception as e:
    log("7 GET /admin/customer-segments (admin)", False, repr(e))


# ── 8. GET /collaboration/decision-modes ─────────────────────────────
try:
    r = requests.get(f"{BASE}/collaboration/decision-modes", headers=H(admin_token), timeout=15)
    body = r.json() if r.status_code == 200 else {}
    modes = body if isinstance(body, list) else body.get("modes", [])
    mode_ids = {m.get("id") for m in modes}
    expected = {"equal", "voting", "command", "sme", "custom", "consensus"}
    missing = expected - mode_ids
    ok = (r.status_code == 200 and len(modes) >= 6 and not missing)
    log("8 GET /collaboration/decision-modes", ok,
        f"status={r.status_code}, count={len(modes)}, ids={sorted(mode_ids)}, missing={missing}")
except Exception as e:
    log("8 GET /collaboration/decision-modes", False, repr(e))


# ── 9. GET /solutions-store/pending-approval (admin) ─────────────────
try:
    r = requests.get(f"{BASE}/solutions-store/pending-approval", headers=H(admin_token), timeout=15)
    body = r.json() if r.status_code == 200 else []
    items = body if isinstance(body, list) else body.get("solutions", body.get("items", []))
    names = [s.get("name") for s in items]
    must_have = [
        "Notion Productivity Coaching (4-week)",
        "TiE Global Summit 2026 — Bengaluru",
        "Dr. Karthik Iyer — Sports Physiotherapist",
    ]
    missing = [n for n in must_have if n not in names]
    bad_status = [s.get("name") for s in items
                  if s.get("solution_id", "").startswith("sol_seed_")
                  and s.get("approval_status") != "pending"]
    ok = (r.status_code == 200 and len(items) >= 6 and not missing and not bad_status)
    log("9 GET /solutions-store/pending-approval", ok,
        f"status={r.status_code}, count={len(items)}, missing={missing}, bad_status={bad_status}")
except Exception as e:
    log("9 GET /solutions-store/pending-approval", False, repr(e))


# ── 10. GET /social-learning/admin/pending (admin) ───────────────────
try:
    r = requests.get(f"{BASE}/social-learning/admin/pending", headers=H(admin_token), timeout=15)
    body = r.json() if r.status_code == 200 else {}
    tmpls = body.get("templates", []) if isinstance(body, dict) else body
    titles = [t.get("title") for t in tmpls]
    spot = [
        "Layoffs in Indian IT — How to Decision-Proof Your Career",
        "Bengaluru Water Crisis — Decision Framework for Apartment Buyers",
    ]
    missing = [n for n in spot if n not in titles]
    seeded = [t for t in tmpls if t.get("id", "").startswith("sl_seed_submitted_")]
    bad_status = [t.get("title") for t in seeded if t.get("status") != "submitted"]
    ok = (r.status_code == 200 and len(tmpls) >= 6 and not missing and not bad_status)
    log("10 GET /social-learning/admin/pending", ok,
        f"status={r.status_code}, count={len(tmpls)}, seeded={len(seeded)}, missing={missing}, bad_status={bad_status}")
except Exception as e:
    log("10 GET /social-learning/admin/pending", False, repr(e))


# ── 11. GET /incidents (admin) ───────────────────────────────────────
try:
    r = requests.get(f"{BASE}/incidents", headers=H(admin_token), timeout=15)
    body = r.json() if r.status_code == 200 else []
    items = body if isinstance(body, list) else body.get("incidents", body.get("items", []))
    seeded = [i for i in items if isinstance(i.get("id"), str) and i["id"].startswith("INC-SEED-")]
    seeded_ids = {i["id"] for i in seeded}
    expected_ids = {"INC-SEED-001", "INC-SEED-002", "INC-SEED-003", "INC-SEED-004"}
    missing = expected_ids - seeded_ids
    required_fields = ["id", "title", "severity", "status", "kyc_data_involved", "created_at", "detected_at"]
    bad = []
    for inc in seeded:
        for f in required_fields:
            if f not in inc:
                bad.append(f"{inc.get('id')} missing {f}")
        if not inc.get("timeline"):
            bad.append(f"{inc.get('id')} empty timeline")
    ok = (r.status_code == 200 and len(seeded) >= 4 and not missing and not bad)
    log("11 GET /incidents (admin)", ok,
        f"status={r.status_code}, total={len(items)}, seeded={len(seeded)}, seeded_ids={sorted(seeded_ids)}, missing={missing}, bad={bad[:5]}")
except Exception as e:
    log("11 GET /incidents (admin)", False, repr(e))


# ── 12. GET /audit-trail (admin) ─────────────────────────────────────
try:
    r = requests.get(f"{BASE}/audit-trail", headers=H(admin_token), timeout=15)
    body = r.json() if r.status_code == 200 else {}
    logs = body.get("logs", []) if isinstance(body, dict) else body
    seeded = [e for e in logs if isinstance(e.get("id"), str) and e["id"].startswith("AUD-SEED-")]
    sens_true = sum(1 for e in seeded if e.get("sensitive_data_accessed") is True)
    sens_false = sum(1 for e in seeded if e.get("sensitive_data_accessed") is False)
    ok = (r.status_code == 200 and len(seeded) >= 25 and sens_true > 0 and sens_false > 0)
    log("12 GET /audit-trail (admin)", ok,
        f"status={r.status_code}, total_logs={len(logs)}, seeded={len(seeded)}, sensitive_true={sens_true}, sensitive_false={sens_false}")
except Exception as e:
    log("12 GET /audit-trail (admin)", False, repr(e))


# ── 13. Regression smoke ─────────────────────────────────────────────
for path, no_auth in [("/health", True), ("/branding/current", True)]:
    try:
        r = requests.get(f"{BASE}{path}", timeout=10)
        log(f"13 GET {path}", r.status_code == 200, f"status={r.status_code}")
    except Exception as e:
        log(f"13 GET {path}", False, repr(e))

# /customer-segments public
try:
    r = requests.get(f"{BASE}/customer-segments", timeout=10)
    body = r.json() if r.status_code == 200 else {}
    has_segs = isinstance(body, dict) and "segments" in body and "tiers" in body
    log("13 GET /customer-segments (public)", r.status_code == 200 and has_segs,
        f"status={r.status_code}, keys={list(body.keys()) if isinstance(body, dict) else type(body).__name__}")
except Exception as e:
    log("13 GET /customer-segments (public)", False, repr(e))

# /pricing public
try:
    r = requests.get(f"{BASE}/pricing", timeout=10)
    body = r.json() if r.status_code == 200 else {}
    has = isinstance(body, dict) and all(k in body for k in ("tiers", "segments", "matrix_rows"))
    log("13 GET /pricing (public)", r.status_code == 200 and has,
        f"status={r.status_code}, keys={list(body.keys()) if isinstance(body, dict) else type(body).__name__}")
except Exception as e:
    log("13 GET /pricing (public)", False, repr(e))


# ── SUMMARY ──────────────────────────────────────────────────────────
print("\n" + "=" * 80)
total = len(results)
passed = sum(1 for r in results if r[0] == "PASS")
failed = total - passed
print(f"TOTAL: {total}   PASSED: {passed}   FAILED: {failed}")
print("=" * 80)
if failed:
    print("\nFAILURES:")
    for s, n, info in results:
        if s == "FAIL":
            print(f"  ❌ {n}: {info}")

sys.exit(0 if failed == 0 else 1)
