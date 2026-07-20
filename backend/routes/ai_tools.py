"""AI tools routes — TEPFI auto-mapping, Factor Data Source fetch, CLD inline analyze"""

import uuid
import os
import logging
import math
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user
from core.rate_limiting import limiter, AI_LIMIT

logger = logging.getLogger(__name__)
router = APIRouter(tags=["AI Tools"])


@router.post("/tepfi-auto-map")
@limiter.limit(AI_LIMIT)
async def tepfi_auto_map(request: Request, user: dict = Depends(get_current_user)):
    """AI auto-map factors to TEPFI elements and solution layers"""
    from core.llm_compat import LlmChat, UserMessage  # provider-agnostic shim (Emergent | direct via litellm)
    import json as json_module

    body = await request.json()
    context = body.get("context", "")
    decision_title = body.get("title", "")
    factors = body.get("factors", [])

    if not factors:
        return {"mappings": []}

    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    factor_list = "\n".join([f"- {f.get('name', '')} (category: {f.get('category', '')}, unit: {f.get('unit', '')})" for f in factors])

    prompt = f"""You are an expert decision analyst using the TEPFI framework.

Decision: {decision_title}
Context: {context}

Factors to classify:
{factor_list}

For each factor, assign:
1. tepfi_elements: one or more from [T=Time, E=Effort, P=People, F=Finance, I=Infrastructure] — use the single letter codes
2. tepfi_layer: one from [self, micro, macro]
   - self = personal/individual control
   - micro = immediate environment (team, family, organization)
   - macro = external/systemic factors

Return ONLY valid JSON array, no markdown, no explanation:
[{{"factor_name": "...", "tepfi_elements": ["T","F"], "tepfi_layer": "self"}}]"""

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"tepfi_{user['user_id']}_{uuid.uuid4().hex[:8]}",
            system_message="You are a TEPFI framework classifier. Return only valid JSON."
        ).with_model("openai", "gpt-4.1-mini")

        response = await chat.send_message(UserMessage(text=prompt))
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        mappings = json_module.loads(response_text)
        return {"mappings": mappings}
    except Exception as e:
        logger.error(f"TEPFI auto-map error: {str(e)}")
        return {"mappings": [], "error": str(e)}


