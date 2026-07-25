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

// Combined list — operators are common to BOTH Quantitative & Qualitative
// factors. The editor always shows every operator; the sensible default is
// auto-selected from the expected VALUE (numeric → "≥", text → "Contains"),
// but the user can override to any operator. Text ≠/= relabelled to avoid
// clashing with the numeric ≠/= glyphs.
export const ALL_OPERATORS = [
  { label: '≥', value: '>=' },
  { label: '≤', value: '<=' },
  { label: '>', value: '>' },
  { label: '<', value: '<' },
  { label: '=', value: '=' },
  { label: '≠', value: '!=' },
  { label: 'Contains', value: 'contains' },
  { label: 'Starts with', value: 'starts_with' },
  { label: 'Ends with', value: 'ends_with' },
  { label: 'Equals', value: 'equals' },
  { label: 'Not equals', value: 'not_equals' },
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

/**
 * Parse a positive-integer count input that may also contain a simple
 * arithmetic expression — e.g. user types `1+3` meaning "1 main option +
 * 3 similar" → returns 4. Falls back to plain parseInt for normal numbers.
 * Returns `undefined` for blank / invalid / non-positive inputs.
 *
 * Accepted: digits, + - * / ( ) and whitespace only. Anything else returns
 * `undefined` (never executes arbitrary code).
 */
export const parseCountInput = (raw: string | undefined | null): number | undefined => {
  if (raw === undefined || raw === null) return undefined;
  const t = String(raw).trim();
  if (!t) return undefined;
  // Pure positive integer fast-path.
  if (/^\d+$/.test(t)) {
    const n = parseInt(t, 10);
    return Number.isFinite(n) && n > 0 ? n : undefined;
  }
  // Whitelist arithmetic only — never run anything else through eval.
  if (/^[\d+\-*/()\s.]+$/.test(t) && /[+\-*/]/.test(t)) {
    try {
      // eslint-disable-next-line no-new-func
      const v = Function(`"use strict"; return (${t});`)();
      if (typeof v === 'number' && Number.isFinite(v) && v > 0) {
        return Math.round(v);
      }
    } catch { /* invalid — fall through */ }
  }
  return undefined;
};

// Standard gap for rating calculation
export const STANDARD_GAP = 10;

// Calculate ratings from priority order.
//
// • When `equalWeightage` is true (June 2026 mode), all Primary (Mandatory/A)
//   factors get a flat rating of 20 and all Secondary (Optional/B) factors a
//   flat rating of 10 — the gap_multiplier is ignored.
// • Otherwise, we ladder bottom-up from STANDARD_GAP using each factor's
//   individual gap_multiplier (the classic behaviour).
export const calculateRatingsFromOrder = (
  factors: Factor[],
  equalWeightageOrLegacyMultiplier?: boolean | number,
): Factor[] => {
  const equalWeightage = equalWeightageOrLegacyMultiplier === true;
  const topLevel = factors.filter(f => !f.parent_id);
  const subFactors = factors.filter(f => !!f.parent_id);

  if (equalWeightage) {
    const updatedTopLevel = topLevel.map(f => ({
      ...f,
      rating: f.category === 'primary' ? 20 : 10,
    }));
    return [...updatedTopLevel, ...subFactors];
  }

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

// ── Standard variable ids (f1, f2, ...) ────────────────────────
// Assigns `variable_id = fN` to every TOP-LEVEL factor in `order` sequence.
// - Preserves ids that are already assigned (so formulas keep referencing the
//   right factor after a reorder / new factor is added at the end).
// - Sub-factors are left untouched (formulas operate at the main-factor tier).
// - Returns a new factors array; safe to pass straight into saveDecision.
export const assignVariableIds = (factors: Factor[]): Factor[] => {
  const topLevel = factors.filter(f => !f.parent_id).sort((a, b) => a.order - b.order);
  const used = new Set<string>();
  topLevel.forEach(f => { if (f.variable_id) used.add(f.variable_id); });

  let next = 1;
  const takeNext = (): string => {
    // Find the smallest fN not already taken
    while (used.has(`f${next}`)) next += 1;
    const id = `f${next}`;
    used.add(id);
    next += 1;
    return id;
  };

  const patched: Factor[] = factors.map(f => {
    if (f.parent_id) return f;
    if (f.variable_id && /^f\d+$/.test(f.variable_id)) return f;
    return { ...f, variable_id: takeNext() };
  });
  return patched;
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

  const getEffectivePercentage = (factor: Factor): number | null =>
    effectiveFactorPct(factor, factors, option.assessments);

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

/**
 * Effective satisfaction % for a (possibly parented) factor.
 *
 * Rules (sub-factor assessment is OPTIONAL):
 *  - No sub-factors → use the factor's own assessment %.
 *  - Has sub-factors, ≥1 assessed (manual % or AI/value-derived %):
 *      • if assessed subs carry weights → weighted average normalised by their
 *        total weight (the un-allocated weight is redistributed across them);
 *      • if no weights are set → the remaining % is split EQUALLY → simple mean.
 *  - Has sub-factors but NONE assessed → fall back to the parent's own direct
 *    ("general") assessment %, if the user entered one; else null (un-assessed).
 */
export const effectiveFactorPct = (
  factor: Factor,
  factors: Factor[],
  assessments: { factor_id: string; percentage?: number | null }[]
): number | null => {
  const ownPct = (): number | null => {
    const a = assessments.find(a => a.factor_id === factor.id);
    return a?.percentage ?? null;
  };

  const subs = factors.filter(f => f.parent_id === factor.id);
  if (subs.length === 0) return ownPct();

  const assessed = subs
    .map(s => ({ s, a: assessments.find(a => a.factor_id === s.id) }))
    .filter(x => x.a?.percentage !== undefined && x.a?.percentage !== null);

  // No sub-factor assessed → direct/general assessment of the main factor.
  if (assessed.length === 0) return ownPct();

  const totalWeight = assessed.reduce((sum, x) => sum + (x.s.weight || 0), 0);
  if (totalWeight > 0) {
    const wSum = assessed.reduce((sum, x) => sum + ((x.a!.percentage as number) * (x.s.weight || 0)) / 100, 0);
    return Math.round(wSum * (100 / totalWeight) * 10) / 10;
  }
  // No weights set → distribute equally (simple mean of assessed sub %s).
  const mean = assessed.reduce((sum, x) => sum + (x.a!.percentage as number), 0) / assessed.length;
  return Math.round(mean * 10) / 10;
};

// Get effective assessment % for a factor (handles sub-factor aggregation)
export const getFactorAssessmentPct = (
  factor: Factor,
  factors: Factor[],
  assessments: { factor_id: string; percentage?: number | null }[]
): number | null => effectiveFactorPct(factor, factors, assessments);
