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

import asyncio
import re
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Request

from core.database import db
from core.auth import get_current_user
from core import ai_wallet
from core.url_crawl import (
    has_any_llm, metered_chat,
    fetch_page, fetch_rendered, parse_hierarchy, candidates_from_response,
    page_text,
)
from core.url_detail import ai_extract_detail, deterministic_hint_issues
from core.url_pagetype import classify_page_type
from core.import_verify import verify_detail
from core import url_telemetry
from core import engine_recos
from core.decision_builder import (
    create_mydezider_from_candidates, create_pros_cons_from_candidates,
    create_hierarchical_mydezider, merge_into_mydezider,
    merge_hierarchical_into_mydezider,
)

router = APIRouter(prefix="/url-analyze", tags=["URL Analyse"])

DISCLAIMER_VERSION = "2026-06-08.v1"
ELIGIBILITY_TYPES = {"own", "partner", "free_public", "custom"}
_NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*")

# Columns whose name implies "lower is better" (cost/fee/risk/etc.). Leading word
# boundary + prefix match → catches 'cost'→'costs', 'fee'→'fees', but NOT 'coffee'.
_LOWER_BETTER_RE = re.compile(
    r"\b(cost|fee|expense|expence|price|charge|premium|risk|drawdown|debt|"
    r"loss|latency|delay|downtime|turnaround|distance|emission|pollution|"
    r"defect|error|complaint|churn|mileage|consumption|penalty|deficit|"
    r"overhead|spend|outflow)",
    re.IGNORECASE,
)


def _is_lower_better(name: str) -> bool:
    return bool(_LOWER_BETTER_RE.search(str(name or "")))


async def _quality_status(resp: Dict[str, Any]) -> tuple:
    """Decide success-vs-partial based on the admin-tunable factor quality
    floor. A "thin" extraction (≪ floor) is `partial` — the user gets the
    result, but the run is flagged in Admin Intel and fed into Auto-Tune.
    Returns (status, partial_reason_or_None)."""
    fc = int(resp.get("factors_added") or resp.get("factor_count") or 0)
    oc = int(resp.get("options_added") or resp.get("item_count") or 0)
    qf = await engine_recos.get_quality_floor()
    if fc and fc < qf:
        return ("partial",
                f"Extracted {fc} factor(s) across {oc} option(s) — below the "
                f"configured quality floor of {qf}. Likely a thin parse "
                "(e.g. Name + Price). Review or re-import on the precise tier.")
    return ("success", None)


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


# A value is a "clean measurement" only if it is essentially a single number with
# an optional short unit / leading approx-tilde / trailing parenthetical — e.g.
# "169 g (5.96 oz)", "3500 mAh", "2.10", "~84%". This deliberately REJECTS messy
# spec strings that merely contain digits ("GSM 850 / 900", "2018, August",
# "Android 8.1", "256GB 12GB RAM, 512GB…") so they become qualitative factors
# instead of nonsensical numeric ones.
_MEASURE_RE = re.compile(
    r"^\s*[~≈]?\s*[₹$€£¥]?\s*(-?\d[\d,]*\.?\d*)\s*"   # optional currency + the number
    r"(?:%|°|[a-zA-Z][a-zA-Z0-9./µ\"'-]{0,7})?\s*"      # optional short unit
    r"(?:\([^)]*\))?\s*$"                                # optional trailing parenthetical
)


