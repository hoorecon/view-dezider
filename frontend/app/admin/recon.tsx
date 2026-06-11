/**
 * /admin/recon — Revenue Reconciliation report (Super-Admin).
 *
 * Tally: Razorpay collections ⟷ internal AI-wallet ledger ⟷ Google Cloud
 * (Gemini) actual billing — so the primary account is never in loss w.r.t.
 * LLM-provider invoices. Granular to single transaction.
 *
 * Sections:
 *  1. Verdict + summary cards (collected / fees / routed / treasury / liability)
 *  2. Per-transaction tally table (zero-loss check per refill)
 *  3. Daily consumption tally (est. cost vs GCP actual)
 *  4. Google Cloud BigQuery connection settings
 */
import React, { useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Platform, useWindowDimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';

const C = {
  bg: '#F8FAFC', card: '#FFFFFF', border: '#E2E8F0', text: '#0F172A',
  muted: '#64748B', primary: '#7C3AED', green: '#059669', red: '#DC2626',
  amber: '#D97706', chipBg: '#F1F5F9',
};

const inr = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `₹${Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;

export default function AdminReconScreen() {
  const { width } = useWindowDimensions();
  const isWide = width >= 1000;

  const [summary, setSummary] = useState<any>(null);
  const [txns, setTxns] = useState<any[]>([]);
  const [daily, setDaily] = useState<any>(null);
  const [cfg, setCfg] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  // GCP config form
  const [saJson, setSaJson] = useState('');
  const [projectId, setProjectId] = useState('');
  const [dataset, setDataset] = useState('');
  const [table, setTable] = useState('');
  const [savingCfg, setSavingCfg] = useState(false);

  useEffect(() => { loadAll(); }, []);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [s, t, d, c] = await Promise.all([
        api.get('/admin/recon/summary'),
        api.get('/admin/recon/transactions?limit=100'),
        api.get('/admin/recon/daily?days=31'),
        api.get('/admin/recon/gcp-config'),
      ]);
      setSummary(s.data);
      setTxns(t.data.items || []);
      setDaily(d.data);
      setCfg(c.data);
      setProjectId(c.data?.gcp?.project_id || '');
      setDataset(c.data?.gcp?.dataset || '');
      setTable(c.data?.gcp?.table || '');
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to load reconciliation data');
    } finally { setLoading(false); }
  };

  const syncNow = async () => {
    setSyncing(true);
    try {
      const r = await api.post('/admin/recon/sync');
      const rz = r.data.razorpay, gc = r.data.gcp;
      showAlert('Sync complete',
        `Razorpay: ${rz.ok ? `${rz.payments ?? 0} payments, ${rz.transfers ?? 0} transfers, ${rz.settlements ?? 0} settlements` : rz.error}\n` +
        `Google Cloud: ${gc.ok ? `${gc.rows} cost rows` : gc.error}`);
      await loadAll();
    } catch (e: any) {
      showAlert('Sync failed', e?.response?.data?.detail || 'Unknown error');
    } finally { setSyncing(false); }
  };

  const saveGcpConfig = async () => {
    setSavingCfg(true);
    try {
      const body: any = { project_id: projectId, dataset, table };
      if (saJson.trim()) body.sa_json = saJson.trim();
      const r = await api.put('/admin/recon/gcp-config', body);
      setCfg(r.data);
      setSaJson('');
      showAlert('Saved', r.data?.gcp?.configured
        ? `Connected as ${r.data.gcp.sa_client_email}`
        : 'Settings saved (no credentials yet)');
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to save');
    } finally { setSavingCfg(false); }
  };

  const exportCsv = async () => {
    try {
      const r = await api.get('/admin/recon/transactions.csv', { responseType: 'text' as any });
      if (Platform.OS === 'web' && typeof document !== 'undefined') {
        const blob = new Blob([r.data], { type: 'text/csv' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `recon_transactions_${new Date().toISOString().slice(0, 10)}.csv`;
        a.click();
        URL.revokeObjectURL(a.href);
      }
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Export failed');
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={s.center} testID="recon-loading">
        <ActivityIndicator size="large" color={C.primary} />
        <Text style={s.mutedTxt}>Loading reconciliation…</Text>
      </SafeAreaView>
    );
  }

  const v = summary?.verdict || {};
  const sales = summary?.sales || {};
  const rzp = summary?.razorpay || {};
  const cons = summary?.consumption || {};
  const gcp = summary?.gcp || {};
  const lossTxns = txns.filter((t) => t.flags?.at_loss).length;

  return (
    <SafeAreaView style={s.root} testID="admin-recon-screen">
      <ScrollView contentContainerStyle={s.scroll} showsVerticalScrollIndicator>
        {/* Header */}
        <View style={s.headerRow}>
          <View style={{ flex: 1 }}>
            <Text style={s.h1} testID="recon-title">Revenue Reconciliation</Text>
            <Text style={s.sub}>
              Razorpay ⟷ AI-Wallet ledger ⟷ Google Cloud (Gemini) · FX ₹{summary?.fx_usd_inr}/USD ({summary?.fx_source})
            </Text>
          </View>
          <TouchableOpacity style={s.syncBtn} onPress={syncNow} disabled={syncing} testID="recon-sync-now-btn">
            {syncing ? <ActivityIndicator size="small" color="#fff" />
              : <Ionicons name="sync" size={15} color="#fff" />}
            <Text style={s.syncBtnTxt}>{syncing ? 'Syncing…' : 'Sync now'}</Text>
          </TouchableOpacity>
        </View>
        <Text style={s.lastSync} testID="recon-last-sync">
          Last sync — Razorpay: {summary?.last_rzp_sync ? new Date(summary.last_rzp_sync).toLocaleString() : 'never'} ·
          {' '}GCP: {summary?.last_gcp_sync ? new Date(summary.last_gcp_sync).toLocaleString() : 'never'} · auto-sync daily
        </Text>

        {/* Verdict banner */}
        <View style={[s.verdict, { backgroundColor: v.at_risk ? '#FEF2F2' : '#ECFDF5', borderColor: v.at_risk ? C.red : C.green }]} testID="recon-verdict-banner">
          <Ionicons name={v.at_risk ? 'warning' : 'shield-checkmark'} size={22} color={v.at_risk ? C.red : C.green} />
          <View style={{ flex: 1 }}>
            <Text style={[s.verdictTitle, { color: v.at_risk ? C.red : C.green }]}>
              {v.at_risk ? 'AT RISK — treasury may not cover LLM liability' : 'COVERED — treasury exceeds LLM liability'}
            </Text>
            <Text style={s.verdictSub}>
              Net treasury {inr(rzp.net_treasury_inr)} vs estimated liability {inr(cons.est_liability_inr)}
              {' '}→ surplus {inr(v.surplus_vs_estimate_inr)}
              {v.surplus_vs_gcp_actual_inr !== null && v.surplus_vs_gcp_actual_inr !== undefined
                ? ` · vs GCP actual: ${inr(v.surplus_vs_gcp_actual_inr)}` : ' · GCP actuals not synced yet'}
              {lossTxns > 0 ? ` · ⚠ ${lossTxns} transaction(s) sold below break-even` : ''}
            </Text>
          </View>
        </View>

        {/* Summary cards */}
        <View style={[s.cards, !isWide && { flexDirection: 'column' }]}>
          <Card testID="recon-card-collected" icon="cash" label="Collected (paid orders)" value={inr(sales.collected_inr)} sub={`${sales.orders} orders · ${Number(sales.credits_sold || 0).toLocaleString()} credits sold`} />
          <Card testID="recon-card-fees" icon="receipt" label="Razorpay fees + GST" value={inr(rzp.fees_inr)} color={C.amber} />
          <Card testID="recon-card-routed" icon="git-branch" label="Markup routed (Route)" value={inr(rzp.routed_markup_inr)} sub="→ linked account" />
          <Card testID="recon-card-treasury" icon="business" label="Net treasury (primary a/c)" value={inr(rzp.net_treasury_inr)} color={C.primary} />
        </View>
        <View style={[s.cards, !isWide && { flexDirection: 'column' }]}>
          <Card testID="recon-card-earmarked" icon="pricetag" label="Earmarked LLM cost (at sale)" value={inr(sales.earmarked_llm_cost_inr)} />
          <Card testID="recon-card-liability" icon="flame" label="Est. liability (tokens used)" value={inr(cons.est_liability_inr)} sub={`${Number(cons.tokens_used || 0).toLocaleString()} tokens · ${Number(cons.credits_used || 0).toLocaleString()} credits`} color={C.amber} />
          <Card testID="recon-card-gcp" icon="logo-google" label="GCP actual (synced window)" value={gcp.actual_cost_inr === null ? (gcp.configured ? 'No data yet' : 'Not connected') : inr(gcp.actual_cost_inr)} sub={gcp.configured ? `${gcp.rows_synced} cost rows` : 'Configure below'} />
          <Card testID="recon-card-surplus" icon={v.at_risk ? 'trending-down' : 'trending-up'} label="Surplus / (Deficit)" value={inr(v.surplus_vs_estimate_inr)} color={v.at_risk ? C.red : C.green} />
        </View>

        {/* Per-transaction tally */}
        <View style={s.section} testID="recon-txn-section">
          <View style={s.sectionHead}>
            <Text style={s.h2}>Per-Transaction Tally ({txns.length})</Text>
            <TouchableOpacity style={s.csvBtn} onPress={exportCsv} testID="recon-export-csv-btn">
              <Ionicons name="download" size={14} color={C.primary} />
              <Text style={s.csvBtnTxt}>Export CSV</Text>
            </TouchableOpacity>
          </View>
          <Text style={s.hint}>
            buffer = collected − Razorpay fee − routed markup − earmarked LLM cost. Negative buffer (red) = that sale
            cannot cover its own Gemini cost from the primary account.
          </Text>
          <ScrollView horizontal showsHorizontalScrollIndicator style={s.tableWrap}>
            <View>
              <View style={s.tr}>
                {['Date', 'User', 'Credits', 'Collected', 'RZP fee', 'Routed', 'Net treasury', 'LLM cost', 'Buffer', 'Status']
                  .map((h, i) => <Text key={h} style={[s.th, i === 0 && { width: 110 }, i === 1 && { width: 130 }]}>{h}</Text>)}
              </View>
              {txns.length === 0 && (
                <Text style={[s.mutedTxt, { padding: 16 }]} testID="recon-txn-empty">
                  No paid refill orders yet — or run "Sync now" to pull Razorpay data.
                </Text>
              )}
              {txns.map((t) => (
                <View key={t.order_id} style={s.tr} testID={`recon-txn-row-${t.order_id}`}>
                  <Text style={[s.td, { width: 110 }]}>{(t.created_at || '').slice(0, 10)}</Text>
                  <Text style={[s.td, { width: 130 }]} numberOfLines={1}>{t.user_id}</Text>
                  <Text style={s.td}>{t.credits?.toLocaleString()}</Text>
                  <Text style={s.td}>{inr(t.collected_inr)}</Text>
                  <Text style={[s.td, { color: C.amber }]}>{t.flags?.fee_known ? inr(t.rzp_fee_inr) : 'sync…'}</Text>
                  <Text style={s.td}>{inr(t.routed_markup_inr)}</Text>
                  <Text style={[s.td, { fontWeight: '700' }]}>{inr(t.net_treasury_inr)}</Text>
                  <Text style={s.td}>{inr(t.earmarked_llm_cost_inr)}</Text>
                  <Text style={[s.td, { fontWeight: '800', color: t.buffer_inr < 0 ? C.red : C.green }]}>{inr(t.buffer_inr)}</Text>
                  <View style={[s.td, { flexDirection: 'row', gap: 4 }]}>
                    <Chip ok={t.flags?.credits_granted} label="credited" />
                    <Chip ok={t.flags?.payment_synced} label="rzp" />
                    {t.route_applied && <Chip ok={t.flags?.transfer_synced} label="routed" />}
                  </View>
                </View>
              ))}
            </View>
          </ScrollView>
        </View>

        {/* Daily tally */}
        <View style={s.section} testID="recon-daily-section">
          <Text style={s.h2}>Daily Consumption Tally (last 31 days)</Text>
          <Text style={s.hint}>
            Estimated cost = tokens ÷ 1M × ${daily?.blended_usd_per_mtok}/Mtok × ₹{daily?.fx_usd_inr}.
            GCP actual appears once BigQuery billing export is connected. Variance = actual − estimate
            (positive = Google billing MORE than we estimated — investigate immediately).
          </Text>
          <ScrollView horizontal showsHorizontalScrollIndicator style={s.tableWrap}>
            <View>
              <View style={s.tr}>
                {['Date', 'AI calls', 'Tokens', 'Credits used', 'Est. cost', 'GCP actual', 'Variance']
                  .map((h) => <Text key={h} style={s.th}>{h}</Text>)}
              </View>
              {(daily?.items || []).length === 0 && (
                <Text style={[s.mutedTxt, { padding: 16 }]} testID="recon-daily-empty">No AI consumption in this window.</Text>
              )}
              {(daily?.items || []).map((d: any) => (
                <View key={d.date} style={s.tr} testID={`recon-daily-row-${d.date}`}>
                  <Text style={s.td}>{d.date}</Text>
                  <Text style={s.td}>{d.calls}</Text>
                  <Text style={s.td}>{Number(d.tokens).toLocaleString()}</Text>
                  <Text style={s.td}>{d.credits}</Text>
                  <Text style={s.td}>{inr(d.est_cost_inr)}</Text>
                  <Text style={s.td}>{d.gcp_actual_inr === null || d.gcp_actual_inr === undefined ? '—' : inr(d.gcp_actual_inr)}</Text>
                  <Text style={[s.td, { fontWeight: '700', color: (d.variance_inr ?? 0) > 0 ? C.red : C.green }]}>
                    {d.variance_inr === null || d.variance_inr === undefined ? '—' : inr(d.variance_inr)}
                  </Text>
                </View>
              ))}
            </View>
          </ScrollView>
        </View>

        {/* GCP config */}
        <View style={s.section} testID="recon-gcp-config-section">
          <Text style={s.h2}>Google Cloud — BigQuery Billing Export</Text>
          <View style={s.gcpStatusRow}>
            <Ionicons name={cfg?.gcp?.configured ? 'checkmark-circle' : 'ellipse-outline'}
              size={16} color={cfg?.gcp?.configured ? C.green : C.muted} />
            <Text style={s.mutedTxt} testID="recon-gcp-status">
              {cfg?.gcp?.configured
                ? `Connected as ${cfg.gcp.sa_client_email}`
                : 'Not connected — follow the steps below, then paste the service-account JSON.'}
            </Text>
          </View>
          {!cfg?.gcp?.configured && (
            <View style={s.steps}>
              {[
                '1. Google Cloud Console → Billing → Billing export → enable "Standard usage cost" export to BigQuery (choose/create a dataset, e.g. billing_export).',
                '2. IAM & Admin → Service Accounts → Create. Grant roles: BigQuery Data Viewer (on the dataset) + BigQuery Job User (on the project).',
                '3. Service account → Keys → Add key → JSON. Download and paste the JSON below.',
                '4. Table name looks like: gcp_billing_export_v1_XXXXXX_XXXXXX_XXXXXX (find it inside the dataset).',
              ].map((t) => <Text key={t} style={s.stepTxt}>{t}</Text>)}
            </View>
          )}
          <View style={[s.formRow, !isWide && { flexDirection: 'column' }]}>
            <Field label="GCP Project ID" value={projectId} onChange={setProjectId} placeholder="my-project-123" testID="recon-gcp-project-input" />
            <Field label="Dataset" value={dataset} onChange={setDataset} placeholder="billing_export" testID="recon-gcp-dataset-input" />
            <Field label="Billing export table" value={table} onChange={setTable} placeholder="gcp_billing_export_v1_…" testID="recon-gcp-table-input" />
          </View>
          <Text style={s.fieldLabel}>Service-account JSON key {cfg?.gcp?.configured ? '(paste to replace)' : ''}</Text>
          <TextInput
            style={s.jsonInput}
            value={saJson}
            onChangeText={setSaJson}
            placeholder='{"type":"service_account","project_id":"…","private_key":"…"}'
            placeholderTextColor={C.muted}
            multiline
            numberOfLines={4}
            testID="recon-gcp-sa-json-input"
          />
          <TouchableOpacity style={s.saveBtn} onPress={saveGcpConfig} disabled={savingCfg} testID="recon-gcp-save-btn">
            {savingCfg ? <ActivityIndicator size="small" color="#fff" /> : <Ionicons name="save" size={14} color="#fff" />}
            <Text style={s.syncBtnTxt}>{savingCfg ? 'Saving…' : 'Save GCP settings'}</Text>
          </TouchableOpacity>
          <Text style={s.hint}>
            The key is stored encrypted-at-rest in the database and never returned to the browser.
            Queries are capped at 2 GB billed bytes per run as a cost guard.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const Card = ({ icon, label, value, sub, color, testID }: any) => (
  <View style={s.card} testID={testID}>
    <View style={s.cardHead}>
      <Ionicons name={icon} size={15} color={color || C.muted} />
      <Text style={s.cardLabel}>{label}</Text>
    </View>
    <Text style={[s.cardValue, color ? { color } : null]}>{value}</Text>
    {sub ? <Text style={s.cardSub}>{sub}</Text> : null}
  </View>
);

const Chip = ({ ok, label }: { ok: boolean; label: string }) => (
  <View style={[s.chip, { backgroundColor: ok ? '#ECFDF5' : '#FEF2F2' }]}>
    <Text style={[s.chipTxt, { color: ok ? C.green : C.red }]}>{ok ? '✓' : '✗'} {label}</Text>
  </View>
);

const Field = ({ label, value, onChange, placeholder, testID }: any) => (
  <View style={{ flex: 1 }}>
    <Text style={s.fieldLabel}>{label}</Text>
    <TextInput style={s.input} value={value} onChangeText={onChange} placeholder={placeholder}
      placeholderTextColor={C.muted} autoCapitalize="none" testID={testID} />
  </View>
);

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  scroll: { padding: 20, paddingBottom: 60, gap: 14 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: C.bg },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  h1: { fontSize: 22, fontWeight: '800', color: C.text },
  h2: { fontSize: 16, fontWeight: '800', color: C.text },
  sub: { fontSize: 12.5, color: C.muted, marginTop: 3 },
  lastSync: { fontSize: 11.5, color: C.muted },
  mutedTxt: { fontSize: 12.5, color: C.muted },
  syncBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: C.primary,
    paddingHorizontal: 14, paddingVertical: 9, borderRadius: 10,
  },
  syncBtnTxt: { color: '#fff', fontWeight: '700', fontSize: 13 },
  verdict: {
    flexDirection: 'row', alignItems: 'center', gap: 12, borderWidth: 1,
    borderRadius: 12, padding: 14,
  },
  verdictTitle: { fontSize: 14, fontWeight: '800' },
  verdictSub: { fontSize: 12.5, color: C.text, marginTop: 3, lineHeight: 18 },
  cards: { flexDirection: 'row', gap: 12 },
  card: {
    flex: 1, backgroundColor: C.card, borderWidth: 1, borderColor: C.border,
    borderRadius: 12, padding: 14, minWidth: 150,
  },
  cardHead: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  cardLabel: { fontSize: 11.5, color: C.muted, fontWeight: '600', flex: 1 },
  cardValue: { fontSize: 18, fontWeight: '800', color: C.text },
  cardSub: { fontSize: 11, color: C.muted, marginTop: 3 },
  section: {
    backgroundColor: C.card, borderWidth: 1, borderColor: C.border,
    borderRadius: 12, padding: 16, gap: 8,
  },
  sectionHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  hint: { fontSize: 11.5, color: C.muted, lineHeight: 17 },
  csvBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 5, borderWidth: 1,
    borderColor: C.primary, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6,
  },
  csvBtnTxt: { color: C.primary, fontWeight: '700', fontSize: 12 },
  tableWrap: { marginTop: 6 },
  tr: {
    flexDirection: 'row', borderBottomWidth: 1, borderBottomColor: C.border,
    paddingVertical: 8, alignItems: 'center',
  },
  th: { width: 96, fontSize: 11, fontWeight: '800', color: C.muted, textTransform: 'uppercase', paddingHorizontal: 4 },
  td: { width: 96, fontSize: 12.5, color: C.text, paddingHorizontal: 4 },
  chip: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 },
  chipTxt: { fontSize: 10, fontWeight: '700' },
  gcpStatusRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  steps: { backgroundColor: C.chipBg, borderRadius: 10, padding: 12, gap: 6 },
  stepTxt: { fontSize: 12, color: C.text, lineHeight: 18 },
  formRow: { flexDirection: 'row', gap: 12, marginTop: 4 },
  fieldLabel: { fontSize: 11.5, fontWeight: '700', color: C.muted, marginBottom: 4, marginTop: 6 },
  input: {
    borderWidth: 1, borderColor: C.border, borderRadius: 8, paddingHorizontal: 10,
    paddingVertical: 8, fontSize: 13, color: C.text, backgroundColor: '#fff',
  },
  jsonInput: {
    borderWidth: 1, borderColor: C.border, borderRadius: 8, padding: 10,
    fontSize: 12, color: C.text, backgroundColor: '#fff', minHeight: 90,
    fontFamily: Platform.OS === 'web' ? 'monospace' : undefined, textAlignVertical: 'top',
  },
  saveBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: C.primary, paddingVertical: 10, borderRadius: 10, marginTop: 8,
    alignSelf: 'flex-start', paddingHorizontal: 16,
  },
});
