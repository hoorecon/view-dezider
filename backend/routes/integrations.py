"""
backend/routes/integrations.py
Admin-only CRUD for 3rd-party integration credentials.

Storage: `integrations` collection in MongoDB.
Fields: provider, config (dict of key/value), enabled, updated_at, updated_by,
        last_tested_at, last_test_result.

Read path:
   from core.integrations import get_integration
   cfg = await get_integration("razorpay")     # returns dict or {}

The actual provider clients (razorpay, exotel, etc.) should call
get_integration() at request time so config edits take effect immediately
without a container restart.
"""
from __future__ import annotations

import os
import datetime as dt
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from core.database import db
from core.auth import require_admin

router = APIRouter(prefix="/admin/integrations", tags=["Admin Integrations"])

# ----------------------------------------------------------------------------
# Provider registry — defines the schema for each integration's config.
# Frontend uses this to render the right form fields.
# ----------------------------------------------------------------------------
PROVIDERS: Dict[str, Dict[str, Any]] = {
    "razorpay": {
        "title": "Razorpay",
        "category": "Payments",
        "icon": "card",
        "description": "Accept payments via UPI, cards, wallets, and net-banking (India).",
        "docs_url": "https://razorpay.com/docs/payments/dashboard/account-settings/api-keys/",
        "fields": [
            {"key": "key_id",     "label": "Key ID",     "type": "text",     "required": True,  "secret": False},
            {"key": "key_secret", "label": "Key Secret", "type": "password", "required": True,  "secret": True},
            {"key": "webhook_secret", "label": "Webhook Secret", "type": "password", "required": False, "secret": True},
        ],
    },
    "exotel": {
        "title": "Exotel (SMS OTP)",
        "category": "Communications",
        "icon": "chatbubble-ellipses",
        "description": "Send transactional SMS / OTP. Requires DLT template approval in India.",
        "docs_url": "https://developer.exotel.com/api/sms",
        "fields": [
            {"key": "sid",              "label": "Account SID",     "type": "text",     "required": True,  "secret": False},
            {"key": "api_key",          "label": "API Key",         "type": "password", "required": True,  "secret": True},
            {"key": "api_token",        "label": "API Token",       "type": "password", "required": True,  "secret": True},
            {"key": "sender_id",        "label": "Sender ID",       "type": "text",     "required": True,  "secret": False, "placeholder": "JELCOS"},
            {"key": "dlt_template_id",  "label": "DLT Template ID", "type": "text",     "required": True,  "secret": False},
        ],
    },
    "digilocker": {
        "title": "DigiLocker / API Setu (eKYC)",
        "category": "Identity",
        "icon": "shield-checkmark",
        "description": "Aadhaar-based eKYC, PAN verification, document fetch via API Setu.",
        "docs_url": "https://www.apisetu.gov.in/",
        "fields": [
            {"key": "client_id",     "label": "Client ID",     "type": "text",     "required": True,  "secret": False},
            {"key": "client_secret", "label": "Client Secret", "type": "password", "required": True,  "secret": True},
            {"key": "redirect_uri",  "label": "Redirect URI",  "type": "text",     "required": True,  "secret": False, "placeholder": "https://www.jelcos.ai/auth/digilocker/callback"},
        ],
    },
    "ultramsg": {
        "title": "UltraMsg (WhatsApp OTP)",
        "category": "Communications",
        "icon": "logo-whatsapp",
        "description": "Send WhatsApp messages for OTP and decision invites.",
        "docs_url": "https://docs.ultramsg.com/",
        "fields": [
            {"key": "instance_id", "label": "Instance ID", "type": "text",     "required": True, "secret": False},
            {"key": "token",       "label": "Token",       "type": "password", "required": True, "secret": True},
        ],
    },
    "google_calendar": {
        "title": "Google Calendar",
        "category": "Productivity",
        "icon": "calendar",
        "description": "Sync decision deadlines and review slots to user calendars.",
        "docs_url": "https://developers.google.com/calendar/api/quickstart",
        "fields": [
            {"key": "client_id",     "label": "OAuth Client ID",     "type": "text",     "required": True, "secret": False},
            {"key": "client_secret", "label": "OAuth Client Secret", "type": "password", "required": True, "secret": True},
        ],
    },
    "emergent_llm": {
        "title": "Emergent LLM Key (AI)",
        "category": "AI",
        "icon": "sparkles",
        "description": "Universal LLM access for OpenAI, Anthropic, Gemini. Get from Emergent profile → Universal Key.",
        "docs_url": "https://emergent.sh/",
        "fields": [
            {"key": "key", "label": "Universal LLM Key", "type": "password", "required": True, "secret": True},
        ],
    },
}

SECRET_MASK = "••••••••"


