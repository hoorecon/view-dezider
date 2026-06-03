/**
 * /whatsapp-verify — mandatory WhatsApp number verification (UltraMsg OTP).
 *
 * Shown after signup/login when the user's WhatsApp number is not yet verified.
 * Collects the number (if missing), sends a 6-digit OTP via WhatsApp, and
 * verifies it. On success, refreshes auth and returns to the dashboard.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ActivityIndicator, ScrollView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../src/utils/api';
import { showAlert } from '../src/utils/alert';
import { useAuthStore } from '../src/store/authStore';

export default function WhatsAppVerifyScreen() {
  const router = useRouter();
  const { user, checkAuth, logout } = useAuthStore();
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [step, setStep] = useState<'enter_phone' | 'enter_code'>('enter_phone');
  const [sending, setSending] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [devCode, setDevCode] = useState<string | null>(null);
  const timerRef = useRef<any>(null);

  // If already verified, leave immediately.
  useEffect(() => {
    (async () => {
      try {
        const r = await api.get('/auth/whatsapp/status');
        if (r.data?.whatsapp_verified) {
          router.replace('/(tabs)' as any);
          return;
        }
        if (r.data?.whatsapp_number) setPhone(String(r.data.whatsapp_number));
      } catch { /* ignore */ }
    })();
  }, [router]);

  useEffect(() => {
    if (cooldown <= 0) return;
    timerRef.current = setInterval(() => setCooldown((c) => (c <= 1 ? 0 : c - 1)), 1000);
    return () => clearInterval(timerRef.current);
  }, [cooldown]);

  const sendOtp = useCallback(async () => {
    const digits = phone.replace(/\D/g, '');
    if (digits.length < 10) {
      showAlert('Invalid number', 'Enter a valid WhatsApp number with country code.');
      return;
    }
    setSending(true);
    try {
      const r = await api.post('/auth/whatsapp/send-otp', { phone_number: phone });
      if (r.data?.already_verified) {
        await checkAuth();
        router.replace('/(tabs)' as any);
        return;
      }
      setStep('enter_code');
      setCooldown(r.data?.cooldown_seconds || 60);
      setDevCode(r.data?.dev_code || null);
      if (!r.data?.delivered) {
        showAlert('Code generated', 'WhatsApp delivery is being set up. Use the code shown on screen to continue.');
      }
    } catch (e: any) {
      showAlert('Could not send code', e?.response?.data?.detail || 'Please try again.');
    } finally {
      setSending(false);
    }
  }, [phone, checkAuth, router]);

  const verifyOtp = useCallback(async () => {
    if (code.trim().length < 4) {
      showAlert('Enter the code', 'Please enter the 6-digit code sent to your WhatsApp.');
      return;
    }
    setVerifying(true);
    try {
      await api.post('/auth/whatsapp/verify-otp', { code: code.trim() });
      // Refresh auth so the (tabs) gate sees whatsapp_verified=true, then route.
      await checkAuth();
      router.replace('/(tabs)' as any);
    } catch (e: any) {
      showAlert('Verification failed', e?.response?.data?.detail || 'Invalid or expired code.');
    } finally {
      setVerifying(false);
    }
  }, [code, checkAuth, router]);

  return (
    <SafeAreaView style={s.root} edges={['top', 'bottom']}>
      <ScrollView contentContainerStyle={s.body} keyboardShouldPersistTaps="handled">
        <LinearGradient colors={['#075E54', '#25D366']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={s.hero}>
          <Ionicons name="logo-whatsapp" size={40} color="#FFF" />
          <Text style={s.heroTitle}>Verify your WhatsApp</Text>
          <Text style={s.heroSub}>We engage with you on WhatsApp. Verify your number to continue.</Text>
        </LinearGradient>

        {step === 'enter_phone' ? (
          <View style={s.card}>
            <Text style={s.label}>WhatsApp number</Text>
            <TextInput
              style={s.input}
              value={phone}
              onChangeText={setPhone}
              placeholder="+91 98765 43210"
              placeholderTextColor="#94A3B8"
              keyboardType="phone-pad"
              autoComplete="tel"
            />
            <Text style={s.hint}>Include country code. A 10-digit number is treated as India (+91).</Text>
            <TouchableOpacity style={[s.primaryBtn, sending && { opacity: 0.6 }]} onPress={sendOtp} disabled={sending}>
              {sending ? <ActivityIndicator color="#FFF" /> : <Text style={s.primaryText}>Send code on WhatsApp</Text>}
            </TouchableOpacity>
          </View>
        ) : (
          <View style={s.card}>
            <Text style={s.label}>Enter the 6-digit code</Text>
            <TextInput
              style={[s.input, s.codeInput]}
              value={code}
              onChangeText={(t) => setCode(t.replace(/\D/g, '').slice(0, 6))}
              placeholder="••••••"
              placeholderTextColor="#CBD5E1"
              keyboardType="number-pad"
              maxLength={6}
            />
            {devCode && (
              <View style={s.devBox}>
                <Ionicons name="information-circle" size={14} color="#92400E" />
                <Text style={s.devText}>Demo code (WhatsApp delivery pending): {devCode}</Text>
              </View>
            )}
            <TouchableOpacity style={[s.primaryBtn, verifying && { opacity: 0.6 }]} onPress={verifyOtp} disabled={verifying}>
              {verifying ? <ActivityIndicator color="#FFF" /> : <Text style={s.primaryText}>Verify & continue</Text>}
            </TouchableOpacity>

            <View style={s.resendRow}>
              <Text style={s.resendLabel}>Didn't get it?</Text>
              <TouchableOpacity onPress={sendOtp} disabled={cooldown > 0 || sending}>
                <Text style={[s.resendLink, (cooldown > 0 || sending) && s.resendDisabled]}>
                  {cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend code'}
                </Text>
              </TouchableOpacity>
            </View>
            <TouchableOpacity onPress={() => setStep('enter_phone')}>
              <Text style={s.changeNum}>Change number</Text>
            </TouchableOpacity>
          </View>
        )}

        <TouchableOpacity style={s.logoutBtn} onPress={async () => { await logout(); router.replace('/' as any); }}>
          <Ionicons name="log-out-outline" size={16} color="#64748B" />
          <Text style={s.logoutText}>Log out</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F8FAFC' },
  body: { padding: 16, paddingBottom: 40 },
  hero: { borderRadius: 20, padding: 24, alignItems: 'center', marginBottom: 18 },
  heroTitle: { color: '#FFF', fontSize: 22, fontWeight: '800', marginTop: 10 },
  heroSub: { color: 'rgba(255,255,255,0.9)', fontSize: 13, textAlign: 'center', marginTop: 6, lineHeight: 18 },
  card: { backgroundColor: '#FFF', borderRadius: 16, padding: 18, borderWidth: 1, borderColor: '#E5E7EB' },
  label: { fontSize: 14, fontWeight: '700', color: '#0F172A', marginBottom: 8 },
  input: { borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, color: '#0F172A', backgroundColor: '#F8FAFC' },
  codeInput: { textAlign: 'center', fontSize: 26, letterSpacing: 10, fontWeight: '800' },
  hint: { fontSize: 12, color: '#94A3B8', marginTop: 8 },
  primaryBtn: { marginTop: 16, backgroundColor: '#25D366', borderRadius: 12, paddingVertical: 14, alignItems: 'center' },
  primaryText: { color: '#FFF', fontWeight: '800', fontSize: 15 },
  devBox: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#FEF3C7', borderRadius: 8, padding: 10, marginTop: 12 },
  devText: { color: '#92400E', fontSize: 12, fontWeight: '600', flex: 1 },
  resendRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 16 },
  resendLabel: { color: '#64748B', fontSize: 13 },
  resendLink: { color: '#25D366', fontSize: 13, fontWeight: '700' },
  resendDisabled: { color: '#94A3B8' },
  changeNum: { color: '#7C3AED', fontSize: 13, fontWeight: '600', textAlign: 'center', marginTop: 14 },
  logoutBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 24 },
  logoutText: { color: '#64748B', fontSize: 13, fontWeight: '600' },
});
