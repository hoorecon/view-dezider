"""
Solutions Store & ReviewNet — Backend Routes
Products, Services, Events, Projects, People organized under HOS hierarchy
with quantitative factors (Store) and qualitative reviews (ReviewNet).
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from core.auth import get_current_user
from core.database import db

router = APIRouter()

# ================================================================
# CONSTANTS
# ================================================================
SOLUTION_TYPES = ["PRODUCT", "SERVICE", "EVENT", "PROJECT", "PERSON_CONTACT"]
VISIBILITY_LEVELS = ["PRIVATE", "ORG", "PUBLIC"]

# Type-specific field definitions
TYPE_SPECIFIC_FIELDS = {
    "PRODUCT": ["brand", "model", "warranty_months", "specifications", "sku"],
    "SERVICE": ["duration", "frequency", "delivery_mode", "availability"],
    "EVENT": ["event_date", "event_end_date", "location", "venue", "capacity", "registration_url"],
    "PROJECT": ["timeline_months", "team_size", "budget", "milestones"],
    "PERSON_CONTACT": ["phone", "email", "designation", "organization", "expertise"],
}

# Default qualitative factor names for ReviewNet
DEFAULT_QUALITATIVE_FACTORS = [
    "Trustworthiness",
    "Quality",
    "Reliability",
    "Value for Money",
    "User Experience",
    "Customer Support",
    "Innovation",
    "Accessibility",
]


# ================================================================
# SOLUTIONS STORE ENDPOINTS
# ================================================================

@router.post("/solutions-store/solutions")
async def create_solution(request: Request, user: dict = Depends(get_current_user)):
    """Create a new solution in the store."""
    body = await request.json()

    sol_type = body.get("type", "").upper()
    if sol_type not in SOLUTION_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type. Must be one of: {SOLUTION_TYPES}")

    visibility = body.get("visibility", "PRIVATE").upper()
    if visibility not in VISIBILITY_LEVELS:
        raise HTTPException(status_code=400, detail=f"Invalid visibility. Must be one of: {VISIBILITY_LEVELS}")

    # Only admins can create PUBLIC (authorized) solutions
    is_authorized = False
    if visibility == "PUBLIC":
        user_role = user.get("role", "")
        org_role = user.get("org_role", "")
        if user_role not in ["super_admin", "co_admin", "admin"] and org_role not in ["org_super_admin", "org_co_admin"]:
            raise HTTPException(status_code=403, detail="Only admins can create public/authorized solutions")
        is_authorized = True

    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Solution name is required")

    # Extract type-specific fields
    type_specific = {}
    for field in TYPE_SPECIFIC_FIELDS.get(sol_type, []):
        if field in body:
            type_specific[field] = body[field]

    solution = {
        "solution_id": str(uuid.uuid4()),
        "type": sol_type,
        "name": name,
        "description": body.get("description", ""),
        "life_area_id": body.get("life_area_id"),
        "sub_area_id": body.get("sub_area_id"),
        "category_id": body.get("category_id"),
        "visibility": visibility,
        "created_by": user["user_id"],
        "org_id": user.get("org_id"),
        "is_authorized": is_authorized,
        "country": body.get("country", "IN"),
        "state": body.get("state", ""),
        "city": body.get("city", ""),
        "language": body.get("language", "en"),
        "provider": body.get("provider", ""),
        "url": body.get("url", ""),
        "image_url": body.get("image_url", ""),
        "tags": body.get("tags", []),
        "price_range": body.get("price_range", ""),
        "currency": body.get("currency", "INR"),
        "type_specific": type_specific,
        "quantitative_factors": body.get("quantitative_factors", []),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.solutions_store.insert_one(solution)
    solution.pop("_id", None)
    return solution


@router.get("/solutions-store/solutions")
async def list_solutions(
    request: Request,
    type: Optional[str] = None,
    life_area_id: Optional[str] = None,
    sub_area_id: Optional[str] = None,
    category_id: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    visibility: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """List solutions visible to the user (own + org + authorized/public)."""
    query = {"status": "active"}

    # Visibility filter: user sees own PRIVATE + own ORG + all PUBLIC
    vis_filter = [
        {"created_by": user["user_id"]},
        {"is_authorized": True},
    ]
    if user.get("org_id"):
        vis_filter.append({"visibility": "ORG", "org_id": user["org_id"]})
    query["$or"] = vis_filter

    if type:
        query["type"] = type.upper()
    if life_area_id:
        query["life_area_id"] = life_area_id
    if sub_area_id:
        query["sub_area_id"] = sub_area_id
    if category_id:
        query["category_id"] = category_id
    if country:
        query["country"] = country
    if city:
        query["city"] = {"$regex": city, "$options": "i"}

    solutions = await db.solutions_store.find(query, {"_id": 0}).sort("name", 1).to_list(500)

    # Attach review summary for each solution
    for sol in solutions:
        review_agg = await db.solution_reviews.aggregate([
            {"$match": {"solution_id": sol["solution_id"]}},
            {"$group": {
                "_id": None,
                "avg_rating": {"$avg": "$overall_rating"},
                "review_count": {"$sum": 1},
            }}
        ]).to_list(1)
        if review_agg:
            sol["avg_rating"] = round(review_agg[0]["avg_rating"], 1)
            sol["review_count"] = review_agg[0]["review_count"]
        else:
            sol["avg_rating"] = None
            sol["review_count"] = 0

    return solutions


@router.get("/solutions-store/solutions/{solution_id}")
async def get_solution_detail(solution_id: str, user: dict = Depends(get_current_user)):
    """Get full solution detail with quantitative factors and review summary."""
    sol = await db.solutions_store.find_one({"solution_id": solution_id, "status": "active"}, {"_id": 0})
    if not sol:
        raise HTTPException(status_code=404, detail="Solution not found")

    # Check visibility
    can_see = (
        sol.get("is_authorized")
        or sol.get("created_by") == user["user_id"]
        or (sol.get("visibility") == "ORG" and sol.get("org_id") == user.get("org_id"))
    )
    if not can_see:
        raise HTTPException(status_code=403, detail="Not authorized to view this solution")

    # Attach reviews
    reviews = await db.solution_reviews.find(
        {"solution_id": solution_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    sol["reviews"] = reviews

    # Compute aggregated qualitative scores
    if reviews:
        factor_scores = {}
        for rev in reviews:
            for qf in rev.get("qualitative_factors", []):
                fname = qf.get("factor_name", "")
                if fname:
                    factor_scores.setdefault(fname, [])
                    factor_scores[fname].append(qf.get("rating", 0))

        sol["quality_scores"] = [
            {"factor_name": k, "avg_rating": round(sum(v) / len(v), 1), "review_count": len(v)}
            for k, v in factor_scores.items()
        ]
        sol["overall_avg_rating"] = round(
            sum(r.get("overall_rating", 0) for r in reviews) / len(reviews), 1
        )
    else:
        sol["quality_scores"] = []
        sol["overall_avg_rating"] = None

    return sol


@router.put("/solutions-store/solutions/{solution_id}")
async def update_solution(solution_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Update a solution (owner or admin only)."""
    sol = await db.solutions_store.find_one({"solution_id": solution_id})
    if not sol:
        raise HTTPException(status_code=404, detail="Solution not found")

    if sol["created_by"] != user["user_id"] and user.get("role") not in ["super_admin", "co_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized to update this solution")

    body = await request.json()
    updates = {}
    for field in ["name", "description", "provider", "url", "image_url", "tags",
                   "price_range", "currency", "country", "state", "city", "language",
                   "quantitative_factors", "life_area_id", "sub_area_id", "category_id",
                   "visibility", "type_specific", "status"]:
        if field in body:
            updates[field] = body[field]
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.solutions_store.update_one({"solution_id": solution_id}, {"$set": updates})
    return {"message": "Solution updated", "solution_id": solution_id}


