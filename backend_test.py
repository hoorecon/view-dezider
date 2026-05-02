"""Backend API Testing for New Collaboration & Contact Features
Tests:
1. Postman Collection Export (admin-only)
2. DigiLocker eKYC
3. Biometric Framework
4. Org Type on Contacts
5. Session Mode + Config Override
"""

import requests
import json
import time
from datetime import datetime

# Backend URL from review request
BASE_URL = "https://dezider-core.preview.emergentagent.com/api"

# Test results tracking
test_results = {
    "passed": 0,
    "failed": 0,
    "tests": []
}

def log_test(name, passed, details=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results["tests"].append({
        "name": name,
        "status": status,
        "details": details
    })
    if passed:
        test_results["passed"] += 1
    else:
        test_results["failed"] += 1
    print(f"{status}: {name}")
    if details:
        print(f"  Details: {details}")

def print_summary():
    """Print test summary"""
    total = test_results["passed"] + test_results["failed"]
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {total}")
    print(f"Passed: {test_results['passed']}")
    print(f"Failed: {test_results['failed']}")
    print(f"Success Rate: {(test_results['passed']/total*100):.1f}%" if total > 0 else "N/A")
    print("="*80)

# Global variables for test data
session_token = None
user_id = None
admin_token = None
admin_user_id = None
contact_id = None
decision_id = None
collab_session_id = None

def test_user_registration():
    """Test user registration"""
    global session_token, user_id
    timestamp = int(time.time())
    email = f"collabtest_{timestamp}@test.com"
    
    payload = {
        "email": email,
        "password": "testpass123",
        "name": "Collab Test User"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/register", json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            session_token = data.get("session_token")
            user_id = data.get("user_id")
            log_test("User Registration", True, f"User ID: {user_id}")
            return True
        else:
            log_test("User Registration", False, f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        log_test("User Registration", False, f"Exception: {str(e)}")
        return False

def test_user_login():
    """Test user login"""
    global session_token, user_id
    timestamp = int(time.time())
    email = f"collabtest_{timestamp}@test.com"
    
    # First register
    reg_payload = {
        "email": email,
        "password": "testpass123",
        "name": "Collab Test User"
    }
    requests.post(f"{BASE_URL}/auth/register", json=reg_payload, timeout=10)
    
    # Then login
    login_payload = {
        "email": email,
        "password": "testpass123"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/login", json=login_payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            session_token = data.get("session_token")
            user_id = data.get("user_id")
            log_test("User Login", True, f"Session token obtained")
            return True
        else:
            log_test("User Login", False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("User Login", False, f"Exception: {str(e)}")
        return False

def promote_to_admin():
    """Promote user to admin role in MongoDB (simulated)"""
    global admin_token, admin_user_id
    # For testing, we'll use the same user and assume admin privileges
    # In real scenario, this would require MongoDB update
    admin_token = session_token
    admin_user_id = user_id
    log_test("Admin Promotion Setup", True, "Using test user as admin")
    return True

# ========================
# 1. POSTMAN COLLECTION EXPORT
# ========================

def test_postman_collection_export():
    """Test GET /api/admin/docs/postman-collection"""
    if not admin_token:
        log_test("Postman Collection Export", False, "No admin token available")
        return False
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    try:
        response = requests.get(f"{BASE_URL}/admin/docs/postman-collection", headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            # Validate Postman v2.1 structure
            has_info = "info" in data
            has_items = "item" in data
            has_schema = data.get("info", {}).get("schema", "").startswith("https://schema.getpostman.com")
            
            if has_info and has_items and has_schema:
                item_count = len(data.get("item", []))
                log_test("Postman Collection Export", True, 
                        f"Valid Postman v2.1 collection with {item_count} folders/categories")
                return True
            else:
                log_test("Postman Collection Export", False, 
                        f"Invalid structure - info:{has_info}, items:{has_items}, schema:{has_schema}")
                return False
        elif response.status_code == 403:
            log_test("Postman Collection Export", False, 
                    "403 Forbidden - Admin access required (expected for non-admin users)")
            return False
        else:
            log_test("Postman Collection Export", False, 
                    f"Status: {response.status_code}, Response: {response.text[:200]}")
            return False
    except Exception as e:
        log_test("Postman Collection Export", False, f"Exception: {str(e)}")
        return False

# ========================
# 2. DIGILOCKER eKYC
# ========================

def test_digilocker_initiate():
    """Test POST /api/collaboration/digilocker/initiate"""
    if not session_token:
        log_test("DigiLocker Initiate", False, "No session token")
        return False
    
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.post(f"{BASE_URL}/collaboration/digilocker/initiate", 
                                headers=headers, json={}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            
            if status == "not_configured":
                # Expected when DIGILOCKER_CLIENT_ID is not set
                has_message = "message" in data
                has_registration_url = "registration_url" in data
                has_supported_docs = "supported_documents" in data
                has_flow = "flow" in data
                
                if has_message and has_registration_url and has_supported_docs and has_flow:
                    log_test("DigiLocker Initiate", True, 
                            "Returns status='not_configured' with helpful info (DIGILOCKER_CLIENT_ID not set)")
                    return True
                else:
                    log_test("DigiLocker Initiate", False, 
                            f"Missing fields - message:{has_message}, url:{has_registration_url}, docs:{has_supported_docs}, flow:{has_flow}")
                    return False
            elif "auth_url" in data:
                # If configured, should return auth_url
                log_test("DigiLocker Initiate", True, 
                        "DigiLocker configured - returns auth_url")
                return True
            else:
                log_test("DigiLocker Initiate", False, 
                        f"Unexpected response structure: {data}")
                return False
        else:
            log_test("DigiLocker Initiate", False, 
                    f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        log_test("DigiLocker Initiate", False, f"Exception: {str(e)}")
        return False

def test_digilocker_status():
    """Test GET /api/collaboration/digilocker/status"""
    if not session_token:
        log_test("DigiLocker Status", False, "No session token")
        return False
    
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.get(f"{BASE_URL}/collaboration/digilocker/status", 
                               headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            has_verified = "verified" in data
            
            if has_verified and data["verified"] == False:
                log_test("DigiLocker Status", True, 
                        "Returns verified=false for unverified user")
                return True
            elif has_verified and data["verified"] == True:
                log_test("DigiLocker Status", True, 
                        "Returns verified=true with verification details")
                return True
            else:
                log_test("DigiLocker Status", False, 
                        f"Missing or invalid 'verified' field: {data}")
                return False
        else:
            log_test("DigiLocker Status", False, 
                    f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        log_test("DigiLocker Status", False, f"Exception: {str(e)}")
        return False

# ========================
# 3. BIOMETRIC FRAMEWORK
# ========================

def test_biometric_supported_devices():
    """Test GET /api/collaboration/biometric/supported-devices"""
    if not session_token:
        log_test("Biometric Supported Devices", False, "No session token")
        return False
    
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.get(f"{BASE_URL}/collaboration/biometric/supported-devices", 
                               headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            devices = data.get("devices", [])
            
            # Should return 4 devices as per implementation
            expected_device_ids = ["mantra_mfs100", "secugen_hamster_pro", "webcam_retina", "iris_scanner_iritech"]
            actual_device_ids = [d.get("id") for d in devices]
            
            if len(devices) == 4 and all(did in actual_device_ids for did in expected_device_ids):
                log_test("Biometric Supported Devices", True, 
                        f"Returns 4 devices: {', '.join(actual_device_ids)}")
                return True
            else:
                log_test("Biometric Supported Devices", False, 
                        f"Expected 4 devices, got {len(devices)}: {actual_device_ids}")
                return False
        else:
            log_test("Biometric Supported Devices", False, 
                    f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        log_test("Biometric Supported Devices", False, f"Exception: {str(e)}")
        return False

def test_biometric_register():
    """Test POST /api/collaboration/biometric/register"""
    if not session_token:
        log_test("Biometric Register", False, "No session token")
        return False
    
    headers = {"Authorization": f"Bearer {session_token}"}
    payload = {
        "type": "fingerprint",
        "device_id": "mantra_mfs100",
        "template_data": "sample_template_data_hash_12345"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/collaboration/biometric/register", 
                                headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            registered = data.get("registered")
            biometric_type = data.get("type")
            device_id = data.get("device_id")
            
            if registered and biometric_type == "fingerprint" and device_id == "mantra_mfs100":
                log_test("Biometric Register", True, 
                        f"Registered {biometric_type} with device {device_id}")
                return True
            else:
                log_test("Biometric Register", False, 
                        f"Invalid response: {data}")
                return False
        else:
            log_test("Biometric Register", False, 
                    f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        log_test("Biometric Register", False, f"Exception: {str(e)}")
        return False

def test_biometric_verify():
    """Test POST /api/collaboration/biometric/verify"""
    if not session_token:
        log_test("Biometric Verify", False, "No session token")
        return False
    
    headers = {"Authorization": f"Bearer {session_token}"}
    
    # Test with device_token (device-level verification)
    payload = {
        "type": "fingerprint",
        "device_token": "expo_device_auth_token"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/collaboration/biometric/verify", 
                                headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            verified = data.get("verified")
            method = data.get("method")
            
            if verified == True and method == "device_biometric":
                log_test("Biometric Verify", True, 
                        f"Device biometric verification successful (method: {method})")
                return True
            else:
                log_test("Biometric Verify", False, 
                        f"Unexpected response: {data}")
                return False
        else:
            log_test("Biometric Verify", False, 
                    f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        log_test("Biometric Verify", False, f"Exception: {str(e)}")
        return False

def test_biometric_status():
    """Test GET /api/collaboration/biometric/status"""
    if not session_token:
        log_test("Biometric Status", False, "No session token")
        return False
    
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.get(f"{BASE_URL}/collaboration/biometric/status", 
                               headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            has_registered = "registered" in data
            has_registrations = "registrations" in data
            
            if has_registered and has_registrations:
                registered = data["registered"]
                registrations = data["registrations"]
                log_test("Biometric Status", True, 
                        f"Returns registered={registered} with {len(registrations)} registration(s)")
                return True
            else:
                log_test("Biometric Status", False, 
                        f"Missing fields - registered:{has_registered}, registrations:{has_registrations}")
                return False
        else:
            log_test("Biometric Status", False, 
                    f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        log_test("Biometric Status", False, f"Exception: {str(e)}")
        return False

# ========================
# 4. ORG TYPE ON CONTACTS
# ========================

def test_contact_create_with_org_type():
    """Test POST /api/contacts with org_type and org_subtype"""
    global contact_id
    
    if not session_token:
        log_test("Contact Create with Org Type", False, "No session token")
        return False
    
    headers = {"Authorization": f"Bearer {session_token}"}
    timestamp = int(time.time())
    payload = {
        "name": "Test Business Contact",
        "email": f"business_{timestamp}@example.com",
        "phone": "+919876543210",
        "org_type": "business",
        "org_subtype": "pvt_ltd",
        "organization": "Test Pvt Ltd",
        "profession": "CEO"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/contacts", 
                                headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            contact_id = data.get("id")
            org_type = data.get("org_type")
            org_subtype = data.get("org_subtype")
            
            if org_type == "business" and org_subtype == "pvt_ltd":
                log_test("Contact Create with Org Type", True, 
                        f"Contact created with org_type={org_type}, org_subtype={org_subtype}")
                return True
            else:
                log_test("Contact Create with Org Type", False, 
                        f"Org fields not stored correctly: org_type={org_type}, org_subtype={org_subtype}")
                return False
        else:
            log_test("Contact Create with Org Type", False, 
                    f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        log_test("Contact Create with Org Type", False, f"Exception: {str(e)}")
        return False

def test_contact_update_org_type():
    """Test PUT /api/contacts/{id} with org_type and org_subtype"""
    if not session_token or not contact_id:
        log_test("Contact Update Org Type", False, "No session token or contact_id")
        return False
    
    headers = {"Authorization": f"Bearer {session_token}"}
    payload = {
        "org_type": "ngo",
        "org_subtype": "trust"
    }
    
    try:
        response = requests.put(f"{BASE_URL}/contacts/{contact_id}", 
                               headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            org_type = data.get("org_type")
            org_subtype = data.get("org_subtype")
            
            if org_type == "ngo" and org_subtype == "trust":
                log_test("Contact Update Org Type", True, 
                        f"Contact updated to org_type={org_type}, org_subtype={org_subtype}")
                return True
            else:
                log_test("Contact Update Org Type", False, 
                        f"Update failed: org_type={org_type}, org_subtype={org_subtype}")
                return False
        else:
            log_test("Contact Update Org Type", False, 
                    f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        log_test("Contact Update Org Type", False, f"Exception: {str(e)}")
        return False

def test_contact_filter_options():
    """Test GET /api/contacts/filter-options"""
    if not session_token:
        log_test("Contact Filter Options", False, "No session token")
        return False
    
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.get(f"{BASE_URL}/contacts/filter-options", 
                               headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            has_org_type_options = "org_type_options" in data
            has_org_subtype_map = "org_subtype_map" in data
            
            if has_org_type_options and has_org_subtype_map:
                org_type_options = data["org_type_options"]
                org_subtype_map = data["org_subtype_map"]
                
                # Validate structure
                expected_types = ["individual", "business", "ngo", "association", "govt"]
                has_all_types = all(t in org_type_options for t in expected_types)
                has_business_subtypes = "business" in org_subtype_map and "pvt_ltd" in org_subtype_map["business"]
                
                if has_all_types and has_business_subtypes:
                    log_test("Contact Filter Options", True, 
                            f"Returns org_type_options ({len(org_type_options)} types) and org_subtype_map")
                    return True
                else:
                    log_test("Contact Filter Options", False, 
                            f"Invalid structure - all_types:{has_all_types}, business_subtypes:{has_business_subtypes}")
                    return False
            else:
                log_test("Contact Filter Options", False, 
                        f"Missing fields - org_type_options:{has_org_type_options}, org_subtype_map:{has_org_subtype_map}")
                return False
        else:
            log_test("Contact Filter Options", False, 
                    f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        log_test("Contact Filter Options", False, f"Exception: {str(e)}")
        return False

# ========================
# 5. SESSION MODE + CONFIG OVERRIDE
# ========================

def test_create_decision_for_collab():
    """Create a decision for collaboration testing"""
    global decision_id
    
    if not session_token:
        log_test("Create Decision for Collab", False, "No session token")
        return False
    
    headers = {"Authorization": f"Bearer {session_token}"}
    payload = {
        "title": "Test Collaboration Decision",
        "context": "Testing collaboration features with session mode and config override",
        "life_area": "career",
        "ask_type": "need"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/decisions", 
                                headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            decision_id = data.get("id")
            log_test("Create Decision for Collab", True, f"Decision ID: {decision_id}")
            return True
        else:
            log_test("Create Decision for Collab", False, 
                    f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        log_test("Create Decision for Collab", False, f"Exception: {str(e)}")
        return False

def test_collab_session_with_mode_and_override():
    """Test POST /api/collaboration/sessions with session_mode and mode_config_override"""
    global collab_session_id
    
    if not session_token or not decision_id or not contact_id:
        log_test("Collab Session with Mode Override", False, 
                "Missing session_token, decision_id, or contact_id")
        return False
    
    headers = {"Authorization": f"Bearer {session_token}"}
    payload = {
        "module_type": "decision",
        "module_id": decision_id,
        "title": "Test Live Sync Collaboration",
        "decision_mode_id": "command",
        "session_mode": "live_sync",
        "mode_config_override": {
            "leader_weight_pct": 70
        },
        "participant_contact_ids": [contact_id],
        "notify_participants": False
    }
    
    try:
        response = requests.post(f"{BASE_URL}/collaboration/sessions", 
                                headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            collab_session_id = data.get("id")
            session_mode = data.get("session_mode")
            mode_config_override = data.get("mode_config_override")
            
            if session_mode == "live_sync" and mode_config_override and mode_config_override.get("leader_weight_pct") == 70:
                log_test("Collab Session with Mode Override", True, 
                        f"Session created with session_mode={session_mode}, leader_weight_pct=70")
                return True
            else:
                log_test("Collab Session with Mode Override", False, 
                        f"Fields not stored correctly: session_mode={session_mode}, override={mode_config_override}")
                return False
        else:
            log_test("Collab Session with Mode Override", False, 
                    f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        log_test("Collab Session with Mode Override", False, f"Exception: {str(e)}")
        return False

def test_get_collab_session():
    """Test GET /api/collaboration/sessions/{id}"""
    if not session_token or not collab_session_id:
        log_test("Get Collab Session", False, "No session_token or collab_session_id")
        return False
    
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.get(f"{BASE_URL}/collaboration/sessions/{collab_session_id}", 
                               headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            session_mode = data.get("session_mode")
            mode_config_override = data.get("mode_config_override")
            
            if session_mode == "live_sync" and mode_config_override and mode_config_override.get("leader_weight_pct") == 70:
                log_test("Get Collab Session", True, 
                        f"Session retrieved with session_mode={session_mode} and mode_config_override preserved")
                return True
            else:
                log_test("Get Collab Session", False, 
                        f"Fields not retrieved correctly: session_mode={session_mode}, override={mode_config_override}")
                return False
        else:
            log_test("Get Collab Session", False, 
                    f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        log_test("Get Collab Session", False, f"Exception: {str(e)}")
        return False

# ========================
# MAIN TEST EXECUTION
# ========================

def run_all_tests():
    """Run all tests in sequence"""
    print("="*80)
    print("BACKEND API TESTING - NEW COLLABORATION & CONTACT FEATURES")
    print("="*80)
    print(f"Backend URL: {BASE_URL}")
    print(f"Test Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    print()
    
    # Step 1: Setup - Register user and login
    print("STEP 1: User Registration & Authentication")
    print("-"*80)
    if not test_user_registration():
        print("⚠️  User registration failed, trying login...")
        if not test_user_login():
            print("❌ Cannot proceed without authentication")
            print_summary()
            return
    
    # Step 2: Promote to admin (for Postman collection test)
    print("\nSTEP 2: Admin Setup")
    print("-"*80)
    promote_to_admin()
    
    # Step 3: Test Postman Collection Export
    print("\nSTEP 3: Postman Collection Export (Admin-only)")
    print("-"*80)
    test_postman_collection_export()
    
    # Step 4: Test DigiLocker eKYC
    print("\nSTEP 4: DigiLocker eKYC")
    print("-"*80)
    test_digilocker_initiate()
    test_digilocker_status()
    
    # Step 5: Test Biometric Framework
    print("\nSTEP 5: Biometric Framework")
    print("-"*80)
    test_biometric_supported_devices()
    test_biometric_register()
    test_biometric_verify()
    test_biometric_status()
    
    # Step 6: Test Org Type on Contacts
    print("\nSTEP 6: Org Type on Contacts")
    print("-"*80)
    test_contact_create_with_org_type()
    test_contact_update_org_type()
    test_contact_filter_options()
    
    # Step 7: Test Session Mode + Config Override
    print("\nSTEP 7: Session Mode + Config Override")
    print("-"*80)
    test_create_decision_for_collab()
    test_collab_session_with_mode_and_override()
    test_get_collab_session()
    
    # Print summary
    print()
    print_summary()
    
    # Print detailed results
    print("\nDETAILED TEST RESULTS:")
    print("-"*80)
    for test in test_results["tests"]:
        print(f"{test['status']}: {test['name']}")
        if test['details']:
            print(f"  → {test['details']}")

if __name__ == "__main__":
    run_all_tests()
