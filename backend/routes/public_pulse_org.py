"""Public Pulse Phase 2 — Org / Gov / Admin portals.

Features:
  - Org application submission (with admin-configurable eligibility)
  - Admin moderation queue (approve / reject with cooldown enforcement)
  - Org team management (invite / remove members)
  - Org dashboard (filtered aggregates, k-anonymity enforced)
  - Rectification workflow (acknowledge → respond → action_taken → close)
  - Feedback auto-routing (exact → fuzzy → district) with citizen confirmation
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request

from core.database import db
from core.auth import get_current_user, require_admin
from models.public_pulse_org_models import (
    ORG_TYPES, ORG_STATUSES, ORG_MEMBER_ROLES,
    DEFAULT_ADMIN_CONFIG,
    AdminConfigUpdate,
    OrgApplicationSubmit, OrgApplication, OrgApplicationReview,
    PPOrg, PPOrgMember, OrgInviteRequest,
    FeedbackRoutingConfirm, FeedbackOrgAction, FEEDBACK_ACTION_TRANSITIONS,
)

router = APIRouter(prefix="/public-pulse", tags=["Public Pulse — Orgs"])


# ============================================================
# ADMIN CONFIG (runtime-tunable org behavior)
# ============================================================

async def _get_config(key: str) -> Any:
    """Read admin config for a key. Falls back to DEFAULT_ADMIN_CONFIG."""
    doc = await db.pp_admin_config.find_one({"key": key}, {"_id": 0})
    if doc:
        return doc.get("value")
    return DEFAULT_ADMIN_CONFIG.get(key)


def _resolve_by_org_type(config_block: Dict, org_type: str) -> Any:
    """Given a `{default, overrides}` block, return the org-type-specific value."""
    if not config_block:
        return None
    overrides = config_block.get("overrides", {})
    return overrides.get(org_type, config_block.get("default"))


@router.get("/admin/config")
async def get_admin_config(user: dict = Depends(require_admin)):
    """Get all tunable admin config (merged with defaults)."""
    out = {}
    for key, default_value in DEFAULT_ADMIN_CONFIG.items():
        doc = await db.pp_admin_config.find_one({"key": key}, {"_id": 0})
        out[key] = doc["value"] if doc else default_value
    out["org_types"] = ORG_TYPES
    return out


@router.put("/admin/config")
async def put_admin_config(req: AdminConfigUpdate, user: dict = Depends(require_admin)):
    """Update an admin config block."""
    if req.key not in DEFAULT_ADMIN_CONFIG:
        raise HTTPException(400, f"Unknown config key. Valid: {list(DEFAULT_ADMIN_CONFIG.keys())}")
    await db.pp_admin_config.update_one(
        {"key": req.key},
        {"$set": {"key": req.key, "value": req.value, "updated_by": user["user_id"], "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    await db.pp_audit_logs.insert_one({
        "user_id": user["user_id"],
        "action": "admin_config_update",
        "details": {"key": req.key},
        "timestamp": datetime.now(timezone.utc),
    })
    return {"ok": True, "key": req.key, "value": req.value}


# ============================================================
# ORG APPLICATION — submit, list own, review (admin)
# ============================================================

@router.get("/orgs/types")
async def get_org_types():
    """Public — list org types for the application form."""
    return {"types": ORG_TYPES}


async def _check_application_eligibility(user_id: str, org_type: str) -> List[str]:
    """Returns a list of blocker messages; empty means eligible."""
    cfg = await _get_config("application_eligibility") or DEFAULT_ADMIN_CONFIG["application_eligibility"]
    rules = _resolve_by_org_type(cfg, org_type) or cfg.get("default", {})
    blockers = []

    if rules.get("require_tool_use"):
        sessions = await db.pp_tool_sessions.count_documents(
            {"user_id": user_id, "completed": True}
        )
        if sessions < 1:
            blockers.append("Complete at least one Public Pulse tool before applying.")

    if rules.get("require_email_verified"):
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if user and not user.get("email_verified", False):
            blockers.append("Verify your email first.")

    # Check cooldown — most recent rejected application
    cooldown_cfg = await _get_config("reapply_cooldown_days") or DEFAULT_ADMIN_CONFIG["reapply_cooldown_days"]
    cooldown_days = _resolve_by_org_type(cooldown_cfg, org_type)
    if cooldown_days:
        last_rejected = await db.pp_org_applications.find_one(
            {"user_id": user_id, "org_type": org_type, "status": "rejected"},
            sort=[("reviewed_at", -1)],
        )
        if last_rejected and last_rejected.get("reviewed_at"):
            reviewed_at = last_rejected["reviewed_at"]
            if not isinstance(reviewed_at, datetime):
                # Motor sometimes returns datetime naive — normalise
                reviewed_at = datetime.fromisoformat(str(reviewed_at).replace("Z", "+00:00"))
            # Ensure tz-aware
            if reviewed_at.tzinfo is None:
                reviewed_at = reviewed_at.replace(tzinfo=timezone.utc)
            cooldown_until = reviewed_at + timedelta(days=cooldown_days)
            now = datetime.now(timezone.utc)
            if now < cooldown_until:
                days_left = (cooldown_until - now).days + 1
                blockers.append(f"Please wait {days_left} more day(s) before re-applying as this org type.")

    # Check for an existing pending application of the same type
    pending = await db.pp_org_applications.find_one(
        {"user_id": user_id, "org_type": org_type, "status": "pending"}
    )
    if pending:
        blockers.append("You already have a pending application for this org type.")

    return blockers


@router.get("/orgs/eligibility/{org_type}")
async def check_eligibility(org_type: str, user: dict = Depends(get_current_user)):
    """Client-side precheck — shows why a user cannot apply (if any)."""
    blockers = await _check_application_eligibility(user["user_id"], org_type)
    return {"eligible": len(blockers) == 0, "blockers": blockers}


@router.post("/orgs/apply")
async def submit_application(req: OrgApplicationSubmit, user: dict = Depends(get_current_user)):
    """Submit a new org application."""
    valid_types = {t["code"] for t in ORG_TYPES}
    if req.org_type not in valid_types:
        raise HTTPException(400, f"Invalid org_type. Valid: {list(valid_types)}")

    blockers = await _check_application_eligibility(user["user_id"], req.org_type)
    if blockers:
        raise HTTPException(403, detail={"code": "not_eligible", "blockers": blockers})

    app = OrgApplication(user_id=user["user_id"], **req.dict())
    await db.pp_org_applications.insert_one(app.dict())
    await db.pp_audit_logs.insert_one({
        "user_id": user["user_id"],
        "action": "org_application_submit",
        "details": {"application_id": app.application_id, "org_type": req.org_type},
        "timestamp": datetime.now(timezone.utc),
    })
    out = app.dict()
    # Strip heavy doc fields from response to save bandwidth
    for fld in ("verification_doc_b64", "authorized_id_b64", "brand_logo_b64"):
        out[fld] = "[uploaded]" if out.get(fld) else None
    return {"ok": True, "application": out}


@router.get("/orgs/my-applications")
async def my_applications(user: dict = Depends(get_current_user)):
    """List the current user's applications (any status)."""
    apps = await db.pp_org_applications.find(
        {"user_id": user["user_id"]}, {"_id": 0, "verification_doc_b64": 0, "authorized_id_b64": 0, "brand_logo_b64": 0},
    ).sort("submitted_at", -1).to_list(50)
    return {"applications": apps}


