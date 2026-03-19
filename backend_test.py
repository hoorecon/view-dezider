#!/usr/bin/env python3

import asyncio
import httpx
import json
import os
from datetime import datetime

# Configuration
BACKEND_URL = "https://best-mate-decisions.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

class AuthEndpointTester:
    def __init__(self):
        self.session_token = None
        self.user_id = None
        self.client = httpx.AsyncClient(timeout=30.0)
        self.stored_otp = None
        
    async def close(self):
        await self.client.aclose()
        
    async def test_register_user(self):
        """Register a test user for forgot password testing"""
        print("\n=== Testing User Registration ===")
        
        test_user_data = {
            "email": "testforgot@test.com",
            "password": "pass123",
            "name": "Test User"
        }
        
        response = await self.client.post(
            f"{API_BASE}/auth/register",
            json=test_user_data
        )
        
        if response.status_code == 200:
            data = response.json()
            self.session_token = data["session_token"]
            self.user_id = data["user_id"]
            print(f"✅ Registration successful")
            print(f"   User ID: {self.user_id}")
            print(f"   Email: {test_user_data['email']}")
            print(f"   Session Token: {self.session_token[:20]}...")
            return True
        elif response.status_code == 400 and "already registered" in response.text:
            print(f"✅ User already exists, continuing with testing")
            # Try to login to get session token
            return await self.login_existing_user()
        else:
            print(f"❌ Registration failed: {response.status_code} - {response.text}")
            return False
            
    async def login_existing_user(self):
        """Login with existing test user"""
        print("\n--- Logging in with existing test user ---")
        login_data = {
            "email": "testforgot@test.com", 
            "password": "pass123"
        }
        
        response = await self.client.post(
            f"{API_BASE}/auth/login",
            json=login_data
        )
        
        if response.status_code == 200:
            data = response.json()
            self.session_token = data["session_token"]
            self.user_id = data["user_id"]
            print(f"✅ Login successful for existing user")
            return True
        else:
            # User might have changed password, try with newpass456
            login_data["password"] = "newpass456"
            response = await self.client.post(
                f"{API_BASE}/auth/login",
                json=login_data
            )
            if response.status_code == 200:
                data = response.json()
                self.session_token = data["session_token"]
                self.user_id = data["user_id"]
                print(f"✅ Login successful with reset password")
                return True
            else:
                print(f"❌ Login failed: {response.status_code} - {response.text}")
                return False

    async def test_forgot_password_flow(self):
        """Test the complete forgot password flow"""
        print("\n=== Testing Forgot Password Flow ===")
        
        # Test 2a: POST forgot-password with valid email
        print("\n2a. Testing forgot-password with valid email...")
        forgot_data = {"email": "testforgot@test.com"}
        
        response = await self.client.post(
            f"{API_BASE}/auth/forgot-password",
            json=forgot_data
        )
        
        if response.status_code == 200:
            data = response.json()
            self.stored_otp = data.get("otp")  # MVP returns OTP in response
            print(f"✅ Forgot password request successful")
            print(f"   Message: {data.get('message', '')}")
            print(f"   OTP: {self.stored_otp}")
            print(f"   Expires in: {data.get('expires_in_minutes', 'Unknown')} minutes")
        else:
            print(f"❌ Forgot password failed: {response.status_code} - {response.text}")
            return False
            
        # Test 2b: POST forgot-password with nonexistent email
        print("\n2b. Testing forgot-password with nonexistent email...")
        forgot_data_invalid = {"email": "nonexistent@test.com"}
        
        response = await self.client.post(
            f"{API_BASE}/auth/forgot-password",
            json=forgot_data_invalid
        )
        
        if response.status_code == 404:
            print(f"✅ Correctly returned 404 for nonexistent email")
            print(f"   Error: {response.json().get('detail', response.text)}")
        else:
            print(f"❌ Expected 404 but got {response.status_code}: {response.text}")
            
        # Test 2c: POST reset-password with correct email + OTP + new_password
        print("\n2c. Testing reset-password with correct OTP...")
        if not self.stored_otp:
            print("❌ No OTP available for testing")
            return False
            
        reset_data = {
            "email": "testforgot@test.com",
            "otp": self.stored_otp,
            "new_password": "newpass456"
        }
        
        response = await self.client.post(
            f"{API_BASE}/auth/reset-password",
            json=reset_data
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Password reset successful")
            print(f"   Message: {data.get('message', '')}")
        else:
            print(f"❌ Password reset failed: {response.status_code} - {response.text}")
            return False
            
        # Test 2d: POST reset-password with wrong OTP
        print("\n2d. Testing reset-password with wrong OTP...")
        wrong_reset_data = {
            "email": "testforgot@test.com",
            "otp": "999999",  # Wrong OTP
            "new_password": "anothernewpass"
        }
        
        response = await self.client.post(
            f"{API_BASE}/auth/reset-password",
            json=wrong_reset_data
        )
        
        if response.status_code == 400:
            print(f"✅ Correctly rejected wrong OTP with 400 status")
            print(f"   Error: {response.json().get('detail', response.text)}")
        else:
            print(f"❌ Expected 400 but got {response.status_code}: {response.text}")
            
        # Test 2e: Login with new password to verify reset worked
        print("\n2e. Testing login with new password...")
        login_data = {
            "email": "testforgot@test.com",
            "password": "newpass456"
        }
        
        response = await self.client.post(
            f"{API_BASE}/auth/login",
            json=login_data
        )
        
        if response.status_code == 200:
            data = response.json()
            self.session_token = data["session_token"]  # Update session token
            print(f"✅ Login with new password successful")
            print(f"   User ID: {data['user_id']}")
            print(f"   Email: {data['email']}")
            return True
        else:
            print(f"❌ Login with new password failed: {response.status_code} - {response.text}")
            return False

    async def test_set_password_flow(self):
        """Test the set password functionality"""
        print("\n=== Testing Set Password Flow ===")
        
        if not self.session_token:
            print("❌ No session token available for set password testing")
            return False
            
        headers = {"Authorization": f"Bearer {self.session_token}"}
        
        # Test 3a: Login first to ensure we have a valid session
        print("\n3a. Verifying current session...")
        response = await self.client.get(
            f"{API_BASE}/auth/me",
            headers=headers
        )
        
        if response.status_code != 200:
            print(f"❌ Session verification failed: {response.status_code} - {response.text}")
            return False
            
        print(f"✅ Session verified for user: {response.json().get('email')}")
        
        # Test 3b: POST set-password with valid password
        print("\n3b. Testing set-password with valid password...")
        set_password_data = {"new_password": "mypass123"}
        
        response = await self.client.post(
            f"{API_BASE}/auth/set-password",
            json=set_password_data,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Set password successful")
            print(f"   Message: {data.get('message', '')}")
        else:
            print(f"❌ Set password failed: {response.status_code} - {response.text}")
            return False
            
        # Test 3c: POST set-password with short password (should fail validation)
        print("\n3c. Testing set-password with short password...")
        short_password_data = {"new_password": "ab"}
        
        response = await self.client.post(
            f"{API_BASE}/auth/set-password",
            json=short_password_data,
            headers=headers
        )
        
        if response.status_code == 400:
            print(f"✅ Correctly rejected short password with 400 status")
            error_msg = response.json().get('detail', response.text)
            print(f"   Error: {error_msg}")
            if "6 characters" in error_msg:
                print(f"✅ Proper minimum length validation message")
            else:
                print(f"⚠️  Validation message doesn't mention 6 character minimum")
        else:
            print(f"❌ Expected 400 but got {response.status_code}: {response.text}")
            
        return True

    async def test_auth_me_has_password_field(self):
        """Test that /auth/me includes has_password field"""
        print("\n=== Testing /auth/me has_password Field ===")
        
        if not self.session_token:
            print("❌ No session token available for /auth/me testing")
            return False
            
        headers = {"Authorization": f"Bearer {self.session_token}"}
        
        response = await self.client.get(
            f"{API_BASE}/auth/me",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ /auth/me endpoint working")
            print(f"   User ID: {data.get('user_id')}")
            print(f"   Email: {data.get('email')}")
            print(f"   Name: {data.get('name')}")
            print(f"   Auth Method: {data.get('auth_method')}")
            
            # Check for has_password field
            if 'has_password' in data:
                has_password = data['has_password']
                print(f"✅ has_password field present: {has_password}")
                if isinstance(has_password, bool):
                    print(f"✅ has_password is boolean type as expected")
                    return True
                else:
                    print(f"⚠️  has_password is not boolean: {type(has_password)}")
                    return True
            else:
                print(f"❌ has_password field missing from /auth/me response")
                print(f"   Available fields: {list(data.keys())}")
                return False
        else:
            print(f"❌ /auth/me failed: {response.status_code} - {response.text}")
            return False

    async def run_all_tests(self):
        """Run all auth endpoint tests in sequence"""
        print("🚀 Starting Authentication Endpoints Testing")
        print(f"Backend URL: {BACKEND_URL}")
        
        tests_passed = 0
        total_tests = 4
        
        # Test 1: Register test user
        if await self.test_register_user():
            tests_passed += 1
            print("✅ User Registration: PASSED")
        else:
            print("❌ User Registration: FAILED")
            
        # Test 2: Forgot Password Flow
        if await self.test_forgot_password_flow():
            tests_passed += 1
            print("✅ Forgot Password Flow: PASSED")
        else:
            print("❌ Forgot Password Flow: FAILED")
            
        # Test 3: Set Password Flow 
        if await self.test_set_password_flow():
            tests_passed += 1
            print("✅ Set Password Flow: PASSED")
        else:
            print("❌ Set Password Flow: FAILED")
            
        # Test 4: Auth Me has_password field
        if await self.test_auth_me_has_password_field():
            tests_passed += 1
            print("✅ Auth Me has_password Field: PASSED")
        else:
            print("❌ Auth Me has_password Field: FAILED")
        
        print("\n" + "="*80)
        print("📊 FINAL AUTH ENDPOINTS TEST SUMMARY")
        print("="*80)
        print(f"Tests passed: {tests_passed}/{total_tests}")
        
        if tests_passed == total_tests:
            print("✅ ALL AUTH ENDPOINTS TESTS PASSED!")
            print("✅ Forgot Password and Set Password features working correctly")
            return True
        else:
            print("❌ Some auth endpoint tests failed")
            return False

async def main():
    """Run all authentication endpoint tests"""
    tester = AuthEndpointTester()
    
    try:
        return await tester.run_all_tests()
    except Exception as e:
        print(f"❌ Unexpected error during testing: {e}")
        return False
    finally:
        await tester.close()

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)