#!/usr/bin/env python3
"""
Enhanced MPPS and Decision Templates API Testing
Testing the enhanced MPPS fields and Decision Templates CRUD operations
"""

import requests
import json
import time
import uuid
from datetime import datetime, timezone

# Backend URL from environment
BACKEND_URL = "https://dezider-multi-user.preview.emergentagent.com/api"

class TestEnhancedMPPSAndTemplates:
    def __init__(self):
        self.session = requests.Session()
        self.user_token = None
        self.admin_token = None
        self.decision_id = None
        self.template_id = None
        
    def log(self, message):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        
    def test_user_registration_and_login(self):
        """Test 1: Register a user and login"""
        self.log("🔐 Testing user registration and login...")
        
        # Generate unique email
        timestamp = int(time.time())
        email = f"mpps.tester.{timestamp}@careerpath.com"
        
        # Register user
        register_data = {
            "email": email,
            "password": "securepass123",
            "name": "MPPS Tester"
        }
        
        response = self.session.post(f"{BACKEND_URL}/auth/register", json=register_data)
        if response.status_code != 200:
            raise Exception(f"Registration failed: {response.status_code} - {response.text}")
            
        result = response.json()
        self.user_token = result["session_token"]
        self.log(f"✅ User registered successfully: {email}")
        
        # Set authorization header
        self.session.headers.update({"Authorization": f"Bearer {self.user_token}"})
        
        return True
        
    def test_create_decision_with_factors(self):
        """Test 2: Create a decision with factors and options"""
        self.log("📋 Testing decision creation with factors...")
        
        # Create decision
        decision_data = {
            "title": "Enhanced MPPS Career Decision",
            "context": "Testing enhanced MPPS features with action items and timeframes",
            "folder": "career"
        }
        
        response = self.session.post(f"{BACKEND_URL}/decisions", json=decision_data)
        if response.status_code != 200:
            raise Exception(f"Decision creation failed: {response.status_code} - {response.text}")
            
        result = response.json()
        self.decision_id = result["id"]
        self.log(f"✅ Decision created: {self.decision_id}")
        
        # Add factors
        factors = [
            {
                "id": "f_salary",
                "name": "Salary Package",
                "category": "primary",
                "rating": 80,
                "order": 0,
                "unit": "USD",
                "expected_value": 120000,
                "data_type": "numeric",
                "operator": ">="
            },
            {
                "id": "f_growth",
                "name": "Career Growth",
                "category": "primary", 
                "rating": 70,
                "order": 1
            },
            {
                "id": "f_location",
                "name": "Work Location",
                "category": "secondary",
                "rating": 50,
                "order": 2,
                "expected_value": "Remote",
                "data_type": "text",
                "operator": "contains"
            }
        ]
        
        # Add options
        options = [
            {
                "id": "opt_company_a",
                "name": "TechCorp Inc",
                "assessments": [
                    {"factor_id": "f_salary", "percentage": 75, "actual_value": 110000, "assessment_mode": "H"},
                    {"factor_id": "f_growth", "percentage": 60, "assessment_mode": "M"},
                    {"factor_id": "f_location", "percentage": 90, "assessment_mode": "H"}
                ]
            },
            {
                "id": "opt_company_b", 
                "name": "InnovateLabs",
                "assessments": [
                    {"factor_id": "f_salary", "percentage": 85, "actual_value": 125000, "assessment_mode": "H"},
                    {"factor_id": "f_growth", "percentage": 80, "assessment_mode": "H"},
                    {"factor_id": "f_location", "percentage": 70, "assessment_mode": "M"}
                ]
            }
        ]
        
        # Update decision with factors and options
        update_data = {
            "factors": factors,
            "options": options
        }
        
        response = self.session.put(f"{BACKEND_URL}/decisions/{self.decision_id}", json=update_data)
        if response.status_code != 200:
            raise Exception(f"Decision update failed: {response.status_code} - {response.text}")
            
        self.log("✅ Decision updated with factors and options")
        return True
        
    def test_enhanced_mpps_data_saving(self):
        """Test 3: Save enhanced MPPS data with new fields"""
        self.log("🎯 Testing enhanced MPPS data saving...")
        
        # Enhanced MPPS data with new fields
        mpps_improvements = [
            {
                "factor_id": "f_salary",
                "original_percentage": 75,
                "projected_percentage": 90,
                "delta_percentage": 15,
                "expected_value": "130000",
                "expected_unit": "USD",
                "improvement_plan": "Negotiate salary increase after 6 months performance review",
                "tepfi_elements": ["T", "F"],  # Time and Finance
                "tepfi_layer": "self",
                "action_items": [
                    {
                        "assignee_name": "John Smith",
                        "assignee_email": "john.smith@techcorp.com",
                        "assignee_mobile": "+1-555-0123",
                        "task": "Schedule performance review meeting",
                        "deadline": "2024-06-15"
                    },
                    {
                        "assignee_name": "Sarah Johnson",
                        "assignee_email": "sarah.j@techcorp.com", 
                        "assignee_mobile": "+1-555-0456",
                        "task": "Prepare salary benchmarking report",
                        "deadline": "2024-06-10"
                    }
                ]
            },
            {
                "factor_id": "f_growth",
                "original_percentage": 60,
                "projected_percentage": 85,
                "delta_percentage": 25,
                "expected_value": "Senior Developer",
                "expected_unit": "Role",
                "improvement_plan": "Complete advanced certification and lead 2 major projects",
                "tepfi_elements": ["E", "P"],  # Education and People
                "tepfi_layer": "micro",
                "action_items": [
                    {
                        "assignee_name": "Mike Chen",
                        "assignee_email": "mike.chen@techcorp.com",
                        "assignee_mobile": "+1-555-0789",
                        "task": "Enroll in AWS Solutions Architect certification",
                        "deadline": "2024-05-01"
                    }
                ]
            },
            {
                "factor_id": "f_location",
                "original_percentage": 90,
                "projected_percentage": 95,
                "delta_percentage": 5,
                "expected_value": "Full Remote",
                "expected_unit": "Policy",
                "improvement_plan": "Negotiate permanent remote work arrangement",
                "tepfi_elements": ["F"],  # Finance (cost savings)
                "tepfi_layer": "macro",
                "action_items": [
                    {
                        "assignee_name": "Lisa Wong",
                        "assignee_email": "lisa.wong@hr.techcorp.com",
                        "assignee_mobile": "+1-555-0321",
                        "task": "Draft remote work policy amendment",
                        "deadline": "2024-04-30"
                    }
                ]
            }
        ]
        
        # Save enhanced MPPS data
        mpps_data = {
            "mpps_option_id": "opt_company_a",
            "mpps_timeframe": "3 months",
            "mpps_improvements": mpps_improvements,
            "mpps_projected_worth": 88.5
        }
        
        response = self.session.put(f"{BACKEND_URL}/decisions/{self.decision_id}", json=mpps_data)
        if response.status_code != 200:
            raise Exception(f"MPPS data saving failed: {response.status_code} - {response.text}")
            
        self.log("✅ Enhanced MPPS data saved successfully")
        return True
        
    def test_mpps_data_persistence(self):
        """Test 4: Verify enhanced MPPS fields persist via GET"""
        self.log("🔍 Testing MPPS data persistence...")
        
        response = self.session.get(f"{BACKEND_URL}/decisions/{self.decision_id}")
        if response.status_code != 200:
            raise Exception(f"Decision retrieval failed: {response.status_code} - {response.text}")
            
        decision = response.json()
        
        # Verify enhanced MPPS fields
        assert decision.get("mpps_timeframe") == "3 months", "MPPS timeframe not persisted"
        assert decision.get("mpps_projected_worth") == 88.5, "MPPS projected worth not persisted"
        assert decision.get("mpps_option_id") == "opt_company_a", "MPPS option ID not persisted"
        
        improvements = decision.get("mpps_improvements", [])
        assert len(improvements) == 3, f"Expected 3 improvements, got {len(improvements)}"
        
        # Verify first improvement with action items
        first_improvement = improvements[0]
        assert first_improvement.get("factor_id") == "f_salary", "Factor ID not persisted"
        assert first_improvement.get("tepfi_elements") == ["T", "F"], "TEPFI elements not persisted"
        assert first_improvement.get("tepfi_layer") == "self", "TEPFI layer not persisted"
        assert first_improvement.get("expected_value") == "130000", "Expected value not persisted"
        assert first_improvement.get("expected_unit") == "USD", "Expected unit not persisted"
        assert first_improvement.get("delta_percentage") == 15, "Delta percentage not persisted"
        
        action_items = first_improvement.get("action_items", [])
        assert len(action_items) == 2, f"Expected 2 action items, got {len(action_items)}"
        
        first_action = action_items[0]
        assert first_action.get("assignee_name") == "John Smith", "Assignee name not persisted"
        assert first_action.get("assignee_email") == "john.smith@techcorp.com", "Assignee email not persisted"
        assert first_action.get("assignee_mobile") == "+1-555-0123", "Assignee mobile not persisted"
        assert first_action.get("task") == "Schedule performance review meeting", "Task not persisted"
        assert first_action.get("deadline") == "2024-06-15", "Deadline not persisted"
        
        self.log("✅ All enhanced MPPS fields persisted correctly")
        return True
        
    def test_mpps_action_plan_csv_download(self):
        """Test 5: Test MPPS Action Plan CSV download"""
        self.log("📊 Testing MPPS Action Plan CSV download...")
        
        response = self.session.get(f"{BACKEND_URL}/decisions/{self.decision_id}/mpps-action-plan")
        if response.status_code != 200:
            raise Exception(f"CSV download failed: {response.status_code} - {response.text}")
            
        # Verify response headers
        content_type = response.headers.get("content-type")
        assert "text/csv" in content_type, f"Expected CSV content type, got {content_type}"
        
        content_disposition = response.headers.get("content-disposition")
        assert "attachment" in content_disposition, "Missing attachment header"
        assert "MPPS_Action_Plan" in content_disposition, "Missing filename in header"
        
        # Verify CSV content
        csv_content = response.text
        lines = csv_content.strip().split('\n')
        
        # Check header structure
        assert "MPPS Action Plan" in lines[0], "Missing CSV title"
        assert "Enhanced MPPS Career Decision" in csv_content, "Decision title not in CSV"
        assert "3 months" in csv_content, "Timeframe not in CSV"
        assert "88.5%" in csv_content, "Projected worth not in CSV"
        
        # Check action items in CSV
        assert "John Smith" in csv_content, "Assignee name not in CSV"
        assert "john.smith@techcorp.com" in csv_content, "Assignee email not in CSV"
        assert "+1-555-0123" in csv_content, "Assignee mobile not in CSV"
        assert "Schedule performance review meeting" in csv_content, "Task not in CSV"
        assert "2024-06-15" in csv_content, "Deadline not in CSV"
        
        # Check TEPFI elements and layers
        assert "T, F" in csv_content, "TEPFI elements not in CSV"
        assert "self" in csv_content, "TEPFI layer not in CSV"
        
        self.log("✅ MPPS Action Plan CSV download working correctly")
        return True
        
    def test_decision_meta_endpoint(self):
        """Test 6: Test decision meta endpoint"""
        self.log("📚 Testing decision meta endpoint...")
        
        response = self.session.get(f"{BACKEND_URL}/decision-meta")
        if response.status_code != 200:
            raise Exception(f"Decision meta failed: {response.status_code} - {response.text}")
            
        meta = response.json()
        
        # Verify life areas
        life_areas = meta.get("life_areas", [])
        assert len(life_areas) > 0, "No life areas returned"
        
        career_area = next((area for area in life_areas if area["id"] == "career"), None)
        assert career_area is not None, "Career life area not found"
        assert career_area["name"] == "Career & Work", "Career area name incorrect"
        assert career_area["icon"] == "briefcase", "Career area icon incorrect"
        
        # Verify decision types
        decision_types = meta.get("decision_types", [])
        assert len(decision_types) == 3, f"Expected 3 decision types, got {len(decision_types)}"
        
        problem_type = next((dt for dt in decision_types if dt["id"] == "problem"), None)
        assert problem_type is not None, "Problem decision type not found"
        assert problem_type["name"] == "Problem", "Problem type name incorrect"
        assert problem_type["color"] == "#EF4444", "Problem type color incorrect"
        
        self.log("✅ Decision meta endpoint working correctly")
        return True
        
    def test_create_admin_user(self):
        """Test 7: Create admin user for template testing"""
        self.log("👑 Creating admin user for template testing...")
        
        # Generate unique admin email
        timestamp = int(time.time())
        admin_email = f"admin.tester.{timestamp}@techcorp.com"
        
        # Register admin user
        admin_data = {
            "email": admin_email,
            "password": "adminpass123",
            "name": "Admin Tester"
        }
        
        # Create new session for admin
        admin_session = requests.Session()
        response = admin_session.post(f"{BACKEND_URL}/auth/register", json=admin_data)
        if response.status_code != 200:
            raise Exception(f"Admin registration failed: {response.status_code} - {response.text}")
            
        result = response.json()
        self.admin_token = result["session_token"]
        admin_session.headers.update({"Authorization": f"Bearer {self.admin_token}"})
        
        # Promote to admin role (assuming super admin exists)
        # For testing purposes, we'll try to create templates and expect 403 for non-admin
        self.admin_session = admin_session
        
        self.log(f"✅ Admin user created: {admin_email}")
        return True
        
    def test_decision_templates_non_admin_access(self):
        """Test 8: Verify template creation requires admin role"""
        self.log("🚫 Testing non-admin template creation restriction...")
        
        # Try to create template with regular user (should fail)
        template_data = {
            "name": "Career Change Template",
            "life_area": "career",
            "decision_type": "aspiration",
            "description": "Template for career transition decisions",
            "factors": [
                {
                    "id": str(uuid.uuid4()),
                    "name": "Salary Expectations",
                    "category": "primary",
                    "rating": 80,
                    "order": 0
                }
            ]
        }
        
        response = self.session.post(f"{BACKEND_URL}/decision-templates", json=template_data)
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}"
        
        error = response.json()
        assert "Admin access required" in error.get("detail", ""), "Missing admin access error message"
        
        self.log("✅ Non-admin template creation correctly restricted")
        return True
        
    def test_decision_templates_get_public(self):
        """Test 9: Test getting decision templates (public endpoint)"""
        self.log("📋 Testing decision templates GET endpoint...")
        
        # Test general templates endpoint
        response = self.session.get(f"{BACKEND_URL}/decision-templates")
        if response.status_code != 200:
            raise Exception(f"Templates GET failed: {response.status_code} - {response.text}")
            
        templates = response.json()
        assert isinstance(templates, list), "Templates should be a list"
        
        # Test with life_area filter
        response = self.session.get(f"{BACKEND_URL}/decision-templates?life_area=career")
        if response.status_code != 200:
            raise Exception(f"Templates GET with filter failed: {response.status_code} - {response.text}")
            
        career_templates = response.json()
        assert isinstance(career_templates, list), "Filtered templates should be a list"
        
        # Test with decision_type filter
        response = self.session.get(f"{BACKEND_URL}/decision-templates?decision_type=problem")
        if response.status_code != 200:
            raise Exception(f"Templates GET with type filter failed: {response.status_code} - {response.text}")
            
        problem_templates = response.json()
        assert isinstance(problem_templates, list), "Type filtered templates should be a list"
        
        self.log("✅ Decision templates GET endpoint working correctly")
        return True
        
    def run_all_tests(self):
        """Run all enhanced MPPS and Decision Templates tests"""
        tests = [
            self.test_user_registration_and_login,
            self.test_create_decision_with_factors,
            self.test_enhanced_mpps_data_saving,
            self.test_mpps_data_persistence,
            self.test_mpps_action_plan_csv_download,
            self.test_decision_meta_endpoint,
            self.test_create_admin_user,
            self.test_decision_templates_non_admin_access,
            self.test_decision_templates_get_public
        ]
        
        passed = 0
        failed = 0
        
        for test in tests:
            try:
                test()
                passed += 1
            except Exception as e:
                self.log(f"❌ {test.__name__} FAILED: {str(e)}")
                failed += 1
                
        self.log(f"\n🎯 ENHANCED MPPS AND DECISION TEMPLATES TESTING COMPLETE")
        self.log(f"✅ Passed: {passed}")
        self.log(f"❌ Failed: {failed}")
        
        if failed == 0:
            self.log("🎉 ALL TESTS PASSED!")
        else:
            self.log(f"⚠️  {failed} tests failed")
            
        return failed == 0

if __name__ == "__main__":
    tester = TestEnhancedMPPSAndTemplates()
    success = tester.run_all_tests()
    exit(0 if success else 1)