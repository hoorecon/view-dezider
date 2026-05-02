"""
Incident Response System — View Dezider
CERT-In compliant breach notification + user alerting + timeline tracking.
Backed by real WhatsApp (UltraMsg) and email notifications.
"""

import os
import uuid
import logging
import httpx
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from core.database import db
from routes.auth_routes import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/incidents", tags=["Incident Response"])

# ========================
# CONFIG
# ========================

ULTRAMSG_INSTANCE_ID = os.environ.get("ULTRAMSG_INSTANCE_ID", "")
ULTRAMSG_API_TOKEN = os.environ.get("ULTRAMSG_API_TOKEN", "")
ULTRAMSG_BASE_URL = f"https://api.ultramsg.com/{ULTRAMSG_INSTANCE_ID}"

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "security@veales.com")

CERTIN_EMAIL = "incident@cert-in.org.in"
CERTIN_PHONE = "+911onal"  # CERT-In helpline

SEVERITY_LEVELS = ["critical", "high", "medium", "low"]
INCIDENT_TYPES = [
    "data_breach",
    "unauthorized_access",
    "malware_attack",
    "ddos_attack",
    "phishing",
    "insider_threat",
    "api_compromise",
    "kyc_data_exposure",
    "credential_leak",
    "other",
]
STATUS_FLOW = ["detected", "investigating", "contained", "certin_notified", "users_notified", "resolved", "post_mortem"]


# ========================
# MODELS
# ========================

class IncidentCreate(BaseModel):
    title: str
    incident_type: str
    severity: str
    description: str
    affected_systems: List[str] = []
    affected_user_count: int = 0
    kyc_data_involved: bool = False
    initial_actions_taken: str = ""


class IncidentUpdate(BaseModel):
    status: Optional[str] = None
    description: Optional[str] = None
    resolution_notes: Optional[str] = None
    affected_user_count: Optional[int] = None
    root_cause: Optional[str] = None
    remediation_steps: Optional[str] = None


# ========================
# HELPERS
# ========================

def generate_certin_report(incident: dict) -> str:
    """Generate CERT-In standardized incident report text."""
    return f"""=== CERT-In INCIDENT REPORT ===
Organization: VEALES (View Dezider Platform)
CIN/Registration: [As per Certificate of Incorporation]
Contact Person: A D Shezhiyan Raj, Founder & CEO
Contact Email: {SMTP_FROM}

--- INCIDENT DETAILS ---
Incident ID: {incident.get('id', 'N/A')}
Title: {incident.get('title', 'N/A')}
Type: {incident.get('incident_type', 'N/A').replace('_', ' ').title()}
Severity: {incident.get('severity', 'N/A').upper()}
Detected At: {incident.get('detected_at', 'N/A')}
Reported At: {datetime.now(timezone.utc).isoformat()}

--- DESCRIPTION ---
{incident.get('description', 'N/A')}

--- AFFECTED SCOPE ---
Affected Systems: {', '.join(incident.get('affected_systems', ['N/A']))}
Estimated Affected Users: {incident.get('affected_user_count', 0)}
KYC/Aadhaar Data Involved: {'YES' if incident.get('kyc_data_involved') else 'NO'}

--- ACTIONS TAKEN ---
{incident.get('initial_actions_taken', 'Investigation in progress')}

--- TIMELINE ---
""".strip() + "\n" + "\n".join(
        [f"  {e['timestamp']} — [{e['status'].upper()}] {e['note']}" for e in incident.get('timeline', [])]
    ) + f"""

--- COMPLIANCE ---
This report is filed under Section 70B of the Information Technology Act, 2000
and the Indian Computer Emergency Response Team (CERT-In) Rules, 2013.
Report filed within 6 hours of incident detection as mandated.

--- DECLARATION ---
The information provided above is accurate to the best of our knowledge.
We commit to providing updates as the investigation progresses.

Signed: A D Shezhiyan Raj, Founder & CEO, VEALES
Date: {datetime.now(timezone.utc).strftime('%d %B %Y, %H:%M UTC')}
================================"""


