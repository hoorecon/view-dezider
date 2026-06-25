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
import logging
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

from core.ai_metering import metered_chat, has_any_llm
from core.integrations import resolve_scraperapi
from core import scrape_meter

logger = logging.getLogger(__name__)

# Domains that render their product/comparison list with JavaScript — direct
# httpx returns thin/empty HTML, so route these through ScraperAPI when a key
# is configured (otherwise they simply won't yield results).
_JS_HEAVY_DOMAINS = (
    "amazon.", "flipkart.", "shopping.google.", "google.com/shopping",
    "myntra.", "ajio.", "croma.", "reliancedigital.", "tatacliq.",
)

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


_VS_SPLIT_RE = re.compile(r"\s+(?:vs\.?|versus)\s+", re.IGNORECASE)
_GENERIC_KEY_RE = re.compile(r"^col\d+$", re.IGNORECASE)


def _names_from_title(soup: "BeautifulSoup") -> List[str]:
    """Extract compared item names from a 'Compare A vs. B vs. C - Site' title/h1."""
    txt = ""
    t = soup.find("title")
    if t:
        txt = t.get_text(" ", strip=True)
    if not txt:
        h1 = soup.find("h1")
        txt = h1.get_text(" ", strip=True) if h1 else ""
    if not txt:
        return []
    txt = re.split(r"\s[-|–—]\s", txt)[0]                 # drop " - GSMArena.com"
    txt = re.sub(r"^\s*compare\s+", "", txt, flags=re.IGNORECASE)
    parts = [p.strip() for p in _VS_SPLIT_RE.split(txt) if p.strip()]
    return parts if 2 <= len(parts) <= 12 else []


def _comparison_matrix_candidates(html: str) -> List[Dict[str, Any]]:
    """Parse a TRANSPOSED comparison matrix where the compared items are COLUMNS
    and the attributes are ROWS (e.g. GSMArena phone compare, versus.com).

    Item names come from the page title ('Compare A vs. B vs. C'); attribute
    rows may be split across many per-category <table>s. Each data row looks like
    ``[<optional category>, <attr label>, value_1, value_2, ... value_N]``.
    """
    soup = BeautifulSoup(html, "html.parser")
    names = _names_from_title(soup)

    tables = soup.find_all("table")
    all_rows: List[List[str]] = []
    for table in tables:
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if any(cells):
                all_rows.append(cells)
    if not all_rows:
        return []

    # Item count N: trust the title if it gave names, else infer from the most
    # common row width (label column + N value columns).
    from collections import Counter
    widths = Counter(len(r) for r in all_rows if len(r) >= 3)
    if names:
        n = len(names)
    elif widths:
        n = widths.most_common(1)[0][0] - 1
    else:
        return []
    if n < 2 or n > 12:
        return []
    if not names or len(names) != n:
        names = [f"Item {i + 1}" for i in range(n)]

    items: List[Dict[str, Any]] = [{"name": names[i], "attributes": {}} for i in range(n)]
    seen: Dict[str, int] = {}
    # Re-walk per table so we can prefix each attribute with its category section
    # header (GSMArena groups specs under Body / Display / Battery / …), yielding
    # readable factor names like "Body · Weight" instead of bare/duplicate "Type".
    for table in tables:
        cat_th = table.find("th")
        category = cat_th.get_text(" ", strip=True) if cat_th else ""
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < n + 1:
                continue
            values = cells[-n:]
            label = (cells[-(n + 1)] or "").strip()
            if not label or not any(v.strip() for v in values):
                continue
            if category and category.lower() != label.lower():
                label = f"{category} · {label}"
            if label in seen:
                seen[label] += 1
                label = f"{label} ({seen[label]})"      # disambiguate true repeats
            else:
                seen[label] = 1
            for i in range(n):
                v = values[i].strip()
                if v:
                    items[i]["attributes"][label] = v

    items = [it for it in items if len(it["attributes"]) >= 2]
    return items if len(items) >= 2 else []


