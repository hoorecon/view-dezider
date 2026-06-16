import React from 'react';
import {
  Modal,
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Pressable,
  StyleProp,
  ViewStyle,
  TextStyle,
} from 'react-native';

/**
 * ConfirmDialog
 * ─────────────
 * Themed, in-app confirm dialog. Replaces `window.confirm` / `Alert.alert` on
 * web so we do not show the harsh native browser sheet ("jelcos.ai says...")
 * inside otherwise immersive screens (e.g. the Emotional Reception 5-min
 * meditation timer).
 *
 * Designed to be a drop-in for the most common cancel/confirm pattern:
 *   <ConfirmDialog
 *     visible={showConfirm}
 *     title="Leave Practice?"
 *     message="It's OK if you can't complete it this time. Would you like to stop?"
 *     confirmLabel="Stop"
 *     cancelLabel="Continue Practice"
 *     destructive
 *     onCancel={() => setShowConfirm(false)}
 *     onConfirm={() => { setShowConfirm(false); doStop(); }}
 *   />
 */
export interface ConfirmDialogProps {
  visible: boolean;
  title: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Renders confirm button in red. Use for irreversible / interrupt actions. */
  destructive?: boolean;
  /** Optional dark theme override (matches immersive backdrops). */
  theme?: 'light' | 'dark';
  onConfirm: () => void;
  onCancel: () => void;
  /** Optional style override for the modal card. */
  cardStyle?: StyleProp<ViewStyle>;
  /** Optional override for the title text style. */
  titleStyle?: StyleProp<TextStyle>;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  visible,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  destructive = false,
  theme = 'light',
  onConfirm,
  onCancel,
  cardStyle,
  titleStyle,
}) => {
  const isDark = theme === 'dark';
  const styles = isDark ? darkStyles : lightStyles;
  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onCancel}
    >
      <Pressable style={styles.overlay} onPress={onCancel}>
        <Pressable style={[styles.card, cardStyle]} onPress={(e) => e.stopPropagation()}>
          <Text style={[styles.title, titleStyle]}>{title}</Text>
          {!!message && <Text style={styles.message}>{message}</Text>}
          <View style={styles.row}>
            <TouchableOpacity
              style={[styles.btn, styles.cancelBtn]}
              onPress={onCancel}
              accessibilityRole="button"
              accessibilityLabel={cancelLabel}
            >
              <Text style={styles.cancelText}>{cancelLabel}</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[
                styles.btn,
                destructive ? styles.destructiveBtn : styles.confirmBtn,
              ]}
              onPress={onConfirm}
              accessibilityRole="button"
              accessibilityLabel={confirmLabel}
            >
              <Text style={destructive ? styles.destructiveText : styles.confirmText}>
                {confirmLabel}
              </Text>
            </TouchableOpacity>
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
};

const baseStyles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.55)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  card: {
    width: '100%',
    maxWidth: 420,
    borderRadius: 16,
    padding: 24,
    gap: 8,
  },
  title: {
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 4,
  },
  message: {
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 16,
  },
  row: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 4,
  },
  btn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cancelBtn: {
    backgroundColor: 'transparent',
    borderWidth: 1,
  },
  confirmBtn: {
    backgroundColor: '#0EA5E9',
  },
  destructiveBtn: {
    backgroundColor: '#EF4444',
  },
  cancelText: {
    fontSize: 14,
    fontWeight: '600',
  },
  confirmText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#FFF',
  },
  destructiveText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#FFF',
  },
});

const lightStyles = StyleSheet.create({
  ...baseStyles,
  card: { ...baseStyles.card, backgroundColor: '#FFFFFF' },
  title: { ...baseStyles.title, color: '#0F172A' },
  message: { ...baseStyles.message, color: '#475569' },
  cancelBtn: { ...baseStyles.cancelBtn, borderColor: '#CBD5E1' },
  cancelText: { ...baseStyles.cancelText, color: '#334155' },
});

const darkStyles = StyleSheet.create({
  ...baseStyles,
  card: { ...baseStyles.card, backgroundColor: '#0F2A36' },
  title: { ...baseStyles.title, color: '#F1F5F9' },
  message: { ...baseStyles.message, color: 'rgba(255,255,255,0.78)' },
  cancelBtn: { ...baseStyles.cancelBtn, borderColor: 'rgba(255,255,255,0.32)' },
  cancelText: { ...baseStyles.cancelText, color: '#E2E8F0' },
});

export default ConfirmDialog;
