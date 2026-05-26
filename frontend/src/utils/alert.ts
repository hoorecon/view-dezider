/**
 * Cross-platform alert utility.
 *
 *   • Native (iOS / Android) — delegates to React Native's Alert.alert
 *   • Web                    — emits an event consumed by <AlertHost />
 *                              (mounted in app/_layout.tsx) which renders
 *                              a polished in-app Modal instead of the
 *                              browser's native window.alert / confirm
 *                              dialogs (those look like ChromeOS popups
 *                              and break our brand experience).
 *
 * Public API is unchanged so every existing caller keeps working:
 *
 *     showAlert('Title');
 *     showAlert('Title', 'Optional message');
 *     showAlert('Delete?', 'This is permanent', [
 *       { text: 'Cancel', style: 'cancel' },
 *       { text: 'Delete', style: 'destructive', onPress: doDelete },
 *     ]);
 */
import { Platform, Alert as RNAlert } from 'react-native';

export type AlertButton = {
  text: string;
  style?: 'default' | 'cancel' | 'destructive';
  onPress?: () => void;
};

export interface AlertRequest {
  title: string;
  message?: string;
  buttons?: AlertButton[];
}

// ──────────────────────────────────────────────────────────────────
// Internal pub/sub used by <AlertHost />.
// ──────────────────────────────────────────────────────────────────
type Listener = (req: AlertRequest) => void;
const listeners = new Set<Listener>();

/** @internal — Consumed by <AlertHost />, do not call directly. */
export function _subscribeAlert(fn: Listener): () => void {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

// Fallback to browser dialogs if AlertHost has not mounted yet (e.g.
// alert fired during very early bootstrap before the React tree is
// attached). Keeps behaviour predictable rather than silently dropping.
function fallbackToBrowser(req: AlertRequest) {
  if (typeof window === 'undefined') return;
  const txt = req.message ? `${req.title}\n\n${req.message}` : req.title;
  const cancel = req.buttons?.find((b) => b.style === 'cancel');
  const action = req.buttons?.find((b) => b.style !== 'cancel') || req.buttons?.[req.buttons.length - 1];

  if (!req.buttons || req.buttons.length <= 1) {
    window.alert(txt);
    action?.onPress?.();
  } else {
    const confirmed = window.confirm(txt);
    if (confirmed) action?.onPress?.();
    else cancel?.onPress?.();
  }
}

export function showAlert(
  title: string,
  message?: string,
  buttons?: AlertButton[]
): void {
  if (Platform.OS !== 'web') {
    RNAlert.alert(title, message, buttons as any);
    return;
  }

  const req: AlertRequest = { title, message, buttons };

  if (listeners.size === 0) {
    fallbackToBrowser(req);
    return;
  }

  listeners.forEach((fn) => {
    try { fn(req); } catch (e) { console.warn('alert listener threw', e); }
  });
}

/**
 * Convenience confirmation helper — Promise-based for cleaner async/await
 * call sites. Resolves true when the primary (non-cancel) action is
 * tapped, false on cancel / dismiss.
 */
export function confirmDialog(
  title: string,
  message?: string,
  opts?: { confirmText?: string; cancelText?: string; destructive?: boolean }
): Promise<boolean> {
  return new Promise((resolve) => {
    showAlert(title, message, [
      { text: opts?.cancelText || 'Cancel', style: 'cancel', onPress: () => resolve(false) },
      {
        text: opts?.confirmText || 'OK',
        style: opts?.destructive ? 'destructive' : 'default',
        onPress: () => resolve(true),
      },
    ]);
  });
}
