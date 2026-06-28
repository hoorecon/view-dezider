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
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, KeyboardAvoidingView, Platform, Modal,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import api from '../../src/utils/api';
import ModuleStoreActions from '../../src/components/ModuleStoreActions';
import ActionItemEditor from '../../src/components/ActionItemEditor';
import { showAlert } from '../../src/utils/alert';
import { downloadAssessmentTemplate, importAssessmentTemplate } from '../../src/utils/assessmentXlsx';
import { createAssessmentGsheet, importAssessmentGsheet, openSheetUrl } from '../../src/utils/googleSheets';
import { safeBack, goHome } from '../../src/utils/navigation';
import AiCreditsBadge from '../../src/components/AiCreditsBadge';
import { useAiWalletStore } from '../../src/store/aiWalletStore';
import { DECISION_TYPES } from '../../src/constants/decisionTypes';
// ── Extracted modules (refactor: split from the former 3.8k-line monolith) ──
import { Factor, OptionT, Rollup, Guideline, Analysis } from '../../src/features/pros-cons/types';
import { STEPS, LIFE_AREAS, COLORS } from '../../src/features/pros-cons/constants';
import { styles, pcAssess } from '../../src/features/pros-cons/styles';
import { CollabBar } from '../../src/components/CollabBar';
import LiveSessionPill from '../../src/components/LiveSessionPill';
import { DecisionContinuePanel } from '../../src/components/DecisionContinuePanel';
import {
  DebouncedInput, NextBack, FactorGroupRow, DataSourceModal, FactorTreeNode,
  FactorAssessmentCard, MainFactorWithSubs, SubFactorEditableList, LmhAiButtons,
} from '../../src/features/pros-cons/components';

