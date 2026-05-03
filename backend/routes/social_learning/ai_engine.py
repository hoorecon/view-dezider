"""
Social Learning Engine — AI Engine
AI classification and synthesis using LLM.
"""

import os
import uuid
import json
import logging

from core.database import db
from .constants import ORG_TYPES, SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")


async def get_hos_hierarchy_for_prompt() -> str:
    """Fetch the HOS Life Area -> Sub Area hierarchy from DB for AI prompt context."""
    life_areas = await db.hos_life_areas.find({}, {"_id": 0}).sort("order", 1).to_list(20)
    sub_areas = await db.hos_sub_areas.find({}, {"_id": 0}).sort("order", 1).to_list(100)

    # Build a lookup
    sa_by_la: dict = {}
    for sa in sub_areas:
        la_id = sa["life_area_id"]
        if la_id not in sa_by_la:
            sa_by_la[la_id] = []
        sa_by_la[la_id].append(sa)

    lines = []
    for la in life_areas:
        subs = sa_by_la.get(la["id"], [])
        sub_names = ", ".join(s["name"] for s in subs)
        lines.append(f"- {la['name']} (id: {la['id']}): [{sub_names}]")

    return "\n".join(lines)


async def classify_news(content: str) -> dict:
    """Use GPT to classify news with full HOS hierarchy, enhanced factors, risks."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    supported_langs = ", ".join(SUPPORTED_LANGUAGES)

    # Get the actual HOS hierarchy from DB
    hierarchy = await get_hos_hierarchy_for_prompt()

    prompt = f"""You are an expert analyst for View Dezider \u2014 a decision intelligence platform.
Analyze the news content below. Detect language, translate to English, and extract structured intelligence.
Supported languages: {supported_langs}

LIFE AREA HIERARCHY (from our database):
{hierarchy}

ORG TYPES: {', '.join(ORG_TYPES)}

NEWS CONTENT:
\"\"\"
{content[:5000]}
\"\"\"

