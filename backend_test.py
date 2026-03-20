#!/usr/bin/env python3
"""
Backend Testing Script for View Dezider API
Testing Focus Areas: Health Check, Notification System, Folder Analytics
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, Any, List

# Use the production URL from frontend/.env
BACKEND_URL = "https://decision-flow-plus.preview.emergentagent.com/api"

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
    
    def log(self, test_name: str, success: bool, details: str = ""):
        status = "✅ PASSED" if success else "❌ FAILED"
        self.results.append(f"{status}: {test_name}")
        if details:
            self.results.append(f"   {details}")
        if success:
            self.passed += 1
        else:
            self.failed += 1
        print(f"{status}: {test_name}")
        if details:
            print(f"   {details}")

def register_user(email: str, password: str, name: str) -> Dict[str, Any]:
    """Register a new user and return user data with session token"""
    data = {
        "email": email,
        "password": password,
        "name": name
    }
    
    response = requests.post(f"{BACKEND_URL}/auth/register", json=data)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Registration failed: {response.status_code} {response.text}")

def create_decision(session_token: str, title: str, context: str, folder: str) -> str:
    """Create a PRR decision and return decision_id"""
    headers = {"Authorization": f"Bearer {session_token}"}
    data = {
        "title": title,
        "context": context,
        "folder": folder
    }
    
    response = requests.post(f"{BACKEND_URL}/decisions", json=data, headers=headers)
    if response.status_code == 200:
        return response.json()["id"]
    else:
        raise Exception(f"Decision creation failed: {response.status_code} {response.text}")

def add_factors_and_options_to_decision(session_token: str, decision_id: str):
    """Add factors and options to a decision for testing"""
    headers = {"Authorization": f"Bearer {session_token}"}
    
    # Add factors
    factors = [
        {"id": "f1", "name": "Salary", "category": "primary", "rating": 80, "order": 1},
        {"id": "f2", "name": "Work-Life Balance", "category": "primary", "rating": 90, "order": 2},
        {"id": "f3", "name": "Growth Opportunities", "category": "secondary", "rating": 70, "order": 3}
    ]
    
    # Add options with assessments
    options = [
        {
            "id": "o1",
            "name": "Job A - Tech Startup",
            "assessments": [
                {"factor_id": "f1", "percentage": 85, "assessment_mode": "H"},
                {"factor_id": "f2", "percentage": 60, "assessment_mode": "M"},
                {"factor_id": "f3", "percentage": 90, "assessment_mode": "H"}
            ]
        },
        {
            "id": "o2",
            "name": "Job B - Corporate",
            "assessments": [
                {"factor_id": "f1", "percentage": 95, "assessment_mode": "H"},
                {"factor_id": "f2", "percentage": 40, "assessment_mode": "L"},
                {"factor_id": "f3", "percentage": 50, "assessment_mode": "M"}
            ]
        }
    ]
    
    update_data = {
        "factors": factors,
        "options": options,
        "status": "completed"
    }
    
    response = requests.put(f"{BACKEND_URL}/decisions/{decision_id}", json=update_data, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Decision update failed: {response.status_code} {response.text}")

def test_health_check(results: TestResults):
    """Test the health check endpoint"""
    print("\n=== TESTING HEALTH CHECK ENDPOINT ===")
    
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            required_fields = ["status", "timestamp"]
            
            if all(field in data for field in required_fields):
                if data["status"] == "healthy":
                    results.log("Health Check Response Format", True, f'Status: {data["status"]}, Timestamp: {data["timestamp"]}')
                else:
                    results.log("Health Check Response Format", False, f'Expected status "healthy", got "{data["status"]}"')
            else:
                missing_fields = [f for f in required_fields if f not in data]
                results.log("Health Check Response Format", False, f"Missing fields: {missing_fields}")
        else:
            results.log("Health Check Endpoint", False, f"HTTP {response.status_code}: {response.text}")
    
    except requests.exceptions.RequestException as e:
        results.log("Health Check Endpoint", False, f"Request failed: {str(e)}")

def test_notification_system(results: TestResults):
    """Test the complete notification system flow"""
    print("\n=== TESTING NOTIFICATION SYSTEM APIs ===")
    
    try:
        # Generate unique timestamps for user emails
        timestamp = str(int(time.time()))
        
        # Step 1: Register two users
        user_a_data = register_user(
            f"alice.tester.{timestamp}@careerpath.com",
            "securepass123",
            f"Alice Tester {timestamp}"
        )
        user_a_token = user_a_data["session_token"]
        user_a_email = user_a_data["email"]
        
        user_b_data = register_user(
            f"bob.tester.{timestamp}@careerpath.com", 
            "securepass123",
            f"Bob Tester {timestamp}"
        )
        user_b_token = user_b_data["session_token"]
        user_b_email = user_b_data["email"]
        
        results.log("User Registration for Testing", True, f"Created users: {user_a_data['name']} and {user_b_data['name']}")
        
        # Step 2: User A creates a decision with folder, factors, and options
        decision_id = create_decision(
            user_a_token,
            "Career Change Decision - Should I Switch Jobs?",
            "Evaluating whether to leave my current position for a new opportunity",
            "career"
        )
        
        add_factors_and_options_to_decision(user_a_token, decision_id)
        results.log("Decision Creation with Factors/Options", True, f"Decision ID: {decision_id}")
        
        # Step 3: User A shares step 7 with User B
        share_data = {
            "decision_id": decision_id,
            "step_number": 7,
            "recipient_emails": [user_b_email],
            "merge_mode": "self_weighted",
            "message": "Please help me evaluate these job options!"
        }
        
        headers_a = {"Authorization": f"Bearer {user_a_token}"}
        response = requests.post(f"{BACKEND_URL}/decisions/{decision_id}/share-step", json=share_data, headers=headers_a)
        
        if response.status_code == 200:
            share_id = response.json()["id"]
            results.log("Step Sharing (creates notification)", True, f"Share ID: {share_id}")
        else:
            results.log("Step Sharing", False, f"HTTP {response.status_code}: {response.text}")
            return
        
        # Wait a moment for notification creation
        time.sleep(1)
        
        # Step 4: Check User B's notifications
        headers_b = {"Authorization": f"Bearer {user_b_token}"}
        response = requests.get(f"{BACKEND_URL}/notifications", headers=headers_b)
        
        if response.status_code == 200:
            notifications = response.json()
            share_invite_notifications = [n for n in notifications if n["type"] == "share_invite"]
            
            if share_invite_notifications:
                notif = share_invite_notifications[0]
                results.log("Get Notifications (share_invite)", True, f'Found notification: "{notif["title"]}" - {notif["message"]}')
                notif_id = notif["id"]
            else:
                results.log("Get Notifications (share_invite)", False, "No share_invite notification found")
                return
        else:
            results.log("Get Notifications", False, f"HTTP {response.status_code}: {response.text}")
            return
        
        # Step 5: Check User B's unread count
        response = requests.get(f"{BACKEND_URL}/notifications/unread-count", headers=headers_b)
        
        if response.status_code == 200:
            unread_data = response.json()
            if unread_data.get("count", 0) >= 1:
                results.log("Unread Count Check", True, f'Unread count: {unread_data["count"]}')
            else:
                results.log("Unread Count Check", False, f'Expected ≥1 unread, got {unread_data.get("count", 0)}')
        else:
            results.log("Unread Count Check", False, f"HTTP {response.status_code}: {response.text}")
        
        # Step 6: Mark notification as read
        response = requests.post(f"{BACKEND_URL}/notifications/{notif_id}/read", headers=headers_b)
        
        if response.status_code == 200:
            results.log("Mark Notification Read", True, response.json().get("message", "Success"))
        else:
            results.log("Mark Notification Read", False, f"HTTP {response.status_code}: {response.text}")
        
        # Step 7: Verify unread count is now 0
        response = requests.get(f"{BACKEND_URL}/notifications/unread-count", headers=headers_b)
        
        if response.status_code == 200:
            unread_data = response.json()
            if unread_data.get("count", 1) == 0:
                results.log("Unread Count After Read", True, "Count correctly reduced to 0")
            else:
                results.log("Unread Count After Read", False, f'Expected 0, got {unread_data.get("count", 1)}')
        else:
            results.log("Unread Count After Read", False, f"HTTP {response.status_code}: {response.text}")
        
        # Step 8: User B contributes to share
        contribute_data = {
            "assessments": {
                "o1_f1": 80,  # Job A - Salary
                "o1_f2": 75,  # Job A - Work-Life Balance  
                "o1_f3": 85,  # Job A - Growth
                "o2_f1": 90,  # Job B - Salary
                "o2_f2": 45,  # Job B - Work-Life Balance
                "o2_f3": 55   # Job B - Growth
            },
            "note": "Based on my experience, Job A offers better long-term growth potential."
        }
        
        response = requests.post(f"{BACKEND_URL}/shared-steps/{share_id}/contribute", json=contribute_data, headers=headers_b)
        
        if response.status_code == 200:
            results.log("User B Contribution (creates notification)", True, response.json().get("message", "Success"))
        else:
            results.log("User B Contribution", False, f"HTTP {response.status_code}: {response.text}")
            return
        
        # Wait for notification creation
        time.sleep(1)
        
        # Step 9: Check User A gets share_contributed notification  
        response = requests.get(f"{BACKEND_URL}/notifications", headers=headers_a)
        
        if response.status_code == 200:
            notifications = response.json()
            contributed_notifications = [n for n in notifications if n["type"] == "share_contributed"]
            
            if contributed_notifications:
                notif = contributed_notifications[0]
                results.log("User A Gets Contribution Notification", True, f'Found: "{notif["title"]}" - {notif["message"]}')
            else:
                results.log("User A Gets Contribution Notification", False, "No share_contributed notification found")
        else:
            results.log("User A Gets Contribution Notification", False, f"HTTP {response.status_code}: {response.text}")
        
        # Step 10: Test mark-all-read
        # First create another notification by having User A share another step
        share_data2 = {
            "decision_id": decision_id,
            "step_number": 6,
            "recipient_emails": [user_b_email],
            "message": "Also need help with factor prioritization"
        }
        
        requests.post(f"{BACKEND_URL}/decisions/{decision_id}/share-step", json=share_data2, headers=headers_a)
        time.sleep(1)
        
        response = requests.post(f"{BACKEND_URL}/notifications/read-all", headers=headers_b)
        
        if response.status_code == 200:
            results.log("Mark All Read", True, response.json().get("message", "Success"))
        else:
            results.log("Mark All Read", False, f"HTTP {response.status_code}: {response.text}")
        
        # Step 11: Test delete notification
        # Get a notification ID to delete
        response = requests.get(f"{BACKEND_URL}/notifications", headers=headers_b)
        if response.status_code == 200 and response.json():
            delete_notif_id = response.json()[0]["id"]
            
            response = requests.delete(f"{BACKEND_URL}/notifications/{delete_notif_id}", headers=headers_b)
            
            if response.status_code == 200:
                results.log("Delete Notification", True, response.json().get("message", "Success"))
            else:
                results.log("Delete Notification", False, f"HTTP {response.status_code}: {response.text}")
        else:
            results.log("Delete Notification", False, "No notifications found to delete")
            
    except Exception as e:
        results.log("Notification System Testing", False, f"Exception: {str(e)}")

def test_folder_analytics(results: TestResults):
    """Test folder analytics APIs"""
    print("\n=== TESTING FOLDER ANALYTICS APIs ===")
    
    try:
        # Generate unique timestamp
        timestamp = str(int(time.time()))
        
        # Register a user for analytics testing
        user_data = register_user(
            f"analytics.user.{timestamp}@careerpath.com",
            "securepass123",
            f"Analytics User {timestamp}"
        )
        token = user_data["session_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        results.log("Analytics User Registration", True, f"Created user: {user_data['name']}")
        
        # Create decisions in different folders
        career_decision1 = create_decision(token, "Job Change Analysis", "Should I switch to a startup?", "career")
        career_decision2 = create_decision(token, "Career Path Planning", "Long-term career strategy", "career")
        finance_decision = create_decision(token, "Investment Portfolio", "Asset allocation strategy", "finance")
        
        # Add factors/options to make decisions "completed"
        for decision_id in [career_decision1, career_decision2, finance_decision]:
            add_factors_and_options_to_decision(token, decision_id)
        
        results.log("Create Decisions in Multiple Folders", True, "Created 2 career + 1 finance decisions")
        
        # Test GET /api/analytics/folders
        response = requests.get(f"{BACKEND_URL}/analytics/folders", headers=headers)
        
        if response.status_code == 200:
            analytics_data = response.json()
            
            # Check response structure
            required_keys = ["folders", "active_folders", "summary"]
            if all(key in analytics_data for key in required_keys):
                results.log("Folders Analytics Structure", True, "Response has required keys: folders, active_folders, summary")
                
                # Check summary fields
                summary = analytics_data["summary"]
                summary_fields = ["total_decisions", "total_completed", "total_folders_used", "overall_completion_rate"]
                
                if all(field in summary for field in summary_fields):
                    results.log("Analytics Summary Fields", True, f"Summary: {json.dumps(summary, indent=2)}")
                    
                    # Verify data makes sense
                    if summary["total_decisions"] == 3 and summary["total_completed"] == 3:
                        results.log("Analytics Data Accuracy", True, "Correct counts: 3 total, 3 completed")
                    else:
                        results.log("Analytics Data Accuracy", False, f"Expected 3/3, got {summary['total_decisions']}/{summary['total_completed']}")
                else:
                    missing = [f for f in summary_fields if f not in summary]
                    results.log("Analytics Summary Fields", False, f"Missing fields: {missing}")
                
                # Check active folders
                active_folders = analytics_data["active_folders"]
                career_folder = next((f for f in active_folders if f["id"] == "career"), None)
                finance_folder = next((f for f in active_folders if f["id"] == "finance"), None)
                
                if career_folder and finance_folder:
                    if career_folder["total_decisions"] == 2 and finance_folder["total_decisions"] == 1:
                        results.log("Folder Breakdown Accuracy", True, "Career: 2 decisions, Finance: 1 decision")
                    else:
                        results.log("Folder Breakdown Accuracy", False, f"Career: {career_folder['total_decisions']}, Finance: {finance_folder['total_decisions']}")
                else:
                    results.log("Folder Breakdown Accuracy", False, "Career or Finance folder not found in active_folders")
            else:
                missing = [k for k in required_keys if k not in analytics_data]
                results.log("Folders Analytics Structure", False, f"Missing keys: {missing}")
        else:
            results.log("Get Folders Analytics", False, f"HTTP {response.status_code}: {response.text}")
            return
        
        # Test GET /api/analytics/folder/career
        response = requests.get(f"{BACKEND_URL}/analytics/folder/career", headers=headers)
        
        if response.status_code == 200:
            folder_data = response.json()
            
            # Check single folder response structure
            expected_fields = ["folder_id", "total_decisions", "completed", "completion_rate", "top_factors", "recent_decisions"]
            
            if all(field in folder_data for field in expected_fields):
                results.log("Single Folder Analytics Structure", True, "Response has all required fields")
                
                # Verify career folder data
                if (folder_data["folder_id"] == "career" and 
                    folder_data["total_decisions"] == 2 and
                    folder_data["completed"] == 2):
                    results.log("Career Folder Detail Accuracy", True, f"Career folder: 2 total, 2 completed, {folder_data['completion_rate']}% completion")
                else:
                    results.log("Career Folder Detail Accuracy", False, f"Unexpected data: {json.dumps(folder_data, indent=2)}")
                
                # Check if top_factors and recent_decisions are present
                if isinstance(folder_data["top_factors"], list) and isinstance(folder_data["recent_decisions"], list):
                    results.log("Folder Detail Subarrays", True, f"Top factors: {len(folder_data['top_factors'])}, Recent decisions: {len(folder_data['recent_decisions'])}")
                else:
                    results.log("Folder Detail Subarrays", False, "top_factors or recent_decisions not arrays")
            else:
                missing = [f for f in expected_fields if f not in folder_data]
                results.log("Single Folder Analytics Structure", False, f"Missing fields: {missing}")
        else:
            results.log("Get Single Folder Analytics", False, f"HTTP {response.status_code}: {response.text}")
            
    except Exception as e:
        results.log("Folder Analytics Testing", False, f"Exception: {str(e)}")

def main():
    """Run all backend tests"""
    print("🚀 BACKEND TESTING - View Dezider API")
    print(f"Testing against: {BACKEND_URL}")
    print(f"Started at: {datetime.now().isoformat()}")
    
    results = TestResults()
    
    # Test 1: Health Check Endpoint Fix
    test_health_check(results)
    
    # Test 2: Notification System APIs
    test_notification_system(results)
    
    # Test 3: Folder Analytics APIs  
    test_folder_analytics(results)
    
    # Print Summary
    print(f"\n{'='*60}")
    print("🏁 BACKEND TESTING COMPLETE")
    print(f"{'='*60}")
    print(f"✅ PASSED: {results.passed}")
    print(f"❌ FAILED: {results.failed}")
    print(f"📊 TOTAL: {results.passed + results.failed}")
    
    if results.failed > 0:
        print(f"\n❌ FAILED TESTS:")
        for result in results.results:
            if "❌ FAILED" in result:
                print(f"   {result}")
    
    print(f"\n✅ SUCCESSFUL TESTS:")
    for result in results.results:
        if "✅ PASSED" in result:
            print(f"   {result}")
    
    print(f"\nCompleted at: {datetime.now().isoformat()}")
    return results.failed == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)