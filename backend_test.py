"""
Backend API Testing for Emotional Reception Endpoints
Tests all Emotional Reception functionality as per review request
"""

import requests
import json
from datetime import datetime

# Backend URL from environment
BASE_URL = "https://dezider-core.preview.emergentagent.com/api"

# Test credentials
TEST_EMAIL = "reception_test@test.com"
TEST_PASSWORD = "Test123!"
TEST_NAME = "Reception Tester"

# Global session token
session_token = None


def print_test(test_name, passed, details=""):
    """Print test result with formatting"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status}: {test_name}")
    if details:
        print(f"   {details}")


def test_1_register():
    """Test 1: Register new user"""
    global session_token
    
    url = f"{BASE_URL}/auth/register"
    payload = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "name": TEST_NAME
    }
    
    try:
        response = requests.post(url, json=payload)
        data = response.json()
        
        if response.status_code == 200 and "session_token" in data:
            session_token = data["session_token"]
            print_test("User Registration", True, f"Registered {TEST_EMAIL} with session token")
            return True
        elif response.status_code == 400 and ("already" in data.get("detail", "").lower() or "registered" in data.get("detail", "").lower()):
            # User already exists, try login
            print_test("User Registration", True, f"User already exists, will login instead")
            return test_1b_login()
        else:
            print_test("User Registration", False, f"Status: {response.status_code}, Response: {data}")
            return False
    except Exception as e:
        print_test("User Registration", False, f"Exception: {str(e)}")
        return False


def test_1b_login():
    """Test 1b: Login existing user"""
    global session_token
    
    url = f"{BASE_URL}/auth/login"
    payload = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    try:
        response = requests.post(url, json=payload)
        data = response.json()
        
        if response.status_code == 200 and "session_token" in data:
            session_token = data["session_token"]
            print_test("User Login", True, f"Logged in {TEST_EMAIL}")
            return True
        else:
            print_test("User Login", False, f"Status: {response.status_code}, Response: {data}")
            return False
    except Exception as e:
        print_test("User Login", False, f"Exception: {str(e)}")
        return False


def test_2_verify_outlets():
    """Test 2: Verify outlets include Emotional Reception (outlet #10)"""
    
    url = f"{BASE_URL}/emotional-gatekeeper/advisor/outlets"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("Verify Outlets", False, f"Status: {response.status_code}")
            return False
        
        outlets = data.get("outlets", [])
        total_outlets = len(outlets)
        
        # Find emotional_reception outlet
        emotional_reception = None
        for outlet in outlets:
            if outlet.get("id") == "emotional_reception":
                emotional_reception = outlet
                break
        
        if not emotional_reception:
            print_test("Verify Outlets", False, f"Emotional Reception outlet not found. Total outlets: {total_outlets}")
            return False
        
        # Verify outlet properties
        checks = []
        checks.append(("id", emotional_reception.get("id") == "emotional_reception"))
        checks.append(("number", emotional_reception.get("number") == "10"))
        checks.append(("has_guided_flow", emotional_reception.get("has_guided_flow") == True))
        checks.append(("category", emotional_reception.get("category") == "emotional"))
        
        all_passed = all(check[1] for check in checks)
        
        if all_passed:
            details = f"Found {total_outlets} outlets including Emotional Reception (#10) with correct properties (id, number, has_guided_flow, category)"
            print_test("Verify Outlets", True, details)
            return True
        else:
            failed_checks = [check[0] for check in checks if not check[1]]
            details = f"Total outlets: {total_outlets}, Failed checks: {failed_checks}"
            print_test("Verify Outlets", False, details)
            return False
            
    except Exception as e:
        print_test("Verify Outlets", False, f"Exception: {str(e)}")
        return False


def test_3_log_completed_5min():
    """Test 3: Log Emotional Reception - Completed 5 mins"""
    
    url = f"{BASE_URL}/emotional-gatekeeper/advisor/emotional-reception/log"
    headers = {"Authorization": f"Bearer {session_token}"}
    payload = {
        "burden": "Work pressure and deadline stress",
        "wants_settled": True,
        "accepted_donts": True,
        "chose_to_be": True,
        "completed_5_min": True,
        "intensity_before": 8,
        "intensity_after": 4,
        "reflection": "I noticed the stress became lighter simply by observing it"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("Log Completed 5min", False, f"Status: {response.status_code}, Response: {data}")
            return False
        
        # Verify response structure
        logged = data.get("logged")
        eq_stats = data.get("eq_stats")
        
        if not logged or not eq_stats:
            print_test("Log Completed 5min", False, "Missing logged or eq_stats in response")
            return False
        
        # Verify eq_stats
        total_attempts = eq_stats.get("total_attempts")
        successful_completions = eq_stats.get("successful_completions")
        
        if total_attempts >= 1 and successful_completions >= 1:
            details = f"Logged successfully. EQ Stats: {total_attempts} attempts, {successful_completions} completions"
            print_test("Log Completed 5min", True, details)
            return True
        else:
            print_test("Log Completed 5min", False, f"Unexpected eq_stats: {eq_stats}")
            return False
            
    except Exception as e:
        print_test("Log Completed 5min", False, f"Exception: {str(e)}")
        return False


def test_4_log_not_completed():
    """Test 4: Log Emotional Reception - Did NOT complete"""
    
    url = f"{BASE_URL}/emotional-gatekeeper/advisor/emotional-reception/log"
    headers = {"Authorization": f"Bearer {session_token}"}
    payload = {
        "burden": "Argument with partner",
        "wants_settled": True,
        "accepted_donts": True,
        "chose_to_be": True,
        "completed_5_min": False,
        "intensity_before": 9,
        "intensity_after": 7
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("Log NOT Completed", False, f"Status: {response.status_code}, Response: {data}")
            return False
        
        eq_stats = data.get("eq_stats")
        
        if not eq_stats:
            print_test("Log NOT Completed", False, "Missing eq_stats in response")
            return False
        
        total_attempts = eq_stats.get("total_attempts")
        successful_completions = eq_stats.get("successful_completions")
        
        # Should have 2 attempts, 1 completion (from previous test)
        if total_attempts >= 2 and successful_completions >= 1:
            details = f"Logged successfully. EQ Stats: {total_attempts} attempts, {successful_completions} completions"
            print_test("Log NOT Completed", True, details)
            return True
        else:
            print_test("Log NOT Completed", False, f"Unexpected eq_stats: {eq_stats}")
            return False
            
    except Exception as e:
        print_test("Log NOT Completed", False, f"Exception: {str(e)}")
        return False


def test_5_log_chose_not_to_wait():
    """Test 5: Log Emotional Reception - Chose NOT to wait"""
    
    url = f"{BASE_URL}/emotional-gatekeeper/advisor/emotional-reception/log"
    headers = {"Authorization": f"Bearer {session_token}"}
    payload = {
        "burden": "Financial anxiety",
        "wants_settled": True,
        "accepted_donts": True,
        "chose_to_be": False,
        "intensity_before": 6
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("Log Chose NOT to Wait", False, f"Status: {response.status_code}, Response: {data}")
            return False
        
        eq_stats = data.get("eq_stats")
        
        if not eq_stats:
            print_test("Log Chose NOT to Wait", False, "Missing eq_stats in response")
            return False
        
        total_attempts = eq_stats.get("total_attempts")
        
        # Should have 3 attempts now
        if total_attempts >= 3:
            details = f"Logged successfully. Total attempts: {total_attempts}"
            print_test("Log Chose NOT to Wait", True, details)
            return True
        else:
            print_test("Log Chose NOT to Wait", False, f"Expected 3+ attempts, got {total_attempts}")
            return False
            
    except Exception as e:
        print_test("Log Chose NOT to Wait", False, f"Exception: {str(e)}")
        return False


def test_6_get_history():
    """Test 6: Get Emotional Reception History"""
    
    url = f"{BASE_URL}/emotional-gatekeeper/advisor/emotional-reception/history"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("Get History", False, f"Status: {response.status_code}, Response: {data}")
            return False
        
        logs = data.get("logs", [])
        eq_stats = data.get("eq_stats")
        
        if not eq_stats:
            print_test("Get History", False, "Missing eq_stats in response")
            return False
        
        total_attempts = eq_stats.get("total_attempts")
        successful_completions = eq_stats.get("successful_completions")
        completion_rate = eq_stats.get("completion_rate")
        
        # Should have 3 logs, 1 successful completion
        if len(logs) >= 3 and total_attempts >= 3 and successful_completions >= 1:
            details = f"Found {len(logs)} logs. EQ Stats: {total_attempts} attempts, {successful_completions} completions, {completion_rate}% completion rate"
            print_test("Get History", True, details)
            return True
        else:
            details = f"Logs: {len(logs)}, Attempts: {total_attempts}, Completions: {successful_completions}"
            print_test("Get History", False, details)
            return False
            
    except Exception as e:
        print_test("Get History", False, f"Exception: {str(e)}")
        return False


def test_7_verify_practice_logged():
    """Test 7: Verify practice was auto-logged"""
    
    url = f"{BASE_URL}/emotional-gatekeeper/advisor/my-practices"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("Verify Practice Auto-logged", False, f"Status: {response.status_code}, Response: {data}")
            return False
        
        logs = data.get("logs", [])
        
        # Filter for emotional_reception practices
        er_practices = [log for log in logs if log.get("outlet_id") == "emotional_reception"]
        
        if len(er_practices) >= 3:
            details = f"Found {len(er_practices)} emotional_reception practice logs (expected 3+)"
            print_test("Verify Practice Auto-logged", True, details)
            return True
        else:
            details = f"Found {len(er_practices)} emotional_reception practices, expected 3+"
            print_test("Verify Practice Auto-logged", False, details)
            return False
            
    except Exception as e:
        print_test("Verify Practice Auto-logged", False, f"Exception: {str(e)}")
        return False


def run_all_tests():
    """Run all Emotional Reception tests"""
    print("=" * 80)
    print("EMOTIONAL RECEPTION ENDPOINTS TESTING")
    print("=" * 80)
    print(f"Backend URL: {BASE_URL}")
    print(f"Test User: {TEST_EMAIL}")
    print("=" * 80)
    
    results = []
    
    # Test 1: Authentication
    results.append(("Authentication", test_1_register()))
    
    if not session_token:
        print("\n❌ CRITICAL: Authentication failed. Cannot proceed with other tests.")
        return
    
    # Test 2: Verify outlets
    results.append(("Verify Outlets", test_2_verify_outlets()))
    
    # Test 3: Log completed 5 min
    results.append(("Log Completed 5min", test_3_log_completed_5min()))
    
    # Test 4: Log not completed
    results.append(("Log NOT Completed", test_4_log_not_completed()))
    
    # Test 5: Log chose not to wait
    results.append(("Log Chose NOT to Wait", test_5_log_chose_not_to_wait()))
    
    # Test 6: Get history
    results.append(("Get History", test_6_get_history()))
    
    # Test 7: Verify practice auto-logged
    results.append(("Verify Practice Auto-logged", test_7_verify_practice_logged()))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("=" * 80)
    print(f"TOTAL: {passed}/{total} tests passed ({round(passed/total*100, 1)}%)")
    print("=" * 80)
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
