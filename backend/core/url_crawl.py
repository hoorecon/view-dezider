"""Shared URL → candidate-list crawler.

Used by BOTH the partner Screener (paste-URL premium mode) and the standalone
end-user "Analyse a URL" feature. Fetches a page, extracts a comparable item
list either from the first usable HTML <table> or — failing that — via a
metered LLM extraction. Returns a normalised list of
``[{"name": str, "attributes": {key: value}}]``.

This module is deliberately gate-free: legal/consent gating is the caller's
responsibility (admin attestation for the partner screener; user consent for
the standalone flow).
"""
from __future__ import annotations

import re
import json
import asyncio
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

from core.ai_metering import metered_chat, has_any_llm

HTTP_TIMEOUT = 25.0
MAX_CANDIDATES = 200

# Realistic desktop-browser headers. Many sites reject non-browser/bot clients
# with 403/503; a standard UA + Accept headers dramatically improves success.
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}

# Status codes that usually mean "automated access blocked" rather than a
# genuinely missing page. Worth a short retry, and a clearer message if persistent.
_BOT_BLOCK_CODES = {403, 429, 503}

_NAME_KEYS = ("name", "Name", "title", "Title", "scheme", "Scheme", "fund", "Fund", "product", "Product")


def _rows_to_candidates(rows: List[Dict[str, Any]], name_key: Optional[str] = None) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        attrs = {str(k): r[k] for k in r.keys()}
        nk = name_key if (name_key and name_key in attrs) else None
        if not nk:
            for cand_key in _NAME_KEYS:
                if cand_key in attrs:
                    nk = cand_key
                    break
        if not nk:
            nk = next(iter(attrs.keys()), None)
        name = str(attrs.get(nk, "")).strip() if nk else ""
        if not name:
            continue
        out.append({"name": name, "attributes": attrs})
        if len(out) >= MAX_CANDIDATES:
            break
    return out


def _html_table_rows(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    best: List[Dict[str, Any]] = []
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        rows: List[Dict[str, Any]] = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if not cells:
                continue
            if headers and len(headers) == len(cells):
                rows.append({headers[i]: cells[i] for i in range(len(cells))})
            else:
                rows.append({f"col{i}": cells[i] for i in range(len(cells))})
        if len(rows) > len(best):
            best = rows
    return best


async def ai_extract_candidates(user_id: str, html: str) -> List[Dict[str, Any]]:
    """LLM fallback for table-less pages. Metered to the user's wallet."""
    if not has_any_llm():
        return []
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = re.sub(r"\n{2,}", "\n", soup.get_text("\n", strip=True))[:6000]
    sys = ("Extract the list of comparable items from this page. Reply ONLY a compact "
           "JSON array of objects: {\"name\": str, \"attributes\": {key: value}} with the "
           "numeric/comparable attributes you can find. No prose, max 50 items.")
    try:
        out = await metered_chat(user_id, system_message=sys, prompt=text,
                                 feature="url_analyze_extract", session_prefix="urlanalyze")
        m = re.search(r"\[.*\]", out, re.S)
        data = json.loads(m.group(0)) if m else []
        return data if isinstance(data, list) else []
    except Exception:
        return []


async def crawl_candidates(url: str, user_id: str, name_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch `url` and return a normalised candidate list. Raises HTTPException
    with a user-friendly message on failure."""
    url = (url or "").strip()
    if not url or not re.match(r"^https?://", url, re.I):
        raise HTTPException(400, "Enter a valid http(s) URL.")

    r = None
    last_err: Optional[Exception] = None
    # Up to 3 attempts; brief backoff helps with transient 429/503 throttling.
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True,
                                         headers=_BROWSER_HEADERS) as cli:
                r = await cli.get(url)
            if r.status_code not in _BOT_BLOCK_CODES:
                break
        except Exception as e:  # network/DNS/TLS errors
            last_err = e
            r = None
        if attempt < 2:
            await asyncio.sleep(0.8 * (attempt + 1))

    if r is None:
        raise HTTPException(
            400,
            f"Could not reach the URL ({type(last_err).__name__ if last_err else 'network error'}). "
            "Check the link is public and reachable.",
        )

    if r.status_code in _BOT_BLOCK_CODES:
        raise HTTPException(
            422,
            f"This site blocked automated access (HTTP {r.status_code}). Large retail/JS-heavy "
            "sites like Amazon, Flipkart or Google often reject crawlers. Try a public comparison "
            "or listing page that shows items in a plain table (e.g. a review/aggregator site), "
            "or the Screener (CSV upload) for retail product lists.",
        )
    if r.status_code >= 400:
        raise HTTPException(422, f"URL fetch failed (HTTP {r.status_code}). The page may be private or removed.")

    ctype = r.headers.get("content-type", "")
    if "json" in ctype:
        try:
            data = r.json()
        except Exception:
            data = None
        if isinstance(data, list):
            cands = _rows_to_candidates(data, name_key)
            if cands:
                return cands
        raise HTTPException(422, "The JSON URL did not yield a usable list of items.")

    rows = _html_table_rows(r.text)
    if rows:
        cands = _rows_to_candidates(rows, name_key)
        if cands:
            return cands

    ai_rows = await ai_extract_candidates(user_id, r.text)
    if ai_rows:
        cands = _rows_to_candidates(ai_rows, name_key)
        if cands:
            return cands

    raise HTTPException(
        422,
        "Could not extract a comparable list from this page. The page may load its items "
        "via JavaScript (which we can't render) or have no clean table. Try a comparison/filter "
        "page that lists items in a table, a JSON/API endpoint, or use the Screener CSV upload.",
    )
