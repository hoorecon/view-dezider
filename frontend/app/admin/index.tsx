/**
 * /admin (index) — Admin Console home dashboard.
 *
 * Web-first design inspired by Tata Neu (super-app shell), Groww (clarity),
 * Practo (decision rails). Multi-column grid, info-dense stat cards,
 * recent-activity feed, system status panel.
 */
import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ActivityIndicator, useWindowDimensions,
  Pressable, Platform, ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../src/utils/api';
import { ADMIN_THEME, BREAKPOINTS } from '../../src/constants/adminTheme';
import { useAuthStore } from '../../src/store/authStore';

interface StatCard {
  key: string; label: string; value: string | number; trend?: string;
  icon: string; color: string; href?: string; subtitle?: string;
}

interface QuickAction {
  key: string; label: string; description: string; icon: string;
  color: string; href: string;
}

const QUICK_ACTIONS: QuickAction[] = [
  { key: 'tier-matrix',     label: 'Tier Matrix',         description: '32 modules × 7 chakra tiers · feature gating', icon: 'apps',            color: '#7C3AED', href: '/admin/tier-matrix' },
  { key: 'segments',        label: 'Customer Segments',   description: 'Target Group profiles · multi-currency pricing · AI research', icon: 'people-circle',   color: '#0EA5E9', href: '/admin/customer-segments' },
  { key: 'pricing',         label: 'Pricing Page',        description: 'Public-facing 7-chakra subscription tiers',   icon: 'pricetag',        color: '#10B981', href: '/pricing' },
  { key: 'payments',        label: 'Payments & Coupons',  description: 'Skip-pay toggle · Coupon CRUD · Org-Type master', icon: 'card', color: '#0D9488', href: '/admin/payments' },
  { key: 'experts',         label: 'Experts',             description: 'Verified expert profiles · ratings · payouts', icon: 'star',            color: '#F59E0B', href: '/admin/experts' },
  { key: 'platform-experts', label: 'Platform Experts',   description: 'Vetted directory · Expert Type · Languages · Experience · Fees/min · multi-Org · catalog-linked · bulk upload', icon: 'ribbon', color: '#D946EF', href: '/admin/platform-experts' },
  { key: 'payouts',          label: 'Payouts',             description: 'Marketplace earnings · weekly auto-payout config · RazorpayX', icon: 'cash', color: '#16A34A', href: '/admin/payouts' },
  { key: 'karma',            label: 'Karma Config',        description: 'Points per collaborative event · ratings · fame', icon: 'trophy', color: '#F59E0B', href: '/admin/karma' },
  { key: 'org-members',     label: 'Org Members',         description: 'Organisation users · roles · invitations',     icon: 'people',          color: '#3B82F6', href: '/admin/org-members' },
  { key: 'embed-partners',  label: 'Partner Embed',       description: 'White-label embed · branding · render mode · Screener pricing · snippet · analytics', icon: 'extension-puzzle', color: '#7B1E3B', href: '/admin/embed-partners' },
  { key: 'acm',             label: 'Access Control',      description: '89 features × subscription plan quotas',       icon: 'shield-checkmark',color: '#6366F1', href: '/admin/acm' },
  { key: 'audit',           label: 'Audit Trail',         description: 'All admin actions · forensic timeline',        icon: 'time',            color: '#64748B', href: '/admin/audit-trail' },
  { key: 'incident',        label: 'Incident Response',   description: 'Active incidents · post-mortems · SLAs',       icon: 'alert-circle',    color: '#DC2626', href: '/admin/incident-response' },
  { key: 'docs',            label: 'Admin Docs',          description: 'PRD · SRS · UAT · Postman · Regression',       icon: 'library',         color: '#059669', href: '/admin/docs' },
  { key: 'handbook',        label: 'Handbook & System KT', description: 'Block diagram · flow charts · PRD/SRS/API/Security/Deployment (markdown)', icon: 'git-network',    color: '#0EA5E9', href: '/admin/handbook' },
  { key: 'masters',         label: 'Masters',             description: 'Org Types · Religions · Castes · Languages · Occupations · Skills · Drives · Traits', icon: 'list-circle', color: '#9333EA', href: '/admin/masters' },
  { key: 'scenarios',       label: 'Intake Scenarios',    description: 'Org-type-aware scenario suggestions on the decision intake (e.g. Family-only)', icon: 'bulb', color: '#0EA5E9', href: '/admin/scenarios' },
  { key: 'appearance',      label: 'Appearance · Font',   description: 'App-wide font family · Inter default · live preview', icon: 'text', color: '#EC4899', href: '/admin/appearance' },
  { key: 'user-lookup',     label: 'User Lookup (PII)',   description: 'Read-only user view by email + WhatsApp · NDA + audit logged', icon: 'shield-checkmark', color: '#0891B2', href: '/admin/user-lookup' },
  { key: 'catalog',         label: 'Central Catalog',     description: 'Explorer tree · LifeArea→OrgType→PNRAG→Scenario→Templates/Store · inline CRUD', icon: 'git-network', color: '#7C3AED', href: '/admin/catalog' },
  { key: 'quota-editor',    label: 'Edit Report Allocation', description: 'Correct a user\'s remaining report quota · OTP-authorized · audited', icon: 'create', color: '#059669', href: '/admin/quota-editor' },
  { key: 'ai-wallet-cfg',   label: 'AI Wallet Config',    description: 'Markup % · Route split (markup_routed_pct) · seeds · FX · live ₹ break-even preview', icon: 'wallet', color: '#7C3AED', href: '/admin/ai-wallet-config' },
  { key: 'recon',           label: 'Revenue Recon',       description: 'Razorpay ⟷ AI-Wallet ⟷ Google Cloud · per-txn zero-loss tally', icon: 'analytics', color: '#0EA5E9', href: '/admin/recon' },
  { key: 'import-analytics', label: 'Import-URL Intelligence', description: 'Per-page-type accuracy, hints, prompts & 👍/👎 verdicts · learning loop', icon: 'pulse', color: '#7C3AED', href: '/admin/import-analytics' },
  { key: 'url-training', label: 'URL Training Console', description: 'Curate ground-truth URLs · pin up to 15 as weekly regression suite · run any anytime · grade vs expectations', icon: 'school', color: '#D97706', href: '/admin/url-training' },
  { key: 'notification-engine', label: 'Notification Engine', description: 'CRUD trigger events · weekly digests & instant alerts · Email + WhatsApp toggles', icon: 'notifications', color: '#D97706', href: '/admin/notification-engine' },
  { key: 'values',          label: 'Values Tracker',      description: '8 VEALES Collaboration Principles + org-custom add-ons · AI alignment threshold', icon: 'shield-checkmark', color: '#0EA5E9', href: '/admin/values' },
  { key: 'seven-seven',     label: '7×7 Org Matrix',      description: '7 Divisions (Chakras) × 7 Drivers (Team/Systems/Strategy) · master seed + custom', icon: 'grid', color: '#8B5CF6', href: '/admin/seven-seven' },
  { key: 'referral',        label: 'Referral Bonus Designer', description: 'L1/L2/L3 commissions · Karma rate · Coupons · AI auto-split · ALOS', icon: 'gift', color: '#EC4899', href: '/admin/referral' },
  { key: 'acm-resolver-cfg', label: 'ACM Resolver Config',  description: '5-axis user-type resolver · trial days · plan aliases · on-demand thresholds', icon: 'options', color: '#5B7CFA', href: '/admin/acm-resolver-config' },
  { key: 'tier-segments',   label: 'Tier ↔ Segments',       description: 'Map customer segments to each chakra tier · multi-select', icon: 'link', color: '#0EA5E9', href: '/admin/tier-segment-mapping' },
  { key: 'trial-payments',  label: 'Trial Payment Tokens',  description: 'Saved cards/UPI captured at trial opt-in · audit + filter', icon: 'card-outline', color: '#F59E0B', href: '/admin/trial-payments' },
  { key: 'content-library', label: 'Content Library CMS',    description: 'Paste/edit verbatim coaching scripts · multi-locale · tenses_feels + 6 modules', icon: 'document-text', color: '#10B981', href: '/admin/content-library' },
  { key: 'collab-auth', label: 'Collaboration Verification', description: 'Advanced ID methods vs WhatsApp / Email OTP for group-decision participants', icon: 'shield-checkmark', color: '#7C3AED', href: '/admin/collab-auth' },
  { key: 'manifestation-content', label: 'Manifestation Content', description: 'Edit CAB-FAME 7-stage mantras, affirmations & YouTube/resource URLs (all users)', icon: 'sparkles', color: '#8B5CF6', href: '/admin/manifestation-content' },
  { key: 'signup-gate', label: 'Signup & WhatsApp Gate', description: 'Toggle the post-login WhatsApp verification gate for all users (opens Settings)', icon: 'shield-half', color: '#0EA5E9', href: '/admin/settings' },
  { key: 'dashboard-layout', label: 'Dashboard Sections', description: 'Rename section titles · drag to reorder sections · move modules between sections · auto-numbered', icon: 'grid', color: '#0D9488', href: '/admin/dashboard-layout' },
  { key: 'subscription-plans', label: 'Subscription Plans', description: 'Plan credits/month · Active toggle · Sync live pricing & plan IDs from Razorpay', icon: 'diamond', color: '#7C3AED', href: '/admin/subscription-plans' },
  { key: 'razorpay-offers', label: 'Razorpay Offers', description: 'Sync live Payment & Subscription offers from Razorpay · toggle apply-flows · auto-attach at checkout', icon: 'pricetag', color: '#DC2626', href: '/admin/razorpay-offers' },
  { key: 'decider-store', label: 'The Decider Store', description: 'Author & authorize public Decision Templates · import 55×10 grids from Excel/Google Sheet · pricing & clone modes', icon: 'storefront', color: '#4F46E5', href: '/admin/decider-store' },
  { key: 'ad-programs', label: 'AdMaker & AdTaker', description: 'Sponsored Solutions auction (AdRank × GSP) · region/time-slot bids · publisher widgets · tracker IDs · cutoffs', icon: 'megaphone', color: '#B45309', href: '/admin/ad-programs' },
];

