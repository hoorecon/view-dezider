import React, { useState, useEffect, useMemo } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  Platform,
  KeyboardAvoidingView,
  Modal,
  Linking,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import { COLORS } from '../../src/constants/colors';
import api from '../../src/utils/api';
import { useACM } from '../../src/hooks/useACM';

const API_BASE = (Constants.expoConfig?.extra?.EXPO_PUBLIC_BACKEND_URL
  || process.env.EXPO_PUBLIC_BACKEND_URL
  || '') as string;

const LIFE_AREAS = [
  { id: 'career', name: 'Career', icon: 'briefcase' },
  { id: 'finance', name: 'Finance', icon: 'cash' },
  { id: 'relationships', name: 'Relationships', icon: 'heart' },
  { id: 'holistic_health', name: 'Holistic Health', icon: 'fitness' },
  { id: 'assets', name: 'Assets', icon: 'home' },
  { id: 'knowledge_skills', name: 'Knowledge & Skills', icon: 'school' },
  { id: 'social_image', name: 'Social Image', icon: 'people' },
  { id: 'social_contributions', name: 'Social Contributions', icon: 'globe' },
  { id: 'hobbies_entertainment', name: 'Hobbies & Entertainment', icon: 'game-controller' },
  { id: 'spirituality_religion', name: 'Spirituality', icon: 'leaf' },
];

// 5 canonical TEPFI fields (shown in the matrix input grid)
const TEPFI_FIELDS = [
  { key: 'time', label: 'Time', icon: 'time' },
  { key: 'energy', label: 'Energy (Capacity)', icon: 'flash' },
  { key: 'people', label: 'People', icon: 'people' },
  { key: 'finance', label: 'Finance', icon: 'cash' },
  { key: 'infrastructure', label: 'Infrastructure', icon: 'construct' },
];

const SOLUTION_CATEGORIES = [
  { key: 'completely_solvable', label: 'Completely Solvable', color: '#10B981' },
  { key: 'partially_solvable', label: 'Partially Solvable', color: '#F59E0B' },
  { key: 'not_solvable', label: 'Not Solvable', color: '#EF4444' },
  { key: 'patience_period', label: 'Patience Period', color: '#6366F1' },
  { key: 'accept_let_go', label: 'Accept & Let Go', color: '#8B5CF6' },
  { key: 'surrender_trust', label: 'Surrender & Trust the Process', color: '#06B6D4' },
  { key: 'surrender_ignore', label: 'Surrender & Ignore', color: '#64748B' },
  { key: 'surrender_involve', label: 'Surrender & Involve (Choiceless Awareness)', color: '#EC4899' },
];

const SOLUTION_SOURCES = [
  { key: 'from_self', label: 'Solution from Self', icon: 'person' },
  { key: 'from_wellwisher', label: 'Solution from Well-wisher', icon: 'heart' },
  { key: 'from_experienced', label: 'Solution from Experienced', icon: 'school' },
  { key: 'from_expert', label: 'Solution from On-Demand Expert', icon: 'star' },
  { key: 'from_coach', label: 'Solution from Regular Coach', icon: 'fitness' },
];

type MatrixMode = 'standard' | 'accurate';

interface Influence { positive: string; negative: string; }

interface MatrixCell {
  // Legacy 7-field set (kept for compat)
  summary: string;
  knowledge_skills: string;
  capacity: string;
  // Canonical TEPFI
  time: string;
  energy: string;
  people: string;
  finance: string;
  infrastructure: string;
  // Per-field influence map keyed by field-name
  influences: Record<string, Influence>;
}

// Standard mode uses `aggregate`; Accurate uses the 4 OrgType slots.
interface MatrixLayerSet {
  aggregate: MatrixCell;
  individual: MatrixCell;
  org: MatrixCell;
  govt: MatrixCell;
  nature: MatrixCell;
}

const emptyCell = (): MatrixCell => ({
  summary: '', knowledge_skills: '', capacity: '',
  time: '', energy: '', people: '', finance: '', infrastructure: '',
  influences: {},
});

const emptySet = (): MatrixLayerSet => ({
  aggregate: emptyCell(),
  individual: emptyCell(),
  org: emptyCell(),
  govt: emptyCell(),
  nature: emptyCell(),
});

// Normalise legacy flat / partial nested payloads to the full shape.
const normaliseSet = (raw: any): MatrixLayerSet => {
  if (!raw || typeof raw !== 'object') return emptySet();
  const isLegacyFlat = 'summary' in raw || 'time' in raw || 'people' in raw;
  const isSlotShape = 'aggregate' in raw || 'individual' in raw || 'org' in raw
    || 'govt' in raw || 'nature' in raw;

  const mergeCell = (src: any): MatrixCell => {
    const base = emptyCell();
    if (!src || typeof src !== 'object') return base;
    (Object.keys(base) as (keyof MatrixCell)[]).forEach((k) => {
      if (k === 'influences') return;
      if (src[k] !== undefined) (base as any)[k] = String(src[k] || '');
    });
    // energy mirrors capacity if missing, vice-versa
    if (!base.energy && base.capacity) base.energy = base.capacity;
    if (!base.capacity && base.energy) base.capacity = base.energy;
    if (src.influences && typeof src.influences === 'object') {
      const inf: Record<string, Influence> = {};
      Object.keys(src.influences).forEach((field) => {
        const v = src.influences[field] || {};
        inf[field] = {
          positive: String(v.positive || ''),
          negative: String(v.negative || ''),
        };
      });
      base.influences = inf;
    }
    return base;
  };

  if (isLegacyFlat && !isSlotShape) {
    const c = mergeCell(raw);
    return {
      aggregate: { ...c, influences: { ...c.influences } },
      individual: c,
      org: emptyCell(), govt: emptyCell(), nature: emptyCell(),
    };
  }

  return {
    aggregate: mergeCell(raw.aggregate),
    individual: mergeCell(raw.individual),
    org: mergeCell(raw.org),
    govt: mergeCell(raw.govt),
    nature: mergeCell(raw.nature),
  };
};

const ORG_TYPES = [
  { key: 'individual' as const, label: 'Individual', icon: 'person', color: '#2563EB', feature_id: 'solution_matrix_orgtype_individual' },
  { key: 'org' as const, label: 'Org', icon: 'business', color: '#7C3AED', feature_id: 'solution_matrix_orgtype_org' },
  { key: 'govt' as const, label: 'Govt', icon: 'shield-checkmark', color: '#F59E0B', feature_id: 'solution_matrix_orgtype_govt' },
  { key: 'nature' as const, label: 'Nature', icon: 'leaf', color: '#10B981', feature_id: 'solution_matrix_orgtype_nature' },
];

