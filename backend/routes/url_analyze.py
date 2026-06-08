"""Standalone "Analyse a URL" — end-user feature.

Crawls a user-pasted comparison/filter page (after an explicit legal +
site-access-rights consent), derives factors from the extracted attributes,
scores each item, and creates a MyDezider decision OR a Pros & Cons analysis
pre-filled with options + factors — landing the user in the assessment step.

Legal model: unlike the partner Screener (admin attestation), the standalone
flow places the legal responsibility on the END USER via a mandatory consent
record (access-eligibility type + disclaimer acceptance), stored for audit.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Request

from core.database import db
from core.auth import get_current_user
from core.url_crawl import crawl_candidates
from core.decision_builder import (
    create_mydezider_from_candidates, create_pros_cons_from_candidates,
    merge_into_mydezider,
)

router = APIRouter(prefix="/url-analyze", tags=["URL Analyse"])

DISCLAIMER_VERSION = "2026-06-08.v1"
ELIGIBILITY_TYPES = {"own", "partner", "free_public", "custom"}
_NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def _now():
    return datetime.now(timezone.utc)


def _num(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = _NUM_RE.search(str(v).replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


class AnalyzeRequest(BaseModel):
    url: str
    eligibility_type: str                       # own | partner | free_public | custom
    custom_note: Optional[str] = None           # required when eligibility_type == custom
    accepted: bool = False                      # disclaimer acceptance (mandatory)
    target: str = "mydezider"                   # mydezider | pros_cons
    title: Optional[str] = None
    life_area: Optional[str] = None
    decision_type: Optional[str] = None
    max_factors: int = Field(default=8, ge=1, le=20)


def _derive_factors_and_scores(
    candidates: List[Dict[str, Any]], max_factors: int,
) -> (List[Dict[str, Any]], List[Dict[str, Any]]):
    """Build a factor list from the union of candidate attribute keys (most-
    populated numeric keys first), then proportionally score each item."""
    # Collect keys in first-seen order, count numeric coverage.
    order: List[str] = []
    numeric_count: Dict[str, int] = {}
    total_count: Dict[str, int] = {}
    name_keys = {"name", "Name", "title", "Title", "scheme", "fund", "product"}
    for c in candidates:
        for k, v in (c.get("attributes") or {}).items():
            if k in name_keys:
                continue
            if k not in total_count:
                order.append(k)
                total_count[k] = 0
                numeric_count[k] = 0
            total_count[k] += 1
            if _num(v) is not None:
                numeric_count[k] += 1

    # Prefer mostly-numeric, well-populated columns.
    def _key_rank(k: str):
        return (numeric_count[k] / max(1, total_count[k]), total_count[k])
    ranked_keys = sorted(order, key=_key_rank, reverse=True)[:max_factors]

    factors: List[Dict[str, Any]] = []
    for k in ranked_keys:
        is_numeric = numeric_count[k] >= max(1, total_count[k] // 2)
        vals = [_num(c.get("attributes", {}).get(k)) for c in candidates]
        nums = [v for v in vals if v is not None]
        expected = str(max(nums)) if (is_numeric and nums) else None
        factors.append({
            "name": k,
            "data_type": "numeric" if is_numeric else "text",
            "operator": ">=" if is_numeric else None,
            "expected_value": expected,
            "weight": 50,
            "_min": min(nums) if nums else None,
            "_max": max(nums) if nums else None,
        })

    # Proportional 0..100 scoring (higher = better, normalised across items).
    scored: List[Dict[str, Any]] = []
    for c in candidates:
        scores: Dict[str, Optional[float]] = {}
        for f in factors:
            if f["data_type"] != "numeric":
                scores[f["name"]] = None
                continue
            v = _num(c.get("attributes", {}).get(f["name"]))
            mn, mx = f["_min"], f["_max"]
            if v is None or mn is None or mx is None:
                scores[f["name"]] = None
            elif mx == mn:
                scores[f["name"]] = 100.0
            else:
                scores[f["name"]] = round((v - mn) / (mx - mn) * 100.0, 1)
        scored.append({"name": c.get("name"), "attributes": c.get("attributes"), "scores": scores})

    for f in factors:
        f.pop("_min", None)
        f.pop("_max", None)
    return factors, scored


@router.post("")
async def analyze_url(req: AnalyzeRequest, request: Request, user: dict = Depends(get_current_user)):
    # ── Consent validation (legal gate) ──
    if not req.accepted:
        raise HTTPException(400, "You must accept the data-access disclaimer to continue.")
    elig = (req.eligibility_type or "").strip().lower()
    if elig not in ELIGIBILITY_TYPES:
        raise HTTPException(400, f"Select a valid access-eligibility type ({', '.join(sorted(ELIGIBILITY_TYPES))}).")
    if elig == "custom" and not (req.custom_note or "").strip():
        raise HTTPException(400, "Describe your access right in the custom field.")
    target = (req.target or "mydezider").lower()
    if target not in ("mydezider", "pros_cons"):
        raise HTTPException(400, "target must be 'mydezider' or 'pros_cons'.")

    # ── Persist auditable consent BEFORE any fetch ──
    consent_id = uuid.uuid4().hex
    await db.url_access_consents.insert_one({
        "id": consent_id, "user_id": user["user_id"], "url": req.url.strip(),
        "eligibility_type": elig, "custom_note": (req.custom_note or "").strip() or None,
        "disclaimer_version": DISCLAIMER_VERSION, "accepted": True, "target": target,
        "ip": (request.client.host if request.client else None),
        "user_agent": request.headers.get("user-agent"),
        "created_at": _now(),
    })

    # ── Crawl → derive → build ──
    candidates = await crawl_candidates(req.url, user["user_id"])
    if len(candidates) < 2:
        raise HTTPException(422, "Need at least 2 comparable items on the page to build a decision.")

    factors, scored = _derive_factors_and_scores(candidates, req.max_factors)
    if not factors:
        raise HTTPException(422, "Could not derive comparable factors from the page.")

    title = (req.title or "").strip() or f"Analyse: {req.url.strip()[:60]}"
    context = f"Auto-built from a {elig.replace('_', '/')} URL ({len(candidates)} items)."

    if target == "pros_cons":
        new_id = await create_pros_cons_from_candidates(
            user["user_id"], title=title, context=context,
            life_area=req.life_area, decision_type=req.decision_type,
            factors=factors, candidates=scored, source_label="url_analyze",
        )
    else:
        new_id = await create_mydezider_from_candidates(
            user["user_id"], title=title, context=context,
            life_area=req.life_area, decision_type=req.decision_type,
            factors=factors, candidates=scored, source_label="url_analyze",
        )

    return {
        "id": new_id, "target": target, "consent_id": consent_id,
        "item_count": len(candidates), "factor_count": len(factors),
    }



class ImportRequest(BaseModel):
    url: str
    eligibility_type: str
    custom_note: Optional[str] = None
    accepted: bool = False
    max_factors: int = Field(default=8, ge=1, le=20)


@router.post("/decision/{decision_id}/import")
async def import_url_into_decision(
    decision_id: str, req: ImportRequest, request: Request,
    user: dict = Depends(get_current_user),
):
    """Step-2 "Import from URL" — crawl a comparison page and MERGE the derived
    factors (with suggested Expected values) + options (with assessment %) into
    an EXISTING MyDezider decision, behind the same consent gate."""
    if not req.accepted:
        raise HTTPException(400, "You must accept the data-access disclaimer to continue.")
    elig = (req.eligibility_type or "").strip().lower()
    if elig not in ELIGIBILITY_TYPES:
        raise HTTPException(400, f"Select a valid access-eligibility type ({', '.join(sorted(ELIGIBILITY_TYPES))}).")
    if elig == "custom" and not (req.custom_note or "").strip():
        raise HTTPException(400, "Describe your access right in the custom field.")

    decision = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(404, "Decision not found")

    consent_id = uuid.uuid4().hex
    await db.url_access_consents.insert_one({
        "id": consent_id, "user_id": user["user_id"], "url": req.url.strip(),
        "eligibility_type": elig, "custom_note": (req.custom_note or "").strip() or None,
        "disclaimer_version": DISCLAIMER_VERSION, "accepted": True, "target": "import",
        "decision_id": decision_id,
        "ip": (request.client.host if request.client else None),
        "user_agent": request.headers.get("user-agent"), "created_at": _now(),
    })

    candidates = await crawl_candidates(req.url, user["user_id"])
    if len(candidates) < 2:
        raise HTTPException(422, "Need at least 2 comparable items on the page to import.")
    factors, scored = _derive_factors_and_scores(candidates, req.max_factors)
    if not factors:
        raise HTTPException(422, "Could not derive comparable factors from the page.")

    counts = await merge_into_mydezider(user["user_id"], decision_id, factors=factors, candidates=scored)
    return {
        "decision_id": decision_id, "consent_id": consent_id,
        "item_count": len(candidates),
        "factors_added": counts["factors_added"], "options_added": counts["options_added"],
    }
