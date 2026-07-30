"""
Admin-CRUDable Custom Landing Pages
====================================
Purpose: Marketing / event landing pages served at short jelcos.ai URLs like
`/tps`, `/sangamam`, `/launch` etc. Admin edits the HTML/CSS/JS + meta from
`/admin/landing-pages`. Public visitors fetch `/api/lp/{slug}` and the
Expo Router catch-all `app/[promo].tsx` renders the payload.

Endpoints:
  GET    /api/lp/{slug}                       PUBLIC — landing page payload
  GET    /api/admin/landing-pages             admin — list
  POST   /api/admin/landing-pages             admin — create
  PUT    /api/admin/landing-pages/{slug}      admin — update
  DELETE /api/admin/landing-pages/{slug}      admin — remove
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.database import db
from core.auth import require_super_admin

router = APIRouter(tags=["Landing Pages"])

# Slugs already claimed by other Expo Router files/segments — refuse to create
# a landing page with any of these names or it would be shadowed forever.
RESERVED_SLUGS = {
    "admin", "api", "auth", "quiz", "tools", "prr", "pricing", "contact",
    "legal", "p", "embed", "decider-store", "journal", "profile", "home",
    "solution-box", "whatsapp-verify", "trash", "subscription-plans",
    "test123", "settings", "docs", "about", "dashboard", "index", "share",
    "shared", "_layout", "not-found", "assets", "static",
}
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,39}$")


class LandingPageCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=40)
    title: str = Field(..., max_length=140)
    html: str = ""
    css: str = ""
    js: str = ""
    meta_description: str = Field("", max_length=280)
    meta_og_image: str = Field("", max_length=500)
    active: bool = True


class LandingPagePatch(BaseModel):
    title: Optional[str] = None
    html: Optional[str] = None
    css: Optional[str] = None
    js: Optional[str] = None
    meta_description: Optional[str] = None
    meta_og_image: Optional[str] = None
    active: Optional[bool] = None


def _validate_slug(slug: str) -> str:
    s = (slug or "").strip().lower()
    if not _SLUG_RE.match(s):
        raise HTTPException(400, "Slug must be 2–40 chars, lowercase letters/digits/hyphens, no leading hyphen.")
    if s in RESERVED_SLUGS:
        raise HTTPException(400, f"'{s}' is a reserved system path. Try a different slug.")
    return s


# ─────────────────── seed the first LP (Tamilpreneur Sangamam /tps) ───────────────────
_DEFAULT_TPS_HTML = """<div class=\"lp-wrap\">
  <div class=\"lp-hero\">
    <div class=\"lp-ribbon\">THE WAIT IS OVER — SANGAMAM #26 IS HERE!</div>
    <div class=\"lp-title-tam\">சங்கமம் <span class=\"lp-hash\">#26</span></div>
    <div class=\"lp-title-en\">Tamilpreneur Sangamam #26</div>
    <div class=\"lp-subtitle\">Startup Networking Event · Chennai</div>
    <div class=\"lp-divider\">◆ Launch &amp; Recognition ◆</div>
    <div class=\"lp-tagline\">Connecting Founders. Creating Opportunities.</div>
  </div>

  <div class=\"lp-detail-grid\">
    <div class=\"lp-detail-card\"><div class=\"lp-detail-ico\">📅</div><div><div class=\"lp-detail-label\">Date</div><div class=\"lp-detail-val\">1<sup>st</sup> Aug, 2026 · Saturday</div></div></div>
    <div class=\"lp-detail-card\"><div class=\"lp-detail-ico\">⏰</div><div><div class=\"lp-detail-label\">Time</div><div class=\"lp-detail-val\">3:00 PM – 7:00 PM</div></div></div>
    <div class=\"lp-detail-card\"><div class=\"lp-detail-ico\">📍</div><div><div class=\"lp-detail-label\">Venue</div><div class=\"lp-detail-val\">Bloom Hub, Guindy, Chennai</div></div></div>
    <div class=\"lp-detail-card lp-spots\"><div class=\"lp-detail-ico\">⭐</div><div><div class=\"lp-detail-label\">Limited</div><div class=\"lp-detail-val\">First 100 spots open now!</div></div></div>
  </div>

  <div class=\"lp-people\">
    <div class=\"lp-person\">
      <div class=\"lp-person-role\">Launched by</div>
      <div class=\"lp-person-name\">Shyam Siddarth</div>
      <div class=\"lp-person-org\">Founder, Tamilpreneur</div>
    </div>
    <div class=\"lp-app-card\">
      <div class=\"lp-app-name\">JELCOS AI</div>
      <div class=\"lp-app-sub\">A Decision Intelligence Platform</div>
      <div class=\"lp-app-for\">For Founders, Business Owners, CXOs &amp; Leaders</div>
    </div>
    <div class=\"lp-person\">
      <div class=\"lp-person-role\">Received by</div>
      <div class=\"lp-person-name\">Ad Shezhiyan Raj</div>
      <div class=\"lp-person-org\">Founder &amp; CEO, VEALES Vedic Decisions Pvt. Ltd.</div>
    </div>
  </div>

  <div class=\"lp-band\">சங்கமத்தில் சந்திப்போம்! ❤</div>

  <div class=\"lp-chips\">
    <div class=\"lp-chip\"><span class=\"lp-chip-ico\">🧠</span> AI Powered</div>
    <div class=\"lp-chip\"><span class=\"lp-chip-ico\">🎯</span> Smarter Decisions</div>
    <div class=\"lp-chip\"><span class=\"lp-chip-ico\">📈</span> Better Outcomes</div>
    <div class=\"lp-chip\"><span class=\"lp-chip-ico\">🪷</span> Conscious Living</div>
  </div>

  <div class=\"lp-cta-wrap\">
    <a class=\"lp-cta\" href=\"/auth/register?ref=tps\" id=\"lp-cta-primary\">Book Your Spot Now</a>
    <a class=\"lp-cta-secondary\" href=\"/quiz\">Try the free Decision-Style Quiz →</a>
  </div>

  <div class=\"lp-footer\">© 2026 Jelcos AI · Chennai · <a href=\"https://jelcos.ai\">jelcos.ai</a></div>
