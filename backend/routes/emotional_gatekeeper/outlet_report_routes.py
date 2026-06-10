"""Emotional Gatekeeper — Outlet Analyzer branded PDF + Email/WhatsApp share.

Reuses the JELCOS-branded `_build_pdf` (same header/footer as the MyDezider flow).
The Outlet Analyzer is metered via the AI wallet, so there is NO L1/L2 paywall here.
"""

import io
import os
import base64
import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from core.database import db
from routes.auth_routes import get_current_user
from routes.decision_reports import _build_pdf, _esc, _format_local, _user_timezone

logger = logging.getLogger(__name__)
router = APIRouter()

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM = os.getenv("RESEND_FROM_EMAIL") or "JELCOS AI <reports@updates.veales.in>"
ULTRAMSG_INSTANCE = os.getenv("ULTRAMSG_INSTANCE_ID")
ULTRAMSG_TOKEN = os.getenv("ULTRAMSG_API_TOKEN")

GROUP_LABEL = {"physical": "Physical", "mental": "Mental", "emotional": "Emotional", "energy": "Energy"}
FREQ_LABEL = {"often": "Often (6-7/wk)", "sometimes": "Sometimes (3-5/wk)",
              "rarely": "Rarely (1-2/wk)", "not_at_all": "Not at all", "prefer_not_say": "Prefer not to say"}


async def _load_outlet(session_id: str, user_id: str):
    session = await db.breakthrough_sessions.find_one({"id": session_id, "user_id": user_id}, {"_id": 0})
    if not session:
        raise HTTPException(404, "Session not found")
    outlet = await db.outlet_reflections.find_one({"session_id": session_id, "user_id": user_id}, {"_id": 0})
    if not outlet or not outlet.get("ai_analysis"):
        raise HTTPException(400, "No completed outlet analysis to export for this session.")
    return session, outlet


def _build_outlet_payload(session: dict, outlet: dict, generated_at: str) -> dict:
    a = outlet.get("ai_analysis", {}) or {}
    entries = outlet.get("entries", []) or []
    bd = a.get("group_breakdown", {}) or {}
    primary = a.get("primary_mode", "")
    secondary = a.get("secondary_mode", "")

    sections = []
    # Profile
    prof = f"Primary Outlet Mode: <b>{_esc(GROUP_LABEL.get(primary, primary or '—'))}</b>"
    if secondary:
        prof += f" &nbsp;|&nbsp; Secondary Outlet Mode: <b>{_esc(GROUP_LABEL.get(secondary, secondary))}</b>"
    sections.append({"heading": "Your Outlet Profile", "paragraph": prof})

    # Energy breakdown table
    order = ["physical", "mental", "emotional", "energy"]
    rows = [["Outlet Group", "Share of Energy"]]
    for k in order:
        if k in bd:
            rows.append([GROUP_LABEL.get(k, k), f"{bd[k]}%"])
    if len(rows) > 1:
        sections.append({"heading": "Where Your Energy Goes", "table": rows, "col_ratios": [2, 1]})

    # What you shared
    in_rows = [["Outlet", "Group", "Frequency", "Compulsive"]]
    for e in entries:
        in_rows.append([
            e.get("name", e.get("strategy_id", "")),
            GROUP_LABEL.get(e.get("nature", ""), e.get("nature", "")),
            FREQ_LABEL.get(e.get("frequency", ""), e.get("frequency", "")),
            "Yes" if e.get("is_compulsive") else "No",
        ])
    if len(in_rows) > 1:
        sections.append({"heading": "What You Shared", "table": in_rows, "col_ratios": [4, 2, 3, 2]})

    if a.get("mode_insight"):
        sections.append({"heading": "Mode Insight", "paragraph": _esc(a["mode_insight"])})

    def _swap_table(items, label):
        if not items:
            return
        t = [["Activity", "Replaces", "Why It Helps"]]
        for it in items:
            t.append([it.get("activity", ""), it.get("replaces", ""), it.get("why", "")])
        sections.append({"heading": label, "table": t, "col_ratios": [3, 3, 4]})

    _swap_table(a.get("primary_activities"),
                f"Primary Outlet Swaps — {GROUP_LABEL.get(primary, primary or '')}")
    _swap_table(a.get("secondary_activities"),
                f"Secondary Outlet Swaps — {GROUP_LABEL.get(secondary, secondary or '')}")

    if a.get("overall_pattern"):
        sections.append({"heading": "Overall Pattern", "paragraph": _esc(a["overall_pattern"])})
    if a.get("encouragement"):
        sections.append({"heading": "A Note for You", "paragraph": f"<i>{_esc(a['encouragement'])}</i>"})

    return {
        "title": session.get("title") or "Emotional Outlet Analysis",
        "module_label": "Emotional Outlet Analyzer",
        "generated_at": generated_at,
        "sections": sections,
    }


