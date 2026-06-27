"""Step-sharing / collaboration routes — share a decision step, contribute, merge."""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Body
from core.database import db
from core.auth import get_current_user
from core.helpers import create_notification
from core.email import send_email, PUBLIC_APP_URL
from models.decisions_models import ShareStepRequest, ContributeStepRequest, MergeStepRequest, ReshareStepRequest

router = APIRouter(tags=["Decisions"])

STEP_NAMES = {1: 'Context & Options', 2: 'List Factors', 3: 'Classify Factors', 4: 'Prioritize Factors',
              5: 'Calculate Ratings', 6: 'Define Options', 7: 'Assess & Calculate', 8: 'Case-1 Results',
              9: 'MPPS Analysis', 10: 'Final Decision'}


def _share_email_html(sender: str, step_number: int, step_name: str, title: str, message: str, link: str) -> str:
    note = (f'<p style="background:#F5F3FF;border-radius:8px;padding:12px 14px;color:#4338CA;'
            f'margin:14px 0">“{message}”</p>') if message else ""
    return f"""
<div style="font-family:Helvetica,Arial,sans-serif;max-width:560px;margin:0 auto;color:#1f2937">
  <h2 style="color:#1E40AF;margin-bottom:4px">JELCOS AI</h2>
  <p style="color:#64748b;margin-top:0;font-style:italic">Joyful Executive's Life Choices Operating System — Powered by AI</p>
  <p><b>{sender}</b> has shared a decision step with you to collaborate on:</p>
  <p style="font-size:17px;font-weight:700;margin:8px 0">Step {step_number}: {step_name}</p>
  <p style="color:#475569;margin-top:0">from “{title}”</p>
  {note}
  <p>Open it in your JELCOS AI account — it's waiting in your <b>“Shared with me”</b> tab where you can review and add your input.</p>
  <p style="margin:24px 0">
    <a href="{link}" style="background:#1E40AF;color:#fff;text-decoration:none;
       padding:12px 22px;border-radius:8px;font-weight:700">Open Shared Step</a>
  </p>
  <p style="color:#94a3b8;font-size:12px">If the button doesn't work, paste this link: {link}</p>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0"/>
  <p style="color:#475569;font-size:13px">Best Wishes from
     <a href="https://jelcos.ai" style="color:#1E40AF">JELCOS AI</a></p>
</div>""".strip()


def _invite_email_html(sender: str, step_number: int, step_name: str, title: str, message: str, link: str) -> str:
    note = (f'<p style="background:#F5F3FF;border-radius:8px;padding:12px 14px;color:#4338CA;'
            f'margin:14px 0">“{message}”</p>') if message else ""
    return f"""
<div style="font-family:Helvetica,Arial,sans-serif;max-width:560px;margin:0 auto;color:#1f2937">
  <h2 style="color:#1E40AF;margin-bottom:4px">JELCOS AI</h2>
  <p style="color:#64748b;margin-top:0;font-style:italic">Joyful Executive's Life Choices Operating System — Powered by AI</p>
  <p><b>{sender}</b> wants to collaborate with you on a decision step:</p>
  <p style="font-size:17px;font-weight:700;margin:8px 0">Step {step_number}: {step_name}</p>
  <p style="color:#475569;margin-top:0">from “{title}”</p>
  {note}
  <p><b>Create a free account to view &amp; contribute.</b> Sign up with this email address and the
     shared step will appear automatically in your <b>“Shared with me”</b> tab.</p>
  <p style="margin:24px 0">
    <a href="{link}" style="background:#1E40AF;color:#fff;text-decoration:none;
       padding:12px 22px;border-radius:8px;font-weight:700">Create free account</a>
  </p>
  <p style="color:#94a3b8;font-size:12px">If the button doesn't work, paste this link: {link}</p>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0"/>
  <p style="color:#475569;font-size:13px">Best Wishes from
     <a href="https://jelcos.ai" style="color:#1E40AF">JELCOS AI</a></p>
</div>""".strip()