@router.post("/factors/fetch-data")
@limiter.limit(AI_LIMIT)
async def fetch_factor_data(request: Request, user: dict = Depends(get_current_user)):
    """Fetch actual values for factors from configured data sources (webhook, web_surf, ai_llm)."""
    from core.llm_compat import LlmChat, UserMessage  # provider-agnostic shim (Emergent | direct via litellm)
    import json as json_module

    body = await request.json()
    decision_title = body.get("decision_title", "")
    decision_context = body.get("decision_context", "")
    option_name = body.get("option_name", "")
    factors = body.get("factors", [])

    if not factors:
        return {"results": []}

    results = []

    webhook_factors = [f for f in factors if f.get("data_source", {}).get("type") == "webhook"]
    web_surf_factors = [f for f in factors if f.get("data_source", {}).get("type") == "web_surf"]
    ai_llm_factors = [f for f in factors if f.get("data_source", {}).get("type") == "ai_llm"]

    # --- WEBHOOK FETCH ---
    for factor in webhook_factors:
        ds = factor.get("data_source", {})
        config = ds.get("config", {})
        url = config.get("url", "")
        if not url:
            results.append({"factor_id": factor["id"], "value": None, "source_type": "webhook", "error": "No URL configured"})
            continue
        try:
            headers_str = config.get("headers", "{}")
            try:
                custom_headers = json_module.loads(headers_str) if headers_str else {}
            except Exception:
                custom_headers = {}
            payload = {
                "factor_name": factor.get("name", ""),
                "factor_type": factor.get("factor_type", ""),
                "option_name": option_name,
                "decision_title": decision_title,
                "unit": factor.get("unit", ""),
                "expected_value": factor.get("expected_value"),
            }
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client_http:
                resp = await client_http.post(url, json=payload, headers=custom_headers)
                data = resp.json()
                value = data.get("value", data.get("result", str(data)))
                results.append({"factor_id": factor["id"], "value": value, "source_type": "webhook", "raw_response": str(data)[:500]})
        except Exception as e:
            results.append({"factor_id": factor["id"], "value": None, "source_type": "webhook", "error": str(e)[:200]})

    # --- WEB SURF FETCH ---
    if web_surf_factors:
        api_key = os.getenv("EMERGENT_LLM_KEY")
        if not api_key:
            for f in web_surf_factors:
                results.append({"factor_id": f["id"], "value": None, "source_type": "web_surf", "error": "LLM key not configured"})
        else:
            for factor in web_surf_factors:
                ds = factor.get("data_source", {})
                config = ds.get("config", {})
                search_query = config.get("search_query", "")
                if not search_query:
                    search_query = f"{factor.get('name', '')} {option_name} {decision_title}"
                else:
                    search_query = search_query.replace("{factor}", factor.get("name", ""))
                    search_query = search_query.replace("{option}", option_name)
                    search_query = search_query.replace("{title}", decision_title)
                try:
                    search_results_text = ""
                    try:
                        from duckduckgo_search import DDGS
                        with DDGS() as ddgs:
                            ddg_results = list(ddgs.text(search_query, max_results=5))
                        for idx, r in enumerate(ddg_results, 1):
                            search_results_text += f"\n{idx}. {r.get('title', '')}: {r.get('body', '')[:300]}"
                            if r.get('href'):
                                search_results_text += f"\n   Source: {r['href']}"
                    except Exception as search_err:
                        search_results_text = f"(Web search unavailable: {str(search_err)[:100]})"

                    prompt = f"""Based on the following web search results, extract the current real-world value for:

Factor: {factor.get('name', '')}
Option/Subject: {option_name}
Decision Context: {decision_title} - {decision_context}
Expected Unit: {factor.get('unit', 'N/A')}
Data Type: {factor.get('factor_type', 'unknown')}

Web Search Results for "{search_query}":
{search_results_text}

Return ONLY a JSON object with:
- "value": the actual value (number for quantitative, text for qualitative)
- "confidence": "high", "medium", or "low"
- "source_note": brief note about the source of this data

Return ONLY valid JSON, no explanation."""

                    chat = LlmChat(
                        api_key=api_key,
                        session_id=f"websurf_{user['user_id']}_{uuid.uuid4().hex[:8]}",
                        system_message="You are a research assistant. Analyze web search results and extract factual data values. Return only valid JSON."
                    ).with_model("openai", "gpt-4.1-mini")
                    response = await chat.send_message(UserMessage(text=prompt))
                    response_text = response.strip()
                    if response_text.startswith("```"):
                        response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                    data = json_module.loads(response_text)
                    results.append({
                        "factor_id": factor["id"], "value": data.get("value"),
                        "source_type": "web_surf", "confidence": data.get("confidence", "medium"),
                        "source_note": data.get("source_note", ""),
                    })
                except Exception as e:
                    results.append({"factor_id": factor["id"], "value": None, "source_type": "web_surf", "error": str(e)[:200]})

    # --- AI LLM FETCH ---
    if ai_llm_factors:
        api_key = os.getenv("EMERGENT_LLM_KEY")
        if not api_key:
            for f in ai_llm_factors:
                results.append({"factor_id": f["id"], "value": None, "source_type": "ai_llm", "error": "LLM key not configured"})
        else:
            for factor in ai_llm_factors:
                ds = factor.get("data_source", {})
                config = ds.get("config", {})
                custom_prompt = config.get("prompt", "")
                if not custom_prompt:
                    custom_prompt = f"What is the {factor.get('name', '')} for {option_name}?"
                else:
                    custom_prompt = custom_prompt.replace("{factor}", factor.get("name", ""))
                    custom_prompt = custom_prompt.replace("{option}", option_name)
                    custom_prompt = custom_prompt.replace("{title}", decision_title)
                try:
                    system_msg = f"""You are a decision-support AI. Provide data values for decision factors.
Decision: {decision_title}
Context: {decision_context}
Evaluating option: {option_name}

Return ONLY a JSON object:
- "value": the value ({factor.get('unit', 'appropriate unit')})
- "reasoning": brief explanation (1-2 sentences)

Return ONLY valid JSON, no markdown."""

                    chat = LlmChat(
                        api_key=api_key,
                        session_id=f"aillm_{user['user_id']}_{uuid.uuid4().hex[:8]}",
                        system_message=system_msg
                    ).with_model("openai", "gpt-4.1-mini")
                    response = await chat.send_message(UserMessage(text=custom_prompt))
                    response_text = response.strip()
                    if response_text.startswith("```"):
                        response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                    data = json_module.loads(response_text)
                    results.append({
                        "factor_id": factor["id"], "value": data.get("value"),
                        "source_type": "ai_llm", "reasoning": data.get("reasoning", ""),
                    })
                except Exception as e:
                    results.append({"factor_id": factor["id"], "value": None, "source_type": "ai_llm", "error": str(e)[:200]})

    return {"results": results}


