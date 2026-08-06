"""The Decider Store — a public storefront (like App Store / Play Store) for
Admin-Authorized Decision Templates.

• Templates are browsable WITHOUT login (public GET routes).
• Cloning ("Use this template") requires an authenticated user; the clone
  builds a fresh MyDezider decision prefilled at the chosen depth:
    - mode="full"        -> factors + classification (mandatory/optional) +
                            prioritization + options + option-values
    - mode="values_only" -> factors + options + option-values only; the user
                            classifies mandatory/optional and prioritizes.
• Admins author templates by importing an Excel file or a shared Google-Sheet
  (see core.decider_import) and can then fine-tune + Authorize them.

Collection: db.decider_store_templates
"""
from __future__ import annotations

import base64
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
import io

from core.auth import get_current_user
from core.database import db
from core.decider_import import (
    parse_import, gsheet_to_csv_url, build_import_template_xlsx,
)
from core.factor_group_import import parse_from_b64 as parse_factor_group_b64

router = APIRouter(prefix="/decider-store", tags=["The Decider Store"])

CLONE_MODES = {"full", "values_only"}


def _clean_finder_settings(raw: Any) -> Dict[str, Any]:
    """Validate optional per-template Finder overrides (blanks fall back to
    the global admin defaults at run time)."""
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {}
    for k in ("min_options", "max_options", "top_n"):
        if raw.get(k) not in (None, ""):
            try:
                out[k] = max(1, int(float(raw[k])))
            except (TypeError, ValueError):
                pass
    if str(raw.get("match_rule") or "").lower() in ("all", "any"):
        out["match_rule"] = str(raw["match_rule"]).lower()
    if str(raw.get("engine") or "").lower() in ("deterministic", "llm"):
        out["engine"] = str(raw["engine"]).lower()
    # Sponsored Solutions per-app overrides (blank → CCM node chain → global).
    if raw.get("sponsored_n") not in (None, ""):
        try:
            out["sponsored_n"] = max(0, min(20, int(float(raw["sponsored_n"]))))
        except (TypeError, ValueError):
            pass
    if raw.get("min_cutoff_pct") not in (None, ""):
        try:
            out["min_cutoff_pct"] = max(0.0, min(100.0, float(raw["min_cutoff_pct"])))
        except (TypeError, ValueError):
            pass
    return out


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_admin(user: dict) -> bool:
    return user.get("role") in ("admin", "super_admin")


def _card(t: Dict[str, Any]) -> Dict[str, Any]:
    """Lightweight card for storefront lists."""
    return {
        "template_id": t.get("template_id"),
        "title": t.get("title"),
        "subtitle": t.get("subtitle"),
        "description": t.get("description"),
        "category": t.get("category"),
        "decision_type": t.get("decision_type"),
        "cover_icon": t.get("cover_icon") or "grid",
        "cover_color": t.get("cover_color") or "#4F46E5",
        "pricing_type": t.get("pricing_type") or "free",
        "price_paise": t.get("price_paise") or 0,
        "currency": t.get("currency") or "INR",
        "kind": t.get("kind") or "template",
        "finder_settings": t.get("finder_settings") or {},
        "catalog_node_id": t.get("catalog_node_id"),
        "allowed_clone_modes": t.get("allowed_clone_modes") or ["full", "values_only"],
        "factor_count": len(t.get("factors") or []),
        "option_count": len(t.get("options") or []),
        "install_count": t.get("install_count") or 0,
        "creator_name": t.get("creator_name") or "Earth Dezider",
        "publisher_type": t.get("publisher_type") or "individual",
        "life_area": t.get("life_area") or "",
        "applicable_org_types": t.get("applicable_org_types") or [],
        "rating_avg":    round(float(t.get("rating_avg") or 0), 2),
        "rating_count":  int(t.get("rating_count") or 0),
        "rating_breakdown": {
            "usefulness":    round(float(t.get("rating_usefulness_avg") or 0), 2),
            "affordability": round(float(t.get("rating_affordability_avg") or 0), 2),
            "accuracy":      round(float(t.get("rating_accuracy_avg") or 0), 2),
        },
        "status": t.get("status"),
        "moderation_status": t.get("moderation_status") or "unverified",
        "moderation_remark": t.get("moderation_remark") or "",
    }


async def _publisher_type_from_plan(user_id: Optional[str]) -> str:
    """Map a user's active subscription tier → publisher_type shown on cards:
       Basic → individual · Pro → expert · Premium → organization.
    """
    if not user_id: return "individual"
    try:
        w = await db.credit_wallets.find_one({"user_id": user_id},
                                             {"_id": 0, "current_plan": 1})
        plan = (w or {}).get("current_plan") or ""
        p = plan.lower()
        if "premium" in p:  return "organization"
        if "pro" in p:      return "expert"
    except Exception:
        pass
    return "individual"


