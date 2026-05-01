"""
Backend API Testing for Pros & Cons and SWOT Analysis Modules
Tests all CRUD operations and convert-to-decision functionality
"""

import requests
import json
import time
from datetime import datetime

# Backend URL from frontend/.env
BASE_URL = "https://dezider-core.preview.emergentagent.com/api"

# Test results tracking
test_results = []

def log_test(test_name, passed, details=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
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
    print(f"TEST SUMMARY: {passed}/{total} tests passed ({failed} failed)")
    print("="*80)
    
    if failed > 0:
        print("\nFailed Tests:")
        for r in test_results:
            if not r["passed"]:
                print(f"  ❌ {r['test']}: {r['details']}")
    print()

# ============================================================================
# AUTHENTICATION SETUP
# ============================================================================

def register_user():
    """Register a new test user"""
    timestamp = int(time.time())
    email = f"proscons_swot_test_{timestamp}@example.com"
    password = "TestPass123!"
    name = f"Test User {timestamp}"
    phone = f"+91987654{timestamp % 10000:04d}"
    
    response = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "email": email,
            "password": password,
            "name": name,
            "phone": phone
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        log_test("User Registration", True, f"Registered {email}")
        return data.get("session_token"), email
    else:
        log_test("User Registration", False, f"Status: {response.status_code}, Response: {response.text}")
        return None, None

def login_user(email, password):
    """Login with credentials"""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password}
    )
    
    if response.status_code == 200:
        data = response.json()
        log_test("User Login", True, f"Logged in as {email}")
        return data.get("session_token")
    else:
        log_test("User Login", False, f"Status: {response.status_code}, Response: {response.text}")
        return None

# ============================================================================
# PROS & CONS MODULE TESTS
# ============================================================================

