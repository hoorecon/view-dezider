"""
Decision Reports — generates PDF reports unlocked by the L1 SKU.

A single endpoint serves all 3 modules:
    GET /api/reports/{module}/{decision_id}.pdf
    GET /api/reports/{module}/{decision_id}/info   (lightweight check)

Modules:
    dezider   → reads `decisions` (PRR Decision flow)
    pros_cons → reads `pros_cons`
    swot      → reads `swot_analyses`

Access policy (in order):
    1. Owner of the decision
    2. With an active L1 entitlement → consumes 1 token, marks decision
       `report_unlocked_for_user=True` so subsequent downloads are free for
       this user/decision pair.
    3. With an L2 / subscription → free download, no consumption.

Anyone without entitlement gets HTTP 402 "Payment Required".
"""

import io
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from core.auth import get_current_user
from core.database import db
from routes.sku_store import (
    consume_one,
    get_active_balance,
    has_any_paid_access,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["Decision Reports"])


# ────────────────────────────────────────────────────────────────────────────
# Module → MongoDB adapter
# ────────────────────────────────────────────────────────────────────────────
async def _load_decision(module: str, decision_id: str, user_id: str) -> Dict[str, Any]:
    module = module.lower()
    if module == "dezider":
        doc = await db.decisions.find_one(
            {"id": decision_id, "user_id": user_id}, {"_id": 0}
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Decision not found")
        return {"module": "dezider", "raw": doc, "title": doc.get("title", "Untitled Decision")}
    if module == "pros_cons":
        doc = await db.pros_cons.find_one(
            {"id": decision_id, "user_id": user_id}, {"_id": 0}
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Pros & Cons analysis not found")
        return {"module": "pros_cons", "raw": doc, "title": doc.get("title", "Untitled Pros & Cons")}
    if module == "swot":
        doc = await db.swot_analyses.find_one(
            {"id": decision_id, "user_id": user_id}, {"_id": 0}
        )
        if not doc:
            raise HTTPException(status_code=404, detail="SWOT analysis not found")
        return {"module": "swot", "raw": doc, "title": doc.get("title", "Untitled SWOT")}
    raise HTTPException(status_code=400, detail=f"Unknown module: {module}")


async def _check_access_and_maybe_consume(
    user_id: str, module: str, decision_id: str
) -> Dict[str, Any]:
    """Returns {access_via, consumed} or raises 402."""
    # Already unlocked this specific decision before?
    unlock_key = f"{module}:{decision_id}"
    prior = await db.decision_report_unlocks.find_one(
        {"user_id": user_id, "key": unlock_key}, {"_id": 0}
    )
    if prior:
        return {"access_via": prior.get("via", "prior_unlock"), "consumed": False}

    # Global admin skip-payment → free pass, but DON'T persist an unlock record:
    # this is a temporary override, so access must re-evaluate each time and
    # re-lock automatically once the admin turns the toggle off.
    access = await has_any_paid_access(user_id)
    if access.get("has_access") and access.get("via") == "admin_skip":
        return {"access_via": "admin_skip", "consumed": False}

    # L2 bundle / subscription → free pass (durable entitlement → persist unlock)
    if access.get("has_access") and access.get("via") in ("subscription", "L2"):
        await db.decision_report_unlocks.insert_one({
            "user_id": user_id,
            "key": unlock_key,
            "module": module,
            "decision_id": decision_id,
            "via": access["via"],
            "at": datetime.now(timezone.utc).isoformat(),
        })
        return {"access_via": access["via"], "consumed": False}

    # L1 single-use → try to consume
    if await consume_one(user_id, "L1", decision_id=decision_id, module=module):
        await db.decision_report_unlocks.insert_one({
            "user_id": user_id,
            "key": unlock_key,
            "module": module,
            "decision_id": decision_id,
            "via": "L1",
            "at": datetime.now(timezone.utc).isoformat(),
        })
        return {"access_via": "L1", "consumed": True}

    raise HTTPException(
        status_code=402,
        detail="No active entitlement. Purchase a DIY Decision Report (L1) to unlock.",
    )


@router.get("/{module}/{decision_id}/info")
async def report_info(
    module: str,
    decision_id: str,
    user: dict = Depends(get_current_user),
):
    """Lightweight check — returns whether the report is unlocked for this user
    + decision combo, and the user's current L1/L2 balances. Used by the
    final-summary screen to decide which button to show.
    """
    await _load_decision(module, decision_id, user["user_id"])  # validates ownership
    unlock_key = f"{module}:{decision_id}"
    prior = await db.decision_report_unlocks.find_one(
        {"user_id": user["user_id"], "key": unlock_key}, {"_id": 0}
    )
    # Free access (global admin skip-payment, active subscription, or L2 bundle)
    # should present as already-unlocked so the FE shows "Download PDF" — not a paywall.
    access = await has_any_paid_access(user["user_id"])
    free = bool(access.get("has_access")) and access.get("via") in ("subscription", "L2", "admin_skip")
    return {
        "module": module,
        "decision_id": decision_id,
        "unlocked": bool(prior) or free,
        "unlocked_via": (prior or {}).get("via") or (access.get("via") if free else None),
        "l1_balance": await get_active_balance(user["user_id"], "L1"),
        "l2_balance": await get_active_balance(user["user_id"], "L2"),
    }


# ────────────────────────────────────────────────────────────────────────────
# PDF rendering helpers (reportlab)
# ────────────────────────────────────────────────────────────────────────────
def _build_pdf(payload: Dict[str, Any]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=payload.get("title", "Decision Report"),
        author="JELCOS / Dezider",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "h1c", parent=styles["Heading1"],
        textColor=colors.HexColor("#1E40AF"), spaceAfter=10,
    )
    h2 = ParagraphStyle(
        "h2c", parent=styles["Heading2"],
        textColor=colors.HexColor("#1E3A8A"), spaceAfter=6,
    )
    body = ParagraphStyle("body", parent=styles["BodyText"], leading=14)
    small = ParagraphStyle(
        "small", parent=styles["BodyText"], fontSize=9,
        textColor=colors.HexColor("#64748B"),
    )

    story = []
    story.append(Paragraph("Dezider Decision Report", h1))
    story.append(Paragraph(payload.get("title", "Untitled"), h2))
    story.append(Paragraph(
        f"Module: <b>{payload['module_label']}</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Generated: <b>{payload['generated_at']}</b>",
        small,
    ))
    story.append(Spacer(1, 6 * mm))

    # Context / summary block
    if payload.get("context"):
        story.append(Paragraph("Context", h2))
        story.append(Paragraph(payload["context"], body))
        story.append(Spacer(1, 4 * mm))

    # Module-specific body
    for section in payload.get("sections", []):
        story.append(Paragraph(section["heading"], h2))
        if section.get("paragraph"):
            story.append(Paragraph(section["paragraph"], body))
            story.append(Spacer(1, 2 * mm))
        if section.get("table"):
            tbl = Table(section["table"], colWidths=section.get("colWidths"))
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E40AF")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                    [colors.white, colors.HexColor("#F1F5F9")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(tbl)
            story.append(Spacer(1, 4 * mm))

    # Footer
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        "Generated by JELCOS Dezider — this report is for the user's personal "
        "decision-making use. Confidential. © JELCOS",
        small,
    ))
    doc.build(story)
    return buf.getvalue()