interface ActionItem { who: string; what: string; by_when: string; status: string; }
interface TemplateMeta {
  template_id: string; org_type: string; matrix_mode: string;
  title: string; subtitle: string; icon: string; color: string;
}

export default function SolutionMatrixScreen() {
  const router = useRouter();
  const params = useLocalSearchParams();
  const editId = params.id as string | undefined;

  const { checkFeature } = useACM();
  const pdfAccess = checkFeature('solution_matrix_pdf_export');
  const tplAccess = checkFeature('solution_matrix_templates');

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);

  // Matrix mode
  const [matrixMode, setMatrixMode] = useState<MatrixMode>('accurate');

  // Form
  const [areaOfLife, setAreaOfLife] = useState('');
  const [smartGoal, setSmartGoal] = useState('');
  const [milestones, setMilestones] = useState([{ description: '', timeline: '' }]);
  const [q1AllConcerns, setQ1AllConcerns] = useState('');
  const [q2PriorityConcerns, setQ2PriorityConcerns] = useState('');
  const [simplerSolutions, setSimplerSolutions] = useState('');
  const [simplerCapabilities, setSimplerCapabilities] = useState('');
  const [simplerResources, setSimplerResources] = useState('');
  const [simplerHelpAspect, setSimplerHelpAspect] = useState('');
  const [simplerHelpLevel, setSimplerHelpLevel] = useState('');
  const [simplerHelpFrom, setSimplerHelpFrom] = useState('');
  const [matrixSelf, setMatrixSelf] = useState<MatrixLayerSet>(emptySet());
  const [matrixMicro, setMatrixMicro] = useState<MatrixLayerSet>(emptySet());
  const [matrixMacro, setMatrixMacro] = useState<MatrixLayerSet>(emptySet());
  const [solutionCategory, setSolutionCategory] = useState<Record<string, boolean>>(
    Object.fromEntries(SOLUTION_CATEGORIES.map(c => [c.key, false]))
  );
  const [solutionSources, setSolutionSources] = useState<Record<string, string>>(
    Object.fromEntries(SOLUTION_SOURCES.map(s => [s.key, '']))
  );
  const [q4NegConsequences, setQ4NegConsequences] = useState('');
  const [q4Mitigation, setQ4Mitigation] = useState('');
  const [q4Contingency, setQ4Contingency] = useState('');
  const [actionItems, setActionItems] = useState<ActionItem[]>([{ who: '', what: '', by_when: '', status: 'pending' }]);

  // Templates
  const [tplModalOpen, setTplModalOpen] = useState(false);
  const [templates, setTemplates] = useState<TemplateMeta[]>([]);
  const [tplLoading, setTplLoading] = useState(false);
  const [applyingTpl, setApplyingTpl] = useState<string | null>(null);

  // Matrix layer/orgtype tabs + expanded influence toggle
  const [activeMatrixTab, setActiveMatrixTab] = useState<'self' | 'micro' | 'macro'>('self');
  const [activeOrgType, setActiveOrgType] = useState<'aggregate' | 'individual' | 'org' | 'govt' | 'nature'>('aggregate');
  const [expandedInfluenceField, setExpandedInfluenceField] = useState<string | null>(null);

  // Whenever mode changes, make sure activeOrgType is valid for that mode
  useEffect(() => {
    if (matrixMode === 'standard') setActiveOrgType('aggregate');
    else if (activeOrgType === 'aggregate') setActiveOrgType('individual');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matrixMode]);

  const steps = [
    { title: 'Life Area & Goal', icon: 'flag' },
    { title: 'Concerns', icon: 'alert-circle' },
    { title: 'Simpler Solutions', icon: 'bulb' },
    { title: 'Solution Matrix', icon: 'grid' },
    { title: 'Categories & Sources', icon: 'layers' },
    { title: 'Risk Management', icon: 'shield-checkmark' },
    { title: 'Action Plan', icon: 'rocket' },
  ];

  // Visible org-types based on ACM + current mode
  const visibleOrgTypes = useMemo(() => {
    if (matrixMode === 'standard') return [];
    return ORG_TYPES.filter(ot => {
      const f = checkFeature(ot.feature_id);
      return f.access_level !== 'hidden';
    });
  }, [matrixMode, checkFeature]);

  useEffect(() => {
    if (editId) loadEntry();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editId]);

  const loadEntry = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/solution-matrices/${editId}`);
      const d = res.data;
      setAreaOfLife(d.area_of_life || '');
      setSmartGoal(d.smart_goal || '');
      setMilestones(d.milestones?.length ? d.milestones : [{ description: '', timeline: '' }]);
      setQ1AllConcerns(d.q1_all_concerns || '');
      setQ2PriorityConcerns(d.q2_priority_concerns || '');
      setSimplerSolutions(d.simpler_solutions || '');
      setSimplerCapabilities(d.simpler_capabilities || '');
      setSimplerResources(d.simpler_resources || '');
      setSimplerHelpAspect(d.simpler_help_aspect || '');
      setSimplerHelpLevel(d.simpler_help_level || '');
      setSimplerHelpFrom(d.simpler_help_from || '');
      setMatrixMode((d.matrix_mode === 'standard' ? 'standard' : 'accurate'));
      setMatrixSelf(normaliseSet(d.matrix_self));
      setMatrixMicro(normaliseSet(d.matrix_micro));
      setMatrixMacro(normaliseSet(d.matrix_macro));
      if (d.solution_category) setSolutionCategory(prev => ({ ...prev, ...d.solution_category }));
      if (d.solution_sources) setSolutionSources(prev => ({ ...prev, ...d.solution_sources }));
      setQ4NegConsequences(d.q4_negative_consequences || '');
      setQ4Mitigation(d.q4_mitigation_plans || '');
      setQ4Contingency(d.q4_contingency_plans || '');
      setActionItems(d.action_items?.length ? d.action_items : [{ who: '', what: '', by_when: '', status: 'pending' }]);
    } catch {
      showAlert('Error', 'Failed to load entry');
    } finally {
      setLoading(false);
    }
  };

  const buildPayload = () => ({
    area_of_life: areaOfLife,
    smart_goal: smartGoal,
    milestones: milestones.filter(m => m.description.trim()),
    q1_all_concerns: q1AllConcerns,
    q2_priority_concerns: q2PriorityConcerns,
    simpler_solutions: simplerSolutions,
    simpler_capabilities: simplerCapabilities,
    simpler_resources: simplerResources,
    simpler_help_aspect: simplerHelpAspect,
    simpler_help_level: simplerHelpLevel,
    simpler_help_from: simplerHelpFrom,
    matrix_mode: matrixMode,
    matrix_self: matrixSelf,
    matrix_micro: matrixMicro,
    matrix_macro: matrixMacro,
    solution_category: solutionCategory,
    solution_sources: solutionSources,
    q4_negative_consequences: q4NegConsequences,
    q4_mitigation_plans: q4Mitigation,
    q4_contingency_plans: q4Contingency,
    action_items: actionItems.filter(a => a.what.trim()),
    status: currentStep >= 6 ? 'completed' : 'in_progress',
  });

  const handleSave = async () => {
    if (!areaOfLife || !smartGoal.trim()) {
      showAlert('Required', 'Please select area and enter SMART goal');
      return;
    }
    setSaving(true);
    try {
      const payload = buildPayload();
      if (editId) await api.put(`/solution-matrices/${editId}`, payload);
      else await api.post('/solution-matrices', payload);
      showAlert('Saved', 'Solution Matrix saved successfully!', [
        { text: 'OK', onPress: () => router.back() },
      ]);
    } catch {
      showAlert('Error', 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  // ---------- Templates ----------
  const openTemplatePicker = async () => {
    if (tplAccess.access_level === 'locked' || tplAccess.access_level === 'hidden') {
      showAlert('Locked', 'Starter templates are a paid feature. Upgrade to unlock.');
      return;
    }
    setTplModalOpen(true);
    if (templates.length === 0) {
      setTplLoading(true);
      try {
        const res = await api.get('/solution-matrices/templates');
        setTemplates(res.data?.templates || []);
      } catch {
        showAlert('Error', 'Failed to load templates');
      } finally {
        setTplLoading(false);
      }
    }
  };

  const applyTemplate = async (tplId: string) => {
    setApplyingTpl(tplId);
    try {
      const res = await api.get(`/solution-matrices/templates/${tplId}`);
      const tpl = res.data;
      const pl = tpl.payload || {};
      setAreaOfLife(pl.area_of_life || '');
      setSmartGoal(pl.smart_goal || '');
      setMilestones(pl.milestones?.length ? pl.milestones : [{ description: '', timeline: '' }]);
      setQ1AllConcerns(pl.q1_all_concerns || '');
      setQ2PriorityConcerns(pl.q2_priority_concerns || '');
      setSimplerSolutions(pl.simpler_solutions || '');
      setSimplerCapabilities(pl.simpler_capabilities || '');
      setSimplerResources(pl.simpler_resources || '');
      setSimplerHelpAspect(pl.simpler_help_aspect || '');
      setSimplerHelpLevel(pl.simpler_help_level || '');
      setSimplerHelpFrom(pl.simpler_help_from || '');
      setMatrixMode(pl.matrix_mode === 'standard' ? 'standard' : 'accurate');
      setMatrixSelf(normaliseSet(pl.matrix_self));
      setMatrixMicro(normaliseSet(pl.matrix_micro));
      setMatrixMacro(normaliseSet(pl.matrix_macro));
      setTplModalOpen(false);
      setCurrentStep(0);
      showAlert('Template applied', `Loaded: ${tpl.title}`);
    } catch {
      showAlert('Error', 'Failed to apply template');
    } finally {
      setApplyingTpl(null);
    }
  };

  // ---------- PDF Export ----------
  const handleExportPdf = async () => {
    if (!editId) {
      showAlert('Save first', 'Save this matrix first, then export to PDF.');
      return;
    }
    if (pdfAccess.access_level === 'locked' || pdfAccess.access_level === 'hidden') {
      showAlert('Locked', 'PDF export is a paid feature. Upgrade to unlock.');
      return;
    }
    setExporting(true);
    try {
      const token = await AsyncStorage.getItem('session_token');
      const url = `${API_BASE}/api/solution-matrices/${editId}/pdf`;
      if (Platform.OS === 'web' && token) {
        const r = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
        if (!r.ok) throw new Error(`${r.status}`);
        const blob = await r.blob();
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const w: any = (typeof window !== 'undefined') ? window : null;
        if (w?.URL?.createObjectURL) {
          const dl = w.URL.createObjectURL(blob);
          const a = w.document.createElement('a');
          a.href = dl;
          a.download = `solution_matrix_${editId.slice(0, 8)}.pdf`;
          w.document.body.appendChild(a);
          a.click();
          w.document.body.removeChild(a);
          w.URL.revokeObjectURL(dl);
        }
      } else {
        await Linking.openURL(`${url}?_=${Date.now()}`);
      }
    } catch {
      showAlert('Export failed', 'Please try again.');
    } finally {
      setExporting(false);
    }
  };

  // ---------- Matrix edits ----------
  const getMatrixSet = (layer: 'self' | 'micro' | 'macro'): MatrixLayerSet => {
    if (layer === 'self') return matrixSelf;
    if (layer === 'micro') return matrixMicro;
    return matrixMacro;
  };

  const setMatrixSet = (layer: 'self' | 'micro' | 'macro', updater: (prev: MatrixLayerSet) => MatrixLayerSet) => {
    if (layer === 'self') setMatrixSelf(updater);
    else if (layer === 'micro') setMatrixMicro(updater);
    else setMatrixMacro(updater);
  };

  const updateCellField = (
    layer: 'self' | 'micro' | 'macro',
    slot: 'aggregate' | 'individual' | 'org' | 'govt' | 'nature',
    field: string,
    value: string,
  ) => {
    setMatrixSet(layer, (prev) => {
      const cell = { ...prev[slot] } as MatrixCell;
      (cell as any)[field] = value;
      // energy <-> capacity mirror
      if (field === 'energy') cell.capacity = value;
      if (field === 'capacity') cell.energy = value;
      return { ...prev, [slot]: cell };
    });
  };

  const updateInfluence = (
    layer: 'self' | 'micro' | 'macro',
    slot: 'aggregate' | 'individual' | 'org' | 'govt' | 'nature',
    field: string,
    kind: 'positive' | 'negative',
    value: string,
  ) => {
    setMatrixSet(layer, (prev) => {
      const cell = { ...prev[slot] } as MatrixCell;
      const infl = { ...(cell.influences || {}) };
      const current = { positive: '', negative: '', ...(infl[field] || {}) };
      current[kind] = value;
      infl[field] = current;
      cell.influences = infl;
      return { ...prev, [slot]: cell };
    });
  };

  const addMilestone = () => setMilestones([...milestones, { description: '', timeline: '' }]);
  const removeMilestone = (i: number) => { if (milestones.length > 1) setMilestones(milestones.filter((_, idx) => idx !== i)); };
  const updateMilestone = (i: number, field: string, val: string) => {
    const u = [...milestones]; u[i] = { ...u[i], [field]: val }; setMilestones(u);
  };

  const addActionItem = () => setActionItems([...actionItems, { who: '', what: '', by_when: '', status: 'pending' }]);
  const removeActionItem = (i: number) => { if (actionItems.length > 1) setActionItems(actionItems.filter((_, idx) => idx !== i)); };
  const updateActionItem = (i: number, field: keyof ActionItem, val: string) => {
    const u = [...actionItems]; u[i] = { ...u[i], [field]: val }; setActionItems(u);
  };

  // ---------- Renderers ----------
  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <ActivityIndicator size="large" color={COLORS.primary} style={{ marginTop: 40 }} />
      </SafeAreaView>
    );
  }

  const layerLabels: any = { self: 'SELF', micro: 'MICRO', macro: 'MACRO' };
  const layerColors: any = { self: '#10B981', micro: '#6366F1', macro: '#F59E0B' };

  const renderMatrixSection = () => {
    const layerSet = getMatrixSet(activeMatrixTab);
    const slot = matrixMode === 'standard' ? 'aggregate' : activeOrgType;
    const cell = layerSet[slot] as MatrixCell;
    const cellColor = matrixMode === 'standard'
      ? layerColors[activeMatrixTab]
      : (ORG_TYPES.find(o => o.key === slot)?.color || layerColors[activeMatrixTab]);

    return (
      <View>
        <Text style={styles.sectionHeader}>Solution Matrix (3.1.2)</Text>

        {/* Mode toggle */}
        <View style={styles.modeToggleRow}>
          <TouchableOpacity
            style={[styles.modeChip, matrixMode === 'standard' && styles.modeChipActive]}
            onPress={() => setMatrixMode('standard')}
          >
            <Ionicons name="apps" size={14} color={matrixMode === 'standard' ? '#FFF' : COLORS.textMuted} />
            <Text style={[styles.modeChipText, matrixMode === 'standard' && { color: '#FFF' }]}>
              Standard · 15 cells
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.modeChip, matrixMode === 'accurate' && styles.modeChipActive]}
            onPress={() => setMatrixMode('accurate')}
          >
            <Ionicons name="grid" size={14} color={matrixMode === 'accurate' ? '#FFF' : COLORS.textMuted} />
            <Text style={[styles.modeChipText, matrixMode === 'accurate' && { color: '#FFF' }]}>
              Accurate · 60 cells
            </Text>
          </TouchableOpacity>
        </View>
        <Text style={styles.sectionHint}>
          {matrixMode === 'standard'
            ? '5 TEPFI elements × 3 layers (Self / Micro / Macro) = 15 cells. Quick entry.'
            : '5 TEPFI elements × 12 (3 layers × 4 OrgTypes) = 60 cells. Cross-stakeholder view.'}
        </Text>

        {/* Layer tabs */}
        <View style={styles.matrixTabs}>
          {(['self', 'micro', 'macro'] as const).map(tab => (
            <TouchableOpacity
              key={tab}
              style={[styles.matrixTab, activeMatrixTab === tab && { backgroundColor: layerColors[tab] }]}
              onPress={() => setActiveMatrixTab(tab)}
            >
              <Text style={[styles.matrixTabText, activeMatrixTab === tab && { color: '#FFF' }]}>
                {layerLabels[tab]}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* OrgType sub-tabs (only in Accurate mode) */}
        {matrixMode === 'accurate' && visibleOrgTypes.length > 0 && (
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.orgTypeTabsScroll}>
            <View style={styles.orgTypeTabs}>
              {visibleOrgTypes.map(ot => {
                const f = checkFeature(ot.feature_id);
                const locked = f.access_level === 'locked';
                const sel = activeOrgType === ot.key;
                return (
                  <TouchableOpacity
                    key={ot.key}
                    style={[styles.orgTypeTab, sel && { backgroundColor: ot.color, borderColor: ot.color }, locked && styles.orgTypeTabLocked]}
                    onPress={() => {
                      if (locked) {
                        showAlert('Locked', `${ot.label} column is a paid feature. Upgrade to unlock.`);
                        return;
                      }
                      setActiveOrgType(ot.key);
                    }}
                  >
                    <Ionicons name={locked ? 'lock-closed' : (ot.icon as any)} size={14} color={sel ? '#FFF' : ot.color} />
                    <Text style={[styles.orgTypeTabText, sel && { color: '#FFF' }, locked && { color: COLORS.textMuted }]}>
                      {ot.label}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </ScrollView>
        )}

        {/* Cell body */}
        <View style={[styles.matrixCard, { borderLeftColor: cellColor }]}>
          <View style={styles.matrixScope}>
            <Text style={[styles.matrixScopeText, { color: cellColor }]}>
              {layerLabels[activeMatrixTab]}
              {matrixMode === 'accurate' ? ` • ${ORG_TYPES.find(o => o.key === slot)?.label}` : ' • Aggregate'}
            </Text>
          </View>

          {TEPFI_FIELDS.map(f => {
            const expanded = expandedInfluenceField === `${activeMatrixTab}:${slot}:${f.key}`;
            const inf = cell.influences?.[f.key] || { positive: '', negative: '' };
            return (
              <View key={f.key}>
                <View style={styles.matrixFieldLabel}>
                  <Ionicons name={f.icon as any} size={14} color={cellColor} />
                  <Text style={styles.matrixFieldText}>{f.label}</Text>
                  <TouchableOpacity
                    onPress={() => setExpandedInfluenceField(expanded ? null : `${activeMatrixTab}:${slot}:${f.key}`)}
                    style={styles.influenceToggle}
                  >
                    <Ionicons
                      name={expanded ? 'chevron-up' : 'add-circle-outline'}
                      size={16}
                      color={COLORS.primary}
                    />
                    <Text style={styles.influenceToggleText}>
                      {expanded ? 'Hide influence' : 'Add +/-'}
                    </Text>
                  </TouchableOpacity>
                </View>
                <TextInput
                  style={styles.matrixInput}
                  placeholder={`${f.label} details`}
                  placeholderTextColor={COLORS.textMuted}
                  value={(cell as any)[f.key] || ''}
                  onChangeText={v => updateCellField(activeMatrixTab, slot as any, f.key, v)}
                  multiline numberOfLines={2}
                />
                {expanded && (
                  <View style={styles.influenceBlock}>
                    <View style={styles.influenceRow}>
                      <Ionicons name="add-circle" size={14} color="#10B981" />
                      <Text style={styles.influenceLabel}>Positive influence</Text>
                    </View>
                    <TextInput
                      style={[styles.matrixInput, styles.influenceInput]}
                      placeholder="How does this help?"
                      placeholderTextColor={COLORS.textMuted}
                      value={inf.positive}
                      onChangeText={v => updateInfluence(activeMatrixTab, slot as any, f.key, 'positive', v)}
                      multiline numberOfLines={2}
                    />
                    <View style={styles.influenceRow}>
                      <Ionicons name="remove-circle" size={14} color="#EF4444" />
                      <Text style={styles.influenceLabel}>Negative influence</Text>
                    </View>
                    <TextInput
                      style={[styles.matrixInput, styles.influenceInput]}
                      placeholder="How does this hurt?"
                      placeholderTextColor={COLORS.textMuted}
                      value={inf.negative}
                      onChangeText={v => updateInfluence(activeMatrixTab, slot as any, f.key, 'negative', v)}
                      multiline numberOfLines={2}
                    />
                  </View>
                )}
              </View>
            );
          })}
        </View>
      </View>
    );
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <View>
            <Text style={styles.stepLabel}>Select Area of Life</Text>
            <View style={styles.areaGrid}>
              {LIFE_AREAS.map(area => (
                <TouchableOpacity
                  key={area.id}
                  style={[styles.areaChip, areaOfLife === area.id && styles.areaChipActive]}
                  onPress={() => setAreaOfLife(area.id)}
                >
                  <Ionicons name={area.icon as any} size={16} color={areaOfLife === area.id ? '#FFF' : COLORS.primary} />
                  <Text style={[styles.areaChipText, areaOfLife === area.id && styles.areaChipTextActive]}>{area.name}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <Text style={styles.stepLabel}>SMART Goal</Text>
            <TextInput
              style={styles.textArea}
              placeholder="Specific, Measurable, Achievable, Relevant, Time-bound goal"
              placeholderTextColor={COLORS.textMuted}
              value={smartGoal}
              onChangeText={setSmartGoal}
              multiline numberOfLines={3}
            />
            <View style={styles.labelRow}>
              <Text style={styles.stepLabel}>Milestones</Text>
              <TouchableOpacity onPress={addMilestone}>
                <Ionicons name="add-circle" size={22} color={COLORS.primary} />
              </TouchableOpacity>
            </View>
            {milestones.map((m, i) => (
              <View key={i} style={styles.milestoneCard}>
                <View style={styles.milestoneHeader}>
                  <Text style={styles.milestoneNum}>#{i + 1}</Text>
                  {milestones.length > 1 && (
                    <TouchableOpacity onPress={() => removeMilestone(i)}>
                      <Ionicons name="close-circle" size={20} color={COLORS.error} />
                    </TouchableOpacity>
                  )}
                </View>
                <TextInput style={styles.input} placeholder="Milestone description" placeholderTextColor={COLORS.textMuted}
                  value={m.description} onChangeText={v => updateMilestone(i, 'description', v)} />
                <TextInput style={styles.input} placeholder="Timeline" placeholderTextColor={COLORS.textMuted}
                  value={m.timeline} onChangeText={v => updateMilestone(i, 'timeline', v)} />
              </View>
            ))}
          </View>
        );
      case 1:
        return (
          <View>
            <Text style={styles.stepLabel}>Q1. What are ALL your concerns?</Text>
            <TextInput style={styles.textArea} placeholder="List all concerns..." placeholderTextColor={COLORS.textMuted}
              value={q1AllConcerns} onChangeText={setQ1AllConcerns} multiline numberOfLines={5} />
            <Text style={styles.stepLabel}>Q2. What are your PRIORITY concerns?</Text>
            <TextInput style={styles.textArea} placeholder="Top priorities..." placeholderTextColor={COLORS.textMuted}
              value={q2PriorityConcerns} onChangeText={setQ2PriorityConcerns} multiline numberOfLines={4} />
          </View>
        );
      case 2:
        return (
          <View>
            <Text style={styles.sectionHeader}>(3.1.1) Simpler Solutions</Text>
            <Text style={styles.stepLabel}>Solutions within Current Influence Level</Text>
            <TextInput style={styles.textArea} placeholder="What can you do now?" placeholderTextColor={COLORS.textMuted}
              value={simplerSolutions} onChangeText={setSimplerSolutions} multiline numberOfLines={4} />
            <Text style={styles.stepLabel}>Current Capabilities</Text>
            <TextInput style={styles.textArea} placeholder="Knowledge, Skills..." placeholderTextColor={COLORS.textMuted}
              value={simplerCapabilities} onChangeText={setSimplerCapabilities} multiline numberOfLines={3} />
            <Text style={styles.stepLabel}>Resources at Present</Text>
            <TextInput style={styles.textArea} placeholder="Contacts, Time, Money, Assets..." placeholderTextColor={COLORS.textMuted}
              value={simplerResources} onChangeText={setSimplerResources} multiline numberOfLines={3} />
            <Text style={styles.sectionHeader}>External Help</Text>
            <TextInput style={styles.input} placeholder="What aspect needs help?" placeholderTextColor={COLORS.textMuted}
              value={simplerHelpAspect} onChangeText={setSimplerHelpAspect} />
            <TextInput style={styles.input} placeholder="Level of help (Consulting/Problem Solving/Coaching)" placeholderTextColor={COLORS.textMuted}
              value={simplerHelpLevel} onChangeText={setSimplerHelpLevel} />
            <TextInput style={styles.input} placeholder="Help from whom?" placeholderTextColor={COLORS.textMuted}
              value={simplerHelpFrom} onChangeText={setSimplerHelpFrom} />
          </View>
        );
      case 3:
        return renderMatrixSection();
      case 4:
        return (
          <View>
            <Text style={styles.sectionHeader}>(3.2) Solution Category</Text>
            <Text style={styles.hint}>Select all that apply</Text>
            {SOLUTION_CATEGORIES.map(cat => (
              <TouchableOpacity
                key={cat.key}
                style={[styles.categoryRow, solutionCategory[cat.key] && { backgroundColor: cat.color + '15', borderColor: cat.color }]}
                onPress={() => setSolutionCategory(prev => ({ ...prev, [cat.key]: !prev[cat.key] }))}
              >
                <Ionicons
                  name={solutionCategory[cat.key] ? 'checkbox' : 'square-outline'}
                  size={22}
                  color={solutionCategory[cat.key] ? cat.color : COLORS.textMuted}
                />
                <Text style={[styles.categoryText, solutionCategory[cat.key] && { color: cat.color, fontWeight: '600' }]}>
                  {cat.label}
                </Text>
              </TouchableOpacity>
            ))}

            <Text style={[styles.sectionHeader, { marginTop: 24 }]}>(3.3) Solution Sources</Text>
            {SOLUTION_SOURCES.map(src => (
              <View key={src.key}>
                <View style={styles.sourceLabel}>
                  <Ionicons name={src.icon as any} size={16} color={COLORS.primary} />
                  <Text style={styles.sourceLabelText}>{src.label}</Text>
                </View>
                <TextInput
                  style={styles.textArea}
                  placeholder={`Describe solution from ${src.label.replace('Solution from ', '')}...`}
                  placeholderTextColor={COLORS.textMuted}
                  value={solutionSources[src.key]}
                  onChangeText={v => setSolutionSources(prev => ({ ...prev, [src.key]: v }))}
                  multiline numberOfLines={2}
                />
              </View>
            ))}
          </View>
        );
      case 5:
        return (
          <View>
            <Text style={styles.sectionHeader}>Q4. Risk Management</Text>
            <Text style={styles.stepLabel}>Possible Negative Consequences</Text>
            <TextInput style={styles.textArea} placeholder="What could go wrong?" placeholderTextColor={COLORS.textMuted}
              value={q4NegConsequences} onChangeText={setQ4NegConsequences} multiline numberOfLines={4} />
            <Text style={styles.stepLabel}>Mitigation Plans</Text>
            <TextInput style={styles.textArea} placeholder="How to prevent?" placeholderTextColor={COLORS.textMuted}
              value={q4Mitigation} onChangeText={setQ4Mitigation} multiline numberOfLines={4} />
            <Text style={styles.stepLabel}>Contingency Plans</Text>
            <TextInput style={styles.textArea} placeholder="Backup plans..." placeholderTextColor={COLORS.textMuted}
              value={q4Contingency} onChangeText={setQ4Contingency} multiline numberOfLines={4} />
          </View>
        );
      case 6:
        return (
          <View>
            <Text style={styles.sectionHeader}>Q5. Action Plan</Text>
            <View style={styles.labelRow}>
              <Text style={styles.stepLabel}>Action Items</Text>
              <TouchableOpacity onPress={addActionItem}>
                <Ionicons name="add-circle" size={22} color={COLORS.primary} />
              </TouchableOpacity>
            </View>
            {actionItems.map((item, i) => (
              <View key={i} style={styles.actionCard}>
                <View style={styles.milestoneHeader}>
                  <Text style={styles.milestoneNum}>Action #{i + 1}</Text>
                  {actionItems.length > 1 && (
                    <TouchableOpacity onPress={() => removeActionItem(i)}>
                      <Ionicons name="close-circle" size={20} color={COLORS.error} />
                    </TouchableOpacity>
                  )}
                </View>
                <TextInput style={styles.input} placeholder="WHAT action?" placeholderTextColor={COLORS.textMuted}
                  value={item.what} onChangeText={v => updateActionItem(i, 'what', v)} />
                <View style={styles.twoCol}>
                  <TextInput style={[styles.input, { flex: 1 }]} placeholder="WHO does?" placeholderTextColor={COLORS.textMuted}
                    value={item.who} onChangeText={v => updateActionItem(i, 'who', v)} />
                  <TextInput style={[styles.input, { flex: 1 }]} placeholder="By WHEN?" placeholderTextColor={COLORS.textMuted}
                    value={item.by_when} onChangeText={v => updateActionItem(i, 'by_when', v)} />
                </View>
                <View style={styles.statusRow}>
                  {['pending', 'in_progress', 'completed'].map(s => (
                    <TouchableOpacity key={s}
                      style={[styles.statusChip, item.status === s && styles.statusChipActive]}
                      onPress={() => updateActionItem(i, 'status', s)}>
                      <Text style={[styles.statusChipText, item.status === s && styles.statusChipTextActive]}>
                        {s.replace('_', ' ').toUpperCase()}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </View>
            ))}
          </View>
        );
      default: return null;
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <LinearGradient colors={['#E91E63', '#8E24AA']} style={styles.header}>
          <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
            <Ionicons name="arrow-back" size={24} color="#FFF" />
          </TouchableOpacity>
          <View style={{ flex: 1 }}>
            <Text style={styles.headerTitle}>Advanced Solution Matrix</Text>
            <Text style={styles.headerSub}>Step {currentStep + 1} of {steps.length}</Text>
          </View>
          <View style={styles.headerActions}>
            {!editId && (
              <TouchableOpacity
                onPress={openTemplatePicker}
                style={styles.headerAction}
                accessibilityLabel="matrix-templates-icon"
                testID="matrix-templates-icon"
              >
                <Ionicons name="albums" size={20} color="#FFF" />
              </TouchableOpacity>
            )}
            {editId && pdfAccess.access_level !== 'hidden' && (
              <TouchableOpacity
                onPress={handleExportPdf}
                style={styles.headerAction}
                disabled={exporting}
                accessibilityLabel="matrix-download-icon"
                testID="matrix-download-icon"
              >
                {exporting ? <ActivityIndicator size="small" color="#FFF" />
                  : <Ionicons name={pdfAccess.access_level === 'locked' ? 'lock-closed' : 'download'} size={20} color="#FFF" />}
              </TouchableOpacity>
            )}
          </View>
        </LinearGradient>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.stepScroll}>
          <View style={styles.stepIndicator}>
            {steps.map((step, i) => (
              <TouchableOpacity
                key={i}
                style={[
                  styles.stepPill,
                  currentStep === i && styles.stepPillActive,
                  currentStep > i && styles.stepPillDone,
                ]}
                onPress={() => setCurrentStep(i)}
              >
                <Ionicons name={step.icon as any} size={14}
                  color={currentStep >= i ? '#FFF' : COLORS.textMuted} />
                <Text style={[styles.stepPillText, currentStep >= i && { color: '#FFF' }]} numberOfLines={1}>{step.title}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </ScrollView>

        <ScrollView style={styles.scrollView} contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
          <Text style={styles.currentStepTitle}>{steps[currentStep].title}</Text>
          {renderStepContent()}
        </ScrollView>

        <View style={styles.bottomNav}>
          {currentStep > 0 && (
            <TouchableOpacity style={styles.navBtnSecondary} onPress={() => setCurrentStep(currentStep - 1)}>
              <Ionicons name="arrow-back" size={18} color={COLORS.accent} />
              <Text style={[styles.navBtnSecondaryText, { color: COLORS.accent }]}>Back</Text>
            </TouchableOpacity>
          )}
          <View style={{ flex: 1 }} />
          {currentStep < steps.length - 1 ? (
            <TouchableOpacity style={[styles.navBtnPrimary, { backgroundColor: COLORS.accent }]}
              onPress={() => setCurrentStep(currentStep + 1)}>
              <Text style={styles.navBtnPrimaryText}>Next</Text>
              <Ionicons name="arrow-forward" size={18} color="#FFF" />
            </TouchableOpacity>
          ) : (
            <TouchableOpacity
              style={[styles.navBtnPrimary, { backgroundColor: COLORS.accent }, saving && { opacity: 0.7 }]}
              onPress={handleSave} disabled={saving}>
              {saving ? <ActivityIndicator size="small" color="#FFF" /> : (
                <><Ionicons name="checkmark-circle" size={18} color="#FFF" />
                <Text style={styles.navBtnPrimaryText}>Save</Text></>
              )}
            </TouchableOpacity>
          )}
        </View>

        {/* Templates Modal */}
        <Modal visible={tplModalOpen} animationType="slide" transparent>
          <View style={styles.modalOverlay}>
            <View style={styles.modalSheet}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>Starter Templates</Text>
                <TouchableOpacity onPress={() => setTplModalOpen(false)}>
                  <Ionicons name="close-circle" size={26} color={COLORS.textMuted} />
                </TouchableOpacity>
              </View>
              <Text style={styles.modalHint}>Tap one to load — you can edit anything after.</Text>
              <ScrollView style={{ maxHeight: '80%' }}>
                {tplLoading ? (
                  <ActivityIndicator size="large" color={COLORS.primary} style={{ marginVertical: 24 }} />
                ) : templates.length === 0 ? (
                  <Text style={styles.modalEmpty}>No templates available.</Text>
                ) : (
                  templates.map(t => (
                    <TouchableOpacity
                      key={t.template_id}
                      style={[styles.templateCard, { borderLeftColor: t.color }]}
                      onPress={() => applyTemplate(t.template_id)}
                      disabled={applyingTpl !== null}
                    >
                      <View style={[styles.templateIcon, { backgroundColor: t.color + '22' }]}>
                        <Ionicons name={t.icon as any} size={22} color={t.color} />
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.templateTitle}>{t.title}</Text>
                        <Text style={styles.templateSub}>{t.subtitle}</Text>
                        <View style={styles.templateTags}>
                          <View style={[styles.tplTag, { backgroundColor: t.color + '15' }]}>
                            <Text style={[styles.tplTagText, { color: t.color }]}>{t.org_type}</Text>
                          </View>
                          <View style={styles.tplTag}>
                            <Text style={styles.tplTagText}>{t.matrix_mode}</Text>
                          </View>
                        </View>
                      </View>
                      {applyingTpl === t.template_id ? (
                        <ActivityIndicator size="small" color={t.color} />
                      ) : (
                        <Ionicons name="chevron-forward" size={20} color={COLORS.textMuted} />
                      )}
                    </TouchableOpacity>
                  ))
                )}
              </ScrollView>
            </View>
          </View>
        </Modal>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: { flexDirection: 'row', alignItems: 'center', padding: 16, paddingBottom: 20 },
  backBtn: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center', alignItems: 'center', marginRight: 12,
  },
  headerTitle: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  headerSub: { fontSize: 12, color: 'rgba(255,255,255,0.7)', marginTop: 2 },
  headerActions: { flexDirection: 'row', gap: 8 },
  headerAction: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: 'rgba(255,255,255,0.2)',
    justifyContent: 'center', alignItems: 'center',
  },
  stepScroll: { backgroundColor: COLORS.white, borderBottomWidth: 1, borderBottomColor: COLORS.border },
  stepIndicator: { flexDirection: 'row', paddingHorizontal: 12, paddingVertical: 10, gap: 8 },
  stepPill: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: 20, backgroundColor: COLORS.divider,
  },
  stepPillActive: { backgroundColor: COLORS.accent },
  stepPillDone: { backgroundColor: COLORS.success },
  stepPillText: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted },
  scrollView: { flex: 1 },
  scrollContent: { padding: 16, paddingBottom: 32 },
  currentStepTitle: { fontSize: 20, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 16 },
  stepLabel: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary, marginTop: 16, marginBottom: 6 },
  hint: { fontSize: 12, color: COLORS.textMuted, marginBottom: 8 },
  sectionHeader: {
    fontSize: 16, fontWeight: '700', color: COLORS.accent,
    marginTop: 20, marginBottom: 4,
    borderBottomWidth: 1, borderBottomColor: COLORS.border, paddingBottom: 6,
  },
  sectionHint: { fontSize: 12, color: COLORS.textMuted, marginBottom: 10, lineHeight: 17 },
  areaGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 8 },
  areaChip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: 20, borderWidth: 1, borderColor: COLORS.primary,
    backgroundColor: 'rgba(142,36,170,0.05)',
  },
  areaChipActive: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  areaChipText: { fontSize: 12, fontWeight: '500', color: COLORS.primary },
  areaChipTextActive: { color: '#FFF' },
  input: {
    backgroundColor: COLORS.white, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border,
    paddingHorizontal: 14, paddingVertical: 10, fontSize: 14, color: COLORS.textPrimary, marginBottom: 8,
  },
  textArea: {
    backgroundColor: COLORS.white, borderRadius: 10, borderWidth: 1, borderColor: COLORS.border,
    paddingHorizontal: 14, paddingVertical: 10, fontSize: 14, color: COLORS.textPrimary,
    minHeight: 80, textAlignVertical: 'top', marginBottom: 8,
  },
  labelRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  milestoneCard: {
    backgroundColor: COLORS.white, borderRadius: 12, padding: 12, marginBottom: 10,
    borderWidth: 1, borderColor: COLORS.border,
  },
  milestoneHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  milestoneNum: { fontSize: 13, fontWeight: '600', color: COLORS.primary },
  actionCard: {
    backgroundColor: COLORS.white, borderRadius: 12, padding: 12, marginBottom: 12,
    borderWidth: 1, borderColor: COLORS.border,
  },
  twoCol: { flexDirection: 'row', gap: 8 },
  statusRow: { flexDirection: 'row', gap: 6, marginTop: 4 },
  statusChip: {
    paddingHorizontal: 10, paddingVertical: 5, borderRadius: 12,
    borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.divider,
  },
  statusChipActive: { backgroundColor: COLORS.success, borderColor: COLORS.success },
  statusChipText: { fontSize: 10, fontWeight: '600', color: COLORS.textMuted },
  statusChipTextActive: { color: '#FFF' },

  // Mode toggle
  modeToggleRow: { flexDirection: 'row', gap: 8, marginVertical: 10 },
  modeChip: {
    flex: 1, flexDirection: 'row', gap: 6, alignItems: 'center', justifyContent: 'center',
    paddingVertical: 10, paddingHorizontal: 12, borderRadius: 10,
    borderWidth: 1, borderColor: COLORS.border, backgroundColor: COLORS.white,
  },
  modeChipActive: { backgroundColor: COLORS.accent, borderColor: COLORS.accent },
  modeChipText: { fontSize: 12, fontWeight: '600', color: COLORS.textMuted },

  // Matrix layout
  matrixTabs: { flexDirection: 'row', gap: 8, marginVertical: 12 },
  matrixTab: {
    flex: 1, paddingVertical: 10, borderRadius: 12,
    backgroundColor: COLORS.divider, alignItems: 'center',
  },
  matrixTabText: { fontSize: 13, fontWeight: '700', color: COLORS.textMuted },
  orgTypeTabsScroll: { marginBottom: 10 },
  orgTypeTabs: { flexDirection: 'row', gap: 8 },
  orgTypeTab: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: 20, borderWidth: 1, borderColor: COLORS.border,
    backgroundColor: COLORS.white,
  },
  orgTypeTabLocked: { opacity: 0.6 },
  orgTypeTabText: { fontSize: 12, fontWeight: '600', color: COLORS.textPrimary },
  matrixCard: {
    backgroundColor: COLORS.white, borderRadius: 12, padding: 14,
    borderWidth: 1, borderColor: COLORS.border,
    borderLeftWidth: 4,
  },
  matrixScope: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 8 },
  matrixScopeText: { fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  matrixFieldLabel: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    marginTop: 10, marginBottom: 4,
  },
  matrixFieldText: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, flex: 1 },
  influenceToggle: { flexDirection: 'row', alignItems: 'center', gap: 3 },
  influenceToggleText: { fontSize: 11, color: COLORS.primary, fontWeight: '600' },
  matrixInput: {
    backgroundColor: COLORS.background, borderRadius: 8, borderWidth: 1, borderColor: COLORS.border,
    paddingHorizontal: 12, paddingVertical: 8, fontSize: 13, color: COLORS.textPrimary,
    minHeight: 50, textAlignVertical: 'top',
  },
  influenceBlock: {
    marginTop: 6, marginBottom: 4, padding: 10,
    backgroundColor: '#F8FAFC', borderRadius: 8,
    borderLeftWidth: 2, borderLeftColor: '#94A3B8',
  },
  influenceRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 4, marginTop: 4 },
  influenceLabel: { fontSize: 11, fontWeight: '700', color: COLORS.textPrimary },
  influenceInput: { minHeight: 40 },

  categoryRow: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    paddingHorizontal: 14, paddingVertical: 12,
    borderRadius: 10, borderWidth: 1, borderColor: COLORS.border,
    backgroundColor: COLORS.white, marginBottom: 8,
  },
  categoryText: { fontSize: 14, color: COLORS.textPrimary, flex: 1 },
  sourceLabel: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 12, marginBottom: 4 },
  sourceLabelText: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary },

  bottomNav: {
    flexDirection: 'row', alignItems: 'center', padding: 16,
    borderTopWidth: 1, borderTopColor: COLORS.border, backgroundColor: COLORS.white,
  },
  navBtnSecondary: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 16, paddingVertical: 10,
    borderRadius: 10, borderWidth: 1, borderColor: COLORS.accent,
  },
  navBtnSecondaryText: { fontSize: 14, fontWeight: '600' },
  navBtnPrimary: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: 20, paddingVertical: 12, borderRadius: 10,
  },
  navBtnPrimaryText: { fontSize: 14, fontWeight: '600', color: '#FFF' },

  // Templates Modal
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  modalSheet: {
    backgroundColor: COLORS.background,
    borderTopLeftRadius: 20, borderTopRightRadius: 20,
    padding: 16, maxHeight: '86%',
  },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  modalTitle: { fontSize: 18, fontWeight: '700', color: COLORS.textPrimary },
  modalHint: { fontSize: 12, color: COLORS.textMuted, marginBottom: 12 },
  modalEmpty: { textAlign: 'center', color: COLORS.textMuted, padding: 24 },
  templateCard: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: COLORS.white,
    borderRadius: 12, borderWidth: 1, borderColor: COLORS.border,
    borderLeftWidth: 4,
    padding: 12, marginBottom: 10,
  },
  templateIcon: {
    width: 44, height: 44, borderRadius: 22,
    justifyContent: 'center', alignItems: 'center',
  },
  templateTitle: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  templateSub: { fontSize: 12, color: COLORS.textMuted, marginTop: 2 },
  templateTags: { flexDirection: 'row', gap: 6, marginTop: 6 },
  tplTag: {
    paddingHorizontal: 8, paddingVertical: 3,
    borderRadius: 12, backgroundColor: COLORS.divider,
  },
  tplTagText: { fontSize: 10, fontWeight: '700', color: COLORS.textMuted, textTransform: 'uppercase' },
});
