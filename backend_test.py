#!/usr/bin/env python3
"""
Backend Testing Script for TEPFI Resource Matrix and Calendar endpoints
Testing against: https://prr-actions-central.preview.emergentagent.com/api
"""

import requests
import json
import time
from datetime import datetime, timedelta
import uuid

# Configuration
BASE_URL = "https://prr-actions-central.preview.emergentagent.com/api"
session_token = None

def log_test(test_name, status, details=""):
    """Log test results with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    status_symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⏭️"
    print(f"[{timestamp}] {status_symbol} {test_name}")
    if details:
        print(f"    {details}")

def register_user():
    """Register a new test user and get session token"""
    global session_token
    timestamp = int(time.time())
    test_email = f"tepfi.test.{timestamp}@careerpath.com"
    
    payload = {
        "name": "TEPFI Test User",
        "email": test_email,
        "password": "testpass123"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/register", json=payload)
        if response.status_code == 200:
            data = response.json()
            session_token = data.get("session_token")
            log_test("User Registration", "PASS", f"Email: {test_email}, Token: {session_token[:20]}...")
            return True
        else:
            log_test("User Registration", "FAIL", f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        log_test("User Registration", "FAIL", f"Exception: {str(e)}")
        return False

def get_headers():
    """Get authorization headers"""
    return {"Authorization": f"Bearer {session_token}", "Content-Type": "application/json"}

def test_tepfi_crud():
    """Test TEPFI Resource Matrix CRUD operations"""
    print("\n=== TESTING TEPFI RESOURCE MATRIX CRUD ===")
    
    # Test 1: Create TEPFI Entry
    tepfi_payload = {
        "title": "Career Development Q1",
        "life_area": "career",
        "matrix": {
            "time": {
                "self": {"description": "8 hours daily", "score": 7, "notes": "Good"},
                "micro": {"description": "Team meetings 2h", "score": 5, "notes": ""},
                "macro": {"description": "Industry events quarterly", "score": 3, "notes": "Need more"}
            },
            "effort": {
                "self": {"description": "High focus", "score": 8, "notes": ""},
                "micro": {"description": "Team coordination", "score": 6, "notes": ""},
                "macro": {"description": "Market analysis", "score": 4, "notes": ""}
            },
            "people": {
                "self": {"description": "Personal network", "score": 6, "notes": ""},
                "micro": {"description": "5 team members", "score": 7, "notes": ""},
                "macro": {"description": "Industry contacts", "score": 3, "notes": ""}
            },
            "finance": {
                "self": {"description": "Savings", "score": 5, "notes": ""},
                "micro": {"description": "Department budget", "score": 6, "notes": ""},
                "macro": {"description": "VC funding options", "score": 2, "notes": ""}
            },
            "infrastructure": {
                "self": {"description": "Laptop & tools", "score": 8, "notes": ""},
                "micro": {"description": "Office setup", "score": 7, "notes": ""},
                "macro": {"description": "Cloud services", "score": 6, "notes": ""}
            }
        },
        "overall_notes": "Good resource allocation",
        "status": "active"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/tepfi/entries", json=tepfi_payload, headers=get_headers())
        if response.status_code == 200:
            tepfi_data = response.json()
            entry_id = tepfi_data.get("entry_id")
            log_test("TEPFI Create Entry", "PASS", f"Entry ID: {entry_id}")
            
            # Validate response structure
            required_fields = ["entry_id", "user_id", "title", "life_area", "matrix", "overall_notes", "status"]
            missing_fields = [field for field in required_fields if field not in tepfi_data]
            if missing_fields:
                log_test("TEPFI Create Response Structure", "FAIL", f"Missing fields: {missing_fields}")
                return None
            else:
                log_test("TEPFI Create Response Structure", "PASS", "All required fields present")
            
            return entry_id
        else:
            log_test("TEPFI Create Entry", "FAIL", f"Status: {response.status_code}, Response: {response.text}")
            return None
    except Exception as e:
        log_test("TEPFI Create Entry", "FAIL", f"Exception: {str(e)}")
        return None

def test_tepfi_list_and_filters(entry_id):
    """Test TEPFI list and filtering"""
    # Test 2: List all TEPFI entries
    try:
        response = requests.get(f"{BASE_URL}/tepfi/entries", headers=get_headers())
        if response.status_code == 200:
            entries = response.json()
            if isinstance(entries, list) and len(entries) > 0:
                log_test("TEPFI List Entries", "PASS", f"Found {len(entries)} entries")
            else:
                log_test("TEPFI List Entries", "FAIL", "No entries returned")
                return False
        else:
            log_test("TEPFI List Entries", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("TEPFI List Entries", "FAIL", f"Exception: {str(e)}")
        return False
    
    # Test 3: Filter by life_area
    try:
        response = requests.get(f"{BASE_URL}/tepfi/entries?life_area=career", headers=get_headers())
        if response.status_code == 200:
            entries = response.json()
            if isinstance(entries, list):
                career_entries = [e for e in entries if e.get("life_area") == "career"]
                log_test("TEPFI Filter by Life Area", "PASS", f"Found {len(career_entries)} career entries")
            else:
                log_test("TEPFI Filter by Life Area", "FAIL", "Invalid response format")
                return False
        else:
            log_test("TEPFI Filter by Life Area", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("TEPFI Filter by Life Area", "FAIL", f"Exception: {str(e)}")
        return False
    
    # Test 4: Filter by status
    try:
        response = requests.get(f"{BASE_URL}/tepfi/entries?status=active", headers=get_headers())
        if response.status_code == 200:
            entries = response.json()
            if isinstance(entries, list):
                active_entries = [e for e in entries if e.get("status") == "active"]
                log_test("TEPFI Filter by Status", "PASS", f"Found {len(active_entries)} active entries")
            else:
                log_test("TEPFI Filter by Status", "FAIL", "Invalid response format")
                return False
        else:
            log_test("TEPFI Filter by Status", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("TEPFI Filter by Status", "FAIL", f"Exception: {str(e)}")
        return False
    
    return True

def test_tepfi_get_single(entry_id):
    """Test getting single TEPFI entry"""
    # Test 5: Get single TEPFI entry
    try:
        response = requests.get(f"{BASE_URL}/tepfi/entries/{entry_id}", headers=get_headers())
        if response.status_code == 200:
            entry = response.json()
            if entry.get("entry_id") == entry_id:
                log_test("TEPFI Get Single Entry", "PASS", f"Retrieved entry: {entry.get('title')}")
                
                # Validate matrix structure
                matrix = entry.get("matrix", {})
                tepfi_dimensions = ["time", "effort", "people", "finance", "infrastructure"]
                tepfi_layers = ["self", "micro", "macro"]
                
                matrix_valid = True
                for dim in tepfi_dimensions:
                    if dim not in matrix:
                        matrix_valid = False
                        break
                    for layer in tepfi_layers:
                        if layer not in matrix[dim]:
                            matrix_valid = False
                            break
                        layer_data = matrix[dim][layer]
                        if not all(key in layer_data for key in ["description", "score", "notes"]):
                            matrix_valid = False
                            break
                
                if matrix_valid:
                    log_test("TEPFI Matrix Structure Validation", "PASS", "All dimensions and layers present")
                else:
                    log_test("TEPFI Matrix Structure Validation", "FAIL", "Matrix structure incomplete")
                
                return True
            else:
                log_test("TEPFI Get Single Entry", "FAIL", "Entry ID mismatch")
                return False
        else:
            log_test("TEPFI Get Single Entry", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("TEPFI Get Single Entry", "FAIL", f"Exception: {str(e)}")
        return False

def test_tepfi_update(entry_id):
    """Test TEPFI entry update"""
    # Test 6: Update TEPFI entry
    update_payload = {
        "title": "Career Development Q1 - Updated",
        "matrix": {
            "time": {
                "self": {"description": "9 hours daily", "score": 8, "notes": "Improved"},
                "micro": {"description": "Team meetings 2h", "score": 5, "notes": ""},
                "macro": {"description": "Industry events quarterly", "score": 4, "notes": "More events planned"}
            },
            "effort": {
                "self": {"description": "High focus", "score": 9, "notes": "Better focus"},
                "micro": {"description": "Team coordination", "score": 6, "notes": ""},
                "macro": {"description": "Market analysis", "score": 5, "notes": ""}
            },
            "people": {
                "self": {"description": "Personal network", "score": 7, "notes": "Expanded"},
                "micro": {"description": "5 team members", "score": 7, "notes": ""},
                "macro": {"description": "Industry contacts", "score": 4, "notes": ""}
            },
            "finance": {
                "self": {"description": "Savings", "score": 6, "notes": "Increased"},
                "micro": {"description": "Department budget", "score": 6, "notes": ""},
                "macro": {"description": "VC funding options", "score": 3, "notes": ""}
            },
            "infrastructure": {
                "self": {"description": "Laptop & tools", "score": 8, "notes": ""},
                "micro": {"description": "Office setup", "score": 7, "notes": ""},
                "macro": {"description": "Cloud services", "score": 7, "notes": "Upgraded"}
            }
        },
        "overall_notes": "Improved resource allocation after review"
    }
    
    try:
        response = requests.put(f"{BASE_URL}/tepfi/entries/{entry_id}", json=update_payload, headers=get_headers())
        if response.status_code == 200:
            updated_entry = response.json()
            if updated_entry.get("title") == "Career Development Q1 - Updated":
                log_test("TEPFI Update Entry", "PASS", "Title and matrix updated successfully")
                
                # Verify specific score updates
                time_self_score = updated_entry.get("matrix", {}).get("time", {}).get("self", {}).get("score", 0)
                if time_self_score == 8:
                    log_test("TEPFI Update Score Verification", "PASS", f"Time-Self score updated to {time_self_score}")
                else:
                    log_test("TEPFI Update Score Verification", "FAIL", f"Expected score 8, got {time_self_score}")
                
                return True
            else:
                log_test("TEPFI Update Entry", "FAIL", "Title not updated correctly")
                return False
        else:
            log_test("TEPFI Update Entry", "FAIL", f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        log_test("TEPFI Update Entry", "FAIL", f"Exception: {str(e)}")
        return False

def test_tepfi_dashboard():
    """Test TEPFI dashboard"""
    # Test 7: Get TEPFI dashboard
    try:
        response = requests.get(f"{BASE_URL}/tepfi/dashboard", headers=get_headers())
        if response.status_code == 200:
            dashboard = response.json()
            required_fields = ["total_entries", "by_area", "avg_matrix"]
            missing_fields = [field for field in required_fields if field not in dashboard]
            
            if missing_fields:
                log_test("TEPFI Dashboard", "FAIL", f"Missing fields: {missing_fields}")
                return False
            else:
                total_entries = dashboard.get("total_entries", 0)
                avg_matrix = dashboard.get("avg_matrix", {})
                log_test("TEPFI Dashboard", "PASS", f"Total entries: {total_entries}, Avg matrix calculated")
                
                # Validate avg_matrix structure
                tepfi_dimensions = ["time", "effort", "people", "finance", "infrastructure"]
                tepfi_layers = ["self", "micro", "macro"]
                
                matrix_valid = True
                for dim in tepfi_dimensions:
                    if dim not in avg_matrix:
                        matrix_valid = False
                        break
                    for layer in tepfi_layers:
                        if layer not in avg_matrix[dim]:
                            matrix_valid = False
                            break
                
                if matrix_valid:
                    log_test("TEPFI Dashboard Matrix Structure", "PASS", "Average matrix structure valid")
                else:
                    log_test("TEPFI Dashboard Matrix Structure", "FAIL", "Average matrix structure invalid")
                
                return True
        else:
            log_test("TEPFI Dashboard", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("TEPFI Dashboard", "FAIL", f"Exception: {str(e)}")
        return False

def test_tepfi_delete(entry_id):
    """Test TEPFI entry deletion"""
    # Create an extra entry to delete
    extra_payload = {
        "title": "Test Entry for Deletion",
        "life_area": "finance",
        "matrix": {
            "time": {
                "self": {"description": "Test", "score": 5, "notes": ""},
                "micro": {"description": "Test", "score": 5, "notes": ""},
                "macro": {"description": "Test", "score": 5, "notes": ""}
            },
            "effort": {
                "self": {"description": "Test", "score": 5, "notes": ""},
                "micro": {"description": "Test", "score": 5, "notes": ""},
                "macro": {"description": "Test", "score": 5, "notes": ""}
            },
            "people": {
                "self": {"description": "Test", "score": 5, "notes": ""},
                "micro": {"description": "Test", "score": 5, "notes": ""},
                "macro": {"description": "Test", "score": 5, "notes": ""}
            },
            "finance": {
                "self": {"description": "Test", "score": 5, "notes": ""},
                "micro": {"description": "Test", "score": 5, "notes": ""},
                "macro": {"description": "Test", "score": 5, "notes": ""}
            },
            "infrastructure": {
                "self": {"description": "Test", "score": 5, "notes": ""},
                "micro": {"description": "Test", "score": 5, "notes": ""},
                "macro": {"description": "Test", "score": 5, "notes": ""}
            }
        },
        "status": "draft"
    }
    
    try:
        # Create extra entry
        response = requests.post(f"{BASE_URL}/tepfi/entries", json=extra_payload, headers=get_headers())
        if response.status_code == 200:
            extra_entry_id = response.json().get("entry_id")
            log_test("TEPFI Create Extra Entry for Deletion", "PASS", f"Entry ID: {extra_entry_id}")
            
            # Delete the extra entry
            delete_response = requests.delete(f"{BASE_URL}/tepfi/entries/{extra_entry_id}", headers=get_headers())
            if delete_response.status_code == 200:
                log_test("TEPFI Delete Entry", "PASS", "Entry deleted successfully")
                
                # Verify deletion
                get_response = requests.get(f"{BASE_URL}/tepfi/entries/{extra_entry_id}", headers=get_headers())
                if get_response.status_code == 404:
                    log_test("TEPFI Delete Verification", "PASS", "Entry not found after deletion")
                    return True
                else:
                    log_test("TEPFI Delete Verification", "FAIL", "Entry still exists after deletion")
                    return False
            else:
                log_test("TEPFI Delete Entry", "FAIL", f"Status: {delete_response.status_code}")
                return False
        else:
            log_test("TEPFI Create Extra Entry for Deletion", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("TEPFI Delete Entry", "FAIL", f"Exception: {str(e)}")
        return False

def create_ctt_task_for_calendar():
    """Create a CTT task with deadline for calendar testing"""
    future_date = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")
    from_time = f"{future_date} 09:00"
    to_time = f"{future_date} 11:00"
    
    task_payload = {
        "task": "Calendar Test Task",
        "deadline": future_date,
        "from_time": from_time,
        "to_time": to_time,
        "priority": "high",
        "current_status": "open",
        "life_area": "career"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/ctt/tasks", json=task_payload, headers=get_headers())
        if response.status_code == 200:
            task_data = response.json()
            task_id = task_data.get("task_id")
            log_test("CTT Create Task for Calendar", "PASS", f"Task ID: {task_id}, Deadline: {future_date}")
            return task_id
        else:
            log_test("CTT Create Task for Calendar", "FAIL", f"Status: {response.status_code}, Response: {response.text}")
            return None
    except Exception as e:
        log_test("CTT Create Task for Calendar", "FAIL", f"Exception: {str(e)}")
        return None

def test_calendar_upcoming():
    """Test calendar upcoming view"""
    print("\n=== TESTING CALENDAR UPCOMING VIEW ===")
    
    # Test 8: Get upcoming calendar items
    try:
        response = requests.get(f"{BASE_URL}/calendar/upcoming?days=30", headers=get_headers())
        if response.status_code == 200:
            calendar_data = response.json()
            required_fields = ["upcoming", "by_date", "total"]
            missing_fields = [field for field in required_fields if field not in calendar_data]
            
            if missing_fields:
                log_test("Calendar Upcoming View", "FAIL", f"Missing fields: {missing_fields}")
                return False
            else:
                total_tasks = calendar_data.get("total", 0)
                by_date = calendar_data.get("by_date", {})
                upcoming = calendar_data.get("upcoming", [])
                
                log_test("Calendar Upcoming View", "PASS", f"Total upcoming tasks: {total_tasks}")
                log_test("Calendar Upcoming Structure", "PASS", f"By date groups: {len(by_date)}, Upcoming list: {len(upcoming)}")
                
                # Validate that tasks are grouped by date correctly
                if by_date:
                    for date, tasks in by_date.items():
                        if isinstance(tasks, list):
                            log_test("Calendar Date Grouping", "PASS", f"Date {date}: {len(tasks)} tasks")
                        else:
                            log_test("Calendar Date Grouping", "FAIL", f"Date {date}: Invalid task list format")
                            return False
                
                return True
        else:
            log_test("Calendar Upcoming View", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("Calendar Upcoming View", "FAIL", f"Exception: {str(e)}")
        return False

def test_calendar_batch_export():
    """Test calendar batch export"""
    print("\n=== TESTING CALENDAR BATCH EXPORT ===")
    
    # Test 9: Batch export all non-done tasks with deadlines
    try:
        response = requests.post(f"{BASE_URL}/calendar/batch-export", json={}, headers=get_headers())
        if response.status_code == 200:
            export_data = response.json()
            required_fields = ["tasks", "count"]
            missing_fields = [field for field in required_fields if field not in export_data]
            
            if missing_fields:
                log_test("Calendar Batch Export", "FAIL", f"Missing fields: {missing_fields}")
                return False
            else:
                tasks = export_data.get("tasks", [])
                count = export_data.get("count", 0)
                
                log_test("Calendar Batch Export", "PASS", f"Exported {count} tasks")
                
                # Validate calendar URLs
                valid_urls = 0
                for task in tasks:
                    calendar_url = task.get("calendar_url", "")
                    if calendar_url.startswith("https://calendar.google.com/calendar/render?action=TEMPLATE"):
                        valid_urls += 1
                        
                        # Check URL parameters
                        if "&text=" in calendar_url and "&details=" in calendar_url:
                            log_test("Calendar URL Format", "PASS", f"Task '{task.get('task')}' has valid Google Calendar URL")
                        else:
                            log_test("Calendar URL Format", "FAIL", f"Task '{task.get('task')}' missing required URL parameters")
                    else:
                        log_test("Calendar URL Format", "FAIL", f"Task '{task.get('task')}' has invalid calendar URL")
                
                if valid_urls == len(tasks) and len(tasks) > 0:
                    log_test("Calendar URL Validation", "PASS", f"All {valid_urls} URLs are valid Google Calendar URLs")
                elif len(tasks) == 0:
                    log_test("Calendar URL Validation", "PASS", "No tasks to export (expected for new user)")
                else:
                    log_test("Calendar URL Validation", "FAIL", f"Only {valid_urls}/{len(tasks)} URLs are valid")
                
                return True
        else:
            log_test("Calendar Batch Export", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("Calendar Batch Export", "FAIL", f"Exception: {str(e)}")
        return False

def test_calendar_batch_export_with_task(task_id):
    """Test calendar batch export with specific task"""
    # Test 10: Batch export specific task
    try:
        response = requests.post(f"{BASE_URL}/calendar/batch-export", json={"task_ids": [task_id]}, headers=get_headers())
        if response.status_code == 200:
            export_data = response.json()
            tasks = export_data.get("tasks", [])
            
            if len(tasks) == 1:
                task = tasks[0]
                calendar_url = task.get("calendar_url", "")
                
                if calendar_url.startswith("https://calendar.google.com/calendar/render?action=TEMPLATE"):
                    log_test("Calendar Specific Task Export", "PASS", f"Task exported with valid URL")
                    
                    # Validate date formatting in URL
                    if "&dates=" in calendar_url:
                        log_test("Calendar Date Formatting", "PASS", "Date parameters included in URL")
                    else:
                        log_test("Calendar Date Formatting", "FAIL", "Date parameters missing from URL")
                    
                    return True
                else:
                    log_test("Calendar Specific Task Export", "FAIL", "Invalid calendar URL format")
                    return False
            else:
                log_test("Calendar Specific Task Export", "FAIL", f"Expected 1 task, got {len(tasks)}")
                return False
        else:
            log_test("Calendar Specific Task Export", "FAIL", f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("Calendar Specific Task Export", "FAIL", f"Exception: {str(e)}")
        return False

def main():
    """Main test execution"""
    print("🚀 STARTING TEPFI RESOURCE MATRIX AND CALENDAR ENDPOINTS TESTING")
    print(f"Backend URL: {BASE_URL}")
    print("=" * 80)
    
    # Step 1: Register user and authenticate
    if not register_user():
        print("❌ CRITICAL: User registration failed. Cannot proceed with tests.")
        return
    
    # Step 2: Test TEPFI CRUD operations
    entry_id = test_tepfi_crud()
    if not entry_id:
        print("❌ CRITICAL: TEPFI entry creation failed. Cannot proceed with TEPFI tests.")
        return
    
    # Continue with TEPFI tests
    test_tepfi_list_and_filters(entry_id)
    test_tepfi_get_single(entry_id)
    test_tepfi_update(entry_id)
    test_tepfi_dashboard()
    test_tepfi_delete(entry_id)
    
    # Step 3: Create CTT task for calendar testing
    task_id = create_ctt_task_for_calendar()
    
    # Step 4: Test Calendar endpoints
    test_calendar_upcoming()
    test_calendar_batch_export()
    
    if task_id:
        test_calendar_batch_export_with_task(task_id)
    
    print("\n" + "=" * 80)
    print("🎯 TEPFI RESOURCE MATRIX AND CALENDAR ENDPOINTS TESTING COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()