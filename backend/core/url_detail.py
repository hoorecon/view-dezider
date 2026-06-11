"""Single-item DETAIL-page import — the "intelligent" Import-from-URL path.

When a pasted URL is a single listing/product/detail page (NOT a comparison
table), ONE metered LLM call turns the page into a decision-ready structure:

  • every concrete attribute of the main item becomes a FACTOR with a smart
    operator (Rent ≤ 18,000 · Area ≥ 650 sqft · Furnishing = Semi …) and the
    item's own value as the suggested Expected value,
  • the main item becomes Option 1 (it satisfies its own expectations → 100%),
  • "Similar / Related items" sections become extra options with whatever
    partial values + relative scores are visible on the page.

Site-agnostic: property listings, e-commerce products, vehicles, jobs,
courses — anything with a spec sheet and (optionally) a related-items rail.

Tiers: "fast" (default) routes through the free-first Gemini chain;
"precise" routes through Claude (admin-configured `precise_model`) via the
Emergent universal key at the configured credit multiplier.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from core import ai_wallet
from core.ai_metering import has_any_llm, metered_chat
from core.url_crawl import page_text

logger = logging.getLogger(__name__)

_NUMERIC_OPS = {"<=", ">=", "=", "<", ">", "!="}
_TEXT_OPS = {"contains", "starts_with", "ends_with", "equals", "not_equals"}

# Keys inside embedded SPA-state JSON that hold "similar / related items" data
# (e.g. NoBroker's similarPropertiesInfo, generic relatedProducts, recommendations).
_RELATED_KEY_RE = re.compile(
    r'"([a-zA-Z0-9_]*(?:similar|related|recommend)[a-zA-Z0-9_]*)"\s*:', re.I)


def _embedded_related_snippets(html: str, max_snippets: int = 2,
                               max_chars: int = 10000) -> str:
    """Mine the raw HTML's inline-script JSON state for similar/related-items
    blocks. Many listing sites server-embed the 'Similar items' rail data but
    only render it with JavaScript — so it is invisible to plain text
    extraction. Heavy media sub-objects are stripped to keep signal density."""
    out: list = []
    for m in _RELATED_KEY_RE.finditer(html or ""):
        tail = html[m.end(): m.end() + 30]
        # Skip empty / scalar values ([], {}, null, "", numbers, booleans).
        if re.match(r'\s*(\[\s*\]|\{\s*\}|null|""|true|false|-?\d)', tail):
            continue
        window = html[m.start(): m.start() + 80000]
        window = re.sub(r'"photos"\s*:\s*\[.*?\]', '"photos":[]', window, flags=re.S)
        window = re.sub(r'"imagesMap"\s*:\s*\{[^{}]*\}', '{}', window)
        window = re.sub(r'"[a-zA-Z]*[Dd]escription"\s*:\s*"[^"]*"', '"description":""', window)
        window = re.sub(r'"[a-f0-9]{24,}[^"]*"', '""', window)  # long ids / image hashes
        window = re.sub(r'"(?:https?:|//|/)[^"]*"', '""', window)  # urls / paths
        window = re.sub(r'"[^"]{200,}"', '""', window)             # any other huge blob
        # Drop now-empty fields so each item compresses to its real signal.
        for _ in range(2):
            window = re.sub(r'"[a-zA-Z0-9_]+"\s*:\s*(?:""|null|\[\]|\{\}|false)\s*,?', '', window)
        out.append(window[:max_chars])
        if len(out) >= max_snippets:
            break
    return "\n".join(out)


def _squash(name: str) -> str:
    """Whitespace-insensitive dedupe key."""
    return " ".join(str(name or "").lower().split())

DETAIL_SYSTEM = """You convert ONE web page into a decision-comparison structure. The page shows a single MAIN item in detail (property listing, product, vehicle, job, course, service, …) and may show a "Similar/Related items" rail.

Reply ONLY compact JSON (no prose, no markdown fences):
{"page_type":"detail",
 "main_item":{"name":"<full display title of the main item>"},
 "factors":[{"name":str,"data_type":"numeric"|"text","operator":"<="|">="|"="|"equals","expected_value":str,"unit":str|null}],
 "items":[{"name":str,"values":{"<factor name>":str|null},"scores":{"<factor name>":0-100|null}}]}

RULES
1. FACTORS — extract EVERY concrete attribute/spec of the MAIN item shown on the page: prices, rents, fees, deposits, maintenance, sizes, counts, scores, ratings, dates, categories, yes/no flags, address/locality. EXCLUDE site navigation, ads, service promos, marketing prose, breadcrumbs, nearby-locality link lists.
2. data_type "numeric" ONLY when the value is one measurable number (650, 18000, 6.2). Composite values like "0/4", "2 BHK", dates, yes/no → "text".
3. operator expresses what a decision-maker would WANT versus this item's value:
   • "<=" for lower-is-better numerics (rent, price, deposit, fees, maintenance, distance, commute)
   • ">=" for higher-is-better numerics (area, livability/transit scores, ratings, capacity, warranty)
   • "=" for numeric identity values (bedroom count, bathroom count)
   • "equals" for ALL text factors (type, furnishing, facing, tenant, possession, yes/no, NA, locality)
