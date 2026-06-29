"""
Import from File — Step-2 of MyDezider.

Accept an uploaded document (pdf / docx / txt / xls(x) / csv / image), extract
its text, use AI to derive decision FACTORS + OPTIONS, optionally ENRICH each
option via a real web search (DuckDuckGo) + an LLM synthesis pass (e.g. fill a
VC firm's stage / sector / ticket-size that wasn't in the file), then merge the
result into the decision. Metered through the same AI wallet as URL import.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import re
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException

from core.database import db
from core.auth import get_current_user
from core import ai_wallet
from core.url_crawl import has_any_llm, metered_chat
from core.decision_builder import merge_into_mydezider
from core import chunk_upload

logger = logging.getLogger("file_import")

router = APIRouter(prefix="/file-import", tags=["File Import"])

MAX_BYTES = 8 * 1024 * 1024  # raw bytes (ingress body cap is 10MB; b64 ~+33%)
MAX_OPTIONS_ENRICH = 8


def _tier(v: Optional[str]) -> str:
    return "precise" if (v or "").strip().lower() == "precise" else "fast"


def _detect_type(filename: str) -> str:
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
    if ext == "pdf":
        return "pdf"
    if ext == "docx":
        return "docx"
    if ext in ("txt", "md", "text"):
        return "txt"
    if ext in ("xlsx", "xls"):
        return "xlsx"
    if ext == "csv":
        return "csv"
    if ext in ("jpg", "jpeg", "png", "webp", "bmp", "tiff", "tif", "gif"):
        return "image"
    if ext == "doc":
        return "doc_legacy"
    return "unknown"


def _extract_text(file_bytes: bytes, ftype: str) -> str:
    """Blocking — call via asyncio.to_thread."""
    if ftype == "pdf":
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    if ftype == "docx":
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if ftype == "txt":
        return file_bytes.decode("utf-8", errors="replace")
    if ftype == "csv":
        import pandas as pd
        df = pd.read_csv(io.BytesIO(file_bytes))
        return df.to_csv(index=False)
    if ftype == "xlsx":
        import pandas as pd
        sheets = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None)
        parts = []
        for name, df in sheets.items():
            parts.append(f"# Sheet: {name}\n" + df.to_csv(index=False))
        return "\n\n".join(parts)
    if ftype == "image":
        from PIL import Image
        import pytesseract
        image = Image.open(io.BytesIO(file_bytes))
        return pytesseract.image_to_string(image, lang="eng").strip()
    raise ValueError(f"Unsupported file type: {ftype}")


_EXTRACT_SYS = (
    "You are extracting decision inputs from a document's text. Identify:\n"
    "(1) OPTIONS — the alternatives / choices / entities being compared or listed "
    "(e.g. specific companies, investors / VC firms, products, candidates, vendors, paths).\n"
    "(2) FACTORS — the criteria / attributes used to compare them "
    "(e.g. price, stage, sector, ticket size, location, fit).\n"
    'Reply with ONLY compact JSON: {"factors":["..."],"options":["..."]} . '
    "Use concise names exactly as they appear. Max 15 factors and 24 options. No prose."
)


async def _ai_extract(user_id: str, text: str, tier: str, context: str) -> Tuple[List[str], List[str]]:
    prompt = (f"CONTEXT (what the user wants to decide): {context}\n\n" if context else "")
    prompt += "DOCUMENT TEXT:\n" + text[:16000]
    out = await metered_chat(
        user_id, system_message=_EXTRACT_SYS, prompt=prompt,
        feature="file_import_extract", session_prefix="fileimp", tier=tier)
    m = re.search(r"\{.*\}", out, re.S)
    data = json.loads(m.group(0)) if m else {}
    factors = [str(x).strip() for x in (data.get("factors") or []) if str(x).strip()][:15]
    options = [str(x).strip() for x in (data.get("options") or []) if str(x).strip()][:24]
    return factors, options


def _ddg_snippets(query: str, max_results: int = 4) -> str:
    """Blocking DuckDuckGo text search → joined title/body snippets."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            res = list(ddgs.text(query, max_results=max_results))
        return "\n".join(
            f"- {r.get('title', '')}: {r.get('body', '')}" for r in res if r)
    except Exception as e:  # noqa: BLE001
        logger.warning("DDG search failed for %r: %s", query[:60], str(e)[:120])
        return ""


_ENRICH_SYS = (
    "You fill structured attribute values for decision OPTIONS using web-research snippets. "
    "For each option, give a short value for each factor when the research supports it; "
    "leave it as an empty string when unknown. Keep values terse (a few words / a number). "
    'Reply with ONLY JSON: {"options":[{"name":"<exact option name>","values":{"<factor>":"<value>"}}]} . '
    "No prose."
)


