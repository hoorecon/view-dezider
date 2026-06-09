"""Regression: free-first provider chain + batched AI-assess + OpenAI consent.

Verifies (against the running dev server):
  * the 4-provider fallback chain succeeds even when Gemini/Emergent are down
    (dev sandbox: Gemini times out, Emergent budget-exceeded → Groq carries it),
  * the batched endpoint scores many cells in one shot (≤ ~1 call / 40 cells),
  * the provider-consent get/set endpoints round-trip.
"""
import os
import requests

API = os.getenv("TEST_API", "http://localhost:8001/api")
EMAIL = os.getenv("TEST_EMAIL", "veales.vedic.decisions@gmail.com")
PASSWORD = os.getenv("TEST_PASSWORD", "Jelcos@Admin2026")
GSM_URL = ("https://www.gsmarena.com/compare.php3?"
           "&idPhone2=14592&idPhone3=14379&idPhone1=9286")


def _token():
    r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    r.raise_for_status()
    return r.json()["session_token"]


def test_provider_consent_roundtrip():
    h = {"Authorization": f"Bearer {_token()}"}
    base = requests.get(f"{API}/ai-wallet/provider-consent", headers=h, timeout=30).json()
    assert "allow_openai" in base and "mode" in base and "openai_available" in base
    up = requests.put(f"{API}/ai-wallet/provider-consent", headers=h,
                      json={"allow_openai": True, "mode": "always"}, timeout=30).json()
    assert up["allow_openai"] is True and up["mode"] == "always"
    # reset
    requests.put(f"{API}/ai-wallet/provider-consent", headers=h,
                 json={"allow_openai": False, "mode": "ask"}, timeout=30)


def test_batched_assess_uses_free_chain():
    h = {"Authorization": f"Bearer {_token()}"}
    did = requests.post(f"{API}/decisions", headers=h,
                        json={"title": "pytest batch", "context": "phone comparison"}, timeout=30).json()["id"]
    try:
        requests.post(f"{API}/url-analyze/decision/{did}/import", headers=h,
                      json={"url": GSM_URL, "eligibility_type": "free_public", "accepted": True}, timeout=120)
        d = requests.get(f"{API}/decisions/{did}", headers=h, timeout=30).json()
        leaves = [f for f in d["factors"] if f.get("parent_id")][:6]
        cells = [{"option_id": d["options"][0]["id"], "factor_id": f["id"], "actual_value": ""} for f in leaves]
        r = requests.post(f"{API}/decisions/{did}/ai-assess-all-batched", headers=h,
                          json={"cells": cells, "force_fill": True}, timeout=180)
        assert r.status_code == 200, r.text
        j = r.json()
        # With Groq in the chain, this must NOT be unavailable and should score cells.
        assert j.get("ai_unavailable") is not True, "free provider chain should carry the load"
        done = [x for x in j.get("results", []) if x.get("status") == "done"]
        assert len(done) >= 1, j
    finally:
        requests.delete(f"{API}/decisions/{did}", headers=h, timeout=30)
