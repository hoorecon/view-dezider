import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, Switch, Platform, KeyboardAvoidingView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { useAuthStore } from '../../src/store/authStore';
import { safeBack } from '../../src/utils/navigation';

/**
 * Admin · Razorpay Offers.
 *
 * Purpose: Merchant creates their Payment offers (Discounts & Cash Backs) AND
 * Subscription offers directly on the Razorpay Dashboard → Offers. This screen
 * pulls that list via `client.offer.all()` into our local `razorpay_offers`
 * collection, and lets the admin choose which flow(s) each offer should
 * auto-attach to at checkout (onetime / recurring / sku / topup / decision_flow).
 *
 * At checkout time, `subscriptions.py` reads this config and forwards the
 * appropriate `offer_id` / `offers[]` to Razorpay's create-order and
 * create-subscription APIs.
 */
type Offer = {
  offer_id: string;
  name: string;
  display_text?: string;
  type?: string;
  payment_method?: string;
  discount_amount?: number | null;
  discount_percentage?: number | null;
  min_order_value?: number | null;
  max_offer_amount?: number | null;
  issuer?: string;
  status?: string;
  starts_at?: number;
  ends_at?: number;
  apply_flows?: string[];
  active?: boolean;
  priority?: number;
  source?: string;
};

const FLOW_OPTIONS: Array<{ id: string; label: string; hint: string }> = [
  { id: 'recurring', label: 'Recurring Subscription', hint: 'Attached as offer_id on subscription.create' },
  { id: 'onetime', label: 'One-time Subscription', hint: 'Attached to order.create (Pay Once button)' },
  { id: 'sku', label: 'SKU / Store Purchase', hint: 'Attached to SKU checkout orders' },
  { id: 'topup', label: 'AI Wallet Top-up', hint: 'Attached to top-up orders' },
  { id: 'decision_flow', label: 'Decision-flow Purchase', hint: 'Attached to standalone flow purchases' },
];

