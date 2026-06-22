"""
Backend API Testing for AALA and LEE Endpoints
Tests all AALA (Accrued Assets & Liabilities Analysis) and LEE (Lifestyle Effectiveness Evaluation) functionality
"""

import requests
import json
from datetime import datetime, timedelta

# Backend URL from environment
BASE_URL = "https://goals-feels-tracker.preview.emergentagent.com/api"

# Test credentials - use unique timestamp to avoid conflicts
timestamp = int(datetime.now().timestamp())
TEST_EMAIL = f"aala_lee_test_{timestamp}@test.com"
TEST_PASSWORD = "Test123!"
TEST_NAME = "AALA LEE Tester"

# Global session token
session_token = None
test_assessment_id = None
test_log_date = None


def print_test(test_name, passed, details=""):
    """Print test result with formatting"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status}: {test_name}")
    if details:
        print(f"   {details}")


def test_1_register():
    """Test 1: Register new user"""
    global session_token
    
    url = f"{BASE_URL}/auth/register"
    payload = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "name": TEST_NAME
    }
    
    try:
        response = requests.post(url, json=payload)
        data = response.json()
        
        if response.status_code == 200 and "session_token" in data:
            session_token = data["session_token"]
            print_test("User Registration", True, f"Registered {TEST_EMAIL} with session token")
            return True
        else:
            print_test("User Registration", False, f"Status: {response.status_code}, Response: {data}")
            return False
    except Exception as e:
        print_test("User Registration", False, f"Exception: {str(e)}")
        return False


def test_2_aala_taxonomy():
    """Test 2: GET /api/aala/taxonomy - Should return 10 life areas with subcategories"""
    
    url = f"{BASE_URL}/aala/taxonomy"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if response.status_code != 200:
            print_test("AALA Taxonomy", False, f"Status: {response.status_code}")
            return False
        
        taxonomy = data.get("taxonomy", [])
        
        if len(taxonomy) != 10:
            print_test("AALA Taxonomy", False, f"Expected 10 life areas, got {len(taxonomy)}")
            return False
        
        # Verify specific areas
        holistic_health = next((a for a in taxonomy if a["area_id"] == "holistic_health"), None)
        relationships = next((a for a in taxonomy if a["area_id"] == "relationships"), None)
        
        if not holistic_health or len(holistic_health.get("subcategories", [])) != 3:
            print_test("AALA Taxonomy", False, "Holistic Health should have 3 subcategories")
            return False
        
        if not relationships or len(relationships.get("subcategories", [])) != 12:
            print_test("AALA Taxonomy", False, "Relationships should have 12 subcategories")
            return False
        
        print_test("AALA Taxonomy", True, f"Found 10 life areas. Holistic Health: 3 subcats, Relationships: 12 subcats")
        return True
        
    except Exception as e:
        print_test("AALA Taxonomy", False, f"Exception: {str(e)}")
        return False


def test_3_aala_create_assessment():
    """Test 3: POST /api/aala/assessments - Create baseline assessment with entries"""
    global test_assessment_id
    
    url = f"{BASE_URL}/aala/assessments"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    # Create assessment with entries for 3 life areas
    payload = {
        "title": "Baseline AALA Assessment",
        "is_baseline": True,
        "tracking_frequency": "weekly",
        "entries": [
            {
                "area_id": "holistic_health",
                "subcategory_id": "physical",
                "current_liabilities": "Chronic back pain",
                "accrued_liabilities": "Sedentary lifestyle",
                "current_assets": "Regular gym membership",
                "accrued_assets": "Good cardiovascular health",
                "current_liabilities_value": 500,
                "accrued_liabilities_value": 1000,
                "current_assets_value": 2000,
                "accrued_assets_value": 3000,
                "notes": "Need to focus on posture"
            },
            {
                "area_id": "finance",
                "subcategory_id": "savings",
                "current_liabilities": "Credit card debt",
                "accrued_liabilities": "Student loan",
                "current_assets": "Emergency fund",
                "accrued_assets": "Retirement savings",
                "current_liabilities_value": 5000,
                "accrued_liabilities_value": 20000,
                "current_assets_value": 10000,
                "accrued_assets_value": 50000,
                "notes": "On track with savings goals"
            },
            {
                "area_id": "relationships",
                "subcategory_id": "spouse",
                "current_liabilities": "Communication issues",
                "accrued_liabilities": "Unresolved conflicts",
                "current_assets": "Strong emotional bond",
                "accrued_assets": "Shared life goals",
                "current_liabilities_value": 300,
                "accrued_liabilities_value": 500,
                "current_assets_value": 5000,
                "accrued_assets_value": 8000,
                "notes": "Working on communication"
            }
        ],
        "summary_notes": "Initial baseline assessment for tracking progress"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("AALA Create Assessment", False, f"Status: {response.status_code}, Response: {data}")
            return False
        
        test_assessment_id = data.get("assessment_id")
        
        if not test_assessment_id:
            print_test("AALA Create Assessment", False, "No assessment_id in response")
            return False
        
        # Verify response structure
        if data.get("is_baseline") != True:
            print_test("AALA Create Assessment", False, "is_baseline should be True")
            return False
        
        if len(data.get("entries", [])) != 3:
            print_test("AALA Create Assessment", False, f"Expected 3 entries, got {len(data.get('entries', []))}")
            return False
        
        print_test("AALA Create Assessment", True, f"Created baseline assessment {test_assessment_id} with 3 entries")
        return True
        
    except Exception as e:
        print_test("AALA Create Assessment", False, f"Exception: {str(e)}")
        return False


def test_4_aala_list_assessments():
    """Test 4: GET /api/aala/assessments - List all assessments"""
    
    url = f"{BASE_URL}/aala/assessments"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("AALA List Assessments", False, f"Status: {response.status_code}")
            return False
        
        if not isinstance(data, list):
            print_test("AALA List Assessments", False, "Response should be a list")
            return False
        
        if len(data) < 1:
            print_test("AALA List Assessments", False, "Should have at least 1 assessment")
            return False
        
        # Verify our test assessment is in the list
        found = any(a.get("assessment_id") == test_assessment_id for a in data)
        
        if not found:
            print_test("AALA List Assessments", False, f"Test assessment {test_assessment_id} not found in list")
            return False
        
        print_test("AALA List Assessments", True, f"Found {len(data)} assessments including test assessment")
        return True
        
    except Exception as e:
        print_test("AALA List Assessments", False, f"Exception: {str(e)}")
        return False


def test_5_aala_get_assessment():
    """Test 5: GET /api/aala/assessments/{id} - Get single assessment"""
    
    url = f"{BASE_URL}/aala/assessments/{test_assessment_id}"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("AALA Get Assessment", False, f"Status: {response.status_code}")
            return False
        
        if data.get("assessment_id") != test_assessment_id:
            print_test("AALA Get Assessment", False, "Assessment ID mismatch")
            return False
        
        if len(data.get("entries", [])) != 3:
            print_test("AALA Get Assessment", False, f"Expected 3 entries, got {len(data.get('entries', []))}")
            return False
        
        print_test("AALA Get Assessment", True, f"Retrieved assessment {test_assessment_id} with 3 entries")
        return True
        
    except Exception as e:
        print_test("AALA Get Assessment", False, f"Exception: {str(e)}")
        return False


def test_6_aala_update_assessment():
    """Test 6: PUT /api/aala/assessments/{id} - Update assessment"""
    
    url = f"{BASE_URL}/aala/assessments/{test_assessment_id}"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    # Add one more entry and change title
    payload = {
        "title": "Updated Baseline Assessment",
        "entries": [
            {
                "area_id": "holistic_health",
                "subcategory_id": "physical",
                "current_liabilities": "Chronic back pain",
                "accrued_liabilities": "Sedentary lifestyle",
                "current_assets": "Regular gym membership",
                "accrued_assets": "Good cardiovascular health",
                "current_liabilities_value": 500,
                "accrued_liabilities_value": 1000,
                "current_assets_value": 2000,
                "accrued_assets_value": 3000
            },
            {
                "area_id": "finance",
                "subcategory_id": "savings",
                "current_liabilities": "Credit card debt",
                "accrued_liabilities": "Student loan",
                "current_assets": "Emergency fund",
                "accrued_assets": "Retirement savings",
                "current_liabilities_value": 5000,
                "accrued_liabilities_value": 20000,
                "current_assets_value": 10000,
                "accrued_assets_value": 50000
            },
            {
                "area_id": "relationships",
                "subcategory_id": "spouse",
                "current_liabilities": "Communication issues",
                "accrued_liabilities": "Unresolved conflicts",
                "current_assets": "Strong emotional bond",
                "accrued_assets": "Shared life goals",
                "current_liabilities_value": 300,
                "accrued_liabilities_value": 500,
                "current_assets_value": 5000,
                "accrued_assets_value": 8000
            },
            {
                "area_id": "career",
                "subcategory_id": "job",
                "current_liabilities": "Job insecurity",
                "accrued_liabilities": "Skill gaps",
                "current_assets": "Strong network",
                "accrued_assets": "Industry experience",
                "current_liabilities_value": 1000,
                "accrued_liabilities_value": 2000,
                "current_assets_value": 8000,
                "accrued_assets_value": 15000
            }
        ]
    }
    
    try:
        response = requests.put(url, json=payload, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("AALA Update Assessment", False, f"Status: {response.status_code}, Response: {data}")
            return False
        
        if data.get("title") != "Updated Baseline Assessment":
            print_test("AALA Update Assessment", False, "Title not updated")
            return False
        
        if len(data.get("entries", [])) != 4:
            print_test("AALA Update Assessment", False, f"Expected 4 entries, got {len(data.get('entries', []))}")
            return False
        
        print_test("AALA Update Assessment", True, f"Updated assessment with new title and 4 entries")
        return True
        
    except Exception as e:
        print_test("AALA Update Assessment", False, f"Exception: {str(e)}")
        return False


def test_7_aala_dashboard():
    """Test 7: GET /api/aala/dashboard - Should return total_assessments, baseline, latest, net_position_by_area"""
    
    url = f"{BASE_URL}/aala/dashboard"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("AALA Dashboard", False, f"Status: {response.status_code}")
            return False
        
        # Verify required fields
        required_fields = ["total_assessments", "baseline", "latest", "net_position_by_area"]
        missing_fields = [f for f in required_fields if f not in data]
        
        if missing_fields:
            print_test("AALA Dashboard", False, f"Missing fields: {missing_fields}")
            return False
        
        if data.get("total_assessments") < 1:
            print_test("AALA Dashboard", False, "Should have at least 1 assessment")
            return False
        
        # Verify net_position_by_area structure
        net_by_area = data.get("net_position_by_area", {})
        
        if not net_by_area:
            print_test("AALA Dashboard", False, "net_position_by_area should not be empty")
            return False
        
        # Check if areas have proper structure
        for area_id, area_data in net_by_area.items():
            if not all(k in area_data for k in ["total_assets", "total_liabilities", "net"]):
                print_test("AALA Dashboard", False, f"Area {area_id} missing required fields")
                return False
        
        print_test("AALA Dashboard", True, f"Dashboard: {data['total_assessments']} assessments, {len(net_by_area)} areas with net position")
        return True
        
    except Exception as e:
        print_test("AALA Dashboard", False, f"Exception: {str(e)}")
        return False


def test_8_aala_for_solution_matrix():
    """Test 8: GET /api/aala/for-solution-matrix - Should return has_data=true, resources_summary, matrix_fields"""
    
    url = f"{BASE_URL}/aala/for-solution-matrix"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("AALA For Solution Matrix", False, f"Status: {response.status_code}")
            return False
        
        if data.get("has_data") != True:
            print_test("AALA For Solution Matrix", False, "has_data should be True")
            return False
        
        # Verify matrix_fields structure
        matrix_fields = data.get("matrix_fields", {})
        required_matrix_fields = ["finance", "people", "infrastructure", "knowledge_skills"]
        
        missing = [f for f in required_matrix_fields if f not in matrix_fields]
        
        if missing:
            print_test("AALA For Solution Matrix", False, f"Missing matrix fields: {missing}")
            return False
        
        # Verify resources_summary is present
        if "resources_summary" not in data:
            print_test("AALA For Solution Matrix", False, "Missing resources_summary")
            return False
        
        print_test("AALA For Solution Matrix", True, f"Solution matrix data ready with all 4 fields (finance, people, infrastructure, knowledge_skills)")
        return True
        
    except Exception as e:
        print_test("AALA For Solution Matrix", False, f"Exception: {str(e)}")
        return False


def test_9_aala_trends():
    """Test 9: GET /api/aala/trends - Should return historical trend data with net_position"""
    
    url = f"{BASE_URL}/aala/trends"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("AALA Trends", False, f"Status: {response.status_code}")
            return False
        
        trends = data.get("trends", [])
        
        if len(trends) < 1:
            print_test("AALA Trends", False, "Should have at least 1 trend data point")
            return False
        
        # Verify trend structure
        first_trend = trends[0]
        required_fields = ["date", "assessment_id", "total_assets", "total_liabilities", "net_position"]
        missing = [f for f in required_fields if f not in first_trend]
        
        if missing:
            print_test("AALA Trends", False, f"Missing trend fields: {missing}")
            return False
        
        print_test("AALA Trends", True, f"Found {len(trends)} trend data points with net_position calculations")
        return True
        
    except Exception as e:
        print_test("AALA Trends", False, f"Exception: {str(e)}")
        return False


def test_10_aala_delete_assessment():
    """Test 10: DELETE /api/aala/assessments/{id} - Delete assessment"""
    
    url = f"{BASE_URL}/aala/assessments/{test_assessment_id}"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.delete(url, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("AALA Delete Assessment", False, f"Status: {response.status_code}")
            return False
        
        if data.get("deleted") != True:
            print_test("AALA Delete Assessment", False, "deleted should be True")
            return False
        
        # Verify it's actually deleted
        get_response = requests.get(url, headers=headers)
        
        if get_response.status_code != 404:
            print_test("AALA Delete Assessment", False, "Assessment should return 404 after deletion")
            return False
        
        print_test("AALA Delete Assessment", True, f"Successfully deleted assessment {test_assessment_id}")
        return True
        
    except Exception as e:
        print_test("AALA Delete Assessment", False, f"Exception: {str(e)}")
        return False


# ============================================================================
# LEE (Lifestyle Effectiveness Evaluation) Tests
# ============================================================================

def test_11_lee_meta():
    """Test 11: GET /api/lifestyle-eval/meta - Should return 10 life_areas and 3 categories"""
    
    url = f"{BASE_URL}/lifestyle-eval/meta"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if response.status_code != 200:
            print_test("LEE Meta", False, f"Status: {response.status_code}")
            return False
        
        life_areas = data.get("life_areas", [])
        categories = data.get("categories", [])
        
        if len(life_areas) != 10:
            print_test("LEE Meta", False, f"Expected 10 life areas, got {len(life_areas)}")
            return False
        
        if len(categories) != 3:
            print_test("LEE Meta", False, f"Expected 3 categories, got {len(categories)}")
            return False
        
        # Verify category IDs
        category_ids = [c.get("id") for c in categories]
        expected_ids = ["problem", "need", "aspiration"]
        
        if set(category_ids) != set(expected_ids):
            print_test("LEE Meta", False, f"Expected categories {expected_ids}, got {category_ids}")
            return False
        
        print_test("LEE Meta", True, f"Found 10 life areas and 3 categories (problem/need/aspiration)")
        return True
        
    except Exception as e:
        print_test("LEE Meta", False, f"Exception: {str(e)}")
        return False


def test_12_lee_create_log():
    """Test 12: POST /api/lifestyle-eval/logs - Create daily log with 3+ activities, verify auto-duration"""
    global test_log_date
    
    url = f"{BASE_URL}/lifestyle-eval/logs"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    test_log_date = datetime.now().strftime("%Y-%m-%d")
    
    payload = {
        "date": test_log_date,
        "activities": [
            {
                "from_time": "06:00",
                "to_time": "07:30",
                "activity": "Morning exercise and meditation",
                "area_of_life": "holistic_health",
                "category": "aspiration"
            },
            {
                "from_time": "09:00",
                "to_time": "12:00",
                "activity": "Deep work on project",
                "area_of_life": "career",
                "category": "need"
            },
            {
                "from_time": "14:00",
                "to_time": "15:30",
                "activity": "Team meeting and collaboration",
                "area_of_life": "career",
                "category": "need"
            },
            {
                "from_time": "19:00",
                "to_time": "20:00",
                "activity": "Family dinner",
                "area_of_life": "relationships",
                "category": "aspiration"
            }
        ],
        "remarks": "Productive day with good balance"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("LEE Create Log", False, f"Status: {response.status_code}, Response: {data}")
            return False
        
        activities = data.get("activities", [])
        
        if len(activities) != 4:
            print_test("LEE Create Log", False, f"Expected 4 activities, got {len(activities)}")
            return False
        
        # Verify auto-duration calculation
        # First activity: 06:00 to 07:30 = 90 minutes
        first_activity = activities[0]
        if first_activity.get("duration_minutes") != 90:
            print_test("LEE Create Log", False, f"Expected duration 90 minutes, got {first_activity.get('duration_minutes')}")
            return False
        
        # Second activity: 09:00 to 12:00 = 180 minutes
        second_activity = activities[1]
        if second_activity.get("duration_minutes") != 180:
            print_test("LEE Create Log", False, f"Expected duration 180 minutes, got {second_activity.get('duration_minutes')}")
            return False
        
        # Verify day_type auto-detection
        day_type = data.get("day_type")
        if day_type not in ["weekday", "saturday", "sunday"]:
            print_test("LEE Create Log", False, f"Invalid day_type: {day_type}")
            return False
        
        print_test("LEE Create Log", True, f"Created log with 4 activities. Auto-duration working (90min, 180min verified). Day type: {day_type}")
        return True
        
    except Exception as e:
        print_test("LEE Create Log", False, f"Exception: {str(e)}")
        return False


def test_13_lee_get_log():
    """Test 13: GET /api/lifestyle-eval/logs/{date} - Get log for specific date, verify exists=true"""
    
    url = f"{BASE_URL}/lifestyle-eval/logs/{test_log_date}"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("LEE Get Log", False, f"Status: {response.status_code}")
            return False
        
        if data.get("exists") != True:
            print_test("LEE Get Log", False, "exists should be True")
            return False
        
        if data.get("date") != test_log_date:
            print_test("LEE Get Log", False, f"Date mismatch: expected {test_log_date}, got {data.get('date')}")
            return False
        
        activities = data.get("activities", [])
        
        if len(activities) != 4:
            print_test("LEE Get Log", False, f"Expected 4 activities, got {len(activities)}")
            return False
        
        print_test("LEE Get Log", True, f"Retrieved log for {test_log_date} with exists=true and 4 activities")
        return True
        
    except Exception as e:
        print_test("LEE Get Log", False, f"Exception: {str(e)}")
        return False


def test_14_lee_list_logs():
    """Test 14: GET /api/lifestyle-eval/logs - List all logs"""
    
    url = f"{BASE_URL}/lifestyle-eval/logs"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("LEE List Logs", False, f"Status: {response.status_code}")
            return False
        
        if not isinstance(data, list):
            print_test("LEE List Logs", False, "Response should be a list")
            return False
        
        if len(data) < 1:
            print_test("LEE List Logs", False, "Should have at least 1 log")
            return False
        
        # Verify our test log is in the list
        found = any(log.get("date") == test_log_date for log in data)
        
        if not found:
            print_test("LEE List Logs", False, f"Test log for {test_log_date} not found in list")
            return False
        
        print_test("LEE List Logs", True, f"Found {len(data)} logs including test log")
        return True
        
    except Exception as e:
        print_test("LEE List Logs", False, f"Exception: {str(e)}")
        return False


def test_15_lee_summary():
    """Test 15: GET /api/lifestyle-eval/summary - Should return aggregated avg_minutes per area per day_type"""
    
    url = f"{BASE_URL}/lifestyle-eval/summary"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("LEE Summary", False, f"Status: {response.status_code}")
            return False
        
        summary = data.get("summary", {})
        day_counts = data.get("day_counts", {})
        
        if not summary:
            print_test("LEE Summary", False, "Summary should not be empty")
            return False
        
        # Verify structure - should have day_type keys
        valid_day_types = ["weekday", "saturday", "sunday"]
        
        # At least one day type should be present
        has_day_type = any(dt in summary for dt in valid_day_types)
        
        if not has_day_type:
            print_test("LEE Summary", False, f"Summary should have at least one day_type from {valid_day_types}")
            return False
        
        # Verify area data structure
        for day_type, areas in summary.items():
            for area_id, area_data in areas.items():
                required_fields = ["avg_minutes", "total_minutes", "activity_count", "days_tracked"]
                missing = [f for f in required_fields if f not in area_data]
                
                if missing:
                    print_test("LEE Summary", False, f"Missing fields in {day_type}/{area_id}: {missing}")
                    return False
        
        print_test("LEE Summary", True, f"Summary aggregated by day_type with avg_minutes per area. Day counts: {day_counts}")
        return True
        
    except Exception as e:
        print_test("LEE Summary", False, f"Exception: {str(e)}")
        return False


def test_16_lee_planned_vs_actual():
    """Test 16: GET /api/lifestyle-eval/planned-vs-actual?date=YYYY-MM-DD - Should return comparison with actual_minutes, gap status"""
    
    url = f"{BASE_URL}/lifestyle-eval/planned-vs-actual?date={test_log_date}"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("LEE Planned vs Actual", False, f"Status: {response.status_code}")
            return False
        
        if data.get("date") != test_log_date:
            print_test("LEE Planned vs Actual", False, f"Date mismatch: expected {test_log_date}, got {data.get('date')}")
            return False
        
        comparison = data.get("comparison", [])
        
        if not isinstance(comparison, list):
            print_test("LEE Planned vs Actual", False, "comparison should be a list")
            return False
        
        # Verify comparison structure
        for item in comparison:
            required_fields = ["area_id", "area_name", "actual_minutes", "has_planned", "has_actual", "gap"]
            missing = [f for f in required_fields if f not in item]
            
            if missing:
                print_test("LEE Planned vs Actual", False, f"Missing fields in comparison: {missing}")
                return False
            
            # Verify gap values
            gap = item.get("gap")
            if gap not in ["covered", "missed", "unplanned", "none"]:
                print_test("LEE Planned vs Actual", False, f"Invalid gap value: {gap}")
                return False
        
        total_actual = data.get("total_actual_minutes", 0)
        
        print_test("LEE Planned vs Actual", True, f"Comparison for {test_log_date}: {len(comparison)} areas, {total_actual} total actual minutes, gap status working")
        return True
        
    except Exception as e:
        print_test("LEE Planned vs Actual", False, f"Exception: {str(e)}")
        return False


def test_17_lee_dashboard():
    """Test 17: GET /api/lifestyle-eval/dashboard - Should return total_logs, week_stats, top_areas"""
    
    url = f"{BASE_URL}/lifestyle-eval/dashboard"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("LEE Dashboard", False, f"Status: {response.status_code}")
            return False
        
        # Verify required fields
        required_fields = ["total_logs", "recent_logs", "week_stats", "top_areas"]
        missing = [f for f in required_fields if f not in data]
        
        if missing:
            print_test("LEE Dashboard", False, f"Missing fields: {missing}")
            return False
        
        if data.get("total_logs") < 1:
            print_test("LEE Dashboard", False, "Should have at least 1 log")
            return False
        
        # Verify week_stats structure
        week_stats = data.get("week_stats", {})
        required_stats = ["total_activities", "total_minutes", "total_hours", "areas_covered"]
        missing_stats = [f for f in required_stats if f not in week_stats]
        
        if missing_stats:
            print_test("LEE Dashboard", False, f"Missing week_stats fields: {missing_stats}")
            return False
        
        # Verify top_areas structure
        top_areas = data.get("top_areas", [])
        
        if top_areas:
            first_area = top_areas[0]
            if not all(k in first_area for k in ["area_id", "area_name", "minutes"]):
                print_test("LEE Dashboard", False, "top_areas missing required fields")
                return False
        
        print_test("LEE Dashboard", True, f"Dashboard: {data['total_logs']} logs, {week_stats['total_activities']} activities, {len(top_areas)} top areas")
        return True
        
    except Exception as e:
        print_test("LEE Dashboard", False, f"Exception: {str(e)}")
        return False


def test_18_lee_delete_log():
    """Test 18: DELETE /api/lifestyle-eval/logs/{date} - Delete a daily log"""
    
    url = f"{BASE_URL}/lifestyle-eval/logs/{test_log_date}"
    headers = {"Authorization": f"Bearer {session_token}"}
    
    try:
        response = requests.delete(url, headers=headers)
        data = response.json()
        
        if response.status_code != 200:
            print_test("LEE Delete Log", False, f"Status: {response.status_code}")
            return False
        
        if data.get("deleted") != True:
            print_test("LEE Delete Log", False, "deleted should be True")
            return False
        
        # Verify it's actually deleted
        get_response = requests.get(url, headers=headers)
        get_data = get_response.json()
        
        if get_data.get("exists") != False:
            print_test("LEE Delete Log", False, "Log should have exists=false after deletion")
            return False
        
        print_test("LEE Delete Log", True, f"Successfully deleted log for {test_log_date}")
        return True
        
    except Exception as e:
        print_test("LEE Delete Log", False, f"Exception: {str(e)}")
        return False


def run_all_tests():
    """Run all AALA and LEE tests"""
    print("=" * 80)
    print("AALA & LEE ENDPOINTS COMPREHENSIVE TESTING")
    print("=" * 80)
    print(f"Backend URL: {BASE_URL}")
    print(f"Test User: {TEST_EMAIL}")
    print("=" * 80)
    
    results = []
    
    # Test 1: Authentication
    results.append(("Authentication", test_1_register()))
    
    if not session_token:
        print("\n❌ CRITICAL: Authentication failed. Cannot proceed with other tests.")
        return False
    
    print("\n" + "=" * 80)
    print("PHASE 1: AALA TESTS")
    print("=" * 80)
    
    # AALA Tests
    results.append(("AALA Taxonomy", test_2_aala_taxonomy()))
    results.append(("AALA Create Assessment", test_3_aala_create_assessment()))
    results.append(("AALA List Assessments", test_4_aala_list_assessments()))
    results.append(("AALA Get Assessment", test_5_aala_get_assessment()))
    results.append(("AALA Update Assessment", test_6_aala_update_assessment()))
    results.append(("AALA Dashboard", test_7_aala_dashboard()))
    results.append(("AALA For Solution Matrix", test_8_aala_for_solution_matrix()))
    results.append(("AALA Trends", test_9_aala_trends()))
    results.append(("AALA Delete Assessment", test_10_aala_delete_assessment()))
    
    print("\n" + "=" * 80)
    print("PHASE 2: LEE TESTS")
    print("=" * 80)
    
    # LEE Tests
    results.append(("LEE Meta", test_11_lee_meta()))
    results.append(("LEE Create Log", test_12_lee_create_log()))
    results.append(("LEE Get Log", test_13_lee_get_log()))
    results.append(("LEE List Logs", test_14_lee_list_logs()))
    results.append(("LEE Summary", test_15_lee_summary()))
    results.append(("LEE Planned vs Actual", test_16_lee_planned_vs_actual()))
    results.append(("LEE Dashboard", test_17_lee_dashboard()))
    results.append(("LEE Delete Log", test_18_lee_delete_log()))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("=" * 80)
    print(f"TOTAL: {passed}/{total} tests passed ({round(passed/total*100, 1)}%)")
    print("=" * 80)
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
