/**
 * Deep Import (multi-page crawl) — opt-in Step-2 import mode.
 * Flow: base URL + 1-2 line context → consent → background crawl (live
 * progress) → FACTOR REVIEW (include / priority per factor) → merge approved
 * factors + options into the decision (zero extra AI cost at merge time).
 */
import React, { useEffect, useRef, useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, Modal,
  ActivityIndicator, ScrollView, StyleSheet,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import api from '../../utils/api';
import { showAlert } from '../../utils/alert';
import UrlAccessConsentModal, { UrlConsentPayload } from '../UrlAccessConsentModal';
import ImportCreditsStrip from '../ImportCreditsStrip';

interface JobFactor {
  name: string; group: string; data_type: string; unit?: string | null;
  operator?: string | null; expected_value?: string | null; coverage: number;
}
interface ReviewRow extends JobFactor { include: boolean; weight: number; }

interface Props {
  decisionId: string;
  onMerged: () => Promise<void> | void;
}

export const DeepImport: React.FC<Props> = ({ decisionId, onMerged }) => {
  const [open, setOpen] = useState(false);
  const [stage, setStage] = useState<'setup' | 'progress' | 'review' | 'merging'>('setup');
  const [constraintNote, setConstraintNote] = useState<string | null>(null);
  const [baseUrl, setBaseUrl] = useState('');
  const [context, setContext] = useState('');
  const [maxPages, setMaxPages] = useState(5);
  // Constraint-gate escape hatch. Default CHECKED (= constraints disabled)
  // so a small import isn't silently axed by the gate. Uncheck to re-enable
  // the gate when the user has tight hard constraints in their context and
  // wants to save AI credits (~56% fewer constraint-related AI calls).
  const [disableHardConstraints, setDisableHardConstraints] = useState(true);
  const [consentOpen, setConsentOpen] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ pct: number; label: string }>({ pct: 5, label: 'Starting…' });
  const [rows, setRows] = useState<ReviewRow[]>([]);
  const [optionCount, setOptionCount] = useState(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPoll = () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };
  useEffect(() => stopPoll, []);

  const reset = () => { stopPoll(); setStage('setup'); setJobId(null); setRows([]); };

  const startJob = async (consent: UrlConsentPayload) => {
    setConsentOpen(false);
    setStage('progress');
    setProgress({ pct: 5, label: 'Starting…' });
    try {
      const { data } = await api.post(`/deep-import/decision/${decisionId}/start`, {
        base_url: baseUrl.trim(),
        context: context.trim(),
        max_pages: maxPages,
        eligibility_type: consent.eligibility_type,
        custom_note: consent.custom_note,
        accepted: true,
        disable_hard_constraints: disableHardConstraints,
      });
      setJobId(data.job_id);
      pollRef.current = setInterval(async () => {
        try {
          const r = await api.get(`/deep-import/jobs/${data.job_id}`);
          const job = r.data;
          setProgress(job.progress || { pct: 10, label: 'Working…' });
          if (job.status === 'factors_ready') {
            stopPoll();
            setOptionCount((job.options || []).length);
            setConstraintNote(job.constraint_note || null);
            setRows((job.factors || []).map((f: JobFactor) => ({ ...f, include: true, weight: 50 })));
            setStage('review');
          } else if (job.status === 'error') {
            stopPoll();
            setStage('setup');
            showAlert('Deep Import failed', job.error || 'Something went wrong during the crawl.');
          }
        } catch { /* transient poll error — keep trying */ }
      }, 1800);
    } catch (e: any) {
      setStage('setup');
      const msg = e?.response?.data?.detail || 'Could not start the deep import.';
      showAlert('Deep Import failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
  };

  const finalize = async () => {
    if (!jobId) return;
    const included = rows.filter(r => r.include);
    if (!included.length) { showAlert('Pick factors', 'Select at least one factor to import.'); return; }
    setStage('merging');
    try {
      const { data } = await api.post(`/deep-import/jobs/${jobId}/finalize`, {
        factors: rows.map(r => ({ name: r.name, include: r.include, weight: r.weight })),
      });
      await onMerged();
      setOpen(false);
      reset();
      const ver = data.verification || {};
      const verNote = (ver.blanked || 0) > 0
        ? `\n\n⚠ Page-grounding check: ${ver.blanked} value(s) could not be verified on the crawled pages and were left blank${(ver.unverified || []).length ? `: ${(ver.unverified || []).slice(0, 4).join('; ')}` : ''}.`
        : (ver.verified || 0) > 0
          ? `\n\n✓ Page-grounding check: all ${ver.verified} values verified against the crawled pages.`
          : '';
      const geoNote = data.geo_note
        ? '\n\nℹ Money values come from the pages\u2019 DEFAULT (non-localised) view — they can differ from prices personalised to your city/account.'
        : '';
      showAlert('Deep Import complete',
        `Added ${data.factors_added} factor${data.factors_added === 1 ? '' : 's'} and ${data.options_added} option${data.options_added === 1 ? '' : 's'} from ${data.item_count} crawled pages. Options (Step 6) and actuals (Step 7) are pre-filled.${verNote}${geoNote}`);
    } catch (e: any) {
      setStage('review');
      const msg = e?.response?.data?.detail || 'Merge failed.';
      showAlert('Deep Import failed', typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
  };

  return (
    <>
      <TouchableOpacity
        testID="deep-import-open-btn"
        style={st.openBtn} activeOpacity={0.85}
        onPress={() => { reset(); setOpen(true); }}>
        <Ionicons name="git-network-outline" size={16} color="#7C3AED" />
        <View style={{ flex: 1 }}>
          <Text style={st.openBtnTitle}>Deep Import (multi-page)</Text>
          <Text style={st.openBtnSub}>
            Give a base URL (homepage or listing page) + your context — we find &amp; crawl the option
            detail pages, you approve &amp; prioritise the factors, then values fill in. Uses more AI
            credits than a normal import.
          </Text>
        </View>
        <Ionicons name="chevron-forward" size={16} color="#94A3B8" />
      </TouchableOpacity>

      <Modal visible={open} transparent animationType="fade" onRequestClose={() => { if (stage === 'setup') { setOpen(false); reset(); } }}>
        <View style={st.overlay}>
          <View style={st.card} testID="deep-import-modal">
            {/* ── SETUP ── */}
            {stage === 'setup' && (
              <>
                <Text style={st.title}>Deep Import</Text>
                <Text style={st.hint}>
                  We crawl up to {maxPages} option/detail pages from your base URL — even a homepage
                  works: we auto-locate the listing page matching your context. Factors come first
                  for your review; values fill in after.
                </Text>
                <Text style={st.fieldLabel}>Base URL *</Text>
                <TextInput testID="deep-import-url-input" style={st.input} autoCapitalize="none"
                  placeholder="https://www.example.com/listing-or-category-page"
                  value={baseUrl} onChangeText={setBaseUrl} />
                <Text style={st.fieldLabel}>Your decision context (1–2 lines) *</Text>
                <TextInput testID="deep-import-context-input" style={[st.input, { minHeight: 56 }]} multiline
                  placeholder="e.g. Choosing an electric hatchback under 10 lakh for city commutes"
                  value={context} onChangeText={setContext} />
                <Text style={st.fieldLabel}>Pages to crawl</Text>
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  {[3, 5, 8].map(n => (
                    <TouchableOpacity key={n} testID={`deep-import-pages-${n}`}
                      style={[st.pageChip, maxPages === n && st.pageChipActive]}
                      onPress={() => setMaxPages(n)}>
                      <Text style={[st.pageChipText, maxPages === n && st.pageChipTextActive]}>{n}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
                <ImportCreditsStrip endpoint="deep_import" pages={maxPages} tier="precise" />

                {/* Hard-constraint escape hatch — keeps users from getting
                    silently bitten by the constraint gate. Default CHECKED
                    so all crawled options reach the merge step. Uncheck to
                    re-enable the cost-saving gate (drops options that
                    contradict your hard constraints like budget caps, BHK
                    counts, 'rent vs buy', furnished/automatic, etc.). */}
                <TouchableOpacity
                  testID="deep-import-disable-constraints"
                  activeOpacity={0.8}
                  onPress={() => setDisableHardConstraints(v => !v)}
                  style={st.constraintRow}>
                  <Ionicons
                    name={disableHardConstraints ? 'checkbox' : 'square-outline'}
                    size={20}
                    color={disableHardConstraints ? '#7C3AED' : '#94A3B8'} />
                  <View style={{ flex: 1 }}>
                    <Text style={st.constraintTitle}>
                      Disable hard constraints — fetch more options
                    </Text>
                    <Text style={st.constraintHint}>
                      {disableHardConstraints
                        ? '✓ All crawled options will reach the merge step (e.g. ₹7.63–10L items kept for an "under ₹10L" context). Slightly higher AI spend.'
                        : 'Strict mode — options contradicting your context (budget caps, BHK counts, furnishing…) are auto-rejected before consolidation. Cheaper but can fail with "fewer than 2 valid options".'}
                    </Text>
                  </View>
                </TouchableOpacity>

                <View style={st.actions}>
                  <TouchableOpacity testID="deep-import-cancel-btn" style={st.cancelBtn}
                    onPress={() => { setOpen(false); reset(); }}>
                    <Text style={st.cancelText}>Cancel</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    testID="deep-import-start-btn"
                    style={[st.primaryBtn, (!baseUrl.trim() || context.trim().length < 3) && st.btnDisabled]}
                    disabled={!baseUrl.trim() || context.trim().length < 3}
                    onPress={() => setConsentOpen(true)}>
                    <Text style={st.primaryText}>Start crawl</Text>
                  </TouchableOpacity>
                </View>
              </>
            )}

            {/* ── PROGRESS ── */}
            {(stage === 'progress' || stage === 'merging') && (
              <>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <ActivityIndicator size="small" color="#7C3AED" />
                  <Text style={st.title}>{stage === 'merging' ? 'Merging…' : 'Deep crawling…'}</Text>
                </View>
                <Text testID="deep-import-progress-stage" style={st.progressLabel}>{progress.label}</Text>
                <View style={st.track}>
                  <View style={[st.fill, { width: `${Math.min(100, progress.pct)}%` }]} />
                </View>
                <Text testID="deep-import-progress-pct" style={st.pctText}>{Math.min(100, progress.pct)}%</Text>
                <Text style={st.hint}>
                  Crawling {maxPages} pages + 2 AI passes can take 2–4 minutes. Keep this open.
                </Text>
              </>
            )}

            {/* ── FACTOR REVIEW ── */}
            {stage === 'review' && (
              <>
                <Text style={st.title}>Review the discovered factors</Text>
                <Text style={st.hint}>
                  Found {rows.length} factor{rows.length === 1 ? '' : 's'} across {optionCount} crawled option pages.
                  Untick anything you don&apos;t need — values are imported ONLY for approved factors.
                  You&apos;ll classify (Mandatory / Optional) and prioritise these in Steps 3-5.
                </Text>
                {!!constraintNote && (
                  <View style={st.constraintNote} testID="deep-import-constraint-note">
                    <Ionicons name="shield-checkmark" size={13} color="#B45309" />
                    <Text style={st.constraintNoteTxt}>{constraintNote}</Text>
                  </View>
                )}
                <ScrollView style={{ maxHeight: 380 }} showsVerticalScrollIndicator={false}>
                  {rows.map((r, i) => (
                    <View key={r.name} style={st.factorRow} testID={`deep-import-factor-row-${i}`}>
                      <TouchableOpacity
                        testID={`deep-import-factor-toggle-${i}`}
                        style={[st.checkbox, r.include && st.checkboxOn]}
                        onPress={() => setRows(rs => rs.map((x, xi) => xi === i ? { ...x, include: !x.include } : x))}>
                        {r.include && <Ionicons name="checkmark" size={13} color="#FFF" />}
                      </TouchableOpacity>
                      <View style={{ flex: 1 }}>
                        <Text style={[st.factorName, !r.include && st.factorOff]}>
                          {r.name}{r.unit ? ` (${r.unit})` : ''}
                        </Text>
                        <Text style={st.factorMeta}>
                          {r.group} · found on {r.coverage}/{optionCount} pages
                          {r.expected_value ? ` · expected ${r.operator || ''} ${r.expected_value}` : ''}
                        </Text>
                      </View>
                      {/* Priority chips were removed (Jun 2026) — classification
                          (Mandatory / Optional) and prioritisation belong to the
                          user's manual Steps 3-5 and must NOT be pre-empted by
                          the discovery review. Factors land in Step 2 with the
                          decision's standard default weight; the user adjusts
                          them later in the proper steps. */}
                    </View>
                  ))}
                </ScrollView>
                <View style={st.actions}>
                  <TouchableOpacity testID="deep-import-discard-btn" style={st.cancelBtn}
                    onPress={() => { setOpen(false); reset(); }}>
                    <Text style={st.cancelText}>Discard</Text>
                  </TouchableOpacity>
                  <TouchableOpacity testID="deep-import-confirm-btn" style={st.primaryBtn} onPress={finalize}>
                    <Text style={st.primaryText}>
                      Import {rows.filter(r => r.include).length} factors
                    </Text>
                  </TouchableOpacity>
                </View>
              </>
            )}
          </View>
        </View>
      </Modal>

      <UrlAccessConsentModal
        visible={consentOpen}
        url={baseUrl.trim()}
        busy={false}
        primary="#7C3AED"
        onCancel={() => setConsentOpen(false)}
        onConfirm={startJob}
      />
    </>
  );
};

const st = StyleSheet.create({
  openBtn: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 10, padding: 12, borderRadius: 12, borderWidth: 1.5, borderColor: '#DDD6FE', backgroundColor: '#FAF5FF' },
  openBtnTitle: { fontSize: 13.5, fontWeight: '800', color: '#6D28D9' },
  openBtnSub: { fontSize: 11, color: '#7C7A8C', marginTop: 2, lineHeight: 15 },
  overlay: { flex: 1, backgroundColor: '#00000066', alignItems: 'center', justifyContent: 'center', padding: 20 },
  card: { width: '100%', maxWidth: 540, backgroundColor: '#FFF', borderRadius: 16, padding: 20 },
  title: { fontSize: 16, fontWeight: '800', color: '#0F172A' },
  hint: { fontSize: 12, color: '#64748B', marginTop: 6, lineHeight: 17 },
  constraintNote: { flexDirection: 'row', alignItems: 'flex-start', gap: 6, backgroundColor: '#FFFBEB', borderWidth: 1, borderColor: '#FDE68A', borderRadius: 8, padding: 9, marginTop: 8 },
  constraintNoteTxt: { flex: 1, fontSize: 11.5, color: '#92400E', fontWeight: '600', lineHeight: 16 },
  fieldLabel: { fontSize: 12, fontWeight: '700', color: '#334155', marginTop: 12, marginBottom: 5 },
  input: { borderWidth: 1, borderColor: '#E2E8F0', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, color: '#0F172A' },
  pageChip: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 16, borderWidth: 1, borderColor: '#E2E8F0' },
  pageChipActive: { backgroundColor: '#7C3AED', borderColor: '#7C3AED' },
  pageChipText: { fontSize: 13, fontWeight: '700', color: '#475569' },
  pageChipTextActive: { color: '#FFF' },
  actions: { flexDirection: 'row', gap: 10, marginTop: 16 },
  cancelBtn: { flex: 1, paddingVertical: 12, borderRadius: 10, backgroundColor: '#F1F5F9', alignItems: 'center' },
  cancelText: { fontSize: 14, fontWeight: '700', color: '#475569' },
  primaryBtn: { flex: 2, paddingVertical: 12, borderRadius: 10, backgroundColor: '#7C3AED', alignItems: 'center' },
  primaryText: { fontSize: 14, fontWeight: '700', color: '#FFF' },
  btnDisabled: { opacity: 0.5 },
  // Hard-constraint escape hatch row — visually prominent so users notice
  // it BEFORE hitting Start, and read the explanation that toggles with the
  // checkbox state.
  constraintRow: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 10,
    padding: 12, borderRadius: 12, marginTop: 10,
    backgroundColor: '#F5F3FF', borderWidth: 1, borderColor: '#DDD6FE',
  },
  constraintTitle: { fontSize: 13, fontWeight: '800', color: '#4C1D95' },
  constraintHint: { fontSize: 11.5, color: '#5B21B6', marginTop: 2, lineHeight: 16 },
  progressLabel: { fontSize: 13.5, fontWeight: '600', color: '#0F172A', marginTop: 10, marginBottom: 8 },
  track: { height: 8, borderRadius: 4, backgroundColor: '#EDE9FE', overflow: 'hidden' },
  fill: { height: 8, borderRadius: 4, backgroundColor: '#7C3AED' },
  pctText: { fontSize: 12, fontWeight: '700', color: '#6D28D9', marginTop: 6 },
  factorRow: { flexDirection: 'row', alignItems: 'center', gap: 9, paddingVertical: 9, borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  checkbox: { width: 20, height: 20, borderRadius: 5, borderWidth: 1.5, borderColor: '#CBD5E1', alignItems: 'center', justifyContent: 'center' },
  checkboxOn: { backgroundColor: '#7C3AED', borderColor: '#7C3AED' },
  factorName: { fontSize: 13, fontWeight: '600', color: '#0F172A' },
  factorOff: { color: '#94A3B8', textDecorationLine: 'line-through' },
  factorMeta: { fontSize: 10.5, color: '#94A3B8', marginTop: 1 },
  prioBtn: { width: 26, height: 26, borderRadius: 7, borderWidth: 1, borderColor: '#E2E8F0', alignItems: 'center', justifyContent: 'center' },  // (deprecated — left in case future re-introduction; no longer referenced)
  prioText: { fontSize: 11, fontWeight: '800', color: '#64748B' },
});

export default DeepImport;
