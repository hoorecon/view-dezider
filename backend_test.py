#!/usr/bin/env python3
"""
Solutions Store + ReviewNet Backend Testing
Comprehensive test suite for all Solutions Store and ReviewNet endpoints
"""

import asyncio
import httpx
import json
import sys
from datetime import datetime

# Backend URL from frontend/.env
BASE_URL = "https://prr-actions-central.preview.emergentagent.com/api"

class SolutionsStoreTestSuite:
    def __init__(self):
        self.base_url = BASE_URL
        self.session_token = None
        self.user_id = None
        self.test_results = []
        self.private_solution_id = None
        self.public_solution_id = None
        
    async def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        result = f"{status}: {test_name}"
        if details:
            result += f" - {details}"
        print(result)
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details
        })
        
    async def make_request(self, method: str, endpoint: str, data: dict = None, headers: dict = None):
        """Make HTTP request with error handling"""
        url = f"{self.base_url}{endpoint}"
        request_headers = {}
        
        if self.session_token:
            request_headers["Authorization"] = f"Bearer {self.session_token}"
            
        if headers:
            request_headers.update(headers)
            
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=request_headers)
                elif method.upper() == "POST":
                    response = await client.post(url, json=data, headers=request_headers)
                elif method.upper() == "PUT":
                    response = await client.put(url, json=data, headers=request_headers)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=request_headers)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                    
                return response
        except Exception as e:
            print(f"Request failed: {method} {url} - {str(e)}")
            return None
            
    async def test_1_register_user(self):
        """Test 1: Register a test user"""
        test_name = "User Registration"
        
        user_data = {
            "email": "store_test@test.com",
            "password": "TestPass123!",
            "name": "Store Test User"
        }
        
        response = await self.make_request("POST", "/auth/register", user_data)
        
        if response and response.status_code == 200:
            data = response.json()
            self.session_token = data.get("session_token")
            self.user_id = data.get("user_id")
            await self.log_result(test_name, True, f"User registered with ID: {self.user_id}")
            return True
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_2_seed_solutions_data(self):
        """Test 2: Seed solutions data"""
        test_name = "Seed Solutions Data"
        
        response = await self.make_request("POST", "/solutions-store/seed?force=true")
        
        if response and response.status_code == 200:
            data = response.json()
            count = data.get("count", 0)
            await self.log_result(test_name, True, f"Seeded {count} solutions")
            return True
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_3_list_solutions(self):
        """Test 3: Test listing solutions"""
        test_name = "List Solutions"
        
        response = await self.make_request("GET", "/solutions-store/solutions")
        
        if response and response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                count = len(data)
                await self.log_result(test_name, True, f"Retrieved {count} solutions")
                return count >= 14  # Should return 14 seeded solutions
            else:
                await self.log_result(test_name, False, "Response is not a list")
                return False
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_4_browse_by_life_area(self):
        """Test 4: Test browsing by life area"""
        test_name = "Browse by Life Area (Health)"
        
        response = await self.make_request("GET", "/solutions-store/browse?life_area_id=la_health")
        
        if response and response.status_code == 200:
            data = response.json()
            solutions = data.get("solutions", [])
            grouped = data.get("grouped_by_sub_area", {})
            total = data.get("total", 0)
            await self.log_result(test_name, True, f"Found {total} health solutions, grouped by {len(grouped)} sub-areas")
            return True
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_5_for_decision_endpoint(self):
        """Test 5: Test for-decision endpoint"""
        test_name = "For-Decision Endpoint (Finance)"
        
        response = await self.make_request("GET", "/solutions-store/for-decision?life_area_id=la_finance")
        
        if response and response.status_code == 200:
            data = response.json()
            solutions = data.get("solutions", [])
            total = data.get("total", 0)
            await self.log_result(test_name, True, f"Found {total} finance solutions for decision")
            return True
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_6_search_solutions(self):
        """Test 6: Test search functionality"""
        test_name = "Search Solutions (Apollo)"
        
        response = await self.make_request("GET", "/solutions-store/search?q=Apollo")
        
        if response and response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            query = data.get("query", "")
            total = data.get("total", 0)
            
            # Check if Apollo Hospitals is found
            apollo_found = any("Apollo" in result.get("name", "") for result in results)
            await self.log_result(test_name, apollo_found, f"Found {total} results for '{query}', Apollo Hospitals: {'Yes' if apollo_found else 'No'}")
            return apollo_found
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_7_create_private_solution(self):
        """Test 7: Create a PRIVATE solution"""
        test_name = "Create Private Solution"
        
        solution_data = {
            "type": "SERVICE",
            "name": "Test Private Service",
            "description": "My private service",
            "life_area_id": "la_health",
            "visibility": "PRIVATE",
            "country": "IN",
            "city": "Chennai",
            "quantitative_factors": [
                {
                    "factor_name": "Cost",
                    "value": 5000,
                    "unit": "INR"
                }
            ]
        }
        
        response = await self.make_request("POST", "/solutions-store/solutions", solution_data)
        
        if response and response.status_code == 200:
            data = response.json()
            self.private_solution_id = data.get("solution_id")
            visibility = data.get("visibility")
            approval_status = data.get("approval_status")
            is_authorized = data.get("is_authorized")
            
            success = (visibility == "PRIVATE" and approval_status == "approved" and not is_authorized)
            await self.log_result(test_name, success, f"Solution ID: {self.private_solution_id}, Visibility: {visibility}, Status: {approval_status}, Authorized: {is_authorized}")
            return success
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_8_create_public_solution(self):
        """Test 8: Create a PUBLIC solution (should get pending approval)"""
        test_name = "Create Public Solution (Pending Approval)"
        
        solution_data = {
            "type": "PRODUCT",
            "name": "Test Public Product",
            "description": "A product for everyone",
            "life_area_id": "la_health",
            "visibility": "PUBLIC",
            "country": "IN",
            "city": "Chennai"
        }
        
        response = await self.make_request("POST", "/solutions-store/solutions", solution_data)
        
        if response and response.status_code == 200:
            data = response.json()
            self.public_solution_id = data.get("solution_id")
            visibility = data.get("visibility")
            approval_status = data.get("approval_status")
            is_authorized = data.get("is_authorized")
            
            # For normal users, PUBLIC solutions should be pending approval and not authorized
            success = (visibility == "PUBLIC" and approval_status == "pending" and not is_authorized)
            await self.log_result(test_name, success, f"Solution ID: {self.public_solution_id}, Visibility: {visibility}, Status: {approval_status}, Authorized: {is_authorized}")
            return success
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_9_solution_detail(self):
        """Test 9: Test solution detail endpoint"""
        test_name = "Solution Detail"
        
        if not self.private_solution_id:
            await self.log_result(test_name, False, "No private solution ID available")
            return False
            
        response = await self.make_request("GET", f"/solutions-store/solutions/{self.private_solution_id}")
        
        if response and response.status_code == 200:
            data = response.json()
            solution_id = data.get("solution_id")
            name = data.get("name")
            quantitative_factors = data.get("quantitative_factors", [])
            
            success = (solution_id == self.private_solution_id and name == "Test Private Service")
            await self.log_result(test_name, success, f"Retrieved solution: {name}, Quantitative factors: {len(quantitative_factors)}")
            return success
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_10_submit_review(self):
        """Test 10: Submit a review via ReviewNet"""
        test_name = "Submit Review"
        
        if not self.private_solution_id:
            await self.log_result(test_name, False, "No private solution ID available")
            return False
            
        review_data = {
            "solution_id": self.private_solution_id,
            "review_text": "Great service!",
            "pros": ["Fast and reliable"],
            "cons": ["Expensive"],
            "qualitative_factors": [
                {"factor_name": "Trustworthiness", "rating": 8},
                {"factor_name": "Quality", "rating": 9},
                {"factor_name": "Value for Money", "rating": 6}
            ]
        }
        
        response = await self.make_request("POST", "/reviewnet/reviews", review_data)
        
        if response and response.status_code == 200:
            data = response.json()
            review_id = data.get("review_id")
            solution_id = data.get("solution_id")
            overall_rating = data.get("overall_rating")
            
            success = (solution_id == self.private_solution_id and review_id is not None)
            await self.log_result(test_name, success, f"Review ID: {review_id}, Overall rating: {overall_rating}")
            return success
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_11_get_reviews(self):
        """Test 11: Get reviews for a solution"""
        test_name = "Get Reviews"
        
        if not self.private_solution_id:
            await self.log_result(test_name, False, "No private solution ID available")
            return False
            
        response = await self.make_request("GET", f"/reviewnet/reviews?solution_id={self.private_solution_id}")
        
        if response and response.status_code == 200:
            data = response.json()
            reviews = data.get("reviews", [])
            aggregated_scores = data.get("aggregated_scores", [])
            overall_avg_rating = data.get("overall_avg_rating")
            total_reviews = data.get("total_reviews", 0)
            
            success = (total_reviews > 0 and overall_avg_rating is not None)
            await self.log_result(test_name, success, f"Reviews: {total_reviews}, Avg rating: {overall_avg_rating}, Aggregated factors: {len(aggregated_scores)}")
            return success
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_12_apply_to_option(self):
        """Test 12: Test apply-to-option endpoint"""
        test_name = "Apply to Option"
        
        if not self.private_solution_id:
            await self.log_result(test_name, False, "No private solution ID available")
            return False
            
        apply_data = {
            "solution_id": self.private_solution_id
        }
        
        response = await self.make_request("POST", "/solutions-store/apply-to-option", apply_data)
        
        if response and response.status_code == 200:
            data = response.json()
            quantitative_factors = data.get("quantitative_factors", [])
            qualitative_factors = data.get("qualitative_factors", [])
            solution_name = data.get("solution_name")
            
            success = (solution_name == "Test Private Service" and len(quantitative_factors) > 0)
            await self.log_result(test_name, success, f"Solution: {solution_name}, Quant factors: {len(quantitative_factors)}, Qual factors: {len(qualitative_factors)}")
            return success
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_13_qualitative_factors_list(self):
        """Test 13: Test qualitative factors list"""
        test_name = "Qualitative Factors List"
        
        response = await self.make_request("GET", "/reviewnet/qualitative-factors")
        
        if response and response.status_code == 200:
            data = response.json()
            factors = data.get("factors", [])
            
            expected_factors = ["Trustworthiness", "Quality", "Reliability", "Value for Money"]
            has_expected = all(factor in factors for factor in expected_factors)
            
            await self.log_result(test_name, has_expected, f"Found {len(factors)} default factors: {factors[:4]}...")
            return has_expected
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_14_setup_admin_user(self):
        """Test 14: Set up admin user for approval tests"""
        test_name = "Setup Admin User"
        
        response = await self.make_request("POST", "/admin/setup")
        
        if response and response.status_code == 200:
            data = response.json()
            role = data.get("role")
            await self.log_result(test_name, True, f"User promoted to: {role}")
            return True
        elif response and response.status_code == 400:
            # Super admin already exists
            await self.log_result(test_name, True, "Super admin already exists (expected)")
            return True
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_15_pending_approvals(self):
        """Test 15: Test pending approvals endpoint"""
        test_name = "Pending Approvals"
        
        response = await self.make_request("GET", "/solutions-store/pending-approval")
        
        if response and response.status_code == 200:
            data = response.json()
            solutions = data.get("solutions", [])
            total = data.get("total", 0)
            
            # Should find the public solution from test 8
            public_found = any(sol.get("solution_id") == self.public_solution_id for sol in solutions)
            await self.log_result(test_name, public_found, f"Found {total} pending solutions, Public solution found: {'Yes' if public_found else 'No'}")
            return public_found
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_16_approve_solution(self):
        """Test 16: Test approve solution"""
        test_name = "Approve Solution"
        
        if not self.public_solution_id:
            await self.log_result(test_name, False, "No public solution ID available")
            return False
            
        response = await self.make_request("PUT", f"/solutions-store/approve/{self.public_solution_id}")
        
        if response and response.status_code == 200:
            data = response.json()
            message = data.get("message")
            solution_id = data.get("solution_id")
            
            success = (solution_id == self.public_solution_id)
            await self.log_result(test_name, success, f"Message: {message}")
            return success
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def test_17_verify_approved_solution(self):
        """Test 17: Verify the approved solution appears with is_authorized=true"""
        test_name = "Verify Approved Solution"
        
        if not self.public_solution_id:
            await self.log_result(test_name, False, "No public solution ID available")
            return False
            
        response = await self.make_request("GET", f"/solutions-store/solutions/{self.public_solution_id}")
        
        if response and response.status_code == 200:
            data = response.json()
            is_authorized = data.get("is_authorized")
            approval_status = data.get("approval_status")
            visibility = data.get("visibility")
            
            success = (is_authorized and approval_status == "approved" and visibility == "PUBLIC")
            await self.log_result(test_name, success, f"Authorized: {is_authorized}, Status: {approval_status}, Visibility: {visibility}")
            return success
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False
            
    async def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Solutions Store + ReviewNet Backend Testing")
        print("=" * 60)
        
        tests = [
            self.test_1_register_user,
            self.test_2_seed_solutions_data,
            self.test_3_list_solutions,
            self.test_4_browse_by_life_area,
            self.test_5_for_decision_endpoint,
            self.test_6_search_solutions,
            self.test_7_create_private_solution,
            self.test_8_create_public_solution,
            self.test_9_solution_detail,
            self.test_10_submit_review,
            self.test_11_get_reviews,
            self.test_12_apply_to_option,
            self.test_13_qualitative_factors_list,
            self.test_14_setup_admin_user,
            self.test_15_pending_approvals,
            self.test_16_approve_solution,
            self.test_17_verify_approved_solution,
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            try:
                result = await test()
                if result:
                    passed += 1
            except Exception as e:
                print(f"❌ FAIL: {test.__name__} - Exception: {str(e)}")
                
        print("\n" + "=" * 60)
        print(f"🎯 TEST SUMMARY: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED! Solutions Store + ReviewNet is working correctly.")
        else:
            print(f"⚠️  {total - passed} tests failed. Please check the implementation.")
            
        return passed == total

async def main():
    """Main test runner"""
    test_suite = SolutionsStoreTestSuite()
    success = await test_suite.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())