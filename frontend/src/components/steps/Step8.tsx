import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../constants/colors';
import { Card } from '../Card';
import { GradientButton } from '../GradientButton';
import { useDecision } from '../../context/DecisionContext';
import { styles } from '../../styles/decisionStyles';

export default function Step8() {
  const { decision, calculateDynamicWorth, setCurrentStep } = useDecision();

  const optionsWithDynamicWorth = decision.options.map(option => ({
    ...option,
    dynamic_worth: calculateDynamicWorth(option).worth,
  }));
  const sortedOptions = [...optionsWithDynamicWorth].sort((a, b) => b.dynamic_worth - a.dynamic_worth);

  return (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Step 8: Case-1 Results</Text>
      <Text style={styles.stepDescription}>
        Options ranked by worth percentage. The highest worth option is the best as per Case-1 analysis.
      </Text>

      {sortedOptions.map((option, index) => (
        <Card key={option.id} style={[styles.resultCard, index === 0 && styles.resultCardBest]}>
          <View style={styles.resultHeader}>
            <View style={styles.resultRank}>
              <Text style={styles.rankText}>#{index + 1}</Text>
            </View>
            <View style={styles.resultInfo}>
              <Text style={styles.resultName}>{option.name}</Text>
              <Text style={styles.resultWorth}>Worth: {option.dynamic_worth.toFixed(1)}%</Text>
            </View>
            {index === 0 && (
              <View style={styles.bestBadge}>
                <Ionicons name="trophy" size={16} color={COLORS.warning} />
                <Text style={styles.bestText}>Best</Text>
              </View>
            )}
          </View>
        </Card>
      ))}

      <View style={styles.caseInfo}>
        <Text style={styles.caseTitle}>Solution Types:</Text>
        <Text style={styles.caseItem}>• Ideal Solution: 100% worth — perfect fit</Text>
        <Text style={styles.caseItem}>• Practical Solution: High worth ({'>'} 50%) — satisfactory</Text>
        <Text style={styles.caseItem}>• Unavoidable: Best available ({'<'} 50%) — limited choices</Text>
      </View>

      <View style={styles.navButtons}>
        <TouchableOpacity style={styles.backButton} onPress={() => setCurrentStep(7)}>
          <Ionicons name="arrow-back" size={20} color={COLORS.textSecondary} />
          <Text style={styles.backButtonText}>Back</Text>
        </TouchableOpacity>
        <GradientButton
          title="MPPS Analysis"
          onPress={() => setCurrentStep(9)}
          icon={<Ionicons name="rocket-outline" size={18} color={COLORS.white} />}
          style={styles.nextButton}
        />
      </View>
    </View>
  );
}
