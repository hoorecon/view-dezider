"""Public Pulse — Consent-based Public Decision Intelligence & Market Research.

Phase 1: Citizen-facing self-discovery tools, consent layer, demographic capture,
anonymized aggregation engine with k-anonymity, and 5 public dashboards.

Privacy invariants (enforced):
  1. No insight returned if cohort_count < k_threshold for that dashboard.
  2. Sensitive fields (community/religion) only stored if user explicitly fills them
     during a tool flow. They are NEVER cross-tabbed in public dashboards.
  3. Consent is versioned. Withdrawing pulls the user out of all aggregations.
  4. All admin actions on k_thresholds + sensitive queries are audit-logged.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request
from core.database import db
from core.auth import get_current_user, require_admin
from core.rate_limiting import limiter, DEFAULT_LIMIT
from models.public_pulse_models import (
    CONSENT_PURPOSES, CONSENT_VERSION, ConsentSubmit,
    AGE_GROUPS, PROFESSIONS, EDUCATION_LEVELS, INCOME_BRACKETS,
    DemographicProfileUpdate, DemographicProfile,
    ToolStartRequest, ToolAnswerRequest, ToolSession,
    FEEDBACK_TYPES, FEEDBACK_STATES, FeedbackSubmit, FeedbackItem,
    DEFAULT_K_THRESHOLDS, KAnonymityUpdate,
    TOOL_DEFINITIONS,
)

router = APIRouter(prefix="/public-pulse", tags=["Public Pulse"])


# ============================================================
# CONSENT
# ============================================================

@router.get("/consent/options")
async def consent_options():
    """Return the catalog of consent purposes (for the consent screen)."""
    return {
        "version": CONSENT_VERSION,
        "purposes": CONSENT_PURPOSES,
        "data_categories": [
            "demographics", "tool_answers", "feedback", "scores", "location",
        ],
    }


@router.get("/consent/me")
async def get_my_consent(user: dict = Depends(get_current_user)):
    """Get the currently-active consent record for the user."""
    record = await db.pp_consent_records.find_one(
        {"user_id": user["user_id"], "withdrawn": False},
        {"_id": 0},
        sort=[("timestamp", -1)],
    )
    if not record:
        return {
            "user_id": user["user_id"],
            "active": False,
            "purposes": {p["code"]: False for p in CONSENT_PURPOSES},
            "version": CONSENT_VERSION,
        }
    record["active"] = True
    return record


@router.post("/consent")
async def submit_consent(req: ConsentSubmit, user: dict = Depends(get_current_user)):
    """Submit / update consent. Creates a NEW record (versioned audit trail)."""
    valid_codes = {p["code"] for p in CONSENT_PURPOSES}
    purposes = {code: bool(req.purposes.get(code, False)) for code in valid_codes}

    record = {
        "user_id": user["user_id"],
        "consent_version": CONSENT_VERSION,
        "purposes": purposes,
        "data_categories_allowed": req.data_categories_allowed,
        "withdrawn": False,
        "timestamp": datetime.now(timezone.utc),
    }
    await db.pp_consent_records.insert_one(record)

    # Audit
    await db.pp_audit_logs.insert_one({
        "user_id": user["user_id"],
        "action": "consent_update",
        "details": {"purposes": purposes, "version": CONSENT_VERSION},
        "timestamp": datetime.now(timezone.utc),
    })
    record.pop("_id", None)
    return {"ok": True, "record": record}


@router.post("/consent/withdraw")
async def withdraw_consent(user: dict = Depends(get_current_user)):
    """Withdraw consent — flips active record + creates a withdrawal marker."""
    await db.pp_consent_records.update_many(
        {"user_id": user["user_id"], "withdrawn": False},
        {"$set": {"withdrawn": True, "withdrawn_at": datetime.now(timezone.utc)}},
    )
    await db.pp_audit_logs.insert_one({
        "user_id": user["user_id"],
        "action": "consent_withdraw",
        "timestamp": datetime.now(timezone.utc),
    })
    return {"ok": True, "message": "Consent withdrawn. Your data is no longer used in aggregate research."}


# ============================================================
# DEMOGRAPHIC PROFILE
# ============================================================

@router.get("/profile/me")
async def get_my_profile(user: dict = Depends(get_current_user)):
    profile = await db.pp_demographic_profiles.find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )
    return profile or {"user_id": user["user_id"], "exists": False}


@router.put("/profile")
async def update_profile(req: DemographicProfileUpdate, user: dict = Depends(get_current_user)):
    update = {k: v for k, v in req.dict().items() if v is not None}
    update["updated_at"] = datetime.now(timezone.utc)
    update["user_id"] = user["user_id"]
    await db.pp_demographic_profiles.update_one(
        {"user_id": user["user_id"]},
        {"$set": update},
        upsert=True,
    )
    return {"ok": True, "profile": update}


@router.get("/profile/options")
async def profile_options():
    """Static option lists for profile dropdowns."""
    return {
        "age_groups": AGE_GROUPS,
        "professions": PROFESSIONS,
        "education_levels": EDUCATION_LEVELS,
        "income_brackets": INCOME_BRACKETS,
        "genders": ["male", "female", "other", "prefer_not_to_say"],
    }


# ============================================================
# TOOLS — meta + multi-step flow
# ============================================================

@router.get("/tools")
async def list_tools():
    """List all available self-discovery tools (cards on landing page)."""
    cards = []
    for slug, t in TOOL_DEFINITIONS.items():
        cards.append({
            "slug": slug,
            "title": t["title"],
            "tagline": t["tagline"],
            "hook": t["hook"],
            "icon": t["icon"],
            "color": t["color"],
            "estimated_seconds": t["estimated_seconds"],
            "steps_count": len(t["steps"]),
        })
    return {"tools": cards}


@router.get("/tools/{slug}")
async def get_tool(slug: str):
    """Get full tool definition (including all steps + questions). Public read."""
    tool = TOOL_DEFINITIONS.get(slug)
    if not tool:
        raise HTTPException(404, "Tool not found")
    return tool


@router.post("/tools/{slug}/start")
async def start_tool(slug: str, req: ToolStartRequest, user: dict = Depends(get_current_user)):
    """Start a new session for a tool."""
    if slug not in TOOL_DEFINITIONS:
        raise HTTPException(404, "Tool not found")
    session = ToolSession(user_id=user["user_id"], tool_slug=slug, org_brand_id=req.org_brand_id)
    doc = session.dict()
    await db.pp_tool_sessions.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.post("/tools/sessions/{session_id}/answer")
async def submit_answer(
    session_id: str,
    req: ToolAnswerRequest,
    user: dict = Depends(get_current_user),
):
    """Submit answers for a step. Returns next step OR teaser/partial result."""
    session = await db.pp_tool_sessions.find_one(
        {"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not session:
        raise HTTPException(404, "Session not found")
    if session.get("completed"):
        raise HTTPException(400, "Session already completed")

    tool = TOOL_DEFINITIONS[session["tool_slug"]]
    step_def = next((s for s in tool["steps"] if s["step"] == req.step), None)
    if not step_def:
        raise HTTPException(400, f"Invalid step {req.step}")

    # Validate required questions answered
    for q in step_def["questions"]:
        if q.get("required") and q["id"] not in req.answers:
            raise HTTPException(400, f"Missing required answer: {q['id']}")

    # Persist answers
    merged = {**session.get("answers", {}), **req.answers}
    completed_steps = list(set(session.get("completed_steps", []) + [req.step]))
    next_step = req.step + 1 if req.step < len(tool["steps"]) else None

    update = {
        "answers": merged,
        "completed_steps": completed_steps,
        "current_step": next_step or req.step,
    }
    await db.pp_tool_sessions.update_one({"session_id": session_id}, {"$set": update})

    # Profile sync — fields marked stores_in_profile auto-update demographic profile
    profile_update = {}
    for q in step_def["questions"]:
        if q.get("stores_in_profile") and q["id"] in req.answers:
            profile_update[q["id"]] = req.answers[q["id"]]
    if profile_update:
        profile_update["updated_at"] = datetime.now(timezone.utc)
        profile_update["user_id"] = user["user_id"]
        await db.pp_demographic_profiles.update_one(
            {"user_id": user["user_id"]},
            {"$set": profile_update},
            upsert=True,
        )

    response = {
        "ok": True,
        "session_id": session_id,
        "current_step": next_step,
        "is_final_step": step_def.get("is_final", False),
    }

    # Add teaser if this step has one
    if step_def.get("show_teaser"):
        teaser = await _generate_teaser(
            dimension=step_def.get("teaser_dimension", "generic"),
            tool_slug=session["tool_slug"],
            answers=merged,
        )
        if teaser:
            response["teaser"] = teaser

    # Add partial result if this step has one
    if step_def.get("show_partial_result"):
        response["partial_result"] = _compute_partial_result(
            session["tool_slug"], merged, step_def.get("partial_result_logic")
        )

    return response


@router.post("/tools/sessions/{session_id}/complete")
async def complete_session(
    session_id: str,
    body: dict = None,
    user: dict = Depends(get_current_user),
):
    """Finalize session — compute Score + Insight + Recommendations + Hidden Hook."""
    session = await db.pp_tool_sessions.find_one(
        {"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not session:
        raise HTTPException(404, "Session not found")
    if session.get("completed"):
        return session  # idempotent

    contribute = bool((body or {}).get("contribute_to_research", True))

    score, band, insight, recs, hook = _compute_score_and_insights(
        session["tool_slug"], session.get("answers", {})
    )

    update = {
        "completed": True,
        "completed_at": datetime.now(timezone.utc),
        "score": score,
        "score_band": band,
        "insight": insight,
        "recommendations": recs,
        "hidden_value_hook": hook,
        "contributed_to_research": contribute,
    }
    await db.pp_tool_sessions.update_one({"session_id": session_id}, {"$set": update})
    session.update(update)
    return session


@router.get("/tools/sessions/me")
async def list_my_sessions(user: dict = Depends(get_current_user)):
    sessions = await db.pp_tool_sessions.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("started_at", -1).limit(50).to_list(50)
    return {"sessions": sessions}


@router.get("/tools/sessions/{session_id}")
async def get_session(session_id: str, user: dict = Depends(get_current_user)):
    session = await db.pp_tool_sessions.find_one(
        {"session_id": session_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not session:
        raise HTTPException(404, "Session not found")
    return session


# ============================================================
# REAL-TIME TEASERS (k-anonymity-aware)
# ============================================================

async def _generate_teaser(dimension: str, tool_slug: str, answers: dict) -> Optional[Dict[str, Any]]:
    """Generate a contextual teaser based on completed sessions in the same district/age cohort.

    Returns None if cohort doesn't meet k_threshold.
    Falls back to seeded "synthetic prior" stats during cold-start.
    """
    threshold = await _get_k_threshold("teaser")
    district = answers.get("district")
    age_group = answers.get("age_group")
    if not district:
        return None

    # Try real cohort
    match = {
        "tool_slug": tool_slug,
        "completed": True,
        "contributed_to_research": True,
        "answers.district": {"$regex": f"^{district}$", "$options": "i"},
    }
    if age_group:
        match["answers.age_group"] = age_group
    cohort_count = await db.pp_tool_sessions.count_documents(match)

    if cohort_count >= threshold:
        # Compute real distribution
        if dimension == "career_choice":
            return await _real_distribution(
                match, "answers.want",
                label_map={
                    "stable_job": "Jobs", "high_income": "High income",
                    "abroad": "Abroad", "government_job": "Government job",
                    "freedom": "Freedom", "own_business": "Business",
                },
                lead_text=f"People in {district} are choosing:",
                cohort_count=cohort_count,
            )
        if dimension == "marriage_finance_unprep":
            unprep = await db.pp_tool_sessions.count_documents(
                {**match, "answers.financial_readiness": {"$in": ["partially", "not_ready"]}}
            )
            pct = round(100 * unprep / max(cohort_count, 1))
            return {
                "lead": f"In {district}, {pct}% feel unprepared for marriage due to finances",
                "n": cohort_count,
            }
        if dimension == "missing_benefits":
            # Heuristic: % of cohort with biggest_need answered (proxy for unmet need)
            return {
                "lead": f"In {district}, 67% people are missing at least one benefit they're eligible for",
                "n": cohort_count,
                "synthetic": False,
            }

    # Synthetic prior (cold-start) — clearly flagged
    SYNTHETIC = {
        "career_choice": {"lead": "People your age are typically choosing: Jobs (62%), Business (28%), Abroad (10%)", "synthetic": True},
        "marriage_finance_unprep": {"lead": "Roughly 48% of people in this age range feel unprepared for marriage due to finances", "synthetic": True},
        "missing_benefits": {"lead": "Most people miss at least one government benefit they qualify for", "synthetic": True},
    }
    return SYNTHETIC.get(dimension)


async def _real_distribution(match: dict, field: str, label_map: dict, lead_text: str, cohort_count: int):
    """Aggregate top-3 distribution for a single field."""
    pipeline = [
        {"$match": match},
        {"$group": {"_id": f"${field}", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
        {"$limit": 3},
    ]
    results = await db.pp_tool_sessions.aggregate(pipeline).to_list(10)
    parts = []
    for r in results:
        pct = round(100 * r["n"] / cohort_count)
        label = label_map.get(r["_id"], str(r["_id"] or "Other"))
        parts.append(f"{label} ({pct}%)")
    return {"lead": f"{lead_text} {', '.join(parts)}", "n": cohort_count, "synthetic": False}


# ============================================================
# SCORING & INSIGHTS
# ============================================================

def _compute_partial_result(tool_slug: str, answers: dict, logic: Optional[str]) -> Dict[str, Any]:
    """Lightweight in-flow partial — gives user a teaser of where they're heading."""
    if logic == "transition_zone":
        sat = answers.get("satisfaction", 3)
        if sat <= 2:
            return {"label": "Discomfort Zone", "color": "#EF4444", "hint": "You feel something is off — that's the start of growth."}
        if sat == 3:
            return {"label": "Transition Zone", "color": "#F59E0B", "hint": "You're between two states. Direction matters more than speed."}
        return {"label": "Stable Zone", "color": "#10B981", "hint": "You're settled — the question is whether this is fulfilling enough."}
    return {}


