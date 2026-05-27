"""
8-step Pros & Cons / SWOT decision framework models — shared by routes/pros_cons.py
and routes/swot.py.

The framework mirrors the user's "REFERENCE Career Consultation" workbook:
  Step #1  List initial Direct Factors
  Step #2  List Options + per-option Pros & Cons
  Step #3  Convert Pros & Cons into factors  (Cons prefixed with "SHOULD NOT - ")
  Step #4  Manual dedup / group factors (assign parent for sub-factor)
  Step #5  Collapse / expand sub-factor view
  Step #6  Notation: Mandatory vs Optional (+ optional knock-out threshold)
  Step #7  Prioritization: drag-reorder + Std Rating + Assessment%
           Cell Value = Assessment% x Std Rating
  Step #8  Full assessment per factor + per option:
             factor_type (subjective|objective), improvable (y|y_bf|n),
             my_expectation / others_expectations / market_standard,
             realistic_gap_pct, realistic_gap_value, realistic_rating,
             actual_value, satisfaction_pct, improvement_pct, satisfaction_value
           Per-option overall_satisfaction_pct (Step #8.10)
  Final Decision Guidelines — shown as a reference panel after Step #8.
"""

import uuid
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────
# Per-option Pros & Cons (Step #2)
# ─────────────────────────────────────────────────────────────

class ProConItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    description: str = ""
    importance: int = 5            # 1-10
    promoted_factor_id: Optional[str] = None   # set after Step #3 promotion


