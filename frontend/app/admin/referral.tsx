/**
 * Admin · Referral Bonus Designer
 * SuperAdmin-configurable commissions, KP rate, coupons, AI split, ALOS.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { showAlert } from '../../src/utils/alert';
import api from '../../src/utils/api';
import { safeBack } from '../../src/utils/navigation';

export default function AdminReferral() {
  const router = useRouter();
  const [cfg, setCfg] = useState<any>({});
  const [busy, setBusy] = useState(false);
  const [sim, setSim] = useState<any>(null);
  const [simInput, setSimInput] = useState({ amount: 5000, level: 1, isFirst: true, topTier: false });

  const load = async () => {
    setBusy(true);
    try { const { data } = await api.get('/referral/config'); setCfg(data || {}); }
    finally { setBusy(false); }
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    try { await api.put('/referral/config', cfg); showAlert('Saved', 'Referral config updated.'); }
    catch(e:any){ showAlert('Save failed', e?.response?.data?.detail || e.message); }
  };

  const simulate = async () => {
    try {
      const { data } = await api.post('/referral/simulate', {
        purchase_amount_inr: Number(simInput.amount),
        level: Number(simInput.level),
        is_first_purchase: simInput.isFirst,
        user_on_highest_tier: simInput.topTier,
      });
      setSim(data);
    } catch (e: any) { showAlert('Simulate failed', e?.response?.data?.detail || e.message); }
  };

  const num = (k: string, label: string, suffix?: string) => (
    <View key={k} style={s.kvRow}>
      <Text style={s.kvLabel}>{label}{suffix ? ` (${suffix})` : ''}</Text>
      <TextInput style={s.kvInput} keyboardType="numeric" value={String(cfg[k] ?? '')} onChangeText={(v) => setCfg((p:any) => ({ ...p, [k]: v === '' ? 0 : Number(v) }))} />
    </View>
  );

  return (
    <SafeAreaView style={s.wrap} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={s.backBtn}><Ionicons name="arrow-back" size={22} color="#FFF" /></TouchableOpacity>
        <Text style={s.title}>Referral Bonus Designer</Text>
        <Text style={s.subtitle}>4-mode payouts · K = referral_rate × avg_refs × conversion</Text>
      </View>
      <ScrollView contentContainerStyle={{ padding: 16 }}>
        {busy ? <ActivityIndicator /> : (<>
          <Text style={s.sectionTitle}>Commissions</Text>
          <View style={s.card}>
            {num('l1_pct_first', 'L1 first purchase', '%')}
            {num('l2_pct_first', 'L2 first purchase', '%')}
            {num('l3_pct_first', 'L3 first purchase', '%')}
            {num('subsequent_multiplier', 'Subsequent multiplier', '×')}
            {num('alos_days', 'ALOS (estimated avg lifespan)', 'days')}
          </View>

          <Text style={s.sectionTitle}>Karma Points</Text>
          <View style={s.card}>
            {num('karma_points_per_unit', 'KP per unit')}
            {num('karma_inr_value', 'INR per KP unit', '₹')}
          </View>

          <Text style={s.sectionTitle}>Coupons</Text>
          <View style={s.card}>
            {num('coupon_min_pct', 'Min %')}
            {num('coupon_max_pct', 'Max %')}
            {num('coupon_default_pct', 'Default %')}
            {num('coupon_validity_days', 'Validity', 'days')}
          </View>

          <Text style={s.sectionTitle}>AI Auto-Split (sums to 100%)</Text>
          <View style={s.card}>
            {num('split_cash', 'Cash %')}
            {num('split_coupon', 'Coupon %')}
            {num('split_karma', 'Karma %')}
            {num('split_special', 'Special-access %')}
            {num('ai_rebalance_days', 'Re-balance every', 'days')}
          </View>

          <Text style={s.sectionTitle}>Cash Payout</Text>
          <View style={s.card}>{num('cash_refund_window_days', 'Refund window', 'days')}</View>

          <TouchableOpacity style={s.saveBig} onPress={save}><Text style={s.saveBigText}>Save All Config</Text></TouchableOpacity>

          <Text style={s.sectionTitle}>Simulate Payout</Text>
          <View style={s.card}>
            <View style={s.kvRow}><Text style={s.kvLabel}>Purchase amount (₹)</Text><TextInput style={s.kvInput} keyboardType="numeric" value={String(simInput.amount)} onChangeText={(v) => setSimInput(p => ({ ...p, amount: Number(v)||0 }))} /></View>
            <View style={s.kvRow}><Text style={s.kvLabel}>Level (1/2/3)</Text><TextInput style={s.kvInput} keyboardType="numeric" value={String(simInput.level)} onChangeText={(v) => setSimInput(p => ({ ...p, level: Math.min(3, Math.max(1, Number(v)||1)) }))} /></View>
            <View style={s.kvRow}><Text style={s.kvLabel}>First purchase?</Text><TouchableOpacity style={[s.toggle, simInput.isFirst && s.toggleOn]} onPress={() => setSimInput(p => ({ ...p, isFirst: !p.isFirst }))}><Text style={[s.toggleText, simInput.isFirst && { color: '#FFF' }]}>{simInput.isFirst ? 'YES' : 'NO'}</Text></TouchableOpacity></View>
            <View style={s.kvRow}><Text style={s.kvLabel}>On highest tier?</Text><TouchableOpacity style={[s.toggle, simInput.topTier && s.toggleOn]} onPress={() => setSimInput(p => ({ ...p, topTier: !p.topTier }))}><Text style={[s.toggleText, simInput.topTier && { color: '#FFF' }]}>{simInput.topTier ? 'YES' : 'NO'}</Text></TouchableOpacity></View>
            <TouchableOpacity style={[s.saveBig, { marginTop: 8 }]} onPress={simulate}><Ionicons name="flash" size={16} color="#FFF" /><Text style={s.saveBigText}>  Run Simulation</Text></TouchableOpacity>
          </View>
          {sim && (
            <View style={s.simCard}>
              <Text style={s.simHead}>Total reward: ₹{sim.total_reward_inr} ({sim.applied_pct}%)</Text>
              <View style={s.simRow}><Text style={s.simK}>Cash</Text><Text style={s.simV}>₹{sim.breakdown?.cash_inr}</Text></View>
              <View style={s.simRow}><Text style={s.simK}>Coupon (₹ equiv)</Text><Text style={s.simV}>₹{sim.breakdown?.coupon_value_inr} · {sim.breakdown?.coupon_default_pct}% off · valid {sim.breakdown?.coupon_validity_days}d</Text></View>
              <View style={s.simRow}><Text style={s.simK}>Karma Points</Text><Text style={s.simV}>{sim.breakdown?.karma_points} KP ≈ ₹{sim.breakdown?.karma_value_inr}</Text></View>
              <View style={s.simRow}><Text style={s.simK}>Special Access</Text><Text style={s.simV}>₹{sim.breakdown?.special_access_value_inr} ({sim.breakdown?.special_access_resolution?.strategy})</Text></View>
              <Text style={s.simNote}>Cash held for {sim.cash_refund_window_days} days (refund window).</Text>
            </View>
          )}
        </>)}
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { backgroundColor: '#003087', padding: 16 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.18)', alignItems: 'center', justifyContent: 'center', marginBottom: 8 },
  title: { color: '#FFF', fontSize: 20, fontWeight: '800' },
  subtitle: { color: 'rgba(255,255,255,0.85)', fontSize: 12, marginTop: 2 },
  sectionTitle: { fontSize: 13, fontWeight: '800', color: '#003087', marginTop: 14, marginBottom: 6 },
  card: { backgroundColor: '#FFF', borderRadius: 12, padding: 12, borderWidth: 1, borderColor: '#E2E8F0' },
  kvRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 6, borderBottomWidth: 1, borderColor: '#F1F5F9' },
  kvLabel: { fontSize: 12, color: '#475569', flex: 1 },
  kvInput: { width: 120, backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 8, padding: 8, fontSize: 13, color: '#0F172A', textAlign: 'right' },
  toggle: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, borderWidth: 1, borderColor: '#CBD5E1', backgroundColor: '#F8FAFC' },
  toggleOn: { backgroundColor: '#10B981', borderColor: '#10B981' },
  toggleText: { fontSize: 12, fontWeight: '800', color: '#475569' },
  saveBig: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', backgroundColor: '#003087', borderRadius: 10, padding: 14, marginTop: 14 },
  saveBigText: { color: '#FFF', fontWeight: '800', fontSize: 14 },
  simCard: { backgroundColor: '#F0FDF4', borderRadius: 12, padding: 12, marginTop: 10, borderWidth: 1, borderColor: '#86EFAC' },
  simHead: { fontSize: 14, fontWeight: '800', color: '#166534', marginBottom: 8 },
  simRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4 },
  simK: { fontSize: 12, color: '#475569' },
  simV: { fontSize: 12, fontWeight: '700', color: '#0F172A' },
  simNote: { fontSize: 11, color: '#64748B', marginTop: 8, fontStyle: 'italic' },
});