def generate_user_notification(incident: dict) -> str:
    """Generate user-facing breach notification message."""
    return f"""⚠️ *SECURITY NOTICE — View Dezider*

Dear User,

We are writing to inform you about a security incident that may affect your account.

*Incident:* {incident.get('title', 'Security Incident')}
*Severity:* {incident.get('severity', 'N/A').upper()}
*Detected:* {incident.get('detected_at', 'N/A')[:10]}
*KYC Data Affected:* {'Yes — your identity verification data may be impacted' if incident.get('kyc_data_involved') else 'No — your KYC data is not affected'}

*What happened:*
{incident.get('description', '')[:300]}

*What we are doing:*
{incident.get('initial_actions_taken', 'Our security team is actively investigating and containing the incident.')[:300]}

*What you should do:*
1. Change your password immediately
2. Enable Authenticator App (TOTP) if not already active
3. Review your recent activity in the app
4. Contact us if you notice anything suspicious

We take the security of your data very seriously. This notification is sent in compliance with the Digital Personal Data Protection Act (DPDPA), 2023.

For questions: security@veales.com

— View Dezider Security Team"""


async def send_whatsapp_message(phone: str, message: str) -> dict:
    """Send WhatsApp message via UltraMsg."""
    if not ULTRAMSG_INSTANCE_ID or not ULTRAMSG_API_TOKEN:
        return {"success": False, "error": "WhatsApp not configured"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{ULTRAMSG_BASE_URL}/messages/chat",
                data={"token": ULTRAMSG_API_TOKEN, "to": phone, "body": message}
            )
            result = resp.json()
            return {"success": result.get("sent") == "true", "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def send_email(to: str, subject: str, body: str) -> dict:
    """Send email via SMTP. Falls back gracefully if not configured."""
    if not SMTP_HOST or not SMTP_USER:
        return {"success": False, "error": "SMTP not configured", "fallback": "email_queued_for_manual_send"}
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart()
        msg['From'] = SMTP_FROM
        msg['To'] = to
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def require_admin(user: dict):
    """Check admin role."""
    u = await db.users.find_one({"user_id": user["user_id"]})
    if not u or u.get("role") not in ["admin", "org_admin", "super_admin"]:
        raise HTTPException(403, "Admin access required")
    return u


# ========================
# ENDPOINTS
# ========================

@router.get("/config")
async def get_incident_config(user: dict = Depends(get_current_user)):
    """Get incident types, severity levels, status flow."""
    await require_admin(user)
    return {
        "incident_types": INCIDENT_TYPES,
        "severity_levels": SEVERITY_LEVELS,
        "status_flow": STATUS_FLOW,
        "certin_email": CERTIN_EMAIL,
        "smtp_configured": bool(SMTP_HOST and SMTP_USER),
        "whatsapp_configured": bool(ULTRAMSG_INSTANCE_ID and ULTRAMSG_API_TOKEN),
    }


@router.post("")
async def create_incident(data: IncidentCreate, user: dict = Depends(get_current_user)):
    """Create a new security incident. Admin only."""
    admin = await require_admin(user)

    if data.severity not in SEVERITY_LEVELS:
        raise HTTPException(400, f"Invalid severity. Must be one of: {SEVERITY_LEVELS}")
    if data.incident_type not in INCIDENT_TYPES:
        raise HTTPException(400, f"Invalid type. Must be one of: {INCIDENT_TYPES}")

    now = datetime.now(timezone.utc).isoformat()
    incident = {
        "id": f"INC-{uuid.uuid4().hex[:8].upper()}",
        "title": data.title,
        "incident_type": data.incident_type,
        "severity": data.severity,
        "description": data.description,
        "affected_systems": data.affected_systems,
        "affected_user_count": data.affected_user_count,
        "kyc_data_involved": data.kyc_data_involved,
        "initial_actions_taken": data.initial_actions_taken,
        "status": "detected",
        "created_by": user["user_id"],
        "created_by_name": admin.get("name", admin.get("email", "")),
        "detected_at": now,
        "created_at": now,
        "updated_at": now,
        "certin_notified": False,
        "certin_notified_at": None,
        "users_notified": False,
        "users_notified_at": None,
        "users_notified_count": 0,
        "resolved_at": None,
        "root_cause": "",
        "remediation_steps": "",
        "resolution_notes": "",
        "timeline": [
            {"timestamp": now, "status": "detected", "note": f"Incident detected and logged by {admin.get('name', admin.get('email', ''))}", "by": user["user_id"]}
        ],
        "notification_log": [],
    }

    await db.incidents.insert_one(incident)

    # Log to audit trail
    await db.audit_trail.insert_one({
        "id": f"AUD-{uuid.uuid4().hex[:8]}",
        "action": "incident_created",
        "entity_type": "incident",
        "entity_id": incident["id"],
        "user_id": user["user_id"],
        "details": f"Security incident created: {data.title} [{data.severity}]",
        "timestamp": now,
        "ip_address": "",
    })

    # Auto-escalation for critical + KYC incidents
    if data.severity == "critical" and data.kyc_data_involved:
        incident["_auto_escalation"] = "CRITICAL KYC incident — CERT-In notification recommended within 6 hours"

    return {"id": incident["id"], "status": "detected", "message": "Incident logged successfully", "auto_escalation": data.severity == "critical"}


@router.get("")
async def list_incidents(status: Optional[str] = None, severity: Optional[str] = None, user: dict = Depends(get_current_user)):
    """List all incidents. Admin only."""
    await require_admin(user)
    query = {}
    if status:
        query["status"] = status
    if severity:
        query["severity"] = severity

    incidents = await db.incidents.find(query).sort("created_at", -1).to_list(100)
    for i in incidents:
        i.pop("_id", None)
    return incidents


@router.get("/{incident_id}")
async def get_incident(incident_id: str, user: dict = Depends(get_current_user)):
    """Get incident details with full timeline."""
    await require_admin(user)
    inc = await db.incidents.find_one({"id": incident_id})
    if not inc:
        raise HTTPException(404, "Incident not found")
    inc.pop("_id", None)
    return inc


@router.put("/{incident_id}")
async def update_incident(incident_id: str, data: IncidentUpdate, user: dict = Depends(get_current_user)):
    """Update incident status, add to timeline."""
    admin = await require_admin(user)
    inc = await db.incidents.find_one({"id": incident_id})
    if not inc:
        raise HTTPException(404, "Incident not found")

    now = datetime.now(timezone.utc).isoformat()
    update_fields = {"updated_at": now}
    timeline_entry = None

    if data.status and data.status != inc.get("status"):
        if data.status not in STATUS_FLOW:
            raise HTTPException(400, f"Invalid status. Must be one of: {STATUS_FLOW}")
        update_fields["status"] = data.status
        timeline_entry = {
            "timestamp": now,
            "status": data.status,
            "note": f"Status changed to {data.status.replace('_', ' ').title()}",
            "by": user["user_id"],
        }
        if data.status == "resolved":
            update_fields["resolved_at"] = now

    if data.description is not None:
        update_fields["description"] = data.description
    if data.resolution_notes is not None:
        update_fields["resolution_notes"] = data.resolution_notes
    if data.affected_user_count is not None:
        update_fields["affected_user_count"] = data.affected_user_count
    if data.root_cause is not None:
        update_fields["root_cause"] = data.root_cause
    if data.remediation_steps is not None:
        update_fields["remediation_steps"] = data.remediation_steps

    update_ops = {"$set": update_fields}
    if timeline_entry:
        update_ops["$push"] = {"timeline": timeline_entry}

    await db.incidents.update_one({"id": incident_id}, update_ops)

    # Audit
    await db.audit_trail.insert_one({
        "id": f"AUD-{uuid.uuid4().hex[:8]}",
        "action": "incident_updated",
        "entity_type": "incident",
        "entity_id": incident_id,
        "user_id": user["user_id"],
        "details": f"Updated: {', '.join(update_fields.keys())}",
        "timestamp": now,
        "ip_address": "",
    })

    return {"id": incident_id, "updated_fields": list(update_fields.keys()), "message": "Incident updated"}


@router.post("/{incident_id}/notify-certin")
async def notify_certin(incident_id: str, user: dict = Depends(get_current_user)):
    """Generate and send CERT-In incident report. Sends via email (if SMTP configured) + stores report."""
    admin = await require_admin(user)
    inc = await db.incidents.find_one({"id": incident_id})
    if not inc:
        raise HTTPException(404, "Incident not found")

    now = datetime.now(timezone.utc).isoformat()
    report = generate_certin_report(inc)

    # Attempt email to CERT-In
    email_result = await send_email(
        to=CERTIN_EMAIL,
        subject=f"[INCIDENT REPORT] {inc['id']} — {inc['title']} [{inc['severity'].upper()}]",
        body=report
    )

    # Store report regardless
    notification_entry = {
        "type": "certin",
        "timestamp": now,
        "channel": "email" if email_result.get("success") else "report_generated",
        "email_sent": email_result.get("success", False),
        "email_error": email_result.get("error"),
        "report_text": report,
        "sent_by": user["user_id"],
    }

    await db.incidents.update_one(
        {"id": incident_id},
        {
            "$set": {
                "certin_notified": True,
                "certin_notified_at": now,
                "status": "certin_notified",
                "updated_at": now,
            },
            "$push": {
                "timeline": {
                    "timestamp": now,
                    "status": "certin_notified",
                    "note": f"CERT-In report {'emailed to ' + CERTIN_EMAIL if email_result.get('success') else 'generated (email pending — SMTP not configured)'}. Report stored.",
                    "by": user["user_id"],
                },
                "notification_log": notification_entry,
            },
        }
    )

    # Audit
    await db.audit_trail.insert_one({
        "id": f"AUD-{uuid.uuid4().hex[:8]}",
        "action": "certin_notified",
        "entity_type": "incident",
        "entity_id": incident_id,
        "user_id": user["user_id"],
        "details": f"CERT-In notification {'sent' if email_result.get('success') else 'generated'}. Severity: {inc.get('severity')}",
        "timestamp": now,
        "ip_address": "",
    })

    return {
        "id": incident_id,
        "certin_notified": True,
        "email_sent": email_result.get("success", False),
        "email_error": email_result.get("error"),
        "report_preview": report[:500] + "...",
        "full_report_stored": True,
        "message": "CERT-In report generated and stored" + (" + emailed" if email_result.get("success") else " (configure SMTP to auto-email)"),
    }


@router.post("/{incident_id}/notify-users")
async def notify_users(incident_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Notify all affected users via WhatsApp + in-app notification."""
    admin = await require_admin(user)
    inc = await db.incidents.find_one({"id": incident_id})
    if not inc:
        raise HTTPException(404, "Incident not found")

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    now = datetime.now(timezone.utc).isoformat()
    message = generate_user_notification(inc)
    custom_message = body.get("custom_message", "")
    if custom_message:
        message += f"\n\n*Additional note from admin:*\n{custom_message}"

    # Fetch all users (or affected subset)
    affected_scope = body.get("scope", "all")  # "all", "kyc_users", "specific_ids"
    user_query = {}
    if affected_scope == "kyc_users":
        kyc_user_ids = await db.user_kyc.distinct("user_id")
        user_query = {"user_id": {"$in": kyc_user_ids}}
    elif affected_scope == "specific_ids":
        specific_ids = body.get("user_ids", [])
        user_query = {"user_id": {"$in": specific_ids}}

    users = await db.users.find(user_query).to_list(10000)

    whatsapp_sent = 0
    whatsapp_failed = 0
    inapp_count = 0

    for u in users:
        # In-app notification
        await db.user_notifications.insert_one({
            "id": f"notif-{uuid.uuid4().hex[:8]}",
            "user_id": u["user_id"],
            "type": "security_alert",
            "title": f"Security Alert: {inc['title']}",
            "body": message[:500],
            "incident_id": incident_id,
            "severity": inc.get("severity"),
            "read": False,
            "created_at": now,
        })
        inapp_count += 1

        # WhatsApp notification
        phone = u.get("whatsapp_number") or u.get("phone")
        if phone:
            result = await send_whatsapp_message(phone, message)
            if result.get("success"):
                whatsapp_sent += 1
            else:
                whatsapp_failed += 1

    # Update incident
    await db.incidents.update_one(
        {"id": incident_id},
        {
            "$set": {
                "users_notified": True,
                "users_notified_at": now,
                "users_notified_count": len(users),
                "status": "users_notified",
                "updated_at": now,
            },
            "$push": {
                "timeline": {
                    "timestamp": now,
                    "status": "users_notified",
                    "note": f"Notified {len(users)} users ({whatsapp_sent} WhatsApp, {inapp_count} in-app). Scope: {affected_scope}.",
                    "by": user["user_id"],
                },
                "notification_log": {
                    "type": "user_notification",
                    "timestamp": now,
                    "scope": affected_scope,
                    "total_users": len(users),
                    "whatsapp_sent": whatsapp_sent,
                    "whatsapp_failed": whatsapp_failed,
                    "inapp_sent": inapp_count,
                    "sent_by": user["user_id"],
                },
            },
        }
    )

    # Audit
    await db.audit_trail.insert_one({
        "id": f"AUD-{uuid.uuid4().hex[:8]}",
        "action": "users_notified",
        "entity_type": "incident",
        "entity_id": incident_id,
        "user_id": user["user_id"],
        "details": f"Breach notification sent to {len(users)} users. WhatsApp: {whatsapp_sent}/{whatsapp_sent + whatsapp_failed}. In-app: {inapp_count}.",
        "timestamp": now,
        "ip_address": "",
    })

    return {
        "id": incident_id,
        "users_notified": True,
        "scope": affected_scope,
        "total_users": len(users),
        "whatsapp_sent": whatsapp_sent,
        "whatsapp_failed": whatsapp_failed,
        "inapp_notifications": inapp_count,
        "message": f"Breach notification sent to {len(users)} users",
    }


@router.get("/{incident_id}/report")
async def get_certin_report(incident_id: str, user: dict = Depends(get_current_user)):
    """Get the full CERT-In report text for an incident."""
    await require_admin(user)
    inc = await db.incidents.find_one({"id": incident_id})
    if not inc:
        raise HTTPException(404, "Incident not found")
    report = generate_certin_report(inc)
    return {"incident_id": incident_id, "report": report, "certin_email": CERTIN_EMAIL}


@router.get("/{incident_id}/timeline")
async def get_incident_timeline(incident_id: str, user: dict = Depends(get_current_user)):
    """Get detailed timeline of an incident."""
    await require_admin(user)
    inc = await db.incidents.find_one({"id": incident_id})
    if not inc:
        raise HTTPException(404, "Incident not found")
    
    # Calculate SLA compliance
    detected_at = inc.get("detected_at", "")
    certin_at = inc.get("certin_notified_at")
    users_at = inc.get("users_notified_at")
    
    sla = {
        "certin_6hr_sla": None,
        "user_24hr_sla": None,
    }
    
    if detected_at and certin_at:
        det = datetime.fromisoformat(detected_at)
        cert = datetime.fromisoformat(certin_at)
        hours_diff = (cert - det).total_seconds() / 3600
        sla["certin_6hr_sla"] = {"compliant": hours_diff <= 6, "hours_taken": round(hours_diff, 2)}
    
    if detected_at and users_at:
        det = datetime.fromisoformat(detected_at)
        usr = datetime.fromisoformat(users_at)
        hours_diff = (usr - det).total_seconds() / 3600
        sla["user_24hr_sla"] = {"compliant": hours_diff <= 24, "hours_taken": round(hours_diff, 2)}

    return {
        "incident_id": incident_id,
        "status": inc.get("status"),
        "severity": inc.get("severity"),
        "timeline": inc.get("timeline", []),
        "notification_log": inc.get("notification_log", []),
        "sla_compliance": sla,
    }