class DecisionOption(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    pros: List[ProConItem] = []
    cons: List[ProConItem] = []
    order: int = 0


# ─────────────────────────────────────────────────────────────
# Consolidated Factor (Steps #1, #3, #4, #5, #6, #7, #8)
# ─────────────────────────────────────────────────────────────

class FrameworkFactor(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    # Step #1.1 — expected value + unit (becomes mandatory at the end of Step #3
    # once the consolidated list is finalised; left optional during data entry).
    expected_value: Optional[str] = None
    unit: Optional[str] = None
    # Step #3.2 — provenance
    source: Literal["direct", "pro", "con"] = "direct"
    source_option_id: Optional[str] = None          # which option's P/C produced this
    source_item_id: Optional[str] = None
    # Step #4 / #5 — hierarchy
    parent_id: Optional[str] = None                 # if set, this is a sub-factor
    # Step #6.1 — notation (Mandatory vs Optional)
    notation: Literal["mandatory", "optional"] = "optional"
    # Step #7.1 — priority rank (1 = highest)
    priority_rank: int = 0
    # Step #7 / #8 — standard rating (0-100)  anchor
    std_rating: int = 50
    # Step #8 — assessment metadata
    factor_type: Literal["subjective", "objective"] = "subjective"
    improvable: Literal["y", "y_bf", "n"] = "n"
    my_expectation: Optional[str] = None
    others_expectations: Optional[str] = None
    market_standard: Optional[str] = None
    realistic_gap_pct: float = 0.0                  # e.g. 0.10 = 10% improvable
    realistic_gap_value: float = 0.0                # absolute units derived
    realistic_rating: Optional[int] = None          # std_rating * (1 + gap_pct)
    notes: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# Per-option per-factor assessment cell  (Steps #7 + #8)
# ─────────────────────────────────────────────────────────────

class AssessmentCell(BaseModel):
    assessment_pct: int = 0                # Step #7.2 — % match
    cell_value: float = 0.0                # = assessment_pct * std_rating / 100
    # Step #8
    actual_value: Optional[str] = None
    satisfaction_pct: float = 0.0          # 0..1
    improvement_pct: float = 0.0           # 0..1
    satisfaction_value: float = 0.0        # realistic_rating * satisfaction_pct
    notes: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# Decision-level config & rollups
# ─────────────────────────────────────────────────────────────

class FrameworkConfig(BaseModel):
    # Step #6.2 — optional knock-out threshold
    mandatory_threshold_pct: Optional[int] = None
    # Step #8.9 — header constants
    max_improvement_period_months: int = 6
    std_gap: int = 10
    # gap bands kept for label clarity (Low/Standard/High/Double @ 50/100/150/200%)
    gap_bands: Dict[str, int] = Field(
        default_factory=lambda: {"low": 50, "standard": 100, "high": 150, "double": 200}
    )


class OptionRollup(BaseModel):
    option_id: str
    overall_satisfaction_pct: float = 0.0   # Step #8.10
    joint_score: float = 0.0                # Step #7.2 sum
    rank_high_to_low: Optional[int] = None
    disqualified: bool = False              # any mandatory below threshold
    disqualifying_factor_ids: List[str] = []


# ─────────────────────────────────────────────────────────────
# Final Decision Guidelines (12 reference rules from the Excel)
# ─────────────────────────────────────────────────────────────

FINAL_DECISION_GUIDELINES: List[Dict[str, Any]] = [
    {"rank": 1,  "rule": "Timeline to decide — some opportunities lapse if not taken in time.",                   "type": "timing"},
    {"rank": 2,  "rule": "Effective time period of the decision (impact horizon).",                                "type": "timing"},
    {"rank": 3,  "rule": "Is the factor worth considering in this specific decision context?",                    "type": "factor_review"},
    {"rank": 4,  "rule": "Expected value of those factors — recheck realism.",                                     "type": "factor_review"},
    {"rank": 5,  "rule": "Primary/Secondary  and  Mandatory/Optional  classification revisit.",                    "type": "classification"},
    {"rank": 6,  "rule": "Prioritization of factors (drag-reorder once more).",                                    "type": "classification"},
    {"rank": 7,  "rule": "Realistic gap analysis — is improvement actually feasible in the chosen window?",        "type": "gap"},
    {"rank": 8,  "rule": "Actual value of any key factor where confidence is low — verify via data/expert.",       "type": "evidence"},
    {"rank": 9,  "rule": "Assessment % of that factor on that option — recheck subjective scores.",                "type": "evidence"},
    {"rank": 10, "rule": "Review Primary-factor matching % AND Secondary-factor matching % vs overall %.",         "type": "review"},
    {"rank": 11, "rule": "Case 2A — analyse positive sequencing of events (if X happens before Y, options shift).","type": "scenario"},
    {"rank": 12, "rule": "Case 2B — alternative positive sequencing chain.",                                        "type": "scenario"},
]


# ─────────────────────────────────────────────────────────────
# Helpers — compute rollups
# ─────────────────────────────────────────────────────────────

def compute_realistic_rating(std_rating: int, realistic_gap_pct: float) -> int:
    """Step #8.5 — derived field."""
    try:
        return int(round(std_rating * (1.0 + (realistic_gap_pct or 0.0))))
    except Exception:
        return std_rating


def compute_cell_value(assessment_pct: int, std_rating: int) -> float:
    """Step #7.2 — Cell Value = Assessment% x Std Rating / 100."""
    try:
        return round((assessment_pct or 0) * (std_rating or 0) / 100.0, 2)
    except Exception:
        return 0.0


def compute_satisfaction_value(realistic_rating: Optional[int], satisfaction_pct: float) -> float:
    """Step #8.8 — Satisfaction Value = Realistic Rating x % Satisfaction."""
    try:
        rr = realistic_rating if realistic_rating is not None else 0
        return round(rr * (satisfaction_pct or 0.0), 2)
    except Exception:
        return 0.0


def compute_option_rollups(
    factors: List[Dict[str, Any]],
    assessments: Dict[str, Dict[str, Dict[str, Any]]],
    options: List[Dict[str, Any]],
    config: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Compute per-option:
      • joint_score  = sum(cell_value) across factors           (Step #7)
      • overall_satisfaction_pct = sum(sat_val) / sum(realistic_rating) * 100   (Step #8.10)
      • disqualified = any mandatory factor's assessment_pct < threshold        (Step #6.2)
      • rank_high_to_low                                                         (Step #7.4)
    """
    cfg = config or {}
    mt = cfg.get("mandatory_threshold_pct")
    rollups: List[Dict[str, Any]] = []

    # Only score MAIN factors:
    #   - exclude sub-factors (parent_id is set)  → they are rated implicitly
    #     by their parent in Steps 6/7/8 per the wizard UI contract
    #   - exclude duplicates (is_duplicate=True)  → audit history, not active
    scoring_factors = [
        f for f in factors
        if not f.get("parent_id") and not f.get("is_duplicate")
    ]

    for opt in options:
        opt_id = opt.get("id")
        opt_asmts = (assessments or {}).get(opt_id, {})

        joint_score = 0.0
        sat_val_sum = 0.0
        max_sat_val_sum = 0.0
        dq = False
        dq_factor_ids: List[str] = []

        for f in scoring_factors:
            cell = opt_asmts.get(f["id"], {}) or {}
            joint_score += float(cell.get("cell_value", 0) or 0)
            sat_val_sum += float(cell.get("satisfaction_value", 0) or 0)
            rr = f.get("realistic_rating") or f.get("std_rating") or 0
            max_sat_val_sum += float(rr)

            # Step #6.2 — knock out
            if mt is not None and f.get("notation") == "mandatory":
                a_pct = int(cell.get("assessment_pct", 0) or 0)
                if a_pct < int(mt):
                    dq = True
                    dq_factor_ids.append(f["id"])

        overall = (sat_val_sum / max_sat_val_sum * 100.0) if max_sat_val_sum > 0 else 0.0
        rollups.append({
            "option_id": opt_id,
            "joint_score": round(joint_score, 2),
            "overall_satisfaction_pct": round(overall, 2),
            "disqualified": dq,
            "disqualifying_factor_ids": dq_factor_ids,
        })

    # Step #7.4 — rank surviving options (qualified first) high-to-low by overall sat%
    surviving = [r for r in rollups if not r["disqualified"]]
    disqualified = [r for r in rollups if r["disqualified"]]
    surviving.sort(key=lambda x: x["overall_satisfaction_pct"], reverse=True)
    for i, r in enumerate(surviving):
        r["rank_high_to_low"] = i + 1
    for r in disqualified:
        r["rank_high_to_low"] = None
    return surviving + disqualified
