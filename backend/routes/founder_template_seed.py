"""Seed 10 curated, official decision templates for Solopreneur / Startup /
MSME founders in TN & KA who are pre-/post-breakeven and heading toward
scalability.

Each template is populated up to MyDezider Step 6:
  Step 2 — every factor has an expected value + operator + unit + data type
  Step 3 — grouping (Mandatory / Optional via `category`)
  Step 4 — prioritization (`rating` 10..1)
  Step 5 — realistic gap adjustment (`gap_multiplier` 0.5–3.0)
  Step 6 — 3 realistic options each with per-factor `values`

Templates are inserted into BOTH:
  • `templates`                 — source-of-truth cloned by /prr/[id]
  • `decider_store_templates`   — storefront read by /decider-store
    (mirrors `factors[]` + `options[]` so store cards show real F/O counts)

Idempotent — re-runs safely (upserts on `id`).

Admin-only endpoint: POST /api/admin/decision-templates/seed-founder-pack
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from core.auth import require_super_admin
from core.database import db

router = APIRouter(tags=["decision-templates-seed"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _f(
    name: str,
    cat: str,
    rating: int,
    order: int,
    *,
    expected: str,
    gap: float = 1.0,
    dtype: str = "qualitative",
    unit: Optional[str] = None,
    op: str = "equals",
    expected_pct: int = 60,
) -> Dict[str, Any]:
    """Build a fully-populated factor dict (Steps 2–5)."""
    return {
        "id": f"seed-f-{order}-{name.lower().replace(' ', '-').replace('(', '').replace(')', '').replace('/', '-')[:28]}",
        "name": name,
        "category": cat,               # 'primary' = Mandatory, 'secondary' = Optional
        "rating": rating,              # 10..1 priority weight
        "order": order,
        "priority_rank": order,
        "factor_type": dtype,
        "data_type": dtype,            # 'quantitative' | 'qualitative'
        "unit": unit,
        "operator": op,                # '<=' | '>=' | '=' | 'equals'
        "expected_value": expected,
        "expected_value_pct": expected_pct,
        "gap_multiplier": gap,
        "rating_gap_multiplier": gap,
        "is_active": True,
    }


def _opt(name: str, values: Dict[str, Any], order: int = 0) -> Dict[str, Any]:
    """Build an option with per-factor values (Step 6)."""
    return {
        "id": f"seed-o-{order}-{name.lower().replace(' ', '-').replace('/', '-')[:24]}",
        "name": name,
        "order": order,
        "values": values,
        "notes": "",
    }


# ────────────────────────────────────────────────────────────────────────
# 10 FOUNDER TEMPLATES — hand-crafted realistic content (₹ / TN-KA / MSME)
# ────────────────────────────────────────────────────────────────────────
_TEMPLATES: List[Dict[str, Any]] = [
    # 1) Hire full-time vs Freelance
    {
        "id": "tpl_founder_hire_vs_freelance",
        "name": "Hire Full-Time vs Freelance / Contractor",
        "context": "You have work to get done — a critical role. Full-time hire = commitment, culture, benefits burden; freelancer = speed, flexibility, no long-term drag but weaker IP and culture. For a founder pre- or just-post breakeven, this call directly impacts runway.",
        "category": "Talent & Team",
        "decision_type": "Choice Selection",
        "factors": [
            _f("Total 12-month cost (₹)",              "primary",   10, 1, expected="≤ ₹15,00,000", gap=2.0, dtype="quantitative", unit="₹",       op="<="),
            _f("Speed to productive output",           "primary",    9, 2, expected="≤ 2 weeks",    gap=1.5, dtype="quantitative", unit="weeks",   op="<="),
            _f("IP protection & confidentiality",      "primary",    8, 3, expected="High",         gap=1.8),
            _f("Strategic vs commodity work",          "primary",    8, 4, expected="Strategic",    gap=1.5),
            _f("Culture fit / long-term retention",    "secondary",  5, 5, expected="Strong",       gap=1.0),
            _f("Managerial overhead on founder",       "secondary",  4, 6, expected="Low",          gap=0.8),
        ],
        "options": [
            _opt("Full-time hire (in-house)", {
                "Total 12-month cost (₹)": "₹18,00,000",
                "Speed to productive output": "6 weeks",
                "IP protection & confidentiality": "High",
                "Strategic vs commodity work": "Strategic",
                "Culture fit / long-term retention": "Strong",
                "Managerial overhead on founder": "High",
            }, 1),
            _opt("Freelancer on retainer", {
                "Total 12-month cost (₹)": "₹9,60,000",
                "Speed to productive output": "1 week",
                "IP protection & confidentiality": "Medium",
                "Strategic vs commodity work": "Commodity",
                "Culture fit / long-term retention": "Weak",
                "Managerial overhead on founder": "Low",
            }, 2),
            _opt("Fractional / part-time expert", {
                "Total 12-month cost (₹)": "₹12,00,000",
                "Speed to productive output": "2 weeks",
                "IP protection & confidentiality": "High",
                "Strategic vs commodity work": "Strategic",
                "Culture fit / long-term retention": "Medium",
                "Managerial overhead on founder": "Medium",
            }, 3),
        ],
    },

    # 2) Bank Loan vs Angel vs Bootstrap
    {
        "id": "tpl_founder_capital_source",
        "name": "Bank Loan vs Angel Investor vs Bootstrap",
        "context": "You need capital to fund growth or a specific initiative. Each source trades off equity, control, cost and speed differently. Wrong choice here can compound painfully — dilution now, control loss later, or debt strangling cashflow.",
        "category": "Financial",
        "decision_type": "Choice Selection",
        "factors": [
            _f("Equity dilution %",                    "primary",   10, 1, expected="0",           gap=2.5, dtype="quantitative", unit="%",         op="<="),
            _f("Effective cost of capital (%)",        "primary",    9, 2, expected="≤ 12",        gap=2.0, dtype="quantitative", unit="% p.a.",    op="<="),
            _f("Founder control retained",             "primary",    9, 3, expected="Full",        gap=2.0),
            _f("Time to close funds (weeks)",          "primary",    8, 4, expected="≤ 6",         gap=1.5, dtype="quantitative", unit="weeks",     op="<="),
            _f("Strategic value beyond money",         "secondary",  6, 5, expected="High",        gap=1.0),
            _f("Reporting / governance burden",        "secondary",  4, 6, expected="Low",         gap=0.8),
            _f("Personal-guarantee risk",              "secondary",  5, 7, expected="None",        gap=1.5),
        ],
        "options": [
            _opt("Bank term loan (secured)", {
                "Equity dilution %": "0",
                "Effective cost of capital (%)": "11",
                "Founder control retained": "Full",
                "Time to close funds (weeks)": "8",
                "Strategic value beyond money": "Low",
                "Reporting / governance burden": "Medium",
                "Personal-guarantee risk": "High",
            }, 1),
            _opt("Angel investor round (₹1-2 Cr)", {
                "Equity dilution %": "15",
                "Effective cost of capital (%)": "0",
                "Founder control retained": "Reduced",
                "Time to close funds (weeks)": "12",
                "Strategic value beyond money": "High",
                "Reporting / governance burden": "High",
                "Personal-guarantee risk": "None",
            }, 2),
            _opt("Bootstrap from revenue", {
                "Equity dilution %": "0",
                "Effective cost of capital (%)": "0",
                "Founder control retained": "Full",
                "Time to close funds (weeks)": "0",
                "Strategic value beyond money": "None",
                "Reporting / governance burden": "None",
                "Personal-guarantee risk": "None",
            }, 3),
        ],
    },

    # 3) B2B Enterprise vs B2C/SMB Volume
    {
        "id": "tpl_founder_b2b_vs_b2c",
        "name": "B2B Enterprise Deal vs B2C / SMB Volume Play",
        "context": "One giant enterprise contract vs many small paying customers. Enterprise = predictable ARR but long sales cycles and founder-time drain. SMB volume = distributed risk but higher CAC per rupee. Which mode do you architect the next 6 months around?",
        "category": "Go-to-Market",
        "decision_type": "Choice Selection",
        "factors": [
            _f("LTV per customer (₹)",                 "primary",   10, 1, expected="≥ ₹5,00,000", gap=2.0, dtype="quantitative", unit="₹",       op=">="),
            _f("Sales cycle length (months)",          "primary",    8, 2, expected="≤ 3",         gap=1.8, dtype="quantitative", unit="months",  op="<="),
            _f("Revenue predictability",               "primary",    9, 3, expected="High",        gap=1.5),
            _f("Cash-flow timing fit",                 "primary",    8, 4, expected="Monthly recurring", gap=1.5),
            _f("Founder time required",                "secondary",  6, 5, expected="Low",         gap=1.0),
            _f("Team capacity match",                  "secondary",  5, 6, expected="Fits current team", gap=1.0),
            _f("Competitive moat built",               "secondary",  4, 7, expected="Strong",      gap=1.0),
        ],
        "options": [
            _opt("Enterprise ACV focus (₹25L+ deals)", {
                "LTV per customer (₹)": "₹40,00,000",
                "Sales cycle length (months)": "9",
                "Revenue predictability": "High",
                "Cash-flow timing fit": "Quarterly",
                "Founder time required": "High",
                "Team capacity match": "Stretched",
                "Competitive moat built": "Strong",
            }, 1),
            _opt("SMB volume play (₹50k-₹2L ACV)", {
                "LTV per customer (₹)": "₹1,80,000",
                "Sales cycle length (months)": "1",
                "Revenue predictability": "Medium",
                "Cash-flow timing fit": "Monthly recurring",
                "Founder time required": "Low",
                "Team capacity match": "Fits current team",
                "Competitive moat built": "Medium",
            }, 2),
            _opt("Mid-market balanced (₹5-10L ACV)", {
                "LTV per customer (₹)": "₹12,00,000",
                "Sales cycle length (months)": "4",
                "Revenue predictability": "High",
                "Cash-flow timing fit": "Monthly recurring",
                "Founder time required": "Medium",
                "Team capacity match": "Fits current team",
                "Competitive moat built": "Medium",
            }, 3),
        ],
    },

    # 4) Delegate vs DIY
    {
        "id": "tpl_founder_delegate_vs_diy",
        "name": "Delegate vs Do-It-Yourself (Founder Task)",
        "context": "As founder, every hour spent doing operational work is an hour NOT spent on strategy, hiring or fundraising. But hiring or outsourcing costs money and quality risk. Apply this to the specific task on your plate right now.",
        "category": "Founder Productivity",
        "decision_type": "Choice Selection",
        "factors": [
            _f("Strategic value of task",              "primary",   10, 1, expected="High",        gap=2.0),
            _f("Cost of hiring / outsourcing (₹/mo)",  "primary",    8, 2, expected="≤ ₹50,000",   gap=1.5, dtype="quantitative", unit="₹/mo", op="<="),
            _f("Quality risk if delegated",            "primary",    8, 3, expected="Low",         gap=1.8),
            _f("Speed impact vs DIY",                  "primary",    7, 4, expected="Faster",      gap=1.3),
            _f("Founder learning value from doing",    "secondary",  5, 5, expected="Low",         gap=0.8),
            _f("Recurring vs one-off nature",          "secondary",  6, 6, expected="Recurring",   gap=1.0),
        ],
        "options": [
            _opt("Do it yourself", {
                "Strategic value of task": "Low",
                "Cost of hiring / outsourcing (₹/mo)": "₹0",
                "Quality risk if delegated": "None",
                "Speed impact vs DIY": "Baseline",
                "Founder learning value from doing": "Medium",
                "Recurring vs one-off nature": "Recurring",
            }, 1),
            _opt("Delegate to internal team", {
                "Strategic value of task": "Medium",
                "Cost of hiring / outsourcing (₹/mo)": "₹35,000",
                "Quality risk if delegated": "Low",
                "Speed impact vs DIY": "Faster",
                "Founder learning value from doing": "Low",
                "Recurring vs one-off nature": "Recurring",
            }, 2),
            _opt("Outsource to specialist agency", {
                "Strategic value of task": "Low",
                "Cost of hiring / outsourcing (₹/mo)": "₹60,000",
                "Quality risk if delegated": "Medium",
                "Speed impact vs DIY": "Much faster",
                "Founder learning value from doing": "Low",
                "Recurring vs one-off nature": "One-off",
            }, 3),
        ],
    },

    # 5) Product depth vs breadth
    {
        "id": "tpl_founder_product_depth_vs_breadth",
        "name": "Deepen Current Product vs Launch New Product Line",
        "context": "Existing customers are asking for BOTH more depth (Product A v2) and adjacent products (Product B). You can only build one this quarter. Wrong choice fragments engineering and dilutes go-to-market focus.",
        "category": "Product Strategy",
        "decision_type": "Choice Selection",
        "factors": [
            _f("Existing customer pull",               "primary",   10, 1, expected="Strong",      gap=2.0),
            _f("TAM expansion potential",              "primary",    8, 2, expected="High",       gap=1.5),
            _f("Engineering cost (person-months)",     "primary",    8, 3, expected="≤ 6",        gap=1.5, dtype="quantitative", unit="p-mo", op="<="),
            _f("Distraction risk to core product",     "primary",    8, 4, expected="Low",        gap=2.0),
            _f("Competitive threat blocked",           "secondary",  6, 5, expected="Yes",        gap=1.0),
            _f("Fits founder's domain expertise",      "secondary",  4, 6, expected="Yes",        gap=1.0),
        ],
        "options": [
            _opt("Deepen Product A (v2)", {
                "Existing customer pull": "Strong",
                "TAM expansion potential": "Medium",
                "Engineering cost (person-months)": "5",
                "Distraction risk to core product": "Low",
                "Competitive threat blocked": "Yes",
                "Fits founder's domain expertise": "Yes",
            }, 1),
            _opt("Launch new Product B", {
                "Existing customer pull": "Medium",
                "TAM expansion potential": "High",
                "Engineering cost (person-months)": "10",
                "Distraction risk to core product": "High",
                "Competitive threat blocked": "No",
                "Fits founder's domain expertise": "Partial",
            }, 2),
            _opt("Small experiment: 20% team on B", {
                "Existing customer pull": "Medium",
                "TAM expansion potential": "Medium",
                "Engineering cost (person-months)": "3",
                "Distraction risk to core product": "Medium",
                "Competitive threat blocked": "Partial",
                "Fits founder's domain expertise": "Yes",
            }, 3),
        ],
    },

    # 6) Geo expansion TN → KA
    {
        "id": "tpl_founder_geo_expansion_tn_ka",
        "name": "Expand from Tamil Nadu into Karnataka (Bangalore)",
        "context": "You've validated in Chennai / TN. Bangalore is the natural next city — bigger buyer maturity, but also more competition and higher cost. Do you open a Karnataka presence this year, or double down at home first?",
        "category": "Growth",
        "decision_type": "Choice Selection",
        "factors": [
            _f("Market maturity for your offering",    "primary",   10, 1, expected="High",       gap=1.8),
            _f("Cost of entry — 12 month burn (₹)",    "primary",    9, 2, expected="≤ ₹40,00,000", gap=2.0, dtype="quantitative", unit="₹", op="<="),
            _f("Talent access (sales / delivery)",     "primary",    8, 3, expected="Strong",     gap=1.5),
            _f("Home-market saturation risk",          "primary",    7, 4, expected="Rising",     gap=1.2),
            _f("Legal / GST / compliance ease",        "secondary",  5, 5, expected="Simple",     gap=0.8),
            _f("Founder travel bandwidth",             "secondary",  5, 6, expected="≤ 4 days/mo", gap=0.8, dtype="quantitative", unit="days/mo", op="<="),
            _f("Existing customer references in KA",   "secondary",  6, 7, expected="≥ 3",        gap=1.0, dtype="quantitative", unit="refs", op=">="),
        ],
        "options": [
            _opt("Full Bangalore office + KA sales lead", {
                "Market maturity for your offering": "High",
                "Cost of entry — 12 month burn (₹)": "₹60,00,000",
                "Talent access (sales / delivery)": "Strong",
                "Home-market saturation risk": "Rising",
                "Legal / GST / compliance ease": "Simple",
                "Founder travel bandwidth": "8 days/mo",
                "Existing customer references in KA": "2",
            }, 1),
            _opt("Double-down in TN (defer KA 12 mo)", {
                "Market maturity for your offering": "Medium",
                "Cost of entry — 12 month burn (₹)": "₹5,00,000",
                "Talent access (sales / delivery)": "Strong",
                "Home-market saturation risk": "Rising",
                "Legal / GST / compliance ease": "Simple",
                "Founder travel bandwidth": "0 days/mo",
                "Existing customer references in KA": "0",
            }, 2),
            _opt("Remote KA sales rep only (no office)", {
                "Market maturity for your offering": "High",
                "Cost of entry — 12 month burn (₹)": "₹18,00,000",
                "Talent access (sales / delivery)": "Medium",
                "Home-market saturation risk": "Rising",
                "Legal / GST / compliance ease": "Simple",
                "Founder travel bandwidth": "3 days/mo",
                "Existing customer references in KA": "4",
            }, 3),
        ],
    },

    # 7) Fire whale client
    {
        "id": "tpl_founder_fire_whale_client",
        "name": "Fire the Whale Client (Concentration Risk)",
        "context": "One client is 40%+ of revenue. Losing them hurts, but they're demanding, slow-paying, and blocking your team from serving other accounts. Do you keep serving them, renegotiate, or exit the relationship?",
        "category": "Client & Revenue",
        "decision_type": "Choice Selection",
        "factors": [
            _f("% of total revenue at risk",           "primary",   10, 1, expected="≤ 20",        gap=2.5, dtype="quantitative", unit="%",     op="<="),
            _f("Payment reliability & terms",          "primary",    8, 2, expected="On-time NET30", gap=1.8),
            _f("Replacement pipeline (months)",        "primary",    9, 3, expected="≤ 3",         gap=2.0, dtype="quantitative", unit="months", op="<="),
            _f("Team morale impact",                   "primary",    7, 4, expected="Positive",    gap=1.5),
            _f("Reputation / reference value",         "secondary",  6, 5, expected="High",        gap=1.0),
            _f("Strategic learning from account",      "secondary",  4, 6, expected="Ongoing",     gap=0.8),
        ],
        "options": [
            _opt("Keep as-is (no changes)", {
                "% of total revenue at risk": "42",
                "Payment reliability & terms": "Slow NET90",
                "Replacement pipeline (months)": "6",
                "Team morale impact": "Negative",
                "Reputation / reference value": "High",
                "Strategic learning from account": "Ongoing",
            }, 1),
            _opt("Renegotiate: better terms + scope cap", {
                "% of total revenue at risk": "35",
                "Payment reliability & terms": "NET45",
                "Replacement pipeline (months)": "4",
                "Team morale impact": "Neutral",
                "Reputation / reference value": "High",
                "Strategic learning from account": "Ongoing",
            }, 2),
            _opt("Exit gracefully over 6 months", {
                "% of total revenue at risk": "0",
                "Payment reliability & terms": "N/A",
                "Replacement pipeline (months)": "6",
                "Team morale impact": "Positive",
                "Reputation / reference value": "Medium",
                "Strategic learning from account": "Ended",
            }, 3),
        ],
    },

    # 8) Office WFH / Coworking / Owned
    {
        "id": "tpl_founder_office_wfh_coworking_owned",
        "name": "Office: WFH vs Coworking vs Owned Space",
        "context": "Post-COVID, the choice is real. WFH keeps costs near-zero but hurts young teams' culture. Coworking is flexible but expensive per seat at scale. Owned office signals commitment but locks in years of rent.",
        "category": "Operations",
        "decision_type": "Choice Selection",
        "factors": [
            _f("Monthly cost per head (₹)",            "primary",    9, 1, expected="≤ ₹6,000",    gap=1.5, dtype="quantitative", unit="₹/hd/mo", op="<="),
            _f("Team collaboration / velocity",        "primary",    8, 2, expected="High",        gap=1.5),
            _f("Talent attraction & retention",        "primary",    8, 3, expected="Strong",      gap=1.5),
            _f("Client-meeting suitability",           "primary",    6, 4, expected="Good",        gap=1.0),
            _f("Cultural depth possible",              "secondary",  6, 5, expected="High",        gap=1.0),
            _f("Flexibility to scale up / down",       "secondary",  7, 6, expected="High",        gap=1.2),
            _f("Lock-in / exit cost",                  "secondary",  5, 7, expected="Low",         gap=1.0),
        ],
        "options": [
            _opt("WFH-first (fully remote)", {
                "Monthly cost per head (₹)": "₹500",
                "Team collaboration / velocity": "Low",
                "Talent attraction & retention": "Medium",
                "Client-meeting suitability": "Poor",
                "Cultural depth possible": "Low",
                "Flexibility to scale up / down": "High",
                "Lock-in / exit cost": "None",
            }, 1),
            _opt("Coworking hub (WeWork / IndiQube)", {
                "Monthly cost per head (₹)": "₹8,500",
                "Team collaboration / velocity": "High",
                "Talent attraction & retention": "Strong",
                "Client-meeting suitability": "Good",
                "Cultural depth possible": "Medium",
                "Flexibility to scale up / down": "High",
                "Lock-in / exit cost": "Low (1 mo notice)",
            }, 2),
            _opt("Owned / long-lease office", {
                "Monthly cost per head (₹)": "₹5,000",
                "Team collaboration / velocity": "High",
                "Talent attraction & retention": "Strong",
                "Client-meeting suitability": "Excellent",
                "Cultural depth possible": "High",
                "Flexibility to scale up / down": "Low",
                "Lock-in / exit cost": "High (3-yr lock-in)",
            }, 3),
        ],
    },

    # 9) SaaS Consolidation vs Best-of-Breed
    {
        "id": "tpl_founder_saas_tool_consolidation",
        "name": "SaaS Tool Consolidation vs Best-of-Breed Stack",
        "context": "You're paying for 12 tools — CRM, PM, HRIS, accounting, marketing… A single suite (Zoho / Freshworks / etc) promises 40% cost savings and unified data. But best-of-breed tools each do their job better. Which side of the tradeoff?",
        "category": "Tools & Infrastructure",
        "decision_type": "Choice Selection",
        "factors": [
            _f("Annual SaaS cost (₹)",                 "primary",    9, 1, expected="≤ ₹6,00,000", gap=1.5, dtype="quantitative", unit="₹/yr",    op="<="),
            _f("Feature depth needed for growth",      "primary",    8, 2, expected="Deep",        gap=1.5),
            _f("Integration / data unification value", "primary",    8, 3, expected="High",        gap=1.5),
            _f("Team ramp-up / retraining cost",       "primary",    6, 4, expected="Low",         gap=1.0),
            _f("Vendor lock-in exposure",              "secondary",  6, 5, expected="Low",         gap=1.2),
            _f("Migration effort (person-days)",       "secondary",  5, 6, expected="≤ 15",        gap=1.0, dtype="quantitative", unit="p-days", op="<="),
        ],
        "options": [
            _opt("Consolidate to Zoho One", {
                "Annual SaaS cost (₹)": "₹4,80,000",
                "Feature depth needed for growth": "Medium",
                "Integration / data unification value": "High",
                "Team ramp-up / retraining cost": "Medium",
                "Vendor lock-in exposure": "High",
                "Migration effort (person-days)": "25",
            }, 1),
            _opt("Best-of-breed stack (12 tools)", {
                "Annual SaaS cost (₹)": "₹9,60,000",
                "Feature depth needed for growth": "Deep",
                "Integration / data unification value": "Low",
                "Team ramp-up / retraining cost": "None",
                "Vendor lock-in exposure": "Low",
                "Migration effort (person-days)": "0",
            }, 2),
            _opt("Hybrid: core suite + 2-3 specialists", {
                "Annual SaaS cost (₹)": "₹6,60,000",
                "Feature depth needed for growth": "Deep",
                "Integration / data unification value": "High",
                "Team ramp-up / retraining cost": "Low",
                "Vendor lock-in exposure": "Medium",
                "Migration effort (person-days)": "12",
            }, 3),
        ],
    },

    # 10) Founder Salary vs Reinvest
    {
        "id": "tpl_founder_salary_vs_reinvest",
        "name": "Founder Salary vs Reinvest into Business",
        "context": "Business is generating cash. You have zero personal runway left. Do you pay yourself a market-rate salary now, take a modest founder salary and reinvest the rest, or stay unpaid and go all-in on growth?",
        "category": "Financial",
        "decision_type": "Choice Selection",
        "factors": [
            _f("Personal / family runway (months)",    "primary",   10, 1, expected="≥ 6",         gap=2.5, dtype="quantitative", unit="months", op=">="),
            _f("Business runway impact (months)",      "primary",   10, 2, expected="≥ 12",        gap=2.5, dtype="quantitative", unit="months", op=">="),
            _f("Tax efficiency (salary vs dividend)",  "primary",    7, 3, expected="High",        gap=1.2),
            _f("Growth-rate hit from cash pulled",     "primary",    8, 4, expected="Minimal",     gap=1.5),
            _f("Signal to investors / lenders",        "secondary",  5, 5, expected="Reasonable",  gap=1.0),
            _f("Founder mental-health / burnout risk", "secondary",  7, 6, expected="Low",         gap=1.5),
        ],
        "options": [
            _opt("Zero salary + full reinvest", {
                "Personal / family runway (months)": "0",
                "Business runway impact (months)": "18",
                "Tax efficiency (salary vs dividend)": "Low",
                "Growth-rate hit from cash pulled": "None",
                "Signal to investors / lenders": "Risky",
                "Founder mental-health / burnout risk": "High",
            }, 1),
            _opt("Modest ₹1L/mo salary", {
                "Personal / family runway (months)": "6",
                "Business runway impact (months)": "14",
                "Tax efficiency (salary vs dividend)": "High",
                "Growth-rate hit from cash pulled": "Minimal",
                "Signal to investors / lenders": "Reasonable",
                "Founder mental-health / burnout risk": "Low",
            }, 2),
            _opt("Market-rate ₹3L/mo salary", {
                "Personal / family runway (months)": "12",
                "Business runway impact (months)": "9",
                "Tax efficiency (salary vs dividend)": "Medium",
                "Growth-rate hit from cash pulled": "Meaningful",
                "Signal to investors / lenders": "Reasonable",
                "Founder mental-health / burnout risk": "Low",
            }, 3),
        ],
    },
]


@router.post("/admin/decision-templates/seed-founder-pack")
async def seed_founder_templates(user: dict = Depends(require_super_admin)) -> Dict[str, Any]:
    return await _seed_founder_pack(user.get("user_id") or "system",
                                    user.get("name") or user.get("email") or "JELCOS AI Editorial",
                                    user.get("email", ""))


async def seed_founder_pack_on_boot() -> Dict[str, Any]:
    """Idempotent auto-seed run on backend startup so admins don't need to
    manually POST /admin/decision-templates/seed-founder-pack post-deploy."""
    return await _seed_founder_pack("system", "JELCOS AI Editorial", "")


async def _seed_founder_pack(admin_uid: str, admin_name: str, admin_email: str) -> Dict[str, Any]:
    """Idempotently create/refresh the 10 curated founder templates in both
    `templates` and `decider_store_templates`.
    """
    inserted = updated = 0
    now = _now()

    for tpl in _TEMPLATES:
        doc = {
            "id": tpl["id"],
            "name": tpl["name"],
            # Now includes options (Step 6) — flip to full choice-selection.
            "template_type": "choice_selection",
            "visibility": "public",
            "shared_with": [],
            "created_by": admin_uid,
            "created_by_name": admin_name,
            "created_by_email": admin_email,
            "source_decision_title": tpl["name"],
            "context": tpl["context"],
            "factors": tpl["factors"],
            "options": tpl["options"],
            "category": tpl["category"],
            "decision_type": tpl["decision_type"],
            "is_official": True,
            "is_approved": True,
            "authorized": True,
            "updated_at": now,
        }
        existing = await db.templates.find_one({"id": tpl["id"]}, {"_id": 1})
        if existing:
            await db.templates.update_one({"id": tpl["id"]}, {"$set": doc})
            updated += 1
        else:
            doc["created_at"] = now
            await db.templates.insert_one(dict(doc))
            inserted += 1

        # Mirror into Decider Store storefront — INCLUDE factors + options
        # so store cards show real F/O counts and click-through preview
        # can render content without an extra fetch.
        await db.decider_store_templates.update_one(
            {"template_id": tpl["id"]},
            {"$set": {
                "template_id": tpl["id"],
                "id": tpl["id"],
                "kind": "template",
                "title": tpl["name"],
                "subtitle": tpl["category"],
                "description": tpl["context"],
                "category": tpl["category"],
                "life_area": tpl.get("life_area", "Business & Career"),
                "applicable_org_types": tpl.get("applicable_org_types",
                                                ["Solopreneur", "Startup", "MSME"]),
                "decision_type": tpl["decision_type"],
                "factors": tpl["factors"],
                "options": tpl["options"],
                "factor_count": len(tpl["factors"]),
                "option_count": len(tpl["options"]),
                "is_public": True,
                "is_free": True,
                "pricing_type": "free",
                "is_active": True,
                "status": "authorized",
                "publisher_type": "organization",
                "rating_avg": 0.0,
                "rating_count": 0,
                "is_official": True,
                "is_approved": True,
                "creator_name": admin_name,
                "created_by": admin_uid,
                "created_by_name": admin_name,
                "updated_at": now,
                "authorized_by": admin_uid,
                "authorized_at": now,
            },
             "$setOnInsert": {"install_count": 0, "created_at": now}},
            upsert=True,
        )

    return {
        "message": f"Founder Template Pack: {inserted} added, {updated} refreshed.",
        "inserted": inserted, "updated": updated,
        "total_templates_in_pack": len(_TEMPLATES),
    }
