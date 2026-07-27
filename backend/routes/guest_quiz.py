"""
Guest Decision-Style Quiz (marketing HOOK) — public endpoints
==============================================================
Rationale (user request): "make the quiz a marketing HOOK by taking it
outside on Guest mode — from the current /profile?startQuiz=self to
https://quiz.jelcos.ai. A guest user must Google sign-in / Email sign-in
into our Jelcos AI system, to view the result, download as PDF, share to
his/her Email & WhatsApp."

Design:
  1. GET  /quiz/questions          — same list as authenticated endpoint,
                                     but public (no auth required).
  2. POST /quiz/guest-submit       — records answers + optional lead info,
                                     returns a short-lived `quiz_token`
                                     (opaque uuid) but WITHOUT the result.
  3. POST /quiz/claim              — auth-required. Trades a quiz_token for
                                     a real assessment row owned by the
                                     signed-in user, returning the full
                                     result (dominant_mode, mode_scores).
                                     After this call the token is burned.

Guest submissions live in `quiz_guest_submissions` and auto-expire after
14 days (TTL index created lazily).
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.database import db
from core.auth import get_current_user
from models.decisions_models import (
    ASSESSMENT_QUESTIONS, ModeAssessmentResult,
)

router = APIRouter(prefix="/quiz", tags=["Guest Quiz"])


# ─────────────────────── lazy TTL index ─────────────────────────
_ttl_ensured = False


async def _ensure_ttl_index() -> None:
    global _ttl_ensured
    if _ttl_ensured:
        return
    try:
        await db.quiz_guest_submissions.create_index(
            "expires_at", expireAfterSeconds=0
        )
        _ttl_ensured = True
    except Exception:
        # Best effort — never block the request.
        pass


# ─────────────────────── request models ─────────────────────────

class GuestQuizSubmit(BaseModel):
    answers: Dict[str, int]
    name: Optional[str] = None
    email: Optional[str] = None
    whatsapp: Optional[str] = None
    gender: Optional[str] = None


class ClaimBody(BaseModel):
    quiz_token: str


# ─────────────────────── endpoints ──────────────────────────────

@router.get("/questions")
async def guest_get_questions():
    """Public — no auth. Returns the same set used inside the app."""
    return {"questions": ASSESSMENT_QUESTIONS}


@router.post("/guest-submit")
async def guest_submit(body: GuestQuizSubmit):
    """Stores a guest quiz submission. Returns a short-lived token that must
    be redeemed after sign-in via /quiz/claim to reveal the result."""
    if not body.answers or len(body.answers) < len(ASSESSMENT_QUESTIONS) // 2:
        # Encourage complete answers — hook is meant to give a real result.
        raise HTTPException(400, "Please answer all questions to see your result.")

    await _ensure_ttl_index()

    token = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=14)

    doc: Dict[str, Any] = {
        "quiz_token": token,
        "answers": body.answers,
        "name": (body.name or "").strip() or None,
        "email": (body.email or "").strip().lower() or None,
        "whatsapp": (body.whatsapp or "").strip() or None,
        "gender": (body.gender or "").strip() or None,
        "created_at": now,
        "expires_at": expires_at,
        "claimed": False,
    }
    await db.quiz_guest_submissions.insert_one(doc)
    return {"quiz_token": token, "expires_in_days": 14}


@router.post("/claim")
async def guest_claim(body: ClaimBody, user: dict = Depends(get_current_user)):
    """Auth-required. Trades a quiz_token for a real ModeAssessmentResult
    row owned by the signed-in user, and returns the full result payload
    (dominant_mode, mode_scores) so the app can render the result screen."""
    sub = await db.quiz_guest_submissions.find_one({"quiz_token": body.quiz_token}, {"_id": 0})
    if not sub:
        raise HTTPException(404, "Quiz token not found or expired. Please retake the quiz.")
    if sub.get("claimed"):
        raise HTTPException(409, "This quiz has already been claimed.")

    answers = sub.get("answers") or {}
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

    result = ModeAssessmentResult(
        user_id=user["user_id"], answers=answers,
        dominant_mode=dominant_mode, mode_scores=mode_scores,
        # Everyone claims the guest quiz *for themselves* — that's the whole
        # point of the marketing hook. Names/gender/email from the guest form
        # are just lead-capture metadata; we store them alongside for future
        # marketing use in a separate `quiz_leads` collection.
        subject_type="self",
    )
    await db.assessments.insert_one(result.dict())

    # Persist lead data (email/whatsapp/gender/name) — never blocks.
    try:
        await db.quiz_leads.update_one(
            {"user_id": user["user_id"]},
            {"$set": {
                "user_id": user["user_id"],
                "name": sub.get("name"),
                "email": sub.get("email"),
                "whatsapp": sub.get("whatsapp"),
                "gender": sub.get("gender"),
                "source": "quiz.jelcos.ai",
                "claimed_at": datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    except Exception:
        pass

    # Mark token as claimed (retain doc until TTL removes it for auditing).
    await db.quiz_guest_submissions.update_one(
        {"quiz_token": body.quiz_token},
        {"$set": {"claimed": True, "claimed_by": user["user_id"],
                  "assessment_id": result.id}},
    )

    return {
        "id": result.id,
        "dominant_mode": dominant_mode,
        "mode_scores": mode_scores,
        "subject_type": "self",
    }
