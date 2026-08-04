"""
Backfill filter metadata for every doc in `decider_store_templates` so the
Decider Store filter drawer (Life area / Applicable org type / Publisher
type / #Factors / #Options / Free-only / Avg rating / # ratings) actually
excludes and includes the right cards.

Historical seed scripts sometimes forgot to write:
  • life_area                 (used by the Life-area chip row)
  • applicable_org_types      (used by the Org-type chip row)
  • publisher_type            (used by the Publisher-type chip row)
  • is_free                   (mirrored from pricing_type — kept for legacy)
  • factor_count / option_count  (used by the client-side numeric range post-filter)
  • rating_avg / rating_count (defaults 0 — otherwise Min-rating filter hides them)
  • is_official / is_approved (used by moderation queries)

Business Model Chooser in particular was seeded with none of the filter
fields, so it was silently excluded from every filter run. This script
sets sensible defaults for it, and for any other doc missing fields.

Run:
    cd /app/backend && python -m scripts.backfill_decider_store_metadata
"""

import asyncio
import os
import sys
from typing import Any, Dict, List

from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME", "venture_buddha")

DEFAULT_LIFE_AREA = "Business & Career"
DEFAULT_ORG_TYPES = ["Solopreneur", "Startup", "MSME"]
DEFAULT_PUBLISHER_TYPE = "organization"


async def backfill() -> Dict[str, Any]:
    if not MONGO_URL:
        print("ERROR: MONGO_URL not set")
        sys.exit(1)

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    coll = db.decider_store_templates
    total = await coll.count_documents({})
    print(f"→ {total} docs in decider_store_templates")

    fixed_life_area = 0
    fixed_org_types = 0
    fixed_pub_type = 0
    fixed_is_free = 0
    fixed_factor_count = 0
    fixed_option_count = 0
    fixed_rating = 0
    fixed_official = 0
    per_doc_summary: List[Dict[str, Any]] = []

    async for d in coll.find({}):
        tid = d.get("template_id")
        title = d.get("title") or d.get("id") or tid or "(no id)"
        updates: Dict[str, Any] = {}
        touched: List[str] = []

        # life_area
        if not d.get("life_area"):
            updates["life_area"] = DEFAULT_LIFE_AREA
            touched.append("life_area")
            fixed_life_area += 1

        # applicable_org_types — always non-empty list
        cur_org = d.get("applicable_org_types")
        if not isinstance(cur_org, list) or len(cur_org) == 0:
            updates["applicable_org_types"] = DEFAULT_ORG_TYPES
            touched.append("applicable_org_types")
            fixed_org_types += 1

        # publisher_type
        if d.get("publisher_type") not in ("individual", "expert", "organization"):
            updates["publisher_type"] = DEFAULT_PUBLISHER_TYPE
            touched.append("publisher_type")
            fixed_pub_type += 1

        # is_free — mirror from pricing_type so legacy readers keep working
        pricing = str(d.get("pricing_type") or "free").lower()
        is_free_actual = pricing == "free" or (int(d.get("price_paise") or 0) == 0)
        if d.get("is_free") is not is_free_actual:
            updates["is_free"] = is_free_actual
            touched.append("is_free")
            fixed_is_free += 1

        # factor_count — take max(existing, len(factors))
        embed_factors = d.get("factors") or []
        fc_new = max(int(d.get("factor_count") or 0), len(embed_factors))
        if int(d.get("factor_count") or 0) != fc_new:
            updates["factor_count"] = fc_new
            touched.append("factor_count")
            fixed_factor_count += 1

        # option_count — take max(existing, len(options))
        embed_options = d.get("options") or []
        oc_new = max(int(d.get("option_count") or 0), len(embed_options))
        if int(d.get("option_count") or 0) != oc_new:
            updates["option_count"] = oc_new
            touched.append("option_count")
            fixed_option_count += 1

        # rating_avg / rating_count — default 0 so min-filter comparisons work
        rating_touched = False
        if d.get("rating_avg") is None:
            updates["rating_avg"] = 0.0
            rating_touched = True
        if d.get("rating_count") is None:
            updates["rating_count"] = 0
            rating_touched = True
        if rating_touched:
            touched.append("rating_avg|count")
            fixed_rating += 1

        # is_official / is_approved — defaults for founder pack and Business
        # Model Chooser (both are "authorized").
        status = str(d.get("status") or "").lower()
        if d.get("is_official") is None:
            updates["is_official"] = status == "authorized"
            touched.append("is_official")
            fixed_official += 1
        if d.get("is_approved") is None:
            updates["is_approved"] = status == "authorized"
            touched.append("is_approved")

        if updates:
            await coll.update_one({"template_id": tid}, {"$set": updates})
            per_doc_summary.append({"id": tid, "title": title, "fixed": touched})

    result = {
        "total_docs": total,
        "fields_backfilled": {
            "life_area": fixed_life_area,
            "applicable_org_types": fixed_org_types,
            "publisher_type": fixed_pub_type,
            "is_free": fixed_is_free,
            "factor_count": fixed_factor_count,
            "option_count": fixed_option_count,
            "rating_avg_count": fixed_rating,
            "is_official": fixed_official,
        },
        "changed_docs": per_doc_summary,
    }
    return result


async def verify_filters() -> Dict[str, Any]:
    """Run each filter query the frontend uses and confirm result counts."""
    if not MONGO_URL:
        return {}
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    coll = db.decider_store_templates

    checks = {
        "total": await coll.count_documents({}),
        "life_area=Business & Career": await coll.count_documents(
            {"life_area": {"$regex": "^Business & Career$", "$options": "i"}}
        ),
        "org_types has Startup": await coll.count_documents(
            {"applicable_org_types": {"$in": ["Startup"]}}
        ),
        "org_types has MSME": await coll.count_documents(
            {"applicable_org_types": {"$in": ["MSME"]}}
        ),
        "org_types has Solopreneur": await coll.count_documents(
            {"applicable_org_types": {"$in": ["Solopreneur"]}}
        ),
        "publisher_type=organization": await coll.count_documents(
            {"publisher_type": "organization"}
        ),
        "pricing_type=free": await coll.count_documents({"pricing_type": "free"}),
        "kind=app": await coll.count_documents({"kind": "app"}),
        "kind=template": await coll.count_documents({"kind": {"$ne": "app"}}),
        "rating_avg >= 0": await coll.count_documents({"rating_avg": {"$gte": 0}}),
    }
    return checks


async def main():
    result = await backfill()
    print("\n" + "=" * 60)
    print("BACKFILL COMPLETE")
    print("=" * 60)
    for k, v in result["fields_backfilled"].items():
        print(f"  {k:<28} {v} docs updated")

    print("\nPer-doc changes:")
    for row in result["changed_docs"]:
        fields = ", ".join(row["fixed"])
        print(f"  • {row['title'][:50]:<52} → {fields}")

    print("\n" + "=" * 60)
    print("FILTER VERIFICATION (post-backfill counts)")
    print("=" * 60)
    checks = await verify_filters()
    for k, v in checks.items():
        print(f"  {k:<40} {v}")


if __name__ == "__main__":
    asyncio.run(main())
