"""
Daily Tracker routes — multi-modal log entries that update Time logs AND AALA cells.

This is the unified entry-point for: text input, voice transcript, AI-classified
free-form sentence, hybrid (voice + AI classification).

Each entry can attach 0+ AALA deltas, 0+ LDC freedom tags, and an optional
time-block (start/end + activity description).

  POST /api/daily-tracker/entries        — create a new entry (text or pre-classified)
  GET  /api/daily-tracker/entries        — list my recent entries (paginated)
  GET  /api/daily-tracker/today          — today's entries + roll-up
  POST /api/daily-tracker/classify       — AI-classify a free-form sentence (LLM-backed; degrades to keyword)

The AI classify endpoint uses the Emergent LLM key. If the budget is exhausted
(503), the route falls back to a deterministic keyword classifier so the UX
stays alive.
"""
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from core.database import db
from core.auth import get_current_user
from models.aala_models import TEPFI, LEVELS

router = APIRouter(prefix="/daily-tracker", tags=["Daily Tracker"])


class AALADeltaIn(BaseModel):
    factor: str
    level: str
    kind: str = "balance_set"
    delta_value: float = 0.0
    description: Optional[str] = None


class DailyEntryCreate(BaseModel):
    text: str                                 # raw input
    source: str = "text"                      # 'text' | 'voice' | 'ai_hybrid'
    activity: Optional[str] = None            # short label for the time block
    minutes: Optional[int] = None             # time spent (if any)
    started_at: Optional[datetime] = None
    aala_deltas: List[AALADeltaIn] = Field(default_factory=list)
    linked_freedoms: List[str] = Field(default_factory=list)
    mood: Optional[int] = None                # 1..5


class ClassifyBody(BaseModel):
    text: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ----------------------------------------------------------------------
# Keyword fallback classifier (used when LLM is unavailable / budget out)
# ----------------------------------------------------------------------
KEYWORD_HINTS = {
    "time": ["time", "hour", "minute", "day", "week", "deadline", "slot", "schedule"],
    "energy": ["energy", "tired", "exhausted", "fresh", "sleep", "workout", "rest", "focus"],
    "people": ["team", "client", "family", "friend", "network", "meeting", "call", "colleague", "customer"],
    "finance": ["money", "income", "revenue", "expense", "cost", "invoice", "loan", "emi", "investment", "₹", "$"],
    "infrastructure": ["learn", "book", "course", "study", "skill", "knowledge", "system", "process", "tool", "platform", "office", "equipment", "infra"],
}
FREEDOM_HINTS = {
    "business": ["business", "client", "product", "sales", "company", "deal"],
    "financial": ["money", "income", "revenue", "expense", "loan", "investment"],
    "time": ["time", "hours", "schedule", "deadline", "slot"],
    "health": ["health", "exercise", "workout", "sleep", "food", "diet", "doctor"],
    "emotional": ["emotion", "stress", "anxious", "happy", "sad", "angry", "meditation", "calm"],
    "social": ["family", "friend", "event", "party", "hangout", "community"],
    "mission": ["purpose", "vision", "mission", "impact", "legacy", "contribution"],
    "sexual": ["intimacy", "sex", "partner", "relationship"],
    "spiritual": ["prayer", "meditation", "god", "spiritual", "soul", "yoga"],
    "eternal": ["eternal", "afterlife", "karma", "dharma"],
}


def _keyword_classify(text: str) -> Dict[str, Any]:
    low = (text or "").lower()
    factor_hits = []
    for factor, kws in KEYWORD_HINTS.items():
        if any(kw in low for kw in kws):
            factor_hits.append(factor)
    freedom_hits = []
    for fk, kws in FREEDOM_HINTS.items():
        if any(kw in low for kw in kws):
            freedom_hits.append(fk)
    sign = +1.0 if any(w in low for w in ["gain", "earn", "add", "finished", "completed", "won", "saved", "good", "happy"]) else (
           -1.0 if any(w in low for w in ["lose", "loss", "spent", "missed", "failed", "sick", "tired", "stress"]) else 0.0)
    minutes_match = re.search(r"(\d{1,3})\s?(?:min|mins|minute|hour|hr)", low)
    minutes = None
    if minutes_match:
        n = int(minutes_match.group(1))
        unit = minutes_match.group(0).split()[-1] if " " in minutes_match.group(0) else minutes_match.group(0)
        minutes = n * 60 if ("hour" in unit or "hr" in unit) else n
    return {
        "factors": factor_hits or ["time"],
        "freedoms": freedom_hits,
        "sign": sign,
        "minutes": minutes,
        "confidence": 0.6 if (factor_hits or freedom_hits) else 0.3,
        "engine": "keyword",
    }


async def _llm_classify(text: str) -> Dict[str, Any]:
    """Try the LLM; fall back to keywords on any failure (budget cap, network, etc.)."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
        api_key = os.getenv("EMERGENT_LLM_KEY")
        if not api_key:
            return _keyword_classify(text)
        prompt = f"""Classify this daily-tracker entry into TEPFI factors and LDC freedoms.
