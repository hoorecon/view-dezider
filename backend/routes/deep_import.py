"""Deep Import (multi-page crawl) — OPT-IN Step-2 import mode.

Flow (factor-first, per product spec):
  1. POST /deep-import/decision/{id}/start  {base_url, context, max_pages, consent}
     → background task: fetch base page → AI picks the option/detail sub-page
       links (guided by the user's 1-2 line context) → crawls each page
       (rendered) → ONE consolidation AI call extracts a unified factor set +
       per-option values → status=factors_ready.
  2. User reviews/edits/prioritises factors in the UI (include, weight).
  3. POST /deep-import/jobs/{job_id}/finalize {factors:[…]} → merges ONLY the
     approved factors + options into the decision (no extra AI cost — values
     were captured in step 1), runs the P0 page-grounding verification, and
     records a telemetry run (provenance quotes available like normal imports).

Cost: 2 LLM calls + N rendered fetches per job (bounded by max_pages ≤ 8) —
which is why this is an explicit mode, not the default import.
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Request

from core.database import db
from core.auth import get_current_user
from core import ai_wallet
from core.url_crawl import fetch_page, fetch_rendered, page_text, metered_chat, has_any_llm
from core.import_verify import verify_detail
from core.decision_builder import merge_into_mydezider
from core import url_telemetry
from core import url_prompt_tuning

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/deep-import", tags=["deep-import"])

ELIGIBILITY_TYPES = {"own", "partner", "free_public", "custom"}
DISCLAIMER_VERSION = "2026-06-08.v1"
MAX_PAGES_CAP = 8
PAGE_TEXT_LIMIT = 12000          # stored per crawled option page
CONSOLIDATE_TEXT_LIMIT = 6000    # per-option text inside the consolidation prompt


def _now():
    return datetime.now(timezone.utc)


class DeepImportStart(BaseModel):
    base_url: str
    context: str = Field(min_length=3, max_length=400)
    max_pages: int = Field(default=5, ge=2, le=MAX_PAGES_CAP)
    ai_tier: str = "precise"
    eligibility_type: str
    custom_note: Optional[str] = None
    accepted: bool = False


class FinalizeFactor(BaseModel):
    name: str
    include: bool = True
    weight: int = Field(default=50, ge=1, le=100)
    operator: Optional[str] = None
    expected_value: Optional[str] = None
    unit: Optional[str] = None


class DeepImportFinalize(BaseModel):
    factors: List[FinalizeFactor]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
_A_RE = re.compile(r'<a\s[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def _extract_links(html: str, base_url: str, cap: int = 600) -> List[Dict[str, str]]:
    """Same-domain anchors with human-readable text — candidates for option pages."""
    host = urlparse(base_url).netloc.replace("www.", "")
    seen, out = set(), []
    for m in _A_RE.finditer(html or ""):
        href = urljoin(base_url, m.group(1).strip())
        text = " ".join(_TAG_RE.sub(" ", m.group(2)).split())[:120]
        p = urlparse(href)
        if p.scheme not in ("http", "https"):
            continue
        if p.netloc.replace("www.", "") != host:
            continue
        if len(text) < 3 or href in seen:
            continue
        seen.add(href)
        out.append({"url": href, "text": text})
        if len(out) >= cap:
            break
    return out


_RANK_STOP = {"the", "for", "and", "best", "good", "choose", "with", "near",
              "area", "new", "top", "buy", "get", "find", "from", "want"}


def _rank_links(links: List[Dict[str, str]], context: str, cap: int = 150) -> List[Dict[str, str]]:
    """Order links by decision-context keyword overlap (text + url) so that on
    link-heavy portals (1000+ anchors) the relevant ones survive the prompt cap
    instead of whatever happened to appear first in the HTML."""
    toks = {t for t in re.findall(r"[a-z0-9]+", (context or "").lower())
            if len(t) >= 3 and t not in _RANK_STOP}
    if not toks:
        return links[:cap]

    def score(l: Dict[str, str]) -> int:
        hay = (l["text"] + " " + l["url"]).lower()
        return sum(1 for t in toks if t in hay)

    ranked = sorted(enumerate(links), key=lambda p: (-score(p[1]), p[0]))
    return [l for _, l in ranked[:cap]]


async def _page_links(url: str, user_id: str):
    """Fetch `url` and return (html, links). Direct fetch first; only falls back
    to a rendered (ScraperAPI-metered) fetch when the direct HTML is link-thin —
    saves the user's scrape credits on server-rendered portals."""
    r = await fetch_page(url, user_id=user_id)
    html = r.text
    links = _extract_links(html, url)
    if len(links) < 10:
        rendered = await fetch_rendered(url, user_id=user_id)
        if rendered:
            rlinks = _extract_links(rendered, url)
            if len(rlinks) > len(links):
                html, links = rendered, rlinks
    return html, links


