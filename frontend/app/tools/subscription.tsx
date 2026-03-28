import React, { useState, useCallback } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  RefreshControl, ActivityIndicator, Alert, Linking, Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import Constants from 'expo-constants';

const PLAN_COLORS: Record<string, string[]> = {
  free: ['#94A3B8', '#CBD5E1'],
  starter: ['#3B82F6', '#60A5FA'],
  pro: ['#7C3AED', '#A855F7'],
  business: ['#059669', '#10B981'],
  enterprise: ['#DC2626', '#EF4444'],
};

const BASE_URL = Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL || '';

export default function SubscriptionScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [wallet, setWallet] = useState<any>(null);
  const [plans, setPlans] = useState<any[]>([]);
  const [topups, setTopups] = useState<any[]>([]);
  const [creditCosts, setCreditCosts] = useState<Record<string, number>>({});
  const [history, setHistory] = useState<any[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = async () => {
    try {
      const [walletRes, plansRes, histRes] = await Promise.all([
        api.get('/payments/wallet'),
        api.get('/payments/plans'),
        api.get('/payments/history'),
      ]);
      setWallet(walletRes.data);
      setPlans(plansRes.data?.plans || []);
      setTopups(plansRes.data?.topup_packs || []);
      setCreditCosts(plansRes.data?.credit_costs || {});
      setHistory(histRes.data?.transactions || []);
    } catch (err) {
      console.error('Subscription fetch error:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useFocusEffect(useCallback(() => { fetchData(); }, []));

  const handleSubscribe = async (planId: string) => {
    if (planId === 'free') return;
    setProcessing(true);
    try {
      const res = await api.post('/payments/create-subscription', { plan_id: planId });
      const data = res.data;
      // Open Razorpay checkout
      await openRazorpay(data.order_id, data.amount, data.key_id, data.user_name, data.user_email, 'subscription', planId);
    } catch (err: any) {
      showAlert('Error', err?.response?.data?.detail || 'Failed to create subscription');
    } finally {
      setProcessing(false);
    }
  };

  const handleTopup = async (packId: string) => {
    setProcessing(true);
    try {
      const res = await api.post('/payments/create-topup-order', { pack_id: packId });
      const data = res.data;
      await openRazorpay(data.order_id, data.amount, data.key_id, data.user_name, data.user_email, 'topup', packId);
    } catch (err: any) {
      showAlert('Error', err?.response?.data?.detail || 'Failed to create order');
    } finally {
      setProcessing(false);
    }
  };

  const openRazorpay = async (orderId: string, amount: number, keyId: string, name: string, email: string, type: string, itemId: string) => {
    // For React Native / Expo, we use a web-based checkout approach
    // Razorpay doesn't have native Expo SDK, so we redirect to a checkout page
    const checkoutUrl = `${BASE_URL}/api/payments/checkout?order_id=${orderId}&key_id=${keyId}&amount=${amount}&name=${encodeURIComponent(name)}&email=${encodeURIComponent(email)}&type=${type}&item_id=${itemId}`;

    showAlert(
      'Complete Payment',
      `You'll be redirected to Razorpay to complete your ₹${(amount / 100).toFixed(0)} payment.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Pay Now',
          onPress: async () => {
            try {
              // For web preview / mobile, open Razorpay checkout link
              if (Platform.OS === 'web') {
                // Use Razorpay JS on web
                const w = window as any;
                if (w.Razorpay) {
                  const rzp = new w.Razorpay({
                    key: keyId,
                    amount: amount,
                    currency: 'INR',
                    order_id: orderId,
                    name: 'Dezider',
                    description: type === 'subscription' ? 'Monthly Subscription' : 'Credit Top-up',
                    prefill: { name, email },
                    handler: async (response: any) => {
                      try {
                        await api.post('/payments/verify', {
                          razorpay_order_id: response.razorpay_order_id,
                          razorpay_payment_id: response.razorpay_payment_id,
                          razorpay_signature: response.razorpay_signature,
                        });
                        showAlert('Success', 'Payment verified! Credits added to your wallet.');
                        fetchData();
                      } catch {
                        showAlert('Verification Failed', 'Payment was made but verification failed. Contact support.');
                      }
                    },
                  });
                  rzp.open();
                } else {
                  // Load Razorpay script dynamically
                  const script = document.createElement('script');
                  script.src = 'https://checkout.razorpay.com/v1/checkout.js';
                  script.onload = () => {
                    const rzp = new (window as any).Razorpay({
                      key: keyId,
                      amount: amount,
                      currency: 'INR',
                      order_id: orderId,
                      name: 'Dezider',
                      description: type === 'subscription' ? 'Monthly Subscription' : 'Credit Top-up',
                      prefill: { name, email },
                      handler: async (response: any) => {
                        try {
                          await api.post('/payments/verify', {
                            razorpay_order_id: response.razorpay_order_id,
                            razorpay_payment_id: response.razorpay_payment_id,
                            razorpay_signature: response.razorpay_signature,
                          });
                          showAlert('Success', 'Payment verified! Credits added.');
                          fetchData();
                        } catch {
                          showAlert('Error', 'Verification failed.');
                        }
                      },
                    });
                    rzp.open();
                  };
                  document.body.appendChild(script);
                }
              } else {
                // Mobile: Open in browser
                Linking.openURL(checkoutUrl);
              }
            } catch {
              showAlert('Error', 'Failed to open payment gateway');
            }
          },
        },
      ]
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={st.container}>
        <View style={st.center}><ActivityIndicator size="large" color={COLORS.primary} /></View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={st.container}>
      <View style={st.header}>
        <TouchableOpacity onPress={() => router.back()} style={st.backBtn}>
          <Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={st.title}>Subscription & Credits</Text>
          <Text style={st.subtitle}>Power your AI-driven decisions</Text>
        </View>
      </View>

      <ScrollView
        contentContainerStyle={st.scrollContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchData(); }} colors={[COLORS.primary]} />}
      >
        {/* Credit Wallet */}
        <LinearGradient colors={['#1E293B', '#334155']} style={st.walletCard}>
          <View style={st.walletTop}>
            <View>
              <Text style={st.walletLabel}>Credit Balance</Text>
              <Text style={st.walletCredits}>{wallet?.credits || 0}</Text>
            </View>
            <View style={st.walletBadge}>
              <Text style={st.walletPlan}>{(wallet?.current_plan || 'free').toUpperCase()}</Text>
            </View>
          </View>
          <View style={st.walletStats}>
            <View style={st.walletStat}>
              <Text style={st.walletStatNum}>{wallet?.total_purchased || 0}</Text>
              <Text style={st.walletStatLabel}>Purchased</Text>
            </View>
            <View style={st.walletStat}>
              <Text style={st.walletStatNum}>{wallet?.total_used || 0}</Text>
              <Text style={st.walletStatLabel}>Used</Text>
            </View>
            {wallet?.subscription_end && (
              <View style={st.walletStat}>
                <Text style={st.walletStatNum}>
                  {new Date(wallet.subscription_end).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                </Text>
                <Text style={st.walletStatLabel}>Renewal</Text>
              </View>
            )}
          </View>
        </LinearGradient>

        {/* Credit Costs */}
        <View style={st.costSection}>
          <Text style={st.sectionTitle}>Credit Costs per Action</Text>
          <View style={st.costGrid}>
            {Object.entries(creditCosts).map(([action, cost]) => (
              <View key={action} style={st.costItem}>
                <Text style={st.costAction}>{action.replace(/_/g, ' ')}</Text>
                <Text style={[st.costNum, { color: cost === 0 ? '#16A34A' : COLORS.primary }]}>
                  {cost === 0 ? 'Free' : `${cost} cr`}
                </Text>
              </View>
            ))}
          </View>
        </View>

        {/* Subscription Plans */}
        <Text style={st.sectionTitle}>Monthly Plans</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={st.plansScroll}>
          {plans.map(plan => {
            const colors = PLAN_COLORS[plan.id] || PLAN_COLORS.free;
            const isCurrent = wallet?.current_plan === plan.id;
            return (
              <View key={plan.id} style={[st.planCard, isCurrent && st.planCardCurrent]}>
                <LinearGradient colors={colors} style={st.planHeader}>
                  {plan.popular && <View style={st.popularBadge}><Text style={st.popularText}>POPULAR</Text></View>}
                  <Text style={st.planName}>{plan.name}</Text>
                  <Text style={st.planPrice}>
                    {plan.price_inr === 0 ? 'Free' : `₹${plan.price_inr}`}
                    {plan.price_inr > 0 && <Text style={st.planPer}>/mo</Text>}
                  </Text>
                  {plan.credits_per_month > 0 && (
                    <Text style={st.planCredits}>{plan.credits_per_month} credits/month</Text>
                  )}
                </LinearGradient>
                <View style={st.planBody}>
                  {(plan.features || []).slice(0, 4).map((f: string, i: number) => (
                    <View key={i} style={st.featureRow}>
                      <Ionicons name="checkmark-circle" size={14} color={colors[0]} />
                      <Text style={st.featureText}>{f}</Text>
                    </View>
                  ))}
                  {isCurrent ? (
                    <View style={st.currentBadge}>
                      <Text style={st.currentText}>Current Plan</Text>
                    </View>
                  ) : plan.id !== 'free' ? (
                    <TouchableOpacity
                      style={[st.subscribeBtn, { backgroundColor: colors[0] }]}
                      onPress={() => handleSubscribe(plan.id)}
                      disabled={processing}
                    >
                      {processing ? <ActivityIndicator size="small" color="#FFF" /> : (
                        <Text style={st.subscribeBtnText}>
                          {wallet?.current_plan !== 'free' ? 'Upgrade' : 'Subscribe'}
                        </Text>
                      )}
                    </TouchableOpacity>
                  ) : null}
                </View>
              </View>
            );
          })}
        </ScrollView>

        {/* Top-up Packs */}
        <Text style={[st.sectionTitle, { marginTop: 16 }]}>Credit Top-ups</Text>
        <Text style={st.sectionSub}>One-time credit purchases for when you need more</Text>
        <View style={st.topupGrid}>
          {topups.map(pack => (
            <TouchableOpacity
              key={pack.id}
              style={st.topupCard}
              onPress={() => handleTopup(pack.id)}
              disabled={processing}
            >
              <Text style={st.topupBadge}>{pack.badge}</Text>
              <Text style={st.topupCredits}>{pack.credits}</Text>
              <Text style={st.topupLabel}>credits</Text>
              <Text style={st.topupPrice}>₹{pack.price_inr}</Text>
              <Text style={st.topupPerCredit}>
                ₹{(pack.price_inr / pack.credits).toFixed(2)}/cr
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Transaction History */}
        <TouchableOpacity style={st.historyToggle} onPress={() => setShowHistory(!showHistory)}>
          <Text style={st.sectionTitle}>Transaction History</Text>
          <Ionicons name={showHistory ? 'chevron-up' : 'chevron-down'} size={18} color={COLORS.textMuted} />
        </TouchableOpacity>

        {showHistory && (
          <View style={st.historyList}>
            {history.length === 0 ? (
              <Text style={st.emptyText}>No transactions yet</Text>
            ) : (
              history.slice(0, 20).map((tx, idx) => (
                <View key={idx} style={st.txRow}>
                  <View style={[st.txIcon, {
                    backgroundColor: tx.type === 'purchase' ? '#DCFCE7' :
                      tx.type === 'grant' ? '#DBEAFE' : '#FEE2E2',
                  }]}>
                    <Ionicons
                      name={tx.type === 'purchase' ? 'add-circle' :
                        tx.type === 'grant' ? 'gift' : 'remove-circle'}
                      size={16}
                      color={tx.type === 'purchase' ? '#16A34A' :
                        tx.type === 'grant' ? '#3B82F6' : '#DC2626'}
                    />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={st.txDesc}>{tx.description}</Text>
                    <Text style={st.txDate}>
                      {new Date(tx.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
                    </Text>
                  </View>
                  <View style={{ alignItems: 'flex-end' }}>
                    <Text style={[st.txAmount, { color: tx.credits > 0 ? '#16A34A' : '#DC2626' }]}>
                      {tx.credits > 0 ? '+' : ''}{tx.credits}
                    </Text>
                    <Text style={st.txBalance}>Bal: {tx.balance_after}</Text>
                  </View>
                </View>
              ))
            )}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 10, gap: 10 },
  backBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#F1F5F9', alignItems: 'center', justifyContent: 'center' },
  title: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 11, color: COLORS.textMuted },
  scrollContent: { padding: 16, paddingBottom: 40 },

  // Wallet
  walletCard: { borderRadius: 16, padding: 20, marginBottom: 16 },
  walletTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  walletLabel: { fontSize: 12, color: 'rgba(255,255,255,0.7)' },
  walletCredits: { fontSize: 42, fontWeight: '800', color: '#FFF' },
  walletBadge: { backgroundColor: 'rgba(255,255,255,0.15)', paddingHorizontal: 12, paddingVertical: 4, borderRadius: 10 },
  walletPlan: { fontSize: 12, fontWeight: '700', color: '#FFF' },
  walletStats: { flexDirection: 'row', gap: 24, marginTop: 16 },
  walletStat: {},
  walletStatNum: { fontSize: 16, fontWeight: '700', color: '#FFF' },
  walletStatLabel: { fontSize: 10, color: 'rgba(255,255,255,0.6)' },

  // Costs
  costSection: { marginBottom: 16 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },
  sectionSub: { fontSize: 12, color: COLORS.textMuted, marginBottom: 8, marginTop: -4 },
  costGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  costItem: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: '#F8FAFC', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6, width: '48%' },
  costAction: { fontSize: 11, color: COLORS.textSecondary, textTransform: 'capitalize', flex: 1 },
  costNum: { fontSize: 12, fontWeight: '700' },

  // Plans
  plansScroll: { marginBottom: 8, marginHorizontal: -4 },
  planCard: { width: 200, backgroundColor: '#FFF', borderRadius: 14, marginHorizontal: 4, borderWidth: 1, borderColor: COLORS.border, overflow: 'hidden' },
  planCardCurrent: { borderColor: COLORS.primary, borderWidth: 2 },
  planHeader: { padding: 14, alignItems: 'center', gap: 2 },
  popularBadge: { position: 'absolute', top: 6, right: 6, backgroundColor: '#FEF3C7', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 },
  popularText: { fontSize: 8, fontWeight: '800', color: '#D97706' },
  planName: { fontSize: 16, fontWeight: '800', color: '#FFF' },
  planPrice: { fontSize: 24, fontWeight: '800', color: '#FFF' },
  planPer: { fontSize: 12, fontWeight: '400' },
  planCredits: { fontSize: 11, color: 'rgba(255,255,255,0.8)', fontWeight: '600' },
  planBody: { padding: 12, gap: 6 },
  featureRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  featureText: { fontSize: 11, color: COLORS.textSecondary, flex: 1 },
  currentBadge: { backgroundColor: '#DCFCE7', borderRadius: 8, paddingVertical: 8, alignItems: 'center', marginTop: 4 },
  currentText: { fontSize: 12, fontWeight: '700', color: '#16A34A' },
  subscribeBtn: { borderRadius: 10, paddingVertical: 10, alignItems: 'center', marginTop: 4 },
  subscribeBtnText: { fontSize: 13, fontWeight: '700', color: '#FFF' },

  // Top-ups
  topupGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 16 },
  topupCard: { width: '31%', backgroundColor: '#FFF', borderRadius: 12, padding: 12, alignItems: 'center', borderWidth: 1, borderColor: COLORS.border },
  topupBadge: { fontSize: 8, fontWeight: '700', color: COLORS.primary, backgroundColor: '#EDE9FE', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6, marginBottom: 4 },
  topupCredits: { fontSize: 22, fontWeight: '800', color: COLORS.textPrimary },
  topupLabel: { fontSize: 10, color: COLORS.textMuted },
  topupPrice: { fontSize: 14, fontWeight: '700', color: '#16A34A', marginTop: 4 },
  topupPerCredit: { fontSize: 9, color: COLORS.textMuted },

  // History
  historyToggle: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  historyList: { gap: 6, marginTop: 4 },
  emptyText: { fontSize: 13, color: COLORS.textMuted, textAlign: 'center', paddingVertical: 16 },
  txRow: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#FFF', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: COLORS.border },
  txIcon: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  txDesc: { fontSize: 12, fontWeight: '600', color: COLORS.textPrimary },
  txDate: { fontSize: 10, color: COLORS.textMuted },
  txAmount: { fontSize: 14, fontWeight: '700' },
  txBalance: { fontSize: 10, color: COLORS.textMuted },
});
