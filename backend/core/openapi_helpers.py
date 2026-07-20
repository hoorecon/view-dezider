"""Shared OpenAPI utilities — sample payload generation from JSON schemas.

Used by Admin Docs (API Catalog + Postman export) and any future tool that
wants to materialise example bodies from FastAPI's auto-generated OpenAPI spec.
"""
from typing import Any, Dict


def generate_sample_payload(schema: Dict[str, Any], definitions: Dict[str, Any], depth: int = 0) -> Any:
    """Generate a sample payload from an OpenAPI schema definition.

    Recursive with a depth cap to guard against pathological self-referencing
    schemas. Resolves $ref against the provided definitions map.
    """
    if depth > 4:
        return {}
    if "$ref" in schema:
        ref_name = schema["$ref"].split("/")[-1]
        if ref_name in definitions:
            return generate_sample_payload(definitions[ref_name], definitions, depth + 1)
        return {}

    schema_type = schema.get("type", "object")
    if schema_type == "object":
        result: Dict[str, Any] = {}
        props = schema.get("properties", {})
        for key, prop in props.items():
            if "$ref" in prop:
                ref_name = prop["$ref"].split("/")[-1]
                if ref_name in definitions:
                    result[key] = generate_sample_payload(definitions[ref_name], definitions, depth + 1)
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
                result[key] = [generate_sample_payload(items, definitions, depth + 1)]
            else:
                result[key] = None
        return result
    elif schema_type == "array":
        items = schema.get("items", {})
        return [generate_sample_payload(items, definitions, depth + 1)]
    elif schema_type == "string":
        return schema.get("default", "sample_string")
    elif schema_type == "integer":
        return schema.get("default", 0)
    elif schema_type == "number":
        return schema.get("default", 0.0)
    elif schema_type == "boolean":
        return schema.get("default", True)
    return {}


def build_postman_collection(openapi: Dict[str, Any]) -> Dict[str, Any]:
    """Build a Postman Collection v2.1 dict from a FastAPI OpenAPI spec.

    Single source of truth for BOTH:
      • GET /api/admin/docs/postman-collection  (live download, admin-only)
      • backend/scripts/generate_postman_collection.py  (writes /app/docs/Postman_Collection.json)

    Folder = category from prompts.admin_docs_taxonomy.get_category (longest-prefix
    + subpath overrides). Special auth: /api/adtaker/self/* requests carry
    X-Adtaker-Key/-Secret headers instead of the Bearer token.
    """
    import json as _json
    from datetime import datetime, timezone
    from prompts.admin_docs_taxonomy import get_category, get_channels

    paths = openapi.get("paths", {})
    definitions = openapi.get("components", {}).get("schemas", {})

    items_by_category: Dict[str, list] = {}
    total_requests = 0
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
                        req_body_raw = _json.dumps(sample, indent=2)

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

            # Auth headers: AdTaker self-serve uses API-key headers, not Bearer.
            if path.startswith("/api/adtaker/self"):
                headers = [
                    {"key": "Content-Type", "value": "application/json"},
                    {"key": "X-Adtaker-Key", "value": "{{adtakerKey}}"},
                    {"key": "X-Adtaker-Secret", "value": "{{adtakerSecret}}"},
                ]
            else:
                headers = [
                    {"key": "Content-Type", "value": "application/json"},
                    {"key": "Authorization", "value": "Bearer {{AUTH_TOKEN}}"},
                ]

            pm_request = {
                "method": method.upper(),
                "header": headers,
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
            total_requests += 1

    folders = [{"name": cat, "item": items} for cat, items in sorted(items_by_category.items())]

    return {
        "info": {
            "name": "View Dezider API — Full Collection",
            "description": (
                "Auto-generated Postman Collection from View Dezider OpenAPI schema.\n"
                f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
                f"{len(folders)} folders · {total_requests} requests.\n"
                "Regenerate: `python backend/scripts/generate_postman_collection.py` "
                "or download from GET /api/admin/docs/postman-collection (admin)."
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": folders,
        "variable": [
            {"key": "BASE_URL", "value": "https://your-domain.com", "type": "string"},
            {"key": "AUTH_TOKEN", "value": "session_xxx", "type": "string"},
            {"key": "adtakerKey", "value": "dzk_xxx", "type": "string"},
            {"key": "adtakerSecret", "value": "dzs_xxx", "type": "string"},
            {"key": "trackerId", "value": "DZ-PUB-XXXXXXXX", "type": "string"},
            {"key": "templateId", "value": "bmp-55-patterns", "type": "string"},
            {"key": "decisionId", "value": "", "type": "string"},
            {"key": "finderJobId", "value": "", "type": "string"},
        ],
    }
