#!/usr/bin/env python3
"""
Backend API Testing for Goal Setter, Goal Manifestation, and Unconditional Happiness Modules
Tests all 18 endpoints across the 3 new modules
"""
import requests
import json
import time
from datetime import datetime, timedelta

# Backend URL
BASE_URL = "https://dezider-core.preview.emergentagent.com/api"

# Test results tracking
test_results = []
session_token = None
user_data = None

def log_test(test_name, passed, details=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    result = f"{status}: {test_name}"
    if details:
        result += f" - {details}"
    test_results.append(result)
    print(result)
    return passed

def register_and_login():
    """Register a new test user and login"""
    global session_token, user_data
    
    timestamp = int(time.time())
    email = f"goaltest_{timestamp}@example.com"
    password = "TestPass123!"
    name = f"Goal Test User {timestamp}"
    
    # Register
    print("\n=== AUTHENTICATION ===")
    register_data = {
        "email": email,
        "password": password,
        "name": name
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/auth/register", json=register_data, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            session_token = data.get("session_token")
            user_data = data
            log_test("User Registration", True, f"Registered {email}")
            
            # Login to verify
            login_resp = requests.post(
                f"{BASE_URL}/auth/login",
                json={"email": email, "password": password},
                timeout=10
            )
            if login_resp.status_code == 200:
                login_data = login_resp.json()
                session_token = login_data.get("session_token")
                log_test("User Login", True, f"Logged in successfully")
                return True
            else:
                log_test("User Login", False, f"Status: {login_resp.status_code}")
                return False
        else:
            log_test("User Registration", False, f"Status: {resp.status_code}, Response: {resp.text}")
            return False
    except Exception as e:
        log_test("User Registration", False, f"Exception: {str(e)}")
        return False

def get_headers():
    """Get authorization headers"""
    return {
        "Authorization": f"Bearer {session_token}",
        "Content-Type": "application/json"
    }

# ═══════════════════════════════════════════════════════════════
# MODULE 1: GOAL SETTER TESTS
# ═══════════════════════════════════════════════════════════════

def test_goal_setter_framework():
    """Test 1: GET /api/goal-setter/framework"""
    print("\n=== MODULE 1: GOAL SETTER ===")
    try:
        resp = requests.get(f"{BASE_URL}/goal-setter/framework", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # Verify structure
            has_audio = "audio_url" in data
            has_fields = "fields" in data and len(data["fields"]) == 5
            has_smart = all(f["letter"] in ["S", "M", "A", "R", "T"] for f in data.get("fields", []))
            
            if has_audio and has_fields and has_smart:
                log_test("Goal Setter Framework", True, f"Returns SMART framework with audio_url")
                return data
            else:
                log_test("Goal Setter Framework", False, f"Missing required fields")
                return None
        else:
            log_test("Goal Setter Framework", False, f"Status: {resp.status_code}")
            return None
    except Exception as e:
        log_test("Goal Setter Framework", False, f"Exception: {str(e)}")
        return None

def test_create_goal():
    """Test 2: POST /api/goal-setter/goals"""
    try:
        goal_data = {
            "title": "Launch SaaS Product",
            "life_area": "career",
            "challenge": "Need to build and launch a profitable SaaS product",
            "specific": "Launch a decision intelligence SaaS platform with core PRR features",
            "measurable": "Achieve ₹10L MRR with 50 paying customers within 12 months",
            "achievable": "I have technical skills, 5 years experience, and ₹5L budget for development",
            "realistic": "Market research shows demand for decision tools, competitors exist but niche is underserved",
            "timebound": "MVP by Aug 2026, 20 customers by Nov 2026, ₹10L MRR by May 2027",
            "milestones": [
                {"date": "2026-08-01", "title": "MVP Launch"},
                {"date": "2026-11-01", "title": "20 Customers"},
                {"date": "2027-05-01", "title": "₹10L MRR"}
            ],
            "priority": "high",
            "status": "active",
            "progress_pct": 15
        }
        
        resp = requests.post(
            f"{BASE_URL}/goal-setter/goals",
            json=goal_data,
            headers=get_headers(),
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            has_id = "goal_id" in data
            has_smart = all(k in data for k in ["specific", "measurable", "achievable", "realistic", "timebound"])
            
            if has_id and has_smart:
                log_test("Create SMART Goal", True, f"Goal created: {data['goal_id']}")
                return data
            else:
                log_test("Create SMART Goal", False, "Missing required fields in response")
                return None
        else:
            log_test("Create SMART Goal", False, f"Status: {resp.status_code}, Response: {resp.text}")
            return None
    except Exception as e:
        log_test("Create SMART Goal", False, f"Exception: {str(e)}")
        return None

def test_list_goals():
    """Test 3: GET /api/goal-setter/goals"""
    try:
        resp = requests.get(
            f"{BASE_URL}/goal-setter/goals",
            headers=get_headers(),
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                log_test("List Goals", True, f"Retrieved {len(data)} goals")
                return data
            else:
                log_test("List Goals", False, "Response is not a list")
                return None
        else:
            log_test("List Goals", False, f"Status: {resp.status_code}")
            return None
    except Exception as e:
        log_test("List Goals", False, f"Exception: {str(e)}")
        return None

def test_get_goal(goal_id):
    """Test 4: GET /api/goal-setter/goals/{goal_id}"""
    try:
        resp = requests.get(
            f"{BASE_URL}/goal-setter/goals/{goal_id}",
            headers=get_headers(),
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("goal_id") == goal_id:
                log_test("Get Single Goal", True, f"Retrieved goal {goal_id}")
                return data
            else:
                log_test("Get Single Goal", False, "Goal ID mismatch")
                return None
        else:
            log_test("Get Single Goal", False, f"Status: {resp.status_code}")
            return None
    except Exception as e:
        log_test("Get Single Goal", False, f"Exception: {str(e)}")
        return None

def test_update_goal(goal_id):
    """Test 5: PUT /api/goal-setter/goals/{goal_id}"""
    try:
        update_data = {
            "status": "completed",
            "progress_pct": 100,
            "notes": "Successfully launched and achieved MRR target!"
        }
        
        resp = requests.put(
            f"{BASE_URL}/goal-setter/goals/{goal_id}",
            json=update_data,
            headers=get_headers(),
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "completed" and data.get("progress_pct") == 100:
                log_test("Update Goal", True, f"Updated goal to completed with 100% progress")
                return data
            else:
                log_test("Update Goal", False, "Update not reflected in response")
                return None
        else:
            log_test("Update Goal", False, f"Status: {resp.status_code}")
            return None
    except Exception as e:
        log_test("Update Goal", False, f"Exception: {str(e)}")
        return None

def test_goal_dashboard():
    """Test 6: GET /api/goal-setter/dashboard"""
    try:
        resp = requests.get(
            f"{BASE_URL}/goal-setter/dashboard",
            headers=get_headers(),
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            required_fields = ["total_goals", "active_goals", "completed_goals", "avg_progress"]
            has_all = all(f in data for f in required_fields)
            
            if has_all:
                log_test("Goal Dashboard", True, 
                    f"Total: {data['total_goals']}, Active: {data['active_goals']}, "
                    f"Completed: {data['completed_goals']}, Avg Progress: {data['avg_progress']}%")
                return data
            else:
                log_test("Goal Dashboard", False, "Missing required dashboard fields")
                return None
        else:
            log_test("Goal Dashboard", False, f"Status: {resp.status_code}")
            return None
    except Exception as e:
        log_test("Goal Dashboard", False, f"Exception: {str(e)}")
        return None

def test_delete_goal(goal_id):
    """Test 7: DELETE /api/goal-setter/goals/{goal_id}"""
    try:
        resp = requests.delete(
            f"{BASE_URL}/goal-setter/goals/{goal_id}",
            headers=get_headers(),
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("deleted") == True:
                log_test("Delete Goal", True, f"Deleted goal {goal_id}")
                return True
            else:
                log_test("Delete Goal", False, "Delete confirmation not received")
                return False
        else:
            log_test("Delete Goal", False, f"Status: {resp.status_code}")
            return False
    except Exception as e:
        log_test("Delete Goal", False, f"Exception: {str(e)}")
        return False

# ═══════════════════════════════════════════════════════════════
# MODULE 2: GOAL MANIFESTATION TESTS
# ═══════════════════════════════════════════════════════════════

def test_manifestation_framework():
    """Test 8: GET /api/goal-manifestation/framework"""
    print("\n=== MODULE 2: GOAL MANIFESTATION (CAB-FAME) ===")
    try:
        resp = requests.get(f"{BASE_URL}/goal-manifestation/framework", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            stages = data.get("stages", [])
            
            # Verify 7 stages
            has_7_stages = len(stages) == 7
            
            # Verify Stage 4 has audio_url (KalphaVriksha)
            stage_4 = next((s for s in stages if s.get("stage_number") == 4), None)
            stage_4_has_audio = stage_4 and "audio_url" in stage_4
            
            # Verify Stage 1 step 1.1 and 1.6 have YouTube links
            stage_1 = next((s for s in stages if s.get("stage_number") == 1), None)
            stage_1_steps = stage_1.get("steps", []) if stage_1 else []
            step_1_1 = next((s for s in stage_1_steps if s.get("id") == "1.1"), None)
            step_1_6 = next((s for s in stage_1_steps if s.get("id") == "1.6"), None)
            has_youtube_links = (step_1_1 and "link" in step_1_1) and (step_1_6 and "link" in step_1_6)
            
            if has_7_stages and stage_4_has_audio and has_youtube_links:
                log_test("Manifestation Framework", True, 
                    f"7 stages (C,A,B,F,A,M,E), Stage 4 has audio_url, Stage 1 has YouTube links")
                return data
            else:
                details = []
                if not has_7_stages:
                    details.append(f"Expected 7 stages, got {len(stages)}")
                if not stage_4_has_audio:
                    details.append("Stage 4 missing audio_url")
                if not has_youtube_links:
                    details.append("Stage 1 missing YouTube links")
                log_test("Manifestation Framework", False, "; ".join(details))
                return None
        else:
            log_test("Manifestation Framework", False, f"Status: {resp.status_code}")
            return None
    except Exception as e:
        log_test("Manifestation Framework", False, f"Exception: {str(e)}")
        return None

def test_create_journey():
    """Test 9: POST /api/goal-manifestation/journeys"""
    try:
        journey_data = {
            "wish": "Become a successful entrepreneur with ₹1Cr annual revenue",
            "life_area": "career",
            "current_stage": 1,
            "stage_inputs": {
                "2.2": "Leadership & Innovation"
            },
            "status": "active",
            "notes": "Starting my manifestation journey"
        }
        
        resp = requests.post(
            f"{BASE_URL}/goal-manifestation/journeys",
            json=journey_data,
            headers=get_headers(),
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            has_id = "journey_id" in data
            has_wish = data.get("wish") == journey_data["wish"]
            has_stage = data.get("current_stage") == 1
            has_inputs = "2.2" in data.get("stage_inputs", {})
            
            if has_id and has_wish and has_stage and has_inputs:
                log_test("Create Journey", True, f"Journey created: {data['journey_id']}")
                return data
            else:
                log_test("Create Journey", False, "Missing required fields in response")
                return None
        else:
            log_test("Create Journey", False, f"Status: {resp.status_code}, Response: {resp.text}")
            return None
    except Exception as e:
        log_test("Create Journey", False, f"Exception: {str(e)}")
        return None

def test_list_journeys():
    """Test 10: GET /api/goal-manifestation/journeys"""
    try:
        resp = requests.get(
            f"{BASE_URL}/goal-manifestation/journeys",
            headers=get_headers(),
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                log_test("List Journeys", True, f"Retrieved {len(data)} journeys")
                return data
            else:
                log_test("List Journeys", False, "Response is not a list")
                return None
        else:
            log_test("List Journeys", False, f"Status: {resp.status_code}")
            return None
    except Exception as e:
        log_test("List Journeys", False, f"Exception: {str(e)}")
        return None

def test_get_journey(journey_id):
    """Test 11: GET /api/goal-manifestation/journeys/{id}"""
    try:
        resp = requests.get(
            f"{BASE_URL}/goal-manifestation/journeys/{journey_id}",
            headers=get_headers(),
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("journey_id") == journey_id:
                log_test("Get Journey", True, f"Retrieved journey {journey_id}")
                return data
            else:
                log_test("Get Journey", False, "Journey ID mismatch")
                return None
        else:
            log_test("Get Journey", False, f"Status: {resp.status_code}")
            return None
    except Exception as e:
        log_test("Get Journey", False, f"Exception: {str(e)}")
        return None

def test_update_journey(journey_id):
    """Test 12: PUT /api/goal-manifestation/journeys/{id}"""
    try:
        update_data = {
            "current_stage": 3,
            "stage_inputs": {
                "2.2": "Leadership & Innovation",
                "5.1": "Called potential investors",
                "5.6": "Daily meditation and business planning"
            },
            "notes": "Progressing through stages, feeling more aligned"
        }
        
        resp = requests.put(
            f"{BASE_URL}/goal-manifestation/journeys/{journey_id}",
            json=update_data,
            headers=get_headers(),
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("current_stage") == 3 and "5.1" in data.get("stage_inputs", {}):
                log_test("Update Journey", True, f"Advanced to stage 3, added more stage_inputs")
                return data
            else:
                log_test("Update Journey", False, "Update not reflected in response")
                return None
        else:
            log_test("Update Journey", False, f"Status: {resp.status_code}")
            return None
    except Exception as e:
        log_test("Update Journey", False, f"Exception: {str(e)}")
        return None

def test_manifestation_dashboard():
    """Test 13: GET /api/goal-manifestation/dashboard"""
    try:
        resp = requests.get(
            f"{BASE_URL}/goal-manifestation/dashboard",
            headers=get_headers(),
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            required_fields = ["total_journeys", "active", "manifested"]
            has_all = all(f in data for f in required_fields)
            
            if has_all:
                log_test("Manifestation Dashboard", True, 
                    f"Total: {data['total_journeys']}, Active: {data['active']}, Manifested: {data['manifested']}")
                return data
            else:
                log_test("Manifestation Dashboard", False, "Missing required dashboard fields")
                return None
        else:
            log_test("Manifestation Dashboard", False, f"Status: {resp.status_code}")
            return None
    except Exception as e:
        log_test("Manifestation Dashboard", False, f"Exception: {str(e)}")
        return None

def test_delete_journey(journey_id):
    """Test 14: DELETE /api/goal-manifestation/journeys/{id}"""
    try:
        resp = requests.delete(
            f"{BASE_URL}/goal-manifestation/journeys/{journey_id}",
            headers=get_headers(),
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("deleted") == True:
                log_test("Delete Journey", True, f"Deleted journey {journey_id}")
                return True
            else:
                log_test("Delete Journey", False, "Delete confirmation not received")
                return False
        else:
            log_test("Delete Journey", False, f"Status: {resp.status_code}")
            return False
    except Exception as e:
        log_test("Delete Journey", False, f"Exception: {str(e)}")
        return False

# ═══════════════════════════════════════════════════════════════
# MODULE 3: UNCONDITIONAL HAPPINESS TESTS
# ═══════════════════════════════════════════════════════════════

def test_happiness_framework():
    """Test 15: GET /api/unconditional-happiness/framework"""
    print("\n=== MODULE 3: UNCONDITIONAL HAPPINESS ===")
    try:
        resp = requests.get(f"{BASE_URL}/unconditional-happiness/framework", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            
            # Verify 4 phases
            phases = data.get("phases", [])
            has_4_phases = len(phases) == 4
            
            # Verify audio_url (Joy.mp3)
            has_audio = "audio_url" in data
            
            if has_4_phases and has_audio:
                log_test("Happiness Framework", True, f"4 phases with audio_url (Joy.mp3)")
                return data
            else:
                details = []
                if not has_4_phases:
                    details.append(f"Expected 4 phases, got {len(phases)}")
                if not has_audio:
                    details.append("Missing audio_url")
                log_test("Happiness Framework", False, "; ".join(details))
                return None
        else:
            log_test("Happiness Framework", False, f"Status: {resp.status_code}")
            return None
    except Exception as e:
        log_test("Happiness Framework", False, f"Exception: {str(e)}")
        return None

def test_create_session():
    """Test 16: POST /api/unconditional-happiness/sessions"""
    try:
        session_data = {
            "reflections": {
                "1": "I remember playing in the garden as a child, completely carefree and joyful",
                "2": "I was attaching happiness to career success, financial goals, and others' approval",
                "3": "Unconditional happiness feels light, free, and expansive in my chest",
                "4": "I will smile more and appreciate small moments throughout the day"
            },
            "happiness_before": 4,
            "happiness_after": 8,
            "listened_audio": True,
            "completed": True,
            "notes": "Powerful session, felt a real shift in perspective"
        }
        
        resp = requests.post(
            f"{BASE_URL}/unconditional-happiness/sessions",
            json=session_data,
            headers=get_headers(),
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            has_id = "session_id" in data
            has_reflections = len(data.get("reflections", {})) == 4
            has_ratings = data.get("happiness_before") == 4 and data.get("happiness_after") == 8
            has_audio = data.get("listened_audio") == True
            
            if has_id and has_reflections and has_ratings and has_audio:
                log_test("Create Happiness Session", True, 
                    f"Session created: {data['session_id']}, Happiness: 4→8")
                return data
            else:
                log_test("Create Happiness Session", False, "Missing required fields in response")
                return None
        else:
            log_test("Create Happiness Session", False, f"Status: {resp.status_code}, Response: {resp.text}")
            return None
    except Exception as e:
        log_test("Create Happiness Session", False, f"Exception: {str(e)}")
        return None

def test_list_sessions():
    """Test 17: GET /api/unconditional-happiness/sessions"""
    try:
        resp = requests.get(
            f"{BASE_URL}/unconditional-happiness/sessions",
            headers=get_headers(),
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                log_test("List Happiness Sessions", True, f"Retrieved {len(data)} sessions")
                return data
            else:
                log_test("List Happiness Sessions", False, "Response is not a list")
                return None
        else:
            log_test("List Happiness Sessions", False, f"Status: {resp.status_code}")
            return None
    except Exception as e:
        log_test("List Happiness Sessions", False, f"Exception: {str(e)}")
        return None

def test_happiness_dashboard():
    """Test 18: GET /api/unconditional-happiness/dashboard"""
    try:
        resp = requests.get(
            f"{BASE_URL}/unconditional-happiness/dashboard",
            headers=get_headers(),
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            required_fields = ["total_sessions", "current_streak", "best_streak", "avg_happiness_improvement"]
            has_all = all(f in data for f in required_fields)
            
            if has_all:
                log_test("Happiness Dashboard", True, 
                    f"Total: {data['total_sessions']}, Streak: {data['current_streak']}, "
                    f"Best: {data['best_streak']}, Avg Improvement: {data['avg_happiness_improvement']}")
                return data
            else:
                log_test("Happiness Dashboard", False, "Missing required dashboard fields")
                return None
        else:
            log_test("Happiness Dashboard", False, f"Status: {resp.status_code}")
            return None
    except Exception as e:
        log_test("Happiness Dashboard", False, f"Exception: {str(e)}")
        return None

def test_happiness_streak():
    """Test consecutive day streak increment"""
    try:
        # Create another session (same day - should not increment streak)
        session_data = {
            "reflections": {"1": "Second session today"},
            "happiness_before": 5,
            "happiness_after": 7,
            "listened_audio": True,
            "completed": True
        }
        
        resp = requests.post(
            f"{BASE_URL}/unconditional-happiness/sessions",
            json=session_data,
            headers=get_headers(),
            timeout=10
        )
        
        if resp.status_code == 200:
            # Check dashboard
            dash_resp = requests.get(
                f"{BASE_URL}/unconditional-happiness/dashboard",
                headers=get_headers(),
                timeout=10
            )
            
            if dash_resp.status_code == 200:
                data = dash_resp.json()
                # Same day should keep streak at 1
                if data.get("current_streak") == 1:
                    log_test("Happiness Streak Logic", True, 
                        f"Same-day sessions don't increment streak (streak={data['current_streak']})")
                    return True
                else:
                    log_test("Happiness Streak Logic", False, 
                        f"Expected streak=1, got {data.get('current_streak')}")
                    return False
            else:
                log_test("Happiness Streak Logic", False, f"Dashboard status: {dash_resp.status_code}")
                return False
        else:
            log_test("Happiness Streak Logic", False, f"Session creation status: {resp.status_code}")
            return False
    except Exception as e:
        log_test("Happiness Streak Logic", False, f"Exception: {str(e)}")
        return False

# ═══════════════════════════════════════════════════════════════
# MAIN TEST EXECUTION
# ═══════════════════════════════════════════════════════════════

def run_all_tests():
    """Run all tests in sequence"""
    print("=" * 80)
    print("BACKEND API TESTING - 3 NEW MODULES")
    print("Goal Setter, Goal Manifestation, Unconditional Happiness")
    print("=" * 80)
    
    # Authentication
    if not register_and_login():
        print("\n❌ Authentication failed. Cannot proceed with tests.")
        return
    
    # MODULE 1: Goal Setter (7 endpoints)
    test_goal_setter_framework()
    goal = test_create_goal()
    test_list_goals()
    if goal:
        goal_id = goal.get("goal_id")
        test_get_goal(goal_id)
        test_update_goal(goal_id)
        test_goal_dashboard()
        test_delete_goal(goal_id)
    
    # MODULE 2: Goal Manifestation (6 endpoints)
    test_manifestation_framework()
    journey = test_create_journey()
    test_list_journeys()
    if journey:
        journey_id = journey.get("journey_id")
        test_get_journey(journey_id)
        test_update_journey(journey_id)
        test_manifestation_dashboard()
        test_delete_journey(journey_id)
    
    # MODULE 3: Unconditional Happiness (4 endpoints)
    test_happiness_framework()
    test_create_session()
    test_list_sessions()
    test_happiness_dashboard()
    test_happiness_streak()
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for r in test_results if "✅ PASS" in r)
    failed = sum(1 for r in test_results if "❌ FAIL" in r)
    total = len(test_results)
    
    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")
    print(f"Success Rate: {(passed/total*100):.1f}%")
    
    print("\n" + "=" * 80)
    print("DETAILED RESULTS")
    print("=" * 80)
    for result in test_results:
        print(result)
    
    return passed, failed, total

if __name__ == "__main__":
    run_all_tests()
