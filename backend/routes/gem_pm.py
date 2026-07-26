"""
GEM Project Management (PM) Workspace
=====================================
Full-fledged PM layer on top of a GEM Goal (Tier-1 of the JELCOS PM spec):

  WBS:            Goal → Milestones → Deliverables → Work Packages
                  → Task (CTT / Routine) → Subtask (recursive under a task)
  Dependencies:   FS / SS / FF / SF with lag days
  Critical Path:  CPM forward/backward pass, zero-slack nodes flagged
  Gantt:          computed ES/EF day offsets + date range
  Kanban:         backlog → todo → in_progress → review → done
  Team roles:     owner / co_owner / reviewer / approver / watchers[]
  Est vs Actual:  start / finish / hours + variance
  Registers:      Risks / Issues / Change Log (Tier-2 lite)

Collections: gem_pm_nodes, gem_pm_deps, gem_pm_registers
"""
import uuid
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from core.database import db
from core.auth import get_current_user
from core.action_status import normalize_status, progress_for

router = APIRouter(prefix="/gem-pm", tags=["GEM PM"])

NODE_TYPES = ["milestone", "deliverable", "work_package", "task", "subtask"]

# Parent type → allowed child types (tasks allowed early to reduce ceremony)
ALLOWED_CHILDREN = {
    "root": ["milestone", "task"],
    "milestone": ["deliverable", "task"],
    "deliverable": ["work_package", "task"],
    "work_package": ["task"],
    "task": ["subtask"],
    "subtask": ["subtask"],
}

