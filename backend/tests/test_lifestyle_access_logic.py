import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, patch

from routes.lifestyle import verify_lifestyle_access

@pytest.mark.asyncio
async def test_verify_lifestyle_access_admin():
    user = {"user_id": "admin_1", "role": "super_admin", "user_type": "free", "subscription_plan": "none"}
    res = await verify_lifestyle_access(user)
    assert res is True

@pytest.mark.asyncio
async def test_verify_lifestyle_access_free_user():
    user = {"user_id": "free_user_1", "role": "user", "user_type": "free", "subscription_plan": "none"}
    with patch("routes.lifestyle.db") as mock_db:
        mock_db.app_settings.find_one = AsyncMock(return_value=None)
        mock_db.users.find_one = AsyncMock(return_value={"user_type": "free", "subscription_plan": "none"})
        mock_db.credit_wallets.find_one = AsyncMock(return_value=None)
        
        with pytest.raises(HTTPException) as exc_info:
            await verify_lifestyle_access(user)
        assert exc_info.value.status_code == 403
        assert "Lifestyle Dezider is not available for Free or On-Demand plans" in exc_info.value.detail

@pytest.mark.asyncio
async def test_verify_lifestyle_access_on_demand_user():
    user = {"user_id": "ondemand_user_1", "role": "user", "user_type": "on_demand_l2", "subscription_plan": "on_demand_l2"}
    with patch("routes.lifestyle.db") as mock_db:
        mock_db.app_settings.find_one = AsyncMock(return_value=None)
        mock_db.users.find_one = AsyncMock(return_value={"user_type": "on_demand_l2", "subscription_plan": "on_demand_l2"})
        mock_db.credit_wallets.find_one = AsyncMock(return_value=None)
        
        with pytest.raises(HTTPException) as exc_info:
            await verify_lifestyle_access(user)
        assert exc_info.value.status_code == 403

@pytest.mark.asyncio
async def test_verify_lifestyle_access_subscribed_user():
    user = {"user_id": "pro_user_1", "role": "user", "user_type": "paid", "subscription_plan": "pro"}
    with patch("routes.lifestyle.db") as mock_db:
        mock_db.app_settings.find_one = AsyncMock(return_value=None)
        mock_db.users.find_one = AsyncMock(return_value={"user_type": "paid", "subscription_plan": "pro"})
        mock_db.credit_wallets.find_one = AsyncMock(return_value={"subscription_status": "active", "current_plan": "pro"})
        
        res = await verify_lifestyle_access(user)
        assert res is True
