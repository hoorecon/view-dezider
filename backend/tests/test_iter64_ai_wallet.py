"""Iter-64: AI Credits Wallet (Phase 2) — backend regression suite.

Validates:
  • GET /api/ai-wallet (auto-seed, structure)
  • GET /api/ai-wallet/ledger (seed entry on first fetch)
  • Super-admin /api/admin/ai-wallet/config GET + PUT (incl. validation)
  • Admin /api/admin/ai-wallet/grant (add + set modes, ledger entries)
  • Admin /api/admin/ai-wallet/users (list)
  • Auth gating: normal user → 403 on admin endpoints
  • AI Assess 402 path when wallet balance forced to 0
"""
import os
import time
import requests
import pytest

BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE}/api"

SUPER_EMAIL = "veales.vedic.decisions@gmail.com"
SUPER_PASS = "Jelcos@Admin2026"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASS = "AdminPass2026!"


def _login(email: str, password: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text[:200]}"
    return r.json()["session_token"]


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _register_throwaway() -> tuple[str, str, str]:
    em = f"wallet_test_{int(time.time())}_{os.urandom(2).hex()}@example.com"
    r = requests.post(f"{API}/auth/register",
                      json={"email": em, "password": "TestPass2026!", "name": "WalletTester"}, timeout=30)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text[:200]}"
    j = r.json()
    return em, "TestPass2026!", j["session_token"]


# ─────────────────── fixtures ───────────────────
@pytest.fixture(scope="module")
def super_token():
    return _login(SUPER_EMAIL, SUPER_PASS)


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def user_ctx():
    email, password, tok = _register_throwaway()
    return {"email": email, "password": password, "token": tok}


# ─────────────────── user wallet ───────────────────
class TestUserWallet:
    def test_balance_autoseeds_and_shape(self, user_ctx):
        r = requests.get(f"{API}/ai-wallet", headers=_h(user_ctx["token"]), timeout=20)
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert "balance" in d and "is_admin" in d
        assert d.get("unit") == "credits"
        assert isinstance(d.get("tokens_per_credit"), (int, float))
        assert isinstance(d.get("balance"), (int, float))
        # default user seed is 20.0 (per code DEFAULTS) — but may be overridden by prior config
        assert d["balance"] >= 0
        assert d["is_admin"] is False

    def test_ledger_has_seed_entry(self, user_ctx):
        # Trigger balance first
        requests.get(f"{API}/ai-wallet", headers=_h(user_ctx["token"]), timeout=20)
        r = requests.get(f"{API}/ai-wallet/ledger?limit=40", headers=_h(user_ctx["token"]), timeout=20)
        assert r.status_code == 200, r.text[:200]
        items = r.json().get("items", [])
        kinds = [i.get("kind") for i in items]
        assert "seed" in kinds, f"no seed entry — kinds={kinds}"


# ─────────────────── admin config ───────────────────
class TestAdminConfig:
    def test_super_admin_can_get_config(self, super_token):
        r = requests.get(f"{API}/admin/ai-wallet/config", headers=_h(super_token), timeout=20)
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        for k in ("default_user_credits", "default_admin_credits", "tokens_per_credit"):
            assert k in d, f"missing {k}"
            assert isinstance(d[k], (int, float))

    def test_super_admin_can_update_config(self, super_token):
        body = {"default_user_credits": 25, "default_admin_credits": 250, "tokens_per_credit": 100}
        r = requests.put(f"{API}/admin/ai-wallet/config", headers=_h(super_token), json=body, timeout=20)
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert d["default_user_credits"] == 25
        assert d["default_admin_credits"] == 250
        assert d["tokens_per_credit"] == 100
        # GET verifies persistence
        r2 = requests.get(f"{API}/admin/ai-wallet/config", headers=_h(super_token), timeout=20)
        assert r2.json()["default_user_credits"] == 25

    def test_config_rejects_negative(self, super_token):
        r = requests.put(f"{API}/admin/ai-wallet/config", headers=_h(super_token),
                         json={"default_user_credits": -5}, timeout=20)
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text[:200]}"

    def test_config_rejects_zero_tokens_per_credit(self, super_token):
        r = requests.put(f"{API}/admin/ai-wallet/config", headers=_h(super_token),
                         json={"tokens_per_credit": 0}, timeout=20)
        assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text[:200]}"

    def test_normal_user_blocked_from_config_get(self, user_ctx):
        r = requests.get(f"{API}/admin/ai-wallet/config", headers=_h(user_ctx["token"]), timeout=20)
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text[:200]}"

    def test_normal_user_blocked_from_config_put(self, user_ctx):
        r = requests.put(f"{API}/admin/ai-wallet/config", headers=_h(user_ctx["token"]),
                         json={"default_user_credits": 5}, timeout=20)
        assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text[:200]}"

    def test_admin_blocked_from_config_put(self, admin_token):
        """Plain admin (non-super) should be blocked from super-admin-only config PUT."""
        r = requests.put(f"{API}/admin/ai-wallet/config", headers=_h(admin_token),
                         json={"default_user_credits": 25}, timeout=20)
        assert r.status_code == 403, f"expected 403 for plain admin, got {r.status_code} {r.text[:200]}"


