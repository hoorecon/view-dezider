"""
Partner Embed Foundation — Phase 0 (P0)
=======================================

A generic, multi-tenant configuration layer that lets ANY comparison platform
(PMSBazaar, real-estate portals, EdTech comparison sites, …) embed the View
Dezider decision tools (MyDezider, Pros & Cons, and the bulk Screener) inside
their own site — white-labelled, brand-themed, and origin allow-listed.

This module owns the *configuration* surface only. The iframe widget + JS
loader (P1), data hand-off (P2) and Screener (P3) build on top of the config
resolved here.

Design notes
------------
* Partner == an `organizations` document (so the EXISTING org login in
  `org_auth.py` doubles as the embed auth — no separate SSO to maintain).
* Config persists in the `decision_embed_config` collection keyed by `org_id`.
* `GET /api/embed/public-config/{slug}` is PUBLIC (no auth) and returns only a
  brand-safe subset so the widget can render itself before the user signs in.
* `PUT /api/embed/config/{slug}` is ADMIN-only and gates server-side scraping
  behind explicit legal/ToS acknowledgement checkboxes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from core.database import db
from core.auth import require_admin, get_current_user

router = APIRouter(prefix="/embed", tags=["Partner Embed"])


# ------------------------------------------------------------------
# Models
# ------------------------------------------------------------------
VALID_FLOWS = ["mydezider", "pros_cons", "screener"]
BRANDING_MODES = ["white_label", "co_brand"]
AUTH_MODES = ["otp", "frictionless"]
BILLING_MODES = ["end_user", "partner", "both"]
RENDER_MODES = ["rn_web", "html_widget"]   # iframe the real RN web app, or a self-contained HTML widget


class EmbedTheme(BaseModel):
    primary_color: str = "#7C3AED"
    accent_color: Optional[str] = None
    logo_uri: Optional[str] = None          # data: URI or https URL; hidden when white_label requests it
    font_family: Optional[str] = None
    hide_powered_by: bool = False           # remove the discreet "Powered by View Dezider" footer


class ScreenerPricing(BaseModel):
    """Dynamic pricing for a Screener run.

        cost = base_credits
             + per_candidate  * catalogue_size
             + per_finalist   * finalists_returned
             + per_factor     * num_factors
    """
    base_credits: float = 1.0
    per_candidate: float = 0.01
    per_finalist: float = 0.1
    per_factor: float = 0.05
    billing_mode: str = "end_user"          # who pays — end_user | partner | both


class IngestionConfig(BaseModel):
    """How the partner supplies the candidate catalogue for the Screener."""
    api_enabled: bool = False
    api_endpoint: Optional[str] = None      # partner-exposed catalogue API
    api_auth_header: Optional[str] = None    # optional header name (value stored server-side later)
    csv_sheet_enabled: bool = True          # CSV / Google Sheet upload per run
    scrape_enabled: bool = False            # server-side scrape of partner page (fallback only)
    # Legal / compliance gating — scraping cannot be enabled until BOTH acks are true.
    scrape_legal_ack: bool = False          # "We have legal authority / permission to scrape"
    scrape_terms_ack: bool = False          # "Partner ToS permits automated access"


class PartnerEmbedConfig(BaseModel):
    allowed_origins: List[str] = Field(default_factory=list)   # e.g. ["pmsbazaar.com", "www.pmsbazaar.com"]
    branding_mode: str = "white_label"
    render_mode: str = "rn_web"             # rn_web (real RN app, themed) | html_widget (self-contained)
    enabled_flows: List[str] = Field(default_factory=lambda: ["mydezider", "pros_cons"])
    theme: EmbedTheme = Field(default_factory=EmbedTheme)
    auth_mode: str = "otp"
    otp_required: bool = True
    expose_dev_code: bool = False           # echo OTP in API response (NON-PROD testing only)
    screener_pricing: ScreenerPricing = Field(default_factory=ScreenerPricing)
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
async def _resolve_org_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    if not slug:
        return None
    return await db.organizations.find_one(
        {"slug": slug.strip().lower()}, {"_id": 0}
    )


def _public_subset(org: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Brand-safe config the widget can read BEFORE the user authenticates."""
    theme = cfg.get("theme") or {}
    branding_mode = cfg.get("branding_mode", "white_label")
    # In white_label mode the partner's own logo/colour win; the View Dezider
    # logo is suppressed. In co_brand mode we keep a discreet dual-brand.
    primary = theme.get("primary_color") or org.get("primary_color") or "#7C3AED"
    logo = theme.get("logo_uri") or org.get("logo_url") or None
    return {
        "slug": org.get("slug"),
        "org_id": org.get("id"),
        "display_name": org.get("name"),
        "branding_mode": branding_mode,
        "render_mode": cfg.get("render_mode", "rn_web"),
        "enabled_flows": cfg.get("enabled_flows", ["mydezider", "pros_cons"]),
        "auth_mode": cfg.get("auth_mode", "otp"),
        "otp_required": cfg.get("otp_required", True),
        "theme": {
            "primary_color": primary,
            "accent_color": theme.get("accent_color") or org.get("accent_color"),
            "logo_uri": logo,
            "font_family": theme.get("font_family"),
            "hide_powered_by": bool(theme.get("hide_powered_by", False)),
        },
        "configured": bool(cfg),
    }


