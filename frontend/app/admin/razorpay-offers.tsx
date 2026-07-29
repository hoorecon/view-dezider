import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Switch, Platform, KeyboardAvoidingView, Modal,
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
 * Admin · Razorpay Offers (manual add).
 *
 * Razorpay does NOT expose a public "list all offers" REST endpoint (verified
 * via their docs — offers can only be fetched by ID). So instead of a bulk
 * Sync, the admin creates each offer on Razorpay Dashboard, copies the offer_id,
 * and adds it here with the flows it should auto-attach to at checkout.
 */
type Offer = {
  offer_id: string;
  label: string;
  display_text?: string;
  apply_flows: string[];
  active: boolean;
  priority: number;
  source?: string;
  created_at?: string;
  updated_at?: string;
};

const FLOW_OPTIONS: Array<{ id: string; label: string }> = [
  { id: 'recurring', label: 'Recurring Subscription' },
  { id: 'onetime', label: 'One-time Subscription' },
  { id: 'sku', label: 'SKU / Store' },
  { id: 'topup', label: 'AI Wallet Top-up' },
  { id: 'decision_flow', label: 'Decision-flow' },
];

export default function AdminRazorpayOffersScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const role = (user?.role || '').toLowerCase();
  const isAdmin = role === 'super_admin' || role === 'admin';

  const [offers, setOffers] = useState<Offer[]>([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);

  // Add-form state
  const [fOfferId, setFOfferId] = useState('');
  const [fLabel, setFLabel] = useState('');
  const [fDisplay, setFDisplay] = useState('');
  const [fFlows, setFFlows] = useState<Set<string>>(new Set());
  const [fPriority, setFPriority] = useState('100');
  const [saving, setSaving] = useState(false);

  const resetForm = () => {
    setFOfferId(''); setFLabel(''); setFDisplay(''); setFFlows(new Set()); setFPriority('100');
  };

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

  const addOffer = async () => {
    if (!fOfferId.trim().startsWith('offer_')) {
      showAlert('Invalid Offer ID', 'Offer ID must start with "offer_". Copy the full ID from Razorpay Dashboard → Offers → Offer detail page.');
      return;
    }
    if (fFlows.size === 0) {
      showAlert('Pick at least one flow', 'Select which checkout flow(s) this offer should auto-attach to.');
      return;
    }
    setSaving(true);
    try {
      await api.post('/admin/razorpay-offers', {
        offer_id: fOfferId.trim(),
        label: fLabel.trim(),
        display_text: fDisplay.trim(),
        apply_flows: Array.from(fFlows),
        active: true,
        priority: Number(fPriority) || 100,
      });
      setAddOpen(false); resetForm();
      await fetchOffers();
      showAlert('Added', 'Offer will now auto-attach at checkout for the selected flows.');
    } catch (e: any) {
      showAlert('Add failed', e?.response?.data?.detail || 'Could not add offer.');
    } finally {
      setSaving(false);
    }
  };

  const patchOffer = async (offer_id: string, patch: Partial<Offer>) => {
    setOffers((prev) => prev.map((o) => (o.offer_id === offer_id ? { ...o, ...patch } : o)));
    try {
      await api.put(`/admin/razorpay-offers/${offer_id}`, patch);
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || 'Could not update offer.');
      fetchOffers();
    }
  };

  const deleteOffer = async (offer_id: string) => {
    try {
      await api.delete(`/admin/razorpay-offers/${offer_id}`);
      setOffers((prev) => prev.filter((o) => o.offer_id !== offer_id));
    } catch (e: any) {
      showAlert('Delete failed', e?.response?.data?.detail || 'Could not delete offer.');
    }
  };

  const toggleFlow = (o: Offer, flow: string) => {
    const cur = new Set(o.apply_flows || []);
    if (cur.has(flow)) cur.delete(flow); else cur.add(flow);
    patchOffer(o.offer_id, { apply_flows: Array.from(cur) });
  };

  const toggleFormFlow = (flow: string) => {
    const n = new Set(fFlows);
    if (n.has(flow)) n.delete(flow); else n.add(flow);
    setFFlows(n);
  };

  if (!isAdmin) {
    return <SafeAreaView style={styles.container}><Text style={styles.gate}>Super-admin access only.</Text></SafeAreaView>;
  }

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => safeBack(router, '/admin')} style={styles.backBtn}>
            <Ionicons name="chevron-back" size={22} color={COLORS.textPrimary} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Razorpay Offers</Text>
          <TouchableOpacity onPress={() => { resetForm(); setAddOpen(true); }} style={styles.addBtn}>
            <Ionicons name="add" size={16} color={COLORS.white} />
            <Text style={styles.addBtnText}>Add Offer</Text>
          </TouchableOpacity>
        </View>

        {loading ? <ActivityIndicator color={COLORS.primary} style={{ marginTop: 40 }} /> : (
          <ScrollView contentContainerStyle={styles.scroll}>
            <View style={styles.infoCard}>
              <Ionicons name="information-circle" size={18} color={COLORS.primary} />
              <Text style={styles.infoText}>
                <Text style={{ fontWeight: '700' }}>How this works:</Text> Razorpay does not expose a "list offers" API,
                so bulk sync is not possible. Instead, create each offer on{' '}
                <Text style={{ fontWeight: '700' }}>Razorpay Dashboard → Offers</Text>, then copy the
                <Text style={{ fontWeight: '700' }}> offer ID</Text> (starts with{' '}
                <Text style={{ fontFamily: Platform.select({ web: 'monospace', default: 'System' }) }}>offer_XXX</Text>) and paste it here via{' '}
                <Text style={{ fontWeight: '700' }}>+ Add Offer</Text>. Choose the flow(s) it should auto-attach to at checkout.
                Subscription offers → <Text style={{ fontWeight: '700' }}>Recurring Subscription</Text>. Bank/UPI/card
                offers → <Text style={{ fontWeight: '700' }}>One-time / SKU / Top-up</Text>.
                {"\n\n"}
                <Text style={{ fontWeight: '700' }}>Priority</Text> (lower wins) — used when multiple offers match the
                same flow (subscriptions accept only one offer per create call).
              </Text>
            </View>

            {offers.length === 0 && (
              <Text style={styles.empty}>
                No offers added yet. Click <Text style={{ fontWeight: '700' }}>+ Add Offer</Text> after creating one on the Razorpay Dashboard.
              </Text>
            )}

            {offers.map((o) => (
              <View key={o.offer_id} style={[styles.card, o.active === false && styles.cardInactive]}>
                <View style={styles.cardHead}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.offerName}>{o.label || o.offer_id}</Text>
                    {!!o.display_text && <Text style={styles.offerSub} numberOfLines={2}>{o.display_text}</Text>}
                    <Text style={styles.offerId}>{o.offer_id}</Text>
                  </View>
                  <View style={{ alignItems: 'flex-end', gap: 6 }}>
                    <Switch value={o.active !== false} onValueChange={(v) => patchOffer(o.offer_id, { active: v })} />
                    <TouchableOpacity onPress={() => deleteOffer(o.offer_id)} accessibilityLabel="Delete offer">
                      <Ionicons name="trash-outline" size={18} color="#DC2626" />
                    </TouchableOpacity>
                  </View>
                </View>

                <View style={styles.priorityRow}>
                  <Text style={styles.priorityLabel}>Priority</Text>
                  <TextInput
                    style={styles.priorityInput}
                    keyboardType="numeric"
                    value={String(o.priority ?? 100)}
                    onChangeText={(t) => setOffers((prev) => prev.map((x) => (x.offer_id === o.offer_id ? { ...x, priority: Number(t) || 100 } : x)))}
                    onBlur={() => patchOffer(o.offer_id, { priority: Number(o.priority) || 100 })}
                  />
                </View>

                <Text style={styles.flowLabel}>Auto-attach to flows</Text>
                <View style={styles.flowRow}>
                  {FLOW_OPTIONS.map((f) => {
                    const on = (o.apply_flows || []).includes(f.id);
                    return (
                      <TouchableOpacity key={f.id} style={[styles.flowChip, on && styles.flowChipOn]} onPress={() => toggleFlow(o, f.id)}>
                        <Ionicons name={on ? 'checkmark-circle' : 'ellipse-outline'} size={13} color={on ? COLORS.primary : COLORS.textMuted} />
                        <Text style={[styles.flowChipT, on && styles.flowChipTOn]}>{f.label}</Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>
                {(o.apply_flows || []).length === 0 && (
                  <Text style={styles.warnText}>⚠️ No flows selected — this offer won't be used at checkout.</Text>
                )}
              </View>
            ))}
          </ScrollView>
        )}

        <Modal visible={addOpen} transparent animationType="slide" onRequestClose={() => setAddOpen(false)}>
          <View style={styles.modalOverlay}>
            <View style={styles.modalSheet}>
              <View style={styles.modalHead}>
                <Text style={styles.modalTitle}>Add Razorpay Offer</Text>
                <TouchableOpacity onPress={() => setAddOpen(false)}><Ionicons name="close" size={22} color={COLORS.textSecondary} /></TouchableOpacity>
              </View>
              <ScrollView>
                <Text style={styles.formLabel}>Offer ID *</Text>
                <TextInput style={styles.formInput} placeholder="offer_XXXXXXXXXXXXXX" placeholderTextColor={COLORS.textMuted} value={fOfferId} onChangeText={setFOfferId} autoCapitalize="none" />
                <Text style={styles.formHint}>Copy from Razorpay Dashboard → Offers → click the offer → the ID at the top.</Text>

                <Text style={styles.formLabel}>Label (internal)</Text>
                <TextInput style={styles.formInput} placeholder="e.g. HDFC Card 10% off ₹1999+" placeholderTextColor={COLORS.textMuted} value={fLabel} onChangeText={setFLabel} />

                <Text style={styles.formLabel}>Display text (what customer sees)</Text>
                <TextInput style={styles.formInput} placeholder="e.g. Save ₹200 with HDFC Credit Card" placeholderTextColor={COLORS.textMuted} value={fDisplay} onChangeText={setFDisplay} />

                <Text style={styles.formLabel}>Priority</Text>
                <TextInput style={styles.formInput} keyboardType="numeric" value={fPriority} onChangeText={setFPriority} />

                <Text style={styles.formLabel}>Auto-attach to flows *</Text>
                <View style={styles.flowRow}>
                  {FLOW_OPTIONS.map((f) => {
                    const on = fFlows.has(f.id);
                    return (
                      <TouchableOpacity key={f.id} style={[styles.flowChip, on && styles.flowChipOn]} onPress={() => toggleFormFlow(f.id)}>
                        <Ionicons name={on ? 'checkmark-circle' : 'ellipse-outline'} size={13} color={on ? COLORS.primary : COLORS.textMuted} />
                        <Text style={[styles.flowChipT, on && styles.flowChipTOn]}>{f.label}</Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>

                <TouchableOpacity style={[styles.saveBtn, saving && { opacity: 0.6 }]} onPress={addOffer} disabled={saving}>
                  {saving ? <ActivityIndicator color={COLORS.white} /> : <Text style={styles.saveBtnText}>Add Offer</Text>}
                </TouchableOpacity>
              </ScrollView>
            </View>
          </View>
        </Modal>
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
  addBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: COLORS.primary, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10 },
  addBtnText: { color: COLORS.white, fontWeight: '700', fontSize: 13 },
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
  priorityRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10 },
  priorityLabel: { fontSize: 11, fontWeight: '700', color: COLORS.textSecondary },
  priorityInput: { width: 60, borderWidth: 1, borderColor: COLORS.border, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4, fontSize: 12, color: COLORS.textPrimary, backgroundColor: COLORS.white, textAlign: 'center' },
  flowLabel: { fontSize: 11, fontWeight: '800', color: COLORS.textSecondary, textTransform: 'uppercase', marginTop: 10, marginBottom: 6 },
  flowRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  flowChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.background },
  flowChipOn: { backgroundColor: '#EEF2FF', borderColor: COLORS.primary },
  flowChipT: { fontSize: 11, color: COLORS.textSecondary, fontWeight: '600' },
  flowChipTOn: { color: COLORS.primary },
  warnText: { fontSize: 11, color: '#DC2626', marginTop: 8, fontStyle: 'italic' },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  modalSheet: { backgroundColor: COLORS.white, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 16, maxHeight: '90%', maxWidth: 700, width: '100%', alignSelf: 'center' },
  modalHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 },
  modalTitle: { fontSize: 16, fontWeight: '800', color: COLORS.textPrimary },
  formLabel: { fontSize: 11, fontWeight: '800', color: COLORS.textSecondary, textTransform: 'uppercase', marginTop: 12, marginBottom: 6 },
  formInput: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 13, color: COLORS.textPrimary, backgroundColor: COLORS.white },
  formHint: { fontSize: 11, color: COLORS.textMuted, marginTop: 4, fontStyle: 'italic' },
  saveBtn: { backgroundColor: COLORS.primary, paddingVertical: 12, borderRadius: 10, alignItems: 'center', marginTop: 18, marginBottom: 12 },
  saveBtnText: { color: COLORS.white, fontWeight: '700', fontSize: 14 },
});