@router.post("/cld/analyze")
@limiter.limit(AI_LIMIT)
async def cld_analyze(request: Request, user: dict = Depends(get_current_user)):
    """Generate a Causal Loop Diagram from factors and auto-derive Steps 3-5 values."""
    from core.llm_compat import LlmChat, UserMessage  # provider-agnostic shim (Emergent | direct via litellm)
    import json as json_module

    body = await request.json()

    # Deduct credits for AI analysis
    try:
        from routes.payments import deduct_credits
        await deduct_credits(user["user_id"], "decision_analyze")
    except HTTPException:
        raise
    except Exception:
        pass

    title = body.get("decision_title", "")
    context = body.get("decision_context", "")
    life_area = body.get("life_area", "")
    decision_type = body.get("decision_type", "")
    factors = body.get("factors", [])

    if len(factors) < 2:
        raise HTTPException(status_code=400, detail="At least 2 factors required for CLD analysis")

    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    factor_names = [f.get("name", "") for f in factors]
    factor_ids = [f.get("id", "") for f in factors]
    factor_list_str = "\n".join([f"  {i+1}. {name} (id: {fid})" for i, (name, fid) in enumerate(zip(factor_names, factor_ids))])

    prompt = f"""Analyze the following decision factors using Causal Loop Diagram (CLD) methodology from Systems Thinking.

Decision: {title}
Context: {context}
Life Area: {life_area}
Decision Type: {decision_type}

Factors:
{factor_list_str}

Perform the following analysis and return ONLY a valid JSON object:

1. **CLD Links**: Identify causal relationships between factors. For each link:
   - from_id: source factor id
   - to_id: target factor id  
   - type: "reinforcing" (same direction change) or "balancing" (opposite direction change)
   - strength: 1-5 (how strong the causal link is)
   - description: brief explanation of the causal relationship

2. **CLD Loops**: Identify feedback loops (reinforcing R or balancing B):
   - name: loop name (e.g., "R1: Growth Loop")
   - type: "reinforcing" or "balancing"
   - factor_ids: array of factor ids in the loop

3. **Centrality Scores**: For each factor, compute a centrality score (0.0 to 1.0) based on:
   - Number of incoming/outgoing links
   - Participation in feedback loops
   - Strength of connections

4. **Classifications**: Based on centrality:
   - centrality >= 0.5 → "primary" (essential, highly connected)
   - centrality < 0.5 → "secondary" (supporting, less connected)

5. **Priority Order**: Rank factors from most to least influential based on:
   - Centrality score
   - Number of reinforcing loops participated in
   - Total link strength

6. **Gap Multipliers**: For rating gaps (Step 5):
   - Factors with much higher centrality than the one below → gap_multiplier 2.0-3.0
   - Moderate difference → 1.0-1.5
   - Small difference → 0.5-1.0

Return this exact JSON structure:
{{
  "links": [
    {{"from_id": "...", "to_id": "...", "type": "reinforcing|balancing", "strength": 1-5, "description": "..."}}
  ],
  "loops": [
    {{"name": "R1: ...", "type": "reinforcing|balancing", "factor_ids": ["..."]}}
  ],
  "factor_analysis": [
    {{
      "factor_id": "...",
      "factor_name": "...",
      "centrality": 0.0-1.0,
      "classification": "primary|secondary",
      "priority_rank": 1,
      "gap_multiplier": 0.5-3.0,
      "reasoning": "brief explanation"
    }}
  ]
}}

Return ONLY valid JSON, no markdown fences, no explanation outside the JSON."""

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"cld_{user['user_id']}_{uuid.uuid4().hex[:8]}",
            system_message="You are an expert in Systems Thinking and Causal Loop Diagrams. Analyze factor relationships precisely."
        ).with_model("openai", "gpt-4.1-mini")

        response = await chat.send_message(UserMessage(text=prompt))
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        cld_data = json_module.loads(response_text)

        # Build node positions (circular layout)
        n = len(factors)
        nodes = []
        for i, factor in enumerate(factors):
            angle = (2 * math.pi * i) / n
            fa = next((fa for fa in cld_data.get("factor_analysis", []) if fa["factor_id"] == factor["id"]), None)
            nodes.append({
                "factor_id": factor["id"],
                "name": factor["name"],
                "x": 200 + 140 * math.cos(angle),
                "y": 200 + 140 * math.sin(angle),
                "centrality": fa["centrality"] if fa else 0.5,
                "classification": fa["classification"] if fa else "secondary",
                "priority_rank": fa["priority_rank"] if fa else i + 1,
                "gap_multiplier": fa["gap_multiplier"] if fa else 1.0,
            })

        return {
            "cld": {
                "nodes": nodes,
                "links": cld_data.get("links", []),
                "loops": cld_data.get("loops", []),
            },
            "factor_analysis": cld_data.get("factor_analysis", []),
        }
    except Exception as e:
        if "JSONDecodeError" in type(e).__name__:
            raise HTTPException(status_code=500, detail=f"AI returned invalid JSON: {str(e)[:100]}")
        raise HTTPException(status_code=500, detail=f"CLD analysis failed: {str(e)[:200]}")



