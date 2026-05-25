import React, { useEffect } from 'react';
import { View, Platform } from 'react-native';
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
import { FontScaleProvider } from '../src/contexts/FontScaleContext';

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
            headerShown: true,
            headerTitle: 'Test123 Session',
            headerTintColor: COLORS.primary,
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
      </FontScaleProvider>
      <GlobalVoiceNav />
    </>
  );
}
