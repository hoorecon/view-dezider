#!/usr/bin/env python3
"""
CLD Verification Test - Quick health check of View Dezider backend
Tests the specific endpoints requested in the review
"""

import asyncio
import httpx
import json
import sys
from datetime import datetime

# Backend URL from frontend/.env
BASE_URL = "https://modal-responsive-fix.preview.emergentagent.com/api"

class CLDVerificationTest:
    def __init__(self):
        self.base_url = BASE_URL
        self.session_token = None
        self.user_id = None
        self.test_results = []
        self.decision_id = None
        
    async def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        result = f"{status}: {test_name}"
        if details:
            result += f" - {details}"
        print(result)
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details
        })
        
    async def make_request(self, method: str, endpoint: str, data: dict = None, headers: dict = None):
        """Make HTTP request with error handling"""
        url = f"{self.base_url}{endpoint}"
        request_headers = {}
        
        if self.session_token:
            request_headers["Authorization"] = f"Bearer {self.session_token}"
            
        if headers:
            request_headers.update(headers)
            
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=request_headers)
                elif method.upper() == "POST":
                    response = await client.post(url, json=data, headers=request_headers)
                elif method.upper() == "PUT":
                    response = await client.put(url, json=data, headers=request_headers)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=request_headers)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                    
                return response
        except Exception as e:
            print(f"Request failed: {method} {url} - {str(e)}")
            return None
            
    async def test_1_register_user(self):
        """Test 1: Register a new user"""
        test_name = "Register User"
        
        # Use timestamp to ensure unique email
        timestamp = int(datetime.now().timestamp())
        user_data = {
            "email": f"cldtest_{timestamp}@test.com",
            "password": "test123",
            "name": "CLD Test User"
        }
        
        response = await self.make_request("POST", "/auth/register", user_data)
        
        if response and response.status_code == 200:
            data = response.json()
            self.session_token = data.get("session_token")
            self.user_id = data.get("user_id")
            await self.log_result(test_name, True, f"User registered with session token: {self.session_token[:20]}...")
            return True
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_2_auth_me(self):
        """Test 2: Test GET /api/auth/me"""
        test_name = "Auth Me Endpoint"
        
        response = await self.make_request("GET", "/auth/me")
        
        if response and response.status_code == 200:
            data = response.json()
            user_id = data.get("user_id")
            email = data.get("email")
            name = data.get("name")
            
            success = (user_id == self.user_id and email.startswith("cldtest_") and name == "CLD Test User")
            await self.log_result(test_name, success, f"User: {name} ({email})")
            return success
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_3_create_decision(self):
        """Test 3: Test POST /api/decisions"""
        test_name = "Create Decision"
        
        decision_data = {
            "title": "Test CLD Decision",
            "context": "Testing CLD features",
            "life_area": "Career",
            "decision_type": "need"
        }
        
        response = await self.make_request("POST", "/decisions", decision_data)
        
        if response and response.status_code == 200:
            data = response.json()
            self.decision_id = data.get("id")  # Response uses 'id' not 'decision_id'
            message = data.get("message")
            
            success = (self.decision_id is not None and message == "Decision created successfully")
            await self.log_result(test_name, success, f"Decision created with ID: {self.decision_id}")
            return success
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_4_list_decisions(self):
        """Test 4: Test GET /api/decisions"""
        test_name = "List Decisions"
        
        response = await self.make_request("GET", "/decisions")
        
        if response and response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                # Find our created decision
                our_decision = None
                for decision in data:
                    if decision.get("id") == self.decision_id:  # Use 'id' instead of 'decision_id'
                        our_decision = decision
                        break
                
                success = our_decision is not None
                count = len(data)
                await self.log_result(test_name, success, f"Found {count} decisions, our decision: {'Yes' if success else 'No'}")
                return success
            else:
                await self.log_result(test_name, False, "Response is not a list")
                return False
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_5_lifestyle_routines(self):
        """Test 5: Test GET /api/lifestyle/routines"""
        test_name = "Lifestyle Routines"
        
        response = await self.make_request("GET", "/lifestyle/routines")
        
        if response and response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                count = len(data)
                await self.log_result(test_name, True, f"Retrieved {count} routines (can be empty)")
                return True
            else:
                await self.log_result(test_name, False, "Response is not a list")
                return False
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_6_solutions_store(self):
        """Test 6: Test GET /api/solutions-store"""
        test_name = "Solutions Store"
        
        response = await self.make_request("GET", "/solutions-store/solutions")
        
        if response and response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                count = len(data)
                await self.log_result(test_name, True, f"Retrieved {count} solutions")
                return True
            else:
                await self.log_result(test_name, False, "Response is not a list")
                return False
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_7_deo_api_keys(self):
        """Test 7: Test GET /api/deo/api-keys"""
        test_name = "DEO API Keys"
        
        response = await self.make_request("GET", "/deo/api-keys")
        
        if response and response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and "keys" in data:
                keys = data.get("keys", [])
                count = len(keys)
                await self.log_result(test_name, True, f"Retrieved {count} API keys")
                return True
            elif isinstance(data, list):
                count = len(data)
                await self.log_result(test_name, True, f"Retrieved {count} API keys")
                return True
            else:
                await self.log_result(test_name, False, "Response format unexpected")
                return False
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting CLD Verification Test - View Dezider Backend Health Check")
        print("=" * 70)
        
        tests = [
            self.test_1_register_user,
            self.test_2_auth_me,
            self.test_3_create_decision,
            self.test_4_list_decisions,
            self.test_5_lifestyle_routines,
            self.test_6_solutions_store,
            self.test_7_deo_api_keys,
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            try:
                result = await test()
                if result:
                    passed += 1
            except Exception as e:
                print(f"❌ FAIL: {test.__name__} - Exception: {str(e)}")
                
        print("\n" + "=" * 70)
        print(f"🎯 CLD VERIFICATION SUMMARY: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED! View Dezider backend is healthy and working correctly.")
        else:
            print(f"⚠️  {total - passed} tests failed. Backend issues detected.")
            
        return passed == total

async def main():
    """Main test runner"""
    test_suite = CLDVerificationTest()
    success = await test_suite.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())