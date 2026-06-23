/**
 * Public Fame profile (Collaboration Epic Phase F) — /fame/[id].
 */
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import api from '../../src/utils/api';
import { safeBack } from '../../src/utils/navigation';

export default function FameProfileScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const [p, setP] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try { const r = await api.get(`/karma/profile/${id}`); setP(r.data); }
      catch { /* noop */ }
      finally { setLoading(false); }
    })();
  }, [id]);

  if (loading) return (<SafeAreaView style={styles.container} edges={['top']}><ActivityIndicator style={{ marginTop: 60 }} color="#F59E0B" /></SafeAreaView>);

  const medal = (rank: number) => rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : `#${rank}`;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <LinearGradient colors={['#F59E0B', '#D97706']} style={styles.header}>
        <TouchableOpacity style={styles.iconHdr} onPress={() => safeBack(router)}><Ionicons name="arrow-back" size={22} color="#FFF" /></TouchableOpacity>
        <Text style={styles.headerTitle}>Fame Profile</Text>
        <View style={{ width: 38 }} />
      </LinearGradient>
      <ScrollView contentContainerStyle={{ padding: 16 }}>
        <View style={styles.hero}>
          <View style={styles.avatar}><Text style={styles.avatarText}>{(p?.name || '?').charAt(0).toUpperCase()}</Text></View>
          <Text style={styles.name}>{p?.name}</Text>
          <Text style={styles.rank}>Rank {medal(p?.rank ?? 0)}</Text>
          <View style={styles.statsRow}>
            <View style={styles.statBox}><Text style={styles.statNum}>{p?.karma_balance ?? 0}</Text><Text style={styles.statLabel}>Karma</Text></View>
            <View style={styles.statBox}>
              <Text style={styles.statNum}>{p?.fame_rating_avg != null ? `${p.fame_rating_avg.toFixed(1)}★` : '—'}</Text>
              <Text style={styles.statLabel}>{p?.fame_rating_count || 0} ratings</Text>
            </View>
          </View>
        </View>

        <Text style={styles.sectionTitle}>Reviews</Text>
        {(!p?.reviews || p.reviews.length === 0) ? (
          <Text style={styles.empty}>No written reviews yet.</Text>
        ) : p.reviews.map((r: any, i: number) => (
          <View key={i} style={styles.review}>
            <View style={styles.reviewHead}>
              <Text style={styles.reviewer}>{r.rater_name}</Text>
              <View style={{ flexDirection: 'row' }}>
                {[1, 2, 3, 4, 5].map(s => <Ionicons key={s} name={r.stars >= s ? 'star' : 'star-outline'} size={13} color="#F59E0B" />)}
              </View>
            </View>
            <Text style={styles.reviewText}>{r.comment}</Text>
          </View>
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
  hero: { backgroundColor: '#FFF', borderRadius: 18, padding: 22, alignItems: 'center', marginBottom: 18, borderWidth: 1, borderColor: '#E2E8F0' },
  avatar: { width: 72, height: 72, borderRadius: 36, backgroundColor: '#F59E0B', alignItems: 'center', justifyContent: 'center', marginBottom: 10 },
  avatarText: { fontSize: 30, fontWeight: '900', color: '#FFF' },
  name: { fontSize: 20, fontWeight: '800', color: '#0F172A' },
  rank: { fontSize: 14, fontWeight: '700', color: '#D97706', marginTop: 2 },
  statsRow: { flexDirection: 'row', gap: 30, marginTop: 16 },
  statBox: { alignItems: 'center' },
  statNum: { fontSize: 22, fontWeight: '900', color: '#0F172A' },
  statLabel: { fontSize: 12, color: '#64748B', marginTop: 2 },
  sectionTitle: { fontSize: 15, fontWeight: '800', color: '#0F172A', marginBottom: 10 },
  empty: { fontSize: 13, color: '#94A3B8' },
  review: { backgroundColor: '#FFF', borderRadius: 12, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: '#EEF2F7' },
  reviewHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  reviewer: { fontSize: 13, fontWeight: '700', color: '#0F172A' },
  reviewText: { fontSize: 13, color: '#334155', lineHeight: 19 },
});
