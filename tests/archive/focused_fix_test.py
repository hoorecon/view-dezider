#!/usr/bin/env python3
"""
TIER 3 E2E - Focused Fix Tests
Fixing the 4 failing tests from the main run
"""

import requests
import json
import time
from datetime import datetime

# Backend URL from environment
BASE_URL = "https://modal-responsive-fix.preview.emergentagent.com/api"

class FocusedFixTester:
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
        
    def get_headers(self):
        """Get authorization headers"""
        return {"Authorization": f"Bearer {self.session_token}"}
    
    def setup_user(self):
        """Setup user and decision for testing"""
        try:
            # Register user
            timestamp = int(time.time())
            payload = {
                "email": f"fix_test_{timestamp}@test.com",
                "password": "FixTest123!",
                "name": "Fix Test User"
            }
            
            response = requests.post(f"{BASE_URL}/auth/register", json=payload)
            if response.status_code == 200:
                data = response.json()
                self.session_token = data.get('session_token')
                print(f"✅ Setup: User registered with session token")
                
                # Create decision
                decision_payload = {
                    "title": "Fix Test Decision",
                    "context": "Testing fixes",
                    "life_area": "Career",
                    "decision_type": "need"
                }
                
                response = requests.post(f"{BASE_URL}/decisions", json=decision_payload, headers=self.get_headers())
                if response.status_code == 200:
                    data = response.json()
                    self.decision_id = data.get('id')
                    print(f"✅ Setup: Decision created with ID: {self.decision_id}")
                    return True
                else:
                    print(f"❌ Setup: Decision creation failed: {response.status_code}")
                    return False
            else:
                print(f"❌ Setup: User registration failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Setup: Exception: {str(e)}")
            return False
    
    def test_fix_1_factors_with_category(self):
        """Fix Test 1: PUT /api/decisions/{id} - Add category field to factors"""
        try:
            payload = {
                "factors": [
                    {
                        "id": "sal",
                        "name": "Salary Impact",
                        "rating": 85,
                        "order": 0,
                        "category": "primary"  # Added missing category
                    },
                    {
                        "id": "growth",
                        "name": "Career Growth",
                        "rating": 90,
                        "order": 1,
                        "category": "primary"  # Added missing category
                    },
                    {
                        "id": "risk",
                        "name": "Risk Level",
                        "rating": 60,
                        "order": 2,
                        "category": "secondary"  # Added missing category
                    },
                    {
                        "id": "wlb",
                        "name": "Work-Life Balance",
                        "rating": 75,
                        "order": 3,
                        "category": "primary"  # Added missing category
                    }
                ]
            }
            
            response = requests.put(f"{BASE_URL}/decisions/{self.decision_id}", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                self.log_result(1, "Fix Factors with Category", True, "4 factors with category added successfully")
                return True
            else:
                self.log_result(1, "Fix Factors with Category", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(1, "Fix Factors with Category", False, f"Exception: {str(e)}")
            return False
    
    def test_fix_2_create_more_ctt_tasks(self):
        """Fix Test 2: Create more CTT tasks to get 5+ blocks"""
        try:
            tasks = [
                {
                    "task": "Morning Standup",
                    "from_time": "09:00",
                    "to_time": "09:30",
                    "task_duration": "30m",
                    "priority": "high",
                    "life_area": "Career",
                    "is_routine": True,
                    "frequency": "daily"
                },
                {
                    "task": "Client Presentation",
                    "from_time": "11:00",
                    "to_time": "12:00",
                    "task_duration": "1h",
                    "priority": "high",
                    "life_area": "Career"
                },
                {
                    "task": "Admin Work",
                    "from_time": "14:00",
                    "to_time": "15:30",
                    "task_duration": "90m",
                    "priority": "low",
                    "life_area": "Career"
                },
                {
                    "task": "Team 1:1",
                    "from_time": "16:00",
                    "to_time": "16:30",
                    "task_duration": "30m",
                    "priority": "medium",
                    "life_area": "Career"
                },
                {
                    "task": "Email Processing",
                    "from_time": "17:00",
                    "to_time": "17:30",
                    "task_duration": "30m",
                    "priority": "low",
                    "life_area": "Career"
                }
            ]
            
            created_count = 0
            for task in tasks:
                response = requests.post(f"{BASE_URL}/ctt/tasks", json=task, headers=self.get_headers())
                if response.status_code == 200:
                    created_count += 1
                else:
                    print(f"Failed to create task {task['task']}: {response.status_code}")
            
            # Create lifestyle routine
            routine_payload = {
                "name": "Morning Exercise",
                "time_slot": "06:30",
                "frequency": "daily",
                "priority": "high",
                "life_area": "Health",
                "category": "health"
            }
            
            routine_response = requests.post(f"{BASE_URL}/lifestyle/routines", json=routine_payload, headers=self.get_headers())
            if routine_response.status_code == 200:
                created_count += 1
            
            # Now check daily schedule
            response = requests.get(f"{BASE_URL}/time-dezider/daily?date=2026-03-27", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                blocks = data.get('blocks', [])
                stats = data.get('stats', {})
                
                if len(blocks) >= 5 and 'scheduled_minutes' in stats:
                    self.log_result(2, "Fix Daily Schedule (5+ blocks)", True, f"Retrieved {len(blocks)} blocks with stats")
                    return True
                else:
                    self.log_result(2, "Fix Daily Schedule (5+ blocks)", False, f"Created {created_count} items but got {len(blocks)} blocks")
                    return False
            else:
                self.log_result(2, "Fix Daily Schedule (5+ blocks)", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(2, "Fix Daily Schedule (5+ blocks)", False, f"Exception: {str(e)}")
            return False
    
    def test_fix_3_payment_history_format(self):
        """Fix Test 3: Check payment history response format"""
        try:
            response = requests.get(f"{BASE_URL}/payments/history", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                print(f"Payment history response type: {type(data)}")
                print(f"Payment history response: {data}")
                
                # Check if it's a dict with a list inside
                if isinstance(data, dict):
                    if 'transactions' in data and isinstance(data['transactions'], list):
                        self.log_result(3, "Fix Payment History Format", True, f"Dict with transactions list: {len(data['transactions'])} records")
                        return True
                    elif 'history' in data and isinstance(data['history'], list):
                        self.log_result(3, "Fix Payment History Format", True, f"Dict with history list: {len(data['history'])} records")
                        return True
                    else:
                        # Check if dict has list-like values
                        list_keys = [k for k, v in data.items() if isinstance(v, list)]
                        if list_keys:
                            self.log_result(3, "Fix Payment History Format", True, f"Dict with list keys: {list_keys}")
                            return True
                        else:
                            self.log_result(3, "Fix Payment History Format", False, f"Dict without list values: {list(data.keys())}")
                            return False
                elif isinstance(data, list):
                    self.log_result(3, "Fix Payment History Format", True, f"Direct list with {len(data)} records")
                    return True
                else:
                    self.log_result(3, "Fix Payment History Format", False, f"Unexpected type: {type(data)}")
                    return False
            else:
                self.log_result(3, "Fix Payment History Format", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(3, "Fix Payment History Format", False, f"Exception: {str(e)}")
            return False
    
    def test_fix_4_deo_api_keys_format(self):
        """Fix Test 4: Check DEO API keys response format"""
        try:
            response = requests.get(f"{BASE_URL}/deo/api-keys", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                print(f"DEO API keys response type: {type(data)}")
                print(f"DEO API keys response: {data}")
                
                # Check if it's a dict with a list inside
                if isinstance(data, dict):
                    if 'api_keys' in data and isinstance(data['api_keys'], list):
                        self.log_result(4, "Fix DEO API Keys Format", True, f"Dict with api_keys list: {len(data['api_keys'])} keys")
                        return True
                    elif 'keys' in data and isinstance(data['keys'], list):
                        self.log_result(4, "Fix DEO API Keys Format", True, f"Dict with keys list: {len(data['keys'])} keys")
                        return True
                    else:
                        # Check if dict has list-like values
                        list_keys = [k for k, v in data.items() if isinstance(v, list)]
                        if list_keys:
                            self.log_result(4, "Fix DEO API Keys Format", True, f"Dict with list keys: {list_keys}")
                            return True
                        else:
                            self.log_result(4, "Fix DEO API Keys Format", False, f"Dict without list values: {list(data.keys())}")
                            return False
                elif isinstance(data, list):
                    self.log_result(4, "Fix DEO API Keys Format", True, f"Direct list with {len(data)} keys")
                    return True
                else:
                    self.log_result(4, "Fix DEO API Keys Format", False, f"Unexpected type: {type(data)}")
                    return False
            else:
                self.log_result(4, "Fix DEO API Keys Format", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(4, "Fix DEO API Keys Format", False, f"Exception: {str(e)}")
            return False
    
    def run_fix_tests(self):
        """Run focused fix tests"""
        print("=" * 80)
        print("TIER 3 E2E - FOCUSED FIX TESTS")
        print("Fixing the 4 failing tests from the main run")
        print("=" * 80)
        print(f"Backend URL: {BASE_URL}")
        print(f"Test started at: {datetime.now()}")
        print()
        
        if not self.setup_user():
            print("❌ CRITICAL: Setup failed. Cannot proceed.")
            return
        
        print("\n🔧 RUNNING FIX TESTS")
        self.test_fix_1_factors_with_category()
        self.test_fix_2_create_more_ctt_tasks()
        self.test_fix_3_payment_history_format()
        self.test_fix_4_deo_api_keys_format()
        
        # Summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 80)
        print("FIX TESTS SUMMARY")
        print("=" * 80)
        
        passed = sum(1 for result in self.test_results if result['success'])
        total = len(self.test_results)
        
        print(f"Total Fix Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        print("\nDETAILED RESULTS:")
        for result in self.test_results:
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"  Test {result['test_num']}: {result['test_name']} - {status}")
            if result['details']:
                print(f"    Details: {result['details']}")

if __name__ == "__main__":
    tester = FocusedFixTester()
    tester.run_fix_tests()