/**
 * ScreenerPanel — the partner Screener UI (P3), rendered inside the white-label
 * embed when flow === 'screener'.
 *
 * Flow: pick a candidate source (carried options / CSV paste / Google-Sheet CSV
 * URL / partner API / premium URL) → ingest → define weighted factors → see a
 * live price quote → run → ranked top finalists with per-factor breakdown +
 * CSV export.
 *
 * Uses the shared `api` axios instance (auto-attaches the session token).
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, TextInput, TouchableOpacity, ActivityIndicator,
  ScrollView, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import api from '../../utils/api';
import { showAlert } from '../../utils/alert';
import UrlAccessConsentModal, { UrlConsentPayload } from '../../components/UrlAccessConsentModal';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL || '';

type Direction = 'higher' | 'lower';
interface FactorRow { id: string; name: string; attribute_key: string; weight: string; direction: Direction; data_type: 'numeric' | 'text'; }
interface Cand { name: string; attributes: Record<string, any>; }
interface Props { partner: string; primary: string; accent: string; initialOptions?: any[]; }

const SOURCES = [
  { key: 'inline', label: 'Carried options', icon: 'swap-horizontal' },
  { key: 'csv', label: 'Paste CSV', icon: 'document-text' },
  { key: 'sheet_csv', label: 'Google Sheet', icon: 'grid' },
  { key: 'api', label: 'Partner API', icon: 'cloud-download' },
  { key: 'url', label: 'Paste URL', icon: 'link' },
] as const;

const looksNumeric = (v: any) => v != null && /[-\d]/.test(String(v)) && !isNaN(parseFloat(String(v).replace(/[,%₹$\s]/g, '')));

export default function ScreenerPanel({ partner, primary, accent, initialOptions = [] }: Props) {
  const [source, setSource] = useState<string>(initialOptions.length ? 'inline' : 'csv');
  const [csvText, setCsvText] = useState('');
  const [url, setUrl] = useState('');

  const [ingestId, setIngestId] = useState<string | null>(null);
  const [count, setCount] = useState(0);
  const [attrKeys, setAttrKeys] = useState<string[]>([]);
  const [preview, setPreview] = useState<Cand[]>([]);
  const [factors, setFactors] = useState<FactorRow[]>([]);
  const [finalists, setFinalists] = useState('10');
  const [useAi, setUseAi] = useState(false);

  const [quote, setQuote] = useState<number | null>(null);
  const [balance, setBalance] = useState<number | null>(null);
  const [results, setResults] = useState<any[] | null>(null);
  const [runId, setRunId] = useState<string | null>(null);

  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [sending, setSending] = useState<null | 'mydezider' | 'pros_cons'>(null);
  const [urlConsentOpen, setUrlConsentOpen] = useState(false);
  const router = useRouter();

  const mkFactor = (key: string): FactorRow => ({
    id: `f_${Date.now()}_${Math.random().toString(36).slice(2, 5)}`,
    name: key, attribute_key: key, weight: '50', direction: 'higher', data_type: 'numeric',
  });

  const seedFactorsFromKeys = useCallback((keys: string[], sample?: Cand) => {
    const numericKeys = keys.filter(k => !sample || looksNumeric(sample.attributes?.[k]));
    const chosen = (numericKeys.length ? numericKeys : keys).slice(0, 3);
    setFactors(chosen.map(mkFactor));
  }, []);

  const doIngest = async () => {
    setBusy(true); setErr(null); setResults(null);
    try {
      const body: any = { partner, mode: source };
      if (source === 'inline') body.candidates = initialOptions.map((o) => ({
        name: typeof o === 'string' ? o : (o?.name || 'Option'),
        attributes: (o && o.attributes) || {},
      }));
      else if (source === 'csv') body.csv_text = csvText;
      else body.url = url;
      const r = await api.post(`/embed/screener/ingest`, body);
      setIngestId(r.data.ingest_id);
      setCount(r.data.count);
      setAttrKeys(r.data.attribute_keys || []);
      setPreview(r.data.preview || []);
      seedFactorsFromKeys(r.data.attribute_keys || [], (r.data.preview || [])[0]);
    } catch (e: any) {
      setErr(e?.response?.data?.detail || 'Ingestion failed');
    } finally { setBusy(false); }
  };

  // live quote when inputs change
  useEffect(() => {
    if (!ingestId || !factors.length) { setQuote(null); return; }
    let cancelled = false;
    (async () => {
      try {
        const r = await api.post(`/embed/screener/quote`, {
          partner, candidate_count: count,
          finalists: Math.max(1, parseInt(finalists || '10', 10) || 10),
          factor_count: factors.length,
        });
        if (!cancelled) { setQuote(r.data.cost_credits); setBalance(r.data.wallet_balance); }
      } catch { /* ignore */ }
    })();
    return () => { cancelled = true; };
  }, [ingestId, factors.length, finalists, count, partner]);

  const doRun = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await api.post(`/embed/screener/run`, {
        partner, ingest_id: ingestId,
        factors: factors.map(f => ({
          name: f.name, attribute_key: f.attribute_key,
          weight: parseFloat(f.weight) || 0, direction: f.direction, data_type: f.data_type,
        })),
        finalists: Math.max(1, parseInt(finalists || '10', 10) || 10),
        use_ai: useAi,
      });
      setResults(r.data.finalists || []);
      setRunId(r.data.run_id);
      setBalance(r.data.wallet_balance);
    } catch (e: any) {
      const d = e?.response?.data?.detail;
      if (d && d.error === 'insufficient_credits') {
        setErr(`Not enough credits — need ${d.needed}, balance ${d.balance}. Add credits in your wallet.`);
      } else {
        setErr(typeof d === 'string' ? d : 'Run failed');
      }
    } finally { setBusy(false); }
  };

  const updateFactor = (id: string, patch: Partial<FactorRow>) =>
    setFactors(fs => fs.map(f => (f.id === id ? { ...f, ...patch } : f)));

  const exportUrl = useMemo(() => runId ? `${API_URL}/api/embed/screener/run/${runId}/export.csv` : null, [runId]);

  const sendTo = async (target: 'mydezider' | 'pros_cons') => {
    if (!runId || sending) return;
    setSending(target);
    try {
      const path = target === 'mydezider' ? 'to-decision' : 'to-pros-cons';
      const { data } = await api.post(`/embed/screener/run/${runId}/${path}`, {});
      showAlert(
        'Sent successfully',
        `Created a ${target === 'mydezider' ? 'MyDezider decision' : 'Pros & Cons analysis'} with ${data.finalists} option(s). Open it now?`,
        [
          { text: 'Later', style: 'cancel' },
          { text: 'Open', onPress: () => {
            if (target === 'pros_cons') router.push(`/tools/pros-cons-wizard?id=${data.id}&module=pros-cons` as any);
            else router.push(`/prr/${data.id}` as any);
          } },
        ]
      );
    } catch (e: any) {
      const d = e?.response?.data?.detail;
      showAlert('Could not send', typeof d === 'string' ? d : 'Please try again.');
    } finally {
      setSending(null);
    }
  };

  const onUrlConsent = (_c: UrlConsentPayload) => { setUrlConsentOpen(false); doIngest(); };

  // ---- render ----
  return (
    <ScrollView style={styles.wrap} keyboardShouldPersistTaps="handled">
      {/* Source picker */}
      <Text style={styles.section}>1 · Candidate source</Text>
      <View style={styles.chipRow}>
        {SOURCES.filter(s => s.key !== 'inline' || initialOptions.length).map(s => (
          <TouchableOpacity key={s.key}
            testID={`screener-source-${s.key}`}
            style={[styles.chip, source === s.key && { backgroundColor: primary, borderColor: primary }]}
            onPress={() => { setSource(s.key); setIngestId(null); setResults(null); }}>
            <Ionicons name={s.icon as any} size={13} color={source === s.key ? '#fff' : '#475569'} />
            <Text style={[styles.chipText, source === s.key && { color: '#fff' }]}>{s.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {source === 'csv' && (
        <TextInput testID="screener-csv-input" style={styles.area} multiline placeholder={'name,1Y Return,AUM\nFund A,44.39%,121.47\nFund B,31.9%,212.0'}
          placeholderTextColor="#9CA3AF" value={csvText} onChangeText={setCsvText} />
      )}
      {(source === 'sheet_csv' || source === 'api' || source === 'url') && (
        <TextInput testID="screener-url-input" style={styles.input}
          placeholder={source === 'sheet_csv' ? 'Published Google-Sheet CSV URL' : source === 'api' ? 'Catalogue API URL (optional if configured)' : 'Filtered page URL (premium — admin-gated)'}
          placeholderTextColor="#9CA3AF" autoCapitalize="none" value={url} onChangeText={setUrl} />
      )}
      {source === 'inline' && (
        <Text style={styles.hint}>{initialOptions.length} option(s) carried over from the partner page.</Text>
      )}

      <TouchableOpacity testID="screener-load-candidates-btn" style={[styles.btn, { backgroundColor: primary }]}
        onPress={source === 'url' ? () => setUrlConsentOpen(true) : doIngest} disabled={busy}>
        {busy && !results ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>{source === 'url' ? 'Review consent & load' : 'Load candidates'}</Text>}
      </TouchableOpacity>

      {ingestId && (
        <>
          <Text style={styles.okLine}><Ionicons name="checkmark-circle" size={14} color="#16A34A" /> {count} candidates loaded</Text>

          {/* Factors */}
          <Text style={styles.section}>2 · Weighted factors</Text>
          {factors.map(f => (
            <View key={f.id} style={styles.factorRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.factorName}>{f.name}</Text>
                <View style={styles.factorCtrls}>
                  <TextInput testID={`screener-factor-weight-${f.attribute_key}`} style={styles.weightInput} keyboardType="number-pad" value={f.weight}
                    onChangeText={(t) => updateFactor(f.id, { weight: t.replace(/[^0-9]/g, '') })} />
                  <Text style={styles.wLabel}>wt</Text>
                  <TouchableOpacity style={styles.dirToggle}
                    testID={`screener-factor-dir-${f.attribute_key}`}
                    onPress={() => updateFactor(f.id, { direction: f.direction === 'higher' ? 'lower' : 'higher' })}>
                    <Ionicons name={f.direction === 'higher' ? 'arrow-up' : 'arrow-down'} size={12} color={primary} />
                    <Text style={[styles.dirText, { color: primary }]}>{f.direction} is better</Text>
                  </TouchableOpacity>
                  <TouchableOpacity testID={`screener-factor-type-${f.attribute_key}`} onPress={() => updateFactor(f.id, { data_type: f.data_type === 'numeric' ? 'text' : 'numeric' })}>
                    <Text style={[styles.typePill, f.data_type === 'text' && { backgroundColor: accent }]}>{f.data_type === 'text' ? 'AI' : '123'}</Text>
                  </TouchableOpacity>
                </View>
              </View>
              <TouchableOpacity testID={`screener-factor-remove-${f.attribute_key}`} onPress={() => setFactors(fs => fs.filter(x => x.id !== f.id))}>
                <Ionicons name="close-circle" size={20} color="#CBD5E1" />
              </TouchableOpacity>
            </View>
          ))}
          {attrKeys.length > 0 && (
            <View style={styles.chipRow}>
              {attrKeys.filter(k => !factors.some(f => f.attribute_key === k) && (!preview[0] || looksNumeric(preview[0].attributes?.[k]))).slice(0, 8).map(k => (
                <TouchableOpacity key={k} testID={`screener-add-factor-${k}`} style={styles.addChip} onPress={() => setFactors(fs => [...fs, mkFactor(k)])}>
                  <Ionicons name="add" size={12} color="#475569" />
                  <Text style={styles.chipText}>{k}</Text>
                </TouchableOpacity>
              ))}
            </View>
          )}

          {/* Run controls */}
          <Text style={styles.section}>3 · Rank</Text>
          <View style={styles.runRow}>
            <Text style={styles.runLabel}>Top</Text>
            <TextInput testID="screener-finalists-input" style={styles.finInput} keyboardType="number-pad" value={finalists}
              onChangeText={(t) => setFinalists(t.replace(/[^0-9]/g, ''))} />
            <Text style={styles.runLabel}>finalists</Text>
            <TouchableOpacity testID="screener-ai-toggle" style={styles.aiToggle} onPress={() => setUseAi(v => !v)}>
              <Ionicons name={useAi ? 'checkbox' : 'square-outline'} size={16} color={primary} />
              <Text style={styles.aiText}>AI-assess “AI” factors</Text>
            </TouchableOpacity>
          </View>

          {quote != null && (
            <Text style={styles.quote}>
              Est. cost: <Text style={{ fontWeight: '800', color: primary }}>{quote} credits</Text>
              {balance != null ? `  ·  balance ${balance}` : ''}
            </Text>
          )}

          <TouchableOpacity testID="screener-run-btn" style={[styles.btn, { backgroundColor: primary }]} onPress={doRun} disabled={busy || !factors.length}>
            {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>Run Screener</Text>}
          </TouchableOpacity>
        </>
      )}

      {!!err && <Text style={styles.err}>{err}</Text>}

      {/* Results */}
      {results && (
        <View style={styles.results}>
          <View style={styles.resultsHead}>
            <Text style={styles.section}>Top {results.length} matches</Text>
            {exportUrl && (
              <TouchableOpacity testID="screener-export-csv-btn" onPress={() => { if (Platform.OS === 'web') window.open(exportUrl!, '_blank'); }}>
                <Text style={[styles.export, { color: primary }]}><Ionicons name="download" size={13} /> CSV</Text>
              </TouchableOpacity>
            )}
          </View>
          {results.map((r) => (
            <View key={r.rank} style={styles.resCard}>
              <View style={[styles.rankBadge, { backgroundColor: primary }]}><Text style={styles.rankText}>{r.rank}</Text></View>
              <View style={{ flex: 1 }}>
                <View style={styles.resTop}>
                  <Text style={styles.resName} numberOfLines={1}>{r.name}</Text>
                  <Text style={[styles.resScore, { color: primary }]}>{r.score}</Text>
                </View>
                <View style={styles.scoreTrack}>
                  <View style={[styles.scoreFill, { width: `${Math.max(2, Math.min(100, r.score))}%`, backgroundColor: accent }]} />
                </View>
                <Text style={styles.resFactors} numberOfLines={2}>
                  {(r.factor_scores || []).map((fs: any) => `${fs.name}: ${fs.pct == null ? '—' : fs.pct}${fs.ai ? '✨' : ''}`).join('   ·   ')}
                </Text>
              </View>
            </View>
          ))}

          {/* Send the shortlist into a full decision flow */}
          <Text style={styles.sendHint}>Take this shortlist further:</Text>
          <View style={styles.sendRow}>
            <TouchableOpacity testID="screener-send-mydezider" style={[styles.sendBtn, { borderColor: primary }]}
              onPress={() => sendTo('mydezider')} disabled={!!sending}>
              {sending === 'mydezider' ? <ActivityIndicator size="small" color={primary} /> : (
                <><Ionicons name="git-branch" size={15} color={primary} /><Text style={[styles.sendText, { color: primary }]}>Send to MyDezider</Text></>
              )}
            </TouchableOpacity>
            <TouchableOpacity testID="screener-send-proscons" style={[styles.sendBtn, { borderColor: primary }]}
              onPress={() => sendTo('pros_cons')} disabled={!!sending}>
              {sending === 'pros_cons' ? <ActivityIndicator size="small" color={primary} /> : (
                <><Ionicons name="layers" size={15} color={primary} /><Text style={[styles.sendText, { color: primary }]}>Send to Pros &amp; Cons</Text></>
              )}
            </TouchableOpacity>
          </View>
        </View>
      )}

      <UrlAccessConsentModal
        visible={urlConsentOpen}
        url={url.trim()}
        primary={primary}
        onCancel={() => setUrlConsentOpen(false)}
        onConfirm={onUrlConsent}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  wrap: { marginTop: 8 },
  section: { fontSize: 13, fontWeight: '800', color: '#0F172A', marginTop: 14, marginBottom: 8 },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 5, borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 18, paddingHorizontal: 12, paddingVertical: 7, backgroundColor: '#fff' },
  addChip: { flexDirection: 'row', alignItems: 'center', gap: 3, borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 14, paddingHorizontal: 10, paddingVertical: 5, backgroundColor: '#F8FAFC' },
  chipText: { fontSize: 12.5, color: '#475569', fontWeight: '600' },
  area: { borderWidth: 1, borderColor: '#D1D5DB', borderRadius: 10, padding: 12, fontSize: 13, color: '#0F172A', minHeight: 96, marginTop: 10, textAlignVertical: 'top', fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' },
  input: { borderWidth: 1, borderColor: '#D1D5DB', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 11, fontSize: 14, color: '#0F172A', marginTop: 10 },
  hint: { fontSize: 12.5, color: '#64748B', marginTop: 10 },
  btn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 13, borderRadius: 11, marginTop: 12 },
  btnText: { color: '#fff', fontSize: 14.5, fontWeight: '800' },
  okLine: { fontSize: 12.5, color: '#16A34A', fontWeight: '700', marginTop: 10 },

  sendHint: { fontSize: 12.5, fontWeight: '700', color: '#334155', marginTop: 16, marginBottom: 8 },
  sendRow: { flexDirection: 'row', gap: 10 },
  sendBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, borderWidth: 1.5, borderRadius: 11, paddingVertical: 11, backgroundColor: '#fff' },
  sendText: { fontSize: 12.5, fontWeight: '800' },

  factorRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#F8FAFC', borderRadius: 10, padding: 10, marginBottom: 8, gap: 8 },
  factorName: { fontSize: 13.5, fontWeight: '700', color: '#1F2937' },
  factorCtrls: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 6, flexWrap: 'wrap' },
  weightInput: { borderWidth: 1, borderColor: '#D1D5DB', borderRadius: 7, paddingHorizontal: 8, paddingVertical: 4, width: 46, fontSize: 13, color: '#0F172A', backgroundColor: '#fff', textAlign: 'center' },
  wLabel: { fontSize: 11, color: '#94A3B8' },
  dirToggle: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  dirText: { fontSize: 11.5, fontWeight: '700' },
  typePill: { fontSize: 11, fontWeight: '800', color: '#fff', backgroundColor: '#94A3B8', paddingHorizontal: 7, paddingVertical: 3, borderRadius: 8, overflow: 'hidden' },

  runRow: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  runLabel: { fontSize: 13, color: '#475569' },
  finInput: { borderWidth: 1, borderColor: '#D1D5DB', borderRadius: 7, paddingHorizontal: 8, paddingVertical: 5, width: 52, fontSize: 14, color: '#0F172A', backgroundColor: '#fff', textAlign: 'center' },
  aiToggle: { flexDirection: 'row', alignItems: 'center', gap: 5, marginLeft: 'auto' },
  aiText: { fontSize: 12.5, color: '#475569', fontWeight: '600' },
  quote: { fontSize: 13, color: '#475569', marginTop: 12 },
  err: { color: '#B91C1C', fontSize: 13, marginTop: 12, fontWeight: '600' },

  results: { marginTop: 18 },
  resultsHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  export: { fontSize: 13, fontWeight: '800' },
  resCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#fff', borderWidth: 1, borderColor: '#E5E7EB', borderRadius: 12, padding: 12, marginBottom: 8 },
  rankBadge: { width: 26, height: 26, borderRadius: 13, alignItems: 'center', justifyContent: 'center' },
  rankText: { color: '#fff', fontSize: 12.5, fontWeight: '800' },
  resTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  resName: { fontSize: 14, fontWeight: '700', color: '#1F2937', flex: 1, marginRight: 8 },
  resScore: { fontSize: 15, fontWeight: '800' },
  scoreTrack: { height: 6, borderRadius: 3, backgroundColor: '#EEF2F7', marginTop: 6, overflow: 'hidden' },
  scoreFill: { height: 6, borderRadius: 3 },
  resFactors: { fontSize: 11.5, color: '#64748B', marginTop: 6 },
});
