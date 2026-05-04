"""Admin Documentation Hub — Auto-generated PRD, SRS, Test Cases, UAT, API Catalog"""

import uuid
import os
import json as json_module
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from core.database import db
from core.auth import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/docs", tags=["Admin Documentation Hub"])

# ========================
# CHANNEL AUTO-TAGGING
# ========================

CHANNEL_RULES = {
    "/auth": ["internal", "chatbot", "ivr", "partner"],
    "/health": ["internal", "chatbot", "ivr", "partner"],
    "/decisions": ["internal", "chatbot", "partner"],
    "/test123": ["internal", "chatbot", "ivr"],
    "/pros-cons": ["internal", "chatbot"],
    "/swot": ["internal", "chatbot"],
    "/assessment": ["internal", "chatbot"],
    "/ctt": ["internal", "chatbot"],
    "/gem": ["internal", "chatbot"],
    "/journal": ["internal", "chatbot"],
    "/stats": ["internal", "chatbot"],
    "/notifications": ["internal", "ivr"],
    "/solutions-store": ["internal", "chatbot", "partner"],
    "/deo": ["internal", "partner"],
    "/payments": ["internal", "partner"],
    "/organizations": ["internal", "partner"],
    "/shared-steps": ["internal", "chatbot", "partner"],
    "/decision-templates": ["internal", "partner"],
    "/feature-flags": ["internal"],
    "/admin": ["internal"],
    "/search": ["internal", "chatbot", "partner"],
    "/folders": ["internal", "chatbot"],
    "/lifestyle": ["internal", "chatbot"],
    "/consciousness-diary": ["internal", "chatbot"],
    "/time-dezider": ["internal", "chatbot"],
    "/time-store": ["internal", "chatbot"],
    "/google-calendar": ["internal"],
    "/cld": ["internal", "chatbot"],
    "/gem-flight": ["internal", "chatbot"],
    "/hos": ["internal", "chatbot"],
    "/org-auth": ["internal", "partner"],
    "/video-calls": ["internal"],
    "/experts": ["internal"],
    "/tepfi": ["internal", "chatbot"],
    "/factor-data": ["internal", "chatbot"],
    "/reviews": ["internal", "chatbot", "partner"],
    "/contacts": ["internal", "chatbot", "partner"],
    "/collaboration": ["internal", "chatbot", "partner"],
    "/digilocker": ["internal"],
    "/biometric": ["internal"],
    "/aala": ["internal", "chatbot"],
    "/lifestyle-eval": ["internal", "chatbot"],
    "/goal-setter": ["internal", "chatbot"],
    "/goal-manifestation": ["internal", "chatbot"],
    "/unconditional-happiness": ["internal", "chatbot"],
    "/meditation-settings": ["internal"],
    "/conflict-breaker": ["internal", "chatbot"],
    "/pna": ["internal", "chatbot"],
    "/lifestyle-designer": ["internal", "chatbot"],
    "/ai-assistant": ["internal", "chatbot"],
}

CATEGORY_MAP = {
    "/auth": "Authentication & User Management",
    "/health": "System",
    "/decisions": "PRR Decision Engine",
    "/test123": "Test123 Quick Decisions",
    "/pros-cons": "Pros & Cons Analysis",
    "/swot": "SWOT Analysis",
    "/assessment": "Decision Mode Assessment",
    "/ctt": "Centralized Task Tracker",
    "/gem": "Goals Execution Manager",
    "/gem-flight": "GEM Flight Model",
    "/journal": "Decision Journal",
    "/stats": "Analytics & Stats",
    "/notifications": "Notifications & Alerts",
    "/solutions-store": "Solutions Store",
    "/deo": "DEO Engine (Import & API)",
    "/payments": "Payments & Subscriptions",
    "/organizations": "Organizations",
    "/shared-steps": "Collaboration & Sharing",
    "/decision-templates": "Decision Templates",
    "/feature-flags": "Feature Configuration",
    "/admin": "Admin Management",
    "/search": "Search",
    "/folders": "Folder Management",
    "/lifestyle": "Lifestyle Dezider",
    "/consciousness-diary": "Consciousness Diary",
    "/time-dezider": "Time Dezider",
    "/time-store": "Time Store",
    "/google-calendar": "Google Calendar Integration",
    "/cld": "CLD (Causal Loop Diagrams)",
    "/hos": "HOS Decision Intake",
    "/org-auth": "Organization Auth",
    "/video-calls": "Video Call Sessions",
    "/experts": "Expert Management",
    "/tepfi": "TEPFI Matrix",
    "/factor-data": "Factor Data Sources",
    "/reviews": "Solution Reviews",
    "/contacts": "Contact List Management",
    "/collaboration": "Multi-User Collaboration",
    "/digilocker": "DigiLocker eKYC (India)",
    "/biometric": "Biometric Authentication",
    "/aala": "AALA (Accrued Assets & Liabilities Analysis)",
    "/lifestyle-eval": "LEE (Lifestyle Effectiveness Evaluation)",
    "/goal-setter": "Goal Setter (SMART Framework)",
    "/goal-manifestation": "Goal Manifestation (CAB-FAME)",
    "/unconditional-happiness": "Unconditional Happiness Tracker",
    "/meditation-settings": "Meditation Audio Settings",
    "/conflict-breaker": "Conflict Breaker (Crucial Conversations)",
    "/pna": "PNA (Problems / Needs / Aspirations)",
    "/lifestyle-designer": "Lifestyle Designer",
    "/ai-assistant": "AI Solution Assistant",
}


