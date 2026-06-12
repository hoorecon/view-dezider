"""LLM page-type classification for the Import-from-URL pipeline.

Every import is classified into ONE of five page types so that (a) the
extraction LLM receives a prompt SPECIALISED for that page shape and (b) the
admin Import-Analytics dashboard can track accuracy per page type.

Classification is a tiny fast-tier metered call (~100 output tokens). When the
LLM is unavailable the heuristic fallback keeps the import unblocked.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict

from bs4 import BeautifulSoup

from core.ai_metering import has_any_llm, metered_chat

logger = logging.getLogger(__name__)

PAGE_TYPES = ("comparison_matrix", "listing_filter", "detail", "search_grid", "article_roundup")

CLASSIFY_SYSTEM = """You classify ONE web page for a data-extraction pipeline. Exactly one type:
- "comparison_matrix": side-by-side spec comparison of 2+ NAMED items (items as columns, attribute rows — e.g. GSMArena compare, versus.com, "A vs B" pages)
- "listing_filter": a category/listing page with filter facets (budget/brand/body-type tabs or sidebars) and a list of items (e.g. "best electric cars under 10 lakh", real-estate locality listings)
- "search_grid": a search-results grid of product cards each showing price/rating (e.g. Amazon/Flipkart search results)
- "detail": ONE main item presented in detail (single product / property / vehicle / job / course page), possibly with a "similar items" rail
- "article_roundup": an editorial ARTICLE ranking or reviewing several items in prose ("Top 10 …", "Best … of 2026" blog-style)
Reply ONLY compact JSON: {"page_type":"<one of the five>","confidence":0.0-1.0}"""


def _signals(html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html or "", "html.parser")
    title = (soup.find("title").get_text(" ", strip=True) if soup.find("title") else "")[:200]
    h1 = (soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else "")[:200]
    tables = soup.find_all("table")
    max_rows = max((len(t.find_all("tr")) for t in tables), default=0)
    cards = len(soup.select('div[data-asin], [itemtype*="schema.org/Product"], li.product, div.product'))
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = re.sub(r"\n{2,}", "\n", soup.get_text("\n", strip=True))
    return {"title": title, "h1": h1, "table_count": len(tables),
            "max_table_rows": max_rows, "product_card_count": cards,
            "text_head": text[:2500]}


def heuristic_page_type(html: str) -> str:
    """No-LLM fallback. Best-effort guess from structural signals."""
    s = _signals(html)
    title = f"{s['title']} {s['h1']}".lower()
    if re.search(r"\bvs\.?\b|\bversus\b|compare", title) and s["table_count"] >= 1:
        return "comparison_matrix"
    if s["product_card_count"] >= 4:
        return "search_grid"
    if re.search(r"\b(best|top)\b.*\b(under|of|in|for)\b|\btop\s*\d+\b", title):
        return "listing_filter"
    if s["table_count"] >= 3 and s["max_table_rows"] >= 4:
        return "comparison_matrix"
    return "detail"


async def classify_page_type(user_id: str, html: str, url: str) -> Dict[str, Any]:
    """Returns {"page_type", "confidence", "provider"} — never raises
    (falls back to the heuristic so classification can't block an import)."""
    if not has_any_llm():
        return {"page_type": heuristic_page_type(html), "confidence": 0.4, "provider": "heuristic"}
    s = _signals(html)
    prompt = (f"URL: {url}\nTITLE: {s['title']}\nH1: {s['h1']}\n"
              f"SIGNALS: tables={s['table_count']} max_table_rows={s['max_table_rows']} "
              f"product_cards={s['product_card_count']}\n"
              f"PAGE TEXT (head):\n{s['text_head']}")
    meta: Dict[str, Any] = {}
    try:
        out = await metered_chat(user_id, system_message=CLASSIFY_SYSTEM, prompt=prompt,
                                 feature="url_import_classify", session_prefix="urlclass",
                                 tier="fast", meta=meta)
        m = re.search(r"\{.*\}", out or "", re.S)
        data = json.loads(m.group(0)) if m else {}
        pt = str(data.get("page_type") or "").strip()
        if pt not in PAGE_TYPES:
            raise ValueError(f"unknown page_type {pt!r}")
        conf = max(0.0, min(1.0, float(data.get("confidence") or 0.5)))
        return {"page_type": pt, "confidence": conf, "provider": meta.get("provider") or ""}
    except Exception as e:  # noqa: BLE001 — classification is best-effort
        logger.warning("page-type LLM classify failed (%s: %s) — heuristic fallback",
                       type(e).__name__, str(e)[:120])
        return {"page_type": heuristic_page_type(html), "confidence": 0.4, "provider": "heuristic"}
