"""
Partner Embed — Widget delivery (P1)
====================================

Serves the three browser-facing artefacts that make the embed work on a
partner's website:

  • GET /api/embed/decision/{slug}/loader.js   — the drop-in <script> loader.
        Injects a themed "Help me Decide" button + a modal iframe, and exposes
        window.Dezider.open({options, flow}) for DOM hand-off (P2).
  • GET /api/embed/decision/{slug}/{flow}      — self-contained HTML widget
        (used when render_mode == "html_widget").
  • GET /api/embed/demo-host/{slug}            — the "Generate Partner Page":
        a dynamically themed mock compare layout for ANY partner, with the
        loader already wired in. Doubles as the pitch demo host page.

All pages are iframe-safe (frame-ancestors *) and pull branding from the
partner's decision_embed_config (resolved server-side, anti-spoof).
"""
from __future__ import annotations

import html
import json
from typing import Dict, Any, Optional, Tuple
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from core.database import db
from routes.partner_embed import VALID_FLOWS

router = APIRouter(prefix="/embed", tags=["Partner Embed Widget"])

FLOW_LABELS = {
    "mydezider": "MyDezider — Weighted Decision",
    "pros_cons": "Pros & Cons Analysis",
    "screener": "Smart Screener",
}
_IFRAME_HEADERS = {
    "X-Frame-Options": "ALLOWALL",
    "Content-Security-Policy": "frame-ancestors *",
    "Cache-Control": "no-store",
}


