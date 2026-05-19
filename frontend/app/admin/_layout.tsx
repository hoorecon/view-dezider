/**
 * /admin/_layout — wraps every /admin/* route in AdminShell + AUTH GUARD.
 *
 * Auth flow:
 *  - /admin/login is the only public route here; rendered without AdminShell
 *  - All other /admin/* routes require:
 *      (a) authenticated session
 *      (b) role: admin / super_admin / co_admin
 *  - On fail → redirect to /admin/login (preserves the deep-link via params)
 */
import React, { useEffect } from 'react';
import { Stack, usePathname, useRouter } from 'expo-router';
import {
  View, useWindowDimensions, Platform, StyleSheet,
  ActivityIndicator, Text,
} from 'react-native';
import AdminShell from '../../src/components/admin/AdminShell';
import { BREAKPOINTS } from '../../src/constants/adminTheme';
import { useAuthStore } from '../../src/store/authStore';
import { COLORS } from '../../src/constants/colors';

const ADMIN_ROLES = ['admin', 'super_admin', 'co_admin'];

function isAdminUser(user: any): boolean {
  if (!user) return false;
  if (user.is_admin === true) return true;
  const role = (user.role || '').toLowerCase();
  return ADMIN_ROLES.includes(role);
}

export default function AdminLayout() {
  const { width } = useWindowDimensions();
  const isDesktop = width >= BREAKPOINTS.mobile;
  const pathname = usePathname();
  const router = useRouter();

  const { isLoading, isAuthenticated, user } = useAuthStore();

  const isStandalone = pathname === '/admin/login';
  const isAdmin = isAdminUser(user);

  // Auth guard — redirect to /admin/login if missing auth or not admin
  useEffect(() => {
    if (isStandalone) return;          // login page itself never redirects
    if (isLoading) return;             // wait for auth check to complete
    if (!isAuthenticated) {
      router.replace('/admin/login' as any);
      return;
    }
    if (!isAdmin) {
      router.replace('/admin/login' as any);
    }
  }, [isStandalone, isLoading, isAuthenticated, isAdmin]);

  // Login page renders standalone (no shell)
  if (isStandalone) {
    return (
      <View style={s.root}>
        <Stack screenOptions={{ headerShown: false, animation: 'fade' }} />
      </View>
    );
  }

  // While auth check is in-flight, OR while we're about to redirect, show
  // a centred spinner instead of leaking admin UI to unauth'd visitors.
  if (isLoading || !isAuthenticated || !isAdmin) {
    return (
      <View style={[s.root, s.gate]}>
        <ActivityIndicator size="large" color={COLORS.primary} />
        <Text style={s.gateText}>
          {isLoading ? 'Loading…' : 'Redirecting to admin sign-in…'}
        </Text>
      </View>
    );
  }

  return (
    <View style={[s.root, isDesktop && Platform.OS === 'web' && s.rootDesktop]}>
      <AdminShell>
        <Stack screenOptions={{ headerShown: false, animation: 'fade' }} />
      </AdminShell>
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.background },
  rootDesktop: {},
  gate: {
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    minHeight: 400,
  },
  gateText: {
    color: COLORS.textMuted,
    fontSize: 13,
    marginTop: 8,
  },
});