KANBAN_COLS = ["backlog", "todo", "in_progress", "review", "done"]
COL_TO_STATUS = {
    "backlog": "pending", "todo": "pending", "in_progress": "wip_50",
    "review": "wip_75", "done": "done",
}
STATUS_TO_COL = {
    "pending": "todo", "wip_25": "in_progress", "wip_50": "in_progress",
    "wip_75": "review", "done": "done", "blocked": "in_progress",
    "deferred": "backlog", "cancelled": "backlog",
}
DEP_TYPES = {"FS", "SS", "FF", "SF"}
REGISTER_KINDS = {"risk", "issue", "change"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_d(s) -> Optional[date]:
    try:
        return date.fromisoformat(str(s)[:10])
    except Exception:
        return None


async def _own_goal(goal_id: str, user: dict) -> dict:
    g = await db.gem_goals.find_one({"goal_id": goal_id, "user_id": user["user_id"]}, {"_id": 0})
    if not g:
        raise HTTPException(404, "GEM goal not found")
    return g


def _node_from_body(body: Dict[str, Any]) -> Dict[str, Any]:
    a = body.get("assignments") or {}
    return {
        "title": (body.get("title") or "").strip(),
        "description": body.get("description") or "",
        "status": normalize_status(body.get("status")),
        "progress_pct": max(0, min(100, int(body.get("progress_pct") or 0))),
        "assignments": {
            "owner": a.get("owner") or "",
            "co_owner": a.get("co_owner") or "",
            "reviewer": a.get("reviewer") or "",
            "approver": a.get("approver") or "",
            "watchers": a.get("watchers") or [],
        },
        "est_start": body.get("est_start") or None,
        "est_finish": body.get("est_finish") or None,
        "est_hours": float(body.get("est_hours") or 0),
        "actual_start": body.get("actual_start") or None,
        "actual_finish": body.get("actual_finish") or None,
        "actual_hours": float(body.get("actual_hours") or 0),
        "task_kind": body.get("task_kind") or None,  # 'ctt' | 'routine'
    }


# ═══════════════════════════ WBS NODES ═══════════════════════════

@router.post("/{goal_id}/nodes")
async def create_node(goal_id: str, request: Request, user: dict = Depends(get_current_user)):
    await _own_goal(goal_id, user)
    body = await request.json()
    node_type = body.get("node_type")
    if node_type not in NODE_TYPES:
        raise HTTPException(400, f"node_type must be one of {NODE_TYPES}")
    parent_id = body.get("parent_id") or None
    parent_type = "root"
    if parent_id:
        parent = await db.gem_pm_nodes.find_one(
            {"node_id": parent_id, "goal_id": goal_id, "user_id": user["user_id"]})
        if not parent:
            raise HTTPException(404, "parent node not found")
        parent_type = parent["node_type"]
    if node_type not in ALLOWED_CHILDREN.get(parent_type, []):
        raise HTTPException(400, f"a {node_type} cannot be added under a {parent_type}")

    fields = _node_from_body(body)
    if not fields["title"]:
        raise HTTPException(400, "title is required")
    count = await db.gem_pm_nodes.count_documents(
        {"goal_id": goal_id, "user_id": user["user_id"], "parent_id": parent_id})
    doc = {
        "node_id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "goal_id": goal_id,
        "parent_id": parent_id,
        "node_type": node_type,
        **fields,
        "kanban_col": STATUS_TO_COL.get(fields["status"], "todo"),
        "linked_action_id": None,
        "order": count,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.gem_pm_nodes.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/nodes/{node_id}")
async def update_node(node_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    node = await db.gem_pm_nodes.find_one({"node_id": node_id, "user_id": user["user_id"]})
    if not node:
        raise HTTPException(404, "node not found")
    merged = {**node, **body}
    fields = _node_from_body(merged)
    if not fields["title"]:
        raise HTTPException(400, "title is required")
    if "status" in body:
        fields["kanban_col"] = STATUS_TO_COL.get(fields["status"], node.get("kanban_col", "todo"))
        fields["progress_pct"] = progress_for(fields["status"]) if fields["status"] in (
            "pending", "wip_25", "wip_50", "wip_75", "done") else fields["progress_pct"]
    fields["updated_at"] = _now()
    await db.gem_pm_nodes.update_one({"node_id": node_id}, {"$set": fields})
    out = await db.gem_pm_nodes.find_one({"node_id": node_id}, {"_id": 0})
    await _propagate_status(out, user)
    return out


async def _propagate_status(node: Dict[str, Any], user: dict) -> None:
    """A task node ported to CTT/LifeStyle keeps its Action Center item (and
    downstream record) in sync when the WBS status changes."""
    aid = node.get("linked_action_id")
    if not aid:
        return
    st = normalize_status(node.get("status"))
    await db.action_items.update_one(
        {"action_id": aid, "user_id": user["user_id"]},
        {"$set": {"status": st, "progress_pct": progress_for(st), "updated_at": _now()}})
    ai = await db.action_items.find_one({"action_id": aid}, {"_id": 0})
    if ai:
        from routes.action_items import _sync_ported_status
        await _sync_ported_status(ai)


@router.put("/nodes/{node_id}/kanban")
async def move_kanban(node_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    col = body.get("col")
    if col not in KANBAN_COLS:
        raise HTTPException(400, f"col must be one of {KANBAN_COLS}")
    node = await db.gem_pm_nodes.find_one({"node_id": node_id, "user_id": user["user_id"]})
    if not node:
        raise HTTPException(404, "node not found")
    st = COL_TO_STATUS[col]
    await db.gem_pm_nodes.update_one(
        {"node_id": node_id},
        {"$set": {"kanban_col": col, "status": st, "progress_pct": progress_for(st),
                  "updated_at": _now()}})
    out = await db.gem_pm_nodes.find_one({"node_id": node_id}, {"_id": 0})
    await _propagate_status(out, user)
    return out


@router.delete("/nodes/{node_id}")
async def delete_node(node_id: str, user: dict = Depends(get_current_user)):
    node = await db.gem_pm_nodes.find_one({"node_id": node_id, "user_id": user["user_id"]})
    if not node:
        raise HTTPException(404, "node not found")

    # Recursive delete of the subtree
    to_delete = [node_id]
    frontier = [node_id]
    while frontier:
        children = await db.gem_pm_nodes.find(
            {"parent_id": {"$in": frontier}, "user_id": user["user_id"]},
            {"node_id": 1}).to_list(1000)
        frontier = [c["node_id"] for c in children]
        to_delete.extend(frontier)
    await db.gem_pm_nodes.delete_many({"node_id": {"$in": to_delete}})
    await db.gem_pm_deps.delete_many({"$or": [
        {"predecessor_id": {"$in": to_delete}}, {"successor_id": {"$in": to_delete}}]})
    return {"deleted": len(to_delete)}


@router.post("/nodes/{node_id}/port")
async def port_task_node(node_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Port a task/subtask node into CTT (one-time) or LifeStyle (routine) via
    the universal Action Item store (source_module=GEM)."""
    from routes.action_items import _normalise, _ctt_doc_from_action, _routine_doc_from_action
    body = await request.json()
    target = (body.get("target") or "CTT").upper()
    if target not in ("CTT", "LIFESTYLE"):
        raise HTTPException(400, "target must be CTT or LIFESTYLE")
    node = await db.gem_pm_nodes.find_one({"node_id": node_id, "user_id": user["user_id"]}, {"_id": 0})
    if not node:
        raise HTTPException(404, "node not found")
    if node.get("node_type") not in ("task", "subtask"):
        raise HTTPException(400, "only task / subtask nodes can be ported")
    if node.get("linked_action_id"):
        raise HTTPException(409, "already ported — manage it from the Action Center")

    goal = await _own_goal(node["goal_id"], user)
    now = _now()
    norm = _normalise({
        "source_module": "GEM",
        "source_id": node["goal_id"],
        "source_label": f"GEM PM · {goal.get('title','')[:60]}",
        "source_subref": node_id,
        "title": node.get("title"),
        "description": node.get("description"),
        "who": (node.get("assignments") or {}).get("owner") or "",
        "by_when": node.get("est_finish"),
        "recurrence_type": "recurring" if target == "LIFESTYLE" else "one_time",
        "recurrence_frequency": body.get("frequency") or ("daily" if target == "LIFESTYLE" else None),
        "status": node.get("status"),
    }, user)
    ai = {
        "action_id": str(uuid.uuid4()), **norm,
        "ported_to": None, "ported_ref_id": None, "ported_at": None,
        "created_at": now, "updated_at": now,
    }
    await db.action_items.insert_one(ai)
    ai.pop("_id", None)
    if target == "CTT":
        rec = _ctt_doc_from_action(ai, user)
        await db.ctt_tasks.insert_one(rec)
        ref = rec["task_id"]
    else:
        rec = _routine_doc_from_action(ai, user)
        await db.lifestyle_routines.insert_one(rec)
        ref = rec["routine_id"]
    await db.action_items.update_one(
        {"action_id": ai["action_id"]},
        {"$set": {"ported_to": target, "ported_ref_id": ref, "ported_at": now, "updated_at": now}})
    await db.gem_pm_nodes.update_one(
        {"node_id": node_id},
        {"$set": {"linked_action_id": ai["action_id"],
                  "task_kind": "routine" if target == "LIFESTYLE" else "ctt",
                  "updated_at": now}})
    out = await db.gem_pm_nodes.find_one({"node_id": node_id}, {"_id": 0})
    return {"node": out, "action_id": ai["action_id"], "ported_to": target}


# ═══════════════════════════ DEPENDENCIES ═══════════════════════════

@router.post("/{goal_id}/deps")
async def create_dep(goal_id: str, request: Request, user: dict = Depends(get_current_user)):
    await _own_goal(goal_id, user)
    body = await request.json()
    pred, succ = body.get("predecessor_id"), body.get("successor_id")
    dep_type = (body.get("dep_type") or "FS").upper()
    if dep_type not in DEP_TYPES:
        raise HTTPException(400, f"dep_type must be one of {sorted(DEP_TYPES)}")
    if not pred or not succ or pred == succ:
        raise HTTPException(400, "predecessor_id and successor_id must be two different nodes")
    n = await db.gem_pm_nodes.count_documents(
        {"node_id": {"$in": [pred, succ]}, "goal_id": goal_id, "user_id": user["user_id"]})
    if n != 2:
        raise HTTPException(404, "both nodes must exist in this project")
    exists = await db.gem_pm_deps.find_one(
        {"goal_id": goal_id, "predecessor_id": pred, "successor_id": succ})
    if exists:
        raise HTTPException(409, "dependency already exists")
    doc = {
        "dep_id": str(uuid.uuid4()), "user_id": user["user_id"], "goal_id": goal_id,
        "predecessor_id": pred, "successor_id": succ,
        "dep_type": dep_type, "lag_days": int(body.get("lag_days") or 0),
        "created_at": _now(),
    }
    await db.gem_pm_deps.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.delete("/deps/{dep_id}")
async def delete_dep(dep_id: str, user: dict = Depends(get_current_user)):
    r = await db.gem_pm_deps.delete_one({"dep_id": dep_id, "user_id": user["user_id"]})
    if r.deleted_count == 0:
        raise HTTPException(404, "dependency not found")
    return {"deleted": True}


# ═══════════════════════════ CPM / SCHEDULING ═══════════════════════════

def _cpm(nodes: List[Dict], deps: List[Dict]) -> Dict[str, Any]:
    """Critical Path Method over the WBS nodes.
    Durations in days from est_start/est_finish (default 1 day).
    Supports FS/SS/FF/SF + lag. Returns per-node es/ef/slack + critical set."""
    by_id = {n["node_id"]: n for n in nodes}
    dur: Dict[str, int] = {}
    anchor: Optional[date] = None
    for n in nodes:
        s, f = _parse_d(n.get("est_start")), _parse_d(n.get("est_finish"))
        if s and (anchor is None or s < anchor):
            anchor = s
        dur[n["node_id"]] = max(1, (f - s).days + 1) if (s and f and f >= s) else 1
    anchor = anchor or date.today()

    preds: Dict[str, List[Dict]] = {n["node_id"]: [] for n in nodes}
    succs: Dict[str, List[Dict]] = {n["node_id"]: [] for n in nodes}
    for d in deps:
        p, sc = d.get("predecessor_id"), d.get("successor_id")
        if p in by_id and sc in by_id:
            preds[sc].append(d)
            succs[p].append(d)

    # Topological order (Kahn); cycle nodes fall back to declared dates
    indeg = {nid: len(preds[nid]) for nid in by_id}
    queue = [nid for nid, k in indeg.items() if k == 0]
    topo: List[str] = []
    while queue:
        nid = queue.pop(0)
        topo.append(nid)
        for d in succs[nid]:
            sc = d["successor_id"]
            indeg[sc] -= 1
            if indeg[sc] == 0:
                queue.append(sc)
    cyclic = set(by_id) - set(topo)

    es: Dict[str, int] = {}
    ef: Dict[str, int] = {}
    for nid in topo:
        n = by_id[nid]
        base = 0
        s = _parse_d(n.get("est_start"))
        if s:
            base = (s - anchor).days
        e = base
        for d in preds[nid]:
            p = d["predecessor_id"]
            if p not in ef:
                continue
            lag = int(d.get("lag_days") or 0)
            t = d.get("dep_type", "FS")
            if t == "FS":
                cand = ef[p] + lag
            elif t == "SS":
                cand = es[p] + lag
            elif t == "FF":
                cand = ef[p] + lag - dur[nid]
            else:  # SF
                cand = es[p] + lag - dur[nid]
            e = max(e, cand)
        es[nid] = e
        ef[nid] = e + dur[nid]
    for nid in cyclic:  # place at declared date, no CPM
        n = by_id[nid]
        s = _parse_d(n.get("est_start"))
        es[nid] = (s - anchor).days if s else 0
        ef[nid] = es[nid] + dur[nid]

    project_end = max(ef.values()) if ef else 0
    # Backward pass
    lf: Dict[str, int] = {nid: project_end for nid in by_id}
    ls: Dict[str, int] = {}
    for nid in reversed(topo):
        for d in succs[nid]:
            sc = d["successor_id"]
            lag = int(d.get("lag_days") or 0)
            t = d.get("dep_type", "FS")
            if t == "FS":
                cand = (ls.get(sc, lf[sc] - dur[sc])) - lag
            elif t == "SS":
                cand = (ls.get(sc, lf[sc] - dur[sc])) - lag + dur[nid]
            elif t == "FF":
                cand = lf[sc] - lag
            else:  # SF
                cand = lf[sc] - lag + dur[nid]
            lf[nid] = min(lf[nid], cand)
        ls[nid] = lf[nid] - dur[nid]

    out = {}
    critical = []
    has_deps = {nid for nid in by_id if preds[nid] or succs[nid]}
    for nid in by_id:
        slack = ls.get(nid, lf[nid] - dur[nid]) - es[nid]
        is_crit = nid in has_deps and slack <= 0
        if is_crit:
            critical.append(nid)
        out[nid] = {"es": es[nid], "ef": ef[nid], "duration": dur[nid],
                    "slack": slack, "critical": is_crit}
    return {"schedule": out, "critical_path": critical,
            "anchor": anchor.isoformat(), "project_duration": project_end}


# ═══════════════════════════ WORKSPACE (single fetch) ═══════════════════════════

@router.get("/{goal_id}/workspace")
async def get_workspace(goal_id: str, user: dict = Depends(get_current_user)):
    goal = await _own_goal(goal_id, user)
    nodes = await db.gem_pm_nodes.find(
        {"goal_id": goal_id, "user_id": user["user_id"]}, {"_id": 0}
    ).sort("order", 1).to_list(2000)
    deps = await db.gem_pm_deps.find(
        {"goal_id": goal_id, "user_id": user["user_id"]}, {"_id": 0}).to_list(2000)

    cpm = _cpm(nodes, deps) if nodes else {
        "schedule": {}, "critical_path": [], "anchor": date.today().isoformat(), "project_duration": 0}

    # Progress roll-up (bottom-up, weighted by est_hours; default weight 1)
    children: Dict[Optional[str], List[Dict]] = {}
    for n in nodes:
        children.setdefault(n.get("parent_id"), []).append(n)

    rollup: Dict[str, float] = {}
    weight: Dict[str, float] = {}

    def _roll(n: Dict) -> None:
        kids = children.get(n["node_id"], [])
        if not kids:
            rollup[n["node_id"]] = float(n.get("progress_pct") or 0)
            weight[n["node_id"]] = float(n.get("est_hours") or 0) or 1.0
            return
        tw = 0.0
        tp = 0.0
        for k in kids:
            _roll(k)
            w = weight[k["node_id"]]
            tw += w
            tp += rollup[k["node_id"]] * w
        rollup[n["node_id"]] = round(tp / tw, 1) if tw else 0.0
        weight[n["node_id"]] = tw

    for root in children.get(None, []):
        _roll(root)

    today = date.today()
    enriched = []
    for n in nodes:
        sched = cpm["schedule"].get(n["node_id"], {})
        est_f = _parse_d(n.get("est_finish"))
        act_f = _parse_d(n.get("actual_finish"))
        delayed = bool(
            (est_f and n.get("status") != "done" and today > est_f)
            or (est_f and act_f and act_f > est_f))
        var_hours = round(float(n.get("actual_hours") or 0) - float(n.get("est_hours") or 0), 1)
        enriched.append({
            **n,
            "computed": {
                "rollup_progress": rollup.get(n["node_id"], float(n.get("progress_pct") or 0)),
                "delayed": delayed,
                "critical": sched.get("critical", False),
                "es": sched.get("es", 0), "ef": sched.get("ef", 1),
                "duration": sched.get("duration", 1), "slack": sched.get("slack", 0),
                "variance_hours": var_hours,
            },
        })

    root_prog = 0.0
    roots = children.get(None, [])
    if roots:
        tw = sum(weight.get(r["node_id"], 1.0) for r in roots)
        root_prog = round(sum(rollup.get(r["node_id"], 0) * weight.get(r["node_id"], 1.0) for r in roots) / tw, 1) if tw else 0

    reg_counts = {}
    for k in REGISTER_KINDS:
        reg_counts[k] = await db.gem_pm_registers.count_documents(
            {"goal_id": goal_id, "user_id": user["user_id"], "kind": k})

    return {
        "goal": goal,
        "nodes": enriched,
        "deps": deps,
        "critical_path": cpm["critical_path"],
        "project": {
            "anchor": cpm["anchor"],
            "duration_days": cpm["project_duration"],
            "progress": root_prog,
            "total_nodes": len(nodes),
            "delayed_count": sum(1 for n in enriched if n["computed"]["delayed"]),
        },
        "register_counts": reg_counts,
    }


# ═══════════════════════════ REGISTERS (Risks / Issues / Change Log) ═══════════════════════════

@router.get("/{goal_id}/registers")
async def list_registers(goal_id: str, request: Request, user: dict = Depends(get_current_user)):
    await _own_goal(goal_id, user)
    q: Dict[str, Any] = {"goal_id": goal_id, "user_id": user["user_id"]}
    kind = request.query_params.get("kind")
    if kind:
        q["kind"] = kind
    rows = await db.gem_pm_registers.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return rows


@router.post("/{goal_id}/registers")
async def create_register(goal_id: str, request: Request, user: dict = Depends(get_current_user)):
    await _own_goal(goal_id, user)
    body = await request.json()
    kind = (body.get("kind") or "").lower()
    if kind not in REGISTER_KINDS:
        raise HTTPException(400, f"kind must be one of {sorted(REGISTER_KINDS)}")
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title is required")
    doc = {
        "reg_id": str(uuid.uuid4()), "user_id": user["user_id"], "goal_id": goal_id,
        "kind": kind, "title": title,
        "description": body.get("description") or "",
        "owner": body.get("owner") or "",
        "status": body.get("status") or "open",       # open | mitigating | resolved | closed
        # risk-specific
        "probability": body.get("probability") or "", # low|medium|high
        "impact": body.get("impact") or "",           # low|medium|high
        "mitigation": body.get("mitigation") or "",
        # issue-specific
        "severity": body.get("severity") or "",       # low|medium|high|critical
        "resolution": body.get("resolution") or "",
        # change-specific
        "change_type": body.get("change_type") or "", # scope|budget|timeline|decision
        "decision": body.get("decision") or "",
        "created_at": _now(), "updated_at": _now(),
    }
    await db.gem_pm_registers.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/registers/{reg_id}")
async def update_register(reg_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    existing = await db.gem_pm_registers.find_one({"reg_id": reg_id, "user_id": user["user_id"]})
    if not existing:
        raise HTTPException(404, "register entry not found")
    allowed = ["title", "description", "owner", "status", "probability", "impact",
               "mitigation", "severity", "resolution", "change_type", "decision"]
    update = {k: body[k] for k in allowed if k in body}
    update["updated_at"] = _now()
    await db.gem_pm_registers.update_one({"reg_id": reg_id}, {"$set": update})
    return await db.gem_pm_registers.find_one({"reg_id": reg_id}, {"_id": 0})


@router.delete("/registers/{reg_id}")
async def delete_register(reg_id: str, user: dict = Depends(get_current_user)):
    r = await db.gem_pm_registers.delete_one({"reg_id": reg_id, "user_id": user["user_id"]})
    if r.deleted_count == 0:
        raise HTTPException(404, "register entry not found")
    return {"deleted": True}
