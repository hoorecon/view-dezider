"""
Test ACM quota evaluation integration with Module Free-Use Limits.
- my_dezider_create, pros_cons, solution_finder evaluate quota via Module Free-Use Limits.
- Other features (e.g. swot_analysis) evaluate quota directly from ACM matrix.
"""
import pytest
from core.acm_engine import check_feature_access, get_all_feature_access, seed_acm_defaults, refresh_acm_cache
from core.database import db

@pytest.mark.asyncio
async def test_acm_module_limits_governed_quota_and_acm_quota():
    await seed_acm_defaults(force=False)
    await refresh_acm_cache()

    # Configure module_free_limits for 'free' tier: my_dezider=2, pros_cons=2, solution_finder=2
    await db.module_free_limits.update_one(
        {"tier": "free", "module": "my_dezider"},
        {"$set": {"limit": 2}},
        upsert=True,
    )
    await db.module_free_limits.update_one(
        {"tier": "free", "module": "pros_cons"},
        {"$set": {"limit": 2}},
        upsert=True,
    )
    await db.module_free_limits.update_one(
        {"tier": "free", "module": "solution_finder"},
        {"$set": {"limit": 2}},
        upsert=True,
    )

    # Ensure my_dezider_create, pros_cons, and solution_finder have 'full' access in ACM for 'free' tier
    await db.acm_modules.update_one(
        {"module_id": "my_dezider", "features.feature_id": "my_dezider_create"},
        {"$set": {"features.$.access.free": {"level": "full", "quota": -1}}}
    )
    await db.acm_modules.update_one(
        {"module_id": "decision_kickstarters", "features.feature_id": "pros_cons"},
        {"$set": {"features.$.access.free": {"level": "full", "quota": -1}}}
    )
    await db.acm_modules.update_one(
        {"module_id": "solution_tools", "features.feature_id": "solution_finder"},
        {"$set": {"features.$.access.free": {"level": "full", "quota": -1}}}
    )
    await refresh_acm_cache()

    test_user = {
        "user_id": "test_quota_user_1",
        "role": "user",
        "user_type": "free",
        "subscription_plan": "none",
    }

    # Reset usage counters for test user
    await db.module_usage_counters.delete_many({"user_id": test_user["user_id"]})
    await db.decisions.delete_many({"user_id": test_user["user_id"]})
    await db.pros_cons.delete_many({"user_id": test_user["user_id"]})
    await db.solution_finders.delete_many({"user_id": test_user["user_id"]})

    # 1. Check feature access for MyDezider (governed by module free limits)
    res_md = await check_feature_access(test_user, "my_dezider_create")
    assert res_md["allowed"] is True
    assert res_md["access_level"] == "full"
    assert res_md["quota_limit"] == 2
    assert res_md["quota_used"] == 0
    assert res_md["quota_remaining"] == 2

    # Simulate 2 creations in module_usage_counters
    await db.module_usage_counters.update_one(
        {"user_id": test_user["user_id"], "module": "my_dezider"},
        {"$set": {"count": 2}},
        upsert=True,
    )

    # 2. Check access after hitting limit -> quota_exceeded
    res_md_exceeded = await check_feature_access(test_user, "my_dezider_create")
    assert res_md_exceeded["allowed"] is False
    assert res_md_exceeded["access_level"] == "quota_exceeded"
    assert res_md_exceeded["quota_limit"] == 2
    assert res_md_exceeded["quota_used"] == 2
    assert res_md_exceeded["quota_remaining"] == 0

    # 3. Check bulk access (get_all_feature_access)
    all_access = await get_all_feature_access(test_user)
    assert all_access["my_dezider_create"]["access_level"] == "quota_exceeded"
    assert all_access["my_dezider_create"]["quota_limit"] == 2
    assert all_access["pros_cons"]["access_level"] == "full"
    assert all_access["pros_cons"]["quota_limit"] == 2

    # 4. Cleanup
    await db.module_usage_counters.delete_many({"user_id": test_user["user_id"]})
