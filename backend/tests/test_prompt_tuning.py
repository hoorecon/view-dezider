"""Regression tests for the AI Auto-Tune prompt-suggestion loop.

Lifecycle: failing runs → suggestion (proposed) → approve → override ACTIVE in
get_active_guidance() → revert → built-in default again.
LLM generation itself is covered by the live e2e (not unit-tested here).
Run: cd /app/backend && python -m pytest tests/test_prompt_tuning.py -q
"""
import asyncio
import sys
import uuid
from datetime import datetime, timezone

import pytest

sys.path.insert(0, "/app/backend")

from core import url_prompt_tuning as tuning  # noqa: E402
from core.url_detail import PAGE_TYPE_GUIDANCE, get_active_guidance  # noqa: E402
from core.database import db  # noqa: E402


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


PT = "search_grid"  # use a page type unlikely to have real overrides in dev


@pytest.fixture(autouse=True)
def _clean():
    async def clean():
        await db.url_prompt_overrides.delete_many({"key": PT})
        await db.prompt_tuning_suggestions.delete_many({"page_type": PT})
    _run(clean())
    yield
    _run(clean())


def _fake_suggestion(status="proposed"):
    return {
        "id": uuid.uuid4().hex, "ts": datetime.now(timezone.utc), "page_type": PT,
        "status": status, "rationale": "cards mis-mapped", "expected_impact": "hint-pass up",
        "current_guidance": PAGE_TYPE_GUIDANCE[PT],
        "proposed_guidance": "\n\nPAGE-TYPE GUIDANCE — REVISED search grid rules:\n- options = cards only.",
        "evidence": {"run_ids": [], "failing_runs": 2, "window_days": 30},
        "created_by": "admin-x", "decided_by": None, "decided_at": None,
    }


class TestOverrideLifecycle:
    def test_default_guidance_when_no_override(self):
        assert _run(get_active_guidance(PT)) == PAGE_TYPE_GUIDANCE[PT]
        assert _run(get_active_guidance(None)) == ""
        assert _run(get_active_guidance("unknown_type")) == ""

    def test_approve_activates_override_and_revert_restores(self):
        async def flow():
            sug = _fake_suggestion()
            await db.prompt_tuning_suggestions.insert_one(dict(sug))
            decided = await tuning.decide(sug["id"], "admin-y", approve=True)
            assert decided["status"] == "approved"
            # Override is now LIVE in the extraction prompt path
            active = await get_active_guidance(PT)
            assert "REVISED search grid rules" in active
            ov = await tuning.get_override(PT)
            assert ov["suggestion_id"] == sug["id"] and ov["updated_by"] == "admin-y"
            # Revert → built-in default again
            assert await tuning.revert_override(PT, "admin-y") is True
            assert await get_active_guidance(PT) == PAGE_TYPE_GUIDANCE[PT]
            assert await tuning.revert_override(PT, "admin-y") is False  # idempotent
        _run(flow())

    def test_reject_does_not_activate(self):
        async def flow():
            sug = _fake_suggestion()
            await db.prompt_tuning_suggestions.insert_one(dict(sug))
            decided = await tuning.decide(sug["id"], "admin-y", approve=False)
            assert decided["status"] == "rejected"
            assert await tuning.get_override(PT) is None
            assert await get_active_guidance(PT) == PAGE_TYPE_GUIDANCE[PT]
        _run(flow())

    def test_double_decide_blocked(self):
        async def flow():
            sug = _fake_suggestion()
            await db.prompt_tuning_suggestions.insert_one(dict(sug))
            await tuning.decide(sug["id"], "a", approve=True)
            with pytest.raises(ValueError):
                await tuning.decide(sug["id"], "a", approve=False)
            with pytest.raises(KeyError):
                await tuning.decide("nope", "a", approve=True)
        _run(flow())


class TestEvidenceCollection:
    def test_failing_runs_query_targets_failures_only(self):
        async def flow():
            now = datetime.now(timezone.utc)
            good = {"id": uuid.uuid4().hex, "ts": now, "page_type": PT, "status": "success",
                    "hint_pass": True, "feedback": "up"}
            bad = {"id": uuid.uuid4().hex, "ts": now, "page_type": PT, "status": "success",
                   "hint_pass": False, "feedback": None, "hints": {"expected_factor_count": 6},
                   "hint_warnings": ["Found 2 factors but you said ~6."], "url": "https://x.example"}
            await db.url_import_runs.insert_many([dict(good), dict(bad)])
            runs = await tuning._failing_runs(PT, 7)
            ids = [r["id"] for r in runs]
            assert bad["id"] in ids and good["id"] not in ids
            text = tuning._evidence_text(runs)
            assert "Found 2 factors" in text and "x.example" in text
            await db.url_import_runs.delete_many({"id": {"$in": [good["id"], bad["id"]]}})
        _run(flow())


class TestGuidanceNormalization:
    def test_single_header_always(self):
        from core.url_prompt_tuning import _normalize_guidance
        cases = [
            "PAGE-TYPE GUIDANCE — rules here",                       # LLM includes header, no \n\n
            "\n\nPAGE-TYPE GUIDANCE — rules here",                    # already canonical
            "PAGE-TYPE GUIDANCE — PAGE-TYPE GUIDANCE — rules here",   # duplicated header
            "- rules here",                                           # no header at all
        ]
        for c in cases:
            out = _normalize_guidance(c)
            assert out.startswith("\n\nPAGE-TYPE GUIDANCE — "), repr(out)
            assert out.count("PAGE-TYPE GUIDANCE") == 1, repr(out)
            assert "rules here" in out
