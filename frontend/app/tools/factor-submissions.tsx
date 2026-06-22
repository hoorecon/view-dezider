import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, FlatList, ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router, Stack } from 'expo-router';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { showAlert, confirmDialog } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';

const TABS: { key: string; label: string }[] = [
  { key: 'pending', label: 'Pending' },
  { key: 'approved', label: 'Approved' },
  { key: 'rejected', label: 'Rejected' },
];

export default function FactorSubmissions() {
  const [tab, setTab] = useState('pending');
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api.get('/solutions-store/factor-submissions', { params: { status: tab } });
      setItems(res.data?.items || []);
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Could not load submissions.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [tab]);

  useEffect(() => { setLoading(true); load(); }, [load]);

  const onRefresh = () => { setRefreshing(true); load(); };

  const approve = async (s: any) => {
    setBusyId(s.submission_id);
    try {
      const res = await api.post(`/solutions-store/factor-submissions/${s.submission_id}/approve`);
      setItems((prev) => prev.filter((i) => i.submission_id !== s.submission_id));
      showAlert('Approved', `${res.data?.applied_rows || 0} value(s) applied to "${s.solution_name}".`);
    } catch (e: any) {
      showAlert('Approve failed', e?.response?.data?.detail || 'Please try again.');
    } finally {
      setBusyId(null);
    }
  };

  const reject = async (s: any) => {
    const ok = await confirmDialog('Reject submission?', `Discard ${s.row_count} row(s) for "${s.solution_name}"?`, { confirmText: 'Reject', destructive: true });
    if (!ok) return;
    setBusyId(s.submission_id);
    try {
      await api.post(`/solutions-store/factor-submissions/${s.submission_id}/reject`, { note: 'Rejected by admin' });
      setItems((prev) => prev.filter((i) => i.submission_id !== s.submission_id));
    } catch (e: any) {
      showAlert('Reject failed', e?.response?.data?.detail || 'Please try again.');
    } finally {
      setBusyId(null);
    }
  };

  const renderItem = ({ item }: { item: any }) => {
    const isOpen = expanded === item.submission_id;
    const isBusy = busyId === item.submission_id;
    return (
      <View style={styles.card}>
        <TouchableOpacity
          style={styles.cardTop}
          onPress={() => setExpanded(isOpen ? null : item.submission_id)}
          activeOpacity={0.7}
        >
          <View style={{ flex: 1 }}>
            <Text style={styles.solName} numberOfLines={1}>{item.solution_name || item.solution_id}</Text>
            <Text style={styles.meta}>
              {(item.source || '').toUpperCase()} · {item.row_count} row(s) · by {item.submitted_by_name || 'user'}
            </Text>
            <Text style={styles.metaDate}>{new Date(item.created_at).toLocaleString()}</Text>
          </View>
          <Ionicons name={isOpen ? 'chevron-up' : 'chevron-down'} size={20} color={COLORS.textMuted} />
        </TouchableOpacity>

        {isOpen && (
          <View style={styles.rows}>
            {(item.rows || []).map((r: any, idx: number) => (
              <View key={idx} style={styles.rowLine}>
                <Text style={styles.rowName} numberOfLines={1}>{r.factor_name}</Text>
                <Text style={styles.rowVal}>
                  {String(r.value)}{r.unit ? ` ${r.unit}` : ''}{r.currency ? ` (${r.currency})` : ''}
                  <Text style={styles.rowType}> · {r.factor_type}</Text>
                </Text>
              </View>
            ))}
            {item.note ? <Text style={styles.note}>Note: {item.note}</Text> : null}
          </View>
        )}

        {tab === 'pending' && (
          <View style={styles.actions}>
            <TouchableOpacity style={styles.rejectBtn} onPress={() => reject(item)} disabled={isBusy}>
              <Ionicons name="close" size={16} color={COLORS.error} />
              <Text style={styles.rejectText}>Reject</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.approveBtn} onPress={() => approve(item)} disabled={isBusy}>
              {isBusy ? <ActivityIndicator size="small" color="#FFF" /> : <Ionicons name="checkmark" size={16} color="#FFF" />}
              <Text style={styles.approveText}>Approve & apply</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }} style={{ width: 44 }}>
          <Ionicons name="arrow-back" size={24} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Factor Submissions</Text>
        <View style={{ width: 44 }} />
      </View>

      <View style={styles.tabs}>
        {TABS.map((t) => (
          <TouchableOpacity key={t.key} style={[styles.tab, tab === t.key && styles.tabActive]} onPress={() => setTab(t.key)}>
            <Text style={[styles.tabText, tab === t.key && styles.tabTextActive]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <View style={styles.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>
      ) : items.length === 0 ? (
        <View style={styles.center}>
          <Ionicons name="file-tray-outline" size={52} color={COLORS.textMuted} />
          <Text style={styles.emptyText}>No {tab} submissions.</Text>
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(i) => i.submission_id}
          renderItem={renderItem}
          contentContainerStyle={{ padding: 16, paddingBottom: 32 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={COLORS.primary} />}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 12 },
  headerTitle: { fontSize: 18, fontWeight: '800', color: COLORS.textPrimary, flex: 1, textAlign: 'center' },
  tabs: { flexDirection: 'row', paddingHorizontal: 16, gap: 8, marginBottom: 8 },
  tab: { flex: 1, paddingVertical: 9, borderRadius: 10, backgroundColor: COLORS.white, borderWidth: 1, borderColor: COLORS.border, alignItems: 'center' },
  tabActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  tabText: { fontSize: 13, fontWeight: '700', color: COLORS.textSecondary },
  tabTextActive: { color: '#FFF' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 10 },
  emptyText: { fontSize: 14, color: COLORS.textMuted },
  card: { backgroundColor: COLORS.white, borderRadius: 14, borderWidth: 1, borderColor: COLORS.border, padding: 14, marginBottom: 12 },
  cardTop: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  solName: { fontSize: 15, fontWeight: '800', color: COLORS.textPrimary },
  meta: { fontSize: 12, color: COLORS.textSecondary, marginTop: 3 },
  metaDate: { fontSize: 11, color: COLORS.textMuted, marginTop: 1 },
  rows: { marginTop: 10, borderTopWidth: 1, borderTopColor: COLORS.border, paddingTop: 8 },
  rowLine: { flexDirection: 'row', justifyContent: 'space-between', gap: 10, paddingVertical: 4 },
  rowName: { flex: 1, fontSize: 13, color: COLORS.textPrimary, fontWeight: '600' },
  rowVal: { fontSize: 13, color: COLORS.textSecondary },
  rowType: { fontSize: 11, color: COLORS.textMuted },
  note: { fontSize: 12, color: COLORS.error, marginTop: 6, fontStyle: 'italic' },
  actions: { flexDirection: 'row', gap: 10, marginTop: 12 },
  rejectBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, borderWidth: 1.5, borderColor: COLORS.error, borderRadius: 10, paddingVertical: 10 },
  rejectText: { color: COLORS.error, fontWeight: '800', fontSize: 13 },
  approveBtn: { flex: 1.4, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#15803D', borderRadius: 10, paddingVertical: 10 },
  approveText: { color: '#FFF', fontWeight: '800', fontSize: 13 },
});