def _mask_config(provider: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """Replace secret values with mask so we never leak them via GET."""
    spec = PROVIDERS.get(provider, {})
    secret_keys = {f["key"] for f in spec.get("fields", []) if f.get("secret")}
    return {k: (SECRET_MASK if (k in secret_keys and v) else v) for k, v in (raw or {}).items()}


# ----------------------------------------------------------------------------
# Schemas
# ----------------------------------------------------------------------------
class IntegrationItem(BaseModel):
    provider: str
    title: str
    category: str
    icon: str
    description: str
    docs_url: str
    fields: List[Dict[str, Any]]
    enabled: bool = False
    configured: bool = False
    config_masked: Dict[str, Any] = Field(default_factory=dict)
    updated_at: str | None = None
    updated_by: str | None = None
    last_tested_at: str | None = None
    last_test_result: Dict[str, Any] | None = None


class IntegrationUpdate(BaseModel):
    enabled: bool | None = None
    config: Dict[str, Any] | None = None  # full or partial — partial uses upsert semantics


# ----------------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------------
@router.get("", response_model=List[IntegrationItem])
async def list_integrations(
    current_user: Dict = Depends(require_admin),

):
    """List all known integration providers with their current config status."""
    docs = await db.integrations.find({}).to_list(length=100)
    by_provider = {d["provider"]: d for d in docs}

    items: List[IntegrationItem] = []
    for provider, spec in PROVIDERS.items():
        doc = by_provider.get(provider) or {}
        raw_cfg = doc.get("config") or {}
        items.append(IntegrationItem(
            provider=provider,
            title=spec["title"],
            category=spec["category"],
            icon=spec["icon"],
            description=spec["description"],
            docs_url=spec["docs_url"],
            fields=spec["fields"],
            enabled=bool(doc.get("enabled", False)),
            configured=bool(raw_cfg),
            config_masked=_mask_config(provider, raw_cfg),
            updated_at=doc.get("updated_at").isoformat() if isinstance(doc.get("updated_at"), dt.datetime) else doc.get("updated_at"),
            updated_by=doc.get("updated_by"),
            last_tested_at=doc.get("last_tested_at").isoformat() if isinstance(doc.get("last_tested_at"), dt.datetime) else doc.get("last_tested_at"),
            last_test_result=doc.get("last_test_result"),
        ))
    return items


@router.get("/{provider}", response_model=IntegrationItem)
async def get_integration_detail(
    provider: str,
    current_user: Dict = Depends(require_admin),

):
    if provider not in PROVIDERS:
        raise HTTPException(404, f"Unknown integration provider: {provider}")
    doc = await db.integrations.find_one({"provider": provider}) or {}
    spec = PROVIDERS[provider]
    raw_cfg = doc.get("config") or {}
    return IntegrationItem(
        provider=provider,
        title=spec["title"],
        category=spec["category"],
        icon=spec["icon"],
        description=spec["description"],
        docs_url=spec["docs_url"],
        fields=spec["fields"],
        enabled=bool(doc.get("enabled", False)),
        configured=bool(raw_cfg),
        config_masked=_mask_config(provider, raw_cfg),
        updated_at=doc.get("updated_at").isoformat() if isinstance(doc.get("updated_at"), dt.datetime) else doc.get("updated_at"),
        updated_by=doc.get("updated_by"),
        last_tested_at=doc.get("last_tested_at").isoformat() if isinstance(doc.get("last_tested_at"), dt.datetime) else doc.get("last_tested_at"),
        last_test_result=doc.get("last_test_result"),
    )


@router.put("/{provider}", response_model=IntegrationItem)
async def update_integration(
    provider: str,
    body: IntegrationUpdate,
    current_user: Dict = Depends(require_admin),

):
    if provider not in PROVIDERS:
        raise HTTPException(404, f"Unknown integration provider: {provider}")

    update_doc: Dict[str, Any] = {
        "provider": provider,
        "updated_at": dt.datetime.utcnow(),
        "updated_by": current_user.get("user_id") or current_user.get("id") or current_user.get("email"),
    }
    if body.enabled is not None:
        update_doc["enabled"] = bool(body.enabled)
    if body.config is not None:
        # Merge with existing so masked secret fields aren't overwritten with mask values
        existing = await db.integrations.find_one({"provider": provider}) or {}
        existing_cfg = existing.get("config") or {}
        new_cfg = {**existing_cfg}
        for k, v in body.config.items():
            if v == SECRET_MASK:
                # User didn't change the secret — keep existing value
                continue
            new_cfg[k] = v
        update_doc["config"] = new_cfg

    await db.integrations.update_one(
        {"provider": provider},
        {"$set": update_doc},
        upsert=True,
    )

    # Audit log entry (best-effort)
    try:
        await db.audit_log.insert_one({
            "event_type": "integration_updated",
            "provider": provider,
            "actor": current_user.get("email"),
            "actor_id": current_user.get("user_id") or current_user.get("id"),
            "changes": {
                "enabled": body.enabled,
                "fields_changed": list((body.config or {}).keys()),
            },
            "created_at": dt.datetime.utcnow(),
        })
    except Exception:
        pass

    return await get_integration_detail(provider, current_user, db)


@router.post("/{provider}/test")
async def test_integration(
    provider: str,
    current_user: Dict = Depends(require_admin),

):
    """
    Lightweight connectivity test — does NOT charge money / send messages.
    For MVP this just checks that required fields are present. Real
    provider-specific health-checks can be added under core/integrations/.
    """
    if provider not in PROVIDERS:
        raise HTTPException(404, "Unknown provider")
    doc = await db.integrations.find_one({"provider": provider}) or {}
    cfg = doc.get("config") or {}
    spec = PROVIDERS[provider]
    missing = [f["key"] for f in spec["fields"] if f.get("required") and not cfg.get(f["key"])]
    result = {
        "ok": len(missing) == 0,
        "missing_fields": missing,
        "tested_at": dt.datetime.utcnow().isoformat(),
        "note": "MVP test only checks required fields are present. Live API ping coming in Phase 2.",
    }
    await db.integrations.update_one(
        {"provider": provider},
        {"$set": {"last_tested_at": dt.datetime.utcnow(), "last_test_result": result}},
        upsert=True,
    )
    return result