def _pdf_payload_for_dezider(raw: Dict[str, Any]) -> Dict[str, Any]:
    sections = []
    options = raw.get("options") or []
    factors = raw.get("factors") or []

    sections.append({
        "heading": "Decision Type",
        "paragraph": f"Type: <b>{raw.get('decision_type', '—')}</b> · "
                     f"Life Area: <b>{raw.get('life_area', '—')}</b>",
    })

    if options:
        rows = [["#", "Option", "Final Score"]]
        for i, o in enumerate(options, 1):
            rows.append([
                str(i),
                str(o.get("name") or o.get("title") or f"Option {i}")[:80],
                f"{o.get('final_score', '—')}",
            ])
        sections.append({"heading": "Options Evaluated", "table": rows})

    if factors:
        rows = [["Factor", "Weight", "Direction"]]
        for f in factors:
            rows.append([
                str(f.get("name", "") or "")[:60],
                f"{f.get('weightage', '—')}",
                str(f.get("polarity") or f.get("direction") or "—"),
            ])
        sections.append({"heading": "Factors Considered", "table": rows})

    if raw.get("final_decision"):
        sections.append({
            "heading": "Final Decision",
            "paragraph": str(raw["final_decision"])[:1200],
        })

    return {
        "title": raw.get("title", "Untitled Decision"),
        "context": raw.get("context"),
        "module_label": "My Dezider",
        "sections": sections,
    }