export default function AdminRazorpayOffersScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const role = (user?.role || '').toLowerCase();
  const isAdmin = role === 'super_admin' || role === 'admin';

  const [offers, setOffers] = useState<Offer[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  const fetchOffers = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/admin/razorpay-offers');
      setOffers(r.data?.offers || []);
    } catch (e: any) {
      showAlert('Load failed', e?.response?.data?.detail || 'Could not load offers.');
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { if (isAdmin) fetchOffers(); }, [isAdmin, fetchOffers]));

  const syncOffers = async () => {
    setSyncing(true);
    try {
      const r = await api.post('/admin/razorpay-offers/sync', {});
      setOffers(r.data?.offers || []);
      const ins = r.data?.inserted ?? 0;
      const upd = r.data?.updated ?? 0;
      const orp = r.data?.orphaned ?? 0;
      showAlert('Synced from Razorpay', `${ins} new offer${ins === 1 ? '' : 's'} added, ${upd} refreshed, ${orp} orphaned.`);
    } catch (e: any) {
      showAlert('Sync failed', e?.response?.data?.detail || 'Could not sync offers.');
    } finally {
      setSyncing(false);
    }
  };

  const patchOffer = async (offer_id: string, patch: Partial<Offer>) => {
    // Optimistic update first so the switch feels instant.
    setOffers((prev) => prev.map((o) => (o.offer_id === offer_id ? { ...o, ...patch } : o)));
    try {
      await api.put(`/admin/razorpay-offers/${offer_id}`, patch);
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || 'Could not update offer.');
      fetchOffers();
    }
  };

  const toggleFlow = (o: Offer, flow: string) => {
    const cur = new Set(o.apply_flows || []);
    if (cur.has(flow)) cur.delete(flow); else cur.add(flow);
    patchOffer(o.offer_id, { apply_flows: Array.from(cur) });
  };

  if (!isAdmin) {
    return (
      <SafeAreaView style={styles.container}>
        <Text style={styles.gate}>Super-admin access only.</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => safeBack(router, '/admin')} style={styles.backBtn}>
            <Ionicons name="chevron-back" size={22} color={COLORS.textPrimary} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Razorpay Offers</Text>
          <TouchableOpacity onPress={syncOffers} disabled={syncing} style={[styles.syncBtn, syncing && { opacity: 0.6 }]}>
            {syncing ? <ActivityIndicator color={COLORS.white} /> : (
              <>
                <Ionicons name="sync" size={16} color={COLORS.white} />
                <Text style={styles.syncBtnText}>Sync</Text>
              </>
            )}
          </TouchableOpacity>
        </View>

        {loading ? (
          <ActivityIndicator color={COLORS.primary} style={{ marginTop: 40 }} />
        ) : (
          <ScrollView contentContainerStyle={styles.scroll}>
            <View style={styles.infoCard}>
              <Ionicons name="information-circle" size={18} color={COLORS.primary} />
              <Text style={styles.infoText}>
                Create your Payment offers and Subscription offers on{' '}
                <Text style={{ fontWeight: '700' }}>Razorpay Dashboard → Offers</Text>, then click{' '}
                <Text style={{ fontWeight: '700' }}>Sync</Text> here. For each offer, tick the flow(s) you want it to
                auto-attach to at checkout. Subscription offers should be flagged as{' '}
                <Text style={{ fontWeight: '700' }}>Recurring Subscription</Text>; card/bank/UPI cashback offers as{' '}
                <Text style={{ fontWeight: '700' }}>One-time / SKU / Top-up</Text>.
                {"\n\n"}
                <Text style={{ fontWeight: '700' }}>Priority</Text> — when multiple offers match, the one with the
                lowest priority number wins (subscriptions accept only one offer per create call).
              </Text>
            </View>

            {offers.length === 0 && (
              <Text style={styles.empty}>
                No offers synced yet. Create offers on the Razorpay Dashboard, then click Sync.
              </Text>
            )}

            {offers.map((o) => (
              <View key={o.offer_id} style={[styles.card, o.active === false && styles.cardInactive]}>
                <View style={styles.cardHead}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.offerName}>{o.name || o.offer_id}</Text>
                    {!!o.display_text && <Text style={styles.offerSub} numberOfLines={2}>{o.display_text}</Text>}
                    <Text style={styles.offerId}>{o.offer_id}</Text>
                  </View>
                  <Switch
                    value={o.active !== false}
                    onValueChange={(v) => patchOffer(o.offer_id, { active: v })}
                  />
                </View>

                <View style={styles.metaRow}>
                  {!!o.type && <Text style={styles.metaChip}>{o.type}</Text>}
                  {!!o.payment_method && <Text style={styles.metaChip}>{o.payment_method}</Text>}
                  {!!o.issuer && <Text style={styles.metaChip}>{o.issuer}</Text>}
                  {o.discount_percentage != null && <Text style={styles.metaChip}>{o.discount_percentage}% off</Text>}
                  {o.discount_amount != null && o.discount_amount > 0 && (
                    <Text style={styles.metaChip}>Flat ₹{Math.round((o.discount_amount || 0) / 100)}</Text>
                  )}
                  {o.min_order_value != null && o.min_order_value > 0 && (
                    <Text style={styles.metaChip}>Min ₹{Math.round((o.min_order_value || 0) / 100)}</Text>
                  )}
                  {!!o.status && <Text style={[styles.metaChip, o.status === 'active' && styles.metaChipActive]}>{o.status}</Text>}
                </View>

                <Text style={styles.flowLabel}>Auto-attach to flows</Text>
                <View style={styles.flowRow}>
                  {FLOW_OPTIONS.map((f) => {
                    const on = (o.apply_flows || []).includes(f.id);
                    return (
                      <TouchableOpacity
                        key={f.id}
                        style={[styles.flowChip, on && styles.flowChipOn]}
                        onPress={() => toggleFlow(o, f.id)}
                      >
                        <Ionicons name={on ? 'checkmark-circle' : 'ellipse-outline'} size={14} color={on ? COLORS.primary : COLORS.textMuted} />
                        <Text style={[styles.flowChipT, on && styles.flowChipTOn]}>{f.label}</Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>
                <Text style={styles.hint}>
                  {(o.apply_flows || []).length === 0
                    ? '⚠️ No flows selected — this offer will NOT be used at checkout.'
                    : `Currently attaches to: ${(o.apply_flows || []).map((f) => FLOW_OPTIONS.find((x) => x.id === f)?.label || f).join(' · ')}`}
                </Text>
              </View>
            ))}
          </ScrollView>
        )}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  gate: { fontSize: 14, color: COLORS.textMuted, textAlign: 'center', marginTop: 40 },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: COLORS.border, backgroundColor: COLORS.white },
  backBtn: { padding: 4 },
  headerTitle: { fontSize: 17, fontWeight: '800', color: COLORS.textPrimary, flex: 1, marginLeft: 8 },
  syncBtn: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: COLORS.primary, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10 },
  syncBtnText: { color: COLORS.white, fontWeight: '700', fontSize: 13 },
  scroll: { padding: 12, paddingBottom: 40, maxWidth: 900, width: '100%', alignSelf: 'center' },
  infoCard: { flexDirection: 'row', gap: 8, backgroundColor: '#EEF2FF', padding: 12, borderRadius: 12, marginBottom: 14 },
  infoText: { flex: 1, fontSize: 12, color: COLORS.textSecondary, lineHeight: 18 },
  empty: { fontSize: 13, color: COLORS.textMuted, textAlign: 'center', marginVertical: 30, paddingHorizontal: 20, lineHeight: 20 },
  card: { backgroundColor: COLORS.white, borderRadius: 14, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: COLORS.border },
  cardInactive: { opacity: 0.55 },
  cardHead: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  offerName: { fontSize: 15, fontWeight: '800', color: COLORS.textPrimary },
  offerSub: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },
  offerId: { fontSize: 10, color: COLORS.textMuted, marginTop: 3, fontFamily: Platform.select({ web: 'monospace', default: 'System' }) },
  metaRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8, marginBottom: 4 },
  metaChip: { fontSize: 10, color: COLORS.textSecondary, backgroundColor: COLORS.background, paddingHorizontal: 7, paddingVertical: 3, borderRadius: 8, fontWeight: '600', overflow: 'hidden' },
  metaChipActive: { backgroundColor: '#DCFCE7', color: '#166534' },
  flowLabel: { fontSize: 11, fontWeight: '800', color: COLORS.textSecondary, textTransform: 'uppercase', marginTop: 10, marginBottom: 6 },
  flowRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  flowChip: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.background },
  flowChipOn: { backgroundColor: '#EEF2FF', borderColor: COLORS.primary },
  flowChipT: { fontSize: 11, color: COLORS.textSecondary, fontWeight: '600' },
  flowChipTOn: { color: COLORS.primary },
  hint: { fontSize: 11, color: COLORS.textMuted, marginTop: 8, fontStyle: 'italic', lineHeight: 15 },
});
