"""
AALA — Accrued Assets & Liabilities Analysis
EVE Exercise #5: Assess Circle of Influence w.r.t Circle of Concern
as a Preparatory Step for Solution Finder & Solution Matrix.
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user

router = APIRouter()

# ═══════════════════════════════════════════════════════════════
# LIFE AREAS TAXONOMY (from EVE Template)
# ═══════════════════════════════════════════════════════════════

AALA_TAXONOMY = [
    {
        "area_id": "holistic_health",
        "area_name": "Holistic Health",
        "area_number": 1,
        "icon": "fitness",
        "subcategories": [
            {"id": "physical", "name": "Physical"},
            {"id": "mental", "name": "Mental"},
            {"id": "emotional", "name": "Emotional"},
        ],
    },
    {
        "area_id": "knowledge_skills",
        "area_name": "Knowledge & Skills",
        "area_number": 2,
        "icon": "school",
        "subcategories": [
            {"id": "knowledge", "name": "Knowledge"},
            {"id": "skills", "name": "Skills"},
        ],
    },
    {
        "area_id": "relationships",
        "area_name": "Relationships",
        "area_number": 3,
        "icon": "heart",
        "subcategories": [
            {"id": "self", "name": "Self"},
            {"id": "parents", "name": "Parents"},
            {"id": "siblings", "name": "Siblings"},
            {"id": "spouse", "name": "Spouse"},
            {"id": "children", "name": "Children"},
            {"id": "relatives", "name": "Relatives"},
            {"id": "colleagues", "name": "Colleagues"},
            {"id": "friends", "name": "Friends"},
            {"id": "mentors", "name": "Mentors on Specific Domain"},
            {"id": "life_coaches", "name": "Life Coaches"},
            {"id": "spiritual_guru", "name": "Spiritual Guru"},
            {"id": "divine", "name": "Divine"},
        ],
    },
    {
        "area_id": "finance",
        "area_name": "Finance",
        "area_number": 4,
        "icon": "cash",
        "subcategories": [
            {"id": "insurance", "name": "Insurance"},
            {"id": "savings", "name": "Savings"},
            {"id": "investments", "name": "Investments"},
        ],
    },
    {
        "area_id": "assets",
        "area_name": "Assets",
        "area_number": 5,
        "icon": "home",
        "subcategories": [
            {"id": "moveable_assets", "name": "Moveable Assets"},
            {"id": "immovable_assets", "name": "Immovable Assets"},
            {"id": "intellectual_assets", "name": "Intellectual Assets"},
        ],
    },
    {
        "area_id": "career",
        "area_name": "Career",
        "area_number": 6,
        "icon": "briefcase",
        "subcategories": [
            {"id": "education", "name": "Education"},
            {"id": "job", "name": "Job"},
            {"id": "self_employed", "name": "Self Employed Business"},
            {"id": "business", "name": "Business"},
            {"id": "venture_investments", "name": "Venture Investments"},
            {"id": "homemaker", "name": "Homemaker"},
            {"id": "retirement_life", "name": "Retirement Life"},
        ],
    },
    {
        "area_id": "personal_dreams",
        "area_name": "PDF - Personal Dreams Fulfillment",
        "area_number": 7,
        "icon": "star",
        "subcategories": [],
    },
    {
        "area_id": "social_image",
        "area_name": "Social Image & Influence",
        "area_number": 8,
        "icon": "people",
        "subcategories": [],
    },
    {
        "area_id": "social_contributions",
        "area_name": "Social Contributions",
        "area_number": 9,
        "icon": "hand-left",
        "subcategories": [],
    },
    {
        "area_id": "spirituality",
        "area_name": "Spirituality",
        "area_number": 10,
        "icon": "leaf",
        "subcategories": [],
    },
]


# ═══════════════════════════════════════════════════════════════
# GET TAXONOMY
# ═══════════════════════════════════════════════════════════════

@router.get("/aala/taxonomy")
async def get_taxonomy():
    """Return the full AALA life-area taxonomy."""
    return {"taxonomy": AALA_TAXONOMY}


# ═══════════════════════════════════════════════════════════════
# CREATE ASSESSMENT
# ═══════════════════════════════════════════════════════════════

@router.post("/aala/assessments")
async def create_assessment(request: Request, user: dict = Depends(get_current_user)):
    """Create a new AALA assessment (initial or periodic snapshot)."""
    body = await request.json()
    assessment_id = f"AALA-{uuid.uuid4().hex[:10].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "assessment_id": assessment_id,
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "title": body.get("title", "AALA Assessment"),
        "tracking_frequency": body.get("tracking_frequency", "weekly"),  # daily/weekly/fortnightly
        "is_baseline": body.get("is_baseline", False),
        "entries": body.get("entries", []),
        # Each entry: { area_id, subcategory_id, current_liabilities, accrued_liabilities,
        #               current_assets, accrued_assets, numeric_value, notes }
        "summary_notes": body.get("summary_notes", ""),
        "status": body.get("status", "active"),
        "snapshot_date": body.get("snapshot_date", now[:10]),
        "created_at": now,
        "updated_at": now,
    }

    await db.aala_assessments.insert_one(doc)
    doc.pop("_id", None)
    return doc


# ═══════════════════════════════════════════════════════════════
# LIST ASSESSMENTS
# ═══════════════════════════════════════════════════════════════

@router.get("/aala/assessments")
async def list_assessments(request: Request, user: dict = Depends(get_current_user)):
    """List all AALA assessments for the user."""
    query = {"user_id": user["user_id"]}
    params = request.query_params

    if params.get("is_baseline"):
        query["is_baseline"] = params["is_baseline"].lower() == "true"
    if params.get("status"):
        query["status"] = params["status"]

    docs = await db.aala_assessments.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    return docs


# ═══════════════════════════════════════════════════════════════
# GET SINGLE ASSESSMENT
# ═══════════════════════════════════════════════════════════════

@router.get("/aala/assessments/{assessment_id}")
async def get_assessment(assessment_id: str, user: dict = Depends(get_current_user)):
    """Get a single AALA assessment by ID."""
    doc = await db.aala_assessments.find_one(
        {"assessment_id": assessment_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return doc


# ═══════════════════════════════════════════════════════════════
# UPDATE ASSESSMENT
# ═══════════════════════════════════════════════════════════════

@router.put("/aala/assessments/{assessment_id}")
async def update_assessment(assessment_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Update an existing AALA assessment."""
    body = await request.json()
    now = datetime.now(timezone.utc).isoformat()

    update_fields = {"updated_at": now}
    for field in ["title", "tracking_frequency", "entries", "summary_notes", "status", "snapshot_date", "is_baseline"]:
        if field in body:
            update_fields[field] = body[field]

    result = await db.aala_assessments.update_one(
        {"assessment_id": assessment_id, "user_id": user["user_id"]},
        {"$set": update_fields},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Assessment not found")

    doc = await db.aala_assessments.find_one(
        {"assessment_id": assessment_id}, {"_id": 0}
    )
    return doc


# ═══════════════════════════════════════════════════════════════
# DELETE ASSESSMENT
# ═══════════════════════════════════════════════════════════════

@router.delete("/aala/assessments/{assessment_id}")
async def delete_assessment(assessment_id: str, user: dict = Depends(get_current_user)):
    """Delete an AALA assessment."""
    result = await db.aala_assessments.delete_one(
        {"assessment_id": assessment_id, "user_id": user["user_id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return {"deleted": True}


# ═══════════════════════════════════════════════════════════════
# DASHBOARD / ANALYTICS
# ═══════════════════════════════════════════════════════════════

@router.get("/aala/dashboard")
async def aala_dashboard(user: dict = Depends(get_current_user)):
    """Get AALA dashboard summary — latest snapshot, trends, net position."""
    assessments = await db.aala_assessments.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("snapshot_date", -1).to_list(100)

    if not assessments:
        return {
            "total_assessments": 0,
            "baseline": None,
            "latest": None,
            "net_position_by_area": {},
            "tracking_frequency": "weekly",
            "history_count": 0,
        }

    baseline = next((a for a in assessments if a.get("is_baseline")), None)
    latest = assessments[0] if assessments else None

    # Compute net position (Assets - Liabilities) by area from latest
    net_by_area = {}
    if latest and latest.get("entries"):
        for entry in latest["entries"]:
            area = entry.get("area_id", "unknown")
            cv_assets = _safe_float(entry.get("current_assets_value", 0))
            ac_assets = _safe_float(entry.get("accrued_assets_value", 0))
            cv_liab = _safe_float(entry.get("current_liabilities_value", 0))
            ac_liab = _safe_float(entry.get("accrued_liabilities_value", 0))
            total_assets = cv_assets + ac_assets
            total_liab = cv_liab + ac_liab
            if area not in net_by_area:
                net_by_area[area] = {"total_assets": 0, "total_liabilities": 0, "net": 0}
            net_by_area[area]["total_assets"] += total_assets
            net_by_area[area]["total_liabilities"] += total_liab
            net_by_area[area]["net"] += total_assets - total_liab

    return {
        "total_assessments": len(assessments),
        "baseline": baseline,
        "latest": latest,
        "net_position_by_area": net_by_area,
        "tracking_frequency": latest.get("tracking_frequency", "weekly") if latest else "weekly",
        "history_count": len(assessments),
    }


def _safe_float(val) -> float:
    try:
        return float(val) if val else 0.0
    except (ValueError, TypeError):
        return 0.0


# ═══════════════════════════════════════════════════════════════
# AUTO-POPULATE FOR SOLUTION MATRIX
# ═══════════════════════════════════════════════════════════════

@router.get("/aala/for-solution-matrix")
async def aala_for_solution_matrix(request: Request, user: dict = Depends(get_current_user)):
    """
    Return the latest AALA data formatted for auto-populating Solution Matrix.
    Maps AALA entries → Solution Matrix fields (resources_at_present, matrix_self fields).
    """
    params = request.query_params
    life_area = params.get("life_area", "")

    latest = await db.aala_assessments.find_one(
        {"user_id": user["user_id"], "status": "active"},
        {"_id": 0},
        sort=[("snapshot_date", -1)],
    )
    if not latest:
        return {"has_data": False, "resources_summary": "", "matrix_fields": {}}

    entries = latest.get("entries", [])
    if life_area:
        entries = [e for e in entries if e.get("area_id") == life_area]

    # Build resources summary text
    resource_lines = []
    finance_summary = []
    people_summary = []
    infra_summary = []
    knowledge_summary = []

    for entry in entries:
        area = entry.get("area_id", "")
        sub = entry.get("subcategory_name", entry.get("subcategory_id", ""))
        ca = entry.get("current_assets", "")
        aa = entry.get("accrued_assets", "")
        cl = entry.get("current_liabilities", "")

        if ca or aa:
            resource_lines.append(f"• {sub}: Assets={ca or 'N/A'}, Accrued={aa or 'N/A'}")
        if cl:
            resource_lines.append(f"  ⚠ Liability: {cl}")

        # Map to Solution Matrix dimensions
        if area in ("finance",):
            if ca:
                finance_summary.append(f"{sub}: {ca}")
        if area in ("relationships",):
            if ca or aa:
                people_summary.append(f"{sub}: {ca or aa}")
        if area in ("assets",):
            if ca or aa:
                infra_summary.append(f"{sub}: {ca or aa}")
        if area in ("knowledge_skills",):
            if ca or aa:
                knowledge_summary.append(f"{sub}: {ca or aa}")

    return {
        "has_data": True,
        "assessment_id": latest.get("assessment_id"),
        "snapshot_date": latest.get("snapshot_date"),
        "resources_summary": "\n".join(resource_lines) if resource_lines else "",
        "matrix_fields": {
            "finance": "; ".join(finance_summary) if finance_summary else "",
            "people": "; ".join(people_summary) if people_summary else "",
            "infrastructure": "; ".join(infra_summary) if infra_summary else "",
            "knowledge_skills": "; ".join(knowledge_summary) if knowledge_summary else "",
        },
        "entry_count": len(entries),
    }


# ═══════════════════════════════════════════════════════════════
# TREND HISTORY
# ═══════════════════════════════════════════════════════════════

@router.get("/aala/trends")
async def aala_trends(request: Request, user: dict = Depends(get_current_user)):
    """Get historical trend data for AALA — net position over time."""
    params = request.query_params
    area_filter = params.get("area_id", "")
    limit = int(params.get("limit", "20"))

    assessments = await db.aala_assessments.find(
        {"user_id": user["user_id"], "status": "active"},
        {"_id": 0, "assessment_id": 1, "snapshot_date": 1, "entries": 1, "is_baseline": 1},
    ).sort("snapshot_date", 1).to_list(limit)

    trends = []
    for a in assessments:
        entries = a.get("entries", [])
        if area_filter:
            entries = [e for e in entries if e.get("area_id") == area_filter]

        total_assets = sum(
            _safe_float(e.get("current_assets_value", 0)) + _safe_float(e.get("accrued_assets_value", 0))
            for e in entries
        )
        total_liab = sum(
            _safe_float(e.get("current_liabilities_value", 0)) + _safe_float(e.get("accrued_liabilities_value", 0))
            for e in entries
        )
        trends.append({
            "date": a.get("snapshot_date"),
            "assessment_id": a.get("assessment_id"),
            "is_baseline": a.get("is_baseline", False),
            "total_assets": total_assets,
            "total_liabilities": total_liab,
            "net_position": total_assets - total_liab,
        })

    return {"trends": trends, "count": len(trends)}
