/**
 * Simple Solution Finder — v2 schema (June 2026 overhaul).
 *
 *   Concerns (⭐ promote to PRIMARY)            ← Q1 (a) + (b)
 *      └─ Root Cause Analysis (per primary)     ← Q2
 *           └─ Solutions (per RCA)              ← Q3   [→ Send to ASM]
 *                └─ Risks (Impact% × Probability% = Index%)  ← Q4 (a)
 *                     ├─ Mitigations (1..many)  ← Q4 (b)  [→ Send to ASM]
 *                     └─ Contingencies (1..many) ← Q4 (c) [→ Send to ASM]
 *   Action Plan = Solutions + Mitigations + Contingencies → Action Center → CTT / Lifestyle.
 *
 * Cross-references:
 *  - Promoted to a first-class dashboard module (Pros&Cons / SWOT row).
 *  - Still launchable from inside GEM goals (gem-goal.tsx → launchSolutionFinder).
 *  - "Send to ASM" pills hand a deeper-analysis context to /tools/solution-matrix.
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, KeyboardAvoidingView, Platform, Modal,
} from 'react-native';
import { useRouter, useLocalSearchParams, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { showAlert } from '../../src/utils/alert';
import { COLORS } from '../../src/constants/colors';
import { useAuthStore } from '../../src/store/authStore';
import api from '../../src/utils/api';
import TimingFieldset, { TimingValue } from '../../src/components/decisions/TimingFieldset';
import { addDaysISO } from '../../src/utils/dateLocalize';

// ============== CONSTANTS ==============
const LIFE_AREAS = [
  { id: 'career', name: 'Career', icon: 'briefcase' },
  { id: 'finance', name: 'Finance', icon: 'cash' },
  { id: 'relationships', name: 'Relationships', icon: 'heart' },
  { id: 'holistic_health', name: 'Holistic Health', icon: 'fitness' },
  { id: 'assets', name: 'Assets', icon: 'home' },
  { id: 'knowledge_skills', name: 'Knowledge & Skills', icon: 'school' },
  { id: 'social_image', name: 'Social Image', icon: 'people' },
  { id: 'social_contributions', name: 'Social Contributions', icon: 'globe' },
  { id: 'hobbies_entertainment', name: 'Hobbies', icon: 'game-controller' },
  { id: 'spirituality_religion', name: 'Spirituality', icon: 'leaf' },
];

const STEPS = [
  { title: 'Goal',         icon: 'flag' },
  { title: 'Concerns',     icon: 'alert-circle' },
  { title: 'RCA',          icon: 'git-branch' },
  { title: 'Solutions',    icon: 'bulb' },
  { title: 'Risks',        icon: 'shield-checkmark' },
  { title: 'Action Plan',  icon: 'rocket' },
];

// ============== TYPES ==============
interface Concern { id: string; text: string; is_primary: boolean; order: number; }
interface RootCause { id: string; concern_id: string; text: string; }
interface Solution { id: string; rca_id: string; text: string; capabilities?: string; resources?: string; }
interface Risk {
  id: string; sol_id: string; name: string;
  impact_pct?: number; probability_pct?: number; risk_index_pct?: number;
}
interface Mitigation { id: string; risk_id: string; text: string; }
interface Contingency { id: string; risk_id: string; text: string; }
interface APItem {
  ap_id: string;
  source_type: 'solution' | 'mitigation' | 'contingency';
  source_id: string;
  text: string;
  who?: string;
  by_when?: string;
  status?: string;
  pushed_to_action_center?: boolean;
  action_id?: string;
  pushed_to_ctt?: boolean;
  pushed_to_lifestyle?: boolean;
  push_ctt?: boolean;       // selected-but-not-yet-pushed flag (UI only)
  push_lifestyle?: boolean;
}

// ============== HELPERS ==============
const uid = () => Math.random().toString(36).slice(2, 10);
const clampPct = (n: any): number | undefined => {
  const x = parseInt(String(n ?? '').replace(/[^0-9]/g, ''), 10);
  if (isNaN(x)) return undefined;
  return Math.min(100, Math.max(0, x));
};

// ============== COMPONENT ==============
export default function SimpleSolutionFinder() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const editId = params.id as string | undefined;
  // Hydration gate — auth store rehydrates async from secure storage; we must
  // NOT fire any /api calls until the user is loaded, else the auto-save on
  // step transitions blows up with a 401 on cold deep-link to this page.
  const user = useAuthStore(st => st.user);
  const authHydrated = !!user;

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedId, setSavedId] = useState<string | null>(editId || null);
  const [step, setStep] = useState(0);

  // Step 0 — Goal
  const [areaOfLife, setAreaOfLife] = useState('');
  const [smartGoal, setSmartGoal] = useState('');
  const [timing, setTiming] = useState<TimingValue>({
    deadline_date: addDaysISO(7), impact_horizon_value: 7, impact_horizon_unit: 'days',
  });

  // Step 1..4 — structured tree
  const [concerns, setConcerns] = useState<Concern[]>([]);
  const [rootCauses, setRootCauses] = useState<RootCause[]>([]);
  const [solutions, setSolutions] = useState<Solution[]>([]);
  const [contacts, setContacts] = useState<any[]>([]);
  const [capPicker, setCapPicker] = useState<{ open: boolean; rcaId: string | null }>({ open: false, rcaId: null });
  const [risks, setRisks] = useState<Risk[]>([]);
  const [mitigations, setMitigations] = useState<Mitigation[]>([]);
  const [contingencies, setContingencies] = useState<Contingency[]>([]);
  const [actionPlan, setActionPlan] = useState<APItem[]>([]);
  // Reverse hook — counts of ASM deep-dives per Q3/Q4b/Q4c row keyed by source_id.
  const [asmCounts, setAsmCounts] = useState<Record<string, number>>({});

  // Per-row "draft" inputs (so adding doesn't require a modal)
  const [newConcernText, setNewConcernText] = useState('');
  const [newRcaText, setNewRcaText] = useState<Record<string, string>>({});
  const [newSolText, setNewSolText] = useState<Record<string, string>>({});
  const [newRiskText, setNewRiskText] = useState<Record<string, string>>({});
  const [newMitText, setNewMitText] = useState<Record<string, string>>({});
  const [newConText, setNewConText] = useState<Record<string, string>>({});

  // ============ DERIVED ============
  const primaryConcerns = useMemo(
    () => concerns.filter(c => c.is_primary).sort((a, b) => a.order - b.order),
    [concerns]
  );
  const rcasFor = (cid: string) => rootCauses.filter(r => r.concern_id === cid);
  const solsFor = (rid: string) => solutions.filter(s => s.rca_id === rid);
  const risksFor = (sid: string) => risks.filter(r => r.sol_id === sid);
  const mitsFor = (riskId: string) => mitigations.filter(m => m.risk_id === riskId);
  const consFor = (riskId: string) => contingencies.filter(c => c.risk_id === riskId);

  // ============ LOAD ============
  useEffect(() => {
    // Gate load on auth hydration to avoid the cold-deep-link 401 race.
    if (editId && authHydrated) loadEntry();
  }, [editId, authHydrated]);

  const loadEntry = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/solution-finders/${editId}`);
      const d = res.data;
      setAreaOfLife(d.area_of_life || '');
      setSmartGoal(d.smart_goal || '');
      setTiming({
        deadline_date: d.deadline_date || addDaysISO(7),
        impact_horizon_value: d.impact_horizon_value ?? 7,
        impact_horizon_unit: d.impact_horizon_unit || 'days',
      });
      setConcerns(d.concerns || []);
      setRootCauses(d.root_causes || []);
      setSolutions(d.solutions || []);
      setRisks(d.risks || []);
      setMitigations(d.mitigations || []);
      setContingencies(d.contingencies || []);
      setActionPlan(d.action_plan_items || []);
    } catch (e) {
      showAlert('Error', 'Failed to load entry');
    } finally { setLoading(false); }
  };

  // Reverse hook fetch — keeps ASM deep-dive counts fresh for the badges next
  // to Solutions / Mitigations / Contingencies. Re-runs whenever the screen
  // regains focus (e.g. user came back from /tools/solution-matrix after a
  // "Send to ASM" round-trip).
  const fetchAsmCounts = useCallback(async (id: string | null | undefined) => {
    if (!id || !authHydrated) return;
    try {
      const r = await api.get(`/solution-finders/${id}/asm-links`);
      setAsmCounts(r.data || {});
    } catch {
      /* silent — badge is purely informational */
    }
  }, [authHydrated]);

  useEffect(() => {
    fetchAsmCounts(savedId);
  }, [savedId, fetchAsmCounts]);

  useFocusEffect(useCallback(() => {
    if (savedId) fetchAsmCounts(savedId);
  }, [savedId, fetchAsmCounts]));

  // ============ SAVE ============
  const buildPayload = (statusOverride?: string) => ({
    area_of_life: areaOfLife,
    smart_goal: smartGoal,
    deadline_date: timing.deadline_date || null,
    impact_horizon_value: timing.impact_horizon_value ?? null,
    impact_horizon_unit: timing.impact_horizon_unit || null,
    concerns,
    root_causes: rootCauses,
    solutions,
    risks,
    mitigations,
    contingencies,
    action_plan_items: actionPlan,
    schema_version: 2,
    ...(statusOverride ? { status: statusOverride } : {}),
  });

  const handleSave = useCallback(async (silent = false, statusOverride?: string): Promise<string | null> => {
    // Skip silently if auth isn't ready yet — caller will get a null and the
    // step transition still works locally; data persists on the next save.
    if (!authHydrated) return null;
    if (!areaOfLife) {
      if (!silent) showAlert('Required', 'Pick a life area.');
      return null;
    }
    if (!smartGoal.trim()) {
      if (!silent) showAlert('Required', 'Enter your SMART goal.');
      return null;
    }
    setSaving(true);
    try {
      const payload = buildPayload(statusOverride);
      let id = savedId;
      if (id) {
        await api.put(`/solution-finders/${id}`, payload);
      } else {
        const r = await api.post('/solution-finders', payload);
        id = r.data.entry_id;
        setSavedId(id);
      }
      return id;
    } catch (e: any) {
      if (!silent) showAlert('Save failed', e?.response?.data?.detail || 'Try again');
      return null;
    } finally { setSaving(false); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [savedId, areaOfLife, smartGoal, timing, concerns, rootCauses, solutions, risks, mitigations, contingencies, actionPlan, authHydrated]);

  // ============ CRUD HELPERS ============
  const addConcern = () => {
    const t = newConcernText.trim();
    if (!t) return;
    setConcerns(prev => [...prev, { id: uid(), text: t, is_primary: false, order: prev.length }]);
    setNewConcernText('');
  };
  const togglePrimary = (cid: string) =>
    setConcerns(prev => prev.map(c => c.id === cid ? { ...c, is_primary: !c.is_primary } : c));
  const editConcern = (cid: string, text: string) =>
    setConcerns(prev => prev.map(c => c.id === cid ? { ...c, text } : c));
  const removeConcern = (cid: string) => {
    setConcerns(prev => prev.filter(c => c.id !== cid));
    // Cascade: drop RCAs / solutions / risks / mitigations / contingencies tied to it.
    const rcaIds = rootCauses.filter(r => r.concern_id === cid).map(r => r.id);
    const solIds = solutions.filter(s => rcaIds.includes(s.rca_id)).map(s => s.id);
    const riskIds = risks.filter(r => solIds.includes(r.sol_id)).map(r => r.id);
    setRootCauses(prev => prev.filter(r => r.concern_id !== cid));
    setSolutions(prev => prev.filter(s => !rcaIds.includes(s.rca_id)));
    setRisks(prev => prev.filter(r => !solIds.includes(r.sol_id)));
    setMitigations(prev => prev.filter(m => !riskIds.includes(m.risk_id)));
    setContingencies(prev => prev.filter(c => !riskIds.includes(c.risk_id)));
  };

  const addRca = (cid: string) => {
    const t = (newRcaText[cid] || '').trim(); if (!t) return;
    setRootCauses(prev => [...prev, { id: uid(), concern_id: cid, text: t }]);
    setNewRcaText(prev => ({ ...prev, [cid]: '' }));
  };
  const removeRca = (rid: string) => {
    const solIds = solutions.filter(s => s.rca_id === rid).map(s => s.id);
    const riskIds = risks.filter(r => solIds.includes(r.sol_id)).map(r => r.id);
    setRootCauses(prev => prev.filter(r => r.id !== rid));
    setSolutions(prev => prev.filter(s => s.rca_id !== rid));
    setRisks(prev => prev.filter(r => !solIds.includes(r.sol_id)));
    setMitigations(prev => prev.filter(m => !riskIds.includes(m.risk_id)));
    setContingencies(prev => prev.filter(c => !riskIds.includes(c.risk_id)));
  };
  const editRca = (rid: string, text: string) =>
    setRootCauses(prev => prev.map(r => r.id === rid ? { ...r, text } : r));

  const addSolution = (rcaId: string) => {
    const t = (newSolText[rcaId] || '').trim(); if (!t) return;
    setSolutions(prev => [...prev, { id: uid(), rca_id: rcaId, text: t }]);
    setNewSolText(prev => ({ ...prev, [rcaId]: '' }));
  };
  const editSolution = (sid: string, patch: Partial<Solution>) =>
    setSolutions(prev => prev.map(s => s.id === sid ? { ...s, ...patch } : s));
  const removeSolution = (sid: string) => {
    const riskIds = risks.filter(r => r.sol_id === sid).map(r => r.id);
    setSolutions(prev => prev.filter(s => s.id !== sid));
    setRisks(prev => prev.filter(r => r.sol_id !== sid));
    setMitigations(prev => prev.filter(m => !riskIds.includes(m.risk_id)));
    setContingencies(prev => prev.filter(c => !riskIds.includes(c.risk_id)));
  };

  // ── Q3: pull skills / resources from Self (Contact-Self) and other contacts ──
  useEffect(() => {
    (async () => {
      try {
        const res = await api.get('/contacts?limit=100');
        setContacts(res.data?.contacts || res.data?.items || res.data || []);
      } catch (e) { /* non-fatal */ }
    })();
  }, []);

  const resourceLines = (c: any): string[] => {
    const out: string[] = [];
    const fin = c?.resources?.finance || {};
    const cur = fin.currency || 'INR';
    if (fin.net_worth) out.push(`Net worth ${cur} ${fin.net_worth}`);
    if (fin.monthly_cashflow) out.push(`Monthly cashflow ${cur} ${fin.monthly_cashflow}`);
    if (fin.amount) out.push(`Funds ${cur} ${fin.amount}`);
    const infra = c?.resources?.infrastructure?.description;
    if (infra) out.push(`Infrastructure: ${infra}`);
    const people = c?.resources?.people_connects?.count;
    if (people) out.push(`People network: ${people} connects`);
    return out;
  };

  const addSolutionFromCapability = (rcaId: string, who: string, kind: 'skill' | 'resource', label: string) => {
    const isSelf = who === 'Self';
    const prefix = isSelf
      ? (kind === 'skill' ? 'Use my skill' : 'Use my resource')
      : (kind === 'skill' ? `Leverage ${who}'s skill` : `Tap ${who}'s resource`);
    const text = `${prefix}: ${label}`;
    setSolutions(prev => [...prev, {
      id: uid(), rca_id: rcaId, text,
      capabilities: kind === 'skill' ? `${who}: ${label}` : undefined,
      resources: kind === 'resource' ? `${who}: ${label}` : undefined,
    }]);
    setCapPicker({ open: false, rcaId: null });
  };

  const addRisk = (sid: string) => {
    const t = (newRiskText[sid] || '').trim(); if (!t) return;
    setRisks(prev => [...prev, { id: uid(), sol_id: sid, name: t }]);
    setNewRiskText(prev => ({ ...prev, [sid]: '' }));
  };
  const editRisk = (rid: string, patch: Partial<Risk>) =>
    setRisks(prev => prev.map(r => {
      if (r.id !== rid) return r;
      const next = { ...r, ...patch };
      const i = next.impact_pct, p = next.probability_pct;
      if (typeof i === 'number' && typeof p === 'number') {
        next.risk_index_pct = Math.round((i * p) / 100);  // both are %, index is %
      } else {
        next.risk_index_pct = undefined;
      }
      return next;
    }));
  const removeRisk = (rid: string) => {
    setRisks(prev => prev.filter(r => r.id !== rid));
    setMitigations(prev => prev.filter(m => m.risk_id !== rid));
    setContingencies(prev => prev.filter(c => c.risk_id !== rid));
  };

  const addMitigation = (riskId: string) => {
    const t = (newMitText[riskId] || '').trim(); if (!t) return;
    setMitigations(prev => [...prev, { id: uid(), risk_id: riskId, text: t }]);
    setNewMitText(prev => ({ ...prev, [riskId]: '' }));
  };
  const removeMitigation = (mid: string) =>
    setMitigations(prev => prev.filter(m => m.id !== mid));
  const editMitigation = (mid: string, text: string) =>
    setMitigations(prev => prev.map(m => m.id === mid ? { ...m, text } : m));

  const addContingency = (riskId: string) => {
    const t = (newConText[riskId] || '').trim(); if (!t) return;
    setContingencies(prev => [...prev, { id: uid(), risk_id: riskId, text: t }]);
    setNewConText(prev => ({ ...prev, [riskId]: '' }));
  };
  const removeContingency = (cid: string) =>
    setContingencies(prev => prev.filter(c => c.id !== cid));
  const editContingency = (cid: string, text: string) =>
    setContingencies(prev => prev.map(c => c.id === cid ? { ...c, text } : c));

  // ============ ACTION PLAN AGGREGATOR ============
  // Q5: derives a fresh list from solutions + mitigations + contingencies, but
  // PRESERVES any push-state already captured on existing items so re-running
  // the aggregator doesn't clobber "pushed_to_action_center" markers.
  const recomputePlan = () => {
    const next: APItem[] = [];
    const idxBy = new Map(actionPlan.map(p => [`${p.source_type}:${p.source_id}`, p]));
    const upsert = (source_type: APItem['source_type'], source_id: string, text: string) => {
      const key = `${source_type}:${source_id}`;
      const prior = idxBy.get(key);
      next.push(prior
        ? { ...prior, text }
        : { ap_id: uid(), source_type, source_id, text, status: 'pending' });
    };
    solutions.forEach(s => upsert('solution', s.id, s.text));
    mitigations.forEach(m => upsert('mitigation', m.id, m.text));
    contingencies.forEach(c => upsert('contingency', c.id, c.text));
    setActionPlan(next);
  };

  // ============ SEND-TO-ASM HOOK ============
  // Hands off context to Advanced Solution Matrix. Saves first so the SF entry
  // exists, then deep-links with the SF entry_id + the source sub-id.
  const sendToASM = async (source: 'solution' | 'mitigation' | 'contingency', sourceId: string, label: string) => {
    const id = await handleSave(true);
    if (!id) return;
    router.push({
      pathname: '/tools/solution-matrix',
      params: {
        from_sf_entry_id: id,
        from_sf_source: source,
        from_sf_source_id: sourceId,
        prefill_title: `Deep-dive: ${label.slice(0, 60)}`,
        prefill_area: areaOfLife,
      },
    } as any);
  };

  // ============ PUSH TO ACTION CENTER ============
  const togglePlanFlag = (apId: string, k: 'push_ctt' | 'push_lifestyle') =>
    setActionPlan(prev => prev.map(p => p.ap_id === apId ? { ...p, [k]: !p[k] } : p));

  const editPlanItem = (apId: string, patch: Partial<APItem>) =>
    setActionPlan(prev => prev.map(p => p.ap_id === apId ? { ...p, ...patch } : p));

  const pushAllToActionCenter = async () => {
    const id = await handleSave(true);
    if (!id) return;
    // Build per-item payload so each row only goes where the user ticked it.
    const items = actionPlan
      .filter(p => !p.pushed_to_action_center)
      .map(p => ({
        ap_id: p.ap_id,
        push_ctt: !!p.push_ctt && !p.pushed_to_ctt,
        push_lifestyle: !!p.push_lifestyle && !p.pushed_to_lifestyle,
      }));
    if (items.length === 0) {
      showAlert('Nothing to push', 'All items are already in Action Center.');
      return;
    }
    try {
      const r = await api.post(`/solution-finders/${id}/push-action-plan`, { items });
      setActionPlan(r.data.action_plan_items || []);
      showAlert('Pushed',
        `${r.data.pushed_to_action_center} to Action Center` +
        (r.data.pushed_to_ctt ? ` · ${r.data.pushed_to_ctt} to CTT` : '') +
        (r.data.pushed_to_lifestyle ? ` · ${r.data.pushed_to_lifestyle} to Lifestyle` : ''));
    } catch (e: any) {
      showAlert('Push failed', e?.response?.data?.detail || 'Try again');
    }
  };

  // ============ NAVIGATION GUARDS ============
  const canProceed = () => {
    if (step === 0) return !!areaOfLife && !!smartGoal.trim();
    if (step === 1) return concerns.some(c => c.is_primary);
    if (step === 2) return rootCauses.length > 0;
    if (step === 3) return solutions.length > 0;
    if (step === 4) return true; // risks optional
    return true;
  };

  const onNext = async () => {
    if (!canProceed()) {
      const msg =
        step === 0 ? 'Pick a life area and enter a SMART goal.'
        : step === 1 ? 'Tap the ⭐ on at least one concern to mark it as PRIMARY.'
        : step === 2 ? 'Add at least one Root Cause for a primary concern.'
        : step === 3 ? 'Add at least one Solution.'
        : 'Cannot proceed.';
      return showAlert('Step incomplete', msg);
    }
    // Auto-save on each transition (silent).
    await handleSave(true);
    if (step === 4) recomputePlan();
    setStep(s => Math.min(5, s + 1));
  };
  const onBack = () => setStep(s => Math.max(0, s - 1));

  // ============ RENDER STEPS ============
  const renderStepIndicator = () => (
    <View style={s.stepIndicator}>
      {STEPS.map((st, i) => {
        const canEdit = i <= step;                 // already reached → tappable
        return (
          <View key={st.title} style={s.stepDotWrap}>
            <TouchableOpacity
              activeOpacity={canEdit ? 0.7 : 1}
              disabled={!canEdit}
              onPress={() => { if (canEdit) setStep(i); }}
              accessibilityLabel={`Step ${i + 1}: ${st.title}`}
            >
              <View style={[s.stepDot, i <= step && s.stepDotActive]}>
                <Ionicons name={st.icon as any} size={12} color={i <= step ? '#FFF' : '#94A3B8'} />
              </View>
            </TouchableOpacity>
            {i < STEPS.length - 1 && <View style={[s.stepLine, i < step && s.stepLineActive]} />}
          </View>
        );
      })}
    </View>
  );

  const renderStep0 = () => (
    <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, paddingBottom: 80 }}>
      <Text style={s.sectionLabel}>Life Area</Text>
      <View style={s.areaGrid}>
        {LIFE_AREAS.map(a => (
          <TouchableOpacity
            key={a.id}
            style={[s.areaChip, areaOfLife === a.id && s.areaChipActive]}
            onPress={() => setAreaOfLife(a.id)}
          >
            <Ionicons name={a.icon as any} size={14} color={areaOfLife === a.id ? '#FFF' : '#475569'} />
            <Text style={[s.areaChipText, areaOfLife === a.id && { color: '#FFF' }]}>{a.name}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <Text style={s.sectionLabel}>SMART Goal</Text>
      <TextInput
        style={[s.textArea, { minHeight: 70 }]}
        multiline placeholder="Specific · Measurable · Achievable · Relevant · Time-bound"
        placeholderTextColor="#9CA3AF" value={smartGoal} onChangeText={setSmartGoal}
      />
      <View style={{ height: 12 }} />
      <TimingFieldset value={timing} onChange={setTiming} />
    </ScrollView>
  );

  const renderStep1 = () => (
    <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, paddingBottom: 80 }}>
      <Text style={s.qTitle}>Q1 (a). What are ALL your concerns?</Text>
      <Text style={s.qHint}>Tap the ⭐ next to a concern to mark it as PRIMARY (Q1 (b)). You can come back and add more stars later.</Text>
      {concerns.length === 0 && <Text style={s.empty}>No concerns yet. Add one below.</Text>}
      {concerns.map(c => (
        <View key={c.id} style={s.concernRow}>
          <TouchableOpacity onPress={() => togglePrimary(c.id)} hitSlop={8}>
            <Ionicons
              name={c.is_primary ? 'star' : 'star-outline'}
              size={22}
              color={c.is_primary ? '#F59E0B' : '#94A3B8'}
            />
          </TouchableOpacity>
          <TextInput
            style={s.concernInput}
            value={c.text}
            onChangeText={t => editConcern(c.id, t)}
            placeholder="Concern..."
            placeholderTextColor="#9CA3AF"
          />
          <TouchableOpacity onPress={() => removeConcern(c.id)} hitSlop={8}>
            <Ionicons name="close-circle" size={20} color="#CBD5E1" />
          </TouchableOpacity>
        </View>
      ))}
      <View style={s.addRow}>
        <TextInput
          style={s.addInput}
          placeholder="Add a concern..."
          placeholderTextColor="#9CA3AF"
          value={newConcernText}
          onChangeText={setNewConcernText}
          onSubmitEditing={addConcern}
        />
        <TouchableOpacity style={s.addBtn} onPress={addConcern}>
          <Ionicons name="add" size={20} color="#FFF" />
        </TouchableOpacity>
      </View>
      {primaryConcerns.length > 0 && (
        <View style={s.previewBox}>
          <Text style={s.previewTitle}>Q1 (b). PRIMARY concerns ({primaryConcerns.length})</Text>
          {primaryConcerns.map((c, i) => (
            <Text key={c.id} style={s.previewItem}>{i + 1}. {c.text}</Text>
          ))}
        </View>
      )}
    </ScrollView>
  );

  const renderStep2 = () => (
    <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, paddingBottom: 80 }}>
      <Text style={s.qTitle}>Q2. Root Cause Analysis</Text>
      <Text style={s.qHint}>For each PRIMARY concern, list the root causes (1 to many).</Text>
      {primaryConcerns.length === 0 && (
        <Text style={s.empty}>No primary concerns yet. Go back to Q1 and tap ⭐ to mark some.</Text>
      )}
      {primaryConcerns.map((c, i) => (
        <View key={c.id} style={s.groupCard}>
          <Text style={s.groupTitle}>{i + 1}. {c.text}</Text>
          {rcasFor(c.id).map(r => (
            <View key={r.id} style={s.childRow}>
              <View style={s.bullet} />
              <TextInput
                style={s.childInput}
                value={r.text}
                onChangeText={t => editRca(r.id, t)}
                placeholder="Root cause..."
                placeholderTextColor="#9CA3AF"
                multiline
              />
              <Ionicons name="pencil" size={12} color="#94A3B8" />
              <TouchableOpacity onPress={() => removeRca(r.id)} hitSlop={6}>
                <Ionicons name="close" size={16} color="#94A3B8" />
              </TouchableOpacity>
            </View>
          ))}
          <View style={s.addRow}>
            <TextInput
              style={s.addInput}
              placeholder="Add a root cause..."
              placeholderTextColor="#9CA3AF"
              value={newRcaText[c.id] || ''}
              onChangeText={t => setNewRcaText(prev => ({ ...prev, [c.id]: t }))}
              onSubmitEditing={() => addRca(c.id)}
            />
            <TouchableOpacity style={s.addBtn} onPress={() => addRca(c.id)}>
              <Ionicons name="add" size={18} color="#FFF" />
            </TouchableOpacity>
          </View>
        </View>
      ))}
    </ScrollView>
  );

  const renderStep3 = () => (
    <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, paddingBottom: 80 }}>
      <Text style={s.qTitle}>Q3. Solutions within your Current Capabilities & Resources</Text>
      <Text style={s.qHint}>For each Root Cause, list practical solutions. Use the “Send to ASM” pill to deep-dive any solution in the Advanced Solution Matrix.</Text>
      {rootCauses.length === 0 && (
        <Text style={s.empty}>No root causes yet. Go back to Q2.</Text>
      )}
      {primaryConcerns.map(c => (
        <View key={c.id} style={{ marginBottom: 8 }}>
          <Text style={s.groupHeader}>{c.text}</Text>
          {rcasFor(c.id).map(r => (
            <View key={r.id} style={s.groupCard}>
              <Text style={s.subGroupTitle}>{r.text}</Text>
              {solsFor(r.id).map(sol => (
                <View key={sol.id} style={s.solCard}>
                  <View style={s.solRow}>
                    <View style={s.bullet} />
                    <TextInput
                      style={s.solInput}
                      value={sol.text}
                      onChangeText={t => editSolution(sol.id, { text: t })}
                      placeholder="Solution..."
                      placeholderTextColor="#9CA3AF"
                      multiline
                    />
                    {asmCounts[sol.id] > 0 && (
                      <View style={s.asmCountBadge}>
                        <Ionicons name="bar-chart" size={9} color="#0F766E" />
                        <Text style={s.asmCountBadgeText}>{asmCounts[sol.id]}</Text>
                      </View>
                    )}
                    <TouchableOpacity onPress={() => sendToASM('solution', sol.id, sol.text)} style={s.asmPill}>
                      <Ionicons name="apps" size={11} color="#0F766E" />
                      <Text style={s.asmPillText}>ASM</Text>
                    </TouchableOpacity>
                    <TouchableOpacity onPress={() => removeSolution(sol.id)} hitSlop={6}>
                      <Ionicons name="close" size={16} color="#94A3B8" />
                    </TouchableOpacity>
                  </View>
                </View>
              ))}
              <View style={s.addRow}>
                <TextInput
                  style={s.addInput}
                  placeholder="Add a solution..."
                  placeholderTextColor="#9CA3AF"
                  value={newSolText[r.id] || ''}
                  onChangeText={t => setNewSolText(prev => ({ ...prev, [r.id]: t }))}
                  onSubmitEditing={() => addSolution(r.id)}
                />
                <TouchableOpacity style={s.addBtn} onPress={() => addSolution(r.id)}>
                  <Ionicons name="add" size={18} color="#FFF" />
                </TouchableOpacity>
              </View>
              <TouchableOpacity style={s.capBtn} onPress={() => setCapPicker({ open: true, rcaId: r.id })}>
                <Ionicons name="people" size={13} color="#6366F1" />
                <Text style={s.capBtnText}>From Skills &amp; Resources (Self / Contacts)</Text>
              </TouchableOpacity>
            </View>
          ))}
        </View>
      ))}

      <Modal visible={capPicker.open} transparent animationType="slide" onRequestClose={() => setCapPicker({ open: false, rcaId: null })}>
        <View style={s.capModalBg}>
          <View style={s.capModalCard}>
            <View style={s.capModalHead}>
              <Text style={s.capModalTitle}>Pick a Skill or Resource</Text>
              <TouchableOpacity onPress={() => setCapPicker({ open: false, rcaId: null })} hitSlop={8}>
                <Ionicons name="close" size={22} color="#64748B" />
              </TouchableOpacity>
            </View>
            <ScrollView style={{ maxHeight: 440 }}>
              {[...contacts].sort((a, b) => (b.is_self ? 1 : 0) - (a.is_self ? 1 : 0)).map((c) => {
                const who = c.is_self ? 'Self' : (c.name || 'Contact');
                const skills: string[] = c.skills || [];
                const resLines = resourceLines(c);
                if (skills.length === 0 && resLines.length === 0) return null;
                const rid = capPicker.rcaId as string;
                return (
                  <View key={c.id} style={s.capGroup}>
                    <Text style={s.capWho}>{c.is_self ? '🧑 Self (You)' : `👤 ${who}`}</Text>
                    {skills.length > 0 && <Text style={s.capKind}>Skills</Text>}
                    <View style={s.capChips}>
                      {skills.map((sk, i) => (
                        <TouchableOpacity key={`s${i}`} style={s.capChip} onPress={() => addSolutionFromCapability(rid, who, 'skill', sk)}>
                          <Ionicons name="construct" size={11} color="#4338CA" />
                          <Text style={s.capChipText}>{sk}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                    {resLines.length > 0 && <Text style={s.capKind}>Resources</Text>}
                    <View style={s.capChips}>
                      {resLines.map((rl, i) => (
                        <TouchableOpacity key={`r${i}`} style={[s.capChip, { backgroundColor: '#ECFDF5' }]} onPress={() => addSolutionFromCapability(rid, who, 'resource', rl)}>
                          <Ionicons name="cube" size={11} color="#047857" />
                          <Text style={[s.capChipText, { color: '#047857' }]}>{rl}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  </View>
                );
              })}
              {contacts.every(c => (c.skills || []).length === 0 && resourceLines(c).length === 0) && (
                <Text style={s.capEmpty}>No skills or resources captured yet. Add them under Contacts → Professional / Resources.</Text>
              )}
            </ScrollView>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );

  const renderStep4 = () => (
    <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, paddingBottom: 80 }}>
      <Text style={s.qTitle}>Q4. Risk Management</Text>
      <Text style={s.qHint}>
        4a · Risks per solution (Impact% × Probability% = Risk Index%).{'\n'}
        4b · Mitigations (1..many) · 4c · Contingencies (1..many). Use “ASM” to deep-dive any item.
      </Text>
      {solutions.length === 0 && <Text style={s.empty}>No solutions yet. Go back to Q3.</Text>}
      {solutions.map(sol => (
        <View key={sol.id} style={s.groupCard}>
          <Text style={s.subGroupTitle}>Solution: {sol.text}</Text>
          {risksFor(sol.id).map(r => (
            <View key={r.id} style={s.riskCard}>
              <View style={s.riskHeader}>
                <Ionicons name="alert-circle" size={16} color="#DC2626" />
                <TextInput
                  style={s.riskNameInput}
                  value={r.name}
                  onChangeText={t => editRisk(r.id, { name: t })}
                  placeholder="Risk name..."
                  placeholderTextColor="#9CA3AF"
                />
                <TouchableOpacity onPress={() => removeRisk(r.id)} hitSlop={6}>
                  <Ionicons name="close" size={16} color="#94A3B8" />
                </TouchableOpacity>
              </View>
              <View style={s.riskScores}>
                <View style={s.scoreCol}>
                  <Text style={s.scoreLbl}>Impact %</Text>
                  <TextInput
                    style={s.scoreInput}
                    keyboardType="numeric"
                    value={r.impact_pct == null ? '' : String(r.impact_pct)}
                    onChangeText={t => editRisk(r.id, { impact_pct: clampPct(t) })}
                    placeholder="0-100"
                    placeholderTextColor="#9CA3AF"
                  />
                </View>
                <Text style={s.scoreX}>×</Text>
                <View style={s.scoreCol}>
                  <Text style={s.scoreLbl}>Probability %</Text>
                  <TextInput
                    style={s.scoreInput}
                    keyboardType="numeric"
                    value={r.probability_pct == null ? '' : String(r.probability_pct)}
                    onChangeText={t => editRisk(r.id, { probability_pct: clampPct(t) })}
                    placeholder="0-100"
                    placeholderTextColor="#9CA3AF"
                  />
                </View>
                <Text style={s.scoreX}>=</Text>
                <View style={s.scoreCol}>
                  <Text style={s.scoreLbl}>Index %</Text>
                  <View style={[s.scoreInput, s.scoreDerived]}>
                    <Text style={s.scoreDerivedText}>
                      {r.risk_index_pct == null ? '—' : `${r.risk_index_pct}%`}
                    </Text>
                  </View>
                </View>
              </View>

              {/* 4b — Mitigations (1..many) */}
              <Text style={s.subSubLabel}>4b · Mitigations</Text>
              {mitsFor(r.id).map(m => (
                <View key={m.id} style={s.childRow}>
                  <View style={[s.bullet, { backgroundColor: '#10B981' }]} />
                  <TextInput
                    style={s.childInput}
                    value={m.text}
                    onChangeText={t => editMitigation(m.id, t)}
                    placeholder="Mitigation..."
                    placeholderTextColor="#9CA3AF"
                    multiline
                  />
                  <Ionicons name="pencil" size={12} color="#94A3B8" />
                  {asmCounts[m.id] > 0 && (
                    <View style={s.asmCountBadge}>
                      <Ionicons name="bar-chart" size={9} color="#0F766E" />
                      <Text style={s.asmCountBadgeText}>{asmCounts[m.id]}</Text>
                    </View>
                  )}
                  <TouchableOpacity onPress={() => sendToASM('mitigation', m.id, m.text)} style={s.asmPill}>
                    <Ionicons name="apps" size={11} color="#0F766E" />
                    <Text style={s.asmPillText}>ASM</Text>
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => removeMitigation(m.id)} hitSlop={6}>
                    <Ionicons name="close" size={16} color="#94A3B8" />
                  </TouchableOpacity>
                </View>
              ))}
              <View style={s.addRow}>
                <TextInput
                  style={s.addInput}
                  placeholder="Add a mitigation..."
                  placeholderTextColor="#9CA3AF"
                  value={newMitText[r.id] || ''}
                  onChangeText={t => setNewMitText(prev => ({ ...prev, [r.id]: t }))}
                  onSubmitEditing={() => addMitigation(r.id)}
                />
                <TouchableOpacity style={s.addBtn} onPress={() => addMitigation(r.id)}>
                  <Ionicons name="add" size={18} color="#FFF" />
                </TouchableOpacity>
              </View>

              {/* 4c — Contingencies (1..many) */}
              <Text style={s.subSubLabel}>4c · Contingencies</Text>
              {consFor(r.id).map(c => (
                <View key={c.id} style={s.childRow}>
                  <View style={[s.bullet, { backgroundColor: '#F59E0B' }]} />
                  <TextInput
                    style={s.childInput}
                    value={c.text}
                    onChangeText={t => editContingency(c.id, t)}
                    placeholder="Contingency..."
                    placeholderTextColor="#9CA3AF"
                    multiline
                  />
                  <Ionicons name="pencil" size={12} color="#94A3B8" />
                  {asmCounts[c.id] > 0 && (
                    <View style={s.asmCountBadge}>
                      <Ionicons name="bar-chart" size={9} color="#0F766E" />
                      <Text style={s.asmCountBadgeText}>{asmCounts[c.id]}</Text>
                    </View>
                  )}
                  <TouchableOpacity onPress={() => sendToASM('contingency', c.id, c.text)} style={s.asmPill}>
                    <Ionicons name="apps" size={11} color="#0F766E" />
                    <Text style={s.asmPillText}>ASM</Text>
                  </TouchableOpacity>
                  <TouchableOpacity onPress={() => removeContingency(c.id)} hitSlop={6}>
                    <Ionicons name="close" size={16} color="#94A3B8" />
                  </TouchableOpacity>
                </View>
              ))}
              <View style={s.addRow}>
                <TextInput
                  style={s.addInput}
                  placeholder="Add a contingency..."
                  placeholderTextColor="#9CA3AF"
                  value={newConText[r.id] || ''}
                  onChangeText={t => setNewConText(prev => ({ ...prev, [r.id]: t }))}
                  onSubmitEditing={() => addContingency(r.id)}
                />
                <TouchableOpacity style={s.addBtn} onPress={() => addContingency(r.id)}>
                  <Ionicons name="add" size={18} color="#FFF" />
                </TouchableOpacity>
              </View>
            </View>
          ))}
          <View style={s.addRow}>
            <TextInput
              style={s.addInput}
              placeholder="Add a risk for this solution..."
              placeholderTextColor="#9CA3AF"
              value={newRiskText[sol.id] || ''}
              onChangeText={t => setNewRiskText(prev => ({ ...prev, [sol.id]: t }))}
              onSubmitEditing={() => addRisk(sol.id)}
            />
            <TouchableOpacity style={s.addBtn} onPress={() => addRisk(sol.id)}>
              <Ionicons name="add" size={18} color="#FFF" />
            </TouchableOpacity>
          </View>
        </View>
      ))}
    </ScrollView>
  );

  const renderStep5 = () => (
    <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16, paddingBottom: 80 }}>
      <Text style={s.qTitle}>Q5. Action Plan</Text>
      <Text style={s.qHint}>
        Auto-aggregated from Solutions, Mitigations & Contingencies. Edit owners / dates, tick CTT or Lifestyle if applicable, then push everything to your universal Action Center.
      </Text>
      <TouchableOpacity onPress={recomputePlan} style={s.regenBtn}>
        <Ionicons name="refresh" size={14} color="#0F172A" />
        <Text style={s.regenText}>Re-aggregate from Q3 + Q4b + Q4c</Text>
      </TouchableOpacity>
      {actionPlan.length === 0 && (
        <Text style={s.empty}>Nothing aggregated yet. Add items in Q3 / Q4 and tap re-aggregate.</Text>
      )}
      {actionPlan.map(p => (
        <View key={p.ap_id} style={s.apCard}>
          <View style={s.apHeader}>
            <View style={[s.apTag,
              p.source_type === 'solution' && { backgroundColor: '#EEF2FF', borderColor: '#6366F1' },
              p.source_type === 'mitigation' && { backgroundColor: '#ECFDF5', borderColor: '#10B981' },
              p.source_type === 'contingency' && { backgroundColor: '#FFFBEB', borderColor: '#F59E0B' },
            ]}>
              <Text style={s.apTagText}>{p.source_type.toUpperCase()}</Text>
            </View>
            {p.pushed_to_action_center && (
              <View style={s.apPushed}>
                <Ionicons name="checkmark-circle" size={12} color="#10B981" />
                <Text style={s.apPushedText}>In Action Center</Text>
              </View>
            )}
          </View>
          <Text style={s.apText}>{p.text}</Text>
          <View style={s.apMetaRow}>
            <TextInput
              style={[s.apMetaInput, { flex: 1 }]}
              placeholder="Owner / Who"
              placeholderTextColor="#9CA3AF"
              value={p.who || ''}
              onChangeText={t => editPlanItem(p.ap_id, { who: t })}
            />
            <TextInput
              style={[s.apMetaInput, { width: 110 }]}
              placeholder="YYYY-MM-DD"
              placeholderTextColor="#9CA3AF"
              value={p.by_when || ''}
              onChangeText={t => editPlanItem(p.ap_id, { by_when: t })}
            />
          </View>
          <View style={s.apFlagRow}>
            <TouchableOpacity
              onPress={() => togglePlanFlag(p.ap_id, 'push_ctt')}
              style={[s.apFlag, (p.push_ctt || p.pushed_to_ctt) && s.apFlagActive]}
            >
              <Ionicons
                name={p.pushed_to_ctt ? 'checkmark-done' : p.push_ctt ? 'checkmark' : 'add'}
                size={12} color={(p.push_ctt || p.pushed_to_ctt) ? '#FFF' : '#475569'}
              />
              <Text style={[s.apFlagText, (p.push_ctt || p.pushed_to_ctt) && { color: '#FFF' }]}>
                → CTT
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              onPress={() => togglePlanFlag(p.ap_id, 'push_lifestyle')}
              style={[s.apFlag, (p.push_lifestyle || p.pushed_to_lifestyle) && s.apFlagActive]}
            >
              <Ionicons
                name={p.pushed_to_lifestyle ? 'checkmark-done' : p.push_lifestyle ? 'checkmark' : 'add'}
                size={12} color={(p.push_lifestyle || p.pushed_to_lifestyle) ? '#FFF' : '#475569'}
              />
              <Text style={[s.apFlagText, (p.push_lifestyle || p.pushed_to_lifestyle) && { color: '#FFF' }]}>
                → Lifestyle
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      ))}
      {actionPlan.length > 0 && (
        <TouchableOpacity style={s.pushBtn} onPress={pushAllToActionCenter}>
          <Ionicons name="rocket" size={16} color="#FFF" />
          <Text style={s.pushBtnText}>Push pending items to Action Center</Text>
        </TouchableOpacity>
      )}
    </ScrollView>
  );

  // ============ MAIN RENDER ============
  if (loading) {
    return (
      <SafeAreaView style={s.container}>
        <ActivityIndicator size="large" color="#7C3AED" style={{ marginTop: 60 }} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <LinearGradient colors={['#7C3AED', '#C084FC']} style={s.header}>
        <TouchableOpacity onPress={() => router.back()} style={s.headerBtn}>
          <Ionicons name="arrow-back" size={22} color="#FFF" />
        </TouchableOpacity>
        <View style={{ flex: 1 }}>
          <Text style={s.headerTitle}>Solution Finder</Text>
          <Text style={s.headerSub}>Step {step + 1} of {STEPS.length} · {STEPS[step].title}</Text>
        </View>
        {saving && <ActivityIndicator size="small" color="#FFF" />}
      </LinearGradient>
      {renderStepIndicator()}
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        {step === 0 && renderStep0()}
        {step === 1 && renderStep1()}
        {step === 2 && renderStep2()}
        {step === 3 && renderStep3()}
        {step === 4 && renderStep4()}
        {step === 5 && renderStep5()}
      </KeyboardAvoidingView>
      <View style={s.footer}>
        <TouchableOpacity style={s.backBtn} onPress={onBack} disabled={step === 0}>
          <Ionicons name="arrow-back" size={16} color={step === 0 ? '#CBD5E1' : '#475569'} />
          <Text style={[s.backBtnText, step === 0 && { color: '#CBD5E1' }]}>Back</Text>
        </TouchableOpacity>
        {step < 5 ? (
          <TouchableOpacity style={s.nextBtn} onPress={onNext}>
            <Text style={s.nextBtnText}>{step === 4 ? 'Build Action Plan' : 'Next'}</Text>
            <Ionicons name="arrow-forward" size={16} color="#FFF" />
          </TouchableOpacity>
        ) : (
          <TouchableOpacity style={s.nextBtn} onPress={() => handleSave(false, 'completed').then(() => router.back())}>
            <Ionicons name="checkmark" size={16} color="#FFF" />
            <Text style={s.nextBtnText}>Save & Close</Text>
          </TouchableOpacity>
        )}
      </View>
    </SafeAreaView>
  );
}

