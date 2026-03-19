#!/usr/bin/env python3

import requests
import json
from datetime import datetime
import sys

# Configuration
BASE_URL = "https://best-mate-decisions.preview.emergentagent.com/api"

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

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)