"""Regression tests for the "AI Assess All" batched scorer (core.ai_assess).

Covers the production escalation where cells were left empty even though AI
credits were consumed:
  * Prompts must NEVER be truncated — chunks are built to fit the JSON budget.
  * Cells the LLM drops/malforms get ONE automatic retry pass.
  * out_of_credits mid-run stops cleanly and surfaces to the client.

Run: cd /app/backend && python -m pytest tests/test_batch_assess.py -q
"""
import asyncio
import json
from unittest.mock import patch

import pytest

from core import ai_assess


def _mk_decision(n_factors=5, n_options=2):
    return {
        "title": "T", "context": "C",
        "factors": [
            {"id": f"f{i}", "name": f"Factor {i}", "expected_value": "good",
             "factor_type": "qualitative", "data_type": "text"}
            for i in range(n_factors)
        ],
        "options": [
            {"id": f"o{j}", "name": f"Opt{j}", "assessments": []}
            for j in range(n_options)
        ],
    }


def _mk_cells(decision):
    return [
        {"option_id": o["id"], "factor_id": f["id"]}
        for o in decision["options"] for f in decision["factors"]
    ]


def test_chunk_work_respects_budget_and_cap():
    """Long factor/option names must produce MORE chunks, never a truncated prompt."""
    work = [
        dict(cell={"option_id": f"o{i % 3}", "factor_id": f"f{i // 3}"},
             fname="Factor " + "X" * 200, ftype="qualitative",
             expected="good " + "Y" * 200, operator=None, unit=None,
             oname="Option " + "Z" * 100, actual=None)
        for i in range(120)
    ]
    chunks = ai_assess._chunk_work(work, ai_assess._BATCH_CHUNK)
    assert sum(len(c) for c in chunks) == 120
    for c in chunks:
        assert len(c) <= ai_assess._BATCH_CHUNK
        items = [ai_assess._work_item(i, w) for i, w in enumerate(c)]
        assert len(json.dumps(items, ensure_ascii=False)) <= ai_assess._BATCH_JSON_BUDGET + 300


def test_retry_pass_recovers_dropped_cells():
    """If the LLM skips indices on the first call, the retry pass must score them."""
    decision = _mk_decision()
    cells = _mk_cells(decision)
    calls = {"n": 0}

    async def fake_chat(user_id, system_message, prompt, feature, session_prefix, allow_openai=None):
        calls["n"] += 1
        items = json.loads(prompt.split("Items (JSON):\n")[1].split("\nReturn ONLY")[0])
        if calls["n"] == 1:
            items = items[:-3]  # simulate the LLM dropping the last 3 cells
        return json.dumps({str(it["i"]): {"pct": 75, "actual": "inferred"} for it in items})

    async def run():
        with patch.object(ai_assess.ai_metering, "metered_chat", side_effect=fake_chat):
            return await ai_assess.batch_score_cells(
                decision=decision, cells=cells, user_id="u1", force_fill=True)

    results, ooc, unavail = asyncio.run(run())
    assert len([r for r in results if r["status"] == "done"]) == len(cells)
    assert calls["n"] == 2  # initial + ONE retry
    assert not ooc and not unavail


def test_out_of_credits_surfaces_and_marks_remaining():
    decision = _mk_decision()
    cells = _mk_cells(decision)

    async def broke_chat(*a, **k):
        raise ai_assess.ai_wallet.InsufficientCredits("no credits")

    async def run():
        with patch.object(ai_assess.ai_metering, "metered_chat", side_effect=broke_chat):
            return await ai_assess.batch_score_cells(
                decision=decision, cells=cells, user_id="u1", force_fill=True)

    results, ooc, unavail = asyncio.run(run())
    assert ooc is True
    assert all(r["status"] == "error" for r in results)


def test_parse_failure_chunk_is_retried_not_hard_errored():
    """A garbage first response must NOT permanently error the chunk."""
    decision = _mk_decision()
    cells = _mk_cells(decision)
    calls = {"n": 0}

    async def flaky_chat(user_id, system_message, prompt, feature, session_prefix, allow_openai=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return "Sorry, I can't do that."  # unparseable
        items = json.loads(prompt.split("Items (JSON):\n")[1].split("\nReturn ONLY")[0])
        return json.dumps({str(it["i"]): {"pct": 60, "actual": "ok"} for it in items})

    async def run():
        with patch.object(ai_assess.ai_metering, "metered_chat", side_effect=flaky_chat):
            return await ai_assess.batch_score_cells(
                decision=decision, cells=cells, user_id="u1", force_fill=True)

    results, ooc, unavail = asyncio.run(run())
    assert len([r for r in results if r["status"] == "done"]) == len(cells)
    assert not ooc and not unavail
