"""
Solution Matrix data models.

Two supported modes (user-selectable on a per-record basis):

  1. STANDARD  — 5 TEPFI × 3 layers (Self/Micro/Macro) = 15 cells
                 Uses the `aggregate` slot inside every layer set. Ignores
                 the four OrgType sub-levels. Quick entry.

  2. ACCURATE  — 5 TEPFI × (3 layers × 4 OrgTypes) = 60 cells
                 Uses the `individual`, `org`, `govt`, `nature` sub-levels.
                 Ideal for cross-stakeholder analysis.

Every cell carries:
  - The 5 canonical TEPFI string fields.
  - Two extended text fields (summary + knowledge_skills) kept for
    backward-compat with the earlier 7-field UI.
  - A per-field `influences` map holding {positive, negative} annotations
    so users can record whether each TEPFI element helps or hurts.

Legacy payloads (flat `{summary, knowledge_skills, ...}` without OrgType
sub-level) are normalised to the `individual` slot with the other three
OrgTypes left empty; the aggregate slot mirrors that payload so a legacy
entry still reads cleanly in Standard mode.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Supported modes + canonical dimension order
# ---------------------------------------------------------------------------
MATRIX_MODES: List[str] = ["standard", "accurate"]

# The 5 canonical TEPFI elements
TEPFI_DIMENSIONS: List[str] = ["time", "energy", "people", "finance", "infrastructure"]

# Legacy 7-field set (kept so older rows + current UI continue to work).
# Note: `capacity` (legacy) ≈ `energy` (TEPFI); both are persisted for
# round-trip safety.
RESOURCE_DIMENSIONS: List[str] = [
    "summary", "knowledge_skills", "capacity",
    "time", "people", "finance", "infrastructure",
]

# OrgTypes for Accurate mode and parent layers
ORG_TYPES: List[str] = ["individual", "org", "govt", "nature"]
MATRIX_PARENT_LAYERS: List[str] = ["matrix_self", "matrix_micro", "matrix_macro"]

# Aggregate slot name used by Standard mode
AGGREGATE_SLOT: str = "aggregate"
ALL_SLOTS: List[str] = [AGGREGATE_SLOT, *ORG_TYPES]


# ---------------------------------------------------------------------------
# Per-field influence annotation
# ---------------------------------------------------------------------------
class MatrixInfluence(BaseModel):
    """Positive and negative influence attributes for a single TEPFI field."""
    positive: str = ""
    negative: str = ""


# ---------------------------------------------------------------------------
# Primitive: a single resource cell (holds the 7 text fields + per-field influence)
# ---------------------------------------------------------------------------
class MatrixResourceCell(BaseModel):
    summary: str = ""
    knowledge_skills: str = ""
    capacity: str = ""            # Legacy label for Energy
    time: str = ""
    energy: str = ""              # Canonical TEPFI-E (mirrors/supersedes `capacity`)
    people: str = ""
    finance: str = ""
    infrastructure: str = ""
    # Optional per-field influence map keyed by field-name -> {positive, negative}
    influences: Dict[str, MatrixInfluence] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Per-layer set — holds the aggregate (Standard mode) + 4 OrgTypes (Accurate mode)
# ---------------------------------------------------------------------------
class MatrixLayerSet(BaseModel):
    aggregate: MatrixResourceCell = Field(default_factory=MatrixResourceCell)  # Standard mode
    individual: MatrixResourceCell = Field(default_factory=MatrixResourceCell)
    org: MatrixResourceCell = Field(default_factory=MatrixResourceCell)
    govt: MatrixResourceCell = Field(default_factory=MatrixResourceCell)
    nature: MatrixResourceCell = Field(default_factory=MatrixResourceCell)


# ---------------------------------------------------------------------------
# Helper primitives
# ---------------------------------------------------------------------------
def empty_resource_cell() -> Dict:
    """Return a fresh resource cell dict (all text = "", no influences)."""
    cell: Dict = {k: "" for k in RESOURCE_DIMENSIONS}
    cell["energy"] = ""       # canonical TEPFI-E
    cell["influences"] = {}   # per-field {positive, negative}
    return cell


def empty_layer_set() -> Dict[str, Dict]:
    """Return a fresh layer set: aggregate + 4 OrgType empty cells."""
    return {slot: empty_resource_cell() for slot in ALL_SLOTS}


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------
def _coerce_influence(raw) -> Dict[str, Dict[str, str]]:
    """Coerce the influences field into {field_name: {positive, negative}}."""
    if not isinstance(raw, dict):
        return {}
    cleaned: Dict[str, Dict[str, str]] = {}
    for key, val in raw.items():
        if not isinstance(val, dict):
            continue
        cleaned[str(key)] = {
            "positive": str(val.get("positive", "") or ""),
            "negative": str(val.get("negative", "") or ""),
        }
    return cleaned


def _normalise_cell(raw) -> Dict:
    """Coerce any incoming cell dict into the canonical MatrixResourceCell dict."""
    base = empty_resource_cell()
    if not isinstance(raw, dict):
        return base
    for key in RESOURCE_DIMENSIONS:
        if key in raw:
            base[key] = str(raw.get(key, "") or "")
    # energy mirrors capacity if energy missing (for TEPFI canonical)
    if "energy" in raw:
        base["energy"] = str(raw.get("energy", "") or "")
    elif "capacity" in raw and not base.get("energy"):
        base["energy"] = base["capacity"]
    # Back-fill capacity from energy if capacity missing (legacy UI)
    if not base.get("capacity") and base.get("energy"):
        base["capacity"] = base["energy"]
    base["influences"] = _coerce_influence(raw.get("influences"))
    return base


def normalise_layer_set(raw: Optional[Dict]) -> Dict[str, Dict]:
    """
    Accepts any of:
      • None / non-dict             → empty layer set.
      • legacy flat dict (no slots) → goes into both `individual` and `aggregate`.
      • partial nested dict         → merges existing slots; missing slots default.
      • fully populated dict        → pass-through with normalisation.

    Extra/unknown keys are silently dropped. Output always has all 5 slots
    (aggregate + 4 OrgTypes) with complete field-sets.
    """
    if not isinstance(raw, dict):
        return empty_layer_set()

    has_legacy_keys = any(k in raw for k in RESOURCE_DIMENSIONS) or "energy" in raw or "influences" in raw
    has_slot_keys = any(k in raw for k in ALL_SLOTS)

    if has_legacy_keys and not has_slot_keys:
        # Legacy flat payload — map to BOTH individual (for Accurate mode)
        # and aggregate (for Standard mode) so older records render in both.
        cell = _normalise_cell(raw)
        result = empty_layer_set()
        result["individual"] = cell
        # Use a copy so edits don't bleed between slots
        result["aggregate"] = _normalise_cell(raw)
        return result

    # Nested slot payload — merge each slot, fall back to empty.
    result: Dict[str, Dict] = {}
    for slot in ALL_SLOTS:
        source = raw.get(slot)
        result[slot] = _normalise_cell(source)
    return result


def normalise_matrix_mode(raw: Optional[str]) -> str:
    """Clamp incoming mode to one of MATRIX_MODES; defaults to 'accurate'."""
    if isinstance(raw, str) and raw.strip().lower() in MATRIX_MODES:
        return raw.strip().lower()
    return "accurate"
