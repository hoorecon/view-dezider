import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator, TextInput, KeyboardAvoidingView, Platform, Switch,
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
import { useAiWalletStore } from '../src/store/aiWalletStore';

const BASE_URL = (Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL as string) || process.env.EXPO_PUBLIC_BACKEND_URL || '';

const KIND_META: Record<string, { icon: any; color: string; label: string }> = {
  seed: { icon: 'gift-outline', color: COLORS.success, label: 'Starting balance' },
  grant: { icon: 'add-circle-outline', color: COLORS.success, label: 'Credited' },
  set: { icon: 'create-outline', color: COLORS.info, label: 'Adjusted' },
  debit: { icon: 'sparkles-outline', color: COLORS.error, label: 'AI usage' },
  refill: { icon: 'card-outline', color: COLORS.success, label: 'Refill' },
};

export default function AiWalletScreen() {
  const router = useRouter();
  const refreshBadge = useAiWalletStore((s) => s.refresh);

  // /ai-wallet is strictly the END-USER wallet view. All Admin controls
  // (defaults, pricing, routing, grant-credits, ledger search) live in
  // /admin/ai-wallet-config and MUST NOT leak here — even when an admin
  // happens to be the logged-in user.

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [wallet, setWallet] = useState<any>(null);
  const [ledger, setLedger] = useState<any[]>([]);

  // refill
  const [packsInfo, setPacksInfo] = useState<any>(null);
  const [customCredits, setCustomCredits] = useState('');
  const [customQuote, setCustomQuote] = useState<any>(null);
  const [quoting, setQuoting] = useState(false);
  const [buyingId, setBuyingId] = useState<string | null>(null);

  // OpenAI free-tier (data-sharing) consent. `feature_enabled` is the
  // ADMIN master switch — when false the entire opt-in UI is hidden,
  // regardless of what the user has previously chosen.
  const [consent, setConsent] = useState<{
    allow_openai: boolean; mode: string;
    openai_free_tier?: boolean; openai_available: boolean;
    feature_enabled?: boolean;
  } | null>(null);
  const [savingConsent, setSavingConsent] = useState(false);

  const saveConsent = async (next: { allow_openai: boolean; mode: string; openai_free_tier?: boolean }) => {
    setConsent((c) => (c ? { ...c, ...next } : c));
    setSavingConsent(true);
    try {
      const res = await api.put('/ai-wallet/provider-consent', next);
      setConsent(res.data);
    } catch (e: any) {
      showAlert('Could not save', e?.response?.data?.detail || 'Please try again.');
    } finally {
      setSavingConsent(false);
    }
  };

  const fetchData = async () => {
    try {
      const [wRes, lRes, pRes] = await Promise.all([
        api.get('/ai-wallet'),
        api.get('/ai-wallet/ledger?limit=40'),
        api.get('/ai-wallet/packs'),
      ]);
      setWallet(wRes.data);
      setLedger(lRes.data?.items || []);
      setPacksInfo(pRes.data);
      try {
        const ccRes = await api.get('/ai-wallet/provider-consent');
        setConsent(ccRes.data);
      } catch { /* ignore */ }
      refreshBadge();
    } catch (err) {
      // silent
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useFocusEffect(useCallback(() => { fetchData(); }, []));

  const getCustomQuote = async () => {
    const c = parseInt(customCredits, 10);
    if (isNaN(c) || c <= 0) { showAlert('Enter credits', 'Type how many credits you want to buy.'); return; }
    setQuoting(true);
    setCustomQuote(null);
    try {
      const res = await api.post('/ai-wallet/refill/quote', { credits: c });
      setCustomQuote(res.data);
    } catch (e: any) {
      showAlert('Quote failed', e?.response?.data?.detail || 'Could not price that amount.');
    } finally {
      setQuoting(false);
    }
  };

  const buy = async (opts: { pack_id?: string; credits?: number }, buttonId: string) => {
    setBuyingId(buttonId);
    try {
      const res = await api.post('/ai-wallet/refill/order', opts);
      const o = res.data;
      const token = (await AsyncStorage.getItem('session_token')) || '';
      const params = new URLSearchParams({
        order_id: o.order_id,
        key_id: o.key_id,
        amount: String(o.amount),
        token,
        name: o.user_name || '',
        email: o.user_email || '',
      });
      const url = `${BASE_URL}/api/ai-wallet/refill/checkout?${params.toString()}`;
      await WebBrowser.openBrowserAsync(url);
      // user returned from checkout — refresh balance/ledger
      await fetchData();
    } catch (e: any) {
      showAlert('Payment error', e?.response?.data?.detail || 'Could not start checkout. Please try again.');
    } finally {
      setBuyingId(null);
    }
  };

  const balance = Number(wallet?.balance ?? 0);
  const tpc = Number(wallet?.tokens_per_credit ?? 100);
  const empty = balance <= 0;
  const low = balance > 0 && balance < 3;

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
                AI Assist tries free providers first (Gemini → Groq), then your AI wallet
                ({tpc} tokens = 1 credit). When all free quotas and your balance are exhausted, AI is paused until you refill.
              </Text>
            </View>

            {/* OpenAI free-tier (data-sharing) consent.
                Visibility rules:
                  • Hidden if server has no OPENAI_API_KEY (`openai_available=false`)
                  • Hidden if admin has disabled the feature (`feature_enabled=false`)

                LAYOUT (swapped per user feedback):
                  ┌────────────────────────────────────────────┐
                  │ 1. PRIMARY (FREE) — route OpenAI first,    │
                  │    skip wallet entirely. Recommended.      │
                  │    [Switch]                                │
                  ├────────────────────────────────────────────┤
                  │ 2. FALLBACK — allow OpenAI as fallback     │
                  │    when free Gemini/Groq quotas exhaust.   │
                  │    [Switch] [Ask/Always chips]             │
                  └────────────────────────────────────────────┘

                Note: PRIMARY implies FALLBACK. Toggling PRIMARY ON
                automatically sets allow_openai=true; toggling PRIMARY
                OFF leaves allow_openai untouched. */}
            {consent?.openai_available && consent?.feature_enabled !== false && (
              <View style={styles.infoCard} testID="openai-consent-card">
                {/* 1. PRIMARY (FREE FOR ME) — first, recommended */}
                <View style={styles.consentRow} testID="openai-free-tier-card">
                  <View style={{ flex: 1, paddingRight: 12 }}>
                    <Text style={styles.infoTitle}>Route OpenAI first — free for me</Text>
                    <Text style={[styles.infoText, { marginTop: 4 }]}>
                      When ON, your AI calls run through our shared{' '}
                      <Text style={{ fontWeight: '700' }}>OpenAI organisation</Text>{' '}
                      where data-sharing is enabled for the free tier — so{' '}
                      <Text style={{ fontWeight: '700', color: COLORS.textSecondary }}>
                        your wallet is NOT charged (₹0)
                      </Text>
                      . OpenAI may use your decision data to improve their models.
                      You do not need your own OpenAI account.
                    </Text>
                  </View>
                  <Switch
                    testID="openai-free-tier-toggle"
                    value={!!consent?.openai_free_tier}
                    disabled={savingConsent}
                    onValueChange={(v) => saveConsent({
                      // PRIMARY implies allow_openai — flip both ON together.
                      allow_openai: v ? true : !!consent?.allow_openai,
                      mode: consent?.mode || 'always',
                      openai_free_tier: v,
                    })}
                    trackColor={{ true: '#16A34A' }}
                  />
                </View>

                {/* Divider */}
                <View style={{ height: 1, backgroundColor: '#EEF2F6', marginVertical: 12 }} />

                {/* 2. FALLBACK — use OpenAI when Gemini/Groq free quotas exhaust */}
                <View style={styles.consentRow}>
                  <View style={{ flex: 1, paddingRight: 12 }}>
                    <Text style={[styles.infoTitle, { fontSize: 13 }]}>
                      Use OpenAI as fallback (paid)
                    </Text>
                    <Text style={[styles.infoText, { marginTop: 4, fontSize: 11.5 }]}>
                      When the free Gemini/Groq quotas run out and PRIMARY (above) is OFF,
                      fall back to OpenAI and charge your wallet.{' '}
                      <Text style={{ fontWeight: '700', color: COLORS.textSecondary }}>
                        This shares your decision&apos;s data with OpenAI.
                      </Text>
                    </Text>
                  </View>
                  <Switch
                    testID="openai-consent-toggle"
                    value={!!consent?.allow_openai}
                    disabled={savingConsent || !!consent?.openai_free_tier}
                    onValueChange={(v) => saveConsent({
                      allow_openai: v,
                      mode: consent?.mode || 'ask',
                      // Turning fallback OFF must also turn PRIMARY off,
                      // otherwise PRIMARY would have no allow gate.
                      openai_free_tier: v ? !!consent?.openai_free_tier : false,
                    })}
                    trackColor={{ true: COLORS.primary }}
                  />
                </View>
                {consent?.allow_openai && !consent?.openai_free_tier && (
                  <View style={styles.consentModeRow}>
                    {([['ask', 'Ask each time'], ['always', 'Always use automatically']] as const).map(([m, label]) => {
                      const active = (consent?.mode || 'ask') === m;
                      return (
                        <TouchableOpacity
                          key={m}
                          testID={`openai-consent-mode-${m}`}
                          style={[styles.consentChip, active && styles.consentChipActive]}
                          onPress={() => saveConsent({
                            allow_openai: true, mode: m,
                            openai_free_tier: !!consent?.openai_free_tier,
                          })}
                          disabled={savingConsent}
                        >
                          <Text style={[styles.consentChipText, active && styles.consentChipTextActive]}>{label}</Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                )}
                {consent?.openai_free_tier && (
                  <Text style={[styles.fieldHint, { marginTop: 8, fontStyle: 'italic' }]}>
                    Fallback toggle is locked while PRIMARY (free-tier) is ON — PRIMARY already implies fallback.
                  </Text>
                )}
              </View>
            )}

            {/* Refill — credit packs */}
            <Text style={styles.sectionTitle}>Top up credits</Text>
            <Text style={styles.fieldHint}>
              Priced at Gemini&apos;s list rate{packsInfo ? ` + ${packsInfo.markup_pct}% service fee` : ''}. Secure payment via Razorpay (INR).
            </Text>

            {(packsInfo?.packs || []).map((p: any) => (
              <View key={p.id} style={styles.packRow}>
                <View style={{ flex: 1 }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                    <Text style={styles.packName}>{p.name}</Text>
                    {!!p.badge && (
                      <View style={styles.packBadge}><Text style={styles.packBadgeText}>{p.badge}</Text></View>
                    )}
                  </View>
                  <Text style={styles.packCredits}>{p.credits.toLocaleString()} credits</Text>
                </View>
                <TouchableOpacity
                  style={styles.buyBtn}
                  onPress={() => buy({ pack_id: p.id }, p.id)}
                  disabled={buyingId !== null}
                >
                  {buyingId === p.id
                    ? <ActivityIndicator color={COLORS.white} size="small" />
                    : <Text style={styles.buyBtnText}>₹{p.price_inr}</Text>}
                </TouchableOpacity>
              </View>
            ))}

            {/* Custom amount */}
            <View style={styles.customCard}>
              <Text style={styles.fieldLabel}>Custom amount</Text>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <TextInput
                  style={[styles.input, { flex: 1 }]}
                  keyboardType="numeric"
                  value={customCredits}
                  onChangeText={(t) => { setCustomCredits(t); setCustomQuote(null); }}
                  placeholder={`Credits (min ${packsInfo?.min_custom_credits ?? 150})`}
                  placeholderTextColor={COLORS.textMuted}
                />
                <TouchableOpacity style={styles.quoteBtn} onPress={getCustomQuote} disabled={quoting}>
                  {quoting ? <ActivityIndicator color={COLORS.primary} size="small" /> : <Text style={styles.quoteBtnText}>Get price</Text>}
                </TouchableOpacity>
              </View>
              {customQuote && (
                <View style={styles.quoteBox}>
                  <Text style={styles.quoteLine}>
                    {Number(customCredits).toLocaleString()} credits ={'  '}
                    <Text style={{ fontWeight: '800', color: COLORS.primary }}>₹{customQuote.total_inr}</Text>
                  </Text>
                  <Text style={styles.quoteSub}>
                    Gemini cost ₹{customQuote.cost_inr} + {customQuote.markup_pct}% fee ₹{customQuote.markup_inr}
                  </Text>
                  <TouchableOpacity
                    style={[styles.primaryBtn, { marginTop: 10 }]}
                    onPress={() => buy({ credits: parseInt(customCredits, 10) }, 'custom')}
                    disabled={buyingId !== null}
                  >
                    {buyingId === 'custom'
                      ? <ActivityIndicator color={COLORS.white} />
                      : <Text style={styles.primaryBtnText}>Pay ₹{customQuote.total_inr}</Text>}
                  </TouchableOpacity>
                </View>
              )}
            </View>

            {/* Admin controls (defaults, pricing, routing, grant credits,
                ledger search) deliberately live ONLY in /admin/ai-wallet-config.
                Do NOT add admin shortcuts here — even for super_admin —
                so the user-facing wallet stays a clean end-user surface. */}

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
  consentRow: { flexDirection: 'row', alignItems: 'center' },
  consentModeRow: { flexDirection: 'row', gap: 8, marginTop: 12 },
  consentChip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999, borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.white },
  consentChipActive: { backgroundColor: COLORS.primary + '14', borderColor: COLORS.primary },
  consentChipText: { fontSize: 12, fontWeight: '600', color: COLORS.textMuted },
  consentChipTextActive: { color: COLORS.primary },
  refillNote: { flexDirection: 'row', alignItems: 'flex-start', gap: 6, marginTop: 10, backgroundColor: COLORS.divider, padding: 10, borderRadius: 10 },
  refillNoteText: { flex: 1, fontSize: 12, color: COLORS.textSecondary, lineHeight: 17 },

  adminCard: { backgroundColor: COLORS.surface, borderRadius: 14, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: COLORS.border },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },
  fieldHint: { fontSize: 12, color: COLORS.textMuted, marginBottom: 8 },
  fieldLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textSecondary, marginTop: 10, marginBottom: 4 },
  input: { borderWidth: 1, borderColor: COLORS.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: COLORS.textPrimary, backgroundColor: COLORS.white },
  primaryBtn: { backgroundColor: COLORS.primary, borderRadius: 12, paddingVertical: 12, alignItems: 'center', marginTop: 14 },
  primaryBtnText: { color: COLORS.white, fontWeight: '700', fontSize: 14 },
  cfgDivider: { height: 1, backgroundColor: COLORS.border, marginVertical: 14 },

  packRow: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: COLORS.surface, borderRadius: 12, padding: 14, marginBottom: 10,
    borderWidth: 1, borderColor: COLORS.border,
  },
  packName: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary },
  packBadge: { backgroundColor: COLORS.primary + '1A', borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 },
  packBadgeText: { fontSize: 10, fontWeight: '700', color: COLORS.primary },
  packCredits: { fontSize: 13, color: COLORS.textSecondary, marginTop: 3 },
  buyBtn: { backgroundColor: COLORS.primary, borderRadius: 10, paddingVertical: 10, paddingHorizontal: 16, minWidth: 84, alignItems: 'center' },
  buyBtnText: { color: COLORS.white, fontWeight: '800', fontSize: 14 },

  customCard: { backgroundColor: COLORS.surface, borderRadius: 12, padding: 14, marginTop: 4, marginBottom: 20, borderWidth: 1, borderColor: COLORS.border },
  quoteBtn: { borderWidth: 1.5, borderColor: COLORS.primary, borderRadius: 10, paddingHorizontal: 14, justifyContent: 'center', alignItems: 'center' },
  quoteBtnText: { color: COLORS.primary, fontWeight: '700', fontSize: 13 },
  quoteBox: { marginTop: 12, backgroundColor: COLORS.divider, borderRadius: 10, padding: 12 },
  quoteLine: { fontSize: 14, color: COLORS.textPrimary },
  quoteSub: { fontSize: 12, color: COLORS.textSecondary, marginTop: 3 },

  emptyLedger: { alignItems: 'center', paddingVertical: 24, gap: 8 },
  emptyLedgerText: { fontSize: 13, color: COLORS.textMuted },
  ledgerRow: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: COLORS.surface, borderRadius: 12, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: COLORS.border },
  ledgerIcon: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  ledgerLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },
  ledgerMeta: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },
  ledgerDelta: { fontSize: 14, fontWeight: '700' },
});
