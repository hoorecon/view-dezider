/**
 * /decider-store/[id] — public template detail + "Use this template" (clone).
 *
 * Logged-out: tapping "Use" stashes the intent and bounces to /auth/login; after
 * auth, getPostAuthRoute() returns here with ?use=<mode> and we auto-run the clone.
 * Logged-in: clones straight into a prefilled MyDezider decision (/prr/[id]).
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';
import { useAuthStore } from '../../src/store/authStore';
import StoreRating from '../../src/components/StoreRating';
import PolicyConsentModal from '../../src/components/PolicyConsentModal';

const MODE_INFO: Record<string, { label: string; desc: string; icon: string }> = {
  full: { label: 'Full clone', icon: 'layers',
    desc: 'Factors + mandatory/optional grouping + priority + options + option-values — ready to score.' },
  values_only: { label: 'Values only', icon: 'options',
    desc: 'Factors + options + option-values. You classify mandatory/optional and set priorities.' },
};

export default function DeciderStoreDetail() {
  const router = useRouter();
  const { id, use, ref } = useLocalSearchParams<{ id: string; use?: string; ref?: string }>();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const authLoading = useAuthStore((s) => s.isLoading);

  const [t, setT] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<string>('full');
  const [cloning, setCloning] = useState(false);
  const [consentModalMode, setConsentModalMode] = useState<string | null>(null);
  const resumed = useRef(false);

  const load = useCallback(async () => {
    try {
      const r = await api.get(`/decider-store/${id}`);
      setT(r.data);
      const modes: string[] = r.data.allowed_clone_modes || ['full'];
      setMode(modes.includes('full') ? 'full' : modes[0]);
    } catch (e: any) {
      showAlert('Not found', 'This template is unavailable.');
    } finally { setLoading(false); }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const doClone = useCallback(async (m: string) => {
    setCloning(true);
    try {
      const r = await api.post(`/decider-store/${id}/clone`, { mode: m, ref: ref || undefined });
      router.replace(`/prr/${r.data.decision_id}?step=2` as any);
    } catch (e: any) {
      if (e?.response?.status === 402) {
        const d = e.response.data?.detail || {};
        showAlert('Paid template',
          `This template costs ${d.currency === 'INR' ? '₹' : '$'}${((d.price_paise || 0) / 100).toFixed(0)}. Checkout is coming soon.`);
      } else {
        showAlert('Could not open', e?.response?.data?.detail || 'Please try again.');
      }
    } finally { setCloning(false); }
  }, [id, router]);

  const onUse = useCallback(async (m: string) => {
    if (!isAuthenticated) {
      // Two intents preserved:
      //  1. pending_decider_clone → auto-resume the clone in the mode chosen
      //  2. post_auth_next → universal return-to-page (handled by
      //     getPostAuthRoute after any auth path — email/OTP/Google/register)
      await AsyncStorage.setItem('pending_decider_clone', `${id}::${m}`);
      const backTo = `/decider-store/${id}?use=${m}`;
      await AsyncStorage.setItem('post_auth_next', backTo);
      router.push(`/auth/login?next=${encodeURIComponent(backTo)}` as any);
      return;
    }
    // Authenticated → gate on policy consent BEFORE cloning.
    setConsentModalMode(m);
  }, [isAuthenticated, id, router]);

  // Post-login auto-resume: arrived back with ?use=<mode> and now authenticated.
  useEffect(() => {
    if (authLoading || resumed.current) return;
    if (use && isAuthenticated && t) {
      resumed.current = true;
      // Even the post-auth auto-resume passes through the consent modal
      // so no user ever proceeds without agreeing to the publisher's
      // policies — including when the "Use" click happened pre-login.
      setConsentModalMode(String(use));
    }
  }, [use, isAuthenticated, authLoading, t]);

  if (loading) {
    return <SafeAreaView style={s.root}><ActivityIndicator color="#4F46E5" style={{ marginTop: 60 }} /></SafeAreaView>;
  }
  if (!t) {
    return (
      <SafeAreaView style={s.root} edges={['top']}>
        <View style={s.header}><TouchableOpacity onPress={() => safeBack(router, '/decider-store')}><Ionicons name="arrow-back" size={22} color="#0F172A" /></TouchableOpacity></View>
        <Text style={s.empty}>Template unavailable.</Text>
      </SafeAreaView>
    );
  }

  const modes: string[] = t.allowed_clone_modes || ['full'];
  const factors: any[] = t.factors || [];
  const options: any[] = t.options || [];
  const isApp = t.kind === 'app';
  const paid = t.pricing_type === 'paid' && (t.price_paise || 0) > 0;
  const priceStr = paid ? `${t.currency === 'INR' ? '₹' : '$'}${((t.price_paise || 0) / 100).toFixed(0)}` : 'Free';

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity style={s.backBtn} onPress={() => safeBack(router, '/decider-store')}>
          <Ionicons name="arrow-back" size={22} color="#0F172A" />
        </TouchableOpacity>
        <Text style={s.headerTitle} numberOfLines={1}>{t.title}</Text>
      </View>

      <ScrollView contentContainerStyle={s.body}>
        <View style={[s.cover, { backgroundColor: (t.cover_color || '#4F46E5') + '18' }]}>
          <Ionicons name={(t.cover_icon || 'grid') as any} size={40} color={t.cover_color || '#4F46E5'} />
        </View>
        <Text style={s.title}>{t.title}</Text>
        {isApp && (
          <View style={s.finderBanner}>
            <Ionicons name="search-circle" size={16} color="#4F46E5" />
            <Text style={s.finderBannerText}>Finder — set your expectations & priorities, then it auto-ranks the best matches for you.</Text>
          </View>
        )}
        {!!t.subtitle && <Text style={s.subtitle}>{t.subtitle}</Text>}
        <View style={s.chipRow}>
          <View style={[s.stat, { backgroundColor: '#EEF2FF' }]}><Text style={[s.statText, { color: '#4F46E5' }]}>📊 {factors.length} factors</Text></View>
          <View style={[s.stat, { backgroundColor: '#F0FDF4' }]}><Text style={[s.statText, { color: '#166534' }]}>🧩 {options.length} options</Text></View>
          <View style={[s.stat, { backgroundColor: paid ? '#FEF3C7' : '#DCFCE7' }]}><Text style={[s.statText, { color: paid ? '#B45309' : '#166534' }]}>{priceStr}</Text></View>
          <View style={[s.stat, { backgroundColor: '#F1F5F9' }]}><Text style={[s.statText, { color: '#475569' }]}>⬇️ {t.install_count || 0}</Text></View>
        </View>
        {!!t.description && <Text style={s.desc}>{t.description}</Text>}

        {/* Play-Store-style 3-factor rating widget */}
        <StoreRating itemId={t.template_id} isAuthenticated={isAuthenticated} />

        {/* Clone mode chooser */}
        <Text style={s.sectionTitle}>Choose how to start</Text>
        {modes.map((m) => (
          <TouchableOpacity key={m} style={[s.modeCard, mode === m && s.modeCardOn]} onPress={() => setMode(m)} activeOpacity={0.85}>
            <Ionicons name={(MODE_INFO[m]?.icon || 'layers') as any} size={20} color={mode === m ? '#4F46E5' : '#94A3B8'} />
            <View style={{ flex: 1 }}>
              <Text style={[s.modeLabel, mode === m && { color: '#4F46E5' }]}>{MODE_INFO[m]?.label || m}</Text>
              <Text style={s.modeDesc}>{MODE_INFO[m]?.desc || ''}</Text>
            </View>
            <Ionicons name={mode === m ? 'radio-button-on' : 'radio-button-off'} size={20} color={mode === m ? '#4F46E5' : '#CBD5E1'} />
          </TouchableOpacity>
        ))}

        {/* Factors preview */}
        <Text style={s.sectionTitle}>Factors ({factors.length})</Text>
        {factors.slice(0, 12).map((f) => (
          <View key={f.id} style={s.facRow}>
            <View style={{ flex: 1 }}>
              <Text style={s.facName}>{f.name}</Text>
              {(() => {
                const subs = (f.sub_factors || []).map((x: any) => x.name).filter(Boolean);
                const vals = subs.length ? subs : (f.possible_values || []);
                return vals.length ? <Text style={s.facVals} numberOfLines={1}>{vals.join(' · ')}</Text> : null;
              })()}
            </View>
            <View style={[s.typeTag, { backgroundColor: (f.factor_type === 'quantitative') ? '#E0F2FE' : '#F3E8FF' }]}>
              <Text style={[s.typeTagText, { color: (f.factor_type === 'quantitative') ? '#0369A1' : '#9333EA' }]}>
                {f.factor_type === 'quantitative' ? 'Quant' : 'Qual'}
              </Text>
            </View>
          </View>
        ))}
        {factors.length > 12 && <Text style={s.more}>+ {factors.length - 12} more factors</Text>}

        {/* Options preview */}
        <Text style={s.sectionTitle}>Options ({options.length})</Text>
        <View style={s.optWrap}>
          {options.slice(0, 16).map((o) => (
            <View key={o.id} style={s.optPill}><Text style={s.optPillText} numberOfLines={1}>{o.name}</Text></View>
          ))}
          {options.length > 16 && <View style={s.optPill}><Text style={s.optPillText}>+{options.length - 16} more</Text></View>}
        </View>
        <View style={{ height: 100 }} />
      </ScrollView>

      {/* Sticky CTA */}
      <View style={s.footer}>
        <TouchableOpacity style={s.useBtn} onPress={() => onUse(mode)} disabled={cloning}>
          {cloning ? <ActivityIndicator color="#FFF" /> : (
            <>
              <Ionicons name={isAuthenticated ? 'rocket' : 'log-in'} size={18} color="#FFF" />
              <Text style={s.useBtnText}>{isAuthenticated ? (isApp ? 'Use this Finder' : 'Use this template') : 'Sign in to use'}{paid ? ` · ${priceStr}` : ''}</Text>
            </>
          )}
        </TouchableOpacity>
      </View>
      <PolicyConsentModal
        visible={!!consentModalMode}
        onClose={() => { setConsentModalMode(null); resumed.current = false; }}
        onAgree={() => {
          const m = consentModalMode || 'full';
          setConsentModalMode(null);
          doClone(m);
        }}
        item={t}
        actionLabel={isApp ? 'Use this Finder' : 'Use this template'}
      />
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 14, paddingVertical: 12, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#E2E8F0' },
  backBtn: { padding: 4 },
  headerTitle: { flex: 1, fontSize: 16, fontWeight: '800', color: '#0F172A' },
  body: { padding: 16, maxWidth: 720, width: '100%', alignSelf: 'center' },
  cover: { height: 120, borderRadius: 16, alignItems: 'center', justifyContent: 'center', marginBottom: 14 },
  title: { fontSize: 22, fontWeight: '900', color: '#0F172A' },
  subtitle: { fontSize: 14, color: '#64748B', marginTop: 4 },
  finderBanner: { flexDirection: 'row', alignItems: 'center', gap: 7, backgroundColor: '#EEF2FF', borderRadius: 10, padding: 10, marginTop: 10 },
  finderBannerText: { flex: 1, fontSize: 12, color: '#3730A3', fontWeight: '600', lineHeight: 17 },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 12 },
  stat: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 10 },
  statText: { fontSize: 12.5, fontWeight: '700' },
  desc: { fontSize: 13.5, color: '#334155', lineHeight: 20, marginTop: 14 },
  sectionTitle: { fontSize: 15, fontWeight: '800', color: '#0F172A', marginTop: 22, marginBottom: 10 },
  modeCard: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#FFF', borderRadius: 14, padding: 14, borderWidth: 1.5, borderColor: '#E2E8F0', marginBottom: 10 },
  modeCardOn: { borderColor: '#4F46E5', backgroundColor: '#F5F3FF' },
  modeLabel: { fontSize: 14.5, fontWeight: '800', color: '#0F172A' },
  modeDesc: { fontSize: 12, color: '#64748B', marginTop: 2, lineHeight: 17 },
  facRow: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#FFF', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: '#EEF2F7', marginBottom: 6 },
  facName: { fontSize: 13.5, fontWeight: '700', color: '#0F172A' },
  facVals: { fontSize: 11.5, color: '#94A3B8', marginTop: 2 },
  typeTag: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 7 },
  typeTagText: { fontSize: 10.5, fontWeight: '800' },
  more: { fontSize: 12.5, color: '#4F46E5', fontWeight: '700', marginTop: 4 },
  optWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 },
  optPill: { backgroundColor: '#FFF', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 7, maxWidth: '48%' },
  optPillText: { fontSize: 12, color: '#334155', fontWeight: '600' },
  footer: { position: 'absolute', bottom: 0, left: 0, right: 0, backgroundColor: '#FFF', borderTopWidth: 1, borderTopColor: '#E2E8F0', padding: 14 },
  useBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#4F46E5', borderRadius: 14, paddingVertical: 15, maxWidth: 720, width: '100%', alignSelf: 'center' },
  useBtnText: { color: '#FFF', fontSize: 15.5, fontWeight: '800' },
  empty: { textAlign: 'center', color: '#94A3B8', marginTop: 40 },
});
