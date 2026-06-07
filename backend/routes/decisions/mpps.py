"""MPPS action-plan download routes (CSV + PDF)."""

import io
import csv
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from core.database import db
from core.auth import get_current_user

router = APIRouter(tags=["Decisions"])


@router.get("/decisions/{decision_id}/mpps-action-plan")
async def download_mpps_action_plan(decision_id: str, user: dict = Depends(get_current_user)):
    """Download MPPS action plan as CSV"""
    decision = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    improvements = decision.get("mpps_improvements", [])
    factors = decision.get("factors", [])
    options = decision.get("options", [])
    mpps_option_id = decision.get("mpps_option_id")
    mpps_timeframe = decision.get("mpps_timeframe", "Not specified")
    target_option = next((o for o in options if o.get("id") == mpps_option_id), options[0] if options else None)
    option_name = target_option.get("name", "Unknown") if target_option else "Unknown"
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["MPPS Action Plan"])
    writer.writerow(["Decision", decision.get("title", "")])
    writer.writerow(["Context", decision.get("context", "")])
    writer.writerow(["Option", option_name])
    writer.writerow(["Timeframe", mpps_timeframe])
    writer.writerow(["Projected Worth", f"{decision.get('mpps_projected_worth', 0)}%"])
    writer.writerow([])
    writer.writerow(["Factor", "Category", "Rating", "Current %", "Projected %", "Delta %",
                     "Target Value", "Target Unit", "Improvement Plan", "TEPFI Elements", "Solution Layer",
                     "Assignee Name", "Assignee Email", "Assignee Mobile", "Task", "Deadline"])
    for imp in improvements:
        factor = next((f for f in factors if f.get("id") == imp.get("factor_id")), {})
        tepfi = ", ".join(imp.get("tepfi_elements", []))
        layer = imp.get("tepfi_layer", "")
        action_items = imp.get("action_items", [])
        base_row = [
            factor.get("name", ""), factor.get("category", ""), factor.get("rating", ""),
            imp.get("original_percentage", ""), imp.get("projected_percentage", ""), imp.get("delta_percentage", ""),
            imp.get("expected_value", ""), imp.get("expected_unit", ""), imp.get("improvement_plan", ""), tepfi, layer,
        ]
        if action_items:
            for ai in action_items:
                writer.writerow(base_row + [ai.get("assignee_name", ""), ai.get("assignee_email", ""),
                                            ai.get("assignee_mobile", ""), ai.get("task", ""), ai.get("deadline", "")])
        else:
            writer.writerow(base_row + ["", "", "", "", ""])
    csv_content = output.getvalue()
    return StreamingResponse(io.BytesIO(csv_content.encode()), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="MPPS_Action_Plan_{decision_id[:8]}.csv"'})


@router.get("/decisions/{decision_id}/mpps-action-plan-pdf")
async def download_mpps_action_plan_pdf(decision_id: str, user: dict = Depends(get_current_user)):
    """Download MPPS action plan as PDF"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.units import mm
    decision = await db.decisions.find_one({"id": decision_id, "user_id": user["user_id"]})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    improvements = decision.get("mpps_improvements", [])
    factors = decision.get("factors", [])
    options = decision.get("options", [])
    mpps_option_id = decision.get("mpps_option_id")
    mpps_timeframe = decision.get("mpps_timeframe", "Not specified")
    target_option = next((o for o in options if o.get("id") == mpps_option_id), options[0] if options else None)
    option_name = target_option.get("name", "Unknown") if target_option else "Unknown"
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm, leftMargin=12*mm, rightMargin=12*mm)
    styles = getSampleStyleSheet()
    story = []
    title_style = ParagraphStyle('Title2', parent=styles['Title'], fontSize=16, spaceAfter=6)
    story.append(Paragraph("MPPS Action Plan", title_style))
    story.append(Spacer(1, 4*mm))
    summary_data = [
        ["Decision", decision.get("title", "")], ["Context", decision.get("context", "")],
        ["Option", option_name], ["Timeframe", mpps_timeframe],
        ["Projected Worth", f"{decision.get('mpps_projected_worth', 0)}%"],
    ]
    summary_table = Table(summary_data, colWidths=[35*mm, 140*mm])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 6*mm))
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=7, leading=9)
    header_style = ParagraphStyle('Header', parent=styles['Normal'], fontSize=7, leading=9, fontName='Helvetica-Bold', textColor=colors.white)
    for imp in improvements:
        factor = next((f for f in factors if f.get("id") == imp.get("factor_id")), {})
        tepfi = ", ".join(imp.get("tepfi_elements", []))
        layer = imp.get("tepfi_layer") or ""
        action_items = imp.get("action_items", [])
        factor_title = ParagraphStyle('FTitle', parent=styles['Heading3'], fontSize=11, spaceAfter=2, spaceBefore=4)
        orig = imp.get("original_percentage", "--")
        proj = imp.get("projected_percentage", "--")
        delta = imp.get("delta_percentage", "--")
        story.append(Paragraph(f"{factor.get('name', '')} — {factor.get('category', '')} (Rating: {factor.get('rating', '')})", factor_title))
        info_data = [
            [Paragraph("<b>Current %</b>", cell_style), Paragraph(f"{orig}%", cell_style),
             Paragraph("<b>Projected %</b>", cell_style), Paragraph(f"{proj}%", cell_style),
             Paragraph("<b>Delta</b>", cell_style), Paragraph(f"+{delta}%" if delta and str(delta) != '--' else str(delta), cell_style)],
            [Paragraph("<b>Target Value</b>", cell_style), Paragraph(str(imp.get("expected_value", "")), cell_style),
             Paragraph("<b>Unit</b>", cell_style), Paragraph(str(imp.get("expected_unit", "")), cell_style),
             Paragraph("<b>TEPFI</b>", cell_style), Paragraph(tepfi, cell_style)],
            [Paragraph("<b>Layer</b>", cell_style), Paragraph(layer, cell_style),
             Paragraph("<b>Plan</b>", cell_style), Paragraph(str(imp.get("improvement_plan", "")), cell_style), "", ""],
        ]
        info_table = Table(info_data, colWidths=[22*mm, 28*mm, 22*mm, 28*mm, 22*mm, 53*mm])
        info_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('FONTSIZE', (0, 0), (-1, -1), 7), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3), ('TOPPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(info_table)
        if action_items:
            story.append(Spacer(1, 2*mm))
            ai_header = [Paragraph("Who", header_style), Paragraph("Email", header_style),
                         Paragraph("Mobile", header_style), Paragraph("Task", header_style), Paragraph("By When", header_style)]
            ai_data = [ai_header]
            for ai in action_items:
                ai_data.append([
                    Paragraph(ai.get("assignee_name", ""), cell_style), Paragraph(ai.get("assignee_email", ""), cell_style),
                    Paragraph(ai.get("assignee_mobile", ""), cell_style), Paragraph(ai.get("task", ""), cell_style),
                    Paragraph(ai.get("deadline", ""), cell_style),
                ])
            ai_table = Table(ai_data, colWidths=[30*mm, 38*mm, 28*mm, 50*mm, 29*mm])
            ai_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6366F1')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey), ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('BOTTOMPADDING', (0, 0), (-1, -1), 3), ('TOPPADDING', (0, 0), (-1, -1), 3),
            ]))
            story.append(ai_table)
        story.append(Spacer(1, 4*mm))
    doc.build(story)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="MPPS_Action_Plan_{decision_id[:8]}.pdf"'})
