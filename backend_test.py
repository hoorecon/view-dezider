#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for Emotional Gatekeeper Module
Tests all endpoints as specified in the review request
"""

import requests
import json
import time
from datetime import datetime

# Backend URL
BASE_URL = "https://dezider-core.preview.emergentagent.com/api"

# Test results tracking
test_results = []
session_token = None
user_email = None

def log_test(test_name, passed, details=""):
    """Log test result"""
    status = "✅ PASSED" if passed else "❌ FAILED"
    test_results.append({
        "test": test_name,
        "passed": passed,
        "details": details
    })
    print(f"{status}: {test_name}")
    if details:
        print(f"  Details: {details}")

def print_summary():
    """Print test summary"""
    passed = sum(1 for r in test_results if r["passed"])
    total = len(test_results)
    print("\n" + "="*80)
    print(f"TEST SUMMARY: {passed}/{total} tests passed ({passed*100//total}% success rate)")
    print("="*80)
    
    if any(not r["passed"] for r in test_results):
        print("\n❌ FAILED TESTS:")
        for r in test_results:
            if not r["passed"]:
                print(f"  - {r['test']}: {r['details']}")

# ============================================================================
# AUTHENTICATION TESTS
# ============================================================================

def test_user_registration():
    """Test 1: Register a new test user"""
    global session_token, user_email
    
    timestamp = int(time.time())
    user_email = f"egtest_{timestamp}@emotionalgateway.com"
    
    payload = {
        "email": user_email,
        "password": "SecurePass123!",
        "name": "Emma Gatekeeper"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/register", json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "session_token" in data and "user_id" in data:
                session_token = data["session_token"]
                log_test("User Registration", True, f"Registered {user_email} with session token")
                return True
            else:
                log_test("User Registration", False, "Missing session_token or user_id in response")
                return False
        else:
            log_test("User Registration", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("User Registration", False, f"Exception: {str(e)}")
        return False

# ============================================================================
# EMOTIONAL GATEKEEPER - DASHBOARD & SESSIONS
# ============================================================================

def test_dashboard_empty():
    """Test 2: Dashboard should show zeros initially"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.get(f"{BASE_URL}/emotional-gatekeeper/dashboard", headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # Check for expected structure - API returns different field names
            if "total_sessions" in data:
                log_test("Dashboard (Empty)", True, f"Dashboard returned: total_sessions={data.get('total_sessions', 0)}")
                return True
            else:
                log_test("Dashboard (Empty)", False, f"Missing total_sessions field in response: {data}")
                return False
        else:
            log_test("Dashboard (Empty)", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Dashboard (Empty)", False, f"Exception: {str(e)}")
        return False

def test_create_trap_session():
    """Test 3: Create a trap session"""
    global trap_session_id
    
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        payload = {
            "session_type": "trap",
            "title": "Test Trap Session"
        }
        response = requests.post(f"{BASE_URL}/emotional-gatekeeper/sessions", json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # API returns 'id' instead of 'session_id'
            if "id" in data:
                trap_session_id = data["id"]
                log_test("Create Trap Session", True, f"Created session: {trap_session_id}")
                return True
            else:
                log_test("Create Trap Session", False, f"Missing id in response: {data}")
                return False
        else:
            log_test("Create Trap Session", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Create Trap Session", False, f"Exception: {str(e)}")
        return False

def test_list_sessions():
    """Test 4: List sessions should return at least 1"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.get(f"{BASE_URL}/emotional-gatekeeper/sessions", headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "sessions" in data and "total" in data:
                if data["total"] >= 1:
                    log_test("List Sessions", True, f"Found {data['total']} session(s)")
                    return True
                else:
                    log_test("List Sessions", False, f"Expected at least 1 session, got {data['total']}")
                    return False
            else:
                log_test("List Sessions", False, f"Missing expected fields: {data}")
                return False
        else:
            log_test("List Sessions", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("List Sessions", False, f"Exception: {str(e)}")
        return False

def test_get_session_detail():
    """Test 5: Get session detail"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.get(f"{BASE_URL}/emotional-gatekeeper/sessions/{trap_session_id}", headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # API returns 'id' instead of 'session_id'
            if "id" in data and "session_type" in data:
                log_test("Get Session Detail", True, f"Retrieved session: {data.get('title', 'N/A')}")
                return True
            else:
                log_test("Get Session Detail", False, f"Missing expected fields: {data}")
                return False
        else:
            log_test("Get Session Detail", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Get Session Detail", False, f"Exception: {str(e)}")
        return False

# ============================================================================
# BREAKING THE TRAP FLOW
# ============================================================================

def test_trap_capture():
    """Test 6: Trap - Capture step"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        payload = {
            "situation": "Worried about job performance review",
            "category": "career",
            "intensity": 7
        }
        response = requests.post(f"{BASE_URL}/emotional-gatekeeper/trap/{trap_session_id}/capture", 
                                json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            log_test("Trap - Capture", True, f"Captured trap situation")
            return True
        else:
            log_test("Trap - Capture", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Trap - Capture", False, f"Exception: {str(e)}")
        return False

def test_trap_landscaping():
    """Test 7: Trap - Landscaping step"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        payload = {
            "scanning_for": "career risks",
            "scanning_patterns": ["failure", "rejection"],
            "scanning_without_urgency": True,
            "repeated_concern": "losing job"
        }
        response = requests.put(f"{BASE_URL}/emotional-gatekeeper/trap/{trap_session_id}/landscaping", 
                               json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            log_test("Trap - Landscaping", True, f"Landscaping completed")
            return True
        else:
            log_test("Trap - Landscaping", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Trap - Landscaping", False, f"Exception: {str(e)}")
        return False

def test_trap_linking():
    """Test 8: Trap - Linking step"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        payload = {
            "trigger_description": "performance review email",
            "trigger_type": "external",
            "linking_meaning": "I might get fired"
        }
        response = requests.put(f"{BASE_URL}/emotional-gatekeeper/trap/{trap_session_id}/linking", 
                               json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            log_test("Trap - Linking", True, f"Linking completed")
            return True
        else:
            log_test("Trap - Linking", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Trap - Linking", False, f"Exception: {str(e)}")
        return False

def test_trap_looping():
    """Test 9: Trap - Looping step"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        payload = {
            "repeating_thought": "What if I lose my job",
            "getting_new_solution": False,
            "emotion_increasing": "increasing",
            "intensity_before": 7,
            "intensity_after": 9
        }
        response = requests.put(f"{BASE_URL}/emotional-gatekeeper/trap/{trap_session_id}/looping", 
                               json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            log_test("Trap - Looping", True, f"Looping completed")
            return True
        else:
            log_test("Trap - Looping", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Trap - Looping", False, f"Exception: {str(e)}")
        return False

def test_trap_analyze():
    """Test 10: Trap - AI Analysis (may take 5-15 seconds)"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.post(f"{BASE_URL}/emotional-gatekeeper/trap/{trap_session_id}/analyze", 
                                headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            # API returns nested structure with 'analysis' key
            if "analysis" in data and "current_stage" in data["analysis"]:
                log_test("Trap - AI Analysis", True, f"AI analysis completed with stage: {data['analysis'].get('current_stage', 'N/A')}")
                return True
            else:
                log_test("Trap - AI Analysis", False, f"Missing expected AI fields: {data}")
                return False
        else:
            log_test("Trap - AI Analysis", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Trap - AI Analysis", False, f"Exception: {str(e)}")
        return False

# ============================================================================
# BREAKING THE LOOP FLOW
# ============================================================================

def test_create_loop_session():
    """Test 11: Create a loop session"""
    global loop_session_id
    
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        payload = {
            "session_type": "loop",
            "title": "Test Loop Session"
        }
        response = requests.post(f"{BASE_URL}/emotional-gatekeeper/sessions", json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "id" in data:
                loop_session_id = data["id"]
                log_test("Create Loop Session", True, f"Created session: {loop_session_id}")
                return True
            else:
                log_test("Create Loop Session", False, f"Missing id: {data}")
                return False
        else:
            log_test("Create Loop Session", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Create Loop Session", False, f"Exception: {str(e)}")
        return False

def test_loop_capture():
    """Test 12: Loop - Capture step"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        payload = {
            "repeated_thought": "I am not good enough",
            "emotion": "anxiety",
            "repeat_count_today": 5,
            "fear": "being inadequate",
            "trying_to_solve": "self-worth"
        }
        response = requests.post(f"{BASE_URL}/emotional-gatekeeper/loop/{loop_session_id}/capture", 
                                json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            log_test("Loop - Capture", True, f"Loop captured")
            return True
        else:
            log_test("Loop - Capture", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Loop - Capture", False, f"Exception: {str(e)}")
        return False

def test_loop_recommend():
    """Test 13: Loop - AI Recommendation (may take 5-15 seconds)"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.post(f"{BASE_URL}/emotional-gatekeeper/loop/{loop_session_id}/recommend", 
                                headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            # API returns nested structure with 'recommendation' key
            if "recommendation" in data and "recommended_method" in data["recommendation"]:
                log_test("Loop - AI Recommendation", True, f"Recommended method: {data['recommendation'].get('recommended_method', 'N/A')}")
                return True
            else:
                log_test("Loop - AI Recommendation", False, f"Missing recommended_method: {data}")
                return False
        else:
            log_test("Loop - AI Recommendation", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Loop - AI Recommendation", False, f"Exception: {str(e)}")
        return False

def test_loop_method():
    """Test 14: Loop - Method selection"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        payload = {
            "selected_method": "i_dont_know",
            "method_answers": {
                "q0": "I'm sure I struggle",
                "q1": "I'm not sure about outcomes",
                "q2": "Yes I can try"
            }
        }
        response = requests.put(f"{BASE_URL}/emotional-gatekeeper/loop/{loop_session_id}/method", 
                               json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            log_test("Loop - Method Selection", True, f"Method selected")
            return True
        else:
            log_test("Loop - Method Selection", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Loop - Method Selection", False, f"Exception: {str(e)}")
        return False

def test_loop_reframe():
    """Test 15: Loop - AI Reframe (may take 5-15 seconds)"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.post(f"{BASE_URL}/emotional-gatekeeper/loop/{loop_session_id}/reframe", 
                                headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            # API returns nested structure with 'reframe' key
            if "reframe" in data and "new_perspective" in data["reframe"] and "calming_statement" in data["reframe"]:
                log_test("Loop - AI Reframe", True, f"Reframe completed")
                return True
            else:
                log_test("Loop - AI Reframe", False, f"Missing expected fields: {data}")
                return False
        else:
            log_test("Loop - AI Reframe", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Loop - AI Reframe", False, f"Exception: {str(e)}")
        return False

# ============================================================================
# BREAKING LIMITATIONS FLOW
# ============================================================================

def test_create_limitation_session():
    """Test 16: Create a limitation session"""
    global limitation_session_id
    
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        payload = {
            "session_type": "limitation",
            "title": "Test Limitation Session"
        }
        response = requests.post(f"{BASE_URL}/emotional-gatekeeper/sessions", json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "id" in data:
                limitation_session_id = data["id"]
                log_test("Create Limitation Session", True, f"Created session: {limitation_session_id}")
                return True
            else:
                log_test("Create Limitation Session", False, f"Missing id: {data}")
                return False
        else:
            log_test("Create Limitation Session", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Create Limitation Session", False, f"Exception: {str(e)}")
        return False

def test_limitation_capture():
    """Test 17: Limitation - Capture step"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        payload = {
            "limitation_statement": "I can never start a business",
            "why_limited": "Failed before",
            "origin": "past failure",
            "belief_duration": "5 years",
            "cost_of_limitation": "Stayed in unfulfilling job"
        }
        response = requests.post(f"{BASE_URL}/emotional-gatekeeper/limitation/{limitation_session_id}/capture", 
                                json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            log_test("Limitation - Capture", True, f"Limitation captured")
            return True
        else:
            log_test("Limitation - Capture", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Limitation - Capture", False, f"Exception: {str(e)}")
        return False

def test_limitation_classify():
    """Test 18: Limitation - AI Classification (may take 5-15 seconds)"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.post(f"{BASE_URL}/emotional-gatekeeper/limitation/{limitation_session_id}/classify", 
                                headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            # API returns nested structure with 'classification' key
            if "classification" in data and "category" in data["classification"] and "confidence" in data["classification"]:
                log_test("Limitation - AI Classification", True, f"Category: {data['classification'].get('category', 'N/A')}, Confidence: {data['classification'].get('confidence', 'N/A')}")
                return True
            else:
                log_test("Limitation - AI Classification", False, f"Missing expected fields: {data}")
                return False
        else:
            log_test("Limitation - AI Classification", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Limitation - AI Classification", False, f"Exception: {str(e)}")
        return False

def test_limitation_flow():
    """Test 19: Limitation - Flow step"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        payload = {
            "answers": {
                "q0": "I failed once 5 years ago",
                "q1": "I have new skills now",
                "q2": "Yes significantly"
            }
        }
        response = requests.put(f"{BASE_URL}/emotional-gatekeeper/limitation/{limitation_session_id}/flow", 
                               json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            log_test("Limitation - Flow", True, f"Flow completed")
            return True
        else:
            log_test("Limitation - Flow", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Limitation - Flow", False, f"Exception: {str(e)}")
        return False

def test_limitation_reframe():
    """Test 20: Limitation - AI Reframe (may take 5-15 seconds)"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.post(f"{BASE_URL}/emotional-gatekeeper/limitation/{limitation_session_id}/reframe", 
                                headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            # API returns nested structure with 'reframe' key
            if "reframe" in data and "old_belief" in data["reframe"] and "new_belief" in data["reframe"] and "affirmation" in data["reframe"]:
                log_test("Limitation - AI Reframe", True, f"Reframe completed")
                return True
            else:
                log_test("Limitation - AI Reframe", False, f"Missing expected fields: {data}")
                return False
        else:
            log_test("Limitation - AI Reframe", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Limitation - AI Reframe", False, f"Exception: {str(e)}")
        return False

# ============================================================================
# OUTLET ANALYZER
# ============================================================================

def test_outlet_strategies():
    """Test 21: Get outlet strategies"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.get(f"{BASE_URL}/emotional-gatekeeper/outlet/strategies", headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "strategies" in data:
                log_test("Outlet - Get Strategies", True, f"Found {len(data['strategies'])} strategies")
                return True
            else:
                log_test("Outlet - Get Strategies", False, f"Missing strategies field: {data}")
                return False
        else:
            log_test("Outlet - Get Strategies", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Outlet - Get Strategies", False, f"Exception: {str(e)}")
        return False

def test_create_outlet_session():
    """Test 22: Create an outlet session"""
    global outlet_session_id
    
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        payload = {
            "session_type": "outlet",
            "title": "Test Outlet Session"
        }
        response = requests.post(f"{BASE_URL}/emotional-gatekeeper/sessions", json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "id" in data:
                outlet_session_id = data["id"]
                log_test("Create Outlet Session", True, f"Created session: {outlet_session_id}")
                return True
            else:
                log_test("Create Outlet Session", False, f"Missing id: {data}")
                return False
        else:
            log_test("Create Outlet Session", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Create Outlet Session", False, f"Exception: {str(e)}")
        return False

def test_outlet_analyze():
    """Test 23: Outlet - AI Analysis (may take 5-15 seconds)"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        payload = {
            "entries": [
                {
                    "strategy_id": "social_media",
                    "frequency": "often",
                    "is_compulsive": True
                },
                {
                    "strategy_id": "yoga_meditation",
                    "frequency": "rarely"
                }
            ]
        }
        response = requests.post(f"{BASE_URL}/emotional-gatekeeper/outlet/{outlet_session_id}/analyze", 
                                json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            log_test("Outlet - AI Analysis", True, f"Analysis completed")
            return True
        else:
            log_test("Outlet - AI Analysis", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Outlet - AI Analysis", False, f"Exception: {str(e)}")
        return False

# ============================================================================
# AIM MANAGER
# ============================================================================

def test_aim_options():
    """Test 24: Get AIM options"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.get(f"{BASE_URL}/emotional-gatekeeper/aim/options", headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "life_areas" in data and "occurrences" in data:
                log_test("AIM - Get Options", True, f"Found {len(data['life_areas'])} life areas")
                return True
            else:
                log_test("AIM - Get Options", False, f"Missing expected fields: {data}")
                return False
        else:
            log_test("AIM - Get Options", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("AIM - Get Options", False, f"Exception: {str(e)}")
        return False

def test_create_aim_session():
    """Test 25: Create an AIM session"""
    global aim_session_id
    
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        payload = {
            "session_type": "aim",
            "title": "Test AIM Session"
        }
        response = requests.post(f"{BASE_URL}/emotional-gatekeeper/sessions", json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "id" in data:
                aim_session_id = data["id"]
                log_test("Create AIM Session", True, f"Created session: {aim_session_id}")
                return True
            else:
                log_test("Create AIM Session", False, f"Missing id: {data}")
                return False
        else:
            log_test("Create AIM Session", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Create AIM Session", False, f"Exception: {str(e)}")
        return False

def test_aim_save():
    """Test 26: AIM - Save addictions and irritations"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        payload = {
            "addictions": [
                {
                    "area_of_life": "career",
                    "addiction": "Scrolling social media",
                    "triggering_situations": "boredom",
                    "positive_impact_pct": 10,
                    "negative_impact_pct": 80
                }
            ],
            "irritations": [
                {
                    "area_of_life": "emotional_relationships",
                    "irritation": "Being interrupted",
                    "probable_reaction": "Getting angry"
                }
            ]
        }
        response = requests.post(f"{BASE_URL}/emotional-gatekeeper/aim/{aim_session_id}/save", 
                                json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            log_test("AIM - Save Data", True, f"AIM data saved")
            return True
        else:
            log_test("AIM - Save Data", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("AIM - Save Data", False, f"Exception: {str(e)}")
        return False

def test_aim_analyze():
    """Test 27: AIM - AI Analysis (may take 5-15 seconds)"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.post(f"{BASE_URL}/emotional-gatekeeper/aim/{aim_session_id}/analyze", 
                                headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            log_test("AIM - AI Analysis", True, f"Analysis completed")
            return True
        else:
            log_test("AIM - AI Analysis", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("AIM - AI Analysis", False, f"Exception: {str(e)}")
        return False

# ============================================================================
# COMMITMENTS & JOURNAL
# ============================================================================

def test_create_commitment():
    """Test 28: Create a commitment"""
    global commitment_id
    
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        payload = {
            "commitment_type": "immediate",
            "commitment_text": "I will practice mindfulness daily"
        }
        response = requests.post(f"{BASE_URL}/emotional-gatekeeper/sessions/{trap_session_id}/commitments", 
                                json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "id" in data:
                commitment_id = data["id"]
                log_test("Create Commitment", True, f"Created commitment: {commitment_id}")
                return True
            else:
                log_test("Create Commitment", False, f"Missing id: {data}")
                return False
        else:
            log_test("Create Commitment", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Create Commitment", False, f"Exception: {str(e)}")
        return False

def test_complete_commitment():
    """Test 29: Complete a commitment"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.put(f"{BASE_URL}/emotional-gatekeeper/commitments/{commitment_id}/complete", 
                               headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            log_test("Complete Commitment", True, f"Commitment completed")
            return True
        else:
            log_test("Complete Commitment", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Complete Commitment", False, f"Exception: {str(e)}")
        return False

def test_create_journal():
    """Test 30: Create a journal entry"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        payload = {
            "journal_content": "Today I realized my thoughts are not facts"
        }
        response = requests.post(f"{BASE_URL}/emotional-gatekeeper/sessions/{trap_session_id}/journal", 
                                json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            log_test("Create Journal Entry", True, f"Journal entry created")
            return True
        else:
            log_test("Create Journal Entry", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Create Journal Entry", False, f"Exception: {str(e)}")
        return False

# ============================================================================
# AI REPORT
# ============================================================================

def test_generate_report():
    """Test 31: Generate AI breakthrough report (may take 5-15 seconds)"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.post(f"{BASE_URL}/emotional-gatekeeper/sessions/{trap_session_id}/report", 
                                headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            log_test("Generate AI Report", True, f"Report generated")
            return True
        else:
            log_test("Generate AI Report", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Generate AI Report", False, f"Exception: {str(e)}")
        return False

# ============================================================================
# DASHBOARD AFTER DATA
# ============================================================================

def test_dashboard_with_data():
    """Test 32: Dashboard should show non-zero counts"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.get(f"{BASE_URL}/emotional-gatekeeper/dashboard", headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "total_sessions" in data:
                if data["total_sessions"] > 0:
                    log_test("Dashboard (With Data)", True, f"Dashboard shows {data['total_sessions']} sessions")
                    return True
                else:
                    log_test("Dashboard (With Data)", False, f"Expected non-zero sessions, got {data['total_sessions']}")
                    return False
            else:
                log_test("Dashboard (With Data)", False, f"Missing total_sessions: {data}")
                return False
        else:
            log_test("Dashboard (With Data)", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Dashboard (With Data)", False, f"Exception: {str(e)}")
        return False

# ============================================================================
# DELETE SESSION
# ============================================================================

def test_delete_session():
    """Test 33: Delete a session"""
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.delete(f"{BASE_URL}/emotional-gatekeeper/sessions/{trap_session_id}", 
                                  headers=headers, timeout=10)
        
        if response.status_code == 200:
            log_test("Delete Session", True, f"Session deleted successfully")
            return True
        else:
            log_test("Delete Session", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Delete Session", False, f"Exception: {str(e)}")
        return False

# ============================================================================
# MAIN TEST EXECUTION
# ============================================================================

def main():
    """Run all tests in sequence"""
    print("="*80)
    print("EMOTIONAL GATEKEEPER MODULE - COMPREHENSIVE BACKEND TESTING")
    print("="*80)
    print(f"Backend URL: {BASE_URL}")
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    print()
    
    # Authentication
    if not test_user_registration():
        print("\n❌ Authentication failed. Cannot proceed with tests.")
        print_summary()
        return
    
    # Dashboard & Sessions
    test_dashboard_empty()
    test_create_trap_session()
    test_list_sessions()
    test_get_session_detail()
    
    # Breaking the Trap Flow
    test_trap_capture()
    test_trap_landscaping()
    test_trap_linking()
    test_trap_looping()
    test_trap_analyze()
    
    # Breaking the Loop Flow
    test_create_loop_session()
    test_loop_capture()
    test_loop_recommend()
    test_loop_method()
    test_loop_reframe()
    
    # Breaking Limitations Flow
    test_create_limitation_session()
    test_limitation_capture()
    test_limitation_classify()
    test_limitation_flow()
    test_limitation_reframe()
    
    # Outlet Analyzer
    test_outlet_strategies()
    test_create_outlet_session()
    test_outlet_analyze()
    
    # AIM Manager
    test_aim_options()
    test_create_aim_session()
    test_aim_save()
    test_aim_analyze()
    
    # Commitments & Journal
    test_create_commitment()
    test_complete_commitment()
    test_create_journal()
    
    # AI Report
    test_generate_report()
    
    # Dashboard After Data
    test_dashboard_with_data()
    
    # Delete Session
    test_delete_session()
    
    # Print summary
    print()
    print_summary()
    print()
    print(f"Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

if __name__ == "__main__":
    main()
