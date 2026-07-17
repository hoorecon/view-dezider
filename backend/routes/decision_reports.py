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
from zoneinfo import ZoneInfo

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
        doc["_action_items"] = await db.action_items.find(
            {"user_id": user_id, "source_module": "MYDEZIDER_MPPS", "source_id": decision_id},
            {"_id": 0},
        ).sort("by_when", 1).to_list(200)
        return {"module": "dezider", "raw": doc, "title": doc.get("title", "Untitled Decision")}
    if module == "pros_cons":
        doc = await db.pros_cons.find_one(
            {"id": decision_id, "user_id": user_id}, {"_id": 0}
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Pros & Cons analysis not found")
        doc["_action_items"] = await db.action_items.find(
            {"user_id": user_id, "source_module": "PROS_CONS", "source_id": decision_id},
            {"_id": 0},
        ).sort("by_when", 1).to_list(200)
        return {"module": "pros_cons", "raw": doc, "title": doc.get("title", "Untitled Pros & Cons")}
    if module == "swot":
        doc = await db.swot_analyses.find_one(
            {"id": decision_id, "user_id": user_id}, {"_id": 0}
        )
        if not doc:
            raise HTTPException(status_code=404, detail="SWOT analysis not found")
        return {"module": "swot", "raw": doc, "title": doc.get("title", "Untitled SWOT")}
    if module == "solution_finder":
        doc = await db.solution_finders.find_one(
            {"entry_id": decision_id, "user_id": user_id}, {"_id": 0}
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Solution Finder entry not found")
        return {"module": "solution_finder", "raw": doc,
                "title": doc.get("smart_goal") or "Solution Finder"}
    if module == "assessment":
        doc = await db.assessments.find_one(
            {"id": decision_id, "user_id": user_id}, {"_id": 0}
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Assessment not found")
        owner = "My" if doc.get("subject_type") != "other" else (doc.get("subject_name") or "Someone")
        title = "My Decision-Making Style" if doc.get("subject_type") != "other" else f"{owner}'s Decision-Making Style"
        return {"module": "assessment", "raw": doc, "title": title}
    raise HTTPException(status_code=400, detail=f"Unknown module: {module}")


_DMS_LABELS = {"emotional": "Emotional", "logical": "Logical",
               "intuitive": "Intuitive", "consciousness": "Consciousness"}


def _pdf_payload_for_assessment(raw: Dict[str, Any]) -> Dict[str, Any]:
    is_other = raw.get("subject_type") == "other"
    owner = (raw.get("subject_name") or "Someone") if is_other else "Your"
    owner_poss = f"{raw.get('subject_name')}'s" if is_other and raw.get("subject_name") else "Your"
    dominant = _DMS_LABELS.get(raw.get("dominant_mode"), raw.get("dominant_mode") or "—")
    scores = raw.get("mode_scores") or {}
    rows = [["Decision Style", "Score"]]
    for k, v in scores.items():
        try:
            pct = f"{round(float(v) * 20)}%"
        except Exception:
            pct = str(v)
        rows.append([_DMS_LABELS.get(k, k), pct])
    sections = [{
        "heading": "Style Breakdown",
        "table": rows,
        "col_ratios": [3, 1],
    }]
    if raw.get("ai_insight"):
        sections.append({"heading": "Personalized AI Insight", "paragraph": _esc(raw["ai_insight"])})
    return {
        "title": f"{owner_poss} Decision-Making Style",
        "context": f"Dominant decision-making style: {dominant}.",
        "module_label": "Decision-Making Style",
        "sections": sections,
    }


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


def _build_pdf(payload: Dict[str, Any], logo_data_url=None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    )

    buf = io.BytesIO()

    # Optional admin-configured logo (data URL) drawn on every page header.
    _logo_reader = None
    if logo_data_url:
        try:
            import base64 as _b64
            _raw = logo_data_url.split(",", 1)[1] if "," in logo_data_url else logo_data_url
            _logo_reader = ImageReader(io.BytesIO(_b64.b64decode(_raw)))
        except Exception:
            _logo_reader = None

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=(28 if _logo_reader else 18) * mm, bottomMargin=18 * mm,
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
    subtitle = ParagraphStyle(
        "subtitle", parent=styles["BodyText"], fontSize=10,
        textColor=colors.HexColor("#64748B"), spaceAfter=8,
        fontName="Helvetica-Oblique",
    )
    brand_footer = ParagraphStyle(
        "brandfoot", parent=styles["BodyText"], fontSize=9.5,
        textColor=colors.HexColor("#475569"), alignment=1,
    )

    _BRAND_LINK = ('<a href="https://jelcos.ai"><font color="#1E40AF">'
                   '<u>JELCOS AI</u></font></a>')

    story = []
    story.append(Paragraph(f"{_BRAND_LINK} — Decision Report", h1))
    story.append(Paragraph(
        "Joyful Executive's Life Choices Operating System — Powered by AI", subtitle))
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
        if section.get("page_break"):
            story.append(PageBreak())
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

    # Footer — branding + lead magnet + legal disclaimer
    # Disclaimer wording is shared with the on-screen Breakthrough Report
    # card so paper and pixel match. Single source: utils.pdf_disclaimer.
    from utils.pdf_disclaimer import legal_disclaimer_flowables
    story.append(Spacer(1, 6 * mm))
    story.extend(legal_disclaimer_flowables(top_gap_mm=0))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"Best Wishes from {_BRAND_LINK}", brand_footer))
    story.append(Paragraph(
        "Joyful Executive's Life Choices Operating System · Powered by AI", brand_footer))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "This report is for your personal decision-making use. Confidential. © JELCOS AI",
        brand_footer,
    ))

    def _page_footer(canvas, _doc):
        canvas.saveState()
        # Admin logo on the header of every page (top-right).
        if _logo_reader is not None:
            try:
                _lw, _lh = 30 * mm, 14 * mm
                canvas.drawImage(
                    _logo_reader, A4[0] - 18 * mm - _lw, A4[1] - 20 * mm,
                    width=_lw, height=_lh, preserveAspectRatio=True,
                    anchor="ne", mask="auto",
                )
            except Exception:
                pass
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#94A3B8"))
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {_doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buf.getvalue()


def _dez_effective_pct(factor, factors, a_by_fid):
    """Effective assessment % for a factor — weighted avg of sub-factors when
    present, else its own assessment (mirrors calculateDynamicWorth)."""
    subs = [f for f in factors if f.get("parent_id") == factor.get("id")]
    if not subs:
        return a_by_fid.get(factor.get("id"))
    wsum = 0.0
    wtot = 0.0
    any_ = False
    for sub in subs:
        sp = a_by_fid.get(sub.get("id"))
        sw = float(sub.get("weight") or 0)
        if sp is not None and sw > 0:
            wsum += float(sp) * sw / 100.0
            wtot += sw
            any_ = True
    if not any_ or wtot == 0:
        return None
    return round(wsum * (100.0 / wtot), 1)


def _dez_worth(option, factors, overrides=None):
    """Option worth % = Σ(rating × effective% / 100) / Σ rating × 100."""
    top = [f for f in factors if not f.get("parent_id")]
    total_rating = sum(float(f.get("rating") or 0) for f in top)
    if total_rating <= 0:
        return 0.0
    a_by_fid = {a.get("factor_id"): a.get("percentage")
                for a in (option.get("assessments") or [])}
    if overrides:
        a_by_fid = {**a_by_fid, **overrides}
    wsum = 0.0
    for f in top:
        pct = _dez_effective_pct(f, factors, a_by_fid)
        if pct is not None:
            wsum += float(f.get("rating") or 0) * max(0.0, min(100.0, float(pct))) / 100.0
    return round(min(100.0, max(0.0, wsum / total_rating * 100.0)), 1)


def _pdf_payload_for_dezider(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Detailed My Dezider report — mirrors Pros & Cons: intake overview,
    factors, per-option assessment detail, Satisfaction-% ranking + Standard
    Recommendation, and MPPS analysis + Final Recommendation."""
    sections = [_decision_overview_section(raw)]

    options = raw.get("options") or []
    factors = raw.get("factors") or []
    top = [f for f in factors if not f.get("parent_id")]
    fsorted = sorted(top, key=lambda f: (f.get("order") if f.get("order") is not None else 9999))

    if not options or not factors:
        # Minimal fallback for empty decisions
        if raw.get("final_decision"):
            sections.append({"heading": "Final Decision",
                             "paragraph": _esc(str(raw["final_decision"])[:1500])})
        return {"title": raw.get("title", "Untitled Decision"),
                "context": raw.get("context"), "module_label": "My Dezider",
                "sections": sections}

    # ── Factors & Priorities ────────────────────────────────────────────────
    frows = [["#", "Factor", "Category", "Rating"]]
    for i, f in enumerate(fsorted, 1):
        frows.append([
            _num(i), _t(f.get("name")),
            _t(str(f.get("category") or "").title() or "—"), _num(f.get("rating")),
        ])
    sections.append({"heading": "Factors & Priorities", "table": frows,
                     "col_ratios": [0.7, 3.4, 1.6, 1.2]})

    # ── Per-option metrics ──────────────────────────────────────────────────
    worth_by_opt = {o.get("id"): _dez_worth(o, factors) for o in options}
    osorted = sorted(options, key=lambda o: worth_by_opt.get(o.get("id"), 0), reverse=True)

    # ── Assessment Detail per option (Satisfaction %) ───────────────────────
    for o in osorted:
        a_by_fid = {a.get("factor_id"): a.get("percentage")
                    for a in (o.get("assessments") or [])}
        drows = [["Factor", "Satisfaction %"]]
        for f in fsorted:
            pct = _dez_effective_pct(f, factors, a_by_fid)
            if pct is None:
                continue
            drows.append([_t(f.get("name")), f"{_num(pct)}%"])
        if len(drows) > 1:
            sections.append({
                "heading": f"Assessment Detail — {o.get('name') or 'Option'}",
                "table": drows, "col_ratios": [3.6, 1.6],
            })

    # ── Options Ranking — Satisfaction % + Standard Recommendation ──────────
    orows = [["Rank", "Option", "Satisfaction %"]]
    for i, o in enumerate(osorted, 1):
        orows.append([_num(i), _t(o.get("name")), f"{_num(worth_by_opt.get(o.get('id')))}%"])
    sections.append({"heading": "Options Ranking — Satisfaction %", "table": orows,
                     "col_ratios": [0.8, 3.2, 1.8]})

    if osorted:
        top_o = osorted[0]
        sections.append({
            "heading": "Standard Recommendation",
            "paragraph": (
                f"Based on your weighted factors, "
                f"<b>{_esc(top_o.get('name') or 'the top option')}</b> ranks #1 "
                f"with a satisfaction of <b>{_esc(_num(worth_by_opt.get(top_o.get('id'))))}%</b>."
            ),
        })

    # ── MPPS Analysis + Final Recommendation (per-option, Phase 4) ──────────
    mpps_by_option = raw.get("mpps_by_option") or {}
    if not mpps_by_option and raw.get("mpps_option_id") and raw.get("mpps_improvements"):
        mpps_by_option = {raw["mpps_option_id"]: raw["mpps_improvements"]}
    mpps_by_option = {oid: imps for oid, imps in mpps_by_option.items()
                      if any(i.get("factor_id") for i in (imps or []))}
    if mpps_by_option:
        fname = {f.get("id"): f.get("name") for f in factors}
        opt_by_id = {o.get("id"): o for o in options}
        mpps_worth = dict(worth_by_opt)
        for oid, imps in mpps_by_option.items():
            opt = opt_by_id.get(oid)
            if not opt:
                continue
            overrides = {i.get("factor_id"): i.get("projected_percentage")
                         for i in imps if i.get("projected_percentage") is not None}
            mpps_worth[oid] = _dez_worth(opt, factors, overrides=overrides)
            irows = [["Factor", "Current %", "Projected %", "Improvement Plan"]]
            for imp in imps:
                cur = imp.get("original_percentage")
                proj = imp.get("projected_percentage")
                irows.append([
                    _t(fname.get(imp.get("factor_id")) or "—"),
                    f"{_num(cur)}%" if cur is not None else "—",
                    f"{_num(proj)}%" if proj is not None else "—",
                    _t(imp.get("improvement_plan")),
                ])
            sections.append({
                "heading": f"MPPS Improvements — {opt.get('name') or 'Option'}",
                "table": irows, "col_ratios": [2.6, 1.2, 1.3, 3.2],
            })

        ranked_mpps = sorted(options, key=lambda o: mpps_worth.get(o.get("id"), 0), reverse=True)
        mrows = [["Rank", "Option", "Satisfaction %", "MPPS Satisfaction %"]]
        for i, o in enumerate(ranked_mpps, 1):
            mrows.append([
                _num(i), _t(o.get("name")),
                f"{_num(worth_by_opt.get(o.get('id')))}%",
                f"{_num(mpps_worth.get(o.get('id')))}%",
            ])
        sections.append({"heading": "Revised Ranking after MPPS", "table": mrows,
                         "col_ratios": [0.8, 3.0, 1.8, 2.0]})

        if ranked_mpps:
            top_m = ranked_mpps[0]
            sections.append({
                "heading": "Final Recommendation",
                "paragraph": (
                    f"After MPPS improvements, "
                    f"<b>{_esc(top_m.get('name') or 'the top option')}</b> ranks #1 "
                    f"with a projected satisfaction of "
                    f"<b>{_esc(_num(mpps_worth.get(top_m.get('id'))))}%</b> "
                    f"(was {_esc(_num(worth_by_opt.get(top_m.get('id'))))}%)."
                ),
            })

    # ── Final Decision (chosen option + reason + review date) + Action Plan ──
    opt_name_by_id = {o.get("id"): o.get("name") for o in options}
    chosen_id = raw.get("chosen_option_id")
    fd_lines = []
    if chosen_id and opt_name_by_id.get(chosen_id):
        fd_lines.append(f"<b>Final Choice:</b> {_esc(opt_name_by_id.get(chosen_id))}")
    elif raw.get("final_decision"):
        fd_lines.append(f"<b>Final Choice:</b> {_esc(str(raw['final_decision'])[:1000])}")
    case = (raw.get("decision_case") or "").replace("_", " ").strip()
    if chosen_id and case:
        fd_lines.append(f"<b>Decision type:</b> {_esc(case.title())}")
    if raw.get("final_choice_reason"):
        fd_lines.append(f"<b>Reason:</b> {_esc(raw['final_choice_reason'])}")
    if raw.get("implementation_review_date"):
        fd_lines.append(f"<b>Review on:</b> {_esc(_ddmmyyyy(raw['implementation_review_date']))}")
    if raw.get("final_choice_decided_at"):
        fd_lines.append(f"<b>Decided on:</b> {_esc(_fmt_date(raw['final_choice_decided_at']))}")
    if fd_lines:
        sections.append({"heading": "Final Decision", "paragraph": "<br/>".join(fd_lines)})

    aps = _action_plan_section(raw.get("_action_items") or [])
    if aps:
        sections.append(aps)

    return {
        "title": raw.get("title", "Untitled Decision"),
        "context": raw.get("context"),
        "module_label": "My Dezider",
        "sections": sections,
    }


# ── Master label maps (mirror frontend constants/lifeAreas.ts) ──────────────
_LIFE_AREA_LABELS = {
    "holistic_health": "Holistic Health",
    "knowledge_skills": "Knowledge & Skills",
    "relationships": "Relationships",
    "finance": "Finance",
    "assets": "Assets",
    "career": "Career",
    "hobbies_entertainment": "Hobbies & Entertainment",
    "social_image": "Social Image & Influence",
    "social_contributions": "Social Contributions",
    "spirituality_religion": "Spirituality & Religion",
}

_DECISION_TYPE_LABELS = {
    "need": "Need",
    "want": "Want",
    "problem": "Problem",
    "aspiration": "Aspiration",
    "product_purchase": "Product Purchase",
    "standard": "Standard Decision",
    "lifestyle_analyzer": "Lifestyle Analyzer",
}


def _label_from(code, mapping) -> Optional[str]:
    """Resolve a stored slug (possibly `la_`/`dt_`-prefixed) to a human label."""
    if not code:
        return None
    key = str(code).strip()
    for pfx in ("la_", "dt_"):
        if key.startswith(pfx):
            key = key[len(pfx):]
    if key in mapping:
        return mapping[key]
    return key.replace("_", " ").title()


def _life_area_label(code) -> Optional[str]:
    return _label_from(code, _LIFE_AREA_LABELS)


def _decision_type_label(code) -> Optional[str]:
    return _label_from(code, _DECISION_TYPE_LABELS)


_ACTING_AS_LABELS = {
    "INDIVIDUAL": "Individual",
    "ORGANIZATION": "Organization",
    "BUSINESS_ORG": "Business / Organization",
    "BUSINESS": "Business",
    "GOVERNMENT": "Government",
}


def _acting_as_label(code) -> Optional[str]:
    if not code:
        return None
    return _ACTING_AS_LABELS.get(str(code).upper(), str(code).replace("_", " ").title())


# ── Timezone: report timestamp in the user's local zone (Profile → country) ──
_COUNTRY_TZ = {
    "india": "Asia/Kolkata", "in": "Asia/Kolkata", "bharat": "Asia/Kolkata",
    "united states": "America/New_York", "united states of america": "America/New_York",
    "usa": "America/New_York", "us": "America/New_York", "america": "America/New_York",
    "united kingdom": "Europe/London", "uk": "Europe/London",
    "england": "Europe/London", "britain": "Europe/London",
    "united arab emirates": "Asia/Dubai", "uae": "Asia/Dubai",
    "singapore": "Asia/Singapore", "sg": "Asia/Singapore",
    "australia": "Australia/Sydney", "au": "Australia/Sydney",
    "canada": "America/Toronto", "ca": "America/Toronto",
    "germany": "Europe/Berlin", "france": "Europe/Paris",
    "saudi arabia": "Asia/Riyadh", "ksa": "Asia/Riyadh",
    "qatar": "Asia/Qatar", "kuwait": "Asia/Kuwait",
    "oman": "Asia/Muscat", "bahrain": "Asia/Bahrain",
    "malaysia": "Asia/Kuala_Lumpur", "japan": "Asia/Tokyo", "china": "Asia/Shanghai",
    "new zealand": "Pacific/Auckland", "south africa": "Africa/Johannesburg",
    "nepal": "Asia/Kathmandu", "sri lanka": "Asia/Colombo",
    "bangladesh": "Asia/Dhaka", "pakistan": "Asia/Karachi",
}
_DEFAULT_TZ = "Asia/Kolkata"


async def _user_timezone(user_id: str) -> str:
    """Resolve the user's timezone from their Self-contact `country`. Falls
    back to IST (Asia/Kolkata) when country is blank or unmapped."""
    try:
        c = await db.contacts.find_one(
            {"user_id": user_id, "is_self": True}, {"_id": 0, "country": 1}
        )
        country = ((c or {}).get("country") or "").strip().lower()
    except Exception:
        country = ""
    return _COUNTRY_TZ.get(country, _DEFAULT_TZ)


def _format_local(dt_utc: datetime, tzname: str) -> str:
    try:
        local = dt_utc.astimezone(ZoneInfo(tzname))
    except Exception:
        local = dt_utc
    abbr = local.tzname() or ""
    return local.strftime(f"%d-%m-%Y, %H:%M {abbr}").strip()


def _decision_overview_section(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Shared 'Decision Overview' block — surfaces the initial intake info
    (For / Life Area / Type / Sub-area / Scenario). Reused across all modules."""
    type_label = _decision_type_label(raw.get("decision_type")) or "Need"
    area_label = _life_area_label(raw.get("life_area") or raw.get("area_of_life")) or "Not specified"
    acting = _acting_as_label(raw.get("acting_as_context"))
    lines = []
    if acting:
        lines.append(f"For: <b>{_esc(acting)}</b>")
    lines.append(f"Life Area: <b>{_esc(area_label)}</b>")
    lines.append(f"Type: <b>{_esc(type_label)}</b>")
    sub = raw.get("sub_area_name") or raw.get("sub_area")
    if sub:
        lines.append(f"Sub-area: <b>{_esc(sub)}</b>")
    scen = raw.get("scenario_title") or raw.get("scenario")
    if scen:
        lines.append(f"Scenario: <b>{_esc(scen)}</b>")
    return {"heading": "Decision Overview", "paragraph": "<br/>".join(lines)}


def _fmt_date(v) -> str:
    if not v:
        return "—"
    try:
        s = str(v).replace("Z", "+00:00")
        return datetime.fromisoformat(s).strftime("%d-%m-%Y, %H:%M")
    except Exception:
        return str(v)[:25]


def _ddmmyyyy(v) -> str:
    """Display a date as DD-MM-YYYY (accepts 'YYYY-MM-DD' or full ISO datetime).
    Returns an em-dash placeholder when empty so it is table-cell safe."""
    if v is None or v == "":
        return "—"
    import re
    s = str(v).strip()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%d-%m-%Y")
    except Exception:
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else s


def _fmt_status(v) -> str:
    """Render a canonical action status code (e.g. 'wip_25') as 'WIP 25%'."""
    from core.action_status import status_label
    if v is None or v == "":
        return "—"
    return status_label(v)


def _action_plan_section(action_items):
    """Action Plan table (ID · Action · Who · By When · Recurrence · Status).
    Shared by Pros & Cons and My Dezider reports."""
    if not action_items:
        return None
    rows = [["ID", "Action", "Who", "By When", "Recurrence", "Status"]]
    for idx, a in enumerate(action_items, 1):
        rec = (a.get("recurrence_type") or "").lower()
        if rec == "recurring":
            rec = (a.get("recurrence_frequency") or "Recurring").title()
        else:
            rec = "One-time"
        rows.append([
            _num(idx),
            _t(a.get("title")),
            _t(a.get("who")),
            _ddmmyyyy(a.get("by_when")),
            rec,
            _fmt_status(a.get("status")),
        ])
    return {"heading": "Action Plan — Who · What · By When", "table": rows,
            "col_ratios": [0.6, 3.0, 1.6, 1.4, 1.4, 1.2]}


def _final_decision_sections(raw, opt_name_by_id, action_items):
    """Final Decision + Reason + Review Date + Action Plan — appended after MPPS."""
    out = []
    cfg = raw.get("config") or {}
    chosen_id = cfg.get("final_choice_option_id")
    reason = cfg.get("final_choice_reason")
    rt_val = cfg.get("review_timeline_value")
    rt_unit = cfg.get("review_timeline_unit") or "Months"
    decided_at = cfg.get("final_choice_decided_at")

    lines = []
    if chosen_id and opt_name_by_id.get(chosen_id):
        lines.append(f"<b>Final Choice:</b> {_esc(opt_name_by_id.get(chosen_id))}")
    elif raw.get("final_decision"):
        lines.append(f"<b>Final Choice:</b> {_esc(str(raw['final_decision'])[:1000])}")
    if reason:
        lines.append(f"<b>Reason:</b> {_esc(reason)}")
    if rt_val:
        lines.append(f"<b>Review in:</b> {_esc(_num(rt_val))} {_esc(rt_unit)}")
    if decided_at:
        lines.append(f"<b>Decided on:</b> {_esc(_fmt_date(decided_at))}")
    if lines:
        out.append({"heading": "Final Decision", "paragraph": "<br/>".join(lines)})

    aps = _action_plan_section(action_items)
    if aps:
        out.append(aps)
    return out


def _scoring_factors(factors):
    """Top-level, non-duplicate factors — the only ones that score (mirrors
    compute_option_rollups in decision_framework_models)."""
    return [
        f for f in (factors or [])
        if not f.get("parent_id") and not f.get("is_duplicate")
    ]


def _total_std_rating(sfactors) -> float:
    return float(sum(float(f.get("std_rating") or 0) for f in sfactors))


def _option_metrics(sfactors, opt_assess, total, mandatory_threshold):
    """Returns dict with joint_score, worth %, mpps worth %, improvement count,
    disqualified + ids — all derived from `assessment_pct` (Satisfaction %) and
    the Step-8 `improvement_pct` delta (MPPS / Case-2)."""
    opt_assess = opt_assess or {}
    js = 0.0
    mpps_js = 0.0
    n_imp = 0
    dq_ids = []
    for f in sfactors:
        cell = opt_assess.get(f.get("id"), {}) or {}
        std = float(f.get("std_rating") or 0)
        a = float(cell.get("assessment_pct") or 0)
        imp = float(cell.get("improvement_pct") or 0)
        eff = max(0.0, min(100.0, a + imp))
        js += a * std / 100.0
        mpps_js += eff * std / 100.0
        if imp:
            n_imp += 1
        if (mandatory_threshold is not None
                and f.get("notation") == "mandatory"
                and int(a) < int(mandatory_threshold)):
            dq_ids.append(f.get("id"))
    worth = (js / total * 100.0) if total > 0 else 0.0
    mpps_worth = (mpps_js / total * 100.0) if total > 0 else 0.0
    return {
        "joint_score": round(js, 1),
        "worth": round(worth, 1),
        "mpps_worth": round(mpps_worth, 1),
        "n_imp": n_imp,
        "disqualified": bool(dq_ids),
        "dq_ids": dq_ids,
    }


def _pdf_payload_for_pros_cons(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Build a COMPLETE Pros & Cons report in app navigation order.

    Section order mirrors the wizard flow:
      Decision Overview → Pros & Cons → Factors & Priorities →
      Assessment Detail (per option) → Options Ranking (Satisfaction %) +
      Standard Recommendation → MPPS Analysis + Final Recommendation.

    Handles both schemas:
      • Rich (8-step): factors + options + assessments (+ MPPS improvement_pct).
      • Flat (legacy): standalone `pros`/`cons` lists with importance.
    """
    sections = []

    factors = raw.get("factors") or []
    options = raw.get("options") or []
    assessments = raw.get("assessments") or {}
    config = raw.get("config") or {}
    flat_pros = raw.get("pros") or []
    flat_cons = raw.get("cons") or []

    is_rich = bool(factors) and bool(options)

    # ── 1. Decision Overview (initial intake info) ──────────────────────────
    sections.append(_decision_overview_section(raw))

    # ── Legacy flat schema (no factor framework) ────────────────────────────
    if not is_rich:
        if flat_pros:
            rows = [["Pro", "Description", "Importance"]]
            for p in flat_pros:
                rows.append([
                    _t(p.get("text") or p.get("name")),
                    _t(p.get("description")),
                    _num(p.get("importance")),
                ])
            sections.append({"heading": "Pros", "table": rows, "col_ratios": [2.0, 3.4, 1.2]})
        if flat_cons:
            rows = [["Con", "Description", "Importance"]]
            for c in flat_cons:
                rows.append([
                    _t(c.get("text") or c.get("name")),
                    _t(c.get("description")),
                    _num(c.get("importance")),
                ])
            sections.append({"heading": "Cons", "table": rows, "col_ratios": [2.0, 3.4, 1.2]})
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

    # ========================= RICH 8-STEP SCHEMA ==========================
    sfactors = _scoring_factors(factors)
    total_std = _total_std_rating(sfactors)
    mandatory_threshold = config.get("mandatory_threshold_pct")
    fsorted = sorted(factors, key=lambda f: (f.get("priority_rank") or 9999))

    metrics = {
        o.get("id"): _option_metrics(
            sfactors, assessments.get(o.get("id")) or {}, total_std, mandatory_threshold
        )
        for o in options
    }

    def _ranked(metric_key):
        """Options by metric desc; disqualified pushed to the bottom (unranked)."""
        qualified = [o for o in options if not metrics[o.get("id")]["disqualified"]]
        disq = [o for o in options if metrics[o.get("id")]["disqualified"]]
        qualified.sort(key=lambda o: metrics[o.get("id")][metric_key], reverse=True)
        return qualified, disq

    # ── 2. Pros & Cons (per option, mirrors Step-2 in the app) ──────────────
    pc_added = False
    for o in options:
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
        pc_added = True
    if not pc_added and (flat_pros or flat_cons):
        max_rows = max(len(flat_pros), len(flat_cons), 1)
        rows = [["Pros", "Cons"]]
        for i in range(max_rows):
            p = flat_pros[i] if i < len(flat_pros) else {}
            c = flat_cons[i] if i < len(flat_cons) else {}
            rows.append([
                _t(p.get("text") or p.get("name")),
                _t(c.get("text") or c.get("name")),
            ])
        sections.append({"heading": "Pros & Cons", "table": rows, "col_ratios": [1, 1]})

    # ── 3. Factors & Priorities ─────────────────────────────────────────────
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

    # ── 4. Assessment Detail per option (Satisfaction % = assessment %) ──────
    q_detail, dq_detail = _ranked("worth")
    for o in (q_detail + dq_detail):
        cell_map = assessments.get(o.get("id")) or {}
        if not cell_map:
            continue
        drows = [["Factor", "Actual Value", "Satisfaction %"]]
        for f in fsorted:
            cell = cell_map.get(f.get("id"))
            if not cell:
                continue
            drows.append([
                _t(f.get("name")),
                _t(cell.get("actual_value")),
                f"{_num(cell.get('assessment_pct'))}%",
            ])
        if len(drows) > 1:
            sections.append({
                "heading": f"Assessment Detail — {o.get('name') or 'Option'}",
                "table": drows,
                "col_ratios": [3.4, 2.0, 1.6],
            })

    # ── 5. Options Ranking — Satisfaction % + Standard Recommendation ───────
    qualified, disq = _ranked("worth")
    orows = [["Rank", "Option", "Joint Score", "Satisfaction %", "Status"]]
    for i, o in enumerate(qualified, 1):
        m = metrics[o.get("id")]
        orows.append([
            _num(i), _t(o.get("name")), _num(m["joint_score"]),
            f"{_num(m['worth'])}%", "Qualified",
        ])
    for o in disq:
        m = metrics[o.get("id")]
        orows.append([
            "—", _t(o.get("name")), _num(m["joint_score"]),
            f"{_num(m['worth'])}%", "Disqualified",
        ])
    sections.append({
        "heading": "Options Ranking — Satisfaction %",
        "table": orows,
        "col_ratios": [0.8, 2.6, 1.4, 1.6, 1.4],
    })

    if qualified:
        top = qualified[0]
        m = metrics[top.get("id")]
        sections.append({
            "heading": "Standard Recommendation",
            "paragraph": (
                f"Based on your prioritised factors, "
                f"<b>{_esc(top.get('name') or 'the top option')}</b> ranks #1 "
                f"with a joint score of <b>{_esc(_num(m['joint_score']))}</b> "
                f"and a satisfaction of <b>{_esc(_num(m['worth']))}%</b>."
            ),
        })

    # ── 6. MPPS Analysis (Case-2) + Final Recommendation ────────────────────
    any_mpps = any(metrics[o.get("id")]["n_imp"] > 0 for o in options)
    if any_mpps:
        mt_val = config.get("mpps_max_time_value")
        mt_unit = config.get("mpps_max_time_unit") or "Months"
        intro = (
            "Maximum Possible Practical Solution — projected satisfaction if the "
            "stated improvements are achieved"
        )
        if mt_val:
            intro += f" within <b>{_esc(_num(mt_val))} {_esc(mt_unit)}</b>"
        intro += "."
        sections.append({"heading": "MPPS Analysis (Case-2)", "paragraph": intro})

        for o in (qualified + disq):
            cell_map = assessments.get(o.get("id")) or {}
            irows = [["Factor", "Current %", "Improvement", "Projected %"]]
            for f in fsorted:
                cell = cell_map.get(f.get("id")) or {}
                imp = float(cell.get("improvement_pct") or 0)
                if not imp:
                    continue
                cur = float(cell.get("assessment_pct") or 0)
                proj = max(0.0, min(100.0, cur + imp))
                irows.append([
                    _t(f.get("name")),
                    f"{_num(cur)}%",
                    f"{'+' if imp > 0 else ''}{_num(imp)} pp",
                    f"{_num(proj)}%",
                ])
            if len(irows) > 1:
                sections.append({
                    "heading": f"MPPS Improvements — {o.get('name') or 'Option'}",
                    "table": irows,
                    "col_ratios": [3.4, 1.5, 1.7, 1.5],
                })

        q_mpps, dq_mpps = _ranked("mpps_worth")
        mrows = [["Rank", "Option", "Satisfaction %", "MPPS Satisfaction %"]]
        for i, o in enumerate(q_mpps, 1):
            m = metrics[o.get("id")]
            mrows.append([
                _num(i), _t(o.get("name")),
                f"{_num(m['worth'])}%", f"{_num(m['mpps_worth'])}%",
            ])
        for o in dq_mpps:
            m = metrics[o.get("id")]
            mrows.append([
                "—", _t(o.get("name")),
                f"{_num(m['worth'])}%", f"{_num(m['mpps_worth'])}%",
            ])
        sections.append({
            "heading": "Revised Ranking after MPPS",
            "table": mrows,
            "col_ratios": [0.8, 3.0, 1.8, 2.0],
        })

        if q_mpps:
            top = q_mpps[0]
            m = metrics[top.get("id")]
            sections.append({
                "heading": "Final Recommendation",
                "paragraph": (
                    f"After MPPS improvements, "
                    f"<b>{_esc(top.get('name') or 'the top option')}</b> ranks #1 "
                    f"with a projected satisfaction of "
                    f"<b>{_esc(_num(m['mpps_worth']))}%</b> "
                    f"(up from {_esc(_num(m['worth']))}%)."
                ),
            })

    opt_name_by_id = {o.get("id"): o.get("name") for o in options}
    sections.extend(_final_decision_sections(
        raw, opt_name_by_id, raw.get("_action_items") or []))

    return {
        "title": raw.get("title", "Untitled Pros & Cons"),
        "context": raw.get("context"),
        "module_label": "Pros & Cons",
        "sections": sections,
    }


def _pdf_payload_for_swot(raw: Dict[str, Any]) -> Dict[str, Any]:
    sections = [_decision_overview_section(raw)]
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


def _sf_text(it) -> str:
    if isinstance(it, str):
        return it
    if isinstance(it, dict):
        return (it.get("text") or it.get("label") or it.get("title")
                or it.get("name") or it.get("description") or "—")
    return str(it)


def _sf_rows(items, header):
    rows = [[header]]
    for it in items:
        rows.append([_t(_sf_text(it))])
    return rows


def _sf_build_index(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "concern": {c.get("id"): c for c in (raw.get("concerns") or [])},
        "rca": {r.get("id"): r for r in (raw.get("root_causes") or [])},
        "sol": {s.get("id"): s for s in (raw.get("solutions") or [])},
        "risk": {k.get("id"): k for k in (raw.get("risks") or [])},
        "mit": {m.get("id"): m for m in (raw.get("mitigations") or [])},
        "con": {c.get("id"): c for c in (raw.get("contingencies") or [])},
    }


def _sf_chain_label(by: Dict[str, Any], source_type: str, source_id: str) -> str:
    """Full hierarchy path for an action item — every level, no truncation:
    'Concern › Root Cause › Solution [› ⚠ Risk]'. Wrapping is handled by the
    PDF table cell (Paragraph), so long names stay fully visible."""
    parts, sol, risk = [], None, None
    if source_type == "solution":
        sol = by["sol"].get(source_id)
    elif source_type in ("mitigation", "contingency"):
        node = by["mit" if source_type == "mitigation" else "con"].get(source_id)
        risk = by["risk"].get(node.get("risk_id")) if node else None
        sol = by["sol"].get(risk.get("sol_id")) if risk else None
    if sol:
        rca = by["rca"].get(sol.get("rca_id"))
        concern = by["concern"].get(rca.get("concern_id")) if rca else None
        if concern:
            parts.append(("★ " if concern.get("is_primary") else "") + str(concern.get("text") or ""))
        if rca:
            parts.append(str(rca.get("text") or ""))
        parts.append(str(sol.get("text") or ""))
    if risk:
        parts.append("⚠ " + str(risk.get("name") or ""))
    return " › ".join([p for p in parts if p])


def _sf_hierarchy_rows(raw: Dict[str, Any]):
    """Nested Concern ★ → Root Cause → Solution → Risk → Mitigation/Contingency
    as an indented 2-column table (nbsp indentation renders under reportlab)."""
    NB = "\u00a0"
    concerns = raw.get("concerns") or []
    if not (concerns or raw.get("solutions")):
        return None
    rcas_by_c: Dict[Any, list] = {}
    for r in (raw.get("root_causes") or []):
        rcas_by_c.setdefault(r.get("concern_id"), []).append(r)
    sols_by_rca: Dict[Any, list] = {}
    for s in (raw.get("solutions") or []):
        sols_by_rca.setdefault(s.get("rca_id"), []).append(s)
    risks_by_sol: Dict[Any, list] = {}
    for k in (raw.get("risks") or []):
        risks_by_sol.setdefault(k.get("sol_id"), []).append(k)
    mits_by_risk: Dict[Any, list] = {}
    for m in (raw.get("mitigations") or []):
        mits_by_risk.setdefault(m.get("risk_id"), []).append(m)
    cons_by_risk: Dict[Any, list] = {}
    for c in (raw.get("contingencies") or []):
        cons_by_risk.setdefault(c.get("risk_id"), []).append(c)

    rows = [["Level", "Detail"]]
    seen_sol = set()

    def add_solution(s):
        seen_sol.add(s.get("id"))
        rows.append([NB * 4 + "↳ Solution", _t(s.get("text"))])
        for k in risks_by_sol.get(s.get("id"), []):
            idx = k.get("risk_index_pct")
            meta = f" · Impact {_num(k.get('impact_pct'))}% · Prob {_num(k.get('probability_pct'))}%"
            if idx not in (None, ""):
                meta += f" · Index {_num(idx)}%"
            rows.append([NB * 6 + "• Risk", _t(k.get("name")) + meta])
            for m in mits_by_risk.get(k.get("id"), []):
                rows.append([NB * 8 + "– Mitigation", _t(m.get("text"))])
            for c in cons_by_risk.get(k.get("id"), []):
                rows.append([NB * 8 + "– Contingency", _t(c.get("text"))])

    ordered = sorted(concerns, key=lambda c: (0 if c.get("is_primary") else 1, c.get("order", 0)))
    for c in ordered:
        star = "★ " if c.get("is_primary") else ""
        rows.append([star + "Concern", _t(c.get("text"))])
        for r in rcas_by_c.get(c.get("id"), []):
            rows.append([NB * 2 + "↳ Root Cause", _t(r.get("text"))])
            for s in sols_by_rca.get(r.get("id"), []):
                add_solution(s)
    orphans = [s for s in (raw.get("solutions") or []) if s.get("id") not in seen_sol]
    if orphans:
        rows.append(["Ungrouped", "Solutions not linked to a concern/root-cause"])
        for s in orphans:
            add_solution(s)
    return rows if len(rows) > 1 else None


def _pdf_payload_for_solution_finder(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Content report for the Solution Finder worksheet (no scoring/% — it is a
    goal → concerns → solutions → risks → action-plan worksheet)."""
    sections = [_decision_overview_section(raw)]

    if raw.get("smart_goal"):
        sections.append({"heading": "SMART Goal",
                         "paragraph": _esc(str(raw["smart_goal"])[:2000])})
    if raw.get("milestones"):
        sections.append({"heading": "Milestones",
                         "table": _sf_rows(raw["milestones"], "Milestone")})

    _hier = _sf_hierarchy_rows(raw)
    if _hier:
        sections.append({
            "heading": "Risk Management Map (hierarchy)",
            "table": _hier,
            "col_ratios": [2.4, 4.6],
        })

    if raw.get("concerns"):
        sections.append({"heading": "Concerns", "table": _sf_rows(raw["concerns"], "Concern")})
    elif raw.get("q1_all_concerns") or raw.get("q2_primary_concerns"):
        lines = []
        if raw.get("q2_primary_concerns"):
            lines.append(f"<b>Primary:</b> {_esc(str(raw['q2_primary_concerns']))}")
        if raw.get("q1_all_concerns"):
            lines.append(f"<b>All:</b> {_esc(str(raw['q1_all_concerns']))}")
        sections.append({"heading": "Concerns", "paragraph": "<br/>".join(lines)})

    if raw.get("root_causes"):
        sections.append({"heading": "Root Causes",
                         "table": _sf_rows(raw["root_causes"], "Root Cause")})

    cr = []
    if raw.get("q3_capabilities"):
        cr.append(f"<b>Capabilities:</b> {_esc(str(raw['q3_capabilities']))}")
    if raw.get("q3_resources"):
        cr.append(f"<b>Resources:</b> {_esc(str(raw['q3_resources']))}")
    if cr:
        sections.append({"heading": "Capabilities & Resources", "paragraph": "<br/>".join(cr)})

    if raw.get("solutions"):
        sections.append({"heading": "Solutions", "table": _sf_rows(raw["solutions"], "Solution")})
    elif raw.get("q3_solutions"):
        sections.append({"heading": "Solutions", "paragraph": _esc(str(raw["q3_solutions"]))})

    eh = []
    if raw.get("external_help_aspect"):
        eh.append(f"<b>Aspect:</b> {_esc(str(raw['external_help_aspect']))}")
    if raw.get("external_help_level"):
        eh.append(f"<b>Level:</b> {_esc(str(raw['external_help_level']))}")
    if raw.get("external_help_from"):
        eh.append(f"<b>From:</b> {_esc(str(raw['external_help_from']))}")
    if eh:
        sections.append({"heading": "External Help", "paragraph": "<br/>".join(eh)})

    if raw.get("risks"):
        sections.append({"heading": "Risks", "table": _sf_rows(raw["risks"], "Risk")})
    elif raw.get("q4_negative_consequences"):
        sections.append({"heading": "Risks", "paragraph": _esc(str(raw["q4_negative_consequences"]))})
    if raw.get("mitigations"):
        sections.append({"heading": "Mitigations", "table": _sf_rows(raw["mitigations"], "Mitigation")})
    elif raw.get("q4_mitigation_plans"):
        sections.append({"heading": "Mitigations", "paragraph": _esc(str(raw["q4_mitigation_plans"]))})
    if raw.get("contingencies"):
        sections.append({"heading": "Contingencies", "table": _sf_rows(raw["contingencies"], "Contingency")})
    elif raw.get("q4_contingency_plans"):
        sections.append({"heading": "Contingencies", "paragraph": _esc(str(raw["q4_contingency_plans"]))})

    ap = raw.get("action_plan_items") or raw.get("action_items") or []
    if ap:
        _idx = _sf_build_index(raw)

        def _ap_row(n, it):
            if isinstance(it, dict):
                ctx = _sf_chain_label(_idx, it.get("source_type") or "", it.get("source_id") or "")
                return [
                    _num(n),
                    _t(it.get("text") or it.get("what") or it.get("title")),
                    _t(ctx) if ctx else "—",
                    _t(it.get("who")),
                    _ddmmyyyy(it.get("by_when") or it.get("byWhen") or it.get("deadline")),
                    _fmt_status(it.get("status")),
                ]
            return [_num(n), _t(str(it)), "—", "—", "—", "—"]

        # Start the Action Plan on a fresh page so it can be printed on its own.
        sections.append({
            "heading": "Action Plan",
            "page_break": True,
            "paragraph": _esc(f"{len(ap)} action item(s), grouped by origin so Solutions, "
                              f"Risk Mitigations and Risk Contingencies are clearly separated."),
        })

        header = ["ID", "Action",
                  "Under (Concern › Root Cause › Solution › Risk)",
                  "Who", "By When", "Status"]
        col_ratios = [0.4, 2.2, 3.0, 1.0, 1.1, 0.9]
        groups = [
            ("solution",    "I",   "Solution Actions",         "Mandatory"),
            ("mitigation",  "II",  "Risk Mitigation Actions",  "Most Recommended"),
            ("contingency", "III", "Risk Contingency Actions", "Recommended"),
        ]
        known = {g[0] for g in groups}
        counter = 0
        for st, roman, label, suffix in groups:
            items = [it for it in ap if isinstance(it, dict) and (it.get("source_type") or "") == st]
            if not items:
                continue
            rows = [header]
            for it in items:
                counter += 1
                rows.append(_ap_row(counter, it))
            sections.append({"heading": f"{roman}. {label} ({len(items)}) - {suffix}",
                             "table": rows, "col_ratios": col_ratios})
        # Anything without a recognised origin (or plain-string items) → catch-all.
        leftover = [it for it in ap
                    if not (isinstance(it, dict) and (it.get("source_type") or "") in known)]
        if leftover:
            rows = [header]
            for it in leftover:
                counter += 1
                rows.append(_ap_row(counter, it))
            sections.append({"heading": f"IV. Other Actions ({len(leftover)})",
                             "table": rows, "col_ratios": col_ratios})

    goal = (raw.get("smart_goal") or "").strip()
    title = goal if goal else "Solution Finder"
    return {
        "title": title,
        "context": None,
        "module_label": "Solution Finder",
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
        "solution_finder": _pdf_payload_for_solution_finder,
    }[module.lower()]
    payload = builder(raw)
    tzname = await _user_timezone(user["user_id"])
    payload["generated_at"] = _format_local(datetime.now(timezone.utc), tzname)

    from routes.app_appearance import get_app_logo
    logo = await get_app_logo()
    pdf_bytes = _build_pdf(payload, logo_data_url=logo)
    filename = f"dezider_{module}_{decision_id[:8]}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Report-Access-Via": access.get("access_via", ""),
        },
    )
