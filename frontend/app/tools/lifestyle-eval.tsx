import React, { useState, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { safeBack } from '../../src/utils/navigation';

const DAY_TABS = [
  { id: '', label: 'All', icon: 'calendar' },
  { id: 'weekday', label: 'Weekdays', icon: 'briefcase' },
  { id: 'saturday', label: 'Saturday', icon: 'sunny' },
  { id: 'sunday', label: 'Sunday', icon: 'leaf' },
];

const AREA_COLORS: Record<string, string> = {
  holistic_health: '#10B981', knowledge_skills: '#3B82F6', relationships: '#EC4899',
  finance: '#8B5CF6', assets: '#F97316', career: '#0EA5E9', personal_dreams: '#F59E0B',
  social_image: '#6366F1', social_contributions: '#14B8A6', spirituality: '#A855F7',
};

function formatMins(m: number) {
  const h = Math.floor(m / 60);
  const min = Math.round(m % 60);
  return h > 0 ? `${h}h ${min}m` : `${min}m`;
}

export default function LifestyleEvalScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [dashboard, setDashboard] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);
  const [dayFilter, setDayFilter] = useState('');
  const [viewMode, setViewMode] = useState<'dashboard' | 'summary'>('dashboard');

  const fetchData = async () => {
    try {
      const [dashRes, sumRes] = await Promise.all([
        api.get('/lifestyle-eval/dashboard'),
        api.get('/lifestyle-eval/summary'),
      ]);
      setDashboard(dashRes.data);
      setSummary(sumRes.data);
    } catch (e) { console.error('LEE fetch error:', e); }
    finally { setLoading(false); }
  };

  useFocusEffect(useCallback(() => { setLoading(true); fetchData(); }, []));
  const onRefresh = async () => { setRefreshing(true); await fetchData(); setRefreshing(false); };

  const today = new Date().toISOString().split('T')[0];

  const renderDashboard = () => {
    if (!dashboard) return null;
    const ws = dashboard.week_stats || {};
    return (
      <>
        {/* Quick Stats */}
        <View style={s.statsRow}>
          <View style={s.statBox}>
            <Text style={s.statNum}>{dashboard.total_logs}</Text>
            <Text style={s.statLabel}>Total Logs</Text>
          </View>
          <View style={s.statBox}>
            <Text style={s.statNum}>{ws.total_hours || 0}</Text>
            <Text style={s.statLabel}>Hours (7d)</Text>
          </View>
          <View style={s.statBox}>
            <Text style={s.statNum}>{ws.areas_covered || 0}</Text>
            <Text style={s.statLabel}>Areas (7d)</Text>
          </View>
        </View>

        {/* Top Areas */}
        {dashboard.top_areas && dashboard.top_areas.length > 0 && (
          <View style={s.card}>
            <Text style={s.cardTitle}>Top Areas (Last 7 Days)</Text>
            {dashboard.top_areas.map((a: any, i: number) => (
              <View key={a.area_id} style={s.topRow}>
                <View style={[s.topDot, { backgroundColor: AREA_COLORS[a.area_id] || '#6B7280' }]} />
                <Text style={s.topName} numberOfLines={1}>{a.area_name}</Text>
                <View style={s.topBarOuter}>
                  <View style={[s.topBarFill, {
                    width: `${Math.min((a.minutes / (dashboard.top_areas[0]?.minutes || 1)) * 100, 100)}%`,
                    backgroundColor: AREA_COLORS[a.area_id] || '#6B7280',
                  }]} />
                </View>
                <Text style={s.topMins}>{formatMins(a.minutes)}</Text>
              </View>
            ))}
          </View>
        )}

        {/* Recent Logs */}
        <Text style={s.sectionTitle}>Recent Logs</Text>
        {(dashboard.recent_logs || []).length === 0 ? (
          <View style={s.emptyMini}>
            <Text style={s.emptyMiniText}>No logs yet. Start tracking today!</Text>
          </View>
        ) : (
          (dashboard.recent_logs || []).map((log: any) => (
            <TouchableOpacity key={log.date} style={s.logCard}
              onPress={() => router.push({ pathname: '/tools/lifestyle-eval-entry', params: { date: log.date } })}
            >
              <View style={[s.dayBadge, {
                backgroundColor: log.day_type === 'saturday' ? '#F59E0B20' :
                  log.day_type === 'sunday' ? '#10B98120' : '#3B82F620'
              }]}>
                <Text style={[s.dayBadgeText, {
                  color: log.day_type === 'saturday' ? '#F59E0B' :
                    log.day_type === 'sunday' ? '#10B981' : '#3B82F6'
                }]}>{(log.day_type || 'weekday').toUpperCase()}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={s.logDate}>{log.date}</Text>
                <Text style={s.logSub}>{log.activity_count} activities logged</Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color={COLORS.textMuted} />
            </TouchableOpacity>
          ))
        )}
      </>
    );
  };

  const renderSummary = () => {
    if (!summary?.summary) return (
      <View style={s.emptyMini}><Text style={s.emptyMiniText}>No data yet for summary</Text></View>
    );
    const dayTypes = dayFilter ? [dayFilter] : ['weekday', 'saturday', 'sunday'];

    return dayTypes.map(dt => {
      const areas = summary.summary[dt];
      if (!areas || Object.keys(areas).length === 0) return null;
      return (
        <View key={dt} style={s.card}>
          <Text style={s.cardTitle}>
            {dt === 'weekday' ? 'Weekdays (Mon-Fri)' : dt === 'saturday' ? 'Saturday' : 'Sunday'}
          </Text>
          <Text style={s.cardSub}>Avg time per area per day</Text>
          {Object.entries(areas).map(([areaId, data]: [string, any]) => (
            <View key={areaId} style={s.summaryRow}>
              <View style={[s.summaryDot, { backgroundColor: AREA_COLORS[areaId] || '#6B7280' }]} />
              <Text style={s.summaryArea} numberOfLines={1}>
                {(summary.life_areas || []).find((a: any) => a.id === areaId)?.name || areaId}
              </Text>
              <Text style={s.summaryTime}>{formatMins(data.avg_minutes)}</Text>
              <View style={s.catRow}>
                {data.categories?.problem > 0 && (
                  <View style={[s.catPill, { backgroundColor: '#EF444420' }]}>
                    <Text style={[s.catText, { color: '#EF4444' }]}>P: {Math.round(data.categories.problem)}m</Text>
                  </View>
                )}
                {data.categories?.need > 0 && (
                  <View style={[s.catPill, { backgroundColor: '#F59E0B20' }]}>
                    <Text style={[s.catText, { color: '#F59E0B' }]}>N: {Math.round(data.categories.need)}m</Text>
                  </View>
                )}
                {data.categories?.aspiration > 0 && (
                  <View style={[s.catPill, { backgroundColor: '#10B98120' }]}>
                    <Text style={[s.catText, { color: '#10B981' }]}>A: {Math.round(data.categories.aspiration)}m</Text>
                  </View>
                )}
              </View>
            </View>
          ))}
        </View>
      );
    });
  };

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <LinearGradient colors={['#7C3AED', '#A855F7']} style={s.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.headerTitle}>Lifestyle Effectiveness</Text>
          <Text style={s.headerSub}>Track actual vs planned lifestyle</Text>
        </View>
        <TouchableOpacity
          onPress={() => router.push({ pathname: '/tools/lifestyle-eval-entry', params: { date: today } })}
          style={s.addBtn}
        >
          <Ionicons name="add" size={22} color="#FFF" />
        </TouchableOpacity>
      </LinearGradient>

      {/* View Toggle */}
      <View style={s.toggleRow}>
        {([{ key: 'dashboard', icon: 'home', label: 'Dashboard' }, { key: 'summary', icon: 'analytics', label: 'Summary' }] as const).map(v => (
          <TouchableOpacity key={v.key} style={[s.toggle, viewMode === v.key && s.toggleActive]} onPress={() => setViewMode(v.key)}>
            <Ionicons name={v.icon as any} size={14} color={viewMode === v.key ? '#FFF' : COLORS.textMuted} />
            <Text style={[s.toggleText, viewMode === v.key && { color: '#FFF' }]}>{v.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Day Filter (summary mode) */}
      {viewMode === 'summary' && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ maxHeight: 44, minHeight: 44 }}>
          <View style={s.filterRow}>
            {DAY_TABS.map(d => (
              <TouchableOpacity key={d.id} style={[s.filterChip, dayFilter === d.id && s.filterActive]} onPress={() => setDayFilter(d.id)}>
                <Ionicons name={d.icon as any} size={12} color={dayFilter === d.id ? '#FFF' : COLORS.textMuted} />
                <Text style={[s.filterText, dayFilter === d.id && { color: '#FFF' }]}>{d.label}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </ScrollView>
      )}

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
          {dashboard?.total_logs === 0 && viewMode === 'dashboard' ? (
            <View style={s.empty}>
              <View style={s.emptyIcon}>
                <Ionicons name="analytics-outline" size={48} color={COLORS.textMuted} />
              </View>
              <Text style={s.emptyTitle}>Track Your Lifestyle</Text>
              <Text style={s.emptySub}>
                Log your daily activities to evaluate how effectively you spend time across life areas
              </Text>
              <TouchableOpacity style={s.emptyBtn}
                onPress={() => router.push({ pathname: '/tools/lifestyle-eval-entry', params: { date: today } })}>
                <Ionicons name="add-circle" size={18} color="#FFF" />
                <Text style={s.emptyBtnText}>Log Today's Activities</Text>
              </TouchableOpacity>
            </View>
          ) : viewMode === 'dashboard' ? renderDashboard() : renderSummary()}

          {/* Planned vs Actual CTA */}
          {dashboard && dashboard.total_logs > 0 && (
            <TouchableOpacity style={s.pvaCta}
              onPress={() => router.push({ pathname: '/tools/lifestyle-eval-entry', params: { date: today, tab: 'comparison' } })}>
              <Ionicons name="git-compare" size={18} color="#7C3AED" />
              <View style={{ flex: 1 }}>
                <Text style={s.pvaTitle}>Planned vs Actual</Text>
                <Text style={s.pvaSub}>Compare today's activities against your CTT tasks & routines</Text>
              </View>
              <Ionicons name="chevron-forward" size={16} color="#7C3AED" />
            </TouchableOpacity>
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

  toggleRow: { flexDirection: 'row', paddingHorizontal: 16, paddingTop: 10, gap: 6 },
  toggle: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 14, paddingVertical: 7, borderRadius: 16, backgroundColor: COLORS.white, borderWidth: 1, borderColor: COLORS.border },
  toggleActive: { backgroundColor: '#7C3AED', borderColor: '#7C3AED' },
  toggleText: { fontSize: 12, fontWeight: '600', color: COLORS.textMuted },

  filterRow: { flexDirection: 'row', paddingHorizontal: 16, gap: 6, paddingVertical: 8 },
  filterChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 14, backgroundColor: COLORS.white, borderWidth: 1, borderColor: COLORS.border },
  filterActive: { backgroundColor: '#7C3AED', borderColor: '#7C3AED' },
  filterText: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted },

  statsRow: { flexDirection: 'row', gap: 10, marginBottom: 16 },
  statBox: { flex: 1, backgroundColor: COLORS.white, borderRadius: 12, padding: 12, alignItems: 'center', borderWidth: 1, borderColor: COLORS.border },
  statNum: { fontSize: 18, fontWeight: '700', color: '#7C3AED' },
  statLabel: { fontSize: 10, color: COLORS.textMuted, marginTop: 2, textTransform: 'uppercase' },

  card: { backgroundColor: COLORS.white, borderRadius: 14, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: COLORS.border },
  cardTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 4 },
  cardSub: { fontSize: 11, color: COLORS.textMuted, marginBottom: 10 },

  topRow: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 5 },
  topDot: { width: 8, height: 8, borderRadius: 4 },
  topName: { width: 80, fontSize: 11, fontWeight: '500', color: COLORS.textPrimary },
  topBarOuter: { flex: 1, height: 8, borderRadius: 4, backgroundColor: COLORS.divider },
  topBarFill: { height: 8, borderRadius: 4 },
  topMins: { width: 50, fontSize: 11, fontWeight: '600', color: COLORS.textPrimary, textAlign: 'right' },

  sectionTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8, marginTop: 8 },

  logCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.white, borderRadius: 12, padding: 12, marginBottom: 6, borderWidth: 1, borderColor: COLORS.border },
  dayBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8 },
  dayBadgeText: { fontSize: 9, fontWeight: '700' },
  logDate: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  logSub: { fontSize: 11, color: COLORS.textMuted, marginTop: 1 },

  summaryRow: { paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  summaryDot: { width: 8, height: 8, borderRadius: 4, position: 'absolute', left: 0, top: 13 },
  summaryArea: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, paddingLeft: 16 },
  summaryTime: { fontSize: 12, fontWeight: '700', color: '#7C3AED', paddingLeft: 16, marginTop: 2 },
  catRow: { flexDirection: 'row', gap: 4, marginTop: 4, paddingLeft: 16 },
  catPill: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 },
  catText: { fontSize: 9, fontWeight: '700' },

  pvaCta: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#7C3AED10', borderRadius: 14, padding: 14, marginTop: 12, borderWidth: 1, borderColor: '#7C3AED30' },
  pvaTitle: { fontSize: 14, fontWeight: '700', color: '#7C3AED' },
  pvaSub: { fontSize: 11, color: COLORS.textMuted, marginTop: 1 },

  emptyMini: { padding: 20, alignItems: 'center' },
  emptyMiniText: { fontSize: 13, color: COLORS.textMuted },

  empty: { alignItems: 'center', paddingTop: 40 },
  emptyIcon: { width: 80, height: 80, borderRadius: 40, backgroundColor: COLORS.divider, justifyContent: 'center', alignItems: 'center', marginBottom: 16 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  emptySub: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', marginTop: 8, paddingHorizontal: 32, lineHeight: 20 },
  emptyBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 20, paddingHorizontal: 20, paddingVertical: 12, backgroundColor: '#7C3AED', borderRadius: 12 },
  emptyBtnText: { fontSize: 14, fontWeight: '600', color: '#FFF' },
});
