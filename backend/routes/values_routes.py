"""Values Tracker — 8 Organizational Values @ Collaboration Principles.

Spec (frozen v3.25 with user):
- 8 platform-default principles (verbatim from "8 Core Values of VEALES" PDF, Mar 2026 v2)
- MANDATORY for every org — cannot be deleted OR hidden by org-admins
- Org-admins may ADD custom principles ON TOP of defaults
- Daily reflection captures 5 fields:
    1. Life Area
    2. Challenging Situation
    3. Applied Collaboration Principle(s) — MULTI-SELECT
    4. Inner Experience after applying
    5. Outer Consequence after applying
  Plus a `module_ref` so the same form is reused across:
    'org-values' (default),
    'eg-trap', 'eg-loop', 'eg-limitation', 'solution-finder'.
- AI Advisor picks TOP-3 most-relevant principles per situation, returns
  per-principle alignment score (0-10) + concrete do/don't guidance.
- AI alignment blocking threshold defaults to "warn + log"; SuperAdmin can
  toggle "block at score < N" for public users (and OrgAdmin for its org).
"""
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from core.database import db
from core.auth import ADMIN_ROLES, get_user_role
from routes.auth_routes import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/values", tags=["Values Tracker"])

REFLECTION_MODULES = (
    "org-values", "eg-trap", "eg-loop", "eg-limitation", "solution-finder",
)

