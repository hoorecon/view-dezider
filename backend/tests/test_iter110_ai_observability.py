"""Iteration 110 — Admin AI observability: per-run AI call trace (engine/model,
engineered prompts, credits), run cost rollups, and Auto-Tune over deep stages.

Unit/DB tests (AI mocked, local Mongo):
  1. add_ai_call captures stage/engine/tokens/credits/latency + truncated bodies.
  2. record_run persists ai_calls + rollups (ai_tokens, ai_engines, ai_credits
     from wallet ledger, total_credits incl. scrape).
  3. _lazy_purge strips ai_calls bodies after retention, keeps metadata.
  4. TUNE_KEYS includes the deep-import stage keys; get_guidance returns
     override text and '' when absent.
  5. Deep-import pickers append active guidance to their system prompts and
     trace the call onto tel.
"""
import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import db                       # noqa: E402
from core import url_telemetry as ut               # noqa: E402
from core import url_prompt_tuning as upt          # noqa: E402
from routes import deep_import as di               # noqa: E402

def _run(coro):
    """Repo-wide test convention: persistent shared event loop
    (asyncio.run would close loops and break sibling suites)."""
    return asyncio.get_event_loop().run_until_complete(coro)


UID = f"testuser_iter110_{uuid.uuid4().hex[:6]}"


def _meta():
    return {"provider": "gemini", "model": "gemini-2.5-flash", "tokens": 1234, "credits": 3.21}


# ── 1. add_ai_call ───────────────────────────────────────────────────────────
def test_add_ai_call_captures_engine_and_bodies():
    tel = {}
    started = datetime.now(timezone.utc) - timedelta(milliseconds=500)
    ut.add_ai_call(tel, stage="links_pick", system_prompt="SYS " + "x" * 9000,
                   prompt_text="PROMPT", raw_response="RAW", meta=_meta(), started=started)
    c = tel["ai_calls"][0]
    assert c["stage"] == "links_pick"
    assert c["engine"] == "gemini/gemini-2.5-flash"
    assert c["tokens"] == 1234 and c["credits"] == 3.21
    assert c["latency_ms"] >= 500
    assert len(c["system_prompt"]) <= ut.CALL_TRUNC + 20  # truncated
    assert c["raw_response"] == "RAW"


def test_add_ai_call_never_raises_on_garbage():
    tel = {}
    ut.add_ai_call(tel, stage="x", system_prompt=None, prompt_text=None,
                   raw_response=None, meta={"tokens": "??"}, started=None)
    # bad tokens swallowed — trace either skipped or stored without crash
    assert isinstance(tel.get("ai_calls", []), list)


# ── 2. record_run rollups ────────────────────────────────────────────────────
def test_record_run_persists_trace_and_credit_rollups():
    async def run():
        tel = ut.new_tel(UID, endpoint="deep_import",
                         url="https://www.nobroker.in/", ai_tier="precise", hints=None)
        # simulate AI debits in the wallet ledger during the run window
        await db.ai_wallet_ledger.insert_many([
            {"user_id": UID, "kind": "debit", "feature": "deep_import_links",
             "delta": -2.5, "created_at": datetime.now(timezone.utc)},
            {"user_id": UID, "kind": "debit", "feature": "scrape_fetch",  # excluded from AI credits
             "delta": -5.0, "created_at": datetime.now(timezone.utc)},
        ])
        ut.add_ai_call(tel, stage="links_pick", system_prompt="S", prompt_text="P",
                       raw_response="R", meta=_meta())
        ut.add_ai_call(tel, stage="consolidate", system_prompt="S2", prompt_text="P2",
                       raw_response="R2",
                       meta={"provider": "emergent_precise", "model": "claude-sonnet",
                             "tokens": 100, "credits": 9.0})
        tel["route"] = "deep_import"
        await ut.record_run(tel, status="success")
        doc = await db.url_import_runs.find_one({"id": tel["run_id"]}, {"_id": 0})
        assert doc["ai_calls_count"] == 2
        assert doc["ai_tokens"] == 1334
        assert doc["ai_engines"] == ["emergent_precise/claude-sonnet", "gemini/gemini-2.5-flash"]
        assert doc["ai_credits"] == 2.5          # ledger rollup, scrape_fetch excluded
        assert doc["total_credits"] == 2.5       # no scrape_usage rows for this user
        # cleanup
        await db.url_import_runs.delete_one({"id": tel["run_id"]})
        await db.ai_wallet_ledger.delete_many({"user_id": UID})
    _run(run())


