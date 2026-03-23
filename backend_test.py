#!/usr/bin/env python3

import requests
import json
import time
import random
import string

# Backend URL
BASE_URL = "https://prr-actions-central.preview.emergentagent.com/api"

def generate_random_suffix():
    """Generate random suffix for unique emails"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

def test_org_level_admin_hierarchy():
    """Test the complete Org-Level Admin Hierarchy endpoints flow"""
    print("🚀 TESTING ORG-LEVEL ADMIN HIERARCHY ENDPOINTS")
    print("=" * 60)
    
    # Generate unique identifiers
    suffix = generate_random_suffix()
    
    # Test data
    org_creator_email = f"orgcreator_test_{suffix}@test.com"
    org_member_email = f"orgmember_test_{suffix}@test.com"
    org_member2_email = f"orgmember2_test_{suffix}@test.com"
    org_slug = f"test-org-roles-{suffix}"
    
    session_token_A = None
    session_token_B = None
    session_token_C = None
    org_id = None
    user_b_id = None
    user_c_id = None
    
    try:
        # Step 1: Register User A (will be org creator)
        print("\n1. 📝 Registering User A (Org Creator)...")
        register_data_a = {
            "email": org_creator_email,
            "password": "test123",
            "name": "Org Creator"
        }
        
        response = requests.post(f"{BASE_URL}/auth/register", json=register_data_a)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            session_token_A = data.get("session_token")
            print(f"   ✅ PASS: User A registered successfully")
            print(f"   Session Token A: {session_token_A[:20]}...")
        else:
            print(f"   ❌ FAIL: Registration failed - {response.text}")
            return False
            
        # Step 2: Create Organization as User A
        print("\n2. 🏢 Creating Organization as User A...")
        org_data = {
            "name": "Test Org Roles",
            "slug": org_slug
        }
        
        headers_a = {"Authorization": f"Bearer {session_token_A}"}
        response = requests.post(f"{BASE_URL}/organizations", json=org_data, headers=headers_a)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            org_id = data.get("id")
            print(f"   ✅ PASS: Organization created successfully")
            print(f"   Org ID: {org_id}")
            print(f"   Org Slug: {org_slug}")
        else:
            print(f"   ❌ FAIL: Organization creation failed - {response.text}")
            return False
            
        # Step 3: Verify User A has org_super_admin
        print("\n3. 👑 Verifying User A has org_super_admin role...")
        response = requests.get(f"{BASE_URL}/auth/me", headers=headers_a)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            org_role = data.get("org_role")
            if org_role == "org_super_admin":
                print(f"   ✅ PASS: User A has org_super_admin role")
            else:
                print(f"   ❌ FAIL: Expected org_super_admin, got {org_role}")
                return False
        else:
            print(f"   ❌ FAIL: Auth me failed - {response.text}")
            return False
            
        # Step 4: Register User B with org slug
        print("\n4. 📝 Registering User B with org slug...")
        register_data_b = {
            "email": org_member_email,
            "password": "test123",
            "name": "Org Member",
            "org_id": org_id  # Using actual org_id instead of slug
        }
        
        response = requests.post(f"{BASE_URL}/auth/register", json=register_data_b)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            session_token_B = data.get("session_token")
            user_b_id = data.get("user_id")
            print(f"   ✅ PASS: User B registered successfully")
            print(f"   Session Token B: {session_token_B[:20]}...")
            print(f"   User B ID: {user_b_id}")
        else:
            print(f"   ❌ FAIL: Registration failed - {response.text}")
            return False
            
        # Step 5: Verify User B has org_member
        print("\n5. 👤 Verifying User B has org_member role...")
        headers_b = {"Authorization": f"Bearer {session_token_B}"}
        response = requests.get(f"{BASE_URL}/auth/me", headers=headers_b)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            org_role = data.get("org_role")
            if org_role == "org_member":
                print(f"   ✅ PASS: User B has org_member role")
            else:
                print(f"   ❌ FAIL: Expected org_member, got {org_role}")
                return False
        else:
            print(f"   ❌ FAIL: Auth me failed - {response.text}")
            return False
            
        # Step 6: Register User C with org slug
        print("\n6. 📝 Registering User C with org slug...")
        register_data_c = {
            "email": org_member2_email,
            "password": "test123",
            "name": "Org Member 2",
            "org_id": org_id  # Using actual org_id instead of slug
        }
        
        response = requests.post(f"{BASE_URL}/auth/register", json=register_data_c)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            session_token_C = data.get("session_token")
            user_c_id = data.get("user_id")
            print(f"   ✅ PASS: User C registered successfully")
            print(f"   Session Token C: {session_token_C[:20]}...")
            print(f"   User C ID: {user_c_id}")
        else:
            print(f"   ❌ FAIL: Registration failed - {response.text}")
            return False
            
        # Step 7: List org members as User A
        print("\n7. 📋 Listing org members as User A...")
        response = requests.get(f"{BASE_URL}/organizations/{org_id}/members", headers=headers_a)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            members = response.json()
            print(f"   ✅ PASS: Retrieved {len(members)} members")
            for member in members:
                print(f"   - {member.get('name')} ({member.get('email')}) - {member.get('org_role')}")
            
            if len(members) == 3:
                print(f"   ✅ PASS: All 3 members present")
            else:
                print(f"   ❌ FAIL: Expected 3 members, got {len(members)}")
                return False
        else:
            print(f"   ❌ FAIL: List members failed - {response.text}")
            return False
            
        # Step 8: Promote User B to org_admin as User A
        print("\n8. ⬆️ Promoting User B to org_admin as User A...")
        promote_data = {"org_role": "org_admin"}
        response = requests.put(f"{BASE_URL}/organizations/{org_id}/members/{user_b_id}/role", 
                              json=promote_data, headers=headers_a)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   ✅ PASS: User B promoted to org_admin")
        else:
            print(f"   ❌ FAIL: Promotion failed - {response.text}")
            return False
            
        # Step 9: Promote User B to org_co_admin as User A
        print("\n9. ⬆️ Promoting User B to org_co_admin as User A...")
        promote_data = {"org_role": "org_co_admin"}
        response = requests.put(f"{BASE_URL}/organizations/{org_id}/members/{user_b_id}/role", 
                              json=promote_data, headers=headers_a)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   ✅ PASS: User B promoted to org_co_admin (only org_super_admin can do this)")
        else:
            print(f"   ❌ FAIL: Promotion failed - {response.text}")
            return False
            
        # Step 10: Test User B promotes C to org_admin (as org_co_admin)
        print("\n10. ⬆️ Testing User B promotes C to org_admin (as org_co_admin)...")
        promote_data = {"org_role": "org_admin"}
        headers_b = {"Authorization": f"Bearer {session_token_B}"}
        response = requests.put(f"{BASE_URL}/organizations/{org_id}/members/{user_c_id}/role", 
                              json=promote_data, headers=headers_b)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   ✅ PASS: User B (org_co_admin) successfully promoted User C to org_admin")
        else:
            print(f"   ❌ FAIL: Promotion failed - {response.text}")
            return False
            
        # Step 11: Test User B cannot promote C to org_co_admin
        print("\n11. 🚫 Testing User B cannot promote C to org_co_admin (should FAIL)...")
        promote_data = {"org_role": "org_co_admin"}
        response = requests.put(f"{BASE_URL}/organizations/{org_id}/members/{user_c_id}/role", 
                              json=promote_data, headers=headers_b)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 403:
            print(f"   ✅ PASS: User B correctly denied promoting to org_co_admin (403 - only org_super_admin can create co_admin)")
        else:
            print(f"   ❌ FAIL: Expected 403, got {response.status_code} - {response.text}")
            return False
            
        # Step 12: Test User C cannot promote anyone (as org_admin, try promote User B)
        print("\n12. 🚫 Testing User C cannot promote User B (User B is org_co_admin >= User C's level)...")
        promote_data = {"org_role": "org_member"}
        headers_c = {"Authorization": f"Bearer {session_token_C}"}
        response = requests.put(f"{BASE_URL}/organizations/{org_id}/members/{user_b_id}/role", 
                              json=promote_data, headers=headers_c)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 403:
            print(f"   ✅ PASS: User C correctly denied modifying User B (403 - User B is org_co_admin which is >= User C's level)")
        else:
            print(f"   ❌ FAIL: Expected 403, got {response.status_code} - {response.text}")
            return False
            
        # Step 13: Test self-modification fails
        print("\n13. 🚫 Testing self-modification fails (User A tries to change own role)...")
        promote_data = {"org_role": "org_admin"}
        user_a_response = requests.get(f"{BASE_URL}/auth/me", headers=headers_a)
        user_a_data = user_a_response.json()
        user_a_id = user_a_data.get("user_id")
        
        response = requests.put(f"{BASE_URL}/organizations/{org_id}/members/{user_a_id}/role", 
                              json=promote_data, headers=headers_a)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 400:
            print(f"   ✅ PASS: Self-modification correctly denied (400 - Cannot change your own org role)")
        else:
            print(f"   ❌ FAIL: Expected 400, got {response.status_code} - {response.text}")
            return False
            
        # Step 14: Remove User C from org as User B
        print("\n14. 🗑️ Removing User C from org as User B...")
        response = requests.delete(f"{BASE_URL}/organizations/{org_id}/members/{user_c_id}", headers=headers_b)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   ✅ PASS: User C removed from organization successfully")
        else:
            print(f"   ❌ FAIL: Removal failed - {response.text}")
            return False
            
        # Step 15: Verify removed user
        print("\n15. ✅ Verifying removed user (User C org_id and org_role should be null)...")
        headers_c = {"Authorization": f"Bearer {session_token_C}"}
        response = requests.get(f"{BASE_URL}/auth/me", headers=headers_c)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            org_id_c = data.get("org_id")
            org_role_c = data.get("org_role")
            if org_id_c is None and org_role_c is None:
                print(f"   ✅ PASS: User C correctly removed - org_id and org_role are null")
            else:
                print(f"   ❌ FAIL: User C still has org_id: {org_id_c}, org_role: {org_role_c}")
                return False
        else:
            print(f"   ❌ FAIL: Auth me failed - {response.text}")
            return False
            
        print("\n" + "=" * 60)
        print("🎉 ALL ORG-LEVEL ADMIN HIERARCHY TESTS PASSED!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_org_level_admin_hierarchy()
    if not success:
        exit(1)