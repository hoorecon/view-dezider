"""Pros & Cons Module — Create, manage, and convert to PRR Decision factors"""

import uuid
import os
import json as json_module
import logging
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from core.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pros-cons", tags=["Pros & Cons"])


# ========================
# MODELS
# ========================

class ProConItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    description: str = ""
    importance: int = 5  # 1-10


class ProsConsCreate(BaseModel):
    title: str
    context: str = ""
    life_area: Optional[str] = None
    decision_type: Optional[str] = None


class ProsConsUpdate(BaseModel):
    title: Optional[str] = None
    context: Optional[str] = None
    pros: Optional[List[ProConItem]] = None
    cons: Optional[List[ProConItem]] = None
    life_area: Optional[str] = None
    decision_type: Optional[str] = None


# ========================
# CRUD ROUTES
# ========================

@router.post("")
async def create_pros_cons(data: ProsConsCreate, user: dict = Depends(get_current_user)):
    """Create a new Pros & Cons analysis"""
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "title": data.title,
        "context": data.context,
        "life_area": data.life_area,
        "decision_type": data.decision_type,
        "pros": [],
        "cons": [],
        "converted_decision_id": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await db.pros_cons.insert_one(doc)
    return {"id": doc["id"], "message": "Pros & Cons analysis created"}