async def _claim_pending_for_user(user: dict) -> None:
    """Move any pending email-invites matching this user's email into the
    share's recipients[] (so an invited user who just signed up can see &
    contribute). Best-effort; idempotent."""
    email = (user.get("email") or "").strip().lower()
    if not email:
        return
    cursor = db.shared_steps.find(
        {"pending_invites.email": email, "status": "active"},
        {"_id": 0, "id": 1, "recipients": 1})
    async for s in cursor:
        already = any(r.get("user_id") == user["user_id"] for r in s.get("recipients", []))
        update: dict = {"$pull": {"pending_invites": {"email": email}}}
        if not already:
            update["$push"] = {"recipients": {
                "user_id": user["user_id"], "email": email,
                "name": user.get("name", email), "status": "pending", "contribution": None}}
        await db.shared_steps.update_one({"id": s["id"]}, update)


_MODULE_META = {
    "decision": {"coll": "decisions", "key": "id", "title": "title"},
    "pros_cons": {"coll": "pros_cons", "key": "id", "title": "title"},
    "swot": {"coll": "swot", "key": "id", "title": "title"},
    "solution_finder": {"coll": "solution_finders", "key": "entry_id", "title": "smart_goal"},
}


async def _resolve_recipients(emails):
    """Split emails into registered recipients and pending invites (deduped)."""
    recipients, pending, seen = [], [], set()
    for raw in emails or []:
        email = (raw or "").strip().lower()
        if not email or email in seen:
            continue
        seen.add(email)
        ru = await db.users.find_one({"email": email}, {"_id": 0})
        if ru:
            recipients.append({"user_id": ru["user_id"], "email": email, "name": ru.get("name", email),
                               "status": "pending", "contribution": None, "invited_by": None, "invited_by_name": None})
        else:
            pending.append({"email": email, "invited_by": None, "invited_by_name": None})
    return recipients, pending


async def _load_owner_doc(module: str, module_id: str, owner_id: str):
    meta = _MODULE_META.get(module)
    if not meta:
        return None, "", meta
    coll = getattr(db, meta["coll"])
    doc = await coll.find_one({meta["key"]: module_id, "user_id": owner_id}, {"_id": 0})
    title = (doc or {}).get(meta["title"]) or (doc or {}).get("title") or "Shared item"
    return doc, title, meta


