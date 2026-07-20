#!/usr/bin/env python3
"""Backend tests for Public Pulse module (Phase 1 Citizen MVP)."""
import os
import sys
import time
import uuid
import json
import requests
from pymongo import MongoClient

BACKEND_URL = "https://repo-blueprint-1.preview.emergentagent.com/api"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "dezider"

results = []
def log(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}: {detail}")
    results.append((name, ok, detail))

def post(path, token=None, json_body=None, params=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = requests.post(f"{BACKEND_URL}{path}", headers=headers, json=json_body, params=params, timeout=30)
    return r

def get(path, token=None, params=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = requests.get(f"{BACKEND_URL}{path}", headers=headers, params=params, timeout=30)
    return r

def put(path, token=None, json_body=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = requests.put(f"{BACKEND_URL}{path}", headers=headers, json=json_body, timeout=30)
    return r

def delete(path, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = requests.delete(f"{BACKEND_URL}{path}", headers=headers, timeout=30)
    return r

# ────────── Setup user ──────────
ts = int(time.time())
email = f"priya.iyer.{ts}@publicpulse.example.com"
pw = "PublicPulse#2026"
name = "Priya Iyer"

r = post("/auth/register", json_body={"email": email, "password": pw, "name": name})
if r.status_code != 200:
    print(f"FATAL: registration failed {r.status_code}: {r.text}")
    sys.exit(1)
token = r.json()["session_token"]
user_id = r.json()["user_id"]
log("Setup: register user", True, f"user_id={user_id}")

# Promote to super_admin
client = MongoClient(MONGO_URL)
db = client[DB_NAME]
res = db.users.update_one({"user_id": user_id}, {"$set": {"role": "super_admin"}})
log("Setup: promote to super_admin", res.modified_count == 1, f"modified={res.modified_count}")

# Re-login to refresh token (some implementations cache role on token)
r = post("/auth/login", json_body={"email": email, "password": pw})
if r.status_code == 200:
    token = r.json()["session_token"]
log("Setup: re-login", r.status_code == 200)

# ────────── ACM ──────────
r = post("/acm/seed", token=token, params={"force": "true"})
log("ACM seed", r.status_code in (200, 201), f"{r.status_code}")

r = get("/acm/matrix", token=token)
ok = r.status_code == 200
matrix = r.json() if ok else {}
total_modules = matrix.get("total_modules") or matrix.get("totals", {}).get("modules")
total_features = matrix.get("total_features") or matrix.get("totals", {}).get("features")
log("ACM matrix counts", total_modules == 32 and total_features == 82, f"modules={total_modules} features={total_features}")

# Find public_pulse module
modules_list = matrix.get("modules") or []
pp_mod = next((m for m in modules_list if (m.get("module_id") == "public_pulse" or m.get("id") == "public_pulse" or m.get("slug") == "public_pulse")), None)
log("ACM: public_pulse module exists", pp_mod is not None, f"found={bool(pp_mod)}")

if pp_mod:
    pp_features = pp_mod.get("features") or []
    feature_ids = [f.get("feature_id") or f.get("id") or f.get("slug") for f in pp_features]
    expected = {"pp_self_discovery_tools", "pp_consent_management", "pp_public_dashboards", "pp_feedback_rectification"}
    log("ACM: 4 public_pulse features", expected.issubset(set(feature_ids)), f"have={feature_ids}")

# ────────── 1. Consent ──────────
r = get("/public-pulse/consent/options")
data = r.json() if r.status_code == 200 else {}
ok = (r.status_code == 200 and "version" in data and "purposes" in data and len(data["purposes"]) == 4
      and "data_categories" in data)
log("GET /consent/options", ok, f"{r.status_code} purposes={len(data.get('purposes', []))}")

r = get("/public-pulse/consent/me", token=token)
data = r.json() if r.status_code == 200 else {}
log("GET /consent/me (no record)", r.status_code == 200 and data.get("active") is False, f"{r.status_code} active={data.get('active')}")

r = post("/public-pulse/consent", token=token, json_body={
    "purposes": {"personal_recommendations": True, "aggregate_research": True, "verified_org_insights": True, "follow_up_contact": False},
    "data_categories_allowed": ["demographics", "tool_answers", "feedback"]
})
data = r.json() if r.status_code == 200 else {}
log("POST /consent", r.status_code == 200 and data.get("ok") is True and "record" in data, f"{r.status_code}")

r = get("/public-pulse/consent/me", token=token)
data = r.json() if r.status_code == 200 else {}
log("GET /consent/me (active)", r.status_code == 200 and data.get("active") is True, f"{r.status_code} active={data.get('active')}")

# Don't withdraw yet - we need consent for tools

# ────────── 2. Profile ──────────
r = get("/public-pulse/profile/options", token=token)
data = r.json() if r.status_code == 200 else {}
ok = (r.status_code == 200 and len(data.get("age_groups", [])) == 5
      and len(data.get("professions", [])) == 10 and len(data.get("education_levels", [])) == 8
      and len(data.get("income_brackets", [])) == 7 and len(data.get("genders", [])) == 4)
log("GET /profile/options", ok, f"{r.status_code} ag={len(data.get('age_groups',[]))} pr={len(data.get('professions',[]))} ed={len(data.get('education_levels',[]))} ib={len(data.get('income_brackets',[]))} g={len(data.get('genders',[]))}")

r = get("/public-pulse/profile/me", token=token)
log("GET /profile/me (empty)", r.status_code == 200, f"{r.status_code}")

r = put("/public-pulse/profile", token=token, json_body={
    "state": "Tamil Nadu", "district": "Coimbatore", "age_group": "25-34",
    "profession": "salaried", "education": "graduate", "income_bracket": "5L-10L"
})
log("PUT /profile", r.status_code == 200 and r.json().get("ok"), f"{r.status_code}")

r = get("/public-pulse/profile/me", token=token)
data = r.json() if r.status_code == 200 else {}
log("GET /profile/me (saved)", r.status_code == 200 and data.get("district") == "Coimbatore", f"{r.status_code}")

# ────────── 3. Tools list & meta ──────────
r = get("/public-pulse/tools", token=token)
data = r.json() if r.status_code == 200 else {}
slugs = [t.get("slug") for t in data.get("tools", [])]
log("GET /tools (list 3)", r.status_code == 200 and set(slugs) == {"life_direction", "marriage_readiness", "govt_benefit_finder"}, f"{r.status_code} slugs={slugs}")

# Tool def: life_direction
r = get("/public-pulse/tools/life_direction", token=token)
data = r.json() if r.status_code == 200 else {}
log("GET /tools/life_direction (4 steps)", r.status_code == 200 and len(data.get("steps", [])) == 4, f"{r.status_code} steps={len(data.get('steps',[]))}")

r = get("/public-pulse/tools/marriage_readiness", token=token)
data = r.json() if r.status_code == 200 else {}
log("GET /tools/marriage_readiness (5 steps)", r.status_code == 200 and len(data.get("steps", [])) == 5, f"{r.status_code} steps={len(data.get('steps',[]))}")

r = get("/public-pulse/tools/govt_benefit_finder", token=token)
data = r.json() if r.status_code == 200 else {}
log("GET /tools/govt_benefit_finder (5 steps)", r.status_code == 200 and len(data.get("steps", [])) == 5, f"{r.status_code} steps={len(data.get('steps',[]))}")

# ────────── 4. Tool flow: life_direction (4 steps) ──────────
r = post("/public-pulse/tools/life_direction/start", token=token, json_body={})
data = r.json() if r.status_code == 200 else {}
ld_session = data.get("session_id")
log("POST /tools/life_direction/start", r.status_code == 200 and ld_session and data.get("current_step") == 1, f"{r.status_code} session={ld_session}")

# Step 1
r = post(f"/public-pulse/tools/sessions/{ld_session}/answer", token=token, json_body={
    "step": 1, "answers": {"age_group": "25-34", "district": "Coimbatore"}
})
data = r.json() if r.status_code == 200 else {}
has_teaser = "teaser" in data and data["teaser"] and "lead" in data["teaser"]
log("LD step 1 (current_step=2 + teaser)", r.status_code == 200 and data.get("current_step") == 2 and has_teaser, f"{r.status_code} cs={data.get('current_step')} teaser={data.get('teaser')}")

# Step 2 (partial result)
r = post(f"/public-pulse/tools/sessions/{ld_session}/answer", token=token, json_body={
    "step": 2, "answers": {"current_status": "working", "satisfaction": 3}
})
data = r.json() if r.status_code == 200 else {}
pr = data.get("partial_result") or {}
log("LD step 2 (partial Transition Zone)", r.status_code == 200 and pr.get("label") == "Transition Zone", f"{r.status_code} pr={pr}")

# Step 3
r = post(f"/public-pulse/tools/sessions/{ld_session}/answer", token=token, json_body={
    "step": 3, "answers": {"want": "high_income", "biggest_blocker": "skills"}
})
log("LD step 3", r.status_code == 200, f"{r.status_code}")

# Step 4 (final)
r = post(f"/public-pulse/tools/sessions/{ld_session}/answer", token=token, json_body={
    "step": 4, "answers": {"profession": "salaried", "education": "graduate"}
})
log("LD step 4", r.status_code == 200, f"{r.status_code}")

# Complete
r = post(f"/public-pulse/tools/sessions/{ld_session}/complete", token=token, json_body={"contribute_to_research": True})
data = r.json() if r.status_code == 200 else {}
ok = (r.status_code == 200 and isinstance(data.get("score"), int) and 0 <= data["score"] <= 100
      and data.get("score_band") in ("low", "medium", "high")
      and data.get("insight") and isinstance(data.get("recommendations"), list)
      and data.get("hidden_value_hook"))
log("LD complete", ok, f"{r.status_code} score={data.get('score')} band={data.get('score_band')} recs={len(data.get('recommendations',[]))}")

# ────────── 5. Tool flow: marriage_readiness (5 steps) ──────────
r = post("/public-pulse/tools/marriage_readiness/start", token=token, json_body={})
mr_session = r.json().get("session_id") if r.status_code == 200 else None
log("POST /tools/marriage_readiness/start", r.status_code == 200 and mr_session, f"{r.status_code}")

if mr_session:
    steps_data = [
        (1, {"age_group": "25-34", "gender": "female", "district": "Coimbatore"}),
        (2, {"current_status": "evaluating", "financial_readiness": "partially", "emotional_readiness": "confident"}),
        (3, {"biggest_concern": "money", "timeline": "1_to_3y"}),
        (4, {"wants_financial_support": True, "wants_guidance": True, "wants_matchmaking": False}),
        (5, {"income_bracket": "5L-10L", "education": "graduate"}),
    ]
    all_ok = True
    for step, answers in steps_data:
        r = post(f"/public-pulse/tools/sessions/{mr_session}/answer", token=token, json_body={"step": step, "answers": answers})
        if r.status_code != 200:
            all_ok = False
            print(f"  MR step {step} FAIL: {r.status_code} {r.text[:200]}")
    log("MR steps 1-5", all_ok)

    r = post(f"/public-pulse/tools/sessions/{mr_session}/complete", token=token, json_body={"contribute_to_research": True})
    data = r.json() if r.status_code == 200 else {}
    log("MR complete", r.status_code == 200 and isinstance(data.get("score"), int) and data.get("insight"), f"{r.status_code} score={data.get('score')}")

# ────────── 6. Tool flow: govt_benefit_finder (5 steps) ──────────
r = post("/public-pulse/tools/govt_benefit_finder/start", token=token, json_body={})
gb_session = r.json().get("session_id") if r.status_code == 200 else None
log("POST /tools/govt_benefit_finder/start", r.status_code == 200 and gb_session, f"{r.status_code}")

if gb_session:
    steps_data = [
        (1, {"district": "Coimbatore", "age_group": "25-34"}),
        (2, {"life_category": "job_seeker"}),
        (3, {"biggest_need": "job", "difficulty": 4}),
        (4, {"income_bracket": "2.5L-5L", "education": "graduate"}),
        (5, {"has_disability": False, "family_size": 4}),
    ]
    all_ok = True
    for step, answers in steps_data:
        r = post(f"/public-pulse/tools/sessions/{gb_session}/answer", token=token, json_body={"step": step, "answers": answers})
        if r.status_code != 200:
            all_ok = False
            print(f"  GB step {step} FAIL: {r.status_code} {r.text[:200]}")
    log("GB steps 1-5", all_ok)

    r = post(f"/public-pulse/tools/sessions/{gb_session}/complete", token=token, json_body={"contribute_to_research": True})
    data = r.json() if r.status_code == 200 else {}
    log("GB complete", r.status_code == 200 and "score" in data and isinstance(data.get("recommendations"), list), f"{r.status_code} score={data.get('score')} matches={len(data.get('recommendations',[]))}")

# ────────── 7. Sessions read ──────────
r = get("/public-pulse/tools/sessions/me", token=token)
data = r.json() if r.status_code == 200 else {}
log("GET /tools/sessions/me", r.status_code == 200 and len(data.get("sessions", [])) >= 3, f"{r.status_code} count={len(data.get('sessions',[]))}")

if ld_session:
    r = get(f"/public-pulse/tools/sessions/{ld_session}", token=token)
    log("GET /tools/sessions/{id}", r.status_code == 200, f"{r.status_code}")

# ────────── 8. Dashboards (before seeding - mostly empty/blocked) ──────────
print("\n--- Dashboards (pre-seed) ---")
for path in ["district-demand-heatmap", "youth-job-priority", "marriage-support-need", "scheme-awareness", "rectification-tracker"]:
    r = get(f"/public-pulse/dashboards/{path}", token=token)
    data = r.json() if r.status_code == 200 else {}
    print(f"  {path}: {r.status_code} keys={list(data.keys())[:6]}")

# Rectification tracker should be blocked initially (k=10, 0 feedback)
r = get("/public-pulse/dashboards/rectification-tracker", token=token)
data = r.json() if r.status_code == 200 else {}
log("Pre-seed: rectification blocked", r.status_code == 200 and data.get("blocked") is True, f"{r.status_code} blocked={data.get('blocked')}")

# ────────── 9. Admin: seed demo data ──────────
r = post("/public-pulse/admin/seed-demo-data", token=token, params={"count": 80})
data = r.json() if r.status_code == 200 else {}
log("POST /admin/seed-demo-data?count=80", r.status_code == 200 and data.get("ok") and data.get("inserted") == 240, f"{r.status_code} inserted={data.get('inserted')}")

# ────────── 10. Dashboards (post-seed) ──────────
print("\n--- Dashboards (post-seed) ---")

r = get("/public-pulse/dashboards/district-demand-heatmap", token=token)
data = r.json() if r.status_code == 200 else {}
ddh_data = data.get("data", [])
log("Dashboard: district-demand-heatmap", r.status_code == 200 and isinstance(ddh_data, list) and len(ddh_data) > 0, f"{r.status_code} buckets={len(ddh_data)}")

r = get("/public-pulse/dashboards/youth-job-priority", token=token)
data = r.json() if r.status_code == 200 else {}
yjp = data.get("data", [])
log("Dashboard: youth-job-priority", r.status_code == 200 and isinstance(yjp, list), f"{r.status_code} buckets={len(yjp)}")

r = get("/public-pulse/dashboards/marriage-support-need", token=token)
data = r.json() if r.status_code == 200 else {}
ms_inner = data.get("by_concern", {}).get("data", [])
log("Dashboard: marriage-support-need", r.status_code == 200 and isinstance(ms_inner, list), f"{r.status_code} buckets={len(ms_inner)}")

r = get("/public-pulse/dashboards/scheme-awareness", token=token)
data = r.json() if r.status_code == 200 else {}
sa = data.get("data", [])
log("Dashboard: scheme-awareness", r.status_code == 200 and isinstance(sa, list), f"{r.status_code} buckets={len(sa)}")

# rectification still blocked likely (no feedback yet, will add one then test)

# ────────── 11. Feedback ──────────
r = get("/public-pulse/feedback/types", token=token)
data = r.json() if r.status_code == 200 else {}
log("GET /feedback/types", r.status_code == 200 and "service" in data.get("types", []), f"{r.status_code}")

r = post("/public-pulse/feedback", token=token, json_body={
    "feedback_text": "Long delay in obtaining ration card update at Coimbatore municipal office.",
    "feedback_type": "service",
    "district": "Coimbatore",
    "severity": 3
})
data = r.json() if r.status_code == 200 else {}
fb_id = data.get("feedback_id")
log("POST /feedback", r.status_code == 200 and data.get("ok") and fb_id and data.get("status") == "new", f"{r.status_code} id={fb_id}")

r = get("/public-pulse/feedback/me", token=token)
data = r.json() if r.status_code == 200 else {}
log("GET /feedback/me", r.status_code == 200 and len(data.get("items", [])) >= 1, f"{r.status_code} count={len(data.get('items',[]))}")

# ────────── 12. Admin: k-thresholds ──────────
r = get("/public-pulse/admin/k-thresholds", token=token)
data = r.json() if r.status_code == 200 else {}
log("GET /admin/k-thresholds", r.status_code == 200 and "values" in data and "defaults" in data, f"{r.status_code}")

r = put("/public-pulse/admin/k-threshold", token=token, json_body={"dashboard_key": "teaser", "threshold": 25})
log("PUT /admin/k-threshold (teaser=25)", r.status_code == 200 and r.json().get("ok"), f"{r.status_code}")

# Reject < 5
r = put("/public-pulse/admin/k-threshold", token=token, json_body={"dashboard_key": "teaser", "threshold": 4})
log("PUT /admin/k-threshold (teaser=4 → reject)", r.status_code == 400, f"{r.status_code}")

# ────────── 13. Admin auth gating: test non-admin denial ──────────
ts2 = int(time.time())
email2 = f"regular.user.{ts2}@publicpulse.example.com"
r = post("/auth/register", json_body={"email": email2, "password": "Regular#2026", "name": "Regular User"})
if r.status_code == 200:
    reg_token = r.json()["session_token"]
    r = get("/public-pulse/admin/k-thresholds", token=reg_token)
    log("Non-admin denied admin k-thresholds", r.status_code == 403, f"{r.status_code}")
    r = post("/public-pulse/admin/seed-demo-data", token=reg_token, params={"count": 5})
    log("Non-admin denied seed-demo-data", r.status_code == 403, f"{r.status_code}")

# ────────── 14. Admin: clear seeded data ──────────
r = delete("/public-pulse/admin/seed-demo-data", token=token)
data = r.json() if r.status_code == 200 else {}
log("DELETE /admin/seed-demo-data", r.status_code == 200 and data.get("ok") and data.get("deleted", 0) >= 240, f"{r.status_code} deleted={data.get('deleted')}")

# ────────── 15. Withdraw consent ──────────
r = post("/public-pulse/consent/withdraw", token=token)
log("POST /consent/withdraw", r.status_code == 200 and r.json().get("ok"), f"{r.status_code}")

r = get("/public-pulse/consent/me", token=token)
data = r.json() if r.status_code == 200 else {}
log("GET /consent/me after withdraw (active=False)", r.status_code == 200 and data.get("active") is False, f"{r.status_code} active={data.get('active')}")

# ────────── Auth gating sanity ──────────
r = get("/public-pulse/consent/me")  # no token
log("GET /consent/me without auth → 401", r.status_code in (401, 403), f"{r.status_code}")

# ────────── Summary ──────────
print("\n" + "="*60)
passed = sum(1 for _, ok, _ in results if ok)
failed = [(n, d) for n, ok, d in results if not ok]
print(f"PASSED: {passed}/{len(results)}")
if failed:
    print(f"FAILED: {len(failed)}")
    for n, d in failed:
        print(f"  - {n}: {d}")
sys.exit(0 if not failed else 1)
