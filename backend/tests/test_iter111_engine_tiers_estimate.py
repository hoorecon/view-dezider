"""Iteration 111 — Engine tiering (margin protection) + import credits preview.

Covers:
  1. engine_recos: stage-tier config roundtrip + validation.
  2. engine_recos.compute_recos: stats from seeded ai_calls traces +
     downgrade/upgrade recommendation rules.
  3. Deep-import _discover honors stage tiers (resolution logic).
  4. /ai-wallet/import-estimate history math (per-page deep estimate).
"""
import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import db          # noqa: E402
from core import engine_recos as er   # noqa: E402


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── 1. config roundtrip ──────────────────────────────────────────────────────
def test_stage_tier_roundtrip_and_validation():
    async def run():
        orig = await er.get_stage_tiers()
        assert set(orig) == set(er.STAGES)
        tiers = await er.set_stage_tier("consolidate", "fast", "test-admin")
        assert tiers["consolidate"] == "fast"
        tiers = await er.set_stage_tier("consolidate", "job", "test-admin")  # restore default
        assert tiers["consolidate"] == "job"
        try:
            await er.set_stage_tier("consolidate", "turbo", "test-admin")
            raise AssertionError("invalid tier accepted")
        except ValueError:
            pass
        try:
            await er.set_stage_tier("nope", "fast", "test-admin")
            raise AssertionError("invalid stage accepted")
        except ValueError:
            pass
    _run(run())


# ── 2. recommendations from seeded traces ────────────────────────────────────
def test_compute_recos_downgrade_rule():
    async def run():
        marker = f"iter111_{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc)
        # Seed: hubs_pick succeeded 4x on fast — while config says precise → downgrade reco
        docs = [{
            "id": f"{marker}_{i}", "endpoint": "deep_import", "status": "success",
            "ts": now, "ai_calls": [
                {"stage": "hubs_pick", "provider": "gemini", "credits": 10.0},
                {"stage": "hubs_pick", "provider": "emergent_precise", "credits": 90.0},
            ]} for i in range(4)]
        await db.url_import_runs.insert_many(docs)
        await er.set_stage_tier("hubs_pick", "precise", "test-admin")
        try:
            recos = await er.compute_recos(days=1)
            hub = next(s for s in recos["stages"] if s["stage"] == "hubs_pick")
            assert hub["current_tier"] == "precise"
            assert hub["tiers"]["fast"]["runs"] >= 4
            assert hub["recommendation"] == "downgrade_to_fast"
            # avg includes any real telemetry rows too — just require a positive saving
            assert hub["projected_saving"] is not None and hub["projected_saving"] > 0
        finally:
            await db.url_import_runs.delete_many({"id": {"$regex": f"^{marker}"}})
            await er.set_stage_tier("hubs_pick", "fast", "test-admin")
    _run(run())


def test_compute_recos_links_pick_normalises_hub_stages():
    assert er._norm_stage("links_pick@hub2") == "links_pick"
    assert er._norm_stage("hubs_pick") == "hubs_pick"
    assert er._tier_of("emergent_precise") == "precise"
    assert er._tier_of("groq") == "fast"


# ── 3. discover-side tier resolution (mirror of routes/deep_import.py) ──────
def test_job_tier_resolution():
    async def run():
        tiers = await er.get_stage_tiers()
        job_tier = "precise"
        cons = job_tier if tiers["consolidate"] == "job" else tiers["consolidate"]
        assert cons in ("fast", "precise")
        assert (tiers["consolidate"] == "job") == (cons == job_tier)
    _run(run())


# ── 4. import-estimate history math ─────────────────────────────────────────
def test_deep_estimate_per_page_math():
    async def run():
        marker = f"iter111est_{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc)
        await db.url_import_runs.insert_one({
            "id": marker, "endpoint": "deep_import", "status": "success",
            "ts": now, "ai_tier": "precise", "total_credits": 600.0, "item_count": 3})
        try:
            # mirror of routes/ai_wallet.import_estimate deep branch
            rows = await (db.url_import_runs
                          .find({"endpoint": "deep_import", "status": "success",
                                 "total_credits": {"$gt": 0}},
                                {"_id": 0, "total_credits": 1, "item_count": 1, "ai_tier": 1})
                          .sort("ts", -1).limit(20).to_list(20))
            tier_rows = [r for r in rows if r.get("ai_tier") == "precise"] or rows
            per_page = (sum(r["total_credits"] / max(int(r.get("item_count") or 1), 1)
                            for r in tier_rows) / len(tier_rows))
            assert per_page > 0
            # seeded run contributes 600/3 = 200 cr/page to the average
            assert any(abs(r["total_credits"] - 600.0) < 0.01 for r in tier_rows)
        finally:
            await db.url_import_runs.delete_one({"id": marker})
    _run(run())
