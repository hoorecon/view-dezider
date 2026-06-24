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

  const syncPlans = async () => {
    setSyncing(true);
    try {
      const res = await api.post('/admin/subscriptions/sync', {});
      setPlans(res.data?.plans || []);
      showAlert('Synced', `Pulled latest pricing & plan IDs from Razorpay (${res.data?.updated ?? 0} updated).`);
    } catch (e: any) {
      showAlert('Sync failed', e?.response?.data?.detail || 'Could not sync.');
    } finally {
      setSyncing(false);
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
                Razorpay so local records match the gateway. Set monthly credits and toggle a
                plan Active/Inactive (inactive plans are hidden from users), then Save.
              </Text>
            </View>

            {plans.map((p) => (
              <View key={p.plan_id} style={styles.card}>
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
});
