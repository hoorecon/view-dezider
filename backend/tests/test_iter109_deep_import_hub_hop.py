"""Iteration 109 — Deep Import two-hop discovery (homepage/portal base URLs).

Covers the fix for: Deep Import failed on https://www.nobroker.in/ because the
homepage links to LISTING hub pages, not option detail pages, and the first
150 extracted links were irrelevant footer links.

Unit tests (no network, AI mocked):
  1. _rank_links surfaces context-relevant links above unrelated ones.
  2. _extract_links honours the raised cap and same-domain rule.
  3. _pick_hubs validates AI output: same-domain only, relative resolved,
     base URL and duplicates dropped, foreign domains rejected.
  4. _pick_detail_links dedupes urls and caps at max_pages.
  5. Prompts: LINKS_SYSTEM forbids hub pages; HUBS_SYSTEM exists.
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routes import deep_import as di  # noqa: E402

def _run(coro):
    """Repo-wide test convention: persistent shared event loop
    (asyncio.run would close loops and break sibling suites)."""
    return asyncio.get_event_loop().run_until_complete(coro)


CTX = "Choose best 2 BHK Flat for Rent in Chennai Mugappair area"


# ── 1. relevance ranking ─────────────────────────────────────────────────────
def test_rank_links_surfaces_context_links():
    links = (
        [{"text": f"Flats for Sale in Bangalore {i}",
          "url": f"https://www.nobroker.in/flats-for-sale-in-bangalore-{i}"} for i in range(200)]
        + [{"text": "2 BHK House for Rent in Chennai",
            "url": "https://www.nobroker.in/2-bhk-house-for-rent-in-chennai-chennai"},
           {"text": "Flats for Rent in Chennai",
            "url": "https://www.nobroker.in/flats-for-rent-in-chennai_chennai"}]
    )
    ranked = di._rank_links(links, CTX, cap=150)
    assert ranked[0]["text"] == "2 BHK House for Rent in Chennai"
    assert ranked[1]["text"] == "Flats for Rent in Chennai"
    assert len(ranked) == 150


def test_rank_links_no_context_keeps_order():
    links = [{"text": f"L{i}", "url": f"https://x.com/{i}"} for i in range(10)]
    assert di._rank_links(links, "a an", cap=5) == links[:5]


# ── 2. link extraction cap + same-domain ────────────────────────────────────
def test_extract_links_cap_and_domain():
    html = "".join(
        f'<a href="/page-{i}">Internal page {i}</a>' for i in range(700)
    ) + '<a href="https://evil.com/x">External link text</a>'
    out = di._extract_links(html, "https://www.nobroker.in/")
    assert len(out) == 600  # raised cap
    assert all("nobroker.in" in l["url"] for l in out)


# ── 3. hub validation ────────────────────────────────────────────────────────
def test_pick_hubs_validates_urls():
    ai_reply = ('{"hubs":["https://www.nobroker.in/flats-for-rent-in-chennai_chennai",'
                '"/properties-for-rent-in-mogappair-chennai",'
                '"https://evil.com/steal",'
                '"https://www.nobroker.in/flats-for-rent-in-chennai_chennai",'
                '"https://www.nobroker.in/"]}')
    with patch.object(di, "metered_chat", AsyncMock(return_value=ai_reply)):
        hubs = _run(di._pick_hubs("u1", CTX, "https://www.nobroker.in/", "text", []))
    assert hubs == [
        "https://www.nobroker.in/flats-for-rent-in-chennai_chennai",
        "https://www.nobroker.in/properties-for-rent-in-mogappair-chennai",
    ]  # foreign domain, duplicate and base-url itself dropped; relative resolved


def test_pick_hubs_accepts_dict_items_and_empty():
    with patch.object(di, "metered_chat", AsyncMock(return_value='{"hubs":[{"url":"/rent-chennai"}]}')):
        hubs = _run(di._pick_hubs("u1", CTX, "https://www.nobroker.in/", "t", []))
    assert hubs == ["https://www.nobroker.in/rent-chennai"]
    with patch.object(di, "metered_chat", AsyncMock(return_value='{"hubs":[]}')):
        assert _run(di._pick_hubs("u1", CTX, "https://www.nobroker.in/", "t", [])) == []


# ── 4. detail-link picking: dedupe + cap ─────────────────────────────────────
def test_pick_detail_links_dedupes_and_caps():
    opts = ",".join(
        f'{{"name":"Flat {i}","url":"https://www.nobroker.in/property/flat-{i % 3}/detail"}}'
        for i in range(8)
    )
    with patch.object(di, "metered_chat", AsyncMock(return_value=f'{{"options":[{opts}]}}')):
        out = _run(di._pick_detail_links("u1", CTX, 5, "text", []))
    assert len(out) == 3  # 8 entries but only 3 unique urls
    assert len({o["url"] for o in out}) == 3


def test_pick_detail_links_empty_on_garbage():
    with patch.object(di, "metered_chat", AsyncMock(return_value="no json here")):
        assert _run(di._pick_detail_links("u1", CTX, 5, "t", [])) == []


# ── 5. prompt contracts ──────────────────────────────────────────────────────
def test_prompts_enforce_two_hop_contract():
    assert "STRICTLY EXCLUDE" in di.LINKS_SYSTEM           # hubs are not options
    assert "ONE specific item" in di.LINKS_SYSTEM
    assert '{"hubs":' in di.HUBS_SYSTEM                    # hub-hop prompt exists
    assert "same domain" in di.HUBS_SYSTEM
