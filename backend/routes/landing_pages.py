"""
Admin-CRUDable Custom Landing Pages
====================================
Purpose: Marketing / event landing pages served at short jelcos.ai URLs like
`/tps`, `/sangamam`, `/launch` etc. Admin edits the HTML/CSS/JS + meta from
`/admin/landing-pages`. Public visitors fetch `/api/lp/{slug}` and the
Expo Router catch-all `app/[promo].tsx` renders the payload.

Also supports **template-based generation**: admin fills structured fields
(ribbon, Tamil title, date/time/venue, people, chips, CTAs) → clicks Generate
→ backend renders full HTML+CSS from the event-launch template. Admin can
further tweak the generated code by hand before saving.

Endpoints:
  GET    /api/lp/{slug}                                PUBLIC — landing page payload
  GET    /api/admin/landing-pages                      admin — list
  POST   /api/admin/landing-pages                      admin — create
  PUT    /api/admin/landing-pages/{slug}               admin — update
  DELETE /api/admin/landing-pages/{slug}               admin — remove
  POST   /api/admin/landing-pages/generate-from-template  admin — render HTML+CSS from form fields
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import html as _html_lib
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
    """Seed the /tps landing page once, or refresh it if it's still on the
    old dark theme (source='seed' or missing template_data)."""
    now = datetime.now(timezone.utc).isoformat()
    existing = await db.landing_pages.find_one({"slug": "tps"}, {"_id": 0, "source": 1, "template_data": 1})
    # Fresh rendering using the new fwdslash-inspired CSS so every existing
    # /tps deployment auto-upgrades on first read after this release.
    default_tpl = EventTemplateData(
        ribbon="THE WAIT IS OVER — SANGAMAM #26 IS HERE!",
        tamil_title="சங்கமம்", tamil_hash="#26",
        english_title="Tamilpreneur Sangamam #26",
        subtitle="Startup Networking Event · Chennai",
        divider_text="Launch & Recognition",
        tagline="Connecting Founders. Creating Opportunities.",
        details=[
            DetailCard(icon="📅", label="Date", value="1st Aug, 2026 · Saturday"),
            DetailCard(icon="⏰", label="Time", value="3:00 PM – 7:00 PM"),
            DetailCard(icon="📍", label="Venue", value="Bloom Hub, Guindy, Chennai"),
            DetailCard(icon="⭐", label="Limited", value="First 100 spots open now!", highlight=True),
        ],
        person_left=PersonItem(role_label="Launched by", name="Shyam Siddarth", org="Founder, Tamilpreneur"),
        app_card=AppCardItem(name="JELCOS AI", subtitle="A Decision Intelligence Platform",
                             description="For Founders, Business Owners, CXOs & Leaders"),
        person_right=PersonItem(role_label="Received by", name="Ad Shezhiyan Raj",
                                org="Founder & CEO, VEALES Vedic Decisions Pvt. Ltd."),
        gold_band_text="சங்கமத்தில் சந்திப்போம்! ❤",
        chips=[
            ChipItem(emoji="🧠", text="AI Powered"),
            ChipItem(emoji="🎯", text="Smarter Decisions"),
            ChipItem(emoji="📈", text="Better Outcomes"),
            ChipItem(emoji="🪷", text="Conscious Living"),
        ],
        primary_cta_text="Book Your Spot Now",
        primary_cta_href="/auth/register?ref=tps",
        secondary_cta_text="Try the free Decision-Style Quiz →",
        secondary_cta_href="/quiz",
        extra_ctas=[
            ExtraCtaItem(text="Know Your Decision Style", href="/quiz", style="outline"),
            ExtraCtaItem(text="Explore The Decider Store", href="/decider-store", style="solid"),
        ],
        callout=CalloutItem(
            subtitle="FEATURED APP FOR TAMILPRENEURS",
            title="Business Model Chooser",
            body="Deciding between competing revenue models? Our flagship app in The "
                 "Decider Store walks Tamilpreneurs through the trade-offs of SaaS, "
                 "marketplace, agency and franchise models — with an AI-scored "
                 "recommendation tailored to your context.",
            cta_text="Try Business Model Chooser",
            cta_href="/decider-store/business-model-chooser",
            accent="#4F46E5",
        ),
        footer_text="© 2026 Jelcos AI · Chennai · <a href=\"https://jelcos.ai\">jelcos.ai</a>",
    )
    rendered = _render_event_template(default_tpl)
    if not existing:
        await db.landing_pages.insert_one({
            "slug": "tps",
            "title": "Tamilpreneur Sangamam #26 · Jelcos AI Launch",
            "meta_description": "Join us at Tamilpreneur Sangamam #26 on 1st Aug 2026 — Bloom Hub, Guindy, Chennai. Launch of Jelcos AI, a Decision Intelligence Platform. First 100 spots open now.",
            "meta_og_image": "",
            "html": rendered["html"], "css": rendered["css"], "js": "",
            "template_data": default_tpl.dict(),
            "active": True, "source": "seed_v3_bmc_callout",
            "created_at": now, "updated_at": now,
        })
    elif existing.get("source") in ("seed", "seed_v2_fwdslash") or not existing.get("template_data"):
        # Auto-upgrade to v3 (adds Decider Style + Decider Store CTAs + BMC callout).
        await db.landing_pages.update_one(
            {"slug": "tps"},
            {"$set": {"html": rendered["html"], "css": rendered["css"],
                      "template_data": default_tpl.dict(),
                      "source": "seed_v3_bmc_callout", "updated_at": now}},
        )


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


# ─────────────────── Template-based generator ───────────────────
#
# Admin fills structured fields on the Admin UI, backend renders full HTML+CSS
# from this template. Same visual as the seeded /tps page. Every field is
# HTML-escaped before interpolation to prevent script injection through the
# template inputs (custom HTML/JS remains available via the raw fields for
# admins who want more control).


class ChipItem(BaseModel):
    text: str = ""
    emoji: str = ""


class ExtraCtaItem(BaseModel):
    text: str = ""
    href: str = ""
    style: str = "outline"   # 'solid' | 'outline'


class CalloutItem(BaseModel):
    title: str = ""
    subtitle: str = ""
    body: str = ""
    cta_text: str = ""
    cta_href: str = ""
    accent: str = "#4F46E5"   # left border colour


class PersonItem(BaseModel):
    role_label: str = ""      # e.g. "Launched by"
    name: str = ""            # e.g. "Shyam Siddarth"
    org: str = ""             # e.g. "Founder, Tamilpreneur"


class AppCardItem(BaseModel):
    name: str = ""            # e.g. "JELCOS AI"
    subtitle: str = ""        # e.g. "A Decision Intelligence Platform"
    description: str = ""     # e.g. "For Founders, Business Owners, CXOs & Leaders"


class DetailCard(BaseModel):
    icon: str = ""            # emoji
    label: str = ""           # UPPERCASE small label (e.g. DATE)
    value: str = ""           # e.g. "1st Aug, 2026 · Saturday"
    highlight: bool = False   # renders in red/gold accent (e.g. Limited spots)


class EventTemplateData(BaseModel):
    """All fields admin fills in the Template Builder tab."""
    # Hero
    ribbon: str = "THE WAIT IS OVER — SANGAMAM #26 IS HERE!"
    tamil_title: str = "சங்கமம்"
    tamil_hash: str = "#26"
    english_title: str = "Tamilpreneur Sangamam #26"
    subtitle: str = "Startup Networking Event · Chennai"
    divider_text: str = "Launch & Recognition"
    tagline: str = "Connecting Founders. Creating Opportunities."
    # Detail cards
    details: List[DetailCard] = Field(default_factory=list)
    # People + App
    person_left: PersonItem = Field(default_factory=PersonItem)
    app_card: AppCardItem = Field(default_factory=AppCardItem)
    person_right: PersonItem = Field(default_factory=PersonItem)
    # Gold band
    gold_band_text: str = "சங்கமத்தில் சந்திப்போம்! ❤"
    # Chips
    chips: List[ChipItem] = Field(default_factory=list)
    # CTAs
    primary_cta_text: str = "Book Your Spot Now"
    primary_cta_href: str = "/auth/register?ref=tps"
    secondary_cta_text: str = "Try the free Decision-Style Quiz →"
    secondary_cta_href: str = "/quiz"
    # Extra CTA row — buttons rendered after primary CTA (admin-editable)
    extra_ctas: List[ExtraCtaItem] = Field(default_factory=list)
    # Optional callout card (e.g. a featured store app / decision template)
    callout: Optional[CalloutItem] = None
    # Footer
    footer_text: str = "© 2026 Jelcos AI · Chennai · <a href=\"https://jelcos.ai\">jelcos.ai</a>"
    # Theme colour overrides (optional)
    bg_gradient: str = "linear-gradient(180deg,#3d0a12 0%,#1a0409 55%,#2a0710 100%)"
    accent_gold: str = "#c9a24e"
    accent_red: str = "#e11d48"
    text_light: str = "#f7e4a8"


def _esc(s: str) -> str:
    """HTML-escape a value coming from admin form fields."""
    return _html_lib.escape(str(s or ""), quote=True)


def _render_extra_ctas(d: "EventTemplateData") -> str:
    if not d.extra_ctas:
        return ""
    btns = "\n".join(
        f'<a class="lp-cta-extra lp-cta-extra-{_esc(c.style or "outline")}" href="{_esc(c.href)}">{_esc(c.text)}</a>'
        for c in d.extra_ctas if (c.text and c.href)
    )
    return f'<div class="lp-cta-extra-row">{btns}</div>' if btns else ""


def _render_callout(d: "EventTemplateData") -> str:
    c = d.callout
    if not c or not (c.title or c.body):
        return ""
    cta = (
        f'<a class="lp-callout-cta" href="{_esc(c.cta_href)}">{_esc(c.cta_text)}</a>'
        if (c.cta_text and c.cta_href) else ""
    )
    return (
        f'<div class="lp-callout" style="border-left-color:{_esc(c.accent or "#4F46E5")}">'
        f'  <div class="lp-callout-sub">{_esc(c.subtitle)}</div>'
        f'  <div class="lp-callout-title">{_esc(c.title)}</div>'
        f'  <div class="lp-callout-body">{_esc(c.body)}</div>'
        f'  {cta}'
        f'</div>'
    )


def _render_event_template(d: EventTemplateData) -> Dict[str, str]:
    """Return {'html': ..., 'css': ...} rendered from the template data."""
    # Detail cards
    detail_html = "\n".join(
        f'<div class="lp-detail-card{" lp-spots" if c.highlight else ""}">'
        f'<div class="lp-detail-ico">{_esc(c.icon)}</div>'
        f'<div><div class="lp-detail-label">{_esc(c.label)}</div>'
        f'<div class="lp-detail-val">{_esc(c.value)}</div></div></div>'
        for c in (d.details or [])
    )
    # Chips
    chip_html = "\n".join(
        f'<div class="lp-chip"><span class="lp-chip-ico">{_esc(c.emoji)}</span> {_esc(c.text)}</div>'
        for c in (d.chips or []) if (c.text or c.emoji)
    )
    p1, p2, p3 = d.person_left, d.app_card, d.person_right
    html = f"""<div class="lp-wrap">
  <div class="lp-hero">
    <div class="lp-ribbon">{_esc(d.ribbon)}</div>
    <div class="lp-title-tam">{_esc(d.tamil_title)} <span class="lp-hash">{_esc(d.tamil_hash)}</span></div>
    <div class="lp-title-en">{_esc(d.english_title)}</div>
    <div class="lp-subtitle">{_esc(d.subtitle)}</div>
    <div class="lp-divider">◆ {_esc(d.divider_text)} ◆</div>
    <div class="lp-tagline">{_esc(d.tagline)}</div>
  </div>

  <div class="lp-detail-grid">
    {detail_html}
  </div>

  <div class="lp-people">
    <div class="lp-person">
      <div class="lp-person-role">{_esc(p1.role_label)}</div>
      <div class="lp-person-name">{_esc(p1.name)}</div>
      <div class="lp-person-org">{_esc(p1.org)}</div>
    </div>
    <div class="lp-app-card">
      <div class="lp-app-name">{_esc(p2.name)}</div>
      <div class="lp-app-sub">{_esc(p2.subtitle)}</div>
      <div class="lp-app-for">{_esc(p2.description)}</div>
    </div>
    <div class="lp-person">
      <div class="lp-person-role">{_esc(p3.role_label)}</div>
      <div class="lp-person-name">{_esc(p3.name)}</div>
      <div class="lp-person-org">{_esc(p3.org)}</div>
    </div>
  </div>

  <div class="lp-band">{_esc(d.gold_band_text)}</div>

  <div class="lp-chips">
    {chip_html}
  </div>

  <div class="lp-cta-wrap">
    <a class="lp-cta" href="{_esc(d.primary_cta_href)}" id="lp-cta-primary">{_esc(d.primary_cta_text)}</a>
    <a class="lp-cta-secondary" href="{_esc(d.secondary_cta_href)}">{_esc(d.secondary_cta_text)}</a>
    {_render_extra_ctas(d)}
    {_render_callout(d)}
  </div>

  <div class="lp-footer">{d.footer_text}</div>
