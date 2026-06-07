"""Iteration 79 — Decision Template Landing-Step regression.

BUG: 'Copy Classification' template (categories set, ratings still 0) was
landing the user on Step 5 instead of Step 3. The fix has 3 surfaces:

(1) frontend DecisionContext.tsx — Step 5 detected by factor.rating>0
    (NOT by category). Step 3 detected by category. Step 2 is bare factors.
(2) backend templates.save_as_template — 'factors' level now stores
    category='' and rating=0 so factor-only templates land on Step 2.
    Higher levels add classification/prioritization cumulatively.
(3) backend crud.clone_decision — same base category='' for factors level.

These backend tests exercise the FULL round-trip: save-as-template →
use-template → GET /api/decisions/{newId} and assert the EXACT data
shape the frontend auto-jump heuristic relies on.
"""

import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://pros-cons-engine.preview.emergentagent.com"
API = f"{BASE_URL}/api"

OWNER_EMAIL = "harden_1777921741@example.com"
OWNER_PASSWORD = "HardenPass2026!"


# ───────────────────────────────────────────────────────────────────
# Fixtures: login as owner, build one fully-completed source decision
# ───────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    token = r.json().get("session_token") or r.json().get("token")
    assert token, f"no token in login response: {r.json()}"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def source_decision_id(session):
    """Create one decision with factors(categories+ratings), options, assessments."""
    title = f"TEST_iter79_src_{uuid.uuid4().hex[:6]}"
    r = session.post(f"{API}/decisions", json={"title": title, "context": "iter79 source"}, timeout=30)
    assert r.status_code == 200, r.text
    did = r.json()["id"]

    factors = [
        {"id": "fct_a", "name": "TEST_FactorA", "category": "primary", "rating": 80, "order": 0},
        {"id": "fct_b", "name": "TEST_FactorB", "category": "secondary", "rating": 40, "order": 1},
    ]
    options = [
        {"id": "opt_x", "name": "TEST_OptionX", "worth_percentage": 0.0,
         "assessments": [
             {"factor_id": "fct_a", "percentage": 70, "assessment_mode": "custom"},
             {"factor_id": "fct_b", "percentage": 50, "assessment_mode": "custom"},
         ]},
        {"id": "opt_y", "name": "TEST_OptionY", "worth_percentage": 0.0,
         "assessments": [
             {"factor_id": "fct_a", "percentage": 60, "assessment_mode": "custom"},
             {"factor_id": "fct_b", "percentage": 80, "assessment_mode": "custom"},
         ]},
    ]
    r = session.put(f"{API}/decisions/{did}", json={"factors": factors, "options": options}, timeout=30)
    assert r.status_code == 200, r.text
    return did


# ───────────────────────────────────────────────────────────────────
# Helper: save template at a given level then use it to create a new
# decision, return that new decision document.
# ───────────────────────────────────────────────────────────────────
def _make_and_use(session, source_id, level):
    save_r = session.post(
        f"{API}/decisions/{source_id}/save-as-template",
        json={"name": f"TEST_iter79_tmpl_{level}", "template_type": level,
              "visibility": "private", "shared_with": []},
        timeout=30,
    )
    assert save_r.status_code == 200, f"save-as-template({level}) failed: {save_r.status_code} {save_r.text}"
    tmpl_id = save_r.json()["id"]

    use_r = session.post(
        f"{API}/templates/{tmpl_id}/use",
        json={"title": f"TEST_iter79_use_{level}"},
        timeout=30,
    )
    assert use_r.status_code == 200, f"use({level}) failed: {use_r.status_code} {use_r.text}"
    new_did = use_r.json()["id"]

    get_r = session.get(f"{API}/decisions/{new_did}", timeout=30)
    assert get_r.status_code == 200, get_r.text
    return tmpl_id, new_did, get_r.json()


# ───────────────────────────────────────────────────────────────────
# Frontend landing-step heuristic (mirror of DecisionContext.tsx auto-jump)
# ───────────────────────────────────────────────────────────────────
def _landing_step(d):
    facs = d.get("factors") or []
    opts = d.get("options") or []
    if d.get("status") == "completed":
        return 10
    if d.get("chosen_option_id"):
        return 8
    if opts and (opts[0].get("assessments") or []):
        return 7
    if opts:
        return 6
    if facs and any((f.get("rating") or 0) > 0 for f in facs):
        return 5
    if facs and any(f.get("category") in ("primary", "secondary") for f in facs):
        return 3
    if facs:
        return 2
    return 1


