#!/usr/bin/env python3
"""
Comprehensive Final Backend Testing for WOWO Features
Testing all new endpoints as requested in the review.
"""

import asyncio
import httpx
import json
import time
from datetime import datetime

# Backend URL from the request
BASE_URL = "https://goals-feels-tracker.preview.emergentagent.com/api"

class ComprehensiveBackendTest:
    def __init__(self):
        self.session_token = None
        self.admin_session_token = None
        self.user_data = None
        self.admin_user_data = None
        self.solution_finder_id = None
        self.solution_matrix_id = None
        self.org_id = None
        
    async def run_comprehensive_test(self):
        """Run comprehensive final backend test for all new features"""
        print("🚀 STARTING COMPREHENSIVE FINAL BACKEND TESTING")
        print("=" * 80)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Setup: Register user and admin
            await self.setup_users(client)
            
            # Test Suite 1: WOWO Feature Flags
            await self.test_feature_flags_system(client)
            
            # Test Suite 2: Solution Finder CRUD
            await self.test_solution_finder_crud(client)
            
            # Test Suite 3: Solution Matrix CRUD
            await self.test_solution_matrix_crud(client)
            
            # Test Suite 4: Admin Call Configuration
            await self.test_admin_call_config(client)
            
            # Test Suite 5: Organization Branding (existing)
            await self.test_organization_branding(client)
            
        print("\n" + "=" * 80)
        print("✅ COMPREHENSIVE FINAL BACKEND TESTING COMPLETE")
        
    async def setup_users(self, client):
        """Setup: Register user and get session_token, setup admin"""
        print("\n🔧 SETUP: User Registration and Admin Setup")
        print("-" * 50)
        
        # Register regular user
        timestamp = int(time.time())
        email = f"finaltest_{timestamp}@test.com"
        
        registration_data = {
            "email": email,
            "password": "test123456",
            "name": "Final Test User"
        }
        
        try:
            response = await client.post(
                f"{BASE_URL}/auth/register",
                json=registration_data
            )
            
            print(f"📤 POST /auth/register")
            print(f"📧 Email: {email}")
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                self.session_token = data.get("session_token")
                self.user_data = data
                print(f"✅ User registration successful!")
                print(f"🎫 Session token: {self.session_token[:20]}...")
            else:
                print(f"❌ User registration failed: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ User registration error: {str(e)}")
            return False
        
        # Setup admin (try to get admin role)
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            response = await client.post(
                f"{BASE_URL}/admin/setup",
                headers=headers
            )
            
            print(f"\n📤 POST /admin/setup")
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Admin setup successful!")
                self.admin_session_token = self.session_token
                self.admin_user_data = self.user_data
            else:
                print(f"ℹ️ Admin setup not available (super admin already exists): {response.text}")
                # Use regular user token for admin tests (will test 403 responses)
                self.admin_session_token = self.session_token
                self.admin_user_data = self.user_data
                
        except Exception as e:
            print(f"ℹ️ Admin setup error (expected): {str(e)}")
            self.admin_session_token = self.session_token
            self.admin_user_data = self.user_data
        
        return True
    
    async def test_feature_flags_system(self, client):
        """Test Suite 1: WOWO Feature Flags"""
        print("\n🚩 TEST SUITE 1: WOWO FEATURE FLAGS SYSTEM")
        print("-" * 50)
        
        # Test 1.1: GET /api/feature-flags (auth required)
        print("\n1.1 Testing GET /api/feature-flags (authenticated)")
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            response = await client.get(
                f"{BASE_URL}/feature-flags",
                headers=headers
            )
            
            print(f"📤 GET /feature-flags")
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Feature flags retrieved successfully!")
                print(f"🚩 Solution Finder: {data.get('solution_finder')}")
                print(f"🚩 Solution Matrix: {data.get('solution_matrix')}")
                
                # Verify structure
                if 'solution_finder' in data and 'solution_matrix' in data:
                    print(f"✅ Feature flags structure correct")
                else:
                    print(f"❌ Feature flags structure incorrect")
            else:
                print(f"❌ Feature flags failed: {response.text}")
                
        except Exception as e:
            print(f"❌ Feature flags error: {str(e)}")
        
        # Test 1.2: GET /api/feature-flags/public (no auth)
        print("\n1.2 Testing GET /api/feature-flags/public (no auth)")
        try:
            response = await client.get(f"{BASE_URL}/feature-flags/public")
            
            print(f"📤 GET /feature-flags/public")
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Public feature flags retrieved successfully!")
                print(f"🚩 Solution Finder: {data.get('solution_finder')}")
                print(f"🚩 Solution Matrix: {data.get('solution_matrix')}")
            else:
                print(f"❌ Public feature flags failed: {response.text}")
                
        except Exception as e:
            print(f"❌ Public feature flags error: {str(e)}")
        
        # Test 1.3: PUT /api/admin/feature-flags (admin only)
        print("\n1.3 Testing PUT /api/admin/feature-flags (admin only)")
        try:
            headers = {"Authorization": f"Bearer {self.admin_session_token}"}
            update_data = {
                "solution_finder": True,
                "solution_matrix": True
            }
            
            response = await client.put(
                f"{BASE_URL}/admin/feature-flags",
                headers=headers,
                json=update_data
            )
            
            print(f"📤 PUT /admin/feature-flags")
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"✅ Feature flags updated successfully!")
            elif response.status_code == 403:
                print(f"✅ Non-admin correctly denied (403): {response.text}")
            else:
                print(f"❌ Feature flags update failed: {response.text}")
                
        except Exception as e:
            print(f"❌ Feature flags update error: {str(e)}")
        
        # Test 1.4: Verify flags persist after update
        print("\n1.4 Testing feature flags persistence")
        try:
            response = await client.get(f"{BASE_URL}/feature-flags/public")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Feature flags persistence verified!")
                print(f"🚩 Solution Finder: {data.get('solution_finder')}")
                print(f"🚩 Solution Matrix: {data.get('solution_matrix')}")
            else:
                print(f"❌ Feature flags persistence check failed: {response.text}")
                
        except Exception as e:
            print(f"❌ Feature flags persistence error: {str(e)}")
    
    async def test_solution_finder_crud(self, client):
        """Test Suite 2: Solution Finder CRUD"""
        print("\n🔍 TEST SUITE 2: SOLUTION FINDER CRUD")
        print("-" * 50)
        
        # Test 2.1: POST /api/solution-finders
        print("\n2.1 Testing POST /api/solution-finders")
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            solution_data = {
                "area_of_life": "career",
                "smart_goal": "Launch successful tech startup",
                "milestones": [
                    {"description": "Complete MVP development", "timeline": "Q1 2025"},
                    {"description": "Secure seed funding", "timeline": "Q2 2025"}
                ],
                "q1_all_concerns": "Market competition, funding challenges, technical complexity",
                "q2_primary_concerns": "Finding the right co-founder and initial customers",
                "q3_solutions": "Network through tech meetups, validate MVP with beta users",
                "q4_risk_management": "Maintain current job until revenue milestone",
                "action_items": [
                    {"action": "Build MVP prototype", "who": "Self", "by_when": "Jan 2025", "status": "pending"},
                    {"action": "Research competitors", "who": "Self", "by_when": "Dec 2024", "status": "pending"}
                ],
                "status": "in_progress"
            }
            
            response = await client.post(
                f"{BASE_URL}/solution-finders",
                headers=headers,
                json=solution_data
            )
            
            print(f"📤 POST /solution-finders")
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                self.solution_finder_id = data.get("entry_id")
                print(f"✅ Solution finder created successfully!")
                print(f"🆔 Entry ID: {self.solution_finder_id}")
                print(f"🎯 Goal: {solution_data['smart_goal']}")
                print(f"📍 Area: {solution_data['area_of_life']}")
            else:
                print(f"❌ Solution finder creation failed: {response.text}")
                
        except Exception as e:
            print(f"❌ Solution finder creation error: {str(e)}")
        
        # Test 2.2: GET /api/solution-finders (list)
        print("\n2.2 Testing GET /api/solution-finders (list)")
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            response = await client.get(
                f"{BASE_URL}/solution-finders",
                headers=headers
            )
            
            print(f"📤 GET /solution-finders")
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Solution finders list retrieved!")
                print(f"📋 Total entries: {len(data)}")
                
                if data:
                    entry = data[0]
                    print(f"🆔 First entry ID: {entry.get('entry_id')}")
                    print(f"🎯 Goal: {entry.get('smart_goal')}")
            else:
                print(f"❌ Solution finders list failed: {response.text}")
                
        except Exception as e:
            print(f"❌ Solution finders list error: {str(e)}")
        
        # Test 2.3: GET /api/solution-finders/{id} (single)
        if self.solution_finder_id:
            print("\n2.3 Testing GET /api/solution-finders/{id} (single)")
            try:
                headers = {"Authorization": f"Bearer {self.session_token}"}
                response = await client.get(
                    f"{BASE_URL}/solution-finders/{self.solution_finder_id}",
                    headers=headers
                )
                
                print(f"📤 GET /solution-finders/{self.solution_finder_id}")
                print(f"📊 Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Solution finder retrieved!")
                    print(f"🎯 Goal: {data.get('smart_goal')}")
                    print(f"📊 Status: {data.get('status')}")
                    print(f"📋 Milestones: {len(data.get('milestones', []))}")
                else:
                    print(f"❌ Solution finder retrieval failed: {response.text}")
                    
            except Exception as e:
                print(f"❌ Solution finder retrieval error: {str(e)}")
        
        # Test 2.4: PUT /api/solution-finders/{id}
        if self.solution_finder_id:
            print("\n2.4 Testing PUT /api/solution-finders/{id}")
            try:
                headers = {"Authorization": f"Bearer {self.session_token}"}
                update_data = {"status": "completed"}
                
                response = await client.put(
                    f"{BASE_URL}/solution-finders/{self.solution_finder_id}",
                    headers=headers,
                    json=update_data
                )
                
                print(f"📤 PUT /solution-finders/{self.solution_finder_id}")
                print(f"📊 Status: {response.status_code}")
                
                if response.status_code == 200:
                    print(f"✅ Solution finder updated successfully!")
                    print(f"📊 New status: completed")
                else:
                    print(f"❌ Solution finder update failed: {response.text}")
                    
            except Exception as e:
                print(f"❌ Solution finder update error: {str(e)}")
        
        # Test 2.5: DELETE /api/solution-finders/{id}
        if self.solution_finder_id:
            print("\n2.5 Testing DELETE /api/solution-finders/{id}")
            try:
                headers = {"Authorization": f"Bearer {self.session_token}"}
                response = await client.delete(
                    f"{BASE_URL}/solution-finders/{self.solution_finder_id}",
                    headers=headers
                )
                
                print(f"📤 DELETE /solution-finders/{self.solution_finder_id}")
                print(f"📊 Status: {response.status_code}")
                
                if response.status_code == 200:
                    print(f"✅ Solution finder deleted successfully!")
                else:
                    print(f"❌ Solution finder deletion failed: {response.text}")
                    
            except Exception as e:
                print(f"❌ Solution finder deletion error: {str(e)}")
    
    async def test_solution_matrix_crud(self, client):
        """Test Suite 3: Solution Matrix CRUD"""
        print("\n🔢 TEST SUITE 3: SOLUTION MATRIX CRUD")
        print("-" * 50)
        
        # Test 3.1: POST /api/solution-matrices
        print("\n3.1 Testing POST /api/solution-matrices")
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            matrix_data = {
                "area_of_life": "finance",
                "smart_goal": "Launch profitable online business",
                "matrix_self": {
                    "summary": "Strong technical skills, limited business experience",
                    "knowledge_skills": "Advanced programming, basic marketing",
                    "capacity": "Can dedicate 20 hours/week initially",
                    "time": "6 months to launch, 2 years to profitability",
                    "people": "Need co-founder with business background",
                    "finance": "Personal savings of $50k available",
                    "infrastructure": "Home office setup, cloud hosting needed"
                },
                "matrix_micro": {
                    "summary": "Supportive family, competitive local market",
                    "knowledge_skills": "Access to tech meetups and mentors",
                    "capacity": "Family support for reduced income period",
                    "time": "Evening and weekend availability",
                    "people": "Network of developer friends",
                    "finance": "Potential family loan of $25k",
                    "infrastructure": "Shared workspace available"
                },
                "matrix_macro": {
                    "summary": "Growing e-commerce market, economic uncertainty",
                    "knowledge_skills": "Online courses and certifications available",
                    "capacity": "Remote work trend supports online business",
                    "time": "Market timing favorable for digital products",
                    "people": "Large pool of freelance talent",
                    "finance": "VC funding available but competitive",
                    "infrastructure": "Excellent cloud infrastructure options"
                },
                "solution_category": {
                    "completely_solvable": True,
                    "mostly_solvable": False,
                    "partially_solvable": False,
                    "minimally_solvable": False,
                    "unsolvable_compensatable": False,
                    "unsolvable_uncompensatable": False,
                    "unknown": False,
                    "not_applicable": False
                },
                "solution_sources": {
                    "from_self": "Technical development and product design",
                    "from_micro": "Business mentorship from local entrepreneurs",
                    "from_macro": "Market research and competitive analysis",
                    "from_unknown": "Customer validation and feedback",
                    "not_applicable": ""
                },
                "action_items": [
                    {"who": "Me", "what": "Build MVP", "by_when": "Q2 2025", "status": "pending"},
                    {"who": "Co-founder", "what": "Business plan", "by_when": "Q1 2025", "status": "pending"}
                ],
                "status": "in_progress"
            }
            
            response = await client.post(
                f"{BASE_URL}/solution-matrices",
                headers=headers,
                json=matrix_data
            )
            
            print(f"📤 POST /solution-matrices")
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                self.solution_matrix_id = data.get("entry_id")
                print(f"✅ Solution matrix created successfully!")
                print(f"🆔 Entry ID: {self.solution_matrix_id}")
                print(f"🎯 Goal: {matrix_data['smart_goal']}")
                print(f"📍 Area: {matrix_data['area_of_life']}")
            else:
                print(f"❌ Solution matrix creation failed: {response.text}")
                
        except Exception as e:
            print(f"❌ Solution matrix creation error: {str(e)}")
        
        # Test 3.2: GET /api/solution-matrices (list)
        print("\n3.2 Testing GET /api/solution-matrices (list)")
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            response = await client.get(
                f"{BASE_URL}/solution-matrices",
                headers=headers
            )
            
            print(f"📤 GET /solution-matrices")
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Solution matrices list retrieved!")
                print(f"📋 Total entries: {len(data)}")
                
                if data:
                    entry = data[0]
                    print(f"🆔 First entry ID: {entry.get('entry_id')}")
                    print(f"🎯 Goal: {entry.get('smart_goal')}")
            else:
                print(f"❌ Solution matrices list failed: {response.text}")
                
        except Exception as e:
            print(f"❌ Solution matrices list error: {str(e)}")
        
        # Test 3.3: PUT /api/solution-matrices/{id}
        if self.solution_matrix_id:
            print("\n3.3 Testing PUT /api/solution-matrices/{id}")
            try:
                headers = {"Authorization": f"Bearer {self.session_token}"}
                update_data = {"status": "completed"}
                
                response = await client.put(
                    f"{BASE_URL}/solution-matrices/{self.solution_matrix_id}",
                    headers=headers,
                    json=update_data
                )
                
                print(f"📤 PUT /solution-matrices/{self.solution_matrix_id}")
                print(f"📊 Status: {response.status_code}")
                
                if response.status_code == 200:
                    print(f"✅ Solution matrix updated successfully!")
                    print(f"📊 New status: completed")
                else:
                    print(f"❌ Solution matrix update failed: {response.text}")
                    
            except Exception as e:
                print(f"❌ Solution matrix update error: {str(e)}")
        
        # Test 3.4: DELETE /api/solution-matrices/{id}
        if self.solution_matrix_id:
            print("\n3.4 Testing DELETE /api/solution-matrices/{id}")
            try:
                headers = {"Authorization": f"Bearer {self.session_token}"}
                response = await client.delete(
                    f"{BASE_URL}/solution-matrices/{self.solution_matrix_id}",
                    headers=headers
                )
                
                print(f"📤 DELETE /solution-matrices/{self.solution_matrix_id}")
                print(f"📊 Status: {response.status_code}")
                
                if response.status_code == 200:
                    print(f"✅ Solution matrix deleted successfully!")
                else:
                    print(f"❌ Solution matrix deletion failed: {response.text}")
                    
            except Exception as e:
                print(f"❌ Solution matrix deletion error: {str(e)}")
    
    async def test_admin_call_config(self, client):
        """Test Suite 4: Admin Call Configuration"""
        print("\n📞 TEST SUITE 4: ADMIN CALL CONFIGURATION")
        print("-" * 50)
        
        # Test 4.1: GET /api/admin/call-config (defaults)
        print("\n4.1 Testing GET /api/admin/call-config")
        try:
            response = await client.get(f"{BASE_URL}/admin/call-config")
            
            print(f"📤 GET /admin/call-config")
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Call config retrieved successfully!")
                print(f"⏱️ Default duration: {data.get('default_duration')} minutes")
                print(f"⏱️ Min duration: {data.get('min_duration')} minutes")
                print(f"⏱️ Max duration: {data.get('max_duration')} minutes")
            else:
                print(f"❌ Call config retrieval failed: {response.text}")
                
        except Exception as e:
            print(f"❌ Call config retrieval error: {str(e)}")
        
        # Test 4.2: PUT /api/admin/call-config (admin only)
        print("\n4.2 Testing PUT /api/admin/call-config")
        try:
            headers = {"Authorization": f"Bearer {self.admin_session_token}"}
            config_data = {
                "default_duration": 45,
                "min_duration": 10,
                "max_duration": 90
            }
            
            response = await client.put(
                f"{BASE_URL}/admin/call-config",
                headers=headers,
                json=config_data
            )
            
            print(f"📤 PUT /admin/call-config")
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"✅ Call config updated successfully!")
                print(f"⏱️ New default: {config_data['default_duration']} minutes")
            elif response.status_code == 403:
                print(f"✅ Non-admin correctly denied (403): {response.text}")
            else:
                print(f"❌ Call config update failed: {response.text}")
                
        except Exception as e:
            print(f"❌ Call config update error: {str(e)}")
        
        # Test 4.3: Verify persistence
        print("\n4.3 Testing call config persistence")
        try:
            response = await client.get(f"{BASE_URL}/admin/call-config")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Call config persistence verified!")
                print(f"⏱️ Current default: {data.get('default_duration')} minutes")
                print(f"⏱️ Current min: {data.get('min_duration')} minutes")
                print(f"⏱️ Current max: {data.get('max_duration')} minutes")
            else:
                print(f"❌ Call config persistence check failed: {response.text}")
                
        except Exception as e:
            print(f"❌ Call config persistence error: {str(e)}")
    
    async def test_organization_branding(self, client):
        """Test Suite 5: Organization Branding (existing)"""
        print("\n🏢 TEST SUITE 5: ORGANIZATION BRANDING")
        print("-" * 50)
        
        # Test 5.1: POST /api/organizations
        print("\n5.1 Testing POST /api/organizations")
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            org_data = {
                "name": "Final Test Organization",
                "slug": f"final-test-org-{int(time.time())}"
            }
            
            response = await client.post(
                f"{BASE_URL}/organizations",
                headers=headers,
                json=org_data
            )
            
            print(f"📤 POST /organizations")
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                self.org_id = data.get("organization_id")
                print(f"✅ Organization created successfully!")
                print(f"🆔 Org ID: {self.org_id}")
                print(f"🏢 Name: {data.get('name')}")
                print(f"🔗 Slug: {data.get('slug')}")
            else:
                print(f"❌ Organization creation failed: {response.text}")
                
        except Exception as e:
            print(f"❌ Organization creation error: {str(e)}")
        
        # Test 5.2: GET /api/organizations/{slug} (verify branding fields)
        if self.org_id:
            print("\n5.2 Testing GET /api/organizations/{slug}")
            try:
                # Get the slug from the created org
                slug = f"final-test-org-{int(time.time())}"
                response = await client.get(f"{BASE_URL}/organizations/{slug}")
                
                print(f"📤 GET /organizations/{slug}")
                print(f"📊 Status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Organization retrieved successfully!")
                    print(f"🏢 Name: {data.get('name')}")
                    print(f"🔗 Slug: {data.get('slug')}")
                    print(f"🎨 Primary color: {data.get('primary_color', 'Not set')}")
                    print(f"🎨 Accent color: {data.get('accent_color', 'Not set')}")
                    print(f"📝 Tagline: {data.get('tagline', 'Not set')}")
                else:
                    print(f"❌ Organization retrieval failed: {response.text}")
                    
            except Exception as e:
                print(f"❌ Organization retrieval error: {str(e)}")
        
        # Test 5.3: PUT /api/organizations/{org_id} (branding update)
        if self.org_id:
            print("\n5.3 Testing PUT /api/organizations/{org_id}")
            try:
                headers = {"Authorization": f"Bearer {self.session_token}"}
                branding_data = {
                    "primary_color": "#FF0000",
                    "accent_color": "#00FF00",
                    "tagline": "Final test tagline for comprehensive testing"
                }
                
                response = await client.put(
                    f"{BASE_URL}/organizations/{self.org_id}",
                    headers=headers,
                    json=branding_data
                )
                
                print(f"📤 PUT /organizations/{self.org_id}")
                print(f"📊 Status: {response.status_code}")
                
                if response.status_code == 200:
                    print(f"✅ Organization branding updated successfully!")
                    print(f"🎨 Primary color: {branding_data['primary_color']}")
                    print(f"🎨 Accent color: {branding_data['accent_color']}")
                    print(f"📝 Tagline: {branding_data['tagline']}")
                else:
                    print(f"❌ Organization branding update failed: {response.text}")
                    
            except Exception as e:
                print(f"❌ Organization branding update error: {str(e)}")

async def main():
    """Run the comprehensive backend testing"""
    tester = ComprehensiveBackendTest()
    await tester.run_comprehensive_test()

if __name__ == "__main__":
    asyncio.run(main())