@router.get("/orgs/my-application/{application_id}")
async def my_application_detail(application_id: str, user: dict = Depends(get_current_user)):
    app = await db.pp_org_applications.find_one(
        {"application_id": application_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not app:
        raise HTTPException(404, "Application not found")
    return app


# ============================================================
# ADMIN MODERATION QUEUE
# ============================================================

@router.get("/admin/orgs/pending")
async def admin_pending(user: dict = Depends(require_admin)):
    """Admin queue — all pending applications (docs included)."""
    apps = await db.pp_org_applications.find(
        {"status": "pending"}, {"_id": 0},
    ).sort("submitted_at", 1).to_list(200)
    return {"count": len(apps), "applications": apps}


@router.get("/admin/orgs/all")
async def admin_all_applications(
    status: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    """Admin — all applications, optionally filtered by status."""
    q: Dict[str, Any] = {}
    if status:
        if status not in ORG_STATUSES:
            raise HTTPException(400, f"Invalid status. Valid: {ORG_STATUSES}")
        q["status"] = status
    apps = await db.pp_org_applications.find(
        q, {"_id": 0, "verification_doc_b64": 0, "authorized_id_b64": 0, "brand_logo_b64": 0},
    ).sort("submitted_at", -1).limit(500).to_list(500)
    return {"count": len(apps), "applications": apps}


@router.get("/admin/orgs/application/{application_id}")
async def admin_application_detail(application_id: str, user: dict = Depends(require_admin)):
    app = await db.pp_org_applications.find_one({"application_id": application_id}, {"_id": 0})
    if not app:
        raise HTTPException(404, "Not found")
    return app


@router.post("/admin/orgs/application/{application_id}/review")
async def admin_review(
    application_id: str,
    req: OrgApplicationReview,
    user: dict = Depends(require_admin),
):
    """Approve or reject an application. On approve, creates a PPOrg + adds applicant as org_admin."""
    app = await db.pp_org_applications.find_one({"application_id": application_id}, {"_id": 0})
    if not app:
        raise HTTPException(404, "Application not found")
    if app["status"] != "pending":
        raise HTTPException(400, f"Application already {app['status']}")

    decision = req.decision.lower()
    if decision not in ("approve", "reject"):
        raise HTTPException(400, "decision must be 'approve' or 'reject'")

    now = datetime.now(timezone.utc)
    update = {"reviewed_by": user["user_id"], "reviewed_at": now}

    if decision == "approve":
        org = PPOrg(
            application_id=application_id,
            owner_user_id=app["user_id"],
            org_type=app["org_type"],
            display_name=app["display_name"],
            legal_name=app.get("legal_name"),
            about=app.get("about"),
            website=app.get("website"),
            email=app["email"],
            phone=app.get("phone"),
            state=app.get("state"),
            district=app.get("district"),
            categories=app.get("categories", []),
            brand_logo_b64=app.get("brand_logo_b64"),
            brand_color=app.get("brand_color"),
        )
        # Generate a slug for future white-label portal URLs
        org.slug = app["display_name"].lower().replace(" ", "-")[:40] + "-" + org.org_id[:6]
        await db.pp_orgs.insert_one(org.dict())
        member = PPOrgMember(
            org_id=org.org_id,
            user_id=app["user_id"],
            role="org_admin",
            added_by=user["user_id"],
        )
        await db.pp_org_members.insert_one(member.dict())
        update["status"] = "approved"
        update["org_id"] = org.org_id
    else:
        update["status"] = "rejected"
        update["rejection_reason"] = req.reason or "Not specified"

    await db.pp_org_applications.update_one(
        {"application_id": application_id}, {"$set": update}
    )
    await db.pp_audit_logs.insert_one({
        "user_id": user["user_id"],
        "action": f"org_application_{decision}",
        "details": {"application_id": application_id, "reason": req.reason},
        "timestamp": now,
    })

    # Notify applicant
    await db.notifications.insert_one({
        "user_id": app["user_id"],
        "type": "public_pulse_org_review",
        "title": f"Your org application was {decision}d",
        "message": (f"Welcome! '{app['display_name']}' is now active on Public Pulse."
                    if decision == "approve"
                    else f"Reason: {req.reason or 'Not specified'}"),
        "read": False,
        "created_at": now,
    })

    return {"ok": True, "status": update["status"], "org_id": update.get("org_id")}


# ============================================================
# ORG CONTEXT — resolve current user's active orgs
# ============================================================

async def _get_user_orgs(user_id: str) -> List[Dict]:
    """Return all orgs where the user is an approved member, with role info."""
    members = await db.pp_org_members.find({"user_id": user_id}, {"_id": 0}).to_list(50)
    if not members:
        return []
    org_ids = [m["org_id"] for m in members]
    orgs = await db.pp_orgs.find(
        {"org_id": {"$in": org_ids}, "status": "approved"}, {"_id": 0}
    ).to_list(50)
    org_map = {o["org_id"]: o for o in orgs}
    result = []
    for m in members:
        o = org_map.get(m["org_id"])
        if o:
            result.append({**o, "my_role": m["role"]})
    return result


@router.get("/orgs/my-orgs")
async def my_orgs(user: dict = Depends(get_current_user)):
    """List orgs the current user is a member of (post-approval)."""
    orgs = await _get_user_orgs(user["user_id"])
    return {"orgs": orgs}


@router.get("/orgs/{org_id}")
async def get_org(org_id: str, user: dict = Depends(get_current_user)):
    """Get org profile — accessible to members (full) or public (limited)."""
    org = await db.pp_orgs.find_one({"org_id": org_id, "status": "approved"}, {"_id": 0})
    if not org:
        raise HTTPException(404, "Org not found")
    # Check membership
    member = await db.pp_org_members.find_one({"org_id": org_id, "user_id": user["user_id"]}, {"_id": 0})
    if not member:
        # Public view — strip internal fields
        return {
            "org_id": org["org_id"],
            "display_name": org["display_name"],
            "org_type": org["org_type"],
            "about": org.get("about"),
            "website": org.get("website"),
            "state": org.get("state"),
            "district": org.get("district"),
            "brand_logo_b64": org.get("brand_logo_b64"),
            "brand_color": org.get("brand_color"),
            "categories": org.get("categories", []),
        }
    return {**org, "my_role": member["role"]}


@router.post("/orgs/{org_id}/invite")
async def invite_member(
    org_id: str,
    req: OrgInviteRequest,
    user: dict = Depends(get_current_user),
):
    """Org admin invites a user by email to join the org."""
    member = await db.pp_org_members.find_one(
        {"org_id": org_id, "user_id": user["user_id"], "role": "org_admin"}
    )
    if not member:
        raise HTTPException(403, "Only org admins can invite members")
    if req.role not in ORG_MEMBER_ROLES:
        raise HTTPException(400, f"Invalid role. Valid: {ORG_MEMBER_ROLES}")

    invitee = await db.users.find_one({"email": req.email.lower()}, {"_id": 0})
    if not invitee:
        raise HTTPException(404, "User with that email not found. They must register first.")

    existing = await db.pp_org_members.find_one({"org_id": org_id, "user_id": invitee["user_id"]})
    if existing:
        raise HTTPException(400, "User is already a member of this org")

    new_member = PPOrgMember(
        org_id=org_id,
        user_id=invitee["user_id"],
        role=req.role,
        added_by=user["user_id"],
    )
    await db.pp_org_members.insert_one(new_member.dict())
    await db.pp_orgs.update_one({"org_id": org_id}, {"$inc": {"active_member_count": 1}})
    await db.notifications.insert_one({
        "user_id": invitee["user_id"],
        "type": "public_pulse_org_invite",
        "title": "You've been added to an organization",
        "message": f"You're now a {req.role} of an org on Public Pulse.",
        "read": False,
        "created_at": datetime.now(timezone.utc),
    })
    return {"ok": True, "member": new_member.dict()}


@router.get("/orgs/{org_id}/members")
async def list_members(org_id: str, user: dict = Depends(get_current_user)):
    member = await db.pp_org_members.find_one({"org_id": org_id, "user_id": user["user_id"]})
    if not member:
        raise HTTPException(403, "Not a member of this org")
    members = await db.pp_org_members.find({"org_id": org_id}, {"_id": 0}).to_list(200)
    # Hydrate with user names
    user_ids = [m["user_id"] for m in members]
    users = await db.users.find({"user_id": {"$in": user_ids}}, {"_id": 0, "user_id": 1, "name": 1, "email": 1}).to_list(200)
    user_map = {u["user_id"]: u for u in users}
    hydrated = [{**m, "name": user_map.get(m["user_id"], {}).get("name"), "email": user_map.get(m["user_id"], {}).get("email")} for m in members]
    return {"members": hydrated}


# ============================================================
# ORG DASHBOARD — filtered aggregates
# ============================================================

@router.get("/orgs/{org_id}/dashboard")
async def org_dashboard(
    org_id: str,
    district: Optional[str] = None,
    age_group: Optional[str] = None,
    tool_slug: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """Filtered aggregate view for verified orgs — k-anonymity enforced."""
    member = await db.pp_org_members.find_one({"org_id": org_id, "user_id": user["user_id"]})
    if not member:
        raise HTTPException(403, "Not a member of this org")
    org = await db.pp_orgs.find_one({"org_id": org_id}, {"_id": 0})
    if not org:
        raise HTTPException(404, "Org not found")

    # Build filter
    match: Dict[str, Any] = {
        "completed": True,
        "contributed_to_research": True,
    }
    if district or org.get("district"):
        match["answers.district"] = {"$regex": f"^{district or org['district']}$", "$options": "i"}
    if age_group:
        match["answers.age_group"] = age_group
    if tool_slug:
        match["answers.tool_slug"] = tool_slug
        match["tool_slug"] = tool_slug

    # Get k-threshold
    k_cfg = await db.pp_config.find_one({"key": "k_thresholds"}, {"_id": 0})
    from models.public_pulse_models import DEFAULT_K_THRESHOLDS
    k = (k_cfg or {}).get("values", {}).get("org_dashboard", DEFAULT_K_THRESHOLDS.get("district_demand_heatmap", 30))

    # Aggregates: by tool, by want, by biggest_concern, by biggest_need
    total = await db.pp_tool_sessions.count_documents(match)
    if total < k:
        return {
            "blocked": True,
            "reason": f"Insufficient sample size ({total} < {k})",
            "k_threshold": k,
            "filter": {"district": district, "age_group": age_group, "tool_slug": tool_slug},
        }

    pipelines = {
        "by_tool": [
            {"$match": match},
            {"$group": {"_id": "$tool_slug", "n": {"$sum": 1}}},
            {"$match": {"n": {"$gte": k}}},
            {"$sort": {"n": -1}},
        ],
        "by_age_group": [
            {"$match": match},
            {"$group": {"_id": "$answers.age_group", "n": {"$sum": 1}}},
            {"$match": {"n": {"$gte": k}}},
            {"$sort": {"n": -1}},
        ],
        "by_district": [
            {"$match": match},
            {"$group": {"_id": "$answers.district", "n": {"$sum": 1}}},
            {"$match": {"n": {"$gte": k}}},
            {"$sort": {"n": -1}},
            {"$limit": 20},
        ],
        "by_career_want": [
            {"$match": {**match, "tool_slug": "life_direction"}},
            {"$group": {"_id": "$answers.want", "n": {"$sum": 1}}},
            {"$match": {"n": {"$gte": k}}},
            {"$sort": {"n": -1}},
        ],
        "by_biggest_need": [
            {"$match": {**match, "tool_slug": "govt_benefit_finder"}},
            {"$group": {"_id": "$answers.biggest_need", "n": {"$sum": 1}}},
            {"$match": {"n": {"$gte": k}}},
            {"$sort": {"n": -1}},
        ],
    }

    result: Dict[str, List] = {}
    for key, pipeline in pipelines.items():
        rows = await db.pp_tool_sessions.aggregate(pipeline).to_list(50)
        result[key] = [{"label": r["_id"], "count": r["n"]} for r in rows if r["_id"] is not None]

    return {
        "blocked": False,
        "k_threshold": k,
        "total_in_aggregate": total,
        "filter": {"district": district, "age_group": age_group, "tool_slug": tool_slug},
        "aggregates": result,
        "org": {
            "display_name": org["display_name"],
            "org_type": org["org_type"],
            "district": org.get("district"),
        },
    }


# ============================================================
# FEEDBACK ROUTING — auto-route exact, suggest for fuzzy
# ============================================================

async def _suggest_orgs_for_feedback(feedback_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Returns either {auto_route_to: org_id} or {suggestions: [...]}.

    Cascade:
      1. Exact display_name match on related_entity → auto-route
      2. Fuzzy match (case-insensitive substring) → suggest
      3. District match (if feedback has district, any org with matching district) → suggest
    Merges categories to boost score if feedback_type aligns with org categories.
    """
    related = (feedback_doc.get("related_entity") or "").strip()
    district = (feedback_doc.get("district") or "").strip()

    routing_cfg = await _get_config("feedback_routing") or DEFAULT_ADMIN_CONFIG["feedback_routing"]
    rules = routing_cfg.get("default", {})
    suggestion_count = int(rules.get("suggestion_count", 3))

    # 1. Exact match
    if related and rules.get("auto_route_exact_match", True):
        exact = await db.pp_orgs.find_one(
            {"status": "approved", "display_name": {"$regex": f"^{related}$", "$options": "i"}},
            {"_id": 0, "org_id": 1, "display_name": 1, "org_type": 1, "district": 1},
        )
        if exact:
            return {"auto_route_to": exact["org_id"], "matched_org": exact, "match_type": "exact"}

    # 2. Fuzzy (partial) match
    suggestions: List[Dict[str, Any]] = []
    if related and rules.get("confirm_fuzzy_match", True):
        cursor = db.pp_orgs.find(
            {"status": "approved", "display_name": {"$regex": related, "$options": "i"}},
            {"_id": 0, "org_id": 1, "display_name": 1, "org_type": 1, "district": 1},
        ).limit(suggestion_count * 2)
        async for o in cursor:
            suggestions.append({**o, "reason": f"Name similar to '{related}'", "score": 70, "match_type": "fuzzy"})

    # 3. District fallback
    if district and len(suggestions) < suggestion_count and rules.get("confirm_district_match", True):
        already = {s["org_id"] for s in suggestions}
        cursor = db.pp_orgs.find(
            {"status": "approved", "district": {"$regex": f"^{district}$", "$options": "i"},
             "org_id": {"$nin": list(already)}},
            {"_id": 0, "org_id": 1, "display_name": 1, "org_type": 1, "district": 1},
        ).limit(suggestion_count)
        async for o in cursor:
            suggestions.append({**o, "reason": f"Active in {district}", "score": 50, "match_type": "district"})

    # Sort by score, take top N
    suggestions.sort(key=lambda s: s["score"], reverse=True)
    return {"suggestions": suggestions[:suggestion_count], "match_type": "none" if not suggestions else "fuzzy_or_district"}


@router.post("/feedback/{feedback_id}/route")
async def compute_routing(feedback_id: str, user: dict = Depends(get_current_user)):
    """Compute (or re-compute) routing suggestions for a feedback item.

    If exact match, auto-routes and returns {auto_routed: true}.
    Otherwise returns {suggestions: [...]} for citizen to pick from.
    """
    item = await db.pp_feedback_items.find_one({"feedback_id": feedback_id, "user_id": user["user_id"]}, {"_id": 0})
    if not item:
        raise HTTPException(404, "Feedback not found")

    routing = await _suggest_orgs_for_feedback(item)
    if routing.get("auto_route_to"):
        await db.pp_feedback_items.update_one(
            {"feedback_id": feedback_id},
            {"$set": {
                "routing_status": "auto_routed",
                "assigned_org_id": routing["auto_route_to"],
                "status": "auto_routed",
                "updated_at": datetime.now(timezone.utc),
            }},
        )
        return {"auto_routed": True, "org": routing["matched_org"]}

    # Save suggestions for later citizen confirmation
    await db.pp_feedback_items.update_one(
        {"feedback_id": feedback_id},
        {"$set": {
            "routing_status": "awaiting_citizen_confirm",
            "suggested_orgs": routing.get("suggestions", []),
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    return {"auto_routed": False, "suggestions": routing.get("suggestions", [])}


@router.post("/feedback/{feedback_id}/confirm-route")
async def confirm_route(
    feedback_id: str,
    req: FeedbackRoutingConfirm,
    user: dict = Depends(get_current_user),
):
    """Citizen picks one of the suggested orgs."""
    item = await db.pp_feedback_items.find_one({"feedback_id": feedback_id, "user_id": user["user_id"]}, {"_id": 0})
    if not item:
        raise HTTPException(404, "Feedback not found")
    suggestions = item.get("suggested_orgs") or []
    if not any(s["org_id"] == req.org_id for s in suggestions):
        raise HTTPException(400, "org_id not in suggestions list")

    await db.pp_feedback_items.update_one(
        {"feedback_id": feedback_id},
        {"$set": {
            "routing_status": "routed",
            "assigned_org_id": req.org_id,
            "status": "routed",
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    return {"ok": True, "assigned_org_id": req.org_id}


@router.post("/feedback/{feedback_id}/skip-routing")
async def skip_routing(feedback_id: str, user: dict = Depends(get_current_user)):
    """Citizen declines all suggestions — feedback escalates to admin triage."""
    item = await db.pp_feedback_items.find_one({"feedback_id": feedback_id, "user_id": user["user_id"]}, {"_id": 0})
    if not item:
        raise HTTPException(404, "Feedback not found")
    await db.pp_feedback_items.update_one(
        {"feedback_id": feedback_id},
        {"$set": {
            "routing_status": "escalated_to_admin",
            "status": "new",
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    return {"ok": True, "message": "Escalated to admin triage"}


# ============================================================
# ORG-SIDE FEEDBACK QUEUE (Rectification)
# ============================================================

async def _can_view_feedback(user_id: str, org_id: str, feedback: Dict) -> bool:
    """Check feedback visibility rules for the user."""
    member = await db.pp_org_members.find_one({"org_id": org_id, "user_id": user_id}, {"_id": 0})
    if not member:
        return False
    if member["role"] == "org_admin":
        return True

    org = await db.pp_orgs.find_one({"org_id": org_id}, {"_id": 0})
    if not org:
        return False
    vis_cfg = await _get_config("feedback_visibility") or DEFAULT_ADMIN_CONFIG["feedback_visibility"]
    policy = _resolve_by_org_type(vis_cfg, org["org_type"]) or "all_members"

    if policy == "all_members":
        return True
    if policy == "admin_only":
        return False  # already handled org_admin above
    if policy == "first_come":
        claimed = feedback.get("claimed_by_user_id")
        return (not claimed) or claimed == user_id
    return False


@router.get("/orgs/{org_id}/feedback/queue")
async def org_feedback_queue(
    org_id: str,
    status: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """List incoming feedback routed to this org (filtered by visibility policy)."""
    member = await db.pp_org_members.find_one({"org_id": org_id, "user_id": user["user_id"]}, {"_id": 0})
    if not member:
        raise HTTPException(403, "Not a member of this org")
    org = await db.pp_orgs.find_one({"org_id": org_id}, {"_id": 0})
    if not org:
        raise HTTPException(404, "Org not found")

    vis_cfg = await _get_config("feedback_visibility") or DEFAULT_ADMIN_CONFIG["feedback_visibility"]
    policy = _resolve_by_org_type(vis_cfg, org["org_type"]) or "all_members"

    q: Dict[str, Any] = {"assigned_org_id": org_id}
    if status:
        q["status"] = status

    if member["role"] != "org_admin":
        if policy == "admin_only":
            raise HTTPException(403, "Only org admins can view the feedback queue for this org type")
        elif policy == "first_come":
            q["$or"] = [{"claimed_by_user_id": {"$exists": False}}, {"claimed_by_user_id": None}, {"claimed_by_user_id": user["user_id"]}]

    items = await db.pp_feedback_items.find(q, {"_id": 0}).sort("created_at", -1).limit(200).to_list(200)
    return {
        "count": len(items),
        "items": items,
        "org_type": org["org_type"],
        "visibility_policy": policy,
    }


@router.post("/orgs/{org_id}/feedback/{feedback_id}/claim")
async def claim_feedback(
    org_id: str,
    feedback_id: str,
    user: dict = Depends(get_current_user),
):
    """First-come-basis claim — used when visibility policy is 'first_come'."""
    member = await db.pp_org_members.find_one({"org_id": org_id, "user_id": user["user_id"]})
    if not member:
        raise HTTPException(403, "Not a member of this org")
    item = await db.pp_feedback_items.find_one({"feedback_id": feedback_id, "assigned_org_id": org_id})
    if not item:
        raise HTTPException(404, "Feedback not found or not assigned to your org")
    if item.get("claimed_by_user_id") and item["claimed_by_user_id"] != user["user_id"]:
        raise HTTPException(400, "Already claimed by another member")
    await db.pp_feedback_items.update_one(
        {"feedback_id": feedback_id},
        {"$set": {
            "claimed_by_user_id": user["user_id"],
            "claimed_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    return {"ok": True, "claimed_by": user["user_id"]}


@router.post("/orgs/{org_id}/feedback/{feedback_id}/action")
async def feedback_action(
    org_id: str,
    feedback_id: str,
    req: FeedbackOrgAction,
    user: dict = Depends(get_current_user),
):
    """Unified action endpoint — acknowledge, respond, action_taken, close, reopen."""
    member = await db.pp_org_members.find_one({"org_id": org_id, "user_id": user["user_id"]}, {"_id": 0})
    if not member:
        raise HTTPException(403, "Not a member of this org")
    item = await db.pp_feedback_items.find_one(
        {"feedback_id": feedback_id, "assigned_org_id": org_id}, {"_id": 0}
    )
    if not item:
        raise HTTPException(404, "Feedback not found or not assigned to your org")

    # Visibility check — can this member even touch this item?
    if not await _can_view_feedback(user["user_id"], org_id, item):
        raise HTTPException(403, "You do not have permission to act on this feedback")

    transition = FEEDBACK_ACTION_TRANSITIONS.get(req.action)
    if not transition:
        raise HTTPException(400, f"Invalid action. Valid: {list(FEEDBACK_ACTION_TRANSITIONS.keys())}")

    if item["status"] not in transition["from"]:
        raise HTTPException(
            400,
            f"Cannot {req.action} from status '{item['status']}'. Allowed from: {transition['from']}",
        )

    update: Dict[str, Any] = {
        "status": transition["to"],
        "updated_at": datetime.now(timezone.utc),
    }
    if req.action == "respond" and req.response_text:
        update["response_text"] = req.response_text
        update["response_org_id"] = org_id
    if req.action == "action_taken":
        if req.action_taken_description:
            update["action_taken_description"] = req.action_taken_description
        update["action_taken_date"] = req.action_taken_date or datetime.now(timezone.utc)

    await db.pp_feedback_items.update_one({"feedback_id": feedback_id}, {"$set": update})

    # Notify citizen
    await db.notifications.insert_one({
        "user_id": item["user_id"],
        "type": "public_pulse_feedback_update",
        "title": f"Your feedback was {transition['to'].replace('_', ' ')}",
        "message": req.response_text or req.action_taken_description or f"Status: {transition['to']}",
        "data": {"feedback_id": feedback_id, "org_id": org_id},
        "read": False,
        "created_at": datetime.now(timezone.utc),
    })

    await db.pp_audit_logs.insert_one({
        "user_id": user["user_id"],
        "action": f"feedback_{req.action}",
        "details": {"feedback_id": feedback_id, "org_id": org_id, "new_status": transition["to"]},
        "timestamp": datetime.now(timezone.utc),
    })

    # Increment org counter if feedback closed with resolution
    if transition["to"] in ("closed", "action_taken"):
        await db.pp_orgs.update_one({"org_id": org_id}, {"$inc": {"total_feedback_handled": 1}})

    return {"ok": True, "new_status": transition["to"]}


# ============================================================
# ADMIN — audit logs + escalated feedback
# ============================================================

@router.get("/admin/audit-logs")
async def admin_audit_logs(
    limit: int = 100,
    action: Optional[str] = None,
    user: dict = Depends(require_admin),
):
    q: Dict[str, Any] = {}
    if action:
        q["action"] = action
    logs = await db.pp_audit_logs.find(q, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    return {"count": len(logs), "logs": logs}


@router.get("/admin/feedback/escalated")
async def admin_escalated_feedback(user: dict = Depends(require_admin)):
    """Feedback items that need admin-level attention."""
    items = await db.pp_feedback_items.find(
        {"routing_status": "escalated_to_admin"}, {"_id": 0},
    ).sort("created_at", -1).limit(200).to_list(200)
    return {"count": len(items), "items": items}


@router.post("/admin/feedback/{feedback_id}/assign-to-org")
async def admin_assign_feedback(
    feedback_id: str,
    org_id: str,
    user: dict = Depends(require_admin),
):
    """Admin manually assigns an escalated feedback to a specific org."""
    item = await db.pp_feedback_items.find_one({"feedback_id": feedback_id}, {"_id": 0})
    if not item:
        raise HTTPException(404, "Feedback not found")
    org = await db.pp_orgs.find_one({"org_id": org_id, "status": "approved"}, {"_id": 0})
    if not org:
        raise HTTPException(404, "Org not found or not approved")

    await db.pp_feedback_items.update_one(
        {"feedback_id": feedback_id},
        {"$set": {
            "assigned_org_id": org_id,
            "routing_status": "routed",
            "status": "routed",
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    await db.pp_audit_logs.insert_one({
        "user_id": user["user_id"],
        "action": "admin_assign_feedback",
        "details": {"feedback_id": feedback_id, "org_id": org_id},
        "timestamp": datetime.now(timezone.utc),
    })
    return {"ok": True, "assigned_org_id": org_id}
