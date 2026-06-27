/**
 * My Published Solutions — creator hub for the Karma/Cash flywheel.
 *
 * Lists every option-published Store solution owned by the user with per-item
 * impact stats (uses · people · Karma · ₹earned) plus a header summary card
 * (Karma rank, totals). Backed by GET /api/option-publish/my-published.
 */
import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter, useFocusEffect } from 'expo-router';
import { COLORS } from '../../src/constants/colors';
import { safeBack } from '../../src/utils/navigation';
import api from '../../src/utils/api';

type Summary = {
  solutions: number;
  total_uses: number;
  total_unique_users: number;
  total_karma_earned: number;
  total_cash_earned: number;
  karma_balance: number;
  karma_rank: number;
};

type Item = {
  solution_id: string;
  name: string;
  type: string;
  usage_count: number;
  unique_users: number;
  karma_earned: number;
  cash_earned: number;
  monetization?: { mode?: string };
};

const TYPE_ICONS: Record<string, string> = {
  PRODUCT: 'cube', SERVICE: 'construct', EVENT: 'calendar',
  PROJECT: 'rocket', PERSON_CONTACT: 'person',
};

export default function MyPublishedScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [items, setItems] = useState<Item[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get('/option-publish/my-published');
      setItems(data.items || []);
      setSummary(data.summary || null);
    } catch {
      setItems([]);
      setSummary(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const renderSummary = () => {
    if (!summary) return null;
    return (
      <View style={styles.summaryCard}>
        <View style={styles.rankRow}>
          <Ionicons name="trophy" size={20} color={COLORS.warning} />
          <Text style={styles.rankText}>Karma rank #{summary.karma_rank}</Text>
          <View style={styles.balancePill}>
            <Ionicons name="sparkles" size={13} color={COLORS.primary} />
            <Text style={styles.balanceText}>{summary.karma_balance} balance</Text>
          </View>
        </View>
        <View style={styles.summaryStatsRow}>
          <View style={styles.summaryStat}>
            <Text style={styles.summaryNum}>{summary.solutions}</Text>
            <Text style={styles.summaryLabel}>published</Text>
          </View>
          <View style={styles.summaryStat}>
            <Text style={styles.summaryNum}>{summary.total_uses}</Text>
            <Text style={styles.summaryLabel}>total uses</Text>
          </View>
          <View style={styles.summaryStat}>
            <Text style={[styles.summaryNum, { color: COLORS.primary }]}>{summary.total_karma_earned}</Text>
            <Text style={styles.summaryLabel}>Karma earned</Text>
          </View>
          {summary.total_cash_earned > 0 && (
            <View style={styles.summaryStat}>
              <Text style={[styles.summaryNum, { color: COLORS.success }]}>₹{summary.total_cash_earned}</Text>
              <Text style={styles.summaryLabel}>earned</Text>
            </View>
          )}
        </View>
      </View>
    );
  };

  const renderItem = ({ item }: { item: Item }) => (
    <TouchableOpacity
      style={styles.card}
      activeOpacity={0.7}
      onPress={() => router.push({ pathname: '/tools/solution-detail', params: { solution_id: item.solution_id } } as any)}
      testID={`published-${item.solution_id}`}
    >
      <View style={styles.cardHead}>
        <View style={styles.typeChip}>
          <Ionicons name={(TYPE_ICONS[item.type] || 'cube') as any} size={12} color={COLORS.primary} />
          <Text style={styles.typeChipText}>{item.type?.replace('_', ' ')}</Text>
        </View>
        <View style={[styles.modeChip, item.monetization?.mode === 'paid' ? styles.modePaid : styles.modeFree]}>
          <Text style={[styles.modeChipText, { color: item.monetization?.mode === 'paid' ? COLORS.success : COLORS.primary }]}>
            {item.monetization?.mode === 'paid' ? 'Paid' : 'Free'}
          </Text>
        </View>
      </View>
      <Text style={styles.cardName} numberOfLines={1}>{item.name}</Text>
      <View style={styles.statsRow}>
        <View style={styles.stat}>
          <Ionicons name="hand-left-outline" size={14} color={COLORS.textSecondary} />
          <Text style={styles.statText}>{item.usage_count} {item.usage_count === 1 ? 'use' : 'uses'}</Text>
        </View>
        <View style={styles.stat}>
          <Ionicons name="people-outline" size={14} color={COLORS.textSecondary} />
          <Text style={styles.statText}>{item.unique_users}</Text>
        </View>
        <View style={styles.stat}>
          <Ionicons name="sparkles-outline" size={14} color={COLORS.primary} />
          <Text style={[styles.statText, { color: COLORS.primary }]}>{item.karma_earned} Karma</Text>
        </View>
        {item.cash_earned > 0 && (
          <View style={styles.stat}>
            <Ionicons name="cash-outline" size={14} color={COLORS.success} />
            <Text style={[styles.statText, { color: COLORS.success }]}>₹{item.cash_earned}</Text>
          </View>
        )}
      </View>
    </TouchableOpacity>
  );

  const renderEmpty = () => (
    <View style={styles.empty}>
      <Ionicons name="storefront-outline" size={56} color={COLORS.textMuted} />
      <Text style={styles.emptyTitle}>No published solutions yet</Text>
      <Text style={styles.emptyText}>
        Publish a Completed decider from your Solution Box to start earning Karma Points (and cash on paid use).
      </Text>
      <TouchableOpacity style={styles.emptyBtn} onPress={() => router.push('/(tabs)/prr' as any)}>
        <Ionicons name="arrow-back" size={16} color={COLORS.white} />
        <Text style={styles.emptyBtnText}>Go to Solution Box</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>My Published Solutions</Text>
          <Text style={styles.subtitle}>Track your impact & earnings</Text>
        </View>
      </View>

      {loading ? (
        <View style={styles.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>
      ) : (
        <FlatList
          data={items}
          renderItem={renderItem}
          keyExtractor={(it) => it.solution_id}
          contentContainerStyle={[styles.list, items.length === 0 && { flexGrow: 1 }]}
          showsVerticalScrollIndicator={false}
          ListHeaderComponent={items.length > 0 ? renderSummary() : null}
          ListEmptyComponent={renderEmpty}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 16, paddingTop: 8 },
  backBtn: { width: 40, height: 40, justifyContent: 'center' },
  title: { fontSize: 20, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 12, color: COLORS.textSecondary, marginTop: 1 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  list: { padding: 16, paddingTop: 4, paddingBottom: 100 },

  summaryCard: { backgroundColor: COLORS.white, borderRadius: 16, padding: 16, marginBottom: 14, borderWidth: 1, borderColor: COLORS.border },
  rankRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 14 },
  rankText: { fontSize: 15, fontWeight: '800', color: COLORS.textPrimary, flex: 1 },
  balancePill: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: COLORS.primary + '14', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 12 },
  balanceText: { fontSize: 12, fontWeight: '700', color: COLORS.primary },
  summaryStatsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 20 },
  summaryStat: { alignItems: 'center', minWidth: 64 },
  summaryNum: { fontSize: 22, fontWeight: '900', color: COLORS.textPrimary },
  summaryLabel: { fontSize: 11, color: COLORS.textSecondary, marginTop: 2 },

  card: { backgroundColor: COLORS.white, borderRadius: 14, padding: 14, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  cardHead: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  typeChip: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: COLORS.primary + '12', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10 },
  typeChipText: { fontSize: 10, fontWeight: '700', color: COLORS.primary },
  modeChip: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10, marginLeft: 'auto' },
  modeFree: { backgroundColor: COLORS.primary + '12' },
  modePaid: { backgroundColor: COLORS.success + '14' },
  modeChipText: { fontSize: 10, fontWeight: '700' },
  cardName: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 10 },
  statsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 14 },
  stat: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  statText: { fontSize: 12.5, color: COLORS.textSecondary, fontWeight: '600' },

  empty: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: 24 },
  emptyTitle: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary, marginTop: 12 },
  emptyText: { fontSize: 13, color: COLORS.textSecondary, textAlign: 'center', marginTop: 6, lineHeight: 19, marginBottom: 18 },
  emptyBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: COLORS.primary, paddingVertical: 11, paddingHorizontal: 18, borderRadius: 12 },
  emptyBtnText: { fontSize: 14, fontWeight: '700', color: COLORS.white },
});
