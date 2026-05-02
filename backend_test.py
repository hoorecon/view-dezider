"""Backend API Testing for DigiLocker Integration and Solution Finder Collaboration"""

import requests
import json
import time
from datetime import datetime

# Backend URL from review request
BASE_URL = "https://dezider-core.preview.emergentagent.com/api"

class TestRunner:
    def __init__(self):
        self.session_token = None
        self.user_id = None
        self.decision_id = None
        self.results = []
        
    def log(self, test_name, status, message, details=None):
        """Log test result"""
        result = {
            "test": test_name,
            "status": status,
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.results.append(result)
        status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⏭️"
        print(f"{status_icon} {test_name}: {message}")
        if details:
            print(f"   Details: {details}")
    
    def register_user(self):
        """Register a new test user"""
        timestamp = int(time.time())
        email = f"digilocker_test_{timestamp}@test.com"
        
        try:
            response = requests.post(
                f"{BASE_URL}/auth/register",
                json={
                    "email": email,
                    "password": "TestPass123!",
                    "name": "DigiLocker Test User"
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self.session_token = data.get("session_token")
                self.user_id = data.get("user_id")
                self.log("User Registration", "PASS", f"Registered user: {email}", 
                        {"user_id": self.user_id, "email": email})
                return True
            else:
                self.log("User Registration", "FAIL", f"Status {response.status_code}", 
                        {"response": response.text})
                return False
        except Exception as e:
            self.log("User Registration", "FAIL", f"Exception: {str(e)}")
            return False
    
    def login_user(self, email, password):
        """Login existing user"""
        try:
            response = requests.post(
                f"{BASE_URL}/auth/login",
                json={"email": email, "password": password},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self.session_token = data.get("session_token")
                self.user_id = data.get("user_id")
                self.log("User Login", "PASS", f"Logged in: {email}")
                return True
            else:
                self.log("User Login", "FAIL", f"Status {response.status_code}", 
                        {"response": response.text})
                return False
        except Exception as e:
            self.log("User Login", "FAIL", f"Exception: {str(e)}")
            return False
    
    def test_digilocker_initiate_not_configured(self):
        """Test DigiLocker initiate endpoint without SANDBOX_API_KEY - should return not_configured with setup_options"""
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            response = requests.post(
                f"{BASE_URL}/collaboration/digilocker/initiate",
                headers=headers,
                json={},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                setup_options = data.get("setup_options", [])
                
                # Check if status is 'not_configured' or 'initiated'
                if status == "not_configured":
                    # Verify setup_options array exists and has TWO providers
                    if len(setup_options) == 2:
                        providers = [opt.get("provider") for opt in setup_options]
                        
                        # Check for both providers
                        has_sandbox = any("sandbox.co.in" in p for p in providers)
                        has_official = any("DigiLocker Official" in p for p in providers)
                        
                        if has_sandbox and has_official:
                            # Verify env_vars are present for each provider
                            sandbox_opt = next((opt for opt in setup_options if "sandbox.co.in" in opt.get("provider", "")), None)
                            official_opt = next((opt for opt in setup_options if "DigiLocker Official" in opt.get("provider", "")), None)
                            
                            sandbox_env_vars = sandbox_opt.get("env_vars", []) if sandbox_opt else []
                            official_env_vars = official_opt.get("env_vars", []) if official_opt else []
                            
                            if sandbox_env_vars and official_env_vars:
                                self.log("DigiLocker Initiate - Not Configured Response", "PASS",
                                        "Returns status='not_configured' with setup_options array containing TWO providers with env_vars",
                                        {
                                            "status": status,
                                            "setup_options_count": len(setup_options),
                                            "providers": providers,
                                            "sandbox_env_vars": sandbox_env_vars,
                                            "official_env_vars": official_env_vars
                                        })
                                return True
                            else:
                                self.log("DigiLocker Initiate - Not Configured Response", "FAIL",
                                        "env_vars missing for one or both providers",
                                        {"sandbox_env_vars": sandbox_env_vars, "official_env_vars": official_env_vars})
                                return False
                        else:
                            self.log("DigiLocker Initiate - Not Configured Response", "FAIL",
                                    "Missing required providers (sandbox.co.in or DigiLocker Official)",
                                    {"providers": providers})
                            return False
                    else:
                        self.log("DigiLocker Initiate - Not Configured Response", "FAIL",
                                f"Expected 2 providers in setup_options, got {len(setup_options)}",
                                {"setup_options": setup_options})
                        return False
                elif status == "initiated":
                    # API is configured, so it initiated the flow
                    self.log("DigiLocker Initiate - Not Configured Response", "PASS",
                            "API is configured (SANDBOX_API_KEY present), initiated flow successfully",
                            {"status": status, "provider": data.get("provider")})
                    return True
                else:
                    self.log("DigiLocker Initiate - Not Configured Response", "FAIL",
                            f"Unexpected status: {status}",
                            {"response": data})
                    return False
            else:
                self.log("DigiLocker Initiate - Not Configured Response", "FAIL",
                        f"Status {response.status_code}",
                        {"response": response.text})
                return False
        except Exception as e:
            self.log("DigiLocker Initiate - Not Configured Response", "FAIL", f"Exception: {str(e)}")
            return False
    
    def test_digilocker_callback_without_session_id(self):
        """Test DigiLocker callback endpoint without session_id - should return 400"""
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            response = requests.post(
                f"{BASE_URL}/collaboration/digilocker/callback",
                headers=headers,
                json={},  # No session_id
                timeout=30
            )
            
            # Should return 400 Bad Request
            if response.status_code == 400:
                data = response.json()
                detail = data.get("detail", "")
                
                if "session_id" in detail.lower():
                    self.log("DigiLocker Callback - Missing session_id", "PASS",
                            "Returns 400 error when session_id is missing",
                            {"status_code": 400, "error_message": detail})
                    return True
                else:
                    self.log("DigiLocker Callback - Missing session_id", "FAIL",
                            "Returns 400 but error message doesn't mention session_id",
                            {"error_message": detail})
                    return False
            else:
                self.log("DigiLocker Callback - Missing session_id", "FAIL",
                        f"Expected 400, got {response.status_code}",
                        {"response": response.text})
                return False
        except Exception as e:
            self.log("DigiLocker Callback - Missing session_id", "FAIL", f"Exception: {str(e)}")
            return False
    
    def create_decision(self):
        """Create a test decision for collaboration"""
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            response = requests.post(
                f"{BASE_URL}/decisions",
                headers=headers,
                json={
                    "title": "Test Decision for Collaboration",
                    "description": "Testing collaboration session creation",
                    "decision_type": "aspiration",
                    "life_area": "career"
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self.decision_id = data.get("id")
                self.log("Create Decision", "PASS", f"Created decision: {self.decision_id}")
                return True
            else:
                self.log("Create Decision", "FAIL", f"Status {response.status_code}",
                        {"response": response.text})
                return False
        except Exception as e:
            self.log("Create Decision", "FAIL", f"Exception: {str(e)}")
            return False
    
    def create_solution_finder(self):
        """Create a test solution finder entry"""
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            response = requests.post(
                f"{BASE_URL}/solution-finders",
                headers=headers,
                json={
                    "area_of_life": "career",
                    "smart_goal": "Test Solution Finder for Collaboration",
                    "milestones": ["Milestone 1", "Milestone 2"],
                    "q1_all_concerns": "Test concerns",
                    "q2_primary_concerns": "Primary test concerns",
                    "q3_solutions": "Test solutions",
                    "q3_capabilities": "Test capabilities",
                    "q3_resources": "Test resources",
                    "q4_negative_consequences": "Test consequences",
                    "q4_mitigation_plans": "Test mitigation",
                    "q4_contingency_plans": "Test contingency",
                    "action_items": []
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                sf_entry_id = data.get("entry_id")
                self.log("Create Solution Finder", "PASS", f"Created solution finder: {sf_entry_id}",
                        {"entry_id": sf_entry_id})
                return sf_entry_id
            else:
                self.log("Create Solution Finder", "FAIL", f"Status {response.status_code}",
                        {"response": response.text})
                return None
        except Exception as e:
            self.log("Create Solution Finder", "FAIL", f"Exception: {str(e)}")
            return None
    
    def create_contact(self):
        """Create a test contact for collaboration"""
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            timestamp = int(time.time())
            response = requests.post(
                f"{BASE_URL}/contacts",
                headers=headers,
                json={
                    "name": "Test Contact",
                    "email": f"contact_{timestamp}@test.com",
                    "phone": "+919876543210",
                    "is_sme": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                contact_id = data.get("id")
                self.log("Create Contact", "PASS", f"Created contact: {contact_id}")
                return contact_id
            else:
                self.log("Create Contact", "FAIL", f"Status {response.status_code}",
                        {"response": response.text})
                return None
        except Exception as e:
            self.log("Create Contact", "FAIL", f"Exception: {str(e)}")
            return None
    
    def test_solution_finder_collab_session(self, sf_entry_id, contact_id):
        """Test creating collaboration session with module_type='solution_finder'"""
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            response = requests.post(
                f"{BASE_URL}/collaboration/sessions",
                headers=headers,
                json={
                    "module_type": "solution_finder",
                    "module_id": sf_entry_id,
                    "title": "Test Solution Finder Collaboration",
                    "decision_mode_id": "equal",
                    "participant_contact_ids": [contact_id],
                    "notify_participants": False,
                    "session_mode": "async"
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                session_id = data.get("id")
                module_type = data.get("module_type")
                module_id = data.get("module_id")
                
                if module_type == "solution_finder" and module_id == sf_entry_id:
                    self.log("Solution Finder Collaboration Session", "PASS",
                            "Successfully created collaboration session with module_type='solution_finder'",
                            {
                                "session_id": session_id,
                                "module_type": module_type,
                                "module_id": module_id,
                                "title": data.get("title"),
                                "decision_mode": data.get("decision_mode_id")
                            })
                    return True
                else:
                    self.log("Solution Finder Collaboration Session", "FAIL",
                            "Session created but module_type or module_id mismatch",
                            {"expected_module_type": "solution_finder", "got": module_type,
                             "expected_module_id": sf_entry_id, "got": module_id})
                    return False
            else:
                self.log("Solution Finder Collaboration Session", "FAIL",
                        f"Status {response.status_code}",
                        {"response": response.text})
                return False
        except Exception as e:
            self.log("Solution Finder Collaboration Session", "FAIL", f"Exception: {str(e)}")
            return False
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        skipped = sum(1 for r in self.results if r["status"] == "SKIP")
        
        print(f"Total Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⏭️ Skipped: {skipped}")
        print(f"Success Rate: {(passed/total*100):.1f}%" if total > 0 else "N/A")
        
        if failed > 0:
            print("\n" + "="*80)
            print("FAILED TESTS:")
            print("="*80)
            for r in self.results:
                if r["status"] == "FAIL":
                    print(f"❌ {r['test']}: {r['message']}")
                    if r.get("details"):
                        print(f"   {r['details']}")
        
        print("\n" + "="*80)
        return passed, failed, skipped

def main():
    print("="*80)
    print("DIGILOCKER INTEGRATION & SOLUTION FINDER COLLABORATION TESTING")
    print("="*80)
    print(f"Backend URL: {BASE_URL}")
    print(f"Test Started: {datetime.now().isoformat()}")
    print("="*80 + "\n")
    
    runner = TestRunner()
    
    # Step 1: Register user
    if not runner.register_user():
        print("\n❌ Failed to register user. Aborting tests.")
        return
    
    # Step 2: Test DigiLocker initiate endpoint
    runner.test_digilocker_initiate_not_configured()
    
    # Step 3: Test DigiLocker callback without session_id
    runner.test_digilocker_callback_without_session_id()
    
    # Step 4: Create decision (for context)
    runner.create_decision()
    
    # Step 5: Create solution finder entry
    sf_entry_id = runner.create_solution_finder()
    
    # Step 6: Create contact for collaboration
    contact_id = runner.create_contact()
    
    # Step 7: Test Solution Finder collaboration session
    if sf_entry_id and contact_id:
        runner.test_solution_finder_collab_session(sf_entry_id, contact_id)
    else:
        runner.log("Solution Finder Collaboration Session", "SKIP",
                  "Skipped due to missing solution finder or contact")
    
    # Print summary
    runner.print_summary()

if __name__ == "__main__":
    main()
