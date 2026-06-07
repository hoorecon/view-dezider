import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { showAlert } from '../../src/utils/alert';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput,
  ActivityIndicator, Alert, KeyboardAvoidingView, Platform, FlatList,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { COLORS } from '../../src/constants/colors';
import { useAuthStore } from '../../src/store/authStore';
import { safeBack, goHome } from '../../src/utils/navigation';
import api from '../../src/utils/api';
import TimingFieldset, { TimingValue } from '../../src/components/decisions/TimingFieldset';
import { addDaysISO } from '../../src/utils/dateLocalize';

// ====== TYPES ======
interface LifeArea { id: string; name: string; slug: string; icon: string; color: string; order: number; }
interface AskType { id: string; name: string; slug: string; icon: string; color: string; description: string; priority_label: string; }
interface SubArea { id: string; name: string; life_area_id: string; }
interface Scenario {
  id: string; title: string; sub_area_id?: string; life_area_id?: string;
  representative_template_id?: string; template_count?: number;
}
interface Template {
  id: string; title: string; description: string; template_type: string;
  tags?: string[]; popularity?: number; life_area_id: string; ask_type_id: string;
  acting_as_contexts: string[]; applies_to_modules?: string[]; org_types?: string[];
  decision_types?: string[];
  // SWOT templates carry per-factor S/W/O/T flags. We expose the array so the
  // picker can render small color-coded counts as a preview.
  factors?: Array<{ id?: string; name?: string; swot_flag?: 'S' | 'W' | 'O' | 'T' | null }>;
}
type ModuleKey = 'dezider' | 'swot' | 'pros-cons';

// ====== CONSTANTS ======
// 6 OrgType cards. Width tuned so 2 fit per row on mobile, 3 per row on web.
const ACTING_AS = [
  { key: 'INDIVIDUAL',    label: 'Individual',             icon: 'person',           color: '#6366F1', desc: 'Self / family' },
  { key: 'BUSINESS_ORG',  label: 'Business Organization',  icon: 'business',         color: '#0EA5E9', desc: 'Company / startup / SMB' },
  { key: 'ACADEMIC_ORG',  label: 'Academic Organization',  icon: 'school',           color: '#F59E0B', desc: 'School / college / research' },
  { key: 'NONPROFIT_ORG', label: 'Non-profit Organization',icon: 'heart',            color: '#10B981', desc: 'NGO / charity / foundation' },
  { key: 'ASSOCIATION',   label: 'Association',            icon: 'people-circle',    color: '#F43F5E', desc: 'Society / club / housing' },
  { key: 'GOVERNMENT',    label: 'Government',             icon: 'globe',            color: '#8B5CF6', desc: 'Public / policy / civic' },
];

const TEMPLATE_TYPE_CONFIG: Record<string, { label: string; color: string; icon: string }> = {
  AUTHORIZED_STANDARD: { label: 'Curated', color: '#10B981', icon: 'shield-checkmark' },
  DYNAMIC_CLD_STARTER: { label: 'CLD Starter', color: '#F59E0B', icon: 'flash' },
};

// SWOT flag color map — used to render small letter chips on template cards
// when the user is in the SWOT module. Mirrors the quadrant colours used in
// /tools/swot.tsx so the visual language stays consistent across screens.
const SWOT_FLAG_META: Record<'S' | 'W' | 'O' | 'T', { label: string; color: string; bg: string }> = {
  S: { label: 'S', color: '#059669', bg: '#ECFDF5' },
  W: { label: 'W', color: '#DC2626', bg: '#FEF2F2' },
  O: { label: 'O', color: '#2563EB', bg: '#EFF6FF' },
  T: { label: 'T', color: '#D97706', bg: '#FFFBEB' },
};

// Module-specific configuration: header, gradient, step list, post-create route.
const MODULE_CONFIG: Record<ModuleKey, {
  title: string;
  subtitle: string;
  gradient: [string, string];
  hasTemplatesStep: boolean;
  finalButtonLabel: string;
}> = {
  'dezider': {
    title: 'My Dezider', subtitle: 'New Decision',
    gradient: ['#6366F1', '#8B5CF6'],
    hasTemplatesStep: true, finalButtonLabel: 'Find Templates',
  },
  'swot': {
    title: 'SWOT Analysis', subtitle: 'New SWOT',
    gradient: ['#1E40AF', '#3B82F6'],
    hasTemplatesStep: true, finalButtonLabel: 'Find Templates',
  },
  'pros-cons': {
    title: 'Pros & Cons', subtitle: 'New Analysis',
    gradient: ['#7C3AED', '#A855F7'],
    hasTemplatesStep: false, finalButtonLabel: 'Create & Start Wizard',
  },
};

const STEPS_BASE = ['Life Area', 'Context', 'Ask Type', 'Define'];
const STEPS_WITH_TEMPLATES = [...STEPS_BASE, 'Choose Template'];