# ============================================================
# Seed — the 8 VEALES values (verbatim from Mar 2026 v2 PDF)
# ============================================================
PLATFORM_DEFAULTS: List[Dict[str, Any]] = [
    {
        "code": "predictable_availability", "order": 1, "name": "PREDICTABLE AVAILABILITY",
        "short": "Be available as agreed; communicate early when you cannot.",
        "body": (
            "Predictably available for the Agreed collaboration activities on the Co-working Days "
            "and easily accessible during the Co-working Hours."
        ),
        "bullets": [
            "On the ACCESS-MODES (Directly / Online & On-Call for Work-From-Home), as required for the Situations & Roles.",
            "By Being Ready at least 3 mins before the planned time, with all necessary Arrangements to ensure Physical, Mental, Emotional, Technical & Situational Readiness.",
            "Except at Medical Emergencies for Self or Immediate Family co-living with you, for unplanned permissions/leaves, communicate with your Reporting Manager / Partner on a Live Video Call — avoid one-way communication by text / mail.",
            "If no response, leave a Voice message with IPR — Impromptu Permission Request — so collective mission can progress despite individual constraints.",
            "Cannot hold seniors accountable for this value (they play a bigger game beyond your perception). Peers can hold each other accountable. Subordinates too.",
        ],
    },
    {
        "code": "honesty", "order": 2, "name": "HONESTY",
        "short": "Accept mistakes openly; clarify gently if feedback is invalid.",
        "body": (
            "Openness to accept mistakes, along with the Action-plan to correct the mistakes if the feedback is valid; "
            "(OR) if the feedback is invalid, gently and clearly clarify with necessary facts/data to the feedback-provider."
        ),
        "bullets": [
            "Before reacting / defending / justifying, honestly ask yourself for at least 5 seconds if you've done anything wrong on your part.",
        ],
    },
    {
        "code": "integrity", "order": 3, "name": "INTEGRITY",
        "short": "Commit realistically; share progress, blockers, risks proactively; complete as committed.",
        "body": (
            "Listen attentively, understand specifics, commit REALISTICALLY (Scope, Quality, Cost, Time) per ATEX. "
            "Provide proactive updates on Progress, Dependency, Blockers, Risk Alerts, Completion. "
            "Be responsive. Complete means REALLY complete — no IFs and BUTs."
        ),
        "bullets": [
            "3.1 Realistic commitment with Documentation (voice note OK).",
            "3.2 Proactive updates DAILY + on Key Milestones; share BAD NEWS at the earliest.",
            "3.3 Responsive to team members with prompt communications + realistic re-commitment.",
            "3.4 Complete means REALLY complete without IFs and BUTs.",
        ],
    },
    {
        "code": "productivity", "order": 4, "name": "PRODUCTIVITY",
        "short": "Deliver best feasible RESULTS smartly — not just talk, action or interim progress.",
        "body": (
            "Ability to deliver the best feasible RESULTS for assigned ROLES & TEAM GOALS — smartly with lesser time "
            "and resources, for maximized ROI. Understand the Actual Purpose of each Task so deliverables align with purpose."
        ),
        "bullets": [
            "Continuously improve on the 6 Ps: Product/Service/Solution (Why & What), Project (What/Who/When), Process (How), Proficiency (Deeper How), People (With Whom & For Whom), Profit (How Much).",
        ],
    },
    {
        "code": "responsibility", "order": 5, "name": "RESPONSIBILITY",
        "short": "Identify risks + propose & implement solutions with ownership.",
        "body": (
            "Ability to identify & alert RISKS along with possible SOLUTIONS; intensity to implement solutions with clear "
            "ACTION-PLAN & Ownership."
        ),
        "bullets": [
            "Every problem is NOT my problem; but I'm RESPONSIBLE for every problem.",
            "Being responsible ≠ blame / guilt. It means I will solve this to create the future I want, from the right state of being.",
            "Looking for, sensing & alerting risks is NOT negativity. Negative THINKING is not what attracts negativity — only negative FEELING does.",
        ],
    },
    {
        "code": "solvability", "order": 6, "name": "SOLVABILITY",
        "short": "Be aware of EC-PC-BC-SC; deal directly; seek Win-Win using PSR-VCS.",
        "body": (
            "Be aware of EC (Emotional Conditioning), PC (Prejudgement Conditioning), BC (Behavioral Conditioning), "
            "SC (Situational Constraints). Clarify facts before judging. Deal directly via Crucial Conversations, "
            "with Mutual Respect & Mutual Purpose, seeking Win-Win solutions aligned with PSR-VCS guidelines."
        ),
        "bullets": [
            "EC / PC / BC / SC awareness; do NOT make personal constraints into project constraints.",
            "No open loops — use live 2-way communication. If urgent unplanned, send ICR — Impromptu Call Request.",
            "PSR-VCS: Purpose (Owner) → Situations (Manager) → Role (Team Lead) → Values (HR) → Culture (Seniors) → Systems (Peers).",
            "3 guidelines: (1) Honestly admit 'I don't know the solution'. (2) Firmly believe a solution must exist. (3) Intensely seek the solution RIGHT NOW from Responsible Surrendering.",
        ],
    },
    {
        "code": "synchronicity", "order": 7, "name": "SYNCHRONICITY",
        "short": "Align What/How/By-When like birds flying in perfect sync.",
        "body": (
            "Without getting stuck in self-limitations or situational constraints. Align on Scope (What), Quality (How) "
            "and Timelines (By When) with the team / task owner / situation needs."
        ),
        "bullets": [
            "Whatever we don't know need not be difficult.",
            "Whatever is difficult need not be impossible.",
            "Whatever is impossible need not be impossible forever.",
        ],
    },
    {
        "code": "inclusivity", "order": 8, "name": "INCLUSIVITY",
        "short": "Never abandon a team-mate; Mission > Team > Self; lead by example.",
        "body": (
            "Never abandon a team-mate in need. Support fellow members beyond self. Default Priorities: (1) Mission "
            "(2) Team (3) Self. Hold each other accountable; include every stakeholder; exclude unauthorized engagements."
        ),
        "bullets": [
            "Lead by example with focus for Collective Good of All Stakeholders in the long run, with minimal short-term compromises.",
        ],
    },
]


# ============================================================
# Pydantic
# ============================================================
class PrincipleIn(BaseModel):
    code: str
    name: str
    short: Optional[str] = ""
    body: str
    bullets: List[str] = Field(default_factory=list)
    order: int = 100
    org_id: Optional[str] = None  # null = platform default
    active: bool = True


class ReflectionIn(BaseModel):
    module_ref: str = "org-values"  # one of REFLECTION_MODULES
    related_session_id: Optional[str] = None  # e.g. eg-trap session id
    life_area: str
    challenging_situation: str
    applied_principle_codes: List[str] = Field(default_factory=list)
    inner_experience: str
    outer_consequence: str


