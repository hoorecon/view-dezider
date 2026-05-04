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
    from emergentintegrations.llm.chat import LlmChat, UserMessage
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
    from emergentintegrations.llm.chat import LlmChat, UserMessage
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
    from emergentintegrations.llm.chat import LlmChat, UserMessage
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