async def _outlet_pdf_bytes(session_id: str, user_id: str) -> tuple[bytes, str, dict]:
    session, outlet = await _load_outlet(session_id, user_id)
    tzname = await _user_timezone(user_id)
    generated_at = _format_local(datetime.now(timezone.utc), tzname)
    payload = _build_outlet_payload(session, outlet, generated_at)
    try:
        from routes.app_appearance import get_app_logo
        logo = await get_app_logo()
    except Exception:
        logo = None
    pdf = _build_pdf(payload, logo_data_url=logo)
    fname = f"outlet_analysis_{session_id[:10]}.pdf"
    return pdf, fname, payload


@router.get("/outlet/{session_id}/report.pdf")
async def outlet_report_pdf(session_id: str, user: dict = Depends(get_current_user)):
    pdf, fname, _ = await _outlet_pdf_bytes(session_id, user["user_id"])
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


class OutletShareRequest(BaseModel):
    channel: str  # 'email' | 'whatsapp'
    recipient_email: Optional[str] = None
    recipient_phone: Optional[str] = None


def _outlet_email_html(owner: str, title: str) -> str:
    return f"""
<div style="font-family:Helvetica,Arial,sans-serif;max-width:560px;margin:0 auto;color:#1f2937">
  <h2 style="color:#1E40AF;margin-bottom:4px">JELCOS AI</h2>
  <p style="color:#64748b;margin-top:0;font-style:italic">Joyful Executive's Life Choices Operating System — Powered by AI</p>
  <p><b>{_esc(owner)}</b> has shared an <b>Emotional Outlet Analysis</b> with you:</p>
  <p style="font-size:18px;font-weight:700;margin:8px 0">{_esc(title)}</p>
  <p>The full branded report is attached as a PDF — open it to see the outlet profile,
     energy breakdown and the suggested healthier swaps.</p>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0"/>
  <p style="color:#475569;font-size:13px">Best Wishes from
     <a href="https://jelcos.ai" style="color:#1E40AF">JELCOS AI</a></p>
</div>
""".strip()


async def _send_email_with_pdf(to: str, subject: str, html: str, pdf: bytes, fname: str) -> None:
    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY not configured")
    b64 = base64.b64encode(pdf).decode("ascii")
    async with httpx.AsyncClient(timeout=25) as client:
        for attempt in range(3):
            r = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
                json={"from": RESEND_FROM, "to": [to], "subject": subject, "html": html,
                      "attachments": [{"filename": fname, "content": b64}]},
            )
            if r.status_code < 300:
                return
            if r.status_code == 429 and attempt < 2:
                import asyncio
                await asyncio.sleep(0.7 * (attempt + 1))
                continue
            raise RuntimeError(f"Resend error {r.status_code}: {r.text[:300]}")


async def _send_whatsapp_text(to: str, body: str) -> None:
    if not (ULTRAMSG_INSTANCE and ULTRAMSG_TOKEN):
        raise RuntimeError("UltraMsg not configured")
    url = f"https://api.ultramsg.com/{ULTRAMSG_INSTANCE}/messages/chat"
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, data={"token": ULTRAMSG_TOKEN, "to": to, "body": body})
    if r.status_code >= 300:
        raise RuntimeError(f"UltraMsg error {r.status_code}: {r.text[:200]}")


@router.post("/outlet/{session_id}/share")
async def outlet_share(session_id: str, payload: OutletShareRequest, user: dict = Depends(get_current_user)):
    if payload.channel not in ("email", "whatsapp"):
        raise HTTPException(400, "channel must be 'email' or 'whatsapp'")
    pdf, fname, built = await _outlet_pdf_bytes(session_id, user["user_id"])
    owner = user.get("name") or "A JELCOS AI user"
    title = built.get("title", "Emotional Outlet Analysis")
    try:
        if payload.channel == "email":
            if not payload.recipient_email:
                raise HTTPException(400, "recipient_email required")
            await _send_email_with_pdf(
                payload.recipient_email.strip().lower(),
                f"{owner} shared an Emotional Outlet Analysis with you",
                _outlet_email_html(owner, title), pdf, fname,
            )
        else:
            if not payload.recipient_phone:
                raise HTTPException(400, "recipient_phone required")
            a = (await _load_outlet(session_id, user["user_id"]))[1].get("ai_analysis", {})
            wa = (
                f"*JELCOS AI*\n_Emotional Outlet Analysis_\n\n"
                f"{owner} shared their outlet profile: *{title}*\n\n"
                f"{a.get('mode_insight', '')}\n\n"
                f"_{a.get('encouragement', '')}_\n\nBest wishes from JELCOS AI 🙏"
            )
            await _send_whatsapp_text(payload.recipient_phone.strip(), wa)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Outlet share ({payload.channel}) failed: {e}")
        raise HTTPException(502, detail={"code": "share_failed",
                                         "message": f"Could not send via {payload.channel}. Please try again."})
    return {"ok": True, "sent": True, "channel": payload.channel}
