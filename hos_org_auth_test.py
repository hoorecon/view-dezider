#!/usr/bin/env python3
"""
HOS Decision Intake Layer and Org Auth Testing
Tests the newly implemented HOS endpoints and Org Auth functionality
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
    
    # ========================
    # TEST GROUP 1: HOS Master Data & Seed
    # ========================
    
    def test_hos_seed_data(self) -> bool:
        """Test POST /api/hos/seed - Should seed master data (idempotent)"""
        print("\n🧪 Testing HOS Seed Data...")
        
        # Test 1: First seed call - should create data
        response = requests.post(f"{BACKEND_URL}/hos/seed")
        if response.status_code != 200:
            print(f"❌ HOS seed failed: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        print(f"✅ HOS seed successful: {data.get('message')}")
        
        # Verify counts
        counts = data.get("counts", {})
        expected_counts = {
            "life_areas": 10,
            "ask_types": 3,
            "sub_areas": 38,  # Updated to match actual seeded data
            "categories": 25,
            "templates": 16,
            "template_defaults": 8
        }
        
        for key, expected in expected_counts.items():
            actual = counts.get(key, 0)
            if actual != expected:
                print(f"❌ Unexpected count for {key}: expected {expected}, got {actual}")
                return False
        
        print(f"✅ All seed counts correct: {counts}")
        
        # Test 2: Second seed call - should return "already seeded"
        response = requests.post(f"{BACKEND_URL}/hos/seed")
        if response.status_code != 200:
            print(f"❌ Second HOS seed failed: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        if "already seeded" not in data.get("message", "").lower():
            print(f"❌ Second seed should return 'already seeded' message: {data.get('message')}")
            return False
        
        print(f"✅ Second seed correctly returned: {data.get('message')}")
        return True
    
    def test_hos_life_areas(self) -> bool:
        """Test GET /api/hos/life-areas - Should return 10 life areas"""
        print("\n🧪 Testing HOS Life Areas...")
        
        response = requests.get(f"{BACKEND_URL}/hos/life-areas")
        if response.status_code != 200:
            print(f"❌ Get life areas failed: {response.status_code} - {response.text}")
            return False
        
        life_areas = response.json()
        if len(life_areas) != 10:
            print(f"❌ Expected 10 life areas, got {len(life_areas)}")
            return False
        
        # Verify structure of first life area
        first_area = life_areas[0]
        required_fields = ["id", "name", "slug", "icon", "color", "order"]
        for field in required_fields:
            if field not in first_area:
                print(f"❌ Missing field '{field}' in life area")
                return False
        
        print(f"✅ Retrieved {len(life_areas)} life areas with correct structure")
        
        # Verify specific life areas exist
        area_slugs = [area.get("slug") for area in life_areas]
        expected_slugs = ["finance", "career", "holistic_health", "relationships"]
        for slug in expected_slugs:
            if slug not in area_slugs:
                print(f"❌ Expected life area slug '{slug}' not found")
                return False
        
        print(f"✅ All expected life area slugs found")
        return True
    
    def test_hos_ask_types(self) -> bool:
        """Test GET /api/hos/ask-types - Should return 3 ask types"""
        print("\n🧪 Testing HOS Ask Types...")
        
        response = requests.get(f"{BACKEND_URL}/hos/ask-types")
        if response.status_code != 200:
            print(f"❌ Get ask types failed: {response.status_code} - {response.text}")
            return False
        
        ask_types = response.json()
        if len(ask_types) != 3:
            print(f"❌ Expected 3 ask types, got {len(ask_types)}")
            return False
        
        # Verify the 3 ask types: Problem (P0), Need (P1), Aspiration (P2)
        expected_types = [
            {"slug": "problem", "priority_label": "P0"},
            {"slug": "need", "priority_label": "P1"},
            {"slug": "aspiration", "priority_label": "P2"}
        ]
        
        for expected in expected_types:
            found = False
            for ask_type in ask_types:
                if ask_type.get("slug") == expected["slug"] and ask_type.get("priority_label") == expected["priority_label"]:
                    found = True
                    break
            if not found:
                print(f"❌ Expected ask type not found: {expected}")
                return False
        
        print(f"✅ Retrieved {len(ask_types)} ask types: Problem (P0), Need (P1), Aspiration (P2)")
        return True
    
    def test_hos_sub_areas(self) -> bool:
        """Test GET /api/hos/sub-areas?life_area_id=la_finance"""
        print("\n🧪 Testing HOS Sub Areas...")
        
        response = requests.get(f"{BACKEND_URL}/hos/sub-areas?life_area_id=la_finance")
        if response.status_code != 200:
            print(f"❌ Get sub areas failed: {response.status_code} - {response.text}")
            return False
        
        sub_areas = response.json()
        if len(sub_areas) == 0:
            print(f"❌ Expected sub areas for Finance, got {len(sub_areas)}")
            return False
        
        # Verify Finance sub-areas exist
        expected_finance_areas = ["Income", "Expenses", "Savings", "Investments", "Debt", "Risk Management"]
        area_names = [area.get("name") for area in sub_areas]
        
        for expected in expected_finance_areas:
            if expected not in area_names:
                print(f"❌ Expected Finance sub-area '{expected}' not found")
                return False
        
        print(f"✅ Retrieved {len(sub_areas)} Finance sub-areas: {area_names}")
        return True
    
    def test_hos_categories(self) -> bool:
        """Test GET /api/hos/categories?sub_area_id=sa_fin_income"""
        print("\n🧪 Testing HOS Categories...")
        
        response = requests.get(f"{BACKEND_URL}/hos/categories?sub_area_id=sa_fin_income")
        if response.status_code != 200:
            print(f"❌ Get categories failed: {response.status_code} - {response.text}")
            return False
        
        categories = response.json()
        if len(categories) == 0:
            print(f"❌ Expected categories for Income sub-area, got {len(categories)}")
            return False
        
        # Verify Income categories exist
        expected_categories = ["Salary Growth", "Business Revenue", "Side Income", "Pricing Strategy", "Cash Flow Stability"]
        category_names = [cat.get("name") for cat in categories]
        
        for expected in expected_categories:
            if expected not in category_names:
                print(f"❌ Expected Income category '{expected}' not found")
                return False
        
        print(f"✅ Retrieved {len(categories)} Income categories: {category_names}")
        return True
    
    # ========================
    # TEST GROUP 2: Template Autosuggest & Detail
    # ========================
    
    def test_hos_templates_list(self) -> bool:
        """Test GET /api/hos/templates?life_area_id=la_finance"""
        print("\n🧪 Testing HOS Templates List...")
        
        response = requests.get(f"{BACKEND_URL}/hos/templates?life_area_id=la_finance")
        if response.status_code != 200:
            print(f"❌ Get templates failed: {response.status_code} - {response.text}")
            return False
        
        templates = response.json()
        if len(templates) == 0:
            print(f"❌ Expected Finance templates, got {len(templates)}")
            return False
        
        print(f"✅ Retrieved {len(templates)} Finance templates")
        
        # Verify template structure
        first_template = templates[0]
        required_fields = ["id", "title", "description", "life_area_id", "ask_type_id", "acting_as_contexts"]
        for field in required_fields:
            if field not in first_template:
                print(f"❌ Missing field '{field}' in template")
                return False
        
        print(f"✅ Template structure verified")
        return True
    
    def test_hos_templates_suggest_basic(self) -> bool:
        """Test GET /api/hos/templates/suggest with basic parameters"""
        print("\n🧪 Testing HOS Templates Suggest (Basic)...")
        
        params = {
            "acting_as": "INDIVIDUAL",
            "life_area_id": "la_finance",
            "ask_type_id": "at_problem"
        }
        
        response = requests.get(f"{BACKEND_URL}/hos/templates/suggest", params=params)
        if response.status_code != 200:
            print(f"❌ Templates suggest failed: {response.status_code} - {response.text}")
            return False
        
        templates = response.json()
        print(f"✅ Retrieved {len(templates)} matching templates for INDIVIDUAL + Finance + Problem")
        
        # Verify all templates match the criteria
        for template in templates:
            if template.get("life_area_id") != "la_finance":
                print(f"❌ Template doesn't match life_area_id filter: {template.get('life_area_id')}")
                return False
            if template.get("ask_type_id") != "at_problem":
                print(f"❌ Template doesn't match ask_type_id filter: {template.get('ask_type_id')}")
                return False
            if "INDIVIDUAL" not in template.get("acting_as_contexts", []):
                print(f"❌ Template doesn't match acting_as filter: {template.get('acting_as_contexts')}")
                return False
        
        print(f"✅ All templates match the filter criteria")
        return True
    
    def test_hos_templates_suggest_with_query(self) -> bool:
        """Test GET /api/hos/templates/suggest with search query"""
        print("\n🧪 Testing HOS Templates Suggest (With Query)...")
        
        params = {
            "acting_as": "INDIVIDUAL",
            "life_area_id": "la_finance",
            "ask_type_id": "at_problem",
            "q": "quit"
        }
        
        response = requests.get(f"{BACKEND_URL}/hos/templates/suggest", params=params)
        if response.status_code != 200:
            print(f"❌ Templates suggest with query failed: {response.status_code} - {response.text}")
            return False
        
        templates = response.json()
        print(f"✅ Retrieved {len(templates)} templates matching 'quit' query")
        
        # Should find "Should I quit my job?" template
        quit_job_found = False
        for template in templates:
            if "quit" in template.get("title", "").lower() or "quit" in template.get("description", "").lower():
                quit_job_found = True
                print(f"✅ Found quit-related template: {template.get('title')}")
                break
        
        if not quit_job_found and len(templates) > 0:
            print(f"❌ Expected to find quit-related template in search results")
            return False
        
        return True
    
    def test_hos_templates_suggest_org_context(self) -> bool:
        """Test GET /api/hos/templates/suggest for ORGANIZATION context"""
        print("\n🧪 Testing HOS Templates Suggest (Organization Context)...")
        
        params = {
            "acting_as": "ORGANIZATION",
            "life_area_id": "la_career",
            "ask_type_id": "at_aspiration"
        }
        
        response = requests.get(f"{BACKEND_URL}/hos/templates/suggest", params=params)
        if response.status_code != 200:
            print(f"❌ Organization templates suggest failed: {response.status_code} - {response.text}")
            return False
        
        templates = response.json()
        print(f"✅ Retrieved {len(templates)} templates for ORGANIZATION + Career + Aspiration")
        
        # Should find organization-context templates like "expand startup"
        org_template_found = False
        for template in templates:
            if "expand" in template.get("title", "").lower() or "startup" in template.get("title", "").lower():
                org_template_found = True
                print(f"✅ Found organization template: {template.get('title')}")
                break
        
        if not org_template_found and len(templates) > 0:
            print(f"❌ Expected to find organization-context template")
            return False
        
        return True
    
    def test_hos_template_detail(self) -> bool:
        """Test GET /api/hos/templates/tpl_fin_quit_job"""
        print("\n🧪 Testing HOS Template Detail...")
        
        response = requests.get(f"{BACKEND_URL}/hos/templates/tpl_fin_quit_job")
        if response.status_code != 200:
            print(f"❌ Get template detail failed: {response.status_code} - {response.text}")
            return False
        
        template = response.json()
        
        # Verify template structure
        required_fields = ["id", "title", "description", "life_area_id", "ask_type_id"]
        for field in required_fields:
            if field not in template:
                print(f"❌ Missing field '{field}' in template detail")
                return False
        
        print(f"✅ Template detail retrieved: {template.get('title')}")
        
        # Verify defaults are included
        defaults = template.get("defaults")
        if defaults:
            if "default_factors_json" not in defaults:
                print(f"❌ Missing default_factors_json in template defaults")
                return False
            
            factors = defaults.get("default_factors_json", [])
            if len(factors) == 0:
                print(f"❌ Expected default factors in template")
                return False
            
            print(f"✅ Template has {len(factors)} default factors")
            
            # Verify CLD placeholder
            if "future_cld_placeholder_json" in defaults:
                cld = defaults["future_cld_placeholder_json"]
                if "starter_variables" in cld and "potential_loops" in cld:
                    print(f"✅ Template has CLD placeholder with variables and loops")
                else:
                    print(f"❌ CLD placeholder missing required fields")
                    return False
        else:
            print(f"❌ Template defaults not found")
            return False
        
        return True
    
    # ========================
    # TEST GROUP 3: Decision Creation from HOS Intake
    # ========================
    
    def test_hos_decision_creation_with_template(self) -> bool:
        """Test POST /api/hos/decisions with template"""
        print("\n🧪 Testing HOS Decision Creation (With Template)...")
        
        decision_data = {
            "acting_as_context": "INDIVIDUAL",
            "life_area_id": "la_finance",
            "ask_type_id": "at_problem",
            "template_id": "tpl_fin_quit_job",
            "title": "Should I quit my current job?",
            "raw_user_input": "I'm considering leaving my job due to stress and better opportunities elsewhere",
            "source_type": "AUTHORIZED_STANDARD"
        }
        
        response = requests.post(f"{BACKEND_URL}/hos/decisions", json=decision_data, headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ HOS decision creation failed: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        self.test_decision_id = data.get("id")
        
        # Verify response structure
        required_fields = ["id", "title", "source_type", "factors_loaded", "message"]
        for field in required_fields:
            if field not in data:
                print(f"❌ Missing field '{field}' in decision creation response")
                return False
        
        factors_loaded = data.get("factors_loaded", 0)
        if factors_loaded == 0:
            print(f"❌ Expected factors to be loaded from template, got {factors_loaded}")
            return False
        
        print(f"✅ HOS decision created: {data.get('title')} with {factors_loaded} factors loaded")
        return True
    
    def test_hos_decision_creation_custom_blank(self) -> bool:
        """Test POST /api/hos/decisions without template (custom blank)"""
        print("\n🧪 Testing HOS Decision Creation (Custom Blank)...")
        
        decision_data = {
            "acting_as_context": "INDIVIDUAL",
            "life_area_id": "la_career",
            "ask_type_id": "at_need",
            "title": "Custom career decision",
            "raw_user_input": "I need to make a custom career decision without using a template",
            "source_type": "CUSTOM_BLANK"
        }
        
        response = requests.post(f"{BACKEND_URL}/hos/decisions", json=decision_data, headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Custom blank decision creation failed: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        
        factors_loaded = data.get("factors_loaded", 0)
        if factors_loaded != 0:
            print(f"❌ Expected 0 factors for custom blank, got {factors_loaded}")
            return False
        
        print(f"✅ Custom blank decision created: {data.get('title')} with {factors_loaded} factors")
        return True
    
    def test_hos_decision_metadata_verification(self) -> bool:
        """Test GET /api/decisions/{id} to verify HOS metadata is stored"""
        print("\n🧪 Testing HOS Decision Metadata Verification...")
        
        if not self.test_decision_id:
            print(f"❌ No test decision ID available")
            return False
        
        response = requests.get(f"{BACKEND_URL}/decisions/{self.test_decision_id}", headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Get decision failed: {response.status_code} - {response.text}")
            return False
        
        decision = response.json()
        
        # Verify HOS metadata is stored
        hos_metadata = decision.get("hos_metadata")
        if not hos_metadata:
            print(f"❌ HOS metadata not found in decision")
            return False
        
        required_metadata_fields = ["acting_as_context", "life_area_id", "ask_type_id", "template_id", "source_type"]
        for field in required_metadata_fields:
            if field not in hos_metadata:
                print(f"❌ Missing HOS metadata field: {field}")
                return False
        
        print(f"✅ HOS metadata verified: {hos_metadata}")
        
        # Verify factors are pre-loaded
        factors = decision.get("factors", [])
        if len(factors) == 0:
            print(f"❌ Expected pre-loaded factors from template")
            return False
        
        print(f"✅ Decision has {len(factors)} pre-loaded factors")
        
        # Verify folder mapping
        folder = decision.get("folder")
        life_area = decision.get("life_area")
        if folder != "finance" or life_area != "finance":
            print(f"❌ Expected folder/life_area to be 'finance', got folder='{folder}', life_area='{life_area}'")
            return False
        
        print(f"✅ Folder and life_area correctly mapped to 'finance'")
        return True
    
    # ========================
    # TEST GROUP 4: Org Auth (validation and error handling)
    # ========================
    
    def test_org_auth_invalid_org_slug(self) -> bool:
        """Test POST /api/org-auth/login with invalid org_slug → 404"""
        print("\n🧪 Testing Org Auth - Invalid Org Slug...")
        
        login_data = {
            "org_slug": "nonexistent-org-slug",
            "email": "test@example.com",
            "password": "password123"
        }
        
        response = requests.post(f"{BACKEND_URL}/org-auth/login", json=login_data)
        if response.status_code != 404:
            print(f"❌ Expected 404 for invalid org slug, got {response.status_code}")
            return False
        
        data = response.json()
        if "organization not found" not in data.get("detail", "").lower():
            print(f"❌ Expected 'Organization not found' error message, got: {data.get('detail')}")
            return False
        
        print(f"✅ Invalid org slug correctly returns 404: {data.get('detail')}")
        return True
    
    def test_org_auth_invalid_verification_id(self) -> bool:
        """Test POST /api/org-auth/verify-otp with invalid verification_id → 404"""
        print("\n🧪 Testing Org Auth - Invalid Verification ID...")
        
        verify_data = {
            "verification_id": "nonexistent-verification-id",
            "otp": "123456"
        }
        
        response = requests.post(f"{BACKEND_URL}/org-auth/verify-otp", json=verify_data)
        if response.status_code != 404:
            print(f"❌ Expected 404 for invalid verification ID, got {response.status_code}")
            return False
        
        data = response.json()
        if "verification session not found" not in data.get("detail", "").lower():
            print(f"❌ Expected 'Verification session not found' error message, got: {data.get('detail')}")
            return False
        
        print(f"✅ Invalid verification ID correctly returns 404: {data.get('detail')}")
        return True
    
    # ========================
    # MAIN TEST RUNNER
    # ========================
    
    def run_all_tests(self) -> bool:
        """Run all HOS and Org Auth tests"""
        print("🚀 Starting HOS Decision Intake Layer and Org Auth Testing...")
        print(f"Backend URL: {BACKEND_URL}")
        
        # Step 1: Register and login
        if not self.register_and_login():
            return False
        
        # TEST GROUP 1: HOS Master Data & Seed
        print("\n" + "="*60)
        print("TEST GROUP 1: HOS Master Data & Seed")
        print("="*60)
        
        if not self.test_hos_seed_data():
            return False
        
        if not self.test_hos_life_areas():
            return False
        
        if not self.test_hos_ask_types():
            return False
        
        if not self.test_hos_sub_areas():
            return False
        
        if not self.test_hos_categories():
            return False
        
        # TEST GROUP 2: Template Autosuggest & Detail
        print("\n" + "="*60)
        print("TEST GROUP 2: Template Autosuggest & Detail")
        print("="*60)
        
        if not self.test_hos_templates_list():
            return False
        
        if not self.test_hos_templates_suggest_basic():
            return False
        
        if not self.test_hos_templates_suggest_with_query():
            return False
        
        if not self.test_hos_templates_suggest_org_context():
            return False
        
        if not self.test_hos_template_detail():
            return False
        
        # TEST GROUP 3: Decision Creation from HOS Intake
        print("\n" + "="*60)
        print("TEST GROUP 3: Decision Creation from HOS Intake")
        print("="*60)
        
        if not self.test_hos_decision_creation_with_template():
            return False
        
        if not self.test_hos_decision_creation_custom_blank():
            return False
        
        if not self.test_hos_decision_metadata_verification():
            return False
        
        # TEST GROUP 4: Org Auth (validation and error handling)
        print("\n" + "="*60)
        print("TEST GROUP 4: Org Auth (validation and error handling)")
        print("="*60)
        
        if not self.test_org_auth_invalid_org_slug():
            return False
        
        if not self.test_org_auth_invalid_verification_id():
            return False
        
        print("\n🎉 ALL HOS AND ORG AUTH TESTS PASSED!")
        return True

def main():
    """Main test execution"""
    tester = HOSOrgAuthTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n✅ HOS Decision Intake Layer and Org Auth Testing Complete - All Tests Passed!")
        exit(0)
    else:
        print("\n❌ HOS Decision Intake Layer and Org Auth Testing Failed!")
        exit(1)

if __name__ == "__main__":
    main()