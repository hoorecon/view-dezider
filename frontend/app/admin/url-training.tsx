/**
 * Admin URL Training Console
 *
 * - Curate a library of ground-truth URL imports (URL, expected #factors,
 *   #options, factor names, option names, optional cell values, notes).
 * - Pin up to 15 as the WEEKLY REGRESSION SUITE (runs Sun 03:00 UTC + on
 *   demand).
 * - Run any single example on demand and see the pass/partial/fail grade.
 * - Each run is captured as its own row in the runs log (no aggregation —
 *   admin can see each invocation separately).
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Modal, useWindowDimensions, Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { api } from '../../src/utils/api';

const C = {
  bg: '#F8FAFC', card: '#FFFFFF', border: '#E2E8F0',
  text: '#0F172A', sub: '#475569', muted: '#94A3B8',
  primary: '#2563EB', primaryBg: '#EFF6FF', primaryBorder: '#BFDBFE',
  green: '#059669', greenBg: '#ECFDF5', greenBorder: '#A7F3D0',
  amber: '#D97706', amberBg: '#FFFBEB', amberBorder: '#FCD34D',
  red: '#DC2626', redBg: '#FEF2F2', redBorder: '#FECACA',
};

type Example = {
  id: string;
  url: string;
  label?: string;
  context?: string;
  expected_factor_count?: number;
  expected_option_count?: number;
  expected_factors?: string[];
  expected_options?: string[];
  expected_cells?: { option: string; factor: string; value?: string }[];
  notes?: string;
  is_regression_pinned?: boolean;
  last_run_id?: string;
  last_run_status?: string;
  last_run_score?: number;
  last_run_at?: string;
};

type Run = {
  id: string; url: string; label?: string; trigger: string;
  status: string; score: number;
  expected_factor_count?: number; expected_option_count?: number;
  ran_factor_count?: number; ran_option_count?: number;
  missed_factors?: number; missed_options?: number;
  started_at?: string; completed_at?: string; elapsed_ms?: number;
  error?: string; example_id?: string; import_run_id?: string;
};

const showAlert = (title: string, msg: string) => {
  if (typeof window !== 'undefined' && (window as any).alert) {
    (window as any).alert(`${title}\n\n${msg}`);
  } else {
    Alert.alert(title, msg);
  }
};

const fmtDate = (iso?: string) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
};

const statusColor = (s?: string) =>
  s === 'pass' ? C.green :
    s === 'partial' ? C.amber :
      s === 'fail' || s === 'error' ? C.red : C.muted;

export default function UrlTrainingConsole() {
  const { width } = useWindowDimensions();
  const isWide = width >= 1024;

  const [items, setItems] = useState<Example[]>([]);
  const [pinned, setPinned] = useState(0);
  const [pinLimit, setPinLimit] = useState(15);
  const [loading, setLoading] = useState(true);
  const [runs, setRuns] = useState<Run[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);   // running example id or 'suite'
  const [editor, setEditor] = useState<Partial<Example> | null>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get('/admin/url-training/examples');
      setItems(r.data.items || []);
      setPinned(r.data.pinned_count || 0);
      setPinLimit(r.data.pin_limit || 15);
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to load training examples');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadRuns = useCallback(async () => {
    setRunsLoading(true);
    try {
      const r = await api.get('/admin/url-training/runs?limit=100');
      setRuns(r.data.items || []);
    } catch { /* non-fatal */ } finally {
      setRunsLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); loadRuns(); }, [loadAll, loadRuns]);

  const runOne = async (ex: Example) => {
    setBusy(ex.id);
    try {
      const r = await api.post(`/admin/url-training/examples/${ex.id}/run`);
      showAlert('Run complete',
        `Status: ${r.data.status.toUpperCase()} · Score: ${r.data.score}/100\n` +
        `Got ${r.data.ran_factor_count}F / ${r.data.ran_option_count}O ` +
        `(expected ${r.data.expected_factor_count ?? '—'}F / ${r.data.expected_option_count ?? '—'}O)`);
      await loadAll();
      await loadRuns();
    } catch (e: any) {
      showAlert('Run failed', e?.response?.data?.detail || 'Unknown error');
    } finally {
      setBusy(null);
    }
  };

  const runSuite = async () => {
    setBusy('suite');
    try {
      const r = await api.post('/admin/url-training/run-suite');
      const pass = r.data.items.filter((x: any) => x.status === 'pass').length;
      const partial = r.data.items.filter((x: any) => x.status === 'partial').length;
      const fail = r.data.items.length - pass - partial;
      showAlert('Regression suite complete',
        `${r.data.ran} example(s) ran:\n• ${pass} pass\n• ${partial} partial\n• ${fail} fail/error`);
      await loadAll();
      await loadRuns();
    } catch (e: any) {
      showAlert('Suite run failed', e?.response?.data?.detail || 'Unknown error');
    } finally {
      setBusy(null);
    }
  };

  const remove = async (ex: Example) => {
    const ok = typeof window !== 'undefined'
      ? (window as any).confirm(`Delete "${ex.label || ex.url}"?`)
      : true;
    if (!ok) return;
    try {
      await api.delete(`/admin/url-training/examples/${ex.id}`);
      await loadAll();
    } catch (e: any) {
      showAlert('Delete failed', e?.response?.data?.detail || 'Unknown error');
    }
  };

  const togglePin = async (ex: Example) => {
    try {
      await api.put(`/admin/url-training/examples/${ex.id}`, {
        ...ex,
        is_regression_pinned: !ex.is_regression_pinned,
      });
      await loadAll();
    } catch (e: any) {
      showAlert('Pin change failed', e?.response?.data?.detail || 'Pin limit reached?');
    }
  };

  const totals = useMemo(() => ({
    total: items.length,
    pinned: pinned,
    last_pass: items.filter(i => i.last_run_status === 'pass').length,
    last_partial: items.filter(i => i.last_run_status === 'partial').length,
    last_fail: items.filter(i => i.last_run_status === 'fail' || i.last_run_status === 'error').length,
  }), [items, pinned]);

  return (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 14 }}>
        {/* Header */}
        <View style={st.card}>
          <Text style={st.title}>URL Training Console</Text>
          <Text style={st.hint}>
            Curate ground-truth examples (URL → expected factors / options / cell values). Pin up to
            <Text style={{ fontWeight: '800' }}> {pinLimit} </Text>
            as the weekly regression suite — runs Sun 03:00 UTC, or trigger now from the button below.
            Every run is captured as its own row in &quot;Run history&quot; for diff-over-time analysis.
          </Text>
          <View style={st.kpis}>
            <Kpi label="Examples" value={String(totals.total)} color={C.text} />
            <Kpi label={`Pinned (${pinLimit} max)`} value={String(totals.pinned)} color={C.primary} />
            <Kpi label="Last: pass" value={String(totals.last_pass)} color={C.green} />
            <Kpi label="Last: partial" value={String(totals.last_partial)} color={C.amber} />
            <Kpi label="Last: fail" value={String(totals.last_fail)} color={C.red} />
          </View>
          <View style={{ flexDirection: 'row', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
            <TouchableOpacity
              testID="url-training-add"
              onPress={() => setEditor({})}
              style={[st.btn, { backgroundColor: C.primaryBg, borderColor: C.primaryBorder }]}>
              <Ionicons name="add-circle" size={14} color={C.primary} />
              <Text style={[st.btnTxt, { color: C.primary }]}>Add example</Text>
            </TouchableOpacity>
            <TouchableOpacity
              testID="url-training-run-suite"
              disabled={busy === 'suite' || totals.pinned === 0}
              onPress={runSuite}
              style={[st.btn, { backgroundColor: C.amberBg, borderColor: C.amberBorder },
                (busy === 'suite' || totals.pinned === 0) && { opacity: 0.5 }]}>
              {busy === 'suite' ? (
                <ActivityIndicator color={C.amber} size="small" />
              ) : (
                <Ionicons name="rocket" size={14} color={C.amber} />
              )}
              <Text style={[st.btnTxt, { color: C.amber }]}>
                {busy === 'suite' ? 'Running suite…' : `Run regression suite (${totals.pinned})`}
              </Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Library */}
        <View style={st.card}>
          <Text style={st.cardTitle}>Library</Text>
          {loading ? (
            <ActivityIndicator color={C.primary} />
          ) : items.length === 0 ? (
            <Text style={st.empty}>No examples yet — tap &quot;Add example&quot; to start.</Text>
          ) : items.map(ex => (
            <View key={ex.id} style={st.row} testID={`ex-${ex.id}`}>
              <View style={{ flex: 1, minWidth: 220 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <Text style={st.rowLabel} numberOfLines={2}>{ex.label || ex.url}</Text>
                  {ex.is_regression_pinned && (
                    <View style={st.pin}>
                      <Ionicons name="pin" size={11} color={C.amber} />
                      <Text style={st.pinTxt}>REGRESSION</Text>
                    </View>
                  )}
                </View>
                <Text style={st.rowUrl} numberOfLines={1}>{ex.url}</Text>
                <Text style={st.rowMeta}>
                  Expected: {ex.expected_factor_count ?? '—'}F · {ex.expected_option_count ?? '—'}O
                  {ex.last_run_status ? (
                    <Text>
                      {'  · last: '}<Text style={{ color: statusColor(ex.last_run_status), fontWeight: '800' }}>
                        {String(ex.last_run_status).toUpperCase()}
                      </Text>{ex.last_run_score != null ? ` (${ex.last_run_score}/100)` : ''}
                      {ex.last_run_at ? ` · ${fmtDate(ex.last_run_at)}` : ''}
                    </Text>
                  ) : <Text style={{ color: C.muted }}>{'  · never run'}</Text>}
                </Text>
              </View>
              <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>
                <TouchableOpacity
                  testID={`ex-${ex.id}-run`}
                  disabled={busy === ex.id}
                  onPress={() => runOne(ex)}
                  style={[st.iconBtn, busy === ex.id && { opacity: 0.5 }]}>
                  {busy === ex.id ? <ActivityIndicator color={C.primary} size="small" /> : <Ionicons name="play" size={14} color={C.primary} />}
                  <Text style={[st.iconBtnTxt, { color: C.primary }]}>{busy === ex.id ? '…' : 'Run'}</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  testID={`ex-${ex.id}-pin`}
                  onPress={() => togglePin(ex)}
                  style={st.iconBtn}>
                  <Ionicons name={ex.is_regression_pinned ? 'pin' : 'pin-outline'} size={14} color={C.amber} />
                  <Text style={[st.iconBtnTxt, { color: C.amber }]}>{ex.is_regression_pinned ? 'Unpin' : 'Pin'}</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  testID={`ex-${ex.id}-edit`}
                  onPress={() => setEditor(ex)}
                  style={st.iconBtn}>
                  <Ionicons name="create" size={14} color={C.sub} />
                  <Text style={[st.iconBtnTxt, { color: C.sub }]}>Edit</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  testID={`ex-${ex.id}-delete`}
                  onPress={() => remove(ex)}
                  style={st.iconBtn}>
                  <Ionicons name="trash" size={14} color={C.red} />
                  <Text style={[st.iconBtnTxt, { color: C.red }]}>Delete</Text>
                </TouchableOpacity>
              </View>
            </View>
          ))}
        </View>

        {/* Run history */}
        <View style={st.card}>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
            <Text style={st.cardTitle}>Run history (each run captured separately)</Text>
            <TouchableOpacity onPress={loadRuns} style={st.iconBtn}>
              <Ionicons name="refresh" size={13} color={C.sub} />
              <Text style={[st.iconBtnTxt, { color: C.sub }]}>Refresh</Text>
            </TouchableOpacity>
          </View>
          {runsLoading ? (
            <ActivityIndicator color={C.primary} />
          ) : runs.length === 0 ? (
            <Text style={st.empty}>No runs yet. Hit &quot;Run regression suite&quot; or a per-example &quot;Run&quot; button.</Text>
          ) : runs.map(r => (
            <View key={r.id} style={st.runRow} testID={`run-${r.id}`}>
              <View style={{ flex: 1 }}>
                <Text style={st.runLabel} numberOfLines={2}>{r.label || r.url}</Text>
                <Text style={st.rowUrl} numberOfLines={1}>
                  {r.trigger.toUpperCase()} · {fmtDate(r.started_at)} · {r.elapsed_ms ? `${(r.elapsed_ms / 1000).toFixed(1)}s` : '—'}
                </Text>
                <Text style={st.rowMeta}>
                  Got {r.ran_factor_count ?? '—'}F / {r.ran_option_count ?? '—'}O
                  · expected {r.expected_factor_count ?? '—'}F / {r.expected_option_count ?? '—'}O
                  {(r.missed_factors ?? 0) > 0 ? ` · missed ${r.missed_factors}F` : ''}
                  {(r.missed_options ?? 0) > 0 ? ` · missed ${r.missed_options}O` : ''}
                  {r.error ? `\n${r.error}` : ''}
                </Text>
              </View>
              <View style={{ alignItems: 'flex-end' }}>
                <Text style={[st.runBadge, { color: statusColor(r.status) }]}>
                  {String(r.status || '').toUpperCase()}
                </Text>
                <Text style={st.rowMeta}>{r.score ?? 0}/100</Text>
              </View>
            </View>
          ))}
        </View>
      </ScrollView>

      {/* Edit / Add modal */}
      <Modal
        visible={!!editor} transparent animationType="fade"
        onRequestClose={() => setEditor(null)}>
        <View style={st.mOverlay}>
          <View style={[st.mBox, { maxWidth: isWide ? 720 : '94%' }]}>
            <View style={st.mHead}>
              <Text style={st.mTitle}>{editor?.id ? 'Edit example' : 'Add example'}</Text>
              <TouchableOpacity onPress={() => setEditor(null)}>
                <Ionicons name="close" size={20} color={C.muted} />
              </TouchableOpacity>
            </View>
            {editor && (
              <ExampleForm
                value={editor as Example}
                onCancel={() => setEditor(null)}
                onSave={async (payload) => {
                  try {
                    if (editor.id) {
                      await api.put(`/admin/url-training/examples/${editor.id}`, payload);
                    } else {
                      await api.post('/admin/url-training/examples', payload);
                    }
                    setEditor(null);
                    await loadAll();
                  } catch (e: any) {
                    showAlert('Save failed', e?.response?.data?.detail || 'Unknown error');
                  }
                }}
                pinnedCount={pinned} pinLimit={pinLimit}
              />
            )}
          </View>
        </View>
      </Modal>
    </View>
  );
}

function Kpi({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <View style={st.kpi}>
      <Text style={[st.kpiVal, { color }]}>{value}</Text>
      <Text style={st.kpiLbl}>{label}</Text>
    </View>
  );
}

function ExampleForm({
  value, pinnedCount, pinLimit, onSave, onCancel,
}: {
  value: Example;
  pinnedCount: number; pinLimit: number;
  onSave: (payload: Partial<Example>) => Promise<void>;
  onCancel: () => void;
}) {
  const [url, setUrl] = useState(value.url || '');
  const [label, setLabel] = useState(value.label || '');
  const [context, setContext] = useState(value.context || '');
  const [efCount, setEfCount] = useState(value.expected_factor_count != null ? String(value.expected_factor_count) : '');
  const [eoCount, setEoCount] = useState(value.expected_option_count != null ? String(value.expected_option_count) : '');
  const [ef, setEf] = useState((value.expected_factors || []).join(', '));
  const [eo, setEo] = useState((value.expected_options || []).join(', '));
  const [notes, setNotes] = useState(value.notes || '');
  const [pinned, setPinned] = useState(Boolean(value.is_regression_pinned));
  const [saving, setSaving] = useState(false);

  const canPinMore = pinned || pinnedCount < pinLimit;

  const save = async () => {
    if (!url.trim()) {
      showAlert('URL required', 'Enter the URL to import for training.');
      return;
    }
    setSaving(true);
    try {
      await onSave({
        url: url.trim(),
        label: label.trim() || undefined,
        context: context.trim() || undefined,
        expected_factor_count: efCount ? parseInt(efCount, 10) : undefined,
        expected_option_count: eoCount ? parseInt(eoCount, 10) : undefined,
        expected_factors: ef.split(',').map(s => s.trim()).filter(Boolean),
        expected_options: eo.split(',').map(s => s.trim()).filter(Boolean),
        notes: notes.trim() || undefined,
        is_regression_pinned: pinned,
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <ScrollView style={{ maxHeight: 560 }}>
      <FormField label="URL" required>
        <TextInput testID="form-url" value={url} onChangeText={setUrl}
          placeholder="https://example.com/listing" style={st.input} />
      </FormField>
      <FormField label="Label (short name)">
        <TextInput testID="form-label" value={label} onChangeText={setLabel}
          placeholder="Carwale EVs <10L" style={st.input} />
      </FormField>
      <FormField label="Context (what should this page yield?)">
        <TextInput testID="form-context" value={context} onChangeText={setContext}
          placeholder="Listing/filter page with EV models, brand, range, battery" multiline
          style={[st.input, { minHeight: 50 }]} />
      </FormField>
      <View style={{ flexDirection: 'row', gap: 10, flexWrap: 'wrap' }}>
        <FormField label="Expected #factors" style={{ flex: 1, minWidth: 120 }}>
          <TextInput testID="form-ef-count" value={efCount} onChangeText={setEfCount}
            keyboardType="number-pad" placeholder="6" style={st.input} />
        </FormField>
        <FormField label="Expected #options" style={{ flex: 1, minWidth: 120 }}>
          <TextInput testID="form-eo-count" value={eoCount} onChangeText={setEoCount}
            keyboardType="number-pad" placeholder="8" style={st.input} />
        </FormField>
      </View>
      <FormField label="Expected factor names (comma-separated)">
        <TextInput testID="form-ef" value={ef} onChangeText={setEf}
          placeholder="Price, Model, Range, Battery, Charging time, Top speed" style={st.input} />
      </FormField>
      <FormField label="Expected option names (comma-separated)">
        <TextInput testID="form-eo" value={eo} onChangeText={setEo}
          placeholder="Tata Nexon EV, Mahindra XUV400 EV, MG ZS EV" style={st.input} />
      </FormField>
      <FormField label="Notes (free-form, optional)">
        <TextInput testID="form-notes" value={notes} onChangeText={setNotes}
          multiline style={[st.input, { minHeight: 50 }]} />
      </FormField>

      <TouchableOpacity
        testID="form-pin-toggle"
        onPress={() => { if (canPinMore) setPinned(p => !p); }}
        style={[st.pinChk, pinned && { backgroundColor: C.amberBg, borderColor: C.amberBorder }]}>
        <Ionicons name={pinned ? 'checkbox' : 'square-outline'} size={16}
          color={pinned ? C.amber : C.sub} />
        <Text style={{ fontSize: 12.5, color: pinned ? C.amber : C.sub, fontWeight: '700' }}>
          Pin to regression suite ({pinnedCount}/{pinLimit} used)
        </Text>
      </TouchableOpacity>

      <View style={{ flexDirection: 'row', gap: 8, marginTop: 12, justifyContent: 'flex-end' }}>
        <TouchableOpacity onPress={onCancel} style={[st.btn, { backgroundColor: '#F1F5F9', borderColor: '#CBD5E1' }]}>
          <Text style={[st.btnTxt, { color: C.sub }]}>Cancel</Text>
        </TouchableOpacity>
        <TouchableOpacity testID="form-save" disabled={saving}
          onPress={save}
          style={[st.btn, { backgroundColor: C.primaryBg, borderColor: C.primaryBorder }, saving && { opacity: 0.6 }]}>
          {saving ? <ActivityIndicator color={C.primary} size="small" /> : <Ionicons name="save" size={14} color={C.primary} />}
          <Text style={[st.btnTxt, { color: C.primary }]}>{saving ? 'Saving…' : 'Save'}</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

function FormField({ label, required, children, style }: any) {
  return (
    <View style={[{ marginBottom: 8 }, style]}>
      <Text style={st.fieldLbl}>{label}{required ? ' *' : ''}</Text>
      {children}
    </View>
  );
}

const st = StyleSheet.create({
  card: { backgroundColor: C.card, borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 14, marginBottom: 12 },
  title: { fontSize: 18, fontWeight: '800', color: C.text, marginBottom: 4 },
  cardTitle: { fontSize: 14, fontWeight: '800', color: C.text, marginBottom: 8 },
  hint: { fontSize: 12, color: C.sub, lineHeight: 17, marginBottom: 8 },
  empty: { fontSize: 12, color: C.muted, fontStyle: 'italic', paddingVertical: 8 },

  kpis: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 4 },
  kpi: { backgroundColor: '#F8FAFC', borderWidth: 1, borderColor: C.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8, minWidth: 110 },
  kpiVal: { fontSize: 16, fontWeight: '800' },
  kpiLbl: { fontSize: 11, color: C.sub, marginTop: 2 },

  row: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 8, paddingVertical: 10, borderTopWidth: 1, borderColor: C.border },
  rowLabel: { fontSize: 13, fontWeight: '800', color: C.text },
  rowUrl: { fontSize: 11, color: C.muted, marginTop: 1 },
  rowMeta: { fontSize: 11.5, color: C.sub, marginTop: 2 },

  pin: { flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: C.amberBg, borderWidth: 1, borderColor: C.amberBorder, borderRadius: 999, paddingHorizontal: 6, paddingVertical: 1 },
  pinTxt: { fontSize: 9.5, fontWeight: '800', color: C.amber, letterSpacing: 0.4 },

  btn: { flexDirection: 'row', alignItems: 'center', gap: 5, borderWidth: 1, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 7 },
  btnTxt: { fontSize: 12.5, fontWeight: '800' },
  iconBtn: { flexDirection: 'row', alignItems: 'center', gap: 3, borderWidth: 1, borderColor: C.border, backgroundColor: '#FFF', borderRadius: 8, paddingHorizontal: 8, paddingVertical: 5 },
  iconBtnTxt: { fontSize: 11.5, fontWeight: '700' },

  runRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, paddingVertical: 9, borderTopWidth: 1, borderColor: C.border },
  runLabel: { fontSize: 12.5, fontWeight: '700', color: C.text },
  runBadge: { fontSize: 11.5, fontWeight: '800' },

  mOverlay: { flex: 1, backgroundColor: 'rgba(15, 23, 42, 0.55)', justifyContent: 'center', alignItems: 'center', padding: 18 },
  mBox: { backgroundColor: '#FFF', width: '100%', borderRadius: 14, padding: 16 },
  mHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 },
  mTitle: { fontSize: 15, fontWeight: '800', color: C.text },

  fieldLbl: { fontSize: 11.5, fontWeight: '700', color: C.sub, marginBottom: 4 },
  input: { borderWidth: 1, borderColor: C.border, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 7, fontSize: 13, color: C.text, backgroundColor: '#FFF' },

  pinChk: { flexDirection: 'row', alignItems: 'center', gap: 6, borderWidth: 1, borderColor: C.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 9, marginTop: 4 },
});
