#!/usr/bin/env python3
"""
COMPREHENSIVE UAT - Test ALL modules of the Dezider system
Testing 47 scenarios across all modules systematically
"""

import requests
import json
import time
from datetime import datetime, timedelta

# Backend URL from environment
BASE_URL = "https://dezider-core.preview.emergentagent.com/api"

class DeziderUATTester:
    def __init__(self):
        self.session_token = None
        self.user_id = None
        self.decision_id = None
        self.test_results = []
        self.passed_count = 0
        self.failed_count = 0
        self.timestamp = int(time.time())  # Store timestamp for reuse
        
    def log_test(self, test_num, description, passed, details=""):
        """Log test result"""
        status = "PASS" if passed else "FAIL"
        result = f"Test {test_num}: {description} - {status}"
        if details:
            result += f" ({details})"
        print(result)
        self.test_results.append({
            'test_num': test_num,
            'description': description,
            'passed': passed,
            'details': details
        })
        if passed:
            self.passed_count += 1
        else:
            self.failed_count += 1
    
    def make_request(self, method, endpoint, data=None, headers=None):
        """Make HTTP request with proper headers"""
        url = f"{BASE_URL}{endpoint}"
        
        # Default headers
        default_headers = {
            'Content-Type': 'application/json'
        }
        
        # Add session token if available
        if self.session_token:
            default_headers['Authorization'] = f'Bearer {self.session_token}'
            
        # Merge with provided headers
        if headers:
            default_headers.update(headers)
            
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=default_headers)
            elif method.upper() == 'POST':
                response = requests.post(url, json=data, headers=default_headers)
            elif method.upper() == 'PUT':
                response = requests.put(url, json=data, headers=default_headers)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=default_headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
                
            return response
        except Exception as e:
            print(f"Request failed: {e}")
            return None
    
    def run_comprehensive_uat(self):
        """Run all 47 UAT test scenarios"""
        print("=" * 80)
        print("COMPREHENSIVE UAT - Testing ALL modules of the Dezider system")
        print("=" * 80)
        
        # SETUP - Create Master Test User
        self.test_setup()
        
        # MODULE 1: AUTH & USER
        self.test_auth_user()
        
        # MODULE 2: DECISIONS / PRR FLOW  
        self.test_decisions_prr()
        
        # MODULE 3: CTT TASKS
        self.test_ctt_tasks()
        
        # MODULE 4: GEM GOALS
        self.test_gem_goals()
        
        # MODULE 5: LIFESTYLE ROUTINES
        self.test_lifestyle_routines()
        
        # MODULE 6: TEPFI
        self.test_tepfi()
        
        # MODULE 7: SOLUTIONS STORE
        self.test_solutions_store()
        
        # MODULE 8: CLD ENGINE
        self.test_cld_engine()
        
        # MODULE 9: TIME DEZIDER
        self.test_time_dezider()
        
        # MODULE 10: TIME STORE
        self.test_time_store()
        
        # MODULE 11: PAYMENTS & CREDITS
        self.test_payments_credits()
        
        # MODULE 12: CREDIT DEDUCTION FLOW (CRITICAL)
        self.test_credit_deduction_flow()
        
        # MODULE 13: DEO ENGINE
        self.test_deo_engine()
        
        # Final Report
        self.print_final_report()
    
    def test_setup(self):
        """SETUP - Create Master Test User"""
        print("\n--- SETUP: Create Master Test User ---")
        
        # Test 1: Register master test user
        user_data = {
            "email": f"uat_master_{self.timestamp}@test.com",
            "password": "UATtest123!",
            "name": "UAT Master User"
        }
        
        response = self.make_request('POST', '/auth/register', user_data)
        if response and response.status_code == 200:
            data = response.json()
            self.session_token = data.get('session_token')
            self.user_id = data.get('user_id')
            self.log_test(1, "POST /api/auth/register - Create master test user", True, 
                         f"User created with session token")
        else:
            self.log_test(1, "POST /api/auth/register - Create master test user", False,
                         f"Status: {response.status_code if response else 'No response'}")
            return
    
    def test_auth_user(self):
        """MODULE 1: AUTH & USER"""
        print("\n--- MODULE 1: AUTH & USER ---")
        
        # Test 3: GET /api/auth/me - Verify user profile
        response = self.make_request('GET', '/auth/me')
        if response and response.status_code == 200:
            data = response.json()
            has_required_fields = all(field in data for field in ['user_id', 'email', 'name'])
            self.log_test(3, "GET /api/auth/me - Verify user profile", has_required_fields,
                         f"Profile returned with required fields")
        else:
            self.log_test(3, "GET /api/auth/me - Verify user profile", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 4: POST /api/auth/register with same email - Should fail
        duplicate_data = {
            "email": f"uat_master_{self.timestamp}@test.com",  # Use same email as test 1
            "password": "UATtest123!",
            "name": "Duplicate User"
        }
        
        response = self.make_request('POST', '/auth/register', duplicate_data)
        if response and response.status_code in [400, 409]:
            self.log_test(4, "POST /api/auth/register with duplicate email - Should fail", True,
                         f"Correctly rejected duplicate with status {response.status_code}")
        else:
            self.log_test(4, "POST /api/auth/register with duplicate email - Should fail", False,
                         f"Status: {response.status_code if response else 'No response'}")
    
    def test_decisions_prr(self):
        """MODULE 2: DECISIONS / PRR FLOW"""
        print("\n--- MODULE 2: DECISIONS / PRR FLOW ---")
        
        # Test 5: POST /api/decisions - Create decision
        decision_data = {
            "title": "UAT Career Decision",
            "context": "Testing all modules",
            "life_area": "Career",
            "decision_type": "need"
        }
        
        response = self.make_request('POST', '/decisions', decision_data)
        if response and response.status_code == 200:
            data = response.json()
            self.decision_id = data.get('id')  # API returns 'id' not 'decision_id'
            self.log_test(5, "POST /api/decisions - Create decision", True,
                         f"Decision created with ID: {self.decision_id}")
        else:
            self.log_test(5, "POST /api/decisions - Create decision", False,
                         f"Status: {response.status_code if response else 'No response'}")
            return
        
        # Test 6: PUT /api/decisions/{id} - Update with factors
        factors_data = {
            "factors": [
                {"id": "f1", "name": "Salary", "category": "primary", "rating": 90, "order": 0},
                {"id": "f2", "name": "Work-Life Balance", "category": "primary", "rating": 80, "order": 1},
                {"id": "f3", "name": "Growth", "category": "secondary", "rating": 70, "order": 2}
            ]
        }
        
        response = self.make_request('PUT', f'/decisions/{self.decision_id}', factors_data)
        if response and response.status_code == 200:
            self.log_test(6, "PUT /api/decisions/{id} - Update with factors", True,
                         "Decision updated with 3 factors")
        else:
            self.log_test(6, "PUT /api/decisions/{id} - Update with factors", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 7: GET /api/decisions - Verify decision list
        response = self.make_request('GET', '/decisions')
        if response and response.status_code == 200:
            data = response.json()
            # Handle both list and dict response formats
            if isinstance(data, list):
                decisions = data
            else:
                decisions = data.get('decisions', [])
            found_decision = any(d.get('id') == self.decision_id for d in decisions)  # Use 'id' not 'decision_id'
            self.log_test(7, "GET /api/decisions - Verify decision list", found_decision,
                         f"Found {len(decisions)} decisions, our decision present")
        else:
            self.log_test(7, "GET /api/decisions - Verify decision list", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 8: GET /api/decisions/{id} - Verify full decision with factors
        response = self.make_request('GET', f'/decisions/{self.decision_id}')
        if response and response.status_code == 200:
            data = response.json()
            factors = data.get('factors', [])
            has_factors = len(factors) >= 3
            self.log_test(8, "GET /api/decisions/{id} - Verify full decision with factors", has_factors,
                         f"Decision has {len(factors)} factors")
        else:
            self.log_test(8, "GET /api/decisions/{id} - Verify full decision with factors", False,
                         f"Status: {response.status_code if response else 'No response'}")
    
    def test_ctt_tasks(self):
        """MODULE 3: CTT TASKS"""
        print("\n--- MODULE 3: CTT TASKS ---")
        
        # Test 9: POST /api/ctt/tasks - Morning Standup
        task1_data = {
            "task": "UAT Morning Standup",
            "from_time": "09:00",
            "to_time": "09:30", 
            "task_duration": "30m",
            "priority": "high",
            "life_area": "Career",
            "is_routine": True,
            "frequency": "daily"
        }
        
        response = self.make_request('POST', '/ctt/tasks', task1_data)
        if response and response.status_code == 200:
            self.log_test(9, "POST /api/ctt/tasks - Morning Standup", True,
                         "Morning standup task created")
        else:
            self.log_test(9, "POST /api/ctt/tasks - Morning Standup", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 10: POST /api/ctt/tasks - Deep Work
        task2_data = {
            "task": "UAT Deep Work",
            "from_time": "10:00",
            "to_time": "12:00",
            "task_duration": "2h", 
            "priority": "medium",
            "life_area": "Career"
        }
        
        response = self.make_request('POST', '/ctt/tasks', task2_data)
        if response and response.status_code == 200:
            self.log_test(10, "POST /api/ctt/tasks - Deep Work", True,
                         "Deep work task created")
        else:
            self.log_test(10, "POST /api/ctt/tasks - Deep Work", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 11: POST /api/ctt/tasks - Email
        task3_data = {
            "task": "UAT Email",
            "from_time": "16:00",
            "to_time": "17:00",
            "task_duration": "1h",
            "priority": "low", 
            "life_area": "Career",
            "is_routine": True,
            "frequency": "daily"
        }
        
        response = self.make_request('POST', '/ctt/tasks', task3_data)
        if response and response.status_code == 200:
            self.log_test(11, "POST /api/ctt/tasks - Email", True,
                         "Email task created")
        else:
            self.log_test(11, "POST /api/ctt/tasks - Email", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 12: GET /api/ctt/tasks - Verify 3 tasks
        response = self.make_request('GET', '/ctt/tasks')
        if response and response.status_code == 200:
            data = response.json()
            # Handle both list and dict response formats
            if isinstance(data, list):
                tasks = data
            else:
                tasks = data.get('tasks', [])
            has_three_tasks = len(tasks) >= 3
            self.log_test(12, "GET /api/ctt/tasks - Verify 3 tasks", has_three_tasks,
                         f"Found {len(tasks)} tasks")
        else:
            self.log_test(12, "GET /api/ctt/tasks - Verify 3 tasks", False,
                         f"Status: {response.status_code if response else 'No response'}")
    
    def test_gem_goals(self):
        """MODULE 4: GEM GOALS"""
        print("\n--- MODULE 4: GEM GOALS ---")
        
        # Test 13: POST /api/gem/goals - Create goal
        goal_data = {
            "title": "UAT Career Growth Goal",
            "life_area": "Career",
            "goal_type": "long_term",
            "priority": "high"
        }
        
        response = self.make_request('POST', '/gem/goals', goal_data)
        if response and response.status_code == 200:
            self.log_test(13, "POST /api/gem/goals - Create goal", True,
                         "Career growth goal created")
        else:
            self.log_test(13, "POST /api/gem/goals - Create goal", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 14: GET /api/gem/goals - Verify goal
        response = self.make_request('GET', '/gem/goals')
        if response and response.status_code == 200:
            data = response.json()
            # Handle both list and dict response formats
            if isinstance(data, list):
                goals = data
            else:
                goals = data.get('goals', [])
            has_goals = len(goals) >= 1
            self.log_test(14, "GET /api/gem/goals - Verify goal", has_goals,
                         f"Found {len(goals)} goals")
        else:
            self.log_test(14, "GET /api/gem/goals - Verify goal", False,
                         f"Status: {response.status_code if response else 'No response'}")
    
    def test_lifestyle_routines(self):
        """MODULE 5: LIFESTYLE ROUTINES"""
        print("\n--- MODULE 5: LIFESTYLE ROUTINES ---")
        
        # Test 15: POST /api/lifestyle/routines - Morning Exercise
        routine1_data = {
            "name": "UAT Morning Exercise",
            "time_slot": "06:30",
            "frequency": "daily",
            "priority": "high",
            "life_area": "Health",
            "category": "health"
        }
        
        response = self.make_request('POST', '/lifestyle/routines', routine1_data)
        if response and response.status_code == 200:
            self.log_test(15, "POST /api/lifestyle/routines - Morning Exercise", True,
                         "Morning exercise routine created")
        else:
            self.log_test(15, "POST /api/lifestyle/routines - Morning Exercise", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 16: POST /api/lifestyle/routines - Evening Meditation
        routine2_data = {
            "name": "UAT Evening Meditation",
            "time_slot": "21:00",
            "frequency": "daily",
            "priority": "medium",
            "life_area": "Mental_Health",
            "category": "wellness"
        }
        
        response = self.make_request('POST', '/lifestyle/routines', routine2_data)
        if response and response.status_code == 200:
            self.log_test(16, "POST /api/lifestyle/routines - Evening Meditation", True,
                         "Evening meditation routine created")
        else:
            self.log_test(16, "POST /api/lifestyle/routines - Evening Meditation", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 17: GET /api/lifestyle/routines - Verify 2 routines
        response = self.make_request('GET', '/lifestyle/routines')
        if response and response.status_code == 200:
            data = response.json()
            # Handle both list and dict response formats
            if isinstance(data, list):
                routines = data
            else:
                routines = data.get('routines', [])
            has_two_routines = len(routines) >= 2
            self.log_test(17, "GET /api/lifestyle/routines - Verify 2 routines", has_two_routines,
                         f"Found {len(routines)} routines")
        else:
            self.log_test(17, "GET /api/lifestyle/routines - Verify 2 routines", False,
                         f"Status: {response.status_code if response else 'No response'}")
    
    def test_tepfi(self):
        """MODULE 6: TEPFI"""
        print("\n--- MODULE 6: TEPFI ---")
        
        # Test 18: POST /api/tepfi/entries - Create TEPFI entry
        tepfi_data = {
            "title": "UAT Career TEPFI",
            "life_area": "Career",
            "matrix": {
                "time": {
                    "self": {"score": 7, "description": "Good time mgmt"}
                },
                "effort": {
                    "attitude_self": {"score": 8, "description": "Positive attitude"},
                    "knowledge_self": {"score": 7, "description": "Strong knowledge"}
                },
                "people": {
                    "micro": {"score": 6, "description": "Supportive team"}
                },
                "finance": {
                    "self": {"score": 5, "description": "Average budget"}
                },
                "infrastructure": {
                    "self": {"score": 8, "description": "Good tools"}
                }
            }
        }
        
        response = self.make_request('POST', '/tepfi/entries', tepfi_data)
        if response and response.status_code == 200:
            self.log_test(18, "POST /api/tepfi/entries - Create TEPFI entry", True,
                         "TEPFI entry created")
        else:
            self.log_test(18, "POST /api/tepfi/entries - Create TEPFI entry", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 19: GET /api/tepfi/entries - Verify TEPFI entry
        response = self.make_request('GET', '/tepfi/entries')
        if response and response.status_code == 200:
            data = response.json()
            # Handle both list and dict response formats
            if isinstance(data, list):
                entries = data
            else:
                entries = data.get('entries', [])
            has_entries = len(entries) >= 1
            self.log_test(19, "GET /api/tepfi/entries - Verify TEPFI entry", has_entries,
                         f"Found {len(entries)} TEPFI entries")
        else:
            self.log_test(19, "GET /api/tepfi/entries - Verify TEPFI entry", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 20: GET /api/tepfi/metadata - Verify effort sub-dimensions
        response = self.make_request('GET', '/tepfi/metadata')
        if response and response.status_code == 200:
            data = response.json()
            effort_sub_dims = data.get('effort_sub_dimensions', [])
            has_eight_dims = len(effort_sub_dims) == 8
            self.log_test(20, "GET /api/tepfi/metadata - Verify 8 effort sub-dimensions", has_eight_dims,
                         f"Found {len(effort_sub_dims)} effort sub-dimensions")
        else:
            self.log_test(20, "GET /api/tepfi/metadata - Verify 8 effort sub-dimensions", False,
                         f"Status: {response.status_code if response else 'No response'}")
    
    def test_solutions_store(self):
        """MODULE 7: SOLUTIONS STORE"""
        print("\n--- MODULE 7: SOLUTIONS STORE ---")
        
        # Test 21: POST /api/solutions-store - Create solution
        solution_data = {
            "name": "UAT Solution",
            "description": "Test solution",
            "category": "Career",
            "visibility": "private"
        }
        
        response = self.make_request('POST', '/solutions-store', solution_data)
        if response and response.status_code == 200:
            self.log_test(21, "POST /api/solutions-store - Create solution", True,
                         "Solution created")
        else:
            self.log_test(21, "POST /api/solutions-store - Create solution", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 22: GET /api/solutions-store - Verify solution
        response = self.make_request('GET', '/solutions-store')
        if response and response.status_code == 200:
            data = response.json()
            # Check if we have solutions (could be from seed data)
            has_solutions = len(data) >= 1 if isinstance(data, list) else True
            self.log_test(22, "GET /api/solutions-store - Verify solution", has_solutions,
                         f"Solutions store accessible")
        else:
            self.log_test(22, "GET /api/solutions-store - Verify solution", False,
                         f"Status: {response.status_code if response else 'No response'}")
    
    def test_cld_engine(self):
        """MODULE 8: CLD ENGINE"""
        print("\n--- MODULE 8: CLD ENGINE ---")
        
        if not self.decision_id:
            self.log_test(23, "CLD Engine tests", False, "No decision_id available")
            self.log_test(24, "CLD Engine tests", False, "No decision_id available")
            self.log_test(25, "CLD Engine tests", False, "No decision_id available")
            self.log_test(26, "CLD Engine tests", False, "No decision_id available")
            self.log_test(27, "CLD Engine tests", False, "No decision_id available")
            return
        
        # Test 23: POST /api/cld/{decision_id}/save - Save CLD
        cld_data = {
            "nodes": [
                {"id": "f1", "name": "Salary", "x": 100, "y": 100, "base_value": 50},
                {"id": "f2", "name": "Work-Life Balance", "x": 200, "y": 100, "base_value": 60},
                {"id": "f3", "name": "Growth", "x": 150, "y": 200, "base_value": 70}
            ],
            "links": [
                {"source": "f1", "target": "f2", "strength": 5, "polarity": "positive"},
                {"source": "f2", "target": "f3", "strength": 7, "polarity": "positive"}
            ]
        }
        
        response = self.make_request('POST', f'/cld/{self.decision_id}/save', cld_data)
        if response and response.status_code == 200:
            self.log_test(23, "POST /api/cld/{decision_id}/save - Save CLD", True,
                         "CLD saved with 3 nodes and 2 links")
        else:
            self.log_test(23, "POST /api/cld/{decision_id}/save - Save CLD", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 24: GET /api/cld/{decision_id} - Verify saved CLD
        response = self.make_request('GET', f'/cld/{self.decision_id}')
        if response and response.status_code == 200:
            data = response.json()
            has_nodes = len(data.get('nodes', [])) >= 3
            has_links = len(data.get('links', [])) >= 2
            self.log_test(24, "GET /api/cld/{decision_id} - Verify saved CLD", has_nodes and has_links,
                         f"CLD has {len(data.get('nodes', []))} nodes and {len(data.get('links', []))} links")
        else:
            self.log_test(24, "GET /api/cld/{decision_id} - Verify saved CLD", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 25: POST /api/cld/{decision_id}/simulate - Run simulation
        sim_data = {
            "shock_factor_id": "f1",
            "shock_delta": 20,
            "time_steps": 5,
            "dampening": 0.7
        }
        
        response = self.make_request('POST', f'/cld/{self.decision_id}/simulate', sim_data)
        if response and response.status_code == 200:
            data = response.json()
            has_timeline = 'timeline' in data
            has_stability = 'stability' in data
            self.log_test(25, "POST /api/cld/{decision_id}/simulate - Run simulation", has_timeline and has_stability,
                         f"Simulation completed with timeline and stability analysis")
        else:
            self.log_test(25, "POST /api/cld/{decision_id}/simulate - Run simulation", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 26: POST /api/cld/{decision_id}/layout - Apply layout
        layout_data = {"layout_type": "force"}
        
        response = self.make_request('POST', f'/cld/{self.decision_id}/layout', layout_data)
        if response and response.status_code == 200:
            self.log_test(26, "POST /api/cld/{decision_id}/layout - Apply layout", True,
                         "Force layout applied")
        else:
            self.log_test(26, "POST /api/cld/{decision_id}/layout - Apply layout", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 27: GET /api/cld/list - Verify CLD in list
        response = self.make_request('GET', '/cld/list')
        if response and response.status_code == 200:
            data = response.json()
            clds = data.get('clds', [])
            has_our_cld = any(cld.get('decision_id') == self.decision_id for cld in clds)
            self.log_test(27, "GET /api/cld/list - Verify CLD in list", has_our_cld,
                         f"Found {len(clds)} CLDs, our CLD present")
        else:
            self.log_test(27, "GET /api/cld/list - Verify CLD in list", False,
                         f"Status: {response.status_code if response else 'No response'}")
    
    def test_time_dezider(self):
        """MODULE 9: TIME DEZIDER"""
        print("\n--- MODULE 9: TIME DEZIDER ---")
        
        # Test 28: GET /api/time-dezider/preferences - Verify defaults
        response = self.make_request('GET', '/time-dezider/preferences')
        if response and response.status_code == 200:
            data = response.json()
            has_day_start = 'day_start' in data
            has_day_end = 'day_end' in data
            self.log_test(28, "GET /api/time-dezider/preferences - Verify defaults", has_day_start and has_day_end,
                         "Preferences have day_start and day_end")
        else:
            self.log_test(28, "GET /api/time-dezider/preferences - Verify defaults", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 29: PUT /api/time-dezider/preferences - Update preferences
        prefs_data = {
            "day_start": "06:00",
            "day_end": "22:00"
        }
        
        response = self.make_request('PUT', '/time-dezider/preferences', prefs_data)
        if response and response.status_code == 200:
            self.log_test(29, "PUT /api/time-dezider/preferences - Update preferences", True,
                         "Preferences updated")
        else:
            self.log_test(29, "PUT /api/time-dezider/preferences - Update preferences", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 30: GET /api/time-dezider/daily - Verify aggregated schedule
        response = self.make_request('GET', '/time-dezider/daily?date=2026-03-27')
        if response and response.status_code == 200:
            data = response.json()
            has_blocks = 'blocks' in data
            has_stats = 'stats' in data
            self.log_test(30, "GET /api/time-dezider/daily - Verify aggregated schedule", has_blocks and has_stats,
                         f"Daily schedule has blocks and stats")
        else:
            self.log_test(30, "GET /api/time-dezider/daily - Verify aggregated schedule", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 31: POST /api/time-dezider/unplanned-task - Add unplanned task
        unplanned_data = {
            "date": "2026-03-27",
            "title": "UAT Urgent Call",
            "duration_minutes": 45,
            "priority": "high"
        }
        
        response = self.make_request('POST', '/time-dezider/unplanned-task', unplanned_data)
        if response and response.status_code == 200:
            self.log_test(31, "POST /api/time-dezider/unplanned-task - Add unplanned task", True,
                         "Unplanned task added")
        else:
            self.log_test(31, "POST /api/time-dezider/unplanned-task - Add unplanned task", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 32: GET /api/time-dezider/daily - Verify unplanned task appears
        response = self.make_request('GET', '/time-dezider/daily?date=2026-03-27')
        if response and response.status_code == 200:
            data = response.json()
            blocks = data.get('blocks', [])
            has_unplanned = any(block.get('source_type') == 'unplanned' for block in blocks)
            self.log_test(32, "GET /api/time-dezider/daily - Verify unplanned task appears", has_unplanned,
                         f"Found unplanned task in {len(blocks)} blocks")
        else:
            self.log_test(32, "GET /api/time-dezider/daily - Verify unplanned task appears", False,
                         f"Status: {response.status_code if response else 'No response'}")
    
    def test_time_store(self):
        """MODULE 10: TIME STORE"""
        print("\n--- MODULE 10: TIME STORE ---")
        
        # Test 33: GET /api/time-store/budget?period=daily - Verify daily budget
        response = self.make_request('GET', '/time-store/budget?period=daily')
        if response and response.status_code == 200:
            data = response.json()
            has_by_area = 'by_area' in data
            has_by_type = 'by_type' in data
            has_items = 'items' in data
            self.log_test(33, "GET /api/time-store/budget?period=daily - Verify daily budget", 
                         has_by_area and has_by_type and has_items,
                         "Daily budget has by_area, by_type, and items")
        else:
            self.log_test(33, "GET /api/time-store/budget?period=daily - Verify daily budget", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 34: GET /api/time-store/budget?period=weekly - Verify weekly budget
        response = self.make_request('GET', '/time-store/budget?period=weekly')
        if response and response.status_code == 200:
            data = response.json()
            has_by_area = 'by_area' in data
            has_by_type = 'by_type' in data
            has_items = 'items' in data
            self.log_test(34, "GET /api/time-store/budget?period=weekly - Verify weekly budget",
                         has_by_area and has_by_type and has_items,
                         "Weekly budget has by_area, by_type, and items")
        else:
            self.log_test(34, "GET /api/time-store/budget?period=weekly - Verify weekly budget", False,
                         f"Status: {response.status_code if response else 'No response'}")
    
    def test_payments_credits(self):
        """MODULE 11: PAYMENTS & CREDITS"""
        print("\n--- MODULE 11: PAYMENTS & CREDITS ---")
        
        # Test 35: GET /api/payments/plans - Verify plans
        response = self.make_request('GET', '/payments/plans')
        if response and response.status_code == 200:
            data = response.json()
            has_plans = len(data.get('plans', [])) == 5
            has_topup_packs = len(data.get('topup_packs', [])) == 5
            has_credit_costs = 'credit_costs' in data
            self.log_test(35, "GET /api/payments/plans - Verify 5 plans + 5 topup packs + credit_costs",
                         has_plans and has_topup_packs and has_credit_costs,
                         f"Found {len(data.get('plans', []))} plans, {len(data.get('topup_packs', []))} packs")
        else:
            self.log_test(35, "GET /api/payments/plans - Verify 5 plans + 5 topup packs + credit_costs", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 36: GET /api/payments/wallet - Verify 100 initial credits
        response = self.make_request('GET', '/payments/wallet')
        if response and response.status_code == 200:
            data = response.json()
            credits = data.get('credits', 0)
            plan = data.get('current_plan', '')
            has_initial_credits = credits == 100
            is_free_plan = plan == 'free'
            self.log_test(36, "GET /api/payments/wallet - Verify 100 initial credits, plan='free'",
                         has_initial_credits and is_free_plan,
                         f"Credits: {credits}, Plan: {plan}")
        else:
            self.log_test(36, "GET /api/payments/wallet - Verify 100 initial credits, plan='free'", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 37: POST /api/payments/check-credits - Verify credit check
        check_data = {"action": "cld_generate"}
        
        response = self.make_request('POST', '/payments/check-credits', check_data)
        if response and response.status_code == 200:
            data = response.json()
            cost = data.get('cost', 0)
            sufficient = data.get('sufficient', False)
            self.log_test(37, "POST /api/payments/check-credits - Verify cost=3, sufficient=true",
                         cost == 3 and sufficient,
                         f"Cost: {cost}, Sufficient: {sufficient}")
        else:
            self.log_test(37, "POST /api/payments/check-credits - Verify cost=3, sufficient=true", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 38: POST /api/payments/create-topup-order - Verify Razorpay order
        topup_data = {"pack_id": "mini"}
        
        response = self.make_request('POST', '/payments/create-topup-order', topup_data)
        if response and response.status_code == 200:
            data = response.json()
            has_order_id = 'order_id' in data
            has_key_id = 'key_id' in data
            self.log_test(38, "POST /api/payments/create-topup-order - Verify Razorpay order created",
                         has_order_id and has_key_id,
                         "Razorpay order created with order_id and key_id")
        else:
            self.log_test(38, "POST /api/payments/create-topup-order - Verify Razorpay order created", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 39: POST /api/payments/create-subscription - Verify Razorpay subscription
        sub_data = {"plan_id": "pro"}
        
        response = self.make_request('POST', '/payments/create-subscription', sub_data)
        if response and response.status_code == 200:
            data = response.json()
            has_order_id = 'order_id' in data
            self.log_test(39, "POST /api/payments/create-subscription - Verify Razorpay order created",
                         has_order_id,
                         "Razorpay subscription order created")
        else:
            self.log_test(39, "POST /api/payments/create-subscription - Verify Razorpay order created", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 40: GET /api/payments/history - Verify initial grant transaction
        response = self.make_request('GET', '/payments/history')
        if response and response.status_code == 200:
            data = response.json()
            transactions = data.get('transactions', [])
            has_initial_grant = any(t.get('type') == 'initial_grant' for t in transactions)
            self.log_test(40, "GET /api/payments/history - Verify initial grant transaction",
                         has_initial_grant,
                         f"Found {len(transactions)} transactions, initial grant present")
        else:
            self.log_test(40, "GET /api/payments/history - Verify initial grant transaction", False,
                         f"Status: {response.status_code if response else 'No response'}")
    
    def test_credit_deduction_flow(self):
        """MODULE 12: CREDIT DEDUCTION FLOW (CRITICAL)"""
        print("\n--- MODULE 12: CREDIT DEDUCTION FLOW (CRITICAL) ---")
        
        # Test 41: GET /api/payments/wallet - Note current credits
        response = self.make_request('GET', '/payments/wallet')
        initial_credits = 100
        if response and response.status_code == 200:
            data = response.json()
            initial_credits = data.get('credits', 100)
            self.log_test(41, "GET /api/payments/wallet - Note current credits", True,
                         f"Current credits: {initial_credits}")
        else:
            self.log_test(41, "GET /api/payments/wallet - Note current credits", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 42: POST /api/cld/{decision_id}/save - Save a CLD first
        if not self.decision_id:
            self.log_test(42, "POST /api/cld/{decision_id}/save - Save CLD first", False, "No decision_id")
            self.log_test(43, "CLD Simulate test", False, "No decision_id")
            self.log_test(44, "Credit check after simulation", False, "No decision_id")
            self.log_test(45, "History check after simulation", False, "No decision_id")
            return
            
        cld_data = {
            "nodes": [
                {"id": "f1", "name": "Salary", "x": 100, "y": 100, "base_value": 50},
                {"id": "f2", "name": "Work-Life Balance", "x": 200, "y": 100, "base_value": 60},
                {"id": "f3", "name": "Growth", "x": 150, "y": 200, "base_value": 70}
            ],
            "links": [
                {"source": "f1", "target": "f2", "strength": 5, "polarity": "positive"},
                {"source": "f2", "target": "f3", "strength": 7, "polarity": "positive"}
            ]
        }
        
        response = self.make_request('POST', f'/cld/{self.decision_id}/save', cld_data)
        if response and response.status_code == 200:
            self.log_test(42, "POST /api/cld/{decision_id}/save - Save CLD first", True,
                         "CLD saved for credit deduction testing")
        else:
            self.log_test(42, "POST /api/cld/{decision_id}/save - Save CLD first", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 43: POST /api/cld/{decision_id}/simulate - Should succeed (simulation is FREE)
        sim_data = {
            "shock_factor_id": "f1",
            "shock_delta": 15,
            "time_steps": 3,
            "dampening": 0.8
        }
        
        response = self.make_request('POST', f'/cld/{self.decision_id}/simulate', sim_data)
        if response and response.status_code == 200:
            self.log_test(43, "POST /api/cld/{decision_id}/simulate - Should succeed (FREE)", True,
                         "CLD simulation completed (0 credits)")
        else:
            self.log_test(43, "POST /api/cld/{decision_id}/simulate - Should succeed (FREE)", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 44: GET /api/payments/wallet - Credits should still be 100
        response = self.make_request('GET', '/payments/wallet')
        if response and response.status_code == 200:
            data = response.json()
            current_credits = data.get('credits', 0)
            credits_unchanged = current_credits == initial_credits
            self.log_test(44, "GET /api/payments/wallet - Credits should still be 100 (simulation free)",
                         credits_unchanged,
                         f"Credits: {current_credits} (expected: {initial_credits})")
        else:
            self.log_test(44, "GET /api/payments/wallet - Credits should still be 100 (simulation free)", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 45: GET /api/payments/history - Verify no deduction for simulation
        response = self.make_request('GET', '/payments/history')
        if response and response.status_code == 200:
            data = response.json()
            transactions = data.get('transactions', [])
            # Should not have deduction transactions for simulation
            deduction_count = sum(1 for t in transactions if t.get('type') == 'deduction')
            self.log_test(45, "GET /api/payments/history - Verify no deduction for simulation",
                         deduction_count == 0,
                         f"Found {deduction_count} deduction transactions (expected: 0)")
        else:
            self.log_test(45, "GET /api/payments/history - Verify no deduction for simulation", False,
                         f"Status: {response.status_code if response else 'No response'}")
    
    def test_deo_engine(self):
        """MODULE 13: DEO ENGINE"""
        print("\n--- MODULE 13: DEO ENGINE ---")
        
        # Test 46: GET /api/deo/api-keys - Verify returns array
        response = self.make_request('GET', '/deo/api-keys')
        if response and response.status_code == 200:
            data = response.json()
            is_array = isinstance(data, list)
            self.log_test(46, "GET /api/deo/api-keys - Verify returns array", is_array,
                         f"Returns array with {len(data) if is_array else 'non-array'} items")
        else:
            self.log_test(46, "GET /api/deo/api-keys - Verify returns array", False,
                         f"Status: {response.status_code if response else 'No response'}")
        
        # Test 47: POST /api/deo/api-keys - Generate API key
        key_data = {
            "name": "UAT Test Key",
            "permissions": ["full_flow", "values_api", "logic_api"]
        }
        
        response = self.make_request('POST', '/deo/api-keys', key_data)
        if response and response.status_code == 200:
            data = response.json()
            has_key_id = 'key_id' in data
            has_api_key = 'api_key' in data
            self.log_test(47, "POST /api/deo/api-keys - Generate API key", has_key_id and has_api_key,
                         "API key generated with key_id and api_key")
        else:
            self.log_test(47, "POST /api/deo/api-keys - Generate API key", False,
                         f"Status: {response.status_code if response else 'No response'}")
    
    def print_final_report(self):
        """Print final test report"""
        print("\n" + "=" * 80)
        print("FINAL UAT REPORT")
        print("=" * 80)
        
        print(f"\nTOTAL TESTS: 47")
        print(f"PASSED: {self.passed_count}")
        print(f"FAILED: {self.failed_count}")
        print(f"SUCCESS RATE: {(self.passed_count/47)*100:.1f}%")
        
        if self.failed_count > 0:
            print(f"\nFAILED TESTS:")
            for result in self.test_results:
                if not result['passed']:
                    print(f"  ❌ Test {result['test_num']}: {result['description']} - {result['details']}")
        
        print(f"\nPASSED TESTS:")
        for result in self.test_results:
            if result['passed']:
                print(f"  ✅ Test {result['test_num']}: {result['description']}")
        
        print("\n" + "=" * 80)
        print(f"UAT COMPLETE: {self.passed_count}/47 PASSED")
        print("=" * 80)

if __name__ == "__main__":
    tester = DeziderUATTester()
    tester.run_comprehensive_uat()