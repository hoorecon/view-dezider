/**
 * WebScrollFix — global keyboard scrolling for web.
 *
 * Problem:
 *   On React Native Web, every screen's <ScrollView> renders as an inner
 *   <div style="overflow-y:scroll">. Browser keyboard scrolling (PageUp,
 *   PageDown, Space, Home, End, arrows) only acts on the *focused* scrollable
 *   element or the document body. Because the body itself is NOT the scroller
 *   (the inner ScrollView div is), pressing PageDown does nothing until the
 *   user first clicks *inside* the container to focus it. That extra click is
 *   an awkward, unprofessional UX.
 *
 * Fix:
 *   Attach a single window-level "keydown" listener (web only). When a scroll
 *   key is pressed and focus is NOT in a text field, locate the main visible
 *   scroll container and scroll it programmatically. This works regardless of
 *   which child element currently has focus — so PageUp/PageDown work the
 *   moment the page has focus, without any click inside the container.
 *
 * Native (iOS/Android): renders nothing, attaches nothing.
 */
import { useEffect } from 'react';
import { Platform } from 'react-native';

const SCROLL_KEYS = new Set([
  'PageDown',
  'PageUp',
  'Home',
  'End',
  ' ',          // Space
  'Spacebar',   // legacy Space key value
  'ArrowDown',
  'ArrowUp',
]);

function isTextEntry(el: any): boolean {
  if (!el) return false;
  const tag = (el.tagName || '').toLowerCase();
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
  if (el.isContentEditable) return true;
  // ARIA roles that capture keyboard
  const role = el.getAttribute && el.getAttribute('role');
  if (role === 'textbox' || role === 'combobox' || role === 'slider') return true;
  return false;
}

function isScrollable(el: any): boolean {
  if (!el || el.nodeType !== 1) return false;
  if (el.scrollHeight - el.clientHeight < 8) return false;
  const oy = window.getComputedStyle(el).overflowY;
  return oy === 'auto' || oy === 'scroll' || oy === 'overlay';
}

// Walk up from a node to the first scrollable ancestor (inclusive).
function nearestScrollable(node: any): HTMLElement | null {
  let el = node as HTMLElement | null;
  while (el && el !== document.body && el !== document.documentElement) {
    if (isScrollable(el)) return el;
    el = el.parentElement;
  }
  return null;
}

// Is this element inside a fixed-position overlay (modal / bottom-sheet)?
function insideOverlay(node: any): boolean {
  let el = node as HTMLElement | null;
  while (el && el !== document.body) {
    if (window.getComputedStyle(el).position === 'fixed') return true;
    el = el.parentElement;
  }
  return false;
}

// Fallback: the most relevant visible scroller. A scroller inside a modal /
// bottom-sheet overlay always wins over the page scroller behind it. Also
// heavily weighs by content-overflow size (scrollHeight − clientHeight) so
// the tab's main list beats any tiny horizontal filter strip.
function findBestScroller(): HTMLElement | null {
  if (typeof document === 'undefined') return null;
  const vh = window.innerHeight || document.documentElement.clientHeight;
  let best: HTMLElement | null = null;
  let bestScore = -1;

  const nodes = document.querySelectorAll('div');
  for (let i = 0; i < nodes.length; i++) {
    const el = nodes[i] as HTMLElement;
    if (!isScrollable(el)) continue;

    const rect = el.getBoundingClientRect();
    if (rect.height < 80) continue;
    // Must be at least partially visible in viewport
    if (rect.bottom <= 0 || rect.top >= vh) continue;

    const visibleHeight = Math.min(rect.bottom, vh) - Math.max(rect.top, 0);
    const overflow = el.scrollHeight - el.clientHeight;
    // Score:
    //   • overflow×1000 — a scroller with more content to reveal always wins
    //   • visibleHeight — tiebreak by on-screen size
    //   • +1e9 if inside a fixed-position overlay (modal/bottom-sheet), so
    //     modals steal keys from the page behind.
    const score = overflow * 1000 + visibleHeight + (insideOverlay(el) ? 1_000_000_000 : 0);
    if (score > bestScore) {
      bestScore = score;
      best = el;
    }
  }
  return best;
}

