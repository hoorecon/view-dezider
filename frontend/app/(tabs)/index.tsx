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
import { useCompany } from '../../src/contexts/FontFamilyContext';
import { useDashboardTiles } from '../../src/utils/useDashboardTiles';
import { useFeatureGate } from '../../src/utils/useFeatureGate';
import { TILE_META, DEFAULT_LAYOUT, LayoutSection, chunk } from '../../src/config/dashboardTiles';

const DISPLAY_FONT = Platform.OS === 'web' ? 'Fraunces, Georgia, "Times New Roman", serif' : undefined;
const OUTFIT_FONT = Platform.OS === 'web' ? 'Outfit, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' : undefined;
const SANS_FONT = Platform.OS === 'web' ? '"Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' : undefined;
const TECH_FONT = Platform.OS === 'web' ? '"Space Grotesk", -apple-system, BlinkMacSystemFont, monospace' : undefined;

const liftProp = Platform.OS === 'web' ? { dataSet: { lift: '1' } } : {};
const displayProp: any = Platform.OS === 'web' ? { dataSet: { display: '1' } } : {};
const outfitProp: any = Platform.OS === 'web' ? { dataSet: { outfit: '1' } } : {};
const sansProp: any = Platform.OS === 'web' ? { dataSet: { sans: '1' } } : {};
const techProp: any = Platform.OS === 'web' ? { dataSet: { tech: '1' } } : {};

const cardShadow = Platform.OS === 'web'
  ? { boxShadow: '0 14px 38px rgba(88, 28, 135, 0.08)' } as any
  : { elevation: 2 };

