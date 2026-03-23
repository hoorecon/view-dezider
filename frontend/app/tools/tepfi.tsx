import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, Alert, ActivityIndicator, Dimensions,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

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

const LIFE_AREAS = [
  { id: 'career', name: 'Career', icon: 'briefcase' },
  { id: 'finance', name: 'Finance', icon: 'cash' },
  { id: 'relationships', name: 'Relationships', icon: 'heart' },
  { id: 'holistic_health', name: 'Health', icon: 'fitness' },
  { id: 'assets', name: 'Assets', icon: 'home' },
  { id: 'knowledge_skills', name: 'Knowledge', icon: 'school' },
  { id: 'social_image', name: 'Social', icon: 'people' },
  { id: 'social_contributions', name: 'Contributions', icon: 'hand-left' },
  { id: 'hobbies_entertainment', name: 'Hobbies', icon: 'game-controller' },
  { id: 'spirituality_religion', name: 'Spirituality', icon: 'leaf' },
];

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

  const fetchData = async () => {
    try {
      const params = selectedArea ? `?life_area=${selectedArea}` : '';
      const [entriesRes, dashRes] = await Promise.all([
        api.get(`/tepfi/entries${params}`),
        api.get('/tepfi/dashboard'),
      ]);
      setEntries(entriesRes.data || []);
      setDashboard(dashRes.data);
    } catch (e) { console.error('TEPFI fetch error:', e); }
    finally { setLoading(false); }
  };

  useFocusEffect(useCallback(() => { setLoading(true); fetchData(); }, [selectedArea]));
  const onRefresh = async () => { setRefreshing(true); await fetchData(); setRefreshing(false); };

  const handleDelete = (id: string) => {
    Alert.alert('Delete', 'Delete this TEPFI assessment?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await api.delete(`/tepfi/entries/${id}`); fetchData(); }
        catch (e) { Alert.alert('Error', 'Failed to delete'); }
      }},
    ]);
  };

  const renderMatrixOverview = () => {
    if (!dashboard?.avg_matrix) return null;
    const m = dashboard.avg_matrix;
    return (
      <View style={s.matrixContainer}>
        <Text style={s.matrixTitle}>Avg Resource Scores</Text>
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
              const score = m[dim.id]?.[l.id] || 0;
              return (
                <View key={l.id} style={[s.matrixCell, s.matrixData]}>
                  <View style={[s.scoreCircle, { backgroundColor: getScoreColor(score) + '20', borderColor: getScoreColor(score) }]}>
                    <Text style={[s.scoreText, { color: getScoreColor(score) }]}>{score}</Text>
                  </View>
                </View>
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
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.headerTitle}>TEPFI Resource Matrix</Text>
          <Text style={s.headerSub}>
            {dashboard?.total_entries || 0} assessments | Time • Effort • People • Finance • Infra
          </Text>
        </View>
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

      {/* Life area filter */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ maxHeight: 44, minHeight: 44 }}>
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
      </ScrollView>

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
              <Text style={s.emptyTitle}>No TEPFI Assessments</Text>
              <Text style={s.emptySub}>
                Track your resources across Time, Effort, People, Finance & Infrastructure
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

  filterRow: { flexDirection: 'row', paddingHorizontal: 16, gap: 6, paddingVertical: 8 },
  filterChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 14, backgroundColor: COLORS.white, borderWidth: 1, borderColor: COLORS.border },
  filterActive: { backgroundColor: '#7C3AED', borderColor: '#7C3AED' },
  filterText: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted },

  // Matrix overview
  matrixContainer: { backgroundColor: COLORS.white, borderRadius: 14, padding: 12, marginBottom: 16, borderWidth: 1, borderColor: COLORS.border },
  matrixTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 10, textAlign: 'center' },
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
