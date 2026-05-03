#!/usr/bin/env python3
"""
Backend API Testing Script for Social Learning - FINAL SLUG RESOLUTION VERIFICATION
Tests the complete flow for 3-tier Social Learning endpoints with slug-to-HOS-ID mapping
"""

import requests
import json
import time
from datetime import datetime

# Backend URL from environment
BACKEND_URL = "https://dezider-core.preview.emergentagent.com/api"

# Test results tracking
test_results = []
session_token = None

def log_test(test_name, passed, details=""):
    """Log test result"""
    status = "✅ PASSED" if passed else "❌ FAILED"
    result = f"{status}: {test_name}"
    if details:
        result += f" - {details}"
    print(result)
    test_results.append({
        "test": test_name,
        "passed": passed,
        "details": details
    })
    return passed

def print_summary():
    """Print test summary"""
    total = len(test_results)
    passed = sum(1 for r in test_results if r["passed"])
    failed = total - passed
    
    print("\n" + "="*80)
    print("FINAL SLUG RESOLUTION VERIFICATION - TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(passed/total*100):.1f}%")
    print("="*80)
    
    if failed > 0:
        print("\n❌ FAILED TESTS:")
        for r in test_results:
            if not r["passed"]:
                print(f"  - {r['test']}: {r['details']}")
    
    return passed == total

