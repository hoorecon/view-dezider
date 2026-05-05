"""
Backend regression tests for v3.9.0:
  1) OrgSurveys (NEW module) — backend/routes/org_surveys.py
  2) ExpertNet v3.9.0 video_url change — backend/routes/expert_net.py

Auth credentials sourced from /app/memory/test_credentials.md.
"""
import os
import sys
import time
import uuid
import requests
from datetime import datetime, timezone, timedelta

BASE = os.environ.get(
    "BACKEND_BASE_URL",
    "https://voice-browse-epic.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE}/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"
USER_EMAIL = "harden_1777921741@example.com"
USER_PASS = "HardenPass2026!"
ORG_SLUG = "coimbatore-skills-foundation-5b9c19"

results = []


def record(name: str, ok: bool, detail: str = ""):
    icon = "PASS" if ok else "FAIL"
    print(f"[{icon}] {name}  {detail if not ok else ''}")
    results.append({"name": name, "ok": ok, "detail": detail})


def login(email: str, pwd: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"login failed for {email}: {r.status_code} {r.text}")
    return r.json()["session_token"]


def H(tok):
    return {"Authorization": f"Bearer {tok}"} if tok else {}


print(f"\n=== Backend base URL: {BASE} ===\n")

try:
    admin_tok = login(ADMIN_EMAIL, ADMIN_PASS)
    user_tok = login(USER_EMAIL, USER_PASS)
    record("auth.login.admin+user", True)
except Exception as ex:
    record("auth.login", False, str(ex))
    sys.exit(1)


# ======================================================================
# SECTION 1 — OrgSurveys
# ======================================================================
print("\n────── OrgSurveys ──────")

# 1.1 — non-existent slug → 404 on every endpoint
bad_slug_paths = [
    ("GET", "/p/non-existent-slug/surveys", None, None),
    ("GET", "/p/non-existent-slug/surveys/sv_x", None, None),
    ("GET", "/p/non-existent-slug/surveys/sv_x/aggregate", None, None),
    ("POST", "/p/non-existent-slug/surveys/sv_x/submit", {"answers": {}}, None),
    ("POST", "/p/non-existent-slug/surveys",
     {"title": "x", "questions": [{"qid": "q1", "text": "?", "qtype": "short_text"}]},
     admin_tok),
    ("PUT", "/p/non-existent-slug/surveys/sv_x",
     {"title": "x", "questions": [{"qid": "q1", "text": "?", "qtype": "short_text"}]},
     admin_tok),
    ("DELETE", "/p/non-existent-slug/surveys/sv_x", None, admin_tok),
    ("GET", "/p/non-existent-slug/surveys/sv_x/responses", None, admin_tok),
]
for m, path, body, tok in bad_slug_paths:
    r = requests.request(m, f"{API}{path}", json=body, headers=H(tok), timeout=20)
    record(f"badslug.{m} {path}", r.status_code == 404,
           f"got {r.status_code}: {r.text[:120]}")

# 1.2 — USER cannot create
r = requests.post(
    f"{API}/p/{ORG_SLUG}/surveys",
    json={"title": "Should not be allowed",
          "questions": [{"qid": "q1", "text": "?", "qtype": "short_text"}]},
    headers=H(user_tok),
    timeout=20,
)
record("create.user_forbidden", r.status_code == 403,
       f"got {r.status_code}: {r.text[:200]}")

# 1.3 — ADMIN creates survey with all 7 question types
survey_payload = {
    "title": f"Regression Survey {int(time.time())}",
    "description": "Covers all 7 qtypes",
    "is_active": True,
    "accepts_anon": True,
    "questions": [
        {"qid": "name", "text": "Your name?", "qtype": "short_text", "required": True},
        {"qid": "feedback", "text": "Long feedback", "qtype": "long_text"},
        {"qid": "city", "text": "Pick city", "qtype": "single_select",
         "options": ["Coimbatore", "Chennai", "Madurai"], "required": True},
        {"qid": "skills", "text": "Pick skills", "qtype": "multi_select",
         "options": ["python", "react", "design", "writing"]},
        {"qid": "rating", "text": "Rate us", "qtype": "rating_5", "required": True},
        {"qid": "would_recommend", "text": "Recommend?", "qtype": "yes_no"},
        {"qid": "age", "text": "Age", "qtype": "number"},
    ],
}
r = requests.post(f"{API}/p/{ORG_SLUG}/surveys", json=survey_payload, headers=H(admin_tok), timeout=20)
ok_create = r.status_code == 200 and r.json().get("ok") is True
survey_id = r.json().get("survey_id") if ok_create else None
record("create.admin", ok_create and bool(survey_id),
       f"status={r.status_code}, sid={survey_id}, body={r.text[:200]}")

if survey_id:
    # 1.4 — list anon
    r = requests.get(f"{API}/p/{ORG_SLUG}/surveys", timeout=20)
    items = r.json().get("items", []) if r.status_code == 200 else []
    found = any(s.get("survey_id") == survey_id for s in items)
    record("list.anon", r.status_code == 200 and found,
           f"status={r.status_code} count={len(items)} found={found}")

    # 1.5 — get single anon
    r = requests.get(f"{API}/p/{ORG_SLUG}/surveys/{survey_id}", timeout=20)
    sv = r.json().get("survey", {}) if r.status_code == 200 else {}
    qcount = len(sv.get("questions", []))
    record("get.single.anon",
           r.status_code == 200 and sv.get("survey_id") == survey_id and qcount == 7,
           f"status={r.status_code} qcount={qcount}")

    # 1.6 — submit MISSING required → 400
    r = requests.post(
        f"{API}/p/{ORG_SLUG}/surveys/{survey_id}/submit",
        json={"answers": {"feedback": "no name no city no rating"}},
        timeout=20,
    )
    has_phrase = "missing required answers for:" in r.text
    record("submit.anon.missing_required",
           r.status_code == 400 and has_phrase,
           f"status={r.status_code}, body={r.text[:200]}")

    # 1.7 — submit anon valid #1
    valid1 = {
        "name": "Lakshmi Iyer",
        "feedback": "Good initiative",
        "city": "Coimbatore",
        "skills": ["python", "react"],
        "rating": 5,
        "would_recommend": True,
        "age": 28,
    }
    r = requests.post(
        f"{API}/p/{ORG_SLUG}/surveys/{survey_id}/submit",
        json={"answers": valid1, "contact_name": "Lakshmi Iyer", "contact_email": "lak@example.com"},
        timeout=20,
    )
    rid1 = r.json().get("response_id") if r.status_code == 200 else None
    record("submit.anon.1", r.status_code == 200 and bool(rid1),
           f"status={r.status_code}, rid={rid1}, body={r.text[:200]}")

    # 1.8 — submit anon valid #2
    valid2 = {
        "name": "Arjun Subramanian",
        "feedback": "Loved the workshops",
        "city": "Chennai",
        "skills": ["python", "design"],
        "rating": 3,
        "would_recommend": False,
        "age": 35,
    }
    r = requests.post(
        f"{API}/p/{ORG_SLUG}/surveys/{survey_id}/submit",
        json={"answers": valid2},
        timeout=20,
    )
    rid2 = r.json().get("response_id") if r.status_code == 200 else None
    record("submit.anon.2", r.status_code == 200 and bool(rid2),
           f"status={r.status_code}, rid={rid2}")

    # 1.9 — list shows response_count=2
    r = requests.get(f"{API}/p/{ORG_SLUG}/surveys", timeout=20)
    items = r.json().get("items", []) if r.status_code == 200 else []
    sv = next((s for s in items if s.get("survey_id") == survey_id), None)
    rc = sv.get("response_count") if sv else None
    record("list.response_count==2", rc == 2, f"actual={rc}")

    # 1.10 — aggregate
    r = requests.get(f"{API}/p/{ORG_SLUG}/surveys/{survey_id}/aggregate", timeout=20)
    agg = r.json() if r.status_code == 200 else {}
    total = agg.get("total_responses")
    counts = agg.get("counts", {}) or {}
    avg = agg.get("avg_per_q", {}) or {}
    city_buckets = counts.get("city", {}).get("buckets", {})
    skills_buckets = counts.get("skills", {}).get("buckets", {})
    yn_buckets = counts.get("would_recommend", {}).get("buckets", {})
    record("agg.total==2", total == 2, f"actual={total}")
    record("agg.counts.city",
           city_buckets.get("Coimbatore") == 1 and city_buckets.get("Chennai") == 1,
           f"actual={city_buckets}")
    record("agg.counts.skills",
           skills_buckets.get("python") == 2 and skills_buckets.get("react") == 1
           and skills_buckets.get("design") == 1,
           f"actual={skills_buckets}")
    record("agg.counts.would_recommend",
           yn_buckets.get("yes") == 1 and yn_buckets.get("no") == 1,
           f"actual={yn_buckets}")
    record("agg.avg.rating==4.0", avg.get("rating") == 4.0, f"actual={avg.get('rating')}")
    record("agg.avg.age==31.5", avg.get("age") == 31.5, f"actual={avg.get('age')}")

    # 1.11 — list responses USER 403
    r = requests.get(f"{API}/p/{ORG_SLUG}/surveys/{survey_id}/responses",
                     headers=H(user_tok), timeout=20)
    record("responses.user_forbidden", r.status_code == 403, f"got {r.status_code}")

    # 1.12 — list responses ADMIN 200
    r = requests.get(f"{API}/p/{ORG_SLUG}/surveys/{survey_id}/responses",
                     headers=H(admin_tok), timeout=20)
    body = r.json() if r.status_code == 200 else {}
    rows = body.get("items", [])
    has_answers = bool(rows) and all("answers" in row for row in rows)
    record("responses.admin",
           r.status_code == 200 and len(rows) == 2 and has_answers,
           f"status={r.status_code} count={len(rows)} has_answers={has_answers}")

    # 1.13 — Update as ADMIN
    new_title = f"Regression Survey UPDATED {int(time.time())}"
    update_payload = dict(survey_payload)
    update_payload["title"] = new_title
    r = requests.put(f"{API}/p/{ORG_SLUG}/surveys/{survey_id}",
                     json=update_payload, headers=H(admin_tok), timeout=20)
    record("update.admin", r.status_code == 200, f"status={r.status_code}")
    r = requests.get(f"{API}/p/{ORG_SLUG}/surveys/{survey_id}", timeout=20)
    title = r.json().get("survey", {}).get("title") if r.status_code == 200 else None
    record("update.title_persisted", title == new_title, f"actual={title}")

    # 1.14 — deactivate → submit 409
    closed_payload = dict(update_payload)
    closed_payload["is_active"] = False
    r = requests.put(f"{API}/p/{ORG_SLUG}/surveys/{survey_id}",
                     json=closed_payload, headers=H(admin_tok), timeout=20)
    record("update.deactivate", r.status_code == 200, f"status={r.status_code}")
    r = requests.post(f"{API}/p/{ORG_SLUG}/surveys/{survey_id}/submit",
                      json={"answers": valid1}, timeout=20)
    record("submit.after_close.409",
           r.status_code == 409 and "survey is closed" in r.text,
           f"status={r.status_code}, body={r.text[:200]}")

    # 1.15 — DELETE as ADMIN
    r = requests.delete(f"{API}/p/{ORG_SLUG}/surveys/{survey_id}",
                        headers=H(admin_tok), timeout=20)
    record("delete.admin", r.status_code == 200, f"status={r.status_code}")

    # 1.16 — GET single → 404
    r = requests.get(f"{API}/p/{ORG_SLUG}/surveys/{survey_id}", timeout=20)
    record("get.after_delete.404", r.status_code == 404, f"status={r.status_code}")

    # 1.17 — aggregate after delete → 404
    r = requests.get(f"{API}/p/{ORG_SLUG}/surveys/{survey_id}/aggregate", timeout=20)
    record("agg.after_delete.404", r.status_code == 404, f"status={r.status_code}")


# ======================================================================
# SECTION 2 — ExpertNet v3.9.0 video_url
# ======================================================================
print("\n────── ExpertNet v3.9.0 video_url ──────")

EXPECTED_PREFIX = "/tools/jitsi-room?room="

expert_payload = {
    "name": f"Test Mentor {uuid.uuid4().hex[:6]}",
    "headline": "Career & Skills Mentor",
    "bio": "v3.9.0 jitsi regression",
    "specializations": ["career", "skills"],
    "languages": ["en", "ta"],
    "hourly_rate_inr": 1500,
    "time_zone": "Asia/Kolkata",
    "is_active": True,
    "accepts_instant_calls": True,
}
r = requests.post(f"{API}/expert-net/experts", json=expert_payload, headers=H(user_tok), timeout=20)
expert_id = r.json().get("expert_id") if r.status_code == 200 else None
record("expertnet.expert.create", bool(expert_id),
       f"status={r.status_code}, body={r.text[:200]}")

if expert_id:
    r = requests.post(f"{API}/expert-net/experts/{expert_id}/online",
                      json={"is_online": True}, headers=H(user_tok), timeout=20)
    record("expertnet.expert.online", r.status_code == 200, f"status={r.status_code}")

    # 2.A — connect-now
    r = requests.post(f"{API}/expert-net/experts/{expert_id}/connect-now",
                      headers=H(admin_tok), timeout=20)
    body = r.json() if r.status_code == 200 else {}
    vurl = body.get("video_url", "")
    record(
        "expertnet.connect-now.video_url",
        r.status_code == 200 and isinstance(vurl, str) and vurl.startswith(EXPECTED_PREFIX),
        f"status={r.status_code} session_id={body.get('session_id')} video_url={vurl}",
    )

    # 2.B — booking → start-call
    today = datetime.now(timezone.utc)
    weekday = today.weekday()
    avail_payload = {
        "windows": [
            {"weekday": weekday, "start_minutes": 0, "end_minutes": 24 * 60,
             "slot_minutes": 30}
        ],
        "blackout_dates": [],
    }
    r = requests.put(f"{API}/expert-net/experts/{expert_id}/availability",
                     json=avail_payload, headers=H(user_tok), timeout=20)
    record("expertnet.availability.set", r.status_code == 200,
           f"status={r.status_code}, body={r.text[:200]}")

    r = requests.put(f"{API}/expert-net/experts/{expert_id}/intake-form",
                     json={
                         "title": "Booking intake",
                         "mode": "builtin",
                         "fields": [
                             {"field_id": "goal", "label": "Goal",
                              "field_type": "short_text", "required": False}
                         ],
                         "is_required_before_booking": False,
                     },
                     headers=H(user_tok), timeout=20)
    record("expertnet.intake.set", r.status_code == 200,
           f"status={r.status_code} body={r.text[:200]}")

    # Slots endpoint requires auth
    r = requests.get(f"{API}/expert-net/experts/{expert_id}/slots?days_ahead=14",
                     headers=H(admin_tok), timeout=20)
    body = r.json() if r.status_code == 200 else {}
    slots = body.get("slots") or []
    record("expertnet.slots.list",
           r.status_code == 200 and len(slots) > 0,
           f"status={r.status_code} count={len(slots)} sample={slots[:1]}")

    booking_id = None
    if slots:
        first = slots[0]
        start_iso = first.get("start") if isinstance(first, dict) else first
        duration = first.get("duration_minutes", 30) if isinstance(first, dict) else 30
        bp = {
            "expert_id": expert_id,
            "slot_start_iso": start_iso,
            "duration_minutes": duration,
            "intake_response": {},
        }
        r = requests.post(f"{API}/expert-net/bookings", json=bp, headers=H(admin_tok), timeout=20)
        booking_id = r.json().get("booking_id") if r.status_code == 200 else None
        record("expertnet.booking.create", bool(booking_id),
               f"status={r.status_code}, body={r.text[:200]}")

    if booking_id:
        r = requests.post(f"{API}/expert-net/bookings/{booking_id}/confirm",
                          headers=H(user_tok), timeout=20)
        record("expertnet.booking.confirm", r.status_code == 200,
               f"status={r.status_code}, body={r.text[:200]}")

        r = requests.post(f"{API}/expert-net/bookings/{booking_id}/start-call",
                          headers=H(admin_tok), timeout=20)
        body = r.json() if r.status_code == 200 else {}
        vurl = body.get("video_url", "")
        record(
            "expertnet.start-call.video_url",
            r.status_code == 200 and isinstance(vurl, str) and vurl.startswith(EXPECTED_PREFIX),
            f"status={r.status_code} video_url={vurl}",
        )

# 2.C — Webinar create + start
webinar_payload = {
    "title": f"Regression Webinar {int(time.time())}",
    "description": "v3.9.0 jitsi-room regression",
    "starts_at_iso": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    "duration_minutes": 60,
    "is_free": True,
    "price_inr": 0,
    "capacity": 100,
    "language": "en",
}
r = requests.post(f"{API}/expert-net/webinars", json=webinar_payload, headers=H(user_tok), timeout=20)
webinar_id = r.json().get("webinar_id") if r.status_code == 200 else None
record("expertnet.webinar.create", bool(webinar_id),
       f"status={r.status_code}, body={r.text[:300]}")

if webinar_id:
    r = requests.post(f"{API}/expert-net/webinars/{webinar_id}/start",
                      headers=H(user_tok), timeout=20)
    body = r.json() if r.status_code == 200 else {}
    vurl = body.get("video_url", "")
    record(
        "expertnet.webinar.start.video_url",
        r.status_code == 200 and isinstance(vurl, str) and vurl.startswith(EXPECTED_PREFIX),
        f"status={r.status_code} video_url={vurl}",
    )


# ======================================================================
# Summary
# ======================================================================
print("\n========== SUMMARY ==========")
total = len(results)
passed = sum(1 for x in results if x["ok"])
failed = total - passed
print(f"Total: {total}, Passed: {passed}, Failed: {failed}")

if failed:
    print("\nFailed cases:")
    for x in results:
        if not x["ok"]:
            print(f"  - {x['name']}: {x['detail']}")

sys.exit(0 if failed == 0 else 1)
