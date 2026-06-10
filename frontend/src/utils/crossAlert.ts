import { Alert as RNAlert, Platform } from 'react-native';

export type CrossAlertButton = {
  text?: string;
  style?: 'default' | 'cancel' | 'destructive';
  onPress?: () => void;
};

/**
 * Web-compatible replacement for React Native's `Alert.alert`.
 *
 * React Native's `Alert.alert` is a NO-OP on react-native-web, which silently
 * swallows validation messages, AI-error prompts and confirm dialogs when the
 * app runs in a browser (e.g. jelcos.ai). This shim maps to `window.alert` /
 * `window.confirm` on web and to the native Alert on iOS/Android, keeping the
 * exact same call signature so existing `Alert.alert(...)` calls work unchanged.
 */
function webAlert(
  title: string,
  message?: string,
  buttons?: CrossAlertButton[],
): void {
  const full = message ? `${title}\n\n${message}` : title;
  const w = typeof window !== 'undefined' ? window : undefined;

  if (!buttons || buttons.length <= 1) {
    w?.alert(full);
    buttons?.[0]?.onPress?.();
    return;
  }

  // 2+ buttons → confirm. OK runs the first non-cancel (primary) action,
  // Cancel runs the cancel button's handler (if any).
  const primary = buttons.find((b) => b.style !== 'cancel') ?? buttons[buttons.length - 1];
  const cancel = buttons.find((b) => b.style === 'cancel');
  const ok = w ? w.confirm(full) : true;
  if (ok) primary?.onPress?.();
  else cancel?.onPress?.();
}

export const Alert = {
  alert(
    title: string,
    message?: string,
    buttons?: CrossAlertButton[],
    options?: { cancelable?: boolean; onDismiss?: () => void },
  ): void {
    if (Platform.OS === 'web') {
      webAlert(title, message, buttons);
      return;
    }
    RNAlert.alert(title, message as any, buttons as any, options as any);
  },
};
