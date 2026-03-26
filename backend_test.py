#!/usr/bin/env python3
"""
Backend Testing for Journal Enhancement Feature
Tests the newly implemented journal endpoints with module linking and reminders
"""

import requests
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

# Backend URL from frontend/.env
BACKEND_URL = "https://prr-actions-central.preview.emergentagent.com/api"

class JournalEnhancementTester:
    def __init__(self):
        self.session_token = None
        self.user_data = None
        self.test_decision_id = None
        self.test_journal_id = None
        
    def register_and_login(self) -> bool:
        """Register a new user and get session token"""
        timestamp = int(time.time())
        email = f"journal.tester.{timestamp}@viewdezider.com"
        
        # Register user
        register_data = {
            "email": email,
            "password": "testpass123",
            "name": f"Journal Tester {timestamp}"
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
    
    def test_enhanced_journal_create(self) -> bool:
        """Test POST /api/journal with new fields (linked_module, entry_type)"""
        print("\n🧪 Testing Enhanced Journal Create...")
        
        # Test 1: Create journal entry with linked_module="decision" and entry_type="best_practice"
        journal_data = {
            "decision_title": "Career Decision Best Practice",
            "decision_description": "Documenting the best practice from my recent career decision",
            "linked_module": "decision",
            "linked_id": "test-decision-123",
            "linked_title": "Should I take the new job offer?",
            "entry_type": "best_practice"
        }
        
        response = requests.post(f"{BACKEND_URL}/journal", json=journal_data, headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Journal create failed: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        self.test_journal_id = data.get("id")
        print(f"✅ Journal entry created with linked_module='decision' and entry_type='best_practice': {self.test_journal_id}")
        
        # Test 2: Create journal entry with linked_module="gem" and entry_type="learning"
        journal_data2 = {
            "decision_title": "Gem Goal Learning",
            "decision_description": "Key learnings from my gem goal achievement",
            "linked_module": "gem",
            "linked_id": "test-gem-456",
            "linked_title": "Complete fitness transformation",
            "entry_type": "learning"
        }
        
        response = requests.post(f"{BACKEND_URL}/journal", json=journal_data2, headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Second journal create failed: {response.status_code} - {response.text}")
            return False
        
        print(f"✅ Journal entry created with linked_module='gem' and entry_type='learning'")
        
        # Test 3: Test validation - invalid linked_module
        invalid_data = {
            "decision_title": "Invalid Test",
            "decision_description": "Testing invalid linked_module",
            "linked_module": "invalid_module",
            "entry_type": "best_practice"
        }
        
        response = requests.post(f"{BACKEND_URL}/journal", json=invalid_data, headers=self.get_headers())
        if response.status_code != 400:
            print(f"❌ Validation failed - should reject invalid linked_module: {response.status_code}")
            return False
        
        print(f"✅ Validation working - invalid linked_module rejected with 400")
        
        # Test 4: Test validation - invalid entry_type
        invalid_data2 = {
            "decision_title": "Invalid Test 2",
            "decision_description": "Testing invalid entry_type",
            "linked_module": "decision",
            "entry_type": "bad_type"
        }
        
        response = requests.post(f"{BACKEND_URL}/journal", json=invalid_data2, headers=self.get_headers())
        if response.status_code != 400:
            print(f"❌ Validation failed - should reject invalid entry_type: {response.status_code}")
            return False
        
        print(f"✅ Validation working - invalid entry_type rejected with 400")
        
        return True
    
    def test_enhanced_journal_get(self) -> bool:
        """Test GET /api/journal with query params"""
        print("\n🧪 Testing Enhanced Journal Get with Filters...")
        
        # Test 1: Get all journal entries (no filters)
        response = requests.get(f"{BACKEND_URL}/journal", headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Get all journal entries failed: {response.status_code} - {response.text}")
            return False
        
        all_entries = response.json()
        print(f"✅ Retrieved all journal entries: {len(all_entries)} entries")
        
        # Test 2: Filter by linked_module="decision"
        response = requests.get(f"{BACKEND_URL}/journal?linked_module=decision", headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Filter by linked_module failed: {response.status_code} - {response.text}")
            return False
        
        decision_entries = response.json()
        print(f"✅ Filtered by linked_module='decision': {len(decision_entries)} entries")
        
        # Test 3: Filter by entry_type="best_practice"
        response = requests.get(f"{BACKEND_URL}/journal?entry_type=best_practice", headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Filter by entry_type failed: {response.status_code} - {response.text}")
            return False
        
        best_practice_entries = response.json()
        print(f"✅ Filtered by entry_type='best_practice': {len(best_practice_entries)} entries")
        
        # Verify filtering worked correctly
        if len(decision_entries) > 0:
            for entry in decision_entries:
                if entry.get("linked_module") != "decision":
                    print(f"❌ Filter failed - found non-decision entry: {entry.get('linked_module')}")
                    return False
        
        if len(best_practice_entries) > 0:
            for entry in best_practice_entries:
                if entry.get("entry_type") != "best_practice":
                    print(f"❌ Filter failed - found non-best_practice entry: {entry.get('entry_type')}")
                    return False
        
        print(f"✅ All filters working correctly")
        return True
    
    def create_test_decision_with_review_date(self) -> bool:
        """Create a PRR decision with implementation_review_date for testing reminders"""
        print("\n🧪 Creating Test Decision with Review Date...")
        
        # Create decision with past implementation_review_date
        past_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        
        decision_data = {
            "title": "Test Problem Decision for Reminders",
            "context": "This is a test decision to verify reminder functionality",
            "decision_type": "problem",
            "implementation_review_date": past_date
        }
        
        response = requests.post(f"{BACKEND_URL}/decisions", json=decision_data, headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Decision creation failed: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        self.test_decision_id = data.get("id")
        print(f"✅ Test decision created with past review date: {self.test_decision_id}")
        
        return True
    
    def test_journal_reminders(self) -> bool:
        """Test GET /api/journal/reminders"""
        print("\n🧪 Testing Journal Reminders...")
        
        # First, get reminders - should include our test decision
        response = requests.get(f"{BACKEND_URL}/journal/reminders", headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Get reminders failed: {response.status_code} - {response.text}")
            return False
        
        reminders = response.json()
        print(f"✅ Retrieved reminders: {len(reminders)} reminders")
        
        # Verify our test decision is in reminders with P0 priority
        found_test_decision = False
        for reminder in reminders:
            if reminder.get("decision_id") == self.test_decision_id:
                found_test_decision = True
                if reminder.get("priority_label") != "P0":
                    print(f"❌ Wrong priority label: expected P0, got {reminder.get('priority_label')}")
                    return False
                print(f"✅ Test decision found in reminders with priority P0")
                break
        
        if not found_test_decision:
            print(f"❌ Test decision not found in reminders")
            return False
        
        # Now create a journal entry linked to this decision
        journal_data = {
            "decision_title": "Documenting Problem Decision",
            "decision_description": "Recording learnings from the problem decision",
            "linked_module": "decision",
            "linked_id": self.test_decision_id,
            "entry_type": "learning"
        }
        
        response = requests.post(f"{BACKEND_URL}/journal", json=journal_data, headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Journal entry creation failed: {response.status_code} - {response.text}")
            return False
        
        print(f"✅ Journal entry created linked to test decision")
        
        # Get reminders again - should NOT include our test decision anymore
        response = requests.get(f"{BACKEND_URL}/journal/reminders", headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Get reminders after journal creation failed: {response.status_code} - {response.text}")
            return False
        
        reminders_after = response.json()
        print(f"✅ Retrieved reminders after journal creation: {len(reminders_after)} reminders")
        
        # Verify our test decision is NOT in reminders anymore
        for reminder in reminders_after:
            if reminder.get("decision_id") == self.test_decision_id:
                print(f"❌ Test decision still in reminders after journal entry created")
                return False
        
        print(f"✅ Test decision correctly removed from reminders after journal entry created")
        return True
    
    def test_journal_linkable_items(self) -> bool:
        """Test GET /api/journal/linkable-items"""
        print("\n🧪 Testing Journal Linkable Items...")
        
        response = requests.get(f"{BACKEND_URL}/journal/linkable-items", headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Get linkable items failed: {response.status_code} - {response.text}")
            return False
        
        linkable_items = response.json()
        print(f"✅ Retrieved linkable items")
        
        # Verify structure - should have all 6 module keys
        expected_keys = ["decision", "solution_finder", "solution_matrix", "gem", "ctt", "lifestyle"]
        for key in expected_keys:
            if key not in linkable_items:
                print(f"❌ Missing key in linkable items: {key}")
                return False
        
        print(f"✅ All expected module keys present: {expected_keys}")
        
        # Verify our test decision is in the decision array
        decisions = linkable_items.get("decision", [])
        found_test_decision = False
        for decision in decisions:
            if decision.get("id") == self.test_decision_id:
                found_test_decision = True
                print(f"✅ Test decision found in linkable items: {decision.get('title')}")
                break
        
        if not found_test_decision:
            print(f"❌ Test decision not found in linkable items")
            return False
        
        return True
    
    def test_prr_decision_implementation_review_date(self) -> bool:
        """Test PRR Decision with implementation_review_date field"""
        print("\n🧪 Testing PRR Decision implementation_review_date Field...")
        
        # Test 1: Create decision with implementation_review_date
        future_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        
        decision_data = {
            "title": "Test Decision with Review Date",
            "context": "Testing implementation_review_date field",
            "decision_type": "need",
            "implementation_review_date": future_date
        }
        
        response = requests.post(f"{BACKEND_URL}/decisions", json=decision_data, headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Decision creation with review date failed: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        new_decision_id = data.get("id")
        print(f"✅ Decision created with implementation_review_date: {new_decision_id}")
        
        # Test 2: Verify the field is stored by retrieving the decision
        response = requests.get(f"{BACKEND_URL}/decisions/{new_decision_id}", headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Get decision failed: {response.status_code} - {response.text}")
            return False
        
        decision = response.json()
        stored_date = decision.get("implementation_review_date")
        if not stored_date:
            print(f"❌ implementation_review_date not stored")
            return False
        
        print(f"✅ implementation_review_date stored correctly: {stored_date}")
        
        # Test 3: Update decision with new implementation_review_date
        new_future_date = (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()
        
        update_data = {
            "implementation_review_date": new_future_date
        }
        
        response = requests.put(f"{BACKEND_URL}/decisions/{new_decision_id}", json=update_data, headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Decision update with review date failed: {response.status_code} - {response.text}")
            return False
        
        print(f"✅ Decision updated with new implementation_review_date")
        
        # Verify the update
        response = requests.get(f"{BACKEND_URL}/decisions/{new_decision_id}", headers=self.get_headers())
        if response.status_code != 200:
            print(f"❌ Get updated decision failed: {response.status_code} - {response.text}")
            return False
        
        updated_decision = response.json()
        updated_date = updated_decision.get("implementation_review_date")
        if updated_date == stored_date:
            print(f"❌ implementation_review_date not updated")
            return False
        
        print(f"✅ implementation_review_date updated correctly: {updated_date}")
        
        return True
    
    def run_all_tests(self) -> bool:
        """Run all journal enhancement tests"""
        print("🚀 Starting Journal Enhancement Feature Testing...")
        print(f"Backend URL: {BACKEND_URL}")
        
        # Step 1: Register and login
        if not self.register_and_login():
            return False
        
        # Step 2: Test enhanced journal create
        if not self.test_enhanced_journal_create():
            return False
        
        # Step 3: Test enhanced journal get with filters
        if not self.test_enhanced_journal_get():
            return False
        
        # Step 4: Create test decision for reminders
        if not self.create_test_decision_with_review_date():
            return False
        
        # Step 5: Test journal reminders
        if not self.test_journal_reminders():
            return False
        
        # Step 6: Test journal linkable items
        if not self.test_journal_linkable_items():
            return False
        
        # Step 7: Test PRR decision implementation_review_date field
        if not self.test_prr_decision_implementation_review_date():
            return False
        
        print("\n🎉 ALL JOURNAL ENHANCEMENT TESTS PASSED!")
        return True

def main():
    """Main test execution"""
    tester = JournalEnhancementTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n✅ Journal Enhancement Feature Testing Complete - All Tests Passed!")
        exit(0)
    else:
        print("\n❌ Journal Enhancement Feature Testing Failed!")
        exit(1)

if __name__ == "__main__":
    main()