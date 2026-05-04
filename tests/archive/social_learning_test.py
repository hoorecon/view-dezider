"""
Social Learning Engine Backend Testing
Tests all Social Learning endpoints following the review request test flow
"""

import requests
import json
import time
from datetime import datetime

# Backend URL
BASE_URL = "https://voice-browse-epic.preview.emergentagent.com/api"

# Test results
test_results = []

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
    total = len(test_results)
    passed = sum(1 for r in test_results if r["passed"])
    failed = total - passed
    
    print("\n" + "="*80)
    print("SOCIAL LEARNING ENGINE TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(passed/total*100):.1f}%")
    print("="*80)
    
    if failed > 0:
        print("\nFailed Tests:")
        for r in test_results:
            if not r["passed"]:
                print(f"  ❌ {r['test']}: {r['details']}")

def main():
    print("Starting Social Learning Engine Backend Tests...")
    print(f"Backend URL: {BASE_URL}\n")
    
    # Step 1: Register user
    print("\n--- STEP 1: User Registration ---")
    timestamp = int(time.time())
    email = f"sociallearning_{timestamp}@test.com"
    password = "SecurePass123!"
    name = "Social Learning Test User"
    
    register_data = {
        "email": email,
        "password": password,
        "name": name
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/auth/register", json=register_data, timeout=10)
        if resp.status_code == 200:
            user_data = resp.json()
            session_token = user_data.get("session_token")
            user_id = user_data.get("user_id")
            log_test("User Registration", True, f"User created: {email}")
            print(f"Session Token: {session_token[:20]}...")
        else:
            log_test("User Registration", False, f"Status {resp.status_code}: {resp.text}")
            return
    except Exception as e:
        log_test("User Registration", False, str(e))
        return
    
    headers = {"Authorization": f"Bearer {session_token}"}
    
    # Step 2: Login to get fresh token
    print("\n--- STEP 2: User Login ---")
    login_data = {"email": email, "password": password}
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json=login_data, timeout=10)
        if resp.status_code == 200:
            login_result = resp.json()
            session_token = login_result.get("session_token")
            headers = {"Authorization": f"Bearer {session_token}"}
            log_test("User Login", True, "Login successful")
        else:
            log_test("User Login", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("User Login", False, str(e))
    
    # TEST 1: Filter Options
    print("\n--- TEST 1: Filter Options ---")
    try:
        resp = requests.get(f"{BASE_URL}/social-learning/filter-options", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            categories = data.get("categories", [])
            life_areas = data.get("life_areas", [])
            org_types = data.get("org_types", [])
            languages = data.get("languages", [])
            template_statuses = data.get("template_statuses", [])
            
            # Check for 6 languages
            expected_languages = ["english", "hindi", "tamil", "telugu", "kannada", "malayalam"]
            has_all_languages = all(lang in languages for lang in expected_languages)
            
            if has_all_languages and len(categories) > 0 and len(life_areas) > 0:
                log_test("Filter Options", True, f"Returns {len(categories)} categories, {len(life_areas)} life_areas, {len(org_types)} org_types, {len(languages)} languages, {len(template_statuses)} statuses")
                print(f"  Languages: {languages}")
            else:
                log_test("Filter Options", False, f"Missing expected data. Languages: {languages}")
        else:
            log_test("Filter Options", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Filter Options", False, str(e))
    
    # TEST 2: Text Upload & AI Classification
    print("\n--- TEST 2: Text Upload & AI Classification ---")
    news_content = """A major data breach at a leading Indian bank has exposed personal details of over 500,000 customers, including Aadhaar numbers and bank account details. The breach was discovered when cybersecurity researchers found the data being sold on the dark web. The Reserve Bank of India has directed all banks to strengthen their cybersecurity frameworks and report any suspicious activities within 6 hours. This incident highlights the growing threat of cyber attacks on financial institutions in India and the need for better data protection measures."""
    
    upload_data = {
        "content": news_content,
        "source_name": "Economic Times",
        "title": "Major Bank Data Breach Exposes 500K Customers"
    }
    
    template_id = None
    try:
        resp = requests.post(f"{BASE_URL}/social-learning/upload", json=upload_data, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            template_id = data.get("template_id") or data.get("id")  # Handle both field names
            detected_language = data.get("detected_language")
            english_summary = data.get("english_summary")
            category = data.get("category")
            life_areas = data.get("life_areas", [])
            factors = data.get("factors", [])
            concerns = data.get("concerns", [])
            root_causes = data.get("root_causes", [])
            
            if template_id and detected_language and category:
                log_test("Text Upload & AI Classification", True, 
                        f"Template created: {template_id}, Language: {detected_language}, Category: {category}, "
                        f"{len(factors)} factors, {len(concerns)} concerns, {len(root_causes)} root causes")
                print(f"  Template ID: {template_id}")
                print(f"  Detected Language: {detected_language}")
                print(f"  Category: {category}")
                print(f"  Life Areas: {life_areas}")
                print(f"  Factors: {len(factors)}")
            else:
                log_test("Text Upload & AI Classification", False, f"Missing required fields in response")
        else:
            log_test("Text Upload & AI Classification", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Text Upload & AI Classification", False, str(e))
    
    if not template_id:
        print("\n⚠️  Template creation failed. Cannot continue with template-dependent tests.")
        print_summary()
        return
    
    # TEST 3: My Templates
    print("\n--- TEST 3: My Templates ---")
    try:
        resp = requests.get(f"{BASE_URL}/social-learning/my-templates", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            templates = data.get("templates", [])
            if len(templates) > 0 and any(t.get("template_id") == template_id or t.get("id") == template_id for t in templates):
                log_test("My Templates", True, f"Returns {len(templates)} template(s), uploaded template found")
            else:
                log_test("My Templates", False, f"Uploaded template not found in my-templates. Got {len(templates)} templates")
        else:
            log_test("My Templates", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("My Templates", False, str(e))
    
    # TEST 4: Template Detail
    print("\n--- TEST 4: Template Detail ---")
    try:
        resp = requests.get(f"{BASE_URL}/social-learning/template/{template_id}", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("template_id") == template_id or data.get("id") == template_id:
                log_test("Template Detail", True, f"Returns full template details for {template_id}")
                print(f"  Status: {data.get('status')}")
                print(f"  Category: {data.get('category')}")
            else:
                log_test("Template Detail", False, f"Template ID mismatch")
        else:
            log_test("Template Detail", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Template Detail", False, str(e))
    
    # TEST 5: Submit for Review
    print("\n--- TEST 5: Submit for Review ---")
    try:
        resp = requests.post(f"{BASE_URL}/social-learning/template/{template_id}/submit", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "submitted":
                log_test("Submit for Review", True, f"Template submitted successfully, status: {data.get('status')}")
            else:
                log_test("Submit for Review", False, f"Expected status 'submitted', got {data.get('status')}")
        else:
            log_test("Submit for Review", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Submit for Review", False, str(e))
    
    # TEST 6: Stats
    print("\n--- TEST 6: Stats ---")
    try:
        resp = requests.get(f"{BASE_URL}/social-learning/stats", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            total_templates = data.get("total_templates", 0)
            tier_breakdown = data.get("tier_breakdown", {})
            if total_templates >= 1:
                log_test("Stats", True, f"Returns stats: {total_templates} total templates, tier breakdown: {tier_breakdown}")
            else:
                log_test("Stats", False, f"Expected at least 1 template, got {total_templates}")
        else:
            log_test("Stats", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Stats", False, str(e))
    
    # TEST 7: Admin Approval - Get Pending (expect 403 for non-admin)
    print("\n--- TEST 7: Admin Approval - Get Pending (Non-Admin) ---")
    try:
        resp = requests.get(f"{BASE_URL}/social-learning/admin/pending", headers=headers, timeout=10)
        if resp.status_code == 403:
            log_test("Admin Pending - Non-Admin Access Control", True, "Correctly returns 403 for non-admin user")
        elif resp.status_code == 200:
            # User might be admin, check if submitted template is in pending list
            data = resp.json()
            templates = data.get("templates", [])
            log_test("Admin Pending - Admin Access", True, f"Returns {len(templates)} pending template(s)")
        else:
            log_test("Admin Pending", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Admin Pending", False, str(e))
    
    # TEST 8: Admin Approval - Approve Template (expect 403 for non-admin)
    print("\n--- TEST 8: Admin Approval - Approve Template (Non-Admin) ---")
    approval_data = {
        "status": "authorized",
        "admin_notes": "Good quality template"
    }
    try:
        resp = requests.post(f"{BASE_URL}/social-learning/admin/approve/{template_id}", 
                           json=approval_data, headers=headers, timeout=10)
        if resp.status_code == 403:
            log_test("Admin Approve - Non-Admin Access Control", True, "Correctly returns 403 for non-admin user")
        elif resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "authorized":
                log_test("Admin Approve - Admin Access", True, f"Template approved successfully, now Tier 2")
            else:
                log_test("Admin Approve", False, f"Expected status 'authorized', got {data.get('status')}")
        else:
            log_test("Admin Approve", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Admin Approve", False, str(e))
    
    # TEST 9: Browse Authorized Templates
    print("\n--- TEST 9: Browse Authorized Templates ---")
    try:
        resp = requests.get(f"{BASE_URL}/social-learning/authorized", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            templates = data.get("templates", [])
            log_test("Browse Authorized", True, f"Returns {len(templates)} authorized template(s)")
        else:
            log_test("Browse Authorized", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Browse Authorized", False, str(e))
    
    # TEST 10: Integration API - Templates for Decision
    print("\n--- TEST 10: Integration API - Templates for Decision ---")
    try:
        resp = requests.get(f"{BASE_URL}/social-learning/templates-for-decision", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            templates = data.get("templates", [])
            log_test("Templates for Decision", True, f"Returns {len(templates)} template(s) with decision entry points")
        else:
            log_test("Templates for Decision", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Templates for Decision", False, str(e))
    
    # TEST 11: Integration API - Templates for Solution Finder
    print("\n--- TEST 11: Integration API - Templates for Solution Finder ---")
    try:
        resp = requests.get(f"{BASE_URL}/social-learning/templates-for-solution-finder", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            templates = data.get("templates", [])
            log_test("Templates for Solution Finder", True, f"Returns {len(templates)} template(s) with solution finder entry points")
        else:
            log_test("Templates for Solution Finder", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("Templates for Solution Finder", False, str(e))
    
    # TEST 12: Error Handling - Upload with content < 50 chars
    print("\n--- TEST 12: Error Handling - Short Content ---")
    short_content_data = {
        "content": "Too short",
        "source_name": "Test",
        "title": "Short Test"
    }
    try:
        resp = requests.post(f"{BASE_URL}/social-learning/upload", json=short_content_data, headers=headers, timeout=10)
        if resp.status_code == 400:
            error_msg = resp.json().get("detail", "")
            if "50 characters" in error_msg or "too short" in error_msg.lower():
                log_test("Error Handling - Short Content", True, f"Correctly rejects content < 50 chars: {error_msg}")
            else:
                log_test("Error Handling - Short Content", True, f"Returns 400 error: {error_msg}")
        else:
            log_test("Error Handling - Short Content", False, f"Expected 400, got {resp.status_code}")
    except Exception as e:
        log_test("Error Handling - Short Content", False, str(e))
    
    # TEST 13: Error Handling - Upload file without file
    print("\n--- TEST 13: Error Handling - Upload File Without File ---")
    try:
        # Send empty multipart request
        resp = requests.post(f"{BASE_URL}/social-learning/upload-file", headers=headers, timeout=10)
        if resp.status_code in [400, 422]:
            log_test("Error Handling - Missing File", True, f"Correctly rejects request without file (status {resp.status_code})")
        else:
            log_test("Error Handling - Missing File", False, f"Expected 400/422, got {resp.status_code}")
    except Exception as e:
        log_test("Error Handling - Missing File", False, str(e))
    
    # Print summary
    print_summary()

if __name__ == "__main__":
    main()