</div>"""

_DEFAULT_TPS_CSS = """.lp-wrap{max-width:900px;margin:0 auto;padding:24px 16px 48px;background:linear-gradient(180deg,#3d0a12 0%,#1a0409 55%,#2a0710 100%);color:#fff8ea;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;border-radius:16px}
.lp-hero{text-align:center;padding:24px 8px 8px}
.lp-ribbon{display:inline-block;background:linear-gradient(90deg,#c9a24e,#f2d36b);color:#3d0a12;font-weight:800;font-size:12px;letter-spacing:.5px;padding:6px 14px;border-radius:999px;margin-bottom:14px}
.lp-title-tam{font-size:52px;font-weight:900;color:#f7e4a8;text-shadow:0 2px 8px rgba(0,0,0,.5);line-height:1;margin:6px 0}
.lp-hash{color:#e11d48}
.lp-title-en{font-size:15px;color:#f7e4a8;opacity:.85;letter-spacing:1.2px;text-transform:uppercase;margin-top:4px}
.lp-subtitle{font-size:14px;color:#f7e4a8;opacity:.75;margin-top:2px}
.lp-divider{color:#c9a24e;margin:16px 0 6px;letter-spacing:2px;font-size:13px}
.lp-tagline{color:#f7e4a8;font-size:14px;font-style:italic;opacity:.9;margin-bottom:8px}
.lp-detail-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin:22px 0}
.lp-detail-card{background:rgba(255,255,255,.06);border:1px solid rgba(201,162,78,.35);border-radius:12px;padding:12px;display:flex;gap:10px;align-items:center;backdrop-filter:blur(6px)}
.lp-detail-ico{font-size:22px}
.lp-detail-label{color:#c9a24e;font-size:10px;font-weight:800;letter-spacing:1px;text-transform:uppercase}
.lp-detail-val{color:#fff;font-size:13px;font-weight:600;margin-top:2px}
.lp-spots{background:linear-gradient(90deg,rgba(225,29,72,.15),rgba(201,162,78,.15));border-color:#e11d48}
.lp-people{display:grid;grid-template-columns:1fr;gap:12px;margin:20px 0}
@media(min-width:720px){.lp-people{grid-template-columns:1fr 1.15fr 1fr;align-items:center}}
.lp-person{background:rgba(0,0,0,.35);border:1px solid #c9a24e88;border-radius:12px;padding:14px;text-align:center}
.lp-person-role{color:#c9a24e;font-size:10px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase}
.lp-person-name{color:#fff;font-size:17px;font-weight:800;margin-top:6px}
.lp-person-org{color:#f7e4a8;font-size:11px;margin-top:4px;opacity:.85;line-height:1.3}
.lp-app-card{background:radial-gradient(circle at 50% 40%,#8b5cf6 0%,#4c1d95 55%,#1e1b4b 100%);border-radius:16px;padding:20px 14px;text-align:center;box-shadow:0 8px 24px rgba(76,29,149,.5)}
.lp-app-name{font-size:22px;font-weight:900;color:#fff;letter-spacing:1px}
.lp-app-sub{color:#f7e4a8;font-size:11px;font-style:italic;margin-top:4px}
.lp-app-for{color:#fff;font-size:11px;margin-top:8px;opacity:.85;line-height:1.4}
.lp-band{background:linear-gradient(90deg,#c9a24e,#f2d36b,#c9a24e);color:#3d0a12;text-align:center;font-weight:900;font-size:17px;padding:12px;border-radius:10px;margin:16px 0;letter-spacing:.3px}
.lp-chips{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin:16px 0 20px}
.lp-chip{background:rgba(255,255,255,.08);border:1px solid rgba(201,162,78,.4);border-radius:999px;padding:6px 12px;font-size:12px;color:#f7e4a8;font-weight:600}
.lp-chip-ico{margin-right:4px}
.lp-cta-wrap{text-align:center;margin:22px 0 10px}
.lp-cta{display:inline-block;background:linear-gradient(135deg,#e11d48,#f43f5e);color:#fff;font-weight:800;font-size:16px;letter-spacing:.5px;text-transform:uppercase;text-decoration:none;padding:14px 30px;border-radius:999px;box-shadow:0 6px 20px rgba(225,29,72,.5);transition:transform .15s ease}
.lp-cta:hover{transform:translateY(-2px)}
.lp-cta-secondary{display:block;color:#f7e4a8;margin-top:14px;font-size:13px;text-decoration:underline;opacity:.9}
.lp-footer{text-align:center;color:#f7e4a8;font-size:11px;margin-top:24px;opacity:.6}
.lp-footer a{color:#c9a24e;text-decoration:none}"""


async def _ensure_seed_tps() -> None:
    """Seed the /tps landing page once."""
    if await db.landing_pages.find_one({"slug": "tps"}, {"_id": 1}):
        return
    now = datetime.now(timezone.utc).isoformat()
    await db.landing_pages.insert_one({
        "slug": "tps",
        "title": "Tamilpreneur Sangamam #26 · Jelcos AI Launch",
        "meta_description": "Join us at Tamilpreneur Sangamam #26 on 1st Aug 2026 — Bloom Hub, Guindy, Chennai. Launch of Jelcos AI, a Decision Intelligence Platform. First 100 spots open now.",
        "meta_og_image": "",
        "html": _DEFAULT_TPS_HTML,
        "css": _DEFAULT_TPS_CSS,
        "js": "",
        "active": True,
        "source": "seed",
        "created_at": now,
        "updated_at": now,
    })


# ─────────────────── Public ───────────────────

@router.get("/lp/{slug}")
async def public_get_landing_page(slug: str):
    await _ensure_seed_tps()
    s = (slug or "").strip().lower()
    row = await db.landing_pages.find_one({"slug": s, "active": True}, {"_id": 0})
    if not row:
        raise HTTPException(404, "Landing page not found.")
    return row


# ─────────────────── Admin ───────────────────

@router.get("/admin/landing-pages")
async def admin_list(user: dict = Depends(require_super_admin)):
    await _ensure_seed_tps()
    rows = await db.landing_pages.find({}, {"_id": 0}).sort("updated_at", -1).to_list(500)
    return {"pages": rows, "reserved_slugs": sorted(RESERVED_SLUGS)}


@router.post("/admin/landing-pages")
async def admin_create(body: LandingPageCreate, user: dict = Depends(require_super_admin)):
    slug = _validate_slug(body.slug)
    if await db.landing_pages.find_one({"slug": slug}, {"_id": 1}):
        raise HTTPException(409, f"A landing page with slug '{slug}' already exists.")
    now = datetime.now(timezone.utc).isoformat()
    doc: Dict[str, Any] = {
        "slug": slug,
        "title": body.title.strip(),
        "html": body.html,
        "css": body.css,
        "js": body.js,
        "meta_description": body.meta_description.strip(),
        "meta_og_image": body.meta_og_image.strip(),
        "active": bool(body.active),
        "source": "admin_manual",
        "created_at": now,
        "updated_at": now,
        "created_by": user.get("user_id"),
    }
    await db.landing_pages.insert_one(doc)
    return {"message": "Created", "page": {k: v for k, v in doc.items() if k != "_id"}}


@router.put("/admin/landing-pages/{slug}")
async def admin_update(slug: str, body: LandingPagePatch, user: dict = Depends(require_super_admin)):
    s = (slug or "").strip().lower()
    update: Dict[str, Any] = {k: v for k, v in body.dict(exclude_unset=True).items() if v is not None}
    if "title" in update:
        update["title"] = update["title"].strip()
    if "meta_description" in update:
        update["meta_description"] = update["meta_description"].strip()
    if "meta_og_image" in update:
        update["meta_og_image"] = update["meta_og_image"].strip()
    if not update:
        raise HTTPException(400, "Nothing to update.")
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    update["updated_by"] = user.get("user_id")
    res = await db.landing_pages.update_one({"slug": s}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Landing page not found.")
    row = await db.landing_pages.find_one({"slug": s}, {"_id": 0})
    return {"message": "Updated", "page": row}


@router.delete("/admin/landing-pages/{slug}")
async def admin_delete(slug: str, user: dict = Depends(require_super_admin)):
    s = (slug or "").strip().lower()
    res = await db.landing_pages.delete_one({"slug": s})
    if res.deleted_count == 0:
        raise HTTPException(404, "Landing page not found.")
    return {"message": "Deleted", "slug": s}
