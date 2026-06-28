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


async def _contact_meta(owner_id: str, email: str) -> dict:
    """Look up the OWNER's contact record for this recipient email so the AI
    merge can weight the contributor by SME status, declared resources and
    capability/bandwidth. Best-effort; returns empty dict when no contact."""
    if not owner_id or not email:
        return {}
    c = await db.contacts.find_one(
        {"user_id": owner_id, "email": email}, {"_id": 0}) or {}
    sme = bool(c.get("is_sme"))
    domains = c.get("sme_domains") or []
    cap = "SME · " + ", ".join(domains) if (sme and domains) else ("SME" if sme else "")
    bw = c.get("time_bandwidth_hours_per_month")
    if bw:
        cap = (cap + f" · ~{bw}h/mo").strip(" ·")
    return {
        "sme": sme,
        "sme_domains": domains,
        "capability": cap or None,
        "resources": c.get("resources") or None,
    }


async def _resolve_recipients(emails, owner_id: str = ""):
    """Split emails into registered recipients and pending invites (deduped).
    Registered recipients are enriched with the owner's contact metadata
    (SME / capability / resources) when available."""
    recipients, pending, seen = [], [], set()
    for raw in emails or []:
        email = (raw or "").strip().lower()
        if not email or email in seen:
            continue
        seen.add(email)
        ru = await db.users.find_one({"email": email}, {"_id": 0})
        if ru:
            recipients.append({"user_id": ru["user_id"], "email": email, "name": ru.get("name", email),
                               "status": "pending", "contribution": None, "invited_by": None, "invited_by_name": None,
                               **await _contact_meta(owner_id, email)})
        else:
            pending.append({"email": email, "invited_by": None, "invited_by_name": None})
    return recipients, pending


async def _load_owner_doc(module: str, module_id: str, owner_id: str):
    meta = _MODULE_META.get(module)
    if not meta:
        return None, "", meta
    coll = getattr(db, meta["coll"])
    doc = await coll.find_one({meta["key"]: module_id, "user_id": owner_id}, {"_id": 0})
    d = doc or {}
    title = (d.get(meta["title"]) or d.get("title") or d.get("name") or d.get("smart_goal")
             or d.get("problem_statement") or d.get("problem") or d.get("concern") or "Shared item")
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
    recipients, pending = await _resolve_recipients(data.get("recipient_emails", []), user["user_id"])
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
    share_doc["session_mode"] = data.get("session_mode", "async")
    share_doc["auth_config"] = data.get("auth_config") or {}
    share_doc["call_room_url"] = data.get("call_room_url")
    await db.shared_steps.insert_one(share_doc)

    # Dispatch invites: in-app notification + Email + WhatsApp, each carrying a
    # contribution link (and, for Live Sync, the meeting link). Best-effort — a
    # failed channel never blocks the share.
    import os as _os
    from core.notify import send_email as _send_email, send_whatsapp as _send_wa
    base = (_os.getenv("PUBLIC_APP_URL") or "").rstrip("/")
    link = f"{base}/?share={share_id}" if base else base
    notify = data.get("notify") or {}
    want_email = notify.get("participants", True)
    sender = share_doc["owner_name"]
    step_no = share_doc["step_number"]
    is_live = share_doc["session_mode"] == "live_sync"
    meeting = share_doc.get("call_room_url")

    async def _dispatch(email: str):
        contact = await db.contacts.find_one(
            {"user_id": user["user_id"], "email": email}, {"_id": 0}) or {}
        phone = contact.get("phone") or contact.get("mobile") or ""
        html = _invite_email_html(sender, step_no, f"Step {step_no}", title, data.get("message", ""), link)
        if is_live and meeting:
            html += f'<p style="margin-top:12px"><a href="{meeting}" style="background:#059669;color:#fff;padding:10px 16px;border-radius:8px;text-decoration:none">Join the live video session</a></p>'
        if want_email and email:
            try:
                await _send_email(email, f'{sender} wants your input — {title}', html)
            except Exception:
                pass
        if phone:
            wa = f'{sender} asked for your input on "{title}" (Step {step_no}). Open: {link}'
            if is_live and meeting:
                wa += f'\nJoin the live session: {meeting}'
            try:
                await _send_wa(phone, wa)
            except Exception:
                pass

    for r in recipients:
        await create_notification(r["user_id"], "share_received", "Shared with you",
            f'{sender} asked for your input on "{title}"',
            {"share_id": share_id, "module": module})
        await _dispatch(r["email"])
    for p in pending:
        await _dispatch(p["email"])
    return {"id": share_id, "shared_count": len(recipients), "invited_count": len(pending), "link": link}


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
                               "contribution": None, "invited_by": None, "invited_by_name": None,
                               **await _contact_meta(user["user_id"], email)})
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


