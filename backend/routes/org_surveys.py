"""
Org Surveys — multi-question public forms scoped to a single Org slug.

White-label sub-portal Phase-3 (B):
  • Org admins can create surveys (with N questions of various types)
  • Surveys live under  /api/p/{slug}/surveys
  • Public users (anon allowed if survey.accepts_anon) can submit responses
  • Aggregate counts are public (no PII)
  • Org members + super admins can edit/delete their own surveys

This is intentionally a separate module from public_pulse_portal.py so it
can grow without bloating that file.
"""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import uuid

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field

from core.database import db
from core.auth import require_admin, get_current_user, get_current_user_optional

router = APIRouter(tags=["Public Pulse — Org Surveys"])


# ------------------------------------------------------------------
# Models
# ------------------------------------------------------------------
ALLOWED_QTYPES = {"single_select", "multi_select", "short_text", "long_text", "rating_5", "yes_no", "number"}


class SurveyQuestion(BaseModel):
    qid: str
    text: str
    qtype: str = "short_text"
    options: Optional[List[str]] = None  # for single_select / multi_select
    required: bool = False
    helper: Optional[str] = None


class SurveyCreate(BaseModel):
    title: str
    description: Optional[str] = None
    questions: List[SurveyQuestion] = Field(default_factory=list)
    is_active: bool = True
    accepts_anon: bool = True
    closes_at: Optional[datetime] = None


