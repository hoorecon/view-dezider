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
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import Response
from core.database import db
from core.assessment_xlsx import build_template, parse_template, build_value_matrix, parse_rows
from core import google_sheets as gs
from core.trash import move_to_trash
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


def _apply_std_rating_ladder(doc: Dict[str, Any]) -> None:
    """Set std_rating on every factor in-place.

    • If `doc.equal_weightage` is truthy (June 2026 mode): mandatory mains →
      std_rating=20, optional mains → 10. Sub/duplicate → 0. Per-pair gap and
      realistic_gap_pct are ignored while this mode is on.
    • Otherwise, apply the classic bottom→top cumulative ladder using each
      main factor's `priority_gap_pct` (default 100%, anchor=BASE_UNIT).

    Callers must pass the FULL analysis doc so `equal_weightage` can be read
    off the top level.
    """
    BASE_UNIT = 10
    eq = bool(doc.get("equal_weightage"))
    mains = sorted(
        [f for f in doc["factors"] if not f.get("parent_id") and not f.get("is_duplicate")],
        key=lambda f: f.get("priority_rank", 999),
    )
    if eq:
        for f in mains:
            f["std_rating"] = 20 if (f.get("notation") == "mandatory") else 10
    elif mains:
        bottom_to_top = list(reversed(mains))
        bottom_to_top[0]["std_rating"] = BASE_UNIT
        running = float(BASE_UNIT)
        for i in range(1, len(bottom_to_top)):
            gap_pct = float(bottom_to_top[i].get("priority_gap_pct") or 100.0)
            running += (gap_pct / 100.0) * BASE_UNIT
            bottom_to_top[i]["std_rating"] = int(round(running))
    for f in doc["factors"]:
        if f.get("parent_id") or f.get("is_duplicate"):
            f["std_rating"] = 0
        # Realistic gap is disabled in equal-weightage mode.
        eff_gap = 0.0 if eq else float(f.get("realistic_gap_pct") or 0.0)
        f["realistic_rating"] = compute_realistic_rating(
            int(f.get("std_rating") or 0),
            eff_gap,
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
    # Initial-intake info (Individual → Life Area → Need → Sub-area → Scenario)
    acting_as_context: Optional[str] = None
    sub_area_id: Optional[str] = None
    sub_area_name: Optional[str] = None
    scenario_id: Optional[str] = None
    scenario_title: Optional[str] = None


class ProsConsUpdate(BaseModel):
    title: Optional[str] = None
    context: Optional[str] = None
    pros: Optional[List[ProConItem]] = None
    cons: Optional[List[ProConItem]] = None
    life_area: Optional[str] = None
    decision_type: Optional[str] = None
    # ── Equal Weightage (June 2026) ──
    # When True, Step 7 ladder is bypassed: mandatory factors get std_rating=20,
    # optional factors std_rating=10, and realistic_gap uplift is ignored.
    equal_weightage: Optional[bool] = None
    # Editable dependency formulas over f-variables.
    formulas: Optional[List[Dict[str, Any]]] = None


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
        # Initial-intake info — surfaced in the PDF report & list-detail views
        "acting_as_context": data.acting_as_context,
        "sub_area_id": data.sub_area_id,
        "sub_area_name": data.sub_area_name,
        "scenario_id": data.scenario_id,
        "scenario_title": data.scenario_title,
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
        {"user_id": user["user_id"], "contribution_clone": {"$exists": False}}, {"_id": 0}
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
    """Delete a Pros & Cons analysis (moves to Trash)"""
    moved = await move_to_trash("pros_cons", analysis_id, user["user_id"])
    if not moved:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"message": "Analysis moved to Trash"}


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
    try:
        from routes.sku_store import ensure_decision_entitlement
        await ensure_decision_entitlement(user["user_id"], module="dezider", decision_id=decision_id)
    except Exception as _e:
        logger.warning("entitlement consume on pros_cons convert failed: %s", _e)

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
        "priority_gap_pct",  # Step 7 — per-pair gap above the next lower factor
        "weight",         # Step 5 — sub-factor weightage (% split under a main factor)
        # Step 5 "Review & Refine Expectations" — factor metadata (parity with My Dezider)
        "operator", "data_type", "data_source",
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
    """Body: { ordered_ids: [factor_id, ...] }.

    Sets priority_rank 1..N for every factor in the order received AND
    auto-ladders std_rating for MAIN factors only:

        bottom main factor gets `std_gap` (default 10),
        each step up adds `std_gap`,
        top main factor ends at  N_mains * std_gap.

    So if std_gap=10 and there are 8 mains: top=80, 70, 60, 50, 40, 30, 20, bottom=10.
    Sub-factors and duplicates keep std_rating=0 — the aggregator excludes
    them from scoring anyway (compute_option_rollups → scoring_factors).
    """
    doc = await _load_analysis(analysis_id, user["user_id"])
    ordered = body.get("ordered_ids") or []
    rank_map = {fid: i + 1 for i, fid in enumerate(ordered)}
    for f in doc["factors"]:
        if f["id"] in rank_map:
            f["priority_rank"] = rank_map[f["id"]]
    doc["factors"].sort(key=lambda f: f.get("priority_rank", 999))

    # Delegate std_rating computation (honours equal_weightage mode).
    _apply_std_rating_ladder(doc)

    await _persist(analysis_id, user["user_id"], {"factors": doc["factors"]})
    return {"factors": doc["factors"]}


