"""
Incident Response and Audit Trail System Testing
Tests CERT-In compliant breach notification + user alerting + timeline tracking + audit logging
"""

import requests
import json
import time
from datetime import datetime

# Backend URL from review request
BASE_URL = "https://modal-responsive-fix.preview.emergentagent.com/api"

class IncidentAuditTestRunner:
    def __init__(self):
        self.session_token = None
        self.user_id = None
        self.admin_token = None
        self.admin_user_id = None
        self.incident_id = None
        self.results = []
        
    def log(self, test_name, status, message, details=None):
        """Log test result"""
        result = {
            "test": test_name,
            "status": status,
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.results.append(result)
        status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⏭️"
        print(f"{status_icon} {test_name}: {message}")
        if details:
            print(f"   Details: {json.dumps(details, indent=2)}")
    
    def register_user(self):
        """Register a new test user"""
        timestamp = int(time.time())
        email = f"incident_test_{timestamp}@test.com"
        
        try:
            response = requests.post(
                f"{BASE_URL}/auth/register",
                json={
                    "email": email,
                    "password": "TestPass123!",
                    "name": "Incident Test User"
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self.session_token = data.get("session_token")
                self.user_id = data.get("user_id")
                self.log("User Registration", "PASS", f"Registered user: {email}", 
                        {"user_id": self.user_id, "email": email})
                return True
            else:
                self.log("User Registration", "FAIL", f"Status {response.status_code}", 
                        {"response": response.text})
                return False
        except Exception as e:
            self.log("User Registration", "FAIL", f"Exception: {str(e)}")
            return False
    
    def promote_to_admin(self):
        """Promote user to admin role using admin setup endpoint"""
        try:
            headers = {"Authorization": f"Bearer {self.session_token}"}
            response = requests.post(
                f"{BASE_URL}/admin/setup",
                headers=headers,
                json={},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self.admin_token = self.session_token
                self.admin_user_id = self.user_id
                self.log("Promote to Admin", "PASS", "User promoted to super_admin", 
                        {"role": data.get("role"), "user_id": self.user_id})
                return True
            elif response.status_code == 400:
                # Super admin already exists, need to manually set admin role
                self.log("Promote to Admin", "SKIP", "Super admin already exists - manually setting admin role", 
                        {"message": "Will manually update user role in database"})
                # Manually update the user role in database
                return self.manually_set_admin_role()
            else:
                self.log("Promote to Admin", "FAIL", f"Status {response.status_code}", 
                        {"response": response.text})
                return False
        except Exception as e:
            self.log("Promote to Admin", "FAIL", f"Exception: {str(e)}")
            return False
    
    def manually_set_admin_role(self):
        """Manually set admin role in database using Python script"""
        try:
            import subprocess
            script = f"""
from core.database import db
import asyncio

async def set_admin():
    result = await db.users.update_one(
        {{'user_id': '{self.user_id}'}},
        {{'$set': {{'role': 'admin'}}}}
    )
    print(f'Updated {{result.modified_count}} user(s)')

asyncio.run(set_admin())
"""
            result = subprocess.run(
                ["python3", "-c", script],
                cwd="/app/backend",
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and "Updated 1" in result.stdout:
                self.admin_token = self.session_token
                self.admin_user_id = self.user_id
                self.log("Manually Set Admin Role", "PASS", "User role updated to admin in database", 
                        {"user_id": self.user_id})
                return True
            else:
                self.log("Manually Set Admin Role", "FAIL", "Failed to update user role", 
                        {"stdout": result.stdout, "stderr": result.stderr})
                return False
        except Exception as e:
            self.log("Manually Set Admin Role", "FAIL", f"Exception: {str(e)}")
            return False
    
    def test_incident_config(self):
        """Test GET /api/incidents/config - Should return incident_types, severity_levels, status_flow, certin_email"""
        try:
            headers = {"Authorization": f"Bearer {self.admin_token or self.session_token}"}
            response = requests.get(
                f"{BASE_URL}/incidents/config",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Verify required fields
                required_fields = ["incident_types", "severity_levels", "status_flow", "certin_email"]
                missing_fields = [f for f in required_fields if f not in data]
                
                if not missing_fields:
                    # Verify incident_types array
                    incident_types = data.get("incident_types", [])
                    if "kyc_data_exposure" in incident_types:
                        self.log("Incident Config", "PASS", 
                                "Config endpoint returns all required fields including kyc_data_exposure type",
                                {
                                    "incident_types_count": len(incident_types),
                                    "severity_levels": data.get("severity_levels"),
                                    "status_flow_count": len(data.get("status_flow", [])),
                                    "certin_email": data.get("certin_email"),
                                    "smtp_configured": data.get("smtp_configured"),
                                    "whatsapp_configured": data.get("whatsapp_configured")
                                })
                        return True
                    else:
                        self.log("Incident Config", "FAIL", 
                                "kyc_data_exposure not found in incident_types",
                                {"incident_types": incident_types})
                        return False
                else:
                    self.log("Incident Config", "FAIL", 
                            f"Missing required fields: {missing_fields}",
                            {"response": data})
                    return False
            elif response.status_code == 403:
                self.log("Incident Config", "FAIL", 
                        "Admin access required (403) - user not admin",
                        {"status_code": 403})
                return False
            else:
                self.log("Incident Config", "FAIL", f"Status {response.status_code}", 
                        {"response": response.text})
                return False
        except Exception as e:
            self.log("Incident Config", "FAIL", f"Exception: {str(e)}")
            return False
    
    def test_create_incident(self):
        """Test POST /api/incidents - Create incident with KYC data breach scenario"""
        try:
            headers = {"Authorization": f"Bearer {self.admin_token or self.session_token}"}
            response = requests.post(
                f"{BASE_URL}/incidents",
                headers=headers,
                json={
                    "title": "Test KYC Data Breach",
                    "incident_type": "kyc_data_exposure",
                    "severity": "critical",
                    "description": "Unauthorized access to DigiLocker-verified user data detected via anomalous API calls from unknown IP. Template data may have been exfiltrated.",
                    "affected_systems": ["MongoDB", "DigiLocker API"],
                    "affected_user_count": 150,
                    "kyc_data_involved": True,
                    "initial_actions_taken": "Isolated database, rotated API keys"
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self.incident_id = data.get("id")
                
                # Verify response structure
                if self.incident_id and data.get("status") == "detected":
                    self.log("Create Incident", "PASS", 
                            f"Created critical KYC incident: {self.incident_id}",
                            {
                                "incident_id": self.incident_id,
                                "status": data.get("status"),
                                "auto_escalation": data.get("auto_escalation"),
                                "message": data.get("message")
                            })
                    return True
                else:
                    self.log("Create Incident", "FAIL", 
                            "Response missing incident_id or status",
                            {"response": data})
                    return False
            elif response.status_code == 403:
                self.log("Create Incident", "FAIL", 
                        "Admin access required (403) - user not admin",
                        {"status_code": 403})
                return False
            else:
                self.log("Create Incident", "FAIL", f"Status {response.status_code}", 
                        {"response": response.text})
                return False
        except Exception as e:
            self.log("Create Incident", "FAIL", f"Exception: {str(e)}")
            return False
    
    def test_list_incidents(self):
        """Test GET /api/incidents - List incidents (should include created one)"""
        try:
            headers = {"Authorization": f"Bearer {self.admin_token or self.session_token}"}
            response = requests.get(
                f"{BASE_URL}/incidents",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, list):
                    # Check if our incident is in the list
                    incident_found = any(inc.get("id") == self.incident_id for inc in data)
                    
                    if incident_found:
                        self.log("List Incidents", "PASS", 
                                f"Found {len(data)} incidents including created incident",
                                {
                                    "total_incidents": len(data),
                                    "created_incident_found": True,
                                    "incident_id": self.incident_id
                                })
                        return True
                    else:
                        self.log("List Incidents", "FAIL", 
                                "Created incident not found in list",
                                {"total_incidents": len(data), "incident_id": self.incident_id})
                        return False
                else:
                    self.log("List Incidents", "FAIL", 
                            "Response is not a list",
                            {"response_type": type(data).__name__})
                    return False
            elif response.status_code == 403:
                self.log("List Incidents", "FAIL", 
                        "Admin access required (403) - user not admin",
                        {"status_code": 403})
                return False
            else:
                self.log("List Incidents", "FAIL", f"Status {response.status_code}", 
                        {"response": response.text})
                return False
        except Exception as e:
            self.log("List Incidents", "FAIL", f"Exception: {str(e)}")
            return False
    
    def test_get_incident(self):
        """Test GET /api/incidents/{id} - Get single incident with timeline"""
        try:
            headers = {"Authorization": f"Bearer {self.admin_token or self.session_token}"}
            response = requests.get(
                f"{BASE_URL}/incidents/{self.incident_id}",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Verify required fields
                required_fields = ["id", "title", "incident_type", "severity", "status", "timeline"]
                missing_fields = [f for f in required_fields if f not in data]
                
                if not missing_fields:
                    timeline = data.get("timeline", [])
                    if len(timeline) > 0:
                        self.log("Get Incident", "PASS", 
                                "Retrieved incident with complete details and timeline",
                                {
                                    "incident_id": data.get("id"),
                                    "title": data.get("title"),
                                    "severity": data.get("severity"),
                                    "status": data.get("status"),
                                    "timeline_entries": len(timeline),
                                    "kyc_data_involved": data.get("kyc_data_involved"),
                                    "affected_user_count": data.get("affected_user_count")
                                })
                        return True
                    else:
                        self.log("Get Incident", "FAIL", 
                                "Timeline is empty",
                                {"timeline": timeline})
                        return False
                else:
                    self.log("Get Incident", "FAIL", 
                            f"Missing required fields: {missing_fields}",
                            {"response": data})
                    return False
            elif response.status_code == 403:
                self.log("Get Incident", "FAIL", 
                        "Admin access required (403) - user not admin",
                        {"status_code": 403})
                return False
            elif response.status_code == 404:
                self.log("Get Incident", "FAIL", 
                        "Incident not found (404)",
                        {"incident_id": self.incident_id})
                return False
            else:
                self.log("Get Incident", "FAIL", f"Status {response.status_code}", 
                        {"response": response.text})
                return False
        except Exception as e:
            self.log("Get Incident", "FAIL", f"Exception: {str(e)}")
            return False
    
    def test_update_incident_status(self):
        """Test PUT /api/incidents/{id} - Update status to 'investigating'"""
        try:
            headers = {"Authorization": f"Bearer {self.admin_token or self.session_token}"}
            response = requests.put(
                f"{BASE_URL}/incidents/{self.incident_id}",
                headers=headers,
                json={"status": "investigating"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("id") == self.incident_id:
                    self.log("Update Incident Status", "PASS", 
                            "Updated incident status to 'investigating'",
                            {
                                "incident_id": data.get("id"),
                                "updated_fields": data.get("updated_fields"),
                                "message": data.get("message")
                            })
                    return True
                else:
                    self.log("Update Incident Status", "FAIL", 
                            "Response incident_id mismatch",
                            {"expected": self.incident_id, "got": data.get("id")})
                    return False
            elif response.status_code == 403:
                self.log("Update Incident Status", "FAIL", 
                        "Admin access required (403) - user not admin",
                        {"status_code": 403})
                return False
            elif response.status_code == 404:
                self.log("Update Incident Status", "FAIL", 
                        "Incident not found (404)",
                        {"incident_id": self.incident_id})
                return False
            else:
                self.log("Update Incident Status", "FAIL", f"Status {response.status_code}", 
                        {"response": response.text})
                return False
        except Exception as e:
            self.log("Update Incident Status", "FAIL", f"Exception: {str(e)}")
            return False
    
    def test_notify_certin(self):
        """Test POST /api/incidents/{id}/notify-certin - Should return certin_notified: true, full_report_stored: true"""
        try:
            headers = {"Authorization": f"Bearer {self.admin_token or self.session_token}"}
            response = requests.post(
                f"{BASE_URL}/incidents/{self.incident_id}/notify-certin",
                headers=headers,
                json={},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Verify required fields
                if data.get("certin_notified") == True and data.get("full_report_stored") == True:
                    self.log("Notify CERT-In", "PASS", 
                            "CERT-In report generated and stored (email_sent=false since SMTP not configured)",
                            {
                                "incident_id": data.get("id"),
                                "certin_notified": data.get("certin_notified"),
                                "email_sent": data.get("email_sent"),
                                "full_report_stored": data.get("full_report_stored"),
                                "report_preview": data.get("report_preview", "")[:200] + "...",
                                "message": data.get("message")
                            })
                    return True
                else:
                    self.log("Notify CERT-In", "FAIL", 
                            "certin_notified or full_report_stored not true",
                            {"response": data})
                    return False
            elif response.status_code == 403:
                self.log("Notify CERT-In", "FAIL", 
                        "Admin access required (403) - user not admin",
                        {"status_code": 403})
                return False
            elif response.status_code == 404:
                self.log("Notify CERT-In", "FAIL", 
                        "Incident not found (404)",
                        {"incident_id": self.incident_id})
                return False
            else:
                self.log("Notify CERT-In", "FAIL", f"Status {response.status_code}", 
                        {"response": response.text})
                return False
        except Exception as e:
            self.log("Notify CERT-In", "FAIL", f"Exception: {str(e)}")
            return False
    
    def test_notify_users(self):
        """Test POST /api/incidents/{id}/notify-users - Send with scope: 'all'"""
        try:
            headers = {"Authorization": f"Bearer {self.admin_token or self.session_token}"}
            response = requests.post(
                f"{BASE_URL}/incidents/{self.incident_id}/notify-users",
                headers=headers,
                json={"scope": "all"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Verify required fields
                if data.get("users_notified") == True:
                    self.log("Notify Users", "PASS", 
                            f"User notifications sent successfully to {data.get('total_users')} users",
                            {
                                "incident_id": data.get("id"),
                                "users_notified": data.get("users_notified"),
                                "scope": data.get("scope"),
                                "total_users": data.get("total_users"),
                                "whatsapp_sent": data.get("whatsapp_sent"),
                                "inapp_notifications": data.get("inapp_notifications"),
                                "message": data.get("message")
                            })
                    return True
                else:
                    self.log("Notify Users", "FAIL", 
                            "users_notified not true",
                            {"response": data})
                    return False
            elif response.status_code == 403:
                self.log("Notify Users", "FAIL", 
                        "Admin access required (403) - user not admin",
                        {"status_code": 403})
                return False
            elif response.status_code == 404:
                self.log("Notify Users", "FAIL", 
                        "Incident not found (404)",
                        {"incident_id": self.incident_id})
                return False
            else:
                self.log("Notify Users", "FAIL", f"Status {response.status_code}", 
                        {"response": response.text})
                return False
        except Exception as e:
            self.log("Notify Users", "FAIL", f"Exception: {str(e)}")
            return False
    
    def test_get_certin_report(self):
        """Test GET /api/incidents/{id}/report - Should return full CERT-In report text"""
        try:
            headers = {"Authorization": f"Bearer {self.admin_token or self.session_token}"}
            response = requests.get(
                f"{BASE_URL}/incidents/{self.incident_id}/report",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Verify required fields
                if data.get("report") and data.get("certin_email"):
                    report = data.get("report", "")
                    # Verify report contains key sections
                    required_sections = ["CERT-In INCIDENT REPORT", "INCIDENT DETAILS", "AFFECTED SCOPE", "TIMELINE"]
                    missing_sections = [s for s in required_sections if s not in report]
                    
                    if not missing_sections:
                        self.log("Get CERT-In Report", "PASS", 
                                "Retrieved full CERT-In report with all required sections",
                                {
                                    "incident_id": data.get("incident_id"),
                                    "certin_email": data.get("certin_email"),
                                    "report_length": len(report),
                                    "report_preview": report[:300] + "..."
                                })
                        return True
                    else:
                        self.log("Get CERT-In Report", "FAIL", 
                                f"Report missing sections: {missing_sections}",
                                {"report_preview": report[:500]})
                        return False
                else:
                    self.log("Get CERT-In Report", "FAIL", 
                            "Missing report or certin_email in response",
                            {"response": data})
                    return False
            elif response.status_code == 403:
                self.log("Get CERT-In Report", "FAIL", 
                        "Admin access required (403) - user not admin",
                        {"status_code": 403})
                return False
            elif response.status_code == 404:
                self.log("Get CERT-In Report", "FAIL", 
                        "Incident not found (404)",
                        {"incident_id": self.incident_id})
                return False
            else:
                self.log("Get CERT-In Report", "FAIL", f"Status {response.status_code}", 
                        {"response": response.text})
                return False
        except Exception as e:
            self.log("Get CERT-In Report", "FAIL", f"Exception: {str(e)}")
            return False
    
    def test_get_incident_timeline(self):
        """Test GET /api/incidents/{id}/timeline - Should return timeline entries with SLA compliance"""
        try:
            headers = {"Authorization": f"Bearer {self.admin_token or self.session_token}"}
            response = requests.get(
                f"{BASE_URL}/incidents/{self.incident_id}/timeline",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Verify required fields
                required_fields = ["incident_id", "status", "severity", "timeline", "sla_compliance"]
                missing_fields = [f for f in required_fields if f not in data]
                
                if not missing_fields:
                    timeline = data.get("timeline", [])
                    sla = data.get("sla_compliance", {})
                    
                    if len(timeline) > 0:
                        self.log("Get Incident Timeline", "PASS", 
                                f"Retrieved timeline with {len(timeline)} entries and SLA compliance data",
                                {
                                    "incident_id": data.get("incident_id"),
                                    "status": data.get("status"),
                                    "severity": data.get("severity"),
                                    "timeline_entries": len(timeline),
                                    "sla_compliance": sla,
                                    "notification_log_entries": len(data.get("notification_log", []))
                                })
                        return True
                    else:
                        self.log("Get Incident Timeline", "FAIL", 
                                "Timeline is empty",
                                {"timeline": timeline})
                        return False
                else:
                    self.log("Get Incident Timeline", "FAIL", 
                            f"Missing required fields: {missing_fields}",
                            {"response": data})
                    return False
            elif response.status_code == 403:
                self.log("Get Incident Timeline", "FAIL", 
                        "Admin access required (403) - user not admin",
                        {"status_code": 403})
                return False
            elif response.status_code == 404:
                self.log("Get Incident Timeline", "FAIL", 
                        "Incident not found (404)",
                        {"incident_id": self.incident_id})
                return False
            else:
                self.log("Get Incident Timeline", "FAIL", f"Status {response.status_code}", 
                        {"response": response.text})
                return False
        except Exception as e:
            self.log("Get Incident Timeline", "FAIL", f"Exception: {str(e)}")
            return False
    
    def test_get_audit_trail(self):
        """Test GET /api/audit-trail - Should have entries (from incident creation at minimum)"""
        try:
            headers = {"Authorization": f"Bearer {self.admin_token or self.session_token}"}
            response = requests.get(
                f"{BASE_URL}/audit-trail",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Verify response structure
                if "logs" in data and "total" in data:
                    logs = data.get("logs", [])
                    total = data.get("total", 0)
                    
                    # Check if we have audit logs from incident creation
                    incident_logs = [log for log in logs if log.get("entity_type") == "incident"]
                    
                    if len(incident_logs) > 0:
                        self.log("Get Audit Trail", "PASS", 
                                f"Retrieved {total} audit logs including {len(incident_logs)} incident-related entries",
                                {
                                    "total_logs": total,
                                    "logs_returned": len(logs),
                                    "incident_logs": len(incident_logs),
                                    "sample_actions": [log.get("action") for log in logs[:5]]
                                })
                        return True
                    else:
                        self.log("Get Audit Trail", "FAIL", 
                                "No incident-related audit logs found",
                                {"total_logs": total, "logs_returned": len(logs)})
                        return False
                else:
                    self.log("Get Audit Trail", "FAIL", 
                            "Response missing 'logs' or 'total' field",
                            {"response": data})
                    return False
            elif response.status_code == 403:
                self.log("Get Audit Trail", "FAIL", 
                        "Admin access required (403) - user not admin",
                        {"status_code": 403})
                return False
            else:
                self.log("Get Audit Trail", "FAIL", f"Status {response.status_code}", 
                        {"response": response.text})
                return False
        except Exception as e:
            self.log("Get Audit Trail", "FAIL", f"Exception: {str(e)}")
            return False
    
    def test_get_kyc_audit_trail(self):
        """Test GET /api/audit-trail/kyc - KYC-specific audit logs"""
        try:
            headers = {"Authorization": f"Bearer {self.admin_token or self.session_token}"}
            response = requests.get(
                f"{BASE_URL}/audit-trail/kyc",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Verify response structure
                if "logs" in data and "total" in data:
                    logs = data.get("logs", [])
                    total = data.get("total", 0)
                    
                    self.log("Get KYC Audit Trail", "PASS", 
                            f"Retrieved {total} KYC-specific audit logs",
                            {
                                "total_logs": total,
                                "logs_returned": len(logs),
                                "sample_entity_types": list(set([log.get("entity_type") for log in logs[:10]])) if logs else []
                            })
                    return True
                else:
                    self.log("Get KYC Audit Trail", "FAIL", 
                            "Response missing 'logs' or 'total' field",
                            {"response": data})
                    return False
            elif response.status_code == 403:
                self.log("Get KYC Audit Trail", "FAIL", 
                        "Admin access required (403) - user not admin",
                        {"status_code": 403})
                return False
            else:
                self.log("Get KYC Audit Trail", "FAIL", f"Status {response.status_code}", 
                        {"response": response.text})
                return False
        except Exception as e:
            self.log("Get KYC Audit Trail", "FAIL", f"Exception: {str(e)}")
            return False
    
    def test_get_audit_stats(self):
        """Test GET /api/audit-trail/stats - Should return total_events, sensitive_accesses, kyc_related, last_24h, action_breakdown"""
        try:
            headers = {"Authorization": f"Bearer {self.admin_token or self.session_token}"}
            response = requests.get(
                f"{BASE_URL}/audit-trail/stats",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Verify required fields
                required_fields = ["total_events", "sensitive_accesses", "kyc_related", "last_24h", "action_breakdown"]
                missing_fields = [f for f in required_fields if f not in data]
                
                if not missing_fields:
                    self.log("Get Audit Stats", "PASS", 
                            "Retrieved audit trail statistics with all required fields",
                            {
                                "total_events": data.get("total_events"),
                                "sensitive_accesses": data.get("sensitive_accesses"),
                                "kyc_related": data.get("kyc_related"),
                                "incident_events": data.get("incident_events"),
                                "last_24h": data.get("last_24h"),
                                "action_breakdown_count": len(data.get("action_breakdown", []))
                            })
                    return True
                else:
                    self.log("Get Audit Stats", "FAIL", 
                            f"Missing required fields: {missing_fields}",
                            {"response": data})
                    return False
            elif response.status_code == 403:
                self.log("Get Audit Stats", "FAIL", 
                        "Admin access required (403) - user not admin",
                        {"status_code": 403})
                return False
            else:
                self.log("Get Audit Stats", "FAIL", f"Status {response.status_code}", 
                        {"response": response.text})
                return False
        except Exception as e:
            self.log("Get Audit Stats", "FAIL", f"Exception: {str(e)}")
            return False
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        skipped = sum(1 for r in self.results if r["status"] == "SKIP")
        
        print(f"Total Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⏭️ Skipped: {skipped}")
        print(f"Success Rate: {(passed/total*100):.1f}%" if total > 0 else "N/A")
        
        if failed > 0:
            print("\n" + "="*80)
            print("FAILED TESTS:")
            print("="*80)
            for r in self.results:
                if r["status"] == "FAIL":
                    print(f"❌ {r['test']}: {r['message']}")
                    if r.get("details"):
                        print(f"   {json.dumps(r['details'], indent=2)}")
        
        print("\n" + "="*80)
        return passed, failed, skipped

def main():
    print("="*80)
    print("INCIDENT RESPONSE AND AUDIT TRAIL SYSTEM TESTING")
    print("="*80)
    print(f"Backend URL: {BASE_URL}")
    print(f"Test Started: {datetime.now().isoformat()}")
    print("="*80 + "\n")
    
    runner = IncidentAuditTestRunner()
    
    # Step 1: Register user
    if not runner.register_user():
        print("\n❌ Failed to register user. Aborting tests.")
        return
    
    # Step 2: Promote to admin
    is_admin = runner.promote_to_admin()
    
    if not is_admin:
        print("\n⚠️ User is not admin. Will test endpoints and expect 403 errors.")
    
    # Step 3: Test Incident Config
    runner.test_incident_config()
    
    # Step 4: Create Incident
    if runner.test_create_incident():
        # Step 5: List Incidents
        runner.test_list_incidents()
        
        # Step 6: Get Single Incident
        runner.test_get_incident()
        
        # Step 7: Update Incident Status
        runner.test_update_incident_status()
        
        # Step 8: Notify CERT-In
        runner.test_notify_certin()
        
        # Step 9: Notify Users
        runner.test_notify_users()
        
        # Step 10: Get CERT-In Report
        runner.test_get_certin_report()
        
        # Step 11: Get Incident Timeline
        runner.test_get_incident_timeline()
    else:
        print("\n⚠️ Incident creation failed. Skipping incident-specific tests.")
    
    # Step 12: Get Audit Trail
    runner.test_get_audit_trail()
    
    # Step 13: Get KYC Audit Trail
    runner.test_get_kyc_audit_trail()
    
    # Step 14: Get Audit Stats
    runner.test_get_audit_stats()
    
    # Print summary
    runner.print_summary()

if __name__ == "__main__":
    main()
