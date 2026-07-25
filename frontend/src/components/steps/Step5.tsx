import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, ActivityIndicator, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../constants/colors';
import { Card } from '../Card';
import { GradientButton } from '../GradientButton';
import { useDecision } from '../../context/DecisionContext';
import { styles } from '../../styles/decisionStyles';
import { GAP_PRESETS, STANDARD_GAP, calculateRatingsFromOrder } from '../../utils/decisionHelpers';
import api from '../../utils/api';
import { showAlert } from '../../utils/alert';
import { DeepImportBudgetPicker } from '../DeepImportBudgetPicker';
import { useAiTouchpoint } from '../../utils/aiEstimates';

export default function Step5() {
  const { decision, saveDecision, applyRatingsAndContinue, setCurrentStep, prefillBestOptions } = useDecision();
  const aiBestOptionsEnabled = useAiTouchpoint('tp_best_options');
  const [aiLoading, setAiLoading] = useState(false);

  // "Find My Best Options" — persists current ratings, asks AI (+ Solution Store)
  // for the top 3-5 options tailored to the life area & prioritized factors,
  // prefills them into Step 6 for review, then advances.
  const handleFindBestOptions = async () => {
    if (aiLoading) return;
    setAiLoading(true);
    try {
      const factorsWithRatings = calculateRatingsFromOrder(decision.factors, !!decision.equal_weightage);
      await saveDecision({ factors: factorsWithRatings });
      const res = await api.post('/ai/find-best-options', { decision_id: decision.id });
      const opts = res.data?.options || [];
      if (opts.length === 0) {
        const unavailable = res.data?.used_model == null;
        showAlert(
          unavailable ? 'AI temporarily unavailable' : 'No suggestions',
          unavailable
            ? 'Could not reach the AI service right now. Please try again shortly, or add options manually.'
            : 'AI could not find options this time. You can add options manually in the next step.'
        );
        setCurrentStep(6);
        return;
      }
      prefillBestOptions(opts);
      setCurrentStep(6);
    } catch (e: any) {
      showAlert('Could not fetch options', e?.response?.data?.detail || 'Please try again, or add options manually.');
    } finally {
      setAiLoading(false);
    }
  };

  const recalculated = calculateRatingsFromOrder(decision.factors, !!decision.equal_weightage);
  const topLevelRecalc = recalculated.filter(f => !f.parent_id);
  const sortedFactors = [...topLevelRecalc].sort((a, b) => b.rating - a.rating);
  const highestRating = sortedFactors.length > 0 ? sortedFactors[0].rating : 100;

  const primaryFactors = topLevelRecalc.filter(f => f.category === 'primary').sort((a, b) => a.order - b.order);
  const secondaryFactors = topLevelRecalc.filter(f => f.category === 'secondary').sort((a, b) => a.order - b.order);
  const orderedFromLowest = [
    ...secondaryFactors.slice().reverse(),
    ...primaryFactors.slice().reverse(),
  ];

  const handleFactorGapChange = (factorId: string, multiplier: number) => {
    const updatedFactors = decision.factors.map(f =>
      f.id === factorId ? { ...f, gap_multiplier: multiplier } : f
    );
    const recalced = calculateRatingsFromOrder(updatedFactors, !!decision.equal_weightage);
    saveDecision({ factors: recalced });
  };

  const exceedsLimit = highestRating > 100;
  const equalWeightage = !!decision.equal_weightage;

  return (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Step 5: Rate Factor Importance</Text>
      <Text style={[styles.stepDescription, equalWeightage && { opacity: 0.5 }]}>
        Adjust each factor&apos;s gap from the one below it. Standard gap = {STANDARD_GAP} pts. Higher gaps amplify how much more important that factor is.
      </Text>

      {/* Equal Weightage banner — the gap ladder is bypassed while this
          mode is on (Step 4 toggle). Show a clear callout instead of
          silently accepting chip taps that don't affect the rating. */}
      {equalWeightage && (
        <View style={{
          flexDirection: 'row', alignItems: 'center', gap: 10,
          backgroundColor: '#EDE7F6', borderWidth: 1, borderColor: '#D1C4E9',
          borderRadius: 12, padding: 12, marginBottom: 12,
        }}>
          <Ionicons name="lock-closed" size={16} color={COLORS.primary} />
          <Text style={{ flex: 1, fontSize: 12, color: COLORS.textPrimary, lineHeight: 17 }}>
            <Text style={{ fontWeight: '700' }}>Equal Weightage is ON</Text> — every Mandatory factor is fixed at 20 and every Optional at 10. The per-pair gap multipliers below are disabled. Turn Equal Weightage OFF (Step 4) to re-enable them.
          </Text>
        </View>
      )}

      {exceedsLimit && (
        <View style={styles.gapWarningBox}>
          <Ionicons name="warning" size={16} color="#F59E0B" />
          <Text style={styles.gapWarningText}>
            Top rating ({highestRating}) exceeds 100%. Requires admin/account-level approval for exceptional cases.
          </Text>
        </View>
      )}

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

            {!isLowest ? (
              <View style={[styles.perFactorGapRow, equalWeightage && { opacity: 0.4 }]}>
                <Text style={styles.perFactorGapLabel}>
                  Gap from {belowFactor?.name || 'below'}: {equalWeightage ? '—' : `+${gapPts}`}
                </Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flex: 1 }} scrollEnabled={!equalWeightage}>
                  <View style={styles.gapChipsRow} pointerEvents={equalWeightage ? 'none' : 'auto'}>
                    {GAP_PRESETS.map((preset) => (
                      <TouchableOpacity
                        key={preset.value}
                        disabled={equalWeightage}
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
              <Text style={styles.baseRatingNote}>
                {equalWeightage
                  ? `Flat rating (Equal Weightage) · ${factor.category === 'primary' ? 20 : 10}`
                  : `Base rating: ${STANDARD_GAP}`}
              </Text>
            )}
          </Card>
        );
      })}

      <Card style={styles.ratingSummaryCard}>
        <View style={styles.ratingSummaryRow}>
          <Text style={styles.ratingSummaryLabel}>Rating range</Text>
          <Text style={[styles.ratingSummaryValue, exceedsLimit && { color: '#F59E0B', fontWeight: '700' as any }]}>
            {STANDARD_GAP} → {highestRating}
          </Text>
        </View>
        <View style={styles.ratingSummaryRow}>
          <Text style={styles.ratingSummaryLabel}>Factors</Text>
          <Text style={styles.ratingSummaryValue}>{topLevelRecalc.length}</Text>
        </View>
      </Card>

      <TouchableOpacity
        style={[localS.aiBtn, aiLoading && { opacity: 0.7 }, !aiBestOptionsEnabled && { display: 'none' }]}
        onPress={handleFindBestOptions}
        disabled={aiLoading || !aiBestOptionsEnabled}
        activeOpacity={0.85}
        accessibilityLabel="Find My Best Options with AI"
      >
        {aiLoading
          ? <ActivityIndicator size="small" color="#FFF" />
          : <Ionicons name="sparkles" size={18} color="#FFF" />}
        <Text style={localS.aiBtnText}>
          {aiLoading ? 'Finding your best options…' : 'Find My Best Options'}
        </Text>
      </TouchableOpacity>
      {aiBestOptionsEnabled && (
        <Text style={localS.aiHint}>
          AI picks the top options for this Life Area & your prioritized factors (incl. matching Solution Store items). Review &amp; remove any in the next step.
        </Text>
      )}

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

      {/* Wave 2 (#8b) — Deep-Import auto-rank prompt. Renders nothing
          unless `decision.deep_import_pending_rank` is true, in which case
          it auto-opens a modal that lets the user pick a budget and jumps
          straight to Step 8 with the top-N options. */}
      <DeepImportBudgetPicker />
    </View>
  );
}

const localS = StyleSheet.create({
  aiBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#7C3AED',
    borderRadius: 12,
    paddingVertical: 13,
    paddingHorizontal: 16,
    marginTop: 8,
    shadowColor: '#7C3AED',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.25,
    shadowRadius: 6,
    elevation: 3,
  },
  aiBtnText: { color: '#FFF', fontSize: 15, fontWeight: '800' },
  aiHint: { fontSize: 11, color: COLORS.textMuted, textAlign: 'center', marginTop: 6, marginBottom: 4, lineHeight: 16, paddingHorizontal: 8 },
});