class AdvisorIn(BaseModel):
    situation: str
    org_id: Optional[str] = None
    use_top_n: int = 3


# ============================================================
# Helpers
# ============================================================
def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _ensure_seeded():
    """Idempotent seed of platform-default values."""
    for v in PLATFORM_DEFAULTS:
        await db.value_principles.update_one(
            {"code": v["code"], "org_id": None},
            {"$setOnInsert": {
                **v, "org_id": None, "platform_default": True, "active": True,
                "id": str(uuid.uuid4()), "created_at": _now(),
            }},
            upsert=True,
        )


async def _resolved_principles_for(user: dict, org_id: Optional[str] = None) -> List[dict]:
    """Return active principles for the user/org: platform defaults + org-custom."""
    await _ensure_seeded()
    org_id = org_id or user.get("org_id")
    # Platform defaults always show. Org-custom only when present.
    q = {"active": True, "$or": [{"org_id": None}, {"org_id": org_id}] if org_id else [{"org_id": None}]}
    if not org_id:
        q = {"active": True, "org_id": None}
    rows = await db.value_principles.find(q, {"_id": 0}).sort("order", 1).to_list(200)
    return rows


# ============================================================
# CRUD — principles (admin / org-admin)
# ============================================================
@router.get("/principles")
async def list_principles(user: dict = Depends(get_current_user)):
    rows = await _resolved_principles_for(user)
    return {"principles": rows}


@router.post("/principles")
async def create_principle(p: PrincipleIn, user: dict = Depends(get_current_user)):
    role = get_user_role(user)
    if role not in ADMIN_ROLES + ["org_admin", "org_co_admin", "org_super_admin"]:
        raise HTTPException(403, "Admin only")
    # Org admins can only create FOR their org. Platform admins can create either.
    if p.org_id is None and role not in ADMIN_ROLES:
        raise HTTPException(403, "Only platform admins can create platform-default principles")
    doc = {
        **p.model_dump(),
        "id": str(uuid.uuid4()),
        "platform_default": p.org_id is None,
        "created_at": _now(),
        "created_by": user["user_id"],
    }
    await db.value_principles.insert_one(doc)
    doc.pop("_id", None)
    return {"principle": doc}