def _parse_json(out: str) -> Optional[dict]:
    import json
    m = re.search(r"\{.*\}", out or "", re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else None
    except Exception:  # noqa: BLE001
        return None


LINKS_SYSTEM = """You select the OPTION/DETAIL sub-pages a decision-maker should crawl from a website's listing/base page.
Given the user's decision context, the base page text and a numbered list of same-domain links, reply ONLY compact JSON:
{"options":[{"name":"<short display name of the option>","url":"<absolute link url>"}]}
Rules: pick at most {max_pages} links. A valid option link leads to the DETAIL page of exactly ONE specific item (one property, one product, one plan) relevant to the user's context — typically a link whose text/url names a single concrete item.
STRICTLY EXCLUDE: listing/category/search/hub pages that list MANY items (e.g. "Flats for rent in <city>", "Properties in <area>"), navigation, login, ads, news, help and policy links.
Prefer the items most relevant to the context. If the page only links to listing/hub pages and no single-item detail pages qualify, reply {"options":[]}."""

HUBS_SYSTEM = """You locate LISTING/SEARCH hub pages on a website — pages that themselves list many option/detail pages relevant to a user's decision context. This is used when the given base page is a homepage/portal with no direct option links.
Given the decision context, the base page text and a numbered list of same-domain links, reply ONLY compact JSON:
{"hubs":["<absolute url>", ...]}
Rules: return at most 3 urls, ordered most → least relevant to the context.
1. STRONGLY prefer urls picked from the provided LINKS list — choose the most SPECIFIC listing page matching the context (right city/locality/category/budget filter).
2. Only if no listed link matches, you MAY construct ONE url by swapping the locality/category segment of a similar listed link's pattern. Constructed urls must stay on the same domain.
3. EXCLUDE login, help, news, blog, policy and generic navigation pages. If nothing plausible exists, reply {"hubs":[]}."""

CONSOLIDATE_SYSTEM = """You consolidate factors for a decision comparison from MULTIPLE crawled option pages.
Given the user's decision context and one text block per option page, reply ONLY compact JSON:
{"factors":[{"name":str,"group":str,"data_type":"numeric"|"text","unit":str|null,"operator":"<="|">="|"="|"equals","expected_value":str|null,
             "values":{"<option name>":str|null}}]}
Rules:
1. FACTORS = the attributes that meaningfully differentiate the options for THIS decision context (prices, fees, sizes, capacities, ratings, key categorical specs). Max 25, ordered most → least decision-relevant. Group related factors with a short "group" label (Costs, Specs, Location, …).
2. GROUNDING — numeric values MUST come from an explicit number in that option's PAGE TEXT (unit conversion allowed: "Rs. 5.84 Lakh" → 584000; for ranges use the minimum for <= factors, maximum for >= factors). If a page does not state a value, use null — NEVER estimate from memory.
3. values keys MUST exactly match the given option names. expected_value = the most desirable value across options (cleaned plain number for numerics; units only in "unit").
4. operator: "<=" lower-is-better, ">=" higher-is-better, "=" numeric identity, "equals" for text."""


def _score_candidates(factors: List[Dict[str, Any]], candidates: List[Dict[str, Any]]):
    """Deterministic direction-aware 0-100 scores for numeric factors."""
    def _f(v):
        try:
            return float(re.sub(r"[^\d.\-]", "", str(v)))
        except (TypeError, ValueError):
            return None
    for f in factors:
        name = f["name"]
        if f.get("data_type") != "numeric":
            continue
        vals = [(_f((c.get("unit_values") or {}).get(name)), c) for c in candidates]
        nums = [v for v, _ in vals if v is not None and v > 0]
        if not nums:
            continue
        op = f.get("operator") or ">="
        best = min(nums) if op == "<=" else max(nums)
        for v, c in vals:
            if v is None or v <= 0:
                continue
            pct = (best / v if op == "<=" else v / best) * 100.0
            c.setdefault("scores", {})[name] = int(max(0, min(100, round(pct))))


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — discovery (background task)
# ─────────────────────────────────────────────────────────────────────────────
async def _pick_detail_links(user_id: str, context: str, max_pages: int,
                             text: str, links: List[Dict[str, str]],
                             tel: Optional[Dict[str, Any]] = None,
                             stage: str = "links_pick") -> List[Dict[str, str]]:
    """One metered AI call: pick the option/detail page links for the context.
    Traced onto the run (stage prompt + engine + credits) when `tel` is given."""
    link_block = "\n".join(f"{i + 1}. [{l['text']}] {l['url']}" for i, l in enumerate(links))
    sys_msg = (LINKS_SYSTEM.replace("{max_pages}", str(max_pages))
               + await url_prompt_tuning.get_guidance("deep_links"))
    prompt = (f"DECISION CONTEXT: {context}\n\nBASE PAGE TEXT:\n{text}\n\n"
              f"LINKS:\n{link_block}")
    meta: Dict[str, Any] = {}
    started = _now()
    out = await metered_chat(
        user_id, system_message=sys_msg, prompt=prompt,
        feature="deep_import_links", session_prefix="deeplinks", tier="fast", meta=meta)
    if tel is not None:
        url_telemetry.add_ai_call(tel, stage=stage, system_prompt=sys_msg,
                                  prompt_text=prompt, raw_response=out,
                                  meta=meta, started=started)
    data = _parse_json(out) or {}
    seen, options = set(), []
    for o in data.get("options") or []:
        if not isinstance(o, dict) or not o.get("url") or not o.get("name"):
            continue
        url = str(o["url"]).strip()
        if url in seen:
            continue
        seen.add(url)
        options.append({"name": str(o["name"]).strip()[:120], "url": url})
        if len(options) >= max_pages:
            break
    return options


async def _pick_hubs(user_id: str, context: str, base_url: str,
                     text: str, links: List[Dict[str, str]],
                     tel: Optional[Dict[str, Any]] = None) -> List[str]:
    """One metered AI call: locate same-domain LISTING hub pages for the context
    (used when the base page is a portal/homepage with no direct detail links)."""
    link_block = "\n".join(f"{i + 1}. [{l['text']}] {l['url']}" for i, l in enumerate(links))
    sys_msg = HUBS_SYSTEM + await url_prompt_tuning.get_guidance("deep_hubs")
    prompt = (f"DECISION CONTEXT: {context}\n\nBASE PAGE TEXT:\n{text}\n\n"
              f"LINKS:\n{link_block}")
    meta: Dict[str, Any] = {}
    started = _now()
    out = await metered_chat(
        user_id, system_message=sys_msg, prompt=prompt,
        feature="deep_import_hubs", session_prefix="deephubs", tier="fast", meta=meta)
    if tel is not None:
        url_telemetry.add_ai_call(tel, stage="hubs_pick", system_prompt=sys_msg,
                                  prompt_text=prompt, raw_response=out,
                                  meta=meta, started=started)
    data = _parse_json(out) or {}
    host = urlparse(base_url).netloc.replace("www.", "")
    hubs: List[str] = []
    for h in (data.get("hubs") or [])[:3]:
        raw = (h.get("url") if isinstance(h, dict) else h) or ""
        u = urljoin(base_url, str(raw).strip())
        p = urlparse(u)
        if (p.scheme in ("http", "https") and p.netloc.replace("www.", "") == host
                and u.rstrip("/") != base_url.rstrip("/") and u not in hubs):
            hubs.append(u)
    return hubs


async def _set_job(job_id: str, **fields):
    fields["updated_at"] = _now()
    await db.deep_import_jobs.update_one({"id": job_id}, {"$set": fields})


async def _prog(job_id: str, pct: int, label: str):
    await _set_job(job_id, progress={"pct": pct, "label": label})


async def _fail(job_id: str, tel: Dict[str, Any], error: str):
    """Surface a discovery failure on the job AND record it as a telemetry run
    so Admin → Import Analytics sees deep-import failures (+ failure alert)."""
    await _set_job(job_id, status="error", error=error)
    await url_telemetry.record_run(tel, status="error", error=error)


async def _discover(job_id: str, user_id: str, base_url: str, context: str,
                    max_pages: int, tier: str, tel: Dict[str, Any]):
    try:
        await _prog(job_id, 8, "Fetching the base page…")
        html, links = await _page_links(base_url, user_id)
        base_text = page_text(html, limit=8000)
        if not links:
            await _fail(job_id, tel,
                        "No crawlable same-site links found on the base page.")
            return

        await _prog(job_id, 18, "AI is identifying the option pages…")
        options = await _pick_detail_links(user_id, context, max_pages, base_text,
                                           _rank_links(links, context), tel=tel)

        if not options:
            # Hop 2 — the base page is a homepage/portal that links to LISTING
            # hub pages rather than option detail pages (e.g. nobroker.in/).
            # Locate the listing page(s) for the context and pick details there.
            await _prog(job_id, 24,
                        "Base page has no option pages — locating a listing page for your context…")
            hubs = await _pick_hubs(user_id, context, base_url, base_text,
                                    _rank_links(links, context), tel=tel)
            for hi, hub in enumerate(hubs):
                await _prog(job_id, 26 + hi * 4,
                            f"Scanning listing page {hi + 1}/{len(hubs)} for option pages…")
                try:
                    hub_html, hub_links = await _page_links(hub, user_id)
                except ai_wallet.InsufficientCredits:
                    raise
                except Exception as e:  # noqa: BLE001 — a constructed hub may 404/410
                    logger.warning("deep-import hub fetch failed %s: %s", hub[:90], str(e)[:120])
                    continue
                if not hub_links:
                    continue
                options = await _pick_detail_links(
                    user_id, context, max_pages, page_text(hub_html, limit=8000),
                    _rank_links(hub_links, context), tel=tel,
                    stage=f"links_pick@hub{hi + 1}")
                if len(options) >= 2:
                    break
                options = []
        if not options:
            await _fail(job_id, tel,
                        "Could not find option detail pages from this URL — paste the "
                        "LISTING/SEARCH-results page that shows the items you want to compare "
                        "(e.g. your filtered search results) as the base URL, or refine the "
                        "context line.")
            return

        page_texts: Dict[str, str] = {}
        step = max(1, int(38 / len(options)))
        for i, opt in enumerate(options):
            await _prog(job_id, 40 + i * step,
                        f"Crawling option {i + 1}/{len(options)} — {opt['name']}…")
            try:
                rhtml = await fetch_rendered(opt["url"], user_id=user_id)
                if not rhtml:
                    rr = await fetch_page(opt["url"], user_id=user_id)
                    rhtml = rr.text
                page_texts[opt["name"]] = page_text(rhtml, limit=PAGE_TEXT_LIMIT)
            except ai_wallet.InsufficientCredits:
                raise
            except Exception as e:  # noqa: BLE001 — skip unreachable pages
                logger.warning("deep-import page fetch failed %s: %s", opt["url"], str(e)[:120])
        page_texts = {k: v for k, v in page_texts.items() if (v or "").strip()}
        if len(page_texts) < 2:
            await _fail(job_id, tel,
                        "Fewer than 2 option pages could be crawled — cannot build a comparison.")
            return

        await _prog(job_id, 80, "AI is consolidating factors across the crawled pages…")
        blocks = "\n\n".join(
            f"=== OPTION: {name} ===\n{txt[:CONSOLIDATE_TEXT_LIMIT]}"
            for name, txt in page_texts.items())
        cons_sys = CONSOLIDATE_SYSTEM + await url_prompt_tuning.get_guidance("deep_consolidate")
        cons_prompt = f"DECISION CONTEXT: {context}\n\n{blocks}"
        meta2: Dict[str, Any] = {}
        started2 = _now()
        out2 = await metered_chat(
            user_id, system_message=cons_sys, prompt=cons_prompt,
            feature="deep_import_consolidate", session_prefix="deepcons", tier=tier,
            meta=meta2)
        url_telemetry.add_ai_call(tel, stage="consolidate", system_prompt=cons_sys,
                                  prompt_text=cons_prompt, raw_response=out2,
                                  meta=meta2, started=started2)
        data2 = _parse_json(out2) or {}
        factors = []
        for f in (data2.get("factors") or [])[:25]:
            if not isinstance(f, dict) or not str(f.get("name") or "").strip():
                continue
            vals = f.get("values") if isinstance(f.get("values"), dict) else {}
            coverage = sum(1 for n in page_texts if vals.get(n) not in (None, ""))
            factors.append({
                "name": str(f["name"]).strip()[:120],
                "group": str(f.get("group") or "General").strip()[:60],
                "data_type": "numeric" if str(f.get("data_type")) == "numeric" else "text",
                "unit": (str(f["unit"]).strip() if f.get("unit") not in (None, "") else None),
                "operator": str(f.get("operator") or "").strip() or None,
                "expected_value": (str(f["expected_value"]).strip()
                                   if f.get("expected_value") not in (None, "") else None),
                "values": {n: (str(vals[n]).strip() if vals.get(n) not in (None, "") else None)
                           for n in page_texts},
                "coverage": coverage,
            })
        if not factors:
            await _fail(job_id, tel,
                        "AI could not consolidate comparable factors from the crawled pages.")
            return

        await _set_job(job_id, status="factors_ready",
                       progress={"pct": 100, "label": "Factors ready for your review."},
                       options=[{"name": n} for n in page_texts],
                       factors=factors, page_texts=page_texts)
        # Discovery SUCCESS run — symmetric with the error runs above (the
        # finalize step records its own run for the actual merge).
        await url_telemetry.record_run(tel, status="success", response={
            "mode": "deep_discovery", "item_count": len(page_texts),
            "factor_count": len(factors)})
    except ai_wallet.InsufficientCredits as e:
        await _fail(job_id, tel,
                    f"Out of AI credits (balance {round(e.balance, 2)}) — top up to use Deep Import.")
    except Exception as e:  # noqa: BLE001 — job must surface, never hang
        logger.exception("deep-import discovery failed")
        await _fail(job_id, tel, f"{type(e).__name__}: {str(e)[:200]}")


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/decision/{decision_id}/start")
async def start_deep_import(decision_id: str, req: DeepImportStart, request: Request,
                            user: dict = Depends(get_current_user)):
    if not req.accepted:
        raise HTTPException(400, "You must accept the data-access disclaimer to continue.")
    elig = (req.eligibility_type or "").strip().lower()
    if elig not in ELIGIBILITY_TYPES:
        raise HTTPException(400, "Select a valid access-eligibility type.")
    if elig == "custom" and not (req.custom_note or "").strip():
        raise HTTPException(400, "Describe your access right in the custom field.")
    if not has_any_llm():
        raise HTTPException(503, "AI is not configured — Deep Import needs the AI engine.")
    decision = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0, "id": 1})
    if not decision:
        raise HTTPException(404, "Decision not found")

    await db.url_access_consents.insert_one({
        "id": uuid.uuid4().hex, "user_id": user["user_id"], "url": req.base_url.strip(),
        "eligibility_type": elig, "custom_note": (req.custom_note or "").strip() or None,
        "disclaimer_version": DISCLAIMER_VERSION, "accepted": True, "target": "deep_import",
        "decision_id": decision_id,
        "ip": (request.client.host if request.client else None),
        "user_agent": request.headers.get("user-agent"), "created_at": _now(),
    })

    job_id = f"dij_{uuid.uuid4().hex[:12]}"
    # Telemetry context for the DISCOVERY phase — failures are recorded as
    # error runs so Admin → Import Analytics sees them (finalize records the
    # merge run separately).
    tel = url_telemetry.new_tel(user["user_id"], endpoint="deep_import",
                                url=req.base_url.strip(), ai_tier=req.ai_tier,
                                hints=None, decision_id=decision_id)
    tel["route"] = "deep_import_discovery"
    await db.deep_import_jobs.insert_one({
        "id": job_id, "user_id": user["user_id"], "decision_id": decision_id,
        "base_url": req.base_url.strip(), "context": req.context.strip(),
        "max_pages": req.max_pages, "ai_tier": req.ai_tier,
        "status": "discovering", "progress": {"pct": 5, "label": "Starting…"},
        "error": None, "created_at": _now(),
        "expires_at": _now() + timedelta(hours=24),
    })
    try:
        await db.deep_import_jobs.create_index("expires_at", expireAfterSeconds=0)
    except Exception:  # noqa: BLE001
        pass
    asyncio.create_task(_discover(job_id, user["user_id"], req.base_url.strip(),
                                  req.context.strip(), req.max_pages,
                                  "precise" if req.ai_tier == "precise" else "fast",
                                  tel))
    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