# ══════════════════════════════════════════════════════════════════════════
# PUBLIC (no login) — browse the store
# ══════════════════════════════════════════════════════════════════════════
@router.get("")
async def list_store(
    category: Optional[str] = None, decision_type: Optional[str] = None,
    q: Optional[str] = None, kind: Optional[str] = None,
    life_area: Optional[str] = None,
    org_types: Optional[str] = None,          # comma-separated
    min_factors: Optional[int] = None, max_factors: Optional[int] = None,
    min_options: Optional[int] = None, max_options: Optional[int] = None,
    is_free: Optional[bool] = None,
    publisher_name: Optional[str] = None,
    publisher_type: Optional[str] = None,     # individual|expert|organization
    min_rating: Optional[float] = None,
    min_ratings_count: Optional[int] = None,
    moderation: Optional[str] = None,         # 'jai_verified' | 'unverified' | 'all' | 'jai_verified,unverified'
):
    """Public storefront. Fixes the "user-published public templates not
    shown here" bug by including ANY doc with `is_public=True` that isn't
    disapproved — regardless of the legacy `status=authorized` value which
    only the admin/system seed writes.
    """
    from routes.decider_moderation import get_moderation_config
    cfg = await get_moderation_config()
    show_unverified = bool(cfg.get("show_unverified_in_store", True))
    show_jai = bool(cfg.get("show_jai_verified_in_store", True))

    # Determine allowed statuses. Priority:
    #  1. Explicit query `moderation=` from the filter UI (comma-separated).
    #  2. Fall back to admin config toggles.
    # `disapproved` is ALWAYS excluded regardless of what's requested.
    allowed_statuses: List[Any] = []
    if moderation and moderation != "all":
        requested = {s.strip() for s in moderation.split(",") if s.strip() and s.strip() != "disapproved"}
        if "unverified" in requested:
            allowed_statuses.extend(["unverified", None])
        if "jai_verified" in requested:
            allowed_statuses.append("jai_verified")
    else:
        if show_jai:        allowed_statuses.append("jai_verified")
        if show_unverified: allowed_statuses.extend(["unverified", None])

    query: Dict[str, Any] = {"is_public": True}
    if allowed_statuses:
        query["moderation_status"] = {"$in": allowed_statuses} if len(allowed_statuses) > 1 else allowed_statuses[0]
    else:
        return {"templates": []}
    if category:            query["category"] = category
    if decision_type:       query["decision_type"] = decision_type
    if kind in ("template", "app"):
        query["kind"] = kind if kind == "app" else {"$ne": "app"}
    if q:
        query["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"subtitle": {"$regex": q, "$options": "i"}},
        ]
    if life_area:           query["life_area"] = {"$regex": f"^{life_area}$", "$options": "i"}
    if org_types:
        parts = [p.strip() for p in org_types.split(",") if p.strip()]
        if parts:
            query["applicable_org_types"] = {"$in": parts}
    if is_free is not None:
        query["pricing_type"] = "free" if is_free else {"$ne": "free"}
    if publisher_name:      query["creator_name"] = {"$regex": publisher_name, "$options": "i"}
    if publisher_type in ("individual", "expert", "organization"):
        query["publisher_type"] = publisher_type
    if min_rating is not None:      query["rating_avg"] = {"$gte": float(min_rating)}
    if min_ratings_count is not None: query["rating_count"] = {"$gte": int(min_ratings_count)}

    docs = await db.decider_store_templates.find(query).sort("install_count", -1).to_list(400)
    # Client-side numeric-range post-filter — factor_count / option_count are
    # denormalized on write but tolerant against older rows missing them.
    def _in_range(v: int, lo: Optional[int], hi: Optional[int]) -> bool:
        if lo is not None and v < lo: return False
        if hi is not None and v > hi: return False
        return True

    cards = []
    for d in docs:
        fc = int(d.get("factor_count") or len(d.get("factors") or []))
        oc = int(d.get("option_count") or len(d.get("options") or []))
        if not _in_range(fc, min_factors, max_factors): continue
        if not _in_range(oc, min_options, max_options): continue
        cards.append(_card(d))
    return {"templates": cards}


@router.get("/facets")
async def store_facets():
    """Filter dropdown facets. life_areas + org_types from masters,
    publisher_types static, tallies from live data."""
    life_areas = set()
    org_types = set()
    publisher_types = {"individual": 0, "expert": 0, "organization": 0}
    async for d in db.decider_store_templates.find(
        {"status": "authorized", "is_public": True},
        {"_id": 0, "life_area": 1, "applicable_org_types": 1, "publisher_type": 1},
    ):
        if d.get("life_area"): life_areas.add(d["life_area"])
        for o in (d.get("applicable_org_types") or []):
            if isinstance(o, str) and o: org_types.add(o)
        pt = d.get("publisher_type")
        if pt in publisher_types: publisher_types[pt] += 1
    # Enrich org_types from masters if available
    try:
        async for m in db.masters.find({"kind": "org_type"}, {"_id": 0, "code": 1, "label": 1}):
            if m.get("code"): org_types.add(m["code"])
    except Exception:
        pass
    return {
        "life_areas": sorted(life_areas),
        "org_types": sorted(org_types),
        "publisher_types": [
            {"key": "individual",   "label": "Individual (Basic)",       "count": publisher_types["individual"]},
            {"key": "expert",       "label": "Expert (Pro)",             "count": publisher_types["expert"]},
            {"key": "organization", "label": "Organization (Premium)",   "count": publisher_types["organization"]},
        ],
    }


# ─────────────────────── Play-Store-style item ratings ───────────────────────
@router.get("/{item_id}/rating")
async def get_item_rating(item_id: str):
    """Public — returns aggregate rating stats for a store item."""
    agg = await db.store_item_ratings.aggregate([
        {"$match": {"item_id": item_id}},
        {"$group": {
            "_id": "$item_id",
            "count": {"$sum": 1},
            "usefulness_avg":   {"$avg": "$usefulness"},
            "affordability_avg":{"$avg": "$affordability"},
            "accuracy_avg":     {"$avg": "$accuracy"},
        }}
    ]).to_list(1)
    a = agg[0] if agg else {}
    overall = 0.0
    if a:
        overall = round((float(a.get("usefulness_avg") or 0) +
                         float(a.get("affordability_avg") or 0) +
                         float(a.get("accuracy_avg") or 0)) / 3.0, 2)
    return {
        "count": int(a.get("count") or 0),
        "overall": overall,
        "usefulness":    round(float(a.get("usefulness_avg") or 0), 2),
        "affordability": round(float(a.get("affordability_avg") or 0), 2),
        "accuracy":      round(float(a.get("accuracy_avg") or 0), 2),
    }