export default function ProsConsWizard() {
  const router = useRouter();
  const refreshAiWallet = useAiWalletStore((s) => s.refresh);
  const { id, module = 'pros-cons', contribShareId, contribStep, access } = useLocalSearchParams<{ id: string; module?: string; contribShareId?: string; contribStep?: string; access?: string }>();
  const base = module === 'swot' ? '/swot' : '/pros-cons';
  // Contribution Mode: contributor edits their sandbox clone, scoped to one step.
  const contributionMode = !!contribShareId;
  const contribStepNum = parseInt(String(contribStep || '0'), 10) || 0;
  const stepAccess = String(access || 'hidden');
  const [submittingContribution, setSubmittingContribution] = useState(false);

  const submitContribution = async () => {
    setSubmittingContribution(true);
    try {
      await api.post(`/shared-steps/${contribShareId}/contribute`, { note: '' });
      showAlert('Contribution submitted ✓', 'Your input has been sent to the owner to review and merge.');
      router.replace('/inbox');
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Could not submit your contribution');
    } finally {
      setSubmittingContribution(false);
    }
  };

  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState<number>(1);
  const [showGuidelines, setShowGuidelines] = useState(false);
  const [guidelines, setGuidelines] = useState<Guideline[]>([]);
  // Bumped to remount the Step-8 Action Plan editor after the MPPS auto-import.
  const [pcActionKey, setPcActionKey] = useState(0);
  // One-shot guard for the partner-embed option pre-seed.
  const embedSeededRef = useRef(false);

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

      // ── Partner-embed pre-seed (pros_cons) ──────────────────────────────
      // Carried-over comparison options from /embed were stashed in
      // AsyncStorage('embed_seed'). Drop them in as Options once, on a fresh
      // analysis, then clear the seed. Only touches pros_cons seeds.
      if (!embedSeededRef.current && module === 'pros-cons') {
        embedSeededRef.current = true;
        try {
          const raw = await AsyncStorage.getItem('embed_seed');
          if (raw) {
            const seed = JSON.parse(raw);
            if (seed && seed.flow === 'pros_cons') {
              const stale = Date.now() - (seed.ts || 0) > 2 * 3600 * 1000;
              const names: string[] = stale
                ? []
                : (seed.options || [])
                    .map((o: any) => (typeof o === 'string' ? o : o?.name))
                    .filter((n: any) => !!n && String(n).trim());
              if (names.length && (r.data?.options || []).length === 0) {
                const seen = new Set<string>();
                for (const n of names) {
                  const k = String(n).trim().toLowerCase();
                  if (!k || seen.has(k)) continue;
                  seen.add(k);
                  try { await api.post(`${base}/${id}/options`, { name: String(n).trim() }); } catch { /* skip */ }
                }
                await AsyncStorage.removeItem('embed_seed');
                const r2 = await api.get(`${base}/${id}`);
                setAnalysis(r2.data);
                setStep(2); // List Options + Pros & Cons
              } else {
                await AsyncStorage.removeItem('embed_seed');
              }
            }
          }
        } catch { /* non-fatal */ }
      }
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to load analysis');
    } finally { setLoading(false); }
  }, [id, base, module, router]);

  useEffect(() => { load(); }, [load]);

  // Contribution Mode: land on the requested step once the analysis is loaded.
  const contribJumpedRef = useRef(false);
  useEffect(() => {
    if (contributionMode && analysis && contribStepNum && !contribJumpedRef.current) {
      contribJumpedRef.current = true;
      setStep(contribStepNum);
    }
  }, [contributionMode, analysis, contribStepNum]);

  const persistStep = async (n: number) => {
    setStep(n);
    if (id) { try { await api.post(`${base}/${id}/step`, { step: n }); } catch { /* non-fatal */ } }
  };

  const reload = async () => { await load(); };

  // ─── Step 1: Direct Factors ───────────────────────────────
  const [fName, setFName] = useState('');

  // ─── Basics (Decision/Topic, Description, Life Area) ─────
  // These appear in a collapsible card at the top of Step 1 so the user
  // can review/edit the same info they would have entered in the "new"
  // modal on the Pros & Cons list. Auto-saved on blur via PUT.
  const [basicsOpen, setBasicsOpen] = useState(true);
  const [bTitle, setBTitle] = useState('');
  const [bContext, setBContext] = useState('');
  const [bLifeArea, setBLifeArea] = useState<string>('');
  const [bDecisionType, setBDecisionType] = useState<string>('');

  // Sync local basics when analysis loads / changes id
  useEffect(() => {
    if (analysis) {
      setBTitle(analysis.title || '');
      setBContext(analysis.context || '');
      setBLifeArea(analysis.life_area || '');
      setBDecisionType((analysis as any).decision_type || '');
    }
  }, [analysis?.id]);  // eslint-disable-line react-hooks/exhaustive-deps

  const saveBasics = async (patch: { title?: string; context?: string; life_area?: string | null; decision_type?: string }) => {
    if (!id) return;
    try {
      await api.put(`${base}/${id}`, patch);
      // Update local state without a full reload (avoids losing input focus mid-typing)
      setAnalysis((prev) => prev ? { ...prev, ...patch } as Analysis : prev);
    } catch (e: any) {
      // Non-fatal; log only
      console.warn('Failed to save basics', e?.response?.data?.detail || e?.message);
    }
  };

  const addFactor = async () => {
    if (!fName.trim()) return;
    const t = fName.trim();
    if ((analysis?.factors || []).some(f => !f.parent_id && (f.name || '').trim().toLowerCase() === t.toLowerCase())) {
      showAlert('Duplicate entry', `“${t}” is already listed as a factor. Please add a different one.`);
      return;
    }
    setBusy(true);
    try {
      await api.post(`${base}/${id}/factors`, { name: t });
      setFName('');
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

  /**
   * Step-4 helper: create a brand-new factor that is already nested under
   * `parentId`. Used by the "+ Type new sub-factor name…" input inside the
   * FactorGroupRow picker, so the user can grow the factor tree without
   * having to first add the factor as a top-level row in Step 1.
   */
  const createSubFactor = async (parentId: string, name: string) => {
    const n = (name || '').trim();
    if (!n) { showAlert('Required', 'Sub-factor name cannot be empty.'); return; }
    try {
      await api.post(`${base}/${id}/factors`, { name: n, parent_id: parentId });
      await reload();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to add sub-factor');
    }
  };

  /**
   * Step-5 helper: create a new sub-factor under `parentId` with a sensible
   * default name (the user renames it inline via the pencil). Used by the
   * "+ Add sub-factor" button inside FactorTreeNode so users can grow the
   * tree directly in Step 5 — parity with My Dezider Step 2.
   */
  const addSubFactorQuick = async (parentId: string) => {
    const existing = analysis?.factors.filter(f => f.parent_id === parentId && !f.is_duplicate).length || 0;
    const parent = analysis?.factors.find(f => f.id === parentId);
    const defaultName = `${(parent?.display_name || parent?.name || 'Factor')} — Part ${existing + 1}`;
    try {
      await api.post(`${base}/${id}/factors`, { name: defaultName, parent_id: parentId });
      await reload();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to add sub-factor');
    }
  };

  // ─── Step 5: Data Source modal (Auto-Fetch parity with My Dezider) ───
  const [dsFactor, setDsFactor] = useState<Factor | null>(null);

  // ─── Inline-edit state for factors and options ─────────────
  // Track which factor / option is currently in "edit" mode and the
  // working copy of its fields so the user can cancel without saving.
  const [editingFactorId, setEditingFactorId] = useState<string | null>(null);
  const [editFactorName, setEditFactorName] = useState('');

  const beginEditFactor = (f: Factor) => {
    setEditingFactorId(f.id);
    setEditFactorName(f.name || '');
  };
  const cancelEditFactor = () => { setEditingFactorId(null); };
  const saveEditFactor = async () => {
    if (!editingFactorId) return;
    const name = editFactorName.trim();
    if (!name) { showAlert('Required', 'Factor name cannot be empty.'); return; }
    await updateFactor(editingFactorId, { name });
    setEditingFactorId(null);
  };

  const confirmDeleteFactor = (f: Factor) => {
    showAlert('Delete factor?', `“${f.name}” will be permanently removed from this analysis.`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => deleteFactor(f.id) },
    ]);
  };

  // ─── Step 2: Options + Pros/Cons ──────────────────────────
  const [optName, setOptName] = useState('');
  const [activeOptId, setActiveOptId] = useState<string | null>(null);
  const [pcText, setPcText] = useState('');
  const [pcKind, setPcKind] = useState<'pro' | 'con'>('pro');

  // Inline-edit for individual Pros / Cons text (parity with Option rename)
  const [editingPcKey, setEditingPcKey] = useState<string | null>(null);  // `${oid}:${kind}:${pcid}`
  const [editPcDraft, setEditPcDraft] = useState('');
  const beginEditPc = (oid: string, kind: 'pros' | 'cons', pc: { id: string; text: string }) => {
    setEditingPcKey(`${oid}:${kind}:${pc.id}`);
    setEditPcDraft(pc.text || '');
  };
  const cancelEditPc = () => { setEditingPcKey(null); };
  const saveEditPc = async () => {
    if (!editingPcKey) return;
    const [oid, kind, pcid] = editingPcKey.split(':');
    const text = editPcDraft.trim();
    if (!text) { showAlert('Required', 'Text cannot be empty.'); return; }
    try {
      await api.put(`${base}/${id}/options/${oid}/${kind}/${pcid}`, { text });
      setEditingPcKey(null);
      await reload();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to update');
    }
  };

  // Per-option collapsible state — by default everything is OPEN.
  // Tracking which IDs are EXPLICITLY collapsed (not a "open set") so
  // newly-added options auto-open.
  const [collapsedOptIds, setCollapsedOptIds] = useState<Set<string>>(new Set());
  const [collapsedProsIds, setCollapsedProsIds] = useState<Set<string>>(new Set());
  const [collapsedConsIds, setCollapsedConsIds] = useState<Set<string>>(new Set());

  // Step 7: per-factor expand for assessment. Default = ALL COLLAPSED so the
  // user gets a compact, glanceable list to re-prioritize. Expanding a card
  // (or tapping "Assess all") reveals the per-option Satisfaction % inputs.
  const [step7ExpandedIds, setStep7ExpandedIds] = useState<Set<string>>(new Set());
  const toggleStep7Expand = (fid: string) => {
    setStep7ExpandedIds((prev) => {
      const n = new Set(prev);
      if (n.has(fid)) n.delete(fid); else n.add(fid);
      return n;
    });
  };
  const toggleOptCollapsed = (oid: string) => {
    setCollapsedOptIds((s) => {
      const n = new Set(s);
      if (n.has(oid)) n.delete(oid); else n.add(oid);
      return n;
    });
  };
  const toggleProsCollapsed = (oid: string) => {
    setCollapsedProsIds((s) => {
      const n = new Set(s);
      if (n.has(oid)) n.delete(oid); else n.add(oid);
      return n;
    });
  };
  const toggleConsCollapsed = (oid: string) => {
    setCollapsedConsIds((s) => {
      const n = new Set(s);
      if (n.has(oid)) n.delete(oid); else n.add(oid);
      return n;
    });
  };

  // Inline rename for options
  const [editingOptId, setEditingOptId] = useState<string | null>(null);
  const [editOptName, setEditOptName] = useState('');
  const beginEditOption = (o: OptionT) => {
    setEditingOptId(o.id);
    setEditOptName(o.name || '');
  };
  const cancelEditOption = () => setEditingOptId(null);
  const saveEditOption = async () => {
    if (!editingOptId) return;
    const name = editOptName.trim();
    if (!name) { showAlert('Required', 'Option name cannot be empty.'); return; }
    try {
      await api.put(`${base}/${id}/options/${editingOptId}`, { name });
      setEditingOptId(null);
      await reload();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to rename option');
    }
  };
  const confirmDeleteOption = (o: OptionT) => {
    const total = (o.pros?.length || 0) + (o.cons?.length || 0);
    const msg = total > 0
      ? `“${o.name}” and its ${o.pros.length} Pros + ${o.cons.length} Cons will be removed.`
      : `“${o.name}” will be removed.`;
    showAlert('Delete option?', msg, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => deleteOption(o.id) },
    ]);
  };

  const addOption = async () => {
    if (!optName.trim()) return;
    const t = optName.trim();
    if ((analysis?.options || []).some(o => (o.name || '').trim().toLowerCase() === t.toLowerCase())) {
      showAlert('Duplicate entry', `“${t}” is already one of your options. Please add a different one.`);
      return;
    }
    setBusy(true);
    try { await api.post(`${base}/${id}/options`, { name: t }); setOptName(''); await reload(); }
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

  /**
   * Step 7 — reorder MAIN factors only (the user prioritises at the parent
   * level). Sub-factors are kept in their existing slots in the underlying
   * factors array; we only permute the positions of the main factors among
   * themselves. The final order sent to the reorder endpoint is:
   *   [main1, main2, ...] in the new sequence, followed by ALL other
   *   factors (sub-factors + duplicates) in their existing array order.
   */
  const moveMainFactor = async (mainIdx: number, dir: -1 | 1) => {
    if (!analysis) return;
    const mains = analysis.factors.filter(f => !f.parent_id && !f.is_duplicate);
    const j = mainIdx + dir;
    if (j < 0 || j >= mains.length) return;
    const reordered = [...mains];
    [reordered[mainIdx], reordered[j]] = [reordered[j], reordered[mainIdx]];
    const others = analysis.factors.filter(f => f.parent_id || f.is_duplicate);
    const finalIds = [...reordered, ...others].map(f => f.id);
    try { await api.post(`${base}/${id}/factors/reorder`, { ordered_ids: finalIds }); await reload(); }
    catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Reorder failed'); }
  };

  /**
   * Step 7 — reorder WITHIN a section (Mandatory or Optional) only.
   *
   * `sectionList` is the visible, already-sorted slice for that section.
   * `idx` is the position WITHIN that slice; `dir` is -1 (up) or +1 (down).
   *
   * Implementation: swap the two factors in `sectionList`, then concatenate
   *   [new mandatory order, new optional order, sub-factors, duplicates]
   * and POST the full id sequence to /factors/reorder. The backend rewrites
   * priority_rank in this order so re-loading the page preserves it.
   */
  const moveWithinSection = async (sectionList: Factor[], idx: number, dir: -1 | 1) => {
    if (!analysis) return;
    const j = idx + dir;
    if (j < 0 || j >= sectionList.length) return;

    const swapped = [...sectionList];
    [swapped[idx], swapped[j]] = [swapped[j], swapped[idx]];

    // Build the other section list (the half NOT being reordered)
    const isThisMandatory = sectionList[0]?.notation === 'mandatory';
    const otherSection = (analysis.factors as Factor[])
      .filter(f => !f.parent_id && !f.is_duplicate)
      .filter(f => (f.notation === 'mandatory') !== isThisMandatory)
      .sort((a, b) => {
        const ra = a.priority_rank ?? 9999, rb = b.priority_rank ?? 9999;
        if (ra !== rb) return ra - rb;
        return (a.display_name || a.name || '').localeCompare(b.display_name || b.name || '');
      });

    const mandatoryOrdered = isThisMandatory ? swapped : otherSection;
    const optionalOrdered  = isThisMandatory ? otherSection : swapped;
    const otherFactors = analysis.factors.filter(f => f.parent_id || f.is_duplicate);
    const finalIds = [...mandatoryOrdered, ...optionalOrdered, ...otherFactors].map(f => f.id);
    try {
      await api.post(`${base}/${id}/factors/reorder`, { ordered_ids: finalIds });
      await reload();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Reorder failed');
    }
  };

  /**
   * Step 7 — set a SINGLE factor's per-pair gap percentage and re-ladder.
   *
   * `factorId`   = the UPPER factor in the pair (its rating depends on the
   *                factor immediately below it in the bottom-up order).
   * `newPct`     = the new gap percentage (50 / 100 / 150 / 200).
   *
   * Semantics — the backend formula is:
   *   thisFactor.std_rating = factorBelow.std_rating + (newPct / 100) * 10
   *
   * So 100% (default) means "10 units higher than the one below", 200% means
   * "20 units higher", etc. The anchor (lowest factor) is always 10.
   */
  const setPairGap = async (factorId: string, newPct: number) => {
    if (!id || !analysis) return;
    try {
      await api.put(`${base}/${id}/factors/${factorId}`, { priority_gap_pct: newPct });
      await api.post(`${base}/${id}/factors/recalc-ladder`);
      await reload();
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to update gap');
    }
  };

  // ─── Step 7+8: assessment cell update ────────────────────
  const upsertCell = async (oid: string, fid: string, patch: any) => {
    try { await api.put(`${base}/${id}/assessments/${oid}/${fid}`, patch); await reload(); }
    catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed'); }
  };

  // AI satisfaction assessment for a single cell (Step 7). Pros-cons only.
  const [aiBusy, setAiBusy] = useState<Record<string, boolean>>({});
  const aiAssessCell = async (oid: string, fid: string, actualValue?: string) => {
    if (module === 'swot') { showAlert('Not available', 'AI assessment is available in the Pros & Cons flow.'); return; }
    // Pre-check mirrors backend (core/ai_assess): Quantitative needs Expected +
    // Operator + Actual; Qualitative/Subjective needs Expected only (AI fetches Actual).
    const factor = analysis?.factors.find(f => f.id === fid);
    const has = (v: any) => v !== undefined && v !== null && String(v).trim() !== '';
    const isQual = (factor?.data_type || 'numeric') === 'text' || factor?.factor_type === 'subjective';
    if (factor && !has(factor.expected_value)) {
      showAlert('Set an Expected value', isQual
        ? 'Add an Expected value for this qualitative factor (Step 5) so AI can assess against it.'
        : 'Add an Expected value (and Operator) for this quantitative factor in Step 5 before AI Assist.');
      return;
    }
    if (factor && !isQual) {
      if (!has(factor.operator)) {
        showAlert('Set an Operator', 'Add an Operator (e.g. ≥) for this quantitative factor in Step 5 before AI Assist.');
        return;
      }
      if (!has(actualValue)) {
        showAlert('Add an Actual value', 'Quantitative factors need an Actual value. Enter it, set a Data Source, or link this option to a Solution Store item.');
        return;
      }
    }
    const key = `${oid}_${fid}`;
    setAiBusy(b => ({ ...b, [key]: true }));
    try {
      await api.post(`${base}/${id}/factors/${fid}/ai-assess`, { option_id: oid, actual_value: actualValue });
      await reload();
      refreshAiWallet();
    } catch (e: any) {
      if (e?.response?.status === 402) {
        showAlert('Out of AI credits', e?.response?.data?.detail || 'Top up your AI wallet to use AI Assist.', [
          { text: 'Not now', style: 'cancel' },
          { text: 'View wallet', onPress: () => router.push('/ai-wallet' as any) },
        ]);
        refreshAiWallet();
      } else {
        showAlert('AI assessment', e?.response?.data?.detail || 'Could not auto-assess. Please enter % manually.');
      }
    } finally {
      setAiBusy(b => ({ ...b, [key]: false }));
    }
  };

  // ─── Phase C: XLS assessment template export / import (pros-cons only) ───
  const [xlsBusy, setXlsBusy] = useState(false);
  const handleDownloadTemplate = async () => {
    setXlsBusy(true);
    try {
      await downloadAssessmentTemplate(`${base}/${id}/assessment-template`, 'assessment-template.xlsx');
    } catch (e: any) {
      showAlert('Download failed', e?.message || 'Could not download the template.');
    } finally {
      setXlsBusy(false);
    }
  };
  const handleImportTemplate = async () => {
    setXlsBusy(true);
    try {
      const res = await importAssessmentTemplate(`${base}/${id}/assessment-import`);
      if (res) {
        await reload();
        showAlert('Import complete', `Applied ${res.applied} value(s) from ${res.rows} row(s).`);
      }
    } catch (e: any) {
      showAlert('Import failed', e?.message || 'Could not import the file.');
    } finally {
      setXlsBusy(false);
    }
  };
  // Google Sheet: create a pre-filled sheet in the user's Drive, then re-import once filled.
  const handleCreateGsheet = async () => {
    setXlsBusy(true);
    try {
      const res = await createAssessmentGsheet(`${base}/${id}/assessment-gsheet`);
      await openSheetUrl(res.url);
      showAlert('Google Sheet ready', 'A Google Sheet was created in your Drive. Fill the “Actual Value” and “Assess %” columns, then tap “Import from Google Sheet”.');
    } catch (e: any) {
      showAlert('Google Sheet', e?.message || 'Could not create the Google Sheet.');
    } finally {
      setXlsBusy(false);
    }
  };
  const handleImportGsheet = async () => {
    setXlsBusy(true);
    try {
      const res = await importAssessmentGsheet(`${base}/${id}/assessment-gsheet/import`);
      await reload();
      showAlert('Import complete', `Applied ${res.applied} value(s) from ${res.rows} row(s).`);
    } catch (e: any) {
      showAlert('Import failed', e?.message || 'Could not import from the Google Sheet. Create one first if you haven’t.');
    } finally {
      setXlsBusy(false);
    }
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

  // Auto-push the CHOSEN option's per-factor improvement deltas (Step 8) into the
  // Action Plan — mirrors My Dezider's MPPS import. Re-runs when the final option
  // changes; idempotent on the backend, then remounts the editor to show new items.
  useEffect(() => {
    const chosen = (analysis as any)?.config?.final_choice_option_id;
    if (step !== 8 || !analysis?.id || !chosen) return;
    let cancelled = false;
    (async () => {
      try {
        await api.post(`/action-items/import-from-pros-cons/${analysis.id}`);
      } catch { /* non-fatal — manual add still works */ }
      if (!cancelled) setPcActionKey((k) => k + 1);
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, analysis?.id, (analysis as any)?.config?.final_choice_option_id]);

  /**
   * Step 7 — alphabetical seed on FIRST entry per analysis.
   *
   * The user expects each section (Mandatory / Optional) to be alphabetical
   * BY DEFAULT, with priority_rank overriding only after they hit ▲ / ▼.
   * Since factors keep their creation-order priority_rank, we have to
   * persist alphabetical ranks once, then let user reorders take over.
   *
   * Persistence is SERVER-SIDE via the `step7_alpha_seeded` flag on the
   * analysis doc (PUT /config). This way the flag survives across
   * devices and across browser-data clears — fixing the localStorage
   * caveat that allowed re-alphabetization on a different browser.
   */
  useEffect(() => {
    if (step !== 7 || !analysis || !id) return;
    if ((analysis as any).step7_alpha_seeded === true) return;

    const mains = analysis.factors.filter(f => !f.parent_id && !f.is_duplicate);
    if (mains.length === 0) {
      // Nothing to alphabetize yet; do not mark done so we retry once
      // factors exist.
      return;
    }
    const labelOf = (f: Factor) => (f.display_name && f.display_name.trim() ? f.display_name : f.name) || '';

    const mandatorySorted = mains
      .filter(f => f.notation === 'mandatory')
      .sort((a, b) => labelOf(a).localeCompare(labelOf(b), undefined, { sensitivity: 'base' }));
    const optionalSorted = mains
      .filter(f => f.notation !== 'mandatory')
      .sort((a, b) => labelOf(a).localeCompare(labelOf(b), undefined, { sensitivity: 'base' }));

    // Check whether the existing priority_rank order ALREADY matches the
    // alphabetical-by-section order. If yes, just set the flag and skip
    // the reorder POST (saves a round-trip on revisits).
    const desired = [...mandatorySorted, ...optionalSorted].map(f => f.id);
    const currentMainsOrder = mains.map(f => f.id);
    const sameOrder =
      desired.length === currentMainsOrder.length &&
      desired.every((d, i) => d === currentMainsOrder[i]);

    const markSeeded = () =>
      api.put(`${base}/${id}/config`, { step7_alpha_seeded: true })
        .then(() => reload())
        .catch(e => console.warn('Step 7 seed-flag persist failed (non-blocking):', e?.response?.data || e?.message || e));

    if (sameOrder) {
      markSeeded();
      return;
    }

    const others = analysis.factors.filter(f => f.parent_id || f.is_duplicate);
    const finalIds = [...mandatorySorted, ...optionalSorted, ...others].map(f => f.id);
    api.post(`${base}/${id}/factors/reorder`, { ordered_ids: finalIds })
      .then(markSeeded)
      .catch(e => {
        console.warn('Step 7 alphabetical init failed (continuing):', e?.response?.data || e?.message || e);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, analysis?.id, (analysis as any)?.step7_alpha_seeded]);

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

  const directFactors = analysis.factors.filter(f => !f.parent_id && !f.is_duplicate);
  const childrenOf = (pid: string) => analysis.factors.filter(f => f.parent_id === pid && !f.is_duplicate);

  // Step 4 — Direct factors that are valid "Group under…" targets:
  // exclude sub-factors and exclude duplicates (you shouldn't be able to
  // nest a factor under a removed/duplicate one)
  const groupingParents = analysis.factors.filter(f => !f.parent_id && !f.is_duplicate);

  /**
   * Display-name helper.
   *
   * Step 1-4 ALWAYS show the original `name` (what the user typed in Step 1),
   * which preserves the source-of-truth label and lets the user track their
   * original thinking even after Step 5 renames.
   *
   * Step 5-8 show `display_name` if the user has renamed in Step 5, otherwise
   * fall back to `name`. This way:
   *   - Step 1-4 captions in Step 5+ ("↳ sub-factor of "<X>"") use display_name
   *     so the user sees the names they chose in Step 5
   *   - Re-visiting earlier steps still shows the original entries verbatim
   */
  const displayName = (f: Factor): string =>
    (step >= 5 ? (f.display_name && f.display_name.trim() ? f.display_name : f.name) : f.name) || '';

  // For tooltips / hints — original name to show under the rename input
  // ("Original: <name>") so the user can see what they overrode.
  const originalName = (f: Factor): string => f.name || '';
  const hasRename = (f: Factor): boolean =>
    Boolean(f.display_name && f.display_name.trim() && f.display_name.trim() !== f.name);

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      {/* Header */}
      <LinearGradient colors={[COLORS.primary, COLORS.primaryDark]} style={styles.header}>
        <TouchableOpacity onPress={() => safeBack(router)} style={styles.headerBtn}>
          <Ionicons name="chevron-back" size={22} color="#fff" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle} numberOfLines={1}>{analysis.title}</Text>
          <Text style={styles.headerSub}>{module === 'swot' ? 'SWOT' : 'Pros & Cons'} · 8-step framework</Text>
        </View>
        <TouchableOpacity onPress={() => goHome(router)} style={styles.headerBtn} accessibilityLabel="Home">
          <Ionicons name="home" size={20} color="#fff" />
        </TouchableOpacity>
        <TouchableOpacity onPress={() => setShowGuidelines(true)} style={styles.headerBtn}>
          <Ionicons name="bulb-outline" size={22} color="#fff" />
        </TouchableOpacity>
      </LinearGradient>

      {contributionMode && (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 14, paddingVertical: 10, backgroundColor: '#EEF2FF' }}>
          <Ionicons name="people-circle-outline" size={18} color="#4338CA" />
          <Text style={{ flex: 1, fontSize: 12.5, fontWeight: '700', color: '#3730A3' }}>
            Contribution Mode — add your input to Step {contribStepNum}. {stepAccess === 'readonly' ? 'Other steps are reference-only.' : 'Only this step is shown.'}
          </Text>
          <TouchableOpacity
            onPress={submitContribution}
            disabled={submittingContribution}
            testID="pc-submit-contribution"
            style={{ flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: COLORS.primary, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10, opacity: submittingContribution ? 0.7 : 1 }}
          >
            {submittingContribution ? <ActivityIndicator color="#fff" size="small" /> : (
              <><Ionicons name="send" size={14} color="#fff" /><Text style={{ color: '#fff', fontWeight: '800', fontSize: 12.5 }}>Submit</Text></>
            )}
          </TouchableOpacity>
        </View>
      )}

      {/* Step strip */}
      <View style={styles.stepStrip}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: 8 }}>
          {(contributionMode && stepAccess === 'hidden' ? STEPS.filter(s => s.n === contribStepNum) : STEPS).map(s => (
            <TouchableOpacity key={s.n} style={[styles.stepChip, step === s.n && styles.stepChipActive]}
              onPress={() => { if (!(contributionMode && stepAccess === 'hidden')) persistStep(s.n); }}>
              <Text style={[styles.stepChipNum, step === s.n && { color: '#fff' }]}>{s.n}</Text>
              <Text style={[styles.stepChipLabel, step === s.n && { color: '#fff' }]}>{s.label}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.body}>

          {/* Collab affordance — share this step or schedule discussion. */}
          {!contributionMode && id && analysis && (
            <CollabBar
              module={module === 'swot' ? 'swot' : 'pros-cons'}
              decisionId={id}
              stepId={`s${step}`}
              stepLabel={`${module === 'swot' ? 'SWOT' : 'P&C'} Step ${step}`}
              decisionTitle={analysis.title || 'Pros & Cons analysis'}
              useShareStep
              stepNumber={step}
            />
          )}

          {/* ────── STEP 1 ────── */}
          {step === 1 && (
            <View>
              {/* ── Basics: Decision / Description / Life Area ── */}
              <View style={styles.basicsCard}>
                <TouchableOpacity
                  style={styles.basicsHeader}
                  onPress={() => setBasicsOpen(o => !o)}
                  activeOpacity={0.7}
                >
                  <Ionicons name="information-circle" size={18} color={COLORS.primary} />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.basicsTitle}>About this decision</Text>
                    {!basicsOpen && (
                      <Text style={styles.basicsSummary} numberOfLines={1}>
                        {bTitle || 'Untitled'}{bLifeArea ? ` · ${LIFE_AREAS.find(la => la.key === bLifeArea)?.label || bLifeArea}` : ''}
                      </Text>
                    )}
                  </View>
                  <Ionicons
                    name={basicsOpen ? 'chevron-up' : 'chevron-down'}
                    size={20}
                    color={COLORS.textDim}
                  />
                </TouchableOpacity>

                {basicsOpen && (
                  <View style={styles.basicsBody}>
                    <Text style={styles.inputLabel}>Decision / Topic *</Text>
                    <TextInput
                      style={styles.input}
                      placeholder="e.g., Which car should I buy?"
                      value={bTitle}
                      onChangeText={setBTitle}
                      onBlur={() => {
                        const t = bTitle.trim();
                        if (t && t !== analysis?.title) saveBasics({ title: t });
                      }}
                    />

                    <Text style={styles.inputLabel}>Description (optional)</Text>
                    <TextInput
                      style={[styles.input, { minHeight: 64, textAlignVertical: 'top' }]}
                      placeholder="Add any relevant background or constraints..."
                      value={bContext}
                      onChangeText={setBContext}
                      multiline
                      onBlur={() => {
                        if (bContext !== (analysis?.context || '')) saveBasics({ context: bContext });
                      }}
                    />

                    {/* Sub-type — consistent across MyDezider / Pros & Cons / Solution Finder.
                        Order is user-mandated: Present Problem · Need · Future Risk · Aspiration. */}
                    <Text style={styles.inputLabel}>Type</Text>
                    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 4 }}>
                      {DECISION_TYPES.map((dt) => {
                        const active = bDecisionType === dt.key;
                        return (
                          <TouchableOpacity
                            key={dt.key}
                            testID={`pc-subtype-${dt.key}`}
                            onPress={() => { setBDecisionType(dt.key); saveBasics({ decision_type: dt.key }); }}
                            style={{
                              flexDirection: 'row', alignItems: 'center',
                              borderWidth: 1.5, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 7,
                              borderColor: active ? dt.color : '#E5E7EB',
                              backgroundColor: active ? dt.color : '#FFF',
                            }}
                          >
                            <Ionicons name={dt.icon as any} size={13} color={active ? '#fff' : dt.color} />
                            <Text style={{ fontSize: 12.5, fontWeight: '600', marginLeft: 5, color: active ? '#fff' : COLORS.text }}>{dt.label}</Text>
                          </TouchableOpacity>
                        );
                      })}
                    </View>

                    {/* Life Area is captured in the 4-step intake on creation and is
                        shown in the collapsed summary above — the redundant re-ask
                        picker was removed (June 2026). */}
                  </View>
                )}
              </View>

              <Text style={styles.stepTitle}>Step 1 — List initial Direct Factors</Text>
              <Text style={styles.stepHint}>Add the factors that matter for this decision — just the names for now. You’ll set expected values, units, operators and data sources later in Step 5 (Review &amp; Refine Expectations).</Text>
              <View style={styles.card}>
                <Text style={styles.inputLabel}>Factor name</Text>
                <TextInput style={styles.input} placeholder="e.g., Mileage - in the case of a Car Purchase decision" placeholderTextColor={COLORS.textDim} value={fName} onChangeText={setFName} onSubmitEditing={addFactor} />
                <TouchableOpacity style={[styles.primaryBtn, !fName.trim() && { opacity: 0.5 }]}
                  disabled={!fName.trim() || busy} onPress={addFactor}>
                  <Ionicons name="add" size={18} color="#fff" />
                  <Text style={styles.primaryBtnText}>Add Direct Factor</Text>
                </TouchableOpacity>
              </View>

              <Text style={styles.sectionTitle}>Direct factors ({directFactors.filter(f => f.source === 'direct').length})</Text>
              {analysis.factors.filter(f => f.source === 'direct').map((f, i) => {
                const isEditing = editingFactorId === f.id;
                return (
                  <View key={f.id} style={[styles.factorRow, isEditing && styles.factorRowEditing]}>
                    <View style={[styles.sourceTag, { backgroundColor: COLORS.direct }]}>
                      <Text style={styles.sourceTagText}>D</Text>
                    </View>
                    {isEditing ? (
                      <View style={{ flex: 1 }}>
                        <TextInput
                          style={[styles.input, { marginBottom: 6 }]}
                          placeholder="Factor name"
                          value={editFactorName}
                          onChangeText={setEditFactorName}
                          autoFocus
                          onSubmitEditing={saveEditFactor}
                        />
                        <View style={{ flexDirection: 'row', gap: 6, marginTop: 2, justifyContent: 'flex-end' }}>
                          <TouchableOpacity onPress={cancelEditFactor} style={styles.editGhostBtn}>
                            <Text style={styles.editGhostBtnText}>Cancel</Text>
                          </TouchableOpacity>
                          <TouchableOpacity onPress={saveEditFactor} style={styles.editSaveBtn}>
                            <Ionicons name="checkmark" size={14} color="#fff" />
                            <Text style={styles.editSaveBtnText}>Save</Text>
                          </TouchableOpacity>
                        </View>
                      </View>
                    ) : (
                      <>
                        <TouchableOpacity
                          onPress={() => beginEditFactor(f)}
                          style={{ flex: 1 }}
                          activeOpacity={0.7}
                          accessibilityLabel={`Edit factor ${f.name}`}
                        >
                          <Text style={styles.factorName}>{f.name}</Text>
                        </TouchableOpacity>
                        <TouchableOpacity
                          onPress={() => beginEditFactor(f)}
                          hitSlop={6}
                          style={{ marginRight: 10 }}
                          accessibilityLabel="Edit"
                        >
                          <Ionicons name="pencil" size={16} color={COLORS.textDim} />
                        </TouchableOpacity>
                        <TouchableOpacity onPress={() => confirmDeleteFactor(f)} hitSlop={6} accessibilityLabel="Delete">
                          <Ionicons name="trash-outline" size={18} color={COLORS.con} />
                        </TouchableOpacity>
                      </>
                    )}
                  </View>
                );
              })}
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
                <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
                  <TextInput
                    style={[styles.input, { flex: 1, marginBottom: 0 }]}
                    placeholder="e.g., Car X"
                    value={optName}
                    onChangeText={setOptName}
                    onSubmitEditing={addOption}
                  />
                  <TouchableOpacity
                    style={[styles.addOptBtn, (!optName.trim() || busy) && { opacity: 0.5 }]}
                    onPress={addOption}
                    disabled={!optName.trim() || busy}
                    accessibilityLabel="Add option"
                  >
                    <Ionicons name="add" size={20} color="#fff" />
                  </TouchableOpacity>
                </View>
              </View>

              {analysis.options.map((o) => {
                const isCollapsed = collapsedOptIds.has(o.id);
                const prosCollapsed = collapsedProsIds.has(o.id);
                const consCollapsed = collapsedConsIds.has(o.id);
                const isEditingThisOpt = editingOptId === o.id;
                return (
                  <View key={o.id} style={styles.optionCard}>
                    <View style={styles.optionHeader}>
                      <TouchableOpacity
                        onPress={() => toggleOptCollapsed(o.id)}
                        hitSlop={6}
                        style={{ marginRight: 6 }}
                        accessibilityLabel={isCollapsed ? 'Expand option' : 'Collapse option'}
                      >
                        <Ionicons
                          name={isCollapsed ? 'chevron-forward' : 'chevron-down'}
                          size={18}
                          color={COLORS.textDim}
                        />
                      </TouchableOpacity>

                      {isEditingThisOpt ? (
                        <>
                          <TextInput
                            style={[styles.input, { flex: 1, marginBottom: 0, paddingVertical: 6 }]}
                            value={editOptName}
                            onChangeText={setEditOptName}
                            autoFocus
                            onSubmitEditing={saveEditOption}
                          />
                          <TouchableOpacity onPress={saveEditOption} style={styles.editSaveBtn}>
                            <Ionicons name="checkmark" size={14} color="#fff" />
                          </TouchableOpacity>
                          <TouchableOpacity onPress={cancelEditOption} style={[styles.editGhostBtn, { marginLeft: 6 }]}>
                            <Ionicons name="close" size={14} color={COLORS.textDim} />
                          </TouchableOpacity>
                        </>
                      ) : (
                        <>
                          <TouchableOpacity
                            onPress={() => toggleOptCollapsed(o.id)}
                            style={{ flex: 1 }}
                            activeOpacity={0.7}
                          >
                            <Text style={styles.optionName}>{o.name}</Text>
                            {isCollapsed && (
                              <Text style={styles.optionSummary}>
                                Pros: {o.pros.length} · Cons: {o.cons.length}
                              </Text>
                            )}
                          </TouchableOpacity>
                          <TouchableOpacity
                            onPress={() => beginEditOption(o)}
                            hitSlop={6}
                            style={{ marginRight: 10 }}
                            accessibilityLabel="Rename option"
                          >
                            <Ionicons name="pencil" size={16} color={COLORS.textDim} />
                          </TouchableOpacity>
                          <TouchableOpacity onPress={() => confirmDeleteOption(o)} hitSlop={6} accessibilityLabel="Delete option">
                            <Ionicons name="trash-outline" size={18} color={COLORS.con} />
                          </TouchableOpacity>
                        </>
                      )}
                    </View>

                    {!isCollapsed && (
                      <>
                        {/* pros section header (collapsible) */}
                        <TouchableOpacity
                          onPress={() => toggleProsCollapsed(o.id)}
                          activeOpacity={0.7}
                          style={styles.pcSectionRow}
                        >
                          <Ionicons
                            name={prosCollapsed ? 'chevron-forward' : 'chevron-down'}
                            size={14}
                            color={COLORS.pro}
                          />
                          <Text style={[styles.pcSection, { color: COLORS.pro, marginTop: 0 }]}>
                            Pros ({o.pros.length})
                          </Text>
                        </TouchableOpacity>
                        {!prosCollapsed && o.pros.map(p => {
                          const editing = editingPcKey === `${o.id}:pros:${p.id}`;
                          return (
                            <View key={p.id} style={[styles.pcRow, { borderLeftColor: COLORS.pro }]}>
                              {editing ? (
                                <>
                                  <TextInput
                                    style={[styles.input, { flex: 1, marginBottom: 0, paddingVertical: 6 }]}
                                    value={editPcDraft}
                                    onChangeText={setEditPcDraft}
                                    autoFocus
                                    onSubmitEditing={saveEditPc}
                                  />
                                  <TouchableOpacity onPress={saveEditPc} style={styles.editSaveBtn}>
                                    <Ionicons name="checkmark" size={14} color="#fff" />
                                  </TouchableOpacity>
                                  <TouchableOpacity onPress={cancelEditPc} style={[styles.editGhostBtn, { marginLeft: 6 }]}>
                                    <Ionicons name="close" size={14} color={COLORS.textDim} />
                                  </TouchableOpacity>
                                </>
                              ) : (
                                <>
                                  <TouchableOpacity onPress={() => beginEditPc(o.id, 'pros', p)} style={{ flex: 1 }} activeOpacity={0.7}>
                                    <Text style={styles.pcText}>{p.text}</Text>
                                  </TouchableOpacity>
                                  <TouchableOpacity onPress={() => beginEditPc(o.id, 'pros', p)} hitSlop={6} style={{ marginRight: 8 }} accessibilityLabel="Edit Pro">
                                    <Ionicons name="pencil" size={14} color={COLORS.textDim} />
                                  </TouchableOpacity>
                                  <TouchableOpacity onPress={() => delPC(o.id, 'pros', p.id)} hitSlop={6}>
                                    <Ionicons name="close-circle" size={18} color={COLORS.textDim} />
                                  </TouchableOpacity>
                                </>
                              )}
                            </View>
                          );
                        })}

                        {/* cons section header (collapsible) */}
                        <TouchableOpacity
                          onPress={() => toggleConsCollapsed(o.id)}
                          activeOpacity={0.7}
                          style={styles.pcSectionRow}
                        >
                          <Ionicons
                            name={consCollapsed ? 'chevron-forward' : 'chevron-down'}
                            size={14}
                            color={COLORS.con}
                          />
                          <Text style={[styles.pcSection, { color: COLORS.con, marginTop: 0 }]}>
                            Cons ({o.cons.length})
                          </Text>
                        </TouchableOpacity>
                        {!consCollapsed && o.cons.map(c => {
                          const editing = editingPcKey === `${o.id}:cons:${c.id}`;
                          return (
                            <View key={c.id} style={[styles.pcRow, { borderLeftColor: COLORS.con }]}>
                              {editing ? (
                                <>
                                  <TextInput
                                    style={[styles.input, { flex: 1, marginBottom: 0, paddingVertical: 6 }]}
                                    value={editPcDraft}
                                    onChangeText={setEditPcDraft}
                                    autoFocus
                                    onSubmitEditing={saveEditPc}
                                  />
                                  <TouchableOpacity onPress={saveEditPc} style={styles.editSaveBtn}>
                                    <Ionicons name="checkmark" size={14} color="#fff" />
                                  </TouchableOpacity>
                                  <TouchableOpacity onPress={cancelEditPc} style={[styles.editGhostBtn, { marginLeft: 6 }]}>
                                    <Ionicons name="close" size={14} color={COLORS.textDim} />
                                  </TouchableOpacity>
                                </>
                              ) : (
                                <>
                                  <TouchableOpacity onPress={() => beginEditPc(o.id, 'cons', c)} style={{ flex: 1 }} activeOpacity={0.7}>
                                    <Text style={styles.pcText}>{c.text}</Text>
                                  </TouchableOpacity>
                                  <TouchableOpacity onPress={() => beginEditPc(o.id, 'cons', c)} hitSlop={6} style={{ marginRight: 8 }} accessibilityLabel="Edit Con">
                                    <Ionicons name="pencil" size={14} color={COLORS.textDim} />
                                  </TouchableOpacity>
                                  <TouchableOpacity onPress={() => delPC(o.id, 'cons', c.id)} hitSlop={6}>
                                    <Ionicons name="close-circle" size={18} color={COLORS.textDim} />
                                  </TouchableOpacity>
                                </>
                              )}
                            </View>
                          );
                        })}

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
                                value={pcText} onChangeText={setPcText}
                                onSubmitEditing={addPC} />
                              <TouchableOpacity style={styles.miniBtn} onPress={addPC} disabled={!pcText.trim() || busy}>
                                <Ionicons name="checkmark" size={16} color="#fff" />
                              </TouchableOpacity>
                            </>
                          )}
                        </View>
                      </>
                    )}
                  </View>
                );
              })}
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
              <Text style={styles.stepHint}>Tap “Group under…” to nest a factor as a sub-factor, or “Mark duplicate” to soft-remove a factor (kept here as audit history; hidden from Steps 5 onward). Both actions are reversible.</Text>

              {/* Step 4 mini-legend — shows running counts */}
              <View style={styles.dedupLegend}>
                <View style={styles.dedupLegendItem}>
                  <Text style={styles.dedupLegendNum}>{analysis.factors.filter(f => !f.parent_id && !f.is_duplicate).length}</Text>
                  <Text style={styles.dedupLegendLabel}>Active</Text>
                </View>
                <View style={[styles.dedupLegendItem, { borderLeftWidth: 1, borderLeftColor: COLORS.border }]}>
                  <Text style={[styles.dedupLegendNum, { color: COLORS.textDim }]}>{analysis.factors.filter(f => f.parent_id && !f.is_duplicate).length}</Text>
                  <Text style={styles.dedupLegendLabel}>Grouped</Text>
                </View>
                <View style={[styles.dedupLegendItem, { borderLeftWidth: 1, borderLeftColor: COLORS.border }]}>
                  <Text style={[styles.dedupLegendNum, { color: COLORS.warn }]}>{analysis.factors.filter(f => f.is_duplicate).length}</Text>
                  <Text style={styles.dedupLegendLabel}>Duplicate</Text>
                </View>
              </View>

              {(() => {
                // ── Hierarchical render for Step 4 ────────────────────────
                // Render order:
                //   1. Each top-level non-duplicate factor IN its natural order
                //   2. Immediately followed by its sub-factors (indented)
                //   3. Then any duplicates at the very end (keeps audit
                //      visibility without polluting the active list)
                // This is what fixes the bug where "Saving of Fuel Cost"
                // (nested under "Expected salary") was visually rendered
                // right after "Will get more free time" — making it look
                // like the wrong parent. We now physically reorder rows so
                // a child ALWAYS appears directly under its true parent.
                const allFactors = analysis.factors;
                const byParent: Record<string, Factor[]> = {};
                for (const f of allFactors) {
                  const pid = f.parent_id || '';
                  if (!pid) continue;
                  if (!byParent[pid]) byParent[pid] = [];
                  byParent[pid].push(f);
                }
                const topLevel = allFactors.filter(f => !f.parent_id && !f.is_duplicate);
                const duplicates = allFactors.filter(f => f.is_duplicate);
                // Orphaned sub-factors: parent_id points to a non-existent
                // or duplicate-marked factor. Should be rare but render
                // them at the bottom under a small note so user can fix.
                const validParentIds = new Set(topLevel.map(f => f.id));
                const orphans = allFactors.filter(f =>
                  f.parent_id && !f.is_duplicate && !validParentIds.has(f.parent_id)
                );
                const rendered: React.ReactNode[] = [];
                for (const parent of topLevel) {
                  rendered.push(
                    <FactorGroupRow
                      key={parent.id}
                      factor={parent}
                      parentName={null}
                      candidateChildren={topLevel.filter(d => d.id !== parent.id)}
                      onAddChild={(childId) => updateFactor(childId, { parent_id: parent.id })}
                      onCreateChild={(name) => createSubFactor(parent.id, name)}
                      onPromote={() => updateFactor(parent.id, { parent_id: null })}
                      onToggleDuplicate={() => updateFactor(parent.id, { is_duplicate: !parent.is_duplicate })}
                    />
                  );
                  for (const child of (byParent[parent.id] || [])) {
                    rendered.push(
                      <FactorGroupRow
                        key={child.id}
                        factor={child}
                        parentName={parent.name}
                        candidateChildren={[]}
                        onAddChild={() => {}}
                        onCreateChild={async () => {}}
                        onPromote={() => updateFactor(child.id, { parent_id: null })}
                        onToggleDuplicate={() => updateFactor(child.id, { is_duplicate: !child.is_duplicate })}
                      />
                    );
                  }
                }
                if (orphans.length > 0) {
                  rendered.push(
                    <Text key="orphan-note" style={[styles.factorMeta, { color: COLORS.warn, marginTop: 12, marginBottom: 4 }]}>
                      ⚠️ {orphans.length} sub-factor(s) reference a missing/duplicate parent. Promote them out or re-group:
                    </Text>
                  );
                  for (const o of orphans) {
                    rendered.push(
                      <FactorGroupRow
                        key={o.id}
                        factor={o}
                        parentName="(missing parent)"
                        candidateChildren={[]}
                        onAddChild={() => {}}
                        onCreateChild={async () => {}}
                        onPromote={() => updateFactor(o.id, { parent_id: null })}
                        onToggleDuplicate={() => updateFactor(o.id, { is_duplicate: !o.is_duplicate })}
                      />
                    );
                  }
                }
                if (duplicates.length > 0) {
                  rendered.push(
                    <Text key="dup-note" style={[styles.factorMeta, { color: COLORS.textDim, marginTop: 12, marginBottom: 4 }]}>
                      — Duplicates (audit history, hidden from Step 5 onward) —
                    </Text>
                  );
                  for (const d of duplicates) {
                    rendered.push(
                      <FactorGroupRow
                        key={d.id}
                        factor={d}
                        parentName={null}
                        candidateChildren={[]}
                        onAddChild={() => {}}
                        onCreateChild={async () => {}}
                        onPromote={() => updateFactor(d.id, { parent_id: null })}
                        onToggleDuplicate={() => updateFactor(d.id, { is_duplicate: !d.is_duplicate })}
                      />
                    );
                  }
                }
                return rendered;
              })()}
              <NextBack onBack={() => persistStep(3)} onNext={() => persistStep(5)} />
            </View>
          )}

          {/* ────── STEP 5 ────── */}
          {step === 5 && (
            <View>
              <Text style={styles.stepTitle}>Step 5 — Review &amp; Refine Expectations</Text>
              <Text style={styles.stepHint}>For each factor (and sub-factor), set the Type (Quantitative/Qualitative), Expected value, Unit, Operator and an optional auto-fetch Data Source. Add sub-factors and tap “Split evenly” to balance their weightage to 100% (weights are optional and normalised on scoring).</Text>
              {directFactors.map(f => (
                <FactorTreeNode
                  key={f.id}
                  factor={f}
                  childrenList={childrenOf(f.id)}
                  displayNameOf={displayName}
                  hasRenameOf={hasRename}
                  originalNameOf={originalName}
                  onRename={(fid, newName) => updateFactor(fid, { display_name: newName })}
                  onRevertName={(fid) => updateFactor(fid, { display_name: null })}
                  onSetWeight={(fid, w) => updateFactor(fid, { weight: w })}
                  onAddSubFactor={(pid) => addSubFactorQuick(pid)}
                  onPatchFactor={(fid, patch) => updateFactor(fid, patch)}
                  onOpenDataSource={(factor) => setDsFactor(factor)}
                  onDeleteFactor={(factor) => confirmDeleteFactor(factor)}
                />
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

              {/* Step 6 — Only main factors get classified A/B. Sub-factors */}
              {/* are shown read-only inside an expand/collapse panel so the  */}
              {/* user can reference them while deciding A/B at parent level. */}
              {/* (Sub-factors inherit their parent's Mandatory/Optional.)    */}
              {directFactors.map(f => (
                <MainFactorWithSubs
                  key={f.id}
                  factor={f}
                  subs={childrenOf(f.id)}
                  displayNameOf={displayName}
                  hasRenameOf={hasRename}
                  originalNameOf={originalName}
                >
                  {(['mandatory', 'optional'] as const).map(n => (
                    <TouchableOpacity key={n} style={[styles.notationBtn, f.notation === n && (n === 'mandatory' ? styles.notationMandActive : styles.notationOptActive)]}
                      onPress={() => updateFactor(f.id, { notation: n })}>
                      <Text style={[styles.notationBtnText, f.notation === n && { color: '#fff' }]}>{n === 'mandatory' ? 'A' : 'B'}</Text>
                    </TouchableOpacity>
                  ))}
                </MainFactorWithSubs>
              ))}
              <NextBack onBack={() => persistStep(5)} onNext={() => persistStep(7)} />
            </View>
          )}

          {/* ────── STEP 7 ────── */}
          {step === 7 && (() => {
            // Partition main factors into Mandatory (A) and Optional (B) sections.
            // Each section is sorted by priority_rank (preserves prior reorders);
            // ties broken alphabetically by display name.
            const sortFn = (a: Factor, b: Factor) => {
              const ra = a.priority_rank ?? 9999;
              const rb = b.priority_rank ?? 9999;
              if (ra !== rb) return ra - rb;
              return displayName(a).localeCompare(displayName(b));
            };
            const mandatoryFactors = directFactors
              .filter(f => f.notation === 'mandatory').sort(sortFn);
            const optionalFactors = directFactors
              .filter(f => f.notation !== 'mandatory').sort(sortFn);

            // Renders one card (extracted so we don't duplicate JSX for A & B).
            const renderCard = (f: Factor, displayIdx: number, sectionList: Factor[], sectionLabel: 'A' | 'B') => {
              const expanded = step7ExpandedIds.has(f.id);
              return (
              <View key={f.id} style={styles.factorCard}>
                <View style={styles.factorCardHeader}>
                  <Text style={[styles.rankBadge, sectionLabel === 'A' ? { backgroundColor: COLORS.mandatory } : { backgroundColor: COLORS.optional }]}>
                    {sectionLabel}{displayIdx + 1}
                  </Text>
                  <Text style={[styles.factorName, { flex: 1 }]}>{displayName(f)}</Text>
                  <View style={{ flexDirection: 'row', gap: 4 }}>
                    <TouchableOpacity
                      onPress={() => moveWithinSection(sectionList, displayIdx, -1)}
                      disabled={displayIdx === 0}
                      accessibilityLabel={`Move ${displayName(f)} up within ${sectionLabel === 'A' ? 'Mandatory' : 'Optional'} section`}
                    >
                      <Ionicons name="chevron-up" size={22} color={displayIdx === 0 ? COLORS.border : COLORS.textDim} />
                    </TouchableOpacity>
                    <TouchableOpacity
                      onPress={() => moveWithinSection(sectionList, displayIdx, 1)}
                      disabled={displayIdx === sectionList.length - 1}
                      accessibilityLabel={`Move ${displayName(f)} down within ${sectionLabel === 'A' ? 'Mandatory' : 'Optional'} section`}
                    >
                      <Ionicons name="chevron-down" size={22} color={displayIdx === sectionList.length - 1 ? COLORS.border : COLORS.textDim} />
                    </TouchableOpacity>
                    <TouchableOpacity
                      onPress={() => toggleStep7Expand(f.id)}
                      style={{ flexDirection: 'row', alignItems: 'center', gap: 3, backgroundColor: expanded ? COLORS.primary : '#EDE7F6', borderRadius: 8, paddingHorizontal: 9, paddingVertical: 5, marginLeft: 4 }}
                      accessibilityLabel={expanded ? `Collapse ${displayName(f)}` : `Assess ${displayName(f)}`}
                    >
                      <Ionicons name={expanded ? 'chevron-up' : 'create-outline'} size={13} color={expanded ? '#fff' : COLORS.primary} />
                      <Text style={{ fontSize: 11, fontWeight: '800', color: expanded ? '#fff' : COLORS.primary }}>{expanded ? 'Done' : 'Assess'}</Text>
                    </TouchableOpacity>
                  </View>
                </View>
                {hasRename(f) && (
                  <Text style={[styles.factorMeta, { color: COLORS.textDim, fontStyle: 'italic', marginTop: 2 }]}>
                    Originally: “{originalName(f)}”
                  </Text>
                )}
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
                  {/* Std Rating is now AUTO-COMPUTED from priority position via */}
                  {/* the backend's reorder endpoint (top = N*gap, bottom = gap).*/}
                  {/* It's read-only here. To change it, reorder via ▲/▼ or     */}
                  {/* change the Realistic Gap slider at the top of Step 7.     */}
                  <Text style={styles.cellLabel}>Std Rating</Text>
                  <View style={[styles.readOnlyChip, { borderColor: sectionLabel === 'A' ? COLORS.mandatory : COLORS.optional }]}>
                    <Text style={[styles.readOnlyChipText, { color: sectionLabel === 'A' ? COLORS.mandatory : COLORS.optional }]}>
                      {f.std_rating || 0}
                    </Text>
                  </View>
                  {/* Optional target/expected value + unit for THIS factor.       */}
                  {/* Lets user record what "good" looks like (e.g., 60000 INR/mo) */}
                  {/* so they can judge each option's actual value below.          */}
                  <Text style={[styles.cellLabel, { marginLeft: 8 }]}>Expected</Text>
                  <DebouncedInput
                    style={[styles.inputSm, { width: 96 }]}
                    placeholder="optional"
                    placeholderTextColor={COLORS.textDim}
                    value={f.expected_value || ''}
                    onSave={(text) => updateFactor(f.id, { expected_value: text || null })}
                  />
                  <Text style={styles.cellLabel}>Unit</Text>
                  <DebouncedInput
                    style={[styles.inputSm, { width: 72 }]}
                    placeholder="e.g., INR"
                    placeholderTextColor={COLORS.textDim}
                    value={f.unit || ''}
                    onSave={(text) => updateFactor(f.id, { unit: text || null })}
                  />
                </View>
                {expanded && analysis.options.map(o => {
                  const cell = (analysis.assessments?.[o.id] || {})[f.id] || { assessment_pct: 0, cell_value: 0, actual_value: '' };
                  return (
                    <View key={o.id} style={[styles.assessRow, { flexWrap: 'wrap' }]}>
                      <Text style={styles.assessOpt} numberOfLines={1}>{o.name}</Text>
                      <Text style={styles.cellLabel}>Actual</Text>
                      <DebouncedInput
                        style={[styles.inputSm, { width: 84 }]}
                        placeholder="value"
                        placeholderTextColor={COLORS.textDim}
                        value={cell.actual_value || ''}
                        onSave={(text) => upsertCell(o.id, f.id, { actual_value: text })}
                      />
                      {f.unit ? <Text style={[styles.cellLabel, { color: COLORS.textDim }]}>{f.unit}</Text> : null}
                      <LmhAiButtons
                        current={Number(cell.assessment_pct ?? 0)}
                        onPick={(p) => upsertCell(o.id, f.id, { assessment_pct: p })}
                        onAI={() => aiAssessCell(o.id, f.id, cell.actual_value || '')}
                        busy={!!aiBusy[`${o.id}_${f.id}`]}
                      />
                      <Text style={styles.cellLabel}>Custom %</Text>
                      <DebouncedInput
                        style={[styles.inputSm, { width: 56 }]}
                        keyboardType="number-pad"
                        value={String(cell.assessment_pct ?? 0)}
                        onSave={(text) => upsertCell(o.id, f.id, { assessment_pct: Math.max(0, Math.min(100, parseInt(text, 10) || 0)) })}
                      />
                      <Text style={styles.cellValue}>= {cell.cell_value?.toFixed?.(1) ?? '0'}</Text>
                    </View>
                  );
                })}
                {/* Editable sub-factor accordion. Each sub-factor expands into    */}
                {/* its own data-collection mini-card with Expected/Unit + per-   */}
                {/* option Actual & Assess %. These values are captured but DO    */}
                {/* NOT contribute to scoring (parent's rating dominates per the  */}
                {/* aggregator's main-factor-only filter).                        */}
                {expanded && (
                  <SubFactorEditableList
                    subs={childrenOf(f.id)}
                    options={analysis.options}
                    assessments={analysis.assessments || {}}
                    displayNameOf={displayName}
                    hasRenameOf={hasRename}
                    originalNameOf={originalName}
                    onFactorPatch={(fid, patch) => updateFactor(fid, patch)}
                    onCellPatch={(oid, fid, patch) => upsertCell(oid, fid, patch)}
                    onAIAssess={(oid, fid, actual) => aiAssessCell(oid, fid, actual)}
                    aiBusy={aiBusy}
                  />
                )}
                {!expanded && (
                  <TouchableOpacity
                    onPress={() => toggleStep7Expand(f.id)}
                    style={{ marginTop: 6, flexDirection: 'row', alignItems: 'center', gap: 6 }}
                    accessibilityLabel={`Assess options for ${displayName(f)}`}
                  >
                    <Ionicons name="chevron-down" size={14} color={COLORS.primary} />
                    <Text style={{ fontSize: 12, color: COLORS.primary, fontWeight: '700' }}>
                      Assess {analysis.options.length} option{analysis.options.length === 1 ? '' : 's'} →
                    </Text>
                  </TouchableOpacity>
                )}
              </View>
              );
            };

            // ── Bottom-most factor in the combined visual order ────────
            // Visual top→bottom : [A1…An, B1…Bn]. Bottom-most = last B (or
            // last A if there are no B-factors). This factor is the ANCHOR
            // (std_rating = 10) — it has NO gap selector below it.
            const bottomMostId =
              optionalFactors.length > 0
                ? optionalFactors[optionalFactors.length - 1].id
                : mandatoryFactors.length > 0
                  ? mandatoryFactors[mandatoryFactors.length - 1].id
                  : null;

            // ── Per-pair gap connector ────────────────────────────────
            // Sits BELOW a card. Controls THIS card's priority_gap_pct
            // (i.e. how much higher THIS card is than the card immediately
            // below it in the visual flow). Buttons: 50/100/150/200%.
            const renderGapConnector = (f: Factor) => {
              const pct = Math.round(Number(f.priority_gap_pct ?? 100));
              const opts = [
                { pct: 50,  add: 5,  label: 'Tight'   },
                { pct: 100, add: 10, label: 'Default' },
                { pct: 150, add: 15, label: 'Wide'    },
                { pct: 200, add: 20, label: 'Steep'   },
              ];
              return (
                <View key={`gap-${f.id}`} style={styles.gapConnector}>
                  <View style={styles.gapConnectorRail} />
                  <View style={styles.gapConnectorInner}>
                    <Text style={styles.gapConnectorLabel}>
                      Gap above ↑ — adds <Text style={{ fontWeight: '900', color: COLORS.text }}>+{Math.round((pct / 100) * 10)}</Text> to the factor below
                    </Text>
                    <View style={styles.gapConnectorRow}>
                      {opts.map(opt => {
                        const active = pct === opt.pct;
                        return (
                          <TouchableOpacity
                            key={opt.pct}
                            style={[styles.gapConnectorBtn, active && styles.gapConnectorBtnActive]}
                            onPress={() => setPairGap(f.id, opt.pct)}
                            accessibilityLabel={`Set gap above ${displayName(f)} to ${opt.pct}% (+${opt.add})`}
                          >
                            <Text style={[styles.gapConnectorPct, active && { color: '#fff' }]}>{opt.pct}%</Text>
                            <Text style={[styles.gapConnectorAdd, active && { color: '#fff' }]}>+{opt.add}</Text>
                          </TouchableOpacity>
                        );
                      })}
                    </View>
                  </View>
                  <View style={styles.gapConnectorRail} />
                </View>
              );
            };

            return (
              <View>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Text style={[styles.stepTitle, { flex: 1 }]}>Step 7 — Prioritize &amp; Assess %</Text>
                  {module !== 'swot' && <AiCreditsBadge compact autoRefresh />}
                </View>
                {module !== 'swot' && (
                  <View style={pcAssess.xlsBar}>
                    <TouchableOpacity style={pcAssess.xlsBtn} onPress={handleDownloadTemplate} disabled={xlsBusy} testID="pc-xls-download">
                      <Ionicons name="download-outline" size={15} color="#1F6FEB" />
                      <Text style={pcAssess.xlsBtnText}>Download XLS</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={pcAssess.xlsBtn} onPress={handleImportTemplate} disabled={xlsBusy} testID="pc-xls-import">
                      {xlsBusy ? <ActivityIndicator size="small" color="#1F6FEB" /> : <Ionicons name="cloud-upload-outline" size={15} color="#1F6FEB" />}
                      <Text style={pcAssess.xlsBtnText}>Import XLS</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={pcAssess.xlsBtn} onPress={handleCreateGsheet} disabled={xlsBusy} testID="pc-gsheet-create">
                      <Ionicons name="logo-google" size={15} color="#0F9D58" />
                      <Text style={[pcAssess.xlsBtnText, { color: '#0F9D58' }]}>Google Sheet</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={pcAssess.xlsBtn} onPress={handleImportGsheet} disabled={xlsBusy} testID="pc-gsheet-import">
                      {xlsBusy ? <ActivityIndicator size="small" color="#0F9D58" /> : <Ionicons name="cloud-download-outline" size={15} color="#0F9D58" />}
                      <Text style={[pcAssess.xlsBtnText, { color: '#0F9D58' }]}>Import Sheet</Text>
                    </TouchableOpacity>
                  </View>
                )}
                <Text style={styles.stepHint}>
                  Bottom factor (lowest priority) = <Text style={{ fontWeight: '800' }}>10</Text>. Each step
                  up adds a per-pair gap that <Text style={{ fontWeight: '800' }}>you control individually</Text>{' '}
                  between every two factors via the toggle that appears below each card.
                  Default gap is 100% (+10); change any one to tighten (50%) or widen (200%) just that pair.
                </Text>

                <View style={{ flexDirection: 'row', gap: 10, marginBottom: 8 }}>
                  <TouchableOpacity
                    onPress={() => setStep7ExpandedIds(new Set([...mandatoryFactors, ...optionalFactors].map(ff => ff.id)))}
                    style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: COLORS.primary, borderRadius: 10, paddingVertical: 11 }}
                    accessibilityLabel="Expand all factors to assess"
                  >
                    <Ionicons name="create-outline" size={16} color="#fff" />
                    <Text style={{ color: '#fff', fontWeight: '800', fontSize: 13 }}>Assess all</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    onPress={() => setStep7ExpandedIds(new Set())}
                    style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, borderWidth: 1.5, borderColor: COLORS.primary, borderRadius: 10, paddingVertical: 10 }}
                    accessibilityLabel="Collapse all factors"
                  >
                    <Ionicons name="contract-outline" size={16} color={COLORS.primary} />
                    <Text style={{ color: COLORS.primary, fontWeight: '800', fontSize: 13 }}>Collapse all</Text>
                  </TouchableOpacity>
                </View>
                <Text style={{ fontSize: 11.5, color: COLORS.textDim, marginBottom: 12, lineHeight: 17 }}>
                  Factors are collapsed for easy re-prioritization. Tap <Text style={{ fontWeight: '800' }}>Assess</Text> on a factor (or “Assess all”) to enter the Satisfaction % for each option.
                </Text>

                {/* ─── Mandatory (A) section ─── */}
                <View style={styles.sectionBox}>
                  <View style={[styles.sectionHeader, { backgroundColor: COLORS.mandatory }]}>
                    <View style={styles.sectionHeaderBadge}>
                      <Text style={styles.sectionHeaderBadgeText}>A</Text>
                    </View>
                    <Text style={styles.sectionHeaderTitle}>Mandatory factors</Text>
                    <Text style={styles.sectionHeaderCount}>{mandatoryFactors.length}</Text>
                  </View>
                  {mandatoryFactors.length === 0 ? (
                    <Text style={styles.sectionEmpty}>
                      No factors marked Mandatory in Step 6. Go back to Step 6 to mark must-haves.
                    </Text>
                  ) : (
                    mandatoryFactors.map((f, i) => (
                      <React.Fragment key={`mand-${f.id}`}>
                        {renderCard(f, i, mandatoryFactors, 'A')}
                        {f.id !== bottomMostId && renderGapConnector(f)}
                      </React.Fragment>
                    ))
                  )}
                </View>

                {/* ─── Optional (B) section ─── */}
                <View style={styles.sectionBox}>
                  <View style={[styles.sectionHeader, { backgroundColor: COLORS.optional }]}>
                    <View style={styles.sectionHeaderBadge}>
                      <Text style={styles.sectionHeaderBadgeText}>B</Text>
                    </View>
                    <Text style={styles.sectionHeaderTitle}>Optional factors</Text>
                    <Text style={styles.sectionHeaderCount}>{optionalFactors.length}</Text>
                  </View>
                  {optionalFactors.length === 0 ? (
                    <Text style={styles.sectionEmpty}>
                      No Optional factors. Mandatory factors will dominate the score; that’s fine.
                    </Text>
                  ) : (
                    optionalFactors.map((f, i) => (
                      <React.Fragment key={`opt-${f.id}`}>
                        {renderCard(f, i, optionalFactors, 'B')}
                        {f.id !== bottomMostId && renderGapConnector(f)}
                      </React.Fragment>
                    ))
                  )}
                </View>

                <NextBack onBack={() => persistStep(6)} onNext={() => persistStep(8)} />
              </View>
            );
          })()}

          {/* ────── STEP 8 ────── */}
          {step === 8 && (() => {
            // Collab affordances + continue-elsewhere CTA panel render after
            // the step 8 body. Both are conditional on a saved analysis id.
            // ── Case-1 max possible score = sum of std_ratings of all main factors.
            // Used internally as the denominator for % computation; not displayed
            // (per UX feedback — keep the math implicit).
            const maxScore = directFactors.reduce(
              (sum, f) => sum + (Number(f.std_rating) || 0),
              0,
            );

            // ── CASE-2 (MPPS) Score: per option, sum over main factors of
            //    effective_assess% × std_rating / 100, where
            //    effective_assess% = clamp(0..100, Step 7 assess% + Step 8 improvement_pct).
            //
            // improvement_pct is a DELTA in percentage points:
            //   +20 → this option will be 20pp BETTER post-improvement
            //   −10 → this option will be 10pp WORSE post-improvement
            //    0  → no change → Case-2 falls back to Case-1
            //
            // With empty Step 8, Case-2 score === Case-1 (Step 7) score.
            const case2ScoreByOpt: Record<string, number> = {};
            const case1ScoreByOpt: Record<string, number> = {};
            analysis.options.forEach(o => {
              let c2 = 0, c1 = 0;
              directFactors.forEach(f => {
                const cell = (analysis.assessments?.[o.id] || {})[f.id] || {};
                const a7 = Number(cell.assessment_pct) || 0;
                const delta = Number(cell.improvement_pct) || 0;
                const std = Number(f.std_rating) || 0;
                const effective = Math.max(0, Math.min(100, a7 + delta));
                c1 += (a7 * std) / 100;
                c2 += (effective * std) / 100;
              });
              case1ScoreByOpt[o.id] = c1;
              case2ScoreByOpt[o.id] = c2;
            });

            // ── Case-2 split %: per option, split into Mandatory (A) and
            //    Optional (B) sub-sections — matches the manual spreadsheet's
            //    row-9 (A subtotal) and row-20 (B subtotal) percentages.
            //
            //    A% = sum(effective_assess% × std / 100 for mandatory factors)
            //         ÷ sum(std for mandatory factors) × 100
            //    B% = same with optional factors
            //
            //    Section-empty (no mandatory factors at all, or no optional)
            //    returns null so we render "—" instead of NaN.
            const mandFactors = directFactors.filter(f => f.notation === 'mandatory');
            const optFactors  = directFactors.filter(f => f.notation !== 'mandatory');
            const sectionPctByOpt: Record<string, { a: number | null; b: number | null }> = {};
            analysis.options.forEach(o => {
              const calcPct = (subset: Factor[]): number | null => {
                if (!subset.length) return null;
                let num = 0, den = 0;
                subset.forEach(f => {
                  const cell = (analysis.assessments?.[o.id] || {})[f.id] || {};
                  const a7 = Number(cell.assessment_pct) || 0;
                  const d  = Number(cell.improvement_pct) || 0;
                  const std = Number(f.std_rating) || 0;
                  const eff = Math.max(0, Math.min(100, a7 + d));
                  num += (eff * std) / 100;
                  den += std;
                });
                return den > 0 ? (num / den) * 100 : null;
              };
              sectionPctByOpt[o.id] = { a: calcPct(mandFactors), b: calcPct(optFactors) };
            });
            // listing order; disqualified options pushed to bottom with no rank).
            const rankByOptId: Record<string, number | null> = {};
            const qualified = analysis.options
              .map((o, originalIdx) => ({
                id: o.id,
                score: case2ScoreByOpt[o.id] || 0,
                disqualified: !!rollupByOpt[o.id]?.disqualified,
                originalIdx,
              }))
              .filter(x => !x.disqualified)
              .sort((a, b) => b.score - a.score || a.originalIdx - b.originalIdx);
            qualified.forEach((q, i) => { rankByOptId[q.id] = i + 1; });
            analysis.options.forEach(o => {
              if (rollupByOpt[o.id]?.disqualified) rankByOptId[o.id] = null;
            });

            // ── MPPS Max Time for Improvement (stored on analysis.config) ──
            const mppsValue = analysis.config?.mpps_max_time_value ?? '';
            const mppsUnit = analysis.config?.mpps_max_time_unit || 'Months';
            const persistMpps = async (patch: { mpps_max_time_value?: number | null; mpps_max_time_unit?: string }) => {
              if (!id) return;
              try { await api.put(`${base}/${id}/config`, patch); await reload(); }
              catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed to save'); }
            };

            return (
            <View>
              <Text style={styles.stepTitle}>Step 8 — Detailed Assessment &amp; Final Score</Text>
              <Text style={styles.stepHint}>
                Review &amp; capture improvement potential per factor &amp; option. Score reflects
                the Max Possible Practical Solution (MPPS) — i.e., the projected score if the
                stated improvements happen within your Max Time below.
              </Text>

              {/* Per-option overall card */}
              <View style={styles.card}>
                <Text style={styles.sectionTitle}>Overall score per option (Case-2 / MPPS)</Text>
                {analysis.options.map(o => {
                  const score = case2ScoreByOpt[o.id] || 0;
                  const baseline = case1ScoreByOpt[o.id] || 0;
                  const overallPct = maxScore > 0 ? (score / maxScore) * 100 : 0;
                  const delta = score - baseline;
                  const dqd = !!rollupByOpt[o.id]?.disqualified;
                  return (
                    <View key={o.id} style={styles.overallRow}>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.factorName}>{o.name}</Text>
                        {dqd ? (
                          <Text style={{ color: COLORS.con, fontSize: 12 }}>Disqualified (Mandatory factor below threshold)</Text>
                        ) : rankByOptId[o.id] ? (
                          <Text style={{ color: COLORS.ok, fontSize: 12 }}>Rank #{rankByOptId[o.id]}</Text>
                        ) : null}
                      </View>
                      <View style={{ alignItems: 'flex-end' }}>
                        <Text style={styles.overallPct}>{overallPct.toFixed(1)}%</Text>
                        <Text style={styles.cellLabel}>Score: {score.toFixed(0)}</Text>
                        {/* A / B section split — matches spreadsheet's
                            yellow-row (A subtotal) and grey-row (B subtotal) */}
                        {(() => {
                          const sp = sectionPctByOpt[o.id] || { a: null, b: null };
                          if (sp.a === null && sp.b === null) return null;
                          return (
                            <View style={{ flexDirection: 'row', gap: 6, marginTop: 2 }}>
                              {sp.a !== null && (
                                <Text style={styles.sectionPctA}>A {sp.a.toFixed(1)}%</Text>
                              )}
                              {sp.a !== null && sp.b !== null && (
                                <Text style={styles.sectionPctSep}>·</Text>
                              )}
                              {sp.b !== null && (
                                <Text style={styles.sectionPctB}>B {sp.b.toFixed(1)}%</Text>
                              )}
                            </View>
                          );
                        })()}
                        {Math.abs(delta) >= 0.5 && (
                          <Text style={{ fontSize: 11, fontWeight: '700', color: delta > 0 ? COLORS.ok : COLORS.con }}>
                            {delta > 0 ? '▲' : '▼'} {Math.abs(delta).toFixed(0)} vs Case-1
                          </Text>
                        )}
                      </View>
                    </View>
                  );
                })}
                <TouchableOpacity style={[styles.primaryBtn, { marginTop: 12 }]} onPress={runAggregate}>
                  <Ionicons name="refresh" size={16} color="#fff" />
                  <Text style={styles.primaryBtnText}>Recompute</Text>
                </TouchableOpacity>
              </View>

              {/* ─── Case-2 (MPPS) section header + Max Time for Improvement input ─── */}
              <View style={styles.case2Header}>
                <Text style={styles.case2Title}>Case-2 Analysis for Max Possible Practical Solution (MPPS)</Text>
                <Text style={styles.case2Sub}>
                  Estimate the realistic improvement on each factor &amp; option, assuming you
                  have the time below to act. Empty cells fall back to Step 7 values.
                </Text>
                <View style={styles.mppsRow}>
                  <Text style={styles.mppsLabel}>Max Time for Improvement</Text>
                  {/* DebouncedInput here too — raw onEndEditing didn't fire
                      on web when the user typed a value then immediately
                      clicked a unit chip / Recompute, causing the value to
                      be lost on refresh. */}
                  <DebouncedInput
                    value={mppsValue === null || mppsValue === undefined || mppsValue === '' ? '' : String(mppsValue)}
                    placeholder="0.0"
                    keyboardType="decimal-pad"
                    style={[styles.inputSm, { width: 90, textAlign: 'center', fontWeight: '700' }]}
                    onSave={(text) => {
                      const t = text.trim();
                      if (t === '') { persistMpps({ mpps_max_time_value: null }); return; }
                      let v = parseFloat(t);
                      if (Number.isNaN(v) || v < 0) v = 0;
                      // Clamp + round to 1 decimal
                      v = Math.round(Math.min(9999, v) * 10) / 10;
                      persistMpps({ mpps_max_time_value: v });
                    }}
                  />
                  <View style={styles.mppsUnitRow}>
                    {(['Hours', 'Days', 'Weeks', 'Months', 'Years'] as const).map(u => {
                      const on = mppsUnit === u;
                      return (
                        <TouchableOpacity
                          key={u}
                          style={[styles.mppsUnitBtn, on && styles.mppsUnitBtnOn]}
                          onPress={() => persistMpps({ mpps_max_time_unit: u })}
                        >
                          <Text style={[styles.mppsUnitText, on && { color: '#fff' }]}>{u}</Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                </View>
              </View>

              {/* Per-factor detail — main factors only. Sub-factors shown read-only inside each card. */}
              {directFactors.map((f, idx) => (
                <FactorAssessmentCard key={f.id} factor={f} factorIndex={idx + 1} options={analysis.options}
                  cells={(analysis.assessments || {})}
                  displayName={displayName(f)}
                  subs={childrenOf(f.id)}
                  subDisplayNameOf={displayName}
                  subHasRenameOf={hasRename}
                  subOriginalNameOf={originalName}
                  onFactorUpdate={(patch) => updateFactor(f.id, patch)}
                  onCellUpdate={(oid, patch) => upsertCell(oid, f.id, patch)} />
              ))}

              <TouchableOpacity style={[styles.bigCta, { marginTop: 16 }]} onPress={() => setShowGuidelines(true)}>
                <LinearGradient colors={['#0ea5e9', '#6366F1']} style={styles.bigCtaGrad}>
                  <Ionicons name="bulb" size={22} color="#fff" />
                  <Text style={styles.bigCtaText}>Show Final Decision Guidelines</Text>
                </LinearGradient>
              </TouchableOpacity>

              {/* ─── FINAL DECISION CAPTURE ─────────────────────────────
                  Persisted on analysis.config so it travels with the doc
                  and shows up later in Solution Box for review.
                  - final_choice_option_id : which option the user picked
                  - final_choice_reason    : free-text justification (optional)
                  - final_choice_decided_at: ISO timestamp set when option picked
                  - review_timeline_value/unit: "by when can we judge whether
                    the decision was right?" — independent of MPPS time. */}
              {(() => {
                const cfg: any = analysis.config || {};
                const chosenOptId: string | null = cfg.final_choice_option_id || null;
                const reasonText: string = cfg.final_choice_reason || '';
                const rtValue = cfg.review_timeline_value;
                const rtUnit: string = cfg.review_timeline_unit || 'Months';
                const decidedAt: string | null = cfg.final_choice_decided_at || null;

                const persistFinal = async (patch: Record<string, any>) => {
                  if (!id) return;
                  try { await api.put(`${base}/${id}/config`, patch); await reload(); }
                  catch (e: any) { showAlert('Error', e?.response?.data?.detail || 'Failed to save'); }
                };
                const pickOption = (optId: string) => {
                  persistFinal({
                    final_choice_option_id: optId,
                    final_choice_decided_at: new Date().toISOString(),
                  });
                };

                return (
                  <View style={styles.finalCard}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <Ionicons name="trophy" size={18} color="#92400E" />
                      <Text style={styles.finalTitle}>Final Decision</Text>
                    </View>
                    <Text style={styles.finalSub}>
                      Lock in the option you’re going with, jot down why (optional),
                      and set a date by which you’ll review whether the call was right.
                    </Text>

                    {/* Option chooser — radio-style chips */}
                    <Text style={styles.finalLabel}>I choose</Text>
                    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
                      {analysis.options.map(o => {
                        const on = chosenOptId === o.id;
                        const r = rankByOptId[o.id];
                        return (
                          <TouchableOpacity
                            key={o.id}
                            style={[styles.finalOptChip, on && styles.finalOptChipOn]}
                            onPress={() => pickOption(o.id)}
                          >
                            <Ionicons
                              name={on ? 'radio-button-on' : 'radio-button-off'}
                              size={14}
                              color={on ? '#fff' : COLORS.textDim}
                            />
                            <Text style={[styles.finalOptChipText, on && { color: '#fff' }]} numberOfLines={1}>
                              {o.name}{r ? ` · Rank #${r}` : ''}
                            </Text>
                          </TouchableOpacity>
                        );
                      })}
                      {chosenOptId && (
                        <TouchableOpacity
                          style={[styles.finalOptChip, { backgroundColor: '#FEE2E2', borderColor: '#FCA5A5' }]}
                          onPress={() => persistFinal({ final_choice_option_id: null, final_choice_decided_at: null })}
                        >
                          <Ionicons name="close-circle" size={14} color={COLORS.con} />
                          <Text style={[styles.finalOptChipText, { color: COLORS.con }]}>Clear</Text>
                        </TouchableOpacity>
                      )}
                    </View>

                    {/* Reason (optional) */}
                    <Text style={[styles.finalLabel, { marginTop: 12 }]}>
                      Why I chose this <Text style={{ color: COLORS.textDim, fontWeight: '500' }}>(optional)</Text>
                    </Text>
                    <DebouncedInput
                      value={reasonText}
                      placeholder="e.g., Best balance of pay, growth, and proximity. Bharath has stronger long-term growth so I'll re-evaluate after 6 months."
                      multiline
                      style={[styles.finalReason]}
                      onSave={(text) => persistFinal({ final_choice_reason: text })}
                    />

                    {/* Review timeline */}
                    <Text style={[styles.finalLabel, { marginTop: 12 }]}>Review the decision in</Text>
                    <View style={[styles.mppsRow, { marginTop: 6 }]}>
                      <DebouncedInput
                        value={rtValue === null || rtValue === undefined || rtValue === '' ? '' : String(rtValue)}
                        placeholder="0.0"
                        keyboardType="decimal-pad"
                        style={[styles.inputSm, { width: 90, textAlign: 'center', fontWeight: '700' }]}
                        onSave={(text) => {
                          const t = text.trim();
                          if (t === '') { persistFinal({ review_timeline_value: null }); return; }
                          let v = parseFloat(t);
                          if (Number.isNaN(v) || v < 0) v = 0;
                          v = Math.round(Math.min(9999, v) * 10) / 10;
                          persistFinal({ review_timeline_value: v });
                        }}
                      />
                      <View style={styles.mppsUnitRow}>
                        {(['Hours', 'Days', 'Weeks', 'Months', 'Years'] as const).map(u => {
                          const on = rtUnit === u;
                          return (
                            <TouchableOpacity
                              key={u}
                              style={[styles.mppsUnitBtn, on && styles.mppsUnitBtnOn]}
                              onPress={() => persistFinal({ review_timeline_unit: u })}
                            >
                              <Text style={[styles.mppsUnitText, on && { color: '#fff' }]}>{u}</Text>
                            </TouchableOpacity>
                          );
                        })}
                      </View>
                    </View>

                    {decidedAt && (
                      <Text style={styles.finalStamp}>
                        Decided on {new Date(decidedAt).toLocaleString()}
                      </Text>
                    )}

                    {analysis?.id ? (
                      <ModuleStoreActions
                        module="pros_cons"
                        decisionId={analysis.id}
                        lifeAreaId={(analysis as any)?.life_area_id || (analysis as any)?.life_area || null}
                        subAreaId={(analysis as any)?.sub_area_id || null}
                      />
                    ) : null}

                    {/* ─── Action Plan capture (Phase B) ─── */}
                    {analysis?.id ? (
                      <ActionItemEditor
                        key={pcActionKey}
                        sourceModule="PROS_CONS"
                        sourceId={analysis.id}
                        sourceLabel={`Pros & Cons · ${(analysis as any)?.title || ''}`}
                        defaultLifeArea={(analysis as any)?.life_area || ''}
                        title="Action Plan — Who · What · By When"
                      />
                    ) : null}

                    {/* Document Learnings — pre-fills the Learning Journal
                        with this Pros & Cons decision (module + linked item). */}
                    {analysis?.id ? (
                      <TouchableOpacity
                        onPress={() => router.push({ pathname: '/(tabs)/journal', params: { linkModule: 'pros_cons', linkId: analysis.id, linkTitle: (analysis as any)?.title || 'Pros & Cons' } } as any)}
                        style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, backgroundColor: '#FFFBEB', borderWidth: 1.5, borderColor: '#F59E0B', borderRadius: 12, paddingVertical: 13, marginTop: 16 }}
                      >
                        <Ionicons name="book" size={18} color="#B45309" />
                        <Text style={{ fontSize: 14, fontWeight: '700', color: '#B45309' }}>Document Learnings</Text>
                      </TouchableOpacity>
                    ) : null}
                  </View>
                );
              })()}
              <NextBack onBack={() => persistStep(7)} onNext={null} />
              {id && (
                <DecisionContinuePanel
                  sourceModule="pros-cons"
                  sourceDecisionId={id}
                  title={analysis?.title || 'Pros & Cons'}
                  contextSummary={`From your 8-Step Pros & Cons analysis.`}
                />
              )}
            </View>
            );
          })()}

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

      {/* Step 5 — Auto-Fetch Data Source configuration (full parity w/ My Dezider) */}
      <DataSourceModal
        factor={dsFactor}
        onClose={() => setDsFactor(null)}
        onSave={(fid, ds) => {
          updateFactor(fid, { data_source: ds });
          setDsFactor(null);
        }}
      />
      {contributionMode && <LiveSessionPill shareId={contribShareId as string} />}
    </SafeAreaView>
  );
}
