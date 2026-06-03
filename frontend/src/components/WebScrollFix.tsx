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
      // Let modifier combos (Ctrl/Cmd/Alt) fall through to the browser
      if (e.ctrlKey || e.metaKey || e.altKey) return;

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
          scroller.scrollTop = 0;
          break;
        case 'End':
          scroller.scrollTop = scroller.scrollHeight;
          break;
        default:
          return;
      }
      e.preventDefault();
    };

    window.addEventListener('keydown', onKeyDown, { capture: true, passive: false });
    return () => {
      window.removeEventListener('keydown', onKeyDown, { capture: true } as any);
      window.removeEventListener('mousemove', onMove as any);
    };
  }, []);

  return null;
}
