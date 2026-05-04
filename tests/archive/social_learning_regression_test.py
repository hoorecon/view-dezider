"""
POST-REFACTORING REGRESSION TEST for Social Learning Module
The code was refactored from a monolith (social_learning.py) into a package (social_learning/ with 11 modules).
This test verifies all endpoints still work correctly after refactoring.

Test Flow (as per review request):
1. Register: POST /api/auth/register
2. Login: POST /api/auth/login - get token
3. Seed HOS: POST /api/hos/seed
4. Upload news: POST /api/social-learning/upload (TIMEOUT 90s)
5. Approve factors: POST /api/social-learning/template/{TEMPLATE_ID}/approve-factors
6. Approve risks: POST /api/social-learning/template/{TEMPLATE_ID}/approve-risks
7. GET /api/social-learning/templates-for-decision?include_personal=true
8. GET /api/social-learning/templates-for-solution-finder?include_personal=true
9. GET /api/social-learning/stats
10. GET /api/social-learning/filter-options
"""

import requests
import json
import time
from datetime import datetime

# Backend URL
BASE_URL = "https://dezider-core.preview.emergentagent.com/api"

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
    print("POST-REFACTORING REGRESSION TEST SUMMARY")
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
    print("="*80)
    print("POST-REFACTORING REGRESSION TEST - Social Learning Module")
    print("="*80)
    print(f"Backend URL: {BASE_URL}")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    print("\nRefactoring: social_learning.py → social_learning/ package (11 modules)")
    print("Verifying all endpoints still work correctly...\n")
    
    # Step 1: Register user
    print("\n--- STEP 1: User Registration ---")
    timestamp = int(time.time())
    email = f"regression_test_{timestamp}@test.com"
    password = "SecurePass123!"
    name = "Regression Test User"
    
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
            log_test("1. User Registration", True, f"User created: {email}")
            print(f"  User ID: {user_id}")
            print(f"  Session Token: {session_token[:30]}...")
        else:
            log_test("1. User Registration", False, f"Status {resp.status_code}: {resp.text}")
            print("\n⚠️  Registration failed. Cannot continue.")
            print_summary()
            return
    except Exception as e:
        log_test("1. User Registration", False, str(e))
        print("\n⚠️  Registration failed. Cannot continue.")
        print_summary()
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
            log_test("2. User Login", True, "Login successful, token refreshed")
        else:
            log_test("2. User Login", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("2. User Login", False, str(e))
    
    # Step 3: Seed HOS
    print("\n--- STEP 3: Seed HOS Data ---")
    try:
        resp = requests.post(f"{BASE_URL}/hos/seed", headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            log_test("3. Seed HOS", True, f"HOS data seeded: {data.get('message', 'Success')}")
            print(f"  Life Areas: {data.get('life_areas', 'N/A')}")
            print(f"  Sub Areas: {data.get('sub_areas', 'N/A')}")
            print(f"  Categories: {data.get('categories', 'N/A')}")
        else:
            log_test("3. Seed HOS", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("3. Seed HOS", False, str(e))
    
    # Step 4: Upload news with AI classification (TIMEOUT 90s)
    print("\n--- STEP 4: Upload News (AI Classification - 90s timeout) ---")
    news_content = "A major cybersecurity breach at a leading Indian fintech company exposed financial data of over 2 million users. The breach exploited a zero-day vulnerability in the company payment gateway. RBI has mandated a security audit. Affected users are advised to monitor their bank accounts and change passwords immediately. The company share price dropped 15% following the disclosure."
    
    upload_data = {
        "content": news_content
    }
    
    template_id = None
    try:
        print("  Uploading news article (this may take up to 90 seconds)...")
        resp = requests.post(f"{BASE_URL}/social-learning/upload", json=upload_data, headers=headers, timeout=90)
        if resp.status_code == 200:
            data = resp.json()
            template_id = data.get("template_id") or data.get("id")
            
            # Verify required fields from review request
            has_factors = "learnings_mydezider" in data and "factors" in data.get("learnings_mydezider", {})
            has_risks = "learnings_solution_finder" in data and "risks" in data.get("learnings_solution_finder", {})
            has_region = "region_hierarchy" in data
            has_life_area = "life_area_mapping" in data
            
            factors = data.get("learnings_mydezider", {}).get("factors", [])
            risks = data.get("learnings_solution_finder", {}).get("risks", [])
            
            if has_factors and has_risks and has_region and has_life_area:
                log_test("4. Upload News", True, 
                        f"Template created: {template_id}, {len(factors)} factors, {len(risks)} risks")
                print(f"  Template ID: {template_id}")
                print(f"  Factors: {len(factors)}")
                print(f"  Risks: {len(risks)}")
                print(f"  Region: {data.get('region_hierarchy', {})}")
                print(f"  Life Area: {data.get('life_area_mapping', {})}")
            else:
                missing = []
                if not has_factors: missing.append("learnings_mydezider.factors")
                if not has_risks: missing.append("learnings_solution_finder.risks")
                if not has_region: missing.append("region_hierarchy")
                if not has_life_area: missing.append("life_area_mapping")
                log_test("4. Upload News", False, f"Missing required fields: {', '.join(missing)}")
        else:
            log_test("4. Upload News", False, f"Status {resp.status_code}: {resp.text}")
    except requests.exceptions.Timeout:
        log_test("4. Upload News", False, "Request timed out after 90 seconds")
    except Exception as e:
        log_test("4. Upload News", False, str(e))
    
    if not template_id:
        print("\n⚠️  News upload failed. Cannot continue with template-dependent tests.")
        print_summary()
        return
    
    # Step 5: Approve factors
    print("\n--- STEP 5: Approve Factors ---")
    approve_factors_data = {
        "approved_factor_indices": [0]
    }
    try:
        resp = requests.post(f"{BASE_URL}/social-learning/template/{template_id}/approve-factors", 
                           json=approve_factors_data, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            log_test("5. Approve Factors", True, f"Factor approved: {data.get('message', 'Success')}")
        else:
            log_test("5. Approve Factors", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("5. Approve Factors", False, str(e))
    
    # Step 6: Approve risks
    print("\n--- STEP 6: Approve Risks ---")
    approve_risks_data = {
        "approved_risk_indices": [0]
    }
    try:
        resp = requests.post(f"{BASE_URL}/social-learning/template/{template_id}/approve-risks", 
                           json=approve_risks_data, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            log_test("6. Approve Risks", True, f"Risk approved: {data.get('message', 'Success')}")
        else:
            log_test("6. Approve Risks", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("6. Approve Risks", False, str(e))
    
    # Step 7: GET templates-for-decision (3-tier structure)
    print("\n--- STEP 7: Templates for Decision (3-tier) ---")
    try:
        resp = requests.get(f"{BASE_URL}/social-learning/templates-for-decision?include_personal=true", 
                          headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            
            # Verify 3-tier structure
            has_tier1 = "tier_1_personal" in data
            has_tier2 = "tier_2_authorized" in data
            has_tier3 = "tier_3_ai_derived" in data
            has_total = "total" in data
            
            if has_tier1 and has_tier2 and has_tier3 and has_total:
                tier1_count = len(data.get("tier_1_personal", []))
                tier2_count = len(data.get("tier_2_authorized", []))
                tier3_count = len(data.get("tier_3_ai_derived", []))
                total = data.get("total", 0)
                
                log_test("7. Templates for Decision", True, 
                        f"3-tier structure verified: Tier1={tier1_count}, Tier2={tier2_count}, Tier3={tier3_count}, Total={total}")
                print(f"  Tier 1 (Personal): {tier1_count}")
                print(f"  Tier 2 (Authorized): {tier2_count}")
                print(f"  Tier 3 (AI Derived): {tier3_count}")
                print(f"  Total: {total}")
            else:
                missing = []
                if not has_tier1: missing.append("tier_1_personal")
                if not has_tier2: missing.append("tier_2_authorized")
                if not has_tier3: missing.append("tier_3_ai_derived")
                if not has_total: missing.append("total")
                log_test("7. Templates for Decision", False, f"Missing 3-tier keys: {', '.join(missing)}")
        else:
            log_test("7. Templates for Decision", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("7. Templates for Decision", False, str(e))
    
    # Step 8: GET templates-for-solution-finder (3-tier structure)
    print("\n--- STEP 8: Templates for Solution Finder (3-tier) ---")
    try:
        resp = requests.get(f"{BASE_URL}/social-learning/templates-for-solution-finder?include_personal=true", 
                          headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            
            # Verify 3-tier structure
            has_tier1 = "tier_1_personal" in data
            has_tier2 = "tier_2_authorized" in data
            has_tier3 = "tier_3_ai_derived" in data
            has_total = "total" in data
            
            if has_tier1 and has_tier2 and has_tier3 and has_total:
                tier1_count = len(data.get("tier_1_personal", []))
                tier2_count = len(data.get("tier_2_authorized", []))
                tier3_count = len(data.get("tier_3_ai_derived", []))
                total = data.get("total", 0)
                
                log_test("8. Templates for Solution Finder", True, 
                        f"3-tier structure verified: Tier1={tier1_count}, Tier2={tier2_count}, Tier3={tier3_count}, Total={total}")
                print(f"  Tier 1 (Personal): {tier1_count}")
                print(f"  Tier 2 (Authorized): {tier2_count}")
                print(f"  Tier 3 (AI Derived): {tier3_count}")
                print(f"  Total: {total}")
            else:
                missing = []
                if not has_tier1: missing.append("tier_1_personal")
                if not has_tier2: missing.append("tier_2_authorized")
                if not has_tier3: missing.append("tier_3_ai_derived")
                if not has_total: missing.append("total")
                log_test("8. Templates for Solution Finder", False, f"Missing 3-tier keys: {', '.join(missing)}")
        else:
            log_test("8. Templates for Solution Finder", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("8. Templates for Solution Finder", False, str(e))
    
    # Step 9: GET stats
    print("\n--- STEP 9: Stats ---")
    try:
        resp = requests.get(f"{BASE_URL}/social-learning/stats", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            log_test("9. Stats", True, f"Stats retrieved: {json.dumps(data, indent=2)}")
            print(f"  Stats: {data}")
        else:
            log_test("9. Stats", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("9. Stats", False, str(e))
    
    # Step 10: GET filter-options
    print("\n--- STEP 10: Filter Options ---")
    try:
        resp = requests.get(f"{BASE_URL}/social-learning/filter-options", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            
            # Verify required fields
            has_categories = "categories" in data
            has_life_areas = "life_areas" in data
            has_org_types = "org_types" in data
            
            if has_categories and has_life_areas and has_org_types:
                categories = data.get("categories", [])
                life_areas = data.get("life_areas", [])
                org_types = data.get("org_types", [])
                
                log_test("10. Filter Options", True, 
                        f"Filter options retrieved: {len(categories)} categories, {len(life_areas)} life_areas, {len(org_types)} org_types")
                print(f"  Categories: {len(categories)}")
                print(f"  Life Areas: {len(life_areas)}")
                print(f"  Org Types: {len(org_types)}")
            else:
                missing = []
                if not has_categories: missing.append("categories")
                if not has_life_areas: missing.append("life_areas")
                if not has_org_types: missing.append("org_types")
                log_test("10. Filter Options", False, f"Missing required fields: {', '.join(missing)}")
        else:
            log_test("10. Filter Options", False, f"Status {resp.status_code}: {resp.text}")
    except Exception as e:
        log_test("10. Filter Options", False, str(e))
    
    # Print summary
    print_summary()
    
    # Return exit code based on results
    failed = sum(1 for r in test_results if not r["passed"])
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