def _pdf_payload_for_pros_cons(raw: Dict[str, Any]) -> Dict[str, Any]:
    sections = []
    options = raw.get("options") or []
    for o in options:
        pros = o.get("pros") or []
        cons = o.get("cons") or []
        max_rows = max(len(pros), len(cons), 1)
        rows = [["Pros", "Cons"]]
        for i in range(max_rows):
            p = pros[i] if i < len(pros) else {}
            c = cons[i] if i < len(cons) else {}
            rows.append([
                str((p.get("text") or p.get("name") or "—"))[:120],
                str((c.get("text") or c.get("name") or "—"))[:120],
            ])
        sections.append({
            "heading": f"Option: {o.get('name') or o.get('title') or 'Untitled'}",
            "table": rows,
        })

    if raw.get("final_decision"):
        sections.append({
            "heading": "Final Decision",
            "paragraph": str(raw["final_decision"])[:1200],
        })

    return {
        "title": raw.get("title", "Untitled Pros & Cons"),
        "context": raw.get("context"),
        "module_label": "Pros & Cons",
        "sections": sections,
    }


def _pdf_payload_for_swot(raw: Dict[str, Any]) -> Dict[str, Any]:
    sections = []
    quadrants = [
        ("Strengths",     raw.get("strengths") or []),
        ("Weaknesses",    raw.get("weaknesses") or []),
        ("Opportunities", raw.get("opportunities") or []),
        ("Threats",       raw.get("threats") or []),
    ]
    for label, items in quadrants:
        rows = [[label, "Impact"]]
        for it in items:
            rows.append([
                str(it.get("text") or it.get("name") or "—")[:140],
                str(it.get("impact") or "—"),
            ])
        if len(rows) == 1:
            rows.append(["(none captured)", "—"])
        sections.append({"heading": label, "table": rows})

    return {
        "title": raw.get("title", "Untitled SWOT"),
        "context": raw.get("context"),
        "module_label": "SWOT Analysis",
        "sections": sections,
    }


@router.get("/{module}/{decision_id}.pdf")
async def download_report_pdf(
    module: str,
    decision_id: str,
    user: dict = Depends(get_current_user),
):
    """Download the polished PDF for a decision. Consumes L1 if needed."""
    loaded = await _load_decision(module, decision_id, user["user_id"])
    raw = loaded["raw"]

    access = await _check_access_and_maybe_consume(user["user_id"], module, decision_id)

    builder = {
        "dezider":    _pdf_payload_for_dezider,
        "pros_cons":  _pdf_payload_for_pros_cons,
        "swot":       _pdf_payload_for_swot,
    }[module.lower()]
    payload = builder(raw)
    payload["generated_at"] = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

    pdf_bytes = _build_pdf(payload)
    filename = f"dezider_{module}_{decision_id[:8]}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Report-Access-Via": access.get("access_via", ""),
        },
    )
