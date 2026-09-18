/**
 * <PaywallGate> — drop-in entitlement gate for the 3 decision modules.
 *
 * Usage:
 *   <PaywallGate module="dezider" onAllowed={openCreate}>
 *     <TouchableOpacity onPress={open}><Text>New Decision</Text></TouchableOpacity>
 *   </PaywallGate>
 *
 * Behaviour:
 *  - On mount, calls /store/access-check and caches result for 60s.
 *  - If user has access → renders children, intercepts onPress to log + run.
 *  - If user has no access → renders children dimmed; press opens an in-app
 *    bottom-sheet modal explaining options and deep-linking to /store.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Dimensions, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, TouchableOpacity, View, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../utils/api';

import { showAlert } from '../utils/alert';

export type DecisionModule = 'dezider' | 'pros_cons' | 'swot' | 'solution_finder' | 'conflict_breaker' | 'conflict-breaker';

interface Props {
  module: DecisionModule;
  children: React.ReactElement;
  onAllowed?: () => void;
}

interface AccessState {
  has_access: boolean;
  access_level?: 'full' | 'read' | 'locked' | 'hidden' | 'quota_exceeded';
  acm_restricted?: boolean;
  message?: string;
  via?: string | null;
  tier?: string;
  balance?: number;
  loading: boolean;
}

const MODULE_LABEL: Record<string, string> = {
  dezider: 'My Dezider',
  pros_cons: 'Pros & Cons',
  swot: 'SWOT Analysis',
  solution_finder: 'Solution Finder',
  conflict_breaker: 'The Conflict Breaker',
  'conflict-breaker': 'The Conflict Breaker',
};

export default function PaywallGate({ module, children, onAllowed }: Props) {
  const router = useRouter();
  const [state, setState] = useState<AccessState>({ has_access: true, loading: true });
  const [showSheet, setShowSheet] = useState(false);
  // Centered card on wider viewports (web / tablet); native bottom-sheet on
  // narrow phone screens. Refreshes on resize so the modal stays appropriate.
  const [isWide, setIsWide] = useState(() => Dimensions.get('window').width >= 640);
  useEffect(() => {
    const sub = Dimensions.addEventListener('change', ({ window }) => {
      setIsWide(window.width >= 640);
    });
    return () => sub.remove();
  }, []);

  const refresh = useCallback(async () => {
    try {
      const res = await api.get('/store/access-check', { params: { module } });
      setState({
        has_access: !!res.data?.has_access,
        access_level: res.data?.access_level || (res.data?.has_access ? 'full' : 'locked'),
        acm_restricted: !!res.data?.acm_restricted,
        message: res.data?.message,
        via: res.data?.via,
        tier: res.data?.tier,
        balance: res.data?.balance,
        loading: false,
      });
    } catch (e: any) {
      // SECURITY: on 401/403 we must NOT bail to has_access=true — that would
      // silently bypass the paywall for any auth blip. Only treat 5xx / network
      // errors as fail-open (matches the original intent of "don't block
      // creators when the backend is down").
      const status = e?.response?.status;
      const failOpen = !status || status >= 500;
      setState({ has_access: failOpen, access_level: failOpen ? 'full' : 'locked', loading: false });
    }
  }, [module]);

  useEffect(() => { refresh(); }, [refresh]);

  // Live pricing for the unlock sheet — fetched from the SAME catalog the Store
  // uses (/store/skus) plus subscription plans, so Admin price edits reflect
  // here too. Loaded lazily the first time the sheet opens; falls back to the
  // default copy if the request fails.
  const money = (paise?: number) => '₹' + Math.round((paise || 0) / 100).toLocaleString('en-IN');
  const [pricing, setPricing] = useState<{ l1?: string; l2?: string; l3?: string; l4?: string }>({});
  useEffect(() => {
    if (!showSheet || pricing.l1) return;
    let cancelled = false;
    (async () => {
      try {
        const skuRes = await api.get('/store/skus');
        const byCode: Record<string, any> = {};
        (skuRes.data?.skus || []).forEach((s: any) => { byCode[s.code] = s; });
        const l1 = byCode['L1'];
        const l2 = byCode['L2'];
        const l3 = byCode['L3'];
        const l4 = byCode['L4'];
        if (cancelled) return;
        setPricing({
          l1: l1 ? `${money(l1.price_paise)} · 1 decision + PDF report` : undefined,
          l2: l2 ? `${money(l2.price_paise)} · 5 decisions across modules` : undefined,
          l3: l3 ? `${money(l3.price_paise)} · 1-on-1 expert session` : undefined,
          l4: l4 ? `${money(l4.price_paise)} · written expert analysis` : undefined,
        });
      } catch {
        /* keep fallback copy */
      }
    })();
    return () => { cancelled = true; };
  }, [showSheet, pricing.l1]);

  const handlePress = useCallback(() => {
    if (state.loading) return;
    if (state.has_access) {
      onAllowed?.();
      const cb = (children as any).props?.onPress;
      if (typeof cb === 'function') cb();
      return;
    }

    // Conflict Breaker is plan-restricted (Pro and Premium plans only).
    // Do NOT show On-Demand purchase popup modal! Display "Plan Upgrade Required" alert instead.
    const isConflictBreaker = module === 'conflict_breaker' || module === 'conflict-breaker';
    if (isConflictBreaker) {
      showAlert(
        'Plan Upgrade Required',
        state.message || 'The Conflict Breaker is available on Pro and Premium plans. Upgrade your plan to access this feature.'
      );
      return;
    }

    // If ACM explicitly restricts access (admin set level to 'locked', 'read', or 'hidden' in ACM):
    // DO NOT ASK FOR PAYMENT MODEL! Display status alert instead.
    if (state.acm_restricted) {
      const label = MODULE_LABEL[module] || 'This module';
      const level = state.access_level || 'locked';

      let title = `${label} is Locked`;
      let body = state.message;

      if (level === 'read') {
        title = `${label} is Read-Only`;
        body = body || `${label} is in read-only mode under Access Control Matrix rules.`;
      } else if (level === 'hidden') {
        title = `${label} is Hidden`;
        body = body || `${label} is hidden under Access Control Matrix rules.`;
      } else {
        body = body || `${label} is locked under Access Control Matrix rules.`;
      }

      showAlert(title, body);
      return;
    }

    // Subscription plan users (basic, pro, premium, enterprise):
    // Do NOT show On-Demand purchase popup modal! Display "Limit Reached" alert instead.
    const tierLc = (state.tier || '').toLowerCase();
    const isSubscriptionUser = ['basic', 'pro', 'premium', 'enterprise', 'paid'].includes(tierLc);
    if (isSubscriptionUser) {
      showAlert(
        'Limit Reached',
        state.message || `Your limit has been reached on the ${state.tier || 'current'} plan. Upgrade your plan for higher limits.`
      );
      return;
    }

    // Standard paywall quota check for free / guest / on-demand users: show On-Demand SKU unlock modal
    setShowSheet(true);
  }, [state, onAllowed, children, module]);

  if (!state.loading && state.access_level === 'hidden' && state.acm_restricted) {
    return null;
  }

  // Clone child so we own the onPress (still passing the original via fallthrough)
  const wrapped = React.cloneElement(children, { onPress: handlePress });

  return (
    <>
      {wrapped}
      <Modal visible={showSheet} transparent animationType="fade" onRequestClose={() => setShowSheet(false)}>
        <Pressable style={[styles.backdrop, isWide && styles.backdropCentered]} onPress={() => setShowSheet(false)}>
          <Pressable style={[styles.sheet, isWide && styles.sheetWide]} onPress={(e) => e.stopPropagation()}>
            {!isWide && <View style={styles.handle} />}
            <View style={styles.lockBadge}>
              <Ionicons name="lock-closed" size={22} color="#7C3AED" />
            </View>
            <Text style={styles.title}>Unlock {MODULE_LABEL[module]}</Text>
            <Text style={styles.body}>
              Choose an On-Demand SKU pack to unlock {MODULE_LABEL[module]}.
            </Text>
            <View style={styles.options}>
              <OptionRow icon="document-text" tone="#3B82F6" title="DIY Decision Report (L1)" desc={pricing.l1 ?? '₹199 · 1 decision + PDF'} onPress={() => { setShowSheet(false); router.push({ pathname: '/store', params: { highlight: 'L1', module } } as any); }} />
              <OptionRow icon="people" tone="#7C3AED" title="5-Decision Bundle (L2)" desc={pricing.l2 ?? '₹999 · 5 decisions across modules'} onPress={() => { setShowSheet(false); router.push({ pathname: '/store', params: { highlight: 'L2', module } } as any); }} />
              <OptionRow icon="videocam" tone="#059669" title="Professional Guided Session (L3)" desc={pricing.l3 ?? '₹1,999 · 1-on-1 Expert Session'} onPress={() => { setShowSheet(false); router.push({ pathname: '/store', params: { highlight: 'L3', module } } as any); }} />
              <OptionRow icon="ribbon" tone="#DC2626" title="Expert Review (L4)" desc={pricing.l4 ?? '₹2,800 · Written Expert Analysis'} onPress={() => { setShowSheet(false); router.push({ pathname: '/store', params: { highlight: 'L4', module } } as any); }} />
            </View>
            <View style={styles.footerRow}>
              <TouchableOpacity style={styles.dismissBtn} onPress={() => setShowSheet(false)}>
                <Text style={styles.dismissText}>Not now</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.viewAll} onPress={() => { setShowSheet(false); router.push({ pathname: '/store', params: { module } } as any); }}>
                <Text style={styles.viewAllText}>See On-Demand Store →</Text>
              </TouchableOpacity>
            </View>
            {state.loading && <ActivityIndicator size="small" style={{ marginTop: 8 }} />}
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

