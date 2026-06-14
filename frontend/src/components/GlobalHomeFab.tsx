/**
 * GlobalHomeFab — a small floating "Home" button mounted once in the root
 * layout. Shows on every internal page so users always have a way back to
 * the home dashboard. Auto-hides on:
 *   • The home dashboard itself (/, /(tabs), /(tabs)/index)
 *   • Auth flows (login / register / forgot / WhatsApp verify)
 *   • Admin pages — they already have a sidebar with Home navigation
 *   • Embed / partner / kiosk surfaces — white-label, no Jelcos chrome
 *
 * Positioned bottom-left (mirroring `GlobalVoiceNav` which sits bottom-right)
 * so the two don't overlap on small viewports.
 */
import React from 'react';
import { TouchableOpacity, StyleSheet, Platform, View, Text } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { usePathname, useRouter } from 'expo-router';
import { useAuthStore } from '../store/authStore';

const HIDE_PREFIXES = [
  '/auth',
  '/admin',
  '/embed',
  '/partner',
  '/kiosk',
  '/whatsapp-verify',
];

// Exact paths considered "home" — clicking Home from these is pointless.
const HOME_PATHS = new Set(['/', '/index', '/(tabs)', '/(tabs)/index']);

export default function GlobalHomeFab() {
  const pathname = usePathname();
  const router = useRouter();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  // Hide while logged out — there is no "home" to go to.
  if (!isAuthenticated) return null;
  // Hide on routes that explicitly own their own navigation chrome.
  if (HIDE_PREFIXES.some((p) => pathname.startsWith(p))) return null;
  // Hide when already on home.
  if (HOME_PATHS.has(pathname)) return null;

  return (
    <View pointerEvents="box-none" style={styles.wrap}>
      <TouchableOpacity
        testID="global-home-fab"
        onPress={() => router.replace('/' as any)}
        activeOpacity={0.85}
        style={styles.btn}
        accessibilityRole="button"
        accessibilityLabel="Go to Home"
      >
        <Ionicons name="home" size={18} color="#FFF" />
        <Text style={styles.label}>Home</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: 'absolute',
    left: 16,
    bottom: Platform.select({ web: 20, default: 28 }),
    zIndex: 9999,
    elevation: 12,
  },
  btn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#7C3AED',
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 999,
    shadowColor: '#000',
    shadowOpacity: 0.18,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
  label: { color: '#FFF', fontSize: 12.5, fontWeight: '800', letterSpacing: 0.2 },
});