4. expected_value = the MAIN item's own value, cleaned: plain numbers for numerics (no currency symbols or thousands separators), concise text otherwise. Keep "NA" when the page shows NA. Put units (sqft, INR, years, km) in "unit".
5. main_item.name = the listing's own DISPLAY HEADING on the page (e.g. "2 BHK Flat In Metro Flats for Rent In Kodambakkam"), NOT the SEO <title> tag.
6. ITEMS — FIRST item MUST be the main item with every factor value filled and every score 100. THEN every DIFFERENT similar/related item (sections like "Similar Properties", "Related products", "You may also like", plus any EMBEDDED RELATED-ITEMS DATA appended after the page text): its name plus whatever factor values are known (rent/price, area, locality, …). NEVER repeat the main item as a similar item. Score each KNOWN value 0-100 for how well it satisfies expected_value+operator (better than expected → 100; ~10% worse → ≈80). Unknown values → null in BOTH maps.
7. Keys inside "values" and "scores" MUST exactly match the factor names.
8. Max {max_factors} factors, max 12 items. If the page actually compares MULTIPLE items (a comparison/filter/listing page with no single main item), reply exactly {"page_type":"comparison"}."""


def _parse_json_obj(out: str) -> Optional[Dict[str, Any]]:
    m = re.search(r"\{.*\}", out or "", re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _pct(v: Any) -> Optional[int]:
    try:
        return max(0, min(100, int(round(float(v)))))
    except (TypeError, ValueError):
        return None


def normalize_detail(data: Any, max_factors: int = 24) -> Optional[Dict[str, Any]]:
    """Validate + normalise the LLM's detail JSON into the shapes expected by
    `merge_into_mydezider` / `create_mydezider_from_candidates`:

        {"main_name": str,
         "factors":    [{name, data_type, operator, expected_value, unit, weight}],
         "candidates": [{name, scores: {factor: pct|None}, unit_values: {factor: str}}]}

    Returns None when the payload isn't a usable detail extraction (including
    the explicit {"page_type": "comparison"} signal).
    """
    if not isinstance(data, dict) or data.get("page_type") != "detail":
        return None
    main_name = str((data.get("main_item") or {}).get("name") or "").strip()
    raw_factors = data.get("factors") or []
    if not main_name or not isinstance(raw_factors, list) or not raw_factors:
        return None

    factors: List[Dict[str, Any]] = []
    seen: set = set()
    for f in raw_factors[: max(1, max_factors)]:
        if not isinstance(f, dict):
            continue
        name = str(f.get("name") or "").strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        dt = "numeric" if str(f.get("data_type") or "").lower() == "numeric" else "text"
        op = str(f.get("operator") or "").strip()
        if dt == "numeric":
            op = op if op in _NUMERIC_OPS else ">="
        else:
            op = op if op in _TEXT_OPS else "equals"
        ev = f.get("expected_value")
        ev = str(ev).strip() if ev not in (None, "") else None
        unit = f.get("unit")
        unit = str(unit).strip() if unit not in (None, "") else None
        factors.append({"name": name, "data_type": dt, "operator": op,
                        "expected_value": ev, "unit": unit, "weight": 50})
    if not factors:
        return None
    fnames = {f["name"] for f in factors}

    candidates: List[Dict[str, Any]] = []
    seen_items: set = set()
    main_key = _squash(main_name)
    for idx, it in enumerate((data.get("items") or [])[:12]):
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or "").strip()
        key = _squash(name)
        if not name or key in seen_items:
            continue
        is_main = idx == 0 or key == main_key
        if is_main and any(_squash(c["name"]) == main_key or c.get("_is_main")
                           for c in candidates):
            continue  # LLM repeated the main item under a slightly different name
        seen_items.add(key)
        values = it.get("values") if isinstance(it.get("values"), dict) else {}
        raw_scores = it.get("scores") if isinstance(it.get("scores"), dict) else {}
        scores: Dict[str, Optional[int]] = {}
        unit_values: Dict[str, str] = {}
        for fn in fnames:
            v = values.get(fn)
            if v not in (None, ""):
                unit_values[fn] = str(v).strip()
            p = _pct(raw_scores.get(fn))
            # The main item DEFINES the expectations → it satisfies them (100).
            if p is None and is_main:
                p = 100
            scores[fn] = p
        candidates.append({"name": name[:160], "scores": scores, "unit_values": unit_values})

    # Guarantee the main item exists as Option 1 even if the LLM omitted `items`.
    if not candidates or candidates[0]["name"].lower() != main_name.lower():
        main = {"name": main_name[:160],
                "scores": {f["name"]: 100 for f in factors},
                "unit_values": {f["name"]: f["expected_value"] for f in factors
                                if f["expected_value"] not in (None, "")}}
        candidates = [c for c in candidates if c["name"].lower() != main_name.lower()]
        candidates.insert(0, main)

    return {"main_name": main_name, "factors": factors, "candidates": candidates}


async def ai_extract_detail(user_id: str, html: str, *, tier: str = "fast",
                            max_factors: int = 24) -> Optional[Dict[str, Any]]:
    """One metered LLM call → normalised detail structure, or None when the
    page isn't a single-item detail page / the model output is unusable.
    Propagates InsufficientCredits so the route can answer 402."""
    if not has_any_llm() or not (html or "").strip():
        return None
    text = page_text(html, limit=14000 if tier == "precise" else 11000)
    related = _embedded_related_snippets(html)
    if related:
        text += "\nEMBEDDED RELATED-ITEMS DATA (similar/related items the page renders with JavaScript):\n" + related
    sys = DETAIL_SYSTEM.replace("{max_factors}", str(max_factors))
    meta: Dict[str, Any] = {}
    try:
        out = await metered_chat(user_id, system_message=sys, prompt=text,
                                 feature="url_import_detail", session_prefix="urldetail",
                                 tier=tier, meta=meta)
    except ai_wallet.InsufficientCredits:
        raise
    except Exception as e:  # noqa: BLE001 — extraction is best-effort
        logger.warning("detail extraction LLM call failed: %s: %s",
                       type(e).__name__, str(e)[:150])
        return None
    result = normalize_detail(_parse_json_obj(out), max_factors=max_factors)
    if result is not None:
        result["provider"] = meta.get("provider") or ""
    return result
