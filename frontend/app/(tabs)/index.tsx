import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Image,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../src/store/authStore';
import { COLORS, GRADIENTS } from '../../src/constants/colors';
import { Card } from '../../src/components/Card';
import api from '../../src/utils/api';

interface Stats {
  decisions: { total: number; completed: number };
  test123: { total: number };
  journal: { total: number; completed: number };
  latest_assessment: any;
}

export default function HomeScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [stats, setStats] = useState<Stats | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [inboxPending, setInboxPending] = useState(0);

  const fetchStats = async () => {
    try {
      const response = await api.get('/stats');
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  const fetchUnreadCount = async () => {
    try {
      const response = await api.get('/notifications/unread-count');
      setUnreadCount(response.data.count || 0);
    } catch (error) {
      console.error('Error fetching unread count:', error);
    }
  };

  const fetchInboxCount = async () => {
    try {
      const response = await api.get('/shared-steps/received');
      const pending = (response.data || []).filter((s: any) =>
        s.status === 'active' && s.recipients?.some((r: any) => r.status === 'pending')
      ).length;
      setInboxPending(pending);
    } catch (error) {
      console.error('Error fetching inbox:', error);
    }
  };

  const fetchAll = async () => {
    await Promise.all([fetchStats(), fetchUnreadCount(), fetchInboxCount()]);
  };

  useFocusEffect(
    useCallback(() => {
      fetchAll();
    }, [])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchAll();
    setRefreshing(false);
  };

  const getModeColor = (mode: string) => {
    switch (mode) {
      case 'emotional': return COLORS.emotional;
      case 'logical': return COLORS.logical;
      case 'intuitive': return COLORS.intuitive;
      case 'awareness': return COLORS.awareness;
      default: return COLORS.primary;
    }
  };

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good Morning';
    if (hour < 17) return 'Good Afternoon';
    return 'Good Evening';
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {/* Header */}
        <LinearGradient
          colors={GRADIENTS.primary}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.header}
        >
          <View style={styles.headerContent}>
            <View style={styles.headerLeft}>
              <Text style={styles.greeting}>{getGreeting()},</Text>
              <Text style={styles.userName}>{user?.name || 'Decision Maker'}</Text>
            </View>
            <View style={styles.headerRight}>
              <TouchableOpacity
                style={styles.headerIconBtn}
                onPress={() => router.push('/notifications')}
              >
                <Ionicons name="notifications-outline" size={22} color="#FFF" />
                {unreadCount > 0 && (
                  <View style={styles.badge}>
                    <Text style={styles.badgeText}>{unreadCount > 9 ? '9+' : unreadCount}</Text>
                  </View>
                )}
              </TouchableOpacity>
              <Image
                source={{ uri: 'https://customer-assets.emergentagent.com/job_chapter2-guide/artifacts/acyqe96y_VENTURE%20BUDDHA-SqaureHD.png' }}
                style={styles.headerLogo}
              />
            </View>
          </View>
          <Text style={styles.tagline}>Make conscious decisions, shape your destiny</Text>
        </LinearGradient>

        <View style={styles.content}>
          {/* Quick Actions */}
          <Text style={styles.sectionTitle}>Quick Actions</Text>
          <View style={styles.quickActions}>
            <TouchableOpacity
              style={styles.actionCard}
              onPress={() => router.push('/prr/new')}
            >
              <LinearGradient
                colors={[COLORS.primary, COLORS.primaryDark]}
                style={styles.actionIcon}
              >
                <Ionicons name="analytics" size={24} color={COLORS.white} />
              </LinearGradient>
              <Text style={styles.actionTitle}>PRR Decision</Text>
              <Text style={styles.actionSubtitle}>10-step analysis</Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.actionCard}
              onPress={() => router.push('/test123/new')}
            >
              <LinearGradient
                colors={[COLORS.accent, COLORS.accentDark]}
                style={styles.actionIcon}
              >
                <Ionicons name="flash" size={24} color={COLORS.white} />
              </LinearGradient>
              <Text style={styles.actionTitle}>Test123</Text>
              <Text style={styles.actionSubtitle}>Instant decision</Text>
            </TouchableOpacity>
          </View>

          {/* Collaborate & Insights */}
          <Text style={styles.sectionTitle}>Collaborate & Insights</Text>
          <View style={styles.colabRow}>
            <TouchableOpacity
              style={styles.colabCard}
              onPress={() => router.push('/inbox')}
            >
              <View style={[styles.colabIconWrap, { backgroundColor: 'rgba(99,102,241,0.1)' }]}>
                <Ionicons name="mail-unread" size={22} color="#6366F1" />
                {inboxPending > 0 && (
                  <View style={[styles.colabBadge, { backgroundColor: '#6366F1' }]}>
                    <Text style={styles.colabBadgeText}>{inboxPending}</Text>
                  </View>
                )}
              </View>
              <Text style={styles.colabTitle}>Shared Inbox</Text>
              <Text style={styles.colabSubtitle}>
                {inboxPending > 0 ? `${inboxPending} pending` : 'No pending'}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.colabCard}
              onPress={() => router.push('/notifications')}
            >
              <View style={[styles.colabIconWrap, { backgroundColor: 'rgba(245,158,11,0.1)' }]}>
                <Ionicons name="notifications" size={22} color="#F59E0B" />
                {unreadCount > 0 && (
                  <View style={[styles.colabBadge, { backgroundColor: '#F59E0B' }]}>
                    <Text style={styles.colabBadgeText}>{unreadCount}</Text>
                  </View>
                )}
              </View>
              <Text style={styles.colabTitle}>Notifications</Text>
              <Text style={styles.colabSubtitle}>
                {unreadCount > 0 ? `${unreadCount} unread` : 'All caught up'}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.colabCard}
              onPress={() => router.push('/analytics')}
            >
              <View style={[styles.colabIconWrap, { backgroundColor: 'rgba(16,185,129,0.1)' }]}>
                <Ionicons name="bar-chart" size={22} color="#10B981" />
              </View>
              <Text style={styles.colabTitle}>Analytics</Text>
              <Text style={styles.colabSubtitle}>Life areas</Text>
            </TouchableOpacity>
          </View>

          {/* Stats */}
          <Text style={styles.sectionTitle}>Your Progress</Text>
          <View style={styles.statsGrid}>
            <Card style={styles.statCard}>
              <Ionicons name="analytics" size={28} color={COLORS.primary} />
              <Text style={styles.statNumber}>{stats?.decisions.total || 0}</Text>
              <Text style={styles.statLabel}>PRR Decisions</Text>
              <Text style={styles.statSubtext}>
                {stats?.decisions.completed || 0} completed
              </Text>
            </Card>

            <Card style={styles.statCard}>
              <Ionicons name="flash" size={28} color={COLORS.accent} />
              <Text style={styles.statNumber}>{stats?.test123.total || 0}</Text>
              <Text style={styles.statLabel}>Quick Decisions</Text>
              <Text style={styles.statSubtext}>Test123 sessions</Text>
            </Card>

            <Card style={styles.statCard}>
              <Ionicons name="book" size={28} color={COLORS.teal} />
              <Text style={styles.statNumber}>{stats?.journal.total || 0}</Text>
              <Text style={styles.statLabel}>Journal Entries</Text>
              <Text style={styles.statSubtext}>
                {stats?.journal.completed || 0} reviewed
              </Text>
            </Card>

            <Card style={styles.statCard}>
              {stats?.latest_assessment ? (
                <>
                  <Ionicons
                    name="compass"
                    size={28}
                    color={getModeColor(stats.latest_assessment.dominant_mode)}
                  />
                  <Text style={[styles.statNumber, { fontSize: 14, textTransform: 'capitalize' }]}>
                    {stats.latest_assessment.dominant_mode}
                  </Text>
                  <Text style={styles.statLabel}>Decision Mode</Text>
                  <Text style={styles.statSubtext}>Your style</Text>
                </>
              ) : (
                <>
                  <Ionicons name="compass-outline" size={28} color={COLORS.textMuted} />
                  <Text style={[styles.statNumber, { fontSize: 14 }]}>Not taken</Text>
                  <Text style={styles.statLabel}>Assessment</Text>
                  <Text style={styles.statSubtext}>Take quiz</Text>
                </>
              )}
            </Card>
          </View>

          {/* Decision Modes Info */}
          <Text style={styles.sectionTitle}>Decision Making Modes</Text>
          <Card style={styles.modesCard}>
            <View style={styles.modeRow}>
              <View style={[styles.modeDot, { backgroundColor: COLORS.emotional }]} />
              <View style={styles.modeInfo}>
                <Text style={styles.modeName}>Emotional</Text>
                <Text style={styles.modeDesc}>30-40% accuracy, comfortable but short-term</Text>
              </View>
            </View>
            <View style={styles.modeRow}>
              <View style={[styles.modeDot, { backgroundColor: COLORS.logical }]} />
              <View style={styles.modeInfo}>
                <Text style={styles.modeName}>Logical</Text>
                <Text style={styles.modeDesc}>50-60% accuracy, rational but lacks heart</Text>
              </View>
            </View>
            <View style={styles.modeRow}>
              <View style={[styles.modeDot, { backgroundColor: COLORS.intuitive }]} />
              <View style={styles.modeInfo}>
                <Text style={styles.modeName}>Intuitive</Text>
                <Text style={styles.modeDesc}>70-80% accuracy, insight-driven</Text>
              </View>
            </View>
            <View style={styles.modeRow}>
              <View style={[styles.modeDot, { backgroundColor: COLORS.awareness }]} />
              <View style={styles.modeInfo}>
                <Text style={styles.modeName}>Awareness</Text>
                <Text style={styles.modeDesc}>~100% accuracy, detached clarity</Text>
              </View>
            </View>
            <TouchableOpacity
              style={styles.takeQuizButton}
              onPress={() => router.push('/(tabs)/profile')}
            >
              <Text style={styles.takeQuizText}>Take Assessment Quiz</Text>
              <Ionicons name="arrow-forward" size={16} color={COLORS.primary} />
            </TouchableOpacity>
          </Card>

          {/* PRR System Overview */}
          <Text style={styles.sectionTitle}>PRR System - 10 Steps</Text>
          <Card style={styles.prrCard}>
            <Text style={styles.prrIntro}>
              Priority Related Ratings (PRR) is a hybrid decision-making system that merges logic and emotions for optimal outcomes.
            </Text>
            <View style={styles.prrSteps}>
              {[
                'State context & options',
                'List all factors',
                'Classify factors',
                'Prioritize factors',
                'Assign ratings',
                'Assess options',
                'Calculate worth %',
                'Case 1: Obvious choice',
                'Case 2: Trial option',
                'Case 3: Accept best',
              ].map((step, index) => (
                <View key={index} style={styles.prrStep}>
                  <View style={styles.stepNumber}>
                    <Text style={styles.stepNumberText}>{index + 1}</Text>
                  </View>
                  <Text style={styles.stepText}>{step}</Text>
                </View>
              ))}
            </View>
            <TouchableOpacity
              style={styles.startPRRButton}
              onPress={() => router.push('/prr/new')}
            >
              <Text style={styles.startPRRText}>Start PRR Analysis</Text>
              <Ionicons name="arrow-forward" size={16} color={COLORS.white} />
            </TouchableOpacity>
          </Card>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  header: {
    padding: 24,
    paddingBottom: 32,
    borderBottomLeftRadius: 24,
    borderBottomRightRadius: 24,
  },
  headerContent: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  headerLeft: {
    flex: 1,
  },
  headerRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  headerIconBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  badge: {
    position: 'absolute',
    top: -2,
    right: -2,
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: '#EF4444',
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 4,
    borderWidth: 2,
    borderColor: '#FFF',
  },
  badgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#FFF',
  },
  headerLogo: {
    width: 48,
    height: 48,
    borderRadius: 12,
    backgroundColor: COLORS.white,
  },
  greeting: {
    fontSize: 16,
    color: 'rgba(255,255,255,0.8)',
  },
  userName: {
    fontSize: 24,
    fontWeight: '700',
    color: COLORS.white,
  },
  tagline: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.7)',
    fontStyle: 'italic',
  },
  content: {
    padding: 16,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: COLORS.textPrimary,
    marginBottom: 12,
    marginTop: 8,
  },
  quickActions: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 16,
  },
  actionCard: {
    flex: 1,
    backgroundColor: COLORS.white,
    borderRadius: 16,
    padding: 16,
    alignItems: 'center',
    boxShadow: '0px 2px 8px rgba(0, 0, 0, 0.05)',
    elevation: 2,
  },
  actionIcon: {
    width: 56,
    height: 56,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 12,
  },
  actionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  actionSubtitle: {
    fontSize: 12,
    color: COLORS.textSecondary,
    marginTop: 2,
  },
  colabRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 16,
  },
  colabCard: {
    flex: 1,
    backgroundColor: COLORS.white,
    borderRadius: 14,
    padding: 12,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  colabIconWrap: {
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 8,
  },
  colabBadge: {
    position: 'absolute',
    top: -4,
    right: -4,
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 3,
  },
  colabBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#FFF',
  },
  colabTitle: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.textPrimary,
    textAlign: 'center',
  },
  colabSubtitle: {
    fontSize: 10,
    color: COLORS.textMuted,
    marginTop: 2,
    textAlign: 'center',
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 16,
  },
  statCard: {
    width: '48%',
    flexGrow: 1,
    alignItems: 'center',
    padding: 16,
  },
  statNumber: {
    fontSize: 28,
    fontWeight: '700',
    color: COLORS.textPrimary,
    marginTop: 8,
  },
  statLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginTop: 4,
  },
  statSubtext: {
    fontSize: 12,
    color: COLORS.textSecondary,
    marginTop: 2,
  },
  modesCard: {
    marginBottom: 16,
  },
  modeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.divider,
  },
  modeDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginRight: 12,
  },
  modeInfo: {
    flex: 1,
  },
  modeName: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  modeDesc: {
    fontSize: 12,
    color: COLORS.textSecondary,
    marginTop: 2,
  },
  takeQuizButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 16,
    gap: 8,
  },
  takeQuizText: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.primary,
  },
  prrCard: {
    marginBottom: 24,
  },
  prrIntro: {
    fontSize: 14,
    color: COLORS.textSecondary,
    lineHeight: 20,
    marginBottom: 16,
  },
  prrSteps: {
    gap: 8,
  },
  prrStep: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  stepNumber: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  stepNumberText: {
    fontSize: 12,
    fontWeight: '700',
    color: COLORS.white,
  },
  stepText: {
    fontSize: 13,
    color: COLORS.textPrimary,
    flex: 1,
  },
  startPRRButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.primary,
    borderRadius: 12,
    paddingVertical: 14,
    marginTop: 20,
    gap: 8,
  },
  startPRRText: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.white,
  },
});