# ============================================================================
# FIND MY BEST OPTIONS — AI-suggested options blended with Solution Store
# ============================================================================
import re as _re


def _tok(text: str) -> set:
    """Tokenise into lowercased words >2 chars."""
    return {t for t in _re.split(r"[^a-z0-9]+", str(text or "").lower()) if len(t) > 2}


def _match_factor_id(name, factor_index):
    """Map a factor name (from AI or a Store quantitative_factor) to a decision
    factor id. Exact (case-insensitive) match first, then containment, then best
    token overlap."""
    if not name or not factor_index:
        return None
    ln = str(name).lower().strip()
    if not ln:
        return None
    for fi in factor_index:
        if fi["lname"] == ln:
            return fi["id"]
    for fi in factor_index:
        if fi["lname"] and (fi["lname"] in ln or ln in fi["lname"]):
            return fi["id"]
    name_toks = _tok(name)
    best, best_score = None, 0
    for fi in factor_index:
        score = len(name_toks & _tok(fi["name"]))
        if score > best_score:
            best, best_score = fi["id"], score
    return best if best_score > 0 else None


async def _store_candidates(user: dict, life_area_id, sub_area_id, goal_tokens: set, title: str, context: str):
    """Return up to 6 ranked Solution-Store candidates relevant to the goal/factors."""
    vis_filter = [
        {"created_by": user["user_id"]},
        {"is_authorized": True},
        {"visibility": "PUBLIC", "approval_status": "approved"},
    ]
    if user.get("org_id"):
        vis_filter.append({"visibility": "ORG", "org_id": user["org_id"]})
    base_q = {"status": "active", "$or": vis_filter}

    docs = []
    if life_area_id:
        q = dict(base_q)
        q["life_area_id"] = life_area_id
        if sub_area_id:
            q["sub_area_id"] = sub_area_id
        docs = await db.solutions_store.find(q, {"_id": 0}).to_list(80)
        if len(docs) < 3 and sub_area_id:
            q.pop("sub_area_id", None)
            docs = await db.solutions_store.find(q, {"_id": 0}).to_list(80)
    taxonomy_hit = len(docs) > 0
    if len(docs) < 3:
        docs = await db.solutions_store.find(base_q, {"_id": 0}).to_list(200)

    tokens = set(goal_tokens) | _tok(f"{title} {context}")

    def _score(sol) -> int:
        toks = _tok(sol.get("name"))
        for t in (sol.get("tags") or []):
            toks |= _tok(t)
        for qf in (sol.get("quantitative_factors") or []):
            toks |= _tok(qf.get("factor_name", ""))
        toks |= _tok(sol.get("description"))
        score = len(tokens & toks)
        if life_area_id and sol.get("life_area_id") == life_area_id:
            score += 2
        if sub_area_id and sol.get("sub_area_id") == sub_area_id:
            score += 1
        return score

    scored = sorted(((s, _score(s)) for s in docs), key=lambda x: x[1], reverse=True)
    # Keep relevant items: positive overlap, OR taxonomy-filtered set when we matched a life area.
    relevant = [s for s, sc in scored if sc > 0]
    if not relevant and taxonomy_hit:
        relevant = [s for s, _ in scored]
    top = relevant[:6]

    ratings = {}
    ids = [s["solution_id"] for s in top]
    if ids:
        try:
            agg = await db.review_net.aggregate([
                {"$match": {"solution_id": {"$in": ids}, "status": {"$in": ["approved", "auto_approved"]}}},
                {"$group": {"_id": "$solution_id", "avg": {"$avg": "$overall_rating"}, "count": {"$sum": 1}}},
            ]).to_list(50)
            for a in agg:
                if a.get("avg") is not None:
                    ratings[a["_id"]] = round(float(a["avg"]), 1)
            legacy = await db.solution_reviews.aggregate([
                {"$match": {"solution_id": {"$in": ids}}},
                {"$group": {"_id": "$solution_id", "avg": {"$avg": "$overall_rating"}}},
            ]).to_list(50)
            for a in legacy:
                if a["_id"] not in ratings and a.get("avg") is not None:
                    ratings[a["_id"]] = round(float(a["avg"]), 1)
        except Exception as e:
            logger.warning(f"find-best-options rating agg failed: {e}")

    return [{
        "solution_id": s["solution_id"],
        "name": s.get("name", "Untitled"),
        "price_range": s.get("price_range") or None,
        "rating": ratings.get(s["solution_id"]),
        "quantitative_factors": s.get("quantitative_factors") or [],
    } for s in top]


