"""
Backend Testing for CLD Module Refinements and ACM Verification (V2)
Tests expanded CLD module types (16 types) and ACM matrix (31 modules, 78 features)
This version seeds ACM first and tests without LLM calls
"""

import requests
import json
import time
from datetime import datetime

# Backend URL
BASE_URL = "https://repo-blueprint-1.preview.emergentagent.com/api"

# Test results
test_results = []

def log_test(test_name, passed, details=""):
    """Log test result"""
    status = "✅ PASSED" if passed else "❌ FAILED"
    result = {
        "test": test_name,
        "status": status,
        "passed": passed,
        "details": details,
        "timestamp": datetime.now().isoformat()
    }
    test_results.append(result)
    print(f"{status}: {test_name}")
    if details:
        print(f"  Details: {details}")
    return passed


def register_and_login():
    """Register a new user and get session token"""
    timestamp = int(time.time())
    email = f"expand_test_{timestamp}@test.com"
    password = "test123456"
    name = "CLD Expand Test"
    
    # Register
    register_url = f"{BASE_URL}/auth/register"
    register_data = {
        "email": email,
        "password": password,
        "name": name
    }
    
    try:
        resp = requests.post(register_url, json=register_data, timeout=10)
        if resp.status_code != 200:
            log_test("User Registration", False, f"Status: {resp.status_code}, Response: {resp.text[:200]}")
            return None, None
        
        data = resp.json()
        session_token = data.get("session_token")
        user_id = data.get("user_id")
        
        if not session_token:
            log_test("User Registration", False, "No session_token in response")
            return None, None
        
        log_test("User Registration", True, f"User: {email}, Token: {session_token[:20]}...")
        return session_token, user_id
    
    except Exception as e:
        log_test("User Registration", False, f"Exception: {str(e)}")
        return None, None


def make_user_admin(user_id):
    """Make user an admin by directly updating MongoDB"""
    try:
        # Use MongoDB to update user role
        import subprocess
        cmd = f"""mongosh mongodb://localhost:27017/test_database --quiet --eval 'db.users.updateOne({{user_id: "{user_id}"}}, {{$set: {{role: "super_admin"}}}})' """
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            log_test("Make User Admin", True, f"User {user_id} promoted to super_admin")
            return True
        else:
            log_test("Make User Admin", False, f"Failed to promote user: {result.stderr}")
            return False
    except Exception as e:
        log_test("Make User Admin", False, f"Exception: {str(e)}")
        return False


def seed_acm(token):
    """Seed ACM data"""
    url = f"{BASE_URL}/acm/seed"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.post(url, headers=headers, params={"force": True}, timeout=10)
        
        if resp.status_code != 200:
            return log_test("ACM Seed", False, f"Status: {resp.status_code}, Response: {resp.text[:300]}")
        
        data = resp.json()
        modules = data.get("modules", 0)
        features = data.get("features", 0)
        
        return log_test("ACM Seed", True, f"Seeded {modules} modules, {features} features")
    
    except Exception as e:
        return log_test("ACM Seed", False, f"Exception: {str(e)}")


def test_cld_invalid_module_type(token):
    """Test POST /api/cld/module/invalid_type/generate - Should return 400 error with valid types list"""
    url = f"{BASE_URL}/cld/module/invalid_type/generate"
    headers = {"Authorization": f"Bearer {token}"}
    body = {}
    
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=10)
        
        # Should return 400 error
        if resp.status_code != 400:
            return log_test("CLD Invalid Module Type Validation", False, 
                          f"Expected 400, got: {resp.status_code}")
        
        # Response should contain list of valid types
        response_text = resp.text.lower()
        
        # Check if response mentions valid module types
        expected_types = ["master", "decision", "ctt", "tepfi", "consciousness", "ai_assistant", "meditation"]
        found_types = [t for t in expected_types if t in response_text]
        
        if len(found_types) < 5:
            return log_test("CLD Invalid Module Type Validation", False, 
                          f"Error message doesn't list enough valid types. Found: {found_types}. Response: {resp.text[:200]}")
        
        return log_test("CLD Invalid Module Type Validation", True, 
                       f"Correctly rejected invalid module type. Found {len(found_types)} valid types in error message")
    
    except Exception as e:
        return log_test("CLD Invalid Module Type Validation", False, f"Exception: {str(e)}")


