import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../constants/colors';
import { Card } from '../Card';
import { GradientButton } from '../GradientButton';
import { useDecision } from '../../context/DecisionContext';
import { styles } from '../../styles/decisionStyles';

export default function Step3() {
  const { decision, saveDecision, setCurrentStep } = useDecision();
  const topLevelFactors = decision.factors.filter(f => !f.parent_id);

  const classifyFactorWithChildren = (factorId: string, category: 'primary' | 'secondary') => {
    const updatedFactors = decision.factors.map(f => {
      if (f.id === factorId || f.parent_id === factorId) return { ...f, category };
      return f;
    });
    saveDecision({ factors: updatedFactors });
  };

  return (
    <View style={styles.stepContent}>
      <Text style={styles.stepTitle}>Step 3: Classify Factors</Text>
      <Text style={styles.stepDescription}>
        Categorize each factor as Primary (essential) or Secondary (important but not critical).
      </Text>

      {topLevelFactors.map((factor) => (
        <Card key={factor.id} style={styles.factorCard}>
          <Text style={styles.factorName}>{factor.name}</Text>
          <View style={styles.categoryButtons}>
            <TouchableOpacity
              style={[styles.categoryButton, factor.category === 'primary' && styles.categoryButtonActive]}
              onPress={() => classifyFactorWithChildren(factor.id, 'primary')}
            >
              <Text style={[styles.categoryText, factor.category === 'primary' && styles.categoryTextActive]}>Primary</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.categoryButton, factor.category === 'secondary' && styles.categoryButtonActive]}
              onPress={() => classifyFactorWithChildren(factor.id, 'secondary')}
            >
              <Text style={[styles.categoryText, factor.category === 'secondary' && styles.categoryTextActive]}>Secondary</Text>
            </TouchableOpacity>
          </View>
        </Card>
      ))}

      <View style={styles.navButtons}>
        <TouchableOpacity style={styles.backButton} onPress={() => setCurrentStep(2)}>
          <Ionicons name="arrow-back" size={20} color={COLORS.textSecondary} />
          <Text style={styles.backButtonText}>Back</Text>
        </TouchableOpacity>
        <GradientButton title="Prioritize Factors" onPress={() => setCurrentStep(4)} style={styles.nextButton} />
      </View>
    </View>
  );
}
