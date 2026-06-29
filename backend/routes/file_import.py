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
import uuid
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc)

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

MAX_BYTES = 100 * 1024 * 1024  # raw bytes; large files arrive via chunked upload
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


_RAPID_OCR = None


def _get_rapidocr():
    """Lazily build a single RapidOCR engine (pip-only, no system binary — works
    in both the preview pod and the production Docker image)."""
    global _RAPID_OCR
    if _RAPID_OCR is None:
        from rapidocr_onnxruntime import RapidOCR
        _RAPID_OCR = RapidOCR()
    return _RAPID_OCR


def _ocr_pdf_pages(file_bytes: bytes, page_indices: List[int], progress=None) -> Dict[int, str]:
    """OCR specific PDF pages (0-based) by rendering them to images.

    Used for slides whose text is baked into images (logos, infographics) so the
    embedded text-layer extraction returns nothing. Best-effort: any failure for a
    page just yields no text for that page.
    """
    out: Dict[int, str] = {}
    if not page_indices:
        return out
    try:
        import fitz  # PyMuPDF
        import numpy as np
        from PIL import Image
        ocr = _get_rapidocr()
    except Exception:  # noqa: BLE001 — OCR deps unavailable; skip silently
        return out
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception:  # noqa: BLE001
        return out
    try:
        mat = fitz.Matrix(2, 2)  # ~200 DPI for legible OCR
        total = len(page_indices)
        for n, idx in enumerate(page_indices, 1):
            if 0 <= idx < doc.page_count:
                try:
                    pix = doc.load_page(idx).get_pixmap(matrix=mat)
                    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                    res, _ = ocr(np.array(img))
                    txt = "\n".join(
                        ln[1] for ln in (res or []) if ln and len(ln) > 1 and ln[1]).strip()
                    if txt:
                        out[idx] = txt
                except Exception:  # noqa: BLE001
                    pass
            if progress:
                try:
                    progress("ocr", n, total)
                except Exception:  # noqa: BLE001
                    pass
    finally:
        doc.close()
    return out


# Cap how many image-only pages we OCR per import (keeps latency/cost bounded).
_MAX_OCR_PAGES = 40


def _extract_text(file_bytes: bytes, ftype: str, progress=None) -> str:
    """Blocking — call via asyncio.to_thread."""
    if ftype == "pdf":
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        page_texts: List[str] = []
        ocr_needed: List[int] = []
        for i, p in enumerate(reader.pages):
            t = (p.extract_text() or "").strip()
            page_texts.append(t)
            # Pages with little/no extractable text are likely image slides → OCR them.
            if len(t) < 25:
                ocr_needed.append(i)
        if ocr_needed:
            ocr_map = _ocr_pdf_pages(file_bytes, ocr_needed[:_MAX_OCR_PAGES], progress)
            for i, txt in ocr_map.items():
                page_texts[i] = (page_texts[i] + "\n" + txt).strip() if page_texts[i] else txt
        parts = [f"--- Page {i + 1} ---\n{t}" for i, t in enumerate(page_texts) if t.strip()]
        return "\n\n".join(parts)
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
        import numpy as np
        from PIL import Image
        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        try:
            ocr = _get_rapidocr()
            res, _ = ocr(np.array(image))
            return "\n".join(ln[1] for ln in (res or []) if ln and len(ln) > 1 and ln[1]).strip()
        except Exception:  # noqa: BLE001
            return ""
    raise ValueError(f"Unsupported file type: {ftype}")


_EXTRACT_SYS = (
    "You are extracting decision inputs from a document's text. Identify two things:\n"
    "(1) OPTIONS — every alternative / choice / entity being compared or listed "
    "(e.g. specific companies, investors / VC firms, products, candidates, vendors, paths). "
    "List EVERY option that appears ANYWHERE in the document — scan ALL pages/slides "
    "(text is split with '--- Page N ---' markers). Do NOT stop early, summarize, or drop any. "
    "Include each distinct option exactly once even if it repeats.\n"
    "(2) FACTORS — the criteria used to compare the options. Include BOTH:\n"
    "   - factors explicitly mentioned in the document, AND\n"
    "   - the KEY standard criteria a domain expert would use to compare these specific options, "
    "inferred from the type of option and the user's context, EVEN IF not spelled out in the text.\n"
    "   Example: for choosing a VC / investor, strong factors include Fund Size, Fund Type "
    "(equity / credit / debt), Stage Focus (seed / Series A / growth), Sector Focus, Ticket / Cheque Size, "
    "Cumulative Portfolio Value, Number of Startups Backed, Value-Add / Support, Geography, "
    "Follow-on Capacity, Reputation. Adapt the criteria to whatever the options actually are.\n"
    "Use concise, comparable factor names. Prefer specific, measurable criteria over vague ones.\n"
    'Reply with ONLY compact JSON: {"factors":["..."],"options":["..."]} . '
    "Max 20 factors and 60 options. No prose."
)


async def _ai_extract(user_id: str, text: str, tier: str, context: str) -> Tuple[List[str], List[str]]:
    prompt = (f"CONTEXT (what the user wants to decide): {context}\n\n" if context else "")
    prompt += "DOCUMENT TEXT:\n" + text[:120000]
    out = await metered_chat(
        user_id, system_message=_EXTRACT_SYS, prompt=prompt,
        feature="file_import_extract", session_prefix="fileimp", tier=tier)
    m = re.search(r"\{.*\}", out, re.S)
    data = json.loads(m.group(0)) if m else {}
    factors = [str(x).strip() for x in (data.get("factors") or []) if str(x).strip()][:20]
    options = [str(x).strip() for x in (data.get("options") or []) if str(x).strip()][:60]
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
        raise HTTPException(413, "File too large — keep it under 100 MB.")

    return await _process_import(
        user["user_id"], decision_id, raw, ftype,
        req.ai_tier, req.context or "", req.crawl_web)


