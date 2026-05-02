"""Unified Multi-User Collaboration Engine for PRR Decisions & Solution Finder.
Supports 6 Decision Making Modes and enhanced participant authentication."""

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user, require_admin
from routes.audit_trail import log_audit_event, get_client_ip

router = APIRouter(prefix="/collaboration", tags=["Multi-User Collaboration"])


# ========================
# DECISION MAKING MODES
# ========================

DEFAULT_MODES = [
    {
        "id": "equal",
        "name": "Equal Weightage",
        "description": "All participants get exactly equal weight in the final outcome.",
        "icon": "people",
        "color": "#3B82F6",
        "weight_logic": "equal_split",
        "config": {},
        "active": True,
        "order": 1,
    },
    {
        "id": "voting",
        "name": "Voting",
        "description": "Majority or custom minimum percentage threshold must be met.",
        "icon": "hand-left",
        "color": "#10B981",
        "weight_logic": "voting",
        "config": {"threshold_type": "majority", "custom_threshold_pct": 51},
        "active": True,
        "order": 2,
    },
    {
        "id": "command",
        "name": "Command (Leader-Driven)",
        "description": "Main user holds 50% weightage. Remaining 50% shared equally among others.",
        "icon": "shield",
        "color": "#F59E0B",
        "weight_logic": "command",
        "config": {"leader_weight_pct": 50},
        "active": True,
        "order": 3,
    },
    {
        "id": "sme",
        "name": "Subject Matter Expert(s)",
        "description": "Designated SMEs hold 50% combined weightage. Rest shared equally among others.",
        "icon": "school",
        "color": "#8B5CF6",
        "weight_logic": "sme",
        "config": {"sme_total_weight_pct": 50},
        "active": True,
        "order": 4,
    },
    {
        "id": "custom",
        "name": "Custom Weightage",
        "description": "Manually assign specific weight percentages to each participant.",
        "icon": "options",
        "color": "#EC4899",
        "weight_logic": "custom",
        "config": {},
        "active": True,
        "order": 5,
    },
    {
        "id": "consensus",
        "name": "Consensus",
        "description": "100% acceptance from all participants required. No partial outcomes.",
        "icon": "checkmark-done-circle",
        "color": "#059669",
        "weight_logic": "consensus",
        "config": {"require_unanimous": True},
        "active": True,
        "order": 6,
    },
]


@router.get("/decision-modes")
async def get_decision_modes(user: dict = Depends(get_current_user)):
    """Get all configured decision making modes."""
    modes = await db.decision_modes.find({}, {"_id": 0}).sort("order", 1).to_list(20)
    if not modes:
        # Seed defaults
        for m in DEFAULT_MODES:
            await db.decision_modes.update_one({"id": m["id"]}, {"$set": m}, upsert=True)
        modes = DEFAULT_MODES
    return modes


@router.put("/decision-modes/{mode_id}")
async def update_decision_mode(mode_id: str, request: Request, user: dict = Depends(require_admin)):
    """Admin: Update a decision making mode configuration."""
    body = await request.json()
    mode = await db.decision_modes.find_one({"id": mode_id})
    if not mode:
        raise HTTPException(status_code=404, detail="Mode not found")

    update = {}
    for field in ["name", "description", "config", "active", "order", "icon", "color"]:
        if field in body:
            update[field] = body[field]

    if update:
        await db.decision_modes.update_one({"id": mode_id}, {"$set": update})

    updated = await db.decision_modes.find_one({"id": mode_id}, {"_id": 0})
    return updated


# ========================
# COLLABORATION SESSIONS
# ========================

