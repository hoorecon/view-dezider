import React, { useEffect } from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useAuthStore } from '../src/store/authStore';
import { COLORS } from '../src/constants/colors';

export default function RootLayout() {
  const checkAuth = useAuthStore((state) => state.checkAuth);

  useEffect(() => {
    checkAuth();
  }, []);

  return (
    <>
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: COLORS.background },
        }}
      >
        <Stack.Screen name="index" />
        <Stack.Screen name="auth/login" />
        <Stack.Screen name="auth/register" />
        <Stack.Screen name="auth/callback" />
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen 
          name="prr/new" 
          options={{ 
            presentation: 'modal',
            headerShown: true,
            headerTitle: 'New PRR Decision',
            headerTintColor: COLORS.primary,
          }} 
        />
        <Stack.Screen 
          name="prr/[id]" 
          options={{ 
            headerShown: true,
            headerTitle: 'PRR Decision',
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
      </Stack>
    </>
  );
}
