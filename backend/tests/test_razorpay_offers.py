"""Razorpay Offers — admin sync/list/patch tests."""
import os
import requests

BASE_URL = os.environ.get(
    "EXPO_PUBLIC_BACKEND_URL",
    "https://modal-responsive-fix.preview.emergentagent.com",
).rstrip("/")


def test_list_offers_requires_auth():
    r = requests.get(f"{BASE_URL}/api/admin/razorpay-offers", timeout=15)
    assert r.status_code in (401, 403)


def test_sync_offers_requires_auth():
    r = requests.post(f"{BASE_URL}/api/admin/razorpay-offers/sync", timeout=15)
    assert r.status_code in (401, 403)


def test_patch_offer_requires_auth():
    r = requests.put(
        f"{BASE_URL}/api/admin/razorpay-offers/offer_test",
        json={"active": True}, timeout=15,
    )
    assert r.status_code in (401, 403)


def test_flow_helpers_return_lists():
    """Direct unit call — helper must return a list even when DB is empty."""
    import asyncio, sys, pathlib
    sys.path.insert(0, str(pathlib.Path("/app/backend")))
    from routes.razorpay_offers import get_offers_for_flow, get_best_offer_for_flow

    async def _run():
        ids = await get_offers_for_flow("recurring")
        assert isinstance(ids, list)
        best = await get_best_offer_for_flow("recurring")
        assert best is None or isinstance(best, str)

    asyncio.run(_run())
