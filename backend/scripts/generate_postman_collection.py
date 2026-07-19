"""Regenerate /app/docs/Postman_Collection.json from the live OpenAPI schema.

Usage (from repo root or backend dir):
    cd /app/backend && python scripts/generate_postman_collection.py

Run this after adding/renaming API routes so the committed collection stays in
lock-step with the code. The same builder powers the admin download endpoint
GET /api/admin/docs/postman-collection. Folder names come from
prompts/admin_docs_taxonomy.py — add new path prefixes there so requests land
in a named folder instead of "Other".
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "Postman_Collection.json")


def main():
    from server import app  # noqa: import builds the FastAPI app (no server start)
    from core.openapi_helpers import build_postman_collection

    collection = build_postman_collection(app.openapi())

    folders = collection["item"]
    total = sum(len(f["item"]) for f in folders)
    other = next((f for f in folders if f["name"] == "Other"), None)

    out = os.path.abspath(OUT_PATH)
    with open(out, "w") as fh:
        json.dump(collection, fh, indent=1)

    print(f"Wrote {out}")
    print(f"Folders: {len(folders)} · Requests: {total}")
    if other:
        print(f"WARNING: {len(other['item'])} requests in 'Other' — "
              f"add their prefixes to prompts/admin_docs_taxonomy.py CATEGORY_MAP")
        for it in other["item"][:20]:
            print("   -", it["request"]["method"], it["request"]["url"]["raw"].replace("{{BASE_URL}}", ""))


if __name__ == "__main__":
    main()
