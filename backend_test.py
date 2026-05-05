"""ExpertNet v3.8.0 backend regression — 37 cases across Phases A-D.

Usage: python /app/backend_test.py
"""
import time
import requests

BASE = "http://localhost:8001/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"
USER_EMAIL = "harden_1777921741@example.com"
USER_PASS = "HardenPass2026!"


def _login(email, password):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return r.json()["session_token"]


def _hdr(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


RESULTS = []


def rec(case, ok, detail=""):
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {case} :: {detail}")
    RESULTS.append((case, ok, detail))


def main():
    try:
        admin_tok = _login(ADMIN_EMAIL, ADMIN_PASS)
        user_tok = _login(USER_EMAIL, USER_PASS)
        rec("Auth.admin+user", True, "both logged in")
    except AssertionError as e:
        rec("Auth.admin+user", False, str(e))
        return

    ts = int(time.time())

    # Phase A
    body = {
        "name": "Dr. Test Mentor",
        "headline": "Career coach",
        "specializations": ["career", "leadership"],
        "languages": ["en", "ta"],
        "hourly_rate_inr": 1500,
        "accepts_instant_calls": True,
    }
    r = requests.post(f"{BASE}/expert-net/experts", headers=_hdr(user_tok), json=body, timeout=30)
    ok = r.status_code == 200 and "expert_id" in r.json()
    expert_id = r.json().get("expert_id") if ok else None
    rec("1. POST /experts as USER", ok, f"status={r.status_code} expert_id={expert_id}")
    if not expert_id:
        return

    r = requests.get(f"{BASE}/expert-net/experts", headers=_hdr(user_tok), timeout=30)
    items = r.json().get("items", [])
    ok = r.status_code == 200 and any(e["expert_id"] == expert_id for e in items)
    rec("2. GET /experts contains new expert", ok, f"status={r.status_code} count={len(items)}")

    r = requests.get(
        f"{BASE}/expert-net/experts?language=ta&min_rate=1000&max_rate=2000",
        headers=_hdr(user_tok), timeout=30,
    )
    items = r.json().get("items", [])
    ok = r.status_code == 200 and any(e["expert_id"] == expert_id for e in items)
    rec("3. GET /experts?language=ta&min_rate=1000&max_rate=2000", ok, f"count={len(items)}")

    r = requests.get(f"{BASE}/expert-net/experts?language=fr", headers=_hdr(user_tok), timeout=30)
    items = r.json().get("items", [])
    ok = r.status_code == 200 and not any(e["expert_id"] == expert_id for e in items)
    rec("4. GET /experts?language=fr excludes", ok, f"count={len(items)}")

    r = requests.get(f"{BASE}/expert-net/experts/{expert_id}", headers=_hdr(user_tok), timeout=30)
    j = r.json() if r.status_code == 200 else {}
    ok = (
        r.status_code == 200
        and j.get("expert", {}).get("expert_id") == expert_id
        and j.get("availability") is None
        and j.get("intake_form") is None
    )
    rec("5. GET /experts/{id} fresh", ok, f"status={r.status_code} avail={j.get('availability')} intake={j.get('intake_form')}")

    r = requests.put(
        f"{BASE}/expert-net/experts/{expert_id}",
        headers=_hdr(admin_tok),
        json={"headline": "Updated by admin"},
        timeout=30,
    )
    ok = r.status_code == 200 and r.json().get("headline") == "Updated by admin"
    rec("6. PUT /experts/{id} as ADMIN override", ok, f"status={r.status_code}")

    other_email = f"xn_other_{ts}@example.com"
    reg = requests.post(
        f"{BASE}/auth/register",
        json={"email": other_email, "password": "UatPass2026!", "name": "Other Tester"},
        timeout=30,
    )
    other_tok = reg.json().get("session_token") if reg.status_code == 200 else None
    if other_tok:
        r = requests.put(
            f"{BASE}/expert-net/experts/{expert_id}",
            headers=_hdr(other_tok),
            json={"headline": "Hijack attempt"},
            timeout=30,
        )
        rec("7. PUT /experts/{id} as different user → 403", r.status_code == 403, f"status={r.status_code}")
    else:
        rec("7. PUT /experts/{id} as different user → 403", False, f"register failed: {reg.status_code} {reg.text}")

    r = requests.post(
        f"{BASE}/expert-net/experts/{expert_id}/online",
        headers=_hdr(user_tok),
        json={"is_online": True},
        timeout=30,
    )
    ok = r.status_code == 200 and r.json().get("is_online") is True
    rec("8. POST /online is_online=true owner", ok, f"status={r.status_code}")

    r = requests.post(f"{BASE}/expert-net/experts/{expert_id}/connect-now", headers=_hdr(admin_tok), timeout=30)
    j = r.json() if r.status_code == 200 else {}
    ok = r.status_code == 200 and str(j.get("session_id", "")).startswith("vc_") and "video_url" in j
    rec("9. POST /connect-now as ADMIN", ok, f"status={r.status_code} session_id={j.get('session_id')}")

    requests.post(
        f"{BASE}/expert-net/experts/{expert_id}/online",
        headers=_hdr(user_tok),
        json={"is_online": False},
        timeout=30,
    )
    r2 = requests.post(f"{BASE}/expert-net/experts/{expert_id}/connect-now", headers=_hdr(admin_tok), timeout=30)
    rec("10. Connect-now when offline → 409", r2.status_code == 409, f"status={r2.status_code}")

    r = requests.post(
        f"{BASE}/expert-net/experts/{expert_id}/online",
        headers=_hdr(user_tok),
        json={"is_online": True},
        timeout=30,
    )
    rec("11. Toggle back online", r.status_code == 200, f"status={r.status_code}")

    # Phase B
    r = requests.put(
        f"{BASE}/expert-net/experts/{expert_id}/availability",
        headers=_hdr(user_tok),
        json={
            "windows": [{"weekday": 1, "start_minutes": 540, "end_minutes": 780, "slot_minutes": 30}],
            "blackout_dates": [],
        },
        timeout=30,
    )
    rec("12. PUT /availability owner", r.status_code == 200, f"status={r.status_code}")

    r = requests.put(
        f"{BASE}/expert-net/experts/{expert_id}/intake-form",
        headers=_hdr(user_tok),
        json={
            "title": "Pre-call form",
            "mode": "builtin",
            "is_required_before_booking": True,
            "fields": [{"field_id": "goal", "label": "Your goal", "field_type": "short_text", "required": True}],
        },
        timeout=30,
    )
    rec("13. PUT /intake-form builtin", r.status_code == 200, f"status={r.status_code}")

    r = requests.put(
        f"{BASE}/expert-net/experts/{expert_id}/intake-form",
        headers=_hdr(user_tok),
        json={"mode": "external", "external_url": "https://forms.gle/abc", "title": "Form", "fields": []},
        timeout=30,
    )
    rec("14. PUT /intake-form external with url", r.status_code == 200, f"status={r.status_code}")

    r = requests.put(
        f"{BASE}/expert-net/experts/{expert_id}/intake-form",
        headers=_hdr(user_tok),
        json={"mode": "external", "title": "Form", "fields": []},
        timeout=30,
    )
    rec("15. PUT /intake-form external no url → 400", r.status_code == 400, f"status={r.status_code} body={r.text[:160]}")

    r = requests.put(
        f"{BASE}/expert-net/experts/{expert_id}/intake-form",
        headers=_hdr(user_tok),
        json={
            "title": "Pre-call form",
            "mode": "builtin",
            "is_required_before_booking": True,
            "fields": [{"field_id": "goal", "label": "Your goal", "field_type": "short_text", "required": True}],
        },
        timeout=30,
    )
    rec("16. PUT /intake-form back to builtin", r.status_code == 200, f"status={r.status_code}")

    r = requests.get(f"{BASE}/expert-net/experts/{expert_id}/slots?days_ahead=14", headers=_hdr(user_tok), timeout=30)
    slots = r.json().get("slots", []) if r.status_code == 200 else []
    ok = r.status_code == 200 and len(slots) >= 1
    first_slot = slots[0]["start"] if slots else None
    rec("17. GET /slots?days_ahead=14", ok, f"status={r.status_code} slots={len(slots)} first={first_slot}")

    if not first_slot:
        rec("ABORT", False, "no slots")
        return

    r = requests.post(
        f"{BASE}/expert-net/bookings",
        headers=_hdr(admin_tok),
        json={"expert_id": expert_id, "slot_start_iso": first_slot, "duration_minutes": 30},
        timeout=30,
    )
    ok = r.status_code == 400 and ("intake" in r.text.lower() or "goal" in r.text.lower())
    rec("18. POST /bookings missing intake → 400", ok, f"status={r.status_code} body={r.text[:160]}")

    r = requests.post(
        f"{BASE}/expert-net/bookings",
        headers=_hdr(admin_tok),
        json={
            "expert_id": expert_id,
            "slot_start_iso": first_slot,
            "duration_minutes": 30,
            "intake_response": {"goal": "Get promoted"},
        },
        timeout=30,
    )
    j = r.json() if r.status_code == 200 else {}
    booking_id = j.get("booking_id")
    ok = r.status_code == 200 and booking_id and j.get("status") in ("pending", "confirmed")
    rec("19. POST /bookings with intake", ok, f"status={r.status_code} booking_id={booking_id} bk_status={j.get('status')}")

    if not booking_id:
        return

    r = requests.post(
        f"{BASE}/expert-net/bookings",
        headers=_hdr(admin_tok),
        json={
            "expert_id": expert_id,
            "slot_start_iso": first_slot,
            "duration_minutes": 30,
            "intake_response": {"goal": "Second"},
        },
        timeout=30,
    )
    rec("20. POST /bookings conflict → 409", r.status_code == 409, f"status={r.status_code}")

    r = requests.post(f"{BASE}/expert-net/bookings/{booking_id}/confirm", headers=_hdr(user_tok), timeout=30)
    ok = r.status_code == 200 and r.json().get("status") == "confirmed"
    rec("21. POST /confirm as OWNER", ok, f"status={r.status_code}")

    r = requests.post(f"{BASE}/expert-net/bookings/{booking_id}/start-call", headers=_hdr(admin_tok), timeout=30)
    j = r.json() if r.status_code == 200 else {}
    ok = r.status_code == 200 and "session_id" in j
    rec("22. POST /start-call as ADMIN", ok, f"status={r.status_code} session_id={j.get('session_id')}")

    # Phase C
    from pymongo import MongoClient
    mongo = MongoClient("mongodb://localhost:27017")
    sol = mongo.test_database.solutions_store.find_one({"is_authorized": True}, {"_id": 0, "solution_id": 1, "name": 1})
    sid = sol["solution_id"] if sol else None
    rec("23. Pick solution_id from db.solutions_store", bool(sid), f"solution_id={sid} name={sol.get('name') if sol else None}")
    if not sid:
        return

    r = requests.post(
        f"{BASE}/expert-net/bookings/{booking_id}/recommend",
        headers=_hdr(user_tok),
        json={
            "booking_id": booking_id,
            "solution_id": sid,
            "note": "Try this",
            "create_ctt_task": True,
            "create_lifestyle_routine": True,
            "routine_frequency": "weekly",
        },
        timeout=30,
    )
    j = r.json() if r.status_code == 200 else {}
    ok = r.status_code == 200 and j.get("linked_ctt_task_id") and j.get("linked_routine_id")
    rec("24. POST /recommend as OWNER", ok,
        f"status={r.status_code} ctt={j.get('linked_ctt_task_id')} routine={j.get('linked_routine_id')}")

    r = requests.post(
        f"{BASE}/expert-net/bookings/{booking_id}/recommend",
        headers=_hdr(admin_tok),
        json={
            "booking_id": booking_id,
            "solution_id": sid,
            "note": "Admin rec",
            "create_ctt_task": False,
            "create_lifestyle_routine": False,
            "routine_frequency": "weekly",
        },
        timeout=30,
    )
    ok = r.status_code in (200, 403)
    rec("25. POST /recommend as ADMIN (200 or 403 accepted)", ok, f"status={r.status_code}")

    r = requests.post(
        f"{BASE}/time-store/purchase",
        headers=_hdr(admin_tok),
        json={"solution_id": sid, "save_minutes_per_day": 15},
        timeout=30,
    )
    j = r.json() if r.status_code == 200 else {}
    order_id = j.get("order_id")
    ok = r.status_code == 200 and order_id
    rec("26. POST /time-store/purchase as ADMIN", ok, f"status={r.status_code} order_id={order_id}")

    if order_id:
        r = requests.post(
            f"{BASE}/expert-net/deliveries/from-purchase/{order_id}",
            headers=_hdr(admin_tok),
            timeout=30,
        )
        j = r.json() if r.status_code == 200 else {}
        ok = r.status_code == 200 and j.get("status") == "ordered"
        rec("27. POST /deliveries/from-purchase", ok, f"status={r.status_code} dstatus={j.get('status')}")

        r = requests.put(
            f"{BASE}/expert-net/deliveries/{order_id}/status",
            headers=_hdr(admin_tok),
            json={"status": "shipped", "tracking_number": "BLR-TEST"},
            timeout=30,
        )
        j = r.json() if r.status_code == 200 else {}
        history_len = len(j.get("history", [])) if isinstance(j, dict) else 0
        ok = r.status_code == 200 and j.get("status") == "shipped" and history_len >= 2
        rec("28. PUT /deliveries/{id}/status shipped", ok,
            f"status={r.status_code} dstatus={j.get('status')} history_len={history_len}")

        r = requests.get(f"{BASE}/expert-net/deliveries", headers=_hdr(admin_tok), timeout=30)
        items = r.json().get("items", []) if r.status_code == 200 else []
        ok = r.status_code == 200 and any(d.get("order_id") == order_id for d in items)
        rec("29. GET /deliveries contains order", ok, f"status={r.status_code} count={len(items)}")

    # Phase D
    r = requests.post(
        f"{BASE}/expert-net/webinars",
        headers=_hdr(user_tok),
        json={
            "title": "Free Test Webinar",
            "starts_at_iso": "2026-12-21T10:00:00+00:00",
            "duration_minutes": 30,
            "is_free": True,
            "price_inr": 0,
            "capacity": 50,
        },
        timeout=30,
    )
    j = r.json() if r.status_code == 200 else {}
    webinar_id = j.get("webinar_id")
    ok = r.status_code == 200 and webinar_id
    rec("30. POST /webinars as OWNER", ok, f"status={r.status_code} webinar_id={webinar_id}")

    nx_email = f"xn_wnonexpert_{ts}@example.com"
    reg2 = requests.post(
        f"{BASE}/auth/register",
        json={"email": nx_email, "password": "UatPass2026!", "name": "Not Expert"},
        timeout=30,
    )
    nx_tok = reg2.json().get("session_token") if reg2.status_code == 200 else None
    if nx_tok:
        r = requests.post(
            f"{BASE}/expert-net/webinars",
            headers=_hdr(nx_tok),
            json={
                "title": "Unauth webinar",
                "starts_at_iso": "2026-12-22T10:00:00+00:00",
                "duration_minutes": 30,
                "is_free": True,
                "price_inr": 0,
            },
            timeout=30,
        )
        rec("31. POST /webinars as non-expert → 403", r.status_code == 403, f"status={r.status_code}")
    else:
        rec("31. POST /webinars as non-expert → 403", False, f"register failed: {reg2.status_code}")

    if webinar_id:
        r = requests.post(
            f"{BASE}/expert-net/webinars/register",
            headers=_hdr(admin_tok),
            json={"webinar_id": webinar_id},
            timeout=30,
        )
        j = r.json() if r.status_code == 200 else {}
        ok = r.status_code == 200 and j.get("payment_status") == "paid_free"
        rec("32. POST /webinars/register ADMIN free", ok, f"status={r.status_code} pmt={j.get('payment_status')}")

        r = requests.post(
            f"{BASE}/expert-net/webinars/register",
            headers=_hdr(admin_tok),
            json={"webinar_id": webinar_id},
            timeout=30,
        )
        j = r.json() if r.status_code == 200 else {}
        ok = r.status_code == 200 and j.get("already_registered") is True
        rec("33. POST /webinars/register duplicate", ok, f"status={r.status_code} j={j}")

        r = requests.get(f"{BASE}/expert-net/webinars?free_only=true", headers=_hdr(admin_tok), timeout=30)
        items = r.json().get("items", []) if r.status_code == 200 else []
        w = next((x for x in items if x.get("webinar_id") == webinar_id), None)
        ok = r.status_code == 200 and w is not None and w.get("i_am_registered") is True
        rec("34. GET /webinars?free_only=true i_am_registered", ok, f"status={r.status_code} found={bool(w)}")

        r = requests.post(f"{BASE}/expert-net/webinars/{webinar_id}/start", headers=_hdr(user_tok), timeout=30)
        j = r.json() if r.status_code == 200 else {}
        ok = r.status_code == 200 and "video_url" in j
        rec("35. POST /webinars/{id}/start as OWNER", ok, f"status={r.status_code} video_url={j.get('video_url')}")

        r = requests.post(f"{BASE}/expert-net/webinars/{webinar_id}/start", headers=_hdr(admin_tok), timeout=30)
        rec("36. POST /webinars/{id}/start as ADMIN override", r.status_code == 200, f"status={r.status_code}")

        alt_tok = nx_tok or other_tok
        if alt_tok:
            r = requests.post(f"{BASE}/expert-net/webinars/{webinar_id}/start", headers=_hdr(alt_tok), timeout=30)
            rec("37. POST /webinars/{id}/start as non-host → 403", r.status_code == 403, f"status={r.status_code}")
        else:
            rec("37. POST /webinars/{id}/start as non-host → 403", False, "no alt token")

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n===== ExpertNet regression: {passed}/{total} passed =====")
    for c, ok, d in RESULTS:
        if not ok:
            print(f"  FAIL {c} :: {d}")


if __name__ == "__main__":
    main()
