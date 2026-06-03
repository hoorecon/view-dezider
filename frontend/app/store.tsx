/**
 * /store — Public on-demand SKU storefront.
 *
 * Renders the 4 SKUs (L1/L2/L3/L4) as buyable tiles + a 5th "Monthly Plans"
 * tile that deep-links to the existing /pricing page. Prices, names, and
 * descriptions are fetched from /api/store/skus (NOT hardcoded).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, ActivityIndicator, Platform, Linking, Modal, TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import api from '../src/utils/api';
import { showAlert } from '../src/utils/alert';
import { safeBack } from '../src/utils/navigation';

interface Sku { code: string; name: string; tagline: string; description: string; price_paise: number; gst_percent?: number; quota: number; kind: string; badge_color: string; icon: string; active: boolean; display_order: number; }
interface Entitlement { sku_code: string; balance: number; granted_qty: number; consumed_qty: number; last_used_at?: string | null }

declare const Razorpay: any; // injected by /razorpay-checkout.html or RN SDK

function formatINR(paise: number) {
  const rupees = paise / 100;
  const fixed = rupees.toFixed(paise % 100 === 0 ? 0 : 2);
  // Indian numbering: last 3 digits separated normally, then groups of 2
  const [intPart, decPart] = fixed.split('.');
  const lastThree = intPart.slice(-3);
  const rest = intPart.slice(0, -3);
  const formatted = rest ? rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + ',' + lastThree : lastThree;
  return '₹' + formatted + (decPart ? '.' + decPart : '');
}

export default function StoreScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ highlight?: string; module?: string; decision_id?: string }>();
  const [skus, setSkus] = useState<Sku[]>([]);
  const [ents, setEnts] = useState<Entitlement[]>([]);
  const [loading, setLoading] = useState(true);
  const [purchasing, setPurchasing] = useState<string | null>(null);
  // Checkout modal + coupon state
  const [checkoutSku, setCheckoutSku] = useState<Sku | null>(null);
  const [couponInput, setCouponInput] = useState('');
  const [couponState, setCouponState] = useState<{ status: 'idle' | 'checking' | 'valid' | 'invalid'; net?: number; message?: string }>({ status: 'idle' });

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const [s, e] = await Promise.all([
        api.get('/store/skus'),
        api.get('/store/my-entitlements').catch(() => ({ data: { entitlements: [] } })),
      ]);
      setSkus(s.data.skus || []);
      setEnts(e.data.entitlements || []);
    } catch {
      showAlert('Network error', 'Could not load the store. Please try again.');
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const balanceFor = (code: string) => (ents.find(x => x.sku_code === code)?.balance ?? 0);

  const startPurchase = useCallback(async (sku: Sku, couponCode?: string) => {
    setPurchasing(sku.code);
    setCheckoutSku(null);
    try {
      const orderRes = await api.post('/store/purchase', {
        sku_code: sku.code,
        decision_id: params.decision_id || null,
        module: params.module || null,
        coupon_code: couponCode || null,
      });
      const data = orderRes.data;
      if (Platform.OS === 'web') {
        // Use Razorpay Web Checkout via script tag
        await loadRazorpayScript();
        const rzp = new (window as any).Razorpay({
          key: data.key_id,
          amount: data.amount,
          currency: data.currency,
          name: 'JELCOS Dezider',
          description: sku.name,
          order_id: data.order_id,
          prefill: { name: data.user_name, email: data.user_email },
          theme: { color: sku.badge_color || '#7C3AED' },
          handler: async (resp: any) => {
            try {
              const verify = await api.post('/store/verify', resp);
              showAlert('Payment successful', `${sku.name} unlocked. ${verify.data.balance ? `New balance: ${verify.data.balance}` : ''}`.trim());
              await load();
              applyRedirectHint(verify.data.redirect_hint, router);
            } catch (err: any) {
              showAlert('Verification failed', err?.response?.data?.detail || 'Could not verify payment. Contact support.');
            }
          },
          modal: { ondismiss: () => setPurchasing(null) },
        });
        rzp.open();
      } else {
        // Native fallback — open hosted checkout via deep link
        Linking.openURL(`https://checkout.razorpay.com/v1/checkout/embedded?key_id=${data.key_id}&order_id=${data.order_id}`);
      }
    } catch (err: any) {
      showAlert('Error', err?.response?.data?.detail || 'Could not start checkout.');
    } finally {
      setTimeout(() => setPurchasing(null), 1200);
    }
  }, [params, load, router]);

  const openCheckout = useCallback((sku: Sku) => {
    setCouponInput('');
    setCouponState({ status: 'idle' });
    setCheckoutSku(sku);
  }, []);

  const applyCoupon = useCallback(async () => {
    if (!checkoutSku) return;
    const code = couponInput.trim().toUpperCase();
    if (!code) { setCouponState({ status: 'idle' }); return; }
    setCouponState({ status: 'checking' });
    try {
      const r = await api.post('/coupons/validate', {
        coupon_code: code,
        list_price: checkoutSku.price_paise / 100,
        flow: 'STORE',
      });
      if (r.data?.valid) {
        setCouponState({ status: 'valid', net: Number(r.data.net_payable_amount), message: r.data.coupon_desc || 'Coupon applied' });
      } else {
        setCouponState({ status: 'invalid', message: r.data?.remarks || 'Invalid coupon' });
      }
    } catch (e: any) {
      setCouponState({ status: 'invalid', message: e?.response?.data?.detail || 'Could not validate coupon' });
    }
  }, [checkoutSku, couponInput]);

  // Live price preview inside the checkout modal
  const previewTotals = (() => {
    if (!checkoutSku) return null;
    const base = checkoutSku.price_paise;
    const gstPct = checkoutSku.gst_percent ?? 18;
    const couponValid = couponState.status === 'valid' && typeof couponState.net === 'number';
    const taxable = couponValid ? Math.max(0, Math.round((couponState.net as number) * 100)) : base;
    const discount = Math.max(0, base - taxable);
    const gst = Math.round(taxable * gstPct / 100);
    const total = taxable + gst;
    return { base, gstPct, taxable, discount, gst, total };
  })();

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      <LinearGradient colors={['#1E40AF', '#7C3AED']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={s.header}>
        <TouchableOpacity style={s.iconBtn} onPress={() => safeBack(router)} accessibilityLabel="Back">
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.headerTitle}>Solution Box · Store</Text>
          <Text style={s.headerSub}>Pay-as-you-go packs · GST extra · Razorpay secured</Text>
        </View>
        <TouchableOpacity style={s.iconBtnSolid} onPress={() => router.push('/' as any)} accessibilityLabel="Home">
          <Ionicons name="home" size={20} color="#7C3AED" />
        </TouchableOpacity>
      </LinearGradient>

      {loading ? (
        <View style={s.center}><ActivityIndicator size="large" color="#7C3AED" /></View>
      ) : (
        <ScrollView contentContainerStyle={s.body}>
          <Text style={s.intro}>Get the depth you need. Every pack works across <Text style={{ fontWeight: '700' }}>My Dezider</Text>, <Text style={{ fontWeight: '700' }}>Pros &amp; Cons</Text>, and <Text style={{ fontWeight: '700' }}>SWOT</Text>.</Text>

          {skus.map(sku => {
            const bal = balanceFor(sku.code);
            const highlighted = params.highlight === sku.code;
            const tone = sku.badge_color || '#3B82F6';
            return (
              <View key={sku.code} style={[s.card, highlighted && { borderColor: tone, borderWidth: 2 }]}>
                <View style={[s.cardIcon, { backgroundColor: tone + '18' }]}>
                  <Ionicons name={(sku.icon || 'pricetag') as any} size={26} color={tone} />
                </View>
                <View style={{ flex: 1 }}>
                  <View style={s.cardHeadRow}>
                    <Text style={s.cardLayer}>{sku.code}</Text>
                    {bal > 0 && <View style={s.balanceChip}><Ionicons name="checkmark-circle" size={12} color="#059669" /><Text style={s.balanceText}>{bal} left</Text></View>}
                  </View>
                  <Text style={s.cardName}>{sku.name}</Text>
                  <Text style={s.cardTagline}>{sku.tagline}</Text>
                  <Text style={s.cardDesc}>{sku.description}</Text>
                  <View style={s.cardFootRow}>
                    <Text style={s.cardPrice}>{formatINR(sku.price_paise)} <Text style={s.cardPriceMuted}>excl. GST</Text></Text>
                    {sku.quota > 1 && <Text style={s.cardQuota}>{sku.quota} uses</Text>}
                  </View>
                  <TouchableOpacity
                    style={[s.buyBtn, { backgroundColor: tone }, purchasing === sku.code && { opacity: 0.6 }]}
                    onPress={() => openCheckout(sku)}
                    disabled={purchasing === sku.code}
                  >
                    {purchasing === sku.code ? <ActivityIndicator size="small" color="#FFF" /> : <Text style={s.buyText}>{bal > 0 ? 'Buy more' : 'Buy now'}</Text>}
                  </TouchableOpacity>
                </View>
              </View>
            );
          })}

          {/* 5th tile — Monthly Subscription */}
          <TouchableOpacity style={s.subCard} onPress={() => router.push('/pricing' as any)}>
            <LinearGradient colors={['#059669', '#10B981']} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={s.subInner}>
              <Ionicons name="infinite" size={28} color="#FFF" />
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={s.subTitle}>Monthly Subscription</Text>
                <Text style={s.subDesc}>7-tier plans from ₹149/mo — unlimited decisions, credits, and premium tools.</Text>
              </View>
              <Ionicons name="chevron-forward" size={22} color="#FFF" />
            </LinearGradient>
          </TouchableOpacity>

          <Text style={s.disclaimer}>Powered by Razorpay · 100% PCI-DSS · Indian GST invoices issued. Need help? support@jelcos.ai</Text>
        </ScrollView>
      )}

      {/* Checkout + coupon modal */}
      <Modal visible={!!checkoutSku} transparent animationType="fade" onRequestClose={() => setCheckoutSku(null)}>
        <View style={s.modalOverlay}>
          <View style={s.modalCard}>
            <View style={s.modalHead}>
              <Text style={s.modalTitle}>{checkoutSku?.name}</Text>
              <TouchableOpacity onPress={() => setCheckoutSku(null)} accessibilityLabel="Close">
                <Ionicons name="close" size={22} color="#64748B" />
              </TouchableOpacity>
            </View>

            <Text style={s.modalSub}>{checkoutSku?.tagline}</Text>

            {/* Coupon input */}
            <Text style={s.couponLabel}>Have a coupon?</Text>
            <View style={s.couponRow}>
              <TextInput
                value={couponInput}
                onChangeText={(t) => { setCouponInput(t.toUpperCase()); if (couponState.status !== 'idle') setCouponState({ status: 'idle' }); }}
                placeholder="Enter code"
                placeholderTextColor="#94A3B8"
                autoCapitalize="characters"
                style={s.couponInput}
              />
              <TouchableOpacity
                style={[s.couponBtn, couponState.status === 'checking' && { opacity: 0.6 }]}
                onPress={applyCoupon}
                disabled={couponState.status === 'checking'}
              >
                {couponState.status === 'checking'
                  ? <ActivityIndicator size="small" color="#FFF" />
                  : <Text style={s.couponBtnText}>Apply</Text>}
              </TouchableOpacity>
            </View>
            {couponState.status === 'valid' && (
              <View style={s.couponMsgOk}><Ionicons name="checkmark-circle" size={14} color="#059669" /><Text style={s.couponMsgOkText}>{couponState.message}</Text></View>
            )}
            {couponState.status === 'invalid' && (
              <View style={s.couponMsgErr}><Ionicons name="alert-circle" size={14} color="#DC2626" /><Text style={s.couponMsgErrText}>{couponState.message}</Text></View>
            )}

            {/* Price breakdown */}
            {previewTotals && (
              <View style={s.breakdown}>
                <View style={s.bRow}><Text style={s.bLabel}>Base price</Text><Text style={s.bVal}>{formatINR(previewTotals.base)}</Text></View>
                {previewTotals.discount > 0 && (
                  <View style={s.bRow}><Text style={[s.bLabel, { color: '#059669' }]}>Coupon discount</Text><Text style={[s.bVal, { color: '#059669' }]}>− {formatINR(previewTotals.discount)}</Text></View>
                )}
                <View style={s.bRow}><Text style={s.bLabel}>GST ({previewTotals.gstPct}%)</Text><Text style={s.bVal}>{formatINR(previewTotals.gst)}</Text></View>
                <View style={[s.bRow, s.bTotalRow]}><Text style={s.bTotalLabel}>Total payable</Text><Text style={s.bTotalVal}>{formatINR(previewTotals.total)}</Text></View>
              </View>
            )}

            <TouchableOpacity
              style={[s.payBtn, { backgroundColor: checkoutSku?.badge_color || '#7C3AED' }]}
              onPress={() => checkoutSku && startPurchase(checkoutSku, couponState.status === 'valid' ? couponInput.trim().toUpperCase() : undefined)}
            >
              <Ionicons name="lock-closed" size={16} color="#FFF" />
              <Text style={s.payText}>Pay {previewTotals ? formatINR(previewTotals.total) : ''}</Text>
            </TouchableOpacity>
            <Text style={s.modalDisclaimer}>Secured by Razorpay · GST invoice issued</Text>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

