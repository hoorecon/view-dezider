"""Emotional Gatekeeper — AI Engine
AI analysis for trap detection, loop recommendation, limitation classification,
outlet analysis, and breakthrough report generation.
"""

import os
import uuid
import json
import logging

logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")


async def _call_llm(prompt: str, system_msg: str = "") -> str:
    """Call GPT-4.1-mini via Emergent LLM."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"eg_{uuid.uuid4().hex[:8]}",
        system_message=system_msg or "You are a compassionate decision coach and emotional intelligence assistant for View Dezider. You speak in a wise, practical, emotionally safe, direct, non-judgmental, and empowering tone. You are NOT a therapist. You are a conscious decision coach."
    ).with_model("openai", "gpt-4.1-mini")
    response = await chat.send_message(UserMessage(text=prompt))
    return response.strip()


async def _call_llm_json(prompt: str, system_msg: str = "") -> dict:
    """Call LLM and parse JSON response."""
    text = await _call_llm(prompt, system_msg)
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
        raise ValueError(f"Failed to parse AI JSON: {text[:200]}")


# ============================================================
# TRAP ANALYSIS
# ============================================================

async def analyze_trap(trap_data: dict) -> dict:
    """Analyze trap data and generate awareness summary."""
    prompt = f"""Analyze this mental trap situation using the 3-stage Trap framework:
- **Landscaping**: Mind scanning for issues/risks without urgency
- **Linking**: Mind connecting a trigger to a problem
- **Looping**: Mind replaying the issue, creating false feeling of solving

User's Situation:
- Situation: {trap_data.get('situation', 'Not specified')}
- Category: {trap_data.get('category', 'Not specified')}
- Intensity: {trap_data.get('intensity', 'Not specified')}/10
- Scanning for: {trap_data.get('scanning_for', 'Not specified')}
- Scanning patterns: {trap_data.get('scanning_patterns', [])}
- Scanning without urgency: {trap_data.get('scanning_without_urgency', 'Not specified')}
- Repeated concern: {trap_data.get('repeated_concern', 'Not specified')}
- Trigger type: {trap_data.get('trigger_type', 'Not specified')}
- External trigger: {trap_data.get('external_trigger', 'Not specified')}
- Internal trigger: {trap_data.get('internal_trigger', 'Not specified')}
- Linking meaning: {trap_data.get('linking_meaning', 'Not specified')}
- Repeating thought: {trap_data.get('repeating_thought', 'Not specified')}
- Getting new solution: {trap_data.get('getting_new_solution', 'Not specified')}
- Emotion increasing: {trap_data.get('emotion_increasing', 'Not specified')}
- Intensity before loop: {trap_data.get('intensity_before', 'N/A')}
- Intensity after loop: {trap_data.get('intensity_after', 'N/A')}

Respond ONLY with valid JSON:
{{
  "current_stage": "<landscaping/linking/looping>",
  "stage_confidence": <0.0-1.0>,
  "main_trigger": "<identified main trigger>",
  "repeated_thought": "<the core repeating thought>",
  "emotional_amplification_pattern": "<how emotions are being amplified>",
  "false_problem_solving": "<what user mistakes as problem-solving>",
  "awareness_statement": "<personalized awareness statement for the user - 2-3 sentences>",
  "intervention": {{
    "type": "<grounding/separating/loop_breaking>",
    "description": "<specific personalized intervention based on the detected stage>",
    "immediate_action": "<one thing user can do right now>"
  }},
  "recommended_next": "<break_loop/ground/separate_trigger>"
}}"""
    return await _call_llm_json(prompt)


# ============================================================
# LOOP ANALYSIS
# ============================================================

async def recommend_loop_method(loop_data: dict) -> dict:
    """AI recommends the best loop-breaking method."""
    prompt = f"""A user is stuck in a mental loop. Based on their situation, recommend the BEST loop-breaking method.

