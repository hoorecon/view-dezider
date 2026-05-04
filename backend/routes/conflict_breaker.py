"""
The Conflict Breaker — 9-Stage Crucial Conversation Preparation Engine
Inspired by the dialogue principles in "Crucial Conversations" by Patterson, Grenny, McMillan & Switzler.

Stages:
1. Is This a Crucial Conversation?
2. Start with Heart
3. Learn to Look
4. Make It Safe
5. Master My Story
6. Speak My Path
7. Explore Their Path
8. Move to Action
9. Follow-Up and Closure
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user
from core.rate_limiting import limiter, AI_LIMIT

router = APIRouter(prefix="/conflict-breaker", tags=["Conflict Breaker"])

# ═══════════════════════════════════════════════════════════════
# STAGE DEFINITIONS
# ═══════════════════════════════════════════════════════════════

STAGES = [
    {"number": 1, "id": "crucial_check", "name": "Is This a Crucial Conversation?", "icon": "alert-circle", "color": "#EF4444"},
    {"number": 2, "id": "start_with_heart", "name": "Start with Heart", "icon": "heart", "color": "#EC4899"},
    {"number": 3, "id": "learn_to_look", "name": "Learn to Look", "icon": "eye", "color": "#F59E0B"},
    {"number": 4, "id": "make_it_safe", "name": "Make It Safe", "icon": "shield-checkmark", "color": "#10B981"},
    {"number": 5, "id": "master_my_story", "name": "Master My Story", "icon": "book", "color": "#3B82F6"},
    {"number": 6, "id": "speak_my_path", "name": "Speak My Path", "icon": "megaphone", "color": "#8B5CF6"},
    {"number": 7, "id": "explore_their_path", "name": "Explore Their Path", "icon": "ear", "color": "#0EA5E9"},
    {"number": 8, "id": "move_to_action", "name": "Move to Action", "icon": "rocket", "color": "#F97316"},
    {"number": 9, "id": "followup_closure", "name": "Follow-Up and Closure", "icon": "checkmark-done-circle", "color": "#059669"},
]

SILENCE_PATTERNS = ["Avoiding", "Withdrawing", "Masking", "Sugarcoating", "Sarcasm", "Delaying", "Ghosting", "Silent resentment"]
VIOLENCE_PATTERNS = ["Controlling", "Labeling", "Attacking", "Interrupting", "Threatening", "Blaming", "Shaming", "Overstating", "Forcing conclusion"]
SAFETY_REPAIR_METHODS = ["apology", "contrasting", "crib", "none"]
DECISION_METHODS = ["command", "consult", "vote", "consensus", "unclear"]
CLEVER_STORY_TYPES = ["victim", "villain", "helpless", "none"]

ACKNOWLEDGMENT = (
    "This tool is inspired by the powerful dialogue principles popularized in the book "
    "\"Crucial Conversations: Tools for Talking When Stakes Are High\" by Kerry Patterson, "
    "Joseph Grenny, Ron McMillan, and Al Switzler. We offer gratitude and courtesy to the "
    "authors and the Crucial Conversations / VitalSmarts team. This app tool is an independent "
    "reflective implementation and is not an official certification, training, or replacement "
    "for the original book or official programs."
)


@router.get("/meta")
async def get_meta():
    """Return stage definitions, pattern lists, and acknowledgment."""
    return {
        "stages": STAGES,
        "silence_patterns": SILENCE_PATTERNS,
        "violence_patterns": VIOLENCE_PATTERNS,
        "safety_repair_methods": SAFETY_REPAIR_METHODS,
        "decision_methods": DECISION_METHODS,
        "clever_story_types": CLEVER_STORY_TYPES,
        "acknowledgment": ACKNOWLEDGMENT,
    }


# ═══════════════════════════════════════════════════════════════
# SESSION CRUD
# ═══════════════════════════════════════════════════════════════

@router.post("/sessions")
async def create_session(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    session_id = f"CB-{uuid.uuid4().hex[:10].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "session_id": session_id,
        "user_id": user["user_id"],
        "title": body.get("title", ""),
        "conversation_type": body.get("conversation_type", "prepare"),
        "other_party_role": body.get("other_party_role", ""),
        "current_stage": body.get("current_stage", 1),
        "status": body.get("status", "draft"),
        "created_at": now, "updated_at": now,
    }
    await db.conflict_breaker_sessions.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/sessions")
async def list_sessions(request: Request, user: dict = Depends(get_current_user)):
    q = {"user_id": user["user_id"]}
    if request.query_params.get("status"):
        q["status"] = request.query_params["status"]
    docs = await db.conflict_breaker_sessions.find(q, {"_id": 0}).sort("updated_at", -1).to_list(100)
    return docs


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user: dict = Depends(get_current_user)):
    doc = await db.conflict_breaker_sessions.find_one(
        {"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(404, "Session not found")
    return doc


@router.put("/sessions/{session_id}")
async def update_session(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    now = datetime.now(timezone.utc).isoformat()
    upd = {"updated_at": now}
    for f in ["title", "conversation_type", "other_party_role", "current_stage", "status"]:
        if f in body:
            upd[f] = body[f]
    r = await db.conflict_breaker_sessions.update_one(
        {"session_id": session_id, "user_id": user["user_id"]}, {"$set": upd}
    )
    if r.matched_count == 0:
        raise HTTPException(404, "Session not found")
    return await db.conflict_breaker_sessions.find_one({"session_id": session_id}, {"_id": 0})


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    r = await db.conflict_breaker_sessions.delete_one(
        {"session_id": session_id, "user_id": user["user_id"]}
    )
    if r.deleted_count == 0:
        raise HTTPException(404, "Session not found")
    # Cascade delete all related data
    for col_name in [
        "conflict_crucial_check", "conflict_motive_clarity", "conflict_safety_diagnosis",
        "conflict_story_map", "conflict_script_builder", "conflict_listening_plan",
        "conflict_action_plan", "conflict_journal", "conflict_followup_reminders",
    ]:
        await db[col_name].delete_many({"session_id": session_id, "user_id": user["user_id"]})
    return {"deleted": True}


# ═══════════════════════════════════════════════════════════════
# STAGE 1: IS THIS A CRUCIAL CONVERSATION?
# ═══════════════════════════════════════════════════════════════

@router.post("/sessions/{session_id}/crucial-check")
async def save_crucial_check(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    now = datetime.now(timezone.utc).isoformat()
    # Compute classification
    stakes = body.get("stakes_score", 5)
    emotion = body.get("emotion_score", 5)
    opinion_diff = body.get("opinion_difference_score", 5)
    rel_sens = body.get("relationship_sensitivity_score", 5)
    urgency = body.get("urgency_score", 5)
    avg = (stakes + emotion + opinion_diff + rel_sens + urgency) / 5

    if avg >= 8:
        classification = "High-Risk Crucial Conversation"
    elif avg >= 6:
        classification = "Crucial Conversation"
    elif avg >= 4:
        classification = "Sensitive Conversation"
    elif body.get("conversation_type") == "repair":
        classification = "Repair Conversation Needed"
    else:
        classification = "Normal Conversation"

    doc = {
        "session_id": session_id, "user_id": user["user_id"],
        "about": body.get("about", ""),
        "who_involved": body.get("who_involved", ""),
        "at_stake": body.get("at_stake", ""),
        "opinions_differ": body.get("opinions_differ", ""),
        "emotions_strong": body.get("emotions_strong", ""),
        "if_avoid": body.get("if_avoid", ""),
        "if_handle_poorly": body.get("if_handle_poorly", ""),
        "desired_result": body.get("desired_result", ""),
        "stakes_score": stakes,
        "emotion_score": emotion,
        "opinion_difference_score": opinion_diff,
        "relationship_sensitivity_score": rel_sens,
        "urgency_score": urgency,
        "classification": classification,
        "updated_at": now,
    }
    await db.conflict_crucial_check.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": doc, "$setOnInsert": {"created_at": now}}, upsert=True
    )
    # Update session stage
    await db.conflict_breaker_sessions.update_one(
        {"session_id": session_id}, {"$set": {"current_stage": 1, "updated_at": now}}
    )
    doc.pop("_id", None)
    return {**doc, "classification": classification}


@router.get("/sessions/{session_id}/crucial-check")
async def get_crucial_check(session_id: str, user: dict = Depends(get_current_user)):
    doc = await db.conflict_crucial_check.find_one(
        {"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    return doc or {}


# ═══════════════════════════════════════════════════════════════
# STAGE 2: START WITH HEART
# ═══════════════════════════════════════════════════════════════

@router.post("/sessions/{session_id}/motive-clarity")
async def save_motive_clarity(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "session_id": session_id, "user_id": user["user_id"],
        "want_for_self": body.get("want_for_self", ""),
        "want_for_other": body.get("want_for_other", ""),
        "want_for_relationship": body.get("want_for_relationship", ""),
        "want_for_project_or_family": body.get("want_for_project_or_family", ""),
        "result_not_to_damage": body.get("result_not_to_damage", ""),
        "am_i_trying_to": body.get("am_i_trying_to", ""),
        "ideal_behavior": body.get("ideal_behavior", ""),
        "sucker_choice_honesty_vs_peace": body.get("sucker_choice_honesty_vs_peace", ""),
        "sucker_choice_truth_vs_relationship": body.get("sucker_choice_truth_vs_relationship", ""),
        "sucker_choice_attack_vs_silence": body.get("sucker_choice_attack_vs_silence", ""),
        "what_i_want": body.get("what_i_want", ""),
        "what_i_do_not_want": body.get("what_i_do_not_want", ""),
        "and_statement": body.get("and_statement", ""),
        "updated_at": now,
    }
    await db.conflict_motive_clarity.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": doc, "$setOnInsert": {"created_at": now}}, upsert=True
    )
    await db.conflict_breaker_sessions.update_one(
        {"session_id": session_id}, {"$set": {"current_stage": 2, "updated_at": now}}
    )
    doc.pop("_id", None)
    return doc


@router.get("/sessions/{session_id}/motive-clarity")
async def get_motive_clarity(session_id: str, user: dict = Depends(get_current_user)):
    doc = await db.conflict_motive_clarity.find_one(
        {"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    return doc or {}


# ═══════════════════════════════════════════════════════════════
# STAGE 3: LEARN TO LOOK
# ═══════════════════════════════════════════════════════════════

@router.post("/sessions/{session_id}/safety-diagnosis")
async def save_safety_diagnosis(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "session_id": session_id, "user_id": user["user_id"],
        "visible_topic": body.get("visible_topic", ""),
        "hidden_emotional_issue": body.get("hidden_emotional_issue", ""),
        "my_direction": body.get("my_direction", ""),
        "their_direction": body.get("their_direction", ""),
        "body_signals": body.get("body_signals", ""),
        "emotion_rising": body.get("emotion_rising", ""),
        "behavior_showing": body.get("behavior_showing", ""),
        "user_pattern": body.get("user_pattern", "dialogue"),
        "user_subpatterns": body.get("user_subpatterns", []),
        "other_pattern": body.get("other_pattern", "unknown"),
        "other_subpatterns": body.get("other_subpatterns", []),
        "updated_at": now,
    }
    await db.conflict_safety_diagnosis.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": doc, "$setOnInsert": {"created_at": now}}, upsert=True
    )
    await db.conflict_breaker_sessions.update_one(
        {"session_id": session_id}, {"$set": {"current_stage": 3, "updated_at": now}}
    )
    doc.pop("_id", None)
    return doc


@router.get("/sessions/{session_id}/safety-diagnosis")
async def get_safety_diagnosis(session_id: str, user: dict = Depends(get_current_user)):
    doc = await db.conflict_safety_diagnosis.find_one(
        {"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    return doc or {}


# ═══════════════════════════════════════════════════════════════
# STAGE 4: MAKE IT SAFE (includes apology, contrasting, CRIB)
# ═══════════════════════════════════════════════════════════════

@router.post("/sessions/{session_id}/make-safe")
async def save_make_safe(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "session_id": session_id, "user_id": user["user_id"],
        "mutual_purpose_at_risk": body.get("mutual_purpose_at_risk", ""),
        "they_believe_i_care": body.get("they_believe_i_care", ""),
        "mutual_respect_at_risk": body.get("mutual_respect_at_risk", ""),
        "they_believe_i_respect": body.get("they_believe_i_respect", ""),
        "did_i_hurt": body.get("did_i_hurt", ""),
        "misunderstood_intention": body.get("misunderstood_intention", ""),
        "competing_purposes": body.get("competing_purposes", ""),
        "safety_repair_method": body.get("safety_repair_method", "none"),
        # Apology
        "apology_what_i_did": body.get("apology_what_i_did", ""),
        "apology_how_affected": body.get("apology_how_affected", ""),
        "apology_responsibility": body.get("apology_responsibility", ""),
        "apology_draft": body.get("apology_draft", ""),
        # Contrasting
        "contrast_they_wrongly_think": body.get("contrast_they_wrongly_think", ""),
        "contrast_i_actually_mean": body.get("contrast_i_actually_mean", ""),
        "contrast_dont_misunderstand": body.get("contrast_dont_misunderstand", ""),
        "contrast_want_to_clarify": body.get("contrast_want_to_clarify", ""),
        "contrasting_statement": body.get("contrasting_statement", ""),
        # CRIB
        "crib_what_i_ask": body.get("crib_what_i_ask", ""),
        "crib_why_i_want": body.get("crib_why_i_want", ""),
        "crib_what_they_ask": body.get("crib_what_they_ask", ""),
        "crib_why_they_want": body.get("crib_why_they_want", ""),
        "crib_higher_purpose": body.get("crib_higher_purpose", ""),
        "crib_new_option": body.get("crib_new_option", ""),
        "mutual_purpose_statement": body.get("mutual_purpose_statement", ""),
        "updated_at": now,
    }
    await db.conflict_make_safe.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": doc, "$setOnInsert": {"created_at": now}}, upsert=True
    )
    await db.conflict_breaker_sessions.update_one(
        {"session_id": session_id}, {"$set": {"current_stage": 4, "updated_at": now}}
    )
    doc.pop("_id", None)
    return doc


@router.get("/sessions/{session_id}/make-safe")
async def get_make_safe(session_id: str, user: dict = Depends(get_current_user)):
    doc = await db.conflict_make_safe.find_one(
        {"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    return doc or {}


# ═══════════════════════════════════════════════════════════════
# STAGE 5: MASTER MY STORY
# ═══════════════════════════════════════════════════════════════

@router.post("/sessions/{session_id}/story-map")
async def save_story_map(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "session_id": session_id, "user_id": user["user_id"],
        "what_i_saw_heard": body.get("what_i_saw_heard", ""),
        "observable_facts": body.get("observable_facts", ""),
        "verifiable_evidence": body.get("verifiable_evidence", ""),
        "what_they_said_did": body.get("what_they_said_did", ""),
        "meaning_i_added": body.get("meaning_i_added", ""),
        "assumed_motive": body.get("assumed_motive", ""),
        "judgment": body.get("judgment", ""),
        "label_used": body.get("label_used", ""),
        "emotion": body.get("emotion", ""),
        "emotional_intensity": body.get("emotional_intensity", 5),
        "intended_action": body.get("intended_action", ""),
        "moving_to": body.get("moving_to", ""),
        "will_action_help": body.get("will_action_help", ""),
        "clever_story_type": body.get("clever_story_type", "none"),
        "my_role_in_problem": body.get("my_role_in_problem", ""),
        "reasonable_person_reason": body.get("reasonable_person_reason", ""),
        "what_i_really_want": body.get("what_i_really_want", ""),
        "what_would_i_do": body.get("what_would_i_do", ""),
        "alternative_story": body.get("alternative_story", ""),
        "updated_at": now,
    }
    await db.conflict_story_map.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": doc, "$setOnInsert": {"created_at": now}}, upsert=True
    )
    await db.conflict_breaker_sessions.update_one(
        {"session_id": session_id}, {"$set": {"current_stage": 5, "updated_at": now}}
    )
    doc.pop("_id", None)
    return doc


@router.get("/sessions/{session_id}/story-map")
async def get_story_map(session_id: str, user: dict = Depends(get_current_user)):
    doc = await db.conflict_story_map.find_one(
        {"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    return doc or {}


# ═══════════════════════════════════════════════════════════════
# STAGE 6: SPEAK MY PATH (STATE)
# ═══════════════════════════════════════════════════════════════

@router.post("/sessions/{session_id}/script-builder")
async def save_script(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "session_id": session_id, "user_id": user["user_id"],
        "facts_to_begin": body.get("facts_to_begin", ""),
        "my_interpretation": body.get("my_interpretation", ""),
        "tentative_framing": body.get("tentative_framing", ""),
        "question_to_invite": body.get("question_to_invite", ""),
        "open_to_correction": body.get("open_to_correction", ""),
        "what_to_avoid": body.get("what_to_avoid", ""),
        "opening_statement": body.get("opening_statement", ""),
        "facts_statement": body.get("facts_statement", ""),
        "story_statement": body.get("story_statement", ""),
        "tentative_statement": body.get("tentative_statement", ""),
        "ask_statement": body.get("ask_statement", ""),
        "testing_invitation": body.get("testing_invitation", ""),
        "final_script": body.get("final_script", ""),
        "updated_at": now,
    }
    await db.conflict_script_builder.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": doc, "$setOnInsert": {"created_at": now}}, upsert=True
    )
    await db.conflict_breaker_sessions.update_one(
        {"session_id": session_id}, {"$set": {"current_stage": 6, "updated_at": now}}
    )
    doc.pop("_id", None)
    return doc


@router.get("/sessions/{session_id}/script-builder")
async def get_script(session_id: str, user: dict = Depends(get_current_user)):
    doc = await db.conflict_script_builder.find_one(
        {"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    return doc or {}


# ═══════════════════════════════════════════════════════════════
# STAGE 7: EXPLORE THEIR PATH (AMPP)
# ═══════════════════════════════════════════════════════════════

@router.post("/sessions/{session_id}/listening-plan")
async def save_listening_plan(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "session_id": session_id, "user_id": user["user_id"],
        "ask_question": body.get("ask_question", ""),
        "mirror_statement": body.get("mirror_statement", ""),
        "paraphrase_statement": body.get("paraphrase_statement", ""),
        "prime_statement": body.get("prime_statement", ""),
        "what_they_feel": body.get("what_they_feel", ""),
        "what_they_fear": body.get("what_they_fear", ""),
        "what_they_want": body.get("what_they_want", ""),
        "what_i_havent_understood": body.get("what_i_havent_understood", ""),
        "what_to_ask_before_responding": body.get("what_to_ask_before_responding", ""),
        "agree_points": body.get("agree_points", ""),
        "build_points": body.get("build_points", ""),
        "compare_points": body.get("compare_points", ""),
        "updated_at": now,
    }
    await db.conflict_listening_plan.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": doc, "$setOnInsert": {"created_at": now}}, upsert=True
    )
    await db.conflict_breaker_sessions.update_one(
        {"session_id": session_id}, {"$set": {"current_stage": 7, "updated_at": now}}
    )
    doc.pop("_id", None)
    return doc


@router.get("/sessions/{session_id}/listening-plan")
async def get_listening_plan(session_id: str, user: dict = Depends(get_current_user)):
    doc = await db.conflict_listening_plan.find_one(
        {"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    return doc or {}


# ═══════════════════════════════════════════════════════════════
# STAGE 8: MOVE TO ACTION
# ═══════════════════════════════════════════════════════════════

@router.post("/sessions/{session_id}/action-plan")
async def save_action_plan(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "session_id": session_id, "user_id": user["user_id"],
        "decision_method": body.get("decision_method", "unclear"),
        "final_decision": body.get("final_decision", ""),
        "owner": body.get("owner", ""),
        "task": body.get("task", ""),
        "deadline": body.get("deadline", ""),
        "support_required": body.get("support_required", ""),
        "resources_required": body.get("resources_required", ""),
        "who_informed": body.get("who_informed", ""),
        "who_must_agree": body.get("who_must_agree", ""),
        "who_must_execute": body.get("who_must_execute", ""),
        "success_measure": body.get("success_measure", ""),
        "followup_date": body.get("followup_date", ""),
        "risk_remaining": body.get("risk_remaining", ""),
        "unresolved_concerns": body.get("unresolved_concerns", ""),
        "updated_at": now,
    }
    await db.conflict_action_plan.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": doc, "$setOnInsert": {"created_at": now}}, upsert=True
    )
    await db.conflict_breaker_sessions.update_one(
        {"session_id": session_id}, {"$set": {"current_stage": 8, "updated_at": now}}
    )
    doc.pop("_id", None)
    return doc


@router.get("/sessions/{session_id}/action-plan")
async def get_action_plan(session_id: str, user: dict = Depends(get_current_user)):
    doc = await db.conflict_action_plan.find_one(
        {"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    return doc or {}


# ═══════════════════════════════════════════════════════════════
# STAGE 9: FOLLOW-UP AND CLOSURE
# ═══════════════════════════════════════════════════════════════

@router.post("/sessions/{session_id}/closure")
async def save_closure(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    now = datetime.now(timezone.utc).isoformat()
    # Journal entry
    journal_doc = {
        "session_id": session_id, "user_id": user["user_id"],
        "completed": body.get("completed", False),
        "unresolved_issue": body.get("unresolved_issue", ""),
        "both_understood": body.get("both_understood", ""),
        "anyone_unsafe": body.get("anyone_unsafe", ""),
        "followup_required": body.get("followup_required", False),
        "what_to_document": body.get("what_to_document", ""),
        "journal_content": body.get("journal_content", ""),
        "tags": body.get("tags", []),
        "resolved_status": body.get("resolved_status", "resolved"),
        "personal_learning": body.get("personal_learning", ""),
        "updated_at": now,
    }
    await db.conflict_journal.update_one(
        {"session_id": session_id, "user_id": user["user_id"]},
        {"$set": journal_doc, "$setOnInsert": {"created_at": now}}, upsert=True
    )
    # Reminder if needed
    if body.get("reminder_date"):
        reminder_doc = {
            "reminder_id": f"REM-{uuid.uuid4().hex[:8].upper()}",
            "session_id": session_id, "user_id": user["user_id"],
            "reminder_title": body.get("reminder_title", "Follow-up conversation"),
            "reminder_date": body.get("reminder_date", ""),
            "reminder_time": body.get("reminder_time", ""),
            "reminder_status": "pending",
            "notes": body.get("reminder_notes", ""),
            "created_at": now,
        }
        await db.conflict_followup_reminders.insert_one(reminder_doc)

    # Update session status
    final_status = body.get("resolved_status", "completed")
    await db.conflict_breaker_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"current_stage": 9, "status": final_status, "updated_at": now}}
    )
    journal_doc.pop("_id", None)
    return journal_doc


@router.get("/sessions/{session_id}/closure")
async def get_closure(session_id: str, user: dict = Depends(get_current_user)):
    doc = await db.conflict_journal.find_one(
        {"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    return doc or {}


# ═══════════════════════════════════════════════════════════════
# FULL SESSION DATA (all stages)
# ═══════════════════════════════════════════════════════════════

@router.get("/sessions/{session_id}/full")
async def get_full_session(session_id: str, user: dict = Depends(get_current_user)):
    """Get all stage data for a session in one call."""
    q = {"session_id": session_id, "user_id": user["user_id"]}
    p = {"_id": 0}
    session = await db.conflict_breaker_sessions.find_one(q, p)
    if not session:
        raise HTTPException(404, "Session not found")

    return {
        "session": session,
        "crucial_check": await db.conflict_crucial_check.find_one(q, p) or {},
        "motive_clarity": await db.conflict_motive_clarity.find_one(q, p) or {},
        "safety_diagnosis": await db.conflict_safety_diagnosis.find_one(q, p) or {},
        "make_safe": await db.conflict_make_safe.find_one(q, p) or {},
        "story_map": await db.conflict_story_map.find_one(q, p) or {},
        "script_builder": await db.conflict_script_builder.find_one(q, p) or {},
        "listening_plan": await db.conflict_listening_plan.find_one(q, p) or {},
        "action_plan": await db.conflict_action_plan.find_one(q, p) or {},
        "closure": await db.conflict_journal.find_one(q, p) or {},
        "reminders": await db.conflict_followup_reminders.find(q, p).to_list(20),
    }


# ═══════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# AI GENERATION — Across stages
# ═══════════════════════════════════════════════════════════════

async def _ai_generate(prompt: str, session_id: str = "") -> str:
    """Helper to call LLM for Conflict Breaker AI features."""
    import os
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(500, "LLM key not configured")
    chat = LlmChat(
        api_key=api_key,
        session_id=f"cb_{session_id}_{uuid.uuid4().hex[:8]}",
        system_message="You are a mature, calm dialogue coach helping users prepare for crucial conversations. Be direct, practical, non-blaming. Not therapeutic diagnosis."
    ).with_model("openai", "gpt-4.1-mini")
    try:
        resp = await chat.send_message(UserMessage(text=prompt))
    except Exception as e:
        from core.llm_errors import llm_error_to_http
        raise llm_error_to_http(e)
    return resp.strip()


@router.post("/sessions/{session_id}/ai-generate/{stage}")
@limiter.limit(AI_LIMIT)
async def ai_generate_for_stage(session_id: str, stage: str, request: Request, user: dict = Depends(get_current_user)):
    """Generate AI insights for a specific stage using all data collected so far."""
    q = {"session_id": session_id, "user_id": user["user_id"]}
    p = {"_id": 0}
    session = await db.conflict_breaker_sessions.find_one(q, p)
    if not session:
        raise HTTPException(404, "Session not found")

    # Gather context from all stages
    ctx = {
        "session": session,
        "crucial_check": await db.conflict_crucial_check.find_one(q, p) or {},
        "motive": await db.conflict_motive_clarity.find_one(q, p) or {},
        "safety": await db.conflict_safety_diagnosis.find_one(q, p) or {},
        "make_safe": await db.conflict_make_safe.find_one(q, p) or {},
        "story": await db.conflict_story_map.find_one(q, p) or {},
        "script": await db.conflict_script_builder.find_one(q, p) or {},
        "listening": await db.conflict_listening_plan.find_one(q, p) or {},
        "action": await db.conflict_action_plan.find_one(q, p) or {},
        "closure": await db.conflict_journal.find_one(q, p) or {},
    }

    base = (
        f"Conversation: {ctx['crucial_check'].get('about', ctx['session'].get('title',''))}\n"
        f"Other party: {ctx['crucial_check'].get('who_involved', ctx['session'].get('other_party_role',''))}\n"
        f"Stakes: {ctx['crucial_check'].get('stakes_score', '?')}/10, "
        f"Emotion: {ctx['crucial_check'].get('emotion_score', '?')}/10, "
        f"Opinion diff: {ctx['crucial_check'].get('opinion_difference_score', '?')}/10\n"
        f"Desired result: {ctx['crucial_check'].get('desired_result', '')}\n"
    )

    prompts = {
        "crucial_check": (
            f"You are a dialogue coach. Based on this situation, classify the conversation and give guidance.\n{base}\n"
            f"At stake: {ctx['crucial_check'].get('at_stake', '')}\n"
            f"If avoided: {ctx['crucial_check'].get('if_avoid', '')}\n"
            f"If handled poorly: {ctx['crucial_check'].get('if_handle_poorly', '')}\n\n"
            "Provide:\n1. Classification (Normal / Sensitive / Crucial / High-Risk Crucial / Repair Needed)\n"
            "2. Why this classification\n3. Key preparation advice (2-3 sentences)\n"
            "Keep it direct, calm, non-preachy. No therapeutic diagnosis."
        ),
        "motive_clarity": (
            f"You are a dialogue coach helping clarify true motive before a difficult conversation.\n{base}\n"
            f"Want for self: {ctx['motive'].get('want_for_self', '')}\n"
            f"Want for other: {ctx['motive'].get('want_for_other', '')}\n"
            f"Want for relationship: {ctx['motive'].get('want_for_relationship', '')}\n"
            f"What I want: {ctx['motive'].get('what_i_want', '')}\n"
            f"What I don't want: {ctx['motive'].get('what_i_do_not_want', '')}\n\n"
            "Generate:\n1. True motive statement (1 sentence)\n"
            "2. Warning if unhealthy motive detected (win/punish/prove/escape/save face)\n"
            "3. An 'AND statement' that combines what they want AND don't want\n"
            "Example: 'I want accountability AND relationship safety.'\n"
            "Keep tone mature, leadership-oriented."
        ),
        "safety_diagnosis": (
            f"You are a dialogue coach analyzing conversation safety patterns.\n{base}\n"
            f"Visible topic: {ctx['safety'].get('visible_topic', '')}\n"
            f"Hidden emotional issue: {ctx['safety'].get('hidden_emotional_issue', '')}\n"
            f"User pattern: {ctx['safety'].get('user_pattern', '')} ({', '.join(ctx['safety'].get('user_subpatterns', []))})\n"
            f"Other person pattern: {ctx['safety'].get('other_pattern', '')} ({', '.join(ctx['safety'].get('other_subpatterns', []))})\n"
            f"Body signals: {ctx['safety'].get('body_signals', '')}\n"
            f"Emotion rising: {ctx['safety'].get('emotion_rising', '')}\n\n"
            "Generate:\n1. Current conversation risk assessment\n"
            "2. User's stress pattern analysis\n"
            "3. Other person's possible safety reaction\n"
            "4. Recommended pause instruction\n"
            "Be direct, calm. Not preachy."
        ),
        "make_safe": (
            f"You are a dialogue coach helping restore safety.\n{base}\n"
            f"Repair method chosen: {ctx['make_safe'].get('safety_repair_method', '')}\n"
            f"Mutual purpose at risk: {ctx['make_safe'].get('mutual_purpose_at_risk', '')}\n"
            f"Mutual respect at risk: {ctx['make_safe'].get('mutual_respect_at_risk', '')}\n"
            f"Did I hurt them: {ctx['make_safe'].get('did_i_hurt', '')}\n"
            f"Apology draft input: {ctx['make_safe'].get('apology_draft', '')}\n"
            f"Contrasting input: do not mean={ctx['make_safe'].get('contrast_they_wrongly_think', '')}, "
            f"do mean={ctx['make_safe'].get('contrast_i_actually_mean', '')}\n"
            f"CRIB: I ask={ctx['make_safe'].get('crib_what_i_ask','')}, They ask={ctx['make_safe'].get('crib_what_they_ask','')}\n\n"
            "Generate based on the repair method chosen:\n"
            "- If apology: A sincere apology draft\n"
            "- If contrasting: A 'I do not mean... I do mean...' statement\n"
            "- If crib: Mutual Purpose statement + win-win options\n"
            "Keep it genuine, not corporate-speak."
        ),
        "story_map": (
            f"You are a dialogue coach helping separate facts from stories.\n{base}\n"
            f"What I saw/heard: {ctx['story'].get('what_i_saw_heard', '')}\n"
            f"Observable facts: {ctx['story'].get('observable_facts', '')}\n"
            f"Meaning I added: {ctx['story'].get('meaning_i_added', '')}\n"
            f"Assumed motive: {ctx['story'].get('assumed_motive', '')}\n"
            f"Judgment: {ctx['story'].get('judgment', '')}\n"
            f"Label used: {ctx['story'].get('label_used', '')}\n"
            f"Emotion: {ctx['story'].get('emotion', '')} (intensity: {ctx['story'].get('emotional_intensity', '?')})\n"
            f"Clever story type: {ctx['story'].get('clever_story_type', '')}\n"
            f"My role: {ctx['story'].get('my_role_in_problem', '')}\n\n"
            "Generate:\n1. Facts only (stripped of interpretation)\n"
            "2. Story being told\n3. Possible alternative story\n"
            "4. Emotional driver\n5. Healthier interpretation\n"
            "6. Recommended conversation opening line\n"
            "Do not blame, do not diagnose. Be calm, factual."
        ),
        "script_builder": (
            f"You are a dialogue coach building a respectful conversation script.\n{base}\n"
            f"Facts to begin: {ctx['script'].get('facts_to_begin', '')}\n"
            f"My interpretation: {ctx['script'].get('my_interpretation', '')}\n"
            f"Tentative framing: {ctx['script'].get('tentative_framing', '')}\n"
            f"Invite their view: {ctx['script'].get('question_to_invite', '')}\n"
            f"What to avoid: {ctx['script'].get('what_to_avoid', '')}\n\n"
            f"Context from earlier stages:\n"
            f"True motive: {ctx['motive'].get('want_for_self', '')} AND {ctx['motive'].get('want_for_relationship', '')}\n"
            f"Facts: {ctx['story'].get('observable_facts', '')}\n\n"
            "Generate a STATE conversation script:\n"
            "1. Opening safety sentence\n2. Facts statement\n"
            "3. My concern (tentative)\n4. Invitation to respond\n"
            "5. Respectful closing\n\n"
            "RULES: No blaming. No threats. No sarcasm. If user wrote harsh language, rewrite into respectful, factual, tentative language."
        ),
        "listening_plan": (
            f"You are a dialogue coach building a listening plan.\n{base}\n"
            f"What they might feel: {ctx['listening'].get('what_they_feel', '')}\n"
            f"What they might fear: {ctx['listening'].get('what_they_fear', '')}\n"
            f"What they might want: {ctx['listening'].get('what_they_want', '')}\n"
            f"What I haven't understood: {ctx['listening'].get('what_i_havent_understood', '')}\n\n"
            "Generate AMPP listening tools:\n"
            "1. Ask question (to understand their view)\n"
            "2. Mirror statement (reflect their emotion)\n"
            "3. Paraphrase draft (restate what they said)\n"
            "4. Prime statement (gently offer possible concern)\n"
            "5. Agree-Build-Compare response template\n"
            "Keep it natural, not scripted-sounding."
        ),
        "action_plan": (
            f"You are a dialogue coach converting conversation into action.\n{base}\n"
            f"Decision method: {ctx['action'].get('decision_method', '')}\n"
            f"Final decision: {ctx['action'].get('final_decision', '')}\n"
            f"Owner: {ctx['action'].get('owner', '')}\n"
            f"Task: {ctx['action'].get('task', '')}\n"
            f"Deadline: {ctx['action'].get('deadline', '')}\n"
            f"Follow-up date: {ctx['action'].get('followup_date', '')}\n"
            f"Unresolved: {ctx['action'].get('unresolved_concerns', '')}\n\n"
            "Generate a clear, formatted Action Agreement:\n"
            "Decision | Owner | Task | Deadline | Support | Follow-up | Success Measure | Unresolved"
        ),
        "report": (
            f"You are generating a Conflict Breakthrough Report.\n\n"
            f"SESSION: {ctx['session'].get('title', '')}\n"
            f"TYPE: {ctx['session'].get('conversation_type', '')}\n{base}\n"
            f"CLASSIFICATION: {ctx['crucial_check'].get('classification', '')}\n"
            f"TRUE MOTIVE: {ctx['motive'].get('want_for_self', '')} AND {ctx['motive'].get('want_for_relationship', '')}\n"
            f"PATTERN: {ctx['safety'].get('user_pattern', '')} / {ctx['safety'].get('other_pattern', '')}\n"
            f"SAFETY REPAIR: {ctx['make_safe'].get('safety_repair_method', '')}\n"
            f"FACTS: {ctx['story'].get('observable_facts', '')}\n"
            f"STORY: {ctx['story'].get('meaning_i_added', '')}\n"
            f"EMOTION: {ctx['story'].get('emotion', '')} ({ctx['story'].get('emotional_intensity', '')})\n"
            f"SCRIPT: {ctx['script'].get('final_script', '')}\n"
            f"DECISION: {ctx['action'].get('final_decision', '')}\n"
            f"LEARNING: {ctx['closure'].get('personal_learning', '')}\n\n"
            "Generate a comprehensive Conflict Breakthrough Report with these sections:\n"
            "1. Conversation Summary\n2. Why This Is a Crucial Conversation\n"
            "3. What I Really Want\n4. My Silence/Violence Pattern\n"
            "5. Other Person's Possible Safety Concern\n6. Facts vs Story\n"
            "7. Emotional Driver\n8. Safety Repair Needed\n"
            "9. Conversation Script\n10. Listening Plan\n"
            "11. Mutual Purpose\n12. Action Agreement\n"
            "13. Follow-Up Plan\n14. Personal Learning\n"
            "15. One-Line Commitment\n\n"
            "Tone: Direct, calm, mature, non-blaming, practical. Not therapeutic diagnosis."
        ),
    }

    if stage not in prompts:
        raise HTTPException(400, f"Invalid stage. Use: {list(prompts.keys())}")

    ai_text = await _ai_generate(prompts[stage], session_id)

    # Store AI output in the session
    await db.conflict_breaker_sessions.update_one(
        {"session_id": session_id},
        {"$set": {f"ai_{stage}": ai_text, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    return {"stage": stage, "ai_output": ai_text}


@router.get("/dashboard")
async def cb_dashboard(user: dict = Depends(get_current_user)):
    sessions = await db.conflict_breaker_sessions.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("updated_at", -1).to_list(100)
    total = len(sessions)
    by_status = {}
    for s in sessions:
        st = s.get("status", "draft")
        by_status[st] = by_status.get(st, 0) + 1
    reminders = await db.conflict_followup_reminders.find(
        {"user_id": user["user_id"], "reminder_status": "pending"}, {"_id": 0}
    ).sort("reminder_date", 1).to_list(10)
    return {
        "total_sessions": total,
        "by_status": by_status,
        "recent": sessions[:5],
        "pending_reminders": reminders,
    }
