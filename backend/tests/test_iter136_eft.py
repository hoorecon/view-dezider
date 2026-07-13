"""EFT Tapping for Stress Relief — backend tests (iteration 136)."""
import os
import uuid
import io
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://repo-blueprint-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "AdminPass2026!"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    if r.status_code != 200:
        return None
    d = r.json()
    return d.get("session_token") or d.get("access_token") or d.get("token")


def _register_user():
    email = f"TEST_eft_{uuid.uuid4().hex[:8]}@test.com"
    payload = {"email": email, "password": "Password123!", "name": "EFT Test User"}
    r = requests.post(f"{API}/auth/register", json=payload, timeout=30)
    if r.status_code not in (200, 201):
        # try alternative login if already exists
        return None, email
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if not token:
        token = _login(email, "Password123!")
    return token, email


@pytest.fixture(scope="module")
def admin_token():
    t = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not t:
        pytest.skip("Admin login failed")
    return t


@pytest.fixture(scope="module")
def user_token():
    t, email = _register_user()
    if not t:
        pytest.skip("User registration failed")
    return t


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ============ GET CONFIG ============

class TestEftConfig:
    def test_user_get_config(self, user_token):
        r = requests.get(f"{API}/emotional-gatekeeper/eft/config", headers=_h(user_token), timeout=30)
        assert r.status_code == 200, r.text
        cfg = r.json()
        assert cfg.get("enabled") is True
        assert isinstance(cfg.get("tapping_points"), list)
        assert len(cfg["tapping_points"]) == 9
        assert "vimeo" in (cfg.get("video_url") or "").lower()
        assert isinstance(cfg.get("safety_keywords"), list) and len(cfg["safety_keywords"]) >= 5
        assert cfg.get("disclaimer")
        # First point should be the karate chop setup
        assert cfg["tapping_points"][0].get("is_setup") is True


# ============ SESSION + SAVE ============

