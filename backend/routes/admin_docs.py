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

    # Get API catalog for context
    from server import app as fastapi_app
    openapi = fastapi_app.openapi()
    paths = openapi.get("paths", {})

    # Build endpoint summary for AI context
    endpoint_summary = []
    for path, methods in paths.items():
        for method, detail in methods.items():
            if method in ("get", "post", "put", "delete", "patch"):
                endpoint_summary.append(
                    f"{method.upper()} {path} — {detail.get('summary', detail.get('description', 'No description')[:80])}"
                )

    api_summary_text = "\n".join(endpoint_summary[:200])  # Cap at 200 for token safety

    content = await _generate_doc_with_ai(doc_type, api_summary_text, user["user_id"])

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
    from server import app as fastapi_app
    openapi = fastapi_app.openapi()
    paths = openapi.get("paths", {})

    endpoint_summary = []
    for path, methods in paths.items():
        for method, detail in methods.items():
            if method in ("get", "post", "put", "delete", "patch"):
                endpoint_summary.append(
                    f"{method.upper()} {path} — {detail.get('summary', detail.get('description', 'No description')[:80])}"
                )

    api_summary_text = "\n".join(endpoint_summary[:200])
    now = datetime.now(timezone.utc)
    results = {}

    for doc_type in DOC_TYPES:
        try:
            content = await _generate_doc_with_ai(doc_type, api_summary_text, user["user_id"])
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
3. Core Features (PRR Decision Engine, Test123, Pros & Cons, SWOT, Solutions Store, CLD, GEM Flight, CTT, Lifestyle Dezider, etc.)
4. User Stories for each major feature
5. Non-functional Requirements (performance, security, scalability)
6. Integration Requirements (Google Calendar, Razorpay, WhatsApp OTP, AI/LLM)
7. Platform Support (Web, Android, iOS, Chatbot, IVR)

Format in clean Markdown with proper headings.""",

            "srs": f"""You are a systems architect. Generate a detailed System Requirements Specification (SRS) for "View Dezider" — a multi-platform Decision Intelligence system.

Based on these API endpoints:

{api_summary}

The SRS must include:
1. System Overview & Architecture (FastAPI + MongoDB + Expo React Native)
2. Functional Requirements per module (with endpoint mappings)
3. Data Models / Schema Definitions
4. Authentication & Authorization (Session tokens, Role hierarchy: user/admin/co_admin/super_admin, Org roles)
5. External Integrations (Google Calendar OAuth, Razorpay, WhatsApp OTP via UltraMsg, Emergent LLM)
6. API Design Patterns (RESTful, prefix /api, JWT-like session tokens)
7. Security Requirements
8. Performance Requirements
9. Deployment Architecture (Kubernetes, Expo Web/Mobile)

Format in clean Markdown with proper headings.""",

            "regression_tests": f"""You are a QA lead. Generate comprehensive regression test cases for "View Dezider" Decision Intelligence platform.

Based on these API endpoints:

{api_summary}

Generate test cases covering:
1. Authentication Flow (Register, Login, Session, Logout, Password Reset)
2. PRR Decision CRUD (Create, Read, Update, Delete, Clone, Share)
3. Factor & Option Management
4. Test123 Quick Decisions
5. Pros & Cons (CRUD + Convert to Decision)
6. SWOT Analysis (CRUD + Convert to Decision)
7. CTT Task Tracker
8. GEM Goals
9. Solutions Store
10. Payments & Credits
11. Admin Operations
12. Notifications
13. Edge Cases (empty data, unauthorized access, invalid IDs)

Format each test case as:
**TC-XXX: [Title]**
- Precondition: ...
- Steps: 1. ... 2. ... 3. ...
- Expected Result: ...
- Priority: P0/P1/P2

Format in clean Markdown.""",

            "uat_cases": f"""You are a UAT coordinator. Generate Quick User Acceptance Test scenarios for "View Dezider" — covering the critical user journeys.

Based on these API endpoints:

{api_summary}

Generate concise UAT scenarios for:
1. New User Onboarding (Register → First Decision → Complete PRR flow)
2. Pros & Cons → PRR Conversion Flow
3. SWOT Analysis → PRR Conversion Flow
4. Task Management (CTT) with Decision linkage
5. Solutions Store browsing and integration
6. Payment & Credit purchase
7. Admin operations (user management, settings, approvals)
8. Multi-platform verification (Web + Mobile)
9. Chatbot interaction flows
10. IVR basic decision flow

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
