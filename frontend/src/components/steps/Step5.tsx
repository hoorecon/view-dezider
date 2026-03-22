import React from 'react';
import { View, Text, TouchableOpacity, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../constants/colors';
import { Card } from '../Card';
import { GradientButton } from '../GradientButton';
import { useDecision } from '../../context/DecisionContext';
import { styles } from '../../styles/decisionStyles';
import { GAP_PRESETS, STANDARD_GAP, calculateRatingsFromOrder } from '../../utils/decisionHelpers';

export default function Step5() {
  const { decision, saveDecision, applyRatingsAndContinue, setCurrentStep } = useDecision();

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
}