def _get_channels(path: str) -> list:
    """Auto-tag an endpoint path with consumer channels."""
    # Strip /api prefix
    clean = path.replace("/api", "", 1) if path.startswith("/api") else path
    for prefix, channels in CHANNEL_RULES.items():
        if clean.startswith(prefix):
            return channels
    return ["internal"]


def _get_category(path: str) -> str:
    """Get category name for a path."""
    clean = path.replace("/api", "", 1) if path.startswith("/api") else path
    for prefix, cat in CATEGORY_MAP.items():
        if clean.startswith(prefix):
            return cat
    return "Other"


def _generate_sample_payload(schema: dict, definitions: dict, depth: int = 0) -> dict:
    """Generate a sample payload from an OpenAPI schema definition."""
    if depth > 4:
        return {}
    if "$ref" in schema:
        ref_name = schema["$ref"].split("/")[-1]
        if ref_name in definitions:
            return _generate_sample_payload(definitions[ref_name], definitions, depth + 1)
        return {}

    schema_type = schema.get("type", "object")
    if schema_type == "object":
        result = {}
        props = schema.get("properties", {})
        for key, prop in props.items():
            if "$ref" in prop:
                ref_name = prop["$ref"].split("/")[-1]
                if ref_name in definitions:
                    result[key] = _generate_sample_payload(definitions[ref_name], definitions, depth + 1)
                else:
                    result[key] = {}
            elif prop.get("type") == "string":
                if "enum" in prop:
                    result[key] = prop["enum"][0]
                elif "default" in prop:
                    result[key] = prop["default"]
                else:
                    result[key] = f"sample_{key}"
            elif prop.get("type") == "integer":
                result[key] = prop.get("default", 1)
            elif prop.get("type") == "number":
                result[key] = prop.get("default", 1.0)
            elif prop.get("type") == "boolean":
                result[key] = prop.get("default", True)
            elif prop.get("type") == "array":
                items = prop.get("items", {})
                result[key] = [_generate_sample_payload(items, definitions, depth + 1)]
            else:
                result[key] = None
        return result
    elif schema_type == "array":
        items = schema.get("items", {})
        return [_generate_sample_payload(items, definitions, depth + 1)]
    elif schema_type == "string":
        return schema.get("default", "sample_string")
    elif schema_type == "integer":
        return schema.get("default", 0)
    elif schema_type == "number":
        return schema.get("default", 0.0)
    elif schema_type == "boolean":
        return schema.get("default", True)
    return {}


# ========================
# API CATALOG ENDPOINT
# ========================