async def _run_options_llm(prompt: str, user: dict, provider: str, model: str, api_key: str, list_key: str = "options"):
    from core.llm_compat import LlmChat, UserMessage
    import json as json_module
    chat = LlmChat(
        api_key=api_key,
        session_id=f"aigen_{user['user_id']}_{uuid.uuid4().hex[:8]}",
        system_message="You are a decision-support strategist. Return only valid JSON.",
    ).with_model(provider, model)
    resp = await chat.send_message(UserMessage(text=prompt))
    txt = (resp or "").strip()
    if txt.startswith("```"):
        txt = txt.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    if txt.lower().startswith("json"):
        txt = txt[4:].strip()
    data = json_module.loads(txt)
    if isinstance(data, dict):
        return data.get(list_key, [])
    if isinstance(data, list):
        return data
    return []


@router.post("/ai/find-best-options")
@limiter.limit(AI_LIMIT)
async def find_best_options(request: Request, user: dict = Depends(get_current_user)):
    """AI-suggest the top 3-5 best-suited options for a PRR decision, blended with
    matching Solution-Store items, ranked by the user's prioritized factors.

    Lets users who have no options yet prefill Step 6 and continue to assessment.
    """
    body = await request.json()
    decision_id = body.get("decision_id")
    limit = max(3, min(5, int(body.get("limit") or 5)))

    from core import ai_wallet as _aw
    if not await _aw.touchpoint_enabled("tp_best_options"):
        raise HTTPException(status_code=403, detail="‘Find My Best Options’ is currently disabled by the administrator.")

    title = body.get("title", "")
    context = body.get("context", "")
    life_area = body.get("life_area")
    life_area_id = body.get("life_area_id")
    sub_area_id = body.get("sub_area_id")
    factors = body.get("factors", [])
    existing_names = set()

    if decision_id:
        dec = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
        if not dec:
            raise HTTPException(status_code=404, detail="Decision not found")
        title = dec.get("title", title)
        context = dec.get("context", context)
        life_area = dec.get("life_area", life_area)
        life_area_id = dec.get("life_area_id", life_area_id)
        sub_area_id = dec.get("sub_area_id", sub_area_id)
        factors = dec.get("factors") or factors
        existing_names = {(o.get("name") or "").strip().lower() for o in (dec.get("options") or [])}

    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    # Prioritized factors: most important first (rating desc, then order asc).
    pri = sorted(
        [f for f in factors if f.get("name")],
        key=lambda f: (-int(f.get("rating") or 0), int(f.get("order") or 0)),
    )
    factor_tokens = set()
    factor_lines = []
    factor_index = []  # [{id, name, lname, data_type}] for value mapping
    for f in pri:
        nm = str(f.get("name"))
        factor_tokens |= _tok(nm)
        exp, op, unit = f.get("expected_value"), f.get("operator"), f.get("unit")
        extra = ""
        if exp not in (None, ""):
            extra = f" (target {op or ''} {exp}{(' ' + str(unit)) if unit else ''})"
        factor_lines.append(f"- {nm} [{f.get('category') or 'primary'}]{extra}")
        factor_index.append({
            "id": f.get("id"),
            "name": nm,
            "lname": nm.lower().strip(),
            "data_type": f.get("data_type") or "numeric",
        })
    factor_block = "\n".join(factor_lines) if factor_lines else "(no factors yet — infer sensible criteria from the goal)"
    factor_name_list = ", ".join(fi["name"] for fi in factor_index) or "(none)"

    store = await _store_candidates(user, life_area_id, sub_area_id, factor_tokens, title, context)
    cand_lines = []
    for i, c in enumerate(store):
        pb = f", price {c['price_range']}" if c.get("price_range") else ""
        rb = f", {c['rating']}\u2605" if c.get("rating") else ""
        cand_lines.append(f"[{i}] {c['name']}{pb}{rb}")
    cand_block = "\n".join(cand_lines) if cand_lines else "(none available)"

    goal = title or context or "the user's goal"
    prompt = f"""You help a user choose the BEST options for a decision so they can evaluate them.

Life area: {life_area or life_area_id or 'general'}
Goal / expectations: {goal}
Context: {context or '(none)'}

Prioritized decision factors (most important first):
{factor_block}

Available Solution-Store items (you MAY reuse these via "store_index"):
{cand_block}

Return the {limit} BEST-suited, DISTINCT options, ranked best-first, that best satisfy the
prioritized factors and the user's goal. Prefer a Solution-Store item when one genuinely fits
(set its "store_index"); otherwise propose a strong, realistic real-world option.

For EACH option, also estimate the option's ACTUAL value for every prioritized factor in
"factor_values" (use the EXACT factor names: {factor_name_list}). Give a realistic number for
quantitative factors (no units, just the number) and a short word/phrase for qualitative ones.

Return ONLY valid JSON, no markdown:
{{"options":[{{"name":"...","rationale":"one concise sentence linking it to the top factors","store_index":0,"factor_values":[{{"factor":"<exact factor name>","value":<number or "short text">}}]}}]}}
Use "store_index": null for options that are NOT from the store list."""

    used_model = "claude-sonnet-4-5-20250929"
    ai_options = []
    try:
        ai_options = await _run_options_llm(prompt, user, "anthropic", used_model, api_key)
    except Exception as e1:
        logger.warning(f"find-best-options primary (claude) failed: {e1}; retrying gpt-4.1-mini")
        try:
            used_model = "gpt-4.1-mini"
            ai_options = await _run_options_llm(prompt, user, "openai", used_model, api_key)
        except Exception as e2:
            logger.error(f"find-best-options fallback failed: {e2}")
            ai_options = []
            used_model = None  # both LLM calls failed → Store-only result below

    merged = []
    seen = set(existing_names)
    for opt in ai_options:
        name = (opt.get("name") or "").strip()
        if not name:
            continue
        si = opt.get("store_index")
        st = store[si] if isinstance(si, int) and 0 <= si < len(store) else None
        if st:
            name = st["name"]
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        item = {
            "name": name,
            "ai_rationale": (opt.get("rationale") or "").strip(),
            "source": "store" if st else "ai",
        }
        if st:
            item["solution_id"] = st["solution_id"]
            item["price_range"] = st.get("price_range")
            item["rating"] = st.get("rating")
        # Per-factor actual values: AI estimates first, Store data overrides (authoritative).
        fv_map = {}
        for fv in (opt.get("factor_values") or []):
            fid = _match_factor_id(fv.get("factor"), factor_index)
            if fid and fv.get("value") not in (None, ""):
                fv_map[fid] = fv.get("value")
        if st:
            for qf in (st.get("quantitative_factors") or []):
                fid = _match_factor_id(qf.get("factor_name"), factor_index)
                val = qf.get("value")
                if fid and val not in (None, ""):
                    fv_map[fid] = val
        if fv_map:
            item["factor_values"] = [{"factor_id": fid, "value": v} for fid, v in fv_map.items()]
        merged.append(item)
        if len(merged) >= limit:
            break

    # Fallback: if the model produced nothing usable, surface top store matches directly.
    if not merged and store:
        for c in store[:limit]:
            if c["name"].lower() in seen:
                continue
            fv_map = {}
            for qf in (c.get("quantitative_factors") or []):
                fid = _match_factor_id(qf.get("factor_name"), factor_index)
                val = qf.get("value")
                if fid and val not in (None, ""):
                    fv_map[fid] = val
            entry = {
                "name": c["name"],
                "ai_rationale": "Matched from the Solution Store by your prioritized factors.",
                "source": "store",
                "solution_id": c["solution_id"],
                "price_range": c.get("price_range"),
                "rating": c.get("rating"),
            }
            if fv_map:
                entry["factor_values"] = [{"factor_id": fid, "value": v} for fid, v in fv_map.items()]
            merged.append(entry)

    return {"options": merged, "used_model": used_model, "store_match_count": len(store)}


