"""
Backend API Testing for Admin Documentation Hub
Tests all admin docs endpoints with proper authentication flow
"""

import requests
import json
import time
from datetime import datetime

# Backend URL
BASE_URL = "https://dezider-core.preview.emergentagent.com/api"

# Test results tracking
test_results = []

def log_test(test_name, passed, details=""):
    """Log test result"""
    status = "✅ PASSED" if passed else "❌ FAILED"
    result = f"{status}: {test_name}"
    if details:
        result += f" — {details}"
    print(result)
    test_results.append({"test": test_name, "passed": passed, "details": details})
    return passed

def test_admin_docs_hub():
    """Test Admin Documentation Hub endpoints"""
    print("\n" + "="*80)
    print("ADMIN DOCUMENTATION HUB TESTING")
    print("="*80 + "\n")
    
    # Generate unique test user email
    timestamp = int(time.time())
    test_email = f"admindocs_{timestamp}@test.com"
    test_password = "SecurePass123!"
    test_name = "Admin Docs Tester"
    
    session_token = None
    user_id = None
    
    # ========================
    # TEST 1: User Registration
    # ========================
    print("\n[TEST 1] User Registration")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json={
                "email": test_email,
                "password": test_password,
                "name": test_name
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            session_token = data.get("session_token")
            user_id = data.get("user_id")
            log_test("User Registration", True, f"User created: {test_email}")
        else:
            log_test("User Registration", False, f"Status: {response.status_code}, Response: {response.text}")
            return
    except Exception as e:
        log_test("User Registration", False, f"Exception: {str(e)}")
        return
    
    # ========================
    # TEST 2: User Login
    # ========================
    print("\n[TEST 2] User Login")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": test_email,
                "password": test_password
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            session_token = data.get("session_token")
            log_test("User Login", True, f"Login successful, token: {session_token[:20]}...")
        else:
            log_test("User Login", False, f"Status: {response.status_code}")
            return
    except Exception as e:
        log_test("User Login", False, f"Exception: {str(e)}")
        return
    
    # Headers for authenticated requests
    headers = {"Authorization": f"Bearer {session_token}"}
    
    # ========================
    # TEST 3: Admin Setup (First Admin) or Manual Promotion
    # ========================
    print("\n[TEST 3] Admin Setup / Manual Promotion")
    
    # First try admin/setup
    try:
        response = requests.post(
            f"{BASE_URL}/admin/setup",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            log_test("Admin Setup", True, "Admin user created successfully")
        elif response.status_code == 400:
            # Super admin already exists, need to manually promote via MongoDB
            log_test("Admin Setup", True, "Super admin already exists")
            print("   Attempting manual MongoDB promotion...")
            
            # Use MongoDB to promote user
            import subprocess
            result = subprocess.run([
                "python", "-c",
                f"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path('/app/backend/.env'))
mongo_url = os.getenv('MONGO_URL')
db_name = os.getenv('DB_NAME')

async def promote():
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    result = await db.users.update_one(
        {{'email': '{test_email}'}},
        {{'$set': {{'role': 'admin'}}}}
    )
    print(f'Modified: {{result.modified_count}}')
    client.close()

asyncio.run(promote())
"""
            ], capture_output=True, text=True, cwd="/app/backend")
            
            if "Modified: 1" in result.stdout:
                log_test("Manual Admin Promotion", True, "User promoted to admin via MongoDB")
            else:
                log_test("Manual Admin Promotion", False, f"MongoDB promotion failed: {result.stdout} {result.stderr}")
        else:
            log_test("Admin Setup", False, f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        log_test("Admin Setup", False, f"Exception: {str(e)}")
    
    # ========================
    # TEST 4: GET /api/admin/docs/api-catalog (Full Catalog)
    # ========================
    print("\n[TEST 4] GET /api/admin/docs/api-catalog (Full Catalog)")
    try:
        response = requests.get(
            f"{BASE_URL}/admin/docs/api-catalog",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            total_endpoints = data.get("total_endpoints", 0)
            endpoints = data.get("endpoints", [])
            available_channels = data.get("available_channels", [])
            
            # Validate structure
            has_total = "total_endpoints" in data
            has_endpoints = "endpoints" in data and isinstance(endpoints, list)
            has_channels = "available_channels" in data and isinstance(available_channels, list)
            
            # Check if we have expected channels
            expected_channels = ["internal", "chatbot", "ivr", "partner"]
            channels_match = set(available_channels) == set(expected_channels)
            
            # Check if endpoints have required fields
            sample_endpoint = endpoints[0] if endpoints else {}
            has_required_fields = all(
                field in sample_endpoint 
                for field in ["method", "path", "summary", "category", "channels"]
            )
            
            if has_total and has_endpoints and has_channels and channels_match and has_required_fields:
                log_test(
                    "API Catalog Full", 
                    True, 
                    f"Total endpoints: {total_endpoints}, Channels: {available_channels}"
                )
                
                # Additional validation: Check for channel diversity
                chatbot_count = sum(1 for ep in endpoints if "chatbot" in ep.get("channels", []))
                partner_count = sum(1 for ep in endpoints if "partner" in ep.get("channels", []))
                ivr_count = sum(1 for ep in endpoints if "ivr" in ep.get("channels", []))
                
                print(f"   Channel distribution: chatbot={chatbot_count}, partner={partner_count}, ivr={ivr_count}")
            else:
                log_test("API Catalog Full", False, "Missing required fields or incorrect structure")
        elif response.status_code == 403:
            log_test("API Catalog Full", False, "403 Forbidden - User not admin. Need to promote user first.")
        else:
            log_test("API Catalog Full", False, f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        log_test("API Catalog Full", False, f"Exception: {str(e)}")
    
    # ========================
    # TEST 5: GET /api/admin/docs/api-catalog?channel=chatbot
    # ========================
    print("\n[TEST 5] GET /api/admin/docs/api-catalog?channel=chatbot")
    try:
        response = requests.get(
            f"{BASE_URL}/admin/docs/api-catalog?channel=chatbot",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            endpoints = data.get("endpoints", [])
            
            # Validate all endpoints have "chatbot" in channels
            all_have_chatbot = all("chatbot" in ep.get("channels", []) for ep in endpoints)
            
            if all_have_chatbot and len(endpoints) > 0:
                log_test(
                    "API Catalog Chatbot Filter", 
                    True, 
                    f"Filtered to {len(endpoints)} chatbot endpoints"
                )
            else:
                log_test("API Catalog Chatbot Filter", False, "Not all endpoints have chatbot channel")
        elif response.status_code == 403:
            log_test("API Catalog Chatbot Filter", False, "403 Forbidden - User not admin")
        else:
            log_test("API Catalog Chatbot Filter", False, f"Status: {response.status_code}")
    except Exception as e:
        log_test("API Catalog Chatbot Filter", False, f"Exception: {str(e)}")
    
    # ========================
    # TEST 6: GET /api/admin/docs/api-catalog?channel=ivr
    # ========================
    print("\n[TEST 6] GET /api/admin/docs/api-catalog?channel=ivr")
    try:
        response = requests.get(
            f"{BASE_URL}/admin/docs/api-catalog?channel=ivr",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            endpoints = data.get("endpoints", [])
            
            # Validate all endpoints have "ivr" in channels
            all_have_ivr = all("ivr" in ep.get("channels", []) for ep in endpoints)
            
            if all_have_ivr and len(endpoints) > 0:
                log_test(
                    "API Catalog IVR Filter", 
                    True, 
                    f"Filtered to {len(endpoints)} IVR endpoints"
                )
            else:
                log_test("API Catalog IVR Filter", False, "Not all endpoints have IVR channel")
        elif response.status_code == 403:
            log_test("API Catalog IVR Filter", False, "403 Forbidden - User not admin")
        else:
            log_test("API Catalog IVR Filter", False, f"Status: {response.status_code}")
    except Exception as e:
        log_test("API Catalog IVR Filter", False, f"Exception: {str(e)}")
    
    # ========================
    # TEST 7: GET /api/admin/docs/api-catalog?channel=partner
    # ========================
    print("\n[TEST 7] GET /api/admin/docs/api-catalog?channel=partner")
    try:
        response = requests.get(
            f"{BASE_URL}/admin/docs/api-catalog?channel=partner",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            endpoints = data.get("endpoints", [])
            
            # Validate all endpoints have "partner" in channels
            all_have_partner = all("partner" in ep.get("channels", []) for ep in endpoints)
            
            if all_have_partner and len(endpoints) > 0:
                log_test(
                    "API Catalog Partner Filter", 
                    True, 
                    f"Filtered to {len(endpoints)} partner endpoints"
                )
            else:
                log_test("API Catalog Partner Filter", False, "Not all endpoints have partner channel")
        elif response.status_code == 403:
            log_test("API Catalog Partner Filter", False, "403 Forbidden - User not admin")
        else:
            log_test("API Catalog Partner Filter", False, f"Status: {response.status_code}")
    except Exception as e:
        log_test("API Catalog Partner Filter", False, f"Exception: {str(e)}")
    
    # ========================
    # TEST 8: GET /api/admin/docs/prd (Before Generation)
    # ========================
    print("\n[TEST 8] GET /api/admin/docs/prd (Before Generation)")
    try:
        response = requests.get(
            f"{BASE_URL}/admin/docs/prd",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            doc_type = data.get("doc_type")
            content = data.get("content")
            generated_at = data.get("generated_at")
            
            # Should return null content before generation
            if doc_type == "prd" and content is None and generated_at is None:
                log_test("Get PRD Before Generation", True, "Returns null content as expected")
            else:
                log_test("Get PRD Before Generation", True, f"PRD already exists (content length: {len(content) if content else 0})")
        elif response.status_code == 403:
            log_test("Get PRD Before Generation", False, "403 Forbidden - User not admin")
        else:
            log_test("Get PRD Before Generation", False, f"Status: {response.status_code}")
    except Exception as e:
        log_test("Get PRD Before Generation", False, f"Exception: {str(e)}")
    
    # ========================
    # TEST 9: POST /api/admin/docs/refresh/prd (AI Generation)
    # ========================
    print("\n[TEST 9] POST /api/admin/docs/refresh/prd (AI Generation - 60s timeout)")
    print("   ⏳ This may take 15-30 seconds due to LLM processing...")
    try:
        response = requests.post(
            f"{BASE_URL}/admin/docs/refresh/prd",
            headers=headers,
            timeout=60  # 60 second timeout for LLM call
        )
        
        if response.status_code == 200:
            data = response.json()
            doc_type = data.get("doc_type")
            content = data.get("content")
            generated_at = data.get("generated_at")
            generated_by = data.get("generated_by")
            
            # Validate response structure
            has_content = content is not None and len(content) > 100
            has_timestamp = generated_at is not None
            has_generator = generated_by is not None
            
            if doc_type == "prd" and has_content and has_timestamp and has_generator:
                log_test(
                    "Refresh PRD", 
                    True, 
                    f"Generated {len(content)} chars by {generated_by}"
                )
            else:
                log_test("Refresh PRD", False, "Missing required fields in response")
        elif response.status_code == 403:
            log_test("Refresh PRD", False, "403 Forbidden - User not admin")
        else:
            log_test("Refresh PRD", False, f"Status: {response.status_code}, Response: {response.text}")
    except requests.exceptions.Timeout:
        log_test("Refresh PRD", False, "Request timeout (>60s)")
    except Exception as e:
        log_test("Refresh PRD", False, f"Exception: {str(e)}")
    
    # ========================
    # TEST 10: GET /api/admin/docs/prd (After Generation)
    # ========================
    print("\n[TEST 10] GET /api/admin/docs/prd (After Generation)")
    try:
        response = requests.get(
            f"{BASE_URL}/admin/docs/prd",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("content")
            
            if content and len(content) > 100:
                log_test("Get PRD After Generation", True, f"Retrieved generated PRD ({len(content)} chars)")
            else:
                log_test("Get PRD After Generation", False, "Content not found or too short")
        elif response.status_code == 403:
            log_test("Get PRD After Generation", False, "403 Forbidden - User not admin")
        else:
            log_test("Get PRD After Generation", False, f"Status: {response.status_code}")
    except Exception as e:
        log_test("Get PRD After Generation", False, f"Exception: {str(e)}")
    
    # ========================
    # TEST 11: POST /api/admin/docs/refresh/regression_tests
    # ========================
    print("\n[TEST 11] POST /api/admin/docs/refresh/regression_tests (60s timeout)")
    print("   ⏳ This may take 15-30 seconds due to LLM processing...")
    try:
        response = requests.post(
            f"{BASE_URL}/admin/docs/refresh/regression_tests",
            headers=headers,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            doc_type = data.get("doc_type")
            content = data.get("content")
            
            if doc_type == "regression_tests" and content and len(content) > 100:
                log_test(
                    "Refresh Regression Tests", 
                    True, 
                    f"Generated {len(content)} chars"
                )
            else:
                log_test("Refresh Regression Tests", False, "Missing content or incorrect doc_type")
        elif response.status_code == 403:
            log_test("Refresh Regression Tests", False, "403 Forbidden - User not admin")
        else:
            log_test("Refresh Regression Tests", False, f"Status: {response.status_code}")
    except requests.exceptions.Timeout:
        log_test("Refresh Regression Tests", False, "Request timeout (>60s)")
    except Exception as e:
        log_test("Refresh Regression Tests", False, f"Exception: {str(e)}")
    
    # ========================
    # TEST 12: GET /api/admin/docs/regression_tests
    # ========================
    print("\n[TEST 12] GET /api/admin/docs/regression_tests")
    try:
        response = requests.get(
            f"{BASE_URL}/admin/docs/regression_tests",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("content")
            
            if content and len(content) > 100:
                log_test("Get Regression Tests", True, f"Retrieved tests ({len(content)} chars)")
            else:
                log_test("Get Regression Tests", False, "Content not found or too short")
        elif response.status_code == 403:
            log_test("Get Regression Tests", False, "403 Forbidden - User not admin")
        else:
            log_test("Get Regression Tests", False, f"Status: {response.status_code}")
    except Exception as e:
        log_test("Get Regression Tests", False, f"Exception: {str(e)}")
    
    # ========================
    # TEST 13: POST /api/admin/docs/refresh/invalid_type (Should Fail)
    # ========================
    print("\n[TEST 13] POST /api/admin/docs/refresh/invalid_type (Should Return 400)")
    try:
        response = requests.post(
            f"{BASE_URL}/admin/docs/refresh/invalid_type",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 400:
            data = response.json()
            detail = data.get("detail", "")
            if "Invalid doc_type" in detail:
                log_test("Invalid Doc Type", True, "Correctly rejected with 400")
            else:
                log_test("Invalid Doc Type", False, f"400 but wrong error message: {detail}")
        else:
            log_test("Invalid Doc Type", False, f"Expected 400, got {response.status_code}")
    except Exception as e:
        log_test("Invalid Doc Type", False, f"Exception: {str(e)}")
    
    # ========================
    # TEST 14: Non-Admin Access Test
    # ========================
    print("\n[TEST 14] Non-Admin Access Test")
    # Create a new regular user
    timestamp2 = int(time.time()) + 1
    regular_email = f"regular_{timestamp2}@test.com"
    
    try:
        # Register regular user
        reg_response = requests.post(
            f"{BASE_URL}/auth/register",
            json={
                "email": regular_email,
                "password": "RegularPass123!",
                "name": "Regular User"
            },
            timeout=30
        )
        
        if reg_response.status_code == 200:
            regular_token = reg_response.json().get("session_token")
            regular_headers = {"Authorization": f"Bearer {regular_token}"}
            
            # Try to access admin endpoint
            access_response = requests.get(
                f"{BASE_URL}/admin/docs/api-catalog",
                headers=regular_headers,
                timeout=30
            )
            
            if access_response.status_code == 403:
                log_test("Non-Admin Access Control", True, "Regular user correctly denied with 403")
            else:
                log_test("Non-Admin Access Control", False, f"Expected 403, got {access_response.status_code}")
        else:
            log_test("Non-Admin Access Control", False, "Failed to create regular user")
    except Exception as e:
        log_test("Non-Admin Access Control", False, f"Exception: {str(e)}")
    
    # ========================
    # SUMMARY
    # ========================
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for r in test_results if r["passed"])
    total = len(test_results)
    percentage = (passed / total * 100) if total > 0 else 0
    
    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {percentage:.1f}%\n")
    
    # List failed tests
    failed_tests = [r for r in test_results if not r["passed"]]
    if failed_tests:
        print("Failed Tests:")
        for test in failed_tests:
            print(f"  ❌ {test['test']}: {test['details']}")
    else:
        print("🎉 All tests passed!")
    
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    test_admin_docs_hub()