// The document's own scroller (html/body) — used when no inner scrollable
// <div> owns the content (some screens let the page itself scroll).
function documentScroller(): HTMLElement | null {
  if (typeof document === 'undefined') return null;
  const de = (document.scrollingElement || document.documentElement) as HTMLElement;
  if (de && de.scrollHeight - de.clientHeight >= 8) return de;
  return null;
}

export default function WebScrollFix() {
  useEffect(() => {
    if (Platform.OS !== 'web' || typeof window === 'undefined') return;
    // If the HTML-level inline fallback (see app/+html.tsx) has already
    // installed itself, skip — its listeners are identical and it runs
    // before React mounts, so avoiding double-attach keeps behaviour clean.
    if ((window as any).__wsf_html) {
      (window as any).__wsf = { version: 'v10-2026-07-26-008-julyfix', ready: true, delegated_to_html_inline: true };
      return;
    }

    (window as any).__wsf = { version: 'v10-2026-07-26-008-julyfix', ready: true };

    // ── ScrollView tabIndex tagger (July 2026) ──────────────────
    // Make every RN-Web ScrollView container div focusable via
    // tabIndex=-1. This lets keyboard focus land on the scrollable
    // content itself so PageDown / PageUp / Space route to the right
    // scroller without any preemptive focus-stealing. Uses a
    // MutationObserver so newly-rendered ScrollViews (route change,
    // modal open, etc.) get the attribute too.
    const tagScroller = (el: Element) => {
      if (!el || el.nodeType !== 1) return;
      if ((el as HTMLElement).hasAttribute('tabindex')) return;
      let oy: string;
      try { oy = getComputedStyle(el).overflowY; } catch { return; }
      if (oy !== 'auto' && oy !== 'scroll' && oy !== 'overlay') return;
      (el as HTMLElement).setAttribute('tabindex', '-1');
    };
    const scanAll = (root: ParentNode = document) => {
      const divs = root.querySelectorAll?.('div') || [];
      divs.forEach(tagScroller);
    };
    scanAll();
    let mo: MutationObserver | null = null;
    try {
      mo = new MutationObserver((mutations) => {
        for (const m of mutations) {
          m.addedNodes.forEach((n) => {
            if (n && (n as Element).nodeType === 1) {
              tagScroller(n as Element);
              const inner = (n as Element).querySelectorAll?.('div') || [];
              inner.forEach(tagScroller);
            }
          });
        }
      });
      mo.observe(document.body || document.documentElement, { childList: true, subtree: true });
    } catch { /* ignore */ }

    // Track the pointer so we can scroll whatever the cursor is over. This is
    // what makes modals / bottom-sheets / split panes scroll correctly instead
    // of the page behind them.
    let lastX = (window.innerWidth || 800) / 2;
    let lastY = (window.innerHeight || 600) / 2;
    const onMove = (e: MouseEvent) => { lastX = e.clientX; lastY = e.clientY; };
    window.addEventListener('mousemove', onMove, { passive: true });

    const pickScroller = (): HTMLElement | null => {
      // 1) Scroller under the mouse pointer (handles modals & multi-pane).
      let s = nearestScrollable(document.elementFromPoint(lastX, lastY));
      if (s) return s;
      // 2) Scroller that owns the currently focused element (keyboard users).
      s = nearestScrollable(document.activeElement);
      if (s) return s;
      // 3) Best visible inner scroller — a modal/bottom-sheet scroller wins.
      s = findBestScroller();
      if (s) return s;
      // 4) Last resort: the document itself (page-level scrolling).
      return documentScroller();
    };

    const onKeyDown = (e: KeyboardEvent) => {
      if (!SCROLL_KEYS.has(e.key)) return;
      // Don't hijack typing or in-field navigation
      if (isTextEntry(e.target) || isTextEntry(document.activeElement)) return;

      // Allow Ctrl/Cmd + Home/End site-wide as conventional jump-to-top /
      // jump-to-bottom shortcuts (especially useful for long PDF / Share /
      // Step-7 / admin runs pages where the inner RN ScrollView owns the
      // scroll and the browser's own Ctrl+Home/End hits the body instead).
      // Every other modifier combo still falls through to the browser.
      const isJumpKey = e.key === 'Home' || e.key === 'End';
      if ((e.ctrlKey || e.metaKey || e.altKey) && !isJumpKey) return;
      // Plain Alt/Ctrl+ArrowKeys etc. → let the browser handle.
      if (e.altKey && isJumpKey) return;

      const scroller = pickScroller();
      if (!scroller) return;

      const page = Math.max(scroller.clientHeight * 0.9, 100);
      const line = 60;

      switch (e.key) {
        case 'PageDown':
          scroller.scrollBy({ top: page, behavior: 'smooth' });
          break;
        case 'PageUp':
          scroller.scrollBy({ top: -page, behavior: 'smooth' });
          break;
        case ' ':
        case 'Spacebar':
          scroller.scrollBy({ top: e.shiftKey ? -page : page, behavior: 'smooth' });
          break;
        case 'ArrowDown':
          scroller.scrollBy({ top: line, behavior: 'auto' });
          break;
        case 'ArrowUp':
          scroller.scrollBy({ top: -line, behavior: 'auto' });
          break;
        case 'Home':
          scroller.scrollTo({ top: 0, behavior: 'smooth' });
          // Also reset document scroll so headers/footers come into view
          if (e.ctrlKey || e.metaKey) {
            try { window.scrollTo({ top: 0, behavior: 'smooth' }); } catch { /* ignore */ }
          }
          break;
        case 'End':
          scroller.scrollTo({ top: scroller.scrollHeight, behavior: 'smooth' });
          if (e.ctrlKey || e.metaKey) {
            try {
              window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' });
            } catch { /* ignore */ }
          }
          break;
        default:
          return;
      }
      e.preventDefault();
    };

    // ------------------------------------------------------------------
    // Mouse-wheel forwarding (June 2026)
    // ------------------------------------------------------------------
    // On desktop web ≥ 768px, WebFrame centres non-landing routes in a
    // 960 px-wide card. The grey/lavender gutters on either side are NOT
    // scrollable, so a wheel event over that area is a no-op — the user
    // has to physically move the pointer into the card first. Similarly,
    // on screens where the header/filter bar sits OUTSIDE a FlatList
    // (e.g. /prr, Solution Box), the top ~200 px inside the card is also
    // non-scrollable, forcing another click.
    //
    // Fix: when a wheel event fires over an element that is NOT inside
    // any real scroller, forward its deltaY to the best visible scroller
    // (the inner ScrollView). This matches Dashboard's "wheel anywhere"
    // feel on every tab, without changing any screen's layout.
    // ------------------------------------------------------------------
    const onWheel = (e: WheelEvent) => {
      // Only handle plain vertical wheel — leave horizontal / zoom (ctrl+wheel)
      // to the browser.
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.deltaY === 0) return;

      // If the event's own target already has a scrollable ancestor, the
      // browser will handle it natively — do nothing.
      const nativeScroller = nearestScrollable(e.target);
      if (nativeScroller) return;

      // Forward to the best visible scroller (typically the tab's ScrollView).
      const scroller = findBestScroller() || documentScroller();
      if (!scroller) return;

      // Convert wheel line/page deltas to pixels (matches browser defaults).
      let dy = e.deltaY;
      if (e.deltaMode === 1) dy *= 16;                              // lines → px
      else if (e.deltaMode === 2) dy *= scroller.clientHeight * 0.9; // pages → px

      scroller.scrollBy({ top: dy, behavior: 'auto' });
      e.preventDefault();
    };

    window.addEventListener('keydown', onKeyDown, { capture: true, passive: false });
    window.addEventListener('wheel', onWheel, { capture: true, passive: false });
    return () => {
      window.removeEventListener('keydown', onKeyDown, { capture: true } as any);
      window.removeEventListener('wheel', onWheel, { capture: true } as any);
      window.removeEventListener('mousemove', onMove as any);
      try { mo?.disconnect(); } catch { /* ignore */ }
    };
  }, []);

  return null;
}
