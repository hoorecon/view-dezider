/**
 * AlertHost — in-app modal that replaces the browser's window.alert /
 * window.confirm popups on web. Subscribes to events emitted by the
 * `showAlert()` utility (src/utils/alert.ts) so callers can keep using
 * the exact same API but get a polished React-Native modal instead of
 * the junky Chrome / Safari native dialog.
 *
 * Mount once at the root of the tree (e.g. in app/_layout.tsx, inside
 * FontScaleProvider so font scaling also applies to the modal copy).
 */
import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  Modal,
  StyleSheet,
  TouchableOpacity,
  TouchableWithoutFeedback,
  Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';
import { _subscribeAlert, AlertButton } from '../utils/alert';

interface QueuedAlert {
  id: number;
  title: string;
  message?: string;
  buttons?: AlertButton[];
}

let _idSeq = 1;

export default function AlertHost() {
  const [queue, setQueue] = useState<QueuedAlert[]>([]);

  useEffect(() => {
    const unsub = _subscribeAlert((req) => {
      setQueue((q) => [...q, { id: _idSeq++, ...req }]);
    });
    return unsub;
  }, []);

  const current = queue[0];

  // ESC key dismisses on web (matches native Alert.alert behaviour)
  useEffect(() => {
    if (Platform.OS !== 'web' || !current) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        const cancel = current.buttons?.find((b) => b.style === 'cancel');
        cancel?.onPress?.();
        setQueue((q) => q.slice(1));
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [current]);

  if (!current) return null;

  const dismissAndRun = (btn?: AlertButton) => {
    setQueue((q) => q.slice(1));
    try { btn?.onPress?.(); } catch (e) { console.warn('alert button onPress threw', e); }
  };

  const buttons: AlertButton[] = current.buttons && current.buttons.length > 0
    ? current.buttons
    : [{ text: 'OK', style: 'default' }];

  // Tone & icon based on whether destructive button present
  const hasDestructive = buttons.some((b) => b.style === 'destructive');
  const isConfirm = buttons.length > 1;
  const accent = hasDestructive ? COLORS.danger : COLORS.primary;
  const iconName = hasDestructive
    ? 'warning'
    : isConfirm
      ? 'help-circle'
      : 'information-circle';

  return Platform.OS === 'web' ? (
    // ── Web branch — react-native-web 0.21's <Modal> portal is unreliable, so
    //    we render a plain fixed-position overlay using web-style `position`.
    <View
      // @ts-ignore — `position: 'fixed'` is web-only and not in RN types.
      style={[styles.backdrop, { position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 999999 }]}
      // @ts-ignore web-only DOM event
      onClick={() => {
        const cancel = buttons.find((b) => b.style === 'cancel');
        if (cancel) dismissAndRun(cancel);
      }}
    >
      <TouchableWithoutFeedback onPress={(e: any) => e.stopPropagation?.()}>
        <View style={styles.card} accessibilityRole="alert" accessibilityLiveRegion="assertive">
          <View style={[styles.iconCircle, { backgroundColor: accent + '15' }]}>
            <Ionicons name={iconName as any} size={26} color={accent} />
          </View>
          <Text style={styles.title}>{current.title}</Text>
          {!!current.message && <Text style={styles.message}>{current.message}</Text>}
          <View style={[styles.row, buttons.length === 1 && styles.rowSingle]}>
            {buttons.map((b, i) => {
              const isDanger = b.style === 'destructive';
              const isCancel = b.style === 'cancel';
              const isPrimary = !isCancel && !isDanger;
              return (
                <TouchableOpacity
                  key={`${b.text}-${i}`}
                  onPress={() => dismissAndRun(b)}
                  style={[
                    styles.btn,
                    isPrimary && { backgroundColor: COLORS.primary },
                    isDanger && { backgroundColor: COLORS.error },
                    isCancel && styles.btnCancel,
                  ]}
                  accessibilityRole="button"
                  accessibilityLabel={b.text}
                >
                  <Text
                    style={[
                      styles.btnText,
                      isPrimary && styles.btnTextPrimary,
                      isDanger && styles.btnTextPrimary,
                      isCancel && styles.btnTextCancel,
                    ]}
                  >
                    {b.text}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>
      </TouchableWithoutFeedback>
    </View>
  ) : (
    <Modal
      transparent
      visible
      animationType="fade"
      onRequestClose={() => {
        // Android hardware back
        const cancel = buttons.find((b) => b.style === 'cancel') || buttons[0];
        dismissAndRun(cancel);
      }}
    >
      <TouchableWithoutFeedback
        onPress={() => {
          // Tap on backdrop → treat as cancel (only if a cancel exists)
          const cancel = buttons.find((b) => b.style === 'cancel');
          if (cancel) dismissAndRun(cancel);
        }}
      >
        <View style={styles.backdrop}>
          <TouchableWithoutFeedback>
            <View style={styles.card}>
              <View style={[styles.iconCircle, { backgroundColor: accent + '15' }]}>
                <Ionicons name={iconName as any} size={26} color={accent} />
              </View>
              <Text style={styles.title}>{current.title}</Text>
              {!!current.message && (
                <Text style={styles.message}>{current.message}</Text>
              )}

              <View style={[styles.row, buttons.length === 1 && styles.rowSingle]}>
                {buttons.map((b, i) => {
                  const isDanger = b.style === 'destructive';
                  const isCancel = b.style === 'cancel';
                  const isPrimary = !isCancel && !isDanger;
                  return (
                    <TouchableOpacity
                      key={`${b.text}-${i}`}
                      onPress={() => dismissAndRun(b)}
                      style={[
                        styles.btn,
                        isPrimary && { backgroundColor: COLORS.primary },
                        isDanger && { backgroundColor: COLORS.error },
                        isCancel && styles.btnCancel,
                      ]}
                      accessibilityRole="button"
                      accessibilityLabel={b.text}
                    >
                      <Text
                        style={[
                          styles.btnText,
                          isPrimary && styles.btnTextPrimary,
                          isDanger && styles.btnTextPrimary,
                          isCancel && styles.btnTextCancel,
                        ]}
                      >
                        {b.text}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            </View>
          </TouchableWithoutFeedback>
        </View>
      </TouchableWithoutFeedback>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(15, 23, 42, 0.55)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  card: {
    width: '100%',
    maxWidth: 420,
    backgroundColor: '#FFF',
    borderRadius: 20,
    padding: 24,
    alignItems: 'center',
    ...(Platform.OS === 'web'
      ? ({ boxShadow: '0 20px 50px rgba(15, 23, 42, 0.25)' } as any)
      : {
          shadowColor: '#000',
          shadowOpacity: 0.2,
          shadowOffset: { width: 0, height: 8 },
          shadowRadius: 24,
          elevation: 8,
        }),
  },
  iconCircle: {
    width: 56, height: 56, borderRadius: 28,
    alignItems: 'center', justifyContent: 'center',
    marginBottom: 16,
  },
  title: {
    fontSize: 18,
    fontWeight: '700',
    color: COLORS.textPrimary,
    textAlign: 'center',
    marginBottom: 8,
  },
  message: {
    fontSize: 14,
    color: COLORS.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 4,
  },
  row: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 20,
    width: '100%',
  },
  rowSingle: {
    justifyContent: 'center',
  },
  btn: {
    flex: 1,
    minHeight: 44,
    paddingHorizontal: 18,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnCancel: {
    backgroundColor: '#F1F5F9',
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  btnText: {
    fontSize: 15,
    fontWeight: '600',
  },
  btnTextPrimary: { color: '#FFF' },
  btnTextCancel: { color: COLORS.textPrimary },
});
