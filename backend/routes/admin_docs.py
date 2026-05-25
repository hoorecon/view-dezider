"""Admin Documentation Hub — Auto-generated PRD, SRS, Test Cases, UAT, API Catalog.

Slim route file. All AI prompts live in /prompts/admin_docs_prompts.py,
all channel/category taxonomy lives in /prompts/admin_docs_taxonomy.py,
and OpenAPI sample-payload generation lives in /core/openapi_helpers.py.
"""

import uuid
import os
import json as json_module
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse

from core.database import db
from core.auth import require_admin
from core.openapi_helpers import generate_sample_payload
from core.rate_limiting import limiter, AI_LIMIT, EXPENSIVE_LIMIT
from prompts.admin_docs_taxonomy import get_channels, get_category
from prompts.admin_docs_prompts import (
    PROMPT_REGISTRY,
    DOC_SYSTEM_MESSAGE,
    DOC_TITLES,
    build_prompt,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/docs", tags=["Admin Documentation Hub"])


# ========================
# API CATALOG ENDPOINT
# ========================

@router.get("/api-catalog")
async def get_api_catalog(
    request: Request,
    channel: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    """Get full API catalog extracted from OpenAPI spec, with channel tagging."""
    from server import app as fastapi_app
    openapi = fastapi_app.openapi()
    paths = openapi.get("paths", {})

    definitions = {}
    if "components" in openapi and "schemas" in openapi["components"]:
        definitions = openapi["components"]["schemas"]
    elif "definitions" in openapi:
        definitions = openapi["definitions"]

    catalog = []
    for path, methods in paths.items():
        for method, detail in methods.items():
            if method not in ("get", "post", "put", "delete", "patch"):
                continue

            channels = get_channels(path)
            category = get_category(path)

            if channel and channel not in channels:
                continue

            # Request body sample
            req_sample = None
            req_body = detail.get("requestBody", {})
            if req_body:
                schema = (req_body.get("content", {})
                          .get("application/json", {})
                          .get("schema", {}))
                if schema:
                    req_sample = generate_sample_payload(schema, definitions)

            # Path / query parameters
            params = [{
                "name": p.get("name"),
                "in": p.get("in"),
                "required": p.get("required", False),
                "type": p.get("schema", {}).get("type", "string"),
                "description": p.get("description", ""),
            } for p in detail.get("parameters", [])]

            # Response sample (200 / 201)
            resp_sample = None
            success_resp = detail.get("responses", {}).get(
                "200", detail.get("responses", {}).get("201", {})
            )
            if success_resp:
                resp_schema = (success_resp.get("content", {})
                               .get("application/json", {})
                               .get("schema", {}))
                if resp_schema:
                    resp_sample = generate_sample_payload(resp_schema, definitions)

            catalog.append({
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
            })

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
    user: dict = Depends(require_admin),
):
    """Export full API catalog as Postman Collection v2.1 JSON (downloadable)."""
    from server import app as fastapi_app
    openapi = fastapi_app.openapi()
    paths = openapi.get("paths", {})
    definitions = {}
    if "components" in openapi and "schemas" in openapi["components"]:
        definitions = openapi["components"]["schemas"]

    items_by_category = {}
    for path, methods in paths.items():
        for method, detail in methods.items():
            if method not in ("get", "post", "put", "delete", "patch"):
                continue

            category = get_category(path)
            channels = get_channels(path)

            req_body_raw = None
            req_body = detail.get("requestBody", {})
            if req_body:
                schema = (req_body.get("content", {})
                          .get("application/json", {})
                          .get("schema", {}))
                if schema:
                    sample = generate_sample_payload(schema, definitions)
                    if sample:
                        req_body_raw = json_module.dumps(sample, indent=2)

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

            postman_url = path.replace("{", ":").replace("}", "")

            pm_request = {
                "method": method.upper(),
                "header": [
                    {"key": "Content-Type", "value": "application/json"},
                    {"key": "Authorization", "value": "Bearer {{AUTH_TOKEN}}"},
                ],
                "url": {
                    "raw": "{{BASE_URL}}" + postman_url + (
                        "?" + "&".join(f"{q['key']}=" for q in query_params)
                        if query_params else ""
                    ),
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

            desc_parts = []
            if detail.get("description"):
                desc_parts.append(detail["description"])
            desc_parts.append(f"Channels: {', '.join(channels)}")
            pm_request["description"] = "\n".join(desc_parts)

            items_by_category.setdefault(category, []).append({
                "name": detail.get("summary") or f"{method.upper()} {path}",
                "request": pm_request,
                "response": [],
            })

    folders = [{"name": cat, "item": items} for cat, items in sorted(items_by_category.items())]

    collection = {
        "info": {
            "name": "View Dezider API — Full Collection",
            "description": (
                "Auto-generated Postman Collection from View Dezider OpenAPI schema.\n"
                f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
            ),
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

DOC_TYPES = list(PROMPT_REGISTRY.keys())  # ["prd", "srs", "regression_tests", "uat_cases"]


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
@limiter.limit(AI_LIMIT)
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
    await db.admin_docs.update_one({"doc_type": doc_type}, {"$set": doc}, upsert=True)
    return doc


@router.post("/refresh-all")
@limiter.limit(EXPENSIVE_LIMIT)
async def refresh_all_documents(request: Request, user: dict = Depends(require_admin)):
    """Regenerate all documents at once."""
    now = datetime.now(timezone.utc)
    results = {}

    for doc_type in DOC_TYPES:
        try:
            content = await _generate_doc_for_type(doc_type, user["user_id"])
            await db.admin_docs.update_one(
                {"doc_type": doc_type},
                {"$set": {
                    "doc_type": doc_type,
                    "content": content,
                    "generated_at": now,
                    "generated_by": user.get("name", user["user_id"]),
                }},
                upsert=True,
            )
            results[doc_type] = "success"
        except Exception as e:
            logger.error(f"Failed to generate {doc_type}: {e}")
            results[doc_type] = f"error: {str(e)}"

    return {"results": results, "generated_at": now.isoformat()}


# ========================
# INTERNAL HELPERS
# ========================

async def _generate_doc_for_type(doc_type: str, user_id: str) -> str:
    """Build API summary then delegate to AI generator (with fallback)."""
    from server import app as fastapi_app
    openapi = fastapi_app.openapi()
    paths = openapi.get("paths", {})

    endpoint_summary = []
    for path, methods in paths.items():
        for method, detail in methods.items():
            if method not in ("get", "post", "put", "delete", "patch"):
                continue
            desc = (detail.get("summary") or detail.get("description") or "")[:60]
            if desc:
                endpoint_summary.append(f"{method.upper()} {path} — {desc}")

    # PRD/SRS need broad coverage; tests/UAT prefer module-grouping for token economy.
    if doc_type in ("prd", "srs"):
        api_summary_text = "\n".join(endpoint_summary[:150])
    else:
        prefix_groups = {}
        for ep in endpoint_summary:
            parts = ep.split(" /api/")
            if len(parts) > 1:
                prefix = "/api/" + parts[1].split("/")[0]
                prefix_groups[prefix] = prefix_groups.get(prefix, 0) + 1
        module_overview = "\n".join(
            f"  {prefix}: {count} endpoints" for prefix, count in sorted(prefix_groups.items())
        )
        api_summary_text = (
            f"Module summary ({len(endpoint_summary)} total endpoints):\n"
            f"{module_overview}\n\nKey endpoints:\n"
            + "\n".join(endpoint_summary[:80])
        )

    return await _generate_doc_with_ai(doc_type, api_summary_text, user_id)


async def _generate_doc_with_ai(doc_type: str, api_summary: str, user_id: str) -> str:
    """Use AI to generate a document. Falls back to a template on error."""
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        return _fallback_doc(doc_type, api_summary)

    try:
        from core.llm_compat import LlmChat, UserMessage  # provider-agnostic shim (Emergent | direct via litellm)

        prompt = build_prompt(doc_type, api_summary)
        chat = LlmChat(
            api_key=api_key,
            session_id=f"admin_doc_{user_id}_{uuid.uuid4().hex[:8]}",
            system_message=DOC_SYSTEM_MESSAGE,
        ).with_model("openai", "gpt-4.1-mini")

        response = await chat.send_message(UserMessage(text=prompt))
        return response.strip()
    except Exception as e:
        logger.error(f"AI doc generation failed for {doc_type}: {e}")
        return _fallback_doc(doc_type, api_summary)


def _fallback_doc(doc_type: str, api_summary: str) -> str:
    """Fallback when AI is unavailable — return a structured template."""
    title = DOC_TITLES.get(doc_type, "Document")
    return f"""# {title}

*Auto-generated on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*
*AI generation unavailable — showing endpoint summary*

## API Endpoints Detected

```
{api_summary}
```

> To get AI-generated content, ensure EMERGENT_LLM_KEY is configured in backend environment.
"""
