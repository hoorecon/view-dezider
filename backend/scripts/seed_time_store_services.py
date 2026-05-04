"""
Seed / upgrade Solutions Store with Time Store metadata.

Adds `time_save_per_day_min` + `time_save_per_week_min` to existing
time-relevant solutions and inserts 8 new genuine time-saver services
(grocery delivery, home cleaning, laundry, tax filing, virtual assistant,
meal prep, chauffeur, accounting), all system-authorized so they appear
in the Time Store services tab without manual approval.

Idempotent:
  - Existing docs get $set updates (no duplicates).
  - New docs are upserted by a stable `seed_key`.

Usage:
  python /app/backend/scripts/seed_time_store_services.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Make /app/backend importable
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

load_dotenv(BACKEND_DIR / ".env")

from core.database import db  # noqa: E402


TIME_SAVE_PATCHES: list[dict] = [
    # name-substring match → patch
    {"match": "Cult.fit Chennai", "day": 20, "week": 120,
     "why": "Skip gym-prep + commute by using nearby centers or on-demand online classes."},
    {"match": "HDFC Mid-Cap Opportunities", "day": 0, "week": 60,
     "why": "Fund manager handles research you'd otherwise do yourself."},
    {"match": "LIC Jeevan Labh", "day": 0, "week": 30,
     "why": "Agent-managed renewals & paperwork."},
    {"match": "Coursera Plus", "day": 15, "week": 90,
     "why": "Pre-curated learning paths remove course-hunting time."},
    {"match": "LinkedIn Premium", "day": 20, "week": 140,
     "why": "InMail + search filters cut networking/outreach time."},
    {"match": "Isha Yoga", "day": 15, "week": 105,
     "why": "Structured practice replaces self-directed wellness planning."},
    {"match": "Apollo Hospitals — Master Health Checkup", "day": 0, "week": 30,
     "why": "One-stop package vs. booking 60+ tests individually."},
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base() -> dict:
    now = _now_iso()
    return {
        "visibility": "PUBLIC",
        "is_authorized": True,
        "approval_status": "approved",   # also satisfies the stricter filter
        "created_by": "system",
        "country": "IN", "state": "TN", "city": "Chennai", "language": "en",
        "currency": "INR", "status": "active",
        "created_at": now, "updated_at": now,
    }


NEW_SERVICES: list[dict] = [
    # ---- grocery delivery ----
    {
        "seed_key": "time_saver.bigbasket_chennai",
        "type": "SERVICE",
        "name": "BigBasket — Doorstep Grocery Delivery (Chennai)",
        "description": "Weekly grocery delivery with slot booking. Saves 2 grocery-run hours/week + driving time.",
        "life_area_id": "la_health", "sub_area_id": "sa_hlt_preventive",
        "provider": "BigBasket", "url": "https://www.bigbasket.com",
        "tags": ["grocery", "delivery", "time saver", "household", "Chennai"],
        "price_range": "Free above ₹600 order",
        "type_specific": {"duration": "2-hr slots", "frequency": "Weekly", "delivery_mode": "Home delivery"},
        "time_save_per_day_min": 20,
        "time_save_per_week_min": 120,
        "time_save_rationale": "Eliminates grocery-run + queue + drive time.",
        "price_inr": 0,
        "price_model": "per_order",
        "quantitative_factors": [
            {"factor_name": "Delivery Fee", "value": 0, "unit": "INR (above ₹600)", "data_type": "numeric"},
            {"factor_name": "Slot Variety", "value": 8, "unit": "slots/day", "data_type": "numeric"},
        ],
    },
    # ---- home cleaning ----
    {
        "seed_key": "time_saver.urbanclap_cleaning",
        "type": "SERVICE",
        "name": "Urban Company — Home Deep Cleaning",
        "description": "Professional home cleaners for 2BHK/3BHK. Weekly or monthly subscriptions.",
        "life_area_id": "la_assets", "sub_area_id": "sa_ast_home",
        "provider": "Urban Company", "url": "https://www.urbancompany.com",
        "tags": ["cleaning", "home services", "time saver", "household", "Chennai"],
        "price_range": "₹1,499 - ₹3,999/visit",
        "type_specific": {"duration": "3-5 hrs", "frequency": "Weekly/Monthly", "delivery_mode": "In-person"},
        "time_save_per_day_min": 25,
        "time_save_per_week_min": 180,
        "time_save_rationale": "Replaces 3 hrs self-cleaning per week.",
        "price_inr": 1999,
        "price_model": "per_visit",
        "quantitative_factors": [
            {"factor_name": "Per Visit Cost", "value": 1999, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "Coverage (sqft)", "value": 1200, "unit": "sqft", "data_type": "numeric"},
        ],
    },
    # ---- laundry ----
    {
        "seed_key": "time_saver.uclean_laundry",
        "type": "SERVICE",
        "name": "UClean — Subscription Laundry (Chennai)",
        "description": "Wash & iron laundry, doorstep pickup/drop, turnaround ≤ 48 hrs.",
        "life_area_id": "la_health", "sub_area_id": "sa_hlt_preventive",
        "provider": "UClean", "url": "https://uclean.in",
        "tags": ["laundry", "time saver", "household", "subscription", "Chennai"],
        "price_range": "₹99/kg or ₹1,499/month (50 kg)",
        "type_specific": {"duration": "48 hrs", "frequency": "Weekly", "delivery_mode": "Pickup + drop"},
        "time_save_per_day_min": 15,
        "time_save_per_week_min": 90,
        "time_save_rationale": "~1.5 hr/week wash + fold + iron.",
        "price_inr": 1499,
        "price_model": "monthly",
        "quantitative_factors": [
            {"factor_name": "Monthly Cost", "value": 1499, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "Kg Included", "value": 50, "unit": "kg", "data_type": "numeric"},
        ],
    },
    # ---- tax filing ----
    {
        "seed_key": "time_saver.cleartax_itr",
        "type": "SERVICE",
        "name": "ClearTax — ITR Filing (Assisted)",
        "description": "CA-assisted income tax return filing, investment-proof optimization included.",
        "life_area_id": "la_finance", "sub_area_id": "sa_fin_planning",
        "provider": "ClearTax", "url": "https://cleartax.in",
        "tags": ["tax filing", "ITR", "time saver", "finance"],
        "price_range": "₹499 - ₹3,999",
        "type_specific": {"duration": "48 hrs", "frequency": "Annual", "delivery_mode": "Online"},
        "time_save_per_day_min": 0,
        "time_save_per_week_min": 180,
        "time_save_rationale": "Saves ~6 hrs of form-filling & slab lookups (annualized).",
        "price_inr": 999,
        "price_model": "annual",
        "quantitative_factors": [
            {"factor_name": "Assisted Price", "value": 999, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "Turnaround", "value": 48, "unit": "hours", "data_type": "numeric"},
        ],
    },
    # ---- virtual assistant ----
    {
        "seed_key": "time_saver.wing_assistant",
        "type": "SERVICE",
        "name": "GetFriday — Virtual Assistant (Part-time)",
        "description": "Remote assistant for scheduling, travel, research, inbox-zero. 20 hrs/month.",
        "life_area_id": "la_career", "sub_area_id": "sa_car_skill",
        "provider": "GetFriday", "url": "https://www.getfriday.com",
        "tags": ["virtual assistant", "VA", "time saver", "outsource"],
        "price_range": "₹7,999 - ₹24,999/month",
        "type_specific": {"duration": "20 hrs/month", "frequency": "Monthly", "delivery_mode": "Remote"},
        "time_save_per_day_min": 30,
        "time_save_per_week_min": 300,
        "time_save_rationale": "Delegates admin + research (~5 hrs/week).",
        "price_inr": 9999,
        "price_model": "monthly",
        "quantitative_factors": [
            {"factor_name": "Monthly Cost", "value": 9999, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "Hours Included", "value": 20, "unit": "hrs", "data_type": "numeric"},
        ],
    },
    # ---- meal prep ----
    {
        "seed_key": "time_saver.freshmenu_subscription",
        "type": "SERVICE",
        "name": "FreshMenu — Weekday Lunch Subscription",
        "description": "Chef-prepared lunch boxes delivered daily. Skips cooking + dish wash.",
        "life_area_id": "la_health", "sub_area_id": "sa_hlt_preventive",
        "provider": "FreshMenu", "url": "https://www.freshmenu.com",
        "tags": ["meal prep", "food delivery", "time saver", "Chennai"],
        "price_range": "₹149 - ₹249/meal or ₹2,999/month",
        "type_specific": {"duration": "Daily", "frequency": "Weekday", "delivery_mode": "Home/Office delivery"},
        "time_save_per_day_min": 40,
        "time_save_per_week_min": 280,
        "time_save_rationale": "Saves ~40 min/day in prep + cook + clean.",
        "price_inr": 2999,
        "price_model": "monthly",
        "quantitative_factors": [
            {"factor_name": "Monthly Cost", "value": 2999, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "Meals Included", "value": 20, "unit": "meals", "data_type": "numeric"},
        ],
    },
    # ---- chauffeur ----
    {
        "seed_key": "time_saver.drivezy_chauffeur",
        "type": "SERVICE",
        "name": "DriveU — On-demand Chauffeur (Chennai)",
        "description": "Book a driver for your own car. Weekday commute or occasional long drives.",
        "life_area_id": "la_assets", "sub_area_id": "sa_ast_vehicle",
        "provider": "DriveU", "url": "https://www.driveu.in",
        "tags": ["chauffeur", "driver", "time saver", "commute", "Chennai"],
        "price_range": "₹149/hour, min 2 hrs",
        "type_specific": {"duration": "On-demand", "frequency": "Flexible", "delivery_mode": "In-person"},
        "time_save_per_day_min": 45,
        "time_save_per_week_min": 225,
        "time_save_rationale": "Reclaim commute time for calls/reading (~45 min/day).",
        "price_inr": 149,
        "price_model": "per_hour",
        "quantitative_factors": [
            {"factor_name": "Hourly Rate", "value": 149, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "Minimum Booking", "value": 2, "unit": "hrs", "data_type": "numeric"},
        ],
    },
    # ---- accounting ----
    {
        "seed_key": "time_saver.zoho_books_bookkeeping",
        "type": "SERVICE",
        "name": "Zoho Books — Monthly Bookkeeping",
        "description": "CA-managed bookkeeping + GST + invoicing for small businesses & professionals.",
        "life_area_id": "la_finance", "sub_area_id": "sa_fin_planning",
        "provider": "Zoho Books", "url": "https://www.zoho.com/in/books/",
        "tags": ["bookkeeping", "GST", "accounting", "time saver", "business"],
        "price_range": "₹2,499 - ₹9,999/month",
        "type_specific": {"duration": "Monthly", "frequency": "Ongoing", "delivery_mode": "Remote"},
        "time_save_per_day_min": 20,
        "time_save_per_week_min": 140,
        "time_save_rationale": "Removes ~2 hrs/week of invoice + GST reconciliation.",
        "price_inr": 2499,
        "price_model": "monthly",
        "quantitative_factors": [
            {"factor_name": "Monthly Cost", "value": 2499, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "Transactions Included", "value": 100, "unit": "/month", "data_type": "numeric"},
        ],
    },
]


async def run():
    patched = 0
    for patch in TIME_SAVE_PATCHES:
        res = await db.solutions_store.update_many(
            {
                "name": {"$regex": patch["match"], "$options": "i"},
                "is_authorized": True,
            },
            {"$set": {
                "time_save_per_day_min": patch["day"],
                "time_save_per_week_min": patch["week"],
                "time_save_rationale": patch.get("why"),
                "updated_at": _now_iso(),
            }},
        )
        patched += res.modified_count

    upserts = 0
    for svc in NEW_SERVICES:
        seed_key = svc["seed_key"]
        existing = await db.solutions_store.find_one({"seed_key": seed_key}, {"_id": 1})
        doc = {**_base(), **svc}
        if "solution_id" not in doc:
            doc["solution_id"] = str(uuid.uuid4()) if not existing else None
        if existing:
            doc.pop("solution_id", None)  # don't overwrite the original uuid
            doc["updated_at"] = _now_iso()
            await db.solutions_store.update_one({"seed_key": seed_key}, {"$set": doc})
        else:
            doc["solution_id"] = doc.get("solution_id") or str(uuid.uuid4())
            await db.solutions_store.insert_one(doc)
            upserts += 1

    total_with_time_save = await db.solutions_store.count_documents(
        {"time_save_per_day_min": {"$exists": True}}
    )

    print(f"[seed_time_store_services] existing patched: {patched}")
    print(f"[seed_time_store_services] new inserted:     {upserts}")
    print(f"[seed_time_store_services] total with time_save_per_day_min: {total_with_time_save}")


if __name__ == "__main__":
    asyncio.run(run())