# ── 3. purge strips trace bodies, keeps metadata ─────────────────────────────
def test_lazy_purge_strips_ai_call_bodies():
    async def run():
        rid = f"run_iter110_{uuid.uuid4().hex[:8]}"
        old_ts = datetime.now(timezone.utc) - timedelta(days=ut.PURGE_DAYS + 5)
        await db.url_import_runs.insert_one({
            "id": rid, "ts": old_ts, "ai_system_prompt": None,
            "ai_calls": [{"stage": "links_pick", "engine": "gemini/x", "tokens": 5,
                          "credits": 0.1, "system_prompt": "S", "prompt_text": "P",
                          "raw_response": "R"}]})
        await ut._lazy_purge(datetime.now(timezone.utc))
        doc = await db.url_import_runs.find_one({"id": rid}, {"_id": 0})
        c = doc["ai_calls"][0]
        assert "system_prompt" not in c and "raw_response" not in c
        assert c["engine"] == "gemini/x" and c["credits"] == 0.1  # metadata kept
        assert doc["ai_calls_bodies_purged"] is True
        await db.url_import_runs.delete_one({"id": rid})
    _run(run())


# ── 4. tuning keys + guidance ────────────────────────────────────────────────
def test_tune_keys_include_deep_stages():
    for k in ("deep_links", "deep_hubs", "deep_consolidate"):
        assert k in upt.TUNE_KEYS and k in upt.DEEP_KEYS
    assert upt._DEEP_STAGE_PREFIX["deep_consolidate"] == "consolidate"


def test_get_guidance_roundtrip():
    async def run():
        key = "deep_links"
        await db.url_prompt_overrides.delete_one({"key": "__iter110__"})
        assert await upt.get_guidance("__iter110__") == ""
        await db.url_prompt_overrides.insert_one({"key": "__iter110__", "guidance": "\nBE STRICTER."})
        assert "BE STRICTER" in await upt.get_guidance("__iter110__")
        await db.url_prompt_overrides.delete_one({"key": "__iter110__"})
        assert isinstance(await upt.get_guidance(key), str)
    _run(run())


# ── 5. deep pickers: guidance appended + call traced ─────────────────────────
def test_pick_detail_links_appends_guidance_and_traces():
    async def run():
        captured = {}

        async def fake_chat(user_id, *, system_message, prompt, **kw):
            captured["sys"] = system_message
            kw.get("meta", {}).update(_meta())
            return '{"options":[{"name":"Flat A","url":"https://x.nobroker.in/property/a/detail"}]}'

        tel = {}
        with patch.object(di, "metered_chat", AsyncMock(side_effect=fake_chat)), \
             patch.object(di.url_prompt_tuning, "get_guidance",
                          AsyncMock(return_value="\nTUNED-GUIDANCE-BLOCK")):
            out = await di._pick_detail_links("u1", "ctx", 5, "text", [], tel=tel)
        assert out[0]["name"] == "Flat A"
        assert "TUNED-GUIDANCE-BLOCK" in captured["sys"]          # override applied
        assert tel["ai_calls"][0]["stage"] == "links_pick"        # traced
        assert tel["ai_calls"][0]["engine"] == "gemini/gemini-2.5-flash"
    _run(run())


def test_pick_hubs_traces_stage():
    async def run():
        async def fake_chat(user_id, *, system_message, prompt, **kw):
            kw.get("meta", {}).update(_meta())
            return '{"hubs":["https://www.nobroker.in/rent-chennai"]}'

        tel = {}
        with patch.object(di, "metered_chat", AsyncMock(side_effect=fake_chat)), \
             patch.object(di.url_prompt_tuning, "get_guidance", AsyncMock(return_value="")):
            hubs = await di._pick_hubs("u1", "ctx", "https://www.nobroker.in/", "t", [], tel=tel)
        assert hubs == ["https://www.nobroker.in/rent-chennai"]
        assert tel["ai_calls"][0]["stage"] == "hubs_pick"
    _run(run())
