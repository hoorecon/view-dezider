/**
 * DeepImportBudgetPicker — Wave 2 #8b (June 2026)
 *
 * After a Deep-Import job finalises, the decision is flagged with
 * `deep_import_pending_rank = true`. Once the user finishes Step 5
 * (factor weightages), this modal pops up to:
 *
 *   1. Show how many options were discovered on the URL.
 *   2. Let the user pick how many to FULLY auto-assess (slider, bounded
 *      by Admin → AI Wallet Config → deep_import_max_options).
 *   3. Show the live AI-credit estimate (also asks
 *      `/deep-import/budget-estimate` for accuracy).
 *   4. Run `/deep-import/auto-assess-rank`, jump straight to Step 8 with
 *      the top-N options (also from admin config) pre-ranked.
 *
 * Skip is intentionally allowed — the user might prefer to assess
 * manually in Step 7. Dismiss writes `deep_import_pending_rank=false`
 * so the modal doesn't keep nagging on every Step-5 visit.
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  View, Text, TouchableOpacity, Modal, ActivityIndicator, StyleSheet, TextInput,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../constants/colors';
import api from '../utils/api';
import { showAlert } from '../utils/alert';
import { useDecision } from '../context/DecisionContext';
import { useLoaderMusic } from '../hooks/useLoaderMusic';

interface BudgetEstimate {
  total_options: number;
  max_options: number;
  top_n: number;
  lower: number;
  upper: number;
  requested: number;
  empty_cells: number;
  per_cell_credits: number;
  estimate_credits: number;
  balance: number;
  sufficient: boolean;
  shortfall: number;
}

interface Props {
  /** Force-hide override — useful when the parent screen wants to
   *  suppress the modal (e.g. while another sheet is open). */
  disabled?: boolean;
  /** Called after a successful run with the top-N option-ids. The
   *  caller is expected to navigate to Step 8. */
  onRanked?: (topN: string[]) => void;
}