def _measure_num(v: Any) -> Optional[float]:
    """Return a float ONLY for clean single-measurement values (see _MEASURE_RE)."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s or "/" in s:                 # slashes => lists/ratios (bands, "16/12 GB")
        return None
    m = _MEASURE_RE.match(s)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
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
    ai_tier: str = "fast"                       # fast | precise (Claude via Emergent key)
    # ── Optional accuracy hints (self-healing oracle) ──
    expected_factor_count: Optional[int] = Field(default=None, ge=1, le=200)
    expected_option_count: Optional[int] = Field(default=None, ge=1, le=50)
    first_factor_name: Optional[str] = None
    first_option_name: Optional[str] = None


def _derive_factors_and_scores(
    candidates: List[Dict[str, Any]], max_factors: int,
) -> (List[Dict[str, Any]], List[Dict[str, Any]]):
    """Build a factor list from the union of candidate attribute keys (most-
    populated numeric keys first), then proportionally score each item."""
    # Collect keys in first-seen order, count clean-numeric coverage + value length.
    order: List[str] = []
    numeric_count: Dict[str, int] = {}
    total_count: Dict[str, int] = {}
    len_sum: Dict[str, int] = {}
    name_keys = {"name", "Name", "title", "Title", "scheme", "fund", "product"}
    for c in candidates:
        for k, v in (c.get("attributes") or {}).items():
            if k in name_keys:
                continue
            if k not in total_count:
                order.append(k)
                total_count[k] = 0
                numeric_count[k] = 0
                len_sum[k] = 0
            total_count[k] += 1
            len_sum[k] += len(str(v or ""))
            if _measure_num(v) is not None:
                numeric_count[k] += 1

    def _avg_len(k: str) -> float:
        return len_sum[k] / max(1, total_count[k])

    # Drop columns whose values are too long to be a useful comparison factor
    # (e.g. band lists, multi-line spec blobs). Keep the filter from nuking
    # everything on terse pages.
    usable = [k for k in order if _avg_len(k) <= 60]
    if len(usable) < 2:
        usable = order

    # Prefer mostly clean-numeric, then well-populated, then shorter (tidier) values.
    def _key_rank(k: str):
        return (numeric_count[k] / max(1, total_count[k]), total_count[k], -_avg_len(k))
    ranked_keys = sorted(usable, key=_key_rank, reverse=True)[:max_factors]

    factors: List[Dict[str, Any]] = []
    for k in ranked_keys:
        is_numeric = numeric_count[k] >= max(1, total_count[k] // 2)
        vals = [_measure_num(c.get("attributes", {}).get(k)) for c in candidates]
        nums = [v for v in vals if v is not None]
        lower_better = is_numeric and _is_lower_better(k)
        if is_numeric and nums:
            # "Standard" target = the best observed value for the column's direction.
            expected = str(min(nums)) if lower_better else str(max(nums))
        else:
            expected = None
        factors.append({
            "name": k,
            "data_type": "numeric" if is_numeric else "text",
            "factor_type": _factor_nature(k),
            "operator": ("<=" if lower_better else ">=") if is_numeric else None,
            "expected_value": expected,
            "weight": 50,
            "_min": min(nums) if nums else None,
            "_max": max(nums) if nums else None,
            "_lower": lower_better,
        })

    # Proportional 0..100 scoring, normalised across items, respecting direction
    # (lower-is-better columns score inversely).
    scored: List[Dict[str, Any]] = []
    for c in candidates:
        scores: Dict[str, Optional[float]] = {}
        for f in factors:
            if f["data_type"] != "numeric":
                scores[f["name"]] = None
                continue
            v = _measure_num(c.get("attributes", {}).get(f["name"]))
            mn, mx = f["_min"], f["_max"]
            if v is None or mn is None or mx is None:
                scores[f["name"]] = None
            elif mx == mn:
                scores[f["name"]] = 100.0
            elif f.get("_lower"):
                scores[f["name"]] = round((mx - v) / (mx - mn) * 100.0, 1)
            else:
                scores[f["name"]] = round((v - mn) / (mx - mn) * 100.0, 1)
        scored.append({"name": c.get("name"), "attributes": c.get("attributes"), "scores": scores})

    for f in factors:
        f.pop("_min", None)
        f.pop("_max", None)
        f.pop("_lower", None)
    return factors, scored


# ---------------------------------------------------------------------------
# Hierarchical scoring: numeric rows scored deterministically (proportional,
# direction-aware); remaining text rows scored 0-100 by the LLM (batched, one
# metered call) relative to the compared items. Best-effort — if the LLM is
# unavailable/over-budget, text cells stay un-scored but keep their raw value.
# ---------------------------------------------------------------------------
def _safe_pct(v: Any) -> Optional[int]:
    try:
        return max(0, min(100, int(round(float(v)))))
    except (TypeError, ValueError):
        return None


# Person-dependent judgment factors (Comfort, Luxury Feel, Design Appeal …).
# Everything else on a spec sheet is an undisputed FACT → "quantitative",
# even when its value is text (Color=Blue, SIM=Nano, Furnishing=Semi).
_QUALITATIVE_RE = re.compile(
    r"comfort|feel|luxur|design|aesthet|style|appeal|vibe|impression|experience|"
    r"ease\s*of|user.?friendl|build\s*quality|ambien|premium|elegan", re.I)


def _factor_nature(label: str) -> str:
    return "qualitative" if _QUALITATIVE_RE.search(label or "") else "quantitative"


def _score_hierarchy_numeric(items: List[str], groups: List[Dict[str, Any]]):
    """Returns (row_scores, row_meta, text_rows). row_scores keyed by (gi, ri)."""
    row_scores: Dict[Any, List[Optional[int]]] = {}
    row_meta: Dict[Any, Dict[str, Any]] = {}
    text_rows: List[tuple] = []
    for gi, g in enumerate(groups):
        for ri, row in enumerate(g.get("rows") or []):
            vals = row.get("values") or []
            nums = [_measure_num(v) for v in vals]
            present = [x for x in nums if x is not None]
            if len(present) >= 2:
                lower = _is_lower_better(row["label"])
                mn, mx = min(present), max(present)
                if mx == mn:
                    sc = [100 if x is not None else None for x in nums]
                else:
                    sc = [None if x is None else
                          round((mx - x) / (mx - mn) * 100) if lower else
                          round((x - mn) / (mx - mn) * 100) for x in nums]
                row_scores[(gi, ri)] = sc
                best = mn if lower else mx
                row_meta[(gi, ri)] = {"is_numeric": True, "expected": str(best),
                                      "operator": "<=" if lower else ">=",
                                      "factor_type": _factor_nature(row["label"])}
            else:
                row_meta[(gi, ri)] = {"is_numeric": False,
                                      "factor_type": _factor_nature(row["label"])}
                text_rows.append((gi, ri, row["label"], vals))
    return row_scores, row_meta, text_rows


async def _ai_score_text_rows(user_id: str, items: List[str], text_rows: List[tuple]):
    """One metered LLM call to score all text rows 0-100 per item."""
    if not has_any_llm() or not text_rows:
        return {}
    capped = text_rows[:80]
    payload = [{"i": idx, "attr": label, "values": vals}
               for idx, (gi, ri, label, vals) in enumerate(capped)]
    sys = (
        f"You compare {len(items)} items: {items}. For EACH attribute row, rate every item "
        "0-100 by how good/desirable its value is for that attribute (100 = best of the set). "
        "If higher is naturally worse (price, weight, SAR, fall height), invert so the better "
        "value scores higher. Missing / '-' / 'No' values score low (0-20). "
        "Reply ONLY compact JSON object mapping row index -> array of scores "
        f"(each array length {len(items)}): {{\"0\": [..], \"1\": [..]}}. No prose."
    )
    try:
        out = await metered_chat(user_id, system_message=sys, prompt=json.dumps(payload)[:6000],
                                 feature="url_analyze_hier_score", session_prefix="urlhier")
        m = re.search(r"\{.*\}", out, re.S)
        data = json.loads(m.group(0)) if m else {}
    except Exception:
        return {}
    result: Dict[Any, List[Optional[int]]] = {}
    for idx, (gi, ri, label, vals) in enumerate(capped):
        arr = data.get(str(idx))
        if isinstance(arr, list) and len(arr) >= len(items):
            result[(gi, ri)] = [_safe_pct(x) for x in arr[:len(items)]]
    return result


async def build_hierarchical_decision(user_id: str, hierarchy: Dict[str, Any], *,
                                      title: str, context: str,
                                      life_area: Optional[str], decision_type: Optional[str]):
    items, groups = hierarchy["items"], hierarchy["groups"]
    row_scores, row_meta, text_rows = _score_hierarchy_numeric(items, groups)
    row_scores.update(await _ai_score_text_rows(user_id, items, text_rows))
    return await create_hierarchical_mydezider(
        user_id, title=title, context=context, life_area=life_area,
        decision_type=decision_type, items=items, groups=groups,
        row_scores=row_scores, row_meta=row_meta, source_label="url_analyze",
    )




@router.post("")
async def analyze_url(req: AnalyzeRequest, request: Request, user: dict = Depends(get_current_user)):
    """Telemetry-wrapped entry — EVERY run (success or error) is recorded to
    `url_import_runs` + PostHog for the admin Import-Analytics dashboard."""
    tel = url_telemetry.new_tel(user["user_id"], endpoint="analyze", url=req.url,
                                ai_tier=_tier(req.ai_tier), hints=_hints_of(req))
    try:
        resp = await _analyze_url_inner(req, request, user, tel)
    except ai_wallet.InsufficientCredits as e:
        msg = (f"You're out of AI credits (balance {round(e.balance, 2)}) — "
               "top up your wallet to fetch & analyse this page.")
        await url_telemetry.record_run(tel, status="error", error=msg)
        raise HTTPException(402, msg)
    except HTTPException as e:
        await url_telemetry.record_run(tel, status="error", error=f"HTTP {e.status_code}: {e.detail}")
        raise
    except Exception as e:  # noqa: BLE001
        await url_telemetry.record_run(tel, status="error", error=f"{type(e).__name__}: {str(e)[:300]}")
        raise
    tel["decision_id"] = resp.get("id")
    final_status, partial_reason = await _quality_status(resp)
    if partial_reason:
        tel["partial_reason"] = partial_reason
    resp["run_id"] = await url_telemetry.record_run(
        tel, status=final_status, response=resp,
        error=partial_reason if final_status == "partial" else None)
    return resp


async def _analyze_url_inner(req: AnalyzeRequest, request: Request, user: dict,
                             tel: Dict[str, Any]) -> Dict[str, Any]:
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

    title = (req.title or "").strip() or f"Analyse: {req.url.strip()[:60]}"
    tier = _tier(req.ai_tier)
    hints = _hints_of(req)

    # ── Fetch ONCE; run all parse strategies against the same response. ──
    r = await fetch_page(req.url, user_id=user["user_id"])
    is_json = "json" in r.headers.get("content-type", "")

    # ── LLM page-type classification (always-on): selects the specialised
    # extraction prompt AND powers per-page-type accuracy analytics. ──
    page_type = None
    if not is_json:
        cls = await classify_page_type(user["user_id"], r.text, req.url)
        page_type = cls["page_type"]
        tel["page_type"] = cls["page_type"]
        tel["page_type_confidence"] = cls["confidence"]
        tel["classifier_provider"] = cls["provider"]

    # ── MyDezider: prefer a FULL two-level import when the page is a category-
    # grouped comparison matrix (e.g. GSMArena: 15 categories × sub-specs) —
    # but ONLY when it does not contradict the user's accuracy hints. ──
    if target == "mydezider" and not is_json:
        hierarchy = parse_hierarchy(r.text)
        if (hierarchy and len(hierarchy.get("groups", [])) >= 2
                and len(hierarchy.get("items", [])) >= 2
                and not deterministic_hint_issues(hints, hierarchy=hierarchy)):
            sub_total = sum(len(g.get("rows") or []) for g in hierarchy["groups"])
            ctx = (f"Auto-built from a {elig.replace('_', '/')} URL — {len(hierarchy['items'])} options, "
                   f"{len(hierarchy['groups'])} categories, {sub_total} sub-factors.")
            built = await build_hierarchical_decision(
                user["user_id"], hierarchy, title=title, context=ctx,
                life_area=req.life_area, decision_type=req.decision_type)
            tel["route"] = "deterministic_hier"
            return {
                "id": built["id"], "target": target, "consent_id": consent_id,
                "mode": "hierarchical",
                "item_count": built["option_count"],
                "category_count": built["category_count"],
                "factor_count": built["subfactor_count"],
            }

    # ── Flat comparison (Pros & Cons always; MyDezider when not a matrix).
    # HINTS ARE LAW: a deterministic parse must MATCH any user hints, else we
    # escalate to the hint-guided AI extraction (parse kept as fallback). ──
    det_fallback = None
    candidates = await candidates_from_response(r, user["user_id"], allow_ai=False)
    if len(candidates) >= 2:
        factors, scored = _derive_factors_and_scores(candidates, req.max_factors)
        if factors:
            det_issues = deterministic_hint_issues(hints, factors=factors, candidates=scored)
            det_thin = tier == "precise" and len(factors) < 3
            if not det_issues and not det_thin:
                tel["route"] = "deterministic_flat"
                return await _create_from_flat(user, req, target, title, elig, consent_id,
                                               factors, scored, len(candidates))
            det_fallback = (factors, scored, det_issues)

    # ── AI-guided extraction (detail OR comparison/listing pages): smart
    # factors with operators + the listed items as options. User hints are
    # injected as ground truth + verified with one corrective retry. ──
    if target == "mydezider" and not is_json:
        detail = await _extract_detail_for_url(user["user_id"], req.url, r.text, tier,
                                               hints=hints, page_type=page_type, tel=tel)
        if (detail and det_fallback
                and len(detail.get("hint_warnings") or []) > len(det_fallback[2])):
            detail = None  # deterministic parse was closer to the user's hints
        if detail:
            tel["route"] = "ai_extraction"
            d_title = (req.title or "").strip() or detail["main_name"][:80]
            d_ctx = f"Auto-built from a {elig.replace('_', '/')} detail page."
            if detail["kind"] == "hier":
                built = await create_hierarchical_mydezider(
                    user["user_id"], title=d_title, context=d_ctx,
                    life_area=req.life_area, decision_type=req.decision_type,
                    items=detail["items"], groups=detail["groups"],
                    row_scores=detail["row_scores"], row_meta=detail["row_meta"],
                    source_label="url_analyze")
                return {
                    "id": built["id"], "target": target, "consent_id": consent_id,
                    "mode": "detail", "structure": "hierarchical",
                    "main_item": detail["main_name"],
                    "ai_provider": detail.get("provider") or "",
                    "hint_warnings": detail.get("hint_warnings") or [],
                    "item_count": built["option_count"],
                    "category_count": built["category_count"],
                    "factor_count": built["subfactor_count"],
                }
            new_id = await create_mydezider_from_candidates(
                user["user_id"], title=d_title, context=d_ctx,
                life_area=req.life_area, decision_type=req.decision_type,
                factors=detail["factors"], candidates=detail["candidates"],
                source_label="url_analyze",
            )
            return {
                "id": new_id, "target": target, "consent_id": consent_id,
                "mode": "detail", "structure": "flat",
                "main_item": detail["main_name"],
                "ai_provider": detail.get("provider") or "",
                "hint_warnings": detail.get("hint_warnings") or [],
                "item_count": len(detail["candidates"]),
                "factor_count": len(detail["factors"]),
            }

    # ── AI couldn't produce a hint-conformant structure — fall back to the
    # deterministic parse rather than fail. ──
    if det_fallback:
        factors, scored, _det_issues = det_fallback
        tel["route"] = "deterministic_fallback"
        resp = await _create_from_flat(user, req, target, title, elig, consent_id,
                                       factors, scored, len(scored))
        resp["hint_warnings"] = _det_issues
        return resp

    # ── LLM flat fallback for table-less / irregular comparison pages ──
    if len(candidates) < 2:
        candidates = await candidates_from_response(r, user["user_id"], allow_ai=True)
    if len(candidates) < 2:
        raise HTTPException(422, "Need at least 2 comparable items on the page to build a decision.")

    factors, scored = _derive_factors_and_scores(candidates, req.max_factors)
    if not factors:
        raise HTTPException(422, "Could not derive comparable factors from the page.")
    tel["route"] = "llm_flat_fallback"
    return await _create_from_flat(user, req, target, title, elig, consent_id,
                                   factors, scored, len(candidates))


async def _create_from_flat(user, req, target, title, elig, consent_id,
                            factors, scored, item_count):
    context = f"Auto-built from a {elig.replace('_', '/')} URL ({item_count} items)."
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
        "item_count": item_count, "factor_count": len(factors),
    }



class ImportRequest(BaseModel):
    url: str
    eligibility_type: str
    custom_note: Optional[str] = None
    accepted: bool = False
    max_factors: int = Field(default=8, ge=1, le=20)
    ai_tier: str = "fast"                       # fast | precise (Claude via Emergent key)
    # Client-generated id the frontend polls (GET /url-analyze/progress/{id})
    # for live stage/percentage updates while this request runs.
    progress_id: Optional[str] = None
    # ── Optional accuracy hints (self-healing oracle) ──
    expected_factor_count: Optional[int] = Field(default=None, ge=1, le=200)
    expected_option_count: Optional[int] = Field(default=None, ge=1, le=50)
    first_factor_name: Optional[str] = None
    first_option_name: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Live import progress — the import POST can legitimately run 30-120s (rendered
# fetch + LLM extraction + corrective retry). The backend reports real stages
# here; the frontend polls while the request is in flight. Docs expire via a
# TTL index (created in core.database boot indexes are heavy — do it lazily).
# ─────────────────────────────────────────────────────────────────────────────
_progress_ttl_ready = False


def _progress_writer(progress_id: Optional[str], user_id: str):
    """Returns async prog(pct, label, status='running') that upserts the
    progress doc. No-op writer when the client didn't send a progress_id."""
    async def _noop(pct: int, label: str, status: str = "running"):
        return None

    if not progress_id:
        return _noop

    async def _write(pct: int, label: str, status: str = "running"):
        global _progress_ttl_ready
        try:
            if not _progress_ttl_ready:
                await db.url_import_progress.create_index(
                    "expires_at", expireAfterSeconds=0)
                _progress_ttl_ready = True
            from datetime import timedelta
            await db.url_import_progress.update_one(
                {"id": progress_id},
                {"$set": {"id": progress_id, "user_id": user_id,
                          "pct": int(pct), "label": label, "status": status,
                          "updated_at": _now(),
                          "expires_at": _now() + timedelta(hours=1)}},
                upsert=True)
        except Exception:  # noqa: BLE001 — progress is best-effort, never block import
            pass
    return _write