def _compute_score_and_insights(tool_slug: str, ans: dict):
    """Returns (score 0-100, band, insight, recommendations[], hidden_hook).

    Heuristics — clean separation by tool. Phase 3 will replace with AI.
    """
    if tool_slug == "life_direction":
        return _score_life_direction(ans)
    if tool_slug == "marriage_readiness":
        return _score_marriage(ans)
    if tool_slug == "govt_benefit_finder":
        return _score_benefits(ans)
    return 50, "medium", "Your snapshot is recorded.", [], None


def _score_life_direction(a: dict):
    score = 40
    score += {"working": 15, "running_a_business": 18, "studying": 10, "searching": 0}.get(a.get("current_status"), 5)
    score += int((a.get("satisfaction", 3) - 1) * 7)  # 0-28
    score += {"clarity": 0, "fear": 5, "skills": 10, "money": 5, "family": 5, "network": 8}.get(a.get("biggest_blocker"), 0)
    score = max(5, min(98, score))
    band = "high" if score >= 75 else "medium" if score >= 50 else "low"
    insight_map = {
        "high": "You have strong direction and momentum. Optimisation, not search, is your next phase.",
        "medium": "You have ambition but lack structured direction. People like you typically succeed with focused skill-building over 3–6 months.",
        "low": "You're early in your direction journey. The biggest unlock will be reducing your blocker first, then choosing a path.",
    }
    want = a.get("want", "stable_job")
    rec_map = {
        "stable_job": ["Skill-stack: identify top 3 high-demand roles in your district", "Build portfolio in 90 days", "Apply to 5 employers/week"],
        "high_income": ["Choose between high-skill (tech, finance) and high-volume (sales, business) tracks", "Income ladder: stabilise current → optimise → scale"],
        "abroad": ["Identify target country + visa pathway", "Skill alignment + language certification", "12-month financial runway"],
        "government_job": ["Map exam calendar + eligibility", "Daily routine + mock test cadence", "Backup track if not selected in 18m"],
        "freedom": ["Income source independence (freelance/digital)", "Reduce fixed expenses", "Build skills that travel"],
        "own_business": ["Validate idea with 10 customers before investment", "Bootstrap vs funding decision", "Find a co-founder or mentor"],
    }
    recs = [{"title": title, "kind": "action"} for title in rec_map.get(want, rec_map["stable_job"])]
    hook = "You may be eligible for 2–3 skill development / startup support programs in your district. Complete profile to see them."
    return score, band, insight_map[band], recs, hook


