"""
Comprehensive Backend API Testing for PNA Framework and Lifestyle Designer
Tests all endpoints with realistic data and proper authentication flow
"""
import requests
import json
import time
from datetime import datetime, timedelta

# Backend URL from environment
BACKEND_URL = "https://dezider-core.preview.emergentagent.com/api"

# Test user credentials
timestamp = int(time.time())
TEST_EMAIL = f"pna_lifestyle_test_{timestamp}@test.com"
TEST_PASSWORD = "SecurePass123!"
TEST_NAME = "PNA Lifestyle Tester"

# Global session token
session_token = None

def log_test(test_name, passed, details=""):
    """Log test results"""
    status = "✅ PASSED" if passed else "❌ FAILED"
    print(f"{status}: {test_name}")
    if details:
        print(f"  Details: {details}")
    print()

def register_user():
    """Register a new test user"""
    global session_token
    print("=" * 80)
    print("REGISTERING TEST USER")
    print("=" * 80)
    
    response = requests.post(
        f"{BACKEND_URL}/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "name": TEST_NAME
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        session_token = data.get("session_token")
        log_test("User Registration", True, f"User ID: {data.get('user_id')}, Email: {TEST_EMAIL}")
        return True
    else:
        log_test("User Registration", False, f"Status: {response.status_code}, Response: {response.text}")
        return False

def login_user():
    """Login with test user"""
    global session_token
    print("=" * 80)
    print("LOGGING IN")
    print("=" * 80)
    
    response = requests.post(
        f"{BACKEND_URL}/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        session_token = data.get("session_token")
        log_test("User Login", True, f"Session token obtained")
        return True
    else:
        log_test("User Login", False, f"Status: {response.status_code}, Response: {response.text}")
        return False

def get_headers():
    """Get authorization headers"""
    return {
        "Authorization": f"Bearer {session_token}",
        "Content-Type": "application/json"
    }

# ═══════════════════════════════════════════════════════════════
# PNA FRAMEWORK TESTS
# ═══════════════════════════════════════════════════════════════

def test_pna_meta():
    """Test GET /api/pna/meta"""
    print("=" * 80)
    print("TEST 1: PNA Meta Endpoint")
    print("=" * 80)
    
    response = requests.get(f"{BACKEND_URL}/pna/meta")
    
    if response.status_code == 200:
        data = response.json()
        has_life_areas = "life_areas" in data and len(data["life_areas"]) == 10
        has_categories = "categories" in data and len(data["categories"]) == 3
        has_statuses = "statuses" in data
        has_priorities = "priorities" in data
        
        passed = has_life_areas and has_categories and has_statuses and has_priorities
        log_test(
            "GET /api/pna/meta",
            passed,
            f"Life areas: {len(data.get('life_areas', []))}, Categories: {len(data.get('categories', []))}, Statuses: {data.get('statuses')}, Priorities: {data.get('priorities')}"
        )
        return data
    else:
        log_test("GET /api/pna/meta", False, f"Status: {response.status_code}")
        return None

def test_create_pna_item(life_area, category, title, priority="high", impact_score=8, urgency_score=7, description=""):
    """Test POST /api/pna/items"""
    print(f"Creating PNA item: {title}")
    
    response = requests.post(
        f"{BACKEND_URL}/pna/items",
        headers=get_headers(),
        json={
            "life_area": life_area,
            "category": category,
            "title": title,
            "priority": priority,
            "impact_score": impact_score,
            "urgency_score": urgency_score,
            "description": description
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        item_id = data.get("item_id")
        log_test(
            f"POST /api/pna/items - Create {category}",
            True,
            f"Item ID: {item_id}, Title: {title}"
        )
        return item_id
    else:
        log_test(f"POST /api/pna/items - Create {category}", False, f"Status: {response.status_code}, Response: {response.text}")
        return None

def test_list_pna_items():
    """Test GET /api/pna/items"""
    print("=" * 80)
    print("TEST 3: List PNA Items")
    print("=" * 80)
    
    response = requests.get(
        f"{BACKEND_URL}/pna/items",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        log_test(
            "GET /api/pna/items",
            True,
            f"Found {len(data)} items"
        )
        return data
    else:
        log_test("GET /api/pna/items", False, f"Status: {response.status_code}")
        return []

def test_get_pna_item(item_id):
    """Test GET /api/pna/items/{item_id}"""
    print(f"Getting PNA item: {item_id}")
    
    response = requests.get(
        f"{BACKEND_URL}/pna/items/{item_id}",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        log_test(
            f"GET /api/pna/items/{item_id}",
            True,
            f"Title: {data.get('title')}, Status: {data.get('status')}"
        )
        return data
    else:
        log_test(f"GET /api/pna/items/{item_id}", False, f"Status: {response.status_code}")
        return None

def test_update_pna_item(item_id, updates):
    """Test PUT /api/pna/items/{item_id}"""
    print(f"Updating PNA item: {item_id}")
    
    response = requests.put(
        f"{BACKEND_URL}/pna/items/{item_id}",
        headers=get_headers(),
        json=updates
    )
    
    if response.status_code == 200:
        data = response.json()
        log_test(
            f"PUT /api/pna/items/{item_id}",
            True,
            f"Updated status to: {data.get('status')}"
        )
        return data
    else:
        log_test(f"PUT /api/pna/items/{item_id}", False, f"Status: {response.status_code}")
        return None

def test_pna_dashboard():
    """Test GET /api/pna/dashboard"""
    print("=" * 80)
    print("TEST 4: PNA Dashboard")
    print("=" * 80)
    
    response = requests.get(
        f"{BACKEND_URL}/pna/dashboard",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        has_counts = "by_category" in data and "by_status" in data
        has_areas = "area_summaries" in data
        has_recent = "recent" in data
        
        passed = has_counts and has_areas and has_recent
        log_test(
            "GET /api/pna/dashboard",
            passed,
            f"Total: {data.get('total')}, By category: {data.get('by_category')}, By status: {data.get('by_status')}"
        )
        return data
    else:
        log_test("GET /api/pna/dashboard", False, f"Status: {response.status_code}")
        return None

def test_pna_area_detail(area_id):
    """Test GET /api/pna/areas/{area_id}"""
    print(f"Getting area detail for: {area_id}")
    
    response = requests.get(
        f"{BACKEND_URL}/pna/areas/{area_id}",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        log_test(
            f"GET /api/pna/areas/{area_id}",
            True,
            f"Problems: {len(data.get('problems', []))}, Needs: {len(data.get('needs', []))}, Aspirations: {len(data.get('aspirations', []))}"
        )
        return data
    else:
        log_test(f"GET /api/pna/areas/{area_id}", False, f"Status: {response.status_code}")
        return None

def test_bulk_status_update(item_ids, new_status):
    """Test POST /api/pna/items/bulk-status"""
    print(f"Bulk updating {len(item_ids)} items to status: {new_status}")
    
    response = requests.post(
        f"{BACKEND_URL}/pna/items/bulk-status",
        headers=get_headers(),
        json={
            "item_ids": item_ids,
            "status": new_status
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        log_test(
            "POST /api/pna/items/bulk-status",
            True,
            f"Updated {data.get('updated')} items to '{new_status}'"
        )
        return data
    else:
        log_test("POST /api/pna/items/bulk-status", False, f"Status: {response.status_code}")
        return None

def test_convert_to_decision(item_id):
    """Test POST /api/pna/items/{item_id}/convert-to-decision"""
    print(f"Converting PNA item to decision: {item_id}")
    
    response = requests.post(
        f"{BACKEND_URL}/pna/items/{item_id}/convert-to-decision",
        headers=get_headers(),
        json={}
    )
    
    if response.status_code == 200:
        data = response.json()
        log_test(
            f"POST /api/pna/items/{item_id}/convert-to-decision",
            True,
            f"Decision ID: {data.get('decision_id')}, Message: {data.get('message')}"
        )
        return data.get("decision_id")
    else:
        log_test(f"POST /api/pna/items/{item_id}/convert-to-decision", False, f"Status: {response.status_code}")
        return None

def test_convert_to_goal(item_id):
    """Test POST /api/pna/items/{item_id}/convert-to-goal"""
    print(f"Converting PNA item to goal: {item_id}")
    
    response = requests.post(
        f"{BACKEND_URL}/pna/items/{item_id}/convert-to-goal",
        headers=get_headers(),
        json={}
    )
    
    if response.status_code == 200:
        data = response.json()
        log_test(
            f"POST /api/pna/items/{item_id}/convert-to-goal",
            True,
            f"Goal ID: {data.get('goal_id')}, Message: {data.get('message')}"
        )
        return data.get("goal_id")
    else:
        log_test(f"POST /api/pna/items/{item_id}/convert-to-goal", False, f"Status: {response.status_code}")
        return None

def test_delete_pna_item(item_id):
    """Test DELETE /api/pna/items/{item_id}"""
    print(f"Deleting PNA item: {item_id}")
    
    response = requests.delete(
        f"{BACKEND_URL}/pna/items/{item_id}",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        log_test(
            f"DELETE /api/pna/items/{item_id}",
            True,
            f"Deleted: {data.get('deleted')}"
        )
        return True
    else:
        log_test(f"DELETE /api/pna/items/{item_id}", False, f"Status: {response.status_code}")
        return False

# ═══════════════════════════════════════════════════════════════
# LIFESTYLE DESIGNER TESTS
# ═══════════════════════════════════════════════════════════════

def test_lifestyle_meta():
    """Test GET /api/lifestyle-designer/meta"""
    print("=" * 80)
    print("TEST 5: Lifestyle Designer Meta")
    print("=" * 80)
    
    response = requests.get(f"{BACKEND_URL}/lifestyle-designer/meta")
    
    if response.status_code == 200:
        data = response.json()
        has_life_areas = "life_areas" in data and len(data["life_areas"]) == 10
        has_day_types = "day_types" in data and len(data["day_types"]) == 3
        
        passed = has_life_areas and has_day_types
        log_test(
            "GET /api/lifestyle-designer/meta",
            passed,
            f"Life areas: {len(data.get('life_areas', []))}, Day types: {data.get('day_types')}"
        )
        return data
    else:
        log_test("GET /api/lifestyle-designer/meta", False, f"Status: {response.status_code}")
        return None

def test_create_lifestyle_plan(name, allocations, is_active=True):
    """Test POST /api/lifestyle-designer/plans"""
    print(f"Creating lifestyle plan: {name}")
    
    response = requests.post(
        f"{BACKEND_URL}/lifestyle-designer/plans",
        headers=get_headers(),
        json={
            "name": name,
            "description": f"Test plan: {name}",
            "allocations": allocations,
            "is_active": is_active
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        plan_id = data.get("plan_id")
        log_test(
            f"POST /api/lifestyle-designer/plans - {name}",
            True,
            f"Plan ID: {plan_id}, Active: {data.get('is_active')}"
        )
        return plan_id
    else:
        log_test(f"POST /api/lifestyle-designer/plans - {name}", False, f"Status: {response.status_code}, Response: {response.text}")
        return None

def test_list_lifestyle_plans():
    """Test GET /api/lifestyle-designer/plans"""
    print("=" * 80)
    print("TEST 6: List Lifestyle Plans")
    print("=" * 80)
    
    response = requests.get(
        f"{BACKEND_URL}/lifestyle-designer/plans",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        log_test(
            "GET /api/lifestyle-designer/plans",
            True,
            f"Found {len(data)} plans"
        )
        return data
    else:
        log_test("GET /api/lifestyle-designer/plans", False, f"Status: {response.status_code}")
        return []

def test_get_active_plan():
    """Test GET /api/lifestyle-designer/active-plan"""
    print("=" * 80)
    print("TEST 7: Get Active Plan")
    print("=" * 80)
    
    response = requests.get(
        f"{BACKEND_URL}/lifestyle-designer/active-plan",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        active_plan = data.get("active_plan")
        if active_plan:
            log_test(
                "GET /api/lifestyle-designer/active-plan",
                True,
                f"Active plan: {active_plan.get('name')} (ID: {active_plan.get('plan_id')})"
            )
        else:
            log_test(
                "GET /api/lifestyle-designer/active-plan",
                True,
                "No active plan (expected if none activated)"
            )
        return active_plan
    else:
        log_test("GET /api/lifestyle-designer/active-plan", False, f"Status: {response.status_code}")
        return None

def test_update_lifestyle_plan(plan_id, updates):
    """Test PUT /api/lifestyle-designer/plans/{plan_id}"""
    print(f"Updating lifestyle plan: {plan_id}")
    
    response = requests.put(
        f"{BACKEND_URL}/lifestyle-designer/plans/{plan_id}",
        headers=get_headers(),
        json=updates
    )
    
    if response.status_code == 200:
        data = response.json()
        log_test(
            f"PUT /api/lifestyle-designer/plans/{plan_id}",
            True,
            f"Updated name to: {data.get('name')}"
        )
        return data
    else:
        log_test(f"PUT /api/lifestyle-designer/plans/{plan_id}", False, f"Status: {response.status_code}")
        return None

def test_activate_plan(plan_id):
    """Test POST /api/lifestyle-designer/plans/{plan_id}/activate"""
    print(f"Activating plan: {plan_id}")
    
    response = requests.post(
        f"{BACKEND_URL}/lifestyle-designer/plans/{plan_id}/activate",
        headers=get_headers(),
        json={}
    )
    
    if response.status_code == 200:
        data = response.json()
        log_test(
            f"POST /api/lifestyle-designer/plans/{plan_id}/activate",
            True,
            f"Message: {data.get('message')}"
        )
        return True
    else:
        log_test(f"POST /api/lifestyle-designer/plans/{plan_id}/activate", False, f"Status: {response.status_code}")
        return False

def test_lifestyle_comparison(days=7):
    """Test GET /api/lifestyle-designer/comparison"""
    print("=" * 80)
    print(f"TEST 8: Lifestyle Comparison (last {days} days)")
    print("=" * 80)
    
    response = requests.get(
        f"{BACKEND_URL}/lifestyle-designer/comparison?days={days}",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        log_test(
            "GET /api/lifestyle-designer/comparison",
            True,
            f"Plan: {data.get('plan_name')}, Days analyzed: {data.get('days_analyzed')}"
        )
        return data
    elif response.status_code == 400:
        # Expected if no active plan or no LEE data
        log_test(
            "GET /api/lifestyle-designer/comparison",
            True,
            "No active plan or LEE data (expected for new user)"
        )
        return None
    else:
        log_test("GET /api/lifestyle-designer/comparison", False, f"Status: {response.status_code}")
        return None

def test_save_override(date, life_area, hours, reason):
    """Test POST /api/lifestyle-designer/overrides"""
    print(f"Saving override for {date}, {life_area}: {hours}h")
    
    response = requests.post(
        f"{BACKEND_URL}/lifestyle-designer/overrides",
        headers=get_headers(),
        json={
            "date": date,
            "life_area": life_area,
            "hours": hours,
            "reason": reason
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        log_test(
            "POST /api/lifestyle-designer/overrides",
            True,
            f"Override saved: {data.get('message')}"
        )
        return True
    else:
        log_test("POST /api/lifestyle-designer/overrides", False, f"Status: {response.status_code}")
        return False

def test_list_overrides():
    """Test GET /api/lifestyle-designer/overrides"""
    print("=" * 80)
    print("TEST 9: List Overrides")
    print("=" * 80)
    
    response = requests.get(
        f"{BACKEND_URL}/lifestyle-designer/overrides",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        log_test(
            "GET /api/lifestyle-designer/overrides",
            True,
            f"Found {len(data)} overrides"
        )
        return data
    else:
        log_test("GET /api/lifestyle-designer/overrides", False, f"Status: {response.status_code}")
        return []

def test_delete_override(date, life_area):
    """Test DELETE /api/lifestyle-designer/overrides/{date}/{life_area}"""
    print(f"Deleting override for {date}, {life_area}")
    
    response = requests.delete(
        f"{BACKEND_URL}/lifestyle-designer/overrides/{date}/{life_area}",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        log_test(
            f"DELETE /api/lifestyle-designer/overrides/{date}/{life_area}",
            True,
            f"Deleted: {data.get('deleted')}"
        )
        return True
    else:
        log_test(f"DELETE /api/lifestyle-designer/overrides/{date}/{life_area}", False, f"Status: {response.status_code}")
        return False

def test_lifestyle_dashboard():
    """Test GET /api/lifestyle-designer/dashboard"""
    print("=" * 80)
    print("TEST 10: Lifestyle Designer Dashboard")
    print("=" * 80)
    
    response = requests.get(
        f"{BACKEND_URL}/lifestyle-designer/dashboard",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        log_test(
            "GET /api/lifestyle-designer/dashboard",
            True,
            f"Total plans: {data.get('total_plans')}, Active plan: {data.get('active_plan')}"
        )
        return data
    else:
        log_test("GET /api/lifestyle-designer/dashboard", False, f"Status: {response.status_code}")
        return None

def test_delete_lifestyle_plan(plan_id):
    """Test DELETE /api/lifestyle-designer/plans/{plan_id}"""
    print(f"Deleting lifestyle plan: {plan_id}")
    
    response = requests.delete(
        f"{BACKEND_URL}/lifestyle-designer/plans/{plan_id}",
        headers=get_headers()
    )
    
    if response.status_code == 200:
        data = response.json()
        log_test(
            f"DELETE /api/lifestyle-designer/plans/{plan_id}",
            True,
            f"Deleted: {data.get('deleted')}"
        )
        return True
    else:
        log_test(f"DELETE /api/lifestyle-designer/plans/{plan_id}", False, f"Status: {response.status_code}")
        return False

# ═══════════════════════════════════════════════════════════════
# MAIN TEST EXECUTION
# ═══════════════════════════════════════════════════════════════

def run_all_tests():
    """Run all PNA and Lifestyle Designer tests"""
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 15 + "PNA FRAMEWORK & LIFESTYLE DESIGNER API TESTS" + " " * 19 + "║")
    print("╚" + "═" * 78 + "╝")
    print("\n")
    
    # Step 1: Register and login
    if not register_user():
        print("❌ Failed to register user. Aborting tests.")
        return
    
    if not login_user():
        print("❌ Failed to login. Aborting tests.")
        return
    
    # ═══════════════════════════════════════════════════════════════
    # PNA FRAMEWORK TESTS
    # ═══════════════════════════════════════════════════════════════
    
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 25 + "PNA FRAMEWORK TESTS" + " " * 34 + "║")
    print("╚" + "═" * 78 + "╝")
    print("\n")
    
    # Test 1: Get PNA meta
    test_pna_meta()
    
    # Test 2: Create PNA items
    print("=" * 80)
    print("TEST 2: Create PNA Items")
    print("=" * 80)
    
    item1_id = test_create_pna_item(
        life_area="finance",
        category="problem",
        title="Debt management",
        priority="high",
        impact_score=8,
        urgency_score=7,
        description="Need to reduce debt"
    )
    
    item2_id = test_create_pna_item(
        life_area="holistic_health",
        category="aspiration",
        title="Run marathon",
        priority="medium",
        impact_score=6,
        urgency_score=5,
        description="Complete a full marathon by end of year"
    )
    
    # Test 3: List items
    test_list_pna_items()
    
    # Test 4: Get single item
    if item1_id:
        test_get_pna_item(item1_id)
    
    # Test 5: Update item
    if item1_id:
        print("=" * 80)
        print("TEST 5: Update PNA Item")
        print("=" * 80)
        test_update_pna_item(item1_id, {"status": "in_progress"})
    
    # Test 6: Dashboard
    test_pna_dashboard()
    
    # Test 7: Area detail
    print("=" * 80)
    print("TEST 7: PNA Area Detail")
    print("=" * 80)
    test_pna_area_detail("finance")
    
    # Test 8: Bulk status update
    if item1_id and item2_id:
        print("=" * 80)
        print("TEST 8: Bulk Status Update")
        print("=" * 80)
        test_bulk_status_update([item1_id, item2_id], "resolved")
    
    # Test 9: Convert to decision
    if item1_id:
        print("=" * 80)
        print("TEST 9: Convert PNA Item to Decision")
        print("=" * 80)
        test_convert_to_decision(item1_id)
    
    # Test 10: Convert to goal
    if item2_id:
        print("=" * 80)
        print("TEST 10: Convert PNA Item to Goal")
        print("=" * 80)
        test_convert_to_goal(item2_id)
    
    # Test 11: Delete item (create a new one first)
    print("=" * 80)
    print("TEST 11: Delete PNA Item")
    print("=" * 80)
    item3_id = test_create_pna_item(
        life_area="career",
        category="need",
        title="Skill upgrade",
        priority="medium",
        description="Learn new programming language"
    )
    if item3_id:
        test_delete_pna_item(item3_id)
    
    # ═══════════════════════════════════════════════════════════════
    # LIFESTYLE DESIGNER TESTS
    # ═══════════════════════════════════════════════════════════════
    
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 22 + "LIFESTYLE DESIGNER TESTS" + " " * 32 + "║")
    print("╚" + "═" * 78 + "╝")
    print("\n")
    
    # Test 12: Get Lifestyle meta
    test_lifestyle_meta()
    
    # Test 13: Create lifestyle plan
    print("=" * 80)
    print("TEST 13: Create Lifestyle Plans")
    print("=" * 80)
    
    # Create first plan with allocations
    allocations1 = {
        "weekday": {
            "career": {"hours": 8, "priority": "high", "notes": "Work hours"},
            "holistic_health": {"hours": 2, "priority": "high", "notes": "Exercise and meditation"},
            "relationships": {"hours": 2, "priority": "medium", "notes": "Family time"},
            "finance": {"hours": 1, "priority": "medium", "notes": "Financial planning"}
        },
        "saturday": {
            "holistic_health": {"hours": 3, "priority": "high", "notes": ""},
            "relationships": {"hours": 4, "priority": "high", "notes": ""},
            "personal_dreams": {"hours": 3, "priority": "medium", "notes": ""}
        },
        "sunday": {
            "spirituality": {"hours": 2, "priority": "high", "notes": ""},
            "relationships": {"hours": 4, "priority": "high", "notes": ""},
            "holistic_health": {"hours": 2, "priority": "medium", "notes": ""}
        }
    }
    
    plan1_id = test_create_lifestyle_plan("My Ideal Day", allocations1, is_active=True)
    
    # Test 14: List plans
    test_list_lifestyle_plans()
    
    # Test 15: Get active plan
    test_get_active_plan()
    
    # Test 16: Update plan
    if plan1_id:
        print("=" * 80)
        print("TEST 16: Update Lifestyle Plan")
        print("=" * 80)
        test_update_lifestyle_plan(plan1_id, {"name": "My Updated Ideal Day"})
    
    # Test 17: Create second plan
    print("=" * 80)
    print("TEST 17: Create Second Plan")
    print("=" * 80)
    
    allocations2 = {
        "weekday": {
            "career": {"hours": 6, "priority": "medium", "notes": ""},
            "holistic_health": {"hours": 3, "priority": "high", "notes": ""},
            "relationships": {"hours": 3, "priority": "high", "notes": ""}
        },
        "saturday": {
            "personal_dreams": {"hours": 5, "priority": "high", "notes": ""},
            "relationships": {"hours": 3, "priority": "high", "notes": ""}
        },
        "sunday": {
            "spirituality": {"hours": 3, "priority": "high", "notes": ""},
            "relationships": {"hours": 5, "priority": "high", "notes": ""}
        }
    }
    
    plan2_id = test_create_lifestyle_plan("Weekend Mode", allocations2, is_active=False)
    
    # Test 18: Activate second plan
    if plan2_id:
        print("=" * 80)
        print("TEST 18: Activate Second Plan")
        print("=" * 80)
        test_activate_plan(plan2_id)
    
    # Test 19: Verify active plan switched
    print("=" * 80)
    print("TEST 19: Verify Active Plan Switched")
    print("=" * 80)
    test_get_active_plan()
    
    # Test 20: Comparison (will work even with no LEE data)
    test_lifestyle_comparison(days=7)
    
    # Test 21: Save manual override
    print("=" * 80)
    print("TEST 21: Save Manual Override")
    print("=" * 80)
    today = datetime.now().strftime("%Y-%m-%d")
    test_save_override(today, "career", 9, "Extra work on project deadline")
    
    # Test 22: List overrides
    test_list_overrides()
    
    # Test 23: Delete override
    print("=" * 80)
    print("TEST 23: Delete Override")
    print("=" * 80)
    test_delete_override(today, "career")
    
    # Test 24: Dashboard
    test_lifestyle_dashboard()
    
    # Test 25: Delete plan
    if plan1_id:
        print("=" * 80)
        print("TEST 25: Delete Lifestyle Plan")
        print("=" * 80)
        test_delete_lifestyle_plan(plan1_id)
    
    # ═══════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════
    
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 30 + "TEST SUMMARY" + " " * 36 + "║")
    print("╚" + "═" * 78 + "╝")
    print("\n")
    print("✅ All PNA Framework and Lifestyle Designer API tests completed!")
    print(f"   Test user: {TEST_EMAIL}")
    print(f"   Backend URL: {BACKEND_URL}")
    print("\n")

if __name__ == "__main__":
    run_all_tests()
