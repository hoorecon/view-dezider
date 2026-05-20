/*
  /admin/regression-tests.tsx
  Feature-mapped API + UI regression test results dashboard. Admin-only.
*/
import React, { useEffect, useState, useCallback } from 'react';
import {
  SafeAreaView, View, Text, ScrollView, TouchableOpacity, StyleSheet,
  ActivityIndicator, Modal, Pressable,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { ADMIN_THEME } from '../../src/constants/adminTheme';
import api from '../../src/utils/api';

const T = ADMIN_THEME;

type CaseMeta = { id: string; name: string; level: 'smoke' | 'functional'; description?: string };
type Suite = {
  id: string; feature: string; module: string; kind: 'api' | 'ui';
  title: string; description: string; owner_file: string;
  case_count: number; smoke_count: number; functional_count: number;
  ui_spec_path?: string; cases: CaseMeta[];
};
type FeatureGroup = { feature: string; suites: Suite[] };
type LatestEntry = {
  run_id: string; triggered_at: string; triggered_by: string;
  status: string; passed: number; failed: number; skipped: number; manual_pending: number;
};

const STATUS_COLOR: Record<string, string> = {
  passed: '#16A34A', failed: '#DC2626', skipped: '#9CA3AF',
  partial: '#F59E0B', running: '#3B82F6', never_run: '#9CA3AF',
};

function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLOR[status] || '#9CA3AF';
  const label = status === 'never_run' ? 'NEVER RUN' : status.toUpperCase();
  return (
    <View style={[s.badge, { backgroundColor: `${color}22`, borderColor: color }]}>
      <View style={[s.dot, { backgroundColor: color }]} />
      <Text style={[s.badgeText, { color }]}>{label}</Text>
    </View>
  );
}

