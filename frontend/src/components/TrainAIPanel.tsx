/**
 * TrainAIPanel — User-facing "Train AI" feedback panel.
 *
 * Shows after a URL import 👎. Lets the user pinpoint exactly what went wrong:
 *  • Step 2  — missed factor count + which extracted factors are wrong/irrelevant
 *  • Step 6  — missed option count + which extracted options are wrong/irrelevant
 *  • Step 7  — option × factor cell grid: tap any cell to flag "wrong value"
 *              or "missing value" and (optionally) type the correct value.
 *
 * Submissions are POSTed to `/url-analyze/runs/{run_id}/training` and persisted
 * on the run document, where Admin Intel surfaces them and Auto-Tune treats
 * the run as a high-priority failing candidate (even when status=success).
 *
 * Designed inline-collapsible (not a modal) so the user can keep referencing
 * the on-screen factors/options while flagging issues.
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView, ActivityIndicator,
  StyleSheet, Platform,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../utils/api';

const C = {
  panel: '#FFFBF1', border: '#FACC15',
  text: '#0F172A', sub: '#475569', muted: '#94A3B8',
  bad: '#DC2626', badBg: '#FEF2F2', badBorder: '#FECACA',
  warn: '#F59E0B', warnBg: '#FFF7E5', warnBorder: '#FCD34D',
  ok: '#059669', okBg: '#ECFDF5', okBorder: '#A7F3D0',
  chipBg: '#F1F5F9', chipBorder: '#CBD5E1',
  chipOn: '#FEE2E2', chipOnBorder: '#FCA5A5', chipOnText: '#B91C1C',
  primary: '#2563EB', primaryBg: '#EFF6FF', primaryBorder: '#BFDBFE',
  cellOk: '#FFFFFF', cellWrong: '#FEE2E2', cellMissing: '#FEF3C7',
};

type Factor = { id?: string; name?: string; display_name?: string };
type Assessment = { factor_id?: string; unit_value?: any; assessment_pct?: number };
type Option = { id?: string; name?: string; assessments?: Assessment[] };

type CellMark = { issue: 'wrong' | 'missing'; should_be?: string };
type CellKey = string; // `${option_id}|${factor_id}`

export type TrainAIPanelProps = {
  runId: string;
  decisionId?: string;
  factors: Factor[];          // current factor list (leaf nodes only is fine)
  options: Option[];          // current option list with their assessments
  onSaved?: () => void;
  onClose?: () => void;
};

const labelOf = (f: { name?: string; display_name?: string }) =>
  f.display_name?.trim() || f.name?.trim() || 'unnamed';

const cellValue = (opt: Option, fid?: string) => {
  if (!fid) return '';
  const a = (opt.assessments || []).find(x => x.factor_id === fid);
  const v = a?.unit_value;
  if (v == null || v === '') return '';
  return String(v);
};

const cellKey = (oid?: string, fid?: string): CellKey =>
  `${oid || ''}|${fid || ''}`;

export default function TrainAIPanel({
  runId, decisionId, factors, options, onSaved, onClose,
}: TrainAIPanelProps) {
  // ── form state ──
  const [missedFactors, setMissedFactors] = useState('');
  const [missedOptions, setMissedOptions] = useState('');
  const [wrongFactorIds, setWrongFactorIds] = useState<Set<string>>(new Set());
  const [wrongOptionIds, setWrongOptionIds] = useState<Set<string>>(new Set());
  const [cells, setCells] = useState<Record<CellKey, CellMark>>({});
  const [activeCell, setActiveCell] = useState<CellKey | null>(null);
  const [activeShouldBe, setActiveShouldBe] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  // Restore previous training feedback (if any) on mount
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { data } = await api.get(`/url-analyze/runs/${runId}/training`);
        if (!alive || !data?.user_training) return;
        const t = data.user_training;
        if (t.missed_factors_count != null) setMissedFactors(String(t.missed_factors_count));
        if (t.missed_options_count != null) setMissedOptions(String(t.missed_options_count));
        if (Array.isArray(t.wrong_factors)) setWrongFactorIds(new Set(t.wrong_factors));
        if (Array.isArray(t.wrong_options)) setWrongOptionIds(new Set(t.wrong_options));
        if (Array.isArray(t.cell_corrections)) {
          const m: Record<CellKey, CellMark> = {};
          for (const c of t.cell_corrections) {
            m[cellKey(c.option_id, c.factor_id)] = {
              issue: (c.issue === 'wrong' || c.issue === 'missing') ? c.issue : 'wrong',
              should_be: c.should_be,
            };
          }
          setCells(m);
        }
        if (t.notes) setNotes(t.notes);
        if (data.user_reported_failure) setSavedAt(Date.now());
      } catch { /* first time — nothing to restore */ }
    })();
    return () => { alive = false; };
  }, [runId]);

  const toggle = (set: Set<string>, key: string,
                  apply: (s: Set<string>) => void) => {
    const next = new Set(set);
    if (next.has(key)) next.delete(key); else next.add(key);
    apply(next);
  };

  const openCell = (oid?: string, fid?: string) => {
    const k = cellKey(oid, fid);
    setActiveCell(k);
    setActiveShouldBe(cells[k]?.should_be || '');
  };

  const applyCellMark = (issue: 'wrong' | 'missing') => {
    if (!activeCell) return;
    setCells(prev => ({
      ...prev, [activeCell]: { issue, should_be: activeShouldBe.trim() || undefined },
    }));
    setActiveCell(null);
    setActiveShouldBe('');
  };

  const clearCell = () => {
    if (!activeCell) return;
    setCells(prev => {
      const next = { ...prev };
      delete next[activeCell];
      return next;
    });
    setActiveCell(null);
    setActiveShouldBe('');
  };

  const flaggedCount = useMemo(() => Object.keys(cells).length, [cells]);
  const hasAnySignal =
    Boolean(missedFactors.trim()) ||
    Boolean(missedOptions.trim()) ||
    wrongFactorIds.size > 0 ||
    wrongOptionIds.size > 0 ||
    flaggedCount > 0 ||
    Boolean(notes.trim());

  const submit = async () => {
    if (!hasAnySignal) {
      // no-op — nothing to save
      onClose?.();
      return;
    }
    setSaving(true);
    try {
      // Build cell_corrections with both ids and human names so admin can read it
      const fById: Record<string, Factor> = {};
      factors.forEach(f => { if (f.id) fById[f.id] = f; });
      const oById: Record<string, Option> = {};
      options.forEach(o => { if (o.id) oById[o.id] = o; });
      const cell_corrections = Object.entries(cells).map(([k, mark]) => {
        const [oid, fid] = k.split('|');
        const opt = oById[oid];
        const fac = fById[fid];
        return {
          option_id: oid || undefined,
          option_name: opt ? labelOf(opt) : undefined,
          factor_id: fid || undefined,
          factor_name: fac ? labelOf(fac) : undefined,
          was: opt ? cellValue(opt, fid) : '',
          should_be: mark.should_be,
          issue: mark.issue,
        };
      });

      await api.post(`/url-analyze/runs/${runId}/training`, {
        missed_factors_count: missedFactors.trim() ? parseInt(missedFactors, 10) : undefined,
        missed_options_count: missedOptions.trim() ? parseInt(missedOptions, 10) : undefined,
        wrong_factors: Array.from(wrongFactorIds),
        wrong_options: Array.from(wrongOptionIds),
        cell_corrections,
        notes: notes.trim() || undefined,
        decision_id: decisionId,
      });
      setSavedAt(Date.now());
      onSaved?.();
    } catch (e: any) {
      // surface inline; keep the panel open so the user can retry
      const msg = e?.response?.data?.detail || 'Could not save your feedback';
      if (Platform.OS === 'web') {
        window.alert(typeof msg === 'string' ? msg : JSON.stringify(msg));
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <View testID="train-ai-panel" style={st.panel}>
      <View style={st.head}>
        <Ionicons name="school-outline" size={16} color="#92400E" />
        <Text style={st.title}>Train AI — tell us exactly what went wrong</Text>
        {onClose && (
          <TouchableOpacity onPress={onClose} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
            <Ionicons name="close" size={18} color="#92400E" />
          </TouchableOpacity>
        )}
      </View>
      <Text style={st.hint}>
        Your input is sent to the Admin&apos;s Import URL Intel for this exact run, and is
        prioritised by Auto-Tune over heuristic-only signals. Skip any section that&apos;s
        fine — only fill what was wrong.
      </Text>

      {/* ─── Step 2 — missed factor count ─── */}
      <SectionHead step="Step 2" title="Factors — did we miss any?" />
      <Row label="How many factors did we miss?">
        <TextInput
          testID="train-missed-factors"
          value={missedFactors} onChangeText={setMissedFactors}
          keyboardType="number-pad" maxLength={3}
          placeholder="e.g. 3" placeholderTextColor={C.muted}
          style={st.num}
        />
        <Text style={st.helper}>e.g. you expected 6 factors, we got {Math.max(0, factors.length)}</Text>
      </Row>
      <Text style={st.subHead}>Tap any factor that is WRONG or irrelevant:</Text>
      <View style={st.chipRow}>
        {factors.length === 0 ? (
          <Text style={st.empty}>No factors extracted yet.</Text>
        ) : factors.map(f => {
          const id = f.id || labelOf(f);
          const on = wrongFactorIds.has(id);
          return (
            <TouchableOpacity
              key={id}
              testID={`train-wrong-factor-${id}`}
              activeOpacity={0.8}
              onPress={() => toggle(wrongFactorIds, id, setWrongFactorIds)}
              style={[st.chip, on && st.chipOn]}>
              <Ionicons name={on ? 'close-circle' : 'ellipse-outline'}
                        size={13} color={on ? C.chipOnText : C.sub} />
              <Text style={[st.chipTxt, on && st.chipTxtOn]}>{labelOf(f)}</Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {/* ─── Step 6 — missed option count ─── */}
      <SectionHead step="Step 6" title="Options — did we miss any?" />
      <Row label="How many options did we miss?">
        <TextInput
          testID="train-missed-options"
          value={missedOptions} onChangeText={setMissedOptions}
          keyboardType="number-pad" maxLength={3}
          placeholder="e.g. 2" placeholderTextColor={C.muted}
          style={st.num}
        />
        <Text style={st.helper}>e.g. you expected 6 options, we got {Math.max(0, options.length)}</Text>
      </Row>
      <Text style={st.subHead}>Tap any option that is WRONG or irrelevant:</Text>
      <View style={st.chipRow}>
        {options.length === 0 ? (
          <Text style={st.empty}>No options extracted yet.</Text>
        ) : options.map(o => {
          const id = o.id || labelOf(o);
          const on = wrongOptionIds.has(id);
          return (
            <TouchableOpacity
              key={id}
              testID={`train-wrong-option-${id}`}
              activeOpacity={0.8}
              onPress={() => toggle(wrongOptionIds, id, setWrongOptionIds)}
              style={[st.chip, on && st.chipOn]}>
              <Ionicons name={on ? 'close-circle' : 'ellipse-outline'}
                        size={13} color={on ? C.chipOnText : C.sub} />
              <Text style={[st.chipTxt, on && st.chipTxtOn]}>{labelOf(o)}</Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {/* ─── Step 7 — option × factor cell grid ─── */}
      <SectionHead step="Step 7" title="Wrong / missing option-factor values" />
      <Text style={st.hint}>
        Tap the exact cell where a value is wrong or missing. We&apos;ll show the AI&apos;s value and
        you can (optionally) enter the correct one.
      </Text>
      <CellGrid
        factors={factors} options={options} cells={cells}
        onPress={openCell}
      />
      {flaggedCount > 0 && (
        <Text style={[st.helper, { color: C.bad, marginTop: 4 }]}>
          {flaggedCount} cell{flaggedCount === 1 ? '' : 's'} flagged
        </Text>
      )}

      {/* ─── Inline cell editor (appears in-place; not a modal) ─── */}
      {activeCell && (
        <ActiveCellEditor
          activeCell={activeCell}
          factors={factors} options={options}
          existing={cells[activeCell]}
          shouldBe={activeShouldBe}
          setShouldBe={setActiveShouldBe}
          onApply={applyCellMark}
          onClear={clearCell}
          onCancel={() => { setActiveCell(null); setActiveShouldBe(''); }}
        />
      )}

      {/* ─── Notes ─── */}
      <SectionHead step="Anything else?" title="Notes for the Auto-Tune team (optional)" />
      <TextInput
        testID="train-notes"
        value={notes} onChangeText={setNotes}
        multiline
        placeholder="e.g. 'All Brands' sidebar was missed; chennai pricing instead of national"
        placeholderTextColor={C.muted}
        style={st.notes}
      />

      {/* ─── Footer ─── */}
      <View style={st.footer}>
        {savedAt && !saving && (
          <Text style={st.savedTxt}>
            <Ionicons name="checkmark-circle" size={12} color={C.ok} /> Saved — admin will see this run flagged.
          </Text>
        )}
        <View style={{ flex: 1 }} />
        <TouchableOpacity
          testID="train-submit"
          disabled={saving || !hasAnySignal}
          onPress={submit}
          style={[st.submit,
                  (saving || !hasAnySignal) && { opacity: 0.5 }]}>
          {saving ? (
            <ActivityIndicator color="#FFF" size="small" />
          ) : (
            <>
              <Ionicons name="send" size={14} color="#FFF" />
              <Text style={st.submitTxt}>Send training feedback</Text>
            </>
          )}
        </TouchableOpacity>
      </View>
    </View>
  );
}

// ── small helpers ───────────────────────────────────────────────────────────
function SectionHead({ step, title }: { step: string; title: string }) {
  return (
    <View style={st.sectionHead}>
      <View style={st.stepPill}><Text style={st.stepPillTxt}>{step}</Text></View>
      <Text style={st.sectionTitle}>{title}</Text>
    </View>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 6 }}>
      <Text style={{ color: C.text, fontSize: 12.5, fontWeight: '600' }}>{label}</Text>
      {children}
    </View>
  );
}

// ── Cell grid (option × factor) ─────────────────────────────────────────────
function CellGrid({
  factors, options, cells, onPress,
}: {
  factors: Factor[]; options: Option[];
  cells: Record<CellKey, CellMark>;
  onPress: (oid?: string, fid?: string) => void;
}) {
  if (!factors.length || !options.length) {
    return <Text style={st.empty}>Need at least one factor and one option to mark cells.</Text>;
  }
  const colW = 110;
  const optColW = 130;
  return (
    <View style={{ borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 8, overflow: 'hidden', backgroundColor: '#FFF' }}>
      <ScrollView horizontal showsHorizontalScrollIndicator>
        <View>
          {/* header row: option name col + each factor */}
          <View style={[st.gridRow, { backgroundColor: '#F8FAFC' }]}>
            <View style={[st.gridCell, { width: optColW, borderRightWidth: 1, borderColor: '#E2E8F0' }]}>
              <Text style={st.gridHead}>Option ↓ / Factor →</Text>
            </View>
            {factors.map(f => (
              <View key={`h-${f.id || labelOf(f)}`}
                    style={[st.gridCell, { width: colW, borderRightWidth: 1, borderColor: '#E2E8F0' }]}>
                <Text style={st.gridHead} numberOfLines={2}>{labelOf(f)}</Text>
              </View>
            ))}
          </View>
          {options.map(o => (
            <View key={`r-${o.id || labelOf(o)}`} style={st.gridRow}>
              <View style={[st.gridCell, { width: optColW, borderRightWidth: 1, borderColor: '#E2E8F0', backgroundColor: '#F8FAFC' }]}>
                <Text style={st.gridOpt} numberOfLines={2}>{labelOf(o)}</Text>
              </View>
              {factors.map(f => {
                const k = cellKey(o.id, f.id);
                const mark = cells[k];
                const v = cellValue(o, f.id);
                const bg = mark?.issue === 'wrong'
                  ? C.cellWrong
                  : mark?.issue === 'missing'
                    ? C.cellMissing
                    : C.cellOk;
                return (
                  <TouchableOpacity
                    key={k}
                    testID={`train-cell-${k}`}
                    activeOpacity={0.7}
                    onPress={() => onPress(o.id, f.id)}
                    style={[st.gridCell, {
                      width: colW, borderRightWidth: 1, borderColor: '#E2E8F0',
                      backgroundColor: bg, paddingVertical: 6,
                    }]}>
                    <Text style={st.gridVal} numberOfLines={2}>{v || <Text style={{ color: C.muted, fontStyle: 'italic' }}>—</Text>}</Text>
                    {mark && (
                      <View style={st.cellPin}>
                        <Ionicons
                          name={mark.issue === 'wrong' ? 'close-circle' : 'alert-circle'}
                          size={12}
                          color={mark.issue === 'wrong' ? C.bad : C.warn}
                        />
                      </View>
                    )}
                  </TouchableOpacity>
                );
              })}
            </View>
          ))}
        </View>
      </ScrollView>
    </View>
  );
}

// ── Active cell inline editor ───────────────────────────────────────────────
function ActiveCellEditor({
  activeCell, factors, options, existing,
  shouldBe, setShouldBe, onApply, onClear, onCancel,
}: {
  activeCell: CellKey;
  factors: Factor[]; options: Option[];
  existing?: CellMark;
  shouldBe: string;
  setShouldBe: (s: string) => void;
  onApply: (issue: 'wrong' | 'missing') => void;
  onClear: () => void;
  onCancel: () => void;
}) {
  const [oid, fid] = activeCell.split('|');
  const opt = options.find(o => o.id === oid);
  const fac = factors.find(f => f.id === fid);
  const wasVal = opt ? cellValue(opt, fid) : '';
  return (
    <View testID="train-cell-editor" style={st.cellEditor}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <Ionicons name="pencil" size={14} color={C.primary} />
        <Text style={st.cellEditorTitle} numberOfLines={2}>
          {opt ? labelOf(opt) : '?'} → {fac ? labelOf(fac) : '?'}
        </Text>
        <View style={{ flex: 1 }} />
        <TouchableOpacity onPress={onCancel} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
          <Ionicons name="close" size={16} color={C.sub} />
        </TouchableOpacity>
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
        <Text style={st.cellEditorLbl}>AI said:</Text>
        <Text style={st.cellEditorWas} numberOfLines={2}>
          {wasVal ? wasVal : <Text style={{ color: C.muted, fontStyle: 'italic' }}>(no value)</Text>}
        </Text>
      </View>
      <Text style={[st.cellEditorLbl, { marginTop: 6 }]}>Correct value (optional):</Text>
      <TextInput
        testID="train-cell-correct-input"
        value={shouldBe} onChangeText={setShouldBe}
        placeholder="e.g. ₹9.99 lakh" placeholderTextColor={C.muted}
        style={st.cellEditorInput}
      />
      <View style={{ flexDirection: 'row', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
        <TouchableOpacity
          testID="train-cell-mark-wrong"
          onPress={() => onApply('wrong')}
          style={[st.cellBtn, { backgroundColor: C.badBg, borderColor: C.badBorder }]}>
          <Ionicons name="close-circle" size={13} color={C.bad} />
          <Text style={[st.cellBtnTxt, { color: C.bad }]}>Wrong value</Text>
        </TouchableOpacity>
        <TouchableOpacity
          testID="train-cell-mark-missing"
          onPress={() => onApply('missing')}
          style={[st.cellBtn, { backgroundColor: C.warnBg, borderColor: C.warnBorder }]}>
          <Ionicons name="alert-circle" size={13} color={C.warn} />
          <Text style={[st.cellBtnTxt, { color: C.warn }]}>Missing value</Text>
        </TouchableOpacity>
        {existing && (
          <TouchableOpacity
            testID="train-cell-clear"
            onPress={onClear}
            style={[st.cellBtn, { backgroundColor: '#F1F5F9', borderColor: '#CBD5E1' }]}>
            <Ionicons name="refresh" size={13} color={C.sub} />
            <Text style={[st.cellBtnTxt, { color: C.sub }]}>Clear mark</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  panel: {
    backgroundColor: C.panel, borderWidth: 1, borderColor: C.border,
    borderRadius: 12, padding: 14, marginBottom: 14, gap: 10,
  },
  head: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  title: { fontSize: 14, fontWeight: '800', color: '#92400E', flex: 1 },
  hint: { fontSize: 11.5, color: C.sub, lineHeight: 16 },

  sectionHead: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 6 },
  stepPill: { backgroundColor: C.primaryBg, borderWidth: 1, borderColor: C.primaryBorder, paddingHorizontal: 8, paddingVertical: 2, borderRadius: 999 },
  stepPillTxt: { fontSize: 10.5, fontWeight: '800', color: C.primary, letterSpacing: 0.3 },
  sectionTitle: { fontSize: 12.5, fontWeight: '800', color: C.text, flex: 1 },
  subHead: { fontSize: 11.5, color: C.sub, fontWeight: '600', marginTop: 4 },

  num: {
    borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 8,
    paddingHorizontal: 10, paddingVertical: 6, width: 70,
    fontSize: 13, color: C.text, backgroundColor: '#FFF',
  },
  helper: { fontSize: 11, color: C.muted },

  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 4 },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: C.chipBg, borderWidth: 1, borderColor: C.chipBorder,
    borderRadius: 999, paddingHorizontal: 8, paddingVertical: 4,
  },
  chipOn: { backgroundColor: C.chipOn, borderColor: C.chipOnBorder },
  chipTxt: { fontSize: 11.5, color: C.sub, fontWeight: '600' },
  chipTxtOn: { color: C.chipOnText, fontWeight: '800' },

  empty: { fontSize: 11.5, color: C.muted, fontStyle: 'italic' },

  gridRow: { flexDirection: 'row' },
  gridCell: { padding: 6, borderBottomWidth: 1, borderColor: '#E2E8F0', minHeight: 36, justifyContent: 'center' },
  gridHead: { fontSize: 10.5, fontWeight: '800', color: C.sub },
  gridOpt: { fontSize: 11, fontWeight: '700', color: C.text },
  gridVal: { fontSize: 11, color: C.text },
  cellPin: { position: 'absolute', top: 2, right: 2 },

  cellEditor: {
    backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: C.primaryBorder,
    borderRadius: 10, padding: 10, marginTop: 6,
  },
  cellEditorTitle: { fontSize: 12.5, fontWeight: '800', color: C.text, flexShrink: 1 },
  cellEditorLbl: { fontSize: 11, fontWeight: '700', color: C.sub },
  cellEditorWas: { fontSize: 12, color: C.text, flexShrink: 1 },
  cellEditorInput: {
    borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 8,
    paddingHorizontal: 10, paddingVertical: 7, marginTop: 4,
    fontSize: 12.5, color: C.text, backgroundColor: '#FFF',
  },
  cellBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    borderWidth: 1, borderRadius: 8, paddingHorizontal: 9, paddingVertical: 5,
  },
  cellBtnTxt: { fontSize: 11.5, fontWeight: '800' },

  notes: {
    borderWidth: 1, borderColor: '#CBD5E1', borderRadius: 8,
    paddingHorizontal: 10, paddingVertical: 8, minHeight: 60, maxHeight: 110,
    fontSize: 12.5, color: C.text, backgroundColor: '#FFF',
    textAlignVertical: 'top',
  },

  footer: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8, flexWrap: 'wrap' },
  savedTxt: { fontSize: 11.5, color: C.ok, fontWeight: '700' },
  submit: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: C.primary, borderRadius: 10,
    paddingHorizontal: 14, paddingVertical: 9,
  },
  submitTxt: { color: '#FFF', fontWeight: '800', fontSize: 12.5 },
});
