"""
Full CLD (Causal Loop Diagram) Engine
- CRUD for CLD diagrams (per decision)
- Dynamic simulation (what-if propagation)
- Force-directed layout generation
- AI-powered causal analysis
- Module-specific CLDs (Master, PNA, Goal, etc.)
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from core.database import db
from core.auth import get_current_user
from core.rate_limiting import limiter, AI_LIMIT
import os
import uuid
import math
import json as json_module
import logging

logger = logging.getLogger(__name__)

# Credit deduction helper
async def _deduct_ai_credits(user_id: str, action: str):
    """Deduct credits for AI actions. Import from payments module."""
    try:
        from routes.payments import deduct_credits
        await deduct_credits(user_id, action)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Credit deduction skipped: {e}")

router = APIRouter(prefix="/cld", tags=["CLD Engine"])

# ========================
# MODELS
# ========================

class CLDNode(BaseModel):
    factor_id: str
    name: str
    x: float = 200.0
    y: float = 200.0
    centrality: float = 0.5
    classification: str = "secondary"  # primary / secondary
    priority_rank: int = 1
    gap_multiplier: float = 1.0
    base_value: float = 50.0  # Baseline value for simulation (0-100)
    locked: bool = False  # If locked, simulation won't change this node

class CLDLink(BaseModel):
    from_id: str
    to_id: str
    link_type: str = "reinforcing"  # reinforcing / balancing
    strength: float = 5.0  # 1-10
    delay: int = 0  # time-step delay (0 = immediate)
    description: str = ""

class CLDLoop(BaseModel):
    name: str
    loop_type: str = "reinforcing"  # reinforcing / balancing
    factor_ids: List[str] = []

class CLDDiagram(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str
    user_id: str
    nodes: List[CLDNode] = []
    links: List[CLDLink] = []
    loops: List[CLDLoop] = []
    layout_type: str = "circular"  # circular / force / manual
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SimulationRequest(BaseModel):
    shock_factor_id: str
    shock_delta: float  # e.g. +20 means increase by 20%
    time_steps: int = 5  # how many propagation steps
    dampening: float = 0.7  # dampening factor per hop (0-1)

class SimulationStep(BaseModel):
    step: int
    values: Dict[str, float]  # factor_id -> value at this step
    deltas: Dict[str, float]  # factor_id -> change from previous step

class SimulationResult(BaseModel):
    timeline: List[SimulationStep]
    final_values: Dict[str, float]
    total_impact: Dict[str, float]  # factor_id -> total change from baseline
    stability: str  # "stable", "oscillating", "diverging"
    most_affected: List[str]  # factor_ids most impacted

class CLDSaveRequest(BaseModel):
    nodes: List[Dict[str, Any]]
    links: List[Dict[str, Any]]
    loops: List[Dict[str, Any]] = []
    layout_type: str = "circular"
    notes: str = ""

class NodeUpdateRequest(BaseModel):
    x: Optional[float] = None
    y: Optional[float] = None
    centrality: Optional[float] = None
    classification: Optional[str] = None
    priority_rank: Optional[int] = None
    gap_multiplier: Optional[float] = None
    base_value: Optional[float] = None
    locked: Optional[bool] = None

class LinkUpdateRequest(BaseModel):
    link_type: Optional[str] = None
    strength: Optional[float] = None
    delay: Optional[int] = None
    description: Optional[str] = None



# ========================
# LIST USER'S CLDs (before parameterized routes)
# ========================

@router.get("/list")
async def list_clds(user: dict = Depends(get_current_user)):
    """List all CLD diagrams for the current user"""
    clds = await db.cld_diagrams.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("updated_at", -1).to_list(50)
    return {"clds": clds}


# ════════════════════════════════════════════════════════
# CLD REFINEMENTS: Module-Specific CLDs (MUST be before /{decision_id})
# ════════════════════════════════════════════════════════

MODULE_TYPES = [
    "master",          # Aggregates ALL modules
    "decision",        # PRR Decisions
    "conflict_breaker",# Crucial Conversations
    "pna",            # Problems/Needs/Aspirations
    "goal",           # GEM Goals + Goal Setter + Goal Manifestation
    "lifestyle",      # Lifestyle Designer + Lifestyle Dezider
    "emotional_gatekeeper",  # Emotional tools
    "aala",           # Assets & Liabilities
    "ctt",            # Centralized Task Tracker
    "solutions_store",# Solutions Store + DEO
    "unconditional_happiness",  # UH tracker
    "time_dezider",   # Time management
    "tepfi",          # TEPFI Resource Matrix
    "consciousness",  # Consciousness Diary
    "ai_assistant",   # AI conversations context
    "meditation",     # KalphaVriksha + Meditation Settings
]


@router.get("/list-modules")
async def list_module_clds(user: dict = Depends(get_current_user)):
    """List all module CLDs for the user."""
    full_clds = await db.cld_diagrams.find(
        {"user_id": user["user_id"], "module_type": {"$exists": True}},
        {"_id": 0}
    ).to_list(50)

    result = []
    for c in full_clds:
        result.append({
            "cld_id": c.get("cld_id"),
            "module_type": c.get("module_type"),
            "context_id": c.get("context_id"),
            "node_count": len(c.get("nodes", [])),
            "link_count": len(c.get("links", [])),
            "updated_at": str(c.get("updated_at", "")),
        })
    return result


@router.post("/module/{module_type}/generate")
@limiter.limit(AI_LIMIT)
async def generate_module_cld(module_type: str, request: Request, user: dict = Depends(get_current_user)):
    """Generate a CLD for a specific module or a master CLD aggregating all modules."""
    if module_type not in MODULE_TYPES:
        raise HTTPException(400, f"Invalid module_type. Use: {MODULE_TYPES}")

    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    context_id = body.get("context_id", "")

    uid = user["user_id"]
    context_parts = []

    if module_type in ["master", "pna"]:
        pna_items = await db.pna_items.find({"user_id": uid}, {"_id": 0}).to_list(50)
        if pna_items:
            pna_text = "\n".join([f"- [{i['category'].upper()}] {i['title']} ({i['life_area']}): {i.get('description','')}" for i in pna_items[:20]])
            context_parts.append(f"PNA Items:\n{pna_text}")

    if module_type in ["master", "goal"]:
        goals = await db.gem_goals.find({"user_id": uid}, {"_id": 0}).to_list(20)
        if goals:
            goals_text = "\n".join([f"- {g['title']} ({g.get('life_area','')}) [{g.get('status','')}]" for g in goals[:10]])
            context_parts.append(f"Goals:\n{goals_text}")

    if module_type in ["master", "conflict_breaker"]:
        cb_sessions = await db.conflict_breaker_sessions.find({"user_id": uid}, {"_id": 0}).to_list(10)
        if cb_sessions:
            cb_text = "\n".join([f"- {c.get('title','')} (stakes:{c.get('stakes_score','?')}, emotion:{c.get('emotion_score','?')})" for c in cb_sessions[:5]])
            context_parts.append(f"Conflict Breaker Sessions:\n{cb_text}")

    if module_type in ["master", "lifestyle"]:
        plan = await db.lifestyle_plans.find_one({"user_id": uid, "is_active": True}, {"_id": 0})
        if plan:
            areas = []
            for area_id, alloc in (plan.get("allocations", {}).get("weekday", {})).items():
                if isinstance(alloc, dict) and alloc.get("hours", 0) > 0:
                    areas.append(f"{area_id}: {alloc['hours']}h")
            context_parts.append(f"Lifestyle Plan ({plan['name']}): {', '.join(areas)}")

    if module_type in ["master", "aala"]:
        aala = await db.aala_records.find({"user_id": uid}, {"_id": 0}).to_list(20)
        if aala:
            aala_text = "\n".join([f"- {a.get('category','')}: {a.get('name','')} ({a.get('type','')}) = {a.get('value',0)}" for a in aala[:10]])
            context_parts.append(f"AALA Records:\n{aala_text}")

    if module_type in ["master", "decision"]:
        decisions = await db.decisions.find({"user_id": uid}, {"_id": 0}).to_list(10)
        if decisions:
            dec_text = "\n".join([f"- {d.get('title','')} [{d.get('status','')}]" for d in decisions[:5]])
            context_parts.append(f"Decisions:\n{dec_text}")

    if module_type in ["master", "ctt"]:
        tasks = await db.ctt_tasks.find({"user_id": uid}, {"_id": 0}).to_list(20)
        if tasks:
            task_text = "\n".join([f"- {t.get('title','')} [{t.get('status','')}] priority:{t.get('priority','')}" for t in tasks[:10]])
            context_parts.append(f"CTT Tasks:\n{task_text}")

    if module_type in ["master", "solutions_store"]:
        solutions = await db.solutions_store.find({"user_id": uid}, {"_id": 0}).to_list(10)
        if solutions:
            sol_text = "\n".join([f"- {s.get('name','')} ({s.get('category','')}) rating:{s.get('avg_rating','?')}" for s in solutions[:5]])
            context_parts.append(f"Solutions Store:\n{sol_text}")

    if module_type in ["master", "unconditional_happiness"]:
        uh_entries = await db.unconditional_happiness.find({"user_id": uid}, {"_id": 0}).sort("date", -1).to_list(14)
        if uh_entries:
            uh_text = "\n".join([f"- {e.get('date','')}: score={e.get('score',0)}, gratitude_count={len(e.get('gratitudes',[]))}" for e in uh_entries[:7]])
            context_parts.append(f"Unconditional Happiness (last 7 days):\n{uh_text}")

    if module_type in ["master", "time_dezider"]:
        time_entries = await db.time_dezider_entries.find({"user_id": uid}, {"_id": 0}).to_list(10)
        if time_entries:
            time_text = "\n".join([f"- {t.get('activity','')} ({t.get('life_area','')}) hours:{t.get('hours',0)}" for t in time_entries[:5]])
            context_parts.append(f"Time Dezider:\n{time_text}")

    if module_type in ["master", "tepfi"]:
        tepfi = await db.tepfi_entries.find({"user_id": uid}, {"_id": 0}).to_list(10)
        if tepfi:
            tepfi_text = "\n".join([f"- {t.get('resource_type','')}: {t.get('name','')} (score:{t.get('score',0)})" for t in tepfi[:5]])
            context_parts.append(f"TEPFI Resources:\n{tepfi_text}")

    if module_type in ["master", "consciousness"]:
        diary = await db.consciousness_diary.find({"user_id": uid}, {"_id": 0}).sort("date", -1).to_list(10)
        if diary:
            diary_text = "\n".join([f"- {d.get('date','')}: {d.get('insight','')[:60]}" for d in diary[:5]])
            context_parts.append(f"Consciousness Diary:\n{diary_text}")

    if module_type in ["master", "ai_assistant"]:
        convos = await db.ai_assistant_conversations.find({"user_id": uid}, {"_id": 0}).to_list(10)
        if convos:
            convo_text = "\n".join([f"- {c.get('title','')} ({c.get('language','en')}) msgs:{c.get('message_count',0)}" for c in convos[:5]])
            context_parts.append(f"AI Assistant Conversations:\n{convo_text}")

    if module_type in ["master", "meditation"]:
        med_sessions = await db.meditation_sessions.find({"user_id": uid}, {"_id": 0}).sort("date", -1).to_list(10)
        if med_sessions:
            med_text = "\n".join([f"- {m.get('date','')}: {m.get('type','')} duration:{m.get('duration_mins',0)}min" for m in med_sessions[:5]])
            context_parts.append(f"Meditation Sessions:\n{med_text}")

    if not context_parts:
        context_parts.append("No data available in this module yet. Generate a basic CLD showing general life area interactions.")

    full_context = "\n\n".join(context_parts)

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(500, "LLM key not configured")

    from core.llm_compat import LlmChat, UserMessage  # provider-agnostic shim (Emergent | direct via litellm)
    chat = LlmChat(
        api_key=api_key,
        session_id=f"cld_module_{uid}_{uuid.uuid4().hex[:8]}",
        system_message="You are a Systems Thinking expert. Generate Causal Loop Diagrams showing cause-effect relationships."
    ).with_model("openai", "gpt-4.1-mini")

    prompt = f"""Analyze this user's {module_type} data and generate a Causal Loop Diagram.

