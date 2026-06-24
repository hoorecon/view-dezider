import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../../src/constants/colors';
import api from '../../../src/utils/api';
import { safeBack } from '../../../src/utils/navigation';

type Tool = {
  slug: string;
  title: string;
  tagline: string;
  hook: string;
  icon: string;
  color: string;
  estimated_seconds: number;
  steps_count: number;
};

export default function PublicPulseHome() {
  const router = useRouter();
  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(true);
  const [consentActive, setConsentActive] = useState<boolean | null>(null);
  const [recentSessions, setRecentSessions] = useState<any[]>([]);

  const fetchAll = async () => {
    try {
      const [toolsRes, consentRes, sessionsRes] = await Promise.all([
        api.get('/public-pulse/tools'),
        api.get('/public-pulse/consent/me').catch(() => ({ data: { active: false } })),
        api.get('/public-pulse/tools/sessions/me').catch(() => ({ data: { sessions: [] } })),
      ]);
      setTools(toolsRes.data.tools || []);
      setConsentActive(!!consentRes.data?.active);
      setRecentSessions(sessionsRes.data.sessions || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { setLoading(true); fetchAll(); }, []));

  const startTool = (slug: string) => {
    if (!consentActive) {
      router.push('/tools/public-pulse/consent' as any);
      return;
    }
    router.push(`/tools/public-pulse/run?slug=${slug}` as any);
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 64 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scroll}>
        {/* Header */}
        <View style={styles.header}>
          <TouchableOpacity onPress={() => safeBack(router)} style={styles.backBtn}>
            <Ionicons name="chevron-back" size={28} color={COLORS.text} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Life Mirror</Text>
          <TouchableOpacity onPress={() => router.push('/tools/public-pulse/dashboards' as any)}>
            <Ionicons name="stats-chart" size={26} color={COLORS.primary} />
          </TouchableOpacity>
        </View>

        {/* Hero */}
        <LinearGradient
          colors={['#6366F1', '#8B5CF6']}
          style={styles.hero}
        >
          <Text style={styles.heroKicker}>SELF-DISCOVERY • LIVE INSIGHTS</Text>
          <Text style={styles.heroTitle}>Decisions that count.{'\n'}Data that helps.</Text>
          <Text style={styles.heroSub}>
            We ask only what improves YOUR decision clarity. You're always in control.
          </Text>
        </LinearGradient>

        {/* Consent banner */}
        {consentActive === false && (
          <TouchableOpacity
            style={styles.consentBanner}
            onPress={() => router.push('/tools/public-pulse/consent' as any)}
          >
            <Ionicons name="shield-checkmark" size={22} color="#F59E0B" />
            <View style={{ flex: 1, marginLeft: 12 }}>
              <Text style={styles.consentTitle}>Set your data preferences</Text>
              <Text style={styles.consentSub}>1 minute. You can change or withdraw anytime.</Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color="#9CA3AF" />
          </TouchableOpacity>
        )}

        {/* Tools */}
        <Text style={styles.sectionTitle}>Choose your Score™</Text>
        {tools.map((t) => (
          <TouchableOpacity
            key={t.slug}
            style={[styles.toolCard, { borderLeftColor: t.color }]}
            onPress={() => startTool(t.slug)}
          >
            <View style={[styles.toolIcon, { backgroundColor: `${t.color}20` }]}>
              <Ionicons name={t.icon as any} size={28} color={t.color} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.toolTitle}>{t.title}</Text>
              <Text style={styles.toolTagline}>{t.tagline}</Text>
              <Text style={styles.toolHook} numberOfLines={2}>{t.hook}</Text>
              <View style={styles.toolMeta}>
                <View style={styles.metaPill}>
                  <Ionicons name="time-outline" size={12} color="#6B7280" />
                  <Text style={styles.metaTxt}>~{t.estimated_seconds}s</Text>
                </View>
                <View style={styles.metaPill}>
                  <Ionicons name="layers-outline" size={12} color="#6B7280" />
                  <Text style={styles.metaTxt}>{t.steps_count} quick steps</Text>
                </View>
              </View>
            </View>
            <Ionicons name="arrow-forward-circle" size={32} color={t.color} />
          </TouchableOpacity>
        ))}

        {/* Recent sessions */}
        {recentSessions.length > 0 && (
          <>
            <Text style={styles.sectionTitle}>Your recent scores</Text>
            {recentSessions.slice(0, 5).map((s: any) => (
              <TouchableOpacity
                key={s.session_id}
                style={styles.recentCard}
                onPress={() => router.push(`/tools/public-pulse/result?session=${s.session_id}` as any)}
              >
                <View style={{ flex: 1 }}>
                  <Text style={styles.recentTool}>
                    {tools.find((t) => t.slug === s.tool_slug)?.title || s.tool_slug}
                  </Text>
                  <Text style={styles.recentMeta}>
                    {s.completed ? `Score: ${s.score}` : `In progress (Step ${s.current_step})`}
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={20} color="#9CA3AF" />
              </TouchableOpacity>
            ))}
          </>
        )}

        {/* Public dashboards CTA */}
        <TouchableOpacity
          style={styles.dashCta}
          onPress={() => router.push('/tools/public-pulse/dashboards' as any)}
        >
          <Ionicons name="trending-up" size={24} color="#10B981" />
          <View style={{ flex: 1, marginLeft: 12 }}>
            <Text style={styles.dashCtaTitle}>See public insights</Text>
            <Text style={styles.dashCtaSub}>Anonymized trends from people across districts</Text>
          </View>
          <Ionicons name="chevron-forward" size={20} color="#9CA3AF" />
        </TouchableOpacity>

        {/* Feedback CTA */}
        <TouchableOpacity
          style={styles.feedbackCta}
          onPress={() => router.push('/tools/public-pulse/feedback' as any)}
        >
          <Ionicons name="megaphone" size={22} color="#3B82F6" />
          <View style={{ flex: 1, marginLeft: 12 }}>
            <Text style={styles.dashCtaTitle}>Share feedback / report an issue</Text>
            <Text style={styles.dashCtaSub}>Service, scheme, or local problem</Text>
          </View>
          <Ionicons name="chevron-forward" size={20} color="#9CA3AF" />
        </TouchableOpacity>

        {/* Org / Gov Portal CTA */}
        <TouchableOpacity
          style={styles.orgCta}
          onPress={() => router.push('/tools/public-pulse/org' as any)}
        >
          <Ionicons name="business" size={22} color="#7C3AED" />
          <View style={{ flex: 1, marginLeft: 12 }}>
            <Text style={styles.dashCtaTitle}>Org / Gov Portal</Text>
            <Text style={styles.dashCtaSub}>Register NGO/MSME/Govt · See rectification queue · Dashboard</Text>
          </View>
          <Ionicons name="chevron-forward" size={20} color="#9CA3AF" />
        </TouchableOpacity>

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F9FAFB' },
  scroll: { paddingHorizontal: 16, paddingBottom: 24 },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingVertical: 12 },
  backBtn: { padding: 4 },
  headerTitle: { fontSize: 20, fontWeight: '700', color: COLORS.text },
  hero: { borderRadius: 20, padding: 24, marginBottom: 20 },
  heroKicker: { fontSize: 11, color: '#E0E7FF', fontWeight: '700', letterSpacing: 1 },
  heroTitle: { fontSize: 26, fontWeight: '800', color: '#FFF', marginTop: 8, lineHeight: 32 },
  heroSub: { fontSize: 14, color: '#E0E7FF', marginTop: 12, lineHeight: 20 },
  consentBanner: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#FEF3C7', borderRadius: 12, padding: 14, marginBottom: 20,
  },
  consentTitle: { fontSize: 14, fontWeight: '700', color: '#92400E' },
  consentSub: { fontSize: 12, color: '#92400E', marginTop: 2 },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text, marginVertical: 12 },
  toolCard: {
    flexDirection: 'row', alignItems: 'center',
    backgroundColor: '#FFF', borderRadius: 16, padding: 16, marginBottom: 12,
    borderLeftWidth: 4,
    shadowColor: '#000', shadowOpacity: 0.04, shadowRadius: 8, shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  toolIcon: { width: 56, height: 56, borderRadius: 14, alignItems: 'center', justifyContent: 'center', marginRight: 14 },
  toolTitle: { fontSize: 16, fontWeight: '700', color: COLORS.text },
  toolTagline: { fontSize: 12, color: '#6B7280', marginTop: 2, fontWeight: '600' },
  toolHook: { fontSize: 13, color: '#374151', marginTop: 6, lineHeight: 18 },
  toolMeta: { flexDirection: 'row', marginTop: 8, gap: 8 },
  metaPill: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F3F4F6', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, gap: 4 },
  metaTxt: { fontSize: 11, color: '#6B7280', fontWeight: '600' },
  recentCard: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFF',
    borderRadius: 12, padding: 14, marginBottom: 8,
  },
  recentTool: { fontSize: 14, fontWeight: '600', color: COLORS.text },
  recentMeta: { fontSize: 12, color: '#6B7280', marginTop: 2 },
  dashCta: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: '#ECFDF5',
    borderRadius: 14, padding: 16, marginTop: 16,
    borderWidth: 1, borderColor: '#A7F3D0',
  },
  feedbackCta: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: '#EFF6FF',
    borderRadius: 14, padding: 16, marginTop: 12,
    borderWidth: 1, borderColor: '#BFDBFE',
  },
  orgCta: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: '#F5F3FF',
    borderRadius: 14, padding: 16, marginTop: 12,
    borderWidth: 1, borderColor: '#DDD6FE',
  },
  dashCtaTitle: { fontSize: 14, fontWeight: '700', color: COLORS.text },
  dashCtaSub: { fontSize: 12, color: '#6B7280', marginTop: 2 },
});