export default function NewDecisionIntake() {
  const router = useRouter();
  const { user } = useAuthStore();
  const params = useLocalSearchParams<{ module?: string }>();

  // Module key from URL (?module=dezider|swot|pros-cons). Defaults to dezider.
  const moduleKey: ModuleKey = useMemo(() => {
    const m = String(params.module || 'dezider').toLowerCase();
    return (m === 'swot' || m === 'pros-cons') ? m as ModuleKey : 'dezider';
  }, [params.module]);
  const moduleCfg = MODULE_CONFIG[moduleKey];
  const STEPS = moduleCfg.hasTemplatesStep ? STEPS_WITH_TEMPLATES : STEPS_BASE;

  // Step tracking
  const [step, setStep] = useState(0);

  // Selections
  const [actingAs, setActingAs] = useState('INDIVIDUAL');
  const [selectedArea, setSelectedArea] = useState<LifeArea | null>(null);
  const [selectedAskType, setSelectedAskType] = useState<AskType | null>(null);
  const [searchText, setSearchText] = useState('');
  const [customTitle, setCustomTitle] = useState('');
  // Timing (added on Initial-Info Step 4 so deadline + impact horizon flow
  // into the PRR decision from the very start). Default = 1 week.
  const [timing, setTiming] = useState<TimingValue>({
    deadline_date: addDaysISO(7),
    impact_horizon_value: 7,
    impact_horizon_unit: 'days',
  });

  // Step-4 new structured fields
  const [selectedSubArea, setSelectedSubArea] = useState<SubArea | null>(null);
  const [selectedScenario, setSelectedScenario] = useState<Scenario | null>(null);
  const [aiParsing, setAiParsing] = useState(false);

  // Data
  const [lifeAreas, setLifeAreas] = useState<LifeArea[]>([]);
  const [askTypes, setAskTypes] = useState<AskType[]>([]);
  const [subAreas, setSubAreas] = useState<SubArea[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);

  // Loading
  const [loadingAreas, setLoadingAreas] = useState(true);
  const [loadingTypes, setLoadingTypes] = useState(true);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [creating, setCreating] = useState(false);
  const [seeding, setSeeding] = useState(false);

  // ====== SEED + FETCH ======
  const seedAndFetch = useCallback(async () => {
    try {
      // Seed master data (idempotent)
      setSeeding(true);
      await api.post('/hos/seed');
    } catch (_e) { /* already seeded or error */ }
    setSeeding(false);

    // Fetch life areas
    setLoadingAreas(true);
    try {
      const r = await api.get('/hos/life-areas');
      setLifeAreas(r.data || []);
    } catch (_e) { setLifeAreas([]); }
    setLoadingAreas(false);

    // Fetch ask types
    setLoadingTypes(true);
    try {
      const r = await api.get('/hos/ask-types');
      setAskTypes(r.data || []);
    } catch (_e) { setAskTypes([]); }
    setLoadingTypes(false);
  }, []);

  useEffect(() => { seedAndFetch(); }, [seedAndFetch]);

  // Fetch templates when context is ready
  useEffect(() => {
    if (selectedArea && selectedAskType) {
      fetchTemplates();
    }
  }, [selectedArea, selectedAskType, searchText]);

  const fetchTemplates = async () => {
    if (!selectedArea || !selectedAskType) return;
    setLoadingTemplates(true);
    try {
      const params = new URLSearchParams({
        acting_as: actingAs,
        life_area_id: selectedArea.id,
        ask_type_id: selectedAskType.id,
        module: moduleKey,
      });
      if (selectedSubArea) params.append('sub_area_id', selectedSubArea.id);
      if (searchText.trim()) params.append('q', searchText.trim());
      const r = await api.get(`/hos/templates/suggest?${params}`);
      setTemplates(r.data || []);
    } catch (_e) { setTemplates([]); }
    setLoadingTemplates(false);
  };

  // Fetch sub-areas when life area selected
  useEffect(() => {
    if (selectedArea) {
      api.get(`/hos/sub-areas?life_area_id=${selectedArea.id}`)
        .then(r => setSubAreas(r.data || []))
        .catch(() => setSubAreas([]));
      // Reset Step-4 dependent state
      setSelectedSubArea(null);
      setSelectedScenario(null);
    }
  }, [selectedArea]);

  // Fetch scenarios when life area / sub area changes
  useEffect(() => {
    if (!selectedArea) { setScenarios([]); return; }
    const p = new URLSearchParams({
      life_area_id: selectedArea.id,
      module: moduleKey,
      limit: '50',
    });
    if (selectedSubArea) p.append('sub_area_id', selectedSubArea.id);
    api.get(`/hos/scenarios?${p}`)
      .then(r => setScenarios(r.data || []))
      .catch(() => setScenarios([]));
  }, [selectedArea, selectedSubArea, moduleKey]);

  // AI-parse: when user types in the free-text box, attempt to match a
  // Sub-area and Scenario via lightweight keyword scoring (no LLM call —
  // cheap & instant). Triggered debounced via onEndEditing/onBlur.
  const aiParseFreeText = useCallback(() => {
    const q = searchText.trim().toLowerCase();
    if (!q || q.length < 4) return;
    setAiParsing(true);
    try {
      // Sub-area match: pick the one whose name shares the most word tokens with the query
      if (!selectedSubArea && subAreas.length) {
        const score = (sa: SubArea) => {
          const tokens = sa.name.toLowerCase().split(/\W+/).filter(t => t.length > 2);
          return tokens.reduce((s, t) => s + (q.includes(t) ? 1 : 0), 0);
        };
        let best: SubArea | null = null; let bestScore = 0;
        for (const sa of subAreas) {
          const sc = score(sa);
          if (sc > bestScore) { best = sa; bestScore = sc; }
        }
        if (best && bestScore >= 1) setSelectedSubArea(best);
      }
      // Scenario match: same approach using scenario.title
      if (!selectedScenario && scenarios.length) {
        const score = (s: Scenario) => {
          const tokens = s.title.toLowerCase().split(/\W+/).filter(t => t.length > 2);
          return tokens.reduce((acc, t) => acc + (q.includes(t) ? 1 : 0), 0);
        };
        let best: Scenario | null = null; let bestScore = 0;
        for (const s of scenarios) {
          const sc = score(s);
          if (sc > bestScore) { best = s; bestScore = sc; }
        }
        if (best && bestScore >= 1) setSelectedScenario(best);
      }
    } finally {
      setAiParsing(false);
    }
  }, [searchText, subAreas, scenarios, selectedSubArea, selectedScenario]);

  // ====== DETERMINE ACTING AS FROM USER CONTEXT ======
  useEffect(() => {
    // If user belongs to an org, pre-select the most likely OrgType.
    // Defaults to BUSINESS_ORG (most common) — user can change to academic/non-profit/etc.
    if (user?.org_id) setActingAs('BUSINESS_ORG');
  }, [user]);

  // ====== SMART-DEFAULT TITLE ======
  // Computed in real-time so the placeholder in Step-4 title input updates as
  // the user picks Sub-area / Scenario. Used both as placeholder and as the
  // final fallback when the user leaves the title field empty.
  const smartDefaultTitle = useMemo(() => {
    const ts = new Date();
    const stamp = ts.toLocaleString('en-IN', {
      day: 'numeric', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit', hour12: false,
    });
    if (selectedScenario) return `${selectedScenario.title} — ${stamp}`;
    if (selectedSubArea)  return `${selectedSubArea.name} — ${stamp}`;
    if (selectedArea)     return `${selectedArea.name} — ${stamp}`;
    return `New Decision — ${stamp}`;
  }, [selectedScenario, selectedSubArea, selectedArea]);

  // ====== CREATE PROS & CONS analysis (P&C path skips Step 5) ======
  const createProsConsAnalysis = async () => {
    if (!selectedArea) {
      showAlert('Missing Context', 'Please choose a Life Area before continuing.');
      return;
    }
    setCreating(true);
    try {
      const title = customTitle.trim() || smartDefaultTitle;
      const r = await api.post('/pros-cons', {
        title,
        context: searchText.trim(),
        life_area: selectedArea.id,
        decision_type: selectedAskType?.slug || selectedAskType?.id || undefined,
        acting_as_context: actingAs,
        sub_area_id: selectedSubArea?.id || undefined,
        sub_area_name: selectedSubArea?.name || undefined,
        scenario_id: selectedScenario?.id || undefined,
        scenario_title: selectedScenario?.title || undefined,
      });
      const id = r.data?.id;
      if (id) {
        router.replace(`/tools/pros-cons-wizard?id=${id}&module=pros-cons` as any);
      } else {
        showAlert('Error', 'Could not create Pros & Cons analysis.');
      }
    } catch (e: any) {
      showAlert('Error', e?.response?.data?.detail || 'Failed to create analysis.');
    } finally {
      setCreating(false);
    }
  };

  // ====== CREATE DECISION ======
  const handleCreateDecision = async (templateId?: string, sourceType?: string) => {
    // Carry forward the Step-4 title. When the user left it blank on the
    // "Create from scratch" path, fall back to the smart-default title (same
    // value shown as the placeholder/hint) so we never block them with a
    // "Title Required" prompt. For template picks we keep blank → the template's
    // own title is used downstream.
    const title = customTitle.trim() || searchText.trim() || (templateId ? '' : smartDefaultTitle);
    if (!title && !templateId) {
      showAlert('Title Required', 'Please enter a decision title or select a template.');
      return;
    }
    if (!selectedArea || !selectedAskType) {
      showAlert('Missing Context', 'Please select a life area and ask type.');
      return;
    }

    setCreating(true);
    try {
      const payload = {
        acting_as_context: actingAs,
        life_area_id: selectedArea.id,
        ask_type_id: selectedAskType.id,
        template_id: templateId || undefined,
        title: title || (templateId ? templates.find(t => t.id === templateId)?.title || 'New Decision' : 'New Decision'),
        raw_user_input: searchText.trim() || title,
        source_type: sourceType || (templateId ? 'AUTHORIZED_STANDARD' : 'CUSTOM_BLANK'),
        // Timing captured on Initial-Info Step 4 — flows through to the PRR
        // decision doc, Action Center handoffs, and downstream reminders.
        deadline_date: timing.deadline_date || null,
        impact_horizon_value: timing.impact_horizon_value ?? null,
        impact_horizon_unit: timing.impact_horizon_unit || null,
      };

      const r = await api.post('/hos/decisions', payload);
      const decisionId = r.data.id;
      const factorsLoaded = r.data.factors_loaded || 0;

      if (factorsLoaded > 0) {
        showAlert(
          'Template Loaded',
          `${factorsLoaded} pre-configured factors loaded with classifications, priorities & ratings. You can review and modify them in the PRR flow.`,
          [{ text: 'Start Analysis', onPress: () => router.replace(`/prr/${decisionId}`) }]
        );
      } else {
        router.replace(`/prr/${decisionId}`);
      }
    } catch (e: any) {
      showAlert('Error', e.response?.data?.detail || 'Failed to create decision');
    } finally {
      setCreating(false);
    }
  };

  // ====== STEP NAVIGATION ======
  const canProceed = () => {
    if (step === 0) return !!selectedArea; // Life Area is now first
    if (step === 1) return true; // acting-as (Context) always has a default
    if (step === 2) return !!selectedAskType;
    if (step === 3) return true; // search text is optional
    return true;
  };

  const nextStep = () => {
    if (step < STEPS.length - 1 && canProceed()) setStep(step + 1);
  };
  const prevStep = () => { if (step > 0) setStep(step - 1); };

  // ====== RENDERERS ======

  const renderStepIndicator = () => (
    <View style={s.stepRow}>
      {STEPS.map((label, i) => (
        <View key={i} style={s.stepItem}>
          <View style={[s.stepDot, i <= step && s.stepDotActive, i < step && s.stepDotDone]}>
            {i < step ? (
              <Ionicons name="checkmark" size={12} color="#FFF" />
            ) : (
              <Text style={[s.stepDotText, i <= step && s.stepDotTextActive]}>{i + 1}</Text>
            )}
          </View>
          {i < STEPS.length - 1 && <View style={[s.stepLine, i < step && s.stepLineActive]} />}
        </View>
      ))}
    </View>
  );

  const renderStep0 = () => (
    <View>
      <Text style={s.stepTitle}>This decision is for...</Text>
      <Text style={s.stepSubtitle}>Select the context for this decision</Text>
      <View style={s.contextCards}>
        {ACTING_AS.map(a => (
          <TouchableOpacity
            key={a.key}
            style={[s.contextCard, actingAs === a.key && { borderColor: a.color, backgroundColor: a.color + '10' }]}
            onPress={() => setActingAs(a.key)}
          >
            <View style={[s.contextIcon, { backgroundColor: a.color + '20' }]}>
              <Ionicons name={a.icon as any} size={28} color={a.color} />
            </View>
            <Text style={[s.contextLabel, actingAs === a.key && { color: a.color, fontWeight: '700' }]}>{a.label}</Text>
            <Text style={s.contextDesc}>{a.desc}</Text>
            {actingAs === a.key && (
              <View style={[s.checkCircle, { backgroundColor: a.color }]}>
                <Ionicons name="checkmark" size={14} color="#FFF" />
              </View>
            )}
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );

  const renderStep1 = () => (
    <View>
      <Text style={s.stepTitle}>Choose Life Area</Text>
      <Text style={s.stepSubtitle}>What domain does this decision belong to?</Text>
      {loadingAreas ? <ActivityIndicator style={{ marginTop: 30 }} /> : (
        <View style={s.areaGrid}>
          {lifeAreas.map(area => (
            <TouchableOpacity
              key={area.id}
              style={[s.areaCard, selectedArea?.id === area.id && { borderColor: area.color, backgroundColor: area.color + '10' }]}
              onPress={() => setSelectedArea(area)}
            >
              <Ionicons name={area.icon as any} size={24} color={selectedArea?.id === area.id ? area.color : COLORS.textMuted} />
              <Text style={[s.areaName, selectedArea?.id === area.id && { color: area.color, fontWeight: '700' }]} numberOfLines={2}>
                {area.name}
              </Text>
              {selectedArea?.id === area.id && (
                <View style={[s.areaCheck, { backgroundColor: area.color }]}>
                  <Ionicons name="checkmark" size={10} color="#FFF" />
                </View>
              )}
            </TouchableOpacity>
          ))}
        </View>
      )}
    </View>
  );

  const renderStep2 = () => (
    <View>
      <Text style={s.stepTitle}>What type of decision?</Text>
      <Text style={s.stepSubtitle}>This helps prioritize and find relevant templates</Text>
      {loadingTypes ? <ActivityIndicator style={{ marginTop: 30 }} /> : (
        <View style={s.askTypeCards}>
          {askTypes.map(t => (
            <TouchableOpacity
              key={t.id}
              style={[s.askTypeCard, selectedAskType?.id === t.id && { borderColor: t.color, backgroundColor: t.color + '10' }]}
              onPress={() => setSelectedAskType(t)}
            >
              <View style={[s.askTypeIcon, { backgroundColor: t.color + '20' }]}>
                <Ionicons name={t.icon as any} size={28} color={t.color} />
              </View>
              <View style={s.askTypeInfo}>
                <View style={s.askTypeHeader}>
                  <Text style={[s.askTypeName, selectedAskType?.id === t.id && { color: t.color }]}>{t.name}</Text>
                  <View style={[s.priorityBadge, { backgroundColor: t.color + '20' }]}>
                    <Text style={[s.priorityText, { color: t.color }]}>{t.priority_label}</Text>
                  </View>
                </View>
                <Text style={s.askTypeDesc}>{t.description}</Text>
              </View>
              {selectedAskType?.id === t.id && (
                <Ionicons name="checkmark-circle" size={22} color={t.color} />
              )}
            </TouchableOpacity>
          ))}
        </View>
      )}
    </View>
  );

  const renderStep3 = () => {
    // Step-4 (index 3): "Define" — structured form.
    // Layout: Sub-area chips → Scenario chips → Title.
    // Note: the free-text "Describe your decision" box is HIDDEN per alpha-user
    // feedback (it confused new users). All of its state/logic is retained below
    // behind SHOW_DESCRIBE_BOX so it can be re-enabled / reused later.
    const SHOW_DESCRIBE_BOX = false;
    return (
      <View>
        <Text style={s.stepTitle}>Tell us about your decision</Text>
        <Text style={s.stepSubtitle}>
          {moduleKey === 'pros-cons'
            ? "Describe it — we'll set up the analysis"
            : "Pick from suggestions — all fields are optional"}
        </Text>

        {/* Free-text — HIDDEN per UX feedback (logic retained for future reuse) */}
        {SHOW_DESCRIBE_BOX && (
          <>
            <Text style={s.fieldLabel}>Describe your decision <Text style={s.fieldOpt}>(optional)</Text></Text>
            <TextInput
              style={s.searchInput}
              placeholder='e.g. "Should I quit my job to start a startup?"'
              value={searchText}
              onChangeText={setSearchText}
              onBlur={aiParseFreeText}
              onEndEditing={aiParseFreeText}
              placeholderTextColor={COLORS.textMuted}
              multiline
              numberOfLines={2}
            />
            {!!searchText.trim() && (
              <View style={s.aiHint}>
                <Ionicons name="sparkles" size={14} color="#7C3AED" />
                <Text style={s.aiHintText}>
                  {aiParsing ? 'Parsing…' : 'AI will pre-fill Sub-area & Scenario below'}
                </Text>
              </View>
            )}
          </>
        )}

        {/* ① Sub-area chips */}
        <Text style={s.fieldLabel}>
          ① Sub-area in {selectedArea?.name} <Text style={s.fieldOpt}>(optional)</Text>
        </Text>
        {subAreas.length === 0 ? (
          <Text style={s.emptyHint}>No sub-areas configured yet for this life area.</Text>
        ) : (
          <View style={s.chipWrap}>
            {subAreas.map(sa => (
              <TouchableOpacity
                key={sa.id}
                style={[
                  s.subAreaChip,
                  selectedSubArea?.id === sa.id && { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
                ]}
                onPress={() => {
                  setSelectedSubArea(selectedSubArea?.id === sa.id ? null : sa);
                  setSelectedScenario(null); // reset scenario when sub-area changes
                }}
              >
                <Text
                  style={[
                    s.subAreaChipText,
                    selectedSubArea?.id === sa.id && { color: '#FFF', fontWeight: '700' },
                  ]}
                >{sa.name}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* ② Scenario chips */}
        <Text style={[s.fieldLabel, { marginTop: 18 }]}>
          ② Scenario <Text style={s.fieldOpt}>(optional · auto-suggest)</Text>
        </Text>
        {scenarios.length === 0 ? (
          <Text style={s.emptyHint}>
            {selectedSubArea
              ? `No scenarios authored yet for ${selectedSubArea.name}.`
              : 'Pick a sub-area above to see scenarios.'}
          </Text>
        ) : (
          <View style={s.chipWrap}>
            {scenarios.map(sc => (
              <TouchableOpacity
                key={sc.id}
                style={[
                  s.subAreaChip,
                  selectedScenario?.id === sc.id && { backgroundColor: '#7C3AED', borderColor: '#7C3AED' },
                ]}
                onPress={() => setSelectedScenario(selectedScenario?.id === sc.id ? null : sc)}
              >
                <Text
                  style={[
                    s.subAreaChipText,
                    selectedScenario?.id === sc.id && { color: '#FFF', fontWeight: '700' },
                  ]}
                >{sc.title}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* ③ Title with smart default */}
        <Text style={[s.fieldLabel, { marginTop: 18 }]}>
          ③ Decision title <Text style={s.fieldOpt}>(optional)</Text>
        </Text>
        <TextInput
          style={s.searchInput}
          placeholder={smartDefaultTitle}
          placeholderTextColor={COLORS.textMuted}
          value={customTitle}
          onChangeText={setCustomTitle}
          multiline={false}
          returnKeyType="done"
        />
        <Text style={s.hintText}>
          Leave blank to use: <Text style={{ fontWeight: '600' }}>{smartDefaultTitle}</Text>
        </Text>
      </View>
    );
  };

  const renderStep4 = () => (
    <View style={{ flex: 1 }}>
      <Text style={s.stepTitle}>Choose a template or start fresh</Text>
      <Text style={s.stepSubtitle}>
        {templates.length > 0
          ? `${templates.length} templates found for ${selectedArea?.name} / ${selectedAskType?.name}`
          : 'No templates match — create a custom decision'}
      </Text>

      {/* Custom title input — carries the Step-4 smart-default title forward so
          the user is never forced to retype it. */}
      <TextInput
        style={[s.searchInput, { marginBottom: 6 }]}
        placeholder={smartDefaultTitle}
        value={customTitle}
        onChangeText={setCustomTitle}
        placeholderTextColor={COLORS.textMuted}
      />
      <Text style={[s.hintText, { marginBottom: 12 }]}>
        Leave blank to use: <Text style={{ fontWeight: '600' }}>{smartDefaultTitle}</Text>
      </Text>

      {/* Timing — Deadline + Impact horizon. Captured here so the very first
          PRR decision record carries a deadline that downstream Action Center
          handoffs and reminders can inherit. */}
      <View style={{ marginBottom: 14 }}>
        <TimingFieldset value={timing} onChange={setTiming} />
      </View>

      {/* Create from scratch button — always visible */}
      <TouchableOpacity
        style={s.scratchCard}
        onPress={() => handleCreateDecision(undefined, 'CUSTOM_BLANK')}
        disabled={creating}
      >
        <View style={s.scratchIconBox}>
          <Ionicons name="create" size={24} color={COLORS.primary} />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={s.scratchTitle}>Create from scratch</Text>
          <Text style={s.scratchDesc}>Start a blank decision with your own factors</Text>
        </View>
        <Ionicons name="arrow-forward" size={20} color={COLORS.primary} />
      </TouchableOpacity>

      {/* Template list */}
      {loadingTemplates ? (
        <ActivityIndicator style={{ marginTop: 20 }} />
      ) : (
        <FlatList
          data={templates}
          keyExtractor={item => item.id}
          renderItem={({ item }) => {
            // Compute SWOT-flag counts (only meaningful when module=swot).
            const flagCounts: Record<'S' | 'W' | 'O' | 'T', number> = { S: 0, W: 0, O: 0, T: 0 };
            if (moduleKey === 'swot' && Array.isArray(item.factors)) {
              for (const f of item.factors) {
                const fl = (f?.swot_flag || '').toString().toUpperCase();
                if (fl === 'S' || fl === 'W' || fl === 'O' || fl === 'T') {
                  flagCounts[fl as 'S' | 'W' | 'O' | 'T'] += 1;
                }
              }
            }
            const totalFlags = flagCounts.S + flagCounts.W + flagCounts.O + flagCounts.T;
            return (
            <TouchableOpacity
              style={s.templateCard}
              onPress={() => handleCreateDecision(item.id, item.template_type)}
              disabled={creating}
            >
              <View style={s.templateHeader}>
                <View style={{ flex: 1 }}>
                  <Text style={s.templateTitle}>{item.title}</Text>
                  <Text style={s.templateDesc} numberOfLines={2}>{item.description}</Text>
                </View>
              </View>
              {/* SWOT flag preview — only render in SWOT module and only if any
                  flagged factor exists. Gives the user a quick glance at how
                  many S/W/O/T factors a template will seed. */}
              {moduleKey === 'swot' && totalFlags > 0 && (
                <View style={{ flexDirection: 'row', gap: 4, marginBottom: 8, flexWrap: 'wrap' }}>
                  {(['S', 'W', 'O', 'T'] as const).map(k => {
                    if (flagCounts[k] === 0) return null;
                    const m = SWOT_FLAG_META[k];
                    return (
                      <View
                        key={k}
                        style={{
                          flexDirection: 'row', alignItems: 'center', gap: 3,
                          paddingHorizontal: 7, paddingVertical: 3, borderRadius: 10,
                          backgroundColor: m.bg, borderWidth: 1, borderColor: m.color + '40',
                        }}
                      >
                        <Text style={{ fontSize: 10, fontWeight: '800', color: m.color }}>{m.label}</Text>
                        <Text style={{ fontSize: 10, color: m.color, fontWeight: '600' }}>{flagCounts[k]}</Text>
                      </View>
                    );
                  })}
                </View>
              )}
              <View style={s.templateFooter}>
                {TEMPLATE_TYPE_CONFIG[item.template_type] && (
                  <View style={[s.typeBadge, { backgroundColor: TEMPLATE_TYPE_CONFIG[item.template_type].color + '15' }]}>
                    <Ionicons name={TEMPLATE_TYPE_CONFIG[item.template_type].icon as any} size={12} color={TEMPLATE_TYPE_CONFIG[item.template_type].color} />
                    <Text style={[s.typeBadgeText, { color: TEMPLATE_TYPE_CONFIG[item.template_type].color }]}>
                      {TEMPLATE_TYPE_CONFIG[item.template_type].label}
                    </Text>
                  </View>
                )}
                {(item.tags || []).slice(0, 3).map((tag, i) => (
                  <View key={i} style={s.tagChip}>
                    <Text style={s.tagText}>{tag}</Text>
                  </View>
                ))}
              </View>
            </TouchableOpacity>
          );
          }}
          ListEmptyComponent={
            !loadingTemplates ? (
              <View style={s.emptyTemplates}>
                <Ionicons name="documents-outline" size={40} color={COLORS.textMuted} />
                <Text style={s.emptyText}>No templates match your search</Text>
                <Text style={s.emptyHint}>Try different keywords or create from scratch</Text>
              </View>
            ) : null
          }
          style={{ maxHeight: 400 }}
          showsVerticalScrollIndicator={false}
        />
      )}
    </View>
  );

  // ====== MAIN RENDER ======
  return (
    <SafeAreaView style={s.container} edges={['top']}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        {/* Header */}
        <LinearGradient colors={moduleCfg.gradient} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={s.header}>
          <TouchableOpacity onPress={() => safeBack(router)} style={s.backBtn}>
            <Ionicons name="arrow-back" size={22} color="#FFF" />
          </TouchableOpacity>
          <View style={{ flex: 1, alignItems: 'center' }}>
            <Text style={s.headerTitle}>{moduleCfg.title}</Text>
            <Text style={s.headerSubtitle}>{moduleCfg.subtitle}</Text>
          </View>
          <TouchableOpacity onPress={() => goHome(router)} style={s.backBtn} accessibilityLabel="Home">
            <Ionicons name="home" size={20} color="#FFF" />
          </TouchableOpacity>
        </LinearGradient>

        {/* Step indicator */}
        {renderStepIndicator()}

        {/* Content */}
        <ScrollView style={s.content} contentContainerStyle={s.contentInner} showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
          {seeding ? (
            <View style={{ alignItems: 'center', paddingVertical: 40 }}>
              <ActivityIndicator size="large" />
              <Text style={s.seedingText}>Initializing decision catalog...</Text>
            </View>
          ) : (
            <>
              {step === 0 && renderStep1()}
              {step === 1 && renderStep0()}
              {step === 2 && renderStep2()}
              {step === 3 && renderStep3()}
              {step === 4 && moduleCfg.hasTemplatesStep && renderStep4()}
            </>
          )}
        </ScrollView>

        {/* Navigation buttons.
            - For modules WITH templates: nav visible on steps 0-3; templates step (4) has its own actions.
            - For Pros & Cons (no templates step): nav visible on steps 0-3 and step 3 button reads "Create & Start Wizard" → createProsConsAnalysis(). */}
        {!seeding && (step < 4 || (step === 4 && moduleCfg.hasTemplatesStep)) && (
          <View style={s.navRow}>
            {step > 0 && (
              <TouchableOpacity style={s.navBtnBack} onPress={prevStep}>
                <Ionicons name="arrow-back" size={18} color={COLORS.textSecondary} />
                <Text style={s.navBtnBackText}>Back</Text>
              </TouchableOpacity>
            )}
            {step < 4 && (
              <TouchableOpacity
                style={[s.navBtnNext, !canProceed() && s.navBtnDisabled]}
                onPress={() => {
                  if (step === 3 && !moduleCfg.hasTemplatesStep) {
                    createProsConsAnalysis();
                  } else {
                    nextStep();
                  }
                }}
                disabled={!canProceed() || creating}
              >
                <Text style={s.navBtnNextText}>
                  {step === 3 ? moduleCfg.finalButtonLabel : 'Next'}
                </Text>
                <Ionicons
                  name={step === 3 && !moduleCfg.hasTemplatesStep ? 'checkmark' : 'arrow-forward'}
                  size={18} color="#FFF"
                />
              </TouchableOpacity>
            )}
          </View>
        )}

        {/* Creating overlay */}
        {creating && (
          <View style={s.overlay}>
            <ActivityIndicator size="large" color={COLORS.primary} />
            <Text style={s.overlayText}>Creating your decision...</Text>
          </View>
        )}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.background },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 16, paddingVertical: 16, paddingTop: 8,
  },
  backBtn: { width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.2)', justifyContent: 'center', alignItems: 'center' },
  headerTitle: { fontSize: 20, fontWeight: '700', color: '#FFF', textAlign: 'center' },
  headerSubtitle: { fontSize: 12, color: 'rgba(255,255,255,0.8)', textAlign: 'center', marginTop: 2 },

  // Step indicator
  stepRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 16, paddingHorizontal: 24 },
  stepItem: { flexDirection: 'row', alignItems: 'center' },
  stepDot: {
    width: 26, height: 26, borderRadius: 13, backgroundColor: COLORS.border,
    justifyContent: 'center', alignItems: 'center',
  },
  stepDotActive: { backgroundColor: COLORS.primary + '30', borderWidth: 2, borderColor: COLORS.primary },
  stepDotDone: { backgroundColor: COLORS.primary, borderWidth: 0 },
  stepDotText: { fontSize: 11, fontWeight: '600', color: COLORS.textMuted },
  stepDotTextActive: { color: COLORS.primary },
  stepLine: { width: 24, height: 2, backgroundColor: COLORS.border, marginHorizontal: 2 },
  stepLineActive: { backgroundColor: COLORS.primary },

  content: { flex: 1 },
  contentInner: { padding: 20, paddingBottom: 40 },

  // Step titles
  stepTitle: { fontSize: 22, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 4 },
  stepSubtitle: { fontSize: 14, color: COLORS.textSecondary, marginBottom: 20, lineHeight: 20 },

  // Step 0: Context cards
  contextCards: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  contextCard: {
    width: '48%' as any, flexDirection: 'column', alignItems: 'center', backgroundColor: COLORS.white,
    borderRadius: 14, padding: 14, borderWidth: 2, borderColor: COLORS.border, gap: 8,
    minHeight: 130,
  },
  contextIcon: { width: 44, height: 44, borderRadius: 12, justifyContent: 'center', alignItems: 'center' },
  contextLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textPrimary, textAlign: 'center' },
  contextDesc: { fontSize: 11, color: COLORS.textMuted, textAlign: 'center', marginTop: 2 },
  checkCircle: {
    position: 'absolute', top: 12, right: 12, width: 24, height: 24, borderRadius: 12,
    justifyContent: 'center', alignItems: 'center',
  },

  // Step 1: Life area grid
  areaGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  areaCard: {
    width: '47%' as any, backgroundColor: COLORS.white, borderRadius: 12, padding: 14,
    borderWidth: 2, borderColor: COLORS.border, alignItems: 'center', gap: 8, minHeight: 90,
  },
  areaName: { fontSize: 12, fontWeight: '500', color: COLORS.textPrimary, textAlign: 'center' },
  areaCheck: {
    position: 'absolute', top: 6, right: 6, width: 18, height: 18, borderRadius: 9,
    justifyContent: 'center', alignItems: 'center',
  },

  // Step 2: Ask type
  askTypeCards: { gap: 12 },
  askTypeCard: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.white,
    borderRadius: 14, padding: 16, borderWidth: 2, borderColor: COLORS.border, gap: 14,
  },
  askTypeIcon: { width: 50, height: 50, borderRadius: 14, justifyContent: 'center', alignItems: 'center' },
  askTypeInfo: { flex: 1 },
  askTypeHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  askTypeName: { fontSize: 17, fontWeight: '600', color: COLORS.textPrimary },
  priorityBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6 },
  priorityText: { fontSize: 11, fontWeight: '700' },
  askTypeDesc: { fontSize: 13, color: COLORS.textSecondary, marginTop: 4 },

  // Step 3: Search
  searchInput: {
    backgroundColor: COLORS.white, borderRadius: 12, borderWidth: 1, borderColor: COLORS.border,
    paddingHorizontal: 16, paddingVertical: 14, fontSize: 16, color: COLORS.textPrimary,
  },
  chipSectionLabel: { fontSize: 13, fontWeight: '600', color: COLORS.textSecondary, marginBottom: 8 },
  chipScroll: { gap: 8, paddingVertical: 4 },
  chipWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, paddingVertical: 4 },
  subAreaChip: {
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20,
    backgroundColor: COLORS.primary + '10', borderWidth: 1, borderColor: COLORS.primary + '30',
    maxWidth: 280,
  },
  subAreaChipText: { fontSize: 13, color: COLORS.primary, fontWeight: '500' },
  hintText: { fontSize: 12, color: COLORS.textMuted, marginTop: 8, fontStyle: 'italic' },

  // Step-4 structured form labels
  fieldLabel: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 8 },
  fieldOpt: { fontSize: 12, fontWeight: '400', color: COLORS.textMuted },
  aiHint: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    marginTop: 6, paddingHorizontal: 4,
  },
  aiHintText: { fontSize: 12, color: '#7C3AED', fontStyle: 'italic' },

  // Step 4: Templates
  scratchCard: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.primary + '08',
    borderRadius: 14, padding: 16, borderWidth: 1.5, borderColor: COLORS.primary + '30',
    borderStyle: 'dashed', gap: 12, marginBottom: 16,
  },
  scratchIconBox: {
    width: 44, height: 44, borderRadius: 12, backgroundColor: COLORS.primary + '15',
    justifyContent: 'center', alignItems: 'center',
  },
  scratchTitle: { fontSize: 15, fontWeight: '700', color: COLORS.primary },
  scratchDesc: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },

  templateCard: {
    backgroundColor: COLORS.white, borderRadius: 12, padding: 16, marginBottom: 10,
    borderWidth: 1, borderColor: COLORS.border,
    shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.04, shadowRadius: 3, elevation: 1,
  },
  templateHeader: { flexDirection: 'row', gap: 12, marginBottom: 10 },
  templateTitle: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 4 },
  templateDesc: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 18 },
  templateFooter: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, alignItems: 'center' },
  typeBadge: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6,
  },
  typeBadgeText: { fontSize: 11, fontWeight: '600' },
  tagChip: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, backgroundColor: COLORS.background },
  tagText: { fontSize: 10, color: COLORS.textMuted },

  emptyTemplates: { alignItems: 'center', paddingVertical: 30 },
  emptyText: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary, marginTop: 12 },
  emptyHint: { fontSize: 13, color: COLORS.textMuted, marginTop: 4 },

  // Nav buttons
  navRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    padding: 16, borderTopWidth: 1, borderTopColor: COLORS.border, backgroundColor: COLORS.white,
  },
  navBtnBack: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingVertical: 12, paddingHorizontal: 16, borderRadius: 12,
    backgroundColor: COLORS.background, borderWidth: 1, borderColor: COLORS.border,
  },
  navBtnBackText: { fontSize: 15, color: COLORS.textSecondary, fontWeight: '500' },
  navBtnNext: {
    flexDirection: 'row', alignItems: 'center', gap: 6, marginLeft: 'auto',
    paddingVertical: 12, paddingHorizontal: 24, borderRadius: 12,
    backgroundColor: COLORS.primary,
  },
  navBtnDisabled: { opacity: 0.4 },
  navBtnNextText: { fontSize: 15, color: '#FFF', fontWeight: '700' },

  // Overlay
  overlay: {
    ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(255,255,255,0.85)',
    justifyContent: 'center', alignItems: 'center', zIndex: 100,
  },
  overlayText: { fontSize: 16, fontWeight: '600', color: COLORS.textPrimary, marginTop: 12 },

  seedingText: { fontSize: 14, color: COLORS.textSecondary, marginTop: 12 },
});