@router.get("/progress/{progress_id}")
async def get_import_progress(progress_id: str, user: dict = Depends(get_current_user)):
    doc = await db.url_import_progress.find_one(
        {"id": progress_id, "user_id": user["user_id"]}, {"_id": 0})
    if not doc:
        return {"pct": 5, "label": "Starting…", "status": "running"}
    return {"pct": doc.get("pct", 0), "label": doc.get("label", ""),
            "status": doc.get("status", "running")}


@router.get("/runs/{run_id}/provenance")
async def get_run_provenance(run_id: str, user: dict = Depends(get_current_user)):
    """Source quotes for every verified value of one import run — lets the
    user see EXACTLY which page line each number came from (e.g. ex-showroom
    vs on-road pricing variants)."""
    doc = await db.url_import_runs.find_one(
        {"id": run_id, "user_id": user["user_id"]},
        {"_id": 0, "url": 1, "verification": 1, "evidence": 1})
    if not doc:
        raise HTTPException(404, "Import run not found")
    return {"url": doc.get("url"), "verification": doc.get("verification") or {},
            "evidence": doc.get("evidence") or []}


def _hints_of(req) -> Optional[Dict[str, Any]]:
    h = {k: getattr(req, k, None) for k in
         ("expected_factor_count", "expected_option_count",
          "first_factor_name", "first_option_name")}
    h = {k: v for k, v in h.items() if v not in (None, "", 0)}
    return h or None


