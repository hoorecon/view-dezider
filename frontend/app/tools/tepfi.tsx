import React, { useState, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, Alert, ActivityIndicator, Dimensions, Modal, TextInput,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import Slider from '@react-native-community/slider';
import { COLORS } from '../../src/constants/colors';
import { LIFE_AREAS as CATALOG_LIFE_AREAS } from '../../src/constants/lifeAreas';
import api from '../../src/utils/api';
import { safeBack } from '../../src/utils/navigation';

const { width: SCREEN_W } = Dimensions.get('window');

const DIMENSIONS = [
  { id: 'time', name: 'Time', icon: 'time', color: '#3B82F6' },
  { id: 'effort', name: 'Effort', icon: 'flash', color: '#F59E0B' },
  { id: 'people', name: 'People', icon: 'people', color: '#10B981' },
  { id: 'finance', name: 'Finance', icon: 'cash', color: '#8B5CF6' },
  { id: 'infrastructure', name: 'Infrastructure', icon: 'construct', color: '#EF4444' },
];

const LAYERS = [
  { id: 'self', name: 'Self', icon: 'person', color: '#06B6D4' },
  { id: 'micro', name: 'Micro', icon: 'people-circle', color: '#F97316' },
  { id: 'macro', name: 'Macro', icon: 'globe', color: '#8B5CF6' },
];

// Canonical L0 life areas — single source of truth from Catalog Manager.
// Visible at-a-glance via 2-row flex wrap (no horizontal scroll).
const LIFE_AREAS = CATALOG_LIFE_AREAS.map(a => ({ id: a.id, name: a.short, icon: a.icon }));

function getScoreColor(score: number): string {
  if (score >= 8) return '#10B981';
  if (score >= 6) return '#3B82F6';
  if (score >= 4) return '#F59E0B';
  if (score >= 2) return '#F97316';
  return '#EF4444';
}

export default function TEPFIScreen() {
  const router = useRouter();
  const [entries, setEntries] = useState<any[]>([]);
  const [dashboard, setDashboard] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedArea, setSelectedArea] = useState('');
  const [viewMode, setViewMode] = useState<'matrix' | 'list'>('matrix');

  // Per-cell override modal state. Each override is keyed by
  // (scope, axis, dim_or_subkey). Scope = 'all' for overall life, or the
  // selected life-area id. Auto-computed cell value is shown as a
  // greyed-out reference beneath the slider when the user overrides.
  const [overrideModal, setOverrideModal] = useState<{
    visible: boolean;
    dimId: string;
    layerId: string;
    auto: number;
    score: number;
    note: string;
    overridden: boolean;
  }>({ visible: false, dimId: '', layerId: '', auto: 0, score: 0, note: '', overridden: false });

  const scope = selectedArea || 'all';

  const fetchData = async () => {
    try {
      const params = selectedArea ? `?life_area=${selectedArea}` : '';
      const [entriesRes, dashRes] = await Promise.all([
        api.get(`/tepfi/entries${params}`),
        api.get(`/tepfi/dashboard${params}`),
      ]);
      setEntries(entriesRes.data || []);
      setDashboard(dashRes.data);
    } catch (e) { console.error('TEPFI fetch error:', e); }
    finally { setLoading(false); }
  };

  useFocusEffect(useCallback(() => { setLoading(true); fetchData(); }, [selectedArea]));
  const onRefresh = async () => { setRefreshing(true); await fetchData(); setRefreshing(false); };

  const handleDelete = (id: string) => {
    showAlert('Delete', 'Delete this TEPFI assessment?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await api.delete(`/tepfi/entries/${id}`); fetchData(); }
        catch (e) { showAlert('Error', 'Failed to delete'); }
      }},
    ]);
  };

  const openOverride = (dimId: string, layerId: string) => {
    const cell = dashboard?.avg_matrix?.[dimId]?.[layerId];
    // Backend may return either a number (legacy) or an enriched object
    // {auto, score, overridden, note}. Normalize both shapes here.
    const auto = typeof cell === 'object' ? Number(cell?.auto || 0) : Number(cell || 0);
    const score = typeof cell === 'object' ? Number(cell?.score || 0) : Number(cell || 0);
    const overridden = typeof cell === 'object' ? !!cell?.overridden : false;
    const note = typeof cell === 'object' ? String(cell?.note || '') : '';
    setOverrideModal({ visible: true, dimId, layerId, auto, score, note, overridden });
  };

  const saveOverride = async () => {
    const { dimId, layerId, score, note } = overrideModal;
    try {
      await api.put(`/tepfi/overrides/${scope}`, {
        cell_key: `${dimId}_${layerId}`,
        score: Math.round(score),
        note: note.trim(),
      });
      setOverrideModal(m => ({ ...m, visible: false }));
      fetchData();
    } catch (e) { showAlert('Save failed', 'Could not save override'); }
  };

  const clearOverride = async () => {
    const { dimId, layerId } = overrideModal;
    try {
      await api.delete(`/tepfi/overrides/${scope}/${dimId}_${layerId}`);
      setOverrideModal(m => ({ ...m, visible: false }));
      fetchData();
    } catch (e) { showAlert('Reset failed', 'Could not reset cell'); }
  };

  const renderMatrixOverview = () => {
    if (!dashboard?.avg_matrix) return null;
    const m = dashboard.avg_matrix;
    return (
      <View style={s.matrixContainer}>
        <Text style={s.matrixTitle}>
          {selectedArea
            ? `Avg Scores · ${LIFE_AREAS.find(a => a.id === selectedArea)?.name || ''}`
            : 'Avg Scores · Overall Life'}
        </Text>
        <Text style={s.matrixHint}>Tap any cell to override the computed average.</Text>
        {/* Header row */}
        <View style={s.matrixRow}>
          <View style={[s.matrixCell, s.matrixCorner]}>
            <Text style={s.matrixCornerText}>TEPFI</Text>
          </View>
          {LAYERS.map(l => (
            <View key={l.id} style={[s.matrixCell, s.matrixHeader]}>
              <Ionicons name={l.icon as any} size={14} color={l.color} />
              <Text style={[s.matrixHeaderText, { color: l.color }]}>{l.name}</Text>
            </View>
          ))}
        </View>
        {/* Data rows */}
        {DIMENSIONS.map(dim => (
          <View key={dim.id} style={s.matrixRow}>
            <View style={[s.matrixCell, s.matrixRowHeader]}>
              <Ionicons name={dim.icon as any} size={14} color={dim.color} />
              <Text style={[s.matrixRowHeaderText, { color: dim.color }]}>{dim.name}</Text>
            </View>
            {LAYERS.map(l => {
              const cell = m[dim.id]?.[l.id];
              const score = typeof cell === 'object' ? Number(cell?.score || 0) : Number(cell || 0);
              const overridden = typeof cell === 'object' ? !!cell?.overridden : false;
              return (
                <TouchableOpacity
                  key={l.id}
                  style={[s.matrixCell, s.matrixData]}
                  onPress={() => openOverride(dim.id, l.id)}
                  testID={`avg-cell-${dim.id}-${l.id}`}>
                  <View style={[s.scoreCircle, { backgroundColor: getScoreColor(score) + '20', borderColor: getScoreColor(score) }]}>
                    <Text style={[s.scoreText, { color: getScoreColor(score) }]}>{score}</Text>
                  </View>
                  {overridden && (
                    <View style={s.overridePill} testID={`override-pill-${dim.id}-${l.id}`}>
                      <Text style={s.overridePillText}>OVR</Text>
                    </View>
                  )}
                </TouchableOpacity>
              );
            })}
          </View>
        ))}
      </View>
    );
  };

  const renderEntryCard = (entry: any) => {
    const areaInfo = LIFE_AREAS.find(a => a.id === entry.life_area);
    const matrix = entry.matrix || {};
    const totalScore = DIMENSIONS.reduce((sum, dim) => {
      return sum + LAYERS.reduce((lSum, l) => lSum + (matrix[dim.id]?.[l.id]?.score || 0), 0);
    }, 0);
    const maxScore = DIMENSIONS.length * LAYERS.length * 10;
    const pct = Math.round((totalScore / maxScore) * 100);

    return (
      <TouchableOpacity
        key={entry.entry_id}
        style={s.entryCard}
        onPress={() => router.push({ pathname: '/tools/tepfi-entry', params: { id: entry.entry_id } })}
      >
        <View style={s.entryHeader}>
          {areaInfo && (
            <View style={s.areaPill}>
              <Ionicons name={areaInfo.icon as any} size={12} color={COLORS.primary} />
              <Text style={s.areaPillText}>{areaInfo.name}</Text>
            </View>
          )}
          <View style={[s.statusPill, { backgroundColor: entry.status === 'active' ? '#10B98115' : '#6B728015' }]}>
            <Text style={[s.statusText, { color: entry.status === 'active' ? '#10B981' : '#6B7280' }]}>
              {entry.status?.toUpperCase()}
            </Text>
          </View>
          <TouchableOpacity onPress={() => handleDelete(entry.entry_id)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
            <Ionicons name="trash-outline" size={16} color={COLORS.textMuted} />
          </TouchableOpacity>
        </View>
        <Text style={s.entryTitle} numberOfLines={2}>{entry.title || 'Untitled Assessment'}</Text>

        {/* Mini matrix */}
        <View style={s.miniMatrix}>
          {DIMENSIONS.map(dim => {
            const dimData = matrix[dim.id] || {};
            return (
              <View key={dim.id} style={s.miniRow}>
                <View style={s.miniLabel}>
                  <Ionicons name={dim.icon as any} size={10} color={dim.color} />
                </View>
                {LAYERS.map(l => {
                  const score = dimData[l.id]?.score || 0;
                  return (
                    <View key={l.id} style={[s.miniCell, { backgroundColor: score ? getScoreColor(score) + '25' : '#F3F4F6' }]}>
                      <Text style={[s.miniScore, { color: score ? getScoreColor(score) : '#D1D5DB' }]}>
                        {score || '-'}
                      </Text>
                    </View>
                  );
                })}
              </View>
            );
          })}
        </View>

        <View style={s.entryFooter}>
          <View style={s.scoreBar}>
            <View style={[s.scoreBarFill, { width: `${pct}%`, backgroundColor: getScoreColor(totalScore / (DIMENSIONS.length * LAYERS.length)) }]} />
          </View>
          <Text style={s.scorePct}>{pct}%</Text>
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <LinearGradient colors={['#7C3AED', '#A855F7']} style={s.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.headerTitle}>Capabilities & Resources Index</Text>
          <Text style={s.headerSub}>
            {dashboard?.total_entries || 0} assessments | Time • Effort • People • Finance • Infra
          </Text>
        </View>
        <TouchableOpacity onPress={() => router.push({ pathname: '/cld/editor', params: { module_type: 'tepfi' } } as any)} style={s.addBtn}>
          <Ionicons name="git-network" size={20} color="#FFF" />
        </TouchableOpacity>
        <TouchableOpacity onPress={() => router.push('/tools/tepfi-entry')} style={s.addBtn}>
          <Ionicons name="add" size={22} color="#FFF" />
        </TouchableOpacity>
      </LinearGradient>

      {/* View toggle */}
      <View style={s.viewRow}>
        {([{ key: 'matrix', icon: 'grid', label: 'Matrix' }, { key: 'list', icon: 'list', label: 'Entries' }] as const).map(v => (
          <TouchableOpacity key={v.key} style={[s.viewToggle, viewMode === v.key && s.viewActive]} onPress={() => setViewMode(v.key)}>
            <Ionicons name={v.icon as any} size={14} color={viewMode === v.key ? '#FFF' : COLORS.textMuted} />
            <Text style={[s.viewText, viewMode === v.key && { color: '#FFF' }]}>{v.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Life area filter — flex-wrap (2 rows on phones) so all 10 areas
          are visible at a glance without horizontal scrolling. */}
      <View style={s.filterRow}>
        <TouchableOpacity style={[s.filterChip, !selectedArea && s.filterActive]} onPress={() => setSelectedArea('')}>
          <Text style={[s.filterText, !selectedArea && { color: '#FFF' }]}>All</Text>
        </TouchableOpacity>
        {LIFE_AREAS.map(a => (
          <TouchableOpacity key={a.id} style={[s.filterChip, selectedArea === a.id && s.filterActive]} onPress={() => setSelectedArea(selectedArea === a.id ? '' : a.id)}>
            <Ionicons name={a.icon as any} size={11} color={selectedArea === a.id ? '#FFF' : COLORS.textMuted} />
            <Text style={[s.filterText, selectedArea === a.id && { color: '#FFF' }]}>{a.name}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <ActivityIndicator size="large" color="#7C3AED" />
        </View>
      ) : (
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ padding: 16, paddingBottom: 32 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          {viewMode === 'matrix' && renderMatrixOverview()}

          {entries.length === 0 ? (
            <View style={s.empty}>
              <View style={s.emptyIcon}>
                <Ionicons name="cube-outline" size={48} color={COLORS.textMuted} />
              </View>
              <Text style={s.emptyTitle}>No Assessments Yet</Text>
              <Text style={s.emptySub}>
                Track your Capabilities & Resources across Time, Effort, People, Finance & Infrastructure
              </Text>
              <TouchableOpacity style={s.emptyBtn} onPress={() => router.push('/tools/tepfi-entry')}>
                <Ionicons name="add-circle" size={18} color="#FFF" />
                <Text style={s.emptyBtnText}>New Assessment</Text>
              </TouchableOpacity>
            </View>
          ) : (
            entries.map(renderEntryCard)
          )}
        </ScrollView>
      )}

      {/* Override modal — slider-based per-cell editor (axis × dim × scope).
          Slider is 0–10 integers; displays "N/10 · M%" for the SI 25-45
          South-India user (school marks-friendly + % capability framing). */}
      <Modal
        visible={overrideModal.visible}
        transparent
        animationType="fade"
        onRequestClose={() => setOverrideModal(m => ({ ...m, visible: false }))}>
        <View style={s.modalBackdrop}>
          <View style={s.modalCard}>
            <View style={s.modalHead}>
              <Text style={s.modalTitle}>Override cell</Text>
              <TouchableOpacity onPress={() => setOverrideModal(m => ({ ...m, visible: false }))}>
                <Ionicons name="close" size={20} color={COLORS.textMuted} />
              </TouchableOpacity>
            </View>
            <Text style={s.modalSub}>
              {(DIMENSIONS.find(d => d.id === overrideModal.dimId)?.name) || ''}
              {' · '}
              {(LAYERS.find(l => l.id === overrideModal.layerId)?.name) || ''}
              {' · Scope: '}
              {scope === 'all' ? 'Overall Life' : (LIFE_AREAS.find(a => a.id === scope)?.name || scope)}
            </Text>
            <Text style={s.modalAutoLine}>Computed avg from assessments: <Text style={s.modalAutoVal}>{overrideModal.auto.toFixed(1)}/10 · {Math.round(overrideModal.auto * 10)}%</Text></Text>
            <Text style={s.modalScoreLine}>
              Your value: <Text style={s.modalScoreVal}>{overrideModal.score}/10 · {overrideModal.score * 10}%</Text>
            </Text>
            <Slider
              style={{ height: 40 }}
              minimumValue={0}
              maximumValue={10}
              step={1}
              value={overrideModal.score}
              onValueChange={(v: number) =>
                setOverrideModal(m => ({ ...m, score: Math.round(v) }))}
              minimumTrackTintColor="#F97316"
              maximumTrackTintColor={COLORS.divider}
              thumbTintColor="#F97316"
            />
            <TextInput
              style={s.modalNoteInput}
              value={overrideModal.note}
              onChangeText={(t) => setOverrideModal(m => ({ ...m, note: t }))}
              placeholder="Why this override? (optional)"
              placeholderTextColor={COLORS.textMuted}
              multiline
            />
            <View style={s.modalBtnRow}>
              {overrideModal.overridden && (
                <TouchableOpacity style={s.modalResetBtn} onPress={clearOverride} testID="override-reset-btn">
                  <Ionicons name="refresh" size={14} color="#7C3AED" />
                  <Text style={s.modalResetText}>Reset to computed</Text>
                </TouchableOpacity>
              )}
              <View style={{ flex: 1 }} />
              <TouchableOpacity style={s.modalSaveBtn} onPress={saveOverride} testID="override-save-btn">
                <Text style={s.modalSaveText}>Save override</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 14, paddingBottom: 18 },
  backBtn: { width: 38, height: 38, borderRadius: 19, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center', marginRight: 12 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 11, color: 'rgba(255,255,255,0.7)', marginTop: 2 },
  addBtn: { width: 38, height: 38, borderRadius: 19, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center' },

  viewRow: { flexDirection: 'row', paddingHorizontal: 16, paddingTop: 10, gap: 6 },
  viewToggle: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: COLORS.white, borderWidth: 1, borderColor: COLORS.border },
  viewActive: { backgroundColor: '#7C3AED', borderColor: '#7C3AED' },
  viewText: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted },

  filterRow: { flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: 16, gap: 6, paddingVertical: 8, rowGap: 6 },
  filterChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 14, backgroundColor: COLORS.white, borderWidth: 1, borderColor: COLORS.border },
  filterActive: { backgroundColor: '#7C3AED', borderColor: '#7C3AED' },
  filterText: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted },

  // Matrix overview
  matrixContainer: { backgroundColor: COLORS.white, borderRadius: 14, padding: 12, marginBottom: 16, borderWidth: 1, borderColor: COLORS.border },
  matrixTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 2, textAlign: 'center' },
  matrixHint: { fontSize: 10, color: COLORS.textMuted, textAlign: 'center', marginBottom: 10, fontStyle: 'italic' },
  matrixRow: { flexDirection: 'row', marginBottom: 4 },
  matrixCell: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: 8 },
  matrixCorner: { alignItems: 'flex-start' },
  matrixCornerText: { fontSize: 10, fontWeight: '700', color: COLORS.textMuted, letterSpacing: 1 },
  matrixHeader: { gap: 2 },
  matrixHeaderText: { fontSize: 10, fontWeight: '700' },
  matrixRowHeader: { flexDirection: 'row', gap: 4, justifyContent: 'flex-start' },
  matrixRowHeaderText: { fontSize: 11, fontWeight: '600' },
  matrixData: {},
  scoreCircle: { width: 36, height: 36, borderRadius: 18, borderWidth: 2, justifyContent: 'center', alignItems: 'center' },
  scoreText: { fontSize: 13, fontWeight: '800' },
  overridePill: {
    position: 'absolute', bottom: -2, paddingHorizontal: 4, paddingVertical: 1,
    borderRadius: 4, backgroundColor: '#F97316',
  },
  overridePillText: { fontSize: 8, fontWeight: '800', color: '#FFF', letterSpacing: 0.5 },

  // Override modal
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'center', alignItems: 'center', padding: 16 },
  modalCard: { width: '100%', maxWidth: 460, backgroundColor: COLORS.white, borderRadius: 16, padding: 18 },
  modalHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  modalTitle: { fontSize: 16, fontWeight: '800', color: COLORS.textPrimary },
  modalSub: { fontSize: 11, color: COLORS.textMuted, marginBottom: 10 },
  modalAutoLine: { fontSize: 12, color: COLORS.textSecondary, marginBottom: 4 },
  modalAutoVal: { fontWeight: '700', color: COLORS.textPrimary },
  modalScoreLine: { fontSize: 13, color: COLORS.textPrimary, marginTop: 6 },
  modalScoreVal: { fontWeight: '800', color: '#F97316' },
  modalNoteInput: { marginTop: 8, minHeight: 60, borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, padding: 10, fontSize: 12, color: COLORS.textPrimary, textAlignVertical: 'top' },
  modalBtnRow: { flexDirection: 'row', alignItems: 'center', marginTop: 12, gap: 8 },
  modalResetBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 8, borderRadius: 10, borderWidth: 1, borderColor: '#7C3AED' },
  modalResetText: { fontSize: 12, fontWeight: '700', color: '#7C3AED' },
  modalSaveBtn: { paddingHorizontal: 14, paddingVertical: 9, borderRadius: 10, backgroundColor: '#F97316' },
  modalSaveText: { fontSize: 13, fontWeight: '800', color: '#FFF' },

  // Entry cards
  entryCard: { backgroundColor: COLORS.white, borderRadius: 14, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  entryHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  areaPill: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: COLORS.primary + '10', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  areaPillText: { fontSize: 10, fontWeight: '600', color: COLORS.primary },
  statusPill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  statusText: { fontSize: 10, fontWeight: '700' },
  entryTitle: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 8 },

  miniMatrix: { gap: 3, marginBottom: 8 },
  miniRow: { flexDirection: 'row', gap: 3, alignItems: 'center' },
  miniLabel: { width: 20, alignItems: 'center' },
  miniCell: { flex: 1, height: 24, borderRadius: 6, justifyContent: 'center', alignItems: 'center' },
  miniScore: { fontSize: 10, fontWeight: '700' },

  entryFooter: { flexDirection: 'row', alignItems: 'center', gap: 8, borderTopWidth: 1, borderTopColor: COLORS.divider, paddingTop: 8 },
  scoreBar: { flex: 1, height: 6, borderRadius: 3, backgroundColor: COLORS.divider },
  scoreBarFill: { height: 6, borderRadius: 3 },
  scorePct: { fontSize: 12, fontWeight: '700', color: COLORS.textPrimary, width: 36 },

  empty: { alignItems: 'center', paddingTop: 40 },
  emptyIcon: { width: 80, height: 80, borderRadius: 40, backgroundColor: COLORS.divider, justifyContent: 'center', alignItems: 'center', marginBottom: 16 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  emptySub: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', marginTop: 8, paddingHorizontal: 32, lineHeight: 20 },
  emptyBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 20, paddingHorizontal: 20, paddingVertical: 12, backgroundColor: '#7C3AED', borderRadius: 12 },
  emptyBtnText: { fontSize: 14, fontWeight: '600', color: '#FFF' },
});