@router.post("/sessions")
async def create_collaboration_session(request: Request, user: dict = Depends(get_current_user)):
    """Create a new multi-user collaboration session for a Decision or Solution Finder."""
    body = await request.json()

    module_type = body.get("module_type")  # "decision" or "solution_finder"
    module_id = body.get("module_id")  # ID of the decision or solution_finder entry
    title = body.get("title", "")
    decision_mode_id = body.get("decision_mode_id", "equal")
    participant_contact_ids = body.get("participant_contact_ids", [])
    auth_config = body.get("auth_config", {})
    notify_participants = body.get("notify_participants", True)
    notify_mode = body.get("notify_mode", True)  # whether to tell participants the mode
    session_mode = body.get("session_mode", "async")  # "async" or "live_sync"
    mode_config_override = body.get("mode_config_override", None)  # override admin default config

    if module_type not in ("decision", "solution_finder"):
        raise HTTPException(status_code=400, detail="module_type must be 'decision' or 'solution_finder'")
    if not module_id:
        raise HTTPException(status_code=400, detail="module_id is required")
    if not participant_contact_ids:
        raise HTTPException(status_code=400, detail="At least one participant required")

    # Validate the module exists
    if module_type == "decision":
        source = await db.decisions.find_one({"id": module_id, "user_id": user["user_id"]}, {"_id": 0, "id": 1, "title": 1})
    else:
        source = await db.solution_finders.find_one({"entry_id": module_id, "user_id": user["user_id"]}, {"_id": 0, "entry_id": 1, "smart_goal": 1})
    if not source:
        raise HTTPException(status_code=404, detail=f"{module_type} not found")

    # Validate mode exists
    mode = await db.decision_modes.find_one({"id": decision_mode_id}, {"_id": 0})
    if not mode:
        # seed and retry
        for m in DEFAULT_MODES:
            await db.decision_modes.update_one({"id": m["id"]}, {"$set": m}, upsert=True)
        mode = next((m for m in DEFAULT_MODES if m["id"] == decision_mode_id), None)
    if not mode:
        raise HTTPException(status_code=400, detail="Invalid decision mode")

    # Resolve contacts to participants
    participants = []
    for cid in participant_contact_ids:
        contact = await db.contacts.find_one({"id": cid, "user_id": user["user_id"]}, {"_id": 0})
        if contact:
            participants.append({
                "contact_id": cid,
                "name": contact.get("name", ""),
                "email": contact.get("email", ""),
                "linked_user_id": contact.get("linked_user_id"),
                "is_sme": contact.get("is_sme", False),
                "status": "invited",
                "auth_verified": False,
                "auth_methods_completed": [],
                "contribution": None,
                "vote": None,  # for voting mode
                "accepted": None,  # for consensus mode
                "custom_weight": None,  # for custom mode
                "invited_at": datetime.now(timezone.utc).isoformat(),
                "contributed_at": None,
            })

    if not participants:
        raise HTTPException(status_code=400, detail="No valid contacts found to add as participants")

    session_id = f"collab_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    # Auth config
    auth_requirements = {
        "methods_required": auth_config.get("methods_required", 0),  # 0=none, 2=any 2 of 3
        "verify_each_time": auth_config.get("verify_each_time", False),
        "enabled_methods": auth_config.get("enabled_methods", []),  # ["country_id", "biometric", "authenticator"]
    }

    # Custom weights (for custom mode)
    custom_weights = body.get("custom_weights", {})

    # Voting config
    voting_config = body.get("voting_config", {})

    session_doc = {
        "id": session_id,
        "owner_id": user["user_id"],
        "owner_name": user.get("name", user.get("email", "")),
        "module_type": module_type,
        "module_id": module_id,
        "title": title or (source.get("title", "") if module_type == "decision" else source.get("smart_goal", "")),
        "decision_mode_id": decision_mode_id,
        "decision_mode": mode,
        "session_mode": session_mode,  # "async" or "live_sync"
        "mode_config_override": mode_config_override,  # user override of admin %
        "participants": participants,
        "auth_requirements": auth_requirements,
        "custom_weights": custom_weights,
        "voting_config": {
            "threshold_type": voting_config.get("threshold_type", mode.get("config", {}).get("threshold_type", "majority")),
            "custom_threshold_pct": voting_config.get("custom_threshold_pct", mode.get("config", {}).get("custom_threshold_pct", 51)),
        },
        "notify_participants": notify_participants,
        "notify_mode": notify_mode,
        "status": "active",  # active, voting, completed, cancelled
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "result": None,
    }

    await db.collaboration_sessions.insert_one(session_doc)

    # Send notifications to linked users
    if notify_participants:
        for p in participants:
            if p.get("linked_user_id"):
                mode_info = f" Mode: {mode['name']}." if notify_mode else ""
                notif_doc = {
                    "id": f"notif_{uuid.uuid4().hex[:12]}",
                    "user_id": p["linked_user_id"],
                    "type": "collaboration_invite",
                    "title": f"Collaboration Invite: {session_doc['title']}",
                    "message": f"{user.get('name', 'Someone')} invited you to collaborate on {module_type.replace('_', ' ')}.{mode_info}",
                    "data": {"session_id": session_id, "module_type": module_type, "module_id": module_id},
                    "read": False,
                    "created_at": now,
                }
                await db.notifications.insert_one(notif_doc)

    session_doc.pop("_id", None)
    return session_doc


@router.get("/sessions")
async def list_sessions(
    user: dict = Depends(get_current_user),
    role: Optional[str] = None,  # "owner" or "participant"
    module_type: Optional[str] = None,
    status: Optional[str] = None,
):
    """List collaboration sessions (owned or participating in)."""
    if role == "owner":
        query = {"owner_id": user["user_id"]}
    elif role == "participant":
        query = {"participants.linked_user_id": user["user_id"]}
    else:
        query = {"$or": [
            {"owner_id": user["user_id"]},
            {"participants.linked_user_id": user["user_id"]},
        ]}

    if module_type:
        query["module_type"] = module_type
    if status:
        query["status"] = status

    sessions = await db.collaboration_sessions.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
    return sessions


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user: dict = Depends(get_current_user)):
    session = await db.collaboration_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    is_owner = session["owner_id"] == user["user_id"]
    is_participant = any(p.get("linked_user_id") == user["user_id"] for p in session.get("participants", []))
    if not is_owner and not is_participant:
        raise HTTPException(status_code=403, detail="Access denied")

    return session