def test_cld_list_modules(token):
    """Test GET /api/cld/list-modules - routing was previously broken, now fixed"""
    url = f"{BASE_URL}/cld/list-modules"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return log_test("CLD List Modules", False, f"Status: {resp.status_code}, Response: {resp.text[:300]}")
        
        data = resp.json()
        
        # Should return an array
        if not isinstance(data, list):
            return log_test("CLD List Modules", False, f"Expected array, got: {type(data)}")
        
        # For new user, should be empty or have modules
        # The important thing is the endpoint works and returns an array
        return log_test("CLD List Modules", True, 
                       f"Endpoint working correctly. Found {len(data)} module CLDs (expected 0 for new user)")
    
    except Exception as e:
        return log_test("CLD List Modules", False, f"Exception: {str(e)}")


def test_acm_matrix(token):
    """Test GET /api/acm/matrix - Should return 31 modules and 78 features"""
    url = f"{BASE_URL}/acm/matrix"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return log_test("ACM Matrix", False, f"Status: {resp.status_code}, Response: {resp.text[:300]}")
        
        data = resp.json()
        
        # Verify structure
        required_fields = ["modules", "total_modules", "total_features"]
        missing = [f for f in required_fields if f not in data]
        
        if missing:
            return log_test("ACM Matrix", False, f"Missing fields: {missing}")
        
        total_modules = data.get("total_modules", 0)
        total_features = data.get("total_features", 0)
        
        # Verify counts
        if total_modules != 31:
            return log_test("ACM Matrix", False, 
                          f"Expected 31 modules, got: {total_modules}")
        
        if total_features != 78:
            return log_test("ACM Matrix", False, 
                          f"Expected 78 features, got: {total_features}")
        
        return log_test("ACM Matrix", True, 
                       f"Verified: {total_modules} modules, {total_features} features")
    
    except Exception as e:
        return log_test("ACM Matrix", False, f"Exception: {str(e)}")


def test_acm_conflict_breaker_module(token):
    """Verify ACM contains 'The Conflict Breaker' module with 4 features"""
    url = f"{BASE_URL}/acm/matrix"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return log_test("ACM Conflict Breaker Module", False, f"Status: {resp.status_code}")
        
        data = resp.json()
        modules = data.get("modules", [])
        
        # Find Conflict Breaker module
        cb_module = None
        for module in modules:
            if "conflict" in module.get("module_name", "").lower() and "breaker" in module.get("module_name", "").lower():
                cb_module = module
                break
        
        if not cb_module:
            return log_test("ACM Conflict Breaker Module", False, 
                          "Module 'The Conflict Breaker' not found in ACM")
        
        features = cb_module.get("features", [])
        feature_count = len(features)
        
        if feature_count != 4:
            return log_test("ACM Conflict Breaker Module", False, 
                          f"Expected 4 features, got: {feature_count}")
        
        # Verify expected features
        expected_features = ["cb_sessions", "cb_9_stage_wizard", "cb_ai_script_rewrite", "cb_dashboard"]
        feature_ids = [f.get("feature_id", "") for f in features]
        
        found_features = [f for f in expected_features if f in feature_ids]
        
        if len(found_features) < 3:
            return log_test("ACM Conflict Breaker Module", False, 
                          f"Expected features not found. Got: {feature_ids}")
        
        return log_test("ACM Conflict Breaker Module", True, 
                       f"Verified: {feature_count} features - {', '.join(feature_ids)}")
    
    except Exception as e:
        return log_test("ACM Conflict Breaker Module", False, f"Exception: {str(e)}")


def test_acm_ai_assistant_module(token):
    """Verify ACM contains 'AI Solution Assistant' module with 4 features"""
    url = f"{BASE_URL}/acm/matrix"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return log_test("ACM AI Solution Assistant Module", False, f"Status: {resp.status_code}")
        
        data = resp.json()
        modules = data.get("modules", [])
        
        # Find AI Solution Assistant module
        ai_module = None
        for module in modules:
            name = module.get("module_name", "").lower()
            if "ai" in name and ("solution" in name or "assistant" in name):
                ai_module = module
                break
        
        if not ai_module:
            return log_test("ACM AI Solution Assistant Module", False, 
                          "Module 'AI Solution Assistant' not found in ACM")
        
        features = ai_module.get("features", [])
        feature_count = len(features)
        
        if feature_count != 4:
            return log_test("ACM AI Solution Assistant Module", False, 
                          f"Expected 4 features, got: {feature_count}")
        
        # Verify expected features
        expected_features = ["ai_assistant_conversations", "ai_assistant_quick_ask", 
                           "ai_assistant_tts", "ai_assistant_cross_module"]
        feature_ids = [f.get("feature_id", "") for f in features]
        
        found_features = [f for f in expected_features if f in feature_ids]
        
        if len(found_features) < 3:
            return log_test("ACM AI Solution Assistant Module", False, 
                          f"Expected features not found. Got: {feature_ids}")
        
        return log_test("ACM AI Solution Assistant Module", True, 
                       f"Verified: {feature_count} features - {', '.join(feature_ids)}")
    
    except Exception as e:
        return log_test("ACM AI Solution Assistant Module", False, f"Exception: {str(e)}")


