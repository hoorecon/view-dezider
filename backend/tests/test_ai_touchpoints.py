"""
Test AI Touchpoints toggles (MyDezider flow) Admin vs User Frontend enforcement.
"""
import pytest
from core.ai_wallet import update_config, get_config, touchpoint_enabled, estimates

@pytest.mark.asyncio
async def test_ai_touchpoints_toggle_and_enforcement():
    # 1. Ensure all touchpoints enabled by default
    await update_config({
        "tp_best_factors": True,
        "tp_prioritize_factors": True,
        "tp_best_options": True,
        "tp_assess_all": True,
        "tp_collab_ai_merge": True,
    }, by="test_admin")

    cfg = await get_config()
    assert cfg["tp_best_factors"] is True
    assert cfg["tp_prioritize_factors"] is True
    assert cfg["tp_best_options"] is True
    assert cfg["tp_assess_all"] is True
    assert cfg["tp_collab_ai_merge"] is True

    est = await estimates()
    tps = est["touchpoints"]
    assert tps["tp_best_factors"] is True
    assert tps["tp_prioritize_factors"] is True
    assert tps["tp_best_options"] is True
    assert tps["tp_assess_all"] is True
    assert tps["tp_collab_ai_merge"] is True

    # 2. Toggle tp_best_factors to False
    await update_config({"tp_best_factors": False}, by="test_admin")
    assert await touchpoint_enabled("tp_best_factors") is False

    est_disabled = await estimates()
    assert est_disabled["touchpoints"]["tp_best_factors"] is False

    # 3. Re-enable all
    await update_config({
        "tp_best_factors": True,
        "tp_prioritize_factors": True,
        "tp_best_options": True,
        "tp_assess_all": True,
        "tp_collab_ai_merge": True,
    }, by="test_admin")
    assert await touchpoint_enabled("tp_best_factors") is True