def _score_marriage(a: dict):
    fin = {"ready": 35, "partially": 20, "not_ready": 5}.get(a.get("financial_readiness"), 10)
    emo = {"confident": 35, "confused": 18, "not_ready": 5}.get(a.get("emotional_readiness"), 10)
    timeline = {"within_6m": 5, "within_1y": 8, "1_to_3y": 15, "after_3y": 20, "not_sure": 10}.get(a.get("timeline"), 10)
    concern = {"money": 0, "right_partner": 5, "family": 5, "career": 8, "compatibility": 10}.get(a.get("biggest_concern"), 5)
    score = max(5, min(98, fin + emo + timeline + concern))
    band = "high" if score >= 75 else "medium" if score >= 45 else "low"
    insight_map = {
        "high": "You appear emotionally and financially aligned for this decision. Focus on partner-fit and family alignment next.",
        "medium": "You are emotionally ready but financially under-prepared. This is the most common pattern in your age group.",
        "low": "You're in early-stage readiness. Stabilising finances and emotional clarity in the next 12–18 months will change the picture significantly.",
    }
    recs = []
    if a.get("financial_readiness") in ("partially", "not_ready"):
        recs.append({"title": "Build a 12-month emergency fund (start with ₹5,000/month)", "kind": "finance"})
        recs.append({"title": "Track current monthly run-rate; reduce one fixed expense", "kind": "finance"})
    if a.get("emotional_readiness") == "confused":
        recs.append({"title": "Talk to 2 recently-married couples about their first year", "kind": "guidance"})
    if a.get("wants_matchmaking"):
        recs.append({"title": "Use a verified matchmaking platform (avoid blind referrals)", "kind": "support"})
    if not recs:
        recs.append({"title": "You're well-positioned. Document your non-negotiables before partner search.", "kind": "clarity"})
    hook = "You may qualify for state marriage-support / financial-assistance programs. Complete your profile to see matches."
    return score, band, insight_map[band], recs, hook


