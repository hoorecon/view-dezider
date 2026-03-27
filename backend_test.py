#!/usr/bin/env python3
"""
Comprehensive Backend Testing for GEM Flight Model
Tests all endpoints as specified in the review request
"""

import requests
import json
import time
from datetime import datetime, timedelta

# Backend URL from frontend/.env
BACKEND_URL = "https://dezider-core.preview.emergentagent.com/api"

class GEMFlightTester:
    def __init__(self):
        self.session = requests.Session()
        self.user_token = None
        self.user_data = None
        self.project_id = None
        self.task_id = None
        self.routine_id = None
        
    def log(self, message):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        
    def test_user_registration(self):
        """Step 1: Register a new test user"""
        self.log("🔐 Testing user registration...")
        
        timestamp = int(time.time())
        email = f"gemflight_test@test.com"
        password = "Test123!"
        
        response = self.session.post(f"{BACKEND_URL}/auth/register", json={
            "email": email,
            "password": password,
            "name": "GEM Flight Test User"
        })
        
        if response.status_code == 200:
            data = response.json()
            self.user_token = data.get("session_token")
            self.user_data = data
            self.session.headers.update({"Authorization": f"Bearer {self.user_token}"})
            self.log(f"✅ User registered successfully: {email}")
            return True
        else:
            self.log(f"❌ Registration failed: {response.status_code} - {response.text}")
            return False
            
    def test_config_endpoint(self):
        """Step 2: Test config endpoint"""
        self.log("⚙️ Testing config endpoint...")
        
        response = self.session.get(f"{BACKEND_URL}/gem-flight/config")
        
        if response.status_code == 200:
            data = response.json()
            secrets = data.get("secrets", [])
            seven_steps = data.get("seven_steps", [])
            gears = data.get("gears", [])
            
            if len(secrets) == 12 and len(seven_steps) == 7 and len(gears) == 4:
                self.log(f"✅ Config endpoint working: {len(secrets)} secrets, {len(seven_steps)} steps, {len(gears)} gears")
                return True
            else:
                self.log(f"❌ Config data incomplete: {len(secrets)} secrets, {len(seven_steps)} steps, {len(gears)} gears")
                return False
        else:
            self.log(f"❌ Config endpoint failed: {response.status_code} - {response.text}")
            return False
            
    def test_create_flight_project(self):
        """Step 3: Create flight project"""
        self.log("🚀 Testing flight project creation...")
        
        project_data = {
            "title": "Career Transition 2026",
            "vision": "Become a senior tech lead at a top company",
            "goal": "Get promoted to senior tech lead within 12 months",
            "point_a": "Mid-level software engineer",
            "point_b": "Senior tech lead at a FAANG company",
            "life_area": "career",
            "specific": "Get promoted to senior tech lead position",
            "measurable": "Achieve promotion within 12 months with 25% salary increase",
            "achievable": "Build leadership skills and technical expertise",
            "realistic": "Based on current performance and market demand",
            "time_bound": (datetime.now() + timedelta(days=365)).isoformat()
        }
        
        response = self.session.post(f"{BACKEND_URL}/gem-flight/projects", json=project_data)
        
        if response.status_code == 200:
            data = response.json()
            self.project_id = data.get("project_id")
            self.log(f"✅ Flight project created: {self.project_id}")
            self.log(f"   Title: {data.get('title')}")
            self.log(f"   Current Step: {data.get('current_step')}")
            self.log(f"   Progress: {data.get('progress_percent')}%")
            return True
        else:
            self.log(f"❌ Project creation failed: {response.status_code} - {response.text}")
            return False
            
    def test_list_projects(self):
        """Step 4: List projects"""
        self.log("📋 Testing project listing...")
        
        response = self.session.get(f"{BACKEND_URL}/gem-flight/projects")
        
        if response.status_code == 200:
            data = response.json()
            projects = data.get("projects", [])
            
            if len(projects) > 0 and any(p.get("project_id") == self.project_id for p in projects):
                self.log(f"✅ Project listing working: Found {len(projects)} projects including our test project")
                return True
            else:
                self.log(f"❌ Project not found in list: {len(projects)} projects")
                return False
        else:
            self.log(f"❌ Project listing failed: {response.status_code} - {response.text}")
            return False
            
    def test_get_single_project(self):
        """Step 5: Get single project"""
        self.log("🔍 Testing single project retrieval...")
        
        response = self.session.get(f"{BACKEND_URL}/gem-flight/projects/{self.project_id}")
        
        if response.status_code == 200:
            data = response.json()
            self.log(f"✅ Single project retrieval working")
            self.log(f"   Title: {data.get('title')}")
            self.log(f"   Vision: {data.get('vision')}")
            self.log(f"   Current Step: {data.get('current_step')}")
            return True
        else:
            self.log(f"❌ Single project retrieval failed: {response.status_code} - {response.text}")
            return False
            
    def test_update_project(self):
        """Step 6: Update project"""
        self.log("✏️ Testing project update...")
        
        update_data = {
            "vision": "Become a senior tech lead at a top company with team leadership responsibilities",
            "goal": "Get promoted to senior tech lead within 12 months and lead a team of 5+ engineers"
        }
        
        response = self.session.put(f"{BACKEND_URL}/gem-flight/projects/{self.project_id}", json=update_data)
        
        if response.status_code == 200:
            data = response.json()
            self.log(f"✅ Project update working")
            self.log(f"   Updated Vision: {data.get('vision')}")
            self.log(f"   Updated Goal: {data.get('goal')}")
            return True
        else:
            self.log(f"❌ Project update failed: {response.status_code} - {response.text}")
            return False
            
    def test_step_management(self):
        """Step 7: Test step management"""
        self.log("📈 Testing step management...")
        
        # Start step 1
        response = self.session.put(f"{BACKEND_URL}/gem-flight/projects/{self.project_id}/step/1", json={
            "status": "in_progress",
            "notes": "Defining SMART goals for career transition"
        })
        
        if response.status_code != 200:
            self.log(f"❌ Step 1 in_progress failed: {response.status_code} - {response.text}")
            return False
            
        # Complete step 1
        response = self.session.put(f"{BACKEND_URL}/gem-flight/projects/{self.project_id}/step/1", json={
            "status": "completed"
        })
        
        if response.status_code == 200:
            data = response.json()
            current_step = data.get("current_step")
            progress = data.get("progress_percent")
            self.log(f"✅ Step 1 completed - Current Step: {current_step}, Progress: {progress}%")
        else:
            self.log(f"❌ Step 1 completion failed: {response.status_code} - {response.text}")
            return False
            
        # Complete steps 2-5 to reach step 6
        for step in range(2, 6):
            response = self.session.put(f"{BACKEND_URL}/gem-flight/projects/{self.project_id}/step/{step}", json={
                "status": "completed",
                "notes": f"Completed step {step}"
            })
            
            if response.status_code == 200:
                data = response.json()
                self.log(f"✅ Step {step} completed - Progress: {data.get('progress_percent')}%")
            else:
                self.log(f"❌ Step {step} completion failed: {response.status_code} - {response.text}")
                return False
                
        return True
        
    def test_gear_management(self):
        """Step 8: Test gear management after reaching step 6"""
        self.log("⚙️ Testing gear management...")
        
        # Start step 6 (should auto-set gear to 1)
        response = self.session.put(f"{BACKEND_URL}/gem-flight/projects/{self.project_id}/step/6", json={
            "status": "in_progress"
        })
        
        if response.status_code == 200:
            data = response.json()
            self.log(f"✅ Step 6 started - should auto-set gear to 1")
        else:
            self.log(f"❌ Step 6 start failed: {response.status_code} - {response.text}")
            return False
            
        # Change to gear 2
        response = self.session.put(f"{BACKEND_URL}/gem-flight/projects/{self.project_id}/gear/2", json={})
        
        if response.status_code == 200:
            data = response.json()
            current_gear = data.get("current_gear")
            self.log(f"✅ Gear management working - Current Gear: {current_gear}")
            return True
        else:
            self.log(f"❌ Gear change failed: {response.status_code} - {response.text}")
            return False
            
    def test_flight_score(self):
        """Step 9: Test auto-compute flight scores"""
        self.log("🎯 Testing flight score computation...")
        
        response = self.session.get(f"{BACKEND_URL}/gem-flight/projects/{self.project_id}/flight-score")
        
        if response.status_code == 200:
            data = response.json()
            scores = data.get("scores", {})
            overall_health = data.get("overall_health")
            gis = data.get("gis", {})
            igis = data.get("igis", {})
            
            self.log(f"✅ Flight scores computed successfully")
            self.log(f"   Overall Health: {overall_health}")
            self.log(f"   Secrets Count: {len(scores)}")
            self.log(f"   GIS: {gis}")
            self.log(f"   iGIS: {igis}")
            return True
        else:
            self.log(f"❌ Flight score computation failed: {response.status_code} - {response.text}")
            return False
            
    def test_flight_dynamics(self):
        """Step 10: Test flight dynamics"""
        self.log("✈️ Testing flight dynamics...")
        
        response = self.session.get(f"{BACKEND_URL}/gem-flight/projects/{self.project_id}/flight-dynamics")
        
        if response.status_code == 200:
            data = response.json()
            
            required_fields = [
                "altitude", "speed", "turbulence", "fuel", "eta_days", 
                "crash_risk", "phase", "heading", "weather", 
                "tasks_summary", "routines_summary"
            ]
            
            missing_fields = [field for field in required_fields if field not in data]
            
            if not missing_fields:
                self.log(f"✅ Flight dynamics working")
                self.log(f"   Altitude: {data.get('altitude_label')}")
                self.log(f"   Speed: {data.get('speed_label')}")
                self.log(f"   Turbulence: {data.get('turbulence_label')}")
                self.log(f"   Fuel: {data.get('fuel_label')}")
                self.log(f"   ETA: {data.get('eta_days')} days")
                self.log(f"   Crash Risk: {data.get('crash_label')}")
                self.log(f"   Phase: {data.get('heading')}")
                self.log(f"   Weather: {data.get('weather_label')}")
                return True
            else:
                self.log(f"❌ Flight dynamics missing fields: {missing_fields}")
                return False
        else:
            self.log(f"❌ Flight dynamics failed: {response.status_code} - {response.text}")
            return False
            
    def test_flight_event_log(self):
        """Step 11: Test flight event log"""
        self.log("📊 Testing flight event log...")
        
        response = self.session.get(f"{BACKEND_URL}/gem-flight/projects/{self.project_id}/flight-log")
        
        if response.status_code == 200:
            data = response.json()
            events = data.get("events", [])
            
            self.log(f"✅ Flight event log working - {len(events)} events recorded")
            if events:
                latest_event = events[-1]
                self.log(f"   Latest Event: Altitude {latest_event.get('altitude')}ft, Speed {latest_event.get('speed')} knots")
            return True
        else:
            self.log(f"❌ Flight event log failed: {response.status_code} - {response.text}")
            return False
            
    def test_dashboard(self):
        """Step 12: Test dashboard endpoint"""
        self.log("📊 Testing dashboard endpoint...")
        
        response = self.session.get(f"{BACKEND_URL}/gem-flight/projects/{self.project_id}/dashboard")
        
        if response.status_code == 200:
            data = response.json()
            
            required_keys = ["project", "linked_tasks", "linked_routines", "linked_decisions", "config"]
            missing_keys = [key for key in required_keys if key not in data]
            
            if not missing_keys:
                project = data.get("project", {})
                config = data.get("config", {})
                
                self.log(f"✅ Dashboard endpoint working")
                self.log(f"   Project: {project.get('title')}")
                self.log(f"   Linked Tasks: {len(data.get('linked_tasks', []))}")
                self.log(f"   Linked Routines: {len(data.get('linked_routines', []))}")
                self.log(f"   Linked Decisions: {len(data.get('linked_decisions', []))}")
                self.log(f"   Config Secrets: {len(config.get('secrets', []))}")
                return True
            else:
                self.log(f"❌ Dashboard missing keys: {missing_keys}")
                return False
        else:
            self.log(f"❌ Dashboard failed: {response.status_code} - {response.text}")
            return False
            
    def test_link_modules(self):
        """Step 13: Test linking modules (tasks and routines)"""
        self.log("🔗 Testing module linking...")
        
        # First create a CTT task
        task_response = self.session.post(f"{BACKEND_URL}/ctt/tasks", json={
            "title": "Complete senior engineer certification",
            "priority": "high",
            "status": "open",
            "life_area": "career"
        })
        
        if task_response.status_code == 200:
            task_data = task_response.json()
            self.task_id = task_data.get("task_id")
            self.log(f"✅ CTT task created: {self.task_id}")
        else:
            self.log(f"❌ CTT task creation failed: {task_response.status_code} - {task_response.text}")
            return False
            
        # Link the task to the project
        link_response = self.session.post(f"{BACKEND_URL}/gem-flight/projects/{self.project_id}/link-task", json={
            "task_id": self.task_id,
            "step_num": 6
        })
        
        if link_response.status_code == 200:
            self.log(f"✅ Task linked to project")
        else:
            self.log(f"❌ Task linking failed: {link_response.status_code} - {link_response.text}")
            return False
            
        # Create a lifestyle routine
        routine_response = self.session.post(f"{BACKEND_URL}/lifestyle/routines", json={
            "title": "Daily skill building",
            "description": "Practice coding and leadership skills daily",
            "life_area": "career",
            "frequency": "daily",
            "time_slot": "19:00",
            "priority": "high",
            "category": "skill_development",
            "expected_value": "2 hours",
            "unit": "hours"
        })
        
        if routine_response.status_code == 200:
            routine_data = routine_response.json()
            self.routine_id = routine_data.get("routine_id")
            self.log(f"✅ Lifestyle routine created: {self.routine_id}")
        else:
            self.log(f"❌ Lifestyle routine creation failed: {routine_response.status_code} - {routine_response.text}")
            return False
            
        # Link the routine to the project
        link_routine_response = self.session.post(f"{BACKEND_URL}/gem-flight/projects/{self.project_id}/link-routine", json={
            "routine_id": self.routine_id
        })
        
        if link_routine_response.status_code == 200:
            self.log(f"✅ Routine linked to project")
            
            # Verify dashboard now shows linked items
            dashboard_response = self.session.get(f"{BACKEND_URL}/gem-flight/projects/{self.project_id}/dashboard")
            if dashboard_response.status_code == 200:
                dashboard_data = dashboard_response.json()
                linked_tasks = dashboard_data.get("linked_tasks", [])
                linked_routines = dashboard_data.get("linked_routines", [])
                
                self.log(f"✅ Dashboard shows {len(linked_tasks)} linked tasks and {len(linked_routines)} linked routines")
                return True
            else:
                self.log(f"❌ Dashboard verification failed: {dashboard_response.status_code}")
                return False
        else:
            self.log(f"❌ Routine linking failed: {link_routine_response.status_code} - {link_routine_response.text}")
            return False
            
    def test_igis_stubs(self):
        """Step 14: Test iGIS stub endpoints"""
        self.log("🔮 Testing iGIS stub endpoints...")
        
        igis_endpoints = [
            ("astrology", "Astrology"),
            ("energy-healing", "Energy Healing"),
            ("manifestation", "Manifestation")
        ]
        
        all_passed = True
        
        for endpoint, name in igis_endpoints:
            response = self.session.get(f"{BACKEND_URL}/gem-flight/projects/{self.project_id}/igis/{endpoint}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "stub" and "placeholder_data" in data:
                    self.log(f"✅ {name} stub working - Status: {data.get('status')}")
                else:
                    self.log(f"❌ {name} stub malformed - Missing status or placeholder_data")
                    all_passed = False
            else:
                self.log(f"❌ {name} stub failed: {response.status_code} - {response.text}")
                all_passed = False
                
        return all_passed
        
    def test_delete_project(self):
        """Step 15: Test project deletion"""
        self.log("🗑️ Testing project deletion...")
        
        response = self.session.delete(f"{BACKEND_URL}/gem-flight/projects/{self.project_id}")
        
        if response.status_code == 200:
            self.log(f"✅ Project deleted successfully")
            
            # Verify it's gone
            get_response = self.session.get(f"{BACKEND_URL}/gem-flight/projects/{self.project_id}")
            if get_response.status_code == 404:
                self.log(f"✅ Project deletion verified - 404 on subsequent GET")
                return True
            else:
                self.log(f"❌ Project still exists after deletion")
                return False
        else:
            self.log(f"❌ Project deletion failed: {response.status_code} - {response.text}")
            return False
            
    def run_all_tests(self):
        """Run all GEM Flight Model tests"""
        self.log("🚀 Starting GEM Flight Model Comprehensive Testing")
        self.log("=" * 60)
        
        tests = [
            ("User Registration", self.test_user_registration),
            ("Config Endpoint", self.test_config_endpoint),
            ("Create Flight Project", self.test_create_flight_project),
            ("List Projects", self.test_list_projects),
            ("Get Single Project", self.test_get_single_project),
            ("Update Project", self.test_update_project),
            ("Step Management", self.test_step_management),
            ("Gear Management", self.test_gear_management),
            ("Flight Score Computation", self.test_flight_score),
            ("Flight Dynamics", self.test_flight_dynamics),
            ("Flight Event Log", self.test_flight_event_log),
            ("Dashboard Endpoint", self.test_dashboard),
            ("Link Modules", self.test_link_modules),
            ("iGIS Stubs", self.test_igis_stubs),
            ("Delete Project", self.test_delete_project),
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
                self.log(f"❌ {test_name} crashed: {str(e)}")
                failed += 1
                
        self.log("\n" + "=" * 60)
        self.log(f"🎯 GEM FLIGHT MODEL TESTING COMPLETE")
        self.log(f"✅ Passed: {passed}")
        self.log(f"❌ Failed: {failed}")
        self.log(f"📊 Success Rate: {(passed/(passed+failed)*100):.1f}%")
        
        return passed, failed

if __name__ == "__main__":
    tester = GEMFlightTester()
    passed, failed = tester.run_all_tests()