"""Build a MyDezider decision or a Pros & Cons analysis from a list of
pre-scored candidates + factors.

Shared by:
  • the Screener → "Send to MyDezider / Pros & Cons" bridge, and
  • the standalone "Analyse a URL" feature.

Inputs are framework-agnostic:
  factors    : [{name, data_type, expected_value?, operator?, unit?, weight}]
  candidates : [{name, scores: {factor_name: pct|None}, attributes?: {..}}]
               (`scores` keyed by factor NAME; pct is 0..100 or None)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.database import db
from models.decisions_models import PRRDecision, Factor, DecisionOption, OptionAssessment
from models.decision_framework_models import (
    FrameworkFactor, FrameworkConfig, AssessmentCell,
    compute_cell_value, compute_option_rollups,
)
from routes.decisions.services import consume_entitlement


def _now():
    return datetime.now(timezone.utc)


def _rating(weight: Any) -> int:
    try:
        return max(1, min(100, int(round(float(weight)))))
    except (TypeError, ValueError):
        return 50


def _pct_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return max(0, min(100, int(round(float(v)))))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# MyDezider (db.decisions)
# ---------------------------------------------------------------------------
async def create_mydezider_from_candidates(
    user_id: str, *, title: str, context: str = "",
    life_area: Optional[str] = None, decision_type: Optional[str] = None,
    factors: List[Dict[str, Any]], candidates: List[Dict[str, Any]],
    source_label: Optional[str] = None,
) -> str:
    built_factors: List[Factor] = []
    name_to_id: Dict[str, str] = {}
    for i, f in enumerate(factors):
        fid = f.get("id") or f"f_{uuid.uuid4().hex[:8]}"
        name_to_id[f["name"]] = fid
        built_factors.append(Factor(
            id=fid, name=f["name"], category="primary", rating=_rating(f.get("weight")),
            order=i, unit=f.get("unit"), expected_value=f.get("expected_value"),
            data_type=("text" if (f.get("data_type") == "text") else "numeric"),
            operator=f.get("operator"),
        ))

    total_rating = sum(fc.rating for fc in built_factors) or 1
    built_options: List[DecisionOption] = []
    for c in candidates:
        scores = c.get("scores") or {}
        assessments: List[OptionAssessment] = []
        worth = 0.0
        for fc in built_factors:
            pct = _pct_int(scores.get(fc.name))
            if pct is None:
                continue
            assessments.append(OptionAssessment(
                factor_id=fc.id, percentage=pct, assessment_mode="manual"))
            worth += (fc.rating / total_rating) * pct
        built_options.append(DecisionOption(
            name=str(c.get("name") or "Option"), assessments=assessments,
            worth_percentage=round(min(100.0, max(0.0, worth)), 2), source="manual"))

    decision = PRRDecision(
        user_id=user_id, title=title, context=context or (source_label or ""),
        life_area=life_area, decision_type=decision_type,
        factors=built_factors, options=built_options, status="draft",
    )
    doc = decision.dict()
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    doc["org_id"] = user_doc.get("org_id") if user_doc else None
    doc["source_module"] = source_label or "url_analyze"
    await db.decisions.insert_one(doc)
    await consume_entitlement(user_id, decision.id, context="create")
    return decision.id


# ---------------------------------------------------------------------------
# Pros & Cons (db.pros_cons)
# ---------------------------------------------------------------------------
async def create_pros_cons_from_candidates(
    user_id: str, *, title: str, context: str = "",
    life_area: Optional[str] = None, decision_type: Optional[str] = None,
    factors: List[Dict[str, Any]], candidates: List[Dict[str, Any]],
    source_label: Optional[str] = None,
) -> str:
    built_factors: List[Dict[str, Any]] = []
    for i, f in enumerate(factors):
        fid = f.get("id") or f"f_{uuid.uuid4().hex[:8]}"
        ff = FrameworkFactor(
            id=fid, name=f["name"], expected_value=f.get("expected_value"),
            unit=f.get("unit"), priority_rank=i + 1, std_rating=_rating(f.get("weight")),
        )
        d = ff.dict()
        d["_name"] = f["name"]
        built_factors.append(d)

    built_options: List[Dict[str, Any]] = []
    assessments: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for c in candidates:
        opt = DecisionOption(name=str(c.get("name") or "Option"))
        od = opt.dict()
        built_options.append(od)
        scores = c.get("scores") or {}
        cell_map: Dict[str, Dict[str, Any]] = {}
        for fd in built_factors:
            pct = _pct_int(scores.get(fd["_name"]))
            if pct is None:
                continue
            std = fd.get("std_rating") or 0
            cell = AssessmentCell(
                assessment_pct=pct, cell_value=compute_cell_value(pct, std))
            cell_map[fd["id"]] = cell.dict()
        assessments[od["id"]] = cell_map

    for fd in built_factors:
        fd.pop("_name", None)

    config = FrameworkConfig().dict()
    try:
        rollups = compute_option_rollups(built_factors, assessments, built_options, config)
    except Exception:
        rollups = []

    now = _now()
    doc = {
        "id": str(uuid.uuid4()), "user_id": user_id, "title": title,
        "context": context or (source_label or ""), "life_area": life_area,
        "decision_type": decision_type, "pros": [], "cons": [],
        "options": built_options, "factors": built_factors, "assessments": assessments,
        "config": config, "current_step": 7, "rollups": rollups,
        "converted_decision_id": None, "source_module": source_label or "url_analyze",
        "created_at": now, "updated_at": now,
    }
    await db.pros_cons.insert_one(doc)
    return doc["id"]
