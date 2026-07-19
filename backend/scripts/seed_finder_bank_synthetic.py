"""Synthetic Option-Bank seeder + FRAME benchmark.

Seeds N synthetic options into `decider_option_bank` for a template, then runs
the full async bank pipeline (S1 indexed pre-filter → S2 streamed heap Top-K →
S3 auction) and reports the timings that back the ≤60s SLA in SRS v3.23.

Usage:
  python scripts/seed_finder_bank_synthetic.py --template bmp-55-patterns \
      --count 200000 [--wipe] [--seed-only | --bench-only]
"""
import argparse
import asyncio
import os
import random
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(os.path.dirname(HERE), ".env"))

from core.database import db  # noqa: E402
from core import finder_bank  # noqa: E402

WORDS = ["swift", "prime", "nova", "atlas", "zen", "flux", "core", "apex",
         "orbit", "pulse", "vertex", "delta", "aero", "terra", "lumen"]


def _synth_vals(sids, rng):
    vals = {}
    for sid, dtype in sids:
        if dtype == "text":
            w = rng.choice(WORDS)
            vals[sid] = {"num": None, "txt": w}
        else:
            n = round(rng.uniform(1, 100), 1)
            vals[sid] = {"num": n, "txt": str(n)}
    return vals


async def seed(template, count, wipe):
    tid = template["template_id"]
    if wipe:
        res = await db[finder_bank.BANK].delete_many({"template_id": tid, "source": "synthetic"})
        print(f"wiped {res.deleted_count} synthetic rows")
    sids = []
    for f in template.get("factors") or []:
        for sf in f.get("sub_factors") or [{"id": f.get("id")}]:
            dt = str(sf.get("data_type") or "").lower()
            sids.append((sf["id"], "text" if dt == "text" else "number"))
    rng = random.Random(42)
    now = finder_bank._now()
    t0 = time.monotonic()
    batch, inserted = [], 0
    for i in range(count):
        name = f"Synthetic Option {i:07d}"
        batch.append({"bank_id": str(uuid.uuid4()), "template_id": tid,
                      "name": name, "name_norm": finder_bank._norm(name),
                      "vals": _synth_vals(sids, rng), "source": "synthetic",
                      "source_ref": None, "description": "", "created_at": now,
                      "updated_at": now})
        if len(batch) >= 10000:
            await db[finder_bank.BANK].insert_many(batch, ordered=False)
            inserted += len(batch)
            batch = []
            print(f"  seeded {inserted:,}/{count:,} "
                  f"({inserted / (time.monotonic() - t0):,.0f}/s)")
    if batch:
        await db[finder_bank.BANK].insert_many(batch, ordered=False)
        inserted += len(batch)
    print(f"seeded {inserted:,} rows in {time.monotonic() - t0:.1f}s")


async def bench(template):
    """Build an in-memory cloned decision with realistic expectations and time
    the real pipeline end-to-end."""
    from routes.decider_store import _build_decision_from_template
    user = {"user_id": "bench_user"}
    decision = _build_decision_from_template(template, "full", user)
    decision["id"] = f"bench_{uuid.uuid4().hex[:8]}"
    tops = [f for f in decision["factors"] if not f.get("parent_id")]
    kids = {}
    for f in decision["factors"]:
        if f.get("parent_id"):
            kids.setdefault(f["parent_id"], []).append(f)
    for i, top in enumerate(tops):
        top["rating"] = 5 - (i % 3)
        top["category"] = "primary" if i < 2 else "secondary"
        leaves = kids.get(top["id"]) or [top]
        for leaf in leaves:
            if str(leaf.get("data_type") or "") == "text":
                continue
            # first mandatory factor is strict (≈10% selectivity), second loose
            leaf["operator"] = ">="
            leaf["expected_value"] = "90" if i == 0 else "40"
    cfg = {"min_options": 3, "max_options": 15, "top_n": 5,
           "match_rule": "any", "engine": "deterministic"}

    job_id = str(uuid.uuid4())
    await db.finder_jobs.insert_one({"id": job_id, "decision_id": decision["id"],
                                     "user_id": "bench_user", "status": "running",
                                     "progress": {}, "created_at": finder_bank._now()})
    t0 = time.monotonic()
    await finder_bank.run_bank_job(job_id, decision, template, cfg, user, "global")
    wall = time.monotonic() - t0
    job = await db.finder_jobs.find_one({"id": job_id}, {"_id": 0})
    await db.finder_jobs.delete_one({"id": job_id})
    await db.decisions.delete_many({"id": decision["id"]})
    if job["status"] != "done":
        print("BENCH FAILED:", job.get("error"))
        return
    r = job["result"]
    print("\n══════════ FRAME BENCHMARK ══════════")
    print(f"bank size        : {r['total_options']:,}")
    print(f"S1 candidates    : {r['candidates']:,}  (stage={r['stage']})")
    print(f"S2 scanned/match : {r['scanned']:,} / {r['survivors']:,}")
    print(f"pipeline time    : {r['duration_ms']/1000:.2f}s (wall {wall:.2f}s)")
    print(f"throughput       : {r['scanned']/max(0.001, r['duration_ms']/1000):,.0f} options/s")
    print("top 5            :")
    for x in r["top"]:
        print(f"  {x['worth_percentage']:6.2f}%  {x['name']}")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", default="bmp-55-patterns")
    ap.add_argument("--count", type=int, default=200000)
    ap.add_argument("--wipe", action="store_true")
    ap.add_argument("--seed-only", action="store_true")
    ap.add_argument("--bench-only", action="store_true")
    args = ap.parse_args()
    template = await db.decider_store_templates.find_one(
        {"template_id": args.template}, {"_id": 0})
    if not template:
        print(f"template {args.template} not found")
        return
    if not args.bench_only:
        await seed(template, args.count, args.wipe)
    if not args.seed_only:
        await bench(template)


if __name__ == "__main__":
    asyncio.run(main())
