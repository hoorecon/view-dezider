import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator, TextInput, KeyboardAvoidingView, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../src/constants/colors';
import api from '../src/utils/api';
import { showAlert } from '../src/utils/alert';
import { useAuthStore } from '../src/store/authStore';
import { useAiWalletStore } from '../src/store/aiWalletStore';

const KIND_META: Record<string, { icon: any; color: string; label: string }> = {
  seed: { icon: 'gift-outline', color: COLORS.success, label: 'Starting balance' },
  grant: { icon: 'add-circle-outline', color: COLORS.success, label: 'Credited' },
  set: { icon: 'create-outline', color: COLORS.info, label: 'Adjusted' },
  debit: { icon: 'sparkles-outline', color: COLORS.error, label: 'AI usage' },
  refill: { icon: 'card-outline', color: COLORS.success, label: 'Refill' },
};

export default function AiWalletScreen() {
  const router = useRouter();
  const { user } = useAuthStore();
  const refreshBadge = useAiWalletStore((s) => s.refresh);

  const role = (user?.role || '').toLowerCase();
  const isSuperAdmin = role === 'super_admin';
  const isAdmin = isSuperAdmin || role === 'admin' || role === 'co_admin' || !!user?.is_admin;

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [wallet, setWallet] = useState<any>(null);
  const [ledger, setLedger] = useState<any[]>([]);

  // admin config
  const [cfg, setCfg] = useState<any>(null);
  const [savingCfg, setSavingCfg] = useState(false);
  // admin grant
  const [grantEmail, setGrantEmail] = useState('');
  const [grantAmount, setGrantAmount] = useState('');
  const [granting, setGranting] = useState(false);

  const fetchData = async () => {
    try {
      const [wRes, lRes] = await Promise.all([
        api.get('/ai-wallet'),
        api.get('/ai-wallet/ledger?limit=40'),
      ]);
      setWallet(wRes.data);
      setLedger(lRes.data?.items || []);
      if (isSuperAdmin) {
        try {
          const cRes = await api.get('/admin/ai-wallet/config');
          setCfg(cRes.data);
        } catch { /* ignore */ }
      }
      refreshBadge();
    } catch (err) {
      // silent
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useFocusEffect(useCallback(() => { fetchData(); }, []));

  const balance = Number(wallet?.balance ?? 0);
  const tpc = Number(wallet?.tokens_per_credit ?? 100);
  const empty = balance <= 0;
  const low = balance > 0 && balance < 3;

  const saveConfig = async () => {
    if (!cfg) return;
    setSavingCfg(true);
    try {
      const body = {
        default_user_credits: Number(cfg.default_user_credits),
        default_admin_credits: Number(cfg.default_admin_credits),
        tokens_per_credit: Number(cfg.tokens_per_credit),
      };
      const res = await api.put('/admin/ai-wallet/config', body);
      setCfg(res.data);
      showAlert('Saved', 'AI wallet defaults updated.');
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || 'Could not update config.');
    } finally {
      setSavingCfg(false);
    }
  };

  const grant = async () => {
    const amt = parseFloat(grantAmount);
    if (!grantEmail.trim() || isNaN(amt)) {
      showAlert('Missing info', 'Enter a user email and a numeric credit amount.');
      return;
    }
    setGranting(true);
    try {
      const res = await api.post('/admin/ai-wallet/grant', {
        email: grantEmail.trim(), credits: amt, mode: 'add',
      });
      showAlert('Credits granted', `New balance: ${res.data?.balance} credits.`);
      setGrantEmail('');
      setGrantAmount('');
      fetchData();
    } catch (e: any) {
      showAlert('Grant failed', e?.response?.data?.detail || 'Could not grant credits.');
    } finally {
      setGranting(false);
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Ionicons name="arrow-back" size={24} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>AI Wallet</Text>
        <View style={{ width: 24 }} />
      </View>

      {loading ? (
        <View style={styles.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>
      ) : (
        <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <ScrollView
            contentContainerStyle={styles.scroll}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchData(); }} />}
          >
            {/* Balance card */}
            <LinearGradient
              colors={empty ? ['#EF4444', '#B91C1C'] : low ? ['#F59E0B', '#D97706'] : ['#8E24AA', '#5E35B1']}
              start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }}
              style={styles.balanceCard}
            >
              <View style={styles.balanceTop}>
                <Ionicons name="sparkles" size={20} color={COLORS.white} />
                <Text style={styles.balanceLabel}>AI Credits</Text>
              </View>
              <Text style={styles.balanceValue}>{balance.toFixed(2)}</Text>
              <Text style={styles.balanceSub}>
                Used for AI Assist in My Dezider & Pros &amp; Cons. {tpc} tokens = 1 credit.
              </Text>
              {empty && (
                <View style={styles.outPill}>
                  <Ionicons name="alert-circle" size={14} color={COLORS.white} />
                  <Text style={styles.outPillText}>Out of credits — top up to keep using AI Assist</Text>
                </View>
              )}
            </LinearGradient>

            {/* How it works / refill note */}
            <View style={styles.infoCard}>
              <View style={styles.infoRow}>
                <Ionicons name="information-circle-outline" size={18} color={COLORS.primary} />
                <Text style={styles.infoTitle}>How AI credits work</Text>
              </View>
              <Text style={styles.infoText}>
                AI Assist runs on Gemini first and only charges for the tokens it actually uses
                ({tpc} tokens = 1 credit). When your balance reaches zero, AI Assist is paused until you refill.
              </Text>
              <View style={styles.refillNote}>
                <Ionicons name="card-outline" size={16} color={COLORS.textSecondary} />
                <Text style={styles.refillNoteText}>
                  Self-serve refill (Razorpay) is coming soon. For now, ask an admin to add credits.
                </Text>
              </View>
            </View>

            {/* Admin: config (super admin only) */}
            {isSuperAdmin && cfg && (
              <View style={styles.adminCard}>
                <Text style={styles.sectionTitle}>Default starting balances</Text>
                <Text style={styles.fieldHint}>New users & admins are seeded with these credits on first AI use.</Text>

                <Text style={styles.fieldLabel}>New user credits</Text>
                <TextInput
                  style={styles.input}
                  keyboardType="numeric"
                  value={String(cfg.default_user_credits)}
                  onChangeText={(t) => setCfg({ ...cfg, default_user_credits: t })}
                  placeholder="20"
                />
                <Text style={styles.fieldLabel}>New admin credits</Text>
                <TextInput
                  style={styles.input}
                  keyboardType="numeric"
                  value={String(cfg.default_admin_credits)}
                  onChangeText={(t) => setCfg({ ...cfg, default_admin_credits: t })}
                  placeholder="200"
                />
                <Text style={styles.fieldLabel}>Tokens per credit</Text>
                <TextInput
                  style={styles.input}
                  keyboardType="numeric"
                  value={String(cfg.tokens_per_credit)}
                  onChangeText={(t) => setCfg({ ...cfg, tokens_per_credit: t })}
                  placeholder="100"
                />
                <TouchableOpacity style={styles.primaryBtn} onPress={saveConfig} disabled={savingCfg}>
                  {savingCfg ? <ActivityIndicator color={COLORS.white} /> : <Text style={styles.primaryBtnText}>Save defaults</Text>}
                </TouchableOpacity>
              </View>
            )}

            {/* Admin: grant credits */}
            {isAdmin && (
              <View style={styles.adminCard}>
                <Text style={styles.sectionTitle}>Grant credits to a user</Text>
                <Text style={styles.fieldLabel}>User email</Text>
                <TextInput
                  style={styles.input}
                  autoCapitalize="none"
                  keyboardType="email-address"
                  value={grantEmail}
                  onChangeText={setGrantEmail}
                  placeholder="user@example.com"
                />
                <Text style={styles.fieldLabel}>Credits to add</Text>
                <TextInput
                  style={styles.input}
                  keyboardType="numeric"
                  value={grantAmount}
                  onChangeText={setGrantAmount}
                  placeholder="50"
                />
                <TouchableOpacity style={styles.primaryBtn} onPress={grant} disabled={granting}>
                  {granting ? <ActivityIndicator color={COLORS.white} /> : <Text style={styles.primaryBtnText}>Grant credits</Text>}
                </TouchableOpacity>
              </View>
            )}

            {/* Ledger */}
            <Text style={styles.sectionTitle}>Recent activity</Text>
            {ledger.length === 0 ? (
              <View style={styles.emptyLedger}>
                <Ionicons name="receipt-outline" size={28} color={COLORS.textMuted} />
                <Text style={styles.emptyLedgerText}>No AI credit activity yet.</Text>
              </View>
            ) : (
              ledger.map((item, idx) => {
                const meta = KIND_META[item.kind] || KIND_META.debit;
                const delta = Number(item.delta || 0);
                const positive = delta >= 0;
                return (
                  <View key={item.id || idx} style={styles.ledgerRow}>
                    <View style={[styles.ledgerIcon, { backgroundColor: meta.color + '1A' }]}>
                      <Ionicons name={meta.icon} size={16} color={meta.color} />
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.ledgerLabel}>
                        {item.feature ? `${meta.label} · ${item.feature}` : (item.note || meta.label)}
                      </Text>
                      <Text style={styles.ledgerMeta}>
                        {item.provider ? `${item.provider} · ` : ''}{item.tokens ? `${item.tokens} tokens · ` : ''}
                        {item.created_at ? new Date(item.created_at).toLocaleString() : ''}
                      </Text>
                    </View>
                    <Text style={[styles.ledgerDelta, { color: positive ? COLORS.success : COLORS.error }]}>
                      {positive ? '+' : ''}{delta.toFixed(2)}
                    </Text>
                  </View>
                );
              })
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
  backBtn: { width: 24 },
  headerTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  scroll: { padding: 16 },

  balanceCard: { borderRadius: 18, padding: 20, marginBottom: 16 },
  balanceTop: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  balanceLabel: { color: COLORS.white, fontSize: 14, fontWeight: '600', opacity: 0.95 },
  balanceValue: { color: COLORS.white, fontSize: 44, fontWeight: '800', marginTop: 6 },
  balanceSub: { color: COLORS.white, opacity: 0.9, fontSize: 12, marginTop: 4 },
  outPill: {
    flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 12,
    backgroundColor: 'rgba(0,0,0,0.18)', paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999, alignSelf: 'flex-start',
  },
  outPillText: { color: COLORS.white, fontSize: 11, fontWeight: '600' },

  infoCard: { backgroundColor: COLORS.surface, borderRadius: 14, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: COLORS.border },
  infoRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  infoTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  infoText: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 19 },
  refillNote: { flexDirection: 'row', alignItems: 'flex-start', gap: 6, marginTop: 10, backgroundColor: COLORS.divider, padding: 10, borderRadius: 10 },
  refillNoteText: { flex: 1, fontSize: 12, color: COLORS.textSecondary, lineHeight: 17 },

  adminCard: { backgroundColor: COLORS.surface, borderRadius: 14, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: COLORS.border },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },
  fieldHint: { fontSize: 12, color: COLORS.textMuted, marginBottom: 8 },
  fieldLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textSecondary, marginTop: 10, marginBottom: 4 },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: COLORS.textPrimary, backgroundColor: COLORS.white },
  primaryBtn: { backgroundColor: COLORS.primary, borderRadius: 12, paddingVertical: 12, alignItems: 'center', marginTop: 14 },
  primaryBtnText: { color: COLORS.white, fontWeight: '700', fontSize: 14 },

  emptyLedger: { alignItems: 'center', paddingVertical: 24, gap: 8 },
  emptyLedgerText: { fontSize: 13, color: COLORS.textMuted },
  ledgerRow: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.surface, borderRadius: 12, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border },
  ledgerIcon: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  ledgerLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  ledgerMeta: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  ledgerDelta: { fontSize: 14, fontWeight: '700' },
});