// Meaningful grouping of the 32 admin modules into 6 collapsible sections.
// 'Essentials' is expanded by default; all others start collapsed.
const ACTION_GROUPS: { key: string; label: string; icon: string; keys: string[] }[] = [
  { key: 'essentials',     label: 'Essentials',                icon: 'star',          keys: ['acm', 'dashboard-layout', 'signup-gate', 'tier-matrix', 'pricing', 'appearance', 'masters', 'user-lookup'] },
  { key: 'monetization',   label: 'Monetization & Billing',    icon: 'cash',          keys: ['subscription-plans', 'razorpay-offers', 'payments', 'payouts', 'ai-wallet-cfg', 'recon', 'trial-payments', 'quota-editor', 'referral', 'karma', 'ad-programs'] },
  { key: 'plans',          label: 'Plans, Tiers & Segments',   icon: 'apps',          keys: ['segments', 'tier-segments', 'acm-resolver-cfg', 'seven-seven', 'values', 'collab-auth'] },
  { key: 'people',         label: 'People & Experts',          icon: 'people',        keys: ['org-members', 'experts', 'platform-experts', 'embed-partners'] },
  { key: 'content',        label: 'Content & Intelligence',    icon: 'sparkles',      keys: ['catalog', 'decider-store', 'content-library', 'manifestation-content', 'scenarios', 'import-analytics', 'url-training', 'notification-engine'] },
  { key: 'ops',            label: 'Operations & Docs',         icon: 'construct',     keys: ['audit', 'incident', 'docs', 'handbook'] },
];

