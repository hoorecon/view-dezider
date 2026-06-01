/**
 * My Dezider — Listing screen.
 *
 * Mirrors the layout of /tools/swot list view but for Decider items.
 * - Shows all user Decisions (most recent first)
 * - Excludes SWOT-converted Deciders (those live under /tools/swot list)
 * - "+" header button opens the existing template/quick-pick screen
 *   at /tools/new-decision.
 * - Tap a row → opens /prr/<id>
 */
import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import { LIFE_AREAS as LIFE_AREAS_CANONICAL } from '../../src/constants/lifeAreas';
import { showAlert } from '../../src/utils/alert';
import { safeBack, goHome } from '../../src/utils/navigation';
import api from '../../src/utils/api';
import { formatAbsolute } from '../../src/utils/datetime';
import PaywallGate from '../../src/components/PaywallGate';
import TimestampLine from '../../src/components/TimestampLine';

interface DecisionItem {
  id: string;
  title: string;
  context?: string;
  folder?: string | null;
  life_area?: string | null;
  source_module?: string;
  status?: string;
  factors?: any[];
  options?: any[];
  chosen_option_id?: string | null;
  created_at: string;
  updated_at?: string;
}

const LIFE_AREA_LABELS: Record<string, { short: string; icon: string }> = LIFE_AREAS_CANONICAL.reduce(
  (acc: any, a: any) => { acc[a.id] = { short: a.short, icon: a.icon }; return acc; }, {}
);

function getStatus(d: DecisionItem): { label: string; color: string; bg: string } {
  if (d.status === 'completed' || d.chosen_option_id) {
    return { label: 'Completed', color: '#059669', bg: '#ECFDF5' };
  }
  const hasOptions = (d.options || []).length > 0;
  const hasFactors = (d.factors || []).length > 0;
  if (hasOptions && hasFactors) {
    return { label: 'In Progress', color: '#D97706', bg: '#FFFBEB' };
  }
  return { label: 'Draft', color: '#6B7280', bg: '#F3F4F6' };
}

