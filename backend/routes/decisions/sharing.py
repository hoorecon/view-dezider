"""Step-sharing / collaboration routes — share a decision step, contribute, merge."""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from core.auth import get_current_user
from core.helpers import create_notification
from models.decisions_models import ShareStepRequest, ContributeStepRequest, MergeStepRequest

router = APIRouter(tags=["Decisions"])

STEP_NAMES = {1: 'Context & Options', 2: 'List Factors', 3: 'Classify Factors', 4: 'Prioritize Factors',
              5: 'Calculate Ratings', 6: 'Define Options', 7: 'Assess & Calculate', 8: 'Case-1 Results',
              9: 'MPPS Analysis', 10: 'Final Decision'}


@router.post("/decisions/{decision_id}/share-step")
async def share_step(decision_id: str, data: ShareStepRequest, user: dict = Depends(get_current_user)):
    decision = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    recipients = []
    for email in data.recipient_emails:
        recipient_user = await db.users.find_one({"email": email}, {"_id": 0})
        if recipient_user:
            recipients.append({"user_id": recipient_user["user_id"], "email": email,
                               "name": recipient_user.get("name", email), "status": "pending", "contribution": None})
    if not recipients:
        raise HTTPException(status_code=400, detail="No valid recipients found")
    share_doc = {
        "id": str(uuid.uuid4()), "decision_id": decision_id, "owner_id": user["user_id"],
        "owner_name": user.get("name", user["email"]), "step_number": data.step_number,
        "merge_mode": data.merge_mode, "custom_weights": data.custom_weights or {},
        "message": data.message, "recipients": recipients,
        "decision_title": decision.get("title", ""), "decision_context": decision.get("context", ""),
        "step_data": {"factors": decision.get("factors", []),
                      "options": [{"id": o["id"], "name": o["name"]} for o in decision.get("options", [])]},
        "status": "active", "created_at": datetime.now(timezone.utc), "merged_at": None,
    }
    await db.shared_steps.insert_one(share_doc)
    step_name = STEP_NAMES.get(data.step_number, f'Step {data.step_number}')
    sender_name = user.get("name", user["email"])
    sender_email = user.get("email", "")
    decision_title = decision.get("title", "a decision")
    for r in recipients:
        await create_notification(r["user_id"], "share_invite", f"Step {data.step_number}: {step_name}",
            f'{sender_name} ({sender_email}) shared Step {data.step_number} "{step_name}" of "{decision_title}" with you',
            {"share_id": share_doc["id"], "decision_id": decision_id, "step_number": data.step_number,
             "step_name": step_name, "sender_name": sender_name, "sender_email": sender_email, "decision_title": decision_title})
    return {"id": share_doc["id"], "message": f"Step {data.step_number} shared with {len(recipients)} users"}


