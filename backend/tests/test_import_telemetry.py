"""Regression tests for Import-URL telemetry + page-type classification.

Covers: heuristic classifier fallback, page-type prompt specialisation blocks,
telemetry record/feedback/purge lifecycle and admin aggregations.
Run: cd /app/backend && python -m pytest tests/test_import_telemetry.py -q
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, "/app/backend")

from core.url_pagetype import PAGE_TYPES, heuristic_page_type  # noqa: E402
from core.url_detail import PAGE_TYPE_GUIDANCE, DETAIL_SYSTEM  # noqa: E402
from core import url_telemetry  # noqa: E402


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestHeuristicClassifier:
    def test_compare_page(self):
        html = "<title>Phone A vs Phone B comparison</title><table><tr><td>x</td></tr></table>"
        assert heuristic_page_type(html) == "comparison_matrix"

    def test_listing_filter_page(self):
        html = "<title>Best Electric Cars Under 10 Lakh in India</title><p>list</p>"
        assert heuristic_page_type(html) == "listing_filter"

    def test_detail_default(self):
        html = "<title>Tata Tiago EV XT — On-road price</title><p>specs</p>"
        assert heuristic_page_type(html) == "detail"


class TestPromptSpecialisation:
    def test_guidance_exists_for_all_five_types(self):
        assert set(PAGE_TYPE_GUIDANCE.keys()) == set(PAGE_TYPES)
        for block in PAGE_TYPE_GUIDANCE.values():
            assert "PAGE-TYPE GUIDANCE" in block

    def test_prompt_has_injection_point(self):
        assert "{page_guidance}" in DETAIL_SYSTEM


@pytest.fixture()
def tel():
    return url_telemetry.new_tel("test-user-telemetry", endpoint="import",
                                 url="https://example.com/x", ai_tier="precise",
                                 hints={"expected_factor_count": 6},
                                 decision_id="dec-1")


class TestTelemetryLifecycle:
    def test_record_run_and_feedback_and_purge(self, tel):
        async def flow():
            tel["page_type"] = "listing_filter"
            tel["page_type_confidence"] = 0.9
            tel["route"] = "ai_extraction"
            tel["ai"] = {"provider": "emergent_precise", "retry_used": False, "attempts": 1,
                         "tokens": 1234, "system_prompt": "SYS" * 9000,  # > TRUNC
                         "prompt_text": "PROMPT", "raw_response": "{}"}
            run_id = await url_telemetry.record_run(
                tel, status="success",
                response={"mode": "detail", "factors_added": 6, "options_added": 4,
                          "item_count": 4, "hint_warnings": [], "ai_provider": "emergent_precise"})
            from core.database import db
            doc = await db.url_import_runs.find_one({"id": run_id})
            assert doc and doc["page_type"] == "listing_filter"
            assert doc["route"] == "ai_extraction" and doc["hint_pass"] is True
            assert doc["ai_tokens"] == 1234
            assert doc["ai_system_prompt"].endswith("…[truncated]")  # 15KB cap applied
            assert len(doc["ai_system_prompt"]) <= url_telemetry.TRUNC + 20

            # 👍 feedback — owner only
            assert await url_telemetry.set_feedback(run_id, "someone-else", "up") is False
            assert await url_telemetry.set_feedback(run_id, "test-user-telemetry", "up") is True
            doc = await db.url_import_runs.find_one({"id": run_id})
            assert doc["feedback"] == "up"

            # purge: backdate the run beyond retention, trigger lazy purge
            await db.url_import_runs.update_one(
                {"id": run_id},
                {"$set": {"ts": datetime.now(timezone.utc) - timedelta(days=url_telemetry.PURGE_DAYS + 1)}})
            await url_telemetry._lazy_purge(datetime.now(timezone.utc))
            doc = await db.url_import_runs.find_one({"id": run_id})
            assert "ai_system_prompt" not in doc and doc.get("bodies_purged") is True
            assert doc["feedback"] == "up"  # metadata retained

            # summary aggregation sees the run (within 365d window)
            s = await url_telemetry.summary(days=365)
            assert s["total_runs"] >= 1
            assert any(b["key"] == "listing_filter" for b in s["by_page_type"])

            await db.url_import_runs.delete_one({"id": run_id})  # cleanup
        _run(flow())

    def test_error_run_recorded(self, tel):
        async def flow():
            run_id = await url_telemetry.record_run(tel, status="error", error="HTTP 422: boom")
            from core.database import db
            doc = await db.url_import_runs.find_one({"id": run_id})
            assert doc["status"] == "error" and "boom" in doc["error"]
            assert doc["hint_pass"] is None  # errors never count as hint-pass
            await db.url_import_runs.delete_one({"id": run_id})
        _run(flow())
