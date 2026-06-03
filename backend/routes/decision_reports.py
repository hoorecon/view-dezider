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

    sections.append(_decision_overview_section(raw))

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
    return local.strftime(f"%d %b %Y, %H:%M {abbr}").strip()


def _decision_overview_section(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Shared 'Decision Overview' block — surfaces the initial intake info
    (For / Life Area / Type / Sub-area / Scenario). Reused across all modules."""
    type_label = _decision_type_label(raw.get("decision_type")) or "Not specified"
    area_label = _life_area_label(raw.get("life_area")) or "Not specified"
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
    tzname = await _user_timezone(user["user_id"])
    payload["generated_at"] = _format_local(datetime.now(timezone.utc), tzname)

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
