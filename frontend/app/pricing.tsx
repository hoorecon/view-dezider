/**
 * /pricing — Public 7-Chakra subscription pricing page.
 *
 * Consumes /api/pricing (one-shot: tiers + segments + matrix_rows).
 * Shows: tier cards (price, aspiration, perks), segment chips, and a
 * compact features-by-tier comparison table.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import api from '../src/utils/api';
import { COLORS } from '../src/constants/colors';

interface Tier { key: string; order: number; chakra_sanskrit: string; label: string; aspiration: string; color: string; icon: string; monthly_price_inr: number }
interface MatrixRow { module_id: string; module_name?: string; module_icon?: string; tiers: Record<string, boolean> }
interface Pricing { tier_key: string; country_code: string; currency: string; monthly_price: number; annual_price: number; enabled: boolean }
interface Segment { segment_id: string; name: string; description?: string; chakra_tier_link?: string | null; tier_pricings: Pricing[] }

const SUPPORTED_COUNTRIES = [
  { code: 'IN', currency: 'INR', symbol: '₹',  name: 'India' },
  { code: 'US', currency: 'USD', symbol: '$',  name: 'US' },
  { code: 'GB', currency: 'GBP', symbol: '£',  name: 'UK' },
  { code: 'EU', currency: 'EUR', symbol: '€',  name: 'EU' },
  { code: 'AE', currency: 'AED', symbol: 'AED',name: 'UAE' },
  { code: 'SG', currency: 'SGD', symbol: 'S$', name: 'SG' },
  { code: 'AU', currency: 'AUD', symbol: 'A$', name: 'AU' },
  { code: 'CA', currency: 'CAD', symbol: 'C$', name: 'CA' },
];

export default function PricingScreen() {
  const router = useRouter();
  const [tiers, setTiers] = useState<Tier[]>([]);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [matrixRows, setMatrixRows] = useState<MatrixRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [billing, setBilling] = useState<'monthly' | 'annual'>('monthly');
  const [country, setCountry] = useState<string>('IN');
  const [activeSegment, setActiveSegment] = useState<string | null>(null);
  const [showCompare, setShowCompare] = useState(false);

  const load = useCallback(async () => {
    try { setLoading(true);
      const r = await api.get('/pricing');
      setTiers(r.data.tiers || []);
      setSegments(r.data.segments || []);
      setMatrixRows(r.data.matrix_rows || []);
    } catch (e) { /* network — silent */ }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const countryMeta = useMemo(
    () => SUPPORTED_COUNTRIES.find(c => c.code === country) || SUPPORTED_COUNTRIES[0],
    [country]
  );

  const getPriceForTier = useCallback((tier: Tier): { amount: number; currency: string; symbol: string; source: string } => {
    // 1. If active segment + has pricing for tier+country → use it
    if (activeSegment) {
      const seg = segments.find(s => s.segment_id === activeSegment);
      const p = seg?.tier_pricings.find(p => p.tier_key === tier.key && p.country_code === country && p.enabled);
      if (p) return {
        amount: billing === 'monthly' ? p.monthly_price : p.annual_price,
        currency: p.currency, symbol: countryMeta.symbol, source: 'segment',
      };
    }
    // 2. Fallback: tier's default INR price (only for IN)
    if (country === 'IN') {
      return { amount: tier.monthly_price_inr * (billing === 'annual' ? 10 : 1), currency: 'INR', symbol: '₹', source: 'default' };
    }
    // 3. No pricing for that geography — return 0 / "Contact"
    return { amount: 0, currency: countryMeta.currency, symbol: countryMeta.symbol, source: 'unset' };
  }, [activeSegment, segments, country, billing, countryMeta]);

  const formatPrice = (amount: number, symbol: string) => {
    if (amount === 0) return 'Free';
    if (amount >= 1000) return `${symbol}${(amount / 1000).toFixed(amount % 1000 === 0 ? 0 : 1)}k`;
    return `${symbol}${amount.toFixed(0)}`;
  };

  const moduleCountForTier = useCallback((tierKey: string) => {
    return matrixRows.filter(r => r.tiers[tierKey]).length;
  }, [matrixRows]);

  if (loading) {
    return <SafeAreaView style={s.container}><View style={s.center}><ActivityIndicator color={COLORS.primary} /></View></SafeAreaView>;
  }

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity onPress={() => router.back()}><Ionicons name="arrow-back" size={22} color={COLORS.textPrimary} /></TouchableOpacity>
        <View style={{ flex: 1, marginHorizontal: 12 }}>
          <Text style={s.title}>Pricing</Text>
          <Text style={s.subtitle}>7 chakra tiers · for every aspiration</Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={{ paddingBottom: 60 }}>
        {/* Hero */}
        <View style={s.hero}>
          <Text style={s.heroEyebrow}>Choose your aspiration</Text>
          <Text style={s.heroTitle}>From Freelancer to Fortune Venture</Text>
          <Text style={s.heroSub}>Pricing scales with your stage. Switch tiers anytime.</Text>
        </View>

        {/* Billing + country toggles */}
        <View style={s.toggleBar}>
          <View style={s.billPill}>
            <TouchableOpacity onPress={() => setBilling('monthly')} style={[s.billOpt, billing === 'monthly' && s.billOptActive]}>
              <Text style={[s.billOptText, billing === 'monthly' && s.billOptTextActive]}>Monthly</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => setBilling('annual')} style={[s.billOpt, billing === 'annual' && s.billOptActive]}>
              <Text style={[s.billOptText, billing === 'annual' && s.billOptTextActive]}>Annual</Text>
              <View style={s.savingsBadge}><Text style={s.savingsBadgeText}>save 16%</Text></View>
            </TouchableOpacity>
          </View>
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 12, paddingTop: 6 }}>
          {SUPPORTED_COUNTRIES.map(c => (
            <TouchableOpacity key={c.code} onPress={() => setCountry(c.code)}
              style={[s.countryChip, country === c.code && s.countryChipActive]}>
              <Text style={[s.countryChipText, country === c.code && s.countryChipTextActive]}>{c.symbol} {c.name}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Segment selector (optional) */}
        {segments.length > 0 && (
          <View style={{ paddingHorizontal: 12, marginTop: 14 }}>
            <Text style={s.segHeader}>Built for which segment?</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingTop: 6 }}>
              <TouchableOpacity onPress={() => setActiveSegment(null)}
                style={[s.segChip, !activeSegment && s.segChipActive]}>
                <Text style={[s.segChipText, !activeSegment && s.segChipTextActive]}>All</Text>
              </TouchableOpacity>
              {segments.map(seg => {
                const tierObj = tiers.find(t => t.key === seg.chakra_tier_link);
                return (
                  <TouchableOpacity key={seg.segment_id} onPress={() => setActiveSegment(seg.segment_id)}
                    style={[s.segChip, activeSegment === seg.segment_id && s.segChipActive,
                            tierObj && activeSegment === seg.segment_id && { borderColor: tierObj.color, backgroundColor: tierObj.color + '22' }]}>
                    <Text style={[s.segChipText, activeSegment === seg.segment_id && s.segChipTextActive,
                                  tierObj && activeSegment === seg.segment_id && { color: tierObj.color }]}>{seg.name}</Text>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          </View>
        )}

        {/* Tier cards (vertical scroll) */}
        <View style={{ paddingHorizontal: 12, marginTop: 14 }}>
          {tiers.map(t => {
            const p = getPriceForTier(t);
            const enabled = p.source !== 'unset';
            const moduleCount = moduleCountForTier(t.key);
            return (
              <View key={t.key} style={[s.tierCard, { borderLeftColor: t.color, borderLeftWidth: 4 }]}>
                <View style={s.tierCardHead}>
                  <View style={[s.tierIcon, { backgroundColor: t.color + '22' }]}>
                    <Ionicons name={t.icon as any} size={20} color={t.color} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={[s.tierCardLabel, { color: t.color }]}>{t.label}</Text>
                    <Text style={s.tierCardChakra}>{t.chakra_sanskrit} · {t.aspiration}</Text>
                  </View>
                </View>
                <View style={s.priceBlock}>
                  {enabled ? (
                    <>
                      <Text style={s.priceAmount}>{formatPrice(p.amount, p.symbol)}</Text>
                      <Text style={s.pricePer}>/{billing === 'monthly' ? 'mo' : 'yr'}</Text>
                    </>
                  ) : (
                    <Text style={s.priceContact}>Contact us</Text>
                  )}
                </View>
                <View style={s.perks}>
                  <View style={s.perkRow}>
                    <Ionicons name="checkmark-circle" size={14} color={t.color} />
                    <Text style={s.perkText}>{moduleCount} modules unlocked</Text>
                  </View>
                  <View style={s.perkRow}>
                    <Ionicons name="checkmark-circle" size={14} color={t.color} />
                    <Text style={s.perkText}>{t.aspiration}-grade features</Text>
                  </View>
                  {t.order >= 5 && (
                    <View style={s.perkRow}>
                      <Ionicons name="checkmark-circle" size={14} color={t.color} />
                      <Text style={s.perkText}>Priority support</Text>
                    </View>
                  )}
                  {t.order >= 7 && (
                    <View style={s.perkRow}>
                      <Ionicons name="checkmark-circle" size={14} color={t.color} />
                      <Text style={s.perkText}>White-label + Govt portal</Text>
                    </View>
                  )}
                </View>
                <TouchableOpacity style={[s.cta, { backgroundColor: t.color }]} onPress={() => router.push('/auth/login')}>
                  <Text style={s.ctaText}>{t.monthly_price_inr === 0 ? 'Start free' : 'Choose ' + t.label}</Text>
                  <Ionicons name="arrow-forward" size={14} color="#FFF" />
                </TouchableOpacity>
              </View>
            );
          })}
        </View>

        {/* Compare features */}
        <View style={{ paddingHorizontal: 12, marginTop: 14 }}>
          <TouchableOpacity onPress={() => setShowCompare(!showCompare)} style={s.compareToggle}>
            <Ionicons name={showCompare ? 'chevron-up' : 'chevron-down'} size={14} color={COLORS.primary} />
            <Text style={s.compareText}>{showCompare ? 'Hide' : 'Show'} feature comparison ({matrixRows.length} modules × 7 tiers)</Text>
          </TouchableOpacity>

          {showCompare && (
            <View style={s.compareCard}>
              <ScrollView horizontal showsHorizontalScrollIndicator>
                <View>
                  <View style={s.tableHeaderRow}>
                    <View style={s.modCol}><Text style={s.tableHeaderText}>Module</Text></View>
                    {tiers.map(t => (
                      <View key={t.key} style={[s.tierCol, { backgroundColor: t.color + '15' }]}>
                        <Ionicons name={t.icon as any} size={11} color={t.color} />
                        <Text style={[s.tierColLabel, { color: t.color }]}>{t.label.split(' ')[0]}</Text>
                      </View>
                    ))}
                  </View>
                  {matrixRows.map(row => (
                    <View key={row.module_id} style={s.tableBodyRow}>
                      <View style={s.modCol}><Text style={s.modName} numberOfLines={1}>{row.module_name || row.module_id}</Text></View>
                      {tiers.map(t => (
                        <View key={t.key} style={s.tierCol}>
                          <Ionicons
                            name={row.tiers[t.key] ? 'checkmark' : 'close'}
                            size={14}
                            color={row.tiers[t.key] ? t.color : COLORS.textMuted}
                          />
                        </View>
                      ))}
                    </View>
                  ))}
                </View>
              </ScrollView>
            </View>
          )}
        </View>

        <Text style={s.footer}>All prices exclusive of taxes. INR includes 18% GST.</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingVertical: 10, backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  title: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary },
  subtitle: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },

  hero: { padding: 18, alignItems: 'center', backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  heroEyebrow: { fontSize: 11, fontWeight: '700', color: COLORS.primary, letterSpacing: 1.5, textTransform: 'uppercase' },
  heroTitle: { fontSize: 22, fontWeight: '800', color: COLORS.textPrimary, marginTop: 6, textAlign: 'center' },
  heroSub: { fontSize: 12, color: COLORS.textSecondary, marginTop: 4, textAlign: 'center' },

  toggleBar: { paddingHorizontal: 12, paddingTop: 14, alignItems: 'center' },
  billPill: { flexDirection: 'row', backgroundColor: '#F3F4F6', borderRadius: 22, padding: 4 },
  billOpt: { paddingHorizontal: 18, paddingVertical: 8, borderRadius: 20, flexDirection: 'row', alignItems: 'center', gap: 6 },
  billOptActive: { backgroundColor: COLORS.white },
  billOptText: { fontSize: 12, fontWeight: '700', color: COLORS.textMuted },
  billOptTextActive: { color: COLORS.textPrimary },
  savingsBadge: { backgroundColor: '#10B981', paddingHorizontal: 5, paddingVertical: 2, borderRadius: 8 },
  savingsBadgeText: { color: '#FFF', fontSize: 9, fontWeight: '700' },

  countryChip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 14, borderWidth: 1, borderColor: COLORS.divider, marginRight: 6, backgroundColor: COLORS.white },
  countryChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  countryChipText: { fontSize: 11, color: COLORS.textPrimary, fontWeight: '600' },
  countryChipTextActive: { color: '#FFF' },

  segHeader: { fontSize: 11, fontWeight: '700', color: COLORS.textPrimary, textTransform: 'uppercase', letterSpacing: 0.5 },
  segChip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 14, borderWidth: 1, borderColor: COLORS.divider, marginRight: 6, backgroundColor: COLORS.white },
  segChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  segChipText: { fontSize: 11, color: COLORS.textPrimary, fontWeight: '600' },
  segChipTextActive: { color: '#FFF' },

  tierCard: { backgroundColor: COLORS.white, borderRadius: 12, padding: 14, marginBottom: 12, borderWidth: 1, borderColor: COLORS.divider },
  tierCardHead: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  tierIcon: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  tierCardLabel: { fontSize: 16, fontWeight: '800' },
  tierCardChakra: { fontSize: 11, color: COLORS.textMuted, marginTop: 2 },

  priceBlock: { flexDirection: 'row', alignItems: 'baseline', marginTop: 12, gap: 4 },
  priceAmount: { fontSize: 28, fontWeight: '800', color: COLORS.textPrimary },
  pricePer: { fontSize: 12, color: COLORS.textMuted, fontWeight: '600' },
  priceContact: { fontSize: 18, fontWeight: '700', color: COLORS.textSecondary },

  perks: { marginTop: 10, gap: 6 },
  perkRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  perkText: { fontSize: 12, color: COLORS.textSecondary },

  cta: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 12, borderRadius: 8, marginTop: 12 },
  ctaText: { color: '#FFF', fontSize: 13, fontWeight: '700' },

  compareToggle: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 12 },
  compareText: { color: COLORS.primary, fontSize: 12, fontWeight: '700' },
  compareCard: { backgroundColor: COLORS.white, borderRadius: 10, borderWidth: 1, borderColor: COLORS.divider, overflow: 'hidden' },
  tableHeaderRow: { flexDirection: 'row', borderBottomWidth: 2, borderBottomColor: COLORS.border },
  tableBodyRow: { flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: COLORS.divider },
  modCol: { width: 140, padding: 8, justifyContent: 'center' },
  tableHeaderText: { fontSize: 10, fontWeight: '700', color: COLORS.textPrimary, textTransform: 'uppercase' },
  tierCol: { width: 60, padding: 8, alignItems: 'center', justifyContent: 'center', borderLeftWidth: 1, borderLeftColor: COLORS.divider },
  tierColLabel: { fontSize: 9, fontWeight: '700', marginTop: 2 },
  modName: { fontSize: 11, color: COLORS.textPrimary, fontWeight: '600' },

  footer: { fontSize: 10, color: COLORS.textMuted, textAlign: 'center', marginTop: 18, paddingHorizontal: 12 },
});