TEPFI factors (pick 1-2 most relevant): time, energy, people, finance, infrastructure
LDC freedoms (pick 1-2 most relevant): business, financial, time, health, emotional, social, mission, sexual, spiritual, eternal
Sign: +1 if positive event, -1 if negative, 0 if neutral.
Minutes: extract any duration in minutes (or null).

Entry: "{text[:300]}"

Reply ONLY with valid JSON: {{"factors": [...], "freedoms": [...], "sign": -1|0|1, "minutes": null|int}}"""
        chat = LlmChat(api_key=api_key, session_id=f"dt_{uuid.uuid4().hex[:8]}", system_message="You are a strict JSON-only classifier.").with_model("openai", "gpt-4o-mini")
        resp = await chat.send_message(UserMessage(text=prompt))
        import json
        m = re.search(r"\{.*\}", resp, re.DOTALL)
        parsed = json.loads(m.group(0)) if m else {}
        return {
            "factors": parsed.get("factors", [])[:3],
            "freedoms": parsed.get("freedoms", [])[:3],
            "sign": float(parsed.get("sign", 0)),
            "minutes": parsed.get("minutes"),
            "confidence": 0.85,
            "engine": "llm",
        }
    except Exception:
        return _keyword_classify(text)


@router.post("/classify")
async def classify_text(body: ClassifyBody, user: dict = Depends(get_current_user)):
    if not body.text.strip():
        raise HTTPException(400, "text is required")
    result = await _llm_classify(body.text)
    return {"ok": True, "classification": result}


@router.post("/entries")
async def create_entry(body: DailyEntryCreate, user: dict = Depends(get_current_user)):
    if not body.text.strip():
        raise HTTPException(400, "text is required")
    entry_id = f"de_{uuid.uuid4().hex[:12]}"
    doc = {
        "entry_id": entry_id,
        "user_id": user["user_id"],
        "text": body.text.strip()[:2000],
        "source": body.source,
        "activity": body.activity,
        "minutes": int(body.minutes) if body.minutes is not None else None,
        "started_at": body.started_at or _now(),
        "linked_freedoms": list(set(body.linked_freedoms))[:8],
        "mood": int(body.mood) if body.mood else None,
        "created_at": _now(),
    }
    await db.daily_entries.insert_one(doc.copy())

    # Apply each AALA delta as a balance change to the relevant cell
    aala_doc = await db.aala.find_one({"user_id": user["user_id"]})
    if aala_doc:
        cells = aala_doc["cells"]
        for d in body.aala_deltas:
            if d.factor not in TEPFI or d.level not in LEVELS:
                continue
            for i, c in enumerate(cells):
                if c["factor"] == d.factor and c["level"] == d.level:
                    new_score = max(-10.0, min(10.0, float(c.get("balance_score", 0.0)) + float(d.delta_value)))
                    cells[i]["balance_score"] = new_score
                    cells[i]["last_updated"] = _now()
                    await db.aala_deltas.insert_one({
                        "delta_id": f"d_{uuid.uuid4().hex[:12]}",
                        "user_id": user["user_id"], "factor": d.factor, "level": d.level,
                        "kind": "balance_set", "delta_value": float(d.delta_value),
                        "description": (d.description or body.text)[:200],
                        "source": f"daily_tracker:{body.source}",
                        "occurred_at": _now(),
                        "linked_entry_id": entry_id,
                    })
                    break
        await db.aala.update_one({"user_id": user["user_id"]}, {"$set": {"cells": cells, "updated_at": _now()}})

    doc.pop("_id", None)
    return {"ok": True, "entry": doc}


@router.get("/entries")
async def list_entries(user: dict = Depends(get_current_user), limit: int = 50, days: int = 30):
    since = _now() - timedelta(days=max(1, min(days, 365)))
    items = []
    async for d in db.daily_entries.find(
        {"user_id": user["user_id"], "created_at": {"$gte": since}}, {"_id": 0}
    ).sort("started_at", -1).limit(min(max(limit, 1), 200)):
        items.append(d)
    return {"items": items, "count": len(items)}


@router.get("/today")
async def todays_summary(user: dict = Depends(get_current_user)):
    n = _now()
    start = n.replace(hour=0, minute=0, second=0, microsecond=0)
    items = []
    minutes = 0
    by_freedom: Dict[str, int] = {}
    async for d in db.daily_entries.find(
        {"user_id": user["user_id"], "started_at": {"$gte": start}}, {"_id": 0}
    ).sort("started_at", 1):
        items.append(d)
        m = int(d.get("minutes") or 0)
        minutes += m
        for fr in d.get("linked_freedoms", []):
            by_freedom[fr] = by_freedom.get(fr, 0) + m
    return {
        "date": start.date().isoformat(),
        "entries": items,
        "total_minutes": minutes,
        "by_freedom_minutes": by_freedom,
    }
