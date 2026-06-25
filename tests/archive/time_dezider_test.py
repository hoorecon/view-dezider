#!/usr/bin/env python3
"""
Time Dezider Fix Verification Test
Quick verification test for Time Dezider functionality as requested
"""

import requests
import json
import time
from datetime import datetime

# Backend URL from environment
BASE_URL = "https://modal-responsive-fix.preview.emergentagent.com/api"

class TimeDeziderTester:
    def __init__(self):
        self.session_token = None
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
        """Test 1: POST /api/auth/register with specific credentials"""
        try:
            payload = {
                "email": "tdfix@test.com",
                "password": "test123",
                "name": "TD Fix"
            }
            
            response = requests.post(f"{BASE_URL}/auth/register", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                self.session_token = data.get('session_token')
                if self.session_token:
                    self.log_result(1, "User Registration", True, f"Session token obtained for tdfix@test.com")
                    return True
                else:
                    self.log_result(1, "User Registration", False, "No session token in response")
                    return False
            else:
                # Try with unique email if user already exists
                timestamp = int(time.time())
                payload["email"] = f"tdfix_{timestamp}@test.com"
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
    
    def test_2_create_ctt_task_1(self):
        """Test 2: POST /api/ctt/tasks - Morning Call"""
        try:
            payload = {
                "task": "Morning Call",
                "from_time": "09:00",
                "to_time": "09:30",
                "task_duration": "30m",
                "priority": "high",
                "life_area": "Career"
            }
            
            response = requests.post(f"{BASE_URL}/ctt/tasks", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                task_id = data.get('task_id') or data.get('id')
                self.log_result(2, "Create CTT Task 1 (Morning Call)", True, f"Task created: {task_id}")
                return True
            else:
                self.log_result(2, "Create CTT Task 1 (Morning Call)", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(2, "Create CTT Task 1 (Morning Call)", False, f"Exception: {str(e)}")
            return False
    
    def test_3_create_ctt_task_2(self):
        """Test 3: POST /api/ctt/tasks - Deep Work"""
        try:
            payload = {
                "task": "Deep Work",
                "from_time": "10:00",
                "to_time": "12:00",
                "task_duration": "2h",
                "priority": "medium",
                "life_area": "Career"
            }
            
            response = requests.post(f"{BASE_URL}/ctt/tasks", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                task_id = data.get('task_id') or data.get('id')
                self.log_result(3, "Create CTT Task 2 (Deep Work)", True, f"Task created: {task_id}")
                return True
            else:
                self.log_result(3, "Create CTT Task 2 (Deep Work)", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(3, "Create CTT Task 2 (Deep Work)", False, f"Exception: {str(e)}")
            return False
    
    def test_4_create_lifestyle_routine(self):
        """Test 4: POST /api/lifestyle/routines - Exercise"""
        try:
            payload = {
                "name": "Exercise",
                "time_slot": "07:00",
                "frequency": "daily",
                "priority": "high",
                "life_area": "Health",
                "category": "health"
            }
            
            response = requests.post(f"{BASE_URL}/lifestyle/routines", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                routine_id = data.get('routine_id') or data.get('id')
                self.log_result(4, "Create Lifestyle Routine (Exercise)", True, f"Routine created: {routine_id}")
                return True
            else:
                self.log_result(4, "Create Lifestyle Routine (Exercise)", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(4, "Create Lifestyle Routine (Exercise)", False, f"Exception: {str(e)}")
            return False
    
    def test_5_get_daily_schedule(self):
        """Test 5: GET /api/time-dezider/daily?date=2026-03-27 - CRITICAL verification"""
        try:
            response = requests.get(f"{BASE_URL}/time-dezider/daily?date=2026-03-27", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for required fields
                if 'blocks' not in data:
                    self.log_result(5, "Get Daily Schedule", False, "Missing 'blocks' field in response")
                    return False
                
                if 'stats' not in data:
                    self.log_result(5, "Get Daily Schedule", False, "Missing 'stats' field in response")
                    return False
                
                blocks = data['blocks']
                stats = data['stats']
                
                # CRITICAL: Verify blocks array contains at LEAST 3 items (2 CTT + 1 Lifestyle)
                if len(blocks) < 3:
                    self.log_result(5, "Get Daily Schedule", False, f"Expected at least 3 blocks, got {len(blocks)}")
                    return False
                
                # Verify stats.total_blocks >= 3
                total_blocks = stats.get('total_blocks', 0)
                if total_blocks < 3:
                    self.log_result(5, "Get Daily Schedule", False, f"Expected stats.total_blocks >= 3, got {total_blocks}")
                    return False
                
                # Verify stats.scheduled_minutes > 0
                scheduled_minutes = stats.get('scheduled_minutes', 0)
                if scheduled_minutes <= 0:
                    self.log_result(5, "Get Daily Schedule", False, f"Expected stats.scheduled_minutes > 0, got {scheduled_minutes}")
                    return False
                
                # Print the number of blocks and their titles
                block_titles = [block.get('title', 'Unknown') for block in blocks]
                details = f"Found {len(blocks)} blocks: {', '.join(block_titles)}. Stats: total_blocks={total_blocks}, scheduled_minutes={scheduled_minutes}"
                
                self.log_result(5, "Get Daily Schedule", True, details)
                return True
            else:
                self.log_result(5, "Get Daily Schedule", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(5, "Get Daily Schedule", False, f"Exception: {str(e)}")
            return False
    
    def test_6_create_unplanned_task(self):
        """Test 6: POST /api/time-dezider/unplanned-task - Urgent Bug Fix"""
        try:
            payload = {
                "date": "2026-03-27",
                "title": "Urgent Bug Fix",
                "duration_minutes": 90,
                "priority": "high"
            }
            
            response = requests.post(f"{BASE_URL}/time-dezider/unplanned-task", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                block_id = data.get('block_id') or data.get('id')
                self.log_result(6, "Create Unplanned Task", True, f"Unplanned task created: {block_id}")
                return True
            else:
                self.log_result(6, "Create Unplanned Task", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(6, "Create Unplanned Task", False, f"Exception: {str(e)}")
            return False
    
    def test_7_verify_updated_schedule(self):
        """Test 7: GET /api/time-dezider/daily?date=2026-03-27 - Verify 4+ blocks"""
        try:
            response = requests.get(f"{BASE_URL}/time-dezider/daily?date=2026-03-27", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for required fields
                if 'blocks' not in data:
                    self.log_result(7, "Verify Updated Schedule", False, "Missing 'blocks' field in response")
                    return False
                
                blocks = data['blocks']
                
                # Verify blocks array now has 4+ items (includes unplanned)
                if len(blocks) < 4:
                    self.log_result(7, "Verify Updated Schedule", False, f"Expected at least 4 blocks after unplanned task, got {len(blocks)}")
                    return False
                
                # Print the number of blocks and their titles
                block_titles = [block.get('title', 'Unknown') for block in blocks]
                details = f"Found {len(blocks)} blocks after unplanned task: {', '.join(block_titles)}"
                
                self.log_result(7, "Verify Updated Schedule", True, details)
                return True
            else:
                self.log_result(7, "Verify Updated Schedule", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(7, "Verify Updated Schedule", False, f"Exception: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        print("=" * 80)
        print("TIME DEZIDER FIX VERIFICATION TEST")
        print("=" * 80)
        print(f"Backend URL: {BASE_URL}")
        print(f"Test started at: {datetime.now()}")
        print()
        
        # Run tests in sequence
        tests = [
            self.test_1_register_user,
            self.test_2_create_ctt_task_1,
            self.test_3_create_ctt_task_2,
            self.test_4_create_lifestyle_routine,
            self.test_5_get_daily_schedule,
            self.test_6_create_unplanned_task,
            self.test_7_verify_updated_schedule
        ]
        
        for test in tests:
            test()
            time.sleep(0.5)  # Small delay between tests
        
        # Summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 80)
        print("TIME DEZIDER TEST SUMMARY")
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
        
        print(f"\n📊 CRITICAL VERIFICATION:")
        critical_tests = [r for r in self.test_results if r['test_num'] in [5, 7]]
        critical_passed = sum(1 for r in critical_tests if r['success'])
        print(f"  Daily Schedule Aggregation: {critical_passed}/{len(critical_tests)} passed")
        
        if critical_passed == len(critical_tests):
            print("\n🎉 TIME DEZIDER FIX VERIFICATION: SUCCESS!")
            print("   - Daily schedule properly aggregates CTT + Lifestyle blocks")
            print("   - Unplanned task integration working correctly")
        else:
            print("\n❌ TIME DEZIDER FIX VERIFICATION: FAILED!")
            print("   - Critical issues found in daily schedule aggregation")

if __name__ == "__main__":
    tester = TimeDeziderTester()
    tester.run_all_tests()