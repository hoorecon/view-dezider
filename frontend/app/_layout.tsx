import React, { useEffect } from 'react';
import { View, Text, Platform } from 'react-native';
import { Stack, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useFonts } from 'expo-font';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../src/store/authStore';
import { useBrandingStore } from '../src/store/brandingStore';
import { COLORS } from '../src/constants/colors';
import { registerForPushNotifications, addNotificationResponseListener } from '../src/utils/pushNotifications';
import GlobalVoiceNav from '../src/components/GlobalVoiceNav';
import WebFrame from '../src/components/WebFrame';
import WebScrollFix from '../src/components/WebScrollFix';
import AlertHost from '../src/components/AlertHost';
import GlobalFontScale from '../src/components/GlobalFontScale';
import { FontScaleProvider } from '../src/contexts/FontScaleContext';

// ----------------------------------------------------------------------
// NavErrorBoundary — last line of defence against the React-Navigation
// "Cannot read properties of undefined (reading 'stale')" white-screen.
// React render errors don't reliably reach window.onerror in production
// bundles, so a real error boundary is the only guaranteed catch. On the
// first crash it wipes persisted state and reloads ONCE (sessionStorage
// guard prevents reload loops); if it somehow crashes again it shows a
// friendly recovery message instead of a blank page.
// ----------------------------------------------------------------------
class NavErrorBoundary extends React.Component<{ children: React.ReactNode }, { crashed: boolean }> {
  constructor(props: any) {
    super(props);
    this.state = { crashed: false };
  }
  static getDerivedStateFromError() {
    return { crashed: true };
  }
  componentDidCatch() {
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      try {
        const FLAG = '__jelcos_eb_recovered__';
        if (!sessionStorage.getItem(FLAG)) {
          sessionStorage.setItem(FLAG, '1');
          try { localStorage.clear(); } catch { /* ignore */ }
          window.location.reload();
        }
      } catch { /* ignore */ }
    }
  }
  render() {
    if (this.state.crashed) {
      return (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, backgroundColor: '#FFFFFF' }}>
          <Text style={{ fontSize: 17, fontWeight: '700', color: '#0F172A', marginBottom: 8 }}>Updating to the latest version…</Text>
          <Text style={{ fontSize: 13, color: '#64748B', textAlign: 'center', lineHeight: 19 }}>
            If this message stays for more than a few seconds, please refresh the page (Ctrl/Cmd + Shift + R).
          </Text>
        </View>
      );
    }
    return this.props.children as any;
  }
}

// ----------------------------------------------------------------------
// Web-only: inject @font-face for Ionicons so static Cloudflare/Pages
// builds render glyphs instead of empty boxes.
//
// We bundle the Ionicons.ttf file directly in /public/fonts/ so it has
// a stable URL (/fonts/Ionicons.ttf) at runtime regardless of how Metro
// hashes assets. This is the most reliable approach for static exports.
// ----------------------------------------------------------------------
if (Platform.OS === 'web' && typeof document !== 'undefined') {
  const IONICONS_FONT_ID = '__ionicons_font_face__';
  if (!document.getElementById(IONICONS_FONT_ID)) {
    const style = document.createElement('style');
    style.id = IONICONS_FONT_ID;
    style.textContent = `
      @font-face {
        font-family: 'Ionicons';
        src: url('/fonts/Ionicons.ttf') format('truetype');
        font-weight: normal;
        font-style: normal;
        font-display: swap;
      }
    `;
    document.head.appendChild(style);
  }

  // -------------------------------------------------------------------
  // Build-version cache buster.
  //
  // Big deploys (e.g. output:static → output:single, Stack route tree
  // changes, Zustand store shape changes) can leave the browser with
  // localStorage that's incompatible with the new bundle. The most
  // visible symptom is React Navigation's useNavigationBuilder crashing
  // with  "Cannot read properties of undefined (reading 'stale')"
  // because the persisted state is from an older route hierarchy.
  //
  // We stamp the build version. If the stored stamp doesn't match the
  // current one, we wipe just the keys most likely to be poisoned —
  // React Navigation cache, Zustand persists, AsyncStorage emulation —
  // and reload once. This is idempotent: second boot sees matching
  // stamp and is a no-op.
  // -------------------------------------------------------------------
  const BUILD_VERSION = '2026-06-02-asm-phase12-v5';
  const STAMP_KEY = '__jelcos_build_version__';
  try {
    const storedStamp = localStorage.getItem(STAMP_KEY);
    if (storedStamp && storedStamp !== BUILD_VERSION) {
      // Build changed under this browser. Any persisted React-Navigation /
      // Zustand / AsyncStorage state may reference the OLD route tree and will
      // crash useNavigationBuilder with "reading 'stale'". Clearing prefix-
      // matched keys is fragile (the poisoned key may use another name), so on
      // a version change we wipe ALL of localStorage, then re-stamp and reload
      // once. One-time cost: the user re-authenticates. This GUARANTEES no
      // stale navigation state can survive the upgrade.
      try { localStorage.clear(); } catch { /* ignore */ }
      try { sessionStorage.clear(); } catch { /* ignore */ }
      try { localStorage.setItem(STAMP_KEY, BUILD_VERSION); } catch { /* ignore */ }
      // Reload once so React Navigation rebuilds state from scratch.
      if (typeof window !== 'undefined') {
        window.location.reload();
      }
    } else if (!storedStamp) {
      // First-time visitor — just record the stamp
      localStorage.setItem(STAMP_KEY, BUILD_VERSION);
    }
  } catch {
    /* localStorage unavailable (e.g. private mode + Safari restrictions) — skip */
  }

  // -------------------------------------------------------------------
  // Runtime self-heal for the React-Navigation "reading 'stale'" crash.
  //
  // If a future deploy ever ships with mismatched persisted nav state and
  // useNavigationBuilder throws while rehydrating, the whole app white-
  // screens. This global handler detects that specific error, wipes
  // storage and reloads exactly once (guarded by a sessionStorage flag so
  // it can never loop). It's a belt-and-suspenders backup to the
  // BUILD_VERSION wipe above.
  // -------------------------------------------------------------------
  const NAV_RECOVER_FLAG = '__jelcos_nav_recovered__';
  window.addEventListener('error', (ev: any) => {
    const msg = (ev && (ev.message || (ev.error && ev.error.message))) || '';
    if (/reading 'stale'|getRehydratedState/.test(String(msg))) {
      try {
        if (sessionStorage.getItem(NAV_RECOVER_FLAG)) return; // already tried — don't loop
        sessionStorage.setItem(NAV_RECOVER_FLAG, '1');
      } catch { /* ignore */ }
      try { localStorage.clear(); } catch { /* ignore */ }
      try { window.location.reload(); } catch { /* ignore */ }
    }
  });

  // -------------------------------------------------------------------
  // Visible browser scrollbar styling (cosmetic only — does NOT change
  // page layout). The actual scroll behaviour is handled by the inner
  // RN ScrollView with showsVerticalScrollIndicator={true}.
  //
  // (Earlier attempt at also forcing body { overflow:auto; display:block;
  // height:auto } collapsed the #root container to 0 height and made
  // every page render blank. Do NOT add layout-affecting rules here.)
  // -------------------------------------------------------------------
  const SCROLLBAR_STYLE_ID = '__page_scroll_fix__';
  if (!document.getElementById(SCROLLBAR_STYLE_ID)) {
    const sheet = document.createElement('style');
    sheet.id = SCROLLBAR_STYLE_ID;
    sheet.textContent = `
      /* Chromium / Safari */
      ::-webkit-scrollbar { width: 10px; height: 10px; }
      ::-webkit-scrollbar-track { background: transparent; }
      ::-webkit-scrollbar-thumb {
        background: rgba(120, 120, 120, 0.45);
        border-radius: 8px;
      }
      ::-webkit-scrollbar-thumb:hover { background: rgba(120, 120, 120, 0.7); }
      /* Firefox */
      html { scrollbar-width: thin; scrollbar-color: rgba(120,120,120,0.45) transparent; }
    `;
    document.head.appendChild(sheet);
  }
}

