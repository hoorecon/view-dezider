"""
Admin docs viewer backend.

Serves the markdown sources from /app/docs/ to the in-app admin viewer
at /admin/docs/[slug].

Routes (all admin-only):
  GET /api/admin-docs        → list available docs
  GET /api/admin-docs/{slug} → raw markdown body + parsed metadata
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.auth import require_admin

router = APIRouter(prefix="/admin-docs", tags=["Admin Docs"])

DOCS_DIR = Path("/app/docs")

# Map URL slug → disk filename (markdown + json artefacts)
DOC_FILES: Dict[str, Dict[str, str]] = {
    "INDEX":         {"file": "INDEX.md",                  "title": "Documentation Index"},
    "SYSTEM_KT":     {"file": "SYSTEM_KT.md",              "title": "System KT — Block Diagram & Flow Charts"},
    "PRD":           {"file": "PRD.md",                    "title": "Product Requirements (PRD)"},
    "SRS":           {"file": "SRS.md",                    "title": "System Requirements (SRS)"},
    "API_REFERENCE": {"file": "API_REFERENCE.md",          "title": "REST API Reference"},
    "POSTMAN":       {"file": "POSTMAN.md",                "title": "Postman Collection Guide"},
    "REGRESSION":    {"file": "REGRESSION.md",             "title": "Regression Test Catalogue"},
    "UAT":           {"file": "UAT.md",                    "title": "UAT Test Cases"},
    "ACM":           {"file": "ACM.md",                    "title": "Access Control Matrix"},
    "WOWO":          {"file": "WOWO.md",                   "title": "Ways of Working / Out"},
    "CLD":           {"file": "CLD.md",                    "title": "CLD Engine Spec"},
    "SECURITY":      {"file": "SECURITY.md",               "title": "Security & Threat Model"},
    "DEPLOYMENT":    {"file": "DEPLOYMENT.md",             "title": "Deployment Runbook"},
    "PRODUCTION_DEPLOYMENT": {"file": "PRODUCTION_DEPLOYMENT.md", "title": "Production Deployment Runbook (Live)"},
    "ADMIN_USER_GUIDE": {"file": "ADMIN_USER_GUIDE.md", "title": "Admin User Guide"},
}

_META_RE = re.compile(r"_metadata:\s*\{([^}]*)\}")


def _read_doc(slug: str) -> Optional[Dict]:
    meta = DOC_FILES.get(slug)
    if not meta:
        return None
    p = DOCS_DIR / meta["file"]
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8")
    parsed = {}
    m = _META_RE.search(text)
    if m:
        try:
            inner = m.group(1)
            for piece in re.findall(r'"([^"]+)"\s*:\s*"([^"]*)"', inner):
                parsed[piece[0]] = piece[1]
        except Exception:
            pass
    return {
        "slug": slug,
        "title": meta["title"],
        "file": meta["file"],
        "size_bytes": p.stat().st_size,
        "version": parsed.get("version"),
        "updated": parsed.get("updated"),
        "author": parsed.get("author"),
        "body": text,
    }


@router.get("")
async def list_docs(user: dict = Depends(require_admin)):
    items: List[Dict] = []
    for slug, meta in DOC_FILES.items():
        p = DOCS_DIR / meta["file"]
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        m = _META_RE.search(text)
        version = updated = None
        if m:
            inner = m.group(1)
            for piece in re.findall(r'"([^"]+)"\s*:\s*"([^"]*)"', inner):
                if piece[0] == "version": version = piece[1]
                if piece[0] == "updated": updated = piece[1]
        items.append({
            "slug": slug,
            "title": meta["title"],
            "size_bytes": p.stat().st_size,
            "version": version,
            "updated": updated,
        })
    return {"items": items, "docs_dir": str(DOCS_DIR)}


@router.get("/{slug}")
async def get_doc(slug: str, user: dict = Depends(require_admin)):
    doc = _read_doc(slug.upper())
    if not doc:
        raise HTTPException(status_code=404, detail="Doc not found")
    return doc