def _is_low_quality(cands: List[Dict[str, Any]]) -> bool:
    """A standard table parse is 'low quality' when it found no real headers
    (keys are generic col0/col1…) or fewer than 2 items — a strong signal the
    page is a transposed/irregular comparison layout rather than a row-per-item
    table."""
    if not cands or len(cands) < 2:
        return True
    keys = set()
    for c in cands:
        keys.update((c.get("attributes") or {}).keys())
    if not keys:
        return True
    real = [k for k in keys if not _GENERIC_KEY_RE.match(str(k))]
    return len(real) < max(1, len(keys) // 2)


def parse_hierarchy(html: str) -> Optional[Dict[str, Any]]:
    """Parse a category-grouped comparison matrix (e.g. GSMArena) into a TWO-LEVEL
    structure: each <table> is a category section (its <th> = category name) and
    its rows are sub-specs. Returns::

        {"items": [name, ...],            # compared items (columns, from <title>)
         "groups": [{"category": str,     # e.g. "Body"
                     "rows": [{"label": str,            # e.g. "Weight"
                               "values": [v1, v2, ...]} # one per item
                              ]}]}

    Returns None when the page is not a multi-category comparison matrix.
    """
    soup = BeautifulSoup(html, "html.parser")
    names = _names_from_title(soup)
    tables = soup.find_all("table")
    if not tables:
        return None

    # Determine item count N (columns) from the title, else the common row width.
    from collections import Counter
    widths = Counter(
        len(tr.find_all(["td", "th"]))
        for t in tables for tr in t.find_all("tr")
        if len(tr.find_all(["td", "th"])) >= 3
    )
    if names:
        n = len(names)
    elif widths:
        n = widths.most_common(1)[0][0] - 1
    else:
        return None
    if n < 2 or n > 12:
        return None
    if not names or len(names) != n:
        names = [f"Item {i + 1}" for i in range(n)]

    groups: List[Dict[str, Any]] = []
    for table in tables:
        cat_th = table.find("th")
        category = (cat_th.get_text(" ", strip=True) if cat_th else "").strip()
        if not category:
            continue
        rows: List[Dict[str, Any]] = []
        seen_lbl: Dict[str, int] = {}
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < n + 1:
                continue
            values = [v.strip() for v in cells[-n:]]
            label = (cells[-(n + 1)] or "").strip()
            if not label or label.lower() == category.lower() or not any(values):
                continue
            if label in seen_lbl:
                seen_lbl[label] += 1
                label = f"{label} ({seen_lbl[label]})"
            else:
                seen_lbl[label] = 1
            rows.append({"label": label, "values": values})
        if rows:
            groups.append({"category": category, "rows": rows})

    if len(groups) < 2:
        return None
    return {"items": names, "groups": groups}


async def crawl_hierarchy(url: str) -> Optional[Dict[str, Any]]:
    """Fetch `url` and return its two-level comparison hierarchy, or None if the
    page is not a category-grouped comparison matrix."""
    r = await _fetch_html(url)
    if "json" in r.headers.get("content-type", ""):
        return None
    return parse_hierarchy(r.text)




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


# ── AI conversation share-links (ChatGPT / Claude / Gemini) ──────────────
# These pages render the conversation client-side from an embedded data
# stream, so the visible DOM is nearly empty and the comparison-table parsers
# find nothing. We recover the message bodies from the embedded escaped-string
# literals and let an LLM pull the decision's factors + options.
_CONVERSATION_HOSTS = ("chatgpt.com", "chat.openai.com", "claude.ai",
                       "gemini.google.com", "g.co", "poe.com")


def is_conversation_url(url: str) -> bool:
    u = (url or "").lower()
    if not any(h in u for h in _CONVERSATION_HOSTS):
        return False
    return ("/share/" in u) or ("/c/" in u) or ("/g/" in u)


def _decode_rr_stream(html: str) -> str:
    """React Router v7 (used by chatgpt.com share pages, 2025+) streams its
    loader data via ``window.__reactRouterContext.streamController.enqueue("…")``.
    The FULL conversation lives there. Concatenate + JS-unescape every enqueued
    chunk into one clean string ('' when the page is not React-Router based)."""
    chunks: List[str] = []
    needle = "streamController.enqueue("
    i = 0
    while True:
        j = html.find(needle, i)
        if j < 0:
            break
        k = j + len(needle)
        if k >= len(html) or html[k] not in "\"'":
            i = k
            continue
        q = html[k]
        k += 1
        buf: List[str] = []
        while k < len(html):
            ch = html[k]
            if ch == "\\":
                buf.append(html[k:k + 2])
                k += 2
                continue
            if ch == q:
                break
            buf.append(ch)
            k += 1
        literal = "".join(buf)
        try:
            chunks.append(json.loads('"' + literal + '"'))
        except Exception:
            try:
                chunks.append(literal.encode().decode("unicode_escape", "ignore"))
            except Exception:
                pass
        i = k + 1
    return "\n".join(chunks)


_PARTS_RE = re.compile(r'"content_type","(?:text|multimodal_text)","parts",\[[\d,\s]*\],')
_ROLE_RE = re.compile(r'"role","(user|assistant|system|tool)"')
_JSTR_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _messages_from_rr_stream(stream: str) -> List[str]:
    """Pull each user/assistant TEXT message body (with its role) from a decoded
    ChatGPT React-Router stream, in document order. Targets the
    ``"content_type":"text","parts":[…],"<body>"`` shape so it never picks up the
    page's UI/system-prompt template strings."""
    out: List[str] = []
    for m in _PARTS_RE.finditer(stream):
        p = m.end()
        texts: List[str] = []
        while p < len(stream) and stream[p] == '"':
            sm = _JSTR_RE.match(stream, p)
            if not sm:
                break
            try:
                txt = json.loads('"' + sm.group(1) + '"')
            except Exception:
                txt = sm.group(1)
            if txt.strip():
                texts.append(txt)
            p = sm.end()
            if p < len(stream) and stream[p] == ",":
                p += 1
            else:
                break
        if not texts:
            continue
        body = "\n".join(texts).strip()
        if len(body) < 2:
            continue
        rm = _ROLE_RE.search(stream, m.end(), m.end() + len(body) + 3000)
        role = rm.group(1) if rm else "assistant"
        if role in ("system", "tool"):
            continue
        out.append(f"{role.upper()}: {body}")
    return out


def extract_conversation_text(html: str) -> str:
    """Recover human-readable conversation text from an AI share page.

    PRIMARY (ChatGPT share pages, React-Router SSR): decode the
    ``streamController.enqueue(...)`` loader stream and pull message bodies with
    roles — avoids the JS-bundle template/system strings a naive string-split
    grabs (which previously made every import fail with "no factors/options").

    FALLBACK (older formats / Claude / Gemini): legacy escaped-literal heuristic,
    then visible DOM text."""
    import codecs
    # 1) React Router stream (chatgpt.com share, 2025+ turbo-stream format)
    stream = _decode_rr_stream(html)
    if stream:
        msgs = _messages_from_rr_stream(stream)
        if msgs:
            return "\n\n".join(msgs)[:16000]

    # 2) Legacy heuristic: escaped-string literals (older share formats)
    out: List[str] = []
    seen: set = set()
    for seg in html.split('\\"'):
        if len(seg) < 45 or " " not in seg:
            continue
        if "<" in seg or "://" in seg or "href" in seg or "rel=" in seg or "charset" in seg:
            continue
        letters = sum(c.isalpha() for c in seg)
        if letters / max(1, len(seg)) < 0.6:
            continue
        s = seg.replace("\\n", "\n").replace("\\t", " ")
        try:
            s = codecs.decode(s, "unicode_escape").encode("latin-1").decode("utf-8")
        except Exception:
            pass
        k = s[:48].strip().lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(s.strip())
    text = "\n\n".join(out)
    if len(text) < 200:
        soup = BeautifulSoup(html, "html.parser")
        for t in soup(["script", "style", "noscript", "svg"]):
            t.decompose()
        text = re.sub(r"\n{2,}", "\n", soup.get_text("\n", strip=True))
    return text[:16000]


async def ai_extract_decision_from_conversation(user_id: str, text: str) -> Dict[str, List[str]]:
    """LLM: from a decision-making chat, pull the comparison OPTIONS and the
    FACTORS/criteria. Returns {"factors": [...], "options": [...]}. Metered."""
    if not has_any_llm() or len(text) < 50:
        return {"factors": [], "options": []}
    sys = (
        "You are reading a chat conversation in which someone works through a real decision. "
        "Identify (1) the DECISION OPTIONS — the choices/alternatives being compared "
        "(e.g. specific companies, investors, products, candidates, or paths), and "
        "(2) the FACTORS — the criteria used to compare them (e.g. price, ticket size, fit, stage). "
        'Reply with ONLY compact JSON: {"factors":["..."],"options":["..."]} . '
        "Use the exact short names used in the chat. Max 15 factors and 24 options. No prose."
    )
    try:
        out = await metered_chat(user_id, system_message=sys, prompt=text,
                                 feature="url_analyze_conversation", session_prefix="urlconv")
        m = re.search(r"\{.*\}", out, re.S)
        data = json.loads(m.group(0)) if m else {}
        f = [str(x).strip() for x in (data.get("factors") or []) if str(x).strip()][:15]
        o = [str(x).strip() for x in (data.get("options") or []) if str(x).strip()][:24]
        return {"factors": f, "options": o}
    except Exception as e:
        logger.warning("conversation extraction failed: %s", str(e)[:120])
        return {"factors": [], "options": []}



def _scraperapi_reason(status: int, body: str) -> str:
    """Map a failed ScraperAPI response to a human-readable admin-facing reason."""
    low = (body or "").lower()
    if status == 500 and "premium" in low:
        return ("this domain is bot-protected and needs ScraperAPI Premium/Ultra-Premium "
                "proxies (premium=true)")
    if status == 403 and ("plan" in low or "upgrade" in low):
        return ("your ScraperAPI plan does not include Premium proxies — protected domains "
                "need a plan upgrade at scraperapi.com")
    if status == 403:
        return "ScraperAPI rejected the request (invalid API key or out of credits)"
    if status == 429:
        return "ScraperAPI rate/credit limit reached"
    return f"ScraperAPI returned HTTP {status}"


async def _scraperapi_fetch(url: str, sc: Dict[str, str],
                            user_id: Optional[str] = None) -> tuple:
    """Fetch fully-rendered HTML via ScraperAPI (JS execution + proxy rotation).
    Auto-escalates ONCE to premium=true when ScraperAPI flags the domain as
    protected. Successful fetches are METERED to the user's wallet when
    `user_id` is given. Returns (html, None) on success, else (None, fail_reason)."""
    params = {"api_key": sc["api_key"], "url": url, "render": "true"}
    if sc.get("country_code"):
        params["country_code"] = sc["country_code"]
    reason = "unknown error"
    for extra in ({}, {"premium": "true"}):
        try:
            async with httpx.AsyncClient(timeout=75.0, follow_redirects=True) as cli:
                r = await cli.get("https://api.scraperapi.com/", params={**params, **extra})
            if r.status_code == 200 and "<html" in r.text.lower():
                if extra:
                    logger.info("ScraperAPI premium=true succeeded for %s", url[:80])
                if user_id:
                    await scrape_meter.charge_scrape(
                        user_id, url, "premium_render" if extra else "render")
                return r.text, None
            body = " ".join(r.text[:300].split())
            reason = _scraperapi_reason(r.status_code, body)
            logger.warning("ScraperAPI %s for %s%s: %s", r.status_code, url[:80],
                           " (premium retry)" if extra else "", body[:200])
            # Protected-domain hint → retry once with premium proxies; else stop.
            if not (r.status_code == 500 and "premium" in r.text.lower()):
                break
        except Exception as e:
            reason = f"ScraperAPI request failed ({type(e).__name__})"
            logger.warning("ScraperAPI fetch failed for %s: %s", url[:80], str(e)[:120])
            break
    return None, reason


_PRICE_RE = re.compile(r"[₹$€£]\s?[\d,]+(?:\.\d{1,2})?")
_RATING_RE = re.compile(r"([\d.]+)\s*out of", re.I)


def _product_grid_candidates(html: str) -> List[Dict[str, Any]]:
    """Extract products from an e-commerce SEARCH/listing GRID (Amazon-style
    cards, or schema.org Product items) → name + Price + Rating. Deterministic,
    so it works without any LLM. Returns [] when the page isn't a product grid."""
    soup = BeautifulSoup(html, "html.parser")
    items: List[Dict[str, Any]] = []
    seen: set = set()

    # Amazon search results: each card carries a data-asin attribute.
    cards = [c for c in soup.select("div[data-asin]") if (c.get("data-asin") or "").strip()]
    # Generic schema.org fallback when there are no Amazon cards.
    if len(cards) < 2:
        cards = soup.select('[itemtype*="schema.org/Product"], li.product, div.product')

    for c in cards:
        title = ""
        h2 = c.select_one("h2")
        if h2:
            title = h2.get_text(" ", strip=True)
        if not title:
            img = c.select_one("img[alt]")
            title = (img.get("alt") or "").strip() if img else ""
        title = title.strip()
        if len(title) < 3:
            continue
        key = title.lower()[:80]
        if key in seen:
            continue

        attrs: Dict[str, Any] = {}
        price_el = c.select_one(".a-price .a-offscreen") or c.select_one(".a-price") or c.select_one('[class*="price"]')
        if price_el:
            pm = _PRICE_RE.search(price_el.get_text(" ", strip=True))
            if pm:
                attrs["Price"] = pm.group(0)
        rating_el = c.select_one(".a-icon-alt") or c.select_one('[class*="rating"]')
        if rating_el:
            rm = _RATING_RE.search(rating_el.get_text(" ", strip=True))
            if rm:
                attrs["Rating"] = rm.group(1)

        if attrs:  # only keep cards we could actually read a comparable value from
            seen.add(key)
            items.append({"name": title[:120], "attributes": attrs})
        if len(items) >= 24:
            break

    return items if len(items) >= 2 else []


async def _fetch_html(url: str, user_id: Optional[str] = None) -> "httpx.Response":
    """Fetch `url` with browser headers + retry on bot-block codes. When a
    ScraperAPI key is configured it is used for JS-heavy domains and as an
    escalation when a direct fetch is bot-blocked. ScraperAPI fetches are
    gated + metered to the user's wallet when `user_id` is given. Raises a
    user-friendly HTTPException on failure. Shared by flat + hierarchical crawls."""
    url = (url or "").strip()
    if not url or not re.match(r"^https?://", url, re.I):
        raise HTTPException(400, "Enter a valid http(s) URL.")

    sc = await resolve_scraperapi()
    js_heavy = any(d in url.lower() for d in _JS_HEAVY_DOMAINS)
    sc_reason: Optional[str] = None  # why ScraperAPI failed (when configured)

    # 1) JS-heavy site + key → go straight to ScraperAPI (direct fetch is useless).
    if sc["api_key"] and js_heavy:
        if user_id:
            await scrape_meter.ensure_can_scrape(user_id)  # raises InsufficientCredits
        html, sc_reason = await _scraperapi_fetch(url, sc, user_id=user_id)
        if html:
            return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    # 2) Direct fetch with browser headers + backoff on transient throttling.
    r = None
    last_err: Optional[Exception] = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True,
                                         headers=_BROWSER_HEADERS) as cli:
                r = await cli.get(url)
            if r.status_code not in _BOT_BLOCK_CODES:
                break
        except Exception as e:
            last_err = e
            r = None
        if attempt < 2:
            await asyncio.sleep(0.8 * (attempt + 1))

    # 3) Bot-blocked (or unreachable) + key → escalate to ScraperAPI.
    if (r is None or r.status_code in _BOT_BLOCK_CODES) and sc["api_key"] and not sc_reason:
        if user_id:
            await scrape_meter.ensure_can_scrape(user_id)  # raises InsufficientCredits
        html, sc_reason = await _scraperapi_fetch(url, sc, user_id=user_id)
        if html:
            return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    if r is None:
        raise HTTPException(
            400,
            f"Could not reach the URL ({type(last_err).__name__ if last_err else 'network error'}). "
            "Check the link is public and reachable.",
        )
    if r.status_code in _BOT_BLOCK_CODES:
        if sc["api_key"]:
            # ScraperAPI IS configured but it also failed — tell the admin WHY.
            raise HTTPException(
                422,
                f"This site blocked automated access (HTTP {r.status_code}), and the configured "
                f"ScraperAPI fallback also failed — {sc_reason or 'no usable HTML returned'}. "
                "Try a public comparison/listing page that shows items in a plain table, or the "
                "Screener (CSV upload).",
            )
        raise HTTPException(
            422,
            f"This site blocked automated access (HTTP {r.status_code}). Large retail/JS-heavy "
            "sites like Amazon, Flipkart or Google often reject crawlers — configure ScraperAPI in "
            "Admin → Integrations to import from those, or try a public comparison/listing page "
            "that shows items in a plain table, or the Screener (CSV upload).",
        )
    if r.status_code >= 400:
        raise HTTPException(422, f"URL fetch failed (HTTP {r.status_code}). The page may be private or removed.")
    return r


