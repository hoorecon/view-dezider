"""Finder engine — the auto-filter + auto-assess + Top-N core behind DeciderApps.

Given a cloned MyDezider decision whose options carry actual values (prefilled
from the uploaded dataset), and whose factors carry the user's Step-2 expected
values / operators + Step-3 classification (primary=mandatory / secondary=
optional) + Step-4 priority (rating):

  1. FILTER options through a mandatory → optional funnel (see run_finder).
  2. ASSESS survivors deterministically (expected-vs-actual, operator-aware),
     rolling sub-factors up by weight and weighting factors by rating.
  3. Return the Top-N by Overall %.

Deterministic + O(options × factors) so it scales to very large option sets.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def _num(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(re.sub(r"[^\d.\-]", "", str(v)))
    except (TypeError, ValueError):
        return None


def _actual(option: Dict[str, Any], fid: str) -> Dict[str, Any]:
    for a in option.get("assessments") or []:
        if a.get("factor_id") == fid:
            return a
    return {}


def _actual_val(option: Dict[str, Any], fid: str) -> Any:
    # PRR shape: option.assessments[] carries {factor_id, unit_value,
    # actual_value, percentage} for each rated factor.
    a = _actual(option, fid)
    v = a.get("unit_value")
    if v in (None, ""):
        v = a.get("actual_value")
    if v in (None, "") and a.get("percentage") is not None:
        v = a.get("percentage")
    if v not in (None, ""):
        return v
    # DeciderApp / sheet-import shape: option.values{} maps
    #   sub_factor_id -> {num, raw, txt}   (see core/factor_group_import.py)
    # We fall back to this when no PRR assessment row exists, so the finder
    # engine can score sheet-imported options identically to hand-assessed
    # ones. Prefer `num` for arithmetic, then `raw`, then `txt`.
    vals = option.get("values") if isinstance(option.get("values"), dict) else None
    if vals:
        cell = vals.get(fid)
        if isinstance(cell, dict):
            for key in ("num", "raw", "txt"):
                cv = cell.get(key)
                if cv not in (None, ""):
                    return cv
        elif cell not in (None, ""):
            return cell
    return None


def _satisfies(actual_raw: Any, op: Any, expected_raw: Any, data_type: Any) -> bool:
    """Boolean filter match: does `actual op expected` hold? A blank expected
    means no constraint → True."""
    if expected_raw is None or str(expected_raw).strip() == "":
        return True
    op = str(op or "").strip().lower()
    text_ops = ("contains", "starts with", "ends with", "equals", "not equals")
    if data_type == "text" or op in text_ops:
        a = str(actual_raw or "").strip().lower()
        e = str(expected_raw).strip().lower()
        if op == "contains":
            return e in a
        if op == "starts with":
            return a.startswith(e)
        if op == "ends with":
            return a.endswith(e)
        if op == "not equals":
            return a != e
        return a == e or e in a  # equals / default
    a, e = _num(actual_raw), _num(expected_raw)
    if a is None or e is None:
        return str(expected_raw).strip().lower() in str(actual_raw or "").strip().lower()
    if op in (">=", "\u2265"):
        return a >= e
    if op in ("<=", "\u2264"):
        return a <= e
    if op == ">":
        return a > e
    if op == "<":
        return a < e
    if op in ("=", "=="):
        return abs(a - e) < 1e-9
    if op in ("\u2260", "!="):
        return abs(a - e) >= 1e-9
    return a >= e  # default higher-is-better


def _score(actual_raw: Any, op: Any, expected_raw: Any, data_type: Any) -> Optional[float]:
    """0-100 suitability of a leaf factor; None when not scorable."""
    a_num = _num(actual_raw)
    if expected_raw is None or str(expected_raw).strip() == "":
        # %-style actual doubles as its own suitability when no expectation set.
        return None if a_num is None else max(0.0, min(100.0, a_num))
    op = str(op or "").strip().lower()
    text_ops = ("contains", "starts with", "ends with", "equals", "not equals")
    if data_type == "text" or op in text_ops:
        return 100.0 if _satisfies(actual_raw, op, expected_raw, "text") else 0.0
    e_num = _num(expected_raw)
    if a_num is None or e_num is None:
        return 100.0 if _satisfies(actual_raw, op, expected_raw, data_type) else 0.0
    if op in ("<=", "\u2264", "<"):
        if a_num <= 0:
            return 100.0
        return 100.0 if a_num <= e_num else max(0.0, min(100.0, (e_num / a_num) * 100.0))
    if op in (">=", "\u2265", ">"):
        if e_num <= 0:
            return 100.0
        return 100.0 if a_num >= e_num else max(0.0, min(100.0, (a_num / e_num) * 100.0))
    if op in ("=", "=="):
        if abs(a_num - e_num) < 1e-9:
            return 100.0
        denom = max(abs(e_num), 1.0)
        return max(0.0, 100.0 - abs(a_num - e_num) / denom * 100.0)
    if op in ("\u2260", "!="):
        return 100.0 if abs(a_num - e_num) >= 1e-9 else 0.0
    return max(0.0, min(100.0, a_num))


def _children(factors: List[Dict[str, Any]], parent_id: str) -> List[Dict[str, Any]]:
    # Flat form: PRR stores sub-factors as top-level entries with parent_id set.
    kids = [f for f in factors if f.get("parent_id") == parent_id]
    if kids:
        return kids
    # Nested form: sheet-imported templates (see core/factor_group_import.py)
    # store sub-factors inside their parent's `sub_factors` list. Surface them
    # here so factor_pct / factor_matches work identically for both shapes.
    for f in factors:
        if f.get("id") == parent_id:
            subs = f.get("sub_factors") or []
            if isinstance(subs, list) and subs:
                return list(subs)
            break
    return []


def factor_pct(option: Dict[str, Any], factor: Dict[str, Any],
               factors: List[Dict[str, Any]]) -> Optional[float]:
    """Suitability % of a top-level factor (rolls sub-factors up by weight)."""
    kids = _children(factors, factor["id"])
    if kids:
        num = 0.0
        wsum = 0.0
        for k in kids:
            # Unticked choice values / dependent refiners (no expectation set)
            # must not self-score — only what the decider selected counts.
            if (str(k.get("role") or "") in ("value", "dependent")
                    and str(k.get("expected_value") if k.get("expected_value") is not None else "").strip() == ""):
                continue
            sc = _score(_actual_val(option, k["id"]), k.get("operator"),
                        k.get("expected_value"), k.get("data_type"))
            if sc is None:
                continue
            w = float(k.get("weight") or 0) or 1.0
            num += w * sc
            wsum += w
        return round(num / wsum, 2) if wsum > 0 else None
    return _score(_actual_val(option, factor["id"]), factor.get("operator"),
                  factor.get("expected_value"), factor.get("data_type"))


def option_worth(option: Dict[str, Any], factors: List[Dict[str, Any]]) -> float:
    """Rating-weighted Overall %. Falls back to equal weighting when no factor
    has a rating yet (e.g. user skipped prioritisation)."""
    tops = [f for f in factors if not f.get("parent_id")]
    has_rating = any(int(f.get("rating") or 0) > 0 for f in tops)
    num = 0.0
    den = 0.0
    for f in tops:
        r = int(f.get("rating") or 0) if has_rating else 1
        if r <= 0:
            continue
        pct = factor_pct(option, f, factors)
        if pct is None:
            continue
        num += r * pct
        den += r * 100.0
    return round(num / den * 100.0, 2) if den > 0 else 0.0


def _has_expectation(factor: Dict[str, Any], factors: List[Dict[str, Any]]) -> bool:
    leaves = _children(factors, factor["id"]) or [factor]
    return any(str((lf.get("expected_value") or "")).strip() != "" for lf in leaves)


def factor_matches(option: Dict[str, Any], factor: Dict[str, Any],
                   factors: List[Dict[str, Any]], match_rule: str) -> bool:
    leaves = _children(factors, factor["id"]) or [factor]
    checks = []
    for lf in leaves:
        exp = lf.get("expected_value")
        if exp is None or str(exp).strip() == "":
            continue
        checks.append(_satisfies(_actual_val(option, lf["id"]), lf.get("operator"),
                                 exp, lf.get("data_type")))
    if not checks:
        return True
    # Multi-select widgets (checkbox/listbox) match ANY ticked value.
    rule = "any" if str(factor.get("ui_object") or "") in ("checkbox", "listbox") else match_rule
    return all(checks) if rule == "all" else any(checks)


def _filter(options: List[Dict[str, Any]], factors: List[Dict[str, Any]],
            cat: str, match_rule: str) -> List[Dict[str, Any]]:
    fs = [f for f in factors if not f.get("parent_id") and f.get("category") == cat
          and _has_expectation(f, factors)]
    if not fs:
        return list(options)
    return [o for o in options if all(factor_matches(o, f, factors, match_rule) for f in fs)]


def run_finder(decision: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    factors = decision.get("factors") or []
    options = decision.get("options") or []
    match_rule = cfg.get("match_rule") or "all"
    mn = int(cfg.get("min_options") or 3)
    mx = int(cfg.get("max_options") or 15)
    top_n = int(cfg.get("top_n") or 5)

    # ── Funnel ─────────────────────────────────────────────
    m_set = _filter(options, factors, "primary", match_rule)   # mandatory
    if len(m_set) >= mn:
        survivors, stage = m_set, "mandatory"
        if len(m_set) > mx:
            mo = _filter(m_set, factors, "secondary", match_rule)  # + optional
            if len(mo) >= mn:
                survivors, stage = mo, "mandatory+optional"
    else:
        survivors, stage = list(options), "relaxed_all"  # too few → widen

    # ── Assess + rank ──────────────────────────────────────
    ranked = [{"option_id": o["id"], "name": o.get("name"),
               "worth_percentage": option_worth(o, factors)} for o in survivors]
    ranked.sort(key=lambda r: r["worth_percentage"], reverse=True)
    top = ranked[:top_n]
    return {
        "stage": stage,
        "total_options": len(options),
        "mandatory_matches": len(m_set),
        "survivors": len(survivors),
        "ranked": ranked,
        "top": top,
        "top_ids": [r["option_id"] for r in top],
        "top_n": top_n,
        "match_rule": match_rule,
        "min_options": mn,
        "max_options": mx,
    }
