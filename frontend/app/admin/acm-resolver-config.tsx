/**
 * Admin · ACM v2 Resolver Configuration
 * Tunes the 5-axis user-type resolver:
 *   - Trial day defaults (starter_trial / pro_trial / premium_trial)
 *   - Plan aliases (enterprise→premium, basic→starter)
 *   - On-demand thresholds (retail/bulk INR minimums)
 *   - Auto-convert + payment-required-for-trial flags
 */
import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, TextInput, ActivityIndicator, Switch } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { showAlert } from '../../src/utils/alert';
import api from '../../src/utils/api';
import { safeBack } from '../../src/utils/navigation';

export default function AdminACMResolverConfig() {
  const router = useRouter();
  const [cfg, setCfg] = useState<any>({});
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setBusy(true);
    try {
      const { data } = await api.get('/acm-v2/resolver-config');
      setCfg(data?.config || {});
    } catch (e: any) {
      showAlert('Load failed', e?.response?.data?.detail || e.message);
    } finally { setBusy(false); }
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    setSaving(true);
    try {
      await api.put('/acm-v2/resolver-config', { config: cfg });
      showAlert('Saved', 'Resolver config updated. Effective immediately.');
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || e.message);
    } finally { setSaving(false); }
  };

  const setTrialDay = (k: string, v: string) => {
    const num = Math.max(0, parseInt(v || '0', 10) || 0);
    setCfg((p: any) => ({ ...p, trial_days: { ...(p.trial_days || {}), [k]: num } }));
  };
  const setAlias = (legacy: string, target: string) => {
    setCfg((p: any) => ({ ...p, plan_alias: { ...(p.plan_alias || {}), [legacy]: target } }));
  };
  const setNum = (k: string, v: string) => {
    setCfg((p: any) => ({ ...p, on_demand_thresholds: { ...(p.on_demand_thresholds || {}), [k]: Number(v || 0) } }));
  };

  return (
    <SafeAreaView style={s.wrap} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={s.backBtn}><Ionicons name="arrow-back" size={22} color="#FFF" /></TouchableOpacity>
        <Text style={s.title}>ACM Resolver · Config</Text>
        <Text style={s.subtitle}>5-axis user-type resolution tuning</Text>
      </View>
      {busy ? <ActivityIndicator style={{ marginTop: 40 }} /> : (
      <ScrollView contentContainerStyle={{ padding: 16 }}>
        <View style={s.card}>
          <Text style={s.cardTitle}>Trial Day Defaults</Text>
          <Text style={s.hint}>Days a user stays in each trial bucket before being auto-downgraded to free.</Text>
          {['starter_trial', 'pro_trial', 'premium_trial'].map(k => (
            <View key={k} style={s.row}>
              <Text style={s.rowLabel}>{k}</Text>
              <TextInput style={s.num} keyboardType="numeric" value={String(cfg?.trial_days?.[k] ?? '')} onChangeText={(v) => setTrialDay(k, v)} placeholder="days" />
            </View>
          ))}
        </View>

        <View style={s.card}>
          <Text style={s.cardTitle}>Legacy Plan Aliases</Text>
          <Text style={s.hint}>Map old plan slugs (Razorpay → ACM). Webhooks use these.</Text>
          {Object.entries(cfg?.plan_alias || {}).map(([legacy, target]: any) => (
            <View key={legacy} style={s.row}>
              <Text style={s.rowLabel}>{legacy} →</Text>
              <TextInput style={s.txt} value={target} onChangeText={(v) => setAlias(legacy, v)} />
            </View>
          ))}
        </View>

        <View style={s.card}>
          <Text style={s.cardTitle}>On-Demand Thresholds (INR)</Text>
          <View style={s.row}><Text style={s.rowLabel}>Retail min</Text><TextInput style={s.num} keyboardType="numeric" value={String(cfg?.on_demand_thresholds?.retail_min_inr ?? '')} onChangeText={(v) => setNum('retail_min_inr', v)} /></View>
          <View style={s.row}><Text style={s.rowLabel}>Bulk min</Text><TextInput style={s.num} keyboardType="numeric" value={String(cfg?.on_demand_thresholds?.bulk_min_inr ?? '')} onChangeText={(v) => setNum('bulk_min_inr', v)} /></View>
        </View>

        <View style={s.card}>
          <Text style={s.cardTitle}>Flags</Text>
          <View style={s.row}><Text style={s.rowLabel}>Auto-convert default</Text><Switch value={!!cfg.auto_convert_default} onValueChange={(v) => setCfg((p:any) => ({ ...p, auto_convert_default: v }))} /></View>
          <View style={s.row}><Text style={s.rowLabel}>Require payment for trial</Text><Switch value={!!cfg.require_payment_for_trial} onValueChange={(v) => setCfg((p:any) => ({ ...p, require_payment_for_trial: v }))} /></View>
          <View style={s.row}><Text style={s.rowLabel}>Fallback to free on expiry</Text><Switch value={!!cfg.fallback_to_free_on_expiry} onValueChange={(v) => setCfg((p:any) => ({ ...p, fallback_to_free_on_expiry: v }))} /></View>
        </View>

        <TouchableOpacity style={[s.saveBtn, saving && { opacity: 0.5 }]} disabled={saving} onPress={save}>
          {saving ? <ActivityIndicator color="#FFF" /> : <><Ionicons name="save" size={18} color="#FFF" /><Text style={s.saveBtnText}>Save Configuration</Text></>}
        </TouchableOpacity>
      </ScrollView>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: '#0B1220' },
  header: { paddingHorizontal: 16, paddingVertical: 14, backgroundColor: '#111B2F', borderBottomColor: '#1F2A44', borderBottomWidth: 1, flexDirection: 'row', alignItems: 'center', gap: 12 },
  backBtn: { padding: 6 },
  title: { color: '#FFF', fontSize: 18, fontWeight: '700' },
  subtitle: { color: '#8A95B0', fontSize: 12, marginTop: 2, flex: 1 },
  card: { backgroundColor: '#111B2F', padding: 14, borderRadius: 12, marginBottom: 14, borderColor: '#1F2A44', borderWidth: 1 },
  cardTitle: { color: '#FFF', fontWeight: '700', marginBottom: 4 },
  hint: { color: '#8A95B0', fontSize: 12, marginBottom: 10 },
  row: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8, gap: 12 },
  rowLabel: { color: '#CED4E5', flex: 1, fontSize: 13 },
  num: { width: 90, backgroundColor: '#0B1220', borderColor: '#1F2A44', borderWidth: 1, color: '#FFF', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8 },
  txt: { flex: 1, backgroundColor: '#0B1220', borderColor: '#1F2A44', borderWidth: 1, color: '#FFF', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8 },
  saveBtn: { backgroundColor: '#5B7CFA', flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 8, padding: 14, borderRadius: 12, marginTop: 8 },
  saveBtnText: { color: '#FFF', fontWeight: '700', fontSize: 15 },
});
