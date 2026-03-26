#!/usr/bin/env python3
"""
Comprehensive CLD Engine Backend Testing
Tests all CLD endpoints in sequence as specified in the review request.
"""

import requests
import json
import time
from datetime import datetime

# Backend URL from environment
BACKEND_URL = "https://dezider-core.preview.emergentagent.com/api"

class CLDEngineTest:
    def __init__(self):
        self.session_token = None
        self.decision_id = None
        self.test_results = []
        
    def log_result(self, test_name, status, details=""):
        """Log test result"""
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        status_icon = "✅" if status == "PASS" else "❌"
        print(f"{status_icon} {test_name}: {details}")
        
    def make_request(self, method, endpoint, data=None, headers=None):
        """Make HTTP request with error handling"""
        url = f"{BACKEND_URL}{endpoint}"
        default_headers = {}
        if self.session_token:
            default_headers["Authorization"] = f"Bearer {self.session_token}"
        if headers:
            default_headers.update(headers)
            
        try:
            if method == "GET":
                response = requests.get(url, headers=default_headers)
            elif method == "POST":
                response = requests.post(url, json=data, headers=default_headers)
            elif method == "PUT":
                response = requests.put(url, json=data, headers=default_headers)
            elif method == "DELETE":
                response = requests.delete(url, headers=default_headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
                
            return response
        except Exception as e:
            return None
            
    def test_1_register_user(self):
        """Test 1: Register user"""
        timestamp = int(time.time())
        user_data = {
            "email": f"cldtest2@test.com",
            "password": "test123",
            "name": "CLD Tester"
        }
        
        response = self.make_request("POST", "/auth/register", user_data)
        if response and response.status_code == 200:
            data = response.json()
            self.session_token = data.get("session_token")
            self.log_result("User Registration", "PASS", f"User registered with session token")
            return True
        else:
            error = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_result("User Registration", "FAIL", f"Status: {response.status_code if response else 'None'}, Error: {error}")
            return False
            
    def test_2_create_decision(self):
        """Test 2: Create a decision"""
        decision_data = {
            "title": "Career Move Decision",
            "context": "Deciding between job offers",
            "life_area": "Career",
            "decision_type": "need"
        }
        
        response = self.make_request("POST", "/decisions", decision_data)
        if response and response.status_code == 200:
            data = response.json()
            self.decision_id = data.get("id")
            self.log_result("Decision Creation", "PASS", f"Decision created with ID: {self.decision_id}")
            return True
        else:
            error = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_result("Decision Creation", "FAIL", f"Status: {response.status_code if response else 'None'}, Error: {error}")
            return False
            
    def test_3_update_decision_with_factors(self):
        """Test 3: Update decision with factors"""
        factors_data = {
            "factors": [
                {"id": "f1", "name": "Salary", "category": "primary", "rating": 90, "order": 0},
                {"id": "f2", "name": "Work-Life Balance", "category": "primary", "rating": 80, "order": 1},
                {"id": "f3", "name": "Growth Opportunity", "category": "secondary", "rating": 70, "order": 2},
                {"id": "f4", "name": "Location", "category": "secondary", "rating": 60, "order": 3}
            ]
        }
        
        response = self.make_request("PUT", f"/decisions/{self.decision_id}", factors_data)
        if response and response.status_code == 200:
            self.log_result("Decision Update with Factors", "PASS", "4 factors added successfully")
            return True
        else:
            error = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_result("Decision Update with Factors", "FAIL", f"Status: {response.status_code if response else 'None'}, Error: {error}")
            return False
            
    def test_4_get_cld_empty(self):
        """Test 4: GET /api/cld/{decision_id} - Should return null"""
        response = self.make_request("GET", f"/cld/{self.decision_id}")
        if response and response.status_code == 200:
            data = response.json()
            if data.get("cld") is None:
                self.log_result("GET CLD (Empty)", "PASS", "Returns null as expected")
                return True
            else:
                self.log_result("GET CLD (Empty)", "FAIL", f"Expected null, got: {data.get('cld')}")
                return False
        else:
            error = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_result("GET CLD (Empty)", "FAIL", f"Status: {response.status_code if response else 'None'}, Error: {error}")
            return False
            
    def test_5_save_cld(self):
        """Test 5: POST /api/cld/{decision_id}/save - Save CLD"""
        cld_data = {
            "nodes": [
                {"factor_id": "f1", "name": "Salary", "x": 200, "y": 60, "centrality": 0.8, "classification": "primary", "priority_rank": 1, "gap_multiplier": 2.0, "base_value": 60, "locked": False},
                {"factor_id": "f2", "name": "Work-Life Balance", "x": 340, "y": 200, "centrality": 0.7, "classification": "primary", "priority_rank": 2, "gap_multiplier": 1.5, "base_value": 45, "locked": False},
                {"factor_id": "f3", "name": "Growth Opportunity", "x": 200, "y": 340, "centrality": 0.5, "classification": "secondary", "priority_rank": 3, "gap_multiplier": 1.0, "base_value": 55, "locked": False},
                {"factor_id": "f4", "name": "Location", "x": 60, "y": 200, "centrality": 0.3, "classification": "secondary", "priority_rank": 4, "gap_multiplier": 0.5, "base_value": 40, "locked": False}
            ],
            "links": [
                {"from_id": "f1", "to_id": "f2", "link_type": "balancing", "strength": 7, "delay": 0, "description": "Higher salary often means less balance"},
                {"from_id": "f3", "to_id": "f1", "link_type": "reinforcing", "strength": 8, "delay": 1, "description": "Growth leads to higher salary"},
                {"from_id": "f2", "to_id": "f3", "link_type": "reinforcing", "strength": 5, "delay": 0, "description": "Balance enables learning"},
                {"from_id": "f4", "to_id": "f2", "link_type": "reinforcing", "strength": 6, "delay": 0, "description": "Good location improves balance"}
            ],
            "loops": [
                {"name": "B1: Salary-Balance Tradeoff", "loop_type": "balancing", "factor_ids": ["f1", "f2", "f3"]}
            ],
            "layout_type": "circular"
        }
        
        response = self.make_request("POST", f"/cld/{self.decision_id}/save", cld_data)
        if response and response.status_code == 200:
            data = response.json()
            self.log_result("Save CLD", "PASS", f"CLD saved successfully: {data.get('message')}")
            return True
        else:
            error = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_result("Save CLD", "FAIL", f"Status: {response.status_code if response else 'None'}, Error: {error}")
            return False
            
    def test_6_get_cld_saved(self):
        """Test 6: GET /api/cld/{decision_id} - Should return saved CLD"""
        response = self.make_request("GET", f"/cld/{self.decision_id}")
        if response and response.status_code == 200:
            data = response.json()
            cld = data.get("cld")
            if cld and "nodes" in cld and "links" in cld and "loops" in cld:
                nodes_count = len(cld.get("nodes", []))
                links_count = len(cld.get("links", []))
                loops_count = len(cld.get("loops", []))
                self.log_result("GET CLD (Saved)", "PASS", f"CLD retrieved: {nodes_count} nodes, {links_count} links, {loops_count} loops")
                return True
            else:
                self.log_result("GET CLD (Saved)", "FAIL", f"Invalid CLD structure: {cld}")
                return False
        else:
            error = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_result("GET CLD (Saved)", "FAIL", f"Status: {response.status_code if response else 'None'}, Error: {error}")
            return False
            
    def test_7_get_cld_list(self):
        """Test 7: GET /api/cld/list - Should return list with saved CLD"""
        response = self.make_request("GET", "/cld/list")
        if response and response.status_code == 200:
            data = response.json()
            clds = data.get("clds", [])
            if len(clds) >= 1:
                self.log_result("GET CLD List", "PASS", f"Found {len(clds)} CLD(s)")
                return True
            else:
                self.log_result("GET CLD List", "FAIL", f"Expected at least 1 CLD, found {len(clds)}")
                return False
        else:
            error = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_result("GET CLD List", "FAIL", f"Status: {response.status_code if response else 'None'}, Error: {error}")
            return False
            
    def test_8_update_node(self):
        """Test 8: PUT /api/cld/{decision_id}/node/f1 - Update node"""
        node_update = {
            "base_value": 70,
            "locked": True
        }
        
        response = self.make_request("PUT", f"/cld/{self.decision_id}/node/f1", node_update)
        if response and response.status_code == 200:
            self.log_result("Update Node", "PASS", "Node f1 updated successfully")
            return True
        else:
            error = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_result("Update Node", "FAIL", f"Status: {response.status_code if response else 'None'}, Error: {error}")
            return False
            
    def test_9_update_link(self):
        """Test 9: PUT /api/cld/{decision_id}/link - Update link"""
        link_update = {
            "from_id": "f1",
            "to_id": "f2",
            "strength": 9
        }
        
        response = self.make_request("PUT", f"/cld/{self.decision_id}/link", link_update)
        if response and response.status_code == 200:
            self.log_result("Update Link", "PASS", "Link f1->f2 updated successfully")
            return True
        else:
            error = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_result("Update Link", "FAIL", f"Status: {response.status_code if response else 'None'}, Error: {error}")
            return False
            
    def test_10_simulate_positive_shock(self):
        """Test 10: POST /api/cld/{decision_id}/simulate - Positive shock"""
        simulation_data = {
            "shock_factor_id": "f3",
            "shock_delta": 25,
            "time_steps": 5,
            "dampening": 0.7
        }
        
        response = self.make_request("POST", f"/cld/{self.decision_id}/simulate", simulation_data)
        if response and response.status_code == 200:
            data = response.json()
            required_fields = ["timeline", "final_values", "total_impact", "stability", "most_affected", "baseline"]
            if all(field in data for field in required_fields):
                timeline_steps = len(data.get("timeline", []))
                stability = data.get("stability")
                self.log_result("Simulate Positive Shock", "PASS", f"Simulation completed: {timeline_steps} steps, stability: {stability}")
                return True
            else:
                missing = [f for f in required_fields if f not in data]
                self.log_result("Simulate Positive Shock", "FAIL", f"Missing fields: {missing}")
                return False
        else:
            error = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_result("Simulate Positive Shock", "FAIL", f"Status: {response.status_code if response else 'None'}, Error: {error}")
            return False
            
    def test_11_simulate_negative_shock(self):
        """Test 11: POST /api/cld/{decision_id}/simulate - Negative shock"""
        simulation_data = {
            "shock_factor_id": "f1",
            "shock_delta": -20,
            "time_steps": 8,
            "dampening": 0.5
        }
        
        response = self.make_request("POST", f"/cld/{self.decision_id}/simulate", simulation_data)
        if response and response.status_code == 200:
            data = response.json()
            timeline_steps = len(data.get("timeline", []))
            stability = data.get("stability")
            total_impact = data.get("total_impact", {})
            f1_impact = total_impact.get("f1", 0)
            self.log_result("Simulate Negative Shock", "PASS", f"Negative shock simulation: {timeline_steps} steps, f1 impact: {f1_impact}")
            return True
        else:
            error = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_result("Simulate Negative Shock", "FAIL", f"Status: {response.status_code if response else 'None'}, Error: {error}")
            return False
            
    def test_12_layout_force(self):
        """Test 12: POST /api/cld/{decision_id}/layout - Force layout"""
        layout_data = {
            "layout_type": "force"
        }
        
        response = self.make_request("POST", f"/cld/{self.decision_id}/layout", layout_data)
        if response and response.status_code == 200:
            data = response.json()
            nodes = data.get("nodes", [])
            layout_type = data.get("layout_type")
            if nodes and layout_type == "force":
                self.log_result("Layout Force", "PASS", f"Force layout computed for {len(nodes)} nodes")
                return True
            else:
                self.log_result("Layout Force", "FAIL", f"Invalid response: {data}")
                return False
        else:
            error = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_result("Layout Force", "FAIL", f"Status: {response.status_code if response else 'None'}, Error: {error}")
            return False
            
    def test_13_layout_hierarchical(self):
        """Test 13: POST /api/cld/{decision_id}/layout - Hierarchical layout"""
        layout_data = {
            "layout_type": "hierarchical"
        }
        
        response = self.make_request("POST", f"/cld/{self.decision_id}/layout", layout_data)
        if response and response.status_code == 200:
            data = response.json()
            nodes = data.get("nodes", [])
            layout_type = data.get("layout_type")
            if nodes and layout_type == "hierarchical":
                self.log_result("Layout Hierarchical", "PASS", f"Hierarchical layout computed for {len(nodes)} nodes")
                return True
            else:
                self.log_result("Layout Hierarchical", "FAIL", f"Invalid response: {data}")
                return False
        else:
            error = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_result("Layout Hierarchical", "FAIL", f"Status: {response.status_code if response else 'None'}, Error: {error}")
            return False
            
    def test_14_delete_cld(self):
        """Test 14: DELETE /api/cld/{decision_id} - Delete CLD"""
        response = self.make_request("DELETE", f"/cld/{self.decision_id}")
        if response and response.status_code == 200:
            self.log_result("Delete CLD", "PASS", "CLD deleted successfully")
            return True
        else:
            error = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_result("Delete CLD", "FAIL", f"Status: {response.status_code if response else 'None'}, Error: {error}")
            return False
            
    def test_15_get_cld_after_delete(self):
        """Test 15: GET /api/cld/{decision_id} - Should return null after delete"""
        response = self.make_request("GET", f"/cld/{self.decision_id}")
        if response and response.status_code == 200:
            data = response.json()
            if data.get("cld") is None:
                self.log_result("GET CLD (After Delete)", "PASS", "Returns null after deletion")
                return True
            else:
                self.log_result("GET CLD (After Delete)", "FAIL", f"Expected null, got: {data.get('cld')}")
                return False
        else:
            error = response.json().get("detail", "Unknown error") if response else "No response"
            self.log_result("GET CLD (After Delete)", "FAIL", f"Status: {response.status_code if response else 'None'}, Error: {error}")
            return False
            
    def run_all_tests(self):
        """Run all CLD Engine tests in sequence"""
        print("🚀 Starting CLD Engine Comprehensive Testing")
        print("=" * 60)
        
        tests = [
            self.test_1_register_user,
            self.test_2_create_decision,
            self.test_3_update_decision_with_factors,
            self.test_4_get_cld_empty,
            self.test_5_save_cld,
            self.test_6_get_cld_saved,
            self.test_7_get_cld_list,
            self.test_8_update_node,
            self.test_9_update_link,
            self.test_10_simulate_positive_shock,
            self.test_11_simulate_negative_shock,
            self.test_12_layout_force,
            self.test_13_layout_hierarchical,
            self.test_14_delete_cld,
            self.test_15_get_cld_after_delete
        ]
        
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                if test():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                self.log_result(test.__name__, "ERROR", f"Exception: {str(e)}")
                failed += 1
                
        print("\n" + "=" * 60)
        print(f"🎯 CLD Engine Testing Complete")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"📊 Success Rate: {(passed/(passed+failed)*100):.1f}%")
        
        return passed, failed, self.test_results

if __name__ == "__main__":
    tester = CLDEngineTest()
    passed, failed, results = tester.run_all_tests()
    
    # Print detailed results
    print("\n📋 Detailed Test Results:")
    for result in results:
        status_icon = "✅" if result["status"] == "PASS" else "❌" if result["status"] == "FAIL" else "⚠️"
        print(f"{status_icon} {result['test']}: {result['details']}")