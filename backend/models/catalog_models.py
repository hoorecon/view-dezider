"""
Central Catalog Management (CCM) — domain model.

A 4-level catalog (Level 0..3) that every Solution Store item maps into.
  Level 0: life_area  (mirrored from `data.hos_seed_data.LIFE_AREAS`)
  Level 1: sub_area   (mirrored from `data.hos_seed_data.SUB_AREAS`)
  Level 2: category   (admin-managed via /api/catalog/*)
  Level 3: subcategory(admin-managed via /api/catalog/*)

Levels 0 & 1 are seeded once and treated as immutable backbone. Levels 2 & 3
are fully editable by admins. Every node carries `life_area_id` and
`sub_area_id` denormalised for fast filtering.

Solutions store items add a `catalog_node_id` pointer that resolves to the
deepest mapped node (Level 1, 2 or 3 — Level 0-only mapping is discouraged
but allowed for legacy items).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


CATALOG_LEVELS = (0, 1, 2, 3)
CATALOG_MAX_DEPTH = 3   # node.level cannot exceed this


class CatalogNode(BaseModel):
    node_id: str                                # e.g. "cn_fin_savings_fd_senior"
    name: str
    slug: str
    level: int                                  # 0..3
    parent_id: Optional[str] = None             # None for level 0
    life_area_id: str                           # Always the level-0 root
    sub_area_id: Optional[str] = None           # The level-1 ancestor (if any)
    description: Optional[str] = None
    icon: Optional[str] = None                  # ionicons name
    color: Optional[str] = None                 # hex
    sort_order: int = 0
    is_active: bool = True
    is_immutable: bool = False                  # True for level 0 / 1 backbone
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("level")
    @classmethod
    def _level_in_range(cls, v: int) -> int:
        if v not in CATALOG_LEVELS:
            raise ValueError(f"level must be one of {CATALOG_LEVELS}")
        return v


class CatalogNodeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    slug: Optional[str] = Field(None, max_length=80)   # auto-derived from name if absent
    parent_id: str                                     # parent must be Level 1 or 2
    description: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = None
    color: Optional[str] = None
    sort_order: int = 0


class CatalogNodeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    slug: Optional[str] = Field(None, max_length=80)
    description: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class CatalogMapping(BaseModel):
    """Used to map / re-map a solution to a catalog leaf."""
    catalog_node_id: str
