import React, { createContext, useContext, useState, useEffect } from 'react';
import { Alert } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../utils/api';
import type { Factor, OptionAssessment, DecisionOption, MPPSImprovement, Decision, BestOptionSuggestion } from '../types/decision';
import { calculateRatingsFromOrder } from '../utils/decisionHelpers';
import { StepVoiceCommand } from '../utils/stepVoiceParser';

interface DecisionContextType {
  decision: Decision;
  loading: boolean;
  saving: boolean;
  currentStep: number;
  setCurrentStep: (step: number) => void;
  isCompleted: boolean;
  saveDecision: (updates: Partial<Decision>) => Promise<void>;
  fetchDecision: () => Promise<void>;

  // Factor operations
  addFactor: () => void;
  addFactorsFromTemplate: (templateFactors: any[]) => number;
  updateFactor: (factorId: string, updates: Partial<Factor>) => void;
  removeFactor: (factorId: string) => void;
  moveFactorUp: (factorId: string) => void;
  moveFactorDown: (factorId: string) => void;
  applyRatingsAndContinue: () => void;
  newFactorName: string;
  setNewFactorName: (name: string) => void;

  // Option operations
  addOption: () => void;
  addOptionByName: (name: string) => void;
  addOptionFromStore: (name: string, solutionId: string) => void;
  prefillBestOptions: (suggestions: BestOptionSuggestion[]) => number;
  removeOption: (optionId: string) => void;
  newOptionName: string;
  setNewOptionName: (name: string) => void;

  // Assessment operations
  updateAssessment: (optionId: string, factorId: string, percentage: number, mode?: 'L' | 'M' | 'H' | 'custom', unitValue?: string, actualValue?: number) => void;
  getAssessmentValue: (optionId: string, factorId: string) => number | null;
  getAssessmentMode: (optionId: string, factorId: string) => 'L' | 'M' | 'H' | 'custom' | undefined;
  getUnitValue: (optionId: string, factorId: string) => string;
  getActualValue: (optionId: string, factorId: string) => number | undefined;
  getAssessmentKey: (optionId: string, factorId: string) => string;
  selectOption: (optionId: string, caseType: string) => void;
  calculateDynamicWorth: (option: DecisionOption) => { worth: number; assessedCount: number; totalCount: number };
  calculateAutoPercentage: (factor: Factor, actualValue: number | string | undefined) => number | null;

  // UI state
  showCustomInput: { [key: string]: boolean };
  setShowCustomInput: React.Dispatch<React.SetStateAction<{ [key: string]: boolean }>>;
  unitValues: { [key: string]: string };
  setUnitValues: React.Dispatch<React.SetStateAction<{ [key: string]: string }>>;
  customInputValues: { [key: string]: string };
  setCustomInputValues: React.Dispatch<React.SetStateAction<{ [key: string]: string }>>;
  actualValues: { [key: string]: string };
  setActualValues: React.Dispatch<React.SetStateAction<{ [key: string]: string }>>;
  customUnitInput: { [key: string]: string };
  setCustomUnitInput: React.Dispatch<React.SetStateAction<{ [key: string]: string }>>;
  showUnitPicker: { [key: string]: boolean };
  setShowUnitPicker: React.Dispatch<React.SetStateAction<{ [key: string]: boolean }>>;
  expectedInputs: { [key: string]: string };
  setExpectedInputs: React.Dispatch<React.SetStateAction<{ [key: string]: string }>>;
  newSubFactorName: { [key: string]: string };
  setNewSubFactorName: React.Dispatch<React.SetStateAction<{ [key: string]: string }>>;
  expandedGroups: { [key: string]: boolean };
  setExpandedGroups: React.Dispatch<React.SetStateAction<{ [key: string]: boolean }>>;
  subWeightInputs: { [key: string]: string };
  setSubWeightInputs: React.Dispatch<React.SetStateAction<{ [key: string]: string }>>;

  // Share modal
  shareModalVisible: boolean;
  setShareModalVisible: (visible: boolean) => void;

  // Voice
  handleUniversalVoiceCommand: (command: StepVoiceCommand) => void;

