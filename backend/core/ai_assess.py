"""Shared AI-Assist helpers for My Dezider & Pros & Cons satisfaction scoring.

Single source of truth for the "AI Assess" button in both flows so behaviour
stays in parity. Implements the product rules:

  * Factor-type resolution — Quantitative vs Qualitative/Subjective.
  * Input validation:
      - Quantitative → needs Expected value + Operator + an Actual value
        (Unit optional). The Actual may be supplied by the user OR resolved
        from a Data Source / a linked Solution Store option before failing.
      - Qualitative  → needs an Expected value only. The Actual is optional —
        AI fetches/infers it.
  * Actual-value resolution chain (used to fill gaps):
      1. factor.data_source (webhook / web_surf / ai_llm) — highest priority.
      2. Linked Solution Store option → quantitative factors (Store) and
         qualitative factors (ReviewNet aggregates) for that specific option.
      3. AI guesses the actual from the decision context.
  * LLM satisfaction scoring (0-100) with the enriched context, plus a
    deterministic numeric-ratio fallback when the LLM is unavailable.
"""
from __future__ import annotations

import json as _json
import logging
import os
import re
import uuid
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException

from core.database import db

log = logging.getLogger("ai_assess")


# ─────────────────────────────────────────────────────────────
# Factor-type + validation
# ─────────────────────────────────────────────────────────────
def _has(v: Any) -> bool:
    return v is not None and str(v).strip() != ""


def resolve_factor_type(factor: dict) -> str:
    """Return 'quantitative' or 'qualitative'.

    Both flows store classification slightly differently:
      * Pros & Cons / Step-5 metadata uses data_type: 'numeric'|'text'.
      * My Dezider also carries factor_type: 'subjective'|'objective'
        (and 'quantitative'|'qualitative' in some records).
    data_type wins when present; factor_type is the fallback.
    """
    dt = (factor.get("data_type") or "").lower()
    if dt == "text":
        return "qualitative"
    if dt == "numeric":
        return "quantitative"
    ft = (factor.get("factor_type") or "").lower()
    if ft in ("subjective", "qualitative"):
        return "qualitative"
    if ft in ("objective", "quantitative"):
        return "quantitative"
    return "qualitative"


def validate_expected(factor: dict, ftype: str) -> None:
    """Validate the ALWAYS-required inputs (Expected, plus Operator for
    quantitative). Raises HTTPException(400) with a friendly message.

    The Actual value is validated separately, AFTER the resolution chain,
    so a Data Source / Solution Store value can satisfy it.
    """
    fname = factor.get("display_name") or factor.get("name") or "this factor"
    expected = factor.get("expected_value")
    if ftype == "quantitative":
        missing = []
        if not _has(expected):
            missing.append("an Expected value")
        if not _has(factor.get("operator")):
            missing.append("an Operator (e.g. ≥)")
        if missing:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"AI Assist for the quantitative factor “{fname}” needs "
                    f"{' and '.join(missing)}. Set it in Step 5 (Review & Refine "
                    f"Expectations) and try again."
                ),
            )
    else:
        if not _has(expected):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"AI Assist for the qualitative factor “{fname}” needs an "
                    f"Expected value to assess against. Set it in Step 5 (Review "
                    f"& Refine Expectations) and try again."
                ),
            )


def _missing_actual_error(factor: dict) -> HTTPException:
    fname = factor.get("display_name") or factor.get("name") or "this factor"
    return HTTPException(
        status_code=400,
        detail=(
            f"AI Assist for the quantitative factor “{fname}” needs an Actual "
            f"value. Enter it, set a Data Source for the factor, or link this "
            f"option to a Solution Store item so the value can be fetched."
        ),
    )


