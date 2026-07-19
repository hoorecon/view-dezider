"""Option-Bank Finder — FRAME at 10-million-option scale.

Search-engine-shaped pipeline (candidate generation → light ranking → exact
re-rank), the same 3-tier architecture Google/Amazon retrieval uses:

  S0  OPTION BANK    — `decider_option_bank`: one doc per option per template,
                       values PRE-NORMALIZED AT INGEST (`vals.<sub_id>.num` /
                       `.txt`), wildcard-indexed. Never parse at query time.
  S1  PRE-FILTER     — mandatory (Step-3 "primary") expectations compile into
                       a native Mongo query executed on indexes INSIDE the DB
                       engine: 10M → 10⁴-10⁵ candidates before Python sees a
                       single row. Adaptive funnel: too few → relax; too many
                       → tighten with optional factors.
  S2  STREAM + HEAP  — Motor cursor (projection = only needed value paths),
                       batches, deterministic FRAME scorer in a tight loop,
                       `heapq` keeps ONLY the Top-K → O(N log K) time,
                       O(K) memory. Progress % surfaced per batch.
  S3  EXACT RE-RANK  — quality gate + AdMaker auction on the survivors
                       (unchanged FRAME stages 3-6; organic stays sacred).

Runs as an async `finder_jobs` background task (same contract as
`deep_import_jobs`): {status, progress{pct,label}, result}. The frontend polls
and plays the 'finder' loader-music slot. Repeat runs with the same
expectations hit a spec-hash cache.
"""
from __future__ import annotations

import hashlib
import heapq
import json
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core import ad_auction
from core.database import db
from core.finder_engine import _num, _satisfies, _score

BANK = "decider_option_bank"
BATCH = 5000
HEAP_K_MIN = 50
RANKED_CAP = 50          # ranked rows returned to the client
TEXT_OPS = ("contains", "starts with", "ends with", "equals")


