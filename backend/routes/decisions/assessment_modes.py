"""Decision-mode self-assessment routes (emotional / logical / intuitive / awareness)."""

from fastapi import APIRouter, Depends
from core.database import db
from core.auth import get_current_user
from models.decisions_models import ModeAssessmentCreate, ModeAssessmentResult, ASSESSMENT_QUESTIONS

router = APIRouter(tags=["Decisions"])


@router.get("/assessment/questions")
async def get_assessment_questions():
    return {"questions": ASSESSMENT_QUESTIONS}


@router.post("/assessment", response_model=dict)
async def submit_assessment(assessment: ModeAssessmentCreate, user: dict = Depends(get_current_user)):
    answers = assessment.answers
    mode_scores = {"emotional": 0.0, "logical": 0.0, "intuitive": 0.0, "awareness": 0.0}
    mode_counts = {"emotional": 0, "logical": 0, "intuitive": 0, "awareness": 0}
    for question in ASSESSMENT_QUESTIONS:
        if question["id"] in answers:
            mode = question["mode"]
            mode_scores[mode] += answers[question["id"]]
            mode_counts[mode] += 1
    for mode in mode_scores:
        if mode_counts[mode] > 0:
            mode_scores[mode] = round(mode_scores[mode] / mode_counts[mode], 2)
    dominant_mode = max(mode_scores, key=mode_scores.get)
    result = ModeAssessmentResult(user_id=user["user_id"], answers=answers, dominant_mode=dominant_mode, mode_scores=mode_scores)
    await db.assessments.insert_one(result.dict())
    return {"id": result.id, "dominant_mode": dominant_mode, "mode_scores": mode_scores}


@router.get("/assessment/history")
async def get_assessment_history(user: dict = Depends(get_current_user)):
    assessments = await db.assessments.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(10)
    return assessments
