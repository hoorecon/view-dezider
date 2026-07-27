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
        subject_email=(assessment.subject_email or "").strip() or None if subject_type == "other" else None,
        subject_gender=(assessment.subject_gender or "").strip() or None if subject_type == "other" else None,
    )
    await db.assessments.insert_one(result.dict())
    return {"id": result.id, "dominant_mode": dominant_mode, "mode_scores": mode_scores,
            "subject_type": subject_type, "subject_name": result.subject_name,
            "subject_whatsapp": result.subject_whatsapp,
            "subject_email": result.subject_email,
            "subject_gender": result.subject_gender}


@router.get("/assessment/history")
async def get_assessment_history(user: dict = Depends(get_current_user)):
    assessments = await db.assessments.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return assessments


@router.get("/assessment/{assessment_id}/report.pdf")
async def assessment_report_pdf(assessment_id: str, user: dict = Depends(get_current_user)):
    """Owner download of a Decision-Making-Style result as a branded PDF
    (reuses the shared reportlab engine — same as decision reports)."""
    from fastapi.responses import Response
    from datetime import datetime, timezone
    from routes.decision_reports import (
        _load_decision, _build_pdf, _pdf_payload_for_assessment,
        _user_timezone, _format_local,
    )
    from routes.app_appearance import get_app_logo
    info = await _load_decision("assessment", assessment_id, user["user_id"])
    payload = _pdf_payload_for_assessment(info["raw"])
    payload["module_label"] = "Decision-Making Style"
    tzname = await _user_timezone(user["user_id"])
    payload["generated_at"] = _format_local(datetime.now(timezone.utc), tzname)
    logo = await get_app_logo()
    pdf = _build_pdf(payload, logo_data_url=logo)
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="jelcos_decision_style_{assessment_id[:8]}.pdf"'},
    )


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
    # Convert 1-5 raw scores into a user-friendly percentage so the prompt
    # (and hence the generated insight) speaks in "93%" / "27%" rather than
    # confusing "4.67 / 1.33" numbers.
    def _pct(v):
        try:
            return int(round(float(v) * 20))
        except Exception:
            return 0
    scores_txt = ", ".join(f"{_MODE_LABELS.get(k, k)} {_pct(v)}%" for k, v in scores.items())
    who = "this person" if a.get("subject_type") == "other" else "the user"
    name = a.get("subject_name") or ("this person" if a.get("subject_type") == "other" else "you")
    prompt = (
        f"A Decision-Making-Style assessment was completed for {name}. "
        f"The dominant style is '{_MODE_LABELS.get(a.get('dominant_mode'), a.get('dominant_mode'))}'. "
        f"Scores by style (as percentages, 0-100%): {scores_txt}. "
        f"Write a warm, specific, personalized insight (~140-180 words) about {who}'s decision-making style. "
        f"Rules — (a) ALWAYS refer to scores as percentages (e.g. 93%, 27%). NEVER use raw 1-5 numbers like 4.67 or 1.33. "
        f"(b) Cover: 1) what this blend means in practice, 2) two concrete strengths, "
        f"3) two blind spots to watch, 4) one practical tip to make better decisions. "
        f"Use second person if it's the user, third person if about someone else. "
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
