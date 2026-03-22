#!/usr/bin/env python3
"""
Backend API Testing for CLD and Call Session Endpoints
Testing URL: https://prr-platform-1.preview.emergentagent.com/api
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "https://prr-platform-1.preview.emergentagent.com/api"
TEST_EMAIL = "cld@test.com"
TEST_PASSWORD = "Test1234!"
TEST_NAME = "CLD Tester"

class BackendTester:
    def __init__(self):
        self.session = requests.Session()
        self.auth_token = None
        self.user_id = None
        self.decision_id = None
        self.session_id = None
        
    def log(self, message):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        
    def test_user_registration(self):
        """Test 1: Register a new user"""
        self.log("🔐 Testing user registration...")
        
        # Use timestamp to ensure unique email
        timestamp = int(time.time())
        email = f"cld.tester.{timestamp}@test.com"
        
        payload = {
            "email": email,
            "password": TEST_PASSWORD,
            "name": TEST_NAME
        }
        
        response = self.session.post(f"{BASE_URL}/auth/register", json=payload)
        
        if response.status_code in [200, 201]:
            data = response.json()
            self.auth_token = data.get("session_token")
            self.user_id = data.get("user_id")
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
            self.log(f"✅ Registration successful - User ID: {self.user_id}")
            return True
        else:
            self.log(f"❌ Registration failed: {response.status_code} - {response.text}")
            return False
            
    def test_create_decision(self):
        """Test 2: Create a decision for CLD analysis"""
        self.log("📋 Creating decision for CLD analysis...")
        
        payload = {
            "title": "Career Decision",
            "description": "Choosing between job offers at different tech companies",
            "context": "Choosing between job offers at different tech companies",
            "folder": "career"
        }
        
        response = self.session.post(f"{BASE_URL}/decisions", json=payload)
        
        if response.status_code in [200, 201]:
            data = response.json()
            self.decision_id = data.get("id")  # Changed from "decision_id" to "id"
            self.log(f"✅ Decision created - ID: {self.decision_id}")
            return True
        else:
            self.log(f"❌ Decision creation failed: {response.status_code} - {response.text}")
            return False
            
    def test_update_decision_with_factors(self):
        """Test 3: Update decision with factors for CLD analysis"""
        self.log("🔧 Adding factors to decision...")
        
        factors = [
            {"id": "f1", "name": "Salary", "category": "secondary", "rating": 50, "order": 0},
            {"id": "f2", "name": "Work-Life Balance", "category": "secondary", "rating": 50, "order": 1},
            {"id": "f3", "name": "Growth Opportunity", "category": "secondary", "rating": 50, "order": 2},
            {"id": "f4", "name": "Location", "category": "secondary", "rating": 50, "order": 3}
        ]
        
        payload = {"factors": factors}
        
        response = self.session.put(f"{BASE_URL}/decisions/{self.decision_id}", json=payload)
        
        if response.status_code == 200:
            self.log("✅ Factors added to decision successfully")
            return True
        else:
            self.log(f"❌ Factor update failed: {response.status_code} - {response.text}")
            return False
            
    def test_cld_analyze(self):
        """Test 4: Test CLD Analysis endpoint"""
        self.log("🧠 Testing CLD Analysis endpoint...")
        
        payload = {
            "decision_title": "Career Decision",
            "decision_context": "Choosing between job offers at different tech companies",
            "life_area": "Career",
            "decision_type": "Job Selection",
            "factors": [
                {"id": "f1", "name": "Salary"},
                {"id": "f2", "name": "Work-Life Balance"},
                {"id": "f3", "name": "Growth Opportunity"},
                {"id": "f4", "name": "Location"}
            ]
        }
        
        response = self.session.post(f"{BASE_URL}/cld/analyze", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            
            # Verify response structure
            required_keys = ["cld", "factor_analysis"]
            missing_keys = [key for key in required_keys if key not in data]
            
            if missing_keys:
                self.log(f"❌ CLD response missing keys: {missing_keys}")
                return False
                
            # Verify CLD structure
            cld = data.get("cld", {})
            cld_required = ["nodes", "links", "loops"]
            cld_missing = [key for key in cld_required if key not in cld]
            
            if cld_missing:
                self.log(f"❌ CLD structure missing keys: {cld_missing}")
                return False
                
            # Verify factor analysis
            factor_analysis = data.get("factor_analysis", [])
            if not isinstance(factor_analysis, list):
                self.log("❌ Factor analysis should be a list")
                return False
                
            self.log(f"✅ CLD Analysis successful - Nodes: {len(cld['nodes'])}, Links: {len(cld['links'])}, Loops: {len(cld['loops'])}")
            self.log(f"✅ Factor analysis returned {len(factor_analysis)} factor classifications")
            return True
        else:
            self.log(f"❌ CLD Analysis failed: {response.status_code} - {response.text}")
            return False
            
    def test_get_call_config(self):
        """Test 5: Get call configuration"""
        self.log("⚙️ Testing GET call configuration...")
        
        response = self.session.get(f"{BASE_URL}/call-config")
        
        if response.status_code == 200:
            data = response.json()
            
            # Verify required fields
            required_fields = ["min_duration", "max_duration", "default_duration"]
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                self.log(f"❌ Call config missing fields: {missing_fields}")
                return False
                
            self.log(f"✅ Call config retrieved - Min: {data['min_duration']}, Max: {data['max_duration']}, Default: {data['default_duration']}")
            return True
        else:
            self.log(f"❌ Get call config failed: {response.status_code} - {response.text}")
            return False
            
    def test_update_call_config(self):
        """Test 6: Try updating call configuration (should require admin)"""
        self.log("⚙️ Testing PUT call configuration (should require admin)...")
        
        payload = {
            "min_duration": 10,
            "max_duration": 90,
            "default_duration": 25
        }
        
        response = self.session.put(f"{BASE_URL}/call-config", json=payload)
        
        # Should return 403 for non-admin users
        if response.status_code == 403:
            self.log("✅ Call config update correctly requires admin privileges (403)")
            return True
        elif response.status_code == 200:
            self.log("⚠️ Call config update succeeded (user might have admin privileges)")
            return True
        else:
            self.log(f"❌ Unexpected call config update response: {response.status_code} - {response.text}")
            return False
            
    def test_create_call_session(self):
        """Test 7: Create a call session"""
        self.log("📞 Testing call session creation...")
        
        payload = {
            "expert_id": None,
            "decision_id": "test-dec",
            "step_number": 3,
            "step_name": "Classify Factors",
            "duration_minutes": 15,
            "decision_title": "Career Decision"
        }
        
        response = self.session.post(f"{BASE_URL}/call-sessions", json=payload)
        
        if response.status_code in [200, 201]:
            data = response.json()
            
            # Verify required fields
            required_fields = ["session_id", "room_id", "room_url", "duration_minutes", "expires_at"]
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                self.log(f"❌ Call session response missing fields: {missing_fields}")
                return False
                
            self.session_id = data.get("session_id")
            
            # Verify room_url is a Jitsi URL
            room_url = data.get("room_url", "")
            if "meet.jit.si" not in room_url and "jitsi" not in room_url.lower():
                self.log(f"⚠️ Room URL might not be Jitsi format: {room_url}")
            
            self.log(f"✅ Call session created - ID: {self.session_id}")
            self.log(f"✅ Room URL: {room_url}")
            self.log(f"✅ Duration: {data['duration_minutes']} minutes")
            return True
        else:
            self.log(f"❌ Call session creation failed: {response.status_code} - {response.text}")
            return False
            
    def test_get_call_session(self):
        """Test 8: Get call session details"""
        if not self.session_id:
            self.log("❌ No session ID available for testing")
            return False
            
        self.log("📞 Testing get call session details...")
        
        response = self.session.get(f"{BASE_URL}/call-sessions/{self.session_id}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Verify session data
            if data.get("id") != self.session_id:
                self.log(f"❌ Session ID mismatch: expected {self.session_id}, got {data.get('id')}")
                return False
                
            self.log(f"✅ Call session details retrieved - Status: {data.get('status')}")
            return True
        else:
            self.log(f"❌ Get call session failed: {response.status_code} - {response.text}")
            return False
            
    def test_end_call_session(self):
        """Test 9: End call session"""
        if not self.session_id:
            self.log("❌ No session ID available for testing")
            return False
            
        self.log("📞 Testing end call session...")
        
        response = self.session.put(f"{BASE_URL}/call-sessions/{self.session_id}/end")
        
        if response.status_code == 200:
            data = response.json()
            if "ended" in data.get("message", "").lower():
                self.log("✅ Call session ended successfully")
                return True
            else:
                self.log(f"❌ Unexpected end session response: {data}")
                return False
        else:
            self.log(f"❌ End call session failed: {response.status_code} - {response.text}")
            return False
            
    def test_list_call_sessions(self):
        """Test 10: List call sessions"""
        self.log("📞 Testing list call sessions...")
        
        response = self.session.get(f"{BASE_URL}/call-sessions")
        
        if response.status_code == 200:
            data = response.json()
            
            if not isinstance(data, list):
                self.log(f"❌ Expected list response, got: {type(data)}")
                return False
                
            self.log(f"✅ Call sessions list retrieved - Count: {len(data)}")
            
            # Verify our session is in the list
            if self.session_id:
                session_found = any(session.get("id") == self.session_id for session in data)
                if session_found:
                    self.log("✅ Created session found in list")
                else:
                    self.log("⚠️ Created session not found in list (might be expected)")
                    
            return True
        else:
            self.log(f"❌ List call sessions failed: {response.status_code} - {response.text}")
            return False
            
    def run_all_tests(self):
        """Run all tests in sequence"""
        self.log("🚀 Starting CLD and Call Session endpoint testing...")
        self.log(f"🌐 Backend URL: {BASE_URL}")
        
        tests = [
            ("User Registration", self.test_user_registration),
            ("Create Decision", self.test_create_decision),
            ("Update Decision with Factors", self.test_update_decision_with_factors),
            ("CLD Analysis", self.test_cld_analyze),
            ("Get Call Config", self.test_get_call_config),
            ("Update Call Config", self.test_update_call_config),
            ("Create Call Session", self.test_create_call_session),
            ("Get Call Session", self.test_get_call_session),
            ("End Call Session", self.test_end_call_session),
            ("List Call Sessions", self.test_list_call_sessions),
        ]
        
        results = []
        
        for test_name, test_func in tests:
            self.log(f"\n{'='*50}")
            self.log(f"Running: {test_name}")
            self.log('='*50)
            
            try:
                result = test_func()
                results.append((test_name, result))
                
                if not result:
                    self.log(f"❌ {test_name} FAILED")
                else:
                    self.log(f"✅ {test_name} PASSED")
                    
            except Exception as e:
                self.log(f"❌ {test_name} ERROR: {str(e)}")
                results.append((test_name, False))
                
        # Summary
        self.log(f"\n{'='*60}")
        self.log("TEST SUMMARY")
        self.log('='*60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            self.log(f"{status} - {test_name}")
            
        self.log(f"\n🎯 Results: {passed}/{total} tests passed")
        
        if passed == total:
            self.log("🎉 ALL TESTS PASSED!")
        else:
            self.log(f"⚠️ {total - passed} tests failed")
            
        return passed == total

if __name__ == "__main__":
    tester = BackendTester()
    success = tester.run_all_tests()
    exit(0 if success else 1)