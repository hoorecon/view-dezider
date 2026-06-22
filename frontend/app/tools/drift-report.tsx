/**
 * /tools/drift-report  — LDC ideal vs daily-tracker actuals.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { COLORS } from '../../src/constants/colors';
import { safeBack } from '../../src/utils/navigation';

export default function DriftReportScreen() {
  const router = useRouter();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(7);

  const load = useCallback(async () => {
    try { setLoading(true);
      const r = await api.get(`/time-allocation/drift?days=${days}`);
      setData(r.data);
    } finally { setLoading(false); }
  }, [days]);
  useEffect(() => { load(); }, [load]);

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => safeBack(router)}><Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} /></TouchableOpacity>
        <View style={{ flex: 1, marginHorizontal: 12 }}>
          <Text style={s.title}>Drift Report</Text>
          <Text style={s.subtitle}>Compass said … vs You actually did</Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={{ padding: 14, paddingBottom: 60 }}>
        <View style={{ flexDirection: 'row', gap: 6, marginBottom: 12 }}>
          {[7, 14, 30].map(d => (
            <TouchableOpacity key={d} onPress={() => setDays(d)} style={[s.dayChip, days === d && s.dayChipActive]}>
              <Text style={[s.dayChipText, days === d && s.dayChipTextActive]}>{d}d</Text>
            </TouchableOpacity>
          ))}
        </View>

        {loading ? <ActivityIndicator color={COLORS.primary} /> : !data?.drifts?.length ? (
          <View style={s.empty}>
            <Ionicons name="information-circle" size={36} color={COLORS.textMuted} />
            <Text style={s.emptyText}>{data?.message || 'Log some daily-tracker entries first to see drift.'}</Text>
          </View>
        ) : (
          <>
            <Text style={s.helper}>{data.total_minutes} min logged in the last {days} days{data.untagged_minutes > 0 ? ` (${data.untagged_minutes} min un-tagged — add freedom labels for sharper drift)` : ''}.</Text>
            {data.drifts.map((d: any) => (
              <View key={d.freedom} style={[s.card, d.status === 'over' && { borderLeftColor: '#F59E0B', borderLeftWidth: 4 }, d.status === 'under' && { borderLeftColor: '#DC2626', borderLeftWidth: 4 }, d.status === 'aligned' && { borderLeftColor: '#10B981', borderLeftWidth: 4 }]}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Text style={s.freedomName}>{d.freedom.toUpperCase()}</Text>
                  <Text style={[s.statusBadge, { backgroundColor: d.status === 'aligned' ? '#10B98122' : d.status === 'over' ? '#F59E0B22' : '#DC262622', color: d.status === 'aligned' ? '#059669' : d.status === 'over' ? '#D97706' : '#DC2626' }]}>{d.status}</Text>
                </View>
                <View style={{ flexDirection: 'row', gap: 14, marginTop: 6 }}>
                  <View><Text style={s.kpiLabel}>Ideal</Text><Text style={s.kpiVal}>{d.ideal_pct}%</Text></View>
                  <View><Text style={s.kpiLabel}>Actual</Text><Text style={s.kpiVal}>{d.actual_pct}%</Text></View>
                  <View><Text style={s.kpiLabel}>Drift</Text><Text style={[s.kpiVal, { color: d.drift_pct > 0 ? '#D97706' : d.drift_pct < 0 ? '#DC2626' : '#10B981' }]}>{d.drift_pct >= 0 ? '+' : ''}{d.drift_pct}%</Text></View>
                </View>
                {d.suggested_correction_minutes !== 0 && (
                  <Text style={s.suggestion}>
                    {d.suggested_correction_minutes > 0 ? `↑ Invest ${d.suggested_correction_minutes} more min` : `↓ Reallocate ${Math.abs(d.suggested_correction_minutes)} min away`} (next {days} days)
                  </Text>
                )}
              </View>
            ))}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingVertical: 10, backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  title: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  helper: { fontSize: 11, color: COLORS.textMuted, marginBottom: 10 },
  dayChip: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 14, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.white },
  dayChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  dayChipText: { fontSize: 12, color: COLORS.textSecondary, fontWeight: '600' },
  dayChipTextActive: { color: '#FFF' },
  card: { backgroundColor: COLORS.white, padding: 14, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border, marginBottom: 10 },
  freedomName: { fontSize: 13, fontWeight: '700', color: COLORS.textPrimary, letterSpacing: 0.3 },
  statusBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4, fontSize: 10, fontWeight: '700', textTransform: 'uppercase' },
  kpiLabel: { fontSize: 10, color: COLORS.textMuted, fontWeight: '600', textTransform: 'uppercase' },
  kpiVal: { fontSize: 16, fontWeight: '800', color: COLORS.textPrimary, marginTop: 2 },
  suggestion: { fontSize: 11, color: COLORS.textSecondary, marginTop: 8, fontStyle: 'italic' },
  empty: { alignItems: 'center', padding: 40 },
  emptyText: { fontSize: 12, color: COLORS.textMuted, marginTop: 8, textAlign: 'center' },
});
