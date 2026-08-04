"""Seed 10 curated, official decision templates for Solopreneur / Startup /
MSME founders in TN & KA who are pre-/post-breakeven and heading toward
scalability. Each template carries:

- Predefined factor list (5–8 factors)
- Mandatory (primary) / Optional (secondary) classification
- Priority-based `rating` (10..1 → higher = more important). Calibrated to
  reflect realistic weighting a bootstrapped founder would use when
  paying ₹2,000 for the decision.

Templates are inserted into BOTH:
  • `templates` — the source-of-truth store used by /prr/[id] cloning
  • `decider_store_templates` — the storefront read by /decider-store

Idempotent — re-runs safely (upserts on `id`).

Admin-only endpoint: POST /api/admin/decision-templates/seed-founder-pack
"""
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from core.auth import require_super_admin
from core.database import db

router = APIRouter(tags=["decision-templates-seed"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _factor(name: str, category: str, rating: int, order: int, factor_type: str = "qualitative") -> Dict[str, Any]:
    """Build a factor dict compatible with `db.templates` schema."""
    return {
        "id": f"seed-f-{order}-{name.lower().replace(' ', '-')[:24]}",
        "name": name,
        "category": category,      # 'primary' = Mandatory, 'secondary' = Optional
        "rating": rating,          # 10..1 priority weight
        "order": order,
        "factor_type": factor_type,
        "gap_multiplier": 1.0,
    }


# Each entry: (id, name, context, category_label, decision_type, factors)
# rating scale: mandatory factors typically 8-10, optional typically 3-6.
_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "tpl_founder_hire_vs_freelance",
        "name": "Hire Full-Time vs Freelance / Contractor",
        "context": "You have work to get done — a critical role. Full-time hire = commitment, culture, benefits burden; freelancer = speed, flexibility, no long-term drag but weaker IP and culture. For a founder pre- or just-post breakeven, this call directly impacts runway.",
        "category": "Talent & Team",
        "decision_type": "Choice Selection",
        "factors": [
            _factor("Total 12-month cost (₹)", "primary", 10, 1, "quantitative"),
            _factor("Speed to productive output", "primary", 9, 2),
            _factor("IP protection & confidentiality", "primary", 8, 3),
            _factor("Strategic vs commodity work", "primary", 8, 4),
            _factor("Culture fit / long-term retention", "secondary", 5, 5),
            _factor("Managerial overhead on founder", "secondary", 4, 6),
        ],
    },
    {
        "id": "tpl_founder_capital_source",
        "name": "Bank Loan vs Angel Investor vs Bootstrap",
        "context": "You need capital to fund growth or a specific initiative. Each source trades off equity, control, cost and speed differently. Wrong choice here can compound painfully — dilution now, control loss later, or debt strangling cashflow.",
        "category": "Financial",
        "decision_type": "Choice Selection",
        "factors": [
            _factor("Equity dilution %", "primary", 10, 1, "quantitative"),
            _factor("Effective cost of capital (%)", "primary", 9, 2, "quantitative"),
            _factor("Founder control retained", "primary", 9, 3),
            _factor("Time to close funds (weeks)", "primary", 8, 4, "quantitative"),
            _factor("Strategic value beyond money", "secondary", 6, 5),
            _factor("Reporting / governance burden", "secondary", 4, 6),
            _factor("Personal-guarantee risk", "secondary", 5, 7),
        ],
    },
    {
        "id": "tpl_founder_b2b_vs_b2c",
        "name": "B2B Enterprise Deal vs B2C / SMB Volume Play",
        "context": "One giant enterprise contract vs many small paying customers. Enterprise = predictable ARR but long sales cycles and founder-time drain. SMB volume = distributed risk but higher CAC per rupee. Which mode do you architect the next 6 months around?",
        "category": "Go-to-Market",
        "decision_type": "Choice Selection",
        "factors": [
            _factor("LTV per customer (₹)", "primary", 10, 1, "quantitative"),
            _factor("Sales cycle length (months)", "primary", 8, 2, "quantitative"),
            _factor("Revenue predictability", "primary", 9, 3),
            _factor("Cash-flow timing fit", "primary", 8, 4),
            _factor("Founder time required", "secondary", 6, 5),
            _factor("Team capacity match", "secondary", 5, 6),
            _factor("Competitive moat built", "secondary", 4, 7),
        ],
    },
    {
        "id": "tpl_founder_delegate_vs_diy",
        "name": "Delegate vs Do-It-Yourself (Founder Task)",
        "context": "As founder, every hour spent doing operational work is an hour NOT spent on strategy, hiring or fundraising. But hiring or outsourcing costs money and quality risk. Apply this to the specific task on your plate right now.",
        "category": "Founder Productivity",
        "decision_type": "Choice Selection",
        "factors": [
            _factor("Strategic value of task", "primary", 10, 1),
            _factor("Cost of hiring / outsourcing (₹)", "primary", 8, 2, "quantitative"),
            _factor("Quality risk if delegated", "primary", 8, 3),
            _factor("Speed impact vs DIY", "primary", 7, 4),
            _factor("Founder learning value from doing", "secondary", 5, 5),
            _factor("Recurring vs one-off nature", "secondary", 6, 6),
        ],
    },
    {
        "id": "tpl_founder_product_depth_vs_breadth",
        "name": "Deepen Current Product vs Launch New Product Line",
        "context": "Existing customers are asking for BOTH more depth (Product A v2) and adjacent products (Product B). You can only build one this quarter. Wrong choice fragments engineering and dilutes go-to-market focus.",
        "category": "Product Strategy",
        "decision_type": "Choice Selection",
        "factors": [
            _factor("Existing customer pull (Y/N/strength)", "primary", 10, 1),
            _factor("TAM expansion potential", "primary", 8, 2),
            _factor("Engineering cost (person-months)", "primary", 8, 3, "quantitative"),
            _factor("Distraction risk to core product", "primary", 8, 4),
            _factor("Competitive threat blocked", "secondary", 6, 5),
            _factor("Fits founder's domain expertise", "secondary", 4, 6),
        ],
    },
    {
        "id": "tpl_founder_geo_expansion_tn_ka",
        "name": "Expand from Tamil Nadu into Karnataka (Bangalore)",
        "context": "You've validated in Chennai / TN. Bangalore is the natural next city — bigger buyer maturity, but also more competition and higher cost. Do you open a Karnataka presence this year, or double down at home first?",
        "category": "Growth",
        "decision_type": "Choice Selection",
        "factors": [
            _factor("Market maturity for your offering", "primary", 10, 1),
            _factor("Cost of entry — 12 month burn (₹)", "primary", 9, 2, "quantitative"),
            _factor("Talent access (sales / delivery)", "primary", 8, 3),
            _factor("Home-market saturation risk", "primary", 7, 4),
            _factor("Legal / GST / compliance ease", "secondary", 5, 5),
            _factor("Founder travel bandwidth", "secondary", 5, 6),
            _factor("Existing customer references in KA", "secondary", 6, 7),
        ],
    },
    {
        "id": "tpl_founder_fire_whale_client",
        "name": "Fire the Whale Client (Concentration Risk)",
        "context": "One client is 40%+ of revenue. Losing them hurts, but they're demanding, slow-paying, and blocking your team from serving other accounts. Do you keep serving them, renegotiate, or exit the relationship?",
        "category": "Client & Revenue",
        "decision_type": "Choice Selection",
        "factors": [
            _factor("% of total revenue at risk", "primary", 10, 1, "quantitative"),
            _factor("Payment reliability & terms", "primary", 8, 2),
            _factor("Replacement pipeline (months to backfill)", "primary", 9, 3, "quantitative"),
            _factor("Team morale impact", "primary", 7, 4),
            _factor("Reputation / reference value", "secondary", 6, 5),
            _factor("Strategic learning from account", "secondary", 4, 6),
        ],
    },
    {
        "id": "tpl_founder_office_wfh_coworking_owned",
        "name": "Office: WFH vs Coworking vs Owned Space",
        "context": "Post-COVID, the choice is real. WFH keeps costs near-zero but hurts young teams' culture. Coworking is flexible but expensive per seat at scale. Owned office signals commitment but locks in years of rent.",
        "category": "Operations",
        "decision_type": "Choice Selection",
        "factors": [
            _factor("Monthly cost per head (₹)", "primary", 9, 1, "quantitative"),
            _factor("Team collaboration / velocity", "primary", 8, 2),
            _factor("Talent attraction & retention", "primary", 8, 3),
            _factor("Client-meeting suitability", "primary", 6, 4),
            _factor("Cultural depth possible", "secondary", 6, 5),
            _factor("Flexibility to scale up / down", "secondary", 7, 6),
            _factor("Lock-in / exit cost", "secondary", 5, 7),
        ],
    },
    {
        "id": "tpl_founder_saas_tool_consolidation",
        "name": "SaaS Tool Consolidation vs Best-of-Breed Stack",
        "context": "You're paying for 12 tools — CRM, PM, HRIS, accounting, marketing… A single suite (Zoho / Freshworks / etc) promises 40% cost savings and unified data. But best-of-breed tools each do their job better. Which side of the tradeoff?",
        "category": "Tools & Infrastructure",
        "decision_type": "Choice Selection",
        "factors": [
            _factor("Annual cost (₹)", "primary", 9, 1, "quantitative"),
            _factor("Feature depth needed for growth", "primary", 8, 2),
            _factor("Integration / data unification value", "primary", 8, 3),
            _factor("Team ramp-up / retraining cost", "primary", 6, 4),
            _factor("Vendor lock-in exposure", "secondary", 6, 5),
            _factor("Migration effort (person-days)", "secondary", 5, 6, "quantitative"),
        ],
    },
    {
        "id": "tpl_founder_salary_vs_reinvest",
        "name": "Founder Salary vs Reinvest into Business",
        "context": "Business is generating cash. You have zero personal runway left. Do you pay yourself a market-rate salary now, take a modest founder salary and reinvest the rest, or stay unpaid and go all-in on growth?",
        "category": "Financial",
        "decision_type": "Choice Selection",
        "factors": [
            _factor("Personal / family runway (months)", "primary", 10, 1, "quantitative"),
            _factor("Business runway impact (months)", "primary", 10, 2, "quantitative"),
            _factor("Tax efficiency (salary vs dividend)", "primary", 7, 3),
            _factor("Growth-rate hit from cash pulled", "primary", 8, 4),
            _factor("Signal to investors / lenders", "secondary", 5, 5),
            _factor("Founder mental-health / burnout risk", "secondary", 7, 6),
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
            "template_type": "prioritization",  # M/O + rating only, no options
            "visibility": "public",
            "shared_with": [],
            "created_by": admin_uid,
            "created_by_name": admin_name,
            "created_by_email": admin_email,
            "source_decision_title": tpl["name"],
            "context": tpl["context"],
            "factors": tpl["factors"],
            "options": [],
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

        # Mirror into Decider Store storefront
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
                "factor_count": len(tpl["factors"]),
                "option_count": 0,
                "is_public": True,
                "is_free": True,
                "pricing_type": "free",
                "is_active": True,
                "status": "authorized",
                "publisher_type": "organization",   # editorial content = organization tier
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