# ─────────────────────────────────────────────────────────────
# Actual-value resolution chain
# ─────────────────────────────────────────────────────────────
async def _fetch_from_data_source(
    factor: dict, option_name: str, decision_title: str, decision_context: str, user_id: str
) -> Optional[str]:
    """Fetch a single factor's actual value from its configured data source.
    Mirrors routes/ai_tools.fetch_factor_data but for one factor. Returns a
    scalar string value or None when unavailable/misconfigured.
    """
    ds = factor.get("data_source") or {}
    dtype = ds.get("type")
    config = ds.get("config") or {}
    if not dtype or dtype == "manual":
        return None

    try:
        if dtype == "webhook":
            url = config.get("url", "")
            if not url:
                return None
            headers_str = config.get("headers", "{}")
            try:
                custom_headers = _json.loads(headers_str) if headers_str else {}
            except Exception:
                custom_headers = {}
            payload = {
                "factor_name": factor.get("name", ""),
                "option_name": option_name,
                "decision_title": decision_title,
                "unit": factor.get("unit", ""),
                "expected_value": factor.get("expected_value"),
            }
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client_http:
                resp = await client_http.post(url, json=payload, headers=custom_headers)
                data = resp.json()
                val = data.get("value", data.get("result"))
                return str(val) if val is not None else None

        api_key = os.getenv("EMERGENT_LLM_KEY")
        if not api_key:
            return None
        from core.llm_compat import LlmChat, UserMessage

        if dtype == "web_surf":
            search_query = config.get("search_query") or f"{factor.get('name','')} {option_name} {decision_title}"
            search_query = (
                search_query.replace("{factor}", factor.get("name", ""))
                .replace("{option}", option_name)
                .replace("{title}", decision_title)
            )
            search_results_text = ""
            try:
                from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    ddg_results = list(ddgs.text(search_query, max_results=5))
                for idx, r in enumerate(ddg_results, 1):
                    search_results_text += f"\n{idx}. {r.get('title','')}: {r.get('body','')[:300]}"
            except Exception as se:
                search_results_text = f"(Web search unavailable: {str(se)[:80]})"
            prompt = (
                f"From the web results, extract the current real-world value for "
                f"factor '{factor.get('name','')}' of '{option_name}' "
                f"(unit: {factor.get('unit','N/A')}).\n{search_results_text}\n"
                'Return ONLY JSON: {"value": <value>}'
            )
            sysmsg = "You are a research assistant. Extract factual values. Return only valid JSON."
        else:  # ai_llm
            custom_prompt = config.get("prompt") or f"What is the {factor.get('name','')} for {option_name}?"
            custom_prompt = (
                custom_prompt.replace("{factor}", factor.get("name", ""))
                .replace("{option}", option_name)
                .replace("{title}", decision_title)
            )
            prompt = custom_prompt + '\nReturn ONLY JSON: {"value": <value>}'
            sysmsg = (
                f"You are a decision-support AI. Decision: {decision_title}. "
                f"Context: {decision_context}. Evaluating: {option_name}. Return only valid JSON."
            )

        chat = LlmChat(
            api_key=api_key,
            session_id=f"dsfetch_{user_id}_{uuid.uuid4().hex[:8]}",
            system_message=sysmsg,
        ).with_model("openai", "gpt-4.1-mini")
        resp = await chat.send_message(UserMessage(text=prompt))
        txt = (resp or "").strip()
        if txt.startswith("```"):
            txt = txt.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        data = _json.loads(txt)
        val = data.get("value")
        return str(val) if _has(val) else None
    except Exception as e:  # never break assessment on a data-source error
        log.warning(f"data-source fetch failed ({dtype}): {e}")
        return None


