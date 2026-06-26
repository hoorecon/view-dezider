"""Regression: Claude share-link conversation extraction.

Claude (claude.ai/share/<uuid>) renders client-side; the transcript lives at the
Cloudflare-gated chat_snapshots JSON API. fetch_ai_conversation fetches it via
ScraperAPI and joins the message blocks. Network + ScraperAPI dependent — skipped
if either is unavailable.
"""
import asyncio
import sys

import pytest

sys.path.insert(0, "/app/backend")

from core.url_crawl import fetch_ai_conversation, is_conversation_url  # noqa: E402

CLAUDE_URL = "https://claude.ai/share/4b324e58-3e3f-453a-8746-3af2b1a970e9"


def test_is_conversation_url_claude():
    assert is_conversation_url(CLAUDE_URL) is True


def test_claude_share_extracts_real_conversation():
    # user_id="" → skip wallet metering for the ScraperAPI fetch in CI.
    conv = asyncio.get_event_loop().run_until_complete(
        fetch_ai_conversation(CLAUDE_URL, ""))
    if not conv or len(conv) < 200:
        pytest.skip("Claude snapshot unreachable (ScraperAPI/network) from CI")
    # role-tagged structured output (not the thin page shell or junk)
    assert ("USER:" in conv) or ("ASSISTANT:" in conv)
    # the unsupported-block placeholder must be filtered out
    assert "not supported on your current device" not in conv
