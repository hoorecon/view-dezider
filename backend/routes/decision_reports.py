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
def _esc(v) -> str:
    """Escape free text so it is safe inside a reportlab Paragraph."""
    from xml.sax.saxutils import escape
    return escape("" if v is None else str(v))


def _p(v) -> str:
    """Escaped value or an em-dash placeholder (safe to embed in markup)."""
    if v is None or v == "":
        return "—"
    return _esc(v)


def _num(v) -> str:
    """Compact number formatting (no trailing .0)."""
    if v is None or v == "":
        return "—"
    try:
        fv = float(v)
        return str(int(fv)) if fv == int(fv) else f"{fv:.1f}"
    except (TypeError, ValueError):
        return str(v)


def _t(v) -> str:
    """Raw cell text with an em-dash placeholder.

    NOTE: table cells are XML-escaped inside `_build_pdf`, so values returned
    here must NOT be pre-escaped (otherwise '&' becomes '&amp;amp;').
    """
    if v is None or v == "":
        return "—"
    return str(v)


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
        author="JELCOS AI",
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
    story.append(Paragraph("JELCOS AI — Decision Report", h1))
    story.append(Paragraph(_esc(payload.get("title", "Untitled")), h2))
    story.append(Paragraph(
        f"Module: <b>{_esc(payload['module_label'])}</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Generated: <b>{_esc(payload['generated_at'])}</b>",
        small,
    ))
    story.append(Spacer(1, 6 * mm))

    # Context / summary block
    if payload.get("context"):
        story.append(Paragraph("Context", h2))
        story.append(Paragraph(_esc(payload["context"]), body))
        story.append(Spacer(1, 4 * mm))

    # Available content width — tables are sized to this so they never overflow.
    content_width = A4[0] - doc.leftMargin - doc.rightMargin
    cell_style = ParagraphStyle("cell", parent=body, fontSize=9, leading=12)
    head_cell_style = ParagraphStyle(
        "hcell", parent=body, fontSize=9.5, leading=12,
        textColor=colors.white, fontName="Helvetica-Bold",
    )

    # Module-specific body
    for section in payload.get("sections", []):
        if section.get("heading"):
            story.append(Paragraph(_esc(section["heading"]), h2))
        if section.get("paragraph"):
            story.append(Paragraph(section["paragraph"], body))
            story.append(Spacer(1, 2 * mm))
        if section.get("table"):
            data = section["table"]
            ncols = len(data[0]) if data else 1
            ratios = section.get("col_ratios") or [1] * ncols
            tot = float(sum(ratios)) or 1.0
            col_widths = [content_width * (r / tot) for r in ratios]
            # Wrap each cell in a Paragraph so long text wraps within its column
            # instead of running off the page edge.
            wrapped = []
            for ri, row in enumerate(data):
                style = head_cell_style if ri == 0 else cell_style
                wrapped.append([
                    c if isinstance(c, Paragraph) else Paragraph(_esc(c), style)
                    for c in row
                ])
            tbl = Table(wrapped, colWidths=col_widths, repeatRows=1)
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E40AF")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                    [colors.white, colors.HexColor("#F8FAFC")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(tbl)
            story.append(Spacer(1, 4 * mm))

    # Footer
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        "Generated by JELCOS AI — this report is for your personal "
        "decision-making use. Confidential. © JELCOS AI",
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
    """Build a COMPLETE Pros & Cons report.

    Handles both schemas:
      • Rich (Step-7 revamp): factors + options + assessments + rollups →
        full prioritisation, ranking, Satisfaction %, and per-option detail.
      • Flat (legacy): standalone `pros`/`cons` lists with importance.
    """
    sections = []

    factors = raw.get("factors") or []
    options = raw.get("options") or []
    assessments = raw.get("assessments") or {}
    rollups = raw.get("rollups") or []
    flat_pros = raw.get("pros") or []
    flat_cons = raw.get("cons") or []

    is_rich = bool(factors) and bool(options)

    # ── Decision overview (always) ──────────────────────────────────────────
    sections.append({
        "heading": "Decision Overview",
        "paragraph": (
            f"Type: <b>{_esc(raw.get('decision_type') or '—')}</b> "
            f"&nbsp;&nbsp;·&nbsp;&nbsp; Life Area: "
            f"<b>{_esc(raw.get('life_area') or '—')}</b>"
        ),
    })

    if is_rich:
        # ── Factors & Priorities ────────────────────────────────────────────
        fsorted = sorted(factors, key=lambda f: (f.get("priority_rank") or 9999))
        frows = [["Rank", "Factor", "Type", "Std Rating", "Expected", "Unit"]]
        for f in fsorted:
            frows.append([
                _num(f.get("priority_rank")),
                _t(f.get("name")),
                (str(f.get("notation") or "").capitalize() or "—"),
                _num(f.get("std_rating")),
                _t(f.get("expected_value")),
                _t(f.get("unit")),
            ])
        sections.append({
            "heading": "Factors & Priorities",
            "table": frows,
            "col_ratios": [0.8, 3.0, 1.5, 1.4, 1.6, 1.1],
        })

        # ── Options Ranking — Satisfaction % ────────────────────────────────
        roll_by_opt = {r.get("option_id"): r for r in rollups}

        def _rank_key(o):
            r = roll_by_opt.get(o.get("id")) or {}
            rk = r.get("rank_high_to_low")
            return rk if rk is not None else 9999

        osorted = sorted(options, key=_rank_key)
        orows = [["Rank", "Option", "Joint Score", "Satisfaction %", "Status"]]
        for o in osorted:
            r = roll_by_opt.get(o.get("id")) or {}
            orows.append([
                _num(r.get("rank_high_to_low")),
                _t(o.get("name")),
                _num(r.get("joint_score")),
                f"{_num(r.get('overall_satisfaction_pct'))}%",
                "Disqualified" if r.get("disqualified") else "Qualified",
            ])
        sections.append({
            "heading": "Options Ranking — Satisfaction %",
            "table": orows,
            "col_ratios": [0.8, 2.6, 1.4, 1.6, 1.4],
        })

        # ── Per-option detailed assessment matrix ───────────────────────────
        for o in osorted:
            oid = o.get("id")
            cell_map = assessments.get(oid) or {}
            if not cell_map:
                continue
            drows = [["Factor", "Actual Value", "Satisfaction %", "Assessment %"]]
            for f in fsorted:
                cell = cell_map.get(f.get("id"))
                if not cell:
                    continue
                drows.append([
                    _t(f.get("name")),
                    _t(cell.get("actual_value")),
                    f"{_num(cell.get('satisfaction_pct'))}%",
                    f"{_num(cell.get('assessment_pct'))}%",
                ])
            if len(drows) > 1:
                sections.append({
                    "heading": f"Assessment Detail — {o.get('name') or 'Option'}",
                    "table": drows,
                    "col_ratios": [3.0, 2.0, 1.6, 1.6],
                })

        # ── Pros & Cons captured per option (optional) ──────────────────────
        for o in osorted:
            pros = o.get("pros") or []
            cons = o.get("cons") or []
            if not pros and not cons:
                continue
            max_rows = max(len(pros), len(cons), 1)
            rows = [["Pros", "Cons"]]
            for i in range(max_rows):
                p = pros[i] if i < len(pros) else {}
                c = cons[i] if i < len(cons) else {}
                rows.append([
                    _t(p.get("text") or p.get("name")),
                    _t(c.get("text") or c.get("name")),
                ])
            sections.append({
                "heading": f"Pros & Cons — {o.get('name') or 'Option'}",
                "table": rows,
                "col_ratios": [1, 1],
            })

        # ── Recommendation (top-ranked qualified option) ────────────────────
        top = next(
            ((o, roll_by_opt.get(o.get("id")) or {}) for o in osorted
             if not (roll_by_opt.get(o.get("id")) or {}).get("disqualified")),
            None,
        )
        if top:
            o, r = top
            sections.append({
                "heading": "Recommendation",
                "paragraph": (
                    f"Based on your prioritised factors, "
                    f"<b>{_esc(o.get('name') or 'the top option')}</b> ranks highest "
                    f"with a joint score of <b>{_esc(_num(r.get('joint_score')))}</b> "
                    f"and an overall satisfaction of "
                    f"<b>{_esc(_num(r.get('overall_satisfaction_pct')))}%</b>."
                ),
            })
    else:
        # ── Legacy flat schema: standalone Pros / Cons with importance ───────
        if flat_pros:
            rows = [["Pro", "Description", "Importance"]]
            for p in flat_pros:
                rows.append([
                    _t(p.get("text") or p.get("name")),
                    _t(p.get("description")),
                    _num(p.get("importance")),
                ])
            sections.append({
                "heading": "Pros", "table": rows,
                "col_ratios": [2.0, 3.4, 1.2],
            })
        if flat_cons:
            rows = [["Con", "Description", "Importance"]]
            for c in flat_cons:
                rows.append([
                    _t(c.get("text") or c.get("name")),
                    _t(c.get("description")),
                    _num(c.get("importance")),
                ])
            sections.append({
                "heading": "Cons", "table": rows,
                "col_ratios": [2.0, 3.4, 1.2],
            })
        if not flat_pros and not flat_cons:
            sections.append({
                "heading": "No Data",
                "paragraph": "This analysis has no pros, cons, or factor data yet.",
            })

    if raw.get("final_decision"):
        sections.append({
            "heading": "Final Decision",
            "paragraph": _esc(str(raw["final_decision"])[:1500]),
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
