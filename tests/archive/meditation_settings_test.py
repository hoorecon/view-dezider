#!/usr/bin/env python3
"""
Backend API Testing Script for Meditation Settings
Tests all meditation settings endpoints with proper authentication flow
"""

import requests
import json
import time
from datetime import datetime

# Backend URL from environment
BACKEND_URL = "https://repo-blueprint-1.preview.emergentagent.com/api"

# Test results tracking
test_results = []

def log_test(test_name, passed, details=""):
    """Log test result"""
    status = "✅ PASSED" if passed else "❌ FAILED"
    result = f"{status}: {test_name}"
    if details:
        result += f" - {details}"
    test_results.append(result)
    print(result)
    return passed

def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    passed = sum(1 for r in test_results if "✅ PASSED" in r)
    failed = sum(1 for r in test_results if "❌ FAILED" in r)
    print(f"Total: {len(test_results)} | Passed: {passed} | Failed: {failed}")
    print("="*80)
    for result in test_results:
        print(result)
    print("="*80)

# ═══════════════════════════════════════════════════════════════
# MEDITATION SETTINGS TESTS
# ═══════════════════════════════════════════════════════════════

def test_meditation_settings():
    """Test Meditation Settings API endpoints"""
    print("\n" + "="*80)
    print("MEDITATION SETTINGS API TESTING")
    print("="*80)
    
    # Step 1: Register a test user
    timestamp = int(time.time())
    test_email = f"medtest_{timestamp}@meditation.com"
    test_password = "MeditationTest123!"
    test_name = "Meditation Test User"
    
    print(f"\n[1] Registering test user: {test_email}")
    register_response = requests.post(
        f"{BACKEND_URL}/auth/register",
        json={
            "email": test_email,
            "password": test_password,
            "name": test_name
        }
    )
    
    if register_response.status_code != 200:
        log_test("User Registration", False, f"Status: {register_response.status_code}, Response: {register_response.text}")
        return
    
    register_data = register_response.json()
    session_token = register_data.get("session_token")
    
    if not session_token:
        log_test("User Registration", False, "No session_token in response")
        return
    
    log_test("User Registration", True, f"User created with session token")
    
    headers = {"Authorization": f"Bearer {session_token}"}
    
    # Step 2: Test GET /api/meditation-settings/defaults
    print("\n[2] Testing GET /api/meditation-settings/defaults")
    defaults_response = requests.get(f"{BACKEND_URL}/meditation-settings/defaults")
    
    if defaults_response.status_code != 200:
        log_test("GET /meditation-settings/defaults", False, f"Status: {defaults_response.status_code}")
        return
    
    defaults_data = defaults_response.json()
    meditations = defaults_data.get("meditations", [])
    
    # Verify 3 meditation slots
    if len(meditations) != 3:
        log_test("GET /meditation-settings/defaults", False, f"Expected 3 meditations, got {len(meditations)}")
        return
    
    # Verify meditation IDs
    meditation_ids = [m.get("id") for m in meditations]
    expected_ids = ["guru_invocation", "stillness_meditation", "goal_manifestation"]
    
    if set(meditation_ids) != set(expected_ids):
        log_test("GET /meditation-settings/defaults", False, f"Expected IDs {expected_ids}, got {meditation_ids}")
        return
    
    # Verify default URLs
    guru_med = next((m for m in meditations if m["id"] == "guru_invocation"), None)
    stillness_med = next((m for m in meditations if m["id"] == "stillness_meditation"), None)
    goal_med = next((m for m in meditations if m["id"] == "goal_manifestation"), None)
    
    if not guru_med or "isha.sadhguru.org" not in guru_med.get("default_url", ""):
        log_test("GET /meditation-settings/defaults", False, "guru_invocation default URL incorrect")
        return
    
    if not stillness_med or "youtube.com" not in stillness_med.get("default_url", ""):
        log_test("GET /meditation-settings/defaults", False, "stillness_meditation default URL incorrect")
        return
    
    if not goal_med or "KalphaVriksha" not in goal_med.get("default_url", ""):
        log_test("GET /meditation-settings/defaults", False, "goal_manifestation default URL incorrect")
        return
    
    log_test("GET /meditation-settings/defaults", True, 
             f"Returns 3 meditation slots with correct default URLs: Isha Sadhguru (guru_invocation), YouTube (stillness), KalphaVriksha MP3 (goal_manifestation)")
    
    # Step 3: Test GET /api/meditation-settings/preferences (initial - should return defaults)
    print("\n[3] Testing GET /api/meditation-settings/preferences (initial state)")
    prefs_response = requests.get(f"{BACKEND_URL}/meditation-settings/preferences", headers=headers)
    
    if prefs_response.status_code != 200:
        log_test("GET /meditation-settings/preferences (initial)", False, f"Status: {prefs_response.status_code}")
        return
    
    prefs_data = prefs_response.json()
    prefs_meditations = prefs_data.get("meditations", {})
    
    # Verify all 3 slots present
    if len(prefs_meditations) != 3:
        log_test("GET /meditation-settings/preferences (initial)", False, f"Expected 3 slots, got {len(prefs_meditations)}")
        return
    
    # Verify all are default initially
    for med_id in expected_ids:
        if med_id not in prefs_meditations:
            log_test("GET /meditation-settings/preferences (initial)", False, f"Missing {med_id}")
            return
        
        med = prefs_meditations[med_id]
        if med.get("source_type") != "default":
            log_test("GET /meditation-settings/preferences (initial)", False, f"{med_id} source_type should be 'default', got '{med.get('source_type')}'")
            return
        
        if not med.get("resolved_url"):
            log_test("GET /meditation-settings/preferences (initial)", False, f"{med_id} missing resolved_url")
            return
    
    log_test("GET /meditation-settings/preferences (initial)", True, 
             "Returns resolved URLs for all 3 slots (defaults initially)")
    
    # Step 4: Test PUT /api/meditation-settings/preferences (set custom URL for guru_invocation)
    print("\n[4] Testing PUT /api/meditation-settings/preferences (set custom URL for guru_invocation)")
    custom_guru_url = "https://example.com/my-guru-invocation.mp3"
    
    update_response = requests.put(
        f"{BACKEND_URL}/meditation-settings/preferences",
        headers=headers,
        json={
            "meditation_id": "guru_invocation",
            "source_type": "custom_url",
            "custom_url": custom_guru_url
        }
    )
    
    if update_response.status_code != 200:
        log_test("PUT /meditation-settings/preferences (guru_invocation)", False, 
                f"Status: {update_response.status_code}, Response: {update_response.text}")
        return
    
    update_data = update_response.json()
    if not update_data.get("updated"):
        log_test("PUT /meditation-settings/preferences (guru_invocation)", False, "updated field not True")
        return
    
    log_test("PUT /meditation-settings/preferences (guru_invocation)", True, 
             f"Set custom URL for guru_invocation: {custom_guru_url}")
    
    # Step 5: Test GET /api/meditation-settings/preferences (verify guru_invocation custom URL)
    print("\n[5] Testing GET /api/meditation-settings/preferences (verify guru_invocation custom URL)")
    prefs_response2 = requests.get(f"{BACKEND_URL}/meditation-settings/preferences", headers=headers)
    
    if prefs_response2.status_code != 200:
        log_test("GET /meditation-settings/preferences (after guru update)", False, f"Status: {prefs_response2.status_code}")
        return
    
    prefs_data2 = prefs_response2.json()
    guru_pref = prefs_data2.get("meditations", {}).get("guru_invocation", {})
    
    if guru_pref.get("source_type") != "custom_url":
        log_test("GET /meditation-settings/preferences (after guru update)", False, 
                f"guru_invocation source_type should be 'custom_url', got '{guru_pref.get('source_type')}'")
        return
    
    if guru_pref.get("resolved_url") != custom_guru_url:
        log_test("GET /meditation-settings/preferences (after guru update)", False, 
                f"guru_invocation resolved_url should be '{custom_guru_url}', got '{guru_pref.get('resolved_url')}'")
        return
    
    log_test("GET /meditation-settings/preferences (after guru update)", True, 
             "guru_invocation now shows source_type='custom_url' and resolved_url equals custom URL")
    
    # Step 6: Test PUT /api/meditation-settings/preferences (set custom URL for stillness_meditation)
    print("\n[6] Testing PUT /api/meditation-settings/preferences (set custom URL for stillness_meditation)")
    custom_stillness_url = "https://example.com/my-stillness.mp3"
    
    update_response2 = requests.put(
        f"{BACKEND_URL}/meditation-settings/preferences",
        headers=headers,
        json={
            "meditation_id": "stillness_meditation",
            "source_type": "custom_url",
            "custom_url": custom_stillness_url
        }
    )
    
    if update_response2.status_code != 200:
        log_test("PUT /meditation-settings/preferences (stillness_meditation)", False, 
                f"Status: {update_response2.status_code}, Response: {update_response2.text}")
        return
    
    log_test("PUT /meditation-settings/preferences (stillness_meditation)", True, 
             f"Set custom URL for stillness_meditation: {custom_stillness_url}")
    
    # Step 7: Test GET /api/meditation-settings/preferences (verify both custom URLs)
    print("\n[7] Testing GET /api/meditation-settings/preferences (verify both custom URLs)")
    prefs_response3 = requests.get(f"{BACKEND_URL}/meditation-settings/preferences", headers=headers)
    
    if prefs_response3.status_code != 200:
        log_test("GET /meditation-settings/preferences (after both updates)", False, f"Status: {prefs_response3.status_code}")
        return
    
    prefs_data3 = prefs_response3.json()
    meditations3 = prefs_data3.get("meditations", {})
    
    guru_pref3 = meditations3.get("guru_invocation", {})
    stillness_pref3 = meditations3.get("stillness_meditation", {})
    goal_pref3 = meditations3.get("goal_manifestation", {})
    
    # Verify guru_invocation still custom
    if guru_pref3.get("source_type") != "custom_url" or guru_pref3.get("resolved_url") != custom_guru_url:
        log_test("GET /meditation-settings/preferences (after both updates)", False, 
                "guru_invocation custom URL not preserved")
        return
    
    # Verify stillness_meditation custom
    if stillness_pref3.get("source_type") != "custom_url" or stillness_pref3.get("resolved_url") != custom_stillness_url:
        log_test("GET /meditation-settings/preferences (after both updates)", False, 
                "stillness_meditation custom URL not set correctly")
        return
    
    # Verify goal_manifestation still default
    if goal_pref3.get("source_type") != "default":
        log_test("GET /meditation-settings/preferences (after both updates)", False, 
                "goal_manifestation should still be default")
        return
    
    log_test("GET /meditation-settings/preferences (after both updates)", True, 
             "Both custom URLs are set correctly, goal_manifestation still default")
    
    # Step 8: Test DELETE /api/meditation-settings/preferences/guru_invocation (reset to default)
    print("\n[8] Testing DELETE /api/meditation-settings/preferences/guru_invocation (reset to default)")
    delete_response = requests.delete(
        f"{BACKEND_URL}/meditation-settings/preferences/guru_invocation",
        headers=headers
    )
    
    if delete_response.status_code != 200:
        log_test("DELETE /meditation-settings/preferences/guru_invocation", False, 
                f"Status: {delete_response.status_code}, Response: {delete_response.text}")
        return
    
    delete_data = delete_response.json()
    if not delete_data.get("reset"):
        log_test("DELETE /meditation-settings/preferences/guru_invocation", False, "reset field not True")
        return
    
    log_test("DELETE /meditation-settings/preferences/guru_invocation", True, 
             "Reset guru_invocation to default")
    
    # Step 9: Test GET /api/meditation-settings/preferences (verify guru_invocation back to default, stillness still custom)
    print("\n[9] Testing GET /api/meditation-settings/preferences (verify reset)")
    prefs_response4 = requests.get(f"{BACKEND_URL}/meditation-settings/preferences", headers=headers)
    
    if prefs_response4.status_code != 200:
        log_test("GET /meditation-settings/preferences (after reset)", False, f"Status: {prefs_response4.status_code}")
        return
    
    prefs_data4 = prefs_response4.json()
    meditations4 = prefs_data4.get("meditations", {})
    
    guru_pref4 = meditations4.get("guru_invocation", {})
    stillness_pref4 = meditations4.get("stillness_meditation", {})
    
    # Verify guru_invocation back to default
    if guru_pref4.get("source_type") != "default":
        log_test("GET /meditation-settings/preferences (after reset)", False, 
                f"guru_invocation should be 'default', got '{guru_pref4.get('source_type')}'")
        return
    
    if "isha.sadhguru.org" not in guru_pref4.get("resolved_url", ""):
        log_test("GET /meditation-settings/preferences (after reset)", False, 
                "guru_invocation resolved_url should be back to Isha Sadhguru default")
        return
    
    # Verify stillness_meditation still custom
    if stillness_pref4.get("source_type") != "custom_url" or stillness_pref4.get("resolved_url") != custom_stillness_url:
        log_test("GET /meditation-settings/preferences (after reset)", False, 
                "stillness_meditation custom URL should still be set")
        return
    
    log_test("GET /meditation-settings/preferences (after reset)", True, 
             "guru_invocation is back to default, stillness_meditation still custom")
    
    # Step 10: Test auth requirement on preferences endpoint
    print("\n[10] Testing auth requirement on GET /api/meditation-settings/preferences")
    unauth_response = requests.get(f"{BACKEND_URL}/meditation-settings/preferences")
    
    if unauth_response.status_code == 200:
        log_test("Auth requirement on GET /meditation-settings/preferences", False, 
                "Should require authentication but returned 200")
        return
    
    if unauth_response.status_code not in [401, 403]:
        log_test("Auth requirement on GET /meditation-settings/preferences", False, 
                f"Expected 401/403, got {unauth_response.status_code}")
        return
    
    log_test("Auth requirement on GET /meditation-settings/preferences", True, 
             f"Correctly requires authentication (status: {unauth_response.status_code})")
    
    # Step 11: Test auth requirement on PUT endpoint
    print("\n[11] Testing auth requirement on PUT /api/meditation-settings/preferences")
    unauth_put_response = requests.put(
        f"{BACKEND_URL}/meditation-settings/preferences",
        json={
            "meditation_id": "guru_invocation",
            "source_type": "custom_url",
            "custom_url": "https://test.com/test.mp3"
        }
    )
    
    if unauth_put_response.status_code == 200:
        log_test("Auth requirement on PUT /meditation-settings/preferences", False, 
                "Should require authentication but returned 200")
        return
    
    if unauth_put_response.status_code not in [401, 403]:
        log_test("Auth requirement on PUT /meditation-settings/preferences", False, 
                f"Expected 401/403, got {unauth_put_response.status_code}")
        return
    
    log_test("Auth requirement on PUT /meditation-settings/preferences", True, 
             f"Correctly requires authentication (status: {unauth_put_response.status_code})")
    
    # Step 12: Test auth requirement on DELETE endpoint
    print("\n[12] Testing auth requirement on DELETE /api/meditation-settings/preferences/{meditation_id}")
    unauth_delete_response = requests.delete(
        f"{BACKEND_URL}/meditation-settings/preferences/guru_invocation"
    )
    
    if unauth_delete_response.status_code == 200:
        log_test("Auth requirement on DELETE /meditation-settings/preferences", False, 
                "Should require authentication but returned 200")
        return
    
    if unauth_delete_response.status_code not in [401, 403]:
        log_test("Auth requirement on DELETE /meditation-settings/preferences", False, 
                f"Expected 401/403, got {unauth_delete_response.status_code}")
        return
    
    log_test("Auth requirement on DELETE /meditation-settings/preferences", True, 
             f"Correctly requires authentication (status: {unauth_delete_response.status_code})")
    
    print("\n" + "="*80)
    print("MEDITATION SETTINGS TESTING COMPLETE")
    print("="*80)

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        test_meditation_settings()
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        print_summary()
