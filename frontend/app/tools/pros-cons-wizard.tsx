/**
 * 8-Step Pros & Cons / SWOT Decision Framework Wizard.
 *
 * Walks the user through:
 *   1) List initial Direct Factors
 *   2) List Options + per-option Pros & Cons
 *   3) Promote Pros & Cons → Factors  (Cons get prefixed "SHOULD NOT - ")
 *   4) Manual de-dup / group as sub-factor
 *   5) Collapse/expand sub-factors
 *   6) Notation (Mandatory/Optional) + optional knock-out threshold
 *   7) Prioritisation (drag-reorder rank) + Std Rating + Assessment %  (cell value auto)
 *   8) Detailed Assessment (subjective/objective, improvable, gap, realistic rating, satisfaction)
 *   Final Decision Guidelines reference panel
 *
 *  Re-used by both Pros & Cons and SWOT through the `module` query param.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, KeyboardAvoidingView, Platform, Modal,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import api from '../../src/utils/api';
import { showAlert } from '../../src/utils/alert';

type Source = 'direct' | 'pro' | 'con';
interface Factor {
  id: string; name: string; expected_value?: string | null; unit?: string | null;
  source: Source; source_option_id?: string | null; parent_id?: string | null;
  notation: 'mandatory' | 'optional'; priority_rank: number; std_rating: number;
  factor_type: 'subjective' | 'objective'; improvable: 'y' | 'y_bf' | 'n';
  my_expectation?: string | null; others_expectations?: string | null; market_standard?: string | null;
  realistic_gap_pct: number; realistic_gap_value: number; realistic_rating?: number | null;
}
interface ProConItem { id: string; text: string; description?: string; importance: number; promoted_factor_id?: string | null; }
interface OptionT { id: string; name: string; description?: string; pros: ProConItem[]; cons: ProConItem[]; }
interface Cell { assessment_pct: number; cell_value: number; actual_value?: string | null; satisfaction_pct: number; improvement_pct: number; satisfaction_value: number; notes?: string | null; }
interface Rollup { option_id: string; joint_score: number; overall_satisfaction_pct: number; disqualified: boolean; disqualifying_factor_ids: string[]; rank_high_to_low: number | null; }
interface Config { mandatory_threshold_pct: number | null; max_improvement_period_months: number; std_gap: number; gap_bands?: Record<string, number>; }
interface Guideline { rank: number; rule: string; type: string; }
interface Analysis {
  id: string; title: string; context: string;
  options: OptionT[]; factors: Factor[];
  assessments: Record<string, Record<string, Cell>>;
  config: Config; current_step: number;
  rollups?: Rollup[];
}

const STEPS = [
  { n: 1, label: 'Factors' },
  { n: 2, label: 'Options' },
  { n: 3, label: 'Promote' },
  { n: 4, label: 'Group' },
  { n: 5, label: 'Review' },
  { n: 6, label: 'Mandatory' },
  { n: 7, label: 'Prioritise' },
  { n: 8, label: 'Assess' },
];

const COLORS = {
  primary: '#6366F1', primaryDark: '#4F46E5',
  pro: '#059669', con: '#DC2626', direct: '#0369A1',
  bg: '#F8FAFC', card: '#FFFFFF', border: '#E2E8F0',
  text: '#0F172A', textDim: '#64748B', warn: '#EA580C', ok: '#16A34A',
};

export default function ProsConsWizard() {
  const router = useRouter();
  const { id, module = 'pros-cons' } = useLocalSearchParams<{ id: string; module?: string }>();
  const base = module === 'swot' ? '/swot' : '/pros-cons';

  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState<number>(1);
  const [showGuidelines, setShowGuidelines] = useState(false);
  const [guidelines, setGuidelines] = useState<Guideline[]>([]);

  const load = useCallback(async () => {
    // -------------------------------------------------------------
    // No `id` in URL  ⇒  user landed here from "Pros & Cons (8-Step)"
    // / "SWOT (8-Step)" Quick-Action card on the home screen.
    // Auto-create a draft analysis, then bounce to the same wizard
    // URL with the new id so the rest of the flow works unchanged.
    // -------------------------------------------------------------
    if (!id) {
      try {
        const titlePrefix = module === 'swot' ? 'SWOT' : 'Pros & Cons';
        const now = new Date();
        const stamp = `${now.toLocaleDateString()} ${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
        const r = await api.post(base, {
          title: `${titlePrefix} draft — ${stamp}`,
          context: '',
          life_area: null,
        });
        const newId = r.data?.id;
        if (newId) {
          router.replace(`/tools/pros-cons-wizard?id=${newId}&module=${module}` as any);
          return; // useEffect will re-fire with the new id once URL changes
        }
        showAlert('Error', 'Could not create a new analysis. Please try again.');
        setLoading(false);
      } catch (e: any) {
        showAlert('Error', e?.response?.data?.detail || 'Failed to start new analysis');
        setLoading(false);
      }
      return;
    }
    try {
      const r = await api.get(`${base}/${id}`);
      setAnalysis(r.data);
      setStep(r.data?.current_step || 1);
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to load analysis');
    } finally { setLoading(false); }
  }, [id, base, module, router]);

  useEffect(() => { load(); }, [load]);

  const persistStep = async (n: number) => {
    setStep(n);
    if (id) { try { await api.post(`${base}/${id}/step`, { step: n }); } catch { /* non-fatal */ } }
  };

  const reload = async () => { await load(); };

  // ─── Step 1: Direct Factors ───────────────────────────────
  const [fName, setFName] = useState('');
  const [fExpected, setFExpected] = useState('');
  const [fUnit, setFUnit] = useState('');

  const addFactor = async () => {
    if (!fName.trim()) return;
    setBusy(true);
    try {
      await api.post(`${base}/${id}/factors`, {
        name: fName.trim(),
        expected_value: fExpected.trim() || null,
        unit: fUnit.trim() || null,
      });
      setFName(''); setFExpected(''); setFUnit('');
      await reload();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed');
    } finally { setBusy(false); }
  };

  const deleteFactor = async (fid: string) => {
    setBusy(true);
    try { await api.delete(`${base}/${id}/factors/${fid}`); await reload(); }
    finally { setBusy(false); }
  };

  const updateFactor = async (fid: string, patch: any) => {
    try { await api.put(`${base}/${id}/factors/${fid}`, patch); await reload(); }
    catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed'); }
  };

  // ─── Step 2: Options + Pros/Cons ──────────────────────────
  const [optName, setOptName] = useState('');
  const [activeOptId, setActiveOptId] = useState<string | null>(null);
  const [pcText, setPcText] = useState('');
  const [pcKind, setPcKind] = useState<'pro' | 'con'>('pro');

  const addOption = async () => {
    if (!optName.trim()) return;
    setBusy(true);
    try { await api.post(`${base}/${id}/options`, { name: optName.trim() }); setOptName(''); await reload(); }
    finally { setBusy(false); }
  };
  const deleteOption = async (oid: string) => {
    setBusy(true); try { await api.delete(`${base}/${id}/options/${oid}`); await reload(); } finally { setBusy(false); }
  };
  const addPC = async () => {
    if (!activeOptId || !pcText.trim()) return;
    setBusy(true);
    try {
      const path = pcKind === 'pro' ? 'pros' : 'cons';
      await api.post(`${base}/${id}/options/${activeOptId}/${path}`, { text: pcText.trim(), importance: 5 });
      setPcText('');
      await reload();
    } finally { setBusy(false); }
  };
  const delPC = async (oid: string, kind: 'pros' | 'cons', itemId: string) => {
    setBusy(true);
    try { await api.delete(`${base}/${id}/options/${oid}/${kind}/${itemId}`); await reload(); }
    finally { setBusy(false); }
  };

  // ─── Step 3: Promote ─────────────────────────────────────
  const promote = async () => {
    setBusy(true);
    try {
      const r = await api.post(`${base}/${id}/promote-pros-cons`);
      showAlert('Promoted', `${r.data.promoted_count} pros/cons converted to factors. (Total factors: ${r.data.total_factors})`);
      await reload();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed');
    } finally { setBusy(false); }
  };

  // ─── Step 6: Config + Notation ───────────────────────────
  const [threshold, setThreshold] = useState<string>('');
  useEffect(() => {
    if (analysis?.config?.mandatory_threshold_pct != null) {
      setThreshold(String(analysis.config.mandatory_threshold_pct));
    }
  }, [analysis?.config?.mandatory_threshold_pct]);

  const saveThreshold = async () => {
    const v = threshold.trim() === '' ? null : Math.max(0, Math.min(100, parseInt(threshold, 10) || 0));
    try { await api.put(`${base}/${id}/config`, { mandatory_threshold_pct: v }); await reload(); }
    catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed'); }
  };

  // ─── Step 7: Reorder + std_rating ────────────────────────
  const moveFactor = async (idx: number, dir: -1 | 1) => {
    if (!analysis) return;
    const list = [...analysis.factors];
    const j = idx + dir;
    if (j < 0 || j >= list.length) return;
    [list[idx], list[j]] = [list[j], list[idx]];
    try { await api.post(`${base}/${id}/factors/reorder`, { ordered_ids: list.map(f => f.id) }); await reload(); }
    catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Reorder failed'); }
  };

  // ─── Step 7+8: assessment cell update ────────────────────
  const upsertCell = async (oid: string, fid: string, patch: any) => {
    try { await api.put(`${base}/${id}/assessments/${oid}/${fid}`, patch); await reload(); }
    catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed'); }
  };

  // ─── Aggregate (Step 7.4 + 8.10 + Final Guidelines) ─────
  const runAggregate = async () => {
    setBusy(true);
    try {
      const r = await api.get(`${base}/${id}/aggregate`);
      setAnalysis(prev => prev ? { ...prev, rollups: r.data.rollups, factors: r.data.factors, options: r.data.options, config: r.data.config } : prev);
      setGuidelines(r.data.final_decision_guidelines || []);
    } finally { setBusy(false); }
  };
  useEffect(() => { if (step === 8 && analysis) runAggregate(); /* refresh on entering step 8 */ }, [step]);

  const rollupByOpt = useMemo(() => {
    const m: Record<string, Rollup> = {};
    (analysis?.rollups || []).forEach(r => { m[r.option_id] = r; });
    return m;
  }, [analysis?.rollups]);

  if (loading) {
    return (
      <SafeAreaView style={styles.center}><ActivityIndicator size="large" color={COLORS.primary} /></SafeAreaView>
    );
  }
  if (!analysis) {
    return (
      <SafeAreaView style={styles.center}><Text>Analysis not found.</Text></SafeAreaView>
    );
  }

  const directFactors = analysis.factors.filter(f => !f.parent_id);
  const childrenOf = (pid: string) => analysis.factors.filter(f => f.parent_id === pid);

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      {/* Header */}
      <LinearGradient colors={[COLORS.primary, COLORS.primaryDark]} style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.headerBtn}>
          <Ionicons name="chevron-back" size={22} color="#fff" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle} numberOfLines={1}>{analysis.title}</Text>
          <Text style={styles.headerSub}>{module === 'swot' ? 'SWOT' : 'Pros & Cons'} · 8-step framework</Text>
        </View>
        <TouchableOpacity onPress={() => setShowGuidelines(true)} style={styles.headerBtn}>
          <Ionicons name="bulb-outline" size={22} color="#fff" />
        </TouchableOpacity>
      </LinearGradient>

      {/* Step strip */}
      <View style={styles.stepStrip}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 8 }}>
          {STEPS.map(s => (
            <TouchableOpacity key={s.n} style={[styles.stepChip, step === s.n && styles.stepChipActive]}
              onPress={() => persistStep(s.n)}>
              <Text style={[styles.stepChipNum, step === s.n && { color: '#fff' }]}>{s.n}</Text>
              <Text style={[styles.stepChipLabel, step === s.n && { color: '#fff' }]}>{s.label}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.body}>

          {/* ────── STEP 1 ────── */}
          {step === 1 && (
            <View>
              <Text style={styles.stepTitle}>Step 1 — List initial Direct Factors</Text>
              <Text style={styles.stepHint}>Add factors that matter for this decision. Expected value &amp; unit are optional now — you can fill them once factors are finalised (Step 3 onwards).</Text>
              <View style={styles.card}>
                <Text style={styles.inputLabel}>Factor name</Text>
                <TextInput style={styles.input} placeholder="e.g., Mileage" value={fName} onChangeText={setFName} />
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  <View style={{ flex: 2 }}>
                    <Text style={styles.inputLabel}>Expected value (optional)</Text>
                    <TextInput style={styles.input} placeholder="e.g., 15" value={fExpected} onChangeText={setFExpected} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.inputLabel}>Unit</Text>
                    <TextInput style={styles.input} placeholder="kmpl" value={fUnit} onChangeText={setFUnit} />
                  </View>
                </View>
                <TouchableOpacity style={[styles.primaryBtn, !fName.trim() && { opacity: 0.5 }]}
                  disabled={!fName.trim() || busy} onPress={addFactor}>
                  <Ionicons name="add" size={18} color="#fff" />
                  <Text style={styles.primaryBtnText}>Add Direct Factor</Text>
                </TouchableOpacity>
              </View>

              <Text style={styles.sectionTitle}>Direct factors ({directFactors.filter(f => f.source === 'direct').length})</Text>
              {analysis.factors.filter(f => f.source === 'direct').map((f, i) => (
                <View key={f.id} style={styles.factorRow}>
                  <View style={[styles.sourceTag, { backgroundColor: COLORS.direct }]}><Text style={styles.sourceTagText}>D</Text></View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.factorName}>{f.name}</Text>
                    {!!(f.expected_value || f.unit) && (
                      <Text style={styles.factorMeta}>Expected: {f.expected_value || '—'} {f.unit || ''}</Text>
                    )}
                  </View>
                  <TouchableOpacity onPress={() => deleteFactor(f.id)}><Ionicons name="trash-outline" size={18} color={COLORS.con} /></TouchableOpacity>
                </View>
              ))}
              <NextBack onBack={null} onNext={() => persistStep(2)} />
            </View>
          )}

          {/* ────── STEP 2 ────── */}
          {step === 2 && (
            <View>
              <Text style={styles.stepTitle}>Step 2 — List Options &amp; their Pros / Cons</Text>
              <Text style={styles.stepHint}>Add each option (e.g., Car X, Car Y). Then tap an option to add Pros &amp; Cons specific to that option.</Text>
              <View style={styles.card}>
                <Text style={styles.inputLabel}>Option name</Text>
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  <TextInput style={[styles.input, { flex: 1 }]} placeholder="e.g., Car X" value={optName} onChangeText={setOptName} />
                  <TouchableOpacity style={[styles.primaryBtn, { flex: 0, paddingHorizontal: 16 }]} onPress={addOption} disabled={!optName.trim() || busy}>
                    <Ionicons name="add" size={18} color="#fff" />
                  </TouchableOpacity>
                </View>
              </View>

              {analysis.options.map((o) => (
                <View key={o.id} style={styles.optionCard}>
                  <View style={styles.optionHeader}>
                    <Text style={styles.optionName}>{o.name}</Text>
                    <TouchableOpacity onPress={() => deleteOption(o.id)}><Ionicons name="trash-outline" size={18} color={COLORS.con} /></TouchableOpacity>
                  </View>
                  {/* pros */}
                  <Text style={styles.pcSection}>Pros ({o.pros.length})</Text>
                  {o.pros.map(p => (
                    <View key={p.id} style={[styles.pcRow, { borderLeftColor: COLORS.pro }]}>
                      <Text style={styles.pcText}>{p.text}</Text>
                      <TouchableOpacity onPress={() => delPC(o.id, 'pros', p.id)}><Ionicons name="close-circle" size={18} color={COLORS.textDim} /></TouchableOpacity>
                    </View>
                  ))}
                  <Text style={styles.pcSection}>Cons ({o.cons.length})</Text>
                  {o.cons.map(c => (
                    <View key={c.id} style={[styles.pcRow, { borderLeftColor: COLORS.con }]}>
                      <Text style={styles.pcText}>{c.text}</Text>
                      <TouchableOpacity onPress={() => delPC(o.id, 'cons', c.id)}><Ionicons name="close-circle" size={18} color={COLORS.textDim} /></TouchableOpacity>
                    </View>
                  ))}
                  <View style={styles.addPcBar}>
                    <TouchableOpacity style={[styles.pcKindBtn, pcKind === 'pro' && activeOptId === o.id && { backgroundColor: COLORS.pro }]}
                      onPress={() => { setActiveOptId(o.id); setPcKind('pro'); }}>
                      <Text style={[styles.pcKindBtnText, pcKind === 'pro' && activeOptId === o.id && { color: '#fff' }]}>+ Pro</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={[styles.pcKindBtn, pcKind === 'con' && activeOptId === o.id && { backgroundColor: COLORS.con }]}
                      onPress={() => { setActiveOptId(o.id); setPcKind('con'); }}>
                      <Text style={[styles.pcKindBtnText, pcKind === 'con' && activeOptId === o.id && { color: '#fff' }]}>+ Con</Text>
                    </TouchableOpacity>
                    {activeOptId === o.id && (
                      <>
                        <TextInput style={[styles.input, { flex: 1, marginBottom: 0 }]}
                          placeholder={`Add ${pcKind === 'pro' ? 'Pro' : 'Con'} for ${o.name}`}
                          value={pcText} onChangeText={setPcText} />
                        <TouchableOpacity style={styles.miniBtn} onPress={addPC} disabled={!pcText.trim() || busy}>
                          <Ionicons name="checkmark" size={16} color="#fff" />
                        </TouchableOpacity>
                      </>
                    )}
                  </View>
                </View>
              ))}
              <NextBack onBack={() => persistStep(1)} onNext={() => persistStep(3)} />
            </View>
          )}

          {/* ────── STEP 3 ────── */}
          {step === 3 && (
            <View>
              <Text style={styles.stepTitle}>Step 3 — Promote Pros &amp; Cons → Factors</Text>
              <Text style={styles.stepHint}>One tap converts every Pro &amp; Con into a Factor. Cons are auto-prefixed with <Text style={{ fontWeight: '700' }}>“SHOULD NOT - ”</Text>. Already-promoted items are skipped (idempotent).</Text>
              <TouchableOpacity style={styles.bigCta} onPress={promote} disabled={busy}>
                <LinearGradient colors={[COLORS.primary, '#8B5CF6']} style={styles.bigCtaGrad}>
                  {busy ? <ActivityIndicator color="#fff" /> : (<>
                    <Ionicons name="flash" size={22} color="#fff" />
                    <Text style={styles.bigCtaText}>Auto-Promote all Pros &amp; Cons</Text>
                  </>)}
                </LinearGradient>
              </TouchableOpacity>

              <Text style={styles.sectionTitle}>All factors ({analysis.factors.length})</Text>
              {analysis.factors.map(f => (
                <View key={f.id} style={styles.factorRow}>
                  <View style={[styles.sourceTag, {
                    backgroundColor: f.source === 'direct' ? COLORS.direct : f.source === 'pro' ? COLORS.pro : COLORS.con
                  }]}>
                    <Text style={styles.sourceTagText}>{f.source === 'direct' ? 'D' : f.source === 'pro' ? 'P' : 'C'}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.factorName}>{f.name}</Text>
                    <Text style={styles.factorMeta}>{f.source === 'direct' ? 'Direct' : f.source === 'pro' ? 'From Pro' : 'From Con'}</Text>
                  </View>
                </View>
              ))}
              <NextBack onBack={() => persistStep(2)} onNext={() => persistStep(4)} />
            </View>
          )}

          {/* ────── STEP 4 ────── */}
          {step === 4 && (
            <View>
              <Text style={styles.stepTitle}>Step 4 — De-dup &amp; Group (sub-factors)</Text>
              <Text style={styles.stepHint}>Remove duplicate factors or tap “Group under…” to make a factor a sub-factor of an existing Direct factor.</Text>
              {analysis.factors.map((f, i) => (
                <FactorGroupRow key={f.id} factor={f} parentChoices={directFactors.filter(d => d.id !== f.id)}
                  onUpdate={(patch) => updateFactor(f.id, patch)}
                  onDelete={() => deleteFactor(f.id)} />
              ))}
              <NextBack onBack={() => persistStep(3)} onNext={() => persistStep(5)} />
            </View>
          )}

          {/* ────── STEP 5 ────── */}
          {step === 5 && (
            <View>
              <Text style={styles.stepTitle}>Step 5 — Review Factor Tree</Text>
              <Text style={styles.stepHint}>Direct factors with their sub-factors (collapsible). Sub-factor-level rating is reserved for a future release — rate at the parent level for now.</Text>
              {directFactors.map(f => (
                <FactorTreeNode key={f.id} factor={f} childrenList={childrenOf(f.id)} />
              ))}
              <NextBack onBack={() => persistStep(4)} onNext={() => persistStep(6)} />
            </View>
          )}

          {/* ────── STEP 6 ────── */}
          {step === 6 && (
            <View>
              <Text style={styles.stepTitle}>Step 6 — Mandatory / Optional + threshold</Text>
              <Text style={styles.stepHint}>Mark “must-have” factors as Mandatory. Optionally set a knock-out threshold % — any option scoring below this on a Mandatory factor is disqualified.</Text>

              <View style={styles.card}>
                <Text style={styles.inputLabel}>Knock-out threshold % (optional)</Text>
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  <TextInput style={[styles.input, { flex: 1 }]} placeholder="e.g., 60" keyboardType="number-pad"
                    value={threshold} onChangeText={setThreshold} />
                  <TouchableOpacity style={styles.miniBtn} onPress={saveThreshold}>
                    <Text style={{ color: '#fff', fontWeight: '700' }}>Save</Text>
                  </TouchableOpacity>
                </View>
              </View>

              {analysis.factors.map(f => (
                <View key={f.id} style={styles.factorRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.factorName}>{f.name}</Text>
                  </View>
                  {(['mandatory', 'optional'] as const).map(n => (
                    <TouchableOpacity key={n} style={[styles.notationBtn, f.notation === n && (n === 'mandatory' ? styles.notationMandActive : styles.notationOptActive)]}
                      onPress={() => updateFactor(f.id, { notation: n })}>
                      <Text style={[styles.notationBtnText, f.notation === n && { color: '#fff' }]}>{n === 'mandatory' ? 'A' : 'B'}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              ))}
              <NextBack onBack={() => persistStep(5)} onNext={() => persistStep(7)} />
            </View>
          )}

          {/* ────── STEP 7 ────── */}
          {step === 7 && (
            <View>
              <Text style={styles.stepTitle}>Step 7 — Prioritise &amp; Assess %</Text>
              <Text style={styles.stepHint}>Reorder by importance (▲▼). Set Standard Rating per factor. For each option, set Assessment %. Cell value = Assessment % × Std Rating.</Text>
              {analysis.factors.map((f, i) => (
                <View key={f.id} style={styles.factorCard}>
                  <View style={styles.factorCardHeader}>
                    <Text style={styles.rankBadge}>#{f.priority_rank}</Text>
                    <Text style={styles.factorName}>{f.name}</Text>
                    <View style={{ flexDirection: 'row', gap: 4 }}>
                      <TouchableOpacity onPress={() => moveFactor(i, -1)}><Ionicons name="chevron-up" size={20} color={COLORS.textDim} /></TouchableOpacity>
                      <TouchableOpacity onPress={() => moveFactor(i, 1)}><Ionicons name="chevron-down" size={20} color={COLORS.textDim} /></TouchableOpacity>
                    </View>
                  </View>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 6 }}>
                    <Text style={styles.cellLabel}>Std Rating</Text>
                    <TextInput style={[styles.inputSm, { width: 64 }]} keyboardType="number-pad"
                      defaultValue={String(f.std_rating)}
                      onEndEditing={(e) => updateFactor(f.id, { std_rating: Math.max(0, Math.min(100, parseInt(e.nativeEvent.text, 10) || 0)) })} />
                  </View>
                  {analysis.options.map(o => {
                    const cell = (analysis.assessments?.[o.id] || {})[f.id] || { assessment_pct: 0, cell_value: 0 };
                    return (
                      <View key={o.id} style={styles.assessRow}>
                        <Text style={styles.assessOpt} numberOfLines={1}>{o.name}</Text>
                        <Text style={styles.cellLabel}>Assess %</Text>
                        <TextInput style={[styles.inputSm, { width: 64 }]} keyboardType="number-pad"
                          defaultValue={String(cell.assessment_pct ?? 0)}
                          onEndEditing={(e) => upsertCell(o.id, f.id, { assessment_pct: Math.max(0, Math.min(100, parseInt(e.nativeEvent.text, 10) || 0)) })} />
                        <Text style={styles.cellValue}>= {cell.cell_value?.toFixed?.(1) ?? '0'}</Text>
                      </View>
                    );
                  })}
                </View>
              ))}
              <NextBack onBack={() => persistStep(6)} onNext={() => persistStep(8)} />
            </View>
          )}

          {/* ────── STEP 8 ────── */}
          {step === 8 && (
            <View>
              <Text style={styles.stepTitle}>Step 8 — Detailed Assessment &amp; Final Score</Text>
              <Text style={styles.stepHint}>Capture Subjective/Objective, Improvable, expectations, gap, actual value, satisfaction %. Overall satisfaction % per option is computed below.</Text>

              {/* Per-option overall card */}
              <View style={styles.card}>
                <Text style={styles.sectionTitle}>Overall satisfaction per option</Text>
                {analysis.options.map(o => {
                  const r = rollupByOpt[o.id];
                  return (
                    <View key={o.id} style={styles.overallRow}>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.factorName}>{o.name}</Text>
                        {r?.disqualified ? (
                          <Text style={{ color: COLORS.con, fontSize: 12 }}>Disqualified (Mandatory factor below threshold)</Text>
                        ) : r?.rank_high_to_low ? (
                          <Text style={{ color: COLORS.ok, fontSize: 12 }}>Rank #{r.rank_high_to_low}</Text>
                        ) : null}
                      </View>
                      <View style={{ alignItems: 'flex-end' }}>
                        <Text style={styles.overallPct}>{r ? r.overall_satisfaction_pct.toFixed(1) : '0'}%</Text>
                        <Text style={styles.cellLabel}>Joint: {r ? r.joint_score.toFixed(0) : '0'}</Text>
                      </View>
                    </View>
                  );
                })}
                <TouchableOpacity style={[styles.primaryBtn, { marginTop: 12 }]} onPress={runAggregate}>
                  <Ionicons name="refresh" size={16} color="#fff" />
                  <Text style={styles.primaryBtnText}>Recompute</Text>
                </TouchableOpacity>
              </View>

              {/* Per-factor detail */}
              {analysis.factors.map(f => (
                <FactorAssessmentCard key={f.id} factor={f} options={analysis.options}
                  cells={(analysis.assessments || {})}
                  onFactorUpdate={(patch) => updateFactor(f.id, patch)}
                  onCellUpdate={(oid, patch) => upsertCell(oid, f.id, patch)} />
              ))}

              <TouchableOpacity style={[styles.bigCta, { marginTop: 16 }]} onPress={() => setShowGuidelines(true)}>
                <LinearGradient colors={['#0ea5e9', '#6366F1']} style={styles.bigCtaGrad}>
                  <Ionicons name="bulb" size={22} color="#fff" />
                  <Text style={styles.bigCtaText}>Show Final Decision Guidelines</Text>
                </LinearGradient>
              </TouchableOpacity>
              <NextBack onBack={() => persistStep(7)} onNext={null} />
            </View>
          )}

        </ScrollView>
      </KeyboardAvoidingView>

      {/* Final Decision Guidelines modal */}
      <Modal visible={showGuidelines} animationType="slide" transparent onRequestClose={() => setShowGuidelines(false)}>
        <View style={styles.modalBg}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Final Decision Guidelines</Text>
              <TouchableOpacity onPress={() => setShowGuidelines(false)}><Ionicons name="close" size={22} color={COLORS.text} /></TouchableOpacity>
            </View>
            <Text style={styles.stepHint}>Reference checklist — use these when two options are close in overall %.</Text>
            <ScrollView style={{ maxHeight: 480 }}>
              {(guidelines.length ? guidelines : []).map(g => (
                <View key={g.rank} style={styles.gRow}>
                  <Text style={styles.gRank}>{g.rank}</Text>
                  <Text style={styles.gRule}>{g.rule}</Text>
                </View>
              ))}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

