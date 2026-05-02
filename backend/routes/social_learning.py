"""
Social Learning Engine — View Dezider
Converts real-world news into proactive decision guardrails.

3-Tier Knowledge Pyramid:
  Tier 1: Social Learning Template (user's personal, from news upload)
  Tier 2: Authorized Social Learning Template (admin-approved, public as-is)
  Tier 3: Social Solution Template (AI-synthesized from multiple Tier 2s, subscription-gated)

Pipeline: News → Language Detection → AI Classification → Factor Extraction → Template Generation
"""

import os
import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from core.database import db
from routes.auth_routes import get_current_user
from routes.audit_trail import log_audit_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/social-learning", tags=["Social Learning"])

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

# ========================
# CONSTANTS
# ========================

LIFE_AREAS = [
    "career_profession", "finance_wealth", "health_wellness",
    "relationships_family", "education_learning", "personal_growth",
    "social_community", "legal_governance", "technology_innovation",
    "environment_sustainability",
]

ORG_TYPES = ["family", "individual", "association", "company", "startup", "ngo", "govt", "cooperative", "trust"]

CATEGORIES = ["problem", "need", "aspiration"]

INDIAN_LANGUAGES = [
    "english", "hindi", "tamil", "telugu", "kannada", "malayalam", "marathi",
    "gujarati", "bengali", "punjabi", "odia", "assamese", "urdu",
    "konkani", "manipuri", "nepali", "sindhi", "sanskrit", "bodo",
    "dogri", "kashmiri", "maithili", "santhali",
]

TEMPLATE_STATUSES = ["draft", "submitted", "authorized", "rejected"]

# ========================
# MODELS
# ========================

class NewsUploadRequest(BaseModel):
    content: str  # News text in any language
    source_url: Optional[str] = None
    source_name: Optional[str] = None
    title: Optional[str] = None


class AdminApprovalRequest(BaseModel):
    status: str  # "authorized" or "rejected"
    admin_notes: Optional[str] = ""


class SynthesizeRequest(BaseModel):
    template_ids: List[str]  # List of Authorized Social Learning Template IDs to synthesize
    target_region: Optional[str] = None
    target_org_type: Optional[str] = None
    target_life_area: Optional[str] = None


# ========================
# AI ENGINE
# ========================

async def classify_news(content: str) -> dict:
    """Use GPT to classify news into Problem/Need/Aspiration, extract factors, concerns, life areas."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    prompt = f"""You are an expert analyst for the View Dezider decision intelligence platform. 
Analyze this news article/content and extract structured insights.

NEWS CONTENT:
\"\"\"
{content[:4000]}
\"\"\"

