"""
Public Pulse — White-labelled Org Sub-Portals (Phase 3 / Section D).

Goal: every approved Org can be reached via a public, brand-themed page
at  /p/{org_slug}   that is hostable on the Org's own website OR on a
Govt department's website (via iframe / embed.js).

Endpoints exposed under /api/p/* are PUBLIC (no auth required) for read.
Feedback submission supports both anonymous and logged-in flows.

CORS: the global CORS middleware already allows '*'. This module additionally
exposes an admin endpoint to record per-org allow-listed embed domains
(useful when reverse-proxies enforce stricter CORS).
"""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import html
import json
import uuid

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from core.database import db
from core.auth import require_admin, get_current_user_optional

router = APIRouter(tags=["Public Pulse — Portal"])


# ------------------------------------------------------------------
# Models
# ------------------------------------------------------------------
class PortalFeedbackSubmit(BaseModel):
    feedback_type: str            # "complaint" | "suggestion" | "idea"
    title: str
    description: str
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    location_district: Optional[str] = None
    location_state: Optional[str] = None


class PortalEmbedConfig(BaseModel):
    allowed_domains: List[str] = []  # e.g. ["example.gov.in", "rajasthantourism.in"]
    show_feedback_form: bool = True
    show_resolved_list: bool = True
    primary_cta_label: Optional[str] = None  # e.g. "Send your suggestion"


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
async def _resolve_org_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """Find an approved org by slug (case-insensitive)."""
    if not slug:
        return None
    org = await db.pp_orgs.find_one(
        {"slug": slug, "status": "approved"},
        {"_id": 0, "brand_logo_b64": 0},
    )
    return org


async def _portal_config_for(org_id: str) -> Dict[str, Any]:
    cfg = await db.pp_portal_config.find_one({"org_id": org_id}, {"_id": 0}) or {}
    return {
        "allowed_domains": cfg.get("allowed_domains", []),
        "show_feedback_form": cfg.get("show_feedback_form", True),
        "show_resolved_list": cfg.get("show_resolved_list", True),
        "primary_cta_label": cfg.get("primary_cta_label", "Send your feedback"),
    }


def _branding_payload(org: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "slug": org.get("slug"),
        "org_id": org.get("org_id"),
        "display_name": org.get("display_name"),
        "about": org.get("about"),
        "website": org.get("website"),
        "email": org.get("email"),
        "state": org.get("state"),
        "district": org.get("district"),
        "categories": org.get("categories", []),
        "primary_color": org.get("brand_color") or "#7C3AED",
        "logo_uri": org.get("brand_logo_uri"),
        "approved_at": org.get("approved_at"),
        "active_member_count": org.get("active_member_count", 0),
        "total_feedback_handled": org.get("total_feedback_handled", 0),
    }


# ------------------------------------------------------------------
# Public read endpoints (no auth)
# ------------------------------------------------------------------
@router.get("/p/{slug}")
async def get_org_portal(slug: str):
    """Return brand + about info for the public org sub-portal."""
    org = await _resolve_org_by_slug(slug)
    if not org:
        raise HTTPException(status_code=404, detail="Org sub-portal not found")
    config = await _portal_config_for(org["org_id"])
    return {"org": _branding_payload(org), "config": config}


@router.get("/p/{slug}/feedback/public")
async def list_public_feedback(slug: str, limit: int = 25):
    """List recent feedback items handled by this org with public-safe fields."""
    org = await _resolve_org_by_slug(slug)
    if not org:
        raise HTTPException(status_code=404, detail="Org sub-portal not found")
    cfg = await _portal_config_for(org["org_id"])
    if not cfg.get("show_resolved_list", True):
        return {"items": [], "config": cfg}

    items = await db.pp_feedback_items.find(
        {
            "assigned_org_id": org["org_id"],
            "status": {"$in": ["resolved", "closed", "responded", "action_taken"]},
        },
        {
            "_id": 0, "user_id": 0, "anon_user_id": 0,
            "contact_email": 0, "contact_phone": 0, "contact_name": 0,
        },
    ).sort("created_at", -1).limit(min(max(limit, 1), 100)).to_list(100)
    # Strip any remaining PII just in case
    safe = []
    for it in items:
        safe.append({
            "feedback_id": it.get("feedback_id"),
            "feedback_type": it.get("feedback_type"),
            "title": it.get("title"),
            "description_short": (it.get("description") or "")[:240],
            "status": it.get("status"),
            "created_at": it.get("created_at"),
            "resolved_at": it.get("resolved_at"),
            "response_text": (it.get("response_text") or "")[:500],
        })
    return {"items": safe, "config": cfg}


