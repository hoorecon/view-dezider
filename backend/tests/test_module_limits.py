"""Module Free-Use Limits tests."""
import os
import asyncio
import sys
import pathlib

import requests
import pytest

BASE_URL = os.environ.get(
    "EXPO_PUBLIC_BACKEND_URL",
    "https://modal-responsive-fix.preview.emergentagent.com",
).rstrip("/")

sys.path.insert(0, str(pathlib.Path("/app/backend")))


def test_get_admin_limits_requires_auth():
    r = requests.get(f"{BASE_URL}/api/admin/module-limits", timeout=15)
    assert r.status_code in (401, 403)


def test_put_admin_limits_requires_auth():
    r = requests.put(
        f"{BASE_URL}/api/admin/module-limits",
        json={"rows": [{"tier": "free", "module": "solution_finder", "limit": 5}]},
        timeout=15,
    )
    assert r.status_code in (401, 403)


def test_me_usage_requires_auth():
    r = requests.get(f"{BASE_URL}/api/me/module-usage", timeout=15)
    assert r.status_code in (401, 403)


def test_defaults_include_three_gated_modules():
    from routes.module_limits import GATED_MODULES
    assert set(GATED_MODULES) == {"solution_finder", "pros_cons", "my_dezider"}


def test_admin_role_is_exempt_from_cap():
    """A super-admin role should never be blocked, no matter the counter."""
    from routes.module_limits import check_and_reserve_usage

    async def _run():
        # Should not raise even if used > limit hypothetically.
        await check_and_reserve_usage(
            {"user_id": "admin-test", "role": "super_admin", "tier": "free"},
            "solution_finder",
        )
        await check_and_reserve_usage(
            {"user_id": "admin-test", "role": "admin", "tier": "free"},
            "pros_cons",
        )

    asyncio.run(_run())


def test_unknown_module_is_unlimited_by_default():
    """User asked: 'no limit for all other modules'. Unknown module → allowed."""
    from routes.module_limits import check_and_reserve_usage

    async def _run():
        await check_and_reserve_usage(
            {"user_id": "some-user", "role": "user", "tier": "free"},
            "unknown_module_xyz",
        )

    asyncio.run(_run())
