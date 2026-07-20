#!/usr/bin/env python3
"""Backend tests for Public Pulse Phase 2 — Org / Gov / Admin Portal.

Covers 27 new endpoints under /api/public-pulse/* (orgs + admin + feedback-workflow),
plus end-to-end flow: admin/owner/citizen journeys, routing, rectification state
machine, reapply cooldown and runtime admin config updates.
"""
import os
import sys
import time
import json
import requests
from pymongo import MongoClient

BACKEND_URL = "https://repo-blueprint-1.preview.emergentagent.com/api"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "dezider"

results = []

def log(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    line = f"[{status}] {name}: {detail}"
    print(line)
    results.append((name, ok, detail))

def post(path, token=None, json_body=None, params=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.post(f"{BACKEND_URL}{path}", headers=headers, json=json_body, params=params, timeout=30)

def get(path, token=None, params=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.get(f"{BACKEND_URL}{path}", headers=headers, params=params, timeout=30)

def put(path, token=None, json_body=None, params=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.put(f"{BACKEND_URL}{path}", headers=headers, json=json_body, params=params, timeout=30)

def delete(path, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return requests.delete(f"{BACKEND_URL}{path}", headers=headers, timeout=30)

# Mongo
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

ts = int(time.time())

def register(email, pw, name):
    r = post("/auth/register", json_body={"email": email, "password": pw, "name": name})
    if r.status_code != 200:
        raise RuntimeError(f"register failed: {r.status_code} {r.text}")
    return r.json()["session_token"], r.json()["user_id"]

def login(email, pw):
    r = post("/auth/login", json_body={"email": email, "password": pw})
    if r.status_code != 200:
        raise RuntimeError(f"login failed: {r.status_code} {r.text}")
    return r.json()["session_token"]

# ═══════════════════════════════════════════════════════════════════
# 1. Register users: admin, org-owner, citizen
# ═══════════════════════════════════════════════════════════════════

admin_email = f"admin.meera.{ts}@publicpulse.example.com"
owner_email = f"owner.arjun.{ts}@coimbatore-skills.example.com"
citizen_email = f"citizen.lakshmi.{ts}@publicpulse.example.com"
pw = "PublicPulseP2#2026"

try:
    admin_token, admin_id = register(admin_email, pw, "Meera Admin")
    owner_token, owner_id = register(owner_email, pw, "Arjun Org Owner")
    citizen_token, citizen_id = register(citizen_email, pw, "Lakshmi Citizen")
    log("Setup: register 3 users", True, f"admin={admin_id[:8]} owner={owner_id[:8]} citizen={citizen_id[:8]}")
except Exception as e:
    log("Setup: register 3 users", False, str(e))
    sys.exit(1)

# Promote admin to super_admin and set email_verified
db.users.update_one({"user_id": admin_id}, {"$set": {"role": "super_admin", "email_verified": True}})
db.users.update_one({"user_id": owner_id}, {"$set": {"email_verified": True}})
# citizen left with email_verified default (unset/false)

# Re-login to refresh any cached role
admin_token = login(admin_email, pw)
owner_token = login(owner_email, pw)
citizen_token = login(citizen_email, pw)
log("Setup: re-login after DB role promotion", True)

# Clean any leftover Phase 2 admin config from prior runs (keep it fresh)
db.pp_admin_config.delete_many({})

# Force ACM seed to pick up pp_org_portal feature
r = post("/acm/seed", token=admin_token, params={"force": "true"})
log("Setup: ACM force re-seed", r.status_code in (200, 201), f"{r.status_code}")

# ═══════════════════════════════════════════════════════════════════
# 2. /admin/config — GET + PUT (admin-only)
# ═══════════════════════════════════════════════════════════════════

r = get("/public-pulse/admin/config", token=admin_token)
cfg = r.json() if r.status_code == 200 else {}
expected_keys = {"application_eligibility", "reapply_cooldown_days", "feedback_visibility", "feedback_routing"}
has_all_keys = expected_keys.issubset(set(cfg.keys()))
org_types = cfg.get("org_types", [])
log("GET /admin/config returns 4 keys + 8 org types",
    r.status_code == 200 and has_all_keys and len(org_types) == 8,
    f"{r.status_code} keys={list(cfg.keys())[:6]} org_types_count={len(org_types)}")

# Non-admin (citizen) should be rejected
r = get("/public-pulse/admin/config", token=citizen_token)
log("GET /admin/config rejects non-admin", r.status_code in (401, 403), f"{r.status_code}")

# PUT /admin/config — set reapply_cooldown_days default=10, overrides govt_dept=60
r = put("/public-pulse/admin/config", token=admin_token, json_body={
    "key": "reapply_cooldown_days",
    "value": {"default": 10, "overrides": {"govt_dept": 60}},
})
log("PUT /admin/config update reapply_cooldown_days",
    r.status_code == 200 and r.json().get("ok") is True,
    f"{r.status_code} body={r.text[:120]}")

# Verify
r = get("/public-pulse/admin/config", token=admin_token)
cooldown = r.json().get("reapply_cooldown_days", {})
log("GET /admin/config persists cooldown update",
    cooldown.get("default") == 10 and cooldown.get("overrides", {}).get("govt_dept") == 60,
    f"cooldown={cooldown}")

# ═══════════════════════════════════════════════════════════════════
# 3. /orgs/types — public
# ═══════════════════════════════════════════════════════════════════

r = get("/public-pulse/orgs/types")
ot = r.json().get("types", []) if r.status_code == 200 else []
codes = {t["code"] for t in ot}
expected_codes = {"ngo", "msme", "industry_association", "govt_dept", "political_org", "education_institute", "media", "other"}
log("GET /orgs/types returns 8 types",
    r.status_code == 200 and codes == expected_codes,
    f"{r.status_code} codes={sorted(codes)}")

# ═══════════════════════════════════════════════════════════════════
# 4. /orgs/eligibility/{org_type} — citizen without email_verified → False
# ═══════════════════════════════════════════════════════════════════

r = get("/public-pulse/orgs/eligibility/ngo", token=citizen_token)
body = r.json() if r.status_code == 200 else {}
blockers = body.get("blockers", [])
log("Eligibility: citizen unverified → eligible:false with 'Verify your email' blocker",
    r.status_code == 200 and body.get("eligible") is False and any("Verify your email" in b for b in blockers),
    f"{r.status_code} body={body}")

# Set citizen email_verified = True and re-check
db.users.update_one({"user_id": citizen_id}, {"$set": {"email_verified": True}})
r = get("/public-pulse/orgs/eligibility/ngo", token=citizen_token)
body = r.json() if r.status_code == 200 else {}
log("Eligibility: after email_verified → eligible:true",
    r.status_code == 200 and body.get("eligible") is True and body.get("blockers") == [],
    f"{r.status_code} body={body}")

# Owner eligibility
r = get("/public-pulse/orgs/eligibility/ngo", token=owner_token)
body = r.json() if r.status_code == 200 else {}
log("Owner eligibility ngo → true", r.status_code == 200 and body.get("eligible") is True, f"{body}")

# ═══════════════════════════════════════════════════════════════════
# 5. /orgs/apply (owner)
# ═══════════════════════════════════════════════════════════════════

unique_org_name = f"Coimbatore Skills Foundation {ts}"
app_body = {
    "org_type": "ngo",
    "display_name": unique_org_name,
    "legal_name": "Coimbatore Skills Foundation Trust",
    "about": "We run skills and livelihood programs for youth in Coimbatore.",
    "website": "https://example.org/csf",
    "email": owner_email,
    "phone": "+91-9876543210",
    "state": "Tamil Nadu",
    "district": "Coimbatore",
    "categories": ["education", "skills"],
}
r = post("/public-pulse/orgs/apply", token=owner_token, json_body=app_body)
app_payload = r.json() if r.status_code == 200 else {}
application = app_payload.get("application", {}) if isinstance(app_payload, dict) else {}
application_id = application.get("application_id")
log("POST /orgs/apply (owner) → 200 with application",
    r.status_code == 200 and app_payload.get("ok") is True and bool(application_id),
    f"{r.status_code} app_id={application_id}")

# ═══════════════════════════════════════════════════════════════════
# 6. /orgs/my-applications (owner)
# ═══════════════════════════════════════════════════════════════════

r = get("/public-pulse/orgs/my-applications", token=owner_token)
apps = r.json().get("applications", []) if r.status_code == 200 else []
log("GET /orgs/my-applications",
    r.status_code == 200 and any(a.get("application_id") == application_id for a in apps),
    f"{r.status_code} count={len(apps)}")

# 7. /orgs/my-application/{id}
r = get(f"/public-pulse/orgs/my-application/{application_id}", token=owner_token)
log("GET /orgs/my-application/{id}",
    r.status_code == 200 and r.json().get("application_id") == application_id,
    f"{r.status_code}")

# ═══════════════════════════════════════════════════════════════════
# 8-10. Admin moderation queue
# ═══════════════════════════════════════════════════════════════════

r = get("/public-pulse/admin/orgs/pending", token=admin_token)
count = r.json().get("count", 0) if r.status_code == 200 else 0
log("GET /admin/orgs/pending", r.status_code == 200 and count >= 1, f"{r.status_code} count={count}")

r = get("/public-pulse/admin/orgs/all", token=admin_token, params={"status": "pending"})
log("GET /admin/orgs/all?status=pending",
    r.status_code == 200 and r.json().get("count", 0) >= 1,
    f"{r.status_code}")

r = get(f"/public-pulse/admin/orgs/application/{application_id}", token=admin_token)
log("GET /admin/orgs/application/{id}",
    r.status_code == 200 and r.json().get("application_id") == application_id,
    f"{r.status_code}")

# ═══════════════════════════════════════════════════════════════════
# 11. Approve application
# ═══════════════════════════════════════════════════════════════════

r = post(f"/public-pulse/admin/orgs/application/{application_id}/review",
         token=admin_token, json_body={"decision": "approve"})
rev = r.json() if r.status_code == 200 else {}
org_id = rev.get("org_id")
log("POST /admin/orgs/application/{id}/review decision=approve",
    r.status_code == 200 and rev.get("status") == "approved" and bool(org_id),
    f"{r.status_code} org_id={org_id}")

# ═══════════════════════════════════════════════════════════════════
# 12. /orgs/my-orgs (owner sees new org with my_role=org_admin)
# ═══════════════════════════════════════════════════════════════════

r = get("/public-pulse/orgs/my-orgs", token=owner_token)
orgs = r.json().get("orgs", []) if r.status_code == 200 else []
owner_role = orgs[0].get("my_role") if orgs else None
log("GET /orgs/my-orgs → 1 org with my_role=org_admin",
    r.status_code == 200 and len(orgs) == 1 and owner_role == "org_admin",
    f"{r.status_code} orgs_count={len(orgs)} my_role={owner_role}")

# ═══════════════════════════════════════════════════════════════════
# 13. /orgs/{org_id} — member (full) vs non-member (public)
# ═══════════════════════════════════════════════════════════════════

r = get(f"/public-pulse/orgs/{org_id}", token=owner_token)
body = r.json() if r.status_code == 200 else {}
log("GET /orgs/{id} as member → full w/ my_role",
    r.status_code == 200 and body.get("my_role") == "org_admin" and body.get("owner_user_id") == owner_id,
    f"{r.status_code}")

r = get(f"/public-pulse/orgs/{org_id}", token=citizen_token)
body = r.json() if r.status_code == 200 else {}
public_only = (r.status_code == 200 and "owner_user_id" not in body and "my_role" not in body
               and body.get("display_name") == unique_org_name)
log("GET /orgs/{id} as non-member → public only",
    public_only,
    f"{r.status_code} keys={list(body.keys())[:8]}")

# ═══════════════════════════════════════════════════════════════════
# 14. /orgs/{id}/invite — admin-only; requires registered invitee
# ═══════════════════════════════════════════════════════════════════

# Non-admin (citizen) attempting invite → 403
r = post(f"/public-pulse/orgs/{org_id}/invite", token=citizen_token,
         json_body={"email": "randomperson@example.com", "role": "org_member"})
log("POST /orgs/{id}/invite by non-admin → 403", r.status_code == 403, f"{r.status_code}")

# Admin (owner) invites unregistered email → 404
r = post(f"/public-pulse/orgs/{org_id}/invite", token=owner_token,
         json_body={"email": f"ghost.{ts}@nowhere.example.com", "role": "org_member"})
log("POST /orgs/{id}/invite unregistered email → 404", r.status_code == 404, f"{r.status_code}")

# Admin invites citizen → 200
r = post(f"/public-pulse/orgs/{org_id}/invite", token=owner_token,
         json_body={"email": citizen_email, "role": "org_member"})
log("POST /orgs/{id}/invite citizen → 200",
    r.status_code == 200 and r.json().get("ok") is True,
    f"{r.status_code}")

# Remove citizen from org to keep subsequent public/non-member tests clean
# Actually keep — citizen as org_member is fine; revert to non-member below
db.pp_org_members.delete_one({"org_id": org_id, "user_id": citizen_id})
db.pp_orgs.update_one({"org_id": org_id}, {"$inc": {"active_member_count": -1}})

# ═══════════════════════════════════════════════════════════════════
# 15. /orgs/{id}/members — members only
# ═══════════════════════════════════════════════════════════════════

r = get(f"/public-pulse/orgs/{org_id}/members", token=owner_token)
members = r.json().get("members", []) if r.status_code == 200 else []
log("GET /orgs/{id}/members",
    r.status_code == 200 and any(m.get("user_id") == owner_id for m in members),
    f"{r.status_code} count={len(members)}")

# Non-member citizen → 403
r = get(f"/public-pulse/orgs/{org_id}/members", token=citizen_token)
log("GET /orgs/{id}/members non-member → 403", r.status_code == 403, f"{r.status_code}")

# ═══════════════════════════════════════════════════════════════════
# 16. /orgs/{id}/dashboard — k-threshold aware
# ═══════════════════════════════════════════════════════════════════

r = get(f"/public-pulse/orgs/{org_id}/dashboard", token=owner_token)
body = r.json() if r.status_code == 200 else {}
# With no sessions, expect blocked=True
log("GET /orgs/{id}/dashboard (cold start) — blocked:true",
    r.status_code == 200 and body.get("blocked") is True and "k_threshold" in body,
    f"{r.status_code} blocked={body.get('blocked')} k={body.get('k_threshold')}")

# ═══════════════════════════════════════════════════════════════════
# 17. Citizen submits feedback, then routes (exact match)
# ═══════════════════════════════════════════════════════════════════

fb_body = {
    "feedback_type": "department_experience",
    "severity": 3,
    "feedback_text": "Need more skilling batches in Coimbatore.",
    "related_entity": unique_org_name,
    "district": "Coimbatore",
}
r = post("/public-pulse/feedback", token=citizen_token, json_body=fb_body)
fb_id = r.json().get("feedback_id") if r.status_code == 200 else None
log("POST /feedback (exact match entity) → 200",
    r.status_code == 200 and bool(fb_id),
    f"{r.status_code} fb_id={fb_id}")

r = post(f"/public-pulse/feedback/{fb_id}/route", token=citizen_token)
body = r.json() if r.status_code == 200 else {}
log("POST /feedback/{id}/route → auto_routed:true",
    r.status_code == 200 and body.get("auto_routed") is True and body.get("org", {}).get("org_id") == org_id,
    f"{r.status_code} body={body}")

# ═══════════════════════════════════════════════════════════════════
# 18. Org feedback queue + state machine (acknowledge → respond)
# ═══════════════════════════════════════════════════════════════════

r = get(f"/public-pulse/orgs/{org_id}/feedback/queue", token=owner_token)
items = r.json().get("items", []) if r.status_code == 200 else []
log("GET /orgs/{id}/feedback/queue",
    r.status_code == 200 and any(it.get("feedback_id") == fb_id for it in items),
    f"{r.status_code} count={len(items)}")

# acknowledge
r = post(f"/public-pulse/orgs/{org_id}/feedback/{fb_id}/action",
         token=owner_token, json_body={"action": "acknowledge"})
log("Action: acknowledge (auto_routed → acknowledged)",
    r.status_code == 200 and r.json().get("new_status") == "acknowledged",
    f"{r.status_code} body={r.text[:150]}")

# respond
r = post(f"/public-pulse/orgs/{org_id}/feedback/{fb_id}/action",
         token=owner_token, json_body={"action": "respond", "response_text": "Thanks — we'll add more batches."})
log("Action: respond",
    r.status_code == 200 and r.json().get("new_status") == "responded",
    f"{r.status_code}")

# Citizen sees status responded
r = get("/public-pulse/feedback/me", token=citizen_token)
my_fbs = r.json().get("items", []) if r.status_code == 200 else []
if not my_fbs:
    # some servers may expose as feedback
    my_fbs = r.json().get("feedback", []) if r.status_code == 200 else []
mine = next((f for f in my_fbs if f.get("feedback_id") == fb_id), None)
log("GET /feedback/me (citizen) sees responded + response_text",
    bool(mine) and mine.get("status") == "responded" and bool(mine.get("response_text")),
    f"status={mine.get('status') if mine else None} rtxt={(mine or {}).get('response_text')}")

# ═══════════════════════════════════════════════════════════════════
# 19. State machine rejection — action=close from status=new
# ═══════════════════════════════════════════════════════════════════

# Create a new feedback for the org (exact match, auto-route so it's assigned)
r = post("/public-pulse/feedback", token=citizen_token, json_body={
    "feedback_type": "policy_suggestion",
    "severity": 2,
    "feedback_text": "Test invalid transition.",
    "related_entity": unique_org_name,
    "district": "Coimbatore",
})
fb_id2 = r.json().get("feedback_id")

# DON'T call /route — so status is still 'new' (not auto-routed)
# But /action requires assigned_org_id on the item. Force-assign via DB to simulate.
db.pp_feedback_items.update_one({"feedback_id": fb_id2}, {"$set": {"assigned_org_id": org_id, "status": "new"}})

r = post(f"/public-pulse/orgs/{org_id}/feedback/{fb_id2}/action",
         token=owner_token, json_body={"action": "close"})
log("State machine: close from 'new' → 400 (invalid transition)",
    r.status_code == 400 and "Cannot close from status" in r.text,
    f"{r.status_code} body={r.text[:140]}")

# ═══════════════════════════════════════════════════════════════════
# 20. Fuzzy routing + confirm-route + skip-routing
# ═══════════════════════════════════════════════════════════════════

r = post("/public-pulse/feedback", token=citizen_token, json_body={
    "feedback_type": "policy_suggestion",
    "severity": 2,
    "feedback_text": "Fuzzy test feedback.",
    "related_entity": f"Coimbatore Skills Foundation {ts}"[:30],  # partial prefix
    "district": "Coimbatore",
})
fb_fz_id = r.json().get("feedback_id")
log("POST /feedback (fuzzy entity)", r.status_code == 200 and bool(fb_fz_id), f"{r.status_code}")

r = post(f"/public-pulse/feedback/{fb_fz_id}/route", token=citizen_token)
body = r.json() if r.status_code == 200 else {}
suggestions = body.get("suggestions", [])
has_org_in_suggs = any(s.get("org_id") == org_id for s in suggestions)
log("Fuzzy route → auto_routed:false + suggestions contain our org",
    r.status_code == 200 and body.get("auto_routed") is False and has_org_in_suggs,
    f"{r.status_code} sugg_count={len(suggestions)}")

# Confirm route with org picked from suggestions
r = post(f"/public-pulse/feedback/{fb_fz_id}/confirm-route", token=citizen_token,
         json_body={"org_id": org_id})
log("POST /feedback/{id}/confirm-route (in suggestions)",
    r.status_code == 200 and r.json().get("ok") is True,
    f"{r.status_code}")

# Confirm-route with invalid org_id → 400
r = post(f"/public-pulse/feedback/{fb_fz_id}/confirm-route", token=citizen_token,
         json_body={"org_id": "not-in-list-xxxx"})
log("POST /confirm-route invalid org → 400", r.status_code == 400, f"{r.status_code}")

# Skip routing test — create a feedback with no match
r = post("/public-pulse/feedback", token=citizen_token, json_body={
    "feedback_type": "local_problem",
    "severity": 2,
    "feedback_text": "No match entity feedback.",
    "related_entity": "Totally NonExistent Org XYZ 99",
    "district": "Madurai",
})
fb_skip_id = r.json().get("feedback_id")
r = post(f"/public-pulse/feedback/{fb_skip_id}/route", token=citizen_token)
# Now skip
r = post(f"/public-pulse/feedback/{fb_skip_id}/skip-routing", token=citizen_token)
log("POST /feedback/{id}/skip-routing",
    r.status_code == 200 and r.json().get("ok") is True,
    f"{r.status_code}")

# ═══════════════════════════════════════════════════════════════════
# 21. /orgs/{id}/feedback/{fid}/claim
# ═══════════════════════════════════════════════════════════════════

# Create feedback auto-routed to org, then claim it
r = post("/public-pulse/feedback", token=citizen_token, json_body={
    "feedback_type": "service",
    "severity": 1,
    "feedback_text": "Claim test.",
    "related_entity": unique_org_name,
    "district": "Coimbatore",
})
fb_claim_id = r.json().get("feedback_id")
post(f"/public-pulse/feedback/{fb_claim_id}/route", token=citizen_token)

r = post(f"/public-pulse/orgs/{org_id}/feedback/{fb_claim_id}/claim", token=owner_token)
log("POST /orgs/{id}/feedback/{fid}/claim",
    r.status_code == 200 and r.json().get("claimed_by") == owner_id,
    f"{r.status_code}")

# ═══════════════════════════════════════════════════════════════════
# 22. Admin audit logs contain expected entries
# ═══════════════════════════════════════════════════════════════════

r = get("/public-pulse/admin/audit-logs", token=admin_token, params={"limit": 200})
logs = r.json().get("logs", []) if r.status_code == 200 else []
actions_set = {l.get("action") for l in logs}
expected_actions = {"org_application_submit", "org_application_approve",
                    "feedback_acknowledge", "feedback_respond", "admin_config_update"}
missing = expected_actions - actions_set
log("GET /admin/audit-logs contains key actions",
    r.status_code == 200 and not missing,
    f"{r.status_code} missing={missing} total_logs={len(logs)}")

# Audit filter
r = get("/public-pulse/admin/audit-logs", token=admin_token, params={"action": "org_application_approve"})
filt = r.json().get("logs", []) if r.status_code == 200 else []
log("GET /admin/audit-logs?action=...",
    r.status_code == 200 and all(l.get("action") == "org_application_approve" for l in filt),
    f"{r.status_code} count={len(filt)}")

# ═══════════════════════════════════════════════════════════════════
# 23. Admin escalated feedback + manual assign
# ═══════════════════════════════════════════════════════════════════

r = get("/public-pulse/admin/feedback/escalated", token=admin_token)
items = r.json().get("items", []) if r.status_code == 200 else []
log("GET /admin/feedback/escalated",
    r.status_code == 200 and any(it.get("feedback_id") == fb_skip_id for it in items),
    f"{r.status_code} count={len(items)}")

# Admin assigns escalated to org
r = post(f"/public-pulse/admin/feedback/{fb_skip_id}/assign-to-org", token=admin_token,
         params={"org_id": org_id})
log("POST /admin/feedback/{id}/assign-to-org",
    r.status_code == 200 and r.json().get("assigned_org_id") == org_id,
    f"{r.status_code}")

# ═══════════════════════════════════════════════════════════════════
# 24. Reapply cooldown (per spec — flow step 20)
#     Current config: reapply_cooldown_days.default=10 (set earlier)
# ═══════════════════════════════════════════════════════════════════

# Owner tries to apply a 2nd ngo app while first (approved) has no pending,
# but since approval, no pending exists. Use a DIFFERENT owner to trigger pending blocker.
# Per spec step 20: "Submit 2nd application for same org_type from same user → 403 with
# 'pending application' blocker."
# This requires a pending application. Register a new user just for cooldown test:
cool_email = f"cooldown.user.{ts}@publicpulse.example.com"
cool_token, cool_id = register(cool_email, pw, "Cooldown User")
db.users.update_one({"user_id": cool_id}, {"$set": {"email_verified": True}})
cool_token = login(cool_email, pw)

# Submit first msme application
r = post("/public-pulse/orgs/apply", token=cool_token, json_body={
    "org_type": "msme", "display_name": f"CoolMSME{ts}",
    "email": cool_email, "district": "Chennai",
})
cool_app_id = r.json().get("application", {}).get("application_id") if r.status_code == 200 else None
log("Cooldown prep: 1st msme application submitted", r.status_code == 200 and bool(cool_app_id), f"{r.status_code}")

# Try to submit 2nd (same user, same type) while pending → 403 with 'pending application'
r = post("/public-pulse/orgs/apply", token=cool_token, json_body={
    "org_type": "msme", "display_name": f"CoolMSME{ts}b",
    "email": cool_email, "district": "Chennai",
})
body = r.json() if r.status_code == 403 else {}
detail = body.get("detail", {}) if isinstance(body, dict) else {}
# FastAPI may wrap the dict under detail (as configured in route)
blockers_text = json.dumps(detail)
log("2nd apply while pending → 403 with 'pending application' blocker",
    r.status_code == 403 and "pending application" in blockers_text.lower(),
    f"{r.status_code} detail={blockers_text[:180]}")

# Admin rejects the first
r = post(f"/public-pulse/admin/orgs/application/{cool_app_id}/review",
         token=admin_token, json_body={"decision": "reject", "reason": "Incomplete docs."})
log("Admin rejects 1st cooldown app",
    r.status_code == 200 and r.json().get("status") == "rejected",
    f"{r.status_code}")

# Submit again → should 403 with cooldown blocker (10 days default)
r = post("/public-pulse/orgs/apply", token=cool_token, json_body={
    "org_type": "msme", "display_name": f"CoolMSME{ts}c",
    "email": cool_email, "district": "Chennai",
})
body = r.json() if r.status_code == 403 else {}
detail_txt = json.dumps(body.get("detail", {}))
log("Re-apply after rejection (within cooldown) → 403 with cooldown blocker",
    r.status_code == 403 and ("wait" in detail_txt.lower() and "day" in detail_txt.lower()),
    f"{r.status_code} detail={detail_txt[:180]}")

# ═══════════════════════════════════════════════════════════════════
# 25. Update config — cooldown default=0 → next apply succeeds
# ═══════════════════════════════════════════════════════════════════

r = put("/public-pulse/admin/config", token=admin_token, json_body={
    "key": "reapply_cooldown_days", "value": {"default": 0, "overrides": {}},
})
log("PUT /admin/config cooldown=0",
    r.status_code == 200 and r.json().get("ok") is True,
    f"{r.status_code}")

r = post("/public-pulse/orgs/apply", token=cool_token, json_body={
    "org_type": "msme", "display_name": f"CoolMSME{ts}d",
    "email": cool_email, "district": "Chennai",
})
log("Re-apply after cooldown=0 → 200",
    r.status_code == 200 and r.json().get("ok") is True,
    f"{r.status_code} body={r.text[:150]}")

# ═══════════════════════════════════════════════════════════════════
# 26. ACM check — 32 modules / 83 features with pp_org_portal feature
# ═══════════════════════════════════════════════════════════════════

r = get("/acm/matrix", token=admin_token)
matrix = r.json() if r.status_code == 200 else {}
total_modules = matrix.get("total_modules") or matrix.get("totals", {}).get("modules")
total_features = matrix.get("total_features") or matrix.get("totals", {}).get("features")
# Find pp_org_portal feature within public_pulse module
modules_list = matrix.get("modules") or []
pp_mod = next((m for m in modules_list if (m.get("module_id") == "public_pulse" or m.get("id") == "public_pulse" or m.get("slug") == "public_pulse")), None)
feat_ids = set()
if pp_mod:
    for f in pp_mod.get("features", []):
        feat_ids.add(f.get("feature_id") or f.get("id") or f.get("slug"))
log("ACM: 32 modules & 83 features & pp_org_portal present",
    total_modules == 32 and total_features == 83 and ("pp_org_portal" in feat_ids),
    f"modules={total_modules} features={total_features} pp_feats={sorted(feat_ids)}")

# ═══════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════

print("\n" + "=" * 70)
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
print(f"RESULTS: {passed} PASSED, {failed} FAILED of {len(results)} total")
print("=" * 70)
if failed:
    print("\nFailed tests:")
    for name, ok, detail in results:
        if not ok:
            print(f"  ✗ {name} — {detail}")

sys.exit(0 if failed == 0 else 1)
