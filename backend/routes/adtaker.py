"""AdTaker Program — AdSense/GDN-style embeddable Decider App widgets.

Any 3rd-party site ("publisher") can embed a Decider App as a widget with a
tracker ID (DZ-PUB-XXXXXXXX). We measure impressions / clicks / conversions
per tracker and the publisher earns a revenue share (default from the global
`adtaker_default_share_pct`).

Publisher identity — BOTH rails enabled:
  • API Key + Secret (minted at creation, secret shown ONCE, stored sha256-
    hashed) → self-serve API under /adtaker/self/* with X-Adtaker-Key/-Secret
    headers. No login required (AdSense-style).
  • Org login portal → publishers linked to an organization (`org_id`) are
    visible to that org's logged-in members at /adtaker/portal/me.

Routes (under /api):
  Admin:
    GET    /adtaker/publishers                      list + lifetime totals
    POST   /adtaker/publishers                      create (mints tracker + keys)
    PUT    /adtaker/publishers/{publisher_id}       update (incl. org link)
    POST   /adtaker/publishers/{publisher_id}/rotate-keys
    DELETE /adtaker/publishers/{publisher_id}       delete
    GET    /adtaker/publishers/{publisher_id}/stats daily series + earnings est.
  Publisher self-serve (API key + secret headers):
    GET    /adtaker/self/profile · /adtaker/self/stats · /adtaker/self/apps
  Org portal (session auth):
    GET    /adtaker/portal/me
  Public (no auth — served to 3rd-party pages):
    GET    /adtaker/widget.js?tracker=&app=         drop-in <script> loader
    GET    /adtaker/embed/{template_id}?tracker=    self-contained HTML card
    POST   /adtaker/track                           impression|click|conversion beacon
"""
from __future__ import annotations

import hashlib
import html as _html
import json
import secrets as _secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from core.auth import get_current_user, require_admin
from core.database import db
from routes.partner_embed_widget import _public_base

router = APIRouter(prefix="/adtaker", tags=["AdTaker Program"])

