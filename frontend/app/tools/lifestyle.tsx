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

const FREQ_LABELS: Record<string, string> = {
  hourly: 'Hourly', daily: 'Daily', weekly: 'Weekly',
  fortnightly: 'Fortnightly', monthly: 'Monthly',
};
const FREQ_COLORS: Record<string, string> = {
  hourly: '#EF4444', daily: '#3B82F6', weekly: '#10B981',
  fortnightly: '#F59E0B', monthly: '#8B5CF6',
};
const AREA_LABELS: Record<string, string> = {
  career: 'Career', finance: 'Finance', relationships: 'Relationships',
  holistic_health: 'Health', assets: 'Assets', knowledge_skills: 'Knowledge',
  social_image: 'Social', social_contributions: 'Contributions',
  hobbies_entertainment: 'Hobbies', spirituality_religion: 'Spirituality',
};
const AREA_ICONS: Record<string, string> = {
  career: 'briefcase', finance: 'cash', relationships: 'heart',
  holistic_health: 'fitness', assets: 'home', knowledge_skills: 'school',
  social_image: 'people', social_contributions: 'hand-left',
  hobbies_entertainment: 'game-controller', spirituality_religion: 'leaf',
};
const PRIORITY_COLORS: Record<string, string> = {
  critical: '#EF4444', high: '#F59E0B', medium: '#3B82F6', low: '#6B7280',
};

function getEffectivenessColor(pct: number): string {
  if (pct >= 80) return '#10B981';
  if (pct >= 60) return '#3B82F6';
  if (pct >= 40) return '#F59E0B';
  return '#EF4444';
}

function getEffectivenessLabel(pct: number): string {
  if (pct >= 80) return 'Excellent';
  if (pct >= 60) return 'Good';
  if (pct >= 40) return 'Fair';
  return 'Needs Attention';
}

