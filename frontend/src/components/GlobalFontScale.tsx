/**
 * GlobalFontScale — floating A/A+/A++ pill, web-only, fixed to the
 * bottom-right corner of the viewport. Rendered once at the root so
 * users can adjust font size from ANY screen (inner tools, wizards,
 * admin, public pages) without each screen having to wire its own
 * FontScaleButton.
 *
 * • Hidden on native — iOS/Android already expose system font scaling.
 * • Skipped on auth screens — keeps the login hero card uncluttered.
 * • Uses position:'fixed' (web) so it never participates in layout
 *   and never causes hydration mismatches.
 */
import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Platform,
} from 'react-native';
import { usePathname } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { FontScaleButton } from './FontScaleButton';

const HIDDEN_PREFIXES = ['/auth', '/admin']; // admin has its own toggle in shell

export default function GlobalFontScale() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  if (Platform.OS !== 'web') return null;
  const p = pathname || '/';
  if (HIDDEN_PREFIXES.some((pre) => p.startsWith(pre))) return null;
  if (p === '/' || p === '/index') return null; // landing/login hero

  return (
    <View
      pointerEvents="box-none"
      // position:'fixed' is a web-only CSS value; works on react-native-web
      style={[styles.wrap, { position: 'fixed' as any }]}
    >
      {open ? (
        <View style={styles.openCard}>
          <FontScaleButton variant="light" />
          <TouchableOpacity
            onPress={() => setOpen(false)}
            style={styles.closeBtn}
            hitSlop={8}
            accessibilityLabel="Hide font size controls"
          >
            <Ionicons name="close" size={14} color="#475569" />
          </TouchableOpacity>
        </View>
      ) : (
        <TouchableOpacity
          onPress={() => setOpen(true)}
          style={styles.fab}
          accessibilityLabel="Open font size controls"
          activeOpacity={0.85}
        >
          <Text style={styles.fabBigA}>A</Text>
          <Text style={styles.fabSmallA}>A</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    right: 16,
    bottom: 16,
    zIndex: 9000,
    // Keep within safe-area on iOS web (notched layouts)
    paddingBottom: 0,
  },
  fab: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#FFFFFF',
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'center',
    paddingHorizontal: 6,
    ...(Platform.OS === 'web'
      ? ({ boxShadow: '0 6px 16px rgba(15, 23, 42, 0.18)' } as any)
      : {}),
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  fabBigA: {
    fontSize: 18,
    fontWeight: '800',
    color: '#1F2937',
    lineHeight: 22,
  },
  fabSmallA: {
    fontSize: 12,
    fontWeight: '700',
    color: '#1F2937',
    marginLeft: 1,
    lineHeight: 16,
  },
  openCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#FFFFFF',
    borderRadius: 18,
    paddingHorizontal: 6,
    paddingVertical: 4,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    ...(Platform.OS === 'web'
      ? ({ boxShadow: '0 6px 16px rgba(15, 23, 42, 0.18)' } as any)
      : {}),
  },
  closeBtn: {
    width: 22,
    height: 22,
    borderRadius: 11,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#F1F5F9',
  },
});
