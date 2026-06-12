"""Single-item DETAIL-page import — the "intelligent" Import-from-URL path.

When a pasted URL is a single listing/product/detail page (NOT a comparison
table), ONE metered LLM call turns the page into a decision-ready structure:

  • every concrete attribute of the main item becomes a FACTOR (optionally
    grouped into parent factors with SUB-factors, equal weight split) with a
    smart direction-aware operator (Rent ≤ 18,000 · Area ≥ 650 sqft ·
    Furnishing = Semi …) and the item's own value as the suggested Expected,
  • each factor carries BOTH data_type (numeric/text — the VALUE format) and
    factor_type (quantitative/qualitative — the NATURE: undisputed fact/spec
    vs person-dependent judgment),
  • the main item becomes Option 1 (it satisfies its own expectations → 100%),
  • "Similar / Related items" sections become extra options with whatever
    partial values + relative scores are visible on the page.

GROUPING GUIDELINES (user-mandated):
  1. Page-defined groups (e.g. GSMArena's BODY → Dimensions/Weight/Build/SIM)
     are SACRED — never modified or overridden.
  2. AI may invent groups ONLY when the page defines none AND the factor count
     exceeds the admin-configurable threshold (`import_group_threshold`).
  3. ZERO TOLERANCE on value mapping: values/scores are keyed by the FULL
     "Group::Factor" path so regrouping can never shuffle an option's values.

ACCURACY HINTS (optional, user-supplied): expected factor/option counts and
first factor/option names. When provided, the extraction is validated against
them and retried ONCE with corrective feedback on mismatch (self-healing).

Tiers: "fast" = free-first Gemini chain; "precise" = Claude (admin-configured
`precise_model`) via the Emergent universal key at the configured multiplier.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from core import ai_wallet
from core.ai_metering import has_any_llm, metered_chat
from core.url_crawl import page_text

logger = logging.getLogger(__name__)

_NUMERIC_OPS = {"<=", ">=", "=", "<", ">", "!="}
_TEXT_OPS = {"contains", "starts_with", "ends_with", "equals", "not_equals"}
SEP = "::"

# Keys inside embedded SPA-state JSON that hold "similar / related items" data
# (e.g. NoBroker's similarPropertiesInfo, generic relatedProducts, recommendations).
_RELATED_KEY_RE = re.compile(
    r'"([a-zA-Z0-9_]*(?:similar|related|recommend)[a-zA-Z0-9_]*)"\s*:', re.I)


def _embedded_related_snippets(html: str, max_snippets: int = 2,
                               max_chars: int = 10000) -> str:
    """Mine the raw HTML's inline-script JSON state for similar/related-items
    blocks. Many listing sites server-embed the 'Similar items' rail data but
    only render it with JavaScript — so it is invisible to plain text
    extraction. Heavy media/description sub-objects are stripped to keep
    signal density high."""
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
    """Whitespace-insensitive dedupe / fuzzy-match key."""
    return " ".join(str(name or "").lower().split())


DETAIL_SYSTEM = """You convert ONE web page into a decision-comparison structure. The page is EITHER:
  (A) page_type="detail" — a single MAIN item shown in detail (property listing, product, vehicle, job, course, service, …), possibly with a "Similar/Related items" rail, OR
  (B) page_type="comparison" — a comparison / listing / filter / "best-of" page presenting MULTIPLE comparable items (e.g. "Best electric cars under 10 lakh", search results, category listings).

Reply ONLY compact JSON (no prose, no markdown fences):
{"page_type":"detail"|"comparison",
 "main_item":{"name":"<detail: the listing's own DISPLAY HEADING on the page (not the SEO <title> tag); comparison: the FIRST listed item>"},
 "groups":[{"name":"<group name or 'General'>","source":"page"|"ai"|"none",
            "factors":[{"name":str,"data_type":"numeric"|"text","factor_type":"quantitative"|"qualitative","operator":"<="|">="|"="|"equals","expected_value":str,"unit":str|null}]}],
 "items":[{"name":str,"values":{"<group>::<factor>":str|null},"scores":{"<group>::<factor>":0-100|null}}]}

