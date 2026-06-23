/**
 * Admin → Karma config (Collaboration Epic Phase F).
 * Configure how many Karma points each collaborative event awards.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput, ActivityIndicator, Switch } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';

const EVENT_LABEL: Record<string, string> = {
  contribution_accepted: 'Public-help contribution accepted',
  decision_cloned_free: 'Decision free-cloned',
  decision_cloned_paid: 'Decision paid-cloned',
  positive_rating: 'Positive rating (per star)',
  public_help_resolved: 'Public-help request resolved',
};

export default function AdminKarmaScreen() {
  const router = useRouter();
  const [cfg, setCfg] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try { const r = await api.get('/admin/karma/config'); setCfg(r.data); }
    catch { /* noop */ }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const save = async () => {
    setSaving(true);
    try {
      const points: Record<string, number> = {};
      Object.entries(cfg.points || {}).forEach(([k, v]) => { points[k] = parseInt(String(v) || '0', 10); });
      const r = await api.put('/admin/karma/config', { enabled: cfg.enabled, points });
      setCfg(r.data); showAlert('Saved', 'Karma configuration updated.');
    } catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Save failed'); }
    finally { setSaving(false); }
  };

  if (loading || !cfg) return (<SafeAreaView style={styles.container} edges={['top']}><ActivityIndicator style={{ marginTop: 60 }} color="#F59E0B" /></SafeAreaView>);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={['#F59E0B', '#D97706']} style={styles.header}>
        <TouchableOpacity style={styles.iconHdr} onPress={() => safeBack(router)}><Ionicons name="arrow-back" size={22} color="#FFF" /></TouchableOpacity>
        <Text style={styles.headerTitle}>Karma Config</Text>
        <View style={{ width: 38 }} />
      </LinearGradient>
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 50 }}>
        <View style={styles.card}>
          <View style={styles.rowBetween}>
            <Text style={styles.label}>Karma awards enabled</Text>
            <Switch value={!!cfg.enabled} onValueChange={(v) => setCfg({ ...cfg, enabled: v })} trackColor={{ true: '#F59E0B' }} />
          </View>
          <Text style={styles.hint}>Points awarded per event. Set 0 to disable a specific reward.</Text>
          {Object.keys(EVENT_LABEL).map((k) => (
            <View key={k} style={styles.pointRow}>
              <Text style={styles.pointLabel}>{EVENT_LABEL[k]}</Text>
              <TextInput
                style={styles.pointInput}
                value={String(cfg.points?.[k] ?? 0)}
                onChangeText={(t) => setCfg({ ...cfg, points: { ...cfg.points, [k]: t.replace(/[^0-9]/g, '') } })}
                keyboardType="numeric"
              />
            </View>
          ))}
          <TouchableOpacity style={styles.saveBtn} onPress={save} disabled={saving}>
            {saving ? <ActivityIndicator color="#FFF" /> : <Text style={styles.saveBtnText}>Save configuration</Text>}
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 10, paddingVertical: 14 },
  iconHdr: { width: 38, height: 38, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { flex: 1, fontSize: 18, fontWeight: '800', color: '#FFF', textAlign: 'center' },
  card: { backgroundColor: '#FFF', borderRadius: 14, padding: 16, borderWidth: 1, borderColor: '#E2E8F0' },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  label: { fontSize: 14, fontWeight: '700', color: '#0F172A' },
  hint: { fontSize: 12, color: '#64748B', marginTop: 8, marginBottom: 8 },
  pointRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  pointLabel: { fontSize: 13, color: '#334155', flex: 1, marginRight: 12 },
  pointInput: { width: 72, borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8, fontSize: 14, color: '#0F172A', backgroundColor: '#FAFAFA', textAlign: 'center' },
  saveBtn: { backgroundColor: '#F59E0B', paddingVertical: 13, borderRadius: 10, alignItems: 'center', marginTop: 18 },
  saveBtnText: { color: '#FFF', fontWeight: '800', fontSize: 14 },
});