Respond ONLY with valid JSON (no markdown, no explanation) in this exact structure:
{{
  "detected_language": "<language code: english, hindi, tamil, telugu, etc.>",
  "english_summary": "<2-3 sentence summary in English>",
  "original_title": "<title extracted or generated from the content>",
  "category": "<exactly one of: problem, need, aspiration>",
  "category_reasoning": "<1 sentence why this category>",
  "life_areas": ["<list of applicable life areas from: career_profession, finance_wealth, health_wellness, relationships_family, education_learning, personal_growth, social_community, legal_governance, technology_innovation, environment_sustainability>"],
  "org_types": ["<list of applicable org types from: family, individual, association, company, startup, ngo, govt, cooperative, trust>"],
  "geo_regions": ["<Indian state(s) or 'pan_india' if national>"],
  "geo_district": "<specific district if mentioned, else null>",
  "factors": [
    {{
      "name": "<factor name>",
      "description": "<what this factor means in context>",
      "priority": <1-10 integer, 10=highest>,
      "expected_value_pct": <0-100 integer, assessment percentage>,
      "factor_type": "<quantitative or qualitative>"
    }}
  ],
  "concerns": [
    {{
      "concern": "<risk/concern statement>",
      "severity": "<high/medium/low>",
      "mitigation": "<how to mitigate this>"
    }}
  ],
  "root_causes": ["<list of root causes identified>"],
  "lessons_learned": ["<list of lessons from this experience>"],
  "what_could_prevent": "<how this situation could have been avoided>",
  "decision_template": {{
    "problem_statement": "<clear problem statement for PRR Step 1>",
    "key_factors": ["<factors for PRR Step 3>"],
    "options_to_evaluate": ["<potential options for PRR Step 6>"],
    "risk_checkpoints": ["<proactive risk checks for Solution Finder Q4>"]
  }},
  "solution_finder_template": {{
    "life_area": "<primary life area>",
    "smart_goal": "<what the person should have aimed for>",
    "main_concerns": ["<top concerns>"],
    "risk_management_questions": ["<Q4 risk questions to ask proactively>"],
    "recommended_actions": ["<preventive action items>"]
  }},
  "tags": ["<relevant tags>"],
  "severity_score": <1-10, how severe/impactful is this incident>
}}"""

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        model="openai/gpt-4.1-mini",
    )
    chat.add_message(UserMessage(content=prompt))
    response = await chat.chat()

    # Parse JSON from response
    text = response.content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        raise ValueError(f"Failed to parse AI response as JSON: {text[:200]}")


async def synthesize_templates(templates: list, target_context: dict) -> dict:
    """AI synthesis of multiple Authorized Social Learning Templates into a Social Solution Template."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    templates_text = ""
    for i, t in enumerate(templates, 1):
        templates_text += f"\n--- Template {i} ---\n"
        templates_text += f"Title: {t.get('title', 'N/A')}\n"
        templates_text += f"Category: {t.get('category', 'N/A')}\n"
        templates_text += f"Summary: {t.get('english_summary', 'N/A')}\n"
        templates_text += f"Life Areas: {', '.join(t.get('life_areas', []))}\n"
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
Your job: Synthesize these into ONE comprehensive 'Social Solution Template' — the distilled wisdom.

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
  "org_types": ["<applicable org types>"],
  "geo_relevance": "<region relevance>",
  "pattern_identified": "<the common pattern across all templates>",
  "synthesized_factors": [
    {{
      "name": "<factor>",
      "priority": <1-10>,
      "expected_value_pct": <0-100>,
      "confidence": "<high/medium/low based on how many templates support this>",
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
  "proactive_decision_template": {{
    "problem_statement": "<generalized problem statement>",
    "key_factors": ["<prioritized factors>"],
    "options_to_evaluate": ["<recommended options>"],
    "risk_checkpoints": ["<critical risk checks>"]
  }},
  "proactive_solution_template": {{
    "life_area": "<primary life area>",
    "smart_goal": "<preventive goal>",
    "main_concerns": ["<top concerns>"],
    "risk_management_questions": ["<proactive Q4 questions>"],
    "recommended_actions": ["<preventive actions>"]
  }},
  "accuracy_notes": "<how confident is this synthesis>",
  "source_template_count": {len(templates)},
  "tags": ["<tags>"]
}}"""

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        model="openai/gpt-4.1-mini",
    )
    chat.add_message(UserMessage(content=prompt))
    response = await chat.chat()

    text = response.content.strip()
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


# ========================
# HELPERS
# ========================

async def require_admin(user: dict):
    u = await db.users.find_one({"user_id": user["user_id"]})
    if not u or u.get("role") not in ["admin", "org_admin", "super_admin"]:
        raise HTTPException(403, "Admin access required")
    return u


# ========================
# TIER 1: Social Learning Templates (User)
# ========================

@router.post("/upload")
async def upload_news(data: NewsUploadRequest, request: Request, user: dict = Depends(get_current_user)):
    """Upload news content, AI classifies and generates Social Learning Template."""
    if not data.content or len(data.content.strip()) < 50:
        raise HTTPException(400, "News content must be at least 50 characters")

    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "AI engine not configured (EMERGENT_LLM_KEY missing)")

    # AI Classification & Extraction
    try:
        classification = await classify_news(data.content)
    except Exception as e:
        logger.error(f"AI classification failed: {e}")
        raise HTTPException(500, f"AI classification failed: {str(e)}")

    now = datetime.now(timezone.utc).isoformat()
    template_id = f"SLT-{uuid.uuid4().hex[:10].upper()}"

    template = {
        "id": template_id,
        "tier": 1,  # Social Learning Template
        "status": "draft",
        "created_by": user["user_id"],
        "created_at": now,
        "updated_at": now,

        # Source
        "original_content": data.content[:5000],
        "source_url": data.source_url,
        "source_name": data.source_name,
        "user_title": data.title,

        # AI Classification
        "detected_language": classification.get("detected_language", "english"),
        "english_summary": classification.get("english_summary", ""),
        "title": classification.get("original_title", data.title or "Untitled"),
        "category": classification.get("category", "problem"),
        "category_reasoning": classification.get("category_reasoning", ""),
        "life_areas": classification.get("life_areas", []),
        "org_types": classification.get("org_types", []),
        "geo_regions": classification.get("geo_regions", []),
        "geo_district": classification.get("geo_district"),
        "severity_score": classification.get("severity_score", 5),

        # Extracted Intelligence
        "factors": classification.get("factors", []),
        "concerns": classification.get("concerns", []),
        "root_causes": classification.get("root_causes", []),
        "lessons_learned": classification.get("lessons_learned", []),
        "what_could_prevent": classification.get("what_could_prevent", ""),

        # Generated Templates
        "decision_template": classification.get("decision_template", {}),
        "solution_finder_template": classification.get("solution_finder_template", {}),

        "tags": classification.get("tags", []),

        # Admin fields
        "admin_notes": "",
        "authorized_at": None,
        "authorized_by": None,
    }

    await db.social_learning_templates.insert_one(template)

    await log_audit_event(
        action="social_learning_created", entity_type="social_learning",
        entity_id=template_id, user_id=user["user_id"],
        details=f"News uploaded & classified: {template['title'][:60]} [{template['category']}] lang={template['detected_language']}",
        ip_address=get_client_ip(request) if hasattr(request, 'client') else "",
    )

    # Remove heavy fields from response
    template.pop("original_content", None)
    template.pop("_id", None)

    return template


@router.get("/my-templates")
async def get_my_templates(
    status: Optional[str] = None,
    category: Optional[str] = None,
    life_area: Optional[str] = None,
    limit: int = 30,
    skip: int = 0,
    user: dict = Depends(get_current_user),
):
    """Get current user's Social Learning Templates."""
    query: dict = {"created_by": user["user_id"]}
    if status:
        query["status"] = status
    if category:
        query["category"] = category
    if life_area:
        query["life_areas"] = life_area

    total = await db.social_learning_templates.count_documents(query)
    templates = await db.social_learning_templates.find(
        query, {"_id": 0, "original_content": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    return {"total": total, "templates": templates}


@router.get("/template/{template_id}")
async def get_template(template_id: str, user: dict = Depends(get_current_user)):
    """Get a specific Social Learning Template with full details."""
    template = await db.social_learning_templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(404, "Template not found")

    # Users can only see their own drafts, or authorized templates
    if template["status"] == "draft" and template["created_by"] != user["user_id"]:
        u = await db.users.find_one({"user_id": user["user_id"]})
        if not u or u.get("role") not in ["admin", "org_admin", "super_admin"]:
            raise HTTPException(403, "Access denied")

    return template


@router.post("/template/{template_id}/submit")
async def submit_template(template_id: str, user: dict = Depends(get_current_user)):
    """Submit a draft template for admin review."""
    template = await db.social_learning_templates.find_one({"id": template_id})
    if not template:
        raise HTTPException(404, "Template not found")
    if template["created_by"] != user["user_id"]:
        raise HTTPException(403, "Only the creator can submit")
    if template["status"] != "draft":
        raise HTTPException(400, f"Template is already '{template['status']}', cannot submit")

    now = datetime.now(timezone.utc).isoformat()
    await db.social_learning_templates.update_one(
        {"id": template_id},
        {"$set": {"status": "submitted", "updated_at": now}}
    )

    return {"id": template_id, "status": "submitted", "message": "Template submitted for admin review"}


# ========================
# TIER 2: Admin Approval → Authorized Social Learning Templates
# ========================

@router.get("/admin/pending")
async def get_pending_templates(
    category: Optional[str] = None,
    life_area: Optional[str] = None,
    limit: int = 30,
    skip: int = 0,
    user: dict = Depends(get_current_user),
):
    """List submitted templates pending admin approval."""
    await require_admin(user)
    query: dict = {"status": "submitted"}
    if category:
        query["category"] = category
    if life_area:
        query["life_areas"] = life_area

    total = await db.social_learning_templates.count_documents(query)
    templates = await db.social_learning_templates.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    return {"total": total, "templates": templates}


@router.post("/admin/approve/{template_id}")
async def approve_template(template_id: str, data: AdminApprovalRequest, user: dict = Depends(get_current_user)):
    """Approve or reject a submitted template. Approved = Tier 2 'Authorized Social Learning Template'."""
    admin = await require_admin(user)

    template = await db.social_learning_templates.find_one({"id": template_id})
    if not template:
        raise HTTPException(404, "Template not found")
    if template["status"] != "submitted":
        raise HTTPException(400, f"Template status is '{template['status']}', expected 'submitted'")

    if data.status not in ["authorized", "rejected"]:
        raise HTTPException(400, "Status must be 'authorized' or 'rejected'")

    now = datetime.now(timezone.utc).isoformat()
    update = {
        "status": data.status,
        "admin_notes": data.admin_notes or "",
        "updated_at": now,
    }
    if data.status == "authorized":
        update["tier"] = 2  # Upgrade to Tier 2
        update["authorized_at"] = now
        update["authorized_by"] = user["user_id"]

    await db.social_learning_templates.update_one({"id": template_id}, {"$set": update})

    await log_audit_event(
        action=f"social_learning_{data.status}", entity_type="social_learning",
        entity_id=template_id, user_id=user["user_id"],
        details=f"Template {data.status}: {template.get('title', '')[:60]}. Notes: {data.admin_notes or 'N/A'}",
    )

    return {"id": template_id, "status": data.status, "tier": 2 if data.status == "authorized" else 1}


@router.get("/authorized")
async def get_authorized_templates(
    category: Optional[str] = None,
    life_area: Optional[str] = None,
    org_type: Optional[str] = None,
    region: Optional[str] = None,
    limit: int = 30,
    skip: int = 0,
    user: dict = Depends(get_current_user),
):
    """Browse Authorized Social Learning Templates (Tier 2). Available to all users."""
    query: dict = {"status": "authorized", "tier": 2}
    if category:
        query["category"] = category
    if life_area:
        query["life_areas"] = life_area
    if org_type:
        query["org_types"] = org_type
    if region:
        query["geo_regions"] = region

    total = await db.social_learning_templates.count_documents(query)
    templates = await db.social_learning_templates.find(
        query, {"_id": 0, "original_content": 0}
    ).sort("severity_score", -1).skip(skip).limit(limit).to_list(limit)

    return {"total": total, "templates": templates}


# ========================
# TIER 3: Social Solution Templates (AI Synthesis)
# ========================

@router.post("/admin/synthesize")
async def synthesize_social_solution(data: SynthesizeRequest, user: dict = Depends(get_current_user)):
    """Synthesize multiple Authorized Social Learning Templates into a Social Solution Template (Tier 3).
    Admin-only. This is the premium, subscription-gated content.
    """
    admin = await require_admin(user)

    if len(data.template_ids) < 2:
        raise HTTPException(400, "At least 2 Authorized templates required for synthesis")

    # Fetch source templates
    templates = await db.social_learning_templates.find(
        {"id": {"$in": data.template_ids}, "status": "authorized", "tier": 2}, {"_id": 0}
    ).to_list(100)

    if len(templates) < 2:
        raise HTTPException(400, f"Only {len(templates)} authorized templates found. Need at least 2.")

    # AI Synthesis
    try:
        synthesis = await synthesize_templates(templates, {
            "target_region": data.target_region,
            "target_org_type": data.target_org_type,
            "target_life_area": data.target_life_area,
        })
    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        raise HTTPException(500, f"AI synthesis failed: {str(e)}")

    now = datetime.now(timezone.utc).isoformat()
    solution_id = f"SST-{uuid.uuid4().hex[:10].upper()}"

    solution = {
        "id": solution_id,
        "tier": 3,  # Social Solution Template
        "status": "active",
        "created_by": user["user_id"],
        "created_at": now,

        # Synthesis metadata
        "source_template_ids": data.template_ids,
        "source_count": len(templates),
        "target_region": data.target_region,
        "target_org_type": data.target_org_type,
        "target_life_area": data.target_life_area,

        # Synthesized content
        "title": synthesis.get("title", "Synthesized Template"),
        "description": synthesis.get("description", ""),
        "category": synthesis.get("category", "problem"),
        "life_areas": synthesis.get("life_areas", []),
        "org_types": synthesis.get("org_types", []),
        "geo_relevance": synthesis.get("geo_relevance", ""),
        "pattern_identified": synthesis.get("pattern_identified", ""),

        "synthesized_factors": synthesis.get("synthesized_factors", []),
        "synthesized_concerns": synthesis.get("synthesized_concerns", []),
        "combined_lessons": synthesis.get("combined_lessons", []),
        "combined_root_causes": synthesis.get("combined_root_causes", []),
        "accuracy_notes": synthesis.get("accuracy_notes", ""),

        # Ready-to-use templates
        "proactive_decision_template": synthesis.get("proactive_decision_template", {}),
        "proactive_solution_template": synthesis.get("proactive_solution_template", {}),

        "tags": synthesis.get("tags", []),

        # Subscription control
        "access_tier": "premium",  # "general" or "premium"
    }

    await db.social_solution_templates.insert_one(solution)

    await log_audit_event(
        action="social_solution_synthesized", entity_type="social_solution",
        entity_id=solution_id, user_id=user["user_id"],
        details=f"Social Solution Template synthesized from {len(templates)} sources: {solution['title'][:60]}",
    )

    solution.pop("_id", None)
    return solution


@router.get("/solutions")
async def get_social_solutions(
    category: Optional[str] = None,
    life_area: Optional[str] = None,
    org_type: Optional[str] = None,
    region: Optional[str] = None,
    access_tier: Optional[str] = None,
    limit: int = 30,
    skip: int = 0,
    user: dict = Depends(get_current_user),
):
    """Browse Social Solution Templates (Tier 3). Subscription-gated."""
    query: dict = {"status": "active", "tier": 3}
    if category:
        query["category"] = category
    if life_area:
        query["life_areas"] = life_area
    if org_type:
        query["org_types"] = org_type
    if region:
        query["geo_relevance"] = {"$regex": region, "$options": "i"}
    if access_tier:
        query["access_tier"] = access_tier

    # TODO: Check user subscription tier for premium access
    total = await db.social_solution_templates.count_documents(query)
    solutions = await db.social_solution_templates.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    return {"total": total, "solutions": solutions}


@router.get("/solution/{solution_id}")
async def get_social_solution(solution_id: str, user: dict = Depends(get_current_user)):
    """Get a specific Social Solution Template."""
    solution = await db.social_solution_templates.find_one({"id": solution_id}, {"_id": 0})
    if not solution:
        raise HTTPException(404, "Social Solution Template not found")
    # TODO: Check subscription for premium access
    return solution


# ========================
# STATS & FILTERS
# ========================

@router.get("/stats")
async def get_social_learning_stats(user: dict = Depends(get_current_user)):
    """Get overall social learning statistics."""
    total_t1 = await db.social_learning_templates.count_documents({"tier": 1})
    total_t2 = await db.social_learning_templates.count_documents({"tier": 2, "status": "authorized"})
    total_t3 = await db.social_solution_templates.count_documents({"tier": 3})
    pending = await db.social_learning_templates.count_documents({"status": "submitted"})
    my_count = await db.social_learning_templates.count_documents({"created_by": user["user_id"]})

    # Category breakdown
    pipeline = [
        {"$match": {"status": "authorized"}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
    ]
    cat_breakdown = await db.social_learning_templates.aggregate(pipeline).to_list(10)

    # Life area breakdown
    pipeline_la = [
        {"$match": {"status": "authorized"}},
        {"$unwind": "$life_areas"},
        {"$group": {"_id": "$life_areas", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    la_breakdown = await db.social_learning_templates.aggregate(pipeline_la).to_list(20)

    return {
        "tier_1_user_templates": total_t1,
        "tier_2_authorized": total_t2,
        "tier_3_solutions": total_t3,
        "pending_review": pending,
        "my_templates": my_count,
        "category_breakdown": [{**c, "category": c["_id"]} for c in cat_breakdown],
        "life_area_breakdown": [{**l, "life_area": l["_id"]} for l in la_breakdown],
    }


@router.get("/filter-options")
async def get_filter_options(user: dict = Depends(get_current_user)):
    """Get available filter options for browsing templates."""
    return {
        "categories": CATEGORIES,
        "life_areas": LIFE_AREAS,
        "org_types": ORG_TYPES,
        "languages": INDIAN_LANGUAGES,
        "template_statuses": TEMPLATE_STATUSES,
    }
