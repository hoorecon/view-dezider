#!/usr/bin/env python3
"""
ACM (WOWO Access Control Matrix) System - Comprehensive Test Suite
Tests all 14 steps of the ACM flow as specified in the review request.
"""

import requests
import json
import time
from datetime import datetime

# Backend URL
BASE_URL = "https://dezider-core.preview.emergentagent.com/api"

# Test data - Use existing super admin for ACM testing
TEST_ADMIN = {
    "email": "super@test.com",
    "password": "test123"
}

timestamp = int(time.time())
TEST_USER = {
    "email": f"acm_test_{timestamp}@example.com",
    "password": "SecurePass123!",
    "name": "ACM Test User"
}

# Global variables to store test data
admin_token = None
admin_user_id = None
session_token = None
user_id = None


def log_test(step_num, description):
    """Log test step"""
    print(f"\n{'='*80}")
    print(f"STEP {step_num}: {description}")
    print(f"{'='*80}")


def log_result(success, message, data=None):
    """Log test result"""
    status = "✅ PASSED" if success else "❌ FAILED"
    print(f"{status}: {message}")
    if data:
        print(f"Response: {json.dumps(data, indent=2)}")


def test_step_1_register():
    """Step 1: Register admin user"""
    global session_token, user_id
    log_test(1, "Register Admin User")
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json=TEST_USER,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            session_token = data.get("session_token")
            user_id = data.get("user_id")
            
            if session_token and user_id:
                log_result(True, f"User registered successfully with user_id: {user_id}")
                return True
            else:
                log_result(False, "Missing session_token or user_id in response", data)
                return False
        else:
            log_result(False, f"Registration failed with status {response.status_code}", response.json())
            return False
    except Exception as e:
        log_result(False, f"Exception during registration: {str(e)}")
        return False


def test_step_2_login():
    """Step 2: Login"""
    global session_token
    log_test(2, "Login")
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": TEST_USER["email"],
                "password": TEST_USER["password"]
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            session_token = data.get("session_token")
            
            if session_token:
                log_result(True, "Login successful, session token refreshed")
                return True
            else:
                log_result(False, "Missing session_token in response", data)
                return False
        else:
            log_result(False, f"Login failed with status {response.status_code}", response.json())
            return False
    except Exception as e:
        log_result(False, f"Exception during login: {str(e)}")
        return False


def test_step_3_login_as_admin():
    """Step 3: Login as existing super admin"""
    global admin_token, admin_user_id
    log_test(3, "Login as Super Admin")
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": TEST_ADMIN["email"],
                "password": TEST_ADMIN["password"]
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            admin_token = data.get("session_token")
            admin_user_id = data.get("user_id")
            
            if admin_token:
                log_result(True, f"Admin login successful, user_id: {admin_user_id}")
                return True
            else:
                log_result(False, "Missing admin session_token in response", data)
                return False
        else:
            log_result(False, f"Admin login failed with status {response.status_code}", response.json())
            return False
    except Exception as e:
        log_result(False, f"Exception during admin login: {str(e)}")
        return False


