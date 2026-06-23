/**
 * Admin → Payouts (Collaboration Epic Phase E).
 * Configure marketplace payout policy (min threshold, weekly schedule, platform
 * commission, RazorpayX account number), trigger a manual run, and review payouts.
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Switch,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';

const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

export default function AdminPayoutsScreen() {
  const router = useRouter();
  const [cfg, setCfg] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [payouts, setPayouts] = useState<any[]>([]);
  const [pending, setPending] = useState<any[]>([]);

  const load = useCallback(async () => {
    try {
      const [c, p] = await Promise.all([api.get('/admin/payouts/config'), api.get('/admin/payouts')]);
      setCfg(c.data); setPayouts(p.data?.payouts || []); setPending(p.data?.pending_balances || []);
    } catch { /* noop */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const update = (patch: any) => setCfg({ ...cfg, ...patch });

  const save = async () => {
    setSaving(true);
    try {
      const r = await api.put('/admin/payouts/config', {
        min_payout_inr: parseInt(String(cfg.min_payout_inr) || '0', 10),
        payout_weekday: cfg.payout_weekday,
        payout_hour_utc: parseInt(String(cfg.payout_hour_utc) || '0', 10),
        platform_commission_percent: parseInt(String(cfg.platform_commission_percent) || '0', 10),
        enabled: cfg.enabled,
        razorpayx_account_number: cfg.razorpayx_account_number || '',
      });
      setCfg(r.data); showAlert('Saved', 'Payout configuration updated.');
    } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Save failed'); }
    finally { setSaving(false); }
  };

  const runNow = async () => {
    showAlert('Run payouts now?', 'This processes all eligible sellers above the threshold immediately.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Run', onPress: async () => {
        setRunning(true);
        try {
          const r = await api.post('/admin/payouts/run-now');
          showAlert('Payout run complete', `Processed ${r.data.processed}, queued ${r.data.queued_pending}, skipped ${r.data.skipped}.\nRazorpayX live: ${r.data.razorpayx_live ? 'yes' : 'no'}`);
          load();
        } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Run failed'); }
        finally { setRunning(false); }
      } },
    ]);
  };

  if (loading || !cfg) return (
    <SafeAreaView style={styles.container} edges={['top']}><ActivityIndicator style={{ marginTop: 60 }} color="#16A34A" /></SafeAreaView>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={['#16A34A', '#15803D']} style={styles.header}>
        <TouchableOpacity style={styles.iconHdr} onPress={() => safeBack(router)}><Ionicons name="arrow-back" size={22} color="#FFF" /></TouchableOpacity>
        <Text style={styles.headerTitle}>Payouts</Text>
        <View style={{ width: 38 }} />
      </LinearGradient>

      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 50 }}>
        {/* RazorpayX status */}
        <View style={[styles.statusCard, { backgroundColor: cfg.razorpayx_active ? '#F0FDF4' : '#FFF7ED', borderColor: cfg.razorpayx_active ? '#BBF7D0' : '#FED7AA' }]}>
          <Ionicons name={cfg.razorpayx_active ? 'checkmark-circle' : 'alert-circle'} size={20} color={cfg.razorpayx_active ? '#16A34A' : '#EA580C'} />
          <Text style={[styles.statusText, { color: cfg.razorpayx_active ? '#166534' : '#9A3412' }]}>
            {cfg.razorpayx_active
              ? 'RazorpayX is active — payouts will be sent automatically.'
              : 'RazorpayX not activated. Payouts will be QUEUED (pending_manual) until you activate RazorpayX and set the account number below.'}
          </Text>
        </View>

        <Text style={styles.sectionTitle}>Configuration</Text>
        <View style={styles.card}>
          <View style={styles.rowBetween}>
            <Text style={styles.label}>Payouts enabled</Text>
            <Switch value={!!cfg.enabled} onValueChange={(v) => update({ enabled: v })} trackColor={{ true: '#16A34A' }} />
          </View>

          <Text style={styles.label}>Minimum payout threshold (₹)</Text>
          <TextInput style={styles.input} value={String(cfg.min_payout_inr)} onChangeText={(t) => update({ min_payout_inr: t.replace(/[^0-9]/g, '') })} keyboardType="numeric" />

          <Text style={styles.label}>Platform commission (%)</Text>
          <TextInput style={styles.input} value={String(cfg.platform_commission_percent)} onChangeText={(t) => update({ platform_commission_percent: t.replace(/[^0-9]/g, '') })} keyboardType="numeric" />

          <Text style={styles.label}>Payout day</Text>
          <View style={styles.weekdayWrap}>
            {WEEKDAYS.map((w, i) => (
              <TouchableOpacity key={w} style={[styles.weekChip, cfg.payout_weekday === i && styles.weekChipActive]} onPress={() => update({ payout_weekday: i })}>
                <Text style={[styles.weekChipText, cfg.payout_weekday === i && { color: '#FFF' }]}>{w.slice(0, 3)}</Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={styles.label}>Payout hour (UTC, 0-23)</Text>
          <TextInput style={styles.input} value={String(cfg.payout_hour_utc)} onChangeText={(t) => { const n = parseInt(t.replace(/[^0-9]/g, '') || '0', 10); update({ payout_hour_utc: Math.min(23, n) }); }} keyboardType="numeric" />

          <Text style={styles.label}>RazorpayX account number</Text>
          <TextInput style={styles.input} value={cfg.razorpayx_account_number || ''} onChangeText={(t) => update({ razorpayx_account_number: t })} placeholder="RazorpayX virtual account no." autoCapitalize="none" />

          <TouchableOpacity style={styles.saveBtn} onPress={save} disabled={saving}>
            {saving ? <ActivityIndicator color="#FFF" /> : <Text style={styles.saveBtnText}>Save configuration</Text>}
          </TouchableOpacity>
        </View>

        <TouchableOpacity style={styles.runBtn} onPress={runNow} disabled={running} testID="run-payouts-now">
          {running ? <ActivityIndicator color="#FFF" /> : <><Ionicons name="play" size={18} color="#FFF" /><Text style={styles.runBtnText}>Run payouts now</Text></>}
        </TouchableOpacity>

        {/* pending balances */}
        <Text style={styles.sectionTitle}>Pending balances ({pending.length})</Text>
        {pending.length === 0 ? <Text style={styles.empty}>No sellers with available balances.</Text> :
          pending.map((p) => (
            <View key={p.user_id} style={styles.row}>
              <Text style={styles.rowSub} numberOfLines={1}>{p.user_id}</Text>
              <Text style={styles.rowAmount}>₹{p.available_inr}</Text>
            </View>
          ))}

        {/* payouts */}
        <Text style={styles.sectionTitle}>Recent payouts ({payouts.length})</Text>
        {payouts.length === 0 ? <Text style={styles.empty}>No payouts yet.</Text> :
          payouts.map((p) => (
            <View key={p.payout_id} style={styles.row}>
              <View style={{ flex: 1 }}>
                <Text style={styles.rowTitle}>₹{p.amount_inr} · {p.method?.toUpperCase()}</Text>
                <Text style={styles.rowSub}>{new Date(p.created_at).toLocaleString()}</Text>
              </View>
              <Text style={[styles.statusTag, p.status === 'processing' && { color: '#0EA5E9' }, p.status === 'pending_manual' && { color: '#F59E0B' }, p.status === 'failed' && { color: '#EF4444' }]}>{p.status}</Text>
            </View>
          ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 10, paddingVertical: 14 },
  iconHdr: { width: 38, height: 38, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { flex: 1, fontSize: 18, fontWeight: '800', color: '#FFF', textAlign: 'center' },
  statusCard: { flexDirection: 'row', gap: 10, borderRadius: 12, padding: 12, borderWidth: 1, marginBottom: 16 },
  statusText: { flex: 1, fontSize: 12.5, lineHeight: 18 },
  sectionTitle: { fontSize: 15, fontWeight: '800', color: '#0F172A', marginBottom: 8, marginTop: 8 },
  card: { backgroundColor: '#FFF', borderRadius: 14, padding: 14, borderWidth: 1, borderColor: '#E2E8F0' },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  label: { fontSize: 12.5, fontWeight: '700', color: '#475569', marginBottom: 6, marginTop: 12 },
  input: { borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: '#0F172A', backgroundColor: '#FAFAFA' },
  weekdayWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  weekChip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8, backgroundColor: '#F1F5F9' },
  weekChipActive: { backgroundColor: '#16A34A' },
  weekChipText: { fontSize: 12, fontWeight: '700', color: '#475569' },
  saveBtn: { backgroundColor: '#16A34A', paddingVertical: 13, borderRadius: 10, alignItems: 'center', marginTop: 18 },
  saveBtnText: { color: '#FFF', fontWeight: '800', fontSize: 14 },
  runBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#0EA5E9', paddingVertical: 13, borderRadius: 12, marginTop: 14 },
  runBtnText: { color: '#FFF', fontWeight: '800', fontSize: 14 },
  empty: { fontSize: 13, color: '#94A3B8', marginBottom: 10 },
  row: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFF', borderRadius: 10, padding: 12, marginBottom: 6, borderWidth: 1, borderColor: '#EEF2F7' },
  rowTitle: { fontSize: 14, fontWeight: '700', color: '#0F172A' },
  rowSub: { fontSize: 11.5, color: '#64748B', flex: 1 },
  rowAmount: { fontSize: 14, fontWeight: '800', color: '#16A34A' },
  statusTag: { fontSize: 11.5, fontWeight: '700', color: '#64748B', textTransform: 'capitalize' },
});