# ------------------------------------------------------------------
async def _load(slug: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    org = await db.organizations.find_one({"slug": (slug or "").strip().lower()}, {"_id": 0})
    if not org:
        raise HTTPException(status_code=404, detail="Partner not found")
    cfg = await db.decision_embed_config.find_one({"org_id": org["id"]}, {"_id": 0}) or {}
    return org, cfg


def _theme(org: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    t = cfg.get("theme") or {}
    return {
        "name": org.get("name") or "Decision Tools",
        "primary": t.get("primary_color") or org.get("primary_color") or "#7C3AED",
        "accent": t.get("accent_color") or org.get("accent_color") or "#C9A24B",
        "logo": t.get("logo_uri") or org.get("logo_url") or "",
        "white_label": cfg.get("branding_mode", "white_label") == "white_label",
        "hide_powered_by": bool(t.get("hide_powered_by", False)),
        "render_mode": cfg.get("render_mode", "rn_web"),
        "enabled_flows": cfg.get("enabled_flows", ["mydezider", "pros_cons"]),
    }


def _powered_by(th: Dict[str, Any]) -> str:
    if th["hide_powered_by"]:
        return ""
    return ('<div style="text-align:center;padding:8px;font-size:11px;color:#9CA3AF;">'
            'Powered by View Dezider</div>')


# ------------------------------------------------------------------
# 1) Drop-in JS loader  (per-slug; bakes urls + render_mode)
# ------------------------------------------------------------------
@router.get("/decision/{slug}/loader.js")
async def embed_loader_js(slug: str, request: Request):
    org, cfg = await _load(slug)
    th = _theme(org, cfg)
    root = str(request.base_url).rstrip("/")
    render_mode = th["render_mode"]
    primary = th["primary"]
    default_flow = (th["enabled_flows"] or ["mydezider"])[0]

    # src builder is computed client-side so host can override flow + pass options
    js = f"""(function(){{
  var ROOT = {json.dumps(root)};
  var SLUG = {json.dumps(slug)};
  var RENDER_MODE = {json.dumps(render_mode)};
  var PRIMARY = {json.dumps(primary)};
  var DEFAULT_FLOW = {json.dumps(default_flow)};

  function buildSrc(flow, options){{
    flow = flow || DEFAULT_FLOW;
    var src;
    if (RENDER_MODE === 'html_widget') {{
      src = ROOT + '/api/embed/decision/' + encodeURIComponent(SLUG) + '/' + encodeURIComponent(flow);
    }} else {{
      src = ROOT + '/embed/' + encodeURIComponent(flow) + '?partner=' + encodeURIComponent(SLUG);
    }}
    if (options && options.length) {{
      var payload = encodeURIComponent(JSON.stringify(options));
      src += (src.indexOf('?') >= 0 ? '&' : '?') + 'options=' + payload;
    }}
    return src;
  }}

  function ensureModal(){{
    var existing = document.getElementById('dezider-modal');
    if (existing) return existing;
    var overlay = document.createElement('div');
    overlay.id = 'dezider-modal';
    overlay.style.cssText = 'position:fixed;inset:0;z-index:2147483000;background:rgba(15,23,42,.55);display:none;align-items:center;justify-content:center;padding:16px;';
    var box = document.createElement('div');
    box.style.cssText = 'position:relative;width:100%;max-width:760px;height:88vh;max-height:900px;background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 24px 60px rgba(0,0,0,.35);';
    var close = document.createElement('button');
    close.setAttribute('aria-label','Close');
    close.innerHTML = '&times;';
    close.style.cssText = 'position:absolute;top:8px;right:10px;z-index:5;border:none;background:rgba(255,255,255,.9);color:#111;width:34px;height:34px;border-radius:17px;font-size:22px;line-height:1;cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,.2);';
    close.onclick = function(){{ overlay.style.display='none'; var f=document.getElementById('dezider-frame'); if(f) f.src='about:blank'; }};
    var frame = document.createElement('iframe');
    frame.id = 'dezider-frame';
    frame.setAttribute('allow','clipboard-write; microphone; camera; geolocation');
    frame.setAttribute('title','Decision Tool');
    frame.style.cssText = 'width:100%;height:100%;border:0;';
    box.appendChild(close); box.appendChild(frame); overlay.appendChild(box);
    document.body.appendChild(overlay);
    overlay.addEventListener('click', function(e){{ if(e.target===overlay) close.onclick(); }});
    return overlay;
  }}

  window.addEventListener('message', function(e){{
    var d = e.data || {{}};
    if (d && d.type === 'dezider:close') {{ var o=document.getElementById('dezider-modal'); if(o){{o.style.display='none'; var f=document.getElementById('dezider-frame'); if(f) f.src='about:blank';}} }}
  }});

  window.Dezider = window.Dezider || {{}};
  window.Dezider.open = function(opts){{
    opts = opts || {{}};
    var overlay = ensureModal();
    var frame = document.getElementById('dezider-frame');
    frame.src = buildSrc(opts.flow, opts.options || []);
    overlay.style.display = 'flex';
  }};
  window.Dezider.buildSrc = buildSrc;

  function mountFab(){{
    if (document.getElementById('dezider-fab')) return;
    // auto-wire any element marked data-dezider-open
    var triggers = document.querySelectorAll('[data-dezider-open]');
    triggers.forEach(function(el){{
      el.addEventListener('click', function(ev){{
        ev.preventDefault();
        var flow = el.getAttribute('data-dezider-flow') || DEFAULT_FLOW;
        window.Dezider.open({{ flow: flow }});
      }});
    }});
    if (triggers.length) return;  // host provides its own button
    var fab = document.createElement('button');
    fab.id = 'dezider-fab';
    fab.textContent = 'Help me Decide';
    fab.style.cssText = 'position:fixed;right:20px;bottom:20px;z-index:2147482000;border:none;background:'+PRIMARY+';color:#fff;font-weight:700;font-size:14px;padding:13px 18px;border-radius:26px;box-shadow:0 8px 24px rgba(0,0,0,.25);cursor:pointer;';
    fab.onclick = function(){{ window.Dezider.open({{}}); }};
    document.body.appendChild(fab);
  }}

  if (document.readyState === 'loading') {{ document.addEventListener('DOMContentLoaded', mountFab); }} else {{ mountFab(); }}
}})();"""
    return Response(content=js, media_type="application/javascript",
                    headers={"Cache-Control": "public, max-age=120", "Access-Control-Allow-Origin": "*"})


# ------------------------------------------------------------------
# 2) Self-contained HTML widget  (render_mode == html_widget)
# ------------------------------------------------------------------
@router.get("/decision/{slug}/{flow}", response_class=HTMLResponse)
async def embed_html_widget(slug: str, flow: str, request: Request, options: Optional[str] = None):
    if flow not in VALID_FLOWS:
        raise HTTPException(404, "Unknown flow")
    org, cfg = await _load(slug)
    th = _theme(org, cfg)
    root = str(request.base_url).rstrip("/")

    parsed_opts = []
    if options:
        try:
            parsed_opts = json.loads(options)
        except Exception:
            parsed_opts = []

    primary = html.escape(th["primary"]); accent = html.escape(th["accent"])
    name = html.escape(th["name"]); flow_label = html.escape(FLOW_LABELS.get(flow, flow))
    logo_html = (f'<img src="{html.escape(th["logo"])}" alt="" style="height:26px;border-radius:6px;"/>'
                 if th["logo"] else f'<strong style="font-size:16px;">{name}</strong>')
    rn_url = f"{root}/embed/{quote(flow)}?partner={quote(slug)}"
    if parsed_opts:
        rn_url += "&options=" + quote(json.dumps(parsed_opts))

    opts_html = ""
    if parsed_opts:
        rows = "".join(
            f'<li style="padding:10px 12px;border:1px solid #E5E7EB;border-radius:10px;margin-bottom:8px;">'
            f'<strong>{html.escape(str(o.get("name", o) if isinstance(o, dict) else o))}</strong>'
            + (f'<div style="font-size:12px;color:#6B7280;margin-top:2px;">'
               + html.escape(", ".join(f"{k}: {v}" for k, v in (o.get("attributes") or {}).items()))
               + '</div>' if isinstance(o, dict) and o.get("attributes") else "")
            + '</li>'
            for o in parsed_opts
        )
        opts_html = (f'<div style="margin:14px 0;"><div style="font-size:12px;font-weight:700;color:#374151;'
                     f'text-transform:uppercase;letter-spacing:.04em;margin-bottom:8px;">'
                     f'{len(parsed_opts)} option(s) carried over</div><ul style="list-style:none;padding:0;margin:0;">{rows}</ul></div>')

    body = f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{name} — {flow_label}</title>
<style>
:root {{ --c:{primary}; --a:{accent}; }}
*{{box-sizing:border-box;}} body{{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#F8FAFC;color:#0F172A;}}
header{{background:var(--c);color:#fff;padding:14px 18px;display:flex;align-items:center;gap:10px;}}
main{{padding:18px;max-width:680px;margin:0 auto;}}
.card{{background:#fff;border:1px solid #E5E7EB;border-radius:14px;padding:18px;box-shadow:0 1px 2px rgba(0,0,0,.03);}}
.badge{{display:inline-block;background:var(--a);color:#1f2937;font-size:11px;font-weight:700;padding:3px 9px;border-radius:10px;}}
.cta{{display:block;text-align:center;background:var(--c);color:#fff;text-decoration:none;font-weight:700;padding:13px;border-radius:10px;margin-top:14px;}}
h1{{font-size:18px;margin:6px 0;}} p{{color:#475569;font-size:14px;line-height:1.5;}}
</style></head><body>
<header>{logo_html}<span style="margin-left:auto;font-size:12px;opacity:.85;">{flow_label}</span></header>
<main>
  <div class="card">
    <span class="badge">{flow_label}</span>
    <h1>Make this decision with confidence</h1>
    <p>Bring your shortlisted options into a structured, weighted decision — factors, priorities and a clear recommendation. Your selections from {name} are carried over automatically.</p>
    {opts_html}
    <a class="cta" href="{html.escape(rn_url)}" target="_top">Start {flow_label} &rarr;</a>
  </div>
  {_powered_by(th)}
</main>
</body></html>"""
    return HTMLResponse(content=body, headers=_IFRAME_HEADERS)


# ------------------------------------------------------------------
# 3) "Generate Partner Page" — dynamic mock compare host for ANY partner
# ------------------------------------------------------------------
_SAMPLE_ITEMS = [
    {"name": "Money Grow Asset — Small Midcap", "tags": ["Small & Mid Cap"],
     "attributes": {"1Y Return": "44.39%", "AUM (Cr)": "121.47", "Benchmark": "Nifty 50 TRI"}},
    {"name": "Hem Securities — India Rising SME Stars", "tags": ["Small Cap"],
     "attributes": {"1Y Return": "36.77%", "AUM (Cr)": "95.01", "Benchmark": "S&P BSE 500 TRI"}},
    {"name": "Green Portfolio — Super 30 Dynamic Fund", "tags": ["Multi Cap"],
     "attributes": {"1Y Return": "31.92%", "AUM (Cr)": "212.02", "Benchmark": "S&P BSE 500 TRI"}},
]


@router.get("/demo-host/{slug}", response_class=HTMLResponse)
async def embed_demo_host(slug: str, request: Request, flow: str = "mydezider"):
    """Dynamically generate a partner-themed mock 'compare' page with the
    'Help me Decide' loader wired in. Works for ANY partner slug."""
    if flow not in VALID_FLOWS:
        flow = "mydezider"
    org, cfg = await _load(slug)
    th = _theme(org, cfg)
    root = str(request.base_url).rstrip("/")
    primary = html.escape(th["primary"]); accent = html.escape(th["accent"])
    name = html.escape(th["name"])
    loader_src = f"{root}/api/embed/decision/{quote(slug)}/loader.js"

    cards = ""
    for i, it in enumerate(_SAMPLE_ITEMS):
        attrs = "".join(
            f'<div style="display:flex;justify-content:space-between;font-size:13px;padding:3px 0;border-bottom:1px dashed #EEF2F7;">'
            f'<span style="color:#64748B;">{html.escape(k)}</span><strong>{html.escape(v)}</strong></div>'
            for k, v in it["attributes"].items()
        )
        tags = "".join(f'<span style="background:#EEF2FF;color:#4338CA;font-size:11px;padding:2px 8px;border-radius:10px;margin-right:6px;">{html.escape(t)}</span>' for t in it["tags"])
        cards += f"""
      <div class="row" data-idx="{i}">
        <label class="cmp"><input type="checkbox" class="pick" data-name="{html.escape(it['name'])}" checked/> Compare</label>
        <div style="flex:1;">
          <div style="font-weight:700;">{html.escape(it['name'])}</div>
          <div style="margin:6px 0;">{tags}</div>
          {attrs}
        </div>
      </div>"""

    page = f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{name} — Compare (Demo)</title>
<style>
:root {{ --c:{primary}; --a:{accent}; }}
*{{box-sizing:border-box;}} body{{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:#F1F5F9;color:#0F172A;}}
header{{background:var(--c);color:#fff;padding:14px 20px;display:flex;align-items:center;gap:14px;}}
header .brand{{font-size:20px;font-weight:800;}} header nav{{margin-left:auto;display:flex;gap:18px;font-size:13px;opacity:.92;}}
.bar{{background:#fff;border-bottom:1px solid #E2E8F0;padding:10px 20px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;}}
.bar input,.bar select{{padding:8px 10px;border:1px solid #CBD5E1;border-radius:8px;font-size:13px;}}
main{{max-width:900px;margin:0 auto;padding:18px 20px 120px;}}
.row{{background:#fff;border:1px solid #E2E8F0;border-radius:12px;padding:14px;margin-bottom:12px;display:flex;gap:14px;align-items:flex-start;}}
.cmp{{font-size:12px;color:#475569;display:flex;flex-direction:column;align-items:center;gap:4px;min-width:64px;}}
.decide{{position:fixed;right:22px;bottom:22px;z-index:50;border:none;background:var(--c);color:#fff;font-weight:800;font-size:15px;padding:14px 22px;border-radius:30px;box-shadow:0 10px 28px rgba(0,0,0,.28);cursor:pointer;}}
.pill{{background:var(--a);color:#1f2937;font-size:11px;font-weight:800;padding:3px 9px;border-radius:10px;}}
h2{{font-size:15px;color:#334155;margin:6px 0 12px;}}
</style></head><body>
<header>
  <div class="brand">{name}</div>
  <nav><span>Discover</span><span>Comparison</span><span>Research</span><span>Learn</span></nav>
</header>
<div class="bar">
  <input placeholder="Search investments" style="flex:1;min-width:180px;"/>
  <select><option>All Categories</option><option>Small Cap</option><option>Multi Cap</option></select>
  <select><option>1 Year Return</option><option>3 Year</option></select>
  <span class="pill">DEMO HOST PAGE</span>
</div>
<main>
  <h2>Compare investment approaches — then let the embedded decision engine rank them for you.</h2>
  {cards}
</main>

<button class="decide" id="decideBtn" data-dezider-flow="{html.escape(flow)}">Help me Decide</button>

<script src="{html.escape(loader_src)}" data-flow="{html.escape(flow)}"></script>
<script>
  // DOM hand-off: collect checked compare items and pass to the embedded tool.
  document.getElementById('decideBtn').addEventListener('click', function(e){{
    e.preventDefault();
    var picks = Array.prototype.slice.call(document.querySelectorAll('.pick:checked')).map(function(c){{
      var row = c.closest('.row');
      var attrs = {{}};
      row.querySelectorAll('div[style*="space-between"]').forEach(function(d){{
        var sp = d.querySelector('span'); var st = d.querySelector('strong');
        if (sp && st) attrs[sp.textContent.trim()] = st.textContent.trim();
      }});
      return {{ name: c.getAttribute('data-name'), attributes: attrs }};
    }});
    window.Dezider.open({{ flow: {json.dumps(flow)}, options: picks }});
  }});
</script>
</body></html>"""
    return HTMLResponse(content=page, headers=_IFRAME_HEADERS)
