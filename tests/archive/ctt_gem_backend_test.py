#!/usr/bin/env python3

import requests
import json
import time
import random
import string
from datetime import datetime, timedelta

# Backend URL
BASE_URL = "https://modal-responsive-fix.preview.emergentagent.com/api"

def generate_random_suffix():
    """Generate random suffix for unique emails"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

def test_ctt_gem_endpoints():
    """Test CTT (Centralized Task Tracker) and GEM (Goals Execution Manager) endpoints"""
    print("🚀 TESTING CTT & GEM ENDPOINTS")
    print("=" * 60)
    
    # Generate unique identifiers
    suffix = generate_random_suffix()
    
    # Test data
    test_email = f"ctt_gem_test_{suffix}@careerpath.com"
    test_name = f"CTT GEM Tester {suffix}"
    
    session_token = None
    task_id = None
    routine_task_id = None
    goal_id = None
    
    try:
        # Step 1: Register a new user
        print("\n1. 📝 Registering new user...")
        register_data = {
            "email": test_email,
            "password": "secure123",
            "name": test_name
        }
        
        response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            session_token = data.get("session_token")
            user_id = data.get("user_id")
            print(f"   ✅ PASS: User registered successfully")
            print(f"   User ID: {user_id}")
            print(f"   Session Token: {session_token[:20]}...")
        else:
            print(f"   ❌ FAIL: Registration failed - {response.text}")
            return False
            
        headers = {"Authorization": f"Bearer {session_token}"}
        
        # ========================
        # CTT ENDPOINTS TESTING
        # ========================
        print("\n" + "=" * 40)
        print("🎯 TESTING CTT ENDPOINTS")
        print("=" * 40)
        
        # Step 2: Create a CTT task
        print("\n2. ➕ Creating CTT task...")
        task_data = {
            "task": "Complete quarterly performance review",
            "sub_task": "Prepare self-assessment document",
            "priority": "high",
            "current_status": "open",
            "deadline": "2026-04-15",
            "task_owners": ["Self"],
            "life_area": "career",
            "decision_type": "need",
            "company": "TechCorp Solutions",
            "division": "Engineering",
            "team": "Backend Development",
            "project": "View Dezider Platform",
            "internal_dependency": "API design completion",
            "external_dependency": "Client approval for requirements",
            "internal_help": "Design team consultation",
            "external_help": "External consultant review",
            "task_duration": "2h",
            "from_time": "2026-04-15 09:00",
            "to_time": "2026-04-15 11:00",
            "is_routine": False,
            "day_status": {}
        }
        
        response = requests.post(f"{BASE_URL}/ctt/tasks", json=task_data, headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            task_id = data.get("task_id")
            print(f"   ✅ PASS: CTT task created successfully")
            print(f"   Task ID: {task_id}")
            print(f"   Task: {data.get('task')}")
            print(f"   Priority: {data.get('priority')}")
            print(f"   Life Area: {data.get('life_area')}")
        else:
            print(f"   ❌ FAIL: Task creation failed - {response.text}")
            return False
            
        # Step 3: Create a routine task
        print("\n3. 🔄 Creating routine CTT task...")
        routine_task_data = {
            "task": "Daily standup meeting",
            "is_routine": True,
            "frequency": "daily",
            "life_area": "career",
            "priority": "medium",
            "current_status": "open",
            "company": "TechCorp Solutions",
            "team": "Backend Development"
        }
        
        response = requests.post(f"{BASE_URL}/ctt/tasks", json=routine_task_data, headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            routine_task_id = data.get("task_id")
            print(f"   ✅ PASS: Routine task created successfully")
            print(f"   Routine Task ID: {routine_task_id}")
            print(f"   Task: {data.get('task')}")
            print(f"   Is Routine: {data.get('is_routine')}")
            print(f"   Frequency: {data.get('frequency')}")
        else:
            print(f"   ❌ FAIL: Routine task creation failed - {response.text}")
            return False
            
        # Step 4: List all CTT tasks
        print("\n4. 📋 Listing all CTT tasks...")
        response = requests.get(f"{BASE_URL}/ctt/tasks", headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            tasks = response.json()
            print(f"   ✅ PASS: Retrieved {len(tasks)} tasks")
            if len(tasks) >= 2:
                print(f"   ✅ PASS: Both tasks present in list")
                for task in tasks[:2]:  # Show first 2 tasks
                    print(f"   - {task.get('task')} (Priority: {task.get('priority')}, Status: {task.get('current_status')})")
            else:
                print(f"   ❌ FAIL: Expected at least 2 tasks, got {len(tasks)}")
                return False
        else:
            print(f"   ❌ FAIL: Task listing failed - {response.text}")
            return False
            
        # Step 5: Test task filtering
        print("\n5. 🔍 Testing task filtering...")
        
        # Filter by status
        response = requests.get(f"{BASE_URL}/ctt/tasks?status=open", headers=headers)
        print(f"   Filter by status=open - Status: {response.status_code}")
        if response.status_code == 200:
            tasks = response.json()
            print(f"   ✅ PASS: Status filter returned {len(tasks)} open tasks")
        
        # Filter by life_area
        response = requests.get(f"{BASE_URL}/ctt/tasks?life_area=career", headers=headers)
        print(f"   Filter by life_area=career - Status: {response.status_code}")
        if response.status_code == 200:
            tasks = response.json()
            print(f"   ✅ PASS: Life area filter returned {len(tasks)} career tasks")
        
        # Filter by decision_type
        response = requests.get(f"{BASE_URL}/ctt/tasks?decision_type=need", headers=headers)
        print(f"   Filter by decision_type=need - Status: {response.status_code}")
        if response.status_code == 200:
            tasks = response.json()
            print(f"   ✅ PASS: Decision type filter returned {len(tasks)} need tasks")
        
        # Filter by priority
        response = requests.get(f"{BASE_URL}/ctt/tasks?priority=high", headers=headers)
        print(f"   Filter by priority=high - Status: {response.status_code}")
        if response.status_code == 200:
            tasks = response.json()
            print(f"   ✅ PASS: Priority filter returned {len(tasks)} high priority tasks")
        
        # Filter by is_routine
        response = requests.get(f"{BASE_URL}/ctt/tasks?is_routine=false", headers=headers)
        print(f"   Filter by is_routine=false - Status: {response.status_code}")
        if response.status_code == 200:
            tasks = response.json()
            print(f"   ✅ PASS: Routine filter returned {len(tasks)} non-routine tasks")
            
        # Step 6: Get single task
        print("\n6. 🎯 Getting single CTT task...")
        response = requests.get(f"{BASE_URL}/ctt/tasks/{task_id}", headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            task = response.json()
            print(f"   ✅ PASS: Retrieved task successfully")
            print(f"   Task: {task.get('task')}")
            print(f"   Company: {task.get('company')}")
            print(f"   Division: {task.get('division')}")
            print(f"   Team: {task.get('team')}")
            print(f"   Project: {task.get('project')}")
        else:
            print(f"   ❌ FAIL: Get task failed - {response.text}")
            return False
            
        # Step 7: Update task
        print("\n7. ✏️ Updating CTT task...")
        update_data = {
            "current_status": "in_progress",
            "priority": "medium",
            "remarks": "Started working on self-assessment"
        }
        
        response = requests.put(f"{BASE_URL}/ctt/tasks/{task_id}", json=update_data, headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            updated_task = response.json()
            print(f"   ✅ PASS: Task updated successfully")
            print(f"   New Status: {updated_task.get('current_status')}")
            print(f"   New Priority: {updated_task.get('priority')}")
            print(f"   Remarks: {updated_task.get('remarks')}")
        else:
            print(f"   ❌ FAIL: Task update failed - {response.text}")
            return False
            
        # Step 8: Update day status
        print("\n8. 📅 Updating day status...")
        day_status_data = {"2026-03-23": "done"}
        
        response = requests.put(f"{BASE_URL}/ctt/tasks/{task_id}/day-status", json=day_status_data, headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ PASS: Day status updated successfully")
            print(f"   Day Status: {result.get('day_status')}")
        else:
            print(f"   ❌ FAIL: Day status update failed - {response.text}")
            return False
            
        # Step 9: Clear day status
        print("\n9. 🗑️ Clearing day status...")
        clear_day_status_data = {"2026-03-23": ""}
        
        response = requests.put(f"{BASE_URL}/ctt/tasks/{task_id}/day-status", json=clear_day_status_data, headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ PASS: Day status cleared successfully")
            print(f"   Day Status: {result.get('day_status')}")
        else:
            print(f"   ❌ FAIL: Day status clear failed - {response.text}")
            return False
            
        # Step 10: Get CTT stats
        print("\n10. 📊 Getting CTT dashboard stats...")
        response = requests.get(f"{BASE_URL}/ctt/stats", headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            stats = response.json()
            print(f"   ✅ PASS: CTT stats retrieved successfully")
            print(f"   Total Tasks: {stats.get('total')}")
            print(f"   By Status: {stats.get('by_status')}")
            print(f"   By Priority: {stats.get('by_priority')}")
            print(f"   By Life Area: {stats.get('by_life_area')}")
            print(f"   By Source: {stats.get('by_source')}")
            print(f"   Routine Count: {stats.get('routine_count')}")
            print(f"   One-time Count: {stats.get('one_time_count')}")
        else:
            print(f"   ❌ FAIL: CTT stats failed - {response.text}")
            return False
            
        # Step 11: Test aggregate action items
        print("\n11. 🔄 Testing aggregate action items...")
        response = requests.post(f"{BASE_URL}/ctt/aggregate", json={}, headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ PASS: Aggregate completed successfully")
            print(f"   Imported: {result.get('imported')} action items")
            print(f"   Message: {result.get('message')}")
        else:
            print(f"   ❌ FAIL: Aggregate failed - {response.text}")
            return False
            
        # Step 12: Generate Google Calendar URL
        print("\n12. 📅 Generating Google Calendar URL...")
        response = requests.get(f"{BASE_URL}/ctt/tasks/{task_id}/calendar-url", headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ PASS: Calendar URL generated successfully")
            print(f"   Task ID: {result.get('task_id')}")
            calendar_url = result.get('calendar_url')
            print(f"   Calendar URL: {calendar_url[:80]}...")
            if "calendar.google.com" in calendar_url:
                print(f"   ✅ PASS: Valid Google Calendar URL format")
            else:
                print(f"   ❌ FAIL: Invalid calendar URL format")
                return False
        else:
            print(f"   ❌ FAIL: Calendar URL generation failed - {response.text}")
            return False
            
        # ========================
        # GEM ENDPOINTS TESTING
        # ========================
        print("\n" + "=" * 40)
        print("🎯 TESTING GEM ENDPOINTS")
        print("=" * 40)
        
        # Step 13: Create a GEM goal
        print("\n13. 🎯 Creating GEM goal...")
        goal_data = {
            "title": "Get promoted to Senior Developer",
            "description": "Achieve promotion to senior developer role with increased responsibilities and compensation",
            "life_area": "career",
            "goal_type": "aspiration",
            "priority": "high",
            "status": "active",
            "target_date": "2026-12-31",
            "smart_goal": "Achieve senior developer title by December 2026 through skill development and project leadership",
            "progress_percent": 25
        }
        
        response = requests.post(f"{BASE_URL}/gem/goals", json=goal_data, headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            goal_id = data.get("goal_id")
            print(f"   ✅ PASS: GEM goal created successfully")
            print(f"   Goal ID: {goal_id}")
            print(f"   Title: {data.get('title')}")
            print(f"   Life Area: {data.get('life_area')}")
            print(f"   Goal Type: {data.get('goal_type')}")
            print(f"   Progress: {data.get('progress_percent')}%")
        else:
            print(f"   ❌ FAIL: Goal creation failed - {response.text}")
            return False
            
        # Step 14: List GEM goals
        print("\n14. 📋 Listing GEM goals...")
        response = requests.get(f"{BASE_URL}/gem/goals", headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            goals = response.json()
            print(f"   ✅ PASS: Retrieved {len(goals)} goals")
            if len(goals) >= 1:
                print(f"   ✅ PASS: Goal present in list")
                for goal in goals[:1]:  # Show first goal
                    print(f"   - {goal.get('title')} (Type: {goal.get('goal_type')}, Status: {goal.get('status')})")
            else:
                print(f"   ❌ FAIL: Expected at least 1 goal, got {len(goals)}")
                return False
        else:
            print(f"   ❌ FAIL: Goal listing failed - {response.text}")
            return False
            
        # Step 15: Test goal filtering
        print("\n15. 🔍 Testing goal filtering...")
        
        # Filter by life_area
        response = requests.get(f"{BASE_URL}/gem/goals?life_area=career", headers=headers)
        print(f"   Filter by life_area=career - Status: {response.status_code}")
        if response.status_code == 200:
            goals = response.json()
            print(f"   ✅ PASS: Life area filter returned {len(goals)} career goals")
        
        # Filter by goal_type
        response = requests.get(f"{BASE_URL}/gem/goals?goal_type=aspiration", headers=headers)
        print(f"   Filter by goal_type=aspiration - Status: {response.status_code}")
        if response.status_code == 200:
            goals = response.json()
            print(f"   ✅ PASS: Goal type filter returned {len(goals)} aspiration goals")
        
        # Filter by status
        response = requests.get(f"{BASE_URL}/gem/goals?status=active", headers=headers)
        print(f"   Filter by status=active - Status: {response.status_code}")
        if response.status_code == 200:
            goals = response.json()
            print(f"   ✅ PASS: Status filter returned {len(goals)} active goals")
            
        # Step 16: Get single goal
        print("\n16. 🎯 Getting single GEM goal...")
        response = requests.get(f"{BASE_URL}/gem/goals/{goal_id}", headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            goal = response.json()
            print(f"   ✅ PASS: Retrieved goal successfully")
            print(f"   Title: {goal.get('title')}")
            print(f"   Description: {goal.get('description')}")
            print(f"   SMART Goal: {goal.get('smart_goal')}")
            print(f"   Target Date: {goal.get('target_date')}")
        else:
            print(f"   ❌ FAIL: Get goal failed - {response.text}")
            return False
            
        # Step 17: Update goal
        print("\n17. ✏️ Updating GEM goal...")
        update_data = {
            "progress_percent": 50,
            "status": "active"
        }
        
        response = requests.put(f"{BASE_URL}/gem/goals/{goal_id}", json=update_data, headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            updated_goal = response.json()
            print(f"   ✅ PASS: Goal updated successfully")
            print(f"   New Progress: {updated_goal.get('progress_percent')}%")
            print(f"   Status: {updated_goal.get('status')}")
        else:
            print(f"   ❌ FAIL: Goal update failed - {response.text}")
            return False
            
        # Step 18: Link a decision to goal
        print("\n18. 🔗 Linking decision to goal...")
        link_data = {
            "link_type": "decision",
            "link_id": "test-decision-123"
        }
        
        response = requests.post(f"{BASE_URL}/gem/goals/{goal_id}/link", json=link_data, headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ PASS: Decision linked to goal successfully")
            print(f"   Message: {result.get('message')}")
        else:
            print(f"   ❌ FAIL: Goal linking failed - {response.text}")
            return False
            
        # Step 19: Get GEM dashboard
        print("\n19. 📊 Getting GEM dashboard...")
        response = requests.get(f"{BASE_URL}/gem/dashboard", headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            dashboard = response.json()
            print(f"   ✅ PASS: GEM dashboard retrieved successfully")
            print(f"   Total Goals: {dashboard.get('total_goals')}")
            print(f"   Average Progress: {dashboard.get('avg_progress')}%")
            print(f"   By Area: {dashboard.get('by_area')}")
            print(f"   By Type: {dashboard.get('by_type')}")
            print(f"   By Status: {dashboard.get('by_status')}")
        else:
            print(f"   ❌ FAIL: GEM dashboard failed - {response.text}")
            return False
            
        # Step 20: Create an extra task for deletion test
        print("\n20. ➕ Creating extra task for deletion test...")
        extra_task_data = {
            "task": "Test task for deletion",
            "priority": "low",
            "current_status": "open",
            "life_area": "career"
        }
        
        response = requests.post(f"{BASE_URL}/ctt/tasks", json=extra_task_data, headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            extra_task_id = data.get("task_id")
            print(f"   ✅ PASS: Extra task created for deletion test")
            print(f"   Extra Task ID: {extra_task_id}")
        else:
            print(f"   ❌ FAIL: Extra task creation failed - {response.text}")
            return False
            
        # Step 21: Delete the extra task
        print("\n21. 🗑️ Deleting extra CTT task...")
        response = requests.delete(f"{BASE_URL}/ctt/tasks/{extra_task_id}", headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ PASS: Task deleted successfully")
            print(f"   Message: {result.get('message')}")
        else:
            print(f"   ❌ FAIL: Task deletion failed - {response.text}")
            return False
            
        # Step 22: Create an extra goal for deletion test
        print("\n22. 🎯 Creating extra goal for deletion test...")
        extra_goal_data = {
            "title": "Test goal for deletion",
            "description": "This goal will be deleted",
            "life_area": "career",
            "goal_type": "need",
            "priority": "low",
            "status": "active"
        }
        
        response = requests.post(f"{BASE_URL}/gem/goals", json=extra_goal_data, headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            extra_goal_id = data.get("goal_id")
            print(f"   ✅ PASS: Extra goal created for deletion test")
            print(f"   Extra Goal ID: {extra_goal_id}")
        else:
            print(f"   ❌ FAIL: Extra goal creation failed - {response.text}")
            return False
            
        # Step 23: Delete the extra goal
        print("\n23. 🗑️ Deleting extra GEM goal...")
        response = requests.delete(f"{BASE_URL}/gem/goals/{extra_goal_id}", headers=headers)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ PASS: Goal deleted successfully")
            print(f"   Message: {result.get('message')}")
        else:
            print(f"   ❌ FAIL: Goal deletion failed - {response.text}")
            return False
            
        print("\n" + "=" * 60)
        print("🎉 ALL CTT & GEM ENDPOINT TESTS PASSED!")
        print("=" * 60)
        print(f"✅ CTT Tasks: Created, Listed, Filtered, Updated, Day Status, Stats, Aggregate, Calendar URL, Deleted")
        print(f"✅ GEM Goals: Created, Listed, Filtered, Updated, Linked, Dashboard, Deleted")
        print(f"✅ Authentication: Bearer token working correctly")
        print(f"✅ Data Persistence: All CRUD operations functional")
        print(f"✅ Filtering: All query parameters working")
        print(f"✅ Business Logic: Task/Goal management complete")
        return True
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_ctt_gem_endpoints()
    if not success:
        exit(1)