@router.get("/shared-steps/{share_id}/review")
async def review_contributions(share_id: str, user: dict = Depends(get_current_user)):
    """Owner-only: own step data + every contributor's per-step input (preserved
    even after merge). Works for all modules / steps."""
    share = await db.shared_steps.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Shared step not found")
    if share["owner_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Only the owner can review contributions")
    module = share.get("module", "decision")
    meta = _MODULE_META.get(module, _MODULE_META["decision"])
    flow_id = share.get("module_id") or share.get("decision_id")
    owner_doc = await getattr(db, meta["coll"]).find_one(
        {meta["key"]: flow_id, "user_id": share["owner_id"]}, {"_id": 0})
    contributions = []
    for r in share.get("recipients", []):
        if r.get("status") == "contributed" and r.get("contribution"):
            c = r["contribution"]
            data = c.get("snapshot") if module != "decision" else c
            contributions.append({
                "user_id": r["user_id"], "name": r.get("name", r.get("email")),
                "email": r.get("email"),
                "sme": bool(r.get("sme")), "sme_domains": r.get("sme_domains") or [],
                "capability": r.get("capability"), "resources": r.get("resources"),
                "data": data, "note": c.get("note", ""), "submitted_at": c.get("submitted_at"),
            })
    return {
        "module": module, "step_number": share.get("step_number"),
        "merge_mode": share.get("merge_mode", "equal"), "status": share.get("status", "active"),
        "decision_title": share.get("decision_title"), "owner": owner_doc,
        "contributions": contributions,
        "merge_history": share.get("merge_history", []),
    }


@router.post("/shared-steps/{share_id}/ai-merge")
async def ai_merge_contributions(share_id: str, data: dict = Body(default={}), user: dict = Depends(get_current_user)):
    """Owner-only: AI proposes a consolidated step from all contributors' inputs,
    weighted by the owner's mode + each contributor's capability/SME/resources.
    Advisory — NOT applied automatically. Routed free-tier→paid like every other
    AI feature and metered per user / flow / step via the tp_collab_ai_merge
    touchpoint."""
    import json as _json
    from core import ai_wallet as _aw
    from core.ai_metering import metered_chat
    share = await db.shared_steps.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Shared step not found")
    if share["owner_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Only the owner can run AI merge")
    if not await _aw.touchpoint_enabled("tp_collab_ai_merge"):
        raise HTTPException(status_code=403, detail="AI merge is currently disabled by the administrator")

    module = share.get("module", "decision")
    step = share.get("step_number")
    flow_id = share.get("module_id") or share.get("decision_id") or share_id
    meta = _MODULE_META.get(module, _MODULE_META["decision"])
    owner_doc = await getattr(db, meta["coll"]).find_one(
        {meta["key"]: flow_id, "user_id": share["owner_id"]}, {"_id": 0}) or {}
    contribs = []
    for r in share.get("recipients", []):
        if r.get("status") == "contributed" and r.get("contribution"):
            c = r["contribution"]
            contribs.append({
                "contributor": r.get("name", r.get("email")),
                "capability": r.get("capability") or "unknown",
                "sme": bool(r.get("sme")),
                "sme_domains": r.get("sme_domains") or [],
                "resources": r.get("resources"),
                "input": (c.get("snapshot") if module != "decision" else
                          {"factors": c.get("factors"), "options": c.get("options"), "assessments": c.get("assessments")}),
                "note": c.get("note", ""),
            })
    if not contribs:
        raise HTTPException(status_code=400, detail="No contributions to merge yet")

    system_msg = (
        "You consolidate multiple contributors' inputs for ONE step of a decision-making flow "
        f"(module='{module}', step={step}). Produce the best merged version of THIS step.\n"
        f"Owner merge mode = '{share.get('merge_mode', 'equal')}'. Weight contributors by this mode AND by "
        "their capability/SME status, declared domains and available resources: an SME (subject-matter expert), "
        "a higher-capability contributor, or one whose declared resources are clearly relevant should carry more "
        "weight; 'self'/'self_weighted' mode means the owner's existing values dominate; 'equal' weights everyone "
        "equally; 'custom' respects provided weights.\n"
        "Return STRICT JSON only: {\"merged\": <object with the same shape as the owner's step fields>, "
        "\"rationale\": \"2-4 sentences explaining how you weighted SME/capability/resources & the owner's mode\"}. "
        "No prose outside JSON."
    )
    prompt = _json.dumps({
        "owner_current": owner_doc,
        "contributions": contribs,
        "instruction": "Merge into a single best version of this step's fields. Keep field names identical to owner_current where possible.",
    }, default=str)[:14000]
    meta_out: dict = {}
    try:
        raw = (await metered_chat(
            user["user_id"], system_message=system_msg, prompt=prompt,
            feature=f"collab_ai_merge:{module}:s{step}",
            session_prefix="collab_merge", session_id=f"{module}:{flow_id}",
            tier="fast", meta=meta_out,
        )).strip()
    except _aw.InsufficientCredits:
        raise HTTPException(status_code=402, detail="You're out of AI credits. Top up to use AI Auto-Merge.")
    except Exception as e:
        from core.llm_errors import llm_error_to_http
        raise llm_error_to_http(e)

    parsed = None
    try:
        txt = raw
        if "```" in txt:
            txt = txt.split("```")[1].replace("json", "", 1).strip() if txt.count("```") >= 2 else txt
        parsed = _json.loads(txt[txt.find("{"): txt.rfind("}") + 1])
    except Exception:
        parsed = {"merged": None, "rationale": raw[:400]}

    return {"proposal": parsed.get("merged"), "rationale": parsed.get("rationale", ""),
            "raw": raw, "charged": meta_out.get("credits"), "provider": meta_out.get("provider"),
            "balance": (await _aw.get_balance(user["user_id"])).get("balance")}


