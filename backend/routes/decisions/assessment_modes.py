"""Decision-mode self-assessment routes (emotional / logical / intuitive / consciousness)."""

import os
import uuid
from fastapi import APIRouter, Depends, HTTPException
from core.database import db
from core.auth import get_current_user
from core import ai_wallet
from models.decisions_models import ModeAssessmentCreate, ModeAssessmentResult, ASSESSMENT_QUESTIONS

router = APIRouter(tags=["Decisions"])

AI_INSIGHT_COST = 8  # flat credits per personalized AI insight (≤ 10)

_MODE_LABELS = {
    "emotional": "Emotional", "logical": "Logical",
    "intuitive": "Intuitive", "consciousness": "Consciousness",
}


@router.get("/assessment/questions")
async def get_assessment_questions():
    return {"questions": ASSESSMENT_QUESTIONS}


@router.post("/assessment", response_model=dict)
async def submit_assessment(assessment: ModeAssessmentCreate, user: dict = Depends(get_current_user)):
    answers = assessment.answers
    mode_scores = {"emotional": 0.0, "logical": 0.0, "intuitive": 0.0, "consciousness": 0.0}
    mode_counts = {"emotional": 0, "logical": 0, "intuitive": 0, "consciousness": 0}
    for question in ASSESSMENT_QUESTIONS:
        if question["id"] in answers:
            mode = question["mode"]
            mode_scores[mode] += answers[question["id"]]
            mode_counts[mode] += 1
    for mode in mode_scores:
        if mode_counts[mode] > 0:
            mode_scores[mode] = round(mode_scores[mode] / mode_counts[mode], 2)
    dominant_mode = max(mode_scores, key=mode_scores.get)
    subject_type = "other" if (assessment.subject_type == "other") else "self"
    result = ModeAssessmentResult(
        user_id=user["user_id"], answers=answers, dominant_mode=dominant_mode,
        mode_scores=mode_scores,
        subject_type=subject_type,
        subject_name=(assessment.subject_name or "").strip() or None if subject_type == "other" else None,
        subject_whatsapp=(assessment.subject_whatsapp or "").strip() or None if subject_type == "other" else None,
    )
    await db.assessments.insert_one(result.dict())
    return {"id": result.id, "dominant_mode": dominant_mode, "mode_scores": mode_scores,
            "subject_type": subject_type, "subject_name": result.subject_name,
            "subject_whatsapp": result.subject_whatsapp}


@router.get("/assessment/history")
async def get_assessment_history(user: dict = Depends(get_current_user)):
    assessments = await db.assessments.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return assessments


@router.post("/assessment/{assessment_id}/ai-insight")
async def generate_ai_insight(assessment_id: str, user: dict = Depends(get_current_user)):
    """Generate a personalized AI insight for a Decision-Making-Style result.
    Metered: deducts a flat AI_INSIGHT_COST from the user's AI credits."""
    a = await db.assessments.find_one({"id": assessment_id, "user_id": user["user_id"]}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Assessment not found")
    if a.get("ai_insight"):
        return {"ai_insight": a["ai_insight"], "credits_charged": 0, "cached": True}

    # Gate on balance
    try:
        await ai_wallet.ensure_can_spend(user["user_id"])
    except Exception:
        raise HTTPException(402, "You're out of AI credits. Add balance from Profile → Universal Key.")

    scores = a.get("mode_scores", {})
    scores_txt = ", ".join(f"{_MODE_LABELS.get(k, k)} {v}/5" for k, v in scores.items())
    who = "this person" if a.get("subject_type") == "other" else "the user"
    name = a.get("subject_name") or ("this person" if a.get("subject_type") == "other" else "you")
    prompt = (
        f"A Decision-Making-Style assessment was completed for {name}. "
        f"The dominant style is '{_MODE_LABELS.get(a.get('dominant_mode'), a.get('dominant_mode'))}'. "
        f"Average scores (1-5) across styles: {scores_txt}. "
        f"Write a warm, specific, personalized insight (~140-180 words) about {who}'s decision-making style: "
        f"1) what this blend means in practice, 2) two concrete strengths, 3) two blind spots to watch, "
        f"4) one practical tip to make better decisions. Use second person if it's the user, third person if about someone else. "
        f"Plain encouraging language, no markdown headers."
    )

    from core.llm_compat import LlmChat, UserMessage
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(500, "LLM key not configured")
    chat = LlmChat(
        api_key=api_key,
        session_id=f"dms_{assessment_id}_{uuid.uuid4().hex[:8]}",
        system_message="You are an insightful decision coach. Be warm, concrete and concise.",
    ).with_model("openai", "gpt-4.1-mini")
    try:
        insight = (await chat.send_message(UserMessage(text=prompt))).strip()
    except Exception as e:
        from core.llm_errors import llm_error_to_http
        raise llm_error_to_http(e)

    charge = await ai_wallet.charge_credits(
        user["user_id"], AI_INSIGHT_COST, feature="dms_ai_insight",
        note="Decision-Making-Style AI insight",
    )
    await db.assessments.update_one(
        {"id": assessment_id, "user_id": user["user_id"]},
        {"$set": {"ai_insight": insight}},
    )
    return {"ai_insight": insight, "credits_charged": charge["charged"], "balance": charge["balance"]}
