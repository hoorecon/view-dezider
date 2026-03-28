"""Decision Templates (Admin-curated Context Library) + related routes"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request, Depends
from core.database import db
from core.auth import get_current_user

router = APIRouter(tags=["Decision Templates"])


# ========================
# MODELS
# ========================

class Factor(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    category: str = "primary"
    rating: int = 0
    order: int = 0
    unit: Optional[str] = None
    expected_value: Optional[str] = None
    data_type: Optional[str] = None
    operator: Optional[str] = None
    gap_multiplier: Optional[float] = 1.0
    parent_id: Optional[str] = None
    weight: Optional[float] = None


class DecisionTemplateCreate(BaseModel):
    name: str
    life_area: str
    decision_type: str
    description: str = ""
    factors: List[Factor] = []


# ========================
# ROUTES
# ========================

@router.get("/decision-templates")
async def get_decision_templates(life_area: Optional[str] = None, decision_type: Optional[str] = None):
    query: dict = {"is_approved": True}
    if life_area:
        query["life_area"] = life_area
    if decision_type:
        query["decision_type"] = decision_type
    templates = await db.decision_templates.find(query).sort("name", 1).to_list(100)
    for t in templates:
        t.pop("_id", None)
    return templates


@router.get("/decision-templates/all")
async def get_all_templates(user: dict = Depends(get_current_user)):
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    templates = await db.decision_templates.find({}).sort("created_at", -1).to_list(200)
    for t in templates:
        t.pop("_id", None)
    return templates


@router.post("/decision-templates")
async def create_decision_template(template: DecisionTemplateCreate, user: dict = Depends(get_current_user)):
    """Create a decision template - admin creates approved + official, user creates pending"""
    is_admin = user.get("role") in ["admin", "super_admin"]
    template_dict = template.dict()
    template_dict["id"] = str(uuid.uuid4())
    template_dict["created_by"] = user["user_id"]
    template_dict["submitted_by"] = user["user_id"]
    template_dict["submitted_by_name"] = user.get("name", "")
    template_dict["is_approved"] = is_admin
    template_dict["is_official"] = is_admin
    template_dict["created_at"] = datetime.now(timezone.utc)
    await db.decision_templates.insert_one(template_dict)
    return {"id": template_dict["id"], "message": "Template created successfully", "is_approved": is_admin}


@router.post("/decision-templates/{template_id}/approve")
async def approve_decision_template(template_id: str, user: dict = Depends(get_current_user)):
    """Admin approves a user-submitted template"""
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    result = await db.decision_templates.update_one(
        {"id": template_id}, {"$set": {"is_approved": True}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"message": "Template approved"}


@router.post("/decision-templates/{template_id}/clone")
async def clone_decision_template(template_id: str, user: dict = Depends(get_current_user)):
    """Admin clones a template for editing before approval"""
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    template = await db.decision_templates.find_one({"id": template_id})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    template.pop("_id", None)
    template["id"] = str(uuid.uuid4())
    template["created_by"] = user["user_id"]
    template["is_official"] = True
    template["is_approved"] = False
    template["name"] = f"{template['name']} (Copy)"
    template["created_at"] = datetime.now(timezone.utc)
    await db.decision_templates.insert_one(template)
    return {"id": template["id"], "message": "Template cloned successfully"}


@router.put("/decision-templates/{template_id}")
async def update_decision_template(template_id: str, template: DecisionTemplateCreate, user: dict = Depends(get_current_user)):
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    update_dict = template.dict()
    result = await db.decision_templates.update_one({"id": template_id}, {"$set": update_dict})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"message": "Template updated successfully"}


@router.delete("/decision-templates/{template_id}")
async def delete_decision_template(template_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    result = await db.decision_templates.delete_one({"id": template_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"message": "Template deleted successfully"}