def _tier(v: Optional[str]) -> str:
    return "precise" if (v or "").strip().lower() == "precise" else "fast"


# Cap for DETAIL-page imports — a single listing legitimately yields 15-25
# factors (specs), unlike a comparison table where 8 columns is plenty.
DETAIL_MAX_FACTORS = 24


async def _extract_detail_for_url(user_id: str, url: str, html: str, tier: str,
                                  hints: Optional[Dict[str, Any]] = None,
                                  page_type: Optional[str] = None,
                                  tel: Optional[Dict[str, Any]] = None,
                                  rendered_task: Optional["asyncio.Task"] = None,
                                  prog=None):
    """AI extraction pipeline (detail OR comparison/listing pages): escalate to
    RENDERED HTML when ScraperAPI is configured (similar-items rails are usually
    JS-loaded), then run the single-call hint-guided LLM extraction (+ one
    corrective retry against the user's accuracy hints) with the prompt
    specialised for the classified `page_type`. The exact prompt + raw response
    are captured into `tel["ai"]` for Import-Analytics.
    `rendered_task` (if given) is an already-running fetch_rendered task so the
    rendered fetch overlaps the page-type classification.
    Translates InsufficientCredits → 402."""
    rendered = await rendered_task if rendered_task is not None else await fetch_rendered(url, user_id=user_id)
    cfg = await ai_wallet.get_config()
    threshold = int(cfg.get("import_group_threshold") or 15)
    max_factors = max(DETAIL_MAX_FACTORS, int((hints or {}).get("expected_factor_count") or 0))
    capture: Dict[str, Any] = {}
    if tel is not None:
        tel["ai"] = capture
    if prog:
        await prog(62, "AI is extracting factors & options…")
    try:
        detail = await ai_extract_detail(user_id, rendered or html, tier=tier,
                                         max_factors=max_factors,
                                         group_threshold=threshold, hints=hints,
                                         page_type=page_type, capture=capture)
    except ai_wallet.InsufficientCredits as e:
        raise HTTPException(
            402,
            f"You're out of AI credits (balance {round(e.balance, 2)}). "
            "Top up your AI wallet to use the URL import.",
        )
    # ── Page-grounding verification (P0 trust contract): every NUMERIC value
    # must be traceable to an explicit number on the page (Lakh/Crore/range
    # aware). Unverifiable numerics are BLANKED + reported; verified values get
    # a provenance quote ("Rs. 5.84 - 9.99 Lakh · Avg. Ex-Showroom price"). ──
    if detail:
        if prog:
            await prog(80, "Verifying every value against the page text…")
        ver = verify_detail(detail, page_text(rendered or html, limit=200000))
        detail["verification"] = {k: ver[k] for k in
                                  ("verified", "blanked", "flagged_text",
                                   "unverified", "has_currency")}
        if tel is not None:
            tel["evidence"] = ver["evidence"]
            tel["verification"] = detail["verification"]
    return detail


