#!/usr/bin/env python3
"""
Backend API Testing for Modular Routes
Testing session-based auth with modular routes after auth fix.
"""

import asyncio
import httpx
import json
import time
from datetime import datetime

# Backend URL from the request
BASE_URL = "https://dezider-solver.preview.emergentagent.com/api"

class ModularRoutesTest:
    def __init__(self):
        self.session_token = None
        self.user_data = None
        
    async def test_modular_routes_workflow(self):
        """Test the complete modular routes workflow as requested"""
        print("🚀 STARTING MODULAR ROUTES TESTING")
        print("=" * 60)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Register user with unique email
            await self.test_user_registration(client)
            
            # Step 2: Test auth/me endpoint (main server routes)
            await self.test_auth_me_endpoint(client)
            
            # Step 3: Test feature-flags endpoint (modular routes from admin.py)
            await self.test_feature_flags_endpoint(client)
            
            # Step 4: Test solution-finders POST (modular routes from tools.py)
            await self.test_solution_finders_create(client)
            
            # Step 5: Test solution-finders GET (modular routes from tools.py)
            await self.test_solution_finders_list(client)
            
        print("\n" + "=" * 60)
        print("✅ MODULAR ROUTES TESTING COMPLETE")
        
    async def test_user_registration(self, client):
        """Step 1: POST /api/auth/register - register user with unique email"""
        print("\n1️⃣ Testing User Registration...")
        
        # Create unique email with timestamp
        timestamp = int(time.time())
        email = f"modtest_{timestamp}@test.com"
        
        registration_data = {
            "email": email,
            "password": "test123",
            "name": "Mod Test"
        }
        
        try:
            response = await client.post(
                f"{BASE_URL}/auth/register",
                json=registration_data
            )
            
            print(f"   📤 POST /auth/register")
            print(f"   📧 Email: {email}")
            print(f"   🔐 Password: test123")
            print(f"   👤 Name: Mod Test")
            print(f"   📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                self.session_token = data.get("session_token")
                self.user_data = data
                print(f"   ✅ Registration successful!")
                print(f"   🎫 Session token: {self.session_token[:20]}...")
                print(f"   🆔 User ID: {data.get('user_id')}")
                return True
            else:
                print(f"   ❌ Registration failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"   ❌ Registration error: {str(e)}")
            return False
    
    async def test_auth_me_endpoint(self, client):
        """Step 2: GET /api/auth/me - verify token works on main server routes"""
        print("\n2️⃣ Testing Auth Me Endpoint (Main Server Routes)...")
        
        if not self.session_token:
            print("   ❌ No session token available")
            return False
            
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            response = await client.get(
                f"{BASE_URL}/auth/me",
                headers=headers
            )
            
            print(f"   📤 GET /auth/me")
            print(f"   🎫 Using Bearer token: {self.session_token[:20]}...")
            print(f"   📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Auth me endpoint working!")
                print(f"   👤 User: {data.get('name')} ({data.get('email')})")
                print(f"   🆔 User ID: {data.get('user_id')}")
                print(f"   🔐 Auth method: {data.get('auth_method')}")
                return True
            else:
                print(f"   ❌ Auth me failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"   ❌ Auth me error: {str(e)}")
            return False
    
    async def test_feature_flags_endpoint(self, client):
        """Step 3: GET /api/feature-flags - verify token works on modular routes (admin.py)"""
        print("\n3️⃣ Testing Feature Flags Endpoint (Modular Routes - admin.py)...")
        
        if not self.session_token:
            print("   ❌ No session token available")
            return False
            
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            response = await client.get(
                f"{BASE_URL}/feature-flags",
                headers=headers
            )
            
            print(f"   📤 GET /feature-flags")
            print(f"   🎫 Using Bearer token: {self.session_token[:20]}...")
            print(f"   📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Feature flags endpoint working!")
                print(f"   🚩 Solution Finder: {data.get('solution_finder')}")
                print(f"   🚩 Solution Matrix: {data.get('solution_matrix')}")
                return True
            else:
                print(f"   ❌ Feature flags failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"   ❌ Feature flags error: {str(e)}")
            return False
    
    async def test_solution_finders_create(self, client):
        """Step 4: POST /api/solution-finders - Create entry (modular routes - tools.py)"""
        print("\n4️⃣ Testing Solution Finders Create (Modular Routes - tools.py)...")
        
        if not self.session_token:
            print("   ❌ No session token available")
            return False
            
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            solution_data = {
                "area_of_life": "career",
                "smart_goal": "Test Goal for Modular Routes",
                "milestones": ["Milestone 1", "Milestone 2"],
                "q1_all_concerns": "Test concerns",
                "q2_primary_concerns": "Primary test concerns",
                "q3_solutions": "Test solutions",
                "status": "in_progress"
            }
            
            response = await client.post(
                f"{BASE_URL}/solution-finders",
                headers=headers,
                json=solution_data
            )
            
            print(f"   📤 POST /solution-finders")
            print(f"   🎫 Using Bearer token: {self.session_token[:20]}...")
            print(f"   📋 Area of life: {solution_data['area_of_life']}")
            print(f"   🎯 SMART goal: {solution_data['smart_goal']}")
            print(f"   📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                self.solution_finder_id = data.get("entry_id")
                print(f"   ✅ Solution finder created successfully!")
                print(f"   🆔 Entry ID: {self.solution_finder_id}")
                print(f"   👤 User ID: {data.get('user_id')}")
                print(f"   📅 Created: {data.get('created_at')}")
                return True
            else:
                print(f"   ❌ Solution finder creation failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"   ❌ Solution finder creation error: {str(e)}")
            return False
    
    async def test_solution_finders_list(self, client):
        """Step 5: GET /api/solution-finders - List entries (modular routes - tools.py)"""
        print("\n5️⃣ Testing Solution Finders List (Modular Routes - tools.py)...")
        
        if not self.session_token:
            print("   ❌ No session token available")
            return False
            
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            response = await client.get(
                f"{BASE_URL}/solution-finders",
                headers=headers
            )
            
            print(f"   📤 GET /solution-finders")
            print(f"   🎫 Using Bearer token: {self.session_token[:20]}...")
            print(f"   📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Solution finders list retrieved successfully!")
                print(f"   📋 Total entries: {len(data)}")
                
                if data:
                    entry = data[0]
                    print(f"   🆔 First entry ID: {entry.get('entry_id')}")
                    print(f"   🎯 Goal: {entry.get('smart_goal')}")
                    print(f"   📍 Area: {entry.get('area_of_life')}")
                    print(f"   📊 Status: {entry.get('status')}")
                else:
                    print("   📝 No entries found (expected for new user)")
                    
                return True
            else:
                print(f"   ❌ Solution finders list failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"   ❌ Solution finders list error: {str(e)}")
            return False

async def main():
    """Run the modular routes testing workflow"""
    tester = ModularRoutesTest()
    await tester.test_modular_routes_workflow()

if __name__ == "__main__":
    asyncio.run(main())