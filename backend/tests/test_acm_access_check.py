"""
Test ACM access_level (locked, read, hidden) integration in /store/access-check.
"""
import pytest
from core.acm_engine import seed_acm_defaults, refresh_acm_cache
from core.database import db

@pytest.mark.asyncio
async def test_acm_locked_read_hidden_in_store_access_check():
    await seed_acm_defaults(force=False)

    # Set my_dezider_create access for free tier to locked
    await db.acm_modules.update_one(
        {"module_id": "my_dezider", "features.feature_id": "my_dezider_create"},
        {"$set": {"features.$.access.free": {"level": "locked", "quota": 0}}}
    )
    await refresh_acm_cache()

    test_user = {"user_id": "test_acm_user_1", "role": "user", "user_type": "free", "subscription_plan": "none"}

    from routes.sku_store import access_check
    res = await access_check(module="dezider", user=test_user)
    assert res["has_access"] is False
    assert res["access_level"] == "locked"
    assert res["acm_restricted"] is True

    # Set access to read
    await db.acm_modules.update_one(
        {"module_id": "my_dezider", "features.feature_id": "my_dezider_create"},
        {"$set": {"features.$.access.free": {"level": "read", "quota": 0}}}
    )
    await refresh_acm_cache()

    res_read = await access_check(module="dezider", user=test_user)
    assert res_read["has_access"] is False
    assert res_read["access_level"] == "read"
    assert res_read["acm_restricted"] is True

    # Set access to hidden
    await db.acm_modules.update_one(
        {"module_id": "my_dezider", "features.feature_id": "my_dezider_create"},
        {"$set": {"features.$.access.free": {"level": "hidden", "quota": 0}}}
    )
    await refresh_acm_cache()

    res_hidden = await access_check(module="dezider", user=test_user)
    assert res_hidden["has_access"] is False
    assert res_hidden["access_level"] == "hidden"
    assert res_hidden["acm_restricted"] is True

    # Restore full access for free tier so DB is left in a clean state
    await db.acm_modules.update_one(
        {"module_id": "my_dezider", "features.feature_id": "my_dezider_create"},
        {"$set": {"features.$.access.free": {"level": "full", "quota": -1}}}
    )
    await refresh_acm_cache()

    res_full = await access_check(module="dezider", user=test_user)
    assert res_full["access_level"] == "full"
    assert res_full["acm_restricted"] is False
    assert res_full["has_access"] is False  # free user needs on-demand payment

