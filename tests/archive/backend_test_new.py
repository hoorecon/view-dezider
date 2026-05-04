#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for View Dezider - New Features
Testing new Decision Folders and Step Sharing System features
"""

import asyncio
import httpx
import json
import time
from datetime import datetime

# Base URL from environment
BASE_URL = "https://voice-browse-epic.preview.emergentagent.com/api"

class ViewDeziderTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.users = {}  # Store user sessions
        
    async def register_user(self, email: str, password: str, name: str):
        """Register a new user"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/auth/register", json={
                "email": email,
                "password": password,
                "name": name
            })
            
            if response.status_code in [200, 201]:
                data = response.json()
                self.users[email] = {
                    "user_id": data["user_id"],
                    "email": data["email"],
                    "name": data["name"],
                    "session_token": data["session_token"]
                }
                print(f"✅ User registered: {email}")
                return True
            else:
                print(f"❌ Registration failed for {email}: {response.text}")
                return False
    
    async def login_user(self, email: str, password: str):
        """Login existing user"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/auth/login", json={
                "email": email,
                "password": password
            })
            
            if response.status_code == 200:
                data = response.json()
                self.users[email] = {
                    "user_id": data["user_id"],
                    "email": data["email"], 
                    "name": data["name"],
                    "session_token": data["session_token"]
                }
                print(f"✅ User logged in: {email}")
                return True
            else:
                print(f"❌ Login failed for {email}: {response.text}")
                return False
    
    def get_auth_headers(self, email: str):
        """Get authorization headers for a user"""
        if email not in self.users:
            raise ValueError(f"User {email} not found")
        return {"Authorization": f"Bearer {self.users[email]['session_token']}"}
    
    async def test_folders_endpoint(self):
        """Test GET /api/folders endpoint"""
        print("\n🧪 Testing Folders Endpoint...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.base_url}/folders")
            
            if response.status_code == 200:
                folders = response.json()
                
                # Validate response structure
                if len(folders) == 10:
                    print(f"✅ Folders endpoint returned {len(folders)} folders")
                    
                    # Validate each folder has required fields
                    for folder in folders:
                        if all(key in folder for key in ["id", "name", "icon", "color"]):
                            print(f"✅ Folder '{folder['name']}' has all required fields")
                        else:
                            print(f"❌ Folder '{folder.get('name', 'unknown')}' missing fields")
                            return False
                    
                    # Check for specific expected folders
                    folder_ids = [f["id"] for f in folders]
                    expected_folders = ["career", "finance", "relationships", "holistic_health"]
                    for expected in expected_folders:
                        if expected in folder_ids:
                            print(f"✅ Found expected folder: {expected}")
                        else:
                            print(f"❌ Missing expected folder: {expected}")
                            return False
                    
                    return True
                else:
                    print(f"❌ Expected 10 folders, got {len(folders)}")
                    return False
            else:
                print(f"❌ Folders endpoint failed: {response.text}")
                return False
    
    async def test_decision_with_folder(self, user_email: str):
        """Test creating decision with folder parameter"""
        print(f"\n🧪 Testing Decision Creation with Folder for {user_email}...")
        
        headers = self.get_auth_headers(user_email)
        decision_data = {
            "title": "Career Change Decision - Finance Focus",
            "context": "Considering switching from marketing to financial consulting",
            "folder": "career"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/decisions", 
                                       json=decision_data, headers=headers)
            
            if response.status_code in [200, 201]:
                result = response.json()
                decision_id = result.get("id")
                if decision_id:
                    # Get the full decision details
                    response = await client.get(f"{self.base_url}/decisions/{decision_id}", headers=headers)
                    if response.status_code == 200:
                        decision = response.json()
                        if decision.get("folder") == "career":
                            print(f"✅ Decision created with folder: {decision['folder']}")
                            return decision["id"]
                        else:
                            print(f"❌ Decision folder mismatch. Expected: career, Got: {decision.get('folder')}")
                            return None
                    else:
                        print(f"❌ Failed to retrieve decision details: {response.text}")
                        return None
                else:
                    print(f"❌ Decision creation response missing ID")
                    return None
            else:
                print(f"❌ Decision creation failed: {response.text}")
                return None
    
    async def test_decision_folder_filter(self, user_email: str):
        """Test filtering decisions by folder"""
        print(f"\n🧪 Testing Decision Folder Filtering for {user_email}...")
        
        headers = self.get_auth_headers(user_email)
        
        # Create decisions in different folders
        folders_to_test = ["career", "finance", "relationships"]
        created_decisions = {}
        
        for folder in folders_to_test:
            decision_data = {
                "title": f"Decision in {folder.title()} folder",
                "context": f"This is a test decision for the {folder} life area",
                "folder": folder
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{self.base_url}/decisions", 
                                           json=decision_data, headers=headers)
                if response.status_code in [200, 201]:
                    result = response.json()
                    decision_id = result.get("id")
                    if decision_id:
                        created_decisions[folder] = decision_id
                        print(f"✅ Created decision in {folder} folder")
                    else:
                        print(f"❌ Failed to create decision in {folder} folder - no ID returned")
                        return False
                else:
                    print(f"❌ Failed to create decision in {folder} folder")
                    return False
        
        # Test filtering by folder
        for folder in folders_to_test:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}/decisions?folder={folder}",
                                          headers=headers)
                
                if response.status_code == 200:
                    decisions = response.json()
                    # Find our test decision in the results
                    found_decision = any(d["id"] == created_decisions[folder] for d in decisions)
                    if found_decision:
                        print(f"✅ Folder filter working for {folder}")
                    else:
                        print(f"❌ Folder filter failed for {folder} - decision not found")
                        return False
                else:
                    print(f"❌ Folder filter request failed for {folder}: {response.text}")
                    return False
        
        return True
    
    async def setup_decision_for_sharing(self, user_email: str):
        """Create a decision with factors and options for sharing"""
        headers = self.get_auth_headers(user_email)
        
        # Create decision
        decision_data = {
            "title": "Job Opportunity Analysis",
            "context": "Evaluating a senior consultant position at Tech Corp vs staying at current company",
            "folder": "career"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/decisions", 
                                       json=decision_data, headers=headers)
            if response.status_code not in [200, 201]:
                print(f"❌ Failed to create decision for sharing")
                return None
                
            result = response.json()
            decision_id = result.get("id")
            if not decision_id:
                print(f"❌ Failed to create decision for sharing - no ID returned")
                return None
            
            # Add factors
            factors = [
                {"id": "f1", "name": "Salary Increase", "category": "primary", "rating": 90, "order": 1},
                {"id": "f2", "name": "Work-Life Balance", "category": "primary", "rating": 85, "order": 2},
                {"id": "f3", "name": "Career Growth", "category": "secondary", "rating": 80, "order": 3},
                {"id": "f4", "name": "Company Culture", "category": "secondary", "rating": 75, "order": 4}
            ]
            
            # Add options with assessments
            options = [
                {
                    "id": "opt1", 
                    "name": "Accept Tech Corp Offer",
                    "assessments": [
                        {"factor_id": "f1", "percentage": 85, "unit_value": "95000 USD", "assessment_mode": "H"},
                        {"factor_id": "f2", "percentage": 70, "unit_value": "Standard", "assessment_mode": "M"},
                        {"factor_id": "f3", "percentage": 90, "unit_value": "Senior Level", "assessment_mode": "H"},
                        {"factor_id": "f4", "percentage": 80, "unit_value": "Innovative", "assessment_mode": "H"}
                    ]
                },
                {
                    "id": "opt2",
                    "name": "Stay at Current Company", 
                    "assessments": [
                        {"factor_id": "f1", "percentage": 60, "unit_value": "72000 USD", "assessment_mode": "M"},
                        {"factor_id": "f2", "percentage": 85, "unit_value": "Excellent", "assessment_mode": "H"},
                        {"factor_id": "f3", "percentage": 65, "unit_value": "Limited", "assessment_mode": "M"},
                        {"factor_id": "f4", "percentage": 90, "unit_value": "Familiar", "assessment_mode": "H"}
                    ]
                }
            ]
            
            # Update decision with factors and options
            update_data = {
                "factors": factors,
                "options": options,
                "status": "in_progress"
            }
            
            response = await client.put(f"{self.base_url}/decisions/{decision_id}",
                                      json=update_data, headers=headers)
            
            if response.status_code == 200:
                print(f"✅ Decision setup complete for sharing: {decision_id}")
                return decision_id
            else:
                print(f"❌ Failed to update decision with factors/options: {response.text}")
                return None
    
    async def test_step_sharing_complete_flow(self):
        """Test complete step sharing system flow with two users"""
        print(f"\n🧪 Testing Complete Step Sharing Flow...")
        
        # Setup users
        sharer_email = "sharer_a@test.com"
        recipient_email = "sharer_b@test.com"
        
        # Register users with unique timestamps to avoid conflicts
        timestamp = int(time.time())
        sharer_email = f"sharer_a_{timestamp}@test.com"
        recipient_email = f"sharer_b_{timestamp}@test.com"
        
        # Register both users
        await self.register_user(sharer_email, "test123456", "Sharer User A")
        await self.register_user(recipient_email, "test123456", "Sharer User B")
        
        # Setup decision for sharing
        decision_id = await self.setup_decision_for_sharing(sharer_email)
        if not decision_id:
            return False
        
        # Step 1: User A shares step 7 with User B
        print(f"\n📤 Testing Share Step (User A to User B)...")
        
        share_data = {
            "decision_id": decision_id,
            "step_number": 7,
            "recipient_emails": [recipient_email],
            "merge_mode": "self_weighted",
            "message": "Please review my option assessments and provide your input"
        }
        
        headers_a = self.get_auth_headers(sharer_email)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/decisions/{decision_id}/share-step",
                                       json=share_data, headers=headers_a)
            
            if response.status_code in [200, 201]:
                share_result = response.json()
                share_id = share_result["id"]
                print(f"✅ Step shared successfully. Share ID: {share_id}")
            else:
                print(f"❌ Step sharing failed: {response.text}")
                return False
        
        # Step 2: User A checks sent shares
        print(f"\n📤 Testing Get Sent Shares (User A)...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.base_url}/shared-steps/sent", headers=headers_a)
            
            if response.status_code == 200:
                sent_shares = response.json()
                if len(sent_shares) > 0 and any(s["id"] == share_id for s in sent_shares):
                    print(f"✅ User A can see sent shares: {len(sent_shares)} shares")
                else:
                    print(f"❌ User A cannot see sent share in list")
                    return False
            else:
                print(f"❌ Get sent shares failed: {response.text}")
                return False
        
        # Step 3: User B checks received shares
        print(f"\n📥 Testing Get Received Shares (User B)...")
        
        headers_b = self.get_auth_headers(recipient_email)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.base_url}/shared-steps/received", headers=headers_b)
            
            if response.status_code == 200:
                received_shares = response.json()
                if len(received_shares) > 0 and any(s["id"] == share_id for s in received_shares):
                    print(f"✅ User B can see received shares: {len(received_shares)} shares")
                else:
                    print(f"❌ User B cannot see received share in list")
                    return False
            else:
                print(f"❌ Get received shares failed: {response.text}")
                return False
        
        # Step 4: User B gets share detail
        print(f"\n🔍 Testing Get Share Detail (User B)...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.base_url}/shared-steps/{share_id}", headers=headers_b)
            
            if response.status_code == 200:
                share_detail = response.json()
                if share_detail["step_number"] == 7 and share_detail["decision_id"] == decision_id:
                    print(f"✅ User B can see share details correctly")
                else:
                    print(f"❌ Share details incorrect")
                    return False
            else:
                print(f"❌ Get share detail failed: {response.text}")
                return False
        
        # Step 5: User B contributes assessments
        print(f"\n✏️ Testing Contribute to Share (User B)...")
        
        contribution_data = {
            "assessments": {
                "opt1_f1": 80,  # Tech Corp - Salary: 80%
                "opt1_f2": 65,  # Tech Corp - Work-Life: 65%
                "opt1_f3": 95,  # Tech Corp - Growth: 95%
                "opt1_f4": 75,  # Tech Corp - Culture: 75%
                "opt2_f1": 70,  # Current - Salary: 70%
                "opt2_f2": 90,  # Current - Work-Life: 90%
                "opt2_f3": 60,  # Current - Growth: 60%
                "opt2_f4": 95   # Current - Culture: 95%
            },
            "note": "Based on my experience in similar companies, I think the work-life balance at Tech Corp might be more demanding than expected."
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/shared-steps/{share_id}/contribute",
                                       json=contribution_data, headers=headers_b)
            
            if response.status_code == 200:
                print(f"✅ User B contributed successfully")
            else:
                print(f"❌ Contribution failed: {response.text}")
                return False
        
        # Step 6: User A merges contributions
        print(f"\n🔀 Testing Merge Contributions (User A)...")
        
        merge_data = {
            "merge_mode": "self_weighted"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/shared-steps/{share_id}/merge",
                                       json=merge_data, headers=headers_a)
            
            if response.status_code == 200:
                merge_result = response.json()
                print(f"✅ User A merged contributions successfully")
                print(f"   Merge result: {merge_result.get('message', 'No message')}")
                
                # Verify the decision was updated
                response = await client.get(f"{self.base_url}/decisions/{decision_id}", headers=headers_a)
                if response.status_code == 200:
                    updated_decision = response.json()
                    # Check if options have updated assessments
                    if updated_decision.get("options") and len(updated_decision["options"]) > 0:
                        print(f"✅ Decision updated with merged assessments")
                        return True
                    else:
                        print(f"❌ Decision not properly updated after merge")
                        return False
                else:
                    print(f"❌ Could not verify decision update: {response.text}")
                    return False
            else:
                print(f"❌ Merge failed: {response.text}")
                return False
    
    async def test_decision_new_fields_update(self, user_email: str):
        """Test updating decisions with new fields: reflection, final_notes, folder"""
        print(f"\n🧪 Testing Decision Update with New Fields for {user_email}...")
        
        headers = self.get_auth_headers(user_email)
        
        # Create a test decision
        decision_data = {
            "title": "Investment Strategy Decision",
            "context": "Deciding between real estate and stock market investment",
            "folder": "finance"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/decisions", 
                                       json=decision_data, headers=headers)
            
            if response.status_code not in [200, 201]:
                print(f"❌ Failed to create test decision")
                return False
            
            result = response.json()
            decision_id = result.get("id")
            if not decision_id:
                print(f"❌ Failed to create test decision - no ID returned")
                return False
            
            # Update decision with new fields
            update_data = {
                "reflection": "This was a complex decision that required careful consideration of risk tolerance and time horizon. The analysis revealed that my initial assumptions about market volatility were overly conservative.",
                "final_notes": "Final decision: 70% stock market ETFs, 30% real estate investment. Implementation timeline: 6 months. Review date: December 2025.",
                "folder": "assets",  # Change folder
                "status": "completed"
            }
            
            response = await client.put(f"{self.base_url}/decisions/{decision_id}",
                                      json=update_data, headers=headers)
            
            if response.status_code == 200:
                # Get the updated decision separately since PUT returns just success message
                response = await client.get(f"{self.base_url}/decisions/{decision_id}", headers=headers)
                if response.status_code == 200:
                    updated_decision = response.json()
                    
                    # Verify all new fields are present and correct
                    checks = [
                        ("reflection", update_data["reflection"]),
                        ("final_notes", update_data["final_notes"]),
                        ("folder", update_data["folder"]),
                        ("status", update_data["status"])
                    ]
                    
                    all_passed = True
                    for field, expected_value in checks:
                        actual_value = updated_decision.get(field)
                        if actual_value == expected_value:
                            print(f"✅ Field '{field}' updated correctly")
                        else:
                            print(f"❌ Field '{field}' mismatch. Expected: '{expected_value}', Got: '{actual_value}'")
                            all_passed = False
                    
                    if all_passed:
                        # Verify persistence by getting the decision again
                        response = await client.get(f"{self.base_url}/decisions/{decision_id}", headers=headers)
                        if response.status_code == 200:
                            retrieved_decision = response.json()
                            
                            # Verify fields persist
                            persist_passed = True
                            for field, expected_value in checks:
                                actual_value = retrieved_decision.get(field)
                                if actual_value == expected_value:
                                    print(f"✅ Field '{field}' persisted correctly")
                                else:
                                    print(f"❌ Field '{field}' persistence failed")
                                    persist_passed = False
                            
                            return persist_passed
                        else:
                            print(f"❌ Failed to retrieve decision for persistence check")
                            return False
                    else:
                        return False
                else:
                    print(f"❌ Failed to retrieve updated decision: {response.text}")
                    return False
            else:
                print(f"❌ Decision update failed: {response.text}")
                return False
    
    async def test_existing_endpoints_still_work(self):
        """Test that existing endpoints still work after new features"""
        print(f"\n🧪 Testing Existing Endpoints Still Work...")
        
        # Use one of our test users
        timestamp = int(time.time())
        test_email = f"existing_test_{timestamp}@test.com"
        
        # Register user
        await self.register_user(test_email, "test123456", "Existing Test User")
        headers = self.get_auth_headers(test_email)
        
        tests_passed = 0
        total_tests = 0
        
        # Test Auth Me endpoint
        total_tests += 1
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.base_url}/auth/me", headers=headers)
            if response.status_code == 200:
                user_data = response.json()
                if user_data.get("email") == test_email:
                    print(f"✅ Auth /me endpoint working")
                    tests_passed += 1
                else:
                    print(f"❌ Auth /me endpoint data incorrect")
            else:
                print(f"❌ Auth /me endpoint failed")
        
        # Test PRR Decisions CRUD
        total_tests += 1
        decision_id = None
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Create decision
            decision_data = {
                "title": "Legacy CRUD Test Decision",
                "context": "Testing that existing CRUD still works"
            }
            response = await client.post(f"{self.base_url}/decisions", 
                                       json=decision_data, headers=headers)
            if response.status_code in [200, 201]:
                result = response.json()
                decision_id = result.get("id")
                if decision_id:
                    # Read decision
                    response = await client.get(f"{self.base_url}/decisions/{decision_id}", headers=headers)
                    if response.status_code == 200:
                        print(f"✅ PRR Decisions CRUD working")
                        tests_passed += 1
                    else:
                        print(f"❌ PRR Decision read failed")
                else:
                    print(f"❌ PRR Decision create failed - no ID returned")
            else:
                print(f"❌ PRR Decision create failed")
        
        # Test Test123 Sessions CRUD  
        total_tests += 1
        async with httpx.AsyncClient(timeout=30.0) as client:
            session_data = {"situation": "Should I test the existing endpoints?"}
            response = await client.post(f"{self.base_url}/test123", 
                                       json=session_data, headers=headers)
            if response.status_code in [200, 201]:
                session = response.json()
                
                # List sessions
                response = await client.get(f"{self.base_url}/test123", headers=headers)
                if response.status_code == 200:
                    sessions = response.json()
                    if any(s["id"] == session["id"] for s in sessions):
                        print(f"✅ Test123 Sessions CRUD working")
                        tests_passed += 1
                    else:
                        print(f"❌ Test123 session not found in list")
                else:
                    print(f"❌ Test123 sessions list failed")
            else:
                print(f"❌ Test123 session create failed")
        
        # Test Journal CRUD
        total_tests += 1
        async with httpx.AsyncClient(timeout=30.0) as client:
            journal_data = {
                "decision_title": "Test Existing Journal",
                "decision_description": "Testing journal CRUD still works"
            }
            response = await client.post(f"{self.base_url}/journal", 
                                       json=journal_data, headers=headers)
            if response.status_code in [200, 201]:
                entry = response.json()
                
                # List entries
                response = await client.get(f"{self.base_url}/journal", headers=headers)
                if response.status_code == 200:
                    entries = response.json()
                    if any(e["id"] == entry["id"] for e in entries):
                        print(f"✅ Journal CRUD working") 
                        tests_passed += 1
                    else:
                        print(f"❌ Journal entry not found in list")
                else:
                    print(f"❌ Journal entries list failed")
            else:
                print(f"❌ Journal entry create failed")
        
        # Test Dashboard Stats
        total_tests += 1
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.base_url}/stats", headers=headers)
            if response.status_code == 200:
                stats = response.json()
                if "decisions" in stats and "test123" in stats:
                    print(f"✅ Dashboard stats working")
                    tests_passed += 1
                else:
                    print(f"❌ Dashboard stats missing fields")
            else:
                print(f"❌ Dashboard stats failed")
        
        print(f"\n📊 Existing Endpoints Test Results: {tests_passed}/{total_tests} passed")
        return tests_passed == total_tests
    
    async def run_comprehensive_test_suite(self):
        """Run all tests in the comprehensive test suite"""
        print("🚀 Starting View Dezider Backend Comprehensive Testing...")
        print(f"🌐 Testing against: {self.base_url}")
        print("=" * 80)
        
        test_results = []
        
        # Test 1: Folders endpoint
        result = await self.test_folders_endpoint()
        test_results.append(("Decision Folders API", result))
        
        # Test 2: Create test user for decision testing
        timestamp = int(time.time())
        test_email = f"decision_test_{timestamp}@test.com"
        await self.register_user(test_email, "test123456", "Decision Test User")
        
        # Test 3: Decision creation with folder
        result = await self.test_decision_with_folder(test_email)
        test_results.append(("Decision Creation with Folder", result is not None))
        
        # Test 4: Decision folder filtering
        result = await self.test_decision_folder_filter(test_email)
        test_results.append(("Decision Folder Filtering", result))
        
        # Test 5: Complete step sharing flow
        result = await self.test_step_sharing_complete_flow()
        test_results.append(("Step Sharing Complete Flow", result))
        
        # Test 6: Decision new fields update
        result = await self.test_decision_new_fields_update(test_email)
        test_results.append(("Decision New Fields Update", result))
        
        # Test 7: Existing endpoints still work
        result = await self.test_existing_endpoints_still_work()
        test_results.append(("Existing Endpoints Still Work", result))
        
        # Print final results
        print("\n" + "=" * 80)
        print("🎯 FINAL TEST RESULTS")
        print("=" * 80)
        
        passed_count = 0
        total_count = len(test_results)
        
        for test_name, passed in test_results:
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"{test_name:<40} {status}")
            if passed:
                passed_count += 1
        
        print("=" * 80)
        print(f"OVERALL RESULT: {passed_count}/{total_count} tests passed")
        
        if passed_count == total_count:
            print("🎉 ALL NEW FEATURES WORKING CORRECTLY!")
        else:
            print("⚠️  SOME TESTS FAILED - REVIEW REQUIRED")
        
        return passed_count == total_count

async def main():
    """Main test execution function"""
    tester = ViewDeziderTester()
    success = await tester.run_comprehensive_test_suite()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)