/**
 * /tools/today — Today's Plan
 * Combined view of TODAY's items only:
 *   • On-demand actions (Action Tracker, still open)  — badge "On-demand"
 *   • Routine items due today (Lifestyle)             — badge "Routine"
 * Routines can be toggled complete inline; actions open the Action Tracker.
 */
import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';

const C = {
  primary: '#4338CA', text: '#0F172A', muted: '#64748B', border: '#E2E8F0',
  bg: '#F8FAFC', white: '#FFF', action: '#0D9488', routine: '#EA580C', done: '#10B981',
};

const OPEN_DONE = ['done', 'completed', 'cancelled', 'archived'];

export default function TodayScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [actions, setActions] = useState<any[]>([]);
  const [routines, setRoutines] = useState<any[]>([]);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [actRes, todayRes] = await Promise.all([
        api.get('/action-items').catch(() => ({ data: [] })),
        api.get('/lifestyle/today-status').catch(() => ({ data: null })),
      ]);
      const acts = (actRes.data || []).filter(
        (it: any) => !OPEN_DONE.includes(String(it.status || '').toLowerCase())
      );
      setActions(acts);
      setRoutines((todayRes.data && todayRes.data.routines) || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const toggleRoutine = async (r: any) => {
    const id = r.routine_id || r.id;
    setTogglingId(id);
    try {
      if (r.completed_today) await api.delete(`/lifestyle/routines/${id}/uncomplete`);
      else await api.post(`/lifestyle/routines/${id}/complete`, {});
      await load();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Could not update.');
    } finally { setTogglingId(null); }
  };

  const todayLabel = new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' });
  const total = actions.length + routines.length;
  const doneCount = routines.filter((r: any) => r.completed_today).length;

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => safeBack(router)} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Ionicons name="arrow-back" size={24} color={C.text} />
        </TouchableOpacity>
        <View style={{ flex: 1, marginLeft: 12 }}>
          <Text style={s.title}>Today&apos;s Plan</Text>
          <Text style={s.subtitle}>{todayLabel}</Text>
        </View>
        <View style={s.countPill}><Text style={s.countPillText}>{doneCount}/{total}</Text></View>
      </View>

      {loading ? (
        <ActivityIndicator style={{ marginTop: 60 }} color={C.primary} />
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: 16, paddingBottom: 100 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        >
          {total === 0 ? (
            <View style={s.empty}>
              <Ionicons name="checkmark-done-circle-outline" size={48} color={C.muted} />
              <Text style={s.emptyText}>Nothing on your plate today. Enjoy! 🎉</Text>
            </View>
          ) : (
            <>
              {/* On-demand actions */}
              {actions.length > 0 && <Text style={s.groupLabel}>On-demand actions</Text>}
              {actions.map((it: any) => (
                <TouchableOpacity
                  key={it.action_id || it.id}
                  style={s.row}
                  onPress={() => router.push('/tools/action-center' as any)}
                >
                  <View style={[s.dot, { backgroundColor: C.action }]} />
                  <View style={{ flex: 1 }}>
                    <Text style={s.rowTitle} numberOfLines={2}>{it.title || it.name || 'Action'}</Text>
                    <View style={s.rowMeta}>
                      <View style={[s.badge, { backgroundColor: C.action + '1A' }]}>
                        <Text style={[s.badgeText, { color: C.action }]}>On-demand</Text>
                      </View>
                      {!!it.status && <Text style={s.metaText}>{it.status}</Text>}
                    </View>
                  </View>
                  <Ionicons name="chevron-forward" size={18} color={C.muted} />
                </TouchableOpacity>
              ))}

              {/* Routine items */}
              {routines.length > 0 && <Text style={[s.groupLabel, { marginTop: 18 }]}>Today&apos;s routines</Text>}
              {routines.map((r: any) => {
                const id = r.routine_id || r.id;
                const done = !!r.completed_today;
                return (
                  <TouchableOpacity key={id} style={s.row} onPress={() => toggleRoutine(r)} disabled={togglingId === id}>
                    {togglingId === id
                      ? <ActivityIndicator size="small" color={C.routine} style={{ width: 24 }} />
                      : <Ionicons name={done ? 'checkmark-circle' : 'ellipse-outline'} size={24} color={done ? C.done : '#CBD5E1'} />}
                    <View style={{ flex: 1, marginLeft: 8 }}>
                      <Text style={[s.rowTitle, done && s.rowTitleDone]} numberOfLines={2}>
                        {r.name || r.routine_name || r.title || 'Routine'}
                      </Text>
                      <View style={s.rowMeta}>
                        <View style={[s.badge, { backgroundColor: C.routine + '1A' }]}>
                          <Text style={[s.badgeText, { color: C.routine }]}>Routine</Text>
                        </View>
                        {!!r.scheduled_time && <Text style={s.metaText}>{r.scheduled_time}</Text>}
                      </View>
                    </View>
                  </TouchableOpacity>
                );
              })}
            </>
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: C.bg },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12, backgroundColor: C.white, borderBottomWidth: 1, borderBottomColor: C.border },
  title: { fontSize: 18, fontWeight: '800', color: C.text },
  subtitle: { fontSize: 12, color: C.muted, marginTop: 1 },
  countPill: { backgroundColor: C.primary + '15', borderRadius: 20, paddingHorizontal: 12, paddingVertical: 6 },
  countPillText: { fontSize: 13, fontWeight: '800', color: C.primary },
  groupLabel: { fontSize: 13, fontWeight: '800', color: C.muted, marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 },
  row: { flexDirection: 'row', alignItems: 'center', backgroundColor: C.white, borderRadius: 12, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: C.border },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: 12 },
  rowTitle: { fontSize: 14.5, fontWeight: '600', color: C.text },
  rowTitleDone: { textDecorationLine: 'line-through', color: C.muted },
  rowMeta: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 5 },
  badge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6 },
  badgeText: { fontSize: 11, fontWeight: '800' },
  metaText: { fontSize: 11, color: C.muted, textTransform: 'capitalize' },
  empty: { alignItems: 'center', paddingVertical: 60, gap: 12 },
  emptyText: { fontSize: 14, color: C.muted, textAlign: 'center' },
});