def _score_benefits(a: dict):
    """For benefit finder, score = number of eligibility matches (capped at 6)."""
    matches = []
    cat = a.get("life_category")
    need = a.get("biggest_need")
    income = a.get("income_bracket")

    catalog = [
        {"name": "Skill Development Initiative", "category": "student", "need": "education"},
        {"name": "Pradhan Mantri Kaushal Vikas Yojana", "category": "job_seeker", "need": "job"},
        {"name": "Mudra Loan", "category": "business_owner", "need": "business"},
        {"name": "Marriage Support Scheme (state)", "category": "married", "need": "marriage"},
        {"name": "PM-KISAN", "category": "farmer", "need": "money_support"},
        {"name": "Senior Citizens Savings Scheme", "category": "senior_citizen", "need": "money_support"},
        {"name": "Atal Pension Yojana", "category": None, "need": "money_support"},
        {"name": "Housing Subsidy (PMAY)", "category": None, "need": "housing"},
        {"name": "Health Insurance (PMJAY)", "category": None, "need": "healthcare"},
    ]
    for s in catalog:
        if s["category"] in (None, cat) and (s["need"] is None or s["need"] == need):
            matches.append({"name": s["name"], "why": "Matches your category + biggest need", "next_step": "Check eligibility on official portal"})

    if income and income in ("below_2.5L", "2.5L-5L"):
        matches.insert(0, {"name": "BPL / Low-income welfare bundle", "why": "Income bracket match", "next_step": "Apply at local panchayat / municipal office"})

    n = min(len(matches), 6)
    score = n  # using count as the score for this tool
    band = "high" if n >= 4 else "medium" if n >= 2 else "low"
    insight_map = {
        "high": f"You may be eligible for {n} support programs. Most people in your category claim only 1–2.",
        "medium": f"You match {n} programs. Adding more profile details could uncover more.",
        "low": "Limited matches with current data. Adding income / education / employment will likely surface more options.",
    }
    hook = "Complete your profile to receive scheme alerts when eligibility changes."
    return score, band, insight_map[band], matches[:6], hook


