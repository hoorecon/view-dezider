/**
 * ImportCreditsStrip — upfront credits preview for the URL-import flows.
 * Shows "≈ N cr needed · M cr available" (history-based estimate from the
 * user's recent runs) with a Top-up shortcut when the balance falls short.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ActivityIndicator, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import api from '../utils/api';

interface Props {
  endpoint: 'import' | 'deep_import';
  pages?: number;
  tier?: string;
}

const fmt = (v: number) =>
  Number(v ?? 0) >= 10000 ? `${(v / 1000).toFixed(1)}k` : `${Math.round(Number(v ?? 0))}`;

export const ImportCreditsStrip: React.FC<Props> = ({ endpoint, pages = 1, tier = 'fast' }) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let on = true;
    setLoading(true);
    api.get('/ai-wallet/import-estimate', { params: { endpoint, pages, tier } })
      .then(r => { if (on) setData(r.data); })
      .catch(() => { if (on) setData(null); })
      .finally(() => { if (on) setLoading(false); });
    return () => { on = false; };
  }, [endpoint, pages, tier]);

  if (loading) {
    return (
      <View style={[s.strip, s.neutral]} testID="import-credits-strip-loading">
        <ActivityIndicator size="small" color="#94A3B8" />
        <Text style={s.mutedTxt}>Checking your AI credits…</Text>
      </View>
    );
  }
  if (!data) return null;

  const ok = !!data.sufficient;
  // Mark when the figure is a tier-scaled estimate (no tier-specific
  // history yet) — so users understand it's an extrapolation, not the
  // user's own historical average.
  const isScaled = data.basis === 'history_scaled';
  const isDefault = data.basis === 'default';
  return (
    <View style={[s.strip, ok ? s.ok : s.bad]} testID="import-credits-strip">
      <Ionicons name={ok ? 'checkmark-circle' : 'alert-circle'} size={15}
        color={ok ? '#059669' : '#DC2626'} />
      <Text style={[s.txt, { color: ok ? '#065F46' : '#991B1B' }]} testID="import-credits-text">
        ≈ {fmt(data.estimate)} cr needed · {fmt(data.balance)} cr available
        {tier === 'precise' ? ' · Precise' : ' · Fast'}
        {isDefault ? ' (est.)' : ''}
        {isScaled ? ` (~${(data.tier_multiplier ?? 4.5).toFixed(1)}× scaled)` : ''}
      </Text>
      {!ok && (
        <TouchableOpacity testID="import-credits-topup-btn" style={s.topup}
          activeOpacity={0.85} onPress={() => router.push('/ai-wallet')}>
          <Ionicons name="flash" size={11} color="#FFF" />
          <Text style={s.topupTxt}>Top up</Text>
        </TouchableOpacity>
      )}
    </View>
  );
};

const s = StyleSheet.create({
  strip: { flexDirection: 'row', alignItems: 'center', gap: 7, marginTop: 10, paddingHorizontal: 10, paddingVertical: 8, borderRadius: 9, borderWidth: 1 },
  neutral: { backgroundColor: '#F8FAFC', borderColor: '#E2E8F0' },
  ok: { backgroundColor: '#ECFDF5', borderColor: '#A7F3D0' },
  bad: { backgroundColor: '#FEF2F2', borderColor: '#FECACA' },
  txt: { flex: 1, fontSize: 12, fontWeight: '700' },
  mutedTxt: { fontSize: 12, color: '#94A3B8', fontWeight: '600' },
  topup: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#DC2626', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 14 },
  topupTxt: { fontSize: 11.5, fontWeight: '800', color: '#FFF' },
});

export default ImportCreditsStrip;