async def gather_solution_factor_data(solution_id: str) -> Optional[dict]:
    """Aggregate a linked Solution Store item's quantitative factors (Store)
    and qualitative factor ratings (legacy solution_reviews + ReviewNet).
    Returns None when the solution is missing.
    """
    sol = await db.solutions_store.find_one({"solution_id": solution_id}, {"_id": 0})
    if not sol:
        return None

    quant = sol.get("quantitative_factors", []) or []

    # Qualitative: legacy solution_reviews aggregation by factor_name
    qual_scores: Dict[str, list] = {}
    try:
        reviews = await db.solution_reviews.find({"solution_id": solution_id}, {"_id": 0}).to_list(200)
        for rev in reviews:
            for qf in rev.get("qualitative_factors", []) or []:
                fname = qf.get("factor_name", "")
                if fname:
                    qual_scores.setdefault(fname, []).append(qf.get("rating", 0))
    except Exception:
        pass
    qualitative = [
        {"factor_name": k, "avg_rating": round(sum(v) / len(v), 2), "review_count": len(v)}
        for k, v in qual_scores.items() if v
    ]

    # ReviewNet enrichment (5-star aggregates per qualitative factor template)
    try:
        factors_lookup: Dict[str, str] = {}
        fq = {"is_active": True, "$or": [{"scope_type": "global"}]}
        if sol.get("life_area_id"):
            fq["$or"].append({"scope_type": "life_area", "scope_id": sol["life_area_id"]})
        if sol.get("sub_area_id"):
            fq["$or"].append({"scope_type": "sub_area", "scope_id": sol["sub_area_id"]})
        async for f in db.review_factors.find(fq, {"_id": 0}):
            factors_lookup[f["factor_id"]] = f.get("name", f["factor_id"])
        buckets: Dict[str, list] = {}
        async for rv in db.review_net.find(
            {"solution_id": solution_id, "status": {"$in": ["approved", "auto_approved"]}}, {"_id": 0}
        ):
            for fid, rating in (rv.get("factor_ratings") or {}).items():
                buckets.setdefault(fid, []).append(int(rating))
        for fid, vals in buckets.items():
            if not vals:
                continue
            qualitative.append({
                "factor_name": factors_lookup.get(fid, fid.replace("qf_", "").replace("_", " ")),
                "avg_rating": round(sum(vals) / len(vals), 2),
                "review_count": len(vals),
            })
    except Exception:
        pass

    return {
        "name": sol.get("name"),
        "type": sol.get("type"),
        "quantitative": quant,
        "qualitative": qualitative,
    }


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def _match_quant(factor: dict, ctx: dict) -> Optional[str]:
    """Best-effort name match of a quantitative factor against a solution's
    quantitative_factors list. Returns "value unit" or None."""
    fname = _norm(factor.get("name"))
    if not fname:
        return None
    for qf in ctx.get("quantitative", []) or []:
        qn = _norm(qf.get("factor_name") or qf.get("name"))
        if qn and (qn == fname or qn in fname or fname in qn):
            val = qf.get("value")
            if _has(val):
                unit = qf.get("unit") or ""
                return f"{val}{(' ' + unit) if unit else ''}".strip()
    return None


def _match_qual(factor: dict, ctx: dict) -> Optional[str]:
    """Best-effort name match of a qualitative factor against ReviewNet /
    review aggregates. Returns a human-readable rating string or None."""
    fname = _norm(factor.get("name"))
    if not fname:
        return None
    # strip the Pros&Cons "should not -" prefix for matching
    fname = fname.replace("should not ", "").strip()
    for qf in ctx.get("qualitative", []) or []:
        qn = _norm(qf.get("factor_name"))
        if qn and (qn == fname or qn in fname or fname in qn):
            return f"{qf.get('avg_rating')}/5 (from {qf.get('review_count')} review(s))"
    return None


async def resolve_actual(
    factor: dict, option: dict, decision_title: str, decision_context: str, user_id: str, ftype: str
) -> Tuple[Optional[str], Optional[str], dict]:
    """Resolve an Actual value via the priority chain.
    Returns (actual_value, source_label, enrichment_ctx).
    enrichment_ctx (solution store data) is always returned so the LLM can
    still infer even when a direct match fails.
    """
    enrichment: dict = {}

    # 1) Data Source (highest priority)
    ds = factor.get("data_source") or {}
    if ds.get("type") and ds.get("type") != "manual":
        val = await _fetch_from_data_source(factor, option.get("name", ""), decision_title, decision_context, user_id)
        if _has(val):
            return str(val), f"data_source:{ds.get('type')}", enrichment

    # 2) Linked Solution Store option → Store (quant) / ReviewNet (qual)
    sol_id = option.get("solution_id")
    if sol_id:
        ctx = await gather_solution_factor_data(sol_id)
        if ctx:
            enrichment = ctx
            match = _match_quant(factor, ctx) if ftype == "quantitative" else _match_qual(factor, ctx)
            if _has(match):
                return str(match), ("solution_store" if ftype == "quantitative" else "review_net"), enrichment

    # 3) No deterministic value — AI will infer (qualitative) / caller errors (quantitative)
    return None, None, enrichment


