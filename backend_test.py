"""
Comprehensive Backend Testing for Contact List and Multi-User Collaboration Engine
Tests all endpoints as per review request
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
    status = "✅ PASS" if passed else "❌ FAIL"
    result = f"{status}: {test_name}"
    if details:
        result += f" - {details}"
    print(result)
    test_results.append({"test": test_name, "passed": passed, "details": details})
    return passed

def register_user(name, email, password):
    """Register a new user"""
    url = f"{BASE_URL}/auth/register"
    payload = {
        "name": name,
        "email": email,
        "password": password
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        data = response.json()
        return data.get("session_token"), data.get("user_id")
    return None, None

def login_user(email, password):
    """Login user"""
    url = f"{BASE_URL}/auth/login"
    payload = {
        "email": email,
        "password": password
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        data = response.json()
        return data.get("session_token"), data.get("user_id")
    return None, None

def promote_to_admin(email):
    """Promote user to admin via MongoDB (simulated - would need direct DB access)"""
    # This would require direct MongoDB access which we don't have in tests
    # For now, we'll skip admin-only tests
    pass

def main():
    print("=" * 80)
    print("CONTACT LIST AND MULTI-USER COLLABORATION ENGINE - COMPREHENSIVE TESTING")
    print("=" * 80)
    print()
    
    timestamp = int(time.time())
    
    # SETUP: Register and login users
    print("SETUP: Registering test users...")
    user1_email = f"collab.owner.{timestamp}@test.com"
    user1_name = "Collab Owner"
    user1_password = "password123"
    
    user2_email = f"participant.user.{timestamp}@test.com"
    user2_name = "Participant User"
    user2_password = "password123"
    
    token1, user1_id = register_user(user1_name, user1_email, user1_password)
    if token1:
        log_test("User 1 Registration", True, f"Registered {user1_name}")
    else:
        log_test("User 1 Registration", False, "Failed to register user 1")
        return
    
    token2, user2_id = register_user(user2_name, user2_email, user2_password)
    if token2:
        log_test("User 2 Registration", True, f"Registered {user2_name}")
    else:
        log_test("User 2 Registration", False, "Failed to register user 2")
        return
    
    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}
    
    print()
    print("=" * 80)
    print("CONTACT LIST MANAGEMENT TESTS")
    print("=" * 80)
    print()
    
    # Test 1: Create contact1 with full details (Alice Engineer - linked to user2)
    print("Test 1: Create contact with full details (Alice Engineer)...")
    contact1_payload = {
        "name": "Alice Engineer",
        "email": user2_email,  # This should link to user2
        "phone": "9876543210",
        "gender": "female",
        "country": "India",
        "language": "English",
        "profession": "Engineer",
        "skills": ["Python", "AI"],
        "organization": "TechCorp",
        "social_status": "employed",
        "is_sme": True
    }
    response = requests.post(f"{BASE_URL}/contacts", json=contact1_payload, headers=headers1)
    if response.status_code == 200:
        contact1 = response.json()
        contact1_id = contact1.get("id")
        linked_user_id = contact1.get("linked_user_id")
        if linked_user_id == user2_id:
            log_test("Create Contact 1 (Alice)", True, f"Created with linked_user_id={user2_id}")
        else:
            log_test("Create Contact 1 (Alice)", False, f"Expected linked_user_id={user2_id}, got {linked_user_id}")
    else:
        log_test("Create Contact 1 (Alice)", False, f"Status {response.status_code}: {response.text}")
        contact1_id = None
    
    # Test 2: Create contact2 (Bob Manager)
    print("Test 2: Create contact without email (Bob Manager)...")
    contact2_payload = {
        "name": "Bob Manager",
        "phone": "9876543211",
        "gender": "male",
        "country": "India",
        "profession": "Manager",
        "skills": ["Leadership"],
        "organization": "BizCorp"
    }
    response = requests.post(f"{BASE_URL}/contacts", json=contact2_payload, headers=headers1)
    if response.status_code == 200:
        contact2 = response.json()
        contact2_id = contact2.get("id")
        log_test("Create Contact 2 (Bob)", True, f"Created contact {contact2_id}")
    else:
        log_test("Create Contact 2 (Bob)", False, f"Status {response.status_code}: {response.text}")
        contact2_id = None
    
    # Test 3: List all contacts (should return 2)
    print("Test 3: List all contacts...")
    response = requests.get(f"{BASE_URL}/contacts", headers=headers1)
    if response.status_code == 200:
        data = response.json()
        contacts = data.get("contacts", [])
        total = data.get("total", 0)
        if total == 2 and len(contacts) == 2:
            # Check if Alice has linked_user_id
            alice = next((c for c in contacts if c.get("name") == "Alice Engineer"), None)
            if alice and alice.get("linked_user_id") == user2_id:
                log_test("List All Contacts", True, f"Found 2 contacts, Alice has linked_user_id={user2_id}")
            else:
                log_test("List All Contacts", False, "Alice doesn't have correct linked_user_id")
        else:
            log_test("List All Contacts", False, f"Expected 2 contacts, got {total}")
    else:
        log_test("List All Contacts", False, f"Status {response.status_code}: {response.text}")
    
    # Test 4: Filter by gender=female (should return only Alice)
    print("Test 4: Filter contacts by gender=female...")
    response = requests.get(f"{BASE_URL}/contacts?gender=female", headers=headers1)
    if response.status_code == 200:
        data = response.json()
        contacts = data.get("contacts", [])
        if len(contacts) == 1 and contacts[0].get("name") == "Alice Engineer":
            log_test("Filter by Gender (female)", True, "Returned only Alice")
        else:
            log_test("Filter by Gender (female)", False, f"Expected 1 contact (Alice), got {len(contacts)}")
    else:
        log_test("Filter by Gender (female)", False, f"Status {response.status_code}: {response.text}")
    
    # Test 5: Filter by is_sme=true (should return only Alice)
    print("Test 5: Filter contacts by is_sme=true...")
    response = requests.get(f"{BASE_URL}/contacts?is_sme=true", headers=headers1)
    if response.status_code == 200:
        data = response.json()
        contacts = data.get("contacts", [])
        if len(contacts) == 1 and contacts[0].get("name") == "Alice Engineer":
            log_test("Filter by is_sme=true", True, "Returned only Alice")
        else:
            log_test("Filter by is_sme=true", False, f"Expected 1 contact (Alice), got {len(contacts)}")
    else:
        log_test("Filter by is_sme=true", False, f"Status {response.status_code}: {response.text}")
    
    # Test 6: Filter by profession=Engineer (should return only Alice)
    print("Test 6: Filter contacts by profession=Engineer...")
    response = requests.get(f"{BASE_URL}/contacts?profession=Engineer", headers=headers1)
    if response.status_code == 200:
        data = response.json()
        contacts = data.get("contacts", [])
        if len(contacts) == 1 and contacts[0].get("name") == "Alice Engineer":
            log_test("Filter by Profession (Engineer)", True, "Returned only Alice")
        else:
            log_test("Filter by Profession (Engineer)", False, f"Expected 1 contact (Alice), got {len(contacts)}")
    else:
        log_test("Filter by Profession (Engineer)", False, f"Status {response.status_code}: {response.text}")
    
    # Test 7: Get filter options
    print("Test 7: Get filter options...")
    response = requests.get(f"{BASE_URL}/contacts/filter-options", headers=headers1)
    if response.status_code == 200:
        options = response.json()
        has_gender = "gender" in options and "female" in options.get("gender", [])
        has_country = "country" in options and "India" in options.get("country", [])
        has_profession = "profession" in options and "Engineer" in options.get("profession", [])
        if has_gender and has_country and has_profession:
            log_test("Get Filter Options", True, "Returns distinct values for gender, country, profession")
        else:
            log_test("Get Filter Options", False, "Missing expected filter values")
    else:
        log_test("Get Filter Options", False, f"Status {response.status_code}: {response.text}")
    
    # Test 8: Update contact (Alice) - change designation to CTO
    print("Test 8: Update contact (Alice) - set designation to CTO...")
    if contact1_id:
        update_payload = {"designation": "CTO"}
        response = requests.put(f"{BASE_URL}/contacts/{contact1_id}", json=update_payload, headers=headers1)
        if response.status_code == 200:
            updated = response.json()
            if updated.get("designation") == "CTO":
                log_test("Update Contact (Alice)", True, "Designation updated to CTO")
            else:
                log_test("Update Contact (Alice)", False, f"Expected designation=CTO, got {updated.get('designation')}")
        else:
            log_test("Update Contact (Alice)", False, f"Status {response.status_code}: {response.text}")
    else:
        log_test("Update Contact (Alice)", False, "contact1_id not available")
    
    # Test 9: Bulk import contacts
    print("Test 9: Bulk import contacts from LinkedIn...")
    bulk_payload = {
        "source": "linkedin",
        "contacts": [
            {
                "name": "Charlie Designer",
                "email": "charlie@test.com",
                "profession": "Designer"
            }
        ]
    }
    response = requests.post(f"{BASE_URL}/contacts/import-bulk", json=bulk_payload, headers=headers1)
    if response.status_code == 200:
        result = response.json()
        imported = result.get("imported", 0)
        if imported == 1:
            log_test("Bulk Import Contacts", True, f"Imported {imported} contact")
        else:
            log_test("Bulk Import Contacts", False, f"Expected 1 import, got {imported}")
    else:
        log_test("Bulk Import Contacts", False, f"Status {response.status_code}: {response.text}")
    
    print()
    print("=" * 80)
    print("DECISION MODES TESTS")
    print("=" * 80)
    print()
    
    # Test 10: Get decision modes (should return 6 modes)
    print("Test 10: Get decision modes...")
    response = requests.get(f"{BASE_URL}/collaboration/decision-modes", headers=headers1)
    if response.status_code == 200:
        modes = response.json()
        if len(modes) == 6:
            mode_ids = [m.get("id") for m in modes]
            expected_ids = ["equal", "voting", "command", "sme", "custom", "consensus"]
            if all(mid in mode_ids for mid in expected_ids):
                log_test("Get Decision Modes", True, "Returns 6 modes with correct IDs")
            else:
                log_test("Get Decision Modes", False, f"Missing expected mode IDs. Got: {mode_ids}")
        else:
            log_test("Get Decision Modes", False, f"Expected 6 modes, got {len(modes)}")
    else:
        log_test("Get Decision Modes", False, f"Status {response.status_code}: {response.text}")
    
    # Test 11: Update decision mode (requires admin) - should fail for non-admin
    print("Test 11: Update decision mode (command) - testing admin requirement...")
    update_mode_payload = {"config": {"leader_weight_pct": 60}}
    response = requests.put(f"{BASE_URL}/collaboration/decision-modes/command", json=update_mode_payload, headers=headers1)
    if response.status_code == 403:
        log_test("Update Decision Mode (non-admin)", True, "Correctly denied for non-admin user (403)")
    elif response.status_code == 200:
        # If user happens to be admin, check if update worked
        updated_mode = response.json()
        if updated_mode.get("config", {}).get("leader_weight_pct") == 60:
            log_test("Update Decision Mode (admin)", True, "Updated leader_weight_pct to 60")
        else:
            log_test("Update Decision Mode", False, "Update didn't persist correctly")
    else:
        log_test("Update Decision Mode", False, f"Unexpected status {response.status_code}: {response.text}")
    
    print()
    print("=" * 80)
    print("COLLABORATION SESSION TESTS")
    print("=" * 80)
    print()
    
    # First, create a decision for collaboration
    print("Setup: Creating a decision for collaboration testing...")
    decision_payload = {
        "title": "Group Test Decision",
        "context": "Testing collaboration features with multiple participants",
        "factors": [
            {"id": "f1", "name": "Cost", "rating": 50, "category": "primary", "order": 0},
            {"id": "f2", "name": "Quality", "rating": 40, "category": "primary", "order": 1}
        ],
        "options": [
            {"id": "opt1", "name": "Option A", "assessments": []},
            {"id": "opt2", "name": "Option B", "assessments": []}
        ]
    }
    response = requests.post(f"{BASE_URL}/decisions", json=decision_payload, headers=headers1)
    if response.status_code == 200:
        decision = response.json()
        decision_id = decision.get("id")
        print(f"✓ Created decision: {decision_id}")
    else:
        print(f"✗ Failed to create decision: {response.status_code}")
        decision_id = None
    
    # Test 12: Create collaboration session
    print("Test 12: Create collaboration session...")
    if decision_id and contact1_id and contact2_id:
        session_payload = {
            "module_type": "decision",
            "module_id": decision_id,
            "decision_mode_id": "equal",
            "participant_contact_ids": [contact1_id, contact2_id],
            "auth_config": {
                "methods_required": 0,
                "verify_each_time": False,
                "enabled_methods": []
            },
            "notify_participants": True,
            "notify_mode": True
        }
        response = requests.post(f"{BASE_URL}/collaboration/sessions", json=session_payload, headers=headers1)
        if response.status_code == 200:
            session = response.json()
            session_id = session.get("id")
            participants = session.get("participants", [])
            if len(participants) == 2:
                log_test("Create Collaboration Session", True, f"Created session {session_id} with 2 participants")
            else:
                log_test("Create Collaboration Session", False, f"Expected 2 participants, got {len(participants)}")
        else:
            log_test("Create Collaboration Session", False, f"Status {response.status_code}: {response.text}")
            session_id = None
    else:
        log_test("Create Collaboration Session", False, "Missing prerequisites (decision_id or contact_ids)")
        session_id = None
    
    # Test 13: List collaboration sessions
    print("Test 13: List collaboration sessions...")
    response = requests.get(f"{BASE_URL}/collaboration/sessions", headers=headers1)
    if response.status_code == 200:
        sessions = response.json()
        if len(sessions) >= 1:
            log_test("List Collaboration Sessions", True, f"Found {len(sessions)} session(s)")
        else:
            log_test("List Collaboration Sessions", False, "No sessions found")
    else:
        log_test("List Collaboration Sessions", False, f"Status {response.status_code}: {response.text}")
    
    # Test 14: Get specific session
    print("Test 14: Get specific collaboration session...")
    if session_id:
        response = requests.get(f"{BASE_URL}/collaboration/sessions/{session_id}", headers=headers1)
        if response.status_code == 200:
            session = response.json()
            has_participants = "participants" in session and len(session["participants"]) == 2
            has_mode = "decision_mode" in session
            if has_participants and has_mode:
                log_test("Get Collaboration Session", True, "Returns full session with participants and mode")
            else:
                log_test("Get Collaboration Session", False, "Missing participants or mode data")
        else:
            log_test("Get Collaboration Session", False, f"Status {response.status_code}: {response.text}")
    else:
        log_test("Get Collaboration Session", False, "session_id not available")
    
    # Test 15: Contribute to session (as user2/Alice)
    print("Test 15: Contribute to session (as user2/Alice)...")
    if session_id:
        contribution_payload = {
            "contribution": {
                "assessments": {
                    "opt1_f1": 75,  # Option A, Cost factor
                    "opt1_f2": 80,  # Option A, Quality factor
                    "opt2_f1": 60,  # Option B, Cost factor
                    "opt2_f2": 70   # Option B, Quality factor
                }
            }
        }
        response = requests.post(f"{BASE_URL}/collaboration/sessions/{session_id}/contribute", 
                                json=contribution_payload, headers=headers2)
        if response.status_code == 200:
            result = response.json()
            log_test("Contribute to Session (user2)", True, "Contribution submitted successfully")
            
            # Verify contribution was recorded
            response = requests.get(f"{BASE_URL}/collaboration/sessions/{session_id}", headers=headers1)
            if response.status_code == 200:
                session = response.json()
                alice_participant = next((p for p in session.get("participants", []) 
                                        if p.get("linked_user_id") == user2_id), None)
                if alice_participant and alice_participant.get("status") == "contributed":
                    log_test("Verify Contribution Recorded", True, "Participant status changed to 'contributed'")
                else:
                    log_test("Verify Contribution Recorded", False, "Status not updated correctly")
        else:
            log_test("Contribute to Session (user2)", False, f"Status {response.status_code}: {response.text}")
    else:
        log_test("Contribute to Session (user2)", False, "session_id not available")
    
    print()
    print("=" * 80)
    print("TOTP AUTHENTICATOR TESTS")
    print("=" * 80)
    print()
    
    # Test 16: Setup TOTP
    print("Test 16: Setup TOTP for user1...")
    response = requests.post(f"{BASE_URL}/collaboration/totp/setup", headers=headers1)
    if response.status_code == 200:
        totp_data = response.json()
        has_secret = "secret" in totp_data
        has_uri = "provisioning_uri" in totp_data
        if has_secret and has_uri:
            log_test("TOTP Setup", True, "Returns secret and provisioning_uri")
            totp_secret = totp_data.get("secret")
        else:
            log_test("TOTP Setup", False, "Missing secret or provisioning_uri")
            totp_secret = None
    else:
        log_test("TOTP Setup", False, f"Status {response.status_code}: {response.text}")
        totp_secret = None
    
    # Test 17: Get TOTP status
    print("Test 17: Get TOTP status...")
    response = requests.get(f"{BASE_URL}/collaboration/totp/status", headers=headers1)
    if response.status_code == 200:
        status = response.json()
        if status.get("setup") == True and status.get("verified") == False:
            log_test("TOTP Status", True, "Returns setup=true, verified=false")
        else:
            log_test("TOTP Status", False, f"Unexpected status: {status}")
    else:
        log_test("TOTP Status", False, f"Status {response.status_code}: {response.text}")
    
    # Test 18: Verify TOTP with invalid code (should fail)
    print("Test 18: Verify TOTP with invalid code...")
    verify_payload = {"code": "000000"}
    response = requests.post(f"{BASE_URL}/collaboration/totp/verify", json=verify_payload, headers=headers1)
    if response.status_code == 400:
        log_test("TOTP Verify (invalid code)", True, "Correctly rejected invalid code (400)")
    else:
        log_test("TOTP Verify (invalid code)", False, f"Expected 400, got {response.status_code}")
    
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print()
    
    passed = sum(1 for r in test_results if r["passed"])
    total = len(test_results)
    pass_rate = (passed / total * 100) if total > 0 else 0
    
    print(f"Total Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Pass Rate: {pass_rate:.1f}%")
    print()
    
    # Show failed tests
    failed_tests = [r for r in test_results if not r["passed"]]
    if failed_tests:
        print("FAILED TESTS:")
        for r in failed_tests:
            print(f"  ❌ {r['test']}: {r['details']}")
    else:
        print("🎉 ALL TESTS PASSED!")
    
    print()
    print("=" * 80)

if __name__ == "__main__":
    main()
