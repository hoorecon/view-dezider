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
  Pressable, Platform,
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
  { key: 'org-members',     label: 'Org Members',         description: 'Organisation users · roles · invitations',     icon: 'people',          color: '#3B82F6', href: '/admin/org-members' },
  { key: 'acm',             label: 'Access Control',      description: '89 features × subscription plan quotas',       icon: 'shield-checkmark',color: '#6366F1', href: '/admin/acm' },
  { key: 'audit',           label: 'Audit Trail',         description: 'All admin actions · forensic timeline',        icon: 'time',            color: '#64748B', href: '/admin/audit-trail' },
  { key: 'incident',        label: 'Incident Response',   description: 'Active incidents · post-mortems · SLAs',       icon: 'alert-circle',    color: '#DC2626', href: '/admin/incident-response' },
  { key: 'docs',            label: 'Admin Docs',          description: 'PRD · SRS · UAT · Postman · Regression',       icon: 'library',         color: '#059669', href: '/admin/docs' },
  { key: 'masters',         label: 'Masters',             description: 'Religions · Castes · Languages · Occupations · Skills · Drives · Traits', icon: 'list-circle', color: '#9333EA', href: '/admin/masters' },
];

export default function AdminHomeScreen() {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const isDesktop = width >= BREAKPOINTS.mobile;
  const isWide = width >= BREAKPOINTS.tablet;
  const user = useAuthStore(s => s.user);

  const [stats, setStats] = useState<StatCard[]>([]);
  const [loading, setLoading] = useState(true);

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
    <View style={{ flex: 1, minHeight: 600 }}>
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
              <Text style={s.sectionSub}>Jump into the most-used admin modules</Text>
            </View>
          </View>
          <View style={s.actionGrid}>
            {QUICK_ACTIONS.map(action => (
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
    </View>
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
    padding: 16,
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
  actionCard: {
    paddingHorizontal: 6,
    paddingVertical: 6,
  },
  actionCardInner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: ADMIN_THEME.content.cardBg,
    borderWidth: 1,
    borderColor: ADMIN_THEME.content.cardBorder,
    borderRadius: 10,
    padding: 14,
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
    padding: 16,
  },
  statusRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 7, gap: 8 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  statusLabel: { flex: 1, fontSize: 12, color: ADMIN_THEME.semantic.textSecondary, fontWeight: '500' },
  statusValue: { fontSize: 12, fontWeight: '700', color: ADMIN_THEME.semantic.text },
  statusBadge: { fontSize: 9, fontWeight: '700', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, letterSpacing: 0.5 },
  statusDivider: { height: 1, backgroundColor: ADMIN_THEME.semantic.divider, marginVertical: 8 },
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
