import React, { useState, useCallback, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Image,
  Platform,
  useWindowDimensions,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../src/store/authStore';
import { COLORS, GRADIENTS } from '../../src/constants/colors';
import { Card } from '../../src/components/Card';
import api from '../../src/utils/api';
import { FontScaleButton } from '../../src/components/FontScaleButton';

interface Stats {
  decisions: { total: number; completed: number };
  test123: { total: number };
  journal: { total: number; completed: number };
  latest_assessment: any;
}

interface FeatureFlags {
  solution_finder: boolean;
  solution_matrix: boolean;
}

interface CTTStats {
  total: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
  routine_count: number;
  one_time_count: number;
}

interface JournalReminder {
  decision_id: string;
  title: string;
  decision_type: string;
  life_area: string;
  priority_label: string;
  implementation_review_date: string;
  status: string;
}

export default function HomeScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const { width: winWidth } = useWindowDimensions();
  const isNarrow = winWidth < 480;
  const [stats, setStats] = useState<Stats | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [inboxPending, setInboxPending] = useState(0);
  const [featureFlags, setFeatureFlags] = useState<FeatureFlags>({ solution_finder: false, solution_matrix: false });
  const [cttStats, setCttStats] = useState<CTTStats | null>(null);
  const [journalReminders, setJournalReminders] = useState<JournalReminder[]>([]);

  // ---------------------------------------------------------------------------
  // Hydration-safe client mount gate
  // ---------------------------------------------------------------------------
  // Expo Router pre-renders this page server-side. Many sections below depend
  // on client-only state (auth/user, AsyncStorage-derived flags, async-loaded
  // featureFlags / cttStats / journalReminders, time-of-day greeting, etc.).
  // When the client React tree diverges from the SSR markup, React throws
  // Minified Error #418 (hydration mismatch) and SILENTLY UNMOUNTS the rest
  // of the page — which is why users only see ~5 modules even though the
  // bundle contains 20+.
  //
  // The fix: render the static gradient header during SSR + initial paint,
  // then flip `isClient` to true in useEffect (which only runs on the client)
  // and lazily render the dynamic dashboard. This guarantees the server-vs-
  // client tree match because the dynamic content simply isn't in the SSR
  // output at all — eliminating any chance of mismatch.
  const [isClient, setIsClient] = useState(false);
  useEffect(() => {
    setIsClient(true);
  }, []);

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

  const fetchFeatureFlags = async () => {
    try {
      const response = await api.get('/feature-flags');
      setFeatureFlags(response.data || { solution_finder: false, solution_matrix: false });
    } catch (error) {
      console.error('Error fetching feature flags:', error);
    }
  };

  const fetchCttStats = async () => {
    try {
      const response = await api.get('/ctt/stats');
      setCttStats(response.data);
    } catch (error) {
      console.error('Error fetching CTT stats:', error);
    }
  };

  const fetchJournalReminders = async () => {
    try {
      const response = await api.get('/journal/reminders');
      setJournalReminders(response.data || []);
    } catch (error) {
      console.error('Error fetching journal reminders:', error);
    }
  };

  const fetchAll = async () => {
    await Promise.all([fetchStats(), fetchUnreadCount(), fetchInboxCount(), fetchFeatureFlags(), fetchCttStats(), fetchJournalReminders()]);
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
    // Defer time-of-day greeting until after hydration; otherwise the SSR
    // build (UTC at build time) produces a different string than the
    // client (local hour), which contributes to React #418 hydration mismatch.
    if (!isClient) return 'Hello';
    const hour = new Date().getHours();
    if (hour < 12) return 'Good Morning';
    if (hour < 17) return 'Good Afternoon';
    return 'Good Evening';
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        showsVerticalScrollIndicator={Platform.OS === 'web'}
        contentContainerStyle={{ paddingBottom: 100 }}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {/* Header */}
        <LinearGradient
          colors={GRADIENTS.primary}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={[styles.header, isNarrow && styles.headerNarrow]}
        >
          <View style={styles.headerContent}>
            <View style={styles.headerLeft}>
              <Text style={styles.greeting} numberOfLines={1}>{getGreeting()},</Text>
              <Text
                style={[styles.userName, isNarrow && styles.userNameNarrow]}
                numberOfLines={1}
                ellipsizeMode="tail"
              >
                {user?.name || 'Decision Maker'}
              </Text>
            </View>
            <View style={styles.headerRight}>
              {/* Font-size A / A+ / A++ pill group — kept inline on wider screens only.
                  On narrow phones we move it to its own row below to avoid squishing
                  the greeting/userName. */}
              {!isNarrow && (
                <FontScaleButton variant="dark" style={{ marginRight: 4 }} />
              )}
              {/* Switch-to-admin button — only visible for admins so they can
                  jump back without using the browser back button. Gated by
                  isClient to avoid SSR/client hydration mismatch on user state. */}
              {isClient && (user?.is_admin || ['admin', 'super_admin', 'co_admin'].includes((user?.role || '').toLowerCase())) && (
                <TouchableOpacity
                  style={[styles.headerIconBtn, isNarrow && styles.headerIconBtnNarrow]}
                  onPress={() => {
                    // Force a hard navigation on web so React Router state
                    // doesn't get confused; on native fall back to router.replace.
                    if (Platform.OS === 'web' && typeof window !== 'undefined') {
                      window.location.href = '/admin';
                    } else {
                      router.replace('/admin' as any);
                    }
                  }}
                  accessibilityLabel="Switch to admin dashboard"
                >
                  <Ionicons name="shield-checkmark" size={isNarrow ? 18 : 22} color="#FFF" />
                </TouchableOpacity>
              )}
              <TouchableOpacity
                style={[styles.headerIconBtn, isNarrow && styles.headerIconBtnNarrow]}
                onPress={() => router.push('/notifications')}
              >
                <Ionicons name="notifications-outline" size={isNarrow ? 18 : 22} color="#FFF" />
                {unreadCount > 0 && (
                  <View style={styles.badge}>
                    <Text style={styles.badgeText}>{unreadCount > 9 ? '9+' : unreadCount}</Text>
                  </View>
                )}
              </TouchableOpacity>
              <Image
                source={{ uri: 'https://customer-assets.emergentagent.com/job_chapter2-guide/artifacts/acyqe96y_VENTURE%20BUDDHA-SqaureHD.png' }}
                style={[styles.headerLogo, isNarrow && styles.headerLogoNarrow]}
              />
            </View>
          </View>
          {/* On narrow screens, FontScaleButton lives on its own row so the
              greeting + username can use the full width. */}
          {isNarrow && (
            <View style={styles.fontScaleRow}>
              <FontScaleButton variant="dark" />
            </View>
          )}
          <Text style={styles.tagline}>Make conscious decisions, shape your destiny</Text>
        </LinearGradient>

        <View style={styles.content}>
          {/*
            HYDRATION-SAFE GATE — render dynamic content only after client mount.
            See big comment block at top of component for why this exists.
            If we render this subtree during SSR with stale defaults
            (no user, no featureFlags, empty cttStats, empty journalReminders)
            and then the client re-renders with real values, React #418 fires
            and the rest of the page silently unmounts.
          */}
          {!isClient ? (
            <View style={{ paddingVertical: 40, alignItems: 'center' }}>
              <Text style={{ color: COLORS.textMuted, fontSize: 13 }}>Loading your dashboard…</Text>
            </View>
          ) : (
          <>
          {/* Journal Review Reminders Banner */}
          {journalReminders.length > 0 && (
            <TouchableOpacity
              style={styles.reminderBanner}
              onPress={() => router.push('/(tabs)/journal')}
              activeOpacity={0.8}
            >
              <View style={styles.reminderBannerIcon}>
                <Ionicons name="book" size={20} color="#FFFFFF" />
              </View>
              <View style={styles.reminderBannerContent}>
                <Text style={styles.reminderBannerTitle}>
                  {journalReminders.length} Decision{journalReminders.length > 1 ? 's' : ''} Need{journalReminders.length === 1 ? 's' : ''} Review
                </Text>
                <Text style={styles.reminderBannerText}>
                  Document learnings from your {journalReminders[0]?.priority_label === 'P0' ? 'critical' : 'important'} decisions
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={20} color="#EF4444" />
            </TouchableOpacity>
          )}

          {/* ════════════════════════════════════════════════════════════════
              24 AI GUIDES — 9-Section Dashboard (June 2026 refactor)
              -------------------------------------------------------------
              §1 Self Discovery   →  My 360° Life · GEM
              §2 Decision Kickstarters → MyDezider · Test123 · Pros&Cons · SWOT
              §3 Inner State      →  Emotional Gatekeeper · Conflict Breaker
              §4 Goals & Manifestation → Goal Setter · Manifestation
              §5 Solution Space   →  Solution Finder · Solution Store · Review Net
              §6 Execute & Track  →  Action Tracker · CTT
              §7 Lifestyle Architecture → Lifestyle Dezider · Lifestyle Designer
              §8 Reflection & Awareness → Lifestyle Analyzer · Consciousness Diary · Unconditional Happiness
              §9 Collaboration & Management → Collaboration · AALA · Time Intelligence · GEM Flight Model
              Pinned strip on top → "Pick up where you left off"
              "More tools" disclosure below → secondary utilities.
              ════════════════════════════════════════════════════════════════ */}

          {/* PINNED — "Pick up where you left off" */}
          <Text style={styles.sectionTitle}>Pick up where you left off</Text>
          <View style={styles.colabRow}>
            <TouchableOpacity
              style={styles.colabCard}
              onPress={() => router.push('/tools/dezider-list' as any)}
            >
              <View style={[styles.colabIconWrap, { backgroundColor: 'rgba(99,102,241,0.1)' }]}>
                <Ionicons name="compass" size={22} color="#6366F1" />
              </View>
              <Text style={styles.colabTitle}>Last Decision</Text>
              <Text style={styles.colabSubtitle}>
                {stats?.decisions.total ? `${stats.decisions.total} total · ${stats.decisions.completed || 0} done` : 'Start your first'}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.colabCard}
              onPress={() => router.push('/tools/action-center' as any)}
            >
              <View style={[styles.colabIconWrap, { backgroundColor: 'rgba(13,148,136,0.1)' }]}>
                <Ionicons name="checkmark-done-circle" size={22} color="#0D9488" />
              </View>
              <Text style={styles.colabTitle}>Action Tracker</Text>
              <Text style={styles.colabSubtitle}>
                {cttStats?.total ? `${cttStats.total} on plate` : 'All clear'}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.colabCard}
              onPress={() => router.push('/tools/lifestyle-designer' as any)}
            >
              <View style={[styles.colabIconWrap, { backgroundColor: 'rgba(234,88,12,0.1)' }]}>
                <Ionicons name="color-palette" size={22} color="#EA580C" />
              </View>
              <Text style={styles.colabTitle}>Today's Routine</Text>
              <Text style={styles.colabSubtitle}>Lifestyle plan</Text>
            </TouchableOpacity>
          </View>

          {/* ══════════ §1 SELF DISCOVERY ══════════ */}
          <Text style={styles.sectionTitle}>1 · Self Discovery</Text>
          <View style={styles.quickActions}>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/pna' as any)}>
              <LinearGradient colors={['#4338CA', '#6366F1']} style={styles.actionIcon}>
                <Ionicons name="layers" size={24} color={COLORS.white} />
              </LinearGradient>
              <Text style={styles.actionTitle}>My 360° Life</Text>
              <Text style={styles.actionSubtitle}>Problems · Needs · Aspirations</Text>
            </TouchableOpacity>

            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/gem' as any)}>
              <LinearGradient colors={['#0F766E', '#14B8A6']} style={styles.actionIcon}>
                <Ionicons name="flag" size={24} color={COLORS.white} />
              </LinearGradient>
              <Text style={styles.actionTitle}>GEM</Text>
              <Text style={styles.actionSubtitle}>Goal Execution Manager</Text>
            </TouchableOpacity>
          </View>

          {/* ══════════ §2 DECISION KICKSTARTERS ══════════ */}
          <Text style={styles.sectionTitle}>2 · Decision Kickstarters</Text>
          <View style={styles.quickActions}>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/dezider-list' as any)}>
              <LinearGradient colors={['#6366F1', '#8B5CF6']} style={styles.actionIcon}>
                <Ionicons name="compass" size={24} color={COLORS.white} />
              </LinearGradient>
              <Text style={styles.actionTitle}>MyDezider</Text>
              <Text style={styles.actionSubtitle}>10-step canonical</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/test123' as any)}>
              <LinearGradient colors={[COLORS.accent, COLORS.accentDark]} style={styles.actionIcon}>
                <Ionicons name="flash" size={24} color={COLORS.white} />
              </LinearGradient>
              <Text style={styles.actionTitle}>Test123</Text>
              <Text style={styles.actionSubtitle}>Instant decision</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.quickActions}>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/pros-cons-list' as any)}>
              <LinearGradient colors={['#059669', '#10B981']} style={styles.actionIcon}>
                <Ionicons name="git-compare" size={24} color={COLORS.white} />
              </LinearGradient>
              <Text style={styles.actionTitle}>Pros & Cons</Text>
              <Text style={styles.actionSubtitle}>Two-column starter</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/swot' as any)}>
              <LinearGradient colors={['#1E40AF', '#3B82F6']} style={styles.actionIcon}>
                <Ionicons name="grid" size={24} color={COLORS.white} />
              </LinearGradient>
              <Text style={styles.actionTitle}>SWOT Analysis</Text>
              <Text style={styles.actionSubtitle}>4-quadrant strategic</Text>
            </TouchableOpacity>
          </View>

          {/* ══════════ §3 INNER STATE ══════════ */}
          <Text style={styles.sectionTitle}>3 · Inner State</Text>
          <View style={styles.quickActions}>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/emotional-gatekeeper' as any)}>
              <LinearGradient colors={['#F59E0B', '#D97706']} style={styles.actionIcon}>
                <Ionicons name="heart-circle" size={24} color={COLORS.white} />
              </LinearGradient>
              <Text style={styles.actionTitle}>Emotional Gatekeeper</Text>
              <Text style={styles.actionSubtitle}>Break loops & traps</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/conflict-breaker' as any)}>
              <LinearGradient colors={['#7C2D12', '#DC2626']} style={styles.actionIcon}>
                <Ionicons name="flash" size={24} color={COLORS.white} />
              </LinearGradient>
              <Text style={styles.actionTitle}>Conflict Breaker</Text>
              <Text style={styles.actionSubtitle}>Crucial conversations</Text>
            </TouchableOpacity>
          </View>

          {/* ══════════ §4 GOALS & MANIFESTATION ══════════ */}
          <Text style={styles.sectionTitle}>4 · Goals & Manifestation</Text>
          <View style={styles.quickActions}>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/goal-setter' as any)}>
              <LinearGradient colors={['#059669', '#10B981']} style={styles.actionIcon}>
                <Ionicons name="flag" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>Goal Setter</Text>
              <Text style={styles.actionSubtitle}>SMART Framework</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/goal-manifestation' as any)}>
              <LinearGradient colors={['#7C3AED', '#9333EA']} style={styles.actionIcon}>
                <Ionicons name="sparkles" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>Manifestation</Text>
              <Text style={styles.actionSubtitle}>CAB-FAME 7 stages</Text>
            </TouchableOpacity>
          </View>

          {/* ══════════ §5 SOLUTION SPACE ══════════ */}
          <Text style={styles.sectionTitle}>5 · Solution Space</Text>
          <View style={styles.quickActions}>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/solution-finder-list' as any)}>
              <LinearGradient colors={['#7C3AED', '#C084FC']} style={styles.actionIcon}>
                <Ionicons name="bulb" size={24} color={COLORS.white} />
              </LinearGradient>
              <Text style={styles.actionTitle}>Solution Finder</Text>
              <Text style={styles.actionSubtitle}>Concerns → RCA → Plan · ASM</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/solutions-store' as any)}>
              <LinearGradient colors={['#7C3AED', '#A855F7']} style={styles.actionIcon}>
                <Ionicons name="storefront" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>Solution Store</Text>
              <Text style={styles.actionSubtitle}>Products & services</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.quickActions}>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/review-net' as any)}>
              <LinearGradient colors={['#F59E0B', '#FBBF24']} style={styles.actionIcon}>
                <Ionicons name="star" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>Review Net</Text>
              <Text style={styles.actionSubtitle}>Factor-wise ratings</Text>
            </TouchableOpacity>
            <View style={[styles.actionCard, { opacity: 0 }]} pointerEvents="none" />
          </View>

          {/* ══════════ §6 EXECUTE & TRACK ══════════ */}
          <Text style={styles.sectionTitle}>6 · Execute & Track</Text>
          <View style={styles.quickActions}>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/action-center' as any)}>
              <LinearGradient colors={['#0D9488', '#0F766E']} style={styles.actionIcon}>
                <Ionicons name="checkmark-done-circle" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>Action Tracker</Text>
              <Text style={styles.actionSubtitle}>Universal inbox</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/ctt' as any)}>
              <LinearGradient colors={['#1E3A5F', '#2D5F8B']} style={styles.actionIcon}>
                <Ionicons name="clipboard" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>CTT</Text>
              <Text style={styles.actionSubtitle}>Project tracker</Text>
            </TouchableOpacity>
          </View>

          {/* ══════════ §7 LIFESTYLE ARCHITECTURE ══════════ */}
          <Text style={styles.sectionTitle}>7 · Lifestyle Architecture</Text>
          <View style={styles.quickActions}>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/lifestyle' as any)}>
              <LinearGradient colors={['#065F46', '#059669']} style={styles.actionIcon}>
                <Ionicons name="leaf" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>Lifestyle Dezider</Text>
              <Text style={styles.actionSubtitle}>Decide a change</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/lifestyle-designer' as any)}>
              <LinearGradient colors={['#7C2D12', '#EA580C']} style={styles.actionIcon}>
                <Ionicons name="color-palette" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>Lifestyle Designer</Text>
              <Text style={styles.actionSubtitle}>Design daily routine</Text>
            </TouchableOpacity>
          </View>

          {/* ══════════ §8 REFLECTION & AWARENESS ══════════ */}
          <Text style={styles.sectionTitle}>8 · Reflection & Awareness</Text>
          <View style={styles.quickActions}>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/lifestyle-eval' as any)}>
              <LinearGradient colors={['#7C3AED', '#A855F7']} style={styles.actionIcon}>
                <Ionicons name="analytics" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>Lifestyle Analyzer</Text>
              <Text style={styles.actionSubtitle}>Actual vs Planned</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/consciousness-diary' as any)}>
              <LinearGradient colors={['#1E1B4B', '#3730A3']} style={styles.actionIcon}>
                <Ionicons name="eye" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>Consciousness Diary</Text>
              <Text style={styles.actionSubtitle}>Self-awareness journal</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.quickActions}>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/unconditional-happiness' as any)}>
              <LinearGradient colors={['#EC4899', '#F472B6']} style={styles.actionIcon}>
                <Ionicons name="happy" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>Unconditional Happiness</Text>
              <Text style={styles.actionSubtitle}>Celebrate · Streaks</Text>
            </TouchableOpacity>
            <View style={[styles.actionCard, { opacity: 0 }]} pointerEvents="none" />
          </View>

          {/* ══════════ §9 COLLABORATION & MANAGEMENT ══════════ */}
          <Text style={styles.sectionTitle}>9 · Collaboration & Management</Text>
          <View style={styles.quickActions}>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/collaborate' as any)}>
              <LinearGradient colors={['#7C3AED', '#A855F7']} style={styles.actionIcon}>
                <Ionicons name="git-network" size={24} color={COLORS.white} />
              </LinearGradient>
              <Text style={styles.actionTitle}>Collaboration Hub</Text>
              <Text style={styles.actionSubtitle}>Group decisions · Contacts</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/aala' as any)}>
              <LinearGradient colors={['#0EA5E9', '#2563EB']} style={styles.actionIcon}>
                <Ionicons name="wallet" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>AALA</Text>
              <Text style={styles.actionSubtitle}>Assets & Liabilities</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.quickActions}>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/time-dezider' as any)}>
              <LinearGradient colors={['#7C3AED', '#A855F7']} style={styles.actionIcon}>
                <Ionicons name="time-outline" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>Time Intelligence</Text>
              <Text style={styles.actionSubtitle}>Daily schedule AI</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/gem-flight' as any)}>
              <LinearGradient colors={['#0C1445', '#3949AB']} style={styles.actionIcon}>
                <Ionicons name="airplane" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>GEM Flight Model</Text>
              <Text style={styles.actionSubtitle}>Pilot your goals</Text>
            </TouchableOpacity>
          </View>

          {/* ══════════ MORE TOOLS (secondary utilities) ══════════ */}
          <Text style={styles.sectionTitle}>More Tools</Text>
          <View style={styles.colabRow}>
            <TouchableOpacity style={styles.colabCard} onPress={() => router.push('/inbox')}>
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
            <TouchableOpacity style={styles.colabCard} onPress={() => router.push('/notifications')}>
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
            <TouchableOpacity style={styles.colabCard} onPress={() => router.push('/analytics')}>
              <View style={[styles.colabIconWrap, { backgroundColor: 'rgba(16,185,129,0.1)' }]}>
                <Ionicons name="bar-chart" size={22} color="#10B981" />
              </View>
              <Text style={styles.colabTitle}>Analytics</Text>
              <Text style={styles.colabSubtitle}>Life areas</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.quickActions}>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/contacts' as any)}>
              <LinearGradient colors={['#1E293B', '#475569']} style={styles.actionIcon}>
                <Ionicons name="people" size={24} color={COLORS.white} />
              </LinearGradient>
              <Text style={styles.actionTitle}>Contacts</Text>
              <Text style={styles.actionSubtitle}>Manage participants</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/calendar-view')}>
              <LinearGradient colors={['#4285F4', '#5B9EF4']} style={styles.actionIcon}>
                <Ionicons name="calendar" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>Calendar</Text>
              <Text style={styles.actionSubtitle}>Schedules & deadlines</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.quickActions}>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/ai-assistant' as any)}>
              <LinearGradient colors={['#312E81', '#818CF8']} style={styles.actionIcon}>
                <Ionicons name="chatbubble-ellipses" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>AI Assistant</Text>
              <Text style={styles.actionSubtitle}>Cross-module advisor</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/public-pulse' as any)}>
              <LinearGradient colors={['#6366F1', '#8B5CF6']} style={styles.actionIcon}>
                <Ionicons name="pulse" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>Public Pulse</Text>
              <Text style={styles.actionSubtitle}>Self-discovery</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.quickActions}>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/social-learning' as any)}>
              <LinearGradient colors={['#7C3AED', '#A855F7']} style={styles.actionIcon}>
                <Ionicons name="newspaper" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>Social Learning</Text>
              <Text style={styles.actionSubtitle}>News → templates</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/tepfi')}>
              <LinearGradient colors={['#7C3AED', '#A855F7']} style={styles.actionIcon}>
                <Ionicons name="cube" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>TEPFI Matrix</Text>
              <Text style={styles.actionSubtitle}>Resource tracking</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.quickActions}>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/deo' as any)}>
              <LinearGradient colors={['#059669', '#10B981']} style={styles.actionIcon}>
                <Ionicons name="git-network" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>DEO</Text>
              <Text style={styles.actionSubtitle}>Import & API</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/cld-engine' as any)}>
              <LinearGradient colors={['#1E40AF', '#3B82F6']} style={styles.actionIcon}>
                <Ionicons name="git-network-outline" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>CLD Engine</Text>
              <Text style={styles.actionSubtitle}>Systems thinking</Text>
            </TouchableOpacity>
          </View>
          <View style={styles.quickActions}>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/time-store' as any)}>
              <LinearGradient colors={['#DC2626', '#EF4444']} style={styles.actionIcon}>
                <Ionicons name="cart-outline" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>Time Store</Text>
              <Text style={styles.actionSubtitle}>Buy back time</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionCard} onPress={() => router.push('/tools/subscription' as any)}>
              <LinearGradient colors={['#1E293B', '#334155']} style={styles.actionIcon}>
                <Ionicons name="diamond-outline" size={24} color="#FFF" />
              </LinearGradient>
              <Text style={styles.actionTitle}>Subscription</Text>
              <Text style={styles.actionSubtitle}>Credits & plans</Text>
            </TouchableOpacity>
          </View>

          {/* Stats */}
          <Text style={styles.sectionTitle}>Your Progress</Text>
          <View style={styles.statsGrid}>
            <Card style={styles.statCard}>
              <Ionicons name="analytics" size={28} color={COLORS.primary} />
              <Text style={styles.statNumber}>{stats?.decisions.total || 0}</Text>
              <Text style={styles.statLabel}>My Dezider</Text>
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

          </>
          )}
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
  // Reminder Banner
  reminderBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF2F2',
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#FECACA',
    gap: 12,
  },
  reminderBannerIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#EF4444',
    justifyContent: 'center',
    alignItems: 'center',
  },
  reminderBannerContent: {
    flex: 1,
  },
  reminderBannerTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#991B1B',
  },
  reminderBannerText: {
    fontSize: 12,
    color: '#B91C1C',
    marginTop: 2,
  },
  header: {
    padding: 24,
    paddingBottom: 32,
    borderBottomLeftRadius: 24,
    borderBottomRightRadius: 24,
  },
  headerNarrow: {
    padding: 16,
    paddingTop: 18,
    paddingBottom: 24,
  },
  headerContent: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  headerLeft: {
    flex: 1,
    minWidth: 0,
    marginRight: 8,
  },
  headerRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flexShrink: 0,
  },
  headerIconBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  headerIconBtnNarrow: {
    width: 32,
    height: 32,
    borderRadius: 16,
  },
  fontScaleRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    marginTop: -4,
    marginBottom: 6,
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
  headerLogoNarrow: {
    width: 36,
    height: 36,
    borderRadius: 9,
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
  userNameNarrow: {
    fontSize: 20,
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
    textAlign: 'center',
  },
  actionSubtitle: {
    fontSize: 12,
    color: COLORS.textSecondary,
    marginTop: 2,
    textAlign: 'center',
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
  // CTT Card styles
  cttCard: {
    marginBottom: 16,
    borderRadius: 16,
    overflow: 'hidden',
    elevation: 3,
    shadowColor: '#1E3A5F',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
  },
  cttGradient: {
    padding: 16,
    borderRadius: 16,
  },
  cttHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  cttIconWrap: {
    width: 48,
    height: 48,
    borderRadius: 14,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  cttTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFF',
  },
  cttSubtitle: {
    fontSize: 12,
    color: 'rgba(255,255,255,0.7)',
    marginTop: 2,
  },
  cttStatsRow: {
    flexDirection: 'row',
    marginTop: 16,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'space-around',
    alignItems: 'center',
  },
  cttStatItem: {
    alignItems: 'center',
  },
  cttStatNum: {
    fontSize: 18,
    fontWeight: '800',
    color: '#FFF',
  },
  cttStatLabel: {
    fontSize: 10,
    fontWeight: '600',
    color: 'rgba(255,255,255,0.6)',
    marginTop: 2,
    textTransform: 'uppercase',
  },
  cttStatDivider: {
    width: 1,
    height: 28,
    backgroundColor: 'rgba(255,255,255,0.2)',
  },
  // Calendar card styles
  calendarCard: {
    marginBottom: 16,
    borderRadius: 14,
    overflow: 'hidden',
    elevation: 2,
    shadowColor: '#4285F4',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  calendarGradient: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderRadius: 14,
  },
  calendarTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#FFF',
  },
  calendarSub: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.7)',
    marginTop: 2,
  },
});