def _default_config_doc(org: Dict[str, Any]) -> Dict[str, Any]:
    """A sensible default config derived from the org's own branding."""
    base = PartnerEmbedConfig(
        theme=EmbedTheme(
            primary_color=org.get("primary_color", "#7C3AED"),
            accent_color=org.get("accent_color"),
            logo_uri=org.get("logo_url") or None,
        )
    ).model_dump()
    return base


# ------------------------------------------------------------------
# PUBLIC — widget bootstrap (no auth)
# ------------------------------------------------------------------
@router.get("/public-config/{slug}")
async def get_public_embed_config(slug: str):
    """Brand-safe embed config for a partner slug. PUBLIC — used by the widget
    to theme itself before sign-in. Returns 404 only for unknown slugs."""
    org = await _resolve_org_by_slug(slug)
    if not org:
        raise HTTPException(status_code=404, detail="Partner not found")
    cfg = await db.decision_embed_config.find_one({"org_id": org["id"]}, {"_id": 0}) or {}
    return _public_subset(org, cfg)


# ------------------------------------------------------------------
# ADMIN — full config CRUD
# ------------------------------------------------------------------
@router.get("/analytics/{slug}")
async def embed_analytics(slug: str, _admin: dict = Depends(require_admin)):
    """Admin analytics for a partner: screener run volume + billing totals."""
    org = await _resolve_org_by_slug(slug)
    if not org:
        raise HTTPException(status_code=404, detail="Partner not found")
    runs = await db.screener_runs.find(
        {"partner_id": org["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    ledger = await db.partner_billing_ledger.find(
        {"partner_id": org["id"]}, {"_id": 0}
    ).to_list(1000)

    def _iso(v):
        try:
            return v.isoformat()
        except Exception:
            return str(v)

    total_candidates = sum(int(r.get("candidate_count", 0) or 0) for r in runs)
    end_user_credits = round(sum(
        float(r.get("cost_credits", 0) or 0) for r in runs
        if r.get("billing_mode") in ("end_user", "both")), 2)
    partner_credits = round(sum(float(led.get("credits", 0) or 0) for led in ledger), 2)

    recent = []
    for r in runs[:25]:
        results = r.get("results", []) or []
        recent.append({
            "id": r.get("id"),
            "candidate_count": r.get("candidate_count"),
            "finalists_count": r.get("finalists_count"),
            "cost_credits": r.get("cost_credits"),
            "billing_mode": r.get("billing_mode"),
            "used_ai": r.get("used_ai", False),
            "top_match": (results[0].get("name") if results else None),
            "created_at": _iso(r.get("created_at")),
        })
    return {
        "slug": org.get("slug"),
        "partner_name": org.get("name"),
        "totals": {
            "runs": len(runs),
            "candidates_ranked": total_candidates,
            "end_user_credits": end_user_credits,
            "partner_credits": partner_credits,
            "ledger_entries": len(ledger),
        },
        "recent_runs": recent,
    }


@router.get("/config/{slug}")
async def get_embed_config(slug: str, _admin: dict = Depends(require_admin)):
    """Full embed config (admin only). If none persisted yet, returns sane
    defaults derived from the org branding so the admin UI has something to
    edit."""
    org = await _resolve_org_by_slug(slug)
    if not org:
        raise HTTPException(status_code=404, detail="Partner not found")
    cfg = await db.decision_embed_config.find_one({"org_id": org["id"]}, {"_id": 0})
    if not cfg:
        cfg = _default_config_doc(org)
        cfg["_persisted"] = False
    else:
        cfg["_persisted"] = True
    cfg["org"] = {"id": org["id"], "slug": org["slug"], "name": org.get("name")}
    return cfg


@router.put("/config/{slug}")
async def put_embed_config(
    slug: str,
    body: PartnerEmbedConfig,
    admin: dict = Depends(require_admin),
):
    """Upsert a partner's embed config (admin only).

    Validation:
      * branding_mode / auth_mode / billing_mode / enabled_flows are enum-checked
      * server-side scraping requires BOTH legal acknowledgements
    """
    org = await _resolve_org_by_slug(slug)
    if not org:
        raise HTTPException(status_code=404, detail="Partner not found")

    if body.branding_mode not in BRANDING_MODES:
        raise HTTPException(400, f"branding_mode must be one of {BRANDING_MODES}")
    if body.render_mode not in RENDER_MODES:
        raise HTTPException(400, f"render_mode must be one of {RENDER_MODES}")
    if body.auth_mode not in AUTH_MODES:
        raise HTTPException(400, f"auth_mode must be one of {AUTH_MODES}")
    if body.screener_pricing.billing_mode not in BILLING_MODES:
        raise HTTPException(400, f"billing_mode must be one of {BILLING_MODES}")
    bad_flows = [f for f in body.enabled_flows if f not in VALID_FLOWS]
    if bad_flows:
        raise HTTPException(400, f"Invalid flows {bad_flows}; allowed {VALID_FLOWS}")

    # Legal gate: scraping cannot be turned on without both acknowledgements.
    if body.ingestion.scrape_enabled and not (
        body.ingestion.scrape_legal_ack and body.ingestion.scrape_terms_ack
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Server-side scraping requires both the legal authority and "
                "partner-ToS acknowledgements to be checked before it can be enabled."
            ),
        )

    doc = body.model_dump()
    doc["org_id"] = org["id"]
    doc["slug"] = org["slug"]
    doc["updated_by"] = admin.get("user_id")
    doc["updated_at"] = datetime.now(timezone.utc)
    await db.decision_embed_config.update_one(
        {"org_id": org["id"]},
        {"$set": doc, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    saved = await db.decision_embed_config.find_one({"org_id": org["id"]}, {"_id": 0})
    return {"ok": True, "config": saved}


@router.get("/partners")
async def list_embed_partners(_admin: dict = Depends(require_admin)):
    """Admin: list every org that has (or could have) an embed config, with a
    quick configured/flows summary for the admin console."""
    orgs = await db.organizations.find(
        {}, {"_id": 0, "id": 1, "slug": 1, "name": 1, "org_type": 1, "primary_color": 1}
    ).to_list(500)
    configs = {
        c["org_id"]: c
        async for c in db.decision_embed_config.find({}, {"_id": 0})
    }
    out = []
    for o in orgs:
        c = configs.get(o["id"])
        out.append({
            "org_id": o["id"],
            "slug": o.get("slug"),
            "name": o.get("name"),
            "org_type": o.get("org_type"),
            "configured": bool(c),
            "branding_mode": (c or {}).get("branding_mode"),
            "enabled_flows": (c or {}).get("enabled_flows", []),
        })
    # Configured partners first, then alphabetical
    out.sort(key=lambda x: (not x["configured"], (x["name"] or "").lower()))
    return {"partners": out, "total": len(out)}
