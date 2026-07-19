/**
 * /admaker-studio — advertiser self-serve dashboard (AdMaker Program).
 *
 * SAME user login (no separate auth): access is ACM-gated (`admaker_program`,
 * Premium paid tiers) or granted via an Org advertiser/org_admin role.
 * Solution owners promote THEIR OWN Solution-Store-linked options as
 * "Sponsored Solutions" below organic DeciderApp results. AdRank = bid ×
 * QualityScore, GSP price charged per click.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Modal, RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import api from '../src/utils/api';
import { showAlert } from '../src/utils/alert';
import { safeBack } from '../src/utils/navigation';

const rup = (paise: number) => `₹${((paise || 0) / 100).toFixed(2)}`;

export default function AdMakerStudio() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lockedMsg, setLockedMsg] = useState<string | null>(null);
  const [dash, setDash] = useState<any>(null);
  const [templates, setTemplates] = useState<any[]>([]);

  // create modal
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [tpl, setTpl] = useState('');
  const [eligible, setEligible] = useState<any[]>([]);
  const [eligLoading, setEligLoading] = useState(false);
  const [optName, setOptName] = useState('');
  const [bid, setBid] = useState('');
  const [budget, setBudget] = useState('');
  const [region, setRegion] = useState('global');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');

  const load = useCallback(async () => {
    try {
      const [d, store] = await Promise.all([
        api.get('/admaker/my/dashboard'),
        api.get('/decider-store').catch(() => ({ data: {} })),
      ]);
      setDash(d.data);
      setLockedMsg(null);
      setTemplates(store.data.templates || []);
    } catch (e: any) {
      if (e?.response?.status === 403) setLockedMsg(e.response.data?.detail || 'AdMaker Studio needs a Premium plan.');
      else showAlert('Load failed', e?.response?.data?.detail || 'Try again');
    } finally { setLoading(false); setRefreshing(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const pickTemplate = async (tid: string) => {
    setTpl(tid); setOptName(''); setEligible([]); setEligLoading(true);
    try {
      const r = await api.get(`/admaker/my/eligible-options?template_id=${tid}`);
      setEligible(r.data.options || []);
    } catch (e: any) {
      showAlert('Failed', e?.response?.data?.detail || 'Try again');
    } finally { setEligLoading(false); }
  };

  const openCreate = () => {
    setOpen(true); setOptName(''); setBid(''); setBudget(''); setRegion('global');
    setStart(''); setEnd('');
    const first = templates.find(t => t.kind === 'app') || templates[0];
    if (first) pickTemplate(first.template_id);
  };

  const create = async () => {
    const paise = Math.round((parseFloat(bid) || 0) * 100);
    if (!optName) return showAlert('Pick an option', 'Choose which of your listings to promote.');
    if (paise < 1) return showAlert('Bid required', 'Set a bid of at least ₹0.01 per click.');
    setBusy(true);
    try {
      await api.post('/admaker/my/bids', {
        template_id: tpl, option_name: optName, bid_paise: paise,
        budget_paise: Math.round((parseFloat(budget) || 0) * 100),
        region: region.trim() || 'global',
        slot_start: start.trim() || null, slot_end: end.trim() || null,
      });
      setOpen(false); load();
    } catch (e: any) {
      showAlert('Create failed', e?.response?.data?.detail || 'Try again');
    } finally { setBusy(false); }
  };

  const toggle = async (b: any) => {
    try {
      await api.put(`/admaker/my/bids/${b.bid_id}`, { status: b.status === 'active' ? 'paused' : 'active' });
      load();
    } catch (e: any) { showAlert('Failed', e?.response?.data?.detail || 'Try again'); }
  };
  const remove = (b: any) => {
    showAlert('Delete bid?', b.option_name, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await api.delete(`/admaker/my/bids/${b.bid_id}`); load(); }
        catch (e: any) { showAlert('Failed', e?.response?.data?.detail || 'Try again'); }
      } },
    ]);
  };

  const T = dash?.totals;

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity style={s.backBtn} onPress={() => safeBack(router, '/')}>
          <Ionicons name="arrow-back" size={22} color="#0F172A" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.title}>AdMaker Studio</Text>
          <Text style={s.sub}>Promote your solutions as Sponsored results</Text>
        </View>
      </View>

      {loading ? <ActivityIndicator color="#B45309" style={{ marginTop: 48 }} /> : lockedMsg ? (
        <View style={s.lockWrap}>
          <Ionicons name="lock-closed" size={40} color="#B45309" />
          <Text style={s.lockTitle}>AdMaker Studio is a Premium feature</Text>
          <Text style={s.lockMsg}>{lockedMsg}</Text>
          <TouchableOpacity style={s.upgradeBtn} onPress={() => router.push('/subscription' as any)}>
            <Text style={s.upgradeText}>See plans</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <ScrollView contentContainerStyle={s.body}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} />}>
          {/* metrics */}
          <View style={s.metricsRow}>
            {[['Impressions', (T?.impressions || 0).toLocaleString()],
              ['Clicks', `${(T?.clicks || 0).toLocaleString()} · ${T?.ctr_pct || 0}%`],
              ['Spend', rup(T?.spend_paise || 0)],
              ['Avg CPC', rup(T?.avg_cpc_paise || 0)]].map(([label, val]) => (
              <View key={label} style={s.metric}>
                <Text style={s.metricVal}>{val}</Text>
                <Text style={s.metricLabel}>{label}</Text>
              </View>
            ))}
          </View>

          <TouchableOpacity style={s.primaryBtn} onPress={openCreate}>
            <Ionicons name="add" size={16} color="#FFF" /><Text style={s.primaryText}>New Sponsored bid</Text>
          </TouchableOpacity>
          <Text style={s.hint}>
            You can only promote options linked to YOUR Solution-Store listings. Ads always appear
            BELOW organic results and only when they clear the user&apos;s quality cutoff.
          </Text>

          {(dash?.bids || []).length === 0 ? (
            <Text style={s.empty}>No bids yet — place your first Sponsored bid.</Text>
          ) : dash.bids.map((b: any) => (
            <View key={b.bid_id} style={s.card}>
              <View style={s.rowHead}>
                <Text style={s.rowTitle} numberOfLines={1}>{b.option_name}</Text>
                <View style={[s.badge, { backgroundColor: b.status === 'active' ? '#DCFCE7' : b.status === 'exhausted' ? '#FEE2E2' : '#FEF3C7' }]}>
                  <Text style={[s.badgeText, { color: b.status === 'active' ? '#166534' : b.status === 'exhausted' ? '#DC2626' : '#B45309' }]}>{String(b.status).toUpperCase()}</Text>
                </View>
              </View>
              <Text style={s.rowSub} numberOfLines={1}>{b.template_title} · 🌍 {b.region || 'global'}</Text>
              <View style={s.metaRow}>
                <Text style={s.meta}>💰 {rup(b.bid_paise)}/click</Text>
                <Text style={s.meta}>👁 {b.impressions || 0}</Text>
                <Text style={s.meta}>👆 {b.clicks || 0} ({b.ctr_pct || 0}%)</Text>
                <Text style={s.meta}>💸 {rup(b.spent_paise || 0)}{b.budget_paise ? ` / ${rup(b.budget_paise)}` : ''}</Text>
                <Text style={s.meta}>⚖️ CPC {rup(b.avg_cpc_paise || 0)}</Text>
              </View>
              <View style={s.actions}>
                <TouchableOpacity style={[s.act, { backgroundColor: '#FEF9C3' }]} onPress={() => toggle(b)}>
                  <Ionicons name={b.status === 'active' ? 'pause' : 'play'} size={13} color="#A16207" />
                  <Text style={[s.actText, { color: '#A16207' }]}>{b.status === 'active' ? 'Pause' : 'Activate'}</Text>
                </TouchableOpacity>
                <TouchableOpacity style={[s.act, { backgroundColor: '#FEE2E2' }]} onPress={() => remove(b)}>
                  <Ionicons name="trash" size={13} color="#DC2626" /><Text style={[s.actText, { color: '#DC2626' }]}>Delete</Text>
                </TouchableOpacity>
              </View>
            </View>
          ))}
          <View style={{ height: 40 }} />
        </ScrollView>
      )}

      {/* create modal */}
      <Modal visible={open} transparent animationType="slide" onRequestClose={() => setOpen(false)}>
        <View style={s.overlay}>
          <View style={s.sheet}>
            <View style={s.mHead}>
              <Text style={s.mTitle}>New Sponsored bid</Text>
              <TouchableOpacity onPress={() => setOpen(false)}><Ionicons name="close" size={22} color="#64748B" /></TouchableOpacity>
            </View>
            <ScrollView style={{ maxHeight: 460 }}>
              <Text style={s.label}>Decider App</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 6 }}>
                {templates.map(t => (
                  <TouchableOpacity key={t.template_id} style={[s.chip, tpl === t.template_id && s.chipOn]} onPress={() => pickTemplate(t.template_id)}>
                    <Text style={[s.chipText, tpl === t.template_id && { color: '#FFF' }]} numberOfLines={1}>
                      {t.kind === 'app' ? '🔍 ' : ''}{t.title}
                    </Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
              <Text style={s.label}>Your option to promote *</Text>
              {eligLoading ? <ActivityIndicator color="#B45309" style={{ marginVertical: 10 }} /> :
                eligible.length === 0 ? (
                  <Text style={s.noneText}>
                    No options in this app are linked to your Solution-Store listings yet.
                    Publish a solution first (Solution Space → Solutions Store).
                  </Text>
                ) : (
                  <View style={s.suggestWrap}>
                    {eligible.map((o: any) => (
                      <TouchableOpacity key={o.option_name} style={[s.suggest, optName === o.option_name && s.suggestOn]} onPress={() => setOptName(o.option_name)}>
                        <Text style={[s.suggestText, optName === o.option_name && { color: '#FFF' }]} numberOfLines={1}>{o.option_name}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                )}
              <View style={s.row2}>
                <View style={{ flex: 1 }}><Text style={s.label}>Bid ₹/click *</Text>
                  <TextInput style={s.input} value={bid} onChangeText={setBid} keyboardType="numeric" placeholder="5.00" placeholderTextColor="#9CA3AF" /></View>
                <View style={{ flex: 1 }}><Text style={s.label}>Budget ₹ (0 = ∞)</Text>
                  <TextInput style={s.input} value={budget} onChangeText={setBudget} keyboardType="numeric" placeholder="0" placeholderTextColor="#9CA3AF" /></View>
                <View style={{ flex: 1 }}><Text style={s.label}>Region</Text>
                  <TextInput style={s.input} value={region} onChangeText={setRegion} autoCapitalize="none" placeholder="global" placeholderTextColor="#9CA3AF" /></View>
              </View>
              <View style={s.row2}>
                <View style={{ flex: 1 }}><Text style={s.label}>From (opt.)</Text>
                  <TextInput style={s.input} value={start} onChangeText={setStart} autoCapitalize="none" placeholder="2026-08-01" placeholderTextColor="#9CA3AF" /></View>
                <View style={{ flex: 1 }}><Text style={s.label}>To (opt.)</Text>
                  <TextInput style={s.input} value={end} onChangeText={setEnd} autoCapitalize="none" placeholder="2026-08-31" placeholderTextColor="#9CA3AF" /></View>
              </View>
              <TouchableOpacity style={s.primaryBtn} onPress={create} disabled={busy}>
                {busy ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={s.primaryText}>Place bid</Text>}
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 16, paddingVertical: 12, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#E2E8F0' },
  backBtn: { padding: 4 },
  title: { fontSize: 18, fontWeight: '800', color: '#0F172A' },
  sub: { fontSize: 12, color: '#64748B', marginTop: 1 },
  body: { padding: 16, maxWidth: 760, width: '100%', alignSelf: 'center' },
  lockWrap: { alignItems: 'center', padding: 32, marginTop: 40 },
  lockTitle: { fontSize: 17, fontWeight: '800', color: '#0F172A', marginTop: 14, textAlign: 'center' },
  lockMsg: { fontSize: 13, color: '#64748B', marginTop: 8, textAlign: 'center', lineHeight: 19 },
  upgradeBtn: { backgroundColor: '#B45309', borderRadius: 12, paddingVertical: 12, paddingHorizontal: 28, marginTop: 18 },
  upgradeText: { color: '#FFF', fontSize: 14, fontWeight: '800' },
  metricsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 12 },
  metric: { flexGrow: 1, minWidth: 150, backgroundColor: '#FFF', borderRadius: 14, borderWidth: 1, borderColor: '#E2E8F0', padding: 14 },
  metricVal: { fontSize: 18, fontWeight: '900', color: '#0F172A' },
  metricLabel: { fontSize: 11.5, color: '#64748B', fontWeight: '700', marginTop: 3 },
  primaryBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#B45309', borderRadius: 12, paddingVertical: 12, marginTop: 8 },
  primaryText: { color: '#FFF', fontSize: 14, fontWeight: '800' },
  hint: { fontSize: 11.5, color: '#64748B', lineHeight: 16, marginTop: 10, marginBottom: 12 },
  empty: { textAlign: 'center', color: '#94A3B8', paddingVertical: 24 },
  card: { backgroundColor: '#FFF', borderRadius: 14, padding: 16, borderWidth: 1, borderColor: '#E2E8F0', marginBottom: 12 },
  rowHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  rowTitle: { flex: 1, fontSize: 14.5, fontWeight: '800', color: '#0F172A' },
  rowSub: { fontSize: 12, color: '#64748B', marginTop: 2 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999 },
  badgeText: { fontSize: 10, fontWeight: '900', letterSpacing: 0.4 },
  metaRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 8 },
  meta: { fontSize: 11.5, color: '#475569', fontWeight: '600' },
  actions: { flexDirection: 'row', gap: 8, marginTop: 12 },
  act: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingVertical: 7, paddingHorizontal: 10, borderRadius: 9 },
  actText: { fontSize: 12, fontWeight: '700' },
  overlay: { flex: 1, backgroundColor: 'rgba(15,23,42,0.5)', justifyContent: 'center', padding: 20 },
  sheet: { backgroundColor: '#FFF', borderRadius: 16, padding: 18, maxWidth: 560, width: '100%', alignSelf: 'center' },
  mHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 },
  mTitle: { fontSize: 16, fontWeight: '800', color: '#0F172A' },
  label: { fontSize: 11.5, fontWeight: '700', color: '#475569', marginTop: 10, marginBottom: 4 },
  input: { backgroundColor: '#F8FAFC', borderRadius: 10, borderWidth: 1, borderColor: '#E2E8F0', paddingHorizontal: 12, paddingVertical: 9, fontSize: 14, color: '#0F172A' },
  row2: { flexDirection: 'row', gap: 10 },
  chip: { paddingVertical: 7, paddingHorizontal: 12, borderRadius: 999, backgroundColor: '#F1F5F9', marginRight: 6, maxWidth: 220 },
  chipOn: { backgroundColor: '#B45309' },
  chipText: { fontSize: 12, fontWeight: '700', color: '#475569' },
  suggestWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 4 },
  suggest: { backgroundColor: '#FEF3C7', borderRadius: 999, paddingVertical: 6, paddingHorizontal: 11, maxWidth: 260 },
  suggestOn: { backgroundColor: '#B45309' },
  suggestText: { fontSize: 12, fontWeight: '700', color: '#B45309' },
  noneText: { fontSize: 12, color: '#64748B', lineHeight: 17, backgroundColor: '#F8FAFC', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: '#E2E8F0' },
});
