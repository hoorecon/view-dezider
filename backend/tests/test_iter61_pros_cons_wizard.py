"""Iter61 — Pros & Cons wizard tests:
- Duplicate Pro/Con hard-block (409)
- Rename Con → "SHOULD NOT - <new>" factor propagation
- Rename Pro → factor name propagation
- Sub-factor creation + Step 5 metadata persistence (operator, data_type,
  expected_value, unit, weight, data_source)
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/") or "http://localhost:8001"
API = f"{BASE_URL}/api"

CREDS = [
    ("super@test.com", "AdminPass2026!"),
    ("admin@test.com", "AdminPass2026!"),
]


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    token = None
    for email, pw in CREDS:
        r = s.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
        if r.status_code == 200:
            token = r.json().get("session_token") or r.json().get("token") or r.json().get("access_token")
            if token:
                break
    if not token:
        pytest.skip("Could not login with provided test credentials")
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def analysis(session):
    title = f"TEST_iter61_{int(time.time())}"
    r = session.post(f"{API}/pros-cons", json={"title": title, "context": "iter61"}, timeout=30)
    assert r.status_code == 200, r.text
    aid = r.json()["id"]
    # add an option
    r2 = session.post(f"{API}/pros-cons/{aid}/options", json={"name": "Opt A"}, timeout=30)
    assert r2.status_code == 200, r2.text
    oid = r2.json()["id"]
    yield aid, oid
    # cleanup
    try:
        session.delete(f"{API}/pros-cons/{aid}", timeout=15)
    except Exception:
        pass


def test_duplicate_pro_409(session, analysis):
    aid, oid = analysis
    text = "Good salary"
    r1 = session.post(f"{API}/pros-cons/{aid}/options/{oid}/pros", json={"text": text}, timeout=30)
    assert r1.status_code == 200, r1.text
    r2 = session.post(f"{API}/pros-cons/{aid}/options/{oid}/pros", json={"text": text}, timeout=30)
    assert r2.status_code == 409, f"Expected 409, got {r2.status_code}: {r2.text}"
    # case-insensitive too
    r3 = session.post(f"{API}/pros-cons/{aid}/options/{oid}/pros", json={"text": text.upper()}, timeout=30)
    assert r3.status_code == 409, f"Expected 409 (case-insensitive), got {r3.status_code}"


def test_duplicate_con_409(session, analysis):
    aid, oid = analysis
    text = "Long commute"
    r1 = session.post(f"{API}/pros-cons/{aid}/options/{oid}/cons", json={"text": text}, timeout=30)
    assert r1.status_code == 200, r1.text
    r2 = session.post(f"{API}/pros-cons/{aid}/options/{oid}/cons", json={"text": text}, timeout=30)
    assert r2.status_code == 409, f"Expected 409, got {r2.status_code}: {r2.text}"


def test_promote_then_rename_con_updates_factor_name(session, analysis):
    aid, oid = analysis
    # add a fresh con to rename
    r = session.post(f"{API}/pros-cons/{aid}/options/{oid}/cons", json={"text": "Bad weather"}, timeout=30)
    assert r.status_code == 200
    con_id = r.json()["id"]
    # promote
    rp = session.post(f"{API}/pros-cons/{aid}/promote-pros-cons", timeout=30)
    assert rp.status_code == 200, rp.text
    # rename
    ru = session.put(f"{API}/pros-cons/{aid}/options/{oid}/cons/{con_id}",
                     json={"text": "NewConName"}, timeout=30)
    assert ru.status_code == 200, ru.text
    # verify factor name
    rg = session.get(f"{API}/pros-cons/{aid}", timeout=30)
    assert rg.status_code == 200
    doc = rg.json()
    con_item = None
    for opt in doc.get("options", []):
        for c in opt.get("cons", []):
            if c["id"] == con_id:
                con_item = c
                break
    assert con_item is not None and con_item.get("promoted_factor_id"), f"Con not promoted: {con_item}"
    fid = con_item["promoted_factor_id"]
    factor = next((f for f in doc.get("factors", []) if f["id"] == fid), None)
    assert factor is not None, "Promoted factor not found"
    assert factor["name"] == "SHOULD NOT - NewConName", f"Factor name mismatch: {factor['name']}"


def test_promote_then_rename_pro_updates_factor_name(session, analysis):
    aid, oid = analysis
    r = session.post(f"{API}/pros-cons/{aid}/options/{oid}/pros", json={"text": "Good benefits"}, timeout=30)
    assert r.status_code == 200
    pro_id = r.json()["id"]
    rp = session.post(f"{API}/pros-cons/{aid}/promote-pros-cons", timeout=30)
    assert rp.status_code == 200
    ru = session.put(f"{API}/pros-cons/{aid}/options/{oid}/pros/{pro_id}",
                     json={"text": "Awesome perks"}, timeout=30)
    assert ru.status_code == 200, ru.text
    rg = session.get(f"{API}/pros-cons/{aid}", timeout=30)
    doc = rg.json()
    pro_item = None
    for opt in doc.get("options", []):
        for p in opt.get("pros", []):
            if p["id"] == pro_id:
                pro_item = p
                break
    assert pro_item and pro_item.get("promoted_factor_id")
    fid = pro_item["promoted_factor_id"]
    factor = next((f for f in doc.get("factors", []) if f["id"] == fid), None)
    assert factor is not None
    assert factor["name"] == "Awesome perks", f"Pro factor name mismatch: {factor['name']}"


def test_subfactor_and_metadata_persistence(session, analysis):
    aid, _oid = analysis
    # create main factor
    rm = session.post(f"{API}/pros-cons/{aid}/factors", json={"name": "MainCost"}, timeout=30)
    assert rm.status_code == 200, rm.text
    main_id = rm.json()["id"]
    # create sub-factor with parent_id
    rs = session.post(f"{API}/pros-cons/{aid}/factors",
                      json={"name": "Tax", "parent_id": main_id}, timeout=30)
    assert rs.status_code == 200, rs.text
    sub_id = rs.json()["id"]
    # verify sub-factor has parent_id
    rg = session.get(f"{API}/pros-cons/{aid}", timeout=30)
    doc = rg.json()
    sub = next((f for f in doc["factors"] if f["id"] == sub_id), None)
    assert sub is not None and sub.get("parent_id") == main_id, f"Sub-factor parent_id missing: {sub}"

    # PUT metadata
    payload = {
        "operator": ">=",
        "data_type": "numeric",
        "expected_value": "1000",
        "unit": "INR",
        "weight": 60,
        "data_source": {"type": "ai_llm", "config": {"prompt": "x"}},
    }
    ru = session.put(f"{API}/pros-cons/{aid}/factors/{sub_id}", json=payload, timeout=30)
    assert ru.status_code == 200, ru.text
    # GET and verify persistence
    rg2 = session.get(f"{API}/pros-cons/{aid}", timeout=30)
    doc2 = rg2.json()
    f = next((f for f in doc2["factors"] if f["id"] == sub_id), None)
    assert f is not None
    for k, v in payload.items():
        assert f.get(k) == v, f"Field {k} did not persist correctly: got {f.get(k)}, expected {v}"
