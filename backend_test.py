#!/usr/bin/env python3
"""
Backend Testing Script for Payment & Credits System
Tests the complete payment and credits workflow as specified in the review request.
"""

import requests
import json
import time
from datetime import datetime

# Backend URL from environment
BACKEND_URL = "https://dezider-core.preview.emergentagent.com/api"

class PaymentCreditsTest:
    def __init__(self):
        self.session_token = None
        self.user_data = None
        
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        
    def test_user_registration(self):
        """Test 1: Register user for payment testing"""
        self.log("🔐 Testing User Registration...")
        
        # Use timestamp to ensure unique email
        timestamp = int(time.time())
        email = f"paytest@test.com"
        password = "test123"
        name = "Pay Tester"
        
        payload = {
            "email": email,
            "password": password,
            "name": name
        }
        
        response = requests.post(f"{BACKEND_URL}/auth/register", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            self.session_token = data.get("session_token")
            self.user_data = data
            self.log(f"✅ Registration successful! User ID: {data.get('user_id')}")
            self.log(f"   Session Token: {self.session_token[:20]}...")
            return True
        else:
            self.log(f"❌ Registration failed: {response.status_code} - {response.text}")
            return False
    
    def get_headers(self):
        """Get authorization headers"""
        return {"Authorization": f"Bearer {self.session_token}"}
    
    def test_plans_pricing(self):
        """Test 2: GET /api/payments/plans - Should return plans array, topup_packs array, and credit_costs object"""
        self.log("💰 Testing Plans & Pricing (Public)...")
        
        response = requests.get(f"{BACKEND_URL}/payments/plans")
        
        if response.status_code == 200:
            data = response.json()
            plans = data.get("plans", [])
            topup_packs = data.get("topup_packs", [])
            credit_costs = data.get("credit_costs", {})
            
            self.log(f"✅ Plans & Pricing retrieved successfully!")
            self.log(f"   Plans count: {len(plans)}")
            self.log(f"   Top-up packs count: {len(topup_packs)}")
            self.log(f"   Credit costs: {len(credit_costs)} actions")
            
            # Verify expected structure
            if len(plans) == 5 and len(topup_packs) == 5:
                self.log("   ✅ Expected 5 plans and 5 topup packs found")
                
                # Check specific plans
                plan_ids = [p.get("id") for p in plans]
                expected_plans = ["free", "starter", "pro", "business", "enterprise"]
                if all(pid in plan_ids for pid in expected_plans):
                    self.log("   ✅ All expected plan IDs found")
                else:
                    self.log(f"   ⚠️ Missing plan IDs. Found: {plan_ids}")
                
                # Check topup pack structure
                pack_ids = [p.get("id") for p in topup_packs]
                expected_packs = ["micro", "mini", "standard", "mega", "ultra"]
                if all(pid in pack_ids for pid in expected_packs):
                    self.log("   ✅ All expected topup pack IDs found")
                else:
                    self.log(f"   ⚠️ Missing pack IDs. Found: {pack_ids}")
                    
                return True
            else:
                self.log(f"   ⚠️ Unexpected counts - Plans: {len(plans)}, Packs: {len(topup_packs)}")
                return False
        else:
            self.log(f"❌ Plans retrieval failed: {response.status_code} - {response.text}")
            return False
    
    def test_wallet_creation(self):
        """Test 3: GET /api/payments/wallet - Should auto-create wallet with 100 initial credits"""
        self.log("👛 Testing Wallet Auto-Creation...")
        
        response = requests.get(f"{BACKEND_URL}/payments/wallet", headers=self.get_headers())
        
        if response.status_code == 200:
            wallet = response.json()
            credits = wallet.get("credits", 0)
            current_plan = wallet.get("current_plan", "")
            initial_credits = wallet.get("initial_credits", 0)
            
            self.log(f"✅ Wallet retrieved successfully!")
            self.log(f"   Credits: {credits}")
            self.log(f"   Current Plan: {current_plan}")
            self.log(f"   Initial Credits: {initial_credits}")
            
            if credits == 100 and current_plan == "free" and initial_credits == 100:
                self.log("   ✅ Wallet auto-created with expected defaults")
                return True
            else:
                self.log(f"   ⚠️ Unexpected wallet values")
                return False
        else:
            self.log(f"❌ Wallet retrieval failed: {response.status_code} - {response.text}")
            return False
    
    def test_credit_history(self):
        """Test 4: GET /api/payments/history - Should return transactions array with initial grant"""
        self.log("📊 Testing Credit History...")
        
        response = requests.get(f"{BACKEND_URL}/payments/history", headers=self.get_headers())
        
        if response.status_code == 200:
            data = response.json()
            transactions = data.get("transactions", [])
            
            self.log(f"✅ Credit history retrieved successfully!")
            self.log(f"   Transactions count: {len(transactions)}")
            
            if len(transactions) >= 1:
                # Check for initial grant transaction
                initial_grant = next((t for t in transactions if t.get("type") == "grant"), None)
                if initial_grant:
                    self.log(f"   ✅ Initial grant transaction found: {initial_grant.get('credits')} credits")
                    self.log(f"   Description: {initial_grant.get('description')}")
                    return True
                else:
                    self.log("   ⚠️ No initial grant transaction found")
                    return False
            else:
                self.log("   ⚠️ No transactions found")
                return False
        else:
            self.log(f"❌ Credit history retrieval failed: {response.status_code} - {response.text}")
            return False
    
    def test_credit_check(self):
        """Test 5 & 6: POST /api/payments/check-credits for different actions"""
        self.log("🔍 Testing Credit Check...")
        
        # Test cld_generate (should cost 3 credits)
        payload1 = {"action": "cld_generate"}
        response1 = requests.post(f"{BACKEND_URL}/payments/check-credits", json=payload1, headers=self.get_headers())
        
        if response1.status_code == 200:
            data1 = response1.json()
            self.log(f"✅ Credit check for cld_generate:")
            self.log(f"   Cost: {data1.get('cost')}")
            self.log(f"   Available: {data1.get('available')}")
            self.log(f"   Sufficient: {data1.get('sufficient')}")
            
            if data1.get("cost") == 3 and data1.get("sufficient") == True:
                self.log("   ✅ cld_generate check passed")
                check1_pass = True
            else:
                self.log("   ⚠️ Unexpected cld_generate values")
                check1_pass = False
        else:
            self.log(f"❌ Credit check for cld_generate failed: {response1.status_code}")
            check1_pass = False
        
        # Test cld_simulate (should cost 0 credits)
        payload2 = {"action": "cld_simulate"}
        response2 = requests.post(f"{BACKEND_URL}/payments/check-credits", json=payload2, headers=self.get_headers())
        
        if response2.status_code == 200:
            data2 = response2.json()
            self.log(f"✅ Credit check for cld_simulate:")
            self.log(f"   Cost: {data2.get('cost')}")
            self.log(f"   Available: {data2.get('available')}")
            self.log(f"   Sufficient: {data2.get('sufficient')}")
            
            if data2.get("cost") == 0 and data2.get("sufficient") == True:
                self.log("   ✅ cld_simulate check passed")
                check2_pass = True
            else:
                self.log("   ⚠️ Unexpected cld_simulate values")
                check2_pass = False
        else:
            self.log(f"❌ Credit check for cld_simulate failed: {response2.status_code}")
            check2_pass = False
        
        return check1_pass and check2_pass
    
    def test_topup_order_creation(self):
        """Test 7 & 8: POST /api/payments/create-topup-order"""
        self.log("🛒 Testing Top-up Order Creation (Razorpay)...")
        
        # Test valid pack_id "mini"
        payload1 = {"pack_id": "mini"}
        response1 = requests.post(f"{BACKEND_URL}/payments/create-topup-order", json=payload1, headers=self.get_headers())
        
        if response1.status_code == 200:
            data1 = response1.json()
            self.log(f"✅ Top-up order creation for 'mini' pack:")
            self.log(f"   Order ID: {data1.get('order_id')}")
            self.log(f"   Amount: {data1.get('amount')}")
            self.log(f"   Currency: {data1.get('currency')}")
            self.log(f"   Key ID: {data1.get('key_id')}")
            
            if (data1.get("amount") == 7900 and 
                data1.get("currency") == "INR" and 
                data1.get("order_id") and 
                data1.get("key_id")):
                self.log("   ✅ Valid mini pack order created successfully")
                order1_pass = True
            else:
                self.log("   ⚠️ Unexpected order values")
                order1_pass = False
        else:
            self.log(f"❌ Top-up order creation for mini failed: {response1.status_code} - {response1.text}")
            order1_pass = False
        
        # Test invalid pack_id
        payload2 = {"pack_id": "invalid"}
        response2 = requests.post(f"{BACKEND_URL}/payments/create-topup-order", json=payload2, headers=self.get_headers())
        
        if response2.status_code == 400:
            self.log("✅ Invalid pack_id correctly rejected with 400")
            order2_pass = True
        else:
            self.log(f"❌ Invalid pack_id should return 400, got: {response2.status_code}")
            order2_pass = False
        
        return order1_pass and order2_pass
    
    def test_subscription_order(self):
        """Test 9 & 10: POST /api/payments/create-subscription"""
        self.log("📅 Testing Subscription Order Creation...")
        
        # Test valid plan_id "pro"
        payload1 = {"plan_id": "pro"}
        response1 = requests.post(f"{BACKEND_URL}/payments/create-subscription", json=payload1, headers=self.get_headers())
        
        if response1.status_code == 200:
            data1 = response1.json()
            self.log(f"✅ Subscription order creation for 'pro' plan:")
            self.log(f"   Order ID: {data1.get('order_id')}")
            self.log(f"   Amount: {data1.get('amount')}")
            self.log(f"   Currency: {data1.get('currency')}")
            
            if (data1.get("amount") == 39900 and 
                data1.get("currency") == "INR" and 
                data1.get("order_id")):
                self.log("   ✅ Valid pro plan subscription created successfully")
                sub1_pass = True
            else:
                self.log("   ⚠️ Unexpected subscription values")
                sub1_pass = False
        else:
            self.log(f"❌ Subscription creation for pro failed: {response1.status_code} - {response1.text}")
            sub1_pass = False
        
        # Test invalid plan_id "free"
        payload2 = {"plan_id": "free"}
        response2 = requests.post(f"{BACKEND_URL}/payments/create-subscription", json=payload2, headers=self.get_headers())
        
        if response2.status_code == 400:
            self.log("✅ Free plan subscription correctly rejected with 400")
            sub2_pass = True
        else:
            self.log(f"❌ Free plan subscription should return 400, got: {response2.status_code}")
            sub2_pass = False
        
        return sub1_pass and sub2_pass
    
    def test_tepfi_metadata(self):
        """Test 11: GET /api/tepfi/metadata"""
        self.log("🧠 Testing TEPFI Metadata...")
        
        response = requests.get(f"{BACKEND_URL}/tepfi/metadata")
        
        if response.status_code == 200:
            data = response.json()
            dimensions = data.get("dimensions", [])
            layers = data.get("layers", [])
            effort_sub_dimensions = data.get("effort_sub_dimensions", [])
            
            self.log(f"✅ TEPFI metadata retrieved successfully!")
            self.log(f"   Dimensions: {dimensions}")
            self.log(f"   Layers: {layers}")
            self.log(f"   Effort sub-dimensions count: {len(effort_sub_dimensions)}")
            
            # Check for expected effort sub-dimensions (8 items as per review request)
            expected_sub_dims = ["attitude", "knowledge", "skills", "physical_health", 
                               "mental_state", "emotional_wellness", "energy_level", "action"]
            
            if len(effort_sub_dimensions) == 8:
                self.log("   ✅ Expected 8 effort sub-dimensions found")
                
                # Check if all expected sub-dimensions are present
                if all(dim in effort_sub_dimensions for dim in expected_sub_dims):
                    self.log("   ✅ All expected effort sub-dimensions present")
                    return True
                else:
                    self.log(f"   ⚠️ Some expected sub-dimensions missing. Found: {effort_sub_dimensions}")
                    return False
            else:
                self.log(f"   ⚠️ Expected 8 effort sub-dimensions, found: {len(effort_sub_dimensions)}")
                return False
        else:
            self.log(f"❌ TEPFI metadata retrieval failed: {response.status_code} - {response.text}")
            return False
    
    def test_admin_credits(self):
        """Test 12 & 13: Admin initial credits endpoints"""
        self.log("👑 Testing Admin Credits Management...")
        
        # Test PUT /api/payments/admin/initial-credits (should fail with 403 for non-admin)
        payload = {"initial_credits": 200}
        response1 = requests.put(f"{BACKEND_URL}/payments/admin/initial-credits", json=payload, headers=self.get_headers())
        
        if response1.status_code == 403:
            self.log("✅ Admin initial credits PUT correctly rejected with 403 (non-admin user)")
            admin1_pass = True
        else:
            self.log(f"❌ Admin initial credits PUT should return 403, got: {response1.status_code}")
            admin1_pass = False
        
        # Test GET /api/payments/admin/initial-credits
        response2 = requests.get(f"{BACKEND_URL}/payments/admin/initial-credits", headers=self.get_headers())
        
        if response2.status_code == 200:
            data2 = response2.json()
            initial_credits = data2.get("initial_credits")
            self.log(f"✅ Admin initial credits GET successful:")
            self.log(f"   Initial credits value: {initial_credits}")
            admin2_pass = True
        else:
            self.log(f"❌ Admin initial credits GET failed: {response2.status_code} - {response2.text}")
            admin2_pass = False
        
        return admin1_pass and admin2_pass
    
    def run_all_tests(self):
        """Run all payment & credits system tests"""
        self.log("🚀 Starting Payment & Credits System Testing...")
        self.log("=" * 60)
        
        test_results = []
        
        # Test 1: User Registration
        test_results.append(("User Registration", self.test_user_registration()))
        
        if not self.session_token:
            self.log("❌ Cannot continue without session token")
            return
        
        # Test 2: Plans & Pricing
        test_results.append(("Plans & Pricing", self.test_plans_pricing()))
        
        # Test 3: Wallet Creation
        test_results.append(("Wallet Auto-Creation", self.test_wallet_creation()))
        
        # Test 4: Credit History
        test_results.append(("Credit History", self.test_credit_history()))
        
        # Test 5 & 6: Credit Check
        test_results.append(("Credit Check", self.test_credit_check()))
        
        # Test 7 & 8: Top-up Order Creation
        test_results.append(("Top-up Order Creation", self.test_topup_order_creation()))
        
        # Test 9 & 10: Subscription Order
        test_results.append(("Subscription Order", self.test_subscription_order()))
        
        # Test 11: TEPFI Metadata
        test_results.append(("TEPFI Metadata", self.test_tepfi_metadata()))
        
        # Test 12 & 13: Admin Credits
        test_results.append(("Admin Credits", self.test_admin_credits()))
        
        # Summary
        self.log("=" * 60)
        self.log("📋 TEST SUMMARY:")
        
        passed = 0
        total = len(test_results)
        
        for test_name, result in test_results:
            status = "✅ PASS" if result else "❌ FAIL"
            self.log(f"   {test_name}: {status}")
            if result:
                passed += 1
        
        self.log("=" * 60)
        self.log(f"🎯 OVERALL RESULT: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
        
        if passed == total:
            self.log("🎉 ALL TESTS PASSED! Payment & Credits system is working correctly.")
        else:
            self.log(f"⚠️ {total-passed} test(s) failed. Please review the issues above.")

if __name__ == "__main__":
    tester = PaymentCreditsTest()
    tester.run_all_tests()