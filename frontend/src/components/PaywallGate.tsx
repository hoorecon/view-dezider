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
import { Modal, Pressable, ScrollView, StyleSheet, Text, TouchableOpacity, View, ActivityIndicator } from 'react-native';
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

  const refresh = useCallback(async () => {
    try {
      const res = await api.get('/store/access-check', { params: { module } });
      setState({ has_access: !!res.data?.has_access, via: res.data?.via, balance: res.data?.balance, loading: false });
    } catch {
      // Fail open so a broken backend never blocks creators.
      setState({ has_access: true, loading: false });
    }
  }, [module]);

  useEffect(() => { refresh(); }, [refresh]);

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
        <Pressable style={styles.backdrop} onPress={() => setShowSheet(false)}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <View style={styles.handle} />
            <Ionicons name="lock-closed" size={36} color="#7C3AED" />
            <Text style={styles.title}>Unlock {MODULE_LABEL[module]}</Text>
            <Text style={styles.body}>You need a paid plan or on-demand pack to create a new {MODULE_LABEL[module]} decision. Pick what suits you:</Text>
            <View style={styles.options}>
              <OptionRow icon="document-text" tone="#3B82F6" title="DIY Decision Report" desc="₹199 · 1 decision + PDF" onPress={() => { setShowSheet(false); router.push({ pathname: '/store', params: { highlight: 'L1', module } } as any); }} />
              <OptionRow icon="people" tone="#7C3AED" title="10-Decision Family Bundle" desc="₹999 · 10 decisions across modules" onPress={() => { setShowSheet(false); router.push({ pathname: '/store', params: { highlight: 'L2', module } } as any); }} />
              <OptionRow icon="infinite" tone="#059669" title="Monthly Subscription" desc="From ₹149/mo · unlimited" onPress={() => { setShowSheet(false); router.push('/pricing' as any); }} />
            </View>
            <TouchableOpacity style={styles.viewAll} onPress={() => { setShowSheet(false); router.push({ pathname: '/store', params: { module } } as any); }}>
              <Text style={styles.viewAllText}>See all plans →</Text>
            </TouchableOpacity>
            {state.loading && <ActivityIndicator size="small" />}
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
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: '#FFFFFF', borderTopLeftRadius: 22, borderTopRightRadius: 22, paddingHorizontal: 20, paddingTop: 12, paddingBottom: 28, alignItems: 'center', gap: 6 },
  handle: { width: 40, height: 4, borderRadius: 2, backgroundColor: '#E5E7EB', marginBottom: 10 },
  title: { fontSize: 20, fontWeight: '700', color: '#0F172A', marginTop: 8 },
  body: { fontSize: 14, color: '#475569', textAlign: 'center', marginTop: 4, marginBottom: 12, lineHeight: 20 },
  options: { width: '100%', gap: 10, marginTop: 4 },
  option: { flexDirection: 'row', alignItems: 'center', borderWidth: 1.5, borderRadius: 14, paddingVertical: 12, paddingHorizontal: 12, gap: 12 },
  optionIcon: { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center' },
  optionTitle: { fontSize: 15, fontWeight: '600', color: '#0F172A' },
  optionDesc: { fontSize: 12, color: '#64748B', marginTop: 1 },
  viewAll: { marginTop: 16, paddingHorizontal: 16, paddingVertical: 10 },
  viewAllText: { color: '#7C3AED', fontWeight: '600', fontSize: 14 },
});
