"""
Iteration 87 — P3 Screener backend re-confirm.

Tests the four endpoints documented in the review request:
  ingest (csv), quote, run, export, plus the URL legal-gate (403).
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://modal-responsive-fix.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
PARTNER = "pmsbazaar-demo"
EMAIL = "analyst@pmsbazaar-demo.com"
PASSWORD = "PmsAnalyst2026!"


@pytest.fixture(scope="module")
def auth_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/org-auth/login", json={
        "org_slug": PARTNER, "email": EMAIL, "password": PASSWORD,
    }, timeout=30)
    assert r.status_code == 200, f"org-auth/login failed {r.status_code}: {r.text}"
    d = r.json()
    token = d.get("session_token")
    if not token:
        pytest.skip(f"org-auth requires OTP: {d}")
    s.headers["Authorization"] = f"Bearer {token}"
    return s


def test_ingest_csv(auth_session):
    payload = {
        "partner": PARTNER, "mode": "csv",
        "csv_text": "name,A,B\nX,10,1\nY,5,2\n",
    }
    r = auth_session.post(f"{API}/embed/screener/ingest", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["count"] == 2
    assert sorted(d["attribute_keys"]) == ["A", "B", "name"] or set(d["attribute_keys"]) >= {"A", "B"}
    assert "ingest_id" in d and len(d["ingest_id"]) > 0
    # stash for later test
    pytest.ingest_id = d["ingest_id"]


def test_quote(auth_session):
    r = auth_session.post(f"{API}/embed/screener/quote", json={
        "partner": PARTNER, "candidate_count": 2, "finalists": 2, "factor_count": 2,
    }, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["cost_credits"] > 0
    assert "wallet_balance" in d


def test_run_ranks_x_first(auth_session):
    ingest_id = getattr(pytest, "ingest_id", None)
    assert ingest_id, "ingest_id from test_ingest_csv missing"
    r = auth_session.post(f"{API}/embed/screener/run", json={
        "partner": PARTNER, "ingest_id": ingest_id,
        "factors": [{"name": "A", "attribute_key": "A", "weight": 100,
                     "direction": "higher", "data_type": "numeric"}],
        "finalists": 2,
    }, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["finalists"]) == 2
    assert d["finalists"][0]["name"] == "X", f"Expected X first, got {d['finalists']}"
    assert d["finalists"][0]["rank"] == 1
    assert d["cost_credits"] > 0
    assert "wallet_balance" in d
    pytest.run_id = d["run_id"]


def test_export_csv(auth_session):
    run_id = getattr(pytest, "run_id", None)
    assert run_id, "run_id from test_run missing"
    r = auth_session.get(f"{API}/embed/screener/run/{run_id}/export.csv", timeout=30)
    assert r.status_code == 200, r.text
    assert "text/csv" in r.headers.get("content-type", "")
    assert "Rank" in r.text


def test_url_mode_legal_gate(auth_session):
    r = auth_session.post(f"{API}/embed/screener/ingest", json={
        "partner": PARTNER, "mode": "url", "url": "https://example.com/list",
    }, timeout=30)
    assert r.status_code == 403, f"Expected 403 legal-gate, got {r.status_code}: {r.text}"


# CSV scenario matching the UI test (Money Grow / Hem / Green Portfolio)
def test_full_ui_scenario(auth_session):
    csv_text = ("name,1Y Return,AUM\n"
                "Money Grow,44.39%,121.47\n"
                "Hem Securities,36.77%,95.01\n"
                "Green Portfolio,31.92%,212.02\n")
    r = auth_session.post(f"{API}/embed/screener/ingest", json={
        "partner": PARTNER, "mode": "csv", "csv_text": csv_text,
    }, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["count"] == 3
    ingest_id = d["ingest_id"]

    r2 = auth_session.post(f"{API}/embed/screener/run", json={
        "partner": PARTNER, "ingest_id": ingest_id,
        "factors": [
            {"name": "1Y Return", "attribute_key": "1Y Return", "weight": 70,
             "direction": "higher", "data_type": "numeric"},
            {"name": "AUM", "attribute_key": "AUM", "weight": 30,
             "direction": "higher", "data_type": "numeric"},
        ],
        "finalists": 2,
    }, timeout=60)
    assert r2.status_code == 200, r2.text
    d2 = r2.json()
    assert d2["finalists"][0]["name"] == "Money Grow", d2["finalists"]
    # ~76.8 score
    assert 70 <= d2["finalists"][0]["score"] <= 85
