#!/usr/bin/env python3
"""
CLD Debug Test - Debug the failing endpoints
"""

import asyncio
import httpx
import json
import sys
from datetime import datetime

# Backend URL from frontend/.env
BASE_URL = "https://repo-blueprint-1.preview.emergentagent.com/api"

async def debug_endpoints():
    """Debug the failing endpoints"""
    
    # First register a user to get session token
    timestamp = int(datetime.now().timestamp())
    user_data = {
        "email": f"debug_test_{timestamp}@test.com",
        "password": "test123",
        "name": "Debug Test User"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Register user
        response = await client.post(f"{BASE_URL}/auth/register", json=user_data)
        if response.status_code == 200:
            data = response.json()
            session_token = data.get("session_token")
            print(f"✅ Registered user, session token: {session_token[:20]}...")
            
            headers = {"Authorization": f"Bearer {session_token}"}
            
            # Debug decision creation
            print("\n🔍 Debugging Decision Creation:")
            decision_data = {
                "title": "Test CLD Decision",
                "context": "Testing CLD features",
                "life_area": "Career",
                "decision_type": "need"
            }
            
            response = await client.post(f"{BASE_URL}/decisions", json=decision_data, headers=headers)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            # Debug DEO API Keys
            print("\n🔍 Debugging DEO API Keys:")
            response = await client.get(f"{BASE_URL}/deo/api-keys", headers=headers)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
        else:
            print(f"❌ Failed to register user: {response.status_code} - {response.text}")

if __name__ == "__main__":
    asyncio.run(debug_endpoints())