// ────────── Sub-components ──────────
function NextBack({ onBack, onNext }: { onBack: (() => void) | null; onNext: (() => void) | null }) {
  return (
    <View style={styles.navBar}>
      <TouchableOpacity style={[styles.navBtn, !onBack && { opacity: 0.3 }]} onPress={() => onBack?.()} disabled={!onBack}>
        <Ionicons name="chevron-back" size={18} color={COLORS.text} />
        <Text style={styles.navBtnText}>Back</Text>
      </TouchableOpacity>
      <TouchableOpacity style={[styles.navBtnPrimary, !onNext && { opacity: 0.3 }]} onPress={() => onNext?.()} disabled={!onNext}>
        <Text style={[styles.navBtnText, { color: '#fff' }]}>Next</Text>
        <Ionicons name="chevron-forward" size={18} color="#fff" />
      </TouchableOpacity>
    </View>
  );
}

function FactorGroupRow({ factor, parentChoices, onUpdate, onDelete }: {
  factor: Factor; parentChoices: Factor[]; onUpdate: (p: any) => void; onDelete: () => void;
}) {
  const [open, setOpen] = useState(false);
  const parent = parentChoices.find(p => p.id === factor.parent_id);
  return (
    <View style={styles.factorRow}>
      <View style={[styles.sourceTag, { backgroundColor: factor.source === 'direct' ? COLORS.direct : factor.source === 'pro' ? COLORS.pro : COLORS.con }]}>
        <Text style={styles.sourceTagText}>{factor.source === 'direct' ? 'D' : factor.source === 'pro' ? 'P' : 'C'}</Text>
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.factorName}>{factor.name}</Text>
        {parent && <Text style={styles.factorMeta}>↳ sub-factor of: {parent.name}</Text>}
      </View>
      <TouchableOpacity onPress={() => setOpen(o => !o)} style={styles.linkBtn}>
        <Text style={styles.linkBtnText}>{factor.parent_id ? 'Move' : 'Group ↳'}</Text>
      </TouchableOpacity>
      <TouchableOpacity onPress={onDelete}><Ionicons name="trash-outline" size={18} color={COLORS.con} /></TouchableOpacity>
      {open && (
        <View style={{ width: '100%', marginTop: 8, flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          <TouchableOpacity style={[styles.parentChip, !factor.parent_id && styles.parentChipActive]} onPress={() => { onUpdate({ parent_id: null }); setOpen(false); }}>
            <Text style={[styles.parentChipText, !factor.parent_id && { color: '#fff' }]}>None</Text>
          </TouchableOpacity>
          {parentChoices.map(p => (
            <TouchableOpacity key={p.id} style={[styles.parentChip, factor.parent_id === p.id && styles.parentChipActive]}
              onPress={() => { onUpdate({ parent_id: p.id }); setOpen(false); }}>
              <Text style={[styles.parentChipText, factor.parent_id === p.id && { color: '#fff' }]} numberOfLines={1}>{p.name}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}
    </View>
  );
}

function FactorTreeNode({ factor, childrenList }: { factor: Factor; childrenList: Factor[] }) {
  const [open, setOpen] = useState(true);
  return (
    <View style={styles.treeNode}>
      <TouchableOpacity style={styles.treeHead} onPress={() => setOpen(o => !o)}>
        <Ionicons name={open ? 'chevron-down' : 'chevron-forward'} size={18} color={COLORS.textDim} />
        <Text style={[styles.factorName, { flex: 1 }]}>{factor.name}</Text>
        <Text style={styles.factorMeta}>{childrenList.length} sub</Text>
      </TouchableOpacity>
      {open && childrenList.map(c => (
        <View key={c.id} style={styles.treeChild}>
          <View style={[styles.sourceTag, { backgroundColor: c.source === 'pro' ? COLORS.pro : c.source === 'con' ? COLORS.con : COLORS.direct }]}>
            <Text style={styles.sourceTagText}>{c.source === 'direct' ? 'D' : c.source === 'pro' ? 'P' : 'C'}</Text>
          </View>
          <Text style={[styles.factorName, { flex: 1 }]}>{c.name}</Text>
        </View>
      ))}
    </View>
  );
}

function FactorAssessmentCard({ factor, options, cells, onFactorUpdate, onCellUpdate }: {
  factor: Factor; options: OptionT[]; cells: Record<string, Record<string, Cell>>;
  onFactorUpdate: (p: any) => void; onCellUpdate: (oid: string, p: any) => void;
}) {
  return (
    <View style={styles.factorCard}>
      <View style={styles.factorCardHeader}>
        <Text style={styles.rankBadge}>#{factor.priority_rank}</Text>
        <Text style={[styles.factorName, { flex: 1 }]}>{factor.name}</Text>
      </View>

      {/* Type & Improvable */}
      <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap', marginVertical: 6 }}>
        {(['subjective', 'objective'] as const).map(t => (
          <TouchableOpacity key={t} style={[styles.tinyChip, factor.factor_type === t && styles.tinyChipOn]}
            onPress={() => onFactorUpdate({ factor_type: t })}>
            <Text style={[styles.tinyChipText, factor.factor_type === t && { color: '#fff' }]}>{t[0].toUpperCase() + t.slice(1)}</Text>
          </TouchableOpacity>
        ))}
        {(['n', 'y', 'y_bf'] as const).map(im => (
          <TouchableOpacity key={im} style={[styles.tinyChip, factor.improvable === im && styles.tinyChipOn]}
            onPress={() => onFactorUpdate({ improvable: im })}>
            <Text style={[styles.tinyChipText, factor.improvable === im && { color: '#fff' }]}>
              {im === 'n' ? 'Not improvable' : im === 'y' ? 'Improvable' : 'Improvable (self)'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Expectations / market */}
      <View style={{ flexDirection: 'row', gap: 6 }}>
        <TextInput style={[styles.inputSm, { flex: 1 }]} placeholder="My expectation"
          defaultValue={factor.my_expectation || ''}
          onEndEditing={e => onFactorUpdate({ my_expectation: e.nativeEvent.text })} />
        <TextInput style={[styles.inputSm, { flex: 1 }]} placeholder="Others'"
          defaultValue={factor.others_expectations || ''}
          onEndEditing={e => onFactorUpdate({ others_expectations: e.nativeEvent.text })} />
        <TextInput style={[styles.inputSm, { flex: 1 }]} placeholder="Market std"
          defaultValue={factor.market_standard || ''}
          onEndEditing={e => onFactorUpdate({ market_standard: e.nativeEvent.text })} />
      </View>

      {/* Gap & rating */}
      <View style={{ flexDirection: 'row', gap: 6, marginTop: 6, alignItems: 'center' }}>
        <Text style={styles.cellLabel}>Std</Text>
        <TextInput style={[styles.inputSm, { width: 56 }]} keyboardType="number-pad"
          defaultValue={String(factor.std_rating)}
          onEndEditing={e => onFactorUpdate({ std_rating: parseInt(e.nativeEvent.text, 10) || 0 })} />
        <Text style={styles.cellLabel}>Gap %</Text>
        <TextInput style={[styles.inputSm, { width: 56 }]} keyboardType="decimal-pad"
          defaultValue={String(factor.realistic_gap_pct ?? 0)}
          onEndEditing={e => onFactorUpdate({ realistic_gap_pct: parseFloat(e.nativeEvent.text) || 0 })} />
        <Text style={styles.cellLabel}>Realistic</Text>
        <Text style={[styles.cellValue, { width: 40 }]}>{factor.realistic_rating ?? factor.std_rating}</Text>
      </View>

      {/* Per-option assessment */}
      {options.map(o => {
        const c = (cells[o.id] || {})[factor.id] || { assessment_pct: 0, satisfaction_pct: 0, cell_value: 0, satisfaction_value: 0 };
        return (
          <View key={o.id} style={styles.assessRow}>
            <Text style={styles.assessOpt} numberOfLines={1}>{o.name}</Text>
            <TextInput style={[styles.inputSm, { width: 80 }]} placeholder="Actual"
              defaultValue={c.actual_value || ''}
              onEndEditing={e => onCellUpdate(o.id, { actual_value: e.nativeEvent.text })} />
            <Text style={styles.cellLabel}>Sat</Text>
            <TextInput style={[styles.inputSm, { width: 56 }]} keyboardType="decimal-pad"
              defaultValue={String(c.satisfaction_pct ?? 0)}
              onEndEditing={e => onCellUpdate(o.id, { satisfaction_pct: parseFloat(e.nativeEvent.text) || 0 })} />
            <Text style={styles.cellValue}>= {c.satisfaction_value?.toFixed?.(1) ?? '0'}</Text>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.bg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  header: { paddingHorizontal: 12, paddingVertical: 12, flexDirection: 'row', alignItems: 'center', gap: 8 },
  headerBtn: { padding: 6 },
  headerTitle: { color: '#fff', fontSize: 17, fontWeight: '700' },
  headerSub: { color: 'rgba(255,255,255,0.85)', fontSize: 12, marginTop: 2 },
  stepStrip: { backgroundColor: '#fff', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  stepChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 16, backgroundColor: COLORS.bg, marginHorizontal: 3, borderWidth: 1, borderColor: COLORS.border },
  stepChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  stepChipNum: { fontWeight: '700', fontSize: 12, color: COLORS.text, width: 14, textAlign: 'center' },
  stepChipLabel: { fontSize: 12, color: COLORS.textDim },
  body: { padding: 12, paddingBottom: 60 },
  stepTitle: { fontSize: 18, fontWeight: '800', color: COLORS.text, marginBottom: 4 },
  stepHint: { fontSize: 12, color: COLORS.textDim, marginBottom: 12, lineHeight: 18 },
  sectionTitle: { fontSize: 14, fontWeight: '700', color: COLORS.text, marginTop: 14, marginBottom: 6 },
  card: { backgroundColor: COLORS.card, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: COLORS.border, marginBottom: 12 },
  inputLabel: { fontSize: 12, color: COLORS.textDim, marginTop: 6, marginBottom: 4 },
  input: { backgroundColor: '#fff', borderWidth: 1, borderColor: COLORS.border, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8, fontSize: 14, color: COLORS.text, marginBottom: 8 },
  inputSm: { backgroundColor: '#fff', borderWidth: 1, borderColor: COLORS.border, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 4, fontSize: 12, color: COLORS.text, textAlign: 'center' },
  primaryBtn: { backgroundColor: COLORS.primary, paddingVertical: 10, paddingHorizontal: 14, borderRadius: 8, alignItems: 'center', flexDirection: 'row', gap: 6, alignSelf: 'flex-start' },
  primaryBtnText: { color: '#fff', fontWeight: '700', fontSize: 13 },
  factorRow: { backgroundColor: '#fff', flexDirection: 'row', alignItems: 'center', padding: 10, borderRadius: 8, marginBottom: 6, gap: 8, borderWidth: 1, borderColor: COLORS.border, flexWrap: 'wrap' },
  sourceTag: { width: 24, height: 24, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  sourceTagText: { color: '#fff', fontSize: 11, fontWeight: '800' },
  factorName: { fontSize: 14, fontWeight: '600', color: COLORS.text },
  factorMeta: { fontSize: 11, color: COLORS.textDim, marginTop: 2 },
  optionCard: { backgroundColor: '#fff', borderRadius: 12, padding: 10, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  optionHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 },
  optionName: { fontSize: 15, fontWeight: '700', color: COLORS.text },
  pcSection: { fontSize: 12, fontWeight: '600', color: COLORS.textDim, marginTop: 6 },
  pcRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 8, marginVertical: 2, backgroundColor: COLORS.bg, borderLeftWidth: 3, borderRadius: 4 },
  pcText: { flex: 1, fontSize: 13, color: COLORS.text },
  addPcBar: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8 },
  pcKindBtn: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 6, backgroundColor: COLORS.bg, borderWidth: 1, borderColor: COLORS.border },
  pcKindBtnText: { fontSize: 12, fontWeight: '700', color: COLORS.text },
  miniBtn: { backgroundColor: COLORS.primary, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 6, alignItems: 'center', justifyContent: 'center' },
  bigCta: { borderRadius: 12, overflow: 'hidden', marginVertical: 6 },
  bigCtaGrad: { paddingVertical: 14, alignItems: 'center', flexDirection: 'row', justifyContent: 'center', gap: 8 },
  bigCtaText: { color: '#fff', fontWeight: '800', fontSize: 15 },
  linkBtn: { paddingHorizontal: 8, paddingVertical: 4, backgroundColor: COLORS.bg, borderRadius: 6, borderWidth: 1, borderColor: COLORS.border },
  linkBtnText: { fontSize: 11, color: COLORS.text, fontWeight: '600' },
  parentChip: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12, backgroundColor: COLORS.bg, borderWidth: 1, borderColor: COLORS.border, maxWidth: 160 },
  parentChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  parentChipText: { fontSize: 11, color: COLORS.text },
  treeNode: { backgroundColor: '#fff', borderRadius: 8, marginBottom: 6, padding: 8, borderWidth: 1, borderColor: COLORS.border },
  treeHead: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  treeChild: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingLeft: 24, paddingTop: 4 },
  notationBtn: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 6, backgroundColor: COLORS.bg, borderWidth: 1, borderColor: COLORS.border, marginLeft: 4 },
  notationMandActive: { backgroundColor: COLORS.warn, borderColor: COLORS.warn },
  notationOptActive: { backgroundColor: COLORS.textDim, borderColor: COLORS.textDim },
  notationBtnText: { fontSize: 12, fontWeight: '800', color: COLORS.text },
  factorCard: { backgroundColor: '#fff', borderRadius: 10, padding: 10, marginBottom: 10, borderWidth: 1, borderColor: COLORS.border },
  factorCardHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  rankBadge: { backgroundColor: COLORS.primary, color: '#fff', fontSize: 12, fontWeight: '800', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6, overflow: 'hidden' },
  assessRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 6, flexWrap: 'wrap' },
  assessOpt: { fontSize: 12, color: COLORS.text, fontWeight: '600', width: 80 },
  cellLabel: { fontSize: 11, color: COLORS.textDim },
  cellValue: { fontSize: 12, color: COLORS.text, fontWeight: '700', minWidth: 36 },
  overallRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  overallPct: { fontSize: 18, fontWeight: '800', color: COLORS.primary },
  tinyChip: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12, backgroundColor: COLORS.bg, borderWidth: 1, borderColor: COLORS.border },
  tinyChipOn: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  tinyChipText: { fontSize: 11, color: COLORS.text, fontWeight: '600' },
  navBar: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 16 },
  navBtn: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingVertical: 10, borderRadius: 8, backgroundColor: COLORS.card, borderWidth: 1, borderColor: COLORS.border, gap: 4 },
  navBtnPrimary: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingVertical: 10, borderRadius: 8, backgroundColor: COLORS.primary, gap: 4 },
  navBtnText: { fontSize: 13, fontWeight: '700', color: COLORS.text },
  modalBg: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  modalCard: { backgroundColor: '#fff', borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 16, maxHeight: '85%' },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  modalTitle: { fontSize: 17, fontWeight: '800', color: COLORS.text },
  gRow: { flexDirection: 'row', gap: 10, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  gRank: { fontSize: 13, fontWeight: '800', color: COLORS.primary, width: 24 },
  gRule: { flex: 1, fontSize: 13, color: COLORS.text, lineHeight: 18 },
});