The 4 methods are:
1. "i_dont_know" — Accept uncertainty. User is strongly judging situation as good/bad.
2. "all_is_well" — Trust life's goodness. User feels hopeless.
3. "both_good_bad" — See duality. User sees only the negative side.
4. "this_too_shall_pass" — Recognize impermanence. User feels stuck in emotional permanence.

User's Loop:
- Repeated thought: {loop_data.get('repeated_thought', '')}
- Emotion: {loop_data.get('emotion', '')}
- Repeat count today: {loop_data.get('repeat_count_today', 'Unknown')}
- Fear: {loop_data.get('fear', '')}
- Trying to solve: {loop_data.get('trying_to_solve', '')}

Respond ONLY with valid JSON:
{{
  "recommended_method": "<i_dont_know/all_is_well/both_good_bad/this_too_shall_pass>",
  "reason": "<why this method fits the user's situation — personalized, 2-3 sentences>",
  "alternative_method": "<second best method>",
  "alternative_reason": "<why the alternative could also help>"
}}"""
    return await _call_llm_json(prompt)


async def generate_loop_reframe(loop_data: dict, method_data: dict) -> dict:
    """Generate the loop reframe summary after method completion."""
    method_names = {
        "i_dont_know": "I Don't Know",
        "all_is_well": "All Is Well",
        "both_good_bad": "Both Good and Bad",
        "this_too_shall_pass": "This Too Shall Pass",
    }
    method_name = method_names.get(method_data.get('selected_method', ''), 'Unknown')

    prompt = f"""Generate a personalized loop reframe summary using the "{method_name}" method.

Apply the specific principles of this method:
{{
  "i_dont_know": "Help user accept they don't know the full truth. Create neutral space. Prevent automatic labeling.",
  "all_is_well": "Help user see hidden opportunities. Rebuild trust. Find the silver lining.",
  "both_good_bad": "Show both positive and negative aspects. Balance the view. Focus on manageable risks.",
  "this_too_shall_pass": "Emphasize impermanence. Perspective across 1 week, 1 month, 1 year. Time heals."
}}

User's Loop:
- Repeated thought: {loop_data.get('repeated_thought', '')}
- Emotion: {loop_data.get('emotion', '')}
- Fear: {loop_data.get('fear', '')}
- Method chosen: {method_name}
- Method answers: {json.dumps(method_data.get('method_answers', {}))}

Respond ONLY with valid JSON:
{{
  "original_thought": "<the repeating thought>",
  "emotional_driver": "<the underlying emotion driving the loop>",
  "method_applied": "{method_name}",
  "new_perspective": "<new way of seeing this situation using the method's principles — personalized, 3-4 sentences>",
  "calming_statement": "<a calming personalized statement based on the method>",
  "immediate_action": "<one practical action to take right now>",
  "reflection_affirmation": "<a personalized affirmation for the user>",
  "deeper_limitation_detected": <true/false>,
  "limitation_hint": "<if true, what deeper limitation may exist>"
}}"""
    return await _call_llm_json(prompt)


# ============================================================
# LIMITATION ANALYSIS
# ============================================================

async def classify_limitation(data: dict) -> dict:
    """AI classifies the limitation category."""
    prompt = f"""Classify this limitation into one of 4 categories:
1. "past_self" — Old failures define present capability
2. "past_others" — Others' past experiences influence user's decisions
3. "external_inputs" — Social media, news, ads, conversations mislead conclusions
4. "fear_unknown" — Unknown = difficult = impossible = impossible forever

User's Limitation:
- Statement: {data.get('limitation_statement', '')}
- Why limited: {data.get('why_limited', '')}
- Origin: {data.get('origin', '')}
- Duration of belief: {data.get('belief_duration', '')}
- Cost: {data.get('cost_of_limitation', '')}

