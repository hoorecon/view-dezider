/**
 * /admin/import-analytics — Import-from-URL Intelligence (Super-Admin).
 *
 * The learning & enhancement loop for the Import-URL feature: every run is
 * recorded (URL + the 4 accuracy hints + AI engine + LLM-classified page type
 * + pipeline route + outcome + EXACT prompt / raw LLM response + 👍/👎 user
 * verdicts) and surfaced here, with PostHog receiving lightweight twin events.
 *
 * Sections:
 *  1. KPI cards (runs / success / hint-pass / escalation / retry / 👍 rate / latency)
 *  2. Breakdowns by page type, AI provider, pipeline route
 *  3. Run list with filters → tap a run for full drill-down incl. prompts
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, Modal, useWindowDimensions,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';

const C = {
  bg: '#F8FAFC', card: '#FFFFFF', border: '#E2E8F0', text: '#0F172A',
  muted: '#64748B', primary: '#7C3AED', green: '#059669', red: '#DC2626',
  amber: '#D97706', blue: '#2563EB', chipBg: '#F1F5F9',
};

const PAGE_TYPES = ['comparison_matrix', 'listing_filter', 'detail', 'search_grid', 'article_roundup'];
const PT_LABEL: Record<string, string> = {
  comparison_matrix: 'Comparison Matrix', listing_filter: 'Listing / Filter',
  detail: 'Detail Page', search_grid: 'Search Grid', article_roundup: 'Article Round-up',
  '(none)': 'Unclassified',
};
const ROUTE_LABEL: Record<string, string> = {
  deterministic_hier: 'Matrix parse (free)', deterministic_flat: 'Table parse (free)',
  ai_extraction: 'AI extraction', deterministic_fallback: 'Parse fallback',
  llm_flat_fallback: 'LLM flat fallback', '(none)': '—',
};

const pct = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${v}%`);
const ms = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${v}ms`;
const when = (ts: string) => {
  try { return new Date(ts).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }); }
  catch { return ts; }
};

export default function AdminImportAnalyticsScreen() {
  const { width } = useWindowDimensions();
  const isWide = width >= 1000;

  const [days, setDays] = useState(30);
  const [summary, setSummary] = useState<any>(null);
  const [runs, setRuns] = useState<any[]>([]);
  const [runsTotal, setRunsTotal] = useState(0);
  const [ptFilter, setPtFilter] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<any>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const q = ptFilter ? `&page_type=${ptFilter}` : '';
      const [s, r] = await Promise.all([
        api.get(`/admin/import-analytics/summary?days=${days}`),
        api.get(`/admin/import-analytics/runs?days=${days}&limit=50${q}`),
      ]);
      setSummary(s.data);
      setRuns(r.data.items || []);
      setRunsTotal(r.data.total || 0);
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to load import analytics');
    } finally { setLoading(false); }
  }, [days, ptFilter]);

  useEffect(() => { loadAll(); }, [loadAll]);

  const openRun = async (id: string) => {
    try {
      const r = await api.get(`/admin/import-analytics/runs/${id}`);
      setDetail(r.data);
      setDetailOpen(true);
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to load run');
    }
  };

  if (loading && !summary) {
    return (
      <SafeAreaView style={st.safe} testID="import-analytics-loading">
        <ActivityIndicator size="large" color={C.primary} style={{ marginTop: 60 }} />
      </SafeAreaView>
    );
  }

  const fb = summary?.feedback || {};
  const kpis = [
    { label: 'Runs', value: String(summary?.total_runs ?? 0), color: C.text },
    { label: 'Success', value: pct(summary?.success_rate), color: C.green },
    { label: 'Hint pass', value: pct(summary?.hint_pass_rate), color: C.blue },
    { label: 'Hint adoption', value: pct(summary?.hint_adoption_rate), color: C.muted },
    { label: 'AI escalation', value: pct(summary?.ai_escalation_rate), color: C.primary },
    { label: 'Retry rate', value: pct(summary?.retry_rate), color: C.amber },
    { label: '👍 Satisfaction', value: fb.satisfaction === null || fb.satisfaction === undefined ? '—' : `${fb.satisfaction}% (${fb.up}↑ ${fb.down}↓)`, color: C.green },
    { label: 'Avg latency', value: ms(summary?.avg_latency_ms), color: C.text },
  ];

  return (
    <SafeAreaView style={st.safe} testID="admin-import-analytics-screen">
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 60 }}>
        <View style={st.headRow}>
          <View style={{ flex: 1 }}>
            <Text style={st.h1} testID="import-analytics-title">Import-URL Intelligence</Text>
            <Text style={st.h1sub}>Accuracy, hints & prompt telemetry per page type — the learning loop</Text>
          </View>
          <TouchableOpacity testID="import-analytics-refresh" style={st.refreshBtn} onPress={loadAll}>
            <Ionicons name="refresh" size={16} color={C.primary} />
          </TouchableOpacity>
        </View>

        {/* Window selector */}
        <View style={st.chipRow}>
          {[7, 30, 90].map(d => (
            <TouchableOpacity key={d} testID={`import-analytics-days-${d}`}
              style={[st.chip, days === d && st.chipOn]} onPress={() => setDays(d)}>
              <Text style={[st.chipTxt, days === d && st.chipTxtOn]}>{d}d</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* KPI cards */}
        <View style={[st.kpiWrap, { flexDirection: 'row', flexWrap: 'wrap' }]} testID="import-analytics-kpis">
          {kpis.map(k => (
            <View key={k.label} style={[st.kpi, { width: isWide ? '23.5%' : '47%' }]}>
              <Text style={st.kpiLabel}>{k.label}</Text>
              <Text style={[st.kpiValue, { color: k.color }]} numberOfLines={1}>{k.value}</Text>
            </View>
          ))}
        </View>

        {/* Breakdowns */}
        {[['By page type', 'by_page_type', PT_LABEL], ['By AI provider', 'by_provider', null], ['By pipeline route', 'by_route', ROUTE_LABEL]].map(([title, key, labels]: any) => (
          <View key={key} style={st.card} testID={`import-analytics-${key}`}>
            <Text style={st.cardTitle}>{title}</Text>
            <View style={st.tRowHead}>
              <Text style={[st.th, { flex: 2.2 }]}>Segment</Text>
              <Text style={st.th}>Runs</Text>
              <Text style={st.th}>Success</Text>
              <Text style={st.th}>Hint pass</Text>
              <Text style={st.th}>👍/👎</Text>
              <Text style={st.th}>Latency</Text>
            </View>
            {(summary?.[key] || []).map((row: any) => (
              <View key={row.key} style={st.tRow}>
                <Text style={[st.td, { flex: 2.2, fontWeight: '600' }]} numberOfLines={1}>
                  {(labels && labels[row.key]) || row.key}
                </Text>
                <Text style={st.td}>{row.runs}</Text>
                <Text style={[st.td, { color: (row.success_rate ?? 100) >= 80 ? C.green : C.red }]}>{pct(row.success_rate)}</Text>
                <Text style={st.td}>{pct(row.hint_pass_rate)}</Text>
                <Text style={st.td}>{row.feedback_up}↑ {row.feedback_down}↓</Text>
                <Text style={st.td}>{ms(row.avg_latency_ms)}</Text>
              </View>
            ))}
            {!(summary?.[key] || []).length && <Text style={st.empty}>No runs in this window yet.</Text>}
          </View>
        ))}

        {/* Runs list */}
        <View style={st.card} testID="import-analytics-runs">
          <Text style={st.cardTitle}>Runs ({runsTotal})</Text>
          <View style={[st.chipRow, { marginBottom: 10 }]}>
            <TouchableOpacity testID="import-analytics-pt-all" style={[st.chip, !ptFilter && st.chipOn]} onPress={() => setPtFilter(null)}>
              <Text style={[st.chipTxt, !ptFilter && st.chipTxtOn]}>All</Text>
            </TouchableOpacity>
            {PAGE_TYPES.map(pt => (
              <TouchableOpacity key={pt} testID={`import-analytics-pt-${pt}`}
                style={[st.chip, ptFilter === pt && st.chipOn]} onPress={() => setPtFilter(pt)}>
                <Text style={[st.chipTxt, ptFilter === pt && st.chipTxtOn]}>{PT_LABEL[pt]}</Text>
              </TouchableOpacity>
            ))}
          </View>
          {runs.map(r => (
            <TouchableOpacity key={r.id} testID={`import-run-${r.id}`} style={st.runRow}
              onPress={() => openRun(r.id)} activeOpacity={0.75}>
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text style={st.runUrl} numberOfLines={1}>{r.url}</Text>
                <Text style={st.runMeta} numberOfLines={1}>
                  {when(r.ts)} · {PT_LABEL[r.page_type] || r.page_type || '—'} · {ROUTE_LABEL[r.route] || r.route || '—'}
                  {r.ai_provider ? ` · ${r.ai_provider}` : ''} · {ms(r.latency_ms)}
                  {r.hints_given ? ` · hints${r.hint_pass === false ? ' ✗' : r.hint_pass ? ' ✓' : ''}` : ''}
                </Text>
              </View>
              <View style={{ alignItems: 'flex-end', gap: 3 }}>
                <Text style={[st.runBadge, { color: r.status === 'success' ? C.green : C.red }]}>
                  {r.status === 'success' ? `${r.factors_added ?? r.factor_count ?? 0}F / ${r.options_added ?? r.item_count ?? 0}O` : 'ERROR'}
                </Text>
                {r.feedback && (
                  <Ionicons name={r.feedback === 'up' ? 'thumbs-up' : 'thumbs-down'} size={13}
                    color={r.feedback === 'up' ? C.green : C.red} />
                )}
              </View>
            </TouchableOpacity>
          ))}
          {!runs.length && <Text style={st.empty}>No runs match these filters.</Text>}
        </View>
      </ScrollView>

      {/* Run drill-down — incl. exact prompt + raw LLM response */}
      <Modal visible={detailOpen} transparent animationType="fade" onRequestClose={() => setDetailOpen(false)}>
        <View style={st.mOverlay}>
          <View style={[st.mBox, { maxWidth: isWide ? 860 : '94%' }]} testID="import-run-detail-modal">
            <View style={st.mHead}>
              <Text style={st.mTitle}>Run drill-down</Text>
              <TouchableOpacity testID="import-run-detail-close" onPress={() => setDetailOpen(false)}>
                <Ionicons name="close" size={20} color={C.muted} />
              </TouchableOpacity>
            </View>
            <ScrollView style={{ maxHeight: 560 }}>
              {detail && (
                <>
                  {[
                    ['URL', detail.url], ['When', when(detail.ts)], ['Endpoint', detail.endpoint],
                    ['Status', detail.status + (detail.error ? ` — ${detail.error}` : '')],
                    ['Page type', `${PT_LABEL[detail.page_type] || detail.page_type || '—'} (conf ${detail.page_type_confidence ?? '—'}, via ${detail.classifier_provider || '—'})`],
                    ['Route', ROUTE_LABEL[detail.route] || detail.route || '—'],
                    ['Engine', `${detail.ai_tier} → ${detail.ai_provider || '—'}${detail.ai_retry_used ? ' · corrective retry used' : ''}${detail.ai_tokens ? ` · ~${detail.ai_tokens} tokens` : ''}`],
                    ['Hints', detail.hints_given ? JSON.stringify(detail.hints) : '(none given)'],
                    ['Hint warnings', (detail.hint_warnings || []).join(' ') || (detail.hints_given ? 'none — passed ✓' : '—')],
                    ['Outcome', detail.status === 'success' ? `${detail.factors_added ?? detail.factor_count ?? 0} factors, ${detail.options_added ?? detail.item_count ?? 0} options, ${ms(detail.latency_ms)}` : '—'],
                    ['User verdict', detail.feedback ? (detail.feedback === 'up' ? '👍 accurate' : '👎 inaccurate') : '(not given)'],
                  ].map(([k, v]: any) => (
                    <View key={k} style={st.dRow}>
                      <Text style={st.dKey}>{k}</Text>
                      <Text style={st.dVal} selectable>{String(v)}</Text>
                    </View>
                  ))}
                  {detail.ai_system_prompt ? (
                    <>
                      <Text style={st.promptTitle}>System prompt (exact, truncated 15KB)</Text>
                      <Text style={st.promptBody} selectable testID="import-run-system-prompt">{detail.ai_system_prompt}</Text>
                      <Text style={st.promptTitle}>Raw LLM response</Text>
                      <Text style={st.promptBody} selectable testID="import-run-raw-response">{detail.ai_raw_response || '(empty)'}</Text>
                    </>
                  ) : (
                    <Text style={st.empty}>{detail.bodies_purged ? 'Prompt bodies purged (90-day retention).' : 'No AI call was made for this run (deterministic parse).'}</Text>
                  )}
                </>
              )}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  safe: { flex: 1, backgroundColor: C.bg },
  headRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 12 },
  h1: { fontSize: 20, fontWeight: '800', color: C.text },
  h1sub: { fontSize: 12, color: C.muted, marginTop: 2 },
  refreshBtn: { padding: 9, borderRadius: 10, backgroundColor: '#F3E8FF' },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  chip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, backgroundColor: C.chipBg, borderWidth: 1, borderColor: C.border },
  chipOn: { backgroundColor: C.primary, borderColor: C.primary },
  chipTxt: { fontSize: 12, color: C.muted, fontWeight: '600' },
  chipTxtOn: { color: '#FFF' },
  kpiWrap: { gap: 8, marginBottom: 14 },
  kpi: { backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 12 },
  kpiLabel: { fontSize: 11, color: C.muted, fontWeight: '600' },
  kpiValue: { fontSize: 17, fontWeight: '800', marginTop: 3 },
  card: { backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 14, marginBottom: 14 },
  cardTitle: { fontSize: 14, fontWeight: '700', color: C.text, marginBottom: 10 },
  tRowHead: { flexDirection: 'row', paddingBottom: 6, borderBottomWidth: 1, borderBottomColor: C.border },
  th: { flex: 1, fontSize: 11, fontWeight: '700', color: C.muted },
  tRow: { flexDirection: 'row', paddingVertical: 7, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  td: { flex: 1, fontSize: 12, color: C.text },
  empty: { fontSize: 12, color: C.muted, paddingVertical: 10, textAlign: 'center' },
  runRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 9, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  runUrl: { fontSize: 12.5, fontWeight: '600', color: C.blue },
  runMeta: { fontSize: 11, color: C.muted, marginTop: 2 },
  runBadge: { fontSize: 12, fontWeight: '800' },
  mOverlay: { flex: 1, backgroundColor: 'rgba(15,23,42,0.5)', alignItems: 'center', justifyContent: 'center', padding: 16 },
  mBox: { backgroundColor: C.card, borderRadius: 14, padding: 16, width: '100%' },
  mHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 },
  mTitle: { fontSize: 16, fontWeight: '800', color: C.text },
  dRow: { flexDirection: 'row', paddingVertical: 5, borderBottomWidth: 1, borderBottomColor: '#F8FAFC' },
  dKey: { width: 110, fontSize: 11.5, fontWeight: '700', color: C.muted },
  dVal: { flex: 1, fontSize: 12, color: C.text },
  promptTitle: { fontSize: 12.5, fontWeight: '800', color: C.primary, marginTop: 12, marginBottom: 6 },
  promptBody: { fontSize: 11, color: C.text, backgroundColor: '#F8FAFC', borderRadius: 8, borderWidth: 1, borderColor: C.border, padding: 10, fontFamily: 'monospace' as any },
});
