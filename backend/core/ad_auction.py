"""AdMaker auction core — Sponsored Solutions for DeciderApps (Finder).

FRAME pipeline stages 4-6 (see docs/SRS.md v3.22.0):

  ORGANIC IS SACRED  — the Finder's organic Top-N is purely quality-ranked;
                       money can NEVER reorder it. Sponsored Solutions render
                       in a clearly-labelled block BELOW the organic list.
  QUALITY GATE       — only options whose Overall Suitability % clears the
                       Min-Cutoff % are auction-eligible. The cutoff resolves
                       hierarchically from the Central Catalog Manager (CCM):
                       template override → Scenario (L3) → Category (L2) →
                       SubArea (L1) → LifeArea (L0) → global admin default.
                       "Higher-level value applies to all leaves unless a
                       deeper node overrides."
  ADRANK AUCTION     — AdRank = bid × QualityScore (suitability/100), the same
                       family of rules Google AdWords uses: a high bid cannot
                       rescue a bad match.
  GSP PRICING        — Generalized Second-Price: each winner pays just enough
                       to hold its slot (next AdRank ÷ own QS, +1 paisa),
                       never more than its own bid. Charged per CLICK (CPC).
  REGION + TIME SLOT — bids target a region ('global' or a country code) plus
                       an optional calendar window and daily hour range in the
                       advertiser's timezone (AdWords-style dayparting).

Pure functions (`bid_is_live`, `score_bids`) are DB-free for unit testing.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from core.database import db

RESERVE_PRICE_PAISE = 1        # auction floor (₹0.01 per click)
QS_FLOOR = 0.05                # quality-score floor to avoid divide-by-zero
DEFAULT_MIN_CUTOFF_PCT = 60.0  # fallback when nothing configured anywhere
DEFAULT_SPONSORED_N = 3


def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def _parse_dt(v: Any) -> Optional[datetime]:
    if not v:
        return None
    try:
        s = str(v).strip()
        if len(s) == 10:  # date-only → midnight
            s += "T00:00:00"
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


# ─────────────────────────── bid liveness (pure) ───────────────────────────
def bid_is_live(bid: Dict[str, Any], region: str = "global",
                now: Optional[datetime] = None) -> bool:
    """Is this bid competing right now, for this user's region?"""
    now = now or datetime.now(timezone.utc)
    if (bid.get("status") or "active") != "active":
        return False
    budget = int(bid.get("budget_paise") or 0)
    if budget > 0 and int(bid.get("spent_paise") or 0) >= budget:
        return False
    br = _norm(bid.get("region") or "global")
    if br not in ("", "global") and br != _norm(region or "global"):
        return False
    start, end = _parse_dt(bid.get("slot_start")), _parse_dt(bid.get("slot_end"))
    if start and now < start:
        return False
    if end and now > end:
        return False
    sh, eh = bid.get("daily_start_hour"), bid.get("daily_end_hour")
    if sh is not None and eh is not None:
        try:
            tz = ZoneInfo(str(bid.get("timezone") or "Asia/Kolkata"))
        except Exception:
            tz = timezone.utc
        h = now.astimezone(tz).hour
        sh, eh = int(sh), int(eh)
        if sh == eh:
            pass                            # degenerate → 24h window
        elif sh < eh:
            if not (sh <= h < eh):
                return False
        else:                               # overnight wrap (e.g. 22 → 6)
            if not (h >= sh or h < eh):
                return False
    return True


# ─────────────────────────── GSP auction (pure) ───────────────────────────
def score_bids(bids: List[Dict[str, Any]], eligible: List[Dict[str, Any]],
               sponsored_n: int) -> List[Dict[str, Any]]:
    """AdRank auction + Generalized Second-Price over the cutoff survivors.

    `eligible` = ranked options ALREADY above the Min-Cutoff %
                 (each: {option_id, name, worth_percentage}).
    Returns slot-ordered winners with the CPC price each pays.
    """
    by_name: Dict[str, Dict[str, Any]] = {}
    for r in eligible:
        by_name.setdefault(_norm(r.get("name")), r)

    entries: List[Dict[str, Any]] = []
    for b in bids:
        opt = by_name.get(_norm(b.get("option_name")))
        if not opt:
            continue  # bid target didn't pass the quality gate → no auction entry
        bid_paise = int(b.get("bid_paise") or 0)
        if bid_paise <= 0:
            continue
        qs = max(QS_FLOOR, float(opt.get("worth_percentage") or 0) / 100.0)
        entries.append({
            "bid_id": b.get("bid_id"),
            "advertiser_name": b.get("advertiser_name") or "Sponsor",
            "option_id": opt.get("option_id"),
            "name": opt.get("name"),
            "worth_percentage": opt.get("worth_percentage"),
            "quality_score": round(qs, 4),
            "bid_paise": bid_paise,
            "ad_rank": bid_paise * qs,
        })

    # One slot per option — keep only the strongest bid per option.
    best: Dict[str, Dict[str, Any]] = {}
    for e in sorted(entries, key=lambda x: x["ad_rank"], reverse=True):
        best.setdefault(e["option_id"], e)
    ordered = sorted(best.values(), key=lambda x: x["ad_rank"], reverse=True)

    winners = ordered[: max(0, int(sponsored_n))]
    for i, w in enumerate(winners):
        if i + 1 < len(ordered):
            price = int(ordered[i + 1]["ad_rank"] / w["quality_score"]) + 1
        else:
            price = RESERVE_PRICE_PAISE
        w["price_paise"] = max(RESERVE_PRICE_PAISE, min(price, w["bid_paise"]))
        w["slot"] = i + 1
        w["ad_rank"] = round(w["ad_rank"], 2)
    return winners


