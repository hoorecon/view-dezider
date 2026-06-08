import React, { useEffect } from 'react';
import { View, Text, Platform } from 'react-native';
import { Stack, useRouter, useSegments } from 'expo-router';
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
import { FontFamilyProvider } from '../src/contexts/FontFamilyContext';

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
  // Web: load the "Inter" UI font (elegant, Google/Amazon-like) from
  // Google Fonts. Marketing/public pages opt in via a root fontFamily
  // that cascades to their text. Weights 400–900 are loaded so headings
  // render at the correct boldness.
  // -------------------------------------------------------------------
  const INTER_FONT_ID = '__inter_font_link__';
  if (!document.getElementById(INTER_FONT_ID)) {
    const pre1 = document.createElement('link');
    pre1.rel = 'preconnect';
    pre1.href = 'https://fonts.googleapis.com';
    document.head.appendChild(pre1);

    const pre2 = document.createElement('link');
    pre2.rel = 'preconnect';
    pre2.href = 'https://fonts.gstatic.com';
    pre2.crossOrigin = 'anonymous';
    document.head.appendChild(pre2);

    const link = document.createElement('link');
    link.id = INTER_FONT_ID;
    link.rel = 'stylesheet';
    link.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap';
    document.head.appendChild(link);

    // Scope Inter to the public marketing/legal pages. Their root View sets
    // nativeID="jelcosMarketing" (→ DOM id). font-family inherits to all child
    // text; Ionicons glyphs keep their own font-family so icons are unaffected.
    const scope = document.createElement('style');
    scope.textContent = `
      #jelcosMarketing div, #jelcosMarketing span, #jelcosMarketing p {
        font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
      }
    `;
    document.head.appendChild(scope);
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

// ----------------------------------------------------------------------
// Public route whitelist for the global auth guard. The FIRST URL segment
// of these areas may be viewed without a session. Everything else requires
// an authenticated user (and a verified WhatsApp number). `admin` is listed
// because app/admin/_layout.tsx runs its own stricter auth+role guard.
// ----------------------------------------------------------------------
const PUBLIC_SEGMENTS = new Set<string>([
  'auth',            // login / register / forgot-password
  'whatsapp-verify', // post-login WhatsApp gate
  'legal',           // privacy / terms / refund / delivery
  'contact',
  'pricing',
  'p',               // public shared-report viewer (/p/[slug])
  'embed',           // white-label partner embed (/embed/[flow]) — iframed on partner sites
  'admin',           // self-guarded (auth + admin role)
]);

export default function RootLayout() {
  const checkAuth = useAuthStore((state) => state.checkAuth);
  const isLoading = useAuthStore((state) => state.isLoading);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const user = useAuthStore((state) => state.user);
  const hydrateBranding = useBrandingStore((s) => s.hydrate);
  const router = useRouter();
  const segments = useSegments();

  // Set the browser tab title on web (dev + SPA export). Keeps the brand
  // consistent instead of the default Expo project name.
  useEffect(() => {
    if (Platform.OS === 'web' && typeof document !== 'undefined') {
      document.title = "JELCOS AI - Joyful Executive's Life Choices Operating System — Powered by AI";
    }
  }, []);

  // --------------------------------------------------------------------
  // GLOBAL AUTH GUARD. Runs on every navigation. Unauthenticated users are
  // bounced to /auth/login from any protected route; authenticated-but-
  // unverified users are forced through /whatsapp-verify. This is the single
  // source of truth so no protected screen (tabs, tools, prr, …) can ever
  // render its content to a logged-out visitor.
  // --------------------------------------------------------------------
  useEffect(() => {
    if (isLoading) return; // wait until checkAuth() resolves
    const first = segments[0] as string | undefined;
    const isPublic = first === undefined || first === 'index' || PUBLIC_SEGMENTS.has(first);

    if (!isAuthenticated) {
      if (!isPublic) router.replace('/auth/login');
      return;
    }
    // Authenticated but WhatsApp not yet verified → force the one-time gate.
    if (user && user.whatsapp_verified !== true && !isPublic) {
      router.replace('/whatsapp-verify');
    }
  }, [segments, isLoading, isAuthenticated, user, router]);

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
    <NavErrorBoundary>
      <StatusBar style="dark" />
      <FontFamilyProvider>
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
      </FontFamilyProvider>
    </NavErrorBoundary>
  );
}
