#!/usr/bin/env python3
"""
Backend Test for CLD Simulation, Solutions Store, and Credit Deduction Re-testing
Re-testing the 3 previously failed areas from comprehensive UAT
"""

import requests
import json
import time
from datetime import datetime

# Backend URL from environment
BASE_URL = "https://dezider-core.preview.emergentagent.com/api"

class BackendTester:
    def __init__(self):
        self.session_token = None
        self.decision_id = None
        self.test_results = []
        
    def log_result(self, test_num, test_name, success, details=""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        result = f"Test {test_num}: {test_name} - {status}"
        if details:
            result += f" - {details}"
        print(result)
        self.test_results.append({
            'test_num': test_num,
            'test_name': test_name,
            'success': success,
            'details': details
        })
        
    def test_1_register_user(self):
        """Test 1: POST /api/auth/register"""
        try:
            timestamp = int(time.time())
            payload = {
                "email": "uat_retest@test.com",
                "password": "Test123!",
                "name": "UAT Retest User"
            }
            
            response = requests.post(f"{BASE_URL}/auth/register", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                self.session_token = data.get('session_token')
                if self.session_token:
                    self.log_result(1, "User Registration", True, f"Session token obtained")
                    return True
                else:
                    self.log_result(1, "User Registration", False, "No session token in response")
                    return False
            else:
                # Try with unique email if user already exists
                payload["email"] = f"uat_retest_{timestamp}@test.com"
                response = requests.post(f"{BASE_URL}/auth/register", json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    self.session_token = data.get('session_token')
                    if self.session_token:
                        self.log_result(1, "User Registration", True, f"Session token obtained with unique email")
                        return True
                
                self.log_result(1, "User Registration", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(1, "User Registration", False, f"Exception: {str(e)}")
            return False
    
    def get_headers(self):
        """Get authorization headers"""
        return {"Authorization": f"Bearer {self.session_token}"}
    
    def test_3_create_decision(self):
        """Test 3: POST /api/decisions - Create a Decision"""
        try:
            payload = {
                "title": "Retest Decision",
                "context": "Retest",
                "life_area": "Career",
                "decision_type": "need"
            }
            
            response = requests.post(f"{BASE_URL}/decisions", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                self.decision_id = data.get('id')  # Backend returns 'id', not 'decision_id'
                if self.decision_id:
                    self.log_result(3, "Create Decision", True, f"Decision ID: {self.decision_id}")
                    return True
                else:
                    self.log_result(3, "Create Decision", False, f"No id in response: {data}")
                    return False
            else:
                self.log_result(3, "Create Decision", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(3, "Create Decision", False, f"Exception: {str(e)}")
            return False
    
    def test_4_add_factors(self):
        """Test 4: PUT /api/decisions/{id} - Add factors"""
        try:
            payload = {
                "factors": [
                    {
                        "id": "rf1",
                        "name": "Factor A",
                        "category": "primary",
                        "rating": 90,
                        "order": 0
                    },
                    {
                        "id": "rf2", 
                        "name": "Factor B",
                        "category": "secondary",
                        "rating": 70,
                        "order": 1
                    },
                    {
                        "id": "rf3",
                        "name": "Factor C", 
                        "category": "secondary",
                        "rating": 60,
                        "order": 2
                    }
                ]
            }
            
            response = requests.put(f"{BASE_URL}/decisions/{self.decision_id}", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                self.log_result(4, "Add Factors", True, "3 factors added successfully")
                return True
            else:
                self.log_result(4, "Add Factors", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(4, "Add Factors", False, f"Exception: {str(e)}")
            return False
    
    def test_5_save_cld(self):
        """Test 5: POST /api/cld/{decision_id}/save - Save CLD with nodes and links"""
        try:
            payload = {
                "nodes": [
                    {
                        "factor_id": "rf1",
                        "name": "Factor A",
                        "x": 200,
                        "y": 60,
                        "centrality": 0.8,
                        "classification": "primary",
                        "priority_rank": 1,
                        "gap_multiplier": 2.0,
                        "base_value": 60,
                        "locked": False
                    },
                    {
                        "factor_id": "rf2",
                        "name": "Factor B", 
                        "x": 340,
                        "y": 200,
                        "centrality": 0.6,
                        "classification": "secondary",
                        "priority_rank": 2,
                        "gap_multiplier": 1.0,
                        "base_value": 50,
                        "locked": False
                    },
                    {
                        "factor_id": "rf3",
                        "name": "Factor C",
                        "x": 60,
                        "y": 200,
                        "centrality": 0.4,
                        "classification": "secondary",
                        "priority_rank": 3,
                        "gap_multiplier": 0.5,
                        "base_value": 40,
                        "locked": False
                    }
                ],
                "links": [
                    {
                        "from_id": "rf1",
                        "to_id": "rf2",
                        "link_type": "reinforcing",
                        "strength": 7,
                        "delay": 0,
                        "description": "A drives B"
                    },
                    {
                        "from_id": "rf2",
                        "to_id": "rf3",
                        "link_type": "balancing",
                        "strength": 5,
                        "delay": 0,
                        "description": "B limits C"
                    }
                ],
                "loops": [
                    {
                        "name": "R1: Growth Loop",
                        "loop_type": "reinforcing",
                        "factor_ids": ["rf1", "rf2"]
                    }
                ]
            }
            
            response = requests.post(f"{BASE_URL}/cld/{self.decision_id}/save", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                self.log_result(5, "Save CLD", True, "CLD saved with nodes, links, and loops")
                return True
            else:
                self.log_result(5, "Save CLD", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(5, "Save CLD", False, f"Exception: {str(e)}")
            return False
    
    def test_6_simulate_positive_shock(self):
        """Test 6: POST /api/cld/{decision_id}/simulate - Positive shock simulation"""
        try:
            payload = {
                "shock_factor_id": "rf1",
                "shock_delta": 20,
                "time_steps": 5,
                "dampening": 0.7
            }
            
            response = requests.post(f"{BASE_URL}/cld/{self.decision_id}/simulate", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ['timeline', 'final_values', 'total_impact', 'stability', 'baseline']
                missing_fields = [field for field in required_fields if field not in data]
                
                if not missing_fields:
                    self.log_result(6, "CLD Positive Shock Simulation", True, f"All required fields present: {required_fields}")
                    return True
                else:
                    self.log_result(6, "CLD Positive Shock Simulation", False, f"Missing fields: {missing_fields}")
                    return False
            else:
                self.log_result(6, "CLD Positive Shock Simulation", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(6, "CLD Positive Shock Simulation", False, f"Exception: {str(e)}")
            return False
    
    def test_7_simulate_negative_shock(self):
        """Test 7: POST /api/cld/{decision_id}/simulate - Negative shock simulation"""
        try:
            payload = {
                "shock_factor_id": "rf2",
                "shock_delta": -15,
                "time_steps": 3,
                "dampening": 0.8
            }
            
            response = requests.post(f"{BASE_URL}/cld/{self.decision_id}/simulate", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ['timeline', 'final_values', 'total_impact', 'stability', 'baseline']
                missing_fields = [field for field in required_fields if field not in data]
                
                if not missing_fields:
                    self.log_result(7, "CLD Negative Shock Simulation", True, f"All required fields present: {required_fields}")
                    return True
                else:
                    self.log_result(7, "CLD Negative Shock Simulation", False, f"Missing fields: {missing_fields}")
                    return False
            else:
                self.log_result(7, "CLD Negative Shock Simulation", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(7, "CLD Negative Shock Simulation", False, f"Exception: {str(e)}")
            return False
    
    def test_8_create_solution(self):
        """Test 8: POST /api/solutions-store/solutions - Create solution"""
        try:
            payload = {
                "name": "Test Solution",
                "description": "UAT test solution",
                "type": "SERVICE",  # Required field: PRODUCT, SERVICE, EVENT, PROJECT, PERSON_CONTACT
                "category": "Career",
                "visibility": "private"
            }
            
            response = requests.post(f"{BASE_URL}/solutions-store/solutions", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                solution_id = data.get('solution_id') or data.get('id')
                if solution_id:
                    self.log_result(8, "Create Solution", True, f"Solution created with ID: {solution_id}")
                    return True
                else:
                    self.log_result(8, "Create Solution", True, "Solution created successfully")
                    return True
            else:
                self.log_result(8, "Create Solution", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(8, "Create Solution", False, f"Exception: {str(e)}")
            return False
    
    def test_9_list_solutions(self):
        """Test 9: GET /api/solutions-store/solutions - List solutions"""
        try:
            response = requests.get(f"{BASE_URL}/solutions-store/solutions", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    solution_count = len(data)
                    self.log_result(9, "List Solutions", True, f"Retrieved {solution_count} solutions")
                    return True
                else:
                    self.log_result(9, "List Solutions", False, f"Expected list, got: {type(data)}")
                    return False
            else:
                self.log_result(9, "List Solutions", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(9, "List Solutions", False, f"Exception: {str(e)}")
            return False
    
    def test_10_get_wallet_initial(self):
        """Test 10: GET /api/payments/wallet - Note initial credits"""
        try:
            response = requests.get(f"{BASE_URL}/payments/wallet", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                initial_credits = data.get('credits', 0)
                self.initial_credits = initial_credits
                self.log_result(10, "Get Initial Wallet Credits", True, f"Initial credits: {initial_credits}")
                return True
            else:
                self.log_result(10, "Get Initial Wallet Credits", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(10, "Get Initial Wallet Credits", False, f"Exception: {str(e)}")
            return False
    
    def test_11_free_simulation(self):
        """Test 11: POST /api/cld/{decision_id}/simulate - Free simulation (0 credits)"""
        try:
            payload = {
                "shock_factor_id": "rf1",
                "shock_delta": 10,
                "time_steps": 2,
                "dampening": 0.7
            }
            
            response = requests.post(f"{BASE_URL}/cld/{self.decision_id}/simulate", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ['timeline', 'final_values', 'total_impact', 'stability', 'baseline']
                missing_fields = [field for field in required_fields if field not in data]
                
                if not missing_fields:
                    self.log_result(11, "Free CLD Simulation", True, "Simulation succeeded (should be free)")
                    return True
                else:
                    self.log_result(11, "Free CLD Simulation", False, f"Missing fields: {missing_fields}")
                    return False
            else:
                self.log_result(11, "Free CLD Simulation", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(11, "Free CLD Simulation", False, f"Exception: {str(e)}")
            return False
    
    def test_12_verify_credits_unchanged(self):
        """Test 12: GET /api/payments/wallet - Verify credits unchanged"""
        try:
            response = requests.get(f"{BASE_URL}/payments/wallet", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                current_credits = data.get('credits', 0)
                
                if hasattr(self, 'initial_credits') and current_credits == self.initial_credits:
                    self.log_result(12, "Verify Credits Unchanged", True, f"Credits remain at {current_credits} (simulation was free)")
                    return True
                else:
                    initial = getattr(self, 'initial_credits', 'unknown')
                    self.log_result(12, "Verify Credits Unchanged", False, f"Credits changed from {initial} to {current_credits}")
                    return False
            else:
                self.log_result(12, "Verify Credits Unchanged", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(12, "Verify Credits Unchanged", False, f"Exception: {str(e)}")
            return False
    
    def test_13_layout_force(self):
        """Test 13: POST /api/cld/{decision_id}/layout - Force layout"""
        try:
            payload = {"layout_type": "force"}
            
            response = requests.post(f"{BASE_URL}/cld/{self.decision_id}/layout", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                if 'nodes' in data or 'layout_type' in data:
                    self.log_result(13, "Force Layout Computation", True, "Layout computed successfully")
                    return True
                else:
                    self.log_result(13, "Force Layout Computation", False, f"Unexpected response format: {data}")
                    return False
            else:
                self.log_result(13, "Force Layout Computation", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(13, "Force Layout Computation", False, f"Exception: {str(e)}")
            return False
    
    def test_14_layout_hierarchical(self):
        """Test 14: POST /api/cld/{decision_id}/layout - Hierarchical layout"""
        try:
            payload = {"layout_type": "hierarchical"}
            
            response = requests.post(f"{BASE_URL}/cld/{self.decision_id}/layout", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                if 'nodes' in data or 'layout_type' in data:
                    self.log_result(14, "Hierarchical Layout Computation", True, "Layout computed successfully")
                    return True
                else:
                    self.log_result(14, "Hierarchical Layout Computation", False, f"Unexpected response format: {data}")
                    return False
            else:
                self.log_result(14, "Hierarchical Layout Computation", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(14, "Hierarchical Layout Computation", False, f"Exception: {str(e)}")
            return False
    
    def test_15_verify_updated_layout(self):
        """Test 15: GET /api/cld/{decision_id} - Verify updated layout"""
        try:
            response = requests.get(f"{BASE_URL}/cld/{self.decision_id}", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                # Handle both direct nodes format and wrapped cld format
                if data and ('nodes' in data or ('cld' in data and 'nodes' in data['cld'])):
                    if 'cld' in data:
                        nodes = data['cld']['nodes']
                    else:
                        nodes = data['nodes']
                    
                    if len(nodes) > 0:
                        self.log_result(15, "Verify Updated Layout", True, f"CLD retrieved with {len(nodes)} nodes")
                        return True
                    else:
                        self.log_result(15, "Verify Updated Layout", False, "No nodes in CLD")
                        return False
                else:
                    self.log_result(15, "Verify Updated Layout", False, f"Unexpected response format: {data}")
                    return False
            else:
                self.log_result(15, "Verify Updated Layout", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(15, "Verify Updated Layout", False, f"Exception: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        print("=" * 80)
        print("BACKEND RE-TESTING: CLD Simulation, Solutions Store, Credit Deduction")
        print("=" * 80)
        print(f"Backend URL: {BASE_URL}")
        print(f"Test started at: {datetime.now()}")
        print()
        
        # Setup tests
        if not self.test_1_register_user():
            print("❌ CRITICAL: User registration failed. Cannot proceed with other tests.")
            return
        
        if not self.test_3_create_decision():
            print("❌ CRITICAL: Decision creation failed. Cannot proceed with CLD tests.")
            return
        
        if not self.test_4_add_factors():
            print("❌ CRITICAL: Factor addition failed. Cannot proceed with CLD tests.")
            return
        
        # CLD Simulation Tests (Previously Failed)
        print("\n🎯 TESTING CLD SIMULATION (Previously Failed with KeyError)")
        self.test_5_save_cld()
        self.test_6_simulate_positive_shock()
        self.test_7_simulate_negative_shock()
        
        # Solutions Store Tests (Previously Timed Out)
        print("\n🎯 TESTING SOLUTIONS STORE (Previously Timed Out)")
        self.test_8_create_solution()
        self.test_9_list_solutions()
        
        # Credit Deduction Verification
        print("\n🎯 TESTING CREDIT DEDUCTION VERIFICATION")
        self.test_10_get_wallet_initial()
        self.test_11_free_simulation()
        self.test_12_verify_credits_unchanged()
        
        # Layout Computation Tests
        print("\n🎯 TESTING LAYOUT COMPUTATION")
        self.test_13_layout_force()
        self.test_14_layout_hierarchical()
        self.test_15_verify_updated_layout()
        
        # Summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        
        passed = sum(1 for result in self.test_results if result['success'])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        print("\nDETAILED RESULTS:")
        for result in self.test_results:
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"  Test {result['test_num']}: {result['test_name']} - {status}")
            if result['details']:
                print(f"    Details: {result['details']}")
        
        # Categorize results by test area
        cld_tests = [r for r in self.test_results if r['test_num'] in [5, 6, 7, 13, 14, 15]]
        solutions_tests = [r for r in self.test_results if r['test_num'] in [8, 9]]
        credit_tests = [r for r in self.test_results if r['test_num'] in [10, 11, 12]]
        
        print(f"\n📊 RESULTS BY CATEGORY:")
        print(f"  CLD Simulation & Layout: {sum(1 for r in cld_tests if r['success'])}/{len(cld_tests)} passed")
        print(f"  Solutions Store: {sum(1 for r in solutions_tests if r['success'])}/{len(solutions_tests)} passed")
        print(f"  Credit Deduction: {sum(1 for r in credit_tests if r['success'])}/{len(credit_tests)} passed")

if __name__ == "__main__":
    tester = BackendTester()
    tester.run_all_tests()