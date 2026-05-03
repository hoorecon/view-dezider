"""
Backend API Testing for Effective Outlets Advisor Endpoints
Testing all endpoints on https://dezider-core.preview.emergentagent.com/api
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "https://dezider-core.preview.emergentagent.com/api"
TEST_USER = {
    "email": "advisor_test@test.com",
    "password": "Test123!",
    "name": "Advisor Tester"
}

# Global variables
session_token = None
test_results = []


def log_test(test_name, passed, details=""):
    """Log test result"""
    status = "✅ PASSED" if passed else "❌ FAILED"
    result = f"{status}: {test_name}"
    if details:
        result += f" - {details}"
    test_results.append(result)
    print(result)


def test_1_register_user():
    """Test 1: Register a new test user"""
    global session_token
    
    url = f"{BASE_URL}/auth/register"
    response = requests.post(url, json=TEST_USER)
    
    if response.status_code == 200:
        data = response.json()
        session_token = data.get("session_token")
        log_test("User Registration", True, f"Registered with session_token")
        return True
    else:
        log_test("User Registration", False, f"Status: {response.status_code}, Response: {response.text}")
        return False


def test_2_get_all_outlets():
    """Test 2: GET /api/emotional-gatekeeper/advisor/outlets"""
    url = f"{BASE_URL}/emotional-gatekeeper/advisor/outlets"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        outlets = data.get("outlets", [])
        forgiveness = data.get("forgiveness_affirmations", [])
        
        # Verify outlets count
        if len(outlets) != 9:
            log_test("Get All Outlets - Count", False, f"Expected 9 outlets, got {len(outlets)}")
            return False
        
        # Verify forgiveness affirmations count
        if len(forgiveness) != 7:
            log_test("Get All Outlets - Forgiveness Count", False, f"Expected 7 categories, got {len(forgiveness)}")
            return False
        
        # Verify outlet structure
        required_fields = ["id", "number", "name", "category", "relief_type", "duration", "instructions", "description"]
        for outlet in outlets:
            for field in required_fields:
                if field not in outlet:
                    log_test("Get All Outlets - Structure", False, f"Missing field '{field}' in outlet")
                    return False
        
        # Verify forgiveness structure
        required_forgiveness_fields = ["id", "title", "icon", "frequency", "sections"]
        for aff in forgiveness:
            for field in required_forgiveness_fields:
                if field not in aff:
                    log_test("Get All Outlets - Forgiveness Structure", False, f"Missing field '{field}' in affirmation")
                    return False
        
        log_test("Get All Outlets", True, f"9 outlets and 7 forgiveness categories with proper structure")
        return True
    else:
        log_test("Get All Outlets", False, f"Status: {response.status_code}, Response: {response.text}")
        return False


def test_3_get_practice_history_empty():
    """Test 3: GET /api/emotional-gatekeeper/advisor/my-practices (empty)"""
    url = f"{BASE_URL}/emotional-gatekeeper/advisor/my-practices"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        logs = data.get("logs", [])
        stats = data.get("stats", {})
        
        if len(logs) != 0:
            log_test("Get Practice History (Empty)", False, f"Expected 0 logs, got {len(logs)}")
            return False
        
        if stats.get("total_practices") != 0:
            log_test("Get Practice History (Empty)", False, f"Expected 0 total_practices, got {stats.get('total_practices')}")
            return False
        
        if stats.get("streak") != 0:
            log_test("Get Practice History (Empty)", False, f"Expected 0 streak, got {stats.get('streak')}")
            return False
        
        log_test("Get Practice History (Empty)", True, "Empty logs and 0 stats")
        return True
    else:
        log_test("Get Practice History (Empty)", False, f"Status: {response.status_code}, Response: {response.text}")
        return False


def test_4_log_practice_joint_exercise():
    """Test 4: POST /api/emotional-gatekeeper/advisor/practice-log - Joint Exercise"""
    url = f"{BASE_URL}/emotional-gatekeeper/advisor/practice-log"
    headers = {"Authorization": f"Bearer {session_token}"}
    payload = {
        "outlet_id": "joint_exercise",
        "duration_seconds": 300
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        logged = data.get("logged", {})
        
        if logged.get("outlet_id") != "joint_exercise":
            log_test("Log Practice - Joint Exercise", False, f"outlet_id mismatch")
            return False
        
        if logged.get("duration_seconds") != 300:
            log_test("Log Practice - Joint Exercise", False, f"duration_seconds mismatch")
            return False
        
        if not logged.get("id"):
            log_test("Log Practice - Joint Exercise", False, f"Missing id field")
            return False
        
        log_test("Log Practice - Joint Exercise", True, f"Logged with id: {logged.get('id')}")
        return True
    else:
        log_test("Log Practice - Joint Exercise", False, f"Status: {response.status_code}, Response: {response.text}")
        return False


def test_5_log_practice_super_brain_yoga():
    """Test 5: POST /api/emotional-gatekeeper/advisor/practice-log - Super Brain Yoga"""
    url = f"{BASE_URL}/emotional-gatekeeper/advisor/practice-log"
    headers = {"Authorization": f"Bearer {session_token}"}
    payload = {
        "outlet_id": "super_brain_yoga",
        "duration_seconds": 200,
        "notes": "14 reps done"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        logged = data.get("logged", {})
        
        if logged.get("outlet_id") != "super_brain_yoga":
            log_test("Log Practice - Super Brain Yoga", False, f"outlet_id mismatch")
            return False
        
        if logged.get("notes") != "14 reps done":
            log_test("Log Practice - Super Brain Yoga", False, f"notes mismatch")
            return False
        
        log_test("Log Practice - Super Brain Yoga", True, f"Logged with notes")
        return True
    else:
        log_test("Log Practice - Super Brain Yoga", False, f"Status: {response.status_code}, Response: {response.text}")
        return False


def test_6_log_practice_release_technique():
    """Test 6: POST /api/emotional-gatekeeper/advisor/practice-log - Release Technique"""
    url = f"{BASE_URL}/emotional-gatekeeper/advisor/practice-log"
    headers = {"Authorization": f"Bearer {session_token}"}
    payload = {
        "outlet_id": "release_technique",
        "duration_seconds": 120
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        log_test("Log Practice - Release Technique", True, "Logged successfully")
        return True
    else:
        log_test("Log Practice - Release Technique", False, f"Status: {response.status_code}, Response: {response.text}")
        return False


def test_7_log_practice_forgiveness_affirmation():
    """Test 7: POST /api/emotional-gatekeeper/advisor/practice-log - Forgiveness Affirmation"""
    url = f"{BASE_URL}/emotional-gatekeeper/advisor/practice-log"
    headers = {"Authorization": f"Bearer {session_token}"}
    payload = {
        "outlet_id": "forgiveness_affirmations",
        "affirmation_category": "forgiving_yourself"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        logged = data.get("logged", {})
        
        if logged.get("affirmation_category") != "forgiving_yourself":
            log_test("Log Practice - Forgiveness Affirmation", False, f"affirmation_category mismatch")
            return False
        
        log_test("Log Practice - Forgiveness Affirmation", True, "Logged with affirmation_category")
        return True
    else:
        log_test("Log Practice - Forgiveness Affirmation", False, f"Status: {response.status_code}, Response: {response.text}")
        return False


def test_8_log_practice_hoorecon_o_pono():
    """Test 8: POST /api/emotional-gatekeeper/advisor/practice-log - HOORECON-o-Pono"""
    url = f"{BASE_URL}/emotional-gatekeeper/advisor/practice-log"
    headers = {"Authorization": f"Bearer {session_token}"}
    payload = {
        "outlet_id": "hoorecon_o_pono",
        "duration_seconds": 120
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        log_test("Log Practice - HOORECON-o-Pono", True, "Logged successfully")
        return True
    else:
        log_test("Log Practice - HOORECON-o-Pono", False, f"Status: {response.status_code}, Response: {response.text}")
        return False


def test_9_log_practice_invalid_outlet():
    """Test 9: POST /api/emotional-gatekeeper/advisor/practice-log - Invalid outlet (error case)"""
    url = f"{BASE_URL}/emotional-gatekeeper/advisor/practice-log"
    headers = {"Authorization": f"Bearer {session_token}"}
    payload = {
        "outlet_id": "invalid_outlet"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 400:
        log_test("Log Practice - Invalid Outlet (Error Case)", True, "Correctly rejected with 400")
        return True
    else:
        log_test("Log Practice - Invalid Outlet (Error Case)", False, f"Expected 400, got {response.status_code}")
        return False


def test_10_save_gratitude_journal():
    """Test 10: POST /api/emotional-gatekeeper/advisor/gratitude"""
    url = f"{BASE_URL}/emotional-gatekeeper/advisor/gratitude"
    headers = {"Authorization": f"Bearer {session_token}"}
    payload = {
        "entries": ["My health", "My family", "This beautiful morning"]
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        
        if data.get("entries_count") != 3:
            log_test("Save Gratitude Journal", False, f"Expected entries_count=3, got {data.get('entries_count')}")
            return False
        
        saved = data.get("saved", {})
        if len(saved.get("entries", [])) != 3:
            log_test("Save Gratitude Journal", False, f"Expected 3 entries in saved object")
            return False
        
        log_test("Save Gratitude Journal", True, "Saved 3 gratitude entries")
        return True
    else:
        log_test("Save Gratitude Journal", False, f"Status: {response.status_code}, Response: {response.text}")
        return False


def test_11_get_gratitude_history():
    """Test 11: GET /api/emotional-gatekeeper/advisor/gratitude-history"""
    url = f"{BASE_URL}/emotional-gatekeeper/advisor/gratitude-history"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        journals = data.get("journals", [])
        total = data.get("total", 0)
        
        if total != 1:
            log_test("Get Gratitude History", False, f"Expected total=1, got {total}")
            return False
        
        if len(journals) != 1:
            log_test("Get Gratitude History", False, f"Expected 1 journal entry, got {len(journals)}")
            return False
        
        log_test("Get Gratitude History", True, "1 journal entry found")
        return True
    else:
        log_test("Get Gratitude History", False, f"Status: {response.status_code}, Response: {response.text}")
        return False


def test_12_get_practice_history_after_logging():
    """Test 12: GET /api/emotional-gatekeeper/advisor/my-practices (after logging)"""
    url = f"{BASE_URL}/emotional-gatekeeper/advisor/my-practices"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        stats = data.get("stats", {})
        
        # We logged 5 practices + 1 gratitude auto-log = 6 total
        total_practices = stats.get("total_practices", 0)
        if total_practices < 6:
            log_test("Get Practice History (After Logging)", False, f"Expected >= 6 practices, got {total_practices}")
            return False
        
        streak = stats.get("streak", 0)
        if streak < 1:
            log_test("Get Practice History (After Logging)", False, f"Expected streak >= 1, got {streak}")
            return False
        
        outlet_counts = stats.get("outlet_counts", {})
        if len(outlet_counts) == 0:
            log_test("Get Practice History (After Logging)", False, f"Expected outlet_counts to have entries")
            return False
        
        log_test("Get Practice History (After Logging)", True, f"total_practices={total_practices}, streak={streak}, outlet_counts={len(outlet_counts)} types")
        return True
    else:
        log_test("Get Practice History (After Logging)", False, f"Status: {response.status_code}, Response: {response.text}")
        return False


def test_13_get_sms_recommendations_no_analysis():
    """Test 13: GET /api/emotional-gatekeeper/advisor/sms-recommendations (no analysis yet)"""
    url = f"{BASE_URL}/emotional-gatekeeper/advisor/sms-recommendations"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        
        if data.get("has_analysis") != False:
            log_test("Get SMS Recommendations (No Analysis)", False, f"Expected has_analysis=false, got {data.get('has_analysis')}")
            return False
        
        if "Complete the Outlet Analyzer first" not in data.get("message", ""):
            log_test("Get SMS Recommendations (No Analysis)", False, f"Expected message about completing Outlet Analyzer")
            return False
        
        log_test("Get SMS Recommendations (No Analysis)", True, "Correctly returns has_analysis=false with message")
        return True
    else:
        log_test("Get SMS Recommendations (No Analysis)", False, f"Status: {response.status_code}, Response: {response.text}")
        return False


def run_all_tests():
    """Run all tests in sequence"""
    print("\n" + "="*80)
    print("EFFECTIVE OUTLETS ADVISOR - BACKEND API TESTING")
    print("="*80 + "\n")
    
    tests = [
        test_1_register_user,
        test_2_get_all_outlets,
        test_3_get_practice_history_empty,
        test_4_log_practice_joint_exercise,
        test_5_log_practice_super_brain_yoga,
        test_6_log_practice_release_technique,
        test_7_log_practice_forgiveness_affirmation,
        test_8_log_practice_hoorecon_o_pono,
        test_9_log_practice_invalid_outlet,
        test_10_save_gratitude_journal,
        test_11_get_gratitude_history,
        test_12_get_practice_history_after_logging,
        test_13_get_sms_recommendations_no_analysis,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            log_test(test_func.__name__, False, f"Exception: {str(e)}")
            failed += 1
        print()  # Empty line between tests
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {passed + failed}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"Success Rate: {(passed / (passed + failed) * 100):.1f}%")
    print("="*80 + "\n")
    
    # Detailed results
    print("\nDETAILED RESULTS:")
    print("-" * 80)
    for result in test_results:
        print(result)
    print("-" * 80)
    
    return passed, failed


if __name__ == "__main__":
    run_all_tests()