RULES
1. FACTORS —
   • detail pages: be EXHAUSTIVE: extract EVERY concrete attribute/spec of the MAIN item (a typical detail page yields 15-25 factors — do NOT summarise attributes away): prices, rents, fees, deposits, maintenance, sizes, counts, scores, ratings, dates, categories, yes/no flags, address/locality.
   • comparison/listing pages: factors = the attributes/facets by which the page compares or filters its items — use the page's OWN facet/section labels as factor names (e.g. Brand, Budget/Price, Body Type, Fuel Type, Transmission, Seating Capacity, Rating) plus per-item attributes shown on the listing cards.
   EXCLUDE site navigation, service promos, marketing prose, breadcrumbs, nearby-locality link lists.
2. GROUPING — three cases, in priority order:
   a. The PAGE already groups specs under section headings (e.g. BODY → Dimensions/Weight/Build/SIM): copy that grouping EXACTLY, source="page". NEVER rename, merge, split or re-assign page-defined groups.
   b. The page defines no grouping and there are MORE than {group_threshold} factors: YOU may group related factors into 3-7 sensible categories (e.g. Costs / Space & Layout / Location / Amenities), source="ai".
   c. Otherwise: a single group {"name":"General","source":"none"} holding all factors flat.
3. data_type describes the VALUE FORMAT only: "numeric" when the value is one measurable number (650, 18000, 6.2); composite values like "0/4", "2 BHK", dates, yes/no → "text".
4. factor_type describes the NATURE — INDEPENDENT of data_type:
   • "quantitative" = an UNDISPUTED fact/spec that is identical for every observer — even when the value is text. Color=Blue, Furnishing=Semi, Facing=South, SIM=Nano, Brand, Address, Yes/No flags are ALL quantitative (measurable & claimable, no debate).
   • "qualitative" = person-dependent judgment that can differ between people for the SAME item: Comfort, Luxury Feel, Design Appeal, Neighbourhood Vibe, Build Quality impression, Ease of Use. These need AI/judgment-based assessment later.
   Most spec-sheet factors are quantitative. Only judgment factors are qualitative.
5. operator expresses the DIRECTION a decision-maker wants versus this item's value:
   • "<=" for lower-is-better numerics (rent, price, deposit, fees, maintenance, distance, commute) — inversely proportional to satisfaction
   • ">=" for higher-is-better numerics (area, scores, ratings, capacity, warranty) — directly proportional
   • "=" for numeric identity values (bedroom count, bathroom count)
   • "equals" for ALL text-format factors (type, furnishing, facing, tenant, possession, yes/no, NA, locality)
6. expected_value, cleaned (plain numbers for numerics — no currency symbols or thousands separators; concise text otherwise; keep "NA" when the page shows NA; units like sqft/INR/years/km go ONLY in "unit", never inside expected_value):
   • detail pages: the MAIN item's own value.
   • comparison pages: the most DESIRABLE value across the listed items (cheapest price, highest rating, …).
7. ITEMS —
   • detail pages: FIRST item MUST be the main item with every factor value filled and every score 100. THEN every DIFFERENT similar/related item (sections like "Similar Properties", "Related products", "You may also like", plus any EMBEDDED RELATED-ITEMS DATA appended after the page text): its name plus whatever factor values are known. NEVER repeat the main item as a similar item. NEVER invent values you cannot see — unknown values MUST be null in BOTH maps.
   • comparison pages: EVERY genuinely listed/compared item, in page order (skip pure ad inserts when identifiable). Fill each item's value for every factor: prefer values shown on the page; for OBJECTIVE specs of a specific well-known product (its brand, fuel type, body type, transmission, seating capacity, …) you may fill from reliable general knowledge when the page omits them; truly unknown values stay null in BOTH maps.
   Score each KNOWN value 0-100 for how well it satisfies expected_value+operator (better than expected → 100; ~10% worse → ≈80).
