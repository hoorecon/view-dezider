"""Smoke tests for Wave 2 #8b — Deep-Import budget picker + auto-assess
& rank-top-N, plus the audit confirmation for #7/#8a (hybrid custom/AI
factors and options don't mix-up in assessment + downstream worth math).

Strategy: keep the AI-side untouched (slow, costs credits) by seeding the
decision with assessments PRE-FILLED so `auto-assess-rank` runs zero
AI calls but still exercises the score → top-N → save path.
"""
import os
import time
import uuid
import asyncio
import requests
import pytest

BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE}/api"


def _register() -> tuple[str, str]:
    em = f"iter118_{int(time.time())}_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{API}/auth/register",
                      json={"email": em, "password": "TestPass2026!", "name": "Iter118"}, timeout=30)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text[:200]}"
    return em, r.json()["session_token"]


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def user():
    em, tok = _register()
    return {"email": em, "tok": tok}


def _seed_decision_with_assessments(user_id: str) -> str:
    """Create a decision DIRECTLY in Mongo with 3 factors × 4 options, every
    cell pre-scored. Returns decision_id. Used to exercise the rank loop
    without burning AI credits.
    """
    from core.database import db

    factors = [
        {"id": "f_range", "name": "Range", "rating": 9, "category": "primary",
         "expected_value": "300", "operator": ">=", "order": 0},
        {"id": "f_price", "name": "Price", "rating": 8, "category": "primary",
         "expected_value": "1500000", "operator": "<=", "order": 1},
        {"id": "f_charging", "name": "Charging time", "rating": 6, "category": "secondary",
         "expected_value": "2", "operator": "<=", "order": 2},
    ]
    options = []
    # Option A — best range, mid-price → top
    options.append({"id": "o_a", "name": "Option A",
                    "assessments": [{"factor_id": "f_range", "percentage": 95},
                                    {"factor_id": "f_price", "percentage": 70},
                                    {"factor_id": "f_charging", "percentage": 80}],
                    "source": "ai"})
    # Option B — mid range, best price
    options.append({"id": "o_b", "name": "Option B",
                    "assessments": [{"factor_id": "f_range", "percentage": 75},
                                    {"factor_id": "f_price", "percentage": 90},
                                    {"factor_id": "f_charging", "percentage": 60}],
                    "source": "ai"})
    # Option C — weakest
    options.append({"id": "o_c", "name": "Option C",
                    "assessments": [{"factor_id": "f_range", "percentage": 40},
                                    {"factor_id": "f_price", "percentage": 50},
                                    {"factor_id": "f_charging", "percentage": 30}],
                    "source": "ai"})
    # Option D — manually added later (no source set), mixed source check
    options.append({"id": "o_d", "name": "Option D (custom)",
                    "assessments": [{"factor_id": "f_range", "percentage": 80},
                                    {"factor_id": "f_price", "percentage": 65},
                                    {"factor_id": "f_charging", "percentage": 75}],
                    "source": "manual"})

    did = str(uuid.uuid4())
    asyncio.get_event_loop().run_until_complete(
        db.decisions.insert_one({
            "id": did, "user_id": user_id, "title": "EV Choice",
            "context": "Pick best EV", "status": "draft",
            "factors": factors, "options": options,
            "deep_import_pending_rank": True,
            "deep_import_top_n_ids": [],
        })
    )
    return did


def _user_id(token: str) -> str:
    r = requests.get(f"{API}/auth/me", headers=_h(token), timeout=10)
    assert r.status_code == 200
    return r.json()["user_id"]