export default function AdminHomeScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isDesktop = width >= BREAKPOINTS.mobile;
  const isWide = width >= BREAKPOINTS.tablet;
  const user = useAuthStore(s => s.user);

  const [stats, setStats] = useState<StatCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [wa, setWa] = useState<{ loading: boolean; connected: boolean; status: string; detail: string; configured: boolean }>(
    { loading: true, connected: false, status: 'checking', detail: '', configured: true },
  );
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({ essentials: true });
  const actionByKey = React.useMemo(
    () => Object.fromEntries(QUICK_ACTIONS.map((a) => [a.key, a])) as Record<string, QuickAction>,
    [],
  );

  const checkWhatsApp = React.useCallback(async () => {
    setWa((w) => ({ ...w, loading: true }));
    try {
      const r = await api.get('/shares/admin/ultramsg-status');
      setWa({
        loading: false,
        connected: !!r.data?.connected,
        configured: r.data?.configured !== false,
        status: r.data?.status || 'unknown',
        detail: r.data?.detail || '',
      });
    } catch (e: any) {
      setWa({ loading: false, connected: false, configured: true, status: 'error', detail: e?.response?.data?.detail || 'Could not reach status endpoint.' });
    }
  }, []);

  useEffect(() => { checkWhatsApp(); }, [checkWhatsApp]);

  useEffect(() => {
    (async () => {
      try {
        const [tierMatrix, segments, acm, pricing] = await Promise.all([
          api.get('/admin/tier-matrix').catch(() => ({ data: { cells: [], modules: [] } })),
          api.get('/admin/customer-segments').catch(() => ({ data: { segments: [] } })),
          api.get('/acm/health').catch(() => ({ data: {} })),
          api.get('/pricing').catch(() => ({ data: { tiers: [], matrix_rows: [] } })),
        ]);

        const tmCells = tierMatrix.data?.cells?.length || 0;
        const tmModules = tierMatrix.data?.modules?.length || pricing.data?.matrix_rows?.length || 0;
        const segCount = segments.data?.segments?.length || 0;
        const acmFeatures = acm.data?.features_loaded || 89;
        const tierCount = pricing.data?.tiers?.length || 7;

        setStats([
          { key: 'tiers',    label: 'Subscription Tiers',  value: tierCount,           icon: 'apps',           color: '#7C3AED', href: '/admin/tier-matrix',     subtitle: `${tmModules} modules · ${tmCells} cells` },
          { key: 'segments', label: 'Customer Segments',   value: segCount,            icon: 'people-circle',  color: '#0EA5E9', href: '/admin/customer-segments', subtitle: `${segCount === 0 ? 'No' : segCount} TG profile${segCount === 1 ? '' : 's'} · ready to map` },
          { key: 'features', label: 'ACM Features',        value: acmFeatures,         icon: 'shield-checkmark', color: '#6366F1', href: '/admin/acm',             subtitle: '32 modules · gated by tier × plan' },
          { key: 'modules',  label: 'Active Modules',      value: tmModules,           icon: 'cube',           color: '#10B981', href: '/admin/tier-matrix',     subtitle: 'Production-ready · v3.14.0' },
        ]);
      } finally { setLoading(false); }
    })();
  }, []);

  const cols = isWide ? 4 : isDesktop ? 2 : 1;
  const cardWidth = `${100 / cols}%` as any;

  return (
    <ScrollView
      style={{ flex: 1 }}
      contentContainerStyle={{ paddingHorizontal: 24, paddingTop: 20, paddingBottom: 40 }}
      showsVerticalScrollIndicator
    >
      {/* Greeting */}
      <View style={s.greetingBlock}>
        <Text style={s.greeting}>Welcome back, {user?.name?.split(' ')[0] || 'Admin'} 👋</Text>
        <Text style={s.greetingSub}>Here's what's happening across the platform today.</Text>
      </View>

      {/* Stat cards */}
      <View style={s.statsRow}>
        {loading ? (
          <View style={s.loadingBox}><ActivityIndicator color={ADMIN_THEME.semantic.primary} /></View>
        ) : (
          stats.map(stat => (
            <Pressable
              key={stat.key}
              onPress={() => stat.href && router.push(stat.href as any)}
              style={({ hovered }: any) => [
                s.statCard,
                { width: cardWidth },
                hovered && s.statCardHover,
              ]}
              testID={`admin-stat-${stat.key}`}
            >
              <View style={s.statCardInner}>
                <View style={s.statHeader}>
                  <View style={[s.statIconWrap, { backgroundColor: stat.color + '15' }]}>
                    <Ionicons name={stat.icon as any} size={16} color={stat.color} />
                  </View>
                  <Text style={s.statLabel}>{stat.label}</Text>
                </View>
                <Text style={s.statValue}>{stat.value}</Text>
                {stat.subtitle && <Text style={s.statSubtitle}>{stat.subtitle}</Text>}
              </View>
            </Pressable>
          ))
        )}
      </View>

      {/* Two-column layout: quick actions + system status */}
      <View style={[s.twoCol, !isWide && { flexDirection: 'column' }]}>
        {/* Quick actions grid */}
        <View style={[s.colMain, !isWide && { width: '100%' }]}>
          <View style={s.sectionHeader}>
            <View>
              <Text style={s.sectionTitle}>Operations</Text>
              <Text style={s.sectionSub}>Browse admin modules by category</Text>
            </View>
          </View>
          {ACTION_GROUPS.map((group) => {
            const open = !!openGroups[group.key];
            const groupActions = group.keys.map((k) => actionByKey[k]).filter(Boolean);
            return (
              <View key={group.key} style={s.groupBlock}>
                <TouchableOpacity
                  style={s.groupHeader}
                  activeOpacity={0.7}
                  onPress={() => setOpenGroups((g) => ({ ...g, [group.key]: !g[group.key] }))}
                  testID={`admin-group-${group.key}`}
                >
                  <View style={[s.groupIcon, { backgroundColor: ADMIN_THEME.semantic.primarySoft }]}>
                    <Ionicons name={group.icon as any} size={15} color={ADMIN_THEME.semantic.primary} />
                  </View>
                  <Text style={s.groupLabel}>{group.label}</Text>
                  <Text style={s.groupCount}>{groupActions.length}</Text>
                  <Ionicons
                    name={open ? 'chevron-up' : 'chevron-down'}
                    size={16}
                    color={ADMIN_THEME.semantic.textMuted}
                  />
                </TouchableOpacity>
                {open && (
                  <View style={s.actionGrid}>
                    {groupActions.map((action) => (
                      <Pressable
                        key={action.key}
                        onPress={() => router.push(action.href as any)}
                        style={({ hovered }: any) => [
                          s.actionCard,
                          { width: isWide ? '33.333%' : isDesktop ? '50%' : '100%' },
                          hovered && s.actionCardHover,
                        ]}
                        testID={`admin-action-${action.key}`}
                      >
                        <View style={s.actionCardInner}>
                          <View style={[s.actionIcon, { backgroundColor: action.color + '15' }]}>
                            <Ionicons name={action.icon as any} size={18} color={action.color} />
                          </View>
                          <View style={{ flex: 1, minWidth: 0 }}>
                            <Text style={s.actionLabel}>{action.label}</Text>
                            <Text style={s.actionDesc} numberOfLines={2}>{action.description}</Text>
                          </View>
                          <Ionicons name="arrow-forward" size={14} color={ADMIN_THEME.semantic.textMuted} style={{ marginLeft: 6 }} />
                        </View>
                      </Pressable>
                    ))}
                  </View>
                )}
              </View>
            );
          })}
        </View>

        {/* System status side panel */}
        <View style={[s.colSide, !isWide && { width: '100%', marginLeft: 0, marginTop: ADMIN_THEME.content.gap }]}>
          <View style={s.statusCard}>
            <View style={s.sectionHeader}>
              <Text style={s.sectionTitle}>System Status</Text>
            </View>
            <View style={s.statusRow}>
              <View style={[s.statusDot, { backgroundColor: ADMIN_THEME.semantic.success }]} />
              <Text style={s.statusLabel}>API · Backend</Text>
              <Text style={[s.statusBadge, { backgroundColor: ADMIN_THEME.semantic.successSoft, color: ADMIN_THEME.semantic.success }]}>OK</Text>
            </View>
            <View style={s.statusRow}>
              <View style={[s.statusDot, { backgroundColor: ADMIN_THEME.semantic.success }]} />
              <Text style={s.statusLabel}>MongoDB</Text>
              <Text style={[s.statusBadge, { backgroundColor: ADMIN_THEME.semantic.successSoft, color: ADMIN_THEME.semantic.success }]}>OK</Text>
            </View>
            <View style={s.statusRow}>
              <View style={[s.statusDot, { backgroundColor: ADMIN_THEME.semantic.warn }]} />
              <Text style={s.statusLabel}>LLM (AI Research)</Text>
              <Text style={[s.statusBadge, { backgroundColor: ADMIN_THEME.semantic.warnSoft, color: ADMIN_THEME.semantic.warn }]}>BUDGET</Text>
            </View>
            <View style={s.statusRow}>
              <View style={[s.statusDot, { backgroundColor: ADMIN_THEME.semantic.success }]} />
              <Text style={s.statusLabel}>/api/pricing cache</Text>
              <Text style={[s.statusBadge, { backgroundColor: ADMIN_THEME.semantic.successSoft, color: ADMIN_THEME.semantic.success }]}>WARM</Text>
            </View>
            <View style={s.statusRow}>
              <View style={[s.statusDot, {
                backgroundColor: wa.loading
                  ? ADMIN_THEME.semantic.textMuted
                  : wa.connected ? ADMIN_THEME.semantic.success : ADMIN_THEME.semantic.danger,
              }]} />
              <Text style={s.statusLabel}>WhatsApp · UltraMsg</Text>
              <TouchableOpacity onPress={checkWhatsApp} accessibilityLabel="Re-check WhatsApp status" style={{ marginRight: 6 }}>
                <Ionicons name="refresh" size={13} color={ADMIN_THEME.semantic.textMuted} />
              </TouchableOpacity>
              {wa.loading ? (
                <ActivityIndicator size="small" color={ADMIN_THEME.semantic.textMuted} />
              ) : (
                <Text style={[s.statusBadge, wa.connected
                  ? { backgroundColor: ADMIN_THEME.semantic.successSoft, color: ADMIN_THEME.semantic.success }
                  : { backgroundColor: ADMIN_THEME.semantic.dangerSoft, color: ADMIN_THEME.semantic.danger }]}>
                  {wa.connected ? 'CONNECTED' : !wa.configured ? 'NOT SET' : 'DISCONNECTED'}
                </Text>
              )}
            </View>
            {!wa.loading && !wa.connected && !!wa.detail && (
              <Text style={s.waDetail}>{wa.detail}</Text>
            )}
            <View style={s.statusDivider} />
            <View style={s.statusRow}>
              <Text style={s.statusLabel}>Edition</Text>
              <View style={s.editionPill}>
                <Ionicons name="checkmark-circle" size={11} color={ADMIN_THEME.semantic.primary} />
                <Text style={s.editionText}>JELCOS AI</Text>
              </View>
            </View>
            <View style={s.statusRow}>
              <Text style={s.statusLabel}>Master brand</Text>
              <Text style={s.statusValue}>Earth Dezider</Text>
            </View>
            <View style={s.statusRow}>
              <Text style={s.statusLabel}>Build</Text>
              <Text style={s.statusValue}>v3.14.0</Text>
            </View>
          </View>

          {/* Quick info card */}
          <View style={[s.statusCard, { marginTop: ADMIN_THEME.content.gap, backgroundColor: ADMIN_THEME.semantic.primarySoft, borderColor: ADMIN_THEME.semantic.primary + '33' }]}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <Ionicons name="rocket" size={16} color={ADMIN_THEME.semantic.primary} />
              <Text style={[s.sectionTitle, { color: ADMIN_THEME.semantic.primary }]}>What's new</Text>
            </View>
            <Text style={s.newsItem}>• Customer Segments TG master with AI factor research</Text>
            <Text style={s.newsItem}>• Public Pricing page with 8-currency multi-country support</Text>
            <Text style={s.newsItem}>• Tier Matrix smart cascade rules</Text>
            <Text style={s.newsItem}>• Postman collection regenerated · 701 endpoints</Text>
          </View>
        </View>
      </View>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  greetingBlock: { marginBottom: ADMIN_THEME.content.gap },
  greeting: { fontSize: 24, fontWeight: '800', color: ADMIN_THEME.semantic.text, letterSpacing: -0.3 },
  greetingSub: { fontSize: 14, color: ADMIN_THEME.semantic.textSecondary, marginTop: 4 },

  statsRow: { flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -8, marginBottom: ADMIN_THEME.content.gap },
  loadingBox: { width: '100%', padding: 40, alignItems: 'center' },
  statCard: {
    paddingHorizontal: 8,
    paddingVertical: 8,
  },
  statCardInner: {
    backgroundColor: ADMIN_THEME.content.cardBg,
    borderWidth: 1,
    borderColor: ADMIN_THEME.content.cardBorder,
    borderRadius: 10,
    paddingVertical: 16,
    paddingHorizontal: 20,
  },
  statCardHover: { transform: [{ translateY: -2 }] as any },
  statHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  statIconWrap: { width: 28, height: 28, borderRadius: 7, alignItems: 'center', justifyContent: 'center' },
  statLabel: { fontSize: 11, fontWeight: '700', color: ADMIN_THEME.semantic.textMuted, textTransform: 'uppercase', letterSpacing: 0.5 },
  statValue: { fontSize: 28, fontWeight: '800', color: ADMIN_THEME.semantic.text, letterSpacing: -0.5 },
  statSubtitle: { fontSize: 11, color: ADMIN_THEME.semantic.textMuted, marginTop: 4 },

  twoCol: { flexDirection: 'row', gap: ADMIN_THEME.content.gap },
  colMain: { flex: 1, minWidth: 0 },
  colSide: { width: 320 },

  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: ADMIN_THEME.semantic.text },
  sectionSub: { fontSize: 12, color: ADMIN_THEME.semantic.textMuted, marginTop: 2 },

  actionGrid: { flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -6 },
  groupBlock: { marginBottom: 12 },
  groupHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: ADMIN_THEME.content.cardBg,
    borderWidth: 1, borderColor: ADMIN_THEME.content.cardBorder,
    borderRadius: 10, paddingVertical: 12, paddingHorizontal: 16,
  },
  groupIcon: { width: 28, height: 28, borderRadius: 7, alignItems: 'center', justifyContent: 'center' },
  groupLabel: { flex: 1, fontSize: 14, fontWeight: '700', color: ADMIN_THEME.semantic.text },
  groupCount: {
    fontSize: 11, fontWeight: '700', color: ADMIN_THEME.semantic.textMuted,
    backgroundColor: ADMIN_THEME.semantic.divider, paddingHorizontal: 8, paddingVertical: 2,
    borderRadius: 10, overflow: 'hidden', marginRight: 4,
  },
  actionCard: {
    paddingHorizontal: 6,
    paddingVertical: 6,
  },
  actionCardInner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    backgroundColor: ADMIN_THEME.content.cardBg,
    borderWidth: 1,
    borderColor: ADMIN_THEME.content.cardBorder,
    borderRadius: 10,
    paddingVertical: 14,
    paddingHorizontal: 18,
    minHeight: 84,
  },
  actionCardHover: { transform: [{ translateY: -1 }] as any },
  actionIcon: { width: 36, height: 36, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  actionLabel: { fontSize: 14, fontWeight: '700', color: ADMIN_THEME.semantic.text },
  actionDesc: { fontSize: 11, color: ADMIN_THEME.semantic.textMuted, marginTop: 2, lineHeight: 16 },

  statusCard: {
    backgroundColor: ADMIN_THEME.content.cardBg,
    borderWidth: 1,
    borderColor: ADMIN_THEME.content.cardBorder,
    borderRadius: 10,
    paddingVertical: 16,
    paddingHorizontal: 20,
  },
  statusRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 7, gap: 8 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  statusLabel: { flex: 1, fontSize: 12, color: ADMIN_THEME.semantic.textSecondary, fontWeight: '500' },
  statusValue: { fontSize: 12, fontWeight: '700', color: ADMIN_THEME.semantic.text },
  statusBadge: { fontSize: 9, fontWeight: '700', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, letterSpacing: 0.5 },
  statusDivider: { height: 1, backgroundColor: ADMIN_THEME.semantic.divider, marginVertical: 8 },
  waDetail: { fontSize: 11, color: ADMIN_THEME.semantic.danger, lineHeight: 16, marginTop: -2, marginBottom: 4, paddingLeft: 16 },
  editionPill: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: ADMIN_THEME.semantic.primarySoft, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  editionText: { fontSize: 10, fontWeight: '700', color: ADMIN_THEME.semantic.primary, letterSpacing: 0.4 },
  newsItem: { fontSize: 12, color: ADMIN_THEME.semantic.textSecondary, lineHeight: 20, marginBottom: 2 },
});

// Apply card surface styles via a dedicated wrapper for hover support on web.
// (RN doesn't support hover natively but Pressable on web does via the
//  pressable-feedback prop signature we used above.)

// Inject web-only styles for hover/transition into the document head once.
if (Platform.OS === 'web' && typeof document !== 'undefined') {
  const id = '__admin_hover_styles__';
  if (!document.getElementById(id)) {
    const style = document.createElement('style');
    style.id = id;
    style.innerHTML = `
      [data-admin-card] { transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease; cursor: pointer; }
      [data-admin-card]:hover { box-shadow: 0 4px 12px rgba(15,23,42,0.08), 0 2px 4px rgba(15,23,42,0.04); transform: translateY(-1px); border-color: #CBD5E1; }
    `;
    document.head.appendChild(style);
  }
}