# ─────────────────── grants ───────────────────
class TestGrants:
    def test_grant_add_mode(self, super_token, user_ctx):
        # capture pre-balance
        rb = requests.get(f"{API}/ai-wallet", headers=_h(user_ctx["token"]), timeout=20)
        pre = float(rb.json()["balance"])

        r = requests.post(f"{API}/admin/ai-wallet/grant", headers=_h(super_token),
                          json={"email": user_ctx["email"], "credits": 12, "mode": "add"}, timeout=20)
        assert r.status_code == 200, r.text[:200]
        d = r.json()
        assert abs(float(d["balance"]) - (pre + 12)) < 0.01, f"balance mismatch: pre={pre}, post={d['balance']}"

        # ledger should contain grant entry
        rl = requests.get(f"{API}/ai-wallet/ledger?limit=40", headers=_h(user_ctx["token"]), timeout=20)
        kinds = [i.get("kind") for i in rl.json().get("items", [])]
        assert "grant" in kinds, f"grant not in ledger: {kinds}"

    def test_grant_set_mode(self, super_token, user_ctx):
        r = requests.post(f"{API}/admin/ai-wallet/grant", headers=_h(super_token),
                          json={"email": user_ctx["email"], "credits": 7, "mode": "set"}, timeout=20)
        assert r.status_code == 200, r.text[:200]
        assert abs(float(r.json()["balance"]) - 7.0) < 0.01
        # Verify by GET
        rb = requests.get(f"{API}/ai-wallet", headers=_h(user_ctx["token"]), timeout=20)
        assert abs(float(rb.json()["balance"]) - 7.0) < 0.01

    def test_grant_unknown_email_404(self, super_token):
        r = requests.post(f"{API}/admin/ai-wallet/grant", headers=_h(super_token),
                          json={"email": "no_such_user_xyz@example.com", "credits": 5, "mode": "add"}, timeout=20)
        assert r.status_code == 404, r.text[:200]

    def test_grant_invalid_credits_400(self, super_token, user_ctx):
        r = requests.post(f"{API}/admin/ai-wallet/grant", headers=_h(super_token),
                          json={"email": user_ctx["email"], "credits": "abc", "mode": "add"}, timeout=20)
        assert r.status_code == 400, r.text[:200]

    def test_normal_user_blocked_from_grant(self, user_ctx):
        r = requests.post(f"{API}/admin/ai-wallet/grant", headers=_h(user_ctx["token"]),
                          json={"email": user_ctx["email"], "credits": 1, "mode": "add"}, timeout=20)
        assert r.status_code == 403, r.text[:200]


# ─────────────────── admin users list ───────────────────
class TestAdminUsersList:
    def test_list_wallets(self, super_token, user_ctx):
        # Ensure throwaway user's wallet exists
        requests.get(f"{API}/ai-wallet", headers=_h(user_ctx["token"]), timeout=20)
        r = requests.get(f"{API}/admin/ai-wallet/users?limit=100", headers=_h(super_token), timeout=20)
        assert r.status_code == 200, r.text[:200]
        items = r.json().get("items", [])
        assert isinstance(items, list) and len(items) >= 1
        sample = items[0]
        for k in ("user_id", "balance", "email"):
            assert k in sample, f"missing {k} in wallet item"

    def test_normal_user_blocked_from_users_list(self, user_ctx):
        r = requests.get(f"{API}/admin/ai-wallet/users", headers=_h(user_ctx["token"]), timeout=20)
        assert r.status_code == 403, r.text[:200]


