"""Deterministic page-grounding verification for URL imports.

Contract: every NUMERIC value an import writes into a decision must be
traceable to an explicit number in the fetched page text (unit conversions
allowed — "Rs. 5.84 Lakh" → 584000, "5.84 - 9.99 Lakh" ranges expand both
endpoints). Values that cannot be traced are BLANKED (never silently kept)
and reported to the user. Text values are flagged but kept (categorical
specs may legitimately come from the LLM's general knowledge per the
extraction prompt's rule 7).

Also produces a PROVENANCE list: the exact source line for every verified
value ("Rs. 5.84 - 9.99 Lakh · Avg. Ex-Showroom price"), which makes page
variants (ex-showroom vs on-road pricing, geo-personalised views) self-
explanatory to the user.

Pure functions — no I/O, never raises.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_MULT = {
    "lakh": 100_000.0, "lakhs": 100_000.0, "lac": 100_000.0, "lacs": 100_000.0,
    "crore": 10_000_000.0, "crores": 10_000_000.0, "cr": 10_000_000.0,
    "million": 1_000_000.0, "mn": 1_000_000.0,
    "billion": 1_000_000_000.0, "bn": 1_000_000_000.0,
    "thousand": 1_000.0,
}
_MULT_PAT = r"lakhs?|lacs?|crores?|cr|million|mn|billion|bn|thousand"

_NUM = r"\d[\d,]*(?:\.\d+)?"
_RANGE_MULT_RE = re.compile(rf"({_NUM})\s*[-–—~]\s*({_NUM})\s*({_MULT_PAT})\b", re.I)
_NUM_MULT_RE = re.compile(rf"({_NUM})\s*({_MULT_PAT})\b", re.I)
_NUM_RE = re.compile(_NUM)
_CURRENCY_RE = re.compile(r"₹|\bRs\.?\s?\d|\bINR\b|\bUSD\b|\$\s?\d|€|£|¥", re.I)

# Factor names that strongly imply money values. Used to set `has_currency`
# only when the imported decision actually deals with prices — so we don't
# pop the "prices may differ in your city" alert on non-monetary imports
# (gadget spec comparisons, ratings, capacity tables, etc.). Substring match,
# case-insensitive.
_MONEY_FACTOR_HINTS = (
    "price", "cost", "fee", "rent", "salary", "budget", "amount",
    "premium", "emi", "deposit", "tuition", "fare", "wage", "income",
    "expense", "charge", "tariff", "subscription", "interest rate",
    "downpayment", "down payment",
)

MAX_EVIDENCE = 80
QUOTE_LEN = 140


def _f(tok: str) -> Optional[float]:
    try:
        return float(str(tok).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _squash(s: str) -> str:
    return " ".join(str(s or "").lower().split())


def _keys(v: float) -> List[float]:
    """Match keys for one float value — exact + rounding tolerance."""
    out = [round(v, 2)]
    if abs(v - round(v)) < 0.005:
        out.append(float(round(v)))
    return out


def build_value_index(page_text: str) -> Dict[float, str]:
    """All numbers stated on the page (raw + Lakh/Crore-multiplied, range
    endpoints expanded) → the source line they appear on."""
    idx: Dict[float, str] = {}

    def _put(v: Optional[float], snippet: str):
        if v is None:
            return
        for k in _keys(v):
            idx.setdefault(k, snippet)

    for raw_line in (page_text or "").splitlines():
        ln = " ".join(raw_line.split())
        if not ln or not any(c.isdigit() for c in ln):
            continue
        snippet = ln[:QUOTE_LEN]
        for m in _RANGE_MULT_RE.finditer(ln):
            mult = _MULT[m.group(3).lower()]
            for g in (1, 2):
                v = _f(m.group(g))
                _put(v * mult if v is not None else None, snippet)
        for m in _NUM_MULT_RE.finditer(ln):
            v = _f(m.group(1))
            _put(v * _MULT[m.group(2).lower()] if v is not None else None, snippet)
        for m in _NUM_RE.finditer(ln):
            _put(_f(m.group(0)), snippet)
    return idx


def _match_number(value: str, idx: Dict[float, str]) -> Optional[str]:
    v = _f(re.sub(r"[^\d.,\-]", "", str(value)))
    if v is None:
        return None
    for k in _keys(v):
        if k in idx:
            return idx[k]
    return None


def _find_text_line(value: str, lines: List[str]) -> Optional[str]:
    sq = _squash(value)
    if len(sq) < 2:
        return None
    for ln in lines:
        if sq in _squash(ln):
            return " ".join(ln.split())[:QUOTE_LEN]
    return None


def verify_detail(detail: Dict[str, Any], page_text: str) -> Dict[str, Any]:
    """Verify (and mutate) a normalised extraction result (kind=flat|hier)
    against the page text. Blanks unverified NUMERIC values + their scores
    and expected values; flags unverified text values (kept).

    Returns {verified, blanked, flagged_text, unverified: [str],
             evidence: [{factor, option, value, quote}], has_currency}.

    `has_currency` is True ONLY when the IMPORT itself deals with money —
    either a factor name implies money ("price", "rent", "fee", …) OR an
    imported cell value contains a currency symbol. We deliberately do NOT
    just check the page text, because comparison pages often have unrelated
    money mentions (EMI calculators, ads, footer) that would falsely fire
    the "prices may differ in your city" alert on non-monetary imports
    (e.g. property pages, gadget spec tables, education comparisons).
    """
    summary = {"verified": 0, "blanked": 0, "flagged_text": 0,
               "unverified": [], "evidence": [], "has_currency": False}

    def _is_money_factor(name: str) -> bool:
        n = (name or "").lower()
        return any(h in n for h in _MONEY_FACTOR_HINTS)

    def _value_has_currency(value: str) -> bool:
        return bool(_CURRENCY_RE.search(str(value or "")))

    try:
        idx = build_value_index(page_text)
        lines = [ln for ln in (page_text or "").splitlines() if ln.strip()]
        # Track whether ANY imported cell looks like money. Page-wide check
        # is now only a fallback signal — see final assignment below.
        imported_has_money = False

        def _evidence(factor: str, option: str, value: str, quote: str):
            summary["verified"] += 1
            if len(summary["evidence"]) < MAX_EVIDENCE:
                summary["evidence"].append({"factor": factor[:80], "option": option[:80],
                                            "value": str(value)[:60], "quote": quote})

        def _blank(factor: str, option: str, value: str):
            summary["blanked"] += 1
            if len(summary["unverified"]) < 25:
                summary["unverified"].append(f"{factor} — {option}: {value}")

        if detail.get("kind") == "flat":
            numeric = {f["name"] for f in detail["factors"] if f.get("data_type") == "numeric"}
            for cand in detail["candidates"]:
                uvals = cand.get("unit_values") or {}
                for fname in list(uvals.keys()):
                    val = str(uvals[fname]).strip()
                    if not val:
                        continue
                    # Detect money INSIDE the imported cells — either the
                    # factor name implies money OR the value carries a
                    # currency symbol.
                    if not imported_has_money and (_is_money_factor(fname) or _value_has_currency(val)):
                        imported_has_money = True
                    if fname in numeric:
                        q = _match_number(val, idx)
                        if q:
                            _evidence(fname, cand["name"], val, q)
                        else:
                            _blank(fname, cand["name"], val)
                            uvals.pop(fname, None)
                            (cand.get("scores") or {}).pop(fname, None)
                    else:
                        q = _find_text_line(val, lines)
                        if q:
                            _evidence(fname, cand["name"], val, q)
                        else:
                            summary["flagged_text"] += 1
            for f in detail["factors"]:
                ev = f.get("expected_value")
                if f.get("data_type") == "numeric" and ev not in (None, "") \
                        and not _match_number(str(ev), idx):
                    f["expected_value"] = None

        elif detail.get("kind") == "hier":
            items = detail.get("items") or []
            for gi, g in enumerate(detail.get("groups") or []):
                for ri, row in enumerate(g.get("rows") or []):
                    meta = (detail.get("row_meta") or {}).get((gi, ri)) or {}
                    is_num = bool(meta.get("is_numeric"))
                    vals = row.get("values") or []
                    if not imported_has_money and _is_money_factor(row.get("label") or ""):
                        imported_has_money = True
                    for ii, val in enumerate(vals):
                        val = str(val or "").strip()
                        if not val:
                            continue
                        if not imported_has_money and _value_has_currency(val):
                            imported_has_money = True
                        opt = items[ii] if ii < len(items) else f"option {ii + 1}"
                        if is_num:
                            q = _match_number(val, idx)
                            if q:
                                _evidence(row["label"], opt, val, q)
                            else:
                                _blank(row["label"], opt, val)
                                vals[ii] = ""
                                scores = (detail.get("row_scores") or {}).get((gi, ri))
                                if scores and ii < len(scores):
                                    scores[ii] = None
                        else:
                            q = _find_text_line(val, lines)
                            if q:
                                _evidence(row["label"], opt, val, q)
                            else:
                                summary["flagged_text"] += 1
                    if is_num and meta.get("expected") not in (None, "") \
                            and not _match_number(str(meta["expected"]), idx):
                        meta["expected"] = None
        # Final assignment: only fire the "prices may differ" alert when
        # the import itself is money-bearing. Page-wide currency mentions
        # alone are NOT sufficient (too many false positives on property,
        # gadget-spec and education comparison pages).
        summary["has_currency"] = bool(imported_has_money)
    except Exception:  # noqa: BLE001 — verification must never break an import
        pass
    return summary
