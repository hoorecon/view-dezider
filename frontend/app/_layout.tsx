import React, { useEffect } from 'react';
import { View } from 'react-native';
import { Stack, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useAuthStore } from '../src/store/authStore';
import { useBrandingStore } from '../src/store/brandingStore';
import { COLORS } from '../src/constants/colors';
import { registerForPushNotifications, addNotificationResponseListener } from '../src/utils/pushNotifications';
import GlobalVoiceNav from '../src/components/GlobalVoiceNav';
import WebFrame from '../src/components/WebFrame';

export default function RootLayout() {
  const checkAuth = useAuthStore((state) => state.checkAuth);
  const hydrateBranding = useBrandingStore((s) => s.hydrate);
  const router = useRouter();

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
      <GlobalVoiceNav />
    </>
  );
}
