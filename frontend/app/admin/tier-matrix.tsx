/**
 * /admin/tier-matrix  — 7-Chakra subscription-tier matrix editor.
 *
 * Rows  = ACM modules (32) + expandable feature children (89 features total)
 * Cols  = 7 chakra tiers (Root → Crown)
 * Cells = Y/N toggle. Admin taps to flip; cascade rules applied server-side.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  TextInput, Modal, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { COLORS } from '../../src/constants/colors';
import { showAlert } from '../../src/utils/alert';

interface Tier { key: string; order: number; chakra_sanskrit: string; label: string; aspiration: string; color: string; icon: string; monthly_price_inr: number }
interface FeatureRow { feature_id: string; feature_name: string; tiers: Record<string, boolean> }
interface ModuleRow { module_id: string; module_name: string; module_icon?: string; module_order?: number; tiers: Record<string, boolean>; features: FeatureRow[] }

export default function TierMatrixScreen() {
  const router = useRouter();
  const [tiers, setTiers] = useState<Tier[]>([]);
  const [rows, setRows] = useState<ModuleRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null); // cell key being saved
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState('');
  const [showLegend, setShowLegend] = useState(false);

  const load = useCallback(async () => {
    try { setLoading(true);
      const r = await api.get('/admin/tier-matrix');
      setTiers(r.data.tiers || []);
      setRows(r.data.rows || []);
    } catch (e: any) { showAlert('Load failed', e?.response?.data?.detail || e.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const toggleCell = async (module_id: string, feature_id: string | null, tier_key: string, current: boolean) => {
    const cellKey = `${module_id}:${feature_id || '*'}:${tier_key}`;
    try { setSaving(cellKey);
      await api.put('/admin/tier-matrix/cell', {
        module_id, feature_id, tier_key, allowed: !current,
      });
      load();  // re-fetch (cheap) so we always show the cascade result
    } catch (e: any) { showAlert('Toggle failed', e?.response?.data?.detail || e.message); }
    finally { setSaving(null); }
  };

  const toggleExpand = (module_id: string) => {
    const n = new Set(expanded);
    n.has(module_id) ? n.delete(module_id) : n.add(module_id);
    setExpanded(n);
  };

  const reset = async () => {
    try {
      await api.post('/admin/tier-matrix/reset');
      showAlert('Reset', 'Matrix wiped and re-seeded with smart defaults.');
      load();
    } catch (e: any) { showAlert('Reset failed', e?.response?.data?.detail || e.message); }
  };

  const filteredRows = useMemo(() => {
    if (!filter.trim()) return rows;
    const q = filter.trim().toLowerCase();
    return rows.filter(r =>
      r.module_id.toLowerCase().includes(q)
      || (r.module_name || '').toLowerCase().includes(q)
      || r.features.some(f => (f.feature_name || '').toLowerCase().includes(q) || f.feature_id.toLowerCase().includes(q))
    );
  }, [rows, filter]);

  if (loading) return <SafeAreaView style={s.container}><View style={s.center}><ActivityIndicator color={COLORS.primary} /></View></SafeAreaView>;

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()}><Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} /></TouchableOpacity>
        <View style={{ flex: 1, marginHorizontal: 12 }}>
          <Text style={s.title}>Tier Matrix · 7 Chakras</Text>
          <Text style={s.subtitle}>Modules × tiers · cascade-up smart toggle</Text>
        </View>
        <TouchableOpacity onPress={() => setShowLegend(true)}><Ionicons name="information-circle" size={22} color={COLORS.primary} /></TouchableOpacity>
      </View>

      <View style={s.toolbar}>
        <View style={s.searchRow}>
          <Ionicons name="search" size={14} color={COLORS.textMuted} />
          <TextInput
            style={s.searchInput}
            placeholder="Filter modules / features…"
            placeholderTextColor={COLORS.textMuted}
            value={filter} onChangeText={setFilter}
          />
          {filter ? <TouchableOpacity onPress={() => setFilter('')}><Ionicons name="close-circle" size={14} color={COLORS.textMuted} /></TouchableOpacity> : null}
        </View>
        <TouchableOpacity onPress={reset} testID="tier-reset" style={s.resetBtn}>
          <Ionicons name="refresh" size={12} color="#DC2626" /><Text style={s.resetBtnText}>Reset</Text>
        </TouchableOpacity>
      </View>

      <ScrollView horizontal>
        <View>
          {/* Tier header */}
          <View style={s.headerRow}>
            <View style={[s.modCol, { backgroundColor: '#F3F4F6' }]}>
              <Text style={s.headerCellText}>Module / Feature</Text>
            </View>
            {tiers.map(t => (
              <View key={t.key} style={[s.tierColHeader, { backgroundColor: t.color + '22', borderTopColor: t.color, borderTopWidth: 3 }]}>
                <Ionicons name={t.icon as any} size={12} color={t.color} />
                <Text style={[s.tierLabel, { color: t.color }]} numberOfLines={1}>{t.label}</Text>
                <Text style={s.tierAspiration} numberOfLines={1}>{t.aspiration.replace(' Startup', '').replace(' Stage', '')}</Text>
                <Text style={s.tierPrice}>{t.monthly_price_inr === 0 ? 'Free' : `₹${(t.monthly_price_inr / 1000).toFixed(t.monthly_price_inr % 1000 === 0 ? 0 : 1)}k`}</Text>
              </View>
            ))}
          </View>

          {/* Module rows */}
          {filteredRows.map(row => {
            const isOpen = expanded.has(row.module_id);
            return (
              <View key={row.module_id}>
                {/* Module-level row */}
                <View style={s.bodyRow}>
                  <TouchableOpacity onPress={() => toggleExpand(row.module_id)} style={[s.modCol, { backgroundColor: '#FAFAFA' }]} testID={`tm-mod-${row.module_id}`}>
                    <Ionicons name={isOpen ? 'chevron-down' : 'chevron-forward'} size={12} color={COLORS.textMuted} />
                    <View style={{ flex: 1 }}>
                      <Text style={s.moduleName} numberOfLines={1}>{row.module_name || row.module_id}</Text>
                      <Text style={s.moduleId} numberOfLines={1}>{row.features.length} features</Text>
                    </View>
                  </TouchableOpacity>
                  {tiers.map(t => {
                    const allowed = row.tiers[t.key];
                    const cellKey = `${row.module_id}:*:${t.key}`;
                    return (
                      <TouchableOpacity
                        key={t.key}
                        testID={`tm-cell-${row.module_id}-${t.key}`}
                        disabled={saving === cellKey}
                        onPress={() => toggleCell(row.module_id, null, t.key, allowed)}
                        style={[s.tierCell, { backgroundColor: allowed ? (t.color + '22') : '#F3F4F6' }]}
                      >
                        {saving === cellKey ? <ActivityIndicator size="small" color={t.color} /> : (
                          <Ionicons name={allowed ? 'checkmark-circle' : 'close-circle'} size={20} color={allowed ? t.color : COLORS.textMuted} />
                        )}
                      </TouchableOpacity>
                    );
                  })}
                </View>

                {/* Feature rows */}
                {isOpen && row.features.map(f => (
                  <View key={f.feature_id} style={s.bodyRow}>
                    <View style={[s.modCol, { paddingLeft: 28, backgroundColor: '#FFF' }]}>
                      <Ionicons name="ellipse" size={6} color={COLORS.textMuted} />
                      <View style={{ flex: 1 }}>
                        <Text style={s.featureName} numberOfLines={2}>{f.feature_name || f.feature_id}</Text>
                        <Text style={s.featureId} numberOfLines={1}>{f.feature_id}</Text>
                      </View>
                    </View>
                    {tiers.map(t => {
                      const allowed = f.tiers[t.key];
                      const moduleAllowed = row.tiers[t.key];
                      const cellKey = `${row.module_id}:${f.feature_id}:${t.key}`;
                      const dominated = !moduleAllowed; // module N → feature forced N
                      return (
                        <TouchableOpacity
                          key={t.key}
                          testID={`tm-feat-${row.module_id}-${f.feature_id}-${t.key}`}
                          disabled={saving === cellKey || dominated}
                          onPress={() => toggleCell(row.module_id, f.feature_id, t.key, allowed)}
                          style={[
                            s.tierCell,
                            { backgroundColor: allowed ? (t.color + '15') : '#FAFAFA' },
                            dominated && { opacity: 0.35 },
                          ]}
                        >
                          {saving === cellKey ? <ActivityIndicator size="small" color={t.color} /> : (
                            <Ionicons
                              name={allowed ? 'checkmark' : (dominated ? 'lock-closed' : 'close')}
                              size={dominated ? 12 : 14}
                              color={allowed ? t.color : COLORS.textMuted}
                            />
                          )}
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                ))}
              </View>
            );
          })}
        </View>
      </ScrollView>

      <Modal visible={showLegend} transparent animationType="slide" onRequestClose={() => setShowLegend(false)}>
        <View style={s.overlay}>
          <View style={s.sheet}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <Text style={s.sheetTitle}>How tier toggling works</Text>
              <TouchableOpacity onPress={() => setShowLegend(false)}><Ionicons name="close" size={22} color={COLORS.textPrimary} /></TouchableOpacity>
            </View>
            <ScrollView style={{ maxHeight: 460 }}>
              <Text style={s.legendH}>Q1 — Cascade rule</Text>
              <Text style={s.legendBody}>When you toggle a cell ON, the same cell is also enabled at all higher tiers automatically. Toggling OFF only affects that one cell — your overrides at higher tiers are preserved.</Text>

              <Text style={s.legendH}>Q2 — Module dominates</Text>
              <Text style={s.legendBody}>If a module is OFF at a tier, all its features are forced OFF at that tier (locked icon 🔒). To grant a feature, the parent module must be ON. Toggling a feature ON when the parent is OFF will auto-enable the parent.</Text>

              <Text style={s.legendH}>Q3 — Smart-seed defaults</Text>
              <Text style={s.legendBody}>Initial fill is based on aspirational fit:</Text>
              <Text style={s.legendBody}>• Root (Freelancer): core decision tools, LDC, AALA, Daily Tracker{'\n'}• Sacral (Solopreneur): + AI assistant, goals, conflict breaker{'\n'}• Solar Plexus (Early Founder): + CTT, Time Dezider full, calendar sync{'\n'}• Heart (Growth Founder): + Public Pulse, Solution Matrix, ReviewNet{'\n'}• Throat (Successful Founder): + ExpertNet, advanced AI, CLD{'\n'}• Third Eye (Unicorn): + webinar host, multi-org, API access{'\n'}• Crown (Fortune): + whitelabel, govt portal, priority support</Text>

              <TouchableOpacity onPress={reset} style={s.resetBigBtn}>
                <Ionicons name="refresh" size={14} color="#FFF" />
                <Text style={s.resetBigBtnText}>Reset to smart-seed defaults</Text>
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingVertical: 10, backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  title: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  toolbar: { flexDirection: 'row', gap: 8, paddingHorizontal: 12, paddingVertical: 8, backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider, alignItems: 'center' },
  searchRow: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#F3F4F6', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6 },
  searchInput: { flex: 1, fontSize: 12, color: COLORS.textPrimary, padding: 0 },
  resetBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 6, borderWidth: 1, borderColor: '#FCA5A5', backgroundColor: '#FEF2F2' },
  resetBtnText: { fontSize: 11, color: '#DC2626', fontWeight: '700' },

  headerRow: { flexDirection: 'row', borderBottomWidth: 2, borderBottomColor: COLORS.border },
  bodyRow: { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  modCol: { width: 200, paddingHorizontal: 10, paddingVertical: 10, flexDirection: 'row', alignItems: 'center', gap: 6, borderRightWidth: 1, borderRightColor: COLORS.divider },
  headerCellText: { fontSize: 11, fontWeight: '700', color: COLORS.textPrimary, textTransform: 'uppercase', letterSpacing: 0.5 },

  tierColHeader: { width: 88, padding: 6, alignItems: 'center', borderRightWidth: 1, borderRightColor: COLORS.divider },
  tierLabel: { fontSize: 11, fontWeight: '700', marginTop: 2 },
  tierAspiration: { fontSize: 8, color: COLORS.textMuted, textAlign: 'center', marginTop: 1 },
  tierPrice: { fontSize: 9, color: COLORS.textPrimary, fontWeight: '700', marginTop: 2 },

  tierCell: { width: 88, height: 44, alignItems: 'center', justifyContent: 'center', borderRightWidth: 1, borderRightColor: COLORS.divider },
  moduleName: { fontSize: 12, fontWeight: '700', color: COLORS.textPrimary },
  moduleId: { fontSize: 9, color: COLORS.textMuted, marginTop: 1 },
  featureName: { fontSize: 11, color: COLORS.textPrimary },
  featureId: { fontSize: 9, color: COLORS.textMuted, marginTop: 1 },

  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: COLORS.white, borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 18, maxHeight: '80%' },
  sheetTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  legendH: { fontSize: 12, fontWeight: '700', color: COLORS.primary, marginTop: 14, textTransform: 'uppercase', letterSpacing: 0.5 },
  legendBody: { fontSize: 12, color: COLORS.textSecondary, lineHeight: 18, marginTop: 6 },
  resetBigBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#DC2626', paddingVertical: 12, borderRadius: 8, marginTop: 18 },
  resetBigBtnText: { color: '#FFF', fontSize: 13, fontWeight: '700' },
});
