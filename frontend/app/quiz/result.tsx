/**
 * Guest-quiz result claim + reveal.
 *
 * URL: /quiz/result?token=<quiz_token>
 *
 * A logged-in user lands here after taking the marketing-hook quiz on /quiz
 * (or quiz.jelcos.ai). We POST /api/quiz/claim to redeem the guest token
 * against a real assessment row, then redirect to /(tabs)/profile where the
 * full result view (mode breakdown, AI insight, PDF, WhatsApp / Email share)
 * is already implemented.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { useAuthStore } from '../../src/store/authStore';

export default function QuizResultScreen() {
  const router = useRouter();
  const { token } = useLocalSearchParams<{ token?: string }>();
  const { isAuthenticated } = useAuthStore();
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) {
      // Stash the token for post-auth redirect and bounce to login.
      (async () => {
        if (token) {
          try {
            const AsyncStorage = (await import('@react-native-async-storage/async-storage')).default;
            await AsyncStorage.setItem('pending_quiz_token', String(token));
          } catch { /* ignore */ }
        }
        router.replace('/auth/login' as any);
      })();
      return;
    }
    if (!token) { setErr('Missing quiz token.'); setBusy(false); return; }
    (async () => {
      try {
        await api.post('/quiz/claim', { quiz_token: token });
        // Success — jump straight to the profile screen where the full result
        // panel, AI-insight button, PDF and share options already live.
        router.replace('/(tabs)/profile' as any);
      } catch (e: any) {
        setErr(e?.response?.data?.detail || 'Could not claim your quiz result.');
        setBusy(false);
      }
    })();
  }, [token, isAuthenticated]);

  return (
    <SafeAreaView style={s.safe}>
      <View style={s.wrap}>
        {busy && !err && (
          <>
            <ActivityIndicator color={COLORS.primary} size="large" />
            <Text style={s.msg}>Unlocking your Decision Style result…</Text>
          </>
        )}
        {!!err && (
          <>
            <Ionicons name="alert-circle" size={40} color="#DC2626" />
            <Text style={[s.msg, { color: '#DC2626', fontWeight: '700' }]}>{err}</Text>
            <TouchableOpacity style={s.retryBtn} onPress={() => router.replace('/quiz' as any)}>
              <Text style={s.retryT}>Retake the quiz</Text>
            </TouchableOpacity>
          </>
        )}
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.background },
  wrap: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, gap: 16 },
  msg: { fontSize: 14, color: COLORS.textPrimary, textAlign: 'center', marginTop: 8, lineHeight: 20 },
  retryBtn: { backgroundColor: COLORS.primary, paddingHorizontal: 20, paddingVertical: 12, borderRadius: 10, marginTop: 8 },
  retryT: { color: '#fff', fontWeight: '700' },
});