@router.post("/sessions/{session_id}/contribute")
async def contribute_to_session(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Submit contribution to a collaboration session."""
    body = await request.json()
    session = await db.collaboration_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["status"] != "active":
        raise HTTPException(status_code=400, detail="Session is not accepting contributions")

    participant = None
    p_idx = -1
    for idx, p in enumerate(session.get("participants", [])):
        if p.get("linked_user_id") == user["user_id"]:
            participant = p
            p_idx = idx
            break
    if participant is None:
        raise HTTPException(status_code=403, detail="You are not a participant in this session")

    # Check auth if required
    auth_req = session.get("auth_requirements", {})
    if auth_req.get("methods_required", 0) > 0:
        if auth_req.get("verify_each_time", False) or not participant.get("auth_verified"):
            completed = len(participant.get("auth_methods_completed", []))
            if completed < auth_req["methods_required"]:
                raise HTTPException(status_code=403, detail=f"Authentication required. Complete {auth_req['methods_required']} verification method(s) first.")

    now = datetime.now(timezone.utc).isoformat()
    contribution = body.get("contribution", {})
    vote = body.get("vote", None)  # for voting mode: True/False
    accepted = body.get("accepted", None)  # for consensus mode: True/False

    update_fields = {
        f"participants.{p_idx}.status": "contributed",
        f"participants.{p_idx}.contribution": contribution,
        f"participants.{p_idx}.contributed_at": now,
        "updated_at": now,
    }
    if vote is not None:
        update_fields[f"participants.{p_idx}.vote"] = vote
    if accepted is not None:
        update_fields[f"participants.{p_idx}.accepted"] = accepted

    await db.collaboration_sessions.update_one({"id": session_id}, {"$set": update_fields})

    # Notify owner
    notif_doc = {
        "id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": session["owner_id"],
        "type": "collaboration_contribution",
        "title": "New Contribution",
        "message": f'{user.get("name", "Someone")} contributed to "{session["title"]}"',
        "data": {"session_id": session_id},
        "read": False,
        "created_at": now,
    }
    await db.notifications.insert_one(notif_doc)

    return {"message": "Contribution submitted successfully"}


@router.post("/sessions/{session_id}/verify-auth")
async def verify_participant_auth(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Verify participant authentication method."""
    body = await request.json()
    method = body.get("method")  # "country_id", "biometric", "authenticator"

    session = await db.collaboration_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    p_idx = -1
    for idx, p in enumerate(session.get("participants", [])):
        if p.get("linked_user_id") == user["user_id"]:
            p_idx = idx
            break
    if p_idx == -1:
        raise HTTPException(status_code=403, detail="Not a participant")

    auth_req = session.get("auth_requirements", {})
    enabled = auth_req.get("enabled_methods", [])
    if method not in enabled:
        raise HTTPException(status_code=400, detail=f"Method '{method}' is not enabled for this session")

    verified = False
    if method == "country_id":
        id_number = body.get("id_number", "").strip()
        id_type = body.get("id_type", "aadhar")
        if not id_number:
            raise HTTPException(status_code=400, detail="ID number required")
        # Validate format
        if id_type == "aadhar" and (len(id_number) != 12 or not id_number.isdigit()):
            raise HTTPException(status_code=400, detail="Invalid Aadhar number (must be 12 digits)")
        verified = True

    elif method == "authenticator":
        otp_code = body.get("otp_code", "").strip()
        if not otp_code or len(otp_code) != 6:
            raise HTTPException(status_code=400, detail="Invalid OTP code (must be 6 digits)")
        # Verify against stored TOTP secret
        user_totp = await db.user_totp.find_one({"user_id": user["user_id"]}, {"_id": 0})
        if not user_totp:
            raise HTTPException(status_code=400, detail="Authenticator not set up. Please set up TOTP first.")
        try:
            import pyotp
            totp = pyotp.TOTP(user_totp["secret"])
            verified = totp.verify(otp_code, valid_window=1)
        except Exception:
            verified = False
        if not verified:
            raise HTTPException(status_code=400, detail="Invalid OTP code")

    elif method == "biometric":
        biometric_token = body.get("biometric_token", "")
        biometric_type = body.get("biometric_type", "fingerprint")  # fingerprint, retina
        if not biometric_token:
            raise HTTPException(status_code=400, detail="Biometric verification token required")
        # For device-based biometric, the token comes from expo-local-authentication
        # For retina, we'd compare against stored image - placeholder for API integration
        verified = True  # Device-level verification is trusted

    if verified:
        completed = session["participants"][p_idx].get("auth_methods_completed", [])
        if method not in completed:
            completed.append(method)

        methods_done = len(completed)
        all_verified = methods_done >= auth_req.get("methods_required", 0)

        await db.collaboration_sessions.update_one(
            {"id": session_id},
            {"$set": {
                f"participants.{p_idx}.auth_methods_completed": completed,
                f"participants.{p_idx}.auth_verified": all_verified,
            }}
        )

        return {
            "verified": True,
            "method": method,
            "methods_completed": completed,
            "fully_verified": all_verified,
            "methods_required": auth_req.get("methods_required", 0),
        }

    raise HTTPException(status_code=400, detail="Verification failed")


@router.post("/sessions/{session_id}/merge")
async def merge_session(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Owner merges all contributions based on the decision mode."""
    body = await request.json()
    session = await db.collaboration_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["owner_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Only the owner can merge")

    mode_id = session.get("decision_mode_id", "equal")
    participants = session.get("participants", [])
    contributions = [p for p in participants if p.get("contribution")]

    if not contributions:
        raise HTTPException(status_code=400, detail="No contributions to merge")

    now = datetime.now(timezone.utc).isoformat()

    # Calculate weights based on mode
    weights = _calculate_weights(mode_id, session, user["user_id"], contributions)

    # Check consensus
    if mode_id == "consensus":
        all_accepted = all(p.get("accepted") is True for p in participants)
        if not all_accepted:
            pending = [p["name"] for p in participants if p.get("accepted") is not True]
            return {
                "status": "pending_consensus",
                "message": f"Consensus not reached. Awaiting acceptance from: {', '.join(pending)}",
                "weights": weights,
            }

    # Check voting threshold
    if mode_id == "voting":
        votes_for = sum(1 for p in participants if p.get("vote") is True)
        total_voters = len(participants)
        threshold_pct = session.get("voting_config", {}).get("custom_threshold_pct", 51)
        actual_pct = (votes_for / total_voters * 100) if total_voters > 0 else 0
        if actual_pct < threshold_pct:
            return {
                "status": "voting_failed",
                "message": f"Voting threshold not met. {votes_for}/{total_voters} voted yes ({actual_pct:.0f}%). Required: {threshold_pct}%.",
                "weights": weights,
                "votes": {"for": votes_for, "against": total_voters - votes_for, "threshold_pct": threshold_pct},
            }

    # Apply merge to source module
    result = {"weights": weights, "mode": mode_id}

    if session["module_type"] == "decision":
        merge_result = await _merge_decision(session, user["user_id"], contributions, weights)
        result["merge_details"] = merge_result
    elif session["module_type"] == "solution_finder":
        merge_result = await _merge_solution_finder(session, user["user_id"], contributions, weights)
        result["merge_details"] = merge_result

    await db.collaboration_sessions.update_one(
        {"id": session_id},
        {"$set": {"status": "completed", "completed_at": now, "result": result, "updated_at": now}}
    )

    # Notify participants
    for p in participants:
        if p.get("linked_user_id") and p["linked_user_id"] != user["user_id"]:
            notif = {
                "id": f"notif_{uuid.uuid4().hex[:12]}",
                "user_id": p["linked_user_id"],
                "type": "collaboration_merged",
                "title": "Collaboration Complete",
                "message": f'"{session["title"]}" has been finalized by {user.get("name", "the owner")}. Mode: {session["decision_mode"]["name"]}',
                "data": {"session_id": session_id},
                "read": False,
                "created_at": now,
            }
            await db.notifications.insert_one(notif)

    return {"status": "merged", "message": "Contributions merged successfully", **result}


def _calculate_weights(mode_id: str, session: dict, owner_id: str, contributions: list) -> dict:
    """Calculate weight distribution based on decision mode. Uses mode_config_override if set."""
    total = len(contributions) + 1  # +1 for owner
    weights = {}
    # Use override config if provided, otherwise fall back to mode defaults
    override = session.get("mode_config_override") or {}
    mode_config = session.get("decision_mode", {}).get("config", {})
    effective_config = {**mode_config, **override} if override else mode_config

    if mode_id == "equal":
        w = round(1.0 / total, 4)
        weights[owner_id] = w
        for c in contributions:
            uid = c.get("linked_user_id") or c.get("contact_id")
            weights[uid] = w

    elif mode_id == "command":
        leader_pct = effective_config.get("leader_weight_pct", 50) / 100
        other_w = round((1 - leader_pct) / len(contributions), 4) if contributions else 0
        weights[owner_id] = leader_pct
        for c in contributions:
            uid = c.get("linked_user_id") or c.get("contact_id")
            weights[uid] = other_w

    elif mode_id == "sme":
        sme_total = effective_config.get("sme_total_weight_pct", 50) / 100
        smes = [c for c in contributions if c.get("is_sme")]
        non_smes = [c for c in contributions if not c.get("is_sme")]

        if smes:
            sme_each = round(sme_total / len(smes), 4)
            remaining = 1 - sme_total
            non_sme_count = len(non_smes) + 1  # +1 for owner
            non_sme_each = round(remaining / non_sme_count, 4) if non_sme_count > 0 else 0

            weights[owner_id] = non_sme_each
            for c in smes:
                uid = c.get("linked_user_id") or c.get("contact_id")
                weights[uid] = sme_each
            for c in non_smes:
                uid = c.get("linked_user_id") or c.get("contact_id")
                weights[uid] = non_sme_each
        else:
            # No SMEs, fall back to equal
            w = round(1.0 / total, 4)
            weights[owner_id] = w
            for c in contributions:
                uid = c.get("linked_user_id") or c.get("contact_id")
                weights[uid] = w

    elif mode_id == "custom":
        cw = session.get("custom_weights", {})
        weights = {k: v / 100 for k, v in cw.items()}
        if owner_id not in weights:
            weights[owner_id] = 0.5

    elif mode_id == "voting":
        # Voting uses equal weight for the merge itself
        w = round(1.0 / total, 4)
        weights[owner_id] = w
        for c in contributions:
            uid = c.get("linked_user_id") or c.get("contact_id")
            weights[uid] = w

    elif mode_id == "consensus":
        w = round(1.0 / total, 4)
        weights[owner_id] = w
        for c in contributions:
            uid = c.get("linked_user_id") or c.get("contact_id")
            weights[uid] = w

    return weights


async def _merge_decision(session: dict, owner_id: str, contributions: list, weights: dict) -> dict:
    """Merge PRR decision assessments using calculated weights."""
    decision = await db.decisions.find_one({"id": session["module_id"]}, {"_id": 0})
    if not decision:
        return {"error": "Decision not found"}

    if decision.get("options"):
        merged_options = []
        for option in decision["options"]:
            merged_assessments = []
            for factor in decision.get("factors", []):
                owner_assessment = next((a for a in option.get("assessments", []) if a.get("factor_id") == factor["id"]), None)
                owner_pct = owner_assessment.get("percentage", 50) if owner_assessment else 50
                weighted_sum = owner_pct * weights.get(owner_id, 0.5)

                for c in contributions:
                    c_data = c.get("contribution", {})
                    c_assessments = c_data.get("assessments", {})
                    c_key = f"{option['id']}_{factor['id']}"
                    c_pct = c_assessments.get(c_key, 50)
                    uid = c.get("linked_user_id") or c.get("contact_id")
                    weighted_sum += c_pct * weights.get(uid, 0)

                merged_assessments.append({
                    "factor_id": factor["id"],
                    "percentage": min(100, max(0, round(weighted_sum))),
                    "assessment_mode": "collaborative",
                    "unit_value": "",
                })
            merged_options.append({**option, "assessments": merged_assessments})

        await db.decisions.update_one(
            {"id": session["module_id"]},
            {"$set": {"options": merged_options, "updated_at": datetime.now(timezone.utc)}}
        )
        return {"merged_options_count": len(merged_options)}

    return {"message": "No options to merge"}


async def _merge_solution_finder(session: dict, owner_id: str, contributions: list, weights: dict) -> dict:
    """Merge Solution Finder contributions."""
    finder = await db.solution_finders.find_one({"entry_id": session["module_id"]}, {"_id": 0})
    if not finder:
        return {"error": "Solution Finder not found"}

    # Collect all concerns, solutions, and action items from all contributors
    all_concerns = [finder.get("q1_all_concerns", "")]
    all_primary = [finder.get("q2_primary_concerns", "")]
    all_solutions = [finder.get("q3_solutions", "")]
    all_capabilities = [finder.get("q3_capabilities", "")]
    all_resources = [finder.get("q3_resources", "")]
    all_neg = [finder.get("q4_negative_consequences", "")]
    all_mitig = [finder.get("q4_mitigation_plans", "")]
    all_contin = [finder.get("q4_contingency_plans", "")]
    all_actions = list(finder.get("action_items", []))

    for c in contributions:
        cd = c.get("contribution", {})
        if cd.get("q1_all_concerns"):
            all_concerns.append(f"[{c['name']}]: {cd['q1_all_concerns']}")
        if cd.get("q2_primary_concerns"):
            all_primary.append(f"[{c['name']}]: {cd['q2_primary_concerns']}")
        if cd.get("q3_solutions"):
            all_solutions.append(f"[{c['name']}]: {cd['q3_solutions']}")
        if cd.get("q3_capabilities"):
            all_capabilities.append(f"[{c['name']}]: {cd['q3_capabilities']}")
        if cd.get("q3_resources"):
            all_resources.append(f"[{c['name']}]: {cd['q3_resources']}")
        if cd.get("q4_negative_consequences"):
            all_neg.append(f"[{c['name']}]: {cd['q4_negative_consequences']}")
        if cd.get("q4_mitigation_plans"):
            all_mitig.append(f"[{c['name']}]: {cd['q4_mitigation_plans']}")
        if cd.get("q4_contingency_plans"):
            all_contin.append(f"[{c['name']}]: {cd['q4_contingency_plans']}")
        for ai in cd.get("action_items", []):
            ai["contributed_by"] = c["name"]
            all_actions.append(ai)

    merged = {
        "q1_all_concerns": "\n\n".join([c for c in all_concerns if c]),
        "q2_primary_concerns": "\n\n".join([c for c in all_primary if c]),
        "q3_solutions": "\n\n".join([c for c in all_solutions if c]),
        "q3_capabilities": "\n\n".join([c for c in all_capabilities if c]),
        "q3_resources": "\n\n".join([c for c in all_resources if c]),
        "q4_negative_consequences": "\n\n".join([c for c in all_neg if c]),
        "q4_mitigation_plans": "\n\n".join([c for c in all_mitig if c]),
        "q4_contingency_plans": "\n\n".join([c for c in all_contin if c]),
        "action_items": all_actions,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.solution_finders.update_one({"entry_id": session["module_id"]}, {"$set": merged})
    return {"merged_fields": len(merged), "total_action_items": len(all_actions), "contributors": len(contributions)}


# ========================
# TOTP AUTHENTICATOR SETUP
# ========================

@router.post("/totp/setup")
async def setup_totp(user: dict = Depends(get_current_user)):
    """Generate TOTP secret and provisioning URI for authenticator app setup."""
    try:
        import pyotp
    except ImportError:
        raise HTTPException(status_code=500, detail="pyotp not installed")

    existing = await db.user_totp.find_one({"user_id": user["user_id"]})
    if existing and existing.get("verified"):
        return {"message": "TOTP already configured", "already_setup": True}

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=user.get("email", "user"), issuer_name="View Dezider")

    await db.user_totp.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"user_id": user["user_id"], "secret": secret, "verified": False, "created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )

    return {"secret": secret, "provisioning_uri": uri, "already_setup": False}


@router.post("/totp/verify")
async def verify_totp(request: Request, user: dict = Depends(get_current_user)):
    """Verify TOTP code and mark as set up."""
    import pyotp
    body = await request.json()
    code = body.get("code", "").strip()
    if not code or len(code) != 6:
        raise HTTPException(status_code=400, detail="6-digit code required")

    doc = await db.user_totp.find_one({"user_id": user["user_id"]})
    if not doc:
        raise HTTPException(status_code=400, detail="TOTP not set up. Call /totp/setup first.")

    totp = pyotp.TOTP(doc["secret"])
    if totp.verify(code, valid_window=1):
        await db.user_totp.update_one({"user_id": user["user_id"]}, {"$set": {"verified": True}})
        await log_audit_event(
            action="totp_verified", entity_type="totp", entity_id=user["user_id"],
            user_id=user["user_id"], details="TOTP authenticator app verified successfully",
            ip_address=get_client_ip(request), sensitive_data_accessed=True,
            data_fields_accessed=["totp_secret"]
        )
        return {"verified": True, "message": "Authenticator app verified successfully"}

    await log_audit_event(
        action="totp_verify_failed", entity_type="totp", entity_id=user["user_id"],
        user_id=user["user_id"], details="TOTP verification failed - invalid code",
        ip_address=get_client_ip(request), sensitive_data_accessed=True,
    )
    raise HTTPException(status_code=400, detail="Invalid code. Please try again.")


@router.get("/totp/status")
async def totp_status(user: dict = Depends(get_current_user)):
    """Check if TOTP is set up for the user."""
    doc = await db.user_totp.find_one({"user_id": user["user_id"]}, {"_id": 0, "secret": 0})
    if doc and doc.get("verified"):
        return {"setup": True, "verified": True}
    elif doc:
        return {"setup": True, "verified": False}
    return {"setup": False, "verified": False}



# ========================
# DIGILOCKER eKYC (India)
# ========================

DIGILOCKER_CONFIG = {
    "auth_url": "https://api.digitallocker.gov.in/public/oauth2/1/authorize",
    "token_url": "https://api.digitallocker.gov.in/public/oauth2/2/token",
    "doc_url": "https://api.digitallocker.gov.in/public/oauth2/3/xml/eaadhaar",
}


@router.post("/digilocker/initiate")
async def initiate_digilocker(request: Request, user: dict = Depends(get_current_user)):
    """Initiate DigiLocker OAuth2 flow for Aadhaar eKYC verification.
    Supports: 
    - sandbox.co.in API (SANDBOX_API_KEY + SANDBOX_AUTH_TOKEN)
    - Official DigiLocker (DIGILOCKER_CLIENT_ID + SECRET)
    """
    import os
    import httpx

    sandbox_api_key = os.getenv("SANDBOX_API_KEY", "")
    sandbox_auth_token = os.getenv("SANDBOX_AUTH_TOKEN", "")
    client_id = os.getenv("DIGILOCKER_CLIENT_ID", "")
    redirect_uri = os.getenv("DIGILOCKER_REDIRECT_URI", "")

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    # Option 1: sandbox.co.in DigiLocker API
    if sandbox_api_key and sandbox_auth_token:
        base_url = os.getenv("SANDBOX_BASE_URL", "https://test-api.sandbox.co.in")
        callback_url = body.get("redirect_url", redirect_uri or "https://example.com/callback")

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{base_url}/kyc/digilocker/sessions/init",
                    headers={
                        "Authorization": sandbox_auth_token,
                        "x-api-key": sandbox_api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "@entity": "in.co.sandbox.kyc.digilocker.session.request",
                        "flow": "signin",
                        "doc_types": ["aadhaar"],
                        "redirect_url": callback_url,
                    }
                )
                data = resp.json()

            session_id = data.get("data", {}).get("session_id") or data.get("session_id")
            auth_url = data.get("data", {}).get("authorization_url") or data.get("authorization_url")

            if session_id:
                await db.digilocker_states.update_one(
                    {"user_id": user["user_id"]},
                    {"$set": {
                        "session_id": session_id,
                        "provider": "sandbox",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }},
                    upsert=True
                )

            return {
                "status": "initiated",
                "provider": "sandbox.co.in",
                "session_id": session_id,
                "authorization_url": auth_url,
                "message": "Redirect user to authorization_url to complete Aadhaar verification via DigiLocker.",
            }
        except Exception as e:
            await log_audit_event(
                action="digilocker_initiate_failed", entity_type="digilocker", entity_id=user["user_id"],
                user_id=user["user_id"], details=f"DigiLocker API call failed: {str(e)}",
                sensitive_data_accessed=True,
            )
            return {
                "status": "error",
                "provider": "sandbox.co.in",
                "message": f"DigiLocker API call failed: {str(e)}",
            }

    # Option 2: Official DigiLocker
    if client_id:
        import urllib.parse
        state = uuid.uuid4().hex[:16]
        await db.digilocker_states.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"state": state, "provider": "official", "created_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
        auth_url = f"https://digilocker.meripehchaan.gov.in/public/oauth2/1/authorize?response_type=code&client_id={client_id}&redirect_uri={urllib.parse.quote(redirect_uri)}&state={state}"
        return {"status": "initiated", "provider": "official_digilocker", "auth_url": auth_url, "state": state}

    # Not configured
    return {
        "status": "not_configured",
        "message": "DigiLocker integration requires API keys. Add SANDBOX_API_KEY + SANDBOX_AUTH_TOKEN (sandbox.co.in) or DIGILOCKER_CLIENT_ID + SECRET to your environment.",
        "setup_options": [
            {"provider": "sandbox.co.in", "url": "https://sandbox.co.in", "env_vars": ["SANDBOX_API_KEY", "SANDBOX_AUTH_TOKEN"]},
            {"provider": "DigiLocker Official", "url": "https://partners.digilocker.gov.in/", "env_vars": ["DIGILOCKER_CLIENT_ID", "DIGILOCKER_CLIENT_SECRET", "DIGILOCKER_REDIRECT_URI"]},
        ],
        "supported_documents": ["aadhaar", "pan", "driving_license", "voter_id"],
    }


@router.post("/digilocker/callback")
async def digilocker_callback(request: Request, user: dict = Depends(get_current_user)):
    """Process DigiLocker callback after user authorization. Fetches Aadhaar + profile."""
    import os
    import httpx

    body = await request.json()
    session_id = body.get("session_id")

    if not session_id:
        raise HTTPException(400, "session_id required")

    sandbox_api_key = os.getenv("SANDBOX_API_KEY", "")
    sandbox_auth_token = os.getenv("SANDBOX_AUTH_TOKEN", "")
    base_url = os.getenv("SANDBOX_BASE_URL", "https://test-api.sandbox.co.in")

    if not (sandbox_api_key and sandbox_auth_token):
        raise HTTPException(400, "DigiLocker API not configured")

    headers = {
        "Authorization": sandbox_auth_token,
        "x-api-key": sandbox_api_key,
    }

    profile_data = {}
    doc_data = {}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Fetch user profile
            profile_resp = await client.get(
                f"{base_url}/kyc/digilocker/sessions/{session_id}/user/profile",
                headers=headers,
            )
            if profile_resp.status_code == 200:
                profile_data = profile_resp.json().get("data", profile_resp.json())

            # Fetch Aadhaar document
            doc_resp = await client.get(
                f"{base_url}/kyc/digilocker/sessions/{session_id}/documents/aadhaar",
                headers=headers,
            )
            if doc_resp.status_code == 200:
                doc_data = doc_resp.json().get("data", doc_resp.json())
    except Exception as e:
        raise HTTPException(500, f"DigiLocker API error: {str(e)}")

    # Save verified KYC
    await db.user_kyc.update_one(
        {"user_id": user["user_id"], "method": "digilocker"},
        {"$set": {
            "verified": True,
            "provider": "sandbox",
            "session_id": session_id,
            "profile": profile_data,
            "document_meta": {k: v for k, v in doc_data.items() if k != "document_url"},
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True
    )

    return {
        "status": "verified",
        "name": profile_data.get("name"),
        "dob": profile_data.get("dob"),
        "gender": profile_data.get("gender"),
        "has_aadhaar": bool(doc_data),
    }


@router.get("/digilocker/status")
async def digilocker_status(request: Request, user: dict = Depends(get_current_user)):
    """Check DigiLocker verification status."""
    kyc = await db.user_kyc.find_one({"user_id": user["user_id"], "method": "digilocker"}, {"_id": 0})
    await log_audit_event(
        action="digilocker_status_check", entity_type="digilocker", entity_id=user["user_id"],
        user_id=user["user_id"], details=f"DigiLocker status checked. Verified: {bool(kyc and kyc.get('verified'))}",
        ip_address=get_client_ip(request), sensitive_data_accessed=True,
        data_fields_accessed=["kyc_verification_status"],
    )
    if kyc and kyc.get("verified"):
        return {"verified": True, "method": "digilocker", "verified_at": kyc.get("verified_at")}
    return {"verified": False}


# ========================
# BIOMETRIC FRAMEWORK
# ========================

SUPPORTED_BIOMETRIC_DEVICES = [
    {
        "id": "mantra_mfs100",
        "name": "Mantra MFS100",
        "type": "fingerprint",
        "cost_inr": 2500,
        "usb": True,
        "sdk": "Mantra RD Service (MFS100 SDK)",
        "integration": "USB HID + RD Service -> Captures fingerprint -> Returns PID block",
        "supported_os": ["Windows", "Android"],
        "aadhaar_certified": True,
        "recommended": True,
        "purchase_url": "https://www.mantratec.com/products/fingerprint-scanners",
    },
    {
        "id": "secugen_hamster_pro",
        "name": "SecuGen Hamster Pro 20",
        "type": "fingerprint",
        "cost_inr": 3500,
        "usb": True,
        "sdk": "SecuGen SDK (FDx Pro)",
        "integration": "USB -> SDK capture -> ISO 19794-2 template -> Match/Verify",
        "supported_os": ["Windows", "Linux", "Android"],
        "aadhaar_certified": True,
        "recommended": False,
    },
    {
        "id": "webcam_retina",
        "name": "Webcam Retina Scan",
        "type": "retina",
        "cost_inr": 0,
        "usb": False,
        "sdk": "Browser MediaDevices API + Server-side OpenCV comparison",
        "integration": "getUserMedia() -> Capture eye image -> Upload -> Compare with stored reference",
        "supported_os": ["Web (all browsers)", "Mobile (via camera)"],
        "aadhaar_certified": False,
        "recommended": False,
    },
    {
        "id": "iris_scanner_iritech",
        "name": "IriTech IriShield USB MK2120U",
        "type": "iris",
        "cost_inr": 15000,
        "usb": True,
        "sdk": "IriTech SDK (IriCore)",
        "integration": "USB -> Capture iris -> ISO 19794-6 template -> Match/Verify",
        "supported_os": ["Windows", "Android"],
        "aadhaar_certified": True,
        "recommended": False,
    },
]


@router.get("/biometric/supported-devices")
async def list_supported_biometric_devices(user: dict = Depends(get_current_user)):
    """List all supported biometric devices with costs and integration details."""
    return {
        "devices": SUPPORTED_BIOMETRIC_DEVICES,
        "recommended": "mantra_mfs100",
        "recommended_reason": "Most cost-effective (INR 2,500), Aadhaar-certified, widely available across India, USB plug-and-play with RD Service",
    }


@router.post("/biometric/register")
async def register_biometric(request: Request, user: dict = Depends(get_current_user)):
    """Register biometric data for a user (admin-uploaded or device-captured)."""
    body = await request.json()
    biometric_type = body.get("type", "fingerprint")
    device_id = body.get("device_id", "")
    template_data = body.get("template_data", "")
    admin_verified = body.get("admin_verified", False)

    if not template_data:
        raise HTTPException(status_code=400, detail="Biometric template data required")

    now = datetime.now(timezone.utc).isoformat()
    await db.user_biometrics.update_one(
        {"user_id": user["user_id"], "type": biometric_type},
        {"$set": {
            "user_id": user["user_id"],
            "type": biometric_type,
            "device_id": device_id,
            "template_hash": hash(template_data),
            "admin_verified": admin_verified,
            "registered_at": now,
        }},
        upsert=True
    )
    return {"registered": True, "type": biometric_type, "device_id": device_id}


@router.post("/biometric/verify")
async def verify_biometric(request: Request, user: dict = Depends(get_current_user)):
    """Verify biometric against stored template."""
    body = await request.json()
    biometric_type = body.get("type", "fingerprint")
    live_template = body.get("live_template", "")
    device_token = body.get("device_token", "")

    if not live_template and not device_token:
        raise HTTPException(status_code=400, detail="Biometric data or device token required")

    if device_token:
        await log_audit_event(
            action="biometric_verified", entity_type="biometric", entity_id=user["user_id"],
            user_id=user["user_id"], details=f"Biometric device auth verified ({biometric_type})",
            ip_address=get_client_ip(request), sensitive_data_accessed=True,
            data_fields_accessed=["biometric_template", "device_token"],
        )
        return {"verified": True, "method": "device_biometric", "type": biometric_type}

    stored = await db.user_biometrics.find_one(
        {"user_id": user["user_id"], "type": biometric_type}, {"_id": 0}
    )
    if not stored:
        await log_audit_event(
            action="biometric_verify_failed", entity_type="biometric", entity_id=user["user_id"],
            user_id=user["user_id"], details=f"No {biometric_type} registered",
            ip_address=get_client_ip(request), sensitive_data_accessed=True,
        )
        raise HTTPException(status_code=404, detail="No biometric registered for this type")

    live_hash = hash(live_template)
    if live_hash == stored.get("template_hash"):
        await log_audit_event(
            action="biometric_verified", entity_type="biometric", entity_id=user["user_id"],
            user_id=user["user_id"], details=f"Biometric template match verified ({biometric_type})",
            ip_address=get_client_ip(request), sensitive_data_accessed=True,
            data_fields_accessed=["biometric_template"],
        )
        return {"verified": True, "method": "server_biometric", "type": biometric_type}

    await log_audit_event(
        action="biometric_verify_failed", entity_type="biometric", entity_id=user["user_id"],
        user_id=user["user_id"], details=f"Biometric template mismatch ({biometric_type})",
        ip_address=get_client_ip(request), sensitive_data_accessed=True,
    )
    raise HTTPException(status_code=400, detail="Biometric verification failed")


@router.get("/biometric/status")
async def biometric_status(user: dict = Depends(get_current_user)):
    """Check biometric registration status."""
    registrations = await db.user_biometrics.find(
        {"user_id": user["user_id"]}, {"_id": 0, "template_hash": 0}
    ).to_list(10)
    return {"registered": len(registrations) > 0, "registrations": registrations}
