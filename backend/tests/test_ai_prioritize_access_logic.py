"""Unit tests for AI Prioritization (Step 4 "Prioritize with AI") feature access restrictions:
Restricted for Free, On-Demand, and Basic users.
Allowed for Pro, Premium, Enterprise, Admins, Testers.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from routes.decider_store import verify_decider_apps_access

@pytest.mark.asyncio
async def test_ai_prioritize_access_admin_allowed():
    user = {"user_id": "u1", "role": "admin"}
    assert await verify_decider_apps_access(user) is True

@pytest.mark.asyncio
async def test_ai_prioritize_access_super_admin_allowed():
    user = {"user_id": "u2", "role": "super_admin"}
    assert await verify_decider_apps_access(user) is True

@pytest.mark.asyncio
async def test_ai_prioritize_access_tester_allowed():
    user = {"user_id": "u3", "role": "user", "user_type": "beta"}
    with patch("routes.decider_store.db") as mock_db:
        mock_db.app_settings.find_one = AsyncMock(return_value=None)
        mock_db.users.find_one = AsyncMock(return_value={"user_type": "beta"})
        assert await verify_decider_apps_access(user) is True

@pytest.mark.asyncio
async def test_ai_prioritize_access_pro_plan_allowed():
    user = {"user_id": "u5", "role": "user", "subscription_plan": "pro"}
    with patch("routes.decider_store.db") as mock_db:
        mock_db.app_settings.find_one = AsyncMock(return_value=None)
        mock_db.users.find_one = AsyncMock(return_value={"subscription_plan": "pro"})
        mock_db.credit_wallets.find_one = AsyncMock(return_value=None)
        assert await verify_decider_apps_access(user) is True

@pytest.mark.asyncio
async def test_ai_prioritize_access_premium_plan_allowed():
    user = {"user_id": "u8", "role": "user", "subscription_plan": "premium"}
    with patch("routes.decider_store.db") as mock_db:
        mock_db.app_settings.find_one = AsyncMock(return_value=None)
        mock_db.users.find_one = AsyncMock(return_value={"subscription_plan": "premium"})
        mock_db.credit_wallets.find_one = AsyncMock(return_value=None)
        assert await verify_decider_apps_access(user) is True

@pytest.mark.asyncio
async def test_ai_prioritize_access_free_plan_blocked():
    user = {"user_id": "u6", "role": "user", "subscription_plan": "free"}
    with patch("routes.decider_store.db") as mock_db:
        mock_db.app_settings.find_one = AsyncMock(return_value=None)
        mock_db.users.find_one = AsyncMock(return_value={"subscription_plan": "free", "user_type": "free"})
        mock_db.credit_wallets.find_one = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as exc:
            await verify_decider_apps_access(user)
        assert exc.value.status_code == 403

@pytest.mark.asyncio
async def test_ai_prioritize_access_on_demand_blocked():
    user = {"user_id": "u7", "role": "user", "subscription_plan": "on_demand_l1"}
    with patch("routes.decider_store.db") as mock_db:
        mock_db.app_settings.find_one = AsyncMock(return_value=None)
        mock_db.users.find_one = AsyncMock(return_value={"subscription_plan": "on_demand_l1", "user_type": "on_demand_l1"})
        mock_db.credit_wallets.find_one = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as exc:
            await verify_decider_apps_access(user)
        assert exc.value.status_code == 403

@pytest.mark.asyncio
async def test_ai_prioritize_access_basic_plan_blocked():
    user = {"user_id": "u4", "role": "user", "subscription_plan": "basic"}
    with patch("routes.decider_store.db") as mock_db:
        mock_db.app_settings.find_one = AsyncMock(return_value=None)
        mock_db.users.find_one = AsyncMock(return_value={"subscription_plan": "basic", "user_type": "basic"})
        mock_db.credit_wallets.find_one = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as exc:
            await verify_decider_apps_access(user)
        assert exc.value.status_code == 403
