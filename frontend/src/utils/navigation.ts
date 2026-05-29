/**
 * Smart navigation helpers for expo-router.
 *
 * Why?
 * ----
 * On Web, when a user lands on a deep-link (`/tools/new-decision?module=…`)
 * directly (e.g., from a notification, a shared URL, or the prod EC2 redirect)
 * there is no in-app history. Calling `router.back()` then walks the browser
 * one step backward — straight OUT of `jelcos.ai` to a blank page (or the
 * referrer). That's a hard dead-end for the user.
 *
 * `safeBack` checks `router.canGoBack()` first and falls back to navigating
 * to the Home tab. The user is never stranded.
 */
import type { Router } from 'expo-router';

export function safeBack(router: Router) {
  try {
    if (typeof (router as any).canGoBack === 'function' && (router as any).canGoBack()) {
      router.back();
      return;
    }
  } catch (_e) { /* fall through to home fallback */ }
  // No in-app history → land on Home (root). `replace` so the user can't
  // browser-back into the now-broken state.
  try { router.replace('/' as any); } catch (_e) { /* noop */ }
}

/** Always go to Home tab — useful for explicit "Home" buttons in headers. */
export function goHome(router: Router) {
  try { router.replace('/' as any); } catch (_e) { /* noop */ }
}