EVENTS = ("impression", "click", "conversion")
_IFRAME_HEADERS = {
    "X-Frame-Options": "ALLOWALL",
    "Content-Security-Policy": "frame-ancestors *",
    "Cache-Control": "no-store",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mint_tracker() -> str:
    return f"DZ-PUB-{uuid.uuid4().hex[:8].upper()}"


def _mint_keys() -> tuple:
    """(api_key, api_secret) — key is public, secret is shown ONCE."""
    return f"dzk_{_secrets.token_hex(8)}", f"dzs_{_secrets.token_hex(24)}"


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


async def _pub_by_tracker(tracker: str) -> Optional[Dict[str, Any]]:
    if not tracker:
        return None
    return await db.adtaker_publishers.find_one(
        {"tracker_id": tracker.strip(), "status": "active"}, {"_id": 0})


async def _log_event(pub: Dict[str, Any], template_id: str, event: str,
                     meta: Optional[Dict[str, Any]] = None) -> None:
    await db.adtaker_events.insert_one({
        "event_id": str(uuid.uuid4()), "tracker_id": pub["tracker_id"],
        "publisher_id": pub["publisher_id"], "template_id": template_id,
        "event": event, "meta": meta or {}, "ts": _now(),
    })


async def log_conversion(tracker_id: str, template_id: str,
                         meta: Optional[Dict[str, Any]] = None) -> bool:
    """Called by the store clone endpoint when a `ref` tracker is attributed."""
    pub = await _pub_by_tracker(tracker_id)
    if not pub:
        return False
    await _log_event(pub, template_id, "conversion", meta)
    return True


# ══════════════════════════════ admin CRUD ══════════════════════════════
@router.get("/publishers")
async def list_publishers(user: dict = Depends(require_admin)):
    pubs = await db.adtaker_publishers.find(
        {}, {"_id": 0, "api_secret_hash": 0}).sort("created_at", -1).to_list(500)
    rows = await db.adtaker_events.aggregate([
        {"$group": {"_id": {"t": "$tracker_id", "e": "$event"}, "n": {"$sum": 1}}}
    ]).to_list(3000)
    totals: Dict[str, Dict[str, int]] = {}
    for r in rows:
        t, e = r["_id"]["t"], r["_id"]["e"]
        totals.setdefault(t, {})[e] = r["n"]
    for p in pubs:
        t = totals.get(p["tracker_id"], {})
        p["totals"] = {"impressions": t.get("impression", 0),
                       "clicks": t.get("click", 0),
                       "conversions": t.get("conversion", 0)}
    return {"publishers": pubs}


@router.post("/publishers")
async def create_publisher(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    name = str(body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name is required")
    from core import ai_wallet
    cfg = await ai_wallet.get_config()
    try:
        share = float(body.get("revenue_share_pct")
                      if body.get("revenue_share_pct") is not None
                      else cfg.get("adtaker_default_share_pct", 68.0))
    except (TypeError, ValueError):
        raise HTTPException(400, "revenue_share_pct must be a number")
    if not (0 <= share <= 95):
        raise HTTPException(400, "revenue_share_pct must be 0-95")
    api_key, api_secret = _mint_keys()
    doc = {
        "publisher_id": f"pub_{uuid.uuid4().hex[:10]}",
        "tracker_id": _mint_tracker(),
        "api_key": api_key,
        "api_secret_hash": _hash_secret(api_secret),
        "name": name,
        "site_url": str(body.get("site_url") or "").strip(),
        "org_id": (str(body.get("org_id") or "").strip() or None),
        "revenue_share_pct": share,
        "status": "active",
        "created_by": user["user_id"], "created_at": _now(), "updated_at": _now(),
    }
    await db.adtaker_publishers.insert_one(doc)
    doc.pop("_id", None)
    doc.pop("api_secret_hash", None)
    # The ONLY time the secret is ever returned.
    doc["api_secret"] = api_secret
    return doc


@router.put("/publishers/{publisher_id}")
async def update_publisher(publisher_id: str, request: Request,
                           user: dict = Depends(require_admin)):
    body = await request.json()
    update: Dict[str, Any] = {}
    if body.get("name") is not None:
        update["name"] = str(body["name"]).strip()
    if body.get("site_url") is not None:
        update["site_url"] = str(body["site_url"]).strip()
    if "org_id" in body:
        update["org_id"] = (str(body.get("org_id") or "").strip() or None)
    if "org_id" in body:
        update["org_id"] = (str(body.get("org_id") or "").strip() or None)
    if body.get("revenue_share_pct") is not None:
        try:
            share = float(body["revenue_share_pct"])
        except (TypeError, ValueError):
            raise HTTPException(400, "revenue_share_pct must be a number")
        if not (0 <= share <= 95):
            raise HTTPException(400, "revenue_share_pct must be 0-95")
        update["revenue_share_pct"] = share
    if body.get("status") in ("active", "paused"):
        update["status"] = body["status"]
    if not update:
        raise HTTPException(400, "Nothing to update")
    update["updated_at"] = _now()
    res = await db.adtaker_publishers.update_one(
        {"publisher_id": publisher_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Publisher not found")
    return await db.adtaker_publishers.find_one(
        {"publisher_id": publisher_id}, {"_id": 0, "api_secret_hash": 0})


@router.post("/publishers/{publisher_id}/rotate-keys")
async def rotate_publisher_keys(publisher_id: str, user: dict = Depends(require_admin)):
    """Mint a fresh API key + secret (old pair stops working immediately).
    The new secret is returned ONCE."""
    api_key, api_secret = _mint_keys()
    res = await db.adtaker_publishers.update_one(
        {"publisher_id": publisher_id},
        {"$set": {"api_key": api_key, "api_secret_hash": _hash_secret(api_secret),
                  "updated_at": _now()}})
    if res.matched_count == 0:
        raise HTTPException(404, "Publisher not found")
    return {"publisher_id": publisher_id, "api_key": api_key, "api_secret": api_secret}


@router.delete("/publishers/{publisher_id}")
async def delete_publisher(publisher_id: str, user: dict = Depends(require_admin)):
    res = await db.adtaker_publishers.delete_one({"publisher_id": publisher_id})
    if res.deleted_count == 0:
        raise HTTPException(404, "Publisher not found")
    return {"message": "deleted"}


async def _stats_payload(pub: Dict[str, Any], days: int) -> Dict[str, Any]:
    days = max(1, min(365, int(days)))
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = await db.adtaker_events.aggregate([
        {"$match": {"tracker_id": pub["tracker_id"], "ts": {"$gte": since}}},
        {"$group": {"_id": {"d": {"$substrBytes": ["$ts", 0, 10]}, "e": "$event"},
                    "n": {"$sum": 1}}},
        {"$sort": {"_id.d": 1}},
    ]).to_list(3000)
    daily: Dict[str, Dict[str, int]] = {}
    totals = {"impressions": 0, "clicks": 0, "conversions": 0}
    key = {"impression": "impressions", "click": "clicks", "conversion": "conversions"}
    for r in rows:
        d, e = r["_id"]["d"], key.get(r["_id"]["e"])
        if not e:
            continue
        daily.setdefault(d, {"impressions": 0, "clicks": 0, "conversions": 0})[e] = r["n"]
        totals[e] += r["n"]
    from core import ai_wallet
    cfg = await ai_wallet.get_config()
    bounty = int(cfg.get("adtaker_conversion_bounty_paise", 500))
    earnings = int(round(totals["conversions"] * bounty * pub.get("revenue_share_pct", 68.0) / 100.0))
    ctr = round(totals["clicks"] / totals["impressions"] * 100.0, 2) if totals["impressions"] else 0.0
    pub_safe = {k: v for k, v in pub.items() if k != "api_secret_hash"}
    return {"publisher": pub_safe, "days": days, "totals": totals, "ctr_pct": ctr,
            "conversion_bounty_paise": bounty, "earnings_estimate_paise": earnings,
            "daily": [{"date": d, **v} for d, v in sorted(daily.items())]}


@router.get("/publishers/{publisher_id}/stats")
async def publisher_stats(publisher_id: str, days: int = 30,
                          user: dict = Depends(require_admin)):
    pub = await db.adtaker_publishers.find_one({"publisher_id": publisher_id}, {"_id": 0})
    if not pub:
        raise HTTPException(404, "Publisher not found")
    return await _stats_payload(pub, days)


# ═════════════ publisher self-serve (API key + secret, no login) ═════════════
async def _pub_by_keys(api_key: Optional[str], api_secret: Optional[str]) -> Dict[str, Any]:
    if not api_key or not api_secret:
        raise HTTPException(401, "X-Adtaker-Key and X-Adtaker-Secret headers required")
    pub = await db.adtaker_publishers.find_one({"api_key": api_key.strip()}, {"_id": 0})
    if not pub or pub.get("api_secret_hash") != _hash_secret(api_secret.strip()):
        raise HTTPException(401, "Invalid API key or secret")
    if pub.get("status") != "active":
        raise HTTPException(403, "Publisher account is paused")
    return pub


@router.get("/self/profile")
async def self_profile(x_adtaker_key: Optional[str] = Header(None),
                       x_adtaker_secret: Optional[str] = Header(None)):
    pub = await _pub_by_keys(x_adtaker_key, x_adtaker_secret)
    pub.pop("api_secret_hash", None)
    return pub


@router.get("/self/stats")
async def self_stats(days: int = 30, x_adtaker_key: Optional[str] = Header(None),
                     x_adtaker_secret: Optional[str] = Header(None)):
    pub = await _pub_by_keys(x_adtaker_key, x_adtaker_secret)
    return await _stats_payload(pub, days)


@router.get("/self/apps")
async def self_apps(request: Request, x_adtaker_key: Optional[str] = Header(None),
                    x_adtaker_secret: Optional[str] = Header(None)):
    """Embeddable Decider Apps + a ready-to-paste snippet per app."""
    pub = await _pub_by_keys(x_adtaker_key, x_adtaker_secret)
    root = _public_base(request)
    apps = await db.decider_store_templates.find(
        {"status": "authorized", "is_public": True},
        {"_id": 0, "template_id": 1, "title": 1, "subtitle": 1, "kind": 1,
         "install_count": 1}).sort("kind", 1).to_list(200)
    for a in apps:
        a["embed_snippet"] = (f'<script src="{root}/api/adtaker/widget.js'
                              f'?tracker={pub["tracker_id"]}&app={a["template_id"]}"></script>')
    return {"tracker_id": pub["tracker_id"], "apps": apps}


# ═══════════════════ org-login publisher portal (session) ═══════════════════
@router.get("/portal/me")
async def portal_me(days: int = 30, user: dict = Depends(get_current_user)):
    """Publishers linked to the caller's organization (org login rail)."""
    if not user.get("org_id"):
        raise HTTPException(403, "This portal is for organization accounts. "
                                 "Ask the admin to link your org to a publisher.")
    pubs = await db.adtaker_publishers.find(
        {"org_id": user["org_id"]}, {"_id": 0, "api_secret_hash": 0}).to_list(50)
    if not pubs:
        raise HTTPException(404, "No publisher is linked to your organization yet.")
    out = []
    for p in pubs:
        st = await _stats_payload(p, days)
        out.append({**p, "stats": {k: st[k] for k in
                                   ("totals", "ctr_pct", "earnings_estimate_paise", "daily")}})
    return {"publishers": out}


# ═══════════════════════ public widget delivery ═══════════════════════
@router.get("/widget.js")
async def widget_js(request: Request, tracker: str = "", app: str = ""):
    """Drop-in loader: <script src=".../api/adtaker/widget.js?tracker=DZ-PUB-…&app=<template_id>"></script>"""
    root = _public_base(request)
    js = f"""(function(){{
  var SELF = (document.currentScript && document.currentScript.src) || '';
  var BAKED = {json.dumps(root)};
  function root(){{ try {{ if (SELF) return new URL(SELF).origin; }} catch(e){{}} return BAKED; }}
  var R = root(), T = {json.dumps(tracker)}, A = {json.dumps(app)};
  if (!T || !A) return;
  var f = document.createElement('iframe');
  f.src = R + '/api/adtaker/embed/' + encodeURIComponent(A) + '?tracker=' + encodeURIComponent(T);
  f.style.cssText = 'width:100%;max-width:420px;height:400px;border:0;border-radius:16px;overflow:hidden;box-shadow:0 8px 28px rgba(2,6,23,.12);display:block';
  f.setAttribute('loading','lazy');
  f.title = 'Decider App';
  var sc = document.currentScript;
  if (sc && sc.parentNode) sc.parentNode.insertBefore(f, sc.nextSibling);
  else document.body.appendChild(f);
}})();"""
    return Response(content=js, media_type="application/javascript",
                    headers={"Cache-Control": "public, max-age=300"})


@router.get("/embed/{template_id}")
async def embed_card(template_id: str, request: Request, tracker: str = ""):
    pub = await _pub_by_tracker(tracker)
    if not pub:
        raise HTTPException(404, "Unknown or paused tracker ID")
    t = await db.decider_store_templates.find_one({"template_id": template_id}, {"_id": 0})
    if not t or not (t.get("status") == "authorized" and t.get("is_public")):
        raise HTTPException(404, "Decider App not found")
    await _log_event(pub, template_id, "impression",
                     {"referer": request.headers.get("referer", "")[:300]})

    root = _public_base(request)
    target = f"{root}/decider-store/{template_id}?ref={tracker}"
    title = _html.escape(t.get("title") or "Decider App")
    sub = _html.escape(t.get("subtitle") or t.get("description") or "")[:140]
    color = _html.escape(t.get("cover_color") or "#4F46E5")
    kind = "Decider App" if t.get("kind") == "app" else "Decision Template"
    nfac = len(t.get("factors") or [])
    nopt = len(t.get("options") or [])
    installs = int(t.get("install_count") or 0)
    api_root = f"{root}/api/adtaker/track"
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/><title>{title}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:#FFF}}
.card{{display:flex;flex-direction:column;height:100vh;border:1px solid #E2E8F0;border-radius:16px;overflow:hidden}}
.hero{{background:linear-gradient(135deg,{color},{color}CC);padding:20px 18px;color:#FFF}}
.pill{{display:inline-block;background:rgba(255,255,255,.22);border-radius:999px;padding:3px 10px;font-size:10.5px;font-weight:800;letter-spacing:.4px;text-transform:uppercase}}
h1{{font-size:19px;font-weight:900;margin-top:10px;line-height:1.25}}
p.sub{{font-size:12.5px;opacity:.92;margin-top:6px;line-height:1.45}}
.body{{flex:1;padding:14px 18px;display:flex;flex-direction:column}}
.meta{{display:flex;gap:14px;font-size:12px;color:#475569;font-weight:700}}
.meta b{{color:#0F172A}}
.cta{{margin-top:auto;background:{color};color:#FFF;border:0;border-radius:12px;padding:13px;font-size:14.5px;font-weight:800;cursor:pointer;width:100%}}
.cta:hover{{filter:brightness(1.08)}}
.foot{{text-align:center;font-size:10px;color:#94A3B8;padding:8px}}
</style></head><body>
<div class="card">
  <div class="hero"><span class="pill">{kind}</span><h1>{title}</h1><p class="sub">{sub}</p></div>
  <div class="body">
    <div class="meta"><span><b>{nfac}</b> factors</span><span><b>{nopt}</b> options</span><span><b>{installs}</b> installs</span></div>
    <button class="cta" onclick="go()">Open Decider App →</button>
  </div>
  <div class="foot">Ads by The Decider Store · AdTaker</div>
</div>
<script>
var T={json.dumps(tracker)},A={json.dumps(template_id)};
function go(){{
  try{{navigator.sendBeacon({json.dumps(api_root)},new Blob([JSON.stringify({{tracker:T,template_id:A,event:'click'}})],{{type:'application/json'}}));}}catch(e){{}}
  window.open({json.dumps(target)},'_blank');
}}
</script></body></html>"""
    return HTMLResponse(content=page, headers=_IFRAME_HEADERS)


@router.post("/track")
async def track_event(request: Request):
    """Public beacon: {tracker, template_id, event: impression|click|conversion}."""
    try:
        body = await request.json()
    except Exception:
        return {"ok": False}
    event = str(body.get("event") or "").strip().lower()
    if event not in EVENTS:
        raise HTTPException(400, f"event must be one of {EVENTS}")
    pub = await _pub_by_tracker(str(body.get("tracker") or ""))
    if not pub:
        raise HTTPException(404, "Unknown or paused tracker ID")
    await _log_event(pub, str(body.get("template_id") or ""), event,
                     {"referer": request.headers.get("referer", "")[:300]})
    return {"ok": True}