# ───────────────────── hierarchical config resolution ─────────────────────
async def resolve_node_chain_config(node_id: str) -> Dict[str, Any]:
    """Walk a CCM node → its ancestors; the NEAREST node that configures a
    key wins for that key (per-key inheritance)."""
    out: Dict[str, Any] = {"min_cutoff_pct": None, "sponsored_n": None,
                           "cutoff_source": None, "sponsored_source": None}
    cur, hops = node_id, 0
    while cur and hops < 8:
        node = await db.catalog_nodes.find_one(
            {"node_id": cur},
            {"_id": 0, "node_id": 1, "parent_id": 1, "name": 1, "finder_ad_config": 1})
        if not node:
            break
        fac = node.get("finder_ad_config") or {}
        if out["min_cutoff_pct"] is None and fac.get("min_cutoff_pct") is not None:
            out["min_cutoff_pct"] = float(fac["min_cutoff_pct"])
            out["cutoff_source"] = {"node_id": node["node_id"], "name": node.get("name")}
        if out["sponsored_n"] is None and fac.get("sponsored_n") is not None:
            out["sponsored_n"] = int(fac["sponsored_n"])
            out["sponsored_source"] = {"node_id": node["node_id"], "name": node.get("name")}
        if out["min_cutoff_pct"] is not None and out["sponsored_n"] is not None:
            break
        cur, hops = node.get("parent_id"), hops + 1
    return out


async def resolve_ad_config(template: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Effective {min_cutoff_pct, sponsored_n} for a Decider App.
    Precedence: template finder_settings → CCM node chain → global defaults."""
    from core import ai_wallet
    admin = await ai_wallet.get_config()
    cutoff: Optional[float] = None
    n: Optional[int] = None
    cutoff_src: Any = "global"
    n_src: Any = "global"

    fs = (template or {}).get("finder_settings") or {}
    if fs.get("min_cutoff_pct") is not None:
        cutoff, cutoff_src = float(fs["min_cutoff_pct"]), "template"
    if fs.get("sponsored_n") is not None:
        n, n_src = int(fs["sponsored_n"]), "template"

    node_id = (template or {}).get("catalog_node_id")
    if node_id and (cutoff is None or n is None):
        chain = await resolve_node_chain_config(node_id)
        if cutoff is None and chain["min_cutoff_pct"] is not None:
            cutoff, cutoff_src = chain["min_cutoff_pct"], chain["cutoff_source"]
        if n is None and chain["sponsored_n"] is not None:
            n, n_src = chain["sponsored_n"], chain["sponsored_source"]

    if cutoff is None:
        cutoff = float(admin.get("finder_min_cutoff_pct", DEFAULT_MIN_CUTOFF_PCT))
    if n is None:
        n = int(admin.get("finder_sponsored_n", DEFAULT_SPONSORED_N))
    return {"min_cutoff_pct": cutoff, "sponsored_n": n,
            "cutoff_source": cutoff_src, "sponsored_source": n_src}


# ─────────────────────────── run + telemetry ───────────────────────────
async def run_auction(template_id: str, ranked: List[Dict[str, Any]],
                      region: str = "global", sponsored_n: int = DEFAULT_SPONSORED_N,
                      min_cutoff_pct: float = DEFAULT_MIN_CUTOFF_PCT,
                      now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    if int(sponsored_n) <= 0:
        return []
    eligible = [r for r in (ranked or [])
                if float(r.get("worth_percentage") or 0) >= float(min_cutoff_pct)]
    if not eligible:
        return []
    bids = await db.admaker_bids.find(
        {"template_id": template_id, "status": "active"}, {"_id": 0}).to_list(500)
    live = [b for b in bids if bid_is_live(b, region=region, now=now)]
    if not live:
        return []
    return score_bids(live, eligible, sponsored_n)


async def record_impressions(winners: List[Dict[str, Any]], template_id: str,
                             decision_id: str, region: str, user_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for w in winners:
        await db.admaker_events.insert_one({
            "event_id": str(uuid.uuid4()), "event": "impression",
            "bid_id": w["bid_id"], "template_id": template_id,
            "decision_id": decision_id, "option_id": w["option_id"],
            "slot": w["slot"], "price_paise": w["price_paise"],
            "region": region, "user_id": user_id, "ts": now,
        })
        await db.admaker_bids.update_one(
            {"bid_id": w["bid_id"]},
            {"$inc": {"impressions": 1},
             "$set": {"last_price_paise": w["price_paise"], "updated_at": now}})
