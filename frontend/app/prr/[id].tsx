import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../src/constants/colors';
import { Card } from '../../src/components/Card';
import { GradientButton } from '../../src/components/GradientButton';
import VoiceStepInput from '../../src/components/VoiceStepInput';
import { StepVoiceCommand } from '../../src/utils/stepVoiceParser';
import ShareStepModal from '../../src/components/ShareStepModal';
// Voice commands now handled by StepVoiceCommand from stepVoiceParser
import api from '../../src/utils/api';

interface Factor {
  id: string;
  name: string;
  category: 'primary' | 'secondary';
  rating: number;
  order: number;
  unit?: string; // e.g., "USD", "hours", "km", etc.
  expected_value?: string | number; // Benchmark value
  data_type?: 'numeric' | 'text'; // Auto-sensed from expected_value
  operator?: string; // >=, <=, >, <, =, !=, between, contains, starts_with, ends_with, equals, not_equals
  gap_multiplier?: number; // Per-factor gap multiplier (default 1.0)
}

interface OptionAssessment {
  factor_id: string;
  percentage: number;
  unit_value?: string; // Legacy: combined value+unit string
  actual_value?: number; // Separated numeric value
  assessment_mode?: 'L' | 'M' | 'H' | 'custom'; // Quick assessment mode
}

interface DecisionOption {
  id: string;
  name: string;
  assessments: OptionAssessment[];
  worth_percentage: number;
}

interface Decision {
  id: string;
  title: string;
  context: string;
  factors: Factor[];
  options: DecisionOption[];
  chosen_option_id: string | null;
  decision_case: string | null;
  notes: string;
  rating_gap_multiplier: number;
  status: string;
}

// Gap multiplier presets
const GAP_PRESETS = [
  { label: '0.25x', value: 0.25, warn: false },
  { label: '0.5x', value: 0.5, warn: false },
  { label: '0.75x', value: 0.75, warn: false },
  { label: '1x', value: 1.0, warn: false },
  { label: '1.5x', value: 1.5, warn: false },
  { label: '2x', value: 2.0, warn: false },
  { label: '3x', value: 3.0, warn: true },
  { label: '4x', value: 4.0, warn: true },
  { label: '5x', value: 5.0, warn: true },
];

// LMH Assessment constants
const LMH_VALUES = {
  L: { label: 'Low', percentage: 25, color: '#EF4444' },    // Red
  M: { label: 'Medium', percentage: 50, color: '#F59E0B' }, // Yellow/Amber
  H: { label: 'High', percentage: 75, color: '#10B981' },   // Green
};

// Common unit presets for factor measurement
const UNIT_PRESETS = [
  { label: '$', value: 'USD' },
  { label: '€', value: 'EUR' },
  { label: '₹', value: 'INR' },
  { label: '£', value: 'GBP' },
  { label: 'hrs', value: 'hours' },
  { label: 'mins', value: 'minutes' },
  { label: 'days', value: 'days' },
  { label: 'yrs', value: 'years' },
  { label: 'km', value: 'km' },
  { label: 'mi', value: 'miles' },
  { label: '%', value: '%' },
  { label: '#', value: 'count' },
  { label: 'ppl', value: 'people' },
];

// Operator presets by data type
const NUMERIC_OPERATORS = [
  { label: '≥', value: '>=' },
  { label: '≤', value: '<=' },
  { label: '>', value: '>' },
  { label: '<', value: '<' },
  { label: '=', value: '=' },
  { label: '≠', value: '!=' },
];
const TEXT_OPERATORS = [
  { label: 'Contains', value: 'contains' },
  { label: 'Starts with', value: 'starts_with' },
  { label: 'Ends with', value: 'ends_with' },
  { label: 'Equals', value: 'equals' },
  { label: '≠', value: 'not_equals' },
];

// Auto-sense data type from value
const senseDataType = (value: string): 'numeric' | 'text' => {
  if (!value || value.trim() === '') return 'numeric'; // default
  const trimmed = value.trim();
  // Check if it's a valid number (including decimals, negatives)
  return /^-?\d+(\.\d+)?$/.test(trimmed) ? 'numeric' : 'text';
};

// Function to auto-calculate ratings based on order within each category
// Rating starts from 10 for lowest priority (last Secondary) and increments by 10
// Order: Secondary (lowest to highest) -> Primary (lowest to highest)
const STANDARD_GAP = 10;

const calculateRatingsFromOrder = (factors: Factor[], _unused?: number): Factor[] => {
  const primaryFactors = factors.filter(f => f.category === 'primary').sort((a, b) => a.order - b.order);
  const secondaryFactors = factors.filter(f => f.category === 'secondary').sort((a, b) => a.order - b.order);
  
  // Build ordered list from lowest to highest priority
  const orderedFromLowest = [
    ...secondaryFactors.slice().reverse(),
    ...primaryFactors.slice().reverse(),
  ];
  
  // Assign ratings using per-factor gap multipliers
  const updatedFactors: Factor[] = [];
  let currentRating = STANDARD_GAP; // Base rating for lowest factor
  
  orderedFromLowest.forEach((factor, index) => {
    if (index === 0) {
      // Lowest priority factor gets base rating
      updatedFactors.push({ ...factor, rating: currentRating });
    } else {
      // Each subsequent factor: previous + (standard_gap × this factor's gap_multiplier)
      const gapMult = factor.gap_multiplier ?? 1.0;
      const gap = Math.round(STANDARD_GAP * gapMult);
      currentRating = currentRating + gap;
      updatedFactors.push({ ...factor, rating: currentRating });
    }
  });
  
  return updatedFactors;
};