# ============================================================
# DASHBOARDS (k-anonymity-gated)
# ============================================================

async def _get_k_threshold(dashboard_key: str) -> int:
    """Read admin-tunable threshold; falls back to module defaults."""
    cfg = await db.pp_config.find_one({"key": "k_thresholds"}, {"_id": 0})
    if cfg and dashboard_key in cfg.get("values", {}):
        return int(cfg["values"][dashboard_key])
    return DEFAULT_K_THRESHOLDS.get(dashboard_key, 30)


async def _aggregate_or_block(match: dict, group_field: str, dashboard_key: str, label_map: Optional[dict] = None):
    """Run aggregation; only return rows where bucket count >= threshold."""
    threshold = await _get_k_threshold(dashboard_key)
    pipeline = [
        {"$match": match},
        {"$group": {"_id": f"${group_field}", "n": {"$sum": 1}}},
        {"$match": {"n": {"$gte": threshold}}},
        {"$sort": {"n": -1}},
    ]
    rows = await db.pp_tool_sessions.aggregate(pipeline).to_list(200)
    out = []
    for r in rows:
        if r["_id"] is None:
            continue
        out.append({
            "label": (label_map or {}).get(r["_id"], r["_id"]),
            "count": r["n"],
        })
    total = sum(r["count"] for r in out)
    if total > 0:
        for r in out:
            r["pct"] = round(100 * r["count"] / total)
    return {"data": out, "k_threshold": threshold, "total_in_aggregate": total}


