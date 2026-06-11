"""Regression tests — Revenue Reconciliation (admin recon) endpoints.

Run: cd /app/backend && python -m pytest tests/test_admin_recon.py -q
"""
import os

import httpx
import pytest

BASE = os.environ.get("RECON_TEST_BASE", "http://localhost:8001")
SUPER_ADMIN = {"email": "veales.vedic.decisions@gmail.com", "password": "Jelcos@Admin2026"}
REGULAR = {"email": "harden_1777921741@example.com", "password": "HardenPass2026!"}


def _login(creds) -> str:
    r = httpx.post(f"{BASE}/api/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    return d.get("session_token") or d.get("token")


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login(SUPER_ADMIN)}"}


@pytest.fixture(scope="module")
def user_headers():
    return {"Authorization": f"Bearer {_login(REGULAR)}"}


def test_summary_shape(admin_headers):
    r = httpx.get(f"{BASE}/api/admin/recon/summary", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    d = r.json()
    for key in ("sales", "razorpay", "consumption", "gcp", "verdict", "fx_usd_inr"):
        assert key in d
    assert "net_treasury_inr" in d["razorpay"]
    assert "est_liability_inr" in d["consumption"]
    assert "at_risk" in d["verdict"]


def test_transactions_tally(admin_headers):
    r = httpx.get(f"{BASE}/api/admin/recon/transactions?limit=5", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert {"items", "total"} <= set(d.keys())
    for row in d["items"]:
        # per-txn zero-loss identity: buffer = net_treasury − earmarked cost
        assert abs(row["buffer_inr"] - round(row["net_treasury_inr"] - row["earmarked_llm_cost_inr"], 2)) < 0.02
        assert "at_loss" in row["flags"]


def test_daily_tally(admin_headers):
    r = httpx.get(f"{BASE}/api/admin/recon/daily?days=7", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert "items" in d and "fx_usd_inr" in d
    for row in d["items"]:
        assert row["tokens"] >= 0 and row["est_cost_inr"] >= 0


def test_csv_export(admin_headers):
    r = httpx.get(f"{BASE}/api/admin/recon/transactions.csv", headers=admin_headers, timeout=30)
    assert r.status_code == 200
    assert r.text.startswith("created_at,order_id,payment_id")


def test_gcp_config_roundtrip_and_validation(admin_headers):
    r = httpx.get(f"{BASE}/api/admin/recon/gcp-config", headers=admin_headers, timeout=20)
    assert r.status_code == 200
    assert "sa_json_b64" not in (r.json().get("gcp") or {})  # never leaked
    # invalid SA json rejected
    r = httpx.put(f"{BASE}/api/admin/recon/gcp-config", headers=admin_headers,
                  json={"sa_json": "not-json"}, timeout=20)
    assert r.status_code == 400
    # plain field update accepted
    r = httpx.put(f"{BASE}/api/admin/recon/gcp-config", headers=admin_headers,
                  json={"dataset": "billing_export"}, timeout=20)
    assert r.status_code == 200
    assert r.json()["gcp"]["dataset"] == "billing_export"


def test_access_control(user_headers):
    for path in ("summary", "transactions", "daily", "gcp-config"):
        r = httpx.get(f"{BASE}/api/admin/recon/{path}", headers=user_headers, timeout=20)
        assert r.status_code == 403, f"{path} should be super-admin only"
    r = httpx.get(f"{BASE}/api/admin/recon/summary", timeout=20)
    assert r.status_code in (401, 403)