@router.get("")
async def list_pros_cons(user: dict = Depends(get_current_user)):
    """List all Pros & Cons analyses for the user"""
    docs = await db.pros_cons.find(
        {"user_id": user["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return docs


@router.get("/{analysis_id}")
async def get_pros_cons(analysis_id: str, user: dict = Depends(get_current_user)):
    """Get a specific Pros & Cons analysis"""
    doc = await db.pros_cons.find_one(
        {"id": analysis_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return doc


@router.put("/{analysis_id}")
async def update_pros_cons(analysis_id: str, data: ProsConsUpdate, user: dict = Depends(get_current_user)):
    """Update a Pros & Cons analysis"""
    existing = await db.pros_cons.find_one(
        {"id": analysis_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Analysis not found")
    update_dict = {k: v for k, v in data.dict().items() if v is not None}
    if "pros" in update_dict:
        update_dict["pros"] = [p if isinstance(p, dict) else p.dict() for p in update_dict["pros"]]
    if "cons" in update_dict:
        update_dict["cons"] = [c if isinstance(c, dict) else c.dict() for c in update_dict["cons"]]
    update_dict["updated_at"] = datetime.now(timezone.utc)
    await db.pros_cons.update_one({"id": analysis_id}, {"$set": update_dict})
    return {"message": "Analysis updated"}


@router.delete("/{analysis_id}")
async def delete_pros_cons(analysis_id: str, user: dict = Depends(get_current_user)):
    """Delete a Pros & Cons analysis"""
    result = await db.pros_cons.delete_one({"id": analysis_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"message": "Analysis deleted"}


# ========================
# CONVERT TO PRR DECISION
# ========================

@router.post("/{analysis_id}/convert-to-decision")
async def convert_to_decision(analysis_id: str, user: dict = Depends(get_current_user)):
    """Convert Pros & Cons into a PRR Decision with AI-generated expected values.
    
    - Pros become factors as-is
    - Cons get prefixed with 'NOT ' and become factors
    - AI generates expected values for each factor
    """
    doc = await db.pros_cons.find_one(
        {"id": analysis_id, "user_id": user["user_id"]}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Analysis not found")

    pros = doc.get("pros", [])
    cons = doc.get("cons", [])

    if not pros and not cons:
        raise HTTPException(status_code=400, detail="Add at least one pro or con before converting")

    # Build factor list
    raw_factors = []
    for i, pro in enumerate(pros):
        raw_factors.append({
            "name": pro["text"],
            "source": "pro",
            "description": pro.get("description", ""),
            "importance": pro.get("importance", 5),
            "order": i,
        })
    for j, con in enumerate(cons):
        raw_factors.append({
            "name": f"NOT {con['text']}",
            "source": "con",
            "description": con.get("description", ""),
            "importance": con.get("importance", 5),
            "order": len(pros) + j,
        })

    # AI-generate expected values
    factors_with_values = await _ai_generate_expected_values(
        doc["title"], doc.get("context", ""), raw_factors, user["user_id"]
    )

    # Create PRR Decision
    decision_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    prr_factors = []
    for idx, f in enumerate(factors_with_values):
        prr_factors.append({
            "id": str(uuid.uuid4()),
            "name": f["name"],
            "category": "primary",
            "rating": f["importance"],
            "order": idx,
            "unit": f.get("unit"),
            "expected_value": f.get("expected_value"),
            "data_type": f.get("data_type"),
            "operator": None,
            "gap_multiplier": 1.0,
            "parent_id": None,
            "weight": None,
        })

    decision_doc = {
        "id": decision_id,
        "user_id": user["user_id"],
        "title": doc["title"],
        "context": doc.get("context", ""),
        "factors": prr_factors,
        "options": [],
        "chosen_option_id": None,
        "decision_case": None,
        "notes": f"Converted from Pros & Cons analysis. {len(pros)} pros, {len(cons)} cons.",
        "reflection": "",
        "final_notes": "",
        "folder": "",
        "life_area": doc.get("life_area"),
        "decision_type": doc.get("decision_type"),
        "rating_gap_multiplier": 1.0,
        "mpps_option_id": None,
        "mpps_improvements": [],
        "mpps_projected_worth": None,
        "mpps_timeframe": None,
        "implementation_review_date": None,
        "status": "in_progress",
        "source_module": "pros_cons",
        "source_id": analysis_id,
        "created_at": now,
        "updated_at": now,
    }

    await db.decisions.insert_one(decision_doc)
    await db.pros_cons.update_one(
        {"id": analysis_id},
        {"$set": {"converted_decision_id": decision_id, "updated_at": now}}
    )

    return {
        "decision_id": decision_id,
        "factors_count": len(prr_factors),
        "message": f"Created PRR Decision with {len(prr_factors)} factors from {len(pros)} pros and {len(cons)} cons",
    }


async def _ai_generate_expected_values(title: str, context: str, raw_factors: list, user_id: str) -> list:
    """Use AI to generate expected values for each factor."""
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        # Fallback: return factors without AI-generated values
        return raw_factors

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        factor_lines = []
        for f in raw_factors:
            factor_lines.append(f"- {f['name']} (source: {f['source']}, importance: {f['importance']}/10, desc: {f.get('description', '')})") 

        prompt = f"""You are a decision analysis expert. For the following decision, generate realistic expected values for each factor.

Decision: {title}
Context: {context}

Factors:
{chr(10).join(factor_lines)}

For EACH factor, provide:
1. expected_value: A realistic target/benchmark value (string)
2. unit: The measurement unit (e.g., "INR", "hours", "rating/10", "percentage", "count", "yes/no")
3. data_type: "quantitative" or "qualitative"

Return ONLY a valid JSON array, one object per factor, in the SAME ORDER:
[{{{{
  "name": "factor name",
  "expected_value": "value",
  "unit": "unit",
  "data_type": "quantitative|qualitative"
}}}}]

Return ONLY valid JSON, no markdown fences."""

        chat = LlmChat(
            api_key=api_key,
            session_id=f"proscons_{user_id}_{uuid.uuid4().hex[:8]}",
            system_message="You are a decision analysis expert. Return only valid JSON arrays."
        ).with_model("openai", "gpt-4.1-mini")

        response = await chat.send_message(UserMessage(text=prompt))
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        ai_values = json_module.loads(response_text)

        # Merge AI values back into factors
        for i, f in enumerate(raw_factors):
            if i < len(ai_values):
                ai = ai_values[i]
                f["expected_value"] = ai.get("expected_value", "")
                f["unit"] = ai.get("unit", "")
                f["data_type"] = ai.get("data_type", "qualitative")

        return raw_factors

    except Exception as e:
        logger.error(f"AI expected value generation failed: {e}")
        return raw_factors