@router.post("/p/{slug}/feedback")
async def submit_portal_feedback(
    slug: str,
    body: PortalFeedbackSubmit,
    request: Request,
    user_opt: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Submit feedback through the public sub-portal.

    Auth optional: when signed in we link to the user; otherwise we tag
    the submission anonymously (with optional contact info).
    """
    org = await _resolve_org_by_slug(slug)
    if not org:
        raise HTTPException(status_code=404, detail="Org sub-portal not found")
    if body.feedback_type not in ("complaint", "suggestion", "idea"):
        raise HTTPException(400, "feedback_type must be one of complaint/suggestion/idea")
    if not body.title.strip() or not body.description.strip():
        raise HTTPException(400, "title and description are required")

    feedback_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    doc: Dict[str, Any] = {
        "feedback_id": feedback_id,
        "feedback_type": body.feedback_type,
        "title": body.title.strip()[:200],
        "description": body.description.strip()[:4000],
        "assigned_org_id": org["org_id"],
        "routing_status": "auto_routed",
        "status": "received",
        "source": "public_portal",
        "portal_slug": slug,
        "submitter_ip_hash": _ip_hash(request),
        "location_district": body.location_district,
        "location_state": body.location_state,
        "created_at": now,
        "updated_at": now,
    }
    if user_opt and user_opt.get("user_id"):
        doc["user_id"] = user_opt["user_id"]
    else:
        doc["anon_user_id"] = f"anon_{uuid.uuid4().hex[:10]}"
        if body.contact_name: doc["contact_name"] = body.contact_name
        if body.contact_email: doc["contact_email"] = body.contact_email
        if body.contact_phone: doc["contact_phone"] = body.contact_phone

    await db.pp_feedback_items.insert_one(doc)
    return {"ok": True, "feedback_id": feedback_id, "status": "received"}


def _ip_hash(request: Request) -> str:
    """Lightweight IP hash for anti-spam tracking (NOT a stable user id)."""
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "0.0.0.0")
    ip = (ip or "").split(",")[0].strip()
    return f"ip_{abs(hash(ip)) % (10 ** 10):010d}"


# ------------------------------------------------------------------
# Embeddable widget (HTML, iframe-safe — for hosting on org/govt domains)
# ------------------------------------------------------------------
@router.get("/embed/{slug}", response_class=HTMLResponse)
async def embed_widget_html(slug: str, request: Request):
    """
    Returns a self-contained HTML widget for the org sub-portal.
    Designed to be loaded inside an iframe on the org/govt website.

    Page is fully responsive, no external CDN, uses the org's primary_color.
    """
    org = await _resolve_org_by_slug(slug)
    if not org:
        raise HTTPException(status_code=404, detail="Org sub-portal not found")
    config = await _portal_config_for(org["org_id"])
    branding = _branding_payload(org)
    api_base = str(request.base_url).rstrip("/")  # e.g. https://api.example.com
    html_doc = _render_widget_html(branding, config, api_base)
    return HTMLResponse(
        content=html_doc,
        headers={
            # Permissive framing so it embeds cleanly on third-party domains.
            # Org admins can override at their CDN/proxy if they want stricter rules.
            "X-Frame-Options": "ALLOWALL",
            "Content-Security-Policy": "frame-ancestors *",
            "Cache-Control": "no-store",
        },
    )


@router.get("/embed/{slug}/widget.js")
async def embed_widget_js(slug: str, request: Request):
    """
    Returns a JS snippet that auto-injects an iframe into the host page.

    Usage on org/govt website:
        <script src="https://YOUR-API/api/embed/my-org-slug/widget.js"
                data-target="public-pulse-widget"
                data-height="640"></script>
        <div id="public-pulse-widget"></div>
    """
    org = await _resolve_org_by_slug(slug)
    if not org:
        raise HTTPException(status_code=404, detail="Org sub-portal not found")
    api_base = str(request.base_url).rstrip("/")
    embed_url = f"{api_base}/api/embed/{slug}"
    js = (
        "(function(){\n"
        "  var script = document.currentScript;\n"
        "  var target = (script && script.getAttribute('data-target')) || 'public-pulse-widget';\n"
        "  var height = (script && script.getAttribute('data-height')) || '640';\n"
        "  function mount(){\n"
        "    var el = document.getElementById(target);\n"
        "    if (!el) { return; }\n"
        "    var iframe = document.createElement('iframe');\n"
        f"    iframe.src = {json.dumps(embed_url)};\n"
        "    iframe.style.width = '100%';\n"
        "    iframe.style.border = '0';\n"
        "    iframe.style.height = height + 'px';\n"
        "    iframe.setAttribute('allow', 'clipboard-write; geolocation');\n"
        "    iframe.setAttribute('title', 'Public Pulse Sub-Portal');\n"
        "    el.innerHTML = '';\n"
        "    el.appendChild(iframe);\n"
        "  }\n"
        "  if (document.readyState === 'loading') {\n"
        "    document.addEventListener('DOMContentLoaded', mount);\n"
        "  } else { mount(); }\n"
        "})();"
    )
    return Response(
        content=js,
        media_type="application/javascript",
        headers={
            "Cache-Control": "public, max-age=300",
            "Access-Control-Allow-Origin": "*",
        },
    )


def _render_widget_html(branding: Dict, config: Dict, api_base: str) -> str:
    color = html.escape(str(branding.get("primary_color") or "#7C3AED"))
    title = html.escape(str(branding.get("display_name") or "Public Pulse"))
    about = html.escape(str(branding.get("about") or ""))
    state = html.escape(str(branding.get("state") or ""))
    district = html.escape(str(branding.get("district") or ""))
    handled = int(branding.get("total_feedback_handled") or 0)
    cta = html.escape(str(config.get("primary_cta_label") or "Send your feedback"))
    show_form = bool(config.get("show_feedback_form", True))
    show_resolved = bool(config.get("show_resolved_list", True))
    slug = html.escape(str(branding.get("slug") or ""))

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{title} – Public Pulse</title>
<style>
:root {{ --c: {color}; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; font-family: system-ui,-apple-system,Segoe UI,Roboto,sans-serif; background:#F8FAFC; color:#111827; }}
header {{ background: var(--c); color:#fff; padding:18px 20px; }}
header h1 {{ margin:0; font-size:20px; font-weight:700; }}
header p {{ margin:6px 0 0; opacity:0.85; font-size:13px; }}
main {{ padding:18px 20px; max-width:840px; margin:0 auto; }}
.card {{ background:#fff; border:1px solid #E5E7EB; border-radius:12px; padding:16px; margin-bottom:16px; box-shadow:0 1px 2px rgba(0,0,0,0.03); }}
.row {{ display:flex; gap:12px; flex-wrap:wrap; }}
.tag {{ display:inline-block; background:#EEF2FF; color:#4338CA; font-size:11px; padding:2px 8px; border-radius:10px; margin-right:6px; }}
label {{ display:block; font-size:12px; color:#374151; margin:8px 0 4px; font-weight:600; }}
input, textarea, select {{ width:100%; padding:8px 10px; border:1px solid #D1D5DB; border-radius:8px; font-size:13px; }}
button {{ background: var(--c); color:#fff; border:none; padding:10px 16px; font-weight:700; border-radius:8px; cursor:pointer; }}
button:disabled {{ opacity:0.5; cursor:not-allowed; }}
.fb {{ border-left:4px solid var(--c); padding-left:10px; margin-bottom:10px; }}
.muted {{ color:#6B7280; font-size:12px; }}
.success {{ color:#065F46; background:#ECFDF5; padding:10px; border-radius:8px; margin-top:8px; }}
.err {{ color:#7F1D1D; background:#FEF2F2; padding:10px; border-radius:8px; margin-top:8px; }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <p>{state}{' · ' if state and district else ''}{district}{' · ' if (state or district) and handled else ''}{('{:,} feedback items handled'.format(handled)) if handled else ''}</p>
</header>
<main>
  <div class="card">
    <div class="row">{''.join([f'<span class="tag">{html.escape(c)}</span>' for c in (branding.get('categories') or [])])}</div>
    <p style="margin-top:8px;font-size:14px;line-height:1.5;">{about}</p>
  </div>

  {('''<div class="card">
    <h2 style="margin:0 0 8px;font-size:15px;">''' + cta + '''</h2>
    <form id="fb-form">
      <label>Type
        <select name="feedback_type" required>
          <option value="complaint">Complaint</option>
          <option value="suggestion">Suggestion</option>
          <option value="idea">Idea</option>
        </select>
      </label>
      <label>Title <input name="title" maxlength="200" required></label>
      <label>Description <textarea name="description" rows="4" maxlength="4000" required></textarea></label>
      <label>Your name (optional) <input name="contact_name" maxlength="120"></label>
      <label>Your email (optional) <input type="email" name="contact_email" maxlength="200"></label>
      <label>District (optional) <input name="location_district" maxlength="120"></label>
      <button type="submit">Submit</button>
      <div id="fb-status"></div>
    </form>
  </div>''') if show_form else ''}

  {'<div class="card"><h2 style="margin:0 0 10px;font-size:15px;">Recently resolved</h2><div id="fb-list">Loading…</div></div>' if show_resolved else ''}

  <div class="muted" style="text-align:center;padding-top:8px;">Powered by Public Pulse</div>
</main>
<script>
(function(){{
  var apiBase = {json.dumps(api_base)};
  var slug = {json.dumps(slug)};
  var fbForm = document.getElementById('fb-form');
  var fbStatus = document.getElementById('fb-status');
  var fbList = document.getElementById('fb-list');

  if (fbForm) {{
    fbForm.addEventListener('submit', function(e) {{
      e.preventDefault();
      var btn = fbForm.querySelector('button');
      var fd = new FormData(fbForm);
      var body = {{}};
      fd.forEach(function(v, k) {{ if (v) body[k] = v; }});
      btn.disabled = true; fbStatus.innerHTML = '';
      fetch(apiBase + '/api/p/' + encodeURIComponent(slug) + '/feedback', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(body),
      }}).then(function(r) {{
        return r.json().then(function(j) {{ return [r.ok, j]; }});
      }}).then(function(arr) {{
        var ok = arr[0], j = arr[1];
        if (ok && j.ok) {{
          fbStatus.innerHTML = '<div class="success">Thanks — we received your feedback (#' + (j.feedback_id || '').slice(0,8) + ')</div>';
          fbForm.reset();
        }} else {{
          fbStatus.innerHTML = '<div class="err">Could not submit: ' + (j.detail || 'try again') + '</div>';
        }}
      }}).catch(function(){{
        fbStatus.innerHTML = '<div class="err">Network error. Please try again.</div>';
      }}).finally(function(){{ btn.disabled = false; }});
    }});
  }}

  if (fbList) {{
    fetch(apiBase + '/api/p/' + encodeURIComponent(slug) + '/feedback/public')
      .then(function(r){{ return r.json(); }})
      .then(function(j){{
        var items = (j && j.items) || [];
        if (items.length === 0) {{ fbList.innerHTML = '<div class="muted">No published feedback yet.</div>'; return; }}
        fbList.innerHTML = items.map(function(it){{
          var t = (it.title || '').replace(/[<>"]/g, '');
          var d = (it.description_short || '').replace(/[<>"]/g, '');
          var s = (it.status || '').toUpperCase();
          var dt = it.resolved_at || it.created_at || '';
          return '<div class="fb"><strong>' + t + '</strong> <span class="muted">— ' + s + '</span><br>'
               + '<span class="muted">' + dt + '</span><br>' + d + '</div>';
        }}).join('');
      }}).catch(function(){{ fbList.innerHTML = '<div class="err">Could not load list.</div>'; }});
  }}
}})();
</script>
</body>
</html>"""


# ------------------------------------------------------------------
# Admin endpoints — manage portal config (per-org)
# ------------------------------------------------------------------
@router.put("/p/{slug}/config")
async def admin_update_portal_config(
    slug: str,
    body: PortalEmbedConfig,
    user: dict = Depends(require_admin),
):
    """
    Admin-only: configure embed/portal behaviour for an org slug.
    Persists into pp_portal_config keyed by org_id.
    """
    org = await _resolve_org_by_slug(slug)
    if not org:
        raise HTTPException(status_code=404, detail="Org sub-portal not found")
    doc = body.model_dump()
    doc["org_id"] = org["org_id"]
    doc["slug"] = slug
    doc["updated_by"] = user.get("user_id")
    doc["updated_at"] = datetime.now(timezone.utc)
    await db.pp_portal_config.update_one(
        {"org_id": org["org_id"]},
        {"$set": doc},
        upsert=True,
    )
    return {"ok": True, "config": doc}
