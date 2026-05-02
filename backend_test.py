"""
Backend API Testing for Video Call Endpoints in LIVE_SYNC Collaboration Sessions
Tests all video call functionality for multi-user collaboration
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
        result += f" - {details}"
    print(result)
    test_results.append({"test": test_name, "passed": passed, "details": details})
    return passed

def register_user(email, password, name):
    """Register a new user"""
    url = f"{BASE_URL}/auth/register"
    payload = {
        "email": email,
        "password": password,
        "name": name
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        data = response.json()
        return data.get("session_token"), data.get("user_id")
    return None, None

def login_user(email, password):
    """Login user"""
    url = f"{BASE_URL}/auth/login"
    payload = {"email": email, "password": password}
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        data = response.json()
        return data.get("session_token"), data.get("user_id")
    return None, None

def promote_to_admin(token, user_id):
    """Promote user to admin (requires existing admin)"""
    url = f"{BASE_URL}/admin/users/{user_id}/promote"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"role": "admin"}
    response = requests.post(url, json=payload, headers=headers)
    return response.status_code == 200

def create_decision_mode(token):
    """Get decision modes (auto-seeds if not exists)"""
    url = f"{BASE_URL}/collaboration/decision-modes"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        modes = response.json()
        return modes[0]["id"] if modes else "equal"
    return "equal"

def create_contact(token, name, email):
    """Create a contact"""
    url = f"{BASE_URL}/contacts"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "name": name,
        "email": email,
        "phone": "+919876543210",
        "is_sme": False
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("id")
    return None

def create_decision(token, title):
    """Create a PRR decision"""
    url = f"{BASE_URL}/decisions"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "title": title,
        "context": "Test decision for video call collaboration",
        "folder": "career"
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("id")
    else:
        print(f"Decision creation failed: Status {response.status_code}, Response: {response.text}")
    return None

def create_collaboration_session(token, decision_id, contact_ids, session_mode="live_sync"):
    """Create a collaboration session"""
    url = f"{BASE_URL}/collaboration/sessions"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "module_type": "decision",
        "module_id": decision_id,
        "title": "Video Call Test Session",
        "decision_mode_id": "equal",
        "participant_contact_ids": contact_ids,
        "session_mode": session_mode,
        "notify_participants": True,
        "notify_mode": True
    }
    response = requests.post(url, json=payload, headers=headers)
    return response

def start_call(token, session_id):
    """Start or get video call"""
    url = f"{BASE_URL}/collaboration/sessions/{session_id}/start-call"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(url, headers=headers)
    return response

def join_call(token, session_id):
    """Join video call"""
    url = f"{BASE_URL}/collaboration/sessions/{session_id}/join-call"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(url, headers=headers)
    return response

def get_call_status(token, session_id):
    """Get call status"""
    url = f"{BASE_URL}/collaboration/sessions/{session_id}/call-status"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    return response

def toggle_screen_share(token, session_id, sharing=True):
    """Toggle screen sharing"""
    url = f"{BASE_URL}/collaboration/sessions/{session_id}/screen-share"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"sharing": sharing}
    response = requests.post(url, json=payload, headers=headers)
    return response

def end_call(token, session_id):
    """End video call"""
    url = f"{BASE_URL}/collaboration/sessions/{session_id}/end-call"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(url, headers=headers)
    return response

def run_video_call_tests():
    """Run comprehensive video call endpoint tests"""
    print("\n" + "="*80)
    print("VIDEO CALL ENDPOINTS TESTING FOR LIVE_SYNC COLLABORATION SESSIONS")
    print("="*80 + "\n")
    
    timestamp = int(time.time())
    
    # Test 1: Register Host User
    print("Test 1: Register Host User")
    host_email = f"videocall_host_{timestamp}@test.com"
    host_token, host_user_id = register_user(host_email, "password123", "Video Call Host")
    log_test("Register Host User", host_token is not None, f"Email: {host_email}")
    
    if not host_token:
        print("❌ Cannot proceed without host user registration")
        return
    
    # Test 2: Register Participant User
    print("\nTest 2: Register Participant User")
    participant_email = f"videocall_participant_{timestamp}@test.com"
    participant_token, participant_user_id = register_user(participant_email, "password123", "Video Call Participant")
    log_test("Register Participant User", participant_token is not None, f"Email: {participant_email}")
    
    if not participant_token:
        print("❌ Cannot proceed without participant user registration")
        return
    
    # Test 3: Get Decision Modes
    print("\nTest 3: Get Decision Modes")
    mode_id = create_decision_mode(host_token)
    log_test("Get Decision Modes", mode_id is not None, f"Mode ID: {mode_id}")
    
    # Test 4: Create Contact for Participant
    print("\nTest 4: Create Contact for Participant")
    contact_id = create_contact(host_token, "Video Call Participant", participant_email)
    log_test("Create Contact", contact_id is not None, f"Contact ID: {contact_id}")
    
    if not contact_id:
        print("❌ Cannot proceed without contact creation")
        return
    
    # Test 5: Create Decision
    print("\nTest 5: Create Decision")
    decision_id = create_decision(host_token, "Video Call Test Decision")
    log_test("Create Decision", decision_id is not None, f"Decision ID: {decision_id}")
    
    if not decision_id:
        print("❌ Cannot proceed without decision creation")
        return
    
    # Test 6: Create LIVE_SYNC Collaboration Session with Call Fields
    print("\nTest 6: Create LIVE_SYNC Collaboration Session")
    session_response = create_collaboration_session(host_token, decision_id, [contact_id], "live_sync")
    session_created = session_response.status_code == 200
    
    if session_created:
        session_data = session_response.json()
        session_id = session_data.get("id")
        has_call_room_url = "call_room_url" in session_data
        has_call_id = "call_id" in session_data
        has_call_room_id = "call_room_id" in session_data
        
        details = f"Session ID: {session_id}, Has call_room_url: {has_call_room_url}, Has call_id: {has_call_id}, Has call_room_id: {has_call_room_id}"
        log_test("Create LIVE_SYNC Session with Call Fields", 
                 has_call_room_url and has_call_id and has_call_room_id, 
                 details)
        
        if not (has_call_room_url and has_call_id and has_call_room_id):
            print(f"❌ Session missing call fields. Response: {json.dumps(session_data, indent=2)}")
            return
    else:
        log_test("Create LIVE_SYNC Session", False, f"Status: {session_response.status_code}")
        print(f"Response: {session_response.text}")
        return
    
    # Test 7: Start Call
    print("\nTest 7: Start Call")
    start_response = start_call(host_token, session_id)
    start_success = start_response.status_code == 200
    
    if start_success:
        start_data = start_response.json()
        has_room_url = "room_url" in start_data
        has_status = start_data.get("status") == "live"
        has_provider = start_data.get("provider") == "jitsi"
        has_participants = "participants_joined" in start_data
        
        details = f"Status: {start_data.get('status')}, Provider: {start_data.get('provider')}, Room URL: {start_data.get('room_url')}"
        log_test("Start Call", has_room_url and has_status and has_provider and has_participants, details)
    else:
        log_test("Start Call", False, f"Status: {start_response.status_code}, Response: {start_response.text}")
        return
    
    # Test 8: Join Call (Participant)
    print("\nTest 8: Join Call (Participant)")
    join_response = join_call(participant_token, session_id)
    join_success = join_response.status_code == 200
    
    if join_success:
        join_data = join_response.json()
        has_room_url = "room_url" in join_data
        has_call_id = "call_id" in join_data
        
        details = f"Call ID: {join_data.get('call_id')}, Room URL: {join_data.get('room_url')}"
        log_test("Join Call", has_room_url and has_call_id, details)
    else:
        log_test("Join Call", False, f"Status: {join_response.status_code}, Response: {join_response.text}")
    
    # Test 9: Check Call Status
    print("\nTest 9: Check Call Status")
    status_response = get_call_status(host_token, session_id)
    status_success = status_response.status_code == 200
    
    if status_success:
        status_data = status_response.json()
        has_call = status_data.get("has_call") == True
        is_live = status_data.get("status") == "live"
        has_participants = len(status_data.get("participants_joined", [])) >= 1
        has_screen_sharing = "screen_sharing_by" in status_data
        
        details = f"Has call: {has_call}, Status: {status_data.get('status')}, Participants: {len(status_data.get('participants_joined', []))}"
        log_test("Check Call Status", has_call and is_live and has_participants and has_screen_sharing, details)
    else:
        log_test("Check Call Status", False, f"Status: {status_response.status_code}, Response: {status_response.text}")
    
    # Test 10: Toggle Screen Share (Enable)
    print("\nTest 10: Toggle Screen Share (Enable)")
    share_response = toggle_screen_share(host_token, session_id, True)
    share_success = share_response.status_code == 200
    
    if share_success:
        share_data = share_response.json()
        screen_sharing_by = share_data.get("screen_sharing_by")
        is_sharing = share_data.get("sharing") == True
        
        details = f"Screen sharing by: {screen_sharing_by}, Sharing: {is_sharing}"
        log_test("Enable Screen Share", screen_sharing_by is not None and is_sharing, details)
    else:
        log_test("Enable Screen Share", False, f"Status: {share_response.status_code}, Response: {share_response.text}")
    
    # Test 11: End Call
    print("\nTest 11: End Call")
    end_response = end_call(host_token, session_id)
    end_success = end_response.status_code == 200
    
    if end_success:
        end_data = end_response.json()
        is_ended = end_data.get("status") == "ended"
        
        details = f"Status: {end_data.get('status')}"
        log_test("End Call", is_ended, details)
    else:
        log_test("End Call", False, f"Status: {end_response.status_code}, Response: {end_response.text}")
    
    # Test 12: Verify Call Ended
    print("\nTest 12: Verify Call Ended")
    verify_response = get_call_status(host_token, session_id)
    verify_success = verify_response.status_code == 200
    
    if verify_success:
        verify_data = verify_response.json()
        is_ended = verify_data.get("status") == "ended"
        
        details = f"Status: {verify_data.get('status')}"
        log_test("Verify Call Ended", is_ended, details)
    else:
        log_test("Verify Call Ended", False, f"Status: {verify_response.status_code}, Response: {verify_response.text}")
    
    # Test 13: Create ASYNC Session
    print("\nTest 13: Create ASYNC Session")
    async_decision_id = create_decision(host_token, "Async Test Decision")
    if async_decision_id:
        async_session_response = create_collaboration_session(host_token, async_decision_id, [contact_id], "async")
        async_created = async_session_response.status_code == 200
        
        if async_created:
            async_session_data = async_session_response.json()
            async_session_id = async_session_data.get("id")
            session_mode = async_session_data.get("session_mode")
            
            details = f"Session ID: {async_session_id}, Mode: {session_mode}"
            log_test("Create ASYNC Session", session_mode == "async", details)
            
            # Test 14: Try Start Call on ASYNC Session (Should Fail with 400)
            print("\nTest 14: Try Start Call on ASYNC Session (Expect 400 Error)")
            async_start_response = start_call(host_token, async_session_id)
            should_fail = async_start_response.status_code == 400
            
            if should_fail:
                error_data = async_start_response.json()
                error_message = error_data.get("detail", "")
                details = f"Status: {async_start_response.status_code}, Error: {error_message}"
                log_test("ASYNC Session Start Call Error", "Live Sync" in error_message or "live_sync" in error_message, details)
            else:
                log_test("ASYNC Session Start Call Error", False, f"Expected 400, got {async_start_response.status_code}")
        else:
            log_test("Create ASYNC Session", False, f"Status: {async_session_response.status_code}")
    else:
        log_test("Create ASYNC Session", False, "Failed to create decision for async session")
    
    # Print Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed_count = sum(1 for r in test_results if r["passed"])
    total_count = len(test_results)
    
    print(f"\nTotal Tests: {total_count}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {total_count - passed_count}")
    print(f"Success Rate: {(passed_count/total_count*100):.1f}%\n")
    
    # Print failed tests
    failed_tests = [r for r in test_results if not r["passed"]]
    if failed_tests:
        print("FAILED TESTS:")
        for test in failed_tests:
            print(f"  ❌ {test['test']}")
            if test['details']:
                print(f"     {test['details']}")
    else:
        print("🎉 ALL TESTS PASSED!")
    
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    run_video_call_tests()
