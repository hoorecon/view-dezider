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
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

from core.ai_metering import metered_chat, has_any_llm

HTTP_TIMEOUT = 20.0
MAX_CANDIDATES = 200
_BOT_UA = "Mozilla/5.0 (ViewDeziderBot; +https://viewdezider.com/bot)"

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
    if not url or not re.match(r"^https?://", url.strip(), re.I):
        raise HTTPException(400, "Enter a valid http(s) URL.")
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True,
                                     headers={"User-Agent": _BOT_UA}) as cli:
            r = await cli.get(url.strip())
    except Exception as e:
        raise HTTPException(400, f"Could not reach the URL ({type(e).__name__}).")
    if r.status_code >= 400:
        raise HTTPException(400, f"URL fetch failed (HTTP {r.status_code}).")

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
        "Could not extract a comparable list from this page (no clean table found "
        "and AI extraction was unavailable). Try a comparison/filter page that lists "
        "items in a table.",
    )