async def fetch_page(url: str, user_id: Optional[str] = None) -> "httpx.Response":
    """Public alias for the shared fetch (browser headers + ScraperAPI
    escalation) — lets routes fetch ONCE and run multiple parse strategies.
    Pass `user_id` so any ScraperAPI fetch is gated + metered to the wallet."""
    return await _fetch_html(url, user_id=user_id)


async def fetch_rendered(url: str, user_id: Optional[str] = None) -> Optional[str]:
    """Best-effort fully-RENDERED HTML via ScraperAPI (when configured).
    Used for single-item DETAIL pages whose 'Similar items' rails are loaded
    by JavaScript and therefore missing from the server-rendered HTML.
    Gated + metered to the user's wallet when `user_id` is given."""
    sc = await resolve_scraperapi()
    if not sc["api_key"]:
        return None
    if user_id:
        await scrape_meter.ensure_can_scrape(user_id)  # raises InsufficientCredits
    html, _reason = await _scraperapi_fetch(url, sc, user_id=user_id)
    return html


def page_text(html: str, limit: int = 11000) -> str:
    """Visible page text PLUS any JSON-LD structured-data blocks (many listing
    sites embed rich item data there). Script/style noise stripped."""
    soup = BeautifulSoup(html, "html.parser")
    ld_blocks = [s.get_text() for s in soup.find_all("script", type="application/ld+json")][:3]
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = re.sub(r"\n{2,}", "\n", soup.get_text("\n", strip=True))[:limit]
    extra = "\n".join(b.strip()[:2000] for b in ld_blocks if b and len(b.strip()) > 40)
    if extra:
        text += "\nSTRUCTURED DATA (JSON-LD):\n" + extra[: max(0, limit + 4000 - len(text))]
    return text


