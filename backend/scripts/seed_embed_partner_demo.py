"""Idempotent seed for the embed-partner demo (PMSBazaar pitch).

Creates / refreshes:
  • organization  pmsbazaar-demo  (BUSINESS, maroon brand)
  • org member     analyst@pmsbazaar-demo.com / PmsAnalyst2026!   (org_member)
  • org admin      admin@pmsbazaar-demo.com   / PmsAdmin2026!     (org_super_admin)
  • decision_embed_config — white-label, maroon theme, frictionless login
    (otp_required=False, expose_dev_code=True) so the embed demo is testable.

Run:  python -m scripts.seed_embed_partner_demo   (from /app/backend)
Safe to run repeatedly.
"""
import asyncio
from datetime import datetime, timezone

from core.database import db
from core.auth import get_password_hash
from core.helpers import generate_user_id

ORG_SLUG = "pmsbazaar-demo"
MAROON = "#7B1E3B"
GOLD = "#C9A24B"


async def _upsert_org() -> dict:
    org = await db.organizations.find_one({"slug": ORG_SLUG})
    if org:
        await db.organizations.update_one(
            {"slug": ORG_SLUG},
            {"$set": {
                "org_type": "BUSINESS",
                "primary_color": MAROON,
                "accent_color": GOLD,
                "tagline": "India's No.1 Alternative Investment Platform",
            }},
        )
        return await db.organizations.find_one({"slug": ORG_SLUG})
    import uuid
    org = {
        "id": str(uuid.uuid4()),
        "name": "PMS Bazaar (Demo)",
        "slug": ORG_SLUG,
        "org_type": "BUSINESS",
        "logo_url": "",
        "primary_color": MAROON,
        "accent_color": GOLD,
        "tagline": "India's No.1 Alternative Investment Platform",
        "created_by": "seed",
        "created_at": datetime.now(timezone.utc),
    }
    await db.organizations.insert_one(org)
    return org


async def _upsert_user(email: str, name: str, password: str, org_id: str,
                       org_role: str, whatsapp: str) -> str:
    existing = await db.users.find_one({"email": email})
    fields = {
        "name": name,
        "password_hash": get_password_hash(password),
        "org_id": org_id,
        "org_role": org_role,
        "auth_method": "email",
        "whatsapp_number": whatsapp,
        "role": "user",
    }
    if existing:
        await db.users.update_one({"email": email}, {"$set": fields})
        return existing["user_id"]
    uid = generate_user_id()
    await db.users.insert_one({
        "user_id": uid,
        "email": email,
        "created_at": datetime.now(timezone.utc),
        **fields,
    })
    return uid


async def _upsert_embed_config(org_id: str):
    doc = {
        "org_id": org_id,
        "slug": ORG_SLUG,
        "allowed_origins": ["pmsbazaar.com", "www.pmsbazaar.com", "localhost"],
        "branding_mode": "white_label",
        "enabled_flows": ["mydezider", "pros_cons", "screener"],
        "theme": {
            "primary_color": MAROON,
            "accent_color": GOLD,
            "logo_uri": None,
            "font_family": None,
            "hide_powered_by": False,
        },
        "auth_mode": "frictionless",
        "otp_required": False,          # frictionless for the demo
        "expose_dev_code": True,        # so OTP path is testable if toggled on
        "screener_pricing": {
            "base_credits": 1.0,
            "per_candidate": 0.01,
            "per_finalist": 0.1,
            "per_factor": 0.05,
            "billing_mode": "both",
        },
        "ingestion": {
            "api_enabled": False,
            "api_endpoint": None,
            "api_auth_header": None,
            "csv_sheet_enabled": True,
            "scrape_enabled": False,
            "scrape_legal_ack": False,
            "scrape_terms_ack": False,
        },
        "updated_by": "seed",
        "updated_at": datetime.now(timezone.utc),
    }
    await db.decision_embed_config.update_one(
        {"org_id": org_id},
        {"$set": doc, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


async def main():
    org = await _upsert_org()
    member_id = await _upsert_user(
        "analyst@pmsbazaar-demo.com", "PMS Analyst", "PmsAnalyst2026!",
        org["id"], "org_member", "919000000001",
    )
    admin_id = await _upsert_user(
        "admin@pmsbazaar-demo.com", "PMS Org Admin", "PmsAdmin2026!",
        org["id"], "org_super_admin", "919000000002",
    )
    await _upsert_embed_config(org["id"])
    print("✅ Embed partner demo seeded")
    print(f"   org_id={org['id']} slug={ORG_SLUG}")
    print(f"   member user_id={member_id} (analyst@pmsbazaar-demo.com)")
    print(f"   admin  user_id={admin_id} (admin@pmsbazaar-demo.com)")


if __name__ == "__main__":
    asyncio.run(main())