def test_step_4_seed_acm():
    """Step 4: Seed ACM - verify response has {message, modules: 22, features: number>30}"""
    log_test(4, "Seed ACM")
    
    try:
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.post(
            f"{BASE_URL}/acm/seed",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            modules = data.get("modules")
            features = data.get("features")
            
            # Verify expected structure
            if modules == 22 and features and features > 30:
                log_result(True, f"ACM seeded successfully: {modules} modules, {features} features", data)
                return True
            else:
                log_result(False, f"Unexpected seed response: modules={modules}, features={features}", data)
                return False
        else:
            log_result(False, f"ACM seed failed with status {response.status_code}", response.json())
            return False
    except Exception as e:
        log_result(False, f"Exception during ACM seed: {str(e)}")
        return False


def test_step_5_get_full_matrix():
    """Step 5: Get full matrix - verify response has {modules (array of 22), user_types (7 items), subscription_plans (5 items), release_stages (array), total_modules: 22, total_features}"""
    log_test(5, "Get Full Matrix")
    
    try:
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/acm/matrix",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            modules = data.get("modules", [])
            user_types = data.get("user_types", [])
            subscription_plans = data.get("subscription_plans", [])
            release_stages = data.get("release_stages", [])
            total_modules = data.get("total_modules")
            total_features = data.get("total_features")
            
            # Verify expected structure
            checks = [
                (len(modules) == 22, f"modules count: {len(modules)} (expected 22)"),
                (len(user_types) == 7, f"user_types count: {len(user_types)} (expected 7)"),
                (len(subscription_plans) == 5, f"subscription_plans count: {len(subscription_plans)} (expected 5)"),
                (len(release_stages) > 0, f"release_stages present: {len(release_stages)} items"),
                (total_modules == 22, f"total_modules: {total_modules} (expected 22)"),
                (total_features and total_features > 30, f"total_features: {total_features} (expected >30)"),
            ]
            
            all_passed = all(check[0] for check in checks)
            
            if all_passed:
                log_result(True, "Full matrix retrieved successfully with correct structure")
                for check in checks:
                    print(f"  ✓ {check[1]}")
                return True
            else:
                log_result(False, "Matrix structure validation failed")
                for check in checks:
                    status = "✓" if check[0] else "✗"
                    print(f"  {status} {check[1]}")
                return False
        else:
            log_result(False, f"Get matrix failed with status {response.status_code}", response.json())
            return False
    except Exception as e:
        log_result(False, f"Exception during get matrix: {str(e)}")
        return False


def test_step_6_check_my_access():
    """Step 6: Check my access (as admin = free user type) - verify response has {user_id, user_type: "free", subscription_plan: "none", features (object with many feature_ids)}"""
    log_test(6, "Check My Access (as free user)")
    
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.get(
            f"{BASE_URL}/acm/my-access",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            returned_user_id = data.get("user_id")
            user_type = data.get("user_type")
            subscription_plan = data.get("subscription_plan")
            features = data.get("features", {})
            
            # Verify expected structure
            checks = [
                (returned_user_id == user_id, f"user_id matches: {returned_user_id}"),
                (user_type == "free", f"user_type: {user_type} (expected 'free')"),
                (subscription_plan == "none", f"subscription_plan: {subscription_plan} (expected 'none')"),
                (len(features) > 30, f"features count: {len(features)} (expected >30)"),
            ]
            
            all_passed = all(check[0] for check in checks)
            
            if all_passed:
                log_result(True, "My access retrieved successfully")
                for check in checks:
                    print(f"  ✓ {check[1]}")
                
                # Show sample feature
                sample_feature_id = list(features.keys())[0] if features else None
                if sample_feature_id:
                    sample = features[sample_feature_id]
                    print(f"\n  Sample feature '{sample_feature_id}':")
                    print(f"    - access_level: {sample.get('access_level')}")
                    print(f"    - quota_limit: {sample.get('quota_limit')}")
                    print(f"    - quota_used: {sample.get('quota_used')}")
                    print(f"    - quota_remaining: {sample.get('quota_remaining')}")
                    print(f"    - quota_unit: {sample.get('quota_unit')}")
                
                return True
            else:
                log_result(False, "My access validation failed")
                for check in checks:
                    status = "✓" if check[0] else "✗"
                    print(f"  {status} {check[1]}")
                return False
        else:
            log_result(False, f"Get my access failed with status {response.status_code}", response.json())
            return False
    except Exception as e:
        log_result(False, f"Exception during get my access: {str(e)}")
        return False


def test_step_7_check_single_feature():
    """Step 7: Check single feature - verify returns {feature_id, allowed: true, access_level: "full", quota_limit: 3, quota_unit: "decisions/month"}"""
    log_test(7, "Check Single Feature (my_dezider_create)")
    
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.get(
            f"{BASE_URL}/acm/check/my_dezider_create",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            feature_id = data.get("feature_id")
            allowed = data.get("allowed")
            access_level = data.get("access_level")
            quota_limit = data.get("quota_limit")
            quota_unit = data.get("quota_unit")
            
            # Verify expected structure for free user
            checks = [
                (feature_id == "my_dezider_create", f"feature_id: {feature_id}"),
                (allowed == True, f"allowed: {allowed} (expected True)"),
                (access_level == "full", f"access_level: {access_level} (expected 'full')"),
                (quota_limit == 3, f"quota_limit: {quota_limit} (expected 3 for free users)"),
                (quota_unit == "decisions/month", f"quota_unit: {quota_unit}"),
            ]
            
            all_passed = all(check[0] for check in checks)
            
            if all_passed:
                log_result(True, "Single feature check successful")
                for check in checks:
                    print(f"  ✓ {check[1]}")
                return True
            else:
                log_result(False, "Single feature validation failed")
                for check in checks:
                    status = "✓" if check[0] else "✗"
                    print(f"  {status} {check[1]}")
                return False
        else:
            log_result(False, f"Check feature failed with status {response.status_code}", response.json())
            return False
    except Exception as e:
        log_result(False, f"Exception during check feature: {str(e)}")
        return False


def test_step_8_check_locked_feature():
    """Step 8: Check locked feature (for free user) - verify returns {allowed: false, access_level: "locked"}"""
    log_test(8, "Check Locked Feature (solution_finder)")
    
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.get(
            f"{BASE_URL}/acm/check/solution_finder",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            allowed = data.get("allowed")
            access_level = data.get("access_level")
            
            # Verify expected structure for locked feature
            checks = [
                (allowed == False, f"allowed: {allowed} (expected False)"),
                (access_level == "locked", f"access_level: {access_level} (expected 'locked')"),
            ]
            
            all_passed = all(check[0] for check in checks)
            
            if all_passed:
                log_result(True, "Locked feature check successful", data)
                for check in checks:
                    print(f"  ✓ {check[1]}")
                return True
            else:
                log_result(False, "Locked feature validation failed")
                for check in checks:
                    status = "✓" if check[0] else "✗"
                    print(f"  {status} {check[1]}")
                return False
        else:
            log_result(False, f"Check locked feature failed with status {response.status_code}", response.json())
            return False
    except Exception as e:
        log_result(False, f"Exception during check locked feature: {str(e)}")
        return False


def test_step_9_check_hidden_feature():
    """Step 9: Check hidden feature (for free user) - verify returns {allowed: false, access_level: "hidden"}"""
    log_test(9, "Check Hidden Feature (deo_scrape)")
    
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.get(
            f"{BASE_URL}/acm/check/deo_scrape",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            allowed = data.get("allowed")
            access_level = data.get("access_level")
            
            # Verify expected structure for hidden feature
            checks = [
                (allowed == False, f"allowed: {allowed} (expected False)"),
                (access_level == "hidden", f"access_level: {access_level} (expected 'hidden')"),
            ]
            
            all_passed = all(check[0] for check in checks)
            
            if all_passed:
                log_result(True, "Hidden feature check successful", data)
                for check in checks:
                    print(f"  ✓ {check[1]}")
                return True
            else:
                log_result(False, "Hidden feature validation failed")
                for check in checks:
                    status = "✓" if check[0] else "✗"
                    print(f"  {status} {check[1]}")
                return False
        else:
            log_result(False, f"Check hidden feature failed with status {response.status_code}", response.json())
            return False
    except Exception as e:
        log_result(False, f"Exception during check hidden feature: {str(e)}")
        return False


def test_step_10_set_user_type():
    """Step 10: Set user type - PUT /api/acm/user/{user_id}/type with {"user_type": "beta", "subscription_plan": "pro"}"""
    log_test(10, "Set User Type to Beta + Pro Plan")
    
    try:
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.put(
            f"{BASE_URL}/acm/user/{user_id}/type",
            headers=headers,
            json={
                "user_type": "beta",
                "subscription_plan": "pro"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            user_type = data.get("user_type")
            subscription_plan = data.get("subscription_plan")
            
            # Verify expected structure
            checks = [
                (user_type == "beta", f"user_type: {user_type} (expected 'beta')"),
                (subscription_plan == "pro", f"subscription_plan: {subscription_plan} (expected 'pro')"),
            ]
            
            all_passed = all(check[0] for check in checks)
            
            if all_passed:
                log_result(True, "User type updated successfully", data)
                for check in checks:
                    print(f"  ✓ {check[1]}")
                return True
            else:
                log_result(False, "User type update validation failed")
                for check in checks:
                    status = "✓" if check[0] else "✗"
                    print(f"  {status} {check[1]}")
                return False
        else:
            log_result(False, f"Set user type failed with status {response.status_code}", response.json())
            return False
    except Exception as e:
        log_result(False, f"Exception during set user type: {str(e)}")
        return False


def test_step_11_recheck_access_after_upgrade():
    """Step 11: Re-check access after upgrade - verify user_type is now "beta" and features that were locked/hidden are now accessible"""
    log_test(11, "Re-check Access After Upgrade")
    
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.get(
            f"{BASE_URL}/acm/my-access",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            user_type = data.get("user_type")
            subscription_plan = data.get("subscription_plan")
            features = data.get("features", {})
            
            # Check that user type is updated
            checks = [
                (user_type == "beta", f"user_type: {user_type} (expected 'beta')"),
            ]
            
            # Check previously locked feature (solution_finder)
            solution_finder = features.get("solution_finder", {})
            solution_finder_level = solution_finder.get("access_level")
            checks.append((
                solution_finder_level in ["full", "read"],
                f"solution_finder access_level: {solution_finder_level} (expected 'full' or 'read', was 'locked')"
            ))
            
            # Check previously hidden feature (deo_scrape)
            deo_scrape = features.get("deo_scrape", {})
            deo_scrape_level = deo_scrape.get("access_level")
            checks.append((
                deo_scrape_level in ["full", "read", "locked"],
                f"deo_scrape access_level: {deo_scrape_level} (expected not 'hidden', was 'hidden')"
            ))
            
            all_passed = all(check[0] for check in checks)
            
            if all_passed:
                log_result(True, "Access upgrade verified successfully")
                for check in checks:
                    print(f"  ✓ {check[1]}")
                return True
            else:
                log_result(False, "Access upgrade validation failed")
                for check in checks:
                    status = "✓" if check[0] else "✗"
                    print(f"  {status} {check[1]}")
                return False
        else:
            log_result(False, f"Re-check access failed with status {response.status_code}", response.json())
            return False
    except Exception as e:
        log_result(False, f"Exception during re-check access: {str(e)}")
        return False


def test_step_12_force_reseed():
    """Step 12: Force re-seed - POST /api/acm/seed?force=true"""
    log_test(12, "Force Re-seed ACM")
    
    try:
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.post(
            f"{BASE_URL}/acm/seed?force=true",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            modules = data.get("modules")
            features = data.get("features")
            
            # Verify expected structure
            if modules == 22 and features and features > 30:
                log_result(True, f"ACM re-seeded successfully: {modules} modules, {features} features", data)
                return True
            else:
                log_result(False, f"Unexpected re-seed response: modules={modules}, features={features}", data)
                return False
        else:
            log_result(False, f"Force re-seed failed with status {response.status_code}", response.json())
            return False
    except Exception as e:
        log_result(False, f"Exception during force re-seed: {str(e)}")
        return False


def test_step_13_update_feature():
    """Step 13: Update feature - PUT /api/acm/feature/my_dezider_create with {"release_stage": "beta", "access": {"free": {"level": "locked", "quota": 0}}}"""
    log_test(13, "Update Feature Access Rules")
    
    try:
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.put(
            f"{BASE_URL}/acm/feature/my_dezider_create",
            headers=headers,
            json={
                "release_stage": "beta",
                "access": {
                    "free": {"level": "locked", "quota": 0}
                }
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            message = data.get("message")
            updates = data.get("updates", [])
            
            # Verify update was successful
            if "updated" in message.lower() and len(updates) > 0:
                log_result(True, "Feature updated successfully", data)
                print(f"  Updated fields: {', '.join(updates)}")
                return True
            else:
                log_result(False, "Unexpected update response", data)
                return False
        else:
            log_result(False, f"Update feature failed with status {response.status_code}", response.json())
            return False
    except Exception as e:
        log_result(False, f"Exception during update feature: {str(e)}")
        return False


def test_step_14_list_users():
    """Step 14: List users - GET /api/acm/users?user_type=beta"""
    log_test(14, "List Users by Type")
    
    try:
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/acm/users?user_type=beta",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            total = data.get("total")
            users = data.get("users", [])
            
            # Verify our test user is in the list
            test_user_found = any(u.get("user_id") == user_id for u in users)
            
            checks = [
                (total >= 1, f"total: {total} (expected >= 1)"),
                (len(users) >= 1, f"users count: {len(users)} (expected >= 1)"),
                (test_user_found, f"test user found in list: {test_user_found}"),
            ]
            
            all_passed = all(check[0] for check in checks)
            
            if all_passed:
                log_result(True, "Users list retrieved successfully")
                for check in checks:
                    print(f"  ✓ {check[1]}")
                
                # Show our test user
                test_user_data = next((u for u in users if u.get("user_id") == user_id), None)
                if test_user_data:
                    print(f"\n  Test user details:")
                    print(f"    - email: {test_user_data.get('email')}")
                    print(f"    - user_type: {test_user_data.get('user_type')}")
                    print(f"    - subscription_plan: {test_user_data.get('subscription_plan')}")
                
                return True
            else:
                log_result(False, "Users list validation failed")
                for check in checks:
                    status = "✓" if check[0] else "✗"
                    print(f"  {status} {check[1]}")
                return False
        else:
            log_result(False, f"List users failed with status {response.status_code}", response.json())
            return False
    except Exception as e:
        log_result(False, f"Exception during list users: {str(e)}")
        return False


def main():
    """Run all ACM tests"""
    print("\n" + "="*80)
    print("ACM (WOWO Access Control Matrix) System - Comprehensive Test Suite")
    print("="*80)
    print(f"Backend URL: {BASE_URL}")
    print(f"Test User: {TEST_USER['email']}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Track results
    results = []
    
    # Run all tests in sequence
    test_functions = [
        ("Step 1: Register Admin User", test_step_1_register),
        ("Step 2: Login", test_step_2_login),
        ("Step 3: Login as Admin", test_step_3_login_as_admin),
        ("Step 4: Seed ACM", test_step_4_seed_acm),
        ("Step 5: Get Full Matrix", test_step_5_get_full_matrix),
        ("Step 6: Check My Access", test_step_6_check_my_access),
        ("Step 7: Check Single Feature", test_step_7_check_single_feature),
        ("Step 8: Check Locked Feature", test_step_8_check_locked_feature),
        ("Step 9: Check Hidden Feature", test_step_9_check_hidden_feature),
        ("Step 10: Set User Type", test_step_10_set_user_type),
        ("Step 11: Re-check Access After Upgrade", test_step_11_recheck_access_after_upgrade),
        ("Step 12: Force Re-seed", test_step_12_force_reseed),
        ("Step 13: Update Feature", test_step_13_update_feature),
        ("Step 14: List Users", test_step_14_list_users),
    ]
    
    for test_name, test_func in test_functions:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ CRITICAL ERROR in {test_name}: {str(e)}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\n{'='*80}")
    print(f"TOTAL: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print(f"{'='*80}\n")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
