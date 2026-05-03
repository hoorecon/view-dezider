import React, { useState, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator, Dimensions,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

const AREA_ICONS: Record<string, string> = {
  holistic_health: 'fitness', knowledge_skills: 'school', relationships: 'heart',
  finance: 'cash', assets: 'home', career: 'briefcase', personal_dreams: 'star',
  social_image: 'people', social_contributions: 'hand-left', spirituality: 'leaf',
};

function netColor(n: number) {
  if (n > 0) return '#10B981';
  if (n < 0) return '#EF4444';
  return '#6B7280';
}

export default function AALAScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [dashboard, setDashboard] = useState<any>(null);
  const [assessments, setAssessments] = useState<any[]>([]);

  const fetchData = async () => {
    try {
      const [dashRes, listRes] = await Promise.all([
        api.get('/aala/dashboard'),
        api.get('/aala/assessments'),
      ]);
      setDashboard(dashRes.data);
      setAssessments(listRes.data || []);
    } catch (e) { console.error('AALA fetch error:', e); }
    finally { setLoading(false); }
  };

  useFocusEffect(useCallback(() => { setLoading(true); fetchData(); }, []));
  const onRefresh = async () => { setRefreshing(true); await fetchData(); setRefreshing(false); };

  const handleDelete = (id: string) => {
    showAlert('Delete', 'Delete this assessment?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await api.delete(`/aala/assessments/${id}`); fetchData(); }
        catch (e) { showAlert('Error', 'Failed to delete'); }
      }},
    ]);
  };

  const renderNetPosition = () => {
    if (!dashboard?.net_position_by_area || Object.keys(dashboard.net_position_by_area).length === 0) return null;
    const net = dashboard.net_position_by_area;
    return (
      <View style={s.netCard}>
        <Text style={s.netTitle}>Net Position by Life Area</Text>
        {Object.entries(net).map(([area, data]: [string, any]) => (
          <View key={area} style={s.netRow}>
            <Ionicons name={(AREA_ICONS[area] || 'ellipse') as any} size={14} color={COLORS.textSecondary} />
            <Text style={s.netArea} numberOfLines={1}>{area.replace(/_/g, ' ')}</Text>
            <View style={s.netValues}>
              <Text style={[s.netVal, { color: '#10B981' }]}>A: {data.total_assets}</Text>
              <Text style={[s.netVal, { color: '#EF4444' }]}>L: {data.total_liabilities}</Text>
              <Text style={[s.netVal, { color: netColor(data.net), fontWeight: '700' }]}>
                Net: {data.net > 0 ? '+' : ''}{data.net}
              </Text>
            </View>
          </View>
        ))}
      </View>
    );
  };

  const renderEntry = (item: any) => {
    const entryCount = (item.entries || []).length;
    return (
      <TouchableOpacity
        key={item.assessment_id}
        style={s.entryCard}
        onPress={() => router.push({ pathname: '/tools/aala-entry', params: { id: item.assessment_id } })}
      >
        <View style={s.entryRow}>
          <View style={{ flex: 1 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              {item.is_baseline && (
                <View style={s.baselineBadge}>
                  <Text style={s.baselineText}>BASELINE</Text>
                </View>
              )}
              <Text style={s.entryTitle} numberOfLines={1}>{item.title}</Text>
            </View>
            <Text style={s.entrySub}>
              {item.snapshot_date} · {entryCount} entries · {item.tracking_frequency}
            </Text>
          </View>
          <TouchableOpacity onPress={() => handleDelete(item.assessment_id)} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
            <Ionicons name="trash-outline" size={16} color={COLORS.textMuted} />
          </TouchableOpacity>
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <LinearGradient colors={['#0EA5E9', '#2563EB']} style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.backBtn}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.headerTitle}>AALA — Assets & Liabilities</Text>
          <Text style={s.headerSub}>
            {dashboard?.total_assessments || 0} assessments · Circle of Influence
          </Text>
        </View>
        <TouchableOpacity onPress={() => router.push('/tools/aala-entry')} style={s.addBtn}>
          <Ionicons name="add" size={22} color="#FFF" />
        </TouchableOpacity>
      </LinearGradient>

      {loading ? (
        <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <ActivityIndicator size="large" color="#2563EB" />
        </View>
      ) : (
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ padding: 16, paddingBottom: 32 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          {/* Quick stats */}
          {dashboard && dashboard.total_assessments > 0 && (
            <View style={s.statsRow}>
              <View style={s.statBox}>
                <Text style={s.statNum}>{dashboard.total_assessments}</Text>
                <Text style={s.statLabel}>Assessments</Text>
              </View>
              <View style={s.statBox}>
                <Text style={s.statNum}>{dashboard.baseline ? '✓' : '—'}</Text>
                <Text style={s.statLabel}>Baseline</Text>
              </View>
              <View style={s.statBox}>
                <Text style={s.statNum}>{dashboard.tracking_frequency}</Text>
                <Text style={s.statLabel}>Frequency</Text>
              </View>
            </View>
          )}

          {renderNetPosition()}

          {assessments.length === 0 ? (
            <View style={s.empty}>
              <View style={s.emptyIcon}>
                <Ionicons name="wallet-outline" size={48} color={COLORS.textMuted} />
              </View>
              <Text style={s.emptyTitle}>No AALA Assessments Yet</Text>
              <Text style={s.emptySub}>
                Assess your Assets & Liabilities across 10 life areas to understand your Circle of Influence
              </Text>
              <TouchableOpacity
                style={s.emptyBtn}
                onPress={() => router.push({ pathname: '/tools/aala-entry', params: { baseline: 'true' } })}
              >
                <Ionicons name="add-circle" size={18} color="#FFF" />
                <Text style={s.emptyBtnText}>Create Baseline Assessment</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <>
              <Text style={s.sectionTitle}>All Assessments</Text>
              {assessments.map(renderEntry)}
              <TouchableOpacity
                style={s.newSnapshotBtn}
                onPress={() => router.push('/tools/aala-entry')}
              >
                <Ionicons name="camera" size={16} color="#2563EB" />
                <Text style={s.newSnapshotText}>Take New Snapshot</Text>
              </TouchableOpacity>
            </>
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

  statsRow: { flexDirection: 'row', gap: 10, marginBottom: 16 },
  statBox: { flex: 1, backgroundColor: COLORS.white, borderRadius: 12, padding: 12, alignItems: 'center', borderWidth: 1, borderColor: COLORS.border },
  statNum: { fontSize: 18, fontWeight: '700', color: '#2563EB' },
  statLabel: { fontSize: 10, color: COLORS.textMuted, marginTop: 2, textTransform: 'uppercase' },

  netCard: { backgroundColor: COLORS.white, borderRadius: 14, padding: 14, marginBottom: 16, borderWidth: 1, borderColor: COLORS.border },
  netTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 10 },
  netRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  netArea: { flex: 1, fontSize: 12, fontWeight: '500', color: COLORS.textPrimary, textTransform: 'capitalize' },
  netValues: { flexDirection: 'row', gap: 8 },
  netVal: { fontSize: 11, fontWeight: '500' },

  sectionTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 10 },
  entryCard: { backgroundColor: COLORS.white, borderRadius: 12, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border },
  entryRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  entryTitle: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary },
  entrySub: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },
  baselineBadge: { backgroundColor: '#0EA5E915', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 },
  baselineText: { fontSize: 9, fontWeight: '700', color: '#0EA5E9' },

  newSnapshotBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 14, borderRadius: 12, borderWidth: 1.5, borderColor: '#2563EB', borderStyle: 'dashed', marginTop: 8 },
  newSnapshotText: { fontSize: 14, fontWeight: '600', color: '#2563EB' },

  empty: { alignItems: 'center', paddingTop: 40 },
  emptyIcon: { width: 80, height: 80, borderRadius: 40, backgroundColor: COLORS.divider, justifyContent: 'center', alignItems: 'center', marginBottom: 16 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  emptySub: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', marginTop: 8, paddingHorizontal: 32, lineHeight: 20 },
  emptyBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 20, paddingHorizontal: 20, paddingVertical: 12, backgroundColor: '#2563EB', borderRadius: 12 },
  emptyBtnText: { fontSize: 14, fontWeight: '600', color: '#FFF' },
});
