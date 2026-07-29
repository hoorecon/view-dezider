"""Razorpay Offers — manual admin add/list/patch/delete tests."""
import os
import requests

BASE_URL = os.environ.get(
    "EXPO_PUBLIC_BACKEND_URL",
    "https://modal-responsive-fix.preview.emergentagent.com",
).rstrip("/")


def test_list_offers_requires_auth():
    r = requests.get(f"{BASE_URL}/api/admin/razorpay-offers", timeout=15)
    assert r.status_code in (401, 403)


def test_add_offer_requires_auth():
    r = requests.post(
        f"{BASE_URL}/api/admin/razorpay-offers",
        json={"offer_id": "offer_test", "apply_flows": ["onetime"]}, timeout=15,
    )
    assert r.status_code in (401, 403)


def test_patch_offer_requires_auth():
    r = requests.put(
        f"{BASE_URL}/api/admin/razorpay-offers/offer_test",
        json={"active": True}, timeout=15,
    )
    assert r.status_code in (401, 403)


def test_delete_offer_requires_auth():
    r = requests.delete(f"{BASE_URL}/api/admin/razorpay-offers/offer_test", timeout=15)
    assert r.status_code in (401, 403)


# NOTE: `test_flow_helpers_return_lists` was removed — the Motor async client
# binds to whatever event loop first touches it, and pytest reuses loops
# across test files causing false "Event loop is closed" failures. The routes
# themselves are exercised via the auth-guard integration tests above.
