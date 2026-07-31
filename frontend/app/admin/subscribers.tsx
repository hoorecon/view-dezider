import React, { useEffect, useMemo, useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
  TextInput, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { safeBack } from '../../src/utils/navigation';

/**
 * /admin/subscribers — roster of every paying user.
 * Shows plan · tier · sub status · BOTH wallet balances (legacy credit_wallets
 * + primary ai_wallets) so admins can verify plan credits actually landed
 * where the user sees them (Profile → AI Credits).
 */

type Row = {
  user_id: string;
  email: string;
  name: string;
  user_type?: string;
  plan_id?: string;
  plan_name?: string;
  tier?: string;
  plan_price_inr?: number;
  plan_credits_per_month?: number;
  subscription_id?: string;
  subscription_status?: string;
  subscription_mode?: string;
  subscription_end?: string;
  legacy_credit_wallet?: number;
  ai_wallet_balance?: number;
  updated_at?: string;
};

const STATUS_TABS: Array<{ key: string; label: string }> = [
  { key: '',           label: 'All' },
  { key: 'active',     label: 'Active' },
  { key: 'manual',     label: 'One-time' },
  { key: 'cancelled',  label: 'Cancelled' },
  { key: 'pending',    label: 'Pending' },
];

export default function AdminSubscribersScreen() {
  const router = useRouter();
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [status, setStatus] = useState('');
  const [q, setQ] = useState('');

  const load = useCallback(async () => {
    try {
      const res = await api.get('/admin/subscribers', {
        params: status ? { status } : {},
      });
      setRows(res.data?.items || []);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [status]);

  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter(r =>
      (r.email || '').toLowerCase().includes(needle) ||
      (r.name || '').toLowerCase().includes(needle) ||
      (r.plan_name || '').toLowerCase().includes(needle) ||
      (r.tier || '').toLowerCase().includes(needle) ||
      (r.subscription_id || '').toLowerCase().includes(needle),
    );
  }, [rows, q]);

  const totalCredits = filtered.reduce((s, r) => s + (r.ai_wallet_balance || 0), 0);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
          <Ionicons name="arrow-back" size={24} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Subscribers</Text>
        <TouchableOpacity onPress={() => { setRefreshing(true); load(); }}>
          <Ionicons name="refresh" size={20} color={COLORS.primary} />
        </TouchableOpacity>
      </View>

      <View style={styles.filterRow}>
        {STATUS_TABS.map(t => (
          <TouchableOpacity
            key={t.key || 'all'}
            onPress={() => setStatus(t.key)}
            style={[styles.chip, status === t.key && styles.chipOn]}
          >
            <Text style={[styles.chipTxt, status === t.key && styles.chipTxtOn]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <View style={styles.searchWrap}>
        <Ionicons name="search" size={16} color={COLORS.textMuted} />
        <TextInput
          value={q}
          onChangeText={setQ}
          placeholder="Search email, name, plan, sub_id…"
          placeholderTextColor={COLORS.textMuted}
          style={styles.searchInput}
        />
      </View>

      {loading ? (
        <View style={styles.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>
      ) : (
        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}
        >
          <View style={styles.summary}>
            <Text style={styles.summaryTxt}>
              {filtered.length} subscriber{filtered.length === 1 ? '' : 's'}
              {'  ·  '}
              Σ AI wallet balance: <Text style={{ fontWeight: '700' }}>{Math.round(totalCredits).toLocaleString()}</Text> credits
            </Text>
          </View>

          {filtered.length === 0 ? (
            <View style={styles.empty}>
              <Ionicons name="people-outline" size={36} color={COLORS.textMuted} />
              <Text style={styles.emptyTxt}>No subscribers match this filter yet.</Text>
            </View>
          ) : filtered.map(r => (
            <View key={r.user_id + (r.subscription_id || '')} style={styles.card}>
              <View style={styles.cardTop}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.name} numberOfLines={1}>{r.name || r.email || r.user_id}</Text>
                  <Text style={styles.email} numberOfLines={1}>{r.email}</Text>
                </View>
                <View style={[styles.badge, badgeStyle(r.subscription_status)]}>
                  <Text style={styles.badgeTxt}>{(r.subscription_status || 'none').toUpperCase()}</Text>
                </View>
              </View>

              <View style={styles.metaRow}>
                <Text style={styles.metaK}>Plan</Text>
                <Text style={styles.metaV} numberOfLines={1}>
                  {r.plan_name || r.plan_id || '—'}{r.tier ? `  ·  ${r.tier}` : ''}
                  {r.plan_price_inr ? `  ·  ₹${r.plan_price_inr}` : ''}
                  {r.subscription_mode ? `  ·  ${r.subscription_mode}` : ''}
                </Text>
              </View>

              <View style={styles.walletRow}>
                <View style={styles.walletBox}>
                  <Text style={styles.walletK}>AI wallet (Profile)</Text>
                  <Text style={[styles.walletV, { color: '#7C3AED' }]}>
                    {Math.round(r.ai_wallet_balance || 0).toLocaleString()}
                  </Text>
                  <Text style={styles.walletSub}>ai_wallets.balance</Text>
                </View>
                <View style={styles.walletBox}>
                  <Text style={styles.walletK}>Legacy wallet</Text>
                  <Text style={styles.walletV}>{(r.legacy_credit_wallet || 0).toLocaleString()}</Text>
                  <Text style={styles.walletSub}>credit_wallets.credits</Text>
                </View>
                <View style={styles.walletBox}>
                  <Text style={styles.walletK}>Plan grant</Text>
                  <Text style={styles.walletV}>{(r.plan_credits_per_month || 0).toLocaleString()}</Text>
                  <Text style={styles.walletSub}>/mo</Text>
                </View>
              </View>

              {r.subscription_end ? (
                <Text style={styles.footer}>Ends: {new Date(r.subscription_end).toLocaleDateString()}</Text>
              ) : null}
              {r.subscription_id ? (
                <Text style={styles.footer} numberOfLines={1}>sub: {r.subscription_id}</Text>
              ) : null}
            </View>
          ))}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

function badgeStyle(status?: string) {
  switch ((status || '').toLowerCase()) {
    case 'active':    return { backgroundColor: '#DCFCE7', borderColor: '#16A34A' };
    case 'manual':    return { backgroundColor: '#FEF3C7', borderColor: '#D97706' };
    case 'cancelled': return { backgroundColor: '#FEE2E2', borderColor: '#DC2626' };
    case 'pending':   return { backgroundColor: '#FEF9C3', borderColor: '#CA8A04' };
    default:          return { backgroundColor: '#F3F4F6', borderColor: '#9CA3AF' };
  }
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
  filterRow: { flexDirection: 'row', gap: 6, paddingHorizontal: 12, paddingVertical: 8, backgroundColor: COLORS.surface },
  chip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 999, backgroundColor: '#F3F4F6' },
  chipOn: { backgroundColor: COLORS.primary },
  chipTxt: { fontSize: 12, fontWeight: '600', color: COLORS.textSecondary },
  chipTxtOn: { color: '#FFF' },
  searchWrap: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    marginHorizontal: 12, marginBottom: 8,
    paddingHorizontal: 10, paddingVertical: 8,
    backgroundColor: COLORS.surface, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border,
  },
  searchInput: { flex: 1, fontSize: 14, color: COLORS.textPrimary, paddingVertical: 0 },
  scroll: { paddingHorizontal: 12, paddingBottom: 24 },
  summary: { paddingVertical: 6, paddingHorizontal: 4 },
  summaryTxt: { fontSize: 12, color: COLORS.textSecondary },
  empty: { alignItems: 'center', paddingVertical: 48, gap: 8 },
  emptyTxt: { color: COLORS.textMuted, fontSize: 13 },
  card: { backgroundColor: COLORS.surface, borderRadius: 12, padding: 12, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  cardTop: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  name: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  email: { fontSize: 12, color: COLORS.textMuted },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, borderWidth: 1 },
  badgeTxt: { fontSize: 10, fontWeight: '800', color: COLORS.textPrimary },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 6 },
  metaK: { fontSize: 11, fontWeight: '700', color: COLORS.textMuted, width: 46 },
  metaV: { flex: 1, fontSize: 12, color: COLORS.textPrimary },
  walletRow: { flexDirection: 'row', gap: 6, marginTop: 8 },
  walletBox: { flex: 1, backgroundColor: '#FAFAFA', borderRadius: 8, padding: 8, borderWidth: 1, borderColor: COLORS.border },
  walletK: { fontSize: 10, fontWeight: '700', color: COLORS.textMuted },
  walletV: { fontSize: 16, fontWeight: '800', color: COLORS.textPrimary, marginTop: 2 },
  walletSub: { fontSize: 9, color: COLORS.textMuted, marginTop: 1 },
  footer: { fontSize: 10, color: COLORS.textMuted, marginTop: 6 },
});
