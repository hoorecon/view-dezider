"""Step-2 matrix imports (XLS / CSV / Google Sheet) + Assessment-step
'Import actuals from URL'. Builds on the same merge + scoring used by the URL
importer so factors, options and numeric scores stay consistent.
"""
import io
import uuid
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import Response
from pydantic import BaseModel

from core.database import db
from core.auth import get_current_user
from core import google_sheets as gs
from core import matrix_import as mx
from core import ai_wallet
from core.url_crawl import crawl_candidates
from core.decision_builder import merge_into_mydezider
from routes.url_analyze import (
    _measure_num, _is_lower_better, _now, ELIGIBILITY_TYPES, DISCLAIMER_VERSION,
)

router = APIRouter(tags=["Decisions"])


# ── shared helpers ───────────────────────────────────────────────────────────
async def _get_decision(decision_id: str, user_id: str) -> Dict[str, Any]:
    d = await db.decisions.find_one({"id": decision_id, "user_id": user_id}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Decision not found")
    return d


def _build_factors_and_scored(factor_names: List[str], candidates: List[Dict[str, Any]]):
    """Build factor dicts (ALL header columns, in order) + per-candidate scores
    (numeric proportional, direction-aware) — matching merge_into_mydezider's
    `candidates[].scores` contract."""
    meta: Dict[str, Dict[str, Any]] = {}
    factors: List[Dict[str, Any]] = []
    for fn in factor_names:
        vals = [c["attributes"].get(fn) for c in candidates]
        nonempty = [v for v in vals if v not in (None, "")]
        nums = [_measure_num(v) for v in nonempty]
        present = [n for n in nums if n is not None]
        is_num = bool(present) and len(present) >= max(1, len(nonempty) // 2)
        lower = is_num and _is_lower_better(fn)
        mn = min(present) if present else None
        mx = max(present) if present else None
        expected = (str(mn) if lower else str(mx)) if (is_num and present) else None
        meta[fn] = {"is_num": is_num, "lower": lower, "min": mn, "max": mx}
        factors.append({
            "name": fn, "data_type": "numeric" if is_num else "text",
            "operator": ("<=" if lower else ">=") if is_num else None,
            "expected_value": expected, "weight": 50,
        })

    scored: List[Dict[str, Any]] = []
    for c in candidates:
        scores: Dict[str, Any] = {}
        for fn in factor_names:
            m = meta[fn]
            if not m["is_num"] or m["min"] is None:
                continue
            x = _measure_num(c["attributes"].get(fn))
            if x is None:
                continue
            if m["max"] == m["min"]:
                scores[fn] = 100
            elif m["lower"]:
                scores[fn] = round((m["max"] - x) / (m["max"] - m["min"]) * 100)
            else:
                scores[fn] = round((x - m["min"]) / (m["max"] - m["min"]) * 100)
        scored.append({"name": c["name"], "attributes": c["attributes"], "scores": scores})
    return factors, scored


async def _apply_matrix(decision_id: str, user_id: str, rows: List[List[Any]]) -> Dict[str, int]:
    try:
        parsed = mx.parse_matrix(rows)
    except ValueError as e:
        raise HTTPException(422, str(e))
    factors, scored = _build_factors_and_scored(parsed["factor_names"], parsed["candidates"])
    counts = await merge_into_mydezider(user_id, decision_id, factors=factors, candidates=scored)
    return {
        "factors_added": counts["factors_added"],
        "options_added": counts["options_added"],
        "item_count": len(parsed["candidates"]),
        "factor_count": len(parsed["factor_names"]),
    }


# ── 1) downloadable template ─────────────────────────────────────────────────
@router.get("/decisions/{decision_id}/factor-matrix-template.xlsx")
async def download_matrix_template(decision_id: str, user: dict = Depends(get_current_user)):
    d = await _get_decision(decision_id, user["user_id"])
    leaf_ids = {f.get("parent_id") for f in d.get("factors", []) if f.get("parent_id")}
    factor_names = [f.get("name") for f in d.get("factors", [])
                    if f.get("id") not in leaf_ids and f.get("name")]
    option_names = [o.get("name") for o in d.get("options", []) if o.get("name")]
    data = mx.build_template_xlsx(factor_names, option_names)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="decision-matrix-template.xlsx"'},
    )


# ── 2a) import from uploaded XLS / CSV ───────────────────────────────────────
@router.post("/decisions/{decision_id}/import-matrix-file")
async def import_matrix_file(decision_id: str, file: UploadFile = File(...),
                             user: dict = Depends(get_current_user)):
    await _get_decision(decision_id, user["user_id"])
    raw = await file.read()
    if not raw:
        raise HTTPException(422, "The uploaded file is empty.")
    name = (file.filename or "").lower()
    try:
        if name.endswith(".csv"):
            rows = mx.extract_rows_from_csv(raw)
        else:
            rows = mx.extract_rows_from_xlsx(raw)
    except Exception:
        raise HTTPException(422, "Could not read the file. Upload a .xlsx or .csv comparison matrix.")
    return await _apply_matrix(decision_id, user["user_id"], rows)


# ── 2b) import from a Google Sheet (public link → CSV, else OAuth) ───────────
class SheetImportRequest(BaseModel):
    sheet_url: str


@router.post("/decisions/{decision_id}/import-matrix-sheet")
async def import_matrix_sheet(decision_id: str, req: SheetImportRequest,
                              user: dict = Depends(get_current_user)):
    await _get_decision(decision_id, user["user_id"])
    url = (req.sheet_url or "").strip()
    sid, _ = mx.gsheet_id_and_gid(url)
    if not sid:
        raise HTTPException(422, "Paste a valid Google Sheets link.")
    rows: List[List[Any]] = []
    try:
        rows = await mx.fetch_public_gsheet_rows(url)
    except PermissionError:
        # Private sheet → fall back to the connected Google account (OAuth).
        try:
            rows = await gs.read_first_sheet(user["user_id"], sid)
        except PermissionError as e:
            raise HTTPException(403, str(e) or "Connect your Google account to import this private sheet.")
        except Exception:
            raise HTTPException(422, "Could not read this Google Sheet via your account.")
    except ValueError as e:
        raise HTTPException(422, str(e))
    if not rows:
        raise HTTPException(422, "The Google Sheet appears to be empty.")
    return await _apply_matrix(decision_id, user["user_id"], rows)


# ── 3) Assessment-step: import ACTUAL VALUES from a URL ──────────────────────
class ActualsFromUrlRequest(BaseModel):
    url: str
    eligibility_type: str
    custom_note: Optional[str] = None
    accepted: bool = False


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, (a or "").lower().strip(), (b or "").lower().strip()).ratio()


