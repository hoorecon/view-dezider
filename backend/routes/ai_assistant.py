"""
AI Solution Assistant — Personal advisor chatbot across all modules.
Knows user's full context (PNA, goals, decisions, lifestyle, conflicts).
Supports 6 languages: English, Tamil, Telugu, Kannada, Malayalam, Hindi.
"""
import uuid
import os
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user
from core.rate_limiting import limiter, AI_LIMIT

router = APIRouter(prefix="/ai-assistant", tags=["AI Solution Assistant"])

SUPPORTED_LANGUAGES = {
    "en": "English",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
    "ml": "Malayalam",
    "hi": "Hindi",
}


@router.get("/meta")
async def get_meta():
    """Return supported languages and capabilities."""
    return {
        "languages": SUPPORTED_LANGUAGES,
        "capabilities": [
            "Cross-module personal advice",
            "PNA-based recommendations",
            "Goal planning assistance",
            "Conflict preparation coaching",
            "Lifestyle optimization suggestions",
            "CLD-based causal insights",
            "Decision support",
        ],
    }


@router.get("/conversations")
async def list_conversations(user: dict = Depends(get_current_user)):
    """List all AI assistant conversations."""
    convos = await db.ai_assistant_conversations.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("updated_at", -1).to_list(50)
    # Return without full messages for list view
    return [
        {
            "conversation_id": c["conversation_id"],
            "title": c.get("title", "New Chat"),
            "language": c.get("language", "en"),
            "message_count": len(c.get("messages", [])),
            "updated_at": c.get("updated_at"),
        }
        for c in convos
    ]