async def _process_import(user_id, decision_id, raw, ftype, ai_tier, context, crawl_web, progress=None):
    """Shared import pipeline: extract (with OCR) → AI factors/options →
    (optional) web enrich → merge. `progress(stage, page, total)` is optional."""
    def _p(stage, page=None, total=None):
        if progress:
            try:
                progress(stage, page, total)
            except Exception:  # noqa: BLE001
                pass

    _p("reading")
    try:
        text = await asyncio.to_thread(_extract_text, raw, ftype, progress)
    except Exception as e:  # noqa: BLE001
        logger.warning("file extract failed (%s): %s", ftype, str(e)[:160])
        raise HTTPException(422, "Couldn't read text from this file. Try a clearer file.")
    if len(text.strip()) < 20:
        raise HTTPException(
            422, "No readable text found in the file (an image scan may need clearer text).")

    tier = _tier(ai_tier)
    _p("analyzing")
    try:
        factors, options = await _ai_extract(user_id, text, tier, context or "")
    except ai_wallet.InsufficientCredits as e:
        raise HTTPException(
            402, f"You're out of AI credits (balance {round(e.balance, 2)}) — top up to import.")
    if len(factors) + len(options) < 1:
        raise HTTPException(
            422, "Couldn't find clear factors or options in this file. "
                 "Add a short context note and retry, or use a more structured file.")

    enriched: Dict[str, Dict[str, str]] = {}
    if crawl_web and options:
        _p("enriching")
        try:
            enriched = await _enrich_web(user_id, factors, options, context or "", tier)
        except ai_wallet.InsufficientCredits:
            enriched = {}
        except Exception as e:  # noqa: BLE001
            logger.warning("web enrichment failed: %s", str(e)[:160])
            enriched = {}

    _p("saving")
    factor_dicts = [{"name": n} for n in factors]
    candidates = []
    for o in options:
        uv = enriched.get(o, {})
        uv = {k: v for k, v in uv.items() if k in factors}
        candidates.append({"name": o, "unit_values": uv})

    counts = await merge_into_mydezider(
        user_id, decision_id, factors=factor_dicts, candidates=candidates)

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


# ── Background job + polling (live per-page OCR progress) ─────────────────────
async def _set_job(job_id: str, **fields):
    fields["updated_at"] = _now()
    await db.import_jobs.update_one({"id": job_id}, {"$set": fields})


async def _run_import_job(job_id, user_id, decision_id, upload_id, ftype, ai_tier, crawl_web, context):
    loop = asyncio.get_running_loop()

    def progress(stage, page=None, total=None):
        fut = asyncio.run_coroutine_threadsafe(
            _set_job(job_id, stage=stage, page=page, total_pages=total), loop)
        try:
            fut.result(timeout=5)
        except Exception:  # noqa: BLE001
            pass

    await _set_job(job_id, status="running", stage="reading")
    try:
        try:
            _fn, raw = await asyncio.to_thread(chunk_upload.assemble, upload_id)
        except KeyError:
            raise HTTPException(404, "Upload session expired — please re-pick the file and retry.")
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "Could not assemble the uploaded file.")
        if not raw:
            raise HTTPException(400, "The uploaded file is empty.")
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, "File too large — keep it under 100 MB.")
        result = await _process_import(
            user_id, decision_id, raw, ftype, ai_tier, context, crawl_web, progress=progress)
        await _set_job(job_id, status="done", stage="done", result=result)
    except HTTPException as e:
        await _set_job(job_id, status="error", stage="error", error=str(e.detail))
    except Exception as e:  # noqa: BLE001
        logger.warning("import job %s failed: %s", job_id, str(e)[:200])
        await _set_job(job_id, status="error", stage="error", error="Import failed unexpectedly.")
    finally:
        chunk_upload.discard(upload_id)


@router.post("/decision/{decision_id}/start")
async def start_import_job(
    decision_id: str, req: FileImportRequest,
    user: dict = Depends(get_current_user),
):
    """Kick off an async import and return a job_id to poll for live progress."""
    decision = await db.decisions.find_one(
        {"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(404, "Decision not found")
    if not has_any_llm():
        raise HTTPException(400, "AI is not configured on this server.")
    if not req.upload_id:
        raise HTTPException(400, "upload_id is required (upload the file in chunks first).")
    ftype = _detect_type(req.filename or "")
    if ftype == "doc_legacy":
        raise HTTPException(400, "Legacy .doc files aren't supported — save as .docx or PDF and retry.")
    if ftype == "unknown":
        raise HTTPException(400, "Unsupported file. Use PDF, DOCX, TXT, XLS/XLSX, CSV or an image (JPG/PNG).")

    job_id = uuid.uuid4().hex
    await db.import_jobs.insert_one({
        "id": job_id, "user_id": user["user_id"], "decision_id": decision_id,
        "status": "queued", "stage": "queued", "page": None, "total_pages": None,
        "result": None, "error": None, "created_at": _now(), "updated_at": _now(),
    })
    asyncio.create_task(_run_import_job(
        job_id, user["user_id"], decision_id, req.upload_id, ftype,
        req.ai_tier, req.crawl_web, req.context or ""))
    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
async def get_import_job(job_id: str, user: dict = Depends(get_current_user)):
    job = await db.import_jobs.find_one(
        {"id": job_id, "user_id": user["user_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(404, "Import job not found")
    return job