@router.get("/shared-steps/received")
async def get_received_shared_steps(user: dict = Depends(get_current_user)):
    shares = await db.shared_steps.find({"recipients.user_id": user["user_id"], "status": "active"}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return shares


@router.get("/shared-steps/sent")
async def get_sent_shared_steps(user: dict = Depends(get_current_user)):
    shares = await db.shared_steps.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return shares


@router.get("/shared-steps/{share_id}")
async def get_shared_step(share_id: str, user: dict = Depends(get_current_user)):
    share = await db.shared_steps.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Shared step not found")
    is_owner = share["owner_id"] == user["user_id"]
    is_recipient = any(r["user_id"] == user["user_id"] for r in share.get("recipients", []))
    if not is_owner and not is_recipient:
        raise HTTPException(status_code=403, detail="Access denied")
    return share


@router.post("/shared-steps/{share_id}/contribute")
async def contribute_to_shared_step(share_id: str, data: ContributeStepRequest, user: dict = Depends(get_current_user)):
    share = await db.shared_steps.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Shared step not found")
    is_recipient = any(r["user_id"] == user["user_id"] for r in share.get("recipients", []))
    if not is_recipient:
        raise HTTPException(status_code=403, detail="You are not a recipient of this share")
    contribution = {"factors": data.factors, "options": data.options, "assessments": data.assessments,
                    "note": data.note, "submitted_at": datetime.now(timezone.utc).isoformat()}
    await db.shared_steps.update_one({"id": share_id, "recipients.user_id": user["user_id"]},
        {"$set": {"recipients.$.status": "contributed", "recipients.$.contribution": contribution}})
    contributor_name = user.get("name", user.get("email", "Someone"))
    await create_notification(share["owner_id"], "share_contributed", "New Contribution",
        f'{contributor_name} contributed to Step {share.get("step_number", "?")} of "{share.get("decision_title", "your decision")}"',
        {"share_id": share_id, "decision_id": share.get("decision_id")})
    return {"message": "Contribution submitted successfully"}


@router.post("/shared-steps/{share_id}/merge")
async def merge_shared_step(share_id: str, data: MergeStepRequest, user: dict = Depends(get_current_user)):
    share = await db.shared_steps.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Shared step not found")
    if share["owner_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Only the owner can merge contributions")
    decision = await db.decisions.find_one({"id": share["decision_id"], "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    contributions = []
    for r in share.get("recipients", []):
        if r.get("contribution"):
            contributions.append({"user_id": r["user_id"], "data": r["contribution"]})
    if not contributions:
        raise HTTPException(status_code=400, detail="No contributions to merge")
    merge_mode = data.merge_mode or share.get("merge_mode", "equal")
    total_participants = len(contributions) + 1
    weights = {}
    if merge_mode == "equal":
        w = 1.0 / total_participants
        weights[user["user_id"]] = w
        for c in contributions:
            weights[c["user_id"]] = w
    elif merge_mode == "self_weighted":
        weights[user["user_id"]] = 0.5
        other_weight = 0.5 / len(contributions) if contributions else 0
        for c in contributions:
            weights[c["user_id"]] = other_weight
    elif merge_mode == "custom" and data.custom_weights:
        weights = data.custom_weights
        if user["user_id"] not in weights:
            weights[user["user_id"]] = 0.5
    step_number = share.get("step_number", 7)
    if step_number == 7 and decision.get("options"):
        merged_options = []
        for option in decision["options"]:
            merged_assessments = []
            for factor in decision.get("factors", []):
                owner_assessment = next((a for a in option.get("assessments", []) if a.get("factor_id") == factor["id"]), None)
                owner_pct = owner_assessment.get("percentage", 50) if owner_assessment else 50
                weighted_sum = owner_pct * weights.get(user["user_id"], 0.5)
                for c in contributions:
                    c_assessments = c["data"].get("assessments", {})
                    c_key = f"{option['id']}_{factor['id']}"
                    c_pct = c_assessments.get(c_key, 50)
                    weighted_sum += c_pct * weights.get(c["user_id"], 0)
                merged_assessments.append({"factor_id": factor["id"], "percentage": min(100, max(0, round(weighted_sum))),
                                           "assessment_mode": "custom", "unit_value": ""})
            merged_options.append({**option, "assessments": merged_assessments})
        now = datetime.now(timezone.utc)
        await db.decisions.update_one({"id": share["decision_id"]}, {"$set": {"options": merged_options, "updated_at": now}})
    await db.shared_steps.update_one({"id": share_id}, {"$set": {"status": "merged", "merged_at": datetime.now(timezone.utc)}})
    for r in share.get("recipients", []):
        if r.get("contribution"):
            await create_notification(r["user_id"], "share_merged", "Contributions Merged",
                f'{user.get("name", "Someone")} merged your input for "{share.get("decision_title", "a decision")}"',
                {"share_id": share_id, "decision_id": share["decision_id"]})
    return {"message": "Contributions merged successfully", "weights": weights}