async def get_deep_import_job(job_id: str, user: dict = Depends(get_current_user)):
    doc = await db.deep_import_jobs.find_one(
        {"id": job_id, "user_id": user["user_id"]},
        {"_id": 0, "page_texts": 0})
    if not doc:
        raise HTTPException(404, "Deep-import job not found")
    return doc


@router.post("/jobs/{job_id}/finalize")
async def finalize_deep_import(job_id: str, req: DeepImportFinalize,
                               user: dict = Depends(get_current_user)):
    """Merge ONLY the user-approved factors (+ all crawled options & their
    captured values) into the decision. Zero extra AI cost. Runs the P0
    page-grounding verification and records a provenance-bearing run."""
    job = await db.deep_import_jobs.find_one({"id": job_id, "user_id": user["user_id"]})
    if not job:
        raise HTTPException(404, "Deep-import job not found")
    if job.get("status") != "factors_ready":
        raise HTTPException(400, f"Job is not ready for finalize (status={job.get('status')}).")

    approved = {f.name.strip().lower(): f for f in req.factors if f.include}
    if not approved:
        raise HTTPException(400, "Select at least one factor to import.")

    num_ops = {"<=", ">=", "=", "<", ">", "!="}
    factors_out: List[Dict[str, Any]] = []
    for jf in job.get("factors") or []:
        edit = approved.get(str(jf["name"]).strip().lower())
        if not edit:
            continue
        dt = jf.get("data_type") or "text"
        op = (edit.operator or jf.get("operator") or "").strip()
        op = op if (op in num_ops if dt == "numeric" else op == "equals") \
            else (">=" if dt == "numeric" else "equals")
        factors_out.append({
            "name": jf["name"], "data_type": dt, "factor_type": "quantitative",
            "operator": op,
            "expected_value": edit.expected_value or jf.get("expected_value"),
            "unit": edit.unit or jf.get("unit"), "weight": edit.weight,
            "_values": jf.get("values") or {},
        })
    if not factors_out:
        raise HTTPException(400, "None of the selected factors matched this job.")

    candidates = []
    for opt in job.get("options") or []:
        name = opt["name"]
        uvals = {f["name"]: f["_values"].get(name)
                 for f in factors_out if f["_values"].get(name) not in (None, "")}
        candidates.append({"name": name, "scores": {}, "unit_values": uvals})
    for f in factors_out:
        f.pop("_values", None)

    # P0 page-grounding verification against ALL crawled page texts
    combined_text = "\n".join((job.get("page_texts") or {}).values())
    detail = {"kind": "flat", "main_name": (candidates[0]["name"] if candidates else ""),
              "factors": factors_out, "candidates": candidates}
    ver = verify_detail(detail, combined_text)
    _score_candidates(factors_out, candidates)

    await _set_job(job_id, status="merging",
                   progress={"pct": 92, "label": "Merging into your decision…"})
    counts = await merge_into_mydezider(user["user_id"], job["decision_id"],
                                        factors=factors_out, candidates=candidates)

    verification = {k: ver[k] for k in ("verified", "blanked", "flagged_text",
                                        "unverified", "has_currency")}
    resp = {
        "decision_id": job["decision_id"], "mode": "deep_import",
        "item_count": len(candidates),
        "factors_added": counts["factors_added"], "options_added": counts["options_added"],
        "verification": verification, "geo_note": bool(ver.get("has_currency")),
    }
    # Telemetry + provenance (reuses the import-runs store → /url-analyze/runs/{id}/provenance)
    tel = url_telemetry.new_tel(user["user_id"], endpoint="deep_import",
                                url=job["base_url"], ai_tier=job.get("ai_tier") or "precise",
                                hints=None, decision_id=job["decision_id"])
    tel["route"] = "deep_import"
    tel["evidence"] = ver["evidence"]
    tel["verification"] = verification
    resp["run_id"] = await url_telemetry.record_run(tel, status="success", response=resp)

    await _set_job(job_id, status="done", result=resp,
                   progress={"pct": 100, "label": "Done — factors & options added."})
    return resp
