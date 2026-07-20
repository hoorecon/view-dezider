"""
ITER 186 — Backend smoke for AI limits pop-up backend caps.

Only ONE minimal AI call per endpoint (max_per_rca=1 / max_risks_per_solution=1)
to conserve AI credits. A 402 wallet-empty response is considered acceptable
(cannot verify caps without spending credits — flag it in report).

Prereq: super@test.com session; SF entry 11cf0bc0-... already has data (Q2/Q3).
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/") \
    or os.environ.get("EXPO_BACKEND_URL", "").rstrip("/")
SF_ID = "11cf0bc0-8086-40c3-a679-6da1ea10fdab"


@pytest.fixture(scope="module")
def super_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "super@test.com", "password": "SuperPass2026!"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def sf_entry(super_token):
    r = requests.get(
        f"{BASE_URL}/api/solution-finders/{SF_ID}",
        headers={"Authorization": f"Bearer {super_token}"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    return r.json()


class TestAILimits:
    """Backend caps for AI suggestions."""

    def test_wallet_balance_visible(self, super_token):
        r = requests.get(
            f"{BASE_URL}/api/ai-wallet",
            headers={"Authorization": f"Bearer {super_token}"},
            timeout=15,
        )
        assert r.status_code == 200
        bal = r.json().get("balance")
        assert bal is not None
        print(f"WALLET BALANCE = {bal}")

    def test_estimates_endpoint(self, super_token):
        r = requests.get(
            f"{BASE_URL}/api/ai-wallet/estimates",
            headers={"Authorization": f"Bearer {super_token}"},
            timeout=15,
        )
        assert r.status_code == 200
        feats = r.json().get("features", {})
        assert "solution_finder_solutions" in feats
        assert "solution_finder_risks" in feats

    def test_suggest_solutions_max_per_rca_1(self, super_token, sf_entry):
        """Pass max_per_rca=1: at most 1 suggestion per rca. 402 acceptable."""
        rcas = sf_entry.get("root_causes") or []
        if not rcas:
            pytest.skip("SF entry has no root causes for Q3 smoke")
        # Use just first 2 root causes to minimize LLM cost
        payload = {
            "area_of_life": sf_entry.get("area_of_life") or "general",
            "smart_goal": sf_entry.get("smart_goal") or "",
            "max_per_rca": 1,
            "root_causes": [
                {
                    "rca_id": r["id"],
                    "text": r.get("text") or "",
                    "existing": [],
                }
                for r in rcas[:2]
            ],
        }
        r = requests.post(
            f"{BASE_URL}/api/solution-finders/ai/suggest-solutions",
            json=payload,
            headers={"Authorization": f"Bearer {super_token}"},
            timeout=120,
        )
        if r.status_code == 402:
            print("402 — wallet empty; cap enforcement code-verified only")
            pytest.skip("Wallet empty (402) — cap verified via code review only")
        assert r.status_code == 200, r.text
        suggestions = r.json().get("suggestions", {})
        for rca_id, items in suggestions.items():
            assert isinstance(items, list)
            assert len(items) <= 1, f"cap violation for {rca_id}: {items}"
        print(f"OK solutions capped 1/rca — got {sum(len(v) for v in suggestions.values())} across {len(suggestions)} rcas")

    def test_suggest_risks_max_1_per_solution(self, super_token, sf_entry):
        """Pass max_risks/mits/cons=1: at most 1 each. 402 acceptable."""
        sols = sf_entry.get("solutions") or []
        if not sols:
            pytest.skip("SF entry has no solutions for Q4 smoke")
        payload = {
            "area_of_life": sf_entry.get("area_of_life") or "general",
            "smart_goal": sf_entry.get("smart_goal") or "",
            "max_risks_per_solution": 1,
            "max_mitigations_per_risk": 1,
            "max_contingencies_per_risk": 1,
            "solutions": [
                {
                    "sol_id": s["id"],
                    "text": s.get("text") or "",
                    "existing_risks": [],
                }
                for s in sols[:2]
            ],
        }
        r = requests.post(
            f"{BASE_URL}/api/solution-finders/ai/suggest-risks",
            json=payload,
            headers={"Authorization": f"Bearer {super_token}"},
            timeout=120,
        )
        if r.status_code == 402:
            print("402 — wallet empty; cap enforcement code-verified only")
            pytest.skip("Wallet empty (402) — cap verified via code review only")
        assert r.status_code == 200, r.text
        suggestions = r.json().get("suggestions", {})
        for sol_id, risks in suggestions.items():
            assert isinstance(risks, list)
            assert len(risks) <= 1, f"risk cap violation for {sol_id}"
            for risk in risks:
                assert len(risk.get("mitigations", [])) <= 1
                assert len(risk.get("contingencies", [])) <= 1
        print(f"OK risks capped 1/sol — {sum(len(v) for v in suggestions.values())} risks across {len(suggestions)} sols")

    def test_lim_clamp_via_11(self, super_token, sf_entry):
        """max_per_rca=11 should clamp to 10 server-side (validate no 500)."""
        rcas = sf_entry.get("root_causes") or []
        if not rcas:
            pytest.skip("No root causes")
        payload = {
            "area_of_life": "general",
            "smart_goal": "",
            "max_per_rca": 11,  # should clamp to 10
            "root_causes": [{"rca_id": rcas[0]["id"], "text": rcas[0].get("text") or "x"}],
        }
        # Don't actually spend credits — just validate that the endpoint accepts it and either 200s or 402s
        r = requests.post(
            f"{BASE_URL}/api/solution-finders/ai/suggest-solutions",
            json=payload,
            headers={"Authorization": f"Bearer {super_token}"},
            timeout=120,
        )
        assert r.status_code in (200, 402), f"Unexpected status {r.status_code}: {r.text}"
        if r.status_code == 200:
            sugg = r.json().get("suggestions", {})
            for k, items in sugg.items():
                assert len(items) <= 10