type ModVariant = 'gradient' | 'dark' | 'outline' | 'row' | 'chip';
const MODULE_VARIANT: Record<string, ModVariant> = {
  self_discovery: 'gradient',
  decision_kickstarters: 'dark',
  problem_solvers: 'outline',
  goals_manifestation: 'gradient',
  execute_track: 'row',
  reflection_awareness: 'chip',
  collaboration_mgmt: 'dark',
  solution_space: 'outline',
  more_tools: 'chip',
};

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
  const company = useCompany();
  const { user } = useAuthStore();
  const { width: winWidth } = useWindowDimensions();
  const isNarrow = winWidth < 480;
  const isWide = winWidth >= 1020;
  const isMid = winWidth >= 720;
  const [selectedGroup, setSelectedGroup] = useState<string>('all');
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

  // Render all visible sections in admin-configured order, styled with landing page module variants.
  const renderDashboardSections = () => {
    const half = isWide ? '48.5%' : '100%';

    return layout.map((sec) => {
      if (!showSection(sec)) return null;
      if (selectedGroup !== 'all' && selectedGroup !== sec.id) return null;
      const visibleTiles = sec.tiles.filter(tileVisible);
      if (!visibleTiles.length) return null;

      const variant = MODULE_VARIANT[sec.id] || 'outline';
      const cols = !isWide && !isMid ? 1 : !isWide || visibleTiles.length === 2 || visibleTiles.length === 4 ? 2 : 3;
      const third: any = cols === 1 ? '100%'
        : Platform.OS === 'web' ? `calc((100% - ${(cols - 1) * 16}px) / ${cols})`
        : cols === 2 ? '47.5%' : '31.5%';

      return (
        <View key={sec.id} style={styles.modGroup}>
          <View style={styles.groupHead}>
            <Text style={styles.groupLabel}>{sec.name}</Text>
            <Text style={styles.groupCount}>
              {visibleTiles.length} {visibleTiles.length === 1 ? 'module' : 'modules'}
            </Text>
          </View>
          <View style={styles.modGrid}>
            {visibleTiles.map((id) => {
              const tile = TILE_META[id];
              if (!tile) return null;
              const tone = tile.gradient?.[0] || COLORS.primary;
              const tone2 = tile.gradient?.[1] || tone;
              const icon = tile.icon as any;

              if (variant === 'gradient') {
                return (
                  <TouchableOpacity
                    key={id}
                    activeOpacity={0.9}
                    onPress={() => router.push(tile.route as any)}
                    style={[styles.modGrad, { flexBasis: half }]}
                    {...liftProp}
                  >
                    <LinearGradient
                      colors={[tone, tone2] as unknown as readonly [string, string]}
                      start={{ x: 0, y: 0 }}
                      end={{ x: 1, y: 1 }}
                      style={StyleSheet.absoluteFillObject}
                    />
                    <View style={styles.modGradWatermark}>
                      <Ionicons name={icon} size={150} color="rgba(255,255,255,0.12)" />
                    </View>
                    <View style={styles.modTagLight}>
                      <Text style={styles.modTagLightText}>{sec.name}</Text>
                    </View>
                    <Text {...displayProp} style={styles.modGradTitle}>{tileLabel(id)}</Text>
                    <Text style={styles.modGradSub}>{tile.subtitle}</Text>
                    <View style={styles.modGradCta}>
                      <Text style={styles.modGradCtaText}>Explore module</Text>
                      <Ionicons name="arrow-forward" size={14} color="#FFFFFF" />
                    </View>
                  </TouchableOpacity>
                );
              }

              if (variant === 'dark') {
                return (
                  <TouchableOpacity
                    key={id}
                    activeOpacity={0.9}
                    onPress={() => router.push(tile.route as any)}
                    style={[styles.modDark, { flexBasis: third, maxWidth: isWide || isMid ? third : '100%' }]}
                    {...liftProp}
                  >
                    <View style={[styles.modDarkGlow, { backgroundColor: tone }]} />
                    <View style={styles.modDarkTop}>
                      <View style={[styles.modDarkIcon, { borderColor: tone + '80' }]}>
                        <Ionicons name={icon} size={20} color={tone2} />
                      </View>
                      <View style={styles.modArrowDark}>
                        <Ionicons name="arrow-up-outline" size={15} color="#FFFFFF" style={{ transform: [{ rotate: '45deg' }] }} />
                      </View>
                    </View>
                    <Text {...techProp} style={styles.modDarkTitle}>{tileLabel(id)}</Text>
                    <Text style={styles.modDarkSub}>{tile.subtitle}</Text>
                  </TouchableOpacity>
                );
              }

              if (variant === 'row') {
                return (
                  <TouchableOpacity
                    key={id}
                    activeOpacity={0.9}
                    onPress={() => router.push(tile.route as any)}
                    style={[styles.modRow, { flexBasis: half }]}
                    {...liftProp}
                  >
                    <LinearGradient
                      colors={[tone, tone2] as unknown as readonly [string, string]}
                      start={{ x: 0, y: 0 }}
                      end={{ x: 1, y: 1 }}
                      style={styles.modRowIcon}
                    >
                      <Ionicons name={icon} size={22} color="#FFFFFF" />
                    </LinearGradient>
                    <View style={{ flex: 1 }}>
                      <Text {...displayProp} style={styles.modRowTitle}>{tileLabel(id)}</Text>
                      <Text style={styles.cardDesc} numberOfLines={2}>{tile.subtitle}</Text>
                    </View>
                    <View style={[styles.modRowArrow, { backgroundColor: tone + '14' }]}>
                      <Ionicons name="chevron-forward" size={18} color={tone} />
                    </View>
                  </TouchableOpacity>
                );
              }

              if (variant === 'chip') {
                return (
                  <TouchableOpacity
                    key={id}
                    activeOpacity={0.9}
                    onPress={() => router.push(tile.route as any)}
                    style={[styles.modChip, { flexBasis: third, maxWidth: isWide || isMid ? third : '100%' }]}
                    {...liftProp}
                  >
                    <View style={[styles.modChipDot, { backgroundColor: tone + '1A' }]}>
                      <Ionicons name={icon} size={16} color={tone} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text {...sansProp} style={styles.modChipTitle}>{tileLabel(id)}</Text>
                      <Text style={styles.modChipSub} numberOfLines={1}>{tile.subtitle}</Text>
                    </View>
                    <Ionicons name="arrow-forward" size={15} color={tone} />
                  </TouchableOpacity>
                );
              }

              // 'outline' variant
              return (
                <TouchableOpacity
                  key={id}
                  activeOpacity={0.9}
                  onPress={() => router.push(tile.route as any)}
                  style={[styles.modOutline, { flexBasis: third, maxWidth: isWide || isMid ? third : '100%' }]}
                  {...liftProp}
                >
                  <LinearGradient
                    colors={[tone + '26', tone + '00'] as unknown as readonly [string, string]}
                    start={{ x: 1, y: 0 }}
                    end={{ x: 0.2, y: 0.8 }}
                    style={styles.modOutlineWash}
                  />
                  <View style={[styles.modOutlineIcon, { backgroundColor: tone }]}>
                    <Ionicons name={icon} size={18} color="#FFFFFF" />
                  </View>
                  <Text {...outfitProp} style={styles.modOutlineTitle}>{tileLabel(id)}</Text>
                  <Text style={styles.cardDesc}>{tile.subtitle}</Text>
                  <View style={styles.modOutlineFoot}>
                    <Text style={[styles.modOutlineLink, { color: tone }]}>Open module</Text>
                    <Ionicons name="arrow-forward" size={14} color={tone} />
                  </View>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>
      );
    });
  };

  // ---------------------------------------------------------------------------
  // Hydration-safe client mount gate
  // ---------------------------------------------------------------------------
  const [isClient, setIsClient] = useState(false);
  useEffect(() => {
    setIsClient(true);
    if (Platform.OS === 'web' && typeof document !== 'undefined') {
      const fontId = 'jelcos-web-fonts';
      if (!document.getElementById(fontId)) {
        const font = document.createElement('link');
        font.id = fontId;
        font.rel = 'stylesheet';
        font.href = 'https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,500..800;1,9..144,500..800&family=Outfit:wght@500;600;700;800&family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Space+Grotesk:wght@600;700&display=swap';
        document.head.appendChild(font);
      }
      const styleId = 'jelcos-dashboard-motion';
      if (!document.getElementById(styleId)) {
        const style = document.createElement('style');
        style.id = styleId;
        style.textContent = `
          [data-lift="1"] {
            transition: transform .22s ease, box-shadow .22s ease, border-color .22s ease;
            cursor: pointer;
          }
          [data-lift="1"]:hover {
            transform: translateY(-4px);
            box-shadow: 0 18px 40px rgba(26, 35, 126, 0.12);
            border-color: #E4D6F2;
          }
          [data-display="1"], [data-display="1"] span {
            font-family: 'Fraunces', Georgia, 'Times New Roman', serif !important;
          }
          [data-outfit="1"], [data-outfit="1"] span {
            font-family: 'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
          }
          [data-sans="1"], [data-sans="1"] span {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
          }
          [data-tech="1"], [data-tech="1"] span {
            font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, monospace !important;
          }
        `;
        document.head.appendChild(style);
      }
    }
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

          {/* ══════════ Category Filter Pills Menu (Above Quick Links) ══════════ */}
          <View style={styles.modulesHeader}>
            <View style={styles.filters}>
              <TouchableOpacity
                style={[styles.filterChip, selectedGroup === 'all' && styles.filterChipOn]}
                onPress={() => setSelectedGroup('all')}
                activeOpacity={0.8}
                {...liftProp}
              >
                <Text style={[styles.filterText, selectedGroup === 'all' && styles.filterTextOn]}>
                  All modules
                </Text>
              </TouchableOpacity>
              {layout.map((section) => {
                if (!showSection(section)) return null;
                const count = section.tiles.filter(tileVisible).length;
                if (!count) return null;
                const on = selectedGroup === section.id;
                return (
                  <TouchableOpacity
                    key={section.id}
                    style={[styles.filterChip, on && styles.filterChipOn]}
                    onPress={() => setSelectedGroup(section.id)}
                    activeOpacity={0.8}
                    {...liftProp}
                  >
                    <Text style={[styles.filterText, on && styles.filterTextOn]}>
                      {section.name}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </View>

          {/* PINNED — "Quick Links" (admin-configured max 3 tiles via /admin/user-quicklinks) */}
          {showQuickLinks && quickLinkTiles.length > 0 && (<>
          <View style={styles.quickLinksHeader}>
            <Text {...displayProp} style={styles.sectionTitle}>Quick Links</Text>
            <Text style={styles.sectionSubtitle}>Pick up where you left off</Text>
          </View>
          <View style={styles.colabRow}>
            {quickLinkTiles.map((t, idx) => {
              const accentColor = t.color || (idx === 0 ? '#7C3AED' : idx === 1 ? '#EC4899' : '#F59E0B');
              const tagLabel = t.key === 'decision_style' ? 'ASSESSMENT' : t.key.includes('store') ? 'STORE' : idx === 0 ? 'INSIGHT' : idx === 1 ? 'STORE' : 'WELLBEING';
              const fontProp = idx % 3 === 0 ? displayProp : idx % 3 === 1 ? outfitProp : sansProp;
              return (
                <TouchableOpacity
                  key={t.key}
                  style={[styles.colabCard, { borderColor: accentColor + '30' }]}
                  activeOpacity={0.88}
                  {...liftProp}
                  onPress={() => {
                    // Special case: 'decision_style' still uses the profile-embedded quiz
                    if (t.key === 'decision_style') {
                      router.push('/(tabs)/profile?startQuiz=self' as any);
                    } else {
                      router.push(t.href as any);
                    }
                  }}
                >
                  <LinearGradient
                    colors={[accentColor + '16', '#FFFFFF', '#FFFFFF']}
                    start={{ x: 0, y: 0 }}
                    end={{ x: 1, y: 1 }}
                    style={styles.colabCardBg}
                  />
                  <View style={styles.colabCardTop}>
                    <View style={[styles.colabIconWrap, { backgroundColor: accentColor + '18', borderColor: accentColor + '2E' }]}>
                      <Ionicons name={t.icon as any} size={22} color={accentColor} />
                    </View>
                    <View style={styles.colabCardTopRight}>
                      <View style={[styles.colabTag, { backgroundColor: accentColor + '14', borderColor: accentColor + '28' }]}>
                        <Text style={[styles.colabTagText, { color: accentColor }]}>{tagLabel}</Text>
                      </View>
                      <View style={[styles.colabArrow, { backgroundColor: accentColor + '12' }]}>
                        <Ionicons name="arrow-up-outline" size={13} color={accentColor} style={{ transform: [{ rotate: '45deg' }] }} />
                      </View>
                    </View>
                  </View>
                  <Text {...fontProp} style={styles.colabTitle} numberOfLines={1}>{t.label}</Text>
                  <Text style={styles.colabSubtitle} numberOfLines={2}>
                    {t.key === 'decision_style' && stats?.latest_assessment?.dominant_mode
                      ? `Dominant: ${stats.latest_assessment.dominant_mode}` : t.subtitle}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
          </>)}

          {/* ══════════ Dashboard sections (admin-configurable layout) ══════════
              Order, display names and tile placement come from
              /admin/dashboard-layout; visibility from ACM (dash_section_* / dash_*).
              Visible sections auto-number 1..N (no gaps when hidden). */}
          {renderDashboardSections()}

          {/* Stats */}
          <Text {...displayProp} style={styles.sectionTitle}>Your Progress</Text>
          <View style={styles.statsGrid}>
            <Card style={styles.statCard}>
              <Ionicons name="analytics" size={28} color={COLORS.primary} />
              <Text {...techProp} style={styles.statNumber}>{stats?.decisions.total || 0}</Text>
              <Text style={styles.statLabel}>My Dezider</Text>
              <Text style={styles.statSubtext}>
                {stats?.decisions.completed || 0} completed
              </Text>
            </Card>

            <Card style={styles.statCard}>
              <Ionicons name="flash" size={28} color={COLORS.accent} />
              <Text {...techProp} style={styles.statNumber}>{stats?.test123.total || 0}</Text>
              <Text style={styles.statLabel}>Quick Decisions</Text>
              <Text style={styles.statSubtext}>Instant Dezider sessions</Text>
            </Card>

            <Card style={styles.statCard}>
              <Ionicons name="book" size={28} color={COLORS.teal} />
              <Text {...techProp} style={styles.statNumber}>{stats?.journal.total || 0}</Text>
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
                  <Text {...techProp} style={[styles.statNumber, { fontSize: 14, textTransform: 'capitalize' }]}>
                    {stats.latest_assessment.dominant_mode}
                  </Text>
                  <Text style={styles.statLabel}>Decision Mode</Text>
                  <Text style={styles.statSubtext}>Your style</Text>
                </>
              ) : (
                <>
                  <Ionicons name="compass-outline" size={28} color={COLORS.textMuted} />
                  <Text {...techProp} style={[styles.statNumber, { fontSize: 14 }]}>Not taken</Text>
                  <Text style={styles.statLabel}>Assessment</Text>
                  <Text style={styles.statSubtext}>Take quiz</Text>
                </>
              )}
            </Card>
          </View>

          {/* Decision Modes Info */}
          <Text {...displayProp} style={styles.sectionTitle}>Decision Making Modes</Text>
          <Card style={styles.modesCard}>
            <View style={styles.modeRow}>
              <View style={[styles.modeDot, { backgroundColor: COLORS.emotional }]} />
              <View style={styles.modeInfo}>
                <Text {...outfitProp} style={styles.modeName}>Emotional</Text>
                <Text style={styles.modeDesc}>30-40% accuracy, comfortable but short-term</Text>
              </View>
            </View>
            <View style={styles.modeRow}>
              <View style={[styles.modeDot, { backgroundColor: COLORS.logical }]} />
              <View style={styles.modeInfo}>
                <Text {...outfitProp} style={styles.modeName}>Logical</Text>
                <Text style={styles.modeDesc}>50-60% accuracy, rational but lacks heart</Text>
              </View>
            </View>
            <View style={styles.modeRow}>
              <View style={[styles.modeDot, { backgroundColor: COLORS.intuitive }]} />
              <View style={styles.modeInfo}>
                <Text {...outfitProp} style={styles.modeName}>Intuitive</Text>
                <Text style={styles.modeDesc}>70-80% accuracy, insight-driven</Text>
              </View>
            </View>
            <View style={styles.modeRow}>
              <View style={[styles.modeDot, { backgroundColor: COLORS.consciousness }]} />
              <View style={styles.modeInfo}>
                <Text {...outfitProp} style={styles.modeName}>Consciousness</Text>
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
    backgroundColor: '#FAF7FD',
  },
  content: {
    padding: 18,
    maxWidth: 1140,
    width: '100%',
    alignSelf: 'center',
  },
  // Header
  header: {
    padding: 24,
    paddingBottom: 32,
    borderBottomLeftRadius: 28,
    borderBottomRightRadius: 28,
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
  greeting: {
    fontSize: 16,
    color: 'rgba(255,255,255,0.85)',
    fontWeight: '500',
  },
  userName: {
    fontSize: 26,
    fontWeight: '800',
    color: '#FFFFFF',
    letterSpacing: -0.4,
  },
  userNameNarrow: {
    fontSize: 20,
  },
  tagline: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.75)',
    fontStyle: 'italic',
  },
  headerLogo: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: '#FFFFFF',
  },
  headerLogoNarrow: {
    width: 32,
    height: 32,
    borderRadius: 9,
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

  // Reminder Banner
  reminderBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF2F2',
    borderRadius: 16,
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

  // Section Headers
  quickLinksHeader: {
    marginBottom: 4,
  },
  sectionTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: '#16132A',
    fontFamily: DISPLAY_FONT,
    marginBottom: 10,
    marginTop: 14,
    letterSpacing: -0.3,
  },
  sectionSubtitle: {
    fontSize: 13,
    fontWeight: '500',
    color: '#6B6480',
    marginTop: -6,
    marginBottom: 14,
  },

  // Modules Category Filters Menu
  modulesHeader: {
    marginTop: 6,
    marginBottom: 16,
    alignItems: 'center',
    width: '100%',
  },
  filters: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    justifyContent: 'center',
    maxWidth: 1120,
    alignSelf: 'center',
  },
  filterChip: {
    paddingHorizontal: 16,
    paddingVertical: 9,
    borderRadius: 999,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E8DCF3',
    ...cardShadow,
  },
  filterChipOn: {
    backgroundColor: '#8E24AA',
    borderColor: '#8E24AA',
    shadowColor: '#8E24AA',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.28,
    shadowRadius: 10,
    elevation: 4,
  },
  filterText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#5E35B1',
    letterSpacing: 0.2,
  },
  filterTextOn: {
    color: '#FFFFFF',
  },

  // ══════════════════════════════════════════════════
  // Landing Page Module Styling & Variants
  // ══════════════════════════════════════════════════
  modGroup: {
    marginTop: 28,
    marginBottom: 6,
    width: '100%',
  },
  groupHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 14,
  },
  groupLabel: {
    fontSize: 13,
    fontWeight: '800',
    letterSpacing: 1.2,
    color: '#5E35B1',
    textTransform: 'uppercase',
  },
  groupCount: {
    fontSize: 12,
    fontWeight: '700',
    color: '#9AA0B4',
  },
  modGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 16,
  },
  cardDesc: {
    fontSize: 13.5,
    lineHeight: 20,
    color: '#5B5470',
  },

  // 1. Gradient Variant
  modGrad: {
    flexGrow: 1,
    borderRadius: 24,
    padding: 26,
    minHeight: 220,
    overflow: 'hidden',
    justifyContent: 'flex-end',
    ...cardShadow,
  },
  modGradWatermark: {
    position: 'absolute',
    right: -16,
    top: -12,
  },
  modTagLight: {
    alignSelf: 'flex-start',
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 999,
    backgroundColor: 'rgba(255,255,255,0.18)',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.3)',
    marginBottom: 'auto',
  },
  modTagLightText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1.2,
    textTransform: 'uppercase',
  },
  modGradTitle: {
    color: '#FFFFFF',
    fontSize: 26,
    lineHeight: 32,
    fontWeight: '700',
    fontFamily: DISPLAY_FONT,
    marginTop: 40,
    letterSpacing: -0.3,
  },
  modGradSub: {
    color: 'rgba(255,255,255,0.88)',
    fontSize: 14,
    lineHeight: 20,
    marginTop: 6,
    maxWidth: 380,
  },
  modGradCta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    alignSelf: 'flex-start',
    marginTop: 18,
    paddingHorizontal: 15,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: 'rgba(10,26,79,0.28)',
  },
  modGradCtaText: {
    color: '#FFFFFF',
    fontSize: 12.5,
    fontWeight: '700',
  },

  // 2. Dark Variant
  modDark: {
    flexGrow: 1,
    borderRadius: 24,
    padding: 24,
    minHeight: 200,
    overflow: 'hidden',
    backgroundColor: '#14307D',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.08)',
    ...cardShadow,
  },
  modDarkGlow: {
    position: 'absolute',
    width: 180,
    height: 180,
    borderRadius: 999,
    top: -70,
    right: -50,
    opacity: 0.35,
    ...(Platform.OS === 'web' ? ({ filter: 'blur(50px)' } as any) : {}),
  },
  modDarkTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 'auto',
  },
  modDarkIcon: {
    width: 44,
    height: 44,
    borderRadius: 14,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.04)',
  },
  modArrowDark: {
    width: 32,
    height: 32,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.1)',
  },
  modDarkTitle: {
    color: '#FFFFFF',
    fontSize: 20,
    fontWeight: '800',
    marginTop: 32,
    letterSpacing: -0.3,
  },
  modDarkSub: {
    color: 'rgba(255,255,255,0.65)',
    fontSize: 13.5,
    lineHeight: 20,
    marginTop: 6,
  },

  // 3. Row Variant
  modRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    flexGrow: 1,
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 16,
    borderWidth: 1,
    borderColor: '#EDE3F5',
    ...cardShadow,
  },
  modRowIcon: {
    width: 52,
    height: 52,
    borderRadius: 15,
    alignItems: 'center',
    justifyContent: 'center',
  },
  modRowTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: '#16132A',
    fontFamily: DISPLAY_FONT,
    marginBottom: 3,
  },
  modRowArrow: {
    width: 36,
    height: 36,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
  },

  // 4. Chip Variant
  modChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    flexGrow: 1,
    backgroundColor: '#FFFFFF',
    borderRadius: 999,
    paddingLeft: 8,
    paddingRight: 18,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: '#E9DDF3',
    ...cardShadow,
  },
  modChipDot: {
    width: 38,
    height: 38,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
  },
  modChipTitle: {
    fontSize: 13.5,
    fontWeight: '700',
    color: '#16132A',
  },
  modChipSub: {
    fontSize: 11.5,
    color: '#6B6480',
    marginTop: 1,
  },

  // 5. Outline Variant
  modOutline: {
    flexGrow: 1,
    borderRadius: 24,
    padding: 24,
    minHeight: 200,
    overflow: 'hidden',
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#EADFF3',
    ...cardShadow,
  },
  modOutlineWash: {
    position: 'absolute',
    top: 0,
    right: 0,
    width: '70%',
    height: '70%',
  },
  modOutlineIcon: {
    width: 40,
    height: 40,
    borderRadius: 999,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 18,
  },
  modOutlineTitle: {
    fontSize: 22,
    lineHeight: 28,
    fontWeight: '700',
    color: '#16132A',
    fontFamily: DISPLAY_FONT,
    marginBottom: 6,
    letterSpacing: -0.3,
  },
  modOutlineFoot: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 'auto',
    paddingTop: 16,
  },
  modOutlineLink: {
    fontSize: 12.5,
    fontWeight: '800',
    letterSpacing: 0.3,
  },

  // Quick Links
  colabRow: {
    flexDirection: 'row',
    gap: 14,
    marginBottom: 20,
    flexWrap: 'wrap',
  },
  colabCard: {
    flex: 1,
    minWidth: 180,
    backgroundColor: '#FFFFFF',
    borderRadius: 22,
    padding: 18,
    position: 'relative',
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: '#EDE1F5',
    ...cardShadow,
  },
  colabCardBg: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
  },
  colabCardTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 14,
  },
  colabCardTopRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  colabIconWrap: {
    width: 44,
    height: 44,
    borderRadius: 14,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
  },
  colabTag: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
    borderWidth: 1,
  },
  colabTagText: {
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 0.6,
  },
  colabArrow: {
    width: 26,
    height: 26,
    borderRadius: 999,
    justifyContent: 'center',
    alignItems: 'center',
  },
  colabTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#16132A',
    marginBottom: 4,
    letterSpacing: -0.2,
  },
  colabSubtitle: {
    fontSize: 12.5,
    lineHeight: 18,
    color: '#6B6480',
  },

  // Progress Stats
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 14,
    marginBottom: 20,
  },
  statCard: {
    width: '47%',
    flexGrow: 1,
    alignItems: 'center',
    padding: 18,
    backgroundColor: '#FFFFFF',
    borderRadius: 22,
    borderWidth: 1,
    borderColor: '#EDE1F5',
    ...cardShadow,
  },
  statNumber: {
    fontSize: 28,
    fontWeight: '800',
    color: '#16132A',
    marginTop: 8,
    letterSpacing: -0.4,
  },
  statLabel: {
    fontSize: 14,
    fontWeight: '700',
    color: '#16132A',
    marginTop: 4,
  },
  statSubtext: {
    fontSize: 12,
    color: '#6B6480',
    marginTop: 2,
  },

  // Decision Modes Card
  modesCard: {
    marginBottom: 20,
    backgroundColor: '#FFFFFF',
    borderRadius: 22,
    padding: 20,
    borderWidth: 1,
    borderColor: '#EDE1F5',
    ...cardShadow,
  },
  modeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#F3ECF8',
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
    fontSize: 15,
    fontWeight: '700',
    color: '#16132A',
  },
  modeDesc: {
    fontSize: 12.5,
    color: '#6B6480',
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
    fontWeight: '700',
    color: COLORS.primary,
  },

  // Report Quota card
  quotaCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#EDE1F5',
    ...cardShadow,
  },
  quotaHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  quotaHeaderTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#16132A',
  },
  quotaBuyBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: COLORS.primary,
    paddingHorizontal: 12,
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
    color: '#9C93B3',
    paddingVertical: 8,
  },
  quotaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 9,
    borderTopWidth: 1,
    borderTopColor: '#F3ECF8',
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
    color: '#5B5470',
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
    color: '#16132A',
  },
  quotaMetricLabel: {
    fontSize: 9,
    fontWeight: '600',
    color: '#9C93B3',
    textTransform: 'uppercase',
    marginTop: 1,
  },
});
