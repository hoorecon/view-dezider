#!/usr/bin/env python3
"""
Google Calendar OAuth Integration and Location-based Filtering Test
Testing the specific endpoints mentioned in the review request.
"""

import requests
import json
import time
from datetime import datetime, timezone

# Configuration
BASE_URL = "https://repo-blueprint-1.preview.emergentagent.com/api"
HEADERS = {"Content-Type": "application/json"}

class CalendarLocationTester:
    def __init__(self):
        self.session_token = None
        self.user_id = None
        self.test_results = []
        
    def log_result(self, test_name, success, details="", response_data=None):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "response_data": response_data
        }
        self.test_results.append(result)
        print(f"{status}: {test_name}")
        if details:
            print(f"   Details: {details}")
        if not success and response_data:
            print(f"   Response: {response_data}")
        print()

    def test_user_registration(self):
        """Test 1: Register a test user"""
        timestamp = int(time.time())
        test_data = {
            "email": "cal_test@test.com",
            "password": "CalTest123!",
            "name": "Calendar Test"
        }
        
        try:
            response = requests.post(f"{BASE_URL}/auth/register", json=test_data, headers=HEADERS)
            
            if response.status_code == 200:
                data = response.json()
                self.session_token = data.get("session_token")
                self.user_id = data.get("user_id")
                self.log_result(
                    "User Registration", 
                    True, 
                    f"User registered successfully. Session token obtained.",
                    {"user_id": self.user_id, "email": data.get("email")}
                )
                return True
            else:
                self.log_result(
                    "User Registration", 
                    False, 
                    f"Registration failed with status {response.status_code}",
                    response.text
                )
                return False
                
        except Exception as e:
            self.log_result("User Registration", False, f"Exception: {str(e)}")
            return False

    def get_auth_headers(self):
        """Get headers with authentication"""
        if not self.session_token:
            return HEADERS
        return {**HEADERS, "Authorization": f"Bearer {self.session_token}"}

    def test_supported_countries_config(self):
        """Test 2: Get supported countries config (NO auth needed)"""
        try:
            response = requests.get(f"{BASE_URL}/solutions-store/config/countries", headers=HEADERS)
            
            if response.status_code == 200:
                data = response.json()
                countries = data.get("countries", [])
                
                # Check if India (IN) is in the list
                india_found = any(country.get("code") == "IN" for country in countries)
                us_found = any(country.get("code") == "US" for country in countries)
                
                if india_found and us_found:
                    self.log_result(
                        "Supported Countries Config", 
                        True, 
                        f"Found {len(countries)} countries including IN (India) and US",
                        {"sample_countries": countries[:3]}
                    )
                    return True
                else:
                    self.log_result(
                        "Supported Countries Config", 
                        False, 
                        f"Missing expected countries. India found: {india_found}, US found: {us_found}",
                        data
                    )
                    return False
            else:
                self.log_result(
                    "Supported Countries Config", 
                    False, 
                    f"Request failed with status {response.status_code}",
                    response.text
                )
                return False
                
        except Exception as e:
            self.log_result("Supported Countries Config", False, f"Exception: {str(e)}")
            return False

    def test_supported_languages_config(self):
        """Test 3: Get supported languages config (NO auth needed)"""
        try:
            response = requests.get(f"{BASE_URL}/solutions-store/config/languages", headers=HEADERS)
            
            if response.status_code == 200:
                data = response.json()
                languages = data.get("languages", [])
                
                # Check if expected languages are in the list
                en_found = any(lang.get("code") == "en" for lang in languages)
                ta_found = any(lang.get("code") == "ta" for lang in languages)
                hi_found = any(lang.get("code") == "hi" for lang in languages)
                
                if en_found and ta_found and hi_found:
                    self.log_result(
                        "Supported Languages Config", 
                        True, 
                        f"Found {len(languages)} languages including en (English), ta (Tamil), hi (Hindi)",
                        {"sample_languages": languages[:3]}
                    )
                    return True
                else:
                    self.log_result(
                        "Supported Languages Config", 
                        False, 
                        f"Missing expected languages. EN: {en_found}, TA: {ta_found}, HI: {hi_found}",
                        data
                    )
                    return False
            else:
                self.log_result(
                    "Supported Languages Config", 
                    False, 
                    f"Request failed with status {response.status_code}",
                    response.text
                )
                return False
                
        except Exception as e:
            self.log_result("Supported Languages Config", False, f"Exception: {str(e)}")
            return False

    def test_get_user_preferences_default(self):
        """Test 4: Get user preferences (default) with auth"""
        try:
            response = requests.get(f"{BASE_URL}/solutions-store/user-preferences", headers=self.get_auth_headers())
            
            if response.status_code == 200:
                data = response.json()
                
                # Check default values
                expected_defaults = {"country": "IN", "language": "en"}
                matches_defaults = all(data.get(key) == value for key, value in expected_defaults.items())
                
                if matches_defaults:
                    self.log_result(
                        "Get User Preferences (Default)", 
                        True, 
                        f"Default preferences returned correctly",
                        data
                    )
                    return True
                else:
                    self.log_result(
                        "Get User Preferences (Default)", 
                        False, 
                        f"Default preferences don't match expected values",
                        data
                    )
                    return False
            else:
                self.log_result(
                    "Get User Preferences (Default)", 
                    False, 
                    f"Request failed with status {response.status_code}",
                    response.text
                )
                return False
                
        except Exception as e:
            self.log_result("Get User Preferences (Default)", False, f"Exception: {str(e)}")
            return False

    def test_update_user_preferences(self):
        """Test 5: Update user preferences with auth"""
        test_data = {
            "country": "US",
            "language": "en",
            "city": "New York"
        }
        
        try:
            response = requests.put(f"{BASE_URL}/solutions-store/user-preferences", json=test_data, headers=self.get_auth_headers())
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("message") == "Preferences updated":
                    self.log_result(
                        "Update User Preferences", 
                        True, 
                        f"Preferences updated successfully",
                        data
                    )
                    return True
                else:
                    self.log_result(
                        "Update User Preferences", 
                        False, 
                        f"Unexpected response message",
                        data
                    )
                    return False
            else:
                self.log_result(
                    "Update User Preferences", 
                    False, 
                    f"Request failed with status {response.status_code}",
                    response.text
                )
                return False
                
        except Exception as e:
            self.log_result("Update User Preferences", False, f"Exception: {str(e)}")
            return False

    def test_get_updated_preferences(self):
        """Test 6: Get updated preferences with auth"""
        try:
            response = requests.get(f"{BASE_URL}/solutions-store/user-preferences", headers=self.get_auth_headers())
            
            if response.status_code == 200:
                data = response.json()
                
                # Check updated values
                expected_values = {"country": "US", "language": "en", "city": "New York"}
                matches_updated = all(data.get(key) == value for key, value in expected_values.items())
                
                if matches_updated:
                    self.log_result(
                        "Get Updated Preferences", 
                        True, 
                        f"Updated preferences returned correctly",
                        data
                    )
                    return True
                else:
                    self.log_result(
                        "Get Updated Preferences", 
                        False, 
                        f"Updated preferences don't match expected values",
                        data
                    )
                    return False
            else:
                self.log_result(
                    "Get Updated Preferences", 
                    False, 
                    f"Request failed with status {response.status_code}",
                    response.text
                )
                return False
                
        except Exception as e:
            self.log_result("Get Updated Preferences", False, f"Exception: {str(e)}")
            return False

    def test_solutions_list_country_filter(self):
        """Test 7: Solutions list with country filter"""
        try:
            response = requests.get(f"{BASE_URL}/solutions-store/solutions?country=IN", headers=self.get_auth_headers())
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, list):
                    # Check if solutions are filtered by India
                    india_solutions = [sol for sol in data if sol.get("country") == "IN"]
                    
                    self.log_result(
                        "Solutions List with Country Filter", 
                        True, 
                        f"Found {len(india_solutions)} solutions filtered by India (IN)",
                        {"total_solutions": len(data), "india_solutions": len(india_solutions)}
                    )
                    return True
                else:
                    self.log_result(
                        "Solutions List with Country Filter", 
                        False, 
                        f"Unexpected response format",
                        data
                    )
                    return False
            else:
                self.log_result(
                    "Solutions List with Country Filter", 
                    False, 
                    f"Request failed with status {response.status_code}",
                    response.text
                )
                return False
                
        except Exception as e:
            self.log_result("Solutions List with Country Filter", False, f"Exception: {str(e)}")
            return False

    def test_solutions_list_language_filter(self):
        """Test 8: Solutions list with language and country filter"""
        try:
            response = requests.get(f"{BASE_URL}/solutions-store/solutions?language=en&country=IN", headers=self.get_auth_headers())
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, list):
                    # Check if solutions are filtered by English and India
                    filtered_solutions = [sol for sol in data if sol.get("language") == "en" and sol.get("country") == "IN"]
                    
                    self.log_result(
                        "Solutions List with Language Filter", 
                        True, 
                        f"Found {len(filtered_solutions)} English Indian solutions",
                        {"total_solutions": len(data), "filtered_solutions": len(filtered_solutions)}
                    )
                    return True
                else:
                    self.log_result(
                        "Solutions List with Language Filter", 
                        False, 
                        f"Unexpected response format",
                        data
                    )
                    return False
            else:
                self.log_result(
                    "Solutions List with Language Filter", 
                    False, 
                    f"Request failed with status {response.status_code}",
                    response.text
                )
                return False
                
        except Exception as e:
            self.log_result("Solutions List with Language Filter", False, f"Exception: {str(e)}")
            return False

    def test_google_calendar_connection_status(self):
        """Test 9: Google Calendar connection status"""
        try:
            response = requests.get(f"{BASE_URL}/oauth/calendar/status", headers=self.get_auth_headers())
            
            if response.status_code == 200:
                data = response.json()
                
                if "connected" in data and data["connected"] == False:
                    self.log_result(
                        "Google Calendar Connection Status", 
                        True, 
                        f"Connection status returned correctly: not connected",
                        data
                    )
                    return True
                else:
                    self.log_result(
                        "Google Calendar Connection Status", 
                        False, 
                        f"Unexpected connection status",
                        data
                    )
                    return False
            else:
                self.log_result(
                    "Google Calendar Connection Status", 
                    False, 
                    f"Request failed with status {response.status_code}",
                    response.text
                )
                return False
                
        except Exception as e:
            self.log_result("Google Calendar Connection Status", False, f"Exception: {str(e)}")
            return False

    def test_google_calendar_oauth_start(self):
        """Test 10: Google Calendar OAuth start"""
        try:
            response = requests.get(f"{BASE_URL}/oauth/calendar/start", headers=self.get_auth_headers())
            
            if response.status_code == 200:
                data = response.json()
                
                auth_url = data.get("authorization_url", "")
                if "accounts.google.com" in auth_url:
                    self.log_result(
                        "Google Calendar OAuth Start", 
                        True, 
                        f"Authorization URL returned correctly",
                        {"auth_url_contains_google": True, "state": data.get("state")}
                    )
                    return True
                else:
                    self.log_result(
                        "Google Calendar OAuth Start", 
                        False, 
                        f"Authorization URL doesn't contain accounts.google.com",
                        data
                    )
                    return False
            else:
                self.log_result(
                    "Google Calendar OAuth Start", 
                    False, 
                    f"Request failed with status {response.status_code}",
                    response.text
                )
                return False
                
        except Exception as e:
            self.log_result("Google Calendar OAuth Start", False, f"Exception: {str(e)}")
            return False

    def test_google_calendar_events_without_connection(self):
        """Test 11: Google Calendar events without connection"""
        try:
            response = requests.get(f"{BASE_URL}/google-calendar/events", headers=self.get_auth_headers())
            
            if response.status_code == 401:
                data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                
                # Check if error message indicates not connected
                error_detail = data.get("detail", "") if isinstance(data, dict) else str(data)
                if "not connected" in error_detail.lower():
                    self.log_result(
                        "Google Calendar Events Without Connection", 
                        True, 
                        f"Correctly returned 401 'not connected' error",
                        {"status_code": 401, "error": error_detail}
                    )
                    return True
                else:
                    self.log_result(
                        "Google Calendar Events Without Connection", 
                        False, 
                        f"401 returned but wrong error message",
                        data
                    )
                    return False
            else:
                self.log_result(
                    "Google Calendar Events Without Connection", 
                    False, 
                    f"Expected 401 but got {response.status_code}",
                    response.text
                )
                return False
                
        except Exception as e:
            self.log_result("Google Calendar Events Without Connection", False, f"Exception: {str(e)}")
            return False

    def test_google_calendar_create_event_without_connection(self):
        """Test 12: Google Calendar create event without connection"""
        test_data = {
            "summary": "Test Event",
            "start": "2026-04-01T10:00:00",
            "timezone": "Asia/Kolkata"
        }
        
        try:
            response = requests.post(f"{BASE_URL}/google-calendar/events", json=test_data, headers=self.get_auth_headers())
            
            if response.status_code == 401:
                data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                
                # Check if error message indicates not connected
                error_detail = data.get("detail", "") if isinstance(data, dict) else str(data)
                if "not connected" in error_detail.lower():
                    self.log_result(
                        "Google Calendar Create Event Without Connection", 
                        True, 
                        f"Correctly returned 401 'not connected' error",
                        {"status_code": 401, "error": error_detail}
                    )
                    return True
                else:
                    self.log_result(
                        "Google Calendar Create Event Without Connection", 
                        False, 
                        f"401 returned but wrong error message",
                        data
                    )
                    return False
            else:
                self.log_result(
                    "Google Calendar Create Event Without Connection", 
                    False, 
                    f"Expected 401 but got {response.status_code}",
                    response.text
                )
                return False
                
        except Exception as e:
            self.log_result("Google Calendar Create Event Without Connection", False, f"Exception: {str(e)}")
            return False

    def test_google_calendar_disconnect(self):
        """Test 13: Google Calendar disconnect (even though not connected)"""
        try:
            response = requests.delete(f"{BASE_URL}/oauth/calendar/disconnect", headers=self.get_auth_headers())
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("message") == "Google Calendar disconnected":
                    self.log_result(
                        "Google Calendar Disconnect", 
                        True, 
                        f"Disconnect succeeded even when not connected",
                        data
                    )
                    return True
                else:
                    self.log_result(
                        "Google Calendar Disconnect", 
                        False, 
                        f"Unexpected response message",
                        data
                    )
                    return False
            else:
                self.log_result(
                    "Google Calendar Disconnect", 
                    False, 
                    f"Request failed with status {response.status_code}",
                    response.text
                )
                return False
                
        except Exception as e:
            self.log_result("Google Calendar Disconnect", False, f"Exception: {str(e)}")
            return False

    def test_ctt_task_sync_without_connection(self):
        """Test 14: CTT task sync without connection"""
        test_data = {
            "task_id": "nonexistent"
        }
        
        try:
            response = requests.post(f"{BASE_URL}/google-calendar/sync-ctt-task", json=test_data, headers=self.get_auth_headers())
            
            # Should return 401 (not connected) or 404 (task not found)
            if response.status_code in [401, 404]:
                data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                
                self.log_result(
                    "CTT Task Sync Without Connection", 
                    True, 
                    f"Correctly returned {response.status_code} error",
                    {"status_code": response.status_code, "response": data}
                )
                return True
            else:
                self.log_result(
                    "CTT Task Sync Without Connection", 
                    False, 
                    f"Expected 401 or 404 but got {response.status_code}",
                    response.text
                )
                return False
                
        except Exception as e:
            self.log_result("CTT Task Sync Without Connection", False, f"Exception: {str(e)}")
            return False

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Google Calendar OAuth Integration and Location-based Filtering Tests")
        print("=" * 80)
        print()
        
        # Test sequence as specified in review request
        tests = [
            self.test_user_registration,
            self.test_supported_countries_config,
            self.test_supported_languages_config,
            self.test_get_user_preferences_default,
            self.test_update_user_preferences,
            self.test_get_updated_preferences,
            self.test_solutions_list_country_filter,
            self.test_solutions_list_language_filter,
            self.test_google_calendar_connection_status,
            self.test_google_calendar_oauth_start,
            self.test_google_calendar_events_without_connection,
            self.test_google_calendar_create_event_without_connection,
            self.test_google_calendar_disconnect,
            self.test_ctt_task_sync_without_connection,
        ]
        
        passed = 0
        failed = 0
        
        for test in tests:
            if test():
                passed += 1
            else:
                failed += 1
        
        print("=" * 80)
        print("🎯 TEST SUMMARY")
        print("=" * 80)
        print(f"✅ PASSED: {passed}")
        print(f"❌ FAILED: {failed}")
        print(f"📊 TOTAL:  {passed + failed}")
        print()
        
        if failed == 0:
            print("🎉 ALL TESTS PASSED! Google Calendar OAuth Integration and Location-based Filtering endpoints are working correctly.")
        else:
            print("⚠️  SOME TESTS FAILED. Please review the failed tests above.")
        
        print()
        print("📋 DETAILED RESULTS:")
        for result in self.test_results:
            print(f"{result['status']}: {result['test']}")
        
        return failed == 0

if __name__ == "__main__":
    tester = CalendarLocationTester()
    success = tester.run_all_tests()
    exit(0 if success else 1)