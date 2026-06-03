import React, { useEffect, useRef } from 'react';
import { View, Text, ActivityIndicator, StyleSheet } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAuthStore } from '../../src/store/authStore';
import api from '../../src/utils/api';
import { COLORS } from '../../src/constants/colors';

/**
 * Deep-link target for shared report links: {PUBLIC_APP_URL}/shared/{token}.
 * - If the visitor is logged in -> accept the share and open "Shared with me".
 * - If not -> remember the token and send them to login/signup (lead-magnet
 *   onboarding); after auth, "Shared with me" auto-accepts the pending token.
 */
export default function SharedDeepLink() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const router = useRouter();
  const isAuthenticated = useAuthStore((st) => st.isAuthenticated);
  const done = useRef(false);

  useEffect(() => {
    if (done.current || !token) return;
    done.current = true;
    (async () => {
      const stored = await AsyncStorage.getItem('session_token');
      if (isAuthenticated || stored) {
        try { await api.post(`/shares/${token}/accept`); } catch { /* ignore */ }
        router.replace('/(tabs)/shared');
      } else {
        await AsyncStorage.setItem('pending_share_token', String(token));
        router.replace('/auth/login');
      }
    })();
  }, [token, isAuthenticated, router]);

  return (
    <View style={s.c}>
      <ActivityIndicator size="large" color={COLORS.primary} />
      <Text style={s.t}>Opening shared report…</Text>
    </View>
  );
}

const s = StyleSheet.create({
  c: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, backgroundColor: '#fff' },
  t: { color: '#6B7280', fontSize: 14 },
});
