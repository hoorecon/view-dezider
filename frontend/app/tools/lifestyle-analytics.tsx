import React, { useState, useCallback } from 'react';
import { getLifeAreaShort, getLifeAreaIcon } from '../../src/constants/lifeAreas';
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

// life-area inline map replaced — see getLifeAreaShort()/getLifeAreaIcon()
// life-area inline map replaced — see getLifeAreaShort()/getLifeAreaIcon()

function getColor(pct: number): string {
  if (pct >= 80) return '#10B981';
  if (pct >= 60) return '#3B82F6';
  if (pct >= 40) return '#F59E0B';
  return '#EF4444';
}

function getLabel(pct: number): string {
  if (pct >= 80) return 'Excellent';
  if (pct >= 60) return 'Good';
  if (pct >= 40) return 'Fair';
  return 'Needs Attention';
}

export default function LifestyleAnalyticsScreen() {
  const router = useRouter();
  const [analytics, setAnalytics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [period, setPeriod] = useState('daily');

  const fetchData = async () => {
    try {
      const res = await api.get(`/lifestyle/analytics?period=${period}`);
      setAnalytics(res.data);
    } catch (e) { console.error('Analytics fetch error:', e); }
    finally { setLoading(false); }
  };

  useFocusEffect(useCallback(() => { setLoading(true); fetchData(); }, [period]));
  const onRefresh = async () => { setRefreshing(true); await fetchData(); setRefreshing(false); };

  const renderOverview = () => {
    if (!analytics) return null;
    const avg = analytics.avg_effectiveness || 0;
    const color = getColor(avg);
    return (
      <View style={s.overviewCard}>
        <View style={s.overviewTop}>
          <View>
            <Text style={s.overviewLabel}>Average Effectiveness</Text>
            <Text style={[s.overviewScore, { color }]}>{avg > 0 ? `${avg}%` : '--'}</Text>
            <Text style={[s.overviewStatus, { color }]}>{avg > 0 ? getLabel(avg) : 'No data'}</Text>
          </View>
          <View style={[s.overviewCircle, { borderColor: color }]}>
            <Text style={[s.overviewCircleText, { color }]}>{avg > 0 ? Math.round(avg) : '?'}</Text>
          </View>
        </View>
        <View style={s.overviewMeta}>
          <View style={s.metaItem}>
            <Ionicons name="checkmark-done" size={16} color="#10B981" />
            <Text style={s.metaText}>{analytics.completed_assessments || 0} completed</Text>
          </View>
          <View style={s.metaItem}>
            <Ionicons name="flame" size={16} color="#F59E0B" />
            <Text style={s.metaText}>{analytics.current_streak || 0} day streak</Text>
          </View>
          <View style={s.metaItem}>
            <Ionicons name="layers" size={16} color="#3B82F6" />
            <Text style={s.metaText}>{analytics.total_assessments || 0} total</Text>
          </View>
        </View>
      </View>
    );
  };

  const renderTrend = () => {
    if (!analytics?.trend?.length) return null;
    const trend = analytics.trend.slice(0, 14);
    const maxScore = 100;

    return (
      <View style={s.trendCard}>
        <Text style={s.sectionTitle}>Effectiveness Trend</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <View style={s.trendChart}>
            {trend.slice().reverse().map((t: any, i: number) => {
              const barH = Math.max(6, (t.effectiveness / maxScore) * 120);
              const color = t.is_complete ? getColor(t.effectiveness) : '#D1D5DB';
              return (
                <View key={i} style={s.trendBar}>
                  <Text style={[s.trendValue, { color }]}>{t.effectiveness > 0 ? `${t.effectiveness}%` : '-'}</Text>
                  <View style={[s.trendBarFill, { height: barH, backgroundColor: color }]} />
                  <Text style={s.trendDate}>{t.date?.slice(5) || ''}</Text>
                </View>
              );
            })}
          </View>
        </ScrollView>
      </View>
    );
  };

  const renderAreaBreakdown = () => {
    if (!analytics?.area_averages || Object.keys(analytics.area_averages).length === 0) return null;
    const areas = Object.entries(analytics.area_averages).sort((a, b) => (b[1] as number) - (a[1] as number));

    return (
      <View style={s.areaCard}>
        <Text style={s.sectionTitle}>By Life Area</Text>
        {areas.map(([area, score]) => {
          const pct = score as number;
          const color = getColor(pct);
          return (
            <View key={area} style={s.areaRow}>
              <View style={s.areaLeft}>
                <Ionicons name={(getLifeAreaIcon(area) || 'ellipse') as any} size={16} color={color} />
                <Text style={s.areaName}>{getLifeAreaShort(area) || area}</Text>
              </View>
              <View style={s.areaBarWrap}>
                <View style={[s.areaBar, { width: `${Math.min(pct, 100)}%`, backgroundColor: color }]} />
              </View>
              <Text style={[s.areaPct, { color }]}>{pct}%</Text>
            </View>
          );
        })}
      </View>
    );
  };

  const renderLegend = () => (
    <View style={s.legendCard}>
      <Text style={s.sectionTitle}>Effectiveness Legend</Text>
      <View style={s.legendRow}>
        {[
          { min: 80, label: 'Excellent', color: '#10B981' },
          { min: 60, label: 'Good', color: '#3B82F6' },
          { min: 40, label: 'Fair', color: '#F59E0B' },
          { min: 0, label: 'Needs Attention', color: '#EF4444' },
        ].map(l => (
          <View key={l.label} style={s.legendItem}>
            <View style={[s.legendDot, { backgroundColor: l.color }]} />
            <Text style={s.legendText}>{l.min}%+ {l.label}</Text>
          </View>
        ))}
      </View>
    </View>
  );

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <LinearGradient colors={['#065F46', '#059669']} style={s.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <Text style={s.headerTitle}>Lifestyle Analytics</Text>
      </LinearGradient>

      {/* Period toggle */}
      <View style={s.periodRow}>
        {['daily', 'weekly', 'monthly', 'all'].map(p => (
          <TouchableOpacity key={p} style={[s.periodChip, period === p && s.periodActive]} onPress={() => setPeriod(p)}>
            <Text style={[s.periodText, period === p && { color: '#FFF' }]}>{p === 'all' ? 'All' : p.charAt(0).toUpperCase() + p.slice(1)}</Text>
          </TouchableOpacity>
        ))}
      </View>

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
          {renderOverview()}
          {renderTrend()}
          {renderAreaBreakdown()}
          {renderLegend()}

          {(!analytics?.trend?.length) && (
            <View style={s.empty}>
              <Ionicons name="analytics-outline" size={48} color={COLORS.textMuted} />
              <Text style={s.emptyTitle}>No Analytics Yet</Text>
              <Text style={s.emptySub}>Complete lifestyle assessments to see your effectiveness trends</Text>
            </View>
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

  periodRow: { flexDirection: 'row', paddingHorizontal: 16, paddingVertical: 10, gap: 6 },
  periodChip: { flex: 1, alignItems: 'center', paddingVertical: 8, borderRadius: 10, backgroundColor: COLORS.white, borderWidth: 1, borderColor: COLORS.border },
  periodActive: { backgroundColor: '#065F46', borderColor: '#065F46' },
  periodText: { fontSize: 12, fontWeight: '600', color: COLORS.textMuted },

  // Overview
  overviewCard: { backgroundColor: COLORS.white, borderRadius: 16, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: COLORS.border },
  overviewTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  overviewLabel: { fontSize: 12, fontWeight: '600', color: COLORS.textMuted, textTransform: 'uppercase', letterSpacing: 0.5 },
  overviewScore: { fontSize: 36, fontWeight: '800', marginTop: 4 },
  overviewStatus: { fontSize: 14, fontWeight: '600', marginTop: 2 },
  overviewCircle: { width: 64, height: 64, borderRadius: 32, borderWidth: 4, justifyContent: 'center', alignItems: 'center' },
  overviewCircleText: { fontSize: 22, fontWeight: '800' },
  overviewMeta: { flexDirection: 'row', justifyContent: 'space-around', marginTop: 16, paddingTop: 14, borderTopWidth: 1, borderTopColor: COLORS.divider },
  metaItem: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  metaText: { fontSize: 12, fontWeight: '600', color: COLORS.textPrimary },

  sectionTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 12 },

  // Trend
  trendCard: { backgroundColor: COLORS.white, borderRadius: 16, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: COLORS.border },
  trendChart: { flexDirection: 'row', gap: 8, alignItems: 'flex-end', paddingBottom: 4, minHeight: 160 },
  trendBar: { alignItems: 'center', width: 40 },
  trendValue: { fontSize: 9, fontWeight: '700', marginBottom: 4 },
  trendBarFill: { width: 24, borderRadius: 6 },
  trendDate: { fontSize: 8, fontWeight: '600', color: COLORS.textMuted, marginTop: 4 },

  // Area breakdown
  areaCard: { backgroundColor: COLORS.white, borderRadius: 16, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: COLORS.border },
  areaRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  areaLeft: { flexDirection: 'row', alignItems: 'center', gap: 6, width: 100 },
  areaName: { fontSize: 12, fontWeight: '600', color: COLORS.textPrimary },
  areaBarWrap: { flex: 1, height: 8, borderRadius: 4, backgroundColor: COLORS.divider },
  areaBar: { height: 8, borderRadius: 4 },
  areaPct: { fontSize: 12, fontWeight: '700', width: 40, textAlign: 'right' },

  // Legend
  legendCard: { backgroundColor: COLORS.white, borderRadius: 16, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: COLORS.border },
  legendRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  legendDot: { width: 12, height: 12, borderRadius: 6 },
  legendText: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted },

  // Empty
  empty: { alignItems: 'center', paddingTop: 40 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary, marginTop: 12 },
  emptySub: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', marginTop: 8, paddingHorizontal: 32, lineHeight: 20 },
});
