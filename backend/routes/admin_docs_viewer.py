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


def _markdown_to_pdf_bytes(doc: Dict) -> bytes:
    """Render a handbook markdown doc to PDF. ASCII block/flow diagrams (fenced
    code + tables) are emitted as small monospaced Preformatted blocks so they
    stay aligned and fit the page width."""
    import io, html as _html
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Preformatted, Spacer, HRFlowable
    from reportlab.lib import colors

    buf = io.BytesIO()
    pdf = SimpleDocTemplate(
        buf, pagesize=letter, leftMargin=0.55 * inch, rightMargin=0.55 * inch,
        topMargin=0.65 * inch, bottomMargin=0.6 * inch, title=doc.get("title") or doc.get("slug"),
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9.5, leading=13)
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=16, spaceBefore=10, spaceAfter=6, textColor=colors.HexColor("#0F172A"))
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13, spaceBefore=8, spaceAfter=4, textColor=colors.HexColor("#1E293B"))
    h3 = ParagraphStyle("H3", parent=styles["Heading3"], fontSize=11, spaceBefore=6, spaceAfter=3, textColor=colors.HexColor("#334155"))
    code = ParagraphStyle("Code", fontName="Courier", fontSize=7, leading=8.4, textColor=colors.HexColor("#0F172A"))
    bullet = ParagraphStyle("Bul", parent=body, leftIndent=12)
    quote = ParagraphStyle("Quote", parent=body, leftIndent=10, textColor=colors.HexColor("#475569"))

    def inline(t: str) -> str:
        t = _html.escape(t)
        t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', t)
        return t

    flow: List = []
    flow.append(Paragraph(_html.escape(doc.get("title") or doc.get("slug")), h1))
    flow.append(Paragraph(_html.escape(f"{doc.get('slug')}  ·  v{doc.get('version') or '-'}  ·  {doc.get('updated') or ''}"), body))
    flow.append(HRFlowable(width="100%", color=colors.HexColor("#CBD5E1"), spaceBefore=4, spaceAfter=8))

    in_code = False
    code_buf: List[str] = []

    def flush_code():
        if code_buf:
            flow.append(Preformatted("\n".join(code_buf), code))
            flow.append(Spacer(1, 6))
            code_buf.clear()

    for raw in doc["body"].split("\n"):
        line = raw.rstrip("\n")
        if line.strip().startswith("```"):
            if in_code:
                flush_code(); in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_buf.append(raw)
            continue
        s = line.strip()
        if not s:
            flow.append(Spacer(1, 4)); continue
        if s.startswith("_metadata:"):
            continue
        if s.startswith("### "):
            flow.append(Paragraph(inline(s[4:]), h3)); continue
        if s.startswith("## "):
            flow.append(Paragraph(inline(s[3:]), h2)); continue
        if s.startswith("# "):
            flow.append(Paragraph(inline(s[2:]), h1)); continue
        if s.startswith("|") and s.endswith("|"):
            flow.append(Preformatted(line, code)); continue
        if s.startswith("- ") or s.startswith("* "):
            flow.append(Paragraph("• " + inline(s[2:]), bullet)); continue
        if s.startswith("> "):
            flow.append(Paragraph(inline(s[2:]), quote)); continue
        mimg = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", s)
        if mimg:
            flow.append(Paragraph(f"[image: {_html.escape(mimg.group(1) or mimg.group(2))}]", quote)); continue
        flow.append(Paragraph(inline(line), body))
    if in_code:
        flush_code()

    pdf.build(flow)
    return buf.getvalue()


@router.get("/{slug}/pdf")
async def get_doc_pdf(slug: str, user: dict = Depends(require_admin)):
    from fastapi import Response
    doc = _read_doc(slug.upper())
    if not doc:
        raise HTTPException(status_code=404, detail="Doc not found")
    pdf_bytes = _markdown_to_pdf_bytes(doc)
    filename = f"{slug.upper()}.pdf"
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{slug}")
async def get_doc(slug: str, user: dict = Depends(require_admin)):
    doc = _read_doc(slug.upper())
    if not doc:
        raise HTTPException(status_code=404, detail="Doc not found")
    return doc