@router.post("/shared-steps/{share_id}/apply")
async def apply_merged_step(share_id: str, data: dict = Body(...), user: dict = Depends(get_current_user)):
    """Owner-only: write the (owner-reviewed) merged step fields back into the
    owner's record and mark the share merged. Contributions are preserved."""
    share = await db.shared_steps.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Shared step not found")
    if share["owner_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Only the owner can apply a merge")
    merged = data.get("merged")
    if not isinstance(merged, dict) or not merged:
        raise HTTPException(status_code=400, detail="merged (object of step fields) is required")
    module = share.get("module", "decision")
    meta = _MODULE_META.get(module, _MODULE_META["decision"])
    flow_id = share.get("module_id") or share.get("decision_id")
    # Never let the merge payload clobber identity/ownership fields.
    for protected in (meta["key"], "_id", "user_id", "id", "entry_id", "contribution_clone", "created_at"):
        merged.pop(protected, None)
    res = await getattr(db, meta["coll"]).update_one(
        {meta["key"]: flow_id, "user_id": share["owner_id"]},
        {"$set": {**merged, "updated_at": datetime.now(timezone.utc).isoformat()}})
    hist = {"at": datetime.now(timezone.utc).isoformat(), "by": user.get("name", "Owner"),
            "by_id": user["user_id"], "method": data.get("method", "manual"),
            "credits": data.get("credits"), "contributor": data.get("contributor"),
            "contributors_count": sum(1 for r in share.get("recipients", []) if r.get("status") == "contributed")}
    await db.shared_steps.update_one({"id": share_id},
        {"$set": {"status": "merged", "merged_at": datetime.now(timezone.utc).isoformat(),
                  "merge_method": data.get("method", "manual")},
         "$push": {"merge_history": hist}})
    return {"ok": True, "modified": res.modified_count}


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
    await db.shared_steps.update_one({"id": share_id}, {"$set": {"status": "merged", "merged_at": datetime.now(timezone.utc)},
        "$push": {"merge_history": {"at": datetime.now(timezone.utc).isoformat(), "by": user.get("name", "Owner"),
                                    "by_id": user["user_id"], "method": "weighted", "merge_mode": merge_mode,
                                    "credits": 0, "contributors_count": len(contributions)}}})
    for r in share.get("recipients", []):
        if r.get("contribution"):
            await create_notification(r["user_id"], "share_merged", "Contributions Merged",
                f'{user.get("name", "Someone")} merged your input for "{share.get("decision_title", "a decision")}"',
                {"share_id": share_id, "decision_id": share["decision_id"]})
    return {"message": "Contributions merged successfully", "weights": weights}