# ─────────────────────────────────────────────────────────────
# LLM satisfaction scoring
# ─────────────────────────────────────────────────────────────
async def _assess_pct(
    factor: dict, option: dict, actual: Optional[str], decision_title: str,
    decision_context: str, enrichment: dict, ftype: str, user_id: str,
) -> Tuple[Optional[int], Optional[str], bool]:
    """Return (pct, inferred_actual, used_llm). When `actual` is None and the
    factor is qualitative, the LLM also infers the actual from context +
    enrichment. Falls back to a numeric ratio for quantitative factors.
    """
    expected = factor.get("expected_value") or factor.get("target_value")
    operator = factor.get("operator") or ""
    unit = factor.get("unit") or ""
    fname = factor.get("display_name") or factor.get("name") or "factor"

    pct: Optional[int] = None
    inferred_actual: Optional[str] = None
    used_llm = False
    api_key = os.getenv("EMERGENT_LLM_KEY")

    if api_key:
        enrich_lines = ""
        if enrichment:
            q = enrichment.get("quantitative") or []
            ql = enrichment.get("qualitative") or []
            if q:
                enrich_lines += "\nSolution Store quantitative data: " + _json.dumps(q)[:1200]
            if ql:
                enrich_lines += "\nReviewNet qualitative ratings (1-5): " + _json.dumps(ql)[:1200]
        actual_line = (
            f"Actual value / observation: {actual} {unit}"
            if _has(actual)
            else "Actual value: NOT provided — infer the most likely actual from the context and data below."
        )
        want_actual = "" if _has(actual) else (
            ' Also return your best-estimate actual under "actual".'
        )
        prompt = (
            "Score, as a single integer percentage from 0 to 100, how well an option "
            "satisfies a decision factor versus its expectation. 100 = fully meets/exceeds, "
            "0 = not at all.\n"
            f"Decision: {decision_title}\n"
            f"Context: {decision_context}\n"
            f"Factor: {fname} (type: {ftype})\n"
            f"Expected / target: {operator} {expected if _has(expected) else 'not specified'} {unit}\n"
            f"Option: {option.get('name')}\n"
            f"{actual_line}{enrich_lines}\n"
            'Return ONLY JSON: {"satisfaction_pct": <integer 0-100>'
            + (', "actual": <string>' if not _has(actual) else "")
            + "}." + want_actual
        )
        try:
            from core.llm_compat import LlmChat, UserMessage
            chat = LlmChat(
                api_key=api_key,
                session_id=f"aiassess_{user_id}_{uuid.uuid4().hex[:8]}",
                system_message="You are a careful decision-analysis assessor. Return only valid JSON.",
            ).with_model("openai", "gpt-4.1-mini")
            resp = await chat.send_message(UserMessage(text=prompt))
            txt = (resp or "").strip()
            if txt.startswith("```"):
                txt = txt.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            parsed = _json.loads(txt)
            pct = int(round(float(parsed.get("satisfaction_pct"))))
            if not _has(actual) and _has(parsed.get("actual")):
                inferred_actual = str(parsed.get("actual"))
            used_llm = True
        except Exception as e:
            log.warning(f"AI assess fallback: {e}")
            pct = None

    if pct is None:
        # Deterministic numeric-ratio fallback (quantitative only).
        def _num(s):
            m = re.search(r"-?\d+(?:\.\d+)?", str(s))
            return float(m.group()) if m else None
        ev, av = _num(expected), _num(actual)
        if ev is not None and ev > 0 and av is not None:
            pct = int(max(0, min(100, round(av / ev * 100))))

    if pct is not None:
        pct = max(0, min(100, pct))
    return pct, inferred_actual, used_llm


async def ai_assess_factor(
    *, factor: dict, option: dict, decision_title: str, decision_context: str,
    user_id: str, provided_actual: Optional[str] = None,
) -> dict:
    """End-to-end AI Assist for one (factor, option). Validates inputs,
    resolves the actual via the priority chain, and returns the satisfaction %.

    Returns: {assessment_pct, actual_value, source, used_llm, factor_type}
    Raises HTTPException(400/502) on invalid input / unavailable AI.
    """
    ftype = resolve_factor_type(factor)
    validate_expected(factor, ftype)

    actual = provided_actual if _has(provided_actual) else None
    source = "user" if actual else None
    enrichment: dict = {}

    if not actual:
        actual, source, enrichment = await resolve_actual(
            factor, option, decision_title, decision_context, user_id, ftype
        )

    # Quantitative MUST end up with an actual; qualitative may be inferred by AI.
    if ftype == "quantitative" and not _has(actual):
        raise _missing_actual_error(factor)

    pct, inferred_actual, used_llm = await _assess_pct(
        factor, option, actual, decision_title, decision_context, enrichment, ftype, user_id
    )
    if pct is None:
        raise HTTPException(status_code=502, detail="AI assessment unavailable — please enter % manually.")

    final_actual = actual if _has(actual) else inferred_actual
    return {
        "assessment_pct": pct,
        "actual_value": final_actual,
        "source": source or ("ai_inferred" if not used_llm else "ai"),
        "used_llm": used_llm,
        "factor_type": ftype,
    }
