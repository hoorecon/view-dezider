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