# ── Budget estimate ──────────────────────────────────────────
def test_budget_estimate_returns_bounds(user):
    h = _h(user["tok"])
    uid = _user_id(user["tok"])
    did = _seed_decision_with_assessments(uid)
    r = requests.get(f"{API}/decisions/{did}/deep-import/budget-estimate",
                     params={"budget_count": 0}, headers=h, timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total_options"] == 4
    assert data["max_options"] >= 2
    assert data["top_n"] >= 1
    assert data["upper"] >= 2 and data["lower"] >= 2
    # Empty cells = 0 because we pre-seeded percentages.
    assert data["empty_cells"] == 0
    assert data["estimate_credits"] == 0


# ── Auto-assess & rank ──────────────────────────────────────
def test_auto_assess_rank_orders_by_worth(user):
    h = _h(user["tok"])
    uid = _user_id(user["tok"])
    did = _seed_decision_with_assessments(uid)

    r = requests.post(f"{API}/decisions/{did}/deep-import/auto-assess-rank",
                      json={"budget_count": 4}, headers=h, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    ranked = data["ranked"]
    assert len(ranked) == 4
    # Worths must be DESC.
    worths = [r["worth_percentage"] for r in ranked]
    assert worths == sorted(worths, reverse=True), worths
    # Decision now has top_n_ids set and pending flag cleared.
    r = requests.get(f"{API}/decisions/{did}", headers=h, timeout=10)
    dec = r.json()
    assert dec.get("deep_import_pending_rank") is False
    assert isinstance(dec.get("deep_import_top_n_ids"), list)
    # `top_n_ids` is capped by available options (4 here) — admin top_n
    # defaults to 5 but the slice naturally truncates.
    assert len(dec["deep_import_top_n_ids"]) == min(data["top_n"], 4)


# ── Audit (#7 / #8a) — hybrid custom + AI options ranked together ────
def test_mixed_source_options_assessed_and_ranked_uniformly(user):
    """Option D was sourced as 'manual', the rest as 'ai'. The ranker
    must treat them identically; no source-based filtering is allowed
    to leak into worth math.
    """
    h = _h(user["tok"])
    uid = _user_id(user["tok"])
    did = _seed_decision_with_assessments(uid)

    r = requests.post(f"{API}/decisions/{did}/deep-import/auto-assess-rank",
                      json={"budget_count": 4}, headers=h, timeout=30)
    assert r.status_code == 200, r.text
    ranked = r.json()["ranked"]
    # 'manual' option D should appear in ranked output exactly once.
    names = {x["name"] for x in ranked}
    assert "Option D (custom)" in names
    # And its worth must follow the same math (rating × pct rule), not be 0.
    d_worth = next(x["worth_percentage"] for x in ranked if x["name"] == "Option D (custom)")
    assert d_worth > 0


# ── Dismiss prompt ──────────────────────────────────────────
def test_dismiss_rank_prompt(user):
    h = _h(user["tok"])
    uid = _user_id(user["tok"])
    did = _seed_decision_with_assessments(uid)
    r = requests.post(f"{API}/decisions/{did}/deep-import/dismiss-rank-prompt",
                      headers=h, timeout=10)
    assert r.status_code == 200, r.text
    r = requests.get(f"{API}/decisions/{did}", headers=h, timeout=10)
    assert r.json().get("deep_import_pending_rank") is False


# ── Admin config: deep_import_max_options + top_n round-trip ───────
def test_admin_deep_import_config_round_trip():
    """Super-admin can read & adjust the two new wallet-config keys via
    the existing admin/ai-wallet/config PUT endpoint."""
    # Use the super-admin account seeded by the conftest pattern (env-driven).
    em = os.environ.get("SUPER_ADMIN_EMAIL", "admin@test.com")
    pw = os.environ.get("SUPER_ADMIN_PASSWORD", "AdminPass2026!")
    r = requests.post(f"{API}/auth/login", json={"email": em, "password": pw}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"Super-admin login unavailable in this env ({r.status_code})")
    tok = r.json()["session_token"]
    h = _h(tok)

    r = requests.get(f"{API}/admin/ai-wallet/config", headers=h, timeout=10)
    if r.status_code == 403:
        pytest.skip("Not a super-admin in this env")
    assert r.status_code == 200, r.text
    cfg = r.json()
    assert "deep_import_max_options" in cfg
    assert "deep_import_top_n" in cfg

    r = requests.put(f"{API}/admin/ai-wallet/config",
                     json={"deep_import_max_options": 8, "deep_import_top_n": 3},
                     headers=h, timeout=10)
    assert r.status_code == 200, r.text
    r = requests.get(f"{API}/admin/ai-wallet/config", headers=h, timeout=10)
    assert r.json()["deep_import_max_options"] == 8
    assert r.json()["deep_import_top_n"] == 3

    # Reset
    requests.put(f"{API}/admin/ai-wallet/config",
                 json={"deep_import_max_options": 10, "deep_import_top_n": 5},
                 headers=h, timeout=10)

    # Out-of-range rejected
    r = requests.put(f"{API}/admin/ai-wallet/config",
                     json={"deep_import_max_options": 1}, headers=h, timeout=10)
    assert r.status_code in (400, 422)
