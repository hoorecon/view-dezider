"""iter94 — Verify the hierarchical URL import endpoint for MyDezider.

Confirms /api/url-analyze returns mode='hierarchical' for a multi-category compare page
with the expected category/sub-factor/option counts.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://pros-cons-engine.preview.emergentagent.com").rstrip("/")

VEALES = {"email": "veales.vedic.decisions@gmail.com", "password": "Jelcos@Admin2026"}
GSMA_URL = "https://www.gsmarena.com/compare.php3?&idPhone2=14592&idPhone3=14379&idPhone1=9286"
PRR_ID = "a856aca3-548f-4bb5-bf5f-c608ae303474"


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=VEALES, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


@pytest.fixture
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


def test_prebuilt_decision_has_15_parents_55_subs_3_options(headers):
    """Pre-built decision exposed at /prr/<id> must already be hierarchical."""
    r = requests.get(f"{BASE_URL}/api/decisions/{PRR_ID}", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    factors = d.get("factors", [])
    options = d.get("options", [])
    parents = [f for f in factors if not f.get("parent_id")]
    subs = [f for f in factors if f.get("parent_id")]

    assert len(parents) == 15, f"Expected 15 parent factors, got {len(parents)}"
    assert 50 <= len(subs) <= 60, f"Expected ~55 sub-factors, got {len(subs)}"
    assert len(options) == 3, f"Expected 3 options, got {len(options)}"

    parent_names = {p["name"] for p in parents}
    expected_categories = {
        "Network", "Launch", "Body", "Display", "Platform", "Memory",
        "Main Camera", "Selfie Camera", "Sound", "Comms", "Features",
        "Battery", "Misc", "Our Tests", "EU LABEL",
    }
    assert parent_names == expected_categories, f"Mismatch: {parent_names ^ expected_categories}"

    body_parent = next(p for p in parents if p["name"] == "Body")
    body_subs = {f["name"] for f in subs if f.get("parent_id") == body_parent["id"]}
    assert body_subs == {"Dimensions", "Weight", "Build", "SIM"}, body_subs

    option_names = {o["name"] for o in options}
    assert option_names == {"Oppo F9 (F9 Pro)", "Oppo Find X9s Pro", "Samsung Galaxy A57"}, option_names


def test_url_analyze_hierarchical_mode(headers):
    """POST /api/url-analyze with GSMArena URL must return mode='hierarchical' with proper counts."""
    payload = {
        "url": GSMA_URL,
        "target": "mydezider",
        "eligibility_type": "free_public",
        "accepted": True,
    }
    r = requests.post(f"{BASE_URL}/api/url-analyze", json=payload, headers=headers, timeout=90)
    # Some live sites might block crawler; report even if non-200
    assert r.status_code in (200, 422, 502, 503), f"Unexpected status: {r.status_code} {r.text[:300]}"
    if r.status_code != 200:
        pytest.skip(f"URL crawl returned {r.status_code} (live site may be blocking) — body: {r.text[:200]}")

    body = r.json()
    assert body.get("mode") == "hierarchical", f"Expected hierarchical mode, got {body.get('mode')}: {body}"
    assert body.get("category_count") == 15, body
    assert body.get("item_count") == 3, body
    # factor_count ~55 (allow slack)
    fc = body.get("factor_count", 0)
    assert 45 <= fc <= 70, f"factor_count out of range: {fc}"
