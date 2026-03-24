#!/usr/bin/env python3
"""
Comprehensive Backend Testing for Lifestyle Dezider and Lifestyle Analyzer
Tests all endpoints mentioned in the review request.
"""

import asyncio
import httpx
import json
import time
from datetime import datetime, timezone

# Backend URL from environment
BACKEND_URL = "https://prr-actions-central.preview.emergentagent.com/api"

class LifestyleBackendTester:
    def __init__(self):
        self.session_token = None
        self.user_data = None
        self.created_routines = []
        self.created_assessments = []
        self.created_ctt_tasks = []
        
    async def register_user(self):
        """Register a new user for testing"""
        timestamp = int(time.time())
        email = f"lifestyle.tester.{timestamp}@routinemaster.com"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BACKEND_URL}/auth/register", json={
                "email": email,
                "password": "lifestyle123",
                "name": f"Lifestyle Tester {timestamp}"
            })
            
            if response.status_code != 200:
                raise Exception(f"Registration failed: {response.status_code} - {response.text}")
            
            data = response.json()
            self.session_token = data["session_token"]
            self.user_data = data
            print(f"✅ User registered: {email}")
            return data
    
    def get_headers(self):
        """Get authorization headers"""
        return {"Authorization": f"Bearer {self.session_token}"}
    
    async def test_routine_crud(self):
        """Test Lifestyle Routine CRUD operations"""
        print("\n🧪 Testing Lifestyle Routine CRUD...")
        
        async with httpx.AsyncClient() as client:
            # Test 1: Create Morning Meditation routine
            routine1_data = {
                "name": "Morning Meditation",
                "description": "20 min guided meditation",
                "life_area": "spirituality_religion",
                "frequency": "daily",
                "time_slot": "6:00 AM - 6:20 AM",
                "priority": "high",
                "category": "primary",
                "expected_value": "20",
                "unit": "minutes",
                "is_active": True
            }
            
            response = await client.post(
                f"{BACKEND_URL}/lifestyle/routines",
                json=routine1_data,
                headers=self.get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"Create routine 1 failed: {response.status_code} - {response.text}")
            
            routine1 = response.json()
            self.created_routines.append(routine1)
            print(f"✅ Created routine 1: {routine1['name']} (ID: {routine1['routine_id']})")
            
            # Test 2: Create Weekly Exercise Plan Review routine
            routine2_data = {
                "name": "Weekly Exercise Plan Review",
                "description": "Review and adjust weekly exercise schedule",
                "life_area": "holistic_health",
                "frequency": "weekly",
                "priority": "medium",
                "category": "secondary",
                "is_active": True
            }
            
            response = await client.post(
                f"{BACKEND_URL}/lifestyle/routines",
                json=routine2_data,
                headers=self.get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"Create routine 2 failed: {response.status_code} - {response.text}")
            
            routine2 = response.json()
            self.created_routines.append(routine2)
            print(f"✅ Created routine 2: {routine2['name']} (ID: {routine2['routine_id']})")
            
            # Test 3: Create Monthly Budget Review routine
            routine3_data = {
                "name": "Monthly Budget Review",
                "description": "Review monthly expenses and budget allocation",
                "life_area": "finance",
                "frequency": "monthly",
                "priority": "high",
                "category": "primary",
                "is_active": True
            }
            
            response = await client.post(
                f"{BACKEND_URL}/lifestyle/routines",
                json=routine3_data,
                headers=self.get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"Create routine 3 failed: {response.status_code} - {response.text}")
            
            routine3 = response.json()
            self.created_routines.append(routine3)
            print(f"✅ Created routine 3: {routine3['name']} (ID: {routine3['routine_id']})")
            
            # Test 4: List all routines (should return 3)
            response = await client.get(
                f"{BACKEND_URL}/lifestyle/routines",
                headers=self.get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"List routines failed: {response.status_code} - {response.text}")
            
            all_routines = response.json()
            if len(all_routines) != 3:
                raise Exception(f"Expected 3 routines, got {len(all_routines)}")
            
            print(f"✅ Listed all routines: {len(all_routines)} routines found")
            
            # Test 5: Filter by frequency (daily)
            response = await client.get(
                f"{BACKEND_URL}/lifestyle/routines?frequency=daily",
                headers=self.get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"Filter by frequency failed: {response.status_code} - {response.text}")
            
            daily_routines = response.json()
            if len(daily_routines) != 1:
                raise Exception(f"Expected 1 daily routine, got {len(daily_routines)}")
            
            print(f"✅ Filtered by frequency (daily): {len(daily_routines)} routines found")
            
            # Test 6: Get single routine
            routine_id = routine1['routine_id']
            response = await client.get(
                f"{BACKEND_URL}/lifestyle/routines/{routine_id}",
                headers=self.get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"Get single routine failed: {response.status_code} - {response.text}")
            
            single_routine = response.json()
            if single_routine['routine_id'] != routine_id:
                raise Exception(f"Wrong routine returned: expected {routine_id}, got {single_routine['routine_id']}")
            
            print(f"✅ Retrieved single routine: {single_routine['name']}")
            
            # Test 7: Update routine (change priority)
            update_data = {"priority": "medium"}
            response = await client.put(
                f"{BACKEND_URL}/lifestyle/routines/{routine_id}",
                json=update_data,
                headers=self.get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"Update routine failed: {response.status_code} - {response.text}")
            
            updated_routine = response.json()
            if updated_routine['priority'] != 'medium':
                raise Exception(f"Priority not updated: expected 'medium', got {updated_routine['priority']}")
            
            print(f"✅ Updated routine priority: {updated_routine['priority']}")
            
            # Test 8: Delete last routine
            routine_to_delete_id = routine3['routine_id']
            response = await client.delete(
                f"{BACKEND_URL}/lifestyle/routines/{routine_to_delete_id}",
                headers=self.get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"Delete routine failed: {response.status_code} - {response.text}")
            
            print(f"✅ Deleted routine: {routine3['name']}")
            
            # Test 9: Recreate the deleted routine
            response = await client.post(
                f"{BACKEND_URL}/lifestyle/routines",
                json=routine3_data,
                headers=self.get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"Recreate routine failed: {response.status_code} - {response.text}")
            
            recreated_routine = response.json()
            self.created_routines[2] = recreated_routine  # Update our tracking
            print(f"✅ Recreated routine: {recreated_routine['name']} (ID: {recreated_routine['routine_id']})")
            
            # Test 10: Check dashboard stats
            response = await client.get(
                f"{BACKEND_URL}/lifestyle/dashboard",
                headers=self.get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"Dashboard failed: {response.status_code} - {response.text}")
            
            dashboard = response.json()
            expected_fields = ['total_routines', 'active_routines', 'by_frequency', 'by_area']
            for field in expected_fields:
                if field not in dashboard:
                    raise Exception(f"Dashboard missing field: {field}")
            
            if dashboard['active_routines'] != 3:
                raise Exception(f"Expected 3 active routines in dashboard, got {dashboard['active_routines']}")
            
            print(f"✅ Dashboard stats: {dashboard['active_routines']} active routines, by_frequency: {dashboard['by_frequency']}")
            
            return True
    
    async def test_lifestyle_assessment(self):
        """Test Lifestyle Assessment (PRR-based) functionality"""
        print("\n🧪 Testing Lifestyle Assessment (PRR-based)...")
        
        async with httpx.AsyncClient() as client:
            # Test 1: Start daily assessment
            response = await client.post(
                f"{BACKEND_URL}/lifestyle/start-assessment",
                json={"period": "daily"},
                headers=self.get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"Start daily assessment failed: {response.status_code} - {response.text}")
            
            daily_assessment = response.json()
            required_fields = ['decision_id', 'factors_count', 'period']
            for field in required_fields:
                if field not in daily_assessment:
                    raise Exception(f"Daily assessment missing field: {field}")
            
            if daily_assessment['period'] != 'daily':
                raise Exception(f"Expected period 'daily', got {daily_assessment['period']}")
            
            # Should match number of daily routines (1 from our test data)
            if daily_assessment['factors_count'] != 1:
                raise Exception(f"Expected 1 daily routine factor, got {daily_assessment['factors_count']}")
            
            self.created_assessments.append(daily_assessment)
            print(f"✅ Started daily assessment: {daily_assessment['factors_count']} factors, decision_id: {daily_assessment['decision_id']}")
            
            # Test 2: Start weekly assessment
            response = await client.post(
                f"{BACKEND_URL}/lifestyle/start-assessment",
                json={"period": "weekly"},
                headers=self.get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"Start weekly assessment failed: {response.status_code} - {response.text}")
            
            weekly_assessment = response.json()
            if weekly_assessment['period'] != 'weekly':
                raise Exception(f"Expected period 'weekly', got {weekly_assessment['period']}")
            
            # Should include daily + weekly routines (2 from our test data)
            if weekly_assessment['factors_count'] != 2:
                raise Exception(f"Expected 2 weekly routine factors, got {weekly_assessment['factors_count']}")
            
            self.created_assessments.append(weekly_assessment)
            print(f"✅ Started weekly assessment: {weekly_assessment['factors_count']} factors, decision_id: {weekly_assessment['decision_id']}")
            
            # Test 3: Start monthly assessment
            response = await client.post(
                f"{BACKEND_URL}/lifestyle/start-assessment",
                json={"period": "monthly"},
                headers=self.get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"Start monthly assessment failed: {response.status_code} - {response.text}")
            
            monthly_assessment = response.json()
            if monthly_assessment['period'] != 'monthly':
                raise Exception(f"Expected period 'monthly', got {monthly_assessment['period']}")
            
            # Should include all routines (3 from our test data)
            if monthly_assessment['factors_count'] != 3:
                raise Exception(f"Expected 3 monthly routine factors, got {monthly_assessment['factors_count']}")
            
            self.created_assessments.append(monthly_assessment)
            print(f"✅ Started monthly assessment: {monthly_assessment['factors_count']} factors, decision_id: {monthly_assessment['decision_id']}")
            
            # Test 4: List assessments
            response = await client.get(
                f"{BACKEND_URL}/lifestyle/assessments",
                headers=self.get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"List assessments failed: {response.status_code} - {response.text}")
            
            assessments_list = response.json()
            if len(assessments_list) != 3:
                raise Exception(f"Expected 3 assessments, got {len(assessments_list)}")
            
            print(f"✅ Listed assessments: {len(assessments_list)} assessments found")
            
            # Test 5: Get analytics for daily period
            response = await client.get(
                f"{BACKEND_URL}/lifestyle/analytics?period=daily",
                headers=self.get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"Get analytics failed: {response.status_code} - {response.text}")
            
            analytics = response.json()
            required_fields = ['trend', 'area_averages', 'avg_effectiveness', 'total_assessments']
            for field in required_fields:
                if field not in analytics:
                    raise Exception(f"Analytics missing field: {field}")
            
            print(f"✅ Retrieved analytics: {analytics['total_assessments']} total assessments, avg effectiveness: {analytics['avg_effectiveness']}%")
            
            # Test 6: Check updated dashboard stats
            response = await client.get(
                f"{BACKEND_URL}/lifestyle/dashboard",
                headers=self.get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"Updated dashboard failed: {response.status_code} - {response.text}")
            
            dashboard = response.json()
            print(f"✅ Updated dashboard stats: {dashboard['active_routines']} active routines, recent scores: {dashboard['recent_scores']}")
            
            return True
    
    async def test_ctt_import(self):
        """Test Import from CTT functionality"""
        print("\n🧪 Testing Import from CTT...")
        
        async with httpx.AsyncClient() as client:
            # Test 1: Create a CTT routine task first
            ctt_task_data = {
                "task": "Daily Standup Meeting",
                "is_routine": True,
                "frequency": "daily",
                "life_area": "career",
                "priority": "medium",
                "current_status": "open"
            }
            
            response = await client.post(
                f"{BACKEND_URL}/ctt/tasks",
                json=ctt_task_data,
                headers=self.get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"Create CTT task failed: {response.status_code} - {response.text}")
            
            ctt_task = response.json()
            self.created_ctt_tasks.append(ctt_task)
            print(f"✅ Created CTT routine task: {ctt_task['task']} (ID: {ctt_task['task_id']})")
            
            # Test 2: Import from CTT
            response = await client.post(
                f"{BACKEND_URL}/lifestyle/import-from-ctt",
                headers=self.get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"Import from CTT failed: {response.status_code} - {response.text}")
            
            import_result = response.json()
            required_fields = ['imported', 'total_ctt_routines']
            for field in required_fields:
                if field not in import_result:
                    raise Exception(f"Import result missing field: {field}")
            
            if import_result['imported'] != 1:
                raise Exception(f"Expected 1 imported routine, got {import_result['imported']}")
            
            print(f"✅ Imported from CTT: {import_result['imported']} routines imported from {import_result['total_ctt_routines']} CTT routines")
            
            # Test 3: Import from CTT again (should return imported=0 due to deduplication)
            response = await client.post(
                f"{BACKEND_URL}/lifestyle/import-from-ctt",
                headers=self.get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"Second import from CTT failed: {response.status_code} - {response.text}")
            
            second_import = response.json()
            if second_import['imported'] != 0:
                raise Exception(f"Expected 0 imported routines on second import (deduplication), got {second_import['imported']}")
            
            print(f"✅ Second import (deduplication test): {second_import['imported']} routines imported (expected 0)")
            
            # Test 4: Verify the imported routine appears in routine list
            response = await client.get(
                f"{BACKEND_URL}/lifestyle/routines",
                headers=self.get_headers()
            )
            
            if response.status_code != 200:
                raise Exception(f"List routines after import failed: {response.status_code} - {response.text}")
            
            all_routines = response.json()
            # Should now have 4 routines (3 original + 1 imported)
            if len(all_routines) != 4:
                raise Exception(f"Expected 4 routines after import, got {len(all_routines)}")
            
            # Find the imported routine
            imported_routine = None
            for routine in all_routines:
                if routine.get('source_ctt_task_id') == ctt_task['task_id']:
                    imported_routine = routine
                    break
            
            if not imported_routine:
                raise Exception("Imported routine not found in routine list")
            
            if imported_routine['name'] != ctt_task['task']:
                raise Exception(f"Imported routine name mismatch: expected '{ctt_task['task']}', got '{imported_routine['name']}'")
            
            print(f"✅ Verified imported routine: {imported_routine['name']} appears in routine list")
            
            return True
    
    async def test_error_cases(self):
        """Test error cases"""
        print("\n🧪 Testing Error Cases...")
        
        async with httpx.AsyncClient() as client:
            # Test 1: Register a fresh user with no routines
            timestamp = int(time.time())
            fresh_email = f"fresh.user.{timestamp}@routinemaster.com"
            
            response = await client.post(f"{BACKEND_URL}/auth/register", json={
                "email": fresh_email,
                "password": "fresh123",
                "name": f"Fresh User {timestamp}"
            })
            
            if response.status_code != 200:
                raise Exception(f"Fresh user registration failed: {response.status_code} - {response.text}")
            
            fresh_user_data = response.json()
            fresh_token = fresh_user_data["session_token"]
            fresh_headers = {"Authorization": f"Bearer {fresh_token}"}
            
            print(f"✅ Registered fresh user: {fresh_email}")
            
            # Test 2: Try to start assessment when no active routines exist (should return 400)
            response = await client.post(
                f"{BACKEND_URL}/lifestyle/start-assessment",
                json={"period": "daily"},
                headers=fresh_headers
            )
            
            if response.status_code != 400:
                raise Exception(f"Expected 400 for no routines, got {response.status_code}")
            
            error_data = response.json()
            if "No active routines found" not in error_data.get("detail", ""):
                raise Exception(f"Expected 'No active routines found' error, got: {error_data}")
            
            print(f"✅ Error case handled correctly: {error_data['detail']}")
            
            return True
    
    async def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Lifestyle Dezider and Lifestyle Analyzer Backend Testing...")
        print(f"Backend URL: {BACKEND_URL}")
        
        try:
            # Step 1: Register user
            await self.register_user()
            
            # Step 2: Test Routine CRUD
            await self.test_routine_crud()
            
            # Step 3: Test Lifestyle Assessment
            await self.test_lifestyle_assessment()
            
            # Step 4: Test CTT Import
            await self.test_ctt_import()
            
            # Step 5: Test Error Cases
            await self.test_error_cases()
            
            print("\n🎉 ALL TESTS PASSED! Lifestyle Dezider and Lifestyle Analyzer backend is working correctly.")
            return True
            
        except Exception as e:
            print(f"\n❌ TEST FAILED: {str(e)}")
            return False

async def main():
    """Main test runner"""
    tester = LifestyleBackendTester()
    success = await tester.run_all_tests()
    
    if success:
        print("\n✅ COMPREHENSIVE TESTING COMPLETE: All Lifestyle endpoints working correctly!")
    else:
        print("\n❌ TESTING FAILED: Some endpoints have issues.")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    exit(0 if result else 1)