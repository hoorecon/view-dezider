"""Regression: ChatGPT share-link conversation extraction (React-Router stream).

The bug: chatgpt.com share pages moved to a React-Router turbo-stream payload,
so the old escaped-quote splitter scraped the page's JS-bundle UI/system-prompt
strings instead of the actual chat -> the import endpoint always 422'd with
"Couldn't find clear decision factors/options in this conversation".

These tests assert the extractor now recovers the REAL message bodies.
Network-dependent (fetches a live public share URL); skipped if unreachable.
"""
import sys
import pytest

sys.path.insert(0, "/app/backend")

from core.url_crawl import (  # noqa: E402
    extract_conversation_text,
    is_conversation_url,
    _BROWSER_HEADERS,
)

SHARE_URL = "https://chatgpt.com/share/6a36d8d2-3b08-83e8-b67a-6dffa9cc9ffa"


def _fetch(url: str) -> str:
    import httpx
    try:
        with httpx.Client(timeout=25, follow_redirects=True, headers=_BROWSER_HEADERS) as c:
            r = c.get(url)
        if r.status_code != 200 or len(r.text) < 1000:
            return ""
        return r.text
    except Exception:
        return ""


def test_is_conversation_url():
    assert is_conversation_url(SHARE_URL) is True
    assert is_conversation_url("https://example.com/page") is False


def test_chatgpt_share_extracts_real_conversation():
    html = _fetch(SHARE_URL)
    if not html:
        pytest.skip("ChatGPT share URL unreachable from CI")
    conv = extract_conversation_text(html)
    assert len(conv) > 500, "extractor returned too little text"
    # The real assistant message lists these investor options.
    assert "Java Capital" in conv
    assert "Chiratae Ventures" in conv
    # Must be tagged with a role (proves structured extraction, not junk).
    assert ("ASSISTANT:" in conv) or ("USER:" in conv)
    # Must NOT contain the JS-bundle UI/system-prompt junk the old code grabbed.
    assert "Please make this response more concise" not in conv
    assert "starts using Codex" not in conv
