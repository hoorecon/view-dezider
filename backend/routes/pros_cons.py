"""Pros & Cons Module — 8-step decision framework.

Legacy flat CRUD (root-level pros[]/cons[]) is preserved for backward
compatibility. New routes implement the 8-step workflow from the user's
REFERENCE Career Consultation workbook.
"""

import uuid
import os
import json as json_module
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends
from core.database import db
from core.auth import get_current_user

from models.decision_framework_models import (
    DecisionOption,
    FrameworkFactor,
    FrameworkConfig,
    AssessmentCell,
    FINAL_DECISION_GUIDELINES,
    compute_cell_value,
    compute_realistic_rating,
    compute_satisfaction_value,
    compute_option_rollups,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pros-cons", tags=["Pros & Cons"])


# ========================
# 8-step framework helpers
# ========================

def _now():
    return datetime.now(timezone.utc)


async def _load_analysis(analysis_id: str, user_id: str) -> Dict[str, Any]:
    doc = await db.pros_cons.find_one({"id": analysis_id, "user_id": user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Analysis not found")
    # ensure default 8-step containers exist
    doc.setdefault("options", [])
    doc.setdefault("factors", [])
    doc.setdefault("assessments", {})
    doc.setdefault("config", FrameworkConfig().dict())
    doc.setdefault("current_step", 1)
    return doc


async def _persist(analysis_id: str, user_id: str, patch: Dict[str, Any]):
    patch["updated_at"] = _now()
    await db.pros_cons.update_one(
        {"id": analysis_id, "user_id": user_id},
        {"$set": patch},
    )


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
    """Create a new Pros & Cons analysis (also seeds the 8-step framework containers)."""
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "title": data.title,
        "context": data.context,
        "life_area": data.life_area,
        "decision_type": data.decision_type,
        # Legacy flat list (kept for backward compat)
        "pros": [],
        "cons": [],
        # 8-step framework containers
        "options": [],
        "factors": [],
        "assessments": {},                       # { option_id: { factor_id: AssessmentCell } }
        "config": FrameworkConfig().dict(),
        "current_step": 1,
        "rollups": [],                            # filled by /aggregate
        "converted_decision_id": None,
        "created_at": _now(),
        "updated_at": _now(),
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
            "name": f"SHOULD NOT - {con['text']}",
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
        from core.llm_compat import LlmChat, UserMessage  # provider-agnostic shim (Emergent | direct via litellm)

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


# ════════════════════════════════════════════════════════════════════
#                  8-STEP FRAMEWORK ENDPOINTS
# ════════════════════════════════════════════════════════════════════

# ─── Step #1 — Direct factors  (initial list, name only; expected_value optional) ───
@router.post("/{analysis_id}/factors")
async def add_factor(analysis_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    """Add a direct factor (Step #1).  Body: { name, expected_value?, unit?, parent_id? }."""
    doc = await _load_analysis(analysis_id, user["user_id"])
    factor = FrameworkFactor(
        name=(body.get("name") or "").strip(),
        expected_value=body.get("expected_value"),
        unit=body.get("unit"),
        parent_id=body.get("parent_id"),
        source="direct",
    ).dict()
    if not factor["name"]:
        raise HTTPException(status_code=400, detail="Factor name is required")
    factor["priority_rank"] = len(doc["factors"]) + 1
    doc["factors"].append(factor)
    await _persist(analysis_id, user["user_id"], {"factors": doc["factors"]})
    return {"id": factor["id"], "factor": factor}


@router.put("/{analysis_id}/factors/{factor_id}")
async def update_factor(analysis_id: str, factor_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    """Patch any field of a factor.  Auto-recomputes realistic_rating when std_rating or realistic_gap_pct change."""
    doc = await _load_analysis(analysis_id, user["user_id"])
    factors = doc["factors"]
    idx = next((i for i, f in enumerate(factors) if f["id"] == factor_id), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Factor not found")
    allowed = {
        "name", "expected_value", "unit", "parent_id", "notation", "priority_rank",
        "std_rating", "factor_type", "improvable", "my_expectation", "others_expectations",
        "market_standard", "realistic_gap_pct", "realistic_gap_value", "notes",
        "is_duplicate",   # Step 4 — non-destructive de-dup flag (audit history)
        "display_name",   # Step 5+ rename override; original `name` preserved for Steps 1-4
    }
    for k, v in body.items():
        if k in allowed:
            factors[idx][k] = v
    # auto-derive realistic_rating
    factors[idx]["realistic_rating"] = compute_realistic_rating(
        int(factors[idx].get("std_rating") or 0),
        float(factors[idx].get("realistic_gap_pct") or 0.0),
    )
    await _persist(analysis_id, user["user_id"], {"factors": factors})
    return {"factor": factors[idx]}


@router.delete("/{analysis_id}/factors/{factor_id}")
async def delete_factor(analysis_id: str, factor_id: str, user: dict = Depends(get_current_user)):
    doc = await _load_analysis(analysis_id, user["user_id"])
    factors = [f for f in doc["factors"] if f["id"] != factor_id and f.get("parent_id") != factor_id]
    # also strip assessments for that factor
    assessments = doc.get("assessments", {}) or {}
    for opt_id, cells in list(assessments.items()):
        cells.pop(factor_id, None)
    await _persist(analysis_id, user["user_id"], {"factors": factors, "assessments": assessments})
    return {"deleted": True}


@router.post("/{analysis_id}/factors/reorder")
async def reorder_factors(analysis_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    """Body: { ordered_ids: [factor_id, ...] }.  Sets priority_rank 1..N."""
    doc = await _load_analysis(analysis_id, user["user_id"])
    ordered = body.get("ordered_ids") or []
    rank_map = {fid: i + 1 for i, fid in enumerate(ordered)}
    for f in doc["factors"]:
        if f["id"] in rank_map:
            f["priority_rank"] = rank_map[f["id"]]
    doc["factors"].sort(key=lambda f: f.get("priority_rank", 999))
    await _persist(analysis_id, user["user_id"], {"factors": doc["factors"]})
    return {"factors": doc["factors"]}


# ─── Step #2 — Options + per-option Pros & Cons ───
@router.post("/{analysis_id}/options")
async def add_option(analysis_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    doc = await _load_analysis(analysis_id, user["user_id"])
    opt = DecisionOption(
        name=(body.get("name") or "").strip() or f"Option {len(doc['options']) + 1}",
        description=body.get("description") or "",
        order=len(doc["options"]),
    ).dict()
    doc["options"].append(opt)
    await _persist(analysis_id, user["user_id"], {"options": doc["options"]})
    return {"id": opt["id"], "option": opt}


@router.put("/{analysis_id}/options/{option_id}")
async def update_option(analysis_id: str, option_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    doc = await _load_analysis(analysis_id, user["user_id"])
    opts = doc["options"]
    idx = next((i for i, o in enumerate(opts) if o["id"] == option_id), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Option not found")
    for k in ("name", "description"):
        if k in body:
            opts[idx][k] = body[k]
    # accept replacing pros / cons whole-list (P&C are managed per-option)
    if "pros" in body and isinstance(body["pros"], list):
        opts[idx]["pros"] = body["pros"]
    if "cons" in body and isinstance(body["cons"], list):
        opts[idx]["cons"] = body["cons"]
    await _persist(analysis_id, user["user_id"], {"options": opts})
    return {"option": opts[idx]}


@router.delete("/{analysis_id}/options/{option_id}")
async def delete_option(analysis_id: str, option_id: str, user: dict = Depends(get_current_user)):
    doc = await _load_analysis(analysis_id, user["user_id"])
    opts = [o for o in doc["options"] if o["id"] != option_id]
    assessments = doc.get("assessments", {}) or {}
    assessments.pop(option_id, None)
    await _persist(analysis_id, user["user_id"], {"options": opts, "assessments": assessments})
    return {"deleted": True}


@router.post("/{analysis_id}/options/{option_id}/pros")
async def add_pro(analysis_id: str, option_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    doc = await _load_analysis(analysis_id, user["user_id"])
    opts = doc["options"]
    idx = next((i for i, o in enumerate(opts) if o["id"] == option_id), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Option not found")
    item = {
        "id": str(uuid.uuid4()),
        "text": (body.get("text") or "").strip(),
        "description": body.get("description", ""),
        "importance": int(body.get("importance", 5)),
        "promoted_factor_id": None,
    }
    if not item["text"]:
        raise HTTPException(status_code=400, detail="Pro text required")
    opts[idx].setdefault("pros", []).append(item)
    await _persist(analysis_id, user["user_id"], {"options": opts})
    return item


@router.post("/{analysis_id}/options/{option_id}/cons")
async def add_con(analysis_id: str, option_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    doc = await _load_analysis(analysis_id, user["user_id"])
    opts = doc["options"]
    idx = next((i for i, o in enumerate(opts) if o["id"] == option_id), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Option not found")
    item = {
        "id": str(uuid.uuid4()),
        "text": (body.get("text") or "").strip(),
        "description": body.get("description", ""),
        "importance": int(body.get("importance", 5)),
        "promoted_factor_id": None,
    }
    if not item["text"]:
        raise HTTPException(status_code=400, detail="Con text required")
    opts[idx].setdefault("cons", []).append(item)
    await _persist(analysis_id, user["user_id"], {"options": opts})
    return item


@router.delete("/{analysis_id}/options/{option_id}/pros/{item_id}")
async def delete_pro(analysis_id: str, option_id: str, item_id: str, user: dict = Depends(get_current_user)):
    doc = await _load_analysis(analysis_id, user["user_id"])
    for o in doc["options"]:
        if o["id"] == option_id:
            o["pros"] = [p for p in o.get("pros", []) if p["id"] != item_id]
    await _persist(analysis_id, user["user_id"], {"options": doc["options"]})
    return {"deleted": True}


@router.delete("/{analysis_id}/options/{option_id}/cons/{item_id}")
async def delete_con(analysis_id: str, option_id: str, item_id: str, user: dict = Depends(get_current_user)):
    doc = await _load_analysis(analysis_id, user["user_id"])
    for o in doc["options"]:
        if o["id"] == option_id:
            o["cons"] = [c for c in o.get("cons", []) if c["id"] != item_id]
    await _persist(analysis_id, user["user_id"], {"options": doc["options"]})
    return {"deleted": True}


# ── Step #2 — Edit existing Pro / Con text (inline rename) ──
@router.put("/{analysis_id}/options/{option_id}/pros/{item_id}")
async def update_pro(analysis_id: str, option_id: str, item_id: str,
                     body: Dict[str, Any], user: dict = Depends(get_current_user)):
    """Inline-edit a Pro's text. Body: { text }"""
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Pro text cannot be empty")
    doc = await _load_analysis(analysis_id, user["user_id"])
    found = False
    for o in doc["options"]:
        if o["id"] == option_id:
            for p in o.get("pros", []):
                if p["id"] == item_id:
                    p["text"] = text
                    found = True
                    break
    if not found:
        raise HTTPException(status_code=404, detail="Pro not found")
    await _persist(analysis_id, user["user_id"], {"options": doc["options"]})
    return {"updated": True}


@router.put("/{analysis_id}/options/{option_id}/cons/{item_id}")
async def update_con(analysis_id: str, option_id: str, item_id: str,
                     body: Dict[str, Any], user: dict = Depends(get_current_user)):
    """Inline-edit a Con's text. Body: { text }"""
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Con text cannot be empty")
    doc = await _load_analysis(analysis_id, user["user_id"])
    found = False
    for o in doc["options"]:
        if o["id"] == option_id:
            for c in o.get("cons", []):
                if c["id"] == item_id:
                    c["text"] = text
                    found = True
                    break
    if not found:
        raise HTTPException(status_code=404, detail="Con not found")
    await _persist(analysis_id, user["user_id"], {"options": doc["options"]})
    return {"updated": True}


# ─── Step #3 — Auto-convert Pros & Cons → factors (with "SHOULD NOT - " prefix for cons) ───
@router.post("/{analysis_id}/promote-pros-cons")
async def promote_pros_cons_to_factors(analysis_id: str, user: dict = Depends(get_current_user)):
    """Step #3.1 — promote every Pro/Con item across all options to a factor.
    Cons get prefixed with 'SHOULD NOT - '.  Idempotent — skips items already promoted.
    """
    doc = await _load_analysis(analysis_id, user["user_id"])
    factors = doc["factors"]
    promoted_count = 0
    next_rank = (max((f.get("priority_rank") or 0) for f in factors) + 1) if factors else 1

    for opt in doc["options"]:
        for p in opt.get("pros", []):
            if p.get("promoted_factor_id"):
                continue
            fid = str(uuid.uuid4())
            factors.append(FrameworkFactor(
                id=fid,
                name=p["text"],
                source="pro",
                source_option_id=opt["id"],
                source_item_id=p["id"],
                std_rating=int((p.get("importance") or 5) * 10),
                priority_rank=next_rank,
            ).dict())
            p["promoted_factor_id"] = fid
            next_rank += 1
            promoted_count += 1
        for c in opt.get("cons", []):
            if c.get("promoted_factor_id"):
                continue
            fid = str(uuid.uuid4())
            factors.append(FrameworkFactor(
                id=fid,
                name=f"SHOULD NOT - {c['text']}",
                source="con",
                source_option_id=opt["id"],
                source_item_id=c["id"],
                std_rating=int((c.get("importance") or 5) * 10),
                priority_rank=next_rank,
            ).dict())
            c["promoted_factor_id"] = fid
            next_rank += 1
            promoted_count += 1

    await _persist(analysis_id, user["user_id"], {"factors": factors, "options": doc["options"]})
    return {"promoted_count": promoted_count, "total_factors": len(factors)}


# ─── Steps #4 + #5 — manual grouping (parent_id set via PUT /factors/{id}) ───
#  (no extra endpoint needed; handled via update_factor with parent_id)


# ─── Step #6 — Mandatory/Optional + threshold config ───
@router.put("/{analysis_id}/config")
async def update_config(analysis_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    doc = await _load_analysis(analysis_id, user["user_id"])
    cfg = doc.get("config") or FrameworkConfig().dict()
    for k in ("mandatory_threshold_pct", "max_improvement_period_months", "std_gap"):
        if k in body:
            cfg[k] = body[k]
    await _persist(analysis_id, user["user_id"], {"config": cfg})
    return {"config": cfg}


# ─── Steps #7 + #8 — Assessment cell (per option per factor) ───
@router.put("/{analysis_id}/assessments/{option_id}/{factor_id}")
async def upsert_assessment(
    analysis_id: str, option_id: str, factor_id: str,
    body: Dict[str, Any], user: dict = Depends(get_current_user),
):
    """Update / create the cell that holds Step #7 + #8 values for one (option, factor).
    Body may include: assessment_pct, actual_value, satisfaction_pct, improvement_pct, notes.
    cell_value and satisfaction_value are derived server-side.
    """
    doc = await _load_analysis(analysis_id, user["user_id"])
    # validate referenced ids
    factor = next((f for f in doc["factors"] if f["id"] == factor_id), None)
    if not factor:
        raise HTTPException(status_code=404, detail="Factor not found")
    if not any(o["id"] == option_id for o in doc["options"]):
        raise HTTPException(status_code=404, detail="Option not found")

    assessments = doc.get("assessments", {}) or {}
    cell = (assessments.get(option_id) or {}).get(factor_id) or AssessmentCell().dict()
    for k in ("assessment_pct", "actual_value", "satisfaction_pct", "improvement_pct", "notes"):
        if k in body:
            cell[k] = body[k]
    # derived
    cell["cell_value"] = compute_cell_value(
        int(cell.get("assessment_pct", 0) or 0),
        int(factor.get("std_rating", 0) or 0),
    )
    cell["satisfaction_value"] = compute_satisfaction_value(
        factor.get("realistic_rating") or factor.get("std_rating"),
        float(cell.get("satisfaction_pct", 0.0) or 0.0),
    )
    assessments.setdefault(option_id, {})[factor_id] = cell
    await _persist(analysis_id, user["user_id"], {"assessments": assessments})
    return {"cell": cell}


# ─── Aggregate / rollup — Step #7.4 + Step #8.10 + Final Guidelines ───
@router.get("/{analysis_id}/aggregate")
async def aggregate(analysis_id: str, user: dict = Depends(get_current_user)):
    doc = await _load_analysis(analysis_id, user["user_id"])
    rollups = compute_option_rollups(
        doc["factors"], doc.get("assessments", {}) or {}, doc["options"], doc.get("config"),
    )
    # persist for convenience
    await _persist(analysis_id, user["user_id"], {"rollups": rollups})
    return {
        "rollups": rollups,
        "factors": doc["factors"],
        "options": doc["options"],
        "config": doc.get("config", FrameworkConfig().dict()),
        "final_decision_guidelines": FINAL_DECISION_GUIDELINES,
    }


@router.post("/{analysis_id}/step")
async def set_current_step(analysis_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    step = int(body.get("step") or 1)
    step = max(1, min(8, step))
    await _persist(analysis_id, user["user_id"], {"current_step": step})
    return {"current_step": step}

