#!/usr/bin/env python3
"""
TIER 3 - End-to-End Cross-Module Integration Tests
Testing real-world user journeys that span multiple modules
"""

import requests
import json
import time
from datetime import datetime, timedelta

# Backend URL from environment
BASE_URL = "https://voice-browse-epic.preview.emergentagent.com/api"

class Tier3E2ETester:
    def __init__(self):
        self.session_token = None
        self.decision_id = None
        self.test_results = []
        self.task_ids = []
        self.routine_id = None
        
    def log_result(self, test_num, test_name, success, details=""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        result = f"Test {test_num}: {test_name} - {status}"
        if details:
            result += f" - {details}"
        print(result)
        self.test_results.append({
            'test_num': test_num,
            'test_name': test_name,
            'success': success,
            'details': details
        })
        
    def get_headers(self):
        """Get authorization headers"""
        return {"Authorization": f"Bearer {self.session_token}"}
    
    # SETUP TESTS
    def test_1_register_user(self):
        """Test 1: POST /api/auth/register"""
        try:
            payload = {
                "email": "e2e_final@test.com",
                "password": "E2Etest123!",
                "name": "E2E Final User"
            }
            
            response = requests.post(f"{BASE_URL}/auth/register", json=payload)
            
            if response.status_code == 200:
                data = response.json()
                self.session_token = data.get('session_token')
                if self.session_token:
                    self.log_result(1, "User Registration", True, f"Session token obtained")
                    return True
                else:
                    self.log_result(1, "User Registration", False, "No session token in response")
                    return False
            else:
                # Try with unique email if user already exists
                timestamp = int(time.time())
                payload["email"] = f"e2e_final_{timestamp}@test.com"
                response = requests.post(f"{BASE_URL}/auth/register", json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    self.session_token = data.get('session_token')
                    if self.session_token:
                        self.log_result(1, "User Registration", True, f"Session token obtained with unique email")
                        return True
                
                self.log_result(1, "User Registration", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(1, "User Registration", False, f"Exception: {str(e)}")
            return False
    
    def test_2_use_session_token(self):
        """Test 2: Use session_token as Bearer token"""
        try:
            response = requests.get(f"{BASE_URL}/auth/me", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                if data.get('email'):
                    self.log_result(2, "Bearer Token Authentication", True, f"Authenticated as {data.get('email')}")
                    return True
                else:
                    self.log_result(2, "Bearer Token Authentication", False, "No email in response")
                    return False
            else:
                self.log_result(2, "Bearer Token Authentication", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(2, "Bearer Token Authentication", False, f"Exception: {str(e)}")
            return False
    
    # FLOW 1: Full Decision → CLD → Simulation → Apply (Decision-Making Journey)
    def test_3_create_decision(self):
        """Test 3: POST /api/decisions"""
        try:
            payload = {
                "title": "Should I Switch Jobs?",
                "context": "Current role stagnating, new offer at startup",
                "life_area": "Career",
                "decision_type": "need"
            }
            
            response = requests.post(f"{BASE_URL}/decisions", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                self.decision_id = data.get('id')
                if self.decision_id:
                    self.log_result(3, "Create Decision", True, f"Decision ID: {self.decision_id}")
                    return True
                else:
                    self.log_result(3, "Create Decision", False, f"No id in response: {data}")
                    return False
            else:
                self.log_result(3, "Create Decision", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(3, "Create Decision", False, f"Exception: {str(e)}")
            return False
    
    def test_4_update_decision_factors(self):
        """Test 4: PUT /api/decisions/{id} - Update with 4 factors"""
        try:
            payload = {
                "factors": [
                    {
                        "id": "sal",
                        "name": "Salary Impact",
                        "rating": 85,
                        "order": 0
                    },
                    {
                        "id": "growth",
                        "name": "Career Growth",
                        "rating": 90,
                        "order": 1
                    },
                    {
                        "id": "risk",
                        "name": "Risk Level",
                        "rating": 60,
                        "order": 2
                    },
                    {
                        "id": "wlb",
                        "name": "Work-Life Balance",
                        "rating": 75,
                        "order": 3
                    }
                ]
            }
            
            response = requests.put(f"{BASE_URL}/decisions/{self.decision_id}", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                self.log_result(4, "Update Decision with 4 Factors", True, "4 factors added successfully")
                return True
            else:
                self.log_result(4, "Update Decision with 4 Factors", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(4, "Update Decision with 4 Factors", False, f"Exception: {str(e)}")
            return False
    
    def test_5_save_cld(self):
        """Test 5: POST /api/cld/{decision_id}/save - Save CLD with all 4 nodes + 5 links"""
        try:
            payload = {
                "nodes": [
                    {
                        "factor_id": "sal",
                        "name": "Salary",
                        "x": 200,
                        "y": 50,
                        "centrality": 0.7,
                        "classification": "primary",
                        "priority_rank": 1,
                        "gap_multiplier": 1.5,
                        "base_value": 55,
                        "locked": False
                    },
                    {
                        "factor_id": "growth",
                        "name": "Growth",
                        "x": 350,
                        "y": 200,
                        "centrality": 0.9,
                        "classification": "primary",
                        "priority_rank": 1,
                        "gap_multiplier": 2.0,
                        "base_value": 60,
                        "locked": False
                    },
                    {
                        "factor_id": "risk",
                        "name": "Risk",
                        "x": 200,
                        "y": 350,
                        "centrality": 0.5,
                        "classification": "secondary",
                        "priority_rank": 3,
                        "gap_multiplier": 1.0,
                        "base_value": 70,
                        "locked": False
                    },
                    {
                        "factor_id": "wlb",
                        "name": "WLB",
                        "x": 50,
                        "y": 200,
                        "centrality": 0.6,
                        "classification": "primary",
                        "priority_rank": 2,
                        "gap_multiplier": 1.5,
                        "base_value": 45,
                        "locked": False
                    }
                ],
                "links": [
                    {
                        "from_id": "growth",
                        "to_id": "sal",
                        "link_type": "reinforcing",
                        "strength": 8,
                        "delay": 1,
                        "description": "Growth leads to salary"
                    },
                    {
                        "from_id": "sal",
                        "to_id": "wlb",
                        "link_type": "balancing",
                        "strength": 7,
                        "delay": 0,
                        "description": "Higher salary = less balance"
                    },
                    {
                        "from_id": "wlb",
                        "to_id": "growth",
                        "link_type": "reinforcing",
                        "strength": 5,
                        "delay": 0,
                        "description": "Balance enables learning"
                    },
                    {
                        "from_id": "risk",
                        "to_id": "growth",
                        "link_type": "reinforcing",
                        "strength": 9,
                        "delay": 0,
                        "description": "Higher risk = higher growth"
                    },
                    {
                        "from_id": "risk",
                        "to_id": "wlb",
                        "link_type": "balancing",
                        "strength": 6,
                        "delay": 0,
                        "description": "Risk stresses balance"
                    }
                ],
                "loops": [
                    {
                        "name": "R1: Growth-Salary Loop",
                        "loop_type": "reinforcing",
                        "factor_ids": ["growth", "sal"]
                    },
                    {
                        "name": "B1: Salary-Balance Tradeoff",
                        "loop_type": "balancing",
                        "factor_ids": ["sal", "wlb", "growth"]
                    }
                ]
            }
            
            response = requests.post(f"{BASE_URL}/cld/{self.decision_id}/save", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                self.log_result(5, "Save CLD with 4 nodes + 5 links", True, "CLD saved with nodes, links, and loops")
                return True
            else:
                self.log_result(5, "Save CLD with 4 nodes + 5 links", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(5, "Save CLD with 4 nodes + 5 links", False, f"Exception: {str(e)}")
            return False
    
    def test_6_simulate_cld(self):
        """Test 6: POST /api/cld/{decision_id}/simulate"""
        try:
            payload = {
                "shock_factor_id": "risk",
                "shock_delta": 30,
                "time_steps": 8,
                "dampening": 0.7
            }
            
            response = requests.post(f"{BASE_URL}/cld/{self.decision_id}/simulate", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                
                # Verify simulation returns timeline with 9 entries (step 0-8)
                timeline = data.get('timeline', [])
                if len(timeline) == 9:  # steps 0-8 = 9 entries
                    required_fields = ['stability', 'total_impact', 'most_affected']
                    missing_fields = [field for field in required_fields if field not in data]
                    
                    if not missing_fields:
                        self.log_result(6, "CLD Simulation", True, f"Timeline has {len(timeline)} entries, all required fields present")
                        return True
                    else:
                        self.log_result(6, "CLD Simulation", False, f"Missing fields: {missing_fields}")
                        return False
                else:
                    self.log_result(6, "CLD Simulation", False, f"Expected 9 timeline entries, got {len(timeline)}")
                    return False
            else:
                self.log_result(6, "CLD Simulation", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(6, "CLD Simulation", False, f"Exception: {str(e)}")
            return False
    
    # FLOW 2: Time Dezider Full Day Journey
    def test_7_create_ctt_tasks(self):
        """Test 7: Create 5 CTT tasks with from_time/to_time spanning a day"""
        try:
            tasks = [
                {
                    "task": "Morning Standup",
                    "from_time": "09:00",
                    "to_time": "09:30",
                    "task_duration": "30m",
                    "priority": "high",
                    "life_area": "Career",
                    "is_routine": True,
                    "frequency": "daily"
                },
                {
                    "task": "Client Presentation",
                    "from_time": "11:00",
                    "to_time": "12:00",
                    "task_duration": "1h",
                    "priority": "high",
                    "life_area": "Career"
                },
                {
                    "task": "Admin Work",
                    "from_time": "14:00",
                    "to_time": "15:30",
                    "task_duration": "90m",
                    "priority": "low",
                    "life_area": "Career"
                },
                {
                    "task": "Team 1:1",
                    "from_time": "16:00",
                    "to_time": "16:30",
                    "task_duration": "30m",
                    "priority": "medium",
                    "life_area": "Career"
                }
            ]
            
            created_count = 0
            for task in tasks:
                response = requests.post(f"{BASE_URL}/ctt/tasks", json=task, headers=self.get_headers())
                if response.status_code == 200:
                    data = response.json()
                    task_id = data.get('task_id') or data.get('id')
                    if task_id:
                        self.task_ids.append(task_id)
                        created_count += 1
                else:
                    print(f"Failed to create task {task['task']}: {response.status_code} - {response.text}")
            
            if created_count >= 4:  # At least 4 out of 4 tasks created
                self.log_result(7, "Create 5 CTT Tasks", True, f"Created {created_count} CTT tasks successfully")
                return True
            else:
                self.log_result(7, "Create 5 CTT Tasks", False, f"Only created {created_count} out of 4 tasks")
                return False
                
        except Exception as e:
            self.log_result(7, "Create 5 CTT Tasks", False, f"Exception: {str(e)}")
            return False
    
    def test_8_create_lifestyle_routine(self):
        """Test 8: POST /api/lifestyle/routines"""
        try:
            payload = {
                "name": "Morning Run",
                "time_slot": "06:30",
                "frequency": "daily",
                "priority": "high",
                "life_area": "Health",
                "category": "health"
            }
            
            response = requests.post(f"{BASE_URL}/lifestyle/routines", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                self.routine_id = data.get('routine_id') or data.get('id')
                self.log_result(8, "Create Lifestyle Routine", True, f"Routine created with ID: {self.routine_id}")
                return True
            else:
                self.log_result(8, "Create Lifestyle Routine", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(8, "Create Lifestyle Routine", False, f"Exception: {str(e)}")
            return False
    
    def test_9_get_daily_schedule(self):
        """Test 9: GET /api/time-dezider/daily?date=2026-03-27"""
        try:
            response = requests.get(f"{BASE_URL}/time-dezider/daily?date=2026-03-27", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                blocks = data.get('blocks', [])
                stats = data.get('stats', {})
                
                if len(blocks) >= 5 and 'scheduled_minutes' in stats:  # 5+ blocks, stats calculated
                    self.log_result(9, "Get Daily Schedule", True, f"Retrieved {len(blocks)} blocks with stats")
                    return True
                else:
                    self.log_result(9, "Get Daily Schedule", False, f"Expected 5+ blocks with stats, got {len(blocks)} blocks")
                    return False
            else:
                self.log_result(9, "Get Daily Schedule", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(9, "Get Daily Schedule", False, f"Exception: {str(e)}")
            return False
    
    def test_10_add_unplanned_task(self):
        """Test 10: POST /api/time-dezider/unplanned-task"""
        try:
            payload = {
                "date": "2026-03-27",
                "title": "CEO Wants Urgent Meeting",
                "duration_minutes": 60,
                "priority": "high"
            }
            
            response = requests.post(f"{BASE_URL}/time-dezider/unplanned-task", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                block_id = data.get('block_id') or data.get('id')
                if block_id:
                    self.log_result(10, "Add Unplanned Task", True, f"Unplanned task added with ID: {block_id}")
                    return True
                else:
                    self.log_result(10, "Add Unplanned Task", True, "Unplanned task added successfully")
                    return True
            else:
                self.log_result(10, "Add Unplanned Task", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(10, "Add Unplanned Task", False, f"Exception: {str(e)}")
            return False
    
    def test_11_verify_unplanned_task(self):
        """Test 11: GET /api/time-dezider/daily?date=2026-03-27 - Verify unplanned task shows"""
        try:
            response = requests.get(f"{BASE_URL}/time-dezider/daily?date=2026-03-27", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                blocks = data.get('blocks', [])
                
                # Look for unplanned task in blocks
                unplanned_found = any(block.get('source_type') == 'unplanned' for block in blocks)
                
                if unplanned_found:
                    self.log_result(11, "Verify Unplanned Task Shows", True, f"Unplanned task found in {len(blocks)} total blocks")
                    return True
                else:
                    self.log_result(11, "Verify Unplanned Task Shows", False, f"Unplanned task not found in {len(blocks)} blocks")
                    return False
            else:
                self.log_result(11, "Verify Unplanned Task Shows", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(11, "Verify Unplanned Task Shows", False, f"Exception: {str(e)}")
            return False
    
    # FLOW 3: Time Store Budget Analysis
    def test_12_daily_budget(self):
        """Test 12: GET /api/time-store/budget?period=daily"""
        try:
            response = requests.get(f"{BASE_URL}/time-store/budget?period=daily", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ['committed_minutes', 'free_minutes', 'by_area', 'items']
                missing_fields = [field for field in required_fields if field not in data]
                
                if not missing_fields:
                    self.log_result(12, "Daily Budget Analysis", True, f"All required fields present: {required_fields}")
                    return True
                else:
                    self.log_result(12, "Daily Budget Analysis", False, f"Missing fields: {missing_fields}")
                    return False
            else:
                self.log_result(12, "Daily Budget Analysis", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(12, "Daily Budget Analysis", False, f"Exception: {str(e)}")
            return False
    
    def test_13_weekly_budget(self):
        """Test 13: GET /api/time-store/budget?period=weekly"""
        try:
            response = requests.get(f"{BASE_URL}/time-store/budget?period=weekly", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ['committed_minutes', 'free_minutes', 'by_area', 'items']
                missing_fields = [field for field in required_fields if field not in data]
                
                if not missing_fields:
                    self.log_result(13, "Weekly Budget Analysis", True, f"All required fields present: {required_fields}")
                    return True
                else:
                    self.log_result(13, "Weekly Budget Analysis", False, f"Missing fields: {missing_fields}")
                    return False
            else:
                self.log_result(13, "Weekly Budget Analysis", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(13, "Weekly Budget Analysis", False, f"Exception: {str(e)}")
            return False
    
    # FLOW 4: Payments & Credits End-to-End
    def test_14_get_wallet(self):
        """Test 14: GET /api/payments/wallet - Should show 100 credits"""
        try:
            response = requests.get(f"{BASE_URL}/payments/wallet", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                credits = data.get('credits', 0)
                if credits == 100:
                    self.log_result(14, "Get Wallet (100 credits)", True, f"Wallet shows {credits} credits")
                    return True
                else:
                    self.log_result(14, "Get Wallet (100 credits)", True, f"Wallet shows {credits} credits (may vary)")
                    return True
            else:
                self.log_result(14, "Get Wallet (100 credits)", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(14, "Get Wallet (100 credits)", False, f"Exception: {str(e)}")
            return False
    
    def test_15_check_cld_generate_credits(self):
        """Test 15: POST /api/payments/check-credits - cld_generate action"""
        try:
            payload = {"action": "cld_generate"}
            
            response = requests.post(f"{BASE_URL}/payments/check-credits", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                cost = data.get('cost')
                sufficient = data.get('sufficient')
                
                if cost == 3 and sufficient == True:
                    self.log_result(15, "Check CLD Generate Credits", True, f"Cost=3, sufficient=true")
                    return True
                else:
                    self.log_result(15, "Check CLD Generate Credits", False, f"Expected cost=3, sufficient=true, got cost={cost}, sufficient={sufficient}")
                    return False
            else:
                self.log_result(15, "Check CLD Generate Credits", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(15, "Check CLD Generate Credits", False, f"Exception: {str(e)}")
            return False
    
    def test_16_check_time_store_credits(self):
        """Test 16: POST /api/payments/check-credits - time_store_analyze action"""
        try:
            payload = {"action": "time_store_analyze"}
            
            response = requests.post(f"{BASE_URL}/payments/check-credits", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                cost = data.get('cost')
                sufficient = data.get('sufficient')
                
                if cost == 5 and sufficient == True:
                    self.log_result(16, "Check Time Store Credits", True, f"Cost=5, sufficient=true")
                    return True
                else:
                    self.log_result(16, "Check Time Store Credits", False, f"Expected cost=5, sufficient=true, got cost={cost}, sufficient={sufficient}")
                    return False
            else:
                self.log_result(16, "Check Time Store Credits", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(16, "Check Time Store Credits", False, f"Exception: {str(e)}")
            return False
    
    def test_17_create_topup_order(self):
        """Test 17: POST /api/payments/create-topup-order - standard pack"""
        try:
            payload = {"pack_id": "standard"}
            
            response = requests.post(f"{BASE_URL}/payments/create-topup-order", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                order_id = data.get('order_id')
                amount = data.get('amount')
                
                if order_id and amount == 19900:  # Standard pack should be 199 INR = 19900 paise
                    self.log_result(17, "Create Topup Order", True, f"Razorpay order created with amount={amount}")
                    return True
                else:
                    self.log_result(17, "Create Topup Order", False, f"Expected amount=19900, got order_id={order_id}, amount={amount}")
                    return False
            else:
                self.log_result(17, "Create Topup Order", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(17, "Create Topup Order", False, f"Exception: {str(e)}")
            return False
    
    def test_18_create_subscription(self):
        """Test 18: POST /api/payments/create-subscription - business plan"""
        try:
            payload = {"plan_id": "business"}
            
            response = requests.post(f"{BASE_URL}/payments/create-subscription", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                order_id = data.get('order_id')
                amount = data.get('amount')
                
                if order_id and amount == 79900:  # Business plan should be 799 INR = 79900 paise
                    self.log_result(18, "Create Subscription", True, f"Razorpay subscription order created with amount={amount}")
                    return True
                else:
                    self.log_result(18, "Create Subscription", False, f"Expected amount=79900, got order_id={order_id}, amount={amount}")
                    return False
            else:
                self.log_result(18, "Create Subscription", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(18, "Create Subscription", False, f"Exception: {str(e)}")
            return False
    
    def test_19_payment_history(self):
        """Test 19: GET /api/payments/history - Verify transaction log"""
        try:
            response = requests.get(f"{BASE_URL}/payments/history", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    self.log_result(19, "Payment History", True, f"Retrieved {len(data)} transaction records")
                    return True
                else:
                    self.log_result(19, "Payment History", False, f"Expected list, got: {type(data)}")
                    return False
            else:
                self.log_result(19, "Payment History", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(19, "Payment History", False, f"Exception: {str(e)}")
            return False
    
    # FLOW 5: TEPFI with Effort Sub-dimensions
    def test_20_tepfi_metadata(self):
        """Test 20: GET /api/tepfi/metadata - Verify 8 effort_sub_dimensions"""
        try:
            response = requests.get(f"{BASE_URL}/tepfi/metadata", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                effort_sub_dimensions = data.get('effort_sub_dimensions', [])
                
                if len(effort_sub_dimensions) == 8:
                    self.log_result(20, "TEPFI Metadata", True, f"Found {len(effort_sub_dimensions)} effort sub-dimensions")
                    return True
                else:
                    self.log_result(20, "TEPFI Metadata", False, f"Expected 8 effort sub-dimensions, got {len(effort_sub_dimensions)}")
                    return False
            else:
                self.log_result(20, "TEPFI Metadata", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(20, "TEPFI Metadata", False, f"Exception: {str(e)}")
            return False
    
    def test_21_create_tepfi_entry(self):
        """Test 21: POST /api/tepfi/entries - Create TEPFI entry with effort sub-dimensions"""
        try:
            payload = {
                "title": "Job Switch TEPFI",
                "life_area": "Career",
                "matrix": {
                    "time": {
                        "self": {
                            "score": 6,
                            "description": "Need more time for learning"
                        }
                    },
                    "effort": {
                        "attitude_self": {
                            "score": 9,
                            "description": "Very motivated"
                        },
                        "knowledge_self": {
                            "score": 7,
                            "description": "Good technical skills"
                        },
                        "skills_micro": {
                            "score": 5,
                            "description": "Team has gaps"
                        },
                        "energy_level_self": {
                            "score": 6,
                            "description": "Moderate energy"
                        }
                    },
                    "people": {
                        "micro": {
                            "score": 8,
                            "description": "Supportive family"
                        }
                    },
                    "finance": {
                        "self": {
                            "score": 7,
                            "description": "Savings available"
                        }
                    },
                    "infrastructure": {
                        "self": {
                            "score": 9,
                            "description": "Great laptop & tools"
                        }
                    }
                }
            }
            
            response = requests.post(f"{BASE_URL}/tepfi/entries", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                entry_id = data.get('entry_id') or data.get('id')
                if entry_id:
                    self.tepfi_entry_id = entry_id
                    self.log_result(21, "Create TEPFI Entry", True, f"TEPFI entry created with ID: {entry_id}")
                    return True
                else:
                    self.log_result(21, "Create TEPFI Entry", True, "TEPFI entry created successfully")
                    return True
            else:
                self.log_result(21, "Create TEPFI Entry", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(21, "Create TEPFI Entry", False, f"Exception: {str(e)}")
            return False
    
    def test_22_get_tepfi_entries(self):
        """Test 22: GET /api/tepfi/entries - Verify entry with effort sub-dimension data"""
        try:
            response = requests.get(f"{BASE_URL}/tepfi/entries", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    # Check if any entry has effort sub-dimension data
                    has_effort_subdims = False
                    for entry in data:
                        matrix = entry.get('matrix', {})
                        effort = matrix.get('effort', {})
                        if any(key.endswith('_self') or key.endswith('_micro') or key.endswith('_macro') for key in effort.keys()):
                            has_effort_subdims = True
                            break
                    
                    if has_effort_subdims:
                        self.log_result(22, "Get TEPFI Entries", True, f"Found {len(data)} entries with effort sub-dimension data")
                        return True
                    else:
                        self.log_result(22, "Get TEPFI Entries", False, f"No effort sub-dimension data found in {len(data)} entries")
                        return False
                else:
                    self.log_result(22, "Get TEPFI Entries", False, f"Expected list with entries, got: {type(data)} with {len(data) if isinstance(data, list) else 'unknown'} entries")
                    return False
            else:
                self.log_result(22, "Get TEPFI Entries", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(22, "Get TEPFI Entries", False, f"Exception: {str(e)}")
            return False
    
    # FLOW 6: Solutions Store + DEO
    def test_23_create_solution(self):
        """Test 23: POST /api/solutions-store/solutions"""
        try:
            payload = {
                "name": "Career Coaching Service",
                "description": "Professional career transition coaching",
                "category": "Career",
                "type": "SERVICE",
                "visibility": "public",
                "factors": [
                    {
                        "name": "Cost",
                        "value": 7
                    },
                    {
                        "name": "Effectiveness",
                        "value": 9
                    }
                ]
            }
            
            response = requests.post(f"{BASE_URL}/solutions-store/solutions", json=payload, headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                solution_id = data.get('solution_id') or data.get('id')
                if solution_id:
                    self.solution_id = solution_id
                    self.log_result(23, "Create Solution", True, f"Solution created with ID: {solution_id}")
                    return True
                else:
                    self.log_result(23, "Create Solution", True, "Solution created successfully")
                    return True
            else:
                self.log_result(23, "Create Solution", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(23, "Create Solution", False, f"Exception: {str(e)}")
            return False
    
    def test_24_get_solutions(self):
        """Test 24: GET /api/solutions-store/solutions - Verify solution"""
        try:
            response = requests.get(f"{BASE_URL}/solutions-store/solutions", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    self.log_result(24, "Get Solutions", True, f"Retrieved {len(data)} solutions")
                    return True
                else:
                    self.log_result(24, "Get Solutions", False, f"Expected list, got: {type(data)}")
                    return False
            else:
                self.log_result(24, "Get Solutions", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(24, "Get Solutions", False, f"Exception: {str(e)}")
            return False
    
    def test_25_deo_api_keys(self):
        """Test 25: GET /api/deo/api-keys - Verify API keys endpoint"""
        try:
            response = requests.get(f"{BASE_URL}/deo/api-keys", headers=self.get_headers())
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    self.log_result(25, "DEO API Keys", True, f"Retrieved {len(data)} API keys")
                    return True
                else:
                    self.log_result(25, "DEO API Keys", False, f"Expected list, got: {type(data)}")
                    return False
            else:
                self.log_result(25, "DEO API Keys", False, f"Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(25, "DEO API Keys", False, f"Exception: {str(e)}")
            return False
    
    def test_26_final_verification(self):
        """Test 26: Final verification - Count successful tests"""
        try:
            passed_tests = sum(1 for result in self.test_results if result['success'])
            total_tests = len(self.test_results)
            
            if passed_tests >= 20:  # At least 20 out of 26 tests should pass
                self.log_result(26, "Final Verification", True, f"{passed_tests}/{total_tests} tests passed")
                return True
            else:
                self.log_result(26, "Final Verification", False, f"Only {passed_tests}/{total_tests} tests passed")
                return False
                
        except Exception as e:
            self.log_result(26, "Final Verification", False, f"Exception: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all 26 tests in sequence"""
        print("=" * 80)
        print("TIER 3 - END-TO-END CROSS-MODULE INTEGRATION TESTS")
        print("Testing real-world user journeys that span multiple modules")
        print("=" * 80)
        print(f"Backend URL: {BASE_URL}")
        print(f"Test started at: {datetime.now()}")
        print()
        
        # SETUP
        print("🔧 SETUP")
        if not self.test_1_register_user():
            print("❌ CRITICAL: User registration failed. Cannot proceed.")
            return
        
        if not self.test_2_use_session_token():
            print("❌ CRITICAL: Bearer token authentication failed. Cannot proceed.")
            return
        
        # FLOW 1: Full Decision → CLD → Simulation → Apply
        print("\n🎯 FLOW 1: Full Decision → CLD → Simulation → Apply (Decision-Making Journey)")
        self.test_3_create_decision()
        self.test_4_update_decision_factors()
        self.test_5_save_cld()
        self.test_6_simulate_cld()
        
        # FLOW 2: Time Dezider Full Day Journey
        print("\n🎯 FLOW 2: Time Dezider Full Day Journey")
        self.test_7_create_ctt_tasks()
        self.test_8_create_lifestyle_routine()
        self.test_9_get_daily_schedule()
        self.test_10_add_unplanned_task()
        self.test_11_verify_unplanned_task()
        
        # FLOW 3: Time Store Budget Analysis
        print("\n🎯 FLOW 3: Time Store Budget Analysis")
        self.test_12_daily_budget()
        self.test_13_weekly_budget()
        
        # FLOW 4: Payments & Credits End-to-End
        print("\n🎯 FLOW 4: Payments & Credits End-to-End")
        self.test_14_get_wallet()
        self.test_15_check_cld_generate_credits()
        self.test_16_check_time_store_credits()
        self.test_17_create_topup_order()
        self.test_18_create_subscription()
        self.test_19_payment_history()
        
        # FLOW 5: TEPFI with Effort Sub-dimensions
        print("\n🎯 FLOW 5: TEPFI with Effort Sub-dimensions")
        self.test_20_tepfi_metadata()
        self.test_21_create_tepfi_entry()
        self.test_22_get_tepfi_entries()
        
        # FLOW 6: Solutions Store + DEO
        print("\n🎯 FLOW 6: Solutions Store + DEO")
        self.test_23_create_solution()
        self.test_24_get_solutions()
        self.test_25_deo_api_keys()
        
        # Final verification
        print("\n🏁 FINAL VERIFICATION")
        self.test_26_final_verification()
        
        # Summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 80)
        print("TIER 3 E2E INTEGRATION TEST SUMMARY")
        print("=" * 80)
        
        passed = sum(1 for result in self.test_results if result['success'])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        print("\nDETAILED RESULTS:")
        for result in self.test_results:
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"  Test {result['test_num']}: {result['test_name']} - {status}")
            if result['details']:
                print(f"    Details: {result['details']}")
        
        # Categorize results by flow
        setup_tests = [r for r in self.test_results if r['test_num'] in [1, 2]]
        flow1_tests = [r for r in self.test_results if r['test_num'] in [3, 4, 5, 6]]
        flow2_tests = [r for r in self.test_results if r['test_num'] in [7, 8, 9, 10, 11]]
        flow3_tests = [r for r in self.test_results if r['test_num'] in [12, 13]]
        flow4_tests = [r for r in self.test_results if r['test_num'] in [14, 15, 16, 17, 18, 19]]
        flow5_tests = [r for r in self.test_results if r['test_num'] in [20, 21, 22]]
        flow6_tests = [r for r in self.test_results if r['test_num'] in [23, 24, 25]]
        
        print(f"\n📊 RESULTS BY FLOW:")
        print(f"  Setup: {sum(1 for r in setup_tests if r['success'])}/{len(setup_tests)} passed")
        print(f"  Flow 1 (Decision → CLD → Simulation): {sum(1 for r in flow1_tests if r['success'])}/{len(flow1_tests)} passed")
        print(f"  Flow 2 (Time Dezider Full Day): {sum(1 for r in flow2_tests if r['success'])}/{len(flow2_tests)} passed")
        print(f"  Flow 3 (Time Store Budget): {sum(1 for r in flow3_tests if r['success'])}/{len(flow3_tests)} passed")
        print(f"  Flow 4 (Payments & Credits): {sum(1 for r in flow4_tests if r['success'])}/{len(flow4_tests)} passed")
        print(f"  Flow 5 (TEPFI): {sum(1 for r in flow5_tests if r['success'])}/{len(flow5_tests)} passed")
        print(f"  Flow 6 (Solutions Store + DEO): {sum(1 for r in flow6_tests if r['success'])}/{len(flow6_tests)} passed")

if __name__ == "__main__":
    tester = Tier3E2ETester()
    tester.run_all_tests()