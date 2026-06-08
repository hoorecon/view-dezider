/**
 * /embed/[flow] — White-label partner embed entry (P1)
 * =====================================================
 * Rendered inside an iframe on a partner's website (render_mode = "rn_web").
 *
 * Responsibilities:
 *   • Resolve partner theme from /api/embed/public-config/{slug} (server-side,
 *     anti-spoof) and apply it (white-label vs co-brand).
 *   • Embedded org sign-in (frictionless OR WhatsApp-OTP, driven by config)
 *     using the EXISTING org login (/api/org-auth/*).
 *   • Show the carried-over options handed off from the partner page (P2 will
 *     consume these to pre-seed the actual flow).
 *   • Launch the selected decision flow.
 *
 * This route is registered as a PUBLIC segment in app/_layout.tsx so the
 * global WhatsApp/auth gate does not hijack it.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  TextInput, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Ionicons } from '@expo/vector-icons';
import axios from 'axios';
import { useAuthStore } from '../../src/store/authStore';
import ScreenerPanel from '../../src/features/screener/ScreenerPanel';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

type FlowKey = 'mydezider' | 'pros_cons' | 'screener';

const FLOW_META: Record<FlowKey, { label: string; blurb: string; route: string; icon: any }> = {
  mydezider: {
    label: 'MyDezider', icon: 'git-network',
    blurb: 'Turn your shortlist into a structured, weighted decision — define factors, set priorities, and get a clear recommendation.',
    route: '/tools/new-decision',
  },
  pros_cons: {
    label: 'Pros & Cons', icon: 'swap-horizontal',
    blurb: 'Weigh each option side-by-side with weighted pros and cons to reveal the strongest choice.',
    route: '/tools/pros-cons-wizard',
  },
  screener: {
    label: 'Smart Screener', icon: 'funnel',
    blurb: 'Rank an entire catalogue against your weighted criteria and surface the top matches.',
    route: '/tools/new-decision',
  },
};

interface PublicConfig {
  slug: string;
  display_name: string;
  branding_mode: 'white_label' | 'co_brand';
  render_mode: string;
  enabled_flows: string[];
  auth_mode: string;
  otp_required: boolean;
  theme: { primary_color: string; accent_color?: string; logo_uri?: string; hide_powered_by?: boolean };
}

export default function PartnerEmbed() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const flow = (String(params.flow || 'mydezider') as FlowKey);
  const slug = String(params.partner || '').trim();
  const rawOptions = String(params.options || '');

  const [cfg, setCfg] = useState<PublicConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [authed, setAuthed] = useState(false);

  // login form state
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [otpStep, setOtpStep] = useState<{ verification_id: string; masked?: string; devCode?: string } | null>(null);
  const [otp, setOtp] = useState('');
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState<string | null>(null);

  const setSession = useAuthStore((s) => s.setSession);

  const options: any[] = (() => {
    if (!rawOptions) return [];
    try { return JSON.parse(rawOptions); } catch { return []; }
  })();

  const meta = FLOW_META[flow] || FLOW_META.mydezider;

  const bootstrap = useCallback(async () => {
    if (!slug) { setError('Missing partner'); setLoading(false); return; }
    try {
      setLoading(true);
      const r = await axios.get(
        `${API_URL}/api/embed/public-config/${encodeURIComponent(slug)}`,
        { timeout: 15000 },
      );
      setCfg(r.data);
      // already signed in?
      const token = await AsyncStorage.getItem('session_token');
      if (token) {
        try {
          await axios.get(`${API_URL}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
          setAuthed(true);
        } catch { /* token stale — show login */ }
      }
      setError(null);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Partner not found');
    } finally { setLoading(false); }
  }, [slug]);

  useEffect(() => { bootstrap(); }, [bootstrap]);

  const primary = cfg?.theme?.primary_color || '#7C3AED';
  const accent = cfg?.theme?.accent_color || '#C9A24B';
  const whiteLabel = cfg?.branding_mode !== 'co_brand';
  const hidePb = !!cfg?.theme?.hide_powered_by;

  const doLogin = async () => {
    if (!email.trim() || !password.trim()) { setFormErr('Enter email and password'); return; }
    setBusy(true); setFormErr(null);
    try {
      const r = await axios.post(`${API_URL}/api/org-auth/login`, {
        org_slug: slug, email: email.trim(), password,
      });
      const d = r.data;
      if (d.status === 'authenticated' && d.session_token) {
        await setSession(d.session_token, d.user || {});
        setAuthed(true);
      } else if (d.requires_otp) {
        setOtpStep({ verification_id: d.verification_id, masked: d.masked_phone, devCode: d.dev_code });
      }
    } catch (e: any) {
      setFormErr(e?.response?.data?.detail || 'Sign in failed');
    } finally { setBusy(false); }
  };

  const doVerify = async () => {
    if (!otp.trim() || !otpStep) { setFormErr('Enter the code'); return; }
    setBusy(true); setFormErr(null);
    try {
      const r = await axios.post(`${API_URL}/api/org-auth/verify-otp`, {
        verification_id: otpStep.verification_id, otp: otp.trim(),
      });
      const d = r.data;
      if (d.session_token) {
        await setSession(d.session_token, d.user || {});
        setAuthed(true);
      }
    } catch (e: any) {
      setFormErr(e?.response?.data?.detail || 'Invalid code');
    } finally { setBusy(false); }
  };

  const launchFlow = async () => {
    // Stash the handed-off options so the real flow can pre-seed (P2).
    try {
      await AsyncStorage.setItem('embed_seed', JSON.stringify({
        flow, partner: slug, options, ts: Date.now(),
      }));
    } catch { /* non-fatal */ }
    router.push(meta.route as any);
  };

  // ---- render ----
  if (loading) {
    return <View style={styles.center}><ActivityIndicator color={primary} size="large" /></View>;
  }
  if (error || !cfg) {
    return (
      <View style={styles.center}>
        <Ionicons name="alert-circle-outline" size={44} color="#9CA3AF" />
        <Text style={styles.errText}>{error || 'Unable to load'}</Text>
        <Text style={styles.errSub}>partner: {slug || '—'}</Text>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1, backgroundColor: '#F8FAFC' }}>
      {/* Header */}
      <View style={[styles.header, { backgroundColor: primary }]}>
        {cfg.theme?.logo_uri
          ? <Text style={styles.headerBrand}>{cfg.display_name}</Text>
          : <Text style={styles.headerBrand}>{whiteLabel ? cfg.display_name : 'View Dezider'}</Text>}
        <View style={[styles.flowChip, { backgroundColor: accent }]}>
          <Ionicons name={meta.icon} size={13} color="#1F2937" />
          <Text style={styles.flowChipText}>{meta.label}</Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
        <View style={styles.card}>
          <Text style={styles.title}>Make this decision with confidence</Text>
          <Text style={styles.blurb}>{meta.blurb}</Text>

          {options.length > 0 && (
            <View style={styles.optsWrap}>
              <Text style={styles.optsHead}>{options.length} option{options.length > 1 ? 's' : ''} carried over from {cfg.display_name}</Text>
              {options.map((o, i) => (
                <View key={i} style={[styles.optRow, { borderLeftColor: primary }]}>
                  <Text style={styles.optName}>{typeof o === 'string' ? o : (o?.name || 'Option')}</Text>
                  {o && typeof o === 'object' && o.attributes && (
                    <Text style={styles.optAttrs} numberOfLines={2}>
                      {Object.entries(o.attributes).map(([k, v]) => `${k}: ${v}`).join('  •  ')}
                    </Text>
                  )}
                </View>
              ))}
            </View>
          )}

          {!authed ? (
            <View style={styles.authBox}>
              <Text style={styles.authHead}>Sign in to continue</Text>
              {!otpStep ? (
                <>
                  <TextInput
                    style={styles.input} placeholder="Work email" placeholderTextColor="#9CA3AF"
                    keyboardType="email-address" autoCapitalize="none" value={email} onChangeText={setEmail}
                  />
                  <TextInput
                    style={styles.input} placeholder="Password" placeholderTextColor="#9CA3AF"
                    secureTextEntry value={password} onChangeText={setPassword}
                  />
                  {!!formErr && <Text style={styles.formErr}>{formErr}</Text>}
                  <TouchableOpacity style={[styles.primaryBtn, { backgroundColor: primary }]} onPress={doLogin} disabled={busy}>
                    {busy ? <ActivityIndicator color="#FFF" /> : <Text style={styles.primaryBtnText}>Sign in</Text>}
                  </TouchableOpacity>
                </>
              ) : (
                <>
                  <Text style={styles.otpHint}>
                    We sent a code to {otpStep.masked || 'your WhatsApp'}.
                    {otpStep.devCode ? `  (dev: ${otpStep.devCode})` : ''}
                  </Text>
                  <TextInput
                    style={styles.input} placeholder="6-digit code" placeholderTextColor="#9CA3AF"
                    keyboardType="number-pad" value={otp} onChangeText={setOtp} maxLength={6}
                  />
                  {!!formErr && <Text style={styles.formErr}>{formErr}</Text>}
                  <TouchableOpacity style={[styles.primaryBtn, { backgroundColor: primary }]} onPress={doVerify} disabled={busy}>
                    {busy ? <ActivityIndicator color="#FFF" /> : <Text style={styles.primaryBtnText}>Verify & continue</Text>}
                  </TouchableOpacity>
                </>
              )}
            </View>
          ) : flow === 'screener' ? (
            <ScreenerPanel partner={slug} primary={primary} accent={accent} initialOptions={options} />
          ) : (
            <TouchableOpacity style={[styles.primaryBtn, { backgroundColor: primary, marginTop: 18 }]} onPress={launchFlow}>
              <Text style={styles.primaryBtnText}>Start {meta.label}</Text>
              <Ionicons name="arrow-forward" size={16} color="#FFF" style={{ marginLeft: 6 }} />
            </TouchableOpacity>
          )}
        </View>

        {!hidePb && (
          <Text style={styles.poweredBy}>{whiteLabel ? 'Powered by View Dezider' : ''}</Text>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, backgroundColor: '#F8FAFC' },
  errText: { marginTop: 10, fontSize: 15, color: '#334155', fontWeight: '600' },
  errSub: { marginTop: 4, fontSize: 12, color: '#94A3B8' },

  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 18, paddingVertical: 14 },
  headerBrand: { color: '#FFF', fontSize: 18, fontWeight: '800', flex: 1 },
  flowChip: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 12 },
  flowChipText: { fontSize: 12, fontWeight: '800', color: '#1F2937' },

  body: { padding: 18, paddingBottom: 60, maxWidth: 680, width: '100%', alignSelf: 'center' },
  card: { backgroundColor: '#FFF', borderRadius: 16, padding: 20, borderWidth: 1, borderColor: '#E5E7EB' },
  title: { fontSize: 19, fontWeight: '800', color: '#0F172A' },
  blurb: { fontSize: 14, color: '#475569', lineHeight: 21, marginTop: 8 },

  optsWrap: { marginTop: 16 },
  optsHead: { fontSize: 11, fontWeight: '800', color: '#64748B', textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 8 },
  optRow: { backgroundColor: '#F8FAFC', borderRadius: 10, borderLeftWidth: 3, paddingVertical: 10, paddingHorizontal: 12, marginBottom: 8 },
  optName: { fontSize: 14, fontWeight: '700', color: '#1F2937' },
  optAttrs: { fontSize: 12, color: '#64748B', marginTop: 3 },

  authBox: { marginTop: 18, borderTopWidth: 1, borderTopColor: '#F1F5F9', paddingTop: 16 },
  authHead: { fontSize: 13, fontWeight: '700', color: '#334155', marginBottom: 10 },
  input: { borderWidth: 1, borderColor: '#D1D5DB', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 12, fontSize: 14, color: '#0F172A', backgroundColor: '#FFF', marginBottom: 10 },
  otpHint: { fontSize: 12, color: '#64748B', marginBottom: 10 },
  formErr: { color: '#B91C1C', fontSize: 12.5, marginBottom: 8 },

  primaryBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 14, borderRadius: 12 },
  primaryBtnText: { color: '#FFF', fontSize: 15, fontWeight: '800' },

  poweredBy: { textAlign: 'center', fontSize: 11, color: '#9CA3AF', marginTop: 14 },
});
