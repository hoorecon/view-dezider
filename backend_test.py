#!/usr/bin/env python3
"""
View Dezider Backend API Test Suite
Tests all backend APIs for the decision intelligence app
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "https://chapter2-guide.preview.emergentagent.com"
API_BASE = f"{BASE_URL}/api"

class BackendTestSuite:
    def __init__(self):
        self.session_token = None
        self.user_id = None
        self.test_email = f"sarah.parker.{int(time.time())}@careerpath.com"
        self.test_password = "securePass2025!"
        self.test_name = "Sarah Parker"
        self.created_decision_id = None
        self.created_test123_id = None
        self.created_journal_id = None
        
    def log_test(self, test_name, status, details=""):
        """Log test results"""
        status_symbol = "✅" if status else "❌"
        print(f"{status_symbol} {test_name}")
        if details:
            print(f"   {details}")
        return status

    def test_auth_registration(self):
        """Test user registration with email/password"""
        url = f"{API_BASE}/auth/register"
        payload = {
            "email": self.test_email,
            "password": self.test_password,
            "name": self.test_name
        }
        
        try:
            response = requests.post(url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["user_id", "email", "name", "session_token"]
                
                if all(field in data for field in required_fields):
                    self.session_token = data["session_token"]
                    self.user_id = data["user_id"]
                    return self.log_test("Auth Registration", True, 
                                       f"User created: {data['user_id']}")
                else:
                    return self.log_test("Auth Registration", False, 
                                       f"Missing fields in response: {data}")
            else:
                return self.log_test("Auth Registration", False, 
                                   f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("Auth Registration", False, f"Error: {str(e)}")

    def test_auth_login(self):
        """Test user login with email/password"""
        url = f"{API_BASE}/auth/login"
        payload = {
            "email": self.test_email,
            "password": self.test_password
        }
        
        try:
            response = requests.post(url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["user_id", "email", "name", "session_token"]
                
                if all(field in data for field in required_fields):
                    # Update session token from login
                    self.session_token = data["session_token"]
                    return self.log_test("Auth Login", True, 
                                       f"Logged in user: {data['user_id']}")
                else:
                    return self.log_test("Auth Login", False, 
                                       f"Missing fields in response: {data}")
            else:
                return self.log_test("Auth Login", False, 
                                   f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("Auth Login", False, f"Error: {str(e)}")

    def test_auth_me(self):
        """Test getting current user info"""
        url = f"{API_BASE}/auth/me"
        headers = {"Authorization": f"Bearer {self.session_token}"}
        
        try:
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["user_id", "email", "name"]
                
                if all(field in data for field in required_fields):
                    return self.log_test("Auth Me", True, 
                                       f"Retrieved user: {data['email']}")
                else:
                    return self.log_test("Auth Me", False, 
                                       f"Missing fields in response: {data}")
            else:
                return self.log_test("Auth Me", False, 
                                   f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("Auth Me", False, f"Error: {str(e)}")

    def test_prr_decisions_create(self):
        """Test creating a new PRR decision"""
        url = f"{API_BASE}/decisions"
        headers = {"Authorization": f"Bearer {self.session_token}"}
        payload = {
            "title": "Accept Senior Marketing Manager Position",
            "context": "I've been offered a senior marketing manager role at a tech startup. The role offers more responsibility and growth potential, but comes with higher pressure and longer hours. I need to decide whether to accept this position or stay in my current comfortable role."
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                if "id" in data and "message" in data:
                    self.created_decision_id = data["id"]
                    return self.log_test("PRR Decision Create", True, 
                                       f"Decision created: {data['id']}")
                else:
                    return self.log_test("PRR Decision Create", False, 
                                       f"Missing fields in response: {data}")
            else:
                return self.log_test("PRR Decision Create", False, 
                                   f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("PRR Decision Create", False, f"Error: {str(e)}")

    def test_prr_decisions_list(self):
        """Test listing PRR decisions"""
        url = f"{API_BASE}/decisions"
        headers = {"Authorization": f"Bearer {self.session_token}"}
        
        try:
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, list) and len(data) > 0:
                    decision = data[0]
                    required_fields = ["id", "title", "context", "user_id"]
                    
                    if all(field in decision for field in required_fields):
                        return self.log_test("PRR Decision List", True, 
                                           f"Found {len(data)} decisions")
                    else:
                        return self.log_test("PRR Decision List", False, 
                                           f"Missing fields in decision: {decision}")
                else:
                    return self.log_test("PRR Decision List", True, 
                                       "No decisions found (empty list)")
            else:
                return self.log_test("PRR Decision List", False, 
                                   f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("PRR Decision List", False, f"Error: {str(e)}")

    def test_prr_decision_get(self):
        """Test getting a specific PRR decision"""
        if not self.created_decision_id:
            return self.log_test("PRR Decision Get", False, "No decision ID available")
            
        url = f"{API_BASE}/decisions/{self.created_decision_id}"
        headers = {"Authorization": f"Bearer {self.session_token}"}
        
        try:
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["id", "title", "context", "user_id"]
                
                if all(field in data for field in required_fields):
                    return self.log_test("PRR Decision Get", True, 
                                       f"Retrieved decision: {data['title']}")
                else:
                    return self.log_test("PRR Decision Get", False, 
                                       f"Missing fields in response: {data}")
            else:
                return self.log_test("PRR Decision Get", False, 
                                   f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("PRR Decision Get", False, f"Error: {str(e)}")

    def test_prr_decision_update(self):
        """Test updating a PRR decision with factors and options"""
        if not self.created_decision_id:
            return self.log_test("PRR Decision Update", False, "No decision ID available")
            
        url = f"{API_BASE}/decisions/{self.created_decision_id}"
        headers = {"Authorization": f"Bearer {self.session_token}"}
        
        # Update with factors and options for the career decision
        payload = {
            "factors": [
                {"id": "factor1", "name": "Career Growth", "category": "primary", "rating": 95, "order": 1},
                {"id": "factor2", "name": "Work-Life Balance", "category": "primary", "rating": 85, "order": 2},
                {"id": "factor3", "name": "Salary Increase", "category": "primary", "rating": 75, "order": 3},
                {"id": "factor4", "name": "Company Culture", "category": "secondary", "rating": 70, "order": 4}
            ],
            "options": [
                {
                    "id": "option1",
                    "name": "Accept New Position",
                    "assessments": [
                        {"factor_id": "factor1", "percentage": 90},
                        {"factor_id": "factor2", "percentage": 60},
                        {"factor_id": "factor3", "percentage": 80},
                        {"factor_id": "factor4", "percentage": 85}
                    ]
                },
                {
                    "id": "option2",
                    "name": "Stay in Current Role",
                    "assessments": [
                        {"factor_id": "factor1", "percentage": 40},
                        {"factor_id": "factor2", "percentage": 90},
                        {"factor_id": "factor3", "percentage": 30},
                        {"factor_id": "factor4", "percentage": 95}
                    ]
                }
            ],
            "status": "in_progress"
        }
        
        try:
            response = requests.put(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                if "message" in data:
                    return self.log_test("PRR Decision Update", True, 
                                       f"Decision updated successfully")
                else:
                    return self.log_test("PRR Decision Update", False, 
                                       f"Unexpected response: {data}")
            else:
                return self.log_test("PRR Decision Update", False, 
                                   f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("PRR Decision Update", False, f"Error: {str(e)}")

    def test_prr_decision_delete(self):
        """Test deleting a PRR decision"""
        if not self.created_decision_id:
            return self.log_test("PRR Decision Delete", False, "No decision ID available")
            
        url = f"{API_BASE}/decisions/{self.created_decision_id}"
        headers = {"Authorization": f"Bearer {self.session_token}"}
        
        try:
            response = requests.delete(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                if "message" in data:
                    return self.log_test("PRR Decision Delete", True, 
                                       "Decision deleted successfully")
                else:
                    return self.log_test("PRR Decision Delete", False, 
                                       f"Unexpected response: {data}")
            else:
                return self.log_test("PRR Decision Delete", False, 
                                   f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("PRR Decision Delete", False, f"Error: {str(e)}")

    def test_test123_create(self):
        """Test creating a Test123 instant decision session"""
        url = f"{API_BASE}/test123"
        headers = {"Authorization": f"Bearer {self.session_token}"}
        payload = {
            "situation": "Should I quit my job to start my own consulting business? I have some savings but no guaranteed clients yet."
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                if "id" in data and "message" in data:
                    self.created_test123_id = data["id"]
                    return self.log_test("Test123 Create", True, 
                                       f"Session created: {data['id']}")
                else:
                    return self.log_test("Test123 Create", False, 
                                       f"Missing fields in response: {data}")
            else:
                return self.log_test("Test123 Create", False, 
                                   f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("Test123 Create", False, f"Error: {str(e)}")

    def test_test123_list(self):
        """Test listing Test123 sessions"""
        url = f"{API_BASE}/test123"
        headers = {"Authorization": f"Bearer {self.session_token}"}
        
        try:
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, list):
                    if len(data) > 0:
                        session = data[0]
                        required_fields = ["id", "situation", "user_id"]
                        
                        if all(field in session for field in required_fields):
                            return self.log_test("Test123 List", True, 
                                               f"Found {len(data)} sessions")
                        else:
                            return self.log_test("Test123 List", False, 
                                               f"Missing fields in session: {session}")
                    else:
                        return self.log_test("Test123 List", True, 
                                           "No sessions found (empty list)")
                else:
                    return self.log_test("Test123 List", False, 
                                       f"Expected list, got: {type(data)}")
            else:
                return self.log_test("Test123 List", False, 
                                   f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("Test123 List", False, f"Error: {str(e)}")

    def test_test123_update(self):
        """Test updating Test123 session with test progress"""
        if not self.created_test123_id:
            return self.log_test("Test123 Update", False, "No session ID available")
            
        url = f"{API_BASE}/test123/{self.created_test123_id}"
        headers = {"Authorization": f"Bearer {self.session_token}"}
        
        payload = {
            "is_emotional": False,
            "what_i_want": "Financial independence and professional fulfillment",
            "worst_case_scenario": "Business fails and I lose my savings",
            "ready_for_worst": True,
            "completed_test": 1
        }
        
        try:
            response = requests.put(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                if "message" in data:
                    return self.log_test("Test123 Update", True, 
                                       "Session updated successfully")
                else:
                    return self.log_test("Test123 Update", False, 
                                       f"Unexpected response: {data}")
            else:
                return self.log_test("Test123 Update", False, 
                                   f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("Test123 Update", False, f"Error: {str(e)}")

    def test_assessment_questions(self):
        """Test getting assessment questions"""
        url = f"{API_BASE}/assessment/questions"
        
        try:
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                
                if "questions" in data and isinstance(data["questions"], list):
                    questions = data["questions"]
                    if len(questions) > 0:
                        question = questions[0]
                        required_fields = ["id", "text", "mode"]
                        
                        if all(field in question for field in required_fields):
                            return self.log_test("Assessment Questions", True, 
                                               f"Retrieved {len(questions)} questions")
                        else:
                            return self.log_test("Assessment Questions", False, 
                                               f"Missing fields in question: {question}")
                    else:
                        return self.log_test("Assessment Questions", False, 
                                           "No questions returned")
                else:
                    return self.log_test("Assessment Questions", False, 
                                       f"Invalid response format: {data}")
            else:
                return self.log_test("Assessment Questions", False, 
                                   f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("Assessment Questions", False, f"Error: {str(e)}")

    def test_assessment_submit(self):
        """Test submitting assessment answers"""
        url = f"{API_BASE}/assessment"
        headers = {"Authorization": f"Bearer {self.session_token}"}
        
        # Sample answers for the assessment
        payload = {
            "answers": {
                "q1": 4, "q2": 5, "q3": 2, "q4": 4,
                "q5": 3, "q6": 5, "q7": 2, "q8": 4,
                "q9": 3, "q10": 5, "q11": 2, "q12": 3
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["id", "dominant_mode", "mode_scores"]
                
                if all(field in data for field in required_fields):
                    return self.log_test("Assessment Submit", True, 
                                       f"Dominant mode: {data['dominant_mode']}")
                else:
                    return self.log_test("Assessment Submit", False, 
                                       f"Missing fields in response: {data}")
            else:
                return self.log_test("Assessment Submit", False, 
                                   f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("Assessment Submit", False, f"Error: {str(e)}")

    def test_journal_create(self):
        """Test creating a decision journal entry"""
        url = f"{API_BASE}/journal"
        headers = {"Authorization": f"Bearer {self.session_token}"}
        payload = {
            "decision_title": "Career Transition Decision",
            "decision_description": "After careful consideration using the PRR method, I decided to accept the senior marketing manager position. The growth potential and learning opportunities outweighed the work-life balance concerns."
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                if "id" in data and "message" in data:
                    self.created_journal_id = data["id"]
                    return self.log_test("Journal Create", True, 
                                       f"Journal entry created: {data['id']}")
                else:
                    return self.log_test("Journal Create", False, 
                                       f"Missing fields in response: {data}")
            else:
                return self.log_test("Journal Create", False, 
                                   f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("Journal Create", False, f"Error: {str(e)}")

    def test_journal_list(self):
        """Test listing journal entries"""
        url = f"{API_BASE}/journal"
        headers = {"Authorization": f"Bearer {self.session_token}"}
        
        try:
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, list):
                    if len(data) > 0:
                        entry = data[0]
                        required_fields = ["id", "decision_title", "decision_description", "user_id"]
                        
                        if all(field in entry for field in required_fields):
                            return self.log_test("Journal List", True, 
                                               f"Found {len(data)} entries")
                        else:
                            return self.log_test("Journal List", False, 
                                               f"Missing fields in entry: {entry}")
                    else:
                        return self.log_test("Journal List", True, 
                                           "No entries found (empty list)")
                else:
                    return self.log_test("Journal List", False, 
                                       f"Expected list, got: {type(data)}")
            else:
                return self.log_test("Journal List", False, 
                                   f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("Journal List", False, f"Error: {str(e)}")

    def test_dashboard_stats(self):
        """Test getting dashboard statistics"""
        url = f"{API_BASE}/stats"
        headers = {"Authorization": f"Bearer {self.session_token}"}
        
        try:
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                required_sections = ["decisions", "test123", "journal"]
                
                if all(section in data for section in required_sections):
                    decisions = data["decisions"]
                    if "total" in decisions and "completed" in decisions:
                        return self.log_test("Dashboard Stats", True, 
                                           f"Stats: {decisions['total']} decisions, "
                                           f"{data['test123']['total']} test123, "
                                           f"{data['journal']['total']} journal")
                    else:
                        return self.log_test("Dashboard Stats", False, 
                                           f"Missing decision stats fields: {decisions}")
                else:
                    return self.log_test("Dashboard Stats", False, 
                                       f"Missing stats sections: {data}")
            else:
                return self.log_test("Dashboard Stats", False, 
                                   f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            return self.log_test("Dashboard Stats", False, f"Error: {str(e)}")

    def run_all_tests(self):
        """Run all backend API tests in order"""
        print(f"\n🧪 View Dezider Backend API Test Suite")
        print(f"Base URL: {BASE_URL}")
        print(f"Test User: {self.test_email}")
        print("=" * 60)
        
        # Track test results
        test_results = []
        
        # Auth Tests
        print("\n📝 Authentication Tests")
        test_results.append(self.test_auth_registration())
        test_results.append(self.test_auth_login())
        test_results.append(self.test_auth_me())
        
        # PRR Decision Tests
        print("\n🎯 PRR Decision Tests")
        test_results.append(self.test_prr_decisions_create())
        test_results.append(self.test_prr_decisions_list())
        test_results.append(self.test_prr_decision_get())
        test_results.append(self.test_prr_decision_update())
        test_results.append(self.test_prr_decision_delete())
        
        # Test123 Tests
        print("\n⚡ Test123 Sessions Tests")
        test_results.append(self.test_test123_create())
        test_results.append(self.test_test123_list())
        test_results.append(self.test_test123_update())
        
        # Assessment Tests
        print("\n🧠 Decision Mode Assessment Tests")
        test_results.append(self.test_assessment_questions())
        test_results.append(self.test_assessment_submit())
        
        # Journal Tests
        print("\n📖 Decision Journal Tests")
        test_results.append(self.test_journal_create())
        test_results.append(self.test_journal_list())
        
        # Dashboard Tests
        print("\n📊 Dashboard Tests")
        test_results.append(self.test_dashboard_stats())
        
        # Summary
        print("\n" + "=" * 60)
        passed = sum(test_results)
        total = len(test_results)
        print(f"🎯 Test Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("✅ All backend APIs are working correctly!")
        else:
            print(f"❌ {total - passed} test(s) failed - see details above")
        
        return passed == total

if __name__ == "__main__":
    suite = BackendTestSuite()
    success = suite.run_all_tests()
    exit(0 if success else 1)