Respond ONLY with valid JSON:
{{
  "category": "<past_self/past_others/external_inputs/fear_unknown>",
  "confidence": <0.0-1.0>,
  "reasoning": "<why this category fits — personalized, 2-3 sentences>",
  "hidden_assumption": "<the hidden assumption driving this limitation>"
}}"""
    return await _call_llm_json(prompt)


async def generate_limitation_reframe(data: dict, category: str, flow_answers: dict) -> dict:
    """Generate reframe based on limitation category and flow answers."""
    category_prompts = {
        "past_self": "Apply the principle: 'I failed before' becomes 'I have grown since then.' Compare old vs current capability.",
        "past_others": "Apply the principle: 'Their result is my future' becomes 'Their experience is one input, not my destiny.' Identify biases in others' experience.",
        "external_inputs": "Apply 4 evaluation filters: Authenticity, Completeness, Accuracy, Intention. 'I heard it, so it is true' becomes 'I will validate before I decide.'",
        "fear_unknown": "Apply: 'Unknown ≠ difficult. Difficult ≠ impossible. Impossible ≠ impossible forever.' Break the fear chain.",
    }

    prompt = f"""Generate a personalized limitation reframe.

Category: {category}
Method to apply: {category_prompts.get(category, '')}

User's Limitation: {data.get('limitation_statement', '')}
Origin: {data.get('origin', '')}
Cost: {data.get('cost_of_limitation', '')}
Flow Answers: {json.dumps(flow_answers)}

Respond ONLY with valid JSON:
{{
  "limitation": "<the original limitation>",
  "category": "{category}",
  "hidden_assumption": "<the hidden assumption>",
  "old_belief": "<the old limiting belief>",
  "new_belief": "<the transformed empowering belief>",
  "growth_evidence": "<evidence of growth or capability — personalized>",
  "reframe_statement": "<powerful reframe in first person>",
  "suggested_action": "<practical next step>",
  "action_timeline": "<when to take this action>",
  "affirmation": "<personalized affirmation>"
}}"""
    return await _call_llm_json(prompt)


# ============================================================
# OUTLET ANALYZER
# ============================================================

async def analyze_outlets(entries: list, user_context: str = "") -> dict:
    """Analyze emotional outlets and recommend constructive alternatives of the SAME nature type."""
    entries_text = ""
    for e in entries:
        entries_text += f"- {e.get('name', e.get('strategy_id', ''))}: Frequency={e.get('frequency', '?')}, Nature={e.get('nature', '?')}, Compulsive={e.get('is_compulsive', False)}, Side-effects={e.get('side_effects', 'None')}\n"

    prompt = f"""Analyze these emotional coping strategies and recommend CONSTRUCTIVE alternatives of the SAME NATURE TYPE.

Nature types: Physical, Mental, Emotional, Energy

IMPORTANT: If a user has a destructive Mental habit (e.g., reading sensational news), recommend constructive Mental alternatives (e.g., reading Economic Times, industry bulletins, educational podcasts).
If Physical is destructive, suggest constructive Physical alternatives. Same for Emotional and Energy.

User's Current Outlets:
{entries_text}

Additional context: {user_context}

Respond ONLY with valid JSON:
{{
  "summary": {{
    "total_strategies": <number>,
    "physical_count": <number>,
    "mental_count": <number>,
    "emotional_count": <number>,
    "energy_count": <number>,
    "compulsive_count": <number>,
    "constructive_count": <number>,
    "destructive_count": <number>
  }},
  "analysis": [
    {{
      "strategy": "<strategy name>",
      "nature": "<physical/mental/emotional/energy>",
      "assessment": "<constructive/destructive/neutral>",
      "explanation": "<why this is constructive or destructive — personalized>",
      "recommended_alternative": "<constructive alternative of the SAME nature — only if destructive/neutral>",
      "why_alternative": "<why this alternative is better — personalized>"
    }}
  ],
  "overall_pattern": "<overall emotional coping pattern — personalized summary>",
  "top_recommendations": [
    "<recommendation 1>",
    "<recommendation 2>",
    "<recommendation 3>"
  ],
  "balance_score": {{
    "physical": <1-10 health score>,
    "mental": <1-10>,
    "emotional": <1-10>,
    "energy": <1-10>
  }}
}}"""
    return await _call_llm_json(prompt)


# ============================================================
# AIM ANALYSIS
# ============================================================

async def analyze_aim(addictions: list, irritations: list) -> dict:
    """Analyze addictions and irritations, suggest corrective actions."""
    add_text = ""
    for a in addictions:
        add_text += f"- Addiction: {a.get('addiction', '')}, Area: {a.get('area_of_life', '')}, Trigger: {a.get('triggering_situations', '')}, +Impact: {a.get('positive_impact', '')} ({a.get('positive_impact_pct', '?')}%), -Impact: {a.get('negative_impact', '')} ({a.get('negative_impact_pct', '?')}%)\n"

    irr_text = ""
    for i in irritations:
        irr_text += f"- Irritation: {i.get('irritation', '')}, Area: {i.get('area_of_life', '')}, Reaction: {i.get('probable_reaction', '')}, +Impact: {i.get('positive_impact', '')}, -Impact: {i.get('negative_impact', '')}\n"

    prompt = f"""Analyze these addictions and irritations. Provide self-awareness insights and corrective action plans.

