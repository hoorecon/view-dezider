#!/usr/bin/env python3
"""
Backend Testing Script for Push Notification and Sharing Infrastructure
Tests the specific features mentioned in the review request:
1. Register 2 users (sender and recipient)
2. Test push token registration
3. Test user search
4. Test expert CRUD (as admin)
5. Test share step with enhanced notification payload
6. Verify notification has rich data
"""

import asyncio
import httpx
import json
import uuid
from datetime import datetime

# Backend URL from frontend/.env
BASE_URL = "https://dezider-multi-user.preview.emergentagent.com/api"

class BackendTester:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.users = {}  # Store user data and tokens
        self.decisions = {}  # Store decision data
        self.experts = {}  # Store expert data
        self.notifications = {}  # Store notification data
        
    async def close(self):
        await self.client.aclose()
    
    async def register_user(self, name: str, email: str, password: str = "testpass123"):
        """Register a new user"""
        print(f"\n🔐 Registering user: {name} ({email})")
        
        response = await self.client.post(f"{BASE_URL}/auth/register", json={
            "name": name,
            "email": email,
            "password": password
        })
        
        if response.status_code == 200:
            user_data = response.json()
            self.users[name] = {
                "data": user_data,
                "email": email,
                "password": password,
                "token": user_data.get("session_token")
            }
            print(f"✅ User {name} registered successfully")
            print(f"   User ID: {user_data.get('user_id')}")
            print(f"   Session Token: {user_data.get('session_token')[:20]}...")
            return True
        else:
            print(f"❌ Failed to register {name}: {response.status_code} - {response.text}")
            return False
    
    async def test_push_token_registration(self, user_name: str):
        """Test push token registration for a user"""
        print(f"\n📱 Testing push token registration for {user_name}")
        
        if user_name not in self.users:
            print(f"❌ User {user_name} not found")
            return False
            
        token = self.users[user_name]["token"]
        test_push_token = f"ExponentPushToken[test_{uuid.uuid4().hex[:8]}]"
        
        response = await self.client.post(
            f"{BASE_URL}/auth/push-token",
            json={"push_token": test_push_token},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Push token registered successfully")
            print(f"   Token: {test_push_token}")
            print(f"   Response: {result}")
            self.users[user_name]["push_token"] = test_push_token
            return True
        else:
            print(f"❌ Failed to register push token: {response.status_code} - {response.text}")
            return False
    
    async def test_user_search(self, searcher_name: str, search_query: str):
        """Test user search functionality"""
        print(f"\n🔍 Testing user search by {searcher_name} for query: '{search_query}'")
        
        if searcher_name not in self.users:
            print(f"❌ User {searcher_name} not found")
            return False
            
        token = self.users[searcher_name]["token"]
        
        response = await self.client.get(
            f"{BASE_URL}/users/search",
            params={"q": search_query},
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            results = response.json()
            print(f"✅ User search successful")
            print(f"   Query: {search_query}")
            print(f"   Results count: {len(results)}")
            for user in results:
                print(f"   - {user.get('name')} ({user.get('email')})")
            
            # Verify current user is excluded
            searcher_email = self.users[searcher_name]["email"]
            current_user_in_results = any(u.get("email") == searcher_email for u in results)
            if not current_user_in_results:
                print(f"✅ Current user correctly excluded from search results")
            else:
                print(f"⚠️  Current user found in search results (should be excluded)")
            
            return True
        else:
            print(f"❌ Failed to search users: {response.status_code} - {response.text}")
            return False
    
    async def setup_admin(self, user_name: str):
        """Setup user as super admin"""
        print(f"\n👑 Setting up {user_name} as super admin")
        
        if user_name not in self.users:
            print(f"❌ User {user_name} not found")
            return False
            
        token = self.users[user_name]["token"]
        
        response = await self.client.post(
            f"{BASE_URL}/admin/setup",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Admin setup successful")
            print(f"   Role: {result.get('role')}")
            self.users[user_name]["role"] = "super_admin"
            return True
        elif response.status_code == 400:
            print(f"ℹ️  Super admin already exists (expected if running multiple times)")
            # Try to get current user info to check if they're admin
            me_response = await self.client.get(
                f"{BASE_URL}/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            if me_response.status_code == 200:
                user_info = me_response.json()
                role = user_info.get("role", "user")
                print(f"   Current user role: {role}")
                self.users[user_name]["role"] = role
                return role in ["admin", "co_admin", "super_admin"]
            return False
        else:
            print(f"❌ Failed to setup admin: {response.status_code} - {response.text}")
            return False
    
    async def test_expert_crud(self, admin_user: str):
        """Test expert CRUD operations"""
        print(f"\n👨‍⚕️ Testing expert CRUD operations as {admin_user}")
        
        if admin_user not in self.users:
            print(f"❌ User {admin_user} not found")
            return False
            
        token = self.users[admin_user]["token"]
        
        # Create expert
        expert_data = {
            "name": "Dr. Sarah Smith",
            "email": "drsmith@careercoaching.com",
            "specialization": "Career Coaching & Leadership Development",
            "bio": "Expert career coach with 15+ years experience helping professionals navigate career transitions and leadership development."
        }
        
        print(f"📝 Creating expert: {expert_data['name']}")
        response = await self.client.post(
            f"{BASE_URL}/experts",
            json=expert_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            result = response.json()
            expert_id = result.get("id")
            print(f"✅ Expert created successfully")
            print(f"   Expert ID: {expert_id}")
            print(f"   Name: {expert_data['name']}")
            print(f"   Specialization: {expert_data['specialization']}")
            self.experts["dr_smith"] = {"id": expert_id, **expert_data}
        else:
            print(f"❌ Failed to create expert: {response.status_code} - {response.text}")
            return False
        
        # Get experts list
        print(f"\n📋 Retrieving experts list")
        response = await self.client.get(f"{BASE_URL}/experts")
        
        if response.status_code == 200:
            experts = response.json()
            print(f"✅ Retrieved experts list successfully")
            print(f"   Total experts: {len(experts)}")
            
            # Find our created expert
            created_expert = next((e for e in experts if e.get("id") == expert_id), None)
            if created_expert:
                print(f"✅ Created expert found in list")
                print(f"   Name: {created_expert.get('name')}")
                print(f"   Email: {created_expert.get('email')}")
                print(f"   Specialization: {created_expert.get('specialization')}")
                print(f"   Active: {created_expert.get('is_active')}")
                return True
            else:
                print(f"❌ Created expert not found in list")
                return False
        else:
            print(f"❌ Failed to retrieve experts: {response.status_code} - {response.text}")
            return False
    
    async def create_test_decision(self, user_name: str):
        """Create a test decision for sharing"""
        print(f"\n📋 Creating test decision for {user_name}")
        
        if user_name not in self.users:
            print(f"❌ User {user_name} not found")
            return False
            
        token = self.users[user_name]["token"]
        
        # Create decision
        decision_data = {
            "title": "Career Transition Decision",
            "context": "Deciding between staying at current company vs joining a startup vs freelancing",
            "folder": "career"
        }
        
        response = await self.client.post(
            f"{BASE_URL}/decisions",
            json=decision_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            result = response.json()
            decision_id = result.get("id")
            print(f"✅ Decision created successfully")
            print(f"   Decision ID: {decision_id}")
            print(f"   Title: {decision_data['title']}")
            
            # Add some factors and options to make it more realistic
            factors = [
                {"id": str(uuid.uuid4()), "name": "Salary & Benefits", "category": "primary", "rating": 80, "order": 0},
                {"id": str(uuid.uuid4()), "name": "Work-Life Balance", "category": "primary", "rating": 70, "order": 1},
                {"id": str(uuid.uuid4()), "name": "Growth Opportunities", "category": "primary", "rating": 90, "order": 2},
                {"id": str(uuid.uuid4()), "name": "Job Security", "category": "secondary", "rating": 60, "order": 3}
            ]
            
            options = [
                {
                    "id": str(uuid.uuid4()),
                    "name": "Stay at Current Company",
                    "assessments": [
                        {"factor_id": factors[0]["id"], "percentage": 75, "assessment_mode": "H"},
                        {"factor_id": factors[1]["id"], "percentage": 50, "assessment_mode": "M"},
                        {"factor_id": factors[2]["id"], "percentage": 25, "assessment_mode": "L"},
                        {"factor_id": factors[3]["id"], "percentage": 90, "assessment_mode": "H"}
                    ],
                    "worth_percentage": 0.0
                },
                {
                    "id": str(uuid.uuid4()),
                    "name": "Join Startup",
                    "assessments": [
                        {"factor_id": factors[0]["id"], "percentage": 60, "assessment_mode": "M"},
                        {"factor_id": factors[1]["id"], "percentage": 40, "assessment_mode": "L"},
                        {"factor_id": factors[2]["id"], "percentage": 95, "assessment_mode": "H"},
                        {"factor_id": factors[3]["id"], "percentage": 30, "assessment_mode": "L"}
                    ],
                    "worth_percentage": 0.0
                }
            ]
            
            # Update decision with factors and options
            update_response = await self.client.put(
                f"{BASE_URL}/decisions/{decision_id}",
                json={"factors": factors, "options": options},
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if update_response.status_code == 200:
                print(f"✅ Decision updated with factors and options")
                self.decisions[user_name] = {
                    "id": decision_id,
                    "title": decision_data["title"],
                    "factors": factors,
                    "options": options
                }
                return decision_id
            else:
                print(f"⚠️  Decision created but failed to update: {update_response.status_code}")
                self.decisions[user_name] = {"id": decision_id, "title": decision_data["title"]}
                return decision_id
        else:
            print(f"❌ Failed to create decision: {response.status_code} - {response.text}")
            return None
    
    async def test_share_step(self, sender_name: str, recipient_name: str, decision_id: str):
        """Test step sharing with enhanced notification payload"""
        print(f"\n🤝 Testing step sharing from {sender_name} to {recipient_name}")
        
        if sender_name not in self.users or recipient_name not in self.users:
            print(f"❌ Required users not found")
            return False
            
        sender_token = self.users[sender_name]["token"]
        recipient_email = self.users[recipient_name]["email"]
        
        # Share step 7 (Assessment step)
        share_data = {
            "decision_id": decision_id,
            "step_number": 7,
            "recipient_emails": [recipient_email],
            "merge_mode": "self_weighted",
            "message": "Hi! I'd love your input on this career decision. Please help me assess the options based on the factors I've identified."
        }
        
        response = await self.client.post(
            f"{BASE_URL}/decisions/{decision_id}/share-step",
            json=share_data,
            headers={"Authorization": f"Bearer {sender_token}"}
        )
        
        if response.status_code == 200:
            result = response.json()
            share_id = result.get("id")
            print(f"✅ Step shared successfully")
            print(f"   Share ID: {share_id}")
            print(f"   Step: {share_data['step_number']}")
            print(f"   Recipients: {len(share_data['recipient_emails'])}")
            print(f"   Message: {share_data['message'][:50]}...")
            
            # Store share info for later verification
            self.notifications["share_id"] = share_id
            return share_id
        else:
            print(f"❌ Failed to share step: {response.status_code} - {response.text}")
            return None
    
    async def test_notifications_with_rich_data(self, recipient_name: str):
        """Test that notifications contain rich data as specified"""
        print(f"\n🔔 Testing notifications with rich data for {recipient_name}")
        
        if recipient_name not in self.users:
            print(f"❌ User {recipient_name} not found")
            return False
            
        token = self.users[recipient_name]["token"]
        
        # Get notifications
        response = await self.client.get(
            f"{BASE_URL}/notifications",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if response.status_code == 200:
            notifications = response.json()
            print(f"✅ Retrieved notifications successfully")
            print(f"   Total notifications: {len(notifications)}")
            
            # Find the share_invite notification
            share_notifications = [n for n in notifications if n.get("type") == "share_invite"]
            
            if share_notifications:
                latest_share = share_notifications[0]  # Most recent
                print(f"✅ Found share invitation notification")
                print(f"   Type: {latest_share.get('type')}")
                print(f"   Title: {latest_share.get('title')}")
                print(f"   Message: {latest_share.get('message')}")
                
                # Check for enhanced payload data
                data = latest_share.get("data", {})
                required_fields = [
                    "sender_name", "sender_email", "decision_title", 
                    "step_name", "step_number", "share_id", "decision_id"
                ]
                
                print(f"\n📊 Verifying enhanced notification payload:")
                all_fields_present = True
                for field in required_fields:
                    if field in data:
                        print(f"   ✅ {field}: {data[field]}")
                    else:
                        print(f"   ❌ {field}: MISSING")
                        all_fields_present = False
                
                if all_fields_present:
                    print(f"\n✅ All required enhanced payload fields present!")
                    print(f"   Enhanced notification data verified:")
                    print(f"   - Sender: {data.get('sender_name')} ({data.get('sender_email')})")
                    print(f"   - Decision: {data.get('decision_title')}")
                    print(f"   - Step: {data.get('step_number')} - {data.get('step_name')}")
                    return True
                else:
                    print(f"\n❌ Some required enhanced payload fields are missing")
                    return False
            else:
                print(f"❌ No share invitation notifications found")
                return False
        else:
            print(f"❌ Failed to retrieve notifications: {response.status_code} - {response.text}")
            return False
    
    async def run_comprehensive_test(self):
        """Run all tests in sequence"""
        print("🚀 Starting Comprehensive Push Notification and Sharing Infrastructure Test")
        print("=" * 80)
        
        test_results = []
        
        # 1. Register 2 users (sender and recipient)
        print("\n" + "="*50)
        print("TEST 1: Register 2 users (sender and recipient)")
        print("="*50)
        
        timestamp = datetime.now().strftime("%H%M%S")
        sender_email = f"alice.sender.{timestamp}@careerpath.com"
        recipient_email = f"bob.recipient.{timestamp}@careerpath.com"
        
        sender_success = await self.register_user("Alice", sender_email)
        recipient_success = await self.register_user("Bob", recipient_email)
        
        test_results.append(("User Registration", sender_success and recipient_success))
        
        if not (sender_success and recipient_success):
            print("❌ User registration failed, cannot continue tests")
            return test_results
        
        # 2. Test push token registration
        print("\n" + "="*50)
        print("TEST 2: Push Token Registration")
        print("="*50)
        
        alice_push = await self.test_push_token_registration("Alice")
        bob_push = await self.test_push_token_registration("Bob")
        
        test_results.append(("Push Token Registration", alice_push and bob_push))
        
        # 3. Test user search
        print("\n" + "="*50)
        print("TEST 3: User Search Functionality")
        print("="*50)
        
        # Test searching for Bob from Alice's account
        search_success = await self.test_user_search("Alice", "bob")
        test_results.append(("User Search", search_success))
        
        # 4. Test expert CRUD (as admin)
        print("\n" + "="*50)
        print("TEST 4: Expert CRUD Operations (Admin)")
        print("="*50)
        
        # Setup Alice as admin
        admin_setup = await self.setup_admin("Alice")
        if admin_setup:
            expert_crud = await self.test_expert_crud("Alice")
            test_results.append(("Expert CRUD", expert_crud))
        else:
            print("❌ Admin setup failed, skipping expert CRUD test")
            test_results.append(("Expert CRUD", False))
        
        # 5. Create decision and test share step
        print("\n" + "="*50)
        print("TEST 5: Decision Creation and Step Sharing")
        print("="*50)
        
        decision_id = await self.create_test_decision("Alice")
        if decision_id:
            share_success = await self.test_share_step("Alice", "Bob", decision_id)
            test_results.append(("Step Sharing", share_success is not None))
            
            # 6. Verify notification has rich data
            print("\n" + "="*50)
            print("TEST 6: Notification Rich Data Verification")
            print("="*50)
            
            # Wait a moment for notification to be created
            await asyncio.sleep(1)
            
            notification_success = await self.test_notifications_with_rich_data("Bob")
            test_results.append(("Notification Rich Data", notification_success))
        else:
            print("❌ Decision creation failed, skipping sharing tests")
            test_results.append(("Step Sharing", False))
            test_results.append(("Notification Rich Data", False))
        
        return test_results
    
    def print_test_summary(self, results):
        """Print comprehensive test summary"""
        print("\n" + "="*80)
        print("🎯 COMPREHENSIVE TEST SUMMARY")
        print("="*80)
        
        passed = sum(1 for _, success in results if success)
        total = len(results)
        
        print(f"\n📊 Overall Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        print("\n📋 Detailed Results:")
        
        for test_name, success in results:
            status = "✅ PASSED" if success else "❌ FAILED"
            print(f"   {status}: {test_name}")
        
        if passed == total:
            print(f"\n🎉 ALL TESTS PASSED! Push notification and sharing infrastructure is working correctly.")
        else:
            failed_tests = [name for name, success in results if not success]
            print(f"\n⚠️  SOME TESTS FAILED:")
            for test in failed_tests:
                print(f"   - {test}")
        
        print("\n" + "="*80)

async def main():
    """Main test execution"""
    tester = BackendTester()
    
    try:
        results = await tester.run_comprehensive_test()
        tester.print_test_summary(results)
        
        # Return success/failure for CI/CD
        all_passed = all(success for _, success in results)
        return 0 if all_passed else 1
        
    except Exception as e:
        print(f"\n❌ Test execution failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        await tester.close()

if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)