@router.delete("/solutions-store/solutions/{solution_id}")
async def delete_solution(solution_id: str, user: dict = Depends(get_current_user)):
    """Soft-delete a solution."""
    sol = await db.solutions_store.find_one({"solution_id": solution_id})
    if not sol:
        raise HTTPException(status_code=404, detail="Solution not found")
    if sol["created_by"] != user["user_id"] and user.get("role") not in ["super_admin", "co_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    await db.solutions_store.update_one(
        {"solution_id": solution_id},
        {"$set": {"status": "inactive", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "Solution deleted", "solution_id": solution_id}


@router.get("/solutions-store/browse")
async def browse_solutions_by_hierarchy(
    life_area_id: Optional[str] = None,
    sub_area_id: Optional[str] = None,
    type: Optional[str] = None,
    country: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """Browse solutions organized by the HOS hierarchy."""
    query = {"status": "active"}
    vis_filter = [{"created_by": user["user_id"]}, {"is_authorized": True}]
    if user.get("org_id"):
        vis_filter.append({"visibility": "ORG", "org_id": user["org_id"]})
    query["$or"] = vis_filter

    if life_area_id:
        query["life_area_id"] = life_area_id
    if sub_area_id:
        query["sub_area_id"] = sub_area_id
    if type:
        query["type"] = type.upper()
    if country:
        query["country"] = country

    solutions = await db.solutions_store.find(query, {"_id": 0}).sort("name", 1).to_list(200)

    # Group by sub_area
    grouped = {}
    for sol in solutions:
        sa = sol.get("sub_area_id", "uncategorized")
        grouped.setdefault(sa, [])
        grouped[sa].append(sol)

    # Get sub-area names
    if life_area_id:
        sub_areas = await db.hos_sub_areas.find(
            {"life_area_id": life_area_id}, {"_id": 0}
        ).sort("order", 1).to_list(100)
    else:
        sub_areas = []

    return {
        "solutions": solutions,
        "grouped_by_sub_area": grouped,
        "sub_areas": sub_areas,
        "total": len(solutions),
    }


@router.get("/solutions-store/search")
async def search_solutions(
    q: str = Query(..., min_length=2),
    type: Optional[str] = None,
    country: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """Full-text search across solutions."""
    query = {"status": "active", "$text": {"$search": q}}
    vis_filter = [{"created_by": user["user_id"]}, {"is_authorized": True}]
    if user.get("org_id"):
        vis_filter.append({"visibility": "ORG", "org_id": user["org_id"]})
    query["$or"] = vis_filter

    if type:
        query["type"] = type.upper()
    if country:
        query["country"] = country

    solutions = await db.solutions_store.find(
        query, {"_id": 0, "score": {"$meta": "textScore"}}
    ).sort([("score", {"$meta": "textScore"})]).to_list(50)

    return {"results": solutions, "query": q, "total": len(solutions)}


@router.get("/solutions-store/for-decision")
async def get_solutions_for_decision(
    life_area_id: str = Query(...),
    sub_area_id: Optional[str] = None,
    ask_type_id: Optional[str] = None,
    type: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """Get solutions relevant to a decision context — used during 'Add Options'."""
    query = {"status": "active", "life_area_id": life_area_id}
    vis_filter = [{"created_by": user["user_id"]}, {"is_authorized": True}]
    if user.get("org_id"):
        vis_filter.append({"visibility": "ORG", "org_id": user["org_id"]})
    query["$or"] = vis_filter

    if sub_area_id:
        query["sub_area_id"] = sub_area_id
    if type:
        query["type"] = type.upper()

    solutions = await db.solutions_store.find(query, {"_id": 0}).sort("name", 1).to_list(100)

    # Attach quick review summary
    for sol in solutions:
        agg = await db.solution_reviews.aggregate([
            {"$match": {"solution_id": sol["solution_id"]}},
            {"$group": {"_id": None, "avg": {"$avg": "$overall_rating"}, "cnt": {"$sum": 1}}}
        ]).to_list(1)
        sol["avg_rating"] = round(agg[0]["avg"], 1) if agg else None
        sol["review_count"] = agg[0]["cnt"] if agg else 0

    return {"solutions": solutions, "total": len(solutions)}


@router.post("/solutions-store/apply-to-option")
async def apply_solution_to_option(request: Request, user: dict = Depends(get_current_user)):
    """
    When user selects a solution as a decision option,
    return its quantitative factors + aggregated qualitative scores
    ready to populate the factor-option matrix.
    """
    body = await request.json()
    solution_id = body.get("solution_id")
    if not solution_id:
        raise HTTPException(status_code=400, detail="solution_id required")

    sol = await db.solutions_store.find_one({"solution_id": solution_id, "status": "active"}, {"_id": 0})
    if not sol:
        raise HTTPException(status_code=404, detail="Solution not found")

    # Get quantitative factors
    quant_factors = sol.get("quantitative_factors", [])

    # Get aggregated qualitative scores
    reviews = await db.solution_reviews.find({"solution_id": solution_id}, {"_id": 0}).to_list(100)
    qual_scores = {}
    for rev in reviews:
        for qf in rev.get("qualitative_factors", []):
            fname = qf.get("factor_name", "")
            if fname:
                qual_scores.setdefault(fname, [])
                qual_scores[fname].append(qf.get("rating", 0))

    qualitative_factors = [
        {"factor_name": k, "avg_rating": round(sum(v) / len(v), 1), "review_count": len(v)}
        for k, v in qual_scores.items()
    ]

    return {
        "solution_id": solution_id,
        "solution_name": sol.get("name"),
        "solution_type": sol.get("type"),
        "quantitative_factors": quant_factors,
        "qualitative_factors": qualitative_factors,
        "overall_avg_rating": round(sum(r.get("overall_rating", 0) for r in reviews) / len(reviews), 1) if reviews else None,
        "price_range": sol.get("price_range"),
        "provider": sol.get("provider"),
    }


# ================================================================
# REVIEWNET ENDPOINTS
# ================================================================

@router.post("/reviewnet/reviews")
async def create_review(request: Request, user: dict = Depends(get_current_user)):
    """Add a qualitative review for a solution."""
    body = await request.json()
    solution_id = body.get("solution_id")
    if not solution_id:
        raise HTTPException(status_code=400, detail="solution_id required")

    sol = await db.solutions_store.find_one({"solution_id": solution_id, "status": "active"})
    if not sol:
        raise HTTPException(status_code=404, detail="Solution not found")

    # Check for duplicate review
    existing = await db.solution_reviews.find_one({
        "solution_id": solution_id, "reviewer_id": user["user_id"]
    })
    if existing:
        raise HTTPException(status_code=409, detail="You have already reviewed this solution. Use PUT to update.")

    qualitative_factors = body.get("qualitative_factors", [])
    overall_rating = body.get("overall_rating")

    # Auto-calculate overall if not provided
    if not overall_rating and qualitative_factors:
        ratings = [qf.get("rating", 0) for qf in qualitative_factors if qf.get("rating")]
        overall_rating = round(sum(ratings) / len(ratings), 1) if ratings else 5.0

    review = {
        "review_id": str(uuid.uuid4()),
        "solution_id": solution_id,
        "reviewer_id": user["user_id"],
        "reviewer_name": user.get("name", "Anonymous"),
        "qualitative_factors": qualitative_factors,
        "overall_rating": overall_rating or 5.0,
        "review_text": body.get("review_text", ""),
        "pros": body.get("pros", []),
        "cons": body.get("cons", []),
        "verified": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.solution_reviews.insert_one(review)
    review.pop("_id", None)
    return review


@router.get("/reviewnet/reviews")
async def list_reviews(
    solution_id: str = Query(...),
    user: dict = Depends(get_current_user),
):
    """Get all reviews for a solution."""
    reviews = await db.solution_reviews.find(
        {"solution_id": solution_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)

    # Compute aggregated scores
    factor_scores = {}
    for rev in reviews:
        for qf in rev.get("qualitative_factors", []):
            fname = qf.get("factor_name", "")
            if fname:
                factor_scores.setdefault(fname, [])
                factor_scores[fname].append(qf.get("rating", 0))

    aggregated = [
        {"factor_name": k, "avg_rating": round(sum(v) / len(v), 1), "review_count": len(v)}
        for k, v in factor_scores.items()
    ]

    overall = round(
        sum(r.get("overall_rating", 0) for r in reviews) / len(reviews), 1
    ) if reviews else None

    return {
        "reviews": reviews,
        "aggregated_scores": aggregated,
        "overall_avg_rating": overall,
        "total_reviews": len(reviews),
    }


@router.put("/reviewnet/reviews/{review_id}")
async def update_review(review_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Update own review."""
    review = await db.solution_reviews.find_one({"review_id": review_id})
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review["reviewer_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Can only update your own review")

    body = await request.json()
    updates = {}
    for field in ["qualitative_factors", "overall_rating", "review_text", "pros", "cons"]:
        if field in body:
            updates[field] = body[field]
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.solution_reviews.update_one({"review_id": review_id}, {"$set": updates})
    return {"message": "Review updated", "review_id": review_id}


@router.delete("/reviewnet/reviews/{review_id}")
async def delete_review(review_id: str, user: dict = Depends(get_current_user)):
    """Delete own review."""
    review = await db.solution_reviews.find_one({"review_id": review_id})
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review["reviewer_id"] != user["user_id"] and user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    await db.solution_reviews.delete_one({"review_id": review_id})
    return {"message": "Review deleted", "review_id": review_id}


@router.get("/reviewnet/qualitative-factors")
async def get_default_qualitative_factors(user: dict = Depends(get_current_user)):
    """Return the default qualitative factor names for reviews."""
    return {"factors": DEFAULT_QUALITATIVE_FACTORS}


# ================================================================
# SEED DATA — Chennai, TN, India Context
# ================================================================

@router.post("/solutions-store/seed")
async def seed_solutions_store(force: bool = False):
    """Seed the solutions store with Chennai-context authorized solutions."""
    existing = await db.solutions_store.count_documents({"is_authorized": True})
    if existing > 0 and not force:
        return {"message": "Solutions already seeded", "count": existing}

    if force:
        await db.solutions_store.delete_many({"is_authorized": True})
        await db.solution_reviews.delete_many({})

    now = datetime.now(timezone.utc).isoformat()
    base = {
        "visibility": "PUBLIC", "is_authorized": True, "created_by": "system",
        "country": "IN", "state": "TN", "city": "Chennai", "language": "en",
        "currency": "INR", "status": "active", "created_at": now, "updated_at": now,
    }

    solutions = [
        # ===== HEALTH — Products & Services =====
        {**base, "solution_id": str(uuid.uuid4()), "type": "SERVICE", "name": "Apollo Hospitals — Master Health Checkup",
         "description": "Comprehensive annual health checkup package at Apollo Hospitals, Greams Road, Chennai.",
         "life_area_id": "la_health", "sub_area_id": "sa_hlt_preventive", "category_id": None,
         "provider": "Apollo Hospitals", "url": "https://www.apollohospitals.com",
         "tags": ["health checkup", "hospital", "preventive", "Chennai"],
         "price_range": "₹3,500 - ₹12,000",
         "type_specific": {"duration": "4-6 hours", "frequency": "Annual", "delivery_mode": "In-person", "availability": "Mon-Sat"},
         "quantitative_factors": [
            {"factor_name": "Package Cost", "value": 5500, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "Tests Included", "value": 65, "unit": "count", "data_type": "numeric"},
            {"factor_name": "Report Turnaround", "value": 48, "unit": "hours", "data_type": "numeric"},
            {"factor_name": "Doctor Consultation", "value": 1, "unit": "included", "data_type": "boolean"},
         ]},
        {**base, "solution_id": str(uuid.uuid4()), "type": "SERVICE", "name": "Cult.fit Chennai — Fitness Membership",
         "description": "Group fitness classes (HIIT, yoga, dance) at multiple Cult.fit centers across Chennai.",
         "life_area_id": "la_health", "sub_area_id": "sa_hlt_fitness", "category_id": "cat_hlt_fitness",
         "provider": "Cult.fit", "url": "https://www.cult.fit",
         "tags": ["fitness", "gym", "yoga", "HIIT", "Chennai"],
         "price_range": "₹1,500 - ₹3,500/month",
         "type_specific": {"duration": "1 hour/session", "frequency": "Daily", "delivery_mode": "In-person & Online", "availability": "6AM-10PM"},
         "quantitative_factors": [
            {"factor_name": "Monthly Cost", "value": 2500, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "Centers in Chennai", "value": 12, "unit": "count", "data_type": "numeric"},
            {"factor_name": "Class Variety", "value": 8, "unit": "types", "data_type": "numeric"},
            {"factor_name": "Online Classes", "value": 1, "unit": "available", "data_type": "boolean"},
         ]},
        {**base, "solution_id": str(uuid.uuid4()), "type": "PERSON_CONTACT", "name": "Dr. Priya Ramesh — Clinical Psychologist",
         "description": "Senior clinical psychologist specializing in stress management, CBT, and work-life balance counseling.",
         "life_area_id": "la_health", "sub_area_id": "sa_hlt_mental", "category_id": "cat_hlt_stress",
         "provider": "Mind Matters Clinic", "tags": ["psychologist", "therapy", "CBT", "stress", "Chennai"],
         "price_range": "₹1,500 - ₹2,500/session",
         "type_specific": {"phone": "+91-XXXXXXXXXX", "email": "contact@mindmatters.in", "designation": "Senior Clinical Psychologist", "organization": "Mind Matters Clinic", "expertise": "CBT, Stress Management, Burnout Recovery"},
         "quantitative_factors": [
            {"factor_name": "Session Cost", "value": 2000, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "Experience", "value": 15, "unit": "years", "data_type": "numeric"},
            {"factor_name": "Online Sessions", "value": 1, "unit": "available", "data_type": "boolean"},
         ]},

        # ===== FINANCE — Products & Services =====
        {**base, "solution_id": str(uuid.uuid4()), "type": "PRODUCT", "name": "SBI Home Loan — Regular",
         "description": "State Bank of India home loan for salaried and self-employed individuals. Competitive rates.",
         "life_area_id": "la_finance", "sub_area_id": "sa_fin_debt", "category_id": "cat_fin_loan",
         "provider": "State Bank of India", "url": "https://www.sbi.co.in",
         "tags": ["home loan", "SBI", "mortgage", "bank", "Chennai"],
         "price_range": "8.50% - 9.85% p.a.",
         "type_specific": {"brand": "SBI", "model": "Regular Home Loan", "warranty_months": 0, "specifications": "Up to ₹5Cr, tenure 30 years"},
         "quantitative_factors": [
            {"factor_name": "Interest Rate", "value": 8.5, "unit": "%", "data_type": "numeric"},
            {"factor_name": "Max Tenure", "value": 30, "unit": "years", "data_type": "numeric"},
            {"factor_name": "Processing Fee", "value": 0.35, "unit": "%", "data_type": "numeric"},
            {"factor_name": "Max Loan Amount", "value": 50000000, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "Prepayment Penalty", "value": 0, "unit": "nil", "data_type": "numeric"},
         ]},
        {**base, "solution_id": str(uuid.uuid4()), "type": "PRODUCT", "name": "HDFC Mid-Cap Opportunities Fund",
         "description": "Equity mutual fund investing in mid-cap companies. Suitable for long-term wealth creation.",
         "life_area_id": "la_finance", "sub_area_id": "sa_fin_investments", "category_id": "cat_fin_mutual",
         "provider": "HDFC AMC", "url": "https://www.hdfcfund.com",
         "tags": ["mutual fund", "mid-cap", "equity", "SIP", "investment"],
         "price_range": "Min SIP ₹500/month",
         "type_specific": {"brand": "HDFC AMC", "model": "Mid-Cap Opportunities", "specifications": "Category: Mid Cap, Benchmark: Nifty Midcap 150"},
         "quantitative_factors": [
            {"factor_name": "3Y Return", "value": 22.5, "unit": "%", "data_type": "numeric"},
            {"factor_name": "5Y Return", "value": 18.3, "unit": "%", "data_type": "numeric"},
            {"factor_name": "Expense Ratio", "value": 1.62, "unit": "%", "data_type": "numeric"},
            {"factor_name": "Min SIP", "value": 500, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "AUM", "value": 45000, "unit": "Cr INR", "data_type": "numeric"},
         ]},
        {**base, "solution_id": str(uuid.uuid4()), "type": "SERVICE", "name": "LIC Jeevan Labh — Endowment Plan",
         "description": "LIC endowment plan combining insurance coverage with savings. Popular in Tamil Nadu.",
         "life_area_id": "la_finance", "sub_area_id": "sa_fin_risk", "category_id": "cat_fin_insurance",
         "provider": "Life Insurance Corporation", "url": "https://www.licindia.in",
         "tags": ["LIC", "insurance", "endowment", "life cover", "savings"],
         "price_range": "₹800 - ₹5,000/month premium",
         "type_specific": {"duration": "16-25 years", "frequency": "Monthly/Quarterly/Annual", "delivery_mode": "Agent + Online"},
         "quantitative_factors": [
            {"factor_name": "Sum Assured", "value": 1000000, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "Policy Term", "value": 16, "unit": "years", "data_type": "numeric"},
            {"factor_name": "Monthly Premium", "value": 2500, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "Maturity Bonus", "value": 25, "unit": "per 1000 SA", "data_type": "numeric"},
         ]},

        # ===== KNOWLEDGE — Courses & People =====
        {**base, "solution_id": str(uuid.uuid4()), "type": "SERVICE", "name": "IIT Madras — BS in Data Science (Online)",
         "description": "India's first online BSc in Programming & Data Science from IIT Madras. Flexible, affordable.",
         "life_area_id": "la_knowledge", "sub_area_id": "sa_kno_education", "category_id": "cat_kno_degree",
         "provider": "IIT Madras", "url": "https://onlinedegree.iitm.ac.in",
         "tags": ["IIT", "data science", "degree", "online", "Chennai"],
         "price_range": "₹15,000 - ₹25,000/term",
         "type_specific": {"duration": "3-6 years", "frequency": "Semester-based", "delivery_mode": "Online", "availability": "Open enrollment"},
         "quantitative_factors": [
            {"factor_name": "Total Cost", "value": 300000, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "Duration", "value": 3, "unit": "years (min)", "data_type": "numeric"},
            {"factor_name": "Courses", "value": 32, "unit": "count", "data_type": "numeric"},
            {"factor_name": "NIRF Ranking", "value": 1, "unit": "rank", "data_type": "numeric"},
         ]},
        {**base, "solution_id": str(uuid.uuid4()), "type": "SERVICE", "name": "Coursera Plus — Annual Subscription",
         "description": "Unlimited access to 7,000+ courses from top universities and companies.",
         "life_area_id": "la_knowledge", "sub_area_id": "sa_kno_skills", "category_id": "cat_kno_upskill",
         "provider": "Coursera", "url": "https://www.coursera.org",
         "tags": ["online course", "upskilling", "certificate", "coursera"],
         "price_range": "₹22,000 - ₹30,000/year",
         "type_specific": {"duration": "Annual", "frequency": "Self-paced", "delivery_mode": "Online", "availability": "24/7"},
         "quantitative_factors": [
            {"factor_name": "Annual Cost", "value": 25000, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "Courses Available", "value": 7000, "unit": "count", "data_type": "numeric"},
            {"factor_name": "Certificates Included", "value": 1, "unit": "unlimited", "data_type": "boolean"},
         ]},

        # ===== CAREER — Companies & Services =====
        {**base, "solution_id": str(uuid.uuid4()), "type": "SERVICE", "name": "Freshworks — Chennai Tech Careers",
         "description": "SaaS unicorn headquartered in Chennai. Engineering, product, and design roles.",
         "life_area_id": "la_career", "sub_area_id": "sa_car_job", "category_id": "cat_car_switch",
         "provider": "Freshworks", "url": "https://www.freshworks.com/careers",
         "tags": ["Freshworks", "SaaS", "tech jobs", "Chennai", "startup"],
         "price_range": "₹8L - ₹45L CTC",
         "type_specific": {"duration": "Full-time", "delivery_mode": "Hybrid (Chennai HQ)", "availability": "Open positions year-round"},
         "quantitative_factors": [
            {"factor_name": "Avg Salary (Mid)", "value": 1800000, "unit": "INR/year", "data_type": "numeric"},
            {"factor_name": "Employee Count", "value": 5500, "unit": "people", "data_type": "numeric"},
            {"factor_name": "Glassdoor Rating", "value": 3.8, "unit": "/5", "data_type": "numeric"},
         ]},

        # ===== ASSETS — Real Estate =====
        {**base, "solution_id": str(uuid.uuid4()), "type": "PRODUCT", "name": "Casagrand — 2BHK Apartments, OMR",
         "description": "Premium 2BHK apartments along IT corridor OMR. Amenities include clubhouse, gym, pool.",
         "life_area_id": "la_assets", "sub_area_id": "sa_ast_home", "category_id": "cat_ast_home",
         "provider": "Casagrand", "url": "https://www.casagrand.co.in",
         "tags": ["apartment", "2BHK", "OMR", "Chennai", "real estate"],
         "price_range": "₹65L - ₹1.2Cr",
         "type_specific": {"brand": "Casagrand", "model": "2BHK Premium", "specifications": "850-1200 sqft, Gated community, RERA approved"},
         "quantitative_factors": [
            {"factor_name": "Price per Sqft", "value": 7500, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "Carpet Area", "value": 950, "unit": "sqft", "data_type": "numeric"},
            {"factor_name": "Amenities", "value": 25, "unit": "count", "data_type": "numeric"},
            {"factor_name": "Distance to IT Park", "value": 3, "unit": "km", "data_type": "numeric"},
         ]},

        # ===== HOBBIES — Experiences =====
        {**base, "solution_id": str(uuid.uuid4()), "type": "EVENT", "name": "Chennai Book Fair 2026",
         "description": "Annual book fair at YMCA Grounds, Nandanam. 800+ publishers, special author sessions.",
         "life_area_id": "la_hobbies", "sub_area_id": "sa_hob_personal", "category_id": "cat_hob_choose",
         "provider": "BAPASI", "tags": ["book fair", "Chennai", "books", "reading", "event"],
         "price_range": "₹20 entry",
         "type_specific": {"event_date": "2026-01-10", "event_end_date": "2026-01-25", "location": "Chennai", "venue": "YMCA Grounds, Nandanam", "capacity": 50000},
         "quantitative_factors": [
            {"factor_name": "Entry Fee", "value": 20, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "Publishers", "value": 800, "unit": "count", "data_type": "numeric"},
            {"factor_name": "Duration", "value": 15, "unit": "days", "data_type": "numeric"},
         ]},

        # ===== SOCIAL IMAGE — Services =====
        {**base, "solution_id": str(uuid.uuid4()), "type": "SERVICE", "name": "LinkedIn Premium Career — Annual Plan",
         "description": "Enhanced LinkedIn profile visibility, InMail credits, and salary insights for career growth.",
         "life_area_id": "la_social_image", "sub_area_id": "sa_soc_brand", "category_id": "cat_soc_thought",
         "provider": "LinkedIn", "url": "https://www.linkedin.com/premium",
         "tags": ["LinkedIn", "personal brand", "networking", "career"],
         "price_range": "₹1,500 - ₹5,000/month",
         "type_specific": {"duration": "Monthly/Annual", "frequency": "Ongoing", "delivery_mode": "Online"},
         "quantitative_factors": [
            {"factor_name": "Monthly Cost", "value": 1800, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "InMail Credits", "value": 15, "unit": "/month", "data_type": "numeric"},
            {"factor_name": "Who Viewed Profile", "value": 1, "unit": "unlimited", "data_type": "boolean"},
         ]},

        # ===== CONTRIBUTION — NGOs =====
        {**base, "solution_id": str(uuid.uuid4()), "type": "PROJECT", "name": "Teach For India — Chennai Fellowship",
         "description": "2-year fellowship program placing graduates as full-time teachers in under-resourced schools.",
         "life_area_id": "la_contribution", "sub_area_id": "sa_con_mentoring", "category_id": "cat_con_mentor",
         "provider": "Teach For India", "url": "https://www.teachforindia.org",
         "tags": ["teaching", "fellowship", "education", "social impact", "Chennai"],
         "price_range": "₹20,000/month stipend",
         "type_specific": {"timeline_months": 24, "team_size": 80, "budget": "Stipend-based"},
         "quantitative_factors": [
            {"factor_name": "Fellowship Duration", "value": 24, "unit": "months", "data_type": "numeric"},
            {"factor_name": "Monthly Stipend", "value": 20000, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "Students Impacted", "value": 120, "unit": "per fellow", "data_type": "numeric"},
         ]},

        # ===== SPIRITUALITY — Services =====
        {**base, "solution_id": str(uuid.uuid4()), "type": "SERVICE", "name": "Isha Yoga — Inner Engineering Online",
         "description": "Guided meditation and yoga program by Sadhguru. Includes Shambhavi Mahamudra Kriya.",
         "life_area_id": "la_spirituality", "sub_area_id": "sa_spi_practice", "category_id": "cat_spi_meditation",
         "provider": "Isha Foundation", "url": "https://www.innerengineering.com",
         "tags": ["yoga", "meditation", "Isha", "Sadhguru", "spiritual practice"],
         "price_range": "₹2,000 - ₹5,000",
         "type_specific": {"duration": "7 days online + 1 day in-person", "frequency": "One-time + daily practice", "delivery_mode": "Online + In-person completion"},
         "quantitative_factors": [
            {"factor_name": "Course Fee", "value": 2100, "unit": "INR", "data_type": "numeric"},
            {"factor_name": "Online Sessions", "value": 7, "unit": "count", "data_type": "numeric"},
            {"factor_name": "Daily Practice Time", "value": 21, "unit": "minutes", "data_type": "numeric"},
         ]},
    ]

    await db.solutions_store.insert_many(solutions)

    # Create indexes
    await db.solutions_store.create_index([("name", "text"), ("description", "text"), ("tags", "text")])
    await db.solutions_store.create_index("life_area_id")
    await db.solutions_store.create_index("type")
    await db.solutions_store.create_index("is_authorized")
    await db.solutions_store.create_index("visibility")
    await db.solution_reviews.create_index("solution_id")
    await db.solution_reviews.create_index("reviewer_id")

    return {"message": "Solutions store seeded", "count": len(solutions)}