Addictions:
{add_text or 'None provided'}

Irritations:
{irr_text or 'None provided'}

Respond ONLY with valid JSON:
{{
  "addictions_analysis": [
    {{
      "addiction": "<name>",
      "severity": "<low/medium/high>",
      "root_pattern": "<underlying pattern — personalized>",
      "corrective_action": "<suggested corrective action>",
      "replacement_behavior": "<healthier replacement>",
      "timeline": "<suggested timeline>"
    }}
  ],
  "irritations_analysis": [
    {{
      "irritation": "<name>",
      "reaction_pattern": "<the automatic reaction pattern>",
      "emotional_root": "<what emotion drives this reaction>",
      "constructive_response": "<suggested constructive response>",
      "practice_tip": "<how to practice this new response>"
    }}
  ],
  "self_awareness_summary": "<overall self-awareness insight — personalized, 3-4 sentences>",
  "top_priorities": [
    "<priority 1>",
    "<priority 2>",
    "<priority 3>"
  ]
}}"""
    return await _call_llm_json(prompt)


# ============================================================
# BREAKTHROUGH REPORT
# ============================================================

async def generate_breakthrough_report(session_data: dict) -> dict:
    """Generate the full 11-section AI Breakthrough Report."""
    prompt = f"""Generate a comprehensive Breakthrough Report for this introspection session.

Session Data:
{json.dumps(session_data, indent=2, default=str)}

The report must follow this exact 11-section structure.
Tone: Wise, practical, emotionally safe, direct, non-judgmental, empowering. Like a conscious decision coach.

Respond ONLY with valid JSON:
{{
  "report_title": "<personalized title>",
  "sections": [
    {{"title": "Your Situation", "content": "<personalized summary of the user's situation>"}},
    {{"title": "Current Mental Pattern", "content": "<identified mental pattern>"}},
    {{"title": "Trap Stage", "content": "<Landscaping/Linking/Looping analysis, or 'Not applicable' if no trap was explored>"}},
    {{"title": "Loop Type & Method", "content": "<loop type and which method was applied, or 'Not applicable'>"}},
    {{"title": "Limitation Category", "content": "<limitation category and analysis, or 'Not applicable'>"}},
    {{"title": "Hidden Assumption", "content": "<the hidden assumption driving the pattern>"}},
    {{"title": "Emotional Driver", "content": "<the core emotion fueling this>"}},
    {{"title": "Reframe", "content": "<the transformative reframe>"}},
    {{"title": "Practical Solution", "content": "<actionable solution>"}},
    {{"title": "Immediate Action", "content": "<one thing to do right now>"}},
    {{"title": "Reflection Affirmation", "content": "<personalized affirmation>"}}
  ],
  "breakthrough_score": <1-10 how significant this breakthrough is>,
  "follow_up_recommended": "<solution_finder/ctt_task/journal/none>"
}}"""
    return await _call_llm_json(prompt)