def deterministic_candidates(html: str, name_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """All NON-LLM html parse strategies in priority order. May return a
    low-quality (or empty) list — callers decide whether to escalate to AI."""
    rows = _html_table_rows(html)
    std_cands = _rows_to_candidates(rows, name_key) if rows else []
    # Good standard (row-per-item) table → use it directly.
    if std_cands and not _is_low_quality(std_cands):
        return std_cands

    # Transposed comparison matrix (items as COLUMNS — e.g. GSMArena, versus.com).
    matrix_cands = _comparison_matrix_candidates(html)
    if matrix_cands:
        return matrix_cands

    # E-commerce product GRID (Amazon-style cards) → name + Price + Rating. No LLM.
    grid_cands = _product_grid_candidates(html)
    if grid_cands:
        return grid_cands

    return std_cands  # low quality or []


async def candidates_from_response(r: "httpx.Response", user_id: str,
                                   name_key: Optional[str] = None,
                                   allow_ai: bool = True) -> List[Dict[str, Any]]:
    """Candidate extraction from an already-fetched response. Returns [] (never
    raises) so callers can chain further strategies (e.g. detail-page import)."""
    ctype = r.headers.get("content-type", "")
    if "json" in ctype:
        try:
            data = r.json()
        except Exception:
            data = None
        return _rows_to_candidates(data, name_key) if isinstance(data, list) else []

    cands = deterministic_candidates(r.text, name_key)
    if cands and not _is_low_quality(cands):
        return cands

    if allow_ai:
        ai_rows = await ai_extract_candidates(user_id, r.text)
        if ai_rows:
            got = _rows_to_candidates(ai_rows, name_key)
            if got:
                return got
    return cands  # low quality or []


async def crawl_candidates(url: str, user_id: str, name_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch `url` and return a normalised candidate list. Raises HTTPException
    with a user-friendly message on failure."""
    r = await _fetch_html(url, user_id=user_id)
    cands = await candidates_from_response(r, user_id, name_key)
    if cands:
        return cands
    if "json" in r.headers.get("content-type", ""):
        raise HTTPException(422, "The JSON URL did not yield a usable list of items.")
    raise HTTPException(
        422,
        "Could not extract a comparable list from this page. The page may load its items "
        "via JavaScript (which we can't render) or have no clean table. Try a comparison/filter "
        "page that lists items in a table, a JSON/API endpoint, or use the Screener CSV upload.",
    )