export default function RegressionTestsScreen() {
  const [groups, setGroups] = useState<FeatureGroup[]>([]);
  const [latest, setLatest] = useState<Record<string, LatestEntry>>({});
  const [totals, setTotals] = useState({ suites: 0, cases: 0 });
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState<string | null>(null); // suite_id or "all"
  const [lastResult, setLastResult] = useState<any>(null);
  const [detailSuite, setDetailSuite] = useState<{ suite: Suite; run?: any } | null>(null);
  const [selectedSuites, setSelectedSuites] = useState<Set<string>>(new Set());

  // History panel
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<any[]>([]);
  const [selectedRuns, setSelectedRuns] = useState<Set<string>>(new Set());
  const [historyBusy, setHistoryBusy] = useState(false);

  // Filters
  const [levelFilter, setLevelFilter] = useState<'smoke' | 'functional' | 'both'>('smoke');
  const [kindFilter, setKindFilter] = useState<'api' | 'ui' | 'both'>('api');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/admin/regression/suites');
      setGroups(r.data.features || []);
      setLatest(r.data.latest_per_suite || {});
      setTotals({ suites: r.data.total_suites || 0, cases: r.data.total_cases || 0 });
    } catch (e) {
      console.error('regression load', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const runRegression = useCallback(async (scope: 'all' | 'selected' | string) => {
    let suite_ids: string[] | null = null;
    if (scope === 'selected') suite_ids = Array.from(selectedSuites);
    else if (scope !== 'all') suite_ids = [scope];
    const tag = scope === 'all' ? 'all' : scope === 'selected' ? 'selected' : scope;
    setRunning(tag);
    try {
      const r = await api.post('/admin/regression/run', {
        level: levelFilter,
        kind: kindFilter,
        suite_ids,
      });
      setLastResult(r.data);
      await load();
    } catch (e: any) {
      setLastResult({ error: e?.response?.data?.detail || e?.message });
    } finally {
      setRunning(null);
    }
  }, [levelFilter, kindFilter, selectedSuites, load]);

  const openDetail = async (suite: Suite) => {
    const lr = latest[suite.id];
    let runDoc;
    if (lr?.run_id) {
      try {
        const r = await api.get(`/admin/regression/runs/${lr.run_id}`);
        runDoc = r.data;
      } catch {}
    }
    setDetailSuite({ suite, run: runDoc });
  };

  const toggleSelect = (id: string) => {
    setSelectedSuites((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  // ── History panel handlers ─────────────────────────────────────────────
  const loadHistory = useCallback(async () => {
    setHistoryBusy(true);
    try {
      const r = await api.get('/admin/regression/runs?limit=50');
      setHistory(r.data.runs || []);
    } finally { setHistoryBusy(false); }
  }, []);

  const toggleRun = (id: string) => {
    setSelectedRuns((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  };

  const downloadSingle = (run_id: string) => {
    const base = (process.env.EXPO_PUBLIC_BACKEND_URL || '') + '/api';
    const token = (api.defaults.headers.common as any).Authorization || '';
    // Use fetch with auth, then trigger blob download (works on web)
    fetch(`${base}/admin/regression/runs/${run_id}/download`, { headers: { Authorization: String(token) } })
      .then((res) => res.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = `regression_${run_id}.zip`; a.click();
        URL.revokeObjectURL(url);
      });
  };

  const downloadSelected = async () => {
    if (selectedRuns.size === 0) return;
    setHistoryBusy(true);
    try {
      const base = (process.env.EXPO_PUBLIC_BACKEND_URL || '') + '/api';
      const token = (api.defaults.headers.common as any).Authorization || '';
      const res = await fetch(`${base}/admin/regression/runs/download-bulk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: String(token) },
        body: JSON.stringify({ run_ids: Array.from(selectedRuns) }),
      });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `regression_bulk_${selectedRuns.size}.zip`; a.click();
      URL.revokeObjectURL(url);
    } finally { setHistoryBusy(false); }
  };

  const deleteSelected = async () => {
    if (selectedRuns.size === 0) return;
    if (!confirm(`Delete ${selectedRuns.size} selected run(s)? This cannot be undone.`)) return;
    setHistoryBusy(true);
    try {
      await api.post('/admin/regression/runs/delete-bulk', { run_ids: Array.from(selectedRuns) });
      setSelectedRuns(new Set());
      await loadHistory();
      await load();
    } finally { setHistoryBusy(false); }
  };

  const deleteSingle = async (run_id: string) => {
    if (!confirm(`Delete run ${run_id}?`)) return;
    setHistoryBusy(true);
    try {
      await api.delete(`/admin/regression/runs/${run_id}`);
      await loadHistory();
      await load();
    } finally { setHistoryBusy(false); }
  };

  useEffect(() => { if (showHistory) loadHistory(); }, [showHistory, loadHistory]);

  if (loading) {
    return (
      <SafeAreaView style={s.container}>
        <View style={s.center}><ActivityIndicator size="large" color={T.primary} /></View>
      </SafeAreaView>
    );
  }

  // overall latest banner
  const lastRun = Object.values(latest).reduce<LatestEntry | null>((acc, e) =>
    !acc || (e.triggered_at > acc.triggered_at) ? e : acc, null);

  return (
    <SafeAreaView style={s.container}>
      <ScrollView contentContainerStyle={{ padding: 24 }}>
        {/* Header */}
        <View style={s.header}>
          <Ionicons name="checkmark-done-circle" size={26} color={T.primary} />
          <View style={{ flex: 1, marginLeft: 12 }}>
            <Text style={s.h1}>Legacy Regression Tests</Text>
            <Text style={s.subtitle}>
              {totals.suites} suites · {totals.cases} test cases ·
              {lastRun ? `  last run ${new Date(lastRun.triggered_at).toLocaleString()} (${lastRun.triggered_by})` : '  never run'}
            </Text>
          </View>
        </View>

        {/* Filter chips */}
        <View style={s.filterRow}>
          <Text style={s.filterLabel}>Level</Text>
          {(['smoke', 'functional', 'both'] as const).map((l) => (
            <Chip key={l} active={levelFilter === l} label={l} onPress={() => setLevelFilter(l)} />
          ))}
          <View style={{ width: 16 }} />
          <Text style={s.filterLabel}>Kind</Text>
          {(['api', 'ui', 'both'] as const).map((k) => (
            <Chip key={k} active={kindFilter === k} label={k.toUpperCase()} onPress={() => setKindFilter(k)} />
          ))}
        </View>

        {/* Action bar */}
        <View style={s.actionsRow}>
          <ActionBtn
            label={running === 'all' ? 'Running…' : `Run all (${kindFilter}/${levelFilter})`}
            icon="play-circle" primary onPress={() => runRegression('all')}
            disabled={!!running}
          />
          <ActionBtn
            label={running === 'selected' ? 'Running…' : `Run selected (${selectedSuites.size})`}
            icon="checkmark-done" onPress={() => runRegression('selected')}
            disabled={!!running || selectedSuites.size === 0}
          />
          <ActionBtn label="Refresh" icon="refresh" onPress={load} disabled={!!running} />
          <ActionBtn
            label={showHistory ? 'Hide Run History' : `Run History (download / delete)`}
            icon="archive"
            onPress={() => setShowHistory((v) => !v)}
            disabled={!!running}
          />
        </View>

        {showHistory && (
          <View style={s.historyCard}>
            <View style={s.historyHeader}>
              <Text style={s.historyTitle}>Run History (last 50)</Text>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <ActionBtn
                  label={`Download (${selectedRuns.size})`}
                  icon="cloud-download"
                  onPress={downloadSelected}
                  disabled={selectedRuns.size === 0 || historyBusy}
                />
                <ActionBtn
                  label={`Delete (${selectedRuns.size})`}
                  icon="trash"
                  onPress={deleteSelected}
                  disabled={selectedRuns.size === 0 || historyBusy}
                />
              </View>
            </View>
            {historyBusy && <ActivityIndicator size="small" color={T.primary} style={{ margin: 8 }} />}
            {history.length === 0 && !historyBusy && (
              <Text style={s.historyEmpty}>No runs yet. Click "Run all" above to create the first run.</Text>
            )}
            {history.map((h) => {
              const sel = selectedRuns.has(h.run_id);
              const t = h.totals || {};
              return (
                <View key={h.run_id} style={s.historyRow}>
                  <TouchableOpacity onPress={() => toggleRun(h.run_id)} style={s.checkbox}>
                    <Ionicons name={sel ? 'checkbox' : 'square-outline'} size={20}
                              color={sel ? T.primary : '#9CA3AF'} />
                  </TouchableOpacity>
                  <View style={{ flex: 1 }}>
                    <Text style={s.historyRowTitle}>{h.run_id}</Text>
                    <Text style={s.historyRowMeta}>
                      {new Date(h.triggered_at).toLocaleString()} · by {h.triggered_by}
                      {' · '}{(h.level_filter || 'smoke')}/{(h.kind_filter || 'api')}
                      {' · '}{Math.round((h.duration_ms || 0) / 100) / 10}s
                    </Text>
                    <Text style={s.historyRowStats}>
                      {t.passed || 0}✓ · {t.failed || 0}✗ · {t.skipped || 0}⊘ · {t.manual_pending || 0}⚙
                    </Text>
                  </View>
                  <StatusBadge status={h.overall_status || 'skipped'} />
                  <TouchableOpacity onPress={() => downloadSingle(h.run_id)} style={s.iconBtn}>
                    <Ionicons name="cloud-download-outline" size={18} color={T.primary} />
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => deleteSingle(h.run_id)} style={s.iconBtn}>
                    <Ionicons name="trash-outline" size={18} color="#DC2626" />
                  </TouchableOpacity>
                </View>
              );
            })}
          </View>
        )}

        {lastResult && (
          <View style={[s.banner, { borderLeftColor: lastResult.error ? '#DC2626' : STATUS_COLOR[lastResult.overall_status] || '#16A34A' }]}>
            <Text style={s.bannerTitle}>
              {lastResult.error ? 'Run failed' : `Run ${lastResult.run_id} — ${lastResult.overall_status?.toUpperCase()}`}
            </Text>
            {!lastResult.error && (
              <Text style={s.bannerBody}>
                {lastResult.totals?.passed || 0} passed · {lastResult.totals?.failed || 0} failed ·
                {' '}{lastResult.totals?.skipped || 0} skipped · {lastResult.totals?.manual_pending || 0} manual ·
                {' '}{Math.round((lastResult.duration_ms || 0) / 1000)}s
              </Text>
            )}
            {lastResult.error && <Text style={s.bannerBody}>{lastResult.error}</Text>}
          </View>
        )}

        {/* Feature groups */}
        {groups.map((g) => (
          <View key={g.feature} style={s.featureCard}>
            <View style={s.featureHeader}>
              <Text style={s.featureName}>{g.feature}</Text>
              <Text style={s.featureMeta}>{g.suites.length} suite{g.suites.length === 1 ? '' : 's'}</Text>
            </View>
            {g.suites.map((suite) => {
              const lr = latest[suite.id];
              const status = lr?.status || 'never_run';
              const selected = selectedSuites.has(suite.id);
              return (
                <View key={suite.id} style={s.suiteRow}>
                  <TouchableOpacity onPress={() => toggleSelect(suite.id)} style={s.checkbox}>
                    <Ionicons
                      name={selected ? 'checkbox' : 'square-outline'}
                      size={22} color={selected ? T.primary : '#9CA3AF'}
                    />
                  </TouchableOpacity>
                  <TouchableOpacity style={{ flex: 1 }} onPress={() => openDetail(suite)}>
                    <View style={s.suiteHead}>
                      <Text style={s.suiteTitle}>{suite.title}</Text>
                      <View style={s.kindPill}>
                        <Text style={s.kindPillText}>{suite.kind.toUpperCase()}</Text>
                      </View>
                    </View>
                    <Text style={s.suiteDesc}>{suite.description}</Text>
                    <Text style={s.suiteMeta}>
                      {suite.case_count} cases  ·  smoke {suite.smoke_count}  ·  functional {suite.functional_count}
                      {lr ? `  ·  last: ${lr.passed}✓ ${lr.failed}✗ ${lr.skipped}⊘ ${lr.manual_pending}⚙` : ''}
                    </Text>
                  </TouchableOpacity>
                  <View style={{ alignItems: 'flex-end', gap: 6 }}>
                    <StatusBadge status={status} />
                    <TouchableOpacity
                      onPress={() => runRegression(suite.id)}
                      disabled={!!running}
                      style={[s.runBtn, !!running && { opacity: 0.5 }]}
                    >
                      <Ionicons name="play" size={14} color="#FFF" />
                      <Text style={s.runBtnText}>Run</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              );
            })}
          </View>
        ))}

        <View style={s.footer}>
          <Text style={s.footerText}>
            Weekly auto-run: every Sunday 02:00 UTC. History retention: 7 days.
            New features add suites in <Text style={s.code}>backend/core/regression/seed_suites.py</Text>.
          </Text>
        </View>
      </ScrollView>

      {/* Suite Detail Modal */}
      <Modal visible={!!detailSuite} animationType="slide" transparent onRequestClose={() => setDetailSuite(null)}>
        <Pressable style={s.modalOverlay} onPress={() => setDetailSuite(null)}>
          <Pressable style={s.modalCard} onPress={(e) => e.stopPropagation()}>
            <View style={s.modalHeader}>
              <Text style={s.modalTitle}>{detailSuite?.suite.title}</Text>
              <TouchableOpacity onPress={() => setDetailSuite(null)}>
                <Ionicons name="close" size={24} color="#666" />
              </TouchableOpacity>
            </View>
            <ScrollView contentContainerStyle={{ padding: 20 }}>
              <Text style={s.modalSection}>Description</Text>
              <Text style={s.modalBody}>{detailSuite?.suite.description}</Text>

              {detailSuite?.suite.ui_spec_path && (
                <>
                  <Text style={s.modalSection}>UI Spec</Text>
                  <Text style={s.code}>/{detailSuite.suite.ui_spec_path}</Text>
                </>
              )}

              <Text style={s.modalSection}>Cases</Text>
              {detailSuite?.suite.cases.map((c) => {
                const caseResult = detailSuite.run?.suites
                  ?.find((sr: any) => sr.suite_id === detailSuite.suite.id)
                  ?.cases?.find((cr: any) => cr.case_id === c.id);
                return (
                  <View key={c.id} style={s.caseRow}>
                    <View style={{ flex: 1 }}>
                      <Text style={s.caseName}>{c.name}</Text>
                      <Text style={s.caseMeta}>level: {c.level}{caseResult ? ` · ${caseResult.latency_ms}ms` : ''}</Text>
                      {caseResult?.message && (
                        <Text style={s.caseMsg}>{caseResult.message}</Text>
                      )}
                      {caseResult?.traceback && (
                        <Text style={s.caseTrace} numberOfLines={6}>{caseResult.traceback}</Text>
                      )}
                    </View>
                    <StatusBadge status={caseResult?.status || 'never_run'} />
                  </View>
                );
              })}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </SafeAreaView>
  );
}

function Chip({ active, label, onPress }: { active: boolean; label: string; onPress: () => void }) {
  return (
    <TouchableOpacity onPress={onPress} style={[s.chip, active && s.chipActive]}>
      <Text style={[s.chipText, active && s.chipTextActive]}>{label}</Text>
    </TouchableOpacity>
  );
}

function ActionBtn({ label, icon, onPress, primary, disabled }:
  { label: string; icon: any; onPress: () => void; primary?: boolean; disabled?: boolean }) {
  return (
    <TouchableOpacity
      onPress={onPress} disabled={disabled}
      style={[s.actionBtn, primary && s.actionBtnPrimary, disabled && { opacity: 0.5 }]}
    >
      <Ionicons name={icon} size={16} color={primary ? '#FFF' : T.primary} />
      <Text style={[s.actionBtnText, primary && { color: '#FFF' }]}>{label}</Text>
    </TouchableOpacity>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: T.content.bg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 40 },
  header: { flexDirection: 'row', alignItems: 'center', marginBottom: 20 },
  h1: { fontSize: 22, fontWeight: '800', color: '#111' },
  subtitle: { fontSize: 12, color: '#6B7280', marginTop: 2 },

  filterRow: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 12 },
  filterLabel: { fontSize: 12, color: '#6B7280', fontWeight: '700', marginRight: 4 },

  chip: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16, backgroundColor: '#F3F4F6', borderWidth: 1, borderColor: '#E5E7EB' },
  chipActive: { backgroundColor: T.primary, borderColor: T.primary },
  chipText: { fontSize: 12, fontWeight: '700', color: '#374151' },
  chipTextActive: { color: '#FFF' },

  actionsRow: { flexDirection: 'row', gap: 10, marginBottom: 12, flexWrap: 'wrap' },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: T.primary, backgroundColor: '#FFF' },
  actionBtnPrimary: { backgroundColor: T.primary },
  actionBtnText: { fontSize: 13, fontWeight: '700', color: T.primary },

  banner: { backgroundColor: '#FFF', borderLeftWidth: 4, padding: 12, borderRadius: 6, marginBottom: 12 },
  bannerTitle: { fontSize: 13, fontWeight: '800', color: '#111' },
  bannerBody: { fontSize: 12, color: '#374151', marginTop: 2 },

  featureCard: { backgroundColor: '#FFF', borderRadius: 10, marginBottom: 12, borderWidth: 1, borderColor: '#E5E7EB', overflow: 'hidden' },
  featureHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 10, backgroundColor: '#F9FAFB', borderBottomWidth: 1, borderBottomColor: '#E5E7EB' },
  featureName: { fontSize: 14, fontWeight: '800', color: '#111', letterSpacing: 0.3 },
  featureMeta: { fontSize: 12, color: '#6B7280' },

  suiteRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, paddingHorizontal: 16, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#F3F4F6' },
  checkbox: { paddingTop: 2 },
  suiteHead: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  suiteTitle: { fontSize: 14, fontWeight: '700', color: '#111' },
  kindPill: { backgroundColor: '#EEF2FF', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  kindPillText: { fontSize: 10, fontWeight: '800', color: T.primary },
  suiteDesc: { fontSize: 12, color: '#4B5563', marginTop: 4 },
  suiteMeta: { fontSize: 11, color: '#9CA3AF', marginTop: 4 },

  runBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: T.primary, paddingHorizontal: 10, paddingVertical: 5, borderRadius: 5 },
  runBtnText: { color: '#FFF', fontSize: 11, fontWeight: '700' },

  badge: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 12, borderWidth: 1 },
  dot: { width: 6, height: 6, borderRadius: 3 },
  badgeText: { fontSize: 10, fontWeight: '800' },

  footer: { marginTop: 20, paddingTop: 14, borderTopWidth: 1, borderTopColor: '#E5E7EB' },
  footerText: { fontSize: 12, color: '#6B7280', lineHeight: 18 },
  code: { fontFamily: 'monospace', fontSize: 11, backgroundColor: '#F3F4F6', paddingHorizontal: 4, borderRadius: 3 },

  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  modalCard: { width: '100%', maxWidth: 720, maxHeight: '90%', backgroundColor: '#FFF', borderRadius: 12, overflow: 'hidden' },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 20, paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: '#E5E7EB' },
  modalTitle: { fontSize: 16, fontWeight: '800', color: '#111', flex: 1 },
  modalSection: { fontSize: 11, fontWeight: '800', color: '#6B7280', letterSpacing: 0.5, marginTop: 14, marginBottom: 6 },
  modalBody: { fontSize: 13, color: '#374151', lineHeight: 20 },

  caseRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, padding: 12, borderBottomWidth: 1, borderBottomColor: '#F3F4F6' },
  caseName: { fontSize: 13, fontWeight: '700', color: '#111' },
  caseMeta: { fontSize: 11, color: '#9CA3AF', marginTop: 2 },
  caseMsg: { fontSize: 12, color: '#374151', marginTop: 6 },
  caseTrace: { fontSize: 11, color: '#DC2626', marginTop: 6, fontFamily: 'monospace' },

  historyCard: { backgroundColor: '#FFF', borderRadius: 10, borderWidth: 1, borderColor: '#E5E7EB', marginBottom: 12, overflow: 'hidden' },
  historyHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 10, backgroundColor: '#F9FAFB', borderBottomWidth: 1, borderBottomColor: '#E5E7EB' },
  historyTitle: { fontSize: 14, fontWeight: '800', color: '#111' },
  historyEmpty: { fontSize: 13, color: '#6B7280', padding: 20, textAlign: 'center' },
  historyRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: '#F3F4F6' },
  historyRowTitle: { fontSize: 12, fontWeight: '700', color: '#111', fontFamily: 'monospace' },
  historyRowMeta: { fontSize: 11, color: '#6B7280', marginTop: 2 },
  historyRowStats: { fontSize: 11, color: '#374151', marginTop: 2 },
  iconBtn: { padding: 6 },
});
