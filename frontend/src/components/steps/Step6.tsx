import React from 'react';
import { View, Text, TextInput, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { COLORS } from '../../constants/colors';
import { Card } from '../Card';
import { GradientButton } from '../GradientButton';
import { useDecision } from '../../context/DecisionContext';
import { styles } from '../../styles/decisionStyles';

export default function Step6() {
  const { decision, addOption, removeOption, newOptionName, setNewOptionName, setCurrentStep } = useDecision();

  return (
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
}