def test_acm_cld_engine_module(token):
    """Verify ACM contains 'CLD Engine' module with 4 features"""
    url = f"{BASE_URL}/acm/matrix"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return log_test("ACM CLD Engine Module", False, f"Status: {resp.status_code}")
        
        data = resp.json()
        modules = data.get("modules", [])
        
        # Find CLD Engine module
        cld_module = None
        for module in modules:
            name = module.get("module_name", "").lower()
            if "cld" in name and "engine" in name:
                cld_module = module
                break
        
        if not cld_module:
            return log_test("ACM CLD Engine Module", False, 
                          "Module 'CLD Engine' not found in ACM")
        
        features = cld_module.get("features", [])
        feature_count = len(features)
        
        if feature_count != 4:
            return log_test("ACM CLD Engine Module", False, 
                          f"Expected 4 features, got: {feature_count}")
        
        # Verify expected features
        expected_features = ["cld_viewer", "cld_module_generate", "cld_master_generate", "cld_simulation"]
        feature_ids = [f.get("feature_id", "") for f in features]
        
        found_features = [f for f in expected_features if f in feature_ids]
        
        if len(found_features) < 3:
            return log_test("ACM CLD Engine Module", False, 
                          f"Expected features not found. Got: {feature_ids}")
        
        return log_test("ACM CLD Engine Module", True, 
                       f"Verified: {feature_count} features - {', '.join(feature_ids)}")
    
    except Exception as e:
        return log_test("ACM CLD Engine Module", False, f"Exception: {str(e)}")


def main():
    """Run all tests"""
    print("=" * 80)
    print("CLD MODULE REFINEMENTS & ACM VERIFICATION TESTING (V2)")
    print("=" * 80)
    print()
    
    # Step 1: Register and login
    print("STEP 1: Authentication")
    print("-" * 80)
    token, user_id = register_and_login()
    
    if not token:
        print("\n❌ CRITICAL: Authentication failed. Cannot proceed with tests.")
        return
    
    print()
    
    # Step 2: Make user admin
    print("STEP 2: Admin Setup")
    print("-" * 80)
    if not make_user_admin(user_id):
        print("\n⚠️  WARNING: Could not promote user to admin. ACM tests may fail.")
    print()
    
    # Step 3: Seed ACM
    print("STEP 3: ACM Seed")
    print("-" * 80)
    seed_acm(token)
    print()
    
    # Step 4: Test CLD Module Endpoints (without LLM calls)
    print("STEP 4: CLD Module Type Validation")
    print("-" * 80)
    test_cld_invalid_module_type(token)
    test_cld_list_modules(token)
    print()
    
    # Step 5: Test ACM Matrix
    print("STEP 5: ACM Verification (31 modules, 78 features)")
    print("-" * 80)
    test_acm_matrix(token)
    test_acm_conflict_breaker_module(token)
    test_acm_ai_assistant_module(token)
    test_acm_cld_engine_module(token)
    print()
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for t in test_results if t["passed"])
    failed_tests = total_tests - passed_tests
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {failed_tests} ❌")
    print(f"Success Rate: {success_rate:.1f}%")
    print()
    
    if failed_tests > 0:
        print("FAILED TESTS:")
        print("-" * 80)
        for result in test_results:
            if not result["passed"]:
                print(f"❌ {result['test']}")
                print(f"   {result['details']}")
        print()
    
    # Save results to file
    with open("/app/test_results_cld_acm_v2.json", "w") as f:
        json.dump({
            "summary": {
                "total": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": success_rate
            },
            "tests": test_results
        }, f, indent=2)
    
    print(f"Detailed results saved to: /app/test_results_cld_acm_v2.json")
    print("=" * 80)


if __name__ == "__main__":
    main()
