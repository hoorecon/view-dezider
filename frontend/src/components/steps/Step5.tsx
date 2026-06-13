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

export default function Step5() {
  const { decision, saveDecision, applyRatingsAndContinue, setCurrentStep, prefillBestOptions } = useDecision();
  const [aiLoading, setAiLoading] = useState(false);

  // "Find My Best Options" — persists current ratings, asks AI (+ Solution Store)
  // for the top 3-5 options tailored to the life area & prioritized factors,
  // prefills them into Step 6 for review, then advances.
  const handleFindBestOptions = async () => {
    if (aiLoading) return;
    setAiLoading(true);
    try {
      const factorsWithRatings = calculateRatingsFromOrder(decision.factors, decision.rating_gap_multiplier || 1.0);
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

  const recalculated = calculateRatingsFromOrder(decision.factors);
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
    const recalced = calculateRatingsFromOrder(updatedFactors);
    saveDecision({ factors: recalced });
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
        style={[localS.aiBtn, aiLoading && { opacity: 0.7 }]}
        onPress={handleFindBestOptions}
        disabled={aiLoading}
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
      <Text style={localS.aiHint}>
        AI picks the top options for this Life Area & your prioritized factors (incl. matching Solution Store items). Review &amp; remove any in the next step.
      </Text>

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
