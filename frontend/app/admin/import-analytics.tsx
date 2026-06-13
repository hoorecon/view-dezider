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
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
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
  deep_links: 'Deep Import · Link pick', deep_hubs: 'Deep Import · Hub locate',
  deep_consolidate: 'Deep Import · Consolidate',
  '(none)': 'Unclassified',
};
const ROUTE_LABEL: Record<string, string> = {
  deterministic_hier: 'Matrix parse (free)', deterministic_flat: 'Table parse (free)',
  ai_extraction: 'AI extraction', deterministic_fallback: 'Parse fallback',
  llm_flat_fallback: 'LLM flat fallback', '(none)': '—',
};

const pct = (v: number | null | undefined) => (v === null || v === undefined ? '—' : `${v}%`);
const cr = (v: number | null | undefined) =>
  v === null || v === undefined || !Number(v) ? '—' : `${Number(v).toFixed(1)} cr`;
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
  const [expandedCall, setExpandedCall] = useState<number | null>(null);

  // ── AI Auto-Tune (prompt suggestions) ──
  const [tuning, setTuning] = useState<{ suggestions: any[]; active_overrides: any[] } | null>(null);
  const [generating, setGenerating] = useState(false);
  const [expandedSug, setExpandedSug] = useState<string | null>(null);

  // ── Engine tiering (margin protection) ──
  const [engineRecos, setEngineRecos] = useState<any>(null);

  // ── Import quality floor (silent under-extraction guard) ──
  const [qFloor, setQFloor] = useState<number | null>(null);
  const [qFloorDraft, setQFloorDraft] = useState<string>('');
  const [qFloorSaving, setQFloorSaving] = useState(false);

  const loadQualityFloor = useCallback(async () => {
    try {
      const r = await api.get('/admin/import-analytics/quality-floor');
      setQFloor(r.data?.min_factors ?? null);
      setQFloorDraft(String(r.data?.min_factors ?? ''));
    } catch { /* card shows loading state */ }
  }, []);

  const saveQualityFloor = async () => {
    const n = Number(qFloorDraft);
    if (!Number.isInteger(n) || n < 1 || n > 50) {
      showAlert('Quality floor', 'Enter an integer between 1 and 50.');
      return;
    }
    setQFloorSaving(true);
    try {
      await api.put('/admin/import-analytics/quality-floor', { min_factors: n });
      showAlert('Quality floor', `Runs with fewer than ${n} factors will now be stamped PARTIAL.`);
      await loadQualityFloor();
      await loadAll();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to save quality floor');
    } finally { setQFloorSaving(false); }
  };

  const loadEngineRecos = useCallback(async () => {
    try {
      const r = await api.get('/admin/import-analytics/engine-recos');
      setEngineRecos(r.data);
    } catch { /* card shows loading state */ }
  }, []);

  const applyTier = async (stage: string, tier: string) => {
    try {
      await api.put('/admin/import-analytics/engine-tiers', { stage, tier });
      showAlert('Engine tiering', `${stage} now runs on the "${tier}" tier for every deep import.`);
      await loadEngineRecos();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to set tier');
    }
  };

  const loadTuning = useCallback(async () => {
    try {
      const r = await api.get('/admin/import-analytics/tuning');
      setTuning(r.data);
    } catch { /* panel shows empty state */ }
  }, []);

  const generateSuggestions = async () => {
    setGenerating(true);
    try {
      const r = await api.post(`/admin/import-analytics/tuning/generate?days=${days}`);
      const created = r.data?.created?.length || 0;
      const reasons = (r.data?.skipped || []).map((s: any) => `${PT_LABEL[s.page_type] || s.page_type}: ${s.reason}`).join('\n');
      showAlert('Auto-Tune', created
        ? `${created} suggestion(s) generated — review below.`
        : `No suggestions generated.\n${reasons}`);
      await loadTuning();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Auto-tune generation failed');
    } finally { setGenerating(false); }
  };

  const decideSuggestion = async (id: string, action: 'approve' | 'reject') => {
    try {
      await api.post(`/admin/import-analytics/tuning/${id}/${action}`);
      showAlert('Auto-Tune', action === 'approve'
        ? 'Approved — the revised prompt block is now LIVE for this page type.'
        : 'Suggestion rejected.');
      await loadTuning();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || `Failed to ${action}`);
    }
  };

  const revertOverride = async (pt: string) => {
    try {
      await api.delete(`/admin/import-analytics/tuning/override/${pt}`);
      showAlert('Auto-Tune', `${PT_LABEL[pt] || pt} reverted to the built-in default prompt.`);
      await loadTuning();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to revert');
    }
  };

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
  useEffect(() => { loadTuning(); }, [loadTuning]);
  useEffect(() => { loadEngineRecos(); }, [loadEngineRecos]);
  useEffect(() => { loadQualityFloor(); }, [loadQualityFloor]);

  const openRun = async (id: string) => {
    try {
      const r = await api.get(`/admin/import-analytics/runs/${id}`);
      setDetail(r.data);
      setExpandedCall(null);
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
    { label: 'Partial (below quality floor)', value: summary?.partial_count != null ? `${summary.partial_count} (${pct(summary?.partial_rate)})` : '—', color: C.amber },
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
              <Text style={st.th}>Avg cr</Text>
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
                <Text style={st.td}>{cr(row.avg_credits)}</Text>
              </View>
            ))}
            {!(summary?.[key] || []).length && <Text style={st.empty}>No runs in this window yet.</Text>}
          </View>
        ))}

        {/* AI Auto-Tune — failed runs → AI-proposed prompt edits → approve to go live */}
        <View style={st.card} testID="import-analytics-tuning">
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <View style={{ flex: 1 }}>
              <Text style={st.cardTitle}>AI Auto-Tune (prompt suggestions)</Text>
              <Text style={{ fontSize: 11, color: C.muted, marginTop: -6, marginBottom: 4 }}>
                AI reads failing runs (errors, hint mismatches, 👎) per page type and proposes prompt edits. Approving makes the edit LIVE instantly.
              </Text>
            </View>
            <TouchableOpacity testID="import-tuning-generate" style={st.genBtn}
              onPress={generateSuggestions} disabled={generating}>
              {generating
                ? <ActivityIndicator size="small" color="#FFF" />
                : <Ionicons name="sparkles" size={14} color="#FFF" />}
              <Text style={st.genBtnTxt}>{generating ? 'Analysing…' : 'Generate (AI)'}</Text>
            </TouchableOpacity>
          </View>

          {!!(tuning?.active_overrides || []).length && (
            <View style={{ marginBottom: 10 }}>
              <Text style={st.subHead}>Active overrides</Text>
              <View style={st.chipRow}>
                {(tuning?.active_overrides || []).map((o: any) => (
                  <View key={o.key} style={st.ovChip} testID={`import-tuning-override-${o.key}`}>
                    <Ionicons name="flash" size={11} color={C.green} />
                    <Text style={st.ovChipTxt}>{PT_LABEL[o.key] || o.key}</Text>
                    <TouchableOpacity testID={`import-tuning-revert-${o.key}`} onPress={() => revertOverride(o.key)}>
                      <Text style={st.ovRevert}>revert</Text>
                    </TouchableOpacity>
                  </View>
                ))}
              </View>
            </View>
          )}

          {(tuning?.suggestions || []).map((s: any) => (
            <View key={s.id} style={st.sugBox} testID={`import-tuning-suggestion-${s.id}`}>
              <TouchableOpacity style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}
                onPress={() => setExpandedSug(expandedSug === s.id ? null : s.id)} activeOpacity={0.75}>
                <Text style={[st.sugStatus, {
                  color: s.status === 'approved' ? C.green : s.status === 'rejected' ? C.red : C.amber,
                }]}>{s.status.toUpperCase()}</Text>
                <Text style={st.sugPt}>{PT_LABEL[s.page_type] || s.page_type}</Text>
                <Text style={st.runMeta}>{when(s.ts)} · {s.evidence?.failing_runs} failing run(s)</Text>
                <Ionicons name={expandedSug === s.id ? 'chevron-up' : 'chevron-down'} size={14} color={C.muted} />
              </TouchableOpacity>
              <Text style={st.sugRationale} numberOfLines={expandedSug === s.id ? undefined : 2}>
                {s.rationale}
              </Text>
              {expandedSug === s.id && (
                <>
                  <Text style={st.subHead}>Expected impact</Text>
                  <Text style={st.sugRationale}>{s.expected_impact || '—'}</Text>
                  <Text style={st.subHead}>Current prompt block</Text>
                  <Text style={st.promptBody} selectable>{(s.current_guidance || '(empty)').trim()}</Text>
                  <Text style={st.subHead}>Proposed prompt block</Text>
                  <Text style={[st.promptBody, { borderColor: '#C4B5FD', backgroundColor: '#FAF5FF' }]} selectable>
                    {(s.proposed_guidance || '').trim()}
                  </Text>
                </>
              )}
              {s.status === 'proposed' && (
                <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
                  <TouchableOpacity testID={`import-tuning-approve-${s.id}`} style={st.approveBtn}
                    onPress={() => decideSuggestion(s.id, 'approve')}>
                    <Text style={st.approveTxt}>Approve & go live</Text>
                  </TouchableOpacity>
                  <TouchableOpacity testID={`import-tuning-reject-${s.id}`} style={st.rejectBtn}
                    onPress={() => decideSuggestion(s.id, 'reject')}>
                    <Text style={st.rejectTxt}>Reject</Text>
                  </TouchableOpacity>
                </View>
              )}
            </View>
          ))}
          {!(tuning?.suggestions || []).length && (
            <Text style={st.empty}>No suggestions yet — tap &quot;Generate (AI)&quot; once some failing runs accumulate.</Text>
          )}
        </View>

        {/* Quality floor — silent under-extraction guard */}
        <View style={st.card} testID="import-analytics-quality-floor">
          <Text style={st.cardTitle}>Quality floor — silent under-extraction guard</Text>
          <Text style={{ fontSize: 11, color: C.muted, marginTop: -6, marginBottom: 8 }}>
            Runs that return FEWER than this many factors are stamped <Text style={{ fontWeight: '800', color: C.amber }}>PARTIAL</Text> instead of success — they
            appear amber in the runs list, are fed into Auto-Tune as failing candidates, and do
            NOT trigger the failure-alert. Set higher to catch more thin parses; lower to tolerate
            sparse pages.
          </Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <Text style={st.runMeta}>Min factors:</Text>
            <TextInput
              testID="import-quality-floor-input"
              keyboardType="number-pad" maxLength={2}
              value={qFloorDraft} onChangeText={setQFloorDraft}
              style={st.qfInput} placeholder="4" placeholderTextColor={C.muted}
            />
            <TouchableOpacity testID="import-quality-floor-save"
              style={[st.approveBtn, qFloorSaving && { opacity: 0.6 }]}
              onPress={saveQualityFloor} disabled={qFloorSaving}>
              <Text style={st.approveTxt}>{qFloorSaving ? 'Saving…' : 'Save'}</Text>
            </TouchableOpacity>
            {qFloor != null && (
              <Text style={st.runMeta}>currently: {qFloor}</Text>
            )}
          </View>
        </View>


        {/* Engine tiering — per deep-import stage: success/cost stats → tier control */}
        <View style={st.card} testID="import-analytics-engine-tiers">
          <Text style={st.cardTitle}>Engine tiering — Deep Import (margin protection)</Text>
          <Text style={{ fontSize: 11, color: C.muted, marginTop: -6, marginBottom: 8 }}>
            Per-stage success % and avg credits per engine tier (from the AI call trace). Set each
            stage to fast / precise / job (&quot;job&quot; = follow the tier the user picked).
          </Text>
          {(engineRecos?.stages || []).map((sg: any) => (
            <View key={sg.stage} style={st.engRow} testID={`engine-tier-row-${sg.stage}`}>
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text style={st.engStage}>{sg.label}</Text>
                <Text style={st.runMeta} numberOfLines={2}>
                  {Object.entries(sg.tiers || {}).map(([t, v]: any) =>
                    `${t}: ${v.success_rate ?? '—'}% over ${v.runs} · ${v.avg_credits ?? '—'} cr`).join('   ') || 'No call data yet'}
                </Text>
                {sg.recommendation !== 'keep' && (
                  <Text style={st.engReco} testID={`engine-tier-reco-${sg.stage}`}>
                    ⚙ {sg.recommendation === 'downgrade_to_fast' ? 'Recommend: switch to FAST'
                      : sg.recommendation === 'upgrade_to_precise' ? 'Recommend: switch to PRECISE'
                      : 'Recommend: trial FAST'}
                    {sg.projected_saving ? ` (~${sg.projected_saving} cr/call saved)` : ''} — {sg.reason}
                  </Text>
                )}
              </View>
              <View style={{ flexDirection: 'row', gap: 4 }}>
                {['fast', 'precise', 'job'].map(t => (
                  <TouchableOpacity key={t} testID={`engine-tier-set-${sg.stage}-${t}`}
                    style={[st.engChip, sg.current_tier === t && st.engChipOn]}
                    onPress={() => applyTier(sg.stage, t)}>
                    <Text style={[st.engChipTxt, sg.current_tier === t && st.engChipTxtOn]}>{t}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          ))}
          {!engineRecos && <Text style={st.empty}>Loading engine stats…</Text>}
        </View>

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
                  {r.total_credits ? ` · ${Number(r.total_credits).toFixed(1)} cr` : ''}
                  {r.hints_given ? ` · hints${r.hint_pass === false ? ' ✗' : r.hint_pass ? ' ✓' : ''}` : ''}
                </Text>
              </View>
              <View style={{ alignItems: 'flex-end', gap: 3 }}>
                {r.status === 'success' ? (
                  <Text style={[st.runBadge, { color: C.green }]}>
                    {`${r.factors_added ?? r.factor_count ?? 0}F / ${r.options_added ?? r.item_count ?? 0}O`}
                  </Text>
                ) : r.status === 'partial' ? (
                  <>
                    <Text style={[st.runBadge, { color: C.amber }]}>
                      {`${r.factors_added ?? r.factor_count ?? 0}F / ${r.options_added ?? r.item_count ?? 0}O`}
                    </Text>
                    <Text style={[st.runMeta, { color: C.amber, fontWeight: '700' }]}>PARTIAL</Text>
                  </>
                ) : (
                  <Text style={[st.runBadge, { color: C.red }]}>ERROR</Text>
                )}
                {r.feedback && (
                  <Ionicons name={r.feedback === 'up' ? 'thumbs-up' : 'thumbs-down'} size={13}
                    color={r.feedback === 'up' ? C.green : C.red} />
                )}
                {r.user_reported_failure && (
                  <Ionicons name="school" size={13} color="#92400E"
                    testID={`import-run-${r.id}-train-flag`} />
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
                    ...(detail.partial_reason ? [['Partial reason', detail.partial_reason]] : []),
                    ['Page type', `${PT_LABEL[detail.page_type] || detail.page_type || '—'} (conf ${detail.page_type_confidence ?? '—'}, via ${detail.classifier_provider || '—'})`],
                    ['Route', ROUTE_LABEL[detail.route] || detail.route || '—'],
                    ['Engine', (detail.ai_engines || []).length
                      ? `${detail.ai_tier} → ${detail.ai_engines.join(', ')}${detail.ai_tokens ? ` · ~${detail.ai_tokens} tokens` : ''}`
                      : `${detail.ai_tier} → ${detail.ai_provider || '—'}${detail.ai_retry_used ? ' · corrective retry used' : ''}${detail.ai_tokens ? ` · ~${detail.ai_tokens} tokens` : ''}`],
                    ['Credits', detail.total_credits != null
                      ? `AI ${(detail.ai_credits ?? 0).toFixed(2)} + scrape ${(detail.scrape?.app_credits ?? 0).toFixed(2)} = ${Number(detail.total_credits).toFixed(2)} cr${detail.scrape?.fetches ? ` (${detail.scrape.fetches} scrape fetch${detail.scrape.fetches > 1 ? 'es' : ''})` : ''}`
                      : '—'],
                    ['Hints', detail.hints_given ? JSON.stringify(detail.hints) : '(none given)'],
                    ['Hint warnings', (detail.hint_warnings || []).join(' ') || (detail.hints_given ? 'none — passed ✓' : '—')],
                    ['Outcome', detail.status === 'error' ? '—' : `${detail.factors_added ?? detail.factor_count ?? 0} factors, ${detail.options_added ?? detail.item_count ?? 0} options, ${ms(detail.latency_ms)}`],
                    ['User verdict', detail.feedback ? (detail.feedback === 'up' ? '👍 accurate' : '👎 inaccurate') : '(not given)'],
                    ...(detail.user_reported_failure
                      ? [['🚨 User-reported failure', 'Train AI feedback received — prioritised by Auto-Tune.']]
                      : []),
                  ].map(([k, v]: any) => (
                    <View key={k} style={st.dRow}>
                      <Text style={st.dKey}>{k}</Text>
                      <Text style={st.dVal} selectable>{String(v)}</Text>
                    </View>
                  ))}
                  {detail.user_training && (
                    <View style={[st.callBox, { borderColor: '#FCD34D', backgroundColor: '#FFFBEB' }]} testID="import-run-user-training">
                      <Text style={[st.callStage, { color: '#92400E' }]}>🎓 User Train AI feedback</Text>
                      {detail.user_training.missed_factors_count != null && (
                        <Text style={st.dVal}>• Missed factors: <Text style={{ fontWeight: '800' }}>{detail.user_training.missed_factors_count}</Text></Text>
                      )}
                      {detail.user_training.missed_options_count != null && (
                        <Text style={st.dVal}>• Missed options: <Text style={{ fontWeight: '800' }}>{detail.user_training.missed_options_count}</Text></Text>
                      )}
                      {(detail.user_training.wrong_factors || []).length > 0 && (
                        <Text style={st.dVal}>• Wrong factors: {detail.user_training.wrong_factors.join(', ')}</Text>
                      )}
                      {(detail.user_training.wrong_options || []).length > 0 && (
                        <Text style={st.dVal}>• Wrong options: {detail.user_training.wrong_options.join(', ')}</Text>
                      )}
                      {(detail.user_training.cell_corrections || []).length > 0 && (
                        <>
                          <Text style={[st.dVal, { marginTop: 4, fontWeight: '700' }]}>• Cell-level corrections ({detail.user_training.cell_corrections.length}):</Text>
                          {detail.user_training.cell_corrections.slice(0, 25).map((c: any, i: number) => (
                            <Text key={i} style={[st.dVal, { paddingLeft: 12, fontSize: 11.5 }]} selectable>
                              {c.issue === 'wrong' ? '✗ WRONG' : '? MISSING'}: {c.option_name || c.option_id} → {c.factor_name || c.factor_id}
                              {c.was ? ` (was: "${c.was}")` : ''}
                              {c.should_be ? ` → should be: "${c.should_be}"` : ''}
                            </Text>
                          ))}
                        </>
                      )}
                      {detail.user_training.notes && (
                        <Text style={[st.dVal, { marginTop: 4, fontStyle: 'italic' }]}>📝 {detail.user_training.notes}</Text>
                      )}
                    </View>
                  )}
                  {!!(detail.ai_calls || []).length && (
                    <>
                      <Text style={st.promptTitle}>
                        AI call trace — {detail.ai_calls.length} call{detail.ai_calls.length > 1 ? 's' : ''} (engine · tokens · credits · latency)
                      </Text>
                      {detail.ai_calls.map((c: any, i: number) => (
                        <View key={i} style={st.callBox} testID={`import-run-ai-call-${i}`}>
                          <TouchableOpacity
                            style={st.callHead}
                            testID={`import-run-ai-call-toggle-${i}`}
                            onPress={() => setExpandedCall(expandedCall === i ? null : i)}
                          >
                            <View style={{ flex: 1 }}>
                              <Text style={st.callStage}>#{i + 1} {c.stage}</Text>
                              <Text style={st.callMeta}>
                                {c.engine || '—'} · ~{c.tokens || 0} tok · {(c.credits ?? 0).toFixed(2)} cr · {ms(c.latency_ms)}
                              </Text>
                            </View>
                            <Ionicons name={expandedCall === i ? 'chevron-up' : 'chevron-down'} size={15} color={C.muted} />
                          </TouchableOpacity>
                          {expandedCall === i && (
                            <>
                              <Text style={st.subHead}>System prompt (engineered)</Text>
                              <Text style={st.promptBody} selectable>{c.system_prompt || '(purged — 90-day retention)'}</Text>
                              <Text style={st.subHead}>Input prompt</Text>
                              <Text style={st.promptBody} selectable>{c.prompt_text || '(purged — 90-day retention)'}</Text>
                              <Text style={st.subHead}>Raw response</Text>
                              <Text style={st.promptBody} selectable>{c.raw_response || '(purged — 90-day retention)'}</Text>
                            </>
                          )}
                        </View>
                      ))}
                    </>
                  )}
                  {detail.ai_system_prompt ? (
                    <>
                      <Text style={st.promptTitle}>System prompt (exact, truncated 15KB)</Text>
                      <Text style={st.promptBody} selectable testID="import-run-system-prompt">{detail.ai_system_prompt}</Text>
                      <Text style={st.promptTitle}>Raw LLM response</Text>
                      <Text style={st.promptBody} selectable testID="import-run-raw-response">{detail.ai_raw_response || '(empty)'}</Text>
                    </>
                  ) : !(detail.ai_calls || []).length ? (
                    <Text style={st.empty}>{detail.bodies_purged ? 'Prompt bodies purged (90-day retention).' : 'No AI call was made for this run (deterministic parse).'}</Text>
                  ) : null}
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
  // AI call trace
  callBox: { borderWidth: 1, borderColor: C.border, borderRadius: 10, padding: 10, marginBottom: 8, backgroundColor: '#FCFCFD' },
  callHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  callStage: { fontSize: 12.5, fontWeight: '800', color: C.text },
  callMeta: { fontSize: 11, color: C.muted, marginTop: 2 },
  // Engine tiering
  engRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 9, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  engStage: { fontSize: 13, fontWeight: '800', color: C.text },
  engReco: { fontSize: 11, color: '#B45309', fontWeight: '700', marginTop: 3 },
  engChip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 12, borderWidth: 1, borderColor: C.border },
  engChipOn: { backgroundColor: C.primary, borderColor: C.primary },
  engChipTxt: { fontSize: 11, fontWeight: '700', color: C.muted },
  engChipTxtOn: { color: '#FFF' },
  // AI Auto-Tune
  genBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: C.primary, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 10 },
  genBtnTxt: { color: '#FFF', fontSize: 12, fontWeight: '700' },
  subHead: { fontSize: 11, fontWeight: '800', color: C.muted, marginTop: 8, marginBottom: 4, textTransform: 'uppercase' as any, letterSpacing: 0.4 },
  ovChip: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#ECFDF5', borderColor: '#A7F3D0', borderWidth: 1, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 5 },
  ovChipTxt: { fontSize: 11.5, fontWeight: '700', color: '#065F46' },
  ovRevert: { fontSize: 11, color: C.red, fontWeight: '700', textDecorationLine: 'underline' as any },
  sugBox: { borderWidth: 1, borderColor: C.border, borderRadius: 10, padding: 11, marginBottom: 10, backgroundColor: '#FCFCFD' },
  sugStatus: { fontSize: 10.5, fontWeight: '900', letterSpacing: 0.5 },
  sugPt: { fontSize: 13, fontWeight: '800', color: C.text, flex: 1 },
  sugRationale: { fontSize: 12, color: C.text, marginTop: 5, lineHeight: 17 },
  approveBtn: { backgroundColor: C.green, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 9 },
  approveTxt: { color: '#FFF', fontSize: 12, fontWeight: '800' },
  rejectBtn: { backgroundColor: '#FEF2F2', borderWidth: 1, borderColor: '#FECACA', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 9 },
  rejectTxt: { color: C.red, fontSize: 12, fontWeight: '800' },
  qfInput: { borderWidth: 1, borderColor: C.border, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6, width: 70, fontSize: 13, color: C.text, backgroundColor: '#FFF' },
});
