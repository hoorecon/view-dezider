"""
Life Directions Compass (LDC) — personal ranked list of life freedoms.

Default seed (7): Business, Financial, Time, Health, Emotional, Social, Mission.
3 reserved (suggested but not seeded): Sexual, Spiritual, Eternal — added by user.

Weight auto-computed from rank: rank 1 -> 10.0, rank N -> max(1.0, 11 - rank).
This-week pin (Q2c hybrid): one freedom can be pinned for the current week,
granting it a hard-priority multiplier (1.5x) inside Time Dezider.
"""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# Default 7-freedom seed (in default rank order)
DEFAULT_FREEDOMS = [
    {"key": "business", "label": "Business Freedom", "icon": "briefcase", "color": "#7C3AED"},
    {"key": "financial", "label": "Financial Freedom", "icon": "cash", "color": "#059669"},
    {"key": "time", "label": "Time Freedom", "icon": "time", "color": "#0EA5E9"},
    {"key": "health", "label": "Health Freedom", "icon": "heart", "color": "#DC2626"},
    {"key": "emotional", "label": "Emotional Freedom", "icon": "sparkles", "color": "#F59E0B"},
    {"key": "social", "label": "Social Freedom", "icon": "people", "color": "#8B5CF6"},
    {"key": "mission", "label": "Mission Freedom", "icon": "flag", "color": "#EC4899"},
]

# 3 reserved suggestions (NOT seeded by default; surfaced in onboarding hint)
RESERVED_SUGGESTIONS = [
    {"key": "sexual", "label": "Sexual Freedom", "icon": "flame", "color": "#F43F5E"},
    {"key": "spiritual", "label": "Spiritual Freedom", "icon": "moon", "color": "#6366F1"},
    {"key": "eternal", "label": "Eternal Freedom", "icon": "infinite", "color": "#0F766E"},
]


class FreedomItem(BaseModel):
    key: str                                 # 'business', 'financial', custom slug, etc.
    label: str
    rank: int                                # 1-based; lower = higher priority
    icon: Optional[str] = None
    color: Optional[str] = None
    custom: bool = False                     # true if user-added (not a default/reserved)
    pinned_this_week: bool = False           # at most one across the list
    pinned_until: Optional[datetime] = None  # auto-clears on Sunday 23:59


class LDCDoc(BaseModel):
    user_id: str
    freedoms: List[FreedomItem]
    influence_pct: int = 30                  # 0-100 — Time Dezider's LDC factor weight
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LDCSetBody(BaseModel):
    freedoms: List[Dict[str, Any]]           # raw list of {key, label, icon?, color?, custom?}
    influence_pct: Optional[int] = None


class PinThisWeekBody(BaseModel):
    key: Optional[str] = None                # if None → unpin all


def weight_from_rank(rank: int) -> float:
    """Linear weight: rank 1 -> 10.0, rank 10+ -> 1.0."""
    return max(1.0, 11.0 - max(1, rank))


def seed_default_freedoms() -> List[Dict[str, Any]]:
    """Return a fresh copy of the default 7 freedoms with rank assigned."""
    return [
        {**f, "rank": i + 1, "custom": False, "pinned_this_week": False, "pinned_until": None}
        for i, f in enumerate(DEFAULT_FREEDOMS)
    ]
