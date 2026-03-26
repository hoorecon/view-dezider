#!/usr/bin/env python3
"""
HOS Decision Intake & Org Auth Testing
Tests the expanded HOS seed data and org-auth endpoints as requested in review
"""

import requests
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

# Backend URL from frontend/.env
BACKEND_URL = "https://prr-actions-central.preview.emergentagent.com/api"

class HOSOrgAuthTester:
    def __init__(self):
        self.session_token = None
        self.user_data = None
        self.test_decision_id = None
        
    def register_and_login(self) -> bool:
        """Register a new user and get session token"""
        timestamp = int(time.time())
        email = f"hos.tester.{timestamp}@viewdezider.com"
        
        # Register user
        register_data = {
            "email": email,
            "password": "testpass123",
            "name": f"HOS Tester {timestamp}"
        }
        
        response = requests.post(f"{BACKEND_URL}/auth/register", json=register_data)
        if response.status_code != 200:
            print(f"❌ Registration failed: {response.status_code} - {response.text}")
            return False
            
        data = response.json()
        self.session_token = data.get("session_token")
        self.user_data = data
        print(f"✅ User registered: {email}")
        return True
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers with authentication"""
        return {
            "Authorization": f"Bearer {self.session_token}",
            "Content-Type": "application/json"
        }
    
    def test_hos_expanded_seed_verification(self) -> bool:
        """Test HOS Expanded Seed Verification (most important)"""
        print("\n🧪 Testing HOS Expanded Seed Verification...")
        
        # Test 1: POST /api/hos/seed (should return "already seeded" with correct counts)
        response = requests.post(f"{BACKEND_URL}/hos/seed")
        if response.status_code != 200:
            print(f"❌ HOS seed failed: {response.status_code} - {response.text}")
            return False
        
        seed_data = response.json()
        print(f"✅ HOS seed response: {seed_data}")
        
        # Check expected counts from review request
        expected_counts = {
            "life_areas": 10,
            "ask_types": 3,
            "sub_areas": 80,
            "categories": 77,
            "templates": 52,
            "template_defaults": 12
        }
        
        # Get actual counts from the response
        actual_counts = seed_data.get("counts", {})
        
        # Verify counts match expectations
        for key, expected_count in expected_counts.items():
            actual_count = actual_counts.get(key, 0)
            if actual_count != expected_count:
                print(f"⚠️  Count mismatch for {key}: expected {expected_count}, got {actual_count}")
            else:
                print(f"✅ {key}: {actual_count} (matches expected)")
        
        # Test 2: POST /api/hos/seed?force=true (should drop and re-seed)
        response = requests.post(f"{BACKEND_URL}/hos/seed?force=true")
        if response.status_code != 200:
            print(f"❌ HOS force seed failed: {response.status_code} - {response.text}")
            return False
        
        force_seed_data = response.json()
        print(f"✅ HOS force seed response: {force_seed_data}")
        
        return True
    
    def test_hos_life_areas_and_sub_areas(self) -> bool:
        """Test HOS life areas and sub-areas endpoints"""
        print("\n🧪 Testing HOS Life Areas and Sub-Areas...")
        
        # Test 1: GET /api/hos/life-areas (should return 10 areas)
        response = requests.get(f"{BACKEND_URL}/hos/life-areas")
        if response.status_code != 200:
            print(f"❌ Get life areas failed: {response.status_code} - {response.text}")
            return False
        
        life_areas = response.json()
        print(f"✅ Retrieved {len(life_areas)} life areas")
        
        if len(life_areas) != 10:
            print(f"⚠️  Expected 10 life areas, got {len(life_areas)}")
        
        # Test 2: GET /api/hos/sub-areas?life_area_id=la_health (should return 8 health sub-areas)
        response = requests.get(f"{BACKEND_URL}/hos/sub-areas?life_area_id=la_health")
        if response.status_code != 200:
            print(f"❌ Get health sub-areas failed: {response.status_code} - {response.text}")
            return False
        
        health_sub_areas = response.json()
        print(f"✅ Retrieved {len(health_sub_areas)} health sub-areas")
        
        if len(health_sub_areas) != 8:
            print(f"⚠️  Expected 8 health sub-areas, got {len(health_sub_areas)}")
        
        # Test 3: GET /api/hos/sub-areas?life_area_id=la_spirituality (should return 8 spirituality sub-areas)
        response = requests.get(f"{BACKEND_URL}/hos/sub-areas?life_area_id=la_spirituality")
        if response.status_code != 200:
            print(f"❌ Get spirituality sub-areas failed: {response.status_code} - {response.text}")
            return False
        
        spirituality_sub_areas = response.json()
        print(f"✅ Retrieved {len(spirituality_sub_areas)} spirituality sub-areas")
        
        if len(spirituality_sub_areas) != 8:
            print(f"⚠️  Expected 8 spirituality sub-areas, got {len(spirituality_sub_areas)}")
        
        return True
    
    def test_hos_categories_and_templates(self) -> bool:
        """Test HOS categories and templates endpoints"""
        print("\n🧪 Testing HOS Categories and Templates...")
        
        # Test 1: GET /api/hos/categories?sub_area_id=sa_hlt_mental (should return health mental categories)
        response = requests.get(f"{BACKEND_URL}/hos/categories?sub_area_id=sa_hlt_mental")
        if response.status_code != 200:
            print(f"❌ Get health mental categories failed: {response.status_code} - {response.text}")
            return False
        
        mental_categories = response.json()
        print(f"✅ Retrieved {len(mental_categories)} health mental categories")
        
        # Test 2: GET /api/hos/templates?life_area_id=la_health (should return 6 Health templates)
        response = requests.get(f"{BACKEND_URL}/hos/templates?life_area_id=la_health")
        if response.status_code != 200:
            print(f"❌ Get health templates failed: {response.status_code} - {response.text}")
            return False
        
        health_templates = response.json()
        print(f"✅ Retrieved {len(health_templates)} health templates")
        
        if len(health_templates) != 6:
            print(f"⚠️  Expected 6 health templates, got {len(health_templates)}")
        
        # Test 3: GET /api/hos/templates?life_area_id=la_knowledge (should return 5 Knowledge templates)
        response = requests.get(f"{BACKEND_URL}/hos/templates?life_area_id=la_knowledge")
        if response.status_code != 200:
            print(f"❌ Get knowledge templates failed: {response.status_code} - {response.text}")
            return False
        
        knowledge_templates = response.json()
        print(f"✅ Retrieved {len(knowledge_templates)} knowledge templates")
        
        if len(knowledge_templates) != 5:
            print(f"⚠️  Expected 5 knowledge templates, got {len(knowledge_templates)}")
        
        # Test 4: GET /api/hos/templates?life_area_id=la_assets (should return 4 Asset templates)
        response = requests.get(f"{BACKEND_URL}/hos/templates?life_area_id=la_assets")
        if response.status_code != 200:
            print(f"❌ Get asset templates failed: {response.status_code} - {response.text}")
            return False
        
        asset_templates = response.json()
        print(f"✅ Retrieved {len(asset_templates)} asset templates")
        
        if len(asset_templates) != 4:
            print(f"⚠️  Expected 4 asset templates, got {len(asset_templates)}")
        
        # Test 5: GET /api/hos/templates?life_area_id=la_spirituality (should return 4 Spirituality templates)
        response = requests.get(f"{BACKEND_URL}/hos/templates?life_area_id=la_spirituality")
        if response.status_code != 200:
            print(f"❌ Get spirituality templates failed: {response.status_code} - {response.text}")
            return False
        
        spirituality_templates = response.json()
        print(f"✅ Retrieved {len(spirituality_templates)} spirituality templates")
        
        if len(spirituality_templates) != 4:
            print(f"⚠️  Expected 4 spirituality templates, got {len(spirituality_templates)}")
        
        return True
    
    def test_template_autosuggest(self) -> bool:
        """Test Template Autosuggest across new areas"""
        print("\n🧪 Testing Template Autosuggest...")
        
        # Test 1: GET /api/hos/templates/suggest?acting_as=INDIVIDUAL&life_area_id=la_health&ask_type_id=at_problem
        response = requests.get(f"{BACKEND_URL}/hos/templates/suggest?acting_as=INDIVIDUAL&life_area_id=la_health&ask_type_id=at_problem")
        if response.status_code != 200:
            print(f"❌ Health problem autosuggest failed: {response.status_code} - {response.text}")
            return False
        
        health_problem_suggestions = response.json()
        print(f"✅ Health problem autosuggest: {len(health_problem_suggestions)} suggestions")
        
        # Test 2: GET /api/hos/templates/suggest?acting_as=INDIVIDUAL&life_area_id=la_spirituality&ask_type_id=at_aspiration
        response = requests.get(f"{BACKEND_URL}/hos/templates/suggest?acting_as=INDIVIDUAL&life_area_id=la_spirituality&ask_type_id=at_aspiration")
        if response.status_code != 200:
            print(f"❌ Spirituality aspiration autosuggest failed: {response.status_code} - {response.text}")
            return False
        
        spirituality_aspiration_suggestions = response.json()
        print(f"✅ Spirituality aspiration autosuggest: {len(spirituality_aspiration_suggestions)} suggestions")
        
        # Test 3: GET /api/hos/templates/suggest?acting_as=INDIVIDUAL&life_area_id=la_assets&ask_type_id=at_need
        response = requests.get(f"{BACKEND_URL}/hos/templates/suggest?acting_as=INDIVIDUAL&life_area_id=la_assets&ask_type_id=at_need")
        if response.status_code != 200:
            print(f"❌ Assets need autosuggest failed: {response.status_code} - {response.text}")
            return False
        
        assets_need_suggestions = response.json()
        print(f"✅ Assets need autosuggest: {len(assets_need_suggestions)} suggestions")
        
        return True
    
    def test_template_detail(self) -> bool:
        """Test Template Detail for new templates"""
        print("\n🧪 Testing Template Detail...")
        
        # Test 1: GET /api/hos/templates/tpl_hlt_mental_health (should have 6 default factors)
        response = requests.get(f"{BACKEND_URL}/hos/templates/tpl_hlt_mental_health")
        if response.status_code != 200:
            print(f"❌ Mental health template detail failed: {response.status_code} - {response.text}")
            return False
        
        mental_health_template = response.json()
        default_factors = mental_health_template.get("defaults", {}).get("default_factors_json", [])
        print(f"✅ Mental health template: {len(default_factors)} default factors")
        
        if len(default_factors) != 6:
            print(f"⚠️  Expected 6 default factors, got {len(default_factors)}")
        
        # Test 2: GET /api/hos/templates/tpl_ast_buy_home (should have 6 default factors)
        response = requests.get(f"{BACKEND_URL}/hos/templates/tpl_ast_buy_home")
        if response.status_code != 200:
            print(f"❌ Buy home template detail failed: {response.status_code} - {response.text}")
            return False
        
        buy_home_template = response.json()
        default_factors = buy_home_template.get("defaults", {}).get("default_factors_json", [])
        print(f"✅ Buy home template: {len(default_factors)} default factors")
        
        if len(default_factors) != 6:
            print(f"⚠️  Expected 6 default factors, got {len(default_factors)}")
        
        # Test 3: GET /api/hos/templates/tpl_spi_purpose (should have 6 default factors)
        response = requests.get(f"{BACKEND_URL}/hos/templates/tpl_spi_purpose")
        if response.status_code != 200:
            print(f"❌ Purpose template detail failed: {response.status_code} - {response.text}")
            return False
        
        purpose_template = response.json()
        default_factors = purpose_template.get("defaults", {}).get("default_factors_json", [])
        print(f"✅ Purpose template: {len(default_factors)} default factors")
        
        if len(default_factors) != 6:
            print(f"⚠️  Expected 6 default factors, got {len(default_factors)}")
        
        # Test 4: GET /api/hos/templates/tpl_kno_degree (should have 6 default factors)
        response = requests.get(f"{BACKEND_URL}/hos/templates/tpl_kno_degree")
        if response.status_code != 200:
            print(f"❌ Degree template detail failed: {response.status_code} - {response.text}")
            return False
        
        degree_template = response.json()
        default_factors = degree_template.get("defaults", {}).get("default_factors_json", [])
        print(f"✅ Degree template: {len(default_factors)} default factors")
        
        if len(default_factors) != 6:
            print(f"⚠️  Expected 6 default factors, got {len(default_factors)}")
        
        return True
    
    def test_decision_creation_from_templates(self) -> bool:
        """Test Decision Creation from new templates"""
        print("\n🧪 Testing Decision Creation from Templates...")
        
        # Test: POST /api/hos/decisions with template_id=tpl_hlt_mental_health
        decision_data = {
            "template_id": "tpl_hlt_mental_health",
            "acting_as_context": "INDIVIDUAL",
            "life_area_id": "la_health",
            "ask_type_id": "at_problem",
            "title": "How to manage my chronic stress?",
            "raw_user_input": "I've been dealing with chronic stress and need help managing it effectively"
        }
        
        response = requests.post(f"{BACKEND_URL}/hos/decisions", json=decision_data, headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Decision creation from template failed: {response.status_code} - {response.text}")
            return False
        
        decision = response.json()
        self.test_decision_id = decision.get("id")
        factors_loaded = decision.get("factors_loaded", 0)
        print(f"✅ Decision created from mental health template: {self.test_decision_id}")
        print(f"✅ Factors loaded from template: {factors_loaded}")
        
        # Verify the created decision has factors pre-loaded from template defaults
        response = requests.get(f"{BACKEND_URL}/decisions/{self.test_decision_id}", headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Get created decision failed: {response.status_code} - {response.text}")
            return False
        
        decision_detail = response.json()
        factors = decision_detail.get("factors", [])
        print(f"✅ Created decision has {len(factors)} factors pre-loaded from template")
        
        if len(factors) == 0:
            print(f"⚠️  Expected factors to be pre-loaded from template defaults")
        
        return True
    
    def test_org_auth_endpoints(self) -> bool:
        """Test Org Auth endpoint validation"""
        print("\n🧪 Testing Org Auth Endpoints...")
        
        # Test 1: POST /api/org-auth/login with invalid org_slug returns 404 with "Organization not found"
        login_data = {
            "org_slug": "invalid-org-slug-12345",
            "email": "test@example.com",
            "password": "testpass123"
        }
        
        response = requests.post(f"{BACKEND_URL}/org-auth/login", json=login_data)
        if response.status_code != 404:
            print(f"❌ Expected 404 for invalid org_slug, got: {response.status_code}")
            return False
        
        error_data = response.json()
        if "Organization not found" not in error_data.get("detail", ""):
            print(f"❌ Expected 'Organization not found' error message, got: {error_data}")
            return False
        
        print(f"✅ Invalid org_slug correctly returns 404 with 'Organization not found'")
        
        # Test 2: POST /api/org-auth/verify-otp with invalid verification_id returns 404
        verify_data = {
            "verification_id": "invalid-verification-id-12345",
            "otp": "123456"
        }
        
        response = requests.post(f"{BACKEND_URL}/org-auth/verify-otp", json=verify_data)
        if response.status_code != 404:
            print(f"❌ Expected 404 for invalid verification_id, got: {response.status_code}")
            return False
        
        print(f"✅ Invalid verification_id correctly returns 404")
        
        return True
    
    def run_all_tests(self) -> bool:
        """Run all HOS and Org Auth tests"""
        print("🚀 Starting HOS Decision Intake & Org Auth Testing...")
        print(f"Backend URL: {BACKEND_URL}")
        
        # Step 1: Register and login for authenticated endpoints
        if not self.register_and_login():
            return False
        
        # Step 2: Test HOS Expanded Seed Verification (most important)
        if not self.test_hos_expanded_seed_verification():
            return False
        
        # Step 3: Test HOS life areas and sub-areas
        if not self.test_hos_life_areas_and_sub_areas():
            return False
        
        # Step 4: Test HOS categories and templates
        if not self.test_hos_categories_and_templates():
            return False
        
        # Step 5: Test Template Autosuggest
        if not self.test_template_autosuggest():
            return False
        
        # Step 6: Test Template Detail
        if not self.test_template_detail():
            return False
        
        # Step 7: Test Decision Creation from Templates
        if not self.test_decision_creation_from_templates():
            return False
        
        # Step 8: Test Org Auth Endpoints
        if not self.test_org_auth_endpoints():
            return False
        
        print("\n🎉 ALL HOS & ORG AUTH TESTS COMPLETED!")
        return True

def main():
    """Main test execution"""
    tester = HOSOrgAuthTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n✅ HOS Decision Intake & Org Auth Testing Complete!")
        exit(0)
    else:
        print("\n❌ HOS Decision Intake & Org Auth Testing Failed!")
        exit(1)

if __name__ == "__main__":
    main()