def test_register():
    """Test 1: User Registration"""
    global session_token
    timestamp = int(time.time())
    email = f"slugtest_{timestamp}@test.com"
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/auth/register",
            json={
                "email": email,
                "password": "testpass123",
                "name": "Slug Test User"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if "session_token" in data:
                session_token = data["session_token"]
                return log_test("User Registration", True, f"Registered {email}")
            else:
                return log_test("User Registration", False, "No session_token in response")
        else:
            return log_test("User Registration", False, f"Status {response.status_code}: {response.text}")
    except Exception as e:
        return log_test("User Registration", False, f"Exception: {str(e)}")

def test_login():
    """Test 2: User Login (verify session token works)"""
    global session_token
    
    try:
        response = requests.get(
            f"{BACKEND_URL}/auth/me",
            headers={"Authorization": f"Bearer {session_token}"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if "email" in data:
                return log_test("User Login/Auth", True, f"Authenticated as {data['email']}")
            else:
                return log_test("User Login/Auth", False, "No email in response")
        else:
            return log_test("User Login/Auth", False, f"Status {response.status_code}: {response.text}")
    except Exception as e:
        return log_test("User Login/Auth", False, f"Exception: {str(e)}")

def test_hos_seed():
    """Test 3: HOS Data Seeding"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/hos/seed",
            headers={"Authorization": f"Bearer {session_token}"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if "message" in data:
                return log_test("HOS Data Seeding", True, data["message"])
            else:
                return log_test("HOS Data Seeding", False, "No message in response")
        else:
            return log_test("HOS Data Seeding", False, f"Status {response.status_code}: {response.text}")
    except Exception as e:
        return log_test("HOS Data Seeding", False, f"Exception: {str(e)}")

def test_social_learning_upload():
    """Test 4: Social Learning Upload with AI Classification (90s timeout)"""
    news_content = """A devastating cybersecurity breach at multiple Indian banks compromised financial data of over 5 million customers. The breach exploited vulnerabilities in core banking software. RBI has ordered immediate remediation. Insurance companies are revising cyber risk policies. Multiple state governments announced compensation schemes. The finance ministry has set up a task force to investigate systemic risks in the banking sector."""
    
    try:
        print("  ⏳ Uploading news content (90s timeout for AI classification)...")
        response = requests.post(
            f"{BACKEND_URL}/social-learning/upload",
            headers={"Authorization": f"Bearer {session_token}"},
            json={"content": news_content},
            timeout=90
        )
        
        if response.status_code == 200:
            data = response.json()
            required_fields = ["id", "learnings_mydezider", "learnings_solution_finder"]
            
            # Check required fields
            missing_fields = [f for f in required_fields if f not in data]
            if missing_fields:
                return log_test("Social Learning Upload", False, f"Missing fields: {missing_fields}")
            
            # Check learnings_mydezider.factors
            if "factors" not in data.get("learnings_mydezider", {}):
                return log_test("Social Learning Upload", False, "Missing learnings_mydezider.factors")
            
            # Check learnings_solution_finder.risks
            if "risks" not in data.get("learnings_solution_finder", {}):
                return log_test("Social Learning Upload", False, "Missing learnings_solution_finder.risks")
            
            factors_count = len(data["learnings_mydezider"]["factors"])
            risks_count = len(data["learnings_solution_finder"]["risks"])
            
            return log_test("Social Learning Upload", True, 
                          f"Template {data['id']} created with {factors_count} factors and {risks_count} risks")
        else:
            return log_test("Social Learning Upload", False, f"Status {response.status_code}: {response.text}")
    except requests.exceptions.Timeout:
        return log_test("Social Learning Upload", False, "Request timeout (>90s)")
    except Exception as e:
        return log_test("Social Learning Upload", False, f"Exception: {str(e)}")

def test_templates_for_decision():
    """Test 5: CRITICAL - Templates for Decision with slug 'finance'"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/social-learning/templates-for-decision",
            headers={"Authorization": f"Bearer {session_token}"},
            params={
                "include_personal": "true",
                "life_area": "finance"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Check required 3-tier structure
            required_keys = ["tier_1_personal", "tier_2_authorized", "tier_3_ai_derived", "total"]
            missing_keys = [k for k in required_keys if k not in data]
            if missing_keys:
                return log_test("Templates for Decision (CRITICAL)", False, 
                              f"Missing required keys: {missing_keys}")
            
            # CRITICAL: tier_1_personal must have at least 1 item
            tier_1_count = len(data["tier_1_personal"])
            if tier_1_count < 1:
                return log_test("Templates for Decision (CRITICAL)", False, 
                              f"tier_1_personal has {tier_1_count} items, expected at least 1 (slug 'finance' -> HOS ID 'la_finance' resolution failed)")
            
            # Verify structure
            tier_2_count = len(data["tier_2_authorized"])
            tier_3_count = len(data["tier_3_ai_derived"])
            total = data["total"]
            
            return log_test("Templates for Decision (CRITICAL)", True, 
                          f"3-tier structure verified: tier_1={tier_1_count}, tier_2={tier_2_count}, tier_3={tier_3_count}, total={total}. Slug 'finance' -> HOS ID 'la_finance' resolution WORKING!")
        else:
            return log_test("Templates for Decision (CRITICAL)", False, 
                          f"Status {response.status_code}: {response.text}")
    except Exception as e:
        return log_test("Templates for Decision (CRITICAL)", False, f"Exception: {str(e)}")

def test_templates_for_solution_finder():
    """Test 6: CRITICAL - Templates for Solution Finder with slug 'finance'"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/social-learning/templates-for-solution-finder",
            headers={"Authorization": f"Bearer {session_token}"},
            params={
                "include_personal": "true",
                "life_area": "finance"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Check required 3-tier structure
            required_keys = ["tier_1_personal", "tier_2_authorized", "tier_3_ai_derived", "total"]
            missing_keys = [k for k in required_keys if k not in data]
            if missing_keys:
                return log_test("Templates for Solution Finder (CRITICAL)", False, 
                              f"Missing required keys: {missing_keys}")
            
            # CRITICAL: tier_1_personal must have at least 1 item with risks
            tier_1_count = len(data["tier_1_personal"])
            if tier_1_count < 1:
                return log_test("Templates for Solution Finder (CRITICAL)", False, 
                              f"tier_1_personal has {tier_1_count} items, expected at least 1 (slug 'finance' -> HOS ID 'la_finance' resolution failed)")
            
            # Verify first item has risks
            if tier_1_count > 0:
                first_item = data["tier_1_personal"][0]
                if "risks" not in first_item:
                    return log_test("Templates for Solution Finder (CRITICAL)", False, 
                                  "tier_1_personal items missing 'risks' field")
            
            # Verify structure
            tier_2_count = len(data["tier_2_authorized"])
            tier_3_count = len(data["tier_3_ai_derived"])
            total = data["total"]
            
            return log_test("Templates for Solution Finder (CRITICAL)", True, 
                          f"3-tier structure verified: tier_1={tier_1_count}, tier_2={tier_2_count}, tier_3={tier_3_count}, total={total}. Slug 'finance' -> HOS ID 'la_finance' resolution WORKING!")
        else:
            return log_test("Templates for Solution Finder (CRITICAL)", False, 
                          f"Status {response.status_code}: {response.text}")
    except Exception as e:
        return log_test("Templates for Solution Finder (CRITICAL)", False, f"Exception: {str(e)}")

def test_social_learning_stats():
    """Test 7: Social Learning Stats"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/social-learning/stats",
            headers={"Authorization": f"Bearer {session_token}"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return log_test("Social Learning Stats", True, f"Stats retrieved: {json.dumps(data)}")
        else:
            return log_test("Social Learning Stats", False, f"Status {response.status_code}: {response.text}")
    except Exception as e:
        return log_test("Social Learning Stats", False, f"Exception: {str(e)}")

def test_filter_options():
    """Test 8: Social Learning Filter Options"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/social-learning/filter-options",
            headers={"Authorization": f"Bearer {session_token}"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            required_keys = ["categories", "life_areas"]
            missing_keys = [k for k in required_keys if k not in data]
            if missing_keys:
                return log_test("Filter Options", False, f"Missing keys: {missing_keys}")
            
            categories_count = len(data.get("categories", []))
            life_areas_count = len(data.get("life_areas", []))
            
            return log_test("Filter Options", True, 
                          f"Filter options retrieved: {categories_count} categories, {life_areas_count} life_areas")
        else:
            return log_test("Filter Options", False, f"Status {response.status_code}: {response.text}")
    except Exception as e:
        return log_test("Filter Options", False, f"Exception: {str(e)}")

def main():
    """Run all tests in sequence"""
    print("="*80)
    print("FINAL SLUG RESOLUTION VERIFICATION - Social Learning 3-Tier Endpoints")
    print("Backend URL:", BACKEND_URL)
    print("="*80)
    print()
    
    # Run tests in order
    tests = [
        ("1. Register User", test_register),
        ("2. Login/Auth Check", test_login),
        ("3. Seed HOS Data", test_hos_seed),
        ("4. Upload News (90s timeout)", test_social_learning_upload),
        ("5. Templates for Decision (CRITICAL)", test_templates_for_decision),
        ("6. Templates for Solution Finder (CRITICAL)", test_templates_for_solution_finder),
        ("7. Social Learning Stats", test_social_learning_stats),
        ("8. Filter Options", test_filter_options),
    ]
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        if not test_func():
            print(f"  ⚠️  Test failed, but continuing...")
    
    # Print summary
    all_passed = print_summary()
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED! SLUG RESOLUTION VERIFIED!")
        return 0
    else:
        print("\n⚠️  SOME TESTS FAILED - See details above")
        return 1

if __name__ == "__main__":
    exit(main())