async def _enrich_web(user_id: str, factors: List[str], options: List[str],
                      context: str, tier: str) -> Dict[str, Dict[str, str]]:
    """Web-research the first MAX_OPTIONS_ENRICH options and return
    {option_name: {factor_name: value}} for any values found."""
    targets = options[:MAX_OPTIONS_ENRICH]
    snippets: Dict[str, str] = {}
    for name in targets:
        q = (f"{name} {context}").strip()[:200]
        snippets[name] = await asyncio.to_thread(_ddg_snippets, q)
    research = "\n\n".join(f"## {n}\n{s}" for n, s in snippets.items() if s)
    if not research:
        return {}
    prompt = (
        f"FACTORS: {json.dumps(factors)}\n"
        f"OPTIONS: {json.dumps(targets)}\n\n"
        f"WEB RESEARCH SNIPPETS:\n{research[:14000]}"
    )
    out = await metered_chat(
        user_id, system_message=_ENRICH_SYS, prompt=prompt,
        feature="file_import_enrich", session_prefix="fileimpenrich", tier=tier)
    m = re.search(r"\{.*\}", out, re.S)
    data = json.loads(m.group(0)) if m else {}
    result: Dict[str, Dict[str, str]] = {}
    for item in (data.get("options") or []):
        nm = str(item.get("name") or "").strip()
        vals = item.get("values") or {}
        if not nm or not isinstance(vals, dict):
            continue
        clean = {str(k).strip(): str(v).strip() for k, v in vals.items()
                 if v not in (None, "") and str(v).strip()}
        if clean:
            result[nm] = clean
    return result


class FileImportRequest(BaseModel):
    filename: str
    file_b64: Optional[str] = None
    upload_id: Optional[str] = None
    ai_tier: Optional[str] = "fast"
    crawl_web: bool = False
    context: Optional[str] = ""


@router.post("/decision/{decision_id}")
async def import_file_into_decision(
    decision_id: str, req: FileImportRequest,
    user: dict = Depends(get_current_user),
):
    """Parse a file → AI factors+options → (optional) web enrich → merge."""
    decision = await db.decisions.find_one(
        {"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(404, "Decision not found")
    if not has_any_llm():
        raise HTTPException(400, "AI is not configured on this server.")

    ftype = _detect_type(req.filename or "")
    if ftype == "doc_legacy":
        raise HTTPException(
            400, "Legacy .doc files aren't supported — save as .docx or PDF and retry.")
    if ftype == "unknown":
        raise HTTPException(
            400, "Unsupported file. Use PDF, DOCX, TXT, XLS/XLSX, CSV or an image (JPG/PNG).")

    try:
        if req.upload_id:
            try:
                _fn, raw = await asyncio.to_thread(chunk_upload.assemble, req.upload_id)
            except KeyError:
                raise HTTPException(404, "Upload session expired — please re-pick the file and retry.")
            except HTTPException:
                raise
            except Exception:  # noqa: BLE001
                raise HTTPException(400, "Could not assemble the uploaded file.")
        else:
            raw = base64.b64decode((req.file_b64 or "").split(",")[-1])
    except HTTPException:
        if req.upload_id:
            chunk_upload.discard(req.upload_id)
        raise
    except Exception:  # noqa: BLE001
        raise HTTPException(400, "Could not decode the uploaded file.")
    if req.upload_id:
        chunk_upload.discard(req.upload_id)
    if not raw:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "File too large — keep it under 8 MB.")

    try:
        text = await asyncio.to_thread(_extract_text, raw, ftype)
    except Exception as e:  # noqa: BLE001
        logger.warning("file extract failed (%s): %s", ftype, str(e)[:160])
        raise HTTPException(422, "Couldn't read text from this file. Try a clearer file.")
    if len(text.strip()) < 20:
        raise HTTPException(
            422, "No readable text found in the file (an image scan may need clearer text).")

    tier = _tier(req.ai_tier)
    try:
        factors, options = await _ai_extract(user["user_id"], text, tier, req.context or "")
    except ai_wallet.InsufficientCredits as e:
        raise HTTPException(
            402, f"You're out of AI credits (balance {round(e.balance, 2)}) — top up to import.")
    if len(factors) + len(options) < 1:
        raise HTTPException(
            422, "Couldn't find clear factors or options in this file. "
                 "Add a short context note and retry, or use a more structured file.")

    enriched: Dict[str, Dict[str, str]] = {}
    if req.crawl_web and options:
        try:
            enriched = await _enrich_web(
                user["user_id"], factors, options, req.context or "", tier)
        except ai_wallet.InsufficientCredits:
            enriched = {}  # enrichment is best-effort — never fail the whole import
        except Exception as e:  # noqa: BLE001
            logger.warning("web enrichment failed: %s", str(e)[:160])
            enriched = {}

    factor_dicts = [{"name": n} for n in factors]
    candidates = []
    for o in options:
        uv = enriched.get(o, {})
        # only keep values whose factor name we actually imported
        uv = {k: v for k, v in uv.items() if k in factors}
        candidates.append({"name": o, "unit_values": uv})

    counts = await merge_into_mydezider(
        user["user_id"], decision_id, factors=factor_dicts, candidates=candidates)

    return {
        "mode": "file",
        "file_type": ftype,
        "item_count": len(options),
        "factors_added": counts["factors_added"],
        "options_added": counts["options_added"],
        "enriched": bool(enriched),
        "enriched_count": len(enriched),
        "factors": factors,
        "options": options,
    }
