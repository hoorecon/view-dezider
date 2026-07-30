"""Homepage variant selector — tests."""
import os
import requests

BASE_URL = os.environ.get(
    "EXPO_PUBLIC_BACKEND_URL",
    "https://modal-responsive-fix.preview.emergentagent.com",
).rstrip("/")


def test_public_variant_is_returned():
    r = requests.get(f"{BASE_URL}/api/home-variant", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert body.get("variant") in {"modern", "classic"}


def test_admin_get_requires_auth():
    r = requests.get(f"{BASE_URL}/api/admin/home-variant", timeout=15)
    assert r.status_code in (401, 403)


def test_admin_put_requires_auth():
    r = requests.put(
        f"{BASE_URL}/api/admin/home-variant",
        json={"variant": "modern"}, timeout=15,
    )
    assert r.status_code in (401, 403)