</div>"""

    css = f""".lp-wrap{{max-width:1120px;margin:0 auto;padding:56px 24px 72px;background:#F8FAFC;color:#0F172A;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Inter',sans-serif;position:relative;overflow:hidden}}
.lp-wrap::before{{content:'';position:absolute;inset:0;background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='40' height='40'><path d='M40 0H0V40' stroke='%23E2E8F0' stroke-width='1' fill='none'/></svg>");background-size:40px 40px;-webkit-mask-image:radial-gradient(ellipse 80% 60% at 50% 20%,black 30%,transparent 85%);mask-image:radial-gradient(ellipse 80% 60% at 50% 20%,black 30%,transparent 85%);pointer-events:none;z-index:0}}
.lp-wrap > *{{position:relative;z-index:1}}
.lp-hero{{text-align:center;padding:16px 8px 8px}}
.lp-ribbon{{display:inline-flex;align-items:center;gap:6px;background:#fff;color:{d.accent_red};font-weight:700;font-size:12px;letter-spacing:.3px;padding:7px 14px;border-radius:999px;border:1px solid #E2E8F0;box-shadow:0 1px 2px rgba(0,0,0,.04)}}
.lp-title-tam{{font-size:clamp(48px,8vw,84px);font-weight:900;color:#0F172A;line-height:1.02;letter-spacing:-1.5px;margin:22px 0 6px}}
.lp-hash{{color:{d.accent_red}}}
.lp-title-en{{font-size:14px;color:#4F46E5;letter-spacing:1.4px;text-transform:uppercase;margin-top:6px;font-weight:700}}
.lp-subtitle{{font-size:15px;color:#64748B;margin-top:4px}}
.lp-divider{{color:{d.accent_gold};margin:20px 0 8px;letter-spacing:2px;font-size:12px;font-weight:700}}
.lp-tagline{{color:#475569;font-size:18px;font-style:italic;line-height:1.55;max-width:680px;margin:0 auto}}
.lp-detail-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:44px auto;max-width:920px}}
.lp-detail-card{{background:#fff;border:1px solid #E2E8F0;border-radius:14px;padding:16px;display:flex;gap:12px;align-items:center;box-shadow:0 1px 2px rgba(0,0,0,.03)}}
.lp-detail-ico{{font-size:26px}}
.lp-detail-label{{color:#94A3B8;font-size:10px;font-weight:800;letter-spacing:1.4px;text-transform:uppercase}}
.lp-detail-val{{color:#0F172A;font-size:14px;font-weight:700;margin-top:3px}}
.lp-spots{{background:linear-gradient(135deg,{d.accent_red}0f,{d.accent_gold}12);border-color:{d.accent_red}55}}
.lp-people{{display:grid;grid-template-columns:1fr;gap:14px;margin:36px auto;max-width:1000px}}
@media(min-width:820px){{.lp-people{{grid-template-columns:1fr 1.2fr 1fr;align-items:center}}}}
.lp-person{{background:#fff;border:1px solid #E2E8F0;border-radius:16px;padding:22px 18px;text-align:center;box-shadow:0 2px 8px rgba(15,23,42,.04)}}
.lp-person-role{{color:#94A3B8;font-size:10px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase}}
.lp-person-name{{color:#0F172A;font-size:19px;font-weight:800;margin-top:8px;letter-spacing:-.3px}}
.lp-person-org{{color:#475569;font-size:12px;margin-top:5px;line-height:1.4}}
.lp-app-card{{background:linear-gradient(135deg,#4F46E5 0%,#7C3AED 55%,#1E1B4B 100%);border-radius:20px;padding:32px 20px;text-align:center;box-shadow:0 20px 40px rgba(79,70,229,.3);color:#fff}}
.lp-app-name{{font-size:28px;font-weight:900;letter-spacing:.5px}}
.lp-app-sub{{color:#C7D2FE;font-size:12px;font-style:italic;margin-top:6px}}
.lp-app-for{{color:#E0E7FF;font-size:12px;margin-top:12px;line-height:1.5;opacity:.9}}
.lp-band{{background:#0F172A;color:{d.accent_gold};text-align:center;font-weight:800;font-size:18px;padding:16px;border-radius:14px;margin:30px auto;max-width:920px;letter-spacing:.3px}}
.lp-chips{{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin:28px auto;max-width:820px}}
.lp-chip{{background:#fff;border:1px solid #E2E8F0;border-radius:999px;padding:8px 14px;font-size:13px;color:#334155;font-weight:600;box-shadow:0 1px 2px rgba(0,0,0,.03)}}
.lp-chip-ico{{margin-right:5px}}
.lp-cta-wrap{{text-align:center;margin:44px auto 10px;display:flex;flex-direction:column;align-items:center;gap:14px}}
.lp-cta{{display:inline-flex;align-items:center;gap:8px;background:#0F172A;color:#fff;font-weight:800;font-size:15px;letter-spacing:.4px;text-decoration:none;padding:15px 32px;border-radius:999px;transition:transform .15s ease, box-shadow .15s ease;box-shadow:0 8px 24px rgba(15,23,42,.15)}}
.lp-cta:hover{{transform:translateY(-2px);box-shadow:0 12px 28px rgba(15,23,42,.25)}}
.lp-cta::after{{content:'→';font-size:16px}}
.lp-cta-secondary{{color:#4F46E5;font-size:14px;text-decoration:underline;text-decoration-color:#C7D2FE;text-underline-offset:4px}}
.lp-cta-extra-row{{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin-top:8px}}
.lp-cta-extra{{display:inline-flex;align-items:center;gap:6px;font-weight:800;font-size:14px;letter-spacing:.3px;text-decoration:none;padding:12px 22px;border-radius:999px;transition:transform .15s ease}}
.lp-cta-extra:hover{{transform:translateY(-1px)}}
.lp-cta-extra-solid{{background:{d.accent_red};color:#fff;box-shadow:0 6px 16px rgba(225,29,72,.35)}}
.lp-cta-extra-outline{{background:#fff;color:#0F172A;border:1.5px solid #0F172A}}
.lp-callout{{background:#fff;border:1px solid #E2E8F0;border-left:5px solid #4F46E5;border-radius:14px;padding:20px 22px;margin:22px auto 0;max-width:520px;text-align:left;box-shadow:0 4px 14px rgba(15,23,42,.05)}}
.lp-callout-sub{{color:#94A3B8;font-size:10px;font-weight:800;letter-spacing:1.4px;text-transform:uppercase;margin-bottom:6px}}
.lp-callout-title{{color:#0F172A;font-size:20px;font-weight:900;letter-spacing:-.3px}}
.lp-callout-body{{color:#475569;font-size:13.5px;line-height:1.55;margin-top:8px}}
.lp-callout-cta{{display:inline-flex;align-items:center;gap:6px;margin-top:12px;background:#0F172A;color:#fff;padding:9px 16px;border-radius:999px;font-size:12.5px;font-weight:800;text-decoration:none}}
.lp-callout-cta::after{{content:'→'}}
.lp-footer{{text-align:center;color:#94A3B8;font-size:11px;margin-top:36px}}
.lp-footer a{{color:#4F46E5;text-decoration:none}}"""
    return {"html": html, "css": css}


@router.post("/admin/landing-pages/generate-from-template")
async def generate_from_template(body: EventTemplateData, user: dict = Depends(require_super_admin)):
    """Render full HTML+CSS from structured event-template fields. Admin can
    then paste the output into the raw HTML/CSS boxes (or the frontend can
    auto-fill them via this endpoint). Returns a nested `template_data` object
    so the frontend can also persist the source-of-truth fields alongside the
    generated code — enabling round-trip re-editing without losing structure."""
    rendered = _render_event_template(body)
    return {
        "html": rendered["html"],
        "css": rendered["css"],
        "template_data": body.dict(),
    }
