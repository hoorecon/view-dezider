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
// bottom-sheet overlay always wins over the page scroller behind it.
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
    // Strongly prefer a scroller that lives inside a modal/bottom-sheet so the
    // page behind the overlay never steals the keys.
    const score = visibleHeight + (insideOverlay(el) ? 1_000_000 : 0);
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

    // Diagnostic tag — users can verify the fix is live by opening DevTools
    // console and typing `__wsf`. If it prints an object, the fix is loaded;
    // if `undefined`, the deployed bundle is stale (hard-refresh needed).
    (window as any).__wsf = { version: 'v3-2026-07-25', ready: true };

    // ── Defensive focus-blur (June 2026) ─────────────────────────
    // When the user clicks a bottom-tab anchor (e.g. "Solution Box"), the
    // <a role="tab"> keeps keyboard focus. Chrome then routes PageUp/Down
    // to that anchor's nearest scrollable ancestor — which is the fixed-
    // position tab bar (not scrollable), so nothing happens until the user
    // clicks INSIDE the content frame. We proactively defocus any tab
    // anchor / button that just received focus via mouse, so PageDown/Space
    // falls through to our window handler cleanly. Keyboard-navigating
    // users (Tab key) are untouched — we only blur when the focus change
    // came from a pointer.
    let lastPointerAt = 0;
    const onPointerDown = () => { lastPointerAt = Date.now(); };
    const onFocusIn = (e: FocusEvent) => {
      const t = e.target as HTMLElement | null;
      if (!t) return;
      // Only defocus if the focus was pointer-triggered (< 100 ms since
      // pointerdown) and the target is a nav-tab role or link — never
      // touch form fields.
      if (Date.now() - lastPointerAt > 100) return;
      const tag = t.tagName?.toLowerCase();
      const role = t.getAttribute?.('role');
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
      if (t.isContentEditable) return;
      if (role === 'textbox' || role === 'combobox') return;
      // Blur tab / link anchors so PageDown/Space stops targeting them.
      if (tag === 'a' || role === 'tab' || role === 'button' || role === 'link') {
        try { (t as any).blur?.(); } catch { /* ignore */ }
      }
    };
    window.addEventListener('pointerdown', onPointerDown, { capture: true, passive: true });
    window.addEventListener('focusin', onFocusIn, { capture: true, passive: true });

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
      window.removeEventListener('pointerdown', onPointerDown, { capture: true } as any);
      window.removeEventListener('focusin', onFocusIn, { capture: true } as any);
    };
  }, []);

  return null;
}
