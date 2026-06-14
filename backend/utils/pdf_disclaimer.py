"""
Shared legal disclaimer for all server-side PDF exports.

Single source of truth — keeps the wording identical across:
  • decision_reports._build_pdf  (My Dezider / Pros & Cons / SWOT / PNA / etc.)
  • decisions.mpps.download_mpps_action_plan_pdf
  • utils.solution_matrix_pdf.render_matrix_pdf
  • emotional_gatekeeper.outlet_report_routes  (reuses _build_pdf)

To update the legal copy site-wide, edit `DISCLAIMER_TEXT` below.

NOTE: The same wording is also surfaced inside the on-screen Breakthrough
Report card (`frontend/app/tools/eg-session.tsx`) so paper and pixel match.
"""
from __future__ import annotations

from typing import List

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Flowable


DISCLAIMER_TEXT = (
    "<b>Disclaimer:</b> This AI-generated report contains suggestions only and "
    "is NOT professional advice. JELCOS AI is not responsible for any actions "
    "taken based on it. Please consult relevant subject-matter experts "
    "(e.g. licensed therapists, financial advisors, legal counsel) before "
    "making decisions with material consequences."
)


def _disclaimer_style() -> ParagraphStyle:
    """Tight italic 9pt grey paragraph, indented with a left rule via padding."""
    base = getSampleStyleSheet()["BodyText"]
    return ParagraphStyle(
        "legalDisclaimer",
        parent=base,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#6B7280"),
        fontName="Helvetica-Oblique",
        borderColor=colors.HexColor("#E5E7EB"),
        borderWidth=0.6,
        borderPadding=6,
        leftIndent=0,
        rightIndent=0,
        spaceBefore=4,
        spaceAfter=4,
    )


def legal_disclaimer_flowables(top_gap_mm: float = 6.0) -> List[Flowable]:
    """Return the flowables to append to any report `story` *before* the
    final brand/copyright lines.

    Use:
        story.extend(legal_disclaimer_flowables())
        story.append(Paragraph("© JELCOS AI", brand_footer))
    """
    return [
        Spacer(1, top_gap_mm * mm),
        Paragraph(DISCLAIMER_TEXT, _disclaimer_style()),
    ]
