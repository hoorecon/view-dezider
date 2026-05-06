"""
AALA — Accrued Assets & Liabilities Analysis.

Resource ledger across TEPFI × {Self, Micro, Macro} = 15 cells.
Each cell holds:
  • assets_summary  — short text describing what's accrued (positive resources)
  • liabilities_summary — what you owe / negative drag
  • balance_score   — net signed score on -10..+10 scale (user-tunable)
  • assets[]        — itemised list (each: id, label, value, units, since)
  • liabilities[]   — itemised list (each: id, label, value, units, due)
  • last_updated

A delta journal logs every change so we can compute trends and surface drift.

When the SAME data shape is scoped to a specific problem, it becomes a row in
the existing Solution Matrix (same TEPFI factors, same Self/Micro/Macro layers).
AALA = the live, ongoing personal ledger; Solution Matrix = problem-snapshots.
"""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


TEPFI = ["time", "energy", "people", "finance", "infrastructure"]
LEVELS = ["self", "micro", "macro"]


class AssetItem(BaseModel):
    item_id: str
    label: str
    value: float = 0.0                       # numeric magnitude (units interpret it)
    units: Optional[str] = None              # 'hrs/week', 'INR', 'people', 'tokens'
    since: Optional[datetime] = None
    notes: Optional[str] = None


class LiabilityItem(BaseModel):
    item_id: str
    label: str
    value: float = 0.0
    units: Optional[str] = None
    due: Optional[datetime] = None
    notes: Optional[str] = None


class AALACell(BaseModel):
    """One TEPFI × level cell."""
    factor: str                              # one of TEPFI
    level: str                               # one of LEVELS
    assets_summary: str = ""
    liabilities_summary: str = ""
    balance_score: float = 0.0               # -10..+10, signed
    assets: List[AssetItem] = Field(default_factory=list)
    liabilities: List[LiabilityItem] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AALADoc(BaseModel):
    user_id: str
    cells: List[AALACell] = Field(default_factory=list)   # 15 entries
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AALADelta(BaseModel):
    """Append-only journal entry — every cell update writes one of these."""
    delta_id: str
    user_id: str
    factor: str                              # 'time', 'energy', etc.
    level: str                               # 'self', 'micro', 'macro'
    kind: str                                # 'asset_add' | 'asset_remove' | 'liability_add' | 'liability_remove' | 'balance_set' | 'summary_edit'
    delta_value: float = 0.0
    description: Optional[str] = None
    source: str = "manual"                   # 'manual' | 'voice' | 'ai_classified' | 'daily_tracker' | 'expert_recommendation'
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def seed_empty_cells() -> List[Dict[str, Any]]:
    """Initialise the 15 TEPFI × level cells empty."""
    out = []
    for factor in TEPFI:
        for level in LEVELS:
            out.append({
                "factor": factor, "level": level,
                "assets_summary": "", "liabilities_summary": "",
                "balance_score": 0.0,
                "assets": [], "liabilities": [],
                "last_updated": datetime.now(timezone.utc),
            })
    return out
