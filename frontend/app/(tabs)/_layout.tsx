import React from 'react';
import { Tabs, Redirect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import { Platform, View, ActivityIndicator } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAuthStore } from '../../src/store/authStore';

export default function TabLayout() {
  const insets = useSafeAreaInsets();
  const { user, isAuthenticated, isLoading } = useAuthStore();

  // Wait for the session check to resolve before deciding — prevents the
  // tab content from flashing for a logged-out visitor on a deep link.
  if (isLoading) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: COLORS.background }}>
        <ActivityIndicator color={COLORS.primary} />
      </View>
    );
  }

  // Not signed in → never render protected tabs.
  if (!isAuthenticated) {
    return <Redirect href="/auth/login" />;
  }

  // Mandatory WhatsApp verification gate: an authenticated user whose WhatsApp
  // number is not yet verified is routed to the verification screen before
  // they can use any in-app service.
  if (user && user.whatsapp_verified !== true) {
    return <Redirect href="/whatsapp-verify" />;
  }

  // Calculate proper bottom padding for the tab bar
  // On iOS/Android: use safe area insets to avoid overlapping with gesture bar
  // On web: use a minimal padding
  const bottomPadding = Platform.OS === 'web' ? 8 : Math.max(insets.bottom, 8);
  const tabBarHeight = Platform.OS === 'web' ? 64 : (56 + bottomPadding);

  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: COLORS.primary,
        tabBarInactiveTintColor: COLORS.textMuted,
        tabBarStyle: {
          backgroundColor: COLORS.white,
          borderTopColor: COLORS.border,
          borderTopWidth: 1,
          height: tabBarHeight,
          paddingBottom: bottomPadding,
          paddingTop: 6,
          // Ensure the tab bar is above the phone's gesture area
          ...(Platform.OS !== 'web' ? { position: 'absolute' as const, bottom: 0, left: 0, right: 0 } : {}),
        },
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: '600',
          marginTop: 2,
        },
        tabBarIconStyle: {
          marginBottom: -2,
        },
        headerShown: false,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="home" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="prr"
        options={{
          title: 'Solution Box',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="albums" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="shared"
        options={{
          title: 'Shared',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="share-social" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="journal"
        options={{
          title: 'Journal',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="book" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: 'Profile',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="person" size={size} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}
