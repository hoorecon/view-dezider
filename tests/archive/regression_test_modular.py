#!/usr/bin/env python3
"""
Regression Test for Modular Endpoints - View Dezider
Testing endpoints after server.py refactoring into modular route files (routes/tools.py, routes/admin.py)
"""

import requests
import json
import time
from datetime import datetime

# Backend URL from review request
BACKEND_URL = "https://modal-responsive-fix.preview.emergentagent.com/api"

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
        print(f"\n=== REGRESSION TEST SUMMARY ===")
        print(f"Total Tests: {total}")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"Success Rate: {(self.passed/total*100):.1f}%" if total > 0 else "No tests run")
        
        if self.failed > 0:
            print(f"\n=== FAILED TESTS ===")
            for result in self.results:
                if not result["passed"]:
                    print(f"❌ {result['test']}: {result['details']}")

def test_modular_endpoints():
    """Test specific endpoints that were refactored into modular route files"""
    results = TestResults()
    
    # Test data
    timestamp = int(time.time())
    test_user_email = f"regression.test.{timestamp}@dezider.com"
    test_user_password = "RegressionTest123!"
    test_user_name = "Regression Test User"
    
    user_token = None
    solution_finder_id = None
    solution_matrix_id = None
    
    print("🔄 Starting REGRESSION TEST for Modular Endpoints")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test User: {test_user_email}")
    print("=" * 60)
    
    # ===== 1. HEALTH CHECK =====
    print("\n💓 HEALTH CHECK")
    
    try:
        response = requests.get(f"{BACKEND_URL}/health")
        if response.status_code == 200:
            health_data = response.json()
            if "status" in health_data and health_data["status"] == "healthy":
                results.add_result("GET /api/health", True, f"Server healthy: {health_data}")
            else:
                results.add_result("GET /api/health", False, f"Unexpected health response: {health_data}")
        else:
            results.add_result("GET /api/health", False, f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        results.add_result("GET /api/health", False, f"Exception: {str(e)}")
    
    # ===== 2. USER REGISTRATION =====
    print("\n👤 USER REGISTRATION")
    
    try:
        response = requests.post(f"{BACKEND_URL}/auth/register", json={
            "email": test_user_email,
            "password": test_user_password,
            "name": test_user_name
        })
        if response.status_code in [200, 201]:
            user_data = response.json()
            user_token = user_data.get("session_token")
            results.add_result("POST /api/auth/register", True, f"User registered: {user_data.get('user_id')}")
        else:
            results.add_result("POST /api/auth/register", False, f"Status: {response.status_code}, Response: {response.text}")
            return results  # Can't continue without auth
    except Exception as e:
        results.add_result("POST /api/auth/register", False, f"Exception: {str(e)}")
        return results
    
    # ===== 3. FEATURE FLAGS (PUBLIC) =====
    print("\n🏁 FEATURE FLAGS")
    
    try:
        response = requests.get(f"{BACKEND_URL}/feature-flags/public")
        if response.status_code == 200:
            flags = response.json()
            if "solution_finder" in flags and "solution_matrix" in flags:
                results.add_result("GET /api/feature-flags/public", True, 
                                 f"Flags: solution_finder={flags['solution_finder']}, solution_matrix={flags['solution_matrix']}")
            else:
                results.add_result("GET /api/feature-flags/public", False, 
                                 f"Missing required flags: {flags}")
        else:
            results.add_result("GET /api/feature-flags/public", False, 
                             f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        results.add_result("GET /api/feature-flags/public", False, f"Exception: {str(e)}")
    
    # ===== 4. FEATURE FLAGS (AUTHENTICATED) =====
    try:
        response = requests.get(f"{BACKEND_URL}/feature-flags",
                              headers={"Authorization": f"Bearer {user_token}"})
        if response.status_code == 200:
            flags = response.json()
            if "solution_finder" in flags and "solution_matrix" in flags:
                results.add_result("GET /api/feature-flags", True, 
                                 f"Auth flags: solution_finder={flags['solution_finder']}, solution_matrix={flags['solution_matrix']}")
            else:
                results.add_result("GET /api/feature-flags", False, 
                                 f"Missing required flags: {flags}")
        else:
            results.add_result("GET /api/feature-flags", False, 
                             f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        results.add_result("GET /api/feature-flags", False, f"Exception: {str(e)}")
    
    # ===== 5. SOLUTION FINDER CREATE =====
    print("\n🔍 SOLUTION FINDER OPERATIONS")
    
    solution_finder_data = {
        "area_of_life": "career",
        "smart_goal": "Test goal for regression testing"
    }
    
    try:
        response = requests.post(f"{BACKEND_URL}/solution-finders",
                               headers={"Authorization": f"Bearer {user_token}"},
                               json=solution_finder_data)
        if response.status_code in [200, 201]:
            created_entry = response.json()
            solution_finder_id = created_entry.get("entry_id")
            results.add_result("POST /api/solution-finders", True, 
                             f"Created entry ID: {solution_finder_id}")
        else:
            results.add_result("POST /api/solution-finders", False, 
                             f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        results.add_result("POST /api/solution-finders", False, f"Exception: {str(e)}")
    
    # ===== 6. SOLUTION FINDER LIST =====
    try:
        response = requests.get(f"{BACKEND_URL}/solution-finders",
                              headers={"Authorization": f"Bearer {user_token}"})
        if response.status_code == 200:
            entries = response.json()
            if isinstance(entries, list) and len(entries) >= 1:
                results.add_result("GET /api/solution-finders", True, 
                                 f"Retrieved {len(entries)} entries")
            else:
                results.add_result("GET /api/solution-finders", False, 
                                 f"Expected list with entries, got: {entries}")
        else:
            results.add_result("GET /api/solution-finders", False, 
                             f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        results.add_result("GET /api/solution-finders", False, f"Exception: {str(e)}")
    
    # ===== 7. SOLUTION FINDER DELETE =====
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
    
    # ===== 8. SOLUTION MATRIX CREATE =====
    print("\n🔬 SOLUTION MATRIX OPERATIONS")
    
    solution_matrix_data = {
        "area_of_life": "finance",
        "smart_goal": "Test matrix for regression testing"
    }
    
    try:
        response = requests.post(f"{BACKEND_URL}/solution-matrices",
                               headers={"Authorization": f"Bearer {user_token}"},
                               json=solution_matrix_data)
        if response.status_code in [200, 201]:
            created_matrix = response.json()
            solution_matrix_id = created_matrix.get("entry_id")
            results.add_result("POST /api/solution-matrices", True, 
                             f"Created matrix ID: {solution_matrix_id}")
        else:
            results.add_result("POST /api/solution-matrices", False, 
                             f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        results.add_result("POST /api/solution-matrices", False, f"Exception: {str(e)}")
    
    # ===== 9. SOLUTION MATRIX LIST =====
    try:
        response = requests.get(f"{BACKEND_URL}/solution-matrices",
                              headers={"Authorization": f"Bearer {user_token}"})
        if response.status_code == 200:
            matrices = response.json()
            if isinstance(matrices, list) and len(matrices) >= 1:
                results.add_result("GET /api/solution-matrices", True, 
                                 f"Retrieved {len(matrices)} matrices")
            else:
                results.add_result("GET /api/solution-matrices", False, 
                                 f"Expected list with matrices, got: {matrices}")
        else:
            results.add_result("GET /api/solution-matrices", False, 
                             f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        results.add_result("GET /api/solution-matrices", False, f"Exception: {str(e)}")
    
    # ===== 10. SOLUTION MATRIX DELETE =====
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
    
    # ===== 11. ADMIN CALL CONFIG =====
    print("\n📞 ADMIN CALL CONFIG")
    
    try:
        response = requests.get(f"{BACKEND_URL}/admin/call-config")
        if response.status_code == 200:
            config = response.json()
            required_fields = ["default_duration", "min_duration", "max_duration"]
            if all(field in config for field in required_fields):
                results.add_result("GET /api/admin/call-config", True, 
                                 f"Config: default={config['default_duration']}, min={config['min_duration']}, max={config['max_duration']}")
            else:
                results.add_result("GET /api/admin/call-config", False, 
                                 f"Missing required fields in config: {config}")
        else:
            results.add_result("GET /api/admin/call-config", False, 
                             f"Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        results.add_result("GET /api/admin/call-config", False, f"Exception: {str(e)}")
    
    return results

if __name__ == "__main__":
    results = test_modular_endpoints()
    results.summary()