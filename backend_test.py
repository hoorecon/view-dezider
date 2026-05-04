"""
Targeted regression tests for v3.5.1 Time Store + DPDP changes.
Scope strictly limited to items listed in the review request.
"""
import subprocess
import sys
import requests

BASE_URL = "http://localhost:8001"

EMAIL = "harden_1777921741@example.com"
PASSWORD = "HardenPass2026!"


def _hr(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def login():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": EMAIL, "password": PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    tok = r.json()["session_token"]
    print("  ✅ Login OK, token captured")
    return tok


def auth_headers(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def test_services_no_filter(tok):
    _hr("2a. GET /api/time-store/services (no filter)")
    r = requests.get(f"{BASE_URL}/api/time-store/services",
                     headers=auth_headers(tok), timeout=20)
    print(f"  status={r.status_code}")
    assert r.status_code == 200, f"want 200, got {r.status_code}: {r.text[:300]}"
    data = r.json()
    services = data.get("services", [])
    print(f"  services.length = {len(services)}")
    assert len(services) >= 20, f"expected >=20 services, got {len(services)}"
    bpd = data.get("buckets_per_day")
    bpw = data.get("buckets_per_week")
    print(f"  buckets_per_day  = {bpd}")
    print(f"  buckets_per_week = {bpw}")
    assert bpd == [30, 60, 120], f"buckets_per_day mismatch: {bpd}"
    assert bpw == [180, 300, 600, 900], f"buckets_per_week mismatch: {bpw}"
    has_meta = sum(1 for s in services
                   if s.get("time_save_per_day_min") is not None
                   or s.get("time_save_per_week_min") is not None)
    print(f"  services with time_save metadata = {has_meta}")
    assert has_meta >= 1, "expected at least one service with time_save metadata"
    sid = None
    for s in services:
        if s.get("solution_id"):
            sid = s["solution_id"]
            break
    assert sid, "no solution_id found in catalogue"
    print(f"  picked solution_id = {sid}")
    return sid, services


def test_services_filter_per_day(tok):
    _hr("2b. GET /api/time-store/services?save_minutes_per_day=60")
    r = requests.get(f"{BASE_URL}/api/time-store/services",
                     params={"save_minutes_per_day": 60},
                     headers=auth_headers(tok), timeout=20)
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
    services = r.json().get("services", [])
    print(f"  services.length = {len(services)}")
    assert len(services) >= 1, "expected non-empty for save_minutes_per_day=60"
    bad = [s for s in services if (s.get("time_save_per_day_min") or 0) < 30]
    if bad:
        print(f"  ❌ services violating time_save_per_day_min>=30: {len(bad)}")
        for b in bad[:3]:
            print(f"     - {b.get('title')} day={b.get('time_save_per_day_min')}")
    assert not bad, f"{len(bad)} items violate time_save_per_day_min>=30 filter"
    print("  ✅ all returned items have time_save_per_day_min >= 30")


def test_services_filter_per_week(tok):
    _hr("2c. GET /api/time-store/services?save_minutes_per_week=300")
    r = requests.get(f"{BASE_URL}/api/time-store/services",
                     params={"save_minutes_per_week": 300},
                     headers=auth_headers(tok), timeout=20)
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
    services = r.json().get("services", [])
    print(f"  services.length = {len(services)}")
    assert len(services) >= 1, "expected non-empty for save_minutes_per_week=300"
    bad = [s for s in services if (s.get("time_save_per_week_min") or 0) < 240]
    if bad:
        print(f"  ❌ services violating time_save_per_week_min>=240: {len(bad)}")
        for b in bad[:3]:
            print(f"     - {b.get('title')} wk={b.get('time_save_per_week_min')}")
    assert not bad, f"{len(bad)} items violate time_save_per_week_min>=240 filter"
    print("  ✅ all returned items have time_save_per_week_min >= 240")


def test_purchase(tok, solution_id):
    _hr("3a. POST /api/time-store/purchase")
    r = requests.post(f"{BASE_URL}/api/time-store/purchase",
                      headers=auth_headers(tok),
                      json={"solution_id": solution_id,
                            "save_minutes_per_day": 30,
                            "note": "uat"}, timeout=20)
    print(f"  status={r.status_code}")
    print(f"  body={r.text[:300]}")
    assert r.status_code == 200, (
        f"purchase failed: {r.status_code} — collection-name fix not effective?")
    body = r.json()
    assert body.get("order_id"), "missing order_id"
    assert body.get("status") == "pending_payment"
    print(f"  ✅ order_id={body['order_id']}, status=pending_payment")
    return body["order_id"]


def test_purchases_list(tok, expected_order_id):
    _hr("3b. GET /api/time-store/purchases")
    r = requests.get(f"{BASE_URL}/api/time-store/purchases",
                     headers=auth_headers(tok), timeout=15)
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
    items = r.json().get("items", [])
    print(f"  items.length = {len(items)}")
    found = any(i.get("order_id") == expected_order_id for i in items)
    assert found, f"new order {expected_order_id} not present in listing"
    new = next(i for i in items if i.get("order_id") == expected_order_id)
    print(f"  ✅ found new order: status={new.get('status')} provider={new.get('payment_provider')}")
    assert new.get("payment_provider") == "mock"


def test_delegate_negative(tok):
    _hr("4a. POST /api/time-store/delegate (invalid source_type → 400)")
    r = requests.post(f"{BASE_URL}/api/time-store/delegate",
                      headers=auth_headers(tok),
                      json={"source_type": "INVALID", "source_id": "x",
                            "description": "uat", "estimated_minutes_saved": 30},
                      timeout=15)
    print(f"  status={r.status_code} body={r.text[:200]}")
    assert r.status_code == 400, f"want 400, got {r.status_code}"
    print("  ✅ rejected with 400")


def test_delegate_positive(tok):
    _hr("4b. POST /api/time-store/delegate (valid)")
    r = requests.post(f"{BASE_URL}/api/time-store/delegate",
                      headers=auth_headers(tok),
                      json={"source_type": "ctt_task", "source_id": "x",
                            "description": "uat", "estimated_minutes_saved": 30},
                      timeout=15)
    print(f"  status={r.status_code} body={r.text[:200]}")
    assert r.status_code == 200
    body = r.json()
    assert body.get("delegation_id"), "missing delegation_id"
    print(f"  ✅ delegation_id={body['delegation_id']}")


def test_delegations_list(tok):
    _hr("4c. GET /api/time-store/delegations")
    r = requests.get(f"{BASE_URL}/api/time-store/delegations",
                     headers=auth_headers(tok), timeout=15)
    assert r.status_code == 200, f"got {r.status_code}"
    items = r.json().get("items", [])
    print(f"  items.length = {len(items)}")
    print("  ✅ listing OK")


def test_time_audit(tok):
    _hr("5. GET /api/time-store/time-audit")
    r = requests.get(f"{BASE_URL}/api/time-store/time-audit",
                     headers=auth_headers(tok), timeout=20)
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
    data = r.json()
    print(f"  keys={list(data.keys())}")
    for k in ("opportunities", "total_minutes_saveable_per_week",
              "total_hours_saveable_per_week"):
        assert k in data, f"missing key: {k}"
    print(f"  opportunities={len(data.get('opportunities', []))}, "
          f"weekly_min={data['total_minutes_saveable_per_week']}, "
          f"weekly_hr={data['total_hours_saveable_per_week']}")
    print("  ✅ shape OK (empty array acceptable for this user)")


def _normalize_dpdp_status_payload(d):
    """Map actual response keys to test-plan keys for assertion clarity."""
    has_pending = (d.get("deletion_status") == "pending")
    return {
        "has_pending_deletion": has_pending,
        "deletion_requested_at": d.get("deletion_requested_at"),
        "scheduled_purge_at": d.get("deletion_grace_until"),
        "raw": d,
    }


def get_dpdp_status(tok, expect_pending=None):
    r = requests.get(f"{BASE_URL}/api/dpdp/status",
                     headers=auth_headers(tok), timeout=15)
    assert r.status_code == 200, f"status got {r.status_code}: {r.text[:300]}"
    data = r.json()
    norm = _normalize_dpdp_status_payload(data)
    print(f"  raw={data}")
    print(f"  has_pending_deletion(derived)={norm['has_pending_deletion']}")
    if expect_pending is True:
        assert norm["has_pending_deletion"] is True
        assert norm["deletion_requested_at"]
        assert norm["scheduled_purge_at"]
    elif expect_pending is False:
        assert norm["has_pending_deletion"] is False
    return norm


def test_dpdp_export(tok):
    _hr("6b. GET /api/dpdp/export")
    r = requests.get(f"{BASE_URL}/api/dpdp/export",
                     headers=auth_headers(tok), timeout=60)
    assert r.status_code == 200, f"export got {r.status_code}: {r.text[:300]}"
    body = r.json()
    print(f"  top-level keys = {list(body.keys())}")
    print(f"  body size = {len(r.content)} bytes")
    coll_keys = list((body.get("collections") or {}).keys())
    print(f"  collections exported = {coll_keys}")
    assert "user_id" in body and "collections" in body
    print("  ✅ export OK")


def test_dpdp_full_roundtrip(tok):
    _hr("6a. GET /api/dpdp/status (initial)")
    initial = get_dpdp_status(tok, expect_pending=None)

    if initial["has_pending_deletion"]:
        print("  ⚠ already pending — cancelling first to start clean")
        rc = requests.post(f"{BASE_URL}/api/dpdp/cancel-delete",
                           headers=auth_headers(tok), timeout=15)
        print(f"  cancel pre-clean status={rc.status_code}")
        assert rc.status_code == 200

    test_dpdp_export(tok)

    _hr("6c. POST /api/dpdp/delete-request")
    r = requests.post(f"{BASE_URL}/api/dpdp/delete-request",
                      headers=auth_headers(tok),
                      json={"confirmation": "DELETE MY ACCOUNT", "reason": "uat"},
                      timeout=15)
    print(f"  status={r.status_code} body={r.text[:300]}")
    assert r.status_code in (200, 409), f"got {r.status_code}"

    _hr("6d. GET /api/dpdp/status (should be pending)")
    pending = get_dpdp_status(tok, expect_pending=True)
    print(f"  ✅ pending=true, requested_at={pending['deletion_requested_at']}, "
          f"scheduled_purge_at={pending['scheduled_purge_at']}")

    _hr("6e. POST /api/dpdp/cancel-delete")
    r = requests.post(f"{BASE_URL}/api/dpdp/cancel-delete",
                      headers=auth_headers(tok), timeout=15)
    print(f"  status={r.status_code} body={r.text[:200]}")
    assert r.status_code == 200

    _hr("6f. GET /api/dpdp/status (should be cleared)")
    cleared = get_dpdp_status(tok, expect_pending=False)
    print(f"  ✅ has_pending_deletion={cleared['has_pending_deletion']}")


def test_seed_idempotency():
    _hr("7. Re-run seed_time_store_services.py (idempotency)")
    p = subprocess.run(
        [sys.executable, "/app/backend/scripts/seed_time_store_services.py"],
        capture_output=True, text=True, timeout=60,
    )
    print("  stdout:", p.stdout.strip())
    if p.stderr.strip():
        print("  stderr:", p.stderr.strip())
    assert p.returncode == 0, "seed script failed"
    out = p.stdout
    assert "new inserted:     0" in out or "new inserted: 0" in out, \
        f"Expected 'new inserted: 0' on idempotent run, got:\n{out}"
    print("  ✅ idempotent — no duplicate inserts on second run")


def main():
    failures = []
    tok = login()

    try:
        sid, _ = test_services_no_filter(tok)
    except AssertionError as e:
        failures.append(("services-no-filter", str(e))); sid = None

    for name, fn in [
        ("services-filter-per-day", lambda: test_services_filter_per_day(tok)),
        ("services-filter-per-week", lambda: test_services_filter_per_week(tok)),
    ]:
        try:
            fn()
        except AssertionError as e:
            failures.append((name, str(e)))

    order_id = None
    if sid:
        try:
            order_id = test_purchase(tok, sid)
        except AssertionError as e:
            failures.append(("purchase", str(e)))
    if order_id:
        try:
            test_purchases_list(tok, order_id)
        except AssertionError as e:
            failures.append(("purchases-list", str(e)))

    for name, fn in [
        ("delegate-negative", lambda: test_delegate_negative(tok)),
        ("delegate-positive", lambda: test_delegate_positive(tok)),
        ("delegations-list", lambda: test_delegations_list(tok)),
        ("time-audit", lambda: test_time_audit(tok)),
    ]:
        try:
            fn()
        except AssertionError as e:
            failures.append((name, str(e)))

    try:
        test_dpdp_full_roundtrip(tok)
    except AssertionError as e:
        failures.append(("dpdp-roundtrip", str(e)))

    try:
        test_seed_idempotency()
    except AssertionError as e:
        failures.append(("seed-idempotency", str(e)))

    _hr("RESULTS")
    if failures:
        print(f"❌ {len(failures)} failure(s):")
        for n, msg in failures:
            print(f"   - {n}: {msg}")
        sys.exit(1)
    print("✅ All targeted v3.5.1 checks passed.")


if __name__ == "__main__":
    main()
