"""
Partner Screener / Ranking Engine (P3)
======================================

The monetised differentiator: rank an ENTIRE partner catalogue against a
weighted set of factor criteria (the MyDezider Steps 1-5 logic applied in
bulk) and return the top 10-50 finalists.

Pipeline
--------
  ingest  →  (cache candidates)  →  quote  →  run (score + rank + bill)  →  export

Ingestion sources (admin-gated via decision_embed_config.ingestion):
  • inline     — options handed off from the partner page DOM (P2 bridge)
  • csv        — pasted CSV text
  • sheet_csv  — a Google-Sheet "Publish to web → CSV" URL
  • api        — a partner-exposed JSON catalogue API
  • url        — premium "paste a filtered URL" fetch (JSON or HTML table);
                 gated behind the scrape legal + ToS acknowledgements.

Scoring (P3a): NUMERIC factors only — proportional min-max normalisation per
factor (higher/lower-is-better), weighted average → 0..100, ranked desc.
Qualitative TEXT factors are AI-assessed on the finalists when use_ai=true
(P3b) via the metered wallet.

Billing (dual, admin-configurable): end_user (AI wallet) and/or partner
(wholesale ledger). Pricing = base + per_candidate·N + per_finalist·F +
per_factor·K (from the partner's screener_pricing config).
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field

from core.database import db
from core.auth import get_current_user
from core import ai_wallet
from core.ai_metering import metered_chat, has_any_llm

router = APIRouter(prefix="/embed/screener", tags=["Partner Screener"])

MAX_CANDIDATES = 5000
HTTP_TIMEOUT = 20.0

# Subscription tier ordering for the premium paste-URL gate (free<basic<pro<premium).
TIER_ORDER = {"free": 0, "basic": 1, "pro": 2, "premium": 3}


async def _user_tier_order(user_id: str) -> int:
    """Resolve a user's subscription tier rank from their wallet.current_plan."""
    w = await db.ai_wallets.find_one({"user_id": user_id}, {"_id": 0, "current_plan": 1})
    plan = ((w or {}).get("current_plan") or "free").lower()
    return TIER_ORDER.get(plan, 0)


# ----------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------
class ScreenerFactor(BaseModel):
    id: Optional[str] = None
    name: str
    weight: float = 50.0                 # 0..100 relative weight
    direction: str = "higher"            # higher | lower (is better)
    data_type: str = "numeric"           # numeric | text
    attribute_key: Optional[str] = None  # candidate.attributes key; defaults to name


class Candidate(BaseModel):
    name: str
    attributes: Dict[str, Any] = Field(default_factory=dict)


class IngestRequest(BaseModel):
    partner: str
    mode: str                            # inline | csv | sheet_csv | api | url
    candidates: Optional[List[Candidate]] = None
    csv_text: Optional[str] = None
    url: Optional[str] = None
    name_key: Optional[str] = None       # which column holds the option name
    items_path: Optional[str] = None     # dotted JSON path to the array (api/url-json)


class QuoteRequest(BaseModel):
    partner: str
    candidate_count: int = 0
    finalists: int = 10
    factor_count: int = 1


class RunRequest(BaseModel):
    partner: str
    ingest_id: Optional[str] = None
    candidates: Optional[List[Candidate]] = None
    factors: List[ScreenerFactor]
    finalists: int = 10
    use_ai: bool = False                 # AI-assess text factors on finalists (P3b)
    billing_mode: Optional[str] = None   # override config: end_user | partner | both


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
async def _load_partner(slug: str):
    org = await db.organizations.find_one({"slug": (slug or "").strip().lower()}, {"_id": 0})
    if not org:
        raise HTTPException(404, "Partner not found")
    cfg = await db.decision_embed_config.find_one({"org_id": org["id"]}, {"_id": 0}) or {}
    return org, cfg


_NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def _num(v: Any) -> Optional[float]:
    """Best-effort numeric parse: '44.39%' → 44.39, '₹1,210.5' → 1210.5."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    m = _NUM_RE.search(s.replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _rows_to_candidates(rows: List[Dict[str, Any]], name_key: Optional[str]) -> List[Candidate]:
    out: List[Candidate] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        attrs = {str(k): r[k] for k in r.keys()}
        nk = name_key if (name_key and name_key in attrs) else None
        if not nk:
            for cand_key in ("name", "Name", "title", "Title", "scheme", "Scheme", "fund", "Fund"):
                if cand_key in attrs:
                    nk = cand_key
                    break
        if not nk:
            nk = next(iter(attrs.keys()), None)
        name = str(attrs.get(nk, "")).strip() if nk else ""
        if not name:
            continue
        out.append(Candidate(name=name, attributes=attrs))
        if len(out) >= MAX_CANDIDATES:
            break
    return out


def _json_dig(data: Any, path: Optional[str]) -> Any:
    if not path:
        return data
    cur = data
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _price(pricing: Dict[str, Any], n: int, finalists: int, factor_count: int) -> float:
    p = pricing or {}
    base = float(p.get("base_credits", 1.0))
    per_c = float(p.get("per_candidate", 0.01))
    per_f = float(p.get("per_finalist", 0.1))
    per_k = float(p.get("per_factor", 0.05))
    cost = base + per_c * max(0, n) + per_f * max(0, finalists) + per_k * max(0, factor_count)
    return round(max(base, cost), 2)


def _ensure_factor_ids(factors: List[ScreenerFactor]) -> None:
    for i, f in enumerate(factors):
        if not f.id:
            f.id = f"f_{i}_{uuid.uuid4().hex[:6]}"


def _score(candidates: List[Candidate], factors: List[ScreenerFactor]) -> List[Dict[str, Any]]:
    """Numeric proportional scoring → weighted 0..100, ranked desc."""
    numeric = [f for f in factors if (f.data_type or "numeric") != "text"]
    mins: Dict[str, Optional[float]] = {}
    maxs: Dict[str, Optional[float]] = {}
    parsed: Dict[int, Dict[str, Optional[float]]] = {}

    for f in numeric:
        key = f.attribute_key or f.name
        vals: List[float] = []
        for i, c in enumerate(candidates):
            raw = c.attributes.get(key, c.attributes.get(f.name))
            v = _num(raw)
            parsed.setdefault(i, {})[f.id] = v
            if v is not None:
                vals.append(v)
        mins[f.id] = min(vals) if vals else None
        maxs[f.id] = max(vals) if vals else None

    total_w = sum(max(0.0, f.weight) for f in numeric) or 1.0
    results: List[Dict[str, Any]] = []
    for i, c in enumerate(candidates):
        wsum = 0.0
        fscores = []
        for f in numeric:
            v = parsed.get(i, {}).get(f.id)
            mn, mx = mins[f.id], maxs[f.id]
            if v is None or mn is None or mx is None:
                pct = None
            elif mx == mn:
                pct = 100.0
            elif (f.direction or "higher") == "lower":
                pct = (mx - v) / (mx - mn) * 100.0
            else:
                pct = (v - mn) / (mx - mn) * 100.0
            fscores.append({"factor_id": f.id, "name": f.name, "value": v,
                            "pct": None if pct is None else round(pct, 1)})
            if pct is not None:
                wsum += pct * max(0.0, f.weight)
        results.append({
            "name": c.name, "attributes": c.attributes,
            "score": round(wsum / total_w, 1), "factor_scores": fscores,
        })
    results.sort(key=lambda r: r["score"], reverse=True)
    for idx, r in enumerate(results):
        r["rank"] = idx + 1
    return results


async def _ai_assess_finalists(user_id: str, finalists: List[Dict[str, Any]],
                               factors: List[ScreenerFactor]) -> None:
    """P3b: AI-score TEXT factors (0..100) for the finalists, metered. Mutates
    the finalists list (adds text factor_scores + blends into the score)."""
    text_factors = [f for f in factors if (f.data_type or "numeric") == "text"]
    if not text_factors or not has_any_llm():
        return
    numeric_w = sum(max(0.0, f.weight) for f in factors if (f.data_type or "numeric") != "text")
    text_w = sum(max(0.0, f.weight) for f in text_factors)
    total_w = (numeric_w + text_w) or 1.0
    sys = ("You are a precise evaluator. Given an option and its attributes, rate it 0-100 "
           "on each requested qualitative factor (100 = best). Reply ONLY compact JSON "
           "mapping factor name → integer score.")
    for r in finalists:
        prompt = (f"Option: {r['name']}\nAttributes: {json.dumps(r.get('attributes', {}))[:800]}\n"
                  f"Factors to rate: {json.dumps([f.name for f in text_factors])}")
        try:
            txt = await metered_chat(user_id, system_message=sys, prompt=prompt,
                                     feature="screener_ai_assess", session_prefix="screener")
            m = re.search(r"\{.*\}", txt, re.S)
            scores = json.loads(m.group(0)) if m else {}
        except Exception:
            scores = {}
        # blend: recompute weighted score with text contributions
        numeric_contrib = 0.0
        for fs in r.get("factor_scores", []):
            if fs.get("pct") is not None:
                wf = next((f for f in factors if f.id == fs["factor_id"]), None)
                if wf:
                    numeric_contrib += fs["pct"] * max(0.0, wf.weight)
        for tf in text_factors:
            val = scores.get(tf.name)
            pct = _num(val)
            pct = max(0.0, min(100.0, pct)) if pct is not None else None
            r.setdefault("factor_scores", []).append(
                {"factor_id": tf.id, "name": tf.name, "value": None,
                 "pct": None if pct is None else round(pct, 1), "ai": True})
            if pct is not None:
                numeric_contrib += pct * max(0.0, tf.weight)
        r["score"] = round(numeric_contrib / total_w, 1)
    finalists.sort(key=lambda x: x["score"], reverse=True)
    for idx, r in enumerate(finalists):
        r["rank"] = idx + 1


# ----------------------------------------------------------------------------
# Ingestion
# ----------------------------------------------------------------------------
async def _ingest_candidates(req: IngestRequest, cfg: Dict[str, Any], user: dict) -> List[Candidate]:
    ing = cfg.get("ingestion") or {}
    mode = (req.mode or "inline").lower()

    if mode == "inline":
        return (req.candidates or [])[:MAX_CANDIDATES]

    if mode == "csv":
        if not ing.get("csv_sheet_enabled", True):
            raise HTTPException(400, "CSV/Sheet ingestion is disabled for this partner.")
        text = req.csv_text or ""
        if not text.strip():
            raise HTTPException(400, "csv_text is empty")
        reader = csv.DictReader(io.StringIO(text))
        return _rows_to_candidates(list(reader), req.name_key)

    if mode == "sheet_csv":
        if not ing.get("csv_sheet_enabled", True):
            raise HTTPException(400, "CSV/Sheet ingestion is disabled for this partner.")
        if not req.url:
            raise HTTPException(400, "url (published CSV) is required")
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as cli:
            r = await cli.get(req.url)
        if r.status_code >= 400:
            raise HTTPException(400, f"Sheet fetch failed ({r.status_code})")
        reader = csv.DictReader(io.StringIO(r.text))
        return _rows_to_candidates(list(reader), req.name_key)

    if mode == "api":
        if not ing.get("api_enabled", False):
            raise HTTPException(400, "Partner API ingestion is disabled for this partner.")
        url = req.url or ing.get("api_endpoint")
        if not url:
            raise HTTPException(400, "No API endpoint configured")
        headers = {}
        if ing.get("api_auth_header"):
            headers[str(ing["api_auth_header"])] = ing.get("api_auth_value", "") or ""
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as cli:
            r = await cli.get(url, headers=headers)
        if r.status_code >= 400:
            raise HTTPException(400, f"API fetch failed ({r.status_code})")
        data = _json_dig(r.json(), req.items_path)
        if not isinstance(data, list):
            raise HTTPException(400, "API did not return a list of items (check items_path)")
        return _rows_to_candidates(data, req.name_key)

    if mode == "url":
        # Premium "paste a filtered URL" — gated behind legal + ToS acks.
        if not (ing.get("scrape_enabled") and ing.get("scrape_legal_ack") and ing.get("scrape_terms_ack")):
            raise HTTPException(
                403,
                "URL fetch requires the admin to enable scraping and confirm the "
                "legal authority + partner-ToS acknowledgements for this partner.",
            )
        # Subscription/tier gate (admin-configured minimum plan).
        min_tier = (ing.get("url_min_tier") or "").strip().lower()
        if min_tier and min_tier in TIER_ORDER:
            user_rank = await _user_tier_order(user["user_id"])
            if user_rank < TIER_ORDER[min_tier]:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "tier_required",
                        "required_tier": min_tier,
                        "message": f"The paste-URL Screener requires the '{min_tier}' plan or higher. Please upgrade.",
                    },
                )
        if not req.url:
            raise HTTPException(400, "url is required")
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True,
                                     headers={"User-Agent": "Mozilla/5.0 (ViewDeziderBot)"}) as cli:
            r = await cli.get(req.url)
        if r.status_code >= 400:
            raise HTTPException(400, f"URL fetch failed ({r.status_code})")
        ctype = r.headers.get("content-type", "")
        if "json" in ctype:
            data = _json_dig(r.json(), req.items_path)
            if isinstance(data, list):
                return _rows_to_candidates(data, req.name_key)
            raise HTTPException(400, "JSON URL did not yield a list (check items_path)")
        # HTML → parse the first reasonable <table> into rows
        rows = _html_table_rows(r.text)
        if rows:
            return _rows_to_candidates(rows, req.name_key)
        # P3b: no clean table → AI extraction fallback (metered to the user)
        ai_rows = await _ai_extract_candidates(user["user_id"], r.text)
        if ai_rows:
            return _rows_to_candidates(ai_rows, req.name_key)
        raise HTTPException(422, "Could not extract a candidate list from the page "
                                 "(no table found and AI extraction unavailable). Try CSV/API.")

    raise HTTPException(400, f"Unknown ingestion mode '{mode}'")


async def _ai_extract_candidates(user_id: str, html: str) -> List[Dict[str, Any]]:
    """Fallback for table-less pages: LLM-extract a candidate list from the page
    text. Metered to the user's wallet. Returns [] if no LLM is configured."""
    if not has_any_llm():
        return []
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = re.sub(r"\n{2,}", "\n", soup.get_text("\n", strip=True))[:6000]
    sys = ("Extract the list of comparable items from this page. Reply ONLY a compact "
           "JSON array of objects: {\"name\": str, \"attributes\": {key: value}} with the "
           "numeric/comparable attributes you can find. No prose, max 50 items.")
    try:
        out = await metered_chat(user_id, system_message=sys, prompt=text,
                                 feature="screener_url_extract", session_prefix="screener")
        m = re.search(r"\[.*\]", out, re.S)
        data = json.loads(m.group(0)) if m else []
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _html_table_rows(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    best: List[Dict[str, Any]] = []
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        body_rows = table.find_all("tr")
        rows: List[Dict[str, Any]] = []
        for tr in body_rows:
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if not cells:
                continue
            if headers and len(headers) == len(cells):
                rows.append({headers[i]: cells[i] for i in range(len(cells))})
            else:
                rows.append({f"col{i}": cells[i] for i in range(len(cells))})
        if len(rows) > len(best):
            best = rows
    return best


# ----------------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------------
@router.post("/ingest")
async def screener_ingest(req: IngestRequest, user: dict = Depends(get_current_user)):
    org, cfg = await _load_partner(req.partner)
    cands = await _ingest_candidates(req, cfg, user)
    if not cands:
        raise HTTPException(422, "No candidates found from the supplied source.")
    ingest_id = uuid.uuid4().hex
    await db.screener_ingests.insert_one({
        "id": ingest_id, "partner_id": org["id"], "user_id": user["user_id"],
        "candidates": [c.model_dump() for c in cands], "count": len(cands),
        "mode": req.mode, "created_at": datetime.now(timezone.utc),
    })
    # detect available attribute keys to help the UI map factors
    keys: List[str] = []
    seen = set()
    for c in cands[:50]:
        for k in c.attributes.keys():
            if k not in seen:
                seen.add(k)
                keys.append(k)
    return {
        "ingest_id": ingest_id, "count": len(cands),
        "attribute_keys": keys,
        "preview": [c.model_dump() for c in cands[:8]],
    }


@router.post("/quote")
async def screener_quote(req: QuoteRequest, user: dict = Depends(get_current_user)):
    org, cfg = await _load_partner(req.partner)
    pricing = cfg.get("screener_pricing") or {}
    cost = _price(pricing, req.candidate_count, req.finalists, req.factor_count)
    bal = await ai_wallet.get_balance(user["user_id"])
    return {
        "cost_credits": cost,
        "billing_mode": pricing.get("billing_mode", "end_user"),
        "breakdown": {
            "base": float(pricing.get("base_credits", 1.0)),
            "per_candidate": float(pricing.get("per_candidate", 0.01)),
            "per_finalist": float(pricing.get("per_finalist", 0.1)),
            "per_factor": float(pricing.get("per_factor", 0.05)),
            "candidate_count": req.candidate_count,
            "finalists": req.finalists,
            "factor_count": req.factor_count,
        },
        "wallet_balance": bal.get("balance", 0),
    }


@router.post("/run")
async def screener_run(req: RunRequest, user: dict = Depends(get_current_user)):
    org, cfg = await _load_partner(req.partner)
    flows = cfg.get("enabled_flows") or []
    if "screener" not in flows:
        raise HTTPException(403, "Screener is not enabled for this partner.")

    # resolve candidates
    candidates: List[Candidate]
    if req.ingest_id:
        doc = await db.screener_ingests.find_one({"id": req.ingest_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "ingest_id not found")
        candidates = [Candidate(**c) for c in doc.get("candidates", [])]
    elif req.candidates:
        candidates = req.candidates[:MAX_CANDIDATES]
    else:
        raise HTTPException(400, "Provide ingest_id or candidates")
    if not candidates:
        raise HTTPException(422, "No candidates to rank")
    if not req.factors:
        raise HTTPException(400, "At least one factor is required")

    _ensure_factor_ids(req.factors)
    finalists_n = max(1, min(int(req.finalists or 10), 50))

    # pricing + billing
    pricing = cfg.get("screener_pricing") or {}
    billing_mode = req.billing_mode or pricing.get("billing_mode", "end_user")
    cost = _price(pricing, len(candidates), finalists_n, len(req.factors))

    charges_user = billing_mode in ("end_user", "both")
    if charges_user:
        bal = await ai_wallet.get_balance(user["user_id"])
        if float(bal.get("balance", 0)) < cost:
            raise HTTPException(
                status_code=402,
                detail={"error": "insufficient_credits", "needed": cost,
                        "balance": bal.get("balance", 0)},
            )

    # score + rank
    ranked = _score(candidates, req.factors)
    finalists = ranked[:finalists_n]

    if req.use_ai:
        await _ai_assess_finalists(user["user_id"], finalists, req.factors)

    run_id = uuid.uuid4().hex
    charged = 0.0
    if charges_user:
        res = await ai_wallet.charge_credits(user["user_id"], cost,
                                             feature="screener_run",
                                             note=f"Screener {org.get('slug')} ({len(candidates)} candidates)")
        charged = res.get("charged", cost)
    if billing_mode in ("partner", "both"):
        await db.partner_billing_ledger.insert_one({
            "id": uuid.uuid4().hex, "partner_id": org["id"], "user_id": user["user_id"],
            "run_id": run_id, "kind": "screener_run", "credits": cost,
            "candidate_count": len(candidates), "finalists": finalists_n,
            "created_at": datetime.now(timezone.utc),
        })

    run_doc = {
        "id": run_id, "partner_id": org["id"], "partner_slug": org.get("slug"),
        "user_id": user["user_id"], "candidate_count": len(candidates),
        "finalists_count": finalists_n, "factors": [f.model_dump() for f in req.factors],
        "results": finalists, "cost_credits": cost, "billing_mode": billing_mode,
        "used_ai": bool(req.use_ai), "created_at": datetime.now(timezone.utc),
    }
    await db.screener_runs.insert_one({k: v for k, v in run_doc.items()})

    bal_after = await ai_wallet.get_balance(user["user_id"])
    return {
        "run_id": run_id, "candidate_count": len(candidates),
        "finalists": finalists, "cost_credits": cost, "charged": charged,
        "billing_mode": billing_mode, "wallet_balance": bal_after.get("balance", 0),
    }


@router.get("/run/{run_id}")
async def screener_get_run(run_id: str, user: dict = Depends(get_current_user)):
    doc = await db.screener_runs.find_one({"id": run_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Run not found")
    if doc.get("user_id") != user["user_id"] and user.get("role") != "admin":
        raise HTTPException(403, "Not allowed")
    return doc


@router.get("/run/{run_id}/export.csv")
async def screener_export(run_id: str, user: dict = Depends(get_current_user)):
    doc = await db.screener_runs.find_one({"id": run_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Run not found")
    if doc.get("user_id") != user["user_id"] and user.get("role") != "admin":
        raise HTTPException(403, "Not allowed")
    results = doc.get("results", [])
    factor_names = [f.get("name") for f in doc.get("factors", [])]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Rank", "Option", "Score", *factor_names])
    for r in results:
        fmap = {fs.get("name"): fs.get("pct") for fs in r.get("factor_scores", [])}
        w.writerow([r.get("rank"), r.get("name"), r.get("score"),
                    *[fmap.get(n, "") for n in factor_names]])
    return Response(
        content=buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="screener_{run_id}.csv"'},
    )
