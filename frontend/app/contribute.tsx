import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ActivityIndicator, TextInput,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../src/store/authStore';
import { COLORS } from '../src/constants/colors';
import { showAlert } from '../src/utils/alert';
import api from '../src/utils/api';

/**
 * Deep-link landing for emailed / WhatsApp contribution invites
 * (`/contribute?share=<id>`).
 *  • If logged out → stash the share + bounce to login (auto-returns here).
 *  • If the owner required identity verification → OTP gate (email/WhatsApp).
 *  • Otherwise → open the EXACT module → flow → step in contribution mode.
 */
export default function ContributeDeepLink() {
  const { share } = useLocalSearchParams<{ share?: string }>();
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuthStore();
  const [phase, setPhase] = useState<'loading' | 'verify' | 'opening' | 'error'>('loading');
  const [access, setAccess] = useState<any>(null);
  const [channel, setChannel] = useState<'email' | 'whatsapp'>('email');
  const [code, setCode] = useState('');
  const [sending, setSending] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [err, setErr] = useState('');

  const routeToStep = useCallback(async (a: any) => {
    setPhase('opening');
    const qs = `contribShareId=${share}&contribStep=${a.step_number}&access=${a.step_access || 'hidden'}`;
    try {
      if (a.module === 'decision') {
        router.replace(`/prr/${a.decision_id}?${qs}` as any);
        return;
      }
      const { data } = await api.post(`/shared-steps/${share}/open`, {});
      const targetId = data.target_id;
      if (a.module === 'pros_cons') router.replace(`/tools/pros-cons-wizard?id=${targetId}&${qs}` as any);
      else router.replace(`/tools/solution-finder?id=${targetId}&${qs}` as any);
    } catch (e: any) {
      setErr(e?.response?.data?.detail || 'Could not open the flow for contribution');
      setPhase('error');
    }
  }, [share, router]);

  const loadAccess = useCallback(async () => {
    try {
      const { data } = await api.get(`/shared-steps/${share}/access`);
      setAccess(data);
      if (data.needs_verification) {
        setChannel(data.methods?.includes('email') ? 'email' : 'whatsapp');
        setPhase('verify');
      } else {
        routeToStep(data);
      }
    } catch (e: any) {
      setErr(e?.response?.data?.detail || 'This contribution link is no longer valid.');
      setPhase('error');
    }
  }, [share, routeToStep]);

  useEffect(() => {
    (async () => {
      if (isLoading) return; // wait for auth hydration on cold load
      if (!share) { setErr('Missing contribution link.'); setPhase('error'); return; }
      if (!isAuthenticated) {
        await AsyncStorage.setItem('pending_contribute_share', String(share));
        router.replace('/auth/login');
        return;
      }
      await loadAccess();
    })();
  }, [share, isAuthenticated, isLoading, loadAccess, router]);

  const sendOtp = async () => {
    setSending(true);
    try {
      const { data } = await api.post(`/shared-steps/${share}/send-otp`, { channel });
      showAlert(data.sent ? 'Code sent' : 'Requested',
        data.sent ? `We sent a 6-digit code to your ${channel}.` : 'If that channel is set up, your code will arrive shortly.');
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Could not send the code.');
    } finally { setSending(false); }
  };

  const verify = async () => {
    if (!code.trim()) { showAlert('Enter code', 'Type the 6-digit code first.'); return; }
    setVerifying(true);
    try {
      await api.post(`/shared-steps/${share}/verify-otp`, { code: code.trim() });
      routeToStep(access);
    } catch (e: any) {
      showAlert('Verification failed', e?.response?.data?.detail || 'Wrong or expired code.');
    } finally { setVerifying(false); }
  };

  if (phase === 'loading' || phase === 'opening') {
    return (
      <View style={s.center}>
        <ActivityIndicator size="large" color={COLORS.primary} />
        <Text style={s.muted}>{phase === 'opening' ? 'Opening your step…' : 'Loading your invitation…'}</Text>
      </View>
    );
  }

  if (phase === 'error') {
    return (
      <View style={s.center}>
        <Ionicons name="alert-circle-outline" size={44} color={COLORS.textMuted} />
        <Text style={s.errTitle}>Can’t open this invite</Text>
        <Text style={s.muted}>{err}</Text>
        <TouchableOpacity style={s.primaryBtn} onPress={() => router.replace('/inbox' as any)}>
          <Text style={s.primaryBtnTxt}>Go to my inbox</Text>
        </TouchableOpacity>
      </View>
    );
  }

  // verify phase
  const methods: string[] = access?.methods || [];
  return (
    <View style={s.center}>
      <View style={s.card}>
        <View style={s.iconWrap}><Ionicons name="shield-checkmark" size={26} color="#7C3AED" /></View>
        <Text style={s.title}>Verify it’s you</Text>
        <Text style={s.sub}>The owner asked contributors to verify identity before opening
          {access?.title ? ` "${access.title}"` : ' this step'}.</Text>

        {methods.length > 1 && (
          <View style={s.channelRow}>
            {methods.includes('email') && (
              <TouchableOpacity onPress={() => setChannel('email')}
                style={[s.channelChip, channel === 'email' && s.channelChipOn]}>
                <Ionicons name="mail" size={14} color={channel === 'email' ? '#FFF' : COLORS.textSecondary} />
                <Text style={[s.channelTxt, channel === 'email' && { color: '#FFF' }]}>Email {access?.email_hint}</Text>
              </TouchableOpacity>
            )}
            {methods.includes('whatsapp') && (
              <TouchableOpacity onPress={() => setChannel('whatsapp')}
                style={[s.channelChip, channel === 'whatsapp' && s.channelChipOn]}>
                <Ionicons name="logo-whatsapp" size={14} color={channel === 'whatsapp' ? '#FFF' : COLORS.textSecondary} />
                <Text style={[s.channelTxt, channel === 'whatsapp' && { color: '#FFF' }]}>WhatsApp {access?.phone_hint}</Text>
              </TouchableOpacity>
            )}
          </View>
        )}

        <TouchableOpacity style={s.sendBtn} onPress={sendOtp} disabled={sending}>
          {sending ? <ActivityIndicator color="#7C3AED" size="small" />
            : <Text style={s.sendTxt}>Send code via {channel === 'email' ? 'Email' : 'WhatsApp'}</Text>}
        </TouchableOpacity>

        <TextInput style={s.codeInput} placeholder="6-digit code" keyboardType="number-pad"
          value={code} onChangeText={setCode} maxLength={6} textAlign="center" />

        <TouchableOpacity style={s.primaryBtn} onPress={verify} disabled={verifying}>
          {verifying ? <ActivityIndicator color="#FFF" size="small" />
            : <Text style={s.primaryBtnTxt}>Verify & continue</Text>}
        </TouchableOpacity>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, backgroundColor: COLORS.background },
  muted: { fontSize: 13.5, color: COLORS.textMuted, marginTop: 12, textAlign: 'center' },
  errTitle: { fontSize: 17, fontWeight: '800', color: COLORS.textPrimary, marginTop: 10 },
  card: { width: '100%', maxWidth: 380, backgroundColor: COLORS.white, borderRadius: 20, padding: 22, alignItems: 'center' },
  iconWrap: { width: 56, height: 56, borderRadius: 28, backgroundColor: '#F5F3FF', alignItems: 'center', justifyContent: 'center', marginBottom: 10 },
  title: { fontSize: 19, fontWeight: '800', color: COLORS.textPrimary },
  sub: { fontSize: 13, color: COLORS.textSecondary, textAlign: 'center', marginTop: 6, lineHeight: 18 },
  channelRow: { flexDirection: 'row', gap: 8, marginTop: 16, flexWrap: 'wrap', justifyContent: 'center' },
  channelChip: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 18, borderWidth: 1, borderColor: COLORS.border },
  channelChipOn: { backgroundColor: '#7C3AED', borderColor: '#7C3AED' },
  channelTxt: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },
  sendBtn: { marginTop: 16, paddingVertical: 10, paddingHorizontal: 16, borderRadius: 10, borderWidth: 1, borderColor: '#DDD6FE', backgroundColor: '#FAF5FF' },
  sendTxt: { fontSize: 13, fontWeight: '700', color: '#7C3AED' },
  codeInput: { marginTop: 14, width: '70%', borderWidth: 1, borderColor: COLORS.border, borderRadius: 12, paddingVertical: 12, fontSize: 20, fontWeight: '700', letterSpacing: 6, color: COLORS.textPrimary },
  primaryBtn: { marginTop: 16, backgroundColor: COLORS.primary, borderRadius: 12, paddingVertical: 13, paddingHorizontal: 28, alignItems: 'center', minWidth: 200 },
  primaryBtnTxt: { fontSize: 15, fontWeight: '700', color: '#FFF' },
});
