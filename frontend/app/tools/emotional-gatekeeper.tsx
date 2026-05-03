import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator, Alert,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';

const EG_COLORS = {
  amber: '#F59E0B',
  amberDark: '#D97706',
  amberLight: '#FFFBEB',
  trap: '#EF4444',
  loop: '#8B5CF6',
  limitation: '#3B82F6',
  outlet: '#10B981',
  aim: '#F97316',
};

interface DashboardData {
  traps_identified: number;
  loops_broken: number;
  limitations_identified: number;
  outlets_analyzed: number;
  aim_sessions: number;
  total_sessions: number;
  completed_sessions: number;
  commitments_total: number;
  commitments_completed: number;
  breakthrough_streak: number;
  recent_sessions: any[];
  pending_actions: any[];
}

export default function EmotionalGatekeeperScreen() {
  const router = useRouter();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchDashboard = async () => {
    try {
      const res = await api.get('/emotional-gatekeeper/dashboard');
      setDashboard(res.data);
    } catch (err) {
      console.error('Dashboard fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { fetchDashboard(); }, []));

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchDashboard();
    setRefreshing(false);
  };

  const startSession = async (type: string) => {
    // Direct navigation tools (no session creation needed)
    if (type === 'advisor') {
      router.push('/tools/eg-advisor' as any);
      return;
    }
    if (type === 'emotional_reception') {
      router.push('/tools/eg-emotional-reception' as any);
      return;
    }
    try {
      const res = await api.post('/emotional-gatekeeper/sessions', { session_type: type });
      const sid = res.data.id;
      const routeMap: Record<string, string> = {
        trap: `/tools/eg-trap?sessionId=${sid}`,
        loop: `/tools/eg-loop?sessionId=${sid}`,
        limitation: `/tools/eg-limitation?sessionId=${sid}`,
        outlet: `/tools/eg-outlet?sessionId=${sid}`,
        aim: `/tools/eg-aim?sessionId=${sid}`,
      };
      router.push(routeMap[type] as any);
    } catch (err) {
      Alert.alert('Error', 'Failed to create session. Please try again.');
    }
  };

  const tools = [
    {
      id: 'trap', title: 'Breaking the Trap', icon: 'alert-circle' as const,
      desc: 'Landscaping → Linking → Looping', colors: [EG_COLORS.trap, '#DC2626'],
      stat: dashboard?.traps_identified || 0, label: 'Traps Found',
    },
    {
      id: 'loop', title: 'Breaking the Loop', icon: 'sync-circle' as const,
      desc: '4 methods to break mental loops', colors: [EG_COLORS.loop, '#7C3AED'],
      stat: dashboard?.loops_broken || 0, label: 'Loops Broken',
    },
    {
      id: 'limitation', title: 'Breaking Limitations', icon: 'lock-open' as const,
      desc: 'Transform limiting beliefs', colors: [EG_COLORS.limitation, '#1D4ED8'],
      stat: dashboard?.limitations_identified || 0, label: 'Limits Broken',
    },
    {
      id: 'outlet', title: 'Outlet Analyzer', icon: 'heart-circle' as const,
      desc: 'Analyze emotional coping strategies', colors: [EG_COLORS.outlet, '#059669'],
      stat: dashboard?.outlets_analyzed || 0, label: 'Analyzed',
    },
    {
      id: 'aim', title: 'AIM Manager', icon: 'flame' as const,
      desc: 'Addictions & Irritations Manager', colors: [EG_COLORS.aim, '#EA580C'],
      stat: dashboard?.aim_sessions || 0, label: 'Sessions',
    },
    {
      id: 'advisor', title: 'Effective Outlets Advisor', icon: 'leaf' as const,
      desc: '10 constructive techniques with guided practice', colors: ['#10B981', '#047857'],
      stat: 0, label: 'Practices', isDirectNav: true,
    },
    {
      id: 'emotional_reception', title: 'Emotional Reception', icon: 'water' as const,
      desc: 'Just Be in the Here and Now — 5 min EQ builder', colors: ['#0EA5E9', '#0369A1'],
      stat: 0, label: 'Sessions', isDirectNav: true,
    },
  ];

  if (loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.loadingWrap}>
          <ActivityIndicator size="large" color={EG_COLORS.amber} />
          <Text style={styles.loadingText}>Loading Emotional Gatekeeper...</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{ paddingBottom: 100 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {/* Header */}
        <LinearGradient colors={['#F59E0B', '#D97706', '#B45309']} style={styles.header}>
          <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
            <Ionicons name="arrow-back" size={22} color="#FFF" />
          </TouchableOpacity>
          <View style={styles.headerContent}>
            <Text style={styles.headerTitle}>Emotional Gatekeeper</Text>
            <Text style={styles.headerSubtitle}>
              Break the Trap. Break the Loop. Break the Limitation.
            </Text>
          </View>
        </LinearGradient>

        <View style={styles.content}>
          {/* Streak Banner */}
          <View style={styles.streakCard}>
            <View style={styles.streakLeft}>
              <Text style={styles.streakEmoji}>🔥</Text>
              <View>
                <Text style={styles.streakNum}>{dashboard?.breakthrough_streak || 0}</Text>
                <Text style={styles.streakLabel}>Day Streak</Text>
              </View>
            </View>
            <View style={styles.streakRight}>
              <View style={styles.streakStat}>
                <Text style={styles.streakStatNum}>{dashboard?.completed_sessions || 0}</Text>
                <Text style={styles.streakStatLabel}>Completed</Text>
              </View>
              <View style={styles.streakDivider} />
              <View style={styles.streakStat}>
                <Text style={styles.streakStatNum}>
                  {dashboard?.commitments_completed || 0}/{dashboard?.commitments_total || 0}
                </Text>
                <Text style={styles.streakStatLabel}>Actions</Text>
              </View>
            </View>
          </View>

          {/* Sub-Tools */}
          <Text style={styles.sectionTitle}>Breakthrough Tools</Text>
          {tools.map((tool) => (
            <TouchableOpacity
              key={tool.id}
              style={styles.toolCard}
              onPress={() => startSession(tool.id)}
              activeOpacity={0.7}
            >
              <LinearGradient colors={tool.colors} style={styles.toolIcon}>
                <Ionicons name={tool.icon} size={26} color="#FFF" />
              </LinearGradient>
              <View style={styles.toolInfo}>
                <Text style={styles.toolTitle}>{tool.title}</Text>
                <Text style={styles.toolDesc}>{tool.desc}</Text>
              </View>
              <View style={styles.toolStatWrap}>
                <Text style={styles.toolStatNum}>{tool.stat}</Text>
                <Text style={styles.toolStatLabel}>{tool.label}</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={COLORS.textMuted} />
            </TouchableOpacity>
          ))}

          {/* Pending Actions */}
          {(dashboard?.pending_actions?.length || 0) > 0 && (
            <>
              <Text style={styles.sectionTitle}>Pending Commitments</Text>
              {dashboard!.pending_actions.map((action: any) => (
                <View key={action.id} style={styles.actionCard}>
                  <View style={styles.actionDot} />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.actionText}>{action.commitment_text}</Text>
                    <Text style={styles.actionMeta}>
                      {action.commitment_type} • {action.due_date || 'No deadline'}
                    </Text>
                  </View>
                </View>
              ))}
            </>
          )}

          {/* Recent Sessions */}
          {(dashboard?.recent_sessions?.length || 0) > 0 && (
            <>
              <Text style={styles.sectionTitle}>Recent Sessions</Text>
              {dashboard!.recent_sessions.map((s: any) => (
                <TouchableOpacity
                  key={s.id}
                  style={styles.sessionCard}
                  onPress={() => router.push(`/tools/eg-session?sessionId=${s.id}` as any)}
                >
                  <View style={[styles.sessionTypeBadge, {
                    backgroundColor: tools.find(t => t.id === s.session_type)?.colors[0] || EG_COLORS.amber,
                  }]}>
                    <Text style={styles.sessionTypeTxt}>{s.session_type?.toUpperCase()}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.sessionTitle}>{s.title}</Text>
                    <Text style={styles.sessionMeta}>
                      {s.status} • {new Date(s.created_at).toLocaleDateString()}
                    </Text>
                  </View>
                  <Ionicons name="chevron-forward" size={16} color={COLORS.textMuted} />
                </TouchableOpacity>
              ))}
            </>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  loadingWrap: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  loadingText: { fontSize: 14, color: COLORS.textMuted },
  header: { padding: 20, paddingTop: 8, paddingBottom: 24, borderBottomLeftRadius: 24, borderBottomRightRadius: 24 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center', marginBottom: 12 },
  headerContent: {},
  headerTitle: { fontSize: 24, fontWeight: '800', color: '#FFF' },
  headerSubtitle: { fontSize: 13, color: 'rgba(255,255,255,0.85)', marginTop: 4, fontStyle: 'italic' },
  content: { padding: 16 },
  streakCard: {
    flexDirection: 'row', backgroundColor: '#FFF', borderRadius: 16, padding: 16,
    marginBottom: 20, borderWidth: 1, borderColor: '#FDE68A',
    alignItems: 'center', justifyContent: 'space-between',
  },
  streakLeft: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  streakEmoji: { fontSize: 32 },
  streakNum: { fontSize: 28, fontWeight: '800', color: EG_COLORS.amberDark },
  streakLabel: { fontSize: 12, color: COLORS.textMuted, fontWeight: '600' },
  streakRight: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  streakStat: { alignItems: 'center' },
  streakStatNum: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  streakStatLabel: { fontSize: 10, color: COLORS.textMuted, marginTop: 2 },
  streakDivider: { width: 1, height: 28, backgroundColor: COLORS.border },
  sectionTitle: { fontSize: 17, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 12, marginTop: 8 },
  toolCard: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: '#FFF',
    borderRadius: 14, padding: 14, marginBottom: 10, gap: 12,
    borderWidth: 1, borderColor: COLORS.border,
  },
  toolIcon: { width: 50, height: 50, borderRadius: 14, justifyContent: 'center', alignItems: 'center' },
  toolInfo: { flex: 1 },
  toolTitle: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  toolDesc: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  toolStatWrap: { alignItems: 'center', marginRight: 4 },
  toolStatNum: { fontSize: 18, fontWeight: '800', color: EG_COLORS.amberDark },
  toolStatLabel: { fontSize: 9, color: COLORS.textMuted, textTransform: 'uppercase' },
  actionCard: {
    flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#FFF',
    borderRadius: 10, padding: 12, marginBottom: 8, borderLeftWidth: 3, borderLeftColor: EG_COLORS.amber,
  },
  actionDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: EG_COLORS.amber },
  actionText: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  actionMeta: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  sessionCard: {
    flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#FFF',
    borderRadius: 12, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border,
  },
  sessionTypeBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  sessionTypeTxt: { fontSize: 9, fontWeight: '700', color: '#FFF' },
  sessionTitle: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  sessionMeta: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
});
