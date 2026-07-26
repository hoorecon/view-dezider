// @ts-nocheck
import { ScrollViewStyleReset } from "expo-router/html";
import type { PropsWithChildren } from "react";

export default function Root({ children }: PropsWithChildren) {
  return (
    <html lang="en" style={{ height: "100%" }}>
      <head>
        <meta charSet="utf-8" />
        <meta httpEquiv="X-UA-Compatible" content="IE=edge" />
        {/*
          Brand-level <title> fallback for every static page. Per-page SEO is
          provided by <Seo> (expo-router <Head>): it serializes meta description,
          canonical and Open Graph / Twitter tags (incl. per-page og:title) into
          the prerendered HTML. NOTE: expo-router 6 SSG does NOT serialize a
          per-page <title> tag, so og:title carries the per-page title for
          crawlers/social; the client also sets document.title per route
          (app/_layout.tsx). Description is intentionally NOT set here to avoid a
          duplicate with <Seo>.
        */}
        {/*
          The brand <title> is provided once, at the root, via <Head> in
          app/_layout.tsx — it serializes into the static HTML as the first
          <title>. Do NOT set a <title> here (or in page-level <Seo>), else
          expo-router emits a duplicate/empty <title> that wins in the browser
          and shows a blank/app-name tab while loading. Per-page name is carried
          by og:title; the client keeps document.title in sync.
        */}
        <meta
          name="viewport"
          content="width=device-width, initial-scale=1, shrink-to-fit=no"
        />
        {/*
          Disable body scrolling on web to make ScrollView components work correctly.
          If you want to enable scrolling, remove `ScrollViewStyleReset` and
          set `overflow: auto` on the body style below.
        */}
        <ScrollViewStyleReset />
        <style
          dangerouslySetInnerHTML={{
            __html: `
              body > div:first-child { position: fixed !important; top: 0; left: 0; right: 0; bottom: 0; }
              [role="tablist"] [role="tab"] * { overflow: visible !important; }
              [role="heading"], [role="heading"] * { overflow: visible !important; }
            `,
          }}
        />
        {/*
          HTML-level scroll fallback (July 2026)
          ────────────────────────────────────────────────────────────────
          Runs BEFORE any React / expo-router JS. Even if the React bundle
          fails to load, is stale, or WebScrollFix isn't mounted, this
          native inline handler guarantees PageUp / PageDown / Space /
          Home / End / Arrow keys scroll the visible content area.
          Idempotent — tags itself on window so a later React mount won't
          double-attach.
          ────────────────────────────────────────────────────────────────
        */}
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function () {
                if (window.__wsf_html) return;
                window.__wsf_html = { installed_at: Date.now(), version: 'v9-tabindex-on-scrollers' };
                var KEYS = ['PageDown','PageUp','Home','End',' ','Spacebar','ArrowDown','ArrowUp'];
                var lastX = (window.innerWidth||800)/2, lastY = (window.innerHeight||600)/2;
                document.addEventListener('mousemove', function (e) { lastX = e.clientX; lastY = e.clientY; }, { passive: true, capture: true });

                function isScrollable(el) {
                  if (!el || el.nodeType !== 1) return false;
                  if (el.scrollHeight - el.clientHeight < 8) return false;
                  var oy = getComputedStyle(el).overflowY;
                  return oy === 'auto' || oy === 'scroll' || oy === 'overlay';
                }
                function nearestScrollable(node) {
                  var el = node;
                  while (el && el !== document.body && el !== document.documentElement) {
                    if (isScrollable(el)) return el;
                    el = el.parentElement;
                  }
                  return null;
                }
                function isTextEntry(el) {
                  if (!el) return false;
                  var tag = (el.tagName||'').toLowerCase();
                  if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
                  if (el.isContentEditable) return true;
                  var role = el.getAttribute && el.getAttribute('role');
                  return role === 'textbox' || role === 'combobox' || role === 'slider';
                }
                function findBestScroller() {
                  var vh = window.innerHeight || document.documentElement.clientHeight;
                  var best = null, bestScore = -1;
                  var divs = document.querySelectorAll('div');
                  for (var i = 0; i < divs.length; i++) {
                    var el = divs[i];
                    if (!isScrollable(el)) continue;
                    var r = el.getBoundingClientRect();
                    if (r.height < 80) continue;
                    if (r.bottom <= 0 || r.top >= vh) continue;
                    var visH = Math.min(r.bottom, vh) - Math.max(r.top, 0);
                    var overflow = el.scrollHeight - el.clientHeight;
                    var fixedBonus = 0;
                    var walk = el;
                    while (walk && walk !== document.body) {
                      if (getComputedStyle(walk).position === 'fixed') { fixedBonus = 1e9; break; }
                      walk = walk.parentElement;
                    }
                    var score = overflow * 1000 + visH + fixedBonus;
                    if (score > bestScore) { bestScore = score; best = el; }
                  }
                  return best;
                }
                function pickScroller() {
                  var s = nearestScrollable(document.elementFromPoint(lastX, lastY));
                  if (s) return s;
                  s = nearestScrollable(document.activeElement);
                  if (s) return s;
                  return findBestScroller();
                }

                function onKey(e) {
                  if (KEYS.indexOf(e.key) === -1) return;
                  if (isTextEntry(e.target) || isTextEntry(document.activeElement)) return;
                  var isJump = e.key === 'Home' || e.key === 'End';
                  if ((e.ctrlKey || e.metaKey || e.altKey) && !isJump) return;
                  if (e.altKey && isJump) return;
                  var s = pickScroller();
                  if (!s) return;
                  var page = Math.max(s.clientHeight * 0.9, 100);
                  var line = 60;
                  switch (e.key) {
                    case 'PageDown': s.scrollBy({ top: page, behavior: 'smooth' }); break;
                    case 'PageUp':   s.scrollBy({ top: -page, behavior: 'smooth' }); break;
                    case ' ':
                    case 'Spacebar': s.scrollBy({ top: e.shiftKey ? -page : page, behavior: 'smooth' }); break;
                    case 'ArrowDown': s.scrollBy({ top: line, behavior: 'auto' }); break;
                    case 'ArrowUp':   s.scrollBy({ top: -line, behavior: 'auto' }); break;
                    case 'Home': s.scrollTo({ top: 0, behavior: 'smooth' }); break;
                    case 'End':  s.scrollTo({ top: s.scrollHeight, behavior: 'smooth' }); break;
                    default: return;
                  }
                  e.preventDefault();
                }
                function onWheel(e) {
                  if (e.ctrlKey || e.metaKey || e.altKey) return;
                  if (!e.deltaY) return;
                  if (nearestScrollable(e.target)) return;
                  var s = findBestScroller();
                  if (!s) return;
                  var dy = e.deltaY;
                  if (e.deltaMode === 1) dy *= 16;
                  else if (e.deltaMode === 2) dy *= s.clientHeight * 0.9;
                  s.scrollBy({ top: dy, behavior: 'auto' });
                  e.preventDefault();
                }
                window.addEventListener('keydown', onKey, { capture: true, passive: false });
                window.addEventListener('wheel', onWheel, { capture: true, passive: false });

                // ── ScrollView tabIndex tagger (August 2026) ─────────────────
                // Make every RN-Web ScrollView container div focusable via
                // tabIndex=-1. This lets keyboard focus land on the scrollable
                // content itself so PageDown/PageUp/Space route to the right
                // scroller without any preemptive focus-stealing. Uses a
                // MutationObserver so newly-rendered ScrollViews (on route
                // change, modal open, etc.) get the attribute too.
                function tagScroller(el) {
                  if (!el || el.nodeType !== 1) return;
                  if (el.hasAttribute('tabindex')) return;
                  var oy;
                  try { oy = getComputedStyle(el).overflowY; } catch (_) { return; }
                  if (oy !== 'auto' && oy !== 'scroll' && oy !== 'overlay') return;
                  el.setAttribute('tabindex', '-1');
                }
                function scanAll(root) {
                  var divs = (root || document).querySelectorAll ? (root || document).querySelectorAll('div') : [];
                  for (var i = 0; i < divs.length; i++) tagScroller(divs[i]);
                }
                if (document.readyState === 'loading') {
                  document.addEventListener('DOMContentLoaded', function () { scanAll(document); });
                } else {
                  scanAll(document);
                }
                try {
                  var mo = new MutationObserver(function (mutations) {
                    for (var i = 0; i < mutations.length; i++) {
                      var m = mutations[i];
                      for (var j = 0; j < m.addedNodes.length; j++) {
                        var n = m.addedNodes[j];
                        if (n && n.nodeType === 1) {
                          tagScroller(n);
                          if (n.querySelectorAll) {
                            var inner = n.querySelectorAll('div');
                            for (var k = 0; k < inner.length; k++) tagScroller(inner[k]);
                          }
                        }
                      }
                    }
                  });
                  mo.observe(document.body || document.documentElement, { childList: true, subtree: true });
                } catch (_) {}
              })();
            `,
          }}
        />
      </head>
      <body
        style={{
          margin: 0,
          height: "100%",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {children}
      </body>
    </html>
  );
}