@router.get("/api-catalog")
async def get_api_catalog(
    request: Request,
    channel: Optional[str] = None,
    user: dict = Depends(require_admin)
):
    """Get full API catalog extracted from OpenAPI spec, with channel tagging."""
    from server import app as fastapi_app
    openapi = fastapi_app.openapi()
    paths = openapi.get("paths", {})
    definitions = {}
    # OpenAPI 3.x uses components/schemas
    if "components" in openapi and "schemas" in openapi["components"]:
        definitions = openapi["components"]["schemas"]
    # OpenAPI 2.x fallback
    elif "definitions" in openapi:
        definitions = openapi["definitions"]

    catalog = []
    for path, methods in paths.items():
        for method, detail in methods.items():
            if method in ("get", "post", "put", "delete", "patch"):
                channels = _get_channels(path)
                category = _get_category(path)

                # Filter by channel if specified
                if channel and channel not in channels:
                    continue

                # Extract request body schema
                req_sample = None
                req_body = detail.get("requestBody", {})
                if req_body:
                    content = req_body.get("content", {})
                    json_content = content.get("application/json", {})
                    schema = json_content.get("schema", {})
                    if schema:
                        req_sample = _generate_sample_payload(schema, definitions)

                # Extract path parameters
                params = []
                for p in detail.get("parameters", []):
                    params.append({
                        "name": p.get("name"),
                        "in": p.get("in"),
                        "required": p.get("required", False),
                        "type": p.get("schema", {}).get("type", "string"),
                        "description": p.get("description", ""),
                    })

                # Extract response schema
                resp_sample = None
                responses = detail.get("responses", {})
                success_resp = responses.get("200", responses.get("201", {}))
                if success_resp:
                    resp_content = success_resp.get("content", {})
                    resp_json = resp_content.get("application/json", {})
                    resp_schema = resp_json.get("schema", {})
                    if resp_schema:
                        resp_sample = _generate_sample_payload(resp_schema, definitions)

                entry = {
                    "method": method.upper(),
                    "path": path,
                    "summary": detail.get("summary", ""),
                    "description": detail.get("description", ""),
                    "tags": detail.get("tags", []),
                    "category": category,
                    "channels": channels,
                    "parameters": params,
                    "request_sample": req_sample,
                    "response_sample": resp_sample,
                    "requires_auth": any(
                        "get_current_user" in str(detail) or
                        "require_admin" in str(detail) or
                        "Authorization" in str(p.get("name", ""))
                        for p in detail.get("parameters", [{}])
                    ) or bool(detail.get("security")),
                }
                catalog.append(entry)

    # Sort by category then path
    catalog.sort(key=lambda x: (x["category"], x["path"], x["method"]))

    return {
        "total_endpoints": len(catalog),
        "endpoints": catalog,
        "available_channels": ["internal", "chatbot", "ivr", "partner"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ========================
# POSTMAN COLLECTION EXPORT
# ========================

@router.get("/postman-collection")
async def export_postman_collection(
    request: Request,
    user: dict = Depends(require_admin)
):
    """Export full API catalog as Postman Collection v2.1 JSON (downloadable)."""
    from fastapi.responses import JSONResponse
    from server import app as fastapi_app
    openapi = fastapi_app.openapi()
    paths = openapi.get("paths", {})
    definitions = {}
    if "components" in openapi and "schemas" in openapi["components"]:
        definitions = openapi["components"]["schemas"]

    # Build Postman collection v2.1
    items_by_category = {}
    for path, methods in paths.items():
        for method, detail in methods.items():
            if method not in ("get", "post", "put", "delete", "patch"):
                continue

            category = _get_category(path)
            channels = _get_channels(path)

            # Build request body
            req_body_raw = None
            req_body = detail.get("requestBody", {})
            if req_body:
                content = req_body.get("content", {})
                json_content = content.get("application/json", {})
                schema = json_content.get("schema", {})
                if schema:
                    sample = _generate_sample_payload(schema, definitions)
                    if sample:
                        req_body_raw = json_module.dumps(sample, indent=2)

            # Build query params
            query_params = []
            path_vars = []
            for p in detail.get("parameters", []):
                if p.get("in") == "query":
                    query_params.append({
                        "key": p["name"],
                        "value": "",
                        "description": p.get("description", ""),
                        "disabled": not p.get("required", False),
                    })
                elif p.get("in") == "path":
                    path_vars.append({
                        "key": p["name"],
                        "value": f"{{{{SAMPLE_{p['name'].upper()}}}}}",
                        "description": p.get("description", ""),
                    })

            # Replace FastAPI {param} with Postman :param
            postman_url = path.replace("{", ":").replace("}", "")

            pm_request = {
                "method": method.upper(),
                "header": [
                    {"key": "Content-Type", "value": "application/json"},
                    {"key": "Authorization", "value": "Bearer {{AUTH_TOKEN}}"},
                ],
                "url": {
                    "raw": "{{BASE_URL}}" + postman_url + ("?" + "&".join(f"{q['key']}=" for q in query_params) if query_params else ""),
                    "host": ["{{BASE_URL}}"],
                    "path": [s for s in postman_url.strip("/").split("/") if s],
                    "query": query_params,
                    "variable": path_vars,
                },
            }
            if req_body_raw:
                pm_request["body"] = {
                    "mode": "raw",
                    "raw": req_body_raw,
                    "options": {"raw": {"language": "json"}},
                }

            item = {
                "name": detail.get("summary") or f"{method.upper()} {path}",
                "request": pm_request,
                "response": [],
            }

            # Add description with channel info
            desc_parts = []
            if detail.get("description"):
                desc_parts.append(detail["description"])
            desc_parts.append(f"Channels: {', '.join(channels)}")
            item["request"]["description"] = "\n".join(desc_parts)

            if category not in items_by_category:
                items_by_category[category] = []
            items_by_category[category].append(item)

    # Build folder structure
    folders = []
    for cat_name, items in sorted(items_by_category.items()):
        folders.append({
            "name": cat_name,
            "item": items,
        })

    collection = {
        "info": {
            "name": "View Dezider API — Full Collection",
            "description": "Auto-generated Postman Collection from View Dezider OpenAPI schema.\nGenerated: " + datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": folders,
        "variable": [
            {"key": "BASE_URL", "value": "https://your-domain.com/api", "type": "string"},
            {"key": "AUTH_TOKEN", "value": "session_xxx", "type": "string"},
        ],
    }

    return JSONResponse(
        content=collection,
        headers={"Content-Disposition": 'attachment; filename="ViewDezider_API_Collection.json"'},
    )


# ========================
# DOC GENERATION & STORAGE
# ========================

DOC_TYPES = ["prd", "srs", "regression_tests", "uat_cases"]


@router.get("/{doc_type}")
async def get_document(doc_type: str, user: dict = Depends(require_admin)):
    """Get a stored generated document."""
    if doc_type not in DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid doc_type. Use one of: {DOC_TYPES}")

    doc = await db.admin_docs.find_one({"doc_type": doc_type}, {"_id": 0})
    if not doc:
        return {
            "doc_type": doc_type,
            "content": None,
            "generated_at": None,
            "message": "Not yet generated. Use the refresh endpoint to generate.",
        }
    return doc


@router.post("/refresh/{doc_type}")
async def refresh_document(doc_type: str, request: Request, user: dict = Depends(require_admin)):
    """Regenerate a specific document using AI."""
    if doc_type not in DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid doc_type. Use one of: {DOC_TYPES}")

    content = await _generate_doc_for_type(doc_type, user["user_id"])

    now = datetime.now(timezone.utc)
    doc = {
        "doc_type": doc_type,
        "content": content,
        "generated_at": now,
        "generated_by": user.get("name", user["user_id"]),
    }

    await db.admin_docs.update_one(
        {"doc_type": doc_type},
        {"$set": doc},
        upsert=True
    )

    return doc


@router.post("/refresh-all")
async def refresh_all_documents(request: Request, user: dict = Depends(require_admin)):
    """Regenerate all documents at once."""
    now = datetime.now(timezone.utc)
    results = {}

    for doc_type in DOC_TYPES:
        try:
            content = await _generate_doc_for_type(doc_type, user["user_id"])
            doc = {
                "doc_type": doc_type,
                "content": content,
                "generated_at": now,
                "generated_by": user.get("name", user["user_id"]),
            }
            await db.admin_docs.update_one(
                {"doc_type": doc_type},
                {"$set": doc},
                upsert=True
            )
            results[doc_type] = "success"
        except Exception as e:
            logger.error(f"Failed to generate {doc_type}: {e}")
            results[doc_type] = f"error: {str(e)}"

    return {"results": results, "generated_at": now.isoformat()}


async def _generate_doc_for_type(doc_type: str, user_id: str) -> str:
    """Build API summary and generate doc for a specific type."""
    from server import app as fastapi_app
    openapi = fastapi_app.openapi()
    paths = openapi.get("paths", {})

    endpoint_summary = []
    for path, methods in paths.items():
        for method, detail in methods.items():
            if method in ("get", "post", "put", "delete", "patch"):
                desc = detail.get('summary', detail.get('description', ''))
                if desc:
                    desc = desc[:60]
                endpoint_summary.append(f"{method.upper()} {path} — {desc}")

    if doc_type in ("prd", "srs"):
        api_summary_text = "\n".join(endpoint_summary[:150])
    else:
        prefix_groups = {}
        for ep in endpoint_summary:
            parts = ep.split(" /api/")
            if len(parts) > 1:
                prefix = "/api/" + parts[1].split("/")[0]
                prefix_groups[prefix] = prefix_groups.get(prefix, 0) + 1
        module_overview = "\n".join(f"  {prefix}: {count} endpoints" for prefix, count in sorted(prefix_groups.items()))
        api_summary_text = f"Module summary ({len(endpoint_summary)} total endpoints):\n{module_overview}\n\nKey endpoints:\n" + "\n".join(endpoint_summary[:80])

    return await _generate_doc_with_ai(doc_type, api_summary_text, user_id)


async def _generate_doc_with_ai(doc_type: str, api_summary: str, user_id: str) -> str:
    """Use AI to generate a document based on the full API surface."""
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        return _fallback_doc(doc_type, api_summary)

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        prompts = {
            "prd": f"""You are a senior product manager. Generate a comprehensive Product Requirements Document (PRD) for "View Dezider" — a Decision Intelligence platform by Venture Buddha.

Based on the following API endpoints, reverse-engineer the full product requirements:

{api_summary}

The PRD must include:
1. Product Overview & Vision
2. Target Users (Individual, Business, Government/NonProfit)
3. Core Features covering ALL modules:
   - PRR Decision Engine (10-step), Test123 Quick Decisions, Pros & Cons, SWOT
   - Solutions Store with ReviewNet, DEO Engine (Inbound scraping + Outbound APIs)
   - CLD (Causal Loop Diagrams) — per-decision, per-module, and Master CLD (cross-module aggregation)
   - GEM Flight Model, CTT Task Tracker, GEM Goal Execution Manager
   - Lifestyle Dezider with routines, streaks, and LEE (Lifestyle Effectiveness Evaluation)
   - AALA (Accrued Assets & Liabilities Analysis) — Circle of Influence across 10 life areas
   - Goal Setter (SMART), Goal Manifestation (CAB-FAME 7 stages), KalphaVriksha Meditation
   - Unconditional Happiness Tracker, Meditation Settings (custom audio per user)
   - Emotional Gatekeeper sub-tools (Breaking the Trap, Breaking the Loop, Breaking Limitations, AIM, Outlet Analyzer, Effective Outlets Advisor, Emotional Reception)
   - Consciousness Diary, Time Dezider, Time Store, HOS Decision Intake
   - PNA Framework (Problems/Needs/Aspirations across 10 life areas with Convert-to-Decision/Goal)
   - Lifestyle Designer (plan ideal lifestyle allocations vs actuals with LEE comparison)
   - Conflict Breaker — 9-stage guided crucial conversation prep (Crucial Check, Motive Clarity, Learn to Look, Make It Safe, Story Map, Script Builder, Listening Plan, Action Plan, Closure) with AI script rewriting
   - AI Solution Assistant — personal AI chatbot with 6 languages (English, Tamil, Telugu, Kannada, Malayalam, Hindi), Text-to-Speech, cross-module context awareness, quick-ask one-shot queries
   - WOWO Access Control Matrix (role-based + subscription-plan feature gating with quotas)
   - Org Admin hierarchy (super_admin, admin, co_admin, user)
   - TEPFI Matrix (Time, Energy, People, Finance, Infrastructure resource analysis)
4. User Stories for each major feature
5. Non-functional Requirements (performance, security, scalability to 10k concurrent)
6. Integration Requirements (Google Calendar OAuth, Razorpay, WhatsApp OTP via UltraMsg, Emergent LLM/AI for doc generation / CLD / Conflict Breaker / AI Assistant, DigiLocker eKYC)
7. Platform Support (Web, Android, iOS, Chatbot, IVR)
8. AI-Powered Features Overview (CLD Generation, Conflict Script Rewriting, AI Assistant Conversations, Admin Doc Generation)

Format in clean Markdown with proper headings.""",

            "srs": f"""You are a systems architect. Generate a detailed System Requirements Specification (SRS) for "View Dezider" — a multi-platform Decision Intelligence system with 35+ modules.

Based on these API endpoints:

{api_summary}

The SRS must include:
1. System Overview & Architecture (FastAPI + MongoDB + Expo React Native + Emergent LLM Integration)
2. Functional Requirements per module (with endpoint mappings) covering:
   - Core Decision modules (PRR 10-step, Test123, Pros-Cons, SWOT, CLD with per-module + Master generation, HOS)
   - Execution modules (CTT, GEM, GEM Flight)
   - Evaluation modules (AALA, LEE, Lifestyle Designer, PNA Framework)
   - Growth modules (Goal Setter SMART, Goal Manifestation CAB-FAME, Unconditional Happiness, KalphaVriksha Meditation)
   - Self-Awareness (Emotional Gatekeeper with 10+ sub-tools, Consciousness Diary, Meditation Settings)
   - External Integration modules (Solutions Store, DEO Engine, Google Calendar OAuth)
   - Collaboration modules (Conflict Breaker 9-stage wizard with AI, Shared Steps, Expert Video Calls, Contacts)
   - AI Intelligence modules (AI Solution Assistant with 6-language TTS, CLD AI Generation, Conflict Script AI Rewriting)
   - Admin modules (WOWO ACM with role-based + subscription-plan gating, Org Auth, Feature Flags, Payments, Admin Doc Hub)
   - Resource modules (TEPFI Matrix, Time Dezider, Time Store)
3. Data Models / Schema Definitions (all 35+ collections including conflict_breaker_sessions, ai_assistant_conversations, pna_items, lifestyle_plans, acm_modules)
4. Authentication & Authorization (Session tokens, Role hierarchy super_admin → admin → co_admin → user, Org roles, WOWO ACM two-axis check: user_type × subscription_plan)
5. External Integrations (Google Calendar OAuth, Razorpay, UltraMsg WhatsApp OTP, Emergent LLM for AI features, DigiLocker, expo-speech for TTS)
6. API Design Patterns (RESTful, prefix /api, session token auth, channel tagging: internal/chatbot/ivr/partner)
7. Security & Privacy Requirements (bcrypt password hashing, session tokens, role-based access)
8. Performance Requirements (10k concurrent users target, in-memory ACM cache, MongoDB indices)
9. Deployment Architecture (Kubernetes, Expo Web/Mobile, FastAPI with uvicorn auto-reload)

Format in clean Markdown with proper headings.""",

            "regression_tests": f"""You are a QA lead. Generate comprehensive regression test cases for "View Dezider" Decision Intelligence platform with 35+ modules and 500+ API endpoints.

Based on these API endpoints:

{api_summary}

Generate test cases covering ALL modules:
1. Authentication Flow (Register, Login, Session, Logout, Password Reset, WhatsApp OTP)
2. PRR Decision CRUD (Create, Read, Update, Delete, Clone, Share — 10 steps)
3. Factor & Option Management
4. Test123 Quick Decisions, Pros & Cons, SWOT Analysis
5. CTT Task Tracker, GEM Goals, GEM Flight
6. Solutions Store & ReviewNet
7. DEO Engine (Scraping import + API Keys)
8. CLD (Causal Loop Diagrams) CRUD + Simulation + Module-Specific Generation (PNA, Goal, Lifestyle, Master) + List Modules
9. AALA (Assets & Liabilities)
10. LEE (Lifestyle Effectiveness Evaluation)
11. Goal Setter (SMART) + Goal Manifestation (CAB-FAME)
12. Unconditional Happiness + Meditation Settings
13. PNA Framework (Problems/Needs/Aspirations) — CRUD + Dashboard + Area Detail + Convert to Decision/Goal
14. Lifestyle Designer — Plan CRUD + Activate + Comparison vs LEE + Manual Overrides
15. Conflict Breaker — Session CRUD, 9-stage data save (Crucial Check through Closure), AI Generate per stage, Full session retrieval, Dashboard
16. AI Solution Assistant — Meta (6 languages), Conversation CRUD, Send Message (LLM), Quick Ask (LLM), Delete Conversation
17. Emotional Gatekeeper — All 10 sub-tools (Breaking Trap/Loop/Limitations, AIM, Outlet Analyzer, Effective Outlets Advisor, Emotional Reception, AI Reports)
18. Payments & Credits (Razorpay integration)
19. Admin Operations + WOWO ACM (Seed, Matrix, Feature Update, User Type Management, Usage Stats)
20. Admin Doc Hub (API Catalog, Postman Collection Export, PRD/SRS/Regression/UAT Generate & Refresh)
21. TEPFI Matrix, Time Dezider, Time Store
22. Google Calendar OAuth (Auth URL, Callback, Sync)
23. Edge Cases (empty data, unauthorized access, invalid IDs, role escalation, quota limits, expired sessions)

Format each test case as:
**TC-XXX: [Title]**
- Precondition: ...
- Steps: 1. ... 2. ... 3. ...
- Expected Result: ...
- Priority: P0/P1/P2

Format in clean Markdown.""",

            "uat_cases": f"""You are a UAT coordinator. Generate User Acceptance Test scenarios for "View Dezider" — covering ALL critical user journeys across 35+ modules.

Based on these API endpoints:

{api_summary}

Generate UAT scenarios for:
1. New User Onboarding (Register → First Decision → Complete PRR flow)
2. Pros & Cons / SWOT → PRR Conversion Flow
3. Task Management (CTT) with Decision linkage + Google Calendar sync
4. Goal Setting → Manifestation (CAB-FAME 7 stages) + KalphaVriksha Meditation
5. Solutions Store browsing + Integration into PRR Step 6/7 (auto-populate factors)
6. AALA Assessment + LEE Daily Logging
7. PNA Framework — Add items across 10 life areas → Convert to Decision/Goal
8. Lifestyle Designer — Create plan, set weekday/weekend allocations, compare vs LEE actuals, manual overrides
9. Unconditional Happiness daily tracking + streaks
10. Emotional Gatekeeper — Breaking the Trap → Breaking the Loop → Breaking Limitations → AI Breakthrough Report
11. Conflict Breaker — Create session → Walk through 9 stages (Crucial Check → Motive Clarity → Learn to Look → Make It Safe → Story Map → Script Builder → Listening Plan → Action Plan → Closure) → AI Script Rewriting → View Full Session
12. AI Solution Assistant — Select language → Start conversation → Send messages (receive AI responses with cross-module context) → Use TTS to hear response → Quick Ask one-shot → Switch language
13. CLD Engine — Generate per-decision CLD → Generate module-specific CLD (PNA, Goal, Lifestyle) → Generate Master CLD → Run What-If Simulation
14. Payment & Credit purchase (Razorpay flow)
15. Admin operations (user management, WOWO ACM settings, seed matrix, update feature access, doc generation/refresh)
16. Multi-platform verification (Web + Mobile via Expo Go)
17. DEO Engine import from external URLs + API key generation for outbound
18. Org Admin hierarchy: super_admin creates org → admin manages members → co_admin limited access → user
19. TEPFI Matrix resource analysis
20. Google Calendar OAuth flow: Authorize → Sync tasks → Sync lifestyle routines

Each scenario should be:
**UAT-XXX: [Scenario Title]**
- Actor: [User type]
- Goal: [What they want to achieve]
- Steps: 1. ... 2. ... 3. ...
- Acceptance Criteria: ...
- Platform: Web/Mobile/Chatbot/IVR/All

Format in clean Markdown.""",
        }

        prompt = prompts.get(doc_type, "Generate documentation.")

        chat = LlmChat(
            api_key=api_key,
            session_id=f"admin_doc_{user_id}_{uuid.uuid4().hex[:8]}",
            system_message="You are an expert technical writer. Generate professional, comprehensive documentation in Markdown format."
        ).with_model("openai", "gpt-4.1-mini")

        response = await chat.send_message(UserMessage(text=prompt))
        return response.strip()

    except Exception as e:
        logger.error(f"AI doc generation failed for {doc_type}: {e}")
        return _fallback_doc(doc_type, api_summary)


def _fallback_doc(doc_type: str, api_summary: str) -> str:
    """Fallback when AI is unavailable — return a structured template."""
    titles = {
        "prd": "Product Requirements Document — View Dezider",
        "srs": "System Requirements Specification — View Dezider",
        "regression_tests": "Regression Test Cases — View Dezider",
        "uat_cases": "User Acceptance Test Cases — View Dezider",
    }
    return f"""# {titles.get(doc_type, 'Document')}

*Auto-generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*
*AI generation unavailable — showing endpoint summary*

## API Endpoints Detected

```
{api_summary}
```

> To get AI-generated content, ensure EMERGENT_LLM_KEY is configured in backend environment.
"""