@router.post("/decision/{decision_id}/import")
async def import_url_into_decision(
    decision_id: str, req: ImportRequest, request: Request,
    user: dict = Depends(get_current_user),
):
    """Step-2 "Import from URL" — telemetry-wrapped entry. EVERY run (success
    or error) is recorded to `url_import_runs` + PostHog for Import-Analytics."""
    tel = url_telemetry.new_tel(user["user_id"], endpoint="import", url=req.url,
                                ai_tier=_tier(req.ai_tier), hints=_hints_of(req),
                                decision_id=decision_id)
    prog = _progress_writer(req.progress_id, user["user_id"])
    try:
        resp = await _import_inner(decision_id, req, request, user, tel, prog)
    except ai_wallet.InsufficientCredits as e:
        msg = (f"You're out of AI credits (balance {round(e.balance, 2)}) — "
               "top up your wallet to fetch & import this page.")
        await prog(100, msg[:200], status="error")
        await url_telemetry.record_run(tel, status="error", error=msg)
        raise HTTPException(402, msg)
    except HTTPException as e:
        await prog(100, str(e.detail)[:200], status="error")
        await url_telemetry.record_run(tel, status="error", error=f"HTTP {e.status_code}: {e.detail}")
        raise
    except Exception as e:  # noqa: BLE001
        await prog(100, "Import failed — see the error message.", status="error")
        await url_telemetry.record_run(tel, status="error", error=f"{type(e).__name__}: {str(e)[:300]}")
        raise
    await prog(100, "Done — factors & options added.", status="done")
    final_status, partial_reason = await _quality_status(resp)
    if partial_reason:
        tel["partial_reason"] = partial_reason
    resp["run_id"] = await url_telemetry.record_run(
        tel, status=final_status, response=resp,
        error=partial_reason if final_status == "partial" else None)
    if final_status == "partial":
        resp["partial_reason"] = partial_reason
    return resp