def test_pros_cons_create(token):
    """Test: Create Pros & Cons analysis"""
    response = requests.post(
        f"{BASE_URL}/pros-cons",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Should I accept the job offer at TechCorp?",
            "context": "Received a job offer from TechCorp as Senior Software Engineer. Need to decide whether to accept or stay at current company.",
            "life_area": "career",
            "decision_type": "need"
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        if "id" in data and "message" in data:
            log_test("Pros & Cons - Create", True, f"Created analysis with ID: {data['id']}")
            return data["id"]
        else:
            log_test("Pros & Cons - Create", False, f"Missing fields in response: {data}")
            return None
    else:
        log_test("Pros & Cons - Create", False, f"Status: {response.status_code}, Response: {response.text}")
        return None

def test_pros_cons_list(token):
    """Test: List all Pros & Cons analyses"""
    response = requests.get(
        f"{BASE_URL}/pros-cons",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        data = response.json()
        if isinstance(data, list):
            log_test("Pros & Cons - List", True, f"Retrieved {len(data)} analyses")
            return True
        else:
            log_test("Pros & Cons - List", False, f"Expected list, got: {type(data)}")
            return False
    else:
        log_test("Pros & Cons - List", False, f"Status: {response.status_code}, Response: {response.text}")
        return False

def test_pros_cons_get(token, analysis_id):
    """Test: Get specific Pros & Cons analysis"""
    response = requests.get(
        f"{BASE_URL}/pros-cons/{analysis_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        data = response.json()
        required_fields = ["id", "title", "context", "pros", "cons", "converted_decision_id"]
        missing = [f for f in required_fields if f not in data]
        if not missing:
            log_test("Pros & Cons - Get", True, f"Retrieved analysis: {data['title']}")
            return True
        else:
            log_test("Pros & Cons - Get", False, f"Missing fields: {missing}")
            return False
    else:
        log_test("Pros & Cons - Get", False, f"Status: {response.status_code}, Response: {response.text}")
        return False

def test_pros_cons_update(token, analysis_id):
    """Test: Update Pros & Cons with items"""
    response = requests.put(
        f"{BASE_URL}/pros-cons/{analysis_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "pros": [
                {
                    "id": "pro1",
                    "text": "Higher Salary",
                    "description": "30% salary increase compared to current role",
                    "importance": 9
                },
                {
                    "id": "pro2",
                    "text": "Better Work-Life Balance",
                    "description": "Flexible work hours and remote work options",
                    "importance": 8
                },
                {
                    "id": "pro3",
                    "text": "Career Growth Opportunities",
                    "description": "Clear path to leadership roles",
                    "importance": 7
                }
            ],
            "cons": [
                {
                    "id": "con1",
                    "text": "Longer Commute",
                    "description": "45 minutes each way vs current 15 minutes",
                    "importance": 6
                },
                {
                    "id": "con2",
                    "text": "Unknown Company Culture",
                    "description": "Risk of not fitting in with new team",
                    "importance": 7
                }
            ]
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        if "message" in data:
            log_test("Pros & Cons - Update", True, "Added 3 pros and 2 cons")
            return True
        else:
            log_test("Pros & Cons - Update", False, f"Unexpected response: {data}")
            return False
    else:
        log_test("Pros & Cons - Update", False, f"Status: {response.status_code}, Response: {response.text}")
        return False

def test_pros_cons_convert_empty(token, analysis_id):
    """Test: Convert should fail with no items"""
    # Create a new empty analysis
    response = requests.post(
        f"{BASE_URL}/pros-cons",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Empty Analysis",
            "context": "Test empty conversion"
        }
    )
    
    if response.status_code == 200:
        empty_id = response.json()["id"]
        
        # Try to convert empty analysis
        convert_response = requests.post(
            f"{BASE_URL}/pros-cons/{empty_id}/convert-to-decision",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if convert_response.status_code == 400:
            log_test("Pros & Cons - Convert Empty (Validation)", True, "Correctly rejected empty analysis")
            return True
        else:
            log_test("Pros & Cons - Convert Empty (Validation)", False, f"Expected 400, got {convert_response.status_code}")
            return False
    else:
        log_test("Pros & Cons - Convert Empty (Validation)", False, "Failed to create empty analysis")
        return False

def test_pros_cons_convert(token, analysis_id):
    """Test: Convert Pros & Cons to PRR Decision with AI"""
    print("\n⏳ Converting Pros & Cons to Decision (may take 5-10 seconds for LLM call)...")
    
    response = requests.post(
        f"{BASE_URL}/pros-cons/{analysis_id}/convert-to-decision",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30  # 30 second timeout for LLM call
    )
    
    if response.status_code == 200:
        data = response.json()
        required_fields = ["decision_id", "factors_count", "message"]
        missing = [f for f in required_fields if f not in data]
        
        if not missing:
            expected_factors = 5  # 3 pros + 2 cons
            if data["factors_count"] == expected_factors:
                log_test("Pros & Cons - Convert to Decision", True, 
                        f"Created decision {data['decision_id']} with {data['factors_count']} factors")
                return data["decision_id"]
            else:
                log_test("Pros & Cons - Convert to Decision", False, 
                        f"Expected {expected_factors} factors, got {data['factors_count']}")
                return None
        else:
            log_test("Pros & Cons - Convert to Decision", False, f"Missing fields: {missing}")
            return None
    else:
        log_test("Pros & Cons - Convert to Decision", False, 
                f"Status: {response.status_code}, Response: {response.text}")
        return None

def test_pros_cons_verify_conversion(token, analysis_id, decision_id):
    """Test: Verify conversion updated analysis and created decision"""
    # Check analysis has converted_decision_id
    analysis_response = requests.get(
        f"{BASE_URL}/pros-cons/{analysis_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if analysis_response.status_code == 200:
        analysis = analysis_response.json()
        if analysis.get("converted_decision_id") == decision_id:
            log_test("Pros & Cons - Verify Conversion Link", True, 
                    f"Analysis correctly linked to decision {decision_id}")
        else:
            log_test("Pros & Cons - Verify Conversion Link", False, 
                    f"Expected decision_id {decision_id}, got {analysis.get('converted_decision_id')}")
            return False
    else:
        log_test("Pros & Cons - Verify Conversion Link", False, "Failed to retrieve analysis")
        return False
    
    # Check decision exists and has correct factors
    decision_response = requests.get(
        f"{BASE_URL}/decisions/{decision_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if decision_response.status_code == 200:
        decision = decision_response.json()
        factors = decision.get("factors", [])
        
        # Verify factor count
        if len(factors) != 5:
            log_test("Pros & Cons - Verify Decision Factors", False, 
                    f"Expected 5 factors, got {len(factors)}")
            return False
        
        # Verify pros are as-is and cons are prefixed with "NOT "
        pros_count = sum(1 for f in factors if not f["name"].startswith("NOT "))
        cons_count = sum(1 for f in factors if f["name"].startswith("NOT "))
        
        if pros_count == 3 and cons_count == 2:
            log_test("Pros & Cons - Verify Decision Factors", True, 
                    f"Decision has 3 pros (as-is) and 2 cons (prefixed with NOT)")
        else:
            log_test("Pros & Cons - Verify Decision Factors", False, 
                    f"Expected 3 pros and 2 cons, got {pros_count} pros and {cons_count} cons")
            return False
        
        # Verify source metadata
        if decision.get("source_module") == "pros_cons" and decision.get("source_id") == analysis_id:
            log_test("Pros & Cons - Verify Decision Metadata", True, 
                    "Decision correctly linked to source analysis")
        else:
            log_test("Pros & Cons - Verify Decision Metadata", False, 
                    f"Source metadata incorrect: {decision.get('source_module')}, {decision.get('source_id')}")
            return False
        
        return True
    else:
        log_test("Pros & Cons - Verify Decision Factors", False, 
                f"Failed to retrieve decision: {decision_response.status_code}")
        return False

def test_pros_cons_delete(token, analysis_id):
    """Test: Delete Pros & Cons analysis"""
    response = requests.delete(
        f"{BASE_URL}/pros-cons/{analysis_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        data = response.json()
        if "message" in data:
            log_test("Pros & Cons - Delete", True, f"Deleted analysis {analysis_id}")
            return True
        else:
            log_test("Pros & Cons - Delete", False, f"Unexpected response: {data}")
            return False
    else:
        log_test("Pros & Cons - Delete", False, f"Status: {response.status_code}, Response: {response.text}")
        return False

# ============================================================================
# SWOT ANALYSIS MODULE TESTS
# ============================================================================

def test_swot_create(token):
    """Test: Create SWOT analysis"""
    response = requests.post(
        f"{BASE_URL}/swot",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Should I start a consulting business?",
            "context": "Considering leaving corporate job to start independent consulting practice in software architecture.",
            "life_area": "career",
            "decision_type": "aspiration"
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        if "id" in data and "message" in data:
            log_test("SWOT - Create", True, f"Created analysis with ID: {data['id']}")
            return data["id"]
        else:
            log_test("SWOT - Create", False, f"Missing fields in response: {data}")
            return None
    else:
        log_test("SWOT - Create", False, f"Status: {response.status_code}, Response: {response.text}")
        return None

def test_swot_list(token):
    """Test: List all SWOT analyses"""
    response = requests.get(
        f"{BASE_URL}/swot",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        data = response.json()
        if isinstance(data, list):
            log_test("SWOT - List", True, f"Retrieved {len(data)} analyses")
            return True
        else:
            log_test("SWOT - List", False, f"Expected list, got: {type(data)}")
            return False
    else:
        log_test("SWOT - List", False, f"Status: {response.status_code}, Response: {response.text}")
        return False

def test_swot_get(token, analysis_id):
    """Test: Get specific SWOT analysis"""
    response = requests.get(
        f"{BASE_URL}/swot/{analysis_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        data = response.json()
        required_fields = ["id", "title", "context", "strengths", "weaknesses", 
                          "opportunities", "threats", "converted_decision_id"]
        missing = [f for f in required_fields if f not in data]
        if not missing:
            log_test("SWOT - Get", True, f"Retrieved analysis: {data['title']}")
            return True
        else:
            log_test("SWOT - Get", False, f"Missing fields: {missing}")
            return False
    else:
        log_test("SWOT - Get", False, f"Status: {response.status_code}, Response: {response.text}")
        return False

def test_swot_update(token, analysis_id):
    """Test: Update SWOT with all 4 quadrants"""
    response = requests.put(
        f"{BASE_URL}/swot/{analysis_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "strengths": [
                {
                    "id": "s1",
                    "text": "15 years of industry experience",
                    "description": "Deep expertise in software architecture",
                    "impact": 9
                },
                {
                    "id": "s2",
                    "text": "Strong professional network",
                    "description": "Connections with potential clients",
                    "impact": 8
                }
            ],
            "weaknesses": [
                {
                    "id": "w1",
                    "text": "No business management experience",
                    "description": "Never run a business before",
                    "impact": 7
                },
                {
                    "id": "w2",
                    "text": "Limited savings buffer",
                    "description": "Only 6 months of runway",
                    "impact": 8
                }
            ],
            "opportunities": [
                {
                    "id": "o1",
                    "text": "Growing demand for cloud architecture",
                    "description": "Market expanding rapidly",
                    "impact": 9
                },
                {
                    "id": "o2",
                    "text": "Remote work normalization",
                    "description": "Can work with clients globally",
                    "impact": 7
                }
            ],
            "threats": [
                {
                    "id": "t1",
                    "text": "Economic recession risk",
                    "description": "Companies cutting consulting budgets",
                    "impact": 8
                },
                {
                    "id": "t2",
                    "text": "Established competitors",
                    "description": "Big consulting firms dominate market",
                    "impact": 6
                }
            ]
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        if "message" in data:
            log_test("SWOT - Update", True, "Added 2 items to each quadrant (S:2 W:2 O:2 T:2)")
            return True
        else:
            log_test("SWOT - Update", False, f"Unexpected response: {data}")
            return False
    else:
        log_test("SWOT - Update", False, f"Status: {response.status_code}, Response: {response.text}")
        return False

def test_swot_convert_empty(token):
    """Test: Convert should fail with no items"""
    # Create a new empty analysis
    response = requests.post(
        f"{BASE_URL}/swot",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Empty SWOT",
            "context": "Test empty conversion"
        }
    )
    
    if response.status_code == 200:
        empty_id = response.json()["id"]
        
        # Try to convert empty analysis
        convert_response = requests.post(
            f"{BASE_URL}/swot/{empty_id}/convert-to-decision",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if convert_response.status_code == 400:
            log_test("SWOT - Convert Empty (Validation)", True, "Correctly rejected empty analysis")
            return True
        else:
            log_test("SWOT - Convert Empty (Validation)", False, f"Expected 400, got {convert_response.status_code}")
            return False
    else:
        log_test("SWOT - Convert Empty (Validation)", False, "Failed to create empty analysis")
        return False

def test_swot_convert(token, analysis_id):
    """Test: Convert SWOT to PRR Decision with AI"""
    print("\n⏳ Converting SWOT to Decision (may take 5-10 seconds for LLM call)...")
    
    response = requests.post(
        f"{BASE_URL}/swot/{analysis_id}/convert-to-decision",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30  # 30 second timeout for LLM call
    )
    
    if response.status_code == 200:
        data = response.json()
        required_fields = ["decision_id", "factors_count", "message"]
        missing = [f for f in required_fields if f not in data]
        
        if not missing:
            expected_factors = 8  # 2S + 2W + 2O + 2T
            if data["factors_count"] == expected_factors:
                log_test("SWOT - Convert to Decision", True, 
                        f"Created decision {data['decision_id']} with {data['factors_count']} factors")
                return data["decision_id"]
            else:
                log_test("SWOT - Convert to Decision", False, 
                        f"Expected {expected_factors} factors, got {data['factors_count']}")
                return None
        else:
            log_test("SWOT - Convert to Decision", False, f"Missing fields: {missing}")
            return None
    else:
        log_test("SWOT - Convert to Decision", False, 
                f"Status: {response.status_code}, Response: {response.text}")
        return None

def test_swot_verify_conversion(token, analysis_id, decision_id):
    """Test: Verify SWOT conversion with proper factor transformation"""
    # Check analysis has converted_decision_id
    analysis_response = requests.get(
        f"{BASE_URL}/swot/{analysis_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if analysis_response.status_code == 200:
        analysis = analysis_response.json()
        if analysis.get("converted_decision_id") == decision_id:
            log_test("SWOT - Verify Conversion Link", True, 
                    f"Analysis correctly linked to decision {decision_id}")
        else:
            log_test("SWOT - Verify Conversion Link", False, 
                    f"Expected decision_id {decision_id}, got {analysis.get('converted_decision_id')}")
            return False
    else:
        log_test("SWOT - Verify Conversion Link", False, "Failed to retrieve analysis")
        return False
    
    # Check decision exists and has correct factors
    decision_response = requests.get(
        f"{BASE_URL}/decisions/{decision_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if decision_response.status_code == 200:
        decision = decision_response.json()
        factors = decision.get("factors", [])
        
        # Verify factor count
        if len(factors) != 8:
            log_test("SWOT - Verify Decision Factors", False, 
                    f"Expected 8 factors, got {len(factors)}")
            return False
        
        # Verify S/O are as-is and W/T are prefixed with "NOT "
        positive_count = sum(1 for f in factors if not f["name"].startswith("NOT "))
        negative_count = sum(1 for f in factors if f["name"].startswith("NOT "))
        
        if positive_count == 4 and negative_count == 4:
            log_test("SWOT - Verify Decision Factors", True, 
                    f"Decision has 4 positive factors (S+O) and 4 negative factors (W+T prefixed with NOT)")
        else:
            log_test("SWOT - Verify Decision Factors", False, 
                    f"Expected 4 positive and 4 negative, got {positive_count} positive and {negative_count} negative")
            return False
        
        # Verify source metadata
        if decision.get("source_module") == "swot" and decision.get("source_id") == analysis_id:
            log_test("SWOT - Verify Decision Metadata", True, 
                    "Decision correctly linked to source analysis")
        else:
            log_test("SWOT - Verify Decision Metadata", False, 
                    f"Source metadata incorrect: {decision.get('source_module')}, {decision.get('source_id')}")
            return False
        
        return True
    else:
        log_test("SWOT - Verify Decision Factors", False, 
                f"Failed to retrieve decision: {decision_response.status_code}")
        return False

def test_swot_delete(token, analysis_id):
    """Test: Delete SWOT analysis"""
    response = requests.delete(
        f"{BASE_URL}/swot/{analysis_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code == 200:
        data = response.json()
        if "message" in data:
            log_test("SWOT - Delete", True, f"Deleted analysis {analysis_id}")
            return True
        else:
            log_test("SWOT - Delete", False, f"Unexpected response: {data}")
            return False
    else:
        log_test("SWOT - Delete", False, f"Status: {response.status_code}, Response: {response.text}")
        return False

# ============================================================================
# MAIN TEST EXECUTION
# ============================================================================

def main():
    print("="*80)
    print("PROS & CONS + SWOT ANALYSIS MODULE TESTING")
    print(f"Backend URL: {BASE_URL}")
    print("="*80)
    print()
    
    # Step 1: Register and authenticate
    print("STEP 1: Authentication Setup")
    print("-" * 80)
    token, email = register_user()
    if not token:
        print("❌ Failed to register user. Aborting tests.")
        return
    
    print()
    
    # Step 2: Test Pros & Cons Module
    print("STEP 2: Pros & Cons Module Tests")
    print("-" * 80)
    
    pc_id = test_pros_cons_create(token)
    if pc_id:
        test_pros_cons_list(token)
        test_pros_cons_get(token, pc_id)
        test_pros_cons_update(token, pc_id)
        test_pros_cons_convert_empty(token, pc_id)
        
        pc_decision_id = test_pros_cons_convert(token, pc_id)
        if pc_decision_id:
            test_pros_cons_verify_conversion(token, pc_id, pc_decision_id)
        
        # Don't delete yet - keep for verification
    
    print()
    
    # Step 3: Test SWOT Analysis Module
    print("STEP 3: SWOT Analysis Module Tests")
    print("-" * 80)
    
    swot_id = test_swot_create(token)
    if swot_id:
        test_swot_list(token)
        test_swot_get(token, swot_id)
        test_swot_update(token, swot_id)
        test_swot_convert_empty(token)
        
        swot_decision_id = test_swot_convert(token, swot_id)
        if swot_decision_id:
            test_swot_verify_conversion(token, swot_id, swot_decision_id)
        
        # Don't delete yet - keep for verification
    
    print()
    
    # Step 4: Verify decisions list includes both converted decisions
    print("STEP 4: Verify Converted Decisions in Decision List")
    print("-" * 80)
    
    decisions_response = requests.get(
        f"{BASE_URL}/decisions",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if decisions_response.status_code == 200:
        decisions = decisions_response.json()
        pc_found = any(d.get("source_module") == "pros_cons" for d in decisions)
        swot_found = any(d.get("source_module") == "swot" for d in decisions)
        
        if pc_found and swot_found:
            log_test("Verify Decisions List", True, 
                    "Both converted decisions appear in decisions list")
        else:
            log_test("Verify Decisions List", False, 
                    f"Pros&Cons found: {pc_found}, SWOT found: {swot_found}")
    else:
        log_test("Verify Decisions List", False, 
                f"Failed to retrieve decisions: {decisions_response.status_code}")
    
    print()
    
    # Print summary
    print_summary()

if __name__ == "__main__":
    main()