export default function PRRDecisionDetail() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const [decision, setDecision] = useState<Decision | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [currentStep, setCurrentStep] = useState(2);

  // Form states
  const [newFactorName, setNewFactorName] = useState('');
  const [newOptionName, setNewOptionName] = useState('');
  
  // LMH Assessment states
  const [showCustomInput, setShowCustomInput] = useState<{[key: string]: boolean}>({});
  const [shareModalVisible, setShareModalVisible] = useState(false);
  const [unitValues, setUnitValues] = useState<{[key: string]: string}>({});
  const [customInputValues, setCustomInputValues] = useState<{[key: string]: string}>({});
  const [actualValues, setActualValues] = useState<{[key: string]: string}>({});
  const [customUnitInput, setCustomUnitInput] = useState<{[key: string]: string}>({});
  const [showUnitPicker, setShowUnitPicker] = useState<{[key: string]: boolean}>({});
  const [expectedInputs, setExpectedInputs] = useState<{[key: string]: string}>({});

  useEffect(() => {
    fetchDecision();
  }, [id]);

  const fetchDecision = async () => {
    try {
      const response = await api.get(`/decisions/${id}`);
      setDecision(response.data);
      // Determine current step based on data
      if (response.data.status === 'completed') {
        setCurrentStep(10);
      } else if (response.data.chosen_option_id) {
        setCurrentStep(8);
      } else if (response.data.options.length > 0 && response.data.options[0].assessments?.length > 0) {
        setCurrentStep(7);
      } else if (response.data.options.length > 0) {
        setCurrentStep(6);
      } else if (response.data.factors.length > 0 && response.data.factors.some((f: Factor) => f.category === 'primary')) {
        setCurrentStep(5); // Factors classified → show ratings (Step 5), back to Step 4 for priority adjustment
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

  const updateFactor = (factorId: string, updates: Partial<Factor>) => {
    const updatedFactors = decision!.factors.map((f) =>
      f.id === factorId ? { ...f, ...updates } : f
    );
    saveDecision({ factors: updatedFactors });
  };

  const removeFactor = (factorId: string) => {
    const updatedFactors = decision!.factors.filter((f) => f.id !== factorId);
    saveDecision({ factors: updatedFactors });
  };

  // Move factor up in priority (within same category)
  const moveFactorUp = (factorId: string) => {
    const factor = decision!.factors.find(f => f.id === factorId);
    if (!factor) return;
    
    const sameCategory = decision!.factors
      .filter(f => f.category === factor.category)
      .sort((a, b) => a.order - b.order);
    
    const currentIndex = sameCategory.findIndex(f => f.id === factorId);
    if (currentIndex <= 0) return; // Already at top
    
    // Swap orders
    const updatedFactors = decision!.factors.map(f => {
      if (f.id === factorId) {
        return { ...f, order: sameCategory[currentIndex - 1].order };
      }
      if (f.id === sameCategory[currentIndex - 1].id) {
        return { ...f, order: factor.order };
      }
      return f;
    });
    
    // Recalculate ratings based on new order
    const factorsWithRatings = calculateRatingsFromOrder(updatedFactors, decision!.rating_gap_multiplier || 1.0);
    saveDecision({ factors: factorsWithRatings });
  };

  // Move factor down in priority (within same category)
  const moveFactorDown = (factorId: string) => {
    const factor = decision!.factors.find(f => f.id === factorId);
    if (!factor) return;
    
    const sameCategory = decision!.factors
      .filter(f => f.category === factor.category)
      .sort((a, b) => a.order - b.order);
    
    const currentIndex = sameCategory.findIndex(f => f.id === factorId);
    if (currentIndex >= sameCategory.length - 1) return; // Already at bottom
    
    // Swap orders
    const updatedFactors = decision!.factors.map(f => {
      if (f.id === factorId) {
        return { ...f, order: sameCategory[currentIndex + 1].order };
      }
      if (f.id === sameCategory[currentIndex + 1].id) {
        return { ...f, order: factor.order };
      }
      return f;
    });
    
    // Recalculate ratings based on new order
    const factorsWithRatings = calculateRatingsFromOrder(updatedFactors, decision!.rating_gap_multiplier || 1.0);
    saveDecision({ factors: factorsWithRatings });
  };

  // Apply ratings when moving to next step
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

  const removeOption = (optionId: string) => {
    const updatedOptions = decision!.options.filter((o) => o.id !== optionId);
    saveDecision({ options: updatedOptions });
  };

  const updateAssessment = (optionId: string, factorId: string, percentage: number, mode?: 'L' | 'M' | 'H' | 'custom', unitValue?: string, actualValue?: number) => {
    // Clamp percentage to 0-100 range to prevent worth exceeding 100%
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
    saveDecision({
      chosen_option_id: optionId,
      decision_case: caseType,
      status: 'completed',
    });
    setCurrentStep(10);
  };

  // Helper used by both voice handler and step 7
  const getAssessmentKey = (optionId: string, factorId: string) => `${optionId}_${factorId}`;

  // ===== UNIVERSAL VOICE COMMAND HANDLER =====
  const handleAssessVoiceCommand = (command: StepVoiceCommand) => {
    if (!decision) return;

    let updatedOptions = [...decision.options.map(o => ({
      ...o,
      assessments: [...o.assessments],
    }))];

    const applyToFactor = (optionIdx: number, factorId: string) => {
      const option = updatedOptions[optionIdx];
      const key = getAssessmentKey(option.id, factorId);
      const clampedPercentage = Math.min(100, Math.max(0, command.value || 0));
      
      const existingIndex = option.assessments.findIndex((a) => a.factor_id === factorId);
      const newAssessment: OptionAssessment = {
        factor_id: factorId,
        percentage: clampedPercentage,
        assessment_mode: command.mode || 'custom',
        unit_value: unitValues[key],
      };

      if (existingIndex >= 0) {
        option.assessments = option.assessments.map((a, i) =>
          i === existingIndex ? { ...a, ...newAssessment } : a
        );
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
      updatedOptions.forEach((_, optionIdx) => {
        decision.factors.forEach(factor => {
          applyToFactor(optionIdx, factor.id);
        });
      });
    } else if (command.factorId) {
      updatedOptions.forEach((_, optionIdx) => {
        applyToFactor(optionIdx, command.factorId!);
      });
    }

    saveDecision({ options: updatedOptions, factors: decision.factors });
  };

  const handleUniversalVoiceCommand = (command: StepVoiceCommand) => {
    if (!decision) return;

    switch (command.type) {
      case 'set_title':
        if (command.text) saveDecision({ title: command.text });
        break;
      case 'set_context':
      case 'dictation':
        if (command.step === 1 && command.text) {
          saveDecision({ context: (decision.context || '') + ' ' + command.text });
        } else if (command.step === 9 && command.text) {
          saveDecision({ reflection: (decision.reflection || '') + ' ' + command.text });
        } else if (command.step === 10 && command.text) {
          saveDecision({ final_notes: (decision.final_notes || '') + ' ' + command.text });
        }
        break;
      case 'add_factor':
        if (command.text) {
          const exists = decision.factors.some(f => f.name.toLowerCase() === command.text!.toLowerCase());
          if (!exists) {
            const newFactor: Factor = {
              id: `factor_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
              name: command.text, category: 'secondary', rating: 50, order: decision.factors.length,
            };
            saveDecision({ factors: [...decision.factors, newFactor] });
          }
        }
        break;
      case 'remove_factor':
        if (command.factorId) removeFactor(command.factorId);
        break;
      case 'classify_factor':
        if (command.allFactors && command.category) {
          saveDecision({ factors: decision.factors.map(f => ({ ...f, category: command.category! })) });
        } else if (command.factorId && command.category) {
          updateFactor(command.factorId, { category: command.category });
        }
        break;
      case 'move_factor':
        if (command.factorId && command.direction) {
          if (command.direction === 'up') moveFactorUp(command.factorId);
          else if (command.direction === 'down') moveFactorDown(command.factorId);
          else if (command.direction === 'first') {
            const updated = decision.factors.map(f => f.id === command.factorId ? { ...f, order: -1 } : f)
              .sort((a, b) => a.order - b.order).map((f, i) => ({ ...f, order: i }));
            saveDecision({ factors: calculateRatingsFromOrder(updated, decision.rating_gap_multiplier || 1.0) });
          } else if (command.direction === 'last') {
            const updated = decision.factors.map(f => f.id === command.factorId ? { ...f, order: 999 } : f)
              .sort((a, b) => a.order - b.order).map((f, i) => ({ ...f, order: i }));
            saveDecision({ factors: calculateRatingsFromOrder(updated, decision.rating_gap_multiplier || 1.0) });
          }
        }
        break;
      case 'add_option':
        if (command.text) {
          const exists = decision.options.some(o => o.name.toLowerCase() === command.text!.toLowerCase());
          if (!exists) {
            const newOption: DecisionOption = {
              id: `option_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
              name: command.text, assessments: [], worth_percentage: 0,
            };
            saveDecision({ options: [...decision.options, newOption] });
          }
        }
        break;
      case 'remove_option':
        if (command.optionId) removeOption(command.optionId);
        break;
      case 'assess_factor':
      case 'assess_all':
        handleAssessVoiceCommand(command);
        break;
      case 'choose_option':
        if (command.optionId) saveDecision({ chosen_option_id: command.optionId });
        break;
      default: break;
    }
  };

  const getAssessmentValue = (optionId: string, factorId: string): number | null => {
    const option = decision?.options.find((o) => o.id === optionId);
    const assessment = option?.assessments.find((a) => a.factor_id === factorId);
    // Return null if no assessment exists (no default value)
    return assessment?.percentage ?? null;
  };

  // Calculate worth percentage using weighted average formula
  // Formula: Sum(Rating × Assessment%) / Sum(All Ratings)
  // This ensures result is always 0-100%
  const calculateDynamicWorth = (option: DecisionOption): { worth: number; assessedCount: number; totalCount: number } => {
    const factors = decision?.factors || [];
    const totalFactors = factors.length;
    const assessedFactors = option.assessments.filter(a => a.percentage !== undefined && a.percentage !== null);
    
    if (assessedFactors.length === 0 || totalFactors === 0) {
      return { worth: 0, assessedCount: 0, totalCount: totalFactors };
    }

    // Get total of ALL factor ratings (not just assessed ones)
    const totalRating = factors.reduce((sum, f) => sum + f.rating, 0);

    if (totalRating === 0) {
      return { worth: 0, assessedCount: assessedFactors.length, totalCount: totalFactors };
    }

    // Calculate weighted sum: Sum(rating × assessment%)
    let weightedSum = 0;
    for (const assessment of assessedFactors) {
      const factor = factors.find(f => f.id === assessment.factor_id);
      if (factor) {
        // Clamp individual assessment percentage to 0-100 before calculation
        const clampedPercentage = Math.min(100, Math.max(0, assessment.percentage));
        weightedSum += factor.rating * (clampedPercentage / 100);
      }
    }

    // Divide by total ratings to get weighted average (0-100%)
    const rawWorth = (weightedSum / totalRating) * 100;
    // Cap at 100% - mathematically impossible to exceed if assessments are 0-100%
    const worth = Math.min(100, Math.max(0, rawWorth));

    return { 
      worth: Math.round(worth * 10) / 10, 
      assessedCount: assessedFactors.length, 
      totalCount: totalFactors 
    };
  };

  if (loading || !decision) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={COLORS.primary} />
        </View>
      </SafeAreaView>
    );
  }

  const isCompleted = decision.status === 'completed';

  const renderStepIndicator = () => (
    <View style={styles.stepIndicator}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flex: 1 }}>
        {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((step) => {
          const canNavigate = isCompleted || step <= currentStep;
          return (
            <TouchableOpacity
              key={step}
              style={[
                styles.stepDot,
                canNavigate && styles.stepDotActive,
                step === currentStep && styles.stepDotCurrent,
              ]}
              onPress={() => canNavigate && setCurrentStep(step)}
            >
              <Text
                style={[
                  styles.stepDotText,
                  canNavigate && styles.stepDotTextActive,
                ]}
              >
                {step}
              </Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
      <TouchableOpacity
        style={styles.shareStepBtn}
        onPress={() => setShareModalVisible(true)}
      >
        <Ionicons name="share-outline" size={16} color={COLORS.primary} />
      </TouchableOpacity>
      {saving && <ActivityIndicator size="small" color={COLORS.primary} style={styles.savingIndicator} />}
    </View>
  );

  const renderStep2 = () => {
    const handleExpectedValueChange = (factorId: string, value: string) => {
      setExpectedInputs({ ...expectedInputs, [factorId]: value });
    };

    const handleExpectedValueBlur = (factorId: string) => {
      const raw = (expectedInputs[factorId] ?? '').trim();
      if (!raw) {
        updateFactor(factorId, { expected_value: undefined, data_type: undefined, operator: undefined });
        return;
      }
      const detectedType = senseDataType(raw);
      const numericVal = detectedType === 'numeric' ? parseFloat(raw) : undefined;
      const currentOp = decision.factors.find(f => f.id === factorId)?.operator;
      // Auto-set default operator if none selected or if type changed
      const validOps = detectedType === 'numeric'
        ? NUMERIC_OPERATORS.map(o => o.value)
        : TEXT_OPERATORS.map(o => o.value);
      const newOp = currentOp && validOps.includes(currentOp) ? currentOp : validOps[0];
      updateFactor(factorId, {
        expected_value: numericVal !== undefined ? numericVal : raw,
        data_type: detectedType,
        operator: newOp,
      });
    };

    const getExpectedInput = (factor: Factor): string => {
      if (expectedInputs[factor.id] !== undefined) return expectedInputs[factor.id];
      if (factor.expected_value !== undefined && factor.expected_value !== null) return String(factor.expected_value);
      return '';
    };

    const getDetectedType = (factor: Factor): 'numeric' | 'text' => {
      if (factor.data_type) return factor.data_type;
      const val = expectedInputs[factor.id] ?? (factor.expected_value !== undefined ? String(factor.expected_value) : '');
      return senseDataType(val);
    };

    return (
      <View style={styles.stepContent}>
        <Text style={styles.stepTitle}>Step 2: Define Factors & Criteria</Text>
        <Text style={styles.stepDescription}>
          List factors, set expected values with comparison operators, and optionally assign measurement units.
        </Text>

        {decision.factors.map((factor) => {
          const detectedType = getDetectedType(factor);
          const operators = detectedType === 'numeric' ? NUMERIC_OPERATORS : TEXT_OPERATORS;
          const hasExpected = factor.expected_value !== undefined && factor.expected_value !== null;

          return (
            <Card key={factor.id} style={styles.factorCard}>
              {/* Row 1: Factor name + badges + delete */}
              <View style={styles.factorHeader}>
                <Text style={styles.factorName}>{factor.name}</Text>
                {hasExpected && (
                  <View style={styles.criteriaPreview}>
                    <Text style={styles.criteriaPreviewText}>
                      {factor.operator || '≥'} {String(factor.expected_value)}{factor.unit ? ` ${factor.unit}` : ''}
                    </Text>
                  </View>
                )}
                <TouchableOpacity onPress={() => removeFactor(factor.id)}>
                  <Ionicons name="close-circle" size={22} color={COLORS.error} />
                </TouchableOpacity>
              </View>

              {/* Row 2: Expected value input + data type badge */}
              <View style={styles.expectedRow}>
                <Text style={styles.expectedLabel}>Expected:</Text>
                <TextInput
                  style={styles.expectedInput}
                  placeholder="e.g. 20 or Bangalore"
                  placeholderTextColor={COLORS.textMuted}
                  value={getExpectedInput(factor)}
                  onChangeText={(v) => handleExpectedValueChange(factor.id, v)}
                  onBlur={() => handleExpectedValueBlur(factor.id)}
                />
                <View style={[styles.dataTypeBadge, detectedType === 'text' ? styles.dataTypeBadgeText : null]}>
                  <Text style={styles.dataTypeBadgeLabel}>
                    {detectedType === 'numeric' ? '123' : 'abc'}
                  </Text>
                </View>
              </View>

              {/* Row 3: Operator selector */}
              <View style={styles.operatorRow}>
                <Text style={styles.operatorLabel}>Operator:</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flex: 1 }}>
                  <View style={styles.operatorChipsContainer}>
                    {operators.map((op) => (
                      <TouchableOpacity
                        key={op.value}
                        style={[
                          styles.operatorChip,
                          factor.operator === op.value && styles.operatorChipActive,
                        ]}
                        onPress={() => updateFactor(factor.id, { operator: op.value })}
                      >
                        <Text style={[
                          styles.operatorChipText,
                          factor.operator === op.value && styles.operatorChipTextActive,
                        ]}>{op.label}</Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </ScrollView>
              </View>

              {/* Row 4: Unit selector (only for numeric) */}
              {detectedType === 'numeric' && (
                <View style={styles.unitSelectorRow}>
                  <Text style={styles.unitSelectorLabel}>Unit:</Text>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.unitChipsScroll}>
                    <View style={styles.unitChipsContainer}>
                      {factor.unit && (
                        <TouchableOpacity
                          style={[styles.unitChip, styles.unitChipClear]}
                          onPress={() => updateFactor(factor.id, { unit: undefined })}
                        >
                          <Ionicons name="close" size={12} color={COLORS.error} />
                        </TouchableOpacity>
                      )}
                      {UNIT_PRESETS.map((preset) => (
                        <TouchableOpacity
                          key={preset.value}
                          style={[
                            styles.unitChip,
                            factor.unit === preset.value && styles.unitChipActive,
                          ]}
                          onPress={() => updateFactor(factor.id, { unit: preset.value })}
                        >
                          <Text style={[
                            styles.unitChipText,
                            factor.unit === preset.value && styles.unitChipTextActive,
                          ]}>{preset.label}</Text>
                        </TouchableOpacity>
                      ))}
                      <TouchableOpacity
                        style={[
                          styles.unitChip,
                          styles.unitChipCustom,
                          showUnitPicker[factor.id] && styles.unitChipActive,
                        ]}
                        onPress={() => setShowUnitPicker({ ...showUnitPicker, [factor.id]: !showUnitPicker[factor.id] })}
                      >
                        <Text style={[
                          styles.unitChipText,
                          showUnitPicker[factor.id] && styles.unitChipTextActive,
                        ]}>✎</Text>
                      </TouchableOpacity>
                    </View>
                  </ScrollView>
                </View>
              )}
              {showUnitPicker[factor.id] && detectedType === 'numeric' && (
                <View style={styles.customUnitRow}>
                  <TextInput
                    style={styles.customUnitInput}
                    placeholder="Custom unit (e.g., Km/Liter)"
                    placeholderTextColor={COLORS.textMuted}
                    value={customUnitInput[factor.id] || ''}
                    onChangeText={(v) => setCustomUnitInput({ ...customUnitInput, [factor.id]: v })}
                    onSubmitEditing={() => {
                      const val = (customUnitInput[factor.id] || '').trim();
                      if (val) {
                        updateFactor(factor.id, { unit: val });
                        setShowUnitPicker({ ...showUnitPicker, [factor.id]: false });
                      }
                    }}
                  />
                  <TouchableOpacity
                    style={styles.customUnitApplyBtn}
                    onPress={() => {
                      const val = (customUnitInput[factor.id] || '').trim();
                      if (val) {
                        updateFactor(factor.id, { unit: val });
                        setShowUnitPicker({ ...showUnitPicker, [factor.id]: false });
                      }
                    }}
                  >
                    <Ionicons name="checkmark" size={18} color={COLORS.white} />
                  </TouchableOpacity>
                </View>
              )}
            </Card>
          );
        })}

        <View style={styles.addFactorRow}>
          <TextInput
            style={styles.addInput}
            placeholder="Add a factor (e.g., Salary, Mileage, Location)"
            placeholderTextColor={COLORS.textMuted}
            value={newFactorName}
            onChangeText={setNewFactorName}
            onSubmitEditing={addFactor}
          />
          <TouchableOpacity style={styles.addButton} onPress={addFactor}>
            <Ionicons name="add" size={24} color={COLORS.white} />
          </TouchableOpacity>
        </View>

        <GradientButton
          title="Continue to Classification"
          onPress={() => setCurrentStep(3)}
          disabled={decision.factors.length < 2}
          style={styles.continueButton}
        />
      </View>
    );
  };

  const renderStep3 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Step 3: Classify Factors</Text>
      <Text style={styles.stepDescription}>
        Categorize each factor as Primary (essential) or Secondary (important but not critical).
      </Text>

      {decision.factors.map((factor) => (
        <Card key={factor.id} style={styles.factorCard}>
          <Text style={styles.factorName}>{factor.name}</Text>
          <View style={styles.categoryButtons}>
            <TouchableOpacity
              style={[
                styles.categoryButton,
                factor.category === 'primary' && styles.categoryButtonActive,
              ]}
              onPress={() => updateFactor(factor.id, { category: 'primary' })}
            >
              <Text
                style={[
                  styles.categoryText,
                  factor.category === 'primary' && styles.categoryTextActive,
                ]}
              >
                Primary
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[
                styles.categoryButton,
                factor.category === 'secondary' && styles.categoryButtonActive,
              ]}
              onPress={() => updateFactor(factor.id, { category: 'secondary' })}
            >
              <Text
                style={[
                  styles.categoryText,
                  factor.category === 'secondary' && styles.categoryTextActive,
                ]}
              >
                Secondary
              </Text>
            </TouchableOpacity>
          </View>
        </Card>
      ))}

      <View style={styles.navButtons}>
        <TouchableOpacity style={styles.backButton} onPress={() => setCurrentStep(2)}>
          <Ionicons name="arrow-back" size={20} color={COLORS.textSecondary} />
          <Text style={styles.backButtonText}>Back</Text>
        </TouchableOpacity>
        <GradientButton
          title="Prioritize Factors"
          onPress={() => setCurrentStep(4)}
          style={styles.nextButton}
        />
      </View>
    </View>
  );

  // Step 4: Prioritize by ordering (drag up/down)
  const renderStep4 = () => {
    const primaryFactors = decision.factors
      .filter(f => f.category === 'primary')
      .sort((a, b) => a.order - b.order);
    const secondaryFactors = decision.factors
      .filter(f => f.category === 'secondary')
      .sort((a, b) => a.order - b.order);

    const renderFactorWithReorder = (factor: Factor, index: number, total: number) => (
      <Card key={factor.id} style={styles.reorderCard}>
        <View style={styles.reorderRow}>
          <View style={styles.reorderRank}>
            <Text style={styles.rankNumber}>{index + 1}</Text>
          </View>
          <Text style={styles.reorderName}>{factor.name}</Text>
          <View style={styles.reorderButtons}>
            <TouchableOpacity
              style={[styles.arrowButton, index === 0 && styles.arrowButtonDisabled]}
              onPress={() => moveFactorUp(factor.id)}
              disabled={index === 0}
            >
              <Ionicons 
                name="chevron-up" 
                size={20} 
                color={index === 0 ? COLORS.textMuted : COLORS.primary} 
              />
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.arrowButton, index === total - 1 && styles.arrowButtonDisabled]}
              onPress={() => moveFactorDown(factor.id)}
              disabled={index === total - 1}
            >
              <Ionicons 
                name="chevron-down" 
                size={20} 
                color={index === total - 1 ? COLORS.textMuted : COLORS.primary} 
              />
            </TouchableOpacity>
          </View>
        </View>
      </Card>
    );

    return (
      <View style={styles.stepContent}>
        <Text style={styles.stepTitle}>Step 4: Prioritize Factors</Text>
        <Text style={styles.stepDescription}>
          Order factors by importance within each category. Use arrows to move factors up or down. 
          The system will automatically calculate ratings based on your ordering.
        </Text>

        {primaryFactors.length > 0 && (
          <>
            <Text style={styles.sectionLabel}>Primary Factors (Most Important First)</Text>
            {primaryFactors.map((factor, index) => 
              renderFactorWithReorder(factor, index, primaryFactors.length)
            )}
          </>
        )}

        {secondaryFactors.length > 0 && (
          <>
            <Text style={[styles.sectionLabel, { marginTop: 16 }]}>Secondary Factors (Most Important First)</Text>
            {secondaryFactors.map((factor, index) => 
              renderFactorWithReorder(factor, index, secondaryFactors.length)
            )}
          </>
        )}

        <View style={styles.tipBox}>
          <Ionicons name="information-circle" size={20} color={COLORS.primary} />
          <Text style={styles.tipText}>
            Ratings are auto-calculated: Starting from 10 for the lowest priority factor, 
            incrementing by 10 for each higher priority. Secondary factors get lower ratings, 
            Primary factors get higher ratings.
          </Text>
        </View>

        <View style={styles.navButtons}>
          <TouchableOpacity style={styles.backButton} onPress={() => setCurrentStep(3)}>
            <Ionicons name="arrow-back" size={20} color={COLORS.textSecondary} />
            <Text style={styles.backButtonText}>Back</Text>
          </TouchableOpacity>
          <GradientButton
            title="Calculate Ratings"
            onPress={() => setCurrentStep(5)}
            style={styles.nextButton}
          />
        </View>
      </View>
    );
  };

  // Step 5: Show calculated ratings with per-factor gap adjustment
  const renderStep5 = () => {
    // Always recalculate from per-factor gaps for live preview
    const recalculated = calculateRatingsFromOrder(decision.factors);

    // Sort factors by rating descending for display (highest priority first)
    const sortedFactors = [...recalculated].sort((a, b) => b.rating - a.rating);
    const highestRating = sortedFactors.length > 0 ? sortedFactors[0].rating : 100;

    // Build ordered list from lowest to highest for gap context
    const primaryFactors = recalculated.filter(f => f.category === 'primary').sort((a, b) => a.order - b.order);
    const secondaryFactors = recalculated.filter(f => f.category === 'secondary').sort((a, b) => a.order - b.order);
    const orderedFromLowest = [
      ...secondaryFactors.slice().reverse(),
      ...primaryFactors.slice().reverse(),
    ];

    const handleFactorGapChange = (factorId: string, multiplier: number) => {
      const updatedFactors = decision.factors.map(f =>
        f.id === factorId ? { ...f, gap_multiplier: multiplier } : f
      );
      const recalculated = calculateRatingsFromOrder(updatedFactors);
      saveDecision({ factors: recalculated });
    };

    const exceedsLimit = highestRating > 100;

    return (
      <View style={styles.stepContent}>
        <Text style={styles.stepTitle}>Step 5: Rate Factor Importance</Text>
        <Text style={styles.stepDescription}>
          Adjust each factor's gap from the one below it. Standard gap = {STANDARD_GAP} pts. Higher gaps amplify how much more important that factor is.
        </Text>

        {exceedsLimit && (
          <View style={styles.gapWarningBox}>
            <Ionicons name="warning" size={16} color="#F59E0B" />
            <Text style={styles.gapWarningText}>
              Top rating ({highestRating}) exceeds 100%. Requires admin/account-level approval for exceptional cases.
            </Text>
          </View>
        )}

        {/* Factors listed from highest to lowest with per-factor gap selector */}
        {sortedFactors.map((factor, displayIndex) => {
          const orderedIndex = orderedFromLowest.findIndex(f => f.id === factor.id);
          const isLowest = orderedIndex === 0;
          const gapMult = factor.gap_multiplier ?? 1.0;
          const gapPts = isLowest ? STANDARD_GAP : Math.round(STANDARD_GAP * gapMult);
          const belowFactor = !isLowest ? orderedFromLowest[orderedIndex - 1] : null;

          return (
            <Card key={factor.id} style={styles.ratingCard}>
              <View style={styles.ratingHeader}>
                <View style={[styles.ratingRank, factor.category === 'secondary' && { backgroundColor: COLORS.teal }]}>
                  <Text style={styles.rankNumber}>{displayIndex + 1}</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.factorName}>{factor.name}</Text>
                </View>
                <View style={[styles.categoryBadgeSmall, factor.category === 'primary' ? styles.catBadgePrimary : styles.catBadgeSecondary]}>
                  <Text style={styles.categoryBadgeSmallText}>
                    {factor.category === 'primary' ? 'P' : 'S'}
                  </Text>
                </View>
                <View style={[
                  styles.ratingBadge,
                  factor.category === 'secondary' && { backgroundColor: COLORS.teal },
                  factor.rating > 100 && { backgroundColor: '#F59E0B' },
                ]}>
                  <Text style={styles.ratingBadgeText}>{factor.rating}</Text>
                </View>
              </View>

              {/* Rating bar */}
              <View style={styles.ratingBarContainer}>
                <View style={[styles.ratingBarFill, {
                  width: `${Math.min(100, (factor.rating / Math.max(highestRating, 100)) * 100)}%`,
                  backgroundColor: factor.rating > 100
                    ? '#F59E0B'
                    : factor.category === 'primary'
                      ? COLORS.primary
                      : COLORS.teal,
                }]} />
              </View>

              {/* Per-factor gap selector (not shown for lowest) */}
              {!isLowest ? (
                <View style={styles.perFactorGapRow}>
                  <Text style={styles.perFactorGapLabel}>
                    Gap from {belowFactor?.name || 'below'}: +{gapPts}
                  </Text>
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flex: 1 }}>
                    <View style={styles.gapChipsRow}>
                      {GAP_PRESETS.map((preset) => (
                        <TouchableOpacity
                          key={preset.value}
                          style={[
                            styles.gapChipSmall,
                            gapMult === preset.value && styles.gapChipSmallActive,
                            preset.warn && styles.gapChipSmallWarn,
                            preset.warn && gapMult === preset.value && styles.gapChipSmallWarnActive,
                          ]}
                          onPress={() => handleFactorGapChange(factor.id, preset.value)}
                        >
                          <Text style={[
                            styles.gapChipSmallText,
                            gapMult === preset.value && styles.gapChipSmallTextActive,
                            preset.warn && styles.gapChipSmallTextWarn,
                            preset.warn && gapMult === preset.value && styles.gapChipSmallTextWarnActive,
                          ]}>{preset.label}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  </ScrollView>
                </View>
              ) : (
                <Text style={styles.baseRatingNote}>Base rating: {STANDARD_GAP}</Text>
              )}
            </Card>
          );
        })}

        {/* Summary */}
        <Card style={styles.ratingSummaryCard}>
          <View style={styles.ratingSummaryRow}>
            <Text style={styles.ratingSummaryLabel}>Rating range</Text>
            <Text style={[styles.ratingSummaryValue, exceedsLimit && { color: '#F59E0B', fontWeight: '700' as any }]}>
              {STANDARD_GAP} → {highestRating}
            </Text>
          </View>
          <View style={styles.ratingSummaryRow}>
            <Text style={styles.ratingSummaryLabel}>Factors</Text>
            <Text style={styles.ratingSummaryValue}>{decision.factors.length}</Text>
          </View>
        </Card>

        <View style={styles.navButtons}>
          <TouchableOpacity style={styles.backButton} onPress={() => setCurrentStep(4)}>
            <Ionicons name="arrow-back" size={20} color={COLORS.textSecondary} />
            <Text style={styles.backButtonText}>Adjust Priority</Text>
          </TouchableOpacity>
          <GradientButton
            title="Add Options"
            onPress={applyRatingsAndContinue}
            style={styles.nextButton}
          />
        </View>
      </View>
    );
  };

  const renderStep6 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Step 6: Define Options</Text>
      <Text style={styles.stepDescription}>
        List all the options you're considering for this decision.
      </Text>

      {decision.options.map((option) => (
        <Card key={option.id} style={styles.optionCard}>
          <View style={styles.optionHeader}>
            <Text style={styles.optionName}>{option.name}</Text>
            <TouchableOpacity onPress={() => removeOption(option.id)}>
              <Ionicons name="close-circle" size={22} color={COLORS.error} />
            </TouchableOpacity>
          </View>
        </Card>
      ))}

      <View style={styles.addFactorRow}>
        <TextInput
          style={styles.addInput}
          placeholder="Add an option (e.g., Company A, Company B)"
          placeholderTextColor={COLORS.textMuted}
          value={newOptionName}
          onChangeText={setNewOptionName}
          onSubmitEditing={addOption}
        />
        <TouchableOpacity style={styles.addButton} onPress={addOption}>
          <Ionicons name="add" size={24} color={COLORS.white} />
        </TouchableOpacity>
      </View>

      <View style={styles.navButtons}>
        <TouchableOpacity style={styles.backButton} onPress={() => setCurrentStep(5)}>
          <Ionicons name="arrow-back" size={20} color={COLORS.textSecondary} />
          <Text style={styles.backButtonText}>Back</Text>
        </TouchableOpacity>
        <GradientButton
          title="Assess Options"
          onPress={() => setCurrentStep(7)}
          disabled={decision.options.length < 2}
          style={styles.nextButton}
        />
      </View>
    </View>
  );

  // Auto-calculate match % from actual value vs factor criteria
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
        case '>=':
        case '>':
          // Directly proportional: higher is better
          if (factor.operator === '>=' ? actual >= expected : actual > expected) return 100;
          return Math.max(0, Math.round((actual / expected) * 100));
        case '<=':
        case '<':
          // Inversely proportional: lower is better
          if (factor.operator === '<=' ? actual <= expected : actual < expected) return 100;
          return actual === 0 ? 100 : Math.max(0, Math.round((expected / actual) * 100));
        case '=':
          // Exact match with deviation penalty
          const deviation = Math.abs(actual - expected) / Math.abs(expected);
          return Math.max(0, Math.round((1 - deviation) * 100));
        case '!=':
          return actual !== expected ? 100 : 0;
        default:
          return null;
      }
    } else {
      // Text comparison
      const expected = String(factor.expected_value).toLowerCase().trim();
      const actual = String(actualValue).toLowerCase().trim();
      if (!expected || !actual) return null;

      switch (factor.operator) {
        case 'contains':
          return actual.includes(expected) ? 100 : 0;
        case 'starts_with':
          return actual.startsWith(expected) ? 100 : 0;
        case 'ends_with':
          return actual.endsWith(expected) ? 100 : 0;
        case 'equals':
          return actual === expected ? 100 : 0;
        case 'not_equals':
          return actual !== expected ? 100 : 0;
        default:
          return null;
      }
    }
  };

  const renderStep7 = () => {
    const handleLMHSelect = (optionId: string, factorId: string, mode: 'L' | 'M' | 'H') => {
      const percentage = LMH_VALUES[mode].percentage;
      const key = getAssessmentKey(optionId, factorId);
      setShowCustomInput({ ...showCustomInput, [key]: false });
      setCustomInputValues({ ...customInputValues, [key]: '' }); // Clear custom input
      // Get current actual value to preserve it
      const currentActual = getActualValue(optionId, factorId);
      const factor = decision.factors.find(f => f.id === factorId);
      const unitStr = factor?.unit || '';
      const displayValue = currentActual !== undefined ? `${currentActual}${unitStr ? ' ' + unitStr : ''}` : '';
      updateAssessment(optionId, factorId, percentage, mode, displayValue, currentActual);
    };

    const handleCustomSelect = (optionId: string, factorId: string) => {
      const key = getAssessmentKey(optionId, factorId);
      const currentValue = getAssessmentValue(optionId, factorId);
      setShowCustomInput({ ...showCustomInput, [key]: true });
      setCustomInputValues({ ...customInputValues, [key]: String(currentValue) });
    };

    const handleCustomInputChange = (optionId: string, factorId: string, value: string) => {
      const key = getAssessmentKey(optionId, factorId);
      // Only allow numbers and clamp to 0-100
      const cleanValue = value.replace(/[^0-9]/g, '');
      const num = parseInt(cleanValue) || 0;
      // Clamp to max 100 in real-time to prevent values > 100%
      const clampedValue = num > 100 ? '100' : cleanValue;
      setCustomInputValues({ ...customInputValues, [key]: clampedValue });
    };

    const handleCustomInputBlur = (optionId: string, factorId: string) => {
      const key = getAssessmentKey(optionId, factorId);
      const inputValue = customInputValues[key] || '0';
      const num = parseInt(inputValue) || 0;
      const percentage = Math.min(100, Math.max(0, num));
      // Preserve actual value when changing percentage
      const currentActual = getActualValue(optionId, factorId);
      const factor = decision.factors.find(f => f.id === factorId);
      const unitStr = factor?.unit || '';
      const displayValue = currentActual !== undefined ? `${currentActual}${unitStr ? ' ' + unitStr : ''}` : '';
      updateAssessment(optionId, factorId, percentage, 'custom', displayValue, currentActual);
    };

    const handleUnitValueChange = (optionId: string, factorId: string, value: string) => {
      const key = getAssessmentKey(optionId, factorId);
      const factor = decision.factors.find(f => f.id === factorId);
      const isTextType = factor?.data_type === 'text';
      
      if (isTextType) {
        // Allow any text for text-type factors
        setActualValues({ ...actualValues, [key]: value });
      } else {
        // Allow only numeric input (with decimal)
        const cleanValue = value.replace(/[^0-9.]/g, '');
        const parts = cleanValue.split('.');
        const sanitized = parts.length > 2 ? parts[0] + '.' + parts.slice(1).join('') : cleanValue;
        setActualValues({ ...actualValues, [key]: sanitized });
      }
    };

    const handleActualValueBlur = (optionId: string, factorId: string) => {
      const key = getAssessmentKey(optionId, factorId);
      const inputValue = (actualValues[key] || '').trim();
      const factor = decision.factors.find(f => f.id === factorId);
      const isTextType = factor?.data_type === 'text';

      let actualVal: number | string | undefined;
      if (isTextType) {
        actualVal = inputValue || undefined;
      } else {
        const numVal = parseFloat(inputValue);
        actualVal = isNaN(numVal) ? undefined : numVal;
      }

      const unitStr = factor?.unit || '';
      const displayValue = actualVal !== undefined ? `${actualVal}${unitStr ? ' ' + unitStr : ''}` : '';
      const numericActual = typeof actualVal === 'number' ? actualVal : undefined;

      // Auto-calculate percentage if criteria defined
      const autoPercent = factor ? calculateAutoPercentage(factor, actualVal) : null;

      if (autoPercent !== null) {
        // Auto-set the percentage from criteria match
        updateAssessment(optionId, factorId, autoPercent, 'auto' as any, displayValue, numericActual);
      } else {
        // Keep existing percentage, just store the actual value
        const currentMode = getAssessmentMode(optionId, factorId);
        const currentPercentage = getAssessmentValue(optionId, factorId);
        updateAssessment(optionId, factorId, currentPercentage, currentMode, displayValue, numericActual);
      }
    };

    const getActualInputValue = (optionId: string, factorId: string): string => {
      const key = getAssessmentKey(optionId, factorId);
      if (actualValues[key] !== undefined) return actualValues[key];
      const stored = getActualValue(optionId, factorId);
      if (stored !== undefined) return String(stored);
      // Fallback: try to parse from legacy unit_value
      const legacy = getUnitValue(optionId, factorId);
      if (legacy) {
        const factor = decision.factors.find(f => f.id === factorId);
        if (factor?.data_type === 'text') return legacy;
        const num = parseFloat(legacy);
        if (!isNaN(num)) return String(num);
      }
      return '';
    };

    const getCustomInputValue = (optionId: string, factorId: string): string => {
      const key = getAssessmentKey(optionId, factorId);
      if (customInputValues[key] !== undefined) {
        return customInputValues[key];
      }
      const value = getAssessmentValue(optionId, factorId);
      return value !== null ? String(value) : '';
    };

    return (
      <View style={styles.stepContent}>
        <Text style={styles.stepTitle}>Step 6-7: Assess & Calculate</Text>
        <Text style={styles.stepDescription}>
          Rate how well each option satisfies each factor using quick LMH toggles or specific percentage.
        </Text>

        {/* Voice Input Hint */}
        <View style={styles.voiceInputRow}>
          <View style={styles.voiceHintBox}>
            <Ionicons name="mic-outline" size={16} color={COLORS.primary} />
            <Text style={styles.voiceHint}>Use the Voice Input button below to speak commands like "Salary High" or "All Medium"</Text>
          </View>
        </View>

        {/* LMH Legend */}
        <Card style={styles.legendCard}>
          <Text style={styles.legendTitle}>Assessment Legend</Text>
          <View style={styles.legendRow}>
            <View style={styles.legendItem}>
              <View style={[styles.legendDot, { backgroundColor: LMH_VALUES.L.color }]} />
              <Text style={styles.legendText}>L = Low (25%)</Text>
            </View>
            <View style={styles.legendItem}>
              <View style={[styles.legendDot, { backgroundColor: LMH_VALUES.M.color }]} />
              <Text style={styles.legendText}>M = Medium (50%)</Text>
            </View>
            <View style={styles.legendItem}>
              <View style={[styles.legendDot, { backgroundColor: LMH_VALUES.H.color }]} />
              <Text style={styles.legendText}>H = High (75%)</Text>
            </View>
          </View>
        </Card>

        {decision.options.map((option) => {
          const dynamicWorth = calculateDynamicWorth(option);
          
          return (
          <Card key={option.id} style={styles.assessmentCard}>
            <View style={styles.assessmentHeader}>
              <Text style={styles.optionName}>{option.name}</Text>
              <View style={[
                styles.worthBadge, 
                dynamicWorth.assessedCount === 0 && styles.worthBadgeEmpty
              ]}>
                {dynamicWorth.assessedCount > 0 ? (
                  <Text style={styles.worthText}>{dynamicWorth.worth.toFixed(1)}%</Text>
                ) : (
                  <Text style={styles.worthTextEmpty}>--</Text>
                )}
              </View>
            </View>
            
            {/* Progress indicator */}
            <View style={styles.assessmentProgress}>
              <Text style={styles.progressText}>
                {dynamicWorth.assessedCount}/{dynamicWorth.totalCount} factors rated
              </Text>
            </View>

            {decision.factors
              .sort((a, b) => b.rating - a.rating)
              .map((factor) => {
                const key = getAssessmentKey(option.id, factor.id);
                const currentMode = getAssessmentMode(option.id, factor.id);
                const currentValue = getAssessmentValue(option.id, factor.id);
                const isCustom = showCustomInput[key] || currentMode === 'custom';
                const hasValue = currentValue !== null;

                return (
                  <View key={factor.id} style={styles.assessmentFactorContainer}>
                    {/* Factor header with rating and unit badge */}
                    <View style={styles.assessmentLabelRow}>
                      <Text style={styles.assessmentLabel}>{factor.name}</Text>
                      {factor.unit && (
                        <View style={styles.factorUnitBadge}>
                          <Text style={styles.factorUnitBadgeText}>{factor.unit}</Text>
                        </View>
                      )}
                      {factor.expected_value !== undefined && factor.expected_value !== null && (
                        <View style={styles.expectedCriteriaBadge}>
                          <Text style={styles.expectedCriteriaText}>
                            {factor.operator || '≥'} {String(factor.expected_value)}{factor.unit ? ` ${factor.unit}` : ''}
                          </Text>
                        </View>
                      )}
                      <Text style={styles.assessmentRating}>({factor.rating})</Text>
                    </View>

                    {/* Actual Value input — text or numeric based on data_type */}
                    <View style={styles.actualValueRow}>
                      <View style={styles.actualValueInputWrap}>
                        <TextInput
                          style={styles.actualValueInput}
                          placeholder={
                            factor.data_type === 'text'
                              ? `Enter ${factor.name.toLowerCase()} value`
                              : factor.unit
                                ? `Value in ${factor.unit}`
                                : 'Actual value (optional)'
                          }
                          placeholderTextColor={COLORS.textMuted}
                          value={getActualInputValue(option.id, factor.id)}
                          onChangeText={(value) => handleUnitValueChange(option.id, factor.id, value)}
                          onBlur={() => handleActualValueBlur(option.id, factor.id)}
                          keyboardType={factor.data_type === 'text' ? 'default' : 'decimal-pad'}
                        />
                        {factor.unit ? (
                          <View style={styles.unitSuffix}>
                            <Text style={styles.unitSuffixText}>{factor.unit}</Text>
                          </View>
                        ) : null}
                      </View>
                    </View>

                    {/* LMH Toggle Buttons + Custom */}
                    <View style={styles.lmhContainer}>
                      <TouchableOpacity
                        style={[
                          styles.lmhButton,
                          { borderColor: LMH_VALUES.L.color },
                          currentMode === 'L' && { backgroundColor: LMH_VALUES.L.color },
                        ]}
                        onPress={() => handleLMHSelect(option.id, factor.id, 'L')}
                      >
                        <Text style={[
                          styles.lmhText,
                          { color: currentMode === 'L' ? COLORS.white : LMH_VALUES.L.color },
                        ]}>L</Text>
                      </TouchableOpacity>

                      <TouchableOpacity
                        style={[
                          styles.lmhButton,
                          { borderColor: LMH_VALUES.M.color },
                          currentMode === 'M' && { backgroundColor: LMH_VALUES.M.color },
                        ]}
                        onPress={() => handleLMHSelect(option.id, factor.id, 'M')}
                      >
                        <Text style={[
                          styles.lmhText,
                          { color: currentMode === 'M' ? COLORS.white : LMH_VALUES.M.color },
                        ]}>M</Text>
                      </TouchableOpacity>

                      <TouchableOpacity
                        style={[
                          styles.lmhButton,
                          { borderColor: LMH_VALUES.H.color },
                          currentMode === 'H' && { backgroundColor: LMH_VALUES.H.color },
                        ]}
                        onPress={() => handleLMHSelect(option.id, factor.id, 'H')}
                      >
                        <Text style={[
                          styles.lmhText,
                          { color: currentMode === 'H' ? COLORS.white : LMH_VALUES.H.color },
                        ]}>H</Text>
                      </TouchableOpacity>

                      {/* Custom % toggle/input */}
                      {isCustom ? (
                        <View style={[styles.customInputContainer, { backgroundColor: COLORS.primary }]}>
                          <TextInput
                            style={[styles.customPercentInput, { color: COLORS.white }]}
                            value={getCustomInputValue(option.id, factor.id)}
                            onChangeText={(text) => handleCustomInputChange(option.id, factor.id, text)}
                            onBlur={() => handleCustomInputBlur(option.id, factor.id)}
                            keyboardType="numeric"
                            maxLength={3}
                            placeholderTextColor="rgba(255,255,255,0.6)"
                            placeholder="0"
                          />
                          <Text style={[styles.customPercentSign, { color: COLORS.white }]}>%</Text>
                        </View>
                      ) : (
                        <TouchableOpacity
                          style={[
                            styles.lmhButton,
                            styles.customButton,
                            currentMode === 'custom' && styles.customButtonActive,
                          ]}
                          onPress={() => handleCustomSelect(option.id, factor.id)}
                        >
                          <Text style={[
                            styles.lmhText,
                            { color: currentMode === 'custom' ? COLORS.white : COLORS.primary },
                          ]}>%</Text>
                        </TouchableOpacity>
                      )}

                      {/* Display current % with auto indicator */}
                      <View style={[
                        styles.currentValueBadge,
                        !hasValue && styles.currentValueBadgeEmpty,
                        currentMode === 'auto' && styles.currentValueBadgeAuto,
                      ]}>
                        {hasValue ? (
                          <View style={styles.percentBadgeInner}>
                            {currentMode === 'auto' && (
                              <Ionicons name="flash" size={10} color={currentMode === 'auto' ? '#6366F1' : COLORS.textSecondary} />
                            )}
                            <Text style={[
                              styles.currentValueText,
                              currentMode === 'auto' && styles.currentValueTextAuto,
                            ]}>{currentValue}%</Text>
                          </View>
                        ) : (
                          <Text style={styles.currentValueTextEmpty}>--</Text>
                        )}
                      </View>
                    </View>
                  </View>
                );
              })}
          </Card>
          );
        })}

        <View style={styles.navButtons}>
          <TouchableOpacity style={styles.backButton} onPress={() => setCurrentStep(6)}>
            <Ionicons name="arrow-back" size={20} color={COLORS.textSecondary} />
            <Text style={styles.backButtonText}>Back</Text>
          </TouchableOpacity>
          <GradientButton
            title="View Results"
            onPress={() => setCurrentStep(8)}
            style={styles.nextButton}
          />
        </View>
      </View>
    );
  };

  const renderStep8 = () => {
    // Use dynamic calculation with clamping instead of stored worth_percentage
    const optionsWithDynamicWorth = decision.options.map(option => ({
      ...option,
      dynamic_worth: calculateDynamicWorth(option).worth,
    }));
    const sortedOptions = [...optionsWithDynamicWorth].sort(
      (a, b) => b.dynamic_worth - a.dynamic_worth
    );
    const bestOption = sortedOptions[0];

    return (
      <View style={styles.stepContent}>
        <Text style={styles.stepTitle}>Step 8-10: Final Decision</Text>
        <Text style={styles.stepDescription}>
          Based on your analysis, here are your options ranked by worth percentage.
        </Text>

        {sortedOptions.map((option, index) => (
          <Card
            key={option.id}
            style={[
              styles.resultCard,
              index === 0 && styles.resultCardBest,
            ]}
          >
            <View style={styles.resultHeader}>
              <View style={styles.resultRank}>
                <Text style={styles.rankText}>#{index + 1}</Text>
              </View>
              <View style={styles.resultInfo}>
                <Text style={styles.resultName}>{option.name}</Text>
                <Text style={styles.resultWorth}>
                  Worth: {option.dynamic_worth.toFixed(1)}%
                </Text>
              </View>
              {index === 0 && (
                <View style={styles.bestBadge}>
                  <Ionicons name="trophy" size={16} color={COLORS.warning} />
                  <Text style={styles.bestText}>Best</Text>
                </View>
              )}
            </View>

            {decision.chosen_option_id !== option.id && (
              <View style={styles.selectButtons}>
                <TouchableOpacity
                  style={styles.selectButton}
                  onPress={() => selectOption(option.id, 'obvious')}
                >
                  <Text style={styles.selectButtonText}>Select as Final Choice</Text>
                </TouchableOpacity>
              </View>
            )}

            {decision.chosen_option_id === option.id && (
              <View style={styles.selectedBadge}>
                <Ionicons name="checkmark-circle" size={20} color={COLORS.success} />
                <Text style={styles.selectedText}>Selected ({decision.decision_case})</Text>
              </View>
            )}
          </Card>
        ))}

        <View style={styles.caseInfo}>
          <Text style={styles.caseTitle}>Decision Cases:</Text>
          <Text style={styles.caseItem}>• Case 1 (Obvious): Clear winner, choose it</Text>
          <Text style={styles.caseItem}>• Case 2 (Trial): Consider if option can improve</Text>
          <Text style={styles.caseItem}>• Case 3 (Unavoidable): Accept best available</Text>
        </View>

        <GradientButton
          title={decision.status === 'completed' ? 'Decision Completed' : 'Back to Analysis'}
          onPress={() => decision.status === 'completed' ? router.back() : setCurrentStep(7)}
          variant={decision.status === 'completed' ? 'accent' : 'primary'}
          style={styles.finalButton}
        />
      </View>
    );
  };

  const renderCurrentStep = () => {
    switch (currentStep) {
      case 2:
        return renderStep2();
      case 3:
        return renderStep3();
      case 4:
        return renderStep4();
      case 5:
        return renderStep5();
      case 6:
        return renderStep6();
      case 7:
        return renderStep7();
      case 8:
      case 9:
      case 10:
        return renderStep8();
      default:
        return renderStep2();
    }
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        <View style={styles.titleSection}>
          <Text style={styles.decisionTitle} numberOfLines={1}>{decision.title}</Text>
          <View style={styles.headerStatusBadge}>
            <Text style={styles.headerStatusText}>
              Step {currentStep}/10
            </Text>
          </View>
        </View>
        {renderStepIndicator()}
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          {renderCurrentStep()}
        </ScrollView>
        {/* Universal voice input panel - rendered outside ScrollView for all steps */}
        {currentStep !== 5 && (
          <VoiceStepInput
            step={currentStep}
            factors={decision.factors}
            options={decision.options.map(o => ({ id: o.id, name: o.name }))}
            onCommand={handleUniversalVoiceCommand}
          />
        )}
      </KeyboardAvoidingView>
      {/* Share Step Modal */}
      <ShareStepModal
        visible={shareModalVisible}
        onClose={() => setShareModalVisible(false)}
        decisionId={id as string}
        stepNumber={currentStep}
        stepName={`Step ${currentStep}`}
        onShareSuccess={() => { fetchDecision(); }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  keyboardView: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  titleSection: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: COLORS.white,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
    gap: 8,
  },
  headerStatusBadge: {
    backgroundColor: COLORS.primary,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  headerStatusText: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.white,
  },
  decisionTitle: {
    flex: 1,
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  stepIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    backgroundColor: COLORS.white,
  },
  stepDot: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: COLORS.background,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
    borderWidth: 2,
    borderColor: COLORS.border,
  },
  stepDotActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  stepDotCurrent: {
    borderColor: COLORS.accent,
    borderWidth: 3,
  },
  stepDotText: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.textSecondary,
  },
  stepDotTextActive: {
    color: COLORS.white,
  },
  savingIndicator: {
    marginLeft: 8,
  },
  shareStepBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: 'rgba(142,36,170,0.1)',
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: 6,
  },
  scrollContent: {
    padding: 16,
  },
  stepContent: {
    flex: 1,
  },
  stepTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: COLORS.textPrimary,
    marginBottom: 8,
  },
  stepDescription: {
    fontSize: 14,
    color: COLORS.textSecondary,
    lineHeight: 20,
    marginBottom: 20,
  },
  sectionLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.primary,
    marginBottom: 8,
    marginTop: 8,
  },
  factorCard: {
    marginBottom: 8,
    padding: 12,
  },
  factorHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  factorName: {
    fontSize: 15,
    fontWeight: '500',
    color: COLORS.textPrimary,
    flex: 1,
  },
  categoryButtons: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 10,
  },
  categoryButton: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: COLORS.border,
    alignItems: 'center',
  },
  categoryButtonActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  categoryText: {
    fontSize: 13,
    fontWeight: '600',
    color: COLORS.textSecondary,
  },
  categoryTextActive: {
    color: COLORS.white,
  },
  addFactorRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 8,
    marginBottom: 16,
  },
  addInput: {
    flex: 1,
    height: 48,
    backgroundColor: COLORS.white,
    borderRadius: 12,
    paddingHorizontal: 16,
    fontSize: 15,
    color: COLORS.textPrimary,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  addButton: {
    width: 48,
    height: 48,
    borderRadius: 12,
    backgroundColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  // Reorder styles for Step 4
  reorderCard: {
    marginBottom: 8,
    padding: 12,
  },
  reorderRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  reorderRank: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  rankNumber: {
    fontSize: 14,
    fontWeight: '700',
    color: COLORS.white,
  },
  reorderName: {
    flex: 1,
    fontSize: 15,
    fontWeight: '500',
    color: COLORS.textPrimary,
  },
  reorderButtons: {
    flexDirection: 'row',
    gap: 4,
  },
  arrowButton: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: COLORS.background,
    justifyContent: 'center',
    alignItems: 'center',
  },
  arrowButtonDisabled: {
    opacity: 0.5,
  },
  tipBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: 'rgba(142, 36, 170, 0.08)',
    borderRadius: 12,
    padding: 12,
    marginTop: 16,
    gap: 8,
  },
  tipText: {
    flex: 1,
    fontSize: 13,
    color: COLORS.textSecondary,
    lineHeight: 18,
  },
  // Rating display styles for Step 5
  ratingCard: {
    marginBottom: 8,
    padding: 12,
  },
  ratingHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  ratingRank: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 10,
  },
  ratingBadge: {
    backgroundColor: COLORS.primary,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 10,
  },
  ratingBadgeText: {
    fontSize: 14,
    fontWeight: '700',
    color: COLORS.white,
  },
  ratingBarContainer: {
    height: 6,
    backgroundColor: COLORS.divider,
    borderRadius: 3,
    overflow: 'hidden',
  },
  ratingBarFill: {
    height: '100%',
    backgroundColor: COLORS.primary,
    borderRadius: 3,
  },
  // Gap selector styles (Step 5)
  gapSelectorCard: {
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  gapHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  gapSelectorTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: COLORS.textPrimary,
  },
  gapCurrentBadge: {
    backgroundColor: 'rgba(142,36,170,0.1)',
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 12,
  },
  gapCurrentBadgeText: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.primary,
  },
  gapChipsScroll: {
    marginTop: 6,
  },
  gapChipsRow: {
    flexDirection: 'row',
    gap: 6,
    paddingRight: 8,
  },
  gapChip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: COLORS.border,
    backgroundColor: COLORS.white,
  },
  gapChipActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  gapChipWarn: {
    borderColor: '#FCD34D',
    backgroundColor: 'rgba(245,158,11,0.05)',
  },
  gapChipWarnActive: {
    backgroundColor: '#F59E0B',
    borderColor: '#F59E0B',
  },
  gapChipText: {
    fontSize: 13,
    fontWeight: '600',
    color: COLORS.textSecondary,
  },
  gapChipTextActive: {
    color: COLORS.white,
  },
  gapChipTextWarn: {
    color: '#D97706',
  },
  gapChipTextWarnActive: {
    color: COLORS.white,
  },
  gapWarningBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 10,
    padding: 10,
    backgroundColor: 'rgba(245,158,11,0.08)',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#FCD34D',
  },
  gapWarningText: {
    flex: 1,
    fontSize: 12,
    color: '#92400E',
    lineHeight: 17,
  },
  perFactorGapRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    gap: 6,
  },
  perFactorGapLabel: {
    fontSize: 11,
    fontWeight: '500',
    color: COLORS.textMuted,
    minWidth: 80,
  },
  gapChipSmall: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: COLORS.white,
  },
  gapChipSmallActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  gapChipSmallWarn: {
    borderColor: '#FCD34D',
    backgroundColor: 'rgba(245,158,11,0.05)',
  },
  gapChipSmallWarnActive: {
    backgroundColor: '#F59E0B',
    borderColor: '#F59E0B',
  },
  gapChipSmallText: {
    fontSize: 10,
    fontWeight: '600',
    color: COLORS.textSecondary,
  },
  gapChipSmallTextActive: {
    color: COLORS.white,
  },
  gapChipSmallTextWarn: {
    color: '#D97706',
  },
  gapChipSmallTextWarnActive: {
    color: COLORS.white,
  },
  baseRatingNote: {
    fontSize: 11,
    color: COLORS.textMuted,
    fontStyle: 'italic',
    marginTop: 6,
  },
  categoryBadgeSmall: {
    width: 20,
    height: 20,
    borderRadius: 10,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 4,
  },
  catBadgePrimary: {
    backgroundColor: 'rgba(142,36,170,0.1)',
  },
  catBadgeSecondary: {
    backgroundColor: 'rgba(0,128,128,0.1)',
  },
  categoryBadgeSmallText: {
    fontSize: 10,
    fontWeight: '700',
    color: COLORS.textSecondary,
  },
  ratingSummaryCard: {
    padding: 14,
    marginTop: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  ratingSummaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 5,
  },
  ratingSummaryLabel: {
    fontSize: 13,
    color: COLORS.textSecondary,
  },
  ratingSummaryValue: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  optionCard: {
    marginBottom: 8,
    padding: 12,
  },
  optionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  optionName: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.textPrimary,
    flex: 1,
  },
  assessmentCard: {
    marginBottom: 12,
    padding: 16,
  },
  assessmentHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.divider,
  },
  worthBadge: {
    backgroundColor: COLORS.primary,
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  worthText: {
    fontSize: 14,
    fontWeight: '700',
    color: COLORS.white,
  },
  assessmentRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  assessmentLabelRow: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  assessmentLabel: {
    fontSize: 14,
    color: COLORS.textPrimary,
  },
  assessmentRating: {
    fontSize: 12,
    color: COLORS.textMuted,
  },
  assessmentInput: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  percentInput: {
    width: 50,
    height: 32,
    backgroundColor: COLORS.background,
    borderRadius: 6,
    textAlign: 'center',
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  percentSign: {
    fontSize: 14,
    color: COLORS.textSecondary,
    marginLeft: 4,
  },
  resultCard: {
    marginBottom: 12,
    padding: 16,
  },
  resultCardBest: {
    borderWidth: 2,
    borderColor: COLORS.success,
  },
  resultHeader: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  resultRank: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: COLORS.background,
    justifyContent: 'center',
    alignItems: 'center',
  },
  rankText: {
    fontSize: 14,
    fontWeight: '700',
    color: COLORS.textPrimary,
  },
  resultInfo: {
    flex: 1,
    marginLeft: 12,
  },
  resultName: {
    fontSize: 16,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  resultWorth: {
    fontSize: 14,
    color: COLORS.textSecondary,
    marginTop: 2,
  },
  bestBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(245, 158, 11, 0.1)',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    gap: 4,
  },
  bestText: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.warning,
  },
  selectButtons: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: COLORS.divider,
  },
  selectButton: {
    backgroundColor: COLORS.primary,
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: 'center',
  },
  selectButtonText: {
    color: COLORS.white,
    fontSize: 14,
    fontWeight: '600',
  },
  selectedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: COLORS.divider,
    gap: 6,
  },
  selectedText: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.success,
  },
  caseInfo: {
    backgroundColor: COLORS.white,
    borderRadius: 12,
    padding: 16,
    marginTop: 8,
  },
  caseTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginBottom: 8,
  },
  caseItem: {
    fontSize: 13,
    color: COLORS.textSecondary,
    lineHeight: 20,
  },
  navButtons: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 16,
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  backButtonText: {
    fontSize: 14,
    color: COLORS.textSecondary,
  },
  nextButton: {
    flex: 1,
    marginLeft: 16,
  },
  continueButton: {
    marginTop: 8,
  },
  finalButton: {
    marginTop: 20,
    marginBottom: 32,
  },
  // LMH Assessment Styles
  legendCard: {
    marginBottom: 16,
    padding: 12,
  },
  voiceInputRow: {
    marginBottom: 12,
    paddingVertical: 4,
  },
  voiceHintBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: 'rgba(142, 36, 170, 0.06)',
    borderRadius: 10,
    padding: 10,
    borderWidth: 1,
    borderColor: 'rgba(142, 36, 170, 0.12)',
  },
  voiceHint: {
    fontSize: 12,
    color: COLORS.textMuted,
    flex: 1,
    fontStyle: 'italic',
  },
  legendTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
    marginBottom: 8,
    textAlign: 'center',
  },
  legendRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  legendDot: {
    width: 16,
    height: 16,
    borderRadius: 8,
  },
  legendText: {
    fontSize: 12,
    color: COLORS.textSecondary,
    fontWeight: '500',
  },
  assessmentFactorContainer: {
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.divider,
  },
  unitValueRow: {
    marginTop: 6,
    marginBottom: 8,
  },
  unitValueInput: {
    height: 36,
    backgroundColor: COLORS.background,
    borderRadius: 8,
    paddingHorizontal: 12,
    fontSize: 13,
    color: COLORS.textPrimary,
  },
  // Unit selector styles (Step 2)
  unitSelectorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    gap: 6,
  },
  unitSelectorLabel: {
    fontSize: 12,
    fontWeight: '500',
    color: COLORS.textMuted,
    minWidth: 30,
  },
  // Expected value & operator styles (Step 2)
  expectedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 10,
    gap: 6,
  },
  expectedLabel: {
    fontSize: 12,
    fontWeight: '500',
    color: COLORS.textMuted,
    minWidth: 55,
  },
  expectedInput: {
    flex: 1,
    height: 36,
    backgroundColor: COLORS.background,
    borderRadius: 8,
    paddingHorizontal: 12,
    fontSize: 14,
    color: COLORS.textPrimary,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  dataTypeBadge: {
    backgroundColor: 'rgba(99,102,241,0.12)',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
  },
  dataTypeBadgeText: {
    backgroundColor: 'rgba(16,185,129,0.12)',
  },
  dataTypeBadgeLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: COLORS.textSecondary,
  },
  operatorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    gap: 6,
  },
  operatorLabel: {
    fontSize: 12,
    fontWeight: '500',
    color: COLORS.textMuted,
    minWidth: 55,
  },
  operatorChipsContainer: {
    flexDirection: 'row',
    gap: 5,
    paddingRight: 8,
  },
  operatorChip: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 14,
    borderWidth: 1.5,
    borderColor: COLORS.border,
    backgroundColor: COLORS.white,
  },
  operatorChipActive: {
    backgroundColor: '#6366F1',
    borderColor: '#6366F1',
  },
  operatorChipText: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.textSecondary,
  },
  operatorChipTextActive: {
    color: COLORS.white,
  },
  criteriaPreview: {
    backgroundColor: 'rgba(99,102,241,0.1)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
    marginRight: 8,
  },
  criteriaPreviewText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#6366F1',
  },
  unitChipsScroll: {
    flex: 1,
  },
  unitChipsContainer: {
    flexDirection: 'row',
    gap: 5,
    paddingRight: 8,
  },
  unitChip: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: COLORS.border,
    backgroundColor: COLORS.background,
  },
  unitChipActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  unitChipClear: {
    backgroundColor: 'rgba(239,68,68,0.08)',
    borderColor: '#EF4444',
    paddingHorizontal: 6,
  },
  unitChipCustom: {
    borderStyle: 'dashed' as any,
    borderColor: COLORS.primary,
  },
  unitChipText: {
    fontSize: 11,
    fontWeight: '600',
    color: COLORS.textSecondary,
  },
  unitChipTextActive: {
    color: COLORS.white,
  },
  unitBadgeSmall: {
    backgroundColor: 'rgba(142,36,170,0.1)',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
    marginRight: 8,
  },
  unitBadgeSmallText: {
    fontSize: 11,
    fontWeight: '600',
    color: COLORS.primary,
  },
  customUnitRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    gap: 8,
  },
  customUnitInput: {
    flex: 1,
    height: 36,
    backgroundColor: COLORS.background,
    borderRadius: 8,
    paddingHorizontal: 12,
    fontSize: 13,
    color: COLORS.textPrimary,
    borderWidth: 1,
    borderColor: COLORS.primary,
  },
  customUnitApplyBtn: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: COLORS.primary,
    justifyContent: 'center',
    alignItems: 'center',
  },
  // Step 7 - Separated actual value + unit
  actualValueRow: {
    marginTop: 6,
    marginBottom: 8,
  },
  actualValueInputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.background,
    borderRadius: 8,
    overflow: 'hidden',
  },
  actualValueInput: {
    flex: 1,
    height: 38,
    paddingHorizontal: 12,
    fontSize: 14,
    color: COLORS.textPrimary,
  },
  unitSuffix: {
    backgroundColor: 'rgba(142,36,170,0.1)',
    paddingHorizontal: 10,
    height: 38,
    justifyContent: 'center',
    alignItems: 'center',
    borderLeftWidth: 1,
    borderLeftColor: COLORS.border,
  },
  unitSuffixText: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.primary,
  },
  factorUnitBadge: {
    backgroundColor: 'rgba(142,36,170,0.1)',
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 8,
    marginLeft: 6,
  },
  factorUnitBadgeText: {
    fontSize: 10,
    fontWeight: '600',
    color: COLORS.primary,
  },
  expectedCriteriaBadge: {
    backgroundColor: 'rgba(99,102,241,0.1)',
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 8,
    marginLeft: 4,
  },
  expectedCriteriaText: {
    fontSize: 9,
    fontWeight: '600',
    color: '#6366F1',
  },
  currentValueBadgeAuto: {
    backgroundColor: 'rgba(99,102,241,0.12)',
    borderWidth: 1,
    borderColor: '#6366F1',
  },
  currentValueTextAuto: {
    color: '#6366F1',
    fontWeight: '700',
  },
  percentBadgeInner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
  },
  lmhContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  lmhButton: {
    width: 40,
    height: 40,
    borderRadius: 8,
    borderWidth: 2,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: COLORS.white,
  },
  lmhText: {
    fontSize: 16,
    fontWeight: '700',
  },
  customButton: {
    borderColor: COLORS.primary,
  },
  customButtonActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  customInputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: COLORS.background,
    borderRadius: 8,
    paddingHorizontal: 8,
    borderWidth: 2,
    borderColor: COLORS.primary,
  },
  customPercentInput: {
    width: 40,
    height: 36,
    textAlign: 'center',
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.textPrimary,
  },
  customPercentSign: {
    fontSize: 14,
    color: COLORS.primary,
    fontWeight: '600',
  },
  currentValueBadge: {
    marginLeft: 'auto',
    backgroundColor: COLORS.primary,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 12,
  },
  currentValueBadgeEmpty: {
    backgroundColor: COLORS.textMuted,
  },
  currentValueText: {
    fontSize: 13,
    fontWeight: '700',
    color: COLORS.white,
  },
  currentValueTextEmpty: {
    fontSize: 13,
    fontWeight: '700',
    color: COLORS.white,
  },
  worthBadgeEmpty: {
    backgroundColor: COLORS.textMuted,
  },
  worthTextEmpty: {
    fontSize: 14,
    fontWeight: '700',
    color: COLORS.white,
  },
  assessmentProgress: {
    marginBottom: 8,
  },
  progressText: {
    fontSize: 12,
    color: COLORS.textSecondary,
    fontStyle: 'italic',
  },
});
