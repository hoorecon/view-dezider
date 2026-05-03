"""
Backend API Testing for 3-Tier Social Learning Integration
Tests the complete Social Learning workflow with HOS integration
Backend URL: https://dezider-core.preview.emergentagent.com/api
"""

import requests
import json
import time
from datetime import datetime

# Backend URL
BASE_URL = "https://dezider-core.preview.emergentagent.com/api"

# Test results tracking
test_results = []
session_token = None
template_id = None
test_email = None
test_password = "Test123456"

def log_test(test_name, passed, details=""):
    """Log test result"""
    status = "✅ PASSED" if passed else "❌ FAILED"
    result = {
        "test": test_name,
        "status": status,
        "passed": passed,
        "details": details,
        "timestamp": datetime.now().isoformat()
    }
    test_results.append(result)
    print(f"\n{status}: {test_name}")
    if details:
        print(f"  Details: {details}")
    return passed


def print_summary():
    """Print test summary"""
    total = len(test_results)
    passed = sum(1 for r in test_results if r["passed"])
    failed = total - passed
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
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
                print(f"  - {r['test']}: {r['details']}")


def test_1_register_user():
    """Test 1: Register a new user"""
    global session_token, test_email
    
    timestamp = int(time.time())
    test_email = f"socialtest_{timestamp}@test.com"
    name = "Social Learning Test User"
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json={
                "email": test_email,
                "password": test_password,
                "name": name
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if "session_token" in data:
                session_token = data["session_token"]
                return log_test(
                    "User Registration",
                    True,
                    f"Registered user: {test_email}, Token: {session_token[:20]}..."
                )
            else:
                return log_test("User Registration", False, "No session_token in response")
        else:
            return log_test("User Registration", False, f"Status: {response.status_code}, Response: {response.text[:200]}")
    
    except Exception as e:
        return log_test("User Registration", False, f"Exception: {str(e)}")


def test_2_login_user():
    """Test 2: Login with the registered user"""
    global session_token, test_email
    
    if not test_email:
        return log_test("User Login", False, "No test email available")
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": test_email,
                "password": test_password
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if "session_token" in data:
                session_token = data["session_token"]
                return log_test(
                    "User Login",
                    True,
                    f"Login successful, Token: {session_token[:20]}..."
                )
            else:
                return log_test("User Login", False, "No session_token in response")
        else:
            return log_test("User Login", False, f"Status: {response.status_code}, Response: {response.text[:200]}")
    
    except Exception as e:
        return log_test("User Login", False, f"Exception: {str(e)}")


def test_3_seed_hos_data():
    """Test 3: Seed HOS data"""
    global session_token
    
    if not session_token:
        return log_test("Seed HOS Data", False, "No session token available")
    
    try:
        response = requests.post(
            f"{BASE_URL}/hos/seed",
            headers={"Authorization": f"Bearer {session_token}"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return log_test(
                "Seed HOS Data",
                True,
                f"HOS data seeded: {json.dumps(data)[:200]}"
            )
        else:
            return log_test("Seed HOS Data", False, f"Status: {response.status_code}, Response: {response.text[:200]}")
    
    except Exception as e:
        return log_test("Seed HOS Data", False, f"Exception: {str(e)}")


def test_4_upload_news():
    """Test 4: Upload news article with AI classification"""
    global session_token, template_id
    
    if not session_token:
        return log_test("Upload News", False, "No session token available")
    
    # Detailed news article about financial fraud
    news_content = """
    A major financial fraud case has shaken the banking sector in India. Over 10,000 customers of a prominent national bank lost their savings amounting to over Rs 500 crore due to a sophisticated cyber attack exploiting weak encryption protocols. The Reserve Bank of India has ordered a forensic audit and the Central Bureau of Investigation has registered a case. Multiple employees including the Chief Information Security Officer have been suspended. The attack vector was a supply chain compromise targeting the bank's third-party payment gateway. Experts recommend immediate implementation of end-to-end encryption, multi-factor authentication, and continuous threat monitoring. Insurance companies are now revising their cyber insurance policies and premiums across the banking sector.
    """
    
    try:
        response = requests.post(
            f"{BASE_URL}/social-learning/upload",
            headers={"Authorization": f"Bearer {session_token}"},
            json={"content": news_content.strip()},
            timeout=90  # 90 second timeout as specified
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Verify required fields
            required_fields = [
                "region_hierarchy",
                "life_area_mapping",
                "learnings_mydezider",
                "learnings_solution_finder"
            ]
            
            missing_fields = [f for f in required_fields if f not in data]
            if missing_fields:
                return log_test("Upload News", False, f"Missing fields: {missing_fields}")
            
            # Verify region_hierarchy structure
            if "level" not in data["region_hierarchy"] or "country" not in data["region_hierarchy"]:
                return log_test("Upload News", False, "region_hierarchy missing 'level' or 'country'")
            
            # Verify life_area_mapping structure
            if "primary_life_area_id" not in data["life_area_mapping"] or "sub_area_1" not in data["life_area_mapping"]:
                return log_test("Upload News", False, "life_area_mapping missing 'primary_life_area_id' or 'sub_area_1'")
            
            # Verify learnings_mydezider.factors structure
            if "factors" not in data["learnings_mydezider"]:
                return log_test("Upload News", False, "learnings_mydezider missing 'factors'")
            
            factors = data["learnings_mydezider"]["factors"]
            if not isinstance(factors, list) or len(factors) == 0:
                return log_test("Upload News", False, "learnings_mydezider.factors is not a non-empty array")
            
            # Verify factor structure
            factor_required_fields = ["practical_priority", "classification", "expected_value", "expected_value_pct"]
            for i, factor in enumerate(factors):
                missing = [f for f in factor_required_fields if f not in factor]
                if missing:
                    return log_test("Upload News", False, f"Factor {i} missing fields: {missing}")
            
            # Verify learnings_solution_finder.risks structure
            if "risks" not in data["learnings_solution_finder"]:
                return log_test("Upload News", False, "learnings_solution_finder missing 'risks'")
            
            risks = data["learnings_solution_finder"]["risks"]
            if not isinstance(risks, list) or len(risks) == 0:
                return log_test("Upload News", False, "learnings_solution_finder.risks is not a non-empty array")
            
            # Verify risk structure
            risk_required_fields = ["probability", "impact", "risk_index", "mitigation_plan", "contingency_plan"]
            for i, risk in enumerate(risks):
                missing = [f for f in risk_required_fields if f not in risk]
                if missing:
                    return log_test("Upload News", False, f"Risk {i} missing fields: {missing}")
            
            # Store template_id for later tests
            if "id" in data:
                template_id = data["id"]
            elif "template_id" in data:
                template_id = data["template_id"]
            
            return log_test(
                "Upload News",
                True,
                f"Template ID: {template_id}, Factors: {len(factors)}, Risks: {len(risks)}, Region: {data['region_hierarchy']['country']}, Life Area: {data['life_area_mapping']['primary_life_area_id']}"
            )
        else:
            return log_test("Upload News", False, f"Status: {response.status_code}, Response: {response.text[:500]}")
    
    except Exception as e:
        return log_test("Upload News", False, f"Exception: {str(e)}")


def test_5_approve_factors():
    """Test 5: Approve factors"""
    global session_token, template_id
    
    if not session_token:
        return log_test("Approve Factors", False, "No session token available")
    
    if not template_id:
        return log_test("Approve Factors", False, "No template_id available")
    
    try:
        response = requests.post(
            f"{BASE_URL}/social-learning/template/{template_id}/approve-factors",
            headers={"Authorization": f"Bearer {session_token}"},
            json={"approved_factor_indices": [0, 1, 2]},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return log_test(
                "Approve Factors",
                True,
                f"Approved factors: {json.dumps(data)[:200]}"
            )
        else:
            return log_test("Approve Factors", False, f"Status: {response.status_code}, Response: {response.text[:200]}")
    
    except Exception as e:
        return log_test("Approve Factors", False, f"Exception: {str(e)}")


def test_6_approve_risks():
    """Test 6: Approve risks"""
    global session_token, template_id
    
    if not session_token:
        return log_test("Approve Risks", False, "No session token available")
    
    if not template_id:
        return log_test("Approve Risks", False, "No template_id available")
    
    try:
        response = requests.post(
            f"{BASE_URL}/social-learning/template/{template_id}/approve-risks",
            headers={"Authorization": f"Bearer {session_token}"},
            json={"approved_risk_indices": [0]},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return log_test(
                "Approve Risks",
                True,
                f"Approved risks: {json.dumps(data)[:200]}"
            )
        else:
            return log_test("Approve Risks", False, f"Status: {response.status_code}, Response: {response.text[:200]}")
    
    except Exception as e:
        return log_test("Approve Risks", False, f"Exception: {str(e)}")


def test_7_re_analyze():
    """Test 7: Re-analyze template with additional context"""
    global session_token, template_id
    
    if not session_token:
        return log_test("Re-analyze Template", False, "No session token available")
    
    if not template_id:
        return log_test("Re-analyze Template", False, "No template_id available")
    
    try:
        response = requests.post(
            f"{BASE_URL}/social-learning/template/{template_id}/re-analyze",
            headers={"Authorization": f"Bearer {session_token}"},
            json={
                "additional_context": "Focus on financial impact for small businesses in India",
                "focus_area": "both"
            },
            timeout=90  # 90 second timeout as specified
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Verify updated factors and risks
            if "learnings_mydezider" in data and "factors" in data["learnings_mydezider"]:
                factors = data["learnings_mydezider"]["factors"]
                if not isinstance(factors, list):
                    return log_test("Re-analyze Template", False, "Updated factors is not an array")
            else:
                return log_test("Re-analyze Template", False, "Missing updated factors in response")
            
            if "learnings_solution_finder" in data and "risks" in data["learnings_solution_finder"]:
                risks = data["learnings_solution_finder"]["risks"]
                if not isinstance(risks, list):
                    return log_test("Re-analyze Template", False, "Updated risks is not an array")
            else:
                return log_test("Re-analyze Template", False, "Missing updated risks in response")
            
            return log_test(
                "Re-analyze Template",
                True,
                f"Re-analyzed with updated factors: {len(factors)}, risks: {len(risks)}"
            )
        else:
            return log_test("Re-analyze Template", False, f"Status: {response.status_code}, Response: {response.text[:500]}")
    
    except Exception as e:
        return log_test("Re-analyze Template", False, f"Exception: {str(e)}")


def test_8_templates_for_decision():
    """Test 8: Get 3-tier templates for decision (CRITICAL)"""
    global session_token, template_id
    
    if not session_token:
        return log_test("3-Tier Decision Endpoint", False, "No session token available")
    
    try:
        response = requests.get(
            f"{BASE_URL}/social-learning/templates-for-decision?include_personal=true",
            headers={"Authorization": f"Bearer {session_token}"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # CRITICAL: Verify 3-tier structure
            required_keys = ["tier_1_personal", "tier_2_authorized", "tier_3_ai_derived", "total"]
            missing_keys = [k for k in required_keys if k not in data]
            
            if missing_keys:
                return log_test(
                    "3-Tier Decision Endpoint",
                    False,
                    f"CRITICAL FAILURE: Missing required keys: {missing_keys}. Response keys: {list(data.keys())}"
                )
            
            # Verify tier_1_personal is an array
            if not isinstance(data["tier_1_personal"], list):
                return log_test("3-Tier Decision Endpoint", False, "tier_1_personal is not an array")
            
            # Verify tier_2_authorized is an array
            if not isinstance(data["tier_2_authorized"], list):
                return log_test("3-Tier Decision Endpoint", False, "tier_2_authorized is not an array")
            
            # Verify tier_3_ai_derived is an array
            if not isinstance(data["tier_3_ai_derived"], list):
                return log_test("3-Tier Decision Endpoint", False, "tier_3_ai_derived is not an array")
            
            # Verify total is an integer
            if not isinstance(data["total"], int):
                return log_test("3-Tier Decision Endpoint", False, "total is not an integer")
            
            # Verify tier_1_personal contains the uploaded template with factors
            if len(data["tier_1_personal"]) > 0:
                template = data["tier_1_personal"][0]
                if "factors" not in template:
                    return log_test("3-Tier Decision Endpoint", False, f"tier_1_personal template missing factors. Keys: {list(template.keys())}")
                
                factors = template["factors"]
                if not isinstance(factors, list):
                    return log_test("3-Tier Decision Endpoint", False, "tier_1_personal template factors is not an array")
            else:
                return log_test("3-Tier Decision Endpoint", False, f"tier_1_personal is empty. Total: {data['total']}")
            
            return log_test(
                "3-Tier Decision Endpoint",
                True,
                f"3-tier structure verified: tier_1={len(data['tier_1_personal'])}, tier_2={len(data['tier_2_authorized'])}, tier_3={len(data['tier_3_ai_derived'])}, total={data['total']}"
            )
        else:
            return log_test("3-Tier Decision Endpoint", False, f"Status: {response.status_code}, Response: {response.text[:500]}")
    
    except Exception as e:
        return log_test("3-Tier Decision Endpoint", False, f"Exception: {str(e)}")


def test_9_templates_for_solution_finder():
    """Test 9: Get 3-tier templates for solution finder (CRITICAL)"""
    global session_token
    
    if not session_token:
        return log_test("3-Tier Solution Finder Endpoint", False, "No session token available")
    
    try:
        response = requests.get(
            f"{BASE_URL}/social-learning/templates-for-solution-finder?include_personal=true",
            headers={"Authorization": f"Bearer {session_token}"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # CRITICAL: Verify 3-tier structure
            required_keys = ["tier_1_personal", "tier_2_authorized", "tier_3_ai_derived", "total"]
            missing_keys = [k for k in required_keys if k not in data]
            
            if missing_keys:
                return log_test(
                    "3-Tier Solution Finder Endpoint",
                    False,
                    f"CRITICAL FAILURE: Missing required keys: {missing_keys}. Response keys: {list(data.keys())}"
                )
            
            # Verify tier_1_personal is an array
            if not isinstance(data["tier_1_personal"], list):
                return log_test("3-Tier Solution Finder Endpoint", False, "tier_1_personal is not an array")
            
            # Verify tier_2_authorized is an array
            if not isinstance(data["tier_2_authorized"], list):
                return log_test("3-Tier Solution Finder Endpoint", False, "tier_2_authorized is not an array")
            
            # Verify tier_3_ai_derived is an array
            if not isinstance(data["tier_3_ai_derived"], list):
                return log_test("3-Tier Solution Finder Endpoint", False, "tier_3_ai_derived is not an array")
            
            # Verify total is an integer
            if not isinstance(data["total"], int):
                return log_test("3-Tier Solution Finder Endpoint", False, "total is not an integer")
            
            # Verify tier_1_personal contains risks
            if len(data["tier_1_personal"]) > 0:
                template = data["tier_1_personal"][0]
                if "risks" not in template:
                    return log_test("3-Tier Solution Finder Endpoint", False, f"tier_1_personal template missing risks. Keys: {list(template.keys())}")
                
                risks = template["risks"]
                if not isinstance(risks, list):
                    return log_test("3-Tier Solution Finder Endpoint", False, "tier_1_personal template risks is not an array")
            else:
                return log_test("3-Tier Solution Finder Endpoint", False, f"tier_1_personal is empty. Total: {data['total']}")
            
            return log_test(
                "3-Tier Solution Finder Endpoint",
                True,
                f"3-tier structure verified: tier_1={len(data['tier_1_personal'])}, tier_2={len(data['tier_2_authorized'])}, tier_3={len(data['tier_3_ai_derived'])}, total={data['total']}"
            )
        else:
            return log_test("3-Tier Solution Finder Endpoint", False, f"Status: {response.status_code}, Response: {response.text[:500]}")
    
    except Exception as e:
        return log_test("3-Tier Solution Finder Endpoint", False, f"Exception: {str(e)}")


def run_all_tests():
    """Run all tests in sequence"""
    print("\n" + "="*80)
    print("3-TIER SOCIAL LEARNING INTEGRATION TESTING")
    print("Backend URL:", BASE_URL)
    print("="*80)
    
    # Run tests in order
    test_1_register_user()
    test_2_login_user()
    test_3_seed_hos_data()
    test_4_upload_news()
    test_5_approve_factors()
    test_6_approve_risks()
    test_7_re_analyze()
    test_8_templates_for_decision()
    test_9_templates_for_solution_finder()
    
    # Print summary
    print_summary()


if __name__ == "__main__":
    run_all_tests()
