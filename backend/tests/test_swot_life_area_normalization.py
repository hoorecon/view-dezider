"""Backend tests for SWOT life_area_id normalization (Phase 2 follow-up).

Verifies the /app/backend/routes/swot.py:_normalize_life_area_id() fix:

For a SWOT created with life_area set to any of:
  - bare slug  ("career")
  - canonical  ("la_career")
  - label      ("Career")
the resulting template's `life_area_id` MUST be the canonical "la_career",
AND the template must surface in
GET /api/hos/templates/suggest
   ?acting_as=INDIVIDUAL&life_area_id=la_career&ask_type_id=at_problem&module=swot
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get(
    "EXPO_PUBLIC_BACKEND_URL",
    "https://repo-blueprint-1.preview.emergentagent.com",
).rstrip("/")

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _create_swot_with_life_area(token, life_area_value):
    r = requests.post(
        f"{BASE_URL}/api/swot",
        headers=_hdr(token),
        json={
            "title": f"TEST_LA_NORM_{life_area_value}_{uuid.uuid4().hex[:6]}",
            "context": "life_area normalization test",
            "decision_type": "problem",
            "life_area": life_area_value,
        },
        timeout=15,
    )
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    # Make sure life_area survived the create (some routes drop unknown fields).
    # If it didn't, set it explicitly via PUT.
    fetched = requests.get(f"{BASE_URL}/api/swot/{sid}", headers=_hdr(token), timeout=15)
    if fetched.status_code == 200:
        if not fetched.json().get("life_area"):
            requests.put(
                f"{BASE_URL}/api/swot/{sid}",
                headers=_hdr(token),
                json={"life_area": life_area_value},
                timeout=15,
            )
    return sid


def _fill_swot(token, sid):
    requests.put(
        f"{BASE_URL}/api/swot/{sid}",
        headers=_hdr(token),
        json={
            "strengths":     [{"text": "S item", "description": "", "impact": 8}],
            "weaknesses":    [{"text": "W item", "description": "", "impact": 6}],
            "opportunities": [{"text": "O item", "description": "", "impact": 7}],
            "threats":       [{"text": "T item", "description": "", "impact": 9}],
        },
        timeout=15,
    )


def _save_as_template(token, sid, name):
    r = requests.post(
        f"{BASE_URL}/api/swot/{sid}/save-as-template",
        headers=_hdr(token),
        json={"name": name, "description": "norm test", "is_public": True},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()["template_id"]


def _fetch_template(token, tid):
    r = requests.get(f"{BASE_URL}/api/hos/templates/{tid}", headers=_hdr(token), timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize(
    "life_area_input,expected_canonical",
    [
        ("career",     "la_career"),
        ("la_career",  "la_career"),
        ("Career",     "la_career"),
        ("holistic_health", "la_health"),
        ("Physical, Mental & Emotional Health", "la_health"),
    ],
)
def test_life_area_normalized_to_canonical(admin_token, life_area_input, expected_canonical):
    """All three input shapes must normalize to canonical la_* id in the template."""
    sid = _create_swot_with_life_area(admin_token, life_area_input)
    _fill_swot(admin_token, sid)
    tid = _save_as_template(
        admin_token, sid,
        f"TEST_NORM_{life_area_input}_{uuid.uuid4().hex[:6]}",
    )

    tpl = _fetch_template(admin_token, tid)
    assert tpl.get("life_area_id") == expected_canonical, (
        f"life_area input '{life_area_input}' yielded "
        f"life_area_id={tpl.get('life_area_id')!r}, expected {expected_canonical!r}"
    )

    requests.delete(f"{BASE_URL}/api/swot/{sid}", headers=_hdr(admin_token), timeout=15)


def test_template_surfaces_in_suggest_for_la_career(admin_token):
    """Round-trip: create with bare slug 'career', confirm it appears in
    /api/hos/templates/suggest?life_area_id=la_career&module=swot."""
    sid = _create_swot_with_life_area(admin_token, "career")
    _fill_swot(admin_token, sid)
    tid = _save_as_template(
        admin_token, sid, f"TEST_SUGGEST_career_{uuid.uuid4().hex[:6]}"
    )

    r = requests.get(
        f"{BASE_URL}/api/hos/templates/suggest"
        f"?acting_as=INDIVIDUAL&life_area_id=la_career"
        f"&ask_type_id=at_problem&module=swot",
        headers=_hdr(admin_token),
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    templates = body if isinstance(body, list) else (
        body.get("templates") or body.get("results") or []
    )
    ids = [t.get("id") for t in templates]
    assert tid in ids, (
        f"template {tid} (life_area_id=la_career, module=swot) NOT in suggest "
        f"results. Got {len(ids)} templates. First 5 ids: {ids[:5]}"
    )

    # Spot-check: surfaced template must carry swot flags on factors.
    tpl = next(t for t in templates if t.get("id") == tid)
    flags = sorted(f.get("swot_flag") for f in tpl.get("factors", []))
    assert flags == ["O", "S", "T", "W"], f"flags missing/wrong: {flags}"

    requests.delete(f"{BASE_URL}/api/swot/{sid}", headers=_hdr(admin_token), timeout=15)


def test_unknown_life_area_falls_back_to_empty(admin_token):
    """If life_area cannot be resolved, life_area_id should be '' (wildcard)
    rather than the raw label — confirms the regression mode is gone."""
    sid = _create_swot_with_life_area(admin_token, "totally_made_up_xyz")
    _fill_swot(admin_token, sid)
    tid = _save_as_template(
        admin_token, sid, f"TEST_UNKNOWN_la_{uuid.uuid4().hex[:6]}"
    )
    tpl = _fetch_template(admin_token, tid)
    la = tpl.get("life_area_id")
    assert la in ("", None), (
        f"unknown life_area should normalize to '' (wildcard), got {la!r}"
    )

    requests.delete(f"{BASE_URL}/api/swot/{sid}", headers=_hdr(admin_token), timeout=15)
