#!/usr/bin/env python3

import requests
import json
from datetime import datetime
import sys

# Configuration
BASE_URL = "https://prr-modal-testing.preview.emergentagent.com/api"

# Test data
USER_A_EMAIL = "userA@test.com"
USER_A_PASSWORD = "test123"
USER_A_NAME = "User A"

USER_B_EMAIL = "userB@test.com"
USER_B_PASSWORD = "test123"
USER_B_NAME = "User B"

def log_test(step, message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] Step {step}: {message}")

def log_error(step, error_message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] ERROR in Step {step}: {error_message}")
    return False

def log_success(step, message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] ✅ Step {step}: {message}")
    return True

def register_user(email, password, name):
    """Register a new user and return session token"""
    url = f"{BASE_URL}/auth/register"
    payload = {
        "email": email,
        "password": password,
        "name": name
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            data = response.json()
            return data.get("session_token")
        else:
            print(f"Registration failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Registration error: {str(e)}")
        return None

def create_decision_with_data(token, title):
    """Create a decision with factors and options"""
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create decision
    create_url = f"{BASE_URL}/decisions"
    decision_data = {
        "title": title,
        "context": "Career decision with multiple factors and options"
    }
    
    response = requests.post(create_url, json=decision_data, headers=headers)
    if response.status_code != 200:
        return None
    
    decision_id = response.json().get("id")
    
    # Update decision with factors and options
    update_url = f"{BASE_URL}/decisions/{decision_id}"
    update_data = {
        "factors": [
            {"id": "f1", "name": "Salary", "category": "primary", "rating": 90, "order": 1},
            {"id": "f2", "name": "Work-Life Balance", "category": "primary", "rating": 85, "order": 2},
            {"id": "f3", "name": "Career Growth", "category": "secondary", "rating": 75, "order": 3}
        ],
        "options": [
            {
                "id": "o1",
                "name": "Company A",
                "assessments": [
                    {"factor_id": "f1", "percentage": 80, "assessment_mode": "H"},
                    {"factor_id": "f2", "percentage": 60, "assessment_mode": "M"},
                    {"factor_id": "f3", "percentage": 90, "assessment_mode": "H"}
                ],
                "worth_percentage": 0.0
            },
            {
                "id": "o2",
                "name": "Company B",
                "assessments": [
                    {"factor_id": "f1", "percentage": 70, "assessment_mode": "M"},
                    {"factor_id": "f2", "percentage": 85, "assessment_mode": "H"},
                    {"factor_id": "f3", "percentage": 75, "assessment_mode": "M"}
                ],
                "worth_percentage": 0.0
            }
        ]
    }
    
    response = requests.put(update_url, json=update_data, headers=headers)
    if response.status_code == 200:
        return decision_id
    else:
        print(f"Failed to update decision: {response.text}")
        return None

def save_template(token, decision_id, name, visibility, shared_with=None):
    """Save a decision as template with specified visibility"""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/decisions/{decision_id}/save-as-template"
    
    payload = {
        "name": name,
        "template_type": "assessment",
        "visibility": visibility
    }
    
    if shared_with:
        payload["shared_with"] = shared_with
    
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json().get("id")
    else:
        print(f"Failed to save template: {response.text}")
        return None

def get_templates(token):
    """Get templates for a user"""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/templates"
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to get templates: {response.text}")
        return None

def import_template(token, template_id):
    """Import a template"""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/templates/{template_id}/import"
    
    response = requests.post(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("id")
    else:
        return response.status_code, response.text

def use_template(token, template_id, title):
    """Use a template to create a new decision"""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{BASE_URL}/templates/{template_id}/use"
    
    payload = {"title": title}
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json().get("id")
    else:
        print(f"Failed to use template: {response.text}")
        return None

def main():
    print("\n=== ENHANCED TEMPLATE SHARING SYSTEM TEST ===\n")
    
    # Step 1: Register User A
    log_test(1, f"Registering User A ({USER_A_EMAIL})")
    token_a = register_user(USER_A_EMAIL, USER_A_PASSWORD, USER_A_NAME)
    if not token_a:
        return log_error(1, "Failed to register User A")
    log_success(1, f"User A registered successfully with token: {token_a[:20]}...")
    
    # Step 2: Register User B
    log_test(2, f"Registering User B ({USER_B_EMAIL})")
    token_b = register_user(USER_B_EMAIL, USER_B_PASSWORD, USER_B_NAME)
    if not token_b:
        return log_error(2, "Failed to register User B")
    log_success(2, f"User B registered successfully with token: {token_b[:20]}...")
    
    # Step 3: User A creates decision with data
    log_test(3, "User A creating decision with factors and options")
    decision_id = create_decision_with_data(token_a, "Career Choice Decision")
    if not decision_id:
        return log_error(3, "Failed to create decision with data")
    log_success(3, f"Decision created with ID: {decision_id}")
    
    # Step 4: User A saves 3 templates with different visibility
    log_test(4, "User A saving 3 templates with different visibility")
    
    # 4a. Private template
    log_test("4a", "Saving private template")
    private_template_id = save_template(token_a, decision_id, "Private Template", "private")
    if not private_template_id:
        return log_error("4a", "Failed to save private template")
    log_success("4a", f"Private template saved: {private_template_id}")
    
    # 4b. Shared template
    log_test("4b", "Saving shared template")
    shared_template_id = save_template(token_a, decision_id, "Shared Template", "shared", [USER_B_EMAIL])
    if not shared_template_id:
        return log_error("4b", "Failed to save shared template")
    log_success("4b", f"Shared template saved: {shared_template_id}")
    
    # 4c. Public template
    log_test("4c", "Saving public template")
    public_template_id = save_template(token_a, decision_id, "Public Template", "public")
    if not public_template_id:
        return log_error("4c", "Failed to save public template")
    log_success("4c", f"Public template saved: {public_template_id}")
    
    # Step 5: User A checks GET /api/templates
    log_test(5, "User A checking template list")
    templates_a = get_templates(token_a)
    if not templates_a:
        return log_error(5, "Failed to get User A templates")
    
    my_templates_count = len(templates_a.get("my_templates", []))
    shared_count = len(templates_a.get("shared_templates", []))
    public_count = len(templates_a.get("public_templates", []))
    
    if my_templates_count != 3:
        return log_error(5, f"Expected 3 my_templates, got {my_templates_count}")
    if shared_count != 0:
        return log_error(5, f"Expected 0 shared_templates, got {shared_count}")
    if public_count != 0:
        return log_error(5, f"Expected 0 public_templates, got {public_count}")
    
    log_success(5, f"User A templates correct: my={my_templates_count}, shared={shared_count}, public={public_count}")
    
    # Step 6: User B checks GET /api/templates
    log_test(6, "User B checking template list")
    templates_b = get_templates(token_b)
    if not templates_b:
        return log_error(6, "Failed to get User B templates")
    
    my_templates_b = len(templates_b.get("my_templates", []))
    shared_templates_b = len(templates_b.get("shared_templates", []))
    public_templates_b = len(templates_b.get("public_templates", []))
    
    if my_templates_b != 0:
        return log_error(6, f"Expected 0 my_templates for User B, got {my_templates_b}")
    if shared_templates_b != 1:
        return log_error(6, f"Expected 1 shared_template for User B, got {shared_templates_b}")
    if public_templates_b != 1:
        return log_error(6, f"Expected 1 public_template for User B, got {public_templates_b}")
    
    # Verify User B cannot see private template
    all_visible_templates = templates_b.get("my_templates", []) + templates_b.get("shared_templates", []) + templates_b.get("public_templates", [])
    private_visible = any(t.get("id") == private_template_id for t in all_visible_templates)
    if private_visible:
        return log_error(6, "User B can see private template - security issue!")
    
    log_success(6, f"User B templates correct: my={my_templates_b}, shared={shared_templates_b}, public={public_templates_b}, private template NOT visible")
    
    # Step 7: User B imports shared template
    log_test(7, "User B importing shared template")
    imported_shared_id = import_template(token_b, shared_template_id)
    if not imported_shared_id:
        return log_error(7, "Failed to import shared template")
    log_success(7, f"Shared template imported: {imported_shared_id}")
    
    # Step 8: User B imports public template
    log_test(8, "User B importing public template")
    imported_public_id = import_template(token_b, public_template_id)
    if not imported_public_id:
        return log_error(8, "Failed to import public template")
    log_success(8, f"Public template imported: {imported_public_id}")
    
    # Step 9: User B tries to import private template (should fail)
    log_test(9, "User B attempting to import private template (should fail with 403)")
    result = import_template(token_b, private_template_id)
    if isinstance(result, tuple):
        status_code, error_msg = result
        if status_code == 403:
            log_success(9, f"Private template access correctly denied with 403: {error_msg}")
        else:
            return log_error(9, f"Expected 403, got {status_code}: {error_msg}")
    else:
        return log_error(9, "Private template import should have failed but succeeded!")
    
    # Step 10: User B uses imported template
    log_test(10, "User B using imported template to create new decision")
    new_decision_id = use_template(token_b, imported_shared_id, "From Imported Template")
    if not new_decision_id:
        return log_error(10, "Failed to use imported template")
    log_success(10, f"New decision created from imported template: {new_decision_id}")
    
    # Verify User B now has 2 imported templates
    log_test("Final", "Verifying final state")
    final_templates_b = get_templates(token_b)
    if not final_templates_b:
        return log_error("Final", "Failed to get final User B templates")
    
    final_my_templates = len(final_templates_b.get("my_templates", []))
    if final_my_templates != 2:
        return log_error("Final", f"Expected 2 my_templates after imports, got {final_my_templates}")
    
    log_success("Final", f"User B has {final_my_templates} templates after imports")
    
    print(f"\n🎉 ALL TESTS PASSED! Enhanced template sharing system working correctly:")
    print(f"   ✅ User registration and authentication")
    print(f"   ✅ Decision creation with factors and options")
    print(f"   ✅ Template creation with different visibility levels (private/shared/public)")
    print(f"   ✅ Cross-user template visibility rules")
    print(f"   ✅ Template import functionality")
    print(f"   ✅ Private template access control (403 on unauthorized access)")
    print(f"   ✅ Template usage to create new decisions")
    print(f"   ✅ Complete enhanced template sharing workflow")
    
    return True

def test_admin_system():
    """Test 3-tier admin system and authorized templates"""
    print("\n🔧 TESTING 3-TIER ADMIN SYSTEM")
    print("=" * 50)
    
    # Generate unique emails with timestamp for new users to avoid conflicts
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    
    # Use existing super admin
    super_email = "super@test.com"
    super_password = "test123"
    super_name = "Super Admin"
    
    # New users with unique emails
    coadmin_email = f"coadmin{timestamp}@test.com"
    coadmin_password = "test123"
    coadmin_name = "Co Admin"
    
    admin_email = f"admin{timestamp}@test.com"
    admin_password = "test123"
    admin_name = "Regular Admin"
    
    # Step 1: Login existing super admin and register 2 new users
    log_test("1", "Logging in existing super admin and registering 2 new users")
    
    # Login existing super admin
    login_url = f"{BASE_URL}/auth/login"
    response = requests.post(login_url, json={
        "email": super_email,
        "password": super_password
    })
    if response.status_code != 200:
        return log_error("1a", f"Failed to login existing super admin: {response.status_code} - {response.text}")
    super_token = response.json().get("session_token")
    log_success("1a", f"Super admin logged in successfully")
    
    coadmin_token = register_user(coadmin_email, coadmin_password, coadmin_name)
    if not coadmin_token:
        return log_error("1b", "Failed to register CoAdmin user")
    log_success("1b", f"CoAdmin user registered successfully")
    
    admin_token = register_user(admin_email, admin_password, admin_name)
    if not admin_token:
        return log_error("1c", "Failed to register Admin user")
    log_success("1c", f"Admin user registered successfully")
    
    # Step 2: Verify admin setup and existing super admin
    log_test("2", "Verifying admin setup with existing super admin")
    
    headers_super = {"Authorization": f"Bearer {super_token}"}
    
    # Verify super admin role
    me_url = f"{BASE_URL}/auth/me"
    response = requests.get(me_url, headers=headers_super)
    if response.status_code != 200:
        return log_error("2a", f"Failed to get super user info: {response.status_code}")
    
    super_data = response.json()
    if super_data.get("role") != "super_admin":
        return log_error("2a", f"Expected role 'super_admin', got: {super_data.get('role')}")
    log_success("2a", f"Super admin verified with correct role: {super_data.get('role')}")
    
    # CoAdmin tries to become super_admin (should fail)
    headers_coadmin = {"Authorization": f"Bearer {coadmin_token}"}
    setup_url = f"{BASE_URL}/admin/setup"
    response = requests.post(setup_url, headers=headers_coadmin)
    if response.status_code != 400:
        return log_error("2b", f"Expected 400 when CoAdmin tries setup, got: {response.status_code}")
    log_success("2b", "CoAdmin correctly denied admin setup (super already exists)")
    
    # Step 3: Skip this since we already verified in step 2
    
    # Step 4: Super Admin promotes users
    log_test("4", "Testing user promotion")
    
    promote_url = f"{BASE_URL}/admin/promote"
    
    # Promote CoAdmin to co_admin
    promote_data = {"email": coadmin_email, "role": "co_admin"}
    response = requests.post(promote_url, json=promote_data, headers=headers_super)
    if response.status_code != 200:
        return log_error("4a", f"Failed to promote CoAdmin: {response.status_code} - {response.text}")
    log_success("4a", "CoAdmin promoted to co_admin successfully")
    
    # Promote Admin to admin
    promote_data = {"email": admin_email, "role": "admin"}
    response = requests.post(promote_url, json=promote_data, headers=headers_super)
    if response.status_code != 200:
        return log_error("4b", f"Failed to promote Admin: {response.status_code} - {response.text}")
    log_success("4b", "Admin promoted to admin successfully")
    
    # Step 5: Test GET /api/admin/users
    log_test("5", "Testing admin users list")
    
    users_url = f"{BASE_URL}/admin/users"
    response = requests.get(users_url, headers=headers_super)
    if response.status_code != 200:
        return log_error("5", f"Failed to get admin users: {response.status_code} - {response.text}")
    
    admin_users = response.json()
    if len(admin_users) < 3:
        return log_error("5", f"Expected at least 3 admin users, got: {len(admin_users)}")
    
    # Check that our specific users exist with correct roles
    user_emails = [user.get("email") for user in admin_users]
    expected_users = {
        super_email: "super_admin",
        coadmin_email: "co_admin",  
        admin_email: "admin"
    }
    
    for email, expected_role in expected_users.items():
        found_user = None
        for user in admin_users:
            if user.get("email") == email:
                found_user = user
                break
        
        if not found_user:
            return log_error("5", f"User {email} not found in admin users list")
        
        if found_user.get("role") != expected_role:
            return log_error("5", f"User {email} has role {found_user.get('role')}, expected {expected_role}")
    
    log_success("5", f"Admin users list contains our 3 test users with correct roles (total {len(admin_users)} admin users)")
    
    # Step 6: Permission tests
    log_test("6", "Testing permission matrix")
    
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    
    # 6a: Admin tries to promote someone (should fail)
    promote_data = {"email": "test@example.com", "role": "admin"}
    response = requests.post(promote_url, json=promote_data, headers=headers_admin)
    if response.status_code != 403:
        return log_error("6a", f"Expected 403 when Admin tries to promote, got: {response.status_code}")
    log_success("6a", "Admin correctly denied promotion privileges (403)")
    
    # 6b: CoAdmin tries to promote to co_admin (should fail)
    promote_data = {"email": admin_email, "role": "co_admin"}  # Try to promote existing admin to co_admin
    response = requests.post(promote_url, json=promote_data, headers=headers_coadmin)
    if response.status_code != 403:
        return log_error("6b", f"Expected 403 when CoAdmin tries to create co_admin, got: {response.status_code}")
    log_success("6b", "CoAdmin correctly denied co_admin promotion (only super can)")
    
    # 6c: CoAdmin promotes to admin (should succeed - create a new user first)
    # Register a test user to promote
    test_email = f"testuser{timestamp}@test.com"
    test_user_token = register_user(test_email, "test123", "Test User")
    if not test_user_token:
        return log_error("6c", "Failed to register test user for promotion")
    
    promote_data = {"email": test_email, "role": "admin"}
    response = requests.post(promote_url, json=promote_data, headers=headers_coadmin)
    if response.status_code != 200:
        return log_error("6c", f"CoAdmin failed to promote to admin: {response.status_code} - {response.text}")
    log_success("6c", "CoAdmin successfully promoted user to admin")
    
    # 6d: Admin tries to demote someone (should fail)
    demote_url = f"{BASE_URL}/admin/demote"
    demote_data = {"email": test_email}
    response = requests.post(demote_url, json=demote_data, headers=headers_admin)
    if response.status_code != 403:
        return log_error("6d", f"Expected 403 when Admin tries to demote, got: {response.status_code}")
    log_success("6d", "Admin correctly denied demotion privileges (403)")
    
    # 6e: CoAdmin tries to demote admin (should succeed)
    response = requests.post(demote_url, json=demote_data, headers=headers_coadmin)
    if response.status_code != 200:
        return log_error("6e", f"CoAdmin failed to demote admin: {response.status_code} - {response.text}")
    log_success("6e", "CoAdmin successfully demoted admin user")
    
    # 6f: CoAdmin tries to demote super_admin (should fail)
    demote_data = {"email": super_email}
    response = requests.post(demote_url, json=demote_data, headers=headers_coadmin)
    if response.status_code != 403:
        return log_error("6f", f"Expected 403 when trying to demote super_admin, got: {response.status_code}")
    log_success("6f", "CoAdmin correctly denied demoting super_admin (403)")
    
    # 6g: Super Admin demotes Co-Admin (should succeed)
    demote_data = {"email": coadmin_email}
    response = requests.post(demote_url, json=demote_data, headers=headers_super)
    if response.status_code != 200:
        return log_error("6g", f"Super Admin failed to demote co-admin: {response.status_code} - {response.text}")
    log_success("6g", "Super Admin successfully demoted Co-Admin")
    
    # Step 7: Template authorization tests
    log_test("7", "Testing template authorization")
    
    # First create a decision and save as public template
    decision_id = create_decision_with_data(super_token, "Template Decision")
    if not decision_id:
        return log_error("7", "Failed to create decision for template testing")
    
    # Save as public template
    template_url = f"{BASE_URL}/decisions/{decision_id}/save-as-template"
    template_data = {
        "name": "Test Authorization Template",
        "template_type": "assessment",
        "visibility": "public"
    }
    response = requests.post(template_url, json=template_data, headers=headers_super)
    if response.status_code != 200:
        return log_error("7", f"Failed to save template: {response.status_code} - {response.text}")
    response_data = response.json()
    template_id = response_data.get("id")
    if not template_id:
        return log_error("7", f"No template ID in response: {response_data}")
    log_success("7a", f"Public template created successfully with ID: {template_id}")
    
    # 7b: Approve template (as Super Admin)
    approve_url = f"{BASE_URL}/admin/templates/{template_id}/approve"
    response = requests.post(approve_url, headers=headers_super)
    if response.status_code != 200:
        return log_error("7b", f"Failed to approve template: {response.status_code} - {response.text}")
    log_success("7b", "Template approved successfully")
    
    # 7c: Check authorized templates in GET /api/templates
    templates_url = f"{BASE_URL}/templates"
    response = requests.get(templates_url, headers=headers_super)
    if response.status_code != 200:
        return log_error("7c", f"Failed to get templates: {response.status_code} - {response.text}")
    
    templates_data = response.json()
    authorized_templates = templates_data.get("authorized_templates", [])
    if len(authorized_templates) == 0:
        return log_error("7c", "No authorized templates found after approval")
    
    # Check if our template is in authorized list
    found_template = False
    for template in authorized_templates:
        if template.get("id") == template_id:
            found_template = True
            if not template.get("authorized"):
                return log_error("7c", "Template found but not marked as authorized")
            break
    
    if not found_template:
        return log_error("7c", "Approved template not found in authorized_templates list")
    log_success("7c", "Authorized template correctly appears in templates list")
    
    # 7d: Revoke template authorization
    revoke_url = f"{BASE_URL}/admin/templates/{template_id}/revoke"
    response = requests.post(revoke_url, headers=headers_super)
    if response.status_code != 200:
        return log_error("7d", f"Failed to revoke template: {response.status_code} - {response.text}")
    log_success("7d", "Template authorization revoked successfully")
    
    # 7e: Non-admin tries to approve (should fail - use regular user token)
    response = requests.post(approve_url, headers={"Authorization": f"Bearer {test_user_token}"})
    if response.status_code != 403:
        return log_error("7e", f"Expected 403 when non-admin tries to approve, got: {response.status_code}")
    log_success("7e", "Non-admin correctly denied template approval (403)")
    
    print(f"\n🎉 ALL ADMIN SYSTEM TESTS PASSED!")
    print(f"   ✅ 3-tier admin system working correctly")
    print(f"   ✅ User registration and bootstrap setup")
    print(f"   ✅ Role promotion and demotion with proper permissions")
    print(f"   ✅ Admin users list endpoint")
    print(f"   ✅ Complete permission matrix validation")
    print(f"   ✅ Template authorization system")
    print(f"   ✅ All security controls functioning properly")
    
    return True

if __name__ == "__main__":
    success = test_admin_system()
    if not success:
        sys.exit(1)