"""Seed the Business-Model-Patterns template into The Decider Store (idempotent).

Run:  cd /app/backend && python scripts/seed_decider_store_bmp.py
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import db  # noqa: E402
from core.decider_import import parse_import  # noqa: E402

FIXED_ID = "bmp-55-patterns"
XLSX = os.path.join(os.path.dirname(__file__), "data", "Business_Model_Assessments.xlsx")


async def main():
    parsed = parse_import(data=open(XLSX, "rb").read())
    now = datetime.now(timezone.utc).isoformat()

    # Attribution only — prefer the known super admin, else any super/admin user.
    admin = (await db.users.find_one({"email": "super@test.com"}, {"user_id": 1})
             or await db.users.find_one({"role": "super_admin"}, {"user_id": 1})
             or await db.users.find_one({"role": "admin"}, {"user_id": 1}))
    admin_id = admin["user_id"] if admin else "system"

    doc = {
        "template_id": FIXED_ID,
        "title": "The 55 Business Model Patterns",
        "subtitle": "Pick the right revenue/business model for your venture",
        "description": ("Compare 54 proven business-model patterns (Affiliation, Aikido, "
                        "Auction, Freemium, Two-Sided Market, White Label, …) across 10 "
                        "strategic factors — Org Type, Solution Category, Nature of Solution, "
                        "Intensity of Need, Affordability, Revenue Model, Tech Orientation, "
                        "Distribution Channels, Value Creation and Differentiation Strategy. "
                        "Each pattern ships with suitability values so you can shortlist fast."),
        "category": "Financial",
        "decision_type": "aspiration",
        "cover_icon": "briefcase",
        "cover_color": "#1E3A8A",
        "pricing_type": "free",
        "price_paise": 0,
        "currency": "INR",
        "creator_split_pct": 70,
        "allowed_clone_modes": ["full", "values_only"],
        "factors": parsed["factors"],
        "options": parsed["options"],
        "created_by": admin_id,
        "creator_name": "Earth Dezider",
        "source": "admin",
        "status": "authorized",
        "is_public": True,
        "install_count": 0,
        "updated_at": now,
        "authorized_at": now,
        "authorized_by": admin_id,
    }
    existing = await db.decider_store_templates.find_one({"template_id": FIXED_ID}, {"install_count": 1, "created_at": 1})
    doc["created_at"] = (existing or {}).get("created_at", now)
    doc["install_count"] = (existing or {}).get("install_count", 0)
    await db.decider_store_templates.replace_one({"template_id": FIXED_ID}, doc, upsert=True)
    print(f"Seeded '{doc['title']}' — {len(doc['factors'])} factors, {len(doc['options'])} options "
          f"(template_id={FIXED_ID}, status=authorized, public).")


if __name__ == "__main__":
    asyncio.run(main())
