/**
 * /admin/ad-programs — AdMaker & AdTaker console.
 *
 * AdMaker  — AdWords-style bids: advertisers bid on a Decider App option for a
 *            region + time slot. Options must clear the Min-Cutoff % quality
 *            gate; AdRank = bid × QualityScore; GSP price charged per click.
 * AdTaker  — AdSense-style publishers: mint tracker IDs, copy the widget
 *            embed snippet, watch impressions / clicks / conversions and the
 *            revenue-share earnings estimate.
 * Cutoffs  — global Sponsored defaults + per-CCM-node overrides (inherited by
 *            all descendant nodes unless a deeper node overrides).
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Modal,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import * as Clipboard from 'expo-clipboard';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';
import { safeBack } from '../../src/utils/navigation';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

type Bid = {
  bid_id: string; template_id: string; template_title?: string; option_name: string;
  advertiser_name: string; region: string; bid_paise: number; budget_paise?: number;
  spent_paise?: number; impressions?: number; clicks?: number; last_price_paise?: number | null;
  slot_start?: string | null; slot_end?: string | null;
  daily_start_hour?: number | null; daily_end_hour?: number | null;
  timezone?: string; status: string;
};
type Publisher = {
  publisher_id: string; tracker_id: string; name: string; site_url?: string;
  revenue_share_pct: number; status: string;
  totals?: { impressions: number; clicks: number; conversions: number };
};

const rup = (paise: number) => `₹${((paise || 0) / 100).toFixed(2)}`;

export default function AdminAdPrograms() {
  const router = useRouter();
  const [tab, setTab] = useState<'bids' | 'publishers' | 'cutoffs'>('bids');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const [bids, setBids] = useState<Bid[]>([]);
  const [pubs, setPubs] = useState<Publisher[]>([]);
  const [templates, setTemplates] = useState<any[]>([]);
  const [nodes, setNodes] = useState<any[]>([]);

  // bid modal
  const [bidOpen, setBidOpen] = useState(false);
  const [editBid, setEditBid] = useState<Bid | null>(null);
  const [bTemplate, setBTemplate] = useState('');
  const [bOption, setBOption] = useState('');
  const [bAdvertiser, setBAdvertiser] = useState('');
  const [bRegion, setBRegion] = useState('global');
  const [bBid, setBBid] = useState('');       // rupees
  const [bBudget, setBBudget] = useState(''); // rupees
  const [bStart, setBStart] = useState('');
  const [bEnd, setBEnd] = useState('');
  const [bHourS, setBHourS] = useState('');
  const [bHourE, setBHourE] = useState('');
  const [bTz, setBTz] = useState('Asia/Kolkata');

  // publisher modal
  const [pubOpen, setPubOpen] = useState(false);
  const [editPub, setEditPub] = useState<Publisher | null>(null);
  const [pName, setPName] = useState('');
  const [pSite, setPSite] = useState('');
  const [pShare, setPShare] = useState('68');

  // snippet modal
  const [snipPub, setSnipPub] = useState<Publisher | null>(null);
  const [snipApp, setSnipApp] = useState('');

  // stats expand
  const [statsFor, setStatsFor] = useState<string | null>(null);
  const [stats, setStats] = useState<any>(null);

  // cutoffs tab
  const [gCutoff, setGCutoff] = useState('60');
  const [gSponsN, setGSponsN] = useState('3');
  const [nodeSearch, setNodeSearch] = useState('');
  const [selNode, setSelNode] = useState<any>(null);
  const [nCutoff, setNCutoff] = useState('');
  const [nSponsN, setNSponsN] = useState('');
  const [effective, setEffective] = useState<any>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [b, p, t, cfg] = await Promise.all([
        api.get('/admaker/bids'),
        api.get('/adtaker/publishers'),
        api.get('/decider-store/admin/all'),
        api.get('/admin/ai-wallet/config').catch(() => ({ data: {} })),
      ]);
      setBids(b.data.bids || []);
      setPubs(p.data.publishers || []);
      const ts = (t.data.templates || []).slice()
        .sort((a: any, x: any) => (a.kind === 'app' ? -1 : 0) - (x.kind === 'app' ? -1 : 0));
      setTemplates(ts);
      const c = cfg.data || {};
      setGCutoff(String(c.finder_min_cutoff_pct ?? 60));
      setGSponsN(String(c.finder_sponsored_n ?? 3));
    } catch (e: any) {
      showAlert('Load failed', e?.response?.data?.detail || 'Try again');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const loadNodes = useCallback(async () => {
    if (nodes.length) return;
    try {
      const r = await api.get('/catalog/nodes?is_active=true');
      setNodes(r.data.items || []);
    } catch { /* non-fatal */ }
  }, [nodes.length]);

  useEffect(() => { if (tab === 'cutoffs') loadNodes(); }, [tab, loadNodes]);

  // ── AdMaker ──────────────────────────────────────────────
  const openBid = (b?: Bid) => {
    setEditBid(b || null);
    setBTemplate(b?.template_id || templates.find(t => t.kind === 'app')?.template_id || templates[0]?.template_id || '');
    setBOption(b?.option_name || '');
    setBAdvertiser(b?.advertiser_name || '');
    setBRegion(b?.region || 'global');
    setBBid(b ? String(b.bid_paise / 100) : '');
    setBBudget(b?.budget_paise ? String(b.budget_paise / 100) : '');
    setBStart(b?.slot_start || '');
    setBEnd(b?.slot_end || '');
    setBHourS(b?.daily_start_hour != null ? String(b.daily_start_hour) : '');
    setBHourE(b?.daily_end_hour != null ? String(b.daily_end_hour) : '');
    setBTz(b?.timezone || 'Asia/Kolkata');
    setBidOpen(true);
  };
  const saveBid = async () => {
    const paise = Math.round((parseFloat(bBid) || 0) * 100);
    if (!bOption.trim()) return showAlert('Option required', 'Which option is being promoted?');
    if (!bAdvertiser.trim()) return showAlert('Advertiser required', 'Who is paying for this bid?');
    if (paise < 1) return showAlert('Bid required', 'Set a bid of at least ₹0.01 per click.');
    setBusy(true);
    const payload: any = {
      template_id: bTemplate, option_name: bOption.trim(), advertiser_name: bAdvertiser.trim(),
      region: bRegion.trim() || 'global', bid_paise: paise,
      budget_paise: Math.round((parseFloat(bBudget) || 0) * 100),
      slot_start: bStart.trim() || null, slot_end: bEnd.trim() || null,
      daily_start_hour: bHourS.trim() === '' ? null : parseInt(bHourS),
      daily_end_hour: bHourE.trim() === '' ? null : parseInt(bHourE),
      timezone: bTz.trim() || 'Asia/Kolkata',
    };
    try {
      if (editBid) await api.put(`/admaker/bids/${editBid.bid_id}`, payload);
      else await api.post('/admaker/bids', payload);
      setBidOpen(false); load();
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || 'Try again');
    } finally { setBusy(false); }
  };
  const toggleBid = async (b: Bid) => {
    try {
      await api.put(`/admaker/bids/${b.bid_id}`, { status: b.status === 'active' ? 'paused' : 'active' });
      load();
    } catch (e: any) { showAlert('Failed', e?.response?.data?.detail || 'Try again'); }
  };
  const deleteBid = (b: Bid) => {
    showAlert('Delete bid?', `${b.advertiser_name} → ${b.option_name}`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await api.delete(`/admaker/bids/${b.bid_id}`); load(); }
        catch (e: any) { showAlert('Failed', e?.response?.data?.detail || 'Try again'); }
      } },
    ]);
  };

  const optionSuggestions = useMemo(() => {
    const t = templates.find(x => x.template_id === bTemplate);
    const names: string[] = (t?.options || []).map((o: any) => o.name).filter(Boolean);
    const q = bOption.trim().toLowerCase();
    return names.filter(n => !q || n.toLowerCase().includes(q)).slice(0, 8);
  }, [templates, bTemplate, bOption]);

  // ── AdTaker ──────────────────────────────────────────────
  const openPub = (p?: Publisher) => {
    setEditPub(p || null);
    setPName(p?.name || ''); setPSite(p?.site_url || '');
    setPShare(p ? String(p.revenue_share_pct) : '68');
    setPubOpen(true);
  };
  const savePub = async () => {
    if (!pName.trim()) return showAlert('Name required', 'Give the publisher a name.');
    setBusy(true);
    const payload = { name: pName.trim(), site_url: pSite.trim(), revenue_share_pct: parseFloat(pShare) || 68 };
    try {
      if (editPub) await api.put(`/adtaker/publishers/${editPub.publisher_id}`, payload);
      else {
        const r = await api.post('/adtaker/publishers', payload);
        showAlert('Publisher created', `Tracker ID: ${r.data.tracker_id}`);
      }
      setPubOpen(false); load();
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || 'Try again');
    } finally { setBusy(false); }
  };
  const togglePub = async (p: Publisher) => {
    try {
      await api.put(`/adtaker/publishers/${p.publisher_id}`, { status: p.status === 'active' ? 'paused' : 'active' });
      load();
    } catch (e: any) { showAlert('Failed', e?.response?.data?.detail || 'Try again'); }
  };
  const deletePub = (p: Publisher) => {
    showAlert('Delete publisher?', p.name, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await api.delete(`/adtaker/publishers/${p.publisher_id}`); load(); }
        catch (e: any) { showAlert('Failed', e?.response?.data?.detail || 'Try again'); }
      } },
    ]);
  };
  const openStats = async (p: Publisher) => {
    if (statsFor === p.publisher_id) { setStatsFor(null); return; }
    setStatsFor(p.publisher_id); setStats(null);
    try {
      const r = await api.get(`/adtaker/publishers/${p.publisher_id}/stats?days=30`);
      setStats(r.data);
    } catch (e: any) { showAlert('Stats failed', e?.response?.data?.detail || 'Try again'); }
  };
  const snippetText = useMemo(() => {
    if (!snipPub || !snipApp) return '';
    return `<script src="${API_URL}/api/adtaker/widget.js?tracker=${snipPub.tracker_id}&app=${snipApp}"></script>`;
  }, [snipPub, snipApp]);
  const copy = async (text: string, label: string) => {
    await Clipboard.setStringAsync(text);
    showAlert('Copied', label);
  };

  // ── Cutoffs ──────────────────────────────────────────────
  const saveGlobals = async () => {
    setBusy(true);
    try {
      await api.put('/admin/ai-wallet/config', {
        finder_min_cutoff_pct: Math.max(0, Math.min(100, parseFloat(gCutoff) || 0)),
        finder_sponsored_n: gSponsN.trim() === '' ? 3 : Math.max(0, parseInt(gSponsN) || 0),
      });
      showAlert('Saved', 'Global Sponsored defaults updated.');
    } catch (e: any) {
      showAlert('Save failed', e?.response?.status === 403
        ? 'Needs Super-Admin.' : (e?.response?.data?.detail || 'Try again'));
    } finally { setBusy(false); }
  };
  const pickNode = async (n: any) => {
    setSelNode(n); setEffective(null);
    const fac = n.finder_ad_config || {};
    setNCutoff(fac.min_cutoff_pct != null ? String(fac.min_cutoff_pct) : '');
    setNSponsN(fac.sponsored_n != null ? String(fac.sponsored_n) : '');
    try {
      const r = await api.get(`/admaker/resolve-config?node_id=${n.node_id}`);
      setEffective(r.data);
    } catch { /* non-fatal */ }
  };
  const saveNode = async () => {
    if (!selNode) return;
    setBusy(true);
    try {
      const r = await api.put(`/catalog/nodes/${selNode.node_id}`, {
        finder_min_cutoff_pct: nCutoff.trim() === '' ? -1 : Math.max(0, Math.min(100, parseFloat(nCutoff) || 0)),
        finder_sponsored_n: nSponsN.trim() === '' ? -1 : Math.max(0, parseInt(nSponsN) || 0),
      });
      setNodes(prev => prev.map(x => (x.node_id === selNode.node_id ? r.data : x)));
      await pickNode(r.data);
      showAlert('Saved', 'Node override updated (blank = inherit from parent/global).');
    } catch (e: any) {
      showAlert('Save failed', e?.response?.data?.detail || 'Try again');
    } finally { setBusy(false); }
  };
  const filteredNodes = useMemo(() => {
    const q = nodeSearch.trim().toLowerCase();
    const base = q ? nodes.filter(n =>
      (n.name || '').toLowerCase().includes(q) || (n.node_id || '').toLowerCase().includes(q)) : nodes;
    return base.slice(0, 40);
  }, [nodes, nodeSearch]);

  const srcLabel = (src: any) =>
    src === 'global' ? 'Global default' : src === 'template' ? 'Template override' : (src?.name ? `Node: ${src.name}` : '—');

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      <View style={s.header}>
        <TouchableOpacity style={s.backBtn} onPress={() => safeBack(router, '/admin')}>
          <Ionicons name="arrow-back" size={22} color="#0F172A" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.title}>AdMaker & AdTaker</Text>
          <Text style={s.sub}>Sponsored Solutions auction · publisher widgets · cutoffs</Text>
        </View>
      </View>

      <View style={s.tabs}>
        {([['bids', 'megaphone', 'AdMaker Bids'], ['publishers', 'globe', 'AdTaker Publishers'], ['cutoffs', 'options', 'Cutoffs & Slots']] as const).map(([k, icon, label]) => (
          <TouchableOpacity key={k} style={[s.tabBtn, tab === k && s.tabOn]} onPress={() => setTab(k)}>
            <Ionicons name={icon as any} size={14} color={tab === k ? '#FFF' : '#475569'} />
            <Text style={[s.tabText, tab === k && { color: '#FFF' }]}>{label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? <ActivityIndicator color="#4F46E5" style={{ marginTop: 40 }} /> : (
        <ScrollView contentContainerStyle={s.body}>
          {/* ═══════════ AdMaker ═══════════ */}
          {tab === 'bids' && (
            <>
              <View style={s.card}>
                <Text style={s.cardTitle}>How AdMaker works</Text>
                <Text style={s.help}>
                  Bids compete ONLY among options that clear the Min-Cutoff % quality gate.
                  AdRank = bid × QualityScore (suitability ÷ 100) — money can&apos;t rescue a bad match.
                  Winners pay the Generalized Second-Price per click and render BELOW the organic list.
                </Text>
                <TouchableOpacity style={s.primaryBtn} onPress={() => openBid()}>
                  <Ionicons name="add" size={16} color="#FFF" /><Text style={s.primaryText}>New bid</Text>
                </TouchableOpacity>
              </View>
              {bids.length === 0 ? <Text style={s.empty}>No bids yet.</Text> : bids.map(b => (
                <View key={b.bid_id} style={s.card}>
                  <View style={s.rowHead}>
                    <Text style={s.rowTitle} numberOfLines={1}>{b.advertiser_name} → {b.option_name}</Text>
                    <View style={[s.badge, { backgroundColor: b.status === 'active' ? '#DCFCE7' : b.status === 'exhausted' ? '#FEE2E2' : '#FEF3C7' }]}>
                      <Text style={[s.badgeText, { color: b.status === 'active' ? '#166534' : b.status === 'exhausted' ? '#DC2626' : '#B45309' }]}>{b.status.toUpperCase()}</Text>
                    </View>
                  </View>
                  <Text style={s.rowSub} numberOfLines={1}>{b.template_title}</Text>
                  <View style={s.metaRow}>
                    <Text style={s.meta}>💰 {rup(b.bid_paise)}/click max</Text>
                    <Text style={s.meta}>🌍 {b.region || 'global'}</Text>
                    {(b.slot_start || b.slot_end) && <Text style={s.meta}>📅 {b.slot_start || '…'} → {b.slot_end || '…'}</Text>}
                    {b.daily_start_hour != null && <Text style={s.meta}>🕐 {b.daily_start_hour}–{b.daily_end_hour}h {b.timezone}</Text>}
                  </View>
                  <View style={s.metaRow}>
                    <Text style={s.meta}>👁 {b.impressions || 0} impr</Text>
                    <Text style={s.meta}>👆 {b.clicks || 0} clicks</Text>
                    <Text style={s.meta}>💸 {rup(b.spent_paise || 0)} spent{b.budget_paise ? ` / ${rup(b.budget_paise)}` : ''}</Text>
                    {b.last_price_paise != null && <Text style={s.meta}>⚖️ GSP {rup(b.last_price_paise)}</Text>}
                  </View>
                  <View style={s.actions}>
                    <TouchableOpacity style={[s.act, { backgroundColor: '#EEF2FF' }]} onPress={() => openBid(b)}>
                      <Ionicons name="create" size={13} color="#4F46E5" /><Text style={[s.actText, { color: '#4F46E5' }]}>Edit</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={[s.act, { backgroundColor: '#FEF9C3' }]} onPress={() => toggleBid(b)}>
                      <Ionicons name={b.status === 'active' ? 'pause' : 'play'} size={13} color="#A16207" />
                      <Text style={[s.actText, { color: '#A16207' }]}>{b.status === 'active' ? 'Pause' : 'Activate'}</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={[s.act, { backgroundColor: '#FEE2E2' }]} onPress={() => deleteBid(b)}>
                      <Ionicons name="trash" size={13} color="#DC2626" /><Text style={[s.actText, { color: '#DC2626' }]}>Delete</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              ))}
            </>
          )}

          {/* ═══════════ AdTaker ═══════════ */}
          {tab === 'publishers' && (
            <>
              <View style={s.card}>
                <Text style={s.cardTitle}>How AdTaker works</Text>
                <Text style={s.help}>
                  Mint a tracker ID per publisher (like AdSense&apos;s pub-XXXX). They paste the widget
                  snippet on their site; every impression, click and attributed install (&quot;conversion&quot;)
                  is measured per tracker, and the publisher earns the configured revenue share.
                </Text>
                <TouchableOpacity style={s.primaryBtn} onPress={() => openPub()}>
                  <Ionicons name="add" size={16} color="#FFF" /><Text style={s.primaryText}>New publisher</Text>
                </TouchableOpacity>
              </View>
              {pubs.length === 0 ? <Text style={s.empty}>No publishers yet.</Text> : pubs.map(p => (
                <View key={p.publisher_id} style={s.card}>
                  <View style={s.rowHead}>
                    <Text style={s.rowTitle} numberOfLines={1}>{p.name}</Text>
                    <View style={[s.badge, { backgroundColor: p.status === 'active' ? '#DCFCE7' : '#FEF3C7' }]}>
                      <Text style={[s.badgeText, { color: p.status === 'active' ? '#166534' : '#B45309' }]}>{p.status.toUpperCase()}</Text>
                    </View>
                  </View>
                  {!!p.site_url && <Text style={s.rowSub} numberOfLines={1}>{p.site_url}</Text>}
                  <TouchableOpacity style={s.trackerRow} onPress={() => copy(p.tracker_id, 'Tracker ID copied')}>
                    <Text style={s.tracker}>{p.tracker_id}</Text>
                    <Ionicons name="copy-outline" size={14} color="#4F46E5" />
                  </TouchableOpacity>
                  <View style={s.metaRow}>
                    <Text style={s.meta}>🤝 {p.revenue_share_pct}% share</Text>
                    <Text style={s.meta}>👁 {p.totals?.impressions || 0}</Text>
                    <Text style={s.meta}>👆 {p.totals?.clicks || 0}</Text>
                    <Text style={s.meta}>✅ {p.totals?.conversions || 0} installs</Text>
                  </View>
                  <View style={s.actions}>
                    <TouchableOpacity style={[s.act, { backgroundColor: '#E0F2FE' }]} onPress={() => { setSnipPub(p); setSnipApp(templates.find(t => t.kind === 'app')?.template_id || templates[0]?.template_id || ''); }}>
                      <Ionicons name="code-slash" size={13} color="#0369A1" /><Text style={[s.actText, { color: '#0369A1' }]}>Snippet</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={[s.act, { backgroundColor: '#F3E8FF' }]} onPress={() => openStats(p)}>
                      <Ionicons name="stats-chart" size={13} color="#9333EA" /><Text style={[s.actText, { color: '#9333EA' }]}>Stats</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={[s.act, { backgroundColor: '#EEF2FF' }]} onPress={() => openPub(p)}>
                      <Ionicons name="create" size={13} color="#4F46E5" /><Text style={[s.actText, { color: '#4F46E5' }]}>Edit</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={[s.act, { backgroundColor: '#FEF9C3' }]} onPress={() => togglePub(p)}>
                      <Ionicons name={p.status === 'active' ? 'pause' : 'play'} size={13} color="#A16207" />
                      <Text style={[s.actText, { color: '#A16207' }]}>{p.status === 'active' ? 'Pause' : 'Activate'}</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={[s.act, { backgroundColor: '#FEE2E2' }]} onPress={() => deletePub(p)}>
                      <Ionicons name="trash" size={13} color="#DC2626" /><Text style={[s.actText, { color: '#DC2626' }]}>Delete</Text>
                    </TouchableOpacity>
                  </View>
                  {statsFor === p.publisher_id && (
                    <View style={s.statsBox}>
                      {!stats ? <ActivityIndicator color="#9333EA" /> : (
                        <>
                          <Text style={s.statsTitle}>Last {stats.days} days</Text>
                          <View style={s.metaRow}>
                            <Text style={s.meta}>👁 {stats.totals.impressions}</Text>
                            <Text style={s.meta}>👆 {stats.totals.clicks} ({stats.ctr_pct}% CTR)</Text>
                            <Text style={s.meta}>✅ {stats.totals.conversions}</Text>
                            <Text style={[s.meta, { color: '#16A34A', fontWeight: '800' }]}>≈ {rup(stats.earnings_estimate_paise)} earned</Text>
                          </View>
                        </>
                      )}
                    </View>
                  )}
                </View>
              ))}
            </>
          )}

          {/* ═══════════ Cutoffs & Slots ═══════════ */}
          {tab === 'cutoffs' && (
            <>
              <View style={s.card}>
                <Text style={s.cardTitle}>Global Sponsored defaults</Text>
                <Text style={s.help}>
                  Apply to every LifeArea/SubArea/Scenario unless a Central-Catalog node overrides them.
                  Min Cutoff % = auction eligibility floor; Slots (N) = Sponsored items shown below organic.
                </Text>
                <View style={s.row2}>
                  <View style={{ flex: 1 }}><Text style={s.label}>Min Cutoff %</Text>
                    <TextInput style={s.input} value={gCutoff} onChangeText={setGCutoff} keyboardType="numeric" /></View>
                  <View style={{ flex: 1 }}><Text style={s.label}>Sponsored slots (N)</Text>
                    <TextInput style={s.input} value={gSponsN} onChangeText={setGSponsN} keyboardType="numeric" /></View>
                </View>
                <TouchableOpacity style={s.primaryBtn} onPress={saveGlobals} disabled={busy}>
                  {busy ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={s.primaryText}>Save global defaults</Text>}
                </TouchableOpacity>
              </View>

              <View style={s.card}>
                <Text style={s.cardTitle}>Per-node overrides (Central Catalog)</Text>
                <Text style={s.help}>
                  The nearest configured ancestor wins: Scenario → Category → SubArea → LifeArea → Global.
                  Leave a field blank to inherit.
                </Text>
                <TextInput style={s.input} value={nodeSearch} onChangeText={setNodeSearch}
                  placeholder="Search catalog nodes (e.g. Savings, Career…)" placeholderTextColor="#9CA3AF" />
                {filteredNodes.map(n => (
                  <TouchableOpacity key={n.node_id}
                    style={[s.nodeRow, selNode?.node_id === n.node_id && s.nodeOn]}
                    onPress={() => pickNode(n)}>
                    <Text style={s.nodeLevel}>L{n.level}</Text>
                    <Text style={s.nodeName} numberOfLines={1}>{n.name}</Text>
                    {(n.finder_ad_config?.min_cutoff_pct != null || n.finder_ad_config?.sponsored_n != null) && (
                      <View style={[s.badge, { backgroundColor: '#EEF2FF' }]}>
                        <Text style={[s.badgeText, { color: '#4F46E5' }]}>OVERRIDE</Text>
                      </View>
                    )}
                  </TouchableOpacity>
                ))}
                {selNode && (
                  <View style={s.nodeEditor}>
                    <Text style={s.statsTitle}>{selNode.name} <Text style={{ color: '#94A3B8' }}>({selNode.node_id})</Text></Text>
                    {effective && (
                      <Text style={s.effText}>
                        Effective: {effective.min_cutoff_pct}% cutoff ({srcLabel(effective.cutoff_source)}) ·
                        {' '}{effective.sponsored_n} slots ({srcLabel(effective.sponsored_source)})
                      </Text>
                    )}
                    <View style={s.row2}>
                      <View style={{ flex: 1 }}><Text style={s.label}>Min Cutoff % (blank = inherit)</Text>
                        <TextInput style={s.input} value={nCutoff} onChangeText={setNCutoff} keyboardType="numeric" placeholder="inherit" placeholderTextColor="#9CA3AF" /></View>
                      <View style={{ flex: 1 }}><Text style={s.label}>Slots N (blank = inherit)</Text>
                        <TextInput style={s.input} value={nSponsN} onChangeText={setNSponsN} keyboardType="numeric" placeholder="inherit" placeholderTextColor="#9CA3AF" /></View>
                    </View>
                    <TouchableOpacity style={s.primaryBtn} onPress={saveNode} disabled={busy}>
                      {busy ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={s.primaryText}>Save node override</Text>}
                    </TouchableOpacity>
                  </View>
                )}
              </View>
            </>
          )}
          <View style={{ height: 40 }} />
        </ScrollView>
      )}

      {/* ── Bid modal ── */}
      <Modal visible={bidOpen} transparent animationType="slide" onRequestClose={() => setBidOpen(false)}>
        <View style={s.overlay}>
          <View style={s.sheet}>
            <View style={s.mHead}>
              <Text style={s.mTitle}>{editBid ? 'Edit bid' : 'New bid'}</Text>
              <TouchableOpacity onPress={() => setBidOpen(false)}><Ionicons name="close" size={22} color="#64748B" /></TouchableOpacity>
            </View>
            <ScrollView style={{ maxHeight: 480 }}>
              {!editBid && (
                <>
                  <Text style={s.label}>Decider App</Text>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 6 }}>
                    {templates.map(t => (
                      <TouchableOpacity key={t.template_id} style={[s.chip, bTemplate === t.template_id && s.chipOn]} onPress={() => setBTemplate(t.template_id)}>
                        <Text style={[s.chipText, bTemplate === t.template_id && { color: '#FFF' }]} numberOfLines={1}>
                          {t.kind === 'app' ? '🔍 ' : ''}{t.title}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </ScrollView>
                </>
              )}
              <Text style={s.label}>Option being promoted *</Text>
              <TextInput style={s.input} value={bOption} onChangeText={setBOption} placeholder="Exact option name" placeholderTextColor="#9CA3AF" />
              {optionSuggestions.length > 0 && (
                <View style={s.suggestWrap}>
                  {optionSuggestions.map(n => (
                    <TouchableOpacity key={n} style={s.suggest} onPress={() => setBOption(n)}>
                      <Text style={s.suggestText} numberOfLines={1}>{n}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              )}
              <Text style={s.label}>Advertiser *</Text>
              <TextInput style={s.input} value={bAdvertiser} onChangeText={setBAdvertiser} placeholder="Acme Corp" placeholderTextColor="#9CA3AF" />
              <View style={s.row2}>
                <View style={{ flex: 1 }}><Text style={s.label}>Bid ₹/click *</Text>
                  <TextInput style={s.input} value={bBid} onChangeText={setBBid} keyboardType="numeric" placeholder="5.00" placeholderTextColor="#9CA3AF" /></View>
                <View style={{ flex: 1 }}><Text style={s.label}>Budget ₹ (0 = ∞)</Text>
                  <TextInput style={s.input} value={bBudget} onChangeText={setBBudget} keyboardType="numeric" placeholder="0" placeholderTextColor="#9CA3AF" /></View>
                <View style={{ flex: 1 }}><Text style={s.label}>Region</Text>
                  <TextInput style={s.input} value={bRegion} onChangeText={setBRegion} autoCapitalize="none" placeholder="global / in / us" placeholderTextColor="#9CA3AF" /></View>
              </View>
              <View style={s.row2}>
                <View style={{ flex: 1 }}><Text style={s.label}>Slot start (opt.)</Text>
                  <TextInput style={s.input} value={bStart} onChangeText={setBStart} autoCapitalize="none" placeholder="2026-07-01" placeholderTextColor="#9CA3AF" /></View>
                <View style={{ flex: 1 }}><Text style={s.label}>Slot end (opt.)</Text>
                  <TextInput style={s.input} value={bEnd} onChangeText={setBEnd} autoCapitalize="none" placeholder="2026-07-31" placeholderTextColor="#9CA3AF" /></View>
              </View>
              <View style={s.row2}>
                <View style={{ flex: 1 }}><Text style={s.label}>Daily from hr</Text>
                  <TextInput style={s.input} value={bHourS} onChangeText={setBHourS} keyboardType="numeric" placeholder="9" placeholderTextColor="#9CA3AF" /></View>
                <View style={{ flex: 1 }}><Text style={s.label}>Daily to hr</Text>
                  <TextInput style={s.input} value={bHourE} onChangeText={setBHourE} keyboardType="numeric" placeholder="21" placeholderTextColor="#9CA3AF" /></View>
                <View style={{ flex: 1.4 }}><Text style={s.label}>Timezone</Text>
                  <TextInput style={s.input} value={bTz} onChangeText={setBTz} autoCapitalize="none" placeholderTextColor="#9CA3AF" /></View>
              </View>
              <TouchableOpacity style={s.primaryBtn} onPress={saveBid} disabled={busy}>
                {busy ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={s.primaryText}>{editBid ? 'Save changes' : 'Create bid'}</Text>}
              </TouchableOpacity>
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* ── Publisher modal ── */}
      <Modal visible={pubOpen} transparent animationType="fade" onRequestClose={() => setPubOpen(false)}>
        <View style={s.overlay}>
          <View style={s.sheet}>
            <View style={s.mHead}>
              <Text style={s.mTitle}>{editPub ? 'Edit publisher' : 'New publisher'}</Text>
              <TouchableOpacity onPress={() => setPubOpen(false)}><Ionicons name="close" size={22} color="#64748B" /></TouchableOpacity>
            </View>
            <Text style={s.label}>Name *</Text>
            <TextInput style={s.input} value={pName} onChangeText={setPName} placeholder="PMSBazaar" placeholderTextColor="#9CA3AF" />
            <Text style={s.label}>Site URL</Text>
            <TextInput style={s.input} value={pSite} onChangeText={setPSite} autoCapitalize="none" placeholder="https://…" placeholderTextColor="#9CA3AF" />
            <Text style={s.label}>Revenue share %</Text>
            <TextInput style={s.input} value={pShare} onChangeText={setPShare} keyboardType="numeric" placeholderTextColor="#9CA3AF" />
            <TouchableOpacity style={s.primaryBtn} onPress={savePub} disabled={busy}>
              {busy ? <ActivityIndicator color="#FFF" size="small" /> : <Text style={s.primaryText}>{editPub ? 'Save changes' : 'Create & mint tracker'}</Text>}
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* ── Snippet modal ── */}
      <Modal visible={!!snipPub} transparent animationType="fade" onRequestClose={() => setSnipPub(null)}>
        <View style={s.overlay}>
          <View style={s.sheet}>
            <View style={s.mHead}>
              <Text style={s.mTitle}>Embed snippet · {snipPub?.name}</Text>
              <TouchableOpacity onPress={() => setSnipPub(null)}><Ionicons name="close" size={22} color="#64748B" /></TouchableOpacity>
            </View>
            <Text style={s.label}>Decider App to embed</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 8 }}>
              {templates.map(t => (
                <TouchableOpacity key={t.template_id} style={[s.chip, snipApp === t.template_id && s.chipOn]} onPress={() => setSnipApp(t.template_id)}>
                  <Text style={[s.chipText, snipApp === t.template_id && { color: '#FFF' }]} numberOfLines={1}>
                    {t.kind === 'app' ? '🔍 ' : ''}{t.title}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
            <View style={s.snippetBox}><Text style={s.snippet}>{snippetText}</Text></View>
            <TouchableOpacity style={s.primaryBtn} onPress={() => copy(snippetText, 'Embed snippet copied')}>
              <Ionicons name="copy" size={15} color="#FFF" /><Text style={s.primaryText}>Copy snippet</Text>
            </TouchableOpacity>
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
  tabs: { flexDirection: 'row', gap: 8, paddingHorizontal: 16, paddingVertical: 10, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#E2E8F0' },
  tabBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 8, paddingHorizontal: 12, borderRadius: 10, backgroundColor: '#F1F5F9' },
  tabOn: { backgroundColor: '#4F46E5' },
  tabText: { fontSize: 12.5, fontWeight: '700', color: '#475569' },
  body: { padding: 16, maxWidth: 760, width: '100%', alignSelf: 'center' },
  card: { backgroundColor: '#FFF', borderRadius: 14, padding: 16, borderWidth: 1, borderColor: '#E2E8F0', marginBottom: 12 },
  cardTitle: { fontSize: 15, fontWeight: '800', color: '#0F172A', marginBottom: 6 },
  help: { fontSize: 12, color: '#64748B', lineHeight: 17, marginBottom: 10 },
  empty: { textAlign: 'center', color: '#94A3B8', paddingVertical: 24 },
  primaryBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#4F46E5', borderRadius: 12, paddingVertical: 12, marginTop: 8 },
  primaryText: { color: '#FFF', fontSize: 14, fontWeight: '800' },
  rowHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  rowTitle: { flex: 1, fontSize: 14.5, fontWeight: '800', color: '#0F172A' },
  rowSub: { fontSize: 12, color: '#64748B', marginTop: 2 },
  badge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999 },
  badgeText: { fontSize: 10, fontWeight: '900', letterSpacing: 0.4 },
  metaRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 8 },
  meta: { fontSize: 11.5, color: '#475569', fontWeight: '600' },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 12 },
  act: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingVertical: 7, paddingHorizontal: 10, borderRadius: 9 },
  actText: { fontSize: 12, fontWeight: '700' },
  trackerRow: { flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10, paddingHorizontal: 10, paddingVertical: 8, marginTop: 8, alignSelf: 'flex-start' },
  tracker: { fontSize: 13, fontWeight: '800', color: '#4F46E5', letterSpacing: 0.5 },
  statsBox: { marginTop: 12, backgroundColor: '#FAF5FF', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: '#E9D5FF' },
  statsTitle: { fontSize: 13, fontWeight: '800', color: '#0F172A', marginBottom: 6 },
  effText: { fontSize: 12, color: '#4F46E5', fontWeight: '600', marginBottom: 8 },
  nodeRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8, paddingHorizontal: 10, borderRadius: 9, marginTop: 4 },
  nodeOn: { backgroundColor: '#EEF2FF' },
  nodeLevel: { fontSize: 10, fontWeight: '900', color: '#94A3B8', width: 22 },
  nodeName: { flex: 1, fontSize: 13, fontWeight: '600', color: '#0F172A' },
  nodeEditor: { marginTop: 12, backgroundColor: '#F8FAFC', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: '#E2E8F0' },
  overlay: { flex: 1, backgroundColor: 'rgba(15,23,42,0.5)', justifyContent: 'center', padding: 20 },
  sheet: { backgroundColor: '#FFF', borderRadius: 16, padding: 18, maxWidth: 560, width: '100%', alignSelf: 'center' },
  mHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 },
  mTitle: { fontSize: 16, fontWeight: '800', color: '#0F172A' },
  label: { fontSize: 11.5, fontWeight: '700', color: '#475569', marginTop: 10, marginBottom: 4 },
  input: { backgroundColor: '#F8FAFC', borderRadius: 10, borderWidth: 1, borderColor: '#E2E8F0', paddingHorizontal: 12, paddingVertical: 9, fontSize: 14, color: '#0F172A' },
  row2: { flexDirection: 'row', gap: 10 },
  chip: { paddingVertical: 7, paddingHorizontal: 12, borderRadius: 999, backgroundColor: '#F1F5F9', marginRight: 6, maxWidth: 220 },
  chipOn: { backgroundColor: '#4F46E5' },
  chipText: { fontSize: 12, fontWeight: '700', color: '#475569' },
  suggestWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 6 },
  suggest: { backgroundColor: '#EEF2FF', borderRadius: 999, paddingVertical: 5, paddingHorizontal: 10, maxWidth: 240 },
  suggestText: { fontSize: 11.5, fontWeight: '700', color: '#4F46E5' },
  snippetBox: { backgroundColor: '#0F172A', borderRadius: 10, padding: 12, marginTop: 6 },
  snippet: { color: '#A5B4FC', fontSize: 11.5, fontFamily: 'monospace' as any },
});
