"""Seed the "Viral Marketing Campaign Planner" decision template.

Idempotent — re-running the script overwrites the same template_id so admin
edits made directly in Mongo are the only source of drift.

Run:
  cd /app/backend && python3 scripts/seed_viral_marketing_template.py

The template is stored in `db.templates` (the same collection used by the
built-in template picker on Solution Box). Any user can list & use it via
POST /api/templates/{template_id}/use.

Reference — viral formula adapted from David Skok / For Entrepreneurs:
  https://www.forentrepreneurs.com/lessons-learnt-viral-marketing/
    projected_customers = initial_users
                          * ref_pct/100
                          * avg_refs_per_user
                          * conv_pct/100
                          * (duration_days / cycle_days)
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import db  # noqa: E402


TEMPLATE_ID = "viral-marketing-campaign-v1"

# Ordered factors (order = 1..N). Every top-level factor gets a stable
# variable_id (f1..fN) so the formulas below always resolve deterministically
# regardless of the user's reorder actions.
FACTORS = [
    # ── Inputs ──
    ("f1",  "Initial Userbase Count",              "primary",   "count",  1000,  "quantitative"),
    ("f2",  "% of Users Who Refer",                "primary",   "%",      20,    "quantitative"),
    ("f3",  "Avg. Number of Referrals per User",   "primary",   "count",  3,     "quantitative"),
    ("f4",  "% of Referrals Converted",            "primary",   "%",      30,    "quantitative"),
    ("f5",  "Avg. Cycle Time of Conversion",       "secondary", "days",   5,     "quantitative"),
    ("f6",  "Campaign Duration (days)",            "primary",   "days",   60,    "quantitative"),
    # ── Computed ──
    ("f7",  "Projected Total Customers",           "primary",   "count",  None,  "quantitative"),
    ("f8",  "ARPU — Avg Revenue per User",         "primary",   "USD",    50,    "quantitative"),
    ("f9",  "CAC — Cost of Sales per Customer",    "secondary", "USD",    12,    "quantitative"),
    ("f10", "Internal Operational Cost",           "secondary", "USD",    5000,  "quantitative"),
    ("f11", "External Ops Cost",                   "secondary", "USD",    3000,  "quantitative"),
    ("f12", "Available Budget / Reserves",         "primary",   "USD",    50000, "quantitative"),
    # ── Roll-ups (used to score / compare campaigns) ──
    ("f13", "Projected Revenue",                   "primary",   "USD",    None,  "quantitative"),
    ("f14", "Total Campaign Cost",                 "primary",   "USD",    None,  "quantitative"),
    ("f15", "Net Contribution (Profit)",           "primary",   "USD",    None,  "quantitative"),
    ("f16", "ROI Multiple",                        "primary",   "x",      None,  "quantitative"),
]

FORMULAS = [
    {
        "id": "fx_projected_customers",
        "target": "f7",
        "expression": "f1 * (f2/100) * f3 * (f4/100) * (f6/f5)",
        "scope": "per_option",
        "description": "Viral spread: initial × refer% × refs × conv% × cycles-in-duration",
    },
    {
        "id": "fx_projected_revenue",
        "target": "f13",
        "expression": "f7 * f8",
        "scope": "per_option",
        "description": "Projected customers × ARPU",
    },
    {
        "id": "fx_total_cost",
        "target": "f14",
        "expression": "(f7 * f9) + f10 + f11",
        "scope": "per_option",
        "description": "CAC × customers + internal + external ops",
    },
    {
        "id": "fx_net_contribution",
        "target": "f15",
        "expression": "f13 - f14",
        "scope": "per_option",
        "description": "Revenue minus total cost",
    },
    {
        "id": "fx_roi_multiple",
        "target": "f16",
        "expression": "f13 / max(f14, 1)",
        "scope": "per_option",
        "description": "Revenue / total cost (guarded against 0)",
    },
]


async def main():
    now = datetime.now(timezone.utc)
    # Attribution — prefer super admin, else any admin, else 'system'.
    admin = (
        await db.users.find_one({"email": "super@test.com"}, {"user_id": 1, "name": 1, "email": 1})
        or await db.users.find_one({"role": "super_admin"}, {"user_id": 1, "name": 1, "email": 1})
        or await db.users.find_one({"role": "admin"}, {"user_id": 1, "name": 1, "email": 1})
    )
    admin_id = admin["user_id"] if admin else "system"
    admin_name = (admin or {}).get("name", "System")
    admin_email = (admin or {}).get("email", "")

    factors = []
    for idx, (var_id, name, category, unit, expected, ftype) in enumerate(FACTORS, start=1):
        factors.append({
            "id": str(uuid.uuid4()),
            "name": name,
            "category": category,
            "rating": 0,           # laddered on-demand on use
            "order": idx - 1,
            "variable_id": var_id,
            "unit": unit,
            "expected_value": expected,
            "factor_type": ftype,
            "operator": ">=" if isinstance(expected, (int, float)) else None,
            "gap_multiplier": 1.0,
        })

    template = {
        "id": TEMPLATE_ID,
        "name": "Viral Marketing Campaign Planner",
        "template_type": "options",
        "visibility": "public",
        "authorized": True,
        "shared_with": [],
        "created_by": admin_id,
        "created_by_name": admin_name,
        "created_by_email": admin_email,
        "source_decision_title": "Viral Marketing Campaign Planner",
        "context": (
            "Compare two or more marketing campaign plans across a proven viral-growth "
            "formula (For Entrepreneurs / David Skok). The template pre-populates 16 "
            "factors — from Initial Userbase (f1) through ROI Multiple (f16) — and 5 "
            "editable dependency formulas that auto-compute Projected Customers, "
            "Projected Revenue, Total Cost, Net Contribution and ROI once you enter "
            "each campaign's inputs. Reference: "
            "https://www.forentrepreneurs.com/lessons-learnt-viral-marketing/"
        ),
        "factors": factors,
        "options": [],
        "formulas": FORMULAS,
        "equal_weightage": False,
        "category": "Marketing",
        "decision_type": "aspiration",
        "created_at": now,
        "updated_at": now,
    }

    result = await db.templates.replace_one(
        {"id": TEMPLATE_ID}, template, upsert=True
    )
    print(
        f"[seed_viral_marketing_template] {'upserted' if result.upserted_id else 'updated'} "
        f"template_id={TEMPLATE_ID} · {len(factors)} factors · {len(FORMULAS)} formulas"
    )


if __name__ == "__main__":
    asyncio.run(main())