async def _import_inner(decision_id: str, req: ImportRequest, request: Request,
                        user: dict, tel: Dict[str, Any], prog) -> Dict[str, Any]:
    """Crawl a comparison page and MERGE the derived factors (with suggested
    Expected values) + options (with assessment %) into an EXISTING MyDezider
    decision, behind the same consent gate."""
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

    # ── Fetch ONCE; run all parse strategies against the same response. ──
    tier = _tier(req.ai_tier)
    hints = _hints_of(req)
    await prog(12, "Fetching the page…")
    r = await fetch_page(req.url, user_id=user["user_id"])
    is_json = "json" in r.headers.get("content-type", "")

    # ── LLM page-type classification (always-on): selects the specialised
    # extraction prompt AND powers per-page-type accuracy analytics. Started
    # as a BACKGROUND task so it overlaps the deterministic parsing below
    # (and, on the AI path, the rendered-HTML fetch) instead of blocking. ──
    cls_task: Optional[asyncio.Task] = None
    if not is_json:
        cls_task = asyncio.create_task(
            classify_page_type(user["user_id"], r.text, req.url))

    async def _page_type() -> Optional[str]:
        """Await the classification (never raises) and fill telemetry once."""
        if cls_task is None:
            return None
        cls = await cls_task
        if "page_type" not in tel:
            tel["page_type"] = cls["page_type"]
            tel["page_type_confidence"] = cls["confidence"]
            tel["classifier_provider"] = cls["provider"]
        return cls["page_type"]

    await prog(22, "Analysing the page structure…")

    # ── Prefer a FULL two-level merge when the page is a category-grouped
    # comparison matrix (e.g. GSMArena: 15 categories × sub-specs) — but ONLY
    # when it does not contradict the user's accuracy hints. ──
    hierarchy = None if is_json else parse_hierarchy(r.text)
    if (hierarchy and len(hierarchy.get("groups", [])) >= 2
            and len(hierarchy.get("items", [])) >= 2
            and not deterministic_hint_issues(hints, hierarchy=hierarchy)):
        items, groups = hierarchy["items"], hierarchy["groups"]
        await prog(45, "Scoring the comparison rows…")
        row_scores, row_meta, text_rows = _score_hierarchy_numeric(items, groups)
        row_scores.update(await _ai_score_text_rows(user["user_id"], items, text_rows))
        await prog(85, "Merging factors & options into your decision…")
        counts = await merge_hierarchical_into_mydezider(
            user["user_id"], decision_id, items=items, groups=groups,
            row_scores=row_scores, row_meta=row_meta)
        tel["route"] = "deterministic_hier"
        await _page_type()
        return {
            "decision_id": decision_id, "consent_id": consent_id, "mode": "hierarchical",
            "item_count": len(items),
            "category_count": counts["category_count"],
            "factor_count": counts["subfactor_count"],
            "factors_added": counts["factors_added"], "options_added": counts["options_added"],
        }

    # ── Flat comparison table / matrix / product grid (deterministic).
    # HINTS ARE LAW: when the user supplied accuracy hints, a deterministic
    # parse is only trusted if it MATCHES them — otherwise we escalate to the
    # hint-guided AI extraction below (keeping this parse as a last-resort
    # fallback). Quality floor: a deterministic parse that gathered fewer than
    # the admin-tunable minimum factors (default 4) is treated as thin on ANY
    # tier — the carwale "best Electric cars under 10 lakh" regression came in
    # as 2 factors (Name + Price) and was silently stamped success on the fast
    # tier. Escalation now applies symmetrically. ──
    det_fallback = None
    qf = await engine_recos.get_quality_floor()
    candidates = await candidates_from_response(r, user["user_id"], allow_ai=False)
    if len(candidates) >= 2:
        factors, scored = _derive_factors_and_scores(candidates, req.max_factors)
        if factors:
            det_issues = deterministic_hint_issues(hints, factors=factors, candidates=scored)
            det_thin = len(factors) < qf
            if not det_issues and not det_thin:
                await prog(85, "Merging factors & options into your decision…")
                counts = await merge_into_mydezider(user["user_id"], decision_id,
                                                    factors=factors, candidates=scored)
                tel["route"] = "deterministic_flat"
                await _page_type()
                return {
                    "decision_id": decision_id, "consent_id": consent_id, "mode": "flat",
                    "item_count": len(candidates),
                    "factors_added": counts["factors_added"], "options_added": counts["options_added"],
                }
            det_fallback = (factors, scored, det_issues)

    # ── AI-guided extraction (detail OR comparison/listing pages): every spec/
    # facet becomes a factor (grouped → parent + sub-factors with equal weight
    # split) with a smart operator + Expected value; the listed items become
    # options. User hints are injected as ground truth + verified with one
    # corrective retry. Rendered-HTML fetch runs CONCURRENTLY with the page-
    # type classification to shave seconds off the slow path. ──
    if not is_json:
        await prog(50, "Fetching the fully-rendered page…")
        rendered_task = asyncio.create_task(fetch_rendered(req.url, user_id=user["user_id"]))
        page_type = await _page_type()
        detail = await _extract_detail_for_url(user["user_id"], req.url, r.text, tier,
                                               hints=hints, page_type=page_type, tel=tel,
                                               rendered_task=rendered_task, prog=prog)
        # If the deterministic parse was actually CLOSER to the user's hints
        # than the AI output, prefer the deterministic one.
        if (detail and det_fallback
                and len(detail.get("hint_warnings") or []) > len(det_fallback[2])):
            detail = None
        if detail:
            tel["route"] = "ai_extraction"
            ver = detail.get("verification") or {}
            ver_fields = {"verification": ver, "geo_note": bool(ver.get("has_currency"))}
            await prog(88, "Merging factors & options into your decision…")
            if detail["kind"] == "hier":
                counts = await merge_hierarchical_into_mydezider(
                    user["user_id"], decision_id,
                    items=detail["items"], groups=detail["groups"],
                    row_scores=detail["row_scores"], row_meta=detail["row_meta"])
                return {
                    "decision_id": decision_id, "consent_id": consent_id, "mode": "detail",
                    "structure": "hierarchical",
                    "main_item": detail["main_name"],
                    "ai_provider": detail.get("provider") or "",
                    "hint_warnings": detail.get("hint_warnings") or [],
                    "item_count": len(detail["items"]),
                    "category_count": counts["category_count"],
                    "factor_count": counts["subfactor_count"],
                    "factors_added": counts["factors_added"],
                    "options_added": counts["options_added"],
                    **ver_fields,
                }
            counts = await merge_into_mydezider(
                user["user_id"], decision_id,
                factors=detail["factors"], candidates=detail["candidates"])
            return {
                "decision_id": decision_id, "consent_id": consent_id, "mode": "detail",
                "structure": "flat",
                "main_item": detail["main_name"],
                "ai_provider": detail.get("provider") or "",
                "hint_warnings": detail.get("hint_warnings") or [],
                "item_count": len(detail["candidates"]),
                "factors_added": counts["factors_added"], "options_added": counts["options_added"],
                **ver_fields,
            }

    # ── AI couldn't produce a hint-conformant structure — fall back to the
    # deterministic parse (with explicit accuracy warnings) rather than fail. ──
    if det_fallback:
        factors, scored, det_issues = det_fallback
        await prog(85, "Merging factors & options into your decision…")
        counts = await merge_into_mydezider(user["user_id"], decision_id,
                                            factors=factors, candidates=scored)
        tel["route"] = "deterministic_fallback"
        await _page_type()
        return {
            "decision_id": decision_id, "consent_id": consent_id, "mode": "flat",
            "item_count": len(scored), "hint_warnings": det_issues,
            "factors_added": counts["factors_added"], "options_added": counts["options_added"],
        }

    # ── LLM flat fallback for table-less / irregular comparison pages ──
    if len(candidates) < 2:
        candidates = await candidates_from_response(r, user["user_id"], allow_ai=True)
    if len(candidates) < 2:
        raise HTTPException(422, "Need at least 2 comparable items on the page to import.")
    factors, scored = _derive_factors_and_scores(candidates, req.max_factors)
    if not factors:
        raise HTTPException(422, "Could not derive comparable factors from the page.")

    await prog(85, "Merging factors & options into your decision…")
    counts = await merge_into_mydezider(user["user_id"], decision_id, factors=factors, candidates=scored)
    tel["route"] = "llm_flat_fallback"
    await _page_type()
    return {
        "decision_id": decision_id, "consent_id": consent_id, "mode": "flat",
        "item_count": len(candidates),
        "factors_added": counts["factors_added"], "options_added": counts["options_added"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# "Set Expectations - By AI" (Step 2 button): one metered LLM call proposes an
# Expected value + direction operator for EVERY leaf factor/sub-factor based on
# the decision context AND the ACTUAL values already on the options (Step 7).
# Gated: factors (Step 2) + options (Step 6) + ≥1 option value (Step 7) must
# exist. The user can override every value afterwards — this only pre-fills.
# ─────────────────────────────────────────────────────────────────────────────
class SetExpectationsRequest(BaseModel):
    ai_tier: str = "precise"        # Claude-first by default; falls back gracefully


EXPECTATIONS_SYSTEM = """You set decision EXPECTATIONS. Given a decision (title/context), its factors (each with an index id, data format, nature, unit) and the ACTUAL values each option holds, propose for EVERY factor the Expected value + operator a sensible decision-maker would set in this context.

RULES
1. operator conveys DIRECTION of satisfaction:
   • "<=" lower-is-better numerics (price, rent, fees, distance, weight) — inversely proportional
   • ">=" higher-is-better numerics (area, scores, ratings, battery, warranty) — directly proportional
   • "=" numeric identity (bedroom count)
   • "equals" for text-format factors (categories, yes/no, names)
2. expected_value must be REALISTIC versus the actual option values supplied: anchor near the best actual value (e.g. cheapest rent seen → "<=" that rent; largest area seen → ">=" that area). For text factors pick the most desirable actual value in context. Plain numbers only (no currency symbols/commas); keep units out of the value.
3. QUALITATIVE factors (Comfort, Luxury Feel …) still get an expectation — phrase a concise desirable level (e.g. "High", "Premium feel") with operator "equals".
4. Cover EVERY factor id given. Do not invent new factors.
Reply ONLY compact JSON: {"expectations":[{"id":"F1","operator":"<=","expected_value":"18000"}]}"""


@router.post("/decision/{decision_id}/set-expectations")
async def set_expectations_by_ai(decision_id: str, req: SetExpectationsRequest,
                                 user: dict = Depends(get_current_user)):
    decision = await db.decisions.find_one(
        {"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(404, "Decision not found")
    factors = decision.get("factors") or []
    options = decision.get("options") or []

    parent_ids = {f.get("parent_id") for f in factors if f.get("parent_id")}
    leaves = [f for f in factors if f["id"] not in parent_ids]
    if not leaves:
        raise HTTPException(422, "No factors yet — import or add factors in Step 2 first.")
    if not options:
        raise HTTPException(422, "No options yet — import or add options (Step 6) first.")
    has_values = any((a.get("unit_value") not in (None, ""))
                     for o in options for a in (o.get("assessments") or []))
    if not has_values:
        raise HTTPException(
            422, "No factor values found on the options yet (Step 7). "
                 "Import from a URL or fill option values first.")

    parent_name = {f["id"]: f.get("name") for f in factors}
    fid_by_key: Dict[str, str] = {}
    lines: List[str] = []
    for i, f in enumerate(leaves):
        key = f"F{i + 1}"
        fid_by_key[key] = f["id"]
        label = f.get("name") or ""
        if f.get("parent_id"):
            label = f"{parent_name.get(f['parent_id'], '')} > {label}"
        vals = []
        for o in options[:10]:
            a = next((a for a in (o.get("assessments") or [])
                      if a.get("factor_id") == f["id"]), None)
            v = (a or {}).get("unit_value")
            if v not in (None, ""):
                vals.append(f"{str(o.get('name') or '')[:40]}={v}")
        lines.append(
            f"{key} | {label} | format={f.get('data_type') or 'numeric'} | "
            f"nature={f.get('factor_type') or 'quantitative'} | unit={f.get('unit') or '-'} | "
            f"current_expected={f.get('expected_value') if f.get('expected_value') not in (None, '') else '-'} | "
            f"actuals: {'; '.join(vals) if vals else '(none)'}")

    prompt = (f"DECISION: {decision.get('title') or ''}\n"
              f"CONTEXT: {(decision.get('context') or '')[:500]}\n"
              f"OPTIONS: {[str(o.get('name') or '')[:50] for o in options[:10]]}\n"
              "FACTORS:\n" + "\n".join(lines))

    tier = "precise" if (req.ai_tier or "").strip().lower() != "fast" else "fast"
    meta: Dict[str, Any] = {}
    try:
        out = await metered_chat(user["user_id"], system_message=EXPECTATIONS_SYSTEM,
                                 prompt=prompt[:14000], feature="ai_set_expectations",
                                 session_prefix="aiexpect", tier=tier, meta=meta)
    except ai_wallet.InsufficientCredits as e:
        raise HTTPException(402, f"You're out of AI credits (balance {round(e.balance, 2)}). "
                                 "Top up your AI wallet to use AI expectations.")
    except Exception:
        raise HTTPException(503, "AI is temporarily unavailable — try again shortly.")

    m = re.search(r"\{.*\}", out or "", re.S)
    try:
        data = json.loads(m.group(0)) if m else {}
    except Exception:
        data = {}
    rows = data.get("expectations") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise HTTPException(502, "AI returned an unusable response — try again.")

    num_ops = {"<=", ">=", "=", "<", ">", "!="}
    txt_ops = {"contains", "starts_with", "ends_with", "equals", "not_equals"}
    by_id = {f["id"]: f for f in factors}
    updated = 0
    changed = 0      # value/operator actually differs from what was there before
    confirmed = 0    # AI agreed with the pre-suggested expectation (e.g. from import)
    for row in rows:
        if not isinstance(row, dict):
            continue
        fid = fid_by_key.get(str(row.get("id") or "").strip())
        f = by_id.get(fid)
        if not f:
            continue
        ev = row.get("expected_value")
        ev = str(ev).strip() if ev not in (None, "") else None
        op = str(row.get("operator") or "").strip()
        ok_ops = num_ops if (f.get("data_type") or "numeric") == "numeric" else txt_ops
        if op not in ok_ops:
            op = ">=" if (f.get("data_type") or "numeric") == "numeric" else "equals"
        if ev is None:
            continue
        prev_ev = str(f.get("expected_value")).strip() if f.get("expected_value") not in (None, "") else None
        prev_op = (f.get("operator") or "").strip()
        if prev_ev == ev and prev_op == op:
            confirmed += 1
        else:
            changed += 1
        f["expected_value"] = ev
        f["operator"] = op
        updated += 1

    if updated:
        await db.decisions.update_one(
            {"id": decision_id, "user_id": user["user_id"]},
            {"$set": {"factors": factors, "updated_at": datetime.now(timezone.utc)}})
    return {"updated": updated, "changed": changed, "confirmed": confirmed,
            "factor_count": len(leaves),
            "ai_provider": meta.get("provider") or ""}


# ── Import accuracy feedback (👍/👎) — labels telemetry runs for the admin
# Import-Analytics learning loop. Owner-only, idempotent (last vote wins). ──
class ImportFeedbackRequest(BaseModel):
    verdict: str  # "up" | "down"


@router.post("/runs/{run_id}/feedback")
async def import_run_feedback(run_id: str, req: ImportFeedbackRequest,
                              user: dict = Depends(get_current_user)):
    verdict = (req.verdict or "").strip().lower()
    if verdict not in ("up", "down"):
        raise HTTPException(400, "verdict must be 'up' or 'down'.")
    found = await url_telemetry.set_feedback(run_id, user["user_id"], verdict)
    if not found:
        raise HTTPException(404, "Import run not found")
    return {"run_id": run_id, "verdict": verdict}