USER CONTEXT:
{full_context}

Generate a JSON CLD with nodes and links showing causal relationships.
Each node: {{"factor_id": "f1", "label": "Factor Name", "value": 50, "x": <random 50-550>, "y": <random 50-350>}}
Each link: {{"source": "f1", "target": "f2", "polarity": "+", "strength": 0.7, "label": "description"}}

Polarity: "+" means same direction (increase causes increase), "-" means opposite.
Generate 6-12 nodes and 8-15 links showing meaningful causal loops.

RESPOND WITH ONLY VALID JSON:
{{"nodes": [...], "links": [...]}}"""

    try:
        resp = await chat.send_message(UserMessage(text=prompt))
        text = resp.strip()
        if "```" in text:
            text = text.split("```")[1].replace("json", "").strip()
        cld_data = json_module.loads(text)
    except json_module.JSONDecodeError as e:
        logger.error(f"CLD AI returned invalid JSON: {e}")
        raise HTTPException(500, f"AI returned invalid JSON: {str(e)[:100]}")
    except Exception as e:
        from core.llm_errors import llm_error_to_http
        rid = getattr(request.state, "request_id", None)
        raise llm_error_to_http(e, request_id=rid)

    cld_id = f"CLD-{module_type.upper()}-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)
    doc = {
        "cld_id": cld_id,
        "user_id": uid,
        "module_type": module_type,
        "context_id": context_id,
        "decision_id": f"module_{module_type}_{context_id or 'default'}",
        "nodes": cld_data.get("nodes", []),
        "links": cld_data.get("links", []),
        "created_at": now,
        "updated_at": now,
    }

    await db.cld_diagrams.update_one(
        {"user_id": uid, "module_type": module_type, "context_id": context_id or "default"},
        {"$set": doc},
        upsert=True
    )

    return doc


@router.get("/module/{module_type}")
async def get_module_cld(module_type: str, request: Request, user: dict = Depends(get_current_user)):
    """Get the CLD for a specific module."""
    context_id = request.query_params.get("context_id", "default")
    cld = await db.cld_diagrams.find_one(
        {"user_id": user["user_id"], "module_type": module_type, "context_id": context_id},
        {"_id": 0}
    )
    if not cld:
        return {"cld": None, "message": f"No CLD found for {module_type}. Generate one first."}
    return cld


# ════════════════════════════════════════════════════════
# CLD ENGINE PHASE A — Manual CRUD for Module CLDs
# ════════════════════════════════════════════════════════

@router.post("/module/{module_type}/save")
async def save_module_cld(module_type: str, request: Request, user: dict = Depends(get_current_user)):
    """Save or update a manually-edited module CLD (Phase A visual editor)."""
    if module_type not in MODULE_TYPES:
        raise HTTPException(400, f"Invalid module_type. Use: {MODULE_TYPES}")
    body = await request.json()
    context_id = body.get("context_id", "default")
    now = datetime.now(timezone.utc)

    doc = {
        "user_id": user["user_id"],
        "module_type": module_type,
        "context_id": context_id,
        "decision_id": f"module_{module_type}_{context_id}",
        "nodes": body.get("nodes", []),
        "links": body.get("links", []),
        "loops": body.get("loops", []),
        "layout_type": body.get("layout_type", "manual"),
        "notes": body.get("notes", ""),
        "updated_at": now,
    }
    existing = await db.cld_diagrams.find_one(
        {"user_id": user["user_id"], "module_type": module_type, "context_id": context_id}
    )
    if existing:
        await db.cld_diagrams.update_one(
            {"user_id": user["user_id"], "module_type": module_type, "context_id": context_id},
            {"$set": doc}
        )
        return {"message": "Module CLD updated", "node_count": len(doc["nodes"]), "link_count": len(doc["links"])}
    else:
        doc["cld_id"] = f"CLD-{module_type.upper()}-{uuid.uuid4().hex[:8].upper()}"
        doc["created_at"] = now
        await db.cld_diagrams.insert_one(doc)
        return {"message": "Module CLD saved", "cld_id": doc["cld_id"]}


@router.delete("/module/{module_type}")
async def delete_module_cld(module_type: str, request: Request, user: dict = Depends(get_current_user)):
    """Delete a module CLD."""
    context_id = request.query_params.get("context_id", "default")
    result = await db.cld_diagrams.delete_one(
        {"user_id": user["user_id"], "module_type": module_type, "context_id": context_id}
    )
    if result.deleted_count == 0:
        raise HTTPException(404, "Module CLD not found")
    return {"message": "Module CLD deleted"}


# ════════════════════════════════════════════════════════
# CLD ENGINE PHASE D — TEPFI + Time Dezider deterministic generators
# ════════════════════════════════════════════════════════

def _build_tepfi_cld_graph(tepfi_entries: list) -> dict:
    """Build a deterministic TEPFI 5×3 (Time/Effort/People/Finance/Infra × Self/Micro/Macro) CLD.
    Each cell becomes a node; structural causal links connect dimensions within the same layer,
    and cross-layer links flow Self → Micro → Macro.
    """
    DIMS = [
        ("time", "Time", "#3B82F6"),
        ("effort", "Effort", "#F59E0B"),
        ("people", "People", "#10B981"),
        ("finance", "Finance", "#8B5CF6"),
        ("infra", "Infrastructure", "#EF4444"),
    ]
    LAYERS = [("self", "Self"), ("micro", "Micro"), ("macro", "Macro")]

    # Aggregate scores by (dim, layer)
    cell_scores: dict = {}
    for entry in tepfi_entries:
        dims_data = entry.get("dimensions", {}) if isinstance(entry, dict) else {}
        for dim_id, _, _ in DIMS:
            dim_data = dims_data.get(dim_id, {}) or {}
            for layer_id, _ in LAYERS:
                level = dim_data.get(layer_id, {}) or {}
                score = level.get("score", 0) or 0
                key = (dim_id, layer_id)
                cell_scores.setdefault(key, []).append(score)
    cell_avg = {k: (sum(v) / len(v)) if v else 0 for k, v in cell_scores.items()}

    nodes = []
    for di, (dim_id, dim_name, color) in enumerate(DIMS):
        for li, (layer_id, layer_name) in enumerate(LAYERS):
            score = round(cell_avg.get((dim_id, layer_id), 0), 1)
            nodes.append({
                "factor_id": f"tepfi_{dim_id}_{layer_id}",
                "name": f"{dim_name}·{layer_name}",
                "x": 80 + li * 200,
                "y": 60 + di * 100,
                "base_value": min(100.0, score * 10),
                "centrality": 0.5,
                "classification": "primary" if score >= 7 else "secondary",
                "priority_rank": di + 1,
                "gap_multiplier": max(0.5, 2.0 - score / 5.0) if score else 1.5,
                "locked": False,
                "color": color,
                "tepfi_dim": dim_id,
                "tepfi_layer": layer_id,
            })

    links = []
    # Within-layer dimension chains: Time → Effort → People → Finance → Infra
    for li, (layer_id, _) in enumerate(LAYERS):
        for di in range(len(DIMS) - 1):
            d1, d2 = DIMS[di][0], DIMS[di + 1][0]
            links.append({
                "from_id": f"tepfi_{d1}_{layer_id}",
                "to_id": f"tepfi_{d2}_{layer_id}",
                "link_type": "reinforcing",
                "strength": 5.0,
                "delay": 0,
                "description": f"{DIMS[di][1]} fuels {DIMS[di+1][1]} at {layer_id} layer",
            })
    # Cross-layer flow: Self → Micro → Macro for each dimension
    for dim_id, dim_name, _ in DIMS:
        links.append({
            "from_id": f"tepfi_{dim_id}_self",
            "to_id": f"tepfi_{dim_id}_micro",
            "link_type": "reinforcing", "strength": 6.0, "delay": 1,
            "description": f"Personal {dim_name} scales to micro environment",
        })
        links.append({
            "from_id": f"tepfi_{dim_id}_micro",
            "to_id": f"tepfi_{dim_id}_macro",
            "link_type": "reinforcing", "strength": 5.0, "delay": 2,
            "description": f"Micro {dim_name} aggregates into macro impact",
        })
    return {"nodes": nodes, "links": links}


def _build_time_dezider_cld_graph(time_entries: list, life_areas_hours: dict) -> dict:
    """Time Dezider CLD: nodes are life-area time allocations; central node is 'Available Time'.
    Each allocation drains Available Time (balancing) but reinforces outcomes."""
    nodes = [{
        "factor_id": "td_available",
        "name": "Available Time",
        "x": 300, "y": 220, "base_value": 100.0,
        "centrality": 1.0, "classification": "primary",
        "priority_rank": 1, "gap_multiplier": 1.0, "locked": True,
        "color": "#6366F1",
    }]
    links = []

    area_meta = [
        ("career", "Career", "#3B82F6"),
        ("finance", "Finance", "#8B5CF6"),
        ("relationships", "Relationships", "#EC4899"),
        ("holistic_health", "Health", "#10B981"),
        ("knowledge_skills", "Learning", "#F59E0B"),
        ("hobbies_entertainment", "Leisure", "#F97316"),
        ("spirituality_religion", "Spirituality", "#84CC16"),
        ("social_contributions", "Contribution", "#06B6D4"),
    ]
    import math as _m
    n = len(area_meta)
    for i, (area_id, name, color) in enumerate(area_meta):
        angle = 2 * _m.pi * i / n
        x = 300 + 200 * _m.cos(angle)
        y = 220 + 160 * _m.sin(angle)
        hours = float(life_areas_hours.get(area_id, 0) or 0)
        nodes.append({
            "factor_id": f"td_{area_id}",
            "name": f"{name} ({hours}h)" if hours else name,
            "x": x, "y": y,
            "base_value": min(100.0, hours * 4) if hours else 30.0,
            "centrality": 0.6,
            "classification": "primary" if hours >= 5 else "secondary",
            "priority_rank": i + 2,
            "gap_multiplier": 1.0,
            "locked": False,
            "color": color,
            "life_area": area_id,
        })
        # Available time DRAINS into each area (balancing for available, reinforcing for area)
        links.append({
            "from_id": "td_available", "to_id": f"td_{area_id}",
            "link_type": "reinforcing", "strength": min(10.0, max(2.0, hours)),
            "delay": 0,
            "description": f"Time allocated to {name}",
        })
        # Each area, when neglected, generates backlog that further drains availability
        links.append({
            "from_id": f"td_{area_id}", "to_id": "td_available",
            "link_type": "balancing", "strength": 4.0, "delay": 1,
            "description": f"Neglected {name} creates rework that drains Available Time",
        })
    return {"nodes": nodes, "links": links}


def _add_tepfi_timedezider_bridges(nodes: list, links: list) -> None:
    """Add cross-module causal links between TEPFI Time/Effort and Time Dezider Available Time."""
    has_tepfi_time_self = any(n.get("factor_id") == "tepfi_time_self" for n in nodes)
    has_td_available = any(n.get("factor_id") == "td_available" for n in nodes)
    if has_tepfi_time_self and has_td_available:
        links.append({
            "from_id": "tepfi_time_self", "to_id": "td_available",
            "link_type": "reinforcing", "strength": 7.0, "delay": 0,
            "description": "Personal time discipline (TEPFI·Time·Self) drives Available Time",
        })
    if any(n.get("factor_id") == "tepfi_effort_self" for n in nodes) and has_td_available:
        links.append({
            "from_id": "tepfi_effort_self", "to_id": "td_available",
            "link_type": "balancing", "strength": 4.0, "delay": 1,
            "description": "High effort burn depletes Available Time",
        })


@router.post("/module/tepfi/generate-structured")
async def generate_tepfi_structured(request: Request, user: dict = Depends(get_current_user)):
    """Deterministic Phase D generator for TEPFI module CLD (no LLM call)."""
    uid = user["user_id"]
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    context_id = body.get("context_id", "default")
    tepfi_entries = await db.tepfi_entries.find({"user_id": uid}, {"_id": 0}).to_list(50)
    graph = _build_tepfi_cld_graph(tepfi_entries)
    now = datetime.now(timezone.utc)
    doc = {
        "cld_id": f"CLD-TEPFI-{uuid.uuid4().hex[:8].upper()}",
        "user_id": uid,
        "module_type": "tepfi",
        "context_id": context_id,
        "decision_id": f"module_tepfi_{context_id}",
        "nodes": graph["nodes"],
        "links": graph["links"],
        "loops": [],
        "layout_type": "grid",
        "created_at": now,
        "updated_at": now,
    }
    await db.cld_diagrams.update_one(
        {"user_id": uid, "module_type": "tepfi", "context_id": context_id},
        {"$set": doc}, upsert=True
    )
    return {"message": "TEPFI CLD generated", "node_count": len(doc["nodes"]), "link_count": len(doc["links"])}


@router.post("/module/time_dezider/generate-structured")
async def generate_time_dezider_structured(request: Request, user: dict = Depends(get_current_user)):
    """Deterministic Phase D generator for Time Dezider module CLD (no LLM call)."""
    uid = user["user_id"]
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    context_id = body.get("context_id", "default")
    # Aggregate hours per life area from active lifestyle plan
    plan = await db.lifestyle_plans.find_one({"user_id": uid, "is_active": True}, {"_id": 0})
    area_hours: dict = {}
    if plan:
        weekday = (plan.get("allocations", {}) or {}).get("weekday", {}) or {}
        for area_id, alloc in weekday.items():
            if isinstance(alloc, dict):
                area_hours[area_id] = float(alloc.get("hours", 0) or 0)
    graph = _build_time_dezider_cld_graph([], area_hours)
    now = datetime.now(timezone.utc)
    doc = {
        "cld_id": f"CLD-TIMEDEZIDER-{uuid.uuid4().hex[:8].upper()}",
        "user_id": uid,
        "module_type": "time_dezider",
        "context_id": context_id,
        "decision_id": f"module_time_dezider_{context_id}",
        "nodes": graph["nodes"],
        "links": graph["links"],
        "loops": [],
        "layout_type": "radial",
        "created_at": now,
        "updated_at": now,
    }
    await db.cld_diagrams.update_one(
        {"user_id": uid, "module_type": "time_dezider", "context_id": context_id},
        {"$set": doc}, upsert=True
    )
    return {"message": "Time Dezider CLD generated", "node_count": len(doc["nodes"]), "link_count": len(doc["links"])}


@router.post("/module/master/generate-bridge")
async def generate_master_bridge(request: Request, user: dict = Depends(get_current_user)):
    """Generate a Master CLD that bridges TEPFI + Time Dezider deterministically (Phase D)."""
    uid = user["user_id"]
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    context_id = body.get("context_id", "default")

    tepfi_entries = await db.tepfi_entries.find({"user_id": uid}, {"_id": 0}).to_list(50)
    tepfi_graph = _build_tepfi_cld_graph(tepfi_entries)

    plan = await db.lifestyle_plans.find_one({"user_id": uid, "is_active": True}, {"_id": 0})
    area_hours: dict = {}
    if plan:
        weekday = (plan.get("allocations", {}) or {}).get("weekday", {}) or {}
        for area_id, alloc in weekday.items():
            if isinstance(alloc, dict):
                area_hours[area_id] = float(alloc.get("hours", 0) or 0)
    td_graph = _build_time_dezider_cld_graph([], area_hours)

    # Offset TEPFI nodes to the left and Time Dezider to the right for visual clarity
    for n in tepfi_graph["nodes"]:
        n["x"] = n["x"]  # 80..480
    for n in td_graph["nodes"]:
        n["x"] = n["x"] + 600  # 700..1100

    all_nodes = tepfi_graph["nodes"] + td_graph["nodes"]
    all_links = tepfi_graph["links"] + td_graph["links"]
    _add_tepfi_timedezider_bridges(all_nodes, all_links)

    now = datetime.now(timezone.utc)
    doc = {
        "cld_id": f"CLD-MASTER-{uuid.uuid4().hex[:8].upper()}",
        "user_id": uid,
        "module_type": "master",
        "context_id": context_id,
        "decision_id": f"module_master_{context_id}",
        "nodes": all_nodes,
        "links": all_links,
        "loops": [],
        "layout_type": "manual",
        "created_at": now,
        "updated_at": now,
        "bridge_modules": ["tepfi", "time_dezider"],
    }
    await db.cld_diagrams.update_one(
        {"user_id": uid, "module_type": "master", "context_id": context_id},
        {"$set": doc}, upsert=True
    )
    return {
        "message": "Master TEPFI ↔ Time Dezider bridge CLD generated",
        "node_count": len(all_nodes),
        "link_count": len(all_links),
    }


# ========================
# CLD CRUD ENDPOINTS
# ========================

@router.get("/{decision_id}")
async def get_cld(decision_id: str, user: dict = Depends(get_current_user)):
    """Get saved CLD for a decision"""
    cld = await db.cld_diagrams.find_one(
        {"decision_id": decision_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if not cld:
        return {"cld": None, "message": "No CLD saved for this decision"}
    return {"cld": cld}


@router.post("/{decision_id}/save")
async def save_cld(decision_id: str, data: CLDSaveRequest, user: dict = Depends(get_current_user)):
    """Save or update a CLD diagram for a decision"""
    now = datetime.now(timezone.utc)

    existing = await db.cld_diagrams.find_one(
        {"decision_id": decision_id, "user_id": user["user_id"]},
        {"_id": 0}
    )

    cld_doc = {
        "decision_id": decision_id,
        "user_id": user["user_id"],
        "nodes": data.nodes,
        "links": data.links,
        "loops": data.loops,
        "layout_type": data.layout_type,
        "notes": data.notes,
        "updated_at": now,
    }

    if existing:
        await db.cld_diagrams.update_one(
            {"decision_id": decision_id, "user_id": user["user_id"]},
            {"$set": cld_doc}
        )
        return {"message": "CLD updated", "id": existing.get("id", decision_id)}
    else:
        cld_doc["id"] = str(uuid.uuid4())
        cld_doc["created_at"] = now
        await db.cld_diagrams.insert_one(cld_doc)
        return {"message": "CLD saved", "id": cld_doc["id"]}


@router.delete("/{decision_id}")
async def delete_cld(decision_id: str, user: dict = Depends(get_current_user)):
    """Delete a saved CLD diagram"""
    result = await db.cld_diagrams.delete_one(
        {"decision_id": decision_id, "user_id": user["user_id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="CLD not found")
    return {"message": "CLD deleted"}


@router.put("/{decision_id}/node/{factor_id}")
async def update_node(decision_id: str, factor_id: str, data: NodeUpdateRequest, user: dict = Depends(get_current_user)):
    """Update a specific node's properties (position, centrality, etc.)"""
    cld = await db.cld_diagrams.find_one(
        {"decision_id": decision_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if not cld:
        raise HTTPException(status_code=404, detail="CLD not found")

    nodes = cld.get("nodes", [])
    updated = False
    for node in nodes:
        if node.get("factor_id") == factor_id:
            update_dict = {k: v for k, v in data.dict().items() if v is not None}
            node.update(update_dict)
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Node not found in CLD")

    await db.cld_diagrams.update_one(
        {"decision_id": decision_id, "user_id": user["user_id"]},
        {"$set": {"nodes": nodes, "updated_at": datetime.now(timezone.utc)}}
    )
    return {"message": "Node updated"}


@router.put("/{decision_id}/link")
async def update_link(decision_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Update a specific link's properties"""
    body = await request.json()
    from_id = body.get("from_id")
    to_id = body.get("to_id")

    cld = await db.cld_diagrams.find_one(
        {"decision_id": decision_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if not cld:
        raise HTTPException(status_code=404, detail="CLD not found")

    links = cld.get("links", [])
    updated = False
    for link in links:
        if link.get("from_id") == from_id and link.get("to_id") == to_id:
            for key in ["link_type", "strength", "delay", "description"]:
                if key in body and body[key] is not None:
                    link[key] = body[key]
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Link not found")

    await db.cld_diagrams.update_one(
        {"decision_id": decision_id, "user_id": user["user_id"]},
        {"$set": {"links": links, "updated_at": datetime.now(timezone.utc)}}
    )
    return {"message": "Link updated"}


# ========================
# SIMULATION ENGINE
# ========================

@router.post("/{decision_id}/simulate")
async def simulate_cld(decision_id: str, sim: SimulationRequest, user: dict = Depends(get_current_user)):
    """
    Run a dynamic simulation on the CLD.
    Propagates a 'shock' to one factor through causal links over multiple time steps.
    
    Algorithm:
    1. Start with baseline values for each node
    2. Apply shock_delta to shock_factor
    3. For each time step, propagate changes through links:
       - Reinforcing: downstream += upstream_change * strength/10 * dampening
       - Balancing: downstream -= upstream_change * strength/10 * dampening
    4. Track values at each step
    5. Assess stability
    """
    cld = await db.cld_diagrams.find_one(
        {"decision_id": decision_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if not cld:
        raise HTTPException(status_code=404, detail="No CLD saved. Generate and save a CLD first.")

    nodes = cld.get("nodes", [])
    links = cld.get("links", [])

    if not nodes or not links:
        raise HTTPException(status_code=400, detail="CLD has no nodes or links for simulation")

    # Normalize node factor_id (handle both 'factor_id' and 'id' field names)
    for node in nodes:
        if "factor_id" not in node and "id" in node:
            node["factor_id"] = node["id"]
        elif "factor_id" not in node:
            node["factor_id"] = str(node.get("name", "unknown"))

    # Validate shock factor exists
    shock_node = next((n for n in nodes if n.get("factor_id") == sim.shock_factor_id), None)
    if not shock_node:
        raise HTTPException(status_code=404, detail=f"Factor {sim.shock_factor_id} not found in CLD")

    # Build adjacency map: from_id -> [(to_id, type, strength, delay)]
    adj = {}
    for link in links:
        fid = link.get("from_id")
        if fid not in adj:
            adj[fid] = []
        adj[fid].append({
            "to_id": link.get("to_id"),
            "type": link.get("link_type", link.get("type", "reinforcing")),
            "strength": link.get("strength", 5),
            "delay": link.get("delay", 0),
        })

    # Initialize values
    values = {}
    for node in nodes:
        values[node.get("factor_id")] = node.get("base_value", 50.0)

    baseline = dict(values)
    timeline = []
    dampening = max(0.01, min(1.0, sim.dampening))
    time_steps = max(1, min(20, sim.time_steps))

    # Record initial state
    timeline.append({
        "step": 0,
        "values": dict(values),
        "deltas": {fid: 0.0 for fid in values},
    })

    # Apply initial shock
    values[sim.shock_factor_id] = max(0, min(100, values[sim.shock_factor_id] + sim.shock_delta))

    # Track pending changes with delay
    pending_changes = []  # (apply_at_step, factor_id, delta)

    for step in range(1, time_steps + 1):
        prev_values = dict(values)
        changes = {fid: 0.0 for fid in values}

        if step == 1:
            # Direct shock propagation
            shock_change = sim.shock_delta
            if sim.shock_factor_id in adj:
                for edge in adj[sim.shock_factor_id]:
                    delta = shock_change * (edge["strength"] / 10.0) * dampening
                    if edge["type"] == "balancing":
                        delta = -delta
                    apply_step = step + edge.get("delay", 0)
                    if apply_step <= time_steps:
                        if edge["delay"] > 0:
                            pending_changes.append((apply_step, edge["to_id"], delta))
                        else:
                            # Check if node is locked
                            target_node = next((n for n in nodes if n.get("factor_id") == edge["to_id"]), None)
                            if not target_node or not target_node.get("locked", False):
                                changes[edge["to_id"]] += delta
        else:
            # Propagate changes from previous step
            for fid in values:
                prev_delta = prev_values[fid] - (timeline[-1]["values"].get(fid, prev_values[fid]) if len(timeline) >= 2 else baseline.get(fid, prev_values[fid]))
                if abs(prev_delta) > 0.01 and fid in adj:
                    for edge in adj[fid]:
                        # Scale propagation by dampening^step for natural decay
                        delta = prev_delta * (edge["strength"] / 10.0) * dampening
                        if edge["type"] == "balancing":
                            delta = -delta
                        apply_step = step + edge.get("delay", 0)
                        if apply_step <= time_steps:
                            if edge["delay"] > 0:
                                pending_changes.append((apply_step, edge["to_id"], delta))
                            else:
                                target_node = next((n for n in nodes if n.get("factor_id") == edge["to_id"]), None)
                                if not target_node or not target_node.get("locked", False):
                                    changes[edge["to_id"]] += delta

        # Apply pending changes for this step
        for pc_step, pc_fid, pc_delta in pending_changes:
            if pc_step == step:
                target_node = next((n for n in nodes if n.get("factor_id") == pc_fid), None)
                if not target_node or not target_node.get("locked", False):
                    changes[pc_fid] += pc_delta

        # Apply changes
        deltas = {}
        for fid in values:
            old_val = values[fid]
            new_val = max(0, min(100, old_val + changes[fid]))
            values[fid] = round(new_val, 2)
            deltas[fid] = round(new_val - old_val, 2)

        timeline.append({
            "step": step,
            "values": dict(values),
            "deltas": deltas,
        })

    # Calculate total impact
    total_impact = {}
    for fid in values:
        total_impact[fid] = round(values[fid] - baseline[fid], 2)

    # Assess stability
    if len(timeline) >= 3:
        last_deltas = [sum(abs(d) for d in t["deltas"].values()) for t in timeline[-3:]]
        if all(d < 0.5 for d in last_deltas):
            stability = "stable"
        elif last_deltas[-1] > last_deltas[-2] > last_deltas[-3]:
            stability = "diverging"
        else:
            stability = "oscillating"
    else:
        stability = "stable"

    # Most affected factors
    sorted_impact = sorted(total_impact.items(), key=lambda x: abs(x[1]), reverse=True)
    most_affected = [fid for fid, _ in sorted_impact[:5] if fid != sim.shock_factor_id]

    return {
        "timeline": timeline,
        "final_values": values,
        "total_impact": total_impact,
        "stability": stability,
        "most_affected": most_affected,
        "baseline": baseline,
    }


# ========================
# AI CLD GENERATION (Enhanced)
# ========================

@router.post("/{decision_id}/generate")
async def generate_cld(decision_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Generate CLD using AI and optionally auto-save it.
    
    Body: { factors: [{id, name}], decision_title, decision_context, life_area, decision_type, auto_save: bool }
    """
    from core.llm_compat import LlmChat, UserMessage  # provider-agnostic shim (Emergent | direct via litellm)

    body = await request.json()

    # Deduct credits for AI generation
    await _deduct_ai_credits(user["user_id"], "cld_generate")

    title = body.get("decision_title", "")
    context = body.get("decision_context", "")
    life_area = body.get("life_area", "")
    decision_type = body.get("decision_type", "")
    factors = body.get("factors", [])
    auto_save = body.get("auto_save", True)

    if len(factors) < 2:
        raise HTTPException(status_code=400, detail="At least 2 factors required for CLD")

    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="LLM key not configured")

    factor_names = [f.get("name", "") for f in factors]
    factor_ids = [f.get("id", "") for f in factors]
    factor_list_str = "\n".join([f"  {i+1}. {name} (id: {fid})" for i, (name, fid) in enumerate(zip(factor_names, factor_ids))])

    prompt = f"""Analyze the following decision factors using Causal Loop Diagram (CLD) methodology from Systems Thinking.

Decision: {title}
Context: {context}
Life Area: {life_area}
Decision Type: {decision_type}

Factors:
{factor_list_str}

Perform the following analysis and return ONLY a valid JSON object:

1. **CLD Links**: Identify ALL meaningful causal relationships between factors. For each link:
   - from_id: source factor id
   - to_id: target factor id  
   - link_type: "reinforcing" (same direction change) or "balancing" (opposite direction change)
   - strength: 1-10 (how strong the causal link is)
   - delay: 0-3 (time-step delay, 0 = immediate effect)
   - description: brief explanation of the causal relationship

2. **CLD Loops**: Identify ALL feedback loops (reinforcing R or balancing B):
   - name: loop name (e.g., "R1: Growth Loop")
   - loop_type: "reinforcing" or "balancing"
   - factor_ids: array of factor ids in the loop (in order)

3. **Factor Analysis**: For each factor, compute:
   - centrality: 0.0 to 1.0 (based on connections and loop participation)
   - classification: "primary" (centrality >= 0.5) or "secondary"
   - priority_rank: 1 = most influential
   - gap_multiplier: 0.5-3.0 (based on centrality gaps)
   - base_value: 30-70 (estimated current state, 50 = neutral)
   - reasoning: brief explanation

Return this exact JSON structure:
{{
  "links": [
    {{"from_id": "...", "to_id": "...", "link_type": "reinforcing|balancing", "strength": 1-10, "delay": 0-3, "description": "..."}}
  ],
  "loops": [
    {{"name": "R1: ...", "loop_type": "reinforcing|balancing", "factor_ids": ["..."]}}
  ],
  "factor_analysis": [
    {{
      "factor_id": "...",
      "factor_name": "...",
      "centrality": 0.0-1.0,
      "classification": "primary|secondary",
      "priority_rank": 1,
      "gap_multiplier": 0.5-3.0,
      "base_value": 30-70,
      "reasoning": "brief explanation"
    }}
  ]
}}

Return ONLY valid JSON, no markdown fences, no explanation outside the JSON."""

    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"cld_{user['user_id']}_{uuid.uuid4().hex[:8]}",
            system_message="You are an expert in Systems Thinking and Causal Loop Diagrams. Analyze factor relationships precisely and identify all meaningful causal connections."
        ).with_model("openai", "gpt-4.1-mini")

        response = await chat.send_message(UserMessage(text=prompt))
        response_text = response.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        cld_data = json_module.loads(response_text)

        # Build node positions using force-directed-like layout
        n = len(factors)
        nodes = []
        for i, factor in enumerate(factors):
            angle = (2 * math.pi * i) / n
            fa = next((fa for fa in cld_data.get("factor_analysis", []) if fa["factor_id"] == factor["id"]), None)
            nodes.append({
                "factor_id": factor["id"],
                "name": factor["name"],
                "x": round(200 + 140 * math.cos(angle), 2),
                "y": round(200 + 140 * math.sin(angle), 2),
                "centrality": fa["centrality"] if fa else 0.5,
                "classification": fa["classification"] if fa else "secondary",
                "priority_rank": fa["priority_rank"] if fa else i + 1,
                "gap_multiplier": fa["gap_multiplier"] if fa else 1.0,
                "base_value": fa.get("base_value", 50.0) if fa else 50.0,
                "locked": False,
            })

        cld_result = {
            "nodes": nodes,
            "links": cld_data.get("links", []),
            "loops": cld_data.get("loops", []),
        }

        # Auto-save if requested
        if auto_save:
            now = datetime.now(timezone.utc)
            existing = await db.cld_diagrams.find_one(
                {"decision_id": decision_id, "user_id": user["user_id"]},
                {"_id": 0}
            )
            save_doc = {
                "decision_id": decision_id,
                "user_id": user["user_id"],
                "nodes": nodes,
                "links": cld_data.get("links", []),
                "loops": cld_data.get("loops", []),
                "layout_type": "circular",
                "notes": "",
                "updated_at": now,
            }
            if existing:
                await db.cld_diagrams.update_one(
                    {"decision_id": decision_id, "user_id": user["user_id"]},
                    {"$set": save_doc}
                )
            else:
                save_doc["id"] = str(uuid.uuid4())
                save_doc["created_at"] = now
                await db.cld_diagrams.insert_one(save_doc)

        return {
            "cld": cld_result,
            "factor_analysis": cld_data.get("factor_analysis", []),
            "auto_saved": auto_save,
        }
    except json_module.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"AI returned invalid JSON: {str(e)[:100]}")
    except HTTPException:
        raise  # re-raise our typed errors as-is
    except Exception as e:
        from core.llm_errors import llm_error_to_http
        rid = getattr(request.state, "request_id", None)
        raise llm_error_to_http(e, request_id=rid)


# ========================
# FORCE-DIRECTED LAYOUT
# ========================

@router.post("/{decision_id}/layout")
async def compute_layout(decision_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Compute force-directed layout for CLD nodes.
    
    Simple force-directed algorithm:
    - Repulsion between all nodes
    - Attraction along links
    - Gravity toward center
    """
    cld = await db.cld_diagrams.find_one(
        {"decision_id": decision_id, "user_id": user["user_id"]},
        {"_id": 0}
    )
    if not cld:
        raise HTTPException(status_code=404, detail="No CLD found")

    body = await request.json()
    layout_type = body.get("layout_type", "force")

    nodes = cld.get("nodes", [])
    links = cld.get("links", [])

    if layout_type == "circular":
        # Circular layout (default)
        n = len(nodes)
        for i, node in enumerate(nodes):
            angle = (2 * math.pi * i) / n
            node["x"] = round(200 + 140 * math.cos(angle), 2)
            node["y"] = round(200 + 140 * math.sin(angle), 2)

    elif layout_type == "force":
        # Simple force-directed layout
        positions = {n["factor_id"]: {"x": n.get("x", 200), "y": n.get("y", 200)} for n in nodes}
        
        CENTER_X, CENTER_Y = 200, 200
        REPULSION = 5000
        ATTRACTION = 0.01
        GRAVITY = 0.02
        ITERATIONS = 100
        DT = 0.5

        for _ in range(ITERATIONS):
            forces = {fid: {"fx": 0, "fy": 0} for fid in positions}

            # Repulsion (all pairs)
            ids = list(positions.keys())
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    a, b = ids[i], ids[j]
                    dx = positions[a]["x"] - positions[b]["x"]
                    dy = positions[a]["y"] - positions[b]["y"]
                    dist2 = dx * dx + dy * dy + 1
                    dist = math.sqrt(dist2)
                    force = REPULSION / dist2
                    fx = force * dx / dist
                    fy = force * dy / dist
                    forces[a]["fx"] += fx
                    forces[a]["fy"] += fy
                    forces[b]["fx"] -= fx
                    forces[b]["fy"] -= fy

            # Attraction (along links)
            for link in links:
                fid = link.get("from_id")
                tid = link.get("to_id")
                if fid in positions and tid in positions:
                    dx = positions[tid]["x"] - positions[fid]["x"]
                    dy = positions[tid]["y"] - positions[fid]["y"]
                    dist = math.sqrt(dx * dx + dy * dy) + 1
                    force = ATTRACTION * dist * (link.get("strength", 5) / 5.0)
                    forces[fid]["fx"] += force * dx / dist
                    forces[fid]["fy"] += force * dy / dist
                    forces[tid]["fx"] -= force * dx / dist
                    forces[tid]["fy"] -= force * dy / dist

            # Gravity toward center
            for fid in positions:
                dx = CENTER_X - positions[fid]["x"]
                dy = CENTER_Y - positions[fid]["y"]
                forces[fid]["fx"] += GRAVITY * dx
                forces[fid]["fy"] += GRAVITY * dy

            # Update positions
            for fid in positions:
                positions[fid]["x"] += forces[fid]["fx"] * DT
                positions[fid]["y"] += forces[fid]["fy"] * DT
                # Clamp to bounds
                positions[fid]["x"] = max(30, min(370, positions[fid]["x"]))
                positions[fid]["y"] = max(30, min(370, positions[fid]["y"]))

        # Update node positions
        for node in nodes:
            pos = positions.get(node["factor_id"])
            if pos:
                node["x"] = round(pos["x"], 2)
                node["y"] = round(pos["y"], 2)

    elif layout_type == "hierarchical":
        # Hierarchical: place by priority rank
        n = len(nodes)
        sorted_nodes = sorted(nodes, key=lambda x: x.get("priority_rank", 99))
        rows = max(1, math.ceil(math.sqrt(n)))
        for i, node in enumerate(sorted_nodes):
            row = i // rows
            col = i % rows
            node["x"] = round(60 + col * (320 / max(1, rows - 1)) if rows > 1 else 200, 2)
            node["y"] = round(60 + row * (320 / max(1, math.ceil(n / rows) - 1)) if math.ceil(n / rows) > 1 else 200, 2)

    # Save updated layout
    await db.cld_diagrams.update_one(
        {"decision_id": decision_id, "user_id": user["user_id"]},
        {"$set": {"nodes": nodes, "layout_type": layout_type, "updated_at": datetime.now(timezone.utc)}}
    )

    return {"nodes": nodes, "layout_type": layout_type}



# (Module CLD routes moved above /{decision_id} to avoid routing conflicts)