// ============== STYLES ==============
const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8FAFC' },
  header: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 12, paddingVertical: 12 },
  headerBtn: { width: 36, height: 36, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.18)', alignItems: 'center', justifyContent: 'center' },
  headerTitle: { color: '#FFF', fontSize: 16, fontWeight: '800' },
  headerSub: { color: 'rgba(255,255,255,0.85)', fontSize: 11, marginTop: 2 },

  stepIndicator: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 10, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#F1F5F9' },
  stepDotWrap: { flexDirection: 'row', alignItems: 'center', flex: 1 },
  stepDot: { width: 24, height: 24, borderRadius: 12, backgroundColor: '#E2E8F0', alignItems: 'center', justifyContent: 'center' },
  stepDotActive: { backgroundColor: '#7C3AED' },
  stepEditBadge: { position: 'absolute', top: -4, right: -4, width: 14, height: 14, borderRadius: 7, backgroundColor: '#F59E0B', alignItems: 'center', justifyContent: 'center', borderWidth: 1.5, borderColor: '#FFF' },
  capBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 6, paddingVertical: 8, paddingHorizontal: 10, borderRadius: 8, borderWidth: 1, borderColor: '#C7D2FE', backgroundColor: '#EEF2FF', alignSelf: 'flex-start' },
  capBtnText: { fontSize: 12, fontWeight: '600', color: '#4338CA' },
  capModalBg: { flex: 1, backgroundColor: '#00000066', justifyContent: 'flex-end' },
  capModalCard: { backgroundColor: '#FFF', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 16, paddingBottom: 28 },
  capModalHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 },
  capModalTitle: { fontSize: 16, fontWeight: '800', color: '#0F172A' },
  capGroup: { marginBottom: 14, borderBottomWidth: 1, borderBottomColor: '#F1F5F9', paddingBottom: 10 },
  capWho: { fontSize: 14, fontWeight: '700', color: '#0F172A', marginBottom: 6 },
  capKind: { fontSize: 11, fontWeight: '700', color: '#94A3B8', textTransform: 'uppercase', marginTop: 4, marginBottom: 4 },
  capChips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  capChip: { flexDirection: 'row', alignItems: 'center', gap: 4, backgroundColor: '#EEF2FF', paddingVertical: 7, paddingHorizontal: 10, borderRadius: 14 },
  capChipText: { fontSize: 12, fontWeight: '600', color: '#4338CA' },
  capEmpty: { fontSize: 13, color: '#94A3B8', textAlign: 'center', paddingVertical: 24 },
  stepLine: { flex: 1, height: 2, backgroundColor: '#E2E8F0', marginHorizontal: 4 },
  stepLineActive: { backgroundColor: '#7C3AED' },

  sectionLabel: { fontSize: 11, fontWeight: '800', color: '#475569', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 8, marginTop: 4 },
  qTitle: { fontSize: 16, fontWeight: '800', color: '#0F172A', marginBottom: 6 },
  qHint: { fontSize: 12, color: '#64748B', lineHeight: 18, marginBottom: 12 },
  empty: { fontSize: 12, color: '#94A3B8', fontStyle: 'italic', textAlign: 'center', padding: 16 },

  areaGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 14 },
  areaChip: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 16, backgroundColor: '#FFF', borderWidth: 1, borderColor: '#E2E8F0' },
  areaChipActive: { backgroundColor: '#7C3AED', borderColor: '#7C3AED' },
  areaChipText: { fontSize: 11, fontWeight: '600', color: '#475569' },

  textArea: { backgroundColor: '#FFF', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: '#E2E8F0', fontSize: 13, color: '#0F172A', textAlignVertical: 'top' },

  concernRow: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 10, backgroundColor: '#FFF', borderRadius: 10, marginBottom: 6, borderWidth: 1, borderColor: '#F1F5F9' },
  concernInput: { flex: 1, fontSize: 13, color: '#0F172A', paddingVertical: 4 },

  addRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 6 },
  addInput: { flex: 1, backgroundColor: '#FFF', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8, fontSize: 12, color: '#0F172A', borderWidth: 1, borderColor: '#E2E8F0' },
  addBtn: { width: 32, height: 32, borderRadius: 16, backgroundColor: '#7C3AED', alignItems: 'center', justifyContent: 'center' },

  previewBox: { marginTop: 16, backgroundColor: '#FEF3C7', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: '#FCD34D' },
  previewTitle: { fontSize: 12, fontWeight: '800', color: '#92400E', marginBottom: 6 },
  previewItem: { fontSize: 12, color: '#78350F', marginBottom: 2 },

  groupHeader: { fontSize: 12, fontWeight: '800', color: '#0F172A', marginTop: 8, marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.4 },
  groupCard: { backgroundColor: '#FFF', borderRadius: 12, padding: 12, marginBottom: 10, borderWidth: 1, borderColor: '#F1F5F9' },
  groupTitle: { fontSize: 13, fontWeight: '700', color: '#0F172A', marginBottom: 8 },
  subGroupTitle: { fontSize: 12, fontWeight: '700', color: '#475569', marginBottom: 8 },
  subSubLabel: { fontSize: 10, fontWeight: '800', color: '#64748B', textTransform: 'uppercase', letterSpacing: 0.5, marginTop: 10, marginBottom: 4 },

  childRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6 },
  bullet: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#7C3AED' },
  childText: { flex: 1, fontSize: 12, color: '#0F172A' },
  childInput: { flex: 1, fontSize: 12, color: '#0F172A', paddingVertical: 4 },

  solCard: { marginBottom: 4 },
  solRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  solInput: { flex: 1, fontSize: 12, color: '#0F172A', paddingVertical: 4 },

  asmPill: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 6, paddingVertical: 3, borderRadius: 10, backgroundColor: '#F0FDFA', borderWidth: 1, borderColor: '#5EEAD4' },
  asmPillText: { fontSize: 9, fontWeight: '800', color: '#0F766E' },
  // Tiny badge that shows how many ASM deep-dives exist for this row
  // (Solutions / Mitigations / Contingencies). Reverse hook from
  // /api/solution-finders/{id}/asm-links.
  asmCountBadge: { flexDirection: 'row', alignItems: 'center', gap: 2, paddingHorizontal: 5, paddingVertical: 2, borderRadius: 8, backgroundColor: '#CCFBF1' },
  asmCountBadgeText: { fontSize: 9, fontWeight: '800', color: '#0F766E' },

  riskCard: { backgroundColor: '#FEF2F2', borderRadius: 10, padding: 10, marginBottom: 8, borderWidth: 1, borderColor: '#FECACA' },
  riskHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  riskNameInput: { flex: 1, fontSize: 13, fontWeight: '700', color: '#0F172A', paddingVertical: 2 },

  riskScores: { flexDirection: 'row', alignItems: 'flex-end', gap: 6, marginBottom: 6 },
  scoreCol: { flex: 1 },
  scoreLbl: { fontSize: 9, fontWeight: '700', color: '#64748B', textTransform: 'uppercase' },
  scoreInput: { backgroundColor: '#FFF', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 6, fontSize: 12, color: '#0F172A', borderWidth: 1, borderColor: '#E2E8F0', minHeight: 32 },
  scoreDerived: { backgroundColor: '#FEF3C7', justifyContent: 'center', alignItems: 'center', borderColor: '#FCD34D' },
  scoreDerivedText: { fontSize: 13, fontWeight: '800', color: '#92400E' },
  scoreX: { fontSize: 14, fontWeight: '800', color: '#94A3B8', paddingBottom: 6 },

  regenBtn: { flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 6, backgroundColor: '#E2E8F0', borderRadius: 8, marginBottom: 12 },
  regenText: { fontSize: 11, fontWeight: '700', color: '#0F172A' },

  apCard: { backgroundColor: '#FFF', borderRadius: 12, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: '#F1F5F9' },
  apHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 },
  apTag: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6, borderWidth: 1, backgroundColor: '#F1F5F9', borderColor: '#CBD5E1' },
  apTagText: { fontSize: 9, fontWeight: '800', color: '#0F172A', letterSpacing: 0.5 },
  apPushed: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  apPushedText: { fontSize: 10, fontWeight: '700', color: '#10B981' },
  apText: { fontSize: 13, color: '#0F172A', marginBottom: 6 },
  apMetaRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  apMetaInput: { backgroundColor: '#F8FAFC', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 6, fontSize: 11, color: '#0F172A', borderWidth: 1, borderColor: '#E2E8F0' },
  apFlagRow: { flexDirection: 'row', gap: 6 },
  apFlag: { flexDirection: 'row', alignItems: 'center', gap: 3, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12, backgroundColor: '#F1F5F9', borderWidth: 1, borderColor: '#CBD5E1' },
  apFlagActive: { backgroundColor: '#10B981', borderColor: '#10B981' },
  apFlagText: { fontSize: 10, fontWeight: '700', color: '#475569' },

  pushBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: '#10B981', borderRadius: 12, paddingVertical: 12, marginTop: 8 },
  pushBtnText: { color: '#FFF', fontSize: 13, fontWeight: '800' },

  footer: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderTopWidth: 1, borderTopColor: '#F1F5F9', backgroundColor: '#FFF' },
  backBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 10, backgroundColor: '#F1F5F9' },
  backBtnText: { fontSize: 12, fontWeight: '700', color: '#475569' },
  nextBtn: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingVertical: 12, borderRadius: 10, backgroundColor: '#7C3AED' },
  nextBtnText: { color: '#FFF', fontSize: 13, fontWeight: '800' },
});
