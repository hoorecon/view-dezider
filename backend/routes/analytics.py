"""Folder analytics + Decision meta routes"""

from datetime import datetime
from fastapi import APIRouter, Depends
from core.database import db
from core.auth import get_current_user

DECISION_FOLDERS = [
    {"id": "holistic_health", "name": "Holistic Health", "icon": "fitness", "color": "#10B981"},
    {"id": "knowledge_skills", "name": "Knowledge & Skills", "icon": "book", "color": "#3B82F6"},
    {"id": "relationships", "name": "Relationships", "icon": "heart", "color": "#EC4899"},
    {"id": "finance", "name": "Finance", "icon": "cash", "color": "#F59E0B"},
    {"id": "assets", "name": "Assets", "icon": "home", "color": "#8B5CF6"},
    {"id": "career", "name": "Career", "icon": "briefcase", "color": "#6366F1"},
    {"id": "hobbies_entertainment", "name": "Hobbies & Entertainment", "icon": "game-controller", "color": "#14B8A6"},
    {"id": "social_image", "name": "Social Image & Influence", "icon": "star", "color": "#F97316"},
    {"id": "social_contributions", "name": "Social Contributions", "icon": "people", "color": "#06B6D4"},
    {"id": "spirituality_religion", "name": "Spirituality & Religion", "icon": "leaf", "color": "#A855F7"},
]

router = APIRouter(tags=["Analytics"])


@router.get("/analytics/folders")
async def get_folder_analytics(user: dict = Depends(get_current_user)):
    """Get analytics broken down by decision folder"""
    decisions = await db.decisions.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(500)

    folder_stats = {}
    for folder in DECISION_FOLDERS:
        folder_stats[folder["id"]] = {
            "id": folder["id"], "name": folder["name"], "icon": folder["icon"], "color": folder["color"],
            "total_decisions": 0, "completed": 0, "in_progress": 0, "draft": 0,
            "avg_factors": 0, "avg_options": 0, "total_factors": 0, "total_options": 0,
            "completion_rate": 0, "recent_decision": None,
        }
    folder_stats["uncategorized"] = {
        "id": "uncategorized", "name": "Uncategorized", "icon": "folder-open", "color": "#9CA3AF",
        "total_decisions": 0, "completed": 0, "in_progress": 0, "draft": 0,
        "avg_factors": 0, "avg_options": 0, "total_factors": 0, "total_options": 0,
        "completion_rate": 0, "recent_decision": None,
    }

    for d in decisions:
        folder_id = d.get("folder", "") or "uncategorized"
        if folder_id not in folder_stats:
            folder_id = "uncategorized"
        stats = folder_stats[folder_id]
        stats["total_decisions"] += 1
        stats["total_factors"] += len(d.get("factors", []))
        stats["total_options"] += len(d.get("options", []))
        status = d.get("status", "draft")
        if status == "completed":
            stats["completed"] += 1
        elif status == "in_progress":
            stats["in_progress"] += 1
        else:
            stats["draft"] += 1
        if not stats["recent_decision"] or d.get("updated_at", d.get("created_at")) > stats["recent_decision"].get("updated_at", stats["recent_decision"].get("created_at")):
            stats["recent_decision"] = {
                "id": d["id"], "title": d["title"],
                "status": d.get("status", "draft"),
                "updated_at": d.get("updated_at", d.get("created_at")),
            }

    for stats in folder_stats.values():
        total = stats["total_decisions"]
        if total > 0:
            stats["avg_factors"] = round(stats["total_factors"] / total, 1)
            stats["avg_options"] = round(stats["total_options"] / total, 1)
            stats["completion_rate"] = round(stats["completed"] / total * 100, 1)
        if stats["recent_decision"] and "updated_at" in stats["recent_decision"]:
            dt = stats["recent_decision"]["updated_at"]
            if isinstance(dt, datetime):
                stats["recent_decision"]["updated_at"] = dt.isoformat()

    active_folders = [s for s in folder_stats.values() if s["total_decisions"] > 0]
    all_folders = list(folder_stats.values())
    total_decisions = len(decisions)
    completed = sum(1 for d in decisions if d.get("status") == "completed")

    return {
        "folders": all_folders,
        "active_folders": active_folders,
        "summary": {
            "total_decisions": total_decisions,
            "total_completed": completed,
            "total_folders_used": len(active_folders),
            "overall_completion_rate": round(completed / total_decisions * 100, 1) if total_decisions > 0 else 0,
            "most_active_folder": max(active_folders, key=lambda x: x["total_decisions"])["name"] if active_folders else None,
        }
    }


@router.get("/analytics/folder/{folder_id}")
async def get_single_folder_analytics(folder_id: str, user: dict = Depends(get_current_user)):
    """Get detailed analytics for a specific folder"""
    decisions = await db.decisions.find(
        {"user_id": user["user_id"], "folder": folder_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    total = len(decisions)
    completed = [d for d in decisions if d.get("status") == "completed"]
    in_progress = [d for d in decisions if d.get("status") == "in_progress"]
    factor_freq = {}
    for d in decisions:
        for f in d.get("factors", []):
            name = f.get("name", "Unknown")
            factor_freq[name] = factor_freq.get(name, 0) + 1
    top_factors = sorted(factor_freq.items(), key=lambda x: x[1], reverse=True)[:10]
    return {
        "folder_id": folder_id,
        "total_decisions": total,
        "completed": len(completed),
        "in_progress": len(in_progress),
        "draft": total - len(completed) - len(in_progress),
        "completion_rate": round(len(completed) / total * 100, 1) if total > 0 else 0,
        "top_factors": [{"name": name, "count": count} for name, count in top_factors],
        "recent_decisions": [
            {"id": d["id"], "title": d["title"], "status": d.get("status", "draft")}
            for d in decisions[:5]
        ],
    }


@router.get("/decision-meta")
async def get_decision_meta():
    return {
        "life_areas": [
            {"id": "career", "name": "Career & Work", "icon": "briefcase"},
            {"id": "finance", "name": "Finance & Investment", "icon": "cash"},
            {"id": "health", "name": "Health & Wellness", "icon": "fitness"},
            {"id": "relationships", "name": "Relationships & Family", "icon": "people"},
            {"id": "education", "name": "Education & Learning", "icon": "school"},
            {"id": "personal", "name": "Personal Growth", "icon": "rocket"},
            {"id": "business", "name": "Business & Entrepreneurship", "icon": "trending-up"},
            {"id": "lifestyle", "name": "Lifestyle & Living", "icon": "home"},
        ],
        "decision_types": [
            {"id": "problem", "name": "Problem", "description": "Solving a current issue or challenge", "color": "#EF4444"},
            {"id": "need", "name": "Need", "description": "Fulfilling a requirement or necessity", "color": "#F59E0B"},
            {"id": "aspiration", "name": "Aspiration", "description": "Pursuing a goal or ambition", "color": "#10B981"},
        ]
    }
