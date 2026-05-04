"""
Solution Matrix data models (nested OrgType layout).

Structure (per user-facing spec — "3 Solution Layers × 4 OrgTypes × 7 Resource
dimensions"):

    matrix_self / matrix_micro / matrix_macro  (3 parent layers)
       └── individual / org / govt / nature    (4 OrgType sub-levels)
             └── summary / knowledge_skills / capacity / time /
                 people / finance / infrastructure               (7 fields)

Legacy payloads (flat `{summary, knowledge_skills, ...}` without OrgType
sub-level) are normalised to the `individual` slot with the other three
OrgTypes left empty.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Primitive layer: the 7 resource dimensions
# ---------------------------------------------------------------------------
class MatrixResourceCell(BaseModel):
    summary: str = ""
    knowledge_skills: str = ""
    capacity: str = ""
    time: str = ""
    people: str = ""
    finance: str = ""
    infrastructure: str = ""


# ---------------------------------------------------------------------------
# Per-parent-layer set: 4 OrgType sub-levels
# ---------------------------------------------------------------------------
class MatrixLayerSet(BaseModel):
    individual: MatrixResourceCell = Field(default_factory=MatrixResourceCell)
    org: MatrixResourceCell = Field(default_factory=MatrixResourceCell)
    govt: MatrixResourceCell = Field(default_factory=MatrixResourceCell)
    nature: MatrixResourceCell = Field(default_factory=MatrixResourceCell)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
ORG_TYPES: List[str] = ["individual", "org", "govt", "nature"]
MATRIX_PARENT_LAYERS: List[str] = ["matrix_self", "matrix_micro", "matrix_macro"]
RESOURCE_DIMENSIONS: List[str] = [
    "summary", "knowledge_skills", "capacity",
    "time", "people", "finance", "infrastructure",
]


def empty_resource_cell() -> Dict[str, str]:
    """Return a fresh flat resource dict (7 empty strings)."""
    return {k: "" for k in RESOURCE_DIMENSIONS}


def empty_layer_set() -> Dict[str, Dict[str, str]]:
    """Return a fresh nested layer set with 4 OrgTypes × 7 empty resource cells."""
    return {ot: empty_resource_cell() for ot in ORG_TYPES}


def normalise_layer_set(raw: Optional[Dict]) -> Dict[str, Dict[str, str]]:
    """
    Convert either:
      • a legacy flat dict `{summary, knowledge_skills, ...}` (no OrgType keys)
      • a partial nested dict `{individual: {...}, org: {...}}`
      • None / missing
      • a fully-populated nested dict
    …into the canonical nested shape with all 4 OrgTypes × 7 fields present.

    Unknown/extra keys are silently dropped. Missing keys default to "".
    """
    if not isinstance(raw, dict):
        return empty_layer_set()

    has_legacy_keys = any(k in raw for k in RESOURCE_DIMENSIONS)
    has_orgtype_keys = any(k in raw for k in ORG_TYPES)

    if has_legacy_keys and not has_orgtype_keys:
        # Legacy flat payload — map to `individual`, zero the others.
        individual_cell = {k: str(raw.get(k, "") or "") for k in RESOURCE_DIMENSIONS}
        return {
            "individual": individual_cell,
            "org": empty_resource_cell(),
            "govt": empty_resource_cell(),
            "nature": empty_resource_cell(),
        }

    # Nested shape — merge each OrgType, coercing values to strings.
    result: Dict[str, Dict[str, str]] = {}
    for ot in ORG_TYPES:
        source = raw.get(ot) if isinstance(raw.get(ot), dict) else {}
        result[ot] = {k: str(source.get(k, "") or "") for k in RESOURCE_DIMENSIONS}
    return result