class TestEftSession:
    def test_create_and_save_session(self, user_token):
        # create session
        r = requests.post(f"{API}/emotional-gatekeeper/sessions", headers=_h(user_token),
                          json={"session_type": "eft"}, timeout=30)
        assert r.status_code == 200, r.text
        sid = r.json()["id"]

        # save with final intensity
        payload = {
            "selected_type": "emotion",
            "subject_text": "fear",
            "affirmation": "Even though I feel fear, I deeply and completely love and accept myself.",
            "initial_intensity_score": 8,
            "final_intensity_score": 2,
            "rounds_completed": 1,
            "user_reflection": "I feel lighter.",
        }
        r = requests.post(f"{API}/emotional-gatekeeper/eft/{sid}/save",
                          headers=_h(user_token), json=payload, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["selected_type"] == "emotion"
        assert d["subject_text"] == "fear"
        assert d["initial_intensity_score"] == 8
        assert d["final_intensity_score"] == 2
        assert d["intensity_reduction"] == 6
        assert d["rounds_completed"] >= 1

        # verify session marked completed via GET
        rs = requests.get(f"{API}/emotional-gatekeeper/sessions/{sid}",
                          headers=_h(user_token), timeout=30)
        assert rs.status_code == 200
        sess = rs.json()
        assert sess["status"] == "completed"
        assert sess["intensity_after"] == 2
        assert sess.get("eft_reflection") is not None
        assert sess["eft_reflection"]["subject_text"] == "fear"

    def test_validation_bad_type(self, user_token):
        r = requests.post(f"{API}/emotional-gatekeeper/sessions", headers=_h(user_token),
                          json={"session_type": "eft"}, timeout=30)
        sid = r.json()["id"]
        r = requests.post(f"{API}/emotional-gatekeeper/eft/{sid}/save", headers=_h(user_token),
                          json={"selected_type": "bogus", "subject_text": "x", "affirmation": "a",
                                "initial_intensity_score": 5}, timeout=30)
        assert r.status_code == 400

    def test_validation_intensity_out_of_range(self, user_token):
        r = requests.post(f"{API}/emotional-gatekeeper/sessions", headers=_h(user_token),
                          json={"session_type": "eft"}, timeout=30)
        sid = r.json()["id"]
        r = requests.post(f"{API}/emotional-gatekeeper/eft/{sid}/save", headers=_h(user_token),
                          json={"selected_type": "emotion", "subject_text": "x", "affirmation": "a",
                                "initial_intensity_score": 11}, timeout=30)
        assert r.status_code == 400

        r2 = requests.post(f"{API}/emotional-gatekeeper/eft/{sid}/save", headers=_h(user_token),
                           json={"selected_type": "emotion", "subject_text": "x", "affirmation": "a",
                                 "initial_intensity_score": 5, "final_intensity_score": 99}, timeout=30)
        assert r2.status_code == 400

    def test_validation_empty_subject(self, user_token):
        r = requests.post(f"{API}/emotional-gatekeeper/sessions", headers=_h(user_token),
                          json={"session_type": "eft"}, timeout=30)
        sid = r.json()["id"]
        r = requests.post(f"{API}/emotional-gatekeeper/eft/{sid}/save", headers=_h(user_token),
                          json={"selected_type": "emotion", "subject_text": "   ",
                                "affirmation": "a", "initial_intensity_score": 5}, timeout=30)
        assert r.status_code == 400


# ============ DASHBOARD ============

class TestEftDashboard:
    def test_dashboard_has_eft_sessions(self, user_token):
        r = requests.get(f"{API}/emotional-gatekeeper/dashboard", headers=_h(user_token), timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "eft_sessions" in d
        assert d["eft_sessions"] >= 1


# ============ ADMIN RBAC + PUT ============

class TestEftAdmin:
    def test_non_admin_blocked(self, user_token):
        r = requests.get(f"{API}/emotional-gatekeeper/eft/admin/config", headers=_h(user_token), timeout=30)
        assert r.status_code in (401, 403)

        r = requests.put(f"{API}/emotional-gatekeeper/eft/admin/config", headers=_h(user_token),
                         json={"title": "Hack"}, timeout=30)
        assert r.status_code in (401, 403)

    def test_admin_get_returns_config_and_defaults(self, admin_token):
        r = requests.get(f"{API}/emotional-gatekeeper/eft/admin/config", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "config" in d and "defaults" in d
        assert d["config"]["title"]
        assert len(d["defaults"]["tapping_points"]) == 9

    def test_admin_put_persists(self, admin_token):
        new_title = f"EFT Title TEST_{uuid.uuid4().hex[:6]}"
        r = requests.put(f"{API}/emotional-gatekeeper/eft/admin/config", headers=_h(admin_token),
                         json={"title": new_title}, timeout=30)
        assert r.status_code == 200, r.text

        # verify via admin GET
        r = requests.get(f"{API}/emotional-gatekeeper/eft/admin/config", headers=_h(admin_token), timeout=30)
        assert r.json()["config"]["title"] == new_title

        # restore default
        defaults_title = "EFT Tapping for Stress Relief"
        requests.put(f"{API}/emotional-gatekeeper/eft/admin/config", headers=_h(admin_token),
                     json={"title": defaults_title}, timeout=30)


# ============ ADMIN UPLOAD ============

class TestEftUpload:
    def test_upload_image_ok(self, admin_token):
        png_bytes = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                     b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf"
                     b"\xc0\x00\x00\x00\x03\x00\x01\xe5\x27\xde\xfc\x00\x00\x00\x00IEND\xaeB`\x82")
        files = {"file": ("test.png", io.BytesIO(png_bytes), "image/png")}
        headers = {"Authorization": f"Bearer {admin_token}"}
        r = requests.post(f"{API}/emotional-gatekeeper/eft/admin/upload-media?media_type=image",
                          headers=headers, files=files, timeout=30)
        assert r.status_code == 200, r.text
        url = r.json().get("url", "")
        assert url.startswith("/api/static/eft/")

    def test_upload_wrong_content_type(self, admin_token):
        files = {"file": ("bad.txt", io.BytesIO(b"hi"), "text/plain")}
        headers = {"Authorization": f"Bearer {admin_token}"}
        r = requests.post(f"{API}/emotional-gatekeeper/eft/admin/upload-media?media_type=image",
                          headers=headers, files=files, timeout=30)
        assert r.status_code == 400

    def test_upload_bad_media_type(self, admin_token):
        files = {"file": ("x.png", io.BytesIO(b"data"), "image/png")}
        headers = {"Authorization": f"Bearer {admin_token}"}
        r = requests.post(f"{API}/emotional-gatekeeper/eft/admin/upload-media?media_type=foo",
                          headers=headers, files=files, timeout=30)
        assert r.status_code == 400
