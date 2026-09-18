import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import os

wb = openpyxl.Workbook()

# Colors
NAVY = "1F497D"
LIGHT_BLUE = "DCE6F1"
ZEBRA_FILL = "F2F5F9"
WHITE = "FFFFFF"
DARK_GRAY = "333333"

GREEN_FILL = "E2EFDA"
GREEN_FONT = "375623"
RED_FILL = "FCE4D6"
RED_FONT = "C65911"
YELLOW_FILL = "FFF2CC"
YELLOW_FONT = "833C0C"

font_title = Font(name="Calibri", size=15, bold=True, color=WHITE)
font_subtitle = Font(name="Calibri", size=11, italic=True, color=WHITE)
font_header = Font(name="Calibri", size=11, bold=True, color=WHITE)
font_section = Font(name="Calibri", size=12, bold=True, color=NAVY)
font_body = Font(name="Calibri", size=11, color=DARK_GRAY)
font_bold = Font(name="Calibri", size=11, bold=True, color=DARK_GRAY)

fill_title = PatternFill(start_color=NAVY, end_color=NAVY, fill_type="solid")
fill_header = PatternFill(start_color=NAVY, end_color=NAVY, fill_type="solid")
fill_zebra = PatternFill(start_color=ZEBRA_FILL, end_color=ZEBRA_FILL, fill_type="solid")

thin_border = Border(
    left=Side(style='thin', color='D9D9D9'),
    right=Side(style='thin', color='D9D9D9'),
    top=Side(style='thin', color='D9D9D9'),
    bottom=Side(style='thin', color='D9D9D9')
)

header_border = Border(
    left=Side(style='medium', color=NAVY),
    right=Side(style='medium', color=NAVY),
    top=Side(style='medium', color=NAVY),
    bottom=Side(style='medium', color=NAVY)
)

# ----------------------------------------------------------------------
# SHEET 1: Executive Overview
# ----------------------------------------------------------------------
ws1 = wb.active
ws1.title = "Executive Overview"
ws1.views.sheetView[0].showGridLines = True

