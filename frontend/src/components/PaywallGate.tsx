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

export type DecisionModule = 'dezider' | 'pros_cons' | 'swot';

interface Props {
  module: DecisionModule;
  children: React.ReactElement;
  onAllowed?: () => void;
}

interface AccessState { has_access: boolean; via?: string | null; balance?: number; loading: boolean; }

const MODULE_LABEL: Record<DecisionModule, string> = {
  dezider: 'My Dezider',
  pros_cons: 'Pros & Cons',
  swot: 'SWOT Analysis',
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
      setState({ has_access: !!res.data?.has_access, via: res.data?.via, balance: res.data?.balance, loading: false });
    } catch (e: any) {
      // SECURITY: on 401/403 we must NOT bail to has_access=true — that would
      // silently bypass the paywall for any auth blip. Only treat 5xx / network
      // errors as fail-open (matches the original intent of "don't block
      // creators when the backend is down").
      const status = e?.response?.status;
      const failOpen = !status || status >= 500;
      setState({ has_access: failOpen, loading: false });
    }
  }, [module]);

  useEffect(() => { refresh(); }, [refresh]);

  // Live pricing for the unlock sheet — fetched from the SAME catalog the Store
  // uses (/store/skus) plus subscription plans, so Admin price edits reflect
  // here too. Loaded lazily the first time the sheet opens; falls back to the
  // default copy if the request fails.
  const money = (paise?: number) => '₹' + Math.round((paise || 0) / 100).toLocaleString('en-IN');
  const [pricing, setPricing] = useState<{ l1?: string; l2?: string; sub?: string }>({});
  useEffect(() => {
    if (!showSheet || pricing.l1) return;
    let cancelled = false;
    (async () => {
      try {
        const [skuRes, planRes] = await Promise.all([
          api.get('/store/skus'),
          api.get('/payments/plans').catch(() => null),
        ]);
        const byCode: Record<string, any> = {};
        (skuRes.data?.skus || []).forEach((s: any) => { byCode[s.code] = s; });
        const l1 = byCode['L1'];
        const l2 = byCode['L2'];
        const paid = (planRes?.data?.plans || [])
          .map((p: any) => p.price_paise)
          .filter((x: number) => x > 0);
        if (cancelled) return;
        setPricing({
          l1: l1 ? `${money(l1.price_paise)} · 1 decision + PDF` : undefined,
          l2: l2 ? `${money(l2.price_paise)} · 10 decisions across modules` : undefined,
          sub: paid.length ? `From ${money(Math.min(...paid))}/mo · unlimited` : undefined,
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
    setShowSheet(true);
  }, [state, onAllowed, children]);

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
              Pick a plan or on-demand pack to create a new {MODULE_LABEL[module]} decision.
            </Text>
            <View style={styles.options}>
              <OptionRow icon="document-text" tone="#3B82F6" title="DIY Decision Report" desc={pricing.l1 ?? '₹199 · 1 decision + PDF'} onPress={() => { setShowSheet(false); router.push({ pathname: '/store', params: { highlight: 'L1', module } } as any); }} />
              <OptionRow icon="people" tone="#7C3AED" title="10-Decision Family Bundle" desc={pricing.l2 ?? '₹999 · 10 decisions across modules'} onPress={() => { setShowSheet(false); router.push({ pathname: '/store', params: { highlight: 'L2', module } } as any); }} />
              <OptionRow icon="infinite" tone="#059669" title="Monthly Subscription" desc={pricing.sub ?? 'From ₹149/mo · unlimited'} onPress={() => { setShowSheet(false); router.push('/pricing' as any); }} />
            </View>
            <View style={styles.footerRow}>
              <TouchableOpacity style={styles.dismissBtn} onPress={() => setShowSheet(false)}>
                <Text style={styles.dismissText}>Not now</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.viewAll} onPress={() => { setShowSheet(false); router.push({ pathname: '/store', params: { module } } as any); }}>
                <Text style={styles.viewAllText}>See all plans →</Text>
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
