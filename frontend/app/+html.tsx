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
                window.__wsf_html = { installed_at: Date.now() };
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
                    // Prefer scrollers with the most content to reveal (overflow) —
                    // guarantees a tab's main list beats any tiny horizontal filter strip.
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
                // Defocus tab-bar anchors on mouse click so PageDown never
                // targets a non-scrollable fixed-position button.
                var lastPointerAt = 0;
                document.addEventListener('pointerdown', function () { lastPointerAt = Date.now(); }, { capture: true, passive: true });
                document.addEventListener('focusin', function (e) {
                  var t = e.target; if (!t) return;
                  if (Date.now() - lastPointerAt > 100) return;
                  var tag = (t.tagName||'').toLowerCase();
                  var role = t.getAttribute && t.getAttribute('role');
                  if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
                  if (t.isContentEditable) return;
                  if (role === 'textbox' || role === 'combobox') return;
                  if (tag === 'a' || role === 'tab' || role === 'button' || role === 'link') {
                    try { t.blur && t.blur(); } catch (_) {}
                  }
                }, { capture: true, passive: true });

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

                // Auto-focus body so keys route to us WITHOUT any user click first.
                // Chrome's URL bar retains focus after typing a URL — this ONLY
                // yields to the page if an autofocus'd element grabs focus first
                // (see the hidden #wsf-focus-grabber input rendered in <body>).
                function grabFocus() {
                  try {
                    if (document.body.getAttribute('tabindex') === null) {
                      document.body.setAttribute('tabindex', '-1');
                    }
                    // Drop the grabber if it still holds focus, forwarding to body.
                    var g = document.getElementById('wsf-focus-grabber');
                    if (g && document.activeElement === g) {
                      g.blur();
                      document.body.focus({ preventScroll: true });
                      return;
                    }
                    var ae = document.activeElement;
                    if (!ae || ae === document.body || ae === document.documentElement) {
                      document.body.focus({ preventScroll: true });
                    }
                  } catch (_) {}
                }
                if (document.readyState === 'loading') {
                  document.addEventListener('DOMContentLoaded', grabFocus);
                } else {
                  grabFocus();
                }
                setTimeout(grabFocus, 200);
                setTimeout(grabFocus, 800);
                window.addEventListener('popstate', function () { setTimeout(grabFocus, 60); });

                // ── Client-side navigation hook ─────────────────
                // expo-router uses history.pushState/replaceState which
                // never trigger popstate. Wrap both to emit a synthetic
                // "wsf:navigation" event, then grab focus back to body
                // after every route change (tab click, deep-link, etc.).
                try {
                  if (!window.history.__wsf_patched) {
                    window.history.__wsf_patched = true;
                    var origPush = window.history.pushState.bind(window.history);
                    var origReplace = window.history.replaceState.bind(window.history);
                    window.history.pushState = function () {
                      var r = origPush.apply(this, arguments);
                      try { window.dispatchEvent(new Event('wsf:navigation')); } catch (_) {}
                      return r;
                    };
                    window.history.replaceState = function () {
                      var r = origReplace.apply(this, arguments);
                      try { window.dispatchEvent(new Event('wsf:navigation')); } catch (_) {}
                      return r;
                    };
                  }
                } catch (_) {}
                window.addEventListener('wsf:navigation', function () { setTimeout(grabFocus, 60); });
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
        {/* HTML autofocus grabber — the one browser-sanctioned way to
            steal keyboard focus back from Chrome's URL bar after a fresh
            navigation. Chrome honors the `autofocus` attribute even when
            the URL bar was previously focused, unlike element.focus()
            from JS. The inline script above blurs this immediately after
            mount and forwards focus to <body> so tab-order isn't skewed. */}
        <input
          id="wsf-focus-grabber"
          tabIndex={-1}
          autoFocus
          readOnly
          aria-hidden="true"
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: 1,
            height: 1,
            opacity: 0,
            pointerEvents: 'none',
            border: 0,
            padding: 0,
          }}
        />
        {children}
      </body>
    </html>
  );
}
