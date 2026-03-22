import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../constants/colors';
import { Card } from '../Card';
import { GradientButton } from '../GradientButton';
import { useDecision } from '../../context/DecisionContext';
import { styles } from '../../styles/decisionStyles';
import type { Factor } from '../../types/decision';

export default function Step4() {
  const { decision, moveFactorUp, moveFactorDown, setCurrentStep } = useDecision();
  const topLevel = decision.factors.filter(f => !f.parent_id);
  const primaryFactors = topLevel.filter(f => f.category === 'primary').sort((a, b) => a.order - b.order);
  const secondaryFactors = topLevel.filter(f => f.category === 'secondary').sort((a, b) => a.order - b.order);

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
            <Ionicons name="chevron-up" size={20} color={index === 0 ? COLORS.textMuted : COLORS.primary} />
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.arrowButton, index === total - 1 && styles.arrowButtonDisabled]}
            onPress={() => moveFactorDown(factor.id)}
            disabled={index === total - 1}
          >
            <Ionicons name="chevron-down" size={20} color={index === total - 1 ? COLORS.textMuted : COLORS.primary} />
          </TouchableOpacity>
        </View>
      </View>
    </Card>
  );

  return (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Step 4: Prioritize Factors</Text>
      <Text style={styles.stepDescription}>
        Order factors by importance within each category. Use arrows to move factors up or down. The system will automatically calculate ratings based on your ordering.
      </Text>

      {primaryFactors.length > 0 && (
        <>
          <Text style={styles.sectionLabel}>Primary Factors (Most Important First)</Text>
          {primaryFactors.map((factor, index) => renderFactorWithReorder(factor, index, primaryFactors.length))}
        </>
      )}

      {secondaryFactors.length > 0 && (
        <>
          <Text style={[styles.sectionLabel, { marginTop: 16 }]}>Secondary Factors (Most Important First)</Text>
          {secondaryFactors.map((factor, index) => renderFactorWithReorder(factor, index, secondaryFactors.length))}
        </>
      )}

      <View style={styles.tipBox}>
        <Ionicons name="information-circle" size={20} color={COLORS.primary} />
        <Text style={styles.tipText}>
          Ratings are auto-calculated: Starting from 10 for the lowest priority factor, incrementing by 10 for each higher priority. Secondary factors get lower ratings, Primary factors get higher ratings.
        </Text>
      </View>

      <View style={styles.navButtons}>
        <TouchableOpacity style={styles.backButton} onPress={() => setCurrentStep(3)}>
          <Ionicons name="arrow-back" size={20} color={COLORS.textSecondary} />
          <Text style={styles.backButtonText}>Back</Text>
        </TouchableOpacity>
        <GradientButton title="Calculate Ratings" onPress={() => setCurrentStep(5)} style={styles.nextButton} />
      </View>
    </View>
  );
}
