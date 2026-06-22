import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  FlatList,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router, Stack } from 'expo-router';
import { COLORS } from '../src/constants/colors';
import api from '../src/utils/api';
import { showAlert, confirmDialog } from '../src/utils/alert';
import { safeBack } from '../src/utils/navigation';

interface TrashItem {
  trash_id: string;
  module?: string;
  label?: string;
  title?: string;
  route?: string;
  deleted_at?: string;
  days_left: number;
}

const MODULE_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  pros_cons: 'swap-horizontal',
  decisions: 'git-compare',
  decision: 'git-compare',
  swot: 'grid',
  swot_analyses: 'grid',
  solution_finder: 'bulb',
  solution_finders: 'bulb',
  solution_matrix: 'apps',
  solution_matrices: 'apps',
};

function moduleIcon(module?: string): keyof typeof Ionicons.glyphMap {
  return (module && MODULE_ICONS[module]) || 'document-text';
}

function formatDate(iso?: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

export default function TrashScreen() {
  const [items, setItems] = useState<TrashItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [retentionDays, setRetentionDays] = useState(7);

  const load = useCallback(async () => {
    try {
      const res = await api.get('/trash');
      setItems(res.data?.items || []);
      if (res.data?.retention_days) setRetentionDays(res.data.retention_days);
    } catch (e: any) {
      showAlert('Could not load Trash', e?.response?.data?.detail || 'Please try again.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    load();
  };

  const handleRestore = async (item: TrashItem) => {
    if (busyId) return;
    setBusyId(item.trash_id);
    try {
      await api.post(`/trash/${item.trash_id}/restore`);
      setItems((prev) => prev.filter((i) => i.trash_id !== item.trash_id));
      showAlert('Restored', `"${item.title || item.label || 'Item'}" has been restored.`);
    } catch (e: any) {
      showAlert('Restore failed', e?.response?.data?.detail || 'Please try again.');
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (item: TrashItem) => {
    if (busyId) return;
    const ok = await confirmDialog(
      'Delete permanently?',
      `"${item.title || item.label || 'This item'}" will be gone for good and cannot be recovered.`,
      { confirmText: 'Delete', destructive: true }
    );
    if (!ok) return;
    setBusyId(item.trash_id);
    try {
      await api.delete(`/trash/${item.trash_id}`);
      setItems((prev) => prev.filter((i) => i.trash_id !== item.trash_id));
    } catch (e: any) {
      showAlert('Delete failed', e?.response?.data?.detail || 'Please try again.');
    } finally {
      setBusyId(null);
    }
  };

  const handleEmpty = async () => {
    if (items.length === 0) return;
    const ok = await confirmDialog(
      'Empty Trash?',
      `All ${items.length} item${items.length === 1 ? '' : 's'} will be permanently deleted and cannot be recovered.`,
      { confirmText: 'Empty Trash', destructive: true }
    );
    if (!ok) return;
    try {
      await api.delete('/trash');
      setItems([]);
    } catch (e: any) {
      showAlert('Could not empty Trash', e?.response?.data?.detail || 'Please try again.');
    }
  };

  const renderItem = ({ item }: { item: TrashItem }) => {
    const isBusy = busyId === item.trash_id;
    const urgent = item.days_left <= 2;
    return (
      <View style={styles.card}>
        <View style={[styles.iconWrap, { backgroundColor: 'rgba(100,116,139,0.12)' }]}>
          <Ionicons name={moduleIcon(item.module)} size={20} color="#64748B" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.title} numberOfLines={1}>
            {item.title || 'Untitled'}
          </Text>
          <View style={styles.metaRow}>
            {!!item.label && <Text style={styles.moduleTag}>{item.label}</Text>}
            <Text style={styles.metaText}>Deleted {formatDate(item.deleted_at)}</Text>
          </View>
          <View style={[styles.daysPill, urgent && styles.daysPillUrgent]}>
            <Ionicons
              name="time-outline"
              size={11}
              color={urgent ? '#B91C1C' : COLORS.textSecondary}
            />
            <Text style={[styles.daysText, urgent && { color: '#B91C1C' }]}>
              {item.days_left === 0
                ? 'Deletes today'
                : `${item.days_left} day${item.days_left === 1 ? '' : 's'} left`}
            </Text>
          </View>
        </View>
        <View style={styles.actions}>
          <TouchableOpacity
            style={styles.restoreBtn}
            onPress={() => handleRestore(item)}
            disabled={isBusy}
          >
            {isBusy ? (
              <ActivityIndicator size="small" color="#FFF" />
            ) : (
              <>
                <Ionicons name="arrow-undo" size={14} color="#FFF" />
                <Text style={styles.restoreText}>Restore</Text>
              </>
            )}
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.deleteBtn}
            onPress={() => handleDelete(item)}
            disabled={isBusy}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <Ionicons name="trash-outline" size={18} color={COLORS.error} />
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
      <Stack.Screen options={{ headerShown: false }} />
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity
          onPress={() => safeBack(router)}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          style={styles.backBtn}
        >
          <Ionicons name="arrow-back" size={24} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Recently Deleted</Text>
        {items.length > 0 ? (
          <TouchableOpacity onPress={handleEmpty} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
            <Text style={styles.emptyLink}>Empty</Text>
          </TouchableOpacity>
        ) : (
          <View style={{ width: 48 }} />
        )}
      </View>

      <Text style={styles.subtitle}>
        Deleted items are kept for {retentionDays} days, then removed automatically.
      </Text>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={COLORS.primary} />
        </View>
      ) : items.length === 0 ? (
        <View style={styles.center}>
          <Ionicons name="trash-bin-outline" size={56} color={COLORS.textMuted} />
          <Text style={styles.emptyTitle}>Trash is empty</Text>
          <Text style={styles.emptyDesc}>
            Items you delete will appear here for {retentionDays} days so you can restore them.
          </Text>
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(it) => it.trash_id}
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
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  backBtn: { width: 48, height: 40, justifyContent: 'center' },
  headerTitle: { fontSize: 18, fontWeight: '800', color: COLORS.textPrimary, flex: 1, textAlign: 'center' },
  emptyLink: { fontSize: 14, fontWeight: '700', color: COLORS.error, width: 48, textAlign: 'right' },
  subtitle: { fontSize: 12, color: COLORS.textMuted, paddingHorizontal: 16, marginBottom: 4, lineHeight: 17 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32, gap: 10 },
  emptyTitle: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary, marginTop: 6 },
  emptyDesc: { fontSize: 13, color: COLORS.textMuted, textAlign: 'center', lineHeight: 19 },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: COLORS.white,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: COLORS.border,
    padding: 14,
    marginBottom: 12,
  },
  iconWrap: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  metaRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 6, marginTop: 3 },
  moduleTag: {
    fontSize: 10,
    fontWeight: '700',
    color: '#475569',
    backgroundColor: '#E2E8F0',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 6,
    overflow: 'hidden',
  },
  metaText: { fontSize: 11, color: COLORS.textMuted },
  daysPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    alignSelf: 'flex-start',
    marginTop: 5,
    backgroundColor: '#F1F5F9',
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: 8,
  },
  daysPillUrgent: { backgroundColor: '#FEE2E2' },
  daysText: { fontSize: 10, fontWeight: '600', color: COLORS.textSecondary },
  actions: { alignItems: 'flex-end', gap: 8 },
  restoreBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    backgroundColor: COLORS.primary,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
    minWidth: 92,
    justifyContent: 'center',
  },
  restoreText: { color: '#FFF', fontSize: 13, fontWeight: '700' },
  deleteBtn: { padding: 4 },
});
