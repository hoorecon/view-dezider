"""Tests for Group Decisions creation limits across plans (Free, On-Demand L1/L2, Basic, Pro, Premium, Admin)."""

import os
import sys
import pathlib
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException

# Ensure backend folder is in python path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from routes.module_limits import check_and_reserve_usage, _get_usage


@pytest.mark.asyncio
async def test_free_user_group_decision_restricted():
    """Free tier user has limit 0 for group_decision and should get 402 error."""
    mock_user = {"user_id": "usr_free_123", "role": "user", "user_type": "free"}
    
    with patch("routes.module_limits._resolve_tier", AsyncMock(return_value="free")), \
         patch("routes.module_limits._get_limit", AsyncMock(return_value=0)), \
         patch("routes.module_limits._get_usage", AsyncMock(return_value=0)), \
         patch("routes.sku_store.has_any_paid_access", AsyncMock(return_value={"has_access": False})):
        with pytest.raises(HTTPException) as exc_info:
            await check_and_reserve_usage(mock_user, "group_decision")
        assert exc_info.value.status_code == 402
        assert "group decision" in exc_info.value.detail.lower() or "tier" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_on_demand_l1_group_decision_restricted():
    """On-Demand L1 user has limit 0 for group_decision and should get 402 error."""
    mock_user = {"user_id": "usr_l1_123", "role": "user", "user_type": "on_demand_l1"}
    
    with patch("routes.module_limits._resolve_tier", AsyncMock(return_value="on_demand_l1")), \
         patch("routes.module_limits._get_limit", AsyncMock(return_value=0)), \
         patch("routes.module_limits._get_usage", AsyncMock(return_value=0)), \
         patch("routes.sku_store.has_any_paid_access", AsyncMock(return_value={"has_access": False})):
        with pytest.raises(HTTPException) as exc_info:
            await check_and_reserve_usage(mock_user, "group_decision")
        assert exc_info.value.status_code == 402


@pytest.mark.asyncio
async def test_on_demand_l2_group_decision_bundle_quota():
    """On-Demand L2 user has shared 5-unit bundle limit across 6 L2 modules."""
    mock_user = {"user_id": "usr_l2_123", "role": "user", "user_type": "on_demand_l2"}
    
    # 1. Under limit (used 4 of 5)
    with patch("routes.module_limits._resolve_tier", AsyncMock(return_value="on_demand_l2")), \
         patch("routes.module_limits._get_limit", AsyncMock(return_value=5)), \
         patch("routes.module_limits._get_combined_l2_usage", AsyncMock(return_value=4)), \
         patch("routes.sku_store.has_any_paid_access", AsyncMock(return_value={"has_access": False})), \
         patch("routes.module_limits.db.module_usage_counters", AsyncMock()):
        # Should not raise exception
        await check_and_reserve_usage(mock_user, "group_decision")

    # 2. Exceeded limit (used 5 of 5)
    with patch("routes.module_limits._resolve_tier", AsyncMock(return_value="on_demand_l2")), \
         patch("routes.module_limits._get_limit", AsyncMock(return_value=5)), \
         patch("routes.module_limits._get_combined_l2_usage", AsyncMock(return_value=5)), \
         patch("routes.sku_store.has_any_paid_access", AsyncMock(return_value={"has_access": False})):
        with pytest.raises(HTTPException) as exc_info:
            await check_and_reserve_usage(mock_user, "group_decision")
        assert exc_info.value.status_code == 402
        assert "L2 bundle" in exc_info.value.detail or "5" in exc_info.value.detail


@pytest.mark.asyncio
async def test_subscription_plans_custom_module_limits():
    """Basic/Pro/Premium subscription plans check module free limits settings."""
    mock_user = {"user_id": "usr_basic_123", "role": "user", "user_type": "paid", "subscription_plan": "basic"}

    # 1. Default unlimited (-1)
    with patch("routes.module_limits._resolve_tier", AsyncMock(return_value="basic")), \
         patch("routes.module_limits._get_limit", AsyncMock(return_value=-1)), \
         patch("routes.sku_store.has_any_paid_access", AsyncMock(return_value={"has_access": False})):
        await check_and_reserve_usage(mock_user, "group_decision")

    # 2. Admin set custom count limit = 2 (used 1 -> allowed)
    with patch("routes.module_limits._resolve_tier", AsyncMock(return_value="basic")), \
         patch("routes.module_limits._get_limit", AsyncMock(return_value=2)), \
         patch("routes.module_limits._get_usage", AsyncMock(return_value=1)), \
         patch("routes.sku_store.has_any_paid_access", AsyncMock(return_value={"has_access": False})), \
         patch("routes.module_limits.db.module_usage_counters", AsyncMock()):
        await check_and_reserve_usage(mock_user, "group_decision")

    # 3. Admin set custom count limit = 2 (used 2 -> 402 blocked)
    with patch("routes.module_limits._resolve_tier", AsyncMock(return_value="basic")), \
         patch("routes.module_limits._get_limit", AsyncMock(return_value=2)), \
         patch("routes.module_limits._get_usage", AsyncMock(return_value=2)), \
         patch("routes.sku_store.has_any_paid_access", AsyncMock(return_value={"has_access": False})):
        with pytest.raises(HTTPException) as exc_info:
            await check_and_reserve_usage(mock_user, "group_decision")
        assert exc_info.value.status_code == 402


@pytest.mark.asyncio
async def test_admin_is_always_exempt():
    """Super Admin / Admin / Co-Admin are always exempt."""
    admin_user = {"user_id": "admin_123", "role": "super_admin"}
    await check_and_reserve_usage(admin_user, "group_decision")
