/**
 * Cross-platform alert utility.
 * On native: uses React Native's Alert.alert
 * On web: uses window.alert / window.confirm for better compatibility
 */
import { Platform, Alert as RNAlert } from 'react-native';

type AlertButton = {
  text: string;
  style?: 'default' | 'cancel' | 'destructive';
  onPress?: () => void;
};

export function showAlert(
  title: string,
  message?: string,
  buttons?: AlertButton[]
) {
  if (Platform.OS === 'web') {
    if (!buttons || buttons.length <= 1) {
      // Simple alert
      window.alert(message ? `${title}\n\n${message}` : title);
      if (buttons && buttons[0]?.onPress) {
        buttons[0].onPress();
      }
    } else {
      // Confirmation dialog
      const cancelBtn = buttons.find(b => b.style === 'cancel');
      const actionBtn = buttons.find(b => b.style !== 'cancel') || buttons[buttons.length - 1];
      const confirmed = window.confirm(message ? `${title}\n\n${message}` : title);
      if (confirmed) {
        actionBtn?.onPress?.();
      } else {
        cancelBtn?.onPress?.();
      }
    }
  } else {
    RNAlert.alert(title, message, buttons);
  }
}
