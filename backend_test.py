"""
Conflict Breaker Backend API Testing
Tests all 9-stage guided tool endpoints
"""
import requests
import json
import time
from datetime import datetime

# Backend URL from frontend/.env
BASE_URL = "https://dezider-core.preview.emergentagent.com/api"

# Test results tracking
test_results = []

def log_test(test_name, passed, details=""):
    """Log test result"""
    status = "✅ PASSED" if passed else "❌ FAILED"
    result = f"{status}: {test_name}"
    if details:
        result += f" - {details}"
    print(result)
    test_results.append({"test": test_name, "passed": passed, "details": details})

def test_conflict_breaker():
    """Test complete Conflict Breaker workflow"""
    
    print("\n" + "="*80)
    print("CONFLICT BREAKER BACKEND API TESTING")
    print("="*80 + "\n")
    
    # Generate unique test user
    timestamp = int(time.time())
    test_email = f"conflict.tester.{timestamp}@workplace.com"
    test_password = "SecurePass123!"
    test_name = "Maya Chen"
    
    session_token = None
    session_id = None
    
    # ========================================================================
    # TEST 1: User Registration
    # ========================================================================
    print("\n[TEST 1] User Registration")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json={
                "name": test_name,
                "email": test_email,
                "password": test_password
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            session_token = data.get("session_token")
            if session_token:
                log_test("User Registration", True, f"Registered {test_email}")
            else:
                log_test("User Registration", False, "No session_token in response")
        else:
            log_test("User Registration", False, f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("User Registration", False, f"Exception: {str(e)}")
        return
    
    # ========================================================================
    # TEST 2: User Login
    # ========================================================================
    print("\n[TEST 2] User Login")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": test_email,
                "password": test_password
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            session_token = data.get("session_token")
            if session_token:
                log_test("User Login", True, f"Login successful")
            else:
                log_test("User Login", False, "No session_token in response")
        else:
            log_test("User Login", False, f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("User Login", False, f"Exception: {str(e)}")
        return
    
    # Headers for authenticated requests
    headers = {"Authorization": f"Bearer {session_token}"}
    
    # ========================================================================
    # TEST 3: GET /api/conflict-breaker/meta
    # ========================================================================
    print("\n[TEST 3] GET /api/conflict-breaker/meta")
    try:
        response = requests.get(
            f"{BASE_URL}/conflict-breaker/meta",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            stages = data.get("stages", [])
            silence_patterns = data.get("silence_patterns", [])
            violence_patterns = data.get("violence_patterns", [])
            
            if len(stages) == 9 and len(silence_patterns) > 0 and len(violence_patterns) > 0:
                log_test("GET /api/conflict-breaker/meta", True, 
                        f"9 stages, {len(silence_patterns)} silence patterns, {len(violence_patterns)} violence patterns")
            else:
                log_test("GET /api/conflict-breaker/meta", False, 
                        f"Expected 9 stages, got {len(stages)}")
        else:
            log_test("GET /api/conflict-breaker/meta", False, 
                    f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("GET /api/conflict-breaker/meta", False, f"Exception: {str(e)}")
    
    # ========================================================================
    # TEST 4: POST /api/conflict-breaker/sessions (Create Session)
    # ========================================================================
    print("\n[TEST 4] POST /api/conflict-breaker/sessions")
    try:
        response = requests.post(
            f"{BASE_URL}/conflict-breaker/sessions",
            headers=headers,
            json={
                "title": "Discuss project delay with partner",
                "conversation_type": "prepare",
                "other_party_role": "co-founder"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            session_id = data.get("session_id")
            if session_id:
                log_test("POST /api/conflict-breaker/sessions", True, 
                        f"Session created: {session_id}")
            else:
                log_test("POST /api/conflict-breaker/sessions", False, 
                        "No session_id in response")
                return
        else:
            log_test("POST /api/conflict-breaker/sessions", False, 
                    f"Status {response.status_code}: {response.text}")
            return
    except Exception as e:
        log_test("POST /api/conflict-breaker/sessions", False, f"Exception: {str(e)}")
        return
    
    # ========================================================================
    # TEST 5: GET /api/conflict-breaker/sessions (List Sessions)
    # ========================================================================
    print("\n[TEST 5] GET /api/conflict-breaker/sessions")
    try:
        response = requests.get(
            f"{BASE_URL}/conflict-breaker/sessions",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                log_test("GET /api/conflict-breaker/sessions", True, 
                        f"Found {len(data)} session(s)")
            else:
                log_test("GET /api/conflict-breaker/sessions", False, 
                        "Expected list with sessions")
        else:
            log_test("GET /api/conflict-breaker/sessions", False, 
                    f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("GET /api/conflict-breaker/sessions", False, f"Exception: {str(e)}")
    
    # ========================================================================
    # TEST 6: POST /api/conflict-breaker/sessions/{sid}/crucial-check (Stage 1)
    # ========================================================================
    print("\n[TEST 6] POST /api/conflict-breaker/sessions/{sid}/crucial-check")
    try:
        response = requests.post(
            f"{BASE_URL}/conflict-breaker/sessions/{session_id}/crucial-check",
            headers=headers,
            json={
                "about": "Project delay discussion",
                "who_involved": "Co-founder Ravi",
                "at_stake": "Trust and investor confidence",
                "opinions_differ": "I think we missed the deadline, he thinks it was unavoidable",
                "emotions_strong": "I feel frustrated and disappointed",
                "if_avoid": "The problem will repeat",
                "if_handle_poorly": "He may feel attacked",
                "desired_result": "Clarity and accountability",
                "stakes_score": 7,
                "emotion_score": 6,
                "opinion_difference_score": 5,
                "relationship_sensitivity_score": 7,
                "urgency_score": 8
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            classification = data.get("classification")
            if classification:
                log_test("POST crucial-check (Stage 1)", True, 
                        f"Classification: {classification}")
            else:
                log_test("POST crucial-check (Stage 1)", False, 
                        "No classification in response")
        else:
            log_test("POST crucial-check (Stage 1)", False, 
                    f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("POST crucial-check (Stage 1)", False, f"Exception: {str(e)}")
    
    # ========================================================================
    # TEST 7: POST /api/conflict-breaker/sessions/{sid}/motive-clarity (Stage 2)
    # ========================================================================
    print("\n[TEST 7] POST /api/conflict-breaker/sessions/{sid}/motive-clarity")
    try:
        response = requests.post(
            f"{BASE_URL}/conflict-breaker/sessions/{session_id}/motive-clarity",
            headers=headers,
            json={
                "want_for_self": "To be heard",
                "want_for_other": "To understand without attack",
                "want_for_relationship": "Keep trust intact",
                "what_i_want": "Accountability",
                "what_i_do_not_want": "Insulting him"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if "want_for_self" in data:
                log_test("POST motive-clarity (Stage 2)", True, 
                        "Motive clarity saved")
            else:
                log_test("POST motive-clarity (Stage 2)", False, 
                        "Missing expected fields")
        else:
            log_test("POST motive-clarity (Stage 2)", False, 
                    f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("POST motive-clarity (Stage 2)", False, f"Exception: {str(e)}")
    
    # ========================================================================
    # TEST 8: POST /api/conflict-breaker/sessions/{sid}/safety-diagnosis (Stage 3)
    # ========================================================================
    print("\n[TEST 8] POST /api/conflict-breaker/sessions/{sid}/safety-diagnosis")
    try:
        response = requests.post(
            f"{BASE_URL}/conflict-breaker/sessions/{session_id}/safety-diagnosis",
            headers=headers,
            json={
                "visible_topic": "Missed deadline",
                "hidden_emotional_issue": "Feel ignored",
                "user_pattern": "silence",
                "user_subpatterns": ["Avoiding", "Masking"],
                "other_pattern": "violence",
                "other_subpatterns": ["Blaming"]
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if "user_pattern" in data and "other_pattern" in data:
                log_test("POST safety-diagnosis (Stage 3)", True, 
                        f"Patterns: {data['user_pattern']} / {data['other_pattern']}")
            else:
                log_test("POST safety-diagnosis (Stage 3)", False, 
                        "Missing expected fields")
        else:
            log_test("POST safety-diagnosis (Stage 3)", False, 
                    f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("POST safety-diagnosis (Stage 3)", False, f"Exception: {str(e)}")
    
    # ========================================================================
    # TEST 9: POST /api/conflict-breaker/sessions/{sid}/make-safe (Stage 4)
    # ========================================================================
    print("\n[TEST 9] POST /api/conflict-breaker/sessions/{sid}/make-safe")
    try:
        response = requests.post(
            f"{BASE_URL}/conflict-breaker/sessions/{session_id}/make-safe",
            headers=headers,
            json={
                "safety_repair_method": "contrasting",
                "mutual_purpose_at_risk": "Yes, he thinks I only blame",
                "mutual_respect_at_risk": "He may feel judged",
                "contrast_they_wrongly_think": "He thinks I am blaming",
                "contrast_i_actually_mean": "I want process improvement"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if "safety_repair_method" in data:
                log_test("POST make-safe (Stage 4)", True, 
                        f"Repair method: {data['safety_repair_method']}")
            else:
                log_test("POST make-safe (Stage 4)", False, 
                        "Missing expected fields")
        else:
            log_test("POST make-safe (Stage 4)", False, 
                    f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("POST make-safe (Stage 4)", False, f"Exception: {str(e)}")
    
    # ========================================================================
    # TEST 10: POST /api/conflict-breaker/sessions/{sid}/story-map (Stage 5)
    # ========================================================================
    print("\n[TEST 10] POST /api/conflict-breaker/sessions/{sid}/story-map")
    try:
        response = requests.post(
            f"{BASE_URL}/conflict-breaker/sessions/{session_id}/story-map",
            headers=headers,
            json={
                "what_i_saw_heard": "Report was 5 days late",
                "observable_facts": "Deadline was Monday, delivered Saturday",
                "meaning_i_added": "He does not care about deadlines",
                "assumed_motive": "Lazy attitude",
                "emotion": "Frustration",
                "emotional_intensity": 7,
                "clever_story_type": "villain"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if "emotion" in data and "clever_story_type" in data:
                log_test("POST story-map (Stage 5)", True, 
                        f"Story type: {data['clever_story_type']}, Emotion: {data['emotion']}")
            else:
                log_test("POST story-map (Stage 5)", False, 
                        "Missing expected fields")
        else:
            log_test("POST story-map (Stage 5)", False, 
                    f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("POST story-map (Stage 5)", False, f"Exception: {str(e)}")
    
    # ========================================================================
    # TEST 11: POST /api/conflict-breaker/sessions/{sid}/script-builder (Stage 6)
    # ========================================================================
    print("\n[TEST 11] POST /api/conflict-breaker/sessions/{sid}/script-builder")
    try:
        response = requests.post(
            f"{BASE_URL}/conflict-breaker/sessions/{session_id}/script-builder",
            headers=headers,
            json={
                "facts_to_begin": "The report was delivered 5 days late",
                "my_interpretation": "I am worried about investor impact",
                "tentative_framing": "I may be wrong but",
                "question_to_invite": "How do you see it?",
                "what_to_avoid": "Never say always or lazy"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if "facts_to_begin" in data:
                log_test("POST script-builder (Stage 6)", True, 
                        "Script builder saved")
            else:
                log_test("POST script-builder (Stage 6)", False, 
                        "Missing expected fields")
        else:
            log_test("POST script-builder (Stage 6)", False, 
                    f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("POST script-builder (Stage 6)", False, f"Exception: {str(e)}")
    
    # ========================================================================
    # TEST 12: POST /api/conflict-breaker/sessions/{sid}/listening-plan (Stage 7)
    # ========================================================================
    print("\n[TEST 12] POST /api/conflict-breaker/sessions/{sid}/listening-plan")
    try:
        response = requests.post(
            f"{BASE_URL}/conflict-breaker/sessions/{session_id}/listening-plan",
            headers=headers,
            json={
                "ask_question": "What happened from your side?",
                "mirror_statement": "You seem stressed",
                "what_they_feel": "Pressured",
                "what_they_fear": "Being blamed",
                "what_they_want": "More time"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if "ask_question" in data:
                log_test("POST listening-plan (Stage 7)", True, 
                        "Listening plan saved")
            else:
                log_test("POST listening-plan (Stage 7)", False, 
                        "Missing expected fields")
        else:
            log_test("POST listening-plan (Stage 7)", False, 
                    f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("POST listening-plan (Stage 7)", False, f"Exception: {str(e)}")
    
    # ========================================================================
    # TEST 13: POST /api/conflict-breaker/sessions/{sid}/action-plan (Stage 8)
    # ========================================================================
    print("\n[TEST 13] POST /api/conflict-breaker/sessions/{sid}/action-plan")
    try:
        response = requests.post(
            f"{BASE_URL}/conflict-breaker/sessions/{session_id}/action-plan",
            headers=headers,
            json={
                "decision_method": "consult",
                "final_decision": "Weekly updates every Friday",
                "owner": "Ravi",
                "task": "Send weekly progress report",
                "deadline": "Every Friday 5 PM",
                "followup_date": "Next Monday"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if "decision_method" in data and "final_decision" in data:
                log_test("POST action-plan (Stage 8)", True, 
                        f"Decision method: {data['decision_method']}")
            else:
                log_test("POST action-plan (Stage 8)", False, 
                        "Missing expected fields")
        else:
            log_test("POST action-plan (Stage 8)", False, 
                    f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("POST action-plan (Stage 8)", False, f"Exception: {str(e)}")
    
    # ========================================================================
    # TEST 14: POST /api/conflict-breaker/sessions/{sid}/closure (Stage 9)
    # ========================================================================
    print("\n[TEST 14] POST /api/conflict-breaker/sessions/{sid}/closure")
    try:
        response = requests.post(
            f"{BASE_URL}/conflict-breaker/sessions/{session_id}/closure",
            headers=headers,
            json={
                "journal_content": "Good conversation, agreed on weekly updates",
                "personal_learning": "Starting with facts works better",
                "resolved_status": "resolved"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if "journal_content" in data and "resolved_status" in data:
                log_test("POST closure (Stage 9)", True, 
                        f"Status: {data['resolved_status']}")
            else:
                log_test("POST closure (Stage 9)", False, 
                        "Missing expected fields")
        else:
            log_test("POST closure (Stage 9)", False, 
                    f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("POST closure (Stage 9)", False, f"Exception: {str(e)}")
    
    # ========================================================================
    # TEST 15: GET /api/conflict-breaker/sessions/{sid}/full
    # ========================================================================
    print("\n[TEST 15] GET /api/conflict-breaker/sessions/{sid}/full")
    try:
        response = requests.get(
            f"{BASE_URL}/conflict-breaker/sessions/{session_id}/full",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            required_keys = ["session", "crucial_check", "motive_clarity", "safety_diagnosis", 
                           "make_safe", "story_map", "script_builder", "listening_plan", 
                           "action_plan", "closure"]
            
            missing_keys = [k for k in required_keys if k not in data]
            if not missing_keys:
                log_test("GET /api/conflict-breaker/sessions/{sid}/full", True, 
                        "All stage data retrieved")
            else:
                log_test("GET /api/conflict-breaker/sessions/{sid}/full", False, 
                        f"Missing keys: {missing_keys}")
        else:
            log_test("GET /api/conflict-breaker/sessions/{sid}/full", False, 
                    f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("GET /api/conflict-breaker/sessions/{sid}/full", False, f"Exception: {str(e)}")
    
    # ========================================================================
    # TEST 16: POST /api/conflict-breaker/sessions/{sid}/ai-generate/crucial_check
    # ========================================================================
    print("\n[TEST 16] POST /api/conflict-breaker/sessions/{sid}/ai-generate/crucial_check")
    try:
        response = requests.post(
            f"{BASE_URL}/conflict-breaker/sessions/{session_id}/ai-generate/crucial_check",
            headers=headers,
            timeout=30  # AI calls may take longer
        )
        
        if response.status_code == 200:
            data = response.json()
            if "stage" in data and "ai_output" in data:
                ai_output_preview = data["ai_output"][:100] + "..." if len(data["ai_output"]) > 100 else data["ai_output"]
                log_test("POST ai-generate/crucial_check", True, 
                        f"AI output generated: {ai_output_preview}")
            else:
                log_test("POST ai-generate/crucial_check", False, 
                        "Missing stage or ai_output in response")
        else:
            log_test("POST ai-generate/crucial_check", False, 
                    f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("POST ai-generate/crucial_check", False, f"Exception: {str(e)}")
    
    # ========================================================================
    # TEST 17: GET /api/conflict-breaker/dashboard
    # ========================================================================
    print("\n[TEST 17] GET /api/conflict-breaker/dashboard")
    try:
        response = requests.get(
            f"{BASE_URL}/conflict-breaker/dashboard",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            total_sessions = data.get("total_sessions", 0)
            by_status = data.get("by_status", {})
            
            if total_sessions > 0:
                log_test("GET /api/conflict-breaker/dashboard", True, 
                        f"Total sessions: {total_sessions}, Status breakdown: {by_status}")
            else:
                log_test("GET /api/conflict-breaker/dashboard", False, 
                        "Expected at least 1 session")
        else:
            log_test("GET /api/conflict-breaker/dashboard", False, 
                    f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("GET /api/conflict-breaker/dashboard", False, f"Exception: {str(e)}")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed_count = sum(1 for r in test_results if r["passed"])
    total_count = len(test_results)
    
    print(f"\nTotal Tests: {total_count}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {total_count - passed_count}")
    print(f"Success Rate: {(passed_count/total_count*100):.1f}%\n")
    
    # Show failed tests
    failed_tests = [r for r in test_results if not r["passed"]]
    if failed_tests:
        print("\n❌ FAILED TESTS:")
        for r in failed_tests:
            print(f"  - {r['test']}: {r['details']}")
    else:
        print("\n🎉 ALL TESTS PASSED!")
    
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    test_conflict_breaker()