export default function RootLayout() {
  const checkAuth = useAuthStore((state) => state.checkAuth);
  const hydrateBranding = useBrandingStore((s) => s.hydrate);
  const router = useRouter();

  // Native + secondary web path for icon font
  const [fontsLoaded] = useFonts({
    ...Ionicons.font,
  });

  useEffect(() => {
    checkAuth();
    hydrateBranding();

    // Register push notifications
    registerForPushNotifications().catch(() => {});

    // Handle notification tap → navigate to inbox
    const sub = addNotificationResponseListener((response) => {
      const data = response.notification.request.content.data;
      if (data?.decision_id) {
        router.push('/inbox');
      }
    });

    return () => sub.remove();
  }, []);

  return (
    <>
      <StatusBar style="dark" />
      <FontScaleProvider>
        <WebFrame>
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: COLORS.background },
          }}
        >
        <Stack.Screen name="index" />
        <Stack.Screen name="auth/login" />
        <Stack.Screen name="auth/register" />
        <Stack.Screen name="auth/forgot-password" />
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen 
          name="prr/new" 
          options={{ 
            presentation: 'modal',
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="tools/new-decision" 
          options={{ 
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="prr/[id]" 
          options={{ 
            headerShown: true,
            headerTitle: 'My Dezider',
            headerTintColor: COLORS.primary,
          }} 
        />
        <Stack.Screen 
          name="test123/new" 
          options={{ 
            presentation: 'modal',
            headerShown: true,
            headerTitle: 'Test123 - Quick Decision',
            headerTintColor: COLORS.primary,
          }} 
        />
        <Stack.Screen 
          name="test123/[id]" 
          options={{ 
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="inbox" 
          options={{ 
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="notifications" 
          options={{ 
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="analytics" 
          options={{ 
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="tools/ctt" 
          options={{ 
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="tools/ctt-task" 
          options={{ 
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="tools/gem" 
          options={{ 
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="tools/gem-goal" 
          options={{ 
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="tools/solution-finder" 
          options={{ 
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="tools/solution-finder-list" 
          options={{ 
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="tools/solution-matrix" 
          options={{ 
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="tools/solution-matrix-list" 
          options={{ 
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="tools/tepfi" 
          options={{ 
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="tools/tepfi-entry" 
          options={{ 
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="tools/calendar-view" 
          options={{ 
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="tools/lifestyle" 
          options={{ 
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="tools/lifestyle-routine" 
          options={{ 
            headerShown: false,
          }} 
        />
        <Stack.Screen 
          name="tools/lifestyle-analytics" 
          options={{ 
            headerShown: false,
          }} 
        />
      </Stack>
      </WebFrame>
      {/* Overlay layer — inside FontScaleProvider so text honours font scaling, */}
      {/* but OUTSIDE WebFrame so it can position itself anywhere on the viewport */}
      <AlertHost />
      <GlobalFontScale />
      <WebScrollFix />
      </FontScaleProvider>
      <GlobalVoiceNav />
    </>
  );
}
