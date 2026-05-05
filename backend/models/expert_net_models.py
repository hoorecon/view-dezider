"""
ExpertNet — domain models.

Covers Phase A (profiles + discovery), Phase B (availability + bookings +
intake forms — built-in or embedded), Phase C (consultation sessions +
recommendations + delivery tracking), Phase D (1:many webinars + tickets).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, conint


# --- Phase A ---------------------------------------------------------------
class ExpertProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    headline: Optional[str] = Field(None, max_length=200)
    bio: Optional[str] = Field(None, max_length=4000)
    specializations: List[str] = Field(default_factory=list)
    catalog_node_ids: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=lambda: ["en"])
    hourly_rate_inr: Optional[int] = Field(None, ge=0)
    intro_video_url: Optional[str] = None
    photo_url: Optional[str] = None
    time_zone: str = "Asia/Kolkata"
    country: str = "IN"
    city: Optional[str] = None
    accepts_instant_calls: bool = False           # if True + currently online → "Connect now"
    is_active: bool = True
    org_id: Optional[str] = None


class ExpertProfileUpdate(BaseModel):
    headline: Optional[str] = None
    bio: Optional[str] = None
    specializations: Optional[List[str]] = None
    catalog_node_ids: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    hourly_rate_inr: Optional[int] = None
    intro_video_url: Optional[str] = None
    photo_url: Optional[str] = None
    time_zone: Optional[str] = None
    accepts_instant_calls: Optional[bool] = None
    is_active: Optional[bool] = None


# --- Phase B: Availability + Booking + Intake forms ------------------------
class AvailabilityWindow(BaseModel):
    """Recurring weekly window: 0=Mon..6=Sun"""
    weekday: conint(ge=0, le=6)
    start_minutes: conint(ge=0, le=24 * 60 - 1)   # minutes from midnight
    end_minutes: conint(ge=0, le=24 * 60)
    slot_minutes: conint(ge=10, le=240) = 30


class AvailabilityUpdate(BaseModel):
    windows: List[AvailabilityWindow]
    blackout_dates: List[str] = Field(default_factory=list)   # ISO yyyy-mm-dd


class IntakeField(BaseModel):
    field_id: str = Field(..., max_length=40)
    label: str = Field(..., max_length=120)
    field_type: Literal["short_text", "long_text", "single_select", "multi_select", "number", "file", "consent"]
    required: bool = False
    options: Optional[List[str]] = None       # for single/multi select
    helper: Optional[str] = None
    placeholder: Optional[str] = None


class IntakeFormUpsert(BaseModel):
    """Hybrid: either an `external_url` (Google Form / Typeform) OR `fields` (built-in)."""
    title: str = Field(..., max_length=120)
    description: Optional[str] = Field(None, max_length=400)
    mode: Literal["builtin", "external"] = "builtin"
    external_url: Optional[str] = None
    fields: List[IntakeField] = Field(default_factory=list)
    is_required_before_booking: bool = True


class BookingCreate(BaseModel):
    expert_id: str
    slot_start_iso: str               # ISO 8601 with offset
    duration_minutes: conint(ge=10, le=240) = 30
    intake_response: Optional[Dict[str, Any]] = None   # answers when builtin form
    note: Optional[str] = Field(None, max_length=1000)
    decision_id: Optional[str] = None    # link to MyDezider decision (multi-user)
    solution_id: Optional[str] = None    # context: consulting on this solution


# --- Phase C: Consultation sessions + recommendations + delivery -----------
class ExpertRecommendation(BaseModel):
    booking_id: str
    solution_id: str
    note: Optional[str] = Field(None, max_length=600)
    create_ctt_task: bool = True
    create_lifestyle_routine: bool = False
    routine_frequency: Literal["daily", "weekdays", "weekly", "custom"] = "weekly"


class DeliveryStatusUpdate(BaseModel):
    status: Literal[
        "ordered", "confirmed", "shipped", "in_transit",
        "out_for_delivery", "delivered", "delayed", "cancelled",
    ]
    note: Optional[str] = Field(None, max_length=300)
    tracking_number: Optional[str] = None
    tracking_url: Optional[str] = None


# --- Phase D: 1:many webinars ---------------------------------------------
class WebinarCreate(BaseModel):
    title: str = Field(..., max_length=200)
    description: Optional[str] = Field(None, max_length=4000)
    starts_at_iso: str
    duration_minutes: conint(ge=15, le=480) = 60
    capacity: Optional[conint(ge=1, le=10000)] = None
    price_inr: int = 0                              # 0 = free
    is_free: bool = True
    catalog_node_ids: List[str] = Field(default_factory=list)
    language: str = "en"


class WebinarRegister(BaseModel):
    webinar_id: str
