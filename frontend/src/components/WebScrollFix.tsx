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

function findMainScroller(): HTMLElement | null {
  if (typeof document === 'undefined') return null;
  const vh = window.innerHeight || document.documentElement.clientHeight;
  let best: HTMLElement | null = null;
  let bestScore = 0;

  const nodes = document.querySelectorAll('div');
  for (let i = 0; i < nodes.length; i++) {
    const el = nodes[i] as HTMLElement;
    // Must actually have overflowing content
    if (el.scrollHeight - el.clientHeight < 24) continue;

    const style = window.getComputedStyle(el);
    const oy = style.overflowY;
    if (oy !== 'auto' && oy !== 'scroll' && oy !== 'overlay') continue;

    const rect = el.getBoundingClientRect();
    if (rect.height < 120) continue;
    // Must be at least partially visible in viewport
    if (rect.bottom <= 0 || rect.top >= vh) continue;

    const visibleHeight = Math.min(rect.bottom, vh) - Math.max(rect.top, 0);
    if (visibleHeight > bestScore) {
      bestScore = visibleHeight;
      best = el;
    }
  }
  return best;
}

export default function WebScrollFix() {
  useEffect(() => {
    if (Platform.OS !== 'web' || typeof window === 'undefined') return;

    const onKeyDown = (e: KeyboardEvent) => {
      if (!SCROLL_KEYS.has(e.key)) return;
      // Don't hijack typing or in-field navigation
      if (isTextEntry(e.target) || isTextEntry(document.activeElement)) return;
      // Let modifier combos (Ctrl/Cmd/Alt) fall through to the browser
      if (e.ctrlKey || e.metaKey || e.altKey) return;

      const scroller = findMainScroller();
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
    return () => window.removeEventListener('keydown', onKeyDown, { capture: true } as any);
  }, []);

  return null;
}