@router.post("/{analysis_id}/factors/recalc-ladder")
async def recalc_ladder(analysis_id: str, user: dict = Depends(get_current_user)):
    """Re-apply the std_rating ladder (or flat equal-weightage) to all main
    factors WITHOUT changing their priority order. Called by the frontend on
    Step 7 entry, whenever the user tweaks any single factor's
    `priority_gap_pct`, or when the user toggles Equal Weightage on/off.

    Idempotent — calling repeatedly with the same data yields the same ratings.
    """
    doc = await _load_analysis(analysis_id, user["user_id"])
    _apply_std_rating_ladder(doc)
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
    # Inter-module hand-off: option inserted from a Solution Finder SMART Goal
    if isinstance(body.get("sf_ref"), dict):
        opt["sf_ref"] = body["sf_ref"]
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


def _duplicate_pro_con(doc: dict, kind: str, text: str, exclude_id: str | None = None) -> bool:
    """True if another item of the same kind ('pros'/'cons') across ALL options
    already has this text (case-insensitive). Keeps the factor tree unique."""
    needle = text.strip().lower()
    for o in doc.get("options", []):
        for it in o.get(kind, []):
            if exclude_id and it.get("id") == exclude_id:
                continue
            if (it.get("text") or "").strip().lower() == needle:
                return True
    return False