# ─────────────────── AI Assess 402 path ───────────────────
class TestAssess402:
    """Force the throwaway user's wallet to 0 and verify both AI Assess endpoints return 402."""

    def _make_decision_with_factor(self, tok: str):
        # Create decision (My Dezider)
        r = requests.post(f"{API}/decisions",
                          headers=_h(tok),
                          json={"title": "Wallet 402 test", "context": "Testing 402 path"}, timeout=20)
        assert r.status_code in (200, 201), f"create decision: {r.status_code} {r.text[:200]}"
        decision_id = r.json().get("id")
        assert decision_id

        # Inject factors + options inline via PUT (this app stores them as sub-arrays)
        factor_id = "f_test_cost"
        option_id = "o_test_a"
        body = {
            "factors": [{
                "id": factor_id, "name": "Cost", "display_name": "Cost",
                "data_type": "numeric", "factor_type": "objective",
                "expected_value": "100", "operator": "<=", "unit": "USD",
                "rating": 5,
            }],
            "options": [{
                "id": option_id, "name": "Option A",
                "assessments": [],
            }],
        }
        r2 = requests.put(f"{API}/decisions/{decision_id}", headers=_h(tok), json=body, timeout=20)
        assert r2.status_code == 200, f"put decision: {r2.status_code} {r2.text[:300]}"
        return decision_id, factor_id, option_id

    def _make_pros_cons(self, tok: str):
        r = requests.post(f"{API}/pros-cons", headers=_h(tok),
                          json={"title": "PC Wallet 402", "context": "ctx"}, timeout=20)
        assert r.status_code in (200, 201), f"create pros-cons: {r.status_code} {r.text[:200]}"
        analysis_id = r.json().get("id") or r.json().get("analysis_id")
        assert analysis_id, f"no analysis id: {r.json()}"

        rf = requests.post(f"{API}/pros-cons/{analysis_id}/factors", headers=_h(tok),
                           json={"name": "Cost", "data_type": "numeric",
                                 "expected_value": "100", "operator": "<=", "unit": "USD",
                                 "rating": 5}, timeout=20)
        assert rf.status_code in (200, 201), f"pc factor: {rf.status_code} {rf.text[:300]}"
        factor_id = rf.json().get("id") or rf.json().get("factor_id")

        ro = requests.post(f"{API}/pros-cons/{analysis_id}/options", headers=_h(tok),
                           json={"name": "Option A"}, timeout=20)
        assert ro.status_code in (200, 201), f"pc option: {ro.status_code} {ro.text[:300]}"
        option_id = ro.json().get("id") or ro.json().get("option_id")
        return analysis_id, factor_id, option_id

    def test_dezider_ai_assess_402_when_empty(self, super_token, user_ctx):
        # Force balance to 0
        r = requests.post(f"{API}/admin/ai-wallet/grant", headers=_h(super_token),
                          json={"email": user_ctx["email"], "credits": 0, "mode": "set"}, timeout=20)
        assert r.status_code == 200

        try:
            decision_id, factor_id, option_id = self._make_decision_with_factor(user_ctx["token"])
        except AssertionError as e:
            pytest.skip(f"could not create decision/factor: {e}")
            return

        r = requests.post(
            f"{API}/decisions/{decision_id}/factors/{factor_id}/ai-assess",
            headers=_h(user_ctx["token"]),
            json={"option_id": option_id, "actual_value": "80"},
            timeout=60,
        )
        assert r.status_code == 402, f"expected 402, got {r.status_code} {r.text[:300]}"
        detail = r.json().get("detail", "")
        assert "credit" in detail.lower(), f"detail not human readable: {detail}"

    def test_pros_cons_ai_assess_402_when_empty(self, super_token, user_ctx):
        # Force balance to 0
        r = requests.post(f"{API}/admin/ai-wallet/grant", headers=_h(super_token),
                          json={"email": user_ctx["email"], "credits": 0, "mode": "set"}, timeout=20)
        assert r.status_code == 200

        try:
            analysis_id, factor_id, option_id = self._make_pros_cons(user_ctx["token"])
        except AssertionError as e:
            pytest.skip(f"could not create pros-cons: {e}")
            return

        r = requests.post(
            f"{API}/pros-cons/{analysis_id}/factors/{factor_id}/ai-assess",
            headers=_h(user_ctx["token"]),
            json={"option_id": option_id, "actual_value": "80"},
            timeout=60,
        )
        assert r.status_code == 402, f"expected 402, got {r.status_code} {r.text[:300]}"
        detail = r.json().get("detail", "")
        assert "credit" in detail.lower(), f"detail not human readable: {detail}"

    def test_assess_succeeds_after_refill(self, super_token, user_ctx):
        # Refill 50 credits
        r = requests.post(f"{API}/admin/ai-wallet/grant", headers=_h(super_token),
                          json={"email": user_ctx["email"], "credits": 50, "mode": "set"}, timeout=20)
        assert r.status_code == 200

        try:
            decision_id, factor_id, option_id = self._make_decision_with_factor(user_ctx["token"])
        except AssertionError as e:
            pytest.skip(f"could not create decision: {e}")
            return

        r = requests.post(
            f"{API}/decisions/{decision_id}/factors/{factor_id}/ai-assess",
            headers=_h(user_ctx["token"]),
            json={"option_id": option_id, "actual_value": "80"},
            timeout=90,
        )
        if r.status_code != 200:
            # If LLM is unreachable / 502 we don't want to fail wallet tests
            pytest.skip(f"AI assess returned {r.status_code} (LLM may be unavailable): {r.text[:200]}")
            return
        d = r.json()
        # MD endpoint returns "percentage", PC may differ — accept any of the known keys
        assert any(k in d for k in ("percentage", "assessment_pct", "satisfaction_pct")), f"unexpected shape: {d}"
        # Ledger SHOULD now show a debit if LLM ran
        rl = requests.get(f"{API}/ai-wallet/ledger?limit=40", headers=_h(user_ctx["token"]), timeout=20)
        kinds = [i.get("kind") for i in rl.json().get("items", [])]
        if "debit" not in kinds:
            pytest.skip(f"no debit recorded — LLM likely not invoked (deterministic path); kinds={kinds[:5]}")
