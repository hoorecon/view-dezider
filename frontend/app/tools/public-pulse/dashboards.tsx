import React, { useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../../src/constants/colors';
import api from '../../../src/utils/api';

const DASHBOARDS = [
  { key: 'district-demand-heatmap', title: 'District Demand', subtitle: 'Where the action is', icon: 'map', color: '#6366F1' },
  { key: 'youth-job-priority', title: 'Youth Job Priorities', subtitle: 'What 18-34 are choosing', icon: 'briefcase', color: '#10B981' },
  { key: 'marriage-support-need', title: 'Marriage Support Need', subtitle: 'Top concerns', icon: 'heart', color: '#EC4899' },
  { key: 'scheme-awareness', title: 'Scheme Demand', subtitle: 'What people need most', icon: 'ribbon', color: '#F59E0B' },
  { key: 'rectification-tracker', title: 'Rectification Tracker', subtitle: 'Issues → Resolution', icon: 'checkmark-done', color: '#3B82F6' },
];

export default function DashboardsScreen() {
  const router = useRouter();
  const [active, setActive] = useState(DASHBOARDS[0].key);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchDashboard = async (key: string) => {
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

  useFocusEffect(useCallback(() => { fetchDashboard(active); }, [active]));

  const dash = DASHBOARDS.find((d) => d.key === active)!;
  // Normalise rows — most dashboards return {data:[]}, marriage_support returns {by_concern:{data:[]}}
  const rows = data?.data || data?.by_concern?.data || [];
  const k = data?.k_threshold || data?.by_concern?.k_threshold || 0;
  const total = data?.total_in_aggregate || data?.by_concern?.total_in_aggregate || data?.total || 0;
  const isFunnel = active === 'rectification-tracker';
  const funnel = data?.funnel || [];

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={28} color={COLORS.text} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Public Insights</Text>
        <View style={{ width: 28 }} />
      </View>

      {/* Tab strip */}
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

        {loading ? (
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
            Individual responses are never shared. Insights only show when {k}+ people contribute.
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
});