def _best(target: str, choices: List[str], threshold: float = 0.5) -> Optional[str]:
    best, score = None, threshold
    for ch in choices:
        r = _ratio(target, ch)
        # token-containment boost (e.g. "Galaxy A57" vs "Samsung Galaxy A57 5G")
        if target.lower() in ch.lower() or ch.lower() in target.lower():
            r = max(r, 0.8)
        if r >= score:
            best, score = ch, r
    return best


@router.post("/decisions/{decision_id}/import-actuals-from-url")
async def import_actuals_from_url(decision_id: str, req: ActualsFromUrlRequest, request: Request,
                                  user: dict = Depends(get_current_user)):
    """Crawl a comparison page and fill ONLY the Actual Values for the decision's
    EXISTING factors (matched by fuzzy name to crawled columns; options matched
    to crawled items). Does not add/remove factors or options. Same consent gate."""
    if not req.accepted:
        raise HTTPException(400, "You must accept the data-access disclaimer to continue.")
    elig = (req.eligibility_type or "").strip().lower()
    if elig not in ELIGIBILITY_TYPES:
        raise HTTPException(400, f"Select a valid access-eligibility type ({', '.join(sorted(ELIGIBILITY_TYPES))}).")
    if elig == "custom" and not (req.custom_note or "").strip():
        raise HTTPException(400, "Describe your access right in the custom field.")

    d = await _get_decision(decision_id, user["user_id"])

    consent_id = uuid.uuid4().hex
    await db.url_access_consents.insert_one({
        "id": consent_id, "user_id": user["user_id"], "url": req.url.strip(),
        "eligibility_type": elig, "custom_note": (req.custom_note or "").strip() or None,
        "disclaimer_version": DISCLAIMER_VERSION, "accepted": True, "target": "actuals",
        "decision_id": decision_id, "ip": (request.client.host if request.client else None),
        "user_agent": request.headers.get("user-agent"), "created_at": _now(),
    })

    try:
        candidates = await crawl_candidates(req.url, user["user_id"])
    except ai_wallet.InsufficientCredits as e:
        raise HTTPException(
            402,
            f"You're out of AI credits (balance {round(e.balance, 2)}) — "
            "top up your wallet to fetch this page.",
        )
    if not candidates:
        raise HTTPException(422, "Could not extract comparable items from this URL.")

    # Build lookup: crawled item name → attributes
    crawl_names = [c["name"] for c in candidates]
    attr_keys: List[str] = []
    for c in candidates:
        for k in (c.get("attributes") or {}):
            if k not in attr_keys:
                attr_keys.append(k)

    leaf_ids = {f.get("parent_id") for f in d.get("factors", []) if f.get("parent_id")}
    leaf_factors = [f for f in d.get("factors", []) if f.get("id") not in leaf_ids]
    options = d.get("options", []) or []

    filled = 0
    matched_opts = 0
    for opt in options:
        crawl_name = _best(opt.get("name", ""), crawl_names)
        if not crawl_name:
            continue
        matched_opts += 1
        cand = next(c for c in candidates if c["name"] == crawl_name)
        cattrs = cand.get("attributes") or {}
        assessments = opt.setdefault("assessments", [])
        for f in leaf_factors:
            col = _best(f.get("name", ""), attr_keys)
            if not col or not str(cattrs.get(col, "")).strip():
                continue
            val = str(cattrs[col]).strip()
            a = next((x for x in assessments if x.get("factor_id") == f["id"]), None)
            if not a:
                a = {"factor_id": f["id"]}
                assessments.append(a)
            a["unit_value"] = val
            a["assessment_mode"] = "manual"
            filled += 1

    await db.decisions.update_one(
        {"id": decision_id, "user_id": user["user_id"]},
        {"$set": {"options": options, "updated_at": _now()}},
    )
    return {
        "consent_id": consent_id, "item_count": len(candidates),
        "matched_options": matched_opts, "filled_cells": filled,
        "factor_count": len(leaf_factors),
    }
