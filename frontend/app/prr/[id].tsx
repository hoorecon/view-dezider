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
import api from '../../src/utils/api';

interface Factor {
  id: string;
  name: string;
  category: 'primary' | 'secondary';
  rating: number;
  order: number;
  unit?: string; // e.g., "USD", "hours", "km", etc.
}

interface OptionAssessment {
  factor_id: string;
  percentage: number;
  unit_value?: string; // Actual value with unit (e.g., "50000 USD")
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
  status: string;
}

// LMH Assessment constants
const LMH_VALUES = {
  L: { label: 'Low', percentage: 25, color: '#EF4444' },    // Red
  M: { label: 'Medium', percentage: 50, color: '#F59E0B' }, // Yellow/Amber
  H: { label: 'High', percentage: 75, color: '#10B981' },   // Green
};

// Function to auto-calculate ratings based on order within each category
// Rating starts from 10 for lowest priority (last Secondary) and increments by 10
// Order: Secondary (lowest to highest) -> Primary (lowest to highest)
const calculateRatingsFromOrder = (factors: Factor[]): Factor[] => {
  const primaryFactors = factors.filter(f => f.category === 'primary').sort((a, b) => a.order - b.order);
  const secondaryFactors = factors.filter(f => f.category === 'secondary').sort((a, b) => a.order - b.order);
  
  const updatedFactors: Factor[] = [];
  
  // Total factors determines the rating range
  // We build from lowest to highest priority:
  // Secondary (reversed - last item is lowest priority) -> Primary (reversed - last item is lower priority within primary)
  
  // Create ordered list from lowest to highest priority:
  // 1. Secondary factors in reverse order (last = lowest priority)
  // 2. Primary factors in reverse order (last = lower priority within primary, but still higher than secondary)
  const orderedFromLowest = [
    ...secondaryFactors.slice().reverse(),  // Secondary: last item first (lowest priority)
    ...primaryFactors.slice().reverse(),     // Primary: last item first (lower within primary)
  ];
  
  // Assign ratings: 10, 20, 30, ... starting from lowest priority
  orderedFromLowest.forEach((factor, index) => {
    const rating = (index + 1) * 10;
    updatedFactors.push({ ...factor, rating });
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
  const [unitValues, setUnitValues] = useState<{[key: string]: string}>({});
  const [customInputValues, setCustomInputValues] = useState<{[key: string]: string}>({});

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
      } else if (response.data.factors.length > 0 && response.data.factors.some((f: Factor) => f.order !== undefined)) {
        setCurrentStep(4);
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
    const factorsWithRatings = calculateRatingsFromOrder(updatedFactors);
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
    const factorsWithRatings = calculateRatingsFromOrder(updatedFactors);
    saveDecision({ factors: factorsWithRatings });
  };

  // Apply ratings when moving to next step
  const applyRatingsAndContinue = () => {
    const factorsWithRatings = calculateRatingsFromOrder(decision!.factors);
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

  const updateAssessment = (optionId: string, factorId: string, percentage: number, mode?: 'L' | 'M' | 'H' | 'custom', unitValue?: string) => {
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

  const selectOption = (optionId: string, caseType: string) => {
    saveDecision({
      chosen_option_id: optionId,
      decision_case: caseType,
      status: 'completed',
    });
    setCurrentStep(10);
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

  const renderStepIndicator = () => (
    <View style={styles.stepIndicator}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((step) => (
          <TouchableOpacity
            key={step}
            style={[
              styles.stepDot,
              step <= currentStep && styles.stepDotActive,
              step === currentStep && styles.stepDotCurrent,
            ]}
            onPress={() => step <= currentStep && setCurrentStep(step)}
          >
            <Text
              style={[
                styles.stepDotText,
                step <= currentStep && styles.stepDotTextActive,
              ]}
            >
              {step}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
      {saving && <ActivityIndicator size="small" color={COLORS.primary} style={styles.savingIndicator} />}
    </View>
  );

  const renderStep2 = () => (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Step 2: List All Factors</Text>
      <Text style={styles.stepDescription}>
        List all logical and emotional factors that influence this decision.
      </Text>

      {decision.factors.map((factor) => (
        <Card key={factor.id} style={styles.factorCard}>
          <View style={styles.factorHeader}>
            <Text style={styles.factorName}>{factor.name}</Text>
            <TouchableOpacity onPress={() => removeFactor(factor.id)}>
              <Ionicons name="close-circle" size={22} color={COLORS.error} />
            </TouchableOpacity>
          </View>
        </Card>
      ))}

      <View style={styles.addFactorRow}>
        <TextInput
          style={styles.addInput}
          placeholder="Add a factor (e.g., Salary, Work-Life Balance)"
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
            title="Calculate & Add Options"
            onPress={applyRatingsAndContinue}
            style={styles.nextButton}
          />
        </View>
      </View>
    );
  };

  // Step 5: Show calculated ratings (read-only)
  const renderStep5 = () => {
    const primaryFactors = decision.factors
      .filter(f => f.category === 'primary')
      .sort((a, b) => a.order - b.order);
    const secondaryFactors = decision.factors
      .filter(f => f.category === 'secondary')
      .sort((a, b) => a.order - b.order);

    return (
      <View style={styles.stepContent}>
        <Text style={styles.stepTitle}>Step 5: Calculated Ratings</Text>
        <Text style={styles.stepDescription}>
          Based on your prioritization, here are the auto-calculated importance ratings.
        </Text>

        <Text style={styles.sectionLabel}>Primary Factors</Text>
        {primaryFactors.map((factor, index) => (
          <Card key={factor.id} style={styles.ratingCard}>
            <View style={styles.ratingHeader}>
              <View style={styles.ratingRank}>
                <Text style={styles.rankNumber}>{index + 1}</Text>
              </View>
              <Text style={styles.factorName}>{factor.name}</Text>
              <View style={styles.ratingBadge}>
                <Text style={styles.ratingBadgeText}>{factor.rating}</Text>
              </View>
            </View>
            <View style={styles.ratingBarContainer}>
              <View style={[styles.ratingBarFill, { width: `${factor.rating}%` }]} />
            </View>
          </Card>
        ))}

        {secondaryFactors.length > 0 && (
          <>
            <Text style={styles.sectionLabel}>Secondary Factors</Text>
            {secondaryFactors.map((factor, index) => (
              <Card key={factor.id} style={styles.ratingCard}>
                <View style={styles.ratingHeader}>
                  <View style={[styles.ratingRank, { backgroundColor: COLORS.teal }]}>
                    <Text style={styles.rankNumber}>{index + 1}</Text>
                  </View>
                  <Text style={styles.factorName}>{factor.name}</Text>
                  <View style={[styles.ratingBadge, { backgroundColor: COLORS.teal }]}>
                    <Text style={styles.ratingBadgeText}>{factor.rating}</Text>
                  </View>
                </View>
                <View style={styles.ratingBarContainer}>
                  <View style={[styles.ratingBarFill, { width: `${factor.rating}%`, backgroundColor: COLORS.teal }]} />
                </View>
              </Card>
            ))}
          </>
        )}

        <View style={styles.navButtons}>
          <TouchableOpacity style={styles.backButton} onPress={() => setCurrentStep(4)}>
            <Ionicons name="arrow-back" size={20} color={COLORS.textSecondary} />
            <Text style={styles.backButtonText}>Adjust Priority</Text>
          </TouchableOpacity>
          <GradientButton
            title="Add Options"
            onPress={() => setCurrentStep(6)}
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

  const renderStep7 = () => {
    const getAssessmentKey = (optionId: string, factorId: string) => `${optionId}_${factorId}`;
    
    const handleLMHSelect = (optionId: string, factorId: string, mode: 'L' | 'M' | 'H') => {
      const percentage = LMH_VALUES[mode].percentage;
      const key = getAssessmentKey(optionId, factorId);
      setShowCustomInput({ ...showCustomInput, [key]: false });
      setCustomInputValues({ ...customInputValues, [key]: '' }); // Clear custom input
      updateAssessment(optionId, factorId, percentage, mode, unitValues[key]);
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
      updateAssessment(optionId, factorId, percentage, 'custom', unitValues[key]);
    };

    const handleUnitValueChange = (optionId: string, factorId: string, value: string) => {
      const key = getAssessmentKey(optionId, factorId);
      setUnitValues({ ...unitValues, [key]: value });
      // Update assessment with unit value
      const currentMode = getAssessmentMode(optionId, factorId);
      const currentPercentage = getAssessmentValue(optionId, factorId);
      updateAssessment(optionId, factorId, currentPercentage, currentMode, value);
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
                const currentUnitValue = unitValues[key] || getUnitValue(option.id, factor.id);
                const hasValue = currentValue !== null;

                return (
                  <View key={factor.id} style={styles.assessmentFactorContainer}>
                    {/* Factor header with rating */}
                    <View style={styles.assessmentLabelRow}>
                      <Text style={styles.assessmentLabel}>{factor.name}</Text>
                      <Text style={styles.assessmentRating}>({factor.rating})</Text>
                    </View>

                    {/* Unit value input (optional) */}
                    <View style={styles.unitValueRow}>
                      <TextInput
                        style={styles.unitValueInput}
                        placeholder="Value (e.g., 50000 USD, 8 hours)"
                        placeholderTextColor={COLORS.textMuted}
                        value={currentUnitValue}
                        onChangeText={(value) => handleUnitValueChange(option.id, factor.id, value)}
                      />
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

                      {/* Display current % */}
                      <View style={[
                        styles.currentValueBadge,
                        !hasValue && styles.currentValueBadgeEmpty
                      ]}>
                        {hasValue ? (
                          <Text style={styles.currentValueText}>{currentValue}%</Text>
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
        </View>
        {renderStepIndicator()}
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          {renderCurrentStep()}
        </ScrollView>
      </KeyboardAvoidingView>
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
    paddingHorizontal: 16,
    paddingVertical: 8,
    backgroundColor: COLORS.white,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  decisionTitle: {
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
