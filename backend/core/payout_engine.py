"""
Catalog Payout Engine
=====================
Resolves per-catalog-node monetization config (free-usage quota, Solution Store
cash payment range, Karma rates) with L3 -> L2 -> L1 -> L0 -> global -> default
inheritance (nearest override wins per-field), and computes cash payouts + Karma
awards per the agreed equations:

  cash_payout = payment_min + (payment_max - payment_min)
                              * (avg_rating / 5) * (num_ratings / 3000)
                (clamped to [payment_min, payment_max])

  karma       = karma_per_use * (1 + star_rating / 5)

Karma vs Cash policy (user-mandated):
  - Solution Store PAID usage   -> CASH  (compute_cash_payout)
  - Solution Store FREE usage   -> KARMA (karma_solution_store)
  - Decision Template FREE use  -> KARMA by copy-depth step (karma_template_by_step;
                                   higher step = more karma)
  - ReviewNet qualitative rate  -> KARMA (karma_reviewnet)
Cash is rewarded ONLY for Solution Store paid usage; everywhere else => Karma.
"""
from typing import Any, Dict, List, Optional

# The 5 cumulative copy-depth steps of a Decision Template (low -> high value).
TEMPLATE_STEPS = ["factors", "classification", "prioritization", "options", "assessment"]

# Per-step dict fields (resolved step-by-step during inheritance).
DICT_FIELDS = {"karma_template_by_step", "free_usage_template_by_step"}

# Fields that participate in inheritance.
CONFIG_FIELDS = [
    "free_usage_solution_store",
    "free_usage_template_by_step",
    "payment_min",
    "payment_max",
    "karma_solution_store",
    "karma_reviewnet",
    "karma_template_by_step",
]

# System default (the implicit L0 baseline if no global config is set).
DEFAULT_GLOBAL: Dict[str, Any] = {
    "free_usage_solution_store": 3,
    "free_usage_template_by_step": {
        "factors": 3,
        "classification": 3,
        "prioritization": 3,
        "options": 3,
        "assessment": 3,
    },
    "payment_min": 10.0,
    "payment_max": 500.0,
    "karma_solution_store": 5,
    "karma_reviewnet": 2,
    "karma_template_by_step": {
        "factors": 1,
        "classification": 2,
        "prioritization": 3,
        "options": 4,
        "assessment": 5,
    },
}


async def resolve_payout_config(db, node_id: Optional[str]) -> Dict[str, Any]:
    """Effective config for a catalog node.

    Resolution order (first non-null value wins, per field):
      node (deepest) -> ... -> ancestors -> L0 -> global doc -> DEFAULT_GLOBAL.
    Returns the merged config plus a `_provenance` map showing where each field
    was resolved from (node_id label / "global" / "default").
    """
    configs: List[tuple] = []  # (label, cfg-dict) ordered nearest -> farthest

    if node_id:
        cur = await db.catalog_nodes.find_one({"node_id": node_id}, {"_id": 0})
        while cur:
            cfg = await db.catalog_payout_configs.find_one(
                {"scope": "node", "node_id": cur["node_id"]}, {"_id": 0}
            )
            label = f"{cur['node_id']} (L{cur.get('level')})"
            configs.append((label, cfg or {}))
            pid = cur.get("parent_id")
            cur = await db.catalog_nodes.find_one({"node_id": pid}, {"_id": 0}) if pid else None

    g = await db.catalog_payout_configs.find_one({"scope": "global"}, {"_id": 0}) or {}
    configs.append(("global", g))
    configs.append(("default", DEFAULT_GLOBAL))

    effective: Dict[str, Any] = {}
    provenance: Dict[str, Any] = {}

    for field in CONFIG_FIELDS:
        if field in DICT_FIELDS:
            merged: Dict[str, int] = {}
            prov: Dict[str, str] = {}
            for step in TEMPLATE_STEPS:
                for label, cfg in configs:
                    raw = cfg.get(field)
                    val = raw.get(step) if isinstance(raw, dict) else None
                    if val is not None:
                        merged[step] = int(val)
                        prov[step] = label
                        break
            effective[field] = merged
            provenance[field] = prov
        else:
            for label, cfg in configs:
                if cfg.get(field) is not None:
                    effective[field] = cfg[field]
                    provenance[field] = label
                    break

    effective["node_id"] = node_id
    effective["_provenance"] = provenance
    return effective


def compute_cash_payout(config: Dict[str, Any], avg_rating: float, num_ratings: int) -> float:
    """Solution Store PAID-usage cash payout (₹), clamped to [min, max]."""
    pmin = float(config.get("payment_min") or 0)
    pmax = float(config.get("payment_max") or 0)
    if pmax < pmin:
        pmax = pmin
    raw = pmin + (pmax - pmin) * (float(avg_rating or 0) / 5.0) * (float(num_ratings or 0) / 3000.0)
    return round(max(pmin, min(raw, pmax)), 2)


def compute_karma(karma_per_use: int, star_rating: Optional[float] = None) -> int:
    """Karma award = karma_per_use * (1 + star_rating/5). No rating => x1."""
    base = int(karma_per_use or 0)
    mult = 1.0 + (float(star_rating) / 5.0 if star_rating else 0.0)
    return int(round(base * mult))


def template_step_karma(config: Dict[str, Any], step: str, star_rating: Optional[float] = None) -> int:
    """Karma for a FREE Decision-Template usage at a given copy-depth step."""
    by = config.get("karma_template_by_step") or {}
    return compute_karma(int(by.get(step, 0) or 0), star_rating)