async function loadRazorpayScript() {
  if (Platform.OS !== 'web') return;
  const w = window as any;
  if (w.Razorpay) return;
  await new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/checkout.js';
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('failed to load Razorpay'));
    document.body.appendChild(script);
  });
}

function applyRedirectHint(hint: any, router: any) {
  if (!hint) return;
  if (hint.type === 'report' && hint.module && hint.decision_id) {
    // PDF screen lives inside each module's detail page; just send user back.
    router.push({ pathname: `/tools/${hint.module}` as any, params: { id: hint.decision_id } } as any);
  } else if (hint.type === 'expert_booking' && hint.module) {
    router.push({ pathname: '/tools/expert-net' as any, params: { from_module: hint.module, decision_id: hint.decision_id } } as any);
  } else if (hint.type === 'modules') {
    router.push('/' as any);
  }
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingVertical: 12, gap: 10 },
  iconBtn: { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.18)' },
  iconBtnSolid: { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center', backgroundColor: '#FFF' },
  headerTitle: { color: '#FFFFFF', fontSize: 18, fontWeight: '700' },
  headerSub: { color: '#E0E7FF', fontSize: 11, marginTop: 2 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  body: { padding: 16, paddingBottom: 32 },
  intro: { color: '#475569', fontSize: 14, lineHeight: 20, marginBottom: 14 },
  card: { flexDirection: 'row', backgroundColor: '#FFFFFF', borderRadius: 16, padding: 14, marginBottom: 14, gap: 12, borderWidth: 1, borderColor: '#E5E7EB', shadowColor: '#000', shadowOpacity: 0.04, shadowRadius: 6, shadowOffset: { width: 0, height: 2 }, elevation: 1 },
  cardIcon: { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center' },
  cardHeadRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  cardLayer: { color: '#64748B', fontSize: 11, fontWeight: '700', letterSpacing: 0.8 },
  balanceChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 8, paddingVertical: 2, backgroundColor: '#ECFDF5', borderRadius: 999, borderWidth: 1, borderColor: '#A7F3D0' },
  balanceText: { color: '#059669', fontSize: 11, fontWeight: '700' },
  cardName: { color: '#0F172A', fontSize: 16, fontWeight: '700', marginTop: 2 },
  cardTagline: { color: '#7C3AED', fontSize: 11, fontWeight: '600', textTransform: 'uppercase', letterSpacing: 0.5, marginTop: 2 },
  cardDesc: { color: '#475569', fontSize: 13, marginTop: 4, lineHeight: 18 },
  cardFootRow: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', marginTop: 8 },
  cardPrice: { color: '#0F172A', fontSize: 20, fontWeight: '800' },
  cardPriceMuted: { color: '#94A3B8', fontSize: 11, fontWeight: '500' },
  cardQuota: { color: '#64748B', fontSize: 12 },
  buyBtn: { marginTop: 10, alignSelf: 'flex-start', paddingHorizontal: 18, paddingVertical: 9, borderRadius: 10 },
  buyText: { color: '#FFFFFF', fontWeight: '700', fontSize: 14 },
  subCard: { borderRadius: 16, overflow: 'hidden', marginTop: 4, marginBottom: 18 },
  subInner: { flexDirection: 'row', alignItems: 'center', padding: 16 },
  subTitle: { color: '#FFFFFF', fontWeight: '700', fontSize: 16 },
  subDesc: { color: '#D1FAE5', fontSize: 12, marginTop: 3, lineHeight: 17 },
  disclaimer: { color: '#94A3B8', fontSize: 11, textAlign: 'center', lineHeight: 16, marginTop: 4 },
  modalOverlay: { flex: 1, backgroundColor: 'rgba(15,23,42,0.55)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  modalCard: { width: '100%', maxWidth: 420, backgroundColor: '#FFFFFF', borderRadius: 18, padding: 20 },
  modalHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  modalTitle: { color: '#0F172A', fontSize: 18, fontWeight: '800', flex: 1, paddingRight: 8 },
  modalSub: { color: '#7C3AED', fontSize: 12, fontWeight: '600', marginTop: 2, marginBottom: 14 },
  couponLabel: { color: '#0F172A', fontSize: 14, fontWeight: '700', marginBottom: 8 },
  couponRow: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  couponInput: { flex: 1, borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: '#0F172A', backgroundColor: '#F8FAFC' },
  couponBtn: { backgroundColor: '#7C3AED', borderRadius: 10, paddingHorizontal: 18, paddingVertical: 11, minWidth: 72, alignItems: 'center' },
  couponBtnText: { color: '#FFFFFF', fontWeight: '700', fontSize: 14 },
  couponMsgOk: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8 },
  couponMsgOkText: { color: '#059669', fontSize: 12, fontWeight: '600', flex: 1 },
  couponMsgErr: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8 },
  couponMsgErrText: { color: '#DC2626', fontSize: 12, fontWeight: '600', flex: 1 },
  breakdown: { marginTop: 16, backgroundColor: '#F8FAFC', borderRadius: 12, padding: 14, borderWidth: 1, borderColor: '#E5E7EB' },
  bRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  bLabel: { color: '#475569', fontSize: 13 },
  bVal: { color: '#0F172A', fontSize: 13, fontWeight: '600' },
  bTotalRow: { borderTopWidth: 1, borderTopColor: '#E2E8F0', paddingTop: 10, marginBottom: 0, marginTop: 2 },
  bTotalLabel: { color: '#0F172A', fontSize: 15, fontWeight: '800' },
  bTotalVal: { color: '#7C3AED', fontSize: 18, fontWeight: '800' },
  payBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 16, paddingVertical: 14, borderRadius: 12 },
  payText: { color: '#FFFFFF', fontWeight: '800', fontSize: 15 },
  modalDisclaimer: { color: '#94A3B8', fontSize: 11, textAlign: 'center', marginTop: 10 },
});
