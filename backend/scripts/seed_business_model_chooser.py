"""One-shot seeder for the "Business Model Chooser" Decider App / Finder.

Executes the plan locked with user on 2026-07-19:
  1. Delete the old `The 55 Business Model Patterns` template + its option bank
  2. Create a fresh template `Business Model Chooser` with kind='app'
     (Decider App / Finder), finder_settings (min_cutoff_pct=60, sponsored_n=3),
     status=authorized + is_public=True (goes LIVE)
  3. Parse /app/docs/business_model_chooser/Business_Model_Chooser_ready.xlsx
     -> 10 factors x 28 sub-factors x 54 options and store on the template
  4. Ingest all 54 options into the Option Bank so `bank_options=54` triggers
     the async job-mode Finder (matches the 10M-scale contract).
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Allow "python scripts/foo.py" style
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import db  # noqa: E402
from core.decider_import import parse_import  # noqa: E402
from core.finder_bank import bank_upsert  # noqa: E402


READY_XLSX = Path("/app/docs/business_model_chooser/Business_Model_Chooser_ready.xlsx")
OLD_TITLE = "The 55 Business Model Patterns"
NEW_TITLE = "Business Model Chooser"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _resolve_admin_user() -> dict:
    """Prefer an existing super_admin, fall back to admin. If none, synthesise."""
    for role in ("super_admin", "admin"):
        u = await db.users.find_one({"role": role})
        if u:
            return {"user_id": u.get("user_id") or u.get("_id") or str(uuid.uuid4()),
                    "email": u.get("email"), "name": u.get("name") or role}
    return {"user_id": "system_seeder", "email": "system@jelcos.ai",
            "name": "System Seeder"}


async def _delete_old(admin: dict) -> dict:
    """Remove ANY prior `Business Model Chooser` doc AND the legacy
    `The 55 Business Model Patterns` template (+ their bank / finder_jobs).

    Idempotent — safe to re-run.
    """
    result = {"deleted_templates": 0, "deleted_bank_rows": 0,
              "deleted_finder_jobs": 0, "old_template_ids": []}
    olds = await db.decider_store_templates.find(
        {"$or": [
            {"title": {"$regex": r"^The 55 Business Model Patterns", "$options": "i"}},
            {"title": {"$regex": r"^Business Model Chooser", "$options": "i"}},
        ]}
    ).to_list(50)
    if not olds:
        return result
    for o in olds:
        tid = o["template_id"]
        result["old_template_ids"].append(tid)
        bank = await db.decider_option_bank.delete_many({"template_id": tid})
        jobs = await db.finder_jobs.delete_many({"template_id": tid})
        result["deleted_bank_rows"] += bank.deleted_count or 0
        result["deleted_finder_jobs"] += jobs.deleted_count or 0
    tres = await db.decider_store_templates.delete_many(
        {"template_id": {"$in": result["old_template_ids"]}})
    result["deleted_templates"] = tres.deleted_count or 0
    return result


async def _create_new(admin: dict, model: dict) -> dict:
    # Build factors + options arrays in the same shape the frontend
    # /decider-store/[id] and Finder engine expect.
    factors_out = []
    for f in model["factors"]:
        factors_out.append({
            "id": f["id"],
            "name": f["name"],
            "order": f.get("order", 0),
            "category": f.get("category", "mandatory"),
            "priority": f.get("priority", 1),
            "factor_type": f.get("factor_type", "qualitative"),
            "sub_factors": [
                {
                    "id": s["id"],
                    "name": s["name"],
                    "order": s.get("order", 0),
                    "data_type": s.get("data_type", "%"),
                    "ui_object": s.get("ui_object", "Input Box"),
                    "split_pct": s.get("split_pct"),
                } for s in f["sub_factors"]
            ],
            "possible_values": f.get("possible_values") or [
                s["name"] for s in f["sub_factors"]
            ],
        })

    options_out = []
    for i, o in enumerate(model["options"], start=1):
        options_out.append({
            "id": o.get("id") or str(uuid.uuid4()),
            "name": o["name"],
            "product_model": o.get("product_model", ""),
            "affected_components": o.get("affected_components", ""),
            "exemplary_companies": o.get("exemplary_companies", ""),
            "description": o.get("description", ""),
            "remarks": o.get("remarks", ""),
            "values": o.get("values") or {},
            "order": i,
        })

    template_id = str(uuid.uuid4())
    doc = {
        "template_id": template_id,
        "title": NEW_TITLE,
        "subtitle": "Pick the right revenue / business model for your venture",
        "description": (
            "A Decider App that ranks all 54 curated business-model patterns "
            "(Gassmann's 55 minus 1) against YOUR org type, solution category, "
            "revenue model, tech orientation, distribution channels and more — "
            "returns the top-N best-suited matches."
        ),
        "category": "Financial",
        "decision_type": "aspiration",
        "cover_icon": "briefcase",
        "cover_color": "#4F46E5",
        "kind": "app",   # -> shown under "Decider Apps · Finders"
        "finder_settings": {
            "min_cutoff_pct": 60.0,
            "sponsored_n": 3,
            "top_n": 5,
            "match_rule": "any",
            "engine": "deterministic",
        },
        "catalog_node_id": None,
        "pricing_type": "free",
        "price_paise": 0,
        "currency": "INR",
        "creator_split_pct": 70,
        "allowed_clone_modes": ["full", "values_only"],
        "auto_push_on_authorize": True,
        "factors": factors_out,
        "options": options_out,
        "created_by": admin["user_id"],
        "creator_name": "Earth Dezider",
        "source": "admin",
        "status": "authorized",
        "is_public": True,
        "install_count": 0,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "authorized_at": now_iso(),
        "authorized_by": admin["user_id"],
    }
    await db.decider_store_templates.insert_one(doc)
    return doc


async def _seed_option_bank(template: dict) -> dict:
    items = []
    for o in template["options"]:
        items.append({
            "name": o["name"],
            "description": o.get("description") or o.get("remarks") or "",
            "source_ref": o["id"],
            "values": o.get("values") or {},
        })
    counts = await bank_upsert(template, items, "template")
    return counts


async def main() -> None:
    if not READY_XLSX.exists():
        raise FileNotFoundError(f"Ready xlsx missing: {READY_XLSX}")
    with open(READY_XLSX, "rb") as fh:
        model = parse_import(data=fh.read())

    print(f"→ Parsed {READY_XLSX.name}: "
          f"{len(model['factors'])} factors · {len(model['options'])} options")

    admin = await _resolve_admin_user()
    print(f"→ Acting as: {admin.get('email') or admin['user_id']}")

    deleted = await _delete_old(admin)
    if deleted["deleted_templates"] == 0:
        print("→ No prior '55 BMP' template found — skipping delete.")
    else:
        print(f"→ Deleted old template(s): {deleted['deleted_templates']} · "
              f"bank rows: {deleted['deleted_bank_rows']} · "
              f"finder jobs: {deleted['deleted_finder_jobs']}")

    new_doc = await _create_new(admin, model)
    print(f"→ Created NEW template `{NEW_TITLE}` id={new_doc['template_id']}  "
          f"kind={new_doc['kind']}  LIVE={new_doc['is_public']}")

    counts = await _seed_option_bank(new_doc)
    print(f"→ Option Bank ingest: inserted={counts['inserted']}  "
          f"updated={counts['updated']}  skipped={counts['skipped']}")

    # Sanity confirm
    total_bank = await db.decider_option_bank.count_documents(
        {"template_id": new_doc["template_id"]})
    print(f"✅ Business Model Chooser is LIVE — {total_bank} rows in Option Bank, "
          f"finder job-mode enabled.")


if __name__ == "__main__":
    asyncio.run(main())
