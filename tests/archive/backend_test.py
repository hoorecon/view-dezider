"""
Backend Testing Script for AI Solution Assistant, CLD Refinements, and Conflict Breaker AI Fix
Tests all endpoints with proper authentication flow.
"""
import requests
import time
import json

# Backend URL from frontend/.env
BASE_URL = "https://dezider-core.preview.emergentagent.com/api"

# Test user credentials
timestamp = int(time.time())
TEST_EMAIL = f"aitest_{timestamp}@test.com"
TEST_PASSWORD = "test123456"
TEST_NAME = "AI Test User"

# Global session token
session_token = None

def print_test(test_name):
    """Print test header"""
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"{'='*80}")

def print_result(success, message, data=None):
    """Print test result"""
    status = "✅ PASSED" if success else "❌ FAILED"
    print(f"{status}: {message}")
    if data:
        print(f"Response: {json.dumps(data, indent=2)[:500]}")

def register_and_login():
    """Register a new user and login to get session token"""
    global session_token
    
    print_test("User Registration and Login")
    
    # Register
    register_data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "name": TEST_NAME
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/auth/register", json=register_data, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            session_token = data.get("session_token")
            print_result(True, f"Registration successful. User: {TEST_EMAIL}", {"user_id": data.get("user_id")})
        else:
            print_result(False, f"Registration failed: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print_result(False, f"Registration error: {str(e)}")
        return False
    
    return session_token is not None

def get_headers():
    """Get authorization headers"""
    return {"Authorization": f"Bearer {session_token}"}

# ============================================================================
# FEATURE 1: AI SOLUTION ASSISTANT TESTS
# ============================================================================

def test_ai_assistant_meta():
    """Test GET /api/ai-assistant/meta"""
    print_test("AI Assistant Meta - GET /api/ai-assistant/meta")
    
    try:
        resp = requests.get(f"{BASE_URL}/ai-assistant/meta", timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            languages = data.get("languages", {})
            capabilities = data.get("capabilities", [])
            
            # Verify expected languages
            expected_langs = ["en", "ta", "te", "kn", "ml", "hi"]
            has_all_langs = all(lang in languages for lang in expected_langs)
            
            print_result(
                has_all_langs and len(capabilities) > 0,
                f"Meta endpoint returns {len(languages)} languages and {len(capabilities)} capabilities",
                {"languages": list(languages.keys()), "capabilities_count": len(capabilities)}
            )
            return has_all_langs
        else:
            print_result(False, f"Meta endpoint failed: {resp.status_code}")
            return False
    except Exception as e:
        print_result(False, f"Meta endpoint error: {str(e)}")
        return False

def test_ai_assistant_create_conversation():
    """Test POST /api/ai-assistant/conversations"""
    print_test("AI Assistant Create Conversation - POST /api/ai-assistant/conversations")
    
    try:
        data = {
            "title": "Test Chat",
            "language": "en"
        }
        resp = requests.post(f"{BASE_URL}/ai-assistant/conversations", json=data, headers=get_headers(), timeout=30)
        
        if resp.status_code == 200:
            result = resp.json()
            conv_id = result.get("conversation_id")
            print_result(
                conv_id is not None,
                f"Conversation created successfully",
                {"conversation_id": conv_id, "title": result.get("title"), "language": result.get("language")}
            )
            return conv_id
        else:
            print_result(False, f"Create conversation failed: {resp.status_code} - {resp.text}")
            return None
    except Exception as e:
        print_result(False, f"Create conversation error: {str(e)}")
        return None

def test_ai_assistant_list_conversations():
    """Test GET /api/ai-assistant/conversations"""
    print_test("AI Assistant List Conversations - GET /api/ai-assistant/conversations")
    
    try:
        resp = requests.get(f"{BASE_URL}/ai-assistant/conversations", headers=get_headers(), timeout=30)
        
        if resp.status_code == 200:
            convos = resp.json()
            print_result(
                isinstance(convos, list),
                f"List conversations returned {len(convos)} conversations",
                {"count": len(convos)}
            )
            return True
        else:
            print_result(False, f"List conversations failed: {resp.status_code}")
            return False
    except Exception as e:
        print_result(False, f"List conversations error: {str(e)}")
        return False

def test_ai_assistant_get_conversation(conv_id):
    """Test GET /api/ai-assistant/conversations/{conv_id}"""
    print_test(f"AI Assistant Get Conversation - GET /api/ai-assistant/conversations/{conv_id}")
    
    try:
        resp = requests.get(f"{BASE_URL}/ai-assistant/conversations/{conv_id}", headers=get_headers(), timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            print_result(
                data.get("conversation_id") == conv_id,
                f"Get conversation successful",
                {"conversation_id": data.get("conversation_id"), "message_count": len(data.get("messages", []))}
            )
            return True
        else:
            print_result(False, f"Get conversation failed: {resp.status_code}")
            return False
    except Exception as e:
        print_result(False, f"Get conversation error: {str(e)}")
        return False

def test_ai_assistant_send_message(conv_id):
    """Test POST /api/ai-assistant/conversations/{conv_id}/message (LLM call)"""
    print_test(f"AI Assistant Send Message - POST /api/ai-assistant/conversations/{conv_id}/message")
    
    try:
        data = {
            "message": "What should I focus on this week?"
        }
        resp = requests.post(
            f"{BASE_URL}/ai-assistant/conversations/{conv_id}/message",
            json=data,
            headers=get_headers(),
            timeout=60  # Longer timeout for LLM call
        )
        
        if resp.status_code == 200:
            result = resp.json()
            ai_response = result.get("ai_response")
            print_result(
                ai_response is not None and len(ai_response) > 0,
                f"AI response received ({len(ai_response)} chars)",
                {"user_message": result.get("user_message"), "ai_response_preview": ai_response[:100] if ai_response else None}
            )
            return ai_response is not None
        else:
            print_result(False, f"Send message failed: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print_result(False, f"Send message error: {str(e)}")
        return False

def test_ai_assistant_delete_conversation(conv_id):
    """Test DELETE /api/ai-assistant/conversations/{conv_id}"""
    print_test(f"AI Assistant Delete Conversation - DELETE /api/ai-assistant/conversations/{conv_id}")
    
    try:
        resp = requests.delete(f"{BASE_URL}/ai-assistant/conversations/{conv_id}", headers=get_headers(), timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            print_result(
                data.get("deleted") == True,
                f"Conversation deleted successfully",
                data
            )
            return True
        else:
            print_result(False, f"Delete conversation failed: {resp.status_code}")
            return False
    except Exception as e:
        print_result(False, f"Delete conversation error: {str(e)}")
        return False

def test_ai_assistant_quick_ask():
    """Test POST /api/ai-assistant/quick-ask (LLM call)"""
    print_test("AI Assistant Quick Ask - POST /api/ai-assistant/quick-ask")
    
    try:
        data = {
            "question": "How do I set better goals?",
            "language": "en"
        }
        resp = requests.post(
            f"{BASE_URL}/ai-assistant/quick-ask",
            json=data,
            headers=get_headers(),
            timeout=60  # Longer timeout for LLM call
        )
        
        if resp.status_code == 200:
            result = resp.json()
            answer = result.get("answer")
            print_result(
                answer is not None and len(answer) > 0,
                f"Quick ask response received ({len(answer)} chars)",
                {"question": result.get("question"), "answer_preview": answer[:100] if answer else None, "language": result.get("language")}
            )
            return answer is not None
        else:
            print_result(False, f"Quick ask failed: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print_result(False, f"Quick ask error: {str(e)}")
        return False

# ============================================================================
# FEATURE 2: CLD REFINEMENTS TESTS
# ============================================================================

def test_cld_module_pna_generate():
    """Test POST /api/cld/module/pna/generate (LLM call)"""
    print_test("CLD Module PNA Generate - POST /api/cld/module/pna/generate")
    
    try:
        data = {}  # Empty body as per review request
        resp = requests.post(
            f"{BASE_URL}/cld/module/pna/generate",
            json=data,
            headers=get_headers(),
            timeout=60  # Longer timeout for LLM call
        )
        
        if resp.status_code == 200:
            result = resp.json()
            nodes = result.get("nodes", [])
            links = result.get("links", [])
            print_result(
                len(nodes) > 0 and len(links) > 0,
                f"PNA CLD generated successfully",
                {"node_count": len(nodes), "link_count": len(links), "module_type": result.get("module_type")}
            )
            return True
        else:
            print_result(False, f"PNA CLD generation failed: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print_result(False, f"PNA CLD generation error: {str(e)}")
        return False

def test_cld_module_master_generate():
    """Test POST /api/cld/module/master/generate (LLM call)"""
    print_test("CLD Module Master Generate - POST /api/cld/module/master/generate")
    
    try:
        data = {}  # Empty body as per review request
        resp = requests.post(
            f"{BASE_URL}/cld/module/master/generate",
            json=data,
            headers=get_headers(),
            timeout=60  # Longer timeout for LLM call
        )
        
        if resp.status_code == 200:
            result = resp.json()
            nodes = result.get("nodes", [])
            links = result.get("links", [])
            print_result(
                len(nodes) > 0 and len(links) > 0,
                f"Master CLD generated successfully (aggregates all modules)",
                {"node_count": len(nodes), "link_count": len(links), "module_type": result.get("module_type")}
            )
            return True
        else:
            print_result(False, f"Master CLD generation failed: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print_result(False, f"Master CLD generation error: {str(e)}")
        return False

def test_cld_get_module_pna():
    """Test GET /api/cld/module/pna"""
    print_test("CLD Get Module PNA - GET /api/cld/module/pna")
    
    try:
        resp = requests.get(f"{BASE_URL}/cld/module/pna", headers=get_headers(), timeout=30)
        
        if resp.status_code == 200:
            result = resp.json()
            # Could be null if not generated yet, or contain CLD data
            if result.get("cld") is None:
                print_result(True, "No PNA CLD found (expected if not generated)", result)
            else:
                nodes = result.get("nodes", [])
                links = result.get("links", [])
                print_result(
                    True,
                    f"PNA CLD retrieved successfully",
                    {"node_count": len(nodes), "link_count": len(links)}
                )
            return True
        else:
            print_result(False, f"Get PNA CLD failed: {resp.status_code}")
            return False
    except Exception as e:
        print_result(False, f"Get PNA CLD error: {str(e)}")
        return False

def test_cld_get_module_master():
    """Test GET /api/cld/module/master"""
    print_test("CLD Get Module Master - GET /api/cld/module/master")
    
    try:
        resp = requests.get(f"{BASE_URL}/cld/module/master", headers=get_headers(), timeout=30)
        
        if resp.status_code == 200:
            result = resp.json()
            # Could be null if not generated yet, or contain CLD data
            if result.get("cld") is None:
                print_result(True, "No Master CLD found (expected if not generated)", result)
            else:
                nodes = result.get("nodes", [])
                links = result.get("links", [])
                print_result(
                    True,
                    f"Master CLD retrieved successfully",
                    {"node_count": len(nodes), "link_count": len(links)}
                )
            return True
        else:
            print_result(False, f"Get Master CLD failed: {resp.status_code}")
            return False
    except Exception as e:
        print_result(False, f"Get Master CLD error: {str(e)}")
        return False

def test_cld_module_list():
    """Test GET /api/cld/modules-list"""
    print_test("CLD Module List - GET /api/cld/modules-list")
    
    try:
        resp = requests.get(f"{BASE_URL}/cld/modules-list", headers=get_headers(), timeout=30)
        
        if resp.status_code == 200:
            result = resp.json()
            print_result(
                isinstance(result, list),
                f"Module CLD list returned {len(result) if isinstance(result, list) else 'non-list'} CLDs",
                {"count": len(result) if isinstance(result, list) else 0, "clds": result[:2] if isinstance(result, list) and len(result) > 0 else []}
            )
            return isinstance(result, list)
        else:
            print_result(False, f"Module list failed: {resp.status_code}")
            return False
    except Exception as e:
        print_result(False, f"Module list error: {str(e)}")
        return False

# ============================================================================
# FEATURE 3: CONFLICT BREAKER AI GENERATION FIX TEST
# ============================================================================

def test_conflict_breaker_ai_generate():
    """Test POST /api/conflict-breaker/sessions/{sid}/ai-generate/crucial_check"""
    print_test("Conflict Breaker AI Generate Fix - POST /api/conflict-breaker/sessions/{sid}/ai-generate/crucial_check")
    
    try:
        # First create a conflict session
        session_data = {
            "title": "Test conflict",
            "other_party": "colleague"
        }
        resp = requests.post(
            f"{BASE_URL}/conflict-breaker/sessions",
            json=session_data,
            headers=get_headers(),
            timeout=30
        )
        
        if resp.status_code != 200:
            print_result(False, f"Failed to create conflict session: {resp.status_code}")
            return False
        
        session = resp.json()
        session_id = session.get("session_id")
        print(f"Created conflict session: {session_id}")
        
        # Save crucial-check data
        crucial_check_data = {
            "stakes_score": 8,
            "emotion_score": 7,
            "opinion_diff_score": 6,
            "urgency_score": 9,
            "classification": "Crucial Conversation"
        }
        resp = requests.post(
            f"{BASE_URL}/conflict-breaker/sessions/{session_id}/crucial-check",
            json=crucial_check_data,
            headers=get_headers(),
            timeout=30
        )
        
        if resp.status_code != 200:
            print_result(False, f"Failed to save crucial-check data: {resp.status_code}")
            return False
        
        print("Saved crucial-check data")
        
        # Test AI generation (this was previously broken)
        resp = requests.post(
            f"{BASE_URL}/conflict-breaker/sessions/{session_id}/ai-generate/crucial_check",
            headers=get_headers(),
            timeout=60  # Longer timeout for LLM call
        )
        
        if resp.status_code == 200:
            result = resp.json()
            ai_output = result.get("ai_output")
            print_result(
                ai_output is not None and len(ai_output) > 0,
                f"AI generation successful! LlmChat init fix working. AI output: {len(ai_output)} chars",
                {"stage": result.get("stage"), "ai_output_preview": ai_output[:150] if ai_output else None}
            )
            return True
        else:
            print_result(False, f"AI generation failed: {resp.status_code} - {resp.text}")
            return False
            
    except Exception as e:
        print_result(False, f"Conflict breaker AI generation error: {str(e)}")
        return False

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def run_all_tests():
    """Run all backend tests"""
    print("\n" + "="*80)
    print("BACKEND TESTING - AI SOLUTION ASSISTANT, CLD REFINEMENTS, CONFLICT BREAKER AI FIX")
    print("="*80)
    print(f"Backend URL: {BASE_URL}")
    print(f"Test User: {TEST_EMAIL}")
    
    # Track results
    results = {
        "total": 0,
        "passed": 0,
        "failed": 0
    }
    
    # Step 1: Register and Login
    if not register_and_login():
        print("\n❌ CRITICAL: Authentication failed. Cannot proceed with tests.")
        return
    
    print(f"\n✅ Authentication successful. Session token obtained.")
    
    # FEATURE 1: AI Solution Assistant (7 endpoints)
    print("\n" + "="*80)
    print("FEATURE 1: AI SOLUTION ASSISTANT (7 endpoints)")
    print("="*80)
    
    tests_feature1 = [
        ("AI Assistant Meta", test_ai_assistant_meta),
        ("AI Assistant Create Conversation", test_ai_assistant_create_conversation),
        ("AI Assistant List Conversations", test_ai_assistant_list_conversations),
    ]
    
    conv_id = None
    for test_name, test_func in tests_feature1:
        results["total"] += 1
        result = test_func()
        if test_name == "AI Assistant Create Conversation":
            conv_id = result
            result = conv_id is not None
        if result:
            results["passed"] += 1
        else:
            results["failed"] += 1
    
    # Tests that require conversation ID
    if conv_id:
        tests_with_conv = [
            ("AI Assistant Get Conversation", lambda: test_ai_assistant_get_conversation(conv_id)),
            ("AI Assistant Send Message (LLM)", lambda: test_ai_assistant_send_message(conv_id)),
            ("AI Assistant Delete Conversation", lambda: test_ai_assistant_delete_conversation(conv_id)),
        ]
        
        for test_name, test_func in tests_with_conv:
            results["total"] += 1
            if test_func():
                results["passed"] += 1
            else:
                results["failed"] += 1
    
    # Quick ask test
    results["total"] += 1
    if test_ai_assistant_quick_ask():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # FEATURE 2: CLD Refinements (5 endpoints)
    print("\n" + "="*80)
    print("FEATURE 2: CLD REFINEMENTS (5 endpoints)")
    print("="*80)
    
    tests_feature2 = [
        ("CLD Module PNA Generate (LLM)", test_cld_module_pna_generate),
        ("CLD Module Master Generate (LLM)", test_cld_module_master_generate),
        ("CLD Get Module PNA", test_cld_get_module_pna),
        ("CLD Get Module Master", test_cld_get_module_master),
        ("CLD Module List", test_cld_module_list),
    ]
    
    for test_name, test_func in tests_feature2:
        results["total"] += 1
        if test_func():
            results["passed"] += 1
        else:
            results["failed"] += 1
    
    # FEATURE 3: Conflict Breaker AI Generation Fix (1 endpoint)
    print("\n" + "="*80)
    print("FEATURE 3: CONFLICT BREAKER AI GENERATION FIX (1 endpoint)")
    print("="*80)
    
    results["total"] += 1
    if test_conflict_breaker_ai_generate():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Print final summary
    print("\n" + "="*80)
    print("FINAL TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {results['total']}")
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"Success Rate: {(results['passed']/results['total']*100):.1f}%")
    print("="*80)

if __name__ == "__main__":
    run_all_tests()
