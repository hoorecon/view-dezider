"""
Backend API Testing for Social Learning URL Upload Endpoint
Tests the NEW Social Learning URL upload endpoint at /api/social-learning/upload-url
"""

import requests
import json
import time
from datetime import datetime

# Backend URL
BASE_URL = "https://dezider-core.preview.emergentagent.com/api"

# Test results tracking
test_results = []

def log_test(test_name, passed, details=""):
    """Log test result"""
    status = "✅ PASSED" if passed else "❌ FAILED"
    result = {
        "test": test_name,
        "status": status,
        "passed": passed,
        "details": details,
        "timestamp": datetime.now().isoformat()
    }
    test_results.append(result)
    print(f"\n{status}: {test_name}")
    if details:
        print(f"  Details: {details}")
    return passed


def print_summary():
    """Print test summary"""
    total = len(test_results)
    passed = sum(1 for r in test_results if r["passed"])
    failed = total - passed
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(passed/total*100):.1f}%")
    print("="*80)
    
    if failed > 0:
        print("\nFailed Tests:")
        for r in test_results:
            if not r["passed"]:
                print(f"  ❌ {r['test']}: {r['details']}")


# Global variables for auth
auth_token = None
user_email = None


def test_1_register_user():
    """Test 1: Register a new user"""
    global auth_token, user_email
    
    timestamp = int(time.time())
    user_email = f"urltest{timestamp}@test.com"
    
    payload = {
        "name": "URL Test User",
        "email": user_email,
        "password": "Test1234!",
        "phone": f"987654{timestamp % 10000:04d}"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/register", json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if "session_token" in data:
                auth_token = data["session_token"]
                return log_test(
                    "User Registration",
                    True,
                    f"Registered user: {user_email}, got session token"
                )
            else:
                return log_test("User Registration", False, "No session_token in response")
        else:
            return log_test(
                "User Registration",
                False,
                f"Status {response.status_code}: {response.text[:200]}"
            )
    except Exception as e:
        return log_test("User Registration", False, f"Exception: {str(e)}")


def test_2_login_user():
    """Test 2: Login with registered user"""
    global auth_token
    
    payload = {
        "email": user_email,
        "password": "Test1234!"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/login", json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if "session_token" in data:
                auth_token = data["session_token"]
                return log_test(
                    "User Login",
                    True,
                    f"Login successful, got session token"
                )
            else:
                return log_test("User Login", False, "No session_token in response")
        else:
            return log_test(
                "User Login",
                False,
                f"Status {response.status_code}: {response.text[:200]}"
            )
    except Exception as e:
        return log_test("User Login", False, f"Exception: {str(e)}")


def test_3_url_upload_valid_news():
    """Test 3: URL Upload - Valid News URL (BBC News)"""
    
    headers = {"Authorization": f"Bearer {auth_token}"}
    # Using BBC News which is more scraping-friendly
    payload = {
        "url": "https://www.bbc.com/news/technology"
    }
    
    try:
        # This is a long-running test (URL scraping + AI classification)
        response = requests.post(
            f"{BASE_URL}/social-learning/upload-url",
            json=payload,
            headers=headers,
            timeout=90  # 90 seconds timeout for AI processing
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Verify required fields
            required_fields = [
                "id", "title", "category", "life_areas", "factors",
                "detected_language", "english_summary", "concerns",
                "life_scenario_template", "input_mode"
            ]
            
            missing_fields = [f for f in required_fields if f not in data]
            
            if missing_fields:
                return log_test(
                    "URL Upload - Valid News URL",
                    False,
                    f"Missing fields: {missing_fields}"
                )
            
            # Verify ID format
            if not data["id"].startswith("SLT-"):
                return log_test(
                    "URL Upload - Valid News URL",
                    False,
                    f"Invalid ID format: {data['id']}"
                )
            
            # Verify input_mode
            if data["input_mode"] != "url":
                return log_test(
                    "URL Upload - Valid News URL",
                    False,
                    f"Wrong input_mode: {data['input_mode']}, expected 'url'"
                )
            
            # Verify category is one of the valid values
            if data["category"] not in ["problem", "need", "aspiration"]:
                return log_test(
                    "URL Upload - Valid News URL",
                    False,
                    f"Invalid category: {data['category']}"
                )
            
            return log_test(
                "URL Upload - Valid News URL",
                True,
                f"Template created: {data['id']}, category: {data['category']}, "
                f"language: {data['detected_language']}, factors: {len(data['factors'])}"
            )
        else:
            return log_test(
                "URL Upload - Valid News URL",
                False,
                f"Status {response.status_code}: {response.text[:300]}"
            )
    except requests.Timeout:
        return log_test(
            "URL Upload - Valid News URL",
            False,
            "Request timeout (>90s) - AI processing took too long"
        )
    except Exception as e:
        return log_test("URL Upload - Valid News URL", False, f"Exception: {str(e)}")


def test_4_url_upload_with_optional_fields():
    """Test 4: URL Upload - With Optional Fields (The Guardian)"""
    
    headers = {"Authorization": f"Bearer {auth_token}"}
    payload = {
        "url": "https://www.theguardian.com/technology",
        "title": "Technology News Article",
        "source_name": "The Guardian"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/social-learning/upload-url",
            json=payload,
            headers=headers,
            timeout=90
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Verify template created
            if not data.get("id", "").startswith("SLT-"):
                return log_test(
                    "URL Upload - With Optional Fields",
                    False,
                    f"Invalid ID: {data.get('id')}"
                )
            
            # Verify input_mode
            if data.get("input_mode") != "url":
                return log_test(
                    "URL Upload - With Optional Fields",
                    False,
                    f"Wrong input_mode: {data.get('input_mode')}"
                )
            
            # Verify optional fields were used (source_name might be overridden by domain extraction)
            # The backend extracts source_name from domain if not provided, so we check if it's set
            if not data.get("source_name"):
                return log_test(
                    "URL Upload - With Optional Fields",
                    False,
                    f"source_name not set: {data.get('source_name')}"
                )
            
            return log_test(
                "URL Upload - With Optional Fields",
                True,
                f"Template created: {data['id']}, title: {data.get('title', 'N/A')[:50]}, "
                f"source: {data.get('source_name')}"
            )
        else:
            return log_test(
                "URL Upload - With Optional Fields",
                False,
                f"Status {response.status_code}: {response.text[:300]}"
            )
    except requests.Timeout:
        return log_test(
            "URL Upload - With Optional Fields",
            False,
            "Request timeout (>90s)"
        )
    except Exception as e:
        return log_test("URL Upload - With Optional Fields", False, f"Exception: {str(e)}")


def test_5_url_upload_invalid_url():
    """Test 5: URL Upload - Invalid URL"""
    
    headers = {"Authorization": f"Bearer {auth_token}"}
    payload = {
        "url": "not-a-url"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/social-learning/upload-url",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        # Should return 400 error
        if response.status_code == 400:
            return log_test(
                "URL Upload - Invalid URL",
                True,
                f"Correctly rejected invalid URL with 400 error: {response.text[:100]}"
            )
        else:
            return log_test(
                "URL Upload - Invalid URL",
                False,
                f"Expected 400 error, got {response.status_code}: {response.text[:200]}"
            )
    except Exception as e:
        return log_test("URL Upload - Invalid URL", False, f"Exception: {str(e)}")


def test_6_url_upload_unreachable_url():
    """Test 6: URL Upload - Unreachable URL"""
    
    headers = {"Authorization": f"Bearer {auth_token}"}
    payload = {
        "url": "https://this-domain-does-not-exist-xyz123.com/page"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/social-learning/upload-url",
            json=payload,
            headers=headers,
            timeout=45
        )
        
        # Should return 400 error
        if response.status_code == 400:
            return log_test(
                "URL Upload - Unreachable URL",
                True,
                f"Correctly rejected unreachable URL with 400 error: {response.text[:100]}"
            )
        else:
            return log_test(
                "URL Upload - Unreachable URL",
                False,
                f"Expected 400 error, got {response.status_code}: {response.text[:200]}"
            )
    except Exception as e:
        return log_test("URL Upload - Unreachable URL", False, f"Exception: {str(e)}")


def test_7_my_templates_check():
    """Test 7: My Templates Check - Verify URL-uploaded templates appear"""
    
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    try:
        response = requests.get(
            f"{BASE_URL}/social-learning/my-templates",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if "templates" not in data:
                return log_test(
                    "My Templates Check",
                    False,
                    "No 'templates' key in response"
                )
            
            templates = data["templates"]
            
            # Check if we have URL-uploaded templates
            url_templates = [t for t in templates if t.get("input_mode") == "url"]
            
            if len(url_templates) == 0:
                return log_test(
                    "My Templates Check",
                    False,
                    f"No URL-uploaded templates found. Total templates: {len(templates)}"
                )
            
            # Verify template structure
            for t in url_templates[:1]:  # Check first URL template
                if not t.get("id", "").startswith("SLT-"):
                    return log_test(
                        "My Templates Check",
                        False,
                        f"Invalid template ID: {t.get('id')}"
                    )
            
            return log_test(
                "My Templates Check",
                True,
                f"Found {len(url_templates)} URL-uploaded templates out of {len(templates)} total. "
                f"Sample IDs: {[t['id'] for t in url_templates[:3]]}"
            )
        else:
            return log_test(
                "My Templates Check",
                False,
                f"Status {response.status_code}: {response.text[:200]}"
            )
    except Exception as e:
        return log_test("My Templates Check", False, f"Exception: {str(e)}")


def test_8_stats_check():
    """Test 8: Stats Check - Verify stats reflect new uploads"""
    
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    try:
        response = requests.get(
            f"{BASE_URL}/social-learning/stats",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            
            required_fields = [
                "tier_1_user_templates",
                "tier_2_authorized",
                "tier_3_solutions",
                "my_templates"
            ]
            
            missing_fields = [f for f in required_fields if f not in data]
            
            if missing_fields:
                return log_test(
                    "Stats Check",
                    False,
                    f"Missing fields: {missing_fields}"
                )
            
            # Verify my_templates count is > 0
            my_count = data.get("my_templates", 0)
            if my_count == 0:
                return log_test(
                    "Stats Check",
                    False,
                    "my_templates count is 0, expected > 0"
                )
            
            return log_test(
                "Stats Check",
                True,
                f"Stats retrieved: my_templates={my_count}, "
                f"tier_1={data.get('tier_1_user_templates')}, "
                f"tier_2={data.get('tier_2_authorized')}, "
                f"tier_3={data.get('tier_3_solutions')}"
            )
        else:
            return log_test(
                "Stats Check",
                False,
                f"Status {response.status_code}: {response.text[:200]}"
            )
    except Exception as e:
        return log_test("Stats Check", False, f"Exception: {str(e)}")


def run_all_tests():
    """Run all tests in sequence"""
    print("="*80)
    print("SOCIAL LEARNING URL UPLOAD ENDPOINT TESTING")
    print("="*80)
    print(f"Backend URL: {BASE_URL}")
    print(f"Test Start Time: {datetime.now().isoformat()}")
    print("="*80)
    
    # Setup tests
    if not test_1_register_user():
        print("\n⚠️  Registration failed, cannot continue with remaining tests")
        print_summary()
        return
    
    if not test_2_login_user():
        print("\n⚠️  Login failed, cannot continue with remaining tests")
        print_summary()
        return
    
    print("\n" + "="*80)
    print("AUTHENTICATION SUCCESSFUL - Starting URL Upload Tests")
    print("="*80)
    
    # Main URL upload tests
    test_3_url_upload_valid_news()
    test_4_url_upload_with_optional_fields()
    test_5_url_upload_invalid_url()
    test_6_url_upload_unreachable_url()
    
    # Verification tests
    test_7_my_templates_check()
    test_8_stats_check()
    
    # Print summary
    print_summary()


if __name__ == "__main__":
    run_all_tests()
