#!/usr/bin/env python3
"""
Backend Testing Script for PRR Decisions API - Sub-Factor Support
Testing Focus: End-to-end sub-factor functionality as specified in review request
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, Any, List

# Use the production URL from frontend/.env
BACKEND_URL = "https://goals-feels-tracker.preview.emergentagent.com/api"

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
    
    def log(self, test_name: str, success: bool, details: str = ""):
        status = "✅ PASSED" if success else "❌ FAILED"
        self.results.append(f"{status}: {test_name}")
        if details:
            self.results.append(f"   {details}")
        if success:
            self.passed += 1
        else:
            self.failed += 1
        print(f"{status}: {test_name}")
        if details:
            print(f"   {details}")

def register_user(email: str, password: str, name: str) -> Dict[str, Any]:
    """Register a new user and return user data with session token"""
    data = {
        "email": email,
        "password": password,
        "name": name
    }
    
    response = requests.post(f"{BACKEND_URL}/auth/register", json=data)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Registration failed: {response.status_code} {response.text}")

def login_user(email: str, password: str) -> str:
    """Login user and return session token"""
    data = {
        "email": email,
        "password": password
    }
    
    response = requests.post(f"{BACKEND_URL}/auth/login", json=data)
    if response.status_code == 200:
        return response.json()["session_token"]
    else:
        raise Exception(f"Login failed: {response.status_code} {response.text}")

def test_subfactor_support_end_to_end(results: TestResults):
    """Test complete sub-factor support workflow as specified in review request"""
    print("\n=== TESTING PRR DECISIONS API - SUB-FACTOR SUPPORT ===")
    
    try:
        # Generate unique timestamp for user
        timestamp = str(int(time.time()))
        
        # Step 1: Create a new user and login to get auth token
        user_email = f"subfactor.tester.{timestamp}@careerpath.com"
        user_password = "securepass123"
        user_name = f"SubFactor Tester {timestamp}"
        
        user_data = register_user(user_email, user_password, user_name)
        auth_token = user_data["session_token"]
        
        results.log("User Registration and Auth Token", True, f"Created user: {user_name}, Token: {auth_token[:20]}...")
        
        # Verify login also works
        login_token = login_user(user_email, user_password)
        results.log("User Login Verification", True, f"Login token: {login_token[:20]}...")
        
        # Use the login token for subsequent requests
        headers = {"Authorization": f"Bearer {login_token}"}
        
        # Step 2: Create a decision
        decision_data = {
            "title": "Job Offer Evaluation - Sub-Factor Test",
            "context": "Evaluating multiple job offers with detailed compensation breakdown and other factors"
        }
        
        response = requests.post(f"{BACKEND_URL}/decisions", json=decision_data, headers=headers)
        
        if response.status_code == 200:
            decision_id = response.json()["id"]
            results.log("Decision Creation", True, f"Decision ID: {decision_id}")
        else:
            results.log("Decision Creation", False, f"HTTP {response.status_code}: {response.text}")
            return
        
        # Step 3: Update the decision with factors including sub-factors
        # Parent factor "Compensation" with sub-factors "Base Salary" and "Bonus"
        # Leaf factors "Location" and "Growth"
        factors_data = [
            # Parent factor "Compensation"
            {
                "id": "f_comp",
                "name": "Compensation",
                "category": "primary",
                "rating": 50,
                "order": 0,
                "parent_id": None,  # Top-level factor
                "weight": None
            },
            # Sub-factor "Base Salary" under Compensation
            {
                "id": "sf_base",
                "name": "Base Salary",
                "category": "primary",  # Inherits from parent
                "rating": 0,  # Sub-factors don't have individual ratings
                "order": 0,
                "parent_id": "f_comp",
                "weight": 60.0,  # 60% of parent factor
                "expected_value": 100000,
                "operator": ">=",
                "unit": "USD",
                "data_type": "numeric"
            },
            # Sub-factor "Bonus" under Compensation
            {
                "id": "sf_bonus",
                "name": "Bonus",
                "category": "primary",  # Inherits from parent
                "rating": 0,  # Sub-factors don't have individual ratings
                "order": 1,
                "parent_id": "f_comp",
                "weight": 40.0,  # 40% of parent factor (60% + 40% = 100%)
                "expected_value": 20000,
                "operator": ">=",
                "unit": "USD",
                "data_type": "numeric"
            },
            # Leaf factor "Location"
            {
                "id": "f_loc",
                "name": "Location",
                "category": "secondary",
                "rating": 30,
                "order": 1,
                "parent_id": None,  # Top-level factor
                "weight": None,
                "expected_value": "Bangalore",
                "operator": "contains",
                "data_type": "text"
            },
            # Leaf factor "Growth"
            {
                "id": "f_growth",
                "name": "Growth",
                "category": "primary",
                "rating": 40,
                "order": 2,
                "parent_id": None,  # Top-level factor
                "weight": None
            }
        ]
        
        update_data = {
            "factors": factors_data
        }
        
        response = requests.put(f"{BACKEND_URL}/decisions/{decision_id}", json=update_data, headers=headers)
        
        if response.status_code == 200:
            results.log("Decision Update with Sub-Factors", True, "Added parent factor 'Compensation' with 2 sub-factors + 2 leaf factors")
        else:
            results.log("Decision Update with Sub-Factors", False, f"HTTP {response.status_code}: {response.text}")
            return
        
        # Step 4: Add 2 options: "Company A" and "Company B"
        options_data = [
            {
                "id": "opt_company_a",
                "name": "Company A",
                "assessments": [],
                "worth_percentage": 0.0
            },
            {
                "id": "opt_company_b", 
                "name": "Company B",
                "assessments": [],
                "worth_percentage": 0.0
            }
        ]
        
        update_data = {
            "factors": factors_data,  # Keep existing factors
            "options": options_data
        }
        
        response = requests.put(f"{BACKEND_URL}/decisions/{decision_id}", json=update_data, headers=headers)
        
        if response.status_code == 200:
            results.log("Add Decision Options", True, "Added Company A and Company B options")
        else:
            results.log("Add Decision Options", False, f"HTTP {response.status_code}: {response.text}")
            return
        
        # Step 5: Add sub-factor assessments for Company A
        # sf_base: 75% (H), sf_bonus: 25% (L), f_growth: 50% (M), f_loc: 100% (auto)
        company_a_assessments = [
            # Sub-factor assessments
            {
                "factor_id": "sf_base",
                "percentage": 75,
                "assessment_mode": "H",
                "actual_value": 120000,  # Exceeds expected 100k
                "unit_value": "120000 USD"
            },
            {
                "factor_id": "sf_bonus",
                "percentage": 25,
                "assessment_mode": "L", 
                "actual_value": 5000,  # Below expected 20k
                "unit_value": "5000 USD"
            },
            # Leaf factor assessments
            {
                "factor_id": "f_growth",
                "percentage": 50,
                "assessment_mode": "M"
            },
            {
                "factor_id": "f_loc",
                "percentage": 100,
                "assessment_mode": "H",  # Auto-calculated as 100% since "Bangalore" contains "Bangalore"
                "actual_value": None,
                "unit_value": "Bangalore, India"
            }
        ]
        
        # Update Company A with assessments
        options_with_assessments = [
            {
                "id": "opt_company_a",
                "name": "Company A",
                "assessments": company_a_assessments,
                "worth_percentage": 0.0  # Will be calculated by backend
            },
            {
                "id": "opt_company_b",
                "name": "Company B", 
                "assessments": [],  # No assessments for Company B yet
                "worth_percentage": 0.0
            }
        ]
        
        update_data = {
            "factors": factors_data,
            "options": options_with_assessments
        }
        
        response = requests.put(f"{BACKEND_URL}/decisions/{decision_id}", json=update_data, headers=headers)
        
        if response.status_code == 200:
            results.log("Add Sub-Factor Assessments", True, "Added assessments for Company A: sf_base=75%, sf_bonus=25%, f_growth=50%, f_loc=100%")
        else:
            results.log("Add Sub-Factor Assessments", False, f"HTTP {response.status_code}: {response.text}")
            return
        
        # Step 6: Verify the data persists correctly via GET
        response = requests.get(f"{BACKEND_URL}/decisions/{decision_id}", headers=headers)
        
        if response.status_code == 200:
            decision_data = response.json()
            results.log("Data Persistence Verification", True, "Successfully retrieved decision data")
            
            # Verify factors structure
            factors = decision_data.get("factors", [])
            
            # Check parent factor
            parent_factor = next((f for f in factors if f["id"] == "f_comp"), None)
            if parent_factor:
                if parent_factor.get("parent_id") is None and parent_factor.get("weight") is None:
                    results.log("Parent Factor Structure", True, f"Compensation factor: parent_id=None, weight=None")
                else:
                    results.log("Parent Factor Structure", False, f"Unexpected parent factor structure: {parent_factor}")
            else:
                results.log("Parent Factor Structure", False, "Parent factor 'f_comp' not found")
            
            # Check sub-factors
            sub_factor_base = next((f for f in factors if f["id"] == "sf_base"), None)
            sub_factor_bonus = next((f for f in factors if f["id"] == "sf_bonus"), None)
            
            if sub_factor_base and sub_factor_bonus:
                base_valid = (sub_factor_base.get("parent_id") == "f_comp" and 
                             sub_factor_base.get("weight") == 60.0 and
                             sub_factor_base.get("expected_value") == 100000 and
                             sub_factor_base.get("operator") == ">=" and
                             sub_factor_base.get("unit") == "USD")
                
                bonus_valid = (sub_factor_bonus.get("parent_id") == "f_comp" and
                              sub_factor_bonus.get("weight") == 40.0 and
                              sub_factor_bonus.get("expected_value") == 20000 and
                              sub_factor_bonus.get("operator") == ">=" and
                              sub_factor_bonus.get("unit") == "USD")
                
                if base_valid and bonus_valid:
                    results.log("Sub-Factor Structure Verification", True, "Both sub-factors have correct parent_id, weight, expected_value, operator, and unit")
                else:
                    results.log("Sub-Factor Structure Verification", False, f"Sub-factor validation failed. Base: {base_valid}, Bonus: {bonus_valid}")
                    results.log("Sub-Factor Details", False, f"Base: {sub_factor_base}")
                    results.log("Sub-Factor Details", False, f"Bonus: {sub_factor_bonus}")
            else:
                results.log("Sub-Factor Structure Verification", False, "Sub-factors not found in response")
            
            # Check leaf factors
            leaf_location = next((f for f in factors if f["id"] == "f_loc"), None)
            leaf_growth = next((f for f in factors if f["id"] == "f_growth"), None)
            
            if leaf_location and leaf_growth:
                loc_valid = (leaf_location.get("parent_id") is None and
                            leaf_location.get("weight") is None and
                            leaf_location.get("expected_value") == "Bangalore" and
                            leaf_location.get("operator") == "contains" and
                            leaf_location.get("data_type") == "text")
                
                growth_valid = (leaf_growth.get("parent_id") is None and
                               leaf_growth.get("weight") is None)
                
                if loc_valid and growth_valid:
                    results.log("Leaf Factor Structure Verification", True, "Leaf factors have correct structure (no parent_id/weight)")
                else:
                    results.log("Leaf Factor Structure Verification", False, f"Leaf factor validation failed. Location: {loc_valid}, Growth: {growth_valid}")
            else:
                results.log("Leaf Factor Structure Verification", False, "Leaf factors not found in response")
            
            # Verify options and assessments
            options = decision_data.get("options", [])
            company_a = next((o for o in options if o["id"] == "opt_company_a"), None)
            
            if company_a:
                assessments = company_a.get("assessments", [])
                
                # Check sub-factor assessments
                base_assessment = next((a for a in assessments if a["factor_id"] == "sf_base"), None)
                bonus_assessment = next((a for a in assessments if a["factor_id"] == "sf_bonus"), None)
                growth_assessment = next((a for a in assessments if a["factor_id"] == "f_growth"), None)
                loc_assessment = next((a for a in assessments if a["factor_id"] == "f_loc"), None)
                
                assessment_checks = []
                if base_assessment and base_assessment.get("percentage") == 75:
                    assessment_checks.append("sf_base: 75% ✓")
                else:
                    assessment_checks.append(f"sf_base: Expected 75%, got {base_assessment.get('percentage') if base_assessment else 'None'} ✗")
                
                if bonus_assessment and bonus_assessment.get("percentage") == 25:
                    assessment_checks.append("sf_bonus: 25% ✓")
                else:
                    assessment_checks.append(f"sf_bonus: Expected 25%, got {bonus_assessment.get('percentage') if bonus_assessment else 'None'} ✗")
                
                if growth_assessment and growth_assessment.get("percentage") == 50:
                    assessment_checks.append("f_growth: 50% ✓")
                else:
                    assessment_checks.append(f"f_growth: Expected 50%, got {growth_assessment.get('percentage') if growth_assessment else 'None'} ✗")
                
                if loc_assessment and loc_assessment.get("percentage") == 100:
                    assessment_checks.append("f_loc: 100% ✓")
                else:
                    assessment_checks.append(f"f_loc: Expected 100%, got {loc_assessment.get('percentage') if loc_assessment else 'None'} ✗")
                
                all_assessments_correct = all("✓" in check for check in assessment_checks)
                
                if all_assessments_correct:
                    results.log("Assessment Persistence Verification", True, "All assessments persisted correctly: " + ", ".join(assessment_checks))
                else:
                    results.log("Assessment Persistence Verification", False, "Assessment issues: " + ", ".join(assessment_checks))
            else:
                results.log("Assessment Persistence Verification", False, "Company A option not found in response")
            
            # Step 7: Verify parent_id and weight fields are stored and returned correctly
            # This is already covered above, but let's do a final comprehensive check
            subfactor_fields_check = []
            
            for factor in factors:
                if factor["id"] in ["sf_base", "sf_bonus"]:
                    has_parent_id = "parent_id" in factor and factor["parent_id"] == "f_comp"
                    has_weight = "weight" in factor and isinstance(factor["weight"], (int, float))
                    
                    if has_parent_id and has_weight:
                        subfactor_fields_check.append(f"{factor['name']}: parent_id='{factor['parent_id']}', weight={factor['weight']} ✓")
                    else:
                        subfactor_fields_check.append(f"{factor['name']}: parent_id={factor.get('parent_id')}, weight={factor.get('weight')} ✗")
            
            if len(subfactor_fields_check) == 2 and all("✓" in check for check in subfactor_fields_check):
                results.log("Parent ID and Weight Fields Verification", True, "Sub-factors correctly store and return parent_id and weight: " + ", ".join(subfactor_fields_check))
            else:
                results.log("Parent ID and Weight Fields Verification", False, "Sub-factor field issues: " + ", ".join(subfactor_fields_check))
            
        else:
            results.log("Data Persistence Verification", False, f"HTTP {response.status_code}: {response.text}")
            return
        
        # Additional verification: Test that the decision can be retrieved and all sub-factor data is intact
        response = requests.get(f"{BACKEND_URL}/decisions", headers=headers)
        
        if response.status_code == 200:
            decisions_list = response.json()
            test_decision = next((d for d in decisions_list if d["id"] == decision_id), None)
            
            if test_decision:
                results.log("Decision List Retrieval", True, f"Decision found in list with title: '{test_decision['title']}'")
                
                # Quick check that factors are present in list view
                if test_decision.get("factors") and len(test_decision["factors"]) == 5:
                    results.log("Factors in List View", True, "All 5 factors (1 parent + 2 sub + 2 leaf) present in list view")
                else:
                    results.log("Factors in List View", False, f"Expected 5 factors, got {len(test_decision.get('factors', []))}")
            else:
                results.log("Decision List Retrieval", False, "Test decision not found in decisions list")
        else:
            results.log("Decision List Retrieval", False, f"HTTP {response.status_code}: {response.text}")
            
    except Exception as e:
        results.log("Sub-Factor Support Testing", False, f"Exception: {str(e)}")

def main():
    """Run sub-factor support tests"""
    print("🚀 PRR DECISIONS API - SUB-FACTOR SUPPORT TESTING")
    print(f"Testing against: {BACKEND_URL}")
    print(f"Started at: {datetime.now().isoformat()}")
    
    results = TestResults()
    
    # Test sub-factor support end-to-end
    test_subfactor_support_end_to_end(results)
    
    # Print Summary
    print(f"\n{'='*60}")
    print("🏁 SUB-FACTOR SUPPORT TESTING COMPLETE")
    print(f"{'='*60}")
    print(f"✅ PASSED: {results.passed}")
    print(f"❌ FAILED: {results.failed}")
    print(f"📊 TOTAL: {results.passed + results.failed}")
    
    if results.failed > 0:
        print(f"\n❌ FAILED TESTS:")
        for result in results.results:
            if "❌ FAILED" in result:
                print(f"   {result}")
    
    print(f"\n✅ SUCCESSFUL TESTS:")
    for result in results.results:
        if "✅ PASSED" in result:
            print(f"   {result}")
    
    print(f"\nCompleted at: {datetime.now().isoformat()}")
    return results.failed == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)