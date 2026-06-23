/**
 * Karma & Fame (Collaboration Epic Phase F).
 * Your karma balance + rank + how you earned it, plus the public leaderboard.
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import api from '../src/utils/api';
import { safeBack } from '../src/utils/navigation';

const EVENT_LABEL: Record<string, string> = {
  contribution_accepted: 'Accepted contributions',
  decision_cloned_free: 'Free clones of your decisions',
  decision_cloned_paid: 'Paid clones of your decisions',
  positive_rating: 'Positive ratings received',
  public_help_resolved: 'Resolved help requests',
  spend: 'Karma spent',
};

function Stars({ avg, size = 13 }: { avg?: number | null; size?: number }) {
  if (avg == null) return <Text style={{ fontSize: size - 1, color: '#94A3B8' }}>No ratings</Text>;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 2 }}>
      {[1, 2, 3, 4, 5].map(i => (
        <Ionicons key={i} name={avg >= i ? 'star' : avg >= i - 0.5 ? 'star-half' : 'star-outline'} size={size} color="#F59E0B" />
      ))}
      <Text style={{ fontSize: size - 1, color: '#64748B', marginLeft: 3 }}>{avg.toFixed(1)}</Text>
    </View>
  );
}

export default function LeaderboardScreen() {
  const router = useRouter();
  const [me, setMe] = useState<any>(null);
  const [board, setBoard] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [m, b] = await Promise.all([api.get('/karma/me'), api.get('/karma/leaderboard')]);
      setMe(m.data); setBoard(b.data?.items || []);
    } catch { /* noop */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const medal = (rank: number) => rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : `#${rank}`;

  if (loading) return (
    <SafeAreaView style={styles.container} edges={['top']}><ActivityIndicator style={{ marginTop: 60 }} color="#F59E0B" /></SafeAreaView>
  );

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={['#F59E0B', '#D97706']} style={styles.header}>
        <TouchableOpacity style={styles.iconHdr} onPress={() => safeBack(router)}><Ionicons name="arrow-back" size={22} color="#FFF" /></TouchableOpacity>
        <Text style={styles.headerTitle}>Karma & Fame</Text>
        <View style={{ width: 38 }} />
      </LinearGradient>

      <ScrollView
        contentContainerStyle={{ padding: 16, paddingBottom: 50 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={async () => { setRefreshing(true); await load(); setRefreshing(false); }} />}
      >
        {/* my karma */}
        <LinearGradient colors={['#F59E0B', '#FBBF24']} style={styles.karmaCard}>
          <View style={styles.karmaTop}>
            <View>
              <Text style={styles.karmaLabel}>Your Karma</Text>
              <Text style={styles.karmaValue}>{me?.karma_balance ?? 0} <Text style={styles.karmaUnit}>KP</Text></Text>
            </View>
            <View style={styles.rankBadge}>
              <Text style={styles.rankText}>Rank {medal(me?.rank ?? 0)}</Text>
            </View>
          </View>
          <View style={styles.fameRow}>
            <Ionicons name="ribbon" size={15} color="#FFF" />
            <Text style={styles.fameText}>Fame rating: </Text>
            {me?.fame_rating_avg != null
              ? <Text style={styles.fameVal}>{me.fame_rating_avg.toFixed(1)}★ ({me.fame_rating_count})</Text>
              : <Text style={styles.fameVal}>Not rated yet</Text>}
          </View>
        </LinearGradient>

        {/* breakdown */}
        {me?.breakdown && Object.keys(me.breakdown).length > 0 && (
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>How you earned it</Text>
            {Object.entries(me.breakdown).map(([k, v]: any) => (
              <View key={k} style={styles.bdRow}>
                <Text style={styles.bdLabel}>{EVENT_LABEL[k] || k}</Text>
                <Text style={[styles.bdValue, v < 0 && { color: '#EF4444' }]}>{v > 0 ? '+' : ''}{v} KP</Text>
              </View>
            ))}
          </View>
        )}

        {/* leaderboard */}
        <Text style={styles.boardTitle}>🏆 Leaderboard</Text>
        {board.length === 0 ? (
          <Text style={styles.empty}>No one has earned karma yet. Help others, share decisions, and climb the ranks!</Text>
        ) : board.map((u) => (
          <TouchableOpacity
            key={u.user_id}
            style={[styles.boardRow, u.is_me && styles.boardRowMe]}
            onPress={() => router.push(`/fame/${u.user_id}` as any)}
            activeOpacity={0.8}
          >
            <Text style={styles.rank}>{medal(u.rank)}</Text>
            <View style={{ flex: 1 }}>
              <Text style={styles.boardName}>{u.name}{u.is_me ? ' (you)' : ''}</Text>
              <Stars avg={u.fame_rating_avg} size={11} />
            </View>
            <Text style={styles.boardKarma}>{u.karma_balance} KP</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 10, paddingVertical: 14 },
  iconHdr: { width: 38, height: 38, alignItems: 'center', justifyContent: 'center' },
  headerTitle: { flex: 1, fontSize: 18, fontWeight: '800', color: '#FFF', textAlign: 'center' },
  karmaCard: { borderRadius: 18, padding: 20, marginBottom: 16 },
  karmaTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  karmaLabel: { fontSize: 13, color: '#FFF7ED', fontWeight: '600' },
  karmaValue: { fontSize: 40, fontWeight: '900', color: '#FFF', marginTop: 2 },
  karmaUnit: { fontSize: 18, fontWeight: '700' },
  rankBadge: { backgroundColor: 'rgba(255,255,255,0.25)', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 12 },
  rankText: { fontSize: 14, fontWeight: '800', color: '#FFF' },
  fameRow: { flexDirection: 'row', alignItems: 'center', marginTop: 12 },
  fameText: { fontSize: 13, color: '#FFF7ED', fontWeight: '600' },
  fameVal: { fontSize: 13, color: '#FFF', fontWeight: '800' },
  card: { backgroundColor: '#FFF', borderRadius: 14, padding: 14, marginBottom: 16, borderWidth: 1, borderColor: '#E2E8F0' },
  sectionTitle: { fontSize: 14, fontWeight: '800', color: '#0F172A', marginBottom: 8 },
  bdRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  bdLabel: { fontSize: 13, color: '#475569', flex: 1 },
  bdValue: { fontSize: 13, fontWeight: '800', color: '#16A34A' },
  boardTitle: { fontSize: 16, fontWeight: '800', color: '#0F172A', marginBottom: 10 },
  empty: { fontSize: 13, color: '#94A3B8', lineHeight: 18 },
  boardRow: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#FFF', borderRadius: 12, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: '#EEF2F7' },
  boardRowMe: { borderColor: '#F59E0B', backgroundColor: '#FFFBEB' },
  rank: { fontSize: 16, fontWeight: '800', color: '#0F172A', width: 40, textAlign: 'center' },
  boardName: { fontSize: 14, fontWeight: '700', color: '#0F172A' },
  boardKarma: { fontSize: 15, fontWeight: '800', color: '#D97706' },
});
