"""Live regression tests for the world-class Import-from-URL feature.

Covers:
- BACKEND 3: GET/PUT /api/admin/ai-wallet/config exposes new precise_model &
  precise_usd_per_mtok fields and validates precise_usd_per_mtok>0.

Run:
    cd /app/backend && python -m pytest tests/test_iter_url_world_class_import.py -v
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://repo-blueprint-1.preview.emergentagent.com").rstrip("/")

SUPER_ADMIN = {"email": "veales.vedic.decisions@gmail.com", "password": "Jelcos@Admin2026"}
REGULAR_ADMIN = {"email": "admin@test.com", "password": "AdminPass2026!"}


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code}: {r.text[:200]}"
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def super_token():
    return _login(SUPER_ADMIN)


@pytest.fixture(scope="module")
def admin_token():
    return _login(REGULAR_ADMIN)


@pytest.fixture(scope="module")
def super_headers(super_token):
    return {"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"}


class TestAiWalletConfigPreciseFields:
    """BACKEND 3: precise_model + precise_usd_per_mtok fields in admin AI wallet config."""

    def test_get_config_exposes_precise_fields(self, super_headers):
        r = requests.get(f"{BASE_URL}/api/admin/ai-wallet/config", headers=super_headers, timeout=15)
        assert r.status_code == 200, r.text[:200]
        cfg = r.json()
        assert "precise_model" in cfg, f"precise_model missing in config: {list(cfg.keys())}"
        assert "precise_usd_per_mtok" in cfg, f"precise_usd_per_mtok missing: {list(cfg.keys())}"
        assert isinstance(cfg["precise_model"], str) and cfg["precise_model"]
        assert isinstance(cfg["precise_usd_per_mtok"], (int, float))
        assert cfg["precise_usd_per_mtok"] > 0

    def test_regular_admin_cannot_access_super_admin_config(self, admin_token):
        h = {"Authorization": f"Bearer {admin_token}"}
        r = requests.get(f"{BASE_URL}/api/admin/ai-wallet/config", headers=h, timeout=15)
        assert r.status_code in (401, 403), f"expected 401/403 for non-super admin, got {r.status_code}"

    def test_put_accepts_precise_fields_and_persists(self, super_headers):
        # Snapshot the current config first
        snap = requests.get(f"{BASE_URL}/api/admin/ai-wallet/config", headers=super_headers, timeout=15).json()
        try:
            new_cfg = {
                "precise_model": "claude-sonnet-4-6",
                "precise_usd_per_mtok": 9.5,
            }
            r = requests.put(f"{BASE_URL}/api/admin/ai-wallet/config", headers=super_headers,
                             json=new_cfg, timeout=20)
            assert r.status_code == 200, r.text[:300]
            updated = r.json()
            assert updated.get("precise_model") == "claude-sonnet-4-6"
            assert updated.get("precise_usd_per_mtok") == pytest.approx(9.5, rel=1e-3)
            # GET back to verify persistence
            r2 = requests.get(f"{BASE_URL}/api/admin/ai-wallet/config", headers=super_headers, timeout=15)
            assert r2.status_code == 200
            cfg2 = r2.json()
            assert cfg2["precise_usd_per_mtok"] == pytest.approx(9.5, rel=1e-3)
            assert cfg2["precise_model"] == "claude-sonnet-4-6"
        finally:
            # Restore original
            restore = {"precise_model": snap.get("precise_model", "claude-sonnet-4-6"),
                       "precise_usd_per_mtok": snap.get("precise_usd_per_mtok", 9.0)}
            requests.put(f"{BASE_URL}/api/admin/ai-wallet/config", headers=super_headers,
                         json=restore, timeout=20)

    def test_put_rejects_zero_precise_usd_per_mtok(self, super_headers):
        r = requests.put(f"{BASE_URL}/api/admin/ai-wallet/config", headers=super_headers,
                         json={"precise_usd_per_mtok": 0}, timeout=15)
        assert r.status_code == 400, f"expected 400 for zero precise_usd_per_mtok, got {r.status_code}: {r.text[:200]}"

    def test_put_rejects_negative_precise_usd_per_mtok(self, super_headers):
        r = requests.put(f"{BASE_URL}/api/admin/ai-wallet/config", headers=super_headers,
                         json={"precise_usd_per_mtok": -3.0}, timeout=15)
        assert r.status_code == 400, f"expected 400 for negative precise_usd_per_mtok, got {r.status_code}: {r.text[:200]}"

    def test_put_empty_precise_model_falls_back_to_default(self, super_headers):
        snap = requests.get(f"{BASE_URL}/api/admin/ai-wallet/config", headers=super_headers, timeout=15).json()
        try:
            r = requests.put(f"{BASE_URL}/api/admin/ai-wallet/config", headers=super_headers,
                             json={"precise_model": "   "}, timeout=15)
            # Either 200 with the default applied, or 400 - both are acceptable patterns.
            assert r.status_code in (200, 400)
            if r.status_code == 200:
                assert r.json().get("precise_model"), "precise_model should be non-empty"
        finally:
            requests.put(f"{BASE_URL}/api/admin/ai-wallet/config", headers=super_headers,
                         json={"precise_model": snap.get("precise_model", "claude-sonnet-4-6")}, timeout=15)
