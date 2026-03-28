#!/usr/bin/env python3
"""
Razorpay E2E Payment Flow Testing
Backend URL: https://dezider-core.preview.emergentagent.com/api

Test the complete payment & credits flow end-to-end with LIVE Razorpay keys.
"""

import requests
import json
import hmac
import hashlib
import time
from datetime import datetime

# Configuration
BASE_URL = "https://dezider-core.preview.emergentagent.com/api"
RAZORPAY_KEY_SECRET = "nWomtUqYGunPQ1P37O1VNuM5"  # From review request

class RazorpayPaymentTester:
    def __init__(self):
        self.session = requests.Session()
        self.user_token = None
        self.user_data = None
        self.test_email = f"razorpay_test_{int(time.time())}@example.com"
        
    def log(self, message):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        
    def test_user_registration(self):
        """Step 1: Register a test user"""
        self.log("🔐 Step 1: Registering test user...")
        
        payload = {
            "email": self.test_email,
            "password": "SecurePass123!",
            "name": "Razorpay Test User"
        }
        
        response = self.session.post(f"{BASE_URL}/auth/register", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            self.user_token = data.get("session_token")
            self.user_data = data
            self.session.headers.update({"Authorization": f"Bearer {self.user_token}"})
            self.log(f"✅ User registered successfully: {data.get('email')}")
            self.log(f"   User ID: {data.get('user_id')}")
            return True
        else:
            self.log(f"❌ Registration failed: {response.status_code} - {response.text}")
            return False
            
    def test_pricing_plans(self):
        """Step 2: Test pricing & plans endpoint (public)"""
        self.log("💰 Step 2: Testing pricing & plans endpoint...")
        
        response = self.session.get(f"{BASE_URL}/payments/plans")
        
        if response.status_code == 200:
            data = response.json()
            plans = data.get("plans", [])
            topup_packs = data.get("topup_packs", [])
            credit_costs = data.get("credit_costs", {})
            
            self.log(f"✅ Plans endpoint working: {len(plans)} plans, {len(topup_packs)} topup packs")
            
            # Verify expected plans
            expected_plans = ["free", "starter", "pro", "business", "enterprise"]
            plan_ids = [p.get("id") for p in plans]
            for plan_id in expected_plans:
                if plan_id in plan_ids:
                    self.log(f"   ✓ Found plan: {plan_id}")
                else:
                    self.log(f"   ❌ Missing plan: {plan_id}")
                    
            # Verify expected topup packs
            expected_packs = ["micro", "mini", "standard", "mega", "ultra"]
            pack_ids = [p.get("id") for p in topup_packs]
            for pack_id in expected_packs:
                if pack_id in pack_ids:
                    self.log(f"   ✓ Found pack: {pack_id}")
                else:
                    self.log(f"   ❌ Missing pack: {pack_id}")
                    
            # Verify credit costs
            expected_actions = ["cld_generate", "decision_analyze"]
            for action in expected_actions:
                if action in credit_costs:
                    self.log(f"   ✓ Credit cost for {action}: {credit_costs[action]}")
                else:
                    self.log(f"   ❌ Missing credit cost for: {action}")
                    
            return True
        else:
            self.log(f"❌ Plans endpoint failed: {response.status_code} - {response.text}")
            return False
            
    def test_wallet_creation(self):
        """Step 3: Test wallet auto-creation with initial credits"""
        self.log("💳 Step 3: Testing wallet auto-creation...")
        
        response = self.session.get(f"{BASE_URL}/payments/wallet")
        
        if response.status_code == 200:
            wallet = response.json()
            credits = wallet.get("credits", 0)
            current_plan = wallet.get("current_plan", "")
            total_purchased = wallet.get("total_purchased", 0)
            total_used = wallet.get("total_used", 0)
            
            self.log(f"✅ Wallet created successfully:")
            self.log(f"   Credits: {credits}")
            self.log(f"   Current plan: {current_plan}")
            self.log(f"   Total purchased: {total_purchased}")
            self.log(f"   Total used: {total_used}")
            
            # Verify expected initial state
            if credits == 100 and current_plan == "free" and total_purchased == 0 and total_used == 0:
                self.log("   ✅ Wallet state matches expected initial values")
                return True
            else:
                self.log("   ❌ Wallet state doesn't match expected values")
                return False
        else:
            self.log(f"❌ Wallet creation failed: {response.status_code} - {response.text}")
            return False
            
    def test_credit_check(self):
        """Step 4: Test credit check for different actions"""
        self.log("🔍 Step 4: Testing credit check functionality...")
        
        # Test cld_generate action (cost=3)
        payload = {"action": "cld_generate"}
        response = self.session.post(f"{BASE_URL}/payments/check-credits", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            cost = data.get("cost")
            sufficient = data.get("sufficient")
            available = data.get("available")
            
            self.log(f"✅ Credit check for cld_generate:")
            self.log(f"   Cost: {cost}, Available: {available}, Sufficient: {sufficient}")
            
            if cost == 3 and sufficient == True:
                self.log("   ✅ Credit check working correctly")
            else:
                self.log("   ❌ Credit check values incorrect")
                return False
        else:
            self.log(f"❌ Credit check failed: {response.status_code} - {response.text}")
            return False
            
        # Test decision_analyze action (cost=2)
        payload = {"action": "decision_analyze"}
        response = self.session.post(f"{BASE_URL}/payments/check-credits", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            cost = data.get("cost")
            
            self.log(f"✅ Credit check for decision_analyze: cost={cost}")
            
            if cost == 2:
                self.log("   ✅ Decision analyze cost correct")
                return True
            else:
                self.log("   ❌ Decision analyze cost incorrect")
                return False
        else:
            self.log(f"❌ Decision analyze credit check failed: {response.status_code} - {response.text}")
            return False
            
    def test_topup_order_creation(self):
        """Step 5: Test top-up order creation (creates real Razorpay order)"""
        self.log("🛒 Step 5: Testing top-up order creation...")
        
        payload = {"pack_id": "micro"}
        response = self.session.post(f"{BASE_URL}/payments/create-topup-order", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            order_id = data.get("order_id")
            amount = data.get("amount")
            key_id = data.get("key_id")
            pack = data.get("pack", {})
            
            self.log(f"✅ Top-up order created successfully:")
            self.log(f"   Order ID: {order_id}")
            self.log(f"   Amount: {amount} paise")
            self.log(f"   Key ID: {key_id}")
            self.log(f"   Pack: {pack.get('name')} ({pack.get('credits')} credits)")
            
            # Store order_id for payment verification
            self.topup_order_id = order_id
            self.topup_pack_credits = pack.get("credits", 0)
            
            if order_id and amount == 2900 and key_id:
                self.log("   ✅ Order creation successful with correct values")
                return True
            else:
                self.log("   ❌ Order creation values incorrect")
                return False
        else:
            self.log(f"❌ Top-up order creation failed: {response.status_code} - {response.text}")
            return False
            
    def test_subscription_order_creation(self):
        """Step 6: Test subscription order creation"""
        self.log("📅 Step 6: Testing subscription order creation...")
        
        payload = {"plan_id": "starter"}
        response = self.session.post(f"{BASE_URL}/payments/create-subscription", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            order_id = data.get("order_id")
            amount = data.get("amount")
            plan = data.get("plan", {})
            
            self.log(f"✅ Subscription order created successfully:")
            self.log(f"   Order ID: {order_id}")
            self.log(f"   Amount: {amount} paise")
            self.log(f"   Plan: {plan.get('name')} ({plan.get('credits_per_month')} credits/month)")
            
            # Store order_id for webhook testing
            self.subscription_order_id = order_id
            self.subscription_plan_credits = plan.get("credits_per_month", 0)
            
            if order_id and amount == 14900:
                self.log("   ✅ Subscription order creation successful")
                return True
            else:
                self.log("   ❌ Subscription order values incorrect")
                return False
        else:
            self.log(f"❌ Subscription order creation failed: {response.status_code} - {response.text}")
            return False
            
    def test_payment_verification(self):
        """Step 7: Test payment verification with simulated signature"""
        self.log("✅ Step 7: Testing payment verification...")
        
        if not hasattr(self, 'topup_order_id'):
            self.log("❌ No top-up order ID available for verification")
            return False
            
        # Simulate payment verification
        fake_payment_id = "pay_simulated_test"
        
        # Calculate HMAC-SHA256 signature as specified in review request
        signature_payload = f"{self.topup_order_id}|{fake_payment_id}"
        signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode('utf-8'),
            signature_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        payload = {
            "razorpay_order_id": self.topup_order_id,
            "razorpay_payment_id": fake_payment_id,
            "razorpay_signature": signature
        }
        
        response = self.session.post(f"{BASE_URL}/payments/verify", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            message = data.get("message")
            credits_added = data.get("credits_added")
            wallet = data.get("wallet", {})
            
            self.log(f"✅ Payment verification successful:")
            self.log(f"   Message: {message}")
            self.log(f"   Credits added: {credits_added}")
            self.log(f"   New wallet balance: {wallet.get('credits')}")
            
            # Verify credits were added correctly (100 initial + 50 micro pack = 150)
            expected_credits = 100 + self.topup_pack_credits
            if wallet.get("credits") == expected_credits and credits_added == self.topup_pack_credits:
                self.log(f"   ✅ Credits added correctly: {expected_credits} total")
                return True
            else:
                self.log(f"   ❌ Credits not added correctly. Expected: {expected_credits}, Got: {wallet.get('credits')}")
                return False
        else:
            self.log(f"❌ Payment verification failed: {response.status_code} - {response.text}")
            return False
            
    def test_wallet_after_payment(self):
        """Step 8: Verify wallet state after payment"""
        self.log("💳 Step 8: Verifying wallet after payment...")
        
        response = self.session.get(f"{BASE_URL}/payments/wallet")
        
        if response.status_code == 200:
            wallet = response.json()
            credits = wallet.get("credits")
            total_purchased = wallet.get("total_purchased")
            
            self.log(f"✅ Wallet state after payment:")
            self.log(f"   Credits: {credits}")
            self.log(f"   Total purchased: {total_purchased}")
            
            # Should have 150 credits (100 initial + 50 micro pack) and 50 total purchased
            if credits == 150 and total_purchased == 50:
                self.log("   ✅ Wallet state correct after payment")
                return True
            else:
                self.log("   ❌ Wallet state incorrect after payment")
                return False
        else:
            self.log(f"❌ Wallet check failed: {response.status_code} - {response.text}")
            return False
            
    def test_payment_history(self):
        """Step 9: Test payment history"""
        self.log("📊 Step 9: Testing payment history...")
        
        response = self.session.get(f"{BASE_URL}/payments/history")
        
        if response.status_code == 200:
            data = response.json()
            transactions = data.get("transactions", [])
            
            self.log(f"✅ Payment history retrieved: {len(transactions)} transactions")
            
            # Should have at least 2 transactions: initial grant + purchase
            if len(transactions) >= 2:
                for i, tx in enumerate(transactions[:3]):  # Show first 3
                    tx_type = tx.get("type")
                    credits = tx.get("credits")
                    description = tx.get("description", "")
                    self.log(f"   Transaction {i+1}: {tx_type} - {credits} credits - {description}")
                    
                # Verify we have both grant and purchase transactions
                tx_types = [tx.get("type") for tx in transactions]
                if "grant" in tx_types and "purchase" in tx_types:
                    self.log("   ✅ Both initial grant and purchase transactions found")
                    return True
                else:
                    self.log("   ❌ Missing expected transaction types")
                    return False
            else:
                self.log("   ❌ Insufficient transaction history")
                return False
        else:
            self.log(f"❌ Payment history failed: {response.status_code} - {response.text}")
            return False
            
    def test_webhook_simulation(self):
        """Step 10: Test webhook simulation for subscription"""
        self.log("🔗 Step 10: Testing webhook simulation...")
        
        if not hasattr(self, 'subscription_order_id'):
            self.log("❌ No subscription order ID available for webhook")
            return False
            
        # Simulate webhook payload for payment.captured event
        webhook_payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_webhook_test",
                        "order_id": self.subscription_order_id,
                        "status": "captured"
                    }
                }
            }
        }
        
        # Remove Authorization header for webhook (no auth required)
        headers = self.session.headers.copy()
        if "Authorization" in headers:
            del headers["Authorization"]
            
        response = requests.post(
            f"{BASE_URL}/payments/webhook", 
            json=webhook_payload,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            
            self.log(f"✅ Webhook processed successfully: {status}")
            
            # Check if credits were added (this might not happen immediately)
            time.sleep(1)  # Brief delay
            wallet_response = self.session.get(f"{BASE_URL}/payments/wallet")
            if wallet_response.status_code == 200:
                wallet = wallet_response.json()
                credits = wallet.get("credits")
                self.log(f"   Wallet credits after webhook: {credits}")
                
            return True
        else:
            self.log(f"❌ Webhook simulation failed: {response.status_code} - {response.text}")
            return False
            
    def test_credit_deduction(self):
        """Step 11: Test credit deduction (indirect test)"""
        self.log("💸 Step 11: Testing credit deduction...")
        
        # Test time_store_analyze action (cost=5, sufficient=true with 150+ credits)
        payload = {"action": "time_store_analyze"}
        response = self.session.post(f"{BASE_URL}/payments/check-credits", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            cost = data.get("cost")
            sufficient = data.get("sufficient")
            available = data.get("available")
            
            self.log(f"✅ Credit deduction check for time_store_analyze:")
            self.log(f"   Cost: {cost}, Available: {available}, Sufficient: {sufficient}")
            
            if cost == 5 and sufficient == True:
                self.log("   ✅ Credit deduction check working correctly")
                return True
            else:
                self.log("   ❌ Credit deduction check failed")
                return False
        else:
            self.log(f"❌ Credit deduction check failed: {response.status_code} - {response.text}")
            return False
            
    def test_admin_initial_credits(self):
        """Step 12: Test admin initial credits endpoints"""
        self.log("👑 Step 12: Testing admin initial credits...")
        
        # Test PUT (should fail for non-admin)
        payload = {"initial_credits": 200}
        response = self.session.put(f"{BASE_URL}/payments/admin/initial-credits", json=payload)
        
        if response.status_code == 403:
            self.log("✅ PUT admin initial credits correctly denied for non-admin user")
        else:
            self.log(f"❌ PUT admin initial credits should have returned 403, got: {response.status_code}")
            return False
            
        # Test GET (should work)
        response = self.session.get(f"{BASE_URL}/payments/admin/initial-credits")
        
        if response.status_code == 200:
            data = response.json()
            initial_credits = data.get("initial_credits")
            
            self.log(f"✅ GET admin initial credits successful: {initial_credits}")
            
            if isinstance(initial_credits, int) and initial_credits >= 0:
                self.log("   ✅ Initial credits value is valid")
                return True
            else:
                self.log("   ❌ Initial credits value is invalid")
                return False
        else:
            self.log(f"❌ GET admin initial credits failed: {response.status_code} - {response.text}")
            return False
            
    def run_all_tests(self):
        """Run all payment flow tests"""
        self.log("🚀 Starting Razorpay E2E Payment Flow Testing...")
        self.log(f"Backend URL: {BASE_URL}")
        self.log(f"Test Email: {self.test_email}")
        self.log("=" * 80)
        
        tests = [
            ("User Registration", self.test_user_registration),
            ("Pricing & Plans (Public)", self.test_pricing_plans),
            ("Wallet Auto-creation", self.test_wallet_creation),
            ("Credit Check", self.test_credit_check),
            ("Top-up Order Creation", self.test_topup_order_creation),
            ("Subscription Order Creation", self.test_subscription_order_creation),
            ("Payment Verification", self.test_payment_verification),
            ("Wallet After Payment", self.test_wallet_after_payment),
            ("Payment History", self.test_payment_history),
            ("Webhook Simulation", self.test_webhook_simulation),
            ("Credit Deduction Check", self.test_credit_deduction),
            ("Admin Initial Credits", self.test_admin_initial_credits),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            self.log(f"\n{'='*20} {test_name} {'='*20}")
            try:
                if test_func():
                    passed += 1
                    self.log(f"✅ {test_name} PASSED")
                else:
                    failed += 1
                    self.log(f"❌ {test_name} FAILED")
            except Exception as e:
                failed += 1
                self.log(f"❌ {test_name} FAILED with exception: {str(e)}")
                
        self.log("\n" + "="*80)
        self.log(f"🎯 RAZORPAY E2E PAYMENT FLOW TESTING COMPLETE")
        self.log(f"✅ Passed: {passed}")
        self.log(f"❌ Failed: {failed}")
        self.log(f"📊 Success Rate: {(passed/(passed+failed)*100):.1f}%")
        
        if failed == 0:
            self.log("🎉 ALL TESTS PASSED! Razorpay payment flow is working correctly.")
        else:
            self.log(f"⚠️  {failed} test(s) failed. Please review the failures above.")
            
        return passed, failed

if __name__ == "__main__":
    tester = RazorpayPaymentTester()
    tester.run_all_tests()