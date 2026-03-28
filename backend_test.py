#!/usr/bin/env python3
"""
Consciousness Diary Backend API Testing
Tests all consciousness diary endpoints comprehensively as per review request.
"""

import requests
import json
import uuid
from datetime import datetime, timedelta
import sys

# Backend URL from frontend/.env
BACKEND_URL = "https://dezider-core.preview.emergentagent.com/api"

class ConsciousnessDiaryTester:
    def __init__(self):
        self.session = requests.Session()
        self.user_token = None
        self.user_email = "diary_test@test.com"
        self.user_password = "Test123!"
        self.test_entry_id = None
        self.test_project_id = None
        
    def log(self, message):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        
    def test_user_registration(self):
        """Step 1: Register a new test user"""
        self.log("🔐 Testing user registration...")
        
        # Add timestamp to make email unique
        timestamp = int(datetime.now().timestamp())
        self.user_email = f"diary_test_{timestamp}@test.com"
        
        payload = {
            "email": self.user_email,
            "password": self.user_password,
            "name": "Diary Test User"
        }
        
        response = self.session.post(f"{BACKEND_URL}/auth/register", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            self.user_token = data.get("session_token")
            self.session.headers.update({"Authorization": f"Bearer {self.user_token}"})
            self.log(f"✅ User registration successful: {self.user_email}")
            return True
        else:
            self.log(f"❌ User registration failed: {response.status_code} - {response.text}")
            return False
    
    def test_config_endpoint(self):
        """Step 2: Test GET /api/consciousness-diary/config"""
        self.log("📋 Testing consciousness diary config endpoint...")
        
        response = self.session.get(f"{BACKEND_URL}/consciousness-diary/config")
        
        if response.status_code == 200:
            data = response.json()
            awareness_levels = data.get("awareness_levels", [])
            metrics_schema = data.get("metrics_schema", [])
            
            if len(awareness_levels) == 6 and len(metrics_schema) == 8:
                self.log(f"✅ Config endpoint working: {len(awareness_levels)} awareness levels, {len(metrics_schema)} metrics")
                return True
            else:
                self.log(f"❌ Config endpoint data mismatch: {len(awareness_levels)} levels, {len(metrics_schema)} metrics")
                return False
        else:
            self.log(f"❌ Config endpoint failed: {response.status_code} - {response.text}")
            return False
    
    def test_create_diary_entry(self):
        """Step 3: Test POST /api/consciousness-diary/entries with ALL 8 metrics"""
        self.log("📝 Testing diary entry creation with all 8 metrics...")
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        payload = {
            "date": today,
            "anger": {
                "count": 3,
                "avg_duration_mins": 15,
                "avg_intensity": 6
            },
            "sadness": {
                "count": 2,
                "avg_duration_mins": 20,
                "avg_intensity": 4
            },
            "fear": {
                "count": 1,
                "avg_duration_mins": 10,
                "avg_intensity": 3
            },
            "emotional_outlets": {
                "time_impact_pct": 20,
                "money_impact_pct": 10,
                "health_impact_pct": 30,
                "relationships_impact_pct": 15
            },
            "ads": {
                "time_impact_pct": 25,
                "money_impact_pct": 15,
                "health_impact_pct": 10,
                "relationships_impact_pct": 20
            },
            "sit_still": {
                "achieved": True,
                "comfort_score": 7
            },
            "peacefulness": {
                "peaceful_hours": 6,
                "depth_score": 7
            },
            "solution_leadership": {
                "problems_with_solutions": 5,
                "problems_without_solutions": 2
            },
            "overall_reflection": "Today I managed my anger better than yesterday"
        }
        
        response = self.session.post(f"{BACKEND_URL}/consciousness-diary/entries", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            self.test_entry_id = data.get("entry_id")
            metrics = data.get("metrics", {})
            
            # Verify all 8 metrics are present
            expected_metrics = ["anger", "sadness", "fear", "emotional_outlets", "ads", "sit_still", "peacefulness", "solution_leadership"]
            present_metrics = [m for m in expected_metrics if m in metrics]
            
            if len(present_metrics) == 8:
                self.log(f"✅ Diary entry created successfully with all 8 metrics: {self.test_entry_id}")
                return True
            else:
                self.log(f"❌ Diary entry missing metrics: {set(expected_metrics) - set(present_metrics)}")
                return False
        else:
            self.log(f"❌ Diary entry creation failed: {response.status_code} - {response.text}")
            return False
    
    def test_get_todays_entry(self):
        """Step 4: Test GET /api/consciousness-diary/entries?date=<today>"""
        self.log("📖 Testing get today's diary entry...")
        
        today = datetime.now().strftime("%Y-%m-%d")
        response = self.session.get(f"{BACKEND_URL}/consciousness-diary/entries?date={today}")
        
        if response.status_code == 200:
            data = response.json()
            entry = data.get("entry")
            daily_context = data.get("daily_context")
            
            if entry and entry.get("entry_id") == self.test_entry_id:
                self.log("✅ Today's entry retrieved successfully with daily_context")
                return True
            else:
                self.log(f"❌ Today's entry not found or mismatched: {entry}")
                return False
        else:
            self.log(f"❌ Get today's entry failed: {response.status_code} - {response.text}")
            return False
    
    def test_update_entry(self):
        """Step 5: Test PUT /api/consciousness-diary/entries/{entry_id}"""
        self.log("✏️ Testing diary entry update...")
        
        if not self.test_entry_id:
            self.log("❌ No entry ID available for update test")
            return False
        
        payload = {
            "anger": {
                "count": 4,  # Modified from 3
                "avg_duration_mins": 20,  # Modified from 15
                "avg_intensity": 7  # Modified from 6
            },
            "overall_reflection": "Updated: Today I managed my anger better than yesterday, but had one more incident"
        }
        
        response = self.session.put(f"{BACKEND_URL}/consciousness-diary/entries/{self.test_entry_id}", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            updated_anger = data.get("metrics", {}).get("anger", {})
            
            if updated_anger.get("count") == 4 and updated_anger.get("avg_duration_mins") == 20:
                self.log("✅ Diary entry updated successfully")
                return True
            else:
                self.log(f"❌ Diary entry update verification failed: {updated_anger}")
                return False
        else:
            self.log(f"❌ Diary entry update failed: {response.status_code} - {response.text}")
            return False
    
    def test_create_second_entry(self):
        """Step 6: Test creating a second entry for yesterday"""
        self.log("📝 Testing second diary entry creation (yesterday)...")
        
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        payload = {
            "date": yesterday,
            "anger": {
                "count": 1,
                "avg_duration_mins": 5,
                "avg_intensity": 3
            },
            "sadness": {
                "count": 0,
                "avg_duration_mins": 0,
                "avg_intensity": 0
            },
            "fear": {
                "count": 2,
                "avg_duration_mins": 15,
                "avg_intensity": 5
            },
            "emotional_outlets": {
                "time_impact_pct": 10,
                "money_impact_pct": 5,
                "health_impact_pct": 15,
                "relationships_impact_pct": 8
            },
            "ads": {
                "time_impact_pct": 30,
                "money_impact_pct": 20,
                "health_impact_pct": 5,
                "relationships_impact_pct": 25
            },
            "sit_still": {
                "achieved": False,
                "comfort_score": 4
            },
            "peacefulness": {
                "peaceful_hours": 4,
                "depth_score": 5
            },
            "solution_leadership": {
                "problems_with_solutions": 3,
                "problems_without_solutions": 4
            },
            "overall_reflection": "Yesterday was more challenging with fear and ADS impact"
        }
        
        response = self.session.post(f"{BACKEND_URL}/consciousness-diary/entries", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            self.log(f"✅ Second diary entry created for yesterday: {data.get('entry_id')}")
            return True
        else:
            self.log(f"❌ Second diary entry creation failed: {response.status_code} - {response.text}")
            return False
    
    def test_history_endpoint(self):
        """Step 7: Test GET /api/consciousness-diary/history?days=7"""
        self.log("📊 Testing diary history endpoint...")
        
        response = self.session.get(f"{BACKEND_URL}/consciousness-diary/history?days=7")
        
        if response.status_code == 200:
            data = response.json()
            entries = data.get("entries", [])
            total = data.get("total", 0)
            
            if total >= 2:  # Should have at least our 2 test entries
                self.log(f"✅ History endpoint working: {total} entries found")
                return True
            else:
                self.log(f"❌ History endpoint insufficient entries: {total}")
                return False
        else:
            self.log(f"❌ History endpoint failed: {response.status_code} - {response.text}")
            return False
    
    def test_self_awareness_get(self):
        """Step 8a: Test GET /api/consciousness-diary/self-awareness"""
        self.log("🧠 Testing get self-awareness levels...")
        
        response = self.session.get(f"{BACKEND_URL}/consciousness-diary/self-awareness")
        
        if response.status_code == 200:
            data = response.json()
            levels = data.get("levels", {})
            overall_level = data.get("overall_level", 0)
            
            # Should have 6 levels with default scores
            if len(levels) == 6 and overall_level > 0:
                self.log(f"✅ Self-awareness levels retrieved: overall={overall_level}")
                return True
            else:
                self.log(f"❌ Self-awareness levels incomplete: {len(levels)} levels, overall={overall_level}")
                return False
        else:
            self.log(f"❌ Get self-awareness failed: {response.status_code} - {response.text}")
            return False
    
    def test_self_awareness_update(self):
        """Step 8b: Test PUT /api/consciousness-diary/self-awareness"""
        self.log("🧠 Testing update self-awareness levels...")
        
        payload = {
            "levels": {
                "1": {"score": 8, "notes": "Strong thought awareness"},
                "2": {"score": 6},
                "3": {"score": 7},
                "5": {"score": 5},
                "6": {"score": 4}
            }
        }
        
        response = self.session.put(f"{BACKEND_URL}/consciousness-diary/self-awareness", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            levels = data.get("levels", {})
            overall_level = data.get("overall_level", 0)
            
            # Verify Level 4 is auto-calculated and not manually settable
            level_4 = levels.get("4", {})
            if (level_4.get("source") == "auto_calculated" and 
                levels.get("1", {}).get("score") == 8 and
                overall_level > 0):
                self.log(f"✅ Self-awareness updated: Level 4 auto-calculated, overall={overall_level}")
                return True
            else:
                self.log(f"❌ Self-awareness update verification failed: Level 4={level_4}")
                return False
        else:
            self.log(f"❌ Update self-awareness failed: {response.status_code} - {response.text}")
            return False
    
    def test_emotional_wellness(self):
        """Step 9: Test GET /api/consciousness-diary/emotional-wellness?days=7"""
        self.log("💚 Testing emotional wellness endpoint...")
        
        response = self.session.get(f"{BACKEND_URL}/consciousness-diary/emotional-wellness?days=7")
        
        if response.status_code == 200:
            data = response.json()
            wellness_score = data.get("wellness_score", 0)
            metrics_summary = data.get("metrics_summary", {})
            trend_direction = data.get("trend_direction", "")
            
            # Should have all 8 metric aggregations
            expected_metrics = ["anger", "sadness", "fear", "emotional_outlets", "ads", "sit_still", "peacefulness", "solution_leadership"]
            present_metrics = [m for m in expected_metrics if m in metrics_summary]
            
            if len(present_metrics) == 8 and wellness_score > 0:
                self.log(f"✅ Emotional wellness working: score={wellness_score}, trend={trend_direction}")
                return True
            else:
                self.log(f"❌ Emotional wellness incomplete: {len(present_metrics)}/8 metrics, score={wellness_score}")
                return False
        else:
            self.log(f"❌ Emotional wellness failed: {response.status_code} - {response.text}")
            return False
    
    def test_daily_context(self):
        """Step 10: Test GET /api/consciousness-diary/daily-context?date=<today>"""
        self.log("📅 Testing daily context endpoint...")
        
        today = datetime.now().strftime("%Y-%m-%d")
        response = self.session.get(f"{BACKEND_URL}/consciousness-diary/daily-context?date={today}")
        
        if response.status_code == 200:
            data = response.json()
            tasks = data.get("tasks", [])
            routines = data.get("routines", [])
            unplanned = data.get("unplanned", [])
            
            # Should return data structure even if empty
            if isinstance(tasks, list) and isinstance(routines, list) and isinstance(unplanned, list):
                self.log(f"✅ Daily context working: {len(tasks)} tasks, {len(routines)} routines, {len(unplanned)} unplanned")
                return True
            else:
                self.log(f"❌ Daily context structure invalid: tasks={type(tasks)}, routines={type(routines)}")
                return False
        else:
            self.log(f"❌ Daily context failed: {response.status_code} - {response.text}")
            return False
    
    def test_delete_entry(self):
        """Step 11: Test DELETE /api/consciousness-diary/entries/{entry_id}"""
        self.log("🗑️ Testing diary entry deletion...")
        
        if not self.test_entry_id:
            self.log("❌ No entry ID available for deletion test")
            return False
        
        response = self.session.delete(f"{BACKEND_URL}/consciousness-diary/entries/{self.test_entry_id}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("message") == "Entry deleted":
                self.log("✅ Diary entry deleted successfully")
                return True
            else:
                self.log(f"❌ Delete response unexpected: {data}")
                return False
        else:
            self.log(f"❌ Diary entry deletion failed: {response.status_code} - {response.text}")
            return False
    
    def test_gem_flight_project_creation(self):
        """Helper: Create a GEM flight project for iGIS testing"""
        self.log("🚀 Creating GEM flight project for iGIS testing...")
        
        payload = {
            "title": "Test Flight Project",
            "vision": "Achieve consciousness mastery",
            "goal": "Complete self-awareness journey",
            "life_area": "spirituality_religion"
        }
        
        response = self.session.post(f"{BACKEND_URL}/gem-flight/projects", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            self.test_project_id = data.get("project_id")
            self.log(f"✅ GEM flight project created: {self.test_project_id}")
            return True
        else:
            self.log(f"❌ GEM flight project creation failed: {response.status_code} - {response.text}")
            return False
    
    def test_gem_flight_igis_emotional_wellness(self):
        """Step 12a: Test GET /api/gem-flight/projects/{pid}/igis/emotional-wellness"""
        self.log("💚 Testing GEM Flight iGIS emotional wellness...")
        
        if not self.test_project_id:
            self.log("❌ No project ID available for iGIS testing")
            return False
        
        response = self.session.get(f"{BACKEND_URL}/gem-flight/projects/{self.test_project_id}/igis/emotional-wellness")
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            module = data.get("module")
            
            if module == "emotional_wellness" and status in ["ok", "no_data"]:
                self.log(f"✅ GEM Flight iGIS emotional wellness working: status={status}")
                return True
            else:
                self.log(f"❌ GEM Flight iGIS emotional wellness unexpected response: {data}")
                return False
        else:
            self.log(f"❌ GEM Flight iGIS emotional wellness failed: {response.status_code} - {response.text}")
            return False
    
    def test_gem_flight_igis_self_awareness(self):
        """Step 12b: Test GET /api/gem-flight/projects/{pid}/igis/self-awareness"""
        self.log("🧠 Testing GEM Flight iGIS self-awareness...")
        
        if not self.test_project_id:
            self.log("❌ No project ID available for iGIS testing")
            return False
        
        response = self.session.get(f"{BACKEND_URL}/gem-flight/projects/{self.test_project_id}/igis/self-awareness")
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            module = data.get("module")
            
            if module == "self_awareness" and status in ["ok", "no_data"]:
                self.log(f"✅ GEM Flight iGIS self-awareness working: status={status}")
                return True
            else:
                self.log(f"❌ GEM Flight iGIS self-awareness unexpected response: {data}")
                return False
        else:
            self.log(f"❌ GEM Flight iGIS self-awareness failed: {response.status_code} - {response.text}")
            return False
    
    def run_all_tests(self):
        """Run all consciousness diary tests in sequence"""
        self.log("🎯 Starting Consciousness Diary Backend API Testing")
        self.log(f"Backend URL: {BACKEND_URL}")
        
        tests = [
            ("User Registration", self.test_user_registration),
            ("Config Endpoint", self.test_config_endpoint),
            ("Create Diary Entry", self.test_create_diary_entry),
            ("Get Today's Entry", self.test_get_todays_entry),
            ("Update Entry", self.test_update_entry),
            ("Create Second Entry", self.test_create_second_entry),
            ("History Endpoint", self.test_history_endpoint),
            ("Get Self-Awareness", self.test_self_awareness_get),
            ("Update Self-Awareness", self.test_self_awareness_update),
            ("Emotional Wellness", self.test_emotional_wellness),
            ("Daily Context", self.test_daily_context),
            ("Delete Entry", self.test_delete_entry),
            ("Create GEM Flight Project", self.test_gem_flight_project_creation),
            ("GEM Flight iGIS Emotional Wellness", self.test_gem_flight_igis_emotional_wellness),
            ("GEM Flight iGIS Self-Awareness", self.test_gem_flight_igis_self_awareness),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            self.log(f"\n--- {test_name} ---")
            try:
                if test_func():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                self.log(f"❌ {test_name} exception: {str(e)}")
                failed += 1
        
        self.log(f"\n🎯 CONSCIOUSNESS DIARY TESTING COMPLETE")
        self.log(f"✅ Passed: {passed}")
        self.log(f"❌ Failed: {failed}")
        self.log(f"📊 Success Rate: {(passed/(passed+failed)*100):.1f}%")
        
        return passed, failed

if __name__ == "__main__":
    tester = ConsciousnessDiaryTester()
    passed, failed = tester.run_all_tests()
    
    # Exit with error code if any tests failed
    sys.exit(0 if failed == 0 else 1)