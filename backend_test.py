#!/usr/bin/env python3
"""
Time Dezider + Time Store Backend Testing
Tests all endpoints in sequence as specified in the review request.
"""

import requests
import json
import time
from datetime import datetime, timezone

# Backend URL
BASE_URL = "https://dezider-core.preview.emergentagent.com/api"

class TimeDezizerTester:
    def __init__(self):
        self.session_token = None
        self.user_data = None
        self.created_tasks = []
        self.created_routines = []
        self.unplanned_block_id = None
        
    def log(self, message):
        """Log test progress"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        
    def make_request(self, method, endpoint, data=None, params=None):
        """Make authenticated API request"""
        url = f"{BASE_URL}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.session_token}" if self.session_token else None
        }
        headers = {k: v for k, v in headers.items() if v is not None}
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=headers, json=data)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
                
            return response
        except Exception as e:
            self.log(f"❌ Request failed: {str(e)}")
            return None
    
    def test_user_registration(self):
        """Step 1: Register user"""
        self.log("🔧 Step 1: User Registration")
        
        user_data = {
            "email": "timetest@test.com",
            "password": "test123",
            "name": "Time Tester"
        }
        
        response = self.make_request("POST", "/auth/register", user_data)
        
        if response and response.status_code == 200:
            data = response.json()
            self.session_token = data.get("session_token")
            self.user_data = data
            self.log(f"✅ User registered successfully: {data.get('name')} ({data.get('email')})")
            self.log(f"   Session token: {self.session_token[:20]}...")
            return True
        else:
            self.log(f"❌ Registration failed: {response.status_code if response else 'No response'}")
            if response:
                self.log(f"   Error: {response.text}")
            return False
    
    def test_ctt_tasks_creation(self):
        """Step 2: Create CTT Tasks with from_time/to_time"""
        self.log("🔧 Step 2: Creating CTT Tasks with Time Slots")
        
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
                "task": "Deep Work Session",
                "from_time": "10:00",
                "to_time": "12:00",
                "task_duration": "2h",
                "priority": "high",
                "life_area": "Career"
            },
            {
                "task": "Lunch Break",
                "from_time": "12:00",
                "to_time": "13:00",
                "task_duration": "1h",
                "priority": "low",
                "life_area": "Health",
                "is_routine": True,
                "frequency": "daily"
            },
            {
                "task": "Team Meeting",
                "from_time": "14:00",
                "to_time": "15:00",
                "task_duration": "1h",
                "priority": "medium",
                "life_area": "Career"
            },
            {
                "task": "Email Processing",
                "from_time": "16:00",
                "to_time": "17:00",
                "task_duration": "1h",
                "priority": "low",
                "life_area": "Career",
                "is_routine": True,
                "frequency": "daily"
            }
        ]
        
        success_count = 0
        for i, task_data in enumerate(tasks, 3):
            self.log(f"   Creating task {i-2}/5: {task_data['task']}")
            response = self.make_request("POST", "/ctt/tasks", task_data)
            
            if response and response.status_code == 200:
                data = response.json()
                self.created_tasks.append(data)
                self.log(f"   ✅ Created: {data.get('task')} ({data.get('from_time')} - {data.get('to_time')})")
                success_count += 1
            else:
                self.log(f"   ❌ Failed to create task: {response.status_code if response else 'No response'}")
                if response:
                    self.log(f"      Error: {response.text}")
        
        self.log(f"✅ CTT Tasks created: {success_count}/5")
        return success_count == 5
    
    def test_lifestyle_routines_creation(self):
        """Step 3: Create Lifestyle Routines"""
        self.log("🔧 Step 3: Creating Lifestyle Routines")
        
        routines = [
            {
                "name": "Morning Exercise",
                "time_slot": "06:30",
                "frequency": "daily",
                "priority": "high",
                "life_area": "Health",
                "category": "health"
            },
            {
                "name": "Evening Meditation",
                "time_slot": "21:00",
                "frequency": "daily",
                "priority": "medium",
                "life_area": "Mental_Health",
                "category": "wellness"
            }
        ]
        
        success_count = 0
        for i, routine_data in enumerate(routines, 8):
            self.log(f"   Creating routine {i-7}/2: {routine_data['name']}")
            response = self.make_request("POST", "/lifestyle/routines", routine_data)
            
            if response and response.status_code == 200:
                data = response.json()
                self.created_routines.append(data)
                self.log(f"   ✅ Created: {data.get('name')} at {data.get('time_slot')}")
                success_count += 1
            else:
                self.log(f"   ❌ Failed to create routine: {response.status_code if response else 'No response'}")
                if response:
                    self.log(f"      Error: {response.text}")
        
        self.log(f"✅ Lifestyle Routines created: {success_count}/2")
        return success_count == 2
    
    def test_time_dezider_preferences(self):
        """Step 4: Test Time Dezider Preferences"""
        self.log("🔧 Step 4: Testing Time Dezider Preferences")
        
        # Get default preferences
        self.log("   Getting default preferences...")
        response = self.make_request("GET", "/time-dezider/preferences")
        
        if response and response.status_code == 200:
            prefs = response.json()
            self.log(f"   ✅ Default preferences: day_start={prefs.get('day_start')}, day_end={prefs.get('day_end')}")
        else:
            self.log(f"   ❌ Failed to get preferences: {response.status_code if response else 'No response'}")
            return False
        
        # Update preferences
        self.log("   Updating preferences...")
        update_data = {
            "day_start": "06:00",
            "day_end": "22:00"
        }
        response = self.make_request("PUT", "/time-dezider/preferences", update_data)
        
        if response and response.status_code == 200:
            updated_prefs = response.json()
            self.log(f"   ✅ Updated preferences: day_start={updated_prefs.get('day_start')}, day_end={updated_prefs.get('day_end')}")
            return True
        else:
            self.log(f"   ❌ Failed to update preferences: {response.status_code if response else 'No response'}")
            return False
    
    def test_daily_schedule_aggregation(self):
        """Step 5: Test Daily Schedule Aggregation"""
        self.log("🔧 Step 5: Testing Daily Schedule Aggregation")
        
        params = {"date": "2026-03-26"}
        response = self.make_request("GET", "/time-dezider/daily", params=params)
        
        if response and response.status_code == 200:
            data = response.json()
            blocks = data.get("blocks", [])
            stats = data.get("stats", {})
            
            self.log(f"   ✅ Daily schedule retrieved for {data.get('date')}")
            self.log(f"   📊 Stats:")
            self.log(f"      - Total blocks: {stats.get('total_blocks', 0)}")
            self.log(f"      - Scheduled minutes: {stats.get('scheduled_minutes', 0)}")
            self.log(f"      - Free minutes: {stats.get('free_minutes', 0)}")
            self.log(f"      - Utilization: {stats.get('utilization_percent', 0)}%")
            
            # Verify we have blocks from CTT and Lifestyle
            ctt_blocks = [b for b in blocks if b.get("source_type") == "ctt"]
            lifestyle_blocks = [b for b in blocks if b.get("source_type") == "lifestyle"]
            
            self.log(f"   📋 Block breakdown:")
            self.log(f"      - CTT tasks: {len(ctt_blocks)}")
            self.log(f"      - Lifestyle routines: {len(lifestyle_blocks)}")
            
            # Verify required fields in response
            required_fields = ["blocks", "stats"]
            required_stats = ["scheduled_minutes", "free_minutes", "utilization_percent"]
            
            missing_fields = [f for f in required_fields if f not in data]
            missing_stats = [s for s in required_stats if s not in stats]
            
            if not missing_fields and not missing_stats:
                self.log("   ✅ All required fields present in response")
                return True
            else:
                self.log(f"   ❌ Missing fields: {missing_fields + missing_stats}")
                return False
        else:
            self.log(f"   ❌ Failed to get daily schedule: {response.status_code if response else 'No response'}")
            if response:
                self.log(f"      Error: {response.text}")
            return False
    
    def test_unplanned_task_workflow(self):
        """Step 6: Test Unplanned Task Workflow"""
        self.log("🔧 Step 6: Testing Unplanned Task Workflow")
        
        # Add unplanned task
        self.log("   Adding unplanned task...")
        unplanned_data = {
            "date": "2026-03-26",
            "title": "Urgent Client Call",
            "duration_minutes": 60,
            "priority": "high"
        }
        
        response = self.make_request("POST", "/time-dezider/unplanned-task", unplanned_data)
        
        if response and response.status_code == 200:
            data = response.json()
            self.unplanned_block_id = data.get("block_id")
            self.log(f"   ✅ Unplanned task created: {data.get('title')} (ID: {self.unplanned_block_id})")
        else:
            self.log(f"   ❌ Failed to create unplanned task: {response.status_code if response else 'No response'}")
            return False
        
        # Verify it appears in daily schedule
        self.log("   Verifying unplanned task in daily schedule...")
        params = {"date": "2026-03-26"}
        response = self.make_request("GET", "/time-dezider/daily", params=params)
        
        if response and response.status_code == 200:
            data = response.json()
            blocks = data.get("blocks", [])
            unplanned_blocks = [b for b in blocks if b.get("source_type") == "unplanned"]
            
            if unplanned_blocks:
                self.log(f"   ✅ Unplanned task found in schedule: {len(unplanned_blocks)} unplanned block(s)")
            else:
                self.log("   ❌ Unplanned task not found in daily schedule")
                return False
        else:
            self.log("   ❌ Failed to verify unplanned task in schedule")
            return False
        
        # Delete unplanned task
        if self.unplanned_block_id:
            self.log("   Deleting unplanned task...")
            response = self.make_request("DELETE", f"/time-dezider/unplanned-task/{self.unplanned_block_id}")
            
            if response and response.status_code == 200:
                self.log("   ✅ Unplanned task deleted successfully")
                return True
            else:
                self.log(f"   ❌ Failed to delete unplanned task: {response.status_code if response else 'No response'}")
                return False
        
        return True
    
    def test_time_store_budget(self):
        """Step 7: Test Time Store Budget Analysis"""
        self.log("🔧 Step 7: Testing Time Store Budget Analysis")
        
        # Test daily budget
        self.log("   Getting daily time budget...")
        params = {"period": "daily"}
        response = self.make_request("GET", "/time-store/budget", params=params)
        
        if response and response.status_code == 200:
            data = response.json()
            self.log(f"   ✅ Daily budget retrieved:")
            self.log(f"      - Available minutes: {data.get('available_minutes', 0)}")
            self.log(f"      - Committed minutes: {data.get('committed_minutes', 0)}")
            self.log(f"      - Free minutes: {data.get('free_minutes', 0)}")
            self.log(f"      - Utilization: {data.get('utilization_percent', 0)}%")
            
            # Verify required fields
            required_fields = ["by_area", "by_type", "items"]
            missing_fields = [f for f in required_fields if f not in data]
            
            if not missing_fields:
                by_area = data.get("by_area", {})
                by_type = data.get("by_type", {})
                items = data.get("items", [])
                
                self.log(f"      - By area: {len(by_area)} areas")
                self.log(f"      - By type: {len(by_type)} types")
                self.log(f"      - Items: {len(items)} items")
                
                daily_success = True
            else:
                self.log(f"   ❌ Missing fields in daily budget: {missing_fields}")
                daily_success = False
        else:
            self.log(f"   ❌ Failed to get daily budget: {response.status_code if response else 'No response'}")
            daily_success = False
        
        # Test weekly budget
        self.log("   Getting weekly time budget...")
        params = {"period": "weekly"}
        response = self.make_request("GET", "/time-store/budget", params=params)
        
        if response and response.status_code == 200:
            data = response.json()
            self.log(f"   ✅ Weekly budget retrieved:")
            self.log(f"      - Available minutes: {data.get('available_minutes', 0)}")
            self.log(f"      - Committed minutes: {data.get('committed_minutes', 0)}")
            self.log(f"      - Free minutes: {data.get('free_minutes', 0)}")
            self.log(f"      - Utilization: {data.get('utilization_percent', 0)}%")
            weekly_success = True
        else:
            self.log(f"   ❌ Failed to get weekly budget: {response.status_code if response else 'No response'}")
            weekly_success = False
        
        return daily_success and weekly_success
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        self.log("🚀 Starting Time Dezider + Time Store Backend Testing")
        self.log("=" * 60)
        
        test_results = []
        
        # Step 1: User Registration
        test_results.append(("User Registration", self.test_user_registration()))
        
        if not self.session_token:
            self.log("❌ Cannot continue without authentication")
            return False
        
        # Step 2: Create CTT Tasks
        test_results.append(("CTT Tasks Creation", self.test_ctt_tasks_creation()))
        
        # Step 3: Create Lifestyle Routines
        test_results.append(("Lifestyle Routines Creation", self.test_lifestyle_routines_creation()))
        
        # Step 4: Test Time Dezider Preferences
        test_results.append(("Time Dezider Preferences", self.test_time_dezider_preferences()))
        
        # Step 5: Test Daily Schedule Aggregation
        test_results.append(("Daily Schedule Aggregation", self.test_daily_schedule_aggregation()))
        
        # Step 6: Test Unplanned Task Workflow
        test_results.append(("Unplanned Task Workflow", self.test_unplanned_task_workflow()))
        
        # Step 7: Test Time Store Budget
        test_results.append(("Time Store Budget Analysis", self.test_time_store_budget()))
        
        # Summary
        self.log("=" * 60)
        self.log("📊 TEST RESULTS SUMMARY")
        self.log("=" * 60)
        
        passed = 0
        total = len(test_results)
        
        for test_name, result in test_results:
            status = "✅ PASSED" if result else "❌ FAILED"
            self.log(f"{status} - {test_name}")
            if result:
                passed += 1
        
        self.log("=" * 60)
        self.log(f"🎯 OVERALL RESULT: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
        
        if passed == total:
            self.log("🎉 ALL TESTS PASSED! Time Dezider + Time Store backend is working correctly.")
            return True
        else:
            self.log(f"⚠️  {total - passed} test(s) failed. Please check the logs above for details.")
            return False

def main():
    """Main test execution"""
    tester = TimeDezizerTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 Time Dezider + Time Store backend testing completed successfully!")
        exit(0)
    else:
        print("\n❌ Some tests failed. Please review the output above.")
        exit(1)

if __name__ == "__main__":
    main()