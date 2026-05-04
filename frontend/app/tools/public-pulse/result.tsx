import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../../src/constants/colors';
import api from '../../../src/utils/api';

const BAND_COLOR: Record<string, string> = { high: '#10B981', medium: '#F59E0B', low: '#EF4444' };
const BAND_LABEL: Record<string, string> = { high: 'Strong Position', medium: 'Building Momentum', low: 'Early Stage' };

export default function ResultScreen() {
  const router = useRouter();
  const { session } = useLocalSearchParams<{ session: string }>();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await api.get(`/public-pulse/tools/sessions/${session}`);
        setData(res.data);
      } finally {
        setLoading(false);
      }
    };
    if (session) fetch();
  }, [session]);

  if (loading || !data) {
    return <SafeAreaView style={styles.container}><ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 64 }} /></SafeAreaView>;
  }

  const isCount = data.tool_slug === 'govt_benefit_finder';
  const score = data.score || 0;
  const band = data.score_band || 'medium';
  const color = BAND_COLOR[band];
  const isCompleted = data.completed;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 40 }}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => router.replace('/tools/public-pulse' as any)}>
            <Ionicons name="close" size={28} color={COLORS.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Your Result</Text>
          <View style={{ width: 28 }} />
        </View>

        {/* Hero Score */}
        <LinearGradient colors={[color, `${color}CC`]} style={styles.scoreHero}>
          <Text style={styles.scoreLabel}>Your Score</Text>
          <Text style={styles.scoreValue}>
            {isCount ? score : `${score}`}
            <Text style={styles.scoreOf}>{isCount ? ` / 6 matches` : ' / 100'}</Text>
          </Text>
          <View style={styles.bandPill}>
            <Text style={styles.bandTxt}>{BAND_LABEL[band]}</Text>
          </View>
        </LinearGradient>

        {/* Insight */}
        {data.insight && (
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Ionicons name="bulb" size={20} color="#F59E0B" />
              <Text style={styles.cardTitle}>Insight for You</Text>
            </View>
            <Text style={styles.insightTxt}>{data.insight}</Text>
          </View>
        )}

        {/* Recommendations */}
        {data.recommendations && data.recommendations.length > 0 && (
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <Ionicons name="list" size={20} color={COLORS.primary} />
              <Text style={styles.cardTitle}>{isCount ? 'You may be eligible for' : 'Recommended next steps'}</Text>
            </View>
            {data.recommendations.map((r: any, idx: number) => (
              <View key={idx} style={styles.recItem}>
                <View style={styles.recIdx}>
                  <Text style={styles.recIdxTxt}>{idx + 1}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.recTitle}>{r.title || r.name}</Text>
                  {r.why && <Text style={styles.recDesc}>{r.why}</Text>}
                  {r.next_step && <Text style={styles.recDesc}>→ {r.next_step}</Text>}
                </View>
              </View>
            ))}
          </View>
        )}

        {/* Hidden Value Hook */}
        {data.hidden_value_hook && (
          <View style={styles.hookCard}>
            <Ionicons name="gift" size={22} color="#7C3AED" />
            <View style={{ flex: 1, marginLeft: 10 }}>
              <Text style={styles.hookTitle}>Did you know?</Text>
              <Text style={styles.hookTxt}>{data.hidden_value_hook}</Text>
            </View>
          </View>
        )}

        {/* Contribution callout */}
        {data.contributed_to_research && (
          <View style={styles.contribCard}>
            <Ionicons name="people" size={18} color="#10B981" />
            <Text style={styles.contribTxt}>
              Your anonymized response helps improve services for thousands like you. Thank you.
            </Text>
          </View>
        )}

        <TouchableOpacity
          style={styles.dashBtn}
          onPress={() => router.push('/tools/public-pulse/dashboards' as any)}
        >
          <Ionicons name="stats-chart" size={18} color="#FFF" />
          <Text style={styles.dashBtnTxt}>See public insights</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.outlineBtn}
          onPress={() => router.replace('/tools/public-pulse' as any)}
        >
          <Text style={styles.outlineBtnTxt}>Take another tool</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F9FAFB' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text },
  scoreHero: { borderRadius: 20, padding: 28, alignItems: 'center', marginBottom: 16 },
  scoreLabel: { color: 'rgba(255,255,255,0.8)', fontSize: 13, fontWeight: '600' },
  scoreValue: { color: '#FFF', fontSize: 56, fontWeight: '800', marginTop: 4 },
  scoreOf: { fontSize: 18, fontWeight: '500', opacity: 0.8 },
  bandPill: { backgroundColor: 'rgba(255,255,255,0.25)', paddingHorizontal: 14, paddingVertical: 6, borderRadius: 14, marginTop: 10 },
  bandTxt: { color: '#FFF', fontSize: 13, fontWeight: '700' },
  card: { backgroundColor: '#FFF', borderRadius: 14, padding: 16, marginBottom: 12 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 10, gap: 8 },
  cardTitle: { fontSize: 14, fontWeight: '700', color: COLORS.text },
  insightTxt: { fontSize: 14, color: '#374151', lineHeight: 21 },
  recItem: { flexDirection: 'row', marginBottom: 10, alignItems: 'flex-start' },
  recIdx: { width: 26, height: 26, borderRadius: 13, backgroundColor: '#EEF2FF', alignItems: 'center', justifyContent: 'center', marginRight: 10 },
  recIdxTxt: { color: COLORS.primary, fontSize: 12, fontWeight: '700' },
  recTitle: { fontSize: 14, fontWeight: '600', color: COLORS.text },
  recDesc: { fontSize: 12, color: '#6B7280', marginTop: 3, lineHeight: 16 },
  hookCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F5F3FF', padding: 14, borderRadius: 12, marginBottom: 12 },
  hookTitle: { fontSize: 13, fontWeight: '700', color: '#7C3AED' },
  hookTxt: { fontSize: 13, color: '#5B21B6', marginTop: 3, lineHeight: 18 },
  contribCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#ECFDF5', padding: 12, borderRadius: 10, marginBottom: 16, gap: 10 },
  contribTxt: { flex: 1, fontSize: 12, color: '#065F46' },
  dashBtn: { flexDirection: 'row', backgroundColor: COLORS.primary, padding: 14, borderRadius: 12, alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 8 },
  dashBtnTxt: { color: '#FFF', fontSize: 14, fontWeight: '700' },
  outlineBtn: { padding: 14, borderRadius: 12, alignItems: 'center', borderWidth: 1, borderColor: '#D1D5DB', marginTop: 8 },
  outlineBtnTxt: { color: COLORS.text, fontSize: 14, fontWeight: '600' },
});