function OptionRow({ icon, tone, title, desc, onPress }: { icon: any; tone: string; title: string; desc: string; onPress: () => void }) {
  return (
    <TouchableOpacity onPress={onPress} style={[styles.option, { borderColor: tone + '55' }]}>
      <View style={[styles.optionIcon, { backgroundColor: tone + '18' }]}>
        <Ionicons name={icon} size={20} color={tone} />
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.optionTitle}>{title}</Text>
        <Text style={styles.optionDesc}>{desc}</Text>
      </View>
      <Ionicons name="chevron-forward" size={18} color="#94A3B8" />
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  // Backdrop centers on wide viewports, sticks to bottom on narrow phones.
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(15, 23, 42, 0.55)',
    justifyContent: 'flex-end',
    alignItems: 'stretch',
    ...Platform.select({ web: { backdropFilter: 'blur(2px)' as any }, default: {} }),
  },
  backdropCentered: { justifyContent: 'center', alignItems: 'center', padding: 16 },
  sheet: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingHorizontal: 22,
    paddingTop: 12,
    paddingBottom: 24,
    alignItems: 'center',
    gap: 4,
  },
  // Elegant centered card on wider screens — replaces edge-to-edge bottom sheet.
  sheetWide: {
    width: '100%',
    maxWidth: 480,
    alignSelf: 'center',
    marginVertical: 'auto' as any,
    marginBottom: 60,
    marginTop: 60,
    borderRadius: 18,
    paddingTop: 24,
    paddingBottom: 22,
    paddingHorizontal: 26,
    shadowColor: '#000',
    shadowOpacity: 0.18,
    shadowOffset: { width: 0, height: 12 },
    shadowRadius: 28,
    elevation: 24,
  },
  handle: { width: 40, height: 4, borderRadius: 2, backgroundColor: '#E5E7EB', marginBottom: 10 },
  lockBadge: {
    width: 52, height: 52, borderRadius: 26,
    backgroundColor: '#F5F3FF', alignItems: 'center', justifyContent: 'center',
    marginBottom: 12,
  },
  title: { fontSize: 19, fontWeight: '700', color: '#0F172A', marginTop: 2 },
  body: { fontSize: 13, color: '#475569', textAlign: 'center', marginTop: 6, marginBottom: 14, lineHeight: 19, maxWidth: 380 },
  options: { width: '100%', gap: 10, marginTop: 2 },
  option: { flexDirection: 'row', alignItems: 'center', borderWidth: 1.5, borderRadius: 14, paddingVertical: 12, paddingHorizontal: 14, gap: 12, backgroundColor: '#FFF' },
  optionIcon: { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center' },
  optionTitle: { fontSize: 14, fontWeight: '600', color: '#0F172A' },
  optionDesc: { fontSize: 12, color: '#64748B', marginTop: 1 },
  footerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', width: '100%', marginTop: 14, paddingHorizontal: 2 },
  dismissBtn: { paddingHorizontal: 14, paddingVertical: 8 },
  dismissText: { color: '#64748B', fontWeight: '600', fontSize: 13 },
  viewAll: { paddingHorizontal: 14, paddingVertical: 8 },
  viewAllText: { color: '#7C3AED', fontWeight: '700', fontSize: 13 },
});
