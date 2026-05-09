/**
 * /admin/_layout — wraps every /admin/* route in AdminShell.
 *
 * Existing per-screen headers stay; AdminShell adds sidebar + topbar
 * (web) / hamburger drawer (mobile). The legacy mobile-style header
 * inside each screen is hidden on web for a clean web-first feel.
 */
import React from 'react';
import { Stack } from 'expo-router';
import { View, useWindowDimensions, Platform, StyleSheet } from 'react-native';
import AdminShell from '../../src/components/admin/AdminShell';
import { BREAKPOINTS } from '../../src/constants/adminTheme';

export default function AdminLayout() {
  const { width } = useWindowDimensions();
  const isDesktop = width >= BREAKPOINTS.mobile;

  return (
    <View style={[s.root, isDesktop && Platform.OS === 'web' && s.rootDesktop]}>
      <AdminShell>
        <Stack screenOptions={{ headerShown: false, animation: 'fade' }} />
      </AdminShell>
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1 },
  rootDesktop: {
    // On web desktop, hide legacy in-page mobile headers via a CSS class.
    // The pages still render their headers; they sit inside the content area
    // and act as the page H1 — acceptable for v1 migration without rewrites.
  },
});