# ───────────────────────────────────────────────────────────────────
# Tests — five template depths
# ───────────────────────────────────────────────────────────────────
class TestTemplateLandingSteps:
    def test_copy_factors_lands_step_2(self, session, source_decision_id):
        _, new_id, d = _make_and_use(session, source_decision_id, "factors")
        assert len(d["factors"]) == 2
        for f in d["factors"]:
            assert f.get("category", "") == "", f"factors-level must have empty category, got {f.get('category')!r}"
            assert (f.get("rating") or 0) == 0, f"factors-level must have rating=0, got {f.get('rating')}"
        assert d.get("options", []) == []
        assert _landing_step(d) == 2

    def test_copy_classification_lands_step_3(self, session, source_decision_id):
        _, new_id, d = _make_and_use(session, source_decision_id, "classification")
        assert len(d["factors"]) == 2
        assert any(f.get("category") in ("primary", "secondary") for f in d["factors"])
        # CRITICAL: ratings must still be 0 (the original bug)
        for f in d["factors"]:
            assert (f.get("rating") or 0) == 0, (
                f"classification-level must NOT carry ratings (bug-trigger), got {f.get('rating')}"
            )
        assert d.get("options", []) == []
        assert _landing_step(d) == 3, (
            f"Expected Step 3 for Copy-Classification, computed {_landing_step(d)}. "
            f"factors={d.get('factors')}"
        )

    def test_copy_prioritization_lands_step_5(self, session, source_decision_id):
        _, new_id, d = _make_and_use(session, source_decision_id, "prioritization")
        assert len(d["factors"]) == 2
        assert any((f.get("rating") or 0) > 0 for f in d["factors"])
        assert d.get("options", []) == []
        assert _landing_step(d) == 5

    def test_copy_options_lands_step_6(self, session, source_decision_id):
        _, new_id, d = _make_and_use(session, source_decision_id, "options")
        assert len(d["factors"]) == 2
        assert len(d["options"]) == 2
        for o in d["options"]:
            assert (o.get("assessments") or []) == [], "options-level must NOT carry assessments"
        assert _landing_step(d) == 6

    def test_copy_assessment_lands_step_7(self, session, source_decision_id):
        _, new_id, d = _make_and_use(session, source_decision_id, "assessment")
        assert len(d["factors"]) == 2
        assert len(d["options"]) == 2
        assert any((o.get("assessments") or []) for o in d["options"])
        assert _landing_step(d) == 7


# ───────────────────────────────────────────────────────────────────
# Regression — normal-decision flows must still pick the correct step
# ───────────────────────────────────────────────────────────────────
class TestNormalDecisionRegression:
    def test_new_decision_with_only_factors_lands_step_2_or_3(self, session):
        """(a) brand-new decision with only factors listed → early step."""
        r = session.post(f"{API}/decisions", json={"title": f"TEST_iter79_reg_factors_{uuid.uuid4().hex[:6]}", "context": "iter79 regression factors-only"}, timeout=30)
        assert r.status_code == 200
        did = r.json()["id"]
        # Factors with NO category (just names) — simulating Step-2 in-progress
        factors = [
            {"id": "f1", "name": "f1", "category": "", "rating": 0, "order": 0},
            {"id": "f2", "name": "f2", "category": "", "rating": 0, "order": 1},
        ]
        session.put(f"{API}/decisions/{did}", json={"factors": factors}, timeout=30)
        d = session.get(f"{API}/decisions/{did}", timeout=30).json()
        step = _landing_step(d)
        assert step in (2, 3), f"factors-only decision should land on 2 or 3, got {step}"
        assert step != 5 and step != 7

    def test_completed_decision_lands_step_10(self, session, source_decision_id):
        """(b) completed decision still opens at Step 10."""
        # Mark a completed copy
        r = session.post(f"{API}/decisions/{source_decision_id}/clone",
                         json={"title": f"TEST_iter79_completed_{uuid.uuid4().hex[:6]}", "clone_level": "assessment"},
                         timeout=30)
        assert r.status_code == 200
        cid = r.json()["id"]
        # Get current factors/options so we can pass them through PUT (model
        # ignores None fields but status alone is allowed)
        d = session.get(f"{API}/decisions/{cid}", timeout=30).json()
        chosen = d["options"][0]["id"] if d.get("options") else None
        session.put(f"{API}/decisions/{cid}", json={"status": "completed", "chosen_option_id": chosen}, timeout=30)
        d2 = session.get(f"{API}/decisions/{cid}", timeout=30).json()
        assert _landing_step(d2) == 10

    def test_options_plus_assessments_lands_step_7(self, session, source_decision_id):
        """(c) decision with options+assessments → Step 7."""
        d = session.get(f"{API}/decisions/{source_decision_id}", timeout=30).json()
        assert _landing_step(d) == 7

    def test_chosen_option_without_completed_lands_step_8(self, session, source_decision_id):
        """(d) decision with chosen_option_id (and not status=completed) → Step 8."""
        r = session.post(f"{API}/decisions/{source_decision_id}/clone",
                         json={"title": f"TEST_iter79_chosen_{uuid.uuid4().hex[:6]}", "clone_level": "assessment"},
                         timeout=30)
        assert r.status_code == 200
        cid = r.json()["id"]
        d = session.get(f"{API}/decisions/{cid}", timeout=30).json()
        chosen = d["options"][0]["id"] if d.get("options") else None
        session.put(f"{API}/decisions/{cid}", json={"chosen_option_id": chosen}, timeout=30)
        d2 = session.get(f"{API}/decisions/{cid}", timeout=30).json()
        assert d2.get("status") != "completed", "regression precondition broken: status=completed"
        assert _landing_step(d2) == 8


# ───────────────────────────────────────────────────────────────────
# crud.clone — same 5-level mapping (mirror check)
# ───────────────────────────────────────────────────────────────────
class TestCloneLandingSteps:
    @pytest.mark.parametrize("level,expected_step", [
        ("factors", 2),
        ("classification", 3),
        ("prioritization", 5),
        ("options", 6),
        ("assessment", 7),
    ])
    def test_clone_lands_correct_step(self, session, source_decision_id, level, expected_step):
        r = session.post(
            f"{API}/decisions/{source_decision_id}/clone",
            json={"title": f"TEST_iter79_clone_{level}_{uuid.uuid4().hex[:4]}", "clone_level": level},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        new_id = r.json()["id"]
        d = session.get(f"{API}/decisions/{new_id}", timeout=30).json()
        assert _landing_step(d) == expected_step, (
            f"clone({level}) landed on {_landing_step(d)} expected {expected_step}. "
            f"factors={d.get('factors')} options={d.get('options')}"
        )
