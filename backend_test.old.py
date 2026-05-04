"""
Backend Testing for CLD Module Refinements and ACM Verification
Tests expanded CLD module types (16 types) and ACM matrix (31 modules, 78 features)
"""

import requests
import json
import time
from datetime import datetime

# Backend URL
BASE_URL = "https://voice-browse-epic.preview.emergentagent.com/api"

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
            return None
        
        data = resp.json()
        session_token = data.get("session_token")
        
        if not session_token:
            log_test("User Registration", False, "No session_token in response")
            return None
        
        log_test("User Registration", True, f"User: {email}, Token: {session_token[:20]}...")
        return session_token
    
    except Exception as e:
        log_test("User Registration", False, f"Exception: {str(e)}")
        return None


def test_cld_module_ctt_generate(token):
    """Test POST /api/cld/module/ctt/generate - NEW module type"""
    url = f"{BASE_URL}/cld/module/ctt/generate"
    headers = {"Authorization": f"Bearer {token}"}
    body = {}
    
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=15)
        
        if resp.status_code != 200:
            return log_test("CLD Module CTT Generate", False, f"Status: {resp.status_code}, Response: {resp.text[:300]}")
        
        data = resp.json()
        
        # Verify response structure
        required_fields = ["cld_id", "user_id", "module_type", "nodes", "links"]
        missing = [f for f in required_fields if f not in data]
        
        if missing:
            return log_test("CLD Module CTT Generate", False, f"Missing fields: {missing}")
        
        if data.get("module_type") != "ctt":
            return log_test("CLD Module CTT Generate", False, f"Wrong module_type: {data.get('module_type')}")
        
        node_count = len(data.get("nodes", []))
        link_count = len(data.get("links", []))
        
        return log_test("CLD Module CTT Generate", True, 
                       f"Generated CTT CLD with {node_count} nodes, {link_count} links")
    
    except Exception as e:
        return log_test("CLD Module CTT Generate", False, f"Exception: {str(e)}")


def test_cld_module_tepfi_generate(token):
    """Test POST /api/cld/module/tepfi/generate - NEW module type"""
    url = f"{BASE_URL}/cld/module/tepfi/generate"
    headers = {"Authorization": f"Bearer {token}"}
    body = {}
    
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=15)
        
        if resp.status_code != 200:
            return log_test("CLD Module TEPFI Generate", False, f"Status: {resp.status_code}, Response: {resp.text[:300]}")
        
        data = resp.json()
        
        # Verify response structure
        if data.get("module_type") != "tepfi":
            return log_test("CLD Module TEPFI Generate", False, f"Wrong module_type: {data.get('module_type')}")
        
        node_count = len(data.get("nodes", []))
        link_count = len(data.get("links", []))
        
        return log_test("CLD Module TEPFI Generate", True, 
                       f"Generated TEPFI CLD with {node_count} nodes, {link_count} links")
    
    except Exception as e:
        return log_test("CLD Module TEPFI Generate", False, f"Exception: {str(e)}")


def test_cld_module_consciousness_generate(token):
    """Test POST /api/cld/module/consciousness/generate - NEW module type"""
    url = f"{BASE_URL}/cld/module/consciousness/generate"
    headers = {"Authorization": f"Bearer {token}"}
    body = {}
    
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=15)
        
        if resp.status_code != 200:
            return log_test("CLD Module Consciousness Generate", False, f"Status: {resp.status_code}, Response: {resp.text[:300]}")
        
        data = resp.json()
        
        # Verify response structure
        if data.get("module_type") != "consciousness":
            return log_test("CLD Module Consciousness Generate", False, f"Wrong module_type: {data.get('module_type')}")
        
        node_count = len(data.get("nodes", []))
        link_count = len(data.get("links", []))
        
        return log_test("CLD Module Consciousness Generate", True, 
                       f"Generated Consciousness CLD with {node_count} nodes, {link_count} links")
    
    except Exception as e:
        return log_test("CLD Module Consciousness Generate", False, f"Exception: {str(e)}")


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
        
        # Should have at least 3 modules (ctt, tepfi, consciousness that we just created)
        if len(data) < 3:
            return log_test("CLD List Modules", False, f"Expected at least 3 modules, got: {len(data)}")
        
        # Verify structure of first item
        if data:
            first = data[0]
            required_fields = ["cld_id", "module_type", "node_count", "link_count"]
            missing = [f for f in required_fields if f not in first]
            
            if missing:
                return log_test("CLD List Modules", False, f"Missing fields in first item: {missing}")
        
        module_types = [m.get("module_type") for m in data]
        return log_test("CLD List Modules", True, 
                       f"Found {len(data)} module CLDs: {', '.join(module_types)}")
    
    except Exception as e:
        return log_test("CLD List Modules", False, f"Exception: {str(e)}")