8. ZERO-TOLERANCE MAPPING: every key inside "values" and "scores" MUST be exactly "<group name>::<factor name>" matching a declared group+factor. A value MUST stay attached to the item it belongs to on the page — never shift values between items or factors.
9. Max {max_factors} factors total, max 12 items.{user_facts}"""


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


def _norm_factor(f: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(f, dict):
        return None
    name = str(f.get("name") or "").strip()
    if not name:
        return None
    dt = "numeric" if str(f.get("data_type") or "").lower() == "numeric" else "text"
    ft = "qualitative" if str(f.get("factor_type") or "").lower() == "qualitative" else "quantitative"
    op = str(f.get("operator") or "").strip()
    if dt == "numeric":
        op = op if op in _NUMERIC_OPS else ">="
    else:
        op = op if op in _TEXT_OPS else "equals"
    ev = f.get("expected_value")
    ev = str(ev).strip() if ev not in (None, "") else None
    unit = f.get("unit")
    unit = str(unit).strip() if unit not in (None, "") else None
    return {"name": name, "data_type": dt, "factor_type": ft, "operator": op,
            "expected_value": ev, "unit": unit, "weight": 50}


def normalize_detail(data: Any, max_factors: int = 24,
                     group_threshold: int = 15) -> Optional[Dict[str, Any]]:
    """Validate + normalise the LLM's detail JSON. Returns either

      kind="flat": {"kind","main_name","factors","candidates"}            or
      kind="hier": {"kind","main_name","items","groups","row_scores","row_meta"}

    (hier shapes feed merge_hierarchical_into_mydezider / create_hierarchical_
    mydezider directly). Returns None for unusable output.

    Handles BOTH page kinds: "detail" (single main item + similar rail — the
    main item gets 100% scores and its values backfilled from Expected) and
    "comparison" (listing/filter/best-of page — every item is a peer, scored
    purely by how its values satisfy the expectations).
    """
    if not isinstance(data, dict) or data.get("page_type") not in ("detail", "comparison"):
        return None
    is_detail = data.get("page_type") == "detail"
    main_name = str((data.get("main_item") or {}).get("name") or "").strip()
    raw_groups = data.get("groups")
    if not main_name:
        first = next((i for i in (data.get("items") or []) if isinstance(i, dict)), None)
        main_name = str((first or {}).get("name") or "").strip()
    if not main_name:
        return None
    # Back-compat: accept a flat "factors" list when "groups" is missing.
    if not isinstance(raw_groups, list) or not raw_groups:
        flat = data.get("factors")
        if not isinstance(flat, list) or not flat:
            return None
        raw_groups = [{"name": "General", "source": "none", "factors": flat}]

    # ── Normalise groups + factors; enforce grouping guidelines server-side ──
    groups: List[Dict[str, Any]] = []
    seen_paths: set = set()
    total = 0
    for g in raw_groups[:10]:
        if not isinstance(g, dict):
            continue
        gname = str(g.get("name") or "General").strip() or "General"
        source = str(g.get("source") or "none").lower()
        facs: List[Dict[str, Any]] = []
        for rf in (g.get("factors") or []):
            if total >= max_factors:
                break
            nf = _norm_factor(rf)
            if not nf:
                continue
            path = _squash(gname) + SEP + _squash(nf["name"])
            if path in seen_paths:
                continue
            seen_paths.add(path)
            nf["_path"] = f"{gname}{SEP}{nf['name']}"
            facs.append(nf)
            total += 1
        if facs:
            groups.append({"name": gname, "source": source, "factors": facs})
    if total == 0:
        return None

    # AI grouping is allowed ONLY above the threshold; page grouping is sacred.
    page_grouped = any(g["source"] == "page" for g in groups)
    ai_grouped = any(g["source"] == "ai" for g in groups)
    flatten = (len(groups) == 1) or (not page_grouped and ai_grouped and total <= group_threshold)

    # Path → factor lookup tolerant to bare-factor-name keys (zero ambiguity:
    # bare names resolve only when unique across all groups).
    by_path: Dict[str, Dict[str, Any]] = {}
    name_counts: Dict[str, int] = {}
    for g in groups:
        for f in g["factors"]:
            by_path[_squash(g["name"]) + SEP + _squash(f["name"])] = f
            name_counts[_squash(f["name"])] = name_counts.get(_squash(f["name"]), 0) + 1
    bare_ok = {n for n, c in name_counts.items() if c == 1}

    def _resolve(key: str) -> Optional[Dict[str, Any]]:
        k = _squash(key)
        if SEP in key:
            gpart, _, fpart = key.partition(SEP)
            return by_path.get(_squash(gpart) + SEP + _squash(fpart))
        return by_path.get(next((p for p in by_path if p.endswith(SEP + k) and k in bare_ok), ""))

    # ── Items (main first; whitespace-insensitive dedupe; main never repeats) ──
    norm_items: List[Dict[str, Any]] = []
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
        if is_main and any(i.get("_is_main") for i in norm_items):
            continue
        seen_items.add(key)
        values = it.get("values") if isinstance(it.get("values"), dict) else {}
        raw_scores = it.get("scores") if isinstance(it.get("scores"), dict) else {}
        vmap: Dict[str, Any] = {}
        smap: Dict[str, Optional[int]] = {}
        for src, dst in ((values, vmap), (raw_scores, smap)):
            for k, v in src.items():
                f = _resolve(str(k))
                if f is None:
                    continue  # ZERO TOLERANCE: unknown keys are dropped, never guessed
                dst[f["_path"]] = v
        item = {"name": name[:160], "_is_main": is_main, "values": vmap, "scores": smap}
        if is_main and is_detail:
            for g in groups:
                for f in g["factors"]:
                    item["scores"].setdefault(f["_path"], 100)
                    if f["expected_value"] not in (None, ""):
                        item["values"].setdefault(f["_path"], f["expected_value"])
        norm_items.append(item)

    if not norm_items or not norm_items[0].get("_is_main"):
        if not is_detail:
            # Comparison pages have no synthetic "main" — items are peers.
            if not norm_items:
                return None
            norm_items[0]["_is_main"] = True
        else:
            main = {"name": main_name[:160], "_is_main": True,
                    "values": {f["_path"]: f["expected_value"] for g in groups for f in g["factors"]
                               if f["expected_value"] not in (None, "")},
                    "scores": {f["_path"]: 100 for g in groups for f in g["factors"]}}
            norm_items = [i for i in norm_items if not i.get("_is_main")]
            norm_items.insert(0, main)

    # ── Emit FLAT ──
    if flatten:
        factors = []
        for g in groups:
            for f in g["factors"]:
                factors.append({k: f[k] for k in
                                ("name", "data_type", "factor_type", "operator",
                                 "expected_value", "unit", "weight")} | {"_path": f["_path"]})
        candidates = []
        for it in norm_items:
            scores = {f["name"]: _pct(it["scores"].get(f["_path"])) for f in factors}
            uvals = {f["name"]: str(it["values"][f["_path"]]).strip()
                     for f in factors if it["values"].get(f["_path"]) not in (None, "")}
            candidates.append({"name": it["name"], "scores": scores, "unit_values": uvals})
        for f in factors:
            f.pop("_path", None)
        return {"kind": "flat", "main_name": main_name,
                "factors": factors, "candidates": candidates}

    # ── Emit HIERARCHICAL (groups → parent factors, factors → sub-factors) ──
    item_names = [it["name"] for it in norm_items]
    out_groups: List[Dict[str, Any]] = []
    row_scores: Dict[Any, List[Optional[int]]] = {}
    row_meta: Dict[Any, Dict[str, Any]] = {}
    for gi, g in enumerate(groups):
        rows = []
        for ri, f in enumerate(g["factors"]):
            vals = [str(it["values"].get(f["_path"], "") or "").strip() for it in norm_items]
            rows.append({"label": f["name"], "values": vals})
            row_scores[(gi, ri)] = [_pct(it["scores"].get(f["_path"])) for it in norm_items]
            row_meta[(gi, ri)] = {
                "is_numeric": f["data_type"] == "numeric",
                "expected": f["expected_value"], "operator": f["operator"],
                "unit": f["unit"], "factor_type": f["factor_type"],
            }
        out_groups.append({"category": g["name"], "rows": rows})
    return {"kind": "hier", "main_name": main_name, "items": item_names,
            "groups": out_groups, "row_scores": row_scores, "row_meta": row_meta}


# ── Accuracy-hint validation (self-healing oracle) ──────────────────────────
def _count_leaf_factors(result: Dict[str, Any]) -> int:
    if result["kind"] == "flat":
        return len(result["factors"])
    return sum(len(g["rows"]) for g in result["groups"])


def _first_factor_name(result: Dict[str, Any]) -> str:
    if result["kind"] == "flat":
        return result["factors"][0]["name"] if result["factors"] else ""
    for g in result["groups"]:
        if g["rows"]:
            return g["rows"][0]["label"]
    return ""


def _option_names(result: Dict[str, Any]) -> List[str]:
    if result["kind"] == "flat":
        return [c["name"] for c in result["candidates"]]
    return list(result["items"])


def _fuzzy_match(a: str, b: str) -> bool:
    sa, sb = _squash(a), _squash(b)
    return bool(sa and sb) and (sa in sb or sb in sa)


def validate_against_hints(result: Dict[str, Any],
                           hints: Optional[Dict[str, Any]]) -> List[str]:
    """Compare the extraction against the user's optional accuracy hints.
    Returns a list of human-readable discrepancies ([] = passes)."""
    issues: List[str] = []
    if not result or not hints:
        return issues
    efc = hints.get("expected_factor_count")
    if efc:
        got = _count_leaf_factors(result)
        tol = max(2, round(int(efc) * 0.2))
        if abs(got - int(efc)) > tol:
            issues.append(f"You extracted {got} factors but the user expects about {efc}. "
                          "Re-scan the page for missed or over-extracted attributes.")
    eoc = hints.get("expected_option_count")
    if eoc:
        got = len(_option_names(result))
        if abs(got - int(eoc)) > 1:
            issues.append(f"You extracted {got} options/items but the user expects about {eoc} "
                          "(the main item plus the similar/related items shown on the page).")
    ffn = (hints.get("first_factor_name") or "").strip()
    if ffn:
        got = _first_factor_name(result)
        if not _fuzzy_match(ffn, got):
            issues.append(f"The FIRST factor should be '{ffn}' (user-confirmed) but you produced "
                          f"'{got}'. Follow the page's own top-to-bottom factor order.")
    fon = (hints.get("first_option_name") or "").strip()
    if fon:
        names = _option_names(result)
        got = names[0] if names else ""
        if not _fuzzy_match(fon, got):
            issues.append(f"The FIRST option should be '{fon}' (user-confirmed, the main item) "
                          f"but you produced '{got}'.")
    return issues


def deterministic_hint_issues(hints: Optional[Dict[str, Any]], *,
                              factors: Optional[List[Dict[str, Any]]] = None,
                              candidates: Optional[List[Dict[str, Any]]] = None,
                              hierarchy: Optional[Dict[str, Any]] = None) -> List[str]:
    """Validate a DETERMINISTIC (non-LLM) parse against the user's accuracy
    hints. Routes use this to decide whether a free table/matrix parse is good
    enough or must ESCALATE to the hint-guided AI extraction. [] = passes."""
    if not hints:
        return []
    if hierarchy is not None:
        shim: Dict[str, Any] = {"kind": "hier", "groups": hierarchy.get("groups") or [],
                                "items": hierarchy.get("items") or []}
    else:
        shim = {"kind": "flat", "factors": factors or [], "candidates": candidates or []}
    return validate_against_hints(shim, hints)


def _user_facts_block(hints: Optional[Dict[str, Any]]) -> str:
    """Render the user's accuracy hints as ground-truth facts for the FIRST
    LLM attempt (not just the corrective retry) — the user is literally looking
    at the page, so these outrank any model judgment."""
    if not hints:
        return ""
    lines: List[str] = []
    if hints.get("expected_factor_count"):
        lines.append(f"- The page offers about {hints['expected_factor_count']} comparison factors/facets.")
    if hints.get("first_factor_name"):
        lines.append(f"- The FIRST factor is named '{hints['first_factor_name']}' — find that section/facet on the page and start with it.")
    if hints.get("expected_option_count"):
        lines.append(f"- There are about {hints['expected_option_count']} options/items to compare.")
    if hints.get("first_option_name"):
        lines.append(f"- The FIRST option/item is '{hints['first_option_name']}'.")
    return ("\n\nUSER-VERIFIED PAGE FACTS (the user is LOOKING at this page; these are ground truth and your output MUST match them):\n"
            + "\n".join(lines)
            + "\nHonor these exactly: use the page's own facet/section labels as factor names, "
              "begin with the named first factor, and order items starting with the named first option.")


async def ai_extract_detail(user_id: str, html: str, *, tier: str = "fast",
                            max_factors: int = 24, group_threshold: int = 15,
                            hints: Optional[Dict[str, Any]] = None,
                            ) -> Optional[Dict[str, Any]]:
    """Metered LLM extraction → normalised detail structure (flat or hier),
    or None when the page isn't a single-item detail page / output unusable.
    When `hints` are given and the first attempt mismatches them, ONE corrective
    retry is made and the better attempt wins (self-healing).
    Propagates InsufficientCredits so the route can answer 402."""
    if not has_any_llm() or not (html or "").strip():
        return None
    text = page_text(html, limit=30000 if tier == "precise" else 12000)
    related = _embedded_related_snippets(html)
    if related:
        text += "\nEMBEDDED RELATED-ITEMS DATA (similar/related items the page renders with JavaScript):\n" + related
    sys = (DETAIL_SYSTEM
           .replace("{max_factors}", str(max_factors))
           .replace("{group_threshold}", str(group_threshold))
           .replace("{user_facts}", _user_facts_block(hints)))

    async def _attempt(extra: str = "") -> Tuple[Optional[Dict[str, Any]], str]:
        meta: Dict[str, Any] = {}
        try:
            out = await metered_chat(user_id, system_message=sys + extra, prompt=text,
                                     feature="url_import_detail", session_prefix="urldetail",
                                     tier=tier, meta=meta)
        except ai_wallet.InsufficientCredits:
            raise
        except Exception as e:  # noqa: BLE001 — extraction is best-effort
            logger.warning("detail extraction LLM call failed: %s: %s",
                           type(e).__name__, str(e)[:150])
            return None, ""
        return (normalize_detail(_parse_json_obj(out), max_factors=max_factors,
                                 group_threshold=group_threshold),
                meta.get("provider") or "")

    result, provider = await _attempt()
    issues = validate_against_hints(result, hints) if result else []
    if hints and (result is None or issues):
        feedback = ("\n\nPREVIOUS ATTEMPT FAILED USER VERIFICATION:\n- "
                    + "\n- ".join(issues or ["Output was not parseable detail JSON."])
                    + "\nRe-extract the ENTIRE structure from scratch, fixing every issue above. "
                      "Keep the zero-tolerance value↔item mapping rule.")
        retry, p2 = await _attempt(feedback)
        if retry is not None:
            retry_issues = validate_against_hints(retry, hints)
            if result is None or len(retry_issues) < len(issues):
                result, provider, issues = retry, p2, retry_issues
    if result is not None:
        result["provider"] = provider
        result["hint_warnings"] = issues
    return result
