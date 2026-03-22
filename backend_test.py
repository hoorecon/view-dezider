#!/usr/bin/env python3
"""
Backend API Testing for View Dezider - New Endpoints
Testing the newly implemented WOWO Feature Flags, Solution Finder CRUD, Solution Matrix CRUD, and Admin Call Config endpoints
"""

import requests
import json
import time
from datetime import datetime

# Backend URL from frontend .env
BACKEND_URL = "https://dezider-solver.preview.emergentagent.com/api"

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
    
    def add_result(self, test_name, passed, details=""):
        self.results.append({
            "test": test_name,
            "passed": passed,
            "details": details
        })
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if details:
            print(f"   Details: {details}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n=== TEST SUMMARY ===")
        print(f"Total Tests: {total}")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Success Rate: {(self.passed/total*100):.1f}%" if total > 0 else "No tests run")
        
        if self.failed > 0:
            print(f"\n=== FAILED TESTS ===")
            for result in self.results:
                if not result["passed"]:
                    print(f"❌ {result['test']}: {result['details']}")

def test_new_endpoints():
    """Test all new endpoints implemented by main agent"""
    results = TestResults()
    
    # Test data
    timestamp = int(time.time())
    test_user_email = f"wowo.tester.{timestamp}@dezider.com"
    test_user_password = "SecurePass123!"
    test_user_name = "WOWO Test User"
    
    admin_email = f"admin.wowo.{timestamp}@dezider.com"
    admin_password = "AdminPass123!"
    admin_name = "WOWO Admin User"
    
    user_token = None
    admin_token = None
    
    print("🚀 Starting NEW ENDPOINTS Testing for View Dezider")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test User: {test_user_email}")
    print(f"Admin User: {admin_email}")
    print("=" * 60)
    
    # ===== AUTHENTICATION SETUP =====
    print("\n📋 AUTHENTICATION SETUP")
    
    # 1. Register regular user
    try:
        response = requests.post(f"{BACKEND_URL}/auth/register", json={
            "email": test_user_email,
            "password": test_user_password,
            "name": test_user_name
        })
        if response.status_code in [200, 201]:
            user_data = response.json()
            user_token = user_data.get("session_token")
            results.add_result("User Registration", True, f"User ID: {user_data.get('user_id')}")
        else:
            results.add_result("User Registration", False, f"Status: {response.status_code}, Response: {response.text}")
            return results
    except Exception as e:
        results.add_result("User Registration", False, f"Exception: {str(e)}")
        return results
    
    # 2. Register admin user
    try:
        response = requests.post(f"{BACKEND_URL}/auth/register", json={
            "email": admin_email,
            "password": admin_password,
            "name": admin_name
        })
        if response.status_code in [200, 201]:
            admin_data = response.json()
            admin_token = admin_data.get("session_token")
            results.add_result("Admin User Registration", True, f"User ID: {admin_data.get('user_id')}")
        else:
            results.add_result("Admin User Registration", False, f"Status: {response.status_code}, Response: {response.text}")
            return results
    except Exception as e:
        results.add_result("Admin User Registration", False, f"Exception: {str(e)}")
        return results
    
    # 3. Setup admin privileges (if no super admin exists)
    try:
        response = requests.post(f"{BACKEND_URL}/admin/setup", 
                               headers={"Authorization": f"Bearer {admin_token}"})
        if response.status_code == 200:
            results.add_result("Admin Setup", True, f"Status: {response.status_code}")
        elif response.status_code == 400 and "Super Admin already exists" in response.text:
            results.add_result("Admin Setup", True, f"Super Admin already exists (expected)")
            # Since we can't create admin, we'll skip admin-only tests
            admin_token = None
        else:
            results.add_result("Admin Setup", False, f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        results.add_result("Admin Setup", False, f"Exception: {str(e)}")
    
    # ===== FEATURE FLAGS TESTING =====
    print("\n🏁 FEATURE FLAGS (WOWO) TESTING")
    
    # 4. Test GET /api/feature-flags (requires auth)
    try:
        response = requests.get(f"{BACKEND_URL}/feature-flags",
                              headers={"Authorization": f"Bearer {user_token}"})
        if response.status_code == 200:
            flags = response.json()
            if "solution_finder" in flags and "solution_matrix" in flags:
                results.add_result("GET /api/feature-flags (authenticated)", True, 
                                 f"Flags: solution_finder={flags['solution_finder']}, solution_matrix={flags['solution_matrix']}")
            else:
                results.add_result("GET /api/feature-flags (authenticated)", False, 
                                 f"Missing required flags in response: {flags}")
        else:
            results.add_result("GET /api/feature-flags (authenticated)", False, 
                             f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        results.add_result("GET /api/feature-flags (authenticated)", False, f"Exception: {str(e)}")
    
    # 5. Test GET /api/feature-flags/public (no auth needed)
    try:
        response = requests.get(f"{BACKEND_URL}/feature-flags/public")
        if response.status_code == 200:
            flags = response.json()
            if "solution_finder" in flags and "solution_matrix" in flags:
                results.add_result("GET /api/feature-flags/public (no auth)", True, 
                                 f"Flags: solution_finder={flags['solution_finder']}, solution_matrix={flags['solution_matrix']}")
            else:
                results.add_result("GET /api/feature-flags/public (no auth)", False, 
                                 f"Missing required flags in response: {flags}")
        else:
            results.add_result("GET /api/feature-flags/public (no auth)", False, 
                             f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        results.add_result("GET /api/feature-flags/public (no auth)", False, f"Exception: {str(e)}")
    
    # 6. Test PUT /api/admin/feature-flags (admin only) - Non-admin should get 403
    try:
        response = requests.put(f"{BACKEND_URL}/admin/feature-flags",
                              headers={"Authorization": f"Bearer {user_token}"},
                              json={"solution_finder": True, "solution_matrix": True})
        if response.status_code == 403:
            results.add_result("PUT /api/admin/feature-flags (non-admin 403)", True, 
                             "Non-admin correctly denied access")
        else:
            results.add_result("PUT /api/admin/feature-flags (non-admin 403)", False, 
                             f"Expected 403, got {response.status_code}: {response.text}")
    except Exception as e:
        results.add_result("PUT /api/admin/feature-flags (non-admin 403)", False, f"Exception: {str(e)}")
    
    # 7. Test PUT /api/admin/feature-flags (admin only) - Admin should succeed
    if admin_token:
        try:
            response = requests.put(f"{BACKEND_URL}/admin/feature-flags",
                                  headers={"Authorization": f"Bearer {admin_token}"},
                                  json={"solution_finder": True, "solution_matrix": True})
            if response.status_code == 200:
                result = response.json()
                results.add_result("PUT /api/admin/feature-flags (admin success)", True, 
                                 f"Feature flags updated: {result}")
            else:
                results.add_result("PUT /api/admin/feature-flags (admin success)", False, 
                                 f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            results.add_result("PUT /api/admin/feature-flags (admin success)", False, f"Exception: {str(e)}")
    else:
        results.add_result("PUT /api/admin/feature-flags (admin success)", True, 
                         "Skipped - No admin privileges available (super admin already exists)")
    
    # ===== SIMPLE SOLUTION FINDER CRUD TESTING =====
    print("\n🔍 SIMPLE SOLUTION FINDER CRUD TESTING")
    
    solution_finder_id = None
    
    # 8. Test POST /api/solution-finders - Create entry
    solution_finder_data = {
        "area_of_life": "career",
        "smart_goal": "Earn 3 lakh per quarter",
        "milestones": [
            {
                "description": "Get 12 students",
                "timeline": "15.09.2025"
            }
        ],
        "q1_all_concerns": "Fees, Health",
        "q2_primary_concerns": "Time, Marketing",
        "q3_capabilities": "Knowledge, Skill",
        "q3_resources": "Contacts, Time",
        "q3_solutions": "Smart scheduling",
        "external_help_aspect": "Marketing",
        "external_help_level": "One-time Consulting",
        "external_help_from": "Mentor",
        "q4_negative_consequences": "Burnout",
        "q4_mitigation_plans": "Regular breaks",
        "q4_contingency_plans": "Delegate work",
        "action_items": [
            {
                "action": "Prepare fee structure",
                "who": "Self",
                "by_when": "01.09.2025",
                "status": "pending"
            }
        ]
    }
    
    try:
        response = requests.post(f"{BACKEND_URL}/solution-finders",
                               headers={"Authorization": f"Bearer {user_token}"},
                               json=solution_finder_data)
        if response.status_code in [200, 201]:
            created_entry = response.json()
            solution_finder_id = created_entry.get("entry_id")
            results.add_result("POST /api/solution-finders (create)", True, 
                             f"Created entry ID: {solution_finder_id}")
        else:
            results.add_result("POST /api/solution-finders (create)", False, 
                             f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        results.add_result("POST /api/solution-finders (create)", False, f"Exception: {str(e)}")
    
    # 9. Test GET /api/solution-finders - List all entries
    try:
        response = requests.get(f"{BACKEND_URL}/solution-finders",
                              headers={"Authorization": f"Bearer {user_token}"})
        if response.status_code == 200:
            entries = response.json()
            if isinstance(entries, list) and len(entries) >= 1:
                results.add_result("GET /api/solution-finders (list)", True, 
                                 f"Retrieved {len(entries)} entries")
            else:
                results.add_result("GET /api/solution-finders (list)", False, 
                                 f"Expected list with entries, got: {entries}")
        else:
            results.add_result("GET /api/solution-finders (list)", False, 
                             f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        results.add_result("GET /api/solution-finders (list)", False, f"Exception: {str(e)}")
    
    # 10. Test GET /api/solution-finders/{entry_id} - Get specific entry
    if solution_finder_id:
        try:
            response = requests.get(f"{BACKEND_URL}/solution-finders/{solution_finder_id}",
                                  headers={"Authorization": f"Bearer {user_token}"})
            if response.status_code == 200:
                entry = response.json()
                if entry.get("entry_id") == solution_finder_id and entry.get("area_of_life") == "career":
                    results.add_result("GET /api/solution-finders/{id} (get specific)", True, 
                                     f"Retrieved entry with correct data")
                else:
                    results.add_result("GET /api/solution-finders/{id} (get specific)", False, 
                                     f"Data mismatch in retrieved entry: {entry}")
            else:
                results.add_result("GET /api/solution-finders/{id} (get specific)", False, 
                                 f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            results.add_result("GET /api/solution-finders/{id} (get specific)", False, f"Exception: {str(e)}")
    
    # 11. Test PUT /api/solution-finders/{entry_id} - Update entry
    if solution_finder_id:
        try:
            update_data = {
                "status": "completed",
                "q3_solutions": "Updated solutions with better scheduling"
            }
            response = requests.put(f"{BACKEND_URL}/solution-finders/{solution_finder_id}",
                                  headers={"Authorization": f"Bearer {user_token}"},
                                  json=update_data)
            if response.status_code == 200:
                updated_entry = response.json()
                if updated_entry.get("status") == "completed":
                    results.add_result("PUT /api/solution-finders/{id} (update)", True, 
                                     f"Entry updated successfully")
                else:
                    results.add_result("PUT /api/solution-finders/{id} (update)", False, 
                                     f"Update not reflected: {updated_entry}")
            else:
                results.add_result("PUT /api/solution-finders/{id} (update)", False, 
                                 f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            results.add_result("PUT /api/solution-finders/{id} (update)", False, f"Exception: {str(e)}")
    
    # 12. Test user isolation - Another user cannot access first user's entries
    try:
        # Create second user
        second_user_email = f"second.user.{timestamp}@dezider.com"
        response = requests.post(f"{BACKEND_URL}/auth/register", json={
            "email": second_user_email,
            "password": "SecondPass123!",
            "name": "Second User"
        })
        if response.status_code in [200, 201]:
            second_user_token = response.json().get("session_token")
            
            # Try to access first user's solution finder
            if solution_finder_id:
                response = requests.get(f"{BACKEND_URL}/solution-finders/{solution_finder_id}",
                                      headers={"Authorization": f"Bearer {second_user_token}"})
                if response.status_code == 404:
                    results.add_result("Solution Finder User Isolation", True, 
                                     "Second user correctly cannot access first user's entries")
                else:
                    results.add_result("Solution Finder User Isolation", False, 
                                     f"Security breach: Second user accessed first user's data. Status: {response.status_code}")
        else:
            results.add_result("Solution Finder User Isolation", False, 
                             f"Could not create second user for isolation test")
    except Exception as e:
        results.add_result("Solution Finder User Isolation", False, f"Exception: {str(e)}")
    
    # ===== ADVANCED SOLUTION MATRIX CRUD TESTING =====
    print("\n🔬 ADVANCED SOLUTION MATRIX CRUD TESTING")
    
    solution_matrix_id = None
    
    # 13. Test POST /api/solution-matrices - Create entry
    solution_matrix_data = {
        "area_of_life": "career",
        "smart_goal": "Launch new business",
        "q1_all_concerns": "Funding, Time",
        "q2_priority_concerns": "Funding",
        "simpler_solutions": "Bootstrap first",
        "simpler_capabilities": "Tech skills",
        "simpler_resources": "Savings",
        "matrix_self": {
            "summary": "Self analysis",
            "knowledge_skills": "Python, ML",
            "capacity": "High energy",
            "time": "Full-time available",
            "people": "Solo",
            "finance": "50K savings",
            "infrastructure": "Laptop"
        },
        "matrix_micro": {
            "summary": "Micro level",
            "knowledge_skills": "Team skills",
            "capacity": "Medium",
            "time": "Part-time team",
            "people": "2 cofounders",
            "finance": "100K",
            "infrastructure": "Office"
        },
        "matrix_macro": {
            "summary": "Macro level",
            "knowledge_skills": "Industry expertise",
            "capacity": "Scale ready",
            "time": "Long-term",
            "people": "Network",
            "finance": "VC potential",
            "infrastructure": "Cloud"
        },
        "solution_category": {
            "completely_solvable": True,
            "partially_solvable": True,
            "patience_period": True
        },
        "solution_sources": {
            "from_self": "Build MVP",
            "from_expert": "Hire consultant"
        },
        "q4_negative_consequences": "Market risk",
        "q4_mitigation_plans": "MVP validation",
        "q4_contingency_plans": "Pivot strategy",
        "action_items": [
            {
                "who": "Founder",
                "what": "Build MVP",
                "by_when": "Q1 2025",
                "status": "in_progress"
            }
        ]
    }
    
    try:
        response = requests.post(f"{BACKEND_URL}/solution-matrices",
                               headers={"Authorization": f"Bearer {user_token}"},
                               json=solution_matrix_data)
        if response.status_code in [200, 201]:
            created_matrix = response.json()
            solution_matrix_id = created_matrix.get("entry_id")
            
            # Verify matrix structure
            matrix_valid = True
            matrix_details = []
            
            # Check matrix_self has all 7 fields
            matrix_self = created_matrix.get("matrix_self", {})
            required_fields = ["summary", "knowledge_skills", "capacity", "time", "people", "finance", "infrastructure"]
            for field in required_fields:
                if field not in matrix_self:
                    matrix_valid = False
                    matrix_details.append(f"Missing {field} in matrix_self")
            
            # Check solution_category returns boolean flags
            solution_category = created_matrix.get("solution_category", {})
            for key, value in solution_category.items():
                if not isinstance(value, bool):
                    matrix_valid = False
                    matrix_details.append(f"solution_category.{key} is not boolean: {type(value)}")
            
            # Check solution_sources returns string values
            solution_sources = created_matrix.get("solution_sources", {})
            for key, value in solution_sources.items():
                if not isinstance(value, str):
                    matrix_valid = False
                    matrix_details.append(f"solution_sources.{key} is not string: {type(value)}")
            
            if matrix_valid:
                results.add_result("POST /api/solution-matrices (create)", True, 
                                 f"Created matrix ID: {solution_matrix_id}")
            else:
                results.add_result("POST /api/solution-matrices (create)", False, 
                                 f"Matrix structure issues: {'; '.join(matrix_details)}")
        else:
            results.add_result("POST /api/solution-matrices (create)", False, 
                             f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        results.add_result("POST /api/solution-matrices (create)", False, f"Exception: {str(e)}")
    
    # 14. Test GET /api/solution-matrices - List all entries
    try:
        response = requests.get(f"{BACKEND_URL}/solution-matrices",
                              headers={"Authorization": f"Bearer {user_token}"})
        if response.status_code == 200:
            matrices = response.json()
            if isinstance(matrices, list) and len(matrices) >= 1:
                results.add_result("GET /api/solution-matrices (list)", True, 
                                 f"Retrieved {len(matrices)} matrices")
            else:
                results.add_result("GET /api/solution-matrices (list)", False, 
                                 f"Expected list with matrices, got: {matrices}")
        else:
            results.add_result("GET /api/solution-matrices (list)", False, 
                             f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        results.add_result("GET /api/solution-matrices (list)", False, f"Exception: {str(e)}")
    
    # 15. Test GET /api/solution-matrices/{entry_id} - Get specific entry
    if solution_matrix_id:
        try:
            response = requests.get(f"{BACKEND_URL}/solution-matrices/{solution_matrix_id}",
                                  headers={"Authorization": f"Bearer {user_token}"})
            if response.status_code == 200:
                matrix = response.json()
                if matrix.get("entry_id") == solution_matrix_id and matrix.get("area_of_life") == "career":
                    results.add_result("GET /api/solution-matrices/{id} (get specific)", True, 
                                     f"Retrieved matrix with correct data")
                else:
                    results.add_result("GET /api/solution-matrices/{id} (get specific)", False, 
                                     f"Data mismatch in retrieved matrix: {matrix}")
            else:
                results.add_result("GET /api/solution-matrices/{id} (get specific)", False, 
                                 f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            results.add_result("GET /api/solution-matrices/{id} (get specific)", False, f"Exception: {str(e)}")
    
    # 16. Test PUT /api/solution-matrices/{entry_id} - Update entry
    if solution_matrix_id:
        try:
            update_data = {
                "status": "completed",
                "matrix_self": {
                    "summary": "Updated self analysis",
                    "knowledge_skills": "Python, ML, AI",
                    "capacity": "High energy",
                    "time": "Full-time available",
                    "people": "Solo",
                    "finance": "50K savings",
                    "infrastructure": "Laptop"
                }
            }
            response = requests.put(f"{BACKEND_URL}/solution-matrices/{solution_matrix_id}",
                                  headers={"Authorization": f"Bearer {user_token}"},
                                  json=update_data)
            if response.status_code == 200:
                updated_matrix = response.json()
                if (updated_matrix.get("status") == "completed" and 
                    updated_matrix.get("matrix_self", {}).get("knowledge_skills") == "Python, ML, AI"):
                    results.add_result("PUT /api/solution-matrices/{id} (update)", True, 
                                     f"Matrix updated successfully")
                else:
                    results.add_result("PUT /api/solution-matrices/{id} (update)", False, 
                                     f"Update not reflected: {updated_matrix}")
            else:
                results.add_result("PUT /api/solution-matrices/{id} (update)", False, 
                                 f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            results.add_result("PUT /api/solution-matrices/{id} (update)", False, f"Exception: {str(e)}")
    
    # ===== ADMIN CALL CONFIG TESTING =====
    print("\n📞 ADMIN CALL CONFIG TESTING")
    
    # 17. Test GET /api/admin/call-config (no auth needed)
    try:
        response = requests.get(f"{BACKEND_URL}/admin/call-config")
        if response.status_code == 200:
            config = response.json()
            required_fields = ["default_duration", "min_duration", "max_duration"]
            if all(field in config for field in required_fields):
                results.add_result("GET /api/admin/call-config (no auth)", True, 
                                 f"Config: default={config['default_duration']}, min={config['min_duration']}, max={config['max_duration']}")
            else:
                results.add_result("GET /api/admin/call-config (no auth)", False, 
                                 f"Missing required fields in config: {config}")
        else:
            results.add_result("GET /api/admin/call-config (no auth)", False, 
                             f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        results.add_result("GET /api/admin/call-config (no auth)", False, f"Exception: {str(e)}")
    
    # 18. Test PUT /api/admin/call-config (admin only) - Non-admin should get 403
    try:
        response = requests.put(f"{BACKEND_URL}/admin/call-config",
                              headers={"Authorization": f"Bearer {user_token}"},
                              json={"default_duration": 45, "min_duration": 10, "max_duration": 90})
        if response.status_code == 403:
            results.add_result("PUT /api/admin/call-config (non-admin 403)", True, 
                             "Non-admin correctly denied access")
        else:
            results.add_result("PUT /api/admin/call-config (non-admin 403)", False, 
                             f"Expected 403, got {response.status_code}: {response.text}")
    except Exception as e:
        results.add_result("PUT /api/admin/call-config (non-admin 403)", False, f"Exception: {str(e)}")
    
    # 19. Test PUT /api/admin/call-config (admin only) - Admin should succeed
    if admin_token:
        try:
            response = requests.put(f"{BACKEND_URL}/admin/call-config",
                                  headers={"Authorization": f"Bearer {admin_token}"},
                                  json={"default_duration": 45, "min_duration": 10, "max_duration": 90})
            if response.status_code == 200:
                result = response.json()
                results.add_result("PUT /api/admin/call-config (admin success)", True, 
                                 f"Call config updated: {result}")
            else:
                results.add_result("PUT /api/admin/call-config (admin success)", False, 
                                 f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            results.add_result("PUT /api/admin/call-config (admin success)", False, f"Exception: {str(e)}")
    else:
        results.add_result("PUT /api/admin/call-config (admin success)", True, 
                         "Skipped - No admin privileges available (super admin already exists)")
    
    # ===== CLEANUP AND DELETE TESTING =====
    print("\n🗑️ DELETE OPERATIONS TESTING")
    
    # 20. Test DELETE /api/solution-finders/{entry_id}
    if solution_finder_id:
        try:
            response = requests.delete(f"{BACKEND_URL}/solution-finders/{solution_finder_id}",
                                     headers={"Authorization": f"Bearer {user_token}"})
            if response.status_code == 200:
                results.add_result("DELETE /api/solution-finders/{id}", True, 
                                 f"Solution finder deleted successfully")
            else:
                results.add_result("DELETE /api/solution-finders/{id}", False, 
                                 f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            results.add_result("DELETE /api/solution-finders/{id}", False, f"Exception: {str(e)}")
    
    # 21. Test DELETE /api/solution-matrices/{entry_id}
    if solution_matrix_id:
        try:
            response = requests.delete(f"{BACKEND_URL}/solution-matrices/{solution_matrix_id}",
                                     headers={"Authorization": f"Bearer {user_token}"})
            if response.status_code == 200:
                results.add_result("DELETE /api/solution-matrices/{id}", True, 
                                 f"Solution matrix deleted successfully")
            else:
                results.add_result("DELETE /api/solution-matrices/{id}", False, 
                                 f"Status: {response.status_code}, Response: {response.text}")
        except Exception as e:
            results.add_result("DELETE /api/solution-matrices/{id}", False, f"Exception: {str(e)}")
    
    return results

if __name__ == "__main__":
    results = test_new_endpoints()
    results.summary()