@router.post("/conversations")
async def create_conversation(request: Request, user: dict = Depends(get_current_user)):
    """Create a new AI assistant conversation."""
    body = await request.json()
    conv_id = f"AIC-{uuid.uuid4().hex[:10].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "conversation_id": conv_id,
        "user_id": user["user_id"],
        "title": body.get("title", "New Conversation"),
        "language": body.get("language", "en"),
        "messages": [],
        "created_at": now,
        "updated_at": now,
    }
    await db.ai_assistant_conversations.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str, user: dict = Depends(get_current_user)):
    """Get a conversation with all messages."""
    doc = await db.ai_assistant_conversations.find_one(
        {"conversation_id": conv_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(404, "Conversation not found")
    return doc


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str, user: dict = Depends(get_current_user)):
    """Delete a conversation."""
    result = await db.ai_assistant_conversations.delete_one(
        {"conversation_id": conv_id, "user_id": user["user_id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(404, "Conversation not found")
    return {"deleted": True}


async def _gather_user_context(user_id: str) -> str:
    """Gather user's full context across all modules for AI personalization."""
    parts = []

    # PNA items
    pna = await db.pna_items.find({"user_id": user_id, "status": {"$ne": "resolved"}}, {"_id": 0}).to_list(15)
    if pna:
        items = "\n".join([f"- [{i['category']}] {i['title']} ({i['life_area']}) — {i.get('priority','medium')}" for i in pna])
        parts.append(f"ACTIVE PNA ITEMS:\n{items}")

    # Goals
    goals = await db.gem_goals.find({"user_id": user_id, "status": "active"}, {"_id": 0}).to_list(10)
    if goals:
        g_text = "\n".join([f"- {g['title']} ({g.get('life_area','')}) — progress: {g.get('progress',0)}%" for g in goals])
        parts.append(f"ACTIVE GOALS:\n{g_text}")

    # Active lifestyle plan
    plan = await db.lifestyle_plans.find_one({"user_id": user_id, "is_active": True}, {"_id": 0})
    if plan:
        top_areas = []
        for area, alloc in (plan.get("allocations", {}).get("weekday", {})).items():
            if isinstance(alloc, dict) and alloc.get("hours", 0) > 0:
                top_areas.append(f"{area}: {alloc['hours']}h")
        if top_areas:
            parts.append(f"LIFESTYLE PLAN ({plan['name']}): {', '.join(top_areas[:6])}")

    # Recent decisions
    decisions = await db.decisions.find({"user_id": user_id}, {"_id": 0, "title": 1, "status": 1}).sort("updated_at", -1).to_list(5)
    if decisions:
        d_text = "\n".join([f"- {d.get('title','')} [{d.get('status','')}]" for d in decisions])
        parts.append(f"RECENT DECISIONS:\n{d_text}")

    # Active conflicts
    conflicts = await db.conflict_breaker_sessions.find(
        {"user_id": user_id, "status": {"$in": ["draft", "prepared"]}}, {"_id": 0}
    ).to_list(5)
    if conflicts:
        c_text = "\n".join([f"- {c.get('title','')} (stakes:{c.get('stakes_score','?')}/10)" for c in conflicts])
        parts.append(f"ACTIVE CONFLICT SESSIONS:\n{c_text}")

    # AALA summary
    aala = await db.aala_records.find({"user_id": user_id}, {"_id": 0}).to_list(20)
    if aala:
        assets = sum(a.get("value", 0) for a in aala if a.get("type") == "asset")
        liabilities = sum(a.get("value", 0) for a in aala if a.get("type") == "liability")
        parts.append(f"AALA: Total Assets={assets}, Total Liabilities={liabilities}, Net Worth={assets - liabilities}")

    # CLD insights (module CLDs)
    clds = await db.cld_diagrams.find(
        {"user_id": user_id, "module_type": {"$exists": True}}, {"_id": 0}
    ).to_list(5)
    if clds:
        cld_text = "\n".join([
            f"- {c.get('module_type','')} CLD: {len(c.get('nodes',[]))} factors, {len(c.get('links',[]))} connections"
            for c in clds
        ])
        parts.append(f"CLD DIAGRAMS:\n{cld_text}")

    return "\n\n".join(parts) if parts else "No data available yet. The user is new."


@router.post("/conversations/{conv_id}/message")
@limiter.limit(AI_LIMIT)
async def send_message(conv_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Send a message to the AI assistant and get a response."""
    body = await request.json()
    user_message = body.get("message", "").strip()
    if not user_message:
        raise HTTPException(400, "Message cannot be empty")

    # Get conversation
    conv = await db.ai_assistant_conversations.find_one(
        {"conversation_id": conv_id, "user_id": user["user_id"]}
    )
    if not conv:
        raise HTTPException(404, "Conversation not found")

    language = conv.get("language", "en")
    lang_name = SUPPORTED_LANGUAGES.get(language, "English")

    # Gather user context
    user_context = await _gather_user_context(user["user_id"])

    # Build conversation history
    messages = conv.get("messages", [])
    history = "\n".join([
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in messages[-10:]  # Last 10 messages for context
    ])

    # Generate AI response
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(500, "LLM key not configured")

    from emergentintegrations.llm.chat import LlmChat, UserMessage

    system_msg = f"""You are a personal advisor and life coach in the "View Dezider" app. You help users make better decisions, manage conflicts, achieve goals, and optimize their lifestyle.

RESPOND IN {lang_name.upper()} LANGUAGE. If the user writes in any language, still respond in {lang_name}.

You have access to the user's data across multiple life modules. Use this context to give personalized, actionable advice.

USER'S CURRENT CONTEXT:
{user_context}

GUIDELINES:
- Be warm, practical, and direct
- Reference specific items from their PNA, goals, conflicts, or lifestyle when relevant
- Suggest specific app tools when appropriate (Conflict Breaker, PNA, Goal Setter, CLD Engine, etc.)
- Keep responses concise but helpful (2-4 paragraphs max)
- Do not give medical, legal, or financial professional advice — recommend professionals when needed
- If user asks about CLD, explain how their factors are interconnected across modules
- If user seems stressed about conflicts, guide them toward the Conflict Breaker tool"""

    chat = LlmChat(
        api_key=api_key,
        session_id=f"ai_asst_{conv_id}_{uuid.uuid4().hex[:6]}",
        system_message=system_msg
    ).with_model("openai", "gpt-4.1-mini")

    prompt = user_message
    if history:
        prompt = f"Previous conversation:\n{history}\n\nUser's new message: {user_message}"

    try:
        resp = await chat.send_message(UserMessage(text=prompt))
        ai_response = resp.strip()
    except Exception as e:
        raise HTTPException(500, f"AI generation failed: {str(e)}")

    now = datetime.now(timezone.utc).isoformat()

    # Append messages
    new_msgs = [
        {"role": "user", "content": user_message, "timestamp": now},
        {"role": "assistant", "content": ai_response, "timestamp": now},
    ]

    await db.ai_assistant_conversations.update_one(
        {"conversation_id": conv_id},
        {
            "$push": {"messages": {"$each": new_msgs}},
            "$set": {"updated_at": now},
        }
    )

    # Auto-set title from first message
    if len(messages) == 0:
        title = user_message[:60] + ("..." if len(user_message) > 60 else "")
        await db.ai_assistant_conversations.update_one(
            {"conversation_id": conv_id},
            {"$set": {"title": title}}
        )

    return {
        "user_message": user_message,
        "ai_response": ai_response,
        "language": language,
        "timestamp": now,
    }


@router.post("/quick-ask")
@limiter.limit(AI_LIMIT)
async def quick_ask(request: Request, user: dict = Depends(get_current_user)):
    """Quick one-shot question without creating a conversation."""
    body = await request.json()
    question = body.get("question", "").strip()
    language = body.get("language", "en")
    if not question:
        raise HTTPException(400, "Question cannot be empty")

    lang_name = SUPPORTED_LANGUAGES.get(language, "English")
    user_context = await _gather_user_context(user["user_id"])

    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(500, "LLM key not configured")

    from emergentintegrations.llm.chat import LlmChat, UserMessage

    chat = LlmChat(
        api_key=api_key,
        session_id=f"quick_{user['user_id']}_{uuid.uuid4().hex[:6]}",
        system_message=f"You are a personal advisor. Respond in {lang_name}. Be concise and practical.\n\nUser Context:\n{user_context}"
    ).with_model("openai", "gpt-4.1-mini")

    resp = await chat.send_message(UserMessage(text=question))
    return {"question": question, "answer": resp.strip(), "language": language}
