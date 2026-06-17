"""ATEX — Accurate Task Estimation for eXcellence.

Follows the methodology from 'Accurate Task Estimation for eXcellence (ATEX) v2'.
Inputs: Task + Sub-Tasks (ST), Quality Conditions (QC/SCC), Internal Preparedness (IP),
Required Support (RS), Practical Breaks (PB), Risk Categories (RC).

Outputs:
  EE = sum(sub_task.effort_minutes)
  MB = 5–10% of EE (default 7.5%)
  RM = sum(risk_mitigation_minutes for applicable RC by priority)
  TT = EE + MB + PB + RM (in minutes)
  + Auto end_date calculation given start_date + holidays_per_week.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from core.database import db
from core.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/atex", tags=["ATEX Estimation"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Models ─────────────────────────────────────────────────────────
class SubTask(BaseModel):
    title: str
    effort_minutes: int = 0
    ip_level: str = "high"  # high|medium|low (Internal Preparedness)
    support_needs: List[str] = Field(default_factory=list)  # IH|ID|EH|ED
    notes: Optional[str] = ""


class RiskItem(BaseModel):
    category: str  # RC1|RC2|RC3
    description: str
    mitigation_minutes: int = 0
    contingency_minutes: int = 0


class ATEXIn(BaseModel):
    task_title: str
    task_priority: str = "P2"  # P0|P1|P2|P3 — which RCs apply
    sub_tasks: List[SubTask] = Field(default_factory=list)
    # QC / SCC — MANDATORY per user spec
    self_satisfaction: str = ""
    synchronized_completion_criteria: str  # required
    # Internal Preparedness (overall)
    ip_summary: Optional[str] = ""
    # Required Support
    support_summary: Optional[str] = ""
    # Practical Breaks (total minutes within the task window)
    practical_break_minutes: int = 0
    # Risk Items
    risks: List[RiskItem] = Field(default_factory=list)
    # Buffer pct (5–10)
    minimal_buffer_pct: float = 7.5
    # Scheduling
    start_date: Optional[str] = None  # YYYY-MM-DD
    work_hours_per_day: float = 8.0
    holidays_per_week: int = 1  # default 1 weekly holiday
    # Origin
    source_module: Optional[str] = "manual"  # ctt | lifestyle_dezider | lifestyle_designer | manual
    source_ref_id: Optional[str] = None
    # Templating
    save_as_template: bool = False
    template_name: Optional[str] = ""


def _allowed_rcs_for_priority(priority: str) -> set:
    p = (priority or "P2").upper()
    return {
        "P0": {"RC1", "RC2", "RC3"},
        "P1": {"RC1", "RC2"},
        "P2": {"RC1"},
        "P3": set(),
    }.get(p, {"RC1"})


def _calc(payload: ATEXIn) -> Dict[str, Any]:
    ee_min = sum(max(0, int(st.effort_minutes or 0)) for st in payload.sub_tasks)
    mb_pct = max(5.0, min(10.0, float(payload.minimal_buffer_pct or 7.5)))
    mb_min = round(ee_min * mb_pct / 100.0)

    allowed = _allowed_rcs_for_priority(payload.task_priority)
    rm_min = 0
    risk_breakdown = []
    for r in payload.risks:
        if r.category not in allowed:
            continue
        m = int(r.mitigation_minutes or 0) + int(r.contingency_minutes or 0)
        rm_min += m
        risk_breakdown.append({
            "category": r.category, "description": r.description,
            "mitigation_minutes": r.mitigation_minutes,
            "contingency_minutes": r.contingency_minutes,
            "applied": True,
        })
    # Add skipped risks for transparency
    for r in payload.risks:
        if r.category not in allowed:
            risk_breakdown.append({
                "category": r.category, "description": r.description,
                "mitigation_minutes": 0, "contingency_minutes": 0,
                "applied": False, "reason": f"Priority {payload.task_priority} does not include {r.category}",
            })

    pb_min = max(0, int(payload.practical_break_minutes or 0))
    tt_min = ee_min + mb_min + pb_min + rm_min

    # End-date calc
    end_date_iso = None
    working_days_needed = None
    if payload.start_date:
        try:
            sd = date.fromisoformat(payload.start_date)
            hrs_needed = tt_min / 60.0
            wpd = max(0.5, float(payload.work_hours_per_day or 8.0))
            working_days_needed = max(1, int((hrs_needed + wpd - 0.0001) // wpd) + (0 if hrs_needed % wpd == 0 else 0))
            # Tally calendar days accounting for holidays_per_week
            hpw = max(0, min(6, int(payload.holidays_per_week or 1)))
            working_days_per_calendar_week = 7 - hpw
            full_weeks = working_days_needed // working_days_per_calendar_week if working_days_per_calendar_week > 0 else 0
            remainder_days = working_days_needed % working_days_per_calendar_week if working_days_per_calendar_week > 0 else working_days_needed
            cal_days = full_weeks * 7 + remainder_days
            end_date_iso = (sd + timedelta(days=max(0, cal_days - 1))).isoformat()
        except Exception as e:
            logger.warning("end-date calc failed: %s", e)

    return {
        "effort_minutes": ee_min,
        "effort_hours": round(ee_min / 60.0, 2),
        "minimal_buffer_minutes": mb_min,
        "minimal_buffer_pct": mb_pct,
        "practical_break_minutes": pb_min,
        "risk_buffer_minutes": rm_min,
        "total_timeline_minutes": tt_min,
        "total_timeline_hours": round(tt_min / 60.0, 2),
        "working_days_needed": working_days_needed,
        "end_date": end_date_iso,
        "risks_breakdown": risk_breakdown,
        "allowed_risk_categories": sorted(list(allowed)),
    }


@router.post("/estimate")
async def estimate(payload: ATEXIn, user: dict = Depends(get_current_user)):
    if not payload.synchronized_completion_criteria or not payload.synchronized_completion_criteria.strip():
        raise HTTPException(400, "Synchronized Completion Criteria (SCC) is required for ATEX")
    if not payload.sub_tasks:
        raise HTTPException(400, "At least one sub-task is required")

    result = _calc(payload)
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "task_title": payload.task_title,
        "task_priority": payload.task_priority,
        "input": payload.model_dump(),
        "output": result,
        "source_module": payload.source_module,
        "source_ref_id": payload.source_ref_id,
        "created_at": _now(),
    }
    await db.atex_estimations.insert_one(doc)

    if payload.save_as_template and (payload.template_name or "").strip():
        await db.atex_templates.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user["user_id"],
            "org_id": user.get("org_id"),
            "name": payload.template_name.strip(),
            "template": payload.model_dump(),
            "created_at": _now(),
        })
    doc.pop("_id", None)
    return {"estimation": doc, "calc": result}


@router.get("/estimations")
async def list_estimations(limit: int = 50, user: dict = Depends(get_current_user)):
    rows = await db.atex_estimations.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return {"estimations": rows}


@router.get("/estimations/{est_id}")
async def get_estimation(est_id: str, user: dict = Depends(get_current_user)):
    row = await db.atex_estimations.find_one({"id": est_id, "user_id": user["user_id"]}, {"_id": 0})
    if not row:
        raise HTTPException(404, "Not found")
    return row


@router.get("/templates")
async def list_templates(user: dict = Depends(get_current_user)):
    rows = await db.atex_templates.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"templates": rows}


@router.delete("/templates/{tpl_id}")
async def delete_template(tpl_id: str, user: dict = Depends(get_current_user)):
    res = await db.atex_templates.delete_one({"id": tpl_id, "user_id": user["user_id"]})
    if res.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"ok": True}


# AI-assisted: suggest sub-tasks given a task title
@router.post("/ai-suggest")
async def ai_suggest(body: Dict[str, Any], user: dict = Depends(get_current_user)):
    task_title = (body.get("task_title") or "").strip()
    if not task_title:
        raise HTTPException(400, "task_title required")
    import os
    prompt = (
        "You are the ATEX (Accurate Task Estimation for eXcellence) AI helper. Given the user's task, propose:\n"
        "1. 4-8 atomic sub-tasks with effort_minutes (integer) and ip_level (high/medium/low).\n"
        "2. A concise Synchronized Completion Criteria (SCC).\n"
        "3. Up to 3 risks with category (RC1=expected may not happen, RC2=unexpected may happen, RC3=unimaginable), "
        "description, mitigation_minutes, contingency_minutes.\n"
        "Respond ONLY as strict JSON: {sub_tasks: [...], scc: str, risks: [...]}.\n\n"
        f"TASK: {task_title}"
    )
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=os.getenv("EMERGENT_LLM_KEY") or "",
            session_id=f"atex-ai-{user['user_id']}",
            system_message="Return ONLY strict JSON as instructed. No commentary.",
        ).with_model("anthropic", "claude-haiku-4-5")
        reply = await chat.send_message(UserMessage(text=prompt))
        import json, re
        m = re.search(r"\{.*\}", (reply or "").strip(), re.DOTALL)
        return json.loads(m.group(0) if m else (reply or "{}"))
    except Exception as e:
        logger.warning("atex ai suggest fallback: %s", e)
        return {
            "sub_tasks": [
                {"title": "Plan and break down the task", "effort_minutes": 30, "ip_level": "high", "support_needs": []},
                {"title": "Execute main steps", "effort_minutes": 120, "ip_level": "medium", "support_needs": []},
                {"title": "Review and quality-check", "effort_minutes": 30, "ip_level": "high", "support_needs": []},
            ],
            "scc": "Deliverable signed-off by stakeholder with all acceptance tests passing.",
            "risks": [
                {"category": "RC1", "description": "Hidden complexity in sub-step", "mitigation_minutes": 15, "contingency_minutes": 0},
            ],
        }