@router.post("/shared-steps/create")
async def create_shared_step(data: dict = Body(...), user: dict = Depends(get_current_user)):
    """Module-aware step share (decision | pros_cons | solution_finder). Used by
    Pros&Cons / SolutionFinder flows and the Collab Hub."""
    module = data.get("module", "decision")
    module_id = data.get("module_id") or data.get("decision_id")
    if not module_id:
        raise HTTPException(status_code=400, detail="module_id is required")
    doc, title, meta = await _load_owner_doc(module, module_id, user["user_id"])
    if not meta:
        raise HTTPException(status_code=400, detail=f"Unsupported module: {module}")
    if not doc:
        raise HTTPException(status_code=404, detail="Item not found")
    recipients, pending = await _resolve_recipients(data.get("recipient_emails", []))
    if not recipients and not pending:
        raise HTTPException(status_code=400, detail="No valid recipient emails provided")
    share_id = str(uuid.uuid4())
    share_doc = {
        "id": share_id, "decision_id": module_id, "module": module, "module_id": module_id,
        "owner_id": user["user_id"], "owner_name": user.get("name", user["email"]),
        "step_number": int(data.get("step_number") or 0),
        "merge_mode": data.get("merge_mode", "equal"), "custom_weights": data.get("custom_weights") or {},
        "message": data.get("message", ""), "allow_reshare": bool(data.get("allow_reshare")),
        "step_access": data.get("step_access", "hidden"),
        "decision_title": title, "decision_context": doc.get("context", ""),
        "step_data": {}, "status": "active",
        "recipients": recipients, "pending_invites": pending,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.shared_steps.insert_one(share_doc)
    for r in recipients:
        await create_notification(r["user_id"], "share_received", "Shared with you",
            f'{share_doc["owner_name"]} asked for your input on "{title}"',
            {"share_id": share_id, "module": module})
    return {"id": share_id, "shared_count": len(recipients), "invited_count": len(pending)}


@router.post("/shared-steps/{share_id}/open")
async def open_for_contribution(share_id: str, user: dict = Depends(get_current_user)):
    """Resolve where the contributor should edit. For decision → the owner's
    decision is loaded read-only via /decision (local-only edits). For pros_cons /
    solution_finder → create (or reuse) a per-recipient sandbox CLONE the
    contributor can edit natively via the normal flow."""
    await _claim_pending_for_user(user)
    share = await db.shared_steps.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Shared step not found")
    rec = next((r for r in share.get("recipients", []) if r["user_id"] == user["user_id"]), None)
    if not rec:
        raise HTTPException(status_code=403, detail="You are not a recipient of this share")
    module = share.get("module", "decision")
    if module == "decision":
        return {"module": "decision", "target_id": share.get("module_id") or share.get("decision_id"),
                "step_number": share.get("step_number"), "step_access": share.get("step_access", "hidden")}

    meta = _MODULE_META.get(module)
    if not meta:
        raise HTTPException(status_code=400, detail=f"Unsupported module: {module}")
    coll = getattr(db, meta["coll"])
    key = meta["key"]
    clone_id = rec.get("clone_id")
    if clone_id and await coll.find_one({key: clone_id}, {"_id": 0, key: 1}):
        return {"module": module, "target_id": clone_id, "step_number": share.get("step_number"),
                "step_access": share.get("step_access", "hidden")}
    owner_doc = await coll.find_one({meta["key"]: share.get("module_id"), "user_id": share["owner_id"]}, {"_id": 0})
    if not owner_doc:
        raise HTTPException(status_code=404, detail="Source item not found")
    import copy as _copy
    clone = _copy.deepcopy(owner_doc)
    new_id = str(uuid.uuid4())
    clone[key] = new_id
    clone["user_id"] = user["user_id"]
    clone["contribution_clone"] = {"share_id": share_id, "owner_id": share["owner_id"], "module": module}
    await coll.insert_one(clone)
    await db.shared_steps.update_one({"id": share_id, "recipients.user_id": user["user_id"]},
                                     {"$set": {"recipients.$.clone_id": new_id}})
    return {"module": module, "target_id": new_id, "step_number": share.get("step_number"),
            "step_access": share.get("step_access", "hidden")}


@router.post("/decisions/{decision_id}/share-step")
async def share_step(decision_id: str, data: ShareStepRequest, user: dict = Depends(get_current_user)):
    decision = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    # Split requested emails into registered users (get in-app + email alert)
    # and unknown emails (get an invite email + a pending claim record).
    recipients = []
    pending_invites = []
    seen = set()
    for raw in data.recipient_emails:
        email = (raw or "").strip().lower()
        if not email or email in seen:
            continue
        seen.add(email)
        recipient_user = await db.users.find_one({"email": email}, {"_id": 0})
        if recipient_user:
            recipients.append({"user_id": recipient_user["user_id"], "email": email,
                               "name": recipient_user.get("name", email), "status": "pending",
                               "contribution": None, "invited_by": None, "invited_by_name": None})
        else:
            pending_invites.append({"email": email, "invited_by": None, "invited_by_name": None})
    if not recipients and not pending_invites:
        raise HTTPException(status_code=400, detail="No valid recipient emails provided")

    share_doc = {
        "id": str(uuid.uuid4()), "decision_id": decision_id, "owner_id": user["user_id"],
        "owner_name": user.get("name", user["email"]), "step_number": data.step_number,
        "merge_mode": data.merge_mode, "custom_weights": data.custom_weights or {},
        "message": data.message, "recipients": recipients, "pending_invites": pending_invites,
        "allow_reshare": bool(data.allow_reshare),
        "module": getattr(data, "module", "decision") or "decision",
        "step_access": getattr(data, "step_access", "hidden") or "hidden",
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
    msg = (data.message or "").strip()

    # Registered recipients → in-app notification + email alert
    for r in recipients:
        await create_notification(r["user_id"], "share_invite", f"Step {data.step_number}: {step_name}",
            f'{sender_name} ({sender_email}) shared Step {data.step_number} "{step_name}" of "{decision_title}" with you',
            {"share_id": share_doc["id"], "decision_id": decision_id, "step_number": data.step_number,
             "step_name": step_name, "sender_name": sender_name, "sender_email": sender_email, "decision_title": decision_title})
        await send_email(
            r["email"],
            f'{sender_name} shared a decision step with you — {step_name}',
            _share_email_html(sender_name, data.step_number, step_name, decision_title, msg, PUBLIC_APP_URL))

    # Unknown emails → invite email (account auto-claims the share on signup)
    for inv in pending_invites:
        await send_email(
            inv["email"],
            f'{sender_name} invited you to collaborate on a decision — {step_name}',
            _invite_email_html(sender_name, data.step_number, step_name, decision_title, msg, f"{PUBLIC_APP_URL}/register"))

    return {
        "id": share_doc["id"],
        "shared_count": len(recipients),
        "invited_count": len(pending_invites),
        "invited_emails": [i["email"] for i in pending_invites],
        "message": (
            f'Step {data.step_number} shared with {len(recipients)} user'
            f'{"" if len(recipients) == 1 else "s"}'
            + (f', and invited {len(pending_invites)} new email'
               f'{"" if len(pending_invites) == 1 else "s"} to join' if pending_invites else '')
        ),
    }


@router.get("/shared-steps/received")
async def get_received_shared_steps(user: dict = Depends(get_current_user)):
    await _claim_pending_for_user(user)
    shares = await db.shared_steps.find({"recipients.user_id": user["user_id"], "status": "active"}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return shares


@router.get("/shared-steps/sent")
async def get_sent_shared_steps(user: dict = Depends(get_current_user)):
    shares = await db.shared_steps.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return shares


@router.get("/shared-steps/{share_id}")
async def get_shared_step(share_id: str, user: dict = Depends(get_current_user)):
    await _claim_pending_for_user(user)
    share = await db.shared_steps.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Shared step not found")
    is_owner = share["owner_id"] == user["user_id"]
    is_recipient = any(r["user_id"] == user["user_id"] for r in share.get("recipients", []))
    if not is_owner and not is_recipient:
        raise HTTPException(status_code=403, detail="Access denied")
    return share


@router.get("/shared-steps/{share_id}/decision")
async def get_shared_step_decision(share_id: str, user: dict = Depends(get_current_user)):
    """Recipient-accessible read of the owner's decision so the contributor can
    open the REAL flow (Contribution Mode) scoped to the requested step."""
    await _claim_pending_for_user(user)
    share = await db.shared_steps.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Shared step not found")
    is_owner = share["owner_id"] == user["user_id"]
    is_recipient = any(r["user_id"] == user["user_id"] for r in share.get("recipients", []))
    if not is_owner and not is_recipient:
        raise HTTPException(status_code=403, detail="Access denied")
    decision = await db.decisions.find_one({"id": share["decision_id"]}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    me = next((r for r in share.get("recipients", []) if r.get("user_id") == user["user_id"]), None)
    return {
        "decision": decision,
        "share": {
            "id": share["id"], "step_number": share.get("step_number"),
            "step_access": share.get("step_access", "hidden"),
            "module": share.get("module", "decision"),
            "merge_mode": share.get("merge_mode", "equal"),
            "owner_name": share.get("owner_name"), "decision_title": share.get("decision_title"),
            "message": share.get("message", ""), "allow_reshare": share.get("allow_reshare", False),
            "status": share.get("status", "active"),
        },
        "my_contribution": (me or {}).get("contribution"),
        "is_owner": is_owner,
    }


@router.delete("/shared-steps/{share_id}/contribution")
async def delete_my_contribution(share_id: str, user: dict = Depends(get_current_user)):
    """A contributor withdraws/deletes their own contribution (back to pending)."""
    share = await db.shared_steps.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Shared step not found")
    is_recipient = any(r["user_id"] == user["user_id"] for r in share.get("recipients", []))
    if not is_recipient:
        raise HTTPException(status_code=403, detail="You are not a recipient of this share")
    res = await db.shared_steps.update_one(
        {"id": share_id, "recipients.user_id": user["user_id"]},
        {"$set": {"recipients.$.status": "pending", "recipients.$.contribution": None}})
    return {"ok": True, "modified": res.modified_count}


@router.post("/shared-steps/{share_id}/contribute")
async def contribute_to_shared_step(share_id: str, data: ContributeStepRequest, user: dict = Depends(get_current_user)):
    await _claim_pending_for_user(user)
    share = await db.shared_steps.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Shared step not found")
    is_recipient = any(r["user_id"] == user["user_id"] for r in share.get("recipients", []))
    if not is_recipient:
        raise HTTPException(status_code=403, detail="You are not a recipient of this share")
    module = share.get("module", "decision")
    if module != "decision":
        # Clone-based modules (pros_cons / solution_finder): snapshot the
        # contributor's edited clone as their contribution.
        rec = next((r for r in share.get("recipients", []) if r["user_id"] == user["user_id"]), None)
        clone_id = (rec or {}).get("clone_id")
        meta = _MODULE_META.get(module)
        snapshot = None
        if clone_id and meta:
            snapshot = await getattr(db, meta["coll"]).find_one({meta["key"]: clone_id}, {"_id": 0})
        contribution = {"snapshot": snapshot, "note": data.note,
                        "submitted_at": datetime.now(timezone.utc).isoformat()}
    else:
        contribution = {"factors": data.factors, "options": data.options, "assessments": data.assessments,
                        "note": data.note, "consolidated": data.consolidated,
                        "submitted_at": datetime.now(timezone.utc).isoformat()}
    await db.shared_steps.update_one({"id": share_id, "recipients.user_id": user["user_id"]},
        {"$set": {"recipients.$.status": "contributed", "recipients.$.contribution": contribution}})
    contributor_name = user.get("name", user.get("email", "Someone"))
    await create_notification(share["owner_id"], "share_contributed", "New Contribution",
        f'{contributor_name} contributed to Step {share.get("step_number", "?")} of "{share.get("decision_title", "your decision")}"',
        {"share_id": share_id, "decision_id": share.get("decision_id")})
    return {"message": "Contribution submitted successfully"}


@router.post("/shared-steps/{share_id}/reshare")
async def reshare_step(share_id: str, data: ReshareStepRequest, user: dict = Depends(get_current_user)):
    """A recipient seeks further help from their OWN contacts/experts — allowed
    only if the owner enabled it. New recipients are added to the SAME share
    with `invited_by` attribution, so the owner sees a transparent tree."""
    await _claim_pending_for_user(user)
    share = await db.shared_steps.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Shared step not found")
    me = next((r for r in share.get("recipients", []) if r.get("user_id") == user["user_id"]), None)
    if not me and share.get("owner_id") != user["user_id"]:
        raise HTTPException(status_code=403, detail="You are not a recipient of this share")
    if not share.get("allow_reshare"):
        raise HTTPException(status_code=403, detail="The decision owner hasn't allowed seeking further help on this share.")

    existing = {r.get("email", "").lower() for r in share.get("recipients", [])} | \
               {p.get("email", "").lower() for p in share.get("pending_invites", [])}
    existing.add((user.get("email") or "").lower())
    by_name = user.get("name", user.get("email", "Someone"))
    added, invited = 0, 0
    for raw in data.recipient_emails:
        email = (raw or "").strip().lower()
        if not email or email in existing or email == share.get("owner_id"):
            continue
        existing.add(email)
        ru = await db.users.find_one({"email": email}, {"_id": 0})
        if ru:
            await db.shared_steps.update_one({"id": share_id}, {"$push": {"recipients": {
                "user_id": ru["user_id"], "email": email, "name": ru.get("name", email),
                "status": "pending", "contribution": None,
                "invited_by": user["user_id"], "invited_by_name": by_name}}})
            await create_notification(ru["user_id"], "share_invite",
                f'Step {share.get("step_number")}: help requested',
                f'{by_name} asked for your input on "{share.get("decision_title", "a decision")}"',
                {"share_id": share_id, "decision_id": share.get("decision_id"), "via": by_name})
            await send_email(email, f'{by_name} asked for your input on a decision step',
                _share_email_html(by_name, share.get("step_number", 0),
                    STEP_NAMES.get(share.get("step_number"), "a step"),
                    share.get("decision_title", "a decision"), data.message, PUBLIC_APP_URL))
            added += 1
        else:
            await db.shared_steps.update_one({"id": share_id}, {"$push": {"pending_invites": {
                "email": email, "invited_by": user["user_id"], "invited_by_name": by_name}}})
            await send_email(email, f'{by_name} invited you to help on a decision step',
                _invite_email_html(by_name, share.get("step_number", 0),
                    STEP_NAMES.get(share.get("step_number"), "a step"),
                    share.get("decision_title", "a decision"), data.message, f"{PUBLIC_APP_URL}/register"))
            invited += 1
    if added + invited == 0:
        raise HTTPException(status_code=400, detail="No new recipients to add.")
    return {"ok": True, "added": added, "invited": invited,
            "message": f'Forwarded for help to {added + invited} {"person" if added + invited == 1 else "people"}.'}


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
