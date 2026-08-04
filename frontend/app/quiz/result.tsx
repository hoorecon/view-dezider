/**
 * Guest-quiz result claim + reveal.
 *
 * URL: /quiz/result?token=<quiz_token>
 *
 * A logged-in user lands here after taking the marketing-hook quiz on /quiz
 * (or quiz.jelcos.ai). We POST /api/quiz/claim to redeem the guest token
 * against a real assessment row, then render an inline success screen with
 * the dominant mode + a big "View Full Result" CTA that jumps to profile.
 *
 * Robustness (fix for empty-page regression):
 *  1. Accepts `?token=` OR `?quiz_token=` (case tolerated).
 *  2. Falls back to `pending_quiz_token` in AsyncStorage when URL has none.
 *  3. If Google-Auth returned `?session_id=` or `#session_id=` to this page
 *     directly, completes login in-place before claiming.
 *  4. Handles 409 "already claimed" with a friendly "Open your result" CTA.
 *  5. Never silently redirects — always renders a visible success/error UI.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ActivityIndicator, TouchableOpacity, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { useAuthStore } from '../../src/store/authStore';

const MODE_LABEL: Record<string, string> = {
  emotional: 'Emotional',
  logical: 'Logical',
  intuitive: 'Intuitive',
  consciousness: 'Consciousness',
};
const MODE_EMOJI: Record<string, string> = {
  emotional: '❤️',
  logical: '🧠',
  intuitive: '✨',
  consciousness: '🌿',
};

export default function QuizResultScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ token?: string; quiz_token?: string; session_id?: string }>();
  const { isAuthenticated, loginWithGoogle } = useAuthStore() as any;
  const [busy, setBusy] = useState(true);
  const [err, setErr] = useState('');
  const [alreadyClaimed, setAlreadyClaimed] = useState(false);
  const [result, setResult] = useState<{ dominant_mode?: string; mode_scores?: Record<string, number> } | null>(null);

  // ── Helper: resolve the quiz token from URL params or AsyncStorage ────
  const resolveToken = async (): Promise<string> => {
    const fromUrl = (params.token || params.quiz_token || '').toString().trim();
    if (fromUrl) return fromUrl;
    try {
      const stashed = await AsyncStorage.getItem('pending_quiz_token');
      if (stashed) return stashed;
    } catch { /* ignore */ }
    return '';
  };

  // ── Helper: complete an in-page Google Auth session if present ────────
  const completeInPageAuth = async (): Promise<boolean> => {
    if (Platform.OS !== 'web' || typeof window === 'undefined') return false;
    const hash = window.location.hash || '';
    const search = window.location.search || '';
    const combined = `${hash}${hash && search ? '&' : ''}${search}`;
    const m = combined.match(/session_?id=([^&#]+)/i);
    const sessionId = m ? m[1] : (params.session_id || '');
    if (!sessionId) return false;
    try {
      // Strip auth params so refresh/back can't replay a consumed OAuth state.
      const cleanQuery = new URLSearchParams(window.location.search);
      cleanQuery.delete('session_id');
      cleanQuery.delete('sessionID');
      const qs = cleanQuery.toString();
      window.history.replaceState(null, '', window.location.pathname + (qs ? `?${qs}` : ''));
    } catch { /* ignore */ }
    try {
      if (loginWithGoogle) await loginWithGoogle(sessionId);
      return true;
    } catch {
      return false;
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      // Step 1 — if OAuth callback params are on this URL, complete auth first.
      if (!isAuthenticated) {
        const ok = await completeInPageAuth();
        if (!ok) {
          // Not authenticated and no session_id to consume → bounce to login,
          // preserving the intent so we come back HERE after sign-in.
          const token = await resolveToken();
          try { if (token) await AsyncStorage.setItem('pending_quiz_token', token); } catch {}
          try { await AsyncStorage.setItem('post_auth_next', `/quiz/result${token ? `?token=${token}` : ''}`); } catch {}
          router.replace('/auth/login' as any);
          return;
        }
        // We just authenticated — the isAuthenticated dep will retrigger this
        // effect; return here to avoid double-claim on the same tick.
        return;
      }

      // Step 2 — claim the token.
      const token = await resolveToken();
      if (!token) {
        if (!cancelled) { setErr('Missing quiz token. Please retake the quiz.'); setBusy(false); }
        return;
      }
      try {
        const resp = await api.post('/quiz/claim', { quiz_token: token });
        // Clear stashed intent — result is now bound to the account.
        try { await AsyncStorage.removeItem('pending_quiz_token'); } catch {}
        try { await AsyncStorage.removeItem('post_auth_next'); } catch {}
        if (!cancelled) {
          setResult({
            dominant_mode: resp.data?.dominant_mode,
            mode_scores: resp.data?.mode_scores,
          });
          setBusy(false);
        }
      } catch (e: any) {
        const status = e?.response?.status;
        const detail = e?.response?.data?.detail || 'Could not claim your quiz result.';
        if (!cancelled) {
          if (status === 409) {
            setAlreadyClaimed(true);
            setErr('');
          } else {
            setErr(detail);
          }
          setBusy(false);
        }
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <SafeAreaView style={s.safe}>
      <View style={s.wrap}>
        {busy && (
          <>
            <ActivityIndicator color={COLORS.primary} size="large" />
            <Text style={s.msg}>Unlocking your Decision Style result…</Text>
          </>
        )}

        {!busy && !!err && !alreadyClaimed && (
          <>
            <Ionicons name="alert-circle" size={40} color="#DC2626" />
            <Text style={[s.msg, { color: '#DC2626', fontWeight: '700' }]}>{err}</Text>
            <TouchableOpacity style={s.retryBtn} onPress={() => router.replace('/quiz' as any)}>
              <Text style={s.retryT}>Retake the quiz</Text>
            </TouchableOpacity>
          </>
        )}

        {!busy && alreadyClaimed && (
          <>
            <Ionicons name="checkmark-circle" size={48} color={COLORS.primary} />
            <Text style={s.headline}>You already claimed this quiz</Text>
            <Text style={s.msg}>Your Decision Style is saved to your profile. Tap below to view it.</Text>
            <TouchableOpacity style={s.primaryBtn} onPress={() => router.replace('/(tabs)/profile' as any)}>
              <Text style={s.primaryBtnT}>Open my Result</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.linkBtn} onPress={() => router.replace('/quiz' as any)}>
              <Text style={s.linkT}>Retake the quiz</Text>
            </TouchableOpacity>
          </>
        )}

        {!busy && !err && result?.dominant_mode && (
          <>
            <View style={s.badgeBig}>
              <Text style={s.badgeEmoji}>{MODE_EMOJI[result.dominant_mode] || '🎯'}</Text>
            </View>
            <Text style={s.headline}>Your Decision Style</Text>
            <Text style={s.dominant}>{MODE_LABEL[result.dominant_mode] || result.dominant_mode}</Text>

            {result.mode_scores && (
              <View style={s.scores}>
                {Object.entries(result.mode_scores).map(([k, v]) => (
                  <View key={k} style={s.scoreRow}>
                    <Text style={s.scoreLabel}>{MODE_EMOJI[k]} {MODE_LABEL[k] || k}</Text>
                    <View style={s.barTrack}>
                      <View style={[s.barFill, { width: `${Math.min(100, (Number(v) / 5) * 100)}%` }]} />
                    </View>
                    <Text style={s.scoreVal}>{Number(v).toFixed(2)}</Text>
                  </View>
                ))}
              </View>
            )}

            <TouchableOpacity style={s.primaryBtn} onPress={() => router.replace('/(tabs)/profile' as any)}>
              <Text style={s.primaryBtnT}>View full breakdown, PDF & share →</Text>
            </TouchableOpacity>
          </>
        )}
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.background },
  wrap: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, gap: 12 },
  msg: { fontSize: 14, color: COLORS.textPrimary, textAlign: 'center', marginTop: 8, lineHeight: 20 },
  headline: { fontSize: 20, fontWeight: '700', color: COLORS.textPrimary, textAlign: 'center', marginTop: 4 },
  dominant: { fontSize: 28, fontWeight: '800', color: COLORS.primary, textAlign: 'center', marginTop: 2 },
  badgeBig: { width: 84, height: 84, borderRadius: 42, backgroundColor: '#F1F5F9', alignItems: 'center', justifyContent: 'center' },
  badgeEmoji: { fontSize: 40 },
  scores: { width: '100%', maxWidth: 420, marginTop: 8, gap: 10 },
  scoreRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  scoreLabel: { width: 130, fontSize: 13, color: COLORS.textPrimary, fontWeight: '600' },
  barTrack: { flex: 1, height: 8, backgroundColor: '#E5E7EB', borderRadius: 4, overflow: 'hidden' },
  barFill: { height: 8, backgroundColor: COLORS.primary, borderRadius: 4 },
  scoreVal: { width: 44, textAlign: 'right', fontSize: 12, color: COLORS.textSecondary, fontVariant: ['tabular-nums'] },
  retryBtn: { backgroundColor: COLORS.primary, paddingHorizontal: 20, paddingVertical: 12, borderRadius: 10, marginTop: 8 },
  retryT: { color: '#fff', fontWeight: '700' },
  primaryBtn: { backgroundColor: COLORS.primary, paddingHorizontal: 22, paddingVertical: 14, borderRadius: 12, marginTop: 14 },
  primaryBtnT: { color: '#fff', fontWeight: '800', fontSize: 15 },
  linkBtn: { paddingHorizontal: 12, paddingVertical: 8, marginTop: 6 },
  linkT: { color: COLORS.primary, fontWeight: '600', fontSize: 13 },
});