export default function LifestyleScreen() {
  const router = useRouter();
  const [routines, setRoutines] = useState<any[]>([]);
  const [dashboard, setDashboard] = useState<any>(null);
  const [assessments, setAssessments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [starting, setStarting] = useState(false);
  const [activeTab, setActiveTab] = useState<'routines' | 'assessments'>('routines');
  const [freqFilter, setFreqFilter] = useState('');

  const fetchData = async () => {
    try {
      const params = freqFilter ? `?frequency=${freqFilter}` : '';
      const [routinesRes, dashRes, assessRes] = await Promise.all([
        api.get(`/lifestyle/routines${params}`),
        api.get('/lifestyle/dashboard'),
        api.get('/lifestyle/assessments?limit=10'),
      ]);
      setRoutines(routinesRes.data || []);
      setDashboard(dashRes.data);
      setAssessments(assessRes.data || []);
    } catch (e) { console.error('Lifestyle fetch error:', e); }
    finally { setLoading(false); }
  };

  useFocusEffect(useCallback(() => { setLoading(true); fetchData(); }, [freqFilter]));
  const onRefresh = async () => { setRefreshing(true); await fetchData(); setRefreshing(false); };

  const handleImport = async () => {
    setImporting(true);
    try {
      const res = await api.post('/lifestyle/import-from-ctt');
      const count = res.data?.imported || 0;
      Alert.alert(
        'Import Complete',
        count > 0
          ? `${count} routine(s) imported from CTT`
          : 'No new routines to import. All CTT routines are already tracked.',
      );
      if (count > 0) fetchData();
    } catch (e) { Alert.alert('Error', 'Failed to import from CTT'); }
    finally { setImporting(false); }
  };

  const handleStartAssessment = async (period: string) => {
    setStarting(true);
    try {
      const res = await api.post('/lifestyle/start-assessment', { period });
      const decisionId = res.data?.decision_id;
      if (decisionId) {
        router.push({ pathname: '/prr/[id]', params: { id: decisionId } });
      }
    } catch (e: any) {
      const detail = e?.response?.data?.detail || 'Failed to start assessment';
      Alert.alert('Cannot Start', detail);
    }
    finally { setStarting(false); }
  };

  const handleDeleteRoutine = (id: string, name: string) => {
    Alert.alert('Delete Routine', `Delete "${name}"?`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await api.delete(`/lifestyle/routines/${id}`); fetchData(); }
        catch (e) { Alert.alert('Error', 'Failed to delete'); }
      }},
    ]);
  };

  const renderEffectivenessCard = () => {
    if (!dashboard) return null;
    const eff = dashboard.latest_effectiveness || 0;
    const color = getEffectivenessColor(eff);
    const label = getEffectivenessLabel(eff);
    const scores = dashboard.recent_scores || [];

    return (
      <View style={s.effCard}>
        <View style={s.effTop}>
          <View>
            <Text style={s.effLabel}>Latest Effectiveness</Text>
            <Text style={[s.effScore, { color }]}>{eff > 0 ? `${eff}%` : '--'}</Text>
            <Text style={[s.effStatus, { color }]}>{eff > 0 ? label : 'No assessments yet'}</Text>
          </View>
          <View style={s.effCircle}>
            <View style={[s.effCircleInner, { borderColor: color }]}>
              <Text style={[s.effCircleText, { color }]}>{eff > 0 ? Math.round(eff) : '?'}</Text>
            </View>
          </View>
        </View>

        {/* Mini trend sparkline */}
        {scores.length > 1 && (
          <View style={s.sparkRow}>
            <Text style={s.sparkLabel}>Recent</Text>
            <View style={s.sparkBars}>
              {scores.slice().reverse().map((score: number, i: number) => (
                <View key={i} style={s.sparkBarWrap}>
                  <View style={[s.sparkBar, { height: Math.max(4, (score / 100) * 32), backgroundColor: getEffectivenessColor(score) }]} />
                </View>
              ))}
            </View>
          </View>
        )}

        {/* Start Assessment buttons */}
        <View style={s.assessBtns}>
          {['daily', 'weekly', 'monthly'].map(period => (
            <TouchableOpacity
              key={period}
              style={[s.assessBtn, starting && { opacity: 0.6 }]}
              onPress={() => handleStartAssessment(period)}
              disabled={starting}
            >
              <Ionicons
                name={period === 'daily' ? 'today' : period === 'weekly' ? 'calendar' : 'calendar-number'}
                size={16}
                color="#FFF"
              />
              <Text style={s.assessBtnText}>{period.charAt(0).toUpperCase() + period.slice(1)}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>
    );
  };

  const renderStats = () => {
    if (!dashboard) return null;
    const freq = dashboard.by_frequency || {};
    return (
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.statsScroll}>
        <View style={s.statsRow}>
          <View style={[s.statCard, { borderLeftColor: '#1E3A5F' }]}>
            <Text style={[s.statNum, { color: '#1E3A5F' }]}>{dashboard.active_routines || 0}</Text>
            <Text style={s.statLabel}>Active</Text>
          </View>
          {Object.entries(freq).map(([f, count]) => (
            <View key={f} style={[s.statCard, { borderLeftColor: FREQ_COLORS[f] || '#6B7280' }]}>
              <Text style={[s.statNum, { color: FREQ_COLORS[f] || '#6B7280' }]}>{count as number}</Text>
              <Text style={s.statLabel}>{FREQ_LABELS[f] || f}</Text>
            </View>
          ))}
        </View>
      </ScrollView>
    );
  };

  const renderRoutineCard = (routine: any) => (
    <TouchableOpacity
      key={routine.routine_id}
      style={s.routineCard}
      onPress={() => router.push({ pathname: '/tools/lifestyle-routine', params: { id: routine.routine_id } })}
    >
      <View style={s.routineTop}>
        <View style={[s.priorityBar, { backgroundColor: PRIORITY_COLORS[routine.priority] || '#6B7280' }]} />
        <View style={[s.freqPill, { backgroundColor: (FREQ_COLORS[routine.frequency] || '#6B7280') + '15' }]}>
          <Text style={[s.freqPillText, { color: FREQ_COLORS[routine.frequency] || '#6B7280' }]}>
            {FREQ_LABELS[routine.frequency] || routine.frequency}
          </Text>
        </View>
        {routine.life_area ? (
          <View style={s.areaPill}>
            <Ionicons name={(AREA_ICONS[routine.life_area] || 'ellipse') as any} size={10} color={COLORS.primary} />
            <Text style={s.areaPillText}>{AREA_LABELS[routine.life_area] || routine.life_area}</Text>
          </View>
        ) : null}
        {!routine.is_active && (
          <View style={[s.freqPill, { backgroundColor: '#EF444415' }]}>
            <Text style={{ fontSize: 10, fontWeight: '600', color: '#EF4444' }}>Inactive</Text>
          </View>
        )}
        <View style={{ flex: 1 }} />
        <TouchableOpacity onPress={() => handleDeleteRoutine(routine.routine_id, routine.name)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
          <Ionicons name="trash-outline" size={16} color={COLORS.textMuted} />
        </TouchableOpacity>
      </View>
      <Text style={s.routineName} numberOfLines={2}>{routine.name || 'Untitled Routine'}</Text>
      {routine.description ? <Text style={s.routineDesc} numberOfLines={1}>{routine.description}</Text> : null}
      {routine.time_slot ? (
        <View style={s.routineMeta}>
          <Ionicons name="time-outline" size={11} color={COLORS.textMuted} />
          <Text style={s.routineMetaText}>{routine.time_slot}</Text>
        </View>
      ) : null}
    </TouchableOpacity>
  );

  const renderAssessmentCard = (a: any) => {
    const color = getEffectivenessColor(a.effectiveness_pct);
    return (
      <TouchableOpacity
        key={a.decision_id}
        style={s.assessCard}
        onPress={() => router.push({ pathname: '/prr/[id]', params: { id: a.decision_id } })}
      >
        <View style={[s.assessDot, { backgroundColor: color }]} />
        <View style={{ flex: 1 }}>
          <Text style={s.assessTitle} numberOfLines={1}>{a.title}</Text>
          <View style={s.assessMeta}>
            <View style={[s.periodPill, { backgroundColor: a.period === 'daily' ? '#3B82F615' : a.period === 'weekly' ? '#10B98115' : '#8B5CF615' }]}>
              <Text style={[s.periodText, { color: a.period === 'daily' ? '#3B82F6' : a.period === 'weekly' ? '#10B981' : '#8B5CF6' }]}>
                {a.period}
              </Text>
            </View>
            <Text style={s.assessDate}>{a.created_at?.slice(0, 10)}</Text>
            <Text style={s.assessFactors}>{a.assessed_count}/{a.factors_count} factors</Text>
          </View>
        </View>
        <View style={s.assessScoreWrap}>
          <Text style={[s.assessScoreNum, { color }]}>{a.effectiveness_pct}%</Text>
          <Text style={s.assessScoreLabel}>{a.is_complete ? 'Complete' : 'In Progress'}</Text>
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <LinearGradient colors={['#065F46', '#059669']} style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.headerTitle}>Lifestyle Dezider</Text>
          <Text style={s.headerSub}>
            {dashboard?.active_routines || 0} routines | {assessments.length} assessments
          </Text>
        </View>
        <View style={s.headerActions}>
          <TouchableOpacity
            style={[s.importBtn, importing && { opacity: 0.6 }]}
            onPress={handleImport}
            disabled={importing}
          >
            {importing ? <ActivityIndicator size="small" color="#FFF" /> : (
              <><Ionicons name="download" size={14} color="#FFF" /><Text style={s.importText}>Import</Text></>
            )}
          </TouchableOpacity>
          <TouchableOpacity onPress={() => router.push('/tools/lifestyle-routine')} style={s.addBtn}>
            <Ionicons name="add" size={22} color="#FFF" />
          </TouchableOpacity>
        </View>
      </LinearGradient>

      {/* Effectiveness card */}
      {renderEffectivenessCard()}

      {/* Stats */}
      {renderStats()}

      {/* Tab toggle */}
      <View style={s.tabRow}>
        <TouchableOpacity style={[s.tab, activeTab === 'routines' && s.tabActive]} onPress={() => setActiveTab('routines')}>
          <Ionicons name="repeat" size={14} color={activeTab === 'routines' ? '#FFF' : COLORS.textMuted} />
          <Text style={[s.tabText, activeTab === 'routines' && { color: '#FFF' }]}>Routines ({routines.length})</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[s.tab, activeTab === 'assessments' && s.tabActive]} onPress={() => setActiveTab('assessments')}>
          <Ionicons name="analytics" size={14} color={activeTab === 'assessments' ? '#FFF' : COLORS.textMuted} />
          <Text style={[s.tabText, activeTab === 'assessments' && { color: '#FFF' }]}>Assessments ({assessments.length})</Text>
        </TouchableOpacity>
        <TouchableOpacity style={s.analyticsBtn} onPress={() => router.push('/tools/lifestyle-analytics')}>
          <Ionicons name="bar-chart" size={16} color={COLORS.primary} />
        </TouchableOpacity>
      </View>

      {/* Frequency filter (for routines tab) */}
      {activeTab === 'routines' && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ maxHeight: 40, minHeight: 40 }}>
          <View style={s.filterRow}>
            <TouchableOpacity style={[s.filterChip, !freqFilter && s.filterActive]} onPress={() => setFreqFilter('')}>
              <Text style={[s.filterText, !freqFilter && { color: '#FFF' }]}>All</Text>
            </TouchableOpacity>
            {Object.entries(FREQ_LABELS).map(([key, label]) => (
              <TouchableOpacity key={key} style={[s.filterChip, freqFilter === key && s.filterActive]} onPress={() => setFreqFilter(freqFilter === key ? '' : key)}>
                <Text style={[s.filterText, freqFilter === key && { color: '#FFF' }]}>{label}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </ScrollView>
      )}

      {/* Content */}
      {loading ? (
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <ActivityIndicator size="large" color="#059669" />
        </View>
      ) : (
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ padding: 16, paddingBottom: 32 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          {activeTab === 'routines' ? (
            routines.length === 0 ? (
              <View style={s.empty}>
                <View style={s.emptyIcon}><Ionicons name="repeat" size={48} color={COLORS.textMuted} /></View>
                <Text style={s.emptyTitle}>No Routines Yet</Text>
                <Text style={s.emptySub}>Add routine tasks or import them from CTT</Text>
                <View style={s.emptyActions}>
                  <TouchableOpacity style={s.emptyBtn} onPress={() => router.push('/tools/lifestyle-routine')}>
                    <Ionicons name="add-circle" size={18} color="#FFF" />
                    <Text style={s.emptyBtnText}>Add Routine</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={[s.emptyBtn, { backgroundColor: '#3B82F6' }]} onPress={handleImport}>
                    <Ionicons name="download" size={18} color="#FFF" />
                    <Text style={s.emptyBtnText}>Import from CTT</Text>
                  </TouchableOpacity>
                </View>
              </View>
            ) : (
              routines.map(renderRoutineCard)
            )
          ) : (
            assessments.length === 0 ? (
              <View style={s.empty}>
                <View style={s.emptyIcon}><Ionicons name="analytics-outline" size={48} color={COLORS.textMuted} /></View>
                <Text style={s.emptyTitle}>No Assessments Yet</Text>
                <Text style={s.emptySub}>Start a self-assessment to evaluate your lifestyle effectiveness</Text>
              </View>
            ) : (
              assessments.map(renderAssessmentCard)
            )
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
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  importBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 12, paddingVertical: 7, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.2)' },
  importText: { fontSize: 12, fontWeight: '600', color: '#FFF' },
  addBtn: { width: 38, height: 38, borderRadius: 19, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center' },

  // Effectiveness card
  effCard: { margin: 16, marginBottom: 8, backgroundColor: COLORS.white, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: COLORS.border },
  effTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  effLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textMuted, textTransform: 'uppercase', letterSpacing: 0.5 },
  effScore: { fontSize: 32, fontWeight: '800', marginTop: 4 },
  effStatus: { fontSize: 13, fontWeight: '600', marginTop: 2 },
  effCircle: { alignItems: 'center' },
  effCircleInner: { width: 56, height: 56, borderRadius: 28, borderWidth: 4, justifyContent: 'center', alignItems: 'center' },
  effCircleText: { fontSize: 20, fontWeight: '800' },
  sparkRow: { flexDirection: 'row', alignItems: 'flex-end', gap: 8, marginTop: 12, paddingTop: 12, borderTopWidth: 1, borderTopColor: COLORS.divider },
  sparkLabel: { fontSize: 10, fontWeight: '600', color: COLORS.textMuted, width: 40 },
  sparkBars: { flexDirection: 'row', gap: 4, flex: 1, alignItems: 'flex-end' },
  sparkBarWrap: { flex: 1, alignItems: 'center' },
  sparkBar: { width: '100%', borderRadius: 3, minHeight: 4 },
  assessBtns: { flexDirection: 'row', gap: 8, marginTop: 14 },
  assessBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 10, borderRadius: 10, backgroundColor: '#065F46' },
  assessBtnText: { fontSize: 13, fontWeight: '700', color: '#FFF' },

  // Stats
  statsScroll: { maxHeight: 68, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  statsRow: { flexDirection: 'row', paddingHorizontal: 16, paddingVertical: 8, gap: 8 },
  statCard: { backgroundColor: COLORS.white, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 6, alignItems: 'center', minWidth: 64, borderWidth: 1, borderColor: COLORS.border, borderLeftWidth: 3 },
  statNum: { fontSize: 18, fontWeight: '800' },
  statLabel: { fontSize: 9, fontWeight: '600', color: COLORS.textMuted, textTransform: 'uppercase' },

  // Tabs
  tabRow: { flexDirection: 'row', paddingHorizontal: 16, paddingTop: 10, gap: 6 },
  tab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4, paddingVertical: 8, borderRadius: 10, backgroundColor: COLORS.white, borderWidth: 1, borderColor: COLORS.border },
  tabActive: { backgroundColor: '#065F46', borderColor: '#065F46' },
  tabText: { fontSize: 12, fontWeight: '600', color: COLORS.textMuted },
  analyticsBtn: { width: 40, height: 40, borderRadius: 10, backgroundColor: COLORS.primary + '10', justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: COLORS.primary + '30' },

  // Filters
  filterRow: { flexDirection: 'row', paddingHorizontal: 16, gap: 6, paddingVertical: 6 },
  filterChip: { paddingHorizontal: 12, paddingVertical: 5, borderRadius: 14, backgroundColor: COLORS.white, borderWidth: 1, borderColor: COLORS.border },
  filterActive: { backgroundColor: '#065F46', borderColor: '#065F46' },
  filterText: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted },

  // Routine cards
  routineCard: { backgroundColor: COLORS.white, borderRadius: 12, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border },
  routineTop: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  priorityBar: { width: 4, height: 24, borderRadius: 2 },
  freqPill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  freqPillText: { fontSize: 10, fontWeight: '700', textTransform: 'capitalize' },
  areaPill: { flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: COLORS.primary + '10', paddingHorizontal: 6, paddingVertical: 3, borderRadius: 8 },
  areaPillText: { fontSize: 10, fontWeight: '600', color: COLORS.primary },
  routineName: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary, marginLeft: 10 },
  routineDesc: { fontSize: 12, color: COLORS.textSecondary, marginLeft: 10, marginTop: 2 },
  routineMeta: { flexDirection: 'row', alignItems: 'center', gap: 4, marginLeft: 10, marginTop: 4 },
  routineMetaText: { fontSize: 11, color: COLORS.textMuted },

  // Assessment cards
  assessCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, borderRadius: 12, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border },
  assessDot: { width: 10, height: 10, borderRadius: 5 },
  assessTitle: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  assessMeta: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 4 },
  periodPill: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 },
  periodText: { fontSize: 10, fontWeight: '600', textTransform: 'capitalize' },
  assessDate: { fontSize: 10, color: COLORS.textMuted },
  assessFactors: { fontSize: 10, color: COLORS.textMuted },
  assessScoreWrap: { alignItems: 'flex-end' },
  assessScoreNum: { fontSize: 18, fontWeight: '800' },
  assessScoreLabel: { fontSize: 9, color: COLORS.textMuted },

  // Empty
  empty: { alignItems: 'center', paddingTop: 40 },
  emptyIcon: { width: 80, height: 80, borderRadius: 40, backgroundColor: COLORS.divider, justifyContent: 'center', alignItems: 'center', marginBottom: 16 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  emptySub: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', marginTop: 8, paddingHorizontal: 32, lineHeight: 20 },
  emptyActions: { flexDirection: 'row', gap: 12, marginTop: 20 },
  emptyBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 16, paddingVertical: 10, borderRadius: 10, backgroundColor: '#065F46' },
  emptyBtnText: { fontSize: 13, fontWeight: '600', color: '#FFF' },
});
