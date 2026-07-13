#!/usr/bin/env python3
"""
Lifestyle Dezider Backend Testing
Test suite for the new Lifestyle Dezider backlog endpoints as specified in review request
"""

import asyncio
import httpx
import json
import sys
from datetime import datetime

# Backend URL from frontend/.env
BASE_URL = "https://repo-blueprint-1.preview.emergentagent.com/api"

class LifestyleDeziderTestSuite:
    def __init__(self):
        self.base_url = BASE_URL
        self.session_token = None
        self.user_id = None
        self.test_results = []
        self.routine_id_1 = None
        self.routine_id_2 = None
        self.ctt_task_id = None
        
    async def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        result = f"{status}: {test_name}"
        if details:
            result += f" - {details}"
        print(result)
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details
        })
        
    async def make_request(self, method: str, endpoint: str, data: dict = None, headers: dict = None):
        """Make HTTP request with error handling"""
        url = f"{self.base_url}{endpoint}"
        request_headers = {}
        
        if self.session_token:
            request_headers["Authorization"] = f"Bearer {self.session_token}"
            
        if headers:
            request_headers.update(headers)
            
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=request_headers)
                elif method.upper() == "POST":
                    response = await client.post(url, json=data, headers=request_headers)
                elif method.upper() == "PUT":
                    response = await client.put(url, json=data, headers=request_headers)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=request_headers)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                    
                return response
        except Exception as e:
            print(f"Request failed: {method} {url} - {str(e)}")
            return None

    async def test_1_register_user(self):
        """Test 1: Register user as specified in review request"""
        test_name = "Register User"
        
        user_data = {
            "email": "life_test@test.com",
            "password": "LifeTest123!",
            "name": "Life Tester"
        }
        
        response = await self.make_request("POST", "/auth/register", user_data)
        
        if response and response.status_code == 200:
            data = response.json()
            self.session_token = data.get("session_token")
            self.user_id = data.get("user_id")
            await self.log_result(test_name, True, f"User registered with ID: {self.user_id}")
            return True
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False

    async def test_2_create_routine_1(self):
        """Test 2: Create first routine - Morning Meditation"""
        test_name = "Create Morning Meditation Routine"
        
        routine_data = {
            "name": "Morning Meditation",
            "description": "15 min mindfulness meditation",
            "life_area": "health",
            "frequency": "daily",
            "time_slot": "06:30",
            "priority": "critical",
            "category": "primary"
        }
        
        response = await self.make_request("POST", "/lifestyle/routines", routine_data)
        
        if response and response.status_code == 200:
            data = response.json()
            self.routine_id_1 = data.get("routine_id")
            await self.log_result(test_name, True, f"Routine created with ID: {self.routine_id_1}")
            return True
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False

    async def test_3_create_routine_2(self):
        """Test 3: Create second routine - Weekly Review"""
        test_name = "Create Weekly Review Routine"
        
        routine_data = {
            "name": "Weekly Review",
            "description": "Review weekly goals",
            "life_area": "career",
            "frequency": "weekly",
            "time_slot": "18:00",
            "priority": "high",
            "category": "supporting"
        }
        
        response = await self.make_request("POST", "/lifestyle/routines", routine_data)
        
        if response and response.status_code == 200:
            data = response.json()
            self.routine_id_2 = data.get("routine_id")
            await self.log_result(test_name, True, f"Routine created with ID: {self.routine_id_2}")
            return True
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False

    async def test_4_get_today_status_initial(self):
        """Test 4: Get today's status - should show routines due today with completed_today: false"""
        test_name = "Get Today's Status (Initial)"
        
        response = await self.make_request("GET", "/lifestyle/today-status")
        
        if response and response.status_code == 200:
            data = response.json()
            routines = data.get("routines", [])
            completed = data.get("completed", 0)
            completion_rate = data.get("completion_rate", 0)
            
            # Should have at least the daily routine (Morning Meditation) due today
            daily_routines = [r for r in routines if r.get("frequency") == "daily"]
            has_daily = len(daily_routines) > 0
            all_incomplete = all(not r.get("completed_today", True) for r in routines)
            
            success = has_daily and all_incomplete and completed == 0 and completion_rate == 0
            await self.log_result(test_name, success, f"Routines due: {len(routines)}, Completed: {completed}, Rate: {completion_rate}%")
            return success
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False

    async def test_5_mark_routine_complete(self):
        """Test 5: Mark first routine complete with notes"""
        test_name = "Mark First Routine Complete"
        
        if not self.routine_id_1:
            await self.log_result(test_name, False, "No routine ID available")
            return False
        
        completion_data = {
            "notes": "Good session today"
        }
        
        response = await self.make_request("POST", f"/lifestyle/routines/{self.routine_id_1}/complete", completion_data)
        
        if response and response.status_code == 200:
            data = response.json()
            current_streak = data.get("current_streak", 0)
            message = data.get("message", "")
            
            success = current_streak == 1 and "completed" in message.lower()
            await self.log_result(test_name, success, f"Message: {message}, Streak: {current_streak}")
            return success
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False

    async def test_6_get_today_status_updated(self):
        """Test 6: Get today's status again - should show completed: 1, higher completion_rate"""
        test_name = "Get Today's Status (After Completion)"
        
        response = await self.make_request("GET", "/lifestyle/today-status")
        
        if response and response.status_code == 200:
            data = response.json()
            completed = data.get("completed", 0)
            completion_rate = data.get("completion_rate", 0)
            routines = data.get("routines", [])
            
            # Should have at least 1 completed routine and higher completion rate
            success = completed >= 1 and completion_rate > 0
            await self.log_result(test_name, success, f"Completed: {completed}, Rate: {completion_rate}%, Total due: {len(routines)}")
            return success
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False

    async def test_7_try_complete_again(self):
        """Test 7: Try completing same routine again - should return 400 'Already completed today'"""
        test_name = "Try Complete Same Routine Again"
        
        if not self.routine_id_1:
            await self.log_result(test_name, False, "No routine ID available")
            return False
        
        response = await self.make_request("POST", f"/lifestyle/routines/{self.routine_id_1}/complete", {})
        
        if response and response.status_code == 400:
            error_text = response.text
            success = "already completed" in error_text.lower()
            await self.log_result(test_name, success, f"Got expected 400 error: {error_text}")
            return success
        else:
            await self.log_result(test_name, False, f"Expected 400 but got: {response.status_code if response else 'None'}")
            return False

    async def test_8_undo_completion(self):
        """Test 8: Undo completion"""
        test_name = "Undo Completion"
        
        if not self.routine_id_1:
            await self.log_result(test_name, False, "No routine ID available")
            return False
        
        response = await self.make_request("DELETE", f"/lifestyle/routines/{self.routine_id_1}/uncomplete")
        
        if response and response.status_code == 200:
            data = response.json()
            message = data.get("message", "")
            success = "undone" in message.lower() or "removed" in message.lower()
            await self.log_result(test_name, success, f"Message: {message}")
            return success
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False

    async def test_9_re_complete_routine(self):
        """Test 9: Re-complete the routine - should succeed"""
        test_name = "Re-complete Routine"
        
        if not self.routine_id_1:
            await self.log_result(test_name, False, "No routine ID available")
            return False
        
        completion_data = {
            "notes": "Second completion today"
        }
        
        response = await self.make_request("POST", f"/lifestyle/routines/{self.routine_id_1}/complete", completion_data)
        
        if response and response.status_code == 200:
            data = response.json()
            message = data.get("message", "")
            current_streak = data.get("current_streak", 0)
            success = "completed" in message.lower()
            await self.log_result(test_name, success, f"Message: {message}, Streak: {current_streak}")
            return success
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False

    async def test_10_get_completion_history(self):
        """Test 10: Get completion history - should show 1 completion"""
        test_name = "Get Completion History"
        
        if not self.routine_id_1:
            await self.log_result(test_name, False, "No routine ID available")
            return False
        
        response = await self.make_request("GET", f"/lifestyle/routines/{self.routine_id_1}/completions?days=30")
        
        if response and response.status_code == 200:
            data = response.json()
            completions = data.get("completions", [])
            total = data.get("total", 0)
            
            success = total >= 1 and len(completions) >= 1
            await self.log_result(test_name, success, f"Total completions: {total}, History entries: {len(completions)}")
            return success
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False

    async def test_11_create_ctt_task(self):
        """Test 11: Create a CTT task to test auto-detect"""
        test_name = "Create CTT Task for Auto-detect"
        
        ctt_task_data = {
            "task": "Daily exercise routine",
            "sub_task": "30 min workout",
            "life_area": "health",
            "frequency": "daily",
            "priority": "high",
            "is_routine": True
        }
        
        response = await self.make_request("POST", "/ctt/tasks", ctt_task_data)
        
        if response and response.status_code == 200:
            data = response.json()
            self.ctt_task_id = data.get("task_id")
            await self.log_result(test_name, True, f"CTT task created with ID: {self.ctt_task_id}")
            return True
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False

    async def test_12_auto_detect_routines(self):
        """Test 12: Auto-detect routines from CTT - should find the task with high confidence"""
        test_name = "Auto-detect Routines from CTT"
        
        response = await self.make_request("POST", "/lifestyle/auto-detect-from-ctt")
        
        if response and response.status_code == 200:
            data = response.json()
            suggestions = data.get("suggestions", [])
            total_found = data.get("total_found", 0)
            
            # Should find the CTT task we created
            found_our_task = any(s.get("task_id") == self.ctt_task_id for s in suggestions)
            high_confidence = any(s.get("confidence_score", 0) >= 5 for s in suggestions if s.get("task_id") == self.ctt_task_id)
            
            success = found_our_task and high_confidence and total_found > 0
            await self.log_result(test_name, success, f"Found {total_found} suggestions, Our task found: {found_our_task}, High confidence: {high_confidence}")
            return success
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False

    async def test_13_bulk_import_from_ctt(self):
        """Test 13: Bulk import from CTT - should import 1 routine"""
        test_name = "Bulk Import from CTT"
        
        if not self.ctt_task_id:
            await self.log_result(test_name, False, "No CTT task ID available")
            return False
        
        import_data = {
            "task_ids": [self.ctt_task_id]
        }
        
        response = await self.make_request("POST", "/lifestyle/bulk-import-from-ctt", import_data)
        
        if response and response.status_code == 200:
            data = response.json()
            imported = data.get("imported", 0)
            total_requested = data.get("total_requested", 0)
            
            success = imported == 1 and total_requested == 1
            await self.log_result(test_name, success, f"Imported: {imported}, Requested: {total_requested}")
            return success
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False

    async def test_14_verify_imported_routine(self):
        """Test 14: Verify imported routine appears - should now show 3 routines"""
        test_name = "Verify Imported Routine Appears"
        
        response = await self.make_request("GET", "/lifestyle/routines")
        
        if response and response.status_code == 200:
            routines = response.json()
            total_routines = len(routines)
            
            # Should have 3 routines now (2 created + 1 imported)
            success = total_routines >= 3
            
            # Check if our imported routine is there
            imported_routine = any(r.get("source_ctt_task_id") == self.ctt_task_id for r in routines)
            
            await self.log_result(test_name, success and imported_routine, f"Total routines: {total_routines}, Imported routine found: {imported_routine}")
            return success and imported_routine
        else:
            error_msg = response.text if response else "No response"
            await self.log_result(test_name, False, f"Status: {response.status_code if response else 'None'}, Error: {error_msg}")
            return False

    async def test_15_calendar_sync_without_connection(self):
        """Test 15: Test calendar sync without connection - should return 401 'Calendar not connected'"""
        test_name = "Calendar Sync Without Connection"
        
        if not self.routine_id_1:
            await self.log_result(test_name, False, "No routine ID available")
            return False
        
        sync_data = {
            "timezone": "Asia/Kolkata"
        }
        
        response = await self.make_request("POST", f"/lifestyle/routines/{self.routine_id_1}/sync-calendar", sync_data)
        
        if response and response.status_code == 401:
            error_text = response.text
            success = "not connected" in error_text.lower() or "calendar" in error_text.lower()
            await self.log_result(test_name, success, f"Got expected 401 error: {error_text}")
            return success
        else:
            await self.log_result(test_name, False, f"Expected 401 but got: {response.status_code if response else 'None'}")
            return False

    async def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Lifestyle Dezider Backend Testing")
        print("=" * 60)
        
        tests = [
            self.test_1_register_user,
            self.test_2_create_routine_1,
            self.test_3_create_routine_2,
            self.test_4_get_today_status_initial,
            self.test_5_mark_routine_complete,
            self.test_6_get_today_status_updated,
            self.test_7_try_complete_again,
            self.test_8_undo_completion,
            self.test_9_re_complete_routine,
            self.test_10_get_completion_history,
            self.test_11_create_ctt_task,
            self.test_12_auto_detect_routines,
            self.test_13_bulk_import_from_ctt,
            self.test_14_verify_imported_routine,
            self.test_15_calendar_sync_without_connection,
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            try:
                result = await test()
                if result:
                    passed += 1
            except Exception as e:
                print(f"❌ FAIL: {test.__name__} - Exception: {str(e)}")
                
        print("\n" + "=" * 60)
        print(f"🎯 TEST SUMMARY: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED! Lifestyle Dezider backlog endpoints are working correctly.")
        else:
            print(f"⚠️  {total - passed} tests failed. Please check the implementation.")
            
        return passed == total

async def main():
    """Main test runner"""
    test_suite = LifestyleDeziderTestSuite()
    success = await test_suite.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())