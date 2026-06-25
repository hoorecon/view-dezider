#!/usr/bin/env python3
"""
Debug specific DEO endpoints
"""

import asyncio
import httpx
import json

BASE_URL = "https://modal-responsive-fix.preview.emergentagent.com/api"

async def debug_endpoints():
    # First register and get API key
    user_data = {
        "email": f"debug_test_{int(asyncio.get_event_loop().time())}@test.com",
        "password": "DebugTest123!",
        "name": "Debug Tester"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Register
        response = await client.post(f"{BASE_URL}/auth/register", json=user_data)
        if response.status_code != 200:
            print(f"Registration failed: {response.status_code} - {response.text}")
            return
            
        data = response.json()
        session_token = data.get("session_token")
        print(f"✅ Registered user: {data.get('user_id')}")
        
        # Generate API key
        key_data = {
            "name": "Debug Key",
            "permissions": ["full_flow", "values_api", "logic_api"]
        }
        
        headers = {"Authorization": f"Bearer {session_token}"}
        response = await client.post(f"{BASE_URL}/deo/api-keys", json=key_data, headers=headers)
        if response.status_code != 200:
            print(f"API key generation failed: {response.status_code} - {response.text}")
            return
            
        api_key_data = response.json()
        api_key = api_key_data.get("api_key")
        print(f"✅ Generated API key: {api_key[:20]}...")
        
        # Get solutions first
        print("\n🔍 Getting solutions...")
        response = await client.get(f"{BASE_URL}/deo/public/solutions?api_key={api_key}")
        if response.status_code == 200:
            solutions_data = response.json()
            solutions = solutions_data.get("solutions", [])
            solution_ids = [sol.get("solution_id") for sol in solutions[:2]]
            print(f"Got {len(solutions)} solutions, using IDs: {solution_ids}")
        else:
            print(f"Failed to get solutions: {response.status_code} - {response.text}")
            return
        
        # Test full flow API
        print("\n🔍 Testing Full Flow API...")
        flow_data = {
            "solution_ids": solution_ids
        }
        
        headers = {"X-DEO-API-Key": api_key}
        response = await client.post(f"{BASE_URL}/deo/public/decision-flow", json=flow_data, headers=headers)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Response keys: {list(data.keys())}")
            if "decision_result" in data:
                result = data["decision_result"]
                print(f"Decision result keys: {list(result.keys())}")
                print(f"Options count: {len(result.get('options', []))}")
            else:
                print(f"Full response: {json.dumps(data, indent=2)}")
        else:
            print(f"Error: {response.text}")
            
        # Test scrape URL
        print("\n🔍 Testing Scrape URL...")
        scrape_data = {
            "url": "https://www.apollo247.com",
            "mode": "ai",
            "context": "Healthcare services in Chennai"
        }
        
        headers = {"Authorization": f"Bearer {session_token}"}
        response = await client.post(f"{BASE_URL}/deo/scrape-url", json=scrape_data, headers=headers)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Response keys: {list(data.keys())}")
            products = data.get("products", [])
            print(f"Products count: {len(products)}")
            scrape_id = data.get("scrape_id")
            print(f"Scrape ID: {scrape_id}")
        else:
            print(f"Error: {response.text}")
            
        # Test import
        print("\n🔍 Testing Import...")
        import_data = {
            "products": [
                {
                    "name": "Test Hospital",
                    "type": "SERVICE",
                    "description": "A test hospital",
                    "provider": "Test Corp",
                    "quantitative_factors": [
                        {
                            "factor_name": "Cost",
                            "value": 5000,
                            "unit": "INR"
                        }
                    ],
                    "qualitative_factors": [
                        {
                            "factor_name": "Quality",
                            "rating": 8,
                            "summary": "Good quality"
                        }
                    ]
                }
            ],
            "source_url": "https://test.com",
            "country": "IN",
            "language": "en",
            "visibility": "PRIVATE"
        }
        
        response = await client.post(f"{BASE_URL}/deo/import", json=import_data, headers=headers)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Response keys: {list(data.keys())}")
            imported_count = data.get("imported_count", 0)
            success_status = data.get("success", False)
            print(f"Imported: {imported_count}, Success: {success_status}")
        else:
            print(f"Error: {response.text}")

if __name__ == "__main__":
    asyncio.run(debug_endpoints())