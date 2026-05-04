"""
Daily Time Log (DTL) data models.

Each user keeps ONE DTL record per calendar date. A record is a list of
`TimeBlock` entries plus derived adherence metrics. Blocks can be
hand-entered or auto-rolled-up from other modules (CTT day status,
Lifestyle Eval logs, Meditation sessions, Journal entries).

Every block has:
  - start/end in HH:MM (local to the user's timezone)
  - category: lifestyle | ctt | meditation | journal | sleep | break | other
  - ref_type + ref_id (optional): links back to the source record
  - mood / energy (optional 1-5)
  - auto_sourced: True when the engine inferred it, False when user entered

A DTL record also carries the user's four situational timings for the day
(wake / bed / business-hours start/end) so the Raja Guru engine can read
them without hitting user preferences.
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


BLOCK_CATEGORIES = [
    "lifestyle", "ctt", "meditation", "journal",
    "sleep", "break", "learning", "other",
]


class TimeBlock(BaseModel):
    block_id: str = ""
    start: str = "00:00"       # "HH:MM"
    end: str = "00:00"         # "HH:MM"
    category: str = "other"    # one of BLOCK_CATEGORIES
    ref_type: Optional[str] = None   # "lifestyle_area" | "ctt_task" | "meditation_session" | "journal_entry"
    ref_id: Optional[str] = None
    label: str = ""
    note: str = ""
    mood: Optional[int] = None      # 1-5
    energy: Optional[int] = None    # 1-5
    auto_sourced: bool = False
    minutes: int = 0


class DailyKeyTimings(BaseModel):
    """User-specific HH:MM anchors for the day (inherited from user prefs
    but may be overridden per-day)."""
    wake_up: str = "06:30"
    bed_time: str = "22:30"
    business_start: str = "09:30"
    business_end: str = "18:30"


class DailyTimeLog(BaseModel):
    user_id: str
    log_date: str       # "YYYY-MM-DD"
    timezone: str = "Asia/Kolkata"
    key_timings: DailyKeyTimings = Field(default_factory=DailyKeyTimings)
    blocks: List[TimeBlock] = Field(default_factory=list)
    overall_mood: Optional[int] = None
    overall_energy: Optional[int] = None
    reflection: str = ""
    total_logged_minutes: int = 0
    planned_vs_actual: dict = Field(default_factory=dict)   # populated by engine
    auto_rollup_run_at: Optional[str] = None
    updated_at: Optional[str] = None


def minutes_between(start: str, end: str) -> int:
    """HH:MM to HH:MM minutes, wrap-around-safe (bed 23:00 → wake 06:00)."""
    try:
        h1, m1 = map(int, start.split(":"))
        h2, m2 = map(int, end.split(":"))
        a = h1 * 60 + m1
        b = h2 * 60 + m2
        if b < a:
            b += 24 * 60
        return max(0, b - a)
    except Exception:
        return 0
