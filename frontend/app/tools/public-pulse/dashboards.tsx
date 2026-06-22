import React, { useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../../src/constants/colors';
import api from '../../../src/utils/api';
import { safeBack } from '../../../src/utils/navigation';

const DASHBOARDS = [
  { key: 'district-demand-heatmap', title: 'District Demand', subtitle: 'Where the action is', icon: 'map', color: '#6366F1', kind: 'rows' as const },
  { key: 'youth-job-priority', title: 'Youth Job Priorities', subtitle: 'What 18-34 are choosing', icon: 'briefcase', color: '#10B981', kind: 'rows' as const },
  { key: 'marriage-support-need', title: 'Marriage Support Need', subtitle: 'Top concerns', icon: 'heart', color: '#EC4899', kind: 'rows' as const },
  { key: 'scheme-awareness', title: 'Scheme Demand', subtitle: 'What people need most', icon: 'ribbon', color: '#F59E0B', kind: 'rows' as const },
  { key: 'rectification-tracker', title: 'Rectification Tracker', subtitle: 'Issues → Resolution', icon: 'checkmark-done', color: '#3B82F6', kind: 'funnel' as const },
  { key: 'yoy-trend', title: 'YoY Trend', subtitle: 'Year-over-year change', icon: 'trending-up', color: '#8B5CF6', kind: 'yoy' as const },
];

const YOY_TARGETS = [
  { id: 'overall', label: 'All sessions', endpoint: '/public-pulse/analytics/yoy/overall' },
  { id: 'feedback', label: 'Feedback', endpoint: '/public-pulse/analytics/yoy/feedback' },
  { id: 'life_direction', label: 'Life Direction', endpoint: '/public-pulse/analytics/yoy/tool/life_direction' },
  { id: 'marriage_readiness', label: 'Marriage Readiness', endpoint: '/public-pulse/analytics/yoy/tool/marriage_readiness' },
  { id: 'govt_benefit_finder', label: 'Benefit Finder', endpoint: '/public-pulse/analytics/yoy/tool/govt_benefit_finder' },
];

export default function DashboardsScreen() {
  const router = useRouter();
  const [active, setActive] = useState(DASHBOARDS[0].key);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // YoY-specific state
  const [yoyTarget, setYoyTarget] = useState(YOY_TARGETS[0].id);
  const [yoyData, setYoyData] = useState<any>(null);
  const [yoyLoading, setYoyLoading] = useState(false);

  const fetchDashboard = async (key: string) => {
    if (key === 'yoy-trend') return; // YoY uses its own loader
    setLoading(true);
    try {
      const res = await api.get(`/public-pulse/dashboards/${key}`);
      setData(res.data);
    } catch (e) {
      setData({ blocked: true, reason: 'Failed to load' });
    } finally {
      setLoading(false);
    }
  };

  const fetchYoy = async () => {
    setYoyLoading(true);
    try {
      const target = YOY_TARGETS.find(t => t.id === yoyTarget) || YOY_TARGETS[0];
      const res = await api.get(target.endpoint);
      setYoyData(res.data);
    } catch (e) {
      setYoyData({ blocked: true, reason: 'Failed to load' });
    } finally {
      setYoyLoading(false);
    }
  };

  useFocusEffect(useCallback(() => {
    if (active === 'yoy-trend') fetchYoy();
    else fetchDashboard(active);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]));

  // Reload yoy when target changes
  React.useEffect(() => { if (active === 'yoy-trend') fetchYoy();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [yoyTarget]);

  const dash = DASHBOARDS.find((d) => d.key === active)!;
  const rows = data?.data || data?.by_concern?.data || [];
  const k = data?.k_threshold || data?.by_concern?.k_threshold || 0;
  const total = data?.total_in_aggregate || data?.by_concern?.total_in_aggregate || data?.total || 0;
  const isFunnel = dash.kind === 'funnel';
  const isYoy = dash.kind === 'yoy';
  const funnel = data?.funnel || [];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)}>
          <Ionicons name="chevron-back" size={28} color={COLORS.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Public Insights</Text>
        <View style={{ width: 28 }} />
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabStrip} contentContainerStyle={{ paddingHorizontal: 16 }}>
        {DASHBOARDS.map((d) => {
          const sel = d.key === active;
          return (
            <TouchableOpacity
              key={d.key}
              style={[styles.tab, sel && { backgroundColor: d.color, borderColor: d.color }]}
              onPress={() => setActive(d.key)}
            >
              <Ionicons name={d.icon as any} size={16} color={sel ? '#FFF' : d.color} />
              <Text style={[styles.tabTxt, sel && { color: '#FFF' }]}>{d.title}</Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
        <View style={[styles.dashHeader, { backgroundColor: `${dash.color}15` }]}>
          <Ionicons name={dash.icon as any} size={28} color={dash.color} />
          <View style={{ flex: 1, marginLeft: 12 }}>
            <Text style={styles.dashTitle}>{dash.title}</Text>
            <Text style={styles.dashSubtitle}>{dash.subtitle}</Text>
          </View>
        </View>

        {/* YoY tab body */}
        {isYoy ? (
          <View>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6, paddingBottom: 12 }}>
              {YOY_TARGETS.map(t => {
                const sel = t.id === yoyTarget;
                return (
                  <TouchableOpacity
                    key={t.id}
                    style={[styles.targetChip, sel && { backgroundColor: dash.color, borderColor: dash.color }]}
                    onPress={() => setYoyTarget(t.id)}
                  >
                    <Text style={[styles.targetChipText, sel && { color: '#FFF' }]}>{t.label}</Text>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>

            {yoyLoading ? (
              <ActivityIndicator size="large" color={dash.color} style={{ marginTop: 40 }} />
            ) : yoyData?.blocked ? (
              <View style={styles.blockedCard}>
                <Ionicons name="lock-closed" size={28} color="#9CA3AF" />
                <Text style={styles.blockedTitle}>Insufficient sample size</Text>
                <Text style={styles.blockedTxt}>{yoyData.reason || 'Need more contributors before showing this insight.'}</Text>
                <Text style={styles.blockedHint}>Threshold: {yoyData.k_threshold || 30} responses minimum</Text>
              </View>
            ) : yoyData ? (
              <View>
                {/* Summary tiles */}
                <View style={styles.tileRow}>
                  <View style={[styles.tile, { borderLeftColor: dash.color }]}>
                    <Text style={styles.tileLabel}>Current 12 mo</Text>
                    <Text style={styles.tileValue}>{yoyData.current_year_total ?? 0}</Text>
                  </View>
                  <View style={[styles.tile, { borderLeftColor: '#94A3B8' }]}>
                    <Text style={styles.tileLabel}>Prior 12 mo</Text>
                    <Text style={styles.tileValue}>{yoyData.previous_year_total ?? 0}</Text>
                  </View>
                  <View style={[styles.tile, {
                    borderLeftColor: (yoyData.delta || 0) >= 0 ? '#10B981' : '#EF4444',
                  }]}>
                    <Text style={styles.tileLabel}>Δ</Text>
                    <Text style={[styles.tileValue, {
                      color: (yoyData.delta || 0) >= 0 ? '#10B981' : '#EF4444',
                    }]}>
                      {(yoyData.delta || 0) >= 0 ? '+' : ''}{yoyData.delta ?? 0}
                      {yoyData.overall_pct_change !== null && yoyData.overall_pct_change !== undefined && (
                        <Text style={styles.tilePct}>  ({yoyData.overall_pct_change >= 0 ? '+' : ''}{yoyData.overall_pct_change}%)</Text>
                      )}
                    </Text>
                  </View>
                </View>

                {/* Monthly compared bars */}
                <Text style={styles.sectionLabel}>Monthly comparison</Text>
                {(yoyData.series || []).map((s: any, i: number) => {
                  const max = Math.max(s.current || 0, s.previous || 0, 1);
                  const cw = Math.round(((s.current || 0) / max) * 100);
                  const pw = Math.round(((s.previous || 0) / max) * 100);
                  const upish = (s.delta || 0) > 0;
                  return (
                    <View key={i} style={styles.yoyRow}>
                      <Text style={styles.yoyMonth}>{s.month_label}</Text>
                      <View style={styles.yoyBars}>
                        <View style={styles.yoyBarTrack}>
                          <View style={[styles.yoyBarFill, { width: `${cw}%`, backgroundColor: dash.color }]} />
                        </View>
                        <View style={styles.yoyBarTrack}>
                          <View style={[styles.yoyBarFill, { width: `${pw}%`, backgroundColor: '#94A3B8' }]} />
                        </View>
                      </View>
                      <View style={{ width: 56, alignItems: 'flex-end' }}>
                        <Text style={[styles.yoyDelta, { color: (s.delta || 0) >= 0 ? '#10B981' : '#EF4444' }]}>
                          {upish ? '▲' : (s.delta < 0 ? '▼' : '–')} {s.delta}
                        </Text>
                        {s.pct_change !== null && (
                          <Text style={styles.yoyPct}>{s.pct_change > 0 ? '+' : ''}{s.pct_change}%</Text>
                        )}
                      </View>
                    </View>
                  );
                })}

                <View style={styles.legendRow}>
                  <View style={styles.legendDot} />
                  <Text style={styles.legendText}>Current</Text>
                  <View style={[styles.legendDot, { backgroundColor: '#94A3B8', marginLeft: 16 }]} />
                  <Text style={styles.legendText}>Previous</Text>
                </View>
              </View>
            ) : null}
          </View>
        ) : loading ? (
          <ActivityIndicator size="large" color={dash.color} style={{ marginTop: 40 }} />
        ) : data?.blocked ? (
          <View style={styles.blockedCard}>
            <Ionicons name="lock-closed" size={28} color="#9CA3AF" />
            <Text style={styles.blockedTitle}>Insufficient sample size</Text>
            <Text style={styles.blockedTxt}>{data.reason || 'Need more contributors before showing this insight.'}</Text>
            <Text style={styles.blockedHint}>Threshold: {k} responses minimum</Text>
          </View>
        ) : isFunnel ? (
          <View>
            {funnel.length === 0 && (
              <Text style={styles.emptyTxt}>No feedback yet</Text>
            )}
            {funnel.map((f: any, i: number) => {
              const pct = total ? Math.round((f.count / total) * 100) : 0;
              return (
                <View key={i} style={styles.row}>
                  <View style={styles.rowHeader}>
                    <Text style={styles.rowLabel}>{f.status?.toUpperCase().replace(/_/g, ' ')}</Text>
                    <Text style={styles.rowCount}>{f.count} ({pct}%)</Text>
                  </View>
                  <View style={styles.barBg}><View style={[styles.barFill, { width: `${pct}%`, backgroundColor: dash.color }]} /></View>
                </View>
              );
            })}
            <Text style={styles.privacyNote}>Total feedback items: {total}</Text>
          </View>
        ) : rows.length === 0 ? (
          <View style={styles.emptyCard}>
            <Ionicons name="hourglass" size={28} color="#9CA3AF" />
            <Text style={styles.emptyTitle}>Building up...</Text>
            <Text style={styles.emptyTxt}>Insights appear once enough people have contributed (k-threshold: {k}).</Text>
          </View>
        ) : (
          <View>
            {rows.map((r: any, i: number) => (
              <View key={i} style={styles.row}>
                <View style={styles.rowHeader}>
                  <Text style={styles.rowLabel}>{r.label}</Text>
                  <Text style={styles.rowCount}>{r.pct}% · {r.count}</Text>
                </View>
                <View style={styles.barBg}><View style={[styles.barFill, { width: `${r.pct || 0}%`, backgroundColor: dash.color }]} /></View>
              </View>
            ))}
            <Text style={styles.privacyNote}>
              Anonymized aggregate from {total} responses · k-threshold {k}
            </Text>
          </View>
        )}

        <View style={styles.privacyCard}>
          <Ionicons name="shield-checkmark" size={18} color="#10B981" />
          <Text style={styles.privacyTxt}>
            Individual responses are never shared. Insights only show when enough people contribute.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F9FAFB' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text },
  tabStrip: { maxHeight: 50, paddingVertical: 8 },
  tab: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20,
    backgroundColor: '#FFF', borderWidth: 1, borderColor: '#E5E7EB',
    marginRight: 8,
  },
  tabTxt: { fontSize: 12, fontWeight: '600', color: COLORS.text },
  dashHeader: { flexDirection: 'row', alignItems: 'center', borderRadius: 12, padding: 16, marginBottom: 16 },
  dashTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text },
  dashSubtitle: { fontSize: 12, color: '#6B7280', marginTop: 2 },
  row: { marginBottom: 14 },
  rowHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 6 },
  rowLabel: { fontSize: 13, fontWeight: '600', color: COLORS.text },
  rowCount: { fontSize: 12, color: '#6B7280' },
  barBg: { height: 8, backgroundColor: '#E5E7EB', borderRadius: 4, overflow: 'hidden' },
  barFill: { height: '100%', borderRadius: 4 },
  privacyNote: { fontSize: 11, color: '#9CA3AF', marginTop: 16, fontStyle: 'italic', textAlign: 'center' },
  privacyCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#ECFDF5', padding: 12, borderRadius: 10, marginTop: 16, gap: 10 },
  privacyTxt: { flex: 1, fontSize: 11, color: '#065F46', lineHeight: 16 },
  blockedCard: { alignItems: 'center', backgroundColor: '#FFF', padding: 24, borderRadius: 12, marginTop: 12 },
  blockedTitle: { fontSize: 16, fontWeight: '700', color: COLORS.text, marginTop: 12 },
  blockedTxt: { fontSize: 13, color: '#6B7280', textAlign: 'center', marginTop: 6 },
  blockedHint: { fontSize: 11, color: '#9CA3AF', marginTop: 8 },
  emptyCard: { alignItems: 'center', padding: 32 },
  emptyTitle: { fontSize: 15, fontWeight: '600', color: COLORS.text, marginTop: 12 },
  emptyTxt: { fontSize: 12, color: '#6B7280', textAlign: 'center', marginTop: 4, lineHeight: 18 },

  // YoY-specific
  targetChip: {
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: 14,
    backgroundColor: '#FFF', borderWidth: 1, borderColor: '#E5E7EB',
    marginRight: 6,
  },
  targetChipText: { fontSize: 12, fontWeight: '600', color: COLORS.text },
  tileRow: { flexDirection: 'row', gap: 8, marginBottom: 14 },
  tile: {
    flex: 1, backgroundColor: '#FFF', borderRadius: 10,
    paddingHorizontal: 12, paddingVertical: 10,
    borderLeftWidth: 4, borderLeftColor: '#8B5CF6',
  },
  tileLabel: { fontSize: 10, fontWeight: '700', color: '#6B7280', textTransform: 'uppercase', letterSpacing: 0.5 },
  tileValue: { fontSize: 18, fontWeight: '700', color: COLORS.text, marginTop: 2 },
  tilePct: { fontSize: 11, fontWeight: '600', color: '#6B7280' },
  sectionLabel: { fontSize: 13, fontWeight: '700', color: COLORS.text, marginTop: 8, marginBottom: 8 },
  yoyRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 8, gap: 8 },
  yoyMonth: { width: 64, fontSize: 11, color: '#6B7280' },
  yoyBars: { flex: 1, gap: 3 },
  yoyBarTrack: { height: 8, backgroundColor: '#F1F5F9', borderRadius: 4, overflow: 'hidden' },
  yoyBarFill: { height: '100%', borderRadius: 4 },
  yoyDelta: { fontSize: 11, fontWeight: '700' },
  yoyPct: { fontSize: 10, color: '#6B7280' },
  legendRow: {
    flexDirection: 'row', alignItems: 'center',
    marginTop: 12, justifyContent: 'center',
  },
  legendDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: '#8B5CF6', marginRight: 4 },
  legendText: { fontSize: 11, color: '#6B7280' },
});
