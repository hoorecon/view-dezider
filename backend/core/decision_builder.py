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
from fastapi import HTTPException
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
            factor_type=f.get("factor_type"),
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



# ---------------------------------------------------------------------------
# MERGE crawled factors + options into an EXISTING MyDezider decision
# (used by Step 2 "Import from URL"). Appends new factors (with suggested
# Expected values) and new options (with assessment % where derivable), so the
# user lands with Step 2 factors filled, Step 6 options pre-filled and Step 7
# half-filled. Existing factors/options are matched by name (case-insensitive)
# and reused rather than duplicated.
# ---------------------------------------------------------------------------
async def merge_into_mydezider(
    user_id: str, decision_id: str, *,
    factors: List[Dict[str, Any]], candidates: List[Dict[str, Any]],
) -> Dict[str, int]:
    decision = await db.decisions.find_one({"id": decision_id, "user_id": user_id}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    ex_factors: List[Dict[str, Any]] = decision.get("factors", []) or []
    ex_options: List[Dict[str, Any]] = decision.get("options", []) or []

    name_to_id: Dict[str, str] = {}
    for f in ex_factors:
        nm = str(f.get("name") or "").strip().lower()
        if nm:
            name_to_id[nm] = f["id"]

    order_base = len(ex_factors)
    factors_added = 0
    import_name_to_id: Dict[str, str] = {}
    for f in factors:
        key = str(f["name"]).strip().lower()
        if key in name_to_id:
            fid = name_to_id[key]
            # fill a missing Expected value on the existing factor if we have one
            existing = next((x for x in ex_factors if x["id"] == fid), None)
            if existing is not None and not _pct_present(existing.get("expected_value")) and _pct_present(f.get("expected_value")):
                existing["expected_value"] = f.get("expected_value")
                if f.get("operator") and not existing.get("operator"):
                    existing["operator"] = f.get("operator")
        else:
            fid = f"f_{uuid.uuid4().hex[:8]}"
            ex_factors.append(Factor(
                id=fid, name=f["name"], category="primary", rating=_rating(f.get("weight")),
                order=order_base + factors_added, unit=f.get("unit"),
                expected_value=f.get("expected_value"),
                data_type=("text" if (f.get("data_type") == "text") else "numeric"),
                factor_type=f.get("factor_type"),
                operator=f.get("operator"),
            ).dict())
            name_to_id[key] = fid
            factors_added += 1
        import_name_to_id[f["name"]] = fid

    ex_opt_names = {str(o.get("name") or "").strip().lower() for o in ex_options}
    total_rating = sum(int(fc.get("rating") or 0) for fc in ex_factors) or 1
    rating_by_id = {fc["id"]: int(fc.get("rating") or 0) for fc in ex_factors}

    options_added = 0
    for c in candidates:
        nm = str(c.get("name") or "").strip()
        if not nm or nm.lower() in ex_opt_names:
            continue
        scores = c.get("scores") or {}
        unit_values = c.get("unit_values") or {}
        assessments: List[OptionAssessment] = []
        worth = 0.0
        for fname, fid in import_name_to_id.items():
            pct = _pct_int(scores.get(fname))
            uv = unit_values.get(fname)
            uv = str(uv).strip() if uv not in (None, "") else None
            if pct is None and uv is None:
                continue
            assessments.append(OptionAssessment(
                factor_id=fid, percentage=pct, unit_value=uv, assessment_mode="manual"))
            if pct is not None:
                worth += (rating_by_id.get(fid, 0) / total_rating) * pct
        ex_options.append(DecisionOption(
            name=nm, assessments=assessments,
            worth_percentage=round(min(100.0, max(0.0, worth)), 2), source="manual",
        ).dict())
        ex_opt_names.add(nm.lower())
        options_added += 1

    await db.decisions.update_one(
        {"id": decision_id, "user_id": user_id},
        {"$set": {"factors": ex_factors, "options": ex_options, "updated_at": _now()}},
    )
    return {"factors_added": factors_added, "options_added": options_added}


def _pct_present(v: Any) -> bool:
    return v is not None and str(v).strip() != ""


# ---------------------------------------------------------------------------
# Hierarchical (TWO-LEVEL) MyDezider build from a parsed comparison matrix.
# Each category -> a primary PARENT factor; each spec row -> a SUB-factor
# (parent_id set, weight split equally). Options carry LEAF assessments
# (percentage + the raw spec value as unit_value). Worth mirrors the frontend's
# effectiveFactorPct() so the stored worth matches what the UI recomputes.
# ---------------------------------------------------------------------------
def _effective_pct(parent: Factor, subs: List[Factor],
                   pct_by_fid: Dict[str, Optional[int]]) -> Optional[float]:
    if not subs:
        return pct_by_fid.get(parent.id)
    assessed = [(s, pct_by_fid[s.id]) for s in subs
                if s.id in pct_by_fid and pct_by_fid[s.id] is not None]
    if not assessed:
        return pct_by_fid.get(parent.id)
    tw = sum((s.weight or 0) for s, _ in assessed)
    if tw > 0:
        wsum = sum(p * (s.weight or 0) / 100.0 for s, p in assessed)
        return wsum * (100.0 / tw)
    return sum(p for _, p in assessed) / len(assessed)


def _hier_worth(parents: List[Factor], factors: List[Factor],
                assessments: List[OptionAssessment]) -> float:
    pct_by_fid = {a.factor_id: a.percentage for a in assessments}
    total_rating = sum(p.rating for p in parents) or 1
    weighted = 0.0
    for p in parents:
        subs = [f for f in factors if f.parent_id == p.id]
        eff = _effective_pct(p, subs, pct_by_fid)
        if eff is not None:
            weighted += p.rating * (eff / 100.0)
    return round(min(100.0, max(0.0, weighted / total_rating * 100.0)), 2)


async def create_hierarchical_mydezider(
    user_id: str, *, title: str, context: str = "",
    life_area: Optional[str] = None, decision_type: Optional[str] = None,
    items: List[str], groups: List[Dict[str, Any]],
    row_scores: Dict[Any, List[Optional[float]]],
    row_meta: Dict[Any, Dict[str, Any]],
    source_label: Optional[str] = None,
) -> Dict[str, Any]:
    built_factors: List[Factor] = []
    submap: Dict[Any, str] = {}
    for gi, g in enumerate(groups):
        pid = f"f_{uuid.uuid4().hex[:8]}"
        built_factors.append(Factor(
            id=pid, name=str(g["category"]), category="primary",
            rating=50, order=gi, parent_id=None,
        ))
        subs = g.get("rows") or []
        n_sub = len(subs)
        base_w = round(100.0 / n_sub, 2) if n_sub else 0
        for ri, row in enumerate(subs):
            sid = f"f_{uuid.uuid4().hex[:8]}"
            submap[(gi, ri)] = sid
            meta = row_meta.get((gi, ri), {})
            is_num = bool(meta.get("is_numeric"))
            # Last sub absorbs the rounding remainder so weights sum to EXACTLY 100.
            weight = round(100.0 - base_w * (n_sub - 1), 2) if ri == n_sub - 1 else base_w
            built_factors.append(Factor(
                id=sid, name=str(row["label"]), category="primary",
                parent_id=pid, order=ri, weight=weight,
                data_type="numeric" if is_num else "text",
                factor_type=meta.get("factor_type"),
                expected_value=meta.get("expected"), operator=meta.get("operator"),
                unit=meta.get("unit"),
            ))

    parents = [f for f in built_factors if f.parent_id is None]
    built_options: List[DecisionOption] = []
    for ii, item in enumerate(items):
        assessments: List[OptionAssessment] = []
        for gi, g in enumerate(groups):
            for ri, row in enumerate(g.get("rows") or []):
                sid = submap[(gi, ri)]
                vals = row.get("values") or []
                raw = vals[ii].strip() if ii < len(vals) else ""
                sc = row_scores.get((gi, ri))
                pct = _pct_int(sc[ii]) if (sc and ii < len(sc)) else None
                if pct is None and not raw:
                    continue
                assessments.append(OptionAssessment(
                    factor_id=sid, percentage=pct,
                    unit_value=(raw or None), assessment_mode="manual"))
        worth = _hier_worth(parents, built_factors, assessments)
        built_options.append(DecisionOption(
            name=str(item or "Option"), assessments=assessments,
            worth_percentage=worth, source="manual"))

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
    return {
        "id": decision.id,
        "category_count": len(parents),
        "subfactor_count": len(built_factors) - len(parents),
        "option_count": len(built_options),
    }



def _hier_worth_dicts(factors: List[Dict[str, Any]],
                      assessments: List[OptionAssessment]) -> float:
    """Worth roll-up over dict-form factors (mirrors _hier_worth / the frontend)."""
    pct_by_fid = {a.factor_id: a.percentage for a in assessments}
    parents = [f for f in factors if not f.get("parent_id")]
    total_rating = sum(int(p.get("rating") or 0) for p in parents) or 1
    weighted = 0.0
    for p in parents:
        subs = [f for f in factors if f.get("parent_id") == p["id"]]
        if subs:
            assessed = [(s, pct_by_fid[s["id"]]) for s in subs
                        if s["id"] in pct_by_fid and pct_by_fid[s["id"]] is not None]
            if assessed:
                tw = sum(int(s.get("weight") or 0) for s, _ in assessed)
                if tw > 0:
                    eff = sum(pp * (int(s.get("weight") or 0)) / 100.0
                              for s, pp in assessed) * (100.0 / tw)
                else:
                    eff = sum(pp for _, pp in assessed) / len(assessed)
            else:
                eff = pct_by_fid.get(p["id"])
        else:
            eff = pct_by_fid.get(p["id"])
        if eff is not None:
            weighted += int(p.get("rating") or 0) * (eff / 100.0)
    return round(min(100.0, max(0.0, weighted / total_rating * 100.0)), 2)


async def merge_hierarchical_into_mydezider(
    user_id: str, decision_id: str, *,
    items: List[str], groups: List[Dict[str, Any]],
    row_scores: Dict[Any, List[Optional[int]]],
    row_meta: Dict[Any, Dict[str, Any]],
) -> Dict[str, int]:
    """Step-2 "Import from URL" for a category-grouped comparison matrix:
    MERGE the FULL two-level structure (parent factors + sub-factors + options
    with leaf assessments) into an EXISTING MyDezider decision. Name-matches to
    avoid duplicating parents / sub-factors / options on re-import."""
    decision = await db.decisions.find_one({"id": decision_id, "user_id": user_id}, {"_id": 0})
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    ex_factors: List[Dict[str, Any]] = decision.get("factors", []) or []
    ex_options: List[Dict[str, Any]] = decision.get("options", []) or []

    parent_by_name = {str(f.get("name") or "").strip().lower(): f["id"]
                      for f in ex_factors if not f.get("parent_id")}
    order_base = len([f for f in ex_factors if not f.get("parent_id")])
    factors_added = 0
    submap: Dict[Any, str] = {}

    for gi, g in enumerate(groups):
        cat = str(g["category"]).strip()
        pkey = cat.lower()
        pid = parent_by_name.get(pkey)
        if not pid:
            pid = f"f_{uuid.uuid4().hex[:8]}"
            ex_factors.append(Factor(
                id=pid, name=cat, category="primary", rating=50,
                order=order_base + gi, parent_id=None,
            ).dict())
            parent_by_name[pkey] = pid
            factors_added += 1
        sub_by_name = {str(f.get("name") or "").strip().lower(): f["id"]
                       for f in ex_factors if f.get("parent_id") == pid}
        subs = g.get("rows") or []
        n_sub = len(subs)
        base_w = round(100.0 / n_sub, 2) if n_sub else 0
        for ri, row in enumerate(subs):
            label = str(row["label"]).strip()
            meta = row_meta.get((gi, ri), {})
            is_num = bool(meta.get("is_numeric"))
            weight = round(100.0 - base_w * (n_sub - 1), 2) if ri == n_sub - 1 else base_w
            sid = sub_by_name.get(label.lower())
            if not sid:
                sid = f"f_{uuid.uuid4().hex[:8]}"
                ex_factors.append(Factor(
                    id=sid, name=label, category="primary",
                    parent_id=pid, order=ri, weight=weight,
                    data_type="numeric" if is_num else "text",
                    factor_type=meta.get("factor_type"),
                    expected_value=meta.get("expected"), operator=meta.get("operator"),
                    unit=meta.get("unit"),
                ).dict())
                factors_added += 1
            submap[(gi, ri)] = sid

    ex_opt_names = {str(o.get("name") or "").strip().lower() for o in ex_options}
    options_added = 0
    for ii, item in enumerate(items):
        nm = str(item or "Option").strip()
        if not nm or nm.lower() in ex_opt_names:
            continue
        assessments: List[OptionAssessment] = []
        for gi, g in enumerate(groups):
            for ri, row in enumerate(g.get("rows") or []):
                sid = submap.get((gi, ri))
                if not sid:
                    continue
                vals = row.get("values") or []
                raw = vals[ii].strip() if ii < len(vals) else ""
                sc = row_scores.get((gi, ri))
                pct = _pct_int(sc[ii]) if (sc and ii < len(sc)) else None
                if pct is None and not raw:
                    continue
                assessments.append(OptionAssessment(
                    factor_id=sid, percentage=pct,
                    unit_value=(raw or None), assessment_mode="manual"))
        worth = _hier_worth_dicts(ex_factors, assessments)
        ex_options.append(DecisionOption(
            name=nm, assessments=assessments,
            worth_percentage=worth, source="manual").dict())
        ex_opt_names.add(nm.lower())
        options_added += 1

    await db.decisions.update_one(
        {"id": decision_id, "user_id": user_id},
        {"$set": {"factors": ex_factors, "options": ex_options, "updated_at": _now()}},
    )
    parents_now = [f for f in ex_factors if not f.get("parent_id")]
    return {
        "factors_added": factors_added,
        "options_added": options_added,
        "category_count": len(parents_now),
        "subfactor_count": len(ex_factors) - len(parents_now),
    }