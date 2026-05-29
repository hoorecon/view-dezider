/**
 * <ModuleStoreActions> — drop-in action bar for decision detail/summary views.
 *
 * Three contextual CTAs that work across MyDezider, Pros & Cons, and SWOT:
 *  • Download Report (L1)  — calls /reports/{module}/{id}.pdf; if no entitlement
 *                            yet, deep-links to /store?highlight=L1.
 *  • Book Expert (L3)      — checks for L3 balance; if none → /store?highlight=L3
 *                            (purchase first); else deep-links to /tools/expert-net
 *                            filtered by the decision's life_area_id.
 *  • Order Expert Review (L4) — purchase + admin queues delivery; manual
 *                               fulfillment for Phase 2.
 *
 * Renders as a soft-coloured horizontal row of pills, safe in narrow viewports.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform, ActivityIndicator, Linking } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../utils/api';
import { showAlert, confirmDialog } from '../utils/alert';
import type { DecisionModule } from './PaywallGate';

interface Props {
  module: DecisionModule;
  decisionId: string;
  lifeAreaId?: string | null;
  subAreaId?: string | null;
}

interface ReportInfo { unlocked: boolean; unlocked_via?: string | null; l1_balance: number; l2_balance: number; }

export default function ModuleStoreActions({ module, decisionId, lifeAreaId, subAreaId }: Props) {
  const router = useRouter();
  const [info, setInfo] = useState<ReportInfo | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const loadInfo = useCallback(async () => {
    try {
      const res = await api.get(`/reports/${module}/${decisionId}/info`);
      setInfo(res.data);
    } catch {
      setInfo({ unlocked: false, l1_balance: 0, l2_balance: 0 });
    }
  }, [module, decisionId]);
  useEffect(() => { loadInfo(); }, [loadInfo]);

  const downloadPdf = useCallback(async () => {
    setBusy('L1');
    try {
      const base = (process.env.EXPO_PUBLIC_BACKEND_URL || '') + `/api/reports/${module}/${decisionId}.pdf`;
      // Use a fetch+blob so we can pass the auth header (axios does not stream PDFs nicely on web)
      const AsyncStorage = (await import('@react-native-async-storage/async-storage')).default;
      const token = await AsyncStorage.getItem('session_token');
      const resp = await fetch(base, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
      if (resp.status === 402) {
        // No entitlement — kick to store
        const want = await confirmDialog('Unlock report', 'You need a DIY Decision Report (₹199) or any plan to download the PDF. Open the store now?', { confirmText: 'Open store' });
        if (want) router.push({ pathname: '/store', params: { highlight: 'L1', module, decision_id: decisionId } } as any);
        return;
      }
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(text || 'Download failed');
      }
      const blob = await resp.blob();
      if (Platform.OS === 'web') {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `dezider_${module}_${decisionId.slice(0, 8)}.pdf`;
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1500);
      } else {
        // Native: open in browser (good enough for Phase A; native FS save can be added later)
        const reader = new FileReader();
        reader.onloadend = () => Linking.openURL(reader.result as string);
        reader.readAsDataURL(blob);
      }
      await loadInfo();
      showAlert('Report ready', 'Your PDF has been downloaded.');
    } catch (e: any) {
      showAlert('Download failed', e?.message || 'Try again later.');
    } finally { setBusy(null); }
  }, [module, decisionId, router, loadInfo]);

  const bookExpert = useCallback(async () => {
    setBusy('L3');
    try {
      // Check L3 balance up front
      const res = await api.get('/store/my-entitlements');
      const l3 = (res.data?.entitlements || []).find((x: any) => x.sku_code === 'L3');
      const hasL3 = (l3?.balance || 0) > 0;
      if (!hasL3) {
        const want = await confirmDialog('Book a Professional Session', 'A Professional Guided Session (₹1,999) lets you screen-share your decision with an expert. Buy now?', { confirmText: 'Open store' });
        if (want) router.push({ pathname: '/store', params: { highlight: 'L3', module, decision_id: decisionId } } as any);
        return;
      }
      // Deep-link into expert-net filtered by life area
      router.push({ pathname: '/tools/expert-net' as any, params: { from_module: module, decision_id: decisionId, life_area_id: lifeAreaId || '', sub_area_id: subAreaId || '' } } as any);
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Could not check entitlements.');
    } finally { setBusy(null); }
  }, [module, decisionId, router, lifeAreaId, subAreaId]);

  const orderReview = useCallback(async () => {
    const ok = await confirmDialog('Order Expert Review', 'A domain expert will review this decision and send written recommendations within 48 hrs (₹2,800). Continue to store?', { confirmText: 'Buy L4' });
    if (!ok) return;
    router.push({ pathname: '/store', params: { highlight: 'L4', module, decision_id: decisionId } } as any);
  }, [router, module, decisionId]);

  return (
    <View style={s.row}>
      <Pill icon="download" label={info?.unlocked ? 'Download PDF' : 'Unlock PDF'} tone="#3B82F6" busy={busy === 'L1'} onPress={downloadPdf} hint={info?.unlocked ? null : info?.l1_balance ? `${info.l1_balance} L1 left` : null} />
      <Pill icon="videocam" label="Book Expert" tone="#059669" busy={busy === 'L3'} onPress={bookExpert} />
      <Pill icon="ribbon" label="Expert Review" tone="#DC2626" busy={busy === 'L4'} onPress={orderReview} />
    </View>
  );
}

function Pill({ icon, label, tone, onPress, busy, hint }: { icon: any; label: string; tone: string; onPress: () => void; busy?: boolean; hint?: string | null }) {
  return (
    <TouchableOpacity onPress={onPress} style={[s.pill, { borderColor: tone + '55', backgroundColor: tone + '12' }]} disabled={!!busy} accessibilityLabel={label}>
      {busy ? <ActivityIndicator size="small" color={tone} /> : <Ionicons name={icon} size={16} color={tone} />}
      <Text style={[s.pillText, { color: tone }]}>{label}</Text>
      {hint && <Text style={[s.pillHint, { color: tone }]}>· {hint}</Text>}
    </TouchableOpacity>
  );
}

const s = StyleSheet.create({
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginVertical: 10, paddingHorizontal: 4 },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 999, borderWidth: 1 },
  pillText: { fontSize: 13, fontWeight: '700' },
  pillHint: { fontSize: 11, fontWeight: '600', opacity: 0.85 },
});