export default function DeziderListScreen() {
  const router = useRouter();
  const [items, setItems] = useState<DecisionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchItems = async () => {
    try {
      const res = await api.get('/decisions');
      const all: DecisionItem[] = res.data || [];
      // Exclude SWOT-converted decisions — they live under the SWOT list.
      const onlyDezider = all.filter(d => d.source_module !== 'swot');
      // Backend already sorts created_at desc but be defensive.
      onlyDezider.sort((a, b) => (b.updated_at || b.created_at).localeCompare(a.updated_at || a.created_at));
      setItems(onlyDezider);
    } catch (err) {
      console.error('Error fetching decisions:', err);
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { fetchItems(); }, []));

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchItems();
    setRefreshing(false);
  };

  const handleDelete = async (id: string) => {
    showAlert(
      'Delete Decision?',
      'This will permanently remove this Decision and all its data.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete', style: 'destructive', onPress: async () => {
            try {
              await api.delete(`/decisions/${id}`);
              setItems(prev => prev.filter(it => it.id !== id));
            } catch (e) {
              showAlert('Delete Failed', 'Could not delete this decision. Please try again.');
            }
          }
        }
      ]
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <LinearGradient
        colors={['#6366F1', '#8B5CF6']}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.header}
      >
        <TouchableOpacity style={styles.backBtn} onPress={() => safeBack(router)}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>My Dezider</Text>
          <Text style={styles.headerSub}>10-step hybrid decision framework</Text>
        </View>
        <TouchableOpacity onPress={() => goHome(router)} style={[styles.backBtn, { marginRight: 8 }]} accessibilityLabel="Home">
          <Ionicons name="home" size={20} color="#FFF" />
        </TouchableOpacity>
        <PaywallGate module="dezider">
          <TouchableOpacity
            style={styles.createBtnHeader}
            onPress={() => router.push('/tools/new-decision?module=dezider' as any)}
          >
            <Ionicons name="add" size={22} color="#6366F1" />
          </TouchableOpacity>
        </PaywallGate>
      </LinearGradient>

      {loading ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={COLORS.primary} />
        </View>
      ) : (
        <ScrollView
          contentContainerStyle={{ padding: 16, paddingBottom: 100 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          showsVerticalScrollIndicator={false}
        >
          {/* How it works */}
          <View style={styles.howItWorks}>
            <Ionicons name="bulb-outline" size={20} color="#6366F1" />
            <Text style={styles.howItWorksText}>
              Make decisions with logic + emotion using a structured 10-step framework.
              For an even broader view across life areas, head to Solution Box.
            </Text>
          </View>

          {items.length === 0 ? (
            <View style={styles.emptyState}>
              <Ionicons name="compass-outline" size={48} color="#D1D5DB" />
              <Text style={styles.emptyStateTitle}>No Decisions Yet</Text>
              <Text style={styles.emptyStateText}>
                Start your first Decision — use a template or build from scratch.
              </Text>
              <PaywallGate module="dezider">
                <TouchableOpacity
                  style={styles.emptyCreateBtn}
                  onPress={() => router.push('/tools/new-decision' as any)}
                >
                  <Ionicons name="add" size={20} color="#FFF" />
                  <Text style={styles.emptyCreateText}>New Decision</Text>
                </TouchableOpacity>
              </PaywallGate>
            </View>
          ) : (
            items.map(d => {
              const status = getStatus(d);
              const lifeKey = (d.folder || d.life_area || '') as string;
              const lifeMeta = LIFE_AREA_LABELS[lifeKey];
              return (
                <TouchableOpacity
                  key={d.id}
                  style={styles.listCard}
                  onPress={() => router.push(`/prr/${d.id}` as any)}
                  activeOpacity={0.7}
                >
                  <View style={styles.listCardHeader}>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.listCardTitle} numberOfLines={1}>{d.title || 'Untitled Decision'}</Text>
                      {d.context ? <Text style={styles.listCardContext} numberOfLines={1}>{d.context}</Text> : null}
                    </View>
                    <View style={[styles.statusBadge, { backgroundColor: status.bg }]}>
                      <Text style={[styles.statusBadgeText, { color: status.color }]}>{status.label}</Text>
                    </View>
                  </View>

                  {/* Stats strip */}
                  <View style={styles.statsRow}>
                    <View style={styles.statChip}>
                      <Ionicons name="list-outline" size={12} color="#6366F1" />
                      <Text style={styles.statChipText}>{(d.factors || []).length} factors</Text>
                    </View>
                    <View style={styles.statChip}>
                      <Ionicons name="git-compare-outline" size={12} color="#8B5CF6" />
                      <Text style={styles.statChipText}>{(d.options || []).length} options</Text>
                    </View>
                    {lifeMeta ? (
                      <View style={styles.statChip}>
                        <Ionicons name={lifeMeta.icon as any} size={12} color={COLORS.textSecondary} />
                        <Text style={styles.statChipText}>{lifeMeta.short}</Text>
                      </View>
                    ) : null}
                  </View>

                  <View style={styles.listCardFooter}>
                    <Text style={styles.listCardDate}>
                      {formatAbsolute(d.updated_at || d.created_at)}
                    </Text>
                    <TimestampLine entity={d} compact />
                    <View style={{ flex: 1 }} />
                    <TouchableOpacity
                      style={styles.deleteBtn}
                      onPress={(e) => { e.stopPropagation(); handleDelete(d.id); }}
                      hitSlop={10}
                    >
                      <Ionicons name="trash-outline" size={16} color="#9CA3AF" />
                    </TouchableOpacity>
                  </View>
                </TouchableOpacity>
              );
            })
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },

  header: {
    flexDirection: 'row', alignItems: 'center',
    padding: 16, paddingTop: 12, paddingBottom: 20, gap: 12,
  },
  backBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center', alignItems: 'center',
  },
  headerTitle: { fontSize: 20, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 11, color: 'rgba(255,255,255,0.85)', marginTop: 2 },
  createBtnHeader: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: '#FFF',
    justifyContent: 'center', alignItems: 'center',
  },

  howItWorks: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 10,
    backgroundColor: '#EEF2FF', borderRadius: 12, padding: 14,
    marginBottom: 16, borderWidth: 1, borderColor: '#C7D2FE',
  },
  howItWorksText: { flex: 1, fontSize: 13, color: '#4338CA', lineHeight: 18 },

  emptyState: { alignItems: 'center', paddingVertical: 48, gap: 12 },
  emptyStateTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  emptyStateText: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', paddingHorizontal: 32 },
  emptyCreateBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: '#6366F1', paddingHorizontal: 20, paddingVertical: 12,
    borderRadius: 12, marginTop: 8,
  },
  emptyCreateText: { fontSize: 15, fontWeight: '600', color: '#FFF' },

  listCard: {
    backgroundColor: '#FFF', borderRadius: 14, padding: 16,
    marginBottom: 12, borderWidth: 1, borderColor: '#E5E7EB',
  },
  listCardHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  listCardTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  listCardContext: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },

  statusBadge: {
    paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8,
  },
  statusBadgeText: { fontSize: 11, fontWeight: '700' },

  statsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 10 },
  statChip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: '#F9FAFB', paddingHorizontal: 8, paddingVertical: 5,
    borderRadius: 8, borderWidth: 1, borderColor: '#E5E7EB',
  },
  statChipText: { fontSize: 11, fontWeight: '600', color: COLORS.textSecondary },

  listCardFooter: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  listCardDate: { fontSize: 11, color: COLORS.textMuted },
  deleteBtn: { padding: 6 },
});
