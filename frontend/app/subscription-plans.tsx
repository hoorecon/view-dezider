import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator, TextInput, Switch, Platform, KeyboardAvoidingView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import * as WebBrowser from 'expo-web-browser';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import { COLORS } from '../src/constants/colors';
import api from '../src/utils/api';
import { showAlert } from '../src/utils/alert';
import { useAuthStore } from '../src/store/authStore';
import { safeBack } from '../src/utils/navigation';

const BASE_URL = (Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL as string) || process.env.EXPO_PUBLIC_BACKEND_URL || '';

const TIER_COLORS: Record<string, string[]> = {
  basic: ['#5E35B1', '#7E57C2'],
  pro: ['#8E24AA', '#5E35B1'],
  premium: ['#D81B60', '#8E24AA'],
};

const STATUS_LABEL: Record<string, { label: string; color: string }> = {
  active: { label: 'Active', color: COLORS.success },
  manual: { label: 'Active (manual renewal)', color: COLORS.success },
  pending: { label: 'Renewal failed — retrying', color: COLORS.warning },
  halted: { label: 'Paused (payment failed)', color: COLORS.error },
  cancelled: { label: 'Cancelling at period end', color: COLORS.warning },
  none: { label: 'No active plan', color: COLORS.textMuted },
};

export default function SubscriptionPlansScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const role = (user?.role || '').toLowerCase();
  const isSuperAdmin = role === 'super_admin';

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [plans, setPlans] = useState<any[]>([]);
  const [me, setMe] = useState<any>(null);
  const [adminPlans, setAdminPlans] = useState<any[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  const fetchData = async () => {
    try {
      const [pRes, mRes] = await Promise.all([
        api.get('/subscriptions/plans'),
        api.get('/subscriptions/me'),
      ]);
      setPlans(pRes.data?.plans || []);
      setMe(mRes.data);
      if (isSuperAdmin) {
        try {
          const aRes = await api.get('/admin/subscriptions/plans');
          setAdminPlans(aRes.data?.plans || []);
        } catch { /* ignore */ }
      }
    } catch { /* silent */ } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useFocusEffect(useCallback(() => { fetchData(); }, []));

  const openCheckout = async (data: any) => {
    const token = (await AsyncStorage.getItem('session_token')) || '';
    if (data.mode === 'recurring' && data.short_url) {
      await WebBrowser.openBrowserAsync(data.short_url);
    } else if (data.mode === 'onetime' && data.order_id) {
      const params = new URLSearchParams({
        order_id: data.order_id, key_id: data.key_id, amount: String(data.amount),
        token, name: data.user_name || '', email: data.user_email || '',
      });
      await WebBrowser.openBrowserAsync(`${BASE_URL}/api/subscriptions/checkout?${params.toString()}`);
    }
    await fetchData();
  };

  const subscribe = async (plan: any) => {
    setBusyId(plan.plan_id);
    try {
      const res = await api.post('/subscriptions/create', { plan_id: plan.plan_id });
      await openCheckout(res.data);
    } catch (e: any) {
      showAlert('Subscription error', e?.response?.data?.detail || 'Could not start subscription.');
    } finally {
      setBusyId(null);
    }
  };

  const payOnce = async (plan: any) => {
    setBusyId(plan.plan_id + '_once');
    try {
      const res = await api.post('/subscriptions/create-onetime', { plan_id: plan.plan_id });
      await openCheckout(res.data);
    } catch (e: any) {
      showAlert('Payment error', e?.response?.data?.detail || 'Could not start payment.');
    } finally {
      setBusyId(null);
    }
  };

  const cancel = () => {
    showAlert('Cancel subscription?', 'Your plan stays active until the end of the current period, then moves to Free.', [
      { text: 'Keep plan', style: 'cancel' },
      {
        text: 'Cancel plan', style: 'destructive', onPress: async () => {
          try {
            await api.post('/subscriptions/cancel', {});
            showAlert('Done', 'Your subscription will not renew.');
            fetchData();
          } catch (e: any) {
            showAlert('Error', e?.response?.data?.detail || 'Could not cancel.');
          }
        },
      },
    ]);
  };

  const saveAdminPlan = async (p: any) => {
    setSavingId(p.plan_id);
    try {
      const res = await api.put(`/admin/subscriptions/plans/${p.plan_id}`, {
        credits_per_month: Number(p.credits_per_month),
        active: !!p.active,
        name: p.name,
      });
      setAdminPlans(prev => prev.map(x => x.plan_id === p.plan_id ? res.data : x));
      showAlert('Saved', `${res.data.name} updated.`);
      fetchData();
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || 'Could not update plan.');
    } finally {
      setSavingId(null);
    }
  };

  const syncPlans = async () => {
    setSyncing(true);
    try {
      const res = await api.post('/admin/subscriptions/sync', {});
      setAdminPlans(res.data?.plans || []);
      showAlert('Synced', `Pulled latest pricing from Razorpay (${res.data?.updated ?? 0} updated).`);
      fetchData();
    } catch (e: any) {
      showAlert('Sync failed', e?.response?.data?.detail || 'Could not sync.');
    } finally {
      setSyncing(false);
    }
  };

  const status = me?.status || 'none';
  const statusMeta = STATUS_LABEL[status] || STATUS_LABEL.none;
  const hasActive = ['active', 'manual', 'pending', 'cancelled'].includes(status);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={{ width: 24 }} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Ionicons name="arrow-back" size={24} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Subscription</Text>
        <View style={{ width: 24 }} />
      </View>

      {loading ? (
        <View style={styles.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>
      ) : (
        <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <ScrollView contentContainerStyle={styles.scroll}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchData(); }} />}>

            {/* Current status */}
            <View style={[styles.statusCard, { borderLeftColor: statusMeta.color }]}>
              <View style={{ flex: 1 }}>
                <Text style={styles.statusLabel}>Current status</Text>
                <Text style={[styles.statusValue, { color: statusMeta.color }]}>{statusMeta.label}</Text>
                {me?.subscription_end && hasActive && (
                  <Text style={styles.statusSub}>
                    {status === 'cancelled' ? 'Access until' : 'Renews/expires on'} {new Date(me.subscription_end).toLocaleDateString()}
                  </Text>
                )}
                {status === 'pending' && (
                  <Text style={styles.statusWarn}>We&apos;ll retry payment within 48h. Update your method to avoid downgrade.</Text>
                )}
              </View>
              {status === 'active' && me?.mode === 'recurring' && (
                <TouchableOpacity onPress={cancel} style={styles.cancelBtn}>
                  <Text style={styles.cancelBtnText}>Cancel</Text>
                </TouchableOpacity>
              )}
            </View>

            <Text style={styles.sectionTitle}>Monthly plans</Text>
            <Text style={styles.sectionHint}>Auto-renews each month. You can cancel anytime.</Text>

            {plans.map((p) => {
              const colors = TIER_COLORS[p.tier] || TIER_COLORS.basic;
              const isCurrent = me?.subscription_plan_id === p.plan_id && hasActive;
              return (
                <View key={p.plan_id} style={styles.planCard}>
                  <LinearGradient colors={colors} start={{ x: 0, y: 0 }} end={{ x: 1, y: 0 }} style={styles.planHeader}>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.planName}>{p.name}</Text>
                      <Text style={styles.planCredits}>{p.credits_per_month.toLocaleString()} credits / month</Text>
                    </View>
                    <View style={{ alignItems: 'flex-end' }}>
                      <Text style={styles.planPrice}>₹{p.price_inr.toLocaleString()}</Text>
                      <Text style={styles.planPer}>/month</Text>
                    </View>
                  </LinearGradient>
                  <View style={styles.planBody}>
                    {(p.features || []).map((f: string, i: number) => (
                      <View key={i} style={styles.featureRow}>
                        <Ionicons name="checkmark-circle" size={16} color={COLORS.success} />
                        <Text style={styles.featureText}>{f}</Text>
                      </View>
                    ))}
                    {isCurrent ? (
                      <View style={styles.currentPill}>
                        <Ionicons name="checkmark-done" size={16} color={COLORS.success} />
                        <Text style={styles.currentPillText}>Your current plan</Text>
                      </View>
                    ) : (
                      <>
                        <TouchableOpacity style={[styles.subBtn, { backgroundColor: colors[0] }]} onPress={() => subscribe(p)} disabled={busyId !== null}>
                          {busyId === p.plan_id ? <ActivityIndicator color={COLORS.white} />
                            : <Text style={styles.subBtnText}>Subscribe — auto-renew</Text>}
                        </TouchableOpacity>
                        <TouchableOpacity style={styles.onceBtn} onPress={() => payOnce(p)} disabled={busyId !== null}>
                          {busyId === p.plan_id + '_once' ? <ActivityIndicator color={colors[0]} size="small" />
                            : <Text style={[styles.onceBtnText, { color: colors[0] }]}>Pay once (1 month, no auto-renew)</Text>}
                        </TouchableOpacity>
                      </>
                    )}
                  </View>
                </View>
              );
            })}

            {/* Admin: plan config */}
            {isSuperAdmin && adminPlans.length > 0 && (
              <View style={styles.adminCard}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <Text style={styles.sectionTitle}>Admin · Plan config</Text>
                  <TouchableOpacity style={styles.syncBtn} onPress={syncPlans} disabled={syncing}>
                    {syncing ? <ActivityIndicator size="small" color={COLORS.primary} />
                      : <><Ionicons name="sync" size={14} color={COLORS.primary} /><Text style={styles.syncBtnText}>Sync</Text></>}
                  </TouchableOpacity>
                </View>
                {adminPlans.map((p) => (
                  <View key={p.plan_id} style={styles.adminRow}>
                    <Text style={styles.adminPlanName}>{p.name} · ₹{p.price_inr}</Text>
                    <Text style={styles.adminPlanId}>{p.plan_id}</Text>
                    <Text style={styles.fieldLabel}>Credits / month</Text>
                    <TextInput
                      style={styles.input} keyboardType="numeric"
                      value={String(p.credits_per_month)}
                      onChangeText={(t) => setAdminPlans(prev => prev.map(x => x.plan_id === p.plan_id ? { ...x, credits_per_month: t } : x))}
                    />
                    <View style={styles.activeRow}>
                      <Text style={styles.fieldLabel}>Active</Text>
                      <Switch
                        value={!!p.active}
                        onValueChange={(v) => setAdminPlans(prev => prev.map(x => x.plan_id === p.plan_id ? { ...x, active: v } : x))}
                        trackColor={{ true: COLORS.primary }}
                      />
                    </View>
                    <TouchableOpacity style={styles.saveBtn} onPress={() => saveAdminPlan(p)} disabled={savingId === p.plan_id}>
                      {savingId === p.plan_id ? <ActivityIndicator color={COLORS.white} size="small" />
                        : <Text style={styles.saveBtnText}>Save</Text>}
                    </TouchableOpacity>
                  </View>
                ))}
              </View>
            )}
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
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 12, backgroundColor: COLORS.surface,
    borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  headerTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  scroll: { padding: 16 },

  statusCard: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.surface,
    borderRadius: 12, padding: 14, borderLeftWidth: 4, borderWidth: 1, borderColor: COLORS.border, marginBottom: 18,
  },
  statusLabel: { fontSize: 12, color: COLORS.textMuted },
  statusValue: { fontSize: 16, fontWeight: '800', marginTop: 2 },
  statusSub: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },
  statusWarn: { fontSize: 12, color: COLORS.warning, marginTop: 4 },
  cancelBtn: { borderWidth: 1, borderColor: COLORS.error, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 6 },
  cancelBtnText: { color: COLORS.error, fontWeight: '700', fontSize: 12 },

  sectionTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  sectionHint: { fontSize: 12, color: COLORS.textMuted, marginBottom: 12, marginTop: 2 },

  planCard: { backgroundColor: COLORS.surface, borderRadius: 16, marginBottom: 16, overflow: 'hidden', borderWidth: 1, borderColor: COLORS.border },
  planHeader: { flexDirection: 'row', alignItems: 'center', padding: 16 },
  planName: { color: COLORS.white, fontSize: 18, fontWeight: '800' },
  planCredits: { color: COLORS.white, opacity: 0.9, fontSize: 12, marginTop: 2 },
  planPrice: { color: COLORS.white, fontSize: 22, fontWeight: '800' },
  planPer: { color: COLORS.white, opacity: 0.9, fontSize: 11 },
  planBody: { padding: 16 },
  featureRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  featureText: { flex: 1, fontSize: 13, color: COLORS.textSecondary },
  subBtn: { borderRadius: 12, paddingVertical: 12, alignItems: 'center', marginTop: 10 },
  subBtnText: { color: COLORS.white, fontWeight: '800', fontSize: 14 },
  onceBtn: { paddingVertical: 10, alignItems: 'center', marginTop: 6 },
  onceBtnText: { fontWeight: '600', fontSize: 12.5 },
  currentPill: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 10, backgroundColor: COLORS.success + '15', paddingVertical: 10, borderRadius: 10 },
  currentPillText: { color: COLORS.success, fontWeight: '700', fontSize: 13 },

  adminCard: { backgroundColor: COLORS.surface, borderRadius: 14, padding: 16, marginTop: 8, borderWidth: 1, borderColor: COLORS.border },
  syncBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, borderWidth: 1, borderColor: COLORS.primary, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 5 },
  syncBtnText: { color: COLORS.primary, fontWeight: '700', fontSize: 12 },
  adminRow: { borderTopWidth: 1, borderTopColor: COLORS.divider, paddingTop: 12, marginTop: 12 },
  adminPlanName: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  adminPlanId: { fontSize: 11, color: COLORS.textMuted, marginBottom: 4 },
  fieldLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textSecondary, marginTop: 8, marginBottom: 4 },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 9, fontSize: 14, color: COLORS.textPrimary, backgroundColor: COLORS.white },
  activeRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 6 },
  saveBtn: { backgroundColor: COLORS.primary, borderRadius: 10, paddingVertical: 10, alignItems: 'center', marginTop: 10 },
  saveBtnText: { color: COLORS.white, fontWeight: '700', fontSize: 13 },
});