@router.post("/{analysis_id}/options/{option_id}/pros")
async def add_pro(analysis_id: str, option_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    doc = await _load_analysis(analysis_id, user["user_id"])
    opts = doc["options"]
    idx = next((i for i, o in enumerate(opts) if o["id"] == option_id), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Option not found")
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Pro text required")
    if _duplicate_pro_con(doc, "pros", text):
        raise HTTPException(status_code=409, detail=f"A Pro named “{text}” already exists in this analysis. Names must be unique.")
    item = {
        "id": str(uuid.uuid4()),
        "text": text,
        "description": body.get("description", ""),
        "importance": int(body.get("importance", 5)),
        "promoted_factor_id": None,
    }
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
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Con text required")
    if _duplicate_pro_con(doc, "cons", text):
        raise HTTPException(status_code=409, detail=f"A Con named “{text}” already exists in this analysis. Names must be unique.")
    item = {
        "id": str(uuid.uuid4()),
        "text": text,
        "description": body.get("description", ""),
        "importance": int(body.get("importance", 5)),
        "promoted_factor_id": None,
    }
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
    """Inline-edit a Pro's text. Body: { text }. Enforces uniqueness and
    propagates the rename to its promoted factor (if already promoted)."""
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Pro text cannot be empty")
    doc = await _load_analysis(analysis_id, user["user_id"])
    if _duplicate_pro_con(doc, "pros", text, exclude_id=item_id):
        raise HTTPException(status_code=409, detail=f"A Pro named “{text}” already exists in this analysis. Names must be unique.")
    found = False
    promoted_fid = None
    for o in doc["options"]:
        if o["id"] == option_id:
            for p in o.get("pros", []):
                if p["id"] == item_id:
                    p["text"] = text
                    promoted_fid = p.get("promoted_factor_id")
                    found = True
                    break
    if not found:
        raise HTTPException(status_code=404, detail="Pro not found")
    # Propagate rename to the promoted factor (Pros keep their text as the name).
    if promoted_fid:
        for f in doc.get("factors", []):
            if f["id"] == promoted_fid:
                f["name"] = text
    await _persist(analysis_id, user["user_id"], {"options": doc["options"], "factors": doc.get("factors", [])})
    return {"updated": True}


@router.put("/{analysis_id}/options/{option_id}/cons/{item_id}")
async def update_con(analysis_id: str, option_id: str, item_id: str,
                     body: Dict[str, Any], user: dict = Depends(get_current_user)):
    """Inline-edit a Con's text. Body: { text }. Enforces uniqueness and
    propagates the rename to its promoted 'SHOULD NOT - …' factor."""
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Con text cannot be empty")
    doc = await _load_analysis(analysis_id, user["user_id"])
    if _duplicate_pro_con(doc, "cons", text, exclude_id=item_id):
        raise HTTPException(status_code=409, detail=f"A Con named “{text}” already exists in this analysis. Names must be unique.")
    found = False
    promoted_fid = None
    for o in doc["options"]:
        if o["id"] == option_id:
            for c in o.get("cons", []):
                if c["id"] == item_id:
                    c["text"] = text
                    promoted_fid = c.get("promoted_factor_id")
                    found = True
                    break
    if not found:
        raise HTTPException(status_code=404, detail="Con not found")
    # Propagate rename to the promoted factor (Cons are prefixed 'SHOULD NOT - ').
    if promoted_fid:
        for f in doc.get("factors", []):
            if f["id"] == promoted_fid:
                f["name"] = f"SHOULD NOT - {text}"
    await _persist(analysis_id, user["user_id"], {"options": doc["options"], "factors": doc.get("factors", [])})
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
    for k in (
        "mandatory_threshold_pct",
        "max_improvement_period_months",
        "std_gap",
        # Step 8 — Case-2 (MPPS) inputs
        "mpps_max_time_value",
        "mpps_max_time_unit",
        # Step 8 — Final Decision capture (post-assessment commitment)
        # Saved on config so it travels with the analysis doc and shows in
        # Solution Box list. final_choice_reason is optional documentation.
        # review_timeline_* is "by when can we judge whether the decision
        # turned out right?" — separate from MPPS improvement window.
        "final_choice_option_id",
        "final_choice_reason",
        "final_choice_decided_at",
        "review_timeline_value",
        "review_timeline_unit",
    ):
        if k in body:
            cfg[k] = body[k]
    # Top-level analysis-scoped flags (kept outside config blob so the
    # wizard can read them as plain booleans from the analysis doc).
    extra: Dict[str, Any] = {}
    for k in ("step7_alpha_seeded",):
        if k in body:
            extra[k] = bool(body[k])
    await _persist(analysis_id, user["user_id"], {"config": cfg, **extra})
    return {"config": cfg, **extra}


# ─── Steps #7 + #8 — Assessment cell (per option per factor) ───
@router.put("/{analysis_id}/assessments/{option_id}/{factor_id}")
async def upsert_assessment(
    analysis_id: str, option_id: str, factor_id: str,
    body: Dict[str, Any], user: dict = Depends(get_current_user),
):
    """Update / create the cell that holds Step #7 + #8 values for one (option, factor).
    Body may include: assessment_pct, actual_value, satisfaction_pct, improvement_pct, notes.
    cell_value and satisfaction_value are derived server-side.

    CONCURRENCY: Uses MongoDB $set on individual nested fields, so two
    parallel PUTs from the frontend (e.g. DebouncedInput unmount-flushes for
    `actual_value` and `assessment_pct` firing simultaneously when navigating
    Step 7 → 8) do NOT clobber each other. Previously this route used a
    read-modify-write pattern (load full doc, mutate, persist), which caused
    the second writer to overwrite the first writer's field on race.
    """
    doc = await _load_analysis(analysis_id, user["user_id"])
    factor = next((f for f in doc["factors"] if f["id"] == factor_id), None)
    if not factor:
        raise HTTPException(status_code=404, detail="Factor not found")
    if not any(o["id"] == option_id for o in doc["options"]):
        raise HTTPException(status_code=404, detail="Option not found")

    # Build the field-level $set payload for ONLY the keys the client sent.
    # This is the key change — we never overwrite the full cell.
    allowed_keys = {"assessment_pct", "actual_value", "satisfaction_pct", "improvement_pct", "notes"}
    field_updates: Dict[str, Any] = {}
    for k in allowed_keys:
        if k in body:
            field_updates[f"assessments.{option_id}.{factor_id}.{k}"] = body[k]

    # If the cell doesn't exist yet, seed defaults so missing keys are
    # initialised — but only with the user's values + zeros (not with
    # values that could clobber a concurrent write).
    assessments = doc.get("assessments") or {}
    existing_cell = (assessments.get(option_id) or {}).get(factor_id)
    if not existing_cell:
        defaults = AssessmentCell().dict()
        for k, v in defaults.items():
            path = f"assessments.{option_id}.{factor_id}.{k}"
            if path not in field_updates:
                field_updates[path] = v

    if field_updates:
        await db.pros_cons.update_one(
            {"id": analysis_id, "user_id": user["user_id"]},
            {"$set": field_updates},
        )

    # Now re-read the cell post-$set to compute derived fields atomically.
    # Worst case: a concurrent writer's $set lands between our $set and read
    # → our derived values reflect the merged state (which is what we want).
    reread = await db.pros_cons.find_one(
        {"id": analysis_id, "user_id": user["user_id"]},
        {f"assessments.{option_id}.{factor_id}": 1},
    )
    cell = ((reread or {}).get("assessments", {}).get(option_id) or {}).get(factor_id) or AssessmentCell().dict()

    derived_cell_value = compute_cell_value(
        int(cell.get("assessment_pct", 0) or 0),
        int(factor.get("std_rating", 0) or 0),
    )
    derived_sat_value = compute_satisfaction_value(
        factor.get("realistic_rating") or factor.get("std_rating"),
        float(cell.get("satisfaction_pct", 0.0) or 0.0),
    )
    cell["cell_value"] = derived_cell_value
    cell["satisfaction_value"] = derived_sat_value

    await db.pros_cons.update_one(
        {"id": analysis_id, "user_id": user["user_id"]},
        {"$set": {
            f"assessments.{option_id}.{factor_id}.cell_value": derived_cell_value,
            f"assessments.{option_id}.{factor_id}.satisfaction_value": derived_sat_value,
            "updated_at": datetime.now(timezone.utc),
        }},
    )
    return {"cell": cell}


# ─── AI satisfaction assessment for a single (option, factor) cell ───
@router.post("/{analysis_id}/factors/{factor_id}/ai-assess")
async def ai_assess_cell(
    analysis_id: str, factor_id: str,
    body: Dict[str, Any], user: dict = Depends(get_current_user),
):
    """LLM-scored satisfaction % (0-100) for one (option, factor).

    Validation + actual-value resolution are delegated to core.ai_assess
    (shared with My Dezider for parity):
      * Quantitative → needs Expected + Operator + Actual (Unit optional).
      * Qualitative  → needs Expected only; AI fetches/infers the Actual.
      * Actual resolution: Data Source → linked Solution Store / ReviewNet → AI guess.
    """
    from core.ai_assess import ai_assess_factor

    doc = await _load_analysis(analysis_id, user["user_id"])
    factor = next((f for f in doc["factors"] if f["id"] == factor_id), None)
    if not factor:
        raise HTTPException(status_code=404, detail="Factor not found")
    option_id = body.get("option_id")
    option = next((o for o in doc["options"] if o["id"] == option_id), None)
    if not option:
        raise HTTPException(status_code=404, detail="Option not found")

    cell = ((doc.get("assessments") or {}).get(option_id) or {}).get(factor_id) or {}
    provided_actual = body.get("actual_value")
    if provided_actual is None or str(provided_actual).strip() == "":
        provided_actual = cell.get("actual_value")

    result = await ai_assess_factor(
        factor=factor,
        option=option,
        decision_title=doc.get("title") or doc.get("name") or "",
        decision_context=doc.get("context") or "",
        user_id=user["user_id"],
        provided_actual=provided_actual,
    )

    pct = result["assessment_pct"]
    final_actual = result.get("actual_value")
    derived_cell_value = compute_cell_value(pct, int(factor.get("std_rating", 0) or 0))
    set_doc = {
        f"assessments.{option_id}.{factor_id}.assessment_pct": pct,
        f"assessments.{option_id}.{factor_id}.cell_value": derived_cell_value,
        "updated_at": datetime.now(timezone.utc),
    }
    if final_actual is not None and str(final_actual).strip() != "":
        set_doc[f"assessments.{option_id}.{factor_id}.actual_value"] = str(final_actual)
    await db.pros_cons.update_one(
        {"id": analysis_id, "user_id": user["user_id"]},
        {"$set": set_doc},
    )
    return {
        "assessment_pct": pct,
        "cell_value": derived_cell_value,
        "actual_value": final_actual,
        "source": result.get("source"),
    }


# ─── XLS assessment template — export / import (Phase C) ───
def _ordered_factors_with_parent(doc: dict) -> List[Dict[str, Any]]:
    """Main factors each followed by their sub-factors, with parent_name."""
    factors = [f for f in doc["factors"] if not f.get("is_duplicate")]
    mains = [f for f in factors if not f.get("parent_id")]
    subs_by_parent: Dict[str, List[dict]] = {}
    for f in factors:
        if f.get("parent_id"):
            subs_by_parent.setdefault(f["parent_id"], []).append(f)

    def name_of(f):
        return f.get("display_name") or f.get("name") or ""

    ordered: List[Dict[str, Any]] = []
    for m in mains:
        ordered.append({"id": m["id"], "name": name_of(m), "parent_id": None,
                        "parent_name": "", "expected": m.get("expected_value") or m.get("target_value"),
                        "unit": m.get("unit") or ""})
        for s in subs_by_parent.get(m["id"], []):
            ordered.append({"id": s["id"], "name": name_of(s), "parent_id": m["id"],
                            "parent_name": name_of(m), "expected": s.get("expected_value") or s.get("target_value"),
                            "unit": s.get("unit") or ""})
    return ordered


@router.get("/{analysis_id}/assessment-template")
async def download_assessment_template(analysis_id: str, user: dict = Depends(get_current_user)):
    doc = await _load_analysis(analysis_id, user["user_id"])
    factors = _ordered_factors_with_parent(doc)
    options = [{"id": o["id"], "name": o.get("name") or "Option"} for o in doc["options"]]
    assessments = doc.get("assessments") or {}

    def get_cell(oid: str, fid: str) -> Dict[str, Any]:
        c = (assessments.get(oid) or {}).get(fid) or {}
        return {"actual": c.get("actual_value") or "", "pct": c.get("assessment_pct")}

    title = doc.get("title") or doc.get("name") or "Pros & Cons"
    data = build_template(title, factors, options, get_cell)
    safe = "".join(ch for ch in title if ch.isalnum() or ch in (" ", "-", "_")).strip()[:40] or "assessment"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{safe}-assessment.xlsx"'},
    )


@router.post("/{analysis_id}/assessment-import")
async def import_assessment_template(
    analysis_id: str, file: UploadFile = File(...), user: dict = Depends(get_current_user),
):
    doc = await _load_analysis(analysis_id, user["user_id"])
    valid_factor_ids = {f["id"] for f in doc["factors"]}
    valid_option_ids = {o["id"] for o in doc["options"]}
    std_by_factor = {f["id"]: int(f.get("std_rating", 0) or 0) for f in doc["factors"]}

    try:
        raw = await file.read()
        rows = parse_template(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read the file: {e}")

    field_updates: Dict[str, Any] = {}
    applied = 0
    for r in rows:
        fid = r.get("factor_id")
        oid = r.get("option_id")
        if fid not in valid_factor_ids or oid not in valid_option_ids:
            continue
        base = f"assessments.{oid}.{fid}"
        if "actual" in r:
            field_updates[f"{base}.actual_value"] = r["actual"]
        if "assessment_pct" in r:
            pct = int(r["assessment_pct"])
            field_updates[f"{base}.assessment_pct"] = pct
            field_updates[f"{base}.cell_value"] = compute_cell_value(pct, std_by_factor.get(fid, 0))
        if "actual" in r or "assessment_pct" in r:
            applied += 1

    if field_updates:
        field_updates["updated_at"] = datetime.now(timezone.utc)
        await db.pros_cons.update_one(
            {"id": analysis_id, "user_id": user["user_id"]}, {"$set": field_updates},
        )
    return {"applied": applied, "rows": len(rows)}


@router.post("/{analysis_id}/assessment-gsheet")
async def create_assessment_gsheet(analysis_id: str, user: dict = Depends(get_current_user)):
    """Create a Google Sheet (in the user's own Drive) pre-filled with the
    assessment template. Returns {url, spreadsheet_id}. Requires the user to
    have connected Google (see /api/oauth/sheets/login)."""
    doc = await _load_analysis(analysis_id, user["user_id"])
    factors = _ordered_factors_with_parent(doc)
    options = [{"id": o["id"], "name": o.get("name") or "Option"} for o in doc["options"]]
    assessments = doc.get("assessments") or {}

    def get_cell(oid: str, fid: str) -> Dict[str, Any]:
        c = (assessments.get(oid) or {}).get(fid) or {}
        return {"actual": c.get("actual_value") or "", "pct": c.get("assessment_pct")}

    title = doc.get("title") or doc.get("name") or "Pros & Cons"
    matrix = build_value_matrix(factors, options, get_cell)
    try:
        res = await gs.create_assessment_sheet(user["user_id"], title, matrix)
    except PermissionError as e:
        raise HTTPException(status_code=428, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not create the Google Sheet: {e}")
    await db.pros_cons.update_one(
        {"id": analysis_id, "user_id": user["user_id"]},
        {"$set": {"gsheet_id": res["spreadsheet_id"], "gsheet_url": res["url"], "updated_at": datetime.now(timezone.utc)}},
    )
    return res


@router.post("/{analysis_id}/assessment-gsheet/import")
async def import_assessment_gsheet(analysis_id: str, body: Optional[Dict[str, Any]] = None, user: dict = Depends(get_current_user)):
    """Read back the linked (or provided) Google Sheet and apply the filled
    Actual/Assess % values. body may include {spreadsheet_id} to override."""
    doc = await _load_analysis(analysis_id, user["user_id"])
    spreadsheet_id = (body or {}).get("spreadsheet_id") or doc.get("gsheet_id")
    if not spreadsheet_id:
        raise HTTPException(status_code=400, detail="No Google Sheet linked. Create one first.")
    valid_factor_ids = {f["id"] for f in doc["factors"]}
    valid_option_ids = {o["id"] for o in doc["options"]}
    std_by_factor = {f["id"]: int(f.get("std_rating", 0) or 0) for f in doc["factors"]}

    try:
        values = await gs.read_assessment_sheet(user["user_id"], spreadsheet_id)
        rows = parse_rows(values)
    except PermissionError as e:
        raise HTTPException(status_code=428, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read the Google Sheet: {e}")

    field_updates: Dict[str, Any] = {}
    applied = 0
    for r in rows:
        fid = r.get("factor_id")
        oid = r.get("option_id")
        if fid not in valid_factor_ids or oid not in valid_option_ids:
            continue
        base = f"assessments.{oid}.{fid}"
        if "actual" in r:
            field_updates[f"{base}.actual_value"] = r["actual"]
        if "assessment_pct" in r:
            pct = int(r["assessment_pct"])
            field_updates[f"{base}.assessment_pct"] = pct
            field_updates[f"{base}.cell_value"] = compute_cell_value(pct, std_by_factor.get(fid, 0))
        if "actual" in r or "assessment_pct" in r:
            applied += 1

    if field_updates:
        field_updates["updated_at"] = datetime.now(timezone.utc)
        await db.pros_cons.update_one(
            {"id": analysis_id, "user_id": user["user_id"]}, {"$set": field_updates},
        )
    return {"applied": applied, "rows": len(rows)}


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