# ============================================================================
# FETCH MY BEST FACTORS — AI-suggested decision factors for Step 2
# ============================================================================
@router.post("/ai/suggest-factors")
@limiter.limit(AI_LIMIT)
async def suggest_factors(request: Request, user: dict = Depends(get_current_user)):
    """AI-suggest 5-8 well-chosen decision factors for a PRR decision, based on the
    chosen life area, decision type, and the decision's title + description.

    Lets a user auto-fill Step 2 (Define Factors & Criteria) and proceed to Step 3.
    Returns factors in the same shape consumed by addFactorsFromTemplate().
    """
    body = await request.json()
    decision_id = body.get("decision_id")
    limit = max(4, min(8, int(body.get("limit") or 7)))

    from core import ai_wallet as _aw
    if not await _aw.touchpoint_enabled("tp_best_factors"):
        raise HTTPException(status_code=403, detail="‘Fetch My Best Factors’ is currently disabled by the administrator.")

    title = body.get("title", "")
    context = body.get("context", "")
    life_area = body.get("life_area")
    decision_type = body.get("decision_type")
    existing_names = set()

    if decision_id:
        dec = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
        if not dec:
            raise HTTPException(status_code=404, detail="Decision not found")
        title = dec.get("title", title)
        context = dec.get("context", context)
        life_area = dec.get("life_area", life_area)
        decision_type = dec.get("decision_type", decision_type)
        existing_names = {(f.get("name") or "").strip().lower() for f in (dec.get("factors") or [])}

    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    prompt = f"""You help a user define the decision factors (criteria) they will use to evaluate options.

Life area: {life_area or 'general'}
Decision type: {decision_type or 'general'}
Decision title: {title or '(none)'}
Description / context: {context or '(none)'}

Propose the {limit} MOST important, DISTINCT factors a thoughtful person would weigh for this
decision. Mark the truly critical ones as "primary" and the rest as "secondary". For factors that
are naturally measurable, set factor_type "quantitative" and suggest a sensible expected target as
a percentage 0-100 in "expected_value_pct"; otherwise use "qualitative".

Order them from MOST important (priority 10) to least (priority 1).

Return ONLY valid JSON, no markdown:
{{"factors":[{{"name":"short factor name","category":"primary","priority":9,"factor_type":"quantitative","expected_value_pct":80,"rationale":"one concise sentence"}}]}}"""

    used_model = "claude-sonnet-4-5-20250929"
    raw = []
    try:
        raw = await _run_options_llm(prompt, user, "anthropic", used_model, api_key, list_key="factors")
    except Exception as e1:
        logger.warning(f"suggest-factors primary (claude) failed: {e1}; retrying gpt-4.1-mini")
        try:
            used_model = "gpt-4.1-mini"
            raw = await _run_options_llm(prompt, user, "openai", used_model, api_key, list_key="factors")
        except Exception as e2:
            logger.error(f"suggest-factors fallback failed: {e2}")
            raw = []
            used_model = None

    factors = []
    seen = set(existing_names)
    for f in raw:
        name = (f.get("name") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        cat = "primary" if str(f.get("category")).lower() == "primary" else "secondary"
        ftype = "quantitative" if str(f.get("factor_type")).lower() == "quantitative" else "qualitative"
        try:
            pr = int(f.get("priority"))
        except (TypeError, ValueError):
            pr = 7 if cat == "primary" else 5
        pr = max(1, min(10, pr))
        item = {
            "name": name,
            "priority": pr,
            "factor_type": ftype,
            "category": cat,
            "rationale": (f.get("rationale") or "").strip(),
        }
        exp = f.get("expected_value_pct")
        if ftype == "quantitative" and exp not in (None, ""):
            try:
                item["expected_value_pct"] = max(0, min(100, float(exp)))
            except (TypeError, ValueError):
                pass
        factors.append(item)
        if len(factors) >= limit:
            break

    return {"factors": factors, "used_model": used_model}


# ============================================================================
# PRIORITIZE FACTORS — AI suggests the importance ORDER for Step 4 (metered)
# ============================================================================
@router.post("/ai/prioritize-factors")
@limiter.limit(AI_LIMIT)
async def prioritize_factors(request: Request, user: dict = Depends(get_current_user)):
    """AI-suggest the priority ORDER of the decision's existing factors for
    Step 4. METERED — charges the user's AI Wallet by ACTUAL tokens used
    (free-first Gemini chain on the 'fast' tier; Claude on 'precise').
    Returns a per-factor {id, name, rank} the frontend applies as the new
    ordering (the user can still tweak with the up/down arrows afterwards)."""
    import re as _re
    import json as _json
    from core.ai_metering import metered_chat
    from core import ai_wallet as _aw

    if not await _aw.touchpoint_enabled("tp_prioritize_factors"):
        raise HTTPException(status_code=403, detail="‘Prioritize with AI’ is currently disabled by the administrator.")

    # Input validation — malformed bodies must fail with 400/422, not 500.
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 — invalid/empty JSON payload
        raise HTTPException(status_code=400, detail="Request body must be valid JSON.")
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object.")
    decision_id = body.get("decision_id")
    ai_tier = "precise" if str(body.get("ai_tier") or "").lower() == "precise" else "fast"

    title = body.get("title", "")
    context = body.get("context", "")
    life_area = body.get("life_area")
    factors = body.get("factors", [])

    if decision_id:
        dec = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
        if not dec:
            raise HTTPException(status_code=404, detail="Decision not found")
        title = dec.get("title", title)
        context = dec.get("context", context)
        life_area = dec.get("life_area", life_area)
        factors = dec.get("factors") or factors

    # Only the TOP-LEVEL factors are prioritised in Step 4.
    if not isinstance(factors, list) or not all(isinstance(f, dict) for f in factors):
        raise HTTPException(status_code=422, detail="'factors' must be a list of factor objects ({id, name, ...}).")
    top = [f for f in factors if not f.get("parent_id")]
    names = [(f.get("name") or "").strip() for f in top if (f.get("name") or "").strip()]
    if len(names) < 2:
        raise HTTPException(status_code=422, detail="Add at least 2 factors before prioritising with AI.")
    if any((f.get("name") or "").strip() and not f.get("id") for f in top):
        raise HTTPException(status_code=422, detail="Each factor must include both 'id' and 'name'.")

    factor_list = "\n".join(f"- {n}" for n in names)
    system_message = "You are a decision-prioritisation strategist. Return only valid JSON."
    prompt = f"""Rank the user's decision factors from MOST to LEAST important for THIS decision.

Life area: {life_area or 'general'}
Decision title: {title or '(none)'}
Description / context: {context or '(none)'}

Factors to prioritise:
{factor_list}

Return a 1-based rank for EVERY factor (1 = most important). Use EXACTLY the factor
names given, rank each once, no ties.

Return ONLY valid JSON, no markdown:
{{"factors":[{{"name":"<exact name>","rank":1}}]}}"""

    meta: dict = {}
    try:
        out = await metered_chat(
            user["user_id"], system_message=system_message, prompt=prompt,
            feature="factor_prioritize", session_prefix="factorprio",
            tier=ai_tier, meta=meta)
    except _aw.InsufficientCredits:
        raise HTTPException(status_code=402, detail="Out of AI credits. Top up your AI Wallet to use AI prioritisation.")
    except Exception as e:  # noqa: BLE001 — every provider failed
        logger.warning(f"prioritize-factors LLM failed: {e}")
        raise HTTPException(status_code=503, detail="AI is temporarily unavailable. Please try again shortly.")

    data = {}
    m = _re.search(r"\{.*\}", (out or "").strip(), _re.S)
    if m:
        try:
            data = _json.loads(m.group(0))
        except Exception:  # noqa: BLE001
            data = {}

    by_name = {(f.get("name") or "").strip().lower(): f for f in top}
    ranked, seen = [], set()
    for r in (data.get("factors") or []):
        if not isinstance(r, dict):
            continue
        f = by_name.get((r.get("name") or "").strip().lower())
        if not f or f["id"] in seen:
            continue
        seen.add(f["id"])
        try:
            rank = int(r.get("rank"))
        except (TypeError, ValueError):
            rank = len(ranked) + 1
        ranked.append({"id": f["id"], "name": f.get("name"), "rank": rank})
    # Append any factors the AI omitted (stable, after the ranked ones).
    for f in top:
        if f["id"] not in seen:
            ranked.append({"id": f["id"], "name": f.get("name"), "rank": len(ranked) + 1})
    ranked.sort(key=lambda x: x["rank"])
    # Normalise to a clean 1..N sequence after sorting.
    for i, r in enumerate(ranked):
        r["rank"] = i + 1

    return {"factors": ranked, "provider": meta.get("provider"), "credits": meta.get("credits")}