def test_cld_get_module_ctt(token):
    """Test GET /api/cld/module/ctt - Should return the generated CTT CLD"""
    url = f"{BASE_URL}/cld/module/ctt"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            return log_test("CLD Get Module CTT", False, f"Status: {resp.status_code}, Response: {resp.text[:300]}")
        
        data = resp.json()
        
        # Should have module_type = ctt
        if data.get("module_type") != "ctt":
            return log_test("CLD Get Module CTT", False, f"Wrong module_type: {data.get('module_type')}")
        
        # Should have nodes and links
        if "nodes" not in data or "links" not in data:
            return log_test("CLD Get Module CTT", False, "Missing nodes or links")
        
        node_count = len(data.get("nodes", []))
        link_count = len(data.get("links", []))
        
        return log_test("CLD Get Module CTT", True, 
                       f"Retrieved CTT CLD with {node_count} nodes, {link_count} links")
    
    except Exception as e:
        return log_test("CLD Get Module CTT", False, f"Exception: {str(e)}")


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
        expected_types = ["master", "decision", "ctt", "tepfi", "consciousness"]
        found_types = [t for t in expected_types if t in response_text]
        
        if len(found_types) < 3:
            return log_test("CLD Invalid Module Type Validation", False, 
                          f"Error message doesn't list valid types. Response: {resp.text[:200]}")
        
        return log_test("CLD Invalid Module Type Validation", True, 
                       f"Correctly rejected invalid module type with error message")
    
    except Exception as e:
        return log_test("CLD Invalid Module Type Validation", False, f"Exception: {str(e)}")


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
            if "conflict" in module.get("name", "").lower() and "breaker" in module.get("name", "").lower():
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
            name = module.get("name", "").lower()
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
            name = module.get("name", "").lower()
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
    print("CLD MODULE REFINEMENTS & ACM VERIFICATION TESTING")
    print("=" * 80)
    print()
    
    # Step 1: Register and login
    print("STEP 1: Authentication")
    print("-" * 80)
    token = register_and_login()
    
    if not token:
        print("\n❌ CRITICAL: Authentication failed. Cannot proceed with tests.")
        return
    
    print()
    
    # Step 2: Test CLD Module Endpoints
    print("STEP 2: CLD Module Type Expansion (16 types)")
    print("-" * 80)
    test_cld_module_ctt_generate(token)
    test_cld_module_tepfi_generate(token)
    test_cld_module_consciousness_generate(token)
    test_cld_list_modules(token)
    test_cld_get_module_ctt(token)
    test_cld_invalid_module_type(token)
    print()
    
    # Step 3: Test ACM Matrix
    print("STEP 3: ACM Verification (31 modules, 78 features)")
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
    with open("/app/test_results_cld_acm.json", "w") as f:
        json.dump({
            "summary": {
                "total": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": success_rate
            },
            "tests": test_results
        }, f, indent=2)
    
    print(f"Detailed results saved to: /app/test_results_cld_acm.json")
    print("=" * 80)


if __name__ == "__main__":
    main()
