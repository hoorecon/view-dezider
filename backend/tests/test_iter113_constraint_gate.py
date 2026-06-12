"""Iteration 113 — generic hard-constraint gate + cost-tuned prompts.

The gate (_constraint_check) is domain-agnostic: one fast AI call derives the
context's hard constraints (budget caps, counts like '2 BHK', attributes like
'furnished') and rejects options whose pages give CLEAR evidence of violation.
Fail-open by design. Cost knobs: ranked links cap 60, pick text 3K, consolidate
4.5K.
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routes import deep_import as di  # noqa: E402


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


PAGES = {
    "Flat A (35k)": "2 BHK flat. Monthly Rent 35,000. Deposit 2L. Mogappair West.",
    "Flat B (25k)": "2 BHK flat. Monthly Rent 25,000. Deposit 1L. Mogappair East.",
    "Flat C (no price)": "2 BHK flat in Mogappair. Spacious. Contact owner for rent details.",
}
CTX = "Choose best 2 BHK Flat for Rent in Chennai Mugappair under ₹30000 per month"


def test_gate_rejects_only_evidenced_violations():
    ai = ('{"constraints":["rent ≤ ₹30,000/month","2 BHK","Mugappair area"],'
          '"options":['
          '{"name":"Flat A (35k)","verdict":"fail","violated":"rent 35,000 > cap 30,000"},'
          '{"name":"Flat B (25k)","verdict":"pass","violated":""},'
          '{"name":"Flat C (no price)","verdict":"unknown","violated":""}]}')
    with patch.object(di, "metered_chat", AsyncMock(return_value=ai)):
        kept, rejected, constraints = _run(di._constraint_check("u1", CTX, dict(PAGES)))
    assert set(kept) == {"Flat B (25k)", "Flat C (no price)"}  # unknown is NOT a violation
    assert rejected == [{"name": "Flat A (35k)", "violated": "rent 35,000 > cap 30,000"}]
    assert "rent ≤ ₹30,000/month" in constraints


def test_gate_fail_requires_evidence_text():
    # "fail" without a violated reason → kept (never guess)
    ai = ('{"constraints":["c"],"options":['
          '{"name":"Flat A (35k)","verdict":"fail","violated":""}]}')
    with patch.object(di, "metered_chat", AsyncMock(return_value=ai)):
        kept, rejected, _ = _run(di._constraint_check("u1", CTX, dict(PAGES)))
    assert len(kept) == 3 and rejected == []


def test_gate_fails_open_on_garbage_and_errors():
    with patch.object(di, "metered_chat", AsyncMock(return_value="not json at all")):
        kept, rejected, constraints = _run(di._constraint_check("u1", CTX, dict(PAGES)))
    assert len(kept) == 3 and rejected == [] and constraints == []
    with patch.object(di, "metered_chat", AsyncMock(side_effect=RuntimeError("provider down"))):
        kept, rejected, _ = _run(di._constraint_check("u1", CTX, dict(PAGES)))
    assert len(kept) == 3 and rejected == []


def test_gate_traces_onto_tel():
    ai = '{"constraints":[],"options":[]}'
    tel = {}

    async def fake(user_id, **kw):
        kw.get("meta", {}).update(provider="gemini", model="gemini-2.5-flash",
                                  tokens=900, credits=9.0)
        return ai

    with patch.object(di, "metered_chat", AsyncMock(side_effect=fake)):
        _run(di._constraint_check("u1", CTX, dict(PAGES), tel=tel))
    call = tel["ai_calls"][0]
    assert call["stage"] == "constraint_check" and call["credits"] == 9.0


def test_cost_knobs():
    assert di._rank_links.__defaults__[0] == 60          # link cap halved+
    assert di.PICK_TEXT_LIMIT == 3000
    assert di.CONSOLIDATE_TEXT_LIMIT == 4500
    assert di.CONSTRAINT_TEXT_LIMIT == 2500
    assert "HARD CONSTRAINTS" in di.LINKS_SYSTEM          # generic derivation in pick prompt
    assert "compliance checker" in di.CONSTRAINT_SYSTEM