class SurveyResponseSubmit(BaseModel):
    answers: Dict[str, Any]  # { qid: value }
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _strip(d: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not d:
        return d
    d.pop("_id", None)
    return d


async def _resolve_org_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    if not slug:
        return None
    return await db.pp_orgs.find_one(
        {"slug": slug, "status": "approved"},
        {"_id": 0, "brand_logo_b64": 0},
    )


async def _is_org_admin(slug: str, user: Dict[str, Any]) -> bool:
    """Allow if user is an admin/super_admin OR an active member of the org with admin role."""
    if not user:
        return False
    if user.get("role") in ("admin", "super_admin", "co_admin"):
        return True
    # Check org-level membership/role
    org = await _resolve_org_by_slug(slug)
    if not org:
        return False
    if user.get("org_id") == org.get("org_id") and user.get("org_role") in ("org_admin", "org_co_admin", "org_super_admin"):
        return True
    return False


def _validate_questions(questions: List[SurveyQuestion]) -> None:
    if not questions:
        raise HTTPException(400, "at least one question is required")
    seen = set()
    for q in questions:
        if not q.qid or not q.text:
            raise HTTPException(400, "each question must have qid and text")
        if q.qid in seen:
            raise HTTPException(400, f"duplicate qid: {q.qid}")
        seen.add(q.qid)
        if q.qtype not in ALLOWED_QTYPES:
            raise HTTPException(400, f"invalid qtype '{q.qtype}'. Allowed: {sorted(ALLOWED_QTYPES)}")
        if q.qtype in ("single_select", "multi_select") and not q.options:
            raise HTTPException(400, f"qid {q.qid}: {q.qtype} requires options")


# ------------------------------------------------------------------
# Public reads
# ------------------------------------------------------------------
@router.get("/p/{slug}/surveys")
async def list_org_surveys(slug: str, include_inactive: bool = False):
    """List all active surveys for an org (public)."""
    org = await _resolve_org_by_slug(slug)
    if not org:
        raise HTTPException(404, "Org sub-portal not found")
    q: Dict[str, Any] = {"org_id": org["org_id"]}
    if not include_inactive:
        q["is_active"] = True
    items = []
    async for s in db.pp_org_surveys.find(q, {"_id": 0}).sort("created_at", -1):
        # Don't expose internal contact info on list response
        s.pop("created_by", None)
        items.append(s)
    return {"items": items, "org": {"slug": slug, "display_name": org.get("display_name")}}


@router.get("/p/{slug}/surveys/{survey_id}")
async def get_org_survey(slug: str, survey_id: str):
    """Get one survey's full schema (public)."""
    org = await _resolve_org_by_slug(slug)
    if not org:
        raise HTTPException(404, "Org sub-portal not found")
    s = await db.pp_org_surveys.find_one({"survey_id": survey_id, "org_id": org["org_id"]}, {"_id": 0})
    if not s:
        raise HTTPException(404, "survey not found")
    s.pop("created_by", None)
    return {"survey": s, "org": {"slug": slug, "display_name": org.get("display_name")}}


@router.get("/p/{slug}/surveys/{survey_id}/aggregate")
async def survey_aggregate(slug: str, survey_id: str):
    """Public aggregated counts for closed-form questions (no PII)."""
    org = await _resolve_org_by_slug(slug)
    if not org:
        raise HTTPException(404, "Org sub-portal not found")
    survey = await db.pp_org_surveys.find_one(
        {"survey_id": survey_id, "org_id": org["org_id"]}, {"_id": 0}
    )
    if not survey:
        raise HTTPException(404, "survey not found")

    counts: Dict[str, Dict[str, Any]] = {}
    total_responses = 0
    async for r in db.pp_org_survey_responses.find(
        {"survey_id": survey_id}, {"_id": 0, "answers": 1}
    ):
        total_responses += 1
        for qid, val in (r.get("answers") or {}).items():
            counts.setdefault(qid, {"total": 0, "buckets": {}})
            counts[qid]["total"] += 1
            if isinstance(val, list):
                for v in val:
                    sv = str(v)[:80]
                    counts[qid]["buckets"][sv] = counts[qid]["buckets"].get(sv, 0) + 1
            elif isinstance(val, bool):
                sv = "yes" if val else "no"
                counts[qid]["buckets"][sv] = counts[qid]["buckets"].get(sv, 0) + 1
            elif isinstance(val, (int, float)):
                sv = str(val)
                counts[qid]["buckets"][sv] = counts[qid]["buckets"].get(sv, 0) + 1
            elif isinstance(val, str):
                # Only bucket if the question is a single_select / yes_no — skip free-text
                q_meta = next((q for q in (survey.get("questions") or []) if q.get("qid") == qid), None)
                if q_meta and q_meta.get("qtype") in ("single_select", "yes_no"):
                    sv = val[:80]
                    counts[qid]["buckets"][sv] = counts[qid]["buckets"].get(sv, 0) + 1

    # Compute averages for rating_5 and number questions
    avg_per_q: Dict[str, float] = {}
    for q in (survey.get("questions") or []):
        if q.get("qtype") in ("rating_5", "number"):
            qid = q["qid"]
            vals: List[float] = []
            async for r in db.pp_org_survey_responses.find(
                {"survey_id": survey_id}, {"_id": 0, "answers": 1}
            ):
                v = (r.get("answers") or {}).get(qid)
                try:
                    if v is not None and v != "":
                        vals.append(float(v))
                except (TypeError, ValueError):
                    continue
            if vals:
                avg_per_q[qid] = round(sum(vals) / len(vals), 2)

    return {
        "survey_id": survey_id,
        "title": survey.get("title"),
        "total_responses": total_responses,
        "counts": counts,
        "avg_per_q": avg_per_q,
    }


# ------------------------------------------------------------------
# Submit response (public + optional auth)
# ------------------------------------------------------------------
@router.post("/p/{slug}/surveys/{survey_id}/submit")
async def submit_survey_response(
    slug: str,
    survey_id: str,
    body: SurveyResponseSubmit,
    request: Request,
    user_opt: Optional[dict] = Depends(get_current_user_optional),
):
    org = await _resolve_org_by_slug(slug)
    if not org:
        raise HTTPException(404, "Org sub-portal not found")
    survey = await db.pp_org_surveys.find_one(
        {"survey_id": survey_id, "org_id": org["org_id"]}, {"_id": 0}
    )
    if not survey:
        raise HTTPException(404, "survey not found")
    if not survey.get("is_active"):
        raise HTTPException(409, "survey is closed")
    if survey.get("closes_at") and survey["closes_at"] < _now():
        raise HTTPException(409, "survey has passed its close date")
    if not (user_opt and user_opt.get("user_id")) and not survey.get("accepts_anon", True):
        raise HTTPException(401, "this survey requires sign-in")

    # Required-field validation
    missing: List[str] = []
    answers = body.answers or {}
    for q in (survey.get("questions") or []):
        if q.get("required"):
            v = answers.get(q["qid"])
            if v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and len(v) == 0):
                missing.append(q["qid"])
    if missing:
        raise HTTPException(400, f"missing required answers for: {', '.join(missing)}")

    response_id = f"sr_{uuid.uuid4().hex[:12]}"
    doc: Dict[str, Any] = {
        "response_id": response_id,
        "survey_id": survey_id,
        "org_id": org["org_id"],
        "slug": slug,
        "answers": answers,
        "submitted_at": _now(),
    }
    if user_opt and user_opt.get("user_id"):
        doc["user_id"] = user_opt["user_id"]
    else:
        doc["anon_id"] = f"anon_{uuid.uuid4().hex[:10]}"
        if body.contact_name:
            doc["contact_name"] = body.contact_name[:120]
        if body.contact_email:
            doc["contact_email"] = body.contact_email[:200]

    await db.pp_org_survey_responses.insert_one(doc)
    await db.pp_org_surveys.update_one(
        {"survey_id": survey_id},
        {"$inc": {"response_count": 1}, "$set": {"last_response_at": _now()}},
    )

    return {"ok": True, "response_id": response_id}