ws1.merge_cells("A1:G1")
ws1["A1"] = "VIEW-DEZIDER: SUBSCRIPTION PLAN GATING DOCUMENTATION"
ws1["A1"].font = font_title
ws1["A1"].fill = fill_title
ws1["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
ws1.row_dimensions[1].height = 35

ws1.merge_cells("A2:G2")
ws1["A2"] = "Summary of Plan Gating Rules, Entitlements, Tier Hierarchy, and Feature Access Controls"
ws1["A2"].font = font_subtitle
ws1["A2"].fill = fill_title
ws1["A2"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
ws1.row_dimensions[2].height = 22

ws1["A4"] = "1. Subscription Plan Tiers Overview"
ws1["A4"].font = font_section

headers_1 = ["Tier ID", "Plan Name", "Target Audience", "Access Scope", "Core DIY Limits", "Advanced Modules Access", "AI Features Access"]
for col_idx, h in enumerate(headers_1, start=1):
    cell = ws1.cell(row=5, column=col_idx, value=h)
    cell.font = font_header
    cell.fill = fill_header
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = header_border
ws1.row_dimensions[5].height = 25

plans_data = [
    ("free", "Free Tier", "Guest / Free Registered", "Basic Free Use", "Capped (Default 2 per module)", "Blocked (403/402)", "Blocked (402 Upgrade Required)"),
    ("on_demand_l1", "On-Demand L1", "Single Decision Buyer", "1 DIY Decision", "1 shared across DIY tools", "Blocked (403)", "Blocked (402 Upgrade Required)"),
    ("on_demand_l2", "On-Demand L2", "Bundle Buyer (5 Units)", "5 Shared Units", "5 shared bundle quota", "Group Decision (Within 5 bundle)", "Blocked (402 Upgrade Required)"),
    ("on_demand_l3", "On-Demand L3", "Expert Booking Buyer", "1 Expert Session", "Standard Free Limits", "1 Book Expert Included", "Blocked (402 Upgrade Required)"),
    ("on_demand_l4", "On-Demand L4", "Expert + Review Buyer", "1 Expert + 1 Review", "Standard Free Limits", "1 Expert + 1 Review Included", "Blocked (402 Upgrade Required)"),
    ("basic", "Basic / Starter Plan", "Individual Subscribers", "Full Core + Standard Tools", "Unlimited", "CTT, Values, Lifestyle, Journal, Manifestation, TEPFI, AIM", "Allowed (Wallet / Plan Access)"),
    ("pro", "Professional Plan", "Power Users & Professionals", "All Standard + Advanced Tools", "Unlimited", "ATEX, PRR Steps 7-8, Conflict Breaker, Group Decisions", "Allowed (Full Access)"),
    ("premium", "Premium / Enterprise", "Startups & Teams", "All-Inclusive Access", "Unlimited", "All Modules + Orgs & Team Features", "Allowed (Priority Access)"),
    ("admin", "Admin / Super Admin", "Internal Operations & Staff", "System Exemption", "Unlimited", "Exempt (Full Access)", "Exempt (Full Access)"),
]

for row_idx, row_data in enumerate(plans_data, start=6):
    ws1.row_dimensions[row_idx].height = 22
    for col_idx, val in enumerate(row_data, start=1):
        cell = ws1.cell(row=row_idx, column=col_idx, value=val)
        cell.font = font_body
        cell.border = thin_border
        if col_idx == 1:
            cell.font = font_bold
            cell.alignment = Alignment(horizontal="center", vertical="center")
        elif col_idx in [2, 3]:
            cell.alignment = Alignment(horizontal="left", vertical="center")
        else:
            cell.alignment = Alignment(horizontal="center", vertical="center")
        if row_idx % 2 == 1:
            cell.fill = fill_zebra

# ----------------------------------------------------------------------
# SHEET 2: Plan Gating Matrix
# ----------------------------------------------------------------------
ws2 = wb.create_sheet(title="Plan Gating Matrix")
ws2.views.sheetView[0].showGridLines = True

ws2.merge_cells("A1:H1")
ws2["A1"] = "FEATURE-BY-FEATURE SUBSCRIPTION PLAN GATING MATRIX"
ws2["A1"].font = font_title
ws2["A1"].fill = fill_title
ws2["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
ws2.row_dimensions[1].height = 35

ws2.merge_cells("A2:H2")
ws2["A2"] = "Detailed Access Rules, HTTP Status Codes, Quota Controls, and Exemption Rules"
ws2["A2"].font = font_subtitle
ws2["A2"].fill = fill_title
ws2["A2"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
ws2.row_dimensions[2].height = 22

headers_2 = [
    "Module / Feature Name",
    "Backend Verification Route",
    "Free Tier",
    "On-Demand (L1-L4)",
    "Basic Plan",
    "Pro Plan",
    "Premium / Enterprise",
    "Admin / Testers",
]

for col_idx, h in enumerate(headers_2, start=1):
    cell = ws2.cell(row=4, column=col_idx, value=h)
    cell.font = font_header
    cell.fill = fill_header
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = header_border
ws2.row_dimensions[4].height = 25

matrix_data = [
    ("Core DIY Decisions (My Dezider, Pros & Cons, Solution Finder)", "routes/module_limits.py", "Capped (Default 2)", "L1: 1 DIY | L2: 5 Bundle", "Unlimited", "Unlimited", "Unlimited", "Exempt"),
    ("CTT (Task Tracker)", "routes/ctt_gem.py", "Blocked (403)", "Blocked (403)", "Allowed", "Allowed", "Allowed", "Exempt"),
    ("ATEX (Effort Estimation)", "routes/atex.py", "Blocked (403)", "Blocked (403)", "Blocked (403)", "Allowed", "Allowed", "Exempt"),
    ("AIM (Action Item Manager)", "routes/action_items.py", "Blocked (403)", "Blocked (403)", "Allowed", "Allowed", "Allowed", "Exempt"),
    ("Values Tracker", "routes/values_routes.py", "Blocked (403)", "Blocked (403)", "Allowed", "Allowed", "Allowed", "Exempt"),
    ("Lifestyle Routine", "routes/lifestyle.py", "Blocked (403)", "Blocked (403)", "Allowed", "Allowed", "Allowed", "Exempt"),
    ("Journaling Tool", "routes/journal.py", "Blocked (403)", "Blocked (403)", "Allowed", "Allowed", "Allowed", "Exempt"),
    ("Manifestation Tool", "routes/manifestation.py", "Blocked (403)", "Blocked (403)", "Allowed", "Allowed", "Allowed", "Exempt"),
    ("TEPFI Tool", "routes/ctt_gem.py", "Blocked (403)", "Blocked (403)", "Allowed", "Allowed", "Allowed", "Exempt"),
    ("Consciousness Diary", "routes/consciousness_diary.py", "Blocked (403)", "Blocked (403)", "Allowed", "Allowed", "Allowed", "Exempt"),
    ("Group Decisions / Collaboration", "routes/module_limits.py", "Blocked (402)", "L1: Blocked | L2: 5 Bundle", "Allowed", "Allowed", "Allowed", "Exempt"),
    ("Conflict Breaker", "routes/module_limits.py", "Blocked (402)", "Blocked (402)", "Blocked (402)", "Allowed", "Allowed", "Exempt"),
    ("AI Features (Fetch Factors, Best Options, AI Assess ALL)", "routes/module_limits.py", "Blocked (402)", "Blocked (402)", "Allowed", "Allowed", "Allowed", "Exempt"),
    ("Decision Templates / MPPS / XLS Export", "routes/decider_store.py", "Blocked (403)", "Blocked (403)", "Allowed", "Allowed", "Allowed", "Exempt"),
    ("Decider Apps (Google Sheets, URL Import)", "routes/decider_store.py", "Blocked (403)", "Blocked (403)", "Blocked (403)", "Allowed", "Allowed", "Exempt"),
    ("Book Expert & Expert Review", "routes/module_limits.py", "0 Quota (402)", "L3: 1 Expert | L4: 1 Exp+1 Rev", "Allowed / SKU", "Priority Access", "Priority Access", "Exempt"),
]

for row_idx, row_data in enumerate(matrix_data, start=5):
    ws2.row_dimensions[row_idx].height = 24
    for col_idx, val in enumerate(row_data, start=1):
        cell = ws2.cell(row=row_idx, column=col_idx, value=val)
        cell.font = font_body
        cell.border = thin_border
        cell.alignment = Alignment(horizontal="center", vertical="center")
        
        if col_idx == 1:
            cell.font = font_bold
            cell.alignment = Alignment(horizontal="left", vertical="center")
        elif col_idx == 2:
            cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # Color Highlights for status
        val_str = str(val)
        if "Allowed" in val_str or "Unlimited" in val_str or "Exempt" in val_str:
            cell.fill = PatternFill(start_color=GREEN_FILL, end_color=GREEN_FILL, fill_type="solid")
            cell.font = Font(name="Calibri", size=11, bold=True, color=GREEN_FONT)
        elif "Blocked" in val_str:
            cell.fill = PatternFill(start_color=RED_FILL, end_color=RED_FILL, fill_type="solid")
            cell.font = Font(name="Calibri", size=11, bold=True, color=RED_FONT)
        elif "Capped" in val_str or "L1:" in val_str or "Quota" in val_str or "Bundle" in val_str:
            cell.fill = PatternFill(start_color=YELLOW_FILL, end_color=YELLOW_FILL, fill_type="solid")
            cell.font = Font(name="Calibri", size=11, bold=True, color=YELLOW_FONT)

# ----------------------------------------------------------------------
# SHEET 3: On-Demand SKU Rules
# ----------------------------------------------------------------------
ws3 = wb.create_sheet(title="On-Demand SKU Breakdown")
ws3.views.sheetView[0].showGridLines = True

ws3.merge_cells("A1:F1")
ws3["A1"] = "ON-DEMAND SKU PRICING & ENTITLEMENT ALLOCATION"
ws3["A1"].font = font_title
ws3["A1"].fill = fill_title
ws3["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
ws3.row_dimensions[1].height = 35

ws3.merge_cells("A2:F2")
ws3["A2"] = "Breakdown of SKU Codes (L1-L4), Quotas, Bundle Sharing, and Subscription Upgrade Prompts"
ws3["A2"].font = font_subtitle
ws3["A2"].fill = fill_title
ws3["A2"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
ws3.row_dimensions[2].height = 22

headers_3 = [
    "SKU Code",
    "Tier ID",
    "Included Quota Units",
    "Allowed Modules",
    "Expiration (Days)",
    "Upgrade Prompt Behavior",
]

for col_idx, h in enumerate(headers_3, start=1):
    cell = ws3.cell(row=4, column=col_idx, value=h)
    cell.font = font_header
    cell.fill = fill_header
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border = header_border
ws3.row_dimensions[4].height = 25

sku_data = [
    ("L1", "on_demand_l1", "1 DIY Decision", "My Dezider, Pros & Cons, Solution Finder", "30 Days", "Prompts for L2 or Basic/Pro after 1 use"),
    ("L2", "on_demand_l2", "5 Shared Bundle Units", "My Dezider, Pros & Cons, Solution Finder, Group Decision, Book Expert, Expert Review", "365 Days", "Prompts after consuming 5 shared bundle units"),
    ("L3", "on_demand_l3", "1 Book Expert Session", "Book Expert", "90 Days", "Prompts to purchase additional sessions or upgrade to Pro/Premium"),
    ("L4", "on_demand_l4", "1 Expert + 1 Review", "Book Expert, Expert Review", "90 Days", "Prompts after using included session units"),
]

for row_idx, row_data in enumerate(sku_data, start=5):
    ws3.row_dimensions[row_idx].height = 24
    for col_idx, val in enumerate(row_data, start=1):
        cell = ws3.cell(row=row_idx, column=col_idx, value=val)
        cell.font = font_body
        cell.border = thin_border
        if col_idx == 1:
            cell.font = font_bold
            cell.alignment = Alignment(horizontal="center", vertical="center")
        elif col_idx in [2, 5]:
            cell.alignment = Alignment(horizontal="center", vertical="center")
        else:
            cell.alignment = Alignment(horizontal="left", vertical="center")
        if row_idx % 2 == 1:
            cell.fill = fill_zebra

# Auto-adjust column widths for all sheets
for ws in [ws1, ws2, ws3]:
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or '')
            if cell.coordinate in ws.merged_cells:
                continue
            max_len = max(max_len, len(val_str))
        ws.column_dimensions[col_letter].width = max(max_len + 4, 15)

# Save output
os.makedirs(r"c:\wamp64\www\view-dezider\scripts", exist_ok=True)
output_path = r"c:\wamp64\www\view-dezider\Subscription_Plan_Gating_Matrix.xlsx"
wb.save(output_path)
print(f"Workbook successfully saved to {output_path}")
