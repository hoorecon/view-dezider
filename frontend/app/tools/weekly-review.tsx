/**
 * Weekly Review — 7-day overview + streak + variance notes.
 */
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

export default function WeeklyReviewScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [review, setReview] = useState<any>(null);
  const [week, setWeek] = useState<any>(null);

  useEffect(() => {
    (async () => {
      try {
        const [r, w] = await Promise.all([
          api.get('/daily-time-log/weekly-review'),
          api.get('/daily-time-log/week'),
        ]);
        setReview(r.data); setWeek(w.data);
      } finally { setLoading(false); }
    })();
  }, []);

  if (loading) return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 60 }} />
    </SafeAreaView>
  );

  const days = week?.days || [];
  const maxMin = Math.max(1, ...days.map((d: any) => d.total_logged_minutes || 0));

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()}>
          <Ionicons name="chevron-back" size={28} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.h1}>Weekly Review</Text>
        <View style={{ width: 28 }} />
      </View>
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
        <View style={styles.tileRow}>
          <View style={[styles.tile, { borderLeftColor: '#10B981' }]}>
            <Text style={styles.tileLabel}>Days logged</Text>
            <Text style={styles.tileValue}>{review?.days_with_logs}/7</Text>
          </View>
          <View style={[styles.tile, { borderLeftColor: '#F59E0B' }]}>
            <Text style={styles.tileLabel}>Streak</Text>
            <Text style={styles.tileValue}>{review?.current_streak}🔥</Text>
          </View>
          <View style={[styles.tile, { borderLeftColor: '#2563EB' }]}>
            <Text style={styles.tileLabel}>Adherence</Text>
            <Text style={styles.tileValue}>{review?.adherence_pct ?? '—'}{review?.adherence_pct != null ? '%' : ''}</Text>
          </View>
        </View>

        <Text style={styles.sectionTitle}>Minutes per day</Text>
        <View style={styles.barGrid}>
          {days.map((d: any) => {
            const h = Math.round((d.total_logged_minutes / maxMin) * 80);
            const dateObj = new Date(d.log_date);
            return (
              <View key={d.log_date} style={styles.barCol}>
                <View style={{ height: 80, justifyContent: 'flex-end' }}>
                  <View style={[styles.bar, { height: Math.max(3, h) }]} />
                </View>
                <Text style={styles.barDay}>{dateObj.toLocaleString('en', { weekday: 'short' })}</Text>
                <Text style={styles.barMin}>{Math.round((d.total_logged_minutes || 0) / 60 * 10) / 10}h</Text>
              </View>
            );
          })}
        </View>

        <Text style={styles.sectionTitle}>Variance notes</Text>
        {(review?.variance_notes || []).map((n: string, i: number) => (
          <View key={i} style={styles.noteRow}>
            <Ionicons name="sparkles" size={14} color={COLORS.primary} />
            <Text style={styles.noteText}>{n}</Text>
          </View>
        ))}
        {(!review?.variance_notes || review.variance_notes.length === 0) && (
          <Text style={styles.emptyText}>No notes yet — log a full week to see insights.</Text>
        )}

        <Text style={styles.sectionTitle}>Category totals (minutes)</Text>
        {Object.entries(review?.actual_category_minutes || {}).map(([cat, m]: [string, any]) => (
          <View key={cat} style={styles.catRow}>
            <Text style={styles.catLabel}>{cat}</Text>
            <Text style={styles.catValue}>{m} min</Text>
          </View>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, justifyContent: 'space-between' },
  h1: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  tileRow: { flexDirection: 'row', gap: 8, marginBottom: 14 },
  tile: { flex: 1, backgroundColor: COLORS.white, borderRadius: 10, padding: 10, borderLeftWidth: 4, borderLeftColor: '#10B981' },
  tileLabel: { fontSize: 10, fontWeight: '700', color: COLORS.textMuted, textTransform: 'uppercase', letterSpacing: 0.5 },
  tileValue: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary, marginTop: 2 },
  sectionTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginTop: 10, marginBottom: 8 },
  barGrid: { flexDirection: 'row', justifyContent: 'space-between', padding: 10, backgroundColor: COLORS.white, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border },
  barCol: { alignItems: 'center', width: 40 },
  bar: { width: 14, backgroundColor: COLORS.primary, borderRadius: 3 },
  barDay: { fontSize: 10, color: COLORS.textMuted, marginTop: 4, fontWeight: '600' },
  barMin: { fontSize: 9, color: COLORS.textPrimary, marginTop: 2 },
  noteRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, paddingVertical: 6 },
  noteText: { flex: 1, fontSize: 13, color: COLORS.textPrimary, lineHeight: 18 },
  emptyText: { color: COLORS.textMuted, fontSize: 12 },
  catRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  catLabel: { fontSize: 13, color: COLORS.textPrimary, textTransform: 'capitalize' },
  catValue: { fontSize: 13, color: COLORS.textMuted, fontWeight: '600' },
});