Respond ONLY with valid JSON (no markdown, no explanation):
{{
  "detected_language": "<one of: {supported_langs}>",
  "english_summary": "<2-3 sentence summary in English>",
  "original_title": "<title extracted or generated from the content>",
  "category": "<exactly one of: problem, need, aspiration>",
  "category_reasoning": "<1 sentence why this category>",

  "region_hierarchy": {{
    "level": "<global/continent/country/state/city/area>",
    "global_region": "<e.g. Asia, Europe, Global>",
    "continent": "<e.g. Asia>",
    "country": "<e.g. India>",
    "state": "<state name if applicable, else null>",
    "city": "<city name if applicable, else null>",
    "area": "<specific locality if applicable, else null>"
  }},

  "org_types": ["<list of applicable org types from: {', '.join(ORG_TYPES)}>"],

  "life_area_mapping": {{
    "primary_life_area_id": "<life area ID from hierarchy above, e.g. la_finance>",
    "primary_life_area_name": "<full name>",
    "sub_area_1": "<most specific sub-area name from hierarchy>",
    "sub_area_2": "<second-level specificity if applicable, else null>"
  }},
  "secondary_life_areas": ["<additional applicable life area IDs>"],

  "scenario_mapping": {{
    "matches_predefined": <true if this maps to a common/known scenario>,
    "predefined_scenario_title": "<title of matching known scenario, or null>",
    "suggested_new_scenario": {{
      "title": "<suggested new scenario title for this sub-area>",
      "description": "<what this scenario represents>",
      "who_is_affected": "<who typically faces this>",
      "typical_trigger": "<what triggers this situation>"
    }}
  }},

  "learnings_for_mydezider": {{
    "factors": [
      {{
        "name": "<factor name>",
        "description": "<what this factor means in this context>",
        "practical_priority": "<P1 to P10, P1=highest situational priority>",
        "practical_priority_num": <1-10 integer>,
        "classification": "<mandatory or optional>",
        "expected_value": "<expected value or benchmark>",
        "expected_value_pct": <0-100 integer>,
        "factor_type": "<quantitative or qualitative>",
        "unit": "<unit of measurement if quantitative, else null>",
        "reasoning": "<why this factor matters in this scenario>"
      }}
    ],
    "summary": "<brief summary of what a decision-maker should evaluate>"
  }},

  "learnings_for_solution_finder": {{
    "risks": [
      {{
        "risk_name": "<risk name>",
        "description": "<what this risk means>",
        "probability": <1-10 integer, likelihood of occurrence>,
        "impact": <1-10 integer, severity of impact>,
        "risk_index": <probability x impact, 1-100>,
        "mitigation_plan": "<actionable mitigation strategy>",
        "contingency_plan": "<backup plan if risk materializes>",
        "personalization_note": "<how to adapt this to current times>"
      }}
    ],
    "summary": "<brief summary of risk landscape for this scenario>"
  }},

  "root_causes": ["<list of root causes identified>"],
  "lessons_learned": ["<key takeaways from this event>"],
  "what_could_prevent": "<how this situation could have been prevented>",

  "tags": ["<relevant tags>"],
  "severity_score": <1-10, how severe/impactful is this>
}}"""

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"social_learning_{uuid.uuid4().hex[:8]}",
        system_message="You are a social learning classifier. Analyze news content and extract structured information. Return only valid JSON."
    ).with_model("openai", "gpt-4.1-mini")
    response = await chat.send_message(UserMessage(text=prompt))

    # Parse JSON from response
    text = response.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        raise ValueError(f"Failed to parse AI response as JSON: {text[:200]}")


async def synthesize_templates(templates: list, target_context: dict) -> dict:
    """AI synthesis of multiple Authorized templates into a Social Solution Template."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    templates_text = ""
    for i, t in enumerate(templates, 1):
        templates_text += f"\n--- Template {i} ---\n"
        templates_text += f"Title: {t.get('title', 'N/A')}\n"
        templates_text += f"Category: {t.get('category', 'N/A')}\n"
        templates_text += f"Summary: {t.get('english_summary', 'N/A')}\n"
        templates_text += f"Life Areas: {', '.join(t.get('life_areas', []))}\n"
        templates_text += f"Scenario: {json.dumps(t.get('life_scenario_template', {}))}\n"
        templates_text += f"Factors: {json.dumps(t.get('factors', [])[:5])}\n"
        templates_text += f"Concerns: {json.dumps(t.get('concerns', [])[:5])}\n"
        templates_text += f"Lessons: {json.dumps(t.get('lessons_learned', []))}\n"
        templates_text += f"Root Causes: {json.dumps(t.get('root_causes', []))}\n"

    context_str = ""
    if target_context.get("target_region"):
        context_str += f"Target Region: {target_context['target_region']}\n"
    if target_context.get("target_org_type"):
        context_str += f"Target Org Type: {target_context['target_org_type']}\n"
    if target_context.get("target_life_area"):
        context_str += f"Target Life Area: {target_context['target_life_area']}\n"

    prompt = f"""You are the View Dezider Social Intelligence Synthesizer. 
You have {len(templates)} verified 'Authorized Social Learning Templates' from real-world incidents.
Your job: Synthesize these into ONE comprehensive 'Social Solution Template' \u2014 the distilled wisdom.

AUTHORIZED TEMPLATES:
{templates_text}

TARGET CONTEXT:
{context_str if context_str else "General / Pan-India"}

Respond ONLY with valid JSON:
{{
  "title": "<synthesized template title>",
  "description": "<comprehensive description of the pattern/situation>",
  "category": "<problem/need/aspiration>",
  "life_areas": ["<applicable life areas>"],
  "primary_life_area": "<single most relevant>",
  "life_area_sub_area": "<sub-area>",
  "org_types": ["<applicable org types>"],
  "geo_relevance": "<region relevance>",
  "pattern_identified": "<the common pattern across all templates>",
  "synthesized_factors": [
    {{
      "name": "<factor>",
      "priority": <1-10>,
      "expected_value_pct": <0-100>,
      "confidence": "<high/medium/low>",
      "supporting_template_count": <number>
    }}
  ],
  "synthesized_concerns": [
    {{
      "concern": "<synthesized concern>",
      "severity": "<high/medium/low>",
      "frequency": "<how often this appeared across templates>",
      "mitigation_consensus": "<best mitigation from all templates>"
    }}
  ],
  "combined_lessons": ["<distilled lessons>"],
  "combined_root_causes": ["<common root causes>"],
  "premium_life_scenario": {{
    "scenario_title": "<generalized scenario title>",
    "scenario_description": "<what this pattern means for decision-makers>",
    "decision_entry_point": {{
      "problem_statement": "<generalized problem statement>",
      "key_factors": ["<prioritized factors>"],
      "options_to_evaluate": ["<recommended options>"],
      "risk_checkpoints": ["<critical risk checks>"]
    }},
    "solution_finder_entry_point": {{
      "smart_goal": "<preventive goal>",
      "main_concerns": ["<top concerns>"],
      "risk_management_questions": ["<proactive Q4 questions>"],
      "recommended_actions": ["<preventive actions>"]
    }}
  }},
  "accuracy_notes": "<how confident is this synthesis>",
  "source_template_count": {len(templates)},
  "tags": ["<tags>"]
}}"""

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"synthesize_{uuid.uuid4().hex[:8]}",
        system_message="You are a social solution synthesizer. Combine multiple templates into a comprehensive solution. Return only valid JSON."
    ).with_model("openai", "gpt-4.1-mini")
    response = await chat.send_message(UserMessage(text=prompt))

    text = response.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        raise ValueError("Failed to parse synthesis response")