def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════ leaf-spec mapping (decision → bank keys) ═══════════════
def build_leaf_specs(decision: Dict[str, Any], template: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Map the user's cloned factors onto the bank's value keys (template
    sub-factor ids). Prefers the persisted `source_sub_id`; falls back to
    normalized-name matching for pre-existing clones.

    Returns top-factor specs:
      [{rating, category, leaves: [{sid, operator, expected, data_type, weight}]}]
    """
    name_to_sid: Dict[str, str] = {}
    for f in template.get("factors") or []:
        subs = f.get("sub_factors") or [{"id": f.get("id"), "name": f.get("name")}]
        for sf in subs:
            name_to_sid.setdefault(_norm(sf.get("name")), sf.get("id"))
        name_to_sid.setdefault(_norm(f.get("name")), subs[0].get("id"))

    factors = decision.get("factors") or []
    kids: Dict[str, List[Dict[str, Any]]] = {}
    for f in factors:
        if f.get("parent_id"):
            kids.setdefault(f["parent_id"], []).append(f)

    specs: List[Dict[str, Any]] = []
    multi_ui = ("checkbox", "listbox")
    for top in factors:
        if top.get("parent_id"):
            continue
        leaves_raw = kids.get(top["id"]) or [top]
        leaves = []
        for lf in leaves_raw:
            sid = lf.get("source_sub_id") or name_to_sid.get(_norm(lf.get("name")))
            if not sid:
                continue
            # Choice values (role='value') only participate when SELECTED —
            # i.e. when the decider gave them an expectation. Unticked values
            # must not filter NOR score (their raw suitability is irrelevant).
            role = str(lf.get("role") or "")
            has_exp = str(lf.get("expected_value") if lf.get("expected_value") is not None else "").strip() != ""
            if role in ("value", "dependent") and not has_exp:
                continue
            leaves.append({
                "sid": sid,
                "operator": lf.get("operator"),
                "expected": lf.get("expected_value"),
                "data_type": lf.get("data_type"),
                "weight": float(lf.get("weight") or 0) or 1.0,
            })
        if leaves:
            specs.append({
                "rating": int(top.get("rating") or 0),
                "category": top.get("category") or "",
                # Multi-select widgets match ANY ticked value regardless of
                # the template-level match rule.
                "match": ("any" if str(top.get("ui_object") or "") in multi_ui else None),
                "leaves": leaves,
            })
    return specs


def spec_hash(specs: List[Dict[str, Any]], cfg: Dict[str, Any]) -> str:
    payload = json.dumps({"s": specs, "c": {k: cfg.get(k) for k in
                          ("min_options", "max_options", "top_n", "match_rule")}},
                         sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


# ═══════════════════ S1 — indexed pre-filter compilation ═══════════════════
def _leaf_clause(leaf: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Compile ONE leaf expectation into a Mongo clause, or None when it can
    only be checked in Python (residual)."""
    exp = leaf.get("expected")
    if exp is None or str(exp).strip() == "":
        return None
    op = str(leaf.get("operator") or "").strip().lower()
    base = f"vals.{leaf['sid']}"
    if leaf.get("data_type") == "text" or op in TEXT_OPS:
        e = re.escape(str(exp).strip())
        if op == "starts with":
            rx = f"^{e}"
        elif op == "ends with":
            rx = f"{e}$"
        elif op == "equals":
            rx = f"^{e}$"
        else:  # contains / default text
            rx = e
        return {f"{base}.txt": {"$regex": rx, "$options": "i"}}
    e_num = _num(exp)
    if e_num is None:
        return None
    if op in (">=", "\u2265"):
        return {f"{base}.num": {"$gte": e_num}}
    if op in ("<=", "\u2264"):
        return {f"{base}.num": {"$lte": e_num}}
    if op == ">":
        return {f"{base}.num": {"$gt": e_num}}
    if op == "<":
        return {f"{base}.num": {"$lt": e_num}}
    if op in ("=", "=="):
        return {f"{base}.num": e_num}
    if op in ("\u2260", "!="):
        return {f"{base}.num": {"$ne": e_num}}
    return {f"{base}.num": {"$gte": e_num}}  # default higher-is-better


def compile_prefilter(specs: List[Dict[str, Any]], categories: Tuple[str, ...],
                      match_rule: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """→ (mongo_clauses, residual_leaf_checks). One clause per constrained
    factor; leaves combine with $and (match ALL) or $or (match ANY)."""
    clauses: List[Dict[str, Any]] = []
    residual: List[Dict[str, Any]] = []
    for spec in specs:
        if spec["category"] not in categories:
            continue
        # per-factor override (multi-select widgets are always ANY)
        f_rule = spec.get("match") or match_rule
        leaf_clauses, leaf_residual = [], []
        for leaf in spec["leaves"]:
            exp = leaf.get("expected")
            if exp is None or str(exp).strip() == "":
                continue
            c = _leaf_clause(leaf)
            if c is not None:
                leaf_clauses.append(c)
            else:
                leaf_residual.append(leaf)
        if f_rule == "any" and (leaf_clauses or leaf_residual):
            if leaf_residual:
                # ANY with a non-compilable leaf → the whole factor must be
                # checked in Python (a DB $or would wrongly exclude rows).
                residual.append({"match": "any",
                                 "leaves": [lf for lf in spec["leaves"]
                                            if str(lf.get("expected") or "").strip() != ""]})
            elif len(leaf_clauses) == 1:
                clauses.append(leaf_clauses[0])
            else:
                clauses.append({"$or": leaf_clauses})
        else:  # match ALL
            clauses.extend(leaf_clauses)
            for lf in leaf_residual:
                residual.append({"match": "all", "leaves": [lf]})
    return clauses, residual


def _residual_ok(vals: Dict[str, Any], checks: List[Dict[str, Any]]) -> bool:
    for chk in checks:
        results = []
        for lf in chk["leaves"]:
            v = vals.get(lf["sid"]) or {}
            actual = v.get("num") if v.get("num") is not None else v.get("txt")
            results.append(_satisfies(actual, lf.get("operator"), lf.get("expected"),
                                      lf.get("data_type")))
        if not results:
            continue
        ok = any(results) if chk["match"] == "any" else all(results)
        if not ok:
            return False
    return True


# ═══════════════════ S2 — streamed scoring (pure per option) ═══════════════
def score_vals(vals: Dict[str, Any], specs: List[Dict[str, Any]], has_rating: bool) -> float:
    """FRAME quality score for one bank option: leaf → factor (Split %
    weights) → Overall % (priority-rating weights). Mirrors
    finder_engine.option_worth exactly."""
    num = den = 0.0
    for spec in specs:
        r = spec["rating"] if has_rating else 1
        if r <= 0:
            continue
        f_num = f_wsum = 0.0
        for leaf in spec["leaves"]:
            v = vals.get(leaf["sid"]) or {}
            actual = v.get("num") if v.get("num") is not None else v.get("txt")
            sc = _score(actual, leaf.get("operator"), leaf.get("expected"), leaf.get("data_type"))
            if sc is None:
                continue
            f_num += leaf["weight"] * sc
            f_wsum += leaf["weight"]
        if f_wsum <= 0:
            continue
        pct = f_num / f_wsum
        num += r * pct
        den += r * 100.0
    return round(num / den * 100.0, 2) if den > 0 else 0.0


# ═══════════════════ the async pipeline (background task) ═══════════════════
async def _set_job(job_id: str, **fields):
    fields["updated_at"] = _now()
    await db.finder_jobs.update_one({"id": job_id}, {"$set": fields})


async def _prog(job_id: str, pct: int, label: str):
    await _set_job(job_id, progress={"pct": pct, "label": label})


async def run_bank_job(job_id: str, decision: Dict[str, Any], template: Dict[str, Any],
                       cfg: Dict[str, Any], user: Dict[str, Any], region: str):
    t0 = time.monotonic()
    try:
        tid = template["template_id"]
        specs = build_leaf_specs(decision, template)
        has_rating = any(s["rating"] > 0 for s in specs)
        match_rule = cfg.get("match_rule") or "all"
        mn, mx = int(cfg.get("min_options") or 3), int(cfg.get("max_options") or 15)
        top_n = int(cfg.get("top_n") or 5)

        base_q = {"template_id": tid}
        total = await db[BANK].count_documents(base_q)
        await _prog(job_id, 3, f"Indexing {total:,} options…")

        # S1 — mandatory pre-filter (indexed, inside the DB engine)
        m_clauses, m_residual = compile_prefilter(specs, ("primary",), match_rule)
        cand_q = {**base_q, **({"$and": m_clauses} if m_clauses else {})}
        candidates = await db[BANK].count_documents(cand_q)
        stage, residual = "mandatory", m_residual
        if candidates < mn:                       # too few → relax to ALL
            cand_q, candidates, stage, residual = base_q, total, "relaxed_all", []
        elif candidates > mx:                     # too many → tighten w/ optional
            mo_clauses, mo_residual = compile_prefilter(specs, ("primary", "secondary"), match_rule)
            if len(mo_clauses) > len(m_clauses) or len(mo_residual) > len(m_residual):
                q2 = {**base_q, **({"$and": mo_clauses} if mo_clauses else {})}
                c2 = await db[BANK].count_documents(q2)
                if c2 >= mn:
                    cand_q, candidates, stage, residual = q2, c2, "mandatory+optional", mo_residual
        await _prog(job_id, 8, f"Filtered {total:,} → {candidates:,} candidates. Scoring…")

        # S2 — stream + heap Top-K
        need_sids = {lf["sid"] for s in specs for lf in s["leaves"]}
        projection = {"_id": 0, "bank_id": 1, "name": 1,
                      **{f"vals.{sid}": 1 for sid in need_sids}}
        K = max(HEAP_K_MIN, top_n)
        heap: List[Tuple[float, str, str]] = []   # (worth, bank_id, name)
        scanned = matched = 0
        cursor = db[BANK].find(cand_q, projection).batch_size(BATCH)
        async for doc in cursor:
            scanned += 1
            if scanned % 1000 == 0:
                await __import__("asyncio").sleep(0)  # keep the event loop fair
            vals = doc.get("vals") or {}
            if residual and not _residual_ok(vals, residual):
                continue
            matched += 1
            worth = score_vals(vals, specs, has_rating)
            entry = (worth, doc.get("bank_id") or "", doc.get("name") or "")
            if len(heap) < K:
                heapq.heappush(heap, entry)
            elif entry > heap[0]:
                heapq.heapreplace(heap, entry)
            if scanned % BATCH == 0:
                pct = 8 + int(84 * scanned / max(1, candidates))
                await _prog(job_id, min(92, pct),
                            f"Scored {scanned:,} / {candidates:,} options…")

        ranked = [{"option_id": b, "name": n, "worth_percentage": w}
                  for (w, b, n) in sorted(heap, reverse=True)]
        top = ranked[:top_n]
        await _prog(job_id, 94, "Running the Sponsored auction…")

        # S3 — quality gate + AdMaker auction. Bid-targeted options are scored
        # even when outside the Top-K heap (they still must clear the cutoff).
        ad_cfg = await ad_auction.resolve_ad_config(template)
        auction_pool = {r["option_id"]: r for r in ranked}
        bids = await db.admaker_bids.find(
            {"template_id": tid, "status": "active"}, {"_id": 0, "option_name": 1}).to_list(500)
        for b in bids:
            nn = _norm(b.get("option_name"))
            if any(_norm(r["name"]) == nn for r in auction_pool.values()):
                continue
            doc = await db[BANK].find_one({"template_id": tid, "name_norm": nn}, projection)
            if doc:
                vals = doc.get("vals") or {}
                if residual and not _residual_ok(vals, residual):
                    continue
                auction_pool[doc["bank_id"]] = {
                    "option_id": doc["bank_id"], "name": doc.get("name"),
                    "worth_percentage": score_vals(vals, specs, has_rating)}
        sponsored = await ad_auction.run_auction(
            template_id=tid, ranked=list(auction_pool.values()), region=region,
            sponsored_n=ad_cfg["sponsored_n"], min_cutoff_pct=ad_cfg["min_cutoff_pct"])
        if sponsored:
            await ad_auction.record_impressions(sponsored, tid, decision["id"],
                                                region, user["user_id"])

        duration_ms = int((time.monotonic() - t0) * 1000)
        result = {
            "engine": "bank", "stage": stage,
            "total_options": total, "candidates": candidates,
            "survivors": matched, "scanned": scanned,
            "ranked": ranked[:RANKED_CAP], "top": top,
            "top_ids": [r["option_id"] for r in top], "top_n": top_n,
            "match_rule": match_rule, "min_options": mn, "max_options": mx,
            "sponsored": [{k: w[k] for k in
                           ("option_id", "name", "worth_percentage", "slot",
                            "advertiser_name", "bid_id")} for w in sponsored],
            "ad_config": {"min_cutoff_pct": ad_cfg["min_cutoff_pct"],
                          "sponsored_n": ad_cfg["sponsored_n"], "region": region},
            "duration_ms": duration_ms,
        }
        await _set_job(job_id, status="done", result=result,
                       progress={"pct": 100, "label": f"Done in {duration_ms/1000:.1f}s."})
        await db.decisions.update_one(
            {"id": decision["id"]},
            {"$set": {"finder_last_run": _now(), "finder_bank_mode": True,
                      "finder_result_ids": result["top_ids"],
                      "finder_sponsored_ids": [w["option_id"] for w in sponsored],
                      "finder_config_used": cfg}})
    except Exception as e:  # surface — never leave a job spinning
        await _set_job(job_id, status="error", error=str(e)[:300],
                       progress={"pct": 100, "label": "Failed."})


# ═══════════════════ ingestion (shared by all 3 sources) ═══════════════════
async def bank_upsert(template: Dict[str, Any], items: List[Dict[str, Any]],
                      source: str) -> Dict[str, int]:
    """Idempotent upsert keyed by (template_id, name_norm).
    item = {name, description?, source_ref?, values: {sub_id: raw | {raw,num}}}
    Values are normalized ONCE here (S0: pay parse cost at ingest)."""
    tid = template["template_id"]
    inserted = updated = skipped = 0
    ops = []
    from pymongo import UpdateOne
    for it in items:
        name = str(it.get("name") or "").strip()
        if not name:
            skipped += 1
            continue
        vals: Dict[str, Any] = {}
        for sid, v in (it.get("values") or {}).items():
            if isinstance(v, dict):
                raw = str(v.get("raw", "")).strip()
                n = v.get("num")
                n = float(n) if n is not None else _num(raw)
            else:
                raw = str(v if v is not None else "").strip()
                n = _num(raw)
            if raw or n is not None:
                vals[str(sid)] = {"num": n, "txt": raw}
        ops.append(UpdateOne(
            {"template_id": tid, "name_norm": _norm(name)},
            {"$set": {"name": name, "vals": vals, "source": source,
                      "source_ref": it.get("source_ref"),
                      "description": (it.get("description") or "")[:500],
                      "updated_at": _now()},
             "$setOnInsert": {"bank_id": str(uuid.uuid4()), "template_id": tid,
                              "name_norm": _norm(name), "created_at": _now()}},
            upsert=True))
        if len(ops) >= 2000:
            res = await db[BANK].bulk_write(ops, ordered=False)
            inserted += res.upserted_count
            updated += res.modified_count
            ops = []
    if ops:
        res = await db[BANK].bulk_write(ops, ordered=False)
        inserted += res.upserted_count
        updated += res.modified_count
    return {"inserted": inserted, "updated": updated, "skipped": skipped}