@router.get("/{item_id}/my-rating")
async def get_my_rating(item_id: str, user: dict = Depends(get_current_user)):
    r = await db.store_item_ratings.find_one({"item_id": item_id, "user_id": user["user_id"]}, {"_id": 0})
    if not r: return {"mine": None}
    return {"mine": {"usefulness": r.get("usefulness"), "affordability": r.get("affordability"), "accuracy": r.get("accuracy")}}


@router.post("/{item_id}/rate")
async def rate_item(item_id: str, body: Dict[str, Any], user: dict = Depends(get_current_user)):
    def _clamp(v):
        try: v = int(v)
        except: return None
        return max(1, min(5, v))
    u = _clamp(body.get("usefulness"))
    af = _clamp(body.get("affordability"))
    ac = _clamp(body.get("accuracy"))
    if u is None or af is None or ac is None:
        raise HTTPException(400, "Rate all three factors (usefulness, affordability, accuracy) from 1..5.")
    now = datetime.now(timezone.utc)
    await db.store_item_ratings.update_one(
        {"user_id": user["user_id"], "item_id": item_id},
        {"$set": {"usefulness": u, "affordability": af, "accuracy": ac, "updated_at": now},
         "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    # Denormalise aggregate onto the item doc for cheap sort/filter in list.
    agg = await db.store_item_ratings.aggregate([
        {"$match": {"item_id": item_id}},
        {"$group": {"_id": "$item_id", "count": {"$sum": 1},
                    "usefulness_avg":{"$avg":"$usefulness"},
                    "affordability_avg":{"$avg":"$affordability"},
                    "accuracy_avg":{"$avg":"$accuracy"}}}
    ]).to_list(1)
    if agg:
        a = agg[0]
        overall = round((float(a["usefulness_avg"]) + float(a["affordability_avg"]) + float(a["accuracy_avg"])) / 3.0, 2)
        await db.decider_store_templates.update_one(
            {"template_id": item_id},
            {"$set": {"rating_avg": overall, "rating_count": int(a["count"]),
                      "rating_usefulness_avg":   round(float(a["usefulness_avg"]), 2),
                      "rating_affordability_avg":round(float(a["affordability_avg"]), 2),
                      "rating_accuracy_avg":     round(float(a["accuracy_avg"]), 2)}}
        )
    return {"message": "Rating saved. Thanks!"}


@router.get("/meta")
async def store_meta():
    docs = await db.decider_store_templates.find(
        {"status": "authorized", "is_public": True}, {"category": 1, "_id": 0}
    ).to_list(500)
    cats: Dict[str, int] = {}
    for d in docs:
        c = d.get("category") or "General"
        cats[c] = cats.get(c, 0) + 1
    return {"categories": [{"key": k, "count": v} for k, v in sorted(cats.items())],
            "total": len(docs)}


@router.get("/import-template.xlsx")
async def download_import_template(sample: bool = True):
    """Downloadable XLSX authoring template (public so it's easy to grab)."""
    data = build_import_template_xlsx(sample=sample)
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="decider_store_import_template.xlsx"'},
    )


# ── TheDecider.store landing page (admin-editable content) ─────────────────
_LANDING_DEFAULT = {
    "title": "The Decider Store",
    "subtitle": "Decider Apps & Templates for every big decision",
    "hero": ("Find your best business model, property, freelancer and more — ranked by "
             "YOUR priorities, expectations and realistic gap-adjusted ratings."),
    "cta_label": "Explore Decider Apps",
    "cta_target": "https://jelcos.ai/decider-store",
    "brand_color": "#4F46E5",
}


async def _get_landing() -> Dict[str, Any]:
    doc = await db.decider_store_config.find_one({"key": "landing"}, {"_id": 0})
    cfg = dict(_LANDING_DEFAULT)
    if doc:
        for k in _LANDING_DEFAULT:
            if doc.get(k) not in (None, ""):
                cfg[k] = doc[k]
    return cfg


@router.get("/landing")
async def get_landing():
    return await _get_landing()


@router.put("/landing")
async def update_landing(request: Request, user: dict = Depends(get_current_user)):
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    body = await request.json()
    patch = {k: str(body[k]).strip() for k in _LANDING_DEFAULT if k in body}
    patch["key"] = "landing"
    patch["updated_at"] = _now()
    patch["updated_by"] = user.get("email") or user["user_id"]
    await db.decider_store_config.update_one({"key": "landing"}, {"$set": patch}, upsert=True)
    return await _get_landing()


@router.get("/landing.html")
async def landing_html():
    """Self-contained landing page for TheDecider.store. 'Explore' opens the
    storefront in a masked full-screen iframe (URL stays on TheDecider.store)."""
    c = await _get_landing()
    import html as _html
    t = _html.escape(c["title"]); sub = _html.escape(c["subtitle"])
    hero = _html.escape(c["hero"]); cta = _html.escape(c["cta_label"])
    target = _html.escape(c["cta_target"]); color = _html.escape(c["brand_color"])
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{t}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:#0B1020;color:#fff}}
.wrap{{min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:32px;
background:radial-gradient(1200px 600px at 50% -10%, {color}55, transparent), #0B1020}}
.badge{{width:64px;height:64px;border-radius:18px;background:{color};display:flex;align-items:center;justify-content:center;font-size:30px;margin-bottom:22px}}
h1{{font-size:clamp(28px,6vw,52px);font-weight:900;letter-spacing:-.5px}}
h2{{font-size:clamp(15px,3vw,20px);font-weight:600;color:#C7D2FE;margin-top:10px}}
p.hero{{max-width:640px;font-size:clamp(14px,2.4vw,18px);color:#94A3B8;margin-top:18px;line-height:1.6}}
.cta{{margin-top:34px;background:{color};color:#fff;border:none;font-size:17px;font-weight:800;padding:16px 30px;border-radius:14px;cursor:pointer;box-shadow:0 12px 30px {color}66}}
.cta:hover{{filter:brightness(1.08)}}
#frame{{position:fixed;inset:0;width:100%;height:100%;border:0;display:none;background:#fff;z-index:9}}
#back{{position:fixed;top:14px;left:14px;z-index:10;display:none;background:rgba(15,23,42,.85);color:#fff;border:0;border-radius:10px;padding:9px 14px;font-weight:700;cursor:pointer}}
.foot{{margin-top:40px;color:#475569;font-size:12px}}
</style></head><body>
<div class="wrap" id="landing">
  <div class="badge">🧭</div>
  <h1>{t}</h1>
  <h2>{sub}</h2>
  <p class="hero">{hero}</p>
  <button class="cta" onclick="openStore()">{cta} →</button>
  <div class="foot">Powered by JELCOS AI</div>
</div>
<button id="back" onclick="closeStore()">← Back</button>
<iframe id="frame" title="Decider Apps"></iframe>
<script>
function openStore(){{var f=document.getElementById('frame');f.src='{target}';f.style.display='block';
document.getElementById('back').style.display='block';document.getElementById('landing').style.display='none';}}
function closeStore(){{var f=document.getElementById('frame');f.style.display='none';f.src='';
document.getElementById('back').style.display='none';document.getElementById('landing').style.display='flex';}}
</script></body></html>"""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=page)


# ══════════════════════════════════════════════════════════════════════════
# ADMIN — author / import / authorize
# ══════════════════════════════════════════════════════════════════════════
@router.get("/admin/all")
async def admin_list_all(user: dict = Depends(get_current_user)):
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    docs = await db.decider_store_templates.find({}).sort("created_at", -1).to_list(500)
    for d in docs:
        d.pop("_id", None)
    return {"templates": docs}


@router.post("/import/excel")
async def import_excel(request: Request, user: dict = Depends(get_current_user)):
    """Parse an uploaded XLSX (base64) -> preview {factors, options}. Not saved."""
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    body = await request.json()
    b64 = body.get("file_b64") or ""
    if "," in b64 and b64.strip().startswith("data:"):
        b64 = b64.split(",", 1)[1]
    try:
        data = base64.b64decode(b64)
        parsed = parse_import(data=data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"Could not read the Excel file: {str(e)[:150]}")
    return parsed


@router.post("/import/gsheet")
async def import_gsheet(request: Request, user: dict = Depends(get_current_user)):
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    body = await request.json()
    csv_url = gsheet_to_csv_url(body.get("sheet_url") or "")
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=25) as client:
            resp = await client.get(csv_url)
        if resp.status_code != 200 or "html" in resp.headers.get("content-type", "").lower():
            raise HTTPException(400, "Could not read the sheet as CSV. Make it link-shareable "
                                     "(Anyone with the link) or 'Publish to web'.")
        parsed = parse_import(csv_text=resp.text)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"Failed to fetch/parse the sheet: {str(e)[:150]}")
    return parsed


@router.post("/import/factor-group-sheet")
async def import_factor_group_sheet(request: Request, user: dict = Depends(get_current_user)):
    """Import a row-per-factor XLSX with 1-3 level Factor Group columns
    (e.g., IndusInd Current Account sheet).

    Body: {file_b64: "..."}
    Returns: {factors[], options[], warnings[]} — preview only, not saved.
    Combine with `POST /decider-store` (kind='app') to publish.
    """
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    body = await request.json()
    b64 = body.get("file_b64") or ""
    try:
        return parse_factor_group_b64(b64)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"Could not read the Excel file: {str(e)[:150]}")


@router.post("")
async def create_template(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    is_admin = _is_admin(user)
    modes = [m for m in (body.get("allowed_clone_modes") or ["full", "values_only"]) if m in CLONE_MODES]
    pricing = (body.get("pricing_type") or "free").lower()
    if pricing not in ("free", "paid"):
        pricing = "free"
    kind = (body.get("kind") or "template").lower()
    if kind not in ("template", "app"):
        kind = "template"
    doc = {
        "template_id": str(uuid.uuid4()),
        "title": (body.get("title") or "Untitled Template").strip(),
        "subtitle": body.get("subtitle") or "",
        "description": body.get("description") or "",
        "category": body.get("category") or "General",
        "decision_type": body.get("decision_type") or "aspiration",
        "cover_icon": body.get("cover_icon") or "grid",
        "cover_color": body.get("cover_color") or "#4F46E5",
        "kind": kind,
        "finder_settings": _clean_finder_settings(body.get("finder_settings")),
        "catalog_node_id": (body.get("catalog_node_id") or None),
        "pricing_type": pricing,
        "price_paise": int(body.get("price_paise") or 0),
        "currency": body.get("currency") or "INR",
        "creator_split_pct": int(body.get("creator_split_pct") or 70),
        "allowed_clone_modes": modes or ["full", "values_only"],
        "auto_push_on_authorize": bool(body.get("auto_push_on_authorize", False)),
        "factors": body.get("factors") or [],
        "options": body.get("options") or [],
        "created_by": user["user_id"],
        "creator_name": user.get("name") or "",
        "source": "admin" if is_admin else "user",
        # Admin-created -> authorized+public immediately; user-created -> pending.
        "status": "authorized" if is_admin else "pending",
        "is_public": bool(is_admin),
        "install_count": 0,
        "created_at": _now(),
        "updated_at": _now(),
        "authorized_at": _now() if is_admin else None,
        "authorized_by": user["user_id"] if is_admin else None,
    }
    await db.decider_store_templates.insert_one(doc)
    return {"template_id": doc["template_id"], "status": doc["status"],
            "is_public": doc["is_public"]}


@router.put("/{template_id}")
async def update_template(template_id: str, request: Request, user: dict = Depends(get_current_user)):
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    body = await request.json()
    allowed = ["title", "subtitle", "description", "category", "decision_type",
               "cover_icon", "cover_color", "pricing_type", "price_paise", "currency",
               "creator_split_pct", "allowed_clone_modes", "factors", "options", "is_public",
               "auto_push_on_authorize", "kind", "finder_settings", "catalog_node_id",
               "lead_gen", "policies"]
    update = {k: body[k] for k in allowed if k in body}
    if "kind" in update and update["kind"] not in ("template", "app"):
        update["kind"] = "template"
    if "finder_settings" in update:
        update["finder_settings"] = _clean_finder_settings(update["finder_settings"])
    if "allowed_clone_modes" in update:
        update["allowed_clone_modes"] = [m for m in update["allowed_clone_modes"] if m in CLONE_MODES] or ["full"]
    update["updated_at"] = _now()
    res = await db.decider_store_templates.update_one({"template_id": template_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Template not found")
    return {"message": "updated"}


@router.post("/{template_id}/authorize")
async def authorize_template(template_id: str, user: dict = Depends(get_current_user)):
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    t = await db.decider_store_templates.find_one({"template_id": template_id})
    if not t:
        raise HTTPException(404, "Template not found")
    await db.decider_store_templates.update_one(
        {"template_id": template_id},
        {"$set": {"status": "authorized", "is_public": True,
                  "authorized_at": _now(), "authorized_by": user["user_id"], "updated_at": _now()}},
    )
    pushed = None
    if t.get("auto_push_on_authorize"):
        t["status"] = "authorized"
        pushed = await _push_template_to_stores(t, user)
    return {"message": "authorized", "auto_pushed": pushed}


@router.post("/{template_id}/unpublish")
async def unpublish_template(template_id: str, user: dict = Depends(get_current_user)):
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    await db.decider_store_templates.update_one(
        {"template_id": template_id}, {"$set": {"is_public": False, "updated_at": _now()}})
    return {"message": "unpublished"}


@router.delete("/{template_id}")
async def delete_template(template_id: str, user: dict = Depends(get_current_user)):
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    res = await db.decider_store_templates.delete_one({"template_id": template_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Template not found")
    return {"message": "deleted"}


# ══════════════════════════════════════════════════════════════════════════
# PUBLIC detail (kept AFTER admin routes so /admin, /meta, /import* win)
# ══════════════════════════════════════════════════════════════════════════
@router.get("/{template_id}")
async def get_template(template_id: str):
    t = await db.decider_store_templates.find_one({"template_id": template_id}, {"_id": 0})
    if not t or not (t.get("status") == "authorized" and t.get("is_public")):
        raise HTTPException(404, "Template not found")
    t.pop("created_by", None)
    return t


# ══════════════════════════════════════════════════════════════════════════
# CLONE (login required) -> new MyDezider decision, prefilled
# ══════════════════════════════════════════════════════════════════════════
def _fmt_value_text(vals: List[Dict[str, Any]]) -> str:
    """Legacy [{value,pct}] -> 'Solo (100%), Startup (40%)' text."""
    parts = []
    for v in vals:
        pct = v.get("pct")
        parts.append(f"{v.get('value')} ({int(pct)}%)" if pct not in (None, 100, 100.0)
                     else str(v.get("value")))
    return ", ".join(parts)


def _sf_list(f: Dict[str, Any]) -> List[Dict[str, Any]]:
    """A factor's sub-factors; synthesize one for legacy factors without any."""
    subs = f.get("sub_factors")
    if subs:
        return subs
    return [{"id": f.get("id"), "name": f.get("name"),
             "data_type": f.get("data_type") or "Text", "split_pct": 100}]


def _val_raw(v: Any) -> str:
    if isinstance(v, dict):
        return str(v.get("raw", ""))
    if isinstance(v, list):  # legacy [{value,pct}]
        return _fmt_value_text(v)
    return "" if v is None else str(v)


def _val_num(v: Any):
    if isinstance(v, dict):
        return v.get("num")
    if isinstance(v, list):
        return _best_pct(v)
    return None


def _dt_map(dt: Any) -> str:
    return "text" if str(dt or "").strip().lower().startswith("text") else "numeric"


def _cat_map(cat: Any) -> str:
    c = str(cat or "").strip().lower()
    if c.startswith("mand"):
        return "primary"
    if c.startswith("opt"):
        return "secondary"
    return "primary"


def _build_decision_from_template(t: Dict[str, Any], mode: str, user: dict) -> Dict[str, Any]:
    """Clone -> MyDezider decision. Each MAIN factor becomes a top-level factor;
    its sub-factors become native child factors (parent_id + weight=split_pct)."""
    full = (mode == "full")
    factors_out: List[Dict[str, Any]] = []
    sid_to_fid: Dict[str, str] = {}          # template sub-factor id -> MyDezider factor id
    order = 0
    for f in t.get("factors") or []:
        subs = _sf_list(f)
        # "real" sub-factors = an explicit list that isn't just the factor itself
        raw_subs = f.get("sub_factors") or []
        has_real_subs = bool(raw_subs) and (
            len(raw_subs) > 1 or (raw_subs[0].get("name") or "") != (f.get("name") or ""))
        parent_id = str(uuid.uuid4())
        cat = _cat_map(f.get("category")) if full else ""
        factors_out.append({
            "id": parent_id,
            "name": f.get("name") or "Factor",
            "order": order,
            "category": cat,                                   # '' for values_only -> user classifies
            "rating": (int(f.get("priority") or 0)) if full else 0,
            "gap_multiplier": 1.0,
            "factor_type": f.get("factor_type") or "qualitative",
            "data_type": "numeric",
            # Dynamic UI (v2): checkbox / radio / dropdown / listbox / None
            "ui_object": f.get("ui_object") or None,
        })
        order += 1
        if has_real_subs:
            for si, sf in enumerate(subs):
                cid = str(uuid.uuid4())
                sid_to_fid[sf.get("id")] = cid
                is_pct = str(sf.get("data_type") or "").strip() == "%"
                factors_out.append({
                    "id": cid,
                    "name": sf.get("name") or "Sub-factor",
                    "order": si,
                    "category": cat,
                    "rating": 0,
                    "gap_multiplier": 1.0,
                    "parent_id": parent_id,
                    "weight": float(sf.get("split_pct") or 0),
                    "factor_type": f.get("factor_type") or "qualitative",
                    "data_type": _dt_map(sf.get("data_type")),
                    "unit": "%" if is_pct else "",
                    # Option-Bank join key (bank `vals` are keyed by the
                    # ORIGINAL template sub-factor id).
                    "source_sub_id": sf.get("id"),
                    # Column role (v2): value | sub | dependent
                    "role": sf.get("role") or ("value" if f.get("ui_object") else None),
                    "linked_value": sf.get("linked_value") or None,
                    "default_operator": sf.get("default_operator") or None,
                    "default_expected": sf.get("default_expected"),
                })
        else:
            # single implicit sub-factor -> maps straight onto the parent
            sid_to_fid[subs[0].get("id")] = parent_id
            factors_out[-1]["source_sub_id"] = subs[0].get("id")

    options_out: List[Dict[str, Any]] = []
    for opt in t.get("options") or []:
        assessments = []
        for old_sid, v in (opt.get("values") or {}).items():
            fid = sid_to_fid.get(old_sid)
            if not fid:
                continue
            num = _val_num(v)
            # %-type sub-factor value doubles as the prefilled suitability %.
            pct = None
            if num is not None:
                pct = max(0.0, min(100.0, float(num)))
            assessments.append({
                "factor_id": fid,
                "percentage": pct,
                "unit_value": _val_raw(v),
                "actual_value": num,
            })
        options_out.append({
            "id": str(uuid.uuid4()),
            "name": opt.get("name") or "Option",
            "assessments": assessments,
            "worth_percentage": 0.0,
            "source": "store",
            "ai_rationale": opt.get("description") or opt.get("remarks") or "",
        })

    return {
        "id": str(uuid.uuid4()),
        "user_id": user["user_id"],
        "org_id": user.get("org_id"),
        "title": t.get("title") or "Decision",
        "context": t.get("description") or "",
        "factors": factors_out,
        "options": options_out,
        "chosen_option_id": None,
        "decision_case": None,
        "notes": "",
        "reflection": "",
        "final_notes": "",
        "folder": "",
        "life_area": t.get("category"),
        "decision_type": t.get("decision_type"),
        "rating_gap_multiplier": 1.0,
        "status": "draft",
        "source_template_id": t.get("template_id"),
        "source": "decider_store",
        "clone_mode": mode,
        # DeciderApp (Finder) vs plain Decision Template
        "decider_kind": ("app" if (t.get("kind") == "app") else "template"),
        "finder_config": t.get("finder_settings") or {},
        "created_at": _now(),
        "updated_at": _now(),
    }


@router.post("/{template_id}/clone")
async def clone_template(template_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    mode = (body.get("mode") or "full").lower()
    if mode not in CLONE_MODES:
        mode = "full"
    t = await db.decider_store_templates.find_one({"template_id": template_id}, {"_id": 0})
    if not t or not (t.get("status") == "authorized" and t.get("is_public")):
        raise HTTPException(404, "Template not found")
    if mode not in (t.get("allowed_clone_modes") or ["full", "values_only"]):
        raise HTTPException(400, f"This template does not allow '{mode}' cloning.")

    # Paid templates require entitlement (fulfillment wired in Phase 2).
    if (t.get("pricing_type") == "paid") and (int(t.get("price_paise") or 0) > 0):
        raise HTTPException(
            status_code=402,
            detail={"message": "This is a paid template.",
                    "price_paise": t.get("price_paise"), "currency": t.get("currency") or "INR",
                    "creator_split_pct": t.get("creator_split_pct", 70)},
        )

    decision = _build_decision_from_template(t, mode, user)
    await db.decisions.insert_one(decision)
    await db.decider_store_templates.update_one(
        {"template_id": template_id}, {"$inc": {"install_count": 1}})
    # AdTaker attribution — a `ref` tracker ID marks a publisher-driven install.
    ref = str(body.get("ref") or "").strip()
    if ref:
        try:
            from routes.adtaker import log_conversion
            await log_conversion(ref, template_id, {"decision_id": decision["id"], "mode": mode})
        except Exception:
            pass
    return {"decision_id": decision["id"], "mode": mode,
            "factors": len(decision["factors"]), "options": len(decision["options"])}


# ══════════════════════════════════════════════════════════════════════════
# STORE ⇄ REVIEWNET BRIDGE
# Each unique Option ↔ one Solution-Store solution (its QUANTITATIVE factor
# values) ↔ its ReviewNet baseline (its QUALITATIVE factor values). Linked by
# solution_id stored on the option (non-duplication). Qualitative values are
# stored BOTH as a categorical baseline_profile AND as a 1–5★ admin baseline.
# ══════════════════════════════════════════════════════════════════════════
def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").strip().lower()).strip("_") or "factor"


def _star_from_pct(pct) -> int:
    try:
        return max(1, min(5, round(float(pct) / 20.0)))
    except (TypeError, ValueError):
        return 5


def _best_pct(vals) -> float:
    ps = [v.get("pct", 100) for v in (vals or []) if v.get("pct") is not None]
    return max(ps) if ps else 100.0


async def _push_template_to_stores(t: dict, user: dict) -> dict:
    """Push each option → Solution Store (quant sub-factors) + ReviewNet baseline
    (qual sub-factors). Keyed by sub-factor id for a clean reverse-sync."""
    factors = t.get("factors") or []
    # sub-factor id -> (main factor, sub factor)
    sub_index: dict = {}
    for f in factors:
        for sf in _sf_list(f):
            sub_index[sf.get("id")] = (f, sf)

    def _is_quant(f):
        return (f.get("factor_type") or "qualitative") == "quantitative"

    def _label(f, sf):
        subs = f.get("sub_factors") or []
        return f"{f.get('name')} · {sf.get('name')}" if len(subs) > 1 else (f.get("name") or sf.get("name"))

    # Ensure a ReviewNet catalog factor per qualitative sub-factor.
    rf_for: dict = {}
    for sid, (f, sf) in sub_index.items():
        if _is_quant(f):
            continue
        rf_id = f"qf_decider_{_slug(f.get('name'))}_{_slug(sf.get('name'))}"
        rf_for[sid] = rf_id
        await db.review_factors.update_one(
            {"factor_id": rf_id},
            {"$set": {"factor_id": rf_id, "name": _label(f, sf), "slug": _slug(_label(f, sf)),
                      "scope_type": "global", "scope_id": None, "is_active": True,
                      "source": "decider_store", "updated_at": _now()},
             "$setOnInsert": {"created_at": _now()}},
            upsert=True,
        )

    options = t.get("options") or []
    solutions_out, reviews_out = 0, 0
    updated_options = []
    for opt in options:
        quant_factors_payload = []
        qual_profile: dict = {}
        factor_ratings: dict = {}
        for sid, v in (opt.get("values") or {}).items():
            fi = sub_index.get(sid)
            if not fi:
                continue
            f, sf = fi
            raw, num = _val_raw(v), _val_num(v)
            label = _label(f, sf)
            if _is_quant(f):
                quant_factors_payload.append({
                    "factor_id": sid, "name": label, "value": raw, "unit": "",
                    "num": num, "data_type": sf.get("data_type") or "Number",
                })
            else:
                qual_profile[sid] = {"name": label, "value": raw, "num": num}
                factor_ratings[rf_for.get(sid, f"qf_decider_{_slug(label)}")] = _star_from_pct(
                    num if num is not None else 100)

        sol_id = opt.get("linked_solution_id") or str(uuid.uuid4())
        sol_doc = {
            "solution_id": sol_id,
            "type": "STRATEGY",
            "name": opt.get("name") or "Option",
            "description": opt.get("description") or opt.get("remarks") or "",
            "visibility": "PUBLIC",
            "approval_status": "approved",
            "is_authorized": True,
            "status": "active",
            "provider": opt.get("exemplary_companies") or "",
            "tags": [t.get("category")] if t.get("category") else [],
            "quantitative_factors": quant_factors_payload,
            "type_specific": {"affected_components": opt.get("affected_components") or "",
                              "strategy_type": t.get("title") or ""},
            "org_types": [], "decision_types": [t.get("decision_type")] if t.get("decision_type") else [],
            "currency": t.get("currency") or "INR",
            # cross-links (non-duplication + "Open in Decider Store")
            "source": "decider_store",
            "decider_template_id": t.get("template_id"),
            "decider_option_id": opt.get("id"),
            "created_by": user["user_id"],
            "created_by_name": user.get("name") or "",
            "org_id": user.get("org_id"),
            "updated_at": _now(),
        }
        existing = await db.solutions_store.find_one({"solution_id": sol_id}, {"created_at": 1})
        sol_doc["created_at"] = (existing or {}).get("created_at", _now())
        await db.solutions_store.replace_one({"solution_id": sol_id}, sol_doc, upsert=True)
        solutions_out += 1

        opt["linked_solution_id"] = sol_id
        updated_options.append(opt)

        if factor_ratings or qual_profile:
            rv_id = f"rv_baseline_{sol_id}"
            avg = round(sum(factor_ratings.values()) / len(factor_ratings), 2) if factor_ratings else 5.0
            await db.review_net.update_one(
                {"review_id": rv_id},
                {"$set": {
                    "review_id": rv_id, "solution_id": sol_id, "solution_name": opt.get("name"),
                    "reviewer_id": "decider_baseline", "reviewer_name": "Decider Baseline",
                    "reviewer_segment": "authoritative", "reviewer_subsegment": None,
                    "factor_ratings": factor_ratings, "overall_rating": avg,
                    "baseline_profile": qual_profile, "is_baseline": True,
                    "status": "approved", "moderation_action": "AUTO_APPROVE",
                    "source": "decider_store", "source_template_id": t.get("template_id"),
                    "source_option_id": opt.get("id"), "updated_at": _now(),
                }, "$setOnInsert": {"created_at": _now()}},
                upsert=True,
            )
            reviews_out += 1

    await db.decider_store_templates.update_one(
        {"template_id": t.get("template_id")},
        {"$set": {"options": updated_options, "pushed_to_stores_at": _now(), "updated_at": _now()}})
    return {"solutions": solutions_out, "reviews": reviews_out}


@router.post("/{template_id}/push-to-stores")
async def push_to_stores(template_id: str, user: dict = Depends(get_current_user)):
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    t = await db.decider_store_templates.find_one({"template_id": template_id})
    if not t:
        raise HTTPException(404, "Template not found")
    res = await _push_template_to_stores(t, user)
    return {"message": "pushed", **res}


@router.post("/{template_id}/sync-from-stores")
async def sync_from_stores(template_id: str, user: dict = Depends(get_current_user)):
    """Pull latest quant (Solution Store) + qual baseline (ReviewNet) back into
    the template options (reverse of push)."""
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    t = await db.decider_store_templates.find_one({"template_id": template_id}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Template not found")
    factors = t.get("factors") or []
    valid_sids = {sf.get("id") for f in factors for sf in _sf_list(f)}
    synced = 0
    options = t.get("options") or []
    for opt in options:
        sol_id = opt.get("linked_solution_id")
        if not sol_id:
            continue
        sol = await db.solutions_store.find_one({"solution_id": sol_id}, {"_id": 0})
        if not sol:
            continue
        vals = dict(opt.get("values") or {})
        # quantitative back from solution (factor_id == sub-factor id)
        for qf in sol.get("quantitative_factors") or []:
            sid = qf.get("factor_id")
            if sid and sid in valid_sids:
                vals[sid] = {"raw": _val_raw(qf.get("value")), "num": qf.get("num")}
        # qualitative back from ReviewNet baseline (keyed by sub-factor id)
        baseline = await db.review_net.find_one(
            {"review_id": f"rv_baseline_{sol_id}"}, {"_id": 0, "baseline_profile": 1})
        for sid, entry in ((baseline or {}).get("baseline_profile") or {}).items():
            if sid in valid_sids and isinstance(entry, dict):
                vals[sid] = {"raw": _val_raw(entry.get("value")), "num": entry.get("num")}
        opt["values"] = vals
        synced += 1
    await db.decider_store_templates.update_one(
        {"template_id": template_id},
        {"$set": {"options": options, "synced_from_stores_at": _now(), "updated_at": _now()}})
    return {"message": "synced", "options": synced}


@router.post("/from-solutions")
async def create_template_from_solutions(request: Request, user: dict = Depends(get_current_user)):
    """Build a NEW Decider template from a set of Solution-Store solutions
    (their quantitative_factors) + their ReviewNet baselines (qualitative)."""
    if not _is_admin(user):
        raise HTTPException(403, "Admin access required")
    body = await request.json()
    solution_ids = body.get("solution_ids") or []
    if not solution_ids:
        raise HTTPException(400, "solution_ids required")
    sols = await db.solutions_store.find({"solution_id": {"$in": solution_ids}}, {"_id": 0}).to_list(500)
    if not sols:
        raise HTTPException(404, "No matching solutions")

    # Build the factor set: quantitative from solutions, qualitative from baselines.
    # Each becomes a main factor with a single sub-factor (uniform new model).
    factors: list = []
    sid_by_name: dict = {}   # source name -> its sub-factor id

    def _ensure_factor(name: str, ftype: str) -> str:
        if name in sid_by_name:
            return sid_by_name[name]
        sid = str(uuid.uuid4())
        sid_by_name[name] = sid
        factors.append({
            "id": str(uuid.uuid4()), "name": name, "order": len(factors),
            "factor_type": ftype, "category": "", "priority": len(factors) + 1,
            "sub_factors": [{"id": sid, "name": name, "order": 0,
                             "data_type": "Number" if ftype == "quantitative" else "%",
                             "ui_object": "Input Box", "split_pct": 100}],
            "possible_values": [name],
        })
        return sid

    baselines: dict = {}
    for sol in sols:
        b = await db.review_net.find_one({"review_id": f"rv_baseline_{sol['solution_id']}"}, {"_id": 0})
        if b:
            baselines[sol["solution_id"]] = b
        for qf in sol.get("quantitative_factors") or []:
            if qf.get("name"):
                _ensure_factor(qf["name"], "quantitative")
        for entry in ((b or {}).get("baseline_profile") or {}).values():
            nm = entry.get("name") if isinstance(entry, dict) else None
            if nm:
                _ensure_factor(nm, "qualitative")

    options: list = []
    for sol in sols:
        vals: dict = {}
        for qf in sol.get("quantitative_factors") or []:
            if qf.get("name") in sid_by_name:
                vals[sid_by_name[qf["name"]]] = {"raw": _val_raw(qf.get("value")), "num": qf.get("num")}
        for entry in (baselines.get(sol["solution_id"], {}).get("baseline_profile") or {}).values():
            nm = entry.get("name") if isinstance(entry, dict) else None
            if nm and nm in sid_by_name:
                vals[sid_by_name[nm]] = {"raw": _val_raw(entry.get("value")), "num": entry.get("num")}
        options.append({
            "id": str(uuid.uuid4()), "name": sol.get("name") or "Option",
            "description": sol.get("description") or "",
            "exemplary_companies": sol.get("provider") or "",
            "affected_components": (sol.get("type_specific") or {}).get("affected_components") or "",
            "remarks": "", "product_model": "",
            "values": vals, "linked_solution_id": sol["solution_id"],
        })

    doc = {
        "template_id": str(uuid.uuid4()),
        "title": (body.get("title") or "Template from Solution Store").strip(),
        "subtitle": body.get("subtitle") or "",
        "description": body.get("description") or "",
        "category": body.get("category") or "General",
        "decision_type": body.get("decision_type") or "aspiration",
        "cover_icon": body.get("cover_icon") or "git-compare",
        "cover_color": body.get("cover_color") or "#0369A1",
        "pricing_type": "free", "price_paise": 0, "currency": "INR", "creator_split_pct": 70,
        "allowed_clone_modes": ["full", "values_only"], "auto_push_on_authorize": False,
        "factors": factors, "options": options,
        "created_by": user["user_id"], "creator_name": user.get("name") or "",
        "source": "solution_store", "status": "authorized", "is_public": True,
        "install_count": 0, "created_at": _now(), "updated_at": _now(),
        "authorized_at": _now(), "authorized_by": user["user_id"],
    }
    await db.decider_store_templates.insert_one(doc)
    return {"template_id": doc["template_id"], "factors": len(factors), "options": len(options)}
