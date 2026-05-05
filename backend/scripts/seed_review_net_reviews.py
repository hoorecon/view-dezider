"""
Seed sample reviews on top demo solutions so the ReviewNet aggregates UI
has rich data without needing manual entry.

Idempotent: each seed review carries a `seed_key`; re-running this script
will skip rows that already exist.

Picks: 8 high-visibility solutions
  - 3 time-saver SKUs (Urban Company, BigBasket, FreshMenu)
  - 1 wellness (Cult.fit)
  - 1 Apollo health checkup
  - 1 LinkedIn Premium
  - 1 SBI Home Loan
  - 1 HDFC Mutual Fund

For each → 4-6 reviews mixing segments (individual + org + government)
and statuses (approved + auto_approved) so per-segment aggregates have
content. Ratings vary 3-5 to mimic realistic distribution.

Usage:
  python /app/backend/scripts/seed_review_net_reviews.py
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from core.database import db  # noqa: E402


# --------------------------- pickers ---------------------------------------
TARGETS_BY_SLUG = [
    # name-substring → expected number of reviews
    ("Urban Company", 6),
    ("BigBasket", 5),
    ("FreshMenu", 5),
    ("Cult.fit Chennai", 6),
    ("Apollo Hospitals — Master Health Checkup", 5),
    ("LinkedIn Premium", 5),
    ("SBI Home Loan", 5),
    ("HDFC Mid-Cap Opportunities", 4),
]

# fixture reviewers — synthetic identities with seed_user_id so they never
# collide with real users
REVIEWER_POOL = [
    # individuals — customers
    {"name": "Priya Ramesh",    "segment": "individual",   "subsegment": "customer", "verified": True},
    {"name": "Arjun Mehta",     "segment": "individual",   "subsegment": "customer", "verified": True},
    {"name": "Sneha Iyer",      "segment": "individual",   "subsegment": "customer", "verified": False},
    {"name": "Karthik Subramanian","segment": "individual","subsegment": "expert",   "verified": False},
    {"name": "Divya Nair",      "segment": "individual",   "subsegment": "observer", "verified": False},
    {"name": "Rohit Khanna",    "segment": "individual",   "subsegment": "customer", "verified": True},
    # organizations
    {"name": "Acme Solutions Pvt Ltd",      "segment": "organization", "subsegment": "business_corporate",       "verified": True},
    {"name": "Anna University CSE Dept",    "segment": "organization", "subsegment": "educational_institution",  "verified": False},
    {"name": "Sustain Earth Foundation",    "segment": "organization", "subsegment": "ngo_nonprofit",            "verified": False},
    # government
    {"name": "RBI Consumer Protection Cell","segment": "government",   "subsegment": "regulator",                "verified": False},
    {"name": "Greater Chennai Corporation", "segment": "government",   "subsegment": "local_body",               "verified": False},
]

REVIEW_TEMPLATES = [
    # generic, segment-agnostic
    {"title": "Solid experience overall",   "comment": "Met expectations on most fronts. Minor friction on onboarding.", "ratings_avg": 4},
    {"title": "Highly recommended",         "comment": "Smooth, prompt, and the team was responsive throughout.",         "ratings_avg": 5},
    {"title": "Decent for the price",       "comment": "You get what you pay for. Service is fair, communication ok.",    "ratings_avg": 3},
    {"title": "Excellent professionalism",  "comment": "Very transparent on fees and timeline. Would use again.",         "ratings_avg": 5},
    {"title": "Mixed bag",                  "comment": "Good core service but follow-up could be tighter.",                "ratings_avg": 4},
    {"title": "Good value",                 "comment": "Worth it for the convenience. Minor delays once.",                 "ratings_avg": 4},
    {"title": "Could be better",            "comment": "Functional but felt rushed. Documentation should improve.",        "ratings_avg": 3},
    {"title": "Reliable choice",            "comment": "Consistent quality across multiple uses.",                          "ratings_avg": 5},
    {"title": "Onboarded smoothly",         "comment": "KYC and setup were quick. No surprises.",                          "ratings_avg": 4},
    {"title": "Solid governance",           "comment": "Compliant with industry norms; documentation matches reality.",     "ratings_avg": 5},
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stagger_date(idx: int) -> datetime:
    return _now() - timedelta(days=(idx + 1) * 3 + (idx % 4))


async def _resolve_factors_for(sol: dict) -> list[dict]:
    """Mirror the runtime resolver: global + life_area + sub_area + catalog_node ancestors."""
    factors_by_slug: dict[str, dict] = {}

    async def _collect(scope_type: str, scope_id):
        cur = db.review_factors.find(
            {"scope_type": scope_type, "scope_id": scope_id, "is_active": True},
            {"_id": 0},
        )
        async for f in cur:
            factors_by_slug.setdefault(f["slug"], f)

    await _collect("global", None)
    if sol.get("life_area_id"):
        await _collect("life_area", sol["life_area_id"])
    if sol.get("sub_area_id"):
        await _collect("sub_area", sol["sub_area_id"])
    if sol.get("catalog_node_id"):
        # walk up
        cur_id = sol["catalog_node_id"]
        while cur_id:
            n = await db.catalog_nodes.find_one({"node_id": cur_id}, {"_id": 0})
            if not n:
                break
            await _collect("catalog_node", n["node_id"])
            cur_id = n.get("parent_id")
    return list(factors_by_slug.values())


def _bucket_ratings(target_avg: int, factors: list[dict]) -> dict[str, int]:
    """Build ratings around the target average ±1 within 1..5."""
    if not factors:
        return {}
    out: dict[str, int] = {}
    for i, f in enumerate(factors[:5]):                  # cap at 5 factors / review
        delta = (-1 if i % 3 == 0 else 1 if i % 3 == 1 else 0)
        v = max(1, min(5, target_avg + delta))
        out[f["factor_id"]] = v
    return out


async def _ensure_indexes():
    await db.review_net.create_index("review_id", unique=True)
    await db.review_net.create_index("solution_id")
    await db.review_net.create_index("seed_key")


async def seed():
    await _ensure_indexes()

    # match solutions
    inserted = 0
    skipped = 0
    target_solutions: list[tuple[dict, int]] = []
    for slug, count in TARGETS_BY_SLUG:
        sol = await db.solutions_store.find_one({"name": {"$regex": slug, "$options": "i"}}, {"_id": 0})
        if sol:
            target_solutions.append((sol, count))
        else:
            print(f"[seed_review_net_reviews] SKIP — no solution matching '{slug}'")

    if not target_solutions:
        print("Nothing to do.")
        return

    for sol, count in target_solutions:
        factors = await _resolve_factors_for(sol)
        if not factors:
            print(f"  [skip] {sol.get('name')}: no factors resolved")
            continue

        for idx in range(count):
            template = REVIEW_TEMPLATES[(hash(sol["solution_id"]) + idx) % len(REVIEW_TEMPLATES)]
            reviewer = REVIEWER_POOL[idx % len(REVIEWER_POOL)]
            seed_key = f"rn_seed::{sol['solution_id']}::{idx}"

            existing = await db.review_net.find_one({"seed_key": seed_key}, {"_id": 1})
            if existing:
                skipped += 1
                continue

            ratings = _bucket_ratings(template["ratings_avg"], factors)
            avg = sum(ratings.values()) / len(ratings) if ratings else 0
            review_id = f"rv_{uuid.uuid4().hex[:14]}"

            doc = {
                "review_id": review_id,
                "seed_key": seed_key,
                "solution_id": sol["solution_id"],
                "solution_name": sol.get("name"),
                "catalog_node_id": sol.get("catalog_node_id"),
                "reviewer_id": f"seed_user_{abs(hash(reviewer['name'])) % 100000}",
                "reviewer_name": reviewer["name"],
                "reviewer_segment": reviewer["segment"],
                "reviewer_subsegment": reviewer["subsegment"],
                "factor_ratings": ratings,
                "overall_rating": round(avg, 2),
                "title": template["title"],
                "comment": template["comment"],
                "is_verified_buyer": reviewer["verified"],
                # alternate between auto_approved and approved so both surfaces are populated
                "status": "auto_approved" if idx % 2 == 0 else "approved",
                "moderation_action": "AUTO_APPROVE" if idx % 2 == 0 else "approve",
                "moderation_note": "Seed data — pre-published",
                "moderated_by": "system_seed",
                "matched_rule_id": None,
                "matched_rule_name": None,
                "helpful_yes_count": (idx * 3) % 17,
                "helpful_no_count": (idx * 1) % 4,
                "owner_reply": None,
                "created_at": _stagger_date(idx),
                "updated_at": _stagger_date(idx),
            }
            await db.review_net.insert_one(doc)
            inserted += 1

    total = await db.review_net.count_documents({})
    seeded_total = await db.review_net.count_documents({"seed_key": {"$exists": True}})
    print(f"[seed_review_net_reviews] inserted: {inserted}, skipped(existing): {skipped}")
    print(f"[seed_review_net_reviews] total reviews in db: {total} (seed-tagged: {seeded_total})")


if __name__ == "__main__":
    asyncio.run(seed())
