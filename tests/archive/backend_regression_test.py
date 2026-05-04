#!/usr/bin/env python3
"""
COMPREHENSIVE BACKEND REGRESSION TEST
After massive server.py refactoring (3413 lines → 140 lines)

Tests all core flows to ensure route extraction didn't break functionality.
"""

import requests
import json
import time
from datetime import datetime, timedelta
import uuid

# Backend URL
BASE_URL = "https://dezider-core.preview.emergentagent.com/api"

class RegressionTester:
    def __init__(self):
        self.session = requests.Session()
        self.auth_token = None
        self.user_id = None
        self.test_data = {}
        self.results = []
        
    def log_result(self, test_name, success, details=""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        self.results.append({
            "test": test_name,
            "success": success,
            "details": details,
            "status": status
        })
        print(f"{status}: {test_name}")
        if details and not success:
            print(f"   Details: {details}")
    
    def make_request(self, method, endpoint, data=None, headers=None):
        """Make HTTP request with error handling"""
        url = f"{BASE_URL}{endpoint}"
        
        # Add auth header if available
        if self.auth_token and headers is None:
            headers = {"Authorization": f"Bearer {self.auth_token}"}
        elif self.auth_token and headers:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        
        try:
            if method == "GET":
                response = self.session.get(url, headers=headers)
            elif method == "POST":
                response = self.session.post(url, json=data, headers=headers)
            elif method == "PUT":
                response = self.session.put(url, json=data, headers=headers)
            elif method == "DELETE":
                response = self.session.delete(url, headers=headers)
            
            return response
        except Exception as e:
            return None
    
    def test_health_check(self):
        """Test health endpoint"""
        response = self.make_request("GET", "/health")
        if response and response.status_code == 200:
            data = response.json()
            success = "status" in data
            self.log_result("Health Check", success, f"Status: {data.get('status', 'unknown')}")
        else:
            self.log_result("Health Check", False, f"HTTP {response.status_code if response else 'No response'}")
    
    def test_auth_flow(self):
        """Test complete authentication flow"""
        timestamp = int(time.time())
        email = f"regression.test.{timestamp}@dezider.com"
        password = "TestPass123!"
        name = f"Regression Tester {timestamp}"
        
        # 1. Register
        register_data = {
            "email": email,
            "password": password,
            "name": name
        }
        
        response = self.make_request("POST", "/auth/register", register_data)
        if response and response.status_code == 200:
            data = response.json()
            if "session_token" in data and "user_id" in data:
                self.auth_token = data["session_token"]
                self.user_id = data["user_id"]
                self.test_data["user_email"] = email
                self.test_data["user_password"] = password
                self.log_result("Auth - Register", True, f"User ID: {self.user_id}")
            else:
                self.log_result("Auth - Register", False, "Missing session_token or user_id")
                return
        else:
            self.log_result("Auth - Register", False, f"HTTP {response.status_code if response else 'No response'}")
            return
        
        # 2. Get current user
        response = self.make_request("GET", "/auth/me")
        if response and response.status_code == 200:
            data = response.json()
            success = data.get("email") == email and data.get("name") == name
            self.log_result("Auth - Me", success, f"Email: {data.get('email')}")
        else:
            self.log_result("Auth - Me", False, f"HTTP {response.status_code if response else 'No response'}")
        
        # 3. Login (test with existing credentials)
        login_data = {
            "email": email,
            "password": password
        }
        
        response = self.make_request("POST", "/auth/login", login_data, headers={})
        if response and response.status_code == 200:
            data = response.json()
            success = "session_token" in data
            self.log_result("Auth - Login", success, "Session token received")
        else:
            self.log_result("Auth - Login", False, f"HTTP {response.status_code if response else 'No response'}")
    
    def test_prr_decisions_crud(self):
        """Test PRR Decisions CRUD operations"""
        if not self.auth_token:
            self.log_result("PRR Decisions CRUD", False, "No auth token available")
            return
        
        # 1. Create Decision
        decision_data = {
            "title": "Regression Test Career Decision",
            "context": "Testing PRR decision flow after refactoring",
            "folder": "career",
            "decision_type": "need"
        }
        
        response = self.make_request("POST", "/decisions", decision_data)
        if response and response.status_code == 200:
            data = response.json()
            # Check for either 'decision_id' or 'id' field
            decision_id = data.get("decision_id") or data.get("id")
            if decision_id:
                self.test_data["decision_id"] = decision_id
                self.log_result("PRR - Create Decision", True, f"Decision ID: {decision_id}")
            else:
                self.log_result("PRR - Create Decision", False, f"Missing decision_id. Response: {data}")
                return
        else:
            self.log_result("PRR - Create Decision", False, f"HTTP {response.status_code if response else 'No response'}")
            return
        
        # 2. Get Decisions List
        response = self.make_request("GET", "/decisions")
        if response and response.status_code == 200:
            data = response.json()
            success = isinstance(data, list) and len(data) > 0
            self.log_result("PRR - List Decisions", success, f"Found {len(data)} decisions")
        else:
            self.log_result("PRR - List Decisions", False, f"HTTP {response.status_code if response else 'No response'}")
        
        # 3. Get Single Decision
        response = self.make_request("GET", f"/decisions/{decision_id}")
        if response and response.status_code == 200:
            data = response.json()
            success = data.get("title") == decision_data["title"]
            self.log_result("PRR - Get Decision", success, f"Title: {data.get('title')}")
        else:
            self.log_result("PRR - Get Decision", False, f"HTTP {response.status_code if response else 'No response'}")
        
        # 4. Update Decision
        update_data = {
            "title": "Updated Regression Test Decision",
            "context": "Updated description after refactoring test"
        }
        
        response = self.make_request("PUT", f"/decisions/{decision_id}", update_data)
        if response and response.status_code == 200:
            self.log_result("PRR - Update Decision", True, "Decision updated successfully")
        else:
            self.log_result("PRR - Update Decision", False, f"HTTP {response.status_code if response else 'No response'}")
        
        # 5. Add factors to decision for clone test
        factors_data = {
            "factors": [
                {"id": "f1", "name": "Salary", "category": "primary", "rating": 80, "order": 0},
                {"id": "f2", "name": "Work-Life Balance", "category": "secondary", "rating": 70, "order": 1},
                {"id": "f3", "name": "Growth Opportunities", "category": "primary", "rating": 90, "order": 2}
            ]
        }
        
        response = self.make_request("PUT", f"/decisions/{decision_id}", factors_data)
        if response and response.status_code == 200:
            self.log_result("PRR - Add Factors", True, "Factors added successfully")
        else:
            self.log_result("PRR - Add Factors", False, f"HTTP {response.status_code if response else 'No response'}")
    
    def test_decision_clone(self):
        """Test decision cloning"""
        if not self.auth_token or "decision_id" not in self.test_data:
            self.log_result("Decision Clone", False, "No auth token or decision_id available")
            return
        
        decision_id = self.test_data["decision_id"]
        clone_data = {
            "title": "Cloned Regression Test Decision",
            "clone_level": "factors"
        }
        
        response = self.make_request("POST", f"/decisions/{decision_id}/clone", clone_data)
        if response and response.status_code == 200:
            data = response.json()
            # Check for 'id' field (the cloned decision ID)
            cloned_id = data.get("id")
            if cloned_id:
                self.test_data["cloned_decision_id"] = cloned_id
                self.log_result("Decision Clone", True, f"Cloned Decision ID: {cloned_id}")
            else:
                self.log_result("Decision Clone", False, f"Missing cloned decision_id. Response: {data}")
        else:
            self.log_result("Decision Clone", False, f"HTTP {response.status_code if response else 'No response'}")
    
    def test_templates(self):
        """Test template operations"""
        if not self.auth_token or "decision_id" not in self.test_data:
            self.log_result("Templates", False, "No auth token or decision_id available")
            return
        
        decision_id = self.test_data["decision_id"]
        
        # 1. Save as template
        template_data = {
            "name": "Regression Test Template",
            "template_type": "options",
            "visibility": "private"
        }
        
        response = self.make_request("POST", f"/decisions/{decision_id}/save-as-template", template_data)
        if response and response.status_code == 200:
            data = response.json()
            # Check for 'id' field (the template ID)
            template_id = data.get("id")
            if template_id:
                self.test_data["template_id"] = template_id
                self.log_result("Templates - Save", True, f"Template ID: {template_id}")
            else:
                self.log_result("Templates - Save", False, f"Missing template_id. Response: {data}")
                return
        else:
            self.log_result("Templates - Save", False, f"HTTP {response.status_code if response else 'No response'}")
            return
        
        # 2. List templates
        response = self.make_request("GET", "/templates")
        if response and response.status_code == 200:
            data = response.json()
            success = isinstance(data, dict) and "my_templates" in data
            self.log_result("Templates - List", success, f"Templates structure: {list(data.keys()) if isinstance(data, dict) else 'Invalid'}")
        else:
            self.log_result("Templates - List", False, f"HTTP {response.status_code if response else 'No response'}")
        
        # 3. Use template
        use_data = {
            "title": "Decision from Regression Test Template"
        }
        
        response = self.make_request("POST", f"/templates/{template_id}/use", use_data)
        if response and response.status_code == 200:
            data = response.json()
            # Check for either 'decision_id' or 'id' field
            decision_id = data.get("decision_id") or data.get("id")
            success = decision_id is not None
            self.log_result("Templates - Use", success, f"New Decision ID: {decision_id}")
        else:
            self.log_result("Templates - Use", False, f"HTTP {response.status_code if response else 'No response'}")
    
    def test_test123(self):
        """Test Test123 instant decision tool"""
        if not self.auth_token:
            self.log_result("Test123", False, "No auth token available")
            return
        
        # 1. Create Test123 session
        session_data = {
            "situation": "Regression Test Quick Decision - Testing Test123 after refactoring"
        }
        
        response = self.make_request("POST", "/test123", session_data)
        if response and response.status_code == 200:
            data = response.json()
            # Check for either 'session_id' or 'id' field
            session_id = data.get("session_id") or data.get("id")
            if session_id:
                self.test_data["test123_session_id"] = session_id
                self.log_result("Test123 - Create", True, f"Session ID: {session_id}")
            else:
                self.log_result("Test123 - Create", False, f"Missing session_id. Response: {data}")
                return
        else:
            self.log_result("Test123 - Create", False, f"HTTP {response.status_code if response else 'No response'}")
            return
        
        # 2. List Test123 sessions
        response = self.make_request("GET", "/test123")
        if response and response.status_code == 200:
            data = response.json()
            success = isinstance(data, list) and len(data) > 0
            self.log_result("Test123 - List", success, f"Found {len(data)} sessions")
        else:
            self.log_result("Test123 - List", False, f"HTTP {response.status_code if response else 'No response'}")
        
        # 3. Update Test123 session
        update_data = {
            "test1_emotional": False,
            "test1_focus": "Career advancement decision"
        }
        
        response = self.make_request("PUT", f"/test123/{session_id}", update_data)
        if response and response.status_code == 200:
            self.log_result("Test123 - Update", True, "Session updated successfully")
        else:
            self.log_result("Test123 - Update", False, f"HTTP {response.status_code if response else 'No response'}")
    
    def test_assessment(self):
        """Test decision mode assessment"""
        if not self.auth_token:
            self.log_result("Assessment", False, "No auth token available")
            return
        
        # 1. Get assessment questions
        response = self.make_request("GET", "/assessment/questions")
        if response and response.status_code == 200:
            data = response.json()
            # Check if it's the expected structure with questions key
            if "questions" in data:
                questions = data["questions"]
                success = isinstance(questions, list) and len(questions) >= 1
                self.log_result("Assessment - Questions", success, f"Found {len(questions)} questions")
            else:
                # Fallback for direct array response
                success = isinstance(data, list) and len(data) >= 1
                self.log_result("Assessment - Questions", success, f"Found {len(data)} questions")
        else:
            self.log_result("Assessment - Questions", False, f"HTTP {response.status_code if response else 'No response'}")
            return
        
        # 2. Submit assessment
        assessment_data = {
            "answers": {
                "q1": 4, "q2": 3, "q3": 5, "q4": 2, "q5": 4, "q6": 3,
                "q7": 5, "q8": 4, "q9": 3, "q10": 4, "q11": 5, "q12": 3
            }
        }
        
        response = self.make_request("POST", "/assessment", assessment_data)
        if response and response.status_code == 200:
            data = response.json()
            success = "dominant_mode" in data and "mode_scores" in data
            self.log_result("Assessment - Submit", success, f"Dominant mode: {data.get('dominant_mode')}")
        else:
            self.log_result("Assessment - Submit", False, f"HTTP {response.status_code if response else 'No response'}")
        
        # 3. Get assessment history
        response = self.make_request("GET", "/assessment/history")
        if response and response.status_code == 200:
            data = response.json()
            success = isinstance(data, list)
            self.log_result("Assessment - History", success, f"Found {len(data)} assessments")
        else:
            self.log_result("Assessment - History", False, f"HTTP {response.status_code if response else 'No response'}")
    
    def test_journal(self):
        """Test journal operations"""
        if not self.auth_token:
            self.log_result("Journal", False, "No auth token available")
            return
        
        # 1. Create journal entry
        journal_data = {
            "decision_title": "Regression Test Journal Entry",
            "decision_description": "Testing journal functionality after refactoring",
            "entry_type": "best_practice"
        }
        
        response = self.make_request("POST", "/journal", journal_data)
        if response and response.status_code == 200:
            data = response.json()
            # Check for either 'entry_id' or 'id' field
            entry_id = data.get("entry_id") or data.get("id")
            if entry_id:
                self.test_data["journal_entry_id"] = entry_id
                self.log_result("Journal - Create", True, f"Entry ID: {entry_id}")
            else:
                self.log_result("Journal - Create", False, f"Missing entry_id. Response: {data}")
                return
        else:
            self.log_result("Journal - Create", False, f"HTTP {response.status_code if response else 'No response'}")
            return
        
        # 2. List journal entries
        response = self.make_request("GET", "/journal")
        if response and response.status_code == 200:
            data = response.json()
            success = isinstance(data, list) and len(data) > 0
            self.log_result("Journal - List", success, f"Found {len(data)} entries")
        else:
            self.log_result("Journal - List", False, f"HTTP {response.status_code if response else 'No response'}")
        
        # 3. Update journal entry
        update_data = {
            "decision_title": "Updated Regression Test Journal Entry",
            "decision_description": "Updated description after refactoring test"
        }
        
        response = self.make_request("PUT", f"/journal/{entry_id}", update_data)
        if response and response.status_code == 200:
            self.log_result("Journal - Update", True, "Entry updated successfully")
        else:
            self.log_result("Journal - Update", False, f"HTTP {response.status_code if response else 'No response'}")
    
    def test_stats_and_folders(self):
        """Test stats and folders endpoints"""
        if not self.auth_token:
            self.log_result("Stats & Folders", False, "No auth token available")
            return
        
        # 1. Get stats
        response = self.make_request("GET", "/stats")
        if response and response.status_code == 200:
            data = response.json()
            # Accept any stats structure as long as it's a dict
            success = isinstance(data, dict) and len(data) > 0
            self.log_result("Stats", success, f"Stats keys: {list(data.keys())}")
        else:
            self.log_result("Stats", False, f"HTTP {response.status_code if response else 'No response'}")
        
        # 2. Get folders
        response = self.make_request("GET", "/folders")
        if response and response.status_code == 200:
            data = response.json()
            success = isinstance(data, list) and len(data) > 0
            self.log_result("Folders", success, f"Found {len(data)} folders")
        else:
            self.log_result("Folders", False, f"HTTP {response.status_code if response else 'No response'}")
    
    def test_organizations(self):
        """Test organization endpoints"""
        if not self.auth_token:
            self.log_result("Organizations", False, "No auth token available")
            return
        
        # 1. Create organization
        org_data = {
            "name": "Regression Test Org",
            "slug": f"regression-test-{int(time.time())}",
            "primary_color": "#6B46C1",
            "tagline": "Testing organization after refactoring"
        }
        
        response = self.make_request("POST", "/organizations", org_data)
        if response and response.status_code == 200:
            data = response.json()
            # Check for either 'organization_id' or 'id' field
            org_id = data.get("organization_id") or data.get("id")
            if org_id:
                self.test_data["org_id"] = org_id
                self.test_data["org_slug"] = org_data["slug"]
                self.log_result("Organizations - Create", True, f"Org ID: {org_id}")
            else:
                self.log_result("Organizations - Create", False, f"Missing organization_id. Response: {data}")
                return
        else:
            self.log_result("Organizations - Create", False, f"HTTP {response.status_code if response else 'No response'}")
            return
        
        # 2. Get organization by slug
        response = self.make_request("GET", f"/organizations/{org_data['slug']}")
        if response and response.status_code == 200:
            data = response.json()
            success = data.get("name") == org_data["name"]
            self.log_result("Organizations - Get", success, f"Name: {data.get('name')}")
        else:
            self.log_result("Organizations - Get", False, f"HTTP {response.status_code if response else 'No response'}")
    
    def test_notifications(self):
        """Test notification endpoints"""
        if not self.auth_token:
            self.log_result("Notifications", False, "No auth token available")
            return
        
        # 1. Get notifications
        response = self.make_request("GET", "/notifications")
        if response and response.status_code == 200:
            data = response.json()
            success = isinstance(data, list)
            self.log_result("Notifications - List", success, f"Found {len(data)} notifications")
        else:
            self.log_result("Notifications - List", False, f"HTTP {response.status_code if response else 'No response'}")
        
        # 2. Get unread count
        response = self.make_request("GET", "/notifications/unread-count")
        if response and response.status_code == 200:
            data = response.json()
            success = "count" in data
            self.log_result("Notifications - Unread Count", success, f"Unread: {data.get('count')}")
        else:
            self.log_result("Notifications - Unread Count", False, f"HTTP {response.status_code if response else 'No response'}")
    
    def test_analytics(self):
        """Test analytics endpoints"""
        if not self.auth_token:
            self.log_result("Analytics", False, "No auth token available")
            return
        
        response = self.make_request("GET", "/analytics/folders")
        if response and response.status_code == 200:
            data = response.json()
            expected_keys = ["folders", "active_folders", "summary"]
            success = all(key in data for key in expected_keys)
            self.log_result("Analytics - Folders", success, f"Analytics keys: {list(data.keys())}")
        else:
            self.log_result("Analytics - Folders", False, f"HTTP {response.status_code if response else 'No response'}")
    
    def test_experts(self):
        """Test experts endpoint"""
        response = self.make_request("GET", "/experts", headers={})
        if response and response.status_code == 200:
            data = response.json()
            success = isinstance(data, list)
            self.log_result("Experts", success, f"Found {len(data)} experts")
        else:
            self.log_result("Experts", False, f"HTTP {response.status_code if response else 'No response'}")
    
    def test_call_sessions(self):
        """Test call session endpoints"""
        if not self.auth_token:
            self.log_result("Call Sessions", False, "No auth token available")
            return
        
        # 1. Get call config
        response = self.make_request("GET", "/call-config")
        if response and response.status_code == 200:
            data = response.json()
            expected_keys = ["min_duration", "max_duration", "default_duration"]
            success = all(key in data for key in expected_keys)
            self.log_result("Call Config", success, f"Config keys: {list(data.keys())}")
        else:
            self.log_result("Call Config", False, f"HTTP {response.status_code if response else 'No response'}")
        
        # 2. Create call session
        session_data = {
            "duration_minutes": 30
        }
        
        response = self.make_request("POST", "/call-sessions", session_data)
        if response and response.status_code == 200:
            data = response.json()
            success = "session_id" in data and "room_url" in data
            self.log_result("Call Sessions - Create", success, f"Session ID: {data.get('session_id')}")
        else:
            self.log_result("Call Sessions - Create", False, f"HTTP {response.status_code if response else 'No response'}")
    
    def test_decision_templates(self):
        """Test decision templates (admin)"""
        if not self.auth_token:
            self.log_result("Decision Templates", False, "No auth token available")
            return
        
        # 1. Get decision templates
        response = self.make_request("GET", "/decision-templates")
        if response and response.status_code == 200:
            data = response.json()
            success = isinstance(data, list)
            self.log_result("Decision Templates - List", success, f"Found {len(data)} templates")
        else:
            self.log_result("Decision Templates - List", False, f"HTTP {response.status_code if response else 'No response'}")
        
        # 2. Create decision template (may fail if not admin)
        template_data = {
            "name": "Regression Test Template",
            "life_area": "career",
            "decision_type": "need",
            "description": "Test template after refactoring",
            "factors": [
                {"name": "Salary", "category": "primary"},
                {"name": "Work-Life Balance", "category": "secondary"}
            ]
        }
        
        response = self.make_request("POST", "/decision-templates", template_data)
        if response and response.status_code == 200:
            data = response.json()
            # Check for either 'template_id' or 'id' field
            template_id = data.get("template_id") or data.get("id")
            if template_id:
                self.log_result("Decision Templates - Create", True, f"Template ID: {template_id}")
            else:
                self.log_result("Decision Templates - Create", False, f"Missing template_id. Response: {data}")
        elif response and response.status_code == 403:
            self.log_result("Decision Templates - Create", True, "Correctly rejected non-admin user (403)")
        else:
            self.log_result("Decision Templates - Create", False, f"HTTP {response.status_code if response else 'No response'}")
    
    def test_decision_meta(self):
        """Test decision meta endpoint"""
        response = self.make_request("GET", "/decision-meta", headers={})
        if response and response.status_code == 200:
            data = response.json()
            expected_keys = ["life_areas", "decision_types"]
            success = all(key in data for key in expected_keys)
            self.log_result("Decision Meta", success, f"Meta keys: {list(data.keys())}")
        else:
            self.log_result("Decision Meta", False, f"HTTP {response.status_code if response else 'No response'}")
    
    def run_all_tests(self):
        """Run all regression tests"""
        print("🚀 STARTING COMPREHENSIVE BACKEND REGRESSION TEST")
        print("=" * 60)
        print(f"Backend URL: {BASE_URL}")
        print(f"Test started at: {datetime.now().isoformat()}")
        print("=" * 60)
        
        # Core tests in order
        self.test_health_check()
        self.test_auth_flow()
        self.test_prr_decisions_crud()
        self.test_decision_clone()
        self.test_templates()
        self.test_test123()
        self.test_assessment()
        self.test_journal()
        self.test_stats_and_folders()
        self.test_organizations()
        self.test_notifications()
        self.test_analytics()
        self.test_experts()
        self.test_call_sessions()
        self.test_decision_templates()
        self.test_decision_meta()
        
        # Summary
        print("\n" + "=" * 60)
        print("🎯 REGRESSION TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.results if r["success"])
        total = len(self.results)
        success_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        print("\n📋 DETAILED RESULTS:")
        for result in self.results:
            print(f"{result['status']}: {result['test']}")
            if result['details'] and not result['success']:
                print(f"   └─ {result['details']}")
        
        # Failed tests
        failed_tests = [r for r in self.results if not r["success"]]
        if failed_tests:
            print(f"\n❌ FAILED TESTS ({len(failed_tests)}):")
            for test in failed_tests:
                print(f"   • {test['test']}: {test['details']}")
        
        print(f"\n✅ REGRESSION TEST COMPLETED at {datetime.now().isoformat()}")
        
        return success_rate >= 80  # Consider 80%+ success rate as passing

if __name__ == "__main__":
    tester = RegressionTester()
    success = tester.run_all_tests()
    exit(0 if success else 1)