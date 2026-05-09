/**
 * WebFrame — global responsive centering wrapper.
 *
 * Behaviour:
 *   • Native (iOS / Android): pass-through, zero overhead.
 *   • Web mobile (<768px):    pass-through (full-width card already correct).
 *   • Web desktop (>=768px):
 *       - Auth pages           → centred narrow card (~ 480px) with subtle bg.
 *       - Pricing / public     → centred medium card (~ 720px).
 *       - Tabs / tools / user  → centred wide card  (~ 960px).
 *       - /admin/*             → SKIPPED (AdminShell handles its own layout).
 *
 * Single source of truth for "this is a web app, not a stretched mobile app".
 */
import React from 'react';
import { View, StyleSheet, Platform, useWindowDimensions } from 'react-native';
import { usePathname } from 'expo-router';

const BREAKPOINT_DESKTOP = 768;

type Variant = 'admin' | 'auth' | 'public' | 'app';

const MAX_WIDTH: Record<Variant, number> = {
  admin:  9999,   // admin shell handles itself
  auth:    460,   // narrow card for login/register
  public:  720,   // pricing / org portal
  app:     960,   // user app: home, tools, profile, etc.
};

function classifyRoute(pathname: string | null | undefined): Variant {
  const p = pathname || '/';
  if (p.startsWith('/admin')) return 'admin';
  if (p.startsWith('/auth') || p === '/' || p.startsWith('/index')) return 'auth';
  if (p.startsWith('/pricing') || p.startsWith('/p/')) return 'public';
  return 'app';
}

interface Props {
  children: React.ReactNode;
}

export default function WebFrame({ children }: Props) {
  const { width } = useWindowDimensions();
  const pathname = usePathname();

  // Native or admin → pass-through (no extra wrapper).
  if (Platform.OS !== 'web') return <>{children}</>;
  const variant = classifyRoute(pathname);
  if (variant === 'admin') return <>{children}</>;

  // Web mobile width → pass-through (full-bleed mobile card already looks fine).
  if (width < BREAKPOINT_DESKTOP) return <>{children}</>;

  const maxWidth = MAX_WIDTH[variant];

  return (
    <View style={s.outer}>
      <View style={[s.inner, { maxWidth, width: '100%' }]}>{children}</View>
    </View>
  );
}

const s = StyleSheet.create({
  outer: {
    flex: 1,
    backgroundColor: '#F1F5F9',
    alignItems: 'center',
    justifyContent: 'flex-start',
  },
  inner: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    minHeight: '100%',
    // Subtle elevation only on web desktop
    ...(Platform.OS === 'web'
      ? ({ boxShadow: '0 0 0 1px #E2E8F0, 0 8px 24px rgba(15,23,42,0.04)' } as any)
      : {}),
  },
});
