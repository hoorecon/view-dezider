"""Emotional Gatekeeper — Pydantic Models"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel


# ============ SESSION ============

class CreateSessionRequest(BaseModel):
    session_type: str  # trap, loop, limitation, outlet, aim, integrated
    title: Optional[str] = None


class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    intensity_before: Optional[int] = None
    intensity_after: Optional[int] = None


# ============ TRAP ============

class TrapCaptureRequest(BaseModel):
    situation: str
    category: Optional[str] = None
    start_period: Optional[str] = None
    intensity: Optional[int] = None  # 1-10


class TrapLandscapingRequest(BaseModel):
    scanning_for: Optional[str] = None
    scanning_patterns: Optional[List[str]] = []
    scanning_without_urgency: Optional[bool] = None
    repeated_concern: Optional[str] = None


class TrapLinkingRequest(BaseModel):
    trigger_description: Optional[str] = None
    trigger_type: Optional[str] = None  # external / internal
    external_trigger: Optional[str] = None
    internal_trigger: Optional[str] = None
    linking_meaning: Optional[str] = None


class TrapLoopingRequest(BaseModel):
    repeating_thought: Optional[str] = None
    repeating_question: Optional[str] = None
    getting_new_solution: Optional[bool] = None
    emotion_increasing: Optional[str] = None
    intensity_before: Optional[int] = None  # 1-10
    intensity_after: Optional[int] = None  # 1-10


# ============ LOOP ============

class LoopCaptureRequest(BaseModel):
    repeated_thought: str
    emotion: Optional[str] = None
    repeat_count_today: Optional[int] = None
    fear: Optional[str] = None
    trying_to_solve: Optional[str] = None


class LoopMethodRequest(BaseModel):
    selected_method: str  # i_dont_know, all_is_well, both_good_bad, this_too_shall_pass
    method_answers: Optional[Dict[str, Any]] = {}


# ============ LIMITATION ============

class LimitationCaptureRequest(BaseModel):
    limitation_statement: str
    why_limited: Optional[str] = None
    origin: Optional[str] = None
    limitation_category: Optional[str] = None  # past_self, past_others, external_inputs, fear_unknown
    belief_duration: Optional[str] = None
    cost_of_limitation: Optional[str] = None


class LimitationFlowRequest(BaseModel):
    answers: Dict[str, Any] = {}


# ============ OUTLET ANALYZER ============

class OutletEntry(BaseModel):
    strategy_id: str
    custom_name: Optional[str] = None  # For "other" strategy
    frequency: str  # often, sometimes, rarely, not_at_all, prefer_not_say
    is_compulsive: Optional[bool] = False
    side_effects: Optional[str] = None
    nature_override: Optional[str] = None  # physical, mental, emotional, energy


class OutletAnalysisRequest(BaseModel):
    entries: List[OutletEntry]


# ============ AIM ============

class AddictionEntry(BaseModel):
    area_of_life: str
    occurrence: Optional[str] = None
    addiction: str
    triggering_situations: Optional[str] = None
    positive_impact: Optional[str] = None
    positive_impact_areas: Optional[List[str]] = []
    positive_impact_pct: Optional[int] = None  # 0-100
    negative_impact: Optional[str] = None
    negative_impact_areas: Optional[List[str]] = []
    negative_impact_pct: Optional[int] = None  # 0-100
    corrective_actions: Optional[str] = None
    task_owner_timeline: Optional[str] = None
    remarks: Optional[str] = None


class IrritationEntry(BaseModel):
    area_of_life: str
    occurrence: Optional[str] = None
    irritation: str
    # Irritation strength as a 0-100 percent. Frontend defaults to 50 so
    # users have a working baseline without forcing a slider drag.
    irritation_pct: Optional[int] = 50
    probable_reaction: Optional[str] = None
    positive_impact: Optional[str] = None
    negative_impact: Optional[str] = None
    # Life areas this irritation negatively affects (multi-select). Stored
    # as canonical IDs from frontend/src/constants/lifeAreas.ts.
    negative_impact_areas: Optional[List[str]] = []
    remarks: Optional[str] = None


class AIMSaveRequest(BaseModel):
    addictions: Optional[List[AddictionEntry]] = []
    irritations: Optional[List[IrritationEntry]] = []


# ============ COMMITMENT ============

class CommitmentRequest(BaseModel):
    commitment_type: str  # immediate, 7_day, 30_day
    commitment_text: str
    due_date: Optional[str] = None
    reminder_enabled: Optional[bool] = True


# ============ JOURNAL ============

class JournalRequest(BaseModel):
    journal_title: Optional[str] = None
    journal_content: Optional[str] = None
    tags: Optional[List[str]] = []
