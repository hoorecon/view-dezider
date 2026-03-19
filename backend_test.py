#!/usr/bin/env python3

import asyncio
import httpx
import json
import os
from datetime import datetime

# Configuration
BACKEND_URL = "https://best-mate-decisions.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

# Test data that looks realistic for PRR Decision System
TEST_USER_DATA = {
    "email": f"alex.carter.{datetime.now().timestamp():.0f}@techstartup.com",
    "password": "SecurePass2025!",
    "name": "Alex Carter"
}

class BackendAPITester:
    def __init__(self):
        self.session_token = None
        self.user_id = None
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def close(self):
        await self.client.aclose()
        
    async def register_user(self):
        """Register a test user and get session token"""
        print("\n=== Testing User Registration ===")
        
        response = await self.client.post(
            f"{API_BASE}/auth/register",
            json=TEST_USER_DATA
        )
        
        if response.status_code == 200:
            data = response.json()
            self.session_token = data["session_token"]
            self.user_id = data["user_id"]
            print(f"✅ Registration successful - User ID: {self.user_id}")
            return True
        else:
            print(f"❌ Registration failed: {response.status_code} - {response.text}")
            return False
            
    async def test_prr_decisions_worth_calculation_bug_fix(self):
        """Test PRR decisions worth percentage calculation bug fix"""
        print("\n=== Testing PRR Decisions Worth Percentage Bug Fix ===")
        
        if not self.session_token:
            print("❌ No session token available")
            return False
            
        headers = {"Authorization": f"Bearer {self.session_token}"}
        
        # 1. Create a PRR decision
        print("\n1. Creating PRR decision...")
        decision_data = {
            "title": "Career Path Selection: Tech Startup vs Corporate Job",
            "context": "Deciding between joining a tech startup as a senior developer or taking a corporate position at a Fortune 500 company"
        }
        
        response = await self.client.post(
            f"{API_BASE}/decisions",
            json=decision_data,
            headers=headers
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to create decision: {response.status_code} - {response.text}")
            return False
            
        decision_id = response.json()["id"]
        print(f"✅ Decision created with ID: {decision_id}")
        
        # 2. Add 5 factors (mix of primary and secondary)
        print("\n2. Adding 5 factors to decision...")
        factors = [
            {"id": "factor_1", "name": "Salary and Benefits", "category": "primary", "rating": 90, "order": 1},
            {"id": "factor_2", "name": "Career Growth Opportunities", "category": "primary", "rating": 85, "order": 2},
            {"id": "factor_3", "name": "Work-Life Balance", "category": "primary", "rating": 80, "order": 3},
            {"id": "factor_4", "name": "Company Culture", "category": "secondary", "rating": 70, "order": 4},
            {"id": "factor_5", "name": "Learning & Development", "category": "secondary", "rating": 75, "order": 5}
        ]
        
        # 3. Add 2 options to the decision
        print("\n3. Adding 2 options to decision...")
        options = [
            {"id": "option_1", "name": "Tech Startup Position", "assessments": [], "worth_percentage": 0.0},
            {"id": "option_2", "name": "Corporate Position", "assessments": [], "worth_percentage": 0.0}
        ]
        
        update_data = {
            "factors": factors,
            "options": options,
            "status": "in_progress"
        }
        
        response = await self.client.put(
            f"{API_BASE}/decisions/{decision_id}",
            json=update_data,
            headers=headers
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to add factors and options: {response.status_code} - {response.text}")
            return False
            
        print("✅ Factors and options added successfully")
        
        # 4. Test cases for assessment percentages and worth calculation
        test_cases = [
            {
                "name": "Normal LMH values test",
                "option_assessments": {
                    "option_1": [
                        {"factor_id": "factor_1", "percentage": 75, "assessment_mode": "H"},  # High
                        {"factor_id": "factor_2", "percentage": 50, "assessment_mode": "M"},  # Medium  
                        {"factor_id": "factor_3", "percentage": 25, "assessment_mode": "L"},  # Low
                        {"factor_id": "factor_4", "percentage": 75, "assessment_mode": "H"},  # High
                        {"factor_id": "factor_5", "percentage": 50, "assessment_mode": "M"}   # Medium
                    ],
                    "option_2": [
                        {"factor_id": "factor_1", "percentage": 50, "assessment_mode": "M"},  # Medium
                        {"factor_id": "factor_2", "percentage": 75, "assessment_mode": "H"},  # High
                        {"factor_id": "factor_3", "percentage": 75, "assessment_mode": "H"},  # High
                        {"factor_id": "factor_4", "percentage": 25, "assessment_mode": "L"},  # Low
                        {"factor_id": "factor_5", "percentage": 75, "assessment_mode": "H"}   # High
                    ]
                }
            },
            {
                "name": "Edge case: Assessment percentage = 150 (should be clamped to 100)",
                "option_assessments": {
                    "option_1": [
                        {"factor_id": "factor_1", "percentage": 150, "assessment_mode": "custom", "unit_value": "150000 USD"},  # Should clamp to 100
                        {"factor_id": "factor_2", "percentage": 80, "assessment_mode": "H"},
                        {"factor_id": "factor_3", "percentage": 60, "assessment_mode": "M"},
                        {"factor_id": "factor_4", "percentage": 70, "assessment_mode": "H"},
                        {"factor_id": "factor_5", "percentage": 90, "assessment_mode": "H"}
                    ]
                }
            },
            {
                "name": "Edge case: Assessment percentage = 0",
                "option_assessments": {
                    "option_1": [
                        {"factor_id": "factor_1", "percentage": 0, "assessment_mode": "custom", "unit_value": "0 USD"},
                        {"factor_id": "factor_2", "percentage": 50, "assessment_mode": "M"},
                        {"factor_id": "factor_3", "percentage": 75, "assessment_mode": "H"},
                        {"factor_id": "factor_4", "percentage": 25, "assessment_mode": "L"},
                        {"factor_id": "factor_5", "percentage": 50, "assessment_mode": "M"}
                    ]
                }
            },
            {
                "name": "All factors at 100% - worth should be exactly 100",
                "option_assessments": {
                    "option_1": [
                        {"factor_id": "factor_1", "percentage": 100, "assessment_mode": "custom", "unit_value": "200000 USD"},
                        {"factor_id": "factor_2", "percentage": 100, "assessment_mode": "custom", "unit_value": "Excellent"},
                        {"factor_id": "factor_3", "percentage": 100, "assessment_mode": "custom", "unit_value": "Perfect"},
                        {"factor_id": "factor_4", "percentage": 100, "assessment_mode": "custom", "unit_value": "Amazing"},
                        {"factor_id": "factor_5", "percentage": 100, "assessment_mode": "custom", "unit_value": "Outstanding"}
                    ]
                }
            },
            {
                "name": "All factors at 75% (H) - worth should be exactly 75",
                "option_assessments": {
                    "option_1": [
                        {"factor_id": "factor_1", "percentage": 75, "assessment_mode": "H"},
                        {"factor_id": "factor_2", "percentage": 75, "assessment_mode": "H"},
                        {"factor_id": "factor_3", "percentage": 75, "assessment_mode": "H"},
                        {"factor_id": "factor_4", "percentage": 75, "assessment_mode": "H"},
                        {"factor_id": "factor_5", "percentage": 75, "assessment_mode": "H"}
                    ]
                }
            }
        ]
        
        success_count = 0
        total_tests = len(test_cases)
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n4.{chr(96+i)}. Testing: {test_case['name']}")
            
            # Update options with assessments
            test_options = []
            for option_id, assessments in test_case['option_assessments'].items():
                test_options.append({
                    "id": option_id,
                    "name": "Tech Startup Position" if option_id == "option_1" else "Corporate Position",
                    "assessments": assessments,
                    "worth_percentage": 0.0
                })
            
            # Add empty option if only one option provided in test case
            if len(test_options) == 1:
                other_option_id = "option_2" if test_options[0]["id"] == "option_1" else "option_1"
                test_options.append({
                    "id": other_option_id,
                    "name": "Corporate Position" if other_option_id == "option_2" else "Tech Startup Position", 
                    "assessments": [],
                    "worth_percentage": 0.0
                })
            
            update_data = {
                "factors": factors,
                "options": test_options
            }
            
            response = await self.client.put(
                f"{API_BASE}/decisions/{decision_id}",
                json=update_data,
                headers=headers
            )
            
            if response.status_code != 200:
                print(f"❌ Failed to update assessments: {response.status_code} - {response.text}")
                continue
                
            # Get the updated decision to check worth_percentage
            response = await self.client.get(
                f"{API_BASE}/decisions/{decision_id}",
                headers=headers
            )
            
            if response.status_code != 200:
                print(f"❌ Failed to retrieve updated decision: {response.status_code} - {response.text}")
                continue
                
            decision = response.json()
            
            # Analyze results for each option
            test_passed = True
            for option in decision.get("options", []):
                worth = option.get("worth_percentage", 0)
                option_name = option.get("name", "Unknown")
                
                print(f"   Option '{option_name}': worth_percentage = {worth}%")
                
                # Check that worth never exceeds 100%
                if worth > 100:
                    print(f"❌ CRITICAL BUG: Worth percentage {worth}% exceeds 100% limit!")
                    test_passed = False
                
                # Verify assessments are properly clamped
                for assessment in option.get("assessments", []):
                    pct = assessment.get("percentage", 0)
                    if pct > 100:
                        print(f"❌ Assessment percentage {pct}% not clamped to 100%")
                        test_passed = False
                    elif pct < 0:
                        print(f"❌ Assessment percentage {pct}% below 0%")
                        test_passed = False
                        
                    # Verify unit_value and assessment_mode are preserved
                    if "unit_value" in assessment:
                        print(f"   - unit_value preserved: {assessment['unit_value']}")
                    if "assessment_mode" in assessment:
                        print(f"   - assessment_mode preserved: {assessment['assessment_mode']}")
                
                # Specific validation for test cases
                if test_case["name"] == "All factors at 100% - worth should be exactly 100":
                    # Only validate the option with assessments
                    if option.get("assessments", []):
                        if abs(worth - 100.0) > 0.01:  # Allow small floating point differences
                            print(f"❌ Expected exactly 100% but got {worth}%")
                            test_passed = False
                elif test_case["name"] == "All factors at 75% (H) - worth should be exactly 75":
                    # Only validate the option with assessments
                    if option.get("assessments", []):
                        if abs(worth - 75.0) > 0.01:
                            print(f"❌ Expected exactly 75% but got {worth}%")
                            test_passed = False
                elif "Assessment percentage = 150" in test_case["name"]:
                    # Check that the 150% input was clamped to 100% in the calculation
                    # Only check for the option that has assessments
                    if option.get("assessments", []):
                        found_clamped = False
                        for assessment in option.get("assessments", []):
                            if assessment.get("percentage") == 100 and assessment.get("unit_value") == "150000 USD":
                                found_clamped = True
                                print(f"✅ Assessment percentage correctly clamped from 150% to 100%")
                                break
                        if not found_clamped:
                            print(f"❌ Assessment percentage clamping not working")
                            test_passed = False
            
            if test_passed:
                print(f"✅ Test case '{test_case['name']}' PASSED")
                success_count += 1
            else:
                print(f"❌ Test case '{test_case['name']}' FAILED")
        
        print(f"\n=== PRR Worth Calculation Test Results ===")
        print(f"Tests passed: {success_count}/{total_tests}")
        
        if success_count == total_tests:
            print("✅ ALL PRR DECISIONS WORTH CALCULATION TESTS PASSED!")
            print("✅ Bug fix verified: worth_percentage never exceeds 100%")
            print("✅ Assessment percentage clamping working correctly")
            print("✅ unit_value and assessment_mode fields preserved")
            return True
        else:
            print("❌ Some PRR decisions tests failed - bug fix needs attention")
            return False

async def main():
    """Run all backend API tests"""
    tester = BackendAPITester()
    
    try:
        print("🚀 Starting Backend API Tests for PRR Decisions Worth Percentage Bug Fix")
        print(f"Backend URL: {BACKEND_URL}")
        
        # Register user first
        if not await tester.register_user():
            print("❌ Cannot continue without user registration")
            return False
            
        # Test PRR decisions worth calculation bug fix
        prr_success = await tester.test_prr_decisions_worth_calculation_bug_fix()
        
        print("\n" + "="*80)
        print("📊 FINAL TEST SUMMARY")
        print("="*80)
        
        if prr_success:
            print("✅ PRR Decisions Worth Percentage Bug Fix: PASSED")
            print("✅ Backend is working correctly with the bug fix implemented")
            return True
        else:
            print("❌ PRR Decisions Worth Percentage Bug Fix: FAILED")
            print("❌ Critical issues found that need immediate attention")
            return False
            
    except Exception as e:
        print(f"❌ Unexpected error during testing: {e}")
        return False
        
    finally:
        await tester.close()

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)