# ------------------------------------------------------------------
# Org-admin: create / edit / delete / list-responses
# ------------------------------------------------------------------
@router.post("/p/{slug}/surveys")
async def create_org_survey(
    slug: str,
    body: SurveyCreate,
    user: dict = Depends(get_current_user),
):
    if not await _is_org_admin(slug, user):
        raise HTTPException(403, "Only org admins can create surveys for this org")
    org = await _resolve_org_by_slug(slug)
    if not org:
        raise HTTPException(404, "Org sub-portal not found")
    _validate_questions(body.questions)
    survey_id = f"sv_{uuid.uuid4().hex[:12]}"
    doc: Dict[str, Any] = {
        "survey_id": survey_id,
        "org_id": org["org_id"],
        "slug": slug,
        "title": body.title.strip()[:200],
        "description": (body.description or "").strip()[:2000] or None,
        "questions": [q.model_dump() for q in body.questions],
        "is_active": body.is_active,
        "accepts_anon": body.accepts_anon,
        "closes_at": body.closes_at,
        "response_count": 0,
        "created_by": user["user_id"],
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.pp_org_surveys.insert_one(doc)
    return {"ok": True, "survey_id": survey_id, "survey": _strip(doc)}


@router.put("/p/{slug}/surveys/{survey_id}")
async def update_org_survey(
    slug: str,
    survey_id: str,
    body: SurveyCreate,
    user: dict = Depends(get_current_user),
):
    if not await _is_org_admin(slug, user):
        raise HTTPException(403, "Only org admins can edit surveys")
    org = await _resolve_org_by_slug(slug)
    if not org:
        raise HTTPException(404, "Org sub-portal not found")
    s = await db.pp_org_surveys.find_one({"survey_id": survey_id, "org_id": org["org_id"]}, {"_id": 0})
    if not s:
        raise HTTPException(404, "survey not found")
    _validate_questions(body.questions)
    update = {
        "title": body.title.strip()[:200],
        "description": (body.description or "").strip()[:2000] or None,
        "questions": [q.model_dump() for q in body.questions],
        "is_active": body.is_active,
        "accepts_anon": body.accepts_anon,
        "closes_at": body.closes_at,
        "updated_at": _now(),
    }
    await db.pp_org_surveys.update_one({"survey_id": survey_id}, {"$set": update})
    return {"ok": True, "survey_id": survey_id}


@router.delete("/p/{slug}/surveys/{survey_id}")
async def delete_org_survey(
    slug: str,
    survey_id: str,
    user: dict = Depends(get_current_user),
):
    if not await _is_org_admin(slug, user):
        raise HTTPException(403, "Only org admins can delete surveys")
    org = await _resolve_org_by_slug(slug)
    if not org:
        raise HTTPException(404, "Org sub-portal not found")
    res = await db.pp_org_surveys.delete_one({"survey_id": survey_id, "org_id": org["org_id"]})
    if res.deleted_count == 0:
        raise HTTPException(404, "survey not found")
    # Optional: cascade delete responses
    await db.pp_org_survey_responses.delete_many({"survey_id": survey_id})
    return {"ok": True}


@router.get("/p/{slug}/surveys/{survey_id}/responses")
async def list_survey_responses(
    slug: str,
    survey_id: str,
    user: dict = Depends(get_current_user),
    limit: int = 100,
):
    """Org-admin only: see raw responses (with PII)."""
    if not await _is_org_admin(slug, user):
        raise HTTPException(403, "Only org admins can view responses")
    org = await _resolve_org_by_slug(slug)
    if not org:
        raise HTTPException(404, "Org sub-portal not found")
    items = []
    async for r in db.pp_org_survey_responses.find(
        {"survey_id": survey_id, "org_id": org["org_id"]}, {"_id": 0}
    ).sort("submitted_at", -1).limit(min(max(limit, 1), 500)):
        items.append(r)
    return {"items": items, "count": len(items)}
