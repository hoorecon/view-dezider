/**
 * Admin · Module Free-Use Limits.
 * Grid of (tier × module) with a numeric input per cell. -1 = unlimited.
 * Seeded defaults on first load:
 *   free / guest / trial → solution_finder=2, pros_cons=2, my_dezider=2
 *   paid tiers → all -1 (unlimited)
 */
import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Platform, KeyboardAvoidingView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { useAuthStore } from '../../src/store/authStore';
import { safeBack } from '../../src/utils/navigation';

type Row = { tier: string; module: string; limit: number };

const MODULE_LABEL: Record<string, string> = {
  solution_finder: 'Solution Finder',
  pros_cons: 'Pros & Cons',
  my_dezider: 'MyDezider',
};

export default function AdminModuleLimitsScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const role = (user?.role || '').toLowerCase();
  const isAdmin = role === 'super_admin' || role === 'admin';

  const [rows, setRows] = useState<Row[]>([]);
  const [tiers, setTiers] = useState<string[]>([]);
  const [modules, setModules] = useState<string[]>([]);
  const [dirty, setDirty] = useState<Record<string, number>>({}); // key = `${tier}::${module}`
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/admin/module-limits');
      setRows(r.data?.rows || []);
      setTiers(r.data?.tiers || []);
      setModules(r.data?.modules || []);
      setDirty({});
    } catch (e: any) {
      showAlert('Load failed', e?.response?.data?.detail || 'Could not load limits.');
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { if (isAdmin) fetchData(); }, [isAdmin, fetchData]));

  const cellValue = (tier: string, module: string): number => {
    const k = `${tier}::${module}`;
    if (k in dirty) return dirty[k];
    const row = rows.find((r) => r.tier === tier && r.module === module);
    return row ? row.limit : -1;
  };

  const setCell = (tier: string, module: string, val: number) => {
    setDirty((prev) => ({ ...prev, [`${tier}::${module}`]: val }));
  };

  const save = async () => {
    const payload = Object.entries(dirty).map(([k, limit]) => {
      const [tier, module] = k.split('::');
      return { tier, module, limit: Number.isFinite(limit) ? limit : -1 };
    });
    if (payload.length === 0) { showAlert('Nothing to save', 'No changes.'); return; }
    setSaving(true);
    try {
      await api.put('/admin/module-limits', { rows: payload });
      showAlert('Saved', `${payload.length} row(s) updated.`);
      await fetchData();
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || 'Could not save.');
    } finally {
      setSaving(false);
    }
  };

  if (!isAdmin) return <SafeAreaView style={styles.container}><Text style={styles.gate}>Super-admin access only.</Text></SafeAreaView>;

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => safeBack(router, '/admin')} style={styles.backBtn}>
            <Ionicons name="chevron-back" size={22} color={COLORS.textPrimary} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Module Free-Use Limits</Text>
          <TouchableOpacity onPress={save} disabled={saving || Object.keys(dirty).length === 0} style={[styles.saveBtn, (saving || Object.keys(dirty).length === 0) && { opacity: 0.5 }]}>
            {saving ? <ActivityIndicator color={COLORS.white} /> : <Text style={styles.saveBtnText}>Save</Text>}
          </TouchableOpacity>
        </View>

        {loading ? <ActivityIndicator color={COLORS.primary} style={{ marginTop: 40 }} /> : (
          <ScrollView contentContainerStyle={styles.scroll}>
            <View style={styles.infoCard}>
              <Ionicons name="information-circle" size={18} color={COLORS.primary} />
              <Text style={styles.infoText}>
                Cap the number of times a user on each tier can <Text style={{ fontWeight: '700' }}>create records</Text> in{' '}
                <Text style={{ fontWeight: '700' }}>Solution Finder / Pros & Cons / MyDezider</Text>. All other modules
                are unlimited by design. Enter <Text style={{ fontWeight: '700' }}>-1</Text> to disable the cap
                (unlimited). Once a user reaches the cap they see an upgrade prompt on their next create attempt.
                {"\n\n"}Admins & Super-admins are exempt from all caps.
              </Text>
            </View>

            <ScrollView horizontal contentContainerStyle={{ paddingBottom: 8 }}>
              <View>
                {/* header row */}
                <View style={styles.hRow}>
                  <View style={[styles.cell, styles.hCellTier]}><Text style={styles.hText}>Tier</Text></View>
                  {modules.map((m) => (
                    <View key={m} style={[styles.cell, styles.hCell]}><Text style={styles.hText}>{MODULE_LABEL[m] || m}</Text></View>
                  ))}
                </View>
                {tiers.map((tier) => (
                  <View key={tier} style={styles.row}>
                    <View style={[styles.cell, styles.cellTier]}><Text style={styles.tierText}>{tier}</Text></View>
                    {modules.map((m) => {
                      const v = cellValue(tier, m);
                      const isDirty = `${tier}::${m}` in dirty;
                      return (
                        <View key={m} style={styles.cell}>
                          <TextInput
                            style={[styles.input, isDirty && styles.inputDirty, v < 0 && styles.inputUnlimited]}
                            keyboardType="numeric"
                            value={String(v)}
                            onChangeText={(t) => setCell(tier, m, parseInt(t || '0', 10))}
                          />
                          <Text style={styles.cellHint}>{v < 0 ? 'Unlimited' : `${v} / lifetime`}</Text>
                        </View>
                      );
                    })}
                  </View>
                ))}
              </View>
            </ScrollView>
          </ScrollView>
        )}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const CELL_W = 110;

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  gate: { fontSize: 14, color: COLORS.textMuted, textAlign: 'center', marginTop: 40 },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: COLORS.border, backgroundColor: COLORS.white },
  backBtn: { padding: 4 },
  headerTitle: { fontSize: 17, fontWeight: '800', color: COLORS.textPrimary, flex: 1, marginLeft: 8 },
  saveBtn: { backgroundColor: COLORS.primary, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 10 },
  saveBtnText: { color: COLORS.white, fontWeight: '700', fontSize: 13 },
  scroll: { padding: 12, paddingBottom: 40, maxWidth: 1100, width: '100%', alignSelf: 'center' },
  infoCard: { flexDirection: 'row', gap: 8, backgroundColor: '#EEF2FF', padding: 12, borderRadius: 12, marginBottom: 14 },
  infoText: { flex: 1, fontSize: 12, color: COLORS.textSecondary, lineHeight: 18 },
  hRow: { flexDirection: 'row', backgroundColor: COLORS.primary + '15', borderTopLeftRadius: 10, borderTopRightRadius: 10 },
  row: { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: COLORS.border, backgroundColor: COLORS.white },
  cell: { width: CELL_W, padding: 8, justifyContent: 'center', alignItems: 'center' },
  hCell: { width: CELL_W, padding: 10 },
  cellTier: { width: 140, alignItems: 'flex-start' },
  hCellTier: { width: 140, alignItems: 'flex-start' },
  hText: { fontSize: 11, fontWeight: '800', color: COLORS.primary, textAlign: 'center' },
  tierText: { fontSize: 12, fontWeight: '700', color: COLORS.textPrimary },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 6, width: 70, textAlign: 'center', fontSize: 13, color: COLORS.textPrimary, backgroundColor: COLORS.white },
  inputDirty: { borderColor: '#EAB308', backgroundColor: '#FEFCE8' },
  inputUnlimited: { color: '#059669', fontWeight: '700' },
  cellHint: { fontSize: 9, color: COLORS.textMuted, marginTop: 3 },
});