@router.put("/principles/{principle_id}")
async def update_principle(principle_id: str, p: PrincipleIn, user: dict = Depends(get_current_user)):
    existing = await db.value_principles.find_one({"id": principle_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Principle not found")
    role = get_user_role(user)
    if existing.get("platform_default"):
        # Platform defaults are MANDATORY — they cannot be deleted nor hidden,
        # but a platform-admin may still tweak name/order/bullets.
        if role not in ADMIN_ROLES:
            raise HTTPException(403, "Platform-default principles can only be edited by platform admins")
        # Forbid disabling a mandatory default.
        if not p.active:
            raise HTTPException(400, "Platform-default principles are mandatory and cannot be hidden/disabled")
    else:
        if existing.get("org_id") != user.get("org_id") and role not in ADMIN_ROLES:
            raise HTTPException(403, "Cannot edit a principle belonging to another org")
    await db.value_principles.update_one({"id": principle_id}, {"$set": p.model_dump()})
    return {"ok": True}


@router.delete("/principles/{principle_id}")
async def delete_principle(principle_id: str, user: dict = Depends(get_current_user)):
    existing = await db.value_principles.find_one({"id": principle_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Principle not found")
    if existing.get("platform_default"):
        raise HTTPException(400, "Platform-default principles cannot be deleted")
    role = get_user_role(user)
    if existing.get("org_id") != user.get("org_id") and role not in ADMIN_ROLES:
        raise HTTPException(403, "Cannot delete a principle belonging to another org")
    await db.value_principles.delete_one({"id": principle_id})
    return {"ok": True}


# ============================================================
# Daily Reflection (5 questions × N modules)
# ============================================================
@router.post("/reflect")
async def submit_reflection(r: ReflectionIn, user: dict = Depends(get_current_user)):
    if r.module_ref not in REFLECTION_MODULES:
        raise HTTPException(400, f"module_ref must be one of {REFLECTION_MODULES}")
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        **r.model_dump(),
        "created_at": _now(),
    }
    await db.value_reflections.insert_one(doc)
    # Also ping the Consciousness Diary's wellness collection so the existing
    # `/wellness` tab can show these without a duplicate query.
    try:
        await db.consciousness_diary_entries.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user["user_id"],
            "kind": "values_reflection",
            "ref_id": doc["id"],
            "module_ref": r.module_ref,
            "summary": (r.challenging_situation or "")[:200],
            "created_at": _now(),
        })
    except Exception as e:
        logger.warning("consciousness diary tie-in failed: %s", e)
    doc.pop("_id", None)
    return {"reflection": doc}


@router.get("/reflections")
async def list_reflections(module_ref: Optional[str] = None, limit: int = 100, user: dict = Depends(get_current_user)):
    q: Dict[str, Any] = {"user_id": user["user_id"]}
    if module_ref:
        q["module_ref"] = module_ref
    rows = await db.value_reflections.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return {"reflections": rows}


# ============================================================
# AI Advisor — alignment check on a situation
# ============================================================
@router.post("/ai-advisor")
async def ai_advise(payload: AdvisorIn, user: dict = Depends(get_current_user)):
    principles = await _resolved_principles_for(user, payload.org_id)
    # Build a compact prompt; we only ship principle name + short summary + bullets.
    p_text = "\n".join(
        f"- [{p['code']}] {p['name']}: {p.get('short') or p['body'][:160]}"
        for p in principles
    )
    prompt = (
        "You are the VEALES Collaboration Principles Advisor. Pick the TOP "
        f"{max(1, min(8, payload.use_top_n))} principles most relevant to the user's situation. "
        "For each, return: (1) why it applies, (2) alignment_score (0-10) of what the user "
        "is currently doing, (3) one concrete DO action, (4) one concrete DON'T action. "
        "Respond as a JSON object: { picks: [{code, alignment_score, why, do, dont}] }.\n\n"
        f"PRINCIPLES:\n{p_text}\n\nUSER SITUATION:\n{payload.situation}"
    )
    # Use Emergent LLM — defer import so module loads cleanly when key absent.
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=os.getenv("EMERGENT_LLM_KEY") or "",
            session_id=f"values-advisor-{user['user_id']}",
            system_message="Return ONLY a strict JSON object as instructed. No commentary.",
        ).with_model("anthropic", "claude-haiku-4-5")
        reply = await chat.send_message(UserMessage(text=prompt))
        text = (reply or "").strip()
        # Best-effort JSON extraction
        import json, re
        m = re.search(r"\{.*\}", text, re.DOTALL)
        parsed = json.loads(m.group(0) if m else text)
    except Exception as e:
        logger.warning("values ai advisor fell back to heuristic: %s", e)
        # Heuristic fallback: pick first N principles, give a neutral 5/10.
        parsed = {"picks": [
            {"code": p["code"], "alignment_score": 5, "why": "Likely relevant — AI offline, heuristic match.",
             "do": "Reflect on this principle deliberately.",
             "dont": "Skip introspection."}
            for p in principles[:payload.use_top_n]
        ]}
    # Log invocation
    await db.value_advisor_invocations.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "situation_excerpt": payload.situation[:500],
        "result": parsed,
        "created_at": _now(),
    })
    return parsed


# ============================================================
# Admin settings (blocking threshold, etc.)
# ============================================================
@router.get("/settings")
async def get_settings(user: dict = Depends(get_current_user)):
    cfg = await db.values_settings.find_one({"_id": "global"}, {"_id": 0}) or {
        "public_block_threshold": None,      # None = warn+log only
        "org_block_threshold_default": None,  # per-org override goes in user.org doc
    }
    return cfg


@router.put("/settings")
async def put_settings(payload: dict, user: dict = Depends(get_current_user)):
    if get_user_role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "Platform admin only")
    await db.values_settings.update_one({"_id": "global"}, {"$set": payload}, upsert=True)
    return {"ok": True}