export const DeepImportBudgetPicker: React.FC<Props> = ({ disabled, onRanked }) => {
  const { decision, fetchDecision, setCurrentStep } = useDecision();
  const pending = !!(decision as any)?.deep_import_pending_rank;
  const [visible, setVisible] = useState(false);
  const [estimate, setEstimate] = useState<BudgetEstimate | null>(null);
  const [budget, setBudget] = useState<number>(0);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  // Once the user closes/skips/finishes for a given decision, remember its id
  // so the auto-open effect below can't immediately re-open the modal while
  // the context's `deep_import_pending_rank` flag is still catching up to the
  // server. Without this the Skip/✕ buttons appeared to do nothing — the modal
  // re-opened on the very next render (the screener.in "stuck popup loop").
  const [dismissedId, setDismissedId] = useState<string | null>(null);

  // Top-5 reveal soundtrack — plays the `results_reveal` slot (fallback:
  // `default`) while the auto-assess-rank loop is in flight, so the user
  // hears the celebratory music BEFORE Step 8 lands. Per-user mute applies
  // globally (same AsyncStorage key as every other LoaderMusicChip).
  const { available: musicAvailable, playing: musicPlaying, muted: musicMuted, toggleMute: toggleMusicMute } =
    useLoaderMusic(running, 'top5_picker');

  // Auto-open when the decision flips into "pending rank" — but only once
  // per decision; the user can re-trigger by manually re-running deep import.
  useEffect(() => {
    if (disabled) return;
    if (pending && !visible && dismissedId !== decision?.id) {
      setVisible(true);
    }
  }, [pending, disabled, visible, dismissedId, decision?.id]);

  // Fetch the auto-default estimate when the modal opens.
  useEffect(() => {
    if (!visible || !decision?.id) return;
    let cancelled = false;
    setLoading(true);
    api.get(`/decisions/${decision.id}/deep-import/budget-estimate`, { params: { budget_count: 0 } })
      .then(({ data }) => {
        if (cancelled) return;
        setEstimate(data);
        setBudget(data.requested);
      })
      .catch((e: any) => {
        const msg = e?.response?.data?.detail || 'Could not load the cost estimate.';
        showAlert('Estimate unavailable', typeof msg === 'string' ? msg : JSON.stringify(msg));
        setVisible(false);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [visible, decision?.id]);

  // Re-fetch estimate whenever the user moves the slider — keeps the
  // credits number accurate (empty-cell count changes with budget).
  useEffect(() => {
    if (!visible || !decision?.id || !estimate) return;
    if (budget === estimate.requested) return;
    let cancelled = false;
    api.get(`/decisions/${decision.id}/deep-import/budget-estimate`, { params: { budget_count: budget } })
      .then(({ data }) => { if (!cancelled) setEstimate(data); })
      .catch(() => { /* keep stale estimate on transient errors */ });
    return () => { cancelled = true; };
  }, [budget, visible, decision?.id, estimate]);

  const close = (alsoDismissOnServer: boolean) => {
    setRunning(false);
    setVisible(false);
    if (decision?.id) setDismissedId(decision.id);   // block the auto-open effect from re-firing
    if (alsoDismissOnServer && decision?.id) {
      api.post(`/decisions/${decision.id}/deep-import/dismiss-rank-prompt`)
        .then(() => { fetchDecision().catch(() => {}); })   // sync context so `pending` flips false
        .catch(() => { /* best effort */ });
    }
  };

  const run = async () => {
    if (!decision?.id || running) return;
    setRunning(true);
    try {
      const { data } = await api.post(
        `/decisions/${decision.id}/deep-import/auto-assess-rank`,
        { budget_count: budget },
      );
      await fetchDecision();
      if (decision?.id) setDismissedId(decision.id);
      setVisible(false);
      const topN: string[] = data?.top_n_option_ids || [];
      if (onRanked) onRanked(topN);
      if (data?.out_of_credits) {
        showAlert(
          'AI credits exhausted',
          'We ranked as many options as the wallet allowed. Top up to finish the rest.',
        );
      } else if (data?.ai_unavailable) {
        showAlert(
          'AI temporarily unavailable',
          `Processed ${data?.cells_succeeded || 0} cells before the AI service went down. Please retry in a minute.`,
        );
      } else {
        showAlert(
          `Top ${topN.length} ready`,
          `Auto-assessed ${data?.cells_succeeded || 0} cells and ranked the top ${topN.length} options. Jumping you into Step 8 (Decision Comparison).`,
        );
      }
      // Jump straight to Step 8 — Decision Comparison.
      setTimeout(() => setCurrentStep(8), 350);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Could not run the auto-assess.';
      showAlert('Auto-assess failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setRunning(false);
    }
  };

  // Derived display values
  const cap = estimate ? Math.max(estimate.lower, estimate.upper) : 0;
  const floor = estimate ? estimate.lower : 0;
  const fmtCr = (n: number) => n.toFixed(1).replace(/\.0$/, '');

  // Slider buttons (we avoid 3rd-party slider lib for a quick install-free UX).
  const stepValues = useMemo(() => {
    if (!estimate) return [] as number[];
    const out: number[] = [];
    for (let i = estimate.lower; i <= estimate.upper; i++) out.push(i);
    return out;
  }, [estimate]);

  if (!visible) return null;

  return (
    <Modal visible={visible} transparent animationType="fade"
      onRequestClose={() => close(false)}>
      <View style={s.overlay}>
        <View style={s.dialog} testID="deep-import-budget-picker">
          <View style={s.head}>
            <Ionicons name="sparkles" size={18} color="#7C3AED" />
            <Text style={s.title}>Rank & jump to Step 8?</Text>
            <TouchableOpacity
              testID="deep-import-budget-close"
              onPress={() => close(true)}
              hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
              style={{ marginLeft: 'auto' }}>
              <Ionicons name="close" size={20} color={COLORS.textMuted} />
            </TouchableOpacity>
          </View>

          {loading && !estimate ? (
            <View style={{ paddingVertical: 22, alignItems: 'center' }}>
              <ActivityIndicator color="#7C3AED" />
              <Text style={[s.sub, { marginTop: 8 }]}>Counting discovered options…</Text>
            </View>
          ) : estimate ? (
            <>
              <Text style={s.sub}>
                We discovered{' '}
                <Text style={s.bold}>{estimate.total_options} option{estimate.total_options === 1 ? '' : 's'}</Text>{' '}
                from the URL.{' '}
                AI can auto-fill factor values, assess every cell against your Step-5 weightages,
                and surface the <Text style={s.bold}>top {estimate.top_n}</Text> in Step 8.
              </Text>

              <Text style={s.lbl}>How many options to fully process?</Text>
              <View style={s.row}>
                <TouchableOpacity
                  testID="deep-import-budget-dec"
                  style={s.stepBtn}
                  onPress={() => setBudget(b => Math.max(floor, b - 1))}
                  disabled={budget <= floor}>
                  <Ionicons name="remove" size={18} color={budget <= floor ? '#CBD5E1' : '#0F172A'} />
                </TouchableOpacity>
                <TextInput
                  testID="deep-import-budget-input"
                  style={s.input}
                  value={String(budget)}
                  onChangeText={(v) => {
                    const n = parseInt(v.replace(/[^\d]/g, ''), 10);
                    if (Number.isFinite(n)) setBudget(Math.max(floor, Math.min(cap, n)));
                  }}
                  keyboardType="number-pad"
                  maxLength={3}
                />
                <TouchableOpacity
                  testID="deep-import-budget-inc"
                  style={s.stepBtn}
                  onPress={() => setBudget(b => Math.min(cap, b + 1))}
                  disabled={budget >= cap}>
                  <Ionicons name="add" size={18} color={budget >= cap ? '#CBD5E1' : '#0F172A'} />
                </TouchableOpacity>
                <Text style={s.rangeHint}>min {floor} · max {cap}</Text>
              </View>

              {stepValues.length <= 12 && (
                <View style={s.chipsRow}>
                  {stepValues.map(v => (
                    <TouchableOpacity
                      key={v}
                      testID={`deep-import-budget-chip-${v}`}
                      onPress={() => setBudget(v)}
                      style={[s.chip, v === budget && s.chipOn]}
                      activeOpacity={0.85}
                    >
                      <Text style={[s.chipTxt, v === budget && s.chipTxtOn]}>{v}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              )}

              <View style={[s.estimateBox, estimate.sufficient ? s.estOk : s.estBad]} testID="deep-import-budget-estimate">
                <Ionicons
                  name={estimate.sufficient ? 'checkmark-circle' : 'alert-circle'}
                  size={16}
                  color={estimate.sufficient ? '#059669' : '#DC2626'}
                />
                <Text style={[s.estTxt, { color: estimate.sufficient ? '#065F46' : '#991B1B' }]}>
                  ≈ {fmtCr(estimate.estimate_credits)} cr needed
                  ({estimate.empty_cells} cell{estimate.empty_cells === 1 ? '' : 's'} × {estimate.per_cell_credits.toFixed(2)} cr) ·{' '}
                  {fmtCr(estimate.balance)} cr available
                  {!estimate.sufficient ? ` — short by ${fmtCr(estimate.shortfall)} cr` : ''}
                </Text>
              </View>

              <View style={s.btnsRow}>
                <TouchableOpacity testID="deep-import-budget-skip" style={s.skipBtn}
                  onPress={() => close(true)}>
                  <Text style={s.skipTxt}>{running ? 'Close (runs in background)' : "Skip — I'll assess manually"}</Text>
                </TouchableOpacity>
                <TouchableOpacity testID="deep-import-budget-run" style={[s.goBtn, (!estimate.sufficient || running) && { opacity: 0.55 }]}
                  onPress={run} disabled={running || !estimate.sufficient}>
                  {running ? <ActivityIndicator color="#FFF" /> : <Ionicons name="rocket" size={14} color="#FFF" />}
                  <Text style={s.goTxt}>{running ? 'Processing…' : 'Process & Rank'}</Text>
                </TouchableOpacity>
              </View>

              {!estimate.sufficient && (
                <Text style={s.warnLine}>
                  Top up your AI Wallet — Profile → AI Wallet — or lower the option budget.
                </Text>
              )}
              {running && musicAvailable && (
                <TouchableOpacity
                  testID="deep-import-budget-music"
                  onPress={toggleMusicMute}
                  activeOpacity={0.7}
                  style={{
                    flexDirection: 'row', alignItems: 'center', gap: 6,
                    alignSelf: 'center', marginTop: 10,
                    paddingHorizontal: 10, paddingVertical: 5, borderRadius: 14,
                    backgroundColor: musicMuted ? '#F1F5F9' : '#FAF5FF',
                    borderWidth: 1, borderColor: musicMuted ? '#CBD5E1' : '#E9D5FF',
                  }}>
                  <Ionicons
                    name={musicMuted ? 'volume-mute-outline' : (musicPlaying ? 'musical-notes' : 'musical-notes-outline')}
                    size={11}
                    color={musicMuted ? '#64748B' : '#7C3AED'}
                  />
                  <Text style={{ fontSize: 10.5, fontWeight: '700', color: musicMuted ? '#64748B' : '#7C3AED' }}>
                    {musicMuted ? 'Reveal music muted — tap to unmute' : 'Reveal music playing — tap to mute'}
                  </Text>
                </TouchableOpacity>
              )}
            </>
          ) : null}
        </View>
      </View>
    </Modal>
  );
};

export default DeepImportBudgetPicker;

const s = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(15, 23, 42, 0.55)', alignItems: 'center', justifyContent: 'center', padding: 18 },
  dialog: { width: '100%', maxWidth: 460, backgroundColor: '#FFF', borderRadius: 16, padding: 20, gap: 8 },
  head: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  title: { fontSize: 16, fontWeight: '800', color: COLORS.textPrimary },
  sub: { fontSize: 12.5, lineHeight: 18, color: COLORS.textMuted, marginTop: 6 },
  bold: { fontWeight: '800', color: '#0F172A' },
  lbl: { fontSize: 12.5, fontWeight: '700', color: '#0F172A', marginTop: 12 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 6, flexWrap: 'wrap' },
  stepBtn: { width: 34, height: 34, borderRadius: 8, backgroundColor: '#F1F5F9', borderWidth: 1, borderColor: '#E2E8F0', alignItems: 'center', justifyContent: 'center' },
  input: { minWidth: 56, paddingHorizontal: 10, paddingVertical: 6, borderWidth: 1.5, borderColor: '#C4B5FD', borderRadius: 8, fontSize: 15, fontWeight: '800', color: '#0F172A', textAlign: 'center', backgroundColor: '#FFF' },
  rangeHint: { fontSize: 11, color: COLORS.textMuted, marginLeft: 'auto' },
  chipsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 8 },
  chip: { paddingHorizontal: 9, paddingVertical: 4, borderRadius: 6, backgroundColor: '#F1F5F9', borderWidth: 1, borderColor: '#E2E8F0' },
  chipOn: { backgroundColor: '#7C3AED', borderColor: '#7C3AED' },
  chipTxt: { fontSize: 11.5, fontWeight: '700', color: '#475569' },
  chipTxtOn: { color: '#FFF' },
  estimateBox: { marginTop: 12, padding: 10, borderRadius: 9, flexDirection: 'row', gap: 8, alignItems: 'flex-start' },
  estOk: { backgroundColor: '#ECFDF5', borderWidth: 1, borderColor: '#A7F3D0' },
  estBad: { backgroundColor: '#FEF2F2', borderWidth: 1, borderColor: '#FECACA' },
  estTxt: { flex: 1, fontSize: 12, lineHeight: 17, fontWeight: '600' },
  btnsRow: { flexDirection: 'row', justifyContent: 'flex-end', gap: 10, marginTop: 14 },
  skipBtn: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: 9 },
  skipTxt: { fontSize: 12.5, fontWeight: '700', color: COLORS.textMuted },
  goBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: '#7C3AED', paddingHorizontal: 18, paddingVertical: 10, borderRadius: 9 },
  goTxt: { color: '#FFF', fontSize: 13, fontWeight: '800' },
  warnLine: { fontSize: 11, color: '#B45309', marginTop: 8, textAlign: 'center' },
});
