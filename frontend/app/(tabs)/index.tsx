// v3.19.0-VERIFY-2026-06-15 — Life Mirror · Inner Wellbeing · 9-section IA
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
import AsyncStorage from '@react-native-async-storage/async-storage';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { useAuthStore } from '../../src/store/authStore';
import { COLORS, GRADIENTS } from '../../src/constants/colors';
import { Card } from '../../src/components/Card';
import api from '../../src/utils/api';
import { FontScaleButton } from '../../src/components/FontScaleButton';
import { useDashboardTiles } from '../../src/utils/useDashboardTiles';
import { useFeatureGate } from '../../src/utils/useFeatureGate';
import { TILE_META, DEFAULT_LAYOUT, LayoutSection, chunk } from '../../src/config/dashboardTiles';

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
  const [quickLinkTiles, setQuickLinkTiles] = useState<Array<{key:string;label:string;subtitle:string;icon:string;color:string;href:string}>>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [inboxPending, setInboxPending] = useState(0);
  const [featureFlags, setFeatureFlags] = useState<FeatureFlags>({ solution_finder: false, solution_matrix: false });
  const [cttStats, setCttStats] = useState<CTTStats | null>(null);
  const [journalReminders, setJournalReminders] = useState<JournalReminder[]>([]);
  const [quotaSkus, setQuotaSkus] = useState<any[]>([]);
  const [quotaEnts, setQuotaEnts] = useState<Record<string, { granted: number; consumed: number; balance: number }>>({});
  const [quotaOpen, setQuotaOpen] = useState(false);

  // WOWO Dashboard Tile gating — single hook gates every tile on this
  // screen via the ACM `dashboard_tiles` module. Admin toggles in
  // /admin/acm hide the direct dashboard entry without affecting
  // inter-module navigation (e.g. Goal Setter is still reachable from
  // inside GEM even when `dash_goal_setter` is locked).
  const { isTileOn } = useDashboardTiles();
  const { isOn: isFeatureOn } = useFeatureGate();

  // Dashboard layout (section order, display names, tile→section assignment).
  // Admin-configurable via /admin/dashboard-layout; falls back to DEFAULT_LAYOUT.
  const [layout, setLayout] = useState<LayoutSection[]>(DEFAULT_LAYOUT);
  // Admin-customizable per-tile display names (tileId → title); overrides TILE_META.
  const [tileTitles, setTileTitles] = useState<Record<string, string>>({});
  const tileLabel = (id: string) => tileTitles[id] ?? TILE_META[id]?.title ?? id;

  // A tile is visible if it's always-on (not ACM-gated) or its ACM flag is on.
  const tileVisible = (id: string): boolean => {
    const m = TILE_META[id];
    if (!m) return false;
    // Tiles whose visibility is centrally controlled by the ACM › Collaboration
    // module (disabled by default; admin enables per audience there).
    const COLLAB_GATED: Record<string, string> = {
      inbox: 'collab_shared_inbox',
      knowledge_marketplace: 'collab_knowledge_marketplace',
      my_earnings: 'collab_my_earnings',
      karma_fame: 'collab_karma_fame',
    };
    if (COLLAB_GATED[id]) return isFeatureOn(COLLAB_GATED[id]);
    return m.alwaysOn ? true : isTileOn(id);
  };
  // A section renders when its `dash_section_<id>` flag is ON and it still has
  // at least one visible tile (so disabling every tile, or the section itself,
  // also removes the now-empty header).
  const showSection = (sec: LayoutSection): boolean => {
    if (!isTileOn(`dash_section_${sec.id}`)) return false;
    return sec.tiles.some((t) => tileVisible(t));
  };
  const showQuickLinks = isTileOn('quick_links')
    && (isTileOn('ql_decision_style') || isTileOn('ql_today_plan') || isTileOn('ql_eft'));

  // Render a single dashboard tile from the registry (gated by ACM unless always-on).
  const renderTile = (id: string) => {
    const m = TILE_META[id];
    if (!m || !tileVisible(id)) return null;
    if (m.variant === 'colab') {
      const badge = m.badgeKey === 'inbox' ? inboxPending : m.badgeKey === 'unread' ? unreadCount : 0;
      const subtitle = m.badgeKey === 'inbox'
        ? (inboxPending > 0 ? `${inboxPending} pending` : 'No pending')
        : m.badgeKey === 'unread'
          ? (unreadCount > 0 ? `${unreadCount} unread` : 'All caught up')
          : m.subtitle;
      return (
        <TouchableOpacity key={id} style={styles.colabCard} onPress={() => router.push(m.route as any)}>
          <View style={[styles.colabIconWrap, { backgroundColor: m.iconBg }]}>
            <Ionicons name={m.icon as any} size={22} color={m.iconColor} />
            {badge > 0 && (
              <View style={[styles.colabBadge, { backgroundColor: m.iconColor }]}>
                <Text style={styles.colabBadgeText}>{badge}</Text>
              </View>
            )}
          </View>
          <Text style={styles.colabTitle}>{tileLabel(id)}</Text>
          <Text style={styles.colabSubtitle}>{subtitle}</Text>
        </TouchableOpacity>
      );
    }
    return (
      <TouchableOpacity key={id} style={styles.actionCard} onPress={() => router.push(m.route as any)}>
        <LinearGradient colors={(m.gradient || ['#64748B', '#475569']) as any} style={styles.actionIcon}>
          <Ionicons name={m.icon as any} size={24} color={COLORS.white} />
        </LinearGradient>
        <Text style={styles.actionTitle}>{tileLabel(id)}</Text>
        <Text style={styles.actionSubtitle}>{m.subtitle}</Text>
      </TouchableOpacity>
    );
  };

  // Render all visible sections in admin-configured order, auto-numbered 1..N.
  const renderDashboardSections = () => {
    let n = 0;
    return layout.map((sec) => {
      if (!showSection(sec)) return null;
      n += 1;
      const visibleTiles = sec.tiles.filter(tileVisible);
      const colabTiles = visibleTiles.filter((t) => TILE_META[t]?.variant === 'colab');
      const actionTiles = visibleTiles.filter((t) => TILE_META[t]?.variant !== 'colab');
      return (
        <View key={sec.id}>
          <Text style={styles.sectionTitle}>{`${sec.emoji ? sec.emoji + ' ' : ''}${n} · ${sec.name}`}</Text>
          {chunk(colabTiles, 3).map((row, i) => (
            <View key={`c${i}`} style={styles.colabRow}>{row.map(renderTile)}</View>
          ))}
          {chunk(actionTiles, 2).map((row, i) => (
            <View key={`a${i}`} style={styles.quickActions}>{row.map(renderTile)}</View>
          ))}
        </View>
      );
    });
  };

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
    // If the user arrived via a shared-report deep link and just authenticated,
    // they land on the dashboard — route them to the Shared tab so the report
    // (e.g. a Decision-Making-Style result) is actually shown & auto-accepted.
    (async () => {
      try {
        const pend = await AsyncStorage.getItem('pending_share_token');
        if (pend) router.replace('/(tabs)/shared' as any);
      } catch { /* ignore */ }
    })();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await api.get('/stats');
      setStats(response.data);
      // Piggyback: fetch admin-configured user Quick Links (max 3)
      try {
        const qr = await api.get('/home/quicklinks');
        setQuickLinkTiles(qr.data?.tiles || []);
      } catch { /* silent */ }
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

  const fetchQuota = async () => {
    try {
      const [s, e] = await Promise.all([
        api.get('/store/skus'),
        api.get('/store/my-entitlements').catch(() => ({ data: { entitlements: [] } })),
      ]);
      setQuotaSkus(s.data.skus || []);
      const map: Record<string, { granted: number; consumed: number; balance: number }> = {};
      (e.data.entitlements || []).forEach((it: any) => {
        map[it.sku_code] = {
          granted: it.granted_qty || 0,
          consumed: it.consumed_qty || 0,
          balance: it.balance || 0,
        };
      });
      setQuotaEnts(map);
    } catch (error) {
      console.error('Error fetching quota:', error);
    }
  };

  const fetchLayout = async () => {
    try {
      const r = await api.get('/dashboard-layout');
      if (Array.isArray(r.data?.sections) && r.data.sections.length) {
        // Merge saved layout with the registry so newly-added always-on tiles
        // (e.g. The Decider Store) still appear even when the DB layout predates
        // them. Admin removals of non-always-on tiles are still respected.
        const saved: LayoutSection[] = r.data.sections;
        const savedIds = new Set(saved.map((s) => s.id));
        const merged: LayoutSection[] = saved.map((s) => {
          const def = DEFAULT_LAYOUT.find((d) => d.id === s.id);
          if (!def) return s;
          const missing = def.tiles.filter((t) => !s.tiles.includes(t) && TILE_META[t]?.alwaysOn);
          return missing.length ? { ...s, tiles: [...s.tiles, ...missing] } : s;
        });
        DEFAULT_LAYOUT.forEach((d) => { if (!savedIds.has(d.id)) merged.push(d); });
        setLayout(merged);
      }
      if (r.data?.tile_titles && typeof r.data.tile_titles === 'object') {
        setTileTitles(r.data.tile_titles);
      }
    } catch (error) {
      console.error('Error fetching dashboard layout:', error);
    }
  };

  const fetchAll = async () => {
    await Promise.all([fetchStats(), fetchUnreadCount(), fetchInboxCount(), fetchFeatureFlags(), fetchCttStats(), fetchJournalReminders(), fetchQuota(), fetchLayout()]);
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
      case 'consciousness': return COLORS.consciousness;
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
          {/* ════════ Report Quota Summary (glanceable for everyone) ════════ */}
          {isTileOn('report_quota') && (
          <View style={styles.quotaCard}>
            <View style={styles.quotaHeader}>
              <TouchableOpacity style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flex: 1 }} activeOpacity={0.7} onPress={() => setQuotaOpen((o) => !o)}>
                <Ionicons name="documents" size={18} color={COLORS.primary} />
                <Text style={styles.quotaHeaderTitle}>Your Report Quota</Text>
                <Ionicons name={quotaOpen ? 'chevron-up' : 'chevron-down'} size={16} color={COLORS.textMuted} />
              </TouchableOpacity>
              <TouchableOpacity onPress={() => router.push('/store' as any)} style={styles.quotaBuyBtn} accessibilityLabel="Buy more reports">
                <Ionicons name="add" size={14} color="#FFF" />
                <Text style={styles.quotaBuyText}>Buy more</Text>
              </TouchableOpacity>
            </View>
            {quotaOpen && (quotaSkus.filter((sk: any) => sk.active).length === 0 ? (
              <Text style={styles.quotaEmpty}>Loading your balances…</Text>
            ) : (
              quotaSkus.filter((sk: any) => sk.active).map((sk: any) => {
                const m = quotaEnts[sk.code] || { granted: 0, consumed: 0, balance: 0 };
                return (
                  <View key={sk.code} style={styles.quotaRow}>
                    <View style={styles.quotaRowLeft}>
                      <View style={[styles.quotaBadge, { backgroundColor: (sk.badge_color || '#7C3AED') + '22' }]}>
                        <Text style={[styles.quotaBadgeText, { color: sk.badge_color || '#7C3AED' }]}>{sk.code}</Text>
                      </View>
                      <Text style={styles.quotaSkuName} numberOfLines={1}>{sk.name}</Text>
                    </View>
                    <View style={styles.quotaMetrics}>
                      <View style={styles.quotaMetric}><Text style={styles.quotaMetricNum}>{m.granted}</Text><Text style={styles.quotaMetricLabel}>Bought</Text></View>
                      <View style={styles.quotaMetric}><Text style={[styles.quotaMetricNum, { color: '#D97706' }]}>{m.consumed}</Text><Text style={styles.quotaMetricLabel}>Used</Text></View>
                      <View style={styles.quotaMetric}><Text style={[styles.quotaMetricNum, { color: '#059669' }]}>{m.balance}</Text><Text style={styles.quotaMetricLabel}>Left</Text></View>
                    </View>
                  </View>
                );
              })
            ))}
          </View>
          )}

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
              24 AI GUIDES — 8-Section Dashboard (June 2026 — revised order)
              -------------------------------------------------------------
              §1 🌌 Self Discovery       →  My 360° Life · GEM
              §2 🔮 Decision Kickstarters → MyDezider · Test123 · Pros&Cons · Solution Finder
              §3 ❤️ Inner State          →  Emotional Gatekeeper · Conflict Breaker
              §4 🎯 Goals & Manifestation → Goal Setter · Manifestation
              §5 ✅ Execute & Track      →  Action Tracker · CTT · Lifestyle Dezider
              §6 🪞 Reflection & Awareness → Life Mirror · Outlet Analyzer · AIM Manager ·
                                            Capabilities & Resources Index · Lifestyle Designer ·
                                            Lifestyle Analyzer · Consciousness Diary · Unconditional Happiness
              §7 👥 Collaboration & Management → Collaboration · AALA · Time Intelligence · GEM Flight Model
              §8 🧩 Solution Space       →  Solution Store · Review Net · DEO · Time Store
              §9 More Tools              →  secondary utilities
              Pinned strip on top → "Pick up where you left off"
              ════════════════════════════════════════════════════════════════ */}

          {/* PINNED — "Quick Links" (admin-configured max 3 tiles via /admin/user-quicklinks) */}
          {showQuickLinks && quickLinkTiles.length > 0 && (<>
          <Text style={styles.sectionTitle}>Quick Links</Text>
          <Text style={styles.sectionSubtitle}>Pick up where you left off</Text>
          <View style={styles.colabRow}>
            {quickLinkTiles.map((t) => (
              <TouchableOpacity
                key={t.key}
                style={styles.colabCard}
                onPress={() => {
                  // Special case: 'decision_style' still uses the profile-embedded quiz
                  if (t.key === 'decision_style') {
                    router.push('/(tabs)/profile?startQuiz=self' as any);
                  } else {
                    router.push(t.href as any);
                  }
                }}
              >
                <View style={[styles.colabIconWrap, { backgroundColor: t.color + '20' }]}>
                  <Ionicons name={t.icon as any} size={22} color={t.color} />
                </View>
                <Text style={styles.colabTitle} numberOfLines={1}>{t.label}</Text>
                <Text style={styles.colabSubtitle} numberOfLines={1}>
                  {t.key === 'decision_style' && stats?.latest_assessment?.dominant_mode
                    ? `${stats.latest_assessment.dominant_mode}` : t.subtitle}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          </>)}

          {/* ══════════ Dashboard sections (admin-configurable layout) ══════════
              Order, display names and tile placement come from
              /admin/dashboard-layout; visibility from ACM (dash_section_* / dash_*).
              Visible sections auto-number 1..N (no gaps when hidden). */}
          {renderDashboardSections()}

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
              <Text style={styles.statSubtext}>Instant Dezider sessions</Text>
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
              <View style={[styles.modeDot, { backgroundColor: COLORS.consciousness }]} />
              <View style={styles.modeInfo}>
                <Text style={styles.modeName}>Consciousness</Text>
                <Text style={styles.modeDesc}>~100% accuracy, detached clarity</Text>
              </View>
            </View>
            <TouchableOpacity
              style={styles.takeQuizButton}
              onPress={() => router.push('/(tabs)/profile?startQuiz=self')}
            >
              <Text style={styles.takeQuizText}>Take Quiz & Know your Decision Style</Text>
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
  // Report Quota card
  quotaCard: {
    backgroundColor: COLORS.white,
    borderRadius: 16,
    padding: 14,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: COLORS.border,
    boxShadow: '0px 2px 8px rgba(0, 0, 0, 0.05)',
    elevation: 2,
  },
  quotaHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
  },
  quotaHeaderTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: COLORS.textPrimary,
  },
  quotaBuyBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    backgroundColor: COLORS.primary,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
  },
  quotaBuyText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
  },
  quotaEmpty: {
    fontSize: 12,
    color: COLORS.textMuted,
    paddingVertical: 8,
  },
  quotaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    borderTopWidth: 1,
    borderTopColor: COLORS.divider,
  },
  quotaRowLeft: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    minWidth: 0,
  },
  quotaBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  quotaBadgeText: {
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  quotaSkuName: {
    fontSize: 13,
    color: COLORS.textSecondary,
    flexShrink: 1,
  },
  quotaMetrics: {
    flexDirection: 'row',
    gap: 14,
  },
  quotaMetric: {
    alignItems: 'center',
    minWidth: 44,
  },
  quotaMetricNum: {
    fontSize: 17,
    fontWeight: '800',
    color: COLORS.textPrimary,
  },
  quotaMetricLabel: {
    fontSize: 9,
    fontWeight: '600',
    color: COLORS.textMuted,
    textTransform: 'uppercase',
    marginTop: 1,
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
  sectionSubtitle: {
    fontSize: 12,
    fontWeight: '500',
    color: COLORS.textSecondary,
    marginTop: -8,
    marginBottom: 12,
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
