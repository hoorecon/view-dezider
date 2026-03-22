// Shared constants and helpers for PRR Decision system
import { Factor, DecisionOption, MPPSImprovement } from '../types/decision';

// Gap multiplier presets
export const GAP_PRESETS = [
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
export const LMH_VALUES = {
  L: { label: 'Low', percentage: 25, color: '#EF4444' },
  M: { label: 'Medium', percentage: 50, color: '#F59E0B' },
  H: { label: 'High', percentage: 75, color: '#10B981' },
};

// Common unit presets for factor measurement
export const UNIT_PRESETS = [
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
export const NUMERIC_OPERATORS = [
  { label: '≥', value: '>=' },
  { label: '≤', value: '<=' },
  { label: '>', value: '>' },
  { label: '<', value: '<' },
  { label: '=', value: '=' },
  { label: '≠', value: '!=' },
];
export const TEXT_OPERATORS = [
  { label: 'Contains', value: 'contains' },
  { label: 'Starts with', value: 'starts_with' },
  { label: 'Ends with', value: 'ends_with' },
  { label: 'Equals', value: 'equals' },
  { label: '≠', value: 'not_equals' },
];

// TEPFI Elements & Layers
export const TEPFI_ELEMENTS: { key: 'T' | 'E' | 'P' | 'F' | 'I'; label: string; icon: string; color: string }[] = [
  { key: 'T', label: 'Time', icon: 'time-outline', color: '#3B82F6' },
  { key: 'E', label: 'Effort', icon: 'fitness-outline', color: '#8B5CF6' },
  { key: 'P', label: 'People', icon: 'people-outline', color: '#EC4899' },
  { key: 'F', label: 'Finance', icon: 'cash-outline', color: '#10B981' },
  { key: 'I', label: 'Infra', icon: 'business-outline', color: '#F59E0B' },
];

export const TEPFI_LAYERS: { key: 'self' | 'micro' | 'macro'; label: string; color: string }[] = [
  { key: 'self', label: 'Self', color: '#6366F1' },
  { key: 'micro', label: 'Micro', color: '#0EA5E9' },
  { key: 'macro', label: 'Macro', color: '#64748B' },
];

// Auto-sense data type from value
export const senseDataType = (value: string): 'numeric' | 'text' => {
  if (!value || value.trim() === '') return 'numeric';
  const trimmed = value.trim();
  return /^-?\d+(\.\d+)?$/.test(trimmed) ? 'numeric' : 'text';
};

// Standard gap for rating calculation
export const STANDARD_GAP = 10;

// Calculate ratings from priority order
export const calculateRatingsFromOrder = (factors: Factor[], _unused?: number): Factor[] => {
  const topLevel = factors.filter(f => !f.parent_id);
  const subFactors = factors.filter(f => !!f.parent_id);

  const primaryFactors = topLevel.filter(f => f.category === 'primary').sort((a, b) => a.order - b.order);
  const secondaryFactors = topLevel.filter(f => f.category === 'secondary').sort((a, b) => a.order - b.order);

  const orderedFromLowest = [
    ...secondaryFactors.slice().reverse(),
    ...primaryFactors.slice().reverse(),
  ];

  const updatedTopLevel: Factor[] = [];
  let currentRating = STANDARD_GAP;

  orderedFromLowest.forEach((factor, index) => {
    if (index === 0) {
      updatedTopLevel.push({ ...factor, rating: currentRating });
    } else {
      const gapMult = factor.gap_multiplier ?? 1.0;
      const gap = Math.round(STANDARD_GAP * gapMult);
      currentRating = currentRating + gap;
      updatedTopLevel.push({ ...factor, rating: currentRating });
    }
  });

  return [...updatedTopLevel, ...subFactors];
};

// Calculate dynamic worth percentage with sub-factor weighted averages
export const calculateDynamicWorth = (
  option: DecisionOption,
  factors: Factor[]
): { worth: number; assessedCount: number; totalCount: number } => {
  const topLevel = factors.filter(f => !f.parent_id);
  const totalFactors = topLevel.length;

  if (totalFactors === 0) return { worth: 0, assessedCount: 0, totalCount: 0 };

  const totalRating = topLevel.reduce((sum, f) => sum + f.rating, 0);
  if (totalRating === 0) return { worth: 0, assessedCount: 0, totalCount: totalFactors };

  const getEffectivePercentage = (factor: Factor): number | null => {
    const subs = factors.filter(f => f.parent_id === factor.id);

    if (subs.length === 0) {
      const assessment = option.assessments.find(a => a.factor_id === factor.id);
      return assessment?.percentage ?? null;
    }

    let weightedSum = 0;
    let totalWeight = 0;
    let anyAssessed = false;

    for (const sub of subs) {
      const subAssessment = option.assessments.find(a => a.factor_id === sub.id);
      const subWeight = sub.weight || 0;
      if (subAssessment?.percentage !== undefined && subAssessment?.percentage !== null && subWeight > 0) {
        weightedSum += (subAssessment.percentage * subWeight) / 100;
        totalWeight += subWeight;
        anyAssessed = true;
      }
    }

    if (!anyAssessed || totalWeight === 0) return null;
    return Math.round(weightedSum * (100 / totalWeight) * 10) / 10;
  };

  let weightedSum = 0;
  let assessedCount = 0;

  for (const factor of topLevel) {
    const pct = getEffectivePercentage(factor);
    if (pct !== null) {
      const clampedPercentage = Math.min(100, Math.max(0, pct));
      weightedSum += factor.rating * (clampedPercentage / 100);
      assessedCount++;
    }
  }

  if (assessedCount === 0) return { worth: 0, assessedCount: 0, totalCount: totalFactors };

  const rawWorth = (weightedSum / totalRating) * 100;
  const worth = Math.min(100, Math.max(0, rawWorth));

  return {
    worth: Math.round(worth * 10) / 10,
    assessedCount,
    totalCount: totalFactors,
  };
};

// Get effective assessment % for a factor (handles sub-factor aggregation)
export const getFactorAssessmentPct = (
  factor: Factor,
  factors: Factor[],
  assessments: { factor_id: string; percentage?: number | null }[]
): number | null => {
  const subs = factors.filter(f => f.parent_id === factor.id);
  if (subs.length === 0) {
    const a = assessments.find(a => a.factor_id === factor.id);
    return a?.percentage ?? null;
  }
  let wSum = 0;
  let wTotal = 0;
  let any = false;
  for (const sub of subs) {
    const sa = assessments.find(a => a.factor_id === sub.id);
    const sw = sub.weight || 0;
    if (sa?.percentage !== undefined && sa?.percentage !== null && sw > 0) {
      wSum += ((sa.percentage as number) * sw) / 100;
      wTotal += sw;
      any = true;
    }
  }
  if (!any || wTotal === 0) return null;
  return Math.round(wSum * (100 / wTotal) * 10) / 10;
};