  // Router
  router: ReturnType<typeof useRouter>;
  id: string;
}

const DecisionContext = createContext<DecisionContextType | null>(null);

export const useDecision = (): DecisionContextType => {
  const ctx = useContext(DecisionContext);
  if (!ctx) throw new Error('useDecision must be used within DecisionProvider');
  return ctx;
};

export const DecisionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const params = useLocalSearchParams<{ id?: string | string[]; step?: string | string[] }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  // Single-shot guard so the ?step=N override is consumed only on the
  // first fetchDecision() call (not on subsequent refreshes triggered by
  // save / reload). Once true, the smart auto-jump takes over.
  const overrideConsumedRef = React.useRef(false);
  // Alias so fetchDecision() can read the latest step value without
  // re-creating the function on every render. (Closures pick this up.)
  const searchParams = params as { step?: string | string[] };
  const router = useRouter();
  const [decision, setDecision] = useState<Decision | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [currentStep, setCurrentStep] = useState(2);

  // Form states
  const [newFactorName, setNewFactorName] = useState('');
  const [newOptionName, setNewOptionName] = useState('');

  // LMH Assessment states
  const [showCustomInput, setShowCustomInput] = useState<{ [key: string]: boolean }>({});
  const [shareModalVisible, setShareModalVisible] = useState(false);
  const [unitValues, setUnitValues] = useState<{ [key: string]: string }>({});
  const [customInputValues, setCustomInputValues] = useState<{ [key: string]: string }>({});
  const [actualValues, setActualValues] = useState<{ [key: string]: string }>({});
  const [customUnitInput, setCustomUnitInput] = useState<{ [key: string]: string }>({});
  const [showUnitPicker, setShowUnitPicker] = useState<{ [key: string]: boolean }>({});
  const [expectedInputs, setExpectedInputs] = useState<{ [key: string]: string }>({});
  const [newSubFactorName, setNewSubFactorName] = useState<{ [key: string]: string }>({});
  const [expandedGroups, setExpandedGroups] = useState<{ [key: string]: boolean }>({});
  const [subWeightInputs, setSubWeightInputs] = useState<{ [key: string]: string }>({});

  useEffect(() => {
    fetchDecision();
  }, [id]);

  const fetchDecision = async () => {
    try {
      const response = await api.get(`/decisions/${id}`);
      setDecision(response.data);

      // ── ?step=N URL override (SWOT->Decider conversion uses this to
      // force-land on Step 2 even when the doc already has factors).
      // Consume the param ONCE on first load — clear it from the ref so
      // subsequent fetchDecision() calls (e.g. refresh after save) fall
      // back to the smart auto-jump below.
      const stepOverrideRaw = searchParams?.step;
      const stepOverride = stepOverrideRaw
        ? parseInt(String(Array.isArray(stepOverrideRaw) ? stepOverrideRaw[0] : stepOverrideRaw), 10)
        : NaN;
      if (
        !overrideConsumedRef.current &&
        !Number.isNaN(stepOverride) &&
        stepOverride >= 2 &&
        stepOverride <= 10
      ) {
        overrideConsumedRef.current = true;
        setCurrentStep(stepOverride);
        return; // skip the smart auto-jump below — user asked for a specific step
      }

      // SWOT-converted Deciders ALWAYS land on Step 2 (Define Factors &
      // Criteria) — that's the only place users can rename the AI-prefilled
      // factor names (pencil icon). Without this guard, the smart auto-jump
      // below would push them forward to Step 5 (because factors already
      // have category="primary") and they'd never see the rename pencil.
      const isSwotSourced = (response.data as any).source_module === 'swot'
        || (response.data as any).allow_single_option === true;
      if (!overrideConsumedRef.current && isSwotSourced) {
        overrideConsumedRef.current = true;
        setCurrentStep(2);
        return;
      }

      // Smart auto-jump to the furthest meaningful step based on data present.
      if (response.data.status === 'completed') {
        setCurrentStep(10);
      } else if (response.data.chosen_option_id) {
        setCurrentStep(8);
      } else if (response.data.options.length > 0 && response.data.options[0].assessments?.length > 0) {
        setCurrentStep(7);
      } else if (response.data.options.length > 0) {
        setCurrentStep(6);
      } else if (response.data.factors.length > 0 && response.data.factors.some((f: Factor) => f.category === 'primary')) {
        setCurrentStep(5);
      } else if (response.data.factors.length > 0) {
        setCurrentStep(3);
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to load decision');
      router.back();
    } finally {
      setLoading(false);
    }
  };

  const saveDecision = async (updates: Partial<Decision>) => {
    setSaving(true);
    try {
      await api.put(`/decisions/${id}`, updates);
      setDecision({ ...decision!, ...updates });
    } catch (error) {
      Alert.alert('Error', 'Failed to save changes');
    } finally {
      setSaving(false);
    }
  };

  const addFactor = () => {
    if (!newFactorName.trim()) return;
    const newFactor: Factor = {
      id: `factor_${Date.now()}`,
      name: newFactorName.trim(),
      category: 'secondary',
      rating: 50,
      order: decision!.factors.length,
    };
    const updatedFactors = [...decision!.factors, newFactor];
    saveDecision({ factors: updatedFactors });
    setNewFactorName('');
  };

  const addFactorsFromTemplate = (templateFactors: any[]) => {
    const existingNames = new Set(decision!.factors.map(f => f.name.toLowerCase()));
    const newFactors: Factor[] = [];
    let orderStart = decision!.factors.length;

    for (const tf of templateFactors) {
      const name = (tf.name || '').trim();
      if (!name || existingNames.has(name.toLowerCase())) continue;
      existingNames.add(name.toLowerCase());

      const priority = tf.priority || 5;
      newFactors.push({
        id: `factor_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
        name,
        category: priority >= 7 ? 'primary' : 'secondary',
        rating: Math.min(priority * 10, 100),
        order: orderStart++,
        expected_value: tf.expected_value_pct ?? undefined,
        factor_type: tf.factor_type === 'quantitative' ? 'quantitative' : 'qualitative',
        data_type: tf.factor_type === 'quantitative' ? 'numeric' : 'text',
      });
    }

    if (newFactors.length > 0) {
      const updatedFactors = [...decision!.factors, ...newFactors];
      saveDecision({ factors: updatedFactors });
    }
    return newFactors.length;
  };

  const updateFactor = (factorId: string, updates: Partial<Factor>) => {
    const updatedFactors = decision!.factors.map((f) =>
      f.id === factorId ? { ...f, ...updates } : f
    );
    saveDecision({ factors: updatedFactors });
  };

  const removeFactor = (factorId: string) => {
    const updatedFactors = decision!.factors.filter((f) => f.id !== factorId && f.parent_id !== factorId);
    saveDecision({ factors: updatedFactors });
  };

  const moveFactorUp = (factorId: string) => {
    const factor = decision!.factors.find(f => f.id === factorId);
    if (!factor || factor.parent_id) return;
    const sameCategory = decision!.factors
      .filter(f => f.category === factor.category && !f.parent_id)
      .sort((a, b) => a.order - b.order);
    const currentIndex = sameCategory.findIndex(f => f.id === factorId);
    if (currentIndex <= 0) return;
    const updatedFactors = decision!.factors.map(f => {
      if (f.id === factorId) return { ...f, order: sameCategory[currentIndex - 1].order };
      if (f.id === sameCategory[currentIndex - 1].id) return { ...f, order: factor.order };
      return f;
    });
    const factorsWithRatings = calculateRatingsFromOrder(updatedFactors, decision!.rating_gap_multiplier || 1.0);
    saveDecision({ factors: factorsWithRatings });
  };

  const moveFactorDown = (factorId: string) => {
    const factor = decision!.factors.find(f => f.id === factorId);
    if (!factor || factor.parent_id) return;
    const sameCategory = decision!.factors
      .filter(f => f.category === factor.category && !f.parent_id)
      .sort((a, b) => a.order - b.order);
    const currentIndex = sameCategory.findIndex(f => f.id === factorId);
    if (currentIndex >= sameCategory.length - 1) return;
    const updatedFactors = decision!.factors.map(f => {
      if (f.id === factorId) return { ...f, order: sameCategory[currentIndex + 1].order };
      if (f.id === sameCategory[currentIndex + 1].id) return { ...f, order: factor.order };
      return f;
    });
    const factorsWithRatings = calculateRatingsFromOrder(updatedFactors, decision!.rating_gap_multiplier || 1.0);
    saveDecision({ factors: factorsWithRatings });
  };

  const applyRatingsAndContinue = () => {
    const factorsWithRatings = calculateRatingsFromOrder(decision!.factors, decision!.rating_gap_multiplier || 1.0);
    saveDecision({ factors: factorsWithRatings });
    setCurrentStep(6);
  };

  const addOption = () => {
    if (!newOptionName.trim()) return;
    const newOption: DecisionOption = {
      id: `option_${Date.now()}`,
      name: newOptionName.trim(),
      assessments: [],
      worth_percentage: 0,
    };
    const updatedOptions = [...decision!.options, newOption];
    saveDecision({ options: updatedOptions });
    setNewOptionName('');
  };

  const addOptionByName = (name: string) => {
    if (!name.trim()) return;
    const exists = decision!.options.some(o => o.name.toLowerCase() === name.trim().toLowerCase());
    if (exists) return;
    const newOption: DecisionOption = {
      id: `option_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      name: name.trim(),
      assessments: [],
      worth_percentage: 0,
    };
    const updatedOptions = [...decision!.options, newOption];
    saveDecision({ options: updatedOptions });
  };

  const addOptionFromStore = (name: string, solutionId: string) => {
    // Check if this solution is already added
    const exists = decision!.options.some(o => o.solution_id === solutionId);
    if (exists) return;
    const newOption: DecisionOption = {
      id: `option_${Date.now()}`,
      name: name.trim(),
      assessments: [],
      worth_percentage: 0,
      solution_id: solutionId,
    };
    const updatedOptions = [...decision!.options, newOption];
    saveDecision({ options: updatedOptions });
  };

  // Prefill multiple AI/Store suggestions in one shot (Find My Best Options).
  // De-dupes against existing options by lowercased name and by solution_id,
  // appends provenance metadata, builds per-factor assessments from the supplied
  // actual values (Store data or AI estimates) — running each through the
  // automated scoring engine (calculateAutoPercentage) — and computes worth %,
  // then persists with a single save.
  const prefillBestOptions = (suggestions: BestOptionSuggestion[]): number => {
    if (!decision || !Array.isArray(suggestions) || suggestions.length === 0) return 0;
    const existing = decision.options || [];
    const factors = decision.factors || [];
    const nameSeen = new Set(existing.map(o => (o.name || '').trim().toLowerCase()));
    const solSeen = new Set(existing.map(o => o.solution_id).filter(Boolean) as string[]);
    const additions: DecisionOption[] = [];
    suggestions.forEach((s, i) => {
      const name = (s.name || '').trim();
      if (!name) return;
      const key = name.toLowerCase();
      if (nameSeen.has(key)) return;
      if (s.solution_id && solSeen.has(s.solution_id)) return;
      nameSeen.add(key);
      if (s.solution_id) solSeen.add(s.solution_id);

      // Build assessments: actual value -> auto % via the proportionality engine.
      const assessments: OptionAssessment[] = [];
      (s.factor_values || []).forEach((fv) => {
        const factor = factors.find(f => f.id === fv.factor_id);
        if (!factor || fv.value === undefined || fv.value === null || fv.value === '') return;
        const isText = (factor.data_type || 'numeric') === 'text';
        const numericActual = typeof fv.value === 'number'
          ? fv.value
          : (!isText ? parseFloat(String(fv.value)) : NaN);
        const pct = calculateAutoPercentage(factor, fv.value);
        const unitStr = factor.unit ? ` ${factor.unit}` : '';
        const display = isText
          ? String(fv.value)
          : `${fv.value}${unitStr}`;
        assessments.push({
          factor_id: fv.factor_id,
          percentage: pct !== null ? pct : undefined,
          actual_value: !isText && !isNaN(numericActual) ? numericActual : undefined,
          unit_value: display,
          assessment_mode: 'auto',
        } as OptionAssessment);
      });

      const baseOption: DecisionOption = {
        id: `option_${Date.now()}_${i}_${Math.random().toString(36).slice(2, 6)}`,
        name,
        assessments,
        worth_percentage: 0,
        source: s.source || 'ai',
        ai_rationale: s.ai_rationale || undefined,
        ...(s.solution_id ? { solution_id: s.solution_id } : {}),
        ...(s.price_range ? { price_range: s.price_range } : {}),
        ...(typeof s.rating === 'number' ? { rating: s.rating } : {}),
      };
      baseOption.worth_percentage = calcDynamicWorth(baseOption).worth;
      additions.push(baseOption);
    });
    if (additions.length === 0) return 0;
    saveDecision({ options: [...existing, ...additions] });
    return additions.length;
  };

  const removeOption = (optionId: string) => {
    const updatedOptions = decision!.options.filter((o) => o.id !== optionId);
    saveDecision({ options: updatedOptions });
  };

  const updateAssessment = (optionId: string, factorId: string, percentage: number, mode?: 'L' | 'M' | 'H' | 'custom', unitValue?: string, actualValue?: number) => {
    const clampedPercentage = percentage !== null && percentage !== undefined
      ? Math.min(100, Math.max(0, percentage))
      : percentage;
    const updatedOptions = decision!.options.map((option) => {
      if (option.id !== optionId) return option;
      const existingIndex = option.assessments.findIndex((a) => a.factor_id === factorId);
      const newAssessment: OptionAssessment = {
        factor_id: factorId,
        percentage: clampedPercentage,
        assessment_mode: mode,
        unit_value: unitValue,
        actual_value: actualValue,
      };
      let newAssessments;
      if (existingIndex >= 0) {
        newAssessments = option.assessments.map((a, i) =>
          i === existingIndex ? { ...a, ...newAssessment } : a
        );
      } else {
        newAssessments = [...option.assessments, newAssessment];
      }
      return { ...option, assessments: newAssessments };
    });
    saveDecision({ options: updatedOptions, factors: decision!.factors });
  };

  const getAssessmentMode = (optionId: string, factorId: string): 'L' | 'M' | 'H' | 'custom' | undefined => {
    const option = decision?.options.find((o) => o.id === optionId);
    const assessment = option?.assessments.find((a) => a.factor_id === factorId);
    return assessment?.assessment_mode;
  };

  const getUnitValue = (optionId: string, factorId: string): string => {
    const option = decision?.options.find((o) => o.id === optionId);
    const assessment = option?.assessments.find((a) => a.factor_id === factorId);
    return assessment?.unit_value || '';
  };

  const getActualValue = (optionId: string, factorId: string): number | undefined => {
    const option = decision?.options.find((o) => o.id === optionId);
    const assessment = option?.assessments.find((a) => a.factor_id === factorId);
    return assessment?.actual_value;
  };

  const selectOption = (optionId: string, caseType: string) => {
    saveDecision({ chosen_option_id: optionId, decision_case: caseType, status: 'completed' });
    setCurrentStep(10);
  };

  const getAssessmentKey = (optionId: string, factorId: string) => `${optionId}_${factorId}`;

  const getAssessmentValue = (optionId: string, factorId: string): number | null => {
    const option = decision?.options.find((o) => o.id === optionId);
    const assessment = option?.assessments.find((a) => a.factor_id === factorId);
    return assessment?.percentage ?? null;
  };

  const calcDynamicWorth = (option: DecisionOption): { worth: number; assessedCount: number; totalCount: number } => {
    const { calculateDynamicWorth: calcWorth } = require('../utils/decisionHelpers');
    return calcWorth(option, decision?.factors || []);
  };

  const calculateAutoPercentage = (factor: Factor, actualValue: number | string | undefined): number | null => {
    if (actualValue === undefined || actualValue === null || actualValue === '') return null;
    if (factor.expected_value === undefined || factor.expected_value === null) return null;
    if (!factor.operator) return null;
    const dataType = factor.data_type || 'numeric';
    if (dataType === 'numeric') {
      const expected = typeof factor.expected_value === 'number' ? factor.expected_value : parseFloat(String(factor.expected_value));
      const actual = typeof actualValue === 'number' ? actualValue : parseFloat(String(actualValue));
      if (isNaN(expected) || isNaN(actual)) return null;
      if (expected === 0) return actual === 0 ? 100 : 0;
      switch (factor.operator) {
        case '>=': case '>':
          if (factor.operator === '>=' ? actual >= expected : actual > expected) return 100;
          return Math.max(0, Math.round((actual / expected) * 100));
        case '<=': case '<':
          if (factor.operator === '<=' ? actual <= expected : actual < expected) return 100;
          return actual === 0 ? 100 : Math.max(0, Math.round((expected / actual) * 100));
        case '=':
          const deviation = Math.abs(actual - expected) / Math.abs(expected);
          return Math.max(0, Math.round((1 - deviation) * 100));
        case '!=': return actual !== expected ? 100 : 0;
        default: return null;
      }
    } else {
      const expected = String(factor.expected_value).toLowerCase().trim();
      const actual = String(actualValue).toLowerCase().trim();
      if (!expected || !actual) return null;
      switch (factor.operator) {
        case 'contains': return actual.includes(expected) ? 100 : 0;
        case 'starts_with': return actual.startsWith(expected) ? 100 : 0;
        case 'ends_with': return actual.endsWith(expected) ? 100 : 0;
        case 'equals': return actual === expected ? 100 : 0;
        case 'not_equals': return actual !== expected ? 100 : 0;
        default: return null;
      }
    }
  };

  // Voice command handler
  const handleAssessVoiceCommand = (command: StepVoiceCommand) => {
    if (!decision) return;
    let updatedOptions = [...decision.options.map(o => ({ ...o, assessments: [...o.assessments] }))];
    const applyToFactor = (optionIdx: number, factorId: string) => {
      const option = updatedOptions[optionIdx];
      const key = getAssessmentKey(option.id, factorId);
      const clampedPercentage = Math.min(100, Math.max(0, command.value || 0));
      const existingIndex = option.assessments.findIndex((a) => a.factor_id === factorId);
      const newAssessment: OptionAssessment = { factor_id: factorId, percentage: clampedPercentage, assessment_mode: command.mode || 'custom', unit_value: unitValues[key] };
      if (existingIndex >= 0) {
        option.assessments = option.assessments.map((a, i) => i === existingIndex ? { ...a, ...newAssessment } : a);
      } else {
        option.assessments = [...option.assessments, newAssessment];
      }
      if (command.mode !== 'custom') {
        setShowCustomInput((prev: any) => ({ ...prev, [key]: false }));
      } else {
        setShowCustomInput((prev: any) => ({ ...prev, [key]: true }));
        setCustomInputValues((prev: any) => ({ ...prev, [key]: String(command.value) }));
      }
    };
    if (command.allFactors) {
      updatedOptions.forEach((_, optionIdx) => { decision.factors.forEach(factor => { applyToFactor(optionIdx, factor.id); }); });
    } else if (command.factorId) {
      updatedOptions.forEach((_, optionIdx) => { applyToFactor(optionIdx, command.factorId!); });
    }
    saveDecision({ options: updatedOptions, factors: decision.factors });
  };

  const handleUniversalVoiceCommand = (command: StepVoiceCommand) => {
    if (!decision) return;
    switch (command.type) {
      case 'set_title': if (command.text) saveDecision({ title: command.text }); break;
      case 'set_context': case 'dictation':
        if (command.step === 1 && command.text) saveDecision({ context: (decision.context || '') + ' ' + command.text });
        else if (command.step === 9 && command.text) saveDecision({ reflection: (decision.reflection || '') + ' ' + command.text });
        else if (command.step === 10 && command.text) saveDecision({ final_notes: (decision.final_notes || '') + ' ' + command.text });
        break;
      case 'add_factor':
        if (command.text) {
          const exists = decision.factors.some(f => f.name.toLowerCase() === command.text!.toLowerCase());
          if (!exists) {
            const nf: Factor = { id: `factor_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`, name: command.text, category: 'secondary', rating: 50, order: decision.factors.length };
            saveDecision({ factors: [...decision.factors, nf] });
          }
        }
        break;
      case 'remove_factor': if (command.factorId) removeFactor(command.factorId); break;
      case 'classify_factor':
        if (command.allFactors && command.category) saveDecision({ factors: decision.factors.map(f => ({ ...f, category: command.category! })) });
        else if (command.factorId && command.category) updateFactor(command.factorId, { category: command.category });
        break;
      case 'move_factor':
        if (command.factorId && command.direction) {
          if (command.direction === 'up') moveFactorUp(command.factorId);
          else if (command.direction === 'down') moveFactorDown(command.factorId);
          else if (command.direction === 'first') {
            const updated = decision.factors.map(f => f.id === command.factorId ? { ...f, order: -1 } : f).sort((a, b) => a.order - b.order).map((f, i) => ({ ...f, order: i }));
            saveDecision({ factors: calculateRatingsFromOrder(updated, decision.rating_gap_multiplier || 1.0) });
          } else if (command.direction === 'last') {
            const updated = decision.factors.map(f => f.id === command.factorId ? { ...f, order: 999 } : f).sort((a, b) => a.order - b.order).map((f, i) => ({ ...f, order: i }));
            saveDecision({ factors: calculateRatingsFromOrder(updated, decision.rating_gap_multiplier || 1.0) });
          }
        }
        break;
      case 'add_option':
        if (command.text) {
          const exists = decision.options.some(o => o.name.toLowerCase() === command.text!.toLowerCase());
          if (!exists) {
            const no: DecisionOption = { id: `option_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`, name: command.text, assessments: [], worth_percentage: 0 };
            saveDecision({ options: [...decision.options, no] });
          }
        }
        break;
      case 'remove_option': if (command.optionId) removeOption(command.optionId); break;
      case 'assess_factor': case 'assess_all': handleAssessVoiceCommand(command); break;
      case 'choose_option': if (command.optionId) saveDecision({ chosen_option_id: command.optionId }); break;
      default: break;
    }
  };

  const isCompleted = decision?.status === 'completed';

  // During loading, provide a minimal context
  const contextValue: DecisionContextType = {
    decision: decision || {
      id: id as string,
      title: '',
      context: '',
      factors: [],
      options: [],
      chosen_option_id: null,
      decision_case: null,
      notes: '',
      rating_gap_multiplier: 1.0,
      status: 'draft',
    },
    loading,
    saving,
    currentStep,
    setCurrentStep,
    isCompleted: isCompleted || false,
    saveDecision,
    fetchDecision,
    addFactor, addFactorsFromTemplate, updateFactor, removeFactor, moveFactorUp, moveFactorDown, applyRatingsAndContinue,
    newFactorName, setNewFactorName,
    addOption, addOptionByName, addOptionFromStore, prefillBestOptions, removeOption,
    newOptionName, setNewOptionName,
    updateAssessment, getAssessmentValue, getAssessmentMode, getUnitValue, getActualValue, getAssessmentKey,
    selectOption,
    calculateDynamicWorth: calcDynamicWorth,
    calculateAutoPercentage,
    showCustomInput, setShowCustomInput,
    unitValues, setUnitValues,
    customInputValues, setCustomInputValues,
    actualValues, setActualValues,
    customUnitInput, setCustomUnitInput,
    showUnitPicker, setShowUnitPicker,
    expectedInputs, setExpectedInputs,
    newSubFactorName, setNewSubFactorName,
    expandedGroups, setExpandedGroups,
    subWeightInputs, setSubWeightInputs,
    shareModalVisible, setShareModalVisible,
    handleUniversalVoiceCommand,
    router,
    id: id as string,
  };

  return (
    <DecisionContext.Provider value={contextValue}>
      {children}
    </DecisionContext.Provider>
  );
};