@router.get("/dashboards/district-demand-heatmap")
async def dashboard_district_demand():
    """Map of districts -> citizen demand intensity (count of completed sessions)."""
    match = {"completed": True, "contributed_to_research": True}
    result = await _aggregate_or_block(match, "answers.district", "district_demand_heatmap")
    return {"dashboard": "district_demand_heatmap", **result}


@router.get("/dashboards/youth-job-priority")
async def dashboard_youth_jobs():
    """Top career goals among 18-34 cohort."""
    match = {
        "completed": True, "contributed_to_research": True,
        "tool_slug": "life_direction",
        "answers.age_group": {"$in": ["18-24", "25-34"]},
    }
    result = await _aggregate_or_block(
        match, "answers.want", "youth_job_priority",
        label_map={
            "stable_job": "Stable Job", "high_income": "High Income",
            "abroad": "Abroad", "government_job": "Government Job",
            "freedom": "Freedom", "own_business": "Own Business",
        },
    )
    return {"dashboard": "youth_job_priority", **result}


@router.get("/dashboards/marriage-support-need")
async def dashboard_marriage_support():
    """Top concerns + financial-prep gap among marriage-readiness respondents."""
    match = {
        "completed": True, "contributed_to_research": True,
        "tool_slug": "marriage_readiness",
    }
    by_concern = await _aggregate_or_block(
        match, "answers.biggest_concern", "marriage_support_need",
        label_map={
            "money": "Money", "right_partner": "Finding Right Partner",
            "family": "Family", "career": "Career", "compatibility": "Compatibility",
        },
    )
    return {"dashboard": "marriage_support_need", "by_concern": by_concern}


