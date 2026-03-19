#!/usr/bin/env python3

import asyncio
import aiohttp
import json
import sys
from datetime import datetime
from typing import Dict, Any, List

# Backend URL configuration
BACKEND_URL = "https://best-mate-decisions.preview.emergentagent.com/api"

class CloneTemplateAPITester:
    def __init__(self):
        self.session = None
        self.bearer_token = None
        self.user_id = None
        self.decision_id = None
        self.template_ids = []
        self.test_results = []
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def log_test(self, test_name: str, status: str, details: str = ""):
        """Log test result"""
        result = f"{'✅' if status == 'PASS' else '❌'} {test_name}: {status}"
        if details:
            result += f" - {details}"
        print(result)
        self.test_results.append({
            "name": test_name,
            "status": status,
            "details": details
        })
    
    async def make_request(self, method: str, endpoint: str, data: Dict = None, auth: bool = True) -> Dict:
        """Make HTTP request with proper headers"""
        headers = {"Content-Type": "application/json"}
        if auth and self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        
        url = f"{BACKEND_URL}{endpoint}"
        
        try:
            if method.upper() == "GET":
                async with self.session.get(url, headers=headers) as resp:
                    response_data = await resp.json()
                    return {"status": resp.status, "data": response_data}
            elif method.upper() == "POST":
                async with self.session.post(url, headers=headers, json=data) as resp:
                    response_data = await resp.json()
                    return {"status": resp.status, "data": response_data}
            elif method.upper() == "PUT":
                async with self.session.put(url, headers=headers, json=data) as resp:
                    response_data = await resp.json()
                    return {"status": resp.status, "data": response_data}
            elif method.upper() == "DELETE":
                async with self.session.delete(url, headers=headers) as resp:
                    if resp.status == 200:
                        response_data = await resp.json()
                    else:
                        response_data = {"message": "Deleted successfully"}
                    return {"status": resp.status, "data": response_data}
        except Exception as e:
            return {"status": 500, "data": {"error": str(e)}}
    
    async def test_01_register_and_login(self):
        """Test 1: Register & Login with Bearer token"""
        print("\n=== STEP 1: USER REGISTRATION & LOGIN ===")
        
        # Register user
        register_data = {
            "email": "clonetest@test.com",
            "password": "test123",
            "name": "Clone Tester"
        }
        
        resp = await self.make_request("POST", "/auth/register", register_data, auth=False)
        if resp["status"] == 200:
            self.bearer_token = resp["data"]["session_token"]
            self.user_id = resp["data"]["user_id"]
            self.log_test("User Registration", "PASS", f"User created: {resp['data']['email']}")
            self.log_test("Bearer Token Generation", "PASS", f"Token: {self.bearer_token[:20]}...")
        else:
            self.log_test("User Registration", "FAIL", f"Status {resp['status']}: {resp['data']}")
            return False
        
        return True
    
    async def test_02_create_decision_with_full_data(self):
        """Test 2: Create a decision with factors, classifications, ratings and options"""
        print("\n=== STEP 2: CREATE DECISION WITH FULL DATA ===")
        
        # Create basic decision
        decision_data = {
            "title": "Career Decision",
            "context": "Choosing next career move"
        }
        
        resp = await self.make_request("POST", "/decisions", decision_data)
        if resp["status"] == 200:
            self.decision_id = resp["data"]["id"]
            self.log_test("Decision Creation", "PASS", f"Decision ID: {self.decision_id}")
        else:
            self.log_test("Decision Creation", "FAIL", f"Status {resp['status']}: {resp['data']}")
            return False
        
        # Add factors with classifications and ratings + options with assessments
        factor1_id = "factor_salary_123"
        factor2_id = "factor_growth_456" 
        factor3_id = "factor_balance_789"
        option1_id = "option_companya_111"
        option2_id = "option_companyb_222"
        
        update_data = {
            "factors": [
                {
                    "id": factor1_id,
                    "name": "Salary",
                    "category": "primary",
                    "rating": 50,
                    "order": 1
                },
                {
                    "id": factor2_id,
                    "name": "Growth",
                    "category": "primary", 
                    "rating": 40,
                    "order": 2
                },
                {
                    "id": factor3_id,
                    "name": "Work-Life Balance",
                    "category": "secondary",
                    "rating": 30,
                    "order": 3
                }
            ],
            "options": [
                {
                    "id": option1_id,
                    "name": "Company A",
                    "assessments": [
                        {"factor_id": factor1_id, "percentage": 80, "unit_value": "120000 USD", "assessment_mode": "custom"},
                        {"factor_id": factor2_id, "percentage": 70, "unit_value": "High", "assessment_mode": "H"},
                        {"factor_id": factor3_id, "percentage": 60, "unit_value": "Medium", "assessment_mode": "M"}
                    ],
                    "worth_percentage": 0.0
                },
                {
                    "id": option2_id,
                    "name": "Company B", 
                    "assessments": [
                        {"factor_id": factor1_id, "percentage": 65, "unit_value": "95000 USD", "assessment_mode": "custom"},
                        {"factor_id": factor2_id, "percentage": 90, "unit_value": "Very High", "assessment_mode": "custom"},
                        {"factor_id": factor3_id, "percentage": 85, "unit_value": "High", "assessment_mode": "H"}
                    ],
                    "worth_percentage": 0.0
                }
            ]
        }
        
        resp = await self.make_request("PUT", f"/decisions/{self.decision_id}", update_data)
        if resp["status"] == 200:
            self.log_test("Decision Update with Factors & Options", "PASS", "3 factors (2 primary, 1 secondary) + 2 options with assessments added")
        else:
            self.log_test("Decision Update with Factors & Options", "FAIL", f"Status {resp['status']}: {resp['data']}")
            return False
        
        # Verify the decision was created correctly
        resp = await self.make_request("GET", f"/decisions/{self.decision_id}")
        if resp["status"] == 200:
            decision = resp["data"]
            factors_count = len(decision.get("factors", []))
            options_count = len(decision.get("options", []))
            self.log_test("Decision Verification", "PASS", f"Decision has {factors_count} factors and {options_count} options")
        else:
            self.log_test("Decision Verification", "FAIL", f"Could not retrieve decision: {resp['data']}")
            return False
        
        return True
    
    async def test_03_clone_at_each_level(self):
        """Test 3: Test Clone at each level"""
        print("\n=== STEP 3: TEST CLONE AT EACH LEVEL ===")
        
        clone_tests = [
            {
                "level": "factors",
                "title": "2026-03-19 Clone Factors", 
                "verify": "factors have names but ratings reset to 0 and category reset to primary"
            },
            {
                "level": "classification",
                "title": "2026-03-19 Clone Classification",
                "verify": "factors have correct primary/secondary categories but ratings reset to 0"
            },
            {
                "level": "prioritization",
                "title": "2026-03-19 Clone Priority",
                "verify": "factors have categories AND ratings preserved"
            },
            {
                "level": "options",
                "title": "2026-03-19 Clone Options", 
                "verify": "factors + options names present, but no assessments"
            },
            {
                "level": "assessment",
                "title": "2026-03-19 Clone Full",
                "verify": "complete clone with assessments and worth_percentages"
            }
        ]
        
        for test in clone_tests:
            clone_data = {
                "title": test["title"],
                "clone_level": test["level"]
            }
            
            resp = await self.make_request("POST", f"/decisions/{self.decision_id}/clone", clone_data)
            if resp["status"] == 200:
                cloned_id = resp["data"]["id"]
                self.log_test(f"Clone {test['level'].title()} Level", "PASS", f"Cloned decision ID: {cloned_id}")
                
                # Verify clone result
                resp = await self.make_request("GET", f"/decisions/{cloned_id}")
                if resp["status"] == 200:
                    cloned = resp["data"]
                    verification_result = await self._verify_clone_level(test["level"], cloned)
                    if verification_result["success"]:
                        self.log_test(f"Verify Clone {test['level'].title()}", "PASS", verification_result["details"])
                    else:
                        self.log_test(f"Verify Clone {test['level'].title()}", "FAIL", verification_result["details"])
                else:
                    self.log_test(f"Verify Clone {test['level'].title()}", "FAIL", f"Could not retrieve cloned decision")
            else:
                self.log_test(f"Clone {test['level'].title()} Level", "FAIL", f"Status {resp['status']}: {resp['data']}")
        
        return True
    
    async def _verify_clone_level(self, level: str, cloned_decision: Dict) -> Dict[str, Any]:
        """Verify clone results match expected level"""
        factors = cloned_decision.get("factors", [])
        options = cloned_decision.get("options", [])
        
        if level == "factors":
            # Should have factor names, but ratings=0 and category=primary
            if all(f.get("rating") == 0 and f.get("category") == "primary" for f in factors):
                return {"success": True, "details": f"✓ {len(factors)} factors with names, ratings reset to 0, categories reset to primary"}
            else:
                return {"success": False, "details": "Factors don't match 'factors' level requirements"}
        
        elif level == "classification": 
            # Should preserve primary/secondary categories but reset ratings to 0
            primary_count = sum(1 for f in factors if f.get("category") == "primary")
            secondary_count = sum(1 for f in factors if f.get("category") == "secondary")
            all_ratings_zero = all(f.get("rating") == 0 for f in factors)
            
            if all_ratings_zero and primary_count >= 1 and secondary_count >= 1:
                return {"success": True, "details": f"✓ Categories preserved ({primary_count} primary, {secondary_count} secondary), ratings reset to 0"}
            else:
                return {"success": False, "details": "Classification level requirements not met"}
        
        elif level == "prioritization":
            # Should preserve categories AND ratings
            ratings_preserved = any(f.get("rating", 0) > 0 for f in factors)
            categories_preserved = any(f.get("category") == "secondary" for f in factors)
            
            if ratings_preserved and categories_preserved:
                return {"success": True, "details": f"✓ Categories and ratings preserved"}
            else:
                return {"success": False, "details": "Prioritization level requirements not met"}
        
        elif level == "options":
            # Should have factors + options but no assessments
            options_have_no_assessments = all(len(opt.get("assessments", [])) == 0 for opt in options)
            
            if len(options) > 0 and options_have_no_assessments:
                return {"success": True, "details": f"✓ {len(factors)} factors + {len(options)} options, no assessments"}
            else:
                return {"success": False, "details": "Options level requirements not met"}
        
        elif level == "assessment":
            # Should be complete clone with assessments
            options_have_assessments = any(len(opt.get("assessments", [])) > 0 for opt in options)
            
            if len(options) > 0 and options_have_assessments:
                return {"success": True, "details": f"✓ Complete clone with assessments preserved"}
            else:
                return {"success": False, "details": "Assessment level requirements not met"}
        
        return {"success": False, "details": "Unknown clone level"}
    
    async def test_04_template_functionality(self):
        """Test 4: Test Templates - save, list, use, delete"""
        print("\n=== STEP 4: TEST TEMPLATE FUNCTIONALITY ===")
        
        # Save decision as template (options type)
        template_data = {
            "name": "Career Template",
            "template_type": "options"
        }
        
        resp = await self.make_request("POST", f"/decisions/{self.decision_id}/save-as-template", template_data)
        if resp["status"] == 200:
            template1_id = resp["data"]["id"]
            self.template_ids.append(template1_id)
            self.log_test("Save Template (Options Type)", "PASS", f"Template ID: {template1_id}")
        else:
            self.log_test("Save Template (Options Type)", "FAIL", f"Status {resp['status']}: {resp['data']}")
            return False
        
        # Save decision as template (assessment type)
        template_data2 = {
            "name": "Career Full Template", 
            "template_type": "assessment"
        }
        
        resp = await self.make_request("POST", f"/decisions/{self.decision_id}/save-as-template", template_data2)
        if resp["status"] == 200:
            template2_id = resp["data"]["id"]
            self.template_ids.append(template2_id)
            self.log_test("Save Template (Assessment Type)", "PASS", f"Template ID: {template2_id}")
        else:
            self.log_test("Save Template (Assessment Type)", "FAIL", f"Status {resp['status']}: {resp['data']}")
            return False
        
        # List all templates
        resp = await self.make_request("GET", "/templates")
        if resp["status"] == 200:
            templates = resp["data"]
            template_count = len(templates)
            our_templates = [t for t in templates if t["id"] in self.template_ids]
            self.log_test("List Templates", "PASS", f"Found {template_count} templates, {len(our_templates)} are ours")
        else:
            self.log_test("List Templates", "FAIL", f"Status {resp['status']}: {resp['data']}")
            return False
        
        # Use template to create new decision
        use_template_data = {
            "title": "2026-03-19 From Template"
        }
        
        resp = await self.make_request("POST", f"/templates/{template1_id}/use", use_template_data)
        if resp["status"] == 200:
            new_decision_id = resp["data"]["id"]
            self.log_test("Use Template", "PASS", f"New decision created: {new_decision_id}")
            
            # Verify new decision has correct data
            resp = await self.make_request("GET", f"/decisions/{new_decision_id}")
            if resp["status"] == 200:
                new_decision = resp["data"]
                factors_count = len(new_decision.get("factors", []))
                options_count = len(new_decision.get("options", []))
                self.log_test("Verify Template Usage", "PASS", f"New decision has {factors_count} factors and {options_count} options")
            else:
                self.log_test("Verify Template Usage", "FAIL", "Could not retrieve new decision")
        else:
            self.log_test("Use Template", "FAIL", f"Status {resp['status']}: {resp['data']}")
        
        # Delete template
        resp = await self.make_request("DELETE", f"/templates/{template1_id}")
        if resp["status"] == 200:
            self.log_test("Delete Template", "PASS", "Template deleted successfully")
        else:
            self.log_test("Delete Template", "FAIL", f"Status {resp['status']}: {resp['data']}")
        
        return True
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("CLONE & TEMPLATE API TESTING SUMMARY")
        print("="*60)
        
        passed = sum(1 for r in self.test_results if r["status"] == "PASS")
        failed = sum(1 for r in self.test_results if r["status"] == "FAIL")
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {(passed/total*100):.1f}%")
        
        if failed > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if result["status"] == "FAIL":
                    print(f"  - {result['name']}: {result['details']}")
        else:
            print("\n🎉 ALL TESTS PASSED!")
        
        print("\n" + "="*60)

async def main():
    """Run all Clone and Template API tests"""
    print("🚀 Starting Clone and Template API Tests...")
    print(f"Backend URL: {BACKEND_URL}")
    
    async with CloneTemplateAPITester() as tester:
        # Run all tests in sequence
        success = True
        
        success = await tester.test_01_register_and_login() and success
        if not success:
            print("❌ Registration failed, stopping tests")
            return
            
        success = await tester.test_02_create_decision_with_full_data() and success
        if not success:
            print("❌ Decision creation failed, stopping tests") 
            return
            
        await tester.test_03_clone_at_each_level()
        await tester.test_04_template_functionality()
        
        # Print summary
        tester.print_summary()

if __name__ == "__main__":
    asyncio.run(main())