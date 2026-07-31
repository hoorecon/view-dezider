import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, TextInput, Switch, Platform, KeyboardAvoidingView,
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
 * Admin · Subscription Plan config.
 * Moved out of the user-facing /subscription-plans screen — only admins
 * configure credits/active state and pull live pricing from Razorpay here.
 */
export default function AdminSubscriptionPlansScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const role = (user?.role || '').toLowerCase();
  const isAdmin = role === 'super_admin' || role === 'admin';

  const [loading, setLoading] = useState(true);
  const [plans, setPlans] = useState<any[]>([]);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  // Per-plan editable "key benefits" text (one benefit per line).
  const [featuresDraft, setFeaturesDraft] = useState<Record<string, string>>({});

  const fetchData = async () => {
    try {
      const res = await api.get('/admin/subscriptions/plans');
      const list = res.data?.plans || [];
      setPlans(list);
      const drafts: Record<string, string> = {};
      list.forEach((p: any) => { drafts[p.plan_id] = (p.features || []).join('\n'); });
      setFeaturesDraft(drafts);
    } catch { /* silent */ } finally {
      setLoading(false);
    }
  };

  useFocusEffect(useCallback(() => { fetchData(); }, []));

  const savePlan = async (p: any) => {
    setSavingId(p.plan_id);
    try {
      const features = (featuresDraft[p.plan_id] ?? '')
        .split('\n').map(s => s.trim()).filter(Boolean).slice(0, 12);
      const res = await api.put(`/admin/subscriptions/plans/${p.plan_id}`, {
        credits_per_month: Number(p.credits_per_month),
        active: !!p.active,
        name: p.name,
        features,
        display_order: Number(p.display_order ?? 99),
      });
      setPlans(prev => prev.map(x => x.plan_id === p.plan_id ? res.data : x));
      setFeaturesDraft(prev => ({ ...prev, [p.plan_id]: (res.data.features || []).join('\n') }));
      showAlert('Saved', `${res.data.name} updated.`);
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || 'Could not update plan.');
    } finally {
      setSavingId(null);
    }
  };

  /**
   * Reorder — swaps this plan's display_order with its neighbour and persists
   * both changes so the user-facing pricing page reflects the new order.
   */
  const reorderPlan = async (planId: string, direction: 'up' | 'down') => {
    // Work on a locally-sorted snapshot so index math matches the visible list.
    const sorted = [...plans].sort(
      (a, b) => (a.display_order ?? 99) - (b.display_order ?? 99),
    );
    const idx = sorted.findIndex((x) => x.plan_id === planId);
    if (idx < 0) return;
    const swapIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (swapIdx < 0 || swapIdx >= sorted.length) return;

    const a = sorted[idx];
    const b = sorted[swapIdx];
    const aOrder = a.display_order ?? 99;
    const bOrder = b.display_order ?? 99;
    // If they collide, seed unique values so subsequent swaps still work.
    const newA = bOrder === aOrder ? aOrder + (direction === 'up' ? -1 : 1) : bOrder;
    const newB = aOrder;

    // Optimistic UI update, then persist both.
    setPlans((prev) =>
      prev.map((x) => {
        if (x.plan_id === a.plan_id) return { ...x, display_order: newA };
        if (x.plan_id === b.plan_id) return { ...x, display_order: newB };
        return x;
      }),
    );
    try {
      await Promise.all([
        api.put(`/admin/subscriptions/plans/${a.plan_id}`, { display_order: newA }),
        api.put(`/admin/subscriptions/plans/${b.plan_id}`, { display_order: newB }),
      ]);
    } catch (e: any) {
      showAlert('Reorder failed', e?.response?.data?.detail || 'Could not save order.');
      // Roll back to server truth on failure.
      fetchData();
    }
  };

  const syncPlans = async () => {
    setSyncing(true);
    try {
      const res = await api.post('/admin/subscriptions/sync', {});
      setPlans(res.data?.plans || []);
      const ins = res.data?.inserted ?? 0;
      const upd = res.data?.updated ?? 0;
      const orp = res.data?.orphaned ?? 0;
      showAlert(
        'Synced from Razorpay',
        `${ins} new plan${ins === 1 ? '' : 's'} added, ${upd} updated, ${orp} orphaned (marked inactive).`,
      );
    } catch (e: any) {
      showAlert('Sync failed', e?.response?.data?.detail || 'Could not sync.');
    } finally {
      setSyncing(false);
    }
  };

  const [backfilling, setBackfilling] = useState(false);
  const runBackfill = async (dryRun: boolean) => {
    setBackfilling(true);
    try {
      const res = await api.post('/admin/subscriptions/backfill-ai-wallet', { dry_run: dryRun });
      const { scanned = 0, granted = 0, skipped = 0, total_credits_granted = 0, razorpay_reconcile = {} } = res.data || {};
      showAlert(
        dryRun ? 'Backfill preview' : 'Backfill complete',
        `Razorpay reconcile: users=${razorpay_reconcile.users_reconciled ?? 0}, payments applied=${razorpay_reconcile.payments_applied ?? 0}\n\n` +
        `Scanned ${scanned} paying users.\n` +
        `${dryRun ? 'Would grant' : 'Granted'}: ${granted} users · ${total_credits_granted} credits.\n` +
        `Skipped: ${skipped} (already backfilled / no credits / errors).`,
      );
    } catch (e: any) {
      showAlert('Backfill failed', e?.response?.data?.detail || 'Could not backfill.');
    } finally {
      setBackfilling(false);
    }
  };

  const [diagEmail, setDiagEmail] = useState('');
  const [diagBusy, setDiagBusy] = useState(false);
  const runDiag = async () => {
    if (!diagEmail.trim()) { showAlert('Enter an email', 'Type the user email to diagnose.'); return; }
    setDiagBusy(true);
    try {
      const res = await api.get('/admin/subscriptions/diag', { params: { email: diagEmail.trim() } });
      const d = res.data || {};
      if (d.error) { showAlert('Diagnostic', d.error); return; }
      const reconcile = d.reconcile || {};
      const beforeBal = d.before?.ai_wallet_balance ?? 0;
      const afterBal = d.after?.ai_wallet_balance ?? 0;
      const subs = (d.local_subscriptions || []).length;
      const orders = (d.recent_payment_orders || []).length;
      const diagLines = (reconcile.diag || []).map((x: any) =>
        `• sub=${x.sub_id} status=${x.remote_status} paid_count=${x.remote_paid_count} invoices=${x.invoices_found} newly_applied=${(x.newly_applied || []).length}`).join('\n');
      showAlert(
        `Diagnostic — ${diagEmail}`,
        `Local subs: ${subs}   Orders (recent): ${orders}\n` +
        `AI wallet: ${beforeBal} → ${afterBal}\n` +
        `Reconcile: subs=${reconcile.subs || 0}, payments applied=${reconcile.payments_applied || 0}, credits=${reconcile.credits_granted || 0}\n\n` +
        (diagLines || 'No local subscription rows found for this user.'),
      );
    } catch (e: any) {
      showAlert('Diagnostic failed', e?.response?.data?.detail || 'Could not diagnose.');
    } finally {
      setDiagBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={{ width: 24 }} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Ionicons name="arrow-back" size={24} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Subscription Plans</Text>
        <TouchableOpacity style={styles.syncBtn} onPress={syncPlans} disabled={syncing}>
          {syncing ? <ActivityIndicator size="small" color={COLORS.primary} />
            : <><Ionicons name="sync" size={14} color={COLORS.primary} /><Text style={styles.syncBtnText}>Sync</Text></>}
        </TouchableOpacity>
      </View>

      {!isAdmin ? (
        <View style={styles.center}><Text style={styles.muted}>Admin access required.</Text></View>
      ) : loading ? (
        <View style={styles.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>
      ) : (
        <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <ScrollView contentContainerStyle={styles.scroll}>
            <View style={styles.infoCard}>
              <Ionicons name="information-circle" size={18} color={COLORS.primary} />
              <Text style={styles.infoText}>
                <Text style={{ fontWeight: '700' }}>Sync</Text> pulls the latest plan IDs and ₹ pricing from
                Razorpay so local records match the gateway. Set monthly credits, use the ↑/↓ arrows (or the
                Order # field) to change the display order shown on the user pricing page, and toggle
                Active/Inactive (inactive plans are hidden from users), then Save.
                {"\n\n"}
                <Text style={{ fontWeight: '700' }}>Auto-renew (recurring)</Text> is controlled in{' '}
                <Text style={{ fontWeight: '700' }}>Admin → Access Control → Credits & Subscription → “Subscribe — Auto-Renew”</Text>
                {' '}(not here). Toggle the tiers you want to enable, then Save.
              </Text>
            </View>

            {/* Retroactive AI-wallet backfill for existing paid users */}
            <View style={styles.backfillCard}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <Ionicons name="wallet" size={16} color="#7C3AED" />
                <Text style={styles.backfillTitle}>Retro-fill AI wallets for existing paid users</Text>
              </View>
              <Text style={styles.backfillBody}>
                Users who paid BEFORE v3.143 never received their plan credits into the
                Profile AI wallet. Run this once to grant each paying user their
                plan&apos;s credits_per_month into ai_wallets. Idempotent — safe to re-run.
              </Text>
              <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
                <TouchableOpacity
                  style={[styles.backfillBtn, { backgroundColor: '#E9D5FF' }]}
                  onPress={() => runBackfill(true)}
                  disabled={backfilling}
                >
                  {backfilling ? <ActivityIndicator size="small" color="#7C3AED" /> : (
                    <><Ionicons name="eye" size={14} color="#7C3AED" />
                      <Text style={[styles.backfillBtnText, { color: '#7C3AED' }]}>Preview (dry run)</Text></>
                  )}
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.backfillBtn, { backgroundColor: '#7C3AED' }]}
                  onPress={() => runBackfill(false)}
                  disabled={backfilling}
                >
                  {backfilling ? <ActivityIndicator size="small" color="#FFF" /> : (
                    <><Ionicons name="play" size={14} color="#FFF" />
                      <Text style={[styles.backfillBtnText, { color: '#FFF' }]}>Run backfill</Text></>
                  )}
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.backfillBtn, { backgroundColor: '#F3F4F6' }]}
                  onPress={() => router.push('/admin/subscribers' as any)}
                >
                  <Ionicons name="people" size={14} color={COLORS.textPrimary} />
                  <Text style={[styles.backfillBtnText, { color: COLORS.textPrimary }]}>View subscribers</Text>
                </TouchableOpacity>
              </View>

              {/* Deep-dive diagnostic — enter a paying user's email to see what
                  Razorpay + local DB say and force-reconcile. */}
              <View style={{ marginTop: 12, gap: 6 }}>
                <Text style={{ fontSize: 12, fontWeight: '700', color: '#5B21B6' }}>
                  Diagnose a specific user
                </Text>
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  <TextInput
                    value={diagEmail}
                    onChangeText={setDiagEmail}
                    placeholder="user@email.com"
                    placeholderTextColor="#A78BFA"
                    autoCapitalize="none"
                    keyboardType="email-address"
                    style={{
                      flex: 1, borderWidth: 1, borderColor: '#DDD6FE', borderRadius: 8,
                      paddingHorizontal: 10, paddingVertical: 7, backgroundColor: '#FFF',
                      color: '#111', fontSize: 13,
                    }}
                  />
                  <TouchableOpacity
                    style={[styles.backfillBtn, { backgroundColor: '#4C1D95' }]}
                    onPress={runDiag}
                    disabled={diagBusy}
                  >
                    {diagBusy ? <ActivityIndicator size="small" color="#FFF" /> : (
                      <><Ionicons name="pulse" size={14} color="#FFF" />
                        <Text style={[styles.backfillBtnText, { color: '#FFF' }]}>Diagnose</Text></>
                    )}
                  </TouchableOpacity>
                </View>
                <Text style={{ fontSize: 10, color: '#7C3AED' }}>
                  Fetches this user&apos;s Razorpay invoices live + auto-applies missed payments.
                </Text>
              </View>
            </View>

            {[...plans]
              .sort((a, b) => (a.display_order ?? 99) - (b.display_order ?? 99))
              .map((p, idx, arr) => (
              <View key={p.plan_id} style={styles.card}>
                {/* Reorder header — Up / Down arrows + numeric Order # input */}
                <View style={styles.reorderRow}>
                  <Text style={styles.reorderPos}>#{idx + 1}</Text>
                  <TouchableOpacity
                    style={[styles.reorderBtn, idx === 0 && styles.reorderBtnDisabled]}
                    onPress={() => reorderPlan(p.plan_id, 'up')}
                    disabled={idx === 0}
                    accessibilityLabel="Move plan up"
                  >
                    <Ionicons name="chevron-up" size={16} color={idx === 0 ? COLORS.textMuted : COLORS.primary} />
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.reorderBtn, idx === arr.length - 1 && styles.reorderBtnDisabled]}
                    onPress={() => reorderPlan(p.plan_id, 'down')}
                    disabled={idx === arr.length - 1}
                    accessibilityLabel="Move plan down"
                  >
                    <Ionicons name="chevron-down" size={16} color={idx === arr.length - 1 ? COLORS.textMuted : COLORS.primary} />
                  </TouchableOpacity>
                  <View style={{ flex: 1 }} />
                  <Text style={styles.reorderNumLabel}>Order #</Text>
                  <TextInput
                    style={styles.reorderNumInput}
                    keyboardType="numeric"
                    value={String(p.display_order ?? 99)}
                    onChangeText={(t) =>
                      setPlans((prev) => prev.map((x) => (x.plan_id === p.plan_id ? { ...x, display_order: t } : x)))
                    }
                  />
                </View>
                <Text style={styles.planName}>{p.name} · ₹{p.price_inr}</Text>
                <Text style={styles.planId}>{p.plan_id}</Text>
                <Text style={styles.fieldLabel}>Credits / month</Text>
                <TextInput
                  style={styles.input} keyboardType="numeric"
                  value={String(p.credits_per_month)}
                  onChangeText={(t) => setPlans(prev => prev.map(x => x.plan_id === p.plan_id ? { ...x, credits_per_month: t } : x))}
                />
                <Text style={styles.fieldLabel}>Key benefits (one per line — shown on the user pricing card)</Text>
                <TextInput
                  style={[styles.input, styles.multiline]}
                  multiline
                  value={featuresDraft[p.plan_id] ?? ''}
                  onChangeText={(t) => setFeaturesDraft(prev => ({ ...prev, [p.plan_id]: t }))}
                  placeholder={'Everything in Free\nCLD Engine\n2,000 credits / month'}
                />
                <Text style={styles.helper}>Tip: update the “credits / month” line here to match the value above.</Text>
                <View style={styles.activeRow}>
                  <Text style={styles.fieldLabel}>Active</Text>
                  <Switch
                    value={!!p.active}
                    onValueChange={(v) => setPlans(prev => prev.map(x => x.plan_id === p.plan_id ? { ...x, active: v } : x))}
                    trackColor={{ true: COLORS.primary }}
                  />
                </View>
                <TouchableOpacity style={styles.saveBtn} onPress={() => savePlan(p)} disabled={savingId === p.plan_id}>
                  {savingId === p.plan_id ? <ActivityIndicator color={COLORS.white} size="small" />
                    : <Text style={styles.saveBtnText}>Save</Text>}
                </TouchableOpacity>
              </View>
            ))}
            <View style={{ height: 32 }} />
          </ScrollView>
        </KeyboardAvoidingView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  muted: { color: COLORS.textMuted, fontSize: 14 },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12, backgroundColor: COLORS.surface,
    borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  headerTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  syncBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, borderWidth: 1, borderColor: COLORS.primary, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 5 },
  syncBtnText: { color: COLORS.primary, fontWeight: '700', fontSize: 12 },
  scroll: { padding: 16 },
  infoCard: { flexDirection: 'row', gap: 8, backgroundColor: COLORS.primary + '10', borderRadius: 12, padding: 12, marginBottom: 16 },
  infoText: { flex: 1, fontSize: 12.5, color: COLORS.textSecondary, lineHeight: 18 },
  backfillCard: { backgroundColor: '#F5F3FF', borderRadius: 12, padding: 12, marginBottom: 16, borderWidth: 1, borderColor: '#DDD6FE' },
  backfillTitle: { fontSize: 13, fontWeight: '700', color: '#5B21B6' },
  backfillBody: { fontSize: 12, color: '#4C1D95', lineHeight: 17 },
  backfillBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 7, borderRadius: 8 },
  backfillBtnText: { fontWeight: '700', fontSize: 12 },
  card: { backgroundColor: COLORS.surface, borderRadius: 14, padding: 16, marginBottom: 14, borderWidth: 1, borderColor: COLORS.border },
  planName: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  planId: { fontSize: 11, color: COLORS.textMuted, marginBottom: 4 },
  fieldLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textSecondary, marginTop: 8, marginBottom: 4 },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 9, fontSize: 14, color: COLORS.textPrimary, backgroundColor: COLORS.white },
  multiline: { minHeight: 110, textAlignVertical: 'top', lineHeight: 22 },
  helper: { fontSize: 11, color: COLORS.textMuted, marginTop: 4 },
  activeRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 6 },
  saveBtn: { backgroundColor: COLORS.primary, borderRadius: 10, paddingVertical: 11, alignItems: 'center', marginTop: 10 },
  saveBtnText: { color: COLORS.white, fontWeight: '700', fontSize: 13 },
  reorderRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  reorderPos: { fontSize: 12, fontWeight: '800', color: COLORS.primary, backgroundColor: COLORS.primary + '15', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  reorderBtn: { width: 26, height: 26, borderRadius: 6, borderWidth: 1, borderColor: COLORS.border, alignItems: 'center', justifyContent: 'center', backgroundColor: COLORS.white },
  reorderBtnDisabled: { opacity: 0.4, backgroundColor: COLORS.background },
  reorderNumLabel: { fontSize: 11, fontWeight: '600', color: COLORS.textSecondary },
  reorderNumInput: { width: 54, borderWidth: 1, borderColor: COLORS.border, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 4, fontSize: 12, textAlign: 'center', color: COLORS.textPrimary, backgroundColor: COLORS.white },
});