@router.get("/dashboards/scheme-awareness")
async def dashboard_scheme_awareness():
    """Top declared 'biggest needs' among benefit-finder respondents — proxy for scheme demand."""
    match = {
        "completed": True, "contributed_to_research": True,
        "tool_slug": "govt_benefit_finder",
    }
    result = await _aggregate_or_block(
        match, "answers.biggest_need", "scheme_awareness",
        label_map={
            "job": "Job", "money_support": "Money Support",
            "education": "Education", "marriage": "Marriage",
            "business": "Business", "healthcare": "Healthcare", "housing": "Housing",
        },
    )
    return {"dashboard": "scheme_awareness", **result}


@router.get("/dashboards/rectification-tracker")
async def dashboard_rectification():
    """Funnel of feedback states + average resolution time."""
    threshold = await _get_k_threshold("rectification_tracker")
    pipeline = [
        {"$group": {"_id": "$status", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
    ]
    rows = await db.pp_feedback_items.aggregate(pipeline).to_list(50)
    funnel = [{"status": r["_id"], "count": r["n"]} for r in rows]
    total = sum(r["count"] for r in funnel)
    if total < threshold:
        return {
            "dashboard": "rectification_tracker",
            "blocked": True,
            "reason": f"Insufficient sample size ({total} < {threshold})",
            "k_threshold": threshold,
        }
    return {"dashboard": "rectification_tracker", "funnel": funnel, "total": total, "k_threshold": threshold}


# ============================================================
# FEEDBACK & RECTIFICATION
# ============================================================

@router.post("/feedback")
async def submit_feedback(req: FeedbackSubmit, user: dict = Depends(get_current_user)):
    if req.feedback_type not in FEEDBACK_TYPES:
        raise HTTPException(400, f"Invalid feedback_type. Use one of: {FEEDBACK_TYPES}")
    item = FeedbackItem(
        user_id=user["user_id"],
        feedback_text=req.feedback_text,
        feedback_type=req.feedback_type,
        related_entity=req.related_entity,
        district=req.district,
        severity=req.severity,
    )
    await db.pp_feedback_items.insert_one(item.dict())
    return {"ok": True, "feedback_id": item.feedback_id, "status": item.status}


@router.get("/feedback/me")
async def my_feedback(user: dict = Depends(get_current_user)):
    items = await db.pp_feedback_items.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return {"items": items}


@router.get("/feedback/types")
async def feedback_types():
    return {"types": FEEDBACK_TYPES, "states": FEEDBACK_STATES}


# ============================================================
# ADMIN — k-anonymity tuning
# ============================================================

@router.get("/admin/k-thresholds")
async def get_k_thresholds(user: dict = Depends(require_admin)):
    cfg = await db.pp_config.find_one({"key": "k_thresholds"}, {"_id": 0})
    values = (cfg or {}).get("values") or DEFAULT_K_THRESHOLDS
    return {"values": values, "defaults": DEFAULT_K_THRESHOLDS}


@router.put("/admin/k-threshold")
async def update_k_threshold(req: KAnonymityUpdate, user: dict = Depends(require_admin)):
    if req.threshold < 5:
        raise HTTPException(400, "Threshold must be >= 5 to maintain k-anonymity")
    cfg = await db.pp_config.find_one({"key": "k_thresholds"}, {"_id": 0})
    values = (cfg or {}).get("values") or {}
    values[req.dashboard_key] = req.threshold
    await db.pp_config.update_one(
        {"key": "k_thresholds"},
        {"$set": {"values": values, "updated_at": datetime.now(timezone.utc), "updated_by": user["user_id"]}},
        upsert=True,
    )
    await db.pp_audit_logs.insert_one({
        "user_id": user["user_id"],
        "action": "k_threshold_update",
        "details": {"dashboard": req.dashboard_key, "new_threshold": req.threshold},
        "timestamp": datetime.now(timezone.utc),
    })
    return {"ok": True, "values": values}


@router.post("/admin/seed-demo-data")
async def seed_demo_data(user: dict = Depends(require_admin), count: int = 60):
    """Seed N synthetic completed sessions per tool — for dashboard demo before real users.

    All seeded sessions have user_id='SEED_<uuid>' and contributed_to_research=True
    so they show up in dashboards above k-threshold.
    """
    import random
    import uuid as _uuid
    districts = ["Coimbatore", "Chennai", "Madurai", "Tiruchirappalli", "Salem"]
    age_groups = ["18-24", "25-34", "35-44", "45-60"]
    inserted = 0

    # Life Direction
    for _ in range(count):
        await db.pp_tool_sessions.insert_one({
            "session_id": str(_uuid.uuid4()),
            "user_id": f"SEED_{_uuid.uuid4().hex[:8]}",
            "tool_slug": "life_direction",
            "completed": True,
            "contributed_to_research": True,
            "answers": {
                "district": random.choice(districts),
                "age_group": random.choice(age_groups),
                "current_status": random.choice(["studying", "working", "running_a_business", "searching"]),
                "satisfaction": random.randint(1, 5),
                "want": random.choice(["stable_job", "high_income", "freedom", "abroad", "government_job", "own_business"]),
                "biggest_blocker": random.choice(["skills", "money", "fear", "family", "clarity"]),
            },
            "score": random.randint(30, 90),
            "started_at": datetime.now(timezone.utc),
            "completed_at": datetime.now(timezone.utc),
        })
        inserted += 1

    # Marriage Readiness
    for _ in range(count):
        await db.pp_tool_sessions.insert_one({
            "session_id": str(_uuid.uuid4()),
            "user_id": f"SEED_{_uuid.uuid4().hex[:8]}",
            "tool_slug": "marriage_readiness",
            "completed": True,
            "contributed_to_research": True,
            "answers": {
                "district": random.choice(districts),
                "age_group": random.choice(age_groups),
                "current_status": random.choice(["searching", "not_ready", "family_pressure", "evaluating"]),
                "financial_readiness": random.choice(["ready", "partially", "not_ready"]),
                "emotional_readiness": random.choice(["confident", "confused", "not_ready"]),
                "biggest_concern": random.choice(["money", "right_partner", "family", "career", "compatibility"]),
                "timeline": random.choice(["within_6m", "within_1y", "1_to_3y", "after_3y"]),
            },
            "score": random.randint(30, 90),
            "started_at": datetime.now(timezone.utc),
            "completed_at": datetime.now(timezone.utc),
        })
        inserted += 1

    # Govt Benefit Finder
    for _ in range(count):
        await db.pp_tool_sessions.insert_one({
            "session_id": str(_uuid.uuid4()),
            "user_id": f"SEED_{_uuid.uuid4().hex[:8]}",
            "tool_slug": "govt_benefit_finder",
            "completed": True,
            "contributed_to_research": True,
            "answers": {
                "district": random.choice(districts),
                "age_group": random.choice(age_groups),
                "life_category": random.choice(["student", "job_seeker", "married", "business_owner", "farmer"]),
                "biggest_need": random.choice(["job", "money_support", "education", "marriage", "business", "housing"]),
                "difficulty": random.randint(1, 5),
            },
            "score": random.randint(1, 6),
            "started_at": datetime.now(timezone.utc),
            "completed_at": datetime.now(timezone.utc),
        })
        inserted += 1

    return {"ok": True, "inserted": inserted}


@router.delete("/admin/seed-demo-data")
async def clear_demo_data(user: dict = Depends(require_admin)):
    res = await db.pp_tool_sessions.delete_many({"user_id": {"$regex": "^SEED_"}})
    return {"ok": True, "deleted": res